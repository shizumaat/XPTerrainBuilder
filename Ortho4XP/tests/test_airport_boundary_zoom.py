"""Twins of the zoom level inside an airport boundary (#2107,
``O4_Airport_Boundary_Zoom``): the provider's finest available level,
capped by the mesh grid, falling back where the provider has no data;
the squares recorded and made low-res last on demand."""
import pickle
import types

import O4_Airport_Approach_Cover as COVER
import O4_Airport_Boundary_Zoom as BZ
import O4_DSF_Utils as DSF
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Budget as BUDGET
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Tile_Info as TINFO
from shapely.geometry import MultiPolygon, Polygon, box

LAT, LON = 40, 10
#: a 3 km x 1.5 km boundary near the tile centre, tile-local degrees
BOUNDARY = MultiPolygon([Polygon([(0.50, 0.50), (0.535, 0.50),
                                  (0.535, 0.5135), (0.50, 0.5135)])])
PROVIDER = {"code": "FAKE", "grid_type": "webmercator", "request_type": "tms"}


def _tile(mesh_zl=19, cover_zl=18, **kw):
    base = dict(lat=LAT, lon=LON, mesh_zl=mesh_zl, cover_zl=cover_zl,
                default_zl=16, default_website="FAKE", zone_list=[],
                cover_extent=0.0, cover_approach_ft=0,
                cover_airports_with_highres="True")
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_the_ceiling_is_the_mesh_grid_capped_by_the_provider():
    assert BZ._ceiling_zl(_tile(), PROVIDER) == 19
    assert BZ._ceiling_zl(_tile(mesh_zl=20), PROVIDER) == 20
    assert BZ._ceiling_zl(_tile(mesh_zl=20), dict(PROVIDER, max_zl=19)) == 19
    # nothing finer than the cover: no change
    assert BZ._ceiling_zl(_tile(), dict(PROVIDER, max_zl=18)) is None
    # a source that cannot be asked tile by tile abstains
    assert BZ._ceiling_zl(_tile(), None) is None
    assert BZ._ceiling_zl(_tile(), dict(PROVIDER, grid_type="epsg4326")) is None


def _probe(has):
    """A provider with imagery at the levels of ``has`` (``None``: no
    answer at all)."""
    def probe(provider, zl, til_x, til_y):
        return None if has is None else zl in has
    return probe


def test_a_square_falls_back_to_the_finest_level_with_data():
    sq = (16 * 1000, 16 * 1000)
    assert BZ._available_zl(PROVIDER, sq, 20, 18, _probe({20, 19})) == 20
    assert BZ._available_zl(PROVIDER, sq, 20, 18, _probe({19})) == 19
    assert BZ._available_zl(PROVIDER, sq, 20, 18, _probe(set())) == 18
    # no answer (offline) is not a "no": the ceiling stands
    assert BZ._available_zl(PROVIDER, sq, 20, 18, _probe(None)) == 20


def test_a_lower_level_asks_the_tiles_under_the_square():
    asked = []

    def probe(provider, zl, til_x, til_y):
        asked.append((zl, til_x, til_y))
        return zl == 18
    sq = (16 * 1001, 16 * 1003)
    assert BZ._available_zl(PROVIDER, sq, 19, 17, probe) == 18
    for zl, til_x, til_y in asked:
        scale = 2 ** (19 - zl)
        assert sq[0] // scale <= til_x < (sq[0] + 16) // scale
        assert sq[1] // scale <= til_y < (sq[1] + 16) // scale


def test_the_blocks_are_the_boundary_squares_alone():
    tile = _tile()
    dico = {"ZZZZ": {"boundary": BOUNDARY}}
    blocks = BZ.boundary_blocks(tile, dico, ["ZZZZ"], PROVIDER, _probe({19}))
    assert blocks and set(blocks.values()) == {19}
    assert set(blocks) == COVER.region_squares(BOUNDARY, LAT, LON, 19)
    for sq in blocks:
        assert BOUNDARY.intersects(box(*COVER.square_bounds(*sq, 19, LAT, LON)))
    # where the provider has nothing finer than the cover, nothing changes
    assert BZ.boundary_blocks(tile, dico, ["ZZZZ"], PROVIDER,
                              _probe({18})) == {}


def test_a_coarser_ceiling_spreads_over_its_mesh_blocks():
    tile = _tile(mesh_zl=20, cover_zl=18)
    dico = {"ZZZZ": {"boundary": BOUNDARY}}
    blocks = BZ.boundary_blocks(tile, dico, ["ZZZZ"],
                                dict(PROVIDER, max_zl=19), _probe({19}))
    squares = COVER.region_squares(BOUNDARY, LAT, LON, 19)
    assert len(blocks) == 4 * len(squares)
    assert {(x // 2 // 16 * 16, y // 2 // 16 * 16) for x, y in blocks} == squares


def test_the_ortho_dico_textures_the_boundary_finest(tmp_path, monkeypatch):
    apt = tmp_path / "Data.apt"
    with open(apt, "wb") as f:
        pickle.dump({"ZZZZ": {"key_type": "icao", "boundary": BOUNDARY}}, f)
    monkeypatch.setattr(FNAMES, "apt_file", lambda tile: str(apt))
    monkeypatch.setattr(BZ, "_provider", lambda code: PROVIDER)
    monkeypatch.setattr(BZ, "_probe_tile", _probe({19}))
    tile = _tile()
    dico = DSF.zone_list_to_ortho_dico(tile)
    inside = COVER.region_squares(BOUNDARY, LAT, LON, 19)
    assert {dico[sq][2] for sq in inside} == {19}
    zooms = {v[2] for k, v in dico.items() if k not in inside}
    assert zooms == {16, 18}          # the cover keeps cover_zl, the rest 16
    names = tile.airport_boundary_textures
    assert len(names) == len(inside)
    assert all(n.endswith("_FAKE19.dds") for n in names)
    # off: the boundary rule follows the airport cover setting
    tile = _tile(cover_airports_with_highres="False")
    assert {v[2] for v in DSF.zone_list_to_ortho_dico(tile).values()} == {16}
    assert tile.airport_boundary_textures == []


def test_a_zone_of_another_provider_keeps_its_own_level(tmp_path, monkeypatch):
    apt = tmp_path / "Data.apt"
    with open(apt, "wb") as f:
        pickle.dump({"ZZZZ": {"key_type": "icao", "boundary": BOUNDARY}}, f)
    monkeypatch.setattr(FNAMES, "apt_file", lambda tile: str(apt))
    monkeypatch.setattr(BZ, "_provider", lambda code: PROVIDER)
    monkeypatch.setattr(BZ, "_probe_tile", _probe({19}))
    zone = [LAT + 0.4, LON + 0.4, LAT + 0.4, LON + 0.6, LAT + 0.6, LON + 0.6,
            LAT + 0.6, LON + 0.4, LAT + 0.4, LON + 0.4]
    tile = _tile(zone_list=[(zone, 17, "OTHER")])
    dico = DSF.zone_list_to_ortho_dico(tile)
    inside = COVER.region_squares(BOUNDARY, LAT, LON, 19)
    assert {dico[sq][3] for sq in inside} == {"OTHER"}
    assert {dico[sq][2] for sq in inside} == {18}
    assert tile.airport_boundary_textures == []


def test_boundary_squares_go_low_res_last_with_the_favorites(tmp_path):
    conn = INDEX.open_index(str(tmp_path / "index.sqlite"))
    for name, near in (("a.dds", 0.0), ("b.dds", 1.0), ("c.dds", 2.0),
                       ("d.dds", 3.0)):
        INDEX.upsert(conn, {"tile": "+40+010", "name": name,
                            "state": "upgraded", "last_near_at": near,
                            "build_dir": str(tmp_path), "tier_px": 4096})
    assert INDEX.set_core(conn, "+40+010", ["b.dds"], ["a.dds"]) == 2
    got = {r["name"]: r["core"] for r in INDEX.rows(conn)}
    assert got == {"a.dds": INDEX.BOUNDARY_CORE, "b.dds": 1, "c.dds": 0,
                   "d.dds": 0}
    assert len(INDEX.rows(conn, core=True)) == 2
    assert len(INDEX.rows(conn, core=False)) == 2
    order = [r["name"] for r in INDEX.lru_order(conn)]
    assert order == ["c.dds", "d.dds", "b.dds", "a.dds"]
    assert BUDGET._tier_of({"pinned": 0, "core": INDEX.BOUNDARY_CORE}) == \
        BUDGET.CLEAR_TIERS.index("favorite")
    conn.close()


def test_the_imagery_record_names_the_boundary_squares(tmp_path, monkeypatch):
    record = {"airport_boundary_textures": ["1_2_FAKE19.dds"]}
    monkeypatch.setattr(TINFO, "read_imagery_record",
                        lambda build_dir, lat, lon: record)
    assert CORES.boundary_names(str(tmp_path), LAT, LON) == ["1_2_FAKE19.dds"]
    record = {}
    assert CORES.boundary_names(str(tmp_path), LAT, LON) == []

