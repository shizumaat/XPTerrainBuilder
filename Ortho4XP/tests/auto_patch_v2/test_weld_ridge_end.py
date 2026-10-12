"""THE WELD READS A BREAKLINE'S END ON A SENIOR BOUNDARY AS ITS VERTEX (#556).

``planar/weld.py`` half (2) inserts a senior's ring vertices into the junior
segments they lie within the tolerance of.  A runway's ridge ends ON the
runway's end edge and becomes a vertex there only at the noding, after the
weld: a rim cell (the pack's own draped runway polygon, a little wider and
longer than the apt.dat rectangle) kept an end edge running corner to
corner a hair past the ridge's end, and the crown stood over it as a cliff.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.classify.roles import Cell  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.planar.weld import weld_cells  # noqa: E402

RIDGE_END = (0.0, 1000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cell(i: int, ring) -> Cell:
    return Cell(i, "runway", "01/19", tuple(ring), (), 4, "E", "airside",
                "runway", {})


def _cells(past_end: float = 0.4, side: float = 1.1):
    """A runway rectangle 40 m wide along +y and the RIM of the polygon the
    pack drew it with: ``side`` wider on both sides and ``past_end`` longer
    at the 19 end — one U-shaped cell sharing the rectangle's edges."""
    runway = [(-20.0, 0.0), (20.0, 0.0), (20.0, 1000.0), (-20.0, 1000.0)]
    w = 20.0 + side
    rim = [(20.0, 500.0), (w, 500.0), (w, 1000.0 + past_end),
           (-w, 1000.0 + past_end), (-w, 500.0), (-20.0, 500.0),
           (-20.0, 1000.0), (20.0, 1000.0)]
    return (_cell(0, runway), _cell(1, rim))


def test_the_ridge_end_enters_the_rim_edge_it_lies_beside(law):
    cells = _cells()
    plain, st0 = weld_cells(cells, law)
    assert plain[1].ring == cells[1].ring          # nothing within reach before
    welded, st = weld_cells(cells, law, (RIDGE_END,))
    new = sorted(set(welded[1].ring) - set(cells[1].ring))
    assert len(new) == 1
    assert st.vertices_inserted == st0.vertices_inserted + 1
    assert st.nodes_seen == 1
    # THE NECK: an input quantum off the node toward the edge it entered,
    # so the U is not pinched into two halves (one of which would be lost)
    quantum = law.tables.emit.identity.input_quantum_m
    assert Point(new[0]).distance(Point(RIDGE_END)) == pytest.approx(quantum)
    assert new[0][1] > RIDGE_END[1]
    poly = Polygon(welded[1].ring)
    assert poly.is_valid and poly.geom_type == "Polygon"
    # the rim keeps both sides; only the sliver past the end is given up
    assert poly.area == pytest.approx(
        Polygon(cells[1].ring).area - 0.5 * 42.2 * 0.4, abs=0.1)
    assert welded[0].ring == cells[0].ring          # the senior never moves


def test_the_weld_is_a_fixed_point_with_the_node(law):
    """The neck vertex is never projected back onto the senior edge and the
    node enters once: welding the result again changes nothing."""
    once, _ = weld_cells(_cells(), law, (RIDGE_END,))
    twice, st = weld_cells(once, law, (RIDGE_END,))
    assert twice[1].ring == once[1].ring


def test_a_node_off_every_senior_boundary_is_not_a_vertex(law):
    """Only a node ON a senior boundary is one of its vertices: a ridge
    station inside the runway is nobody's boundary vertex."""
    cells = _cells()
    welded, st = weld_cells(cells, law, ((0.0, 999.5), (0.0, 990.0)))
    assert welded[1].ring == cells[1].ring
    assert st.nodes_seen == 0


def test_an_edge_beyond_the_tolerance_is_left_alone(law):
    """The weld's own horizon: an end edge further off than
    ``weld_spacing_m`` is a strip of pavement, not a sliver."""
    tol = law.tables.emit.identity.weld_spacing_m
    cells = _cells(past_end=tol + 0.5)
    welded, _ = weld_cells(cells, law, (RIDGE_END,))
    assert welded[1].ring == cells[1].ring


def test_no_nodes_is_the_weld_as_it_was(law):
    cells = _cells()
    a, sa = weld_cells(cells, law)
    b, sb = weld_cells(cells, law, ())
    assert a == b and sa == sb
