"""A REFUSED EAT PIN CONTRIBUTES NOTHING — the band at its site must be
the band it would have been with NO EAT pin at all.

THE SITE (KDFW +32-098, wave-3 triage 2026-08-20, dossier
``docs/triage/KAFW-KDFW-20260820.md`` §2.4 / §4).  At 18L/36R's south end
the anchor-rect pins sit at 196.824 m against the runway's CIFP 175.26.
Both scoping guards fired — 8 of 72 pins refused, "released to their
seed" — and 134 of 284 airside rows (worst 21.74 m) shipped at that one
site anyway, off an INVERTED band ``[196.824, 175.943]`` the writeback
clamped 72 solved values into.  ``O4_EAT_SURFACE_CEILING=0`` took airside
284 → 145 and the site's rows to 0.

THE LAW, in two halves — and the instrumented build (2026-08-21, per pin)
put the weight on the SECOND, against the dossier's reading:

1. **A pin the guards REFUSE is NO authority.**  Refusal must remove it
   from every consumer, and the reach band (``reach_band_unified`` →
   ``spine_value_fields``, seeded from ``G.runway_anchor``) is the one
   that matters: an entry there is a floor AND ceiling source at that
   node, at distance 0.  The classes below prove this half HOLDS on the
   release path as built — KDFW's three refused pins came back with no
   value, no hardness and no anchor entry.
2. **A pin the guard cannot PRICE is not thereby lawful.**  The
   predicate runs on ``build_anchor_envelope``, a Dijkstra over the
   SPINE adjacency, so a pin off the spine graph has no box and
   ``violation`` returns ``None``.  At the south rect the envelope
   prices 3 of the 19 pins carrying 196.824 and refuses all three; the
   other 16 kept full authority, and one of them (node 3316) authored
   the inverted band.  ``eat_rect_value_refusals`` closes that: the rect
   is pinned FLAT at ONE value, so a contradiction priced anywhere on it
   condemns the value everywhere it is stamped.

The arms below are the same graph three ways — no pin, a REFUSED pin, an
ACCEPTED pin — and they drive production's own functions end to end:
``eat_pin_contradiction_refusals`` (the guard), ``release_refused_eat_pins``
(the release), ``register_eat_anchors`` (the band registration) and
``spine_value_fields`` (the band).  Nothing is re-spelled locally.

Headless: no DEM, no network, no X-Plane install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from auto_patch.elevation_per_surface.building_feasibility import (  # noqa: E402
    assert_no_final_band_inversion, spine_value_fields)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    solve as SV)

# KDFW's own numbers (dossier §2.4): the runway's CIFP anchor, the
# regulation pin the rect carried, and a route budget short enough that
# the two cannot reconcile.
RUNWAY_VALUE = 175.290
PIN_VALUE = 196.824
ROUTE_BUDGET = 0.653          # 43.5 m of taxiway at the 1.5 % cap
#: What the guard's ceiling — and the band's — is at the pinned node.
CEILING_AT_PIN = RUNWAY_VALUE + ROUTE_BUDGET     # 175.943


class _G:
    """Minimal unified-graph stand-in — the attributes
    ``spine_value_fields`` and the guards read."""

    def __init__(self):
        # 0 = the runway-join anchor (hard, senior); 1 = a free corridor
        # node; 2 = the EAT rect node the pin lands on.
        self.runway_anchor = {0: RUNWAY_VALUE}
        self.spine_adj = {
            0: [(1, 0.4)],
            1: [(0, 0.4), (2, 0.253)],
            2: [(1, 0.253)],
        }
        self.pos = {0: (0.0, 0.0), 1: (26.7, 0.0), 2: (43.5, 0.0)}
        self.service_spine_pairs = set()


class _CPS:
    """The canonical-point registry's MEASUREMENT query only — the
    refusal publication joins on ``cps.get(x, y)`` and nothing here
    interns anything, so the position tuple IS the key (exact by
    construction in a hermetic test; see ``_hard_truth_spine_seeds``)."""

    @staticmethod
    def get(x, y):
        return (float(x), float(y))


class _Layout:
    """Enough layout for ``_decrowned_anchor_seeds`` (no crown field ⇒
    0.0 drop) and for the hard-truth join's registry-less fallback."""

    def __init__(self):
        self.shapes = []
        self.anchor = (0.0, 0.0)
        self.canonical_points = _CPS()


def _fresh_state():
    """The solve's state at the guard site: ``nodes``, ``elev``,
    ``base_hard``, ``have_initial`` with the runway anchor hard at its
    CIFP value and the rect node soft on its DEM seed."""
    G = _G()
    layout = _Layout()
    nodes = [G.pos[i] for i in (0, 1, 2)]
    elev = [RUNWAY_VALUE, 175.4, 175.6]        # node 2's DEM seed
    base_hard = [True, False, False]
    have_initial = [True, False, False]
    return G, layout, nodes, elev, base_hard, have_initial


def _seed_eat_pin(layout, elev, base_hard, have_initial, pins):
    """``_seed_elevations``' EAT stanza, verbatim in contract
    (solver_primitives.py, "EAT ANCHOR-RECT hard pins"): snapshot
    ``(elev, have_initial)`` per pinned node FIRST, then stamp value +
    hard + have_initial, publish the index map, and join the seam-pin
    protection set."""
    layout._eat_anchor_pin_prev = {
        i: (float(elev[i]), bool(have_initial[i])) for i in pins}
    for i, v in pins.items():
        elev[i] = float(v)
        base_hard[i] = True
        have_initial[i] = True
    layout._eat_anchor_pin_idx = dict(pins)
    layout._seam_pin_idx = set(getattr(layout, "_seam_pin_idx", None)
                               or ()) | set(pins)


def _senior_values(G, elev, base_hard):
    """The guard's senior anchor set, as the call site builds it."""
    return {i: float(elev[i]) for i in G.spine_adj
            if i < len(base_hard) and base_hard[i]}


def _publish_hard_truth(layout, G, elev, base_hard):
    """The solve's HARD TRUTH publication (solve.py, "HARD TRUTH
    PUBLICATION"), keyed by point — the registry-less join the hermetic
    tests use, which ``_hard_truth_spine_seeds`` documents as exact here
    by construction."""
    layout._seed_hard_truth_values = {
        G.pos[i]: float(elev[i]) for i in G.spine_adj
        if i < len(base_hard) and base_hard[i]}


def _band(layout, G, elev, base_hard, pins):
    """One arm's band: publish the hard truth, register the SURVIVING
    pins as band anchors through production's own registration, then
    build the value fields."""
    _publish_hard_truth(layout, G, elev, base_hard)
    SV.register_eat_anchors(G, pins, len(elev))
    ceiling, floor = spine_value_fields(layout, G)
    return {i: (floor.get(i), ceiling.get(i)) for i in G.spine_adj}


# ── the three arms ───────────────────────────────────────────────────────

def _arm_no_pin():
    G, layout, _nodes, elev, base_hard, _hi = _fresh_state()
    return _band(layout, G, elev, base_hard, {}), layout


def _arm_refused():
    G, layout, nodes, elev, base_hard, have_initial = _fresh_state()
    _seed_eat_pin(layout, elev, base_hard, have_initial, {2: PIN_VALUE})
    refused = SV.eat_pin_contradiction_refusals(
        layout._eat_anchor_pin_idx, G.spine_adj,
        _senior_values(G, elev, base_hard))
    assert refused, ("the arm is only a test of the refusal path if the "
                     "guard actually refuses — KDFW's numbers must fire")
    SV.release_refused_eat_pins(layout, refused, elev, base_hard,
                                have_initial)
    SV.publish_eat_refusal_keys(layout, refused, nodes)
    return (_band(layout, G, elev, base_hard,
                  layout._eat_anchor_pin_idx),
            layout, elev, base_hard, have_initial, refused)


def _arm_accepted(value):
    G, layout, _nodes, elev, base_hard, have_initial = _fresh_state()
    _seed_eat_pin(layout, elev, base_hard, have_initial, {2: value})
    refused = SV.eat_pin_contradiction_refusals(
        layout._eat_anchor_pin_idx, G.spine_adj,
        _senior_values(G, elev, base_hard))
    assert not refused, "this arm's pin must be LAWFUL"
    return (_band(layout, G, elev, base_hard,
                  layout._eat_anchor_pin_idx),
            layout, elev, base_hard)


# ── (a) A REFUSED PIN CONTRIBUTES NOTHING ────────────────────────────────

class TestARefusedPinContributesNothing:

    def test_the_guard_refuses_KDFWs_pin_against_KDFWs_runway(self):
        """The fixture is the defect's own arithmetic: 196.824 is
        21.2 m past a ceiling of 175.943 over 0.653 m of route budget."""
        _band_out, _layout, _elev, _bh, _hi, refused = _arm_refused()
        assert set(refused) == {2}
        assert refused[2]["side"] == "ceiling"
        assert refused[2]["bound"] == pytest.approx(CEILING_AT_PIN)
        assert refused[2]["witness"] == 0
        assert refused[2]["excess_m"] == pytest.approx(
            PIN_VALUE - CEILING_AT_PIN)

    def test_the_band_is_IDENTICAL_to_the_band_with_no_EAT_pin(self):
        """THE LAW.  Value-identical at every node — not "close", not
        "clamped back": the refused pin is not an authority, so the field
        it must produce is the field of an airport that never had it."""
        no_pin, _l0 = _arm_no_pin()
        refused_arm, *_rest = _arm_refused()
        assert refused_arm == no_pin

    def test_the_pinned_node_keeps_its_own_runway_derived_band(self):
        """Named explicitly so a regression reads as the CLASS: the rect
        node's band is the runway's, propagated at cap — never the pin's
        own value at distance 0."""
        refused_arm, *_rest = _arm_refused()
        lo, hi = refused_arm[2]
        assert lo == pytest.approx(RUNWAY_VALUE - ROUTE_BUDGET)
        assert hi == pytest.approx(CEILING_AT_PIN)

    def test_the_release_restores_the_seeders_own_state(self):
        """The release's contract (``release_refused_eat_pins``): the
        node comes back an ORDINARY SOFT node on its DEM seed — not a
        phase-A truth anchor, not a reach-band anchor, not seam-
        protected."""
        _b, layout, elev, base_hard, have_initial, _r = _arm_refused()
        _G0, _l0, _n0, elev0, hard0, hi0 = _fresh_state()
        assert elev == elev0
        assert base_hard == hard0
        assert have_initial == hi0
        assert 2 not in layout._eat_anchor_pin_idx
        assert 2 not in layout._seam_pin_idx

    def test_the_refused_pin_is_not_a_band_anchor(self):
        """The mechanism, stated where a reader will look for it: the
        band's authority set is ``G.runway_anchor``, and the refused pin
        may not appear in it at ANY value."""
        _b, layout, elev, _bh, _hi, _r = _arm_refused()
        G = _G()
        SV.register_eat_anchors(G, layout._eat_anchor_pin_idx, len(elev))
        assert G.runway_anchor == {0: RUNWAY_VALUE}

    def test_the_verdict_is_CARRIED_so_a_re_seed_cannot_re_pin_it(self):
        """``_seed_elevations`` runs again at every later pass on a GROWN
        layout; the carried key set is the only thing standing between a
        refused pin and its own resurrection."""
        _b, layout, _e, _bh, _hi, _r = _arm_refused()
        assert getattr(layout, "_eat_pin_refused_keys", None), (
            "the refusal must be published for the later re-seeds")


# ── (b) AN ACCEPTED PIN STILL SEEDS EXACTLY AS TODAY ─────────────────────

class TestAnAcceptedPinIsUnchanged:

    def test_a_lawful_pin_stands_and_seeds_the_band_at_its_own_value(self):
        """The falsifier for (a): the law refuses CONTRADICTIONS, never
        the feature.  A pin inside the senior envelope keeps every bit of
        its authority — it is a band anchor at distance 0, so the band at
        its node is its own value on BOTH sides."""
        band, layout, _elev, _bh = _arm_accepted(RUNWAY_VALUE + 0.2)
        assert 2 in layout._eat_anchor_pin_idx
        lo, hi = band[2]
        assert lo == pytest.approx(RUNWAY_VALUE + 0.2)
        assert hi == pytest.approx(RUNWAY_VALUE + 0.2)

    def test_a_lawful_pin_propagates_outward_at_cap(self):
        """And it binds its NEIGHBOURS at ``E_anchor ± cap·d``, which is
        what the feature is FOR — the descent/climb ramps the solver
        grades.  The corridor node between the runway and the rect gets
        its floor from the pin, 0.253 m of budget away."""
        band, _layout, _elev, _bh = _arm_accepted(RUNWAY_VALUE + 0.2)
        no_pin, _l0 = _arm_no_pin()
        lo1, _hi1 = band[1]
        assert lo1 == pytest.approx(RUNWAY_VALUE + 0.2 - 0.253)
        assert lo1 > no_pin[1][0]

    def test_the_accepted_arm_is_NOT_the_no_pin_arm(self):
        """Without this the (a) twin would pass for a build that had
        simply deleted the feature."""
        no_pin, _l0 = _arm_no_pin()
        accepted, _l1, _e, _bh = _arm_accepted(RUNWAY_VALUE + 0.2)
        assert accepted != no_pin


# ── (c) THE INVERTED BAND CANNOT SURVIVE A REFUSAL ───────────────────────

class TestNoInvertedBandAfterARefusal:

    def test_a_seed_above_the_CIFP_ceiling_cannot_invert_the_band(self):
        """KDFW's shipped signature was ``band [196.824, 175.943]`` —
        floor ABOVE ceiling at a node whose own runway truth is 21 m
        lower.  After the refusal no inversion of any class may stand."""
        band, layout, *_rest = _arm_refused()
        lo, hi = band[2]
        assert lo <= hi, ("floor above ceiling at the EAT site is the "
                          "KDFW signature — the refusal did not hold")
        assert assert_no_final_band_inversion(layout, "TEST") == 0
        assert layout._final_band_inversions == []

    def test_an_OFF_SPINE_rect_mate_cannot_keep_the_condemned_value(self):
        """THE KDFW SHAPE, end to end (dossier §2.4 + the instrumented
        2026-08-21 read).  The rect is pinned FLAT at 196.824; ONE of its
        three nodes carries a spine edge, so the per-node predicate can
        price only that one.  Before the rect-value law the other two
        kept full authority and one of them authored the band.

        Node 3 here is the off-spine mate: it is in ``pins`` and in the
        rect, and it has NO envelope box at all."""
        G, layout, nodes, elev, base_hard, have_initial = _fresh_state()
        # node 3 — an EAT rect vertex OFF the spine graph (no entry in
        # ``spine_adj``), exactly like KDFW's 3316.
        G.pos[3] = (43.5, 12.0)
        nodes = nodes + [G.pos[3]]
        elev.append(175.6)
        base_hard.append(False)
        have_initial.append(False)
        _seed_eat_pin(layout, elev, base_hard, have_initial,
                      {2: PIN_VALUE, 3: PIN_VALUE})
        layout._eat_anchor_pin_rect = {2: 1, 3: 1}
        unbounded: set = set()
        priced = SV.eat_pin_contradiction_refusals(
            layout._eat_anchor_pin_idx, G.spine_adj,
            _senior_values(G, elev, base_hard),
            unbounded_out=unbounded)
        assert set(priced) == {2}, "only the on-spine pin can be priced"
        assert unbounded == {3}, ("the off-spine pin carries NO bound — "
                                  "the silence the law closes")
        extended = SV.eat_rect_value_refusals(
            layout._eat_anchor_pin_idx, layout._eat_anchor_pin_rect,
            priced)
        assert set(extended) == {2, 3}
        assert extended[3]["via_rect"] == 2
        assert extended[3]["excess_m"] == pytest.approx(
            priced[2]["excess_m"])
        SV.release_refused_eat_pins(layout, extended, elev, base_hard,
                                    have_initial)
        assert layout._eat_anchor_pin_idx == {}
        SV.register_eat_anchors(G, layout._eat_anchor_pin_idx, len(elev))
        assert G.runway_anchor == {0: RUNWAY_VALUE}, (
            "no node of the condemned rect may be a band anchor")

    def test_the_UNGUARDED_pin_is_what_inverts_it_the_control(self):
        """The control that proves the twin can fail: with the SAME pin
        left standing (no guard, no release) the band inverts exactly as
        KDFW's build reported it.  Without this arm the test above would
        pass for a band that had stopped being computed."""
        G, layout, _nodes, elev, base_hard, have_initial = _fresh_state()
        _seed_eat_pin(layout, elev, base_hard, have_initial,
                      {2: PIN_VALUE})
        band = _band(layout, G, elev, base_hard,
                     layout._eat_anchor_pin_idx)
        lo, hi = band[2]
        assert lo == pytest.approx(PIN_VALUE)
        assert hi == pytest.approx(CEILING_AT_PIN)
        assert lo > hi                       # INVERTED — KDFW's signature
        with pytest.raises(Exception):
            assert_no_final_band_inversion(layout, "TEST")


# ── (d) THE RECT'S VALUE IS ONE VALUE ────────────────────────────────────

class TestTheRectValueLaw:
    """:func:`eat_rect_value_refusals` — the FACILITY carries the verdict."""

    PINS = {1: 196.824, 2: 196.824, 3: 196.824, 7: 174.522, 8: 174.522}
    RECTS = {1: 1, 2: 1, 3: 1, 7: 2, 8: 2}

    def _priced(self, nodes):
        return {i: {"side": "ceiling", "excess_m": 20.0 + i,
                    "bound": 175.9, "witness": 0,
                    "route_budget_m": 0.6} for i in nodes}

    def test_one_priced_contradiction_condemns_its_whole_rect(self):
        out = SV.eat_rect_value_refusals(self.PINS, self.RECTS,
                                         self._priced([2]))
        assert set(out) == {1, 2, 3}
        assert out[1]["via_rect"] == 2 and out[3]["via_rect"] == 2
        assert "via_rect" not in out[2], "the priced pin is not derived"

    def test_rects_are_judged_INDEPENDENTLY(self):
        """The falsifier: a lawful rect beside a condemned one keeps
        every pin — KDFW's other three rects are priced, sit inside their
        envelopes and must be untouched."""
        out = SV.eat_rect_value_refusals(self.PINS, self.RECTS,
                                         self._priced([2]))
        assert 7 not in out and 8 not in out

    def test_NO_priced_contradiction_refuses_NOTHING(self):
        """No witness, no verdict — the law never invents a refusal for a
        rect the predicate did not condemn."""
        assert SV.eat_rect_value_refusals(self.PINS, self.RECTS, {}) == {}

    def test_the_WORST_priced_contradiction_is_the_rects_witness(self):
        out = SV.eat_rect_value_refusals(self.PINS, self.RECTS,
                                         self._priced([1, 3]))
        assert out[2]["via_rect"] == 3, "excess 23.0 beats 21.0"
        assert out[2]["excess_m"] == pytest.approx(23.0)

    def test_a_pin_with_no_rect_identity_is_its_OWN_rect(self):
        """The unroutable law's convention, so a missing publication can
        only ever refuse LESS."""
        out = SV.eat_rect_value_refusals({4: 196.824, 5: 196.824}, {},
                                         self._priced([4]))
        assert set(out) == {4}

    def test_the_loud_line_names_the_unpriceable_population(self):
        line = SV.format_eat_rect_value_line("KDFW", 61, 1, 61)
        assert line.count("\n") == 0, "ONE loud line, not a report"
        assert "61 further pin(s) over 1 rect(s) REFUSED WITH THEM" in line
        assert "61 of them carry NO senior-anchor bound at all" in line
        assert "released to their seed." in line


class TestTheRectValueWiring:

    def test_the_extension_sits_between_the_predicate_and_the_release(self):
        """THE WIRING, which no unit call can show: the rect-value law
        must run on the PRICED verdict and before the release, so the
        release, the carried keys and the loud line all see one verdict."""
        import inspect
        src = inspect.getsource(SV.solve_route_profile)
        at_priced = src.index("_eat_priced = eat_pin_contradiction_refusals(")
        at_rect = src.index("_eat_refused = eat_rect_value_refusals(")
        at_release = src.index("_n_released = release_refused_eat_pins(")
        at_publish = src.index("publish_eat_refusal_keys(layout, _eat_refused")
        assert at_priced < at_rect < at_release < at_publish

    def test_the_law_needs_no_env_flag(self):
        """``EAT_SURFACE_CEILING`` stays the feature's only switch."""
        import inspect
        assert "environ" not in inspect.getsource(
            SV.eat_rect_value_refusals)
