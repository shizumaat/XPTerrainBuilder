"""R17-2 — THE DECLARED CAUSEWAY CORRIDOR (owner ruling 2026-08-11).

The owner declared the corridor between VHHH and the island to its EAST
(lat 22.3125624–22.3145276, lon 113.9426422–113.9469981) flat at the
airport's Z0, LAND, and walled on both long edges.  Open water OUTSIDE
the declared box stays sea — R8-1's channel ruling stands everywhere
else, which is why the declaration is a BOX LIST and never a grown
extent.

Three authorities, one declaration:

* ELEVATION — the box takes a flat-site constant inset at the airport's
  Z0 (``flat_site_mode`` hands it to ``overlay_flat_site_insets``);
* LAND — the box's ring is inserted with ``PATCH_RING_MARKER`` and joins
  ``patches_area``, so no sea flood and no sea seed crosses it;
* WALLS — the box joins the R17-3 admission union.

Headless: parser fixtures plus a synthetic patch dir; no network, no
DEM, no tile build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402
from auto_patch import flat_site as FS  # noqa: E402
from auto_patch import flat_site_mode as FSM  # noqa: E402

OWNER_BOX = (22.3125624, 113.9426422, 22.3145276, 113.9469981)
OWNER_DECL = ("VHHH:22.3125624,113.9426422,22.3145276,113.9469981")


class TestDeclarationParser:
    def test_the_owners_box_parses_exactly(self):
        assert FS.declared_flat_corridors(OWNER_DECL) == {"VHHH": [OWNER_BOX]}

    def test_several_corridors_and_airports(self):
        parsed = FS.declared_flat_corridors(
            OWNER_DECL + ";VHHH:22.0,113.0,22.1,113.1;VMMC:22.2,113.5,"
            "22.3,113.6")
        assert len(parsed["VHHH"]) == 2
        assert parsed["VMMC"] == [(22.2, 113.5, 22.3, 113.6)]

    def test_corners_are_normalised(self):
        parsed = FS.declared_flat_corridors(
            "VHHH:22.3145276,113.9469981,22.3125624,113.9426422")
        assert parsed == {"VHHH": [OWNER_BOX]}

    def test_malformed_entries_are_skipped_never_raised(self):
        parsed = FS.declared_flat_corridors(
            "nonsense;VHHH:1,2,3;VHHH:a,b,c,d;VHHH:22.0,113.0,22.0,113.1;"
            + OWNER_DECL)
        # A degenerate box (zero span) is not a corridor either.
        assert parsed == {"VHHH": [OWNER_BOX]}

    def test_no_declaration_is_an_empty_map(self):
        assert FS.declared_flat_corridors("") == {}

    def test_tile_degree_conversion_matches_the_extent_contract(self):
        assert FS.corridor_bounds_tile_degrees(OWNER_BOX, 22, 113) == (
            OWNER_BOX[1] - 113, OWNER_BOX[0] - 22,
            OWNER_BOX[3] - 113, OWNER_BOX[2] - 22)


class TestTheTileCfgIsTheDeliveryVehicle:
    """A per-tile cfg value lands on the ``Tile`` INSTANCE, never on the
    config module — so a corridor written into ``Ortho4XP_+22+113.cfg``
    is invisible to a module-level reader (``flat_site_declared`` has
    exactly that hole).  Every corridor consumer holds the tile."""

    def test_the_key_is_registered_as_a_tile_var(self):
        import O4_Cfg_Vars as CV
        assert "flat_site_declared_corridors" in CV.cfg_vars
        assert "flat_site_declared_corridors" in CV.list_tile_vars
        assert CV.cfg_vars["flat_site_declared_corridors"]["default"] == ""

    def test_the_tiles_own_value_wins_over_the_module(self, monkeypatch):
        import O4_Config_Utils as CFG
        monkeypatch.setattr(CFG, "flat_site_declared_corridors", "",
                            raising=False)
        tile = _Tile()
        assert FS.corridors_for_tile(tile) == {}
        tile.flat_site_declared_corridors = OWNER_DECL
        assert FS.corridors_for_tile(tile) == {"VHHH": [OWNER_BOX]}

    def test_the_global_config_still_works_for_a_tileless_caller(
            self, monkeypatch):
        import O4_Config_Utils as CFG
        monkeypatch.setattr(CFG, "flat_site_declared_corridors", OWNER_DECL,
                            raising=False)
        assert FS.corridors_for_tile(None) == {"VHHH": [OWNER_BOX]}
        assert FS.corridors_for_tile(_Tile()) == {"VHHH": [OWNER_BOX]}

    def test_a_real_tile_cfg_file_round_trips(self, tmp_path, monkeypatch):
        """The owner's delivery: the line in the tile cfg, read by the
        engine's own loader, reaching the corridor parser."""
        import O4_Config_Utils as CFG
        import O4_File_Names as FNAMES
        build = tmp_path / "zOrtho4XP_+22+113"
        build.mkdir()
        (build / ("Ortho4XP_" + FNAMES.short_latlon(22, 113) + ".cfg")
         ).write_text("flat_site_declared_corridors=" + OWNER_DECL + "\n")
        tile = CFG.Tile(22, 113, str(build))
        assert tile.read_from_config() == 1
        assert FS.corridors_for_tile(tile) == {"VHHH": [OWNER_BOX]}


class TestSubstitutionBoxes:
    def test_only_corridors_on_this_tile_are_returned(self, monkeypatch):
        monkeypatch.setattr(FS, "declared_flat_corridors",
                            lambda value=None: {"VHHH": [
                                OWNER_BOX, (40.0, 5.0, 40.1, 5.1)]})
        boxes = FSM._declared_corridor_boxes("VHHH", 22, 113)
        assert len(boxes) == 1
        assert boxes[0]["corridor_wgs84"] == list(OWNER_BOX)

    def test_an_airport_without_a_declaration_gets_none(self, monkeypatch):
        monkeypatch.setattr(FS, "declared_flat_corridors",
                            lambda value=None: {"VHHH": [OWNER_BOX]})
        assert FSM._declared_corridor_boxes("VMMC", 22, 113) == []


# ── the LAND authority: the ring, the cutter, the seeds ──────────────


class _DEM:
    """Flat Z0 stand-in — what the corridor's own inset leaves behind."""

    def alt_vec(self, way):
        return numpy.full((len(way), 1), 7.315)


class _Tile:
    def __init__(self, lat=22, lon=113):
        self.lat = lat
        self.lon = lon
        self.dem = _DEM()
        self.auto_patch = "All"


def _run(tmp_path, monkeypatch, declaration):
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    monkeypatch.setattr(VMAP.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(FS, "declared_flat_corridors",
                        lambda value=None: declaration)
    vector_map = VECT.Vector_Map()
    tile = _Tile()
    (patches_area, _list, graded_area) = VMAP.include_patches(
        vector_map, tile)
    return vector_map, patches_area, graded_area


def _corridor_point(box, dlat=0.5, dlon=0.5):
    lat = box[0] + (box[2] - box[0]) * dlat
    lon = box[1] + (box[3] - box[1]) * dlon
    return geometry.Point(lon - 113, lat - 22)


class TestCorridorIsLand:
    def test_the_corridor_joins_the_land_cutter_and_the_wall_set(
            self, tmp_path, monkeypatch):
        _vm, patches_area, graded_area = _run(
            tmp_path, monkeypatch, {"VHHH": [OWNER_BOX]})
        inside = _corridor_point(OWNER_BOX)
        assert patches_area.contains(inside)
        assert graded_area.contains(inside)

    def test_the_ring_carries_the_full_flood_stopping_marker(
            self, tmp_path, monkeypatch):
        vector_map, _pa, _ga = _run(
            tmp_path, monkeypatch, {"VHHH": [OWNER_BOX]})
        markers = {vector_map.data_edges[e] for e in vector_map.edges_dico}
        assert markers == {VMAP.PATCH_RING_MARKER}
        # and the interior is seeded INTERP_ALT so the mesh takes the
        # patch elevation inside the box.
        assert set(vector_map.seeds) == {"INTERP_ALT"}

    def test_the_ring_takes_the_corridors_own_dem_level(
            self, tmp_path, monkeypatch):
        vector_map, _pa, _ga = _run(
            tmp_path, monkeypatch, {"VHHH": [OWNER_BOX]})
        assert set(vector_map.data_nodes.values()) == {7.315}

    def test_open_water_outside_the_box_stays_sea(
            self, tmp_path, monkeypatch):
        """The R8-1 channel ruling: a point in the channel NORTH of the
        declared corridor is not land, is not walled, and still takes a
        sea seed."""
        _vm, patches_area, graded_area = _run(
            tmp_path, monkeypatch, {"VHHH": [OWNER_BOX]})
        # 200 m north of the corridor's north edge, inside the channel.
        north = geometry.Point(
            (OWNER_BOX[1] + OWNER_BOX[3]) / 2 - 113,
            OWNER_BOX[2] + 0.0018 - 22)
        assert not patches_area.contains(north)
        assert not graded_area.contains(north)
        sea = geometry.Polygon([
            (0.93, 0.30), (0.96, 0.30), (0.96, 0.33), (0.93, 0.33)])
        seed = VMAP.sea_seed_areas(
            VECT.ensure_MultiPolygon(sea), geometry.Polygon(),
            patch_pavement_area=patches_area)
        assert seed.contains(north)

    def test_no_declaration_changes_nothing(self, tmp_path, monkeypatch):
        vector_map, patches_area, graded_area = _run(
            tmp_path, monkeypatch, {})
        assert patches_area.is_empty
        assert graded_area.is_empty
        assert not vector_map.edges_dico

    def test_a_corridor_declared_on_another_tile_is_not_inserted(
            self, tmp_path, monkeypatch):
        _vm, patches_area, _ga = _run(
            tmp_path, monkeypatch, {"VHHH": [(40.0, 5.0, 40.1, 5.1)]})
        assert patches_area.is_empty
