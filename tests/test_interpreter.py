from ipywidgets import DOMWidget

from robotframework_interpreter import init_suite, execute, complete
from robotframework_interpreter.robot_version import ROBOT_MAJOR_VERSION


CELL1 = """\
*** Settings ***

Library  Collections
"""

CELL2 = """\
*** Variables ***

${VARNAME}  Hello
"""

CELL3 = """\
*** Keywords ***

Head
    [Arguments]  ${list}
    ${value}=  Get from list  ${list}  0
    [Return]  ${value}
"""

CELL4 = """\
*** Test Cases ***

Get head
    ${array}=  Create list  1  2  3  4  5
    ${head}=  Head  ${array}
    Should be equal  ${head}  1
"""

INCOMPLETE_CELL1 = """
*** Keywords ***

Head
    [Arguments]  ${list}
    ${value}=  Get from list  ${list}  0
    [Return]  ${
"""


def test_execution():
    suite = init_suite('test suite')

    execute(CELL1, suite)

    assert len(suite.resource.keywords) == 0
    assert len(suite.tests) == 0

    result, widgets = execute(CELL3, suite)

    assert result is None
    assert len(widgets) == 1
    assert isinstance(widgets[0], DOMWidget)

    assert len(suite.resource.keywords) == 1
    assert len(suite.tests) == 0

    result, _ = execute(CELL4, suite)

    assert len(suite.resource.keywords) == 1
    assert len(suite.tests) == 0  # Test cases should be cleared between cell code executions

    if ROBOT_MAJOR_VERSION == 4:
        assert result.statistics.total.failed == 0
        assert result.statistics.total.passed == 1
    else:
        assert result.statistics.total.critical.failed == 0
        assert result.statistics.total.critical.passed == 1


def test_keywords_completion():
    suite = init_suite('test suite')

    execute(CELL1, suite)
    execute(CELL2, suite)

    completion = complete(INCOMPLETE_CELL1, len(INCOMPLETE_CELL1) - 1, suite)

    assert '${VARNAME}' in completion['matches']
    assert '${list}' in completion['matches']
    assert '${value}' in completion['matches']
    assert '${False}' in completion['matches']
    assert '${SPACE}' in completion['matches']
