from robotframework_interpreter.utils import detect_robot_context


def test_detect_robot_context():
    assert detect_robot_context("", -1) == "__root__"
    assert (
        detect_robot_context(
            """\
*** Variables ***
""",
            -1,
        )
        == "__root__"
    )
    assert (
        detect_robot_context(
            """\
*** Settings ***
*** Variables ***
""",
            -1,
        )
        == "__root__"
    )

    assert (
        detect_robot_context(
            """\
    *** Settings ***
    """,
            -1,
        )
        == "__settings__"
    )
    assert (
        detect_robot_context(
            """\
*** Settings ***
*** Tasks ***
""",
            len("*** Settings ***"),
        )
        == "__settings__"
    )

    assert (
        detect_robot_context(
            """\
*** Test Cases ***

This is a test case
    With a keyword  and  param
""",
            -1,
        )
        == "__tasks__"
    )
    assert (
        detect_robot_context(
            """\
*** Settings ***
*** Test Cases ***

This is a test case
    With a keyword  and  param
""",
            -1,
        )
        == "__tasks__"
    )
    assert (
        detect_robot_context(
            """\
*** Settings ***
*** Tasks ***

This is a task
    With a keyword  and  param
""",
            -1,
        )
        == "__tasks__"
    )
