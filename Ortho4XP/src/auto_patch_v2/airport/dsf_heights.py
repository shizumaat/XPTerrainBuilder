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
_POOL_LINE = re.compile(r"^#\s*pool\s+\d+:\s+p=(\d+)\s+s=\s*\d+\s+(.*)$")

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
        m = _POOL_LINE.match(line)
        if m is None:
            continue
        try:
            pools.append((int(m.group(1)), [float(v) for v in m.group(2).split()]))
        except ValueError:
            continue
    return pools


def _guess_good_heights(min_all: float, max_all: float, min_rng: float
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


def _file_heights(text: str) -> tuple[float, float]:
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
    return _guess_good_heights(min_all, max_all, min_rng)


def _is_overlay(text: str) -> bool:
    return any(line.split() == ["PROPERTY", "sim/overlay", "1"]
               for line in text.splitlines() if line.startswith("PROPERTY "))


def pin_heights(text: str) -> str:
    """``text`` with its ``HEIGHTS`` row rewritten from the file's own pool
    header (:func:`_file_heights`), in DSFTool's format.  A text with no
    ``HEIGHTS`` row, or not an overlay (a base mesh reads the row from its
    terrain pools, which this does not model), is returned unchanged."""
    if not _is_overlay(text):
        return text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = _HEIGHTS_LINE.match(line)
        if m is None:
            continue
        scale, offs = _file_heights(text)
        lines[i] = (f"HEIGHTS {scale / 65535.0:.5f} {offs:.1f}  "
                    f"# max encodeable {offs + scale:.5f}{m.group(1) or ''}")
        return "".join(lines)
    return text


#: the elevated object rows: ``OBJECT_MSL|OBJECT_AGL idx lon lat z hdg``
_ELEVATED = ("OBJECT_MSL ", "OBJECT_AGL ")


#: the coarsest quantum a written row may be encoded at: the round trip's
#: own elevation tolerance (``dsf_write.TOL_ELEV_M``), which a row encoded
#: at a coarser one fails (the encode floors to the quantum)
_FINE_QUANTUM = 0.0625


def _row_elevations(text: str) -> tuple[float, float] | None:
    """``(lowest, highest)`` elevation of the elevated object rows."""
    low = high = None
    for line in text.splitlines():
        if not line.startswith(_ELEVATED):
            continue
        toks = line.split()
        try:
            z = float(toks[4])
        except (IndexError, ValueError):
            continue
        low = z if low is None else min(low, z)
        high = z if high is None else max(high, z)
    return None if low is None else (low, high)


def cover_row_elevations(text: str) -> str:
    """``text`` with its ``HEIGHTS`` base lowered to cover the lowest
    elevated object row it carries, the quantum kept.

    ``--text2dsf`` encodes an elevation as ``base + quantum * q`` with
    ``q >= 0``, so a row below the base is refused — ``ERROR: could not
    place object`` — and the WHOLE file with it.  The pinned base comes
    from the pristine pools; a seat the plan writes at the sea surface
    (a ferry ramp at -0.08 m MSL) or at a below-sea-level airport lies
    under it.  The base drops to the whole metre under the lowest row
    (``GuessGoodHeights`` floors its offset the same way); a text whose
    rows all lie at or above the base is returned unchanged, byte for
    byte.

    #1903: a pristine DSF with NO elevated row pins DSFLib's empty answer,
    ``HEIGHTS 0.50000``, and a row the plan writes there (a body seated by
    its row) was encoded 0.27 m under its seat and refused by the round
    trip.  Where the quantum is coarser than :data:`_FINE_QUANTUM` the row
    is ``GuessGoodHeights`` over the written rows themselves."""
    got = _row_elevations(text)
    if got is None:
        return text
    low, high = got
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _HEIGHTS_LINE.match(line) is None:
            continue
        toks = line.split()
        try:
            quantum, base = float(toks[1]), float(toks[2])
        except (IndexError, ValueError):
            return text
        eol = _HEIGHTS_LINE.match(line).group(1) or ""
        if quantum > _FINE_QUANTUM:
            scale, offs = _guess_good_heights(low, high, high - low)
            if scale / 65535.0 < quantum:
                lines[i] = (f"HEIGHTS {scale / 65535.0:.5f} {offs:.1f}  "
                            f"# max encodeable {offs + scale:.5f}{eol}")
                return "".join(lines)
        if low >= base:
            return text
        offs = float(math.floor(low))
        lines[i] = (f"HEIGHTS {toks[1]} {offs:.1f}  # max encodeable "
                    f"{offs + quantum * 65535.0:.5f}{eol}")
        return "".join(lines)
    return text


__all__ = ["cover_row_elevations", "pin_heights", "pool_header"]
