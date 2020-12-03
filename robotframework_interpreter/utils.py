import re
from typing import List
from difflib import SequenceMatcher
from copy import deepcopy
from operator import itemgetter

from robot.libraries import STDLIBS

from lunr.builder import Builder
from lunr.stemmer import stemmer
from lunr.stop_word_filter import stop_word_filter
from lunr.trimmer import trimmer


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


def line_at_cursor(code: str, cursor_pos: int = 0):
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


def scored_results(needle: str, results: List[str]) -> List[str]:
    results = deepcopy(results)
    for result in results:
        match = SequenceMatcher(
            None, needle.lower(), result["ref"].lower(), autojunk=False
        ).find_longest_match(0, len(needle), 0, len(result["ref"]))
        result["score"] = (match.size, match.size / float(len(result["ref"])))
    return list(reversed(sorted(results, key=itemgetter("score"))))


def remove_prefix(value, prefix):
    if value.startswith(prefix):
        value = value[len(prefix):]
    return value


def complete_libraries(needle: str,) -> List[str]:
    """Complete library names."""
    matches = []

    for lib in list(STDLIBS):
        if lib.lower().startswith(needle):
            matches.append(lib)

    return matches


def readable_keyword(s):
    """Return keyword in title case."""
    if s and not s.startswith("*") and not s.startswith("["):
        if s.count("."):
            library, name = s.rsplit(".", 1)
            return library + "." + name[0:].title()
        else:
            return s
    else:
        return s


def lunr_builder(ref, fields):
    """A convenience function to configure and construct a lunr.Builder.

    Returns:
        Index: The populated Index ready to search against.
    """
    builder = Builder()
    builder.pipeline.add(trimmer, stop_word_filter, stemmer)
    builder.search_pipeline.add(stemmer)
    builder.ref(ref)
    for field in fields:
        builder.field(field)
    return builder


def lunr_query(query):
    query = re.sub(r"([:*])", r"\\\1", query, re.U)
    query = re.sub(r"[\[\]]", r"", query, re.U)
    return f"*{query.strip().lower()}*"


def get_lunr_completions(needle: str, index, keywords, context):
    matches = []
    results = []

    if needle.rstrip():
        query = lunr_query(needle)
        results = index.search(query)
        results += index.search(query.strip("*"))

    for result in scored_results(needle, results):
        ref = result["ref"]
        if ref.startswith("__") and not ref.startswith(context):
            continue
        if not ref.startswith(context) and context not in [
            "__tasks__",
            "__keywords__",
            "__settings__",
        ]:
            continue
        if not needle.count("."):
            keyword = keywords[ref].name
            if keyword not in matches:
                matches.append(readable_keyword(keyword))
        else:
            matches.append(readable_keyword(ref))
    return matches
