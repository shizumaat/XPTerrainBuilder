"""Obstacle-limitation-surface (OLS) terrain-penetration CUT emitter.

The follow-on arc of the adjacent-ground lateral law
(``docs/specs/obstacle-limitation-surfaces-spec.md``): beyond the graded
strip the ICAO Annex 14 **transitional** surface continues the zone-3
ceiling upward, and beyond each runway end the **approach** surface's
first section governs a splayed fan.  Where the smoothed DEM pokes
through either surface we cut it back — a deliberate scenery-repair
reinterpretation of an obstacle rule (real aerodromes operate with
assessed terrain penetrations; DEM surface-model lumps are the target).

Two phases, in this order and for a reason:

1. **Raster pre-scan** (:func:`ols_penetration_islands`) — vectorized
   numpy over the DEM cells inside each runway's OLS footprint,
   evaluating the analytic ceiling per cell and labelling contiguous
   penetration ISLANDS.  NO geometry is built here.  At an airport with
   no penetrations the whole feature ends in this phase, in
   milliseconds; that is what makes it admissible against the per-airport
   build-time budget (repo ``CLAUDE.md`` HARD LAW).
2. **Banded emission** (:func:`emit_ols_cuts`) — only for the islands the
   refusal guard admits, and only over the ground those islands occupy.
   Reuses ``adjacent_ground._build_cut_bands`` verbatim (run grouping,
   per-station daylight scanning, the shared benching law
   ``grade_law.adjacent_ground_supported_depths``, abutting bands split at
   breakpoints, outer-jump flush) rather than minting a second walker.

**Cut-only, always.**  A vertex altitude is ``min(ceiling, DEM)``: the
emitted surface never rides above the terrain and this law never fills —
save for the SNAP-TO-BOUND triangle diet (spec emission step 5), which
rides a DEM within ``adjacent_ground._CORRIDOR_SNAP_TOL_M`` (0.15 m) of
the ceiling ON the ceiling.  That is the established corridor-band
convention, inside the validator's own edge-noise allowance and below the
smoothed DEM's noise floor, and it is what keeps a planar surface planar
so 3D-collinear decimation can collapse it.

**MOUNTAIN REFUSAL.**  A contiguous island whose required cut exceeds
``OLS_MAX_CUT_DEPTH_M`` anywhere is refused WHOLE
(``grade_law.ols_island_refused``) — cutting a mountain's fringe while
leaving its core sculpts a moat.  Refused islands are still REPORTED
(the validator recomputes the same refusal from the same law and exempts
them — lockstep).

**SEAM REFUSAL.**  An island touching the covering DEM's tile-boundary
edge is likewise refused whole: at a tile line each build sees only half
the island, and an island-GLOBAL depth verdict on two different halves
can disagree — cut one side, refuse the other, wall along the seam.  See
:func:`_prescan`.  Since 2026-07-25 the same refusal is measured against
the CURRENT TILE's own boundary as well (:func:`_tile_line_seam_mask`,
gate ``OLS_SEAM_TILE_LINE_REFUSAL``): an airport DEM usually covers past
the tile it is keyed to, so the data-extent test alone let islands reach
the line and left ``ols_cut`` cut-back nodes metres below the DEM the
seam gap renders — and a cut node cannot be DEM-pinned without un-cutting
the obstruction.  The OLS therefore stops short of the seam instead.

**Clip discipline** (2026-07-09 WELD RULING,
``docs/adjacent_ground_grade_law_plan.md``): exact ``difference()``
against the union of every existing shape — no buffered standoff, which
would leave a groove of raw DEM that renders as a knife edge.
Deliberately NOT clipped to the airport boundary: an OLS lives outside
the fence by nature (the runway-end skirt already emits beyond it).

**ROAD REGRADE** (owner direction 2026-07-28, sub-gate
``config.OLS_ROAD_REGRADE_ENABLED``).  Surface road corridors are masked
out of the banded cut (2026-07-25) so a road keeps its own embankment —
but where a corridor crosses an ADMITTED penetration island that
preserved the very hill the law removes, as a road-width causeway proud
of the fan at grades no ground vehicle route allows.  Such a road is
regraded instead (:func:`_emit_road_regrades`): the OSM way is the road
SPINE, carrying a continuous ``SERVICE_ROAD_MAX_GRADE``-capped,
cut-only profile bounded by the composed ceiling over admitted cells;
emitted as TWO matching ``service_junction`` half-shapes, half a
corridor width outward each side of the spine, with outer edges under
the service-road LATERAL rule (``SERVICE_ROAD_MAX_TRANSVERSE``).  The
graded segment follows the spine at least
``OLS_ROAD_REGRADE_FOLLOW_M`` past the OLS both ways and lands ON the
DEM at both ends.

Behind ``config.OLS_CUT_ENABLED`` (env ``O4_OLS_CUT``, default OFF).  The
gate is read at CALL time so a test can toggle it without a re-import;
with it off :func:`emit_ols_cuts` returns 0 having touched nothing.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

from . import config as _config
from .config import (
    CLEARANCE_STATION_STEP_M,
    OLS_APPROACH_DIVERGENCE,
    OLS_APPROACH_EMIT_REACH_M,
    OLS_APPROACH_FIRST_SECTION_SLOPE,
    OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M,
    OLS_APPROACH_SETBACK_M,
    OLS_APPROACH_SETBACK_VISUAL_CODE1_M,
    OLS_OBSTRUCTION_THRESHOLD_M,
    OLS_TRANSITIONAL_EMIT_REACH_M,
    TILE_CUT_HALF_WIDTH_M,
    runway_code_number,
    runway_end_approach_class,
)
from .grade_law import (
    ols_approach_ceiling,
    ols_island_refused,
    ols_lateral_handover_distance_m,
    ols_transitional_ceiling,
    ols_transitional_slope,
)
from .layout import (BuiltShape, PavementLayout, ROLE_OLS_CUT,
                     ROLE_SERVICE_JUNCTION, R_EARTH)
from .elevation import _sample_dem
from .emit_decimate import Z_TOL_BOUNDARY_M, decimate_shape_group
from .adjacent_ground import _CORRIDOR_SNAP_TOL_M, _build_cut_bands
from .clearance import (
    _AIRSIDE_PAVEMENT_ROLES,
    _GEOM_EXC,
    _nearest_pav_alt,
    _open_coords,
    _pavement_exit_along,
    _RESA_PAVEMENT_PROBE_MAX_M,
    _RESA_SEED_INSET_M,
)

__all__ = ["emit_ols_cuts", "ols_penetration_islands"]

# Ref tags on the emitted shapes — the two surfaces this law builds.
REF_TRANSITIONAL = "ols_transitional"
REF_APPROACH = "ols_approach"

# ── Implementation constants (NOT rule values; every rule number this
# module uses comes from config.py) ───────────────────────────────────
# The law's domain boundaries are strict (``ols_approach_ceiling`` is None
# at exactly s == 0, ``ols_transitional_ceiling`` at exactly S + reach).
# Evaluations that must land INSIDE the domain are nudged by this — the
# convention ``_build_cut_bands`` already uses for its own reach clamp
# (``d = min(cap - 1e-3, ...)``).
_LAW_EPS_M = 1e-3
# SLAB length — the along-reach chunk one ``_build_cut_bands`` march
# covers (see :func:`_surface_slabs` for why the march is slabbed at all).
# Ten stations: long enough that the shared daylight bench still kills an
# isolated ray inside a slab, short enough that a real island is not
# benched away, and it also scopes the emitted footprint to the island
# instead of a ribbon of polygon that merely re-states the DEM.
_BAND_SPLIT_M = 10.0 * CLEARANCE_STATION_STEP_M
# Station-selection margin: how far from an admitted penetration cell a
# station's ray may pass and still be marched.  One band split, so a run
# is never truncated inside the band that carries its island.
_STATION_MARGIN_M = _BAND_SPLIT_M
# Pavement-edge REFERENCE profile sampling.  The transitional anchor is
# the pavement-edge elevation, which is a GRADED surface: <= 1.5 %
# longitudinal under FAA vertical-curve limits, so the worst chord sagitta
# a 50 m sample spacing can hide is r*c^2/8 with r the curve's grade rate
# — about 3 cm at the tightest lawful runway curve, well under the 0.1 m
# emit quantum.  Kept as coarse as that bound allows because this is the
# only per-station shapely read in the pre-scan and therefore the pass's
# cost centre (measured SPJC: ~0.14 ms per read on a welded runway ring).
_REF_PROFILE_STEP_M = 10.0 * CLEARANCE_STATION_STEP_M
# Emitted pieces smaller than this are clip confetti, not surfaces.
_MIN_PIECE_AREA_M2 = 1.0
# Pre-scan raster stride target: the pre-scan is never sampled coarser
# than the emission marches, and a lidar-posting DEM is strided down to
# that rather than scanned at 1 m over square kilometres.
_PRESCAN_POSTING_M = CLEARANCE_STATION_STEP_M


# ──────────────────────────────────────────────────────────────────
# Runway + surface descriptors
# ──────────────────────────────────────────────────────────────────
class _Runway:
    """One runway in LOCAL METRES, with the law keys its surfaces need."""

    def __init__(self, desig_a, desig_b, a, b, width_m, class_a, class_b):
        self.desig_a = str(desig_a or "A")
        self.desig_b = str(desig_b or "B")
        self.a = (float(a[0]), float(a[1]))
        self.b = (float(b[0]), float(b[1]))
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        self.length = math.hypot(dx, dy)
        self.u = (dx / self.length, dy / self.length)
        self.perp = (-self.u[1], self.u[0])
        self.half_width = 0.5 * float(width_m)
        self.code = runway_code_number(self.length)
        self.class_a = class_a
        self.class_b = class_b

    @property
    def classes(self) -> tuple:
        """The distinct approach classes this runway's two ends carry.

        The TRANSITIONAL surface belongs to the runway as a whole, not to
        one end; where the two ends are classified differently the
        composed ceiling is the ``min`` of both (the spec's corner rule
        applied to the flanks) — always the stricter, never permissive.
        """
        return tuple(dict.fromkeys((self.class_a, self.class_b)))


class _Surface:
    """One emitted OLS surface: a flank (transitional) or a fan (approach).

    Carries the law's own PIECES — ``(d_lo, ceiling_at_d_lo, slope,
    d_hi)`` per approach class — so the raster pre-scan, the emission
    closure and the per-vertex valuation all read one definition.  Every
    piece is read out of ``grade_law`` (anchor value + slope + domain),
    never re-derived from the tables; ``tests/test_ols.py`` asserts the
    vectorized form reproduces the scalar law exactly.
    """

    def __init__(self, kind: str, desig: str, runway: _Runway, ref: str):
        self.kind = kind            # "transitional" | "approach"
        self.desig = desig
        self.runway = runway
        self.ref = ref              # REF_TRANSITIONAL / REF_APPROACH
        self.origin = (0.0, 0.0)    # frame origin in local metres
        self.u = (1.0, 0.0)         # along-surface unit vector
        self.n = (0.0, 1.0)         # cross-surface unit vector
        self.pieces: list = []      # (d_lo, c_lo, slope, d_hi)
        self.d_lo = 0.0             # earliest governed distance
        self.d_hi = 0.0             # outermost governed distance
        # transitional only
        self.along_lo = None
        self.along_hi = None
        self.ref_along = None       # coarse profile stations (m along)
        self.ref_profile = None     # coarse profile altitudes (m)
        # approach only
        self.anchor = None          # solved runway-end elevation
        self.half_lo = None         # inner-edge half-width
        self.divergence = None


def _flank_law(code: int, classes, edge_to_centerline_m: float):
    """The transitional law for one flank, as both a closure and pieces.

    Returns ``(ceiling_offset, pieces)``.  ``ceiling_offset(d)`` is the
    composed (``min`` over the runway's approach classes) ceiling OFFSET
    relative to the pavement-EDGE elevation, ``None`` outside the law's
    domain — i.e. exactly ``grade_law.ols_transitional_ceiling``,
    min-composed.  ``pieces`` is the same function in affine form,
    ``(S, C(S), slope, S + reach)`` per class, which the vectorized
    evaluator mins over.
    """
    pieces = []
    for c in classes:
        s = ols_lateral_handover_distance_m(code, c, edge_to_centerline_m)
        c_s = ols_transitional_ceiling(code, c, s, edge_to_centerline_m)
        if c_s is None:
            continue
        pieces.append((float(s), float(c_s),
                       float(ols_transitional_slope(code, c)),
                       float(s) + OLS_TRANSITIONAL_EMIT_REACH_M))

    def ceiling_offset(d: float) -> Optional[float]:
        best = None
        for cls in classes:
            v = ols_transitional_ceiling(code, cls, d, edge_to_centerline_m)
            if v is not None and (best is None or v < best):
                best = v
        return best

    return ceiling_offset, pieces


def _approach_law(code: int, approach_class: str):
    """``(setback, inner_half, divergence, slope)`` of one end's approach
    fan, read from ``config`` exactly as ``grade_law.ols_approach_ceiling``
    reads them — the vectorized pre-scan and the splayed-ray construction
    both need the pieces, not just the scalar evaluation."""
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code == 1)
               else OLS_APPROACH_SETBACK_M)
    inner_half = float(
        OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M[approach_class][code])
    div = float(OLS_APPROACH_DIVERGENCE[approach_class])
    slope = float(OLS_APPROACH_FIRST_SECTION_SLOPE[approach_class][code])
    return setback, inner_half, div, slope


def _fill_gaps(values) -> np.ndarray:
    """Nearest-valid fill of a reference profile: a sample with no
    pavement within reach borrows its neighbours' read (the runway-end
    skirt's own short-run rescue)."""
    arr = np.array([np.nan if v is None else float(v) for v in values],
                   dtype=float)
    ok = ~np.isnan(arr)
    if not ok.any():
        return arr
    idx = np.arange(len(arr), dtype=float)
    arr[~ok] = np.interp(idx[~ok], idx[ok], arr[ok])
    return arr


# ──────────────────────────────────────────────────────────────────
# Scene assembly (shared by the pre-scan and the emitter)
# ──────────────────────────────────────────────────────────────────
class _Scene:
    """Everything both phases need, built once: the local-metre frame, the
    DEM sampler, the runway list and the elevation-anchored surfaces."""

    def __init__(self, layout: PavementLayout, dem, tile_lat: int,
                 tile_lon: int, source_runways=None):
        self.layout = layout
        self.dem = dem
        self.tile_lat = int(tile_lat)
        self.tile_lon = int(tile_lon)
        lat0, lon0 = layout.anchor
        self.lat0, self.lon0 = float(lat0), float(lon0)
        self.cos0 = math.cos(math.radians(self.lat0))
        self.airside = [s for s in layout.shapes
                        if s.role in _AIRSIDE_PAVEMENT_ROLES
                        and s.polygon is not None and not s.polygon.is_empty]
        self._pav_tree = None
        self._prep_pav = None
        if self.airside:
            try:
                self._pav_tree = STRtree([s.polygon for s in self.airside])
            except _GEOM_EXC:
                self._pav_tree = None
        # The RUNWAY-family subset, and its own index.  A flank's law
        # anchor is the RUNWAY's pavement edge (the transitional rises
        # from the runway strip), so the reference profile reads that
        # rather than whatever apron happens to lie nearest — which is
        # also what keeps the pre-scan cheap: ``_edge_interp_alt`` walks
        # every vertex of the shape it is given, and a runway segment is a
        # four-corner rect where an apron can carry hundreds.
        from .layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING
        self.runway_pav = [s for s in self.airside
                           if s.role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)]
        self._rwy_tree = None
        if self.runway_pav:
            try:
                self._rwy_tree = STRtree(
                    [s.polygon for s in self.runway_pav])
            except _GEOM_EXC:
                self._rwy_tree = None
        self.runways = self._build_runways(source_runways)
        self.surfaces: list = []
        for rw in self.runways:
            self.surfaces.extend(self._flank_surfaces(rw))
            self.surfaces.extend(self._fan_surfaces(rw))

    # -- frame -----------------------------------------------------
    def to_m(self, lat: float, lon: float) -> tuple:
        return (math.radians(lon - self.lon0) * R_EARTH * self.cos0,
                math.radians(lat - self.lat0) * R_EARTH)

    def sample_dem(self, x: float, y: float) -> Optional[float]:
        try:
            lat = self.lat0 + math.degrees(y / R_EARTH)
            lon = self.lon0 + math.degrees(x / (R_EARTH * self.cos0))
            return _sample_dem(self.dem, self.tile_lat, self.tile_lon,
                               lat, lon)
        except _GEOM_EXC:
            return None

    # -- runways ---------------------------------------------------
    def _build_runways(self, source_runways) -> list:
        out: list = []
        if source_runways:
            # AUTHORITATIVE: apt.dat row-100 centreline endpoints + width,
            # the same anchor Pass C and the runway-end skirt use.
            for r in source_runways:
                try:
                    a = self.to_m(r.lat_a, r.lon_a)
                    b = self.to_m(r.lat_b, r.lon_b)
                except _GEOM_EXC:
                    continue
                width = float(getattr(r, "width_m", 0.0) or 0.0)
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 1.0 or width <= 0:
                    continue
                out.append(_Runway(
                    getattr(r, "desig_a", ""), getattr(r, "desig_b", ""),
                    a, b, width,
                    runway_end_approach_class(
                        getattr(r, "markings_a", 0),
                        getattr(r, "approach_lights_a", 0)),
                    runway_end_approach_class(
                        getattr(r, "markings_b", 0),
                        getattr(r, "approach_lights_b", 0))))
            return out
        # FALLBACK: derive from the emitted runway rects.  No apt.dat
        # metadata on this path — the blank-data ladder in
        # ``runway_end_approach_class`` classifies both ends
        # ``non_precision``, the stricter instrument geometry (the safe
        # direction the spec's risk register calls for).
        from .layout import ROLE_RUNWAY
        groups: dict = {}
        for s in self.layout.shapes:
            if s.role != ROLE_RUNWAY or s.polygon is None \
                    or s.polygon.is_empty:
                continue
            groups.setdefault(s.ref or "?", []).append(s)
        for ref, shapes in groups.items():
            pts = [p for s in shapes for p in _open_coords(s.polygon)]
            if len(pts) < 4:
                continue
            axis = _principal_axis(pts)
            if axis is None:
                continue
            a, b, width = axis
            out.append(_Runway(ref, ref, a, b, width,
                               runway_end_approach_class(0, 0),
                               runway_end_approach_class(0, 0)))
        return out

    # -- pavement reads --------------------------------------------
    def pav_alt_near(self, x: float, y: float,
                     max_distance_m: float = 5.0,
                     runway_only: bool = False) -> Optional[float]:
        """``clearance._nearest_pav_alt`` narrowed to the candidates an
        STRtree returns — the unfiltered call is O(#shapes) in shapely
        ``distance`` and the reference profiles need it hundreds of times
        per runway.

        ``runway_only`` reads the RUNWAY family alone (the flank's law
        anchor), falling back to the whole airside union when no runway
        pavement is in range.
        """
        if runway_only and self.runway_pav:
            v = self._nearest_in(self.runway_pav, self._rwy_tree,
                                 x, y, max_distance_m)
            if v is not None:
                return v
        if not self.airside:
            return None
        return self._nearest_in(self.airside, self._pav_tree,
                                x, y, max_distance_m)

    @staticmethod
    def _nearest_in(shapes, tree, x, y, max_distance_m):
        cand = shapes
        if tree is not None:
            try:
                idx = tree.query_nearest(
                    Point(x, y), max_distance=max_distance_m,
                    return_distance=False)
            except (TypeError, *_GEOM_EXC):
                idx = None
            if idx is not None:
                if len(idx) == 0:
                    return None
                cand = [shapes[int(i)] for i in np.atleast_1d(idx)]
        return _nearest_pav_alt(cand, x, y, max_distance_m)

    def prep_pav_near(self, x: float, y: float, radius_m: float):
        """Prepared airside-pavement union LOCAL to one runway end — the
        containment target ``_pavement_exit_along`` marches against.

        Local rather than airport-wide because the union is the pre-scan's
        second cost centre and the exit march never leaves
        ``_RESA_PAVEMENT_PROBE_MAX_M`` of the end (unioning every apron at
        a big airport to answer a 300 m ray is pure waste)."""
        if not self.airside:
            return None
        polys = [s.polygon for s in self.airside]
        if self._pav_tree is not None:
            try:
                idx = self._pav_tree.query(
                    Point(x, y).buffer(radius_m))
                polys = [self.airside[int(i)].polygon
                         for i in np.atleast_1d(idx)]
            except _GEOM_EXC:
                pass
        if not polys:
            return None
        try:
            return prep(unary_union(polys))
        except _GEOM_EXC:
            return None

    # -- surfaces --------------------------------------------------
    def _flank_surfaces(self, rw: _Runway) -> list:
        """The two lateral transitional surfaces of one runway.

        The surface frame's origin is the runway rectangle's long-edge
        start; ``d`` is the distance out from that pavement EDGE (the
        law's own coordinate) and ``edge_to_centerline`` is the rectangle
        half-width.  Each carries the pavement-EDGE elevation profile —
        the law's anchor.
        """
        out = []
        _closure, pieces = _flank_law(rw.code, rw.classes, rw.half_width)
        if not pieces:
            return out
        n_ref = max(2, int(math.ceil(rw.length / _REF_PROFILE_STEP_M)) + 1)
        ts = np.linspace(0.0, rw.length, n_ref)
        for side in (-1.0, 1.0):
            nx, ny = side * rw.perp[0], side * rw.perp[1]
            ox = rw.a[0] + nx * rw.half_width
            oy = rw.a[1] + ny * rw.half_width
            raw = [self.pav_alt_near(float(ox + rw.u[0] * t),
                                     float(oy + rw.u[1] * t),
                                     runway_only=True) for t in ts]
            if not any(v is not None for v in raw):
                continue
            srf = _Surface("transitional", f"{rw.desig_a}/{rw.desig_b}",
                           rw, REF_TRANSITIONAL)
            srf.origin = (ox, oy)
            srf.u = rw.u
            srf.n = (nx, ny)
            srf.pieces = pieces
            srf.d_lo = min(p[0] for p in pieces)
            srf.d_hi = max(p[3] for p in pieces)
            srf.along_lo, srf.along_hi = 0.0, rw.length
            srf.ref_along = ts
            srf.ref_profile = _fill_gaps(raw)
            out.append(srf)
        return out

    def _fan_surfaces(self, rw: _Runway) -> list:
        """The approach fan off each runway end.

        ANCHOR (the runway-end skirt's discipline): seed
        ``_RESA_SEED_INSET_M`` inside the apt.dat row-100 endpoint, march
        ``_pavement_exit_along`` to the pavement exit and read the
        pavement altitude just inside it — the SOLVED runway-end
        elevation, the surface the patch renders.  The law is still
        evaluated at the distance beyond the RUNWAY END itself
        (``ols_approach_ceiling``'s setback is measured from the end, not
        from the pavement exit).
        """
        out = []
        ends = (((rw.a, (-rw.u[0], -rw.u[1])), rw.desig_a, rw.class_a),
                ((rw.b, rw.u), rw.desig_b, rw.class_b))
        for (end_pt, outward), desig, cls in ends:
            nx, ny = outward
            prep_pav = self.prep_pav_near(end_pt[0], end_pt[1],
                                          _RESA_PAVEMENT_PROBE_MAX_M)
            seed = (end_pt[0] - nx * _RESA_SEED_INSET_M,
                    end_pt[1] - ny * _RESA_SEED_INSET_M)
            start = 0.0
            if prep_pav is not None:
                start = _pavement_exit_along(
                    prep_pav, seed[0], seed[1], nx, ny,
                    _RESA_PAVEMENT_PROBE_MAX_M, CLEARANCE_STATION_STEP_M)
            p0 = (seed[0] + nx * start, seed[1] + ny * start)
            anchor = self.pav_alt_near(p0[0] - nx * 1.0, p0[1] - ny * 1.0)
            if anchor is None:
                anchor = self.pav_alt_near(seed[0], seed[1])
            if anchor is None:
                anchor = self.sample_dem(end_pt[0], end_pt[1])
            if anchor is None:
                continue
            setback, inner_half, div, slope = _approach_law(rw.code, cls)
            srf = _Surface("approach", str(desig), rw, REF_APPROACH)
            srf.origin = end_pt                 # the RUNWAY END itself
            srf.u = (nx, ny)
            srf.n = (-ny, nx)
            srf.anchor = float(anchor)
            srf.half_lo = inner_half
            srf.divergence = div
            srf.d_lo = setback
            srf.d_hi = setback + OLS_APPROACH_EMIT_REACH_M
            srf.pieces = [(setback, 0.0, slope, srf.d_hi)]
            out.append(srf)
        return out

    # -- ceiling evaluation ----------------------------------------
    def surface_ceiling(self, srf: _Surface, x, y, clamp: bool = False):
        """Absolute ceiling elevation of ``srf`` at local ``(x, y)``.

        Array-in / array-out, ``np.nan`` where this surface does not
        govern.  ``clamp=True`` extends the evaluation to the nearest
        in-domain point instead of returning ``nan`` — used ONLY when
        valuing a clip-introduced vertex of a piece this surface owns, so
        a vertex a few centimetres outside the domain does not fall back
        to the raw DEM and mint a step.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        ox, oy = srf.origin
        ux, uy = srf.u
        nx, ny = srf.n
        along = (x - ox) * ux + (y - oy) * uy
        lateral = (x - ox) * nx + (y - oy) * ny
        if srf.kind == "transitional":
            ref = np.interp(along, srf.ref_along, srf.ref_profile)
            d = lateral
            in_span = ((along >= srf.along_lo - _STATION_MARGIN_M)
                       & (along <= srf.along_hi + _STATION_MARGIN_M))
            if clamp:
                d = np.clip(d, srf.d_lo, srf.d_hi - _LAW_EPS_M)
                in_span = np.ones(np.shape(d), dtype=bool)
        else:
            ref = np.full(np.shape(x), srf.anchor, dtype=float)
            d = along
            half = (srf.half_lo
                    + srf.divergence * np.maximum(d - srf.d_lo, 0.0))
            in_span = np.abs(lateral) <= half
            if clamp:
                d = np.clip(d, srf.d_lo + _LAW_EPS_M, srf.d_hi)
                in_span = np.ones(np.shape(d), dtype=bool)
        best = np.full(np.shape(x), np.nan, dtype=float)
        for d_lo, c_lo, slope, d_hi in srf.pieces:
            gov = in_span & (d >= d_lo) & (d < d_hi)
            if clamp:
                gov = in_span
            val = ref + c_lo + slope * (np.clip(d, d_lo, d_hi) - d_lo)
            best = np.where(gov & (np.isnan(best) | (val < best)),
                            val, best)
        return best

    def composed_ceiling(self, x, y, own: Optional[_Surface] = None):
        """``min`` over every OLS surface that governs ``(x, y)``.

        The spec's corner-composition rule: alongside the runway the
        transitional governs, beyond the end the fan governs, and where
        both claim, the emitted ceiling is the lower of the two.  ``own``
        (the surface a piece belongs to) is additionally evaluated CLAMPED
        so a clip vertex just outside its own domain still takes that
        surface's value rather than dropping to the DEM.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        best = np.full(np.shape(x), np.nan, dtype=float)
        for srf in self.surfaces:
            c = self.surface_ceiling(srf, x, y, clamp=(srf is own))
            best = np.fmin(best, c)
        return best


def _principal_axis(pts):
    """Centreline endpoints + width of a runway-rectangle point cloud
    (the no-apt.dat fallback path only)."""
    arr = np.asarray(pts, dtype=float)
    c = arr.mean(axis=0)
    try:
        vals, vecs = np.linalg.eigh(np.cov((arr - c).T))
    except np.linalg.LinAlgError:
        return None
    u = vecs[:, int(np.argmax(vals))]
    t = (arr - c) @ u
    w = (arr - c) @ np.array([-u[1], u[0]])
    length = float(t.max() - t.min())
    width = float(w.max() - w.min())
    if length < 1.0 or width <= 0.0:
        return None
    a = (float(c[0] + u[0] * t.min()), float(c[1] + u[1] * t.min()))
    b = (float(c[0] + u[0] * t.max()), float(c[1] + u[1] * t.max()))
    return a, b, width


# ──────────────────────────────────────────────────────────────────
# Phase 1 — the raster pre-scan
# ──────────────────────────────────────────────────────────────────
class _Grid:
    """The pre-scan raster: DEM cells in the layout's local frame with the
    composed ceiling, the penetration labels and the refusal mask.  The
    emitter re-reads it (rather than the DEM) so its band scan is in
    LOCKSTEP with the pre-scan that admitted the islands."""

    def __init__(self, X, Y, Z, ceil, dx_m, dy_m, tile_edge=None,
                 seam_edge=None):
        self.X, self.Y, self.Z, self.ceil = X, Y, Z, ceil
        self.dx_m, self.dy_m = dx_m, dy_m
        self.x0 = float(X[0, 0])
        self.y0 = float(Y[0, 0])
        self.h, self.w = Z.shape
        self.cell_area = dx_m * dy_m
        self.labels = np.zeros(Z.shape, dtype=np.int32)
        self.refused = np.zeros(Z.shape, dtype=bool)
        # Cells on a raster row/column that IS the covering DEM's own tile
        # boundary — i.e. where the footprint ran off the end of the data
        # (see :func:`_dem_raster` and the seam-determinism rule in
        # :func:`_prescan`).
        self.tile_edge = (np.zeros(Z.shape, dtype=bool)
                          if tile_edge is None else tile_edge)
        # Cells at (or past) the CURRENT TILE's own integer lat/lon line —
        # the ground ``tile_cut`` slices.  See
        # :func:`_tile_line_seam_mask`; all-False with its gate off.
        self.seam_edge = (np.zeros(Z.shape, dtype=bool)
                          if seam_edge is None else seam_edge)

    def index(self, x: float, y: float):
        j = int(round((x - self.x0) / self.dx_m))
        i = int(round((self.y0 - y) / self.dy_m))
        if 0 <= i < self.h and 0 <= j < self.w:
            return i, j
        return None

    def scan_alt(self, x: float, y: float) -> Optional[float]:
        """DEM read for the band SCAN — nearest pre-scan cell, blinded
        over REFUSED ground so no band can ever be triggered by a mountain
        the law refused whole."""
        ij = self.index(x, y)
        if ij is None:
            return None
        i, j = ij
        if self.refused[i, j]:
            return None
        return float(self.Z[i, j])


def _dem_raster(scene: _Scene, bbox):
    """The DEM cells covering ``bbox`` (local metres) as a :class:`_Grid`.

    Reads the DEM's OWN posting (nothing is invented between samples) and
    strides it down so the pre-scan is never finer than
    ``_PRESCAN_POSTING_M`` — a 1 m lidar tile would otherwise mean 10⁶+
    cells per runway for no fidelity over the 5 m emission march.
    ``None`` when the DEM exposes no raster.

    The window is CLAMPED to the DEM's own extent, so an OLS footprint
    that reaches past the covering tile is silently truncated.  Which
    sides were clamped is recorded in the grid's ``tile_edge`` mask —
    :func:`_prescan` needs it for the cross-tile seam rule (an island
    against a truncated side is only HALF an island).
    """
    dem = scene.dem
    alt = getattr(dem, "alt_dem", None)
    if alt is None or int(getattr(dem, "nxdem", 0) or 0) < 2:
        return None
    x0, x1 = float(dem.x0), float(dem.x1)
    y0, y1 = float(dem.y0), float(dem.y1)
    nx, ny = int(dem.nxdem), int(dem.nydem)
    xmin, ymin, xmax, ymax = bbox
    lat_lo = scene.lat0 + math.degrees(ymin / R_EARTH) - scene.tile_lat
    lat_hi = scene.lat0 + math.degrees(ymax / R_EARTH) - scene.tile_lat
    lon_lo = (scene.lon0 + math.degrees(xmin / (R_EARTH * scene.cos0))
              - scene.tile_lon)
    lon_hi = (scene.lon0 + math.degrees(xmax / (R_EARTH * scene.cos0))
              - scene.tile_lon)
    step_lon = (x1 - x0) / (nx - 1)
    step_lat = (y1 - y0) / (ny - 1)
    j0 = max(0, int(math.floor((lon_lo - x0) / step_lon)))
    j1 = min(nx - 1, int(math.ceil((lon_hi - x0) / step_lon)))
    i0 = max(0, int(math.floor((y1 - lat_hi) / step_lat)))
    i1 = min(ny - 1, int(math.ceil((y1 - lat_lo) / step_lat)))
    if j1 <= j0 or i1 <= i0:
        return None
    post_x = math.radians(step_lon) * R_EARTH * scene.cos0
    post_y = math.radians(step_lat) * R_EARTH
    stride = max(1, int(math.floor(
        _PRESCAN_POSTING_M / max(1e-6, min(post_x, post_y)))))
    Z = np.asarray(alt[i0:i1 + 1:stride, j0:j1 + 1:stride], dtype=float)
    if Z.size == 0 or Z.shape[0] < 2 or Z.shape[1] < 2:
        return None
    jj = np.arange(j0, j1 + 1, stride)
    ii = np.arange(i0, i1 + 1, stride)
    lon = scene.tile_lon + x0 + jj * step_lon
    lat = scene.tile_lat + y1 - ii * step_lat
    Xr = np.radians(lon - scene.lon0) * R_EARTH * scene.cos0
    Yr = np.radians(lat - scene.lat0) * R_EARTH
    X, Y = np.meshgrid(Xr, Yr)
    # TILE-EDGE mask: the outermost grid row / column on each side whose
    # window bound was CLAMPED by the DEM's own extent.  ``j0 <= 0`` /
    # ``j1 >= nx - 1`` is exactly "the footprint asked for data past this
    # end of the raster and did not get it".
    tile_edge = np.zeros(Z.shape, dtype=bool)
    if i0 <= 0:
        tile_edge[0, :] = True
    if i1 >= ny - 1:
        tile_edge[-1, :] = True
    if j0 <= 0:
        tile_edge[:, 0] = True
    if j1 >= nx - 1:
        tile_edge[:, -1] = True
    return _Grid(X, Y, Z, None, post_x * stride, post_y * stride,
                 tile_edge=tile_edge,
                 seam_edge=_tile_line_seam_mask(
                     scene, X, Y, post_x * stride, post_y * stride))


def _tile_line_seam_mask(scene: _Scene, X, Y, dx_m: float, dy_m: float):
    """Cells within the cut band of the CURRENT TILE's own integer lat/lon
    boundary — the ground ``tile_cut`` slices through — as a boolean mask,
    or ``None`` when the gate ``OLS_SEAM_TILE_LINE_REFUSAL`` is off.

    WHY THIS EXISTS (defect measured at SPLP -13/-078, 2026-07-25).  The
    spec's seam rule refuses an island "touching the covering DEM's
    tile-boundary edge", and :func:`_dem_raster` marks exactly that: the
    rows/columns where the WINDOW WAS CLAMPED by the DEM's own extent.
    But an airport DEM routinely covers well past the tile line it is
    keyed to — measured here, the -13/-078 raster runs 1088 m EAST of
    lon -77 — so no island near the seam was ever flagged, and two
    penetration islands sitting ON the tile line (x = -137.3, exactly the
    integer meridian) and 5 m inside the cut-back (x = -147.4) were
    admitted.  Their bands emitted ``ols_cut`` pieces that the post-emit
    ``cut_layout_at_tile_boundaries`` then SLICED at the cut-back line,
    minting 4 cut-back nodes 0.35-2.18 m BELOW the DEM the neighbouring
    10 m seam gap renders — the exact wall along the seam the rule was
    written to prevent.  (And it is one-sided: the -13/-077 build's
    pre-scan finds no transitional island there at all.)
    A DEM-pin cannot repair those nodes: an OLS cut is
    ``min(ceiling, DEM)``, so raising a node to the DEM would UN-CUT a
    real obstruction at the seam.

    Rule: measure against the TILE LINE (what the cut actually slices),
    not the data extent.  A cell within ``TILE_CUT_HALF_WIDTH_M`` + one
    raster cell of the current tile's boundary — the cut's own gap plus
    the raster's resolution — is a seam cell, and :func:`_prescan` refuses
    any island touching one WHOLE, exactly as it already does for a
    truncated side.  Both tile builds apply the identical geometric test
    to the shared line, so they cannot disagree.  The trade is the spec's
    own: some lawful cuts within a band of the seam are given up to buy a
    seam that cannot wall.

    Deliberately a BAND about the line, not a half-plane: an island lying
    wholly in the NEIGHBOUR tile is that build's business (this build's
    copy is removed by the same tile cut either way), and refusing those
    too would blind ``scan_alt`` over most of a cross-tile airport's
    raster for no gain."""
    if not _config.OLS_SEAM_TILE_LINE_REFUSAL:
        return None
    band_x = TILE_CUT_HALF_WIDTH_M + max(dx_m, 0.0)
    band_y = TILE_CUT_HALF_WIDTH_M + max(dy_m, 0.0)
    x_lo, y_lo = scene.to_m(float(scene.tile_lat), float(scene.tile_lon))
    x_hi, y_hi = scene.to_m(float(scene.tile_lat + 1),
                            float(scene.tile_lon + 1))
    return ((np.abs(X - x_lo) <= band_x) | (np.abs(X - x_hi) <= band_x)
            | (np.abs(Y - y_lo) <= band_y) | (np.abs(Y - y_hi) <= band_y))


def _footprint_bbox(scene: _Scene):
    """Local-metre bbox of every OLS surface footprint in the scene."""
    pts = []
    for srf in scene.surfaces:
        ox, oy = srf.origin
        ux, uy = srf.u
        nx, ny = srf.n
        if srf.kind == "transitional":
            for a in (srf.along_lo, srf.along_hi):
                for d in (0.0, srf.d_hi):
                    pts.append((ox + ux * a + nx * d, oy + uy * a + ny * d))
        else:
            half_hi = (srf.half_lo
                       + srf.divergence * OLS_APPROACH_EMIT_REACH_M)
            for a, h in ((srf.d_lo, srf.half_lo), (srf.d_hi, half_hi)):
                for sgn in (-1.0, 1.0):
                    pts.append((ox + ux * a + nx * sgn * h,
                                oy + uy * a + ny * sgn * h))
    if not pts:
        return None
    arr = np.asarray(pts, dtype=float)
    return (float(arr[:, 0].min()), float(arr[:, 1].min()),
            float(arr[:, 0].max()), float(arr[:, 1].max()))


def _label_islands(mask: np.ndarray):
    """8-connected labelling of the penetration mask.

    ``scipy.ndimage.label`` when scipy is importable (it is a declared
    dependency — ``requirements.txt``); a small iterative flood fill
    otherwise, so this module never hard-depends on the optional path.
    8-connectivity deliberately: a mountain's diagonally-touching fringe
    cells belong to the SAME island, and refusal is a whole-island rule.
    """
    try:
        from scipy.ndimage import label as _label
        return _label(mask, structure=np.ones((3, 3), dtype=int))
    except ImportError:                                   # pragma: no cover
        labels = np.zeros(mask.shape, dtype=np.int32)
        n = 0
        h, w = mask.shape
        for si in range(h):
            for sj in range(w):
                if not mask[si, sj] or labels[si, sj]:
                    continue
                n += 1
                labels[si, sj] = n
                stack = [(si, sj)]
                while stack:
                    ci, cj = stack.pop()
                    for di in (-1, 0, 1):
                        for dj in (-1, 0, 1):
                            ai, aj = ci + di, cj + dj
                            if (0 <= ai < h and 0 <= aj < w
                                    and mask[ai, aj] and not labels[ai, aj]):
                                labels[ai, aj] = n
                                stack.append((ai, aj))
        return labels, n


def _prescan(scene: _Scene):
    """The raster pre-scan.  Returns ``(islands, grid)``; ``grid`` is None
    when there is nothing to scan.  Builds NO geometry.

    CROSS-TILE SEAM DETERMINISM (ruling 2026-07-25).  ``_sample_dem``
    returns ``None`` out-of-tile and ``_dem_raster`` clamps its window to
    the covering DEM, so at a tile line the pre-scan sees only HALF an
    island — and the refusal guard (``grade_law.ols_island_refused``) is
    island-GLOBAL.  The two tile builds can therefore reach OPPOSITE
    verdicts on one island: cut on the side whose half is shallow, refuse
    on the side that owns the peak, leaving a wall along the seam.

    Rule: an island any of whose cells lies on the raster's TILE-BOUNDARY
    edge is REFUSED WHOLE, deterministically.  Each build sees its own
    half touching that edge, so both refuse — under every data-availability
    condition, including the case where one tile's DEM is missing
    entirely.  The trade is deliberate: some lawful cuts near seams are
    given up to buy a verdict that cannot disagree across a seam.  A
    forensics line names the count.
    """
    if not scene.surfaces:
        return [], None
    bbox = _footprint_bbox(scene)
    if bbox is None:
        return [], None
    grid = _dem_raster(scene, bbox)
    if grid is None:
        return [], None
    X, Y, Z = grid.X, grid.Y, grid.Z
    ceil = np.full(X.shape, np.nan, dtype=float)
    owner = np.full(X.shape, -1, dtype=np.int32)
    for k, srf in enumerate(scene.surfaces):
        c = scene.surface_ceiling(srf, X, Y)
        take = ~np.isnan(c) & (np.isnan(ceil) | (c < ceil))
        ceil = np.where(take, c, ceil)
        owner = np.where(take, k, owner)
    grid.ceil = ceil
    governed = ~np.isnan(ceil)
    if not governed.any():
        return [], None
    depth = np.where(governed, Z - ceil, -np.inf)
    mask = depth > OLS_OBSTRUCTION_THRESHOLD_M
    if not mask.any():
        return [], grid
    labels, n = _label_islands(mask)
    grid.labels = labels
    islands = []
    n_seam_refused = 0
    for lab in range(1, n + 1):
        sel = labels == lab
        d = depth[sel]
        deep = int(np.argmax(d))
        max_depth = float(d[deep])
        # HALF-AN-ISLAND GUARD, evaluated before the depth guard so the
        # reason reported is the one that actually decided it.
        on_data_edge = bool((sel & grid.tile_edge).any())
        on_tile_line = bool((sel & grid.seam_edge).any())
        on_seam = on_data_edge or on_tile_line
        if on_seam:
            reason = "tile_edge" if on_data_edge else "tile_line"
            refused = True
            n_seam_refused += 1
        else:
            refused = bool(ols_island_refused(max_depth))
            reason = "max_depth" if refused else None
        if refused:
            grid.refused |= sel
        srf_idx = int(owner[sel][deep])
        srf = scene.surfaces[srf_idx] if srf_idx >= 0 else None
        xs, ys = X[sel], Y[sel]
        islands.append({
            "surface": srf.kind if srf else "transitional",
            "desig": srf.desig if srf else "",
            "ref": srf.ref if srf else REF_TRANSITIONAL,
            "max_depth_m": max_depth,
            "refused": refused,
            "refused_reason": reason,
            "on_tile_edge": on_seam,
            "cells": [(float(a), float(b)) for a, b in zip(xs, ys)],
            "n_cells": int(sel.sum()),
            "area_m2": float(sel.sum()) * float(grid.cell_area),
            "deepest_xy": (float(xs[deep]), float(ys[deep])),
            "ceiling_at_deepest_m": float(ceil[sel][deep]),
            "dem_at_deepest_m": float(Z[sel][deep]),
        })
    islands.sort(key=lambda isl: -isl["max_depth_m"])
    if n_seam_refused:
        try:
            import O4_UI_Utils as UI
            UI.vprint(1, f"  [ols] cross-tile seam: {n_seam_refused} of "
                         f"{n} penetration island(s) touch the DEM's "
                         f"tile-boundary edge — REFUSED WHOLE for "
                         f"determinism (each tile build sees only half an "
                         f"island; an island-global depth verdict could "
                         f"disagree across the seam and mint a wall).")
        except Exception:
            pass
    return islands, grid


def ols_penetration_islands(layout: PavementLayout, dem, tile_lat: int,
                            tile_lon: int, source_runways=None) -> list:
    """The raster pre-scan result: one dict per contiguous penetration
    island of the OLS transitional / approach surfaces.

    Keys: ``surface`` (``"transitional"`` | ``"approach"``), ``desig``,
    ``max_depth_m``, ``refused`` (``grade_law.ols_island_refused`` OR the
    cross-tile seam rule), ``refused_reason`` (``"max_depth"`` /
    ``"tile_edge"`` / ``None``), ``on_tile_edge``,
    ``cells`` (local-metre centres of the penetrating DEM cells),
    ``area_m2``; plus the forensics fields ``ref``, ``n_cells``,
    ``deepest_xy``, ``ceiling_at_deepest_m``, ``dem_at_deepest_m``.

    PURE READ — emits nothing, mutates nothing, and is deliberately NOT
    gated: the validator recomputes it in lockstep with the emitter, and
    slice 2 is a report-only pass.  Sorted deepest-first.
    """
    if dem is None or layout is None:
        return []
    if getattr(layout, "anchor", None) is None:
        return []
    scene = _Scene(layout, dem, tile_lat, tile_lon, source_runways)
    islands, _grid = _prescan(scene)
    return islands


# ──────────────────────────────────────────────────────────────────
# Phase 2 — banded emission
# ──────────────────────────────────────────────────────────────────
def _surface_slabs(srf: _Surface):
    """The along-reach SLABS one surface is marched in: ``(d0, cap)`` pairs
    in the surface's own outward coordinate, ``d0`` measured from its INNER
    EDGE (the handover ``S`` for a flank, the setback for a fan).

    WHY SLABS (and not one march over the whole reach).  The shared
    daylight-benching law ``grade_law.adjacent_ground_supported_depths`` —
    which ``_build_cut_bands`` applies internally, and which this module
    reuses rather than minting a second rule — limits a station's governed
    OUTWARD extent to ``ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`` times the
    ALONG-FRONTAGE distance to an unobstructed neighbour.  For an
    adjacent-ground band, outward extent and frontage are both lateral and
    comparable.  For an OLS surface they are not: the SPJC origin island is
    ~50 m of frontage across the approach fan but ~250 m of along-track
    extent, and a single full-reach march would bench that legitimate
    island down to ~50 m — i.e. cut the empty ground short of the knoll and
    leave the knoll standing.  Marching in slabs applies the SAME law at
    the scale it was written for: within a slab an isolated deep ray is
    still clamped to a shallow benched entry (the blade class the law
    kills), while an island that genuinely spans several slabs is cut in
    each of them.

    Consecutive slabs overlap by ``_LAW_EPS_M`` so the next slab's inner
    row is trimmed by the emitted-piece difference rather than standing a
    millimetre off it (the weld ruling: no groove of raw DEM between two
    active cut bands).
    """
    reach = srf.d_hi - srf.d_lo
    d0 = 0.0
    while d0 < reach - _LAW_EPS_M:
        remaining = reach - d0
        cap = min(_BAND_SPLIT_M + 2.0 * _LAW_EPS_M, remaining)
        yield d0, cap
        d0 += _BAND_SPLIT_M


def _flank_slab(srf: _Surface, d0: float):
    """``(stations, alts, outwards, ceiling_offset)`` for one flank slab:
    the runway long edge, offset out to ``S + d0``, marched at
    ``CLEARANCE_STATION_STEP_M`` with the pavement-EDGE elevation as the
    law's anchor.

    The closure IS ``grade_law.ols_transitional_ceiling``, min-composed
    over the runway's approach classes (the transitional belongs to the
    runway, not to one end) and shifted into the slab's coordinate.  It
    returns ``None`` wherever the law does not govern — beyond
    ``S + OLS_TRANSITIONAL_EMIT_REACH_M`` — and ``_build_cut_bands`` skips
    a ``None`` ceiling, which is what bounds the outermost slab.

    THE HANDOVER, and why the station line sits AT ``S`` rather than on
    the pavement edge.  Inside ``S`` the law also answers ``None``
    ("adjacent-ground owns that ground"), and the obvious arrangement —
    stations on the pavement edge, the ``None``-skip emptying the first
    band — does bound the band correctly, but it makes the shared daylight
    bench read the ABSOLUTE from-edge distance: ``_build_cut_bands`` hands
    ``adjacent_ground_supported_depths`` an outer of ~S + something while
    every unobstructed neighbour reads 0, so at
    ``ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`` any run shorter than ~S/2 of
    frontage is benched below the band's own inner edge and vanishes
    entirely (measured: a 140 m-wide knoll straddling the handover emitted
    nothing).  Starting the march AT ``S`` gives the bench the quantity it
    was written for — the extent BEYOND the surface's inner edge — and the
    band still cannot reach inside ``S``, because no station does.
    """
    rw = srf.runway
    base = srf.d_lo + d0
    n_st = max(2, int(math.ceil(rw.length / CLEARANCE_STATION_STEP_M)) + 1)
    ts = np.linspace(0.0, rw.length, n_st)
    ox = srf.origin[0] + srf.n[0] * base
    oy = srf.origin[1] + srf.n[1] * base
    stations = [(float(ox + srf.u[0] * t), float(oy + srf.u[1] * t))
                for t in ts]
    ref = np.interp(ts, srf.ref_along, srf.ref_profile)
    alts = [None if math.isnan(v) else float(v) for v in ref]
    law, _pieces = _flank_law(rw.code, rw.classes, rw.half_width)

    def ceiling_offset(d: float) -> Optional[float]:
        return law(base + float(d))

    return stations, alts, [srf.n] * n_st, ceiling_offset


def _fan_slab(srf: _Surface, d0: float):
    """``(stations, alts, outwards, ceiling_offset)`` for one approach-fan
    slab.

    The rays are laid out so the fan is confined by the LAW's own
    divergence rather than by bespoke clipping geometry: a ray at relative
    offset ``t`` starts at ``t * (inner_half + divergence * d0)`` on the
    slab's inner line and marches along ``u + t * divergence * n`` — a
    direction whose ALONG-track component is exactly 1, so
    ``_build_cut_bands``' ``d`` IS the along-track distance and the ray's
    lateral offset stays at ``t * (inner_half + divergence * (d0 + d))``:
    a constant RELATIVE position inside the splay.  Every sample is
    therefore inside the fan at every ``d``, and the ceiling — flat
    transversely (Annex 14 measures the approach slope in the vertical
    plane through the centreline) — is one function of ``d`` shared by
    every ray, which is exactly what the builder's single
    ``ceiling_offset`` closure requires.
    """
    code = srf.runway.code
    cls = _fan_class(srf)
    ox, oy = srf.origin
    ux, uy = srf.u
    nx, ny = srf.n
    half0 = srf.half_lo + srf.divergence * d0
    base = srf.d_lo + d0                    # metres beyond the runway END
    n_st = max(2, int(math.ceil(2.0 * srf.half_lo
                                / CLEARANCE_STATION_STEP_M)) + 1)
    stations, outwards = [], []
    for t in np.linspace(-1.0, 1.0, n_st):
        q = float(t) * half0
        stations.append((ox + ux * base + nx * q, oy + uy * base + ny * q))
        k = float(t) * srf.divergence
        outwards.append((ux + nx * k, uy + ny * k))

    def ceiling_offset(d: float) -> Optional[float]:
        # The law itself, on the fan centreline (flat transversely).  The
        # ``_LAW_EPS_M`` nudge keeps the inner edge itself — where the
        # law's own domain test is strict — inside the domain.
        return ols_approach_ceiling(
            code, cls, max(base + float(d), srf.d_lo + _LAW_EPS_M), 0.0)

    return stations, [srf.anchor] * n_st, outwards, ceiling_offset


def _slab_caps(srf: _Surface, d0: float, cap: float, n_st: int, cells):
    """Per-station reach for one slab: ``cap`` where the station's ray
    passes an ADMITTED penetration cell inside this slab, ``0.0``
    elsewhere.

    ``_build_cut_bands`` skips a zero-reach station outright but keeps it
    in the station SEQUENCE, so the shared daylight bench still sees the
    true frontage geometry — which is why this scopes by reach rather than
    by dropping stations.  Islands-only emission and the build-time bound
    both come from here: an airport whose penetration is one knoll marches
    a few dozen rays over a couple of slabs, not thousands over twenty.
    """
    if cells is None or len(cells) == 0:
        return [0.0] * n_st
    pts = np.asarray(cells, dtype=float)
    ox, oy = srf.origin
    ux, uy = srf.u
    nx, ny = srf.n
    along = (pts[:, 0] - ox) * ux + (pts[:, 1] - oy) * uy
    lateral = (pts[:, 0] - ox) * nx + (pts[:, 1] - oy) * ny
    lo = srf.d_lo + d0 - _STATION_MARGIN_M
    hi = srf.d_lo + d0 + cap + _STATION_MARGIN_M
    if srf.kind == "transitional":
        inside = ((lateral >= lo) & (lateral <= hi)
                  & (along >= srf.along_lo - _STATION_MARGIN_M)
                  & (along <= srf.along_hi + _STATION_MARGIN_M))
        span = max(1e-6, srf.along_hi - srf.along_lo)
        idx = (along[inside] - srf.along_lo) / span * (n_st - 1)
        margin_idx = _STATION_MARGIN_M / span * (n_st - 1)
    else:
        half = (srf.half_lo
                + srf.divergence * np.maximum(along - srf.d_lo, 0.0))
        inside = (along >= lo) & (along <= hi) & (np.abs(lateral) <= half)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = lateral / np.maximum(half, 1e-6)
        idx = (t[inside] + 1.0) / 2.0 * (n_st - 1)
        margin_idx = (_STATION_MARGIN_M
                      / np.maximum(half[inside], 1.0)) / 2.0 * (n_st - 1)
    if idx.size == 0:
        return [0.0] * n_st
    keep = np.zeros(n_st, dtype=bool)
    a = np.floor(np.maximum(idx - margin_idx, 0.0)).astype(int)
    b = np.ceil(np.minimum(idx + margin_idx, n_st - 1)).astype(int)
    for lo_i, hi_i in zip(np.atleast_1d(a), np.atleast_1d(b)):
        keep[lo_i:hi_i + 1] = True
    return [cap if k else 0.0 for k in keep]


def _refused_block(grid: _Grid):
    """Union of the REFUSED cells' footprints — ground this law has
    refused and must therefore not touch.  A piece that merely grazes a
    refused mountain is differenced against it."""
    if not grid.refused.any():
        return None
    ii, jj = np.nonzero(grid.refused)
    hx, hy = 0.5 * grid.dx_m, 0.5 * grid.dy_m
    boxes = [box(float(grid.X[i, j]) - hx, float(grid.Y[i, j]) - hy,
                 float(grid.X[i, j]) + hx, float(grid.Y[i, j]) + hy)
             for i, j in zip(ii, jj)]
    try:
        return unary_union(boxes)
    except _GEOM_EXC:
        return None


def emit_ols_cuts(layout: PavementLayout, dem, tile_lat: int, tile_lon: int,
                  source_runways=None) -> int:
    """Emit OLS terrain-penetration cuts.  Mutates ``layout.shapes``;
    returns the number of shapes emitted.

    No-op returning 0 when ``config.OLS_CUT_ENABLED`` is False or ``dem``
    is None — the gate is read at CALL time, so the module is byte-inert
    off even once it is imported.

    Ordering contract for the caller: run this AFTER the runway-end
    skirts, the RESA cut and the adjacent-ground bands, so all of them are
    in the static block these pieces clip against.
    """
    if not _config.OLS_CUT_ENABLED or dem is None:
        return 0
    if layout is None or getattr(layout, "anchor", None) is None:
        return 0
    scene = _Scene(layout, dem, tile_lat, tile_lon, source_runways)
    islands, grid = _prescan(scene)
    if grid is None:
        return 0
    admitted_cells = [xy for isl in islands if not isl["refused"]
                      for xy in isl["cells"]]
    if not admitted_cells:
        return 0
    try:
        admitted_tree = STRtree([Point(x, y) for x, y in admitted_cells])
    except _GEOM_EXC:
        return 0
    cell_radius = 0.5 * math.hypot(grid.dx_m, grid.dy_m)
    refused_block = _refused_block(grid)

    # Static block: EVERY existing shape, clipped EXACTLY (weld ruling
    # 2026-07-09 — a buffered standoff leaves a groove of raw DEM that
    # renders as a knife-edge wall).  The airport BOUNDARY is deliberately
    # NOT a clip: an OLS lives outside the fence by nature.
    #
    # Indexed rather than pre-unioned: a whole-airport ``unary_union`` is
    # ~0.2 s at a 3 500-shape airport and every OLS piece is a few hundred
    # square metres, so each piece is differenced against only the shapes
    # its own bbox reaches (the ``_nearby_static_polys`` pattern).  Same
    # result, exact clip either way.
    shape_polys = [s.polygon for s in layout.shapes
                   if s.polygon is not None and not s.polygon.is_empty]
    static_polys = shape_polys

    # SURFACE ROAD / RAILWAY / WATER CORRIDORS (owner report 2026-07-25).
    # The runway-end skirt has masked these since 2026-07-05 — "the ground
    # the runway-end skirt must not fill over" — and the OLS spec said to
    # inherit the same clamp for the fan.  It was not built, so the OLS cut
    # was the ONLY terrain law in the subsystem that ignored real
    # infrastructure.
    #
    # WHY IT CANNOT BE DETECTED FROM THE DEM (the owner's point, measured
    # at SPJC 16R): the airport-smoothed DEM does not CONTAIN the road cut.
    # A transect across a cutting 210 m off the 16R end reads 12.91-13.26 m
    # flat over ±80 m — the smoothing (radius 16 px, 100 % inset coverage)
    # erased it.  So the terrain scan sees a plateau at 13.19 m, breaches
    # the 9.60 m ceiling by 3.59 m, and lawfully cuts to 9.60 — which sits
    # ABOVE the real road deck and renders as a fill burying the road.
    # Sampling the DEM harder cannot fix this: the feature is not in the
    # raster.  The vector corridor is the only thing that knows the road is
    # there, which is exactly why the skirt uses it.
    #
    # Masked (not merely clipped-against) so the cut is ABSENT over the
    # corridor rather than welded to its edge: the corridor keeps its own
    # embankment, as it does for the skirt.  ONE source with the skirt and
    # the verification reader — ``clearance._surface_road_corridors``.
    try:
        from .clearance import _surface_road_corridors
        _road_block = _surface_road_corridors(layout, layout.ll_to_m)
    except (_GEOM_EXC + (ImportError, AttributeError, TypeError)):
        _road_block = None
    if _road_block is not None and not _road_block.is_empty:
        static_polys = list(shape_polys) + [_road_block]

    try:
        static_tree = STRtree(static_polys) if static_polys else None
    except _GEOM_EXC:
        static_tree = None

    emitted = 0
    emitted_pieces: list = []
    emitted_shapes: list = []
    for srf in scene.surfaces:
        for d0, cap in _surface_slabs(srf):
            if srf.kind == "transitional":
                stations, alts, outwards, ceiling_offset = _flank_slab(
                    srf, d0)
            else:
                stations, alts, outwards, ceiling_offset = _fan_slab(srf, d0)
            caps = _slab_caps(srf, d0, cap, len(stations), admitted_cells)
            if not any(c > 0.0 for c in caps):
                continue
            bands = _build_cut_bands(
                stations, alts, outwards, caps, ceiling_offset, set(),
                OLS_OBSTRUCTION_THRESHOLD_M, CLEARANCE_STATION_STEP_M,
                grid.scan_alt)
            for ring, _band_alts in bands:
                if len(ring) < 3:
                    continue
                try:
                    poly = Polygon(ring + [ring[0]])
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                except _GEOM_EXC:
                    continue
                if poly.is_empty or poly.geom_type not in ("Polygon",
                                                           "MultiPolygon"):
                    continue
                # ISLAND SCOPING, in lockstep with the pre-scan: a band is
                # kept only where it actually covers an ADMITTED
                # penetration cell.  Refused islands never appear here, so
                # a refused mountain emits nothing at all.
                try:
                    if len(admitted_tree.query(
                            poly.buffer(cell_radius))) == 0:
                        continue
                except _GEOM_EXC:
                    continue
                for piece in _clipped_pieces(poly, static_polys, static_tree,
                                             emitted_pieces, refused_block):
                    coords = _open_coords(piece)
                    if len(coords) < 3:
                        continue
                    vals = _value_ring(scene, srf, coords)
                    if vals is None:
                        continue
                    shape = BuiltShape(
                        polygon=piece, role=ROLE_OLS_CUT, ref=srf.ref,
                        node_altitudes=vals + [vals[0]])
                    layout.shapes.append(shape)
                    emitted += 1
                    emitted_pieces.append(piece)
                    emitted_shapes.append(shape)
    # ROAD REGRADE (config.OLS_ROAD_REGRADE_ENABLED): a surface road
    # whose corridor crosses an admitted island is regraded THROUGH the
    # cut instead of standing on its masked-out DEM embankment.  Decks
    # clip against the SHAPES-ONLY static set (``shape_polys``) — the
    # corridor mask itself must not erase them — and against the pieces
    # already emitted, so bands and decks never overlap.
    if _config.OLS_ROAD_REGRADE_ENABLED:
        try:
            deck_tree = STRtree(shape_polys) if shape_polys else None
        except _GEOM_EXC:
            deck_tree = None
        road_shapes = _emit_road_regrades(
            scene, grid, layout, admitted_tree, admitted_cells,
            cell_radius, shape_polys, deck_tree, emitted_pieces,
            refused_block, standdown_block=_runway_strip_standdown(layout))
        emitted += len(road_shapes)
        emitted_shapes.extend(road_shapes)
    _decimate_ols_group(layout, emitted_shapes)
    return emitted


def _decimate_ols_group(layout: PavementLayout, emitted_shapes: list) -> int:
    """TRIANGLE DIET (spec emission step 5) — 3D-collinear decimation over
    the OLS group, the adjacent-ground band pattern verbatim.

    OLS is by area the largest law in the repo, and its surfaces are
    ANALYTIC PLANES: post-snap, every vertex of a fully-penetrating run
    sits exactly on the ceiling plane, so a marched 5 m station grid
    collapses to the few vertices that actually carry the piece's shape.
    The pipeline's layout-wide ``decimate_emit_nodes`` has already run by
    the time this emitter is called, so without this pass the OLS rows
    reach the triangulator undecimated.

    WELD PROTECTION (2026-07-09 ruling): OLS pieces are clipped EXACTLY
    against every existing shape, so a piece's ring can TRACE a foreign
    constrained edge coordinate-exactly.  Chord-cutting such a vertex
    diverges the two chains by up to ``XY_TOL_M`` and mints the
    near-parallel sliver pair Ruppert refinement explodes on — so a vertex
    on a non-group boundary is force-kept (keeping it is triangle-free: a
    vertex on a constrained edge splits that edge anyway).

    Returns the number of vertices removed; logs one forensics line.
    """
    if not emitted_shapes:
        return 0
    from shapely.geometry import box as _box
    _emitted_ids = {id(es) for es in emitted_shapes}
    _static_exteriors = [s.polygon.exterior for s in layout.shapes
                         if s.polygon is not None and not s.polygon.is_empty
                         and s.polygon.geom_type == "Polygon"
                         and id(s) not in _emitted_ids]
    try:
        _ext_tree = STRtree(_static_exteriors) if _static_exteriors else None
    except _GEOM_EXC:
        _ext_tree = None

    def _on_foreign_boundary(x, y):
        if _ext_tree is None:
            return False
        p = Point(x, y)
        try:
            cand = _ext_tree.query(
                _box(x - 0.06, y - 0.06, x + 0.06, y + 0.06))
        except _GEOM_EXC:
            return False
        for gi in cand:
            try:
                if _static_exteriors[int(gi)].distance(p) <= 0.05:
                    return True
            except _GEOM_EXC:
                continue
        return False

    before = sum(len(_open_coords(s.polygon)) for s in emitted_shapes)
    removed = decimate_shape_group(emitted_shapes, Z_TOL_BOUNDARY_M,
                                   protect_predicate=_on_foreign_boundary)
    after = sum(len(_open_coords(s.polygon)) for s in emitted_shapes)
    # Fan-triangulation proxy for the triangle audit: an n-gon is n-2.
    tri_before = max(0, before - 2 * len(emitted_shapes))
    tri_after = max(0, after - 2 * len(emitted_shapes))
    try:
        import O4_UI_Utils as UI
        UI.vprint(1, f"  [ols] triangle diet: {len(emitted_shapes)} piece(s) "
                     f"{before} -> {after} node(s) (removed {removed} "
                     f"3D-collinear vertex(es), ±{Z_TOL_BOUNDARY_M} m); "
                     f"fan triangles {tri_before} -> {tri_after}.")
    except Exception:
        pass
    return removed


def _fan_class(srf: _Surface) -> str:
    """The approach class of the end a fan surface belongs to."""
    rw = srf.runway
    return rw.class_a if srf.desig == rw.desig_a else rw.class_b


def _clipped_pieces(poly, static_polys, static_tree, emitted_pieces,
                    refused_block):
    """The surviving pieces after the exact clips: every existing shape,
    every already-emitted OLS piece (first wins — no self-overlap) and
    every refused island's footprint.

    The clips are EXACT differences (no buffered standoff — the weld
    ruling); only the SELECTION of operands is indexed, so shapes the
    piece cannot reach are skipped rather than unioned."""
    blockers = []
    if static_tree is not None:
        try:
            blockers.extend(static_polys[int(i)]
                            for i in static_tree.query(poly))
        except _GEOM_EXC:
            blockers.extend(static_polys)
    else:
        blockers.extend(static_polys)
    bounds = poly.bounds
    for p in emitted_pieces:
        b = p.bounds
        if (b[0] <= bounds[2] and b[2] >= bounds[0]
                and b[1] <= bounds[3] and b[3] >= bounds[1]):
            blockers.append(p)
    if refused_block is not None:
        blockers.append(refused_block)
    for blocker in blockers:
        if poly is None or poly.is_empty:
            break
        try:
            if poly.intersects(blocker):
                poly = poly.difference(blocker)
        except _GEOM_EXC:
            return []
    if poly is None or poly.is_empty:
        return []
    parts = ([poly] if poly.geom_type == "Polygon"
             else [g for g in getattr(poly, "geoms", [])
                   if g.geom_type == "Polygon"])
    return [p for p in parts if p.area >= _MIN_PIECE_AREA_M2]


def _value_ring(scene: _Scene, srf: _Surface, coords):
    """Per-vertex altitudes of one emitted piece — ``min(ceiling, DEM)``,
    with the spec's SNAP-TO-BOUND (emission step 5).

    CUT-ONLY BY CONSTRUCTION: never above the DEM (so this law can never
    fill) and never above the composed OLS ceiling (so a corner claimed by
    both surfaces takes the lower one).  Clip-introduced vertices are
    valued ANALYTICALLY, exactly like the runway-end skirt's strips, so
    clipping may introduce vertices freely.

    THE QUANTUM (2026-07-25).  These values were rounded to 0.1 m, which
    quantizes a 2 % plane into 5 m treads — up to 5 cm of pure emit error
    against the law surface, on the law with the largest area in the repo,
    and exactly the "0.1 m quantization stairs" ``emit_decimate``'s own
    module doc names as the V15 waviness root cause.  A penetrating vertex
    now emits the ANALYTIC ceiling at a 1 cm quantum, so the emitted
    surface reproduces the plane rather than a staircase of it.

    (Honest scope: measured on synthetic planar fans the quantum alone
    moves the DECIMATED node count by only a few per cent either way —
    a 0.1 m staircase happens to fit inside the ±0.1 m boundary Z band the
    diet runs at, so it decimates about as well as the true plane.  The
    triangle win is :func:`_decimate_ols_group`, which did not exist; this
    change is about accuracy, and about making the snap below MEAN
    something — snapping to ``round(ceiling, 1)`` is not snapping to the
    bound.)

    SNAP-TO-BOUND: a vertex riding the DEM within ``_CORRIDOR_SNAP_TOL_M``
    (0.15 m — the adjacent-ground corridor's own constant, imported not
    re-declared) BELOW the ceiling takes the ceiling instead, so the
    fringe of an island where the DEM grazes the surface does not sprinkle
    sub-decimetre jitter through an otherwise planar cut.  Same trade the
    corridor bands make, same magnitude, and it is a CUT law's only
    tolerated upward move.
    """
    xs = np.array([c[0] for c in coords], dtype=float)
    ys = np.array([c[1] for c in coords], dtype=float)
    ceil = scene.composed_ceiling(xs, ys, own=srf)
    out = []
    for i in range(len(coords)):
        c = float(ceil[i])
        d = scene.sample_dem(float(xs[i]), float(ys[i]))
        if math.isnan(c):
            if d is None:
                return None
            out.append(round(float(d), 2))
            continue
        if d is None or float(d) >= c - _CORRIDOR_SNAP_TOL_M:
            # Penetrating (DEM above the surface) or grazing it within
            # the snap band: emit the ANALYTIC ceiling, unquantized bar
            # the 1 cm emit quantum.  This is the planar run decimation
            # exists to collapse.
            out.append(round(c, 2))
            continue
        out.append(round(float(d), 2))
    return out


# ──────────────────────────────────────────────────────────────────
# Road regrade through the cut (config.OLS_ROAD_REGRADE_ENABLED)
# ──────────────────────────────────────────────────────────────────
#: Ref tag on regraded road half-shapes (role ``service_junction`` — a
#: graded pavement role, so ``check_grade`` validates them under the
#: service-road rules; the ref keeps them identifiable as this law's).
REF_ROAD = "ols_road"

# A deck run is emitted only where the graded profile cuts below the DEM
# by more than this; the first station back at (or within this of) the
# DEM is where the deck ends and the road returns to its own ground.
# Implementation epsilon, not a rule value.
_ROAD_REGRADE_MIN_CUT_M = 0.05


def _road_regrade_profile(ss, bound, valid, grade):
    """Grade-capped LOWER ENVELOPE of ``bound`` over stations ``ss``:
    ``z(s) = min over t of (bound(t) + grade * |s - t|)`` within each
    contiguous ``valid`` segment — one forward plus one backward pass
    computes it exactly.  Cut-only by construction (``z <= bound``
    everywhere), and wherever the profile is below the bound on either
    side of a station its longitudinal grade is exactly capped."""
    z = np.asarray(bound, dtype=float).copy()
    n = len(z)
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            z[i] = min(z[i], z[i - 1] + grade * (ss[i] - ss[i - 1]))
    for i in range(n - 2, -1, -1):
        if valid[i] and valid[i + 1]:
            z[i] = min(z[i], z[i + 1] + grade * (ss[i + 1] - ss[i]))
    return z


def _near_tile_seam(scene: _Scene, x: float, y: float) -> bool:
    """True when local ``(x, y)`` lies within the tile-cut standoff of the
    CURRENT TILE's integer boundary (or outside the tile).  A deck node
    below the DEM at the seam is the exact wall the island seam refusal
    exists to prevent, and like an OLS cut node it cannot be DEM-pinned
    without un-grading the road — so a run is broken before the seam and
    the blend refusal (below) decides its fate."""
    lat = scene.lat0 + math.degrees(y / R_EARTH)
    lon = scene.lon0 + math.degrees(x / (R_EARTH * scene.cos0))
    m_per_deg = math.radians(1.0) * R_EARTH
    margin_lat = (TILE_CUT_HALF_WIDTH_M + CLEARANCE_STATION_STEP_M) / m_per_deg
    margin_lon = margin_lat / max(scene.cos0, 1e-6)
    return (lat < scene.tile_lat + margin_lat
            or lat > scene.tile_lat + 1 - margin_lat
            or lon < scene.tile_lon + margin_lon
            or lon > scene.tile_lon + 1 - margin_lon)


class NonFiniteRoadAltitude(AssertionError):
    """A road-regrade half-shape was about to carry a non-finite vertex
    altitude.  Raised LOUDLY (production, ungated): a NaN/inf altitude is
    not a defect the validator should have to discover — it mints
    ``inf``-graded violations, poisons every downstream statistic, and
    there is no lawful "off" behaviour to preserve."""


def _nonfinite_road_vals_msg(way_id, sgn, lo, hi, ss, valid, invalid_cause,
                             coords, vals, piece) -> str:
    """Name the piece, the stations, and WHICH invalidity cause fired.

    The three causes are the only ways a station can be invalid
    (:func:`_emit_road_regrades` station loop): ``sample_dem is None``
    (DEM hole), ``_near_tile_seam`` (tile-cut standoff), ``grid.refused``
    (refused OLS cell).  Reported for the offending span, so the answer
    is read off production's own output instead of reconstructed."""
    bad = [k for k, v in enumerate(vals) if not math.isfinite(v)]
    inside = [(i, invalid_cause[i]) for i in range(lo, hi + 1)
              if not valid[i]]
    census: dict = {}
    for _i, c in inside:
        census[c] = census.get(c, 0) + 1
    try:
        bnds = tuple(round(float(b), 1) for b in piece.bounds)
    except Exception:
        bnds = None
    head = (f"OLS road regrade emitted {len(bad)} non-finite vertex "
            f"altitude(s) of {len(vals)} on way {way_id!r} "
            f"side {'+' if sgn > 0 else '-'}: piece bounds {bnds}, "
            f"span stations [{lo}, {hi}] "
            f"s=[{float(ss[lo]):.1f}, {float(ss[hi]):.1f}] m.")
    v_lines = "; ".join(
        f"vertex {k} @ ({coords[k][0]:.1f},{coords[k][1]:.1f}) = {vals[k]}"
        for k in bad[:5])
    if inside:
        cause = (f"INVALID stations INSIDE the span: "
                 f"{[i for i, _c in inside][:12]} "
                 f"(causes {census}) — the span grew over invalid ground.")
    else:
        cause = ("NO invalid station inside the span — the non-finite "
                 "value did not come from the +inf station sentinel; "
                 "look at the outer-edge profile / interpolation.")
    return f"{head}  {v_lines}.  {cause}"


def _runway_strip_standdown(layout: PavementLayout):
    """The RUNWAY-STRIP footprint the road deck stands down over, or ``None``.

    HECA round 5 item 1 (owner sim read of 1.0.265; spec
    ``docs/specs/heca-round5-drainage-and-ramps-spec.md``): *"the runway
    family is aircraft-transit — NOTHING crosses it carrying its own
    elevation authority … at a runway crossing the ols_road/drainage
    corridor takes the RUNWAY's surface exactly (weld, canonical identity,
    zero tear rows), or STANDS DOWN OVER THE STRIP."*  This is the second
    branch, and it needs no geometry of its own: the footprint is a
    STANDING law object (``adjacent_ground.runway_strip_lateral_zone``,
    rings from ``grade_law.runway_strip_lateral_footprint_ring``, grouped
    by runway ``ref``) — the same family of footprints the
    lateral-contiguity law's clause (5) already yields to ("the
    runway-strip footprint law supersedes inside strips").
    ``require_gate=False`` for the same reason clause (5) passes it: this
    law needs the GEOMETRY, under its own gate.

    THE SCOPE IS THE **LATERAL** STRIP — the rectangles BESIDE the runway,
    between its ends (``runway_strip_lateral_zone``, the §2 abeam law's
    own domain, built from the same law function and the same runway
    grouping as the wall keepout).  That is where the measured defect is:
    the deck rode over the adjacent-ground bands flanking runway 05C/23C.
    The END corridors are deliberately NOT in it — the SPJC-16R approach
    fan this whole emitter exists for lies past a runway END, and taking
    the wall keepout instead (which extends 240 m beyond each end) would
    stand the feature down at the very site it was built for.

    ``None`` when the gate is off, when the layout carries no runway, or
    when the footprint cannot be built — in every one of those the deck
    emits exactly as it did before this round.
    """
    if not getattr(_config, "OLS_ROAD_RUNWAY_STANDDOWN", True):
        return None
    try:
        from .adjacent_ground import runway_strip_lateral_zone
        block = runway_strip_lateral_zone(layout, require_gate=False,
                                          prepared=False)
    except (_GEOM_EXC + (ImportError, AttributeError, TypeError)):
        return None
    if block is None or getattr(block, "is_empty", True):
        return None
    return block


def _emit_road_regrades(scene: _Scene, grid: _Grid, layout: PavementLayout,
                        admitted_tree, admitted_cells, cell_radius: float,
                        shape_polys, deck_tree, emitted_pieces,
                        refused_block, standdown_block=None):
    """Regrade surface roads through the cut (owner direction 2026-07-28,
    SPJC 16R).  Returns the list of emitted deck shapes.

    The corridor mask makes the banded cut ABSENT over surface road
    corridors, which is right everywhere except across an admitted
    penetration island: there the mask preserves the very hill the law
    cuts back, as a road-width causeway metres proud of the fan carrying
    grades no ground vehicle route allows (measured SPJC 16R: 12.8 % and
    13.2 % on the two flanking service roads, against the 5 %
    ``SERVICE_ROAD_MAX_GRADE``).

    THE LAW (owner ruling 2026-07-28).  The OSM way IS the road spine.
    Along each mapped surface highway way whose corridor reaches an
    admitted island: stations at ``CLEARANCE_STATION_STEP_M``;
    per-station spine bound ``min(DEM, composed OLS ceiling)`` where the
    ceiling governs near an admitted cell, plain DEM elsewhere; spine
    profile = the grade-capped lower envelope of that bound
    (:func:`_road_regrade_profile`, cap ``SERVICE_ROAD_MAX_GRADE`` — the
    ground-vehicle grade rule, imported not re-declared; the envelope is
    grade-Lipschitz EVERYWHERE, so the profile maintains grade through
    the OLS and cuts both rises and over-steep descents).

    EMISSION: TWO MATCHING ``service_junction`` HALF-SHAPES, one each
    side of the spine, ``half_w`` (½ carriageway + shoulder — the mask's
    own width law) outward.  Both halves share the spine chain
    coordinate-exactly with identical spine altitudes, so they weld into
    one road surface, and each carries its own outer-edge profile: the
    grade-capped envelope of the terrain bound sampled along the offset
    edge, clamped within ``SERVICE_ROAD_MAX_TRANSVERSE * half_w`` of the
    spine — the service-road LATERAL grade rule, enforced by
    construction (and by ``check_grade``, since ``service_junction`` is
    a graded pavement role).  A clip-introduced vertex is valued
    analytically by its ``(s, d)`` position: spine profile at ``d = 0``
    blending linearly to the outer profile at ``d = half_w``.

    EXTENT: the graded segment follows the spine through the whole OLS
    crossing and AT LEAST ``OLS_ROAD_REGRADE_FOLLOW_M`` (100 m) past the
    OLS surface footprint in both directions, then extends further to
    the profile's own blend points, so both ends land ON the DEM.
    Clamped at the way's end when the way stops sooner — lawful only if
    that end is already at the DEM.

    REFUSALS, in the island-refusal spirit:

    * BLEND refusal — a span that cannot return to the DEM inside its
      own way (it reaches the way's end, refused ground, missing DEM, or
      the tile seam, :func:`_near_tile_seam`, while still cut) is
      refused whole: a road ending mid-cut would mint the wall this
      module exists to remove.
    * DEPTH refusal — a span needing a refused-class cut anywhere
      (``grade_law.ols_island_refused``, same helper, lockstep) is
      refused whole (a road trench through a real mountain is obstacle
      removal, not DEM repair).
    * Railway ways are out of scope (rail grade law is far stricter than
      the road law; the embankment behavior stands) and tunnel-tagged
      ways stay excluded exactly as in the mask.

    Halves difference against the SHAPES-ONLY static set plus every
    piece already emitted (bands cannot overlap a corridor, so band/deck
    overlap is impossible by construction; the two halves meet only on
    the zero-area spine line; overlap between two parallel ways resolves
    first-wins in deterministic way order).
    """
    from shapely.ops import substring
    from .bridges import (_load_tunnel_road_network,
                          _carriageway_width_from_tags)
    from .clearance import _SKIRT_ROAD_SHOULDER_M
    try:
        nodes_r, ways_r, _big_ids, _ntags = _load_tunnel_road_network(layout)
    except (_GEOM_EXC + (ImportError, AttributeError, TypeError)):
        return []
    if not ways_r:
        return []
    step = CLEARANCE_STATION_STEP_M
    grade = float(_config.SERVICE_ROAD_MAX_GRADE)
    shapes_out: list = []
    n_ways = n_spans = n_blend_refused = n_depth_refused = 0
    n_standdown = n_standdown_st = 0
    worst_cut = 0.0
    # ── THE RUNWAY-STRIP STAND-DOWN (HECA round 5 item 1) ─────────────
    # The deck already clips against every layout shape, so it never
    # OVERLAPS the runway; what it did was ride its own DEM-derived
    # profile right up to the runway's edge INSIDE the strip (measured at
    # HECA: the two ols_road halves at 116.4-118.85 over a runway surface
    # at 109.3-111.2), where the adjacent-ground bands weld to it and
    # tear against each other (5.10 m over 0.19 m on the owner's line).
    #
    # THE SPAN REFUSES WHOLE — the module's own refusal idiom, beside
    # BLEND and DEPTH.  Two weaker forms were built and MEASURED WORSE on
    # this lane, and both are recorded here so they are not re-tried:
    #   * marking the strip stations INVALID truncated the span and the
    #     standing blend refusal then took the whole thing anyway, but it
    #     also took spans that merely reach the strip with a stub;
    #   * CLIPPING the emitted pieces against the strip left the deck's
    #     own (s, d) blend cut open at the boundary: HECA gained a
    #     ``road_cross_section`` row of 7.330 m at 733 % inside the deck
    #     piece -13742 and a cluster of 7.3 m mid-edge steps against
    #     service_junction -12157.  A clip that mints a 7 m corner where
    #     a 5 m tear was is not a fix.
    # A deck may not stand PART of the way across a runway strip, so the
    # unit of the law is the SPAN: if any of its stations lies in the
    # lateral strip the span is not emitted at all, and the road keeps
    # the DEM embankment the pre-regrade behaviour gave it there.
    _strip_prep = None
    if standdown_block is not None:
        try:
            _strip_prep = prep(standdown_block)
        except _GEOM_EXC:                                  # pragma: no cover
            _strip_prep = None
    # O(1) bbox prefilter before any per-way buffer: the road caches can
    # hold thousands of ways and ``buffer()`` is the expensive step of
    # the quick reject below.  40 m covers the widest carriageway the
    # width law can return (40 m sanity clamp) at half width + shoulder.
    _adm_pts = np.asarray(admitted_cells, dtype=float)
    _margin = 40.0 + cell_radius
    _adm_bbox = (_adm_pts[:, 0].min() - _margin,
                 _adm_pts[:, 1].min() - _margin,
                 _adm_pts[:, 0].max() + _margin,
                 _adm_pts[:, 1].max() + _margin)
    for way_id, node_refs, tags in sorted(ways_r, key=lambda w: str(w[0])):
        highway_type = tags.get("highway")
        if highway_type is None:
            continue
        if tags.get("tunnel", "no") not in ("", "no"):
            continue
        pts = [layout.ll_to_m(*nodes_r[n]) for n in node_refs
               if n in nodes_r]
        if len(pts) < 2:
            continue
        try:
            line = LineString(pts)
        except _GEOM_EXC:
            continue
        if line.length < 2.0 * step:
            continue
        lb = line.bounds
        if (lb[2] < _adm_bbox[0] or lb[0] > _adm_bbox[2]
                or lb[3] < _adm_bbox[1] or lb[1] > _adm_bbox[3]):
            continue
        try:
            half_w = (0.5 * _carriageway_width_from_tags(
                highway_type, tags, 6.0) + _SKIRT_ROAD_SHOULDER_M)
        except _GEOM_EXC:
            continue
        # Quick reject: only ways whose corridor reaches an admitted cell.
        try:
            if len(admitted_tree.query(
                    line.buffer(half_w + cell_radius))) == 0:
                continue
        except _GEOM_EXC:
            continue
        n_ways += 1
        n_st = int(math.ceil(line.length / step)) + 1
        ss = np.linspace(0.0, float(line.length), n_st)
        st = [line.interpolate(float(s)) for s in ss]
        xs = np.array([p.x for p in st], dtype=float)
        ys = np.array([p.y for p in st], dtype=float)
        ceil_v = scene.composed_ceiling(xs, ys)
        dem_v = np.full(n_st, np.nan, dtype=float)
        valid = np.zeros(n_st, dtype=bool)
        near_adm = np.zeros(n_st, dtype=bool)
        #: HECA round 5 item 1 — stations standing in a runway's LATERAL
        #: strip.  Consumed at SPAN level (the whole span refuses).
        in_strip = np.zeros(n_st, dtype=bool)
        # WHY each invalid station is invalid — read only by the
        # finiteness assertion below, so a NaN altitude can name its own
        # cause instead of being guessed at offline.  The causes are
        # disjoint and the first three are tested in the SAME short-circuit
        # order as before; the RUNWAY-STRIP stand-down (HECA round 5 item
        # 1) is asked LAST, so no existing cause changes hands.
        invalid_cause: list = [None] * n_st
        for i in range(n_st):
            x, y = float(xs[i]), float(ys[i])
            d = scene.sample_dem(x, y)
            if d is None:
                invalid_cause[i] = "sample_dem is None"
                continue
            if _near_tile_seam(scene, x, y):
                invalid_cause[i] = "_near_tile_seam"
                continue
            ij = grid.index(x, y)
            if ij is not None and grid.refused[ij]:
                invalid_cause[i] = "grid.refused"
                continue
            # ── THE RUNWAY-STRIP STAND-DOWN (HECA round 5 item 1) ─────
            # Inside the runway's LATERAL strip the strip's own law owns
            # the ground and nothing crosses the runway family carrying
            # its own elevation authority, so the deck has no domain
            # here.  The station stays VALID — the profile is computed
            # exactly as before, so a span that never touches the strip
            # is byte-identical — and the mark is consumed at SPAN level
            # below, where the whole span refuses.
            if _strip_prep is not None:
                try:
                    if _strip_prep.covers(Point(x, y)):
                        in_strip[i] = True
                        n_standdown_st += 1
                except _GEOM_EXC:                          # pragma: no cover
                    pass
            valid[i] = True
            dem_v[i] = float(d)
            try:
                near_adm[i] = len(admitted_tree.query(
                    Point(x, y).buffer(cell_radius))) > 0
            except _GEOM_EXC:
                near_adm[i] = False
        if not valid.any():
            continue
        bound = dem_v.copy()
        gov = valid & near_adm & ~np.isnan(ceil_v)
        bound[gov] = np.minimum(bound[gov], ceil_v[gov])
        z = _road_regrade_profile(ss, np.where(valid, bound, np.inf),
                                  valid, grade)
        depth = np.where(valid, dem_v - z, 0.0)
        cut = depth > _ROAD_REGRADE_MIN_CUT_M
        gov_any = ~np.isnan(ceil_v)
        follow_st = int(math.ceil(
            float(_config.OLS_ROAD_REGRADE_FOLLOW_M) / step))
        lat_cap = float(_config.SERVICE_ROAD_MAX_TRANSVERSE) * half_w
        # 1. ANCHORS: contiguous cut runs that actually touch an
        #    admitted cell (island scoping, in lockstep with the bands).
        anchors = []
        i = 0
        while i < n_st:
            if not cut[i]:
                i += 1
                continue
            j = i
            while j + 1 < n_st and cut[j + 1]:
                j += 1
            try:
                probe = substring(
                    line, float(ss[i]), float(ss[j])).buffer(
                        half_w + cell_radius)
                if len(admitted_tree.query(probe)) > 0:
                    anchors.append((i, j))
            except _GEOM_EXC:
                pass
            i = j + 1
        if not anchors:
            continue
        # 2. SPANS: each anchor grows to the contiguous OLS-governed
        #    stretch containing it, follows the spine >= FOLLOW_M past
        #    the OLS both ways (stopping early only at invalid ground),
        #    then extends to the profile's own blend points.
        spans = []
        for a, b in anchors:
            lo, hi = a, b
            gov_idx = np.nonzero(gov_any[a:b + 1])[0]
            if gov_idx.size:
                # ``valid`` guard, in the same idiom as the FOLLOW and
                # blend extensions below: an INVALID station carries the
                # ``+inf`` profile sentinel (:func:`_road_regrade_profile`
                # never propagates across one), and ``depth`` is forced
                # 0.0 there, so an unguarded walk over ``gov_any`` alone
                # could swallow invalid ground, pass the blend refusal on
                # a fake 0.0 depth, and mint ``inf - inf = NaN`` vertex
                # altitudes in the analytic blend.  OLS governance is a
                # property of the CEILING, which exists over ground the
                # DEM/seam/refusal rules exclude.
                g_lo = a + int(gov_idx[0])
                while g_lo - 1 >= 0 and gov_any[g_lo - 1] and valid[g_lo - 1]:
                    g_lo -= 1
                g_hi = a + int(gov_idx[-1])
                while (g_hi + 1 < n_st and gov_any[g_hi + 1]
                       and valid[g_hi + 1]):
                    g_hi += 1
                lo, hi = min(lo, g_lo), max(hi, g_hi)
            for _ in range(follow_st):
                if lo - 1 >= 0 and valid[lo - 1]:
                    lo -= 1
                else:
                    break
            for _ in range(follow_st):
                if hi + 1 < n_st and valid[hi + 1]:
                    hi += 1
                else:
                    break
            while (depth[lo] > _ROAD_REGRADE_MIN_CUT_M
                   and lo - 1 >= 0 and valid[lo - 1]):
                lo -= 1
            while (depth[hi] > _ROAD_REGRADE_MIN_CUT_M
                   and hi + 1 < n_st and valid[hi + 1]):
                hi += 1
            spans.append((lo, hi))
        spans.sort()
        merged = [list(spans[0])]
        for lo, hi in spans[1:]:
            if lo <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        for lo, hi in merged:
            # RUNWAY-STRIP refusal (HECA round 5 item 1), asked FIRST
            # because a span standing in a runway strip has no business
            # being priced for blend or depth at all.
            if bool(in_strip[lo:hi + 1].any()):
                n_standdown += 1
                continue
            # BLEND refusal: both ends must sit ON the DEM.
            if (depth[lo] > _ROAD_REGRADE_MIN_CUT_M
                    or depth[hi] > _ROAD_REGRADE_MIN_CUT_M):
                n_blend_refused += 1
                continue
            d_max = float(depth[lo:hi + 1].max())
            # SAME depth law as the islands (lockstep, not a re-declared
            # number): a span needing a refused-class cut refuses whole.
            if ols_island_refused(d_max):
                n_depth_refused += 1
                continue
            if hi - lo < 2:
                continue
            n_spans += 1
            # 3. Per-side OUTER-EDGE profiles: terrain bound sampled
            #    along the offset edge, grade-capped (same envelope
            #    law), clamped to the lateral rule around the spine.
            span = np.arange(lo, hi + 1)
            z_sp = z[span]
            ss_sp = ss[span]
            txs = np.gradient(xs[span])
            tys = np.gradient(ys[span])
            tl = np.hypot(txs, tys)
            tl[tl == 0] = 1.0
            nxs, nys = -tys / tl, txs / tl        # left normal
            outer_prof = {}
            for sgn in (1.0, -1.0):
                ox = xs[span] + sgn * half_w * nxs
                oy = ys[span] + sgn * half_w * nys
                oceil = scene.composed_ceiling(ox, oy)
                tgt = np.empty(len(span), dtype=float)
                for k in range(len(span)):
                    d = scene.sample_dem(float(ox[k]), float(oy[k]))
                    if d is None:
                        tgt[k] = float(z_sp[k])   # no data: no tilt
                        continue
                    b_ = float(d)
                    if (near_adm[span[k]]
                            and not math.isnan(float(oceil[k]))):
                        b_ = min(b_, float(oceil[k]))
                    tgt[k] = b_
                env = _road_regrade_profile(
                    ss_sp, tgt, np.ones(len(span), dtype=bool), grade)
                outer_prof[sgn] = np.clip(
                    env, z_sp - lat_cap, z_sp + lat_cap)
            # 4. The two matching halves, welded along the spine.
            try:
                sub = substring(line, float(ss[lo]), float(ss[hi]))
                halves = ((1.0, sub.buffer(half_w, single_sided=True)),
                          (-1.0, sub.buffer(-half_w, single_sided=True)))
            except _GEOM_EXC:
                continue
            for sgn, poly in halves:
                try:
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    poly = poly.segmentize(step)
                except _GEOM_EXC:
                    continue
                if poly is None or poly.is_empty:
                    continue
                for piece in _clipped_pieces(poly, shape_polys, deck_tree,
                                             emitted_pieces, refused_block):
                    coords = _open_coords(piece)
                    if len(coords) < 3:
                        continue
                    vals = []
                    for cx, cy in coords:
                        p = Point(cx, cy)
                        try:
                            s_loc = float(sub.project(p))
                            d_sp = min(float(sub.distance(p)), half_w)
                        except _GEOM_EXC:
                            s_loc, d_sp = 0.0, 0.0
                        s_abs = float(ss[lo]) + s_loc
                        zs = float(np.interp(s_abs, ss, z))
                        zo = float(np.interp(
                            s_abs, ss_sp, outer_prof[sgn]))
                        vals.append(round(
                            zs + (d_sp / half_w) * (zo - zs), 2))
                    # FINITENESS ASSERTION (production, ungated): never
                    # emit a non-finite altitude silently.  With the
                    # ``valid`` guard above, every station of a span is
                    # valid and every ``vals`` entry is finite; if that
                    # ever fails, say WHY on the spot.
                    if not all(math.isfinite(v) for v in vals):
                        raise NonFiniteRoadAltitude(
                            _nonfinite_road_vals_msg(
                                way_id, sgn, lo, hi, ss, valid,
                                invalid_cause, coords, vals, piece))
                    shape = BuiltShape(polygon=piece,
                                       role=ROLE_SERVICE_JUNCTION,
                                       ref=REF_ROAD,
                                       node_altitudes=vals + [vals[0]])
                    layout.shapes.append(shape)
                    emitted_pieces.append(piece)
                    shapes_out.append(shape)
                    worst_cut = max(worst_cut, d_max)
    if n_ways:
        try:
            import O4_UI_Utils as UI
            UI.vprint(1, f"  [ols] road regrade: {n_ways} way(s) at "
                         f"admitted island(s) -> {len(shapes_out)} "
                         f"service-road half-shape piece(s) over "
                         f"{n_spans} span(s), worst cut {worst_cut:.2f} m; "
                         f"{n_blend_refused} blend-refused, "
                         f"{n_depth_refused} depth-refused span(s); "
                         f"{n_standdown} span(s) STAND DOWN over a "
                         f"runway's LATERAL strip ({n_standdown_st} "
                         f"station(s) inside one — HECA round 5 item 1: "
                         f"nothing crosses the runway family carrying its "
                         f"own elevation authority).")
        except Exception:
            pass
    return shapes_out
