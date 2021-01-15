import os
from io import BytesIO
import base64
import binascii
import urllib
from urllib.parse import unquote
import mimetypes
import re
import json
from json import JSONDecodeError
from typing import List
from difflib import SequenceMatcher
from copy import deepcopy
from operator import itemgetter

from .robot_version import ROBOT_MAJOR_VERSION

from robot.libraries import STDLIBS

if ROBOT_MAJOR_VERSION == 4:
    from robot.libdocpkg.htmlutils import DocToHtml
else:
    from robot.libdocpkg.htmlwriter import DocToHtml

from PIL import Image

from lunr.builder import Builder
from lunr.stemmer import stemmer
from lunr.stop_word_filter import stop_word_filter
from lunr.trimmer import trimmer

from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
import pygments

from .constants import SCRIPT_DISPLAY_LOG, NAME_REGEXP


def data_uri(mimetype, data):
    return "data:{};base64,{}".format(mimetype, base64.b64encode(data).decode("utf-8"))


def process_screenshots(outputdir: str):
    cwd = os.getcwd()

    with open(os.path.join(outputdir, "output.xml")) as fp:
        xml = fp.read()

    for src in re.findall('img src="([^"]+)', xml):
        if os.path.exists(src):
            filename = src
        elif os.path.exists(os.path.join(outputdir, src)):
            filename = os.path.join(outputdir, src)
        elif os.path.exists(os.path.join(cwd, src)):
            filename = os.path.join(cwd, src)
        elif src.startswith("data:"):
            filename = None
            try:
                spec, uri = src.split(",", 1)
                spec, encoding = spec.split(";", 1)
                spec, mimetype = spec.split(":", 1)
                if not (encoding == "base64" and mimetype.startswith("image/")):
                    continue
                data = base64.b64decode(unquote(uri).encode("utf-8"))
                im = Image.open(BytesIO(data))
            except (binascii.Error, IndexError, ValueError):
                continue
        else:
            continue
        if filename:
            im = Image.open(filename)
            mimetype = Image.MIME[im.format]
            # Fix issue where Pillow on Windows returns APNG for PNG
            if mimetype == "image/apng":
                mimetype = "image/png"
            with open(filename, "rb") as fp:
                data = fp.read()
        uri = data_uri(mimetype, data)
        xml = xml.replace('a href="{}"'.format(src), "a")
        xml = xml.replace(
            'img src="{}" width="800px"'.format(src),
            'img src="{}" style="max-width:800px;"'.format(uri),
        )
        xml = xml.replace('img src="{}"'.format(src), 'img src="{}"'.format(uri))

    with open(os.path.join(outputdir, "output.xml"), "w") as fp:
        fp.write(xml)


def display_log(html, filename=""):
    if isinstance(html, str):
        html = html.encode("utf-8")
    return SCRIPT_DISPLAY_LOG.format(
        content=base64.b64encode(html).decode("utf-8"), filename=filename
    )


def highlight(language, data):
    lexer = get_lexer_by_name(language)
    formatter = HtmlFormatter(noclasses=True, nowrap=True)
    return pygments.highlight(data, lexer, formatter)


def to_html(obj):
    """Return object as highlighted JSON."""
    return highlight("json", json.dumps(obj, sort_keys=False, indent=4))


def img_to_data(path):
    mime, _ = mimetypes.guess_type(path)

    if path.startswith("http"):
        with urllib.request.urlopen(path) as fp:
            data = fp.read()
    else:
        with open(path, 'rb') as fp:
            data = fp.read()

    return data_uri(mime, data)


def to_mime_and_metadata(obj):
    if isinstance(obj, bytes):
        obj = base64.b64encode(obj).decode("utf-8")
        return {"text/html": to_html(obj)}
    elif isinstance(obj, str) and (obj.startswith("http") or os.path.exists(obj)):
        if re.match(r".*\.(gif|jpg|svg|jpeg||png)$", obj, re.I):
            return {"text/html": "<img src='{}'>".format(img_to_data(obj))}
    elif hasattr(obj, "_repr_mimebundle_"):
        obj.embed = True
        return obj._repr_mimebundle_()
    elif hasattr(obj, "_repr_json_"):
        obj.embed = True
        return {"application/json": obj._repr_json_()}
    elif hasattr(obj, "_repr_html_"):
        obj.embed = True
        return {"text/html": obj._repr_html_()}
    elif hasattr(obj, "_repr_png_"):
        return {"image/png": obj._repr_png_()}
    elif hasattr(obj, "_repr_jpeg_"):
        return {"image/jpeg": obj._repr_jpeg_()}
    elif hasattr(obj, "_repr_svg_"):
        return {"image/svg": obj._repr_svg_()}
    try:
        if isinstance(obj, str):
            return {"text/html": f"<pre>{to_html(obj)}</pre>".replace("\\n", "\n")}
    except (TypeError, JSONDecodeError):
        pass
    try:
        return {"text/html": to_html(obj)}
    except TypeError:
        return {}


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


def complete_libraries(needle: str, extra_libraries: List[str]) -> List[str]:
    """Complete library names."""
    matches = []

    libs = list(STDLIBS) + extra_libraries

    for lib in libs:
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


def get_keyword_doc(keyword):
    title = keyword.name.strip("*").strip()
    title_html = f"<strong>{title}</strong>"
    if keyword.args:
        title += " " + ", ".join(keyword.args)
        title_html += " " + ", ".join(keyword.args)

    body = ""
    if keyword.doc:
        body = "\n\n" + keyword.doc

    return {
        "text/plain": title + "\n\n" + body,
        "text/html": f"<p>{title_html}</p>" +
        NAME_REGEXP.sub(
            lambda m: f"<code>{m.group(1)}</code>", DocToHtml(keyword.doc_format)(body)
        ),
    }
