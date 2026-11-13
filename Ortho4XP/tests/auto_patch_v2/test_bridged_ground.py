"""#2053 (owner RULINGS 2026-11-13i, "no visible edge floats"): a pack
object that carries its own ground in the water -- an island -- and whose
mapped road bridges run out of its footprint onto the shore is ONE rigid
frame seated so the bridges' far ends meet the shore, on the terrain
model's path (OBJECT_MSL rows, the 13k cut under it, one cell of erosion).
Synthetic geometry, no corpus."""
import os
import sys
import types

import numpy as np
from shapely.geometry import LineString

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import bridged_ground as BG  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport.obj8 import PlacedObject  # noqa: E402
from auto_patch_v2.model.frame import Frame  # noqa: E402


def _quad(x0, x1, z0, z1, y0, y1):
    """Two triangles over the plan box, ``y`` running ``y0`` -> ``y1`` in x."""
    a, b = (x0, y0, z0), (x1, y1, z0)
    c, d = (x0, y0, z1), (x1, y1, z1)
    return [[a, b, c], [b, d, c]]


def _island(arm=True, body=True):
    """A 200 m square island top at y 5 (centre at the origin) and an 8 m
    wide, 50 m road deck out of its east side, ramping 5 -> 4."""
    t = []
    if body:
        t += _quad(-100.0, 100.0, -100.0, 100.0, 5.0, 5.0)
    if arm:
        t += _quad(100.0, 150.0, -4.0, 4.0, 5.0, 4.0)
    return np.asarray(t, dtype=float)


def _geom(tris):
    v = tris.reshape(-1, 3)
    return types.SimpleNamespace(vertices=v, solid=np.arange(len(v)).reshape(-1, 3),
                                 animated=np.zeros(len(tris), dtype=bool))


def _dem(xs, ys):
    """The shore east of x 150 at 2 m, the island's own ground 6 m."""
    xs = np.asarray(xs, float)
    return np.where(xs > 150.0, 2.0, 6.0)


def _sea(shore_x=150.0):
    """Water everywhere but the island's square and the shore."""
    def water(xs, ys):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        island = (np.abs(xs) <= 100.0) & (np.abs(ys) <= 100.0)
        return ~(island | (xs > shore_x))
    return water


#: frame (east, north): authored z is south, so z 0 is north 0
_WAY = [(-1, LineString([(80.0, 0.0), (155.0, 0.0)]))]


def test_the_arm_end_meets_the_shore():
    """The deck stops at x 150, 5 m short of the mapped end: its top there
    (4.0) is put on the shore 1.5 m beyond (2.0) -- zero -2.0."""
    ends = BG._arm_ends(_island(), (0.0, 0.0), 0.0, _WAY, _dem, _sea())
    assert len(ends) == 1
    e = ends[0]
    assert abs(e.xy[0] - 150.0) <= BG.STEP_M and abs(e.xy[1]) < 1e-6
    assert abs(e.top_y - 4.0) < 0.02 and e.ground == 2.0
    assert abs(e.zero + 2.0) < 0.02


def test_a_bridge_of_its_own_is_no_arm():
    """A deck that stops at both ends (no body behind the way) is a bridge,
    the deck law's -- not an arm of a ground object."""
    assert BG._arm_ends(_island(body=False), (0.0, 0.0), 0.0, _WAY, _dem, _sea()) == []


def test_an_end_over_water_is_no_arm():
    assert BG._arm_ends(_island(), (0.0, 0.0), 0.0, _WAY, _dem, _sea(shore_x=1e9)) == []


def test_the_ring_outside_the_island_is_read_for_water():
    tris = _island()
    assert BG._rim_water_share(tris, (0.0, 0.0), 0.0, _sea()) > 0.9
    land = BG._rim_water_share(tris, (0.0, 0.0), 0.0,
                              lambda xs, ys: np.zeros(len(np.asarray(xs)), dtype=bool))
    assert land == 0.0


def _placed(oid, path, xy=(0.0, 0.0)):
    return PlacedObject(oid, path, "/pack/" + path, xy, 0.0, 0.0, "OBJECT", 0.0,
                        None, None, None, None, None, None, deck_kind="candidate")


def _airport(water):
    way = types.SimpleNamespace(id=-1, tags={"highway": "service", "bridge": "yes"},
                                points=[(80.0, 0.0), (155.0, 0.0)])
    dem = types.SimpleNamespace(z_many=_dem, is_water_many=water)
    return types.SimpleNamespace(osm_ways=[way], dem=dem)


def test_the_origin_set_rides_the_island_on_the_terrain_model_path():
    """The island and the walls sharing its frame are one rigid set at the
    bridge-end zero, terrain features out of the deck verdict; a row
    elsewhere is untouched.  Its seat records carry the cut with one cell
    of erosion and say how the zero was read."""
    objs = [_placed("dsf:obj0", "isle.obj"), _placed("dsf:obj1", "walls.obj"),
            _placed("dsf:obj2", "far.obj", (900.0, 0.0))]
    cache = types.SimpleNamespace(geometry=lambda p: _geom(_island()) if "isle" in p
                                  else _geom(_island(arm=False, body=True) * 0.01))
    out = BG.mark(_airport(_sea()), objs, cache)
    got = {o.id: o for o in out}
    assert got["dsf:obj0"].terrain_model is got["dsf:obj1"].terrain_model
    m = got["dsf:obj0"].terrain_model
    assert m.seat_by == BG.SEAT_BY and abs(m.z0 + 2.0) < 0.02 and not m.hideable
    assert got["dsf:obj0"].terrain_feature and got["dsf:obj0"].deck_kind == ""
    assert got["dsf:obj2"].terrain_model is None
    # on land, no seat: §16g and the deck law keep it
    land = BG.mark(_airport(lambda xs, ys: np.zeros(len(np.asarray(xs)), dtype=bool)),
                   objs, cache)
    assert all(o.terrain_model is None for o in land)

    class _A:
        terrain_models = (("dsf:obj0", "isle.obj", m, 0.0),)
        frame = Frame("TEST", (-22.95, -43.15), 11)
    rec = TM.seat_records(_A())[0]
    assert rec["by"] == BG.SEAT_BY and rec["cut"]["erode_m"] == BG.ERODE_M
    assert rec["cut"]["floor"] is True
    assert TM.log_line("TEST", [m]).endswith("none")
    assert "dsf:obj0" in BG.log_line("TEST", [m])


def test_the_cut_erodes_by_the_radius_it_is_given():
    """A narrow low strip inside a high top lowers the bound only within
    the erosion radius: one cell keeps the top beside it."""
    from auto_patch_v2.geom.terrain_deck import DeckGrid
    top = np.full((40, 40), 10.0)
    top[20, :] = 2.0
    g = DeckGrid(0.0, 0.0, top.copy(), top)
    wide = TC._cut_grid(g).top
    narrow = TC._cut_grid(g, BG.ERODE_M).top
    assert narrow[25, 20] == 10.0 and wide[25, 20] == 2.0


def test_the_cut_reads_the_floor_under_a_roof():
    """#2053 round 2: cut to its LOWEST surface, the ground under a roof is
    cut to the ground (not left at the roof), and the edge band never lifts
    an open court over its own surface beside a raised terrace."""
    from auto_patch_v2.geom.terrain_deck import DeckGrid
    bot = np.full((40, 40), 2.0)
    top = bot.copy()
    top[10:20, 10:20] = 9.0               # a roof over the ground
    bot[0:3, 20:30] = top[0:3, 20:30] = 6.0   # a raised terrace at the edge
    g = DeckGrid(0.0, 0.0, bot, top)
    old = TC._cut_grid(g, BG.ERODE_M).top
    new = TC._cut_grid(g, BG.ERODE_M, floor=True).top
    assert old[15, 15] == 9.0 and new[15, 15] == 2.0
    assert old[0, 18] == 6.0 and new[0, 18] == 2.0      # open court at the edge
    assert np.all(new <= g.bot + 1e-9)
    # the record names it, and the tile build reads it
    fit = TC.cut_fit(g, 0.0, 0.0, BG.ERODE_M, floor=True)
    assert np.nanmax(fit.grid.top) <= 6.0


def test_the_tile_build_cuts_to_the_floor_its_record_names(monkeypatch):
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.geom.terrain_deck import DeckGrid
    bot = np.full((10, 10), 1.0)
    top = bot.copy()
    top[3:7, 3:7] = 8.0
    monkeypatch.setattr(TM, "plan_grid", lambda path: DeckGrid(0.0, 0.0, bot, top))
    rec = {"elevation": 0.0, "cut": {"file": "x.obj", "heading": 0.0,
                                     "erode_m": BG.ERODE_M, "floor": True}}
    assert np.nanmax(TCS._fit(rec).grid.top) == 1.0
    del rec["cut"]["floor"]
    assert np.nanmax(TCS._fit(rec).grid.top) == 8.0
