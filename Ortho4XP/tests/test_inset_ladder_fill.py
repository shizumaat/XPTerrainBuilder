"""HOLES FILL DOWN THE LADDER (spec las-tile-lidar-provider §12, owner
RULINGS 2026-10-01d; #154 / #153 follow-up).

"If the best option is a 42% coverage at 1m, do we then fill the gaps with
the next available, like the 10m?  Obviously can't have areas with no
data."  A NoData cell inside a delivered inset takes the value of the
finest coarser covering rung that holds data there -- 3 m, then 10 m --
before the bake ever reaches the tile's base DEM; every hole edge is
feathered by the one ``feather_weight``; islands under
``INSET_HOLE_MIN_CELLS`` stay NoData for the bake.  No network: fake
rasters in ``tmp_path``.
"""

import json
import os

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

NODATA = INSETS.LADDER_INSET_NODATA

#: 600 m x 600 m at Aspen's latitude.
SOUTH, NORTH = 39.2000, 39.2000 + 600.0 / INSETS.GEO.lat_to_m
WEST = -106.9000
EAST = WEST + 600.0 / INSETS.GEO.lon_to_m((SOUTH + NORTH) / 2.0)
BOX = (WEST, SOUTH, EAST, NORTH)


def _write(path, size, values):
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((WEST, (EAST - WEST) / size, 0.0, NORTH, 0.0,
                             -(NORTH - SOUTH) / size))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None
    return str(path)


def _read(path):
    dataset = gdal.Open(str(path))
    values = dataset.GetRasterBand(1).ReadAsArray().astype(numpy.float64)
    dataset = None
    return values


THREE = {"provider": "USGS3DEP", "rung": 4, "label": "1/9 arc-second"}
TEN = {"provider": "USGS3DEP", "rung": 5, "label": "1/3 arc-second"}


def _plane(rows, cols):
    """The core's measured surface: 101 m rising 1 mm per cell east."""
    return 101.0 + 0.001 * numpy.arange(cols)[None, :] + numpy.zeros(
        (rows, 1))


def _void_case(tmp_path):
    """A 1 m core (600 x 600) on a plane, with
    * hole A: its east 40 % missing (an EDGE island: a partial mosaic),
    * hole B: a south-edge notch where the 3 m has no data either,
    * hole C: a 60 x 60 building void ringed by lidar (INTERIOR),
    * a 2-cell interior roof void;
    a 3 m fill (100 m) everywhere but under hole B, a 10 m fill (99 m)."""
    core = _plane(600, 600)
    core[:, 360:] = NODATA                    # A: 144,000 cells = 40 %
    core[560:, 100:200] = NODATA              # B: 4,000 cells
    core[200:260, 100:160] = NODATA           # C: 3,600 cells
    core[20, 20:22] = NODATA                  # 2-cell roof void
    three = numpy.full((200, 200), 100.0)
    three[180:, 30:70] = NODATA               # no 3 m over hole B
    ten = numpy.full((60, 60), 99.0)
    return (_write(tmp_path / "core.tif", 600, core),
            _write(tmp_path / "three.tif", 200, three),
            _write(tmp_path / "ten.tif", 60, ten))


def test_edge_holes_fill_down_the_ladder_interior_ones_interpolate(
        tmp_path):
    """Acceptance §12 (1) with the spec-author refinement: every cell
    valid; the EDGE void (40 %) is filled from 3 m and its seam feathered,
    the 10 m-only edge notch names 10 m; the INTERIOR building void and
    the roof void interpolate from the core's own ring
    (``core_interpolation``) -- never from a coarser rung."""
    (core, three, ten) = _void_case(tmp_path)
    out = str(tmp_path / "out.tif")
    record = INSETS.assemble_ladder_inset(
        core, [(three, THREE), (ten, TEN)], out, feather_m=60.0,
        core_region_is_box=True)
    values = _read(out)
    assert int((values == NODATA).sum()) == 0          # every cell valid
    assert (record["islands"], record["interior_islands"],
            record["edge_islands"]) == (4, 2, 2)
    assert record["sub_threshold_voids"] == 1
    assert record["sub_threshold_cells"] == 2
    assert record["interpolation_left_cells"] == 0
    rows = {row["cells"]: row for row in record["holes"]}
    assert sorted(rows) == [3600, 4000, 144000]       # >= hole_min_cells
    hole_a, hole_b, hole_c = rows[144000], rows[4000], rows[3600]
    assert hole_a["kind"] == "edge" and hole_a["filled_by"] == THREE
    assert hole_a["unfilled_cells"] == 0
    assert hole_a["area_m2"] == pytest.approx(144000.0, rel=0.02)
    assert hole_a["seam_median_m"] == pytest.approx(1.36, abs=0.05)
    assert hole_b["kind"] == "edge" and hole_b["filled_by"] == TEN
    assert hole_c["kind"] == "interior"
    assert hole_c["filled_by"] == INSETS.HOLE_FILLED_BY_CORE_INTERPOLATION
    # the building pad reads its own lidar ring, not the 3 m / 10 m
    assert hole_c["fill_median_m"] == pytest.approx(
        hole_c["ring_median_m"], abs=0.05)
    assert values[230, 130] == pytest.approx(101.13, abs=0.05)
    assert values[20, 20] == pytest.approx(101.02, abs=0.01)
    assert values[300, 500] == pytest.approx(100.0)       # 3 m inside A
    assert values[590, 150] == pytest.approx(99.0)        # 10 m inside B
    assert values[5, 5] == pytest.approx(101.005)         # the core
    # FEATHERED: across hole A's west edge the core ramps to the fill
    # over 60 m with no cliff
    transect = values[300, 280:400]
    assert numpy.max(numpy.abs(numpy.diff(transect))) <= 0.05
    assert record["filled_fraction"] == 1.0
    assert record["unanswered_cells"] == 0
    (west, south, east, north) = hole_c["bounding_box_wgs84"]
    assert WEST < west < east < EAST and SOUTH < south < north < NORTH


def test_interior_voids_alone_need_no_fill(tmp_path):
    """A core whose only voids are interior (KASE's 291 building
    islands): nothing is fetched, the voids interpolate."""
    core = _plane(600, 600)
    core[200:260, 100:160] = NODATA
    core[20, 20:22] = NODATA
    path = _write(tmp_path / "core.tif", 600, core)
    assembly = INSETS.LadderInsetAssembly(path, core_region_is_box=True)
    assert not assembly.needs_fill()
    assert assembly.interpolated()
    record = assembly.write(str(tmp_path / "out.tif"))
    assert record["filled_fraction"] == 1.0
    assert record["holes"][0]["filled_by"] == "core_interpolation"


def test_needs_fill_climbs_until_the_box_is_valid(tmp_path):
    (core, three, ten) = _void_case(tmp_path)
    assembly = INSETS.LadderInsetAssembly(core, core_region_is_box=True)
    assert assembly.needs_fill()
    assert assembly.add_fill(three, THREE) > 0
    assert assembly.needs_fill()              # hole B: no 3 m there
    assert assembly.add_fill(ten, TEN) > 0
    assert not assembly.needs_fill()


def test_islands_are_classified_interior_or_edge():
    void = numpy.zeros((20, 20), dtype=bool)
    void[2, 2:5] = True                       # interior, 3 cells
    void[10:12, 10:12] = True                 # interior, 4 cells
    void[15, 15] = void[16, 16] = True        # interior, diagonal: 2
    void[0:3, 18:20] = True                   # touches the box edge
    outside = numpy.zeros((20, 20), dtype=bool)
    outside[7, 0:3] = True                    # beyond the core region
    void[8, 1:3] = True                       # touches it: edge
    (labels, islands) = INSETS.inset_void_islands(void, outside)
    kinds = sorted((island["cells"], island["interior"])
                   for island in islands)
    assert kinds == [(2, False), (2, True), (3, True), (4, True),
                     (6, False)]
    assert int((labels > 0).sum()) == int(void.sum())


# ---------------------------------------------------------------------
# THROUGH THE LADDER: the partial path (30bu, KGEG) delivers its partial
# 1 m rung THROUGH the assembler, the ladder's own coarser rungs as fills.
# ---------------------------------------------------------------------
STRATEGY = "fill_fake_strategy"
OTHER = "fill_fake_other"


@pytest.fixture
def ladder(monkeypatch, tmp_path):
    """FAKE3DEP: 1 m (rung 0) -> FAKEOPR (1 m, airport cover) -> 3 m ->
    10 m.  ``plan[key]`` = ``{"keep": (W,S,E,N) | None, "value": z}`` or
    ``{"unavailable": why}``; a key absent = no product listed."""
    plan = {}
    calls = []

    def _key(definition):
        if definition["code"] == "FAKEOPR":
            return "FAKEOPR"
        return "FAKE3DEP:%g" % definition["native_resolution_m"]

    class _Base:
        def discover(self, definition, bounding_box_wgs84):
            return [{"source_id": _key(definition)}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            key = _key(definition)
            calls.append(key)
            entry = plan.get(key)
            if entry is None:
                self.last_listing = []
                return None
            if entry.get("unavailable"):
                raise INSETS.ProviderUnavailable(entry["unavailable"])
            size = 120
            (west, south, east, north) = bounding_box_wgs84
            values = numpy.full((size, size), NODATA, dtype=numpy.float32)
            keep = entry.get("keep") or bounding_box_wgs84
            xs = west + (numpy.arange(size) + 0.5) * (east - west) / size
            ys = north - (numpy.arange(size) + 0.5) * (north - south) / size
            inside = ((ys >= keep[1]) & (ys <= keep[3]))[:, None] & (
                (xs >= keep[0]) & (xs <= keep[2]))[None, :]
            values[inside] = entry["value"]
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            dataset = gdal.GetDriverByName("GTiff").Create(
                destination_path, size, size, 1, gdal.GDT_Float32)
            dataset.SetGeoTransform((west, (east - west) / size, 0.0,
                                     north, 0.0, -(north - south) / size))
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            dataset.SetProjection(srs.ExportToWkt())
            dataset.GetRasterBand(1).SetNoDataValue(NODATA)
            dataset.GetRasterBand(1).WriteArray(values)
            dataset = None
            return {"provider": definition["code"],
                    "native_resolution_m": definition["native_resolution_m"],
                    "resolution_m": target_resolution_m,
                    "source_ids": [key], "sources_used": [{"source_id": key}]}

    INSETS.register_access_strategy(STRATEGY)(type("_A", (_Base,), {}))
    INSETS.register_access_strategy(OTHER)(type("_B", (_Base,), {}))
    chain = {
        "code": "FAKE3DEP", "access_strategy": STRATEGY,
        "role": INSETS.ROLE_AIRPORT_INSET, "enabled": True, "priority": 1.0,
        "native_resolution_m": 1.0, "ladder_label": "1 meter",
        "discovery_url_template": "rung0",
        "resolution_ladder_rungs": INSETS._parse_resolution_ladder(
            "1|USGS original product resolution|provider:FAKEOPR;"
            "3|1/9 arc-second|rung3;10|1/3 arc-second|rung10"),
    }
    opr = {
        "code": "FAKEOPR", "access_strategy": OTHER,
        "role": INSETS.ROLE_AIRPORT_INSET, "enabled": True, "priority": 0.5,
        "native_resolution_m": 1.0, "ladder_judge": "airport_cover",
    }
    monkeypatch.setattr(INSETS, "elevation_providers_dict",
                        {"FAKE3DEP": chain, "FAKEOPR": opr})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    try:
        yield plan, calls, chain
    finally:
        INSETS.ACCESS_STRATEGIES.pop(STRATEGY, None)
        INSETS.ACCESS_STRATEGIES.pop(OTHER, None)


LADDER_BOX = (-117.56, 47.60, -117.50, 47.64)       # ~4.5 x 4.4 km


def _airport():
    from shapely.geometry import box as _box

    return _box(-117.545, 47.610, -117.515, 47.630)


def _sidecar():
    path = FNAMES.airport_inset_provenance(47, -118, "KGEG", "FAKE3DEP")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_partial_1m_delivers_through_the_assembler_3m_then_10m(ladder):
    """Acceptance §12 (2), synthetic: USGS 1 m covers the west 42 % of
    the airport, OPR is not a rung here (unavailable), the 1/9" holds
    the box but a north strip, 1/3" holds all of it.  Rung 0 is
    delivered (30bu), its holes filled from 3 m where it holds data and
    10 m elsewhere; ``airport_filled_fraction`` 1.0, the core's own
    ``airport_valid_fraction`` kept."""
    plan, calls, chain = ladder
    split = -117.545 + 0.42 * 0.030
    plan.update({
        "FAKE3DEP:1": {"keep": (-117.56, 47.60, split, 47.64),
                       "value": 720.0},
        "FAKEOPR": {"unavailable": "removed from this ladder (twin)"},
        "FAKE3DEP:3": {"keep": (-117.56, 47.60, -117.50, 47.635),
                       "value": 719.0},
        "FAKE3DEP:10": {"value": 718.0},
    })
    INSETS.ensure_airport_insets(47, -118, {"KGEG": LADDER_BOX}, [chain],
                                 None, airport_polygons={"KGEG": _airport()})
    assert calls == ["FAKE3DEP:1", "FAKEOPR", "FAKE3DEP:3", "FAKE3DEP:10"]
    meta = _sidecar()
    ladder_block = meta["ladder"]
    assert ladder_block["delivered_rung"] == 0
    assert [(row["outcome"], row.get("role"))
            for row in ladder_block["rungs_tried"]] == [
        ("delivered", None), ("unavailable", None), ("delivered", "fill"),
        ("delivered", "fill")]
    assert meta["airport_valid_fraction"] == pytest.approx(0.42, abs=0.03)
    assert meta["airport_filled_fraction"] == 1.0
    assert meta["valid_fraction"] == 1.0
    assert [layer["label"] for layer in meta["fills"]["layers"]] == [
        "1/9 arc-second", "1/3 arc-second"]
    assert meta["fills"]["ran_out"] is None
    (hole,) = meta["holes"]
    assert hole["filled_by"]["label"] == "1/9 arc-second"
    assert {row["label"] for row in hole["fill_cells"]} == {
        "1/9 arc-second", "1/3 arc-second"}
    assert hole["unfilled_cells"] == 0
    assert hole["seam_median_m"] == pytest.approx(1.0, abs=0.05)
    summary = INSETS.inset_fill_summary(meta)
    assert INSETS.inset_fill_shortfall(summary) is None
    # The build-time re-check never takes a FILL row for a ladder rung:
    # it re-asks the partial rung's same-resolution alternative (the
    # unavailable OPR, 30bv (2)) and nothing coarser.
    recheck = INSETS.ladder_recheck(47, -118, "KGEG", "FAKE3DEP",
                                    LADDER_BOX, record=False)
    assert recheck["new_source_ids"] == ["FAKEOPR"]


def test_fill_stops_once_the_box_is_valid(ladder):
    plan, calls, chain = ladder
    plan.update({
        "FAKE3DEP:1": {"keep": (-117.56, 47.60, -117.535, 47.64),
                       "value": 720.0},
        "FAKE3DEP:3": {"value": 719.0},
        "FAKE3DEP:10": {"value": 718.0},
    })
    INSETS.ensure_airport_insets(47, -118, {"KGEG": LADDER_BOX}, [chain],
                                 None, airport_polygons={"KGEG": _airport()})
    assert calls == ["FAKE3DEP:1", "FAKEOPR", "FAKE3DEP:3"]
    meta = _sidecar()
    assert [layer["label"] for layer in meta["fills"]["layers"]] == [
        "1/9 arc-second"]
    assert meta["airport_filled_fraction"] == 1.0


def test_a_ladder_that_runs_out_records_the_rung(ladder):
    """No coarser rung holds the hole: the cover after fills stays < 1.0
    and the record names the rung the ladder ran out at -- REPORTED."""
    plan, calls, chain = ladder
    plan.update({
        "FAKE3DEP:1": {"keep": (-117.56, 47.60, -117.535, 47.64),
                       "value": 720.0},
    })
    INSETS.ensure_airport_insets(47, -118, {"KGEG": LADDER_BOX}, [chain],
                                 None, airport_polygons={"KGEG": _airport()})
    meta = _sidecar()
    assert meta["ladder"]["delivered_rung"] == 0
    assert meta["airport_filled_fraction"] < 1.0
    assert meta["fills"]["ran_out"] == "1/3 arc-second"
    assert meta["holes"][0]["filled_by"] is None
    shortfall = INSETS.inset_fill_shortfall(INSETS.inset_fill_summary(meta))
    assert "ran out at 1/3 arc-second" in shortfall


def test_a_pre_ladder_fill_sidecar_reads_no_holes():
    summary = INSETS.inset_fill_summary({"provider": "USGS3DEP",
                                         "valid_fraction": 1.0})
    assert summary["holes"] == 0 and not summary["recorded"]
    assert INSETS.inset_fill_shortfall(summary) is None
    assert "predates" in INSETS.inset_fill_summary_text(summary)


def test_water_detection_skips_filled_holes(tmp_path):
    """Consumer (spec §5 water-supplement row, generalised): a filled
    hole is an upsampled coarser rung -- never read as a measured
    surface by the hydro-flat detector."""
    inset = tmp_path / "KGEG_x.tif"
    hole_box = [WEST + 0.001, SOUTH + 0.001, WEST + 0.002, SOUTH + 0.002]
    with open(tmp_path / "KGEG_x.json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump({"holes": [{"cells": 100, "bounding_box_wgs84": hole_box,
                              "filled_by": TEN}]}, handle)
    size = 100
    transform = (WEST, (EAST - WEST) / size, 0.0, NORTH, 0.0,
                 -(NORTH - SOUTH) / size)
    valid = numpy.ones((size, size), dtype=bool)
    kept = INSETS._restrict_to_inset_core_box(str(inset), valid, transform)
    xs = WEST + (numpy.arange(size) + 0.5) * transform[1]
    ys = NORTH + (numpy.arange(size) + 0.5) * transform[5]
    inside = ((ys >= hole_box[1]) & (ys <= hole_box[3]))[:, None] & (
        (xs >= hole_box[0]) & (xs <= hole_box[2]))[None, :]
    assert inside.any()
    assert not kept[inside].any()
    assert kept[~inside].all()


def test_a_box_edge_sliver_beyond_every_rung_never_runs_the_ladder_out(
        tmp_path):
    """KASE witness: the 1/3" rung warped to its own 10 m grid stops a
    metre or two short of the box's east and south edges.  That sliver
    is no rung's to answer (the bake's outer feather gives it zero
    weight): it is counted, never a climb or a ``ran_out``."""
    core = _plane(600, 600)
    core[:, 400:] = NODATA                    # an edge hole to the east
    core_path = _write(tmp_path / "core.tif", 600, core)
    size = 59                                 # 59 x 10 m: 10 m short
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(tmp_path / "short.tif"), size, size, 1, gdal.GDT_Float32)
    step_x = (EAST - WEST) / 60
    step_y = (NORTH - SOUTH) / 60
    dataset.SetGeoTransform((WEST, step_x, 0.0, NORTH, 0.0, -step_y))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    dataset.GetRasterBand(1).SetNoDataValue(NODATA)
    dataset.GetRasterBand(1).WriteArray(
        numpy.full((size, size), 99.0, dtype=numpy.float32))
    dataset = None
    assembly = INSETS.LadderInsetAssembly(core_path, core_region_is_box=True)
    assert assembly.needs_fill()
    assembly.add_fill(str(tmp_path / "short.tif"), TEN)
    assert not assembly.needs_fill()
    record = assembly.write(str(tmp_path / "out.tif"))
    assert record["unanswered_cells"] == 0
    assert record["box_edge_sliver_cells"] > 0
    assert record["filled_fraction"] < 1.0
