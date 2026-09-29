"""Every text read/write in the SUITE names its encoding, every text write
its newline (#92, RULINGS 17g).

On Windows the default text encoding is cp1252 and the default write
newline is CRLF.  Before #92 ~110 twins read UTF-8 sources/fixtures with a
bare ``read_text()`` / ``open()`` and died on ``UnicodeDecodeError:
'charmap'``, and fixtures written with a bare ``write_text()`` came back as
CRLF bytes.  macOS and Linux default to UTF-8/LF, so a new bare call is
green everywhere the author runs it — this twin makes it red there too.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _const_mode(call: ast.Call):
    mode = None
    if len(call.args) >= 2:
        m = call.args[1]
        if not (isinstance(m, ast.Constant) and isinstance(m.value, str)):
            return False            # computed mode: not judged here
        mode = m.value
    for k in call.keywords:
        if k.arg == "mode":
            if not (isinstance(k.value, ast.Constant)
                    and isinstance(k.value.value, str)):
                return False
            mode = k.value.value
    return mode or "r"


def _offences(tree: ast.AST):
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        kws = {k.arg for k in n.keywords}
        if None in kws:             # **kwargs: not judged here
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id == "open":
            mode = _const_mode(n)
            if mode is False or "b" in mode or len(n.args) > 3:
                continue
            if not n.args and "file" not in kws:
                continue
            if "encoding" not in kws:
                yield n.lineno, "open() without encoding="
            elif any(c in mode for c in "wax+") and "newline" not in kws:
                yield n.lineno, "text-mode open() for write without newline="
        elif isinstance(f, ast.Attribute) and f.attr == "read_text":
            if not n.args and "encoding" not in kws:
                yield n.lineno, "read_text() without encoding="
        elif isinstance(f, ast.Attribute) and f.attr == "write_text":
            if len(n.args) == 1 and not {"encoding", "newline"} <= kws:
                yield n.lineno, "write_text() without encoding= and newline="


def test_suite_text_io_names_encoding_and_newline():
    bad = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        bad += [f"{path.relative_to(TESTS).as_posix()}:{line}: {what}"
                for line, what in _offences(tree)]
    assert not bad, ("text I/O that is cp1252/CRLF on Windows (#92):\n  "
                     + "\n  ".join(bad[:40]))
