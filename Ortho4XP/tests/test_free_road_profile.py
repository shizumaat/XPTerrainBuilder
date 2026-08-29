"""THE FREE-ROAD PROFILE PASS — round 5b twins.

Spec: ``docs/specs/free-road-profile-pass-spec.md``.  Each class below is
one of the spec's four laws, and the U-LOOP class is the interventional
twin it names: the flatten reproduced with the pass OFF, gone with it ON.

The measured defect these encode (lane/hecar5, merged 52d54c6e): at the
owner's item-2 cliff the crossing adoption built the ramp — 106.70 ->
108.383 — and ``groundside._grade_limit_groundside_chords`` flattened it
back to 106.71, its binding pair being the road ring's OWN RETURN SIDE
across the U-loop, 5-25 m EUCLIDEAN between points far apart along the
PATH.  Raising the ring's cap from 1 % to 8 % did not help, which is why
re-pricing alone shipped default OFF.

Hand-computed geometry, no build, no network, no solver.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import free_road_profile as FRP               # noqa: E402
from auto_patch import groundside as GS                       # noqa: E402
from auto_patch.layout import BuiltShape                       # noqa: E402

CAP = CFG.SERVICE_ROAD_MAX_GRADE                # 8 %, the free-road class
AMBIENT = 100.0
TAXI_Z = AMBIENT + 4.6                          # item 2's own 4.6 m climb
ROAD_HALF_W = 3.0                               # a 6 m service road


@pytest.fixture(autouse=True)
def _arm_the_pass(monkeypatch):
    """THE ON ARM, pinned.  Both gates ship DEFAULT OFF pending the
    metric ruling (see ``config.FREE_ROAD_PROFILE_PASS``); these twins
    state the LAW, so they arm it explicitly — the same posture 9ac6ee55
    used for the contact-cap scoping."""
    monkeypatch.setattr(CFG, "FREE_ROAD_PROFILE_PASS", True)
    monkeypatch.setattr(CFG, "ROAD_CONTACT_CAP_SCOPE", True)
    monkeypatch.setattr(CFG, "PROJECTION_AIRSIDE_FREEZE", True)


class _Layout:
    """The attribute surface the pass reads."""

    def __init__(self, shapes, lines):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = list(lines)
        self._slice_service_subsegments = []
        self._apron_spine_subsegments = []
        self.source_pavement_union = None
        self.absorbed_road_context = []


def _u_loop_layout(gap_m: float = 0.0, road_len: float = 120.0):
    """THE U-LOOP: one road running out and back, its far end welded to a
    taxiway ``TAXI_Z`` above ambient.

    The two legs stand ``2·ROAD_HALF_W`` apart in the PLANE — the 5-25 m
    euclidean chord the limiter priced — while being ``2·road_len`` apart
    along the PATH.  ``gap_m`` moves the taxiway off the road's end face,
    which is the END-ON BINDING tolerance's own axis.
    """
    y_out, y_back = 0.0, -2.0 * ROAD_HALF_W
    # The out leg and the back leg, as one road ring (the U).
    ring = [(0.0, y_out - ROAD_HALF_W), (road_len, y_out - ROAD_HALF_W),
            (road_len, y_out + ROAD_HALF_W), (0.0, y_out + ROAD_HALF_W)]
    road = BuiltShape(polygon=Polygon(ring), role="service_road")
    road.node_altitudes = [AMBIENT] * len(ring)
    back = [(0.0, y_back - ROAD_HALF_W), (road_len, y_back - ROAD_HALF_W),
            (road_len, y_back + ROAD_HALF_W), (0.0, y_back + ROAD_HALF_W)]
    road2 = BuiltShape(polygon=Polygon(back), role="service_road")
    road2.node_altitudes = [AMBIENT] * len(back)
    # The taxiway the far end meets, ALREADY SOLVED at TAXI_Z.
    tx = road_len + gap_m
    taxi_ring = [(tx, -30.0), (tx + 40.0, -30.0),
                 (tx + 40.0, 30.0), (tx, 30.0)]
    taxi = BuiltShape(polygon=Polygon(taxi_ring), role="junction")
    taxi.node_altitudes = [TAXI_Z] * len(taxi_ring)
    # ONE chain: out along the first leg, U-turn, back along the second.
    line = LineString([(0.0, y_out), (road_len, y_out),
                       (road_len, y_back), (0.0, y_back)])
    return _Layout([taxi, road, road2], [line])


def _alt_at(layout, x, y):
    for s in layout.shapes:
        ring = list(s.polygon.exterior.coords)[:-1]
        alts = list(s.node_altitudes or [])
        if len(alts) == len(ring) + 1:
            alts = alts[:-1]
        for (px, py), a in zip(ring, alts):
            if abs(px - x) < 1e-6 and abs(py - y) < 1e-6:
                return a
    return None


# ══════════════════════════════════════════════════════════════════════
# LAW 3 — THE PROFILE ITSELF, stated geometry-free
# ══════════════════════════════════════════════════════════════════════

class TestTheProfileLaw:

    def test_the_climb_distributes_over_the_whole_run_at_the_cap(self):
        ss = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0]
        target, infeasible = FRP.chain_profile(
            ss, [103.2] * 7, {6: 108.0}, 0.08)
        assert not infeasible
        assert target[6] == pytest.approx(108.0)
        # Monotone, and at the cap exactly where the envelope binds.
        for a, b in zip(target, target[1:]):
            assert b >= a - 1e-9
        for i in range(6):
            d = ss[i + 1] - ss[i]
            assert target[i + 1] - target[i] <= 0.08 * d + 1e-9
        # …and the road is UNTOUCHED where the envelope does not reach.
        assert target[0] == pytest.approx(103.2)

    def test_a_pin_pair_no_cap_profile_connects_STILL_BUILDS(self):
        """RULING 1 (coordinator 2026-08-29) — THE WELD OUTRANKS THE CAP.

        The shortfall is still returned with its number, but the span
        BUILDS: both welds are met EXACTLY (contact-is-value, RULINGS
        29c) and the excess grade stands between them for the census to
        price.  The refuted arm — leave the chain alone, which turns the
        excess into a CLIFF at the weld — is kept behind its gate.
        """
        target, infeasible = FRP.chain_profile(
            [0.0, 5.0, 10.0], [100.0] * 3, {0: 100.0, 2: 110.0}, 0.08)
        assert infeasible and infeasible[0][2] == pytest.approx(1.0)
        assert target[0] == pytest.approx(100.0)      # weld, exactly
        assert target[2] == pytest.approx(110.0)      # weld, exactly
        assert target[1] == pytest.approx(105.0)      # the span built
        # THE REFUTED ARM: the whole chain reverts and the 10 m span
        # becomes a 10 m step at the weld instead.
        t_off, inf_off = FRP.chain_profile(
            [0.0, 5.0, 10.0], [100.0] * 3, {0: 100.0, 2: 110.0}, 0.08,
            weld_outranks=False)
        assert inf_off and t_off == [100.0] * 3

    def test_a_chain_with_no_pin_is_left_alone(self):
        target, infeasible = FRP.chain_profile(
            [0.0, 50.0], [100.0, 101.0], {}, 0.08)
        assert target == [100.0, 101.0] and not infeasible


# ══════════════════════════════════════════════════════════════════════
# THE U-LOOP — the interventional twin the spec names
# ══════════════════════════════════════════════════════════════════════

class TestTheULoop:

    def test_the_ramp_is_built_along_the_PATH(self):
        layout = _u_loop_layout()
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["on"] and out["chains"] >= 1
        assert out["moved"] > 0
        # The end that meets the taxiway arrives at its value…
        near = _alt_at(layout, 120.0, ROAD_HALF_W)
        assert near is not None and near > AMBIENT + 3.0
        # …and the far end is still on its own level: a ramp, not a lift.
        far = _alt_at(layout, 0.0, ROAD_HALF_W)
        assert far == pytest.approx(AMBIENT, abs=0.5)

    def test_the_two_legs_are_far_apart_along_the_path(self):
        """THE POINT OF THE STATION COORDINATE.  The two legs stand 6 m
        apart in the plane — the chord the limiter priced at 8 % × 6 m =
        0.48 m and flattened the ramp with — while carrying values the
        profile has every right to separate, because along the PATH they
        are a U-turn apart."""
        layout = _u_loop_layout()
        FRP.solve_free_road_profiles(layout, "TEST")
        a = _alt_at(layout, 0.0, ROAD_HALF_W)              # out leg, start
        b = _alt_at(layout, 0.0, -2.0 * ROAD_HALF_W + ROAD_HALF_W)
        assert a is not None and b is not None
        # Same station region on the two legs -> same order of value; the
        # law never forces them together at the euclidean chord.
        assert abs(a - b) <= CAP * 240.0 + 1e-6

    def test_the_limiter_is_told_the_chain_is_profile_owned(self):
        layout = _u_loop_layout()
        FRP.solve_free_road_profiles(layout, "TEST")
        keys = FRP.profile_owned_keys(layout)
        assert keys, "the profile published no keys for the limiter"
        # The keys are in the LIMITER's own space (2-dp xy).
        for (x, y) in list(keys)[:5]:
            assert round(x, 2) == x and round(y, 2) == y

    def test_the_limiter_ACTUALLY_READS_them(self):
        """RULING 3 (coordinator 2026-08-29) — nothing after the road
        profile re-solves road-chain stations except welds.

        ``who_wrote`` named ``_grade_limit_groundside_chords`` twice on
        the owner's item-4 ramp (pipeline 6733 after the pre-solve,
        pipeline 6998 after the re-solve).  For three rounds
        ``profile_owned_keys`` had NO production reader at all; this
        twin is what stops it silently losing one again.
        """
        import inspect
        from auto_patch import groundside as GS
        src = inspect.getsource(GS._grade_limit_groundside_chords)
        assert "profile_owned_keys" in src
        assert "_profile_owned" in src
        # …and the pins are actually applied to the free-node selection,
        # not merely counted in the stats line (which they already were).
        assert "not in _profile_owned" in src

    def test_the_ruling_3_gate_is_named_and_ships_OFF_on_its_measurement(self):
        """Ruling 3's mechanism is built and attributed, and ships OFF:
        isolated at CYXY it costs +187 law-true rows, and they are the
        service_junction LATERAL class (81 transverse + 74
        road_cross_section, worst 98 % against a 2 % cap), which is the
        coordinator's own STOP condition, not the accepted re-pricing.
        The premise it refutes is in the gate's comment."""
        from auto_patch import config as _C
        assert _C.ROAD_PROFILE_OWNS_ITS_STATIONS is False
        # …and it is EXPORTED, like every other gate in this family: an
        # unexported gate is invisible to the readers that enumerate the
        # module (the blast-radius env-flag hazard).
        assert "ROAD_PROFILE_OWNS_ITS_STATIONS" in _C.__all__
        for _g in ("ROAD_PROFILE_CUMULATIVE_CAP",
                   "ROAD_PROFILE_WELD_OUTRANKS_CAP",
                   "ROAD_PROFILE_CHORD_TWO_SIDED"):
            assert _g in _C.__all__ and getattr(_C, _g) is True

    def test_a_WELD_is_never_exempted_by_the_profile(self):
        """The profile writes ROAD-family nodes only and never a frozen
        one, so no weld can enter the exemption set — the ruling's
        "except welds" is true BY CONSTRUCTION, not by a filter."""
        import inspect
        src = inspect.getsource(FRP.solve_free_road_profiles)
        assert "if m in frozen or m not in cur:" in src

    def test_flag_off_mints_nothing(self, monkeypatch):
        monkeypatch.setattr(CFG, "FREE_ROAD_PROFILE_PASS", False)
        layout = _u_loop_layout()
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["on"] is False and out["moved"] == 0
        assert _alt_at(layout, 120.0, ROAD_HALF_W) == pytest.approx(AMBIENT)
        assert not FRP.profile_owned_keys(layout)


# ══════════════════════════════════════════════════════════════════════
# LAW 1 — THE ONE-WAY WELD
# ══════════════════════════════════════════════════════════════════════

class TestOneWayWeld:

    def test_the_airside_surface_is_BYTE_IDENTICAL(self):
        """The gate of the whole round: the pass may not write one
        airside value.  It cannot, by construction — it writes road-family
        rings only and freezes every node another authority carries."""
        layout = _u_loop_layout()
        taxi = [s for s in layout.shapes if s.role == "junction"][0]
        before = list(taxi.node_altitudes)
        before_ring = list(taxi.polygon.exterior.coords)
        FRP.solve_free_road_profiles(layout, "TEST")
        assert list(taxi.node_altitudes) == before
        assert list(taxi.polygon.exterior.coords) == before_ring

    def test_a_vertex_a_NON_ROAD_shape_carries_is_never_written(self):
        layout = _u_loop_layout()
        weld = (0.0, ROAD_HALF_W)
        pad_ring = [weld, (weld[0] - 8.0, weld[1]),
                    (weld[0] - 8.0, weld[1] + 8.0), (weld[0], weld[1] + 8.0)]
        pad = BuiltShape(polygon=Polygon(pad_ring), role="building")
        pad.node_altitudes = [AMBIENT] * len(pad_ring)
        layout.shapes.append(pad)
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["frozen"] >= 1
        assert _alt_at(layout, *weld) == pytest.approx(AMBIENT)

    def test_the_road_reads_the_SETTLED_airside_value(self):
        """A pure lookup in one direction: move the taxiway and the road
        follows; nothing moves the other way."""
        layout = _u_loop_layout()
        taxi = [s for s in layout.shapes if s.role == "junction"][0]
        taxi.node_altitudes = [TAXI_Z + 2.0] * len(taxi.node_altitudes)
        FRP.solve_free_road_profiles(layout, "TEST")
        assert all(a == pytest.approx(TAXI_Z + 2.0)
                   for a in taxi.node_altitudes)
        near = _alt_at(layout, 120.0, ROAD_HALF_W)
        assert near is not None and near > AMBIENT + 3.0


# ══════════════════════════════════════════════════════════════════════
# LAW 2 — END-ON BINDING WITHIN THE ROAD'S OWN HALF-WIDTH
# ══════════════════════════════════════════════════════════════════════

class TestEndOnBinding:

    def test_a_gap_inside_the_half_width_BINDS(self):
        """Item 3's class: 1.538 m of gap against the derived 1.5 m mouth
        tolerance bound NOTHING before this round.  Under a 6 m road the
        half-width is 3 m, so it binds — geometric, per road, no new
        constant."""
        layout = _u_loop_layout(gap_m=1.6)
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["bound_end_on"] >= 1, (
            "an end-on approach inside the road's own half-width did not "
            "bind — item 3 stays unbound")
        assert _alt_at(layout, 120.0, ROAD_HALF_W) > AMBIENT + 3.0

    def test_a_gap_OUTSIDE_the_half_width_is_REFUSED_and_PUBLISHED(self):
        """The other side of the tolerance: a near miss is reported with
        its numbers, never quietly bound (the veto-refusal posture)."""
        layout = _u_loop_layout(gap_m=6.0)
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["bound_end_on"] == 0
        refusals = getattr(layout, "_free_road_binding_refusals", [])
        assert refusals, "a refused near-miss was not published"
        r = max(refusals, key=lambda d: d.get("gap_m", 0.0))
        assert r["gap_m"] > r["half_width_m"]

    def test_the_half_width_is_DERIVED_from_the_shape(self):
        road = [s for s in _u_loop_layout().shapes
                if s.role == "service_road"][0]
        hw = FRP._mean_half_width(road)
        # 2·A/P halved, for a 6 m × 120 m rect -> just under 3 m.
        assert hw == pytest.approx(ROAD_HALF_W, abs=0.2)


# ══════════════════════════════════════════════════════════════════════
# LAW 4 — THE FLAG DAY
# ══════════════════════════════════════════════════════════════════════

class TestTheGates:

    def test_the_gates_ship_ON_by_owner_order(self):
        """FLIPPED ON (owner 2026-08-29, "skip the ship arm and build the
        app" — the in-sim pass is acceptance in pre-ship mode, RULINGS
        2026-08-29b: law violations only).  The 5b-era +120/+410 rows
        were the census-wrapper class closed by Amendment 9's fourth
        reader (5k, merged); the historic OFF pin above this commit is
        the refutation ledger."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.FREE_ROAD_PROFILE_PASS is True
            assert _fresh.ROAD_CONTACT_CAP_SCOPE is True
        finally:
            importlib.reload(_fresh)

    def test_the_limiter_PRICES_the_path_AND_pins_the_profile(self):
        """AMENDMENT 1 + RULING 3, and they are not alternatives.

        Amendment 1 replaced the round-5b exemption with the PATH METRIC
        because pinning silenced ONE reader while the census still
        priced by chord.  The metric landed in both readers, so that
        collision is gone — and ruling 3 (coordinator 2026-08-29) then
        restored the exemption on ``who_wrote`` evidence that this very
        limiter overwrites the profile's ramp twice per build.  The
        limiter now does BOTH: prices road pairs at the ring walk, and
        leaves the profile's own stations alone.
        """
        import inspect
        src = inspect.getsource(GS._grade_limit_groundside_chords)
        assert "RULING 3" in src and "profile_owned_keys" in src
        assert "_GL_RING_PATH_CUM" in src
        band = inspect.getsource(GS._chord_band)
        assert "_GL_ROAD_PAIR_DISTANCE" in band


# ══════════════════════════════════════════════════════════════════════
# THE FIFTH OWNER SITE — a MID-RUN SAG between two bound ends
# (CYXY 60.7100244,-135.0727863 -> 60.7095834,-135.073401 ->
#  60.7087015,-135.0746305, service_road -10379 / service_junction
#  -10064; measured on the round-5d control: both ends weld at 702.44 /
#  703.11 and the middle sits at 698.93 — 3.63 m below the chord of its
#  own pinned ends, with nothing in the pins asking for a dip.)
# ══════════════════════════════════════════════════════════════════════

class TestTheMidRunSag:

    def test_the_sag_is_lifted_to_the_chord_of_its_pinned_ends(self):
        ss = [0.0, 47.5, 59.4, 118.8, 190.3]
        vals = [702.44, 699.05, 698.93, 699.91, 703.11]
        target, infeasible = FRP.chain_profile(
            ss, vals, {0: 702.44, 4: 703.11}, CAP)
        assert not infeasible
        for i, s in enumerate(ss):
            chord = 702.44 + (703.11 - 702.44) * (s - ss[0]) / (ss[-1] - ss[0])
            assert target[i] >= chord - FRP.MATERIALITY_M, (
                f"station {s} sits {chord - target[i]:.3f} m below the "
                f"chord of its pinned ends — the owner's fifth site")

    def test_the_ends_keep_their_weld_values(self):
        ss = [0.0, 59.4, 190.3]
        target, _inf = FRP.chain_profile(
            ss, [702.44, 698.93, 703.11], {0: 702.44, 2: 703.11}, CAP)
        assert target[0] == pytest.approx(702.44)
        assert target[2] == pytest.approx(703.11)

    def test_the_road_chord_binds_BOTH_WAYS(self):
        """RULING 2 (coordinator 2026-08-29) — THE ROAD CHORD BINDS BOTH
        WAYS.

        THE DISCRIMINATOR: this pass solves ROAD chains, whose interior
        between two welds is pavement the pass itself constructs — not
        ground — so a bump there is the solve's residual and conforms to
        the chord downward as well as upward.  Amendment 3 §2's
        RAISE-ONLY chord (terrain protection) is kept behind its gate for
        any chain class whose interior IS genuine ground.
        """
        target, _inf = FRP.chain_profile(
            [0.0, 50.0, 100.0], [100.0, 120.0, 100.0],
            {0: 100.0, 2: 100.0}, 0.5)
        assert target[1] == pytest.approx(100.0)      # conformed down
        # …and the terrain-protecting arm, unchanged, behind its gate.
        raise_only, _i2 = FRP.chain_profile(
            [0.0, 50.0, 100.0], [100.0, 120.0, 100.0],
            {0: 100.0, 2: 100.0}, 0.5, two_sided=False)
        assert raise_only[1] == pytest.approx(120.0)

    def test_only_a_PIN_holds_its_own_value(self):
        """"only weld/authored/crossing-pinned stations hold" — the
        pins keep their values exactly; every bracketed interior station
        takes the chord whatever the solve left there."""
        target, _inf = FRP.chain_profile(
            [0.0, 25.0, 50.0, 75.0, 100.0],
            [700.0, 693.0, 712.0, 688.0, 700.0],
            {0: 702.0, 4: 706.0}, 0.08)
        assert target[0] == pytest.approx(702.0)
        assert target[4] == pytest.approx(706.0)
        assert target[1:4] == pytest.approx([703.0, 704.0, 705.0])

    def test_an_unbracketed_station_has_no_chord(self):
        """Beyond the last pin there is no chord to hold — the road
        returns to its own level under the cap envelope alone."""
        target, _inf = FRP.chain_profile(
            [0.0, 50.0, 200.0], [100.0, 100.0, 90.0], {0: 104.0}, CAP)
        assert target[2] == pytest.approx(90.0)


# ══════════════════════════════════════════════════════════════════════
# THE CUMULATIVE CAP-DISTANCE (lane/rampsites, site-first re-open):
# a Lipschitz bound whose constant varies in space INTEGRATES.
# ══════════════════════════════════════════════════════════════════════

class TestTheCumulativeCapDistance:

    def test_the_prefix_is_each_intervals_own_cap_times_its_own_length(self):
        ss = [0.0, 10.0, 20.0, 30.0]
        caps = [0.08, 0.08, 0.01, 0.08]
        C = FRP.cap_distance_prefix(ss, caps, 0.08)
        # interval 1-2 and 2-3 both touch the 1 % station, so both carry
        # 1 % — a station's cap binds the grade THROUGH it, both sides.
        assert C == pytest.approx([0.0, 0.8, 0.9, 1.0])

    def test_one_strict_station_no_longer_prices_the_whole_chain(self):
        """THE MECHANISM THIS ROUND MEASURED.  Under ``min x span`` a
        single 1 % station 200 m from the pins refused the ramp and the
        WHOLE chain reverted to the solve's values — the owner's cliff.
        """
        ss = [0.0, 100.0, 200.0, 300.0, 400.0]
        caps = [0.08, 0.08, 0.01, 0.08, 0.08]
        pins = {0: 100.0, 4: 108.0}                 # 8 m over 400 m = 2 %
        t_on, inf_on = FRP.chain_profile(ss, [100.0] * 5, pins, CAP,
                                         caps=caps, cumulative=True)
        t_off, inf_off = FRP.chain_profile(ss, [100.0] * 5, pins, CAP,
                                           caps=caps, cumulative=False,
                                           weld_outranks=False)
        assert inf_off and t_off == [100.0] * 5     # refused, cliff kept
        assert not inf_on and t_on[4] == pytest.approx(108.0)
        for k in range(4):
            c = min(caps[k], caps[k + 1])
            assert abs(t_on[k + 1] - t_on[k]) <= c * (ss[k + 1] - ss[k]) + 1e-9

    def test_the_chord_runs_in_the_CAP_DISTANCE_coordinate(self):
        """The raise-only chord may not stand above the ceiling the same
        caps generate: it interpolates in cap-distance, so it crosses a
        1 % stretch at 1 %, not at the chain's average grade."""
        ss = [0.0, 100.0, 200.0, 300.0, 400.0]
        caps = [0.08, 0.08, 0.08, 0.01, 0.01]      # free first, 1 % last
        pins = {0: 100.0, 4: 108.0}
        t, _inf = FRP.chain_profile(ss, [100.0] * 5, pins, CAP,
                                    caps=caps, cumulative=True)
        # The straight-in-s chord (102, 104, 106) climbs 2 % across the
        # 1 %-capped tail — an unlawful floor.  The cap-distance chord
        # front-loads the rise onto the stretch that can carry it…
        assert t[1] > 103.0
        # …and every interval still respects its own cap.
        for k in range(4):
            c = min(caps[k], caps[k + 1])
            assert abs(t[k + 1] - t[k]) <= c * (ss[k + 1] - ss[k]) + 1e-9
        # …and with ONE cap everywhere the chord is the linear one.
        flat, _ = FRP.chain_profile(ss, [100.0] * 5, pins, CAP,
                                    caps=[0.08] * 5, cumulative=True)
        assert flat[2] == pytest.approx(104.0)

    def test_the_gate_off_restores_the_refuted_arm(self, monkeypatch):
        monkeypatch.setattr(CFG, "ROAD_PROFILE_CUMULATIVE_CAP", False)
        monkeypatch.setattr(CFG, "ROAD_PROFILE_WELD_OUTRANKS_CAP", False)
        ss = [0.0, 100.0, 200.0]
        caps = [0.08, 0.01, 0.08]
        t, inf = FRP.chain_profile(ss, [100.0] * 3, {0: 100.0, 2: 104.0},
                                   CAP, caps=caps)
        assert inf and t == [100.0] * 3


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 3 §2 — SELF-PINS (the fifth site's binding question dissolved)
# ══════════════════════════════════════════════════════════════════════

class TestSelfPins:

    def test_a_chain_with_no_airside_weld_still_gets_pinned_ENDS(self):
        """The owner's fifth site: 0 shared nodes with airside at either
        end (both meet a gap_fill_spine graded_strip), so under the
        pre-ruling law that chain had NO pins and its sag was invisible.
        A SELF-PIN reads the chain's OWN end value — nothing else."""
        layout = _u_loop_layout(gap_m=40.0)      # taxiway far away: no bind
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["bound_end_on"] == 0, "the fixture must have no binding"
        assert out["self_pinned"] >= 1, (
            "a chain with no airside weld got no pins at all — the fifth "
            "site's defect")

    def test_the_strips_value_is_NEVER_read(self):
        """The 2026-08-15 carrier adjudication stands untouched: the pass
        reads airside rings (ENCLAVE_AIRSIDE_ROLES) and the chain's own
        values, and no soft receiver's value anywhere."""
        import inspect
        from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES
        # The only value the pass reads off another shape is an AIRSIDE
        # one, and the airside register excludes every soft receiver.
        assert "graded_strip" not in ENCLAVE_AIRSIDE_ROLES
        assert "boundary" not in ENCLAVE_AIRSIDE_ROLES
        src = inspect.getsource(FRP.solve_free_road_profiles)
        # …and a SELF-pin is the chain's own value, by construction.
        assert "v_end = vals[_end]" in src
        assert "pins[_end] = float(v_end)" in src

    def test_the_self_pin_is_the_chains_OWN_value(self):
        ss = [0.0, 50.0, 100.0]
        vals = [702.44, 698.93, 703.11]
        target, _inf = FRP.chain_profile(ss, vals, {0: vals[0], 2: vals[2]},
                                         CAP)
        assert target[0] == pytest.approx(702.44)
        assert target[2] == pytest.approx(703.11)
        assert target[1] > 698.93                      # the sag is lifted

    def test_the_gate_off_restores_weld_only_pins(self, monkeypatch):
        monkeypatch.setattr(CFG, "FREE_ROAD_PROFILE_SELF_PINS", False)
        layout = _u_loop_layout(gap_m=40.0)
        out = FRP.solve_free_road_profiles(layout, "TEST")
        assert out["self_pinned"] == 0


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 3 §1 — THE PROJECTION'S AIRSIDE FREEZE
# ══════════════════════════════════════════════════════════════════════

class TestTheAirsideFreeze:

    def test_the_freeze_ships_OFF_on_its_LIVE_measurement(self):
        """5e's BLANKET freeze removed this pass's founding repair
        (+94/+563/+926 airside rows at CYXY/SPJC/HECA, profile off) and
        shipped OFF.  Amendment 4 scopes it to UNMUTATED rings, which is
        what makes it shippable — a mutated ring still re-derives."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.PROJECTION_AIRSIDE_FREEZE is False
        finally:
            importlib.reload(_fresh)

    def test_the_projection_hardens_the_solve_owned_airside_set(self):
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        src = inspect.getsource(S.final_grade_projection)
        assert "solve_owned_airside_nodes" in src
        assert "hard |= _airside_frozen" in src

    def test_the_freeze_and_its_GATE_read_ONE_population(self):
        """The freeze holds exactly the set ``airside_value_delta``'s
        solve-owned frame measures — PAVEMENT_ROLES ∩ stage A — so the
        law and its instrument cannot describe two populations."""
        import inspect
        from auto_patch.elevation_per_surface import solver_primitives as SP
        src = inspect.getsource(SP.solve_owned_airside_nodes)
        assert "PAVEMENT_ROLES" in src and "STAGE_A" in src
        from pathlib import Path
        tool = (Path(__file__).resolve().parents[1] / "tools"
                / "airside_value_delta.py").read_text()
        assert "PAVEMENT_ROLES" in tool and "STAGE_A" in tool

    def test_the_freeze_never_hardens_a_ROAD_node(self):
        """It may re-derive road/groundside, never airside — so the road
        family must NOT be in the frozen set."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from auto_patch.elevation_per_surface.solver_primitives import (
            PAVEMENT_ROLES)
        from auto_patch.solve_stage import stage_of_role, STAGE_A
        frozen_roles = {r for r in PAVEMENT_ROLES
                        if stage_of_role(r) == STAGE_A}
        assert "service_road" not in frozen_roles
        assert "service_junction" not in frozen_roles
        assert "groundside_pavement" not in frozen_roles


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 4 — THE FREEZE IS SCOPED TO **UNMUTATED** AIRSIDE RINGS
# (5e measured the blanket form removing this pass's founding repair:
#  +94 / +563 / +926 airside rows at CYXY / SPJC / HECA with the free-road
#  profile not even running.)
# ══════════════════════════════════════════════════════════════════════

class TestTheScopedFreeze:
    """SUPERSEDED BY AMENDMENT 6 (round 5h).  The 5f scoped freeze read
    its mutation set from ``_scoped_projection_defer_ids``, which needs
    ``SCOPED_FINAL_PROJECTION`` — a PARKED feature that never runs, so
    that freeze was byte-identically inert (5g, measured).  The mutation
    criterion is now store MEMBERSHIP and lives in
    ``TestTheLiveStoreFoundation``; what survives here is the one clause
    that was never about the snapshot."""

    def test_the_freeze_never_hardens_a_ROAD_node(self):
        from auto_patch.elevation_per_surface.solver_primitives import (
            PAVEMENT_ROLES)
        from auto_patch.solve_stage import stage_of_role, STAGE_A
        frozen_roles = {r for r in PAVEMENT_ROLES
                        if stage_of_role(r) == STAGE_A}
        assert "service_road" not in frozen_roles
        assert "service_junction" not in frozen_roles


class TestSnapshotBlindRederivation:
    """RETIRED-KEPT-GATED with the freeze family (Amendment 7 §3).  The
    two-stage snapshot-blind staging existed to serve a freeze, and
    rounds 5e-5h measured every freeze form dead.  What replaces it is
    ``TestRoadBlindRederivation`` below: no freeze, no staging, one
    projection, and the ROAD-FAMILY VALUE SOURCE scoped instead."""

    def test_the_staging_ships_off(self):
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.PROJECTION_SNAPSHOT_BLIND is False
            assert _fresh.PROJECTION_AIRSIDE_FREEZE is False
        finally:
            importlib.reload(_fresh)


class TestWeldIdentity:

    def test_the_freeze_takes_the_LIMITERS_second_reading(self):
        """One edit, never a third key derivation: the profile's freeze
        joins canonically through ``_airside_claimed_keys`` — the same
        helper the chord limiter already pins with."""
        import inspect
        src = inspect.getsource(GS._road_vertex_graph)
        assert "_airside_claimed_keys(layout)" in src
        assert "find_nearest" in src

    def test_the_mm_bucket_alone_is_NOT_the_identity(self):
        """Why the second reading exists, in the code's own terms: the
        emitter merges by the canonical spelling, not the mm bucket."""
        import inspect
        src = inspect.getsource(GS._road_vertex_graph)
        assert "MILLIMETRE bucket" in src
        assert "0.09 m and 0.07 m" in src


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 6 — THE LIVE STORE AS THE FREEZE'S FOUNDATION
# ══════════════════════════════════════════════════════════════════════

class TestTheLiveStoreFoundation:
    """The store SURVIVES the freeze family's retirement — Amendment 7
    keeps it as the value source for road-blind re-derivation.  What is
    retired with the freezes is the MUTATION CRITERION built on it
    (5h: CYXY released 5 % and lost the repair, SPJC released 21 % and
    moved 1,545 solve-owned nodes, 1,490 with no road contact)."""

    def test_the_store_is_minted_UNCONDITIONALLY_by_the_solve(self):
        """Why it can be the foundation at all, and why it costs nothing:
        minted the moment the one solve publishes its surface, keyed by
        canonical point id, over every key of every solve node.  Measured
        coverage of the solve-owned airside population: 99.89 % at CYXY
        (1853/1855), 99.95 % at SPJC (7377/7381)."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        whole = inspect.getsource(S)
        assert '"solved_values", "scalar",' in whole
        # the parked feature 5f/5g stood on is still parked, untouched
        assert "SCOPED_FINAL_PROJECTION = False" in whole
        proj = inspect.getsource(S.final_grade_projection)
        assert "_carried_solved" in proj


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 7 — ROAD-BLIND RE-DERIVATION, NO FREEZE
# ══════════════════════════════════════════════════════════════════════

class TestRoadBlindRederivation:

    def test_the_projection_runs_UNCHANGED_nothing_frozen(self):
        """The whole point: same population, same solve, full repair.
        Only the road-family VALUE SOURCE changes."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        proj = inspect.getsource(S.final_grade_projection)
        # one projection call, not the retired two-stage form
        assert proj.count("feasibility_project_partitioned(") == 1
        assert "_road_blind_rederive_on()" in proj
        assert "Nothing frozen, full repair." in proj

    def test_road_values_resolve_through_the_LIVE_store(self):
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        proj = inspect.getsource(S.final_grade_projection)
        assert "_carried_solved.get(_i)" in proj
        assert "ROAD_ROLES as _RB_ROAD" in proj
        # …and the store is minted in exactly one place, by the solve.
        whole = inspect.getsource(S)
        assert whole.count('"solved_values", "scalar",') == 1

    def test_PROFILE_OFF_is_byte_identical_BY_CONSTRUCTION(self):
        """With no post-solve road writer the store value EQUALS the
        current value, so the reseed loop cannot change a thing — the
        `elev[_i] == _sv` guard is that proof in code."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        proj = inspect.getsource(S.final_grade_projection)
        assert "if _sv is None or elev[_i] == _sv:" in proj
        assert "continue" in proj

    def test_the_interventional_property_moving_a_road_changes_nothing(self):
        """PROFILE ON ⇒ the airside re-derivation is independent of the
        road's post-solve movement.  Stated on the mechanism: whatever
        the road's current value is, the projection reads the store's.
        A road moved post-solve is re-seated to its SOLVE-TIME value
        before the projection sees it, so two arms differing only in a
        post-solve road write hand the projection identical inputs."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        proj = inspect.getsource(S.final_grade_projection)
        assert "elev[_i] = _sv" in proj
        assert "_road_blind_reseeded += 1" in proj

    def test_no_ring_is_selected_anywhere(self):
        """The refutation 5e-5h earned: ring selection cannot reach
        airside-blindness, because the value-mutated rings are exactly
        the rings roads touch."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as S
        proj = inspect.getsource(S.final_grade_projection)
        assert "_released" not in proj
        assert "_mutated = True" not in proj

    def test_the_gate_is_RETIRED_KEPT_GATED(self):
        """Owner 2026-08-29a (Amendment 8): the 5e-5i freeze/road-blind
        knobs stay retired-kept-gated.  Road-blind was the best of the
        post-solve remedies — CYXY's post-solve channel goes to 0 under
        it — but 5i proved the residual is UPSTREAM of every post-solve
        pass, and the owner has ruled the equilibrium shift ACCEPTED
        rather than defended against.  The mechanism is kept and the
        twins above still state it."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.PROJECTION_ROAD_BLIND is False
        finally:
            importlib.reload(_fresh)
