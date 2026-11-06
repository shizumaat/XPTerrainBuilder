"""THE TERRAIN A DSF DRAWS (#1903): the physical triangles of a DSF's own
terrain patches, read straight from ``DSFTool --dsf2text``.

X-Plane draws the ground from the tile DSF's PHYSICAL patches
(``BEGIN_PATCH`` flag bit 1); every other mesh this engine holds -- the
patch, the graded sidecars, the ``.mesh`` -- is an input to that DSF, not
what the sim shows.  The drawn-mesh instrument (``tools/drawn_check.py``)
and the companion-mesh witness (``terrain_mesh_witness``) both read the
ground from here.

:func:`stream_text` runs DSFTool into a FIFO (POSIX) so a whole tile -- 13.5
million text lines at LOWS +47+012, about 11 s of DSFTool -- is read once and
never lands on disk; where there is no ``mkfifo`` it dumps to a temp file.
The child is declared to an armed write guard first, as every DSFTool spawn
is (``O4_DSFTool.run``).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
import typing as _t

import numpy as np

__all__ = ["expand_primitive", "physical_triangles", "stream_text"]

_PHYSICAL = 1


def expand_primitive(ptype: int, v: list) -> list:
    """A DSF primitive's triangles by vertex: 0 a list of triangles, 1 a
    strip, 2 a fan.  The winding is immaterial to every reader (a plan
    footprint and a barycentric z); triangles with two coincident plan
    corners are dropped."""
    if ptype == 0:
        idx = [(k, k + 1, k + 2) for k in range(0, len(v) - 2, 3)]
    elif ptype == 1:
        idx = [(k, k + 1, k + 2) for k in range(len(v) - 2)]
    elif ptype == 2:
        idx = [(0, k, k + 1) for k in range(1, len(v) - 1)]
    else:
        idx = []
    return [(v[a], v[b], v[c]) for a, b, c in idx
            if v[a][:2] != v[b][:2] and v[b][:2] != v[c][:2] and v[a][:2] != v[c][:2]]


def physical_triangles(text_lines: _t.Iterable[str],
                       ll_box: tuple[float, float, float, float]) -> np.ndarray:
    """``(n, 3, 3)`` corners ``(lon, lat, z)`` of every PHYSICAL patch
    triangle of a DSF text dump that has a corner inside ``ll_box`` =
    ``(west, south, east, north)``.  ``z`` is the vertex's own elevation
    as written (a raster-deferred vertex reads -32768, left to the
    caller)."""
    x0, y0, x1, y1 = ll_box
    out: list = []
    phys, ptype, verts = False, -1, []
    for line in text_lines:
        if line.startswith("PATCH_VERTEX"):
            if phys and ptype >= 0:
                t = line.split()
                verts.append((float(t[1]), float(t[2]), float(t[3])))
            continue
        if line.startswith("BEGIN_PATCH"):
            phys, ptype, verts = bool(int(line.split()[4]) & _PHYSICAL), -1, []
        elif line.startswith("BEGIN_PRIMITIVE"):
            ptype, verts = int(line.split()[1]), []
        elif line.startswith("END_PRIMITIVE"):
            if verts and any(x0 <= v[0] <= x1 and y0 <= v[1] <= y1 for v in verts):
                out.extend(expand_primitive(ptype, verts))
            ptype, verts = -1, []
    return np.asarray(out, dtype=float).reshape(-1, 3, 3)


@contextlib.contextmanager
def stream_text(dsf_path: str, tool: str, timeout: float = 900.0):
    """The DSF's text dump as an open text file, read once.  Raises
    ``O4_DSFTool.DsfToolError`` when DSFTool fails."""
    import O4_DSFTool as _dsftool
    import O4_External_Writes as _external_writes
    work = tempfile.mkdtemp(prefix="o4_dsf_stream_")
    text = os.path.join(work, "dsf.txt")
    try:
        if not hasattr(os, "mkfifo"):
            _dsftool.run([tool, "--dsf2text", dsf_path, text], writes=text, timeout=timeout)
            with open(text, encoding="utf-8", errors="replace") as fh:
                yield fh
            return
        os.mkfifo(text)
        _external_writes.declare_external_write(text, writer="DSFTool")
        proc = subprocess.Popen([tool, "--dsf2text", dsf_path, text],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with open(text, encoding="utf-8", errors="replace") as fh:
                yield fh
                for _rest in fh:          # a reader that stopped early still drains
                    pass
            rc = proc.wait(timeout=timeout)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        if rc != 0:
            raise _dsftool.DsfToolError(
                f"{tool} --dsf2text {_dsftool.exit_in_words(rc)} on {dsf_path}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
