"""THE 5 % PAVEMENT CEILING (owner RULINGS 2026-09-09b (4), verbatim:
"all pavement including groundside has a MAX grade of 5 %; roads are the
only exception at 8 %"; law values ``rulesets.toml [common]
pavement_max_grade`` / ``road_max_grade``).

Under the design surface every class cap is a TARGET the solve aims for
(owner 08t answer 4) — so a pavement the geometry fights can be graded as
steeply as the sheet likes.  The owner's answer is a CEILING no class may
cross: HARD in the design solve's active set beside the runway rows
(``emit.toml [design] hard_rulings`` names this module's ruling), while
the per-class letter caps stay one-sided targets under it.

THE POPULATION IS THE LAW SET ITSELF.  This is a POST-PASS over every row
the generators minted (``constraints.generate``, beside ``seam_exempt``
and ``reconcile_datums``), never a second reading of the geometry: a
class cap is already stated over exactly the pairs the law prices — the
chain's hops and centreline edges, the short-pair box, the within-shape
pairs, the no-step pairs, the lateral-contiguity rows.  For each such
DIFFERENCE row over PAVEMENT vertices this mints ONE twin at the ceiling
over the same span; identical spans are minted once (the same pair is
priced by several families).

A DIFFERENCE ROW is a ``Diff``, or a two- / three-term two-sided
``Linear`` of the point-vs-interpolated-point form ``c·(z_v − z_foot)``
(the chain's foot rows, the transverse hops).  Everything else — the
vertical-curve and rate rows (second differences), the plane-gradient
half-planes, the bands, the offsets — states no span and mints nothing;
their own geometry is bounded by the pair rows over the same vertices.

THE CEILING IS LOCAL.  A twin is minted only over a span shorter than
``emit.within_shape.withdrawn_chord_min_m`` (30 m — the box's own floor):
the grade between two points farther apart than that is read along the
ROUTE, never across the chord (owner 2026-09-05aa, the withdrawn chord
law), and a surface whose every local pair is inside the ceiling cannot
run steeper than it along a chain.  Measured HECA: without the span
limit the pass mints 201k twins (the no-step route-window pairs) and the
solve's wall triples for no change in the built grades.

WHICH CEILING: ``road_max_grade`` where EVERY vertex of the row belongs
to road-family faces only (a FREE road, owner 2026-08-03's 8 %), else
``pavement_max_grade``.  A road welded into an apron IS the apron
(free-road ruling) and takes the 5 %.  A vertex of no non-structure VALUE
face — the graded strip, the clearances, a structure's own ring — is not
pavement and its rows mint nothing: the adjacent ground is a law surface
(09-09b (3)), not a capped pavement.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import is_structure_role, is_value_role
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["pavement_ceiling", "GEN", "RULING"]

GEN = "pavement_ceiling"
#: The ruling HEAD ``[design] hard_rulings`` names (everything before the
#: first parenthesis, ``solve.design.is_hard``).
RULING = ("rulesets.common.pavement_max_grade ceiling "
          "(owner 2026-09-09b (4))")

#: A coefficient is treated as balanced within this (the rows are built
#: from exact interpolation weights, so this only absorbs float error).
_EPS = 1.0e-9


def _span(terms: _t.Sequence[tuple[int, float]],
          xy: _t.Mapping[int, tuple[float, float]]
          ) -> tuple[float, float] | None:
    """``(head coefficient, span in metres)`` of a point-vs-interpolated-
    point row, or ``None`` when the row is not of that form: exactly one
    POSITIVE coefficient, the negatives summing to its opposite."""
    pos = [(v, c) for v, c in terms if c > 0.0]
    neg = [(v, c) for v, c in terms if c < 0.0]
    if len(pos) != 1 or not neg:
        return None
    (hv, hc) = pos[0]
    if abs(sum(c for _v, c in neg) + hc) > _EPS * max(1.0, abs(hc)):
        return None
    hx, hy = xy[hv]
    fx = sum(-c * xy[v][0] for v, c in neg) / hc
    fy = sum(-c * xy[v][1] for v, c in neg) / hc
    d = math.hypot(hx - fx, hy - fy)
    return (hc, d) if d > 0.0 else None


def pavement_ceiling(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                     ) -> list[Row]:
    """The ceiling twins of ``rows`` (module docstring)."""
    common = law.tables.common
    ceil_pav = float(common.pavement_max_grade)
    ceil_road = float(common.road_max_grade)
    pav_roles = {r for r in law.tables.precedence.roles
                 if is_value_role(law, r) and not is_structure_role(law, r)}
    road_roles = set(law.tables.families["road_cross_section"].roles)
    pav: set[int] = set()
    road_only: set[int] = set()
    for f in planar.faces.values():
        if f.role not in pav_roles:
            continue
        vs = [v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)]
        pav.update(vs)
        if f.role in road_roles:
            road_only.update(v for v in vs if v not in road_only)
    # 30e (4): a ribbon's KERB shared with a zone band leads for the BAND
    # (29r): a row from the kerb to anything but the ribbon (the strip's
    # transverse pairs to the runway, the band's own pairs) is the band's
    # law surface and is not twinned; a row from the kerb INTO the ribbon
    # is the road's and keeps the road cap (29ab (1), 29ac)
    kerb = planar.band_kerb_vertices()
    rib_vs: set[int] = set()
    if kerb:
        from ..model.planar import is_osm_ribbon_ref
        for f in planar.faces.values():
            if f.role in road_roles and is_osm_ribbon_ref(f.ref):
                for ring in (f.ring, *f.holes):
                    rib_vs.update(planar.ring_vertices(ring))

    def _band_row(vset) -> bool:
        return bool(kerb) and bool(vset & kerb) and not vset <= rib_vs
    # a vertex any NON-road pavement also touches is that pavement's
    # (the free-road ruling: only a genuinely free road keeps the 8 %)
    for f in planar.faces.values():
        if f.role in pav_roles and f.role not in road_roles:
            for ring in (f.ring, *f.holes):
                road_only.difference_update(planar.ring_vertices(ring))
    max_span = float(law.tables.emit.within_shape.withdrawn_chord_min_m)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    src = Source(GEN, RULING, ())
    seen: set[tuple] = set()
    out: list[Row] = []
    # A PAD'S OWN CEILING IS STRICTER AND ALREADY HARD (owner 2026-09-09c,
    # spec §9.2 B5): twinning its 1 % rows at 5 % adds one row per pad pair
    # and constrains nothing.
    # A PAD'S FRONTAGE LEVEL ROW IS THE SAME CASE (owner 2026-09-10l/10y):
    # a cap-0 ONE-WAY row twinned two-way at 5 % is a route by which the
    # pad could pull the pavement edge it is supposed to follow.
    # A GROUNDSIDE FRONTAGE ROW IS THE SAME CASE AGAIN (owner RULINGS
    # 2026-09-12r, spec §28): a cap-0 ONE-WAY row twinned two-way at 5 %
    # is a route by which the LOT could pull the PAD it is supposed to
    # follow, and §28 (2) is that a pad's level never moves.
    from .pad_frontage_gs import GS_LEVEL_JUNIOR_RULING as _GS_LVL_J
    from .pad_frontage_gs import GS_LEVEL_RULING as _GS_LVL
    from .pads import CEILING_RULING as _PAD_CEIL
    from .pads import LEVEL_JUNIOR_RULING as _PAD_LVL_J
    from .pads import LEVEL_RULING as _PAD_LVL
    # THE PLATFORM COLLAR IS A 1:3 BANK (unit-platform spec §3 P11, §20 C5's
    # reason): twinned at the 5 % pavement ceiling it would make the bank a
    # HARD 5 % grade under the building — the collar exists to be steeper
    # than that; and its plane rows are already hard equalities.
    from .platform import COLLAR_RULING as _COLLAR
    from .platform import PLANE_RULING as _PLANE
    from .platform import RIM_RULING as _RIM
    _skip = {_PAD_CEIL, _PAD_LVL, _PAD_LVL_J, _GS_LVL, _GS_LVL_J, _COLLAR, _PLANE,
             _RIM}
    # RULINGS 2026-09-30aa rule 1 (#100): a twin CARRIES its row's minting
    # face (``face:N``), so a twin of a WELDED road's row is stage 2's with
    # its row; and the airside's own rows are twinned FIRST, so a pair both
    # price keeps the twin the airside alone would give it (measured HECA:
    # 460 twins reached stage 1 off ribbon rows)
    from .roads import welded_road
    welded = {f"face:{f.id}" for f in planar.faces.values() if welded_road(f)}

    def _welded_src(row) -> bool:
        return bool(welded) and any(t in welded for t in row.source.inputs)
    for row in sorted(rows, key=_welded_src) if welded else rows:
        if row.source.ruling.split(" (")[0].strip() in _skip:
            continue
        src = Source(GEN, RULING, tuple(t for t in row.source.inputs
                                        if str(t).startswith("face:")))
        if isinstance(row, Diff):
            vs: tuple[int, ...] = (row.a, row.b)
            if not 0.0 < row.d <= max_span or not set(vs) <= pav \
                    or _band_row(set(vs)):
                continue
            key = (min(vs), max(vs))
            if key in seen:
                continue
            seen.add(key)
            cap = ceil_road if set(vs) <= road_only else ceil_pav
            # §50.1 (6) THE CEILING NEVER RE-IMPOSES WHAT THE PINS REFUSE:
            # a row the law itself prices ABOVE the ceiling (a yielded
            # runway, an altiport) is not twinned below its own cap — the
            # twin would re-make infeasible exactly what §50 made feasible.
            out.append(Diff(row.a, row.b, max(cap, row.cap), row.d, src))
            continue
        if not isinstance(row, Linear) or row.source.generator == GEN:
            continue
        if row.lo is None or row.hi is None or abs(row.lo + row.hi) > _EPS:
            continue                       # not a symmetric two-sided span row
        if len(row.terms) not in (2, 3):
            continue
        vs2 = {v for v, _c in row.terms}
        if not vs2 <= pav or _band_row(vs2):
            continue
        got = _span(row.terms, xy)
        if got is None:
            continue
        hc, d = got
        if d > max_span:
            continue
        key = tuple(sorted(row.terms))
        if key in seen:
            continue
        seen.add(key)
        cap = ceil_road if vs2 <= road_only else ceil_pav
        # §50.1 (6), the two-sided form: the twin's bound never falls
        # below the ROW'S OWN bound.
        bound = max(hc * cap * d, float(row.hi))
        out.append(Linear(row.terms, -bound, bound, src))
    return out
