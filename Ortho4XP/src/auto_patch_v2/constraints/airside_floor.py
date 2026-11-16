"""A STRUCTURE'S FLOOR NEVER STANDS ON AN AIRSIDE VERTEX (#2099 R3 Part A;
"airside is king"; owner RULINGS 2026-11-15k).

A vertex a stage-1 airside face carries (``model/platform.
stage_air_vertices``) is airside's: stage 1 solves it alone, and a
structure row naming it is a row the airside problem must also satisfy.
Measured CYYZ (#2099 R3 review): the M deck trench's datum group held a
taxiway corner, so the floor's seat less the deck's depth pulled the
taxiway 4 m under its DEM and stage 1 relaxed three hard rows (16.4 /
8.9 / 8.0 m).  The floor follows the airside, one direction only.

:func:`off_airside` is applied ONCE to the ``structures`` generator's own
rows before it returns (never a per-site veto):

* a ``Flat`` group loses its airside vertices (kept while two remain);
* a ``Diff`` / ``Offset`` / ``Band`` / ``Pin`` naming one is dropped;
* a ``Linear`` is dropped where its LEAD (first term — the floor vertex a
  seat row hangs) is airside; its other terms are the SEAT the floor
  hangs from, and an airside seat vertex there is untouched.

The generator supplies each floor row's lead from the group's first
non-airside vertex (:func:`lead`), so a floor with any vertex of its own
keeps its seat rows."""
from __future__ import annotations

import collections
import dataclasses as _dc
import typing as _t

from ..model.constraints import Band, Diff, Flat, Linear, Offset, Pin, Row

__all__ = ["off_airside", "lead"]


def lead(vs: _t.Sequence[int], air: _t.Collection[int]) -> int | None:
    """The first vertex of ``vs`` no airside face carries, or ``None``."""
    return next((v for v in vs if v not in air), None)


def off_airside(rows: _t.Iterable[Row], air: _t.Collection[int]
                ) -> tuple[list[Row], dict[str, int]]:
    """``(rows less every airside vertex as the module doc states, the
    count of rows changed or dropped per kind)``."""
    out: list[Row] = []
    n: dict[str, int] = collections.Counter()
    if not air:
        return list(rows), {}
    for r in rows:
        if isinstance(r, Flat):
            keep = tuple(v for v in r.group if v not in air)
            if len(keep) == len(r.group):
                out.append(r)
                continue
            n["flat"] += 1
            if len(keep) > 1:
                out.append(_dc.replace(r, group=keep))
            continue
        if isinstance(r, (Diff, Offset)):
            if r.a in air or r.b in air:
                n["diff" if isinstance(r, Diff) else "offset"] += 1
                continue
        elif isinstance(r, (Band, Pin)):
            if r.v in air:
                n["band" if isinstance(r, Band) else "pin"] += 1
                continue
        elif isinstance(r, Linear):
            if r.terms and r.terms[0][0] in air:
                n["linear"] += 1
                continue
        out.append(r)
    return out, dict(n)
