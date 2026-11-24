"""Synthetic twin of a custom patch's reference elevation (#2179; the fit
of RULINGS 2026-11-19b (2), kept when its re-base and band were retired by
2026-11-23d): a patch authored on DEM A, a build meshing DEM B = A + a
smooth bump; the fit names A, the patch is never rewritten, and only a
custom patch's source is recorded."""

import json

import os
import sys
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Custom_Patch_Source as R  # noqa: E402

LAT, LON = 39.0, -107.0
KX = 111120.0 * numpy.cos(numpy.radians(LAT + 0.2))


def dem_a(p):
    p = numpy.atleast_2d(p)
    return 2000.0 + 0.02 * (p[:, 0] - LON - 0.2) * KX


def dem_b(p):
    p = numpy.atleast_2d(p)
    dx = (p[:, 0] - LON - 0.2) * KX
    dy = (p[:, 1] - LAT - 0.2) * 111120.0
    return dem_a(p) + 4.0 + 3.0 * numpy.exp(-(dx ** 2 + dy ** 2) / 800.0 ** 2)


def square(x_m, y_m, half_m):
    return [(LON + 0.2 + (x_m + sx * half_m) / KX,
             LAT + 0.2 + (y_m + sy * half_m) / 111120.0)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def patch_text(source):
    """Pads of 30 m on a 120 m grid at ``source``'s mean, and one ramp."""
    nodes, ways, nid = [], [], 0
    for i, x in enumerate(range(-600, 601, 120)):
        for y in (-120, 0, 120):
            ring = square(x, y, 15)
            ids = []
            for lon, lat in ring:
                nid -= 1
                ids.append(nid)
                nodes.append("<node id='%d' lat='%.9f' lon='%.9f' />"
                             % (nid, lat, lon))
            alt = float(source(numpy.array(ring)).mean())
            ways.append("<way id='-%d%d'>%s<tag k='altitude' v='%.2f' />"
                        "</way>" % (i + 1, y + 500, "".join(
                            "<nd ref='%d' />" % n for n in ids + ids[:1]),
                            alt))
    ring = square(700, 0, 20)
    ids = []
    for lon, lat in ring:
        nid -= 1
        ids.append(nid)
        nodes.append("<node id='%d' lat='%.9f' lon='%.9f' />"
                     % (nid, lat, lon))
    ends = numpy.array([(numpy.array(ring[3]) + ring[0]) / 2,
                        (numpy.array(ring[1]) + ring[2]) / 2])
    high, low = source(ends)
    ways.append("<way id='-9999'>%s<tag k='altitude_high' v='%.2f' />"
                "<tag k='altitude_low' v='%.2f' /></way>" % ("".join(
                    "<nd ref='%d' />" % n for n in ids + ids[:1]), high, low))
    return ("<?xml version='1.0'?>\n<osm version='0.6'>\n"
            + "\n".join(nodes + ways).replace("</way>", "\n</way>")
            + "\n</osm>\n")


def test_reference_is_the_authoring_dem():
    nodes, pads, ramps = R._height_points(patch_text(dem_a))
    assert len(pads) == 33 and len(ramps) == 1
    ref, stats = R._pick_reference(nodes, pads, ramps,
                                  {R.BUILD_SOURCE: dem_b, "A": dem_a})
    assert ref == "A"
    ref, _ = R._pick_reference(*R._height_points(patch_text(dem_b)),
                              {R.BUILD_SOURCE: dem_b, "A": dem_a})
    assert ref == R.BUILD_SOURCE


@pytest.mark.parametrize("name", ["KXXX_auto.patch.osm",
                                  "KXXX_edited.patch.osm"])
def test_auto_and_edited_patches_record_no_source(tmp_path, name):
    tile = SimpleNamespace(build_dir=str(tmp_path / "build"), lat=39,
                           lon=-107)
    (tmp_path / name).write_text(patch_text(dem_a), encoding="utf-8", newline="")
    R.remember_source(tile, str(tmp_path), name)
    assert not (tmp_path / "build" / R.SOURCES_RECORD).exists()


def test_a_custom_patch_records_its_source_and_is_never_rewritten(
        tmp_path, monkeypatch):
    tile = SimpleNamespace(build_dir=str(tmp_path / "build"), lat=39,
                           lon=-107)
    path = tmp_path / "KXXX.patch.osm"
    text = patch_text(dem_a)
    path.write_text(text, encoding="utf-8", newline="")
    monkeypatch.setattr(R, "_ground_record", lambda *_a: None)
    monkeypatch.setattr(R, "_sources",
                        lambda _t: {R.BUILD_SOURCE: dem_b, "A": dem_a})
    R.remember_source(tile, str(tmp_path), "KXXX.patch.osm")
    record = json.loads((tmp_path / "build" / R.SOURCES_RECORD).read_text(
        encoding="utf-8"))
    assert record["KXXX.patch.osm"]["source"] == "A"
    assert path.read_text(encoding="utf-8") == text
    assert not (tmp_path / "build" / "custom_patch_rebase").exists()
