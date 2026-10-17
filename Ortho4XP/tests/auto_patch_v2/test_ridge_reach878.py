"""THE RIDGE REACHES THE RUNWAY'S OWN PAVEMENT EDGE (#878).

KLGB 08L: the pack drew runway 08L/26R 0.37 m past the apt.dat end and
0.45 m wider on one side.  The rim cell is narrower than the weld
tolerance, so the weld refuses it (it would collapse) and it survives with
an end edge running corner to corner, no vertex on the axis: the crown
stood 0.20 m over it across 0.5 m — a ``runway_step`` DEFECT that refused
the airport.  ``planar/ridge_reach.reach_pavement_edge`` carries the ridge
end to that edge, so the noding makes the vertex the crown stands on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.classify.roles import Cell  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.planar.ridge_reach import reach_pavement_edge  # noqa: E402
from auto_patch_v2.planar.weld import weld_cells  # noqa: E402

REF = "08/26"


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cell(i: int, ring, ref: str = REF, role: str = "runway") -> Cell:
    return Cell(i, role, ref, tuple(ring), (), 4, "E", "airside", "runway", {})


def _runway(past_end: float = 0.366, side: float = 0.45, seam: float = 0.0014):
    """A 46 m runway along +x from x=0 to 1000 and the RIM the pack drew it
    with: ``past_end`` beyond the x=0 end and ``side`` wider on the north,
    starting ``seam`` off the rectangle (the input lattice's own residue)."""
    rect = [(0.0, -23.0), (1000.0, -23.0), (1000.0, 23.0), (0.0, 23.0)]
    s, e = -seam, -past_end
    rim = [(s, -23.0), (s, 23.0 + seam), (1000.0, 23.0 + seam),
           (1000.0, 23.0 + side), (e, 23.0 + side), (e, -23.0)]
    ridge = LineString([(0.0, 0.0), (12.0, 0.0), (1000.0, 0.0)])
    return (_cell(0, rect), _cell(1, rim)), ridge


def test_the_weld_cannot_fold_a_rim_narrower_than_its_tolerance(law):
    """The mechanism: the rim survives the weld whole, ridge end or not."""
    cells, ridge = _runway()
    welded, _st = weld_cells(cells, law, (ridge.coords[0],))
    assert welded[1].ring == cells[1].ring


def test_the_ridge_end_is_carried_to_the_rim_edge(law):
    cells, ridge = _runway()
    tol = law.tables.emit.identity.weld_spacing_m
    gap = 0.5 * law.tables.emit.identity.min_distinct_spacing_m
    (ref, out), = reach_pavement_edge([(REF, ridge)], cells, tol, gap)[0]
    coords = list(out.coords)
    assert ref == REF
    assert coords[0] == pytest.approx((-0.366, 0.0))
    assert coords[1:] == list(ridge.coords)        # the old end stays a station
    assert reach_pavement_edge([(REF, ridge)], cells, tol, gap)[1] == 1


def test_pavement_reaching_past_the_tolerance_is_left_alone(law):
    """A runway-ref pavement running on beyond the weld tolerance is a
    surface of its own (a drawn overrun), never a sliver this rule reaches
    into."""
    cells, ridge = _runway(past_end=3.0)
    tol = law.tables.emit.identity.weld_spacing_m
    out, n = reach_pavement_edge([(REF, ridge)], cells, tol, 0.25)
    assert n == 0 and out[0][1] is ridge


def test_no_rim_and_another_runways_rim_change_nothing(law):
    cells, ridge = _runway()
    tol = law.tables.emit.identity.weld_spacing_m
    out, n = reach_pavement_edge([(REF, ridge)], cells[:1], tol, 0.25)
    assert n == 0 and out[0][1] is ridge
    other = (cells[0], _cell(1, cells[1].ring, ref="12/30"))
    out, n = reach_pavement_edge([(REF, ridge)], other, tol, 0.25)
    assert n == 0 and out[0][1] is ridge
