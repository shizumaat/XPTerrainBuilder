"""#2044: STAGE 1'S RIBBON-FREE DERIVE RUN AHEAD (``pipeline/
stage_one_ahead``) beside the main pass's shapes and constraints.

Synthetic, no corpus: ``test_roadmint100``'s airport with a tertiary road
across the runway's end strip (one ribbon: stage 1 has its own map).  The
main pass runs through ``run_prefix`` with the build's hook; the ahead arm
runs stage 1's derive in ONE spawned pool worker the moment the channels
are done.  It must equal the serial arm — the stage-1 map, rows, strips and
registries, the derive's run count and record — on a HIT, when the
finished map's decks moved (refused: derived here), and with the stage
cache on, where the worker's records serve a later serial build."""
from __future__ import annotations

import dataclasses as dc
import shutil

import numpy as np
import pytest
from auto_patch_v2.airport import pool as P
from auto_patch_v2.classify import classify
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline import stage_one_ahead as SA
from auto_patch_v2.pipeline.prefix import Deriver, run_prefix
from auto_patch_v2.pipeline.stage_one_map import stage_one_problem
from tests.auto_patch_v2.test_backhalf_records import ICAO, _states
from tests.auto_patch_v2.test_late_speculate import _fields
from tests.auto_patch_v2.test_roadmint100 import RWY_END, _way, _with
from tests.auto_patch_v2.test_solve_late_records import INPUTS, PACK

from test_classify import _FlatDem


class _BulkFlat(_FlatDem):
    """The world's DEM, at module level: the worker unpickles it."""

    def z_many(self, xs, ys):
        return np.array([self.z(float(x), float(y)) for x, y in zip(xs, ys, strict=True)])


@pytest.fixture
def two_cores():
    """The suite pins the pool to one core (``tests/conftest.py``)."""
    P.configure(2)
    yield
    P.configure(1)


def _arm(ahead: bool, root=None, bind=None) -> dict:
    law = Law.for_airport("SYNT")
    airport = dc.replace(_with(_way(-3, RWY_END, highway="tertiary")), dem=_BulkFlat())
    cl = classify(airport, law)
    fc = FC.FrontCache(ICAO, airport, law, enabled=root is not None,
                       mod_cache_root=None if root is None else str(root))
    airport = fc.airport(airport)
    common = fc.common_inputs(None, None)
    lines: list[str] = []
    box: dict = {}

    def hook(ap, pm_ch):
        d = Deriver(ap, law, INPUTS, PACK, cache=fc, common=common)
        box.update(derive=d, ahead=SA.start(cl, d, pm_ch, out=lines.append) if ahead else None)
    pre = run_prefix(airport, cl, law, INPUTS, PACK, fc, common=common,
                     cl_digest=fc.digest(cl), after_channels=hook)
    derive, a = box["derive"], box["ahead"]
    assert derive.airport is pre.airport
    if a is None:
        s1 = stage_one_problem(cl, derive, pre.pm.registries, full=pre.pm)
    else:
        s1 = stage_one_problem(cl, a.bind(pre.pm if bind is None else bind(pre.pm)),
                               pre.pm.registries, full=pre.pm, split=a.split)
        a.close()
    return {"s1": s1, "runs": derive.runs, "last": derive.last, "lines": lines,
            "outcome": None if a is None else a.outcome, "states": _states(fc.finish())}


def _same(a: dict, b: dict) -> None:
    assert a["s1"] is not None and b["s1"] is not None
    for f in ("pm", "cs", "strips", "state", "report"):
        assert _fields(getattr(a["s1"], f)) == _fields(getattr(b["s1"], f)), f
    assert a["runs"] == b["runs"] == 1
    for f in ("pm", "cs", "strips", "stage", "planar_pm", "road_rep", "reports"):
        assert _fields(getattr(a["last"], f)) == _fields(getattr(b["last"], f)), f
    assert a["last"].airport.flat_site == b["last"].airport.flat_site


def test_a_hit_is_the_serial_derive(two_cores):
    ahead = _arm(True)
    assert ahead["outcome"] == "hit", ahead["lines"]
    assert any("run ahead beside the main pass" in ln for ln in ahead["lines"])
    _same(ahead, _arm(False))


def test_a_moved_deck_refuses_the_workers_run(two_cores):
    # the finished map's decks are not what the worker was handed: its run
    # is refused and stage 1 is derived here, as it always was
    ahead = _arm(True, bind=lambda pm: dc.replace(pm, decks=("moved",)))
    assert ahead["outcome"] == "miss", ahead["lines"]
    assert any("moved a deck" in ln for ln in ahead["lines"])
    _same(ahead, _arm(False))


def test_budget_one_does_not_run_ahead():
    ahead = _arm(True)
    assert ahead["outcome"] is None
    assert any("not run ahead" in ln and "budget 1" in ln for ln in ahead["lines"])


def test_the_workers_records_serve_a_later_serial_build(two_cores, tmp_path):
    writer = _arm(True, tmp_path / "w")
    assert writer["outcome"] == "hit", writer["lines"]
    shutil.copytree(tmp_path / "w", tmp_path / "r")
    reader = _arm(False, tmp_path / "r")
    _same(writer, reader)
    s1 = {k: v for k, v in reader["states"].items() if k.endswith("@prefix1")}
    assert s1 and set(s1.values()) == {"hit"}, reader["states"]
