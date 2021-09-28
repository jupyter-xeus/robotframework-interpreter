import inspect
import json
import logging
import os
import urllib.request

from robot.errors import DataError
from robot.libdocpkg import LibraryDocumentation
from robot.libraries.BuiltIn import BuiltIn

from .utils import lunr_builder, to_mime_and_metadata
from .constants import CONTEXT_LIBRARIES


class GlobalVarsListener:
    ROBOT_LISTENER_API_VERSION = 2

    variables = {}

    black_list = [
        '${/}', '${:}', '${\n}', '${DEBUG_FILE}',
        '${EXECDIR}', '${False}', '${LOG_FILE}',
        '${LOG_LEVEL}', '${None}', '${null}',
        '${OUTPUT_DIR}', '${OUTPUT_FILE}',
        '${PREV_TEST_MESSAGE}', '${PREV_TEST_NAME}',
        '${PREV_TEST_STATUS}', '${REPORT_FILE}',
        '${SPACE}', '${SUITE_DOCUMENTATION}',
        '${SUITE_MESSAGE}', '${SUITE_NAME}',
        '${SUITE_SOURCE}', '${SUITE_STATUS}',
        '${TEMPDIR}', '${True}',
        '&{SUITE_METADATA}'
    ]

    def start_suite(self, name, attributes):
        for name, value in GlobalVarsListener.variables.items():
            if name not in GlobalVarsListener.black_list:
                BuiltIn().set_global_variable(name, value)

    def end_suite(self, name, attributes):
        GlobalVarsListener.variables = BuiltIn().get_variables()


class RobotKeywordsIndexerListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self):
        self.builder = lunr_builder("dottedname", ["dottedname", "name"])
        self.index = None
        self.libraries = []
        self.keywords = {}

        self.library_import("BuiltIn", {})
        for name, keywords in CONTEXT_LIBRARIES.items():
            self._library_import(keywords, name)

    def library_import(self, alias, attributes):
        name = attributes.get("originalName") or alias

        if alias not in self.libraries:
            self.libraries.append(alias)
            try:
                lib_doc = LibraryDocumentation(name)
                self._library_import(lib_doc, alias)
            except DataError:
                pass

    def _library_import(self, lib_doc, alias):
        if isinstance(lib_doc, list):
            keywords = lib_doc
            doc_format = "REST"
        else:
            keywords = lib_doc.keywords
            doc_format = lib_doc.doc_format
        for keyword in keywords:
            keyword.doc_format = doc_format
            self.builder.add(
                {"name": keyword.name, "dottedname": f"{alias}.{keyword.name}"}
            )
            self.keywords[f"{alias}.{keyword.name}"] = keyword
        if len(self.keywords):
            self.index = self.builder.build()

    def resource_import(self, name, attributes):
        if name not in self.libraries:
            self.libraries.append(name)
            try:
                resource_doc = LibraryDocumentation(name)
                self._resource_import(resource_doc.keywords)
            except DataError:
                pass

    def _resource_import(self, keywords):
        for keyword in keywords:
            keyword.doc_format = "REST"
            self.builder.add({"name": keyword.name, "dottedname": keyword.name})
            self.keywords[keyword.name] = keyword
        if len(self.keywords):
            self.index = self.builder.build()

    def import_from_suite_data(self, suite):
        self._resource_import(suite.resource.keywords)
        try:
            for import_data in suite.resource.imports:
                attributes = {}
                if import_data.type == "Library":
                    alias = import_data.alias or import_data.name
                    attributes["originalName"] = import_data.name
                    self.library_import(alias, attributes)
                else:
                    name = import_data.name
                    self.resource_import(name, attributes)
        except AttributeError:
            pass


class StatusEventListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, callback=None):
        self.callback = callback

    def start_test(self, name, attributes):
        if self.callback is not None:
            self.callback({"test": name})

    def start_keyword(self, name, attributes):
        if self.callback is not None:
            self.callback({"keyword": name})


class ReturnValueListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self):
        self.return_value = None

    def end_keyword(self, name, attributes):
        frame = inspect.currentframe()
        while frame is not None:
            if "return_value" in frame.f_locals:
                self.return_value = frame.f_locals.get("return_value")
                break
            frame = frame.f_back

    def start_test(self, name, attributes):
        self.return_value = None

    def get_last_value(self):
        if not self.has_value(self.return_value):
            return None

        value = to_mime_and_metadata(self.return_value)
        self.return_value = None
        return value

    @staticmethod
    def has_value(value):
        try:
            return value is not None and value != "" and value != b""
        except Exception:
            return True


def clear_drivers(drivers, type_):
    remained = []
    for driver in drivers:
        if driver.get("type") != type_:
            remained.append(driver)
    drivers.clear()
    drivers.extend(remained)


def get_webdrivers(cache, type_):
    drivers = []
    for idx in range(len(cache._connections)):
        conn = cache._connections[idx]
        if conn in cache._closed:
            continue
        aliases = []
        for alias, idx_ in cache._aliases.items():
            if (idx + 1) == idx_:
                aliases.append(alias)
        drivers.append(
            dict(
                instance=conn,
                aliases=aliases,
                current=conn == cache.current,
                type=type_,
            )
        )
    return drivers


def set_webdrivers(drivers, cache, type_):
    idx = 1
    for driver in drivers:
        if driver["type"] != type_:
            continue
        cache._connections.append(driver["instance"])
        for alias in driver["aliases"]:
            cache._aliases[alias] = idx
        if driver["current"]:
            cache.current = driver["instance"]
        idx += 1


class SeleniumConnectionsListener:
    ROBOT_LISTENER_API_VERSION = 2

    NAMES = [
        "SeleniumLibrary",
        "Selenium2Library",
        "RPA.Browser.Selenium",
        "RPA.Browser",
    ]

    def __init__(self, drivers: list):
        self.drivers = drivers

    def end_suite(self, name, attributes):
        before = [driver["instance"] for driver in self.drivers]

        for name in self.NAMES:
            try:
                instance = BuiltIn().get_library_instance(name)
                clear_drivers(self.drivers, name)
                drivers = get_webdrivers(instance._drivers, name)
                self.drivers.extend(drivers)
            except RuntimeError:
                pass

        added = [
            driver["instance"]
            for driver in self.drivers
            if driver["instance"] not in before
        ]

        try:
            self._register_webdrivers(added)
        except Exception as err:
            logging.debug("Failed to register webdrivers: %s", err)

    def start_suite(self, name, attributes):
        for name in self.NAMES:
            try:
                instance = BuiltIn().get_library_instance(name)
                set_webdrivers(self.drivers, instance._drivers, name)
            except RuntimeError:
                pass

    def _register_webdrivers(self, drivers):
        remote_url = os.getenv("BROWSERS_REMOTE_URL")
        if not remote_url:
            return

        for driver in drivers:
            info = {
                "type": "selenium",
                "executor_url": driver.command_executor._url,
                "session_id": driver.session_id,
            }

            logging.debug("Registering remote webdriver: %s", info)

            payload = json.dumps(info).encode("utf-8")
            req = urllib.request.Request(remote_url)
            req.add_header("Content-Type", "application/json; charset=utf-8")
            req.add_header("Content-Length", str(len(payload)))

            with urllib.request.urlopen(req, payload):
                pass  # Ignore response


class PlaywrightConnectionsListener:
    ROBOT_LISTENER_API_VERSION = 2

    NAMES = [
        "Browser",
        "RPA.Browser.Playwright",
    ]

    def __init__(self, drivers: list):
        self.drivers = drivers

    def end_suite(self, name, attributes):
        for name in self.NAMES:
            try:
                library = BuiltIn().get_library_instance(name)
                clear_drivers(self.drivers, name)
                driver = {
                    "instance": library.playwright,
                    "aliases": [],
                    "current": True,
                    "type": name,
                }
                self.drivers.append(driver)
            except RuntimeError:
                pass

    def start_suite(self, name, attributes):
        for name in self.NAMES:
            try:
                library = BuiltIn().get_library_instance(name)
                for driver in self.drivers:
                    if driver["type"] == name:
                        library.playwright = driver["instance"]
                        break
            except RuntimeError:
                pass


class JupyterConnectionsListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, drivers: list):
        self.drivers = drivers

    def end_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("JupyterLibrary")
            clear_drivers(self.drivers, "jupyter")
            self.drivers.extend(get_webdrivers(instance._drivers, "jupyter"))
        except RuntimeError:
            pass

    def start_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("JupyterLibrary")
            set_webdrivers(self.drivers, instance._drivers, "jupyter")
        except RuntimeError:
            pass


class AppiumConnectionsListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, drivers: list):
        self.drivers = drivers

    def end_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("AppiumLibrary")
            clear_drivers(self.drivers, "appium")
            self.drivers.extend(get_webdrivers(instance._cache, "appium"))
        except RuntimeError:
            pass

    def start_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("AppiumLibrary")
            set_webdrivers(self.drivers, instance._cache, "appium")
        except RuntimeError:
            pass


class WhiteLibraryListener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, drivers: list):
        self.drivers = drivers

    def end_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("WhiteLibrary")
            clear_drivers(self.drivers, "white")
            self.drivers.append(
                dict(
                    instance=(
                        getattr(instance, "app", None),
                        getattr(instance, "window", None),
                        getattr(instance, "screenshotter", None),
                    ),
                    aliases=[],
                    current=True,
                    type="white",
                )
            )
        except RuntimeError:
            pass

    def start_suite(self, name, attributes):
        try:
            builtin = BuiltIn()
            instance = builtin.get_library_instance("WhiteLibrary")
            for driver in self.drivers:
                if driver.get("type") == "white" and driver.get("current"):
                    setattr(instance, "app", driver["instance"][0])
                    setattr(instance, "window", driver["instance"][1])
                    setattr(instance, "screenshotter", driver["instance"][2])
        except RuntimeError:
            pass
