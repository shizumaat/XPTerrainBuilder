"""Twins for #2037 (3): World drape tiles get index rows, so the follow
job sharpens them.

Observed on 2026-11-13 (CYEG, 1.0.506): fifteen Bing drape tiles swapped
into the World pack around Edmonton had no index rows (``textures/<tile>``
of the pack, no build folder left), so the follow job could never land a
finer tier over them.  The rules these twins hold:

* a drape swapped in is registered from the pack's own files: one row per
  texture, ``low`` at the drape's width, its file kept as the placeholder
  (the same file, linked), its rows folder marked ``kind: drape``;
* a drape row lands like the drape's fetch converts: no colour field, and
  a WATER square (its file is DXT5) gets the drape's own mask imprinted;
  the converter's copy in the rows folder goes once landed;
* ``O4_DDS_Alpha`` decodes a DXT5 alpha exactly as the block format says;
* the World publish registers a drape and forgets the drape a full tile
  replaces.
"""
from __future__ import annotations

import os

import numpy
import O4_DDS_Alpha as ALPHA
import O4_DDS_Encode as ENCODE
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Index as INDEX
import O4_World_Drape as DRAPE
import O4_World_Pack as WP
from o4_engine import imagery_follow_drape as DRAPE_ROWS

LAT, LON, ZL = 52, -113, 16
TILE = "+52-113"
LAND, WATER = (12208, 21344), (12192, 21344)     # (til_x, til_y)


def _dds(path, width, alpha=None) -> None:
    rng = numpy.random.default_rng(width)
    pixels = rng.integers(0, 255, (width, width, 3), dtype=numpy.uint8)
    if alpha is not None:
        pixels = numpy.dstack([pixels, alpha])
    with open(path, "wb") as handle:
        handle.write(ENCODE.encode_dds(pixels, "bc3" if alpha is not None
                                       else "bc1"))


def _mask(width):
    """Open water on the left, shore feather, land on the right."""
    ramp = numpy.clip(numpy.linspace(-200, 455, width), 135, 255)
    return numpy.tile(ramp.astype(numpy.uint8), (width, 1))


def _pack(tmp_path):
    """A World pack holding one drape tile: a land and a water square."""
    pack = tmp_path / "World"
    textures, terrain = pack / "textures" / TILE, pack / "terrain" / TILE
    textures.mkdir(parents=True)
    terrain.mkdir(parents=True)
    for (x, y), water in ((LAND, False), (WATER, True)):
        name = DRAPE.default_dds_name(x, y, ZL, "BI")
        _dds(textures / name, 512, _mask(512) if water else None)
        rel = f"../../textures/{TILE}/{name}"
        stem = name[:-4]
        (terrain / f"{stem}.pol").write_text(
            DRAPE.pol_text(rel, x, y, ZL, 512), encoding="utf-8", newline="")
        if water:
            (terrain / f"{stem}_water.pol").write_text(DRAPE.pol_text(
                rel, x, y, ZL, 512, DRAPE.WATER_LAYER_GROUP, alpha=True),
                encoding="utf-8", newline="")
    dsf = pack / WP.dsf_relpath(LAT, LON)
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF" + DRAPE.DRAPE_AGENT.encode() + b"\0" * 64)
    return pack


def test_a_dxt5_alpha_decodes_as_its_blocks_say():
    from auto_patch_v2.airport.image_opacity import _dxt5_alpha
    mask = _mask(64)
    pixels = numpy.dstack([numpy.zeros((64, 64, 3), numpy.uint8), mask])
    data = ENCODE.encode_dds(pixels, "bc3", mips=False)
    blocks = data[DDS.HEADER_BYTES:]
    alpha = ALPHA._decode_bc3_alpha(blocks, 64, 64)
    for b in range(0, 256, 17):         # the scalar reading, block by block
        by, bx = divmod(b, 16)
        ref = numpy.array(_dxt5_alpha(blocks[16 * b:16 * b + 8])).reshape(4, 4)
        assert (alpha[4 * by:4 * by + 4, 4 * bx:4 * bx + 4] == ref).all()
    assert numpy.abs(alpha.astype(int) - mask.astype(int)).max() <= 12


def test_a_drape_swapped_in_gets_its_rows(tmp_path):
    pack = _pack(tmp_path)
    index = str(tmp_path / "index.sqlite")
    store = str(tmp_path / "store")
    assert DRAPE_ROWS.register(str(pack), LAT, LON, index=index, store=store) == 2
    conn = INDEX.open_index(index)
    rows = INDEX.rows(conn, tile=TILE)
    conn.close()
    assert {r["state"] for r in rows} == {"low"}
    assert {r["tier_px"] for r in rows} == {512}
    for row in rows:
        assert DRAPE_ROWS.is_drape_dir(row["build_dir"])
        assert INDEX.texture_path(row) == str(pack / "textures" / TILE / row["name"])
        kept = row["placeholder_path"]
        assert kept.startswith(row["build_dir"])          # never the store's own
        assert os.path.samefile(kept, INDEX.texture_path(row))
        assert row["centre_lat"] and row["load_size_m"] > 4000
    assert DRAPE_ROWS.forget(LAT, LON, store=store)
    assert not os.path.exists(DRAPE_ROWS._rows_dir(TILE, store))


def test_a_drape_row_lands_with_its_water_mask(tmp_path, monkeypatch):
    import O4_Imagery_Utils as IMG
    from o4_engine.imagery_follow_land import TierLander
    pack = _pack(tmp_path)
    index = str(tmp_path / "index.sqlite")
    DRAPE_ROWS.register(str(pack), LAT, LON, index=index,
                        store=str(tmp_path / "store"))
    conn = INDEX.open_index(index)
    rows = {r["name"]: r for r in INDEX.rows(conn, tile=TILE)}
    conn.close()
    seen = {}

    def convert(tile, til_x, til_y, zl, provider, drop=None):
        name = FNAMES.dds_file_name_from_attributes(til_x, til_y, zl, provider)
        mask = os.path.join(tile.build_dir, "textures",
                            FNAMES.mask_file(til_x, til_y, zl, provider))
        seen[name] = (os.path.isfile(mask), tile.color_harmonization,
                      tile.imprint_masks_to_dds)
        if os.path.isfile(mask):
            os.remove(mask)                         # as the converter does
        _dds(os.path.join(tile.build_dir, "textures", name), 4096 >> drop)

    monkeypatch.setattr(IMG, "build_jpeg_ortho", lambda *a, **k: 1)
    monkeypatch.setattr(IMG, "convert_texture", convert)
    lander = TierLander()
    for (x, y), water in ((LAND, False), (WATER, True)):
        name = DRAPE.default_dds_name(x, y, ZL, "BI")
        facts = lander(rows[name], 1)
        assert facts["tier_px"] == 1024
        final = pack / "textures" / TILE / name
        assert TIERS.texture_header(str(final))[0] == 1024
        assert seen[name] == (water, False, True)
        built = os.path.join(rows[name]["build_dir"], "textures", name)
        assert not os.path.exists(built)            # the work copy is gone
        kept = rows[name]["placeholder_path"]
        assert TIERS.texture_header(kept)[0] == 512  # the drape's file kept


def test_the_world_publish_registers_a_drape(tmp_path, monkeypatch):
    from o4_engine import imagery_ondemand as ONDEMAND
    from o4_engine import world_commands as WORLD
    from o4_engine import world_publish as PUBLISH
    pack = _pack(tmp_path)
    monkeypatch.setattr(WORLD, "pack_dir", lambda scenery: str(pack))
    calls = []
    monkeypatch.setattr(DRAPE_ROWS, "register",
                        lambda p, la, lo: calls.append(("register", la, lo)))
    monkeypatch.setattr(DRAPE_ROWS, "forget",
                        lambda la, lo: calls.append(("forget", la, lo)))
    monkeypatch.setattr(ONDEMAND, "register_tiles", lambda tiles: 0)
    PUBLISH._after_swap(str(tmp_path), str(tmp_path / "gone"), LAT, LON)
    assert calls == [("register", LAT, LON)]
    (pack / WP.dsf_relpath(LAT, LON)).write_bytes(b"XPLNEDSF a full tile")
    PUBLISH._after_swap(str(tmp_path), str(tmp_path / "build"), LAT, LON)
    assert calls[-1] == ("forget", LAT, LON)
