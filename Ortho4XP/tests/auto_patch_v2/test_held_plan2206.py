"""#2206 lane lkdfw: the pack placement plans the crossing decision reads
(``deck_takeover._plan`` / ``_body_top`` / ``_solid_plan``,
``deck_pack_cover._cover_plan``) are read once per geometry and placed
once per placement (``deck_pack_cover.held_plan``) -- the same bytes a
fresh read gives."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport.obj8 import ObjGeometry
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.planar import deck_pack_cover as dpc
from auto_patch_v2.planar import deck_takeover as dt
from shapely.geometry import Polygon, box

LAW = load_default()


def _geom() -> ObjGeometry:
    """A deck slab 6 m up over a ground plate (authored x, y, z)."""
    vs, ts = [], []
    for y, half in ((0.0, 30.0), (6.0, 10.0)):
        n = len(vs)
        vs += [(-half, y, -half), (half, y, -half), (half, y, half), (-half, y, half)]
        ts += [(n, n + 2, n + 1), (n, n + 3, n + 2)]
    k = len(ts)
    return ObjGeometry("x.obj", np.asarray(vs, dtype=float), np.asarray(ts, dtype=np.int64),
                       np.zeros(k, dtype=np.int8), np.zeros((0, 3), dtype=np.int64),
                       np.zeros(k, dtype=bool), np.zeros(k, dtype=bool))


def _objs(n: int):
    return [types.SimpleNamespace(id=f"o{i}", path="x.obj", resolved="x", xy=(70.3 * i, 3.1),
                                  heading_deg=23.0 * i, plan_bbox=box(-1e4, -1e4, 1e4, 1e4))
            for i in range(n)]


def test_each_plan_is_the_fresh_read_and_placed_once(monkeypatch):
    g = _geom()
    cache = types.SimpleNamespace(geometry=lambda _r: g)
    objs = _objs(3)
    ny = float(LAW.tables.structures.bridge.deck_plate_normal_y_min)
    clear = float(LAW.tables.structures.bridge.clearance_minimum_m)
    fresh = {
        "solid": [dpc._placed(o, dt._local_solid(g), LAW) for o in objs],
        "body": [dpc._placed(o, dt._local_body_top(g, -2.0, 9.0, ny, clear), LAW)
                 for o in objs],
        "hull": [dpc._placed(o, dt._local_hull(g), LAW) for o in objs]}
    placed = []
    real = dpc._placed
    monkeypatch.setattr(dpc, "_placed", lambda *a: placed.append(1) or real(*a))
    for _ in range(2):                         # every deck asks again
        got = {"solid": [dt._solid_plan(o, cache, LAW) for o in objs],
               "body": [dt._body_top(o, cache, LAW, -2.0, 9.0) for o in objs],
               "hull": [dt._plan(o, cache, LAW) for o in objs]}
        assert [p.wkb_hex for p in got["solid"]] == [p.wkb_hex for p in fresh["solid"]]
        assert [p.wkb_hex for p in got["body"]] == [p.wkb_hex for p in fresh["body"]]
        assert got["hull"] == [tuple(p.exterior.coords[:-1]) for p in fresh["hull"]]
    assert len(placed) == 9                    # three readings x three placements, once


def test_the_hull_holds_the_drawn_solid():
    # ``_pieces_on`` passes over a mate whose hull, ``_hull_reach`` out,
    # reaches under min_area_m2 of our decks: its solid cannot reach more
    g = _geom()
    cache = types.SimpleNamespace(geometry=lambda _r: g)
    reach = dt._hull_reach(LAW)
    for o in _objs(4):
        sol = dt._solid_plan(o, cache, LAW)
        hull = Polygon(dt._plan(o, cache, LAW))
        assert sol.difference(hull.buffer(reach)).area == 0.0
