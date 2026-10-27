"""The ``HEIGHTS`` row a DSF dump carries, read from the FILE, not from
DSFTool's memory.

``DSFTool --dsf2text`` prints ``HEIGHTS quantum base`` from
``GuessGoodHeights`` over the elevation plane of every OBJECT pool the
command stream selects (``DSFLib.cpp``, ``DSFReadFile``).  It reads that
plane as index 3 of EVERY such pool, and a plain ``OBJECT`` pool has
three planes: the read runs off the end of the pool's plane vector, so
the printed row follows whatever memory lies there (#166, #181: one
input, two runs, two rows).  The ``# pool`` header lines the same dump
prints are the file's own scales and offsets and are exact.

``--text2dsf`` builds the object pools' elevation range from the
``HEIGHTS`` row it reads, so carrying the printed row into an encode made
the written bytes a function of that memory: two writes of one plan from
one pristine DSF came out with an elevation plane based at 0 and at -1
(CI, Windows, batch AK 2026-10-27).  :func:`pin_heights` replaces the row
with the one DSFTool would print without the over-read: the same
``GuessGoodHeights`` over the four-plane object pools only.
"""
from __future__ import annotations

import math
import re

#: ``# pool N: p=P s=S  span0 off0  span1 off1 ...`` (``DSFReadFile``).
POOL_LINE = re.compile(r"^#\s*pool\s+\d+:\s+p=(\d+)\s+s=\s*\d+\s+(.*)$")

#: ``HEIGHTS quantum base`` with DSFTool's trailing comment, if any.
_HEIGHTS_LINE = re.compile(r"^HEIGHTS\s+\S+\s+\S+.*?(\r?\n)?$")

#: An object pool's heading plane: span 360, offset 0.
_HEADING_SPAN = 360.0


def pool_header(text: str) -> list[tuple[int, list[float]]]:
    """``[(planes, [span0, off0, span1, off1, ...]), ...]`` of the dump's
    ``# pool`` header, in order.  The header is the leading comment block:
    reading stops at the first row after it."""
    pools: list[tuple[int, list[float]]] = []
    for line in text.splitlines():
        if not line.startswith("#"):
            if pools:
                break
            continue
        m = POOL_LINE.match(line)
        if m is None:
            continue
        try:
            pools.append((int(m.group(1)), [float(v) for v in m.group(2).split()]))
        except ValueError:
            continue
    return pools


def guess_good_heights(min_all: float, max_all: float, min_rng: float
                       ) -> tuple[float, float]:
    """``(scale, offset)`` — DSFLib's ``GuessGoodHeights``, line for line
    (the scale is the plane's whole span, ``quantum * 65535``)."""
    offs = math.floor(min_all)
    max_rng = max_all - offs
    scale = 65535.0
    for _ in range(5):
        if max_rng > scale * 0.5:
            break
        if min_rng * 0.7 >= scale:
            break
        scale *= 0.5
    if max_all <= scale and offs > 0.0:
        offs = 0.0
    return scale, float(offs)


def file_heights(text: str) -> tuple[float, float]:
    """``(scale, offset)`` DSFTool's dump of an OVERLAY would print if it
    read only the elevation plane of the four-plane object pools (plane 2
    is the heading, span 360).  With none, DSFLib's own empty answer."""
    min_all, max_all, min_rng = 32767.0, -32768.0, 65535.0
    for planes, vals in pool_header(text):
        if planes < 4 or len(vals) < 8:
            continue
        if abs(vals[4] - _HEADING_SPAN) > 1e-6 or vals[5] != 0.0:
            continue
        span, off = vals[6], vals[7]
        min_all = min(min_all, off)
        max_all = max(max_all, off + span)
        min_rng = min(min_rng, span)
    return guess_good_heights(min_all, max_all, min_rng)


def _is_overlay(text: str) -> bool:
    return any(line.split() == ["PROPERTY", "sim/overlay", "1"]
               for line in text.splitlines() if line.startswith("PROPERTY "))


def pin_heights(text: str) -> str:
    """``text`` with its ``HEIGHTS`` row rewritten from the file's own pool
    header (:func:`file_heights`), in DSFTool's format.  A text with no
    ``HEIGHTS`` row, or not an overlay (a base mesh reads the row from its
    terrain pools, which this does not model), is returned unchanged."""
    if not _is_overlay(text):
        return text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = _HEIGHTS_LINE.match(line)
        if m is None:
            continue
        scale, offs = file_heights(text)
        lines[i] = (f"HEIGHTS {scale / 65535.0:.5f} {offs:.1f}  "
                    f"# max encodeable {offs + scale:.5f}{m.group(1) or ''}")
        return "".join(lines)
    return text


__all__ = ["POOL_LINE", "file_heights", "guess_good_heights",
                     "pin_heights", "pool_header"]
