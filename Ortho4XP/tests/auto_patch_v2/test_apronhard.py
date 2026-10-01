"""§5a FEASIBILITY BEFORE THE SOLVE (flat-pad spec v2 §5 / §5a; owner
RULINGS 2026-09-30be, ratified 30bf; ``solve/feasibility.py``).

Twins: a synthetic infeasible pair NAMES ITSELF (the relaxed rows are
reported with the law they conflict with, and the relaxed count equals the
conflict count); the LAW HIERARCHY decides which member relaxes (pad hold
under the apron cap, the apron cap under a taxi cap, never a runway row);
a conflict only a runway row could absorb RAISES; the apron heads are HARD
and ranked; ``plane_gradient`` is hard on an apron face only.
"""
from __future__ import annotations

import types

import numpy as np
import pytest
import scipy.sparse as sp

from auto_patch_v2.law import tables as T
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.solve import feasibility as F

APRON = "common.roles.apron ring edge"
PAD = "structures.building_pad frontage_hold"
TAXI = "rulesets.taxi.longitudinal centreline"
RUNWAY = "rulesets.runway.longitudinal"
GROUND = "road_cross_section"
STRICT = "apron body chord, strict"


@pytest.fixture(scope="module")
def law():
    return T.load_default()


class _Row:
    def __init__(self, head: str):
        self.source = Source("test", f"{head} (twin)", ("face:1", "objpav402"))


def _planar(n: int):
    vs = {i: types.SimpleNamespace(key=(30.0 + i * 1e-4, 31.0)) for i in range(n)}
    return types.SimpleNamespace(vertices=vs)


def _problem(rows):
    """``rows`` = [(head, {col: coef}, rhs)] over columns 0..n-1 (one vertex
    per column)."""
    n = 1 + max(c for _h, t, _b in rows for c in t)
    one, data, ii, jj, b = [], [], [], [], []
    for k, (head, terms, rhs) in enumerate(rows):
        one.append((tuple(terms.items()), rhs, _Row(head)))
        for c, w in terms.items():
            ii.append(k); jj.append(c); data.append(w)
        b.append(rhs)
    A = sp.csr_matrix((data, (ii, jj)), shape=(len(rows), n))
    return one, A, np.asarray(b, float), _planar(n)


def test_infeasible_pair_names_itself_and_the_pad_relaxes(law):
    # apron cap: x1 - x0 <= 1.5 ; the pad hold: x0 <= 0 and x1 >= 5
    one, A, b, pl = _problem([(APRON, {1: 1.0, 0: -1.0}, 1.5),
                              (PAD, {0: 1.0}, 0.0),
                              (PAD, {1: -1.0}, -5.0)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(3), A, b, stage="1")
    assert rep.status == "optimal"
    assert rep.relaxed == len(demote) == len(rep.conflicts) >= 1
    assert set(int(k) for k in demote) <= {1, 2}         # never the apron row
    assert rep.by_tier == {"pad": rep.relaxed}
    # 3.5 m of relief the pad rows must give up, read in each row's OWN
    # metres (``row_metre_scale`` = 2 / Σ|c|: 2 for a one-term twin row)
    total = sum(c["s_m"] for c in rep.conflicts)
    assert total == pytest.approx(2 * 3.5, abs=1e-6)
    for c in rep.conflicts:
        assert c["row"] == PAD and c["tier"] == "pad"
        assert APRON in c["against"]                     # BOTH laws named
        assert c["site"] and c["stage"] == "1"


def test_feasible_set_relaxes_nothing(law):
    one, A, b, pl = _problem([(APRON, {1: 1.0, 0: -1.0}, 1.5),
                              (PAD, {0: 1.0}, 0.0),
                              (PAD, {1: -1.0}, -1.0)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(3), A, b)
    assert demote.size == 0 and rep.relaxed == 0 and not rep.conflicts


def test_taxi_vs_apron_relaxes_the_apron_rows(law):
    # a taxi cap pins the step x1 - x0 >= 4; two apron chords cap it at 1.5
    one, A, b, pl = _problem([(TAXI, {0: 1.0, 1: -1.0}, -4.0),
                              (APRON, {1: 1.0, 0: -1.0}, 1.5),
                              (APRON, {1: 1.0, 0: -1.0}, 2.0)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(3), A, b)
    assert set(int(k) for k in demote) == {1, 2}
    assert rep.by_tier == {"apron": 2} and rep.relaxed == 2


def test_runway_row_is_never_relaxed(law):
    # the runway holds x0 = 0 .. the apron yields to it
    one, A, b, pl = _problem([(RUNWAY, {0: 1.0}, 0.0), (RUNWAY, {0: -1.0}, 0.0),
                              (APRON, {0: -1.0}, -3.0)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(3), A, b)
    assert [int(k) for k in demote] == [2]
    assert rep.conflicts[0]["against"].get(RUNWAY)


def test_a_runway_only_conflict_is_named_never_relaxed(law):
    # §7: a conflict only a runway row could absorb is NAMED and the runway
    # row stays hard (the runway machinery owns it) — never demoted
    one, A, b, pl = _problem([(RUNWAY, {0: 1.0}, 0.0),
                              (RUNWAY, {0: -1.0}, -1.0),
                              (APRON, {1: 1.0, 0: -1.0}, 1.5)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(3), A, b)
    assert demote.size == 0 and rep.relaxed == 0
    assert rep.runway_conflict == 1 and "runway" in rep.runway_rows[0]
    assert "RUNWAY" in rep.line()


def test_a_pad_vs_apron_conflict_relaxes_the_pads_even_when_many(law):
    """RULINGS 2026-09-30bj (3): where the pad hold alone suffices the apron
    row is never relaxed — fifty pad rows give way before one apron cap."""
    rows = [(APRON, {1: 1.0, 0: -1.0}, 1.5)]
    rows += [(PAD, {1: -1.0, 2 + k: 1.0}, -5.0) for k in range(50)]   # x1 >= x_k + 5
    rows += [(RUNWAY, {2 + k: 1.0}, 0.0) for k in range(50)]          # x_k <= 0 ...
    rows += [(RUNWAY, {2 + k: -1.0}, 0.0) for k in range(50)]         # ... = 0
    rows += [(RUNWAY, {0: 1.0}, 0.0), (RUNWAY, {0: -1.0}, 0.0)]      # x0 = 0
    one, A, b, pl = _problem(rows)
    demote, rep = F.check_hard_set(pl, law, one, np.arange(len(rows)), A, b)
    assert rep.by_tier == {"pad": 50} and 0 not in set(int(k) for k in demote)


def test_groundside_is_the_fifth_tier_below_the_pads(law):
    one, A, b, pl = _problem([(GROUND, {0: 1.0}, 0.0), (PAD, {0: -1.0}, -2.0)])
    demote, rep = F.check_hard_set(pl, law, one, np.arange(2), A, b, stage="2")
    assert [int(k) for k in demote] == [0] and rep.by_tier == {"groundside": 1}
    assert F.tier_of(law)[GROUND] == len(design_law(law).hard_conflict_tiers) - 1


def test_a_missed_strict_body_chord_is_promoted_alone(law):
    """RULINGS 2026-09-30bj (#149): the strict chords are PRICED; the ones
    the iterate misses — exactly those pairs — are promoted to hard."""
    one, A, b, _pl = _problem([(STRICT, {1: 1.0, 0: -1.0}, 1.5),
                               (STRICT, {2: 1.0, 0: -1.0}, 1.5),
                               (APRON, {1: 1.0, 2: -1.0}, 1.5)])
    rep = type("R", (), {"hard_feasibility": F.ConflictReport()})()
    miss, sc = F.promote_missed(one, np.array([2]), A, b, None,
                                np.array([0.0, 3.0, 1.0]), law, rep)
    assert [int(k) for k in miss] == [0] and rep.hard_feasibility.promoted_on_miss == 1
    assert sc[0] == pytest.approx(1.0) and sc[1] == 1.0


def test_a_runway_conflict_left_over_tolerance_after_the_projection_is_the_stop(law):
    one, _A, _b, _pl = _problem([(RUNWAY, {0: 1.0}, 0.0)])
    f = F.ConflictReport(runway_conflict=1, runway_idx=[0])
    rep = type("R", (), {"hard_feasibility": f})()
    F.runway_after(rep, one, np.array([0.005]), law)       # a one-term row reads x2
    assert not f.runway_stop and f.runway_after_m == pytest.approx(0.01)
    F.runway_after(rep, one, np.array([0.5]), law)
    assert f.runway_stop


def test_apron_heads_are_hard_and_every_hard_head_is_ranked(law):
    d = design_law(law)
    for h in ("common.roles.apron ring edge", "common.roles.apron frontage chord",
              "common.roles.apron on the shared edge portion",
              "apron body chord, stationed across the face"):
        assert h in d.hard_rulings
        assert h not in d.fronting_hard_rulings
    assert STRICT not in d.hard_rulings and STRICT in d.apron_promote_on_miss_rulings
    assert "plane_gradient" in d.apron_hard_rulings
    assert "plane_gradient" not in d.hard_rulings      # taxi / road planes stay priced
    tiers = F.tier_of(law)
    assert tiers[RUNWAY] == 0 and tiers[APRON] > tiers[TAXI]
    assert tiers[PAD] > tiers[APRON]
    for h in (*d.hard_rulings, *d.fronting_hard_rulings, *d.apron_hard_rulings):
        assert h in tiers


def test_source_face_reads_the_row_face():
    r = Diff(0, 1, 0.015, 10.0, Source("g", "plane_gradient (x)", ("face:17", "r")))
    assert F.source_face(r) == 17
    assert F.source_face(Diff(0, 1, 0.015, 10.0, Source("g", "x", ()))) is None
