"""A ROAD IN ITS OWN CUT THROUGH ZONE 2 FOLLOWS ITS GROUND UNDER THE BAND'S
CEILING (#2121; owner RULINGS 2026-10-20c (39) and 2026-10-19a) — a stage-2
rewrite.

A mapped carriageway through a runway or taxi band's zone 2 is cut out of
the band (``planar/road_yield``); its ribbon vertices standing in the cut
carry the road's own-ground target (the §37 (6) row,
``airport/road_ramp._cut_kerb_ground``) and the band's CEILING row only
(``constraints/zones``' cap-only kerb row).  Both are design rows: where the
road's ground stands over the band's grade the target would pull the road
up through the ceiling — and 19a lets a road beat the band only AT OR BELOW
its grade (13ar / 29r / 30b govern above it).

THE RULE.  Between the stages the band's ceiling at such a vertex is read
as a number: the zone row's bound less its pavement-foot terms, each foot at
stage 1's solved level, or — a foot stage 1 did not carry (a vertex the
ribbon-free map does not have) — at its published airside level (the
highest of its apron / taxi trend and preferred targets and its DEM, the
reading ``airport/road_ramp._airside_level`` takes).  The vertex's own-ground
target becomes the lower of the two: its ground where that is at or under
the band's grade, the band's ceiling where the ground stands over it.  The
rows stay design rows; nothing here is hard (a hard ceiling against a
lagged foot opened a 55 m pit at EGGW, lane l2121)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet, Linear
from ..model.planar import PlanarMap

__all__ = ["cut_kerb_rewrite"]

#: the zone law's adjacent-ground rows (``constraints/zones.zone_bands``)
_ZONE_GEN = "zones"
_ZONE_HEAD = "zones.adjacent_ground ("


def cut_kerb_rewrite(planar: PlanarMap, law: Law, cs: ConstraintSet,
                     levels: _t.Mapping[int, float]
                     ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """``(cs, report)``: every cut-kerb vertex's §37 (6) target lowered to
    the band's ceiling where the ceiling stands under it (module
    docstring)."""
    from .road_ramp import GEN, RULING, _cut_kerb
    cut = _cut_kerb(planar, law)
    rep: dict[str, _t.Any] = {"vertices": len(cut), "capped": 0, "max_cap_m": 0.0}
    if not cut:
        return cs, rep
    ceil = _ceilings(planar, cs, cut, levels)
    if not ceil:
        return cs, rep
    linears = []
    for r in cs.linears:
        v = _vertex(r) if r.source.generator == GEN and r.source.ruling == RULING else None
        if v in ceil and r.lo is not None and r.hi is not None and ceil[v] < r.hi:
            rep["capped"] += 1
            rep["max_cap_m"] = max(rep["max_cap_m"], round(float(r.hi) - ceil[v], 3))
            r = _dc.replace(r, lo=ceil[v], hi=ceil[v])
        linears.append(r)
    return _dc.replace(cs, linears=tuple(linears)), rep


def _ceilings(planar: PlanarMap, cs: ConstraintSet, cut: frozenset[int],
              levels: _t.Mapping[int, float]) -> dict[int, float]:
    """``{v: ceiling}``: the lowest cap-only zone row over each cut vertex,
    its foot terms read as numbers (module docstring)."""
    out: dict[int, float] = {}
    for r in cs.linears:
        if (r.source.generator != _ZONE_GEN or r.follows not in cut or r.lo is not None
                or r.hi is None or not str(r.source.ruling).startswith(_ZONE_HEAD)):
            continue
        own = sum(c for u, c in r.terms if u == r.follows)
        if own <= 0.0:
            continue
        rest = [(c, levels.get(u, _published(planar, u))) for u, c in r.terms
                if u != r.follows]
        if any(zu is None for _c, zu in rest):
            continue
        z = (float(r.hi) - sum(c * float(zu) for c, zu in rest)) / own
        out[r.follows] = min(z, out.get(r.follows, z))
    return out


def _published(planar: PlanarMap, v: int) -> float | None:
    """A foot's published airside level: the highest of its trend and
    preferred targets and its DEM (``airport/road_ramp._airside_level``)."""
    cands = [z for z in ((getattr(planar, "apron_trend_z", None) or {}).get(v),
                         (getattr(planar, "taxi_trend_z", None) or {}).get(v),
                         (getattr(planar, "preferred_z", None) or {}).get(v))
             if z is not None]
    dem = planar.vertices[v].dem_z if v in planar.vertices else None
    if dem is not None:
        cands.append(float(dem))
    return max(float(z) for z in cands) if cands else None


def _vertex(r: Linear) -> int | None:
    tag = r.source.inputs[0] if r.source.inputs else ""
    return int(tag[7:]) if tag.startswith("vertex:") else None
