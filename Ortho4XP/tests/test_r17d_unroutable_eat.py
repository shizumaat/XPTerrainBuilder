"""R17D LAW 1 — THE UNROUTABLE EAT IS NOT AN EAT.

Owner ruling 2026-08-12 ("CANYON ROOT FIELD-CONFIRMED"): 25C is clean in
the owner's rebuilt +22+113 and 07L/25R still reads −8.9 m; the phantom
EAT pins author the band at the remaining runway ends and the seal
enforces them.  The false-EAT ratification gains its third guard: **an
EAT anchor-rect pin with NO taxi route to any runway anchor is not an
end-around taxiway.**

The rect's scoping is purely GEOMETRIC — a corridor about the extended
centreline beyond a runway end — so a PERIMETER ROAD lying there is
claimed by it.  A road is not an end-around taxiway, and the airside
route graph says so exactly: ``REACH_NO_SERVICE_SPINES`` withholds the
service pairs, so a road-only component holds no route to a runway.

The refusal is WHOLE-RECT because the question is about the FACILITY.
Its sibling, the contradiction guard, stays PER NODE because that law
asks whether one VALUE contradicts a senior anchor.

ATTRIBUTION (r17d, instrumented builds 2026-08-12, one line per airport,
report-only arm): KCLT 11 pins / 1 rect — 11 TAXI-BOUND, 0 refused;
KSTJ 18 pins / 1 rect — 5 bound, 13 unbound, whole-rect refusal 0 (the
rect routes, so its pins stand and its 5 contradiction-refusals are
untouched); VHHH — see the round's claims table.

Headless: no DEM, no network, no X-Plane install.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    solve as SV)


def _chain(pairs, budget=1.0):
    """``{i: [(j, budget), ...]}`` — an undirected graph from ``pairs``."""
    adj: dict = {}
    for (a, b) in pairs:
        adj.setdefault(a, []).append((b, budget))
        adj.setdefault(b, []).append((a, budget))
    return adj


#: A runway anchor at 0, taxiway 0-1-2-3 with the EAT rect on 3-4, and a
#: PERIMETER ROAD 10-11-12 that no airside edge touches — exactly what
#: ``u_spine_adj_airside`` looks like once the service pairs are out.
AIRSIDE = _chain([(0, 1), (1, 2), (2, 3), (3, 4), (10, 11), (11, 12)])
RUNWAY_ANCHOR = {0: 12.0}


class TestTheRouteTest:
    """:func:`eat_pin_taxi_bound` — does a taxi route to a runway exist?"""

    def test_a_pin_on_the_taxi_network_is_BOUND(self):
        assert SV.eat_pin_taxi_bound({3: 5.0, 4: 5.0}, AIRSIDE,
                                     RUNWAY_ANCHOR) == {3, 4}

    def test_a_pin_on_a_ROAD_ONLY_component_is_UNBOUND(self):
        assert SV.eat_pin_taxi_bound({11: 5.0, 12: 5.0}, AIRSIDE,
                                     RUNWAY_ANCHOR) == set()

    def test_a_pin_on_no_edge_at_all_is_UNBOUND(self):
        assert SV.eat_pin_taxi_bound({99: 5.0}, AIRSIDE,
                                     RUNWAY_ANCHOR) == set()

    def test_the_pins_own_value_never_enters_the_test(self):
        """Connectivity, never budget: a pin 400 m out of band is bound
        exactly when a route exists.  (The VALUE is the contradiction
        guard's question, and that guard is priced separately.)"""
        assert SV.eat_pin_taxi_bound({4: -400.0}, AIRSIDE,
                                     RUNWAY_ANCHOR) == {4}

    def test_NO_RUNWAY_ANCHOR_BINDS_EVERYTHING(self):
        """A missing bound is honest — with no anchor on the graph the
        law refuses nothing rather than refusing the airport."""
        assert SV.eat_pin_taxi_bound({11: 5.0}, AIRSIDE, {}) == {11}
        assert SV.eat_pin_taxi_bound({11: 5.0}, AIRSIDE, None) == {11}
        assert SV.eat_pin_taxi_bound({11: 5.0}, {}, RUNWAY_ANCHOR) == {11}

    def test_an_anchor_off_the_graph_is_no_anchor(self):
        assert SV.eat_pin_taxi_bound({3: 5.0}, AIRSIDE,
                                     {777: 12.0}) == {3}

    def test_no_pins_is_the_inert_answer(self):
        assert SV.eat_pin_taxi_bound({}, AIRSIDE, RUNWAY_ANCHOR) == set()


class TestTheWholeRectRefusal:
    """:func:`eat_unroutable_rect_refusals` — the FACILITY is judged."""

    def test_a_rect_with_NO_routable_node_is_refused_WHOLE(self):
        pins = {11: 5.0, 12: 5.0}
        rects = {11: 2, 12: 2}
        bound = SV.eat_pin_taxi_bound(pins, AIRSIDE, RUNWAY_ANCHOR)
        assert SV.eat_unroutable_rect_refusals(pins, rects, bound) == {
            11: 2, 12: 2}

    def test_a_rect_with_ONE_routable_node_stands_WHOLE(self):
        """A genuine EAT whose other vertices were decimated off the
        spine keeps its whole rect: some node of it routes."""
        pins = {3: 5.0, 4: 5.0, 99: 5.0}
        rects = {3: 1, 4: 1, 99: 1}
        bound = SV.eat_pin_taxi_bound(pins, AIRSIDE, RUNWAY_ANCHOR)
        assert 99 not in bound
        assert SV.eat_unroutable_rect_refusals(pins, rects, bound) == {}

    def test_two_rects_are_judged_INDEPENDENTLY(self):
        pins = {3: 5.0, 4: 5.0, 11: 5.0, 12: 5.0}
        rects = {3: 1, 4: 1, 11: 2, 12: 2}
        bound = SV.eat_pin_taxi_bound(pins, AIRSIDE, RUNWAY_ANCHOR)
        assert SV.eat_unroutable_rect_refusals(pins, rects, bound) == {
            11: 2, 12: 2}

    def test_a_pin_with_NO_rect_identity_is_its_own_rect(self):
        """A missing publication can only ever refuse LESS: the node is
        judged alone, never folded into a sibling's verdict."""
        pins = {3: 5.0, 11: 5.0}
        bound = SV.eat_pin_taxi_bound(pins, AIRSIDE, RUNWAY_ANCHOR)
        refused = SV.eat_unroutable_rect_refusals(pins, {}, bound)
        assert set(refused) == {11}

    def test_everything_bound_refuses_nothing(self):
        pins = {3: 5.0, 4: 5.0}
        bound = SV.eat_pin_taxi_bound(pins, AIRSIDE, RUNWAY_ANCHOR)
        assert SV.eat_unroutable_rect_refusals(pins, {3: 1, 4: 1},
                                               bound) == {}

    def test_no_pins_is_the_inert_answer(self):
        assert SV.eat_unroutable_rect_refusals({}, {}, set()) == {}


class TestTheReleaseAndTheLine:
    def test_the_refused_pins_are_released_to_their_seed(self):
        """The release is the contradiction guard's own — one
        implementation, so a refused rect leaves a node in exactly the
        state ``_seed_elevations`` found it in."""

        class _L:
            pass

        layout = _L()
        layout._eat_anchor_pin_prev = {11: (3.25, False), 12: (3.5, True)}
        layout._eat_anchor_pin_idx = {11: 5.0, 12: 5.0}
        layout._seam_pin_idx = {11, 12}
        elev = [0.0] * 13
        elev[11] = elev[12] = 5.0
        base_hard = [False] * 13
        base_hard[11] = base_hard[12] = True
        have = [True] * 13
        n = SV.release_refused_eat_pins(layout, {11: 2, 12: 2}, elev,
                                        base_hard, have)
        assert n == 2
        assert elev[11] == 3.25 and elev[12] == 3.5
        assert not base_hard[11] and not base_hard[12]
        assert have[11] is False and have[12] is True
        assert layout._eat_anchor_pin_idx == {}
        assert layout._seam_pin_idx == set()

    def test_the_line_names_the_rects_and_the_reason(self):
        line = SV.format_eat_unroutable_line(
            "VHHH", {11: 2, 12: 2, 13: 3}, 41, 5)
        assert "[eat-anchor-rect] VHHH" in line
        assert "3 of 41 pin(s) REFUSED" in line
        assert "2 of 5 rect(s)" in line
        assert "[2, 3]" in line
        assert "NO taxi route" in line

    def test_the_line_elides_a_long_rect_list(self):
        line = SV.format_eat_unroutable_line(
            "VHHH", {i: i for i in range(40)}, 40, 40)
        assert "'...'" in line


class TestTheWiring:
    """The law is priced where the graph exists, before its sibling."""

    def test_the_route_law_runs_BEFORE_the_contradiction_guard(self):
        """An unroutable rect is not an EAT at all, so it is refused
        before anything asks whether its VALUE contradicts an anchor —
        otherwise the contradiction guard prices a facility that does
        not exist."""
        src = inspect.getsource(SV.solve_route_profile)
        assert (src.index("eat_unroutable_rect_refusals(")
                < src.index("eat_pin_contradiction_refusals("))

    def test_it_is_priced_on_the_AIRSIDE_view_of_the_graph(self):
        """The service pairs are what make a road a road: priced on the
        full graph, a perimeter road would route to the runway through a
        truck route and the law would be inert."""
        src = inspect.getsource(SV.solve_route_profile)
        call = src[src.index("eat_pin_taxi_bound("):]
        assert "u_spine_adj_airside" in call[:200]
        assert "u_spine_adj," not in call[:200]

    def test_it_needs_no_env_flag(self):
        """``EAT_SURFACE_CEILING`` stays the feature's only switch."""
        assert "environ" not in inspect.getsource(SV.eat_pin_taxi_bound)
        assert "environ" not in inspect.getsource(
            SV.eat_unroutable_rect_refusals)

    def test_the_rect_identity_is_published_with_the_pins(self):
        """Published in ONE statement beside ``_eat_anchor_pin_idx`` so
        the guard never has to guess whether it is stale — and never
        re-segmented at the guard site (a second spelling)."""
        from auto_patch.elevation_per_surface import solver_primitives as SP
        src = inspect.getsource(SP._seed_elevations)
        assert "layout._eat_anchor_pin_rect = dict(" in src
        guard = inspect.getsource(SV.solve_route_profile)
        assert "_eat_anchor_pin_rect" in guard

    def test_the_rect_identity_survives_a_probe_reseed(self):
        """It is published in the seeder's NODE-INDEX SPACE, so every
        list that fences the other published index maps must fence it
        too — else a probe leaves rect ids naming the probe's nodes."""
        assert "_eat_anchor_pin_rect" in SV._PROBE_PUBLISHED_ATTRS
