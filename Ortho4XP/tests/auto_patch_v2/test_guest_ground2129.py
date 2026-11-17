"""#2129: a GUEST body (a body of one tile's placement written as an
on-ground row of the neighbour tile's DSF, #1884) is seated on the ground
that tile DRAWS — its built mesh — never on the airport's DEM when the
mesh is there; the guest record says which ground; a later build of that
tile re-seats a record seated on another ground; and the one solve's
piece for a tile that builds no patch of the airport is laid there.

EDDH (owner sim read 2026-11-17T02:36Z): 1,190 terminal bodies past 10°E
were cut against the airport DEM and drawn on the +53+010 mesh,
−11.7..+3.0 m off their plan; the +53+010 piece was never installed."""
from __future__ import annotations

import json
import types

import numpy as np
import pytest
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import tile_route as TR
from tests.auto_patch_v2.test_backup_state import _record_doc, _stand_in_dsftool
from tests.auto_patch_v2.test_tile_route1884 import B_, A, _routed, _two_tile_pack


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _dem(monkeypatch, z=428.0):
    asked = []

    def airport_ground(icao, here, root, feather_m=60.0):
        def g(lats, lons):
            asked.append(len(np.atleast_1d(lats)))
            return np.full(np.shape(lats), z)
        return g
    monkeypatch.setattr(TR, "airport_ground", airport_ground)
    return asked


def test_a_guest_reads_the_neighbours_built_mesh_and_says_so(monkeypatch):
    """RED ON BASE: the split read the airport DEM past the edge even where
    the neighbour's mesh was built — the body was cut 9.9 m off the ground
    X-Plane seats it on."""
    asked = _dem(monkeypatch)

    def mesh(lat, lon):
        return (437.9, False) if lat < 47.9 else None
    mesh.many = lambda las, los: [mesh(a, o) for a, o in zip(las, los, strict=True)]
    g = TR.neighbour_ground("LOWS", A, "/elev", meshes=lambda t: (
        (mesh, TR.mesh_mark("ab" * 32)) if t == B_ else None))
    z = g([47.79, 47.95, 46.5], [13.005, 13.005, 12.5])
    assert z.tolist() == [437.9, 428.0, 428.0]      # the mesh, else the DEM
    assert asked == [2]                              # only the uncovered points
    assert g.mark(B_) == "mesh:" + "ab" * 8
    assert g.mark((46, 12)) == TR.DEM_MARK


def test_no_mesh_anywhere_is_the_airport_dem_as_before(monkeypatch):
    _dem(monkeypatch, 412.0)
    g = TR.neighbour_ground("LOWS", A, "/elev")
    assert g([47.79], [13.005]).tolist() == [412.0]
    assert g.mark(B_) == TR.DEM_MARK

    def unreadable(_t):
        raise OSError("truncated mesh")
    g = TR.neighbour_ground("LOWS", A, "/elev", meshes=unreadable)
    assert g([47.79], [13.005]).tolist() == [412.0] and g.mark(B_) == TR.DEM_MARK


def test_the_guest_record_keeps_its_ground_and_the_neighbour_keeps_it(
        tmp_path, monkeypatch):
    """The mark rides the guest row (``write_pack``), survives the
    neighbour's own write (``_sibling_plans`` carries the row) and is read
    back by ``guest_mark``."""
    from auto_patch_v2.airport import placement_write as PW
    from tests.auto_patch_v2.test_tile_route1884 import _b_own, _lows_a
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    plan, files = _lows_a(pack, a)
    PW.apply_routed(plan, files, tool, here=A, work_dir=str(tmp_path / "wa"),
                    guest_ground=lambda t: "mesh:0123456789abcdef")
    row = _record_doc(b)["dsfs"]["+47+013.dsf"]["airports"]["LOWS@+47+012"]
    assert row["ground"] == "mesh:0123456789abcdef"
    _b_own(pack, b, tool, tmp_path)
    B.invalidate_memo()
    assert TR.guest_mark(str(pack), B_, "LOWS@+47+012") == "mesh:0123456789abcdef"
    assert TR.guest_mark(str(pack), B_, "KXYZ@+47+012") is None
    assert TR.guest_mark(str(pack), A, "LOWS@+47+013") is None


def test_a_record_before_2129_reads_as_the_dem(tmp_path, monkeypatch):
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    row = _record_doc(b)["dsfs"]["+47+013.dsf"]["airports"]["LOWS@+47+012"]
    assert "ground" not in row
    assert TR.guest_mark(str(pack), B_, "LOWS@+47+012") == TR.DEM_MARK


def test_the_later_build_of_the_guests_tile_reseats_them(tmp_path, monkeypatch):
    """``guest_stage.reseat_guests``: +47+013's build finds LOWS@+47+012
    seated on the DEM and runs +47+012's LOWS plan again (``only``); a
    record already on this mesh is left alone."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    from auto_patch import guest_stage as GS
    from auto_patch import object_stage as OS
    pack = tmp_path / "pack"
    patches = tmp_path / "Patches"
    monkeypatch.setattr(FNAMES, "Patch_dir", str(patches))
    origin = patches / "+40+010" / "+47+012"
    origin.mkdir(parents=True)
    (origin / "o4_v2_placement_LOWS.json").write_text(json.dumps(
        {"icao": "LOWS", "pack_root": str(pack)}), encoding="utf-8")
    mesh = tmp_path / "Data+47+013.mesh"
    mesh.write_bytes(b"mesh")
    marks = {"LOWS@+47+012": TR.DEM_MARK}
    monkeypatch.setattr(TR, "guest_mark", lambda root, there, key: (
        marks.get(key) if (root, tuple(there)) == (str(pack), B_) else None))
    ran = []
    monkeypatch.setattr(OS, "_object_stage", lambda t, only=None: (
        ran.append(((t.lat, t.lon), only)) or {"airports_failed": 0}))
    monkeypatch.setattr(CFG.Tile, "read_from_config", lambda self, *a, **k: None)
    tile = types.SimpleNamespace(lat=B_[0], lon=B_[1], custom_build_dir="")
    assert GS.reseat_guests(tile, str(mesh)) == {"guests_reseated": 1,
                                                 "guests_reseat_failed": 0}
    assert ran == [(A, frozenset({"LOWS"}))]
    marks["LOWS@+47+012"] = TR.mesh_mark(GS._mesh_digest(str(mesh)))
    ran.clear()
    assert GS.reseat_guests(tile, str(mesh)) == {} and ran == []


def test_the_piece_for_a_tile_that_builds_no_patch_is_laid_there(tmp_path, monkeypatch):
    """RED ON BASE: ``engine_v2`` placed the current tile's piece only."""
    import O4_File_Names as FNAMES
    from auto_patch import engine_v2 as EV
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    pieces = {}
    for t in ((53, 9), (53, 10), (54, 9)):
        p = tmp_path / f"{t[0]}_{t[1]}.osm"
        p.write_text(f"piece {t}", encoding="utf-8")
        s = tmp_path / f"{t[0]}_{t[1]}.axes.json"
        s.write_text("{}", encoding="utf-8")
        pieces[t] = types.SimpleNamespace(patch=p, sidecar=s)
    task = {"threshold_tiles": [(53, 9), (54, 9)]}
    assert EV._install_neighbour_pieces(task, "EDDH", pieces, (53, 9)) == ["+53+010"]
    laid = tmp_path / "Patches" / "+50+010" / "+53+010" / "EDDH_auto.patch.osm"
    assert laid.read_text(encoding="utf-8") == "piece (53, 10)"
    assert (laid.parent / "EDDH_auto.patch.osm.axes.json").is_file()
    assert not (tmp_path / "Patches" / "+50+000" / "+54+009").exists()
    # a task that does not name its threshold tiles lays nothing
    assert EV._install_neighbour_pieces({}, "EDDH", pieces, (53, 9)) == []


def test_the_neighbours_ground_is_its_mesh_else_its_built_dsf_else_the_dem(
        tmp_path, monkeypatch):
    """A pruned rebuild cache keeps the DSF X-Plane draws (LOWS +47+013 on
    the owner's install has no .mesh): the guest reads that DSF."""
    from auto_patch import guest_stage as GS
    tiles = tmp_path / "Tiles"
    tile = types.SimpleNamespace(lat=47, lon=12, custom_build_dir=str(tiles) + "/")
    nb = tiles / "zOrtho4XP_+47+013"
    assert GS._ground_mark(tile, B_) == TR.DEM_MARK
    dsf = nb / "Earth nav data" / "+40+010" / "+47+013.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"dsf")
    assert GS._ground_mark(tile, B_) == TR.mesh_mark(GS._mesh_digest(str(dsf)), "dsf")
    mesh = nb / "Data+47+013.mesh"
    mesh.write_bytes(b"mesh")
    assert GS._ground_mark(tile, B_) == TR.mesh_mark(GS._mesh_digest(str(mesh)))
    assert GS.neighbour_marks(tile, (12.9, 47.7, 13.1, 47.8)) == {
        "+47+013": TR.mesh_mark(GS._mesh_digest(str(mesh)))}
    assert GS.neighbour_marks(tile, (12.1, 47.7, 12.9, 47.8)) == {}
