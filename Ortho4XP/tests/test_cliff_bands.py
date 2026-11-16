"""The cliff overlay's texture follows the slope over the shadow (#2102).

Synthetic ramp: columns of cells at 5, 48 and 75 degrees.  Over the
carried (shadow) opacity the overlay must read base -> hill -> cliff, the
way X-Plane's landclass does, and never put rock on the gentle ground."""
import array

import numpy
import O4_Cliff_Bands as BANDS
import O4_Cliff_DSF as CLIFF
import O4_Cliff_Faces as FACES
import O4_Cliff_Library as LIBRARY
import O4_DSF_Pools as POOLS

SLOPES = [5.0] * 4 + [48.0] * 4 + [75.0] * 4


def _ramp_mesh(rows=12, cell=30.0):
    """Columns of cells rising east at :data:`SLOPES` degrees."""
    dz = numpy.concatenate(([0.0], numpy.tan(numpy.radians(SLOPES)) * cell))
    zs = numpy.cumsum(dz)
    n = len(SLOPES)
    gx, gy = numpy.meshgrid(numpy.arange(n + 1) * cell,
                            numpy.arange(rows + 1) * cell)
    z = numpy.tile(zs, (rows + 1, 1))
    xyz = numpy.stack((gx.ravel(), gy.ravel(), z.ravel()), 1)
    tris = []
    for j in range(rows):
        for i in range(n):
            a = j * (n + 1) + i
            tris += [(a, a + 1, a + n + 2), (a, a + n + 2, a + n + 1)]
    return xyz, numpy.array(tris)


def _column(xyz, tris):
    return (xyz[tris, 0].mean(1) // 30.0).astype(int)


def _alphas(xyz, tris, extra):
    land = numpy.ones(len(tris), bool)
    slope = FACES.triangle_slopes(xyz, tris)[0]
    steepest = FACES.node_steepest(tris, slope, land, len(xyz))
    bands = numpy.tile(BANDS.DEFAULT_BANDS, (len(xyz), 1))
    return BANDS.band_alphas(steepest, FACES.slope_ramp(steepest, 58, 68),
                             extra, bands)


def test_ramp_reads_base_then_hill_then_cliff():
    xyz, tris = _ramp_mesh()
    alphas = _alphas(xyz, tris, numpy.ones(len(xyz)))
    top = BANDS.dominant_layers(tris, numpy.arange(len(tris)), alphas)
    col = _column(xyz, tris)
    by_col = [sorted(set(top[col == c].tolist())) for c in range(len(SLOPES))]
    assert by_col[0] == [0] and by_col[5] == [1] and by_col[-1] == [2]
    # monotone up the ramp: never rock below hill, never hill below base
    worst = [max(b) for b in by_col]
    assert worst == sorted(worst)
    # gentle ground carries no rock at all
    gentle = col <= 2
    assert alphas["cliff"][tris[gentle]].max() == 0.0


def test_without_carried_opacity_only_the_cliff_ramp_draws():
    xyz, tris = _ramp_mesh()
    alphas = _alphas(xyz, tris, numpy.zeros(len(xyz)))
    assert not alphas["base"].any() and not alphas["hill"].any()
    slope = FACES.triangle_slopes(xyz, tris)[0]
    steepest = FACES.node_steepest(tris, slope, numpy.ones(len(tris), bool),
                                   len(xyz))
    assert numpy.array_equal(alphas["cliff"],
                             FACES.slope_ramp(steepest, 58, 68))


def test_slope_bands_read_from_the_landclass(tmp_path):
    tex = tmp_path / "textures10"
    tex.mkdir()
    for name in ("hill.dds", "cliff.dds", "base.dds"):
        (tex / name).write_bytes(b"x")
    ter = tmp_path / "terrain10" / "l.ter"
    ter.parent.mkdir()
    ter.write_text(
        "A\n800\nTERRAIN\nBASE_TEX ../textures10/base.dds\n"
        "PROJECTED 2992 2992\nSUPER_ROUGHNESS 0.5\n"
        "AUTO_SLOPE_HILL 2328 1164 35 40 ../textures10/hill.dds\n"
        "AUTO_SLOPE_CLIFF 2832 708 57 62 ../textures10/cliff.dds\n"
        "DECAL_LIB lib/g10/decals/x.dcl\n", encoding="utf-8")
    bands = LIBRARY._slope_bands(str(ter))
    assert bands.hill_band == (35.0, 40.0)
    assert bands.cliff_band == (57.0, 62.0)
    assert bands.hill.dds.endswith("hill.dds")
    assert bands.hill_projected == (2328.0, 1164.0)
    assert (bands.base.width_m, bands.base.height_m) == (2992.0, 2992.0)
    assert bands.base.material == ("SUPER_ROUGHNESS 0.5",
                                   "DECAL_LIB lib/g10/decals/x.dcl")
    (tex / "base.dds").unlink()
    assert LIBRARY._slope_bands(str(ter)).base is None


def _tri_count(terrain):
    return sum(len(v) // (6 if k == "cross-pool" else 3)
               for k, v in terrain.items())


def test_dsf_draws_base_and_hill_under_the_cliff(tmp_path, monkeypatch):
    """Carried over the whole ramp: base, hill, cliff terrains in that
    order (drawn bottom to top); the gentle columns are base, not rock."""
    xyz, tris = _ramp_mesh()
    k = 111319.49
    nodes = numpy.stack((13.0 + xyz[:, 0] / (k * numpy.cos(numpy.radians(
        38.5))), 38.0 + xyz[:, 1] / k, xyz[:, 2], numpy.zeros(len(xyz)),
        numpy.zeros(len(xyz))), 1)

    def tex(name, w, h):
        return LIBRARY._CliffTexture(str(tmp_path / name), w, h, ())
    bands = LIBRARY._SlopeBands(tex("hill.dds", 2328, 582), (2328, 1164),
                                tex("base.dds", 2992, 2992), (35, 40),
                                (57, 62))
    monkeypatch.setattr(LIBRARY, "region_cliff_textures",
                        lambda t, ll, regions: [tex("rock.dds", 2832, 708)]
                        * len(regions))
    monkeypatch.setattr(LIBRARY, "region_slope_bands",
                        lambda t, ll, regions: [bands] * len(regions))
    monkeypatch.setattr(LIBRARY, "install_texture", lambda tile, t: (
        "_shared/" + t.dds.rsplit("/", 1)[-1], "link"))

    def over_shadow(tile, layout, xyz, nodes, tri_idx, land, params, dico):
        extra = numpy.ones(len(xyz))
        return FACES.find_cliff_layout(xyz, tri_idx, land, params,
                                       extra_alpha=extra), extra
    monkeypatch.setattr(CLIFF, "_over_shadow", over_shadow)
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
    tert, _plan = CLIFF.emit_cliff_overlays(
        tile, nodes, tris, numpy.zeros(len(tris), int),
        array.array("H", [0] * (5 * len(nodes))),
        {i: 0 for i in range(len(nodes))}, pool_param, pools, base, 1,
        None, textured, dico, overlays, "xpface")
    names = tert.decode().strip("\0").split("\0")
    assert names == ["terrain/cliff_base_base.ter",
                     "terrain/cliff_hill_hill.ter",
                     "terrain/cliff_rock.ter"]
    count = [_tri_count(textured[i]) for i in (1, 2, 3)]
    assert count[0] == len(tris)              # base under everything
    assert count[2] < len(tris) // 2          # rock only up the ramp
    assert count[1] < count[0]                # no hill on the flat
