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

THE TIERED APRON LAW (owner, RULINGS 2026-09-06w; spec ``apron-route-cap``
§3 superseded): every apron row this module prices — ring edges, frontage /
spine chords, body chords under the gate and the 05ae face cover, the
04t-2 edge portions — is HARD at ``common.roles.apron max`` (1.5 % all
directions, ``role_cap``) and CARRIES the ``preferred`` tier (1 %,
``role_preferred_cap``) as a second, PREFERENCE row on the same pair:
``Diff(cap=preferred, soft="apron:<face>:<k>", ceiling=None)`` — one
escalation group PER ROW, so the solver spends grade above 1 % only on
the rows a senior law (the runway's fit, a route's 1.5 %, a pad seat)
needs, and pays for exactly the relief it uses (``solve/assemble.py``
charges ``Weights.preference["apron"] × the largest DEM-fit weight`` per
metre of relief: below the runway family's fit and smoothness, above
every other role's fit).  Two rows, not one, because the relaxation
(``solve/relax.py``) admits only HARD rows and prices a preference row
at its ceiling: the hard row is the one an IIS names and 04t(1) relaxes
above 1.5 %, the preference row (no ceiling) constrains nothing there.
:func:`apron_preference_report` reads the built surface against the
preference: per face the rows over 1 % and the max grade (the sidecar's
``apron_over_preference``, ``why``).  The 5 % back-edge class between
adjacent pads (08-24, 06w (3)) is NOT modelled yet — owed.

Lattice / membrane (``emit.chords.apron_interior_spacing_m``): the M1 map
has no interior vertices (M0 open question 3); the membrane family is
therefore vacuous on v2's own publication — recorded in the M2 report,
nothing minted here.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import is_rigid_role, role_cap, role_preferred_cap, snap_margin_m
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.frame import rotated_rectangle
from ..model.planar import PlanarMap
from .geometry import chords_covered, face_cover, principal_axis, project_to_chain
from .precedence import View, view

__all__ = ["apron_within_shape", "apron_edge_portions", "shared_apron_runs",
           "face_width", "STATS", "PREFERENCE_GROUP", "PREFERENCE_RULING",
           "tiered_rows", "preference_face"]

#: The preference rows' escalation-group prefix (``Weights.preference``
#: key; ``solve/assemble.preference_weight``): ``apron:<face>:<k>``.
PREFERENCE_GROUP = "apron"
#: The preference row's citation: it states the apron law's PREFERRED
#: tier (``solve.relax.stated_role`` reads the ``common.roles.apron``
#: prefix; the row is never admitted to the relaxation — it is soft).
PREFERENCE_RULING = "common.roles.apron preferred tier (2026-09-06w)"

#: The last run's generator statistics by generator function name
#: (``generate`` publishes them as ``<generator>.<stat>``):
#: ``chords_outside_face`` — chords dropped for leaving their face (05ae-1).
STATS: dict[str, dict[str, int]] = {}

GEN = "apron"
#: The edge-portion rows' generator: they bind a NON-apron face's rim
#: and belong to that face's tier (the vertex rule), so they carry their
#: own name — a demotion of the apron tier never reads them as apron rows.
GEN_EDGE = "apron_edge_portion"


class _Tier:
    """One face's row minter: the hard row at ``hard`` and, where the
    law states a preference, the preference row on the same pair in its
    own group ``apron:<face>:<k>``."""

    def __init__(self, fid: int, ref: str, hard: float | None, preferred: float | None,
                 generator: str = GEN) -> None:
        self.fid, self.hard, self.preferred = fid, hard, preferred
        self.k = 0
        self.generator = generator

    def rows(self, a: int, b: int, d: float, src: Source) -> tuple[Row, ...]:
        """The hard row (none when ``hard`` is ``None``: the face's own cap
        already holds it, an edge portion of a taxi face) and the
        preference row on the same pair, citing the hard row's inputs."""
        out: list[Row] = []
        if self.hard is not None:
            out.append(Diff(a, b, self.hard, d, src))
        if self.preferred is not None:
            g = f"{PREFERENCE_GROUP}:{self.fid}:{self.k}"
            self.k += 1
            out.append(Diff(a, b, self.preferred, d,
                            Source(self.generator, PREFERENCE_RULING, src.inputs),
                            soft=g, ceiling=None))
        return tuple(out)


def tiered_rows(fid: int, ref: str, hard: float | None, preferred: float | None,
                generator: str = GEN) -> _Tier:
    """A face's tiered-row minter (module docstring)."""
    return _Tier(fid, ref, hard, preferred, generator)


def preference_face(row: Row) -> int | None:
    """The face an apron PREFERENCE row belongs to (its group's second
    field), ``None`` for any other row."""
    g = getattr(row, "soft", None)
    if not g or not g.startswith(PREFERENCE_GROUP + ":"):
        return None
    try:
        return int(g.split(":", 2)[1])
    except (IndexError, ValueError):
        return None


def apron_within_shape(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """Ring edges and spine chords HARD at the apron cap (1.5 %, 06w)
    with the 1 % preference row beside each; body chords within the body
    gate likewise (the 5 % back-edge class is not modelled — owed)."""
    vw = view(planar, law)
    cap = role_cap(law, "apron")
    if cap is None:
        return []
    pref = role_preferred_cap(law, "apron")
    pref_l = None if pref is None else pref.longitudinal
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
    rows: list[Row] = []
    outside = 0
    n_pref = 0
    for f in vw.faces_of_role(("apron",)):
        tier = _Tier(f.id, f.ref, cap.longitudinal, pref_l)
        src_ring = Source(GEN, "common.roles.apron ring edge (2026-08-21b)",
                          (f"face:{f.id}", f.ref))
        src_spine = Source(GEN, "common.roles.apron frontage chord (2026-08-21c)",
                           (f"face:{f.id}", f.ref))
        src_body = Source(GEN, "apron body chord, strict (2026-08-24 amends 08-21c)",
                          (f"face:{f.id}", f.ref))
        src_long = Source(GEN, "apron body chord, stationed across the face "
                               "(2026-09-10t (2) amends 08-24)",
                          (f"face:{f.id}", f.ref))
        # THE CHORDS (never the ring edges) must stay inside the face (05ae-1)
        chords: list[tuple[Row, ...]] = []
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
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
                        rows.extend(tier.rows(a, b, d, src_ring))
                    elif a_strict or b in strict:
                        chords.append(tier.rows(a, b, d, src_spine))
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
                        chords.append(tier.rows(a, b, d, src_body))
                    else:
                        # THE GATE IS A CHORD LENGTH, NOT A COVERAGE LIMIT
                        # (owner RULINGS 2026-09-10t (2) / 10v (3)).  A pair
                        # past the gate used to get NO ROW AT ALL, so a path
                        # right across an apron body was unpriced: SPJC's
                        # terminal apron fell 4.66 m over 85.3 m — 5.46 %
                        # against a 1.5 % cap — between nodes -2440/-2477,
                        # which are 85 m apart and not ring-adjacent, and
                        # no apron grade row saw the path.  The rows are now
                        # STATIONED ACROSS THE FACE: the same apron cap over
                        # the pair's OWN distance, so every path across a
                        # body is priced.  The gate keeps its meaning as the
                        # longest chord priced in ONE row — a longer path is
                        # priced in ``ceil(d / gate)`` equal stations, which
                        # for a straight chord is exactly the same statement
                        # (cap x d) written per station, and never a weaker
                        # one.  The 05ae face cover below still applies: a
                        # chord leaving the pavement is still no path.
                        chords.append(tier.rows(a, b, d, src_long))
        n_pref += tier.k
        if not chords:
            continue
        cover = face_cover(vw.face_ring_xy(f.id),
                           [[vw.xy[v] for v in h] for h in vw.holes[f.id]], tol)
        inside = chords_covered(cover, [(vw.xy[c[0].a], vw.xy[c[0].b]) for c in chords])
        for c, ok in zip(chords, inside):
            if ok:
                rows.extend(c)
            else:
                outside += 1
                n_pref -= len(c) - 1
    STATS["apron_within_shape"] = {"chords_outside_face": outside,
                                   "preference_rows": n_pref}
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
    non-rigid face at the apron's cap (module docstring) — under the
    tiered law (06w) the HARD row only where the face's own cap is looser
    than the apron's hard cap (a road, a lot; a taxi face at 1.5 % already
    holds it), the PREFERENCE row wherever the face's cap is looser than
    the preference."""
    vw = view(planar, law)
    cap = role_cap(law, "apron")
    if cap is None:
        return []
    pref = role_preferred_cap(law, "apron")
    pref_l = None if pref is None else pref.longitudinal
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
        face_cap = vw.caps[fid][0]
        hard_here = cap.longitudinal if face_cap > cap.longitudinal else None
        pref_here = pref_l if pref_l is not None and face_cap > pref_l else None
        if hard_here is None and pref_here is None:
            continue                        # already at or under the apron's tiers
        runs = shared_apron_runs(vw, fid, apron_fv, ratio)
        if not runs:
            continue
        src = Source(GEN_EDGE, "common.roles.apron on the shared edge portion (04t-2)",
                     (f"face:{fid}", f.ref))
        tier = _Tier(fid, f.ref, hard_here, pref_here, GEN_EDGE)
        for run in runs:
            for i in range(len(run)):
                for j in range(i + 1, len(run)):
                    a, b = run[i], run[j]
                    d = vw.dist(a, b)
                    if d >= min_d:
                        rows.extend(tier.rows(a, b, d, src))
    return rows
