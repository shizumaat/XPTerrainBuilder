"""Round 14 — roads serve tunnels: the paved area IS the corridor.

Spec: ``docs/specs/round14-tunnel-road-integration-spec.md`` including its
2026-08-11 AMENDMENT (A-1..A-3), owner laws on the round-10 KCLT output.

R14-1/A-1  THE PAVED AREA IS THE CORRIDOR.  Where mapped road pavement
        covers a tunnel system's open cut, that pavement IS the tunnel
        surface: it is CLAIMED and re-profiled in place (bore-depth level
        across the mouths and the roadway between facing portals, then
        climbing at the approach grade back to its solved value), takes
        ref ``tunnel_road``, and joins ``BELOW_GRADE_REFS`` so the
        unchanged R5 law grades the surroundings toward it.  The
        synthetic rectangle it replaces stands down.  A synthetic
        corridor beside at-grade road pavement is a CLIFF — measured at
        KCLT as an 8.31 m step across the 0.6 m graze standoff — and
        that cliff is the defect class this round removes.
        AIRSIDE IS KING: an apron or transit shape inside the extent is
        never claimed; it mints a ``tunnel_airside_conflict`` finding.
R14-2/A-3  A CUT NEVER INTERRUPTS AIRCRAFT-TRANSIT PAVEMENT.  The runway
        family plus junction / cross_connector / primary_parallel /
        secondary_parallel / stub leave ``_tunnel_ramp_cut_roles``;
        apron and the service/groundside roads stay cuttable, because
        owner ruling 4's beheading precedent lives exactly there.  Over
        protected pavement the stretch is covered bore.
R14-3/A-2  THE RUN IS DEPTH OVER GRADE.  The bore floor is
        ``deck_reference − BRIDGE_ROAD_CLEARANCE_M`` (a measured cut
        keeps R10-3's deeper-of-the-two; the 8 m synthetic is the last
        resort with no deck reference at all), and the approach runs
        ``bore_depth / TUNNEL_APPROACH_GRADE``.  Owner 2026-08-11:
        "Ramps should be at up to 5% grade" — a CAP, so that run is the
        MINIMUM lawful one and the emitted top edge never exceeds it.
        The three mechanisms that used to outlive grade-reach are each
        pinned below.

Fixtures are synthetic and headless — the idiom of
``tests/test_round10_tunnel_emission.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import box

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import bridges  # noqa: E402
from auto_patch import config as _CFG  # noqa: E402
from auto_patch import groundside  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    PavementLayout,
    ROLE_APRON,
    ROLE_JUNCTION,
    ROLE_RETAINING_WALL,
    ROLE_SERVICE_JUNCTION,
    ROLE_TUNNEL_RAMP,
)

ANCHOR = (35.215, -80.944)
AMBIENT_M = 219.8
DECK_M = 219.0


def _portal_row(way_id, station, outward, mouth_grade, deck=DECK_M,
                carriage_w=10.0, walk=None):
    """One ``portal_data`` row: the prefix the emitters slice."""
    _walk = walk if walk is not None else [station, outward]
    return ("n" + way_id, way_id, _walk, "service", AMBIENT_M, AMBIENT_M,
            False, carriage_w, False, mouth_grade, [], deck, None)


# ══════════════════════════════════════════════════════════════════
# R14-3 / A-2 — the bore floor and the run
# ══════════════════════════════════════════════════════════════════
class TestBoreFloorIsTheClearance:

    def test_a_deck_reference_gives_the_clearance_floor(self):
        floor = bridges._bore_floor_elevation(
            214.0, DECK_M, None, False, 8.0)
        assert floor == pytest.approx(
            DECK_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M))

    def test_a_measured_cut_keeps_the_deeper_of_the_two(self):
        # R10-3 unchanged: a real trench is never filled back in.
        floor = bridges._bore_floor_elevation(
            214.0, DECK_M, 210.0, True, 8.0)
        assert floor == pytest.approx(210.0)

    def test_a_shallow_measured_cut_still_takes_the_clearance(self):
        floor = bridges._bore_floor_elevation(
            214.0, DECK_M, 217.0, True, 8.0)
        assert floor == pytest.approx(
            DECK_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M))

    def test_no_deck_reference_falls_back_to_the_synthetic_depth(self):
        # The last resort: nothing has been measured to reason from.
        floor = bridges._bore_floor_elevation(214.0, None, None, False, 8.0)
        assert floor == pytest.approx(214.0 - 8.0)

    def test_the_synthetic_8m_no_longer_sets_a_measured_bore(self):
        # The KCLT SE regression in one line: with a deck reference the
        # floor is 5.1 m down, not 8 m (which measured 11.46 m below
        # ambient once apt_elev sat under the local DEM).
        assert bridges._bore_floor_elevation(
            214.0, DECK_M, None, False, 8.0) > 214.0 - 8.0


class TestApproachGradeConstant:

    def test_the_owner_cap_is_five_percent(self):
        # Owner 2026-08-11: "Ramps should be at up to 5% grade."
        assert bridges.TUNNEL_APPROACH_GRADE == pytest.approx(0.05)

    def test_the_run_is_depth_over_the_cap(self):
        # The owner's worked example: 5.1 m at the cap is ~102 m.
        depth = float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
        assert depth / bridges.TUNNEL_APPROACH_GRADE == pytest.approx(
            102.0, abs=1.0)

    def test_the_cap_beats_the_old_highway_planning_grade(self):
        # 0.035 is what the walk used to size against; it bought 43 %
        # more roadway for the same climb.
        old = 0.04 - bridges.TUNNEL_RAMP_GRADE_SAFETY_MARGIN
        assert bridges.TUNNEL_APPROACH_GRADE > old


# ══════════════════════════════════════════════════════════════════
# R14-2 / A-3 — a cut never interrupts aircraft-transit pavement
# ══════════════════════════════════════════════════════════════════
class TestTransitPavementIsNeverCut:

    def test_the_taxiway_family_left_the_cut_set(self):
        cuts = bridges._tunnel_ramp_cut_roles()
        for role in ("junction", "cross_connector", "primary_parallel",
                     "secondary_parallel", "stub", "runway",
                     "runway_crossing", "runway_clearance"):
            assert role not in cuts, f"{role} must never be cut"

    def test_apron_and_the_service_roads_stay_cuttable(self):
        # Owner ruling 4's beheading precedent lives exactly there —
        # OTHH's mapped portals open within apron and service pavement.
        cuts = bridges._tunnel_ramp_cut_roles()
        for role in ("apron", "service_road", "service_junction",
                     "groundside_pavement"):
            assert role in cuts

    def test_a_piece_mostly_over_a_taxiway_is_covered_bore(self):
        shape = BuiltShape(polygon=box(0.0, 0.0, 10.0, 10.0),
                           role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                           altitude=210.0)
        taxiway = box(-5.0, -5.0, 12.0, 15.0)
        assert bridges._clip_piece_off_protected(shape, taxiway) is None

    def test_a_grazing_piece_is_clipped_back_to_the_edge(self):
        shape = BuiltShape(polygon=box(0.0, 0.0, 100.0, 10.0),
                           role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                           altitude=210.0)
        taxiway = box(90.0, -5.0, 200.0, 15.0)
        kept = bridges._clip_piece_off_protected(shape, taxiway)
        assert kept is not None
        assert kept.polygon.intersection(taxiway).area == pytest.approx(
            0.0, abs=1e-9)
        assert kept.polygon.area < 100.0 * 10.0

    def test_a_piece_clear_of_transit_pavement_is_untouched(self):
        poly = box(0.0, 0.0, 10.0, 10.0)
        shape = BuiltShape(polygon=poly, role=ROLE_TUNNEL_RAMP,
                           ref="tunnel_ramp", altitude=210.0)
        kept = bridges._clip_piece_off_protected(
            shape, box(500.0, 500.0, 600.0, 600.0))
        assert kept is shape and kept.polygon is poly


# ══════════════════════════════════════════════════════════════════
# R14-1 / A-1 — the claim
# ══════════════════════════════════════════════════════════════════
def _claim_scene(road_role=ROLE_SERVICE_JUNCTION, road_alt=AMBIENT_M):
    """Two facing portals 56 m apart with ONE road plate covering the
    whole gap — KCLT's triangle in miniature."""
    layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    layout.shapes.append(BuiltShape(
        polygon=box(-6.0, -12.0, 62.0, 12.0), role=road_role,
        ref="", node_altitudes=[road_alt] * 5))
    floor = DECK_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
    rows = [_portal_row("W1", (0.0, 0.0), (56.0, 0.0), floor),
            _portal_row("W2", (56.0, 0.0), (0.0, 0.0), floor)]
    return layout, rows, floor


class TestTheClaim:

    def test_a_covering_road_is_claimed_and_levelled(self):
        layout, rows, floor = _claim_scene()
        n, claimed = bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert n == 1 and len(claimed) == 1
        shape = layout.shapes[0]
        assert shape.ref == bridges.TUNNEL_ROAD_REF
        # ONE level surface at bore depth across the between-portals zone.
        assert max(shape.node_altitudes) - min(shape.node_altitudes) \
            <= 0.1
        assert shape.node_altitudes[0] == pytest.approx(floor, abs=0.02)

    def test_the_claimed_ref_is_a_below_grade_source(self):
        # This one ref is the whole registration: neighbours grade toward
        # the claimed pavement under the UNCHANGED R5 law.
        assert bridges.TUNNEL_ROAD_REF in groundside.BELOW_GRADE_REFS

    def test_a_claimed_road_keeps_its_own_role_and_authority(self):
        layout, rows, _floor = _claim_scene()
        bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert layout.shapes[0].role == ROLE_SERVICE_JUNCTION, (
            "the claim is a ref in an existing source set, never a new "
            "authority class")

    def test_the_claim_never_raises_a_vertex(self):
        # A road already BELOW the profile keeps its own value: the claim
        # can only dig.
        deeper = 200.0
        layout, rows, _floor = _claim_scene(road_alt=deeper)
        bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert all(v == pytest.approx(deeper)
                   for v in layout.shapes[0].node_altitudes)

    def test_an_apron_inside_the_open_cut_is_never_sunk(self):
        layout, rows, _floor = _claim_scene(road_role=ROLE_APRON)
        n, claimed = bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert n == 0 and claimed == []
        assert layout.shapes[0].ref == "", "airside is king"
        assert all(v == pytest.approx(AMBIENT_M)
                   for v in layout.shapes[0].node_altitudes)
        findings = getattr(layout, "tunnel_airside_conflict", [])
        assert findings and findings[0]["role"] == ROLE_APRON
        assert "level_it_would_need_m" in findings[0]

    def test_the_conflict_finding_carries_a_lat_lon_join_key(self):
        """KCLT adjudication 2026-08-11 §4: the record named a role, an
        area and a level and NO PLACE, so joining it to the classify
        instrument's rows meant re-deriving the shape geometrically off
        an emitted patch.  The centroid is the join key — in the
        module's own projection, the frame every sibling finding here
        records."""
        layout, rows, _floor = _claim_scene(road_role=ROLE_APRON)
        bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        finding = layout.tunnel_airside_conflict[0]
        centroid = layout.shapes[0].polygon.centroid
        assert finding["x_m"] == pytest.approx(centroid.x, abs=0.05)
        assert finding["y_m"] == pytest.approx(centroid.y, abs=0.05)
        expect_lat, expect_lon = bridges._local_meter_projections(
            ANCHOR)[1](centroid.x, centroid.y)
        assert finding["lat"] == pytest.approx(expect_lat, abs=1e-7)
        assert finding["lon"] == pytest.approx(expect_lon, abs=1e-7)
        # …and it lands where the shape actually is: metres from the
        # anchor, not degrees adrift from a transposed lat/lon.
        assert abs(finding["lat"] - ANCHOR[0]) < 0.01
        assert abs(finding["lon"] - ANCHOR[1]) < 0.01

    def test_a_transit_shape_inside_the_open_cut_is_never_sunk(self):
        layout, rows, _floor = _claim_scene(road_role=ROLE_JUNCTION)
        n, _claimed = bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert n == 0
        assert getattr(layout, "tunnel_airside_conflict", [])

    def test_pavement_clear_of_the_extent_is_untouched(self):
        layout, rows, _floor = _claim_scene()
        layout.shapes.append(BuiltShape(
            polygon=box(500.0, 500.0, 560.0, 520.0),
            role=ROLE_SERVICE_JUNCTION, ref="",
            node_altitudes=[AMBIENT_M] * 5))
        bridges._claim_road_pavement(layout, rows, [(0, 1)], 0.6)
        assert layout.shapes[-1].ref == ""
        assert all(v == pytest.approx(AMBIENT_M)
                   for v in layout.shapes[-1].node_altitudes)

    def test_the_approach_grades_out_at_the_owner_cap(self):
        # Beyond the level zone the claimed surface climbs at the cap and
        # meets its solved value; no vertex may sit below the profile.
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        layout.shapes.append(BuiltShape(
            polygon=box(0.0, -6.0, 200.0, 6.0),
            role=ROLE_SERVICE_JUNCTION, ref="",
            node_altitudes=[AMBIENT_M] * 5))
        floor = DECK_M - float(_CFG.BRIDGE_ROAD_CLEARANCE_M)
        walk = [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)]
        rows = [_portal_row("W1", (0.0, 0.0), (200.0, 0.0), floor,
                            walk=walk)]
        bridges._claim_road_pavement(layout, rows, [], 0.6)
        shape = layout.shapes[0]
        assert shape.ref == bridges.TUNNEL_ROAD_REF
        for (x, _y), value in zip(
                list(shape.polygon.exterior.coords), shape.node_altitudes):
            assert value <= AMBIENT_M + 1e-6
            assert value >= floor - 1e-6


class TestSyntheticStandsDown:

    def test_a_rectangle_over_claimed_pavement_is_dropped(self):
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        pre = {id(s) for s in layout.shapes}
        layout.shapes.append(BuiltShape(
            polygon=box(0.0, 0.0, 40.0, 10.0), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_corridor", altitude=213.9))
        claimed = [box(-5.0, -5.0, 45.0, 15.0)]
        n = bridges._stand_down_synthetic_over_claimed(layout, claimed, pre)
        assert n == 1
        assert bridges._TUNNEL_PAVEMENT_REFS  # sanity
        assert [s for s in layout.shapes
                if getattr(s, "ref", "") == "tunnel_corridor"] == []

    def test_a_rectangle_clear_of_claimed_pavement_survives(self):
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        pre = {id(s) for s in layout.shapes}
        layout.shapes.append(BuiltShape(
            polygon=box(0.0, 0.0, 40.0, 10.0), role=ROLE_TUNNEL_RAMP,
            ref="tunnel_corridor", altitude=213.9))
        n = bridges._stand_down_synthetic_over_claimed(
            layout, [box(500.0, 500.0, 540.0, 510.0)], pre)
        assert n == 0
        assert len(layout.shapes) == 1

    def test_a_wall_may_not_cover_a_claimed_road(self):
        # R14-1 third bullet: the R10-2 cuts apply to the claimed surface
        # exactly as to an emitted ramp.
        wall = BuiltShape(polygon=box(0.0, 0.0, 100.0, 4.0),
                          role=ROLE_RETAINING_WALL, ref="tunnel_wall",
                          altitude=219.0)
        claimed_road = box(30.0, -1.0, 60.0, 5.0)
        pieces = bridges._tunnel_cover_pieces(wall, claimed_road)
        assert len(pieces) == 2
        for piece in pieces:
            assert piece.polygon.intersection(
                claimed_road).area == pytest.approx(0.0, abs=1e-9)


# ══════════════════════════════════════════════════════════════════
# R14-1 item 1 — the claimed plate is PINNED (owner 2026-08-11)
# ══════════════════════════════════════════════════════════════════
class TestClaimedPlateIsPinned:
    """The claim keeps the shape's pavement ROLE, so the role-keyed
    feature-weld classifier never hardens it and the projection relaxed
    the plate by 0.90 m.  The fix is the EXISTING born-plate pin idiom
    applied to a new member — node-keyed, so the role gate is bypassed
    without touching authority."""

    def _arrays(self, ring, alts, hard=None):
        from auto_patch.elevation_per_surface import solver_primitives as sp
        layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
        layout.shapes.append(BuiltShape(
            polygon=__import__("shapely.geometry", fromlist=["Polygon"])
            .Polygon(ring),
            role=ROLE_SERVICE_JUNCTION, ref=bridges.TUNNEL_ROAD_REF,
            node_altitudes=list(alts)))
        keys = {(round(x, 3), round(y, 3)): i
                for i, (x, y) in enumerate(ring)}
        elev = [0.0] * len(ring)
        is_hard = list(hard or [False] * len(ring))

        def intern(x, y):
            return (round(x, 3), round(y, 3))

        return sp, layout, keys, elev, is_hard, intern

    def test_every_claimed_vertex_is_pinned_at_its_profile(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        alts = [213.9, 213.9, 213.9, 213.9, 213.9]
        sp, layout, keys, elev, is_hard, intern = self._arrays(ring, alts)
        pins = sp._build_tunnel_road_pins(layout, keys, elev, is_hard, intern)
        assert len(pins) == 4
        assert all(v == pytest.approx(213.9) for v in pins.values())

    def test_a_senior_pin_is_never_overwritten(self):
        # Runway / seam / deck / skirt / EAT own their value; the claim
        # never outranks them.
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        alts = [213.9] * 5
        hard = [True, False, False, False]
        sp, layout, keys, elev, is_hard, intern = self._arrays(
            ring, alts, hard=hard)
        pins = sp._build_tunnel_road_pins(layout, keys, elev, is_hard, intern)
        assert 0 not in pins and len(pins) == 3

    def test_an_unclaimed_road_is_not_pinned(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
        sp, layout, keys, elev, is_hard, intern = self._arrays(
            ring, [219.8] * 5)
        layout.shapes[0].ref = ""
        pins = sp._build_tunnel_road_pins(layout, keys, elev, is_hard, intern)
        assert pins == {}
