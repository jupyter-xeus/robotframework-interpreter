"""Utility functions for creating an interpreter."""

from io import StringIO
import os
import re
from tempfile import TemporaryDirectory

from robot.api import get_model
from robot.errors import DataError
from robot.running.model import TestSuite
from robot.running.builder.testsettings import TestDefaults
from robot.running.builder.parsers import ErrorReporter
from robot.running.builder.transformers import SettingsBuilder, SuiteBuilder
from robot.model.itemlist import ItemList

from .utils import (
    detect_robot_context, line_at_cursor, scored_results,
    complete_libraries, get_lunr_completions, remove_prefix
)
from .constants import VARIABLE_REGEXP
from .listeners import RobotKeywordsIndexerListener


def init_suite(name: str, source: str = os.getcwd()):
    """Create a new test suite."""
    return TestSuite(name=name, source=source)


def execute(code: str, suite: TestSuite, defaults: TestDefaults = TestDefaults(), stdout=StringIO(), stderr=StringIO(), listeners=[]):
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

    for listener in listeners:
        if isinstance(listener, RobotKeywordsIndexerListener):
            listener.import_from_suite_data(suite)

    # Execute suite
    with TemporaryDirectory() as path:
        if len(listeners):
            result = suite.run(outputdir=path, stdout=stdout, stderr=stderr, listener=listeners)
        else:
            result = suite.run(outputdir=path, stdout=stdout, stderr=stderr)

    # Remove tests run so far,
    # this is needed so that we don't run them again in the next execution
    clean_items(suite.tests)

    # Detect RPA
    suite.rpa = get_rpa_mode(model)

    return result


def complete(code: str, cursor_pos: int, suite: TestSuite, keywords_listener: RobotKeywordsIndexerListener = None):
    """Complete a snippet of code, given the current test suite."""
    context = detect_robot_context(code, cursor_pos)
    cursor_pos = cursor_pos is None and len(code) or cursor_pos
    line, offset = line_at_cursor(code, cursor_pos)
    line_cursor = cursor_pos - offset
    needle = re.split(r"\s{2,}|\t| \| ", line[:line_cursor])[-1].lstrip()

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
        potential_vars = list(set([var.name for var in suite.resource.variables] + VARIABLE_REGEXP.findall(code)))

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
        needle = needle.lower()
        needle = remove_prefix(needle, 'library ')
        needle = remove_prefix(needle, 'import library ')
        needle = remove_prefix(needle, 'reload library ')
        needle = remove_prefix(needle, 'get library instance ')

        matches = complete_libraries(needle)
    # Try to complete a keyword
    elif keywords_listener is not None:
        matches = get_lunr_completions(
            needle,
            keywords_listener.index,
            keywords_listener.keywords,
            context
        )

    return {
        "matches": matches,
        "cursor_end": cursor_pos,
        "cursor_start": cursor_pos - len(needle),
        "metadata": {},
        "status": "ok",
    }


def strip_duplicate_items(items: ItemList):
    """Remove duplicates from an item list."""
    new_items = {}
    for item in items:
        new_items[item.name] = item
    items._items = list(new_items.values())


def clean_items(items: ItemList):
    """Remove elements from an item list."""
    items._items = []


def get_rpa_mode(model):
    """Get RPA mode for the test suite."""
    if not model:
        return None
    tasks = [s.tasks for s in model.sections if hasattr(s, 'tasks')]
    if all(tasks) or not any(tasks):
        return tasks[0] if tasks else None
    raise DataError('One file cannot have both tests and tasks.')
