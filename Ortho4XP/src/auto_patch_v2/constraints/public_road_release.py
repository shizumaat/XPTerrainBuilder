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
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import airside_stage_roles, pavement_roles
from ..model.constraints import Diff, Row
from ..model.planar import PlanarMap, face_vertex_set
from .roads import stage_one_vertices

__all__ = ["terrain_release", "steep_release", "steep_vertex_caps", "GEN", "STEEP_GEN",
           "RELEASE_SLACK", "TRANSVERSE_HEAD"]

GEN = "public_road_release"
STEEP_GEN = "steep_road_release"
#: the cross-fall rows' ruling head (``constraints/roads.road_within_shape``'s
#: ``src_t``), which the release never touches
TRANSVERSE_HEAD = "road_cross_section"
#: the widened bound stands this far (relative) over the target's own
#: difference, so the target is strictly inside it
RELEASE_SLACK = 1e-3


def released_vertices(planar: PlanarMap, law: Law,
                      lifted: _t.Mapping[int, float] | None = None) -> frozenset[int]:
    """The vertices whose rows yield on the ``lifted`` faces (default the
    public road's, ``PlanarMap.public_road_lifted``; module docstring)."""
    if lifted is None:
        lifted = getattr(planar, "public_road_lifted", None) or {}
    targets = getattr(planar, "road_ramp_z", None) or {}
    if not lifted or not targets:
        return frozenset()
    vs: set[int] = set()
    for fid in lifted:
        if fid in planar.faces:
            vs |= face_vertex_set(planar, planar.faces[fid])
    pav = set(pavement_roles(law))
    for f in planar.faces.values():
        if f.id not in lifted and f.role in pav:
            vs -= face_vertex_set(planar, f)
    vs -= stage_one_vertices(planar, law)
    vs -= planar.band_kerb_vertices(airside_stage_roles(law))
    return frozenset(v for v in vs if v in targets)


def steep_vertex_caps(planar: PlanarMap, law: Law) -> dict[int, float]:
    """Released vertex -> the highest steep-ground cap of the lifted faces
    it stands on (``PlanarMap.steep_road_lifted``); empty where no road
    stands on ground steeper than the road cap."""
    lifted = getattr(planar, "steep_road_lifted", None) or {}
    rel = released_vertices(planar, law, lifted)
    out: dict[int, float] = {}
    for fid, g in lifted.items():
        if fid in planar.faces:
            for v in face_vertex_set(planar, planar.faces[fid]) & rel:
                out[v] = max(out.get(v, 0.0), float(g))
    return out


def terrain_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                    ) -> tuple[list[Row], int]:
    """``(rows, widened)``: ``rows`` with every longitudinal grade row
    between two released vertices widened to the target's own difference."""
    rel = released_vertices(planar, law)
    if not rel:
        return list(rows), 0
    t = planar.road_ramp_z
    k = 1.0 + RELEASE_SLACK
    out: list[Row] = []
    n = 0
    for row in rows:
        if isinstance(row, Diff) and row.a in rel and row.b in rel and row.d > 0.0 \
                and not str(row.source.ruling).startswith(TRANSVERSE_HEAD):
            need = abs(t[row.a] - t[row.b]) * k / row.d
            if need > row.cap:
                ceil = row.ceiling if row.ceiling is None else max(row.ceiling, need)
                row = _dc.replace(row, cap=need, ceiling=ceil)
                n += 1
        out.append(row)
    return out, n


def steep_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                  ) -> tuple[list[Row], int]:
    """``(rows, raised)``: ``rows`` with every longitudinal grade row between
    two vertices of :func:`steep_vertex_caps` raised to the lower of their
    two caps (2026-11-17, module docstring)."""
    caps = steep_vertex_caps(planar, law)
    if not caps:
        return list(rows), 0
    out: list[Row] = []
    n = 0
    for row in rows:
        if isinstance(row, Diff) and row.a in caps and row.b in caps and row.d > 0.0 \
                and not str(row.source.ruling).startswith(TRANSVERSE_HEAD):
            need = min(caps[row.a], caps[row.b])
            if need > row.cap:
                ceil = row.ceiling if row.ceiling is None else max(row.ceiling, need)
                row = _dc.replace(row, cap=need, ceiling=ceil)
                n += 1
        out.append(row)
    return out, n
