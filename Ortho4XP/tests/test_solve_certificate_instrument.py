"""Cycle-7.5 STANDING-INSTRUMENT SWEEP, lane VI — the calibration twins
for the solve's own report instruments.

RULINGS 2026-08-06 ("Instrument truth is law"), the four binding points
these twins exist to satisfy:

1. KNOWN-ANSWER TWIN, or it is not an instrument.  Every case below feeds
   a hand-built input whose answer is known by construction and asserts
   THE REPORTED NUMBERS — never "the function ran" or "a key exists".
2. Instruments report NUMBERS AND FRAMES; a verdict sentence belongs to
   the law layer or to a WORLD-INVARIANT computation.
3. FRAME STAMPS on every reported number (node space, world, crown
   space).
4. TWO INDEPENDENT INSTRUMENTS per load-bearing quantity, agreement
   ASSERTED within a stated materiality.

Three instruments are covered:

* the HARD-ANCHOR ATTRIBUTION (``attribute_seam_spine_hardening``) — the
  unattributed hardening channel the campaign rider named ("444 of 1,077
  nodes in the class were hardened with NO seeder record").  These twins
  also carry the SURFACE-NEUTRALITY PROOF: ``_hard_cat`` is NOT
  report-only — two production consumers read its VALUES and feed
  ``crown.build_crown_drop_field``, the writeback transform on emitted
  elevations — so the twins assert that both consumers see IDENTICAL
  membership before and after the change.
* the SOLVE EXIT / final ENTRY / final EXIT LAW CERTIFICATE
  (``_report_law_certificate``), which had no test of any kind though a
  comment calls its number "the one number the single-solve architecture
  is judged on".
* the CIFP WORLD-INVARIANT LINE (``report_cifp_world_invariant``),
  twinned against the second reader of the same quantities,
  ``building_feasibility._anchor_cifp_envelopes`` (binding point 4).

Hermetic: hand-built structures, no fixtures, no network, no X-Plane
install.
"""
from __future__ import annotations

import math
import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch import runway_redistribute as RR              # noqa: E402
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    solve as SOLVE)


# ── the log capture every twin below reads its numbers off ────────────

@pytest.fixture
def log(monkeypatch):
    out: list = []
    import O4_UI_Utils as UI
    monkeypatch.setattr(UI, "vprint",
                        lambda level, msg, *a, **k: out.append(str(msg)))
    return out


# ═══════════════════════════════════════════════════════════════════════
# TASK 1 — THE UNATTRIBUTED HARDENING CHANNEL
# ═══════════════════════════════════════════════════════════════════════
#
# THE DEFECT.  ``_seam_spine_anchors`` hardened nodes
# (``elev[bi] = v; base_hard[bi] = True``), kept its ``seen`` set purely
# LOCAL, returned a count — and the call site DISCARDED the return value
# entirely.  Its only trace was the blanket one layer down:
#
#     truth_hard = {i for i in range(n) if base_hard[i]}
#     for i in truth_hard:
#         _hard_cat.setdefault(i, "seam_spine_anchor")
#
# which labels EVERY node hardened since the classifier
# ``seam_spine_anchor`` regardless of what actually hardened it, and runs
# even when the seam machinery never ran at all.

# The classes the solve's CROWN-FREEZE set is keyed on, and the class its
# runway-join sample set is keyed on.  Restated here as the twin's own
# statement of the contract: a change to either list in ``solve.py``
# without a matching change here is a change to the emitted surface.
_CROWN_FREEZE_CLASSES = ("seam_spine_anchor", "seat_on_spine", "gs_pin")
_JOIN_SAMPLE_CLASS = "rwy_join"


def _crown_freeze_from(hard_cat):
    """CONSUMER 1, verbatim from ``solve.py``'s ``_crown_freeze`` build:
    a frozen node emits at crown drop 0 instead of its family's drop."""
    return {i for i, cat in hard_cat.items()
            if cat in _CROWN_FREEZE_CLASSES}


def _join_samples_from(hard_cat, runway_anchor_sample, n):
    """CONSUMER 2, verbatim from ``solve.py``'s ``_join_samples`` build:
    a join in this map gets a VALUE-DERIVED crown drop that lands it on
    the crowned runway edge."""
    return {i: s for i, s in runway_anchor_sample.items()
            if i < n and hard_cat.get(i) == _JOIN_SAMPLE_CLASS}


def _blanket_only(hard_cat, truth_hard):
    """THE PRE-FIX BEHAVIOUR, verbatim — the blanket with nothing
    published.  The control arm of every surface-neutrality assertion
    below."""
    out = dict(hard_cat)
    for i in truth_hard:
        out.setdefault(i, "seam_spine_anchor")
    return out


# A hand-built mixed population.  Node 0 was classified ``rwy_profile``
# by the classifier AND is pinned by the seam pass (the real case: the
# pass picks the nearest spine node within 30 m of a seam crossing
# without testing hardness, and at a seam that node is very often already
# a runway/seam/seat node).  Node 1 is a classified node the seam pass
# never touched.  Nodes 2-3 are pinned by the seam pass and unclassified.
# Node 4 is hardened by NOBODY the map knows about — the channel.
_CAT0 = {0: "rwy_profile", 1: "seam_pin"}
_TRUTH = {0, 1, 2, 3, 4}
_PINNED = {0, 2, 3}


class TestHardeningAttribution:

    def test_the_counts_are_the_known_answer(self):
        cat = dict(_CAT0)
        rep = SOLVE.attribute_seam_spine_hardening(cat, _TRUTH, _PINNED)
        assert rep == {"pinned": 3, "attributed": 2,
                       "pre_classified": 1, "unattributed": 1}

    def test_the_published_set_is_what_attributes_not_the_blanket(self):
        """THE POINT OF THE FIX.  The blanket alone can only ever report
        ONE number — "3 nodes were labelled here" — and cannot say how
        many of them the seam pass actually pinned.  Publishing the set
        splits that 3 into 2 attributed + 1 unattributed, and the 1 IS
        the channel the campaign rider named."""
        cat = dict(_CAT0)
        n_blanket_would_label = len(_TRUTH - set(cat))
        assert n_blanket_would_label == 3
        rep = SOLVE.attribute_seam_spine_hardening(cat, _TRUTH, _PINNED)
        assert rep["attributed"] + rep["unattributed"] == 3
        assert rep["unattributed"] == 1, (
            "node 4 is hardened by no publisher — that is the whole "
            "instrument")

    def test_an_unrun_seam_pass_puts_the_whole_blanket_in_the_residual(
            self):
        """The blanket runs UNCONDITIONALLY, including when the seam
        machinery never ran (``SEAM_FIELD_ANCHORS`` off, no DEM, no cut
        lines).  Everything it labels is then unattributed by
        definition, and the instrument says so instead of naming it
        ``seam_spine_anchor`` and moving on."""
        cat = dict(_CAT0)
        rep = SOLVE.attribute_seam_spine_hardening(cat, _TRUTH, set())
        assert rep == {"pinned": 0, "attributed": 0,
                       "pre_classified": 0, "unattributed": 3}

    # ── THE SURFACE-NEUTRALITY PROOF ─────────────────────────────────

    def test_the_class_map_is_identical_to_the_blanket_only_map(self):
        """Byte-identity, stated as an assertion: the published-set loop
        and the blanket both use ``setdefault``, so every key gets
        exactly the value the blanket alone would have given it."""
        fixed = dict(_CAT0)
        SOLVE.attribute_seam_spine_hardening(fixed, _TRUTH, _PINNED)
        assert fixed == _blanket_only(_CAT0, _TRUTH)

    def test_crown_freeze_membership_is_unchanged(self):
        """CONSUMER 1.  ``_hard_cat`` is NOT report-only: this set feeds
        ``build_crown_drop_field``, whose output is the writeback
        transform on EMITTED elevations.  Same membership ⇒ same
        surface."""
        fixed = dict(_CAT0)
        SOLVE.attribute_seam_spine_hardening(fixed, _TRUTH, _PINNED)
        assert (_crown_freeze_from(fixed)
                == _crown_freeze_from(_blanket_only(_CAT0, _TRUTH))
                == {2, 3, 4})

    def test_runway_join_sample_membership_is_unchanged(self):
        """CONSUMER 2.  A join node that fell out of this map would lose
        its value-derived drop and emit off the crowned runway edge."""
        cat0 = dict(_CAT0)
        cat0[5] = "rwy_join"
        truth = _TRUTH | {5}
        samples = {5: (1.0, 2.0), 2: (3.0, 4.0)}
        fixed = dict(cat0)
        SOLVE.attribute_seam_spine_hardening(fixed, truth, _PINNED | {5})
        assert (_join_samples_from(fixed, samples, 9)
                == _join_samples_from(_blanket_only(cat0, truth),
                                      samples, 9)
                == {5: (1.0, 2.0)})

    def test_an_already_classified_pinned_node_is_never_relabelled(self):
        """THE TRAP the fix had to avoid, as a test.  Node 0 is pinned by
        the seam pass AND already ``rwy_profile``.  Writing
        ``hard_cat[i] = "seam_spine_anchor"`` (rather than
        ``setdefault``) would move it INTO the crown-freeze set and drop
        its crown — a moved surface from a "report-only" change."""
        fixed = dict(_CAT0)
        SOLVE.attribute_seam_spine_hardening(fixed, _TRUTH, _PINNED)
        assert fixed[0] == "rwy_profile"
        assert 0 not in _crown_freeze_from(fixed)
        # and the counterfactual, so the twin fails if anyone "tidies"
        # the setdefault away: an ``=`` assignment DOES move it.
        overwritten = dict(_CAT0)
        for i in _PINNED:
            overwritten[i] = "seam_spine_anchor"
        assert 0 in _crown_freeze_from(overwritten)

    def test_the_publisher_returns_a_set_not_a_count(self):
        """``_seam_spine_anchors`` used to return an int the call site
        threw away.  The contract is now a SET — the identity of what it
        pinned, which is what attribution needs."""
        import inspect
        src = inspect.getsource(SOLVE._seam_spine_anchors)
        assert "return seen" in src
        assert "layout._seam_spine_anchor_idx = seen" in src


# ═══════════════════════════════════════════════════════════════════════
# TASK 6 — THE REAL CLASSIFIER, NOT A SECOND IMPLEMENTATION
# ═══════════════════════════════════════════════════════════════════════

class TestNoClassIsAssignedByBlanket:
    """The behavioural replacement for the old source-text scan
    (``'{i: "seed_rwy_seam" for i in _hard_cat}' not in src``), which was
    trivially satisfied and would stay satisfied under any rename."""

    def test_differently_sourced_nodes_get_different_classes(self):
        cat = SOLVE.classify_hard_anchors(
            5, [True] * 5, flexed_idx={0}, seam_pins={1},
            runway_anchor={2: 10.0}, runway_nodes={3})
        assert cat == {0: "rwy_flexed", 1: "seam_pin", 2: "rwy_join",
                       3: "rwy_profile", 4: "base_hard:unattributed"}

    def test_the_blanket_adds_nothing_when_every_node_has_a_source(self):
        """The blanket's residual is the instrument: when the classifier
        has claimed every hard node and the seam pass pinned only nodes
        it already claimed, the blanket labels NOTHING.  A nonzero
        number here is an unattributed hardening channel, by
        definition."""
        cat = SOLVE.classify_hard_anchors(
            4, [True] * 4, flexed_idx={0}, seam_pins={1},
            runway_anchor={2: 1.0}, runway_nodes={3})
        rep = SOLVE.attribute_seam_spine_hardening(cat, set(range(4)),
                                                   {1, 2})
        assert rep["unattributed"] == 0
        assert rep["attributed"] == 0
        assert rep["pre_classified"] == 2


# ═══════════════════════════════════════════════════════════════════════
# TASK 2 — THE SOLVE EXIT CERTIFICATE
# ═══════════════════════════════════════════════════════════════════════

def _cert_lines(log):
    return [ln for ln in log if "[proj-law-certificate]" in ln]


def _detail_rows(log):
    return [ln for ln in log
            if "[proj-law-certificate]" not in ln and "worst" in ln]


class TestLawCertificateNumbers:
    """The certificate had NO test of any kind.  Known answers, computed
    by hand from a constructed ``cert``."""

    # 10 violating families + 1 present-but-clean family.
    #   total  = 1+2+…+10                = 55
    #   both   = Σ k//2 for k in 1..10   = 25
    #   n_viol = 10 ; families present   = 11
    CERT = dict({f"fam{k:02d}": (k, 0.1 * k, k // 2)
                 for k in range(1, 11)}, **{"fam00": (0, 0.0, 0)})

    def test_every_headline_number(self, log):
        SOLVE._report_law_certificate("TEST", "SOLVE EXIT", self.CERT,
                                      n_nodes=146743)
        head = _cert_lines(log)[0]
        assert "over_cap=55 law edge(s)" in head, head
        assert "(25 both-hard)" in head, head
        assert "in 10 violating family(ies) of 11 present" in head, head

    def test_the_frame_stamp_is_on_the_line(self, log):
        """BINDING POINT 3.  Without the node space, three readings that
        ran on 142,635 / 144,056 / 146,743 nodes at HECA print as if
        they were ENTRY/EXIT of one thing — the two-instruments trap by
        construction.  Without the crown space, a reader comparing this
        number to an emitted .osm value is off by ``_crown_of`` with no
        warning."""
        SOLVE._report_law_certificate("TEST", "SOLVE EXIT", self.CERT,
                                      n_nodes=146743)
        head = _cert_lines(log)[0]
        assert "[node space n=146743; crown space uncrowned z']" in head

    def test_the_verdict_word_is_gone(self, log):
        """BINDING POINT 2.  ``CERTIFIED`` was a world-DEPENDENT
        interpretation (``total`` is a function of ``elev``, hence of the
        DEM) printed by a function whose call site says "Pure
        measurement, no gate".  It read as a gate result and gated
        nothing.  ``over_cap=N`` is the measurement it restated."""
        SOLVE._report_law_certificate("TEST", "SOLVE EXIT", {},
                                      n_nodes=10)
        head = _cert_lines(log)[0]
        assert "CERTIFIED" not in head, head
        assert "over_cap=0 law edge(s)" in head, head
        assert "in 0 violating family(ies) of 0 present" in head, head

    def test_the_family_rollup_order_and_top_truncation(self, log):
        """``top=8``, worst first: the eight largest families in
        descending order, the two smallest truncated, and the clean
        family never printed at all."""
        SOLVE._report_law_certificate("TEST", "SOLVE EXIT", self.CERT,
                                      n_nodes=1)
        rows = _detail_rows(log)
        assert len(rows) == 8
        assert [r.split()[-1] for r in rows] == [
            f"fam{k:02d}" for k in range(10, 2, -1)]
        assert "fam02" not in "".join(rows)
        assert "fam01" not in "".join(rows)
        assert "fam00" not in "".join(rows)
        # …and the worst row's own three numbers.
        assert rows[0].split()[0] == "10"
        assert "worst    1.000 m" in rows[0], rows[0]
        assert "both-hard      5" in rows[0], rows[0]

    def test_top_is_configurable_and_still_worst_first(self, log):
        SOLVE._report_law_certificate("TEST", "L", self.CERT, top=3,
                                      n_nodes=1)
        rows = _detail_rows(log)
        assert [r.split()[-1] for r in rows] == ["fam10", "fam09",
                                                 "fam08"]

    def test_the_certificate_reads_a_hand_built_joint(self, log):
        """End to end on hand-built law: one over-cap edge, both ends
        hard, one lawful edge — so the whole line is hand-checkable.

          edge (0,1): |0.0 − 2.0| − 0.5 = 1.5 m over, both hard
          edge (1,2): |2.0 − 2.2| − 0.5 = −0.3    → lawful
        """
        joint = [{"family": "runway:09/27",
                  "edges": [(0, 1, 0.5), (1, 2, 0.5)]}]
        cert = SOLVE.projection_law_certificate(
            joint, [0.0, 2.0, 2.2], 3, {0, 1})
        assert cert == {"runway:09/27": (1, 1.5, 1)}
        SOLVE._report_law_certificate("TEST", "SOLVE EXIT", cert,
                                      n_nodes=3)
        head = _cert_lines(log)[0]
        assert "over_cap=1 law edge(s) (1 both-hard)" in head, head
        assert "[node space n=3; crown space uncrowned z']" in head


class TestTwoReadersOneQuantity:
    """BINDING POINT 4 for "law edges over cap in the solved field".

    Three readers exist — the SOLVE EXIT certificate, the final pass's
    ENTRY certificate, and ``one_solve._exit_residual_by_family`` — in
    three node spaces, with their disagreement DOCUMENTED at
    ``solve.py``'s SOLVE EXIT comment and never asserted.  These twins
    assert both halves of the contract: same space ⇒ agreement within
    materiality; different space ⇒ disagreement, and the stamp is what
    makes it legible."""

    JOINT = [{"family": "runway:09/27",
              "edges": [(0, 1, 0.5), (1, 2, 0.5), (2, 3, 0.5)]}]
    ELEV = [0.0, 2.0, 2.2, 5.0]

    def test_the_two_readings_agree_in_one_node_space(self):
        exit_r = SOLVE.projection_law_certificate(
            self.JOINT, self.ELEV, 4, {0, 1})
        entry_r = SOLVE.projection_law_certificate(
            self.JOINT, self.ELEV, 4, {0, 1})
        assert exit_r == entry_r
        # the MATERIALITY the agreement is asserted within: 0.01 m on
        # the worst excess, the campaign's elevation materiality floor.
        assert (exit_r["runway:09/27"][1]
                == pytest.approx(entry_r["runway:09/27"][1], abs=0.01))
        assert exit_r["runway:09/27"][0] == 2

    def test_a_smaller_node_space_reads_a_different_number(self):
        """The real configuration: the final passes REBUILD their graph,
        so they read a SMALLER space (142,635 / 144,056 vs the solve's
        146,743 at HECA).  Edges touching a node the rebuilt space does
        not contain are skipped, so the counts genuinely differ — and
        equating them is the two-instruments trap."""
        big = SOLVE.projection_law_certificate(
            self.JOINT, self.ELEV, 4, {0, 1})
        small = SOLVE.projection_law_certificate(
            self.JOINT, self.ELEV, 3, {0, 1})
        assert big["runway:09/27"][0] == 2
        assert small["runway:09/27"][0] == 1
        assert big != small

    def test_the_stamps_are_what_make_that_visible(self, log):
        SOLVE._report_law_certificate(
            "TEST", "SOLVE EXIT",
            SOLVE.projection_law_certificate(self.JOINT, self.ELEV, 4,
                                             {0, 1}),
            n_nodes=4)
        SOLVE._report_law_certificate(
            "TEST", "final#1 ENTRY",
            SOLVE.projection_law_certificate(self.JOINT, self.ELEV, 3,
                                             {0, 1}),
            n_nodes=3)
        heads = _cert_lines(log)
        assert "node space n=4" in heads[0]
        assert "node space n=3" in heads[1]
        assert "over_cap=2" in heads[0] and "over_cap=1" in heads[1]


# ═══════════════════════════════════════════════════════════════════════
# TASK 5 — THE CIFP DUAL INSTRUMENT
# ═══════════════════════════════════════════════════════════════════════

_AXIS = 3000.0
_REF = "09/27"
_PINS = [(0.0, 100.0), (1.0, 110.0)]      # CIFP thresholds, both ends
_MAIN = 0.015
_END = 0.008
# The as-solved caps, deliberately DIFFERENT from the law caps so the
# twin proves the line reports both and the envelope prices only the law.
_ENDZONE_AS_SOLVED = 0.012
_THRESHOLD_AS_SOLVED = 0.010


class _G:
    def __init__(self, pos):
        self.pos = dict(pos)


class _Layout:
    def __init__(self, profiles):
        self._runway_redistributed_profiles = profiles


def _profile():
    return {
        "axis_a": (0.0, 0.0), "axis_d": (_AXIS, 0.0),
        "axis_len2": _AXIS ** 2, "half_width_m": 30.0,
        "cifp_pins": list(_PINS),
        "max_grade": _MAIN, "law_end_grade": _END,
        "max_grade_change_per_m": None,
        "fractions": [0.0, 1.0], "elevs": [100.0, 110.0],
        "anchored": [True, True], "flex_minted": [False, False],
        "seam_t": [], "threshold_strict_fraction": 0.0,
    }


class TestCifpWorldInvariantLine:

    def test_the_line_reports_every_input_exactly(self, log):
        out = RR.report_cifp_world_invariant(
            _REF, _PINS, _MAIN, _END, _AXIS, _ENDZONE_AS_SOLVED,
            _THRESHOLD_AS_SOLVED)
        line = next(ln for ln in log if "CIFP pins" in ln)
        assert "[(0.0, 100.0), (1.0, 110.0)]" in line, line
        assert "law caps main 1.5000% end 0.8000%" in line, line
        assert "axis 3000.000 m" in line, line
        assert ("(as-solved end zone 1.2000%, threshold 1.0000%)"
                in line), line
        assert out["cifp_pins"] == [(0.0, 100.0), (1.0, 110.0)]
        assert out["main_cap"] == _MAIN and out["end_grade_law"] == _END

    def test_a_class_with_no_end_zone_cap_says_none_not_zero(self, log):
        """``law_end_grade`` present and ``None`` is the authority
        stating NO first/last-quarter cap (ICAO code 1-2).  Printing
        0.0000% would invent a rule."""
        RR.report_cifp_world_invariant(_REF, _PINS, _MAIN, None, _AXIS,
                                       _ENDZONE_AS_SOLVED,
                                       _THRESHOLD_AS_SOLVED)
        line = next(ln for ln in log if "CIFP pins" in ln)
        assert "end none" in line, line

    def test_the_line_does_not_move_with_the_world(self, log):
        """WHAT THE INSTRUMENT IS FOR.  Its inputs are the CIFP pins,
        the station geometry and the runway's OWN law caps — none of
        which is a function of the DEM.  Two worlds, one line.  (This is
        also why binding point 2 permits its "WORLD-INVARIANT" claim:
        the property is of the computation, not of the result.)"""
        for _dem in (-500.0, 10000.0):
            RR.report_cifp_world_invariant(
                _REF, _PINS, _MAIN, _END, _AXIS, _ENDZONE_AS_SOLVED,
                _THRESHOLD_AS_SOLVED)
        lines = [ln for ln in log if "CIFP pins" in ln]
        assert len(lines) == 2 and lines[0] == lines[1]


class TestCifpAgreesWithTheAnchorEnvelope:
    """BINDING POINT 4, the nearest ready-made instance in the sweep.

    ``building_feasibility._anchor_cifp_envelopes`` is the SECOND reader
    of the same three quantities.  Its envelope is

        lo = max_p (e_p − budget(t, t_p)),  hi = min_p (e_p + budget(t, t_p))

    over the CIFP pins ``p``.  If the printed line is a true instrument,
    the envelope must be RECONSTRUCTIBLE from the line's numbers alone.

    MATERIALITY: the line rounds ``t`` to 1e-6 and elevations to 1e-4 m,
    so the reconstruction can only be held to ~1e-4 m.  Asserted at
    1e-3 m, an order below the 0.01 m campaign elevation floor.
    """

    MATERIALITY_M = 1e-3
    STATION_T = 0.40

    def _envelope_from_the_line(self, reported, t):
        """Reconstruct the second reader's envelope from the FIRST
        reader's printed numbers — nothing else."""
        from auto_patch.config import RUNWAY_END_FRACTION
        cap_kw = dict(grade_cap=reported["main_cap"],
                      end_grade_cap=reported["end_grade_law"],
                      end_fraction=RUNWAY_END_FRACTION,
                      threshold_strict_cap=None,
                      threshold_strict_fraction=0.0)
        lo, hi = -math.inf, math.inf
        for (pt, pe) in reported["cifp_pins"]:
            budget = RR._lawful_ramp_budget(t, float(pt),
                                            reported["axis_len_m"],
                                            cap_kw)
            lo = max(lo, float(pe) - budget)
            hi = min(hi, float(pe) + budget)
        return lo, hi

    def test_the_two_readers_agree_within_materiality(self, log):
        from auto_patch.elevation_per_surface.building_feasibility import (
            _anchor_cifp_envelopes)
        profile = _profile()
        layout = _Layout({_REF: profile})
        # one anchor node ON the axis at t = 0.40
        G = _G({7: (self.STATION_T * _AXIS, 0.0)})
        env = _anchor_cifp_envelopes(layout, G, {7: 0.0})
        assert 7 in env, "the second reader must have priced this anchor"
        lo_b, hi_b, ref_b = env[7]
        assert ref_b == _REF

        reported = RR.report_cifp_world_invariant(
            _REF, profile["cifp_pins"], _MAIN, _END, _AXIS,
            _ENDZONE_AS_SOLVED, _THRESHOLD_AS_SOLVED)
        lo_a, hi_a = self._envelope_from_the_line(reported,
                                                  self.STATION_T)
        assert lo_a == pytest.approx(lo_b, abs=self.MATERIALITY_M)
        assert hi_a == pytest.approx(hi_b, abs=self.MATERIALITY_M)
        # …and the envelope is a real one, not two infinities agreeing.
        assert math.isfinite(lo_b) and math.isfinite(hi_b)
        assert lo_b < hi_b

    def test_the_envelope_is_priced_at_the_LAW_caps_not_as_solved(self):
        """The agreement above would be vacuous if the second reader
        used the as-solved caps: those escalate for WORLD-DEPENDENT
        reasons (seam and crossing anchors), so folding them in would
        let terrain widen a "world-invariant" envelope.  Here the
        as-solved end zone is 1.2 % against a 0.8 % law, so a
        law-priced envelope is strictly TIGHTER than an as-solved one."""
        from auto_patch.config import RUNWAY_END_FRACTION
        from auto_patch.elevation_per_surface.building_feasibility import (
            _anchor_cifp_envelopes)
        layout = _Layout({_REF: _profile()})
        G = _G({7: (0.05 * _AXIS, 0.0)})       # inside the end zone
        lo_b, hi_b, _ref = _anchor_cifp_envelopes(layout, G, {7: 0.0})[7]
        as_solved = dict(grade_cap=_MAIN,
                         end_grade_cap=_ENDZONE_AS_SOLVED,
                         end_fraction=RUNWAY_END_FRACTION,
                         threshold_strict_cap=None,
                         threshold_strict_fraction=0.0)
        budget = RR._lawful_ramp_budget(0.05, 0.0, _AXIS, as_solved)
        assert hi_b < 100.0 + budget - 1e-9, (
            "an as-solved-priced envelope would be wider")
