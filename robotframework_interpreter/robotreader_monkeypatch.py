# -*- coding: utf-8 -*-
from io import StringIO

import os
import re
import sys
import types

import nbformat

from robot.libdocpkg import builder
from robot.running import importer
from robot.utils import FileReader


def _exec_code_into_module(code, module):
    if module not in sys.modules:
        sys.modules[module] = types.ModuleType(module)
    exec(code, sys.modules[module].__dict__)


def _read_notebook(ipynbfile):
    notebook = nbformat.read(ipynbfile, 4)
    data = []

    for cell in notebook.cells:
        # Skip non-code cells
        if not cell.cell_type == "code":
            continue

        # Execute %%python module magics
        match = re.match("^%%python module ([a-zA-Z_]+)", cell.source)
        if match is not None:
            module = match.groups()[0]
            cursor = len("%%python module {0:s}".format(module))
            _exec_code_into_module(cell.source[cursor:], module)
            continue

        # Add the rest into robot test suite
        data.append(cell.source)

    data = "\n\n".join(data)

    return data


def _get_ipynb_file(old):
    def _get_file(self, source, accept_text):
        path = self._get_path(source, accept_text)
        if path and os.path.splitext(path)[1].lower() == ".ipynb":
            file = StringIO(_read_notebook(path))
            return file, os.path.basename(path), True
        else:
            return old(self, source, accept_text)

    return _get_file


def inject_libdoc_ipynb_support():
    builder.RESOURCE_EXTENSIONS += (".ipynb",)


def inject_robot_ipynb_support():
    # Enable reading a Notebook with robot
    FileReader._get_file = _get_ipynb_file(FileReader._get_file)
    importer.RESOURCE_EXTENSIONS += (".ipynb",)
