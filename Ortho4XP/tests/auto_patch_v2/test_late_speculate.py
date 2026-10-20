"""#412 phase 1, C4b: THE PAD ROADS' DERIVE BESIDE THE GAP STAGE
(``pipeline/late_speculate``; spec cold-patch-300s §3.1 C4b).

Synthetic, no corpus: ``test_backhalf_end_to_end``'s two-pass world (a gap
piece beside a pad whose road is solved against the gap stage).  The
speculative arm runs the roads pass's cut and derive in ONE spawned pool
worker; it must equal the serial arm — the map, the levels, the derive's
run count and record, every line but the speculation's own — on a HIT, on
a forced MISS (today's path), and with the stage cache on, where the
worker's records serve a later serial build."""
from __future__ import annotations

import dataclasses as dc
import shutil

import numpy as np
import pytest
from auto_patch_v2.airport import pool as P
from auto_patch_v2.airport import stage_cache as STORE
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline import late_speculate as LS
from auto_patch_v2.pipeline.late_stage import run_last_stages
from auto_patch_v2.pipeline.prefix import Deriver
from auto_patch_v2.pipeline.stage_one_map import gap_free
from auto_patch_v2.solve import Options, solve_design
from tests.auto_patch_v2.test_backhalf_end_to_end import _two_pass_world
from tests.auto_patch_v2.test_backhalf_records import ICAO, _states
from tests.auto_patch_v2.test_roads609 import _FallingDem
from tests.auto_patch_v2.test_solve_late_records import INPUTS, PACK

_OWN = ("C4b", "[pool]")
#: a stage's clocks (``ShapeStage.wall_s``, ``PrefixRecord.wall``)
_CLOCKS = ("wall_s", "wall")


class _BulkDem(_FallingDem):
    """The world's DEM, at module level: the worker unpickles it."""

    def z_many(self, xs, ys):
        return np.array([self.z(float(x), float(y)) for x, y in zip(xs, ys, strict=True)])


@pytest.fixture
def two_cores():
    """The suite pins the pool to one core (``tests/conftest.py``)."""
    P.configure(2)
    yield
    P.configure(1)


def _arm(speculate, root=None) -> dict:
    law, airport, cl = _two_pass_world()
    airport = dc.replace(airport, dem=_BulkDem())
    fc = FC.FrontCache(ICAO, airport, law, enabled=root is not None,
                       mod_cache_root=None if root is None else str(root))
    airport = fc.airport(airport)
    derive = Deriver(airport, law, INPUTS, PACK, cache=fc, common=fc.common_inputs(None, None))
    pm0, cs0, strips0, hold0 = derive(gap_free(cl))
    sol0, rep0 = solve_design(pm0, cs0, law, Options(), strips=strips0, hold=hold0)
    lines: list[str] = []
    pm, sol, rep = run_last_stages(
        cl, airport, law, derive,
        {"pm": pm0, "z": sol0.z, "pin_yield": list(rep0.pin_yield or ()),
         "hard_conflict": list(rep0.hard_conflict)},
        options=Options(), out=lines.append, speculate=speculate)
    return {"pm": pm, "z": np.asarray(sol.z), "runs": derive.runs, "last": derive.last,
            "lines": lines, "states": _states(fc.finish())}


def _fields(obj) -> str:
    """A digest of a dataclass's FIELDS: an unpickled ``PlanarMap`` also
    carries its ``_unpickled_defaults`` note (``model/planar``)."""
    if dc.is_dataclass(obj):
        return STORE.content_digest(tuple(_fields(getattr(obj, f.name)) for f in dc.fields(obj)
                                          if f.name not in _CLOCKS))
    return STORE.content_digest(obj)


def _same(a: dict, b: dict) -> None:
    assert _fields(a["pm"]) == _fields(b["pm"])
    assert np.array_equal(a["z"], b["z"])
    assert a["runs"] == b["runs"]
    for f in ("pm", "cs", "strips", "stage", "planar_pm", "road_rep", "reports"):
        assert _fields(getattr(a["last"], f)) == _fields(getattr(b["last"], f)), f
    assert a["last"].airport.flat_site == b["last"].airport.flat_site
    assert [ln for ln in a["lines"] if not any(o in ln for o in _OWN)] == b["lines"]


class _Kept:
    """``late_speculate.speculate``, keeping what it returned."""

    def __init__(self, change=None) -> None:
        self.change, self.got = change, None

    def __call__(self, derive, cl_all, *a, **kw):
        if self.change is not None:
            cl_all = self.change(cl_all)
        self.got = LS.speculate(derive, cl_all, *a, **kw)
        return self.got


def test_a_hit_is_the_serial_derive(two_cores):
    kept = _Kept()
    spec = _arm(kept)
    assert kept.got is not None and kept.got.outcome == "hit", spec["lines"]
    _same(spec, _arm(None))


def test_a_forced_miss_takes_todays_path(two_cores):
    # the worker cuts a classification the roads pass never sees (one cell
    # renumbered): its digest disagrees — posted before the roads pass
    # arrives, or with its answer — and the derive runs here
    kept = _Kept(lambda cl: dc.replace(cl, cells=tuple(cl.cells)[:-1] + (
        dc.replace(cl.cells[-1], id=cl.cells[-1].id + 1000),)))
    spec = _arm(kept)
    assert kept.got is not None and kept.got.outcome == "miss", spec["lines"]
    _same(spec, _arm(None))


def test_budget_one_does_not_speculate():
    kept = _Kept()
    spec = _arm(kept)
    assert kept.got is None
    assert any("not speculated" in ln and "budget 1" in ln for ln in spec["lines"])


def test_the_workers_records_serve_a_later_serial_build(two_cores, tmp_path):
    kept = _Kept()
    writer = _arm(kept, tmp_path / "w")
    assert kept.got.outcome == "hit"
    shutil.copytree(tmp_path / "w", tmp_path / "r")
    reader = _arm(None, tmp_path / "r")
    _same(writer, reader)
    tag = f"@prefix{reader['runs']}"
    late = {k: v for k, v in reader["states"].items() if k.endswith(tag)}
    assert late and set(late.values()) == {"hit"}, reader["states"]
    # the worker's misses are in the writer's own report, under the same names
    assert all(str(writer["states"].get(k, "")).startswith("miss") for k in late), \
        writer["states"]
