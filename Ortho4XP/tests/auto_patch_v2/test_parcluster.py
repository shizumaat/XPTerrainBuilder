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
