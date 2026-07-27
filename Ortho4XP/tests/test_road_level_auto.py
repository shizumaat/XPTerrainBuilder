"""Auto road-smoothing mode (owner ruling 2026-07-27).

``road_level="auto"`` = level 1 tile-wide + full level-5 roads and the
airport rail classes fetched ONLY inside the airport elevation-inset
bounding boxes.  These tests cover the setting resolver, the inset-bbox
harvesting and the merged per-tile cache — headless, no network (the
Overpass call is monkeypatched).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402


class _Tile:
    lat = 35
    lon = -81

    def __init__(self, road_level):
        self.road_level = road_level


# ── resolver ─────────────────────────────────────────────────────────


def test_auto_resolves_to_level_one_plus_auto():
    assert VMAP.resolved_road_level(_Tile("auto")) == (1, True)
    assert VMAP.resolved_road_level(_Tile("AUTO ")) == (1, True)


def test_numeric_strings_and_ints_keep_tile_wide_levels():
    assert VMAP.resolved_road_level(_Tile("0")) == (0, False)
    assert VMAP.resolved_road_level(_Tile("5")) == (5, False)
    assert VMAP.resolved_road_level(_Tile(2)) == (2, False)


def test_garbage_reads_as_auto_not_crash():
    assert VMAP.resolved_road_level(_Tile("banana")) == (1, True)
    assert VMAP.resolved_road_level(_Tile(None)) == (1, True)


def test_missing_attribute_reads_as_auto():
    class _Bare:
        lat = 0
        lon = 0
    assert VMAP.resolved_road_level(_Bare()) == (1, True)


# ── inset-bbox layer ─────────────────────────────────────────────────


def _write_inset(dir_path: Path, stem: str, bbox_lonlat):
    (dir_path / f"{stem}.tif").write_bytes(b"")
    (dir_path / f"{stem}.json").write_text(json.dumps(
        {"bounding_box_wgs84": bbox_lonlat}), encoding="utf-8")


def test_auto_layer_queries_each_inset_bbox_and_caches(
        tmp_path, monkeypatch):
    inset_dir = tmp_path / "insets"
    inset_dir.mkdir()
    _write_inset(inset_dir, "A_usgs3dep", [-80.9, 35.1, -80.8, 35.2])
    _write_inset(inset_dir, "B_usgs3dep", [-80.5, 35.4, -80.4, 35.5])
    # A sidecar without a bbox must be skipped, not crash.
    (inset_dir / "C_usgs3dep.tif").write_bytes(b"")
    (inset_dir / "C_usgs3dep.json").write_text("{}", encoding="utf-8")

    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [
            str(inset_dir / "A_usgs3dep.tif"),
            str(inset_dir / "B_usgs3dep.tif"),
            str(inset_dir / "C_usgs3dep.tif"),
        ])
    cache_path = tmp_path / "+35-081_airport_small_roads.osm.bz2"
    monkeypatch.setattr(
        FNAMES, "osm_cached",
        lambda lat, lon, suffix: str(cache_path))

    seen_bboxes = []

    def _fake_query(queries, bbox, layer, tags_of_interest=None,
                    cached_file_name=""):
        seen_bboxes.append(bbox)
        # level-5 road classes and the airport rail classes must all be
        # in the query set
        joined = ";".join(queries)
        assert '"highway"="track"' in joined
        assert '"highway"="service"' in joined
        assert '"railway"="siding"' in joined
        return 1

    written = []
    monkeypatch.setattr(VMAP.OSM, "OSM_query_to_OSM_layer", _fake_query)

    class _FakeLayer:
        def update_dicosm(self, *a, **k):
            raise AssertionError("no cache exists yet — must query")

        def write_to_file(self, path):
            written.append(path)
            Path(path).write_bytes(b"x")

    monkeypatch.setattr(VMAP.OSM, "OSM_layer", _FakeLayer)

    layer = VMAP._airport_auto_roads_layer(_Tile("auto"))
    assert layer is not None
    # bbox order is (lat_min, lon_min, lat_max, lon_max) — the Overpass
    # convention get_overpass_data expects.
    assert seen_bboxes == [(35.1, -80.9, 35.2, -80.8),
                           (35.4, -80.5, 35.5, -80.4)]
    assert written == [str(cache_path)]


def test_auto_layer_recycles_merged_cache(tmp_path, monkeypatch):
    inset_dir = tmp_path / "insets"
    inset_dir.mkdir()
    _write_inset(inset_dir, "A_usgs3dep", [-80.9, 35.1, -80.8, 35.2])

    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [
            str(inset_dir / "A_usgs3dep.tif")])
    cache_path = tmp_path / "+35-081_airport_small_roads.osm.bz2"
    cache_path.write_bytes(b"cached")
    monkeypatch.setattr(
        FNAMES, "osm_cached",
        lambda lat, lon, suffix: str(cache_path))

    recycled = []

    class _FakeLayer:
        def update_dicosm(self, path, input_tags, target_tags):
            recycled.append(path)

        def write_to_file(self, path):        # pragma: no cover
            raise AssertionError("cache hit must not re-write")

    monkeypatch.setattr(VMAP.OSM, "OSM_layer", _FakeLayer)
    monkeypatch.setattr(
        VMAP.OSM, "OSM_query_to_OSM_layer",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("cache hit must not query")))

    layer = VMAP._airport_auto_roads_layer(_Tile("auto"))
    assert layer is not None
    assert recycled == [str(cache_path)]


def test_auto_layer_none_without_insets(monkeypatch):
    import O4_Airport_Elevation_Insets as INSETS
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [])
    assert VMAP._airport_auto_roads_layer(_Tile("auto")) is None
