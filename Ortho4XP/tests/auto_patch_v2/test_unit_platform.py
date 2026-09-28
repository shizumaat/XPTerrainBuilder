"""Twins for ONE PLATFORM PER UNIT (owner RULINGS 2026-09-28a (1); issues
#66 / #4; lane ``platform``) — ``constraints/pads._pad_rows`` under
``[building_pad] unit_platform``.

A terminal cluster's plate is priced over its OWN vertices only: no
flatness pair and no ceiling pair reaches a vertex an airside face owns,
so a sloping apron frontage can no longer bend the plate (HECA T3: the
airside-led cap-0 pairs were the only pad rows binding on the plate's
lowest vertex).  The key ships OFF (see the lane report on #66): the
twins pin the mechanism both ways.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.pads import (airside_vertices, pad_flats,
                                            pad_slope_ceiling)
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build

from test_v2clusterpad import HALF_W, RUN_LEN, _airport, _Cluster, _rect

#: a terminal fronting the apron along ONE edge (y = 200); its other three
#: edges stand on ground, so its plate has vertices of its own
PAD = (-120.0, 200.0, 80.0, 280.0)


def _cells():
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W,
                                             RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA", _rect(-300.0, 140.0, 300.0, 200.0),
                 (), None, None, "airside", "apron", {}),
            Cell(2, "building", "padT", _rect(*PAD), (), None, None,
                 "airside", "pad", {})]


def _law(on: bool) -> Law:
    law = Law.for_airport("ZZZZ")
    t = law.tables
    bp = _dc.replace(t.structures.building_pad, unit_platform=on)
    st = _dc.replace(t.structures, building_pad=bp)
    return _dc.replace(law, tables=_dc.replace(t, structures=st))


def _map(law):
    airport = _airport(law)
    airport = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD,), floors=(0.0,)),))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    return airport, pm


@pytest.mark.parametrize("gen", [pad_flats, pad_slope_ceiling])
def test_28a_1_the_platform_prices_no_pair_reaching_the_airside(gen):
    law = _law(True)
    airport, pm = _map(law)
    air = airside_vertices(pm, law)
    rows = gen(pm, law, airport)
    assert rows, "the platform keeps its own plate"
    assert not any(r.a in air or r.b in air for r in rows)
    assert all(r.follows is None for r in rows)


@pytest.mark.parametrize("gen", [pad_flats, pad_slope_ceiling])
def test_28a_1_off_is_the_airside_led_plate(gen):
    law = _law(False)
    airport, pm = _map(law)
    air = airside_vertices(pm, law)
    rows = gen(pm, law, airport)
    # the pad shares its south edge with the apron: OFF prices it
    assert any(r.a in air or r.b in air for r in rows)
