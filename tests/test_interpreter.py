from robotframework_interpreter import init_suite, execute


CELL1 = """\
*** Settings ***

Library  Collections
"""

CELL2 = """\
*** Keywords ***

Head
    [Arguments]  ${list}
    ${value}=  Get from list  ${list}  0
    [Return]  ${value}
"""

CELL3 = """\
*** Test Cases ***

Get head
    ${array}=  Create list  1  2  3  4  5
    ${head}=  Head  ${array}
    Should be equal  ${head}  1
"""


def test_execution():
    suite = init_suite('test suite')

    execute(CELL1, suite)

    assert len(suite.resource.keywords) == 0
    assert len(suite.tests) == 0

    execute(CELL2, suite)

    assert len(suite.resource.keywords) == 1
    assert len(suite.tests) == 0

    result = execute(CELL3, suite)

    assert len(suite.resource.keywords) == 1
    assert len(suite.tests) == 0  # Test cases should be cleared between cell code executions
    assert result.statistics.total.critical.failed == 0
    assert result.statistics.total.critical.passed == 1
