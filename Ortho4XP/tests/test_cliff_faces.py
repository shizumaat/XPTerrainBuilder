"""Cliff faces (#2096): the layout, the texture algorithms, the DSF band.

Synthetic meshes only: a flat grid with one column of cells raised into a
near-vertical wall."""
import array
import collections
import dataclasses

import numpy
import O4_Cliff_DSF as CLIFF
import O4_Cliff_Faces as FACES
import O4_Cliff_Texture as TEX
import O4_DSF_Pools as POOLS
import pytest

LOOSE = dataclasses.replace(FACES.CliffParams(), min_area_m2=100.0)


def _wall_mesh(height=200.0, n=12, cell=30.0):
    """``n`` x ``n`` cells; the east half is ``height`` m higher, so the
    middle column of cells is a ~80 degree wall for 30 m cells."""
    xs = numpy.arange(n + 1) * cell
    gx, gy = numpy.meshgrid(xs, xs)
    z = numpy.where(gx > xs[n // 2], height, 0.0)
    xyz = numpy.stack((gx.ravel(), gy.ravel(), z.ravel()), 1)
    tris = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            tris += [(a, a + 1, a + n + 2), (a, a + n + 2, a + n + 1)]
    return xyz, numpy.array(tris)


def _steep(xyz, tris, above=60.0):
    return set(numpy.nonzero(FACES.triangle_slopes(xyz, tris)[0] > above)[0]
               .tolist())


def test_wall_is_one_region_with_one_face_chart():
    xyz, tris = _wall_mesh()
    lay = FACES.find_cliff_layout(xyz, tris, numpy.ones(len(tris), bool),
                                  LOOSE)
    assert len(lay.region_area) == 1
    steep = _steep(xyz, tris)
    assert steep <= set(lay.tris.tolist())
    face = {int(c) for t, c in zip(lay.tris, lay.chart, strict=True)
            if t in steep}
    assert len(face) == 1
    u, v = lay.chart_axes[face.pop()]
    assert abs(abs(u[1]) - 1) < 1e-6      # along the wall (north)
    assert v[2] > 0.1                     # up the wall
    assert lay.alpha[tris[min(steep)]].min() == pytest.approx(1.0)
    assert lay.alpha[0] == 0.0            # far from it: photo only


def test_face_chart_keeps_lengths():
    xyz, tris = _wall_mesh()
    lay = FACES.find_cliff_layout(xyz, tris, numpy.ones(len(tris), bool),
                                  LOOSE)
    t = min(_steep(xyz, tris))
    chart = int(lay.chart[list(lay.tris).index(t)])
    p = xyz[tris[t]]
    uv = lay.chart_uv(chart, p, 1.0)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        assert numpy.linalg.norm(uv[i] - uv[j]) == pytest.approx(
            numpy.linalg.norm(p[i] - p[j]), rel=1e-6)


def test_gentle_mesh_and_water_have_no_overlay():
    xyz, tris = _wall_mesh(height=20.0)
    lay = FACES.find_cliff_layout(xyz, tris, numpy.ones(len(tris), bool))
    assert len(lay.tris) == 0 and not lay.alpha.any()
    xyz, tris = _wall_mesh()
    lay = FACES.find_cliff_layout(xyz, tris, numpy.zeros(len(tris), bool),
                                  LOOSE)
    assert len(lay.tris) == 0


def test_small_regions_stay_photo():
    xyz, tris = _wall_mesh()
    lay = FACES.find_cliff_layout(
        xyz, tris, numpy.ones(len(tris), bool),
        dataclasses.replace(LOOSE, min_area_m2=1e9))
    assert len(lay.tris) == 0 and lay.dropped_regions == 1


def test_lab_round_trip():
    rgb = numpy.random.default_rng(1).integers(0, 256, (50, 3)).astype(
        numpy.uint8)
    back = TEX._lab_to_srgb(TEX.srgb_to_lab(rgb))
    assert numpy.abs(back.astype(int) - rgb).max() <= 1


def test_match_lab_moves_the_statistics():
    rgb = numpy.random.default_rng(2).integers(60, 200, (64, 64, 3)).astype(
        numpy.uint8)
    out = TEX.match_lab(rgb, (55.0, 5.0, 12.0), (8.0, 2.0, 3.0))
    lab = TEX.srgb_to_lab(out).reshape(-1, 3)
    assert numpy.allclose(lab.mean(0), (55, 5, 12), atol=1.0)
    assert numpy.allclose(lab.std(0), (8, 2, 3), atol=1.0)


def test_quilt_wraps_without_a_seam():
    """A smooth exemplar: every step between neighbouring pixels is small,
    so a seam is a step far above the rest.  The wrap edge of the quilt is
    not one; the wrap edge of the exemplar itself (naive tiling) is."""
    rng = numpy.random.default_rng(3)
    y, x = numpy.mgrid[0:192, 0:192] / 192.0
    ex = numpy.stack([127 + 100 * numpy.sin(2 * numpy.pi * (f * x + g * y)
                                             + rng.uniform(0, 6))
                      for f, g in ((1.3, 0.4), (0.5, 1.7), (2.1, 1.1))], -1)
    ex = ex.astype(numpy.uint8)
    tile = TEX.quilt(ex, size=256, rng=rng).astype(int)
    assert tile.shape == (256, 256, 3)

    def jump(a, b):
        return numpy.abs(a - b).sum(-1).mean()
    inner = numpy.percentile([jump(tile[:, i], tile[:, i + 1])
                              for i in range(255)], 90)
    naive = jump(ex[:, -1].astype(int), ex[:, 0].astype(int))
    assert naive > 4 * inner
    assert jump(tile[:, -1], tile[:, 0]) < 2 * inner
    assert jump(tile[-1], tile[0]) < 2 * inner


def test_pick_exemplar_prefers_the_target_colour():
    img = numpy.zeros((64, 64, 3), numpy.uint8)
    img[:, :32] = (40, 120, 40)
    img[:, 32:] = (170, 160, 140)
    img = img + numpy.random.default_rng(4).integers(
        0, 30, img.shape).astype(numpy.uint8)
    target = TEX.srgb_to_lab(numpy.array((170, 160, 140)))
    r, c = TEX.pick_exemplar(img, numpy.ones((64, 64), bool), target, 16)
    assert c >= 32


def test_blend_ramp_reads_the_same_either_way_up():
    ramp = TEX.blend_ramp(64, 2)[:, 0].astype(int)
    assert (ramp == ramp[::-1]).all()
    assert ramp[0] <= 4 and ramp[31] >= 250


def test_dsf_band_points_terrain_and_plan(tmp_path, monkeypatch):
    xyz, tris = _wall_mesh()
    k = 111319.49
    nodes = numpy.stack((13.0 + xyz[:, 0] / (k * numpy.cos(numpy.radians(
        38.5))), 38.0 + xyz[:, 1] / k, xyz[:, 2], numpy.zeros(len(xyz)),
        numpy.zeros(len(xyz))), 1)
    planes, base = CLIFF.add_cliff_band(7 * numpy.ones(3, "int"), 1)
    assert base == 3 and planes[3] == 9
    pools = POOLS.DsfPointPools(1, planes)
    pool_param = {0: (1, 13, 1, 38, 771, 0, 2, -1, 2, -1, 1, 0, 1, 0,
                      1, 0, 1, 0)}
    (tmp_path / "textures").mkdir()
    tile = type("Tile", (), {"lat": 38, "lon": 13, "mesh_zl": 18,
                             "build_dir": str(tmp_path),
                             "terrain_staging": str(tmp_path)})
    monkeypatch.setattr(FACES, "CliffParams", lambda: LOOSE)
    dico, textured, overlays = {"terrain_Water": 0}, {0: {}}, set()
    tert, plan = CLIFF.emit_cliff_overlays(
        tile, nodes, tris, numpy.zeros(len(tris), int),
        array.array("H", [0] * (5 * len(nodes))),
        {i: 0 for i in range(len(nodes))}, pool_param, pools, base, 1,
        collections.defaultdict(lambda: (0, 0, 17, "BI")), textured, dico,
        overlays)
    assert tert == b"terrain/cliff_+38+013_000.ter\0"
    assert len(plan) == 1 and plan[0]["texture"] == "cliff_+38+013_000.dds"
    assert overlays == {1} and textured[1]
    assert pool_param[pools.geometric[base]][10:14] == (
        CLIFF.UV_RANGE, 0, CLIFF.UV_RANGE, 0)
    pts = numpy.frombuffer(pools.points[base], numpy.uint16).reshape(-1, 9)
    assert (pts[:, 7] == 32768).all()
    assert pts[:, 8].max() == 32768       # alpha 1 -> t2 = 0.5
    ter = (tmp_path / "cliff_+38+013_000.ter").read_text()
    assert "BASE_TEX ../textures/cliff_+38+013_000.dds" in ter
    assert "BORDER_TEX ../textures/cliff_blend.png" in ter
    assert (tmp_path / "textures" / "cliff_blend.png").is_file()
