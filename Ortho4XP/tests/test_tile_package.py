"""Twins for PACKAGES (#2014, ``src/tile_bundle`` ``inputs`` / ``package``
/ ``install`` / ``merge``).

Headless: two stand-in "machines" in ``tmp_path``, each with its own OSM,
elevation and patch folders and Custom Scenery; no pipeline, no network.
A package saved on A and installed on B must leave B's data identical to
A's (times included), carry no local path, auto patch, mosaic or lock,
refuse damage and an incompatible key, combine with a second package for
the same tile, and settle a patch both hold by the owner's rules.
"""

import io
import json
import os
import sys
import tarfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Config_Utils as CFG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Version  # noqa: E402
import pytest  # noqa: E402
from tile_bundle import BundleRefused  # noqa: E402
from tile_bundle import estimate as ESTIMATE  # noqa: E402
from tile_bundle import export as EXPORT  # noqa: E402
from tile_bundle import install as INSTALL  # noqa: E402
from tile_bundle import key as KEY  # noqa: E402
from tile_bundle import kinds as KINDS  # noqa: E402
from tile_bundle import merge as MERGE  # noqa: E402
from tile_bundle import package as PACKAGE  # noqa: E402
from tile_bundle import recipient_time as RTIME  # noqa: E402

LAT, LON = 30, 31
SCHEMAS = {"osm:airports": "", "osm:big_roads": "2026-09-15", "insets": "2026-07-30"}
AIRPORTS = {"HECA": {"pack": "PackA", "custom": True, "signature": "s1"},
            "HEAZ": {"pack": "", "custom": False, "signature": "s2"}}


class _Tile:
    def __init__(self, lat, lon, root):
        self.lat, self.lon = lat, lon
        self.build_dir = str(root / "Tiles" / FNAMES.tile_dir(lat, lon))
        self.custom_build_dir = ""
        self.base_elevation_source = "auto"


class _Machine:
    def __init__(self, root, monkeypatch):
        self.root, self.mp = root, monkeypatch
        self.scenery = root / "Custom Scenery"
        (self.scenery / "PackA").mkdir(parents=True)

    def live(self):
        root, mp = self.root, self.mp
        mp.setattr(FNAMES, "OSM_dir", str(root / "OSM_data"))
        mp.setattr(FNAMES, "Elevation_dir", str(root / "Elevation_data"))
        mp.setattr(FNAMES, "Patch_dir", str(root / "Patches"))
        mp.setattr(CFG, "custom_scenery_dir", str(self.scenery))
        tile = lambda lat, lon, *_a, **_k: _Tile(lat, lon, root)  # noqa: E731
        mp.setattr(EXPORT, "load_tile", tile)
        mp.setattr(INSTALL, "load_tile", tile)
        return self

    def write(self, rel, data, mtime=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if mtime is not None:
            os.utime(path, ns=(mtime, mtime))
        return path


def _patch(machine, body=b"<way id='1'/>\n</osm>\n") -> bytes:
    apt = urllib_quote(str(machine.scenery / "PackA" / "Earth nav data" / "apt.dat"))
    return ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6' "
            "o4_apt_dat='%s'>\n" % apt).encode("utf-8") + body


def urllib_quote(text):
    import urllib.parse
    return urllib.parse.quote(text, safe="/")


PATCHES = "Patches/+30+030/+30+031/"
INSETS = "Elevation_data/+30+030/N30E031_airport_insets/"


def _data_on(m, lat=LAT, lon=LON):
    """What builds of tile (lat, lon) leave in A's caches."""
    key = FNAMES.short_latlon(lat, lon)
    stem = FNAMES.hem_latlon(lat, lon)
    block = "Elevation_data/%s/" % FNAMES.round_latlon(lat, lon)
    osm = "OSM_data/%s/" % FNAMES.long_latlon(lat, lon).replace(os.sep, "/")
    m.write(osm + key + "_airports.osm.bz2", b"airports " + key.encode(), 1_700_000_000_123_456_789)
    m.write(osm + key + "_big_roads.osm.bz2", b"roads " + key.encode())
    m.write(osm + key + "_big_roads.osm.bz2.lock", b"")
    m.write(block + stem + ".hgt", b"base " + key.encode())
    m.write(block + stem + "_approach_rings/cell_01_00_cop_30m.tif", b"ring")
    m.write(block + stem + "_approach_rings/index.json", b'{"cells": {}}')
    m.write(block + stem + "_bathymetry_band/band_gebco.vrt", b"<VRTDataset/>")
    m.write("Elevation_data/+30+030/N30E030.hgt", b"west neighbour")
    m.write("Elevation_data/+30+030/N30E030_airport_insets/X_cop.tif", b"not ours")
    m.write("OSM_data/_airport_road_feed/HECA_road_feed.cache", b"\x80\x05pickle")


def _airport_data(m):
    m.write(INSETS + "HECA_copernicusglo30.tif", b"heca inset")
    m.write(INSETS + "HECA_copernicusglo30.json", b'{"provider": "COPERNICUSGLO30"}')
    m.write(INSETS + "HEAZ_copernicusglo30.tif", b"heaz inset")
    m.write(INSETS + "index.json", json.dumps(
        {"HECA": {"COPERNICUSGLO30": "ok"}, "HEAZ": {"COPERNICUSGLO30": "ok"}}).encode())
    m.write(INSETS + "complete.json", b'{"insets": []}')
    m.write(PATCHES + "HECA_edited.patch.osm", _patch(m), 1_700_000_100_000_000_000)
    m.write(PATCHES + "HECA_edited.patch.osm.axes.json", b"{}")
    m.write(PATCHES + "HEAZ_edited.patch.osm", _patch(m, b"<way id='9'/>\n</osm>\n"))
    m.write(PATCHES + "HECA_auto.patch.osm", _patch(m))


@pytest.fixture
def machines(tmp_path, monkeypatch):
    from patch_library import client as LIBCLIENT
    from patch_library import terms as TERMS
    monkeypatch.setattr(LIBCLIENT, "licences", lambda: TERMS.DEFAULT_LICENCES)
    monkeypatch.setattr(PACKAGE, "_schemas", lambda tile: dict(SCHEMAS))
    monkeypatch.setattr(KEY, "xplane_root", lambda tile: None)
    monkeypatch.setattr(KEY, "airport_signatures", lambda tile: dict(AIRPORTS))
    monkeypatch.setattr(INSTALL, "_downloads_left", lambda tile: [])
    monkeypatch.setattr(ESTIMATE, "_processing", lambda lat, lon: [
        RTIME._row("airports", "2 airports", 600.0, 500.0, 700.0)])
    monkeypatch.setattr(RTIME, "grid_rate", lambda: 10.0)
    monkeypatch.setattr(O4_Version, "version", "1.50.1900", raising=False)
    a = _Machine(tmp_path / "A", monkeypatch).live()
    b = _Machine(tmp_path / "B", monkeypatch)
    _data_on(a)
    _airport_data(a)
    return a, b


def _save(a, tmp_path, name, **kw):
    a.live()
    return PACKAGE.save_package([(LAT, LON)], str(tmp_path / name), **kw)["path"]


def _members(path) -> dict:
    with tarfile.open(path, "r:*") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}


def test_round_trip_lays_down_a_identical_data_with_its_times(machines, tmp_path):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb", title="Cairo", creator="Dev")
    names = set(_members(path))
    assert "data/OSM_data/+30+030/+30+031/+30+031_airports.osm.bz2" in names
    assert "data/Elevation_data/+30+030/N30E030.hgt" in names       # neighbour base
    assert "patches/+30+031/HECA_edited.patch.osm.axes.json" in names
    assert not [n for n in names if n.endswith((".lock", ".vrt", ".cache"))
                or "_auto.patch" in n or "N30E030_airport_insets" in n]
    for name, data in _members(path).items():
        assert str(a.root).encode() not in data, name
    b.live()
    done = INSTALL.install(path)
    assert done["downloads_left"] == {"+30+031": []}
    for rel in ("OSM_data/+30+030/+30+031/+30+031_airports.osm.bz2",
                INSETS + "complete.json", "Elevation_data/+30+030/N30E030.hgt"):
        assert (b.root / rel).read_bytes() == (a.root / rel).read_bytes(), rel
        assert os.stat(b.root / rel).st_mtime_ns == os.stat(a.root / rel).st_mtime_ns
    assert (b.root / PATCHES / "HECA_edited.patch.osm").read_bytes() == _patch(b)
    assert INSTALL.plan(path)["counts"] == {"same": done["files"]}


def test_plan_shows_tiles_airports_sources_and_branding(machines, tmp_path):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb", title="Cairo", creator="Dev", notes="n")
    b.live()
    details = INSTALL.plan(path)
    assert (details["title"], details["creator"], details["format"]) == (
        "Cairo", "Dev", "xptb-2")
    assert [r["icao"] for r in details["tiles"][0]["airports"]] == ["HEAZ", "HECA"]
    assert any(s["provider"] == "OpenStreetMap" for s in details["sources"])
    assert details["summary"][-1].startswith("Imagery is not included")
    assert not (b.root / "OSM_data").exists()                   # plan writes nothing


def _restricted(monkeypatch):
    """A source the library holds (its terms do not allow sharing it)."""
    from patch_library import client as LIBCLIENT
    from patch_library import terms as TERMS
    held = dict(TERMS.DEFAULT_LICENCES, held={"SWISSALTI3D": {
        "licence": "swisstopo free geodata terms", "summary": "no redistribution"}})
    monkeypatch.setattr(LIBCLIENT, "licences", lambda: held)
    plain = EXPORT.sources
    monkeypatch.setattr(EXPORT, "sources", lambda tile, icao="": plain(tile, icao) + [
        {"kind": "elevation", "provider": "SWISSALTI3D",
         "licence": "swisstopo free geodata terms", "credit": ""}])


def test_an_unrestricted_package_has_no_warning(machines, tmp_path):
    a, _b = machines
    a.live()
    done = PACKAGE.save_package([(LAT, LON)], str(tmp_path / "open.xptb"))
    assert (done["personal"], done["warning"]) == (False, "")
    assert json.loads(_members(done["path"])["manifest.json"])["personal"] is False


def test_a_restricted_source_writes_a_personal_package_that_warns(machines, tmp_path,
                                                                 monkeypatch):
    """Owner 2026-11-12: a package of a tile built from a source whose
    terms do not allow sharing it is written (the user's own store, a
    backup) and marked personal; exporting it, and opening it, warn."""
    a, b = machines
    _restricted(monkeypatch)
    a.live()
    done = PACKAGE.save_package([(LAT, LON)], str(tmp_path / "swiss.xptb"))
    manifest = json.loads(_members(done["path"])["manifest.json"])
    assert manifest["personal"] is True and manifest["noncommercial"] is True
    assert [s["provider"] for s in manifest["sources"] if s.get("personal")] == [
        "SWISSALTI3D"]
    assert done["personal"] is True
    assert done["warning"].startswith("For personal, non-commercial use only")
    assert "SWISSALTI3D" in done["warning"]
    b.live()
    details = INSTALL.plan(done["path"])
    assert details["warning"] == done["warning"]
    assert done["warning"] in details["summary"]


def test_a_damaged_member_refuses_and_writes_nothing(machines, tmp_path):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb")
    members = _members(path)
    name = "data/Elevation_data/+30+030/N30E031.hgt"
    members[name] = b"tampered"
    damaged = tmp_path / "damaged.xptb"
    with tarfile.open(damaged, "w:xz") as tar:
        for member, data in members.items():
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    b.live()
    with pytest.raises(BundleRefused, match="damaged"):
        INSTALL.install(str(damaged))
    leftover = [p for p in b.root.rglob("*") if p.is_file()]
    assert leftover == []


def test_an_incompatible_key_refuses(machines, tmp_path, monkeypatch):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb")
    b.live()
    monkeypatch.setattr(PACKAGE, "_schemas", lambda tile: dict(SCHEMAS, **{
        "osm:big_roads": "2027-01-01"}))
    with pytest.raises(BundleRefused, match="osm:big_roads"):
        INSTALL.plan(path)


def test_a_region_package_carries_each_tile_once(machines, tmp_path):
    a, b = machines
    _data_on(a, 30, 32)
    path = PACKAGE.save_package([(30, 31), (30, 32)], str(tmp_path))["path"]
    assert os.path.basename(path) == "XPTerrainBuilder_+30+031_2tiles.xptb"
    manifest = INSTALL.read_manifest(path)
    assert [t["tile"] for t in manifest["tiles"]] == ["+30+031", "+30+032"]
    names = list(_members(path))
    assert names.count("data/Elevation_data/+30+030/N30E031.hgt") == 1
    b.live()
    INSTALL.install(path)
    assert (b.root / "OSM_data/+30+030/+30+032/+30+032_airports.osm.bz2").is_file()


def test_an_airport_package_carries_only_that_airport(machines, tmp_path):
    a, _b = machines
    path = _save(a, tmp_path, "heca.xptb", airports=["heca"])
    members = _members(path)
    manifest = json.loads(members["manifest.json"])
    assert manifest["airports_only"] == ["HECA"]
    assert list(manifest["tiles"][0]["airports"]) == ["HECA"]
    insets = [n for n in members if "_airport_insets/" in n]
    assert sorted(os.path.basename(n) for n in insets) == [
        "HECA_copernicusglo30.json", "HECA_copernicusglo30.tif", "index.json"]
    assert list(json.loads(members["data/" + INSETS + "index.json"])) == ["HECA"]
    assert not [n for n in members if "HEAZ" in n]
    assert "data/OSM_data/+30+030/+30+031/+30+031_big_roads.osm.bz2" in members
    with pytest.raises(BundleRefused, match="grades"):
        _save(a, tmp_path, "none.xptb", airports=["KXXX"])


def test_two_airport_packages_merge_on_one_tile(machines, tmp_path):
    a, b = machines
    heca = _save(a, tmp_path, "heca.xptb", airports=["HECA"])
    heaz = _save(a, tmp_path, "heaz.xptb", airports=["HEAZ"])
    b.live()
    INSTALL.install(heca)
    INSTALL.install(heaz)
    index = json.loads((b.root / INSETS / "index.json").read_text(encoding="utf-8"))
    assert sorted(index) == ["HEAZ", "HECA"]
    for name in ("HECA_copernicusglo30.tif", "HEAZ_copernicusglo30.tif"):
        assert (b.root / INSETS / name).is_file()
    assert (b.root / PATCHES / "HEAZ_edited.patch.osm").is_file()
    registry = json.loads((b.root / PATCHES / INSTALL.REGISTRY).read_text(encoding="utf-8"))
    assert sorted(registry) == ["HEAZ", "HECA"]


def _two_versions(a, tmp_path, monkeypatch, first, second):
    monkeypatch.setattr(O4_Version, "version", first, raising=False)
    one = _save(a, tmp_path, "one.xptb", title="One")
    a.write(PATCHES + "HECA_edited.patch.osm", _patch(a, b"<way id='2'/>\n</osm>\n"),
            1_700_000_200_000_000_000)
    monkeypatch.setattr(O4_Version, "version", second, raising=False)
    two = _save(a, tmp_path, "two.xptb", title="Two")
    return one, two


def test_the_newer_app_versions_patch_wins_between_packages(machines, tmp_path, monkeypatch):
    a, b = machines
    one, two = _two_versions(a, tmp_path, monkeypatch, "1.50.1900", "1.50.1901")
    b.live()
    INSTALL.install(one)
    first = (b.root / PATCHES / "HECA_edited.patch.osm").read_bytes()
    done = INSTALL.install(two)
    assert done["conflicts"] == []
    target = b.root / PATCHES / "HECA_edited.patch.osm"
    assert b"id='2'" in target.read_bytes()
    assert (b.root / PATCHES / "HECA_edited.patch.osm.disabled").read_bytes() == first
    assert INSTALL.install(one)["conflicts"] == []          # older: kept
    assert b"id='2'" in target.read_bytes()


def test_one_app_version_twice_asks_and_keeps_by_default(machines, tmp_path, monkeypatch):
    a, b = machines
    one, two = _two_versions(a, tmp_path, monkeypatch, "1.50.1900", "1.50.1900")
    b.live()
    INSTALL.install(one)
    target = b.root / PATCHES / "HECA_edited.patch.osm"
    kept = target.read_bytes()
    question = INSTALL.plan(two)["conflicts"]
    assert [(q["icao"], q["kind"], q["choice"]) for q in question] == [
        ("HECA", "package", "keep")]
    INSTALL.install(two)
    assert target.read_bytes() == kept
    INSTALL.install(two, choices={"HECA": "replace"})
    assert b"id='2'" in target.read_bytes()


def test_a_newer_package_patch_than_the_users_asks(machines, tmp_path):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb")
    b.live()
    mine = b.write(PATCHES + "HECA_edited.patch.osm", b"my own edit", 1_600_000_000_000_000_000)
    details = INSTALL.plan(path)
    [question] = details["conflicts"]
    assert (question["kind"], question["choice"]) == ("custom", "keep")
    assert question["backup"].endswith("HECA_edited.patch.osm.disabled")
    assert any("backed up" in line or "kept unless" in line for line in details["summary"])
    INSTALL.install(path)                                      # default: keep mine
    assert mine.read_bytes() == b"my own edit"
    INSTALL.install(path, choices={"HECA": "replace"})
    assert mine.read_bytes() == _patch(b)
    assert (b.root / PATCHES / "HECA_edited.patch.osm.disabled").read_bytes() == b"my own edit"


def test_a_users_newer_patch_is_kept_without_a_question(machines, tmp_path):
    a, b = machines
    path = _save(a, tmp_path, "one.xptb")
    b.live()
    mine = b.write(PATCHES + "HECA_edited.patch.osm", b"my newer edit", 1_800_000_000_000_000_000)
    assert INSTALL.plan(path)["conflicts"] == []
    INSTALL.install(path, choices={"HECA": "replace"})
    assert mine.read_bytes() == b"my newer edit"


def test_packages_combine_into_one(machines, tmp_path):
    a, b = machines
    heca = _save(a, tmp_path, "heca.xptb", airports=["HECA"])
    heaz = _save(a, tmp_path, "heaz.xptb", airports=["HEAZ"])
    done = MERGE.merge_packages([heca, heaz], str(tmp_path / "both.xptb"), title="Both")
    manifest = INSTALL.read_manifest(done["path"])
    assert manifest["airports_only"] == ["HEAZ", "HECA"]
    assert sorted(manifest["tiles"][0]["airports"]) == ["HEAZ", "HECA"]
    b.live()
    INSTALL.install(done["path"])
    index = json.loads((b.root / INSETS / "index.json").read_text(encoding="utf-8"))
    assert sorted(index) == ["HEAZ", "HECA"]
    with pytest.raises(BundleRefused, match="two or more"):
        MERGE.merge_packages([heca], str(tmp_path))


def test_a_tile_bundle_still_reads(machines, tmp_path, monkeypatch):
    _a, b = machines
    parts = {"format": "xptb-1", "tile": "+30+031"}
    manifest = {"format": "xptb-1", "tile": "+30+031", "key": "k", "key_parts": parts,
                "airports": {"HECA": {"pack": "PackA"}}, "sources": [],
                "licence": "ODbL-1.0", "files": {}}
    path = tmp_path / "XPTerrainBuilder_+30+031.xptbundle"
    with tarfile.open(path, "w:xz") as tar:
        data = json.dumps(manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    b.live()
    monkeypatch.setattr(KEY, "key_parts", lambda tile: parts)
    details = INSTALL.plan(str(path))
    assert details["legacy"] and details["tiles"][0]["tile"] == "+30+031"
    from tile_bundle import importer
    monkeypatch.setattr(importer, "import_bundle", lambda p, c: {"tile": "+30+031",
                                                                  "reused": ["vector"]})
    assert INSTALL.install(str(path))["reused"] == ["vector"]
    monkeypatch.setattr(KEY, "key_parts", lambda tile: dict(parts, tile="+30+032"))
    with pytest.raises(BundleRefused, match="does not match"):
        INSTALL.plan(str(path))


def test_a_member_outside_its_folders_is_refused():
    from tile_bundle import inputs
    for bad in ("data/OSM_data/../../etc/passwd.osm", "data/Elevation_data/x/a.py",
                "patches/+30+031/sub/x.patch.osm", "other/x.json",
                "data/OSM_data/a/feed.cache"):
        with pytest.raises(ValueError):
            inputs.destination(bad)


# ---------------------------------------------------------------------------
# Package kinds (#2014 follow-up, owner 2026-11-11T16:10Z): airport-first
# export — Exact match, Airport patch only, Whole tile.
# ---------------------------------------------------------------------------
RINGS = "Elevation_data/+30+030/N30E031_approach_rings/"


def _boxes_and_rings(m):
    """HECA near the tile's south-west, HEAZ near its north-east, a ring
    cell beside each and the inset index rows' boxes."""
    m.write(INSETS + "index.json", json.dumps({
        "HECA": {"COPERNICUSGLO30": "ok", "bounding_box": [31.38, 30.10, 31.42, 30.14]},
        "HEAZ": {"COPERNICUSGLO30": "ok", "bounding_box": [31.85, 30.85, 31.90, 30.90]},
    }).encode())
    m.write(RINGS + "cell_02_01_cop_30m.tif", b"ring by HECA")
    m.write(RINGS + "cell_02_01_cop_30m.json", b"{}")
    m.write(RINGS + "cell_08_08_cop_30m.tif", b"ring by HEAZ")


def test_an_exact_package_trims_the_rings_to_its_airport(machines, tmp_path):
    a, _b = machines
    _boxes_and_rings(a)
    rings = lambda path: sorted(os.path.basename(n) for n in _members(path)  # noqa: E731
                                if "_approach_rings/" in n)
    heca = _save(a, tmp_path, "heca.xptb", airports=["HECA"], kind="exact")
    assert rings(heca) == ["cell_01_00_cop_30m.tif", "cell_02_01_cop_30m.json",
                           "cell_02_01_cop_30m.tif", "index.json"]
    heaz = _save(a, tmp_path, "heaz.xptb", airports=["HEAZ"])           # exact by default
    assert rings(heaz) == ["cell_08_08_cop_30m.tif", "index.json"]
    whole = _save(a, tmp_path, "whole.xptb")
    assert "cell_01_00_cop_30m.tif" in rings(whole) and len(rings(whole)) == 5
    assert INSTALL.read_manifest(heca)["kind"] == "exact"
    assert INSTALL.read_manifest(whole)["kind"] == "tile"


def test_an_airport_with_no_inset_box_keeps_every_ring(machines, tmp_path):
    a, _b = machines
    _boxes_and_rings(a)
    a.write(INSETS + "index.json", b'{"HECA": {"COPERNICUSGLO30": "ok"}}')
    names = _members(_save(a, tmp_path, "heca.xptb", airports=["HECA"]))
    assert len([n for n in names if "_approach_rings/" in n]) == 5


def test_a_patch_package_carries_only_the_airports_own_files(machines, tmp_path):
    a, b = machines
    a.write(PATCHES + "o4_user_roles_HECA.json", b'{"version": 1, "roles": []}')
    a.write(PATCHES + "o4_user_object_seats_HECA.json", b'{"version": 1}')
    a.write(PATCHES + "o4_user_roles_HEAZ.json", b'{"version": 1, "roles": []}')
    a.write(PATCHES + "o4_v2_rebake_HECA.json", b"{}")
    path = _save(a, tmp_path, "heca.xptb", airports=["HECA"], kind="patch")
    assert sorted(n for n in _members(path) if n not in ("manifest.json", "ATTRIBUTION.txt")) == [
        "patches/+30+031/HECA_edited.patch.osm",
        "patches/+30+031/HECA_edited.patch.osm.axes.json",
        "patches/+30+031/o4_user_object_seats_HECA.json",
        "patches/+30+031/o4_user_roles_HECA.json"]
    manifest = INSTALL.read_manifest(path)
    assert manifest["kind"] == "patch"
    assert [n["what"] for n in manifest["still_needs"]] == ["data", "imagery"]
    b.live()
    INSTALL.install(path)
    assert (b.root / PATCHES / "o4_user_roles_HECA.json").is_file()
    assert not (b.root / PATCHES / "HECA_auto.patch.osm").exists()
    assert not (b.root / PATCHES / "HEAZ_edited.patch.osm").exists()
    with pytest.raises(BundleRefused, match="no custom patch"):
        a.live()
        (a.root / PATCHES / "HEAZ_edited.patch.osm").unlink()
        a.write(PATCHES + "HEAZ_auto.patch.osm", _patch(a))
        (a.root / PATCHES / "o4_user_roles_HEAZ.json").unlink()
        PACKAGE.save_package([(LAT, LON)], str(tmp_path / "heaz.xptb"), airports=["HEAZ"],
                             kind="patch")


def test_the_install_sheet_says_what_still_downloads(machines, tmp_path):
    a, b = machines
    patch = _save(a, tmp_path, "patch.xptb", airports=["HECA"], kind="patch")
    exact = _save(a, tmp_path, "exact.xptb", airports=["HECA"], kind="exact")
    whole = _save(a, tmp_path, "whole.xptb")
    b.live()
    lines = INSTALL.plan(patch)["summary"]
    assert lines[1].startswith("Airport patch only: ")
    assert lines[2].startswith("Building still downloads: Elevation and map data for the "
                               "tile (about ") and lines[2].endswith("; Imagery.")
    assert lines[3].startswith("Estimated time to build, downloads included "
                               "(imagery not): about ")
    exact_lines = INSTALL.plan(exact)["summary"]
    assert exact_lines[1].startswith("Exact match: ")
    assert exact_lines[2].startswith("Building still downloads: Elevation for the tile's "
                                     "other airports (about ")
    assert INSTALL.plan(whole)["summary"][2] == "Building still downloads: Imagery."
    assert INSTALL.plan(exact)["kind"] == "exact"


def _noise(n, seed=7) -> bytes:
    import random
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(n))


def _terrain(n) -> bytes:
    """An SRTM-like big-endian int16 raster: smooth relief plus noise."""
    import math
    import random
    import struct
    rng = random.Random(5)
    return b"".join(struct.pack(">%dh" % n, *(
        int(200 + 80 * math.sin(r / 90.0) * math.cos(c / 70.0) + rng.randint(-3, 3))
        for c in range(n))) for r in range(n))


def test_the_size_estimate_is_within_15_percent(machines, tmp_path):
    a, _b = machines
    lines = "".join("<node id='%d' lat='30.%06d' lon='31.%06d'/>\n" % (i, i * 37 % 999983,
                                                                      i * 91 % 999979)
                    for i in range(40_000)).encode()
    a.write(PATCHES + "HECA_edited.patch.osm", _patch(a, lines + b"</osm>\n"))
    a.write(PATCHES + "HECA_edited.patch.osm.axes.json", json.dumps(
        {"axes": [[i, i * 0.5, "taxiway"] for i in range(30_000)]}).encode())
    a.write(INSETS + "HECA_copernicusglo30.tif", _noise(1_500_000))
    a.write("Elevation_data/+30+030/N30E031.hgt", _terrain(1201))
    found = ESTIMATE.estimate([(LAT, LON)], "HECA")
    assert [r["kind"] for r in found["kinds"]] == ["exact", "patch", "tile"]
    for row in found["kinds"]:
        airports = None if row["kind"] == "tile" else ["HECA"]
        actual = PACKAGE.save_package([(LAT, LON)], str(tmp_path / (row["kind"] + ".xptb")),
                                      airports=airports, kind=row["kind"])["bytes"]
        assert abs(row["bytes"] - actual) <= 0.15 * actual, (row["kind"], row["bytes"], actual)
        assert row["build_seconds"] >= 600.0
        assert "builds in about %s (estimate)" % KINDS.span_text(
            row["build_seconds"], row["build_low"], row["build_high"]) in row["figures"]


def test_the_export_window_offers_custom_patch_airports_first(machines, monkeypatch):
    a, _b = machines
    monkeypatch.setattr(KEY, "graded_airports", lambda tile: ["HEAZ", "HELX"])
    (a.root / PATCHES / "HEAZ_edited.patch.osm").unlink()
    found = PACKAGE.airports_of([(LAT, LON)])
    assert found["tiles"] == {"+30+031": ["HEAZ", "HECA", "HELX"]}
    assert found["custom"] == {"+30+031": ["HECA"]}
    assert found["default"] == "HECA"
    rows = ESTIMATE.estimate([(LAT, LON)], "HEAZ")["kinds"]
    assert [(r["kind"], r["available"]) for r in rows] == [
        ("exact", True), ("patch", False), ("tile", True)]
    assert "no custom patch" in rows[1]["why"]
    assert [r["kind"] for r in ESTIMATE.estimate([(LAT, LON)])["kinds"]] == ["tile"]


def test_combined_airport_packages_say_their_kinds(machines, tmp_path):
    a, _b = machines
    heca = _save(a, tmp_path, "heca.xptb", airports=["HECA"], kind="patch")
    heaz = _save(a, tmp_path, "heaz.xptb", airports=["HEAZ"], kind="exact")
    done = MERGE.merge_packages([heca, heaz], str(tmp_path / "both.xptb"))
    manifest = INSTALL.read_manifest(done["path"])
    assert manifest["kind"] == "combined"
    assert [n["what"] for n in manifest["still_needs"]][-1] == "imagery"
