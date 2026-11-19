"""Synthetic twin of the custom-patch BLEND BAND (#2173 part 2): a custom
pad over a sloped DEM gets a foot ring on the DEM at the bank law's
daylight point, the mesh's bank blend runs from the pad edge to that foot
(no step at the edge, the DEM at the foot, the flanks never steeper than
1:3 where the ground is gentle), grass enclosed by pavement keeps the DEM,
and auto patches are never touched."""

import os
import sys
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Bank_Annulus as BANK_ANNULUS  # noqa: E402
import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Patch_Band as BAND  # noqa: E402
import O4_Patch_Rebase as R  # noqa: E402
import O4_Patch_Voids as VOIDS  # noqa: E402

LAT, LON = 39, -107
LAT0, LON0 = LAT + 0.5, LON + 0.5
DEG = 111120.0
KX = DEG * numpy.cos(numpy.radians(LAT0))
GROUND_SLOPE = 0.05          # the DEM rises 5 % to the east
LAW_SLOPE = 0.33


def to_ll(x, y):
    return (LON0 + x / KX, LAT0 + y / DEG)


def dem(lonlat):
    p = numpy.atleast_2d(numpy.asarray(lonlat, dtype=float))
    return 2000.0 + GROUND_SLOPE * (p[:, 0] - LON0) * KX


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def patch_text(pads):
    """``pads``: ``[(rect in metres, altitude)]`` -> custom patch OSM, one
    element per line as JOSM writes it (the engine's reader is line-based)."""
    nodes, ways, nid = [], [], 0
    for k, (ring, alt) in enumerate(pads):
        ids = []
        for x, y in ring:
            nid -= 1
            lon, lat = to_ll(x, y)
            nodes.append("  <node id='%d' lat='%.10f' lon='%.10f' />"
                         % (nid, lat, lon))
            ids.append(nid)
        ways.append("  <way id='%d'>\n%s\n    <tag k='altitude' v='%.2f' />"
                    "\n  </way>" % (-1000 - k, "\n".join(
                        "    <nd ref='%d' />" % i for i in ids + ids[:1]),
                        alt))
    return ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
            + "\n".join(nodes + ways) + "\n</osm>\n")


@pytest.fixture()
def tile(tmp_path, monkeypatch):
    """A tile whose custom patch dir and build dir are temp folders; the
    build DEM is the sloped plane above (and the patch's reference)."""
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    build = tmp_path / "build"
    build.mkdir()
    monkeypatch.setattr(R.FNAMES, "patch_dir", lambda lat, lon: str(patch_dir))
    monkeypatch.setattr(R, "_sources", lambda t: {R.BUILD_SOURCE: dem})
    return SimpleNamespace(lat=LAT, lon=LON, build_dir=str(build),
                           auto_patch="All", rebase_custom_patches=True,
                           patch_dir=patch_dir)


def _write(tile, name, pads):
    (tile.patch_dir / name).write_text(patch_text(pads), encoding="utf-8",
                                       newline="")


def _bands(path):
    nodes, _pads, _ramps = R._height_points(open(path, encoding="utf-8").read())
    import xml.etree.ElementTree as ET
    out = []
    for way in ET.parse(path).getroot().iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        if tags.get("o4_feature") == BAND.BAND_FEATURE:
            refs = [nd.get("ref") for nd in way.iter("nd")]
            out.append((numpy.array([nodes[r] for r in refs]), tags))
    return out


def _metres(lonlat):
    p = numpy.atleast_2d(lonlat)
    return numpy.column_stack([(p[:, 0] - LON0) * KX, (p[:, 1] - LAT0) * DEG])


# ── the band itself ────────────────────────────────────────────────────

def test_a_custom_pad_over_a_sloped_dem_gets_a_band_at_its_daylight(tile):
    # 1.5 m above the ground at its centre: fill on the west, cut east
    _write(tile, "TEST.patch.osm", [(rect(-40, -20, 40, 20), 2001.5)])
    copy = R.mesh_path(tile, str(tile.patch_dir), "TEST.patch.osm")
    assert copy != str(tile.patch_dir / "TEST.patch.osm")
    bands = _bands(copy)
    assert len(bands) == 1
    ring, tags = bands[0]
    assert tags["var_alt_rel"] == "0" and VOIDS.VOID_TAG[0] not in tags
    xy = _metres(ring)
    from shapely import geometry
    pad = geometry.Polygon(rect(-40, -20, 40, 20))
    gap = numpy.array([pad.exterior.distance(geometry.Point(p)) for p in xy])
    assert gap.min() >= 5.0 - 0.3                  # the law's minimum width
    # every foot node is on the 1:3 line's daylight or nearer the pad:
    # |pad - DEM(foot)| <= slope * distance (+ the walk's half step)
    assert numpy.all(numpy.abs(2001.5 - dem(ring)) <= LAW_SLOPE * gap + 0.25)
    # the user's file is untouched
    assert "bank_foot" not in (tile.patch_dir / "TEST.patch.osm").read_text(
        encoding="utf-8")
    assert R.read_path(tile, str(tile.patch_dir), "TEST.patch.osm") == copy


def test_the_band_blends_from_the_pad_edge_to_the_dem(tile, monkeypatch,
                                                      tmp_path):
    """Through the mesh's own blend (``bank_annulus_blend_values``): no
    step at the pad edge, the DEM at the foot, the band no steeper than
    the bank law, nothing written beyond the foot or on the pad."""
    from scipy.spatial import Delaunay
    from shapely import geometry

    pad_ring = rect(-40, -20, 40, 20)
    _write(tile, "TEST.patch.osm", [(pad_ring, 2001.5)])
    copy = R.mesh_path(tile, str(tile.patch_dir), "TEST.patch.osm")
    (foot, _tags), = _bands(copy)
    foot_m = _metres(foot)[:-1]
    pad_m = numpy.array(_densified(pad_ring, 2.0))
    grid = numpy.array([(x, y) for x in numpy.arange(-80, 81, 1.5)
                        for y in numpy.arange(-60, 61, 1.5)])
    outer = geometry.Polygon(foot_m)
    padp = geometry.Polygon(pad_ring)
    inside = [p for p in grid if outer.buffer(-0.3).contains(geometry.Point(p))
              and not padp.buffer(0.3).contains(geometry.Point(p))]
    pts = numpy.vstack([pad_m, foot_m, inside])
    n_pad, n_foot = len(pad_m), len(foot_m)
    z = numpy.concatenate([numpy.full(n_pad, 2001.5),
                           dem(numpy.array([to_ll(*p) for p in foot_m])),
                           numpy.full(len(inside), -999.0)])
    vertices = numpy.zeros(6 * len(pts))
    ll = numpy.array([to_ll(*p) for p in pts])
    vertices[0::6] = ll[:, 0] - LON
    vertices[1::6] = ll[:, 1] - LAT
    vertices[5::6] = z
    tri = Delaunay(pts)
    triangles = [tuple(int(v) for v in s) for s in tri.simplices
                 if outer.contains(geometry.Point(pts[s].mean(axis=0)))
                 and not padp.contains(geometry.Point(pts[s].mean(axis=0)))]
    edges = [(i, (i + 1) % n_pad) for i in range(n_pad)]
    edges += [(n_pad + i, n_pad + (i + 1) % n_foot) for i in range(n_foot)]
    poly = tmp_path / "twin.poly"
    poly.write_text("0 2 0 0\n%d 1\n%s\n0\n" % (len(edges), "\n".join(
        "%d %d %d %d" % (k + 1, a + 1, b + 1, MESH.PATCH_RING_MARKER)
        for k, (a, b) in enumerate(edges))), encoding="utf-8", newline="")
    monkeypatch.setattr(MESH.FNAMES, "input_poly_file", lambda t: str(poly))
    blend = MESH.bank_annulus_blend_values(
        tile, vertices, triangles, set(range(n_pad + n_foot)))
    free = set(range(n_pad + n_foot, len(pts)))
    assert free and free <= set(blend), len(free - set(blend))
    assert not set(blend) & set(range(n_pad))           # the pad stays flat
    for index, value in blend.items():
        vertices[6 * index + 5] = value
    worst_edge = worst_slope = 0.0
    for index in free:
        p = geometry.Point(pts[index])
        d_pad = padp.exterior.distance(p)
        if d_pad < 1.0:                                  # beside the edge
            worst_edge = max(worst_edge, abs(vertices[6 * index + 5]
                                             - 2001.5) / max(d_pad, 1e-6))
    for a, b, c in triangles:
        cx, cy = pts[[a, b, c]].mean(axis=0)
        if abs(cx) > 38 and abs(cy) > 18:
            # a CORNER FAN: RULINGS 2026-09-09ab's station normal splits it
            # between the two edges' feet (no closed form is asserted, as
            # in the auto-bank twin); measured at KASE with the rest
            continue
        for u, v in ((a, b), (b, c), (c, a)):
            run = float(numpy.hypot(*(pts[u] - pts[v])))
            rise = abs(vertices[6 * u + 5] - vertices[6 * v + 5])
            worst_slope = max(worst_slope, rise / run)
    # no step at the edge: the ground beside it leaves at the band's slope
    assert worst_edge <= LAW_SLOPE + GROUND_SLOPE
    assert worst_slope <= LAW_SLOPE + GROUND_SLOPE, worst_slope


def _densified(ring, step):
    """The ring's nodes every ``step`` metres (the pad's .poly ring)."""
    from auto_patch_v2.planar.chords import densify
    return densify(ring, step, closed=True)[:-1]


def test_grass_enclosed_by_pavement_is_a_void_and_keeps_the_dem(tile):
    """A loop of taxiways round a 120 m square of grass: the band's inner
    foot is a ``bank_foot`` AND a void, so the grass beyond it is no patch
    coverage, and the annulus is only the band on each side."""
    from shapely import geometry

    loop = [(rect(-100, -100, 100, -80), 2000.0),
            (rect(-100, 80, 100, 100), 2000.0),
            (rect(-100, -80, -80, 80), 2000.0),
            (rect(80, -80, 100, 80), 2000.0)]
    _write(tile, "TEST.patch.osm", loop)
    copy = R.mesh_path(tile, str(tile.patch_dir), "TEST.patch.osm")
    feet = _bands(copy)
    holes = [tags for _r, tags in feet if VOIDS.is_hole(tags)]
    assert len(feet) == 2 and len(holes) == 1
    annulus = BANK_ANNULUS.bank_annulus_polygon(tile)
    scalx = numpy.cos(numpy.radians(LAT + 0.5))

    def iso(x, y):
        lon, lat = to_ll(x, y)
        return geometry.Point((lon - LON) * scalx, lat - LAT)
    assert annulus.contains(iso(0, -77))             # band inside the loop
    assert annulus.contains(iso(0, -103))            # band outside it
    assert not annulus.contains(iso(0, 0))           # the grass: the DEM
    assert not annulus.contains(iso(0, -90))         # the pavement


def test_auto_and_edited_patches_get_no_band(tile):
    for name in ("TEST_auto.patch.osm", "TEST_edited.patch.osm"):
        _write(tile, name, [(rect(-40, -20, 40, 20), 2001.5)])
        path = str(tile.patch_dir / name)
        assert R.mesh_path(tile, str(tile.patch_dir), name) == path
        assert R.read_path(tile, str(tile.patch_dir), name) == path
        assert "bank_foot" not in open(path, encoding="utf-8").read()


def test_turning_the_setting_off_drops_the_copy(tile):
    _write(tile, "TEST.patch.osm", [(rect(-40, -20, 40, 20), 2001.5)])
    copy = R.mesh_path(tile, str(tile.patch_dir), "TEST.patch.osm")
    assert os.path.exists(copy)
    tile.rebase_custom_patches = False
    path = str(tile.patch_dir / "TEST.patch.osm")
    assert R.mesh_path(tile, str(tile.patch_dir), "TEST.patch.osm") == path
    assert not os.path.exists(copy)
    assert R.read_path(tile, str(tile.patch_dir), "TEST.patch.osm") == path


def test_the_band_never_outreaches_the_mesh_blend_s_ray():
    assert BAND.MAX_WIDTH_M * 3.0 <= MESH.BANK_RAY_MAX_M
