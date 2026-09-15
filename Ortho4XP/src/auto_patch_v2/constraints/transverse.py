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
from .stretches import edge_cap, stretches
from .roads import road_family_roles

__all__ = ["Axis", "axes", "transverse", "priced_roles",
           "junction_raw_transverse", "RAW_PAIR_RULING",
           "RAW_PAIR_CONTACT_RULING"]

GEN = "transverse"

#: §34 (13) (3) THE RAW PAIR IS THE JUNCTION'S TRANSVERSE LAW (Fable
#: 2026-09-15; RULINGS 2026-09-15y; owner 15e item 7 "the lateral slope …
#: still not fixed").  Registered in ``[design] one_way_rulings``: where
#: one end of the pair is a vertex the JUNCTION SHARES WITH A RUNWAY, the
#: junction end follows and the runway's column never feels it — AIRSIDE
#: IS KING, and the runway's edge level at the contact is the datum the
#: junction's width is measured from.
RAW_PAIR_RULING = ("rulesets.taxi.transverse raw pair "
                   "(Fable 2026-09-15; RULINGS 2026-09-15y; spec §34 (13) (3))")
#: §34 (13) (3), THE CONTACT ROW: the raw pair one of whose ends is a
#: vertex the junction SHARES WITH A RUNWAY — "the runway's edge level at
#: the contact per airside-is-king".  Its own head so the two halves of
#: the law can be told apart in a report and in the registers.
#:
#: IT IS NOT A HARD ROW, AND THAT WAS MEASURED TWICE, NOT ARGUED.  The
#: row is minted correctly and ONE-WAY (LEMD pav157: ±0.268 m over
#: 18.12 m, ``follows`` the junction's far edge v6622) and as a TARGET it
#: LOSES — the site still reads 5.01 % against ``foot_rows`` (dual
#: 42,656, the object feet), ``junction_mesh`` at cap 1.50 % × 43.2 m and
#: ``no_step_pairs``.  Hardening the whole family (1,591 rows) leaves
#: **10,006 of 109,240 hard rows violated, worst 60.48 m**; hardening
#: only this CONTACT subset (**62 rows**) leaves **8,548 of 106,182
#: violated, worst 105.29 m**.  A junction's far edge is over-determined
#: — the feet, the zone band, the mesh and the no-step pairs all hold it
#: — so the raw pair stands as the LAW and as a target, and §34 (13) (3)'s
#: own alternative ("or the residual named with the row that binds and
#: the object feet that yield") is what r3 reports.
RAW_PAIR_CONTACT_RULING = (
    "rulesets.taxi.transverse raw pair at a runway contact "
    "(Fable 2026-09-15; RULINGS 2026-09-15y; spec §34 (13) (3))")

#: §34 (13) (3): the RUNWAY family, for the contact test.  The same two
#: role names ``planar/zones`` and ``check_grade`` key by.
_RUNWAY_FAMILY = ("runway", "runway_crossing")


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
    """A centreline edge's cap: its STRETCH's (RULINGS 2026-09-04t-3),
    tightened by a governed non-taxi face it bounds; a road edge the
    strictest bounding face (``stretches.edge_cap``)."""
    return edge_cap(vw.pm, vw.law, stretches(vw.pm, vw.law), eid, vw.caps)


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


def junction_raw_transverse(planar: PlanarMap, law: Law, airport: Airport
                            ) -> list[Row]:
    """§34 (13) (3) THE RAW PAIR IS THE JUNCTION'S TRANSVERSE LAW (Fable
    2026-09-15; RULINGS 2026-09-15y; owner 15e item 7).

    :func:`transverse` above prices a cross-section as a FOUR-TERM row —
    a vertex against a point INTERPOLATED along the far ring edge — and
    at LEMD's ``pav157`` every one of those rows sits AT ITS BOUND
    (1.35 % of a 1.5 % cap) while the RAW PAIR across the same junction,
    the reading ``tools/check_grade`` prices and the reading the owner
    sees from the cockpit, reads **4.30 %** (0.78 m over 18.12 m between
    v906 on the runway edge and v6622, the junction's far edge).  Two
    instruments, one geometry, and the ruling settles it: the raw pair is
    the law, and a satisfied 4-term row does not discharge it.

    THE STATION SET IS THE SAME WALK, never a second one
    (:func:`geometry.walk_transects`, the census's own): at each station
    the transect crosses the junction's ring twice, and this row prices
    the two RING VERTICES those hits fall nearest — real emitted columns,
    which is what makes it a raw pair — over their own plan distance, at
    the axis's transverse cap.

    AIRSIDE IS KING AT THE CONTACT.  A junction that touches a runway
    shares its nodes there (LEMD: v906 carries ``junction#86`` and
    ``runway#5`` both).  Where exactly one end of the pair is such a
    shared vertex the row is ONE-WAY on the other end — the junction's
    far edge follows, the runway's own column never moves — so the
    junction's width is measured FROM the runway's edge level.  Where
    BOTH ends are runway-shared the runway owns the pair and no row is
    minted; where NEITHER is, the row is two-way between two junction
    columns.

    The population is the JUNCTION role alone.  The apron and
    ``service_junction`` bodies the aircraft axis also prices keep the
    4-term reading: 15y rules the raw pair for the junction, which is the
    shape the owner's site is, and a law is widened by measurement, not
    by analogy."""
    vw = view(planar, law)
    tw = law.tables.emit.transect
    axs = axes(planar, law)
    shapes: list[TransectShape] = []
    ring_of: dict[int, list[int]] = {}
    for f in vw.faces_of_role(frozenset(("junction",))):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        ring_of[f.id] = ring
        shapes.append(TransectShape(
            f.role, [(vw.xy[v][0], vw.xy[v][1], 0.0) for v in ring], f.id))
    if not shapes:
        return []
    taxes = [TransectAxis([vw.xy[v] for v in a.vertices], a.cap_l,
                          a.is_service, key=i) for i, a in enumerate(axs)]
    on_runway = {
        v for v, vx in planar.vertices.items()
        if any(planar.faces[fid].role in _RUNWAY_FAMILY
               for fid in vx.incident_faces if fid in planar.faces)}
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    seen: set[tuple[int, int]] = set()
    rows: list[Row] = []
    for st in walk_transects(shapes, taxes,
                             lambda ax: frozenset(("junction",)),
                             step_m=tw.step_m, half_m=tw.half_width_m,
                             min_width_m=tw.min_width_m, max_gap_m=tw.max_gap_m):
        axis = axs[st.axis_key]
        if axis.is_service:
            continue                     # a truck route is not an aircraft spine
        ring = ring_of[st.shape_key]
        n = len(ring)
        a = ring[st.edge_lo if st.t_lo < 0.5 else (st.edge_lo + 1) % n]
        b = ring[st.edge_hi if st.t_hi < 0.5 else (st.edge_hi + 1) % n]
        if a == b:
            continue
        key = (min(a, b), max(a, b))
        if key in seen:
            continue                     # one row per pair, not per station
        ax_, ay_ = vw.xy[a]
        bx_, by_ = vw.xy[b]
        d = ((ax_ - bx_) ** 2 + (ay_ - by_) ** 2) ** 0.5
        if d < min_d:
            continue
        a_run, b_run = a in on_runway, b in on_runway
        if a_run and b_run:
            continue                     # the runway owns both columns
        follows = (b,) if a_run else (a,) if b_run else None
        seen.add(key)
        bound = axis.cap_t * d
        rows.append(Linear(((a, 1.0), (b, -1.0)), -bound, bound,
                           Source(GEN,
                                  RAW_PAIR_CONTACT_RULING if follows
                                  else RAW_PAIR_RULING,
                                  (f"axis:{axis.ref}", f"face:{st.shape_key}",
                                   f"vertex:{a}", f"vertex:{b}")),
                           follows=follows))
    return rows
