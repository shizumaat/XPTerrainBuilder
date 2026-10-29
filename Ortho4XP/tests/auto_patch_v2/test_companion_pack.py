"""Owner RULINGS 2026-10-28p (5) (Q244 a; #1301 / #1279 LFPG): an
objects-only COMPANION pack -- no apt.dat, objects of its own inside the
airport boundary -- is re-seated with the main pack; an OVERLAY pack (one
that places only library objects) is left alone.  The witness is the
pack's own content (``airport/companion``), never its name.
"""
from __future__ import annotations

import os
import types

from auto_patch_v2.airport import companion as C

TILE = (49, 2)
DSF = os.path.join("Earth nav data", "+40+000", "+49+002.dsf")


def _touch(path):
    with open(path, "w", encoding="utf-8", newline="\n"):
        pass


def _pack(scenery, name, *, apt=False, objs=(), dsf=True):
    root = os.path.join(scenery, name)
    os.makedirs(os.path.join(root, "Earth nav data", "+40+000"))
    if apt:
        _touch(os.path.join(root, "Earth nav data", "apt.dat"))
    if dsf:
        open(os.path.join(root, DSF), "wb").close()
    for rel in objs:
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        _touch(os.path.join(root, rel))
    return root


def _scenery(tmp_path):
    scenery = os.path.join(str(tmp_path), "Custom Scenery")
    main = _pack(scenery, "main airport", apt=True, objs=("objects/t2.obj",))
    comp = _pack(scenery, "terminals", objs=("AIRPORT/K9/K9_8.obj",))
    over = _pack(scenery, "overlay")                 # library objects only
    other = _pack(scenery, "another airport", apt=True, objs=("o/x.obj",))
    bare = _pack(scenery, "no tile", objs=("o/y.obj",), dsf=False)
    return main, comp, over, other, bare


def test_candidates_are_packs_with_no_apt_dat_and_a_tile_dsf(tmp_path):
    main, comp, over, other, bare = _scenery(tmp_path)
    assert C._candidates(main, *TILE) == [over, comp]      # folder-name order
    # only a pack shipping objects of its own is worth a DSF dump
    assert C.dump_candidates(main, *TILE) == [comp]


def _row(path, lon, lat):
    return types.SimpleNamespace(def_path=path, lon=lon, lat=lat, heading_deg=0.0,
                                 elevation=None, kind="OBJECT")


def test_only_pack_local_objects_inside_the_airport_are_admitted(tmp_path):
    _main, comp, _over, _other, _bare = _scenery(tmp_path)
    dump = types.SimpleNamespace(placements=[
        _row("AIRPORT/K9/K9_8.obj", 2.56, 49.01),     # pack-local, inside
        _row("lib/airport/vehicles/tug.obj", 2.56, 49.01),   # library: an overlay row
        _row("AIRPORT/K9/K9_8.obj", 2.90, 49.30),     # pack-local, outside
        _row("../main airport/objects/t2.obj", 2.56, 49.01),  # another pack's file
        _row("AIRPORT/K9/missing.obj", 2.56, 49.01),  # not shipped
    ])

    def inside(lo, la):
        return abs(lo - 2.56) < 0.05 and abs(la - 49.01) < 0.05
    assert [i for i, _pl in C.admitted(dump, comp, inside)] == [0]


def test_an_overlay_has_no_admitted_row(tmp_path):
    _main, _comp, over, _other, _bare = _scenery(tmp_path)
    dump = types.SimpleNamespace(placements=[_row("lib/airport/tug.obj", 2.56, 49.01)])
    assert C.admitted(dump, over, lambda lo, la: True) == []


def test_place_replaces_an_earlier_builds_plans(tmp_path):
    patch_dir = str(tmp_path / "patches")
    os.makedirs(patch_dir)
    stale = os.path.join(patch_dir, C.COMPANION_PLAN.format(icao="LFPG", k=2))
    _touch(stale)
    src = tmp_path / "LFPG.rebake.c1.json"
    src.write_text("{}", encoding="utf-8", newline="\n")
    placed = C.place(patch_dir, "LFPG", [str(src)])
    assert [os.path.basename(p) for p in placed] == ["o4_v2_rebake_LFPG~1.json"]
    assert not os.path.exists(stale)
    assert C.place(patch_dir, "LFPG", []) == []
    assert not os.listdir(patch_dir)


def test_the_object_stage_reads_a_companion_plan():
    from auto_patch.object_stage import _PLAN_NAME_RE
    assert _PLAN_NAME_RE.match("o4_v2_rebake_LFPG~1.json")
    assert _PLAN_NAME_RE.match("o4_v2_rebake_LFPG.json")
    assert not _PLAN_NAME_RE.match("o4_v2_rebake_LFPG.screen.json")


def test_a_companion_plan_reads_the_airports_stands(tmp_path, monkeypatch):
    """#1639 (LFPG 1.0.444, T1 floated 8 m): a companion ships no apt.dat,
    so the stands its airside floor is read at (RULINGS 2026-10-23b) are
    the AIRPORT's -- the plan carries the serving pack's apt.dat."""
    import dataclasses as dc

    from auto_patch_v2.airport import basin_witness, pack_partition, rebake_plan
    from auto_patch_v2.airport.airside_group_seat import stands_of
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.rebake import RebakePlan

    apt = tmp_path / "main" / "Earth nav data" / "apt.dat"
    apt.parent.mkdir(parents=True)
    apt.write_text("I\n1100 Version\n\n1 1000 0 0 ZZZZ Test\n"
                   "1300 49.0001 2.0002 90.0 gate jets A1\n\n99\n",
                   encoding="utf-8", newline="")

    @dc.dataclass(frozen=True)
    class _Airport:
        frame: object
        pack: object
        dsf_objects: tuple = ()

    frame = types.SimpleNamespace(transformers=lambda: (lambda lo, la: (lo, la), None))
    airport = _Airport(frame, types.SimpleNamespace(apt_dat_path=str(apt)))
    monkeypatch.setattr(C, "_objects", lambda c, to_xy: ())
    monkeypatch.setattr(basin_witness, "read_objects", lambda site, law, cache: ((), None))
    monkeypatch.setattr(pack_partition, "partition_pack", lambda *a, **k: None)
    monkeypatch.setattr(rebake_plan, "plan", lambda site, *a, **k: RebakePlan(
        "ZZZZ", "terminals", site.pack.root, (), (), {}))
    comp = types.SimpleNamespace(name="terminals", root=str(tmp_path / "terminals"))
    (got,) = C.plans(airport, Law.load(), [comp])
    assert got.apt_dat == str(apt) and got.pack_root == comp.root
    assert stands_of(got) == [(49.0001, 2.0002)]
    # the field round-trips, and a plan with none writes no key (the main
    # pack's plan is unchanged)
    assert RebakePlan.from_json(got.to_json()).apt_dat == str(apt)
    assert "apt_dat" not in dc.replace(got, apt_dat="").to_dict()
