"""THE POOLED CLUSTER PROFILES' twin (``airport/cluster_profile.py``, issue
#362; owner RULINGS 2026-10-04x (4)): ``plan_clusters`` with a work pool is
``plan_clusters`` without one — the same clusters, in the same order, with
the same composed base profiles — at 1, 2 and N workers, whatever order the
workers finish in, and when the pool dies under it.

The plan is the base-profile twins' own T3-shaped unit
(``test_base_profile_compose``) beside a unit whose ground plane SURVIVES
the composition and a unit written without origins, so the three answers a
job can give (a FEET record, a plane, the vertical-only upper bound) all
cross the pipe.  Hermetic: ``tmp_path`` fixtures, no corpus, no pack.
"""
from __future__ import annotations

import dataclasses as dc
import os

import pytest

from auto_patch_v2.airport import cluster_profile as CP
from auto_patch_v2.airport import placement_family as PF
from auto_patch_v2.airport import pool as P
from auto_patch_v2.model import rebake as RB

from test_base_profile import _slab
from test_base_profile_compose import (HEADING, PROFILE_LAW, _ll, _member,
                                       _origin, _part, _profile, _t3_unit)


def _ground_unit(tmp_path, uid: str, slabs: int) -> RB.Unit:
    """``slabs`` ground slabs side by side, each standing on its own feet:
    a base plane that the composed roof test and the grounded test keep."""
    prof = _profile(tmp_path, f"{uid}.obj".replace(":", "_"),
                    [_slab(0.0, 0.0, 40.0, 30.0, 0.0, base=-0.2)])
    members = []
    for i in range(slabs):
        org = _origin(1000.0 + i * 45.0, 500.0)
        feet = [(*_ll(org, HEADING, x, z), 0.0)
                for x in (0.0, 40.0) for z in (0.0, 30.0)]
        members.append(_member(f"{uid}slab{i}".replace(":", "_"), prof, org, HEADING,
                               parts=[_part(1000 + i, *_ll(org, HEADING, 20.0, 15.0),
                                            0.0, feet=feet)]))
    return RB.Unit(id=uid, anchor=_origin(0.0, 0.0), agl_m=0.0,
                   members=tuple(members))


@pytest.fixture(scope="module")
def plan(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("parcluster")
    bare = dc.replace(_t3_unit(tmp, halls=2, placed=False), id="unit:7")
    units = (_t3_unit(tmp, halls=3), _ground_unit(tmp, "unit:5", 3), bare)
    return RB.RebakePlan(icao="TEST", pack_name="p", pack_root="/pack",
                         units=units, skipped=(), counts={})


def _clusters(plan, pool=None, counts=None):
    return PF.plan_clusters(plan, 0.5, profile_law=PROFILE_LAW, pool=pool,
                            counts=counts)


@pytest.fixture(scope="module")
def serial(plan):
    return _clusters(plan)


def test_the_plan_gives_every_kind_of_answer(serial):
    hows = {c.composition for c in serial}
    assert {"composed", "vertical_only"} <= hows, hows
    assert any(c.base_profile.get("planes") for c in serial)
    assert any(c.base_profile and not c.base_profile.get("planes") for c in serial)
    assert sum(1 for c in serial if c.composition) >= 4


@pytest.mark.parametrize("n", [1, 2, max(2, os.cpu_count() or 2)])
def test_pooled_clusters_equal_serial(plan, serial, n):
    c0: dict = {}
    _clusters(plan, counts=c0)
    c1: dict = {}
    with P.WorkPool(workers=n, out=lambda s: None) as pool:
        got = _clusters(plan, pool=pool, counts=c1)
        answered = pool.tasks_done
    assert repr(got) == repr(serial) and got == serial
    assert c1 == c0
    assert answered == (0 if n == 1 else sum(1 for c in serial if c.composition))


def _jobs(plan):
    out = []
    for u in plan.units:
        for mi in range(len(u.members)):
            job = CP.profile_job(u, [mi, (mi + 1) % len(u.members)], PROFILE_LAW)
            if job is not None:
                out.append(job)
    return out


def test_answers_come_back_in_job_order(plan):
    jobs = _jobs(plan)
    assert len(jobs) >= 6
    want = [CP.compose_job(j) for j in jobs]
    assert CP.compose_jobs(jobs) == want
    with P.WorkPool(workers=3, out=lambda s: None) as pool:
        # heaviest-first submission is not input order, forwards or back
        assert repr(CP.compose_jobs(jobs, pool)) == repr(want)
        assert repr(CP.compose_jobs(jobs[::-1], pool)) == repr(want[::-1])


def test_the_job_is_the_one_spelling(plan):
    u = plan.units[1]
    assert CP.cluster_base_profile(u, (0, 1), PROFILE_LAW) == \
        CP.compose_job(CP.profile_job(u, (0, 1), PROFILE_LAW))
    cols = [i for i, m in enumerate(plan.units[0].members)
            if not m.base_profile.get("planes")]
    assert CP.profile_job(plan.units[0], cols, PROFILE_LAW) is None
    assert CP.cluster_base_profile(plan.units[0], cols, PROFILE_LAW) == ({}, "")
    assert PF.cluster_base_profile is CP.cluster_base_profile


def _die_setup():
    os._exit(3)


def test_a_pool_that_dies_leaves_the_serial_clusters(plan, serial):
    said = []
    with P.WorkPool(_die_setup, workers=2, out=said.append) as pool:
        got = _clusters(plan, pool=pool)
        assert pool.fell_back and not pool.parallel
    assert repr(got) == repr(serial)
    assert any("FELL BACK" in s for s in said)


# ── the connector topology's sweep and the spanning sheets (step 2) ──────
#
# Both are a READING replayed into a verdict: the pooled reading must give
# the serial lists in the serial ORDER (the DFS walks the adjacency lists;
# the sheet counts are replayed sheet by sheet).

from auto_patch_v2.airport import footprint_connector as FC   # noqa: E402
from auto_patch_v2.airport import footprint_unit as FU        # noqa: E402
from auto_patch_v2.airport import sheet_chain as SC           # noqa: E402

from test_sheetchain import FRAC, _terminal                   # noqa: E402
from test_v2connector import _blk, _lat, _shim                # noqa: E402
from test_v2padcluster import TOUCH                           # noqa: E402

W = 0.0004          # one block's width in degrees of longitude


def _lattice():
    """63 abutting blocks on a 9 x 7 lattice with every third one missing
    a neighbour, handed over in a scrambled order."""
    cells = [(r, c) for r in range(9) for c in range(7) if (r * 7 + c) % 11 != 5]
    cells = cells[::3] + cells[1::3] + cells[2::3]
    return [_shim(i, [_blk(_lat(40 * r), _lat(40 * r + 40),
                           -3.0 + c * W, -3.0 + (c + 1) * W)])
            for i, (r, c) in enumerate(cells)]


@pytest.mark.parametrize("n", [2, max(2, os.cpu_count() or 2)])
def test_the_pooled_contact_sweep_is_the_serial_graph(monkeypatch, n):
    shims = _lattice()
    cl = list(range(len(shims)))
    want = FC.contact_graph(cl, shims, 0.5)
    assert sum(len(v) for v in want.values()) > 150
    topo = FC.cluster_topology(cl, shims, 0.5)
    monkeypatch.setattr(FC, "POOL_MIN_BODIES", 1)
    with P.WorkPool(workers=n, out=lambda s: None) as pool:
        got = FC.contact_graph(cl, shims, 0.5, pool)
        assert pool.tasks_done > 0
        t2 = FC.cluster_topology(cl, shims, 0.5, pool)
    assert got == want and list(got) == list(want)
    for f in ("nodes", "adj", "order", "tin", "tout", "sep", "tree", "spans"):
        assert getattr(t2, f) == getattr(topo, f), f


def test_any_split_of_the_sweep_is_the_sweep():
    shims = _lattice()
    hull = [s.box for s in shims]
    order = sorted(range(len(shims)), key=lambda i: hull[i][0])
    data = ([hull[i] for i in order], [list(shims[i].part_boxes) for i in order],
            [[] for _ in order])
    whole = FC._sweep(data, 0.5, 0, len(order))
    for step in (1, 7, 20):
        parts = [FC._sweep(data, 0.5, a, min(a + step, len(order)))
                 for a in range(0, len(order), step)]
        assert [v for p in parts for v in p] == whole


def _sheet_world():
    """Twelve walled blocks in a row with 20 m between them, and thirty
    sheets: over two blocks, over one, over none, over three."""
    shims = [_shim(i, [_blk(_lat(60 * i), _lat(60 * i + 40))]) for i in range(12)]
    walled = list(range(12))
    spans = [(60 * k + 30, 60 * k + 70) for k in range(11)]            # two each
    spans += [(60 * k + 5, 60 * k + 35) for k in range(8)]             # one each
    spans += [(60 * k + 42, 60 * k + 58) for k in range(6)]            # none
    spans += [(60 * k + 20, 60 * k + 150) for k in range(5)]           # three
    for a, b in spans:
        shims.append(_shim(len(shims), [_blk(_lat(a), _lat(b))]))
    return shims, walled, list(range(12, len(shims)))


def _links(pool=None, min_fraction=FRAC):
    shims, walled, leaves = _sheet_world()
    counts: dict = {}
    fr: list = []
    out = SC.sheet_links(shims, walled, leaves, min_fraction,
                         is_deck=lambda i: i % 7 == 0, is_footed=lambda i: i % 5 == 0,
                         ml=111_132.0, mo=111_132.0, counts=counts, prefix="t_",
                         fractions=fr, pool=pool)
    return out, counts, fr


@pytest.mark.parametrize("n", [2, max(2, os.cpu_count() or 2)])
def test_the_pooled_sheet_reading_is_the_serial_links(monkeypatch, n):
    want = _links()
    assert want[0] and want[1]["t_sheet_over_one_body"] and want[1]["t_sheet_refused_deck"]
    assert any(len(b) == 3 for _s, b in want[0]) and len(want[2]) > 20
    monkeypatch.setattr(SC, "POOL_MIN_SHEETS", 1)
    with P.WorkPool(workers=n, out=lambda s: None) as pool:
        assert _links(pool) == want
        assert pool.tasks_done > 0
        assert _links(pool, 0.999) == _links(None, 0.999)     # a second unit


def test_the_plan_reads_the_same_units_connectors_and_clusters_through_a_pool(monkeypatch):
    plan = _terminal(with_canopy=True)
    kw = dict(chain_min_height_m=2.5, sheet_chain_min_fraction=FRAC)
    c0: dict = {}
    want = (FU.plan_units_and_connectors(plan, TOUCH, 10.0, c0, **kw),
            PF.plan_clusters(plan, TOUCH, **kw))
    monkeypatch.setattr(SC, "POOL_MIN_SHEETS", 1)
    monkeypatch.setattr(FC, "POOL_MIN_BODIES", 1)
    c1: dict = {}
    with P.WorkPool(workers=2, out=lambda s: None) as pool:
        got = (FU.plan_units_and_connectors(plan, TOUCH, 10.0, c1, pool=pool, **kw),
               PF.plan_clusters(plan, TOUCH, pool=pool, **kw))
        assert pool.tasks_done > 0
    assert repr(got) == repr(want) and c1 == c0


def test_a_dead_pool_leaves_the_serial_sweep_and_sheets(monkeypatch):
    shims = _lattice()
    cl = list(range(len(shims)))
    want_g, want_l = FC.contact_graph(cl, shims, 0.5), _links()
    monkeypatch.setattr(SC, "POOL_MIN_SHEETS", 1)
    monkeypatch.setattr(FC, "POOL_MIN_BODIES", 1)
    for _ in range(2):
        with P.WorkPool(_die_setup, workers=2, out=lambda s: None) as pool:
            assert FC.contact_graph(cl, shims, 0.5, pool) == want_g
            assert pool.fell_back
            assert _links(pool) == want_l


def _read_shared(_state, spec):
    return P.shared_object(spec)["answer"]


def test_an_object_is_shared_once_and_replaced_by_the_next():
    with P.WorkPool(workers=2, out=lambda s: None) as pool:
        for answer in (list(range(1000)), "second"):
            with P.share_object({"answer": answer}) as sh:
                assert pool.try_map(_read_shared, [sh.spec] * 6) == [answer] * 6
