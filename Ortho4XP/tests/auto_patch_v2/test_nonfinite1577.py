"""#1577: a held block whose contacts face no taxiway reaches ``inf``
(``planar/pad_blocks.reach``); read through the infinity, its fill level
(``model.platform.fill_levels``) was infinite, every road mouth on the fill
took it as its §37 (6) target and VHHH's design solve answered NaN.  The
reach a fill level reads is the widest FINITE one, and a design off the
reals is refused by name, never emitted."""
from __future__ import annotations

import math
import types

import numpy as np
import pytest

from auto_patch_v2.model.constraints import Band, ConstraintSet, Linear, Pin, Source
from auto_patch_v2.model.platform import fill_levels, widest_reach
from auto_patch_v2.solve.design import NonFiniteDesign, _refuse_nonfinite


def test_widest_reach_ignores_an_unbounded_contact():
    assert widest_reach({"samples_reach": np.full(4, np.inf)}) == 0.0
    assert widest_reach({"samples_reach": np.array([1.0, np.inf, 2.5])}) == 2.5
    assert widest_reach({"samples_reach": None}) == 0.0
    assert widest_reach({}) == 0.0


def test_fill_level_of_a_block_facing_no_taxiway_is_finite():
    reg = types.SimpleNamespace(
        landings={"fill1": {"block": "b1", "y": 0.5, "kind": "deck"}},
        held={"b1": {"datum_pred": 7.3, "samples_reach": np.full(3, np.inf)}})
    pm = types.SimpleNamespace(registries=reg, faces={}, ring_vertices=lambda c: c)
    rec = fill_levels(pm)["fill1"]
    assert math.isfinite(rec["z_hi"])
    assert rec["z_hi"] == pytest.approx(7.8)


S = Source("g", "r", ("vertex:1",))


def test_nonfinite_rows_names_only_rows_no_solve_can_hold():
    held = [Band(1, None, math.inf, S), Band(1, -math.inf, 3.0, S),
            Linear(((1, 1.0),), None, 2.0, S), Pin(1, 2.0, S)]
    off = [Linear(((1, 1.0),), math.inf, math.inf, S), Pin(2, float("nan"), S),
           Band(3, 1.0, -math.inf, S), Linear(((1, float("nan")),), 0.0, 1.0, S)]
    cs = ConstraintSet.from_rows(held + off)
    assert set(map(id, cs.nonfinite_rows())) == set(map(id, off))


def test_a_nan_design_is_refused_naming_the_row():
    cs = ConstraintSet.from_rows([Linear(((0, 1.0),), math.inf, math.inf,
                                         Source("road_ramp", "roads.groundside_road ramp",
                                                ("vertex:0",)))])
    _refuse_nonfinite(cs, np.array([1.0, 2.0]))
    with pytest.raises(NonFiniteDesign, match="road_ramp"):
        _refuse_nonfinite(cs, np.array([float("nan"), 2.0]))
