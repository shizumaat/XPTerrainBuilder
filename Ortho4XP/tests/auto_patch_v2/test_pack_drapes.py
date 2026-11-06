"""DRAPED PHOTOS A PACK SHIPS OVER ITS AIRPORT (#1916): the witness, the
hiding the write carries, and its Undo.

The witness reads the files only: the pack's own ``.pol`` (draped, one
non-wrapping image, no surface, not weather-transparent), its placement
(image-mapped north-up, over an airport, photo-sized) and its image (not
all see-through).  A draped pavement or marking polygon, a decal turned
to its runway, a see-through overlay and a library polygon are never
one.  Synthetic packs, a byte-copy DSFTool; no network, no corpus.
"""
from __future__ import annotations

import math
import struct
import sys
import types

import pytest
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import image_opacity as IO
from auto_patch_v2.airport import pack_drapes as PD
from auto_patch_v2.model import placement as PM

APT = ("I\n1100 test\n\n1      12 0 0 OTST Test Field\n"
       "100 30.00 1 0 0.25 0 2 0 09 25.00100 51.00000 0 0 1 0 0 0 "
       "27 25.00100 51.01000 0 0 1 0 0 0\n99\n")
POLS = {
    "ortho/photo.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP photo.dds\n"
                       "SCALE 25 25\nLOAD_CENTER 25.0 51.0 300 2048\n"
                       "LAYER_GROUP terrain 1\n",
    "ortho/plain.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP plain.dds\n"
                       "SCALE 25 25\nLAYER_GROUP markings -1\n",
    "ground/asphalt.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE asphalt.dds\n"
                          "SCALE 25 25\nSURFACE asphalt\n"
                          "LAYER_GROUP taxiways 1\n",
    "ground/stripe.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE stripe.dds\n"
                         "SCALE 5 5\nLAYER_GROUP markings 1\n",
    "ground/grime.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP grime.dds\n"
                        "WEATHER_TRANSPARENT\nSCALE 25 25\n",
    "ground/skid.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP skid.dds\n"
                       "SCALE 25 25\n",
    "ground/haze.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP haze.dds\n"
                       "SCALE 25 25\n",
}
#: the image each .pol names: True = opaque (DXT1), False = see-through
IMAGES = {"ortho/photo.dds": True, "ortho/plain.dds": True,
          "ground/asphalt.dds": True, "ground/stripe.dds": True,
          "ground/grime.dds": False, "ground/skid.dds": True,
          "ground/haze.dds": False}
#: def index -> (path, turn of the image, over the airport)
DEFS = [("ortho/photo.pol", 0.0, True),          # 0 a photo: hidden
        ("ortho/plain.pol", 1.0, True),          # 1 a photo, no LOAD_CENTER
        ("ground/asphalt.pol", 0.0, True),       # 2 pavement
        ("ground/stripe.pol", 0.0, True),        # 3 a tiled marking
        ("ground/grime.pol", 0.0, True),         # 4 weather-transparent
        ("ground/skid.pol", 30.0, True),         # 5 turned to its runway
        ("ground/haze.pol", 0.0, True),          # 6 see-through image
        ("lib/airport/markings/DrapedDirSigns.pol", 0.0, True),  # 7 library
        ("ortho/photo.pol", 0.0, False)]         # 8 a photo off the airport


def _dds(opaque: bool, size: int = 64) -> bytes:
    head = bytearray(128)
    head[:4] = b"DDS "
    struct.pack_into("<IIII", head, 4, 124, 0x1007, size, size)
    struct.pack_into("<II", head, 76, 32, 0x4)
    head[84:88] = b"DXT1" if opaque else b"DXT5"
    block = bytes(16) if not opaque else b"\xff" * 16
    return bytes(head) + block * ((size // 4) ** 2)


def _polygon(i: int, turn: float, over: bool) -> str:
    lon0, lat0 = (51.000, 25.000) if over else (51.500, 25.500)
    d = 0.003
    t = math.radians(turn)
    rows = []
    for dx, dy in ((0, 0), (d, 0), (d, d), (0, d)):
        x, y = dx / d, dy / d
        u = math.cos(t) * x + math.sin(t) * y
        v = -math.sin(t) * x + math.cos(t) * y
        rows.append(f"POLYGON_POINT {lon0 + dx:.9f} {lat0 + dy:.9f} "
                    f"{u:.6f} {v:.6f}")
    return (f"BEGIN_POLYGON {i} 65535 4\nBEGIN_WINDING\n" + "\n".join(rows)
            + "\nEND_WINDING\nEND_POLYGON\n")


def _dump(defs=DEFS) -> str:
    head = "PROPERTY sim/west 51\n" + "".join(
        f"POLYGON_DEF {p}\n" for p, _t, _o in defs)
    return head + "".join(_polygon(i, t, o) for i, (_p, t, o) in enumerate(defs))


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "Custom Scenery" / "Photo Pack"
    for rel, text in POLS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8", newline="")
    for rel, opaque in IMAGES.items():
        (root / rel).write_bytes(_dds(opaque))
    nav = root / "Earth nav data"
    nav.mkdir()
    (nav / "apt.dat").write_text(APT, encoding="utf-8", newline="")
    return root


def _found(pack, dump=None):
    areas = PD.airport_areas(str(pack / "Earth nav data" / "apt.dat"))
    return PD.draped_orthos(str(pack), (dump or _dump()).splitlines(True), areas)


def test_the_photos_are_found_and_nothing_else(pack):
    found = _found(pack)
    assert [(m.index, m.path) for m in found] == [
        (0, "ortho/photo.pol"), (1, "ortho/plain.pol")]
    assert all(m.kind == "polygon" and m.uses == 1 for m in found)


def test_draped_pavement_and_markings_are_never_photos(pack):
    for rel in ("ground/asphalt.pol", "ground/stripe.pol"):
        assert not PD.is_ortho_header(PD.pol_header(str(pack / rel)))
    found = {m.index for m in _found(pack)}
    assert not found & {2, 3, 4, 5, 6, 7, 8}


def test_without_an_airport_nothing_is_found(pack):
    assert PD.draped_orthos(str(pack), _dump().splitlines(True), []) == ()


def test_the_opacity_sampler(pack, tmp_path):
    assert IO.opaque_fraction(str(pack / "ortho/photo.dds")) == 1.0
    assert IO.opaque_fraction(str(pack / "ground/haze.dds")) == 0.0
    five = bytearray(_dds(False))
    for b in range(128, len(five), 16):
        five[b:b + 2] = b"\xff\xff"          # every alpha block opaque
    path = tmp_path / "five.dds"
    path.write_bytes(bytes(five))
    assert IO.opaque_fraction(str(path)) == 1.0
    assert IO.opaque_fraction(str(tmp_path / "absent.dds")) is None


def test_the_record_reads_back_only_for_its_pristine_file(pack):
    found = _found(pack)
    row = PD.record("abc", found, {}, "t")
    assert PD.recorded({PD.RECORD_KEY: row}, "abc") == found
    assert PD.recorded({PD.RECORD_KEY: row}, "other") == ()
    assert PD.summary(found)["count"] == 2


# ── the write hides them; Undo puts them back ───────────────────────────

@pytest.fixture
def written(pack, tmp_path, monkeypatch):
    """The pack's DSF (its dump as bytes) and a byte-copy DSFTool."""
    import O4_UI_Utils as UI
    from auto_patch import dsf_reader as DSFR
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\nshutil.copyfile(sys.argv[2], "
                    "sys.argv[3])\n", encoding="utf-8", newline="")
    real_run = W.subprocess.run
    monkeypatch.setattr(W.subprocess, "run", lambda args, **kw: real_run(
        [sys.executable, str(tool)] + list(args[1:]), **kw))
    monkeypatch.setattr(DSFR, "_dsftool_path", lambda: str(tool))
    monkeypatch.setattr(DSFR, "ensure_dsf_text_path", lambda *a, **k: None)
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    B.invalidate_memo()
    dsf = pack / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(_dump().encode("utf-8"))
    yield types.SimpleNamespace(pack=pack, dsf=dsf, tool=str(tool))
    B.invalidate_memo()


def test_the_write_hides_them_and_undo_puts_them_back(written):
    from auto_patch import drape_stage as DS
    rp = written
    original = rp.dsf.read_bytes()
    found = _found(rp.pack)
    plan = PM.PlacementPlan("", rp.pack.name, str(rp.pack), str(rp.dsf),
                            str(rp.dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}))
    W.write_pack(str(rp.pack), plan, rp.tool, allow_live_install=True,
                 drapes=found)
    live = rp.dsf.read_text(encoding="utf-8")
    assert "ortho/plain.pol" not in live
    assert live.count("POLYGON_DEF ") == len(DEFS) - 2
    assert "POLYGON_DEF ortho/photo.pol" in live, "the copy off the airport stays"
    assert "ground/skid.pol" in live and "BEGIN_POLYGON 0 65535 4" in live
    assert DS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert rp.dsf.read_bytes() == original
