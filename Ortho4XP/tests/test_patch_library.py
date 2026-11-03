"""Twins for the PATCH LIBRARY's airport entries (#1699 phase 2,
``src/patch_library``) against a FAKE library: a bare git repository
behind a fake GitHub (``tools/patch_library_fake.py``), read through
``file://``.  No network, no keychain, no corpus.

Two stand-in machines in ``tmp_path``: A publishes an airport of its
built tile (device sign-in, fork, branch, pull request, the library's
checks, merge, index rebuild); B, an empty data folder with the same
pack installed under another folder name, finds it on "app open",
lays it down, and the build's reuse gate skips the airport's solve.
Version 2 reads "newer"; a changed pack on B falls back to re-solve.
"""

import json
import lzma
import shutil
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE.parent / "tools"))

import O4_Cfg_Vars as CFGVARS  # noqa: E402
import O4_Config_Utils as CFG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402
import tile_bundle.export as TB_EXPORT  # noqa: E402
import tile_bundle.key as TB_KEY  # noqa: E402
from auto_patch import driver as DRIVER  # noqa: E402
from patch_library import LibraryRefused  # noqa: E402
from patch_library import apply as APPLY  # noqa: E402
from patch_library import checks as CHECKS  # noqa: E402
from patch_library import github as GITHUB  # noqa: E402
from patch_library import index as INDEX  # noqa: E402
from patch_library import key as KEY  # noqa: E402
from patch_library import layout as L  # noqa: E402
from patch_library import publish as PUBLISH  # noqa: E402
from patch_library import scan as SCAN  # noqa: E402

pytest.importorskip("patch_library_fake")
if shutil.which("git") is None:                      # pragma: no cover
    pytest.skip("the fake library needs git", allow_module_level=True)
from patch_library_fake import FakeGitHub  # noqa: E402

LAT, LON, ICAO = 45, -123, "KXXX"
TEMPLATE = HERE.parents[1] / "library_template"
BODY = b"  <node id='-1' lat='45.5' lon='-122.5'/>\n</osm>\n"



def _put(path, text):
    """Write ``text`` as UTF-8 with LF line ends (#92, #539)."""
    path.write_text(text, encoding="utf-8", newline="\n")


class _Tile:
    def __init__(self, build_dir):
        self.lat, self.lon, self.build_dir = LAT, LON, str(build_dir)
        self.custom_build_dir = ""
        for name in CFGVARS.list_tile_vars:
            setattr(self, name, CFGVARS.cfg_vars[name]["default"])


class _Machine:
    """One installation: an X-Plane folder with the pack, a data folder."""

    def __init__(self, root: Path, pack: str):
        self.root, self.pack = root, pack
        self.xp = root / "X-Plane"
        self.scenery = self.xp / "Custom Scenery"
        (self.scenery / pack / "Earth nav data").mkdir(parents=True)
        _put(self.scenery / pack / "Earth nav data" / "apt.dat", "1 0 0 0 KXXX\n")
        for name in ("data", "patches", "build", "insets"):
            (root / name).mkdir()
        self.tile = _Tile(root / "build")
        self.sig = {"pack": pack, "custom": True, "signature": "a" * 32}

    def live(self, mp):
        mp.setattr(FNAMES, "current_data_root", lambda: str(self.root / "data"))
        mp.setattr(FNAMES, "patch_dir", lambda lat, lon: str(self.root / "patches"))
        mp.setattr(FNAMES, "airport_inset_directory",
                   lambda lat, lon: str(self.root / "insets"))
        mp.setattr(CFG, "custom_scenery_dir", str(self.scenery))
        mp.setattr(TB_EXPORT, "load_tile", lambda *a, **k: self.tile)
        mp.setattr(TB_KEY, "xplane_root", lambda tile: str(self.xp))
        mp.setattr(KEY, "pack_now", lambda root, icao, lat, lon: dict(self.sig))
        mp.setattr(SCAN, "_candidates", lambda working_dir="": {ICAO: (LAT, LON)})
        return self

    @property
    def patches(self) -> Path:
        return self.root / "patches"

    def build(self, marker: str = "v1"):
        """What a finished build leaves for KXXX: the patch family."""
        apt = self.scenery / self.pack / "Earth nav data" / "apt.dat"
        inset = self.root / "insets" / "KXXX_usgs3dep.tif"
        inset.write_bytes(b"lidar")
        head = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6' "
                "o4_icao='KXXX' o4_apt_dat='%s' o4_apt_dat_mtime='1.0' "
                "o4_fresh_v='7' o4_cfg='c' o4_code='d' o4_ap_engine='v2' "
                "o4_solve_cfg='%s' o4_dem='insets:%s|5|1.0' o4_marker='%s'>\n" % (
                    urllib.parse.quote(str(apt), safe="/"), KEY.solve_now(self.tile),
                    urllib.parse.quote(str(inset), safe=""), marker))
        (self.patches / "KXXX_auto.patch.osm").write_bytes(head.encode() + BODY)
        _put(self.patches / "KXXX_auto.patch.osm.axes.json",
             json.dumps({"road_bridge_decks": [], "marker": marker}))
        _put(self.patches / "KXXX.graded.json", json.dumps({"faces": []}))
        _put(self.patches / "o4_v2_rebake_KXXX.json", json.dumps({
            "pack_root": str(self.scenery / self.pack),
            "objects": [str(self.scenery / self.pack / "objects" / "a.obj")]}))
        _put(self.patches / "o4_v2_rebake_KXXX.screen.refused", "local")


@pytest.fixture
def world(tmp_path, monkeypatch):
    template = tmp_path / "template"
    shutil.copytree(TEMPLATE, template)
    _put(template / L.PUBLISHERS, json.dumps({"developers": [
        {"login": "dev", "packs": [{"pack": "Pack*", "airports": [ICAO]}]}],
        "reviewers": ["owner"]}))
    fake = FakeGitHub(str(tmp_path / "github"), str(template),
                      users={"tok-dev": "dev", "tok-pilot": "pilot"})
    for name, value in fake.environ().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(GITHUB, "TRANSPORT", fake.transport)
    tokens = {}
    monkeypatch.setattr(GITHUB, "stored_token", lambda: tokens.get("t"))
    monkeypatch.setattr(GITHUB, "store_token", lambda t: tokens.__setitem__("t", t))
    monkeypatch.setattr(DRIVER, "auto_patch_stale_inputs", lambda *a, **k: [])
    a = _Machine(tmp_path / "A", "PackA")
    b = _Machine(tmp_path / "B", "PackB (renamed)")
    a.live(monkeypatch).build()
    return {"fake": fake, "a": a, "b": b, "mp": monkeypatch, "tokens": tokens}


def _sign_in(world):
    start = GITHUB.device_start()
    assert start["user_code"] and start["verification_uri"]
    assert GITHUB.device_poll(start["device_code"])["status"] == "pending"
    done = GITHUB.device_poll(start["device_code"])
    assert done == {"status": "ok", "login": "dev"}


def _publish(world, kind="payware"):
    world["a"].live(world["mp"])
    out = PUBLISH.publish(LAT, LON, ICAO, kind=kind, accept=True)
    verdict = world["fake"].run_checks(out["number"])
    return out, verdict


def test_publish_find_apply_skips_the_solve(world):
    """The phase-2 gate's core path: publish on A, find on B's app open,
    lay it down, and the reuse gate skips B's solve."""
    _sign_in(world)
    out, verdict = _publish(world)
    assert verdict["ok"] and verdict["auto_merge"], verdict["problems"]
    assert out["auto_merge"] and out["version"] == 1
    world["fake"].merge(out["number"])
    b = world["b"].live(world["mp"])
    found = SCAN.check(force=True)
    assert [(r["icao"], r["state"], r["version"], r["solved_usable"], r["verified"])
            for r in found["rows"]] == [(ICAO, "available", 1, True, True)]
    done = APPLY.apply_entry(found["rows"][0]["entry"])
    assert done["mode"] == "solved" and done["files"] == 4
    patch = b.patches / "KXXX_auto.patch.osm"
    head = patch.read_text(encoding="utf-8").split("\n")[1]
    assert str(b.scenery / b.pack) in urllib.parse.unquote(head)      # B's own paths
    assert str(world["a"].root) not in patch.read_text(encoding="utf-8")
    assert patch.read_bytes().endswith(BODY)
    assert not (b.patches / "o4_v2_rebake_KXXX.screen.refused").exists()
    plan = json.loads((b.patches / "o4_v2_rebake_KXXX.json").read_text(encoding="utf-8"))
    assert plan["pack_root"] == str(b.scenery / b.pack)               # renamed pack
    assert DRIVER._auto_patch_is_current(str(patch), str(b.xp), ICAO, tile=b.tile)
    assert SCAN.check(force=True)["rows"] == []                       # current


def test_version_two_reads_newer(world):
    _sign_in(world)
    first, _v = _publish(world)
    world["fake"].merge(first["number"])
    world["b"].live(world["mp"])
    APPLY.apply_entry(SCAN.check(force=True)["rows"][0]["entry"])
    world["a"].build("v2")
    second, verdict = _publish(world)
    assert second["version"] == 2 and verdict["ok"], verdict["problems"]
    world["fake"].merge(second["number"])
    world["b"].live(world["mp"])
    rows = SCAN.check(force=True)["rows"]
    assert [(r["state"], r["version"], r["local_version"]) for r in rows] == [
        ("newer", 2, 1)]
    APPLY.apply_entry(rows[0]["entry"])
    patch = world["b"].patches / "KXXX_auto.patch.osm"
    assert "o4_marker='v2'" in patch.read_text(encoding="utf-8")


def test_a_changed_pack_falls_back_to_re_solve(world):
    _sign_in(world)
    out, _v = _publish(world)
    world["fake"].merge(out["number"])
    b = world["b"].live(world["mp"])
    entry = SCAN.check(force=True)["rows"][0]["entry"]
    APPLY.apply_entry(entry)
    patch = str(b.patches / "KXXX_auto.patch.osm")
    b.sig["signature"] = "b" * 32                  # the developer updated the pack
    assert not DRIVER._auto_patch_is_current(patch, str(b.xp), ICAO, tile=b.tile)
    assert SCAN.check(force=True)["rows"][0]["state"] == "pack_changed"
    again = APPLY.apply_entry(entry)
    assert again["mode"] == "re-solve" and "scenery pack" in again["reason"]
    assert not (b.patches / "o4_library_KXXX.json").exists()


def test_another_engine_law_re_solves(world, monkeypatch):
    _sign_in(world)
    out, _v = _publish(world)
    world["fake"].merge(out["number"])
    world["b"].live(world["mp"])
    law = KEY.law_now(None)
    monkeypatch.setattr(KEY, "law_now", lambda tile: dict(law, code="newer"))
    row = SCAN.check(force=True)["rows"][0]
    assert row["state"] == "available" and not row["solved_usable"]
    assert APPLY.apply_entry(row["entry"])["mode"] == "re-solve"


def test_community_payware_refused_freeware_goes_to_review(world):
    world["tokens"]["t"] = "tok-pilot"             # not a verified developer
    with pytest.raises(LibraryRefused, match="pack-relative"):
        _publish(world, kind="payware")
    out, verdict = _publish(world, kind="freeware")
    assert verdict["ok"] and not verdict["auto_merge"] and not out["auto_merge"]


def test_publish_needs_the_licence_and_a_sign_in(world):
    world["a"].live(world["mp"])
    with pytest.raises(LibraryRefused, match="licence"):
        PUBLISH.publish(LAT, LON, ICAO, kind="freeware")
    with pytest.raises(LibraryRefused, match="Sign in"):
        PUBLISH.publish(LAT, LON, ICAO, kind="freeware", accept=True)


def test_preview_shows_the_library_checks(world):
    _sign_in(world)
    world["a"].live(world["mp"])
    view = PUBLISH.preview(LAT, LON, ICAO, kind="payware")
    assert view["problems"] == [] and view["verified"] and view["version"] == 1
    names = [f["name"] for f in view["files"]]
    assert "solved/KXXX_auto.patch.osm.xz" in names
    assert not any("refused" in n for n in names)
    assert "OpenStreetMap" in view["attribution"]


def test_a_stale_patch_refuses_the_publish(world, monkeypatch):
    _sign_in(world)
    monkeypatch.setattr(DRIVER, "auto_patch_stale_inputs",
                        lambda *a, **k: [("o4_dem", 1, 2), ("o4_code", "x", "y")])
    with pytest.raises(LibraryRefused, match="o4_code"):
        _publish(world)


def test_users_own_edits_are_never_overwritten(world):
    a = world["a"]
    (a.patches / "KXXX_edited.patch.osm").write_bytes(b"<osm>edited on A</osm>\n")
    _sign_in(world)
    out, _v = _publish(world)
    world["fake"].merge(out["number"])
    b = world["b"].live(world["mp"])
    (b.patches / "KXXX_edited.patch.osm").write_bytes(b"<osm>mine</osm>\n")
    done = APPLY.apply_entry(SCAN.check(force=True)["rows"][0]["entry"])
    assert done["edits"] == "conflict"
    assert (b.patches / "KXXX_edited.patch.osm").read_bytes() == b"<osm>mine</osm>\n"


def _entry_folder(world, tmp_path):
    _sign_in(world)
    world["a"].live(world["mp"])
    entry = PUBLISH._package(LAT, LON, ICAO, "", "payware", "dev", "",
                             PUBLISH._client.licences())[1]
    root = tmp_path / "lib"
    shutil.copytree(TEMPLATE, root)
    _put(root / L.PUBLISHERS, json.dumps({"developers": [
        {"login": "dev", "packs": [{"pack": "Pack*"}]}]}))
    import patch_library.entry as ENTRY
    return root, entry, Path(ENTRY.write_folder(str(root), entry))


def test_checks_refuse_a_local_path_a_bad_hash_and_a_skipped_version(world, tmp_path):
    root, entry, folder = _entry_folder(world, tmp_path)
    pubs = json.loads((root / L.PUBLISHERS).read_text(encoding="utf-8"))
    lic = json.loads((root / L.LICENCES).read_text(encoding="utf-8"))
    assert CHECKS.check_entry(str(root), entry["rel"], publishers=pubs,
                              licences=lic)["problems"] == []
    graded = folder / "solved" / "KXXX.graded.json.xz"
    graded.write_bytes(lzma.compress(b'{"from": "/Users/someone/pack"}'))
    problems = CHECKS.check_entry(str(root), entry["rel"], publishers=pubs,
                                  licences=lic)["problems"]
    assert any("hash" in p for p in problems)
    meta = json.loads((folder / L.MANIFEST).read_text(encoding="utf-8"))
    data = graded.read_bytes()
    import hashlib
    raw = lzma.decompress(data)
    meta["files"]["solved/KXXX.graded.json.xz"].update(
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        raw_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw))
    _put(folder / L.MANIFEST, json.dumps(meta))
    problems = CHECKS.check_entry(str(root), entry["rel"], publishers=pubs,
                                  licences=lic)["problems"]
    assert problems == ["solved/KXXX.graded.json.xz holds a local path (/Users/s)"]
    v3 = folder.parent / "v3"
    shutil.copytree(folder, v3)
    meta["version"] = 3
    _put(v3 / L.MANIFEST, json.dumps(meta))
    rel3 = entry["rel"].rsplit("/", 1)[0] + "/v3"
    assert any("before version 2" in p for p in CHECKS.check_entry(
        str(root), rel3, publishers=pubs, licences=lic)["problems"])


def test_per_source_terms_mark_a_noncommercial_entry_and_refuse_a_held_one(world, tmp_path):
    """Owner Q319: an open entry is ODbL 1.0 and credits each source's
    terms; a non-commercial source publishes and marks the whole entry
    non-commercial; a held source refuses it; the mark is re-derived."""
    from patch_library import LICENCE, LICENCE_NC
    from patch_library import terms as TERMS
    root, entry, folder = _entry_folder(world, tmp_path)
    lic = json.loads((root / L.LICENCES).read_text(encoding="utf-8"))
    meta = entry["manifest"]
    assert meta["licence"] == LICENCE and meta["noncommercial"] is False
    usgs = next(s for s in meta["sources"] if s["provider"] == "USGS3DEP")
    assert usgs["terms"].startswith("https://") and not usgs["noncommercial"]
    assert "terms: https://" in entry["files"][L.ATTRIBUTION].decode("utf-8")

    def verdict(sources, licence, noncommercial):
        _put(folder / L.MANIFEST, json.dumps(dict(
            meta, sources=sources, licence=licence, noncommercial=noncommercial)))
        pubs = json.loads((root / L.PUBLISHERS).read_text(encoding="utf-8"))
        return CHECKS.check_entry(str(root), entry["rel"], publishers=pubs,
                                  licences=lic)["problems"]

    nc = TERMS.annotate(meta["sources"] + [{"kind": "elevation",
                                            "provider": "VIEWFINDER1",
                                            "licence": "x"}], lic)
    assert nc[-1]["noncommercial"] and TERMS.entry_licence(nc) == LICENCE_NC
    assert verdict(nc, LICENCE_NC, True) == []
    assert any("non-commercial mark" in p for p in verdict(nc, LICENCE_NC, False))
    assert any("published under %s" % LICENCE_NC in p for p in verdict(nc, LICENCE, False))
    held = meta["sources"] + [{"provider": "NORTHERNIRELAND1M", "licence": "x"}]
    assert any("NORTHERNIRELAND1M is held" in p for p in verdict(held, LICENCE, False))
    for name in TERMS.CLASSES:
        for code, row in lic[name].items():
            assert set(row) >= {"licence", "attribution", "terms", "evidence",
                                "summary"}, code


def test_a_published_version_never_changes(world, tmp_path):
    root, entry, folder = _entry_folder(world, tmp_path)
    verdict = CHECKS.check_pull(str(root), str(root), [entry["rel"] + "/manifest.json"],
                                "dev")
    assert not verdict["ok"] and "already published" in verdict["problems"][0]
    verdict = CHECKS.check_pull(str(root), str(tmp_path), ["README.md"], "dev")
    assert not verdict["ok"] and "outside entries/" in verdict["problems"][0]


def test_the_index_lists_verified_developers_first(tmp_path):
    root = tmp_path / "lib"
    for login, sig, when in (("pilot", "1" * 32, "2026-11-02"), ("dev", "2" * 32, "2026-11-01")):
        rel = L.entry_dir(ICAO, "PackA", sig, 1)
        (root / rel).mkdir(parents=True)
        _put(root / rel / L.MANIFEST, json.dumps({
            "icao": ICAO, "tile": "+45-123", "version": 1, "signature": sig,
            "pack": {"name": "PackA", "custom": True, "kind": "freeware"},
            "law": {}, "solve": "", "min_engine": "1", "publisher": login,
            "published": when}))
    _put(root / L.PUBLISHERS, json.dumps({"developers": [
        {"login": "dev", "packs": [{"pack": "Pack*"}]}]}))
    assert INDEX.rebuild(str(root)) == ["index/+40-130.json"]
    doc = json.loads((root / "index" / "+40-130.json").read_text(encoding="utf-8"))
    assert [r["publisher"] for r in doc["airports"][ICAO]] == ["dev", "pilot"]


def test_the_library_side_imports_nothing_of_the_engine():
    """checks / index / layout run in the library's Actions from a sparse
    checkout of ``patch_library`` alone."""
    import ast
    src = HERE.parent / "src" / "patch_library"
    for name in ("__init__.py", "layout.py", "checks.py", "index.py"):
        tree = ast.parse((src / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in sys.stdlib_module_names, (name, node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in sys.stdlib_module_names, (name, alias.name)


def test_road_level_is_matched_not_refused():
    """Owner Q315: a tile bundle's key carries ``road_level``; a non-default
    value is matched, never a reason to refuse the export."""
    profile = {"road_level": repr("1"), "curvature_tol": repr(
        CFGVARS.cfg_vars["curvature_tol"]["default"])}
    assert TB_KEY.profile_deviations(profile) == []
    other = dict(profile, road_level=repr("3"))
    assert TB_KEY._digest(profile) != TB_KEY._digest(other)


def test_an_unset_library_is_not_set_up(monkeypatch):
    for name in ("XPTB_LIBRARY_REPO", "XPTB_LIBRARY_RAW", "XPTB_LIBRARY_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)
    from patch_library import config
    monkeypatch.setattr(config, "REPO", "")
    monkeypatch.setattr(config, "CLIENT_ID", "")
    assert not config.configured()
    assert SCAN.check() == {"configured": False, "rows": [], "regions": [], "checked": ""}


def test_apply_never_trusts_an_entry_member_name(world, tmp_path):
    """A manifest naming a file outside the patch family (a path, another
    airport's file) refuses the apply before anything is written."""
    manifest = {"icao": ICAO}
    for bad in ("solved/../../evil.osm.xz", "solved/KYYY.graded.json.xz",
                "solved/notes.txt.xz", "edits/KXXX.graded.json.xz"):
        with pytest.raises(LibraryRefused, match="no entry may carry"):
            APPLY._member(manifest, bad, bad.split("/")[0],
                          L.SOLVED_NAME_RE if bad.startswith("solved") else L.EDITED_NAME_RE)
    assert APPLY._member(manifest, "solved/o4_v2_rebake_KXXX~1.json.xz", L.SOLVED,
                         L.SOLVED_NAME_RE) == "o4_v2_rebake_KXXX~1.json"
    assert L.parse_entry_dir("entries/KXXX/../0123456789ab/v1") is None
