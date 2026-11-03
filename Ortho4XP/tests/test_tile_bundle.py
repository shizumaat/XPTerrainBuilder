"""Twins for TILE BUNDLES (#1699 phase 1, ``src/tile_bundle``) and the
step-reuse records a bundle lays down (``O4_Step_Reuse.adopt_bundle_record``).

Headless: two stand-in "machines" in ``tmp_path`` — each with its own OSM,
patch, mask, inset and build folders and its own Custom Scenery — the
tile's folders redirected there, no pipeline, no network.  The export on
machine A and the import on machine B must leave B's step records equal
to A's in everything but B's own paths, carry no local path, imagery or
pack file, and refuse a bundle that does not match.
"""

import hashlib
import io
import json
import os
import sys
import tarfile
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Cfg_Vars as CFGVARS  # noqa: E402
import O4_Config_Utils as CFG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Object_Stage as OBJECT_STAGE  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402
import pytest  # noqa: E402
from tile_bundle import BundleRefused, contents  # noqa: E402
from tile_bundle import export as EXPORT  # noqa: E402
from tile_bundle import importer as IMPORTER  # noqa: E402
from tile_bundle import key as KEY  # noqa: E402
from tile_bundle import paths as PATHS  # noqa: E402

LAT, LON = 25, 51
BODY = b"<node id='1' lat='25.1' lon='51.1'/>\n<way id='2'/>\n</osm>\n"
MESH = bytes(range(256)) * 64


class _Tile:
    """A configured tile: every tile setting at its registry default."""

    def __init__(self, build_dir):
        self.lat, self.lon, self.build_dir = LAT, LON, str(build_dir)
        self.custom_build_dir = ""
        self.iterate = 0
        for name in CFGVARS.list_tile_vars:
            setattr(self, name, CFGVARS.cfg_vars[name]["default"])
        self.texture_mode = "full_ortho"

    def make_dirs(self):
        os.makedirs(self.build_dir, exist_ok=True)


class _Machine:
    """One installation's folders, and the redirects that make it live."""

    def __init__(self, root, pack, monkeypatch):
        self.root, self.pack, self.mp = root, pack, monkeypatch
        for name in ("osm", "patches", "masks", "build", "insets", "out"):
            (root / name).mkdir(parents=True)
        self.scenery = root / "Custom Scenery"
        (self.scenery / pack / "Earth nav data").mkdir(parents=True)
        self.tile = _Tile(root / "build")

    def live(self):
        root, mp = self.root, self.mp
        mp.setattr(FNAMES, "osm_dir", lambda lat, lon: str(root / "osm"))
        mp.setattr(FNAMES, "patch_dir", lambda lat, lon: str(root / "patches"))
        mp.setattr(FNAMES, "mask_dir", lambda lat, lon: str(root / "masks"))
        mp.setattr(FNAMES, "airport_inset_directory",
                   lambda lat, lon: str(root / "insets"))
        mp.setattr(CFG, "custom_scenery_dir", str(self.scenery))
        mp.setattr(CFG, "cifp_data_path", str(root / "Custom Data" / "CIFP"))
        mp.setattr(EXPORT, "load_tile", lambda *a, **k: self.tile)
        mp.setattr(IMPORTER, "load_tile", lambda *a, **k: self.tile)
        mp.setattr(KEY, "xplane_root", lambda tile: str(root))
        mp.setattr(KEY, "airport_signatures", lambda tile: {
            "KXXX": {"pack": self.pack, "custom": True, "signature": "s1"}})
        return self

    def apt_dat(self):
        return str(self.scenery / self.pack / "Earth nav data" / "apt.dat")


def _patch_head(machine) -> bytes:
    path = machine.apt_dat()
    return ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6' "
            "o4_apt_dat='%s' o4_dsf='%s|1|2'>\n" % (
                urllib.parse.quote(path, safe="/"),
                urllib.parse.quote(path, safe=""))).encode("utf-8")


def _build_on(machine):
    """What a finished build leaves: outputs, a plan naming the pack, and
    the three step records."""
    tile = machine.tile
    os.makedirs(tile.build_dir, exist_ok=True)
    for path in (FNAMES.input_node_file(tile), FNAMES.input_poly_file(tile),
                 FNAMES.alt_file(tile)):
        with open(path, "wb") as handle:
            handle.write(b"triangulation input")
    with open(FNAMES.mesh_file(tile.build_dir, LAT, LON), "wb") as handle:
        handle.write(MESH)
    with open(FNAMES.apt_file(tile), "wb") as handle:
        handle.write(b"apt polygons")
    patches = machine.root / "patches"
    (patches / "KXXX_auto.patch.osm").write_bytes(_patch_head(machine) + BODY)
    (patches / "KXXX_auto.patch.osm.axes.json").write_bytes(b"{}")
    (patches / "o4_v2_rebake_KXXX.json").write_bytes(json.dumps({
        "icao": "KXXX", "pack_root": str(machine.scenery / machine.pack),
        "objects": [str(machine.scenery / machine.pack / "objects" / "a.obj")]
    }).encode("utf-8"))
    (patches / "texture.dds").write_bytes(b"imagery")
    (machine.root / "masks" / "+25+051.png").write_bytes(b"mask png")
    (machine.root / "osm" / "+25+051_airports.osm.bz2").write_bytes(b"osm")
    (machine.root / "insets" / "KXXX_usgs3dep.tif").write_bytes(b"lidar")
    for step in REUSE.REUSABLE_STEPS:
        REUSE.forget_from(tile, step)
        REUSE.record(tile, step)


@pytest.fixture
def machines(tmp_path, monkeypatch):
    monkeypatch.delenv("O4_STEP_REUSE", raising=False)
    staged = []
    import O4_DSF_Data_Inputs as DSFDATA
    monkeypatch.setattr(DSFDATA, "compute", lambda tile: {
        "band": False, "measured": None, "elevation": None})
    monkeypatch.setattr(OBJECT_STAGE, "run",
                        lambda tile: staged.append(tile.build_dir) or {"airports": 1})
    a = _Machine(tmp_path / "A", "PackA", monkeypatch)
    b = _Machine(tmp_path / "B", "PackB", monkeypatch)
    a.live()
    _build_on(a)
    return a, b, staged


def _export(a):
    a.live()
    return EXPORT.export_tile(LAT, LON, str(a.root / "out"))


def _members(path) -> dict:
    with tarfile.open(path, "r:*") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}


def test_the_bundle_carries_no_local_path_imagery_or_pack_file(machines):
    a, _b, _staged = machines
    done = _export(a)
    members = _members(done["path"])
    assert "manifest.json" in members and "build/Data+25+051.mesh" in members
    assert members["build/Data+25+051.mesh"] == MESH
    for name, data in members.items():
        assert str(a.root).encode() not in data, name
        assert os.path.expanduser("~").encode() not in data, name
        assert not contents.forbidden(name), name
    assert not any(n.endswith((".axes.json", ".dds", ".alt", ".node", ".poly"))
                   for n in members)
    manifest = json.loads(members["manifest.json"])
    assert manifest["key"] == KEY.bundle_key(manifest["key_parts"])
    assert any(s["provider"] == "USGS3DEP" for s in manifest["sources"])
    # the patch BODY is untouched; only its stamp line is tokenised
    patch = members["patches/KXXX_auto.patch.osm"]
    assert patch.split(b"\n", 2)[2] == BODY
    assert b"{custom_scenery|q}/PackA" in patch


def test_import_on_another_machine_reuses_all_three_steps(machines):
    a, b, staged = machines
    done = _export(a)
    b.live()
    got = IMPORTER.import_bundle(done["path"])
    assert got["reused"] == ["vector", "mesh", "masks"], got["stale"]
    assert staged == [b.tile.build_dir]             # the object stage, alone
    plan = json.loads((b.root / "patches" / "o4_v2_rebake_KXXX.json").read_bytes())
    assert plan["pack_root"] == str(b.scenery / "PackB")   # the renamed pack
    patch = (b.root / "patches" / "KXXX_auto.patch.osm").read_bytes()
    assert patch == _patch_head(b) + BODY
    with open(FNAMES.mesh_file(b.tile.build_dir, LAT, LON), "rb") as handle:
        assert handle.read() == MESH


def _normalised(machine) -> dict:
    """A machine's step records without what only names that machine:
    install-path settings, file paths and times — and, for a file the
    bundle rewrote, its content (its paths are the machine's)."""
    absent = {os.path.basename(p) for p in REUSE.bundle_absent_outputs(machine.tile)}
    out = {}
    for step in REUSE.REUSABLE_STEPS:
        entry = REUSE.committed_entry(machine.tile, step)
        inputs = entry["inputs"]
        binary = {os.path.basename(row[0]): row[3] for row in entry["outputs"]
                  if not row[0].endswith((".json", ".osm"))
                  and os.path.basename(row[0]) not in absent}
        out[step] = {"settings": {k: v for k, v in inputs["settings"].items()
                                  if k not in KEY.NOT_PROFILE},
                     "code": inputs["code"],
                     "auto_patch_cfg": inputs["auto_patch_cfg"],
                     "binary_outputs": binary}
    return out


def test_twin_the_imported_records_equal_the_exported_ones(machines):
    a, b, _staged = machines
    done = _export(a)
    exported = _normalised(a)
    vector = REUSE.committed_entry(a.tile, "vector")["inputs"]
    pairs = PATHS.roots(a.tile, str(a.scenery), str(a.root))
    b.live()
    IMPORTER.import_bundle(done["path"])
    assert _normalised(b) == exported
    adopted = REUSE.committed_entry(b.tile, "vector")
    assert adopted["bundle"]["trusted"] == sorted(REUSE.BUNDLE_TRUSTED_KEYS)
    for name in REUSE.BUNDLE_TRUSTED_KEYS:
        assert PATHS.tokenise_text(vector[name], pairs) == \
            PATHS.tokenise_text(adopted["inputs"][name],
                                PATHS.roots(b.tile, str(b.scenery), str(b.root)))


def test_a_mismatched_pack_refuses_the_import(machines, monkeypatch):
    a, b, _staged = machines
    done = _export(a)
    b.live()
    monkeypatch.setattr(KEY, "airport_signatures", lambda tile: {
        "KXXX": {"pack": "PackB", "custom": True, "signature": "other"}})
    with pytest.raises(BundleRefused, match="KXXX"):
        IMPORTER.import_bundle(done["path"])
    assert not REUSE.committed_entry(b.tile, "vector")


def test_a_damaged_bundle_refuses_the_import(machines, tmp_path):
    a, b, _staged = machines
    done = _export(a)
    members = _members(done["path"])
    members["masks/+25+051.png"] = b"tampered"
    damaged = tmp_path / "damaged.xptbundle"
    with tarfile.open(damaged, "w:xz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    b.live()
    with pytest.raises(BundleRefused, match="damaged"):
        IMPORTER.import_bundle(str(damaged))


def test_a_non_default_mesh_setting_refuses_the_export(machines):
    a, _b, _staged = machines
    a.tile.mesh_zl = CFGVARS.cfg_vars["mesh_zl"]["default"] + 1
    with pytest.raises(BundleRefused):
        _export(a)                      # the mesh record is stale first
    for step in REUSE.REUSABLE_STEPS:
        REUSE.record(a.tile, step)
    with pytest.raises(BundleRefused, match="mesh_zl"):
        _export(a)


def test_an_edit_after_the_import_reruns_the_vector_step(machines):
    a, b, _staged = machines
    done = _export(a)
    b.live()
    IMPORTER.import_bundle(done["path"])
    patch = b.root / "patches" / "KXXX_auto.patch.osm"
    patch.write_bytes(patch.read_bytes() + b"<!-- the user's edit -->\n")
    os.utime(patch, (1, 1))
    assert REUSE.stale_reason(b.tile, "vector") == \
        "its output files changed or are missing"


def test_only_the_vector_record_is_adopted_and_only_data_is_trusted(machines):
    a, _b, _staged = machines
    with pytest.raises(ValueError):
        REUSE.adopt_bundle_record(a.tile, "mesh", "k", {})
    with pytest.raises(ValueError):
        REUSE.adopt_bundle_record(a.tile, "vector", "k", {"settings": {}})


def test_tokens_round_trip_in_every_spelling():
    root = "/Users/someone/X-Plane 12/Custom Scenery"
    pairs = [("custom_scenery", root)]
    def spelled(base, pack):
        return "%s/%s|%s|%s" % (
            base, pack, urllib.parse.quote(base + "/" + pack, safe="/"),
            urllib.parse.quote(base + "/" + pack, safe=""))
    text = spelled(root, "Old")
    token = PATHS.tokenise_text(text, pairs)
    assert root not in token and "Users" not in token
    here = [("custom_scenery", "C:/X Plane/Custom Scenery")]
    back = PATHS.detokenise_text(token, here, {"Old": "New"})
    assert back == spelled(here[0][1], "New")
    assert PATHS.leftovers(text.encode(), pairs) == [root]
    assert PATHS.leftovers(token.encode(), pairs) == []


def test_bundle_member_hashes_are_of_the_bundled_bytes(machines):
    a, _b, _staged = machines
    done = _export(a)
    members = _members(done["path"])
    manifest = json.loads(members.pop("manifest.json"))
    members.pop("ATTRIBUTION.txt")
    assert {n: hashlib.sha256(d).hexdigest() for n, d in members.items()} == \
        {n: f["sha256"] for n, f in manifest["files"].items()}


def test_twin_a_windows_bundle_imports_on_posix_and_back():
    """#1761: separators are spelled ``/`` in a bundle whatever machine
    wrote it, and with the importing machine's own separator on import."""
    win = "C:\\Users\\someone\\X-Plane 12\\Custom Scenery"
    pack = win + "\\PackA\\Earth nav data\\apt.dat"
    text = "%s|%s|%s" % (pack, urllib.parse.quote(pack, safe="/"),
                         urllib.parse.quote(pack, safe=""))
    token = PATHS.tokenise_text(text, [("custom_scenery", win)])
    assert "\\" not in token and "%5C" not in token and "C:" not in token
    assert "{custom_scenery|q}/PackA/Earth%20nav%20data/apt.dat" in token
    mac = "/Users/other/X-Plane 12/Custom Scenery"
    back = PATHS.detokenise_text(token, [("custom_scenery", mac)],
                                 {"PackA": "PackB"}, sep="/")
    want = mac + "/PackB/Earth nav data/apt.dat"
    # a Windows path holds no "/", so its two quoted spellings are one
    # string and both come back in the "/"-kept spelling (unquoted alike)
    assert back == "%s|%s|%s" % (want, urllib.parse.quote(want, safe="/"),
                                 urllib.parse.quote(want, safe="/"))
    again = PATHS.detokenise_text(token, [("custom_scenery", win)], sep="\\")
    assert again == text
