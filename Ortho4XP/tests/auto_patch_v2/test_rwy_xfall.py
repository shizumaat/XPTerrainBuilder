"""Twin of ``tools/harness/rwy_xfall.py`` (promoted 2026-09-05, lane
v2relaxfull): the harness cross-fall reading agrees with the v2 verify
reader on the transverse fixture — the generator-less arm builds the
cliff and the tool reads that half OVER at the reader's own magnitude;
the generator arm holds every half ``ok`` (≤ cap + quantum)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from auto_patch_v2.constraints import roads
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import tables as T
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Status
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import FAMILY_TRANSVERSE

from tests.auto_patch_v2.test_runway_transverse import (PULL_M, _built_falls, _solve_with_pin,
                                                        build_shared_edge, law)  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "harness"))
import rwy_xfall  # noqa: E402


@pytest.fixture(scope="module")
def shared_edge(law):
    return build_shared_edge(law)


def _emit(shared_edge, law, tmp_path, with_generator):
    airport, pm, rw, v, cs, sol, _rep = _solve_with_pin(shared_edge, law, PULL_M,
                                                  with_generator=with_generator,
                                                  hold_ridge=not with_generator)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    paths = write_patch(surf, law, tmp_path / ("gen" if with_generator else "nogen"), pub)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))[FAMILY_TRANSVERSE]
    return pm, rw, v, sol, paths.patch, rows


def test_tool_reads_the_cliff_the_verify_reader_flags(shared_edge, law, tmp_path):
    pm, rw, v, sol, patch, rows = _emit(shared_edge, law, tmp_path, with_generator=False)
    assert rows, "the fixture's cliff must be a verify defect"
    lines: list[str] = []
    got = rwy_xfall.read_cross_falls(patch, "ZZZZ", out=lines.append)
    assert got and any(not r.ok for r in got)
    over = [r for r in got if not r.ok]
    cap = T.runway_transverse_max(law, rw.code_letter, rw.code_number)
    assert all(r.cap == cap for r in got)
    # the tool's worst grade is the reader's worst row (same population,
    # same foot): fall over d, within the stationing of the two readers
    worst_reader = max(abs(r["grade_pct"]) for r in rows) / 100.0
    assert max(r.worst for r in over) == pytest.approx(worst_reader, rel=0.05)
    assert any("OVER" in ln for ln in lines)
    # CLI: exit 1 on an OVER half
    assert rwy_xfall.main([str(patch), "--icao", "ZZZZ"]) == 1


def test_tool_holds_every_half_with_the_generator(shared_edge, law, tmp_path):
    pm, rw, v, sol, patch, rows = _emit(shared_edge, law, tmp_path, with_generator=True)
    assert rows == []
    got = rwy_xfall.read_cross_falls(patch, "ZZZZ")
    assert got and all(r.ok for r in got), [(r.shape_id, r.worst, r.cap) for r in got]
    assert all(r.worst <= r.cap + r.allowance for r in got)
    assert all(r.allowance > 0.0 for r in got)          # the quantum is stated, never zero
    assert rwy_xfall.main([str(patch), "--icao", "ZZZZ", "--half", got[0].shape_id,
                           "--stations", "0", "--json", str(tmp_path / "x.json")]) == 0
    assert (tmp_path / "x.json").is_file()
