"""#2063 (KRNT, owner sim read 2026-11-13 "some floating airplanes"): an
airport pack whose apt.dat defines only OTHER airports is a companion for
the pack-local rows inside this airport that none of its own airports
reads (``object_window.own_claim``); a pack whose apt.dat defines this
airport never is; a body authored far from its anchor is admitted by its
plan centre (``companion.find``'s ``also`` witness)."""
from __future__ import annotations

import os
import types

from auto_patch_v2.airport import companion as C
from auto_patch_v2.airport import object_window as W
from auto_patch_v2.airport.pack_local import admitted, tile_candidates
from auto_patch_v2.model.frame import Frame

TILE = (47, -123)
DSF = os.path.join("Earth nav data", "+40-130", "+47-123.dsf")

#: ZQQA (the pack's own airport) at -122.30; this airport is ~7.5 km east
APT = """I
1200 synthetic
1 100 0 0 ZQQA Alpha
100 45.00 1 0 0.25 1 2 0 09 47.5000 -122.3200 0 0 3 0 0 0 27 47.5000 -122.2900 0 0 3 0 0 0
99
"""


def _pack(scenery, name, apt_text=None, objs=()):
    root = os.path.join(scenery, name)
    os.makedirs(os.path.join(root, "Earth nav data", "+40-130"))
    if apt_text is not None:
        with open(os.path.join(root, "Earth nav data", "apt.dat"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(apt_text)
    open(os.path.join(root, DSF), "wb").close()
    for rel in objs:
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        open(os.path.join(root, rel), "w", encoding="utf-8").close()
    return root


def test_a_pack_of_other_airports_is_a_candidate_a_rival_pack_is_not(tmp_path):
    scenery = os.path.join(str(tmp_path), "Custom Scenery")
    main = _pack(scenery, "a main", APT.replace("ZQQA", "ZQQB"))
    other = _pack(scenery, "b other airport", APT, objs=("o/plane.obj",))
    rival = _pack(scenery, "c rival", APT.replace("ZQQA", "ZQQB"), objs=("o/x.obj",))
    # without the airport named, the old rule: no pack with an apt.dat
    assert tile_candidates(main, *TILE) == []
    assert tile_candidates(main, *TILE, icao="ZQQB") == [other]
    assert C.dump_candidates(main, *TILE, "ZQQB") == [other]
    assert rival not in tile_candidates(main, *TILE, icao="ZQQB")


def test_own_claim_covers_the_packs_airport_and_its_load_box(tmp_path):
    p = os.path.join(str(tmp_path), "apt.dat")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(APT)
    to_xy = Frame("ZQQB", (47.5, -122.20), 9).transformers()[0]
    claim = W.own_claim(p, (47.5, -122.20), to_xy, 1000.0, 0.05)
    from shapely.geometry import Point
    assert claim.contains(Point(*to_xy(-122.305, 47.5)))     # on its runway
    assert claim.contains(Point(*to_xy(-122.284, 47.5)))     # 450 m off its end
    assert not claim.contains(Point(*to_xy(-122.20, 47.5)))  # this airport
    assert W.own_claim(p, (10.0, 10.0), to_xy, 1000.0, 0.05) is None   # far away
    assert W.own_claim(None, (47.5, -122.2), to_xy, 1000.0, 0.05) is None


def _row(path, lon, lat):
    return types.SimpleNamespace(def_path=path, lon=lon, lat=lat, heading_deg=0.0,
                                 elevation=None, kind="OBJECT")


def test_a_body_far_from_its_anchor_is_admitted_by_also(tmp_path):
    scenery = os.path.join(str(tmp_path), "Custom Scenery")
    root = _pack(scenery, "b other airport", APT, objs=("o/plane.obj", "o/hut.obj"))
    dump = types.SimpleNamespace(placements=[
        _row("o/plane.obj", 2.0, 2.0),      # anchor outside; body inside
        _row("o/hut.obj", 2.0, 2.0),        # anchor outside; body outside
        _row("o/hut.obj", 1.0, 1.0),        # anchor inside
    ])
    got = admitted(dump, root, lambda lo, la: lo == 1.0,
                   also=lambda path, pl: path.endswith("plane.obj"))
    assert [i for i, _pl in got] == [0, 2]
