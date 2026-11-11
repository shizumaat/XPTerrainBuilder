"""WHERE A v2 BUILD RAISED: the one line an airport's failure record adds
to its error so the console names the stage, the function and the regions
it was working on -- the traceback itself goes only to the tile's verify
debug log.

MEASURED EGKK (2026-11-10, app 1.0.481): the log said only
``TopologyException: side location conflict at 1971.99 724.90`` (a GEOS
refusal deep in shapely); the stage was ``planar/pad_cut.py``'s plateau
cut and the operand the ``dsf:pol43`` apron, which only a capture found.
"""
from __future__ import annotations

import os

__all__ = ["raised_at"]

_PACKAGE = "auto_patch_v2"
_MAX_REFS = 4


def _refs_of(frame) -> list[str]:
    """The ``ref`` of every local in ``frame`` that carries one (a planar
    region, a pavement), in the frame's own order, at most ``_MAX_REFS``."""
    out: list[str] = []
    for value in frame.f_locals.values():
        ref = getattr(value, "ref", None)
        if isinstance(ref, str) and ref and ref not in out:
            out.append(ref)
            if len(out) >= _MAX_REFS:
                break
    return out


def raised_at(exc: BaseException) -> str:
    """`` (raised in <stage file>:<line> <function>; refs a, b)`` for the
    innermost frame of ``exc``'s traceback inside the v2 package, or ``""``
    when none is (the exception came from outside the engine)."""
    tb, last = exc.__traceback__, None
    while tb is not None:
        parts = os.path.normpath(tb.tb_frame.f_code.co_filename).split(os.sep)
        if _PACKAGE in parts:
            last = (tb, "/".join(parts[parts.index(_PACKAGE) + 1:]))
        tb = tb.tb_next
    if last is None:
        return ""
    tb, where = last
    refs = _refs_of(tb.tb_frame)
    tail = f"; refs {', '.join(refs)}" if refs else ""
    return f" (raised in {where}:{tb.tb_lineno} {tb.tb_frame.f_code.co_name}{tail})"
