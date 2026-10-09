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
