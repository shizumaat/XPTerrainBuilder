"""#1741 LIRF: a weld never drops a real part of a pavement cell.

The bent ring of a junior cell can pinch into parts.  ``_weld_one`` keeps
the largest, so it must refuse the weld when any other part is wider than
the weld tolerance (real pavement, not a sliver the weld made).  MEASURED
at LIRF (Aerosoft pack): a 36,655 m2 parallel taxiway came back as
28,163 + 8,056 m2 and the 8,056 m2 piece was graded as runway strip.
"""
from shapely.geometry import LineString, Polygon

from auto_patch_v2.planar import weld

# two pavement squares joined by a 0.8 m neck; a senior edge runs along
# the neck's middle, so projecting the neck onto it pinches the cell in two
_CELL = Polygon([(0, 0), (40, 0), (40, 20), (50, 20), (50, 0), (80, 0),
                 (80, 30), (50, 30), (50, 20.8), (40, 20.8), (40, 40), (0, 40)])
_SENIOR = LineString([(40, 20.4), (50, 20.4)])


def test_pinched_weld_is_refused_not_cropped():
    q, _moved, _ins, _passes = weld._weld_one(_CELL, _SENIOR, 1.0)
    assert q is None


def test_sliver_part_is_still_dropped():
    # the same neck, but the far square is itself a sliver (0.5 m wide):
    # dropping it is the weld's own clean-up and stays allowed
    cell = Polygon([(0, 0), (40, 0), (40, 20), (50, 20), (50, 19.9),
                    (80, 19.9), (80, 20.4), (50, 20.4), (50, 20.8),
                    (40, 20.8), (40, 40), (0, 40)])
    q, _moved, _ins, _passes = weld._weld_one(cell, _SENIOR, 1.0)
    assert q is not None and q.is_valid
    assert q.area > 0.95 * 1600.0
