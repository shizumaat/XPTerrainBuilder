"""Validate elevation continuity + grade across an X-Plane patch OSM.

Usage:
    python3 tools/check_grade.py <output.osm> [--max-grade 1.5]
                                                [--proximity-m 1.0]
                                                [--edge-step-m 0.5]
                                                [--top-n 10]
                                                [--strict]

Three checks are run on the per-vertex elevations encoded in the
patch (``altitude`` / ``altitude_high`` + ``altitude_low`` /
``node_altitudes`` tags):

1. **Within-shape grade.**  Every pair of vertices on the same way
   must obey ``|de| / dist <= max_grade%`` (default 1.5%).

2. **Cross-shape proximity.**  Two vertices on different ways that
   sit within ``proximity-m`` of each other should agree on
   elevation: max permitted step is the same grade rule applied to
   the (sub-metre) distance — effectively zero step for shared
   corners.  Catches "shape A's corner says X, shape B's matching
   corner says Y" desyncs.

3. **Vertex-to-edge step.**  For every vertex, find the closest
   edge of any OTHER way within 5 m, project the vertex onto that
   edge, and compute the elevation X-Plane would render for the
   *edge* at that projected position (linear interpolation between
   the edge's two endpoint elevations).  The vertex's elevation
   should match within ``edge-step-m`` (default 0.5 m).  Catches
   the "junction triangle 1 m below the sloped taxi rect next to
   it" case.

Exit code is 1 in ``--strict`` mode if any check has any violation
beyond its threshold; 0 otherwise.  Without ``--strict`` the tool
always exits 0 and only reports counts — useful as an informational
diagnostic.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

R_EARTH = 6_378_137.0


# Import per-role grade limits from the auto_patch package (the
# single source of truth).  ``ROLE_GRADE_LIMITS`` maps role-tag to
# decimal grade (e.g. 0.015 for 1.5 %); a value of ``None`` means
# "skip the within-shape grade check for this role".  Roles
# missing from the dict fall back to ``max_grade`` (the function
# argument, default 1.5 %).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(os.path.dirname(_THIS_DIR), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
try:
    from auto_patch.config import (
        ROLE_GRADE_LIMITS,
        GRADE_VISIBILITY_BUFFER_M as _GRADE_VISIBILITY_BUFFER_M,
        ELEV_ROUNDING_NOISE_M,
        SLOPED_QUAD_ROUNDING_NOISE_M,
        ROUTE_FIELD_MODEL,
        ROUTE_FIELD_LOCAL_WINDOW_M,
        ROAD_FRONTAGE_TOL_M,
        DRAINAGE_SPINE_MIN_FALL_M as _DRAINAGE_SPINE_MIN_FALL_M,
        GAP_PAVEMENT_CONFORM_MARGIN_M as _GAP_CONFORM_MARGIN_M,
        SERVICE_ROAD_MAX_GRADE,
        TAXI_GRADE_BY_WIDTH,
        TAXI_GRADE_WIDTH_ROLES,
        TAXI_MAX_GRADE_NARROW,
        TAXI_MAX_TRANSVERSE_NARROW,
        SERVICE_ROAD_MAX_TRANSVERSE,
        taxi_grade_cap_for_letter,
        transverse_cap_for_longitudinal_cap as _transverse_cap_law,
        FAN_RAMP_LAW as _FAN_RAMP_LAW,
        fan_ramp_law_cap as _fan_ramp_law_cap,
    )
    from auto_patch.layout import SHARED_VERTEX_TOL_M
except Exception:
    ROLE_GRADE_LIMITS: Dict[str, Optional[float]] = {}
    # Fallbacks (kept in sync with auto_patch.config/layout) so the standalone
    # validator still runs if the package import fails.
    SHARED_VERTEX_TOL_M = 0.5
    _GRADE_VISIBILITY_BUFFER_M = 1.0
    ELEV_ROUNDING_NOISE_M = 0.03
    SLOPED_QUAD_ROUNDING_NOISE_M = 0.1
    ROUTE_FIELD_MODEL = False
    ROUTE_FIELD_LOCAL_WINDOW_M = 80.0
    ROAD_FRONTAGE_TOL_M = 3.0
    _DRAINAGE_SPINE_MIN_FALL_M = 0.30
    _GAP_CONFORM_MARGIN_M = 10.0
    SERVICE_ROAD_MAX_GRADE = 0.08
    TAXI_GRADE_BY_WIDTH = True
    TAXI_GRADE_WIDTH_ROLES = frozenset({
        "primary_parallel", "secondary_parallel", "stub", "cross_connector",
    })
    TAXI_MAX_GRADE_NARROW = 0.030
    TAXI_MAX_TRANSVERSE_NARROW = 0.020
    SERVICE_ROAD_MAX_TRANSVERSE = 0.020
    _transverse_cap_law = None

    def taxi_grade_cap_for_letter(letter, *, enabled=None):
        on = TAXI_GRADE_BY_WIDTH if enabled is None else enabled
        if on and letter and str(letter).upper() in ("A", "B"):
            return 0.030
        return 0.015

    _FAN_RAMP_LAW = "fan_ramp"

    def _fan_ramp_law_cap(law_value):
        return 0.050 if law_value == _FAN_RAMP_LAW else None

# ── THE GRADED-STRIP SEAM LAW (spec seam-continuity-v2 §1) ──────
# ONE home for the STRIP-seam constants and predicates:
# ``auto_patch.strip_seam_law``.  They used to live in this file only,
# so nothing in ``src/`` could read them and any generation-binding law
# would have had to copy them (docs/RULINGS.md, grade-law completeness:
# emitter and validator must be lockstep, never two copies).  The module
# is stdlib-only and cannot fail to import, so this one is NOT wrapped in
# the standalone fallback above — a law module that silently degrades to a
# second copy of its own numbers is the defect this move exists to end.
#
# VOCABULARY (binding for this lane): "strip seam" = the fabric tear
# between two ``graded_strip`` shapes; "TILE seam" = the graticule
# tile-cut corridor (``TILE_SEAM_*`` below).  A bare ``seam`` identifier
# is banned in new code.  The census row key ``seam::seam`` is
# deliberately NOT renamed (baseline continuity) and means STRIP seam.
from auto_patch.strip_seam_law import (      # noqa: E402
    STRIP_SEAM_TEAR_RADIUS_M,
    STRIP_SEAM_TEAR_MIN_STEP_M,
    STRIP_SEAM_TEAR_MIN_GRADE,
    STRIP_SEAM_TEAR_MIN_DISTANCE_M,
    STRIP_SEAM_WALL_STRADDLE_TOL_M,
    STRIP_SEAM_ROLE,
    STRIP_SEAM_OPEN_GROUND_MIN_M,
    STRIP_SEAM_OPEN_GROUND_SAMPLES,
    STRIP_SEAM_GRADED_ROLES,
    STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M,
    GradedDomain as _GradedDomain,
    WallFaces as _WallFaces,
    open_ground_between as _open_ground_between_law,
    point_in_ring as _point_in_ring,
    seam_pair_is_tear as _seam_pair_is_tear,
)

# LAW GEOMETRY shared with the emitters (single source — never a second
# copy of a rule number here).  ``None`` when the package is unavailable:
# the checks that consume them then report nothing rather than guessing.
try:
    from auto_patch.grade_law import (
        runway_axis_and_width as _runway_axis_and_width,
        runway_strip_wall_keepout_rings as _runway_strip_wall_keepout_rings,
        runway_strip_longitudinal_runs as _runway_strip_longitudinal_runs,
        runway_strip_max_longitudinal_slope as _runway_strip_long_slope,
        drainage_spine_parents as _drainage_spine_parents,
        DRAINAGE_SPINE_PARENT_ROLES as _DRAINAGE_SPINE_PARENT_ROLES,
        # F3c — THE GRADED HANDOFF on a disjoint interval.  One law, both
        # readers: the emitter composes its station interval from these two
        # and so does the dam reader below, so a station in a
        # disjoint-interval zone cannot be emitted against one number and
        # judged against another.
        drainage_spine_envelope as _drainage_spine_envelope,
        drainage_spine_parent_family as _drainage_spine_parent_family,
        drainage_spine_interval as _drainage_spine_interval,
        # ── phase B + the reg families: the law functions the emitters
        # bind through, read HERE verbatim so the census and the surface
        # cannot drift (grade-law completeness, lockstep half).
        strip_longitudinal_law as _strip_longitudinal_law,
        strip_longitudinal_breaches as _strip_longitudinal_breaches,
        # THE AIRSIDE RATE-OF-CHANGE LAW (owner ruling RULINGS
        # 2026-08-27 clause 2; spec ``airside-no-step-law-spec.md``
        # §1.2).  One constant, two readers — the strip family and this
        # one both resolve the aerodrome's vertical-curve rate through
        # ``grade_law``, never a private number here.
        airside_arc_rate_per_m as _airside_arc_rate_per_m,
        resa_transverse_band as _resa_transverse_band,
        raoa_footprint_ring as _raoa_footprint_ring,
        raoa_applies as _raoa_applies,
        shoulder_transverse_envelope as _shoulder_transverse_envelope,
        shoulder_edge_dropoff_exempt as _shoulder_dropoff_exempt,
        transverse_surface_bounds as _transverse_surface_bounds,
        transverse_minimum_for_role as _transverse_minimum_for_role,
        transverse_minimum_binds as _transverse_minimum_binds,
        transverse_span_budget_m as _transverse_span_budget_law,
        # ── THE ROAD CROSS-SECTION LAW (owner RULINGS 2026-08-25g).
        # The ring-axis reader, the ≥45 ° classifier and the cap
        # resolver, read HERE verbatim: ``grade_graph.shape_constraints``
        # flags the solve's pairs with these same three, so the surface
        # we build and the surface we census cannot classify one pair two
        # ways.  ``ROAD_ROLES`` comes from the law too — a fourth
        # hand-written road-role list is the census-wrapper defect.
        long_axis_of_points as _long_axis_of_points,
        pair_is_transverse as _pair_is_transverse,
        road_cross_section_cap as _road_xsection_cap,
        drainage_minimum_grade as _drainage_minimum_grade,
        drainage_minimum_shortfall as _drainage_minimum_shortfall,
        _ADJACENT_APRON_ROLES as _LAW_DRAIN_MIN_APRON_ROLES,
        _DRAINAGE_MIN_GROUNDSIDE_ROLES as _LAW_DRAIN_MIN_GS_ROLES,
    )
    from auto_patch.config import (
        runway_code_number as _runway_code_number,
        runway_code_letter as _runway_code_letter,
        resolve_ruleset as _resolve_ruleset,
        DEFAULT_RULESET as _DEFAULT_RULESET,
        STRIP_PRECEDENCE_ENABLED as _STRIP_PRECEDENCE,
        # NEAR-MISS BUILDING FRONTAGE (cycle-5 item 6): the radius, the role
        # set and the budget the SOLVE prices its law edges with — read here
        # verbatim so the census twin and the surface cannot drift.
        BUILDING_FRONTAGE_NEAR_MISS_M as _BUILDING_FRONTAGE_NEAR_MISS_M,
        NEAR_MISS_FRONTAGE_SOFT_ROLES as _NEAR_MISS_FRONTAGE_SOFT_ROLES,
        near_miss_frontage_budget as _near_miss_frontage_budget,
        # THE TUNNEL-TRENCH DECLARED-STEP LAW (spec docs/specs/
        # tunnel-trench-law-and-basin-floor-spec.md §1): the declared
        # plate roles, the facility join tolerance and the emitter's own
        # floor-disagreement threshold — read HERE verbatim so the census
        # and the trench emitter judge one law.
        DECLARED_TERRAIN_PLATE_ROLES as _DECLARED_PLATE_ROLES,
        BASIN_DECLARED_FLOOR_MATCH_TOL_M as _BASIN_FLOOR_MATCH_TOL_M,
        BASIN_FLOOR_DISAGREEMENT_M as _BASIN_FLOOR_DISAGREEMENT_M,
        ROAD_CROSS_SECTION_LAW as _ROAD_XSECTION_LAW,
    )
except Exception:
    # THE LAW IS UNREACHABLE ⇒ THE LAW DOES NOT RUN, and says so.  The
    # road cross-section has no standalone fallback ON PURPOSE: a second
    # copy of the classifier here is exactly the drift this lane's law
    # module exists to prevent, and a census that silently priced roads
    # against its own private 45 ° / 2 % would be the census-wrapper
    # defect in its usual costume.  Every soft-shape path this reaches
    # already imports ``auto_patch.grade_graph`` unconditionally, so a
    # frame that cannot import the law cannot census within-shape pairs
    # at all.
    _long_axis_of_points = None
    _pair_is_transverse = None
    _road_xsection_cap = None
    _ROAD_XSECTION_LAW = False
    _runway_axis_and_width = None
    _runway_strip_wall_keepout_rings = None
    _runway_strip_longitudinal_runs = None
    _runway_strip_long_slope = None
    _runway_code_number = None
    _runway_code_letter = None
    _resolve_ruleset = None
    _DEFAULT_RULESET = "icao"
    _strip_longitudinal_law = None
    _strip_longitudinal_breaches = None
    _airside_arc_rate_per_m = None
    _resa_transverse_band = None
    _raoa_footprint_ring = None
    _raoa_applies = None
    _shoulder_transverse_envelope = None
    _shoulder_dropoff_exempt = None
    _transverse_surface_bounds = None
    _transverse_minimum_for_role = None
    _transverse_minimum_binds = None
    _transverse_span_budget_law = None
    _drainage_minimum_grade = None
    _drainage_minimum_shortfall = None
    _LAW_DRAIN_MIN_APRON_ROLES = frozenset()
    _LAW_DRAIN_MIN_GS_ROLES = frozenset()
    _STRIP_PRECEDENCE = False
    _BUILDING_FRONTAGE_NEAR_MISS_M = 0.0
    _NEAR_MISS_FRONTAGE_SOFT_ROLES = ()
    _near_miss_frontage_budget = None
    # No-engine fallback for the bare-patch CLI (the ``_GROUNDSIDE_ROLES``
    # pattern below); ``tests/test_harness.py`` twins the values.
    _DECLARED_PLATE_ROLES = frozenset({"tunnel_trench"})
    _BASIN_FLOOR_MATCH_TOL_M = 0.15
    _BASIN_FLOOR_DISAGREEMENT_M = 2.0
    _DRAINAGE_SPINE_PARENT_ROLES = frozenset({
        "runway", "runway_crossing", "primary_parallel",
        "secondary_parallel", "stub", "cross_connector", "junction",
        "apron",
    })
    # No law module ⇒ NO handoff: the dam reader falls back to its
    # pre-F3c geometric form rather than guessing an envelope.
    _drainage_spine_envelope = None
    _drainage_spine_parent_family = None
    _drainage_spine_interval = None

    def _drainage_spine_parents(candidates, max_parents=2):
        best = {}
        for d, key, payload in candidates:
            cur = best.get(key)
            if cur is None or d < cur[0]:
                best[key] = (float(d), key, payload)
        return sorted(best.values(), key=lambda r: (r[0], r[1]))[:max_parents]


# ── OSM parsing ─────────────────────────────────────────────────

_NODE_RE = re.compile(
    r"<node id='(-?\d+)'[^>]*lat='([^']+)'[^>]*lon='([^']+)'"
)
# A node carrying a per-node ``alt_abs`` tag (the backward-compatible
# replacement for the ``node_altitudes`` way tag): the opening <node ...>
# is NOT self-closing and is immediately followed by its alt_abs child.
_NODE_ALT_RE = re.compile(
    r"<node id='(-?\d+)'[^>]*?>\s*<tag k='alt_abs' v='([^']+)'", re.S
)
_WAY_RE = re.compile(r"<way id='(-?\d+)'[^>]*>(.*?)</way>", re.S)
_ND_RE = re.compile(r"<nd ref='(-?\d+)'")
_TAG_RE = re.compile(r"<tag k='([^']+)' v='([^']+)'")


@dataclass
class Way:
    wid: str
    role: str
    ref: str
    aeroway: str
    nids: List[str]               # closed ring (first repeats at end)
    elevs: List[Optional[float]]  # one per nid (closed-ring length)
    tags: Dict[str, str]


def _parse_osm(path: Path, feature_out: "Optional[Dict[str, List[Way]]]" = None
               ) -> Tuple[Dict[str, Tuple[float, float]], List[Way]]:
    """``(nodes, ways)`` — the pavement ways of the patch.

    ``feature_out`` (optional): a dict the OPEN BREAKLINE ways skipped
    below are collected into, keyed by their ``o4_feature`` value.  They
    are not pavement rings and must stay out of every ring-shaped check
    (see the skip comment), but they carry real emitted elevations that
    their OWN laws are checked against — the drainage-spine law reads
    ``feature_out["gap_drainage_spine"]``.  Passing the dict keeps that a
    SINGLE parse of the file rather than a second one."""
    txt = path.read_text()
    nodes: Dict[str, Tuple[float, float]] = {}
    for m in _NODE_RE.finditer(txt):
        nodes[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    node_alt: Dict[str, float] = {}
    for m in _NODE_ALT_RE.finditer(txt):
        try:
            node_alt[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    ways: List[Way] = []
    for m in _WAY_RE.finditer(txt):
        wid = m.group(1)
        body = m.group(2)
        nids = _ND_RE.findall(body)
        if len(nids) < 3:
            continue
        tags = dict(_TAG_RE.findall(body))
        # Crown-spine breaklines (crown.py, user 2026-07-07) are OPEN
        # ways carrying the PRE-crown spine profile as per-node
        # ``alt_abs`` — mesh input only, not a pavement shape.  Grading
        # them as a '?'-role ring produced phantom 10 % pairs (the
        # closing pseudo-edge spans the whole spine).  The gap-fill
        # drainage spines (2026-07-09) and gap interior rings (ratified
        # 2026-07-11) are the same class: open constrained breakline
        # ways inside a gap face — their phantom closing pseudo-edge
        # cuts across the gap and minted artifact vertex-to-edge steps
        # against real interior nodes.
        if tags.get("o4_feature") in ("crown_spine",
                                      "gap_drainage_spine",
                                      "gap_interior_ring",
                                      "apron_lattice",
                                      "apron_spine_station"):
            if feature_out is not None:
                feature_out.setdefault(tags["o4_feature"], []).append(Way(
                    wid=wid, role=tags.get("role", ""),
                    ref=tags.get("ref", ""), aeroway=tags.get("aeroway", ""),
                    nids=nids,
                    elevs=_derive_per_vertex_elevations(nids, tags, node_alt),
                    tags=tags))
            continue
        elevs = _derive_per_vertex_elevations(nids, tags, node_alt)
        ways.append(Way(
            wid=wid,
            role=tags.get("role", ""),
            ref=tags.get("ref", ""),
            aeroway=tags.get("aeroway", ""),
            nids=nids,
            elevs=elevs,
            tags=tags,
        ))
    return nodes, ways


def _derive_per_vertex_elevations(nids: List[str], tags: Dict[str, str],
                                  node_alt: Optional[Dict[str, float]] = None
                                  ) -> List[Optional[float]]:
    """Decode the X-Plane patch elevation tags into a per-nid
    elevation list of the same length as ``nids`` (i.e. closed-ring
    length, last entry == first entry's elevation)."""
    n = len(nids)
    if "altitude_high" in tags and "altitude_low" in tags:
        try:
            ah = float(tags["altitude_high"])
            al = float(tags["altitude_low"])
        except ValueError:
            return [None] * n
        # X-Plane patch convention for a 4-corner rect way:
        # nids[0]=hi-left, [1]=lo-left, [2]=lo-right, [3]=hi-right,
        # [4]=closing repeat of [0].  Way[-2:] = [n3, n0] is the
        # HIGH short edge; way[1:3] = [n1, n2] is the LOW short
        # edge.  See O4_Vector_Map.include_patches() for the parser.
        # altitude_high/low ways are COMPLEX upstream (cplx_way=True):
        # the per-node alt_abs override does NOT apply to them.
        if n == 5:
            return [ah, al, al, ah, ah]
        # Rectangles with insertions along the long edges are
        # unsupported by X-Plane's altitude_high/low parser
        # (it expects exactly 5 nodes); flag as unknown.
        return [None] * n
    # Non-complex ways: start from the way-level altitude form, then apply
    # the per-node ``alt_abs`` override exactly as O4_Vector_Map.include_
    # patches() does (it overrides alti_way[i] for every node carrying the
    # tag).  The legacy ``node_altitudes`` way tag is handled the same way
    # so old and new patches validate identically.
    base: List[Optional[float]]
    if "node_altitudes" in tags:
        try:
            vals = [float(x) for x in tags["node_altitudes"].split(",")]
        except ValueError:
            vals = []
        base = [float(v) for v in vals] if len(vals) == n else [None] * n
    elif "altitude" in tags:
        try:
            base = [float(tags["altitude"])] * n
        except ValueError:
            base = [None] * n
    else:
        base = [None] * n
    if node_alt:
        for i, nid in enumerate(nids):
            if nid in node_alt:
                base[i] = node_alt[nid]
    return base


# ── Coordinate space ────────────────────────────────────────────

def _ll_to_m_factory(nodes: Dict[str, Tuple[float, float]],
                     anchor: "Optional[Tuple[float, float]]" = None):
    """Equirectangular lat/lon→meter factory.

    ``anchor`` (lat, lon): use the BUILDER's projection anchor (from the axes
    sidecar) instead of the mean of nodes — the two frames differ in x-scale
    via ``cos(lat0)``, millimetres over a chord, enough to flip epsilon
    contact predicates (the crossing-skip rule) and make the validator read
    the law differently from the solver.  Same formula and R_EARTH as
    ``auto_patch.layout._projection``, so with the anchor the frames are
    identical to float precision."""
    if anchor is not None:
        lat0, lon0 = float(anchor[0]), float(anchor[1])
    elif nodes:
        lats = [v[0] for v in nodes.values()]
        lons = [v[1] for v in nodes.values()]
        lat0 = sum(lats) / len(lats)
        lon0 = sum(lons) / len(lons)
    else:
        return lambda lat, lon: (0.0, 0.0)
    cos0 = math.cos(math.radians(lat0))

    def _f(lat: float, lon: float) -> Tuple[float, float]:
        x = math.radians(lon - lon0) * R_EARTH * cos0
        y = math.radians(lat - lat0) * R_EARTH
        return x, y
    return _f


# ── Vertex / edge tables ────────────────────────────────────────

@dataclass
class Vertex:
    way_idx: int
    nid: str
    x: float
    y: float
    elev: Optional[float]


@dataclass
class Edge:
    way_idx: int
    a: Tuple[float, float]
    b: Tuple[float, float]
    ea: float
    eb: float


def _build_vertex_edge_tables(
    nodes: Dict[str, Tuple[float, float]],
    ways: List[Way],
    ll_to_m,
) -> Tuple[List[Vertex], List[Edge]]:
    vertices: List[Vertex] = []
    edges: List[Edge] = []
    for way_idx, w in enumerate(ways):
        # Vertices (skip the closing repeat to avoid double-counting).
        for k, nid in enumerate(w.nids[:-1] if len(w.nids) > 1
                                and w.nids[0] == w.nids[-1]
                                else w.nids):
            if nid not in nodes:
                continue
            lat, lon = nodes[nid]
            x, y = ll_to_m(lat, lon)
            vertices.append(Vertex(
                way_idx=way_idx, nid=nid, x=x, y=y, elev=w.elevs[k]))
        # Edges (use the closed ring so the last edge wraps).
        ring = w.nids
        if len(ring) >= 2 and ring[0] != ring[-1]:
            ring = ring + [ring[0]]
        for k in range(len(ring) - 1):
            a_nid = ring[k]
            b_nid = ring[k + 1]
            if a_nid not in nodes or b_nid not in nodes:
                continue
            a_xy = ll_to_m(*nodes[a_nid])
            b_xy = ll_to_m(*nodes[b_nid])
            ea = w.elevs[k] if k < len(w.elevs) else None
            eb = (w.elevs[k + 1] if (k + 1) < len(w.elevs)
                  else w.elevs[0])
            if ea is None or eb is None:
                continue
            edges.append(Edge(
                way_idx=way_idx, a=a_xy, b=b_xy, ea=ea, eb=eb))
    return vertices, edges


# ── Spatial bucketing ───────────────────────────────────────────

def _bucket_vertices(vertices: List[Vertex], cell_m: float
                     ) -> Dict[Tuple[int, int], List[int]]:
    out: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for i, v in enumerate(vertices):
        out[(int(math.floor(v.x / cell_m)),
             int(math.floor(v.y / cell_m)))].append(i)
    return out


def _bucket_edges(edges: List[Edge], cell_m: float
                  ) -> Dict[Tuple[int, int], List[int]]:
    """Bucket each edge into every cell its bounding box touches
    (inflated by 1 cell so a query within any neighbour cell finds
    it)."""
    out: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for i, e in enumerate(edges):
        x_lo = min(e.a[0], e.b[0])
        x_hi = max(e.a[0], e.b[0])
        y_lo = min(e.a[1], e.b[1])
        y_hi = max(e.a[1], e.b[1])
        cx_lo = int(math.floor(x_lo / cell_m))
        cx_hi = int(math.floor(x_hi / cell_m))
        cy_lo = int(math.floor(y_lo / cell_m))
        cy_hi = int(math.floor(y_hi / cell_m))
        for cx in range(cx_lo, cx_hi + 1):
            for cy in range(cy_lo, cy_hi + 1):
                out[(cx, cy)].append(i)
    return out


# ── Checks ──────────────────────────────────────────────────────

@dataclass
class Violation:
    grade_pct: float       # %
    excess_pct: float      # %
    distance_m: float
    de_m: float
    way_a: Way
    way_b: Way
    pt_a: Tuple[float, float]
    pt_b: Tuple[float, float]
    elev_a: float
    elev_b: float
    # Geographic location of the violation (lat, lon), filled in by
    # run_checks so callers can point a user at the spot.  None until set.
    lat: Optional[float] = None
    lon: Optional[float] = None
    #: Set to the NAME of the adjudication that takes this row out of the
    #: acceptance count (currently only ``"disconnected_ring"``).  The row
    #: is still measured, still counted in its family and still printed —
    #: instruments report, the law adjudicates.
    out_of_scope: Optional[str] = None
    #: THE CAP THAT PRICED THIS ROW, in percent (owner ruling RULINGS
    #: 2026-08-21c, spec A1 §2a).  With the apron interior at 5 % and its
    #: movement surfaces at the strict cap, "how bad is this row" is not
    #: answerable from ``grade_pct`` alone — two rows at 3 % are a PASS and a
    #: FAIL depending on which law priced them.  Set by every within-shape
    #: row; ``None`` on families that carry no per-pair cap.
    cap_pct: Optional[float] = None


@dataclass
class EdgeStep:
    step_m: float
    distance_m: float
    way_v: Way
    way_e: Way
    vert_pt: Tuple[float, float]
    proj_pt: Tuple[float, float]
    elev_v: float
    elev_proj: float
    lat: Optional[float] = None
    lon: Optional[float] = None
    out_of_scope: Optional[str] = None


# ELEV_ROUNDING_NOISE_M now imported from auto_patch.config (single source of
# truth shared with the runtime audit) — see the import block above.


# X-Plane tile seams run along integer latitude / longitude lines.
# auto_patch handles them in two passes:
#
#   1. ``seam_anchors`` inserts vertices on each integer line that
#      crosses the airport and HARD-anchors them to ``dem.alt_strict``
#      — the terrain mesh in the neighbour tile pins the same points
#      to DEM, so they must agree or the patch tears at the boundary.
#   2. ``tile_cut`` later subtracts a ``half_width_m`` strip
#      (default 5 m each side, 10 m total) at every integer line.
#      The pre-cut seam vertex at the integer line is removed; the
#      resulting polygon gets new boundary vertices on the airport
#      side of the strip, exactly ``half_width_m`` away from the
#      integer line.  Those new vertices inherit altitudes by
#      resampling (nearest-neighbour or slope-projected) from the
#      pre-cut DEM-anchored ring — so they're effectively DEM-pinned
#      too, even though they no longer carry the seam tag.
#
# Both classes of vertex are immovable from the solver's POV: their
# altitudes are dictated by the DEM at the tile boundary, and the
# adjacent-tile patch + terrain mesh must agree exactly.  Within-
# shape grade between any pair touching one of these vertices is a
# function of DEM noise at the tile edge, not of solver feasibility,
# so we skip those pairs (and any triangle that touches one).
#
# Cross-shape proximity and edge/mid-edge step checks naturally
# still pass because both adjacent shapes sample the same DEM at
# the same XY, so the tile-edge vertex altitudes agree across
# shapes.
#
# Detection is geometric: a vertex is on the tile seam iff its lat
# OR its lon is within ``TILE_SEAM_LL_TOL_DEG`` of an integer value.
# The tolerance (1e-4 °, ~11 m) covers the 5-m offset of post-cut
# boundary vertices plus slack for projection round-trip drift.
TILE_SEAM_LL_TOL_DEG = 1e-4

# SEAM TERRAIN-MATCHING ZONE (user 2026-06-20): at a tile boundary the
# pavement must MATCH the neighbour tile's terrain mesh (so X-Plane bridges the
# gap without a cliff), so it follows the DEM from the seam inward — not the
# designed flat/compliant surface.  The within-shape grade cap and the
# runway-anchored route-band law both assume a designed surface, so they YIELD
# inside this zone.  Only shapes that actually reach a seam (a real integer-line
# crossing) get the zone; single-tile airports are unaffected.  The width
# covers the cross-seam sliver where terrain controls (SPLP descends ~4 m to
# the seam over a few hundred metres).  NOT special-cased per airport.
TILE_SEAM_ZONE_M = 400.0
_M_PER_DEG_LAT = 110540.0


def _seam_lines(nodes: Dict[str, Tuple[float, float]]) -> Tuple[set, set]:
    """Integer lat / lon values that an exact seam vertex sits on — i.e. the
    tile boundaries the airport actually CROSSES (a real seam, not just being
    near a tile edge)."""
    seam_lats: set = set()
    seam_lons: set = set()
    for (lat, lon) in nodes.values():
        if abs(lat - round(lat)) <= TILE_SEAM_LL_TOL_DEG:
            seam_lats.add(round(lat))
        if abs(lon - round(lon)) <= TILE_SEAM_LL_TOL_DEG:
            seam_lons.add(round(lon))
    return seam_lats, seam_lons


def _seam_nids_from_pins(nodes: Dict[str, Tuple[float, float]],
                         seam_pins_ll: list) -> set:
    """Nids coincident (≤ ``SHARED_VERTEX_TOL_M``) with a sidecar seam-PIN
    vertex — the exact DEM-pinned anchors the solver graded to.  Replaces
    the 400 m zone of :func:`_seam_nids` when the sidecar carries pins."""
    if not seam_pins_ll:
        return set()
    out: set = set()
    for nid, (lat, lon) in nodes.items():
        mlon = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(lat)))
        for (pla, plo) in seam_pins_ll:
            d_lat = abs(lat - pla) * _M_PER_DEG_LAT
            if d_lat > SHARED_VERTEX_TOL_M:
                continue
            if math.hypot(d_lat, abs(lon - plo) * mlon) \
                    <= SHARED_VERTEX_TOL_M:
                out.add(nid)
                break
    return out


def _crown_drops_by_nid(nodes: Dict[str, Tuple[float, float]],
                        crown_drops_ll: list) -> Dict[str, float]:
    """Map each nid to its solver crown drop (axes sidecar ``crown_drops``,
    ``[[lat, lon, drop], …]``) — nids coincident (≤ ``SHARED_VERTEX_TOL_M``)
    with an exported field node.  The within-shape law re-centres each
    pair's budget on ``grade_law.crown_pair_offset`` from this field, so
    the validator reads the SAME designed crown the solver built (part
    30).  Empty/None ⇒ offset 0 everywhere (uncrowned/old patches)."""
    if not crown_drops_ll:
        return {}
    # coarse lat/lon grid (~SHARED_VERTEX_TOL_M cells) for O(1) lookups.
    # ONE cell size for build AND lookup (reference latitude): a per-point
    # cos(lat) cell size shifts the integer cell index by whole cells at
    # large |lon| (~14.6 M cells at lon −135), silently missing matches.
    ref_lat = crown_drops_ll[0][0]
    cell_lat = SHARED_VERTEX_TOL_M / _M_PER_DEG_LAT
    mlon_ref = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(ref_lat)))
    cell_lon = SHARED_VERTEX_TOL_M / mlon_ref
    grid: Dict[Tuple[int, int], list] = defaultdict(list)
    for (pla, plo, drop) in crown_drops_ll:
        grid[(int(pla // cell_lat), int(plo // cell_lon))].append(
            (pla, plo, float(drop)))
    out: Dict[str, float] = {}
    for nid, (lat, lon) in nodes.items():
        mlon = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(lat)))
        gx, gy = int(lat // cell_lat), int(lon // cell_lon)
        best = None
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for (pla, plo, drop) in grid.get((gx + ox, gy + oy), ()):
                    d = math.hypot((lat - pla) * _M_PER_DEG_LAT,
                                   (lon - plo) * mlon)
                    if d <= SHARED_VERTEX_TOL_M and (best is None
                                                     or d < best[0]):
                        best = (d, drop)
        if best is not None:
            out[nid] = best[1]
    return out


def _crown_centerline_nids(nodes: Dict[str, Tuple[float, float]],
                           crown_centerline_ll: list) -> set:
    """The nids coincident (≤ ``SHARED_VERTEX_TOL_M``) with a CROWN-CENTERLINE
    vertex the interior runway cross-edge crown inserted (axes sidecar
    ``crown_centerline``, ``[[lat, lon], …]``).  Such a node lies ON the
    runway ridge, so its longitudinal grade is governed by the SPINE PROFILE
    check and its lateral crown is sub-cap by design — the within-shape
    flat-cap all-pairs plane law skips any runway pair touching one (a
    cross-station diagonal to it would conflate the two).  Empty/None ⇒ no
    skips (uncrowned / old patches)."""
    if not crown_centerline_ll:
        return set()
    ref_lat = crown_centerline_ll[0][0]
    cell_lat = SHARED_VERTEX_TOL_M / _M_PER_DEG_LAT
    mlon_ref = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(ref_lat)))
    cell_lon = SHARED_VERTEX_TOL_M / mlon_ref
    grid: Dict[Tuple[int, int], list] = defaultdict(list)
    for (pla, plo) in crown_centerline_ll:
        grid[(int(pla // cell_lat), int(plo // cell_lon))].append((pla, plo))
    out: set = set()
    for nid, (lat, lon) in nodes.items():
        mlon = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(lat)))
        gx, gy = int(lat // cell_lat), int(lon // cell_lon)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for (pla, plo) in grid.get((gx + ox, gy + oy), ()):
                    d = math.hypot((lat - pla) * _M_PER_DEG_LAT,
                                   (lon - plo) * mlon)
                    if d <= SHARED_VERTEX_TOL_M:
                        out.add(nid)
                        break
    return out


def _seam_nids(nodes: Dict[str, Tuple[float, float]]) -> set:
    """Set of nids in the seam terrain-matching zone: within ``TILE_SEAM_ZONE_M``
    of a tile boundary the airport CROSSES (lat/lon line carrying an exact seam
    vertex).  Empty for single-tile airports → no exemption (byte-identical)."""
    seam_lats, seam_lons = _seam_lines(nodes)
    if not seam_lats and not seam_lons:
        return set()
    out: set = set()
    for nid, (lat, lon) in nodes.items():
        d = float("inf")
        for sl in seam_lats:
            d = min(d, abs(lat - sl) * _M_PER_DEG_LAT)
        if seam_lons:
            mlon = _M_PER_DEG_LAT * max(0.05, math.cos(math.radians(lat)))
            for sl in seam_lons:
                d = min(d, abs(lon - sl) * mlon)
        if d <= TILE_SEAM_ZONE_M:
            out.add(nid)
    return out


def _check_plane_gradient(ways: List[Way],
                          nodes: Dict[str, Tuple[float, float]],
                          ll_to_m,
                          max_grade: float,
                          seam_nids: Optional[set] = None,
                          crown_by_nid: Optional[Dict[str, float]] = None,
                          ) -> List[Violation]:
    """For each 3-vertex polygon (a triangle, which X-Plane renders
    as a planar surface), compute the plane's elevation gradient
    and flag if its magnitude exceeds ``max_grade``.

    A triangle can pass every vertex-PAIR grade check yet still
    have a steep perpendicular gradient: for (A=20, B=19, C=19.5)
    placed with A 300 m from B (edge grades ~0.3 %), the plane's
    gradient perpendicular to BC may be several %.  This shows up
    as a visible slope inside the triangle even though no vertex
    pair is "too steep".

    Triangles that touch any seam vertex are skipped — their plane
    is dictated by DEM-pinned corners the solver cannot move.

    SPINE CROWN (part 30): ``crown_by_nid`` is the solver's designed
    crown-drop field (sidecar ``crown_drops`` → ``_crown_drops_by_nid``).
    The plane is evaluated in UNCROWNED space ``z' = z + crown_drop`` —
    the SAME space the solver grades in (``grade_law`` crown block) and
    the within-shape pair check re-centres to via
    ``grade_law.crown_pair_offset``.  Without the lift this check was
    the one crown-blind reader of the three (solver / within-pair /
    plane): a lawful crowned triangle spanning a ridge node and dropped
    edge nodes false-flagged whenever the raw resultant tilt
    (longitudinal grade ⊕ transverse crown) exceeded the cap — SPJC
    junction #141 read 2.30 % raw vs 1.10 % designed.  Since every
    crown rate ≤ every transverse cap, the lift can only remove the
    designed-crown component — a genuinely over-cap surface still
    flags — and an empty field (uncrowned / old patches) leaves
    ``z' = z``, byte-identical to the unlifted check.
    """
    seam_nids = seam_nids or set()
    crown_by_nid = crown_by_nid or {}
    out: List[Violation] = []
    for w in ways:
        grade_cap = _role_grade_limit(w, max_grade)
        if grade_cap is None:
            continue
        # Pre-screen ring nids — skip the whole triangle if any
        # vertex lies on the tile seam.
        ring_nids = (w.nids[:-1] if (len(w.nids) > 1
                     and w.nids[0] == w.nids[-1])
                     else w.nids)
        if any(nid in seam_nids for nid in ring_nids):
            continue
        pts: List[Tuple[float, float, float]] = []
        for k, nid in enumerate(w.nids[:-1] if (len(w.nids) > 1
                                and w.nids[0] == w.nids[-1])
                                else w.nids):
            if nid not in nodes:
                continue
            lat, lon = nodes[nid]
            x, y = ll_to_m(lat, lon)
            e = w.elevs[k]
            if e is None:
                continue
            # Crown lift: evaluate the plane in the solver's UNCROWNED
            # space (see the docstring) — 0 for nodes off the field.
            pts.append((x, y, e + crown_by_nid.get(nid, 0.0)))
        if len(pts) != 3:
            continue  # only check triangles
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = pts
        # Plane normal via cross product of two in-plane vectors.
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        if abs(nz) < 1e-6:
            continue  # degenerate triangle in xy plane
        # Plane: nx*X + ny*Y + nz*Z = d; dz/dx = -nx/nz, dz/dy = -ny/nz.
        gx = -nx / nz
        gy = -ny / nz
        grad = math.hypot(gx, gy)
        # Project vertices along the gradient direction to get the
        # plane's altitude swing across the triangle.  The
        # gradient check fires only when the swing exceeds the
        # grade cap allowance for that swing distance — matching
        # the within-shape pair check's rounding-noise envelope.
        gnorm = grad
        if gnorm < 1e-9:
            continue
        ghx, ghy = gx / gnorm, gy / gnorm
        proj = [(p[0] * ghx + p[1] * ghy, p[2], p)
                for p in pts]
        proj.sort()
        lo_p, lo_z, lo_pt = proj[0]
        hi_p, hi_z, hi_pt = proj[-1]
        dist_along_grad = hi_p - lo_p
        de_along_grad = abs(hi_z - lo_z)
        allowance = grade_cap * dist_along_grad + ELEV_ROUNDING_NOISE_M
        if de_along_grad <= allowance:
            continue
        out.append(Violation(
            grade_pct=grad * 100,
            excess_pct=(grad - grade_cap) * 100,
            distance_m=dist_along_grad if dist_along_grad > 0.5
                       else 1.0,
            de_m=de_along_grad,
            way_a=w, way_b=w,
            pt_a=(lo_pt[0], lo_pt[1]),
            pt_b=(hi_pt[0], hi_pt[1]),
            elev_a=lo_z, elev_b=hi_z))
    return out


# (The old WITHIN_SHAPE_MAX_PAIR_DIST_M distance cap was removed: the
# within-shape check is now uncapped + visibility-gated — see
# _check_within_shape.)


def _lateral_cap_tag(way: "Way") -> Optional[float]:
    """The LATERAL-CONTIGUITY cap the build stamped on this way
    (``o4_grade_law_cap``, owner FINAL 2026-08-02 clause 2), or ``None``.

    The solver reads the same number off ``BuiltShape.lateral_cap`` through
    ``grade_graph._body_cap`` — one law, two readers."""
    raw = way.tags.get("o4_grade_law_cap")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _role_grade_limit(way: "Way",
                      default_grade: float) -> Optional[float]:
    """Resolve the within-shape grade limit for a way.

    Looks up the way's ``role`` tag in ``ROLE_GRADE_LIMITS`` (the
    single source of truth in ``auto_patch.config``):

    * Returns the role-specific limit (decimal, e.g. 0.015) if
      the role is present.
    * Returns ``None`` if the role is explicitly mapped to ``None``
      (skip the check — vertical structures, terrain-following
      outlines).
    * Falls back to ``default_grade`` when the role is absent
      from the dict (unknown role; use the function-argument
      cap so behaviour stays compatible with un-tagged input).
    """
    role = law_role(way)
    # APRON-EDGE GRADE ADOPTION (USER RULING 2026-07-06): a service
    # road/junction portion inside or alongside an apron follows the
    # apron grading rules — the build stamps ``o4_grade_law='apron'``
    # on exactly those pieces; validate them at that role's cap so both
    # readers apply the same law.
    _law_override = way.tags.get("o4_grade_law")
    # THE FAN-RAMP LAW (owner RULINGS 21f0980): a declared fan-ramp zone
    # piece is apron ground between two adjacent building frontages,
    # clear of every aircraft-movement surface, and holds the ZONE cap.
    # Resolved by the ONE function the solver's cap resolvers read
    # (``config.fan_ramp_law_cap``); it RELAXES, so it is answered before
    # the strict role table below.  Returned WITHOUT the lateral minimum:
    # the lateral-contiguity law binds ROADS (its own role set), never an
    # apron piece, so there is no cap for it to compose with here.
    _fan_cap = _fan_ramp_law_cap(_law_override)
    if _fan_cap is not None:
        return _fan_cap
    # TAXIWAY-EDGE ADOPTION (USER RULING 2026-07-07): a service-road
    # portion inside/alongside a taxiway follows the taxiway grade law
    # (1.5 %, letter-aware).  The build stamps ``o4_grade_law='taxi'`` +
    # ``code_letter``; validate at the same letter-aware cap the solver
    # used so both readers apply the same law.
    if _law_override == "taxi":
        base = taxi_grade_cap_for_letter(way.tags.get("code_letter"))
    elif _law_override and _law_override in ROLE_GRADE_LIMITS:
        base = ROLE_GRADE_LIMITS[_law_override]
    # Size-dependent taxiway cap (gate TAXI_GRADE_BY_WIDTH): a sized
    # taxiway carries the ICAO code letter the build stamped on it; code
    # A/B (narrow, <15 m) validate at 3 %, C–F at 1.5 % — ICAO Annex 14
    # §3.9.8.  Mirrors the solver's per-shape cap so the validator and
    # build stay in lockstep.  Patches without the tag (gate off / older
    # builds) fall through to the uniform role cap below.
    elif role in TAXI_GRADE_WIDTH_ROLES and way.tags.get("code_letter"):
        base = taxi_grade_cap_for_letter(way.tags.get("code_letter"))
    elif role in ROLE_GRADE_LIMITS:
        base = ROLE_GRADE_LIMITS[role]
    else:
        base = default_grade
    # LATERAL-CONTIGUITY LAW (owner FINAL 2026-08-02, clause 2): the piece
    # carries the strictest cap of its laterally-contiguous cross-section.
    # A MINIMUM, never a relaxation — the same composition
    # ``grade_graph._body_cap`` applies on the solver side.
    lat = _lateral_cap_tag(way)
    if lat is not None and base is not None:
        return min(base, lat)
    return base


def _pair_grade_limit(way_a: "Way", way_b: "Way",
                      default_grade: float) -> Optional[float]:
    """Resolve the cross-shape grade limit between two ways.

    Returns ``None`` (= skip the pair) when either way's role is
    on the skip-list (boundary, retaining_wall,
    groundside_pavement) — these are intentionally at terrain
    elevations or stacked at different vertical layers (a
    retaining_wall sitting at apt_elev above a tunnel_ramp at
    apt_elev−8m at the same XY is not an elevation
    "disagreement"; the wall and the ramp are different terrain
    layers by design).

    Otherwise returns the more restrictive of the two role's
    grade caps so close-but-not-shared vertices satisfy both
    surfaces' grade rules.
    """
    a = _role_grade_limit(way_a, default_grade)
    if a is None:
        return None
    b = _role_grade_limit(way_b, default_grade)
    if b is None:
        return None
    return min(a, b)


# Groundside pavement (vehicle roads, curbside drop-off, parking) is
# deliberately SEPARATED from airside pavement by a clearance gap and a
# retaining / vertical wall (user 2026-05-28): the two surfaces are NOT meant to
# be flush and can legitimately differ by several metres.  So the cross-shape
# STEP checks below — which assume neighbouring pavement should be vertically
# continuous — must NOT fire across the airside <-> groundside boundary.  (Each
# side's own within-shape grade still applies.)
# ``tunnel_ramp`` (the depressed-road plates + portal ramps) is the same class
# (user 2026-06-10): the road runs at apt_elev−8 m, clipped 0.5 m short of all
# airside pavement — the 8 m face across that designed gap is the retaining
# wall, not an elevation defect.  KPHX's ZDP aprons abutting Sky Harbor Blvd
# fired 307 step / 32 cross warnings on this designed separation.
# ONE PARTITION, BOTH SIDES (cycle 8, the projection-partition round).
# The solve's RECEIVER set and this census's SIDE split are the same law:
# ``layout.GROUNDSIDE_ROLES`` is the registry's copy and this reads it, so
# a role added to one side cannot silently miss the other (the lockstep
# pattern the frontage-gap lesson bought).  The literal below is the
# no-engine fallback for the bare-patch CLI, and the harness twin
# ``tests/test_harness.py`` asserts the two agree.
try:                                                   # pragma: no cover
    from auto_patch.layout import GROUNDSIDE_ROLES as _LAYOUT_GS_ROLES
    _GROUNDSIDE_ROLES = set(_LAYOUT_GS_ROLES)
except Exception:                                      # pragma: no cover
    _GROUNDSIDE_ROLES = {"groundside_pavement", "service_road",
                         "service_junction", "tunnel_ramp"}


def _is_groundside(way: "Way") -> bool:
    return law_role(way) in _GROUNDSIDE_ROLES


# THE ROAD FAMILY, from THE LAW (``grade_law.ROAD_ROLES``).  RULINGS
# 2026-08-25g puts the road CROSS-SECTION limit on this exact set, so a
# second spelling here would be two laws over two populations — the
# census-wrapper defect.  The literal is the no-engine fallback only, and
# ``tests/test_road_cross_section.py`` asserts the two agree.
try:                                                   # pragma: no cover
    from auto_patch.grade_law import ROAD_ROLES as _LAW_ROAD_ROLES
    _ROAD_FAMILY_ROLES = set(_LAW_ROAD_ROLES)
except Exception:                                      # pragma: no cover
    _ROAD_FAMILY_ROLES = {"service_road", "service_junction"}

# ══════════════════════════════════════════════════════════════════════
# ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST
# (lead ruling 2026-08-07, nidfix2 escalation (a))
# ══════════════════════════════════════════════════════════════════════
#
# THE DEFECT.  A handful of emitted ways carry an ``o4_feature`` tag and NO
# ``role`` tag at all — HECA's 232-way population: ``shape_interior_ring``
# 92, ``gap_interior_ring`` 88, ``gap_drainage_spine`` 49, ``crown_spine``
# 3.  They are ARTICULATION geometry (a shape's hole boundary, a breakline
# inside a gap face, a crown ridge), not surfaces.  Judged as surfaces they
# fall through ``_role_grade_limit``'s unknown-role branch to the CALLER's
# default cap — 1.5 % in the law-true frame — and through ``_is_groundside``
# to AIRSIDE, whatever their host actually is.  Measured on the frame of
# record: three ``shape_interior_ring`` rows, every one of them hosted by a
# ``service_junction`` (an 8 % GROUNDSIDE surface), reported as airside 1.5 %
# violations; two of the three duplicate their host way's whole vertex set,
# so that geometry was being judged twice.
#
# THE RULING.  "They take the ROLE AND SIDE of their HOST shape and are
# judged at the host's cap; where their geometry duplicates a host way's,
# rows belong to the HOST ONLY — one geometry, one row set; never
# airside-default at 1.5 %, never a double-count."
#
# WHAT IS IMPLEMENTED — AND THE CAP CLAUSE, NOW LAW (L-1).
# Role, side and the duplicate disposition landed first, under the
# ADJUDICATION-ONLY materiality-floor spec ("law, generation and law-true
# counts unchanged"), so "JUDGED AT THE HOST'S CAP" was deliberately left
# out then.  It is IN now: spec ``tunnel-ramp-cut-boundaries-spec.md`` §3
# (L-1) makes it law, because ruling 4's ramp/pavement cut turns every
# tunnel-ramp cut edge into a role-less ``shape_interior_ring`` — the hole
# the cut leaves in the pavement — and OTHH's two rings (-12315/-12316)
# minted 78 step + 9 within-shape rows purely by falling through to the
# CALLER's default cap (1.5 %) and to AIRSIDE, while the ring's own host is
# the 4 % groundside tunnel ramp whose vertices it literally is.
#
# THE SCOPE, AND WHY IT IS NOT A ROLE STAMP.  The cap clause is applied
# through ``law_role`` — ONE accessor, read by the ONE cap resolver
# (``_role_grade_limit``), the ONE side partition (``_is_groundside``) and
# the road-family test in ``_airside_groundside_pair``.  The ``role`` tag
# itself is still NOT written, and that is the difference between JUDGING a
# ring at its host's cap and ADMITTING it into its host's laws: a stamped
# ``role`` also selects a way into ``_DRAINAGE_MIN_ROLES`` /
# ``_STRIP_PAVEMENT_ROLES``, which on the frame of record MINTED a phantom
# drainage-minimum row by treating an articulation ring as a surface that
# must drain.  ``law_role`` moves the CAP and the SIDE — what the spec
# names — and moves no way into a law it is not a surface of.
# ``HOST_CAP_FEATURE_CLASSES`` is the scope: the INTERIOR RING classes the
# spec names.  ``gap_drainage_spine`` keeps reporting-only host resolution
# (it is a breakline, not a ring, and it is the class that minted the
# phantom row); ``crown_spine`` is inert either way.
#
# TWO HOST RESOLVERS, ONE NOTION, each named on the row it stamps:
#
#   ``shared_nodes``       — a ``shape_interior_ring``'s nids ARE its host's
#                            already-interned vertices (``layout.to_osm``:
#                            "the nids are the already-interned
#                            exterior/wall vertices, so nothing new is
#                            created here").  The host is the role-carrying
#                            way sharing the MOST of them.
#   ``drainage_parents``   — a ``gap_drainage_spine``'s nodes are NEW ids
#                            shared with nothing, so node sharing cannot
#                            answer.  Its host is the bounding pavement the
#                            DRAINAGE LAW ITSELF already selected
#                            (``grade_law.drainage_spine_parents``, the same
#                            function ``gap_fill`` ranks with) — never a
#                            second predicate invented here.
#
# ``gap_interior_ring`` and ``crown_spine`` are open breaklines skipped by
# ``_parse_osm`` and consumed by no law, so they mint no rows and there is
# nothing to side; they are named in the register anyway, because a class
# absent from a register is a class the next reader re-discovers by hand.
ROLE_LESS_HOST_RULING = (
    "2026-08-07 (lead, nidfix2 escalation (a)) — Role-less feature ways "
    "side with their host")

#: The ``o4_feature`` classes the emitter writes with NO ``role`` tag.
#: NOTE (blast role-literal hazard): these are ``layout.to_osm`` literals.
ROLE_LESS_FEATURE_CLASSES: Tuple[str, ...] = (
    "shape_interior_ring",
    "gap_interior_ring",
    "gap_drainage_spine",
    "crown_spine",
    # THE APRON INTERIOR LATTICE (spec heca-apron-round2 Amendment 1
    # §1b): open constrained breakline ways carrying interior apron
    # anchors as per-node ``alt_abs``.  Role-less like the spines, and
    # for the same reason — a phantom closing pseudo-edge across the
    # apron would mint artifact pairs the solver never constrained.
    # Its real law is the ``apron_lattice_membrane`` family, which
    # prices each published edge against the solve's own budget.
    "apron_lattice",
    # APRON SPINE STATIONS (spec heca-apron-round3 §1): the interior
    # CENTERLINE stations of an aircraft taxi axis crossing an apron,
    # one open way per crossing.  Role-less and open for the lattice's
    # reason — a phantom closing pseudo-edge back across the apron would
    # mint artifact pairs the solver never constrained.  Its law is the
    # SAME registered family as the lattice's,
    # ``apron_lattice_membrane``: the station edges extend the same
    # sidecar publication, because the lattice and the stations are ONE
    # membrane (RULINGS 2026-08-26b item 4, "join seamlessly").
    "apron_spine_station",
)

#: The subset of :data:`ROLE_LESS_FEATURE_CLASSES` whose members are judged
#: at their HOST's role and cap — spec ``tunnel-ramp-cut-boundaries-spec.md``
#: §3 (L-1), "a role-less ``shape_interior_ring`` way is judged at its HOST
#: shape's role/cap ... not at airside defaults".  Interior RINGS only: they
#: are a host shape's own hole boundary, carrying the host's own interned
#: vertices, so the host's law is the only law that ever described them.
#: A class outside this set keeps host resolution for REPORTING only.
HOST_CAP_FEATURE_CLASSES: Tuple[str, ...] = (
    "shape_interior_ring",
    "gap_interior_ring",
)

#: The in-memory tags the host resolvers stamp.  They are NEVER written to a
#: patch — an emitted way carries none of them — so a stamped tree and a
#: freshly parsed one differ only in what the REPORT can say.
HOST_WAY_TAG = "o4_host_way"
HOST_ROLE_TAG = "o4_host_role"
HOST_SOURCE_TAG = "o4_host_source"
HOST_SHARED_NODES_TAG = "o4_host_shared_nodes"
HOST_DUPLICATE_TAG = "o4_host_duplicate"

try:                                                   # pragma: no cover
    from auto_patch.layout import AUTHORITY_RANK as _LAYOUT_AUTHORITY_RANK
except Exception:                                      # pragma: no cover
    _LAYOUT_AUTHORITY_RANK = {}


def _authority_rank(role: Optional[str]) -> int:
    """The emitter's OWN airside-first precedence rank for a role
    (``layout.AUTHORITY_RANK``); unnamed roles rank last.  Used only to
    break a host TIE deterministically, so the winner of "two shapes share
    the same number of this ring's vertices" is the one the emitter itself
    would let author the value."""
    return _LAYOUT_AUTHORITY_RANK.get(role, len(_LAYOUT_AUTHORITY_RANK) + 1)


def resolve_feature_hosts(ways: List["Way"],
                          feature_ways: "Optional[List[Way]]" = None) -> dict:
    """Stamp every ROLE-LESS feature way in ``ways`` with its HOST shape.

    Returns ``{feature wid: {...}}`` — the host way id, its role, how many
    of the feature way's DISTINCT nodes the host carries, how many it has,
    and whether the host's vertex set COVERS the feature way's (the
    ruling's "duplicates a host way's geometry").

    THE ``role`` TAG ITSELF IS STILL NOT WRITTEN.  A role tag is LAW
    INPUT twice over: it resolves a cap and a side, AND it selects a way
    into ``_DRAINAGE_MIN_ROLES`` / ``_STRIP_PAVEMENT_ROLES``.  Stamping it
    MEASURABLY moves the population — on the frame of record it removed two
    within-shape rows and MINTED one phantom drainage-minimum row by
    admitting an articulation ring into that law's surface set.  So L-1
    (spec ``tunnel-ramp-cut-boundaries-spec.md`` §3) takes the first half
    only: an INTERIOR RING (:data:`HOST_CAP_FEATURE_CLASSES`) is JUDGED at
    its host's cap and side through :func:`law_role`, and joins no law it
    is not a surface of.  The adjudication clause is unchanged: a row whose
    geometry the host already carries is marked ``role_less_host_duplicate``
    (one geometry, one row set), and every row's reported role and side are
    read through ``effective_role``.  A way whose host cannot be resolved is
    left exactly as parsed.

    Called once, from ``run_checks``, before any check runs.
    """
    hosts: dict = {}
    candidates = [w for w in ways if w.tags.get("role")]
    if not candidates:
        return hosts
    owner: Dict[str, List["Way"]] = {}
    for w in candidates:
        for nid in set(w.nids):
            owner.setdefault(nid, []).append(w)
    pool = list(ways) + list(feature_ways or ())
    for w in pool:
        if w.tags.get("role"):
            continue
        if w.tags.get("o4_feature") not in ROLE_LESS_FEATURE_CLASSES:
            continue
        distinct = set(w.nids)
        share: Dict[str, int] = {}
        by_wid: Dict[str, "Way"] = {}
        for nid in distinct:
            for h in owner.get(nid, ()):
                share[h.wid] = share.get(h.wid, 0) + 1
                by_wid[h.wid] = h
        if not share:
            continue
        # Most shared vertices wins; ties go to the emitter's own
        # airside-first authority order, then to the lowest way id — a
        # host that depends on dict iteration order is not a measurement.
        best_wid = sorted(
            share, key=lambda k: (-share[k],
                                  _authority_rank(by_wid[k].tags.get("role")),
                                  str(k)))[0]
        host = by_wid[best_wid]
        n_shared = share[best_wid]
        duplicate = (n_shared == len(distinct) and len(distinct) >= 3)
        w.tags[HOST_WAY_TAG] = str(host.wid)
        w.tags[HOST_ROLE_TAG] = host.tags["role"]
        w.tags[HOST_SOURCE_TAG] = "shared_nodes"
        w.tags[HOST_SHARED_NODES_TAG] = str(n_shared)
        if duplicate:
            w.tags[HOST_DUPLICATE_TAG] = "1"
        hosts[str(w.wid)] = {
            "feature": w.tags.get("o4_feature"),
            "host_way": str(host.wid),
            "host_role": host.tags["role"],
            "host_source": "shared_nodes",
            "shared_nodes": n_shared,
            "n_nodes": len(distinct),
            "duplicate": duplicate,
        }
    return hosts


def law_role(way: "Way") -> Optional[str]:
    """THE ROLE THE LAW JUDGES THIS WAY AT — its own ``role`` tag, or, for
    a role-less INTERIOR RING (:data:`HOST_CAP_FEATURE_CLASSES`), its
    resolved HOST's (spec ``tunnel-ramp-cut-boundaries-spec.md`` §3, L-1).

    THE single accessor for that question.  Its three readers are the ONE
    cap resolver (:func:`_role_grade_limit`), the ONE side partition
    (:func:`_is_groundside`) and the road-family test in
    :func:`_airside_groundside_pair` — so a ring is judged at its host's
    cap and on its host's side, in the CLI, the census and the pytest
    fixtures alike (one code path; ``tests/test_harness.py`` twin-asserts
    that no reader of the raw tag reappears beside them).

    It deliberately does NOT stamp ``role``: membership of the surface
    laws (``_DRAINAGE_MIN_ROLES``, ``_STRIP_PAVEMENT_ROLES``, …) still
    reads the raw tag, so an articulation ring is judged at its host's cap
    without being admitted to laws it is not a surface of.  A way whose
    host did not resolve reads exactly as parsed."""
    if way is None:
        return None
    tags = getattr(way, "tags", None) or {}
    own = tags.get("role")
    if own:
        return own
    if tags.get("o4_feature") in HOST_CAP_FEATURE_CLASSES:
        return tags.get(HOST_ROLE_TAG) or None
    return None


def effective_role(way: "Way") -> Optional[str]:
    """The way's own ``role``, or — for ANY ROLE-LESS feature way — its
    resolved HOST's (lead ruling 2026-08-07).

    The REPORTING accessor, wider than :func:`law_role`: it sides every
    role-less class, including the breaklines the law still judges as
    parsed, so ``row_roles`` / ``row_side`` / ``row_runway_family`` — the
    accessors a REPORT is built from — never present an articulation way
    as an airside-by-default surface."""
    if way is None:
        return None
    tags = getattr(way, "tags", None) or {}
    return tags.get("role") or tags.get(HOST_ROLE_TAG) or None


def role_less_host_duplicate(row) -> bool:
    """True when EVERY way of ``row`` is a role-less feature way whose host
    COVERS its vertex set — the ruling's "rows belong to the HOST ONLY".

    Both ways, deliberately, exactly as ``_mark_disconnected`` requires both
    endpoints: a row between an articulation ring and a DIFFERENT shape is a
    statement about that pair, and the host does not own it."""
    a = getattr(row, "way_a", None) or getattr(row, "way_v", None)
    b = getattr(row, "way_b", None) or getattr(row, "way_e", None)
    ws = [w for w in (a, b) if w is not None]
    if not ws:
        return False
    return all((getattr(w, "tags", None) or {}).get(HOST_DUPLICATE_TAG)
               for w in ws)


def _airside_groundside_pair(way_a: "Way", way_b: "Way") -> bool:
    """True iff a designed wall separates the two ways: exactly one is
    groundside, OR exactly one is ROAD-family (s79 Step D) — a
    ground-vehicle road grades at 5 % from its apron mouth down to
    terrain, so where it runs beside curbside groundside (the CYXY
    pav[1] ramp: a 6.5 m retaining wall vs the parking lot) or beside
    airside pavement, the vertical seam is by design.  Road↔road pairs
    stay checked — the road network itself is one continuous surface.
    (Both-groundside-family pairs previously slipped the exactly-one
    test and fired 151 false steps at the CYXY ramp.)"""
    a_road = law_role(way_a) in _ROAD_FAMILY_ROLES
    b_road = law_role(way_b) in _ROAD_FAMILY_ROLES
    if a_road != b_road:
        return True
    return _is_groundside(way_a) != _is_groundside(way_b)


# The step checks enforce vertical continuity only where two shapes actually
# TOUCH (share a boundary).  Beyond this perpendicular contact distance the
# shapes are separated by a GAP (no pavement between them) and a height
# difference is allowed (user 2026-05-28) — do not flag it.  Genuinely adjacent
# pavement shares welded / conformance-inserted vertices (contact ~0); the
# documented real case (a junction edge ~0.3 m alongside a sloped rect) stays
# within this tolerance, while gapped neighbours 2-5 m apart are excluded.
_STEP_CONTACT_TOL_M = 1.0


# _GRADE_VISIBILITY_BUFFER_M now imported from auto_patch.config (single source
# of truth) — see the import block above.


@dataclass
class ShapePairConstraint:
    """One within-shape grade constraint on a vertex pair (the SINGLE source
    of truth for the constrained pair set — consumed by the validator; the
    feasibility oracle that was its other consumer,
    ``tools/attic/grade_feasibility_audit.py``, was retired by the cycle-7.5
    instrument sweep).  The grade law
    is ``|elev_a - elev_b| <= cap * dist`` plus the emit/weld quantization
    envelope, folded into ``allowance`` by :func:`_pair_grade_allowance`
    (``max(route-baked budget, cap*dist)`` — never TIGHTER than the flat cap —
    plus the per-shape quantization noise, :func:`_pair_quant_noise_m`)."""
    way: "Way"
    nid_a: str
    nid_b: str
    xa: float
    ya: float
    ea: float
    xb: float
    yb: float
    eb: float
    dist: float
    cap: float          # decimal grade limit for this pair (role / road / ramp)
    allowance: float    # max(baked, cap*dist) + quant-noise (validator tolerance)
    # SPINE CROWN (part 30): the designed crown target of ``ea − eb``
    # (``grade_law.crown_pair_offset`` over the sidecar drop field); the
    # law is ``|(ea − eb) − offset| ≤ allowance``.  0 for uncrowned pairs.
    offset: float = 0.0
    # THE ROAD CROSS-SECTION (owner ruling RULINGS 2026-08-25g): this pair
    # is a road ring's cross-section (``grade_law.pair_is_transverse``
    # against the ring's own long axis), so its ``cap`` is the road's
    # TRANSVERSE limit and the census reports it in the
    # ``road_cross_section`` family rather than ``within_shape``.  Carried
    # ON the constraint rather than re-derived from ``cap``: a 2 % cap is
    # reachable by other routes through the chain (a narrow-taxi rate, a
    # tightened frontage), so a guess would mint or lose rows either way.
    transverse_road: bool = False


_WELD_HUB_ROLES = frozenset({"junction", "service_junction"})


def _pair_quant_noise_m(way: "Way") -> float:
    """Quantization allowance for a within-shape PAIR on ``way`` — the emit /
    weld micro-step envelope the pair's Δz can carry without meaning a real
    grade defect.

    Per-node ``alt_abs`` emits at 0.01 m, so an all-per-node body pair carries
    only ``ELEV_ROUNDING_NOISE_M`` of rounding.  The coarse envelope
    ``SLOPED_QUAD_ROUNDING_NOISE_M`` (0.1 m) applies to two shape classes whose
    ring edges carry a full decimetre of emit/weld displacement:

    * **Sloped-quad ways** (``altitude_high``/``altitude_low``) emit at 0.1 m
      (``bridges.py`` ``_emit_tunnel_portals`` grade_safety_margin) — a pair
      spanning the high and low corners carries a full 0.1-m round.
    * **Junction-family ways** (the emit WELD HUBS): junction rings are
      rebuilt by the conformance / planarization pass — T-vertex inserts,
      unshared-neighbour-corner inserts, epsilon-wedge welds (see the
      ``[conformance]`` / ``[pav-builder]`` junction logs) — which displace a
      short ring edge by up to the same decimetre.  A junction's short ring
      edge can therefore read a few % over its 1.5 % cap purely from that
      weld displacement (SPLP junction #68: 6 cm over 0.85 m).  On a LONG
      junction pair the absolute 0.1 m adds only a fraction of a % of grade
      headroom, so this loosens only the short weld-artifact edges, not the
      real long-range junction grade the field solver owns."""
    if "altitude_high" in way.tags and "altitude_low" in way.tags:
        return SLOPED_QUAD_ROUNDING_NOISE_M
    if way.tags.get("role") in _WELD_HUB_ROLES:
        return SLOPED_QUAD_ROUNDING_NOISE_M
    return ELEV_ROUNDING_NOISE_M


def _pair_grade_allowance(cap_allow, dist: float, way: "Way") -> float:
    """The within-shape PAIR grade tolerance ``cap × run + allowance`` (the
    symmetric quantization envelope the plane-gradient law already grants —
    ``_check_plane_gradient`` uses ``grade_cap·dist + ELEV_ROUNDING_NOISE_M``).

    ``cap × run`` is the FLAT budget ``cap_allow.flat_cap() · dist``; a
    route-decomposed BAKED allowance (``cap_allow.at`` returning an anisotropic
    ``√((cL·Δs∥)² + (cT·Δs⊥)²)`` budget) is honoured only when it EXCEEDS the
    flat budget (the curve arc-credit case) — never when it is TIGHTER, so an
    at-cap emitted pair never false-flags merely because its route projection
    trimmed the budget below the flat cap (SPJC service_road #461: 5.006 % =
    0.5 mm over the 5 % cap, but the baked budget sat 5 cm below it).  The
    quantization allowance on top is the emit/weld envelope for the shape's
    encoding (``_pair_quant_noise_m``).  The budget core is
    ``grade_law.pair_grade_budget_m`` — THE single formula shared with
    ``grade_graph_validate`` so the two pair-law readers cannot drift."""
    from auto_patch.grade_law import pair_grade_budget_m
    return pair_grade_budget_m(cap_allow, dist) + _pair_quant_noise_m(way)


_SLOPING_RECT_OSM_ROLES = frozenset({
    "primary_parallel", "secondary_parallel", "stub", "cross_connector",
})


def _grade_context_from_osm(ways, nodes, ll_to_m, taxi_axes, seam_nids,
                            max_grade, road_zone=None, routes_m=None,
                            mesh_edges_m=None, interior_zones_m=None):
    """Build the SAME ``grade_graph.GradeContext`` the solver uses, but from the
    emitted OSM — so the grade TEST reads the one shared within-shape LAW
    (``grade_law.classify_pair`` via ``grade_graph.shape_constraints``).  Keys are
    OSM node ids (the ``GradeShape.keys`` the soft-shape reader puts on its ring),
    so the seam / building-step exemptions match by identity.  Mirrors
    ``grade_graph.build_context`` (centerlines from the apt.dat taxi axes, spine-
    less junction cap inherited from the nearest taxi rect, building-pad keys)."""
    from auto_patch import grade_graph as GG
    from auto_patch.config import TAXI_MAX_GRADE

    centerlines = []
    axis_ridx = []
    for entry in (taxi_axes or []):
        poly, cL = entry[0], entry[1]
        if len(poly) < 2:
            continue
        # ``cL`` is a scalar (legacy split axes: one cap for the whole piece)
        # or a per-SEGMENT cap list (exact build_context mirror).
        if isinstance(cL, (list, tuple)):
            seg_caps = list(cL)[:len(poly) - 1]
            if len(seg_caps) < len(poly) - 1:
                pad = seg_caps[-1] if seg_caps else TAXI_MAX_GRADE
                seg_caps += [pad] * (len(poly) - 1 - len(seg_caps))
        else:
            seg_caps = [cL] * (len(poly) - 1)
        # 5th element = the sidecar's IS_SERVICE flag: a truck route is not
        # an aircraft spine, and ``grade_graph._spine_membership`` applies
        # that rule for both readers off this one field (cycle 9).  Absent
        # (legacy sidecar) ⇒ False, i.e. the pre-flag reading.
        centerlines.append(GG.Centerline(
            pts=poly, seg_caps=seg_caps,
            is_service=bool(entry[4]) if len(entry) > 4 else False))
        # 4th element = the BUILDER's route ordinal (identity binding);
        # legacy 3-tuple sidecars fall back to nearest-route below.
        axis_ridx.append(entry[3] if len(entry) > 3 else None)

    # ANISOTROPIC EDGES (gate O4_ANISO_EDGES): chained ROUTES (meter polylines)
    # for the spine-arc decomposition, so the standalone grade TEST uses the SAME
    # anisotropic budget the solver built to (else a curve the solver arc-credited
    # would false-flag here).  Each centerline carries the builder's OWN route
    # binding when the sidecar provides it (identity, like build_context);
    # nearest-route-by-midpoint is only the legacy-sidecar fallback — it
    # mis-binds axes near junctions and the readers then bake different
    # anisotropic budgets for the same pair.  Gate OFF / no routes ⇒ ``routes``
    # empty, ``route_idx`` -1, isotropic (byte-ident).
    # index-preserving (axis ordinals are positional — see routes_m note)
    routes = [GG.RouteChain(pts=list(r)) for r in (routes_m or [])]
    if routes:
        for cl, ridx in zip(centerlines, axis_ridx):
            if ridx is not None:
                cl.route_idx = (int(ridx)
                                if 0 <= int(ridx) < len(routes) else -1)
                continue
            mx = 0.5 * (cl.pts[0][0] + cl.pts[-1][0])
            my = 0.5 * (cl.pts[0][1] + cl.pts[-1][1])
            best_i, best_d = -1, float("inf")
            for ri, r in enumerate(routes):
                _a, d, _f = GG._project(r, mx, my)
                if d < best_d:
                    best_d, best_i = d, ri
            cl.route_idx = best_i

    bld_keys = {nid for w in ways if w.tags.get("role") == "building"
                for nid in w.nids}

    # ── FRONTAGE VERTICES (owner ruling RULINGS 2026-08-21b) ────────────
    # The census half of the apron movement-surface population.  Same LAW
    # function and same soft-role set as ``grade_graph.build_context``
    # (``grade_law.frontage_vertex_keys`` / ``FRONTAGE_SOFT_ROLES``), read on
    # emitted node IDENTITY — never a proximity join — so the census and the
    # solver bake enumerate the same apron pairs.
    from auto_patch import grade_law as _GL_F
    _soft_front_nids = {nid for w in ways
                        if w.tags.get("role") in _GL_F.FRONTAGE_SOFT_ROLES
                        for nid in w.nids}
    _bld_rings = [(w.nids[:-1] if (len(w.nids) > 1
                                   and w.nids[0] == w.nids[-1]) else w.nids)
                  for w in ways if w.tags.get("role") == "building"]
    frontage_keys = (_GL_F.frontage_vertex_keys(_bld_rings, _soft_front_nids)
                     if _soft_front_nids else set())

    rect_cap_at: dict = {}
    for w in ways:
        if w.tags.get("role") not in _SLOPING_RECT_OSM_ROLES:
            continue
        cap = _role_grade_limit(w, max_grade)
        if cap is None:
            continue
        for nid in w.nids:
            if rect_cap_at.get(nid, -1.0) < cap:
                rect_cap_at[nid] = cap

    def _inherited(shape):
        best = None
        for k in shape.keys:
            c = rect_cap_at.get(k)
            if c is not None and (best is None or c > best):
                best = c
        return best if best is not None else TAXI_MAX_GRADE

    # Taxi-ROUTE pavement zone (O4_APRON_ROUTE_CONTACT), mirroring
    # ``grade_graph.build_context``: an apron ring edge welded to a taxi-route
    # pavement is a contact ramp and earns the taxi cap in its climbing
    # direction.  This reader previously never built the zone, so it refused
    # contact budgets the solver lawfully granted (SPJC apron #188:
    # ring-adjacent 1.46 % flagged against the 1.17 % blend while the solver
    # graded the contact at 1.5 %).
    route_zone = None
    if GG.APRON_ROUTE_CONTACT:
        try:
            from shapely.geometry import Polygon as _RzPoly
            from shapely.ops import unary_union as _rz_union
            from shapely.prepared import prep as _rz_prep
            _route_polys = []
            for w in ways:
                if w.tags.get("role") not in (
                        "junction", "primary_parallel",
                        "secondary_parallel", "stub", "cross_connector"):
                    continue
                ring = [ll_to_m(*nodes[nid]) for nid in w.nids
                        if nid in nodes]
                if len(ring) >= 3:
                    _route_polys.append(_RzPoly(ring).buffer(0))
            if _route_polys:
                route_zone = _rz_prep(_rz_union(_route_polys)
                                      .buffer(GG._ROUTE_CONTACT_TOL_M))
        except Exception:
            route_zone = None

    # ── THE RUNWAY-STRIP KEEP-OUT (spec AMENDMENT A4.2; owner ruling
    # RULINGS 2026-08-21d, WIRED 2026-08-24) — the census half.
    # SAME LAW FUNCTION as the solver's (``grade_law.runway_strip_wall_
    # keepout_rings``, reached here through ``_runway_strip_keepout_rings``
    # over the EMITTED runway rings grouped by ref), so both readers
    # exclude the identical ground.  Neither side had it assigned before
    # today: the field was declared, documented and never filled.
    strip_keepout = None
    try:
        _sk_rings = _runway_strip_keepout_rings(ways, nodes, ll_to_m)
        if _sk_rings:
            from shapely.geometry import Polygon as _SkPoly
            from shapely.ops import unary_union as _sk_union
            from shapely.prepared import prep as _sk_prep
            _sk_block = _sk_union([_SkPoly(r) for r in _sk_rings
                                   if len(r) >= 3])
            if _sk_block is not None and not _sk_block.is_empty:
                strip_keepout = _sk_prep(_sk_block)
    except Exception:
        strip_keepout = None

    return GG.GradeContext(
        centerlines=centerlines,
        routes=routes,
        seam_keys=frozenset(seam_nids or ()),
        inherited_junction_cap=_inherited,
        building_keys=frozenset(bld_keys),
        frontage_keys=frozenset(frontage_keys),
        strip_keepout=strip_keepout,
        # ── THE BACK-EDGE ZONES (owner ruling RULINGS 2026-08-24) ────
        # The sidecar's ``interior_zones`` rings, already in this
        # reader's metre frame.  ``grade_graph`` owns the predicate for
        # BOTH readers (this context flows straight into
        # ``shape_constraints``), so the census cannot spell the
        # back-edge test differently from the bake — it does not spell
        # it at all.
        interior_zones=tuple(
            tuple((float(x), float(y)) for (x, y) in ring)
            for ring in (interior_zones_m or []) if len(ring) >= 3),
        corridor_lines=GG.centerline_geometries(centerlines),
        road_zone=road_zone,
        route_zone=route_zone,
        # EXACT-MESH sidecar: the solver's junction mesh, consumed 1:1
        # (emit-time ring repairs otherwise make this reader's Delaunay
        # differ from the one the solver graded to).
        mesh_edges_exact=(GG.MeshEdgesExact(mesh_edges_m)
                          if mesh_edges_m else None))


def _soft_grade_shape(w: "Way", role0: str, pts, pnids):
    """The ``grade_graph.GradeShape`` for ONE soft airside ring.

    ONE construction, shared by both consumers inside
    :func:`iter_shape_grade_constraints` (the re-bake path and the
    baked path's ring-edge floor) — the law tags below must never
    differ between them.

    THE FAN-RAMP LAW (owner RULINGS 21f0980), the census half: the flag
    goes into the SAME ``GradeShape`` the solver builds, so both sides
    reach the zone cap through ONE function
    (``grade_graph._body_cap_unbounded``) rather than each carrying its
    own idea of where the ramp is.  A patch predating the law has no
    tag and is judged as before.
    """
    from auto_patch import grade_graph as _GG
    return _GG.GradeShape(
        role=role0, ring=[(p[0], p[1]) for p in pts], keys=list(pnids),
        fan_ramp_zone=(w.tags.get("o4_grade_law") == _FAN_RAMP_LAW),
        adopts_apron_grade=(w.tags.get("o4_grade_law") == "apron"),
        adopts_taxi_grade=(w.tags.get("o4_grade_law") == "taxi"),
        adopted_taxi_letter=(w.tags.get("code_letter")
                             if w.tags.get("o4_grade_law") == "taxi"
                             else None),
        lateral_cap=_lateral_cap_tag(w))


def iter_shape_grade_constraints(
        ways: List[Way],
        nodes: Dict[str, Tuple[float, float]],
        ll_to_m,
        max_grade: float,
        seam_nids: Optional[set] = None,
        taxi_axes: Optional[list] = None,
        routes_ll: Optional[list] = None,
        mesh_edges_m: Optional[list] = None,
        crown_by_nid: Optional[Dict[str, float]] = None,
        crown_centerline_nids: Optional[set] = None,
        pair_caps_ll: Optional[list] = None,
        interior_zones_m: Optional[list] = None,
        ) -> "list[ShapePairConstraint]":
    """Yield every within-shape vertex-pair the grade check constrains.

    SINGLE SOURCE OF TRUTH for "which pairs are graded" — ``_check_within_shape``
    (the validator) and the feasibility oracle both consume this so the
    solver-target and the audit can never drift (W1 graph lockstep).  Encodes:
    triangle = all 3 edges; 4+ = mutually-visible pairs (apron/junction gated by
    ``_polygon_visibility``; convex rects all-pair) within the ROUTE-FIELD local
    window (ring edges always kept); per-axis junction/apron allowance with the
    cross-axis diagonal skip; seam-anchored pairs dropped (DEM controls); road-
    frontage and back-edge-ramp relaxed caps.

    "Ring edges always kept" binds the BAKED path too (R19-5): a soft shape
    with sidecar ``pair_caps`` coverage constrains the baked pairs AND every
    ring edge the bake missed, the latter at the law's own ring-only budget.
    The bake selects which BODY pairs were enforced; it never removes a
    physical boundary edge from the domain.
    """
    seam_nids = seam_nids or set()
    out: List[ShapePairConstraint] = []
    # ROAD-FRONTAGE zone (config.ROAD_FRONTAGE_TOL_M): an apron/junction
    # pair with BOTH endpoints welded to a service-road carve carries the
    # ROAD's 5 % law, not the shape's 1.5 % — the carve corners sit ON
    # the host ring, so the host's law would otherwise regulate the
    # road's own descent (CYXY road #30: the apron-ring frontage edge
    # read the road's drop as a 3.13 % apron violation; the squeeze is
    # hard-anchored, so no legal apron value exists).  VALIDATOR-ONLY:
    # the solver still solves at the strict cap (see config note).
    road_zone = None
    try:
        from shapely.geometry import Point as _FzPt, Polygon as _FzPoly
        from shapely.ops import unary_union as _fz_union
        from shapely.prepared import prep as _fz_prep
        _fz_polys = []
        for w in ways:
            if w.tags.get("role") not in _ROAD_FAMILY_ROLES:
                continue
            ring = [ll_to_m(*nodes[nid]) for nid in w.nids
                    if nid in nodes]
            if len(ring) >= 3:
                _fz_polys.append(_FzPoly(ring).buffer(0))
        if _fz_polys:
            road_zone = _fz_prep(
                _fz_union(_fz_polys).buffer(ROAD_FRONTAGE_TOL_M))
    except Exception:
        road_zone = None
    # THE LAW reader for soft airside shapes (apron / junction / service_junction):
    # build the shared grade context once and route every soft shape through
    # ``grade_graph.shape_constraints`` (→ ``grade_law.classify_pair``), so the
    # test selects the SAME within-shape pairs at the SAME base caps the solver
    # enforces.  The road-frontage / back-edge relaxations below stay a test-only
    # layer ON TOP (they only RELAX a cap).  Non-soft shapes (rects / runway /
    # terminal) keep their per-role all-pair handling further down.
    from auto_patch import grade_graph as _GG
    # INDEX-PRESERVING: axis route ordinals index this list positionally, so a
    # degenerate route must keep its slot (never filter — that shifts every
    # later ordinal).  A <2-point route becomes a 2-point degenerate chain.
    routes_m = ([([(ll_to_m(la, lo)) for (la, lo) in pts] if pts
                  and len(pts) >= 2 else
                  [ll_to_m(*pts[0]), ll_to_m(*pts[0])] if pts else
                  [(0.0, 0.0), (0.0, 0.0)])
                 for pts in routes_ll]
                if routes_ll else None)
    _law_ctx = _grade_context_from_osm(ways, nodes, ll_to_m, taxi_axes,
                                       seam_nids, max_grade, road_zone=road_zone,
                                       routes_m=routes_m,
                                       mesh_edges_m=mesh_edges_m,
                                       interior_zones_m=interior_zones_m)
    # SPINE CROWN (part 30): per-nid designed drops (sidecar field);
    # every pair's law re-centres on grade_law.crown_pair_offset.
    from auto_patch.grade_law import crown_pair_offset as _crown_off  # noqa: F401
    from auto_patch.grade_law import (
        crown_pair_offset_clamped as _crown_off_clamped)
    # AN UNDECLARED CROWN ENDPOINT IS UNKNOWN, NOT ON THE RIDGE.  The tally
    # below ACCUMULATES across this builder's several calls per census and is
    # reset by ``run_checks`` — the one entry every law frame goes through —
    # so a reader that prints it after the run sees that run's whole count.
    crown_by_nid = crown_by_nid or {}
    crown_centerline_nids = crown_centerline_nids or set()
    # BAKED PAIR CAPS (sidecar ``pair_caps``, 2026-07-17): the exact pair
    # selection + metre allowances the solver's final projection enforced
    # (``verification.lockstep_pair_caps_ll``).  When a SOFT shape has
    # coverage, constrain exactly these pairs — re-baking from the
    # emitted ring diverges: post-projection vertex inserts shorten the
    # spans (tighter anisotropic credit than was lawfully enforced) and
    # the OSM-side context can select pairs the law-side bake never did.
    # ROW SHAPE (2026-08-21): ``[[la,lo],[la,lo],budget]`` grew a fourth
    # element, the FAMILY TAG (``grade_graph.edge_family_name``, spec
    # ``apron-within-shape-population`` §7).  Read POSITIONALLY so a patch
    # from either side of that change is consumed identically.
    _pair_cap_map: Dict[tuple, float] = {}
    for _entry in (pair_caps_ll or []):
        (_pla, _plo), (_plb, _plo2), _pcap = (
            _entry[0], _entry[1], _entry[2])
        _ka = (round(float(_pla), 7), round(float(_plo), 7))
        _kb = (round(float(_plb), 7), round(float(_plo2), 7))
        _pk = (min(_ka, _kb), max(_ka, _kb))
        _pcap = abs(float(_pcap))
        if _pk not in _pair_cap_map or _pcap < _pair_cap_map[_pk]:
            _pair_cap_map[_pk] = _pcap
    _SOFT_ROLES = _GG.SOFT_VISIBILITY_ROLES
    for w in ways:
        # DECLARED TERRAIN PLATES (spec docs/specs/
        # tunnel-trench-law-and-basin-floor-spec.md §1.2): a basin/tunnel
        # trench floor or rim plate is FLAT-BY-LAW TERRAIN whose
        # elevations the trench law set from the facility's own declared
        # floor and rim.  It carries no taxiway cap, so its within-shape
        # pairs price at None — the declared geometry, not the 1.5 %
        # fall-through this role reached only because it has no
        # ``ROLE_GRADE_LIMITS`` entry.  The plate stays fully visible to
        # the CROSS-SHAPE step law, which prices its contacts against the
        # facility's declared floor→rim drop (``_basin_declared_drop``) —
        # that is why this is not a ``ROLE_GRADE_LIMITS[role] = None``
        # entry, which would take it off the step checks too.
        if law_role(w) in _DECLARED_PLATE_ROLES:
            continue
        grade_cap = _role_grade_limit(w, max_grade)
        if grade_cap is None:
            continue  # skip ROLE_GRADE_LIMITS[role] is None
        pts: List[Tuple[float, float, float, bool]] = []
        pnids: List[str] = []
        for k, nid in enumerate(w.nids[:-1] if (len(w.nids) > 1
                                and w.nids[0] == w.nids[-1])
                                else w.nids):
            if nid not in nodes:
                continue
            lat, lon = nodes[nid]
            x, y = ll_to_m(lat, lon)
            e = w.elevs[k]
            if e is None:
                continue
            pts.append((x, y, e, nid in seam_nids))
            pnids.append(nid)
        n = len(pts)
        if n < 3:
            continue
        # ── SOFT airside shapes → THE LAW (one shared within-shape rule set) ──
        role0 = w.tags.get("role")
        # ── THE ROAD CROSS-SECTION (owner ruling RULINGS 2026-08-25g) ────
        # THIS RING'S OWN AXIS, once per way, through THE law's reader
        # (``grade_law.long_axis_of_points`` — the same function the
        # solver's ``shape_constraints`` and the lateral-contiguity
        # station walk read a road's direction with).  ``None`` for every
        # non-road way and with the law gated off, which is what makes
        # every branch below a no-op on those.
        _road_axis = None
        if _ROAD_XSECTION_LAW and law_role(w) in _ROAD_FAMILY_ROLES:
            _ax = _long_axis_of_points([(p[0], p[1]) for p in pts])
            _road_axis = _ax[0] if _ax else None

        def _xsec(ia: int, ib: int) -> bool:
            """Is the pair ``pts[ia] → pts[ib]`` this road's cross-section?"""
            if _road_axis is None:
                return False
            return _pair_is_transverse(_road_axis,
                                       pts[ib][0] - pts[ia][0],
                                       pts[ib][1] - pts[ia][1])

        def _xsec_allowance(d: float, cap_l: float):
            """``(cap, allowance)`` for a CROSS-SECTION pair whose
            LONGITUDINAL cap is ``cap_l``.

            ``cap_l`` is the caller's — the law's own ``flat_cap()`` where
            the pair went through ``classify_pair``, the role cap on the
            sidecar-lockstep path where it did not.  It is never re-read
            from the role here: the cross-section cap is a pure function
            OF the longitudinal cap (``grade_law.road_cross_section_cap``,
            which is ``min``-shaped), so a pair the chain already
            tightened — a frontage chord at 1 % inside a road ring — keeps
            its own cap and is never LOOSENED to 2 % by this branch.

            THE BAKED BUDGET DOES NOT APPLY ACROSS A ROAD, and that is
            the whole of the 25g fix on this side.  Every other pair's
            allowance is ``max(baked, cap·dist)`` — "never TIGHTER than
            the flat cap" — because the baked budget is an anisotropic
            TRAVEL credit: a pair spanning a curve earns its along-route
            arc.  On a pair that runs ACROSS the road there is no travel
            to credit, and that ``max`` against the 8 % longitudinal cap
            is exactly why the 2 % cross-section limit was generated and
            never held (the KAFW N-1 population: 2-8 % transverse rows,
            under the chord cap, over the cross-section limit, priced by
            nothing).  So a cross-section pair is judged at ``cT·dist``
            plus the shape's own emit/weld quantization envelope — the
            same envelope every other family gets, no more and no less.
            """
            cap = _road_xsection_cap(cap_l)
            return cap, cap * d + _pair_quant_noise_m(w)

        if role0 in _SOFT_ROLES and _pair_cap_map:
            # LOCKSTEP CONSUMPTION: constrain exactly the solver-baked
            # pairs of this ring (matched by rounded lat/lon endpoint
            # keys).  A ring with ZERO matches falls through to the
            # re-bake path below (no bake ⇒ old law).
            _llk = [(round(nodes[pnids[k]][0], 7),
                     round(nodes[pnids[k]][1], 7)) for k in range(n)]
            _matched = []
            for _ia in range(n):
                for _ib in range(_ia + 1, n):
                    _pk = (min(_llk[_ia], _llk[_ib]),
                           max(_llk[_ia], _llk[_ib]))
                    _cap_m = _pair_cap_map.get(_pk)
                    if _cap_m is not None:
                        _matched.append((_ia, _ib, _cap_m))
            if _matched:
                for (_ia, _ib, _cap_m) in _matched:
                    xi, yi, ei, _si = pts[_ia]
                    xj, yj, ej, _sj = pts[_ib]
                    d = math.hypot(xi - xj, yi - yj)
                    if d < 0.5:
                        continue
                    # Same envelope structure as _pair_grade_allowance:
                    # the baked budget, floored at the flat cap (the
                    # pair-law MAX), plus the shape's quantization
                    # noise.
                    _off, _unk = _crown_off_clamped(
                        crown_by_nid.get(pnids[_ia]),
                        crown_by_nid.get(pnids[_ib]), ei - ej)
                    if _unk:
                        _CROWN_UNKNOWN_PAIRS[w.tags.get("role") or "?"] += 1
                    _tv = _xsec(_ia, _ib)
                    if _tv:
                        _pcap, _pallow = _xsec_allowance(d, grade_cap)
                    else:
                        _pcap = grade_cap
                        _pallow = (max(_cap_m, grade_cap * d)
                                   + _pair_quant_noise_m(w))
                    out.append(ShapePairConstraint(
                        way=w, nid_a=pnids[_ia], nid_b=pnids[_ib],
                        xa=xi, ya=yi, ea=ei, xb=xj, yb=yj, eb=ej,
                        dist=d, cap=_pcap,
                        allowance=_pallow,
                        offset=_off, transverse_road=_tv))
                # ── RING-EDGE FLOOR (R19-5) ─────────────────────────
                # The bake is a PAIR SELECTION, not a domain: a vertex
                # absent from it (post-projection insert, weld) used to
                # take its whole ring edge out of the constrained-pair
                # domain, so the census carried NO ROW for it however
                # steep it was — this docstring's "ring edges always
                # kept" was false exactly here.  Measured on the owner's
                # 2026-08-12 HECA artifact: 628 ring edges of graded
                # soft shapes silently unconstrained, including apron
                # -10629's 148.4 % over 8.49 m and 55.6 % over 22.39 m.
                # The physical boundary edge is the one pair no
                # selection may remove, so every ring edge the bake
                # missed is re-added at THE LAW's own budget — the
                # ring-only ``shape_constraints`` pass, the same
                # ``classify_pair`` the no-bake path below uses (its
                # seam / min-distance / relaxation rulings therefore
                # still decide; only the bake's silent subtraction is
                # gone).
                _mk = {(min(_ia, _ib), max(_ia, _ib))
                       for (_ia, _ib, _c) in _matched}
                _ring_gs = _soft_grade_shape(w, role0, pts, pnids)
                _idx = {pnids[k]: k for k in range(n)}
                for (ka, kb, cap) in _GG.shape_constraints(
                        _ring_gs, _law_ctx, ring_only=True).edges:
                    ia = _idx.get(ka)
                    ib = _idx.get(kb)
                    if ia is None or ib is None:
                        continue
                    if (min(ia, ib), max(ia, ib)) in _mk:
                        continue
                    xi, yi, ei, _si = pts[ia]
                    xj, yj, ej, _sj = pts[ib]
                    d = math.hypot(xi - xj, yi - yj)
                    if d < 0.5:
                        continue
                    _off, _unk = _crown_off_clamped(
                        crown_by_nid.get(pnids[ia]),
                        crown_by_nid.get(pnids[ib]), ei - ej)
                    if _unk:
                        _CROWN_UNKNOWN_PAIRS[w.tags.get("role") or "?"] += 1
                    _tv = _xsec(ia, ib)
                    if _tv:
                        _pcap, _pallow = _xsec_allowance(d, cap.flat_cap())
                    else:
                        _pcap = cap.flat_cap()
                        _pallow = _pair_grade_allowance(cap, d, w)
                    out.append(ShapePairConstraint(
                        way=w, nid_a=pnids[ia], nid_b=pnids[ib],
                        xa=xi, ya=yi, ea=ei, xb=xj, yb=yj, eb=ej,
                        dist=d, cap=_pcap,
                        allowance=_pallow,
                        offset=_off, transverse_road=_tv))
                continue
        if role0 in _SOFT_ROLES:
            gs = _soft_grade_shape(w, role0, pts, pnids)
            sc = _GG.shape_constraints(gs, _law_ctx)
            idx = {pnids[k]: k for k in range(n)}
            for (ka, kb, cap) in sc.edges:
                ia = idx.get(ka)
                ib = idx.get(kb)
                if ia is None or ib is None:
                    continue
                xi, yi, ei, _si = pts[ia]
                xj, yj, ej, _sj = pts[ib]
                d = math.hypot(xi - xj, yi - yj)
                if d < 0.5:
                    continue
                # ``cap`` comes ENTIRELY from the shared law (incl. the road-
                # frontage relaxation).  No test-only back-edge relaxation: the
                # live model (TAXI_SLACK_TERMINALS) regulates the apron strictly
                # and the back-edge-ramp model it superseded is gone — a steep
                # building-facing apron pair is a real solver failure to flag.
                _off, _unk = _crown_off_clamped(
                    crown_by_nid.get(pnids[ia]), crown_by_nid.get(pnids[ib]),
                    ei - ej)
                if _unk:
                    _CROWN_UNKNOWN_PAIRS[w.tags.get("role") or "?"] += 1
                _tv = _xsec(ia, ib)
                if _tv:
                    _pcap, _pallow = _xsec_allowance(d, cap.flat_cap())
                else:
                    _pcap = cap.flat_cap()
                    _pallow = _pair_grade_allowance(cap, d, w)
                out.append(ShapePairConstraint(
                    way=w, nid_a=pnids[ia], nid_b=pnids[ib],
                    xa=xi, ya=yi, ea=ei, xb=xj, yb=yj, eb=ej,
                    dist=d, cap=_pcap,
                    allowance=_pallow,
                    offset=_off, transverse_road=_tv))
            continue
        # PLANE shapes (rects / runway / terminal) → the SAME law: all vertex
        # pairs at the role cap, via grade_graph.plane_constraints (the single
        # rule source for every shape).  classify_pair owns the seam skip, the
        # min-pair-distance and the road-carve relaxation, so the old per-axis /
        # triangle / visibility branches here are gone.
        # ``o4_single_poly`` marks a DE-SEGMENTED runway ring so
        # ``plane_constraints`` scopes its within-shape pairs to LATERAL +
        # same/adjacent-station (user ruling 2026-07-08); a segmented rect
        # carries no marker and keeps its full all-pair check.
        gs = _GG.GradeShape(role=role0, ring=[(p[0], p[1]) for p in pts],
                            keys=list(pnids),
                            single_poly=(w.tags.get("o4_single_poly") == "1"))
        sc = _GG.plane_constraints(gs, _law_ctx, grade_cap)
        idx = {pnids[k]: k for k in range(n)}
        _is_runway = role0 in ("runway", "runway_crossing")
        for (ka, kb, capp) in sc.edges:
            ia = idx.get(ka)
            ib = idx.get(kb)
            if ia is None or ib is None:
                continue
            # CROWN CENTERLINE skip (Phase 0 hotfix): a runway pair touching a
            # crown-centerline node lies on the ridge — its longitudinal grade
            # is the SPINE PROFILE check's domain and its lateral crown is
            # sub-cap by design; a cross-station diagonal to it conflates the
            # two.  Same exemption class as the crown_spine breakline.
            if _is_runway and (ka in crown_centerline_nids
                               or kb in crown_centerline_nids):
                continue
            xi, yi, ei, _sa = pts[ia]
            xj, yj, ej, _sb = pts[ib]
            d = math.hypot(xi - xj, yi - yj)
            _off, _unk = _crown_off_clamped(
                crown_by_nid.get(pnids[ia]), crown_by_nid.get(pnids[ib]),
                ei - ej)
            if _unk:
                _CROWN_UNKNOWN_PAIRS[w.tags.get("role") or "?"] += 1
            out.append(ShapePairConstraint(
                way=w, nid_a=pnids[ia], nid_b=pnids[ib],
                xa=xi, ya=yi, ea=ei, xb=xj, yb=yj, eb=ej,
                dist=d, cap=capp.flat_cap(),
                allowance=_pair_grade_allowance(capp, d, w),
                offset=_off))
    return out


def _check_runway_end_skirt_edges(ways: List[Way],
                                  nodes: Dict[str, Tuple[float, float]],
                                  ll_to_m) -> List[Violation]:
    """DEM-free skirt-law reader on the EMITTED patch: every ring edge
    of a ``runway_end_skirt`` way must stay within the law's maximum
    down-grade (``grade_law.RUNWAY_END_SKIRT_MAX_DOWN_GRADE``).  By
    construction the skirt surface never exceeds it in ANY direction —
    band rows are level and the descent is rate-limited — so a steeper
    emitted edge means the patch was corrupted after emission.  The
    full DEM-aware floor/curvature law lives in
    ``verification.check_runway_end_skirt``; this is the always-on
    lockstep reader for emitted patches."""
    from auto_patch.grade_law import RUNWAY_END_SKIRT_MAX_DOWN_GRADE
    # Skirt altitudes emit at 0.1 m quantization — a pair carries up to
    # ~0.1 m of rounding; padded slightly for float noise.
    skirt_edge_noise_m = 0.15
    # LIFT-ONLY tolerance (2026-07-07): the skirt surface is
    # ``max(analytic_floor, DEM)`` per vertex (clearance._skirt_lift_alt
    # — the fill-only / flat-shadow convention: a fill never cuts).  A
    # band that TRIGGERS on falling terrain can still SPAN a DEM bump
    # that sits above the floor; that vertex lifts to the DEM instead of
    # being graded DOWN to the floor.  So a band row is no longer level,
    # and the surface can descend from a lifted bump back to the floor
    # FASTER than the down-grade cap — this is LAWFUL (the law bounds how
    # far BELOW the floor the surface may drop, not how it rides an
    # existing bump back up; a vertex at/above the floor descending no
    # lower than the floor is compliant).  DEM-free we cannot read the
    # floor, but we CAN tell the two apart by SHAPE: a lift raises a
    # vertex ABOVE its ring neighbours (a peak); post-emission corruption
    # DROPS a vertex below its neighbours (a valley).  So an over-steep
    # edge is flagged ONLY when its HIGHER endpoint is NOT a local lift
    # peak — i.e. the steepness comes from the lower vertex dropping, the
    # one signature ``max(floor, DEM)`` can never produce.  The DEM-aware
    # floor/curvature law (verification.check_runway_end_skirt) remains
    # the full below-floor check.

    def _ring_neighbour_elevs(w, i):
        """Elevations of the two ring-adjacent vertices of index ``i``
        on the closed way ``w`` (its ring's last nid repeats the first)."""
        m = len(w.nids) - 1  # distinct vertices (ring closes)
        if m < 2:
            return []
        elevs = []
        for j in (i - 1, i + 1):
            k = j % m
            e = w.elevs[k] if k < len(w.elevs) else None
            if e is not None:
                elevs.append(float(e))
        return elevs

    out: List[Violation] = []
    for w in ways:
        if w.ref != "runway_end_skirt":
            continue
        ring = w.nids
        for i in range(len(ring) - 1):
            nid_a, nid_b = ring[i], ring[i + 1]
            if nid_a not in nodes or nid_b not in nodes:
                continue
            ea = w.elevs[i] if i < len(w.elevs) else None
            eb = w.elevs[i + 1] if i + 1 < len(w.elevs) else None
            if ea is None or eb is None:
                continue
            xa, ya = ll_to_m(*nodes[nid_a])
            xb, yb = ll_to_m(*nodes[nid_b])
            dist = math.hypot(xb - xa, yb - ya)
            if dist < 0.5:
                continue
            de = abs(float(ea) - float(eb))
            allowance = (RUNWAY_END_SKIRT_MAX_DOWN_GRADE * dist
                         + skirt_edge_noise_m)
            if de <= allowance:
                continue
            # Lift check: if the HIGHER endpoint is strictly above BOTH
            # its ring neighbours, it is a lifted DEM bump and the steep
            # descent off it is lawful (max(floor, DEM) riding terrain).
            hi_idx = i if float(ea) >= float(eb) else i + 1
            hi_elev = max(float(ea), float(eb))
            neigh = _ring_neighbour_elevs(w, hi_idx)
            if neigh and all(hi_elev > ne + skirt_edge_noise_m
                             for ne in neigh):
                continue
            # END-CAP exclusion (CYXY diagnosis 2026-07-26): the skirt
            # ring is two station rows; the short edges CLOSING the ring
            # run ACROSS the band, where the surface is pure DEM drape —
            # the 5 % law bounds the descent ALONG the rows, not the
            # lateral terrain.  An edge near-perpendicular to BOTH its
            # ring neighbours is such an end-cap/row-transition edge and
            # is exempt; along-row steps (the real dropped-vertex class,
            # KCLT #845) stay flagged because they parallel their
            # neighbours.  Rings under 6 distinct vertices have no row
            # structure to protect (a bare quad reads all-perpendicular),
            # so they keep the full check.
            m_ring = len(ring) - 1
            if m_ring >= 6 and dist > 1e-6:
                ex, ey = (xb - xa) / dist, (yb - ya) / dist
                perp_both = True
                for pj, qj in (((i - 1) % m_ring, i),
                               ((i + 1) % m_ring, (i + 2) % m_ring)):
                    pn, qn = ring[pj], ring[qj]
                    if pn not in nodes or qn not in nodes:
                        perp_both = False
                        break
                    px, py = ll_to_m(*nodes[pn])
                    qx, qy = ll_to_m(*nodes[qn])
                    nlen = math.hypot(qx - px, qy - py)
                    if nlen < 0.5:
                        perp_both = False
                        break
                    if abs(ex * (qx - px) / nlen
                           + ey * (qy - py) / nlen) > 0.35:
                        perp_both = False
                        break
                if perp_both:
                    continue
            grade = de / dist
            out.append(Violation(
                grade_pct=grade * 100,
                excess_pct=(grade - RUNWAY_END_SKIRT_MAX_DOWN_GRADE) * 100,
                distance_m=dist,
                de_m=de,
                way_a=w, way_b=w,
                pt_a=(xa, ya), pt_b=(xb, yb),
                elev_a=float(ea), elev_b=float(eb)))
    out.sort(key=lambda v: -v.excess_pct)
    return out


def _check_adjacent_ground_edges(ways: List[Way],
                                 nodes: Dict[str, Tuple[float, float]],
                                 ll_to_m) -> List[Violation]:
    """DEM-free TEAR sentinel on the EMITTED patch: an ``adjacent_ground``
    graded-strip must not carry a near-vertical SUB-METRE edge (a clip /
    weld discontinuity — the epsilon-wedge corruption class).

    Why not a corridor-grade check (the skirt's approach).  The runway-end
    skirt is a fill-ONLY ramp with a single bounded down-grade, so its
    OSM-side reader can flag any over-steep edge that is not a lawful DEM
    lift-peak (``_check_runway_end_skirt_edges``).  A LATERAL band is a
    two-directional corridor whose FILL rides ``max(floor, DEM)`` and whose
    CUT rides the ceiling: it lawfully follows terrain UP a bump (a peak)
    AND down a pit (a valley) AND along a monotonic hillside — DEM-free NONE
    of those are distinguishable from a real over-steep edge, so a
    corridor-grade check false-flags every terrain-riding band edge
    (measured: ~200-1100 at CYXY/HECA, nearly all lawful).  The DEM-aware
    corridor law — coverage + floor/ceiling — is
    ``verification.check_adjacent_ground`` (the authoritative reader); the
    ONE thing a DEM-free reader CAN prove wrong here is a TEAR: a band edge
    far shorter than the emitter's station step carrying an altitude jump no
    lawful graded slope produces, i.e. a vertical face the clip/weld
    introduced.  Real band edges span ~one station step (5 m) or the
    pavement gap (~1 m); a sub-gap edge with a metre-plus jump is a tear.

    Returns ``Violation`` rows (``grade_pct`` = the tear's near-vertical
    grade), worst-jump first — the LATERAL twin of
    ``_check_runway_end_skirt_edges``, narrowed to what DEM-free is sound."""
    from auto_patch.config import CLEARANCE_STATION_STEP_M
    # A lawful band edge spans ~a station step; anything under a fifth of it
    # is a clip sliver, not a graded row.  A jump exceeding this over so
    # short a span is a vertical face (> ~100 % grade) — no lawful ≤5 %
    # corridor slope reaches it.
    tear_max_edge_m = 0.2 * CLEARANCE_STATION_STEP_M      # 1.0 m
    tear_min_jump_m = 1.0

    # WALL-SPANNED EXEMPTION (no-stacked-nodes unit, 2026-07-19): a
    # strip edge whose BOTH endpoints a ``retaining_wall`` way
    # references is the side of a deliberate wall wedge (the strip
    # retreat's end taper) — the face fills the jump; it is not a bare
    # clip tear.  Same reading as the strip-SEAM check's exemption.
    wall_nid_ways: Dict[str, set] = defaultdict(set)
    for wi, w in enumerate(ways):
        if w.tags.get("role") == "retaining_wall":
            for nid in w.nids:
                wall_nid_ways[nid].add(wi)

    out: List[Violation] = []
    for w in ways:
        if w.ref != "adjacent_ground":
            continue
        ring = w.nids
        for i in range(len(ring) - 1):
            nid_a, nid_b = ring[i], ring[i + 1]
            if nid_a not in nodes or nid_b not in nodes:
                continue
            ea = w.elevs[i] if i < len(w.elevs) else None
            eb = w.elevs[i + 1] if i + 1 < len(w.elevs) else None
            if ea is None or eb is None:
                continue
            xa, ya = ll_to_m(*nodes[nid_a])
            xb, yb = ll_to_m(*nodes[nid_b])
            dist = math.hypot(xb - xa, yb - ya)
            de = abs(float(ea) - float(eb))
            if not (dist < tear_max_edge_m and de > tear_min_jump_m):
                continue
            if wall_nid_ways.get(nid_a, set()) & wall_nid_ways.get(
                    nid_b, set()):
                continue  # side of a deliberate retaining_wall wedge
            grade = de / dist if dist > 1e-9 else float("inf")
            out.append(Violation(
                grade_pct=grade * 100,
                excess_pct=grade * 100,
                distance_m=dist,
                de_m=de,
                way_a=w, way_b=w,
                pt_a=(xa, ya), pt_b=(xb, yb),
                elev_a=float(ea), elev_b=float(eb)))
    out.sort(key=lambda v: -v.de_m)
    return out


# ── Cross-shape graded-strip SEAM tear thresholds ───────────────
# MOVED (spec seam-continuity-v2 §1) to ``src/auto_patch/
# strip_seam_law.py`` — the constants, the graded-domain index, the
# open-ground predicate and the wall-straddle predicate now have ONE
# home that ``src/`` can read, so a generation-binding strip-seam law
# and this validator are lockstep by construction instead of by
# comment.  Imported at the top of this file; nothing here is a
# second copy.


# ── RUNWAY-STRIP WALL LAW (owner ruling 2026-08-01) ─────────────
# "Retaining walls are NEVER lawful at a runway edge — runway
# surroundings must grade away smoothly" (docs/RULINGS.md, runway-edge
# terrain law).  The emitter half is
# ``adjacent_ground.runway_strip_wall_keepout``; BOTH halves build the
# footprint from ``grade_law.runway_strip_wall_keepout_rings`` over the
# same emitted runway rings grouped by ``ref`` — lockstep by
# construction.  A wall vertex this far INSIDE a strip footprint is a
# violation; the margin absorbs the emitted-coordinate quantum so a face
# the emitter clipped AT the strip boundary does not flag on its own
# boundary vertices.
_WALL_STRIP_MARGIN_M = 0.05


def _point_in_rect_ring(px: float, py: float,
                        ring: List[Tuple[float, float]],
                        margin: float) -> bool:
    """Is ``(px, py)`` at least ``margin`` inside the PARALLELOGRAM closed
    ring ``ring`` (5 points, last repeating the first)?

    ``runway_strip_wall_keepout_rings`` emits rectangles, so the inset is
    exact in metres along both edge directions — which a centroid-scaling
    inset is not (a 3 km × 150 m strip would lose 50× more width than
    length).  Any other ring shape falls back to the even-odd test with no
    inset (honest: the law emits no such ring today)."""
    if len(ring) != 5:
        return _point_in_ring(px, py, ring[:-1])
    ox, oy = ring[0]
    e1x, e1y = ring[1][0] - ox, ring[1][1] - oy
    e2x, e2y = ring[3][0] - ox, ring[3][1] - oy
    l1 = math.hypot(e1x, e1y)
    l2 = math.hypot(e2x, e2y)
    if l1 <= 2.0 * margin or l2 <= 2.0 * margin:
        return False
    t1 = ((px - ox) * e1x + (py - oy) * e1y) / l1
    t2 = ((px - ox) * e2x + (py - oy) * e2y) / l2
    return (margin <= t1 <= l1 - margin) and (margin <= t2 <= l2 - margin)


# ── THE ACTIVE RULESET (phase B) ─────────────────────────────────────
# The census judges in the ruleset the BUILD ran under — carried by the
# ``.axes.json`` sidecar's ``ruleset`` key and never re-resolved from the
# ICAO identifier here.  That is the two-instruments law applied to
# authority: production emits what it did, and the validator judges the
# same law.  A sidecar predating the split has no key; the module default
# then applies and ``run_checks`` says so out loud.
_ACTIVE_RULESET = _DEFAULT_RULESET


def _set_active_ruleset(key) -> str:
    """Install the sidecar's ruleset for this run and return it."""
    global _ACTIVE_RULESET
    _ACTIVE_RULESET = str(key or _DEFAULT_RULESET)
    return _ACTIVE_RULESET


def _runway_strip_groups(ways: List[Way], nodes, ll_to_m):
    """One record per RUNWAY of this patch:
    ``(rings, axis_unit, code_number, length_m, code_letter)`` — the strip
    FOOTPRINT rings in the check's metre frame plus the runway's
    along-axis unit vector, aerodrome code number and (phase B) the code
    LETTER the FAA-keyed tables need.

    ``[]`` when the law module is unavailable or the patch carries no
    runway.  Runway ways are grouped by ``ref`` first: a tile cut or a
    runway crossing leaves one runway as several ways, and a fragment's own
    principal axis is not the runway's.

    THE one place the check derives strip geometry; both the wall law's
    footprint (``_runway_strip_keepout_rings``) and the abeam-longitudinal
    reader read it, so they cannot disagree about where a strip is."""
    if _runway_axis_and_width is None:
        return []
    groups: Dict[str, List[Tuple[float, float]]] = {}
    for w in ways:
        if w.role != "runway":
            continue
        # FRAME CONGRUENCE (rsa-law amendment 4, landed with the terrace
        # flip-readiness round §1).  ``w.nids`` is a CLOSED ring — the
        # first vertex repeats at the end — and feeding the duplicate
        # into the principal-axis fit weights that corner twice.  The
        # emitter derives the same footprint from ``_open_coords``, so
        # the two frames disagreed: endpoints shifted 0.27-0.98 m and
        # ring width by up to 1.19 m, which is exactly the drift class
        # that lets a wall or joint sit inside one footprint and outside
        # the other.  Dedupe the closing vertex (the transverse
        # checker's own ``nids[:-1]`` pattern) so emitter and validator
        # read ONE strip.
        nids = w.nids
        if len(nids) > 1 and nids[0] == nids[-1]:
            nids = nids[:-1]
        pts = [ll_to_m(*nodes[n]) for n in nids if n in nodes]
        if len(pts) < 3:
            continue
        groups.setdefault(w.ref or w.wid, []).extend(pts)
    out = []
    for pts in groups.values():
        axis = _runway_axis_and_width(pts)
        if axis is None:
            continue
        (ax, ay), (bx, by), width_m = axis
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            continue
        letter = (_runway_code_letter(width_m)
                  if _runway_code_letter is not None else None)
        rings = _runway_strip_wall_keepout_rings(
            (ax, ay), (bx, by), width_m, letter, _ACTIVE_RULESET)
        code = (_runway_code_number(length)
                if _runway_code_number is not None else 4)
        out.append((rings, ((bx - ax) / length, (by - ay) / length),
                    code, length, letter))
        # NOTE for consumers: ``rings[0]`` is the LATERAL graded-strip
        # rectangle (between the ends) and ``rings[1:]`` the two END
        # corridors — the split the abeam-longitudinal law needs (see
        # ``grade_law.runway_strip_lateral_footprint_ring``).
    return out


def _runway_strip_keepout_rings(ways: List[Way], nodes, ll_to_m):
    """The runway STRIP footprints of this patch, as closed rings (the
    wall law's consumer view of ``_runway_strip_groups``)."""
    rings = []
    for group_rings, _axis, _code, _length, _lett in _runway_strip_groups(
            ways, nodes, ll_to_m):
        rings.extend(group_rings)
    return rings


def _check_no_wall_in_runway_strip(ways: List[Way], nodes, ll_to_m
                                   ) -> List[Violation]:
    """Every ``retaining_wall`` vertex standing inside a runway strip
    footprint (owner ruling 2026-08-01).  Cap ZERO — a wall there is
    inadmissible geometry, not an over-cap grade, so the reported
    ``grade_pct`` carries the vertex's depth INSIDE the footprint (metres)
    rather than a slope."""
    rings = _runway_strip_keepout_rings(ways, nodes, ll_to_m)
    if not rings:
        return []
    out: List[Violation] = []
    for w in ways:
        if w.role != "retaining_wall":
            continue
        for k, nid in enumerate(w.nids):
            if nid not in nodes:
                continue
            x, y = ll_to_m(*nodes[nid])
            if not any(_point_in_rect_ring(x, y, r, _WALL_STRIP_MARGIN_M)
                       for r in rings):
                continue
            z = w.elevs[k] if k < len(w.elevs) else None
            z = 0.0 if z is None else float(z)
            out.append(Violation(
                grade_pct=0.0, excess_pct=0.0, distance_m=0.0, de_m=0.0,
                way_a=w, way_b=w, pt_a=(x, y), pt_b=(x, y),
                elev_a=z, elev_b=z))
            break        # one violation per WAY (the face is the defect)
    return out


# ── ABEAM-LONGITUDINAL STRIP LAW (§2, standards gap G-2) ────────
# The VALIDATOR TWIN of ``grade_law.runway_strip_longitudinal_clamp``.
# ICAO Annex 14 §3.4.13 caps the graded strip's ALONG-RUNWAY slope by code
# number (1.5 % code 4 / 1.75 % code 3 / 2 % code 1-2); FAA AC 150/5300-13B
# §3.16.5 item 1 says the same ground carries the RUNWAY's own longitudinal
# standard between the ends.  Nothing in this repo read that axis before —
# the lateral corridor law bounds a band vertex against the pavement edge at
# its own depth and never couples two stations along the runway — so this
# reader's rows are NEW VISIBILITY, and the honest expectation is that the
# count RISES when it is switched on: it sees ground that was never read.
#
# Lockstep is structural: the emitter and this reader call the SAME
# ``runway_strip_longitudinal_runs`` over the SAME footprint geometry, so
# they agree pair-for-pair about which pairs the longitudinal law binds.
#
# The band emitter rounds every band vertex to 0.1 m, so a PAIR carries a
# full decimetre of quantization; that is the allowance granted (the same
# constant the sloped-quad / weld-hub classes take).
_STRIP_LONGITUDINAL_ROLE = "graded_strip"
# The PAVEMENT roles whose nodes a band welds to (the weld-row skip above).
# NOTE (blast role-literal hazard): renaming a role VALUE in
# auto_patch/layout.py silently empties this set.
_STRIP_PAVEMENT_ROLES = frozenset({
    "runway", "runway_crossing", "primary_parallel", "secondary_parallel",
    "stub", "cross_connector", "junction", "apron", "terminal", "building",
    "service_road", "service_junction", "groundside_pavement",
    "tunnel_ramp", "hangar_pad",
})
# Pairs shorter than this along-axis carry more rounding than signal (a
# 0.1 m quantum over 0.2 m of run is 50 % of phantom grade); the allowance
# alone does not separate them, so they are not censused.  One station step
# is the emitter's own along-frontage granularity.
_STRIP_LONGITUDINAL_MIN_RUN_M = 1.0


def _check_strip_longitudinal_grade(ways: List[Way], nodes, ll_to_m
                                    ) -> Tuple[List[Violation], int, int]:
    """``(violations, n_pairs, n_ways)`` — every strip-band pair whose
    ALONG-RUNWAY slope exceeds the strip's by-code longitudinal cap.

    Only vertices INSIDE a runway strip footprint are read (that is where
    the law applies), and only pairs whose separation is predominantly
    along-axis: a transverse step is the graded strip's own mandatory
    cross-fall (Annex 14 §3.4.15), whose law is the lateral corridor's, and
    reading it here would demand that the drainage fall be flat.

    A pair whose BOTH endpoints are pavement nodes is skipped: that edge is
    the band's weld row, i.e. the pavement's own edge, and its longitudinal
    profile is the RUNWAY's law (``RUNWAY_MAX_GRADE`` + the vertical-curve
    rules), already read by the runway checks.  Skipping it here keeps this
    reader's population "strip GROUND", which is what G-2 is about."""
    if _runway_strip_longitudinal_runs is None or not _STRIP_PRECEDENCE:
        return [], 0, 0
    groups = _runway_strip_groups(ways, nodes, ll_to_m)
    if not groups:
        return [], 0, 0
    pavement_nids: set = set()
    for w in ways:
        if w.role in _STRIP_PAVEMENT_ROLES:
            pavement_nids.update(w.nids)
    out: List[Violation] = []
    n_pairs = 0
    hit_ways: set = set()
    seen_sites: set = set()     # one row per physical site (see _site_key)
    for w in ways:
        if w.role != _STRIP_LONGITUDINAL_ROLE:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        pts: List[Tuple[float, float]] = []
        zs: List[Optional[float]] = []
        for k, nid in enumerate(nn):
            if nid not in nodes:
                pts, zs = [], []
                break
            x, y = ll_to_m(*nodes[nid])
            pts.append((x, y))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if len(pts) < 2:
            continue
        allow = _pair_quant_noise_m(w)
        if allow < SLOPED_QUAD_ROUNDING_NOISE_M:
            allow = SLOPED_QUAD_ROUNDING_NOISE_M
        for rings, axis, code, _length, letter in groups:
            # BETWEEN THE ENDS only: ``rings[0]`` is the lateral graded
            # strip; the end corridors carry the runway-END regime's own
            # longitudinal law (FAA §3.16.5 items 2-4), read elsewhere.
            inside = [_point_in_rect_ring(px, py, rings[0], 0.0)
                      for px, py in pts]
            if not any(inside):
                continue
            cap, arc_rate = _strip_longitudinal_law(
                code, letter, _ACTIVE_RULESET)
            for run in _runway_strip_longitudinal_runs(pts, axis, inside):
                for a, b in zip(run, run[1:]):
                    if zs[a] is None or zs[b] is None:
                        continue
                    if nn[a] in pavement_nids and nn[b] in pavement_nids:
                        continue
                    ds = abs((pts[b][0] - pts[a][0]) * axis[0]
                             + (pts[b][1] - pts[a][1]) * axis[1])
                    if ds < _STRIP_LONGITUDINAL_MIN_RUN_M:
                        continue
                    _site = _site_key(pts[a], pts[b])
                    if _site in seen_sites:
                        continue    # same physical pair, another band
                    seen_sites.add(_site)
                    n_pairs += 1
                    dz = abs(float(zs[b]) - float(zs[a]))
                    if dz <= cap * ds + allow:
                        continue
                    hit_ways.add(w.wid)
                    out.append(Violation(
                        grade_pct=100.0 * dz / ds,
                        excess_pct=100.0 * (dz - cap * ds - allow) / ds,
                        distance_m=ds, de_m=dz,
                        way_a=w, way_b=w,
                        pt_a=pts[a], pt_b=pts[b],
                        elev_a=float(zs[a]), elev_b=float(zs[b])))
    out.sort(key=lambda v: -v.grade_pct)
    return out, n_pairs, len(hit_ways)


# ══════════════════════════════════════════════════════════════════════
# VALIDATOR TWINS FOR THE REMAINING REG FAMILIES
# (spec docs/specs/DRAFT-reg-families-round-spec.md rounds A and B)
#
# Each reader below evaluates THE SAME ``grade_law`` function its
# generation-binding half evaluates, in the ruleset the SIDECAR records —
# so the surface we build and the surface we check cannot drift, and a
# family cannot be lawful under one authority and judged under another.
# ══════════════════════════════════════════════════════════════════════

#: A rate instrument reading an emit quantum at a station spacing has a
#: BLIND SPOT — a grade-change reading it cannot distinguish from pure
#: rounding.  A row inside it is PASS-with-residual (materiality law),
#: never iterated on.  Documented exactly as the RSA lane documented the
#: slope reader's.
#:
#: BROKEN-INSTRUMENT FIX (2026-08-05, verdict (d)): the old constant was
#: ``0.1 / 30.0`` — the quantum divided by an ASSUMED 30 m spacing, hard
#: coded, while the emitted graded-strip rings actually station 2-5 m
#: apart (measured KCLT: 585 of 985 arc rows at a 2-5 m span, only 16
#: beyond 20 m).  At 3 m the true blind spot is twenty times the constant,
#: so the reader was judging pure emit rounding as a curvature violation.
#:
#: THE DERIVATION.  With ``change = (z_c - z_b)/dn - (z_b - z_a)/dp`` and
#: each node value carrying at most ``q/2`` of rounding, the worst-case
#: rounding contribution to ``change`` is
#:     q/2 * (1/dp + 1/dn + 1/dp + 1/dn) = q * (1/dp + 1/dn).
#: ``q`` is the way's OWN emit quantum — ``_pair_quant_noise_m``, the same
#: envelope the abeam reader grants — so there is one derivation and no
#: second constant.
def _rate_reader_blind_spot(way: "Way", dp: float, dn: float) -> float:
    """Grade-change reading below which a rate row is pure emit rounding."""
    q = _pair_quant_noise_m(way)
    if q < SLOPED_QUAD_ROUNDING_NOISE_M:
        q = SLOPED_QUAD_ROUNDING_NOISE_M
    if dp < 1e-9 or dn < 1e-9:
        return float("inf")
    return q * (1.0 / dp + 1.0 / dn)


#: Rounding for the physical-site key the strip readers dedupe on (mm).
_SITE_KEY_DP = 3


def _site_key(*pts) -> tuple:
    """Identity of a physical STATION SITE, order-independent.

    THE DOUBLE-COUNT (2026-08-05, verdict (d)).  Adjacent graded-strip
    band pieces share their whole common boundary chain, so every
    consecutive vertex pair on that chain belongs to BOTH rings and the
    per-way readers below counted the SAME physical site once per way.
    Measured KCLT: strip_abeam 847 rows over 433 distinct sites (414 of
    them carried by more than one way) = x1.96; strip_arc 985 over 517 =
    x1.91.  The law is about the SURFACE, and the surface has one station
    there — the no-stacked-nodes invariant guarantees the shared vertices
    are ONE node with ONE value, so the second reading is arithmetically
    identical, never independent evidence.
    """
    return tuple(sorted((round(x, _SITE_KEY_DP), round(y, _SITE_KEY_DP))
                        for (x, y) in pts))


def _check_strip_arc_rate(ways: List[Way], nodes, ll_to_m
                          ) -> Tuple[List[Violation], int, int]:
    """§A3(b) twin — strip stations whose GRADE CHANGE along the runway
    axis outruns the strip's rate-of-change law.

    ICAO Annex 14 §3.4.14 is qualitative ("as gradual as practicable"),
    so the ICAO rate is the PROVISIONAL operationalization flagged on the
    ruleset (owner question 2); FAA AC §3.16.5 item 5 gives ±2 % per
    100 ft (30.5 m).  Both come from ``grade_law.strip_longitudinal_law``
    — the same call the emitter's clamp makes."""
    if _strip_longitudinal_law is None or _strip_longitudinal_breaches is None:
        return [], 0, 0
    groups = _runway_strip_groups(ways, nodes, ll_to_m)
    if not groups:
        return [], 0, 0
    out: List[Violation] = []
    n_stations = 0
    hit_ways: set = set()
    seen_sites: set = set()     # one row per physical site (see _site_key)
    for w in ways:
        if w.role != _STRIP_LONGITUDINAL_ROLE:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(nn):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if not ok or len(pts) < 3:
            continue
        for rings, axis, code, _length, letter in groups:
            inside = [_point_in_rect_ring(px, py, rings[0], 0.0)
                      for px, py in pts]
            if not any(inside):
                continue
            cap, arc_rate = _strip_longitudinal_law(
                code, letter, _ACTIVE_RULESET)
            if not arc_rate:
                continue
            for run in _runway_strip_longitudinal_runs(pts, axis, inside):
                s = [pts[i][0] * axis[0] + pts[i][1] * axis[1] for i in run]
                z = [zs[i] for i in run]
                n_stations += max(0, len(run) - 2)
                for k in _strip_longitudinal_breaches(
                        s, z, cap, arc_rate):
                    if k <= 0 or k >= len(run) - 1:
                        continue
                    a, b, c = run[k - 1], run[k], run[k + 1]
                    if zs[a] is None or zs[b] is None or zs[c] is None:
                        continue
                    dp = abs(s[k] - s[k - 1])
                    dn = abs(s[k + 1] - s[k])
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    change = abs((float(zs[c]) - float(zs[b])) / dn
                                 - (float(zs[b]) - float(zs[a])) / dp)
                    allowed = arc_rate * 0.5 * (dp + dn)
                    if change - allowed <= _rate_reader_blind_spot(
                            w, dp, dn):
                        continue        # PASS-with-residual
                    _site = _site_key(pts[a], pts[b], pts[c])
                    if _site in seen_sites:
                        continue    # same physical station, another band
                    seen_sites.add(_site)
                    hit_ways.add(w.wid)
                    span = 0.5 * (dp + dn)
                    out.append(Violation(
                        grade_pct=100.0 * change,
                        excess_pct=100.0 * (change - allowed),
                        distance_m=span, de_m=abs(float(zs[c]) - float(zs[a])),
                        way_a=w, way_b=w, pt_a=pts[a], pt_b=pts[c],
                        elev_a=float(zs[a]), elev_b=float(zs[c])))
    out.sort(key=lambda v: -v.grade_pct)
    return out, n_stations, len(hit_ways)


def _check_resa_transverse_grade(ways: List[Way], nodes, ll_to_m
                                 ) -> Tuple[List[Violation], int, int]:
    """§A1 twin — the END-corridor ACROSS-corridor grade, a family
    NOTHING read before (the count therefore RISES on first sight; that
    is the honest-count law, not a regression).

    Population: ground vertices inside either END corridor ring
    (``_runway_strip_groups`` rings 1 and 2 — the same footprint the
    emitter's law uses).  Each consecutive pair whose separation is
    predominantly ACROSS the extended centreline is judged against
    ``grade_law.resa_transverse_band`` at its own distance beyond the
    end: FAA Table 3-6 S-3 inside the 61 m near zone, ±5 % beyond
    (Fig 3-35); ICAO §3.5.11 ±5 % throughout."""
    if _resa_transverse_band is None:
        return [], 0, 0
    groups = _runway_strip_groups(ways, nodes, ll_to_m)
    if not groups:
        return [], 0, 0
    out: List[Violation] = []
    n_pairs = 0
    hit_ways: set = set()
    for w in ways:
        if w.role != _STRIP_LONGITUDINAL_ROLE:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(nn):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if not ok or len(pts) < 2:
            continue
        allow = max(_pair_quant_noise_m(w), SLOPED_QUAD_ROUNDING_NOISE_M)
        for rings, axis, _code, length, letter in groups:
            ux, uy = axis
            px, py = -uy, ux
            # The corridor rings' own along-axis origin: ring 1 is the
            # approach end (s < 0), ring 2 the departure end (s > L).
            for ring_idx in (1, 2):
                if ring_idx >= len(rings):
                    continue
                ring = rings[ring_idx]
                inside = [_point_in_rect_ring(qx, qy, ring, 0.0)
                          for qx, qy in pts]
                if not any(inside):
                    continue
                for a in range(len(pts) - 1):
                    b = a + 1
                    if not (inside[a] and inside[b]):
                        continue
                    if zs[a] is None or zs[b] is None:
                        continue
                    dx = pts[b][0] - pts[a][0]
                    dy = pts[b][1] - pts[a][1]
                    along = abs(dx * ux + dy * uy)
                    across = abs(dx * px + dy * py)
                    if across <= along or across < 1.0:
                        continue        # the LONGITUDINAL skirt law's pair
                    n_pairs += 1
                    # distance beyond the end, from the nearer endpoint
                    s_mid = 0.5 * ((pts[a][0] + pts[b][0]) * ux
                                   + (pts[a][1] + pts[b][1]) * uy)
                    beyond = (abs(s_mid) if ring_idx == 1
                              else max(0.0, s_mid - length))
                    _min_down, max_abs = _resa_transverse_band(
                        beyond, letter, _ACTIVE_RULESET)
                    if not max_abs:
                        continue
                    dz = abs(float(zs[b]) - float(zs[a]))
                    if dz <= max_abs * across + allow:
                        continue
                    hit_ways.add(w.wid)
                    out.append(Violation(
                        grade_pct=100.0 * dz / across,
                        excess_pct=100.0 * (
                            dz - max_abs * across - allow) / across,
                        distance_m=across, de_m=dz,
                        way_a=w, way_b=w, pt_a=pts[a], pt_b=pts[b],
                        elev_a=float(zs[a]), elev_b=float(zs[b])))
    out.sort(key=lambda v: -v.grade_pct)
    return out, n_pairs, len(hit_ways)


def _check_raoa_rate(ways: List[Way], nodes, ll_to_m
                     ) -> Tuple[List[Violation], int, int]:
    """§A4 twin — the RADIO ALTIMETER OPERATING AREA's rate of change
    (ICAO Annex 14 §3.8.4, ≤2 % per 30 m).

    A no-op under the FAA ruleset: the family does not exist there
    (``grade_law.raoa_footprint_ring`` returns ``None``), so KCLT reads
    zero rows by construction — jurisdictional fidelity, not a silent
    skip.  The reader walks the SAME rectangle the emitter clamps and
    reuses the §A3(b) rate machinery on that second footprint."""
    if _raoa_footprint_ring is None:
        return [], 0, 0
    groups = _runway_strip_groups(ways, nodes, ll_to_m)
    if not groups:
        return [], 0, 0
    rects = []
    for rings, axis, _code, length, _letter in groups:
        ux, uy = axis
        # The lateral ring's two ends ARE the thresholds in this frame.
        a_end = (rings[0][0][0] * 0.5 + rings[0][3][0] * 0.5,
                 rings[0][0][1] * 0.5 + rings[0][3][1] * 0.5)
        b_end = (rings[0][1][0] * 0.5 + rings[0][2][0] * 0.5,
                 rings[0][1][1] * 0.5 + rings[0][2][1] * 0.5)
        for thr, inward in ((a_end, (ux, uy)), (b_end, (-ux, -uy))):
            ring = _raoa_footprint_ring(thr, inward, _ACTIVE_RULESET)
            if ring:
                rects.append((ring, inward))
    if not rects:
        return [], 0, 0
    from auto_patch.config import get_ruleset as _get_ruleset
    rate = _get_ruleset(_ACTIVE_RULESET).raoa_max_grade_change_per_m
    if not rate:
        return [], 0, 0
    out: List[Violation] = []
    n_stations = 0
    hit_ways: set = set()
    seen_sites: set = set()     # one row per physical site (see _site_key)
    for w in ways:
        if w.role != _STRIP_LONGITUDINAL_ROLE:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(nn):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if not ok or len(pts) < 3:
            continue
        for ring, inward in rects:
            inside = [_point_in_rect_ring(qx, qy, ring, 0.0)
                      for qx, qy in pts]
            if sum(1 for f in inside if f) < 3:
                continue
            idx = [i for i, f in enumerate(inside) if f and zs[i] is not None]
            if len(idx) < 3:
                continue
            s = [pts[i][0] * inward[0] + pts[i][1] * inward[1] for i in idx]
            z = [float(zs[i]) for i in idx]
            order = sorted(range(len(idx)), key=lambda k: s[k])
            s = [s[k] for k in order]
            z = [z[k] for k in order]
            src = [idx[k] for k in order]
            n_stations += max(0, len(s) - 2)
            for k in range(1, len(s) - 1):
                dp, dn = s[k] - s[k - 1], s[k + 1] - s[k]
                if dp < 1e-6 or dn < 1e-6:
                    continue
                change = abs((z[k + 1] - z[k]) / dn - (z[k] - z[k - 1]) / dp)
                allowed = rate * 0.5 * (dp + dn)
                if change - allowed <= _rate_reader_blind_spot(w, dp, dn):
                    continue
                _site = _site_key(pts[src[k - 1]], pts[src[k]],
                                  pts[src[k + 1]])
                if _site in seen_sites:
                    continue    # same physical station, another band
                seen_sites.add(_site)
                hit_ways.add(w.wid)
                out.append(Violation(
                    grade_pct=100.0 * change,
                    excess_pct=100.0 * (change - allowed),
                    distance_m=0.5 * (dp + dn), de_m=abs(z[k + 1] - z[k - 1]),
                    way_a=w, way_b=w,
                    pt_a=pts[src[k - 1]], pt_b=pts[src[k + 1]],
                    elev_a=z[k - 1], elev_b=z[k + 1]))
    out.sort(key=lambda v: -v.grade_pct)
    return out, n_stations, len(hit_ways)


#: Roles the §B3 drainage MINIMUM is read on — DERIVED FROM THE LAW, never
#: typed here.  Building pads are excluded by owner law
#: (``TERMINAL_PADS_SLOPE=False``) and terrace panels by the open owner
#: question 4; both exclusions live in ``grade_law.drainage_minimum_grade``,
#: so this set only chooses WHICH emitted ways to walk.
#:
#: IT USED TO BE A HAND-TYPED TUPLE, and it was wrong (fix cycle 2 item 5,
#: verdict (d) BROKEN INSTRUMENT): ``("apron", "stand", "groundside",
#: "parking")``.  Of those four literals exactly ONE — ``apron`` — is a role
#: this engine ever emits.  ``stand``, ``groundside`` and ``parking`` are not
#: in ``layout.ROLE_*`` at all; the emitted landside role is
#: ``groundside_pavement``.  So the walk skipped every groundside way and the
#: GROUNDSIDE HALF OF §B3 NEVER FIRED — the law had a 1.0 % minimum
#: (``GROUNDSIDE_MIN_DRAINAGE_GRADE``) and its twin was reading a role set
#: that could not match it.  Structurally silent: an empty walk and a
#: compliant walk report the same zero.
#:
#: The law already owns the answer in two frozensets.  Deriving from them
#: is the single-source fix: emitter and validator cannot disagree about
#: WHICH surfaces the minimum is read on, the same way
#: ``drainage_minimum_shortfall`` already makes them agree about HOW FLAT
#: is too flat.
#:
#: THE GROUNDSIDE HALF IS NOW EMPTY BY LAW, not by drift (owner 2026-08-14,
#: RULINGS "DRAINAGE RULING SCOPE CLARIFIED": the family "retires only
#: where it demanded curvature ON taxiway/road/groundside pavement
#: surfaces").  ``grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES`` is the empty
#: set, so this walk is the APRON half alone — which did NOT retire: FAA
#: §5.9.1.1's 0.5 % is a cited authority number, and it still binds at
#: every FAA airport (a no-op under ICAO, which states none).
#:
#: Read ``RETIRED_LAWS`` before concluding anything from a zero here: the
#: two ways this family can print zero on landside pavement — the law
#: exempts it, or the walk lost it — are indistinguishable in the output,
#: and this repo has now seen both.
_DRAINAGE_MIN_ROLES = frozenset(
    _LAW_DRAIN_MIN_APRON_ROLES) | frozenset(_LAW_DRAIN_MIN_GS_ROLES)


def _check_drainage_minimum(ways: List[Way], nodes, ll_to_m
                            ) -> Tuple[List[Violation], int, int]:
    """§B3 twin — surfaces FLATTER than their drainage minimum.

    FAA §5.9.1.1 mandates a minimum 0.5 % apron gradient; ICAO §3.13.4 is
    qualitative and states no number, so the apron half is a no-op at
    every ICAO airport.  The groundside minimum is region-invariant and
    PROVISIONAL (owner question 3).

    Reported as a SHORTFALL: ``grade_pct`` is the measured grade,
    ``excess_pct`` how far below the minimum it sits.  Runs shorter than
    the materiality floor are not read — a 1 m puddle is not a drainage
    defect."""
    if _drainage_minimum_grade is None:
        return [], 0, 0
    out: List[Violation] = []
    n_pairs = 0
    hit_ways: set = set()
    for w in ways:
        if w.role not in _DRAINAGE_MIN_ROLES:
            continue
        low = _drainage_minimum_grade(w.role, _ACTIVE_RULESET)
        if not low:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(nn):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if not ok or len(pts) < 2:
            continue
        for a in range(len(pts) - 1):
            b = a + 1
            if zs[a] is None or zs[b] is None:
                continue
            dist = math.hypot(pts[b][0] - pts[a][0], pts[b][1] - pts[a][1])
            if dist < _DRAINAGE_MIN_RUN_M:
                continue
            n_pairs += 1
            grade = abs(float(zs[b]) - float(zs[a])) / dist
            short = _drainage_minimum_shortfall(grade, w.role, _ACTIVE_RULESET)
            if short <= 0.0:
                continue
            hit_ways.add(w.wid)
            out.append(Violation(
                grade_pct=100.0 * grade, excess_pct=100.0 * short,
                distance_m=dist, de_m=abs(float(zs[b]) - float(zs[a])),
                way_a=w, way_b=w, pt_a=pts[a], pt_b=pts[b],
                elev_a=float(zs[a]), elev_b=float(zs[b])))
    out.sort(key=lambda v: -v.excess_pct)
    return out, n_pairs, len(hit_ways)


#: Minimum run (m) over which the drainage minimum is read.  Below it the
#: 0.01 m emit quantum dominates the measured grade (0.01/2 m = 0.5 %,
#: exactly the FAA minimum), so a shorter pair says nothing about
#: drainage.
_DRAINAGE_MIN_RUN_M = 5.0


# ══════════════════════════════════════════════════════════════════════
# THE RUNWAY CROWN — the KEPT drainage law's census reader
# ══════════════════════════════════════════════════════════════════════
# WHY THIS FAMILY EXISTS (S7 escalation, ruled 2026-08-14).  RULINGS
# 2026-08-13b retired the drainage minimum with the owner's rationale
# "only runways get a crown, the rest can be flat for the sim", and the
# 2026-08-14 scope clarification KEEPS the runway crown as law.  It had
# NO census reader: a runway emitted dead flat against a declared 0.30 m
# crown drop censused ZERO rows, because the only crown-aware reader is
# the within-shape pair law, which re-centres each pair's budget on the
# DESIGNED crown (``grade_law.crown_pair_offset``) and then judges the
# residue against the runway's own transverse CAP — and a 1 % crown sits
# inside a 1.5 % cap by construction.  The minimum was bound only where
# it is GENERATED (``tests/test_crown_minimum_bound.py``), which is
# exactly the half of "every reg generation-binding with twins" this
# campaign does not accept alone.
#
# WHAT THE LAW SOURCE IS, and it is NOT a global constant.  The rate
# comes from the ruleset (``grade_law.runway_crown_rate`` — at least
# ``runway_transverse_min``, never above ``runway_transverse_max``), but
# the number that governs a NODE is the per-node DECLARED DROP the build
# resolved from it and exported in the axes sidecar (``crown_drops``,
# ``crown.runway_crown_drop_m`` → ``_rail_continuous_drops`` → the
# tile-seam taper).  Two lawful mechanisms REDUCE a node's drop below
# ``rate × half_width``: rail continuity (the crown may not spend budget
# the runway's own longitudinal profile needs) and the seam ramp (a
# crowned edge at a tile cut is a cliff).  A reader that re-derived
# ``rate × offset`` would therefore report the law's own relaxations as
# defects.  SO THE READER HONOURS THE DECLARATION — the same field the
# solver built to and the within-shape law already re-centres on.
#
# HOW THE CROWN IS EMITTED, which is what makes it readable at all: the
# runway RING carries the crowned surface (``z' − drop``) and the ridge
# is a separate ``o4_feature=crown_spine`` breakline at ``z'`` (the
# pre-crown spine profile).  ``crown_centerline`` is empty on every
# battery patch — the ring holds no ridge vertex — so the REALISED crown
# is the fall from the spine breakline to the ring node, and nothing but
# this reader looks at that pair.
#
# A MISSING DECLARATION IS ITS OWN CONDITION, never a silent zero (the
# S3 blindness verdict, applied before the family can acquire the
# defect): a runway shape NO node of which appears in the crown field
# has no relaxation record to honour, so its nodes are judged against
# the ruleset's own floor (``grade_law.transverse_minimum_for_role``),
# and only where that floor BINDS (``transverse_minimum_binds`` —
# ``CROWN_MINIMUM_BOUND_RUNWAYS``, owner d48bc0a).  Counted separately
# and printed.

#: The runway family — the roles the crown law governs.  Same two values
#: as ``MATERIALITY_RUNWAY_FAMILY_ROLES`` and ``flex_audit.RUNWAY_ROLES``.
_CROWN_RUNWAY_ROLES = frozenset({"runway", "runway_crossing"})

#: THE INTERSECTION EXEMPTION, cited not invented.  ICAO Annex 14
#: §3.1.19: the runway transverse "should not exceed 1.5 per cent or 2
#: per cent, as applicable, nor be less than 1 per cent EXCEPT AT RUNWAY
#: OR TAXIWAY INTERSECTIONS" (FAA Table 3-6 S-1 carries the same
#: exception).  ``runway_crossing`` IS the intersection surface in this
#: engine, so a node on one — or welded to one — is where the crown
#: minimum is expressly not required.  Such rows are still MEASURED and
#: still counted in the family; they are stamped ``out_of_scope`` so the
#: acceptance verdict does not adjudicate a row the law exempts.
_CROWN_INTERSECTION_ROLES = frozenset({"runway_crossing"})
_CROWN_OUT_OF_SCOPE = "runway_intersection"


def _nearest_ridge(px: float, py: float, spines):
    """``(distance_m, ridge_elev, foot_xy)`` — the nearest point on any crown-spine
    breakline, elevation interpolated ALONG the polyline (X-Plane renders
    a breakline linearly, so the interpolated value is the ridge height at
    that station, not an approximation of one).

    No search radius: the crown-spine ways ARE this airport's runway
    ridges, and a runway node's own ridge is the nearest one by
    construction.  An arbitrary cutoff would turn "the ridge is far
    away" into "no row", which is the silent-zero this family exists to
    remove — the distance is REPORTED on the row instead."""
    best_d, best_z, best_pt = float("inf"), None, None
    for pts in spines:
        for i in range(len(pts) - 1):
            ax, ay, az = pts[i]
            bx, by, bz = pts[i + 1]
            vx, vy = bx - ax, by - ay
            l2 = vx * vx + vy * vy
            t = 0.0 if l2 < 1e-12 else max(0.0, min(
                1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
            qx, qy = ax + t * vx, ay + t * vy
            d = math.hypot(px - qx, py - qy)
            if d < best_d:
                best_d, best_z, best_pt = d, az + t * (bz - az), (qx, qy)
    return best_d, best_z, best_pt


def _check_runway_crown(ways: List[Way], nodes, ll_to_m,
                        crown_by_nid: Dict[str, float],
                        spine_ways: List[Way]
                        ) -> Tuple[List[Violation], int, int, int]:
    """``(violations, n_nodes, n_no_ridge, n_undeclared_shapes)`` — every
    runway cross-section that does NOT carry the crown its build declared
    (or, where nothing was declared, the ruleset's own floor).

    Reported as a SHORTFALL, the same shape ``_check_drainage_minimum``
    uses: ``grade_pct`` is the REALISED transverse grade from the ridge to
    the node, ``excess_pct`` how much of the required grade is missing,
    ``de_m`` the realised fall.  The allowance is ``_pair_quant_noise_m``
    on the runway — ridge and ring are both emitted per-node at the 0.01 m
    grid and the drop is quantised UP onto it, so a cm of round is not a
    flat runway."""
    if not ways:
        return [], 0, 0, 0
    spines = []
    for sw in spine_ways or []:
        pts = []
        for k, nid in enumerate(sw.nids):
            if nid not in nodes or k >= len(sw.elevs) or sw.elevs[k] is None:
                continue
            x, y = ll_to_m(*nodes[nid])
            pts.append((x, y, float(sw.elevs[k])))
        if len(pts) >= 2:
            spines.append(pts)
    # Nodes at a runway/taxiway INTERSECTION — the cited exception.
    xing_nids: set = set()
    for w in ways:
        if w.role in _CROWN_INTERSECTION_ROLES:
            xing_nids.update(w.nids)
    # THE FALLBACK RIDGE, for a patch that emitted no crown spine at all.
    # Absence of the breakline IS the finding — the crown was not emitted —
    # but a row still needs the node's lateral OFFSET to price a grade, and
    # that comes from the LAW's own runway axis (``runway_axis_and_width``,
    # the principal axis of the runway's emitted ring cloud, joined across
    # the fragments a tile cut or a crossing leaves), never a second idea
    # of where a runway's centreline is.
    axis_pts: Dict[str, list] = defaultdict(list)
    for w in ways:
        if w.role not in _CROWN_RUNWAY_ROLES:
            continue
        # OPEN vertex list: the closing repeat would weight one corner
        # twice and tilt the principal axis off the centreline.
        for nid in (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
                    else w.nids):
            if nid in nodes:
                axis_pts[w.ref].append(ll_to_m(*nodes[nid]))
    axis_by_ref: Dict[str, tuple] = {}
    if _runway_axis_and_width is not None:
        for ref, pts in axis_pts.items():
            try:
                ax = _runway_axis_and_width(pts)
            except Exception:                          # pragma: no cover
                ax = None
            if ax:
                axis_by_ref[ref] = ax

    def _axis_offset(ref: str, px: float, py: float):
        """``(distance_m, foot_xy)`` to the law's own runway axis."""
        ax = axis_by_ref.get(ref)
        if not ax:
            return 0.0, (px, py)
        (ax0, ay0), (ax1, ay1) = ax[0], ax[1]
        vx, vy = ax1 - ax0, ay1 - ay0
        l2 = vx * vx + vy * vy
        if l2 < 1e-12:
            return 0.0, (px, py)
        t = ((px - ax0) * vx + (py - ay0) * vy) / l2
        foot = (ax0 + t * vx, ay0 + t * vy)
        return math.hypot(px - foot[0], py - foot[1]), foot

    # The ruleset's own floor, for shapes that declared nothing.
    floor = None
    if (_transverse_minimum_for_role is not None
            and _transverse_minimum_binds is not None
            and _transverse_minimum_binds("runway")):
        floor = _transverse_minimum_for_role("runway", _ACTIVE_RULESET)

    out: List[Violation] = []
    n_nodes = n_no_ridge = n_undeclared = 0
    for w in ways:
        if w.role not in _CROWN_RUNWAY_ROLES:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        declared = any(nid in crown_by_nid for nid in nn)
        if not declared:
            if floor is None:
                continue          # the crown minimum does not bind here
            n_undeclared += 1
        noise = _pair_quant_noise_m(w)
        for k, nid in enumerate(nn):
            if (nid not in nodes or k >= len(w.elevs)
                    or w.elevs[k] is None):
                continue
            x, y = ll_to_m(*nodes[nid])
            z = float(w.elevs[k])
            dist, ridge_z, foot = _nearest_ridge(x, y, spines)
            if ridge_z is None:
                # NO ridge geometry at all: the crown cannot have been
                # emitted, and the ABSENCE is the finding.  The offset
                # comes from the law's runway axis so the row still
                # carries a real cross-section; the realised fall is 0
                # because there is nothing above the node to fall from.
                dist, foot = _axis_offset(w.ref, x, y)
                ridge_z, realised = z, 0.0
                n_no_ridge += 1
            else:
                realised = ridge_z - z
            if declared:
                required = float(crown_by_nid.get(nid, 0.0))
            else:
                required = float(floor) * dist
            if required <= 0.0:
                continue          # uncrowned by declaration (or on the ridge)
            n_nodes += 1
            short = required - realised - noise
            if short <= 0.0:
                continue
            span = max(dist, SHARED_VERTEX_TOL_M)
            v = Violation(
                grade_pct=100.0 * realised / span,
                excess_pct=100.0 * short / span,
                distance_m=dist, de_m=abs(realised),
                way_a=w, way_b=w, pt_a=(x, y), pt_b=foot,
                elev_a=z, elev_b=float(ridge_z))
            if w.role in _CROWN_INTERSECTION_ROLES or nid in xing_nids:
                v.out_of_scope = _CROWN_OUT_OF_SCOPE
            out.append(v)
    out.sort(key=lambda r: -r.excess_pct)
    return out, n_nodes, n_no_ridge, n_undeclared


# ── DRAINAGE-SPINE LAW (owner field report 2026-08-02) ──────────
# "The drainage spine must be below the lower adjacent pavement."  The
# emitter half is ``grade_law.drainage_spine_envelope`` (consumed by
# ``gap_fill._spine_interval``, ``_freeze_spine_parent_specs`` and the
# post-projection re-clamp).  This reader takes the geometric form of the
# same statement — a spine vertex at or above the LOWER of its two nearest
# airside pavement edges dams the interior it is supposed to drain — and
# reports the shortfall against ``DRAINAGE_SPINE_MIN_FALL_M`` separately,
# because that constant is PROVISIONAL and must not silently become the
# pass/fail line.
# THE parent role set is the law's (``grade_law``), not a second copy —
# same statement, same population as ``gap_fill._airside_shapes``.
_SPINE_AIRSIDE_ROLES = _DRAINAGE_SPINE_PARENT_ROLES
_SPINE_PARENT_CELL_M = 40.0


def _scan_edges(px, py, rings, cand):
    """``[(distance, wid, edge_alt), …]`` for the candidate ring edges —
    distance to the ring, elevation LINEARLY INTERPOLATED along the
    nearest edge (the same metric ``gap_fill._spine_interval`` uses)."""
    out = []
    for (si, ei) in cand:
        wid, ring = rings[si]
        ax, ay, az = ring[ei]
        bx, by, bz = ring[(ei + 1) % len(ring)]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        t = 0.0 if l2 < 1e-12 else max(0.0, min(
            1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
        qx, qy = ax + t * vx, ay + t * vy
        out.append((math.hypot(px - qx, py - qy), wid, az + t * (bz - az)))
    return out


def _nearest_edge_alt_by_way(px, py, rings, grid, search_m=200.0):
    """The station's BOUNDING PARENTS, nearest first, as
    ``[(distance, wid, edge_alt), …]``.

    Selection is ``grade_law.drainage_spine_parents`` — the same function
    ``gap_fill._AirsideNearestIndex`` ranks with — so the emitter and this
    reader cannot pick different parents for the same station.

    THE SEARCH IS SOUND, which the previous grid walk was not: it stopped
    at the first cell ring holding two distinct ways, and a way whose
    nearest edge lies just outside that ring can be NEARER than one inside
    it.  Measured at HECA (2026-08-02): the true nearest parent at 67.31 m
    was missed and a 91.96 m one substituted, whose lower edge sat 0.85 m
    under the real one — one spine read 0.47 m ABOVE its "lower" pavement
    when against its real parents it is 0.38 m BELOW.  Scanning cells
    ``±k`` about the station's own cell covers every geometry within
    ``k·r`` of the station (the station is at least ``k·r`` from the
    scanned region's boundary), so the answer is exact once the SECOND
    parent sits inside that radius; otherwise the reach doubles, and a
    station that outruns ``search_m`` falls back to the full scan rather
    than to a truncated answer."""
    r = _SPINE_PARENT_CELL_M
    reach = r
    cx, cy = int(px // r), int(py // r)
    while reach <= search_m:
        cand = set()
        k = max(1, int(reach // r))
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                cand.update(grid.get((cx + dx, cy + dy), ()))
        picked = _drainage_spine_parents(
            [(d, wid, z) for d, wid, z in _scan_edges(px, py, rings, cand)])
        # SOUND once the second parent lies inside the guaranteed radius
        # (everything excluded is strictly beyond it).
        if len(picked) >= 2 and picked[1][0] <= k * r:
            return [(d, wid, z) for d, wid, z in picked]
        reach *= 2.0
    all_edges = [(si, ei) for si, (_wid, ring) in enumerate(rings)
                 for ei in range(len(ring))]
    return [(d, wid, z) for d, wid, z in _drainage_spine_parents(
        [(d, wid, z) for d, wid, z in _scan_edges(px, py, rings, all_edges)])]


#: The convergence-guard materiality floor for elevation classes (CLAUDE.md
#: "MATERIALITY FLOOR", 0.01 m).  A graded-handoff residual under it is a
#: PASS-with-residual and never a row; above it the census carries it.
_SPINE_HANDOFF_MATERIALITY_M = 0.01


def _spine_handoff_here(near, family_by_wid, bench_slope):
    """``(handoff_value | None, residual_m)`` for one interior spine station.

    F3c, the validator half.  ``near`` is this station's bounding parents as
    ``[(distance_m, wid, edge_alt), …]``; each parent's envelope offsets come
    from ``grade_law.drainage_spine_envelope`` at its own distance, and the
    composition is ``grade_law.drainage_spine_interval`` — the identical call
    ``gap_fill._spine_interval`` makes.  ``None`` means "no handoff applies
    here": either the law module is absent, a parent's family is unknown, or
    the two envelopes INTERSECT, in which case this reader's pre-F3c dam
    clause is untouched.
    """
    if _drainage_spine_interval is None or len(near) < 2:
        return None, 0.0
    per_parent = []
    for d, wid, edge in near[:2]:
        fam = family_by_wid.get(wid)
        if fam is None:
            return None, 0.0
        try:
            floor_off, ceil_off = _drainage_spine_envelope(
                fam[0], fam[1], fam[2], max(0.0, float(d)))
        except Exception:
            return None, 0.0
        per_parent.append((
            max(0.0, float(d)),
            None if floor_off is None else float(edge) + float(floor_off),
            None if ceil_off is None else float(edge) + float(ceil_off)))
    _lo, hi, residual, is_handoff = _drainage_spine_interval(
        per_parent, bench_slope=bench_slope)
    if not is_handoff:
        # An intersecting (or one-sided) interval — no handoff was composed.
        return None, 0.0
    return hi, float(residual)


# ══════════════════════════════════════════════════════════════════════
# APRON LATTICE MEMBRANE (spec heca-apron-round2 Amendment 1 §1b)
# ══════════════════════════════════════════════════════════════════════
# THE FAMILY THAT MAKES A VOID PRICEABLE.  Every other within-shape
# family reaches its pairs through RING ADJACENCY or a proximity sweep
# over emitted ring vertices.  A lattice node lies on NO ring — it is an
# interior anchor minted precisely because the apron's interior had no
# vertices — so no existing family can discover its pairs, and a region
# with no pairs contributes no rows however wrong its surface is.  That
# blindness is the defect this whole round was written for: HECA shipped
# 247 m of cliff dropping 6.06 m at ZERO census rows.
#
# THE BUDGET IS THE SOLVER'S OWN, CARRIED.  The solve priced each lattice
# edge through ``classify_pair`` at the APRON'S own cap and published the
# pair with that budget in the sidecar.  This family checks the EMITTED
# membrane against that number rather than re-deriving a cap from a role
# table — a second derivation here is exactly the census-wrapper defect,
# and it could not be right anyway: the lattice's cap depends on the
# apron's own fan-ramp/lateral context, which only the solve holds.
#
# A published edge whose endpoints are not both emitted is SKIPPED and
# counted, never silently dropped: the emit decimators can remove a
# lattice vertex, and an unmatched edge is a missing measurement, not a
# pass.

#: How close an emitted node must be to a published lattice endpoint to
#: BE it.  The canonical registry interns within ``SHARED_VERTEX_TOL_M``
#: and emit rounds lat/lon, so this is the same identity every other
#: sidecar-joined family uses.
_LATTICE_JOIN_TOL_M = SHARED_VERTEX_TOL_M


def _check_apron_lattice_membrane(
        lattice_edges_ll, lattice_ways, ways, nodes, ll_to_m
) -> Tuple[List[Violation], int, int]:
    """``(violations, n_checked, n_unmatched)``.

    A violation is an emitted lattice edge whose |Δz| exceeds the budget
    the SOLVE priced it at.  ``n_unmatched`` counts published edges an
    endpoint of which no emitted node carries — reported beside the
    count, because a dropped vertex is a lost measurement.

    ONE IMPLEMENTATION, TWO FAMILIES.  The AIRSIDE NO-STEP family
    (RULINGS 2026-08-27) prices its sidecar publication by exactly this
    rule — "solver publishes, census prices the same list" — so the body
    lives in :func:`_check_published_law_edges` and both families call
    it.  A second copy would be the census-wrapper defect in miniature:
    one law, two readers, nothing asserting they agree.
    """
    return _check_published_law_edges(
        lattice_edges_ll, lattice_ways, ways, nodes, ll_to_m)


def _check_published_law_edges(
        edges_ll, feature_ways, ways, nodes, ll_to_m
) -> Tuple[List[Violation], int, int]:
    """``(violations, n_checked, n_unmatched)`` for ANY sidecar-published
    law-edge list of ``{"a", "b", "budget_m"}`` records.

    A violation is an emitted pair whose |Δz| exceeds the budget the
    SOLVE priced it at.  ``n_unmatched`` counts published edges an
    endpoint of which no emitted node carries — reported beside the
    count, because a dropped vertex is a lost measurement.
    """
    lattice_edges_ll, lattice_ways = edges_ll, feature_ways
    if not lattice_edges_ll:
        return [], 0, 0
    # Emitted nodes that carry a value, indexed in metres.
    # The join population is the LATTICE WAYS FIRST (the open constrained
    # breaklines the emitter wrote — ``_parse_osm`` routes them to
    # ``feature_out``, never to ``ways``, so a ring-only population would
    # find none of them) and then every ordinary emitted ring, so a
    # lattice vertex that interned into a ring is still found.
    pts: List[Tuple[float, float, float, str]] = []
    alt_of: Dict[str, float] = {}
    way_of: Dict[str, "Way"] = {}
    for w in list(lattice_ways or []) + list(ways):
        for nid, a in zip(w.nids, (w.elevs or [None] * len(w.nids))):
            if a is None or nid not in nodes:
                continue
            alt_of.setdefault(nid, float(a))
            way_of.setdefault(nid, w)
    for nid, a in alt_of.items():
        lat, lon = nodes[nid]
        x, y = ll_to_m(lat, lon)
        pts.append((x, y, a, nid))
    if not pts:
        return [], 0, len(lattice_edges_ll)

    cell = max(1.0, _LATTICE_JOIN_TOL_M * 2.0)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for k, (x, y, _a, _n) in enumerate(pts):
        grid.setdefault((int(x // cell), int(y // cell)), []).append(k)

    def _find(x, y):
        best = None
        cx, cy = int(x // cell), int(y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((cx + dx, cy + dy), ()):
                    px, py, _a, _n = pts[k]
                    d = math.hypot(px - x, py - y)
                    if d <= _LATTICE_JOIN_TOL_M and (best is None
                                                     or d < best[0]):
                        best = (d, k)
        return None if best is None else best[1]

    out: List[Violation] = []
    n_checked = 0
    n_unmatched = 0
    for rec in lattice_edges_ll:
        try:
            a_ll = rec["a"]
            b_ll = rec["b"]
            budget = float(rec["budget_m"])
        except (KeyError, TypeError, ValueError):        # pragma: no cover
            n_unmatched += 1
            continue
        ax, ay = ll_to_m(float(a_ll[0]), float(a_ll[1]))
        bx, by = ll_to_m(float(b_ll[0]), float(b_ll[1]))
        ka, kb = _find(ax, ay), _find(bx, by)
        if ka is None or kb is None:
            n_unmatched += 1
            continue
        n_checked += 1
        za, zb = pts[ka][2], pts[kb][2]
        dz = abs(zb - za)
        excess = dz - budget
        if excess <= 0.0:
            continue
        dist = math.hypot(bx - ax, by - ay)
        grade = (100.0 * dz / dist) if dist > 1e-9 else 0.0
        cap = (100.0 * budget / dist) if dist > 1e-9 else None
        wa = way_of.get(pts[ka][3])
        wb = way_of.get(pts[kb][3])
        v = Violation(
            grade_pct=grade,
            excess_pct=(100.0 * excess / dist) if dist > 1e-9 else 0.0,
            distance_m=dist, de_m=dz,
            way_a=wa, way_b=wb,
            pt_a=(float(a_ll[0]), float(a_ll[1])),
            pt_b=(float(b_ll[0]), float(b_ll[1])),
            elev_a=za, elev_b=zb, cap_pct=cap)
        v.lat = 0.5 * (float(a_ll[0]) + float(b_ll[0]))
        v.lon = 0.5 * (float(a_ll[1]) + float(b_ll[1]))
        out.append(v)
    return out, n_checked, n_unmatched


# ── THE AIRSIDE NO-STEP LAW (owner ruling RULINGS 2026-08-27) ────────
# ONE REGISTER, never a hand list (spec §1.1): the same
# ``enclaves.ENCLAVE_AIRSIDE_ROLES`` the solve enumerates its airside
# nodes from, so the two readers cannot price different pavement.
try:                                                    # pragma: no cover
    from auto_patch.enclaves import (
        ENCLAVE_AIRSIDE_ROLES as _NO_STEP_AIRSIDE_ROLES)
except Exception:                                       # pragma: no cover
    _NO_STEP_AIRSIDE_ROLES = frozenset()

#: The role-less FEATURE classes that ARE airside membrane polylines
#: (spec §1.2, "lattice rows/columns, spine-station runs"): the emitted
#: open breaklines of the apron interior.  Ring sequences come from the
#: airside ROLE ways themselves.
_NO_STEP_POLYLINE_FEATURES: Tuple[str, ...] = (
    "apron_lattice", "apron_spine_station",
)


def _check_airside_no_step(no_step_edges_ll, feature_ways, ways, nodes,
                           ll_to_m) -> Tuple[List[Violation], int, int]:
    """§1.1 — the LOCAL DIRECT-DISTANCE grade rows.

    ``(violations, n_checked, n_unmatched)``.  The population is EXACTLY
    the solve's own sidecar publication (spec §1.6, the
    ``apron_lattice_membrane`` precedent: solver publishes, census prices
    the same list — one law, one population), so this is
    :func:`_check_published_law_edges` with the no-step list.  A pair
    whose |Δz| exceeds ``cap x DIRECT distance`` is the step the ruling
    forbids.
    """
    return _check_published_law_edges(
        no_step_edges_ll, feature_ways, ways, nodes, ll_to_m)


def _no_step_polylines(ways, feature_ways, nodes, ll_to_m):
    """``[(way, [(x, y), ...], [z, ...], closed), ...]`` — the airside
    membrane's own polylines (spec §1.2).

    Three classes, all emitted geometry, none re-derived: the apron
    LATTICE rows/columns and the spine-STATION runs (open breaklines,
    handed in as ``feature_ways``), and the RING SEQUENCES of every
    airside-role way.  A ring is genuinely cyclic, so its wrap-around
    triples are stations too.
    """
    out = []
    for w in list(feature_ways or []):
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(w.nids):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if ok and len(pts) >= 3:
            out.append((w, pts, zs, False))
    for w in list(ways or []):
        if w.role not in _NO_STEP_AIRSIDE_ROLES:
            continue
        nn = list(w.nids)
        closed = len(nn) > 1 and nn[0] == nn[-1]
        if closed:
            nn = nn[:-1]
        pts, zs = [], []
        ok = True
        for k, nid in enumerate(nn):
            if nid not in nodes:
                ok = False
                break
            pts.append(ll_to_m(*nodes[nid]))
            zs.append(w.elevs[k] if k < len(w.elevs) else None)
        if ok and len(pts) >= 3:
            out.append((w, pts, zs, closed))
    return out


def _check_airside_no_step_rate(ways, feature_ways, nodes, ll_to_m
                                ) -> Tuple[List[Violation], int, int]:
    """§1.2 — the RATE-OF-CHANGE rows: airside membrane stations whose
    grade CHANGE per unit length outruns the aerodrome's vertical-curve
    rate.

    ``(violations, n_stations, n_ways)``.

    THE MACHINERY IS THE STRIP FAMILY'S, EXTENDED — never forked (spec
    §1.2, "extend that machinery").  The rate comes from
    ``grade_law.airside_arc_rate_per_m`` (which IS the strip/runway
    constant, one source); the second-difference form, the per-row
    reader blind spot (``_rate_reader_blind_spot``) and the physical
    ``_site_key`` dedupe are the same three the ``strip_arc`` reader
    uses, for the same reasons.  ``max_slope`` is passed as infinite so
    only the ARC half of ``strip_longitudinal_breaches`` fires: the
    pointwise slope half is already every airside family's business, and
    counting it twice would be two instruments on one population.

    THE STATION COORDINATE is ARC LENGTH along the polyline — the direct
    analogue of the strip reader's along-axis coordinate, and the one an
    aircraft actually travels.
    """
    if (_strip_longitudinal_breaches is None
            or _airside_arc_rate_per_m is None):
        return [], 0, 0
    rate = _airside_arc_rate_per_m(_ACTIVE_RULESET)
    if not rate:
        return [], 0, 0
    out: List[Violation] = []
    n_stations = 0
    hit_ways: set = set()
    seen_sites: set = set()
    inf = float("inf")
    for (w, pts, zs, closed) in _no_step_polylines(
            ways, feature_ways, nodes, ll_to_m):
        idx = list(range(len(pts)))
        if closed:
            # The cyclic sequence, walked once with its two wrap triples.
            idx = idx + [0, 1]
        s = [0.0]
        for p in range(1, len(idx)):
            (xa, ya) = pts[idx[p - 1]]
            (xb, yb) = pts[idx[p]]
            s.append(s[-1] + math.hypot(xb - xa, yb - ya))
        z = [zs[i] for i in idx]
        n_stations += max(0, len(idx) - 2)
        for k in _strip_longitudinal_breaches(s, z, inf, rate):
            if k <= 0 or k >= len(idx) - 1:
                continue
            a, b, c = idx[k - 1], idx[k], idx[k + 1]
            if zs[a] is None or zs[b] is None or zs[c] is None:
                continue
            dp = abs(s[k] - s[k - 1])
            dn = abs(s[k + 1] - s[k])
            if dp < 1e-6 or dn < 1e-6:
                continue
            change = abs((float(zs[c]) - float(zs[b])) / dn
                         - (float(zs[b]) - float(zs[a])) / dp)
            allowed = rate * 0.5 * (dp + dn)
            if change - allowed <= _rate_reader_blind_spot(w, dp, dn):
                continue                    # PASS-with-residual
            site = _site_key(pts[a], pts[b], pts[c])
            if site in seen_sites:
                continue                    # one row per physical station
            seen_sites.add(site)
            hit_ways.add(w.wid)
            span = 0.5 * (dp + dn)
            out.append(Violation(
                grade_pct=100.0 * change,
                excess_pct=100.0 * (change - allowed),
                distance_m=span, de_m=abs(float(zs[c]) - float(zs[a])),
                way_a=w, way_b=w, pt_a=pts[a], pt_b=pts[c],
                elev_a=float(zs[a]), elev_b=float(zs[c])))
    out.sort(key=lambda v: -v.grade_pct)
    return out, n_stations, len(hit_ways)


def _check_drainage_spine_below_pavement(
        spine_ways: List[Way], ways: List[Way], nodes, ll_to_m
) -> Tuple[List[Violation], int, int]:
    """``(violations, n_checked, n_short_of_fall)``.

    A violation is a spine vertex at or ABOVE the lower of its two nearest
    airside pavement edges (cap 0 — a dam, not an over-cap grade); the
    reported ``de_m`` is how far above.  ``n_short_of_fall`` counts the
    vertices that ARE below but by less than ``DRAINAGE_SPINE_MIN_FALL_M``
    — reported, never failed, while that constant is provisional."""
    if not spine_ways:
        return [], 0, 0
    rings: List[Tuple[str, List[Tuple[float, float, float]]]] = []
    parent_by_wid: Dict[str, "Way"] = {}
    # F3c: the ENVELOPE FAMILY of each parent, resolved through the law's own
    # ``drainage_spine_parent_family`` (the same call
    # ``gap_fill._parent_family_code`` makes) so the handoff this reader
    # prices is composed from the same per-parent bounds the emitter used.
    family_by_wid: Dict[str, tuple] = {}
    for w in ways:
        if w.role not in _SPINE_AIRSIDE_ROLES:
            continue
        parent_by_wid[w.wid] = w
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        ring = []
        for k, nid in enumerate(nn):
            if nid not in nodes or k >= len(w.elevs) or w.elevs[k] is None:
                ring = []
                break
            x, y = ll_to_m(*nodes[nid])
            ring.append((x, y, float(w.elevs[k])))
        if len(ring) >= 3:
            rings.append((w.wid, ring))
            if _drainage_spine_parent_family is not None:
                # The runway code number keys off the shape's own longest
                # vertex chord — the emitter's proxy, no row-100 axis here.
                _long = None
                if w.role in ("runway", "runway_crossing"):
                    _long = 0.0
                    for _i in range(len(ring)):
                        for _j in range(_i + 1, len(ring)):
                            _d = math.hypot(ring[_j][0] - ring[_i][0],
                                            ring[_j][1] - ring[_i][1])
                            if _d > _long:
                                _long = _d
                family_by_wid[w.wid] = _drainage_spine_parent_family(
                    w.role, long_side_m=_long,
                    code_letter=w.tags.get("code_letter"))
    if len(rings) < 2:
        return [], 0, 0
    grid: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    c = _SPINE_PARENT_CELL_M
    for si, (_wid, ring) in enumerate(rings):
        for ei in range(len(ring)):
            a = ring[ei]
            b = ring[(ei + 1) % len(ring)]
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for gx in range(int(x0 // c), int(x1 // c) + 1):
                for gy in range(int(y0 // c), int(y1 // c) + 1):
                    grid.setdefault((gx, gy), []).append((si, ei))
    out: List[Violation] = []
    n_checked = 0
    n_short = 0
    # THE SPINE'S HOST (lead ruling 2026-08-07, ``drainage_parents``): a
    # gap spine's nodes are NEW ids shared with nothing, so the node-sharing
    # resolver cannot answer for it.  Its host shape is the bounding
    # pavement THIS LAW already selected — tallied per spine way here and
    # stamped below, so ``row_roles``/``row_side`` report the host instead
    # of the airside-by-default '?' the way carries.  Reporting only:
    # nothing in the law reads a spine way's role.
    host_tally: Dict[str, Dict[str, int]] = {}
    _BENCH_SLOPE = 0.05  # gap_fill._RING_ALONG_BENCH_SLOPE, the band's
    #                       own maximum down slope (one number, both
    #                       readers; gap_fill asserts the twin below).
    try:
        from auto_patch.gap_fill import _RING_ALONG_BENCH_SLOPE
        _BENCH_SLOPE = float(_RING_ALONG_BENCH_SLOPE)
    except Exception:
        pass
    for w in spine_ways:
        # F3b cone geometry: the way's arclength and its two END PINS
        # (the nearest bounding edge's interpolated elevation at each
        # end station — the emitter's conformed boundary read).
        _pts = []
        for nid in w.nids:
            _pts.append(ll_to_m(*nodes[nid]) if nid in nodes else None)
        _spine_s = None
        _spine_ends = None
        if all(p is not None for p in _pts) and len(_pts) >= 2:
            _spine_s = [0.0]
            for (ax, ay), (bx, by) in zip(_pts, _pts[1:]):
                _spine_s.append(_spine_s[-1] + math.hypot(bx - ax, by - ay))
            _ends = []
            for j in (0, -1):
                nj = _nearest_edge_alt_by_way(
                    _pts[j][0], _pts[j][1], rings, grid)
                # An end grants a descent cone only when it is itself
                # CONFORMED (within the band margin of its edge) — the
                # emitter's own reach; a far end never conformed and
                # grants nothing.
                _ends.append(nj[0][2] if nj
                             and nj[0][0] <= _GAP_CONFORM_MARGIN_M
                             else None)
            _spine_ends = _ends
        for k, nid in enumerate(w.nids):
            if nid not in nodes or k >= len(w.elevs) or w.elevs[k] is None:
                continue
            px, py = ll_to_m(*nodes[nid])
            z = float(w.elevs[k])
            near = _nearest_edge_alt_by_way(px, py, rings, grid)
            if len(near) < 2:
                continue
            n_checked += 1
            tally = host_tally.setdefault(w.wid, {})
            tally[near[0][1]] = tally.get(near[0][1], 0) + 1
            lower = min(near[0][2], near[1][2])
            # F3b staged law (gap-conformance spec): within the
            # conformance margin of its nearest bounding pavement the
            # spine is PINNED to that edge's value (the owner's
            # conformance ruling) — a band station is judged against
            # its pin, never the dam clause; the dam clause owns the
            # INTERIOR.  Same stage, same distance, as the emitter's
            # ``grade_law.drainage_spine_envelope``.
            if near[0][0] <= _GAP_CONFORM_MARGIN_M:
                if abs(z - near[0][2]) > SHARED_VERTEX_TOL_M:
                    out.append(Violation(
                        grade_pct=0.0, excess_pct=0.0,
                        distance_m=near[0][0], de_m=z - near[0][2],
                        way_a=w, way_b=w, pt_a=(px, py), pt_b=(px, py),
                        elev_a=z, elev_b=near[0][2]))
                continue
            # F3b interior ceiling: max(lower − FALL, cone floor) — a
            # spine lawfully DESCENDING from its higher conformed end
            # spends distance above the lower edge; the cone (the
            # emitter's own descent bound from each end pin at the
            # bench slope) is the lawful allowance for that, and the
            # dam clause binds once the descent could have arrived.
            cones = []
            if _spine_s is not None and _spine_ends is not None:
                if _spine_ends[0] is not None:
                    cones.append(_spine_ends[0]
                                 - _BENCH_SLOPE * _spine_s[k])
                if _spine_ends[1] is not None:
                    cones.append(_spine_ends[1] - _BENCH_SLOPE
                                 * (_spine_s[-1] - _spine_s[k]))
            # The dam line stays the LOWER EDGE (MIN_FALL is provisional
            # and never the pass/fail line, per this family's charter);
            # a lawful descent from a CONFORMED end raises the ceiling
            # along its cone.
            ceiling = lower
            if cones:
                ceiling = max(ceiling, max(cones))
            # F3c — THE GRADED HANDOFF.  Where this station's two parents'
            # envelopes do NOT intersect (the higher parent's crater floor
            # above the lower parent's dam ceiling), the emitter no longer
            # takes the nearer parent's interval: it descends from one
            # authority to the other, and this reader prices that SAME value
            # from the SAME law call.  ``handoff`` raises the ceiling only —
            # a station that passes the dam clause today cannot newly fail —
            # and where the separation is too short for a lawful descent the
            # law's own ``residual`` becomes the row (never silent).
            handoff, residual = _spine_handoff_here(
                near, family_by_wid, _BENCH_SLOPE)
            if handoff is not None:
                ceiling = max(ceiling, handoff)
            if z > ceiling + 0.11:
                out.append(Violation(
                    grade_pct=0.0, excess_pct=0.0,
                    distance_m=near[0][0], de_m=z - ceiling,
                    way_a=w, way_b=w, pt_a=(px, py), pt_b=(px, py),
                    elev_a=z, elev_b=ceiling))
            elif residual > _SPINE_HANDOFF_MATERIALITY_M:
                # PASS-with-residual is the sub-materiality case; this one is
                # above the floor, so the census carries it.
                out.append(Violation(
                    grade_pct=0.0, excess_pct=0.0,
                    distance_m=near[0][0], de_m=residual,
                    way_a=w, way_b=w, pt_a=(px, py), pt_b=(px, py),
                    elev_a=z, elev_b=z - residual))
            elif z > lower - _DRAINAGE_SPINE_MIN_FALL_M:
                n_short += 1
    for w in spine_ways:
        tally = host_tally.get(w.wid)
        if not tally or w.tags.get("role") or w.tags.get(HOST_ROLE_TAG):
            continue
        # The MODAL nearest parent over the spine's own censused stations;
        # ties to the lowest way id, so the answer never depends on dict
        # iteration order.
        host_wid = sorted(tally, key=lambda k: (-tally[k], str(k)))[0]
        host = parent_by_wid.get(host_wid)
        if host is None:
            continue
        w.tags[HOST_WAY_TAG] = str(host_wid)
        w.tags[HOST_ROLE_TAG] = host.tags.get("role") or ""
        w.tags[HOST_SOURCE_TAG] = "drainage_parents"
        w.tags[HOST_SHARED_NODES_TAG] = "0"
    out.sort(key=lambda v: -v.de_m)
    return out, n_checked, n_short


# ── TRANSVERSE (cross-corridor) GRADE (owner field report 2026-08-02) ──
# The law already exists — ICAO Annex 14 Vol I §3.9.11 caps the taxiway
# TRANSVERSE slope (config.py, ``TAXI_MAX_TRANSVERSE_NARROW``: 2 % at code
# A/B, and at C–F it coincides with the 1.5 % longitudinal cap, i.e.
# isotropic) — but NOTHING read it unconditionally.  Within-shape pairs
# bound transverse slope only INCIDENTALLY, so wherever pair selection
# drops the spine-to-edge pair (baked pair caps, the route-leg floor,
# visibility) the cross-section is unbounded: the owner flew a 4.17 m
# step across a 38 m corridor at ZERO reported violations.  This is a
# READER, not a new law: perpendicular transects at ``_TRANSVERSE_STEP_M``
# stations along the sidecar centrelines, the pavement span bracketing the
# station, elevations interpolated along the crossed RING EDGES (X-Plane
# renders a boundary edge linearly, so a boundary hit's z is exact — no
# interior triangulation is modelled and none is claimed).
#
# COVERAGE, stated honestly: only pavement a taxi centreline actually
# crosses is censused (pure apron interior and off-axis fillets are NOT in
# the population), and stations 10 m apart on one shape are correlated —
# so both the station count and the distinct-shape count are reported.
_TRANSVERSE_STEP_M = 10.0
_TRANSVERSE_HALF_M = 80.0
_TRANSVERSE_MIN_WIDTH_M = 3.0
#: How far the priced span's nearest hit may sit from the axis.  A span
#: whose near side is further out than this is not the corridor the axis
#: runs down, so the law does not price it.  NAMED because the emitter
#: reads the SAME number: ``lateral_spine_nodes._SPAN_MAX_GAP_M`` inserts
#: the pair this rule selects, and two copies of a span rule drifting is
#: the census-wrapper defect class (twin:
#: ``tests/test_lateral_cross_section.py``).
_TRANSVERSE_MAX_GAP_M = 1.0

# ── THE AXIS-KIND SCOPE — THE GENERATOR'S OWN TARGET ROLES ────────────
# WHICH shapes an axis prices, imported from the pass that plants the
# cross-sections (``auto_patch.lateral_spine_nodes``) rather than typed
# here: one list, two readers, no drift.  A TAXI axis prices the taxi
# lateral pass's targets; a SERVICE axis prices the SERVICE pass's
# targets — "a truck route is not an aircraft spine" (the rule below),
# and its mirror, an aircraft spine does not price a service road.
#
# WHY THIS IS NOT COSMETIC (S7 escalation, ruled 2026-08-14).  The set
# used to be one flat ``{junction, service_junction, apron}`` with a
# service-axis filter through ``_GROUNDSIDE_ROLES`` — which intersects
# to ``{service_junction}``, i.e. ``service_road`` was priced by NOBODY.
# Meanwhile ``lateral_spine_nodes.insert_service_lateral_nodes`` plants
# aligned cross-section vertices on service_road edges from the
# truck-route spine and ``grade_graph`` binds them across the route at
# ``SERVICE_ROAD_MAX_TRANSVERSE`` (``service_road`` joins
# ``SOFT_VISIBILITY_ROLES`` under ``config.SVC_SPINE_FIRST``, default
# ON).  A GENERATION-BINDING CONSTRAINT WHOSE VALIDATOR READ NOTHING:
# the CYXY cross-road tear the emitter was built to make unrepresentable
# censused zero.  The cap itself never needed changing — it already
# resolves through ``_transverse_cap_for_seg_cap`` →
# ``config.transverse_cap_for_longitudinal_cap``, the one law source
# ``grade_graph._bake_edge`` binds with.
try:
    from auto_patch.lateral_spine_nodes import (
        TAXI_AXIS_PRICED_ROLES as _LAT_TAXI_PRICED_ROLES,
        SERVICE_AXIS_PRICED_ROLES as _LAT_SERVICE_PRICED_ROLES,
    )
except Exception:                                      # pragma: no cover
    # The standalone (no-``auto_patch``) path this module keeps for every
    # constant it imports.  Kept in sync by
    # ``tests/test_lateral_cross_section.py``.
    _LAT_TAXI_PRICED_ROLES = frozenset({"junction", "service_junction",
                                        "apron"})
    _LAT_SERVICE_PRICED_ROLES = frozenset({"service_road",
                                           "service_junction"})
_TRANSVERSE_TAXI_ROLES = frozenset(_LAT_TAXI_PRICED_ROLES)
_TRANSVERSE_SERVICE_ROLES = frozenset(_LAT_SERVICE_PRICED_ROLES)
#: The union — WHICH shapes are gathered at all.  The per-axis scope
#: above decides which of them a given axis may censure.
_TRANSVERSE_ROLES = _TRANSVERSE_TAXI_ROLES | _TRANSVERSE_SERVICE_ROLES


# ── LATERAL CONTIGUITY (owner-confirmed FINAL 2026-08-02) ──────────────
# The VALIDATOR TWIN of ``groundside.apply_lateral_contiguity_law``, and the
# reason the pair is law rather than visibility (grade-law completeness
# standard, 2026-08-02: "our grade law must not allow us to GENERATE a patch
# that violates any of the region-appropriate regulations" — every
# requirement needs a generation-binding constraint AND its validator twin).
# The existing ``o4_grade_law`` / ``o4_grade_law_cap`` readers only trust the
# tag the build stamped: a piece the emitter FAILED to cap reads clean.  This
# check re-derives the law from the emitted geometry instead — at every
# station of every road-family way it takes the laterally-contiguous paved
# cross-section, asks the LAW for the strictest cap present
# (``grade_law.lateral_contiguity_cap`` — the same function the emitter
# used), and flags the station when the way's effective cap is looser.
_LATERAL_STEP_M = 5.0
_LATERAL_PROBE_M = 60.0
_LATERAL_GAP_TOL_M = 0.05
_LATERAL_MIN_MEMBER_M = 0.5
_LATERAL_ROAD_ROLES = frozenset({"service_road", "service_junction"})


def _check_lateral_contiguity(ways: List[Way], nodes, ll_to_m
                              ) -> Tuple[List[Violation], int, int]:
    """``(violations, n_stations, n_shapes)`` — road-family stations whose
    laterally-contiguous cross-section holds a STRICTER class than the cap
    the way is validated at.

    The station walk is ``auto_patch.lateral_contiguity.station_caps`` — the
    SAME call the emitter makes, so this reader cannot census a station the
    emitter never saw.  ``de_m`` carries the cap excess so the worst
    offenders sort first.
    """
    try:
        from shapely.geometry import Polygon
        from shapely.strtree import STRtree
        from auto_patch.lateral_contiguity import ROAD_ROLES, station_caps
    except Exception:
        return [], 0, 0
    rows = []
    for w in ways:
        if ROLE_GRADE_LIMITS.get(w.role) is None:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        ring = [ll_to_m(*nodes[n]) for n in nn if n in nodes]
        if len(ring) < 3:
            continue
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            continue
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        rows.append((w, poly))
    if not rows:
        return [], 0, 0
    polys = [p for _w, p in rows]
    roles = [w.role for w, _p in rows]
    tree = STRtree(polys)
    # Clause (5): the runway-strip footprint law supersedes inside strips —
    # the SAME keepout the emitter skips its stations on, from the SAME law
    # geometry (``grade_law.runway_strip_wall_keepout_rings``).
    keepout = None
    strip_rings = _runway_strip_keepout_rings(ways, nodes, ll_to_m)
    if strip_rings:
        try:
            from shapely.ops import unary_union
            keepout = unary_union([Polygon(r) for r in strip_rings])
        except Exception:
            keepout = None
    out: List[Violation] = []
    n_stations = 0
    shapes_flagged = set()
    for i, (w, poly) in enumerate(rows):
        if w.role not in ROAD_ROLES:
            continue
        eff = _role_grade_limit(w, ROLE_GRADE_LIMITS.get(w.role) or 0.05)
        if eff is None:
            continue
        stations, caps = station_caps(poly, tree, polys, roles, i,
                                      keepout=keepout)
        for st, law_cap in zip(stations, caps):
            if st is None or law_cap is None:
                continue
            n_stations += 1
            if eff <= law_cap + 1e-12:
                continue
            shapes_flagged.add(w.wid)
            out.append(Violation(
                grade_pct=100.0 * eff, excess_pct=100.0 * (eff - law_cap),
                distance_m=0.0, de_m=eff - law_cap,
                way_a=w, way_b=w, pt_a=st, pt_b=st,
                elev_a=0.0, elev_b=0.0))
    out.sort(key=lambda v: -v.de_m)
    return out, n_stations, len(shapes_flagged)


def _axes_to_m(taxi_axes_ll: Optional[list], ll_to_m) -> Optional[list]:
    """The sidecar's taxi axes in the audit's METRE frame, SLOTS INTACT.

    THE SLOTS ARE THE READER'S CONTRACT.  ``law_context_from_sidecar``
    emits ``(pts, seg_caps, None, route_ordinal, is_service)``: the 4th
    slot is the builder's route ordinal (identity binding), the 5th is the
    sidecar's IS_SERVICE flag — a truck route is not an aircraft spine
    (``grade_graph._reads_service_spines``), and both metre-frame readers
    of that flag (``_grade_context_from_osm``'s ``Centerline.is_service``
    and ``_check_transverse_grade``'s ``_axis_is_svc``) resolve it by
    POSITION.

    This conversion used to truncate the tuple at 4, so the flag never
    arrived, every axis read as an aircraft spine, and the service-axis
    rule those readers each state never fired once.  The transverse law is
    the one that mints rows off it: a service axis stamped apron
    cross-sections it has no spine for (measured HECA, arms b6936ed /
    0c003ba after the road feed joined the graph — ``transverse::apron|
    apron`` 10 000 m 57 -> 185 and 69 -> 205, −500 m 62 -> 210 and
    54 -> 197; 555 rows over the four patches, every one traceable to a
    service axis).  A legacy 3- or 4-slot sidecar keeps its own length and
    reads as all-taxi, which is how it was graded.

    Degenerate (<2 point) axes are dropped, as they always were.
    """
    if not taxi_axes_ll:
        return None
    out: List[tuple] = []
    for entry in taxi_axes_ll:
        latlon_pts, cL, cT = entry[0], entry[1], entry[2]
        poly = [ll_to_m(lat, lon) for (lat, lon) in latlon_pts]
        if len(poly) < 2:
            continue
        if len(entry) < 4:
            out.append((poly, cL, cT))
        elif len(entry) < 5:
            out.append((poly, cL, cT, entry[3]))
        else:
            out.append((poly, cL, cT, entry[3], bool(entry[4])))
    return out


def _transverse_cap_for_seg_cap(cap_l: float) -> float:
    """The TRANSVERSE cap ``cT`` for a centreline segment whose emitted
    LONGITUDINAL cap is ``cap_l`` — the sidecar carries the longitudinal
    cap per segment, and the transverse cap is a pure function of the same
    role/letter (config.py ``taxi_transverse_cap_for_letter`` /
    ``SERVICE_ROAD_MAX_TRANSVERSE``): code A/B 3 %∥ → 2 %⊥, service road
    8 %∥ → 2 %⊥ (owner constant 2026-08-03), everything else ISOTROPIC
    (C–F 1.5 %).

    ONE LAW SOURCE (2026-08-08): the three branches live in
    ``auto_patch.config.transverse_cap_for_longitudinal_cap`` and this
    validator DELEGATES to them, as ``grade_graph._bake_edge`` and the
    emitter's cross-section pair budget do.  Cross-section pairs are now
    BOUND in the solve at this cap (priced ⟺ bound, LEAD RULINGS 2
    ruling 1), so a drifted second copy would bind one number and price
    another — the census-wrapper defect class, one law with two readers.
    The literal fallback below is the no-``auto_patch`` path this module
    already keeps for every other constant it imports."""
    if _transverse_cap_law is not None:
        return float(_transverse_cap_law(cap_l))
    if abs(cap_l - TAXI_MAX_GRADE_NARROW) < 1e-9:
        return TAXI_MAX_TRANSVERSE_NARROW
    if abs(cap_l - SERVICE_ROAD_MAX_GRADE) < 1e-9:
        return SERVICE_ROAD_MAX_TRANSVERSE
    return cap_l


try:
    from auto_patch import transect_walk as _TW
except Exception:                                      # pragma: no cover
    _TW = None


#: How far an emitted interpolated height may sit from the height the
#: solve BOUND before the span counts as broken by the emit stage.  The
#: decimation z-tolerance (spec AMENDMENT A1 section 8c); a collinear
#: insert is height-neutral by construction, which the walker's own twin
#: asserts, so anything above this came from a repair that MOVED the
#: boundary — needle drops, on-edge moves, sliver repairs, decimation.
BROKEN_BY_EMIT_TOL_M = 0.02


def transverse_bind_report(stations, xsection_spans):
    """``(priced, bound, unbound, broken, worst)`` — the lockstep line
    (spec section 12 + AMENDMENT A1 section 8c).

    ``stations`` are the census's own priced stations, walked on the
    EMITTED ring; ``xsection_spans`` are the spans the FINAL PROJECTION
    bound, walked on the ring it saw, carried in the sidecar.  They are
    joined on ``station_id`` — never by proximity — and every bound span
    is re-evaluated against the emitted heights: ``broken`` counts the
    ones the emit stage moved by more than ``BROKEN_BY_EMIT_TOL_M``.

    The number is the deliverable, not a verdict: it is what decides
    whether the topology-only emit repairs have to move ahead of the
    final projection ("nothing moves after the final projection", a
    separate spec).  This round REPORTS it."""
    priced = len(stations)
    if not xsection_spans:
        return priced, 0, priced, 0, 0.0
    by_id: dict = {}
    for sp in xsection_spans:
        try:
            by_id.setdefault(tuple(sp["station_id"])[:3], []).append(sp)
        except Exception:                              # pragma: no cover
            continue
    bound = broken = 0
    worst = 0.0
    for st in stations:
        # JOIN ON THE AXIS GEOMETRY (axis, segment, station) — the part
        # both readers derive from the SAME sidecar axes.  The shape
        # ordinal is reader-local (a way id here, a ring index there) and
        # deliberately stays out of the key; where one station prices two
        # shapes the nearest WIDTH disambiguates, and the width is a
        # property of the span, not of either reader's numbering.
        cands = by_id.get(tuple(st.station_id[:3])) or []
        if not cands:
            continue
        sp = min(cands, key=lambda q: abs(float(q.get("width_m", 0.0))
                                          - float(st.width_m)))
        bound += 1
        try:
            d = max(abs(float(st.z_lo) - float(sp["z_lo"])),
                    abs(float(st.z_hi) - float(sp["z_hi"])))
        except Exception:                              # pragma: no cover
            continue
        if d > BROKEN_BY_EMIT_TOL_M:
            broken += 1
            worst = max(worst, d)
    return priced, bound, priced - bound, broken, worst


def _transverse_span_budget(cap_l: float, width_m: float) -> float:
    """THE cross-section budget, from THE law function
    (``grade_law.transverse_span_budget_m``) — the same product the solve's
    cross-section binding uses (spec ``transverse-hyperplane-solve-spec.md``
    step 1, owner ruling 2026-08-21).  This reader adds its own encoding
    envelope on top; the law states the budget only.

    The literal fallback is the no-``auto_patch`` path this module keeps
    for every constant it imports, and it composes the SAME two factors
    through this module's own cap resolver."""
    if _transverse_span_budget_law is not None:
        return float(_transverse_span_budget_law(cap_l, width_m))
    return _transverse_cap_for_seg_cap(cap_l) * float(width_m)


def _check_transverse_grade(ways: List[Way], nodes, ll_to_m, taxi_axes,
                            terrace_joints_m: Optional[list] = None,
                            stations_out: Optional[list] = None
                            ) -> Tuple[List[Violation], int, int, int]:
    """``(violations, n_stations, n_rows, n_shapes)`` — every censused
    corridor cross-section steeper than its transverse cap.

    THE STATION SET IS NOT THIS READER'S OWN (spec
    ``transverse-hyperplane-solve-spec.md`` step 2, owner ruling
    2026-08-21).  Where the walk used to live inline here it now comes
    from ``auto_patch.transect_walk.walk_transects`` — the ONE walker the
    solve's cross-section binding reads too, because the owner moved this
    family into the solve and a bound span that is not a priced station
    buys nothing.  Two walks cannot be asserted equal by comparing
    constants; one walk is equal by construction
    (``tests/test_transect_walk.py``).

    What stays HERE is this reader's own forgiveness: the quantization
    allowance (``_pair_quant_noise_m`` on the crossed way — the two hits
    are ring vertices interpolated along ring edges, the identical
    emit/weld envelope; without it a 0.1 m weld quantum across a 23 m
    taxiway reads as 0.43 % of phantom transverse grade) and the declared
    apron-terrace step.  The BUDGET is the shared law function.

    ``stations_out`` (optional list) receives every walked station, so a
    caller can join the priced population to the sidecar's bound spans
    (the ``priced / bound / unbound`` line) without walking twice."""
    if not taxi_axes:
        return [], 0, 0, 0
    if _TW is None:                                    # pragma: no cover
        return [], 0, 0, 0
    by_key: Dict[object, "Way"] = {}
    tshapes: List = []
    for w in ways:
        if w.role not in _TRANSVERSE_ROLES:
            continue
        nn = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
              else w.nids)
        ring = []
        for k, nid in enumerate(nn):
            if nid not in nodes or k >= len(w.elevs) or w.elevs[k] is None:
                ring = []
                break
            x, y = ll_to_m(*nodes[nid])
            ring.append((x, y, float(w.elevs[k])))
        if len(ring) >= 3:
            key = (str(w.wid), len(tshapes))
            by_key[key] = w
            tshapes.append(_TW.TransectShape(role=w.role, ring=ring,
                                             key=key))
    if not tshapes:
        return [], 0, 0, 0
    taxes = []
    for entry in taxi_axes:
        taxes.append(_TW.TransectAxis(
            poly=entry[0], seg_caps=entry[1],
            is_service=bool(entry[4]) if len(entry) > 4 else False))

    # A TRUCK ROUTE IS NOT AN AIRCRAFT SPINE (cycle 9; lockstep with
    # ``grade_graph._reads_service_spines``).  A service axis may only
    # censure the road family's own shapes — otherwise a road passing an
    # apron stamps the apron with a cross-section it has no spine for
    # (measured: ``transverse::apron|apron`` +176 at HECA 10 000 when the
    # road feed joined the graph).  The scope is the LATERAL PASS'S OWN
    # target roles, so priced ⟺ planted in BOTH directions.
    def _priced_roles(axis):
        return (_TRANSVERSE_SERVICE_ROLES if axis.is_service
                else _TRANSVERSE_TAXI_ROLES)

    out: List[Violation] = []
    n_rows = 0
    hit_shapes: set = set()
    counted: list = []
    for st in _TW.walk_transects(tshapes, taxes, _priced_roles,
                                 station_count=counted):
        way = by_key[st.shape_key]
        n_rows += 1
        hit_shapes.add(way.wid)
        if stations_out is not None:
            stations_out.append(st)
        width = st.width_m
        dz = st.dz
        # THE ONE LAW FUNCTION, BOTH READERS (spec step 1) — plus this
        # reader's own encoding envelope.
        allow = (_transverse_span_budget(st.cap_l, width)
                 + _pair_quant_noise_m(way))
        # APRON TERRACE LOCKSTEP.  A cross-section whose two hits sit on
        # OPPOSITE sides of a declared joint has a DECLARED step between
        # them — the same fact the within-pair reader already forgives,
        # read by a different instrument.  Leaving it out left the
        # transverse check as the last joint-blind reader: KCLT and HEAZ
        # each returned cross-sections whose own |dz| was BELOW the
        # declared step of the joint they span, reported as defects.  One
        # declared population, one number, every reader.
        if terrace_joints_m:
            pa, pb = st.point_lo(), st.point_hi()
            allow += _terrace_step_allowance(terrace_joints_m,
                                             pa[0], pa[1], pb[0], pb[1])
        if dz <= allow:
            continue
        pa, pb = st.point_lo(), st.point_hi()
        out.append(Violation(
            grade_pct=100.0 * dz / width,
            excess_pct=100.0 * (dz - allow) / width,
            distance_m=width, de_m=dz,
            way_a=way, way_b=way,
            pt_a=pa, pt_b=pb,
            elev_a=st.z_lo, elev_b=st.z_hi))
    out.sort(key=lambda v: -v.grade_pct)
    n_stations = counted[0] if counted else 0
    return out, n_stations, n_rows, len(hit_shapes)



def _check_strip_seam_tears(
    vertices: List[Vertex],
    ways: List[Way],
    radius_m: float = STRIP_SEAM_TEAR_RADIUS_M,
    min_step_m: float = STRIP_SEAM_TEAR_MIN_STEP_M,
    min_distance_m: float = STRIP_SEAM_TEAR_MIN_DISTANCE_M,
    open_boundary_floor_m: float = STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M,
) -> List[Violation]:
    """DEM-free SEAM-tear sentinel BETWEEN two different ``graded_strip``
    shapes — the cross-shape twin of ``_check_adjacent_ground_edges``.

    A single strip drapes terrain and carries no lawful grade cap, so a
    steep edge WITHIN one strip is not provably wrong DEM-free.  But two
    distinct strips that meet along a seam must AGREE in elevation where
    their nodes fall near-adjacent: a metre-plus altitude step across a
    sub-``radius_m`` gap is a clip / weld discontinuity (the in-sim "sharp
    cliff"), which no lawful terrain drape produces (real terracing steps
    between neighbouring strips stay ~0.3 m — see the module constants).

    A pair qualifies when the two nodes belong to DIFFERENT strip ways
    (same-way pairs are the within-shape check's business), their planar
    distance is under ``radius_m``, their absolute altitude difference is
    over ``min_step_m``, AND the implied grade exceeds
    ``STRIP_SEAM_TEAR_MIN_GRADE`` (steep-relief airports hold lawful
    metre-plus deltas between strips several metres apart — hillside
    drape — while true seam cliffs run far past 50 %; an exactly-interned
    shared node carries one value, so a same-coordinate pair with a real
    delta is a stacked bare WALL and is flagged).  Ways that carry the same
    ``shapeID`` are treated as one shape (a strip emitted as several ways)
    and skipped.

    WALL-SPANNED EXEMPTION (no-stacked-nodes unit, 2026-07-19): a level
    change between two strips rendered as DELIBERATE wall geometry — a
    ``retaining_wall`` way referencing BOTH endpoints (its top row welds
    the upper strip's chain, its bottom row the retreated lower strip)
    — is the ruling's sanctioned form, not a bare tear; the face fills
    the gap the bare-seam reading assumes empty.

    STRADDLE form (HECA, 2026-08-01): the same sanctioned face also sits
    BETWEEN two nodes neither of which the wall references — a pavement
    weld vertex metres up-slope paired against the wall's own bottom row.
    A pair is straddle-exempt when a ``retaining_wall`` segment crosses
    the pair's INTERIOR (within ``STRIP_SEAM_WALL_STRADDLE_TOL_M``, the
    contact point off both endpoints), that wall way's elevation range
    brackets both pair altitudes to within one step floor, AND ungraded
    ground lies between the two nodes — the pair's connecting segment
    must leave the graded domain (``STRIP_SEAM_GRADED_ROLES`` polygons)
    by more than ``STRIP_SEAM_OPEN_GROUND_MIN_M``.  That last clause is
    the owner's law: the exemption is for the graded→DEM terrace in OPEN
    ground, so a tear INTERIOR to graded ground (corridor zones 1-2, or a
    filled pocket) is never dissolved by a wall face that happens to
    cross it.

    OPEN-BOUNDARY FLOOR (PROVISIONAL, owner 2026-08-01): that same
    open-ground test now also sets the pair's STEP FLOOR.  A pair with
    ungraded ground in its interior sits at the graded→DEM boundary and
    is reported only past ``open_boundary_floor_m``
    (``STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M``, 15 m) — the owner is judging
    unwalled terraces in the simulator and raised the floor until then.
    A pair whose interior stays graded keeps ``min_step_m`` (1 m).  The
    wall exemptions above are unchanged and still run for pairs that
    clear the floor.

    Runs in ~linear time via a spatial grid over the strip nodes (never an
    O(n^2) all-pairs scan — airports reach ~50k strip nodes).  Returns
    ``Violation`` rows (``grade_pct`` = the seam's near-vertical grade),
    worst-step first."""
    # Restrict to strip vertices carrying a known elevation, keeping a map
    # back to the global vertex index only for readability of intent.
    strip_vertices: List[Vertex] = [
        v for v in vertices
        if v.elev is not None
        and ways[v.way_idx].tags.get("role") == STRIP_SEAM_ROLE
    ]
    if len(strip_vertices) < 2:
        return []
    # Wall-vertex registry for the wall-spanned exemption: coordinate
    # key -> set of retaining_wall way indices referencing it.  Wall
    # rows are emitted at the exact canonical coordinates of the chains
    # they weld, so exact (cm-rounded) matching suffices.
    wall_keys: Dict[Tuple[int, int], set] = defaultdict(set)
    for v in vertices:
        if ways[v.way_idx].tags.get("role") == "retaining_wall":
            wall_keys[(round(v.x * 100), round(v.y * 100))].add(v.way_idx)

    def _wall_spans(a: Vertex, b: Vertex) -> bool:
        wa = wall_keys.get((round(a.x * 100), round(a.y * 100)))
        if not wa:
            return False
        wb = wall_keys.get((round(b.x * 100), round(b.y * 100)))
        return bool(wb) and bool(wa & wb)

    cell = max(radius_m, 0.5)

    # Straddle exemption: the wall's own FACE segments, plus the per-way
    # elevation range the face spans.  Wall vertices arrive in ring order
    # per way, so consecutive same-way entries are the face's segments.
    #
    # RING-CLOSING FACE (2026-08-01): ``_build_vertex_edge_tables`` drops
    # a closed ring's repeated last node, so walking the vertex table
    # alone MISSES each wall ring's closing segment — its end cap, a real
    # emitted face.  Close every wall ring here, exactly as that function
    # closes every ring for its EDGE table.  (Measured: production walls
    # are 100 % closed rings — 95/95 across the four battery patches.)
    wall_segs: List[Tuple[float, float, float, float, int]] = []
    wall_elev_range: Dict[int, Tuple[float, float]] = {}
    if wall_keys:
        wall_pts: Dict[int, List[Tuple[float, float]]] = defaultdict(list)
        for v in vertices:
            if ways[v.way_idx].tags.get("role") != "retaining_wall":
                continue
            wall_pts[v.way_idx].append((v.x, v.y))
            if v.elev is not None:
                lo, hi = wall_elev_range.get(
                    v.way_idx, (v.elev, v.elev))
                wall_elev_range[v.way_idx] = (
                    min(lo, v.elev), max(hi, v.elev))
        for w_idx, pts in wall_pts.items():
            for k in range(len(pts) - 1):
                wall_segs.append((pts[k][0], pts[k][1],
                                  pts[k + 1][0], pts[k + 1][1], w_idx))
            if len(pts) > 2 and pts[-1] != pts[0]:
                wall_segs.append((pts[-1][0], pts[-1][1],
                                  pts[0][0], pts[0][1], w_idx))
    # The wall-face index and the straddle predicate now live in the ONE
    # strip-seam law module (spec seam-continuity-v2 §1) — same grid, same
    # cell, same tolerance; imported, never re-derived.
    wall_faces = _WallFaces(wall_segs, wall_elev_range, cell)

    # The graded domain, for the open-ground clause.  Ring points come
    # from the vertex table (closing repeat already dropped), so each
    # entry is the way's ring in order.
    #
    # BUILT UNCONDITIONALLY since the open-boundary floor (2026-08-01).
    # Under the straddle-only v2 the domain was reachable only from
    # ``_wall_straddles`` and was built under ``if wall_keys``; the floor
    # gates EVERY pair, and an empty domain answers "not covered" to every
    # query — which would read every pair as open boundary and silence a
    # wall-free patch's tears wholesale.  The guard is not an optimisation
    # to restore.
    _graded_ring_pts: Dict[int, List[Tuple[float, float]]] = defaultdict(list)
    for v in vertices:
        if ways[v.way_idx].tags.get("role") in STRIP_SEAM_GRADED_ROLES:
            _graded_ring_pts[v.way_idx].append((v.x, v.y))
    graded_domain = _GradedDomain(
        [pts for pts in _graded_ring_pts.values() if len(pts) >= 3],
        STRIP_SEAM_OPEN_GROUND_MIN_M)

    def _open_ground_between(a: Vertex, b: Vertex) -> bool:
        """Does UNGRADED ground lie between the two nodes?  The shared
        law's predicate (``strip_seam_law.open_ground_between``), bound to
        this instrument's vertex type."""
        return _open_ground_between_law(graded_domain, a.x, a.y, b.x, b.y)

    def _wall_straddles(a: Vertex, b: Vertex, open_ground: bool) -> bool:
        """The shared law's STRADDLE predicate
        (``strip_seam_law.WallFaces.straddles``), bound to this
        instrument's vertex type and step floors."""
        return wall_faces.straddles(
            a.x, a.y, a.elev, b.x, b.y, b.elev,
            open_ground=open_ground, min_step_m=min_step_m,
            min_distance_m=min_distance_m)

    grid = _bucket_vertices(strip_vertices, cell)
    out: List[Violation] = []
    for v_local, v in enumerate(strip_vertices):
        cx = int(math.floor(v.x / cell))
        cy = int(math.floor(v.y / cell))
        for dcx in (-1, 0, 1):
            for dcy in (-1, 0, 1):
                bucket = grid.get((cx + dcx, cy + dcy))
                if not bucket:
                    continue
                for u_local in bucket:
                    if u_local <= v_local:
                        continue  # each unordered pair considered once
                    u = strip_vertices[u_local]
                    if u.way_idx == v.way_idx:
                        continue  # same strip — within-shape check owns it
                    way_v = ways[v.way_idx]
                    way_u = ways[u.way_idx]
                    shape_v = way_v.tags.get("shapeID")
                    shape_u = way_u.tags.get("shapeID")
                    if shape_v is not None and shape_v == shape_u:
                        continue  # one strip emitted as several ways
                    d = math.hypot(v.x - u.x, v.y - u.y)
                    if d >= radius_m:
                        continue  # too far apart to be a seam
                    de = abs(v.elev - u.elev)
                    # THE PAIR PREDICATE — one arithmetic, shared with the
                    # healer's guard allowance (v4 §1,
                    # ``strip_seam_law.seam_pair_is_tear`` /
                    # ``seam_guard_allowance_m``).  Value-identical to the
                    # two inline conjuncts it replaces.
                    if not _seam_pair_is_tear(
                            de, d, min_step_m=min_step_m,
                            min_grade=STRIP_SEAM_TEAR_MIN_GRADE,
                            min_distance_m=min_distance_m):
                        continue  # lawful terrace step / noise, or a
                        # steep-terrain drape rather than a cliff
                    grade = de / max(d, min_distance_m)
                    if _wall_spans(v, u):
                        continue  # deliberate retaining_wall face
                    # The open-ground test is now BOTH the straddle
                    # exemption's precondition and the pair's step-floor
                    # selector, so compute it once.
                    open_ground = _open_ground_between(v, u)
                    if open_ground and de <= open_boundary_floor_m:
                        continue  # graded→DEM terrace, under the
                        # PROVISIONAL open-boundary floor (owner
                        # 2026-08-01, pending in-sim review)
                    if _wall_straddles(v, u, open_ground):
                        continue  # face crosses BETWEEN the two nodes,
                        # and ungraded ground lies between them
                    out.append(Violation(
                        grade_pct=grade * 100,
                        excess_pct=grade * 100,
                        distance_m=d,
                        de_m=de,
                        way_a=way_v, way_b=way_u,
                        pt_a=(v.x, v.y), pt_b=(u.x, u.y),
                        elev_a=v.elev, elev_b=u.elev))
    out.sort(key=lambda v: -v.de_m)
    return out


# ── Stacked-node invariant ──────────────────────────────────────
# OWNER RULING 2026-07-19: nodes can NEVER be stacked — two distinct
# OSM node ids at the same coordinate are illegal regardless of their
# elevations ("if they are in the same spot they must be merged and
# share the same elevation").  A genuine level change must be emitted
# as HORIZONTAL wall geometry (two node columns offset in plan — the
# retaining_wall machinery), never as coincident nodes with different
# elevations (those render as bare near-vertical mesh tears: the CYXY
# d=0.00 audit pairs, the SPLP seam site).  Cap is ZERO.
#
# The emitter's canonical-point registry spaces distinct points by its
# 0.5 m proximity tolerance, and stacked twins are emitted at the
# IDENTICAL canonical lat/lon — so anything under this radius is "the
# same spot" with wide margin, not a near-adjacent pair (those belong
# to the proximity / seam checks).
STACKED_NODE_XY_TOL_M = 0.05
# Two nodes at one spot violate the invariant when their ELEVATIONS
# differ — "they must be merged and share the same elevation".  A
# same-value coordinate twin is a legal OSM-encoding artifact (an OSM
# ring cannot reference one node id twice, so a figure-8 revisit emits
# a twin carrying identical claims; the mesh welds by coordinates into
# ONE vertex with one elevation — no tear exists).  Emitted altitudes
# are rounded to 0.1 m, so anything above this noise floor is a real
# disagreement.
STACKED_NODE_ALT_TOL_M = 0.05


def _check_stacked_nodes(
    vertices: List[Vertex],
    ways: List[Way],
    xy_tol_m: float = STACKED_NODE_XY_TOL_M,
    alt_tol_m: float = STACKED_NODE_ALT_TOL_M,
) -> List[Violation]:
    """STRUCTURAL stacked-node detector (owner invariant 2026-07-19).

    Flags every pair of DISTINCT node ids lying within ``xy_tol_m`` of
    each other whose claimed elevations disagree by more than
    ``alt_tol_m`` — one Violation row per node pair.  Same-value
    coordinate twins (the figure-8 OSM-encoding artifact) and
    elevation-less pairs (both drape onto the DEM — one surface) are
    NOT violations: the invariant is about the rendered surface, and
    those weld into one mesh vertex.  Works identically on test-DEM
    and production-DEM builds: the invariant is structural, so it
    needs no per-airport calibration and no DEM.

    Linear-time via the shared spatial grid; never an all-pairs scan.
    """
    # One entry per node id: representative coordinate, every elevation
    # claimed for it across referencing ways, a representative way.
    by_nid: Dict[str, list] = {}
    for v in vertices:
        entry = by_nid.get(v.nid)
        if entry is None:
            by_nid[v.nid] = [v.x, v.y, [] if v.elev is None else [v.elev],
                             v.way_idx]
        elif v.elev is not None:
            entry[2].append(v.elev)
    entries = [(nid, e[0], e[1], e[2], e[3])
               for nid, e in by_nid.items()]
    if len(entries) < 2:
        return []
    cell = 0.5
    grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for i, (_nid, x, y, _elevs, _w) in enumerate(entries):
        grid[(int(math.floor(x / cell)), int(math.floor(y / cell)))].append(i)
    out: List[Violation] = []
    for i, (nid_a, xa, ya, elevs_a, way_a) in enumerate(entries):
        cx = int(math.floor(xa / cell))
        cy = int(math.floor(ya / cell))
        for dcx in (-1, 0, 1):
            for dcy in (-1, 0, 1):
                for j in grid.get((cx + dcx, cy + dcy), ()):
                    if j <= i:
                        continue  # each unordered pair once
                    (nid_b, xb, yb, elevs_b, way_b) = entries[j]
                    d = math.hypot(xa - xb, ya - yb)
                    if d > xy_tol_m:
                        continue
                    if not elevs_a or not elevs_b:
                        continue  # both drape the DEM — one surface
                    elev_a = sum(elevs_a) / len(elevs_a)
                    elev_b = sum(elevs_b) / len(elevs_b)
                    de = abs(elev_a - elev_b)
                    if de <= alt_tol_m:
                        continue  # same-value encoding twin — merged in mesh
                    grade = de / max(d, 0.01)
                    out.append(Violation(
                        grade_pct=grade * 100,
                        excess_pct=grade * 100,
                        distance_m=d,
                        de_m=de,
                        way_a=ways[way_a], way_b=ways[way_b],
                        pt_a=(xa, ya), pt_b=(xb, yb),
                        elev_a=elev_a, elev_b=elev_b))
    out.sort(key=lambda v: -v.de_m)
    return out


# ── APRON TERRACE LAW — the validator twin (owner ruling 2026-08-04;
# spec ``docs/specs/apron-terrace-law-spec.md`` §5) ──────────────────
# The emitter half is
# ``elevation_per_surface.route_profile.apron_terrace``; the joints
# themselves arrive through the ``terrace_joints`` sidecar key, so both
# readers judge the IDENTICAL declared population — a re-derivation here
# would be a second instrument over the same ground, which is the failure
# mode this campaign keeps paying for.
#
# The BINDING CONSTRAINT (joints never cross a taxi spine/route) is
# STRUCTURAL in the emitter: a joint is born as the terrace line MINUS the
# corridor cover.  These checks are its twin — visibility, not
# enforcement.  A hit here means the structural guarantee was broken and
# the round STOPS.


# Synthetic ways so a terrace-joint finding prints and geocodes through
# the ordinary ``Violation`` path (``_label`` / ``_way_latlon`` read a Way;
# a bare ``None`` would crash the reporter on the ONE class that must
# always be heard).
_TERRACE_JOINT_WAY = Way("terrace_joint", "retaining_wall",
                         "apron_terrace_joint", "", [], [], {})
_TERRACE_ROUTE_WAY = Way("taxi_route", "taxiway_route", "routes_exact",
                         "", [], [], {})
_TERRACE_STRIP_WAY = Way("runway_strip", "runway", "strip_footprint",
                         "", [], [], {})


def _segments_cross(p, q, r, s) -> bool:
    """Proper/improper segment intersection test in the metre frame."""
    def _o(a, b, c):
        return ((b[0] - a[0]) * (c[1] - a[1])
                - (b[1] - a[1]) * (c[0] - a[0]))

    d1, d2 = _o(r, s, p), _o(r, s, q)
    d3, d4 = _o(p, q, r), _o(p, q, s)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True

    def _on(a, b, c):
        return (abs(_o(a, b, c)) <= 1e-9
                and min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
                and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9)

    return (_on(r, s, p) or _on(r, s, q) or _on(p, q, r) or _on(p, q, s))


def _terrace_joints_to_m(terrace_joints_ll, ll_to_m):
    """Sidecar rows → ``[(points_m, step_m), …]`` in the audit frame."""
    out = []
    for row in (terrace_joints_ll or []):
        pts = row.get("points") or []
        if len(pts) < 2:
            continue
        out.append(([ll_to_m(float(la), float(lo)) for (la, lo) in pts],
                    float(row.get("step_m") or 0.0)))
    return out


def _terrace_step_allowance(terrace_joints_m, xa, ya, xb, yb) -> float:
    """Σ of the declared step heights of every joint this chord crosses."""
    total = 0.0
    p, q = (xa, ya), (xb, yb)
    for (pts, step) in terrace_joints_m:
        for k in range(len(pts) - 1):
            if _segments_cross(p, q, pts[k], pts[k + 1]):
                total += step
                break
    return total


# ── THE TUNNEL-TRENCH DECLARED-STEP LAW — the census half ───────────
# Spec ``docs/specs/tunnel-trench-law-and-basin-floor-spec.md`` §1.
#
# A basin/tunnel trench is an open pit: the R2 node-split wall between its
# FLOOR plate and its RIM plate is a step BY LAW, and so is the wall
# between its floor and the pavement it cut.  With no ``ROLE_GRADE_LIMITS``
# entry the role fell through to the default cap and every one of those
# contacts priced as a defect — 90.7 % of LEMD's 12,253 census rows and
# 95.7 % of OTHH's 5,871.
#
# THE ONE READER, exactly as the terrace joints above: the facilities
# arrive through the ``basin_facilities`` sidecar key, so the emitter and
# the census price the IDENTICAL declared population.  The allowance is
# the facility's own DECLARED floor→rim drop and only the EXCESS beyond
# it reports — NOT a blanket exemption, which would blind the census to a
# trench born 51 m too deep (LEMD's, 51.5 m below its own rim under a
# 7.02 m body).  That defect gets its own family below instead.
#
# THE JOIN IS THE DECLARED NUMBER, never proximity: the floor plate is
# emitted AT ``floor_m``, so a step row whose LOWER elevation reads back
# that floor (within ``BASIN_DECLARED_FLOOR_MATCH_TOL_M``, the 1-decimal
# emit-rounding step) belongs to that facility.  Where two facilities
# declare the same floor the MOST FAVOURABLE declared drop applies — the
# crown-declaration-gap idiom: a row over cap under EVERY compatible
# declaration still reports in full, so nothing is blinded.

def _basin_facilities_declared(basin_facilities) -> list:
    """Sidecar rows → ``[(floor_m, declared_drop_m, resources,
    body_depth_m, solid_minimum_y_m, lat, lon, emitted_rim_parts), …]``.

    ``emitted_rim_parts`` is the facility's PUBLISHED per-part rim
    elevations, sorted (trench-law Amendment 1) — the numbers
    :func:`_basin_declared_drop` joins a wall row to.  A patch built
    before the basin law carries no key, reads ``None`` and is judged
    exactly as before; one built before Amendment 1 carries no per-part
    list and falls back to the flat declared drop, likewise unchanged."""
    out = []
    for row in (basin_facilities or []):
        try:
            floor_m = float(row["floor_m"])
            rim_m = float(row["rim_law_m"])
        except (KeyError, TypeError, ValueError):
            continue
        anchor = row.get("anchor_longitude_latitude") or (None, None)
        try:
            lon, lat = float(anchor[0]), float(anchor[1])
        except (TypeError, ValueError, IndexError):
            lon = lat = None
        body_depth = row.get("body_depth_m")
        solid_minimum = row.get("solid_minimum_y_m")
        try:
            rim_parts = tuple(sorted(
                float(value)
                for value in (row.get("emitted_rim_parts_m") or ())))
        except (TypeError, ValueError):
            rim_parts = ()
        out.append((
            floor_m,
            rim_m - floor_m,
            tuple(row.get("resources") or ()),
            None if body_depth is None else float(body_depth),
            None if solid_minimum is None else float(solid_minimum),
            lat, lon, rim_parts))
    return out


def _basin_declared_drop(basin_declared, way_a, way_b,
                         elev_a: float, elev_b: float) -> float:
    """The DECLARED drop this trench contact is priced against.

    Zero unless one side is a DECLARED TERRAIN PLATE and the contact's
    LOWER elevation reads back a declared facility floor — a pavement↔
    pavement pair, a rim↔rim pair on the DEM band and every patch with no
    basin at all are untouched, so their counts are byte-identical.

    ── THE ALLOWANCE IS PER PART (trench-law spec Amendment 1,
    2026-08-25) ────────────────────────────────────────────────────────
    A facility declares ONE floor and, because the rim band is
    TERRAIN-TRUE (each part samples the DEM at its own centroid), MANY
    rims.  Pricing every wall contact against the flat ``rim_law_m``
    charges the ground's own relief as excess: measured at LEMD_a4, an
    emitted rim of 592.64-595.24 against a 593.03 law value reported
    +930 lawful wall rows, worst 9.23 m, every one of them
    ``tunnel_trench|tunnel_trench``.  OTHH never exposed it — its DEM is
    flat there and the emitted rim IS the law value.

    So the allowance is THAT PART's own published rim minus the
    facility's floor: the greatest published part at or below the row's
    HIGHER elevation (within the emit-rounding tolerance).  The join is
    the DECLARED NUMBER on both sides — the part rims and the floor are
    what the emitter published in the sidecar, and the row's own
    elevations are what it emitted; nothing is matched by proximity.

    EXCESS BEYOND THE PART'S OWN DROP STILL REPORTS IN FULL.  A contact
    a metre deeper than the deepest rim the facility published is a
    metre over, and a floor 50 m below its rim is still fully visible —
    the allowance can never exceed what was declared for that part.
    A facility that published no parts (an older artifact, or one whose
    cut seated no band) keeps the flat declared drop, so every such
    patch is judged exactly as before."""
    if not basin_declared:
        return 0.0
    if (law_role(way_a) not in _DECLARED_PLATE_ROLES
            and law_role(way_b) not in _DECLARED_PLATE_ROLES):
        return 0.0
    lower = elev_a if elev_a < elev_b else elev_b
    higher = elev_a if elev_a > elev_b else elev_b
    best = 0.0
    for (floor_m, drop_m, _res, _bd, _sm, _la, _lo,
         rim_parts) in basin_declared:
        if abs(lower - floor_m) > _BASIN_FLOOR_MATCH_TOL_M:
            continue
        allowance = drop_m
        if rim_parts:
            # The greatest published part this contact can belong to.
            # ``rim_parts`` is sorted, so the last one at or below the
            # row's high side (plus the emit-rounding step) is it.
            part = None
            for value in rim_parts:
                if value <= higher + _BASIN_FLOOR_MATCH_TOL_M:
                    part = value
                else:
                    break
            if part is not None:
                # REPLACES the flat drop, never max'd with it: the part's
                # own published rim IS the law at this contact
                # (Amendment 1 item 1).  A facility whose parts all sit
                # BELOW its law rim is therefore held to what it actually
                # emitted, which is the point.
                allowance = part - floor_m
        if allowance > best:
            best = allowance
    return best


# The synthetic way a basin-facility finding prints and sides through (the
# ``_TERRACE_JOINT_WAY`` pattern: ``_label``/``row_side`` read a Way, and a
# bare ``None`` would crash the reporter on a class that must be heard).
_BASIN_FACILITY_WAY = Way("basin_facility", "tunnel_trench",
                          "basin_facility", "", [], [],
                          {"role": "tunnel_trench"})


def _check_basin_floor_declaration(basin_declared) -> List[Violation]:
    """THE DECLARATION ITSELF, judged (spec §1.1 + §2.2).

    The step law above prices every trench contact against the facility's
    OWN declared floor→rim drop — so a facility that declared an absurd
    drop would exempt its own absurdity.  This is the check that stops
    that: the record carries TWO instruments for one bottom, the deepest
    SOLID witness (``solid_minimum_y_m``) and the deck-face body depth
    (``body_depth_m``), and where they disagree by more than
    ``config.BASIN_FLOOR_DISAGREEMENT_M`` the floor this facility was cut
    to is not evidenced by its own geometry.

    ONE THRESHOLD, both halves: the emitter's §2.2 gate refuses that
    witness at cut time and this reports any that still reach a patch —
    an old artifact, a build with the gate's law changed underneath it, or
    a facility the gate did not cover.  A LEMD-class facility (floor 51.5 m
    below its declared rim under a 7.02 m body) reports one row of 42.98 m;
    every OTHH basin agrees within 0.4 m and reports nothing."""
    out: List[Violation] = []
    for (floor_m, drop_m, res, body_depth, solid_minimum,
         lat, lon, _rim_parts) in (basin_declared or []):
        if body_depth is None or solid_minimum is None:
            continue
        disagreement = abs(solid_minimum + body_depth)
        if disagreement <= _BASIN_FLOOR_DISAGREEMENT_M:
            continue
        way = Way("basin_facility", "tunnel_trench",
                  ",".join(str(r).split("/")[-1] for r in res)
                  or "basin_facility",
                  "", [], [], {"role": "tunnel_trench"})
        v = Violation(
            grade_pct=0.0,
            excess_pct=0.0,
            distance_m=0.0,
            de_m=disagreement,
            way_a=way, way_b=way,
            pt_a=(0.0, 0.0), pt_b=(0.0, 0.0),
            elev_a=floor_m, elev_b=floor_m + drop_m)
        v.lat, v.lon = lat, lon
        out.append(v)
    return out


# ── THE FAN-RAMP LAW, VALIDATOR HALF (owner RULINGS 21f0980) ────────
# THE ONE READER: the zones arrive through the ``fan_ramp_zones`` sidecar
# key, exactly as the joints arrive through ``terrace_joints`` — so the
# solve and the census read ONE declaration of where the ramp is.  The
# named precedent for why this matters is in this repo's own CLAUDE.md:
# a private census wrapper that dropped ``terrace_joints_ll`` reported
# lawful declared terraces as violations.  A patch predating the law has
# no key, reads ``None``, and is judged exactly as before.

def _fan_ramp_zones_to_m(fan_ramp_zones_ll, ll_to_m):
    """``[(polygon, cap, bounds, prepared)]`` from the sidecar rows.

    Prepared + bbox-indexed for the same reason the solver's side is:
    the within-shape check asks per PAIR, and a raw shapely predicate
    per pair per zone does not finish at a real airport."""
    out = []
    for row in (fan_ramp_zones_ll or []):
        ring = row.get("ring_ll") if isinstance(row, dict) else None
        if not ring or len(ring) < 3:
            continue
        pts = [ll_to_m(la, lo) for (la, lo) in ring]
        try:
            from shapely.geometry import Polygon as _Poly
            poly = _Poly(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
        except Exception:
            continue
        try:
            from shapely.prepared import prep
            pre = prep(poly)
        except Exception:
            pre = None
        out.append((poly, float(row.get("cap") or 0.0), poly.bounds, pre))
    return out


def _disconnected_rings_to_m(disconnected_rings_ll, ll_to_m):
    """``[(polygon, bounds, prepared)]`` from the ``disconnected_rings``
    sidecar key — the rings the SOLVE could not couple to the network.

    Same shape and the same prepared/bbox indexing as the fan-ramp reader
    next door, for the same reason: the question is asked per ROW at a
    real airport.
    """
    out = []
    for ring in (disconnected_rings_ll or []):
        if not ring or len(ring) < 3:
            continue
        pts = [ll_to_m(la, lo) for (la, lo) in ring]
        try:
            from shapely.geometry import Polygon as _Poly
            poly = _Poly(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
        except Exception:
            continue
        try:
            from shapely.prepared import prep
            pre = prep(poly)
        except Exception:
            pre = None
        out.append((poly, poly.bounds, pre))
    return out


#: How far outside a declared disconnected ring a row's endpoint may sit
#: and still belong to it.  A ring vertex is emitted at millimetre
#: precision and a step row's projected point lands ON the edge, so the
#: predicate needs a hair of slack — not a proximity join (the 11.6 %
#: wrong-object lesson): this is containment with an emit-noise margin.
DISCONNECTED_RING_TOL_M = 0.25


def _in_disconnected_ring(rings_m, x, y) -> bool:
    if not rings_m:
        return False
    for (poly, bb, pre) in rings_m:
        if (x < bb[0] - DISCONNECTED_RING_TOL_M
                or x > bb[2] + DISCONNECTED_RING_TOL_M
                or y < bb[1] - DISCONNECTED_RING_TOL_M
                or y > bb[3] + DISCONNECTED_RING_TOL_M):
            continue
        try:
            from shapely.geometry import Point as _Pt
            p = _Pt(x, y)
            if (pre or poly).covers(p):
                return True
            if poly.distance(p) <= DISCONNECTED_RING_TOL_M:
                return True
        except Exception:
            continue
    return False


def _mark_disconnected(pair_rows, step_rows, rings_m) -> int:
    """Stamp ``out_of_scope='disconnected_ring'`` on every row BOTH of
    whose points lie in a declared disconnected ring.

    BOTH points, deliberately.  A row with one end on unsolved geometry
    and the other on the solved network is a statement about the coupling
    — if the two really are that close, the ring was not disconnected —
    so it stays in the acceptance count and is visible as the defect it
    would be.  Returns how many rows were marked.
    """
    n = 0
    for r in pair_rows:
        if (_in_disconnected_ring(rings_m, *r.pt_a)
                and _in_disconnected_ring(rings_m, *r.pt_b)):
            r.out_of_scope = "disconnected_ring"
            n += 1
    for s in step_rows:
        if (_in_disconnected_ring(rings_m, *s.vert_pt)
                and _in_disconnected_ring(rings_m, *s.proj_pt)):
            s.out_of_scope = "disconnected_ring"
            n += 1
    return n


def _fan_ramp_pair_cap(fan_ramp_zones_m, xa, ya, xb, yb):
    """The zone cap for a pair wholly inside ONE zone, else ``None``.

    BOTH ends AND the chord: a pair that leaves the zone touches an
    aircraft-movement surface, and those hold the strict apron cap
    always.  This is ``FanRampPlan.pair_cap``'s predicate verbatim — the
    lockstep is that the two ask the same question of the same geometry.
    """
    if not fan_ramp_zones_m:
        return None
    try:
        from shapely.geometry import LineString as _LS
        chord = _LS([(xa, ya), (xb, yb)])
    except Exception:
        return None
    lo_x, hi_x = (xa, xb) if xa <= xb else (xb, xa)
    lo_y, hi_y = (ya, yb) if ya <= yb else (yb, ya)
    best = None
    for (poly, cap, bb, pre) in fan_ramp_zones_m:
        # bbox prefilter: a chord whose own box leaves the zone's box
        # cannot be covered by it, and that rejects almost every pair
        # for the cost of four comparisons.
        if lo_x < bb[0] or hi_x > bb[2] or lo_y < bb[1] or hi_y > bb[3]:
            continue
        if best is not None and cap <= best:
            continue
        try:
            if (pre or poly).covers(chord):
                best = cap
        except Exception:
            continue
    return best


def _check_terrace_joint_crosses_route(terrace_joints_m, routes_ll,
                                       taxi_axes) -> List[Violation]:
    """§5(b)/(c): a declared joint intersecting a taxi ROUTE is an ERROR.

    The population is the sidecar's own ``routes_exact`` chains, converted
    to metres by the caller (``taxi_axes`` carries the same polylines with
    their per-segment caps, and every route ordinal indexes into it).  Cap
    ZERO — this is inadmissible geometry, not an over-cap grade, so the
    reported ``de_m`` carries nothing but the fact of the crossing."""
    if not terrace_joints_m or not taxi_axes:
        return []
    out: List[Violation] = []
    for (pts, step) in terrace_joints_m:
        for entry in taxi_axes:
            poly = entry[0]
            for a in range(len(poly) - 1):
                hit = False
                for k in range(len(pts) - 1):
                    if _segments_cross(pts[k], pts[k + 1],
                                       poly[a], poly[a + 1]):
                        hit = True
                        break
                if not hit:
                    continue
                out.append(Violation(
                    grade_pct=100.0, excess_pct=100.0,
                    distance_m=0.0, de_m=step,
                    way_a=_TERRACE_JOINT_WAY, way_b=_TERRACE_ROUTE_WAY,
                    pt_a=pts[0], pt_b=poly[a],
                    elev_a=0.0, elev_b=0.0))
                break
    return out


def _check_terrace_joint_in_runway_strip(terrace_joints_m, ways, nodes,
                                         ll_to_m) -> List[Violation]:
    """§5(d): a declared joint inside the runway-strip footprint is an
    ERROR — walls at runway edges are NEVER lawful (owner 2026-08-01), and
    a joint is a wall by construction."""
    if not terrace_joints_m:
        return []
    rings = _runway_strip_keepout_rings(ways, nodes, ll_to_m)
    if not rings:
        return []
    out: List[Violation] = []
    for (pts, step) in terrace_joints_m:
        for (px, py) in pts:
            if not any(_point_in_rect_ring(px, py, r, _WALL_STRIP_MARGIN_M)
                       for r in rings):
                continue
            out.append(Violation(
                grade_pct=100.0, excess_pct=100.0,
                distance_m=0.0, de_m=step,
                way_a=_TERRACE_JOINT_WAY, way_b=_TERRACE_STRIP_WAY,
                pt_a=(px, py), pt_b=(px, py),
                elev_a=0.0, elev_b=0.0))
            break
    return out


_TERRACE_ACTUAL_WAY = Way("terrace_step", "retaining_wall",
                          "apron_terrace_actual_step", "", [], [], {})
# The straddling-pair window (flip-readiness v2 §3(b)).  A pair speaks
# for the joint's own step only when both vertices sit close to the joint
# line AND close to each other: a LONG window folds lawful cap-graded
# relief into the number, which is how the emitter's flank MEANS declared
# ≤1.994 m while shipping 5.52 m faces (defect D2).
_TERRACE_STRADDLE_PERP_M = 5.0
_TERRACE_STRADDLE_PAIR_M = 5.0
_TERRACE_STEP_QUANT_M = 0.11        # 2 x emit rounding + weld noise
# The joint FACE's own width — the band the lower panel retreats by.
# Read from the emitter's constant so the two never drift.
try:
    from auto_patch.adjacent_ground import (
        STACKED_WALL_RETREAT_M as _WALL_RETREAT_M)
except Exception:                                    # pragma: no cover
    _WALL_RETREAT_M = 0.6


def _seg_point_distance(px: float, py: float, a, b) -> float:
    """Point-to-segment distance in the check's metre frame."""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _check_terrace_actual_step(terrace_joints_m, ways, nodes, ll_to_m,
                               max_grade: float) -> List[Violation]:
    """§3(b) THE HONEST INSTRUMENT: the ACTUAL emitted step per declared
    joint, recomputed from the PATCH — never read out of the sidecar.

    Two readings, both from emitted geometry:

    1. NEAREST STRADDLING VERTEX PAIRS.  For emitted pavement vertices
       ``m``, ``n`` on OPPOSITE sides of the joint line, both within
       ``_TERRACE_STRADDLE_PERP_M`` of it and within
       ``_TERRACE_STRADDLE_PAIR_M`` of each other in plan, the law allows
       ``|Δz| ≤ step_m + cap·planar(m, n) + quant``.  Each vertex is
       paired with its NEAREST opposite-side partner only — a long
       window would fold lawful cap-graded relief into the reading, which
       is the exact error the emitter's flank means made.
    2. THE EMITTED JOINT FACE.  An ``apron_terrace_joint`` retaining wall
       IS the vertical step the simulator draws, so its own altitude
       delta is the actual step at its joint, with no window at all.

    ``panel_lo``/``panel_hi``/``actual_step_m`` in the sidecar are REPORT
    fields; this check trusts none of them.
    """
    if not terrace_joints_m:
        return []
    out: List[Violation] = []
    # ── reading 2: the emitted faces ────────────────────────────────
    for w in ways:
        if (w.tags.get("ref") or "") != "apron_terrace_joint":
            continue
        zs = [z for z in (w.elevs or []) if z is not None]
        if len(zs) < 2:
            continue
        pts = [ll_to_m(*nodes[n]) for n in w.nids if n in nodes]
        if not pts:
            continue
        # ── ACROSS the band, not along it (D2 lockstep) ─────────────
        # The face is minted PER STATION now, so its two long edges
        # follow the panels and ``max(zs) − min(zs)`` over the whole
        # polygon would fold LAWFUL along-joint relief into the reading
        # — the same error the emitter's whole-joint flank means made.
        # The step a face expresses is the delta between vertices that
        # face each other ACROSS the retreat band: each vertex is paired
        # with its nearest partner at a planar distance in
        # ``[0.3·retreat, 3·retreat]``, and the allowance is the law's
        # own ``step + cap·d``.
        _zl = list(w.elevs or [])
        _pairs: List[Tuple[float, float]] = []       # (|dz|, planar)
        for _i, (_pi, _zi) in enumerate(zip(pts, _zl)):
            if _zi is None:
                continue
            _best = None
            for _j, (_pj, _zj) in enumerate(zip(pts, _zl)):
                if _j == _i or _zj is None:
                    continue
                _d = math.hypot(_pj[0] - _pi[0], _pj[1] - _pi[1])
                if _d < 0.3 * _WALL_RETREAT_M or _d > 3.0 * _WALL_RETREAT_M:
                    continue
                if _best is None or _d < _best[1]:
                    _best = (abs(float(_zi) - float(_zj)), _d)
            if _best is not None:
                _pairs.append(_best)
        if not _pairs:
            continue
        delta, _pair_d = max(_pairs, key=lambda r: r[0] - r[1])
        # the joint this face belongs to = the nearest declared line
        best = None
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        for (jpts, step) in terrace_joints_m:
            d = min(_seg_point_distance(cx, cy, jpts[k], jpts[k + 1])
                    for k in range(len(jpts) - 1))
            if best is None or d < best[0]:
                best = (d, step)
        if best is None:
            continue
        allow = best[1] + max_grade * _pair_d + _TERRACE_STEP_QUANT_M
        if delta <= allow:
            continue
        out.append(Violation(
            grade_pct=100.0, excess_pct=100.0,
            distance_m=_pair_d, de_m=delta,
            way_a=w, way_b=_TERRACE_ACTUAL_WAY,
            pt_a=pts[0], pt_b=pts[-1],
            elev_a=max(zs), elev_b=min(zs)))
    # ── reading 1: nearest straddling pairs ─────────────────────────
    verts: List[Tuple[float, float, float, Way]] = []
    for w in ways:
        if _role_grade_limit(w, 1.0) is None:
            continue                       # skip-list roles (walls etc.)
        for nid, z in zip(w.nids, w.elevs or []):
            if z is None or nid not in nodes:
                continue
            x, y = ll_to_m(*nodes[nid])
            verts.append((x, y, float(z), w))
    for (jpts, step) in terrace_joints_m:
        pos: List[Tuple[float, float, float, Way]] = []
        neg: List[Tuple[float, float, float, Way]] = []
        for (x, y, z, w) in verts:
            best_d = None
            best_k = 0
            for k in range(len(jpts) - 1):
                d = _seg_point_distance(x, y, jpts[k], jpts[k + 1])
                if best_d is None or d < best_d:
                    best_d, best_k = d, k
            if best_d is None or best_d > _TERRACE_STRADDLE_PERP_M:
                continue
            (ax, ay), (bx, by) = jpts[best_k], jpts[best_k + 1]
            s = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
            if abs(s) < 1e-12:
                continue
            (pos if s > 0 else neg).append((x, y, z, w))
        if not pos or not neg:
            continue
        for (x1, y1, z1, w1) in pos:
            best = None
            for (x2, y2, z2, w2) in neg:
                d = math.hypot(x2 - x1, y2 - y1)
                if d > _TERRACE_STRADDLE_PAIR_M:
                    continue
                if best is None or d < best[0]:
                    best = (d, x2, y2, z2, w2)
            if best is None:
                continue
            (d, x2, y2, z2, w2) = best
            if abs(z1 - z2) <= step + max_grade * d + _TERRACE_STEP_QUANT_M:
                continue
            out.append(Violation(
                grade_pct=(abs(z1 - z2) / d * 100.0) if d > 1e-6 else 100.0,
                excess_pct=100.0, distance_m=d, de_m=abs(z1 - z2),
                way_a=w1, way_b=w2, pt_a=(x1, y1), pt_b=(x2, y2),
                elev_a=z1, elev_b=z2))
    return out


#: PAIRS THE CROWN FIELD CANNOT PRICE — one endpoint carries a declared
#: NONZERO crown drop, the other is absent from the field, and the measured
#: step falls INSIDE the interval of designed steps the field is compatible
#: with (``grade_law.crown_pair_offset_clamped``).  The pair stays in the
#: domain and is judged at its most favourable compatible target, so nothing
#: is blinded — a pair over cap under EVERY compatible declaration still
#: reports its full excess.  Counted per role by
#: ``iter_shape_grade_constraints`` and REPORTED by ``run_checks``: the count
#: is a gap in the DECLARATION, and a census that hid it would hide exactly
#: the emitter defect that makes these pairs unpriceable.  Reporter-only;
#: nothing adjudicates on it.
_CROWN_UNKNOWN_PAIRS: Dict[str, int] = defaultdict(int)


def _check_within_shape(ways: List[Way],
                        nodes: Dict[str, Tuple[float, float]],
                        ll_to_m,
                        max_grade: float,
                        seam_nids: Optional[set] = None,
                        taxi_axes: Optional[list] = None,
                        routes_ll: Optional[list] = None,
                        mesh_edges_m: Optional[list] = None,
                        crown_by_nid: Optional[Dict[str, float]] = None,
                        crown_centerline_nids: Optional[set] = None,
                        pair_caps_ll: Optional[list] = None,
                        terrace_joints_m: Optional[list] = None,
                        fan_ramp_zones_m: Optional[list] = None,
                        interior_zones_m: Optional[list] = None,
                        transverse_road_out: Optional[List] = None,
                        ) -> List[Violation]:
    """Grade check between vertex pairs on the same way.  Consumes
    ``iter_shape_grade_constraints`` (the single source of constrained pairs)
    and flags any pair whose stored Δelev exceeds its allowance — a violation
    requires ``|de − crown_offset| > max(baked, cap*dist) + quant_noise`` (see
    ``_pair_grade_allowance`` — the flat-cap floor mirrors the plane-gradient
    law's ``cap*dist + noise``, and ``quant_noise`` is the shape's emit/weld
    envelope; crown offset is 0 for uncrowned pairs) so emit rounding and
    weld-insert micro-steps don't produce spurious sub-metre flags.

    ``transverse_road_out``: when a list is passed, ROAD CROSS-SECTION
    rows (owner ruling RULINGS 2026-08-25g) are appended THERE instead of
    to the return value — they are their own law family
    (``road_cross_section``), priced at the road's transverse limit
    rather than its longitudinal chord cap.  A row lands in exactly one
    of the two lists, never both: the ruling says the cross-section
    prices at the cross-section limit, *not* at the chord cap, so
    counting it under both caps would be pricing one pair twice.  With no
    list passed (a caller that predates the family) every row returns as
    before.
    """
    out: List[Violation] = []
    for c in iter_shape_grade_constraints(
            ways, nodes, ll_to_m, max_grade, seam_nids, taxi_axes, routes_ll,
            mesh_edges_m=mesh_edges_m, crown_by_nid=crown_by_nid,
            crown_centerline_nids=crown_centerline_nids,
            pair_caps_ll=pair_caps_ll,
            interior_zones_m=interior_zones_m):
        de = abs((c.ea - c.eb) - c.offset)
        allowance = c.allowance
        if terrace_joints_m:
            # APRON TERRACE LAW (spec §5a): a within-pair edge crossing a
            # DECLARED joint is judged by the step law, not by the grade
            # cap alone — ``cap·d + Σ step``, the identical rule
            # ``apron_terrace._rewrite_edges`` bound the solver to.  One
            # law, both readers.  A pair crossing no joint is untouched,
            # so an old patch (or the gate off) reads exactly as before.
            allowance += _terrace_step_allowance(
                terrace_joints_m, c.xa, c.ya, c.xb, c.yb)
        if fan_ramp_zones_m:
            # FAN-RAMP LAW: a within-apron pair lying wholly inside a
            # declared zone is judged at the ZONE's cap — the identical
            # rule ``apron_terrace._rewrite_fan_edges`` bound the solver
            # to.  RELAXING ONLY: ``max`` never tightens an allowance
            # some other law already widened.
            _zc = _fan_ramp_pair_cap(fan_ramp_zones_m,
                                     c.xa, c.ya, c.xb, c.yb)
            if _zc is not None:
                allowance = max(allowance, _zc * c.dist)
        if de <= allowance:
            continue
        grade = de / c.dist
        v = Violation(
            grade_pct=grade * 100,
            excess_pct=(grade - c.cap) * 100,
            distance_m=c.dist,
            de_m=de,
            way_a=c.way, way_b=c.way,
            pt_a=(c.xa, c.ya), pt_b=(c.xb, c.yb),
            elev_a=c.ea, elev_b=c.eb,
            # WHICH CAP PRICED IT (spec A1 §2a) — ``c.cap`` is the cap
            # ``grade_law.classify_pair`` returned for this very pair, so the
            # strict/5 % split is reported from the law itself, never
            # re-derived from the geometry by the reader.
            cap_pct=c.cap * 100)
        # THE ROW POINTS AT THE PAIR, NOT THE SHAPE (R19-5).  Every other
        # family's ``lat``/``lon`` is the offending way's ring centroid
        # (``run_checks._way_latlon``), which on a 1.2 km apron ring puts
        # a 148 % edge hundreds of metres from where it is — the HECA
        # attribution had to re-derive sites by hand because of it.  A
        # within-shape row has TWO known vertices, so it reports their
        # MIDPOINT; ``site_m`` (the metre-frame endpoints) is untouched.
        _lla = nodes.get(c.nid_a)
        _llb = nodes.get(c.nid_b)
        if _lla is not None and _llb is not None:
            v.lat = (_lla[0] + _llb[0]) / 2.0
            v.lon = (_lla[1] + _llb[1]) / 2.0
        if transverse_road_out is not None and c.transverse_road:
            transverse_road_out.append(v)
        else:
            out.append(v)
    return out


# Roles excluded from the route-band check: anchors themselves (runway /
# runway-interpolated crossings) and groundside surfaces (wall-separated from
# the airside network by design — they have no taxi route to a runway).
_ROUTE_BAND_SKIP_ROLES = {"runway", "runway_crossing"}


SHARED_NID_TOLERANCE_M = 0.15  # rounding-precision step at a
                                # shared OSM node (1-decimal elev)


def _check_cross_shape_proximity(
    vertices: List[Vertex],
    ways: List[Way],
    proximity_m: float,
    max_grade: float,
) -> List[Violation]:
    """For every pair of vertices on DIFFERENT ways within
    ``proximity_m`` of each other, verify ``|de| / dist <= grade``.
    For sub-metre distances this is essentially "shared corners
    must agree on elevation".

    When two ways reference the SAME OSM node id, the vertices are
    geometrically identical — any non-zero elevation difference is
    a desync (we tolerate up to SHARED_NID_TOLERANCE_M for one-
    decimal rounding noise, then flag).
    """
    out: List[Violation] = []
    cell = max(proximity_m, 0.5)
    grid = _bucket_vertices(vertices, cell)
    for v_idx, v in enumerate(vertices):
        if v.elev is None:
            continue
        cx = int(math.floor(v.x / cell))
        cy = int(math.floor(v.y / cell))
        for dcx in (-1, 0, 1):
            for dcy in (-1, 0, 1):
                bucket = grid.get((cx + dcx, cy + dcy))
                if not bucket:
                    continue
                for u_idx in bucket:
                    if u_idx <= v_idx:
                        continue
                    u = vertices[u_idx]
                    if u.way_idx == v.way_idx:
                        continue
                    if u.elev is None:
                        continue
                    d = math.hypot(v.x - u.x, v.y - u.y)
                    if d > proximity_m:
                        continue
                    way_v = ways[v.way_idx]
                    way_u = ways[u.way_idx]
                    # Airside <-> groundside is separated by a clearance gap +
                    # retaining/vertical wall (user 2026-05-28): the two are NOT
                    # meant to be flush and may differ by several metres.  The
                    # STEP checks already skip this boundary; the cross-shape
                    # proximity check (same continuity assumption) must too.
                    if _airside_groundside_pair(way_v, way_u):
                        continue
                    grade_cap = _pair_grade_limit(
                        way_v, way_u, max_grade)
                    if grade_cap is None:
                        continue
                    de = abs(v.elev - u.elev)
                    # Same OSM node referenced by two ways: the
                    # only valid step is rounding noise.  Don't
                    # apply the grade rule (denominator is zero).
                    if v.nid == u.nid or d < 0.05:
                        if de <= SHARED_NID_TOLERANCE_M:
                            continue
                        out.append(Violation(
                            grade_pct=float("inf"),
                            excess_pct=float("inf"),
                            distance_m=d,
                            de_m=de,
                            way_a=way_v,
                            way_b=way_u,
                            pt_a=(v.x, v.y), pt_b=(u.x, u.y),
                            elev_a=v.elev, elev_b=u.elev))
                        continue
                    allowance = grade_cap * d + ELEV_ROUNDING_NOISE_M
                    if de <= allowance:
                        continue
                    grade = de / d
                    out.append(Violation(
                        grade_pct=grade * 100,
                        excess_pct=(grade - grade_cap) * 100,
                        distance_m=d,
                        de_m=de,
                        way_a=way_v,
                        way_b=way_u,
                        pt_a=(v.x, v.y), pt_b=(u.x, u.y),
                        elev_a=v.elev, elev_b=u.elev))
    return out


def _check_frontage_near_miss(ways: List[Way], nodes, ll_to_m
                              ) -> List[Violation]:
    """NEAR-MISS BUILDING FRONTAGE — the validator twin of the solve's
    near-miss frontage LAW EDGES (cycle-5 instrument-fix spec item 6).

    THE LAW (``route_profile.anchors.near_miss_building_frontage_edges``,
    STANDING).  A DSF building-pad outline and the apt.dat apron edge it
    fronts can be offset by a sub-metre source mismatch (SPJC building29 vs
    its SW apron: 0.68 m), leaving a thin unpaved sliver that defeats every
    exact-identity reconciler.  The frontage law binds ACROSS that sliver:
    for a soft-pavement (apron / junction / service_junction) ring EDGE that
    passes within ``BUILDING_FRONTAGE_NEAR_MISS_M`` of a pad, with BOTH
    endpoints canonically unshared with the pad, each endpoint must satisfy
    ``|z(endpoint) − z(pad node)| ≤ near_miss_frontage_budget(d)`` — the
    apron cap over ``d``, the endpoint's own distance to the pad polygon —
    against the pad's NEAREST ring node.

    WHY THE FAMILY EXISTS.  The law BINDS in the solve (measured edge counts:
    HEAZ 4 · SPJC 12-38 · KCLT 78-86 · HECA 118-138) but nothing measured it
    on the emitted patch.  ``cross_shape`` cannot: it is scoped to
    ``proximity_m`` = ``SHARED_VERTEX_TOL_M`` (0.5 m) and reads 0 rows
    everywhere, and a near-miss pair beyond that radius could only ever show
    up as unattributed ``within_shape`` noise, if at all.  A law with no
    census row is a law nobody can prove is enforced.

    LOCKSTEP, NOT A SECOND COPY.  The radius, the role set and the budget all
    come from ``auto_patch.config`` — the same three objects the solve's edge
    builder prices with (``BUILDING_FRONTAGE_NEAR_MISS_M``,
    ``NEAR_MISS_FRONTAGE_SOFT_ROLES``, ``near_miss_frontage_budget``).

    THE TWO SCOPE DIFFERENCES, both named rather than hidden:

    * The solve skips an endpoint that already carries a building SEAT
      (``i in building_seats``).  On the emitted patch that set is the union
      of every pad's ring nodes — seats are assigned per pad ring node — so
      that union is what is skipped here.  Conservative: a node identity has
      already reconciled is never re-judged across a sliver.
    * The solve only builds an edge for a pad that carries a CHOSEN seat
      (``build_building_seats``' airside-touch test); this reads every
      emitted ``building`` way.  A row on a pad the solve never seated is
      therefore a report that the law did not REACH that frontage, which is
      a finding about the law's scope and not a miscount — the row's own
      distance, |de| and role pair say which case it is.

    ``d`` is legitimately larger than the recognition radius on a long edge
    that grazes a pad near its middle: the law is per-ENDPOINT and the budget
    scales with each endpoint's own ``d`` (see the emitter's docstring — SPJC's
    49 m frontage edge with endpoints 1.5 m and 10 m from the pad is the type
    specimen).
    """
    if (_near_miss_frontage_budget is None
            or not _NEAR_MISS_FRONTAGE_SOFT_ROLES):
        return []                       # law unavailable → report nothing
    try:
        from shapely.geometry import LineString, Point, Polygon
        from shapely.strtree import STRtree
    except ImportError:                                    # pragma: no cover
        return []
    near_m = float(_BUILDING_FRONTAGE_NEAR_MISS_M)
    cap = float(_near_miss_frontage_budget(1.0))           # the apron cap

    def _rings(roles):
        out = []
        for idx, w in enumerate(ways):
            if w.tags.get("role") not in roles:
                continue
            ring = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
                    else w.nids)
            pts, elevs, nids = [], [], []
            for k, nid in enumerate(ring):
                if nid not in nodes:
                    continue
                pts.append(ll_to_m(*nodes[nid]))
                elevs.append(w.elevs[k] if k < len(w.elevs) else None)
                nids.append(nid)
            if len(pts) < 3:
                continue
            try:
                poly = Polygon(pts)
            except Exception:                              # pragma: no cover
                continue
            if poly.is_empty:
                continue
            out.append((idx, pts, elevs, nids, poly))
        return out

    pads = _rings({"building"})
    soft = _rings(set(_NEAR_MISS_FRONTAGE_SOFT_ROLES))
    if not pads or not soft:
        return []
    # CANONICAL IDENTITY, POSITIONALLY.  The emitter's "unshared with the pad"
    # test is over ``layout.canonical_points``, which INTERNS within
    # ``SHARED_VERTEX_TOL_M`` (0.5 m) — that radius IS the one canonical
    # identity.  Matching on OSM node id alone would be wrong in exactly the
    # dangerous direction: a welded corner can ship as two distinct ids at one
    # coordinate (the whole reason a ``stacked_nodes`` family exists), and this
    # check would then judge a reconciled corner as a near miss.  A 0.5 m grid
    # of every pad ring node answers both scopes: shared with THIS pad (the
    # edge test) and shared with ANY pad (the seated-node skip — on the emitted
    # patch, "carries a building seat" is exactly "is a pad ring node").
    # Note the SPJC type specimen survives by design: its 0.68 m source offset
    # is outside 0.5 m, so no vertex is canonically shared and the law binds.
    _tol = float(SHARED_VERTEX_TOL_M)
    pad_grid: Dict[Tuple[int, int], List[Tuple[float, float, int]]] = \
        defaultdict(list)
    for (pi, (_i, p_pts, _e, _n, _poly)) in enumerate(pads):
        for (px, py) in p_pts:
            pad_grid[(int(math.floor(px / _tol)),
                      int(math.floor(py / _tol)))].append((px, py, pi))

    def _canonical_pads(x: float, y: float) -> set:
        """Pad indices with a ring node canonically identical to ``(x, y)``."""
        cx, cy = int(math.floor(x / _tol)), int(math.floor(y / _tol))
        hit = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py, pi) in pad_grid.get((cx + dx, cy + dy), ()):
                    if math.hypot(px - x, py - y) <= _tol:
                        hit.add(pi)
        return hit

    tree = STRtree([p[4] for p in pads])

    out: List[Violation] = []
    for (s_idx, s_pts, s_elevs, s_nids, s_poly) in soft:
        try:
            cand = tree.query(s_poly, predicate="dwithin", distance=near_m)
        except Exception:                                  # pragma: no cover
            continue
        n = len(s_pts)
        canon = [_canonical_pads(px, py) for (px, py) in s_pts]
        for pi in cand:
            (p_idx, p_pts, p_elevs, p_nids, p_poly) = pads[int(pi)]
            fired: set = set()
            for a in range(n):
                b = (a + 1) % n
                # A pad-SHARED endpoint means identity already reconciles that
                # corner (weld / stitch / seat anchor) and the edge
                # legitimately grades away from the seat — not a near miss.
                if int(pi) in canon[a] or int(pi) in canon[b]:
                    continue
                try:
                    if LineString([s_pts[a], s_pts[b]]).distance(p_poly) \
                            > near_m:
                        continue
                except Exception:                          # pragma: no cover
                    continue
                for e in (a, b):
                    if canon[e] or e in fired:
                        continue        # a seated pad node / already judged
                    fired.add(e)
                    ez = s_elevs[e]
                    if ez is None:
                        continue
                    x, y = s_pts[e]
                    try:
                        d = float(p_poly.distance(Point(x, y)))
                    except Exception:                      # pragma: no cover
                        continue
                    j = min(range(len(p_pts)),
                            key=lambda k: ((p_pts[k][0] - x) ** 2
                                           + (p_pts[k][1] - y) ** 2))
                    pz = p_elevs[j]
                    if pz is None:
                        continue
                    de = abs(float(ez) - float(pz))
                    if de <= _near_miss_frontage_budget(d) \
                            + ELEV_ROUNDING_NOISE_M:
                        continue
                    grade = (de / d) if d > 1e-9 else float("inf")
                    out.append(Violation(
                        grade_pct=grade * 100,
                        excess_pct=(grade - cap) * 100,
                        distance_m=d,
                        de_m=de,
                        way_a=ways[s_idx],
                        way_b=ways[p_idx],
                        pt_a=(x, y), pt_b=p_pts[j],
                        elev_a=float(ez), elev_b=float(pz)))
    out.sort(key=lambda v: -v.de_m)
    return out


def _check_vertex_to_edge_step(
    vertices: List[Vertex],
    edges: List[Edge],
    ways: List[Way],
    edge_search_m: float,
    edge_step_m: float,
    contact_tol_m: Optional[float] = None,
    pair_ok=None,
    terrace_joints_m: Optional[list] = None,
    basin_declared: Optional[list] = None,
) -> List[EdgeStep]:
    """For each vertex, find the closest edge of ANY OTHER way
    within ``edge_search_m``.  Project the vertex onto the edge,
    compute interpolated elevation along the edge at that point,
    and report a violation if the vertex's own elevation differs
    by more than ``edge_step_m``.

    ``contact_tol_m`` (default ``_STEP_CONTACT_TOL_M``): a vertex is
    treated as touching the edge only when its perpendicular distance is
    within this bound — beyond it the two shapes are gapped and a height
    difference is allowed.  ``pair_ok(way_v, way_e) -> bool`` (default
    None = allow all): an extra predicate to restrict the pairs checked
    (e.g. the airside-only mid-edge gate); the standard role/groundside
    skips still apply on top of it."""
    ctol = _STEP_CONTACT_TOL_M if contact_tol_m is None else contact_tol_m
    out: List[EdgeStep] = []
    cell = max(edge_search_m, 1.0)
    edge_grid = _bucket_edges(edges, cell)
    for v in vertices:
        if v.elev is None:
            continue
        way_v = ways[v.way_idx]
        if _role_grade_limit(way_v, 1.0) is None:
            continue  # vertex's role is on the skip-list
        cx = int(math.floor(v.x / cell))
        cy = int(math.floor(v.y / cell))
        best_d2 = edge_search_m * edge_search_m
        best: Optional[Tuple[Edge, float, float, float]] = None
        for dcx in (-1, 0, 1):
            for dcy in (-1, 0, 1):
                bucket = edge_grid.get((cx + dcx, cy + dcy))
                if not bucket:
                    continue
                for e_idx in bucket:
                    e = edges[e_idx]
                    if e.way_idx == v.way_idx:
                        continue
                    way_e = ways[e.way_idx]
                    if _role_grade_limit(way_e, 1.0) is None:
                        continue  # edge's role is on the skip-list
                    if _airside_groundside_pair(way_v, way_e):
                        continue  # wall-separated boundary — step by design
                    if pair_ok is not None and not pair_ok(way_v, way_e):
                        continue  # caller's pair restriction (airside gate)
                    ax, ay = e.a
                    bx, by = e.b
                    dx = bx - ax
                    dy = by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 0.04:
                        continue
                    t = ((v.x - ax) * dx + (v.y - ay) * dy) / seg2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                    px = ax + t * dx
                    py = ay + t * dy
                    d2 = (v.x - px) * (v.x - px) + (v.y - py) * (v.y - py)
                    if d2 < best_d2:
                        best_d2 = d2
                        best = (e, t, px, py)
        if best is None:
            continue
        if best_d2 > ctol * ctol:
            continue  # gap, not a shared edge — height difference allowed
        e, t, px, py = best
        e_proj = e.ea + t * (e.eb - e.ea)
        step = abs(v.elev - e_proj)
        # APRON TERRACE LOCKSTEP.  The apron is split into PANELS before
        # the solve, so a declared joint shows up here as a CROSS-SHAPE
        # pair 0.6 m apart (the two panels' edges, with the wall band
        # between them) — lawful declared geometry, not a defect.  The allowance is the DECLARED step of
        # the joint the pair straddles: the identical population, and the
        # identical number, the solver was bound to.  A pair crossing no
        # joint is untouched, so a gate-off patch reads exactly as before.
        allow_step = edge_step_m
        if terrace_joints_m:
            allow_step += _terrace_step_allowance(
                terrace_joints_m, v.x, v.y, px, py)
        # THE TUNNEL-TRENCH DECLARED STEP (spec §1.1): a contact with a
        # declared trench plate is lawful down to the facility's OWN
        # declared floor→rim drop; only the EXCESS beyond it reports.
        if basin_declared:
            allow_step += _basin_declared_drop(
                basin_declared, way_v, ways[e.way_idx], v.elev, e_proj)
        if step > allow_step + 1e-5:
            out.append(EdgeStep(
                step_m=step,
                distance_m=math.sqrt(best_d2),
                way_v=ways[v.way_idx],
                way_e=ways[e.way_idx],
                vert_pt=(v.x, v.y),
                proj_pt=(px, py),
                elev_v=v.elev,
                elev_proj=e_proj))
    return out


def _check_edge_midpoint_step(
    edges: List[Edge],
    ways: List[Way],
    edge_search_m: float,
    edge_step_m: float,
    samples_per_edge: int = 5,
    contact_tol_m: Optional[float] = None,
    pair_ok=None,
    terrace_joints_m: Optional[list] = None,
    basin_declared: Optional[list] = None,
) -> List[EdgeStep]:
    """For every edge, sample at ``samples_per_edge`` points
    (including the midpoint), compute the edge's interpolated
    elevation at that sample, then find the closest edge of any
    OTHER way and compare its interpolated elevation at the
    projected point.

    This catches the "two parallel edges drift apart in elevation"
    case that vertex-only checks miss: endpoints may agree but a
    mid-edge sample can still have a visible step if the two
    edges aren't exactly coincident (e.g. a junction edge running
    0.3 m alongside a sloped rect's long edge, with the junction's
    other endpoint dragging the midpoint elevation off the rect's
    slope at that point).

    ``contact_tol_m`` / ``pair_ok`` mirror ``_check_vertex_to_edge_step``:
    override the touch tolerance and restrict the checked pairs (the
    airside-only mid-edge gate uses a wider tolerance so a wedge whose
    steep edge runs ~1 m from the neighbour is still caught).
    """
    ctol = _STEP_CONTACT_TOL_M if contact_tol_m is None else contact_tol_m
    out: List[EdgeStep] = []
    cell = max(edge_search_m, 1.0)
    edge_grid = _bucket_edges(edges, cell)
    for e1 in edges:
        way_e1 = ways[e1.way_idx]
        if _role_grade_limit(way_e1, 1.0) is None:
            continue  # this edge's role is on the skip-list
        ax, ay = e1.a
        bx, by = e1.b
        dx = bx - ax
        dy = by - ay
        seg_len = math.hypot(dx, dy)
        if seg_len < 1.0:
            continue
        # Sample at interior t = 1/(N+1), 2/(N+1), ... N/(N+1).
        for k in range(1, samples_per_edge + 1):
            t = k / (samples_per_edge + 1)
            sx = ax + t * dx
            sy = ay + t * dy
            s_elev = e1.ea + t * (e1.eb - e1.ea)
            # Find closest OTHER-way edge to this sample.
            cx = int(math.floor(sx / cell))
            cy = int(math.floor(sy / cell))
            best_d2 = edge_search_m * edge_search_m
            best: Optional[Tuple[Edge, float, float, float]] = None
            for dcx in (-1, 0, 1):
                for dcy in (-1, 0, 1):
                    bucket = edge_grid.get((cx + dcx, cy + dcy))
                    if not bucket:
                        continue
                    for e2_idx in bucket:
                        e2 = edges[e2_idx]
                        if e2.way_idx == e1.way_idx:
                            continue
                        way_e2 = ways[e2.way_idx]
                        if _role_grade_limit(way_e2, 1.0) is None:
                            continue  # other edge's role on skip-list
                        if _airside_groundside_pair(way_e1, way_e2):
                            continue  # wall-separated boundary — step by design
                        if pair_ok is not None and not pair_ok(way_e1, way_e2):
                            continue  # caller's pair restriction (airside gate)
                        e2ax, e2ay = e2.a
                        e2bx, e2by = e2.b
                        e2dx = e2bx - e2ax
                        e2dy = e2by - e2ay
                        e2seg2 = e2dx * e2dx + e2dy * e2dy
                        if e2seg2 < 0.04:
                            continue
                        tt = ((sx - e2ax) * e2dx
                              + (sy - e2ay) * e2dy) / e2seg2
                        if tt < 0.0:
                            tt = 0.0
                        elif tt > 1.0:
                            tt = 1.0
                        px = e2ax + tt * e2dx
                        py = e2ay + tt * e2dy
                        d2 = (sx - px) * (sx - px) + (sy - py) * (sy - py)
                        if d2 < best_d2:
                            best_d2 = d2
                            best = (e2, tt, px, py)
            if best is None:
                continue
            if best_d2 > ctol * ctol:
                continue  # gap, not a shared edge — height difference allowed
            e2, tt, px, py = best
            e2_elev = e2.ea + tt * (e2.eb - e2.ea)
            step = abs(s_elev - e2_elev)
            # APRON TERRACE LOCKSTEP (see ``_check_vertex_to_edge_step``):
            # after the pre-solve split a declared joint is a cross-shape
            # pair 0.6 m apart, and its DECLARED step is the allowance.
            allow_step = edge_step_m
            if terrace_joints_m:
                allow_step += _terrace_step_allowance(
                    terrace_joints_m, sx, sy, px, py)
            # THE TUNNEL-TRENCH DECLARED STEP (see
            # ``_check_vertex_to_edge_step``): the facility's declared
            # floor→rim drop, and only the excess beyond it.
            if basin_declared:
                allow_step += _basin_declared_drop(
                    basin_declared, way_e1, ways[e2.way_idx],
                    s_elev, e2_elev)
            if step > allow_step + 1e-5:
                out.append(EdgeStep(
                    step_m=step,
                    distance_m=math.sqrt(best_d2),
                    way_v=ways[e1.way_idx],
                    way_e=ways[e2.way_idx],
                    vert_pt=(sx, sy),
                    proj_pt=(px, py),
                    elev_v=s_elev,
                    elev_proj=e2_elev))
    return out


# ── Reporting ───────────────────────────────────────────────────

def _label(w: Way) -> str:
    base = f"{w.role or '?'}/{w.ref or w.wid}"
    sid = w.tags.get("shapeID")
    return f"{base} [#{sid}]" if sid else base


def _print_violations(title: str, vios: List[Violation], top_n: int):
    n = len(vios)
    print(f"\n{title}: {n} violation{'s' if n != 1 else ''}")
    if not vios:
        return
    vios.sort(key=lambda v: -v.grade_pct)
    print(f"  worst {min(top_n, n)}:")
    for v in vios[:top_n]:
        print(f"    {v.grade_pct:6.2f}% (excess {v.excess_pct:+5.2f}%) "
              f"d={v.distance_m:6.2f}m |de|={v.de_m:5.2f}m  "
              f"{_label(v.way_a)} ({v.elev_a:.1f}) -> "
              f"{_label(v.way_b)} ({v.elev_b:.1f})")
    # Bucket distribution by excess.
    band_caps = [0.5, 1.0, 2.0, 5.0]
    band_counts = [0] * (len(band_caps) + 1)
    for v in vios:
        for bi, cap in enumerate(band_caps):
            if v.excess_pct < cap:
                band_counts[bi] += 1
                break
        else:
            band_counts[-1] += 1
    print("  excess distribution:")
    last = 0.0
    for bi, cap in enumerate(band_caps):
        print(f"    {last:.1f} → {cap:.1f}% over: {band_counts[bi]}")
        last = cap
    print(f"    {last:.1f}% → ∞ over: {band_counts[-1]}")


def _print_steps(title: str, steps: List[EdgeStep], top_n: int,
                 step_threshold_m: float):
    n = len(steps)
    print(f"\n{title}: {n} step{'s' if n != 1 else ''} > {step_threshold_m}m")
    if not steps:
        return
    steps.sort(key=lambda s: -s.step_m)
    print(f"  worst {min(top_n, n)}:")
    for s in steps[:top_n]:
        print(f"    step={s.step_m:5.2f}m  d={s.distance_m:5.2f}m  "
              f"vert={_label(s.way_v)} ({s.elev_v:.1f}) -> "
              f"edge={_label(s.way_e)} (proj {s.elev_proj:.1f})")


def _check_spine_curvature(ways, nodes, ll_to_m, taxi_axes,
                           noise_m: float = 0.03,
                           min_seg_m: float = 5.0):
    """Grade-CHANGE rate along each taxi axis' emitted profile —
    ``|g2 − g1| ≤ TAXIWAY_MAX_GRADE_CHANGE_PER_M·(L1+L2)/2`` plus a
    2-decimal-emit noise allowance ``noise_m·(1/L1 + 1/L2)`` (on short
    segments rounding alone swamps the rate; the rule is meaningful at
    vertical-curve scale).  The SAME constant the solver's
    ``_fair_spine_chains`` enforces.  Returns ``(count, worst_excess)``.
    """
    try:
        from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M
    except Exception:                                  # pragma: no cover
        return 0, 0.0
    k_rate = TAXIWAY_MAX_GRADE_CHANGE_PER_M
    _AIR = {"apron", "junction", "service_junction", "runway",
            "runway_crossing", "primary_parallel", "secondary_parallel",
            "stub", "cross_connector"}
    # emitted airside vertices with elevation, deduped by position
    pts = {}
    for w in ways:
        if w.tags.get("role") not in _AIR:
            continue
        ring = (w.nids[:-1] if len(w.nids) > 1 and w.nids[0] == w.nids[-1]
                else w.nids)
        for k, nid in enumerate(ring):
            if nid not in nodes or k >= len(w.elevs):
                continue
            e = w.elevs[k]
            if e is None:
                continue
            lat, lon = nodes[nid]
            x, y = ll_to_m(lat, lon)
            pts[(round(x, 1), round(y, 1))] = (x, y, float(e))
    pt_list = list(pts.values())
    n_kinks = 0
    worst = 0.0
    for entry in taxi_axes:
        poly = entry[0]
        if len(poly) < 2:
            continue
        # cumulative arc + per-point projection onto the axis
        arcs = [0.0]
        for i in range(1, len(poly)):
            arcs.append(arcs[-1] + math.hypot(poly[i][0] - poly[i - 1][0],
                                              poly[i][1] - poly[i - 1][1]))
        on_axis = []
        for (x, y, e) in pt_list:
            best_d = 0.6
            best_arc = None
            for i in range(len(poly) - 1):
                x1, y1 = poly[i]
                x2, y2 = poly[i + 1]
                dx, dy = x2 - x1, y2 - y1
                seg2 = dx * dx + dy * dy
                if seg2 < 1e-9:
                    continue
                t = ((x - x1) * dx + (y - y1) * dy) / seg2
                t = min(1.0, max(0.0, t))
                px, py = x1 + t * dx, y1 + t * dy
                d = math.hypot(x - px, y - py)
                if d < best_d:
                    best_d = d
                    best_arc = arcs[i] + t * math.sqrt(seg2)
            if best_arc is not None:
                on_axis.append((best_arc, e))
        if len(on_axis) < 3:
            continue
        on_axis.sort()
        # dedupe coincident arc positions
        prof = []
        for (a, e) in on_axis:
            if prof and a - prof[-1][0] < 0.5:
                continue
            prof.append((a, e))
        for t in range(1, len(prof) - 1):
            l1 = prof[t][0] - prof[t - 1][0]
            l2 = prof[t + 1][0] - prof[t][0]
            if l1 < min_seg_m or l2 < min_seg_m:
                continue
            g1 = (prof[t][1] - prof[t - 1][1]) / l1
            g2 = (prof[t + 1][1] - prof[t][1]) / l2
            allowance = (k_rate * 0.5 * (l1 + l2)
                         + noise_m * (1.0 / l1 + 1.0 / l2))
            ex = abs(g2 - g1) - allowance
            if ex > 0:
                n_kinks += 1
                rate_ex = ex / (0.5 * (l1 + l2))
                if rate_ex > worst:
                    worst = rate_ex
    return n_kinks, worst


# ── Main ────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════════════════════
# THE LAW FAMILY REGISTER — the census contract
# ══════════════════════════════════════════════════════════════════════
# Every violation family ``run_checks`` produces, in the exact order it
# concatenates them.  This register exists because per-lane census
# wrappers kept enumerating families BY HAND and kept missing some (one
# lane's private wrapper counted 12 of them and reported 9; another
# omitted ``terrace_joints_ll`` outright).  A hand-written family list is
# a frame error waiting to happen, so ``run_checks`` now fills
# ``family_out`` itself and ``tests/test_harness.py`` asserts that the
# register, the signature and the returned rows agree.
#
# Each entry: (key, human title, bucket) where bucket names which of the
# three returned lists the rows land in ("within" / "cross" / "steps").
# A NEW check added to ``run_checks`` MUST be added here in its emission
# position — the twin fails otherwise.
LAW_FAMILIES: Tuple[Tuple[str, str, str], ...] = (
    ("within_shape", "WITHIN-SHAPE vertex-pair grade", "within"),
    # THE ROAD CROSS-SECTION (owner ruling RULINGS 2026-08-25g, "ROADS ARE
    # LATERALLY FLAT").  Emitted immediately after ``within_shape``
    # because it is the same pair walk: a road ring's pairs partition by
    # angle to the ring axis, the ALONG ones staying in ``within_shape``
    # at the chord cap and the ACROSS ones landing here at the road's
    # transverse limit.  One pair, one family, never both.
    ("road_cross_section", "ROAD CROSS-SECTION (lateral) grade", "within"),
    ("plane_gradient", "PLANE GRADIENT (triangle surface)", "within"),
    ("runway_end_skirt", "RUNWAY-END SKIRT edge grade", "within"),
    ("terrace_joint_route", "APRON TERRACE JOINT crossing a taxi ROUTE",
     "within"),
    ("terrace_joint_strip", "APRON TERRACE JOINT inside a RUNWAY STRIP",
     "within"),
    ("terrace_actual_step", "APRON TERRACE ACTUAL step past its DECLARED step",
     "within"),
    ("basin_floor_declaration",
     "BASIN FACILITY floor DISAGREES with its own body depth", "within"),
    ("adjacent_ground_tear", "ADJACENT-GROUND graded-strip TEAR", "within"),
    ("strip_seam_tear", "ADJACENT-GROUND strip SEAM tear", "within"),
    ("transverse", "TRANSVERSE (cross-corridor) grade", "within"),
    ("drainage_spine", "DRAINAGE SPINE at or above its LOWER pavement",
     "within"),
    ("apron_lattice_membrane",
     "APRON LATTICE MEMBRANE pair over the apron's own budget", "within"),
    # THE AIRSIDE NO-STEP LAW (owner ruling RULINGS 2026-08-27, "NO
    # STEPS IN AIRSIDE PAVEMENT"; spec ``airside-no-step-law-spec.md``
    # §1.6).  ONE family carrying both of the ruling's bounds: the §1.1
    # LOCAL DIRECT-DISTANCE grade rows (priced against the solve's own
    # sidecar publication) and the §1.2 RATE-OF-CHANGE rows (the
    # strip_arc machinery extended to the membrane's own polylines).
    # They are one law — the ruling states them as a pair, "the
    # runway-style grade + curvature pair, applied to ALL airside
    # pavement" — and the census line reports the two terms' counts
    # separately so an A/B can still read them apart.  Emitted directly
    # after ``apron_lattice_membrane`` because it is the same membrane
    # seen at direct distance.
    ("airside_no_step",
     "AIRSIDE NO-STEP (direct-distance grade + rate of change)", "within"),
    ("lateral_contiguity", "LATERAL CONTIGUITY (road vs strictest class)",
     "within"),
    ("strip_longitudinal", "STRIP ABEAM-LONGITUDINAL grade", "within"),
    ("strip_arc", "STRIP LONGITUDINAL grade-CHANGE rate", "within"),
    ("resa_transverse", "RESA / END-CORRIDOR TRANSVERSE grade", "within"),
    ("raoa", "RAOA grade-change rate (ICAO only)", "within"),
    ("drainage_minimum", "SURFACE FLATTER than its drainage minimum",
     "within"),
    ("runway_crown", "RUNWAY CROWN below its DECLARED drop", "within"),
    ("wall_in_runway_strip", "RETAINING WALL inside a RUNWAY STRIP", "within"),
    ("stacked_nodes", "STACKED NODES (one coordinate, values disagree)",
     "within"),
    ("cross_shape", "CROSS-SHAPE proximity grade", "cross"),
    ("frontage_near_miss",
     "NEAR-MISS BUILDING FRONTAGE (pad ↔ soft pavement across a sliver)",
     "cross"),
    ("vertex_to_edge_step", "VERTEX-TO-EDGE step", "steps"),
    ("mid_edge_step", "MID-EDGE step", "steps"),
)


# ══════════════════════════════════════════════════════════════════════
# THE STEP EXEMPTION REGISTER — one authority, every reader
# ══════════════════════════════════════════════════════════════════════
# A LAW EXEMPTION that lived as a hand-written closure in TWO report/gate
# files at once (``tools/harness/census.py`` and
# ``tests/test_pavement_grade.py``) — the census-wrapper defect class
# exactly: one law, two copies, and nothing asserting they agree.  It is
# registered here so both readers call ONE implementation and a change to
# the exemption cannot move one acceptance number without moving the
# other.
#
#: Exemption name -> the ruling that grants it.  A step row matching a
#: registered exemption is LAWFUL geometry, not a defect.
STEP_EXEMPTIONS: Dict[str, str] = {
    "building_to_building":
        "owner 2026-06-20: two adjacent terminal/hangar pads are "
        "independent FLAT surfaces and may legitimately sit at different "
        "floor levels with a facade/wall between them (SPJC building16 "
        "@30.9 abuts building30 @29.5 = a 1.4 m terminal-to-terminal step, "
        "correct in X-Plane).  A pad-vs-pavement step is still gated.",
}

#: The families ``step_exempt`` is defined over (the ``steps`` bucket).
STEP_EXEMPT_FAMILIES: Tuple[str, ...] = tuple(
    key for key, _title, bucket in LAW_FAMILIES if bucket == "steps")


def step_exempt(row) -> Optional[str]:
    """The NAME of the registered exemption this step row holds, else None.

    ``bool(step_exempt(row))`` is the predicate both the harness census and
    the acceptance gate filter with.  Returns the name rather than a bare
    bool so a report can say WHICH exemption applied without a second
    lookup table.

    Total where the two hand-written copies were partial: a row missing
    ``way_v``/``way_e`` returns None instead of raising.  Every ``EdgeStep``
    ``run_checks`` emits carries both, so the answer is identical on the
    measured population — see ``tests/test_census_instrument.py``.
    """
    way_v = getattr(row, "way_v", None)
    way_e = getattr(row, "way_e", None)
    if way_v is None or way_e is None:
        return None
    tags_v = getattr(way_v, "tags", None) or {}
    tags_e = getattr(way_e, "tags", None) or {}
    if (tags_v.get("role") == "building"
            and tags_e.get("role") == "building"):
        return "building_to_building"
    return None


# ══════════════════════════════════════════════════════════════════════
# VERSION-DEFERRED ADJUDICATION (owner ruling RULINGS d48bc0a)
# ══════════════════════════════════════════════════════════════════════
# INSTRUMENTS REPORT, THE LAW ADJUDICATES.  The owner deferred a named
# grade-law family to a later version; the census must keep MEASURING it
# (a silently dropped family is the census-wrapper defect) while the
# acceptance verdict must not be blocked by it.  Both halves are law:
#
#   RULINGS d48bc0a (2026-08-05, "Drainage scope for this version"):
#   runway crowns and pavement-edge (unpaved-area) drainage are IN;
#   INTERIOR PAVEMENT DRAINAGE GRADING — the FAA apron drainage-minimum
#   shaping, KCLT's 1,099-row family and its siblings — is
#   VERSION-DEFERRED: "the census still REPORTS the family (instruments
#   report), but the acceptance gate adjudicates it VERSION-DEFERRED with
#   this ruling as the citation … Flat-world zero is therefore: zero
#   adjudicated rows EXCLUDING the version-deferred classes, which appear
#   in every report under their own heading."
#
# Until this register existed, NO harness instrument implemented it (the
# c4tip battery subtracted the family BY HAND, and the oracle's
# ``compliance`` verdict tested instrument-zero — which the owner
# explicitly separated from law compliance on 2026-08-02).  This is the
# one place the deferral is spelled; ``harness/census.py`` and
# ``harness/oracle.py`` read it, and ``tests/test_harness.py`` asserts
# every key here is a registered family.
DEFERRED_ADJUDICATION_RULING = "d48bc0a"
VERSION_DEFERRED_FAMILIES: Dict[str, str] = {
    "drainage_minimum":
        "interior pavement drainage-minimum shaping — VERSION-DEFERRED by "
        "RULINGS d48bc0a (2026-08-05, 'Drainage scope for this version'); "
        "reported always, never adjudicated, never silently dropped",
}


# ══════════════════════════════════════════════════════════════════════
# THE RETIRED LAWS — a rule the owner WITHDREW, recorded not deleted
# ══════════════════════════════════════════════════════════════════════
#: A law that retires stops producing rows, and so does a walk that goes
#: blind — the output is the same zero either way.  This repo has now had
#: both inside ONE family within a week: §B3's groundside half lost 11,932
#: rows across the five baseline airports to a role migration (RULINGS
#: 2026-08-13b, the OTHH −639 census-blindness verdict) and then, once
#: restored and readable, was withdrawn by the owner (RULINGS 2026-08-14).
#: The register is the difference between those two zeros.
#:
#: Key -> what was withdrawn, by which ruling.  Unlike
#: ``VERSION_DEFERRED_FAMILIES`` these keys are NOT family keys: a retired
#: law may be one HALF of a family's domain, which is exactly the case
#: here — the family still runs, on aprons.  ``tests/test_harness.py``
#: asserts each entry's surfaces really are absent from the family's walk,
#: so a "retired" law that quietly kept firing fails.
RETIRED_LAW_RULING = "2026-08-14"
RETIRED_LAWS: Dict[str, dict] = {
    "drainage_minimum::groundside": {
        "family": "drainage_minimum",
        "roles": ("groundside_pavement", "service_road", "service_junction"),
        "why":
            "the PROVISIONAL 1.0 % landside drainage minimum (owner "
            "question 3, version-deferred by RULINGS d48bc0a, never "
            "adjudicated) — RETIRED by RULINGS 2026-08-14, \"DRAINAGE "
            "RULING SCOPE CLARIFIED\": what retires is \"ADDING drainage "
            "curvature (crown / minimum-slope requirements) to TAXIWAY and "
            "ROAD pavement surfaces; those may be flat for the sim\".  The "
            "APRON half of the family did NOT retire (FAA §5.9.1.1, a "
            "cited number), nor did the drainage SPINE in enclosed areas, "
            "the drainage slope on ADJACENT GROUND beside runways and "
            "taxiways, or the runway crown",
    },
}


#: OUT-OF-SCOPE ADJUDICATION CLASSES — rows the law never governed, as
#: opposed to rows a later version will govern (the version-deferred
#: register above).  Keyed by the ``out_of_scope`` stamp ``run_checks``
#: puts on the row.
OUT_OF_SCOPE_RULING = "2026-08-06 ONE graph"
OUT_OF_SCOPE_CLASSES: Dict[str, str] = {
    "role_less_host_duplicate":
        "every way of the row is ROLE-LESS ARTICULATION geometry (an "
        "o4_feature way with no role tag) whose HOST shape's vertex set "
        "COVERS it.  Lead ruling " + ROLE_LESS_HOST_RULING + ": such a way "
        "is articulation, not a surface — \"where their geometry duplicates "
        "a host way's, rows belong to the HOST ONLY: one geometry, one row "
        "set\".  The host's own rows are that row set; this one is the "
        "duplicate.  REPORTED under its own heading and never dropped, the "
        "same treatment the version-deferred family gets",
    _CROWN_OUT_OF_SCOPE:
        "the crown-shortfall row sits at a RUNWAY OR TAXIWAY "
        "INTERSECTION, where the transverse MINIMUM is expressly not "
        "required: ICAO Annex 14 §3.1.19 — the runway transverse "
        "\"should not exceed 1.5 per cent or 2 per cent, as applicable, "
        "nor be less than 1 per cent EXCEPT AT RUNWAY OR TAXIWAY "
        "INTERSECTIONS\" (FAA Table 3-6 S-1 carries the same exception).  "
        "``runway_crossing`` IS that surface in this engine, and a node "
        "welded to one is on its boundary.  MEASURED and counted in the "
        "family like every other out-of-scope class; only the acceptance "
        "verdict skips it",
    "disconnected_ring":
        "the row lies wholly inside a groundside ring the ONE route graph "
        "does not reach — no route, frontage or weld coupling to the "
        "solved network.  Owner RULINGS 2026-08-06 (\"ONE graph\"): such "
        "geometry is NOT SOLVED, stays at its DEM seed by construction "
        "and mints nothing.  The rings come from the SOLVE's own answer "
        "(the disconnected_rings sidecar key), never a second predicate",
}


def row_adjudicated(family_key: str, row) -> bool:
    """Is this row part of the ADJUDICATED population?

    THE predicate ``adjudication`` splits on, factored out so a second
    reader (the site census's materiality accumulation, which may only be
    funded by real defects) tests the same thing rather than re-deriving
    "not deferred and not out of scope" — the census-wrapper defect at
    row granularity."""
    if family_key in VERSION_DEFERRED_FAMILIES:
        return False
    return not getattr(row, "out_of_scope", None)


def adjudication(rows_by_family_key) -> dict:
    """THE deferred-adjudication split for one census.

    ``rows_by_family_key`` is any iterable of ``(family_key, row)`` pairs
    (what ``harness/census.py`` already builds).  Returns

        {"ruling", "deferred_families", "deferred_total",
         "adjudicated_total", "adjudicated_by_side", "pass", "note"}

    where ``pass`` is the LAW's verdict — zero ADJUDICATED rows — and the
    deferred rows are carried alongside under their own heading rather
    than folded into either number.  One implementation, so the census,
    the oracle and any report quoting an "ADJ" number cannot drift (the
    battery computed exactly this by hand).
    """
    from collections import Counter as _Counter
    deferred = _Counter()
    out_of_scope = _Counter()
    adjudicated = []
    for key, row in rows_by_family_key:
        # The split predicate is ``row_adjudicated``; the two branches below
        # only name WHICH heading a non-adjudicated row is reported under.
        if key in VERSION_DEFERRED_FAMILIES:
            deferred[key] += 1
        elif getattr(row, "out_of_scope", None):
            # OUT OF SCOPE BY LAW, not by instrument choice.  The only
            # member today is ``disconnected_ring`` (RULINGS 2026-08-06,
            # "ONE graph"): geometry the route graph does not reach is
            # NOT SOLVED, so a grade row on it is not a violation of a
            # law that never governed it.  The rows are still measured
            # and still counted in their family — this is the same
            # report-but-do-not-adjudicate treatment the version-
            # deferred family gets, with its own heading.
            out_of_scope[row.out_of_scope] += 1
        else:
            adjudicated.append(row)
    sides = _Counter(row_side(r) for r in adjudicated)
    return {
        "ruling": DEFERRED_ADJUDICATION_RULING,
        "deferred_families": {k: {"n": deferred.get(k, 0), "why": why}
                              for k, why in
                              sorted(VERSION_DEFERRED_FAMILIES.items())},
        "deferred_total": int(sum(deferred.values())),
        "out_of_scope_classes": {k: {"n": v, "why": OUT_OF_SCOPE_CLASSES.get(
            k, "unnamed out-of-scope class")}
            for k, v in sorted(out_of_scope.items())},
        "out_of_scope_total": int(sum(out_of_scope.values())),
        "adjudicated_total": len(adjudicated),
        "adjudicated_by_side": {
            "airside": sides.get("airside", 0),
            "groundside": sides.get("groundside", 0),
            "mixed": sides.get("mixed", 0),
            "unknown": sides.get("unknown", 0),
        },
        "pass": not adjudicated,
        "note": (f"adjudicated = every law-true row EXCLUDING the "
                 f"version-deferred classes (RULINGS "
                 f"{DEFERRED_ADJUDICATION_RULING}) and the out-of-scope "
                 f"classes (RULINGS {OUT_OF_SCOPE_RULING}); both are "
                 f"REPORTED under their own headings and never dropped"),
    }


# ══════════════════════════════════════════════════════════════════════
# THE MATERIALITY FLOOR (owner ruling RULINGS 2026-08-07)
# ══════════════════════════════════════════════════════════════════════
#
# THE OWNER'S WORDS: "when I was building osm patch files by hand I never
# set an elevation in increments smaller than 1 meter… we don't want any
# sharp bumps, but we don't need to be grading to less than 0.5m."
#
# The interview ruled it ADJUDICATION-ONLY first: the law and the solver
# are untouched, the census keeps MEASURING every row, and a defect SITE is
# ACTIONABLE only if its unlawful excess ACCUMULATES to the floor.  Value
# quantization of the OUTPUT was REJECTED in the same ruling (the
# dense-node staircase trap — the hand files were smooth at 1 m increments
# because they were SPARSE), which is why nothing here rounds a value.
#
# Three parts, three knobs, each carrying its clause:
#
#   (1) THE FLOOR       a site under 0.5 m of accumulated unlawful excess
#                       is not actionable.
#   (2) THE SHARP GUARD …unless one of its rows is a single step >= 0.15 m
#                       or sits at >= 2x its own cap.  "We don't want any
#                       sharp bumps" is the half of the sentence a bare
#                       accumulation floor would throw away: 40 rows of
#                       1 cm and one 20 cm cliff accumulate the same.
#   (3) RUNWAY EXEMPT   a site touching the runway family is ALWAYS
#                       actionable — reg-derived precision governs there
#                       (CIFP threshold values, RUNWAY_END_GRADE, the FAA
#                       vertical-curve K-factors), and "0.5 m is close
#                       enough" is not a statement anyone made about a
#                       runway profile.
#
# The floor is PROVISIONAL (the owner said so), which is why sub-floor
# sites are REPORTED under their own label rather than dropped — the
# counted-never-dropped convention this repo already runs on
# (VERSION_DEFERRED_FAMILIES, OUT_OF_SCOPE_CLASSES).  Moving the constant
# must change a number in a report, never make evidence disappear.
MATERIALITY_FLOOR_RULING = (
    "2026-08-07 (owner) — Materiality floor: 0.5 m accumulated, guarded, "
    "runways exempt")

#: (1) THE FLOOR, metres of ACCUMULATED unlawful excess per SITE.
MATERIALITY_FLOOR_M = 0.5

#: (2a) THE SHARP GUARD, single-step half: metres.  A step this tall is a
#: bump the owner named ("we don't want any sharp bumps") regardless of how
#: little the site accumulates.
MATERIALITY_SHARP_STEP_M = 0.15

#: (2b) THE SHARP GUARD, steepness half: a MULTIPLE of the row's own cap.
#: Expressed as a multiple rather than an absolute grade because the caps
#: this battery spans differ by more than 5x (1 % apron … 8 % service
#: road), and "twice the law" means the same thing on all of them.
MATERIALITY_SHARP_GRADE_CAP_MULTIPLE = 2.0

#: (3) THE RUNWAY FAMILY.  The repo's own definition, in two places that
#: already agree: ``tools/flex_audit.RUNWAY_ROLES`` and the "# runway
#: family" head of ``layout.AUTHORITY_PRECEDENCE`` (ROLE_RUNWAY,
#: ROLE_RUNWAY_CROSSING — the runway surface and the runway-interpolated
#: crossings, which ``_ROUTE_BAND_SKIP_ROLES`` calls "the anchors
#: themselves").  NOTE (blast role-literal hazard): renaming a ROLE_* VALUE
#: in auto_patch/layout.py silently empties this set.
MATERIALITY_RUNWAY_FAMILY_ROLES: FrozenSet[str] = frozenset({
    "runway", "runway_crossing",
})

#: THE SUB-FLOOR LABEL — the counted-never-dropped register for sites the
#: floor takes out of the actionable count.  Same shape as
#: ``VERSION_DEFERRED_FAMILIES`` / ``OUT_OF_SCOPE_CLASSES``: label -> why,
#: read by the census's site section, twin-asserted in tests/test_harness.py.
MATERIALITY_SUB_FLOOR_LABEL = "sub_floor"
MATERIALITY_SUB_FLOOR_CLASSES: Dict[str, str] = {
    MATERIALITY_SUB_FLOOR_LABEL:
        "the site's ADJUDICATED rows accumulate less than the "
        "materiality floor of unlawful excess AND no row trips the sharp "
        "guard AND no runway-family role is present — owner RULINGS "
        "2026-08-07 (\"we don't need to be grading to less than 0.5m\").  "
        "The site is still measured, still carries every row, and is "
        "reported under this label in every site table; the floor is "
        "PROVISIONAL and moving it must change a number here, never make "
        "a site disappear",
}

#: FAMILIES A METRES FLOOR CANNOT MEASURE.  ``lateral_contiguity`` prices a
#: CAP, not a surface: its ``de_m`` is ``eff - law_cap``, a bare decimal
#: GRADE difference, and the law priced no span at all (``distance_m == 0``,
#: ``elev_a == elev_b == 0``).  Summing that number into a metre
#: accumulation is the two-instruments failure inside one headline — 0.03
#: would read as 3 cm of grading owed when it is a 3-percentage-point cap
#: breach.  A FLOOR MAY ONLY RELAX WHAT IT CAN MEASURE, so a site carrying
#: one of these rows stays ACTIONABLE and says why.  (Measured on the frame
#: of record: this is the ONLY family emitting zero-span rows — 17 of
#: 30,548 — every other zero-span row shape the code can construct is a
#: genuine step in metres.)
MATERIALITY_UNMEASURED_FAMILIES: Dict[str, str] = {
    "lateral_contiguity":
        "the row prices a CAP, not metres — de_m is a grade difference "
        "(eff - law_cap) and the law priced no span — so a metres floor "
        "has nothing to compare.  The site stays ACTIONABLE: a floor may "
        "only relax what it can measure",
}

#: THE ACCUMULATION RULE, in one sentence, quoted verbatim into every site
#: report so an actionable count is never read without the summation that
#: produced it (the ``SITE_RULE`` convention one level up).
MATERIALITY_ACCUMULATION_RULE = (
    "a site's ACCUMULATION is the sum of row_excess_m over its ADJUDICATED "
    "rows only (a version-deferred or out-of-scope row is not a defect and "
    "may not fund a defect's materiality).  row_excess_m is derived from "
    "the fields the row already carries, never re-measured: for a STEP row "
    "the step height; for a graded pair the metres its elevation "
    "difference exceeds its own cap over its own span "
    "(excess_pct/100 x distance_m), floored at 0 and capped at |de| "
    "because a row can never be more unlawful than its whole elevation "
    "difference; and for a row the law priced as a PURE VERTICAL quantity "
    "(distance_m == 0, or a cap-0 law that reports grade_pct == 0 such as "
    "the drainage-spine dam) the magnitude itself.  A row from an "
    "UNMEASURED family (MATERIALITY_UNMEASURED_FAMILIES: the "
    "cap-not-metres shapes) contributes 0 and makes its site actionable "
    "outright")


def row_cap_pct(row) -> Optional[float]:
    """The row's OWN cap, in percent — ``grade_pct - excess_pct``.

    The cap is not a field on ``Violation``; it is the difference of two
    fields every graded row carries, which is why this is an accessor and
    not a second cap resolver (``_role_grade_limit`` is the only one, and
    it needs the way's tags, the sidecar's baked caps and the fan-ramp
    zones — none of which a row carries).  ``None`` when the row carries no
    grade semantic at all (a step row)."""
    grade = getattr(row, "grade_pct", None)
    excess = getattr(row, "excess_pct", None)
    if grade is None or excess is None:
        return None
    return float(grade) - float(excess)


def row_step_m(row) -> Optional[float]:
    """The row's SINGLE STEP height in metres, or ``None`` if the row is a
    graded pair rather than a vertical discontinuity.

    Two shapes carry one: an ``EdgeStep`` (``step_m``), and a ``Violation``
    the law priced over ZERO run — the terrace ACTUAL-step and the
    lateral-contiguity rows, whose ``distance_m`` is 0 by construction
    because there is no span to divide by."""
    step = getattr(row, "step_m", None)
    if step is not None:
        return abs(float(step))
    dist = getattr(row, "distance_m", None)
    de = getattr(row, "de_m", None)
    if de is not None and (dist is None or float(dist) == 0.0):
        return abs(float(de))
    return None


def row_excess_m(row, family_key: Optional[str] = None) -> float:
    """The row's UNLAWFUL EXCESS in metres — see
    ``MATERIALITY_ACCUMULATION_RULE``, which states this function in one
    sentence and is printed with every count it produces.

    NOT ``row_magnitude``: a 3.2 m rise over 200 m of taxiway at a 1.5 %
    cap is a 3.2 m MAGNITUDE and a 0.2 m EXCESS, and it is the second
    number the owner's floor is about ("we don't need to be grading to less
    than 0.5m" is a statement about how much grading is owed, not about how
    much relief exists).

    ``family_key`` is the row's law family when the caller has it (the site
    census always does).  It is the ONE thing this function cannot read off
    the row, and it is what keeps a cap-not-metres family
    (``MATERIALITY_UNMEASURED_FAMILIES``) out of a metre sum.
    """
    if family_key is not None and family_key in MATERIALITY_UNMEASURED_FAMILIES:
        return 0.0
    step = getattr(row, "step_m", None)
    if step is not None:
        return abs(float(step))
    de = abs(float(getattr(row, "de_m", 0.0) or 0.0))
    grade = getattr(row, "grade_pct", None)
    excess = getattr(row, "excess_pct", None)
    dist = getattr(row, "distance_m", None)
    if grade is None or excess is None or not grade:
        # No grade semantic (a cap-0 law: the drainage-spine dam reports
        # grade 0 / excess 0 and puts the whole shortfall in ``de_m``), or
        # a row with no grade fields at all.
        return de
    if dist is None or float(dist) <= 0.0:
        # Priced over zero run — the magnitude IS the excess.
        return de
    return max(0.0, min(de, float(excess) / 100.0 * float(dist)))


def row_is_sharp(row) -> Optional[str]:
    """The NAME of the sharp-guard clause this row trips, else ``None``.

    ``"step"`` — a single step at or over ``MATERIALITY_SHARP_STEP_M``.
    ``"grade"`` — a local grade at or over
    ``MATERIALITY_SHARP_GRADE_CAP_MULTIPLE`` x its own cap; a row whose cap
    is ZERO OR NEGATIVE (a cap-0 law, or the near-miss frontage sentinel)
    trips on ANY positive grade, because a law that allows no grade at all
    is exceeded by any of it.  Returns the clause name rather than a bool so
    a report can say WHICH half fired without a second lookup.
    """
    step = row_step_m(row)
    if step is not None and step >= MATERIALITY_SHARP_STEP_M:
        return "step"
    cap = row_cap_pct(row)
    grade = getattr(row, "grade_pct", None)
    if cap is None or grade is None:
        return None
    grade = float(grade)
    if cap > 0.0:
        if grade >= MATERIALITY_SHARP_GRADE_CAP_MULTIPLE * cap:
            return "grade"
    elif grade > 0.0:
        return "grade"
    return None


def row_runway_family(row) -> bool:
    """True when either of the row's ways is a RUNWAY-FAMILY surface —
    read through ``effective_role`` so a role-less articulation way sided
    with a runway host is exempt with it."""
    a = getattr(row, "way_a", None) or getattr(row, "way_v", None)
    b = getattr(row, "way_b", None) or getattr(row, "way_e", None)
    for w in (a, b):
        if w is None:
            continue
        if effective_role(w) in MATERIALITY_RUNWAY_FAMILY_ROLES:
            return True
    return False


#: Sidecar key -> ``run_checks`` keyword.  THE contract between an emitted
#: patch and every reader of it.  ``law_context_from_sidecar`` is the only
#: implementation; the CLI, ``tools/harness/census.py`` and the pytest
#: fixtures all go through it, so a new sidecar key is wired in ONE place.
#: (``axes``/``routes`` are the legacy pre-exact spelling and are used only
#: when ``axes_exact`` is absent — see ``law_context_from_sidecar``.)
SIDECAR_LAW_KEYS: Dict[str, str] = {
    "axes_exact": "taxi_axes_ll",
    "routes_exact": "routes_ll",
    "anchor": "anchor",
    "seam_pins": "seam_pins_ll",
    "mesh_edges": "mesh_edges_ll",
    "crown_drops": "crown_drops_ll",
    "crown_centerline": "crown_centerline_ll",
    "pair_caps": "pair_caps_ll",
    "terrace_joints": "terrace_joints_ll",
    "fan_ramp_zones": "fan_ramp_zones_ll",
    # THE APRON INTERIOR LATTICE's own law edges (spec
    # heca-apron-round2 Amendment 1 section 1b, Amendment 2 clause 3).
    # LAW INPUT, and the only possible kind: a lattice edge joins two
    # INTERIOR nodes that lie on no ring, so no ring-adjacency rule can
    # discover it and no cap table can re-derive its budget.  The solve
    # priced each edge through classify_pair at the apron's own cap and
    # publishes the pair WITH that budget, so the family below checks
    # the emitted membrane against the law the solver actually built to
    # — one law, one number, no second opinion.
    "apron_lattice_edges": "apron_lattice_edges_ll",
    # THE AIRSIDE NO-STEP LAW's direct-distance law edges (owner ruling
    # RULINGS 2026-08-27; spec ``airside-no-step-law-spec.md`` §1.6).
    # LAW INPUT of the same kind and for a stronger reason: the pair may
    # cross a SHAPE BOUNDARY, so no within-shape rule can rediscover it,
    # and its cap came out of the pair's own frontage / corridor /
    # back-edge / strip context.  The solve publishes the pair with the
    # budget it built to; the family below prices EXACTLY that list.
    "airside_no_step_edges": "airside_no_step_edges_ll",
    # THE BACK-EDGE ZONES the apron 5 % class was priced with (owner
    # ruling RULINGS 2026-08-24).  LAW INPUT: the census reaches
    # ``grade_law.is_apron_interior`` through the SAME context field the
    # bake filled, so a census without this key would price every
    # back-edge pair strict and invent violations the law never had.
    "interior_zones": "interior_zones_ll",
    "disconnected_rings": "disconnected_rings_ll",
    # THE DECLARED BASIN FACILITIES (spec docs/specs/
    # tunnel-trench-law-and-basin-floor-spec.md §1).  LAW INPUT since this
    # round — it was EVIDENCE while nothing read it, and the census then
    # priced every by-law trench wall as a step (LEMD 11,110 rows of
    # 12,253, OTHH 5,616 of 5,871).  The floor→rim drop each facility
    # declares is the allowance its own contacts are judged against, and
    # its two bottom instruments are the ``basin_floor_declaration``
    # family — so a census without this key would judge a law the build
    # never ran under, in both directions.
    "basin_facilities": "basin_facilities",
    "ruleset": "ruleset",
    # THE BOUND TRANSECTS (owner ruling 2026-08-21; spec section 11 +
    # AMENDMENT A1 section 8b).  LAW INPUT, not evidence: the census
    # re-walks the emitted ring and joins these to report priced / bound /
    # unbound / broken_by_emit, which is this round's measurement.
    "xsection_spans": "xsection_spans",
}

#: Sidecar keys that are EVIDENCE, not law input: they are reported by the
#: census but never passed to ``run_checks``.  Every key an emitted sidecar
#: carries must appear here or in ``SIDECAR_LAW_KEYS`` (twin-asserted), so a
#: newly emitted key can never be silently ignored by every reader.
SIDECAR_EVIDENCE_KEYS: Tuple[str, ...] = (
    "axes",                       # legacy per-size-split axes
    "routes",                     # legacy chained routes
    "triangle_plane_unresolved",  # count of unresolved triangle vertices
    # THE PAD-SEAT FEASIBILITY GATE (owner ruling RULINGS 2026-08-24c):
    # pad seats that cannot reach their governing centerline anchor within
    # 1 % x chord.  EVIDENCE, deliberately: a seat defect is caught at
    # SEATING time and is not surface debt, so it is reported beside the
    # census and never adjudicated as a law family — which is also what
    # keeps this round's acceptance counts comparable with the last.
    # THE BAND AT PAD FRONTAGE POINTS (lead order 2026-08-24) — evidence
    # for the seat adjudication, reported and never adjudicated.
    "frontage_band",
    "pad_seat_infeasible",
    # THE ALTERNATION INSTRUMENT (owner ruling RULINGS 2026-08-25h, spec
    # ``service-road-apron-spine-spec.md`` §3.2).  EVIDENCE, deliberately
    # and by the spec's own word ("report-first"): a shared apron/road
    # edge should carry ONE solved value series, and this counts the
    # adjacent station pairs whose authorship alternates past the
    # tolerance.  It is watched, never adjudicated — making it a law
    # family would re-found the acceptance bar, which is the owner's call
    # and not this round's.
    "edge_alternation",
    # How many service sub-segments were recognised as APRON SPINES in
    # this build (§1).  Evidence for reading the line above: an
    # alternation count means something different at 0 spines than at 200.
    "apron_spine_segments",
    "apron_seniority",            # the apron staged solve's SENIOR/INTERIOR
                                  # partition per apron ring node (spec
                                  # apron-staged-solve-spec.md section 3):
                                  # evidence about the SOLVE, so the census
                                  # can say whether a senior node moved in
                                  # the interior pass without re-deriving
                                  # the partition it did not run.
    "band_clamp_nodes",           # the writeback band clamp's own sites +
                                  # deltas: evidence about the SOLVE, which
                                  # the census reports and never re-judges
    "terrace_certificates",       # the panelization evidence chain
    # FINAL BAND EXCESS (cycle-5 item 7): the build's own post-solve band
    # MEMBERSHIP report.  EVIDENCE, not law input — the census does not
    # re-judge it (route_band lives in-memory, on the solver's graph); it is
    # here so "did this patch ship with vertices outside their band?" is
    # answerable from the artifacts instead of only from a pytest run.
    "band_excess",
    # (``basin_facilities`` was here — an EVIDENCE key nothing read —
    # until the tunnel-trench declared-step law made it LAW INPUT; it now
    # lives in ``SIDECAR_LAW_KEYS`` above.  Its own spec is
    # basin-rim-flush-seating-spec.md section 2.1e item E2.)
    # SERVICE-CORRIDOR FREE-END DEM TIES (corridor-joins round, spec
    # ``docs/specs/corridor-joins-round-spec.md`` rulings 3 + 4(b)).  One
    # record per anchored corridor terminus: its lat/lon, the AMBIENT DEM
    # the build read there, the target it was anchored at (clamped into the
    # road cap's reach where terrain is out of reach) and the terminal
    # cross-section's node count.  EVIDENCE, never law input — the census
    # judges the emitted road by the ordinary grade families; this exists so
    # "did the road reach GROUND?" is answerable from the artifacts, in the
    # BUILD's own DEM frame, which an offline DEM read cannot reproduce
    # (warm-vs-cold has moved terrain 12 m).  Read by
    # ``tools/corridor_axis_coverage.py --free-ends``.
    "svc_free_ends",
    # THE FLAT-SITE EVIDENCE RECORD (spec docs/specs/
    # flat-site-detector-spec.md section 2).  The detector's four
    # signals + verdict, measured at the build's DEM-in-hand point:
    # CIFP threshold consensus, DEM relief vs its own SOURCE CLASS's
    # noise floor over the pavement+boundary+margin extent, the
    # DEM-vs-instrument offset, and the pack-object consensus.
    # REPORT-ONLY — nothing in the law reads it, and the census
    # re-judges none of it; it is here so "did this patch ship from a
    # site whose DEM was pure noise?" is answerable from the artifact.
    "site_class",
    # THE NODELESS-INTERIOR INSTRUMENT (spec docs/specs/
    # heca-apron-round2-spec.md section 2).  One record per apron-role
    # polygon carrying an interior disk of radius >
    # ``config.APRON_NODELESS_RADIUS_M`` with ZERO emitted vertices.
    # EVIDENCE, and the most important kind: this is the census's own
    # BLIND SPOT reported by the build.  The census prices PAIRS OF
    # EMITTED NODES, so a region with no nodes yields no rows and reads
    # as compliant however wrong it is — HECA's 215 x 430 m void passed
    # three rounds of censuses at 1,679 while carrying a visible cliff.
    # Printed at ZERO too (zero-of-zero is not a pass).
    "nodeless_interiors",
    # THE GAP-BRIDGING SPINE's provenance (same spec, section 1.2): one
    # record per synthesized bridging centerline — the two route ends it
    # joins (apt.dat 1201 node ids where nameable), its length and its
    # inherited size letter.  EVIDENCE: the census judges the bridge's
    # emitted pavement by the ordinary grade families like any other
    # route; this exists so a reader can NAME a centerline that is in
    # the patch but in no upstream feed.
    "gap_spine_bridges",
    # THE STAND-DOWN (gap-spine-bridge-stand-down-spec Amendment 1): one
    # record when this patch is the bridge-free RETRY of a build the
    # post-solve band law refused with bridges minted.  EVIDENCE — a
    # stand-down is not a defect row; it says the surface in this patch
    # was adjudicated by an interventional re-run, and which refusal it
    # answered.  Counted, never re-judged.
    "gap_spine_stand_down",
    # THE PAD BINDING ROUTES (spec docs/specs/pad-binding-routes-spec.md
    # §1.4/§1.5).  EVIDENCE, deliberately: per pad, the recorded route
    # that bound its seat on each side — anchor, anchor value, route
    # budget, plan length, hop chain.  The census REPORTS it and
    # adjudicates nothing from it; the surface those seats produced is
    # judged by the ordinary law families, exactly as before.  It is here
    # so an emitted patch answers "which route bound this pad?" without a
    # rebuild (``tools/trace_reach_route.py --from-sidecar``).
    "pad_binding_routes",
)


def law_context_from_sidecar(osm_path, *, announce: bool = False) -> dict:
    """Read the patch's ``.axes.json`` sidecar and return the ``run_checks``
    law keywords it declares — THE single sidecar reader.

    The sidecar is the CONTRACT: it carries the axes/routes the solver
    graded to, the projection anchor, the seam pins, the solver's junction
    mesh, the crown field, the baked pair caps, the declared apron-terrace
    joints and the REGION RULESET the build actually ran under.  A reader
    that drops any one of them silently judges a different law than the
    build ran (both known frame errors in this repo were exactly that).

    Raises ``FileNotFoundError`` when there is no sidecar: a context-free
    check overcounts by construction and must never be mistaken for a
    census (memory ``check-grade-needs-law-true-frame``).  Callers that
    genuinely want the bare frame call ``run_checks`` with no law kwargs.
    """
    import json as _json
    side = Path(str(osm_path) + ".axes.json")
    if not side.exists():
        raise FileNotFoundError(
            f"no axes sidecar for {osm_path} — refusing a context-free run. "
            f"Every emit writes one (the config.LOG_VERBOSITY gate was "
            f"removed 2026-08-05), so a missing sidecar means the patch was "
            f"not emitted by this tree — rebuild through "
            f"tools/harness/build_airport.py.")
    data = _json.loads(side.read_text())
    ctx: dict = {}
    exact = data.get("axes_exact") or None
    if exact:
        # exact build_context mirror: (pts, seg_caps, route_ordinal,
        # is_service).  The 5th slot of the reader's tuple carries the
        # SERVICE flag through to the centerline rebuild — a truck route is
        # not an aircraft spine (grade_graph._reads_service_spines), and the
        # solver and this reader must agree on that or they judge two
        # different laws.  Sidecars written before the flag existed carry
        # 3-element entries and read as all-taxi, which is how they were
        # graded.
        ctx["taxi_axes_ll"] = [
            (e[0], e[1], None, e[2], bool(e[3]) if len(e) > 3 else False)
            for e in exact]
        ctx["routes_ll"] = data.get("routes_exact") or None
    else:
        ctx["taxi_axes_ll"] = data.get("axes") or None
        ctx["routes_ll"] = data.get("routes") or None
    anchor = data.get("anchor") or None
    ctx["anchor"] = tuple(anchor) if anchor else None
    ctx["seam_pins_ll"] = data.get("seam_pins")
    ctx["mesh_edges_ll"] = data.get("mesh_edges") or None
    ctx["crown_drops_ll"] = data.get("crown_drops") or None
    ctx["crown_centerline_ll"] = data.get("crown_centerline") or None
    ctx["pair_caps_ll"] = data.get("pair_caps") or None
    ctx["xsection_spans"] = data.get("xsection_spans") or None
    ctx["terrace_joints_ll"] = data.get("terrace_joints") or None
    ctx["fan_ramp_zones_ll"] = data.get("fan_ramp_zones") or None
    ctx["apron_lattice_edges_ll"] = data.get("apron_lattice_edges") or None
    ctx["airside_no_step_edges_ll"] = (
        data.get("airside_no_step_edges") or None)
    ctx["interior_zones_ll"] = data.get("interior_zones") or None
    ctx["disconnected_rings_ll"] = data.get("disconnected_rings") or None
    ctx["basin_facilities"] = data.get("basin_facilities") or None
    ctx["ruleset"] = data.get("ruleset") or None
    if announce:
        print(f"  (axes sidecar loaded: {len(ctx['taxi_axes_ll'] or [])} axes"
              + (" [exact]" if exact else "")
              + f", {len(ctx['routes_ll'] or [])} routes"
              + (", builder anchor frame" if ctx["anchor"] else "")
              + (f", {len(ctx['seam_pins_ll'])} seam pins"
                 if ctx["seam_pins_ll"] is not None else "")
              + (f", {len(ctx['mesh_edges_ll'])} solver mesh edges"
                 if ctx["mesh_edges_ll"] else "")
              + (f", {len(ctx['crown_drops_ll'])} crown drops"
                 if ctx["crown_drops_ll"] else "")
              + (f", {len(ctx['terrace_joints_ll'])} terrace joints"
                 if ctx["terrace_joints_ll"] else "")
              + (f", {len(ctx['fan_ramp_zones_ll'])} fan-ramp zones"
                 if ctx["fan_ramp_zones_ll"] else "")
              + (f", {len(ctx['interior_zones_ll'])} back-edge zones"
                 if ctx["interior_zones_ll"] else "")
              + (f", {len(ctx['disconnected_rings_ll'])} disconnected "
                 f"groundside ring(s)"
                 if ctx["disconnected_rings_ll"] else "")
              + (f", {len(ctx['basin_facilities'])} declared basin "
                 f"facility(ies)" if ctx["basin_facilities"] else "")
              + f", ruleset={ctx['ruleset']!r}"
              + " — law-true check)")
    return ctx


def sidecar_evidence(osm_path) -> dict:
    """The sidecar's non-law EVIDENCE fields (see ``SIDECAR_EVIDENCE_KEYS``)
    plus ``unknown_keys`` — any key this build of the reader does not know.
    A non-empty ``unknown_keys`` means the emitter grew a field no reader
    consumes: report it, never ignore it."""
    import json as _json
    side = Path(str(osm_path) + ".axes.json")
    if not side.exists():
        return {}
    data = _json.loads(side.read_text())
    known = set(SIDECAR_LAW_KEYS) | set(SIDECAR_EVIDENCE_KEYS)
    out = {}
    for k in SIDECAR_EVIDENCE_KEYS:
        if k not in data:
            continue
        v = data[k]
        if k == "band_excess":
            # ALREADY a summary (counts + the worst ten), and its whole point
            # is to be readable from the artifact — collapsing it to
            # "<N entries>" would re-hide exactly what item 7 surfaced.  The
            # worst-row list is dropped; the numbers are kept.
            out[k] = (None if not isinstance(v, dict) else
                      {kk: vv for kk, vv in v.items() if kk != "worst"})
            continue
        if k == "site_class":
            # ALREADY a flat record of scalars (four signals + verdict),
            # and its whole point is to be readable from the artifact —
            # collapsing it to "<N entries>" would hide exactly the
            # numbers it exists to carry.  Passed through verbatim.
            out[k] = v
            continue
        # SUMMARISE, never embed: the legacy ``axes``/``routes`` arrays are
        # megabytes of geometry, and a report that inlines them is a report
        # nobody reads.  Scalars pass through.
        out[k] = f"<{len(v)} entries>" if isinstance(v, (list, dict)) else v
    out["unknown_keys"] = sorted(set(data) - known)
    out["seam_pin_count"] = len(data.get("seam_pins") or [])
    out["terrace_joint_count"] = len(data.get("terrace_joints") or [])
    out["terrace_certificate_count"] = len(data.get("terrace_certificates")
                                           or [])
    # LAW-KEY COUNTS beside the evidence (the ``seam_pin_count`` /
    # ``terrace_joint_count`` idiom): the KEY is law input, but how big its
    # declared population was is what a reader needs to judge the counts
    # above — ZERO OF ZERO IS NOT A PASS (RULINGS 2026-08-06, binding
    # point 2).  A patch with no basin declares nothing and exempts
    # nothing, and this is where that is visible.
    out["basin_facility_count"] = len(data.get("basin_facilities") or [])
    # THE CENSUS'S OWN BLIND SPOT, counted (spec heca-apron-round2 §2).
    # A nodeless apron interior contributes ZERO census rows however
    # wrong its surface is, so this count is the only thing standing
    # between "no violations" and "no evidence".  Reported at zero.
    out["nodeless_interior_count"] = len(
        data.get("nodeless_interiors") or [])
    out["gap_spine_bridge_count"] = len(data.get("gap_spine_bridges")
                                        or [])
    # A STAND-DOWN IS NOT A DEFECT ROW (spec Amendment 1 §2 register):
    # the census reports the COUNT so a reader can tell a surface that
    # was adjudicated by the bridge-free re-run from one that never had
    # bridges at all.  Reported at zero — zero-of-zero is not a pass.
    out["gap_spine_stand_down_count"] = len(
        data.get("gap_spine_stand_down") or [])
    return out


#: THE LAW-TRUE NUMERIC FRAME.  The knobs ``run_checks_law_true`` binds —
#: named here rather than written as call literals so a report can SERIALISE
#: the frame its numbers were taken in (RULINGS 2026-08-06 "Instrument truth
#: is law", binding point 3: every reported number carries its frame).  Two
#: census JSONs are comparable only if these agree; before they were in the
#: report they were knowable only by reading this function's source at the
#: tree the census ran from.  Values unchanged from the call literals they
#: replace.
LAW_TRUE_KNOBS: Dict[str, float] = {
    "max_grade_pct": 1.5,
    "proximity_m": SHARED_VERTEX_TOL_M,   # the solver's weld tolerance
    "edge_search_m": 5.0,
    "edge_step_m": 0.5,
}


def run_checks_law_true(osm_path, *, family_out: Optional[dict] = None,
                        quiet: bool = True, top_n: int = 0,
                        announce: bool = False, **overrides):
    """``run_checks`` in the patch's OWN law frame — the law-true census.

    Reads every law keyword from the sidecar (``law_context_from_sidecar``)
    and applies the same numeric knobs the suite uses (``LAW_TRUE_KNOBS``:
    proximity = the solver's weld tolerance, 5 m edge search, 0.5 m step).
    This is THE entry point: the CLI, ``tools/harness/census.py`` and any
    test that wants a law-true count must call it rather than assembling
    kwargs.
    """
    ctx = law_context_from_sidecar(osm_path, announce=announce)
    ctx.update(overrides)
    return run_checks(
        Path(osm_path), top_n=top_n, quiet=quiet,
        family_out=family_out, **LAW_TRUE_KNOBS, **ctx)


def row_side(row) -> str:
    """AIRSIDE / GROUNDSIDE / MIXED for one violation or step row.

    Uses THIS module's ``_is_groundside`` — the law's own partition, the one
    that decides whether a designed retaining wall exempts a step.  It is
    NOT ``auto_patch.geom_guard._AIRSIDE_ROLES``, which is a different
    partition built for the geometry guard and disagrees on
    ``service_junction`` and ``building``; censuses that used it were
    measuring a different population than the law was.

    MIXED is reported separately rather than folded into AIRSIDE.  Owner
    law ("airside is king") means a mixed row counts AGAINST airside for
    acceptance — the split is reported so the reader can see the pull, not
    so it can be discounted.

    ROLE-LESS ARTICULATION WAYS SIDE WITH THEIR HOST (lead ruling
    2026-08-07): the side is read through ``effective_role``, so a way with
    no role of its own is never reported as airside-by-default.  The LAW's
    own partition (``_is_groundside``, which GATES the cross-boundary step
    checks) is deliberately untouched: re-siding a report is adjudication,
    re-siding the law's gate would change which rows exist.
    """
    def _gs(w):
        return effective_role(w) in _GROUNDSIDE_ROLES
    a = getattr(row, "way_a", None) or getattr(row, "way_v", None)
    b = getattr(row, "way_b", None) or getattr(row, "way_e", None)
    if a is None:
        return "unknown"
    if b is None:
        return "groundside" if _gs(a) else "airside"
    ga, gb = _gs(a), _gs(b)
    if ga and gb:
        return "groundside"
    if ga or gb:
        return "mixed"
    return "airside"


def row_roles(row) -> Tuple[str, str]:
    """The (role_a, role_b) pair of a row, '?' where a way is absent.

    Read through ``effective_role``: a ROLE-LESS feature way reports its
    HOST's role (lead ruling 2026-08-07), so ``?|?`` in a class table means
    "no host could be resolved", not "the emitter shipped a bare way"."""
    def _r(w):
        return effective_role(w) or "?"
    a = getattr(row, "way_a", None) or getattr(row, "way_v", None)
    b = getattr(row, "way_b", None) or getattr(row, "way_e", None)
    return (_r(a), _r(b))


def row_magnitude(row) -> float:
    """The row's own severity in metres: |de| for a grade violation, the
    step height for an edge step.  One accessor so worst-row tables from
    different lanes are the same number."""
    for attr in ("de_m", "step_m"):
        v = getattr(row, attr, None)
        if v is not None:
            return abs(float(v))
    return 0.0


def run_checks(
    osm_path: Path,
    max_grade_pct: float = 1.5,
    proximity_m: float = SHARED_VERTEX_TOL_M,
    edge_search_m: float = 5.0,
    edge_step_m: float = 0.5,
    top_n: int = 10,
    taxi_axes_ll: Optional[list] = None,
    routes_ll: Optional[list] = None,
    quiet: bool = False,
    anchor: Optional[Tuple[float, float]] = None,
    seam_pins_ll: Optional[list] = None,
    mesh_edges_ll: Optional[list] = None,
    crown_drops_ll: Optional[list] = None,
    crown_centerline_ll: Optional[list] = None,
    pair_caps_ll: Optional[list] = None,
    terrace_joints_ll: Optional[list] = None,
    fan_ramp_zones_ll: Optional[list] = None,
    apron_lattice_edges_ll: Optional[list] = None,
    airside_no_step_edges_ll: Optional[list] = None,
    interior_zones_ll: Optional[list] = None,
    disconnected_rings_ll: Optional[list] = None,
    basin_facilities: Optional[list] = None,
    ruleset: Optional[str] = None,
    xsection_spans: Optional[list] = None,
    family_out: Optional[dict] = None,
) -> Tuple[List[Violation], List[Violation], List[EdgeStep]]:
    """``taxi_axes_ll`` (the builder's APT.DAT taxi centerlines as
    ``[(latlon_points, cL, cT), …]``) supplies the within-shape grade graph's
    CENTERLINES (spine membership + per-letter cap), sourced from
    ``layout.apt_taxi_centerlines`` and passed as lat/lon so the audit's
    mean-centred meter frame matches; ``routes_ll`` supplies the chained ROUTES
    for the anisotropic spine-arc decomposition (``grade_graph``).  Re-deriving
    centerlines from the OSM would diverge from the apt.dat geometry the builder
    actually used — do not.

    ``seam_pins_ll`` (sidecar ``seam_pins``, ``[[lat, lon], …]``): the exact
    tile-seam DEM-pin vertices the solver graded to.  When given, ONLY nodes
    coincident with a pin are seam-flagged — pin↔pin pairs skip, pin↔free
    pairs check at the shape's body cap — matching the solver's law reading
    (user 2026-07-04, "treat the seam like a runway edge or building").
    Without it the legacy 400 m blanket zone applies (old patches).

    ``mesh_edges_ll`` (sidecar ``mesh_edges``, ``[[[lat, lon], [lat, lon]],
    …]``): the SOLVER's junction triangle-mesh edges, consumed 1:1 for the
    JUNCTION MESH RULE so emit-time ring repairs can't make this reader's
    Delaunay differ from the one the solver graded to.  Without it the mesh
    is re-triangulated from the emitted ring (old patches — stricter, and
    cm-noisy where emit repaired a junction ring).
    """
    _CROWN_UNKNOWN_PAIRS.clear()
    # REGION RULESET (phase B).  ``ruleset`` is the SIDECAR's key — the
    # authority the build actually ran under.  The census NEVER re-derives
    # it from the ICAO identifier: production emits what it did, and the
    # validator judges the same law (the two-instruments discipline
    # applied to authority).  A patch predating the split has no key; the
    # default then applies and is announced.
    _active = _set_active_ruleset(ruleset)

    # PER-FAMILY CENSUS (see ``LAW_FAMILIES``).  When ``family_out`` is a
    # dict, every family records its OWN rows here as it is produced — so a
    # census never has to re-derive the split by monkeypatching private
    # functions or by slicing the printed report, which is how per-lane
    # wrappers lost families.  ``family_out is None`` (the default) is a
    # no-op: the returned lists are byte-identical either way.
    def _fam(key: str, rows):
        if family_out is not None:
            family_out[key] = list(rows)
        return rows

    if family_out is not None:
        # BOTH, never one: ``_ruleset_declared`` is what the patch's sidecar
        # says the BUILD ran under (None ⇒ the patch predates the FAA/ICAO
        # split), ``_ruleset_active`` is what this run judged in.  Reporting
        # only the active key would silently present the default as a
        # declaration — the same authority-frame error the sidecar exists
        # to prevent.
        family_out["_ruleset_declared"] = ruleset
        family_out["_ruleset_active"] = _active
    if not quiet:
        # NUMBERS AND FRAMES, never a cause.  The old line said the patch
        # "predates the FAA/ICAO split" and told the reader to rebuild —
        # a cause this code never verifies (an emitter bug or a truncated
        # write produce the same absent key) plus an instruction.  What is
        # verified: what the sidecar declared, what this run judged in,
        # and where the active value came from.
        if ruleset:
            print(f"  (ruleset declared={ruleset!r} active={_active!r} "
                  f"source=SIDECAR)")
        else:
            print(f"  (ruleset declared=None active={_active!r} "
                  f"source=DEFAULT — no 'ruleset' key in the sidecar)")

    open_features: Dict[str, List[Way]] = {}
    nodes, ways = _parse_osm(osm_path, feature_out=open_features)
    # ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead ruling 2026-08-07),
    # resolved ONCE, before any check runs — so the ONE cap resolver and
    # the ONE side partition both see the host role rather than falling
    # through to the caller's default cap and to airside.
    _feature_hosts = resolve_feature_hosts(
        ways, [w for v in open_features.values() for w in v])
    if _feature_hosts and not quiet:
        _dups = sum(1 for h in _feature_hosts.values() if h["duplicate"])
        print(f"  role-less feature ways: {len(_feature_hosts)} sided with "
              f"their host shape ({_dups} whose host COVERS their geometry "
              f"— rows adjudicated 'role_less_host_duplicate')")
    if family_out is not None:
        family_out["_feature_hosts"] = _feature_hosts
    ll_to_m = _ll_to_m_factory(nodes, anchor=anchor)
    vertices, edges = _build_vertex_edge_tables(nodes, ways, ll_to_m)
    max_grade = max_grade_pct / 100.0
    if seam_pins_ll is not None:
        seam_nids = _seam_nids_from_pins(nodes, seam_pins_ll)
    else:
        seam_nids = _seam_nids(nodes)

    # Convert apt.dat centerlines (lat/lon) into the audit's meter frame.
    taxi_axes = _axes_to_m(taxi_axes_ll, ll_to_m)

    def _pv(*a, **k):
        if not quiet:
            _print_violations(*a, **k)

    def _ps(*a, **k):
        if not quiet:
            _print_steps(*a, **k)

    if not quiet:
        print(f"=== Grade validation: {osm_path} ===")
        n_with_elev = sum(1 for v in vertices if v.elev is not None)
        print(f"  ways: {len(ways)} | vertices: {len(vertices)} "
              f"({n_with_elev} with elevation) | edges: {len(edges)} "
              f"| seam vertices: {len(seam_nids)}")

    # Sidecar mesh edges arrive as lat/lon; convert to this audit's meter
    # frame (both endpoints of a shared solver vertex serialize to the same
    # rounded lat/lon, so vertex identity survives the conversion).
    mesh_edges_m = None
    if mesh_edges_ll:
        mesh_edges_m = [(ll_to_m(*edge[0]), ll_to_m(*edge[1]))
                        for edge in mesh_edges_ll]

    # SPINE CROWN drop field (sidecar ``crown_drops``, part 30): the
    # within-shape law re-centres every pair's budget on the designed
    # crown target (grade_law.crown_pair_offset) — the SAME field the
    # solver built to.  Absent ⇒ offsets 0 (uncrowned/old patches).
    crown_by_nid = _crown_drops_by_nid(nodes, crown_drops_ll or [])
    if crown_by_nid and not quiet:
        print(f"  crown drop field: {len(crown_by_nid)} node(s) crowned")
    # CROWN CENTERLINE nids (Phase 0 hotfix): runway ridge vertices the
    # interior cross-edge crown inserted — skipped from the runway within-shape
    # all-pairs plane law (governed by the spine profile check instead).
    crown_centerline_nids = _crown_centerline_nids(
        nodes, crown_centerline_ll or [])
    if crown_centerline_nids and not quiet:
        print(f"  crown centerline: {len(crown_centerline_nids)} ridge "
              f"node(s) exempt from the runway plane all-pairs check")

    # APRON TERRACE LAW (owner 2026-08-04, spec §5): the DECLARED joints,
    # in this audit's metre frame.  Empty for every patch built without
    # the law — every check below is then byte-identical to before.
    terrace_joints_m = _terrace_joints_to_m(terrace_joints_ll, ll_to_m)
    if terrace_joints_m and not quiet:
        print(f"  apron terraces: {len(terrace_joints_m)} declared "
              f"joint(s) (within-pairs crossing one are judged by the "
              f"step law)")

    # THE DECLARED BASIN FACILITIES (spec ``docs/specs/
    # tunnel-trench-law-and-basin-floor-spec.md`` §1): the floor→rim drop
    # each open pit declares, which its own trench contacts are priced
    # against.  Empty for every patch built without the basin law, so
    # every count below is byte-identical on one.
    basin_declared = _basin_facilities_declared(basin_facilities)
    if basin_declared and not quiet:
        print(f"  basin facilities: {len(basin_declared)} declared "
              f"(floor→rim drops "
              f"{', '.join(f'{d:.2f}' for _f, d, *_r in basin_declared[:6])}"
              f"{' …' if len(basin_declared) > 6 else ''} m; trench "
              f"contacts price against their OWN declared drop)")

    # THE FAN-RAMP LAW (owner RULINGS 21f0980), in this audit's metre
    # frame.  Empty for every patch built without the law.
    fan_ramp_zones_m = _fan_ramp_zones_to_m(fan_ramp_zones_ll, ll_to_m)
    if fan_ramp_zones_m and not quiet:
        _caps = sorted({row[1] for row in fan_ramp_zones_m})
        print(f"  fan ramps: {len(fan_ramp_zones_m)} declared zone(s) at "
              f"{', '.join(f'{c * 100:.0f} %' for c in _caps)} "
              f"(within-apron pairs inside one are judged at the zone cap; "
              f"every movement surface keeps the strict apron cap)")

    # THE DISCONNECTED RINGS (owner RULINGS 2026-08-06, "ONE graph"), in
    # this audit's metre frame.  Empty for every patch built without the
    # law, so every count below is byte-identical to before on one.
    disconnected_rings_m = _disconnected_rings_to_m(disconnected_rings_ll,
                                                    ll_to_m)
    if disconnected_rings_m and not quiet:
        print(f"  disconnected groundside: {len(disconnected_rings_m)} "
              f"ring(s) the route graph does not reach (NOT SOLVED by "
              f"ruling; rows inside one are reported and adjudicated "
              f"OUT OF SCOPE, never dropped)")

    # THE BACK-EDGE ZONES (owner ruling RULINGS 2026-08-24), converted to
    # this reader's metre frame.  A patch predating the rescope has no key,
    # reads ``None``, and every apron pair inside the 60 m body gate is
    # then STRICT — the conservative direction, never a looser one.
    interior_zones_m = [
        [ll_to_m(float(la), float(lo)) for (la, lo) in ring]
        for ring in (interior_zones_ll or []) if len(ring) >= 3]
    # THE ROAD CROSS-SECTION (RULINGS 2026-08-25g) rides the SAME pair
    # walk: one enumeration, split by the law's own classifier into the
    # along-road rows (``within_shape``) and the across-road rows.
    _road_xsec_rows: List[Violation] = []
    within = _fam("within_shape", _check_within_shape(
        ways, nodes, ll_to_m, max_grade, seam_nids=seam_nids,
        taxi_axes=taxi_axes, routes_ll=routes_ll,
        mesh_edges_m=mesh_edges_m, crown_by_nid=crown_by_nid,
        crown_centerline_nids=crown_centerline_nids,
        pair_caps_ll=pair_caps_ll, terrace_joints_m=terrace_joints_m,
        fan_ramp_zones_m=fan_ramp_zones_m,
        interior_zones_m=interior_zones_m,
        transverse_road_out=_road_xsec_rows))
    # THE BREAK-REGION SPLIT IS DELETED (spec ``docs/specs/kill-half-
    # spec.md`` §2, 2026-08-04).  Pairs touching a solver-declared broken
    # node used to be moved out of the actionable within-shape count into
    # a BREAK-REGION section.  Owner law (docs/RULINGS.md): quarantine is
    # unauthorized and "all counts are full-census, never quarantine-
    # excluded".  Every pair is now counted where it falls; the law's own
    # exemptions still adjudicate what is a violation.
    _pv(f"WITHIN-SHAPE vertex-pair grade > {max_grade_pct}%",
        within, top_n)
    if _CROWN_UNKNOWN_PAIRS and not quiet:
        _n_unk = sum(_CROWN_UNKNOWN_PAIRS.values())
        _by = ", ".join(f"{r} {n}" for r, n in
                        sorted(_CROWN_UNKNOWN_PAIRS.items(),
                               key=lambda kv: (-kv[1], kv[0])))
        print(f"  crown field UNPRICEABLE pairs: {_n_unk} ({_by}) — one "
              f"endpoint carries a declared NONZERO crown drop and the other "
              f"is absent from the sidecar 'crown_drops' field, so the "
              f"designed step is UNKNOWN; each is judged at the most "
              f"favourable step the field is compatible with (a pair over "
              f"cap under EVERY compatible declaration still reports in "
              f"full). Reported, never adjudicated: defaulting the absent "
              f"endpoint to the RIDGE minted 3 rows on the 2026-08-16 HECA "
              f"arm whose raw grades were all under cap. A rising count is a "
              f"DECLARATION gap (crown.extend_field_to_new_ring_nodes not "
              f"reaching a post-solve insert), not a surface defect")

    # ── THE ROAD CROSS-SECTION FAMILY (RULINGS 2026-08-25g) ───────────
    road_xsec = _fam("road_cross_section", _road_xsec_rows)
    _pv(f"ROAD CROSS-SECTION (lateral) grade > "
        f"{SERVICE_ROAD_MAX_TRANSVERSE * 100:g}%", road_xsec, top_n)
    within = within + road_xsec

    plane = _fam("plane_gradient", _check_plane_gradient(
        ways, nodes, ll_to_m, max_grade, seam_nids=seam_nids,
        crown_by_nid=crown_by_nid))
    # The triangle-plane split went with it (§2): an unresolved triangle
    # is REPORTED (``solve.triangle_plane_disposition``) and its plane
    # violation stays visible here.
    _pv(f"PLANE GRADIENT (triangle surface) > {max_grade_pct}%",
        plane, top_n)
    within = within + plane

    # SPINE-PROFILE VERTICAL CURVE (task 3, user 2026-07-04): the same
    # grade-change rate the solver's fairing pass enforces
    # (``config.TAXIWAY_MAX_GRADE_CHANGE_PER_M``), validated on the
    # emitted profile along each sidecar axis.  Reporter-only (not part
    # of the returned violation lists yet — counts calibrate first).
    #
    # THE LABEL IS LOAD-BEARING (RULINGS 2026-08-06, binding point 1).
    # This count is law-SHAPED but is not a law family: it is not in
    # ``LAW_FAMILIES``, never enters ``family_out``, never reaches
    # ``adjudication``, and is printed only when ``not quiet`` — so the
    # harness census (quiet=True) never sees it and no acceptance gate
    # can act on it.  Printed unlabelled it read exactly like a defect
    # count.  Its known-answer twin is
    # ``tests/test_census_instrument.py::TestSpineCurvatureIsReporterOnly``.
    if taxi_axes and not quiet:
        n_kinks, worst_kink = _check_spine_curvature(
            ways, nodes, ll_to_m, taxi_axes)
        print(f"\n[reporter-only, not a law family, not censused] "
              f"SPINE PROFILE grade-change (vertical curve, "
              f"noise-aware): {n_kinks} kink(s)"
              + (f", worst excess {worst_kink:.4f}/m" if n_kinks else ""))

    # ROUTE-BAND: NOT checked on the OSM patch.  route_field (a parallel
    # per-vertex band on a SEPARATE centerline graph) was retired; the
    # route-band rule is now confirmed in-memory on the ONE graph G by
    # grade_graph_validate.route_band_violations (see
    # docs/grade_law_consolidation_handover.md).  Reconstructing G from the
    # shipped OSM to confirm it here is the remaining "purist OSM-path" follow-up.

    skirt_edges = _fam("runway_end_skirt",
                       _check_runway_end_skirt_edges(ways, nodes, ll_to_m))
    _pv("RUNWAY-END SKIRT edge grade > law max down-grade",
        skirt_edges, top_n)
    within = within + skirt_edges

    # APRON TERRACE LAW — the BINDING CONSTRAINT's twin (spec §5b/c/d).
    # A hit on either of these means the emitter's structural guarantee
    # was broken: the round's STOP rule, not a tuning signal.
    joint_route = _fam("terrace_joint_route",
                       _check_terrace_joint_crosses_route(
                           terrace_joints_m, routes_ll, taxi_axes))
    _pv("APRON TERRACE JOINT crossing a taxi ROUTE (owner 2026-08-04 "
        "binding constraint — a joint may NEVER interrupt a spine "
        "aircraft travel on)", joint_route, top_n)
    within = within + joint_route

    joint_strip = _fam("terrace_joint_strip",
                       _check_terrace_joint_in_runway_strip(
                           terrace_joints_m, ways, nodes, ll_to_m))
    _pv("APRON TERRACE JOINT inside a RUNWAY STRIP footprint (owner "
        "2026-08-01 — walls at runway edges are NEVER lawful)",
        joint_strip, top_n)
    within = within + joint_strip

    joint_actual = _fam("terrace_actual_step",
                        _check_terrace_actual_step(
                            terrace_joints_m, ways, nodes, ll_to_m,
                            max_grade))
    _pv("APRON TERRACE ACTUAL step past its DECLARED step (recomputed "
        "from the patch: nearest straddling vertex pairs + the emitted "
        "joint face — never the sidecar's own report fields)",
        joint_actual, top_n)
    within = within + joint_actual

    basin_declaration = _fam(
        "basin_floor_declaration",
        _check_basin_floor_declaration(basin_declared))
    _pv(f"BASIN FACILITY floor DISAGREES with its own body depth (the "
        f"deepest-solid witness against the deck-face population, "
        f"> {_BASIN_FLOOR_DISAGREEMENT_M:.1f} m — the declared floor→rim "
        f"drop this facility's own trench contacts are priced against is "
        f"not evidenced by its geometry)",
        basin_declaration, top_n)
    within = within + basin_declaration

    adjacent_edges = _fam("adjacent_ground_tear",
                          _check_adjacent_ground_edges(ways, nodes, ll_to_m))
    _pv("ADJACENT-GROUND graded-strip TEAR (sub-metre near-vertical edge)",
        adjacent_edges, top_n)
    within = within + adjacent_edges

    strip_seam_tears = _fam("strip_seam_tear",
                            _check_strip_seam_tears(vertices, ways))
    _pv(f"ADJACENT-GROUND strip SEAM tear (cross-shape step, "
        f"> {STRIP_SEAM_TEAR_MIN_STEP_M:.1f}m at "
        f"> {STRIP_SEAM_TEAR_MIN_GRADE * 100:.0f}% within "
        f"{STRIP_SEAM_TEAR_RADIUS_M:.1f}m; "
        f"> {STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M:.0f}m at the OPEN "
        f"graded→DEM boundary — PROVISIONAL, owner 2026-08-01)",
        strip_seam_tears, top_n)
    within = within + strip_seam_tears

    _tr_stations: list = []
    transverse, n_tr_st, n_tr_rows, n_tr_shapes = _check_transverse_grade(
        ways, nodes, ll_to_m, taxi_axes,
        terrace_joints_m=terrace_joints_m, stations_out=_tr_stations)
    _fam("transverse", transverse)
    _pv("TRANSVERSE (cross-corridor) grade > the role/letter transverse "
        "cap (ICAO Annex 14 §3.9.11)",
        transverse, top_n)
    if n_tr_rows and not quiet:
        print(f"  ({n_tr_st} transect station(s); {n_tr_rows} censused "
              f"crossing(s) over {n_tr_shapes} shape(s) — coverage is "
              f"pavement a taxi centreline crosses, stations "
              f"{_TRANSVERSE_STEP_M:g} m apart are correlated)")
    # ── THE LOCKSTEP LINE (spec section 12 + AMENDMENT A1 section 8c) ──
    # priced HERE, on the emitted ring; bound THERE, on the ring the final
    # projection saw.  ``broken_by_emit`` is the count the amendment
    # exists to take: bound spans the emit-stage repairs moved after the
    # binding.  Printed whenever the patch carries bound spans, and
    # printed as ZERO-BOUND when it does not, because "the solve bound
    # nothing here" is exactly the fact a reader must not have to infer.
    if _tr_stations:
        # PRINTED EVEN UNDER ``quiet`` — the census runs quiet and this is
        # the round's measurement, not chatter (the ``[bake] UNVERIFIED``
        # precedent: a number a report can omit is a number nobody reads).
        _p, _b, _u, _brk, _bw = transverse_bind_report(
            _tr_stations, xsection_spans)
        print(f"  [transverse-bind] priced {_p} / bound {_b} / unbound "
              f"{_u} / broken_by_emit {_brk}"
              + (f" (worst {_bw:.3f} m)" if _brk else "")
              + ("" if xsection_spans else
                 "  — this patch carries NO bound spans (built before the "
                 "law, or O4_TRANSVERSE_HYPER=0)"))
    within = within + transverse

    spine_dams, n_spine_checked, n_spine_short = (
        _check_drainage_spine_below_pavement(
            open_features.get("gap_drainage_spine", []),
            ways, nodes, ll_to_m))
    _fam("drainage_spine", spine_dams)
    _pv("DRAINAGE SPINE at or above its LOWER adjacent pavement (owner "
        "field report 2026-08-02 — cap 0)", spine_dams, top_n)
    if n_spine_checked and not quiet:
        print(f"  ({n_spine_checked} spine vertex/vertices checked; "
              f"{n_spine_short} below the lower edge by less than the "
              f"PROVISIONAL {_DRAINAGE_SPINE_MIN_FALL_M:.2f} m fall — "
              f"reported, not failed)")
    within = within + spine_dams

    lattice_rows, n_lat_checked, n_lat_unmatched = (
        _check_apron_lattice_membrane(
            apron_lattice_edges_ll,
            # ONE MEMBRANE, ONE JOIN POPULATION (round 3 §1/§3): the
            # sidecar's ``apron_lattice_edges`` now carries the SPINE
            # STATION pairs too, and a station's value lives on an
            # ``apron_spine_station`` way — a lattice-only population
            # would fail to match those endpoints and report every one
            # of them as a LOST measurement.
            list(open_features.get("apron_lattice", []))
            + list(open_features.get("apron_spine_station", [])),
            ways, nodes, ll_to_m))
    _fam("apron_lattice_membrane", lattice_rows)
    _pv("APRON LATTICE MEMBRANE pair over the budget the SOLVE priced it "
        "at (spec heca-apron-round2 Amendment 1 section 1b)",
        lattice_rows, top_n)
    if not quiet and (n_lat_checked or n_lat_unmatched):
        print(f"  ({n_lat_checked} published lattice edge(s) checked"
              + (f"; {n_lat_unmatched} SKIPPED — an endpoint is not an "
                 f"emitted node, so the pair is a LOST MEASUREMENT, not "
                 f"a pass" if n_lat_unmatched else "") + ")")
    within = within + lattice_rows

    # ── THE AIRSIDE NO-STEP LAW (owner ruling RULINGS 2026-08-27) ────
    no_step_rows, n_ns_checked, n_ns_unmatched = _check_airside_no_step(
        airside_no_step_edges_ll,
        # The membrane's own emitted breaklines carry the values of every
        # interior endpoint; a ring-only population would report each of
        # them as a LOST measurement (the round-3 lattice/station
        # precedent, same reason).
        [w for cls in _NO_STEP_POLYLINE_FEATURES
         for w in open_features.get(cls, [])],
        ways, nodes, ll_to_m)
    no_step_rate_rows, n_ns_st, n_ns_ways = _check_airside_no_step_rate(
        ways,
        [w for cls in _NO_STEP_POLYLINE_FEATURES
         for w in open_features.get(cls, [])],
        nodes, ll_to_m)
    no_step_all = no_step_rows + no_step_rate_rows
    _fam("airside_no_step", no_step_all)
    _pv("AIRSIDE NO-STEP: a pair over cap x DIRECT distance, or a "
        "membrane station whose grade CHANGE outruns the aerodrome's "
        "vertical-curve rate (owner ruling RULINGS 2026-08-27 — no step "
        "in airside pavement is lawful; relief spread smoothly is)",
        no_step_all, top_n)
    if not quiet and (n_ns_checked or n_ns_unmatched or n_ns_st):
        print(f"  ({len(no_step_rows)} direct-distance row(s) over "
              f"{n_ns_checked} published edge(s)"
              + (f"; {n_ns_unmatched} SKIPPED — an endpoint is not an "
                 f"emitted node, so the pair is a LOST MEASUREMENT, not "
                 f"a pass" if n_ns_unmatched else "")
              + f"; {len(no_step_rate_rows)} rate row(s) over {n_ns_st} "
                f"membrane station(s) on {n_ns_ways} polyline(s) — the "
                f"rate reader's blind spot is the strip family's own, "
                f"derived per row at its OWN spacing)")
    within = within + no_step_all

    lateral, n_lat_stations, n_lat_shapes = _check_lateral_contiguity(
        ways, nodes, ll_to_m)
    _fam("lateral_contiguity", lateral)
    _pv("LATERAL CONTIGUITY: road graded looser than the STRICTEST class in "
        "its laterally-contiguous cross-section (owner FINAL 2026-08-02)",
        lateral, top_n)
    if n_lat_stations and not quiet:
        print(f"  ({n_lat_stations} road station(s) censused; "
              f"{n_lat_shapes} road shape(s) flagged — stations "
              f"{_LATERAL_STEP_M:g} m apart on one shape are correlated)")
    within = within + lateral

    strip_long, n_sl_pairs, n_sl_ways = _check_strip_longitudinal_grade(
        ways, nodes, ll_to_m)
    _fam("strip_longitudinal", strip_long)
    _pv("STRIP ABEAM-LONGITUDINAL grade > the by-code strip cap (ICAO "
        "Annex 14 §3.4.13 / FAA AC 150/5300-13B §3.16.5 item 1 — "
        "standing law)",
        strip_long, top_n)
    if n_sl_pairs and not quiet:
        print(f"  ({n_sl_pairs} along-axis strip pair(s) censused over "
              f"{n_sl_ways} band(s))")
    within = within + strip_long

    # ── §A3(b) — the strip's CURVATURE law ───────────────────────────
    strip_arc, n_sa_st, n_sa_ways = _check_strip_arc_rate(
        ways, nodes, ll_to_m)
    _fam("strip_arc", strip_arc)
    _pv("STRIP LONGITUDINAL grade-CHANGE rate > the strip arc law "
        "(FAA AC §3.16.5 item 5 ±2%/30.5 m; ICAO §3.4.14 is qualitative "
        "— PROVISIONAL operationalization, owner question 2)",
        strip_arc, top_n)
    if n_sa_st and not quiet:
        print(f"  ({n_sa_st} strip station(s) censused over {n_sa_ways} "
              f"band(s); rate-reader blind spot is derived per row at its "
              f"OWN station spacing — q·(1/dp + 1/dn), see "
              f"_rate_reader_blind_spot — and rows inside it are "
              f"PASS-with-residual)")
    within = within + strip_arc

    # ── §A1 — the END-corridor TRANSVERSE law ────────────────────────
    resa_tr, n_rt_pairs, n_rt_ways = _check_resa_transverse_grade(
        ways, nodes, ll_to_m)
    _fam("resa_transverse", resa_tr)
    _pv("RESA / END-CORRIDOR TRANSVERSE grade > the per-authority cap "
        "(FAA Table 3-6 S-3 inside 61 m, Fig 3-35 ±5% beyond; ICAO "
        "Annex 14 §3.5.11 ±5%)",
        resa_tr, top_n)
    if n_rt_pairs and not quiet:
        print(f"  ({n_rt_pairs} across-corridor pair(s) censused over "
              f"{n_rt_ways} band(s))")
    within = within + resa_tr

    # ── §A4 — the RADIO ALTIMETER OPERATING AREA ─────────────────────
    raoa, n_ra_st, n_ra_ways = _check_raoa_rate(ways, nodes, ll_to_m)
    _fam("raoa", raoa)
    _pv("RAOA grade-change rate > 2%/30 m (ICAO Annex 14 §3.8.4; no FAA "
        "equivalent exists — a no-op under the FAA ruleset)",
        raoa, top_n)
    if n_ra_st and not quiet:
        print(f"  ({n_ra_st} pre-threshold station(s) censused over "
              f"{n_ra_ways} band(s))")
    within = within + raoa

    # ── §B3 — the DRAINAGE MINIMUM ───────────────────────────────────
    drain_min, n_dm_pairs, n_dm_ways = _check_drainage_minimum(
        ways, nodes, ll_to_m)
    _fam("drainage_minimum", drain_min)
    _pv("SURFACE FLATTER than its drainage minimum (FAA AC §5.9.1.1 "
        "0.5% apron — ICAO states no apron minimum, so this family is a "
        "no-op there; the groundside/road half RETIRED, owner 2026-08-14)",
        drain_min, top_n)
    if n_dm_pairs and not quiet:
        print(f"  ({n_dm_pairs} drainage pair(s) censused over "
              f"{n_dm_ways} surface(s))")
    within = within + drain_min

    # ── THE RUNWAY CROWN — the drainage law the 2026-08-14 scope KEPT ──
    crown_short, n_cr_nodes, n_cr_no_ridge, n_cr_undeclared = (
        _check_runway_crown(ways, nodes, ll_to_m, crown_by_nid,
                            open_features.get("crown_spine", [])))
    _fam("runway_crown", crown_short)
    _pv("RUNWAY CROWN below its DECLARED drop (ICAO Annex 14 §3.1.19 / "
        "FAA Table 3-6 S-1 1% transverse minimum, BOUND on runways by "
        "owner d48bc0a; the per-node declared field is the sidecar's "
        "crown_drops — rows at a runway/taxiway INTERSECTION carry the "
        "cited exception and are adjudicated out of scope)",
        crown_short, top_n)
    if (n_cr_nodes or n_cr_no_ridge or n_cr_undeclared) and not quiet:
        print(f"  ({n_cr_nodes} crowned runway node(s) censused against "
              f"the ridge breakline"
              + (f"; {n_cr_undeclared} runway shape(s) declared NO crown "
                 f"and were judged against the ruleset floor"
                 if n_cr_undeclared else "")
              + (f"; {n_cr_no_ridge} node(s) had NO crown-spine ridge in "
                 f"the patch at all" if n_cr_no_ridge else "")
              + ")")
    within = within + crown_short

    wall_in_strip = _fam(
        "wall_in_runway_strip",
        _check_no_wall_in_runway_strip(ways, nodes, ll_to_m))
    _pv("RETAINING WALL inside a RUNWAY STRIP footprint (owner ruling "
        "2026-08-01: walls are never lawful at a runway edge — cap 0)",
        wall_in_strip, top_n)
    within = within + wall_in_strip

    stacked = _fam("stacked_nodes", _check_stacked_nodes(vertices, ways))
    _pv("STACKED NODES (distinct node ids at one coordinate, values "
        "disagree — owner invariant 2026-07-19, cap 0)",
        stacked, top_n)
    within = within + stacked

    cross = _fam("cross_shape", _check_cross_shape_proximity(
        vertices, ways, proximity_m, max_grade))
    _pv(f"CROSS-SHAPE proximity (≤ {proximity_m}m) "
        f"grade > {max_grade_pct}%",
        cross, top_n)

    # NEAR-MISS BUILDING FRONTAGE — the solve's frontage law edges, judged on
    # the emitted patch.  A separate family from ``cross_shape`` because it is
    # a different law with a different scope: cross-shape proximity is capped
    # at SHARED_VERTEX_TOL_M (0.5 m) and reads 0 everywhere, while this binds
    # out to BUILDING_FRONTAGE_NEAR_MISS_M against the pad's own node.
    near_miss = _fam("frontage_near_miss",
                     _check_frontage_near_miss(ways, nodes, ll_to_m))
    _pv(f"NEAR-MISS BUILDING FRONTAGE (soft pavement within "
        f"{_BUILDING_FRONTAGE_NEAR_MISS_M:g} m of a pad, across the sliver, "
        f"vs the pad's own node at the apron cap)",
        near_miss, top_n)
    cross = cross + near_miss

    steps = _fam("vertex_to_edge_step", _check_vertex_to_edge_step(
        vertices, edges, ways, edge_search_m, edge_step_m,
        terrace_joints_m=terrace_joints_m,
        basin_declared=basin_declared))
    mid_steps = _fam("mid_edge_step", _check_edge_midpoint_step(
        edges, ways, edge_search_m, edge_step_m,
        terrace_joints_m=terrace_joints_m,
        basin_declared=basin_declared))
    # The step split went with the rest of the break machinery (§2): a
    # step near a solver-declared break node used to be dropped from both
    # step checks (at a 2.0 m tolerance, wider than the vertex-pair
    # split's weld tolerance).  Full census now.
    _ps(f"VERTEX-TO-EDGE step (within {edge_search_m}m of "
        f"another shape)",
        steps, top_n, edge_step_m)

    _ps(f"MID-EDGE step (sample along each edge, compare to "
        f"nearest other-shape edge)",
        mid_steps, top_n, edge_step_m)

    # Attach a geographic location (lat, lon) to each finding so callers
    # can point a user at the spot in their apt.dat / DSF.  nodes maps
    # nid -> (lat, lon); use the centroid of the offending way's ring.
    def _way_latlon(way):
        lls = [nodes[n] for n in way.nids if n in nodes]
        if not lls:
            return (None, None)
        return (sum(p[0] for p in lls) / len(lls),
                sum(p[1] for p in lls) / len(lls))

    for v in within + cross:
        # A row that already KNOWS where it is keeps its own site: the
        # within-shape check reports its pair MIDPOINT (R19-5).  The ring
        # centroid stays the fallback for every row whose location is a
        # whole shape.
        if v.lat is None:
            v.lat, v.lon = _way_latlon(v.way_a)
    for s in steps + mid_steps:
        s.lat, s.lon = _way_latlon(s.way_v)

    # ── OUT OF SCOPE: the TRULY DISCONNECTED groundside rings ──────────
    # RULINGS 2026-08-06 ("ONE graph"), binding point 3: geometry with no
    # route, frontage or weld coupling to the solved network is NOT
    # SOLVED — it stays at its DEM seed by construction and mints
    # nothing.  The rings are the SOLVE's own answer, carried in the
    # ``disconnected_rings`` sidecar key; nothing is re-derived here, so
    # the coupling law and the census cannot drift apart (the second
    # predicate is exactly what the frontage-gap lesson cost).
    #
    # MARKED, NEVER DROPPED.  The row stays in every family count and in
    # the worst-row lists; ``adjudication`` carries it under its own
    # heading, the same treatment the version-deferred family gets.
    if disconnected_rings_m:
        _mark_disconnected(within + cross, steps + mid_steps,
                           disconnected_rings_m)

    # ── OUT OF SCOPE: ONE GEOMETRY, ONE ROW SET ───────────────────────
    # Lead ruling 2026-08-07 ("Role-less feature ways side with their
    # host"): where an articulation way's geometry duplicates a host way's,
    # the rows belong to the HOST ONLY.  The host's own way carries the
    # same vertices and is judged by the same law at the same cap, so a row
    # minted on the articulation way alone is the SECOND reading of one
    # geometry.  MARKED, NEVER DROPPED — it stays in its family count and
    # in every worst-row list, and ``adjudication`` carries it under its own
    # heading, exactly as the disconnected rings above.
    if _feature_hosts:
        for _r in within + cross + steps + mid_steps:
            if _r.out_of_scope is None and role_less_host_duplicate(_r):
                _r.out_of_scope = "role_less_host_duplicate"

    return within, cross, steps + mid_steps


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("osm", type=Path,
                   help="Path to an X-Plane patch.osm file.")
    p.add_argument("--max-grade", type=float, default=1.5,
                   help="Max permitted grade in %% (default 1.5)")
    p.add_argument("--proximity-m", type=float, default=SHARED_VERTEX_TOL_M,
                   help="Cross-shape proximity radius (defaults to the solver's "
                        "SHARED_VERTEX_TOL_M weld tolerance — vertices farther "
                        "apart are independent solver nodes, not a grade pair)")
    p.add_argument("--edge-search-m", type=float, default=5.0,
                   help="Vertex-to-edge search radius (default 5.0 m)")
    p.add_argument("--edge-step-m", type=float, default=0.5,
                   help="Max permitted vertex-to-edge step in m "
                        "(default 0.5)")
    p.add_argument("--top-n", type=int, default=10,
                   help="Show this many worst violations per check")
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 if any check has any violation.")
    args = p.parse_args(argv)
    # AXES SIDECAR (2026-07-02): ``layout.to_osm`` writes the taxi axes +
    # chained routes to ``<patch>.axes.json`` so the STANDALONE check can
    # apply the SAME within-shape law the solver and the suite use (spine
    # membership, per-letter caps, anisotropic Δs∥ credit).  Auto-loaded
    # when present; without it the check is context-free and over-flags
    # every spine/blend-relaxed pair.
    #
    # ONE READER: ``law_context_from_sidecar`` (above) is the only place a
    # sidecar key is turned into a law keyword.  This CLI, the harness
    # census and the test fixtures all go through it, so a new key is
    # wired in exactly once (both historical frame errors — a lane wrapper
    # that dropped ``terrace_joints`` and one that dropped ``ruleset`` —
    # came from a second, hand-written copy of this block).
    try:
        ctx = law_context_from_sidecar(args.osm, announce=True)
    except FileNotFoundError:
        print("  (no axes sidecar — CONTEXT-FREE check.  These counts "
              "OVERCOUNT by construction and are not defect counts; see "
              "CLAUDE.md 'The standard test harness'.)")  # noqa: F541
        ctx = {}
    except Exception as ex:
        print(f"  (axes sidecar unreadable, context-free check: {ex})")
        ctx = {}
    within, cross, steps = run_checks(
        args.osm,
        max_grade_pct=args.max_grade,
        proximity_m=args.proximity_m,
        edge_search_m=args.edge_search_m,
        edge_step_m=args.edge_step_m,
        top_n=args.top_n,
        **ctx,
    )
    if args.strict and (within or cross or steps):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
