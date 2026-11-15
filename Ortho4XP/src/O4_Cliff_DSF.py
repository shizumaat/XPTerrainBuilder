"""The cliff overlay in the DSF (#2096, build option ``cliff_textures``).

On top of the orthophoto base, each cliff region of the tile's mesh
(``O4_Cliff_Faces``) is drawn again as an OVERLAY terrain patch (flag 2)
whose texture is unstretched on the face and fades into the photo:

* the points live in their own 9-plane band of the point pools --
  ``(lon, lat, elev, nx, ny, s, t, s2, t2)``: ``(s, t)`` are face-space
  coordinates in repeats of a WRAPPING texture (``BASE_TEX``, so the band's
  scale for them is :data:`UV_RANGE`, not the photo's 0..1), ``(s2, t2)``
  = ``(0.5, alpha / 2)`` read the blend ramp (``BORDER_TEX``), which turns
  each node's alpha into the patch's opacity;
* one terrain (``.ter``) and one texture per region, named
  ``cliff_<tile>_<region>``; the texture is made after the photos are
  converted (``O4_Cliff_Synth``) from the plan :func:`emit_cliff_overlays`
  returns.

A per-vertex texture coordinate is what makes this possible: a PROJECTED
terrain is projected from above, exactly like the photo, and stretches the
same way.  Nothing here runs when the option is off, so the DSF is the same
bytes as without this module.
"""
from __future__ import annotations

import array
import os

import numpy
import O4_Cliff_Faces as FACES
import O4_Cliff_Library as LIBRARY
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Tile_Staging as STAGING
import O4_UI_Utils as UI

__all__ = ["ARMS", "BLEND_TEXTURE", "UV_RANGE", "add_cliff_band",
           "cliff_arm", "emit_cliff_overlays"]

#: ``cliff_textures`` values that draw the overlay: ``synth`` (a texture
#: made from the tile's photos) and ``xplane`` (X-Plane's own default
#: landclass terrain, ``O4_Cliff_Library``).
ARMS = ("synth", "xplane")

#: Face coordinates are stored in 0 .. UV_RANGE repeats (65,535 steps: a
#: 480 m repeat is quantised to 0.47 m).
UV_RANGE = 64.0
BLEND_TEXTURE = "cliff_blend.png"
#: Exemplar pixels are taken from triangles this sloped (degrees): the
#: mountain's own flanks, unstretched (1 / cos 42 = 1.35) and not the flat
#: floor around it where roofs and fields are.
EXEMPLAR_SLOPES = (15.0, 42.0)
#: ... and within this distance (m) of the region's bounding box.
EXEMPLAR_REACH_M = 1500.0


def cliff_arm(value):
    """The arm a ``cliff_textures`` value selects, or None (off).  ``True``
    (the option's first, boolean form) is ``synth``."""
    value = str(value).strip().lower()
    if value == "true":
        return "synth"
    return value if value in ARMS else None


def add_cliff_band(planes, pool_nbr, arm="synth"):
    """``planes`` with the cliff band appended (9 planes per geometric
    pool for ``synth``, 7 for ``xplane``) and the band's first dsf-pool
    index."""
    base = len(planes)
    n = LIBRARY.PLANES if arm == "xplane" else 9
    return numpy.concatenate((planes, n * numpy.ones(pool_nbr, "int"))), base


def _cliff_pool_params(point_pools, pool_param, base, pool_nbr):
    """Point the cliff band's pools at scale/offset records of their own:
    their geometric pool's, with the face coordinates on 0..UV_RANGE."""
    for i in range(pool_nbr):
        key = ("cliff", i)
        record = list(pool_param[i])
        record[10:12] = [UV_RANGE, 0]
        record[12:14] = [UV_RANGE, 0]
        pool_param[key] = tuple(record)
        point_pools.geometric[base + i] = key


def _terrain_file(tile, name):
    path = os.path.join(STAGING.terrain_dir(tile), name + ".ter")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("A\n800\nTERRAIN\n\n")
        f.write("BASE_TEX ../textures/" + name + ".dds\n")
        f.write("BORDER_TEX ../textures/" + BLEND_TEXTURE + "\n")
        f.write("NO_ALPHA\nNO_SHADOW\n")
    return name + ".ter"


def _write_blend(tile):
    import O4_Cliff_Texture as TEX
    from PIL import Image
    path = os.path.join(tile.build_dir, "textures", BLEND_TEXTURE)
    Image.fromarray(TEX.blend_ramp()).save(path)


def _photos(lonlat, dico_customzl, mesh_zl):
    """The photos (texture attributes) under triangles ``lonlat``, the one
    most of them lie on first."""
    centre = lonlat.mean(1)
    count = {}
    for lon, lat in centre[:: max(1, len(centre) // 400)]:
        attrs = dico_customzl[GEO.wgs84_to_orthogrid(lat, lon, mesh_zl)]
        count[attrs] = count.get(attrs, 0) + 1
    return sorted(count, key=lambda a: -count[a])


def _exemplar_tris(lonlat_all, slope, land, foot, lat0):
    lo, hi = EXEMPLAR_SLOPES
    pad_lat = EXEMPLAR_REACH_M / 111320.0
    pad_lon = pad_lat / max(0.1, numpy.cos(numpy.radians(lat0 + 0.5)))
    (lon0, lat0_), (lon1, lat1) = foot.min((0, 1)), foot.max((0, 1))
    c = lonlat_all.mean(1)
    pick = (land & (slope >= lo) & (slope < hi)
            & (c[:, 0] > lon0 - pad_lon) & (c[:, 0] < lon1 + pad_lon)
            & (c[:, 1] > lat0_ - pad_lat) & (c[:, 1] < lat1 + pad_lat))
    return lonlat_all[pick]


def emit_cliff_overlays(tile, nodes, tri_idx, tri_types, node_icoords,
                        idx_node_to_idx_pool, pool_param, point_pools,
                        band_base, pool_nbr, dico_customzl, textured_tris,
                        dico_terrains, overlay_terrains, arm="synth"):
    """Add the cliff overlay patches; return ``(bTERT bytes, plan)``.

    ``arm`` ``xplane`` draws them with the default landclass terrain
    (``O4_Cliff_Library``; no texture to make, so no region cap and an
    empty plan).

    ``nodes`` is the (n, 5) node array (lon, lat, elev, nx, ny) the DSF is
    built from, ``tri_idx`` (m, 3), ``tri_types`` (m,) with 0 = land.  The
    plan has one dict per region: ``texture`` (file name), ``ortho`` (the
    photo most of it lies on), ``photos`` (every photo under it and its
    exemplar candidates, ``ortho`` first), ``foot`` ((k, 3, 2) lon, lat of
    its triangles) and ``exemplar`` (the same for the candidates), which
    ``O4_Cliff_Synth`` reads once the photos are on disk."""
    params = FACES.CliffParams()
    if arm == "xplane":
        params = FACES.CliffParams(max_regions=10 ** 9)
    xyz = FACES.local_metres(nodes[:, 0], nodes[:, 1], nodes[:, 2],
                             tile.lat, tile.lon)
    land = numpy.asarray(tri_types) == 0
    layout: FACES.CliffLayout = FACES.find_cliff_layout(xyz, tri_idx, land,
                                                        params)
    UI.vprint(1, "-> Cliff faces: %d region(s), %d overlay triangle(s), "
                 "%d chart(s); %d small region(s) left to the photo."
              % (len(layout.region_area), len(layout.tris),
                 len(layout.chart_axes), layout.dropped_regions))
    plan = []
    if not len(layout.tris):
        return b"", plan
    if arm == "xplane":
        return LIBRARY.emit_library_overlays(
            tile, layout, tri_idx, nodes[:, :2][tri_idx], node_icoords,
            idx_node_to_idx_pool, point_pools, band_base, textured_tris,
            dico_terrains, overlay_terrains), plan
    _cliff_pool_params(point_pools, pool_param, band_base, pool_nbr)
    _write_blend(tile)
    slope = FACES.triangle_slopes(xyz, tri_idx)[0]
    lonlat_all = nodes[:, :2][tri_idx]
    tag = FNAMES.short_latlon(tile.lat, tile.lon)
    bTERT = b""
    region_terrain = []
    for r, tris in enumerate(layout.region_tris):
        name = "cliff_%s_%03d" % (tag, r)
        terrain_idx = len(dico_terrains)
        dico_terrains[("cliff", r)] = terrain_idx
        overlay_terrains.add(terrain_idx)
        textured_tris[terrain_idx] = {}
        region_terrain.append(terrain_idx)
        bTERT += bytes("terrain/" + _terrain_file(tile, name) + "\0", "ascii")
        foot = lonlat_all[tris]
        exemplar = _exemplar_tris(lonlat_all, slope, land, foot, tile.lat)
        photos = _photos(foot, dico_customzl, tile.mesh_zl)
        if len(exemplar):
            photos += [a for a in _photos(exemplar, dico_customzl,
                                          tile.mesh_zl) if a not in photos]
        plan.append({"texture": name + ".dds", "ortho": photos[0],
                     "photos": photos, "foot": foot, "exemplar": exemplar})
    _emit_charts(layout, xyz, tri_idx, node_icoords, idx_node_to_idx_pool,
                 point_pools, band_base, region_terrain, textured_tris,
                 params.repeat_m)
    return bTERT, plan


def _chart_points(layout, chart_id, tris, xyz, tri_idx, repeat_m):
    """``{node: (s, t)}`` quantised face coordinates of one chart."""
    nodes = numpy.unique(tri_idx[tris])
    uv = layout.chart_uv(chart_id, xyz[nodes], repeat_m)
    uv -= numpy.floor(uv.min(0))
    if uv.max() > UV_RANGE:
        UI.vprint(2, "     cliff chart", chart_id, "wider than the UV range;"
                     " clamped.")
    q = numpy.round(numpy.clip(uv / UV_RANGE, 0.0, 1.0) * 65535).astype(int)
    return dict(zip(nodes.tolist(), map(tuple, q.tolist()), strict=True))


def _emit_charts(layout, xyz, tri_idx, node_icoords, idx_node_to_idx_pool,
                 point_pools, band_base, region_terrain, textured_tris,
                 repeat_m):
    by_chart = {}
    for t, c in zip(layout.tris.tolist(), layout.chart.tolist(), strict=True):
        by_chart.setdefault(c, []).append(t)
    for chart_id, tris in by_chart.items():
        terrain = textured_tris[region_terrain[layout.chart_region[chart_id]]]
        st = _chart_points(layout, chart_id, tris, xyz, tri_idx, repeat_m)
        slots = {}
        for t in tris:
            n1, n2, n3 = tri_idx[t].tolist()
            tri_p = array.array("H")
            for n in (n1, n3, n2):  # X-Plane's winding, as the base mesh
                if n not in slots:
                    pool, pos = point_pools.slot(idx_node_to_idx_pool[n]
                                                 + band_base)
                    point_pools.points[pool].extend(
                        node_icoords[5 * n: 5 * n + 5])
                    a = float(layout.alpha[n])
                    point_pools.points[pool].extend(
                        (*st[n], 32768, int(round(a / 2 * 65535))))
                    slots[n] = (pool, pos)
                tri_p.extend(slots[n])
            if (tri_p[:2] == tri_p[2:4] or tri_p[2:4] == tri_p[4:]
                    or tri_p[4:] == tri_p[:2]):
                continue
            if tri_p[0] == tri_p[2] == tri_p[4]:
                terrain.setdefault(tri_p[0], array.array("H")).extend(
                    (tri_p[1], tri_p[3], tri_p[5]))
            else:
                terrain.setdefault("cross-pool", array.array("H")).extend(tri_p)
