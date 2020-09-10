"""Utility functions for creating an interpreter."""

from io import StringIO
import os
from tempfile import TemporaryDirectory

from robot.api import get_model
from robot.running.model import TestSuite
from robot.running.builder.testsettings import TestDefaults
from robot.running.builder.parsers import ErrorReporter
from robot.running.builder.transformers import SettingsBuilder, SuiteBuilder
from robot.model.itemlist import ItemList


def init_suite(name: str, source: str=os.getcwd()):
    """Create a new test suite."""
    return TestSuite(name=name, source=source)


def execute(code: str, suite: TestSuite, defaults: TestDefaults=TestDefaults()):
    """Execute a snippet of code, given the current test suite."""
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

    # Execute suite
    stdout = StringIO()
    with TemporaryDirectory() as path:
        result = suite.run(outputdir=path, stdout=stdout)

    # Remove tests run so far,
    # this is needed so that we don't run them again in the next execution
    clean_items(suite.tests)

    return result


def strip_duplicate_items(items: ItemList):
    """Remove duplicates from an item list."""
    new_items = {}
    for item in items:
        new_items[item.name] = item
    items._items = list(new_items.values())


def clean_items(items: ItemList):
    """Remove elements from an item list."""
    items._items = []
