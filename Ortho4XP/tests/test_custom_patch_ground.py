"""Synthetic twin of #2179 option (a), RULINGS 2026-11-19n (2): an airport
using its custom patch stands on the elevation the patch was made for --
its own insets and approach rings are left out when that is the base
raster, every other airport keeps its lidar, and the patch is meshed as
authored (no re-base, no band)."""

import os
import sys
from types import SimpleNamespace

import numpy
import pytest
from shapely import geometry

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Custom_Patch_Ground as GROUND  # noqa: E402
import O4_DEM_Utils as DEM  # noqa: E402
import O4_Patch_Rebase as R  # noqa: E402

LAT, LON = 39, -107
LAT0, LON0 = LAT + 0.5, LON + 0.5
BASE = "base elevation (Test)"
LIDAR = "KAAA_usgs3dep.tif"


def base(lonlat):
    p = numpy.atleast_2d(lonlat)
    return 2000.0 + 0.0 * p[:, 0]


def lidar(lonlat):
    p = numpy.atleast_2d(lonlat)
    return 2004.0 + 0.0 * p[:, 0]


def patch_text(alt, x=0.0):
    """One square pad ~100 m wide at *alt*, JOSM's line-per-element form."""
    d = 0.0005
    pts = [(LON0 + x - d, LAT0 - d), (LON0 + x + d, LAT0 - d),
           (LON0 + x + d, LAT0 + d), (LON0 + x - d, LAT0 + d)]
    nodes = ["  <node id='%d' lat='%.9f' lon='%.9f' />" % (-1 - k, la, lo)
             for k, (lo, la) in enumerate(pts)]
    refs = "\n".join("    <nd ref='%d' />" % i for i in (-1, -2, -3, -4, -1))
    return ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
            + "\n".join(nodes) + "\n  <way id='-10'>\n" + refs
            + "\n    <tag k='altitude' v='%.2f' />\n  </way>\n</osm>\n" % alt)


@pytest.fixture()
def tile(tmp_path, monkeypatch):
    """A tile whose patch folder is a temp folder; KAAA holds one inset;
    the fit reads the two synthetic surfaces above."""
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    (tmp_path / "build").mkdir()
    monkeypatch.setattr(GROUND.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(GROUND, "_MEMO", {})
    monkeypatch.setattr(GROUND, "_own_insets", lambda t, icao: (
        ["/insets/" + LIDAR] if icao == "KAAA" else []))
    monkeypatch.setattr(INSETS, "_declined_on_read", lambda path: False)
    monkeypatch.setattr(DEM, "is_cached", lambda t: True)
    monkeypatch.setattr(GROUND, "_sources",
                        lambda t, insets: {BASE: base, LIDAR: lidar})
    return SimpleNamespace(lat=LAT, lon=LON, custom_dem="",
                           build_dir=str(tmp_path / "build"),
                           rebase_custom_patches=True, patch_dir=patch_dir)


def _write(tile, name, text):
    (tile.patch_dir / name).write_text(text, encoding="utf-8", newline="")


def test_a_patch_made_for_the_base_leaves_its_airport_s_insets_out(tile):
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    record = GROUND.grounds(tile)["KAAA"]
    assert record["reference"] == BASE and record["left_out"]
    area = GROUND.left_out(tile)["KAAA"]
    # the pad's hull grown by HULL_MARGIN_M on each side
    kx = 111120 * numpy.cos(numpy.radians(LAT0))
    width_m = (area.bounds[2] - area.bounds[0]) * kx
    assert width_m == pytest.approx(0.001 * kx + 2 * GROUND.HULL_MARGIN_M,
                                    abs=2.0)


def test_a_patch_made_on_its_lidar_keeps_it_and_is_still_as_authored(tile):
    _write(tile, "KAAA.patch.osm", patch_text(2004.0))
    record = GROUND.grounds(tile)["KAAA"]
    assert record["reference"] == LIDAR and not record["left_out"]
    assert GROUND.left_out(tile) == {}


def test_an_airport_without_an_inset_stands_on_the_base_without_a_fit(
        tile, monkeypatch):
    monkeypatch.setattr(GROUND, "_sources", lambda t, i: pytest.fail(
        "no inset: the base is the only source, nothing to load"))
    _write(tile, "KZZZ.patch.osm", patch_text(1.0))
    assert GROUND.grounds(tile)["KZZZ"]["reference"] == GROUND._BASE


def test_the_editor_s_patch_and_auto_patches_decide_nothing(tile):
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    _write(tile, "KAAA_edited.patch.osm", patch_text(2000.0))
    _write(tile, "KBBB_auto.patch.osm", patch_text(2000.0))
    assert GROUND.grounds(tile) == {}


def test_no_base_on_disk_decides_later(tile, monkeypatch):
    monkeypatch.setattr(DEM, "is_cached", lambda t: False)
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    assert GROUND.grounds(tile) == {}


def test_the_bake_listing_leaves_out_that_airport_only(tile, monkeypatch):
    """ONE listing for the composite, the bake, the threshold plan and the
    baked boxes: KAAA's inset goes, KCCC's stays, in the same order."""
    paths = ["/i/KAAA_usgs3dep.tif", "/i/KCCC_usgs3dep.tif"]
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    monkeypatch.setattr(INSETS, "list_cached_inset_dems",
                        lambda lat, lon, provider_codes=None: list(paths))
    before = INSETS.bake_candidate_inset_paths(tile)
    assert sorted(before) == sorted(paths)
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    assert INSETS.bake_candidate_inset_paths(tile) == [
        p for p in before if "KCCC" in p]
    assert INSETS.assemble_inset_composite_source(tile, "") == (
        ";/i/KCCC_usgs3dep.tif")


def test_the_coverage_warning_is_silent_for_a_left_out_airport(
        tile, monkeypatch):
    monkeypatch.setattr(INSETS, "cached_inset_paths_for_airport",
                        lambda t, icao: ["/i/%s_usgs3dep.tif" % icao])
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    assert not INSETS.warn_if_inset_does_not_cover_airport(tile, "KAAA", 0.0)
    assert INSETS.warn_if_inset_does_not_cover_airport(tile, "KCCC", 0.0)


def test_the_patch_is_meshed_as_authored(tile):
    """No re-base, no band: ``mesh_path`` hands the user's own file and
    drops a copy an earlier build wrote."""
    _write(tile, "KAAA.patch.osm", patch_text(2000.0))
    stale = os.path.join(tile.build_dir, "custom_patch_rebase",
                         "KAAA.patch.osm")
    os.makedirs(os.path.dirname(stale))
    open(stale, "w", encoding="utf-8", newline="").close()
    path = R.mesh_path(tile, str(tile.patch_dir), "KAAA.patch.osm")
    assert path == str(tile.patch_dir / "KAAA.patch.osm")
    assert not os.path.exists(stale)
    assert R.read_path(tile, str(tile.patch_dir), "KAAA.patch.osm") == path


def test_rings_leave_the_airport_out_and_cut_the_others_back(
        tmp_path, monkeypatch):
    """The left-out airport holds no ring, and another airport's ring
    region no longer reaches its patch hull; the other airport keeps its
    rings."""
    import O4_Elevation_Level as RINGS
    from shapely import wkt

    from tests import test_approach_rings as AR

    if not AR.HAS_GDAL:     # the ring plan needs GDAL, as in test_approach_rings
        pytest.skip("requires the GDAL python bindings")
    AR._install_registry(monkeypatch, AR._definition("FINE", 1.0))
    ring_tile = AR._tile(tmp_path, monkeypatch)
    dico = AR._dico(KAAA=AR._boundary(0.45, 0.5), KCCC=AR._boundary(0.55, 0.5))
    hull = geometry.Point(LON + 0.45, LAT + 0.5).buffer(0.005)
    monkeypatch.setattr(GROUND, "left_out", lambda t: {"KAAA": hull})
    plan = RINGS.resolve_approach_ring_plan(ring_tile, dico)
    assert sorted(plan["airports"]) == ["KCCC"]
    for name in ("R1", "R2"):
        region = wkt.loads(plan["regions"][name])
        assert not region.intersects(hull.buffer(-1e-6))
        assert region.contains(geometry.Point(LON + 0.55, LAT + 0.5))
