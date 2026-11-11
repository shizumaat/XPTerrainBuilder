"""Twins for the export window's honest estimates (#2014 follow-up; owner
2026-11-11T16:45Z: "The estimates for LAX seem too similar … is that
taking into account estimated download times?"), on
``test_tile_package``'s two synthetic machines:

* the three kinds differ the way a recipient's build does: a whole tile
  downloads only imagery, an exact match its other airports' elevation,
  a patch-only package all the map and elevation data — in bytes and in
  time, each with its breakdown;
* a left-out file costs what its SOURCE costs to fetch
  (``tile_bundle.source_bytes``): the Overpass wire bytes, a recorded
  fetch, overlapping sources;
* the airports are priced from their recorded finishes on this
  machine's cores, else from the tile's recorded airport phase
  (``tile_bundle.recipient_time``).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import tile_time_model as MODEL  # noqa: E402
from test_tile_package import INSETS, LAT, LON, machines  # noqa: E402,F401
from tile_bundle import estimate as ESTIMATE  # noqa: E402
from tile_bundle import recipient_time as RTIME  # noqa: E402
from tile_bundle import source_bytes as SRC  # noqa: E402


def test_the_kinds_differ_the_way_a_recipients_build_does(machines):  # noqa: F811
    a, _b = machines
    a.write(INSETS + "HEAZ_copernicusglo30.json", json.dumps({"sources_used": 3}).encode())
    rows = {r["kind"]: r for r in ESTIMATE.estimate([(LAT, LON)], "HECA")["kinds"]}
    tile, exact, patch = rows["tile"], rows["exact"], rows["patch"]
    assert tile["download_bytes"] == 0 < exact["download_bytes"] < patch["download_bytes"]
    assert tile["build_seconds"] < exact["build_seconds"] < patch["build_seconds"]
    assert tile["build_low"] < tile["build_seconds"] < tile["build_high"]
    steps = {k: [s["step"] for s in r["breakdown"]] for k, r in rows.items()}
    assert steps == {"tile": ["airports"], "exact": ["elevation", "airports"],
                     "patch": ["map", "elevation", "airports"]}
    assert "recipient downloads only imagery" in tile["figures"]
    assert "at 2 MB/s" in patch["figures"] and "map data" in patch["figures"]
    assert exact["figures"].count("\n") == 1          # the breakdown line
    assert "other airports" in exact["still_needs"][0]["text"]


def test_a_left_out_file_costs_its_source(tmp_path):
    def put(rel, size, sidecar=None):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        if sidecar is not None:
            path.with_suffix(".json").write_bytes(json.dumps(sidecar).encode("utf-8"))
        return "data/" + rel, str(path)
    osm = put("OSM_data/+30+030/+30+031/+30+031_roads.osm.bz2", 1000)
    fetched = put("Elevation_data/+30+030/N30E031_airport_insets/A_x.tif", 100,
                  {"bytes_fetched": 5000})
    mosaic = put("Elevation_data/+30+030/N30E031_approach_rings/c.tif", 100,
                 {"sources_used": 3})
    base = put("Elevation_data/+30+030/N30E031.hgt", 700)
    left = SRC.left_out([osm, fetched, mosaic, base])
    assert {k: v["source_bytes"] for k, v in left.items()} == {
        "osm": int(1000 * SRC.OSM_WIRE_RATIO), "inset": 5000, "ring": 200, "base": 700}
    assert {k: v["bytes"] for k, v in left.items()} == {
        "osm": 1000, "inset": 100, "ring": 100, "base": 700}
    rows = RTIME.acquisition_rows(left, rate=10.0)
    assert [r["step"] for r in rows] == ["map", "elevation"]
    assert rows[0]["download_seconds"] >= SRC.OVERPASS_SECONDS_PER_LAYER


def test_airports_are_priced_from_their_recorded_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(MODEL, "STORE_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    MODEL.record_build(LAT, LON, {"airports": 3, "autopatch_seconds": 700.0},
                       {"vector": 760.0})
    row = next(r for r in RTIME.processing_rows(LAT, LON) if r["step"] == "airports")
    assert row["seconds"] == 700.0 and "as recorded here" in row["label"]
    MODEL.record_build(LAT, LON, {"airports": 3, "autopatch_seconds": 700.0,
                                  "airport_seconds": {"A": 600.0, "B": 300.0,
                                                      "C": 290.0}},
                       {"vector": 760.0})
    row = next(r for r in RTIME.processing_rows(LAT, LON) if r["step"] == "airports")
    assert row["seconds"] == 600.0                    # A alone; B and C share a core
    assert "longest A" in row["label"]
