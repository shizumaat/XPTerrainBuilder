"""DRAPED PHOTOS A PACK SHIPS OVER ITS AIRPORT (#1916): the witness, the
hiding the write carries, and its Undo.

The witness reads the files only: the pack's own ``.pol`` (draped, one
non-wrapping image, no paved surface, not weather-transparent), its placement
(image-mapped north-up, over an airport, photo-sized) and its image (not
all see-through).  A draped pavement or marking polygon, a decal turned
to its runway, a see-through overlay and a library polygon are never
one.  The grid rule (RULINGS 2026-11-07a (3), ``pack_drape_grid``) then
hides only a machine-named photo grid that extends outside the airport,
WHOLE (#1960); a detail-texture grid drawn over it stays (RULINGS
2026-11-09a (11), #1946); every other photo of the pack on the tile goes
with it (RULINGS 2026-11-09a (10), #1968).  A single photo and scattered
tiles alone are kept; a decal on a tile holds nothing.  Synthetic packs, a byte-copy DSFTool; no
network, no corpus.
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
from auto_patch_v2.airport import pack_art as PA
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
    "ground/oil.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP oil.dds\n"
                      "SCALE 25 25\nLOAD_CENTER 25.0 51.0 29 2048\n"
                      "LAYER_GROUP markings 2\n",
    **{f"nice/nice_0x{n}.pol": f"A\n850\nDRAPED_POLYGON\n\nDECAL_LIB decal.dcl\n"
                               "LAYER_GROUP terrain 1\nSURFACE grass\n\n"
                               f"TEXTURE_NOWRAP nice_0x{n}.png\nSCALE 25 25"
       for n in range(1, 7)},
    **{f"grid/Tile{n}.pol": f"A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP\tTile{n}.dds\n"
                            "SCALE 25 25\nLOAD_CENTER 25.0 51.0 300 2048\n"
                            "LAYER_GROUP terrain 1\n" for n in range(1, 7)},
    **{f"grid/Veil{n}.pol": f"A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP Veil{n}.dds\n"
                            "SCALE 25 25\nLAYER_GROUP markings 0\n"
                            for n in range(1, 7)},
}
#: the image each .pol names: True = opaque (DXT1), False = see-through
IMAGES = {"ortho/photo.dds": True, "ortho/plain.dds": True,
          "ground/asphalt.dds": True, "ground/stripe.dds": True,
          "ground/grime.dds": False, "ground/skid.dds": True,
          "ground/haze.dds": False, "ground/oil.dds": True,
          **{f"grid/Tile{n}.dds": True for n in range(1, 7)},
          **{f"grid/Veil{n}.dds": False for n in range(1, 7)}}
AT = (51.000, 25.000, 0.003)        # over the airport (lon, lat, size)
OFF = (51.500, 25.500, 0.003)       # far from it


def _tile(col: int, row: int) -> tuple[float, float, float]:
    """One cell of a 3 x 2 grid of 0.004-degree tiles east of AT: its
    first row crosses the runway, its second leaves the airport."""
    return (51.004 + 0.004 * col, 25.000 + 0.004 * row, 0.004)


#: def index -> (path, turn of the image, where)
DEFS = [("ortho/photo.pol", 0.0, AT),            # 0 a single photo: kept
        ("ortho/plain.pol", 1.0, AT),            # 1 a single photo, no LOAD_CENTER
        ("ground/asphalt.pol", 0.0, AT),         # 2 pavement
        ("ground/stripe.pol", 0.0, AT),          # 3 a tiled marking
        ("ground/grime.pol", 0.0, AT),           # 4 weather-transparent
        ("ground/skid.pol", 30.0, AT),           # 5 turned to its runway
        ("ground/haze.pol", 0.0, AT),            # 6 see-through image
        ("lib/airport/markings/DrapedDirSigns.pol", 0.0, AT),  # 7 library
        ("ortho/photo.pol", 0.0, OFF)]           # 8 a photo off the airport
#: 9-14 the machine-named grid Tile1..Tile6; 9 and 10 cross the runway
GRID = [(f"grid/Tile{c + 3 * r + 1}.pol", 0.0, _tile(c, r))
        for r in range(2) for c in range(3)]
DEFS += GRID


def _dds(opaque: bool, size: int = 64) -> bytes:
    head = bytearray(128)
    head[:4] = b"DDS "
    struct.pack_into("<IIII", head, 4, 124, 0x1007, size, size)
    struct.pack_into("<II", head, 76, 32, 0x4)
    head[84:88] = b"DXT1" if opaque else b"DXT5"
    block = bytes(16) if not opaque else b"\xff" * 16
    return bytes(head) + block * ((size // 4) ** 2)


def _polygon(i: int, turn: float, where: tuple[float, float, float]) -> str:
    lon0, lat0, d = where
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
    areas = [b for b, _ok in PD.airport_boxes(str(pack / "Earth nav data" / "apt.dat"))]
    return PD.draped_orthos(str(pack), (dump or _dump()).splitlines(True), areas)


def test_the_grid_over_the_airport_is_hidden_whole(pack):
    found = _found(pack)
    assert [(m.index, m.path) for m in found] == [
        (9 + k, f"grid/Tile{k + 1}.pol") for k in range(6)], \
        "every tile, the four off the airport too (#1960)"
    assert all(m.kind == "polygon" and m.uses == 1 for m in found)


def test_a_decal_on_a_tile_holds_nothing(pack):
    oil = [("ground/oil.pol", 0.0, (51.0045, 25.0005, 0.0003))]
    found = {m.path for m in _found(pack, _dump(DEFS + oil))}
    assert found == {f"grid/Tile{k}.pol" for k in range(1, 7)}, \
        "an oil decal (with WED's LOAD_CENTER) is not a photo stack (#1960)"


def test_a_grid_carrying_a_grass_surface_is_a_photo_grid(pack):
    nice = [(f"nice/nice_0x{k + 1}.pol", 0.0, w) for k, (_p, _t, w) in enumerate(GRID)]
    found = {m.path for m in _found(pack, _dump(DEFS[:9] + nice))}
    assert found == {f"nice/nice_0x{k}.pol" for k in range(1, 7)}, \
        "SURFACE grass + DECAL_LIB, no LOAD_CENTER: still a photo grid (#1943)"


def test_single_photos_and_scattered_tiles_are_kept(pack):
    found = {m.index for m in _found(pack)}
    assert not found & {0, 1}, "a single photo over the airport stays"
    scattered = DEFS[:9] + [(p, t, (lon + 0.004 * k, lat + 0.004 * k, d))
                            for k, (p, t, (lon, lat, d)) in enumerate(GRID)]
    assert _found(pack, _dump(scattered)) == (), "tiles that touch no other"


def test_a_grid_inside_the_airport_is_kept(pack):
    apt = (pack / "Earth nav data" / "apt.dat")
    apt.write_text(APT.replace("99\n", "130 boundary\n"
                               "111 25.10 50.90\n111 25.10 51.10\n"
                               "111 24.90 51.10\n113 24.90 50.90\n99\n"),
                   encoding="utf-8", newline="")
    rows = PD.airport_boxes(str(apt))
    areas, bounded = [b for b, _ok in rows], all(ok for _b, ok in rows)
    assert bounded
    assert PD.draped_orthos(str(pack), _dump().splitlines(True), areas,
                            bounded=bounded) == ()


def test_a_photo_grid_under_a_detail_grid_is_hidden(pack):
    tiles = {f"grid/Tile{k}.pol" for k in range(1, 7)}
    veils = [(f"grid/Veil{k + 1}.pol", 0.0, w) for k, (_p, _t, w) in enumerate(GRID)]
    assert {m.path for m in _found(pack, _dump(DEFS + veils))} == tiles, \
        "hide the grid, keep the detail textures (RULINGS 2026-11-09a (11))"
    part = [(f"grid/Veil{k + 1}.pol", 0.0, (lon + 0.008, lat, d))
            for k, (_p, _t, (lon, lat, d)) in enumerate(GRID)]
    assert {m.path for m in _found(pack, _dump(DEFS + part))} == tiles, \
        "a detail grid over one column: the whole photo grid, no veil (#1946)"


def test_every_photo_of_the_pack_goes_with_the_grid(pack):
    far = [(p, t, (lon + 0.4, lat + 0.4, d)) for p, t, (lon, lat, d) in GRID]
    stray = [("grid/Tile1.pol", 0.0, (51.3, 25.3, 0.004)),     # tiles nothing
             ("grid/Tile2.pol", 30.0, (51.2, 25.2, 0.004))]    # reads turned
    defs = DEFS + far + stray
    found = {m.index for m in _found(pack, _dump(defs))}
    assert found == set(range(9, len(defs))), \
        "hide them all so our ortho imagery shows (RULINGS 2026-11-09a (10))"
    alone = DEFS[:9] + far + stray
    assert _found(pack, _dump(alone)) == (), \
        "with no grid over the airport nothing is hidden"


def test_masks_over_the_hidden_photos_go_with_them(pack, tmp_path):
    for n in range(1, 7):        # the veils drawn at the photos' own order
        (pack / f"grid/Veil{n}.pol").write_text(
            POLS[f"grid/Veil{n}.pol"].replace("markings 0", "terrain 1"),
            encoding="utf-8", newline="")
    veils = [(f"grid/Veil{k + 1}.pol", 0.0, w) for k, (_p, _t, w) in enumerate(GRID)]
    found = {m.path for m in _found(pack, _dump(DEFS + veils))}
    assert found == {f"grid/{n}{k}.pol" for n in ("Tile", "Veil")
                     for k in range(1, 7)}


def _small_grid(pack, rows: int, cols: int, d: float = 0.0004) -> list:
    """WED's photo laid as many SMALL tiles (issue #2036, SBRJ: 839 tiles
    of 34-145 m named ``images/sdu_ortophoto_<r>x<c>.pol``, no
    ``LOAD_CENTER``): ``rows`` x ``cols`` tiles of ``d`` degrees going
    north from the runway, each under ``MIN_SPAN_M``."""
    out = []
    for r in range(rows):
        for c in range(cols):
            rel = f"images/sdu_ortophoto_{r}x{c}"
            (pack / f"{rel}.pol").parent.mkdir(parents=True, exist_ok=True)
            (pack / f"{rel}.pol").write_text(
                "A\n850\nDRAPED_POLYGON\nDECAL_LIB lib/g10/decals/x.dcl\n"
                f"LAYER_GROUP beaches -1\n\nTEXTURE_NOWRAP sdu_ortophoto_{r}x{c}.dds\n"
                "SCALE 25.000000 25.000000", encoding="utf-8", newline="")
            (pack / f"{rel}.dds").write_bytes(_dds(True))
            out.append((f"images\\sdu_ortophoto_{r}x{c}.pol", 0.0,
                        (51.004 + d * c, 25.000 + d * r, d)))
    return out


def test_a_grid_of_small_tiles_is_photo_sized_by_its_extent(pack):
    small = _small_grid(pack, rows=20, cols=2)
    assert all(PD._span_m((lon, lat, lon + d, lat + d)) < PD.MIN_SPAN_M
               for _p, _t, (lon, lat, d) in small), "every tile is small"
    found = {m.path for m in _found(pack, _dump(DEFS[:9] + small))}
    assert found == {p for p, _t, _w in small}, \
        "the grid's 885 m extent makes its tiles a photo (#2036)"


def test_a_lone_small_tile_is_no_photo(pack):
    small = _small_grid(pack, rows=1, cols=1)
    assert _found(pack, _dump(DEFS[:9] + small)) == (), \
        "no grid and no LOAD_CENTER: a small polygon is a decal"


def test_draped_pavement_and_markings_are_never_photos(pack):
    for rel in ("ground/asphalt.pol", "ground/stripe.pol"):
        assert not PD.is_ortho_header(PD.pol_header(str(pack / rel)))
    found = {m.index for m in _found(pack)}
    assert not found & {2, 3, 4, 5, 6, 7, 8}


def test_a_tab_separated_header_is_read(pack):
    head = PD.pol_header(str(pack / "grid/Tile1.pol"))
    assert head["TEXTURE_NOWRAP"] == "Tile1.dds" and PD.is_ortho_header(head)


def test_the_family_keys():
    from auto_patch_v2.airport import pack_drape_grid as G
    assert (G._family_keys("o/KDAL_Photoreal23+2k+4k.pol", "")
            & G._family_keys("o/KDAL_Photoreal28.pol", ""))
    assert (G._family_keys("Orthophoto\\7JF26B82.pol", "")
            & G._family_keys("Orthophoto/IA255JC3.pol", ""))
    assert not (G._family_keys("o/Asphalt.pol", "")
                & G._family_keys("o/Concrete.pol", ""))


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
    row = PA.record("abc", found, {}, "t")
    assert PD.recorded({PD.RECORD_KEY: row}, "abc") == found
    assert PD.recorded({PD.RECORD_KEY: row}, "other") == ()
    assert PD.summary(found)["count"] == 6


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
    assert "grid/Tile1.pol" not in live and "grid/Tile6.pol" not in live
    assert live.count("POLYGON_DEF ") == len(DEFS) - 6
    assert "ground/skid.pol" in live and "BEGIN_POLYGON 0 65535 4" in live
    assert DS.undo(str(rp.pack)) == ["Earth nav data/+20+050/+25+051.dsf"]
    assert rp.dsf.read_bytes() == original
