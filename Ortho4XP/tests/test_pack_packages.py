"""Twins for DEVELOPER PACKAGES and PACK-SHIPPED ``.xptb`` (RULINGS
2026-11-11m (3)–(5); ``tile_bundle.pack_dev`` / ``pack_apply`` /
``pack_shipped``).

Headless, on ``tmp_path`` only (the two stand-in machines of
``test_tile_package``): a pack's "objects are final" stands the object
stage down for it; "apply into my pack" moves the stage's kept originals
into the pack's backup folder and marks it applied; Export saves into the
pack's own folder; a package a pack ships is applied when a tile builds,
with a notice; a changed one marks the tile stale; a pack that no longer
matches falls back (once); the user's own patch keeps precedence.
"""

import json
import os
import shutil
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from auto_patch_v2.airport import pack_identity as PIDENT  # noqa: E402
from o4_engine import xplane_root as XROOT  # noqa: E402
from test_tile_package import (  # noqa: E402,F401  (the fixture is used by name)
    LAT,
    LON,
    PATCHES,
    _patch,
    _Tile,
    machines,
)
from tile_bundle import BundleRefused  # noqa: E402
from tile_bundle import install as INSTALL  # noqa: E402
from tile_bundle import key as KEY  # noqa: E402
from tile_bundle import pack_apply as APPLY  # noqa: E402
from tile_bundle import pack_dev as DEV  # noqa: E402
from tile_bundle import pack_shipped as SHIPPED  # noqa: E402
from tile_bundle import package as PACKAGE  # noqa: E402

SIGNATURES = {"HECA": "s1", "HEAZ": "s2"}
DSF = "Earth nav data/+30+030/+30+031.dsf"


def _pack(m) -> str:
    return str(m.scenery / "PackA")


@pytest.fixture
def signed(machines, monkeypatch):  # noqa: F811
    """Both machines have an X-Plane root, PackA serves HECA, and the pack
    signatures are ``SIGNATURES`` until a test changes them."""
    a, b = machines
    sig = dict(SIGNATURES)
    def root(tile):
        return os.path.dirname(os.path.dirname(tile.build_dir))

    def signature(root, icao, lat, lon):
        return {"pack": "PackA", "custom": True, "signature": sig.get(icao, "")}

    # ``pack_dev`` reads both past ``key`` (the object stage's code key)
    for mod, name, fake in ((KEY, "xplane_root", root), (XROOT, "xplane_root_of", root),
                            (KEY, "pack_signature", signature),
                            (PIDENT, "pack_signature", signature)):
        monkeypatch.setattr(mod, name, fake)
    monkeypatch.setattr(KEY, "pack_root", lambda tile, icao: os.path.join(
        os.path.dirname(os.path.dirname(tile.build_dir)), "Custom Scenery", "PackA")
        if icao == "HECA" else "")
    for m in (a, b):
        (m.scenery / "PackA" / "Earth nav data").mkdir(parents=True, exist_ok=True)
    return a, b, sig


def _modified_pack(m) -> str:
    """PackA as the object stage leaves it: a rewritten DSF and object with
    their kept originals, a split body and the write records."""
    root = m.scenery / "PackA"
    for rel, data in ((DSF, b"rewritten dsf"), (DSF + ".anchor_bak", b"original dsf"),
                      ("objects/hangar.obj", b"rewritten obj"),
                      ("objects/hangar.obj.anchor_bak", b"original obj"),
                      ("objects/hangar__b1.obj", b"split body"),
                      ("Earth nav data/+30+030/o4_placement_provenance.json", b"{}"),
                      (".o4_reanchor_provenance.json", b"{}")):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return str(root)


# ── (3) the developer's choice, honoured by the object stage ─────────────

def _stage(tmp_path, monkeypatch, pack_root):
    """The object stage over one plan for ``pack_root``, everything below
    the gate stubbed: returns (counts, the stages that ran)."""
    from auto_patch import adjust_stage as AS
    from auto_patch import object_stage as OS
    from auto_patch import post_mesh as PM
    from auto_patch import selection as SEL
    from auto_patch_v2.law import Law
    from auto_patch_v2.model import rebake as RB
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir(exist_ok=True)
    (patch_dir / "o4_v2_rebake_ZZZZ.json").write_text("{}", encoding="utf-8", newline="\n")
    build = tmp_path / "build"
    mesh = build / "Data+30+031.mesh"
    mesh.parent.mkdir(exist_ok=True)
    mesh.write_bytes(b"mesh")
    ran = []
    monkeypatch.setattr(OS, "restore_unpatched_packs", lambda tile: {
        "restored": 0, "recomposed": 0})
    monkeypatch.setattr(OS, "restore_stopped_build", lambda *a: None, raising=False)
    monkeypatch.setattr(PM, "object_anchor_worklist_path",
                        lambda tile: str(patch_dir / "w.json"))
    monkeypatch.setattr(PM, "_mesh_is_newer_than_alt", lambda tile, path: True)
    monkeypatch.setattr(OS.__dict__["os"].path, "isfile",
                        lambda p, _f=os.path.isfile: True if p.endswith(".mesh") else _f(p))
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "mesh_file", lambda *a: str(mesh))
    monkeypatch.setattr(SEL, "auto_patch_not_applied", lambda *a, **k: "")
    monkeypatch.setattr(SEL, "manual_patch_files_for", lambda *a: [])
    monkeypatch.setattr(Law, "for_airport", classmethod(lambda cls, icao: None))
    monkeypatch.setattr(RB.RebakePlan, "from_json", staticmethod(
        lambda text: types.SimpleNamespace(icao="ZZZZ", pack_root=pack_root,
                                           units=[1], skipped=[])))
    monkeypatch.setattr(OS, "_art_stage", lambda *a, **k: ran.append("art"))
    monkeypatch.setattr(AS, "adjust_stage", lambda *a, **k: ran.append("adjust"))
    monkeypatch.setattr(AS, "tile_stage", lambda *a, **k: None)
    tile = types.SimpleNamespace(lat=LAT, lon=LON, build_dir=str(build),
                                 modify_custom_airports=True)
    return OS.rebake_after_mesh(tile), ran


def test_objects_final_stands_the_object_stage_down_for_that_pack(
        tmp_path, monkeypatch):
    pack = tmp_path / "Custom Scenery" / "PackA"
    pack.mkdir(parents=True)
    DEV.set_objects(str(pack), DEV.FINAL)
    counts, ran = _stage(tmp_path, monkeypatch, str(pack))
    assert counts["airports_objects_final"] == 1 and ran == []
    DEV.set_objects(str(pack), "")
    counts, ran = _stage(tmp_path, monkeypatch, str(pack))
    assert "airports_objects_final" not in counts and ran[0] == "art"
    assert DEV.read(str(pack))["objects"] == ""


def test_apply_into_pack_moves_the_kept_originals_and_marks_it(signed):
    a, _b, _sig = signed
    a.live()
    root = _modified_pack(a)
    with pytest.raises(BundleRefused, match="not served"):
        APPLY.developer("HEAZ", [(LAT, LON)])
    before = APPLY.developer("HECA", [(LAT, LON)])
    assert (before["objects"], before["modified"]) == ("", True)
    done = APPLY.developer("HECA", [(LAT, LON)], action="apply")
    assert (done["objects"], done["moved"], done["modified"]) == ("applied", 4, False)
    backup = os.path.join(root, DEV.read(root)["applied"]["backup"])
    assert open(os.path.join(backup, DSF + ".anchor_bak"), "rb").read() == b"original dsf"
    assert open(os.path.join(root, DSF), "rb").read() == b"rewritten dsf"
    assert os.path.isfile(os.path.join(root, "objects", "hangar__b1.obj"))
    assert APPLY.engine_files(root) == []
    tile = _Tile(LAT, LON, a.root)
    assert "already carries" in DEV.frozen_reason(tile, "HECA", root)
    with pytest.raises(BundleRefused, match="has not changed"):
        APPLY.developer("HECA", [(LAT, LON)], action="apply")


def test_objects_final_puts_the_originals_back_first(signed, monkeypatch):
    from auto_patch import object_rebake
    a, _b, _sig = signed
    a.live()
    root = _modified_pack(a)
    restored = []
    monkeypatch.setattr(object_rebake, "restore_detail",
                        lambda pack: restored.append(pack) or {"restored": 2})
    done = APPLY.developer("HECA", [(LAT, LON)], action="final")
    assert (done["objects"], done["restored"], restored) == ("final", 2, [root])
    assert APPLY.developer("HECA", [(LAT, LON)], action="default")["objects"] == ""


# ── Export into the pack's folder; the choice travels in the package ─────

def test_export_saves_into_the_airports_pack_and_records_its_objects(signed, tmp_path):
    a, b, _sig = signed
    a.live()
    DEV.set_objects(_pack(a), DEV.APPLIED)
    done = PACKAGE.save_package([(LAT, LON)], str(tmp_path / "ignored.xptb"),
                                airports=["HECA"], kind="patch", into_pack=True)
    assert done["path"] == DEV.package_path(_pack(a), "HECA")
    assert DEV.shipped_packages(_pack(a)) == [done["path"]]
    [entry] = INSTALL.read_manifest(done["path"])["tiles"]
    assert entry["airports"]["HECA"]["objects"] == "applied"
    with pytest.raises(BundleRefused, match="one airport"):
        PACKAGE.save_package([(LAT, LON)], "x", kind="tile", into_pack=True)
    b.live()
    INSTALL.install(done["path"])
    tile = _Tile(LAT, LON, b.root)
    assert "package installed for it" in DEV.frozen_reason(tile, "HECA", _pack(b))
    _sig = signed[2]
    _sig["HECA"] = "updated pack"                       # not that pack any more
    assert DEV.frozen_reason(tile, "HECA", _pack(b)) == ""


# ── (4) a pack's shipped package, applied on build with a notice ────────

def _ship(a, b, tmp_path, **fields) -> str:
    """A saves HECA's patch package into its pack; B installs the pack."""
    a.live()
    path = PACKAGE.save_package([(LAT, LON)], "", airports=["HECA"], kind="patch",
                                into_pack=True, **fields)["path"]
    dest = DEV.package_path(_pack(b), "HECA")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(path, dest)
    b.live()
    return dest


def _apply(b):
    said = []
    notices = SHIPPED.apply_for_tile(_Tile(LAT, LON, b.root), str(b.scenery),
                                     say=lambda _v, text: said.append(text))
    return notices, said


def test_a_shipped_package_is_applied_on_build_with_a_notice(signed, tmp_path, monkeypatch):
    a, b, _sig = signed
    _ship(a, b, tmp_path)
    [notice], said = _apply(b)
    assert (notice["state"], notice["icao"], notice["pack"]) == ("applied", "HECA", "PackA")
    assert notice["text"] == "Using PackA's XPTerrainBuilder data for HECA"
    assert said == ["  [pack package] " + notice["text"]]
    assert (b.root / PATCHES / "HECA_edited.patch.osm").read_bytes() == _patch(b)
    registry = json.loads((b.root / PATCHES / INSTALL.REGISTRY).read_text(encoding="utf-8"))
    assert registry["HECA"]["source"] == "pack:PackA"
    monkeypatch.setattr(INSTALL, "install", lambda *a, **k: pytest.fail("installed again"))
    [again], _said = _apply(b)                         # unchanged: noticed, not reinstalled
    assert again["state"] == "applied"


def test_the_build_posts_the_notice_as_an_event(monkeypatch):
    from o4_engine import events as EV
    from o4_engine import parallel
    from o4_engine.session import EngineSession
    row = {"pack": "PackA", "pack_root": "/p", "path": "/p/XPTerrainBuilder/HECA.xptb",
           "icao": "HECA", "state": "applied", "text": "Using PackA's …", "lat": 30, "lon": 31}
    monkeypatch.setattr(SHIPPED, "apply_for_tile", lambda tile: [row])
    session, got = EngineSession(), []
    session.subscribe(got.append)
    session._apply_pack_packages(types.SimpleNamespace(lat=30, lon=31))
    [event] = [e for e in got if isinstance(e, EV.PackPackage)]
    assert {k: getattr(event, k) for k in row} == row
    assert "PackPackage" in parallel._FORWARDED_EVENT_TYPES
    assert "pack_packages" in EV.CAPABILITIES


def test_a_changed_package_marks_the_tile_stale_and_the_next_build_applies_it(
        signed, tmp_path):
    from o4_engine import flight_manager as FM
    a, b, _sig = signed
    _ship(a, b, tmp_path)
    assert SHIPPED.stale_tiles(str(b.scenery)) == {(LAT, LON)}  # built before it shipped
    _apply(b)
    assert SHIPPED.stale_tiles(str(b.scenery)) == set()
    a.write(PATCHES + "HECA_edited.patch.osm", _patch(a, b"<way id='2'/>\n</osm>\n"),
            1_700_000_200_000_000_000)
    _ship(a, b, tmp_path, title="update")              # the developer's update
    [row] = SHIPPED.stale_rows(LAT, LON, SHIPPED.scan(str(b.scenery)))
    assert (row["reason"], row["icao"]) == ("package", "HECA")
    assert SHIPPED.stale_tiles(str(b.scenery), [(LAT, LON), (1, 2)]) == {(LAT, LON)}
    assert FM._job_for("destination", "stale", "drape") == ("full", "queued")
    assert FM._job_for("enroute", "stale", "drape") == ("full", "swapped")
    [notice], _said = _apply(b)                        # replaced without a question
    assert notice["state"] == "applied"
    assert (b.root / PATCHES / "HECA_edited.patch.osm").read_bytes() == _patch(
        b, b"<way id='2'/>\n</osm>\n")
    assert SHIPPED.stale_tiles(str(b.scenery)) == set()


def test_a_pack_that_no_longer_matches_falls_back_once(signed, tmp_path):
    a, b, sig = signed
    _ship(a, b, tmp_path)
    _apply(b)
    sig["HECA"] = "the developer changed the pack"
    [notice], said = _apply(b)
    assert notice["state"] == "fallback" and "built as usual" in notice["text"]
    assert not (b.root / PATCHES / "HECA_edited.patch.osm").exists()
    assert (b.root / PATCHES / "HECA_edited.patch.osm.disabled").is_file()
    assert _apply(b)[0] == []                          # noticed once
    assert "built as usual" in _apply(b)[1][0]         # logged every build
    assert SHIPPED.stale_tiles(str(b.scenery)) == set()


# ── (5) precedence: the user's patch > the pack's package > auto ────────

def test_the_users_own_patch_keeps_precedence(signed, tmp_path):
    a, b, _sig = signed
    path = _ship(a, b, tmp_path)
    auto = b.write(PATCHES + "HECA_auto.patch.osm", b"auto")
    mine = b.write(PATCHES + "HECA_edited.patch.osm", b"my newer edit",
                   1_800_000_000_000_000_000)
    [notice], _said = _apply(b)                        # theirs is older: kept silently
    assert notice["state"] == "applied" and mine.read_bytes() == b"my newer edit"
    os.utime(mine, ns=(1_600_000_000_000_000_000,) * 2)
    os.utime(path, None)                               # a new file of the pack
    with open(path, "ab") as handle:                   # (a new hash)
        handle.write(b"")
    SHIPPED._write_record(LAT, LON, {})
    notices, _said = _apply(b)
    assert [n["state"] for n in notices] == ["applied", "conflict"]
    assert notices[1]["path"] == path and mine.read_bytes() == b"my newer edit"
    assert [n["state"] for n in _apply(b)[0]] == ["applied"]   # asked once
    assert auto.read_bytes() == b"auto"
