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
import hashlib
import os
from collections import Counter

import numpy
import O4_Cliff_Bands as BANDS
import O4_Cliff_Faces as FACES
import O4_Cliff_Library as LIBRARY
import O4_Cliff_Photos as PHOTOS
import O4_Cliff_Shade as SHADE
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Overlay_Utils as OVL
import O4_Tile_Staging as STAGING
import O4_UI_Utils as UI
import O4_World_Pack as WP

__all__ = ["ARMS", "BLEND_TEXTURE", "UV_RANGE", "add_cliff_band",
           "tile_arm", "emit_cliff_overlays"]

#: ``cliff_textures`` values that draw the overlay (``xpface`` is the
#: default since 2026-11-15, owner: "add it to the app to be used on all
#: tiles going forward"; ``False`` is off): ``synth`` (a texture
#: made from the tile's photos), ``xplane`` (X-Plane's own default
#: landclass terrain, ``O4_Cliff_Library``, projected from above as
#: X-Plane draws it) and ``xpface`` (that landclass's cliff texture laid
#: in this module's face charts, so it is not stretched).
ARMS = ("synth", "xplane", "xpface")

#: The X-Plane arms' alpha ramp (degrees): the overlay only where X-Plane's
#: landclasses switch to their cliff texture (``AUTO_SLOPE_CLIFF .. 57 62``).
XP_SLOPES = (58.0, 68.0)
#: Face coordinates are stored in 0 .. UV_RANGE repeats (65,535 steps: a
#: 480 m repeat is quantised to 0.47 m).
UV_RANGE = 64.0
#: The alpha ramp every cliff terrain's ``BORDER_TEX`` reads: one file per
#: pack in ``textures/_shared/`` (``O4_World_Pack.SHARED_DIR``), like the
#: X-Plane textures -- it is the same bytes on every tile.
BLEND_TEXTURE = "cliff_blend.png"
#: Exemplar pixels are taken from triangles this sloped (degrees): the
#: mountain's own flanks, unstretched (1 / cos 42 = 1.35) and not the flat
#: floor around it where roofs and fields are.
EXEMPLAR_SLOPES = (15.0, 42.0)
#: ... and within this distance (m) of the region's bounding box.
EXEMPLAR_REACH_M = 1500.0


def _cliff_arm(value):
    """The arm a ``cliff_textures`` value selects, or None (off).  ``True``
    (the option's first, boolean form) is ``synth``."""
    value = str(value).strip().lower()
    if value == "true":
        return "synth"
    return value if value in ARMS else None


def tile_arm(tile, texture_mode):
    """The arm this tile's DSF draws, or None: the option's arm on a
    ``full_ortho`` tile, except that an X-Plane arm with no default Global
    Scenery DSF to read (no X-Plane install set, or the tile not in it)
    is off for the tile -- one line says so, never an error, and the DSF
    is the bytes the option off writes."""
    arm = _cliff_arm(getattr(tile, "cliff_textures", False))
    if arm is None or texture_mode != "full_ortho":
        return None
    if arm in ("xplane", "xpface") and OVL.source_dsf(
            tile.lat, tile.lon, LIBRARY.scenery_dir()) is None:
        UI.vprint(1, "-> Cliff faces: off for this tile (0 region(s)): no "
                     "X-Plane default scenery found for it (Settings: the "
                     "Global Scenery folder).")
        return None
    return arm


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


def _terrain_file(tile, name, texture=None, material=()):
    """Write ``terrain/<name>.ter``; ``texture`` is its ``BASE_TEX`` path
    under ``textures/`` (default ``<name>.dds``), ``material`` the source
    landclass's lines it carries (``O4_Cliff_Library.MATERIAL_KEYS``)."""
    path = os.path.join(STAGING.terrain_dir(tile), name + ".ter")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("A\n800\nTERRAIN\n\n")
        f.write("BASE_TEX ../textures/" + (texture or name + ".dds") + "\n")
        f.write("BORDER_TEX ../textures/" + _BLEND_REL + "\n")
        f.write("NO_ALPHA\nNO_SHADOW\n")
        f.writelines(line + "\n" for line in material)
    return name + ".ter"


_BLEND_REL = WP.SHARED_DIR + "/" + BLEND_TEXTURE


def _write_blend(tile):
    """The ramp in the build's ``textures/_shared/``, once."""
    path = os.path.join(tile.build_dir, "textures", _BLEND_REL)
    if os.path.isfile(path):
        return
    import O4_Cliff_Texture as TEX
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
    if arm in ("xplane", "xpface"):
        # No texture to make, so no region cap; and only the faces X-Plane
        # itself draws with its cliff texture (AUTO_SLOPE_CLIFF 57-62).
        params = FACES.CliffParams(max_regions=10 ** 9, slope_lo=XP_SLOPES[0],
                                   slope_hi=XP_SLOPES[1])
    xyz = FACES.local_metres(nodes[:, 0], nodes[:, 1], nodes[:, 2],
                             tile.lat, tile.lon)
    land = numpy.asarray(tri_types) == 0
    try:
        layout: FACES.CliffLayout = FACES.find_cliff_layout(
            xyz, tri_idx, land, params)
    except Exception as error:      # nothing added yet: the tile as off
        UI.vprint(1, "-> Cliff faces: off for this tile (0 region(s)): "
                     "the face search failed (%s)." % (error,))
        return b"", []
    extra = None
    if arm == "xpface" and len(layout.tris):
        layout, extra = _over_shadow(tile, layout, xyz, nodes, tri_idx,
                                     land, params, dico_customzl)
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
    if arm == "xpface":
        emit = (layout, xyz, tri_idx, node_icoords, idx_node_to_idx_pool,
                point_pools, band_base)
        terrains = (dico_terrains, overlay_terrains, textured_tris)
        bTERT, cliff_alpha = b"", None
        if extra is not None:
            bTERT, cliff_alpha = _slope_band_layers(
                tile, emit, lonlat_all, slope, land, params, extra,
                terrains)
        tert, region_terrain, repeats = _xplane_face_terrains(
            tile, layout, lonlat_all, *terrains)
        _emit_charts(*emit, region_terrain, textured_tris, repeats,
                     alpha=cliff_alpha)
        return bTERT + tert, plan
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
                 [params.repeat_m] * len(region_terrain))
    return bTERT, plan


def _over_shadow(tile, layout, xyz, nodes, tri_idx, land, params,
                 dico_customzl):
    """``(layout, extra)``: ``layout`` carried over the photo's shadow next
    to its regions (``O4_Cliff_Shade``) and the carried node opacity, or
    ``(layout, None)`` when no region touches dark photo or the read fails
    (the DSF is then the bytes without it)."""
    try:
        extra, stats = SHADE.shadow_alpha(
            layout, xyz, nodes[:, :2], tri_idx, land,
            PHOTOS.photo_lookup(dico_customzl, tile.mesh_zl),
            PHOTOS.photo_reader(tile),
            PHOTOS.photo_reader(tile, fetch=False))
        if extra is not None:
            layout = FACES.find_cliff_layout(xyz, tri_idx, land, params,
                                             extra_alpha=extra)
    except Exception as error:
        UI.vprint(1, "-> Cliff faces over shadow: not read (%s); the "
                     "overlay ends at the slope ramp." % (error,))
        return layout, None
    UI.vprint(1, "-> Cliff faces over shadow: " + stats.line())
    return layout, extra


def _xplane_face_terrains(tile, layout, lonlat_all, dico_terrains,
                          overlay_terrains, textured_tris):
    """``xpface``: one terrain per X-Plane cliff texture and landclass
    material; per region its terrain index (None: its landclass has no
    cliff texture) and ``(contour, fall line)`` metres per repeat."""
    textures, placed = _placed_face_textures(tile, lonlat_all,
                                             layout.region_tris)
    bTERT, region_terrain, repeats = _face_terrains(
        tile, textures, placed, "cliff_", dico_terrains, overlay_terrains,
        textured_tris)
    used = Counter("%s %gx%g m%s" % (
        placed[t.dds][0], t.width_m, t.height_m,
        " + " + "; ".join(t.material) if t.material else "")
        for t in textures if t)
    UI.vprint(1, "-> Cliff faces (X-Plane cliff textures): %s; %d region(s)"
                 " without one (left to the photo); placed as %s." % (
                     dict(used), sum(t is None for t in textures),
                     sorted({how for _t, how in placed.values()})))
    return bTERT, region_terrain, repeats


def _face_terrains(tile, textures, placed, prefix, dico_terrains,
                   overlay_terrains, textured_tris):
    """``(bTERT, region_terrain, repeats)``: one overlay terrain per
    (texture, material) of ``textures`` (per region a placed
    ``_CliffTexture`` or None), named with ``prefix``; per region its
    terrain index (None: not drawn) and ``(W, H)`` metres per repeat."""
    bTERT, region_terrain, repeats = b"", [], []
    for tex in textures:
        if tex is None:
            region_terrain.append(None)
            repeats.append(0.0)
            continue
        texture = placed[tex.dds][0]
        name = _face_terrain_name(texture, tex.material, prefix)
        if ("cliff", name) not in dico_terrains:
            terrain_idx = len(dico_terrains)
            dico_terrains[("cliff", name)] = terrain_idx
            overlay_terrains.add(terrain_idx)
            textured_tris[terrain_idx] = {}
            bTERT += bytes("terrain/" + _terrain_file(
                tile, name, texture, tex.material) + "\0", "ascii")
        region_terrain.append(dico_terrains[("cliff", name)])
        repeats.append((tex.width_m, tex.height_m))
    return bTERT, region_terrain, repeats


def _slope_band_layers(tile, emit, lonlat_all, slope, land, params, extra,
                       terrains):
    """Over the carried part of the overlay, the landclass's base and hill
    textures under its cliff texture, faded in by slope
    (``O4_Cliff_Bands``); returns the base and hill terrains' ``bTERT``
    (registered and drawn BEFORE the cliff layer, so under it) and the
    cliff layer's node opacity.  A region whose landclass gives no bands
    draws the cliff layer only, at the default bands."""
    layout, xyz, tri_idx = emit[:3]
    n = len(xyz)
    try:
        bands = LIBRARY.region_slope_bands(tile, lonlat_all,
                                           layout.region_tris)
    except Exception as error:
        UI.vprint(1, "-> Cliff faces: slope bands not read (%s)." % (error,))
        bands = []
    bands = list(bands) + [None] * (len(layout.region_tris) - len(bands))
    steepest = FACES.node_steepest(tri_idx, slope, land, n)
    alphas = BANDS.band_alphas(
        steepest, FACES.slope_ramp(steepest, params.slope_lo,
                                   params.slope_hi), extra,
        BANDS.node_bands(layout, tri_idx, [
            b and (*b.hill_band, *b.cliff_band) for b in bands], n))
    hill = [b and b.hill for b in bands]
    base = [b and b.base for b in bands]
    placed = _place_textures(tile, [t for t in hill + base if t])
    bTERT = b""
    for layer, textures in (("base", base), ("hill", hill)):
        textures = [t if t and t.dds in placed else None for t in textures]
        tert, region_terrain, repeats = _face_terrains(
            tile, textures, placed, "cliff_%s_" % layer, *terrains)
        bTERT += tert
        if layer == "base":
            _emit_charts(*emit, region_terrain, terrains[2], repeats,
                         alpha=alphas["base"], plan_only=True)
        else:
            _emit_charts(*emit, region_terrain, terrains[2], repeats,
                         alpha=alphas["hill"], plan_repeats=[
                             b.hill_projected if b else 0.0 for b in bands])
    _report_bands(layout, tri_idx, extra, alphas, bands)
    return bTERT, alphas["cliff"]


def _report_bands(layout, tri_idx, extra, alphas, bands):
    carried = layout.tris[extra[tri_idx[layout.tris]].max(1) > 0]
    top = numpy.bincount(BANDS.dominant_layers(tri_idx, carried, alphas),
                         minlength=3)
    no_rock = int((alphas["cliff"][tri_idx[carried]].max(1) <= 0).sum())
    UI.vprint(1, "-> Cliff faces slope bands: %d carried triangle(s) of %d;"
                 " shown as base %d, hill %d, cliff %d; %d with no cliff "
                 "texture at all; %d of %d region(s) with landclass bands."
              % (len(carried), len(layout.tris), *top.tolist(), no_rock,
                 sum(b is not None for b in bands), len(bands)))


def _face_terrain_name(texture, material, prefix="cliff_"):
    """``cliff_<texture>[_<material hash>]``: one terrain per (texture,
    landclass material), so two landclasses sharing a rock texture but not
    a decal never share a ``.ter``; ``prefix`` keeps the slope layers'
    terrains apart from the cliff layer's."""
    name = prefix + texture.rsplit("/", 1)[-1][: -len(".dds")]
    if material:
        name += "_" + hashlib.sha1("\n".join(material).encode(
            "utf-8")).hexdigest()[:8]
    return name


def _placed_face_textures(tile, lonlat_all, region_tris):
    """Per region the X-Plane cliff texture (``_CliffTexture``) its
    terrain is drawn with, or None -- no landclass cliff texture, a DDS
    the install lacks, or one that could not be placed in
    ``textures/_shared``: that region is left to the photo, as with the
    option off.  Also ``{dds: (relative path, how placed)}``.  Never
    raises: a failure to read the install leaves every region None."""
    try:
        textures = LIBRARY.region_cliff_textures(tile, lonlat_all,
                                                 region_tris)
    except Exception as error:
        UI.vprint(1, "-> Cliff faces: X-Plane's cliff textures could not "
                     "be read (%s); the regions are left to the photo."
                  % (error,))
        textures = []
    textures = list(textures) + [None] * (len(region_tris) - len(textures))
    placed = _place_textures(tile, [t for t in textures if t])
    return [t if t and t[0] in placed else None for t in textures], placed


def _place_textures(tile, textures):
    """``{dds: (relative path, how placed)}`` of the ``_CliffTexture``s
    placed in ``textures/_shared``; one that cannot be is left out."""
    placed = {}
    for tex in {t[0]: t for t in textures}.values():
        try:
            placed[tex[0]] = LIBRARY.install_texture(tile, tex)
        except OSError as error:
            UI.vprint(1, "-> Cliff faces: could not place", tex[0],
                      "(%s); its regions are left to the photo." % (error,))
    return placed


def _chart_points(layout, chart_id, tris, xyz, tri_idx, repeat_m):
    """``{node: (s, t)}`` quantised face coordinates of one chart;
    ``repeat_m`` is metres of face per repeat, one number or ``(along the
    contour, down the fall line)``."""
    nodes = numpy.unique(tri_idx[tris])
    uv = layout.chart_uv(chart_id, xyz[nodes], numpy.asarray(repeat_m,
                                                             float))
    uv -= numpy.floor(uv.min(0))
    if uv.max() > UV_RANGE:
        UI.vprint(2, "     cliff chart", chart_id, "wider than the UV range;"
                     " clamped.")
    q = numpy.round(numpy.clip(uv / UV_RANGE, 0.0, 1.0) * 65535).astype(int)
    return dict(zip(nodes.tolist(), map(tuple, q.tolist()), strict=True))


def _emit_charts(layout, xyz, tri_idx, node_icoords, idx_node_to_idx_pool,
                 point_pools, band_base, region_terrain, textured_tris,
                 repeats, alpha=None, plan_repeats=None, plan_only=False):
    """``repeats[r]``: metres of face per texture repeat in region r (one
    number, or per axis as :func:`_chart_points` takes it); a
    region whose terrain is None is not drawn.  ``alpha`` (n,) node
    opacity (default the layout's; a triangle with none is not drawn),
    ``plan_repeats[r]`` the repeats on region r's plan chart (default
    ``repeats``), ``plan_only``: every triangle in its plan chart."""
    alpha = layout.alpha if alpha is None else alpha
    plan = layout.plan_charts()
    by_chart = {}
    for t, c in zip(layout.tris.tolist(), layout.chart.tolist(), strict=True):
        if plan_only:
            c = plan[layout.chart_region[c]]
        by_chart.setdefault(c, []).append(t)
    for chart_id, tris in by_chart.items():
        region = layout.chart_region[chart_id]
        if region_terrain[region] is None:
            continue
        tris = [t for t in tris if alpha[tri_idx[t]].max() > 0]
        if not tris:
            continue
        terrain = textured_tris[region_terrain[region]]
        st = _chart_points(layout, chart_id, tris, xyz, tri_idx,
                           plan_repeats[region] if plan_repeats is not None
                           and chart_id == plan[region] else repeats[region])
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
                    a = float(alpha[n])
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
