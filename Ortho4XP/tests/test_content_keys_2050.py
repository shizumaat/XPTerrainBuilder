"""#2050 (owner RULINGS 2026-11-13o): downloaded data rarely changes, so
nothing is re-fetched, re-stamped or rebuilt unless its CONTENT changed.

Twins for the parts not covered beside their modules
(``test_auto_patch_freshness`` holds the patch gate's OSM and DEM keys,
``test_step_reuse`` the step keys, ``test_fetch_cache_predicates`` the
inset completion stamp, ``test_approach_rings`` the ring index):

* ``osm_content`` — the box digest is id- and order-free and reads only
  the box; the whole-layer digest likewise;
* an inset re-fetch equal to the cached raster keeps the cached file (and
  its mtime) and is noted for the refresh ledger; a different one lands;
* the harness turns the noted paths into the ledger's ``unchanged``;
* the OSM region index is not asked again before the user's expiry.
"""
import os
import sys
from pathlib import Path

import pytest

import O4_Airport_Elevation_Insets as INSETS
from auto_patch_v2.airport import osm as OSM
from auto_patch_v2.airport import osm_content as OC
from elevation_access import raster_same
from test_inset_fetch_scratch import _corpus, _inset_dir, requires_gdal
from test_inset_resolution_ladder import BOX, _write_raster

HARNESS = Path(__file__).resolve().parent.parent / "tools" / "harness"


def _way(wid, tags, pts):
    return OSM.RawWay(wid, tuple(pts), tags)


def test_the_box_digest_ignores_ids_and_order():
    a = _way("x:-1", {"aeroway": "taxiway"}, [(1.0, 2.0), (1.1, 2.0)])
    b = _way("x:-2", {"aeroway": "apron"}, [(1.2, 2.0), (1.3, 2.0)])
    a2 = _way("y:-900", dict(a.tags), a.points)
    b2 = _way("y:-901", dict(b.tags), b.points)
    one = OC.docs_content({"airports": OSM.OsmDoc("airports", (a, b), ())},
                          1.0, 2.0, 0.05)
    two = OC.docs_content({"airports": OSM.OsmDoc("airports", (b2, a2), ())},
                          1.0, 2.0, 0.05)
    assert one == two
    moved = _way("z", {"aeroway": "taxiway"}, [(1.0, 2.0), (1.1, 2.0001)])
    three = OC.docs_content(
        {"airports": OSM.OsmDoc("airports", (moved, b), ())}, 1.0, 2.0, 0.05)
    assert three != one
    assert OC.changed_feeds(one, three) == ["airports"]
    assert OC.parse_stamp(one)[:3] == (1.0, 2.0, 0.05)
    assert "airports" in OC.describe(one, three)


def _layer(path, nodes, ways):
    import bz2
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<osm>"]
    lines += [f'  <node id="{i}" lat="{la}" lon="{lo}"/>' for i, la, lo in nodes]
    for wid, refs, tags in ways:
        lines.append(f'  <way id="{wid}">')
        lines += [f'    <nd ref="{r}"/>' for r in refs]
        lines += [f'    <tag k="{k}" v="{v}"/>' for k, v in tags]
        lines.append("  </way>")
    lines.append("</osm>")
    path.write_bytes(bz2.compress("\n".join(lines).encode()))


def test_the_layer_digest_is_id_free(tmp_path):
    p1, p2, p3 = (tmp_path / f"{n}.osm.bz2" for n in "abc")
    _layer(p1, [(-1, 1, 2), (-2, 1, 3)], [(-1, [-1, -2], [("aeroway", "apron")])])
    _layer(p2, [(-7, 1, 3), (-8, 1, 2)], [(-9, [-8, -7], [("aeroway", "apron")])])
    _layer(p3, [(-1, 1, 2), (-2, 1, 4)], [(-1, [-1, -2], [("aeroway", "apron")])])
    assert OC.layer_content_digest(str(p1)) == OC.layer_content_digest(str(p2))
    assert OC.layer_content_digest(str(p1)) != OC.layer_content_digest(str(p3))
    assert OC.layer_content_digest(str(tmp_path / "none.osm.bz2")) is None


@pytest.fixture
def valued_strategy(monkeypatch, tmp_path):
    """A provider that answers the raster ``plan["fraction"]`` describes."""
    from elevation_access import definitions as ea_definitions
    from elevation_access import fetch_scratch
    from elevation_access import registry as ea_registry
    name = "fake_2050"
    plan = {"fraction": 1.0}

    @ea_registry.register_access_strategy(name)
    class _Fake:
        def discover(self, definition, bounding_box_wgs84):
            return [{"source_id": "s1"}]

        def fetch(self, definition, bounding_box_wgs84, target_resolution_m,
                  destination_path):
            _write_raster(destination_path, plan["fraction"])
            return {"provider": definition["code"],
                    "native_resolution_m": 1.0,
                    "resolution_m": target_resolution_m,
                    "sources_used": [{"source_id": "s1"}]}

    definition = {"code": "FAKE2050", "access_strategy": name,
                  "role": ea_definitions.ROLE_AIRPORT_INSET, "enabled": True,
                  "priority": 1.0, "native_resolution_m": 1.0}
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"FAKE2050": definition})
    monkeypatch.setenv(fetch_scratch.SCRATCH_ENV, str(tmp_path / "scratch"))
    monkeypatch.setattr(raster_same, "_KEPT", [])
    try:
        yield plan, definition
    finally:
        ea_registry.ACCESS_STRATEGIES.pop(name, None)


@requires_gdal
def test_a_refetch_of_the_same_raster_keeps_the_cached_file(
        tmp_path, monkeypatch, valued_strategy):
    plan, definition = valued_strategy
    _corpus(tmp_path, monkeypatch)
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None)
    cached = os.path.join(_inset_dir(), "KASE_fake2050.tif")
    assert os.path.isfile(cached)
    os.utime(cached, (1_000_000, 1_000_000))
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None,
                                 refresh=True)
    assert os.stat(cached).st_mtime == 1_000_000          # kept, untouched
    assert raster_same.kept_unchanged() == [cached]
    plan["fraction"] = 0.5                                # the data moved
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [definition], None,
                                 refresh=True)
    assert os.stat(cached).st_mtime != 1_000_000
    assert raster_same.kept_unchanged() == [cached]


@requires_gdal
def test_same_raster_reads_values_not_bytes(tmp_path):
    a, b, c = (str(tmp_path / f"{n}.tif") for n in "abc")
    _write_raster(a, 1.0)
    _write_raster(b, 1.0)
    _write_raster(c, 0.5)
    assert raster_same.same_raster(a, b)
    assert not raster_same.same_raster(a, c)
    assert not raster_same.same_raster(a, str(tmp_path / "missing.tif"))


def test_the_ledger_names_the_kept_rasters_relative_to_the_repo(
        tmp_path, monkeypatch):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import build_airport as BA
    repo = tmp_path / "repo"
    kept = repo / "Elevation_data" / "+30-110" / "N39W105_airport_insets" / "K.tif"
    kept.parent.mkdir(parents=True)
    kept.write_bytes(b"x")
    monkeypatch.setattr(BA, "DATA_REPO", repo)
    monkeypatch.setattr(raster_same, "_KEPT",
                        [str(kept), str(kept), str(tmp_path / "elsewhere.tif")])
    assert BA.refetched_unchanged() == [
        "Elevation_data/+30-110/N39W105_airport_insets/K.tif"]


def test_the_osm_region_index_waits_for_the_users_expiry(tmp_path,
                                                         monkeypatch):
    import time

    import O4_OSM_Extracts as EXTRACTS
    index = tmp_path / "index-v1.json"
    index.write_text("{}", encoding="utf-8", newline="")
    monkeypatch.setattr(EXTRACTS, "_index_path", lambda: str(index))
    monkeypatch.setattr(EXTRACTS, "_extract_refresh_days", lambda: 180.0)
    old = time.time() - 30 * 86400            # past the old 7-day check
    os.utime(index, (old, old))
    assert EXTRACTS._index_is_stale() is False
    older = time.time() - 181 * 86400
    os.utime(index, (older, older))
    assert EXTRACTS._index_is_stale() is True
    index.unlink()
    assert EXTRACTS._index_is_stale() is True
