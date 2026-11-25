"""THE SIDE BANKS of the core's levelled road ribbons (owner RULINGS
2026-11-18d).

``O4_Vector_Map.include_roads`` levels a banked road: its ribbon (the
centreline buffered ``lane_width`` each side) holds the clamped
centreline profile across its width, and its ring is a hard Dirichlet
set in the mesh.  The ground one vertex outside follows the DEM, so
wherever the DEM beside the road stands off the road's level -- a road
along a bluff top whose centreline zigzags across the DEM's bluff face
(owner sim read LPPD 2026-11-18T13:32Z, ribbon vertices 15 m above /
16 m below the DEM) -- the ribbon edge is a vertical wall.

THE OWNER'S RULE: the road is right and the elevation data is wrong;
the road keeps its standard grading, and the ground on EITHER side is
cut and filled to it.  "With a cliff top road there's likely some near
vertical walls filled up to support the road where it crosses gaps, or
hillside cut away to allow the road to pass a bluff."  So, per station
and per side of the road:

* a 1:2 BANK (``BANK_RUN`` m out per metre of height) from the ribbon
  edge to the natural ground, where its foot lies within
  ``BANK_MAX_WIDTH_M`` of the edge;
* otherwise a 2:1 RETAINING FACE (``FACE_RUN``) standing at the ribbon
  edge, a straight face along the road, down (fill) or up (cut) to the
  ground, again within the width cap;
* beyond the foot (and beyond the cap) the ground keeps its DEM;
* a side whose ground stands less than ``BANK_MIN_STEP_M`` outside the
  1:2 bank line is not banked.

TWO HALVES, one law.  The VECTOR STEP decides it (:func:`assign_bank_runs`):
the ground is read at the ribbon edge and every ``BANK_STEP_M`` out to
the cap, on the centreline resampled at ``lane_width`` (so the decision
follows the road between sparse OSM vertices), and each clamped station
publishes its ``[left, right]`` run and foot distance in the
``o4_levelled_roads.json`` sidecar; the banks' foot lines are drawn
into the vector map (:func:`bank_foot_lines`).  The MESH STEP draws it
(:func:`road_bank_values`): every free vertex beside a levelled road
takes the ground clipped into the band ``z_road +/- d / run`` (``d`` its
plan distance past the ribbon edge), with ``z_road``, ``run`` and the
foot interpolated along the station polyline -- one continuous surface
along the road, never a per-station step.
"""

from __future__ import annotations

import json
import os
from math import cos, pi

import numpy
import O4_File_Names as FNAMES
import O4_Vector_Utils as VECT

__all__ = ["BANK_RUN", "FACE_RUN", "BANK_MAX_WIDTH_M", "BANK_MIN_STEP_M",
           "assign_bank_runs", "bank_foot_lines", "bank_field",
           "road_bank_values", "ribbon_vertices"]

#: The bank: metres out per metre of height (1:2).
BANK_RUN = 2.0
#: The retaining face where a bank would not fit: 2:1 (0.5 m out per metre).
FACE_RUN = 0.5
#: The widest bank or face, from the ribbon edge, in metres.
BANK_MAX_WIDTH_M = 20.0
#: The plan step the ground is read at, out from the ribbon edge.
BANK_STEP_M = 1.0
#: Ground this close to the bank line counts as met (the foot).
BANK_TOL_M = 0.1
#: Past the foot the bank hands back to the DEM over this distance.
FOOT_FADE_M = 2.0
#: A road side is banked where the ground stands at least this far outside
#: the 1:2 bank line from its ribbon edge; below it the ground meets the
#: ribbon as it always has.
BANK_MIN_STEP_M = 2.0
#: Metres per degree of latitude (``O4_Mesh_Utils.BANK_METRES_PER_DEGREE``).
_M_PER_DEG = 111120.0
#: A mesh vertex this far or less outside a ribbon's edge is the ribbon's.
RIBBON_TOL_M = 0.5


def _feet(ground, z, offsets, run):
    """Per sample: ``(foot, peak)`` for the ``run`` cone from the ribbon
    edge.  The foot is the first offset where the ground is back inside
    the cone after it first left it (0 where it never leaves, ``inf``
    where it does not come back within the cap); the peak is how far the
    ground stands outside the cone before the foot."""
    g = numpy.vstack(ground)
    excess = numpy.abs(g - z[None, :]) - offsets[:, None] / run
    out = excess > BANK_TOL_M
    left = numpy.cumsum(out, axis=0) > 0
    back = numpy.vstack([numpy.zeros((1, len(z)), dtype=bool),
                         left[:-1]]) & ~out
    j = numpy.argmax(back, axis=0)
    rows = numpy.arange(len(offsets))[:, None]
    upto = numpy.where(back.any(axis=0), j, len(offsets))
    peak = numpy.where(rows < upto[None, :], excess, -numpy.inf).max(axis=0)
    foot = numpy.where(back.any(axis=0), offsets[j], numpy.inf)
    foot[~left[-1]] = 0.0
    return foot, peak


def _side_runs(ref, z_ref, k, n, alt_vec, lane_width, side):
    """``(run, foot, face)`` per station on one side of a way."""
    offsets = numpy.arange(0.0, BANK_MAX_WIDTH_M + 1e-9, BANK_STEP_M)
    ground = [numpy.asarray(alt_vec(VECT.shift_way(ref, lane_width + d, side)),
                            dtype=numpy.float64) for d in offsets]
    (f_bank, peak) = _feet(ground, z_ref, offsets, BANK_RUN)
    f_face = numpy.minimum(_feet(ground, z_ref, offsets, FACE_RUN)[0],
                           BANK_MAX_WIDTH_M)
    flat = ~(peak >= BANK_MIN_STEP_M)
    f_bank[flat] = 0.0
    f_face[flat] = 0.0
    face = numpy.zeros(n, dtype=bool)
    numpy.logical_or.at(face, k, numpy.isinf(f_bank))
    # one station of bank between two faces is part of the face: the
    # retaining face runs straight along the road, not in and out
    if n >= 3:
        face[1:-1] |= face[:-2] & face[2:]
    foot_bank = numpy.zeros(n)
    numpy.maximum.at(foot_bank, k, numpy.where(numpy.isinf(f_bank), 0.0,
                                               f_bank))
    foot_face = numpy.zeros(n)
    numpy.maximum.at(foot_face, k, f_face)
    return (numpy.where(face, FACE_RUN, BANK_RUN),
            numpy.where(face, foot_face, foot_bank), face)


def assign_bank_runs(roads, alt_vec, lane_width):
    """Decide every levelled way's side banks, in place (``w["bank_run"]``
    and ``w["bank_foot_m"]``, ``[left, right]`` per station), on its
    graded (answering) stations only (RULINGS 2026-11-18e (g)).

    Returns ``{"bank_m", "face_m"}``: the road-side length banked 1:2
    (a foot past the edge) and held by a retaining face.
    """
    report = {"bank_m": 0.0, "face_m": 0.0}
    if roads is None:
        return report
    for w in roads.ways:
        pts = numpy.asarray(w["points"], dtype=numpy.float64)
        n = len(pts)
        # OWNER RULINGS 2026-11-18e (g): banks only where the profile was
        # graded -- the answering stations of a run or a DEM-wrong window;
        # a terrain station's ribbon reads its own DEM
        graded = numpy.asarray(w.get("answers", numpy.ones(n, dtype=bool)),
                               dtype=bool)
        if n < 2 or not graded.any():
            w["bank_run"] = [[BANK_RUN] * n, [BANK_RUN] * n]
            w["bank_foot_m"] = [[0.0] * n, [0.0] * n]
            continue
        s_st = VECT.way_arclengths(pts)
        ref = numpy.asarray(VECT.refine_way(pts, lane_width),
                            dtype=numpy.float64)
        s_ref = VECT.way_arclengths(ref)
        z_ref = numpy.interp(s_ref, s_st,
                             numpy.asarray(w["alt"], dtype=numpy.float64))
        k = numpy.searchsorted((s_st[:-1] + s_st[1:]) / 2.0, s_ref)
        share = numpy.zeros(n)
        seg = numpy.diff(s_st) / 2.0
        share[:-1] += seg
        share[1:] += seg
        runs, feet = [], []
        for side in ("left", "right"):
            run, foot, face = _side_runs(ref, z_ref, k, n, alt_vec,
                                         lane_width, side)
            foot = numpy.where(graded, foot, 0.0)
            run = numpy.where(graded, run, BANK_RUN)
            face = face & graded
            runs.append(run)
            feet.append(foot)
            report["face_m"] += float(share[face & (foot > 0.0)].sum())
            report["bank_m"] += float(share[~face & (foot > 0.0)].sum())
        w["bank_run"] = runs
        w["bank_foot_m"] = feet
    return report


def bank_foot_lines(roads, lane_width):
    """The banks' FOOT LINES, tile-relative: per way side, the centreline
    resampled at ``lane_width`` and offset to the ribbon edge plus the
    foot, wherever the side is banked.  The vector step draws them as
    DUMMY constrained lines so the mesh has vertices at the foot: the bank
    is then the ruled surface between the ribbon edge and this line.
    """
    from shapely import geometry

    out = []
    for w in (roads.ways if roads is not None else ()):
        if "bank_foot_m" not in w or len(w["points"]) < 2:
            continue
        pts = numpy.asarray(w["points"], dtype=numpy.float64)
        s_st = VECT.way_arclengths(pts)
        ref = numpy.asarray(VECT.refine_way(pts, lane_width),
                            dtype=numpy.float64)
        s_ref = VECT.way_arclengths(ref)
        for side, feet in zip(("left", "right"), w["bank_foot_m"], strict=True):
            foot = numpy.interp(s_ref, s_st, numpy.asarray(feet, float))
            on = foot > 0.0
            if not on.any():
                continue
            normals = VECT.weighted_normals(ref, side)
            normals /= numpy.maximum(numpy.hypot(
                normals[:, 0] * VECT.scalx, normals[:, 1]), 1e-9)[:, None]
            line = ref + ((lane_width + foot) * VECT.GEO.m_to_lat)[:, None] \
                * normals
            edges = numpy.flatnonzero(numpy.diff(on.astype(numpy.int8)))
            for a, b in zip(numpy.r_[0, edges + 1],
                            numpy.r_[edges + 1, len(on)], strict=True):
                if on[a] and b - a >= 2:
                    out.append(geometry.LineString(line[a:b]))
    return geometry.MultiLineString(out)


def _segments(payload, tile_lat, tile_lon, scalx):
    """The sidecar's banked station polylines as per-segment arrays in a
    metric tile frame: ``(a, b, z, run_l, run_r, foot_l, foot_r)``, the
    endpoints ``(S, 2)`` and every per-end value ``(S, 2)`` too."""
    a, b, z, rl, rr, fl, fr = [], [], [], [], [], [], []
    for way in payload.get("ways", ()):
        runs, feet = way.get("bank_run"), way.get("bank_foot_m")
        lats, lons, alt = way.get("lat"), way.get("lon"), way.get("alt")
        if not runs or not feet or not lats or len(lats) < 2:
            continue
        p = numpy.column_stack([
            (numpy.asarray(lons) - tile_lon) * scalx * _M_PER_DEG,
            (numpy.asarray(lats) - tile_lat) * _M_PER_DEG])
        a.append(p[:-1])
        b.append(p[1:])
        for out, v in ((z, alt), (rl, runs[0]), (rr, runs[1]),
                       (fl, feet[0]), (fr, feet[1])):
            v = numpy.asarray(v, dtype=numpy.float64)
            out.append(numpy.column_stack([v[:-1], v[1:]]))
    if not a:
        return None
    return tuple(numpy.vstack(x) for x in (a, b, z, rl, rr, fl, fr))


def bank_field(payload, tile_lat, tile_lon, xy, zv):
    """The banked altitude of free points ``xy`` (tile-relative degrees)
    whose ground is ``zv``: ``(index, z)`` of the points the banks move."""
    import shapely

    scalx = cos((tile_lat + 0.5) * pi / 180.0)
    segs = _segments(payload, tile_lat, tile_lon, scalx)
    empty = (numpy.zeros(0, dtype=numpy.int64), numpy.zeros(0))
    if segs is None or not len(xy):
        return empty
    (a, b, z, rl, rr, fl, fr) = segs
    lane = float(payload.get("lane_width_m", 0.0))
    reach = lane + BANK_MAX_WIDTH_M + FOOT_FADE_M
    p = numpy.column_stack([xy[:, 0] * scalx * _M_PER_DEG,
                            xy[:, 1] * _M_PER_DEG])
    tree = shapely.STRtree(shapely.linestrings(numpy.stack([a, b], axis=1)))
    (pi_, si) = tree.query_nearest(shapely.points(p), max_distance=reach,
                                   all_matches=False)
    if not len(pi_):
        return empty
    ab = b[si] - a[si]
    ap = p[pi_] - a[si]
    l2 = numpy.maximum((ab ** 2).sum(axis=1), 1e-12)
    t = numpy.clip((ap * ab).sum(axis=1) / l2, 0.0, 1.0)
    off = ap - t[:, None] * ab
    dist = numpy.hypot(off[:, 0], off[:, 1])
    left = (ab[:, 0] * ap[:, 1] - ab[:, 1] * ap[:, 0]) > 0.0

    def lerp(v):
        return v[si, 0] + t * (v[si, 1] - v[si, 0])

    zr = lerp(z)
    run = numpy.where(left, lerp(rl), lerp(rr))
    foot = numpy.where(left, lerp(fl), lerp(fr))
    d = numpy.maximum(dist - lane, 0.0)
    g = zv[pi_]
    zc = numpy.clip(g, zr - d / run, zr + d / run)
    wgt = numpy.clip((foot + FOOT_FADE_M - d) / FOOT_FADE_M, 0.0, 1.0)
    wgt = numpy.minimum(wgt, numpy.clip(foot / FOOT_FADE_M, 0.0, 1.0))
    znew = g + wgt * (zc - g)
    moved = numpy.abs(znew - g) > 1e-3
    return pi_[moved], znew[moved]


def _payload(tile):
    """The tile's levelled-road sidecar, or ``None`` when it has none."""
    path = FNAMES.levelled_roads_file(tile.build_dir, tile.lat, tile.lon)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def ribbon_vertices(tile, vertices, candidates):
    """The ROAD-RIBBON vertices among ``candidates`` (vertex indices, the
    INTERP_ALT corners): those within the lane width (and
    :data:`RIBBON_TOL_M`) of a levelled road's centreline in the sidecar
    -- a shell frees them under its body (``auto_patch.terrain_cut_stage.
    hold``, #2272 S6).  Empty without a sidecar."""
    import shapely

    payload = _payload(tile)
    cand = numpy.unique(numpy.fromiter(candidates, dtype=numpy.int64))
    if payload is None or not len(cand):
        return numpy.zeros(0, dtype=numpy.int64)
    scalx = cos((tile.lat + 0.5) * pi / 180.0)
    lines = [numpy.column_stack([(numpy.asarray(w["lon"]) - tile.lon) * scalx * _M_PER_DEG,
                                 (numpy.asarray(w["lat"]) - tile.lat) * _M_PER_DEG])
             for w in payload.get("ways", ()) if len(w.get("lat") or ()) >= 2]
    if not lines:
        return numpy.zeros(0, dtype=numpy.int64)
    v = numpy.asarray(vertices).reshape(-1, 6)
    cand = cand[(cand >= 0) & (cand < len(v))]
    p = shapely.points(numpy.column_stack([v[cand, 0] * scalx * _M_PER_DEG,
                                           v[cand, 1] * _M_PER_DEG]))
    reach = float(payload.get("lane_width_m", 0.0)) + RIBBON_TOL_M
    (hit, _) = shapely.STRtree(shapely.linestrings(lines)).query_nearest(
        p, max_distance=reach, all_matches=False)
    return cand[numpy.unique(hit)]


def road_bank_values(tile, vertices, fixed):
    """``{vertex index: z}`` for the free mesh vertices the side banks move.

    ``vertices`` is the post-processed flat 6-per-vertex array
    (tile-relative x, y; column 2 the altitude); ``fixed`` the vertices
    another authority values (INTERP_ALT corners, water, patch pins),
    never moved.  Empty when the tile has no levelled-road sidecar or it
    carries no banks.
    """
    payload = _payload(tile)
    if payload is None:
        return {}
    v = numpy.asarray(vertices).reshape(-1, 6)
    free = numpy.ones(len(v), dtype=bool)
    fixed = numpy.fromiter(fixed, dtype=numpy.int64)
    free[fixed[(fixed >= 0) & (fixed < len(v))]] = False
    idx = numpy.flatnonzero(free)
    (sel, znew) = bank_field(payload, tile.lat, tile.lon, v[idx, :2],
                             v[idx, 2])
    return dict(zip(idx[sel].tolist(), znew.tolist(), strict=True))
