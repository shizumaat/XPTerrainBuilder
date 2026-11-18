"""Twins of #2140: a tile package (``.xptb``) carries the airport's
generated decks and road bridges, and an install places them without the
generator (``tile_bundle/generated``, ``airport/generated_record``,
``object_stage._generated_recipe``).

Headless: two stand-in machines in ``tmp_path`` (an ESSA-like tile
+59+017 with one generated deck, one faked-cut hide and one road bridge),
each with its own X-Plane install at a different path; no pipeline, no
network.  A saves a package; B installs it; B's object stage makes the
same objects, placements, chains, regions and hides with the generator
switched off, its links resolved in B's own install (never a Laminar file
in the package)."""
from __future__ import annotations

import copy
import json
import os
import tarfile

import O4_File_Names as FNAMES
import O4_Version
import pytest
from auto_patch import agp_reader
from auto_patch import object_stage as OS
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport import generated_record as grec
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.rebake import graded_surface_path
from test_deck_bridge_2132 import _install  # noqa: E402  (sibling twin)
from test_generated_2123 import _pub  # noqa: E402  (sibling twin)
from test_pack_edits_2123 import BLOCK  # noqa: E402
from tile_bundle import estimate as ESTIMATE
from tile_bundle import export as EXPORT
from tile_bundle import install as INSTALL
from tile_bundle import key as KEY
from tile_bundle import package as PACKAGE
from tile_bundle import recipient_time as RTIME

LAW = load_default()
LAT, LON, ICAO = 59, 17, "ESSA"
ROWS = ("decks", "regions", "chains", "hides")


def _essa_pub() -> dict:
    pub = _pub()
    pub["decks"][0]["hides"] = [{"object_id": "fake_cut", "resource": "objects/cut.obj",
                                 "lon": 17.005, "lat": 59.005}]
    return pub


class _Tile:
    def __init__(self, lat, lon, root):
        self.lat, self.lon = lat, lon
        self.build_dir = str(root / "Tiles" / FNAMES.tile_dir(lat, lon))
        self.custom_build_dir = ""
        self.base_elevation_source = "auto"


class _Machine:
    """One computer: its caches, patch folder, X-Plane install and pack."""

    def __init__(self, root, mp):
        self.root, self.mp = root, mp
        root.mkdir(parents=True)
        self.xplane, self.look = _install(root)
        self.pack = os.path.join(self.xplane, "Custom Scenery", "PackE")
        nav = os.path.join(self.pack, "Earth nav data")
        os.makedirs(nav)
        with open(os.path.join(nav, "apt.dat"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("I\n1100 test\n\n" + "\n".join(BLOCK) + "\n\n99\n")

    def live(self):
        mp, root = self.mp, self.root
        mp.setattr(FNAMES, "OSM_dir", str(root / "OSM_data"))
        mp.setattr(FNAMES, "Elevation_dir", str(root / "Elevation_data"))
        mp.setattr(FNAMES, "Patch_dir", str(root / "Patches"))
        mp.setattr(KEY, "pack_root", lambda tile, icao: self.pack)
        mp.setattr(agp_reader, "resolve_library_path", self.look)
        tile = lambda lat, lon, *_a, **_k: _Tile(lat, lon, root)  # noqa: E731
        mp.setattr(EXPORT, "load_tile", tile)
        mp.setattr(INSTALL, "load_tile", tile)
        return self

    @property
    def patch_dir(self) -> str:
        return FNAMES.patch_dir(LAT, LON)


@pytest.fixture
def machines(tmp_path, monkeypatch):
    from patch_library import client as LIBCLIENT
    from patch_library import terms as TERMS
    monkeypatch.setattr(LIBCLIENT, "licences", lambda: TERMS.DEFAULT_LICENCES)
    monkeypatch.setattr(PACKAGE, "_schemas", lambda tile: {"generated": grec.SCHEMA})
    monkeypatch.setattr(KEY, "xplane_root", lambda tile: None)
    monkeypatch.setattr(KEY, "airport_signatures", lambda tile: {
        ICAO: {"pack": "PackE", "custom": True, "signature": "s1"}})
    monkeypatch.setattr(KEY, "graded_airports", lambda tile: [ICAO])
    monkeypatch.setattr(INSTALL, "_downloads_left", lambda tile: [])
    monkeypatch.setattr(ESTIMATE, "_processing", lambda lat, lon: [
        RTIME._row("airports", "1 airport", 600.0, 500.0, 700.0)])
    monkeypatch.setattr(RTIME, "grid_rate", lambda: 10.0)
    monkeypatch.setattr(O4_Version, "version", "1.50.2140", raising=False)
    monkeypatch.setattr(Law, "for_airport", classmethod(lambda cls, icao: LAW))
    a = _Machine(tmp_path / "A", monkeypatch).live()
    b = _Machine(tmp_path / "B", monkeypatch)
    osm = os.path.join(FNAMES.osm_dir(LAT, LON), "+59+017_airports.osm.bz2")
    os.makedirs(os.path.dirname(osm))
    with open(osm, "wb") as fh:
        fh.write(b"airports")
    path = graded_surface_path(a.patch_dir, ICAO)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"provenance": {"generated": _essa_pub()}}, fh)
    return a, b


def _apt(m) -> str:
    return os.path.join(m.pack, "Earth nav data", "apt.dat")


def _made_on(m) -> dict:
    """What the generator makes on machine ``m``."""
    return gen.recipe(_essa_pub(), _apt(m), ICAO, LAW, resolve_library=m.look)


def test_package_carries_the_record_and_install_rebuilds_without_the_generator(
        machines, tmp_path, monkeypatch):
    a, b = machines
    made = _made_on(a)
    assert made["decks"] and made["chains"] and made["hides"] and made["links"]
    path = PACKAGE.save_package([(LAT, LON)], str(tmp_path / "essa.xptb"),
                                airports=[ICAO], kind="exact")["path"]
    with tarfile.open(path, "r:*") as tar:
        names = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    member = "generated/+59+017/ESSA.json"
    assert member in names
    for name, data in names.items():                     # no local path, no art
        assert str(a.root).encode() not in data, name
        assert not name.endswith((".dds", ".png", ".obj")), name
    doc = json.loads(names[member])
    assert set(doc["references"]) == set(made["links"])
    assert all(r.startswith("Resources/default scenery/") for r in doc["references"].values())

    b.live()
    INSTALL.install(path)
    assert os.path.isfile(grec.installed_path(b.patch_dir, ICAO))
    monkeypatch.setattr(gen, "recipe", lambda *a_, **k_: pytest.fail("the generator ran"))
    graded = {"provenance": {"generated": _essa_pub()}}
    rec = OS._generated_recipe(graded, b.pack, ICAO, LAW, "", b.patch_dir)
    assert rec["files"] == made["files"]                  # identical objects
    for k in ROWS:                                        # identical placements
        assert rec[k] == json.loads(json.dumps(made[k])), k
    assert set(rec["links"]) == set(made["links"])
    for rel, src in rec["links"].items():                 # re-linked in B's install
        assert src.startswith(b.xplane) and os.path.isfile(src)
        assert os.path.relpath(src, b.xplane) == os.path.relpath(made["links"][rel], a.xplane)


def test_a_record_is_used_only_for_its_own_publication(machines, tmp_path):
    a, b = machines
    path = PACKAGE.save_package([(LAT, LON)], str(tmp_path / "essa.xptb"))["path"]
    b.live()
    INSTALL.install(path)
    other = _essa_pub()
    other["decks"][0]["zero_m"] = 31.5                   # B's solve differs
    assert grec.installed_recipe(b.patch_dir, ICAO, other, _apt(b)) is None
    assert grec.installed_recipe(b.patch_dir, ICAO, _essa_pub(), _apt(b)) is not None


def test_a_reference_the_install_lacks_falls_back_to_the_generator(machines):
    a, b = machines
    made = _made_on(a)
    doc = grec.to_record(made, _essa_pub(), ICAO, a.xplane)
    ref = next(iter(doc["references"].values()))
    os.remove(os.path.join(b.xplane, *ref.split("/")))
    assert grec._from_record(copy.deepcopy(doc), b.xplane) is None
    assert grec._from_record(doc, a.xplane)["links"] == made["links"]


def test_art_outside_the_install_is_never_recorded(machines, tmp_path):
    a, _b = machines
    made = _made_on(a)
    outside = {"objects/o4_generated/xp_x.dds": str(tmp_path / "x.dds")}
    made["links"] = dict(made["links"], **outside)
    assert grec.to_record(made, _essa_pub(), ICAO, a.xplane) is None


def test_the_record_keeps_the_hides_a_rewrite_reapplies():
    rec = {"decks": [{"resource": "r"}], "hides": [{"resource": "objects/cut.obj",
                                                     "lon": 1.0, "lat": 2.0}]}
    row = gen.record("sha", rec, {}, "t")
    assert gen.recorded({gen.RECORD_KEY: row}, "sha")["hides"] == rec["hides"]
