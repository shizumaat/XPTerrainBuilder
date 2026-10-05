"""THE BASIN RIM DIAGNOSTICS ARE READ ON DEMAND (owner RULINGS 2026-10-04x
(2), issue #362; ``planar/basin_rim``).

A build's basin pass makes neither rim reading and reads the at-grade
POLYGONS alone; asked for them (``build_basins(rim_diagnostics=True)`` —
the ``--stage structures`` replay, ``tools/v2_solve_replay.py
--rim-diagnostics``) it writes the two notes every build wrote before, and
the cells, the basins and the refusals are the same either way.
"""
from __future__ import annotations

import dataclasses as _dc
import importlib.util
import inspect
from pathlib import Path

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.planar import basin_rim as _rim
from auto_patch_v2.planar import basins as _basins

from test_m4b import _basins_of, law, objs                       # noqa: E402,F401

_RIM_HEADS = ("rim stations", "rim vs the shells")
PLACEMENTS = {"open": [("open", (0.0, 0.0), 0.0, 0.0)],
              "pit": [("pit", (0.0, 0.0), 0.0, 0.0)],
              "covered": [("pit", (0.0, 0.0), 0.0, 0.0), ("roof", (0.0, 0.0), 0.0, 0.0)]}


@pytest.fixture
def linework_asked(monkeypatch):
    """Every ``linework`` argument the basin pass hands the at-grade read."""
    asked: list[bool] = []
    real = obj8.at_grade_geometry

    def spy(*a, **k):
        asked.append(k.get("linework", True))
        return real(*a, **k)
    monkeypatch.setattr(_basins.obj8, "at_grade_geometry", spy)
    return asked


@pytest.mark.parametrize("case", sorted(PLACEMENTS))
def test_a_build_reads_polygons_only_and_names_the_on_demand_read(objs, law, case,
                                                                 linework_asked):
    _cl, _cl3, basins, _bs, _rep = _basins_of(objs, law, PLACEMENTS[case])
    assert len(basins) == 1
    assert linework_asked and not any(linework_asked), \
        "a build's basin pass asks the at-grade read for no linework"
    notes = basins[0].notes
    assert _rim.ON_DEMAND in notes
    assert not any(n.startswith(_RIM_HEADS) for n in notes)


@pytest.mark.parametrize("case", sorted(PLACEMENTS))
def test_the_products_are_the_same_with_and_without_the_readings(objs, law, case):
    """The cut cells, the basin records (their rim notes apart) and the
    refusals of a build equal those of the on-demand pass; the on-demand
    notes are the build's with the two readings in the one note's place."""
    _cl, cl_a, basins_a, bs_a, _r = _basins_of(objs, law, PLACEMENTS[case])
    _cl, cl_b, basins_b, bs_b, _r = _basins_of(objs, law, PLACEMENTS[case],
                                               rim_diagnostics=True)
    assert cl_a == cl_b
    assert bs_a.refused == bs_b.refused and bs_a.rim_yields == bs_b.rim_yields
    assert (bs_a.grade_unions, bs_a.grade_vertices) == (bs_b.grade_unions, bs_b.grade_vertices)
    for a, b in zip(basins_a, basins_b, strict=True):
        assert _dc.replace(a, notes=()) == _dc.replace(b, notes=())
        i = a.notes.index(_rim.ON_DEMAND)
        assert b.notes[i].startswith(_RIM_HEADS[0]) and b.notes[i + 1].startswith(_RIM_HEADS[1])
        assert a.notes[:i] == b.notes[:i] and a.notes[i + 1:] == b.notes[i + 2:]


def test_the_switch_is_read_at_one_site_and_the_replays_ask_for_it():
    """One keyword, read once in ``build_basins``; ``planar.build.build``
    hands it through; the structures replay asks for the readings and the
    channel DECISION pass (nothing of it is published) never does."""
    import importlib
    _main = importlib.import_module("auto_patch_v2.planar.__main__")
    _build = importlib.import_module("auto_patch_v2.planar.build")
    src = inspect.getsource(_basins.build_basins)
    assert src.count("if rim_diagnostics else None") == 1
    assert src.count("rim_diagnostics") == 3            # the keyword, its doc, the one read
    assert "rim_diagnostics=True" in inspect.getsource(_main.structure_records)
    assert "rim_diagnostics=rim_diagnostics" in inspect.getsource(_build.build)
    assert "rim_diagnostics" not in inspect.getsource(_build.channels_after_basins)
    assert inspect.signature(_build.build).parameters["rim_diagnostics"].default is False
    assert inspect.signature(_basins.build_basins).parameters["rim_diagnostics"].default is False


def test_the_replay_tool_prints_the_readings_it_asked_for(objs, law):
    tool = Path(__file__).resolve().parents[2] / "tools" / "v2_solve_replay.py"
    spec = importlib.util.spec_from_file_location("_v2_solve_replay_rim362", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _cl, _cl3, basins, _bs, _rep = _basins_of(objs, law, PLACEMENTS["open"],
                                              rim_diagnostics=True)

    class _Map:
        pass
    pm = _Map()
    pm.basins = basins
    lines = mod.rim_diagnostic_lines(pm)
    assert [ln.split(": ", 1)[0] for ln in lines] == ["RIM basin:0", "RIM basin:0"]
    assert lines[0].split(": ", 1)[1].startswith(_RIM_HEADS[0])
    assert lines[1].split(": ", 1)[1].startswith(_RIM_HEADS[1])
    src = tool.read_text(encoding="utf-8")
    assert '"--rim-diagnostics"' in src and "rim_diagnostics=rim_diagnostics" in src
