"""``airport/obj8_memo`` (#412): one parse per OBJ8 file version inside a
scope, a fresh parse outside it and after the file changes."""
from __future__ import annotations

import os

from auto_patch_v2.airport import obj8_memo as M

_OBJ = """I
800
OBJ

POINT_COUNTS\t3 0 0 3
VT\t0 0 0\t0 1 0\t0 0
VT\t1 0 0\t0 1 0\t0 0
VT\t0 0 1\t0 1 0\t0 0
IDX\t0 1 2
ATTR_hard
TRIS\t0 3
"""


def _write(path, text=_OBJ):
    path.write_text(text, encoding="latin-1", newline="\n")
    return str(path)


def test_a_scope_parses_each_file_version_once(tmp_path):
    p = _write(tmp_path / "a.obj")
    assert M.parse(p) is not M.parse(p)            # no scope: a parse each time
    with M._scope():
        g = M.parse(p)
        assert M.parse(p) is g
        c = M.components(g)
        assert M.components(g) is c and len(c) == 1
        with M._scope():                             # nested: the outer memo
            assert M.parse(p) is g
        st = os.stat(p)
        _write(tmp_path / "a.obj", _OBJ + "\n")     # a new version
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        assert M.parse(p) is not g
    assert M._MEMO is None


def test_scoped_keeps_the_signature_and_opens_a_scope(tmp_path):
    import inspect
    seen = []

    @M.scoped
    def f(a, *, b=2):
        seen.append(M._MEMO is not None)
        return a + b
    assert f(1) == 3 and seen == [True] and M._MEMO is None
    assert list(inspect.signature(f).parameters) == ["a", "b"]


def test_per_file_reads_by_kind(tmp_path):
    p = _write(tmp_path / "b.obj")
    calls = []

    def read(path):
        calls.append(path)
        return [len(calls)]
    with M._scope():
        assert M.per_file(p, "k1", read) == M.per_file(p, "k1", read) == [1]
        assert M.per_file(p, "k2", read) == [2]
    assert M.per_file(p, "k1", read) == [3]
