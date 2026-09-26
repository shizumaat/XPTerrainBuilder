"""Issue #68 (lane ``padgate``): the pad mint's boundary gate admits a piece
by the AREA it has inside the airport, never by one representative point.

OTHH's terminal cluster pad (74,193 m2, 74 % inside the boundary, the
owner's site 25.2599127, 51.6149444 inside it) was dropped because GEOS
put its ``representative_point`` 10.5 m past a concave boundary."""
from shapely.geometry import box
from shapely.ops import unary_union

from auto_patch_v2.classify import evidence as ev

GATE = box(0, 0, 100, 100)


def test_mostly_inside_piece_with_outside_rep_point_is_kept():
    # a block inside the gate + a thin tall stem just outside it: the
    # bounds' mid-height line crosses only the stem, so GEOS's
    # representative point lies OUTSIDE although 92 % of the area is in.
    piece = unary_union([box(10, 0, 100, 90), box(100, 0, 102, 300)])
    assert piece.geom_type == "Polygon"
    assert not GATE.contains(piece.representative_point())
    assert piece.intersection(GATE).area / piece.area > 0.9
    assert ev._inside_gate(piece, GATE)


def test_wholly_outside_piece_is_dropped():
    assert not ev._inside_gate(box(200, 200, 260, 260), GATE)
    # touching the boundary along an edge is not inside
    assert not ev._inside_gate(box(100, 0, 160, 50), GATE)


def test_sliver_inside_is_dropped():
    # 5 % inside, below the floor
    piece = box(95, 0, 195, 50)
    assert 0 < piece.intersection(GATE).area / piece.area < ev.PAD_GATE_MIN_FRACTION
    assert not ev._inside_gate(piece, GATE)


def test_wholly_inside_is_kept():
    assert ev._inside_gate(box(10, 10, 20, 20), GATE)


def test_mint_loop_uses_the_area_gate():
    import inspect
    src = inspect.getsource(ev._pads)
    assert "_inside_gate(piece, gate)" in src
    assert "gate.contains(piece.representative_point())" not in src
