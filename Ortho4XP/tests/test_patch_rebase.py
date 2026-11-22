"""Synthetic twin of the custom-patch re-base (#2173, RULINGS 2026-11-19b):
a patch authored on DEM A, a build meshing DEM B = A + a smooth bump; the
re-based heights follow B, pads stay one height, the user's file is never
edited, and auto / ``_edited`` patches are never re-based."""

import os
import sys
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Patch_Rebase as R  # noqa: E402

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


def test_rebased_heights_follow_the_build_dem_and_pads_stay_flat():
    text = patch_text(dem_a)
    nodes, pads, ramps = R._height_points(text)
    field = R._OffsetField(*R._height_gaps(nodes, pads, ramps, dem_b))
    new, stats = R._rebase_text(text, field, nodes, pads, ramps)
    n2, p2, r2 = R._height_points(new)
    gaps = numpy.array([dem_b(numpy.array([n2[r] for r in refs[:-1]])).mean()
                        - alt for _, refs, alt in p2])
    assert numpy.abs(numpy.median(gaps)) < 0.1
    assert numpy.abs(gaps).max() < 0.5
    assert stats["pad_spread"].max() < 0.2
    _, (high, low) = r2[0][0], r2[0][2:]
    want = dem_b(R._ends(n2, r2[0][1]))
    assert abs(high - want[0]) < 1.0 and abs(low - want[1]) < 1.0
    # Only height values changed.
    changed = [a for a, b in zip(text.splitlines(), new.splitlines(), strict=False)
               if a != b]
    assert changed and all("altitude" in line for line in changed)


@pytest.mark.parametrize("name", ["KXXX_auto.patch.osm",
                                  "KXXX_edited.patch.osm"])
def test_auto_and_edited_patches_are_never_rebased(tmp_path, name):
    tile = SimpleNamespace(build_dir=str(tmp_path), lat=39, lon=-107)
    assert R.mesh_path(tile, str(tmp_path), name) == str(tmp_path / name)


def test_setting_off_reads_the_users_file(tmp_path):
    tile = SimpleNamespace(build_dir=str(tmp_path), lat=39, lon=-107,
                           rebase_custom_patches=False)
    assert (R.mesh_path(tile, str(tmp_path), "KXXX.patch.osm")
            == str(tmp_path / "KXXX.patch.osm"))
