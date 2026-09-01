"""THE DECK READS ITS OWN FOOTPRINT — the local-top law.

Spec §5-SUPPLEMENT item 1 merged each descending run into ONE surface;
§1 of the road-bridge-deck law asks a LOCAL question of it ("how high is
the structure BENEATH THIS SPAN") and was answering with the shape's
GLOBAL maximum.  MEASURED at LEMD: merged run -11627 spans 598.50 at
bore datum to 606.50 at its far end, the read returned 606.49 under a
deck whose own ground is 603.55, and the clearance came out -2.94 m
where the truth is 5.10 m.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch import road_bridge_deck as RBD
from auto_patch.layout import BuiltShape, ROLE_TUNNEL_RAMP


def _merged_run(n=8, seg=40.0, z0=598.5, z1=606.5):
    """A merged run: stations SEG apart, descending z0 -> z1."""
    st = [(k * seg, z0 + (z1 - z0) * k / n) for k in range(n + 1)]
    left = [(20.0, y) for y, _z in st]
    right = [(0.0, y) for y, _z in st]
    ring = left + right[::-1]
    alts = [z for _y, z in st] + [z for _y, z in reversed(st)]
    return BuiltShape(polygon=Polygon(ring), role=ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp", node_altitudes=alts)


def _corridor(y0, y1):
    return Polygon([(-5.0, y0), (25.0, y0), (25.0, y1), (-5.0, y1)])


class TestTheLocalTop:

    def test_a_corridor_over_the_low_end_reads_the_low_value(self):
        s = _merged_run()
        top = RBD._shape_top_within(s, _corridor(0.0, 14.0), 606.5)
        assert top < 600.0, (
            f"read {top}: the deck crosses the run at bore datum, not at "
            f"its far end")

    def test_a_corridor_over_the_high_end_reads_the_high_value(self):
        s = _merged_run()
        top = RBD._shape_top_within(s, _corridor(306.0, 320.0), 606.5)
        assert top > 605.0

    def test_a_corridor_BETWEEN_two_stations_interpolates(self):
        """THE NORMAL CASE for a merged run: stations stand 40 m apart
        and a deck corridor is ~14 m wide, so the ramp crosses with NO
        vertex inside.  Falling back to the global top there is what
        left the LEMD clearance at -2.94 m."""
        s = _merged_run()
        corr = _corridor(50.0, 64.0)          # strictly between y=40,80
        ring = [pt for pt in s.polygon.exterior.coords]
        from shapely.geometry import Point
        assert not any(corr.covers(Point(x, y)) for x, y in ring), (
            "the fixture must have NO vertex inside the corridor")
        top = RBD._shape_top_within(s, corr, 606.5)
        assert top == pytest.approx(599.9, abs=0.6), (
            f"read {top}: it fell back to the global maximum instead of "
            f"interpolating onto the clipped part")
        assert top < 604.0

    def test_a_shape_that_misses_the_corridor_keeps_the_fallback(self):
        s = _merged_run()
        assert RBD._shape_top_within(
            s, _corridor(9000.0, 9014.0), 606.5) == 606.5

    def test_a_flat_shape_with_no_per_vertex_values_keeps_the_fallback(self):
        s = BuiltShape(polygon=_corridor(0.0, 10.0),
                       role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                       altitude=598.45)
        assert RBD._shape_top_within(
            s, _corridor(0.0, 10.0), 598.45) == 598.45

    def test_the_global_max_is_what_it_replaces(self):
        """The bug, stated: the global maximum of this run is 8 m above
        the value under a span at its low end."""
        s = _merged_run()
        alts = [float(a) for a in s.node_altitudes]
        assert max(alts) - min(alts) == pytest.approx(8.0, abs=0.01)
        local = RBD._shape_top_within(s, _corridor(0.0, 14.0), max(alts))
        assert max(alts) - local > 5.0
