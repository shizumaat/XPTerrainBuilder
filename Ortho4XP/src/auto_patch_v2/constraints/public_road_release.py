"""THE PUBLIC ROAD'S ROWS YIELD TO ITS TERRAIN (owner RULINGS 2026-10-22h,
Q111; issue #1254) — the last assembly post-pass.

A public road's target (``PlanarMap.road_ramp_z``) follows the terrain
wherever the terrain is steeper than the road cap (the floor is the core's
clamp at ``road_inside_cap``, ``airport/public_road``).  Every row the law
set prices at the cap would still hold it there — MEASURED at LGAV
(``--why-at`` on residential way -1190, 37.95118, 23.98655): the road sat
4.49 m under its DEM, held by ``road_within_shape`` (+4.48 m at 10 %) and
``pavement_road_cap`` (+2.02 m at 10 %) off the ramp's ceiling band.

THE RULE.  On the faces ``PlanarMap.public_road_lifted`` names (a public
road whose own target runs over the cap), every GRADE row (a ``Diff``)
between two RELEASED vertices is widened to the target's own difference
over the pair (x ``1 + RELEASE_SLACK``) — whichever generator minted it
(within-shape, the pavement ceiling's twin, the fallback cap).  A row is
never tightened.  A released vertex is a vertex of such a face that is

* not §20b stage 1's (airside is king: an airside vertex's rows are the
  airside's, and a road row welded to it stays one-way at its own cap);
* not a band kerb (``PlanarMap.band_kerb_vertices``: the zone band's rows
  lead there);
* touched by no other pavement face (the free-road ruling: a vertex an
  apron, lot or service road also carries is that pavement's).

THE CROSS-SECTION IS NOT RELEASED (RULINGS 2026-08-25g "roads are
laterally flat"; the 13e precedent, ``pad_road_reach.pad_grade_release``):
the ruling gives the road its terrain's grade ALONG it, never across it.
MEASURED (LGAV, same capture): widening the ``road_cross_section`` rows too
tilted 42 junction sections up to 2.27 m over 4.7 m (-1276 | -1190 at
37.95121, 23.98649), where two routes' targets meet on one face.  The
cross-fall rows (``road_cross_section``, and every ``Linear`` hop) keep
their 2 %; the longitudinal rows yield.

THE ROAD ON STEEP GROUND (owner RULINGS 2026-11-17, #2122: "Raise our road
grade limit to 20%"): on the faces ``PlanarMap.steep_road_lifted`` names (a
non-public mapped road whose own target runs over the road cap,
``airport/public_road.steep_road_lifts``), every longitudinal grade row
between two released vertices (the same three exclusions, against that
map) RISES TO THE FACE'S CAP — ``tables.road_terrain_cap`` — not to the
target's own difference: a road
the terrace holds at a pavement's level below its ground climbs back to it
at up to that cap (:func:`steep_release`).  A row is never tightened and
the cross-fall rows keep their 2 %.

WHAT ELSE HELD A RELEASED ROAD (#2284; MEASURED TNCS, public way -12
climbing the hill west of the runway, 17.644359, -63.224090, on the 0.5 m
lidar: 10-32 m under its own target with every released pair widened).
Four row kinds the two-released-vertices test never reached, each now
released by the same rule (target difference, never under the steep cap,
never tightened):

* the pairs from a MOUTH -- a vertex the road shares with the lot or road
  it leaves (:func:`_release_sets`); a mouth carries no target and is
  read at its DEM;
* §37 (10) (1)'s CONTACT rows off that lot (:func:`_is_contact`);
* the LONGITUDINAL PART of a cross-section diagonal on one route
  (:func:`_section_run`) -- the cross-fall part stays;
* the cross-section pairs between TWO ROUTES of one road -- a driveway's
  kerb on the road's own ribbon -- capped at the steep cap x the pair
  (:func:`_capped_widened`).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import airside_stage_roles, family, pavement_roles, road_terrain_cap, role_cap
from ..model.constraints import Diff, Linear, Row
from ..model.planar import PlanarMap, face_vertex_set
from .roads import stage_one_vertices

__all__ = ["terrain_release", "steep_release", "steep_vertex_caps", "contact_cap", "GEN",
           "STEEP_GEN",
           "RELEASE_SLACK", "TRANSVERSE_HEAD"]

GEN = "public_road_release"
STEEP_GEN = "steep_road_release"
#: the cross-fall rows' ruling head (``constraints/roads.road_within_shape``'s
#: ``src_t``), which the release never touches
TRANSVERSE_HEAD = "road_cross_section"
#: the contact rows' ruling head (``constraints/road_ramp.CONTACT_RULING``;
#: that module imports this one, so the head is matched as a prefix)
CONTACT_HEAD = "roads.groundside_road airside contact"
#: the widened bound stands this far (relative) over the target's own
#: difference, so the target is strictly inside it
RELEASE_SLACK = 1e-3


def released_vertices(planar: PlanarMap, law: Law,
                      lifted: _t.Mapping[int, float] | None = None) -> frozenset[int]:
    """The vertices whose rows yield on the ``lifted`` faces (default the
    public road's, ``PlanarMap.public_road_lifted``; module docstring)."""
    return _release_sets(planar, law, lifted)[0]


def _release_sets(planar: PlanarMap, law: Law,
                  lifted: _t.Mapping[int, float] | None = None
                  ) -> tuple[frozenset[int], frozenset[int]]:
    """``(released, mouths)`` on the ``lifted`` faces.  A MOUTH is a
    vertex of the road, not airside, that another pavement (a lot, a pad,
    a service road it leaves) shares or a zone band's rows lead to (a band
    kerb): those rows hold it, and the road's rows from it to its released
    vertices yield (#2284, :func:`_yields`; MEASURED TFFJ hill road 2
    ``small_roads:-26``, 17.904295, -62.847988: held 2.4 m under its ground
    by the pairs from the band kerb it leaves the strip road at).  A mouth need
    carry no target (the ramp publishes none on a vertex another
    pavement owns): :func:`terrain_release` reads it at its DEM."""
    if lifted is None:
        lifted = getattr(planar, "public_road_lifted", None) or {}
    targets = getattr(planar, "road_ramp_z", None) or {}
    if not lifted or not targets:
        return frozenset(), frozenset()
    vs: set[int] = set()
    for fid in lifted:
        if fid in planar.faces:
            vs |= face_vertex_set(planar, planar.faces[fid])
    vs -= stage_one_vertices(planar, law)
    shared: set[int] = vs & planar.band_kerb_vertices(airside_stage_roles(law))
    pav = set(pavement_roles(law))
    for f in planar.faces.values():
        if f.id not in lifted and f.role in pav:
            shared |= vs & face_vertex_set(planar, f)
    rel = frozenset(v for v in vs - shared if v in targets)
    return rel, frozenset(shared)


def _yields(row: Row, rel: _t.AbstractSet[int], mouths: _t.AbstractSet[int]) -> bool:
    """A LONGITUDINAL grade row the release widens: between two released
    vertices, or between a released vertex and a MOUTH (#2284: MEASURED
    TNCS, public way -12 climbing the hill off lot ``parking_lot#116`` --
    the all-pairs rows from the lot's corner, at the 10 % cap times the
    route distance, held the released road up to 32 m under its own
    target while every released pair beside them had yielded).  Never a
    row between two mouths: that pair is the pavements' own."""
    if not isinstance(row, Diff) or row.d <= 0.0 \
            or str(row.source.ruling).startswith(TRANSVERSE_HEAD):
        return False
    a, b = row.a in rel, row.b in rel
    return (a and b) or (a and row.b in mouths) or (b and row.a in mouths)


def steep_vertex_caps(planar: PlanarMap, law: Law) -> dict[int, float]:
    """Released vertex -> the highest steep-ground cap of the lifted faces
    it stands on (``PlanarMap.steep_road_lifted``); empty where no road
    stands on ground steeper than the road cap."""
    caps, mouths = _steep_caps(planar, law)
    return {v: g for v, g in caps.items() if v not in mouths}


def _steep_caps(planar: PlanarMap, law: Law
                ) -> tuple[dict[int, float], frozenset[int]]:
    """``(released vertex -> cap, mouths)`` of the steep-ground faces."""
    lifted = getattr(planar, "steep_road_lifted", None) or {}
    rel, mouths = _release_sets(planar, law, lifted)
    out: dict[int, float] = {}
    for fid, g in lifted.items():
        if fid in planar.faces:
            for v in face_vertex_set(planar, planar.faces[fid]) & (rel | mouths):
                out[v] = max(out.get(v, 0.0), float(g))
    return out, mouths


def terrain_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                    ) -> tuple[list[Row], int]:
    """``(rows, widened)``: ``rows`` with every longitudinal grade row
    between two released vertices -- or a released vertex and a mouth --
    widened to the target's own difference, and never under the
    steep-ground cap (``tables.road_terrain_cap``, the cap
    :func:`steep_release` gives every other road on this ground: #2284,
    MEASURED TNCS, rows at the bare target difference carried each mouth's
    residual up the whole climb, -2.4 m median under the target, -1.5 m
    with the floor); the contact rows and the cross-section's
    longitudinal part likewise (:func:`_is_contact`,
    :func:`_section_run`, :func:`_capped_widened`)."""
    rel, mouths = _release_sets(planar, law)
    if not rel:
        return list(rows), 0
    t = planar.road_ramp_z
    frame = getattr(planar, "road_route_frame", None) or {}

    def level(v: int) -> float:
        # a mouth without a target stands at its ground (the lot it
        # belongs to is held there by its own rows)
        return t[v] if v in t else float(planar.vertices[v].dem_z)

    k = 1.0 + RELEASE_SLACK
    steep = road_terrain_cap(law)
    out: list[Row] = []
    n = 0
    for row in rows:
        if _yields(row, rel, mouths):
            need = max(abs(level(row.a) - level(row.b)) * k / row.d, steep)
            if need > row.cap:
                ceil = row.ceiling if row.ceiling is None else max(row.ceiling, need)
                row = _dc.replace(row, cap=need, ceiling=ceil)
                n += 1
        elif _is_contact(row, rel):
            # the contact pair, read off the target: the road's own level
            # over the contact edge's
            need = k * sum(c * level(v) for v, c in row.terms)
            got = _widened(row, need)
            if got is not row:
                row = got
                n += 1
        elif _released_pair(row, rel):
            dt = abs(t[row.a] - t[row.b]) * k
            ds = _section_run(row, frame)
            if ds is not None:
                got = _section_widened(row, planar, law, ds, dt)
            else:
                # across two routes (a side way's kerb on the road's own):
                # the target's difference, never past the steep cap
                got = _capped_widened(row, min(dt, steep * row.d))
            if got is not row:
                row = got
                n += 1
        out.append(row)
    return out, n


def _released_pair(row: Row, rel: _t.AbstractSet[int]) -> bool:
    """A cross-section grade row between two released vertices."""
    return isinstance(row, Diff) and row.d > 0.0 and row.a in rel and row.b in rel \
        and str(row.source.ruling).startswith(TRANSVERSE_HEAD)


def _capped_widened(row: Diff, bound: float) -> Diff:
    """``row`` widened to ``bound`` metres; never tightened.

    #2284: TWO ROUTES ON ONE ROAD.  A side way's kerb vertices on the
    road's own ribbon take the side way's route frame (the nearer way
    answers them), so a ring edge along the road between them and the
    road's own vertices is priced as a CROSS-SECTION at the 2 % cap
    (``roads.road_pair_reading``'s one-ribbon and ring-edge readings).
    MEASURED TNCS public way -12: at each of its nine driveway mouths the
    climb was held level over 5-12 m (2 % x 11.7 m = 0.23 m against a
    target step of 1.8 m) and the coverage-edge pins there yielded by up to
    16 m.  The two targets are each their own route's floor, so the pair
    widens to their difference -- capped at the steep-ground cap x the
    pair (2026-11-17, #2122), the most a road on this ground is ever
    graded at, so two routes' floors never tilt a section past it (the
    2026-10-22h LGAV junction tilt, 2.27 m over 4.7 m, stays out)."""
    if bound <= row.cap * row.d:
        return row
    new = bound / row.d
    ceil = row.ceiling if row.ceiling is None else max(row.ceiling, new)
    return _dc.replace(row, cap=new, ceiling=ceil)


def _section_run(row: Diff, frame: _t.Mapping[int, tuple]) -> float | None:
    """The ROUTE run ``|Δs|`` of a cross-section row between two vertices
    of ONE route (``PlanarMap.road_route_frame``), else ``None``.

    #2284: a cross-section pair is a DIAGONAL of the road's box
    (``roads.road_pair_reading``: ``cap_l·|Δs| + cap_t·|Δt|``), so its
    longitudinal part still read the road cap where the road had yielded
    -- MEASURED TNCS public way -12: the climb walked up its ribbon on
    those diagonals at 6-8 % over 9-10 m, 16 m under its target at the
    top with every longitudinal pair released.  On one route the target is
    a function of the station alone (§37 (8)), so its difference over the
    pair IS the longitudinal part; the cross-fall ``cap_t·|Δt|`` stays."""
    fa, fb = frame.get(row.a), frame.get(row.b)
    if fa is None or fb is None or fa[0] != fb[0]:
        return None
    return abs(float(fa[1]) - float(fb[1]))


def _section_widened(row: Diff, planar: PlanarMap, law: Law, ds: float,
                     need_l: float) -> Diff:
    """``row`` with its longitudinal part ``cap_l·ds`` raised to ``need_l``
    (the face's own role cap, named in the row's inputs); never tightened."""
    fid = next((int(x[5:]) for x in row.source.inputs
                if isinstance(x, str) and x.startswith("face:")), None)
    face = planar.faces.get(fid) if fid is not None else None
    cap = role_cap(law, face.role) if face is not None else None
    if cap is None:
        return row
    extra = need_l - cap.longitudinal * ds
    if extra <= 0.0:
        return row
    new = (row.cap * row.d + extra) / row.d
    ceil = row.ceiling if row.ceiling is None else max(row.ceiling, new)
    return _dc.replace(row, cap=new, ceiling=ceil)


def _is_contact(row: Row, rel: _t.AbstractSet[int]) -> bool:
    """§37 (10) (1)'s contact row (``road_ramp.road_contact_rows``) on a
    released road vertex (its first term): the road stands within the
    road cap x route of the contact edge's level.  #2284: MEASURED TNCS
    (public way -12 off lot ``dsf:pol7#beyond1``), with the pairs released
    this row alone held the climb 7 m under its target at 10 % x route."""
    return isinstance(row, Linear) and bool(row.terms) and row.terms[0][0] in rel \
        and str(row.source.ruling).startswith(CONTACT_HEAD)


def _widened(row: Linear, need: float) -> Linear:
    """``row`` with its bound on ``need``'s side widened to reach it; never
    tightened."""
    if need > 0.0 and row.hi is not None and need > row.hi:
        return _dc.replace(row, hi=need)
    if need < 0.0 and row.lo is not None and need < row.lo:
        return _dc.replace(row, lo=need)
    return row


def steep_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                  ) -> tuple[list[Row], int]:
    """``(rows, raised)``: ``rows`` with every longitudinal grade row between
    two vertices of :func:`steep_vertex_caps` raised to the lower of their
    two caps (2026-11-17, module docstring)."""
    caps, mouths = _steep_caps(planar, law)
    if not caps:
        return list(rows), 0
    rel = caps.keys() - mouths
    out: list[Row] = []
    n = 0
    base = contact_cap(law)
    frame = getattr(planar, "road_route_frame", None) or {}
    for row in rows:
        if _yields(row, rel, mouths) and row.a in caps and row.b in caps:
            need = min(caps[row.a], caps[row.b])
            if need > row.cap:
                ceil = row.ceiling if row.ceiling is None else max(row.ceiling, need)
                row = _dc.replace(row, cap=need, ceiling=ceil)
                n += 1
        elif base and _is_contact(row, rel):
            # the contact pair rises to the steep cap x the same route
            g = caps[row.terms[0][0]] / base
            got = _widened(row, (row.hi or 0.0) * g)
            got = _widened(got, (row.lo or 0.0) * g)
            if got is not row:
                row = got
                n += 1
        elif _released_pair(row, rel):
            ds = _section_run(row, frame)
            if ds is not None:
                got = _section_widened(row, planar, law, ds,
                                       min(caps[row.a], caps[row.b]) * ds)
                if got is not row:
                    row = got
                    n += 1
        out.append(row)
    return out, n


def contact_cap(law: Law) -> float | None:
    """THE ROAD CAP THE CONTACT ROWS ARE MINTED AT -- the strictest of the
    road family's longitudinal caps; ONE site, read by
    ``road_ramp.road_contact_rows`` and :func:`steep_release`."""
    caps = [role_cap(law, r).longitudinal for r in family(law, "road_cross_section").roles
            if role_cap(law, r)]
    return min(caps) if caps else None
