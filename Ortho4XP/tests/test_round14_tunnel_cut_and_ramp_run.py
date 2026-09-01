"""Round 14 — the tunnel CUT and the RAMP RUN (R14-2 and R14-3).

Spec: ``docs/specs/round14-tunnel-road-integration-spec.md`` including its
2026-08-11 AMENDMENT (A-1..A-3), owner laws on the round-10 KCLT output.

**R14-1/A-1 IS RETIRED — do not re-add its twins here.**  "THE PAVED AREA
IS THE CORRIDOR" minted a CLAIM CLASS: mapped road pavement covering a
tunnel's open cut was re-profiled in place, took ref ``tunnel_road`` and
joined ``BELOW_GRADE_REFS``.  RULINGS 2026-08-31a judged that class the
defect and 2026-08-31b retired it; the replacement is the pre-claim model
— tunnel MOUTHS, RAMPS and RETAINING WALLS — specified in
``docs/specs/linear-transport-redesign-spec.md`` §5 and ruled consumer by
consumer in ``docs/specs/linear-transport-consumer-census.md`` §2/§3.
Under §5.3 the canonical mouth (RULINGS 2026-08-30) is the emitted set,
and mapped road pavement over a cut is CORE road ground above a covered
stretch (the deck model, §4) or severed by the open cut — never
re-profiled in place.  What used to live in this file and where its
successor lives now:

* the claim minter / ``TUNNEL_ROAD_REF`` / the corridor split + densify /
  the synthetic stand-down / the claimed-plate solver pins — all DELETED
  with the class (census rows #22-26, #30-32, #37);
* the ``claimed_tunnel_corridor`` predicate re-keyed to
  ``groundside.is_tunnel_ramp_surface`` — twinned in
  ``tests/test_tunnel_ramp_surface_survives.py`` (census #33/#34);
* the node-book exclusion re-keyed from the claim set to
  ``layout.tunnel_open_cut_polys`` — twinned in
  ``tests/test_tunnel_corridor_exclusion.py`` (census #51, seam-probe 4);
* the open-cut region publisher — ``tests/test_tunnel_open_cut_publisher.py``.

The two laws of this round that STAND, and are pinned below:

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
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    ROLE_TUNNEL_RAMP,
)

ANCHOR = (35.215, -80.944)
AMBIENT_M = 219.8
DECK_M = 219.0


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
