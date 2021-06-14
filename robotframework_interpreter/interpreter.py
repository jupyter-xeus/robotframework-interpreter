"""Utility functions for creating an interpreter."""

from collections import OrderedDict
from copy import deepcopy
from io import StringIO
import os
import re
from functools import partial
from tempfile import TemporaryDirectory
from typing import List

from IPython.core.display import display

from robot.api import get_model
from robot.errors import DataError
from robot.reporting import ResultWriter
from robot.running.model import TestSuite
from robot.running.builder.testsettings import TestDefaults
from robot.running.builder.parsers import ErrorReporter
from robot.running.builder.transformers import SettingsBuilder, SuiteBuilder
from robot.model.itemlist import ItemList

from ipywidgets import VBox, HBox, Button, Output, Text

from .utils import (
    detect_robot_context, line_at_cursor, scored_results,
    complete_libraries, get_lunr_completions, remove_prefix,
    display_log, process_screenshots, lunr_query, get_keyword_doc
)
from .selectors import (
    BrokenOpenConnection, clear_selector_highlights, get_autoit_selector_completions, get_selector_completions,
    get_white_selector_completions, get_win32_selector_completions, is_autoit_selector,
    is_selector, is_white_selector, is_win32_selector, close_current_connection, yield_current_connection
)
from .constants import VARIABLE_REGEXP, BUILTIN_VARIABLES
from .listeners import RobotKeywordsIndexerListener

from robot.running.model import UserKeyword


# Monkey patch user-keyword source for JupyterLab debugger
def get_source(self):
    if hasattr(self, 'actual_source'):
        return self.actual_source

    return self.parent.source if self.parent is not None else None


UserKeyword.source = property(get_source)


def normalize_argument(name):
    if "=" in name:
        name, default = name.split("=", 1)
    else:
        default = None

    return (
        name,
        re.sub(r"\W", "_", re.sub(r"^[^\w]*|[^\w]*$", "", name, re.U), re.U),
        default
    )


def execute_keyword(suite: TestSuite, name, arguments, **values):
    header = suite.rpa and "Tasks" or "Test Cases"
    code = f"""\

*** {header} ***

{name}
    {name}  {'  '.join([values[a[1]] for a in arguments])}
"""

    # Copy the test suite
    suite = deepcopy(suite)
    suite.rpa = True

    with TemporaryDirectory() as path:
        _, report = _execute_impl(code, suite, outputdir=path, interactive_keywords=False)

    if report is not None:
        display(report, raw=True)


def on_button_execute(execute, controls, out, widgets, *args, **kwargs):
    values = {key: control.value for key, control in controls.items()}

    with out:
        description = widgets[0].description
        widgets[0].description = "Executing..."

        for widget in widgets:
            widget.disabled = True

        out.clear_output(wait=True)

        try:
            execute(**values)
        finally:
            widgets[0].description = description
            for widget in widgets:
                widget.disabled = False


def get_interactive_keyword(suite: TestSuite, keyword):
    """Get an interactive widget for testing a keyword."""
    name = keyword.name
    arguments = [normalize_argument(arg) for arg in keyword.args]

    # Make a copy of the suite, the suite the widget operates on must no be
    # the same as the main one
    suite_copy = deepcopy(suite)

    execute_key = partial(execute_keyword, suite_copy, name, arguments)

    widgets = []
    controls = OrderedDict()
    out = Output()

    for arg in arguments:
        input_widget = Text(description=arg[1] + "=", value=arg[2])
        widgets.append(input_widget)
        controls[arg[1]] = input_widget

    button = Button(description=name)
    button.on_click(partial(on_button_execute, execute_key, controls, out, widgets))
    widgets.insert(0, button)

    return VBox((HBox(widgets), out))


class TestSuiteError(Exception):
    pass


class ProgressUpdater(StringIO):
    """Wrapper designed to capture robot.api.logger.console and display it.
    This can be used passing an instance of this to the execute's stdout argument"""

    colors = re.compile(r"\[[0-?]+[^m]+m")

    def __init__(self, display, update_display):
        self.display = display
        self.update_display = update_display

        self.progress = {"test": "n/a", "keyword": "n/a", "message": None}
        self.already_displayed = False

        super(ProgressUpdater, self).__init__()

    def _update(self):
        status_line = " | ".join(
            str(s)
            for s in [
                self.progress["test"],
                self.progress["keyword"],
                self.progress["message"],
            ]
            if s
        )

        mimebundle = {
            "text/html": f'<pre style="white-space:nowrap;overflow:hidden;padding-left:1ex;'
                         f'"><i class="fa fa-spinner fa-pulse"></i>{status_line}</pre>'
        }

        if not self.already_displayed:
            self.display(mimebundle)
            self.already_displayed = True
        else:
            self.update_display(mimebundle)

    def update(self, data):
        if "test" in data:
            self.progress["test"] = data["test"]
            self.progress["message"] = None
        elif "keyword" in data:
            self.progress["keyword"] = data["keyword"]
            self.progress["message"] = None
        self._update()

    def clear(self):
        self.update_display({"text/plain": ""})

    def write(self, s):
        self.progress["message"] = s.strip()
        self._update()
        return super(ProgressUpdater, self).write(s)


class NoOpStream():
    def write(self, message, flush=False):
        # This is a no-op
        pass

    def flush(self):
        # This is a no-op
        pass


def init_suite(name: str, source: str = os.getcwd()):
    """Create a new test suite."""
    return TestSuite(name=name, source=source)


def generate_report(suite: TestSuite, outputdir: str):
    process_screenshots(outputdir)

    writer = ResultWriter(os.path.join(outputdir, "output.xml"))
    writer.write_results(
        log=os.path.join(outputdir, "log.html"),
        report=None,
        rpa=getattr(suite, "rpa", False),
    )

    with open(os.path.join(outputdir, "log.html"), "rb") as fp:
        log = fp.read()
        log = log.replace(b'"reportURL":"report.html"', b'"reportURL":null')

    html = """
        <button
          class="jp-mod-styled jp-mod-accept"
          onClick="{};event.preventDefault();event.stopPropagation();"
        >
            <i class="fa fa-file" aria-hidden="true"></i>
            Log
        </button>
        """.format(display_log(log, "log.html"))

    return {"text/html": html}


def _execute_impl(code: str, suite: TestSuite, defaults: TestDefaults = TestDefaults(),
                  stdout=None, stderr=None, listeners=[], drivers=[], outputdir=None, interactive_keywords=True, logger=None):
    # Clear selector completion highlights
    for driver in yield_current_connection(drivers, ["RPA.Browser.Selenium", "RPA.Browser", "selenium", "jupyter"]):
        try:
            clear_selector_highlights(driver)
        except BrokenOpenConnection:
            close_current_connection(drivers, driver)

    if logger is not None:
        logger.debug("Compiling code: \n%s", code)

    # Copy keywords/variables/libraries in case of failure
    imports = get_items_copy(suite.resource.imports)
    variables = get_items_copy(suite.resource.variables)
    keywords = get_items_copy(suite.resource.keywords)

    # Compile AST
    model = get_model(
        StringIO(code),
        data_only=False,
        curdir=os.getcwd().replace("\\", "\\\\"),
    )
    ErrorReporter(code).visit(model)
    SettingsBuilder(suite, defaults).visit(model)
    SuiteBuilder(suite, defaults).visit(model)

    # Strip variables/keyword duplicates
    strip_duplicate_items(suite.resource.variables)
    strip_duplicate_items(suite.resource.keywords)

    new_imports = [item for item in get_items_copy(suite.resource.imports) if item not in imports]
    for new_import in new_imports:
        new_import.source = suite.source
    new_variables = [item for item in get_items_copy(suite.resource.variables) if item not in variables]
    for new_variable in new_variables:
        new_variable.source = suite.source
    # If there is no test, allow the user to interact with defined keywords by providing widgets
    new_keywords = [item for item in get_items_copy(suite.resource.keywords) if item not in keywords]
    for new_keyword in new_keywords:
        new_keyword.actual_source = suite.source
    if not suite.tests and new_keywords and interactive_keywords:
        return None, [get_interactive_keyword(suite, keyword) for keyword in new_keywords]

    # Set default streams
    # By default stdout is no-op
    if stdout is None:
        stdout = NoOpStream()

    if logger is not None:
        logger.debug("Executing code")

    # Execute suite
    try:
        result = suite.run(outputdir=outputdir, stdout=stdout, stderr=stderr, listener=listeners)
    except TestSuiteError as e:
        # Reset keywords/variables/libraries
        set_items(suite.resource.imports, imports)
        set_items(suite.resource.variables, variables)
        set_items(suite.resource.keywords, keywords)

        clean_items(suite.tests)

        if logger is not None:
            logger.debug("Execution error: %s", e)

        raise e

    for listener in listeners:
        if isinstance(listener, RobotKeywordsIndexerListener):
            listener.import_from_suite_data(suite)

    # Detect RPA
    suite.rpa = get_rpa_mode(model)

    report = None
    if suite.tests:
        report = generate_report(suite, outputdir)

    # Remove tests run so far,
    # this is needed so that we don't run them again in the next execution
    clean_items(suite.tests)

    return result, report


def execute(code: str, suite: TestSuite, defaults: TestDefaults = TestDefaults(),
            stdout=None, stderr=None, listeners=[], drivers=[], outputdir=None, logger=None):
    """
    Execute a snippet of code, given the current test suite. Returns a tuple containing the result of the
    suite (if there were tests) and a displayable object containing either the report or interactive widgets.
    """
    if outputdir is None:
        with TemporaryDirectory() as path:
            result = _execute_impl(code, suite, defaults, stdout, stderr, listeners, drivers, path, logger=logger)
    else:
        result = _execute_impl(code, suite, defaults, stdout, stderr, listeners, drivers, outputdir, logger=logger)

    return result


def complete(code: str, cursor_pos: int, suite: TestSuite, keywords_listener: RobotKeywordsIndexerListener = None, extra_libraries: List[str] = [], drivers=[], logger=None):
    """Complete a snippet of code, given the current test suite."""
    context = detect_robot_context(code, cursor_pos)
    cursor_pos = cursor_pos is None and len(code) or cursor_pos
    line, offset = line_at_cursor(code, cursor_pos)
    line_cursor = cursor_pos - offset
    needle = re.split(r"\s{2,}|\t| \| ", line[:line_cursor])[-1].lstrip()

    if logger is not None:
        logger.debug("Completing text: %s", needle)

    library_completion = context == "__settings__" and any(
        [
            line.lower().startswith("library "),
            "import library " in line.lower(),
            "reload library " in line.lower(),
            "get library instance" in line.lower(),
        ]
    )

    matches = []

    # Try to complete a variable
    if needle and needle[0] in "$@&%":
        if logger is not None:
            logger.debug("Context: Variable")

        potential_vars = list(set(
            [var.name for var in suite.resource.variables] +
            VARIABLE_REGEXP.findall(code) +
            BUILTIN_VARIABLES
        ))

        matches = [
            m["ref"]
            for m in scored_results(needle, [dict(ref=v) for v in potential_vars])
            if needle.lower() in m["ref"].lower()
        ]

        if len(line) > line_cursor and line[line_cursor] == "}":
            cursor_pos += 1
            needle += "}"
    # Try to complete a library name
    elif library_completion:
        if logger is not None:
            logger.debug("Context: Library name")

        needle = needle.lower()
        needle = remove_prefix(needle, 'library ')
        needle = remove_prefix(needle, 'import library ')
        needle = remove_prefix(needle, 'reload library ')
        needle = remove_prefix(needle, 'get library instance ')

        matches = complete_libraries(needle, extra_libraries)
    # Try to complete a CSS selector
    elif is_selector(needle):
        if logger is not None:
            logger.debug("Context: Selenium or Appium selector")
            logger.debug("Current WebDrivers: %s", drivers)

        matches = []
        for driver in yield_current_connection(drivers, ["RPA.Browser.Selenium", "RPA.Browser", "selenium", "jupyter", "appium"]):
            matches = [get_selector_completions(needle.rstrip(), driver)[0]]
    # Try to complete an AutoIt selector
    elif is_autoit_selector(needle):
        if logger is not None:
            logger.debug("Context: AutoIt selector")

        matches = [get_autoit_selector_completions(needle)[0]]
    # Try to complete a white selector
    elif is_white_selector(needle):
        if logger is not None:
            logger.debug("Context: WhiteLibrary selector")

        matches = [get_white_selector_completions(needle)[0]]
    # Try to complete a Windows selector
    elif is_win32_selector(needle):
        if logger is not None:
            logger.debug("Context: Win32 selector")

        matches = [get_win32_selector_completions(needle)[0]]
    # Try to complete a keyword
    elif keywords_listener is not None:
        if logger is not None:
            logger.debug("Context: Keywords or Built-ins")

        matches = get_lunr_completions(
            needle,
            keywords_listener.index,
            keywords_listener.keywords,
            context
        )

    if logger is not None:
        logger.debug("Available completions: %s", matches)

    return {
        "matches": matches,
        "cursor_end": cursor_pos,
        "cursor_start": cursor_pos - len(needle)
    }


def inspect(code: str, cursor_pos: int, suite: TestSuite, keywords_listener: RobotKeywordsIndexerListener = None, detail_level=0, logger=None):
    cursor_pos = len(code) if cursor_pos is None else cursor_pos
    line, offset = line_at_cursor(code, cursor_pos)
    line_cursor = cursor_pos - offset
    left_needle = re.split(r"\s{2,}|\t| \| ", line[:line_cursor])[-1]
    right_needle = re.split(r"\s{2,}|\t| \| ", line[line_cursor:])[0]
    needle = left_needle.lstrip().lower() + right_needle.rstrip().lower()

    if logger is not None:
        logger.debug("Inspecting text: %s", needle)

    results = []
    data = {}
    found = False

    if needle and lunr_query(needle):
        query = lunr_query(needle)
        results = keywords_listener.index.search(query)
        results += keywords_listener.index.search(query.strip("*"))

    for result in results:
        keyword = keywords_listener.keywords[result["ref"]]

        if needle not in [keyword.name.lower(), result["ref"].lower()]:
            continue

        data = get_keyword_doc(keyword)
        found = True
        break

    if logger is not None:
        logger.debug("Inspection data: %s", data)

    return {
        "data": data,
        "found": found,
    }


def shutdown_drivers(drivers=[]):
    for driver in drivers:
        if hasattr(driver["instance"], "quit"):
            driver["instance"].quit()


def strip_duplicate_items(items: ItemList):
    """Remove duplicates from an item list."""
    new_items = {}
    for item in items:
        new_items[item.name] = item
    items._items = list(new_items.values())


def clean_items(items: ItemList):
    """Remove elements from an item list."""
    items._items = []


def set_items(items: ItemList, value: List):
    """Remove elements from an item list."""
    items._items = value


def get_items_copy(items: ItemList):
    """Get copy of an itemlist."""
    return list(items._items)


def get_rpa_mode(model):
    """Get RPA mode for the test suite."""
    if not model:
        return None
    tasks = [s.tasks for s in model.sections if hasattr(s, 'tasks')]
    if all(tasks) or not any(tasks):
        return tasks[0] if tasks else None
    raise DataError('One file cannot have both tests and tasks.')
