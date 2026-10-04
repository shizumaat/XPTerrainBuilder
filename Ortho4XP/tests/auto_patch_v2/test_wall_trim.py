"""OWNER RULINGS 2026-10-04p (B) b1 (issue #359; spec §54): THE LOT PAGE
ENDS AT THE WALL — ``classify/wall_trim``.

A lot page ran on under a placed wall to the road's kerb, so road and lot
shared the wall-top kerb vertices (HECA lot ``dsf:objpav394`` / ``route3``
/ ``metal_strip_2.obj`` comp 117).  The wall and the ground between it and
the kerb leave the lot, with the zone band's own groundside stand-off, so
the two can no longer node to one vertex."""
from __future__ import annotations

import os
import subprocess
import sys

from shapely.geometry import LineString, Point, Polygon, box

from auto_patch_v2.airport import road_ramp as rr
from auto_patch_v2.classify import wall_trim
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m

from test_roadrows143 import _airport, _rect

#: a road along x 300..306, a lot east of it sharing the kerb x = 306, a
#: 0.3 m wall 0.8 m inside the lot's edge for y 120..180 (a gate beyond)
ROAD = (300.0, 100.0, 306.0, 200.0)
LOT = (306.0, 100.0, 360.0, 200.0)
WALL = box(306.8, 120.0, 307.1, 180.0)
#: the HECA class the first arm missed: the wall stands ON the kerb
KERB_WALL = box(305.9, 120.0, 306.2, 180.0)


def _law():
    return Law.for_airport("ZZZZ")


def _cell(i, role, ref, rect, side="groundside"):
    return Cell(i, role, ref, _rect(*rect), (), None, None, side, role, {})


def _cells():
    return [_cell(0, "service_road", "route3", ROAD),
            _cell(1, "parking_lot", "lotA", LOT),
            _cell(2, "apron", "apronA", (200.0, 100.0, 300.0, 200.0), "airside")]


def _walls(monkeypatch, *polys):
    pieces = tuple(rr.WallPiece(g, 3.1, f"wall#comp{i}")
                   for i, g in enumerate(polys))
    monkeypatch.setattr(wall_trim, "wall_pieces",
                        lambda airport, cfg=None: pieces)


def _standoff(law):
    return law.tables.zones.adjacent_ground.groundside_cutback_m \
        + snap_margin_m(law)


def test_the_shadow_is_the_wall_and_the_ground_to_the_kerb():
    road = Polygon(_rect(*ROAD))
    sh = wall_trim.wall_shadow(WALL, road, 4.0, 0.5)
    assert sh.contains(WALL.buffer(-0.01))
    assert sh.contains(Point(306.4, 150.0))            # between kerb and wall
    assert not sh.contains(Point(307.6, 150.0))        # the pad's side
    assert not sh.intersects(Point(306.4, 190.0))      # past the wall's end
    # a wall beyond the reach casts none
    assert wall_trim.wall_shadow(box(320.0, 120.0, 320.3, 180.0), road,
                                 4.0, 0.5).is_empty


def test_the_lot_page_ends_at_the_wall(monkeypatch):
    law = _law()
    _walls(monkeypatch, WALL)
    cells = _cells()
    out, st = wall_trim.trim_lots_at_walls(_airport(law), cells, law,
                                           load_rules())
    assert st["wall_trim_lots"] == 1 and st["wall_trim_walls"] == 1
    assert st["wall_trim_m2"] > 0.0
    assert [c.id for c in out] == list(range(len(out)))
    lot_c = next(c for c in out if c.ref == "lotA")
    assert lot_c.role == "parking_lot" and lot_c.evidence["wall_trim"] == 1.0
    lot = Polygon(lot_c.ring)
    road = Polygon(_rect(*ROAD))
    assert not lot.intersects(WALL)
    assert not lot.intersects(Point(306.4, 150.0))
    assert lot.distance(LineString([(306.95, 121.0), (306.95, 179.0)])) \
        >= snap_margin_m(law) - 1e-6
    # along the wall the lot stands off the KERB by the zone band's own
    # stand-off: no lot vertex can node back onto the road
    assert lot.intersection(box(300.0, 121.5, 320.0, 178.5)).distance(road) \
        >= _standoff(law) - 1e-6
    # through the gate and past the wall's end the lot still meets the road
    assert lot.intersects(Point(306.0, 110.0).buffer(0.01))
    assert lot.intersects(Point(306.0, 195.0).buffer(0.01))
    # the road and the apron are untouched; the pad's side is intact
    assert out[0] == cells[0] and out[-1].ring == cells[2].ring
    assert lot.contains(Point(308.5, 150.0))


def test_a_wall_on_the_kerb_still_leaves_the_stand_off(monkeypatch):
    law = _law()
    _walls(monkeypatch, KERB_WALL)
    out, st = wall_trim.trim_lots_at_walls(_airport(law), _cells(), law,
                                           load_rules())
    assert st["wall_trim_lots"] == 1
    lot = Polygon(next(c for c in out if c.ref == "lotA").ring)
    road = Polygon(_rect(*ROAD))
    assert lot.intersection(box(300.0, 121.5, 320.0, 178.5)).distance(road) \
        >= _standoff(law) - 1e-6
    for x, y in lot.exterior.coords:
        if 121.5 <= y <= 178.5:
            assert x - 306.0 >= _standoff(law) - 1e-6


def test_only_lots_are_trimmed(monkeypatch):
    law = _law()
    _walls(monkeypatch, WALL)
    cells = [_cell(0, "service_road", "route3", ROAD),
             _cell(1, "apron", "apronB", LOT, "airside"),
             _cell(2, "service_road", "route9", (306.0, 210.0, 360.0, 216.0))]
    out, st = wall_trim.trim_lots_at_walls(_airport(law), cells, law,
                                           load_rules())
    assert out is cells and st["wall_trim_lots"] == 0


def test_no_wall_no_trim(monkeypatch):
    law = _law()
    _walls(monkeypatch)
    cells = _cells()
    out, st = wall_trim.trim_lots_at_walls(_airport(law), cells, law,
                                           load_rules())
    assert out is cells and st == {"wall_trim_lots": 0, "wall_trim_walls": 0,
                                   "wall_trim_m2": 0.0}


def test_the_trim_publishes_no_pad_pair():
    """Round 2 ruling: the trim ONLY — no ``wall_lot`` channel, the wall
    terrace rows read a terrace's own pairs and nothing else."""
    import inspect
    from auto_patch_v2.constraints import road_ramp as cr
    assert "wall_lot" not in inspect.getsource(rr.with_road_ramp)
    assert "wall_lot" not in inspect.getsource(cr.wall_terrace_rows)


def test_the_module_imports_alone():
    """A fresh interpreter imports the module on its own (the frozen
    engine and the peer lane's per-module twin)."""
    src = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src")
    env = dict(os.environ, PYTHONPATH=os.path.abspath(src))
    r = subprocess.run([sys.executable, "-c",
                        "import auto_patch_v2.classify.wall_trim"],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_a_chip_the_wall_leaves_is_no_lot(monkeypatch):
    """What is left of a lot under the planar sliver floor (16 m²) is
    dropped, never minted as a face of its own."""
    law = _law()
    _walls(monkeypatch, WALL)
    cells = [_cell(0, "service_road", "route3", ROAD),
             _cell(1, "groundside_pavement", "chip", (306.0, 140.0, 308.6, 160.0))]
    out, st = wall_trim.trim_lots_at_walls(_airport(law), cells, law,
                                           load_rules())
    assert st["wall_trim_lots"] == 1
    assert [c.ref for c in out] == ["route3"]
