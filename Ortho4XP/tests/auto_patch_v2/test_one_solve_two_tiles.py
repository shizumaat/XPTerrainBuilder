"""ONE AIRPORT, ONE SOLVE ACROSS TWO TILES (issue #1645; spec §38 (4),
RULINGS 2026-09-13am "ONE AIRPORT, ONE SOLVE, PER-TILE PIECES").

A synthetic airport straddling the 24°E seam: its pack has a DSF on each
side.  Both tile builds must read the SAME inputs — every tile's dump, the
origin's first, the same ids, the same cache keys — and each tile's object
stage must write only its own rows.  Before #1645 each tile build read its
own tile's dump only (KPHX: 18 pavements / 2,072 objects in one build, 47 /
4,594 in the other, the same vertex 7.31 m apart).
"""
from __future__ import annotations

import dataclasses as _dc
from pathlib import Path

from auto_patch_v2.airport import dsf as S
from auto_patch_v2.airport import partition_cache as PC
from auto_patch_v2.airport.load import Inputs, load_with_report, tiles_of
from auto_patch_v2.airport.tile_rows import for_tile
from auto_patch_v2.law import Law
from auto_patch_v2.model.rebake import Member, RebakePlan, Unit

ICAO = "ZZTT"
LA = 37.90
#: the runway runs from 23.995 to 24.003: the reference point (its mean)
#: lies WEST of the seam, so the origin tile is +37+023
W, E = 23.995, 24.003
ORIGIN, EAST = (37, 23), (37, 24)


def _pav(lo: float) -> str:
    d = 0.0006
    return ("110 1 0.25 0 pav\n"
            f"111 {LA:.6f} {lo:.6f}\n111 {LA:.6f} {lo + d:.6f}\n"
            f"111 {LA + d:.6f} {lo + d:.6f}\n113 {LA + d:.6f} {lo:.6f}\n")


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "XP"
    apt = root / "Custom Scenery" / "Seam Pack" / "Earth nav data" / "apt.dat"
    apt.parent.mkdir(parents=True)
    rw = (f"100 45.00 1 0 0.25 0 0 0 09 {LA:.6f} {W:.6f} 0 0 3 0 0 0 "
          f"27 {LA:.6f} {E:.6f} 0 0 3 0 0 0\n")
    apt.write_text("I\n1100 Generated\n" f"1 100 0 0 {ICAO} Seam Fixture\n"
                   + rw + _pav(23.996) + _pav(24.001) + "99\n",
                   encoding="utf-8", newline="")
    return root


def _dump(path: Path, lo: float) -> str:
    """A tile dump: one material page and two objects near ``lo``."""
    d = 0.0004
    pts = [(lo, LA), (lo + d, LA), (lo + d, LA + d), (lo, LA + d)]
    rows = (["POLYGON_DEF g/concrete_a.pol", "OBJECT_DEF o/hut.obj",
             "BEGIN_POLYGON 0 65535 2", "BEGIN_WINDING"]
            + [f"POLYGON_POINT {x:.9f} {y:.9f}" for x, y in pts]
            + ["END_WINDING", "END_POLYGON",
               f"OBJECT 0 {lo:.9f} {LA + 0.0002:.9f} 0",
               f"OBJECT 0 {lo + 0.0003:.9f} {LA + 0.0002:.9f} 90"])
    path.write_text("\n".join(rows + [""]), encoding="utf-8", newline="")
    return str(path)


def _inputs(root: Path, dumps) -> Inputs:
    return Inputs(xplane_root=str(root), cifp_dir="", osm_root="",
                  elevation_root="", mod_cache_root="", dsf_dump_path=dumps)


def test_row_of_reads_the_origin_and_a_neighbour_tile():
    assert S.on_tile("dsf:obj7", None) == "dsf:obj7"
    assert S.on_tile("dsf:obj7", (33, -112)) == "dsf:obj7@+33-112"
    assert S.row_of("dsf:obj7") == (None, 7)
    assert S.row_of("dsf:obj7@+33-112") == ((33, -112), 7)
    assert S.row_of("dsf:object7") == (None, None)
    assert S.row_of("dsf:pol3") == (None, None)


def test_both_tile_builds_read_every_tile_origin_first(tmp_path):
    """The tile set is the airport's, never the build tile's; the loads of
    the two tile builds are the same airport, id for id."""
    root = _root(tmp_path)
    assert tiles_of(ICAO, str(root)) == [ORIGIN, EAST]
    from auto_patch.engine_v2 import airport_tiles
    assert (airport_tiles(str(root), ICAO, *ORIGIN)
            == airport_tiles(str(root), ICAO, *EAST) == [ORIGIN, EAST])
    dumps = {ORIGIN: _dump(tmp_path / "+37+023.dsf.t.text", 23.9962),
             EAST: _dump(tmp_path / "+37+024.dsf.t.text", 24.0012)}
    law = Law.for_airport(ICAO)
    a1, r1 = load_with_report(ICAO, _inputs(root, dumps), law)
    a2, r2 = load_with_report(ICAO, _inputs(root, dict(reversed(dumps.items()))), law)
    ids = [o.id for o in a1.dsf_objects]
    assert ids == ["dsf:obj0", "dsf:obj1", "dsf:obj0@+37+024", "dsf:obj1@+37+024"]
    assert [p.id for p in a1.pavements if p.id.startswith("dsf:")] == [
        "dsf:pol0", "dsf:pol0@+37+024"]
    assert a1.dsf_objects == a2.dsf_objects and a1.pavements == a2.pavements
    assert r1.dsf_dump_path == r2.dsf_dump_path == dumps[ORIGIN]
    assert r1.dsf_dump_paths == r2.dsf_dump_paths == (
        (ORIGIN, dumps[ORIGIN]), (EAST, dumps[EAST]))


def test_a_single_tile_airport_keeps_its_bare_ids(tmp_path):
    root = _root(tmp_path)
    one = _dump(tmp_path / "+37+023.dsf.t.text", 23.9962)
    a, rep = load_with_report(ICAO, _inputs(root, one), Law.for_airport(ICAO))
    assert [o.id for o in a.dsf_objects] == ["dsf:obj0", "dsf:obj1"]
    assert rep.dsf_dump_paths == ((ORIGIN, one),)


def test_the_partition_key_names_the_full_dump_set(tmp_path):
    a = tmp_path / "+37+023.dsf.t.text"
    b = tmp_path / "+37+024.dsf.t.text"
    for f, body in ((a, "A\n"), (b, "B\n")):
        f.write_text(body, encoding="utf-8", newline="")
    assert PC.dump_digest(str(a)) is not None
    # the cache file is named by the origin's dump in both tile builds
    air = type("Air", (), {"pack": type("P", (), {"name": "Seam Pack"})(),
                           "icao": ICAO})()
    assert PC.cache_path(air, str(tmp_path), str(a)).endswith(
        "o4_v2_partition_+37+023_ZZTT.cache")


def _member(oid: str) -> Member:
    return Member(oid, "o/hut.obj", "", "", 0.0)


def test_each_tile_writes_only_its_own_rows():
    plan = RebakePlan(ICAO, "Seam Pack", "/p", (
        Unit("unit:0", (LA, 24.0), 0.0, (_member("dsf:obj0"), _member("dsf:obj0@+37+024"))),
        Unit("unit:1", (LA, 24.0), 0.0, (_member("dsf:obj1@+37+024"),))),
        (), {}, authored_seats=({"id": "dsf:obj1@+37+024", "seat": "x"},
                                {"id": "dsf:obj1", "seat": "x"}),
        origin_tile=ORIGIN)
    strips = ({"riders": [[LA, 23.99, "o/j.obj", 0.0, 1, "", 0.0],
                          [LA, 24.01, "o/j.obj", 0.0, 1, "", 0.0, [37, 24]]]},)
    west, ws = for_tile(plan, strips, ORIGIN)
    east, es = for_tile(plan, strips, EAST)
    assert [[m.id for m in u.members] for u in west.units] == [["dsf:obj0"]]
    assert [[m.id for m in u.members] for u in east.units] == [["dsf:obj0"], ["dsf:obj1"]]
    assert [r["id"] for r in west.authored_seats] == ["dsf:obj1"]
    assert [r["id"] for r in east.authored_seats] == ["dsf:obj1"]
    assert [r[4] for r in ws[0]["riders"]] == [1, None]
    assert [r[4] for r in es[0]["riders"]] == [None, 1]
    # a localised plan is the dump's own: a second call changes nothing
    assert for_tile(east, es, EAST) == (east, es)
    # a plan written before #1645 (no origin tile) is left as it was
    old = _dc.replace(plan, origin_tile=None)
    assert for_tile(old, strips, EAST) == (old, strips)
    assert RebakePlan.from_json(plan.to_json()).origin_tile == ORIGIN
