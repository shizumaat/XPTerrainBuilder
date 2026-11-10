"""THE PLACEMENT ROWS OF A DSF TEXT DUMP — which rows are placements
(``airport/dsf.read_dump``'s grammar, row for row) and which of them are
one placement drawn twice (§15 (4), and the "Optimise pack" tolerance
groups of #1707 D1).

Pure text reads, shared by the write half (``airport/dsf_write`` edits
these rows) and the readers that only count or group them
(``pack_optimise``), kept apart from the writer so a reader does not key
its code on it (#1901).  ``dsf_write`` re-exports both names.
"""
from __future__ import annotations

import math
import typing as _t

from ..model.placement import CONVERTIBLE_KINDS, KIND_ON_GROUND

__all__ = ["placement_rows", "duplicate_rows"]


def placement_rows(lines: _t.Sequence[str]) -> list[tuple[int, int, list[str]]]:
    """``(ordinal, line index, tokens)`` for every row
    ``airport/dsf.read_dump`` counts as a placement, in dump order.

    The ordinal is the plan's ``index``, so the acceptance rule here is
    read_dump's EXACTLY — a row whose def index is out of range, or
    whose numbers do not parse, is a placement to neither (twin-asserted
    in ``tests/auto_patch_v2/test_v2dsfagl.py``)."""
    out: list[tuple[int, int, list[str]]] = []
    n_defs = 0
    ordinal = 0
    for i, raw in enumerate(lines):
        if not raw or raw[0] in "#\n":
            continue
        toks = raw.split()
        kw = toks[0]
        if kw == "OBJECT_DEF":
            n_defs += 1
            continue
        if kw == KIND_ON_GROUND and len(toks) >= 4:
            hi, elev_i = 4, None
        elif kw in CONVERTIBLE_KINDS and len(toks) >= 5:
            hi, elev_i = 5, 4
        else:
            continue
        try:
            oi = int(toks[1])
            float(toks[2]); float(toks[3])
            if len(toks) > hi:
                float(toks[hi])
            if elev_i is not None:
                float(toks[elev_i])
        except (ValueError, IndexError):
            continue
        if not (0 <= oi < n_defs):
            continue
        out.append((ordinal, i, toks))
        ordinal += 1
    return out


def duplicate_rows(lines: _t.Sequence[str],
                   of: _t.AbstractSet[int] | None = None, *,
                   tol_m: float | None = None, tol_deg: float = 0.0,
                   tol_h: float = 0.0) -> dict[int, list[int]]:
    """§15 (4): the DUPLICATE placement rows, ``{first ordinal: [the
    others]}``.

    Rows of one resource identical in DEF, longitude, latitude and
    HEADING are ONE placement: the pack drew the same object twice on
    the same spot, and the re-seat plan reads it once.  Splitting then
    replaced ONE of them and left the other drawing the WHOLE un-split
    object at the datum — measured on LEMD's pristine DSF, 19 of the
    ``Airport_Cargo`` resources carry two identical rows on the shared
    datum ``-3.564788 40.492764``, so 19 whole objects survived every
    split the plan made.

    ``of`` restricts the answer to groups whose FIRST row is one of
    those ordinals — the plan's SPLIT indices, an EMPTY set meaning no
    split and so no group: a pack that authors the same info sign twice
    on purpose is the pack's business, and nothing here touches a row no
    split replaces.  ``None`` is every group (what the twin reads).

    ``tol_m`` (issue #1707 D1, the user's "Optimise pack"): rows of one
    def and row kind whose positions lie within ``tol_m`` metres, headings
    within ``tol_deg`` and heights (``OBJECT_AGL`` / ``OBJECT_MSL``)
    within ``tol_h`` metres of a group's FIRST row are that placement
    too.  ``None`` (the default) is the exact token match above."""
    if tol_m is not None:
        groups = _near_groups(placement_rows(lines), tol_m, tol_deg, tol_h)
    else:
        seen: dict[tuple, list[int]] = {}
        for o, _i, toks in placement_rows(lines):
            hdg = toks[4] if toks[0] == KIND_ON_GROUND else (
                toks[5] if len(toks) > 5 else "")
            seen.setdefault((toks[0], toks[1], toks[2], toks[3], hdg),
                            []).append(o)
        groups = list(seen.values())
    return {v[0]: v[1:] for v in groups
            if len(v) > 1 and (of is None or v[0] in of)}


#: metres per radian on the mean Earth sphere (the D1 tolerance's frame)
_EARTH_R_M = 6371008.8


def _near_groups(rows: _t.Iterable[tuple[int, int, list[str]]], tol_m: float,
                 tol_deg: float, tol_h: float) -> list[list[int]]:
    """:func:`duplicate_rows`' tolerance groups, in dump order: each row
    joins the first group of its (kind, def) whose FIRST row is inside
    every tolerance, else starts one.  A grid of ``tol_m`` cells finds
    the candidates (the 3x3 cells around a row hold every row within
    ``tol_m``)."""
    cell = max(float(tol_m), 1e-3)
    firsts: dict[tuple, list[tuple[float, float, float, float | None, list[int]]]] = {}
    groups: list[list[int]] = []
    for o, _i, toks in rows:
        lat = float(toks[3])
        y = math.radians(lat) * _EARTH_R_M
        x = math.radians(float(toks[2])) * _EARTH_R_M * math.cos(math.radians(lat))
        if toks[0] == KIND_ON_GROUND:
            hdg, h = float(toks[4]), None
        else:
            h = float(toks[4])
            hdg = float(toks[5]) if len(toks) > 5 else 0.0
        gx, gy = int(math.floor(x / cell)), int(math.floor(y / cell))
        group = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for fx, fy, fh, fz, members in firsts.get(
                        (toks[0], toks[1], gx + dx, gy + dy), ()):
                    turn = abs(hdg - fh) % 360.0
                    if (math.hypot(x - fx, y - fy) <= tol_m
                            and min(turn, 360.0 - turn) <= tol_deg
                            and (h is None or abs(h - fz) <= tol_h)):
                        group = members
                        break
                if group is not None:
                    break
            if group is not None:
                break
        if group is None:
            group = []
            groups.append(group)
            firsts.setdefault((toks[0], toks[1], gx, gy), []).append(
                (x, y, hdg, h, group))
        group.append(o)
    return groups
