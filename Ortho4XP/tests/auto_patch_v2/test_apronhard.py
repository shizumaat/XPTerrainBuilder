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
    assert "STOP" in rep.line()


def test_apron_heads_are_hard_and_every_hard_head_is_ranked(law):
    d = design_law(law)
    for h in ("common.roles.apron ring edge", "common.roles.apron frontage chord",
              "apron body chord, strict",
              "apron body chord, stationed across the face"):
        assert h in d.hard_rulings
        assert h not in d.fronting_hard_rulings
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
