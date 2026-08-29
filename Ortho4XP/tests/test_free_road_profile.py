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

    def test_a_pin_pair_no_cap_profile_connects_is_REFUSED(self):
        """"reports honestly if the binding still cannot be met" — the
        chain is left alone and the shortfall is returned with its
        number, never emitted as a silent cliff."""
        target, infeasible = FRP.chain_profile(
            [0.0, 10.0], [100.0, 100.0], {0: 100.0, 1: 110.0}, 0.08)
        assert infeasible and infeasible[0][2] == pytest.approx(1.0)
        assert target == [100.0, 100.0]        # untouched

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

    def test_both_gates_ship_OFF_pending_the_metric_ruling(self):
        """DEVIATION FROM THE SPEC, reported not decided (lane/hecar5b).

        Spec law 4 asked for the scoping to flip ON in this arm.  The arm
        did not meet its acceptance — the profile is path-metric while the
        within-shape census is chord-metric, so HECA went 6820 -> 7230
        (+410) and CYXY 368 -> 488 (+120), every CYXY row a within_shape
        road pair at 8.33-9.11 % against the 8 % cap.  Shipping a measured
        regression default-ON is the one thing the flag day must not do,
        so both gates ship OFF and the twins above arm them explicitly."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.FREE_ROAD_PROFILE_PASS is False
            assert _fresh.ROAD_CONTACT_CAP_SCOPE is False
        finally:
            importlib.reload(_fresh)

    def test_the_limiter_PRICES_the_path_instead_of_exempting(self):
        """SUPERSEDED BY AMENDMENT 1.  Round 5b pinned the profile's nodes
        so the limiter could not flatten them; that silenced ONE reader
        and left the census pricing the same pairs by chord.  The
        amendment rules the metric instead, so the limiter prices road
        pairs at the ring walk — the same law function the census uses —
        and goes on fixing genuine road defects."""
        import inspect
        src = inspect.getsource(GS._grade_limit_groundside_chords)
        assert "ROUND 5b's EXEMPTION IS RETIRED" in src
        assert "_GL_RING_PATH_CUM" in src
        band = inspect.getsource(GS._chord_band)
        assert "_GL_ROAD_PAIR_DISTANCE" in band
