"""The station walk of the LATERAL-CONTIGUITY grade law — ONE instrument,
both readers.

The law itself (which cap a cross-section takes, how stations group into
segments) lives in :mod:`auto_patch.grade_law`, which is deliberately
geometry-library free.  This module is the geometric half: given a road
polygon and the pavement around it, WHERE the stations are and WHAT the
laterally-contiguous cross-section holds at each of them.

It exists as its own module because the emitter
(``groundside.apply_lateral_contiguity_law``) and the validator
(``tools/check_grade._check_lateral_contiguity``) must census the IDENTICAL
population.  Two independent walks — even from the same law — would be two
instruments describing different station sets, and the validator would flag
stations the emitter never saw (measured: SPLP way -10009 survived a walk
the emitter had made with its own axis convention).  With one walker, every
station the validator can flag is a station the emitter capped.

Frame: whatever planar metre frame the caller's polygons live in (the
builder's layout frame for the emitter, ``check_grade``'s anchor frame for
the validator).  The law is frame-independent — it reads roles and metres.
"""
from __future__ import annotations

import math
from typing import Optional

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point

from .grade_law import (ROAD_ROLES as _LAW_ROAD_ROLES,
                        lateral_contiguity_cap, long_axis_of_points)

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

__all__ = [
    "STATION_STEP_M", "PROBE_M", "GAP_TOL_M", "MIN_MEMBER_M", "ROAD_ROLES",
    "APRON_CONTACT_ROLES", "EDGE_IDENTITY_TOL_M", "airside_contact_roles",
    "long_axis", "cross_section_roles", "edge_shared_roles", "station_caps",
]

# Station spacing and cross-section probe: the SAME numbers
# ``groundside.free_road_subsegments`` / ``_svc_contiguous_width`` use,
# because this is the same measurement — one sample every 5 m, 60 m of probe
# each side.
STATION_STEP_M = 5.0
PROBE_M = 60.0
# A "real gap" for the closure.  Adjacency is a LITERAL shared boundary in
# the sliced arrangement (owner: "never proximity"), so the run breaks at
# anything wider than emitted-coordinate noise.
GAP_TOL_M = 0.05
# A cross-section class must occupy at least this much of the run to count —
# a probe grazing the corner of a neighbour is not a shared flank.  (The
# station's OWN shape always counts, whatever its width.)
MIN_MEMBER_M = 0.5
# THE ROAD FAMILY, from THE LAW (RULINGS 2026-08-25g put the road
# cross-section limit on this same set, so a second spelling here would be
# two laws over two populations).  Re-exported, not re-typed.
ROAD_ROLES = _LAW_ROAD_ROLES

# ── EDGE-SHARING CONTACT (owner RULINGS 2026-08-25b) ─────────────────────
# "A ROAD SHARING AN EDGE WITH AN APRON CONFORMS TO THE STRICTEST GRADE — IT
# BECOMES PART OF THE APRON."  This is a CONTACT term, and the walk above is
# a LATERAL one: both this module (``cross_section_roles``: "a road dying
# INTO an apron — the apron is ahead of the station, not beside it — can
# never pick the apron up") and ``groundside.free_road_subsegments`` cast a
# perpendicular probe, and ``station_caps`` deliberately never samples the
# road's END FACE.  That end connection was an EARLIER owner exclusion; the
# 2026-08-25b ruling sharpens it away, and this is the term that does it.
#
# MEASURED (HECA, patch body 27292e8e62ed, the roads round's build): 272
# road rings share at least one edge with an airside ring, 135 of them with
# an apron.  Of the 469 shared edges, 197 run PARALLEL to the road's own
# axis (lateral contact the width test priced as "road-width" because the
# whole contiguous cross-section is under 25 m) and 162 run PERPENDICULAR
# to it (the road dies INTO the apron — invisible to any lateral probe, by
# construction).  Neither class is reachable by widening a probe; the
# contact has to be asked for directly.
#
# THE APRON, not "any airside surface": the 25b ruling names the apron.
# Contact with a building pad, a runway or a taxi junction was reported by
# the attribution tool and ruled on separately — this term never widened
# itself, and this is still the 25b set.
APRON_CONTACT_ROLES = frozenset({"apron"})

# ── …AND THE RULING THAT WIDENED IT (owner RULINGS 2026-08-26b item 2,
# spec ``road-airside-crossing-conformance-spec.md`` §1.1) ───────────────
# "A service-road stretch whose cross-section stands in AIRSIDE pavement
# is a CONFORMING stretch … the non-free complement now carries
# conformance against ANY airside neighbour, not only aprons."  §0 of that
# spec names this constant as one of the two reasons no standing law fires
# at the owner's site: the road there shares its edge with taxi JUNCTIONS
# -10250 / -10257, which the 25b set does not contain.
#
# The register is ``enclaves.ENCLAVE_AIRSIDE_ROLES`` — THE canonical
# airside-pavement family, imported at call time rather than re-spelled
# here (blast.py's role-literal hazard), the same one the 2026-08-15
# proximity mouth seat indexes its carrier edges from.  Buildings and
# ``graded_strip``s stay OUT, on that seat's own measured grounds: a strip
# is the road's own grading product at the road's own level, and a
# building is a stage-B seat, not a surface a truck arrives at.
def airside_contact_roles() -> frozenset:
    """The roles a road ring CONFORMS to on edge contact.

    Read at CALL time, like :func:`_edge_conformance_on`, so a twin can
    flip the gate without reloading and both readers of the law agree
    within one process.  Gate off ⇒ exactly the 25b set, so the
    pre-ruling arm is byte-identical.
    """
    from . import config as _cfg
    if not bool(getattr(_cfg, "ROAD_AIRSIDE_CROSSING_CONFORM", True)):
        return APRON_CONTACT_ROLES
    # THE DIAGNOSTIC GATE (spec Amendment 2 §2, Fable-authorized).  The
    # widening carries NONE of this law's acceptance once values are
    # ADOPTED post-solve — and it is the last term in the arm that can
    # still reach the airside solve, through the lateral pass's cuts.
    # ``O4_ROAD_AIRSIDE_CONTACT_WIDEN=0`` measures that directly.
    if not bool(getattr(_cfg, "ROAD_AIRSIDE_CONTACT_WIDEN", True)):
        return APRON_CONTACT_ROLES
    from .enclaves import ENCLAVE_AIRSIDE_ROLES
    return frozenset(APRON_CONTACT_ROLES | ENCLAVE_AIRSIDE_ROLES)


# ── …AND THE RULING THAT SCOPED IT BACK (owner 2026-08-28e, HECA round 5
# items 2/3/4; spec ``heca-round5-drainage-and-ramps-spec.md`` LAW 2) ────
# Owner, verbatim: *"THE DEFECT IS SCOPING, NOT A MISSING CONSTANT: all
# four stretches carry ``o4_grade_law_cap 0.010000`` — classified as APRON
# SPINES … even where the owner says they have left the apron … fix the
# scoping so the stretch beyond the apron prices and solves at the 8 %
# free class."*  ``SERVICE_ROAD_MAX_GRADE`` (8 %) is that class and it
# already exists; nothing here adds or changes a law constant.
#
# WHAT WAS OVER-SCOPED.  :func:`edge_shared_roles` is RING-LEVEL by
# construction — "so every station of a contact ring reads the apron in
# its cross-section and the ring takes one cap end to end".  A road that
# merely MEETS airside pavement at an END FACE (162 of HECA's 469 shared
# edges are PERPENDICULAR to the road's own axis, this module's own
# measurement) therefore carried the apron's 1 % along its whole run, tens
# or hundreds of metres away from any apron.  Measured on this tree,
# HECA arm ``r5base``: service_road 2863 (way -12859) carries 0.010000
# over its 130 m run to taxiway junction -12711, and 2854 / 2859 the same.
#
# THE SCOPING.  Edge contact is a VALUE law, not a CAP law:
#   * the contact's VALUES stand untouched — the shared vertices ARE the
#     apron's by canonical identity (``apply_service_road_dem_follow``'s
#     exact-vertex anchors), and the apron-CONTACT DATUM seeding
#     (RULINGS 2026-08-25b clause 2(c)) still seeds the ring from those
#     anchors.  The weld is what stops the step at the contact, and the
#     weld is not touched here;
#   * the CAP is what the LATERAL walk sees.  A road running INSIDE or
#     ALONGSIDE an apron is laterally contiguous with it, so
#     :func:`cross_section_roles` reads the apron at every such station
#     and the ring still takes 1 % — the 2026-07-27 free-road ruling and
#     25b's substance are preserved exactly where they are true.  A road
#     that only TOUCHES airside at a face is a free road, and prices and
#     solves as one.
# Gate ``O4_ROAD_CONTACT_CAP_SCOPE=0`` restores the ring-wide contact
# pricing byte-identically.
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
    from . import config as _cfg
    return not bool(getattr(_cfg, "ROAD_CONTACT_CAP_SCOPE", True))


def station_cap_vector(poly, tree, polys, roles, own_index, keepout=None):
    """``[(x, y, cap), …]`` — THE per-station cap vector (Amendment 2).

    ONE DERIVATION, THREE READERS.  The cap authority lives at the
    STATION, and this is the only place it is computed: the pair pricing
    (``grade_graph.shape_constraints``), the solve's DEM-follow envelope
    (``anchors.apply_service_road_dem_follow``) and the free-road profile
    pass's cap-Lipschitz envelope all consume THIS vector, and the census
    reads the same walk.  A second per-station cap anywhere would be the
    census-wrapper defect at cap granularity.

    Stations with no verdict (off the shape, inside the runway-strip
    keepout, unmeasurable cross-section) are omitted — the caller's own
    fallback owns them, exactly as it owns a ``None`` in
    :func:`station_caps`.
    """
    stations, caps = station_caps(poly, tree, polys, roles, own_index,
                                  keepout=keepout)
    return [(float(st[0]), float(st[1]), float(c))
            for st, c in zip(stations, caps)
            if st is not None and c is not None]


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

# CANONICAL IDENTITY, NEVER PROXIMITY (the ruling's own words).  Two rings
# share an edge when they carry the SAME two consecutive vertices.  The
# tolerance here is a spelling tolerance, not a gap tolerance: it is 500×
# tighter than ``GAP_TOL_M`` (itself "emitted-coordinate noise") and 10,000×
# tighter than the 1 m near-miss horizon the ruling excludes, so no pair of
# genuinely distinct vertices can meet under it.  Both readers reach the
# same answer for a different reason: the emitter's shapes hold literally
# shared coordinates after the T-vertex weld, and the validator's rings come
# from OSM nodes that ``layout.to_osm`` already deduplicated by their
# 11-decimal spelling.
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
    from . import config as _cfg
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


def station_normal(poly):
    """The unit NORMAL of ``poly``'s long axis (the probe direction), or
    ``None`` — the direction the segment cuts are made along."""
    axis = long_axis(poly)
    if axis is None:
        return None
    (ux, uy), _length, _mid = axis
    return (-uy, ux)
