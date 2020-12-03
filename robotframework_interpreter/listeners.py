from .utils import lunr_builder
from .constants import CONTEXT_LIBRARIES

from robot.errors import DataError
from robot.libdocpkg import LibraryDocumentation


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
            self.builder.add(
                {"name": keyword.name, "dottedname": keyword.name}
            )
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
