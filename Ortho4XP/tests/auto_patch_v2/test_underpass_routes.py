"""Issues #806 / #807: an underpass bore is a road that CROSSES the deck, and
its ramp follows the road at the road's width.

Synthetic, headless: the predicates of ``planar/structure_underpass`` and
``planar/structure_approach.merge_duals`` on hand-built ways.  The site
they were found at is KCLT taxiway U (way −1560) over the tertiary's
trench; the rules are general."""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import structure_underpass as _su
from auto_patch_v2.planar.structure_approach import Bore, Mouth, merge_duals
from auto_patch_v2.planar.structure_stats import StructureStats
from shapely.geometry import LineString


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _way(i, pts, **tags):
    return OsmWay(i, "small_roads", tuple(pts), False,
                  {"highway": "tertiary", **tags})


def test_a_road_beside_the_deck_is_never_bored():
    """#806: the clip ribbon carries the strip, so a road running BESIDE the
    taxiway lands in it; only a route that crosses the aeroway's centreline
    is bored — and a route mapped as two ways counts as one."""
    deck = LineString([(-30.0, 0.0), (30.0, 0.0)])
    crossing_a = _way(1, [(0.0, -20.0), (0.0, 10.0)])
    crossing_b = _way(2, [(0.0, 10.0), (0.0, 25.0)])      # touches the axis only via 1
    beside = _way(3, [(-30.0, 20.0), (-10.0, 22.0)])      # parallel, 20 m off
    pieces = [(w, LineString(w.points)) for w in (crossing_a, crossing_b, beside)]
    kept, left = _su.crossing_pieces(pieces, deck)
    assert [w.id for w, _p in kept] == [1, 2]
    assert [w.id for w in left] == [3]


def test_the_ramp_walks_on_along_the_road_past_the_parents_end(law):
    """#807: a parent mapped as a short way ends; the ramp follows the next
    way of the road (here a bend), never a straight line off its end."""
    parent = LineString([(0.0, 0.0), (0.0, -50.0)])
    nxt = _way(9, [(0.0, -50.0), (40.0, -90.0), (40.0, -200.0)])
    path = _su.approach_along(parent, (0.0, -10.0), (0.0, 1.0), 150.0, [nxt],
                              ("yes",), 60.0)
    assert path[0] == pytest.approx((0.0, -10.0))
    assert (40.0, -90.0) in [tuple(p) for p in path], "the ramp left the road"
    assert LineString(path).length >= 150.0 - 1e-6


def test_the_mouth_takes_the_parent_of_its_own_piece():
    """#807: a bore chained from several pieces; the mouth at its south end
    takes the south piece's road, not the bore's first piece's."""
    north = _way(1, [(0.0, 30.0), (0.0, 10.0)])
    south = _way(2, [(0.0, 10.0), (0.0, -20.0)])
    par_n, par_s = LineString([(0, 60), (0, 10)]), LineString([(0, 10), (5, -90)])
    bore = Bore([north, south], [(0.0, 30.0), (0.0, 10.0), (0.0, -20.0)])
    m = Mouth(bore, (0.0, -20.0), (0.0, 1.0), 7.0, [], (1, 2))
    assert _su.mouth_parent(m, {id(north): par_n, id(south): par_s}) is par_s


def test_a_dual_ramp_spans_its_carriageways_until_they_part(law):
    """#807: the dual's width is read along the ramp, not at the mouth
    alone, and stops where the carriageways part."""
    west = [(-5.5, 0.0), (-5.5, -40.0), (-9.0, -100.0), (-60.0, -150.0)]
    east = [(5.5, 0.0), (5.5, -40.0), (9.0, -100.0), (60.0, -150.0)]

    def mk(xy, ap):
        return Mouth(Bore([], [xy, (xy[0], 10.0)]), xy, (0.0, 1.0), 7.0, ap, ())
    (members, _xy, _inw, width, _axis), = merge_duals(
        [mk(west[0], west), mk(east[0], east)], law, StructureStats())
    assert len(members) == 2
    # wider than the mouth's 18 m (11 m apart + 7 m), and read only until
    # the carriageways stand half the dual separation (20 m) apart: at most
    # 20 + 7 m — never the 120 m the parted roads stand apart further out
    sep = law.tables.structures.tunnel.dual_carriageway_max_separation_m
    assert 18.0 + 5.0 < width <= sep / 2.0 + 7.0 + 1e-6


def test_past_the_parting_the_dual_axis_runs_straight(law):
    """#807: where the carriageways part (a roundabout), the mean of the two
    routes kinks and the corridor folds; the dual's axis runs straight on
    from the parting along its last direction."""
    west = [(-5.5, 0.0), (-5.5, -100.0), (20.0, -180.0)]
    east = [(5.5, 0.0), (5.5, -100.0), (90.0, -110.0)]

    def mk(xy, ap):
        return Mouth(Bore([], [xy, (xy[0], 10.0)]), xy, (0.0, 1.0), 7.0, ap, ())
    (_m, _xy, _inw, _w, axis), = merge_duals([mk(west[0], west), mk(east[0], east)],
                                             law, StructureStats())
    tail = [p for p in axis if p[1] < -105.0]
    assert len(tail) == 1, axis                    # one straight run, no kink
    (x0, y0), (x1, y1) = axis[-2], axis[-1]
    assert abs(x1 - x0) < 0.25 * abs(y1 - y0), axis  # on the shared line south
