"""#2240 (RULINGS 2026-11-20m): the strip behind a wall seated under the
ground it retains joins the groundside cell beside it -- the lot runs on to
the wall's back face -- never an airside cell, a road or a structure."""
from __future__ import annotations

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.planar.wing_cut import _grow_into
from shapely.geometry import Polygon, box

LAW = Law.for_airport("KDEN")


def _cell(i, role, ref, poly, side):
    return Cell(i, role, ref, tuple(poly.exterior.coords)[:-1], (), None, None, side,
                "test", {})


def test_the_fill_joins_the_lot_beside_it():
    lot = _cell(0, "parking_lot", "dsf:pol1", box(0.0, 3.0, 50.0, 40.0), "groundside")
    fill = (tuple(box(0.0, 0.0, 50.0, 3.0).exterior.coords)[:-1],)
    cells, grown = _grow_into([lot], fill, Polygon(), LAW, frozenset(), 0.5)
    assert grown == 150.0
    assert Polygon(cells[0].ring).bounds == (0.0, 0.0, 50.0, 40.0)


def test_the_fill_never_joins_the_airside():
    apron = _cell(0, "apron", "pav1", box(0.0, 3.0, 50.0, 40.0), "airside")
    fill = (tuple(box(0.0, 0.0, 50.0, 3.0).exterior.coords)[:-1],)
    cells, grown = _grow_into([apron], fill, Polygon(), LAW, frozenset(), 0.5)
    assert grown == 0.0 and cells[0] is apron
