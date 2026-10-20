"""Issue #786 (HECA 30.133878, 31.412821): a DSF road page that runs BESIDE
a mapped-road ribbon of its OWN route is that road's other carriageway — one
road, one profile — so it is not ``own`` and the 10-03l wall-key trim never
splits it from the ribbon's terrace level.  A page that only CONTINUES a
ribbon end to end (no ribbon edge spans its station) stays ``own``.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.airport.road_ramp import _beside_ribbon

ROADS = frozenset({"service_road"})


class _PM:
    """The two members ``_beside_ribbon`` reads: ``faces`` and
    ``ring_vertices`` (a ring here IS its vertex tuple)."""

    def __init__(self, faces):
        self.faces = faces

    @staticmethod
    def ring_vertices(cyc):
        return list(cyc)


def _face(ref, ring):
    return NS(role="service_road", ref=ref, ring=tuple(ring), holes=())


def test_a_page_beside_its_ribbon_is_not_own_and_a_continuation_is():
    # route 1: ribbon 1..4 spans stations 0..50; page 10..12 beside it at
    # 10 / 30 / 50, page 13 continues the road at 80 (end to end)
    frame = {1: (1, 0.0, 2.0), 2: (1, 50.0, 2.0), 3: (1, 50.0, 4.0), 4: (1, 0.0, 4.0),
             10: (1, 10.0, -2.0), 11: (1, 30.0, -2.0), 12: (1, 50.0, -2.0),
             13: (1, 80.0, 0.0),
             20: (2, 30.0, 0.0)}       # another route at the same station
    pm = _PM({0: _face("small_roads:-1", (1, 2, 3, 4)),
              1: _face("dsf:objpav9", (10, 11, 12, 13, 20))})
    out = _beside_ribbon(pm, ROADS, frozenset(), frame, [10, 11, 12, 13, 20])
    assert out == {10, 11, 12}


def test_a_deck_ribbon_spans_nothing():
    frame = {1: (1, 0.0, 0.0), 2: (1, 50.0, 0.0), 10: (1, 20.0, -2.0)}
    pm = _PM({0: _face("small_roads:-1", (1, 2))})
    assert _beside_ribbon(pm, ROADS, frozenset({"small_roads:-1"}), frame, [10]) == set()
    assert _beside_ribbon(pm, ROADS, frozenset(), frame, [10]) == {10}
