"""ONE BUILDING, ONE DATUM (owner RULINGS 2026-10-19u, issue #798 (a)).

Owner, answering "#798a, KASE multi-file buildings whose pieces sit 0.78 m
and 2.2 m apart: one shared datum plus a level pad cut into the apron where
airside rules allow, tilt as one, or shared height only?": "Shared height
plus pad would be best".  This module is the SHARED HEIGHT half, read
plan-wide in ``footprint_unit.plan_unit_datums`` so every seat that reads
the plan-wide map (the §16g bind, the issue #10 unit-carried pieces) takes
the same zero.  The pad half is the slope pad (RULINGS 2026-10-19w).
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar
from .placement_family import _median

__all__ = ["one_building_groups", "walled_files", "pavement_top", "span_m"]


def one_building_groups(units: _t.Sequence[_t.Any],
                         out: dict[str, tuple[float, str, str]],
                         pav: _t.Mapping[str, tuple[float, frozenset]],
                         reach_m: float = 0.0, span_max_m: float = 0.0
                         ) -> dict[str, tuple[float, str, str]]:
    """A MULTI-FILE BUILDING ON PAVEMENT SEATS ON ONE SHARED DATUM (owner
    RULINGS 2026-10-19u, issue #798 (a); overrides 12ap (A) and §16g (2)'s
    "pavement is king" for this case).

    The pieces: footprint units standing entirely on rolled-on pavement
    (``pav``) that hold bodies of one resource FILE (one rigid authored
    frame) and whose part boxes come within ``reach_m`` (``[placement]
    piece_reach_m``, 14p (3)'s reach for the pieces of one building),
    chained transitively.  The witness that they are a BUILDING: their
    walled files (:func:`walled_files`) number two or more, and its plan
    span stays under ``span_max_m`` (``[placement] connector_span_m``, the
    span at which §16g (6) stops reading a body as holding its unit rigid:
    HECA's elevated rail, ``road_train/titles_1`` on its concrete bases, is
    400 m of pillars and one datum floated it 2.10 m).  Such a group
    takes ONE datum, the highest any of its pieces' feet imply on the
    pavement (17x's floor, so no piece is written under the apron); every
    other unit keeps its datum and pavement-is-king.

    MEASURED (KASE, the 1.0.398 app mesh): the tower's files fell into four
    footprint units 0.75-1.61 m apart with datums 0.78 m apart, Hangar1's
    pieces 2.22 m apart; pavement-is-king seated each piece on the apron
    under its own feet."""
    ids = [un for un in units if un.id in pav]
    if not ids:
        return out
    par = list(range(len(ids)))

    def find(i: int) -> int:
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i

    def touch(a, b) -> bool:
        for p in a.boxes:
            ml, mo = _ar._m_per_deg(0.5 * (p[0] + p[2]))
            for q in b.boxes:
                dy = max(0.0, p[0] - q[2], q[0] - p[2]) * ml
                dx = max(0.0, p[1] - q[3], q[1] - p[3]) * mo
                if dx * dx + dy * dy <= reach_m * reach_m:
                    return True
        return False
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if (set(ids[i].members) & set(ids[j].members)
                    and find(i) != find(j) and touch(ids[i], ids[j])):
                par[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(ids)):
        groups.setdefault(find(i), []).append(i)
    for g in groups.values():
        walled = frozenset().union(*(pav[ids[i].id][1] for i in g))
        if len(walled) < 2 or (span_max_m > 0.0 and span_m(
                [b for i in g for b in ids[i].boxes]) >= span_max_m):
            continue
        top = max(max(float(out[ids[i].id][0]), pav[ids[i].id][0]) for i in g)
        for i in g:
            out[ids[i].id] = (top, out[ids[i].id][1], "one_building")
    return out


def span_m(boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """The diagonal of the boxes' joint lat/lon extent, in metres."""
    if not boxes:
        return 0.0
    lo0 = min(b[0] for b in boxes); hi0 = max(b[2] for b in boxes)
    lo1 = min(b[1] for b in boxes); hi1 = max(b[3] for b in boxes)
    ml, mo = _ar._m_per_deg(0.5 * (lo0 + hi0))
    return float(((hi0 - lo0) * ml) ** 2 + ((hi1 - lo1) * mo) ** 2) ** 0.5


def walled_files(mine: _t.Sequence[_t.Any], plan: _t.Any,
                  wall_min_m: float) -> frozenset:
    """The resource FILES of the unit that hold a WALLED part — one at
    least ``[placement] chain_min_height_m`` tall (``Part.height_m``, §16g
    (10) (4)'s own test of a wall).  19u's MULTI-FILE BUILDING has two or
    more: a row of signs on a painted kerb is two files with one wall at
    most (MEASURED, HECA ``titles_1`` + ``T3_concrete_Yellow``, 300 m of
    apron: one shared datum floated it 2.10 m), a hangar authored as five
    files has walls in several.  ``wall_min_m`` 0 counts every file."""
    pids = {p.pid for p in mine}
    tall = {p.pid for p in mine if wall_min_m <= 0.0
            or float(getattr(p, "height_m", 0.0)) >= wall_min_m}
    files = set()
    for u in plan.units:
        for m in u.members:
            if any(p.pid in tall for p in m.parts if p.pid in pids):
                files.add(m.resource)
    return frozenset(files)


def pavement_top(cc: _t.Sequence[tuple[float, float, float, float]],
                  parts: _t.Sequence[_t.Any],
                  surface: _ar.Surface) -> "float | None":
    """When EVERY part centre ``cc`` stands on rolled-on pavement (the
    sampler's own role channels, as ``footprint_unit._airside_floor`` reads them):
    the HIGHEST zero any part's own feet imply on that pavement — per part
    the median of ``ground - y`` over its feet, 17x's floor read per rigid
    piece, so no piece of the building is written under the apron; else
    ``None``."""
    roles = getattr(surface, "roles", None)
    rolled = getattr(surface, "rolled_on", None)
    if roles is None or not rolled or not cc:
        return None
    got = roles.roles_many([q[0] for q in cc], [q[1] for q in cc])
    if not all(r in rolled for r in got):
        return None
    top = max(float(q[3]) for q in cc)
    for p in parts:
        feet = list(getattr(p, "feet", ()) or ())
        if not feet:
            continue
        rs = roles.roles_many([f[0] for f in feet], [f[1] for f in feet])
        zs = [g - float(f[2]) for f, r in zip(feet, rs)
              if r in rolled and (g := surface(f[0], f[1])) is not None]
        if zs:
            top = max(top, _median(zs))
    return top
