"""GENERIC X-PLANE GROUND ANY PACK DRAPES OVER A BUILT TILE (#2085; owner
2026-11-14T15:20Z): the witness, the DSF header's cheap look, the tile
scan and the adjustment row.

Generic ground is a ``.pol`` of X-Plane's stock land-class library
(``lib/g10/terrain10``, ``lib/g8/pol``) or the pack's own draped ``.pol``
whose texture lies in the simulator's stock land-class folder.  Pavement,
markings, airport surfaces, a third-party library, pack imagery, lines
and facades are never one.  Synthetic packs and DSFs; no corpus.
"""
from __future__ import annotations

import os

import pytest
from auto_patch_v2.airport import pack_generic_ground as GG

# 0.01 deg squares at lat 25: about 1,113 m x 1,009 m = ~112 ha each
SQ = (51.00, 25.00, 51.01, 25.01)
DEFS = [
    ("lib/g10/terrain10/grass_hot_sdry_hill.pol", [SQ, SQ]),        # 0 generic
    ("lib/airport/pavement/asphalt_2D.pol", [SQ]),                  # 1 pavement
    ("lib/airport/ground/terrain/grass_dry.pol", [SQ]),             # 2 airport surface
    ("lib/airport/markings/taxi_line.pol", [SQ]),                   # 3 marking
    ("MisterX_Library/Ground_Textures/Gravel.pol", [SQ]),           # 4 a library's
    ("objects/photo.pol", [SQ]),                                    # 5 pack imagery
    ("objects/stock_grass.pol", [(51.02, 25.00, 51.03, 25.01)]),    # 6 generic (own)
    ("objects/stock_paved.pol", [SQ]),                              # 7 stock tex, paved
    ("lib/g8/pol/wet_warm_flat.pol", [(51.04, 25.00, 51.045, 25.01)]),  # 8 generic
    ("MisterX_Library/Airport/Taxilines/EdgeLine.lin", [SQ]),       # 9 a line
    ("lib/g10/terrain10/grass_cld_wet_sflat.pol", []),              # 10 unused
]
POLS = {
    "objects/photo.pol": "A\n850\nDRAPED_POLYGON\nTEXTURE_NOWRAP photo.dds\n",
    "objects/stock_grass.pol": (
        "A\n850\nDRAPED_POLYGON\nTEXTURE ../../../Resources/default scenery/"
        "1000 world terrain/textures10/loveg/grass.dds\nSCALE 3015 3015\n"),
    "objects/stock_paved.pol": (
        "A\n850\nDRAPED_POLYGON\nTEXTURE ../../../Resources/default scenery/"
        "1000 world terrain/textures10/urban/asphalt.dds\nSURFACE asphalt\n"),
}


def _ring(lon0, lat0, lon1, lat1):
    return "BEGIN_WINDING\n" + "".join(
        f"POLYGON_POINT {x:.6f} {y:.6f} {u} {v}\n" for x, y, u, v in (
            (lon0, lat0, 0, 0), (lon1, lat0, 1, 0), (lon1, lat1, 1, 1),
            (lon0, lat1, 0, 1))) + "END_WINDING\n"


def _dump(defs=DEFS) -> list[str]:
    text = "".join(f"POLYGON_DEF {p}\n" for p, _b in defs)
    for i, (_p, boxes) in enumerate(defs):
        for box in boxes:
            text += f"BEGIN_POLYGON {i} 65535 4\n" + _ring(*box) + "END_POLYGON\n"
    return text.splitlines(True)


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "Custom Scenery" / "Landmark Pack"
    for rel, text in POLS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8", newline="")
    return root


def test_only_the_generic_ground_is_flagged(pack):
    got = GG.generic_ground(str(pack), _dump())
    assert [(m.index, m.path, m.uses) for m in got.defs] == [
        (0, "lib/g10/terrain10/grass_hot_sdry_hill.pol", 2),
        (6, "objects/stock_grass.pol", 1),
        (8, "lib/g8/pol/wet_warm_flat.pol", 1)]
    assert all(m.kind == "polygon" for m in got.defs)


def test_the_hectares_union_each_definition(pack):
    got = GG.generic_ground(str(pack), _dump())
    sq = got.areas[0]
    assert 105 < sq < 120, "two polygons on one square count it once"
    assert got.areas[1] == pytest.approx(sq, rel=1e-3)
    assert got.areas[2] == pytest.approx(sq / 2, rel=1e-3)
    assert got.hectares() == pytest.approx(2.5 * sq, rel=1e-3)
    assert got.hectares(got.defs[:1]) == pytest.approx(sq, rel=1e-3)


def test_nothing_generic_is_nothing(pack):
    got = GG.generic_ground(str(pack), _dump(DEFS[1:6]))
    assert got.defs == () and got.hectares() == 0.0


def test_the_library_rule_reads_paths_not_names():
    assert GG.is_stock_land_class("lib/g10/terrain10/rock_vcld_dry_hill.pol")
    assert GG.is_stock_land_class("/LIB\\g8\\pol\\dry_cool_flat.pol")
    assert not GG.is_stock_land_class("lib/g10/terrain10/rock_vcld_dry_hill.ter")
    assert not GG.is_stock_land_class("lib/airport/ground/terrain/grass.pol")
    assert not GG.is_stock_land_class("simheaven/ground/grass.pol")


# ── the DSF header's cheap look and the tile scan ──────────────────────

def _dsf(polys, overlay="1") -> bytes:
    import O4_DSF_Binary as B
    head = B._atom("HEAD", B._atom("PROP", B._prop_bytes(
        [("sim/planet", "earth"), ("sim/overlay", overlay)])))
    defn = B._atom("DEFN", b"".join(
        B._atom(t, B._table(polys if t == "POLY" else ()))
        for t in B.DEFN_TABLES))
    return B._dsf_file([head, defn, B._atom("CMDS", b"")])


def test_the_header_names_the_polygon_definitions(tmp_path):
    import O4_DSF_Header as H
    f = tmp_path / "+25+051.dsf"
    f.write_bytes(_dsf([p for p, _b in DEFS]))
    assert H.dsf_polygon_definitions(str(f)) == [p for p, _b in DEFS]
    f.write_bytes(b"not a dsf")
    assert H.dsf_polygon_definitions(str(f)) is None


def _install(scenery, name, polys, overlay="1", marker=False):
    root = scenery / name
    dsf = root / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(_dsf(polys, overlay))
    if marker:
        import O4_Overlay_Pack as OP
        (root / OP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    return root


def test_the_scan_names_every_overlay_draping_generic_ground(tmp_path):
    from auto_patch import drape_stage as DS
    scenery = tmp_path / "Custom Scenery"
    generic = ["lib/g10/terrain10/grass_hot_sdry_hill.pol"]
    _install(scenery, "Landmarks", ["x.fac"] + generic)
    _install(scenery, "Paving", ["lib/airport/pavement/asphalt_2D.pol"])
    _install(scenery, "A Mesh", generic, overlay="0")
    _install(scenery, "Our Overlays", generic, marker=True)
    got = [os.path.basename(p) for p in DS.scanned(str(scenery), 25, 51)]
    assert got == ["Landmarks"], \
        "pavement, a base mesh and the app's own overlay pack are never asked"


def test_the_row_carries_the_hectares():
    from auto_patch import adjust_stage as AS
    from auto_patch import drape_stage as DS
    from auto_patch_v2.airport import pack_art as PA
    m = PA.MissingDef("polygon", 0, "lib/g10/terrain10/grass.pol", 3)
    row = AS._drapes_row(DS.PackDrapes("P", "/p/d.dsf", (m,), (), (), 2870.4),
                         DS.GENERIC.key)
    assert (row["key"], row["count"], row["uses"], row["hectares"],
            row["checked"]) == ("generic", 1, 3, 2870, True)
    assert "generic" in AS.CHOICES and DS.GENERIC in DS.KINDS
