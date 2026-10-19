"""#843 step 9d — the back half's records END TO END, in build order:
the prefix (constraints, jetway strips) → the base solve → the late cut and
late solve → emit → verify (spec ``v2-stage-cache-spec.md`` §4b, §8 T8).

Synthetic, no corpus: ``test_solve_late_records``' pad-road world (a base
without the road, the road solved against its levels in the last stage) run
as ``pipeline/build.py`` runs it, emit and verify named by
``emit_records.final_identity``.  Three arms: COLD (the cache off), the
MISS arm (every record written) and the FULL HIT.  The hit equals the
build that wrote it byte for byte — the files on disk, the report, the
lines and the verify rows (RULINGS 2026-10-18d); cold equals it but for
the solve's clocks, which the sidecar's ``design`` block carries
(``qp_solves`` rows, ``*_s``).  The closing HECA / CYXY identity is the
master's."""
from __future__ import annotations

import dataclasses as dc
import json
import re
import shutil
import types
from pathlib import Path

import pytest
from auto_patch_v2.pipeline import emit_records as ER
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.pipeline import solve_record as SR
from auto_patch_v2.pipeline.late_records import LateRecords
from auto_patch_v2.pipeline.prefix import Deriver
from auto_patch_v2.pipeline.shapes import joint_steps
from auto_patch_v2.solve import Options, solve_design
from tests.auto_patch_v2.test_backhalf_records import ICAO, _copy, _states
from tests.auto_patch_v2.test_solve_late_records import (
    INPUTS, PACK, _first_difference, _late_world, _unclocked)


def _run(root: Path | None, out_dir: Path) -> dict:
    """One build's back half into a fresh ``out_dir`` (``root`` None: the
    cache off)."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    from auto_patch_v2.pipeline.late_stage import run_last_stages
    from auto_patch_v2.pipeline.stage_one_map import gap_free
    law, airport, cl = _late_world()
    fc = FC.FrontCache(ICAO, airport, law, enabled=root is not None,
                       mod_cache_root=None if root is None else str(root))
    airport = fc.airport(airport)
    common = fc.common_inputs(None, None)
    derive = Deriver(airport, law, INPUTS, PACK, cache=fc, common=common)
    pm0, cs0, strips0, hold0 = derive(gap_free(cl))
    keys0 = dict(derive.last.keys)

    def solve():
        sol, rep = solve_design(pm0, cs0, law, Options(), strips=strips0, hold=hold0)
        return sol, rep, {}, {}, None
    solved = SR.solve_stage(fc, {**keys0, "stage_one": "none",
                                 "options": fc.digest(Options())},
                            solve, cs=cs0, n=len(pm0.vertices), law=law, options=Options(),
                            held=pm0.registries.held)
    late = LateRecords(fc, {"airport": keys0.get("airport"), "options": fc.digest(Options())},
                       SR.identity(keys0.get("pm"), solved.digest), law, Options())
    lines: list[str] = []
    design0 = solved.value.design
    pm, sol, rep = run_last_stages(
        cl, airport, law, derive,
        {"pm": pm0, "z": solved.value.sol.z, "pin_yield": list(design0.pin_yield or ()),
         "hard_conflict": list(design0.hard_conflict)},
        options=Options(), out=lines.append, records=late)
    stage = dc.replace(derive.last.stage, pm=pm)
    report: dict = {"joint_steps": joint_steps(pm, law, stage, sol.z)}
    wall: dict = {}
    lrep = types.SimpleNamespace(dsf_dump_path=None)
    late_report = {"cut": rep["cut"], "stage": rep["stage"]}
    kw = dict(cl=rep["cl"], yield_records=[], lrep=lrep, airport=airport, objects_out=[])
    em_in = ER.emit_inputs(fc, final=ER.final_identity(solved, late), common=common,
                           feather_m=60.0, **kw)
    em = ER.emit(fc, em_in, icao=ICAO, law=law, header_extra=None, out_dir=out_dir,
                 report=report, wall=wall, out=lines.append, pm=pm, sol=sol,
                 cs=rep["cs_full"], strips=rep["strips"], design_rep=rep["design"],
                 hard_conflict=rep["hard_conflict"], late_report=late_report, **kw)
    rows = ER.verify(fc, em, pm_digest=em_in.get("final"),
                     airport_digest=em_in.get("airport"), icao=ICAO, pm=pm, law=law,
                     airport=airport, report=report, wall=wall, pool_out=[],
                     out=lines.append)
    states = {k.split("@")[0]: v for k, v in _states(fc.finish()).items()
              if not k.startswith("constraints.gen.")}
    files = {str(p.relative_to(out_dir)): p.read_bytes()
             for p in sorted(out_dir.rglob("*")) if p.is_file()}
    return {"files": files, "report": report, "lines": lines, "rows": rows,
            "states": states, "final": em_in.get("final")}


def _clockless(lines: list[str]) -> list[str]:
    return [re.sub(r"\d+\.\d+ s\b|served", "T", ln) for ln in lines]


def _files(arm: dict, clocks: bool) -> dict:
    if clocks:
        return arm["files"]
    return {k: _unclocked(json.loads(v)) if k.endswith(".json") else v
            for k, v in arm["files"].items()}


_SIDECAR_B = re.compile(r"sidecar \d+ B")


def _sidecar_sized(arm: dict) -> dict:
    """``arm`` with the sidecar's byte count checked against the file the
    arm wrote and then masked: the sidecar carries the solve's clocks as
    decimals (``"solver_wall_s":0.01`` / ``0.009``), so its LENGTH is a
    clock reading too — a cold run's equals a hit's only when every clock
    happens to print as many digits (a slow runner, e.g. Windows CI, often
    does not).  Its CONTENT is compared unclocked by ``_files``."""
    rep = dict(arm["report"])
    emit = dict(rep["emit"])
    side = Path(emit["sidecar"]).name
    assert emit["bytes_sidecar"] == len(arm["files"][side])
    emit["bytes_sidecar"] = "<clocked>"
    rep["emit"] = emit
    lines = [_SIDECAR_B.sub("sidecar <clocked> B", ln) for ln in arm["lines"]]
    assert sum(_SIDECAR_B.search(ln) is not None for ln in arm["lines"]) == 1
    return {**arm, "report": rep, "lines": lines}


def _same(a: dict, b: dict, *, clocks: bool = True) -> None:
    """``a`` equals ``b``: every file byte for byte (``clocks`` False: the
    JSON files but for their clocks, and the sidecar's byte count — itself
    a clock reading — only against each arm's own file), the report, the
    lines, the rows."""
    assert a["files"] and _files(a, clocks) == _files(b, clocks)
    if not clocks:
        a, b = _sidecar_sized(a), _sidecar_sized(b)
    ra, rb = dict(a["report"]), dict(b["report"])
    va, vb = ra.pop("verify"), rb.pop("verify")
    if not clocks:
        ra, rb = _unclocked(ra), _unclocked(rb)
    assert ra == rb, _first_difference(ra, rb) or "same values, other container types"
    assert {k: v for k, v in va.items() if k != "wall_s"} == \
        {k: v for k, v in vb.items() if k != "wall_s"}
    assert _clockless(a["lines"]) == _clockless(b["lines"])
    assert a["rows"] == b["rows"]


@pytest.fixture(scope="module")
def arms(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    out = tmp_path_factory.mktemp("o") / "out"     # one out_dir: the report names it
    cold = _run(None, out)
    miss = _run(root, out)
    hit = _run(_copy(root, tmp_path_factory.mktemp("c") / "c"), out)
    return cold, miss, hit


def test_the_records_run_in_build_order_and_a_full_hit_equals_its_writer(arms):
    cold, miss, hit = arms
    order = ("jetway_strip", "solve", "late.cut.1", "late.solve.1", "emit", "verify")
    assert all(miss["states"].get(s) == "miss" for s in order), miss["states"]
    assert "constraints.assembly" in miss["states"]
    assert set(hit["states"].values()) == {"hit"}, hit["states"]
    assert miss["final"] is not None and miss["final"] == hit["final"]
    _same(miss, hit)                       # byte for byte, clocks and all
    _same(cold, hit, clocks=False)
