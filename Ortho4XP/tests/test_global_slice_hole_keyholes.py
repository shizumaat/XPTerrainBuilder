"""Hole keyholes in the global slice, and the per-piece buffer memo.

The hole walk in ``pavement.global_slice.build_global_slice_faces`` asks
``_piece.buffer(0.05).covers(candidate_spur)`` for every candidate cut it
considers.  That buffer is INVARIANT per piece, so it is computed once and
memoised (perf P3 lane F).  A memo over a pure function is output-inert
only if the function really is pure on this input and the verdicts it
feeds really are the same — both are asserted here on a many-holed piece,
alongside the hole-survival behaviour the walk exists for.

Hermetic: hand-built geometry, no fixtures, no DEM, no network.
"""
from shapely.geometry import LineString, Point, Polygon

from auto_patch.pavement.global_slice import build_global_slice_faces


def _holed_slab():
    """A 600 x 400 slab with nine square holes."""
    holes = []
    for ix in range(3):
        for iy in range(3):
            x0 = 60.0 + 180.0 * ix
            y0 = 60.0 + 100.0 * iy
            holes.append([(x0, y0), (x0 + 40.0, y0),
                          (x0 + 40.0, y0 + 30.0), (x0, y0 + 30.0)])
    return Polygon([(0.0, 0.0), (600.0, 0.0), (600.0, 400.0), (0.0, 400.0)],
                   holes)


_SLAB = _holed_slab()
_SPINE = LineString([(10.0, 200.0), (590.0, 200.0)])


def test_the_piece_buffer_is_pure_and_its_verdicts_are_stable():
    """The memo's premise: on THIS geometry ``buffer(0.05)`` is
    deterministic and the ``covers`` verdicts it feeds do not move."""
    first = _SLAB.buffer(0.05)
    second = _SLAB.buffer(0.05)
    assert first.wkb == second.wkb
    probes = [
        LineString([(110.0, 75.0), (110.0, 200.0)]),   # in-pavement spur
        LineString([(70.0, 75.0), (70.0, 400.0)]),     # crosses two holes
        LineString([(300.0, 200.0), (900.0, 200.0)]),  # leaves the slab
    ]
    assert ([first.covers(p) for p in probes]
            == [second.covers(p) for p in probes])
    assert first.covers(probes[0]) and not first.covers(probes[2]), \
        "the fixture must exercise both verdicts"


def test_holes_survive_the_slice():
    """Every hole is still unpaved after the cut — the keyhole walk's
    reason to exist, and the behaviour the memo must not change."""
    faces = build_global_slice_faces(_SLAB, [_SPINE])
    assert faces
    for ix in range(3):
        for iy in range(3):
            centre = Point(60.0 + 180.0 * ix + 20.0,
                           60.0 + 100.0 * iy + 15.0)
            assert not any(f.polygon.contains(centre) for f in faces), \
                f"hole ({ix},{iy}) was paved over"


def test_the_slice_covers_the_paved_area():
    """Sanity floor: the faces are the slab, less the holes, less the
    grid-snapped cut linework."""
    faces = build_global_slice_faces(_SLAB, [_SPINE])
    total = sum(f.polygon.area for f in faces)
    assert total > 0.99 * _SLAB.area
