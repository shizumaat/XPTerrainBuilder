"""Cliff faces (#2096): the layout, the texture algorithms, the DSF band.

Synthetic meshes only: a flat grid with one column of cells raised into a
near-vertical wall."""
import array
import collections
import dataclasses
import struct

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
    ter = (tmp_path / "cliff_+38+013_000.ter").read_text(encoding="utf-8")
    assert "BASE_TEX ../textures/cliff_+38+013_000.dds" in ter
    assert "BORDER_TEX ../textures/_shared/cliff_blend.png" in ter
    assert (tmp_path / "textures" / "_shared" / "cliff_blend.png").is_file()


def test_cliff_arm_values():
    assert CLIFF._cliff_arm(True) == CLIFF._cliff_arm("synth") == "synth"
    assert CLIFF._cliff_arm("xplane") == "xplane"
    assert CLIFF._cliff_arm(False) is CLIFF._cliff_arm("False") is None


def test_xplane_arm_draws_the_default_terrain(monkeypatch):
    """The ``xplane`` arm: 7-plane overlay points (s = alpha, t = 0) on the
    library terrain the default DSF has there; water takes the majority."""
    import O4_Default_Terrain_Map as DEFTER
    xyz, tris = _wall_mesh()
    k = 111319.49
    nodes = numpy.stack((13.0 + xyz[:, 0] / (k * numpy.cos(numpy.radians(
        38.5))), 38.0 + xyz[:, 1] / k, xyz[:, 2], numpy.zeros(len(xyz)),
        numpy.zeros(len(xyz))), 1)
    planes, base = CLIFF.add_cliff_band(7 * numpy.ones(3, "int"), 1,
                                        "xplane")
    assert base == 3 and planes[3] == 7
    pools = POOLS.DsfPointPools(1, planes)

    class Map:
        terrain_paths = ["lib/g10/terrain10/rock_cld_wet_steep.ter",
                         "lib/g10/terrain10/water_lake.ter"]

        def terrain_index_at(self, lon, lat):
            return 1 if lat > 38.0 + 300 / k else 0

        def is_projected(self, i):
            return True

    monkeypatch.setattr(DEFTER.DefaultTerrainMap, "from_tile",
                        classmethod(lambda cls, lat, lon, d="": Map()))
    monkeypatch.setattr(FACES, "CliffParams",
                        lambda **k: dataclasses.replace(LOOSE, **k))
    tile = type("Tile", (), {"lat": 38, "lon": 13, "mesh_zl": 18})
    dico, textured, overlays = {"terrain_Water": 0}, {0: {}}, set()
    tert, plan = CLIFF.emit_cliff_overlays(
        tile, nodes, tris, numpy.zeros(len(tris), int),
        array.array("H", [0] * (5 * len(nodes))),
        {i: 0 for i in range(len(nodes))}, {}, pools, base, 1,
        None, textured, dico, overlays, "xplane")
    assert tert == b"lib/g10/terrain10/rock_cld_wet_steep.ter\0"
    assert plan == [] and overlays == {1} and textured[1]
    pts = numpy.frombuffer(pools.points[base], numpy.uint16).reshape(-1, 7)
    assert pts[:, 5].max() == 65535 and pts[:, 5].min() < 65535
    assert (pts[:, 6] == 0).all()


def test_xpface_arm_lays_the_cliff_texture_in_face_charts(tmp_path,
                                                          monkeypatch):
    """``xpface``: the landclass's AUTO_SLOPE_CLIFF texture is LINKED once
    into ``textures/_shared/`` (never copied per tile, owner 2026-11-15)
    and drawn in 9-plane face charts W m along the contour and H m down
    the fall line, with the landclass's decal and roughness."""
    import O4_Cliff_Library as LIBRARY
    xyz, tris = _wall_mesh()
    k = 111319.49
    nodes = numpy.stack((13.0 + xyz[:, 0] / (k * numpy.cos(numpy.radians(
        38.5))), 38.0 + xyz[:, 1] / k, xyz[:, 2], numpy.zeros(len(xyz)),
        numpy.zeros(len(xyz))), 1)
    soil = (tmp_path / "Resources" / "default scenery" / "1000 world terrain"
            / "textures10" / "soil")
    soil.mkdir(parents=True)
    dds = soil / "cliff_cld_wet.dds"
    dds.write_bytes(b"DDS ")
    material = ("SUPER_ROUGHNESS 0.5",
                "DECAL_LIB lib/g10/decals/maquify_1_alpha_key.dcl")
    monkeypatch.setattr(LIBRARY, "region_cliff_textures",
                        lambda tile, lonlat, regions: [
                            LIBRARY._CliffTexture(str(dds), 2160.0, 1080.0,
                                                 material)
                        ] * len(regions))
    monkeypatch.setattr(FACES, "CliffParams",
                        lambda **k: dataclasses.replace(LOOSE, **{
                            n: v for n, v in k.items() if n == "max_regions"}))
    planes, base = CLIFF.add_cliff_band(7 * numpy.ones(3, "int"), 1,
                                        "xpface")
    pools = POOLS.DsfPointPools(1, planes)
    pool_param = {0: (1, 13, 1, 38, 771, 0, 2, -1, 2, -1, 1, 0, 1, 0,
                      1, 0, 1, 0)}
    (tmp_path / "textures").mkdir()
    tile = type("Tile", (), {"lat": 38, "lon": 13, "mesh_zl": 18,
                             "build_dir": str(tmp_path),
                             "terrain_staging": str(tmp_path)})
    dico, textured, overlays = {"terrain_Water": 0}, {0: {}}, set()
    tert, plan = CLIFF.emit_cliff_overlays(
        tile, nodes, tris, numpy.zeros(len(tris), int),
        array.array("H", [0] * (5 * len(nodes))),
        {i: 0 for i in range(len(nodes))}, pool_param, pools, base, 1,
        None, textured, dico, overlays, "xpface")
    name = "xp_textures10_soil_cliff_cld_wet"
    terrain = CLIFF._face_terrain_name("_shared/%s.dds" % name, material)
    assert terrain.startswith("cliff_" + name + "_")
    assert terrain != CLIFF._face_terrain_name("_shared/%s.dds" % name, ())
    assert tert == b"terrain/%s.ter\0" % terrain.encode() and plan == []
    assert overlays == {1} and textured[1]
    shared = tmp_path / "textures" / "_shared" / (name + ".dds")
    assert shared.is_symlink() and shared.resolve() == dds.resolve()
    assert not list((tmp_path / "textures").glob("*.dds"))  # no copy
    ter = (tmp_path / ("%s.ter" % terrain)).read_text(encoding="utf-8")
    assert "BASE_TEX ../textures/_shared/%s.dds" % name in ter
    assert ter.splitlines()[-2:] == list(material)
    assert len(pools.points[base])


def test_xpface_charts_are_unstretched_per_axis():
    """W m of face per repeat along the contour (s), H m down the fall
    line (t): the 2048 x 1024 px art of 2160 x 1080 m has square pixels
    on the face, where one W on both axes stretched t x 2."""
    xyz, tris = _wall_mesh()
    layout = FACES.find_cliff_layout(xyz, tris, numpy.ones(len(tris), bool),
                                     LOOSE)
    chart = int(numpy.argmax([v[2] for _u, v in layout.chart_axes]))
    sub = layout.tris[layout.chart == chart]

    def span(repeat):
        st = numpy.array(list(CLIFF._chart_points(
            layout, chart, sub, xyz, tris, repeat).values()), float)
        return (st.max(0) - st.min(0)) / 65535 * CLIFF.UV_RANGE

    one, both = span(2160.0), span((2160.0, 1080.0))
    assert both[0] == pytest.approx(one[0], abs=1e-4)
    assert both[1] == pytest.approx(2 * one[1], abs=1e-3)
    # the 202 m face (30 m run, 200 m rise) in repeats of 1080 m
    assert both[1] == pytest.approx(numpy.hypot(30, 200) / 1080, abs=0.01)


def test_world_library_reads_generic_summer_rows(tmp_path):
    import O4_Cliff_Library as LIBRARY
    root = tmp_path / "Resources" / "default scenery" / "1000 world terrain"
    (root / "terrain10").mkdir(parents=True)
    (root / "library.txt").write_text(
        "A\n800\nLIBRARY\n"
        "REGION terrain10_VLC/\n"
        "EXPORT_EXCLUDE\tlib/g10/terrain10/r.ter\tterrain10_VLC/r.ter\n"
        "REGION all\n"
        "EXPORT_EXCLUDE_SEASON fal,win\tlib/g10/terrain10/r.ter\tterrain10/fal/r.ter\n"
        "EXPORT_EXCLUDE_SEASON spr,sum\tlib/g10/terrain10/r.ter\tterrain10/r.ter\n",
        encoding="utf-8", newline="\n")
    lib = LIBRARY._world_library(str(tmp_path))
    assert lib["lib/g10/terrain10/r.ter"] == str(root / "terrain10" / "r.ter")
    (root / "textures10").mkdir()
    (root / "textures10" / "c.dds").write_bytes(b"x")  # no header: H
    (root / "terrain10" / "r.ter").write_text(
        "A\n800\nTERRAIN\nPROJECTED 10 10\nSUPER_ROUGHNESS 0.5\n"
        "NORMAL_TEX 20 ../textures10/n.png\n"
        "AUTO_SLOPE_CLIFF 2160 1080 57 62 ../textures10/c.dds\n"
        "DECAL_LIB lib/g10/decals/stony_dirt_1.dcl\n",
        encoding="utf-8", newline="\n")
    tex = LIBRARY._cliff_texture(lib["lib/g10/terrain10/r.ter"])
    assert (tex.width_m, tex.height_m) == (2160.0, 1080.0)
    assert tex.dds.endswith("c.dds")
    assert tex.material == ("SUPER_ROUGHNESS 0.5",
                            "DECAL_LIB lib/g10/decals/stony_dirt_1.dcl")
    # a readable header decides: 2048 x 512 px -> square pixels on the face
    (root / "textures10" / "c.dds").write_bytes(
        b"DDS " + struct.pack("<IIII", 124, 0, 512, 2048))
    tex = LIBRARY._cliff_texture(lib["lib/g10/terrain10/r.ter"])
    assert (tex.width_m, tex.height_m) == (2160.0, 540.0)


def test_xplane_texture_goes_through_the_world_packs_one_file(tmp_path,
                                                             monkeypatch):
    """With the World pack as the tiles' home, the pack's own
    ``textures/_shared/`` file is placed first and every build links to the
    same source: one file per pack, whatever the number of tiles."""
    import O4_Cliff_Library as LIBRARY
    import O4_File_Names as FNAMES
    src = (tmp_path / "X" / "Resources" / "default scenery"
           / "1000 world terrain" / "textures10" / "soil" / "c.dds")
    src.parent.mkdir(parents=True)
    src.write_bytes(b"DDS ")
    world = tmp_path / "World"
    monkeypatch.setattr(FNAMES, "world_home", lambda: str(world))
    for t in ("a", "b"):
        tile = type("Tile", (), {"build_dir": str(tmp_path / t)})
        ref, how = LIBRARY.install_texture(
            tile, LIBRARY._CliffTexture(str(src), 2160.0, 1080.0))
        assert ref == "_shared/xp_textures10_soil_c.dds" and how == "symlink"
        assert (tmp_path / t / "textures" / ref).resolve() == src.resolve()
    home = world / "textures" / "_shared" / "xp_textures10_soil_c.dds"
    assert home.is_symlink() and home.resolve() == src.resolve()


def test_xpface_is_the_default_and_the_old_default_is_raised():
    """#2096 (owner 2026-11-15: "used on all tiles going forward"): a new
    cfg reads xpface; an existing global cfg's stored old default False is
    raised once; False still turns the arm off."""
    import O4_Cfg_Vars as CFGVARS
    assert CFGVARS.cfg_vars["cliff_textures"]["default"] == "xpface"
    assert CFGVARS.CHANGED_DEFAULTS["cliff_textures"] == ("False", "xpface")
    assert CLIFF._cliff_arm("xpface") == "xpface"
    assert CLIFF._cliff_arm("False") is None


def test_tile_without_default_scenery_builds_as_off(monkeypatch, capsys):
    """No X-Plane default DSF for the tile: no band, one line, no error."""
    import O4_Overlay_Utils as OVL
    monkeypatch.setattr(OVL, "source_dsf", lambda lat, lon, d: None)
    tile = type("Tile", (), {"lat": 46, "lon": 7, "cliff_textures": "xpface"})
    assert CLIFF.tile_arm(tile, "full_ortho") is None
    out = capsys.readouterr().out
    assert out.count("Cliff faces: off for this tile") == 1
    assert "ERROR" not in out and "WARNING" not in out
    assert CLIFF.tile_arm(tile, "airport_ortho") is None
    monkeypatch.setattr(OVL, "source_dsf", lambda lat, lon, d: "x.dsf")
    assert CLIFF.tile_arm(tile, "full_ortho") == "xpface"
    tile.cliff_textures = "False"
    assert CLIFF.tile_arm(tile, "full_ortho") is None


def test_unplaceable_or_unreadable_textures_leave_regions_to_the_photo(
        tmp_path, monkeypatch):
    """A texture that cannot be placed, or an install that cannot be read,
    leaves those regions undrawn (the photo, as off) -- never a failure."""
    import O4_Cliff_Library as LIBRARY
    tile = type("Tile", (), {"build_dir": str(tmp_path)})
    regions = [[0], [1], [2]]
    monkeypatch.setattr(LIBRARY, "region_cliff_textures",
                        lambda *a: [LIBRARY._CliffTexture("a.dds", 1.0, 1.0),
                                    None,
                                    LIBRARY._CliffTexture("b.dds", 2.0, 1.0)])

    def install(tile, cliff):
        if cliff[0] == "b.dds":
            raise PermissionError("read-only")
        return ("_shared/a.dds", "copy")
    monkeypatch.setattr(LIBRARY, "install_texture", install)
    textures, placed = CLIFF._placed_face_textures(tile, None, regions)
    assert textures == [("a.dds", 1.0, 1.0, ()), None, None]
    assert list(placed) == ["a.dds"]

    def broken(*a):
        raise RuntimeError("no library")
    monkeypatch.setattr(LIBRARY, "region_cliff_textures", broken)
    assert CLIFF._placed_face_textures(tile, None, regions) == (
        [None, None, None], {})


def test_blend_ramp_is_written_once_in_shared(tmp_path):
    tile = type("Tile", (), {"build_dir": str(tmp_path)})
    CLIFF._write_blend(tile)
    path = tmp_path / "textures" / "_shared" / CLIFF.BLEND_TEXTURE
    first = path.stat().st_mtime_ns
    CLIFF._write_blend(tile)
    assert path.stat().st_mtime_ns == first
    assert not (tmp_path / "textures" / CLIFF.BLEND_TEXTURE).exists()
