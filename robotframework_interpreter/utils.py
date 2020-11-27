from difflib import SequenceMatcher
from copy import deepcopy
from operator import itemgetter


def detect_robot_context(code: str, cursor_pos: int):
    """Return robot code context in cursor position."""
    code = code[:cursor_pos]
    line = code.rsplit("\n")[-1]
    context_parts = code.rsplit("***", 2)
    if len(context_parts) != 3:
        return "__root__"
    else:
        context_name = context_parts[1].strip().lower()
        if context_name == "settings":
            return "__settings__"
        elif line.lstrip() == line:
            return "__root__"
        elif context_name in ["tasks", "test cases"]:
            return "__tasks__"
        elif context_name == "keywords":
            return "__keywords__"
        else:
            return "__root__"


def line_at_cursor(code: str, cursor_pos: int=0):
    """Return the line of code that is at the cursor position."""
    offset = 0
    lines = code.splitlines(True)
    for line in lines:
        next_offset = offset + len(line)
        if not line.endswith('\n'):
            # If the last line doesn't have a trailing newline, treat it as if
            # it does so that the cursor at the end of the line still counts
            # as being on that line.
            next_offset += 1
        if next_offset > cursor_pos:
            break
        offset = next_offset
    else:
        line = ""
    return (line, offset)


def scored_results(needle, results):
    results = deepcopy(results)
    for result in results:
        match = SequenceMatcher(
            None, needle.lower(), result["ref"].lower(), autojunk=False
        ).find_longest_match(0, len(needle), 0, len(result["ref"]))
        result["score"] = (match.size, match.size / float(len(result["ref"])))
    return list(reversed(sorted(results, key=itemgetter("score"))))
