"""TRANSVERSE generator (family ``transverse``, ICAO Annex 14 §3.9.11 /
FAA §4; owner 2026-08-21 "the solver prices transverse"; spec
``transverse-hyperplane-solve-spec.md``).

THE STATION SET IS THE CENSUS'S OWN: :func:`geometry.walk_transects` is
the walk ``tools/check_grade`` prices with (``emit.transect`` carries its
constants), run over the SAME axes the emitter publishes in the sidecar
(:func:`axes`) and the SAME rings the patch carries.  At every station a
perpendicular crosses the priced ring twice; each hit is a linear
INTERPOLATION along a ring edge, so one cross-section is one four-term
``Linear`` row: ``|z_hi − z_lo| ≤ cT · width``.

Which shapes an axis prices (the census rule, lockstep): an AIRCRAFT
axis (a ``taxi_centerline``) prices the soft airside bodies — apron,
junction, service_junction (v1 ``TAXI_AXIS_PRICED_ROLES``); a SERVICE
axis (a ``road_centerline``) prices the road family only ("a truck route
is not an aircraft spine").  The budget is the AXIS's own transverse cap
(``transverse_cap_for_longitudinal_cap`` in v1: the cap of the role the
axis serves), not the crossed shape's.

An axis's longitudinal cap is the strictest governed cap of the faces its
chords bound (a stand lane inside an apron is apron, RULINGS
2026-09-03j); where that changes along a chain the chain is split so
every published axis carries ONE cap.
"""
from __future__ import annotations

import dataclasses as _dc

from ..law import Law
from ..law.tables import family, role_cap
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .geometry import TransectAxis, TransectShape, walk_transects
from .precedence import View, view
from .roads import road_family_roles

__all__ = ["Axis", "axes", "transverse", "priced_roles"]

GEN = "transverse"


@_dc.dataclass(frozen=True)
class Axis:
    """One published axis: its vertex chain, one longitudinal cap, its
    transverse cap and whether it is a service (truck) axis."""

    vertices: tuple[int, ...]
    cap_l: float
    cap_t: float
    is_service: bool
    ref: str


def priced_roles(law: Law, is_service: bool) -> frozenset[str]:
    """Roles a transect from this axis kind may price.  Service axes:
    the road family; aircraft axes: the lateral bodies — the roles the
    ``transverse`` family is defined over plus the soft bodies the v1
    walk prices (apron, junction, service_junction)."""
    if is_service:
        return frozenset(road_family_roles(law))
    return frozenset(("apron", "junction", "service_junction"))


def _edge_cap(vw: View, eid: int) -> tuple[float, float] | None:
    e = vw.pm.edges[eid]
    caps = [vw.caps[f] for f in (e.left_face, e.right_face)
            if f is not None and vw.caps[f] is not None]
    if not caps:
        return None
    return min(caps, key=lambda c: c[0])


def axes(planar: PlanarMap, law: Law) -> list[Axis]:
    """Every centreline breakline as one or more constant-cap axes."""
    vw = view(planar, law)
    out: list[Axis] = []
    for bid, b in planar.breaklines.items():
        if b.kind not in ("taxi_centerline", "road_centerline"):
            continue
        svc = b.kind == "road_centerline"
        chain = vw.chains[bid]
        cur: list[int] = []
        cur_cap: tuple[float, float] | None = None
        for k, eid in enumerate(b.edges):
            cap = _edge_cap(vw, eid)
            if cap is None:
                if len(cur) >= 2 and cur_cap is not None:
                    out.append(Axis(tuple(cur), cur_cap[0], cur_cap[1], svc, b.ref))
                cur, cur_cap = [], None
                continue
            if cur_cap is not None and cap != cur_cap:
                out.append(Axis(tuple(cur), cur_cap[0], cur_cap[1], svc, b.ref))
                cur = [chain[k]]
            elif not cur:
                cur = [chain[k]]
            cur.append(chain[k + 1])
            cur_cap = cap
        if len(cur) >= 2 and cur_cap is not None:
            out.append(Axis(tuple(cur), cur_cap[0], cur_cap[1], svc, b.ref))
    return out


def transverse(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One ``Linear`` row per priced cross-section."""
    vw = view(planar, law)
    tw = law.tables.emit.transect
    axs = axes(planar, law)
    roles = priced_roles(law, False) | priced_roles(law, True)
    shapes: list[TransectShape] = []
    ring_of: dict[int, list[int]] = {}
    for f in vw.faces_of_role(roles):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        ring_of[f.id] = ring
        shapes.append(TransectShape(
            f.role, [(vw.xy[v][0], vw.xy[v][1], 0.0) for v in ring], f.id))
    taxes = [TransectAxis([vw.xy[v] for v in a.vertices], a.cap_l,
                          a.is_service, key=i) for i, a in enumerate(axs)]
    rows: list[Row] = []
    for st in walk_transects(shapes, taxes,
                             lambda ax: priced_roles(law, ax.is_service),
                             step_m=tw.step_m, half_m=tw.half_width_m,
                             min_width_m=tw.min_width_m, max_gap_m=tw.max_gap_m):
        axis = axs[st.axis_key]
        ring = ring_of[st.shape_key]
        n = len(ring)
        terms: dict[int, float] = {}

        def add(v: int, c: float) -> None:
            terms[v] = terms.get(v, 0.0) + c

        a_lo, b_lo = ring[st.edge_lo], ring[(st.edge_lo + 1) % n]
        a_hi, b_hi = ring[st.edge_hi], ring[(st.edge_hi + 1) % n]
        add(a_hi, 1.0 - st.t_hi)
        add(b_hi, st.t_hi)
        add(a_lo, -(1.0 - st.t_lo))
        add(b_lo, -st.t_lo)
        terms = {v: c for v, c in terms.items() if abs(c) > 1e-12}
        if not terms:
            continue
        bound = axis.cap_t * st.width_m
        rows.append(Linear(tuple(terms.items()), -bound, bound,
                           Source(GEN, "rulesets.taxi.transverse (2026-08-21)",
                                  (f"axis:{axis.ref}", f"face:{st.shape_key}",
                                   f"station:{st.px:.1f},{st.py:.1f}"))))
    return rows
