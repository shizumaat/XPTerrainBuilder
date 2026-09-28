"""A PAD OUTLINE NEVER REACHES THE AIRSIDE SOLVE (issue #67; §20b (1)/(1b);
owner RULINGS 14ah "airside is king", 23a "the apron welds to the pad").

MEASURED at HECA (lane ``clustertrim``, capture on main be2dfd43, one
142 m square trimmed off one pad outline, ``--from classify``): 413 non-pad
airside vertices moved > 0.02 m (worst 0.27 m), 388 of them beyond 500 m.
Two channels carried the outline into stage 1, and closing BOTH (never
either alone: 615 / 568 movers) moved 0:

1. THE APRON TREND's bodies were the bending class (``apron_roles``), which
   holds the pad, ``groundside_pavement`` and ``parking_lot`` beside the
   apron; the pad's vertices occupied DEM cells of the fit, and 680 stage-1
   apron rows were retargeted up to 0.36 m.  Now the airside is fitted over
   the airside alone and the conforming vertices take a second pass.
2. THE PAD's HARD 1 % CEILING over pairs of apron rim vertices stood in
   stage 1 (20,748 rows): ``[design] conforming_hard_rulings`` names it as
   a conforming hard law, and stage 1 refuses it.

Each reading carries its CONTROL (the pre-#67 reading on the same
fixture), so neither twin can pass vacuously.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import apron_trend as _at
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.apron_trend import apron_trend_targets
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import airside_stage_roles, apron_roles
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.design import assemble, stage_split
from auto_patch_v2.solve.design_report import DesignReport
from auto_patch_v2.solve.design_roles import conforming_rulings, ruling_head
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2 import test_v2aprontrend as _tr
from tests.auto_patch_v2 import test_v2staged as _st

CEILING = "structures.building_pad pad_slope_max ceiling"


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── (1) THE APRON TREND IS FITTED OVER THE AIRSIDE ALONE ────────────────

def _trend_map(law, pad_far_y: float):
    """The 1.2 km apron of the apron-trend twin on its noisy ground, with a
    PAD welded along its far edge — the pad's own far edge at
    ``pad_far_y``, so two arms differ ONLY in how far the pad reaches
    AWAY from the apron (the shared edge and its corners are identical)."""
    airport, r = _tr._airport(law, _tr._CornerDem(noise=_tr.NOISE_M))
    far = 300.0 + _tr.APRON_WIDTH
    cells = (
        Cell(0, "runway", "09/27",
             _rect(r, -_tr.RUN_LEN / 2, -HALF_WIDTH, _tr.RUN_LEN / 2, HALF_WIDTH),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA",
             _rect(r, -_tr.APRON_LEN / 2, 300.0, _tr.APRON_LEN / 2, far),
             (), None, "D", "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(r, -150.0, far, 150.0, pad_far_y),
             (), None, None, "airside", "pad", {}),
    )
    pm, _s = build(airport, Classification(cells, (), {}, ()), law)
    return pm, airport


def _targets_by_xy(law, pm, airport, roles):
    t = apron_trend_targets(pm, law, airport)
    out = {}
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                if v in t:
                    x, y = pm.vertices[v].xy
                    out[(round(x, 6), round(y, 6))] = t[v]
    return out


def _worst_airside_retarget(law, near, far) -> tuple[float, int]:
    a = _targets_by_xy(law, *near, {"apron"})
    b = _targets_by_xy(law, *far, {"apron"})
    both = set(a) & set(b)
    assert len(both) > 50, "the fixture's apron carries trend targets"
    return max(abs(a[k] - b[k]) for k in both), len(both)


@pytest.fixture(scope="module")
def trend_arms(law):
    return _trend_map(law, 300.0 + _tr.APRON_WIDTH + 100.0), \
        _trend_map(law, 300.0 + _tr.APRON_WIDTH + 260.0)


def test_a_pad_reaching_further_retargets_no_airside_vertex(law, trend_arms):
    """The pad grows 160 m AWAY from the apron: every apron vertex's trend
    target is unchanged to 1e-9 m — the airside's fit reads no pad cell."""
    worst, n = _worst_airside_retarget(law, *trend_arms)
    assert worst < 1e-9, (worst, n)


def test_the_control_one_body_fit_retargets_the_apron(law, trend_arms,
                                                       monkeypatch):
    """THE CONTROL — the pre-#67 reading (one body over every bending
    role): the SAME two pads retarget the apron, so the twin above is not
    vacuous."""
    monkeypatch.setattr(_at, "airside_stage_roles", lambda lw: apron_roles(lw))
    worst, _n = _worst_airside_retarget(law, *trend_arms)
    assert worst > 1e-3, worst


def test_the_conforming_vertices_keep_a_trend_target(law, trend_arms):
    """The second pass: the pad's own vertices (which read the airside's
    cells, never the reverse) still carry a target."""
    for pm, airport in trend_arms:
        pad = _targets_by_xy(law, pm, airport, {"building"})
        assert pad, "the pad's vertices carry trend targets"


def test_the_airside_stage_roles_live_in_the_law_layer(law):
    """One derivation, re-exported: ``constraints`` may not import
    ``solve`` (M0 §1), so the roles moved to ``law.tables``."""
    from auto_patch_v2.solve.design_roles import airside_stage_roles as s
    assert s is airside_stage_roles
    assert "building" not in airside_stage_roles(law)
    assert "apron" in airside_stage_roles(law)


# ── (2) THE PAD's HARD CEILING IS NOT STAGE 1's ─────────────────────────

def _stage_one_heads(law):
    airport = _st._airport(law)
    pm, _s = build(airport, Classification(tuple(_st._cells()), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    drop, foreign = stage_split(pm, cs, law)
    base = assemble(pm, cs, law, DesignReport(), drop=drop, fixed=foreign,
                    stage_roles=airside_stage_roles(law))
    heads = [ruling_head(row) for _t, _h, row in base.one]
    # the fixture carries the class: ceiling rows over two apron vertices
    all_air = [row for terms, _h, row in
               assemble(pm, cs, law, DesignReport()).one
               if ruling_head(row) == CEILING]
    return heads, all_air


def test_the_register_names_the_pads_ceiling_as_conforming(law):
    assert CEILING in law.tables.emit.design.conforming_hard_rulings
    assert CEILING in law.tables.emit.design.hard_rulings
    assert CEILING in conforming_rulings(law)


def test_stage_one_assembles_no_pad_ceiling_row(law):
    heads, all_air = _stage_one_heads(law)
    assert all_air, "the fixture prices the pad's ceiling"
    assert CEILING not in heads


def test_the_control_without_the_register_puts_the_ceiling_in_stage_one(law):
    """THE CONTROL: the register emptied (the pre-#67 law) — the pad welded
    to the apron puts its ceiling over apron pairs INTO stage 1."""
    lw = _st._law_arm(law, conforming_hard_rulings=())
    heads, _all = _stage_one_heads(lw)
    assert CEILING in heads


def test_a_stray_conforming_head_is_refused(law):
    """The register names which HARD law conforms; it makes nothing hard."""
    from auto_patch_v2.law.design_schema import check_design
    d = _dc.replace(law.tables.emit.design,
                    conforming_hard_rulings=("no such ruling",))
    with pytest.raises(ValueError):
        check_design(d, ValueError, None)


# ── (3) THE STAGE-1 DUMP CARRIES THE --placement ARM ────────────────────

def test_the_stage1_dump_passes_the_placement_arm_to_the_prelude(monkeypatch,
                                                                 tmp_path):
    """Issue #67's own note: ``--placement pad_keeps_footprint=false``
    through ``--stage1-dump`` printed no arm line — the dump's capture path
    called the replay prelude without it, so the arm was silently the
    shipped law.  The prelude now receives it."""
    import importlib.util
    from pathlib import Path
    tool = Path(__file__).resolve().parents[2] / "tools" / "v2_solve_replay.py"
    spec = importlib.util.spec_from_file_location("_v2sr_clustertrim", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen = {}

    class _Stop(Exception):
        pass

    def _prelude(pkl, resume, drop, dw=None, *a, **k):
        seen.update(k)
        raise _Stop
    monkeypatch.setattr(mod, "replay_problem", _prelude)
    with pytest.raises(_Stop):
        mod.stage1_population(tmp_path / "x.pkl", [], tmp_path / "o.json.gz",
                              None, from_capture=True, resume="classify",
                              placement={"pad_keeps_footprint": "false"})
    assert seen.get("placement") == {"pad_keeps_footprint": "false"}
