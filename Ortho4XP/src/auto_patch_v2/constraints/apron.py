"""APRON generator (families ``within_shape`` on aprons and
``apron_lattice_membrane``; RULINGS 2026-08-21b/c/d, 2026-08-24b/c,
2026-08-26).

THE APRON WITHIN-SHAPE POPULATION (2026-08-21c, spec
``apron-within-shape-population``): an apron's strict cap
(``common.roles.apron``) is owed on its MOVEMENT SURFACES — every ring
edge, every chord from a ring vertex to a SPINE vertex (a taxi / road
centreline vertex on the ring) and every FRONTAGE chord from a pad
vertex (a vertex a rigid face shares with the apron: the building seat
the census prices at the strict cap, 2026-08-08 / 09-01g); a
generic interior body chord is law at the interior fan cap
(``common.apron_fan_ramp_max``) out to ``within_shape.apron_body_chord_max_m``
and not a grade path beyond it.  The census gates body chords further by
polygon visibility; v2 prices the superset, which can only be stricter.

CAP BY EDGE PORTION (RULINGS 2026-09-04t-2, refining owner 2026-07-06):
a junction / road / other governed face sharing a LONG EDGE with an
apron takes the apron's cap on the portion ALONG the apron — every pair
inside one contiguous run of ring edges shared with an apron whose
length is at least ``within_shape.apron_edge_portion_min_width_ratio``
face widths (:func:`apron_edge_portions`); a MOUTH (a shorter shared
run: a corridor joining or leaving the apron) keeps the face's own cap,
and so does every pair with a vertex off the run.  v1's oracle applied
the apron cap to the junction's whole body (``grade_graph.
_body_cap_unbounded``); the oracle now follows the same portion rule.

A CHORD STAYS INSIDE ITS FACE (RULINGS 2026-09-05ae(1), the owner's KML
read at 30°07'40.66"N 31°24'45.73"E): a frontage / spine or body chord is
a row ONLY when the straight chord lies entirely inside the apron face —
crossing no hole and no exterior (:func:`geometry.face_cover` at the snap
tolerance, ``shapely.covered_by``).  HECA pav132's 585–770 m frontage
chords left the pavement through the face's hole where a road and a
building stand, and 21 km of the relaxation's 26.5 km of relief rode on
them; the ring edges and the inside chords carry the apron law around
the obstacle.  A dropped chord is counted in ``STATS["chords_outside_
face"]`` (published by ``generate`` under ``apron_within_shape.chords_
outside_face``).  A ring edge is never a chord and is never dropped.

A ROUTE THROUGH THE APRON (owner, RULINGS 2026-09-06t; spec author,
RULINGS 2026-09-06v; spec ``apron-route-cap`` §3 amended): the taxi
centreline stretch crossing an apron face keeps the taxiway law
(``stretches.edge_cap``), and the apron beside it is ANISOTROPIC — within
a face CROSSED by a stretch (``stretches.crossing_axes``: an edge of the
stretch on one of the face's rings) EVERY priced pair (ring edges, spine
chords, body chords under their gates and the 05ae face-cover gate) at
ANY length is the BOX against the crossing axis nearest its midpoint
(ties strictest): ``|Δz| ≤ cL_stretch·|Δs| + cA·|Δt|``, cL the
stretch's longitudinal cap and cA the APRON cap across (06s's
``AxisIndex`` / ``taxi.box_pair_rows``, the apron cap as the index's
``cT``).  A face crossed by no stretch stays isotropic.  The round-1
corridor (short pairs within a taxiway half-width) was REFUTED by
arithmetic — any apron vertex with d(P,A) + d(P,B) < 1.5·d(A,B) re-caps
the route through its 1 % chords — and is deleted.  Counted in
``STATS[...]["route_box"]``.  The v2 verify (``verify/within.py::
taxi_box``) and the v1 oracle (``check_grade._StretchBox``) read the
same population (lockstep twin, ``tests/auto_patch_v2/test_v2routecap``).

Lattice / membrane (``emit.chords.apron_interior_spacing_m``): the M1 map
has no interior vertices (M0 open question 3); the membrane family is
therefore vacuous on v2's own publication — recorded in the M2 report,
nothing minted here.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import is_rigid_role, role_cap, snap_margin_m
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.frame import rotated_rectangle
from ..model.planar import PlanarMap
from .geometry import chords_covered, face_cover, principal_axis, project_to_chain
from .precedence import View, view
from .stretches import AxisIndex, crossing_axes, stretches
from .taxi import box_pair_rows

__all__ = ["apron_within_shape", "apron_edge_portions", "shared_apron_runs",
           "face_width", "STATS", "ROUTE_BOX_RULING"]

#: The route box row's citation (module docstring): it STATES the apron's
#: law (``solve.relax.stated_role`` reads the ``common.roles.apron``
#: prefix — apron tier, relaxable under 04t-1 like the isotropic row it
#: replaces); ``solve.why`` keys the ``apron_route_box`` family on
#: "route box".
ROUTE_BOX_RULING = ("common.roles.apron route box in a crossed face: "
                    "|dz| <= cL_stretch*|ds| + cA*|dt| vs the nearest crossing "
                    "stretch (2026-09-06v)")

#: The last run's generator statistics by generator function name
#: (``generate`` publishes them as ``<generator>.<stat>``):
#: ``chords_outside_face`` — chords dropped for leaving their face (05ae-1).
STATS: dict[str, dict[str, int]] = {}

GEN = "apron"
#: The edge-portion rows' generator: they bind a NON-apron face's rim
#: and belong to that face's tier (the vertex rule), so they carry their
#: own name — a demotion of the apron tier never reads them as apron rows.
GEN_EDGE = "apron_edge_portion"


def apron_within_shape(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """Ring edges and spine chords at the apron cap; body chords within
    the body gate at the interior fan cap."""
    vw = view(planar, law)
    cap = role_cap(law, "apron")
    if cap is None:
        return []
    fan = law.tables.common.apron_fan_ramp_max
    gate = law.tables.emit.within_shape.apron_body_chord_max_m
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    strict = set(vw.spine)
    for fid, f in planar.faces.items():
        if f.role in rigid:
            strict.update(vw.rings[fid])
            for h in vw.holes[fid]:
                strict.update(h)
    # the census reads spine membership by PROXIMITY to the published axis
    # polylines (the weld tolerance): an apron vertex lying ON a taxi
    # centreline chord between two axis vertices is a spine node there
    # even when the noding left it off the breakline chain
    chains = [[vw.xy[v] for v in ch] for bid, ch in vw.chains.items()
              if planar.breaklines[bid].kind == "taxi_centerline" and len(ch) >= 2]
    for f in vw.faces_of_role(("apron",)):
        for v in vw.rings[f.id]:
            if v in strict:
                continue
            for ch in chains:
                if project_to_chain(vw.xy[v], ch)[0] <= min_d:
                    strict.add(v)
                    break
    tol = snap_margin_m(law)
    st = stretches(planar, law)
    cell = law.tables.emit.within_shape.withdrawn_chord_min_m
    rows: list[Row] = []
    outside = 0
    for f in vw.faces_of_role(("apron",)):
        # THE CROSSED FACE (06v): its crossing stretches as one axis
        # index with the APRON cap across; every priced pair below is
        # the box against the nearest of them
        src_box = Source(GEN, ROUTE_BOX_RULING, (f"face:{f.id}", f.ref))
        rings = [vw.rings[f.id], *vw.holes[f.id]]
        axes = crossing_axes(vw.xy, rings,
                             [(st.items[sid].vertices, st.items[sid].cap_l, cap.longitudinal)
                              for sid in st.face_stretches.get(f.id, ())])
        index = AxisIndex(axes, cell) if axes else None

        def priced(a: int, b: int, d: float, src: Source) -> Row:
            if index is None:
                return Diff(a, b, cap.longitudinal, d, src)
            return box_pair_rows(vw, index, [(a, b, d)], src_box)[0]
        src_ring = Source(GEN, "common.roles.apron ring edge (2026-08-21b)",
                          (f"face:{f.id}", f.ref))
        src_spine = Source(GEN, "common.roles.apron frontage chord (2026-08-21c)",
                           (f"face:{f.id}", f.ref))
        src_body = Source(GEN, "apron body chord, strict (2026-08-24 amends 08-21c)",
                          (f"face:{f.id}", f.ref))
        # THE CHORDS (never the ring edges) must stay inside the face (05ae-1)
        chords: list[Row] = []
        for ring in rings:
            n = len(ring)
            for i in range(n):
                a = ring[i]
                a_strict = a in strict
                for j in range(i + 1, n):
                    b = ring[j]
                    d = vw.dist(a, b)
                    if d < min_d:
                        continue
                    adjacent = (j == i + 1) or (i == 0 and j == n - 1)
                    if adjacent:
                        rows.append(priced(a, b, d, src_ring))
                    elif a_strict or b in strict:
                        chords.append(priced(a, b, d, src_spine))
                    elif d <= gate + min_d:
                        # the body gate is read in the CENSUS'S OWN frame
                        # (equirectangular, ~0.2 % off this one at CYXY's
                        # latitude): inflated by the identity spacing, as
                        # the strip footprints are — measured CYXY way 88
                        # (lane v2fix288): a 60.10 m body chord here read
                        # 59.97 m there and was the one v2-verify row
                        # THE 5 % CLASS IS ONLY THE BACK-EDGE ZONES BETWEEN
                        # BUILDINGS (owner 2026-08-24, amends 08-21c): v2
                        # models no fan-ramp zone yet, so every body chord
                        # inside the gate holds the STRICT cap; ``fan`` is
                        # the back-edge zones' cap when M3b generates them
                        chords.append(priced(a, b, d, src_body))
        if not chords:
            continue
        cover = face_cover(vw.face_ring_xy(f.id),
                           [[vw.xy[v] for v in h] for h in vw.holes[f.id]], tol)
        inside = chords_covered(cover, [(vw.xy[c.a], vw.xy[c.b]) for c in chords])
        for c, ok in zip(chords, inside):
            if ok:
                rows.append(c)
            else:
                outside += 1
    boxed = sum(1 for r in rows if r.source.ruling == ROUTE_BOX_RULING)
    STATS["apron_within_shape"] = {"chords_outside_face": outside, "route_box": boxed}
    return rows


def face_width(xy: list[tuple[float, float]]) -> float:
    """The face's WIDTH: the short side of its minimum rotated rectangle
    (``shapely.minimum_rotated_rectangle``); a degenerate ring reads 0."""
    if len(xy) < 3:
        return 0.0
    from shapely.geometry import Polygon
    poly = Polygon(xy)
    if poly.area < 1e-6:                    # collinear / degenerate: no width
        return 0.0
    try:
        rect = rotated_rectangle(poly)
    except Exception:                       # a self-touching ring: fall back
        ax = principal_axis(xy)
        return 0.0 if ax is None else float(ax[2])
    pts = list(rect.exterior.coords)
    if len(pts) < 4:
        return 0.0
    import math as _m
    sides = [_m.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
             for k in range(len(pts) - 1)]
    return float(min(s for s in sides if s > 0.0) if any(s > 0.0 for s in sides) else 0.0)


def shared_apron_runs(vw: View, fid: int, apron_v: frozenset[int],
                      ratio: float) -> list[list[int]]:
    """The LONG shared runs of face ``fid`` with the aprons: maximal
    contiguous ring runs whose every edge has both ends on an apron ring
    (the edge IS shared — same vertex ids in the planar map), kept when
    the run's length >= ``ratio`` × the face's width.  A closed run (the
    whole ring) is one run."""
    ring = vw.rings[fid]
    n = len(ring)
    if n < 2:
        return []
    width = face_width(vw.face_ring_xy(fid))
    shared_edge = [ring[i] in apron_v and ring[(i + 1) % n] in apron_v for i in range(n)]
    if all(shared_edge):
        total = sum(vw.dist(ring[i], ring[(i + 1) % n]) for i in range(n))
        return [list(ring)] if total >= ratio * width else []
    # rotate so the ring starts on a non-shared edge, then walk the runs
    start = next(i for i in range(n) if not shared_edge[i])
    runs: list[list[int]] = []
    cur: list[int] = []
    for k in range(1, n + 1):
        i = (start + k) % n
        if shared_edge[i]:
            if not cur:
                cur = [ring[i]]
            cur.append(ring[(i + 1) % n])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    out: list[list[int]] = []
    for run in runs:
        length = sum(vw.dist(a, b) for a, b in zip(run, run[1:]))
        if length >= ratio * width:
            out.append(run)
    return out


def apron_edge_portions(planar: PlanarMap, law: Law, airport: Airport
                        ) -> list[Row]:
    """Every pair inside a LONG shared apron run of a governed non-apron,
    non-rigid face at the apron's cap (module docstring)."""
    vw = view(planar, law)
    cap = role_cap(law, "apron")
    if cap is None:
        return []
    ratio = law.tables.emit.within_shape.apron_edge_portion_min_width_ratio
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    apron_v: set[int] = set()
    for f in vw.faces_of_role(("apron",)):
        apron_v.update(vw.rings[f.id])
        for h in vw.holes[f.id]:
            apron_v.update(h)
    apron_fv = frozenset(apron_v)
    rows: list[Row] = []
    for fid, f in planar.faces.items():
        if f.role == "apron" or vw.caps[fid] is None or is_rigid_role(law, f.role):
            continue
        if vw.caps[fid][0] <= cap.longitudinal:
            continue                        # already at or under the apron cap
        runs = shared_apron_runs(vw, fid, apron_fv, ratio)
        if not runs:
            continue
        src = Source(GEN_EDGE, "common.roles.apron on the shared edge portion (04t-2)",
                     (f"face:{fid}", f.ref))
        for run in runs:
            for i in range(len(run)):
                for j in range(i + 1, len(run)):
                    a, b = run[i], run[j]
                    d = vw.dist(a, b)
                    if d >= min_d:
                        rows.append(Diff(a, b, cap.longitudinal, d, src))
    return rows
