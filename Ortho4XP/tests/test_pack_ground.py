"""Twins of issue #1362 (``airport/pack_ground``; spec
``docs/specs/pack-supplied-ground-spec.md``, owner RULINGS 2026-11-04 A):
a frame set whose ``ATTR_hard`` skin covers the runway IS the pack's
ground -- one rigid seat for the whole set, our ground under its top, no
water pin under it, and the user told when no companion mesh is found."""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.airport import pack_ground as PG
from auto_patch_v2.airport.obj8 import HARD
from auto_patch_v2.constraints import water as W
from auto_patch_v2.geom.terrain_deck import UNDER_M, target_at


def _skin(half_x: float, half_z: float, y: float, hard: bool = True):
    """A flat two-triangle skin at authored height ``y``."""
    v = np.array([[-half_x, y, -half_z], [half_x, y, -half_z],
                  [half_x, y, half_z], [-half_x, y, half_z]], float)
    solid = np.array([[0, 1, 2], [0, 2, 3]])
    return types.SimpleNamespace(vertices=v, solid=solid,
                                 hardness=np.full(2, HARD if hard else 0, np.int8))


class _Cache:
    def __init__(self, geoms):
        self.geoms = geoms

    def geometry(self, path):
        return self.geoms.get(path)


def _obj(oid, path, xy=(0.0, 0.0), hdg=0.0):
    return types.SimpleNamespace(id=oid, path=path, resolved=path, xy=xy,
                                 heading_deg=hdg, agl_m=0.0)


def _airport(half_len=500.0, half_w=20.0):
    rw = types.SimpleNamespace(slab_corners=((-half_len, -half_w), (half_len, -half_w),
                                             (half_len, half_w), (-half_len, half_w)))
    return types.SimpleNamespace(runways=(rw,), pack=types.SimpleNamespace(pack_root=""))


def _flat_dem(z):
    return lambda xs, ys: np.full(np.shape(xs), float(z))


def test_a_hard_skin_over_the_runway_makes_its_whole_frame_one_rigid_ground():
    cache = _Cache({"terrain.obj": _skin(600, 100, 25.0), "decal.obj": _skin(500, 20, 25.05,
                                                                              hard=False),
                    "hangar.obj": _skin(20, 20, 0.0, hard=False)})
    objs = [_obj("dsf:obj0", "terrain.obj"), _obj("dsf:obj1", "decal.obj"),
            _obj("dsf:obj2", "hangar.obj", xy=(300.0, 300.0))]
    fits = PG._ground_fits(_airport(), objs, cache, _flat_dem(27.0))
    assert set(fits) == {"dsf:obj0", "dsf:obj1"}          # the frame, not the hangar
    assert {round(f.z0, 2) for f in fits.values()} == {2.0}   # one seat: 27 - 25
    assert all(f.ground for f in fits.values())
    assert fits["dsf:obj0"].follow == 1.0                  # covers the whole runway
    assert not fits["dsf:obj1"].grid.covered.any()         # only the skin carries rows


def test_a_hard_plate_under_half_the_runway_is_no_ground():
    cache = _Cache({"plate.obj": _skin(200, 30, 5.0)})      # 400 m of a 1000 m runway
    assert PG._ground_fits(_airport(), [_obj("dsf:obj0", "plate.obj")], cache,
                          _flat_dem(0.0)) == {}


def test_the_ground_under_the_skin_stands_under_its_top_even_over_water():
    cache = _Cache({"terrain.obj": _skin(600, 100, 25.0)})
    fit = PG._ground_fits(_airport(), [_obj("dsf:obj0", "terrain.obj")], cache,
                         _flat_dem(25.0))["dsf:obj0"]
    z, under = target_at(fit, np.array([0.0, 0.0, 900.0]), np.array([0.0, 50.0, 0.0]),
                         np.array([np.nan, -3.0, 1.0]))
    assert under.tolist() == [True, True, False]
    assert np.allclose(z[:2], fit.z0 + 25.0 - UNDER_M) and z[2] == 1.0


def test_water_is_land_under_the_pack_ground():
    cache = _Cache({"terrain.obj": _skin(600, 100, 25.0)})
    fit = PG._ground_fits(_airport(), [_obj("dsf:obj0", "terrain.obj")], cache,
                         _flat_dem(25.0))["dsf:obj0"]
    ap = types.SimpleNamespace(terrain_decks=(fit,))
    xy = {1: (0.0, 0.0), 2: (900.0, 0.0)}
    assert W._off_pack_ground(ap, [1, 2], xy) == [2]


def test_the_notice_names_the_skin_and_the_rows_reach_build_done(monkeypatch):
    cache = _Cache({"terrain.obj": _skin(600, 100, 25.0)})
    fits = list(PG._ground_fits(_airport(), [_obj("dsf:obj0", "terrain.obj")], cache,
                               _flat_dem(25.0)).values())
    note = PG.notice("PAKT", fits, "Some Pack")
    assert note["resource"] == "terrain.obj" and note["runway_cover"] == 1.0
    assert "NO companion" in PG.log_line("PAKT", fits, False)
    assert "kept as authored" in PG.log_line("PAKT", fits, True)
    import O4_Tile_Failures as FAIL
    import O4_Unpatched_Airports as UNPATCHED
    from auto_patch import driver
    got = {}
    monkeypatch.setattr(UNPATCHED, "record_degraded",
                        lambda tile, source, rows: got.setdefault(source, rows))
    monkeypatch.setattr(driver.UI, "loud_warning", lambda *a: None)
    driver._record_pack_ground(object(), [{"ok": True, "pack_ground_no_mesh": note}])
    rows = got["pack-ground"]
    assert [r["code"] for r in rows] == ["pack_ground_no_mesh"]
    assert FAIL.severity_of("pack_ground_no_mesh") == "degraded"
    w = FAIL.from_degraded(rows)
    assert w and w[0]["code"] == "pack_ground_no_mesh"
