"""LATERAL CONTIGUITY, the priced lateral axes, the enclave airside roles and two ground constants.

COPIED from ``adjacent_ground.py, enclaves.py, gap_fill.py, lateral_contiguity.py, lateral_spine_nodes.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
of the stage-B brief: "the census stays engine-neutral BY IMPLEMENTATION").
`tools/check_grade.py` priced v2 patches with law machinery that lived in
modules the v1 deletion takes; what it USES is copied here ONCE, verbatim, and
the census reads it from the harness.  Values that are law live in
``auto_patch/config.py`` (KEEP) or ``auto_patch_v2/law/*.toml`` and are
IMPORTED, never re-spelled.

Do not edit to change behaviour: this is a transcription, and the acceptance
was a census A/B on the same HECA patch bytes reading IDENTICAL.
"""

from __future__ import annotations

from .grade_law import ROAD_ROLES as _LAW_ROAD_ROLES
from .grade_law import lateral_contiguity_cap
from .grade_law import long_axis_of_points
from .roles import ROLE_APRON
from .roles import ROLE_CROSS_CONNECTOR
from .roles import ROLE_JUNCTION
from .roles import ROLE_PRIMARY_PARALLEL
from .roles import ROLE_RUNWAY
from .roles import ROLE_RUNWAY_CROSSING
from .roles import ROLE_SECONDARY_PARALLEL
from .roles import ROLE_SERVICE_JUNCTION
from .roles import ROLE_SERVICE_ROAD
from .roles import ROLE_STUB
from auto_patch import config as _cfg
from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point
from typing import Optional
import auto_patch.config as _cfg


STACKED_WALL_RETREAT_M = 0.6


ENCLAVE_AIRSIDE_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_APRON,
})


_RING_ALONG_BENCH_SLOPE = 0.05


_GEOM_EXC = (ValueError, GEOSException, TopologicalError)


STATION_STEP_M = 5.0


PROBE_M = 60.0


GAP_TOL_M = 0.05


MIN_MEMBER_M = 0.5


ROAD_ROLES = _LAW_ROAD_ROLES


APRON_CONTACT_ROLES = frozenset({"apron"})


def airside_contact_roles() -> frozenset:
    """The roles a road ring CONFORMS to on edge contact.

    Read at CALL time, like :func:`_edge_conformance_on`, so a twin can
    flip the gate without reloading and both readers of the law agree
    within one process.  Gate off ⇒ exactly the 25b set, so the
    pre-ruling arm is byte-identical.
    """
    from auto_patch import config as _cfg
    if not bool(getattr(_cfg, "ROAD_AIRSIDE_CROSSING_CONFORM", True)):
        return APRON_CONTACT_ROLES
    # THE DIAGNOSTIC GATE (spec Amendment 2 §2, Fable-authorized).  The
    # widening carries NONE of this law's acceptance once values are
    # ADOPTED post-solve — and it is the last term in the arm that can
    # still reach the airside solve, through the lateral pass's cuts.
    # ``O4_ROAD_AIRSIDE_CONTACT_WIDEN=0`` measures that directly.
    if not bool(getattr(_cfg, "ROAD_AIRSIDE_CONTACT_WIDEN", True)):
        return APRON_CONTACT_ROLES
    from .contiguity import ENCLAVE_AIRSIDE_ROLES
    return frozenset(APRON_CONTACT_ROLES | ENCLAVE_AIRSIDE_ROLES)


def _contact_prices_the_cap() -> bool:
    """Does EDGE CONTACT fold into every station's cap?  **NO — ruled**
    (owner 2026-08-28, Amendment 2 clause 1): the way-level gate
    ``O4_ROAD_CONTACT_CAP_SCOPE`` DISSOLVES into the per-station vector.
    End-on contact binds VALUES (the weld, the apron-CONTACT DATUM
    seeding, the profile pass's pins) and caps nothing; LATERAL contact
    is read by ``cross_section_roles`` at the stations it actually
    touches and caps exactly those.

    Kept as a function, and still readable through the retired gate, so
    the pre-ruling arm can be reproduced for an A/B: ``O4_ROAD_CONTACT_
    CAP_SCOPE=0`` restores ring-wide contact pricing byte-identically.
    """
    from auto_patch import config as _cfg
    return not bool(getattr(_cfg, "ROAD_CONTACT_CAP_SCOPE", True))


def cap_at(vector, x, y, default=None):
    """The cap governing point ``(x, y)`` — its NEAREST station's.

    The stations are 5 m apart along the road, so nearest-station is the
    station the point stands in; asking any other way would be a second
    convention.  ``default`` when the vector is empty.
    """
    if not vector:
        return default
    best = None
    for (sx, sy, c) in vector:
        d = (sx - x) * (sx - x) + (sy - y) * (sy - y)
        if best is None or d < best[0]:
            best = (d, c)
    return best[1]


EDGE_IDENTITY_TOL_M = 1e-4


def long_axis(poly):
    """``((ux, uy), length, (mx, my))`` — the unit long axis, length and
    mid-point of ``poly``'s minimum-area rectangle, or ``None``.

    The road's own direction.  A blobby service JUNCTION has no natural
    axis; the minimum-area rectangle still gives both readers the SAME
    answer, which is what the law needs (a shared convention), and the
    cross-section is then measured across the shape's short dimension —
    exactly where a laterally-touching neighbour lies.

    THE BODY MOVED TO THE LAW (RULINGS 2026-08-25g): the road
    CROSS-SECTION classifier needs the same "which way does this road
    run" answer this walk uses, and it reaches it from the solver's bare
    ring lists where no shapely polygon exists.  ``grade_law`` — which
    this module already imports for the cap — holds the one
    implementation; this stays the shapely-shaped door onto it, so every
    caller here is unchanged.
    """
    try:
        pts = list(poly.exterior.coords)[:-1]
    except _GEOM_EXC:
        return None
    return long_axis_of_points(pts)


def cross_section_roles(px, py, nx, ny, tree, polys, roles, own_index):
    """The roles present in the laterally-contiguous paved cross-section at
    one station, or ``None`` when the station is not on pavement.

    Casts the perpendicular ``(nx, ny)`` through ``(px, py)``, cuts it
    against every pavement polygon, merges the pieces that TOUCH (gap ≤
    ``GAP_TOL_M``) into runs, and returns the role set of the run containing
    the station.  Any real gap ends the run — the owner's "genuinely unpaved
    ground" test — and the run never continues past the probe, so a road
    dying INTO an apron (the apron is ahead of the station, not beside it)
    can never pick the apron up.
    """
    cut = LineString([(px - nx * PROBE_M, py - ny * PROBE_M),
                      (px + nx * PROBE_M, py + ny * PROBE_M)])
    segs = []
    for k in tree.query(cut):
        k = int(k)
        try:
            inter = cut.intersection(polys[k])
        except _GEOM_EXC:
            continue
        if inter.is_empty:
            continue
        parts = ([inter] if inter.geom_type == "LineString"
                 else [g for g in getattr(inter, "geoms", ())
                       if g.geom_type == "LineString"])
        for g in parts:
            ts = [((x - px) * nx + (y - py) * ny) for x, y in g.coords]
            if ts:
                segs.append((min(ts), max(ts), k))
    if not segs:
        return None
    segs.sort()
    runs = []
    cur = [segs[0][0], segs[0][1], [segs[0]]]
    for s in segs[1:]:
        if s[0] <= cur[1] + GAP_TOL_M:
            cur[1] = max(cur[1], s[1])
            cur[2].append(s)
        else:
            runs.append(cur)
            cur = [s[0], s[1], [s]]
    runs.append(cur)
    for lo, hi, members in runs:
        if not (lo - GAP_TOL_M <= 0.0 <= hi + GAP_TOL_M):
            continue
        return {roles[k] for t0, t1, k in members
                if k == own_index or (t1 - t0) >= MIN_MEMBER_M}
    return None


def _edge_conformance_on() -> bool:
    """Is the 2026-08-25b edge-conformance term armed?  Default ON.

    Read at CALL time (not import) so a test — and the twin that proves the
    gate off is the pre-ruling law — can flip it without reloading the
    module, and so both readers of the law see the same answer within one
    process.
    """
    from auto_patch import config as _cfg
    return bool(getattr(_cfg, "ROAD_APRON_EDGE_CONFORMANCE", True))


def _edge_keys(poly, tol=EDGE_IDENTITY_TOL_M):
    """The ring's undirected consecutive-vertex-pair keys, or ``None``.

    A key is a ``frozenset`` of two quantised vertices — see
    :data:`EDGE_IDENTITY_TOL_M` for why quantising is identity here and not
    proximity.  Interior rings are included: a road threaded through a hole
    in an apron shares that hole's boundary and is as much "inside the
    apron" as one beside it.
    """
    q = 1.0 / tol
    out = set()
    try:
        rings = [list(poly.exterior.coords)]
        rings += [list(r.coords) for r in poly.interiors]
    except _GEOM_EXC:                                      # pragma: no cover
        return None
    for coords in rings:
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        n = len(coords)
        if n < 2:
            continue
        pts = [(round(x * q), round(y * q)) for (x, y) in coords]
        for k in range(n):
            a, b = pts[k], pts[(k + 1) % n]
            if a != b:
                out.add(frozenset((a, b)))
    return out


def edge_shared_roles(poly, tree, polys, roles, own_index,
                      only_roles=None):
    """The roles of the shapes this one SHARES AN EDGE with (2026-08-25b,
    widened to every airside neighbour by RULINGS 2026-08-26b item 2).

    The set of neighbour roles the ring holds at least one edge in common
    with, restricted to ``only_roles`` — which defaults to
    :func:`airside_contact_roles`, read at call time so the 2026-08-26b
    gate can restore the 25b apron-only set exactly.

    RING-LEVEL, deliberately.  The ruling puts *the road ring* under the
    apron's law — "it becomes part of the apron" — not the two stations
    nearest the shared edge, so every station of a contact ring reads the
    apron in its cross-section and the ring takes one cap end to end.  A
    ring priced apron at one end and road at the other is the step this
    ruling exists to remove.
    """
    if only_roles is None:
        only_roles = airside_contact_roles()
    own = _edge_keys(poly)
    if not own:
        return set()
    found = set()
    try:
        cand = tree.query(poly)
    except _GEOM_EXC:                                      # pragma: no cover
        return set()
    for k in cand:
        k = int(k)
        if k == own_index or roles[k] not in only_roles:
            continue
        keys = _edge_keys(polys[k])
        if keys and (own & keys):
            found.add(roles[k])
    return found


def station_caps(poly, tree, polys, roles, own_index, keepout=None):
    """``(stations, caps)`` for one road shape — THE census both readers run.

    ``stations[i]`` is ``(x, y)`` or ``None``; ``caps[i]`` is the station's
    lawful cap (``grade_law.lateral_contiguity_cap`` of its cross-section) or
    ``None`` where there is no verdict: off the shape, inside ``keepout``
    (the runway-strip footprint — clause 5, whose own law supersedes there),
    or an unmeasurable cross-section.

    Stations sit at interval CENTRES, never on the road's END FACE: a probe
    cast exactly along a shared end face reads the apron's whole span as
    "beside" the road, which is a different (and wrong) measurement.  The
    end connection is not thereby exempt — RULINGS 2026-08-25b puts an
    edge-sharing road under the apron's law — it is priced by
    :func:`edge_shared_roles` instead, which asks for the contact directly
    rather than trying to see it down a perpendicular probe.
    """
    axis = long_axis(poly)
    if axis is None:
        return [], []
    (ux, uy), length, mid = axis
    nx, ny = -uy, ux
    # THE CONTACT TERM (RULINGS 2026-08-25b) — one query per shape, folded
    # into every station's cross-section so the ring takes ONE cap.  Gate
    # ``O4_ROAD_APRON_EDGE_CONFORM=0`` restores the pre-ruling law exactly.
    # …AND THE SCOPING (owner 2026-08-28e): contact is a VALUE law, so it
    # no longer folds into the cap.  The lateral walk below still reads an
    # apron a road stands INSIDE or ALONGSIDE — that contiguity is what
    # 25b's substance is — while a road that only meets airside at a FACE
    # keeps its own free-road class beyond the contact.
    contact = set()
    own_role = (roles[own_index]
                if own_index is not None and 0 <= own_index < len(roles)
                else None)
    # …AND THE RULING THAT DISSOLVED THE WAY-LEVEL GATE (owner
    # 2026-08-28, round-5b spec Amendment 2 clause 1): "end-on contact
    # binds VALUES and never caps any station; lateral contact caps
    # exactly the stations it touches."  ``_contact_prices_the_cap`` is
    # therefore permanently False — the gate is gone, not flipped — and
    # the CAP now lives at ONE granularity, the STATION, in the vector
    # this walk already produces.
    if (own_role in ROAD_ROLES and _edge_conformance_on()
            and _contact_prices_the_cap()):
        contact = edge_shared_roles(poly, tree, polys, roles, own_index)
    n_st = max(1, int(length / STATION_STEP_M))
    stations = []
    caps: list[Optional[float]] = []
    for k in range(n_st):
        t = -0.5 * length + length * (k + 0.5) / n_st
        px, py = mid[0] + ux * t, mid[1] + uy * t
        pt = Point(px, py)
        try:
            inside = poly.contains(pt)
        except _GEOM_EXC:
            inside = False
        if not inside:
            stations.append(None)
            caps.append(None)
            continue
        if keepout is not None:
            try:
                if keepout.covers(pt):
                    stations.append((px, py))
                    caps.append(None)
                    continue
            except _GEOM_EXC:
                pass
        present = cross_section_roles(px, py, nx, ny, tree, polys, roles,
                                      own_index)
        if contact:
            # The contact is part of THIS cross-section's class set: the
            # apron the road shares an edge with is one surface with it.
            # A station with no measurable cross-section at all keeps its
            # ``None`` verdict — the contact term prices a station, it
            # does not manufacture one where the walk found no pavement.
            present = set(present) | contact if present else present
        stations.append((px, py))
        caps.append(lateral_contiguity_cap(present) if present else None)
    return stations, caps


_LATERAL_BODY_ROLES = frozenset({ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION})


TAXI_AXIS_PRICED_ROLES = _LATERAL_BODY_ROLES


SERVICE_AXIS_PRICED_ROLES = frozenset({ROLE_SERVICE_ROAD,
                                       ROLE_SERVICE_JUNCTION})

