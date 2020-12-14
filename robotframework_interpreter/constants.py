from robot.libdocpkg.model import KeywordDoc
import re

VARIABLE_REGEXP = re.compile(r"[$@&%]\{[\w\s]+\}")

BUILTIN_VARIABLES = [
    "${TEMPDIR}",
    "${EXECDIR}",
    "${/}",
    "${:}",
    "${\\n}",
    "${SPACE}",
    "${True}",
    "${False}",
    "${None}",
    "${null}",
    "${OUTPUT_DIR}",
    "${OUTPUT_FILE}",
    "${REPORT_FILE}",
    "${LOG_FILE}",
    "${DEBUG_FILE}",
    "${LOG_LEVEL}",
    "${PREV_TEST_NAME}",
    "${PREV_TEST_STATUS}",
    "${PREV_TEST_MESSAGE}",
]

NAME_REGEXP = re.compile("`(.+?)`")

CONTEXT_LIBRARIES = {
    "__root__": list(
        map(
            lambda item: KeywordDoc(name=item[0], doc=item[1]),
            {
                "*** Settings ***": """\
The Setting table is used to import test libraries, resource files and variable
files and to define metadata for test suites and test cases. It can be included
in test case files and resource files. Note that in a resource file, a Setting
table can only include settings for importing libraries, resources, and
variables.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#appendices
""",  # noqa: E501
                "*** Variables ***": """\
The most common source for variables are Variable tables in test case files and
resource files. Variable tables are convenient, because they allow creating
variables in the same place as the rest of the test data, and the needed syntax
is very simple. Their main disadvantages are that values are always strings and
they cannot be created dynamically. If either of these is a problem, variable
files can be used instead.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#creating-variables
""",  # noqa: E501
                "*** Test Cases ***": """\
Test cases are constructed in test case tables from the available keywords.
Keywords can be imported from test libraries or resource files, or created in
the keyword table of the test case file itself.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-syntax
""",  # noqa: E501
                "*** Tasks ***": """\
Tasks are constructed in tasks tables from the available keywords. Keywords can
be imported from test libraries or resource files, or created in the keyword
table of the tasks file itself.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-syntax
""",  # noqa: E501
                "*** Keywords ***": """\
User keyword names are in the first column similarly as test cases names. Also
user keywords are created from keywords, either from keywords in test libraries
or other user keywords. Keyword names are normally in the second column, but
when setting variables from keyword return values, they are in the subsequent
columns.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-syntax
""",  # noqa: E501
            }.items(),
        )
    ),
    "__settings__": list(
        map(
            lambda item: KeywordDoc(name=item[0], doc=item[1]),
            {
                "Library": """\
Test libraries are typically imported using the Library setting.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#importing-libraries
""",  # noqa: E501
                "Resource": """\
Resource files are imported using the Resource setting in the Settings table.
The path to the resource file is given in the cell after the setting name.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#taking-resource-files-into-use
""",  # noqa: E501
                "Variables": """\
All test data files can import variables using the Variables setting in the
Setting table, in the same way as resource files are imported using the
Resource setting.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#taking-variable-files-into-use
""",  # noqa: E501
                "Documentation": """\
Used for specifying a test suite or resource file documentation.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-suite-name-and-documentation
""",  # noqa: E501
                "Metadata": """\
Used for setting free test suite metadata.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#free-test-suite-metadata
""",  # noqa: E501
                "Suite Setup": """\
Used for specifying the suite setup.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#suite-setup-and-teardown
""",  # noqa: E501
                "Suite Teardown": """\
Used for specifying the suite teardown.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#suite-setup-and-teardown
""",  # noqa: E501
                "Test Setup": """\
Used for specifying a default test setup.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "Test Teardown": """\
Used for specifying a default test teardown.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "Test Template": """\
Used for specifying a default template keyword for test cases.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-templates
""",  # noqa: E501
                "Test Timeout": """\
Used for specifying a default test case timeout.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-timeout
""",  # noqa: E501
                "Task Setup": """\
Used for specifying a default task setup.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "Task Teardown": """\
Used for specifying a default task teardown.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "Task Template": """\
Used for specifying a default template keyword for tasks.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-templates
""",  # noqa: E501
                "Task Timeout": """\
Used for specifying a default task timeout.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-timeout
""",  # noqa: E501
                "Force Tags": """\
Used for specifying forced values for tags when tagging test cases.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#tagging-test-cases
""",  # noqa: E501
                "Default Tags": """\
Used for specifying default values for tags when tagging test cases.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#tagging-test-cases
""",  # noqa: E501
            }.items(),
        )
    ),
    "__tasks__": list(
        map(
            lambda item: KeywordDoc(name=item[0], doc=item[1]),
            {
                "[Documentation]": """\
Used for specifying test case documentation.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-name-and-documentation
""",  # noqa: E501
                "[Tags]": """\
Used for tagging test cases.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#tagging-test-cases
""",  # noqa: E501
                "[Setup]": """\
Used for specifying a test setup.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "[Teardown]": """\
Used for specifying a test teardown.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-setup-and-teardown
""",  # noqa: E501
                "[Template]": """\
Used for specifying a template keyword.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-templates
""",  # noqa: E501
                "[Timeout]": """\
Used for specifying a test case timeout.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#test-case-timeout
""",  # noqa: E501
            }.items(),
        )
    ),
    "__keywords__": list(
        map(
            lambda item: KeywordDoc(name=item[0], doc=item[1]),
            {
                "[Documentation]": """\
Used for specifying a user keyword documentation.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-documentation
""",  # noqa: E501
                "[Tags]": """\
Used for specifying user keyword tags.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-tags
""",  # noqa: E501
                "[Arguments]": """\
Used for specifying user keyword arguments.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-arguments
""",  # noqa: E501
                "[Return]": """\
Used for specifying user keyword return values.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-return-values
""",  # noqa: E501
                "[Teardown]": """\
Used for specifying user keyword teardown.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-teardown
""",  # noqa: E501
                "[Timeout]": """\
Used for specifying a user keyword timeout.

`Robot Framework User Guide`__

__ http://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#user-keyword-timeout
""",  # noqa: E501
            }.items(),
        )
    ),
}

CONTEXT_LIBRARIES["__settings__"].extend(CONTEXT_LIBRARIES["__root__"])


SCRIPT_DISPLAY_LOG = """\
var content = '{content}';

var w = window.open('', '', 'width=900,height=900');
w.document.body.style = 'margin:0; overflow: hidden;';

var i = w.document.createElement('iframe');
i.src = 'data:text/html;base64,' + content;
i.style = (
  'position:absolute;' +
  'left: 0px; width: 100%;' +
  'top: 0px; height: 100%;' +
  'border-width: 0;'
);
w.document.body.append(i);

var a = w.document.createElement('a');
a.appendChild(w.document.createTextNode('Download'));
a.href = 'data:text/html;base64,' + content;
a.download = '{filename}';
a.style = (
  'position:fixed;top:0;right:0;' +
  'color:white;background:black;text-decoration:none;' +
  'font-weight:bold;padding:7px 14px;border-radius:0 0 0 5px;'
);
w.document.body.append(a);
"""
