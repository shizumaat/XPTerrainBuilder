"""A GROUNDSIDE PAVEMENT'S CEILING NEVER OUTRANKS A PAD (spec §63, owner
RULINGS 2026-10-09j (1) "apron, taxiway, and pads all take precedence over
roads"; 09d (1): pavement touching a pad grades inside its OWN cap).

``[design] hard_conflict_ranks`` lists the common pavement ceilings
(``pavement_max_grade ceiling``, ``road_max_grade pavement fallback``) in
the TAXI tier.  Before ``solve.feasibility.row_tiers`` that was their rank
whatever face the row stood on, so where a lot welded to a pad's rim and a
pad's plane could not both hold, the LP relaxed the PAD (HECA
``building59``: ``pad_slope_max ceiling`` 3 -> 20 relaxed rows).

Twins: (a) a flat pad fronting an apron at 5 m, a lot welded to the pad's
rim whose far corner the apron holds at 0 m — the LOT's ceiling relaxes,
never the pad's plane; (b) the rank of a ceiling row standing on airside
vertices only (apron / taxi / pad) is the taxi tier, unchanged.
"""
from __future__ import annotations

import types

import numpy as np
import pytest
import scipy.sparse as sp

from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import Source
from auto_patch_v2.solve import feasibility as F

CEIL = "rulesets.common.pavement_max_grade ceiling"
FALLBACK = "rulesets.common.road_max_grade pavement fallback"
PLANE = "structures.building_pad platform plane"
APRON = "common.roles.apron ring edge"


@pytest.fixture(scope="module")
def law():
    return T.load_default()


class _Row:
    def __init__(self, head: str):
        self.source = Source("test", f"{head} (twin)", ())


def _planar(roles: dict[int, tuple[str, ...]]):
    vs = {i: types.SimpleNamespace(key=(30.0 + i * 1e-4, 31.0)) for i in roles}
    return types.SimpleNamespace(vertices=vs, roles_at=lambda v: roles[v])


def _problem(rows, roles):
    one, data, ii, jj, b = [], [], [], [], []
    for k, (head, terms, rhs) in enumerate(rows):
        one.append((tuple(terms.items()), rhs, _Row(head)))
        for c, w in terms.items():
            ii.append(k); jj.append(c); data.append(w)
        b.append(rhs)
    A = sp.csr_matrix((data, (ii, jj)), shape=(len(rows), len(roles)))
    return one, A, np.asarray(b, float), _planar(roles)


# v0 the pad's rim, welded to the lot; v1 the pad's apron frontage;
# v2 the lot's interior; v3 the lot's corner on the apron edge
ROLES = {0: ("building", "groundside_pavement"), 1: ("building", "apron"),
         2: ("groundside_pavement",), 3: ("groundside_pavement", "apron")}


def _welded_lot():
    return [(APRON, {1: 1.0}, 5.0), (APRON, {1: -1.0}, -5.0),       # v1 = 5
            (PLANE, {0: 1.0, 1: -1.0}, 0.0),                       # the flat pad
            (PLANE, {0: -1.0, 1: 1.0}, 0.0),
            (CEIL, {0: 1.0, 2: -1.0}, 0.5), (CEIL, {2: 1.0, 0: -1.0}, 0.5),
            (FALLBACK, {2: 1.0, 3: -1.0}, 0.5), (FALLBACK, {3: 1.0, 2: -1.0}, 0.5),
            (APRON, {3: 1.0}, 0.0), (APRON, {3: -1.0}, 0.0)]       # v3 = 0


def test_the_lots_ceiling_relaxes_never_the_pads_plane(law):
    one, A, b, pl = _problem(_welded_lot(), ROLES)
    demote, rep = F.check_hard_set(pl, law, one, np.arange(len(one)), A, b, stage="1")
    assert rep.status == "optimal" and rep.relaxed >= 1
    assert PLANE not in rep.by_head, rep.by_head          # the pad holds
    assert set(rep.by_head) <= {CEIL, FALLBACK}
    assert rep.by_tier == {"groundside": rep.relaxed}
    assert not {2, 3} & {int(k) for k in demote}          # nor the pad's plane rows


def test_an_airside_ceiling_keeps_its_taxi_rank(law):
    taxi = F.tier_of(law)[CEIL]
    roles = {0: ("apron",), 1: ("apron", "stub"), 2: ("building", "apron"),
             3: ("groundside_pavement",), 4: ("building", "groundside_pavement")}
    rows = [(CEIL, {0: 1.0, 1: -1.0}, 0.5), (FALLBACK, {2: 1.0, 0: -1.0}, 0.5),
            (CEIL, {0: 1.0, 3: -1.0}, 0.5), (FALLBACK, {4: 1.0, 3: -1.0}, 0.5),
            (PLANE, {3: 1.0, 4: -1.0}, 0.0)]
    one, _A, _b, pl = _problem(rows, roles)
    heads = [h for h, _t, _r in rows]
    got = F.row_tiers(pl, law, one, np.arange(len(rows)), heads)
    gs = list(T.design(law).hard_conflict_tiers).index("groundside")
    assert list(got) == [taxi, taxi, gs, gs, F.tier_of(law)[PLANE]]


# ── owner RULINGS 2026-10-10a (2): a landside pad MOVES; a pad airside holds
#    stays and the ROAD welded to it takes the grade required ─────────────

XSEC = "road_cross_section"
RAMP = "roads.groundside_road ramp ceiling"

# v0 the pad's rim, welded to the road; v1 the pad's other rim vertex (its
# airside frontage when an apron holds it); v2 the road's interior;
# v3 the road's contact with the apron, fixed at 0 m
ROAD_ROLES = {0: ("building", "service_road"), 1: ("building",),
              2: ("service_road",), 3: ("service_road", "apron")}


def _welded_road(held_at: float | None):
    rows = [(PLANE, {0: 1.0, 1: -1.0}, 0.0), (PLANE, {0: -1.0, 1: 1.0}, 0.0),
            (FALLBACK, {0: 1.0, 2: -1.0}, 0.5), (FALLBACK, {2: 1.0, 0: -1.0}, 0.5),
            (XSEC, {0: 1.0, 2: -1.0}, 0.5), (XSEC, {2: 1.0, 0: -1.0}, 0.5),
            (RAMP, {2: 1.0, 3: -1.0}, 0.5), (RAMP, {3: 1.0, 2: -1.0}, 0.5),
            (APRON, {3: 1.0}, 0.0), (APRON, {3: -1.0}, 0.0)]           # v3 = 0
    if held_at is not None:                                           # v1 = held_at
        rows += [(APRON, {1: 1.0}, held_at), (APRON, {1: -1.0}, -held_at)]
    return rows


def test_a_landside_pad_moves_and_nothing_is_relaxed(law):
    """10a (2) (a): the pad touches no airside — nothing holds it, so the
    hard set is feasible with the pad wherever the road welded to it grades
    inside its caps (within 1 m of the road's fixed contact here)."""
    roles = dict(ROAD_ROLES)
    one, A, b, pl = _problem(_welded_road(None), roles)
    demote, rep = F.check_hard_set(pl, law, one, np.arange(len(one)), A, b, stage="1")
    assert rep.status == "optimal" and rep.relaxed == 0 and not len(demote)


def test_a_pad_airside_holds_stays_and_the_road_takes_the_grade(law):
    """10a (2) (b): the pad's other rim vertex is an apron's at 5 m; the
    road welded to it meets its fixed contact 5 m below over rows that
    allow 1 m.  The relaxed rows are the ROAD's own grade rows — the
    cross-section, the ramp ceiling, the fallback cap — in the groundside
    tier; the pad's plane and the apron hold."""
    roles = dict(ROAD_ROLES); roles[1] = ("building", "apron")
    one, A, b, pl = _problem(_welded_road(5.0), roles)
    _demote, rep = F.check_hard_set(pl, law, one, np.arange(len(one)), A, b, stage="1")
    assert rep.status == "optimal" and rep.relaxed >= 1
    assert set(rep.by_head) <= {XSEC, RAMP, FALLBACK}, rep.by_head
    assert rep.by_tier == {"groundside": rep.relaxed}
    assert sum(c["s_m"] for c in rep.conflicts) == pytest.approx(4.0, abs=1e-6)


def test_a_roads_own_cap_stays_senior_to_its_ramp_ceiling(law):
    """A groundside ceiling left the taxi tier to rank under the pads; it
    is still senior to the road's ramp ceiling and cross-section (HECA
    ``dsf:objpav405``, lane weldverify: priced equal, the road went 5.9 m
    over its cap with no pad near it).  A road vertex its ramp ceiling
    wants 3 m under what the cap allows from a fixed contact: the RAMP
    row relaxes, the cap holds."""
    roles = {0: ("service_road", "apron"), 1: ("service_road",)}
    rows = [(APRON, {0: 1.0}, 0.0), (APRON, {0: -1.0}, 0.0),         # v0 = 0
            (FALLBACK, {0: 1.0, 1: -1.0}, 0.5),                     # v1 >= -0.5
            (RAMP, {1: 1.0}, -3.5)]                                 # v1 <= -3.5
    one, A, b, pl = _problem(rows, roles)
    _demote, rep = F.check_hard_set(pl, law, one, np.arange(len(one)), A, b, stage="1")
    assert rep.status == "optimal" and rep.by_head == {RAMP: 1}, rep.by_head
    heads = [h for h, _t, _r in rows]
    tiers = F.row_tiers(pl, law, one, np.arange(len(rows)), heads)
    assert list(F.cap_seniority(law, heads, tiers)) == [0.0, 0.0, 0.5, 0.0]
