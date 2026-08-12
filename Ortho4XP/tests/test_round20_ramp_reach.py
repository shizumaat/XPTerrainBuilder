"""Round 20 — the tunnel ramp follows the road and reaches grade.

Two laws, both in ``auto_patch.bridges``:

R20-1 CURVATURE SURVIVES THE WALK.  The surface walk's plan filter was a
15 m SPACING merge — it deleted a vertex for being close to its
neighbour, whatever the road did there (measured at KCLT: OSM node
-75937 deleted, 1.86 m off the chord left behind).  It is now a
DEVIATION filter (``bridges._deviation_filter``), so the retained chain
is within ``_TUNNEL_WALK_DEVIATION_TOL_M`` of EVERY input vertex, and the
rounding-safe segment floor the spacing merge was really buying is
DERIVED from the emitted altitude grid instead of guessed.

R20-2 THE RUN REACHES GRADE.  The run was sized on a PORTAL-LOCAL
ambient at ``TUNNEL_APPROACH_GRADE`` (5 %) while the chain is emitted at
``plan_grade`` (3.5 %), so where the road climbed away from the mouth the
ramp stopped buried (KCLT: 4.26 m below the DEM beside it).  The run now
extends while ``dem_along_walk(s) - elev_low > emit_grade * s`` and ends
where the ramp meets the ground — never SHORTER than R14's minimum
lawful run, and never a declared minimum of its own.

Everything here is headless and synthetic: the road-layer loader and the
DEM sampler are monkeypatched (the fixture idiom of
``tests/test_tunnel_dem_cut_portals.py``), nothing is written, no network
and no X-Plane install are touched.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import box

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import bridges  # noqa: E402
from auto_patch import config  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    PavementLayout,
    ROLE_BOUNDARY,
    ROLE_JUNCTION,
)


# ══════════════════════════════════════════════════════════════════
# R20-1 — the deviation filter
# ══════════════════════════════════════════════════════════════════
class TestDeviationFilterConstants:
    """The rounding-safe floor is DERIVED from the two constants that
    set it, so it can never drift from the emitted precision again."""

    def test_emit_step_matches_what_to_osm_writes(self) -> None:
        # ``layout.to_osm`` writes ``alt_abs`` at ``{:.2f}`` and the ramp
        # quads round their own corner values to 2 dp — 0.01 m, not the
        # 0.1 m the retired spacing merge's comment sized itself against.
        assert bridges._TUNNEL_ALT_EMIT_STEP_M == 0.01

    def test_min_segment_is_derived_not_a_literal(self) -> None:
        assert bridges._TUNNEL_WALK_MIN_SEGMENT_M == pytest.approx(
            bridges._TUNNEL_ALT_EMIT_STEP_M
            / bridges.TUNNEL_RAMP_GRADE_SAFETY_MARGIN)
        # …which is 2 m at the shipped constants.  The point of the twin
        # is the 15 m spacing merge NOT coming back under another name.
        assert bridges._TUNNEL_WALK_MIN_SEGMENT_M == pytest.approx(2.0)
        assert bridges._TUNNEL_WALK_MIN_SEGMENT_M < 15.0

    def test_worst_case_rounding_error_fits_the_safety_margin(self) -> None:
        # One segment's Δe carries at most one grid step of error, so the
        # grade error it adds is step/length.  At the floor that must sit
        # inside the ramp's planning headroom — the whole rationale the
        # spacing merge carried.
        worst_grade_error = (bridges._TUNNEL_ALT_EMIT_STEP_M
                             / bridges._TUNNEL_WALK_MIN_SEGMENT_M)
        assert worst_grade_error <= bridges.TUNNEL_RAMP_GRADE_SAFETY_MARGIN

    def test_tolerance_is_under_the_round_claim(self) -> None:
        assert bridges._TUNNEL_WALK_DEVIATION_TOL_M <= 0.3


class TestDeviationFilter:
    """Deviation decides, spacing does not."""

    def test_drops_a_collinear_node(self) -> None:
        # Three evenly spaced collinear points: the middle one carries no
        # deviation and must go.
        out = bridges._deviation_filter(
            [(0.0, 0.0), (20.0, 0.0), (40.0, 0.0)], 0.25, 2.0)
        assert out == [(0.0, 0.0), (40.0, 0.0)]

    def test_keeps_a_curve_node_the_spacing_merge_deleted(self) -> None:
        # The KCLT shape: a bend node 1.86 m off the chord, only 10 m
        # from its neighbour.  The 15 m SPACING merge deleted it for the
        # spacing; a deviation filter keeps it for the bend.
        pts = [(0.0, 0.0), (10.0, 1.86), (20.0, 0.0)]
        out = bridges._deviation_filter(pts, 0.25, 2.0)
        assert (10.0, 1.86) in out

    def test_keeps_a_whole_run_of_tight_curve_nodes(self) -> None:
        # Five nodes 5 m apart tracing an arc: EVERY one of them would
        # have been deleted by a 15 m spacing merge (only the last
        # survived it), and every one of them carries a bend.
        pts = [(0.0, 0.0), (5.0, 0.6), (10.0, 1.6), (15.0, 3.0),
               (20.0, 4.8), (25.0, 7.0)]
        out = bridges._deviation_filter(pts, 0.25, 2.0)
        assert len(out) >= 4, out

    def test_every_input_vertex_is_within_tolerance_of_the_output(
        self,
    ) -> None:
        # The claim metric of the round: max lateral offset
        # emitted-vs-OSM at every OSM node.
        pts = [(float(i) * 7.0,
                40.0 * math.sin(math.radians(float(i) * 6.0)))
               for i in range(40)]
        out = bridges._deviation_filter(
            pts, bridges._TUNNEL_WALK_DEVIATION_TOL_M,
            bridges._TUNNEL_WALK_MIN_SEGMENT_M)
        assert len(out) < len(pts), "nothing was thinned at all"
        for p in pts:
            assert _distance_to_chain(p, out) <= (
                bridges._TUNNEL_WALK_DEVIATION_TOL_M + 1e-9), p

    def test_endpoints_always_survive(self) -> None:
        pts = [(0.0, 0.0), (3.0, 0.0), (6.0, 0.0), (9.0, 0.0)]
        out = bridges._deviation_filter(pts, 0.25, 2.0)
        assert out[0] == pts[0]
        assert out[-1] == pts[-1]

    def test_no_output_segment_is_shorter_than_the_floor(self) -> None:
        # Deviating nodes 0.5 m apart: the deviation filter WANTS them
        # all, the rounding floor overrules for the sub-2 m ones.
        pts = [(0.0, 0.0)]
        for i in range(1, 21):
            pts.append((0.5 * i, 0.4 if i % 2 else -0.4))
        out = bridges._deviation_filter(
            pts, bridges._TUNNEL_WALK_DEVIATION_TOL_M,
            bridges._TUNNEL_WALK_MIN_SEGMENT_M)
        for a, b in zip(out, out[1:]):
            assert math.dist(a, b) >= (
                bridges._TUNNEL_WALK_MIN_SEGMENT_M - 1e-9), (a, b)

    def test_short_chains_pass_through(self) -> None:
        assert bridges._deviation_filter([(0.0, 0.0)], 0.25, 2.0) == [
            (0.0, 0.0)]
        two = [(0.0, 0.0), (1.0, 0.0)]
        assert bridges._deviation_filter(two, 0.25, 2.0) == two


def _distance_to_chain(pt, chain) -> float:
    best = float("inf")
    for a, b in zip(chain, chain[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-18:
            d = math.dist(pt, a)
        else:
            t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / seg2
            t = max(0.0, min(1.0, t))
            d = math.dist(pt, (a[0] + t * dx, a[1] + t * dy))
        best = min(best, d)
    return best


# ══════════════════════════════════════════════════════════════════
# R20-2 — the run reaches grade
# ══════════════════════════════════════════════════════════════════
ANCHOR_LATITUDE = 35.213
ANCHOR_LONGITUDE = -80.942
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
TILE_LATITUDE = 35
TILE_LONGITUDE = -81

# TWO SURFACES, AS IN PRODUCTION.  ``apt_elev`` comes from the boundary
# ribbon (CIFP-anchored, grade-clamped); the deck reference the bore
# floor is measured from comes from the DEM beside the road.  They are
# different quantities and the scene keeps them apart, seated so the
# gatherer's clearance floor (deck − BRIDGE_ROAD_CLEARANCE_M) and the
# cluster's emit floor (apt_elev − tunnel_depth_m) COINCIDE — which is
# what the owner's KCLT portal measures (206.34 vs 206.36) and what the
# round's reach claim rests on.  Where a field's two floors diverge the
# ramp cannot meet ground however the run is sized; that split is a
# separate defect, deliberately not papered over here.
TUNNEL_DEPTH_DEFAULT_M = 8.0
GROUND_M = 211.4
RIBBON_SURFACE_M = GROUND_M + (
    TUNNEL_DEPTH_DEFAULT_M - float(config.BRIDGE_ROAD_CLEARANCE_M))
EMIT_FLOOR_M = RIBBON_SURFACE_M - TUNNEL_DEPTH_DEFAULT_M
PORTAL_X_M = 60.0
BORE_DEPTH_M = GROUND_M - EMIT_FLOOR_M
EMIT_GRADE = (float(config.TUNNEL_RAMP_MAX_GRADE)
              - bridges.TUNNEL_RAMP_GRADE_SAFETY_MARGIN)
R14_MINIMUM_RUN_M = BORE_DEPTH_M / bridges.TUNNEL_APPROACH_GRADE


def test_scene_seats_the_two_floors_on_one_value() -> None:
    """The scene's premise, asserted rather than assumed."""
    assert EMIT_FLOOR_M == pytest.approx(
        GROUND_M - float(config.BRIDGE_ROAD_CLEARANCE_M))
    assert BORE_DEPTH_M == pytest.approx(
        float(config.BRIDGE_ROAD_CLEARANCE_M))


# The CURVED east approach: OSM nodes 12 m apart, each 1.8 m off the
# chord through its neighbours.  Every one of them is closer to its
# neighbour than the retired 15 m spacing merge's threshold, so that
# merge deleted every other one; every one of them also carries a bend
# far larger than the deviation tolerance, so the deviation filter keeps
# them all.  (The wiggle is deliberate rather than a circular arc: an arc
# tight enough to give this sag would fold the walk back on itself and
# trip ``_walk_surface``'s loop detector.)
_CURVE_NODE_SPACING_M = 12.0
_CURVE_AMPLITUDE_M = 0.9
_CURVE_NODE_COUNT = 14


def _curved_approach_nodes() -> list[tuple[tuple[float, float], float]]:
    """``[((x, y), station_from_portal_m)]`` for the curved approach's
    OSM nodes, in walk order, portal excluded."""
    out = []
    previous = (PORTAL_X_M, 0.0)
    station = 0.0
    for k in range(1, _CURVE_NODE_COUNT + 1):
        pt = (PORTAL_X_M + _CURVE_NODE_SPACING_M * k,
              _CURVE_AMPLITUDE_M * (-1.0 if k % 2 else 1.0))
        station += math.dist(previous, pt)
        out.append((pt, station))
        previous = pt
    return out


def _synthetic_road_network(*, curved: bool) -> tuple[dict, list, set, dict]:
    """A ``tunnel=yes`` way under a taxiway strip with a surface approach
    running ~400 m east of the east portal.

    ``curved=False`` makes that approach STRAIGHT, so ``_emit_chain``'s
    effective-space clamp (which shortens mitred edges on a bend) is the
    identity and the emitted ramp top is the run sizing's own arithmetic,
    not a miter artefact — that is the scene the R20-2 twins measure in.
    ``curved=True`` is the R20-1 scene.
    """
    _to_m, meters_to_lat_lon = bridges._local_meter_projections(ANCHOR)
    nodes_metres = {
        "A": (-PORTAL_X_M, 0.0),
        "M": (0.0, 0.0),
        "B": (PORTAL_X_M, 0.0),
        "W1": (-160.0, 0.0),
        "W2": (-460.0, 0.0),
    }
    east_refs = ["B"]
    if curved:
        for k, (pt, _station) in enumerate(_curved_approach_nodes()):
            nodes_metres[f"C{k}"] = pt
            east_refs.append(f"C{k}")
        nodes_metres["E3"] = (460.0, 0.0)
        east_refs.append("E3")
    else:
        for nid, pt in (("E1", (160.0, 0.0)), ("E2", (260.0, 0.0)),
                        ("E3", (460.0, 0.0))):
            nodes_metres[nid] = pt
            east_refs.append(nid)
    nodes_r = {nid: meters_to_lat_lon(x, y)
               for nid, (x, y) in nodes_metres.items()}
    ways_r = [
        ("TUN", ["A", "M", "B"],
         {"highway": "unclassified", "tunnel": "yes"}),
        ("APPW", ["A", "W1", "W2"], {"highway": "unclassified"}),
        ("APPE", east_refs, {"highway": "unclassified"}),
    ]
    return nodes_r, ways_r, {"TUN"}, {}


def _build_layout() -> PavementLayout:
    layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    layout.shapes.append(BuiltShape(
        polygon=box(-40.0, -200.0, 40.0, 200.0),
        role=ROLE_JUNCTION, ref="taxiway"))
    layout.shapes.append(BuiltShape(
        polygon=box(-100.0, -100.0, 100.0, 100.0),
        role=ROLE_BOUNDARY, ref="airport_boundary",
        node_altitudes=[RIBBON_SURFACE_M] * 5))
    return layout


def _install_scene(monkeypatch, *, climb_rate: float,
                   curved: bool = False) -> PavementLayout:
    """Flat ground over the airport, then ground CLIMBING at
    ``climb_rate`` away from the east portal (negative = falling).

    No cross-road trench anywhere, so ``cut_detected`` is False and the
    synthetic sloped-ramp path — the one R20-2 sizes — is the path taken.
    """
    monkeypatch.setattr(
        bridges, "_load_tunnel_road_network",
        lambda _layout: _synthetic_road_network(curved=curved))
    to_meters, _m2ll = bridges._local_meter_projections(ANCHOR)

    def _fake_sample_dem(_dem, _tile_lat, _tile_lon, lat, lon):
        x_m, _y_m = to_meters(lon, lat)
        beyond = x_m - PORTAL_X_M
        if beyond <= 0.0:
            return GROUND_M
        return GROUND_M + climb_rate * beyond

    monkeypatch.setattr(bridges, "_sample_dem", _fake_sample_dem)
    return _build_layout()


def _east_ramps(layout: PavementLayout) -> list[BuiltShape]:
    """Sloped ramp pieces of the EAST portal cluster (x > 0)."""
    out = []
    for s in layout.shapes:
        if getattr(s, "ref", "") != "tunnel_ramp":
            continue
        if s.altitude_high is None and s.altitude_low is None:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.polygon.centroid.x > 0.0:
            out.append(s)
    return out


def _east_ramp_reach_m(layout: PavementLayout) -> float:
    """How far east of the portal the ramp chain reaches, in metres."""
    reach = 0.0
    for s in _east_ramps(layout):
        for x, _y in s.polygon.exterior.coords:
            reach = max(reach, x - PORTAL_X_M)
    return reach


def _east_ramp_top_m(layout: PavementLayout) -> float:
    return max(float(s.altitude_high) for s in _east_ramps(layout))


class TestRunReachesGrade:
    """The run is sized on the ground along the walk, at the grade the
    chain is emitted with."""

    def test_climbing_ground_extends_the_run_past_the_r14_minimum(
        self, monkeypatch
    ) -> None:
        # Ground climbs 1 %; the ramp climbs 3.5 %.  It closes the
        # clearance depth at 2.5 %/m, so it meets the ground at
        # depth/0.025 — about twice the R14 minimum run.
        climb = 0.01
        layout = _install_scene(monkeypatch, climb_rate=climb)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _east_ramps(layout), "no synthetic ramp was emitted"
        expected = BORE_DEPTH_M / (EMIT_GRADE - climb)
        assert expected > R14_MINIMUM_RUN_M * 1.5   # scene sanity
        assert _east_ramp_reach_m(layout) == pytest.approx(
            expected, abs=12.0)

    def test_the_ramp_top_meets_the_ground_no_cliff(
        self, monkeypatch
    ) -> None:
        climb = 0.01
        layout = _install_scene(monkeypatch, climb_rate=climb)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        top = _east_ramp_top_m(layout)
        ground_at_top = (GROUND_M
                         + climb * _east_ramp_reach_m(layout))
        # The pre-round KCLT defect was a 4.26 m gap here.
        assert abs(ground_at_top - top) <= 0.35, (top, ground_at_top)

    def test_flat_ground_run_is_grade_sized_and_under_200_m(
        self, monkeypatch
    ) -> None:
        # NO 200 m MINIMUM COMES BACK.  On flat ground the run is exactly
        # what the emitted grade needs — depth/3.5 % ≈ 146 m — even
        # though the walk is 400 m long and ``ramp_min_length_m``
        # defaults to 200 m.
        layout = _install_scene(monkeypatch, climb_rate=0.0)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        reach = _east_ramp_reach_m(layout)
        assert reach == pytest.approx(BORE_DEPTH_M / EMIT_GRADE, abs=12.0)
        assert reach < 200.0, reach
        assert reach > R14_MINIMUM_RUN_M   # the 5 % sizing was shorter

    def test_falling_ground_keeps_the_r14_minimum_run(
        self, monkeypatch
    ) -> None:
        # Ground falling away from the mouth: the ramp is at or above it
        # from the first station, so there is nothing to reach and the
        # R14 minimum lawful run governs.  The extension is a FLOOR-AND-
        # EXTEND — it can never shorten a run.
        layout = _install_scene(monkeypatch, climb_rate=-0.02)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert _east_ramps(layout)
        assert _east_ramp_reach_m(layout) == pytest.approx(
            R14_MINIMUM_RUN_M, abs=12.0)

    def test_walk_keeps_every_bend_of_a_curving_approach(
        self, monkeypatch
    ) -> None:
        # R20-1 AT THE CALL SITE, not just in the helper.  A surface
        # approach whose OSM nodes sit 12 m apart and 1.8 m off the
        # chord through their neighbours — the KCLT shape.  The retired
        # 15 m SPACING merge deleted every other one of these (they are
        # "too close"), leaving a chain up to ~1.8 m from the road; the
        # deviation filter keeps them, so the walk the emitter carries
        # is within tolerance of the OSM way at EVERY node.
        layout = _install_scene(monkeypatch, climb_rate=0.0, curved=True)
        walks: list = []
        real_gather = bridges._gather_portal_walks

        def _spy(*args, **kwargs):
            portal_data = real_gather(*args, **kwargs)
            walks.append(portal_data)
            return portal_data

        monkeypatch.setattr(bridges, "_gather_portal_walks", _spy)
        bridges._emit_tunnel_portals(
            layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
        assert walks and walks[0], "no portal walk was gathered"
        east = [row for row in walks[0] if row[2][0][0] > 0.0]
        assert east, "the east portal produced no walk"
        chain = east[0][2]
        chain_length = sum(math.dist(a, b)
                           for a, b in zip(chain, chain[1:]))
        checked = 0
        for node_xy, station in _curved_approach_nodes():
            if station > chain_length - 1.0:
                continue
            checked += 1
            assert _distance_to_chain(node_xy, chain) <= (
                bridges._TUNNEL_WALK_DEVIATION_TOL_M + 1e-6), (
                node_xy, station,
                _distance_to_chain(node_xy, chain))
        assert checked >= 6, checked

    def test_emitted_grade_never_exceeds_the_ramp_cap(
        self, monkeypatch
    ) -> None:
        # Whatever the run, the chain is still emitted inside the ramp
        # law — the reach must be bought by LENGTH, never by grade.
        for climb in (0.0, 0.01, 0.02):
            layout = _install_scene(monkeypatch, climb_rate=climb)
            bridges._emit_tunnel_portals(
                layout, object(), TILE_LATITUDE, TILE_LONGITUDE)
            reach = _east_ramp_reach_m(layout)
            rise = _east_ramp_top_m(layout) - EMIT_FLOOR_M
            assert rise / max(reach, 1e-6) <= (
                float(config.TUNNEL_RAMP_MAX_GRADE) + 1e-6), climb
