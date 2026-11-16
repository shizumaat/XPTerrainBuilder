"""The cliff overlay drawn with X-Plane's own terrain (#2096, ``xplane`` arm).

The ``synth`` arm (``O4_Cliff_DSF``) gives each cliff region a texture made
from the tile's photos.  This arm instead draws the cliff overlay with the
terrain X-Plane's DEFAULT mesh puts at that spot: the landclass ``.ter`` of
the default Global Scenery DSF (``O4_Default_Terrain_Map``), referenced by
its library path, so the simulator picks the regional variant and its own
slope textures.  Those terrains are ``PROJECTED`` (top-down, like the photo)
but carry ``AUTO_SLOPE_HILL`` / ``AUTO_SLOPE_CLIFF`` directives: past
~57-62 degrees X-Plane swaps in a rock-cliff texture aligned with the slope
heading (``AUTO_SLOPE_HEADING``), W x H projected metres (e.g. 2160 x
1080 m) of a face-on rock photo, so X-Plane itself stretches it down the
fall line by ``H / (W cos a)``; the ``xpface`` arm lays it W x H on the
face instead (:class:`_CliffTexture`).

The overlay is X-Plane's own overlay form: a flag-2 patch whose points have
7 planes ``(lon, lat, elev, nx, ny, s, t)``, ``(s, t)`` reading the
terrain's ``BORDER_TEX`` (a ramp along ``s``: 0 transparent, 1 opaque), so
``s`` is the node's alpha and the cliff fades into the photo.  No texture is
made or shipped; the terrain lives in the simulator's library.
"""
from __future__ import annotations

import array
import os
import struct
from collections import Counter
from typing import NamedTuple

import numpy
import O4_Default_Terrain_Map as DEFTER
import O4_UI_Utils as UI

__all__ = ["MATERIAL_KEYS", "PLANES", "emit_library_overlays",
           "install_texture", "region_cliff_textures", "region_slope_bands",
           "scenery_dir"]

#: Plane count of an overlay point on a projected terrain with a border.
PLANES = 7


def scenery_dir():
    """The Custom Scenery folder set in the app (``custom_scenery_dir``):
    with no ``custom_overlay_src``, the default DSF is read from the
    ``Global Scenery`` beside it, as the overlay step does."""
    import O4_Config_Utils as CFG
    return getattr(CFG, "custom_scenery_dir", "") or ""


def _triangle_terrains(terrain_map, lonlat):
    """Library path per triangle (``lonlat`` (k, 3, 2)); a water or
    unprojected landclass takes its region's running majority, as the
    default-land path does."""
    paths = terrain_map.terrain_paths
    out, majority = [], Counter()
    for lon, lat in lonlat.mean(1):
        i = terrain_map.terrain_index_at(lon, lat)
        path = paths[i] if 0 <= i < len(paths) else ""
        if (not path or DEFTER.is_water_terrain(path)
                or terrain_map.is_projected(i) is False):
            path = majority.most_common(1)[0][0] if majority else ""
        else:
            majority[path] += 1
        out.append(path)
    fallback = majority.most_common(1)[0][0] if majority else ""
    return [p or fallback for p in out]


def emit_library_overlays(tile, layout, tri_idx, lonlat, node_icoords,
                          idx_node_to_idx_pool, point_pools, band_base,
                          textured_tris, dico_terrains, overlay_terrains):
    """Draw ``layout``'s triangles as overlay patches of the default
    landclass terrain; return the ``bTERT`` bytes of the terrains added
    (empty when the default Global Scenery DSF cannot be read)."""
    terrain_map = DEFTER.DefaultTerrainMap.from_tile(tile.lat, tile.lon,
                                                     scenery_dir())
    if terrain_map is None:
        UI.lvprint(1, "WARNING: cliff_textures=xplane needs the default "
                      "Global Scenery DSF of this tile; no cliff overlay.")
        return b""
    terrains = _triangle_terrains(terrain_map, lonlat[layout.tris])
    if not any(terrains):
        return b""
    UI.vprint(1, "-> Cliff faces (X-Plane terrain): %d terrain(s): %s"
              % (len(set(terrains)), ", ".join(
                  "%s x%d" % (p.rsplit("/", 1)[-1], n)
                  for p, n in Counter(terrains).most_common(4))))
    bTERT = b""
    slots = {}
    alpha = numpy.clip(layout.alpha, 0.0, 1.0)
    for t, path in zip(layout.tris.tolist(), terrains, strict=True):
        if not path:
            continue
        key = ("cliff-xp", path)
        if key not in dico_terrains:
            dico_terrains[key] = len(dico_terrains)
            overlay_terrains.add(dico_terrains[key])
            textured_tris[dico_terrains[key]] = {}
            bTERT += bytes(path + "\0", "ascii")
        terrain = textured_tris[dico_terrains[key]]
        tri_p = array.array("H")
        for n in (tri_idx[t, 0], tri_idx[t, 2], tri_idx[t, 1]):
            n = int(n)
            if n not in slots:
                pool, pos = point_pools.slot(idx_node_to_idx_pool[n]
                                             + band_base)
                point_pools.points[pool].extend(
                    node_icoords[5 * n: 5 * n + 5])
                point_pools.points[pool].extend(
                    (int(round(float(alpha[n]) * 65535)), 0))
                slots[n] = (pool, pos)
            tri_p.extend(slots[n])
        if tri_p[0] == tri_p[2] == tri_p[4]:
            terrain.setdefault(tri_p[0], array.array("H")).extend(
                (tri_p[1], tri_p[3], tri_p[5]))
        else:
            terrain.setdefault("cross-pool", array.array("H")).extend(tri_p)
    return bTERT


# ── the ``xpface`` arm: X-Plane's cliff texture, laid in face charts ────

#: The scenery pack whose library.txt carries the landclass terrains.
_WORLD_TERRAIN = os.path.join("Resources", "default scenery",
                              "1000 world terrain")


def _world_library(xplane_root):
    """``{virtual path: physical .ter}`` of the generic (``REGION all``),
    summer entries of the world-terrain library.  The shared resolver
    (``auto_patch.agp_reader``) reads ``EXPORT`` only, and every landclass
    terrain is an ``EXPORT_EXCLUDE`` / ``EXPORT_EXCLUDE_SEASON`` row."""
    root = os.path.join(xplane_root, _WORLD_TERRAIN)
    out, region = {}, None
    try:
        lines = open(os.path.join(root, "library.txt"), encoding="utf-8",
                     errors="replace").read().splitlines()
    except OSError:
        return out
    for line in lines:
        f = line.split()
        if f[:1] == ["REGION"]:
            region = f[1] if len(f) > 1 else None
        elif region == "all" and f and f[0].startswith("EXPORT"):
            if f[0].endswith("_SEASON"):
                if "sum" not in f[1].split(","):
                    continue
                f = f[1:]
            if len(f) >= 3:
                out.setdefault(f[1], os.path.normpath(
                    os.path.join(root, f[2])))
    return out


#: ``.ter`` lines of the landclass that are carried into the cliff terrain:
#: its detail decals (``DECAL_LIB``, X-Plane's fine detail layer; projected
#: or keyed on the texture, so they need no extra point planes) and its
#: material roughness.  ``NORMAL_TEX`` is left out: in the landclasses it
#: is a turf normal map scaled on the BASE texture, not on the rock.
MATERIAL_KEYS = ("DECAL_LIB", "SUPER_ROUGHNESS")


class _CliffTexture(NamedTuple):
    """A landclass's ``AUTO_SLOPE_CLIFF`` texture: the DDS, the metres of
    face one repeat covers along the contour (``width_m``) and down the
    fall line (``height_m``), and the landclass's :data:`MATERIAL_KEYS`
    lines."""
    dds: str
    width_m: float
    height_m: float
    material: tuple = ()


def _ter_lines(ter_path):
    """``(lines, material)`` of a ``.ter`` file (``material``: its
    :data:`MATERIAL_KEYS` lines), or None when it cannot be read."""
    try:
        lines = open(ter_path, encoding="utf-8", errors="replace").read(
        ).splitlines()
    except OSError:
        return None
    material = tuple(" ".join(f) for f in map(str.split, lines)
                     if f[:1] and f[0] in MATERIAL_KEYS)
    return lines, material


def _face_texture(ter_path, row, material):
    """The :class:`_CliffTexture` of an ``AUTO_SLOPE_* W H lo hi dds`` row
    (split), or None when its DDS is missing: W m along the contour and
    ``W * rows / columns`` m down the fall line (H when the DDS header
    cannot be read)."""
    dds = os.path.normpath(os.path.join(os.path.dirname(ter_path), row[5]))
    if not os.path.isfile(dds):
        return None
    width = float(row[1])
    size = _dds_size(dds)
    height = width * size[1] / size[0] if size else float(row[2])
    return _CliffTexture(dds, width, height, material)


def _cliff_texture(ter_path):
    """The :class:`_CliffTexture` of a ``.ter`` file, or None.

    ``AUTO_SLOPE_CLIFF W H lo hi dds``: the art is a face-on photo of
    rock, so it is unstretched on the face when its pixels are square
    there: W m along the contour and ``W * rows / columns`` m down the fall
    line (2048 x 512 px -> 2840 x 710 m).  That is the ``.ter``'s own H on
    most rows, but not all (``cliff_tmp_wet``, 2048 x 512 px, is also
    listed at 2160 x 1080 m), so the pixels decide; H only when the DDS
    header cannot be read.  (#2096 follow-up: one W on both axes
    stretched the fall line x4 here, the owner's vertical streaks.)"""
    read = _ter_lines(ter_path)
    if read is None:
        return None
    lines, material = read
    for line in lines:
        f = line.split()
        if f[:1] == ["AUTO_SLOPE_CLIFF"] and len(f) >= 6:
            found = _face_texture(ter_path, f, material)
            if found:
                return found
    return None


class _SlopeBands(NamedTuple):
    """What a landclass draws by slope, below its cliff texture (#2102
    follow-up): ``hill`` its ``AUTO_SLOPE_HILL`` texture laid on a face
    (a :class:`_CliffTexture`) and ``hill_projected`` its ``(W, H)`` metres
    projected from above; ``base`` its ``BASE_TEX`` at its ``PROJECTED``
    size; ``hill_band`` / ``cliff_band`` the ``(lo, hi)`` degrees over
    which X-Plane fades the hill and the cliff texture in.  ``hill`` or
    ``base`` is None when its DDS is missing."""
    hill: object
    hill_projected: tuple
    base: object
    hill_band: tuple
    cliff_band: tuple


def _slope_bands(ter_path):
    """The :class:`_SlopeBands` of a ``.ter`` file, or None when it has no
    ``AUTO_SLOPE_HILL`` and ``AUTO_SLOPE_CLIFF`` rows."""
    read = _ter_lines(ter_path)
    if read is None:
        return None
    lines, material = read
    rows = {}
    for line in lines:
        f = line.split()
        if f[:1] and f[0] not in rows:
            rows[f[0]] = f
    hill, cliff = rows.get("AUTO_SLOPE_HILL"), rows.get("AUTO_SLOPE_CLIFF")
    if not (hill and cliff and len(hill) >= 6 and len(cliff) >= 6):
        return None
    base = None
    tex, size = rows.get("BASE_TEX"), rows.get("PROJECTED")
    if tex and size and len(tex) >= 2 and len(size) >= 3:
        dds = os.path.normpath(os.path.join(os.path.dirname(ter_path),
                                            tex[1]))
        if os.path.isfile(dds):
            base = _CliffTexture(dds, float(size[1]), float(size[2]),
                                 material)
    return _SlopeBands(_face_texture(ter_path, hill, material),
                       (float(hill[1]), float(hill[2])), base,
                       (float(hill[3]), float(hill[4])),
                       (float(cliff[3]), float(cliff[4])))


def _dds_size(path):
    """``(columns, rows)`` of a DDS file from its header, or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b"DDS ":
        return None
    rows, columns = struct.unpack("<II", head[12:20])
    return (columns, rows) if rows and columns else None


def _region_landclasses(tile, lonlat, region_tris, warn):
    """Per region, the physical ``.ter`` of the landclass the default DSF
    has under most of its triangles (None when the library lacks it); an
    empty list when the default DSF or the X-Plane install cannot be
    read (``warn`` then names the arm that needed it)."""
    terrain_map = DEFTER.DefaultTerrainMap.from_tile(tile.lat, tile.lon,
                                                     scenery_dir())
    root = getattr(terrain_map, "_xplane_root", None)
    if terrain_map is None or not root:
        UI.lvprint(1, "WARNING: %s needs the default Global Scenery DSF and"
                      " the X-Plane install; no cliff overlay." % warn)
        return []
    library = _world_library(root)
    out = []
    for tris in region_tris:
        paths = [p for p in _triangle_terrains(terrain_map, lonlat[tris])
                 if p]
        path = Counter(paths).most_common(1)[0][0] if paths else ""
        out.append(library.get(path))
    return out


def _per_landclass(ters, read):
    seen = {}
    for ter in ters:
        if ter not in seen:
            seen[ter] = read(ter) if ter else None
    return [seen[ter] for ter in ters]


def region_cliff_textures(tile, lonlat, region_tris):
    """Per region, the cliff texture of the landclass the default DSF has
    under most of its triangles (None when it has none); ``lonlat`` is
    every mesh triangle's (3, 2) lon, lat.  An empty list when the default
    DSF or the X-Plane install cannot be read."""
    return _per_landclass(_region_landclasses(
        tile, lonlat, region_tris, "cliff_textures=xpface"), _cliff_texture)


def region_slope_bands(tile, lonlat, region_tris):
    """Per region, the :class:`_SlopeBands` of the same landclass as
    :func:`region_cliff_textures` (None when it has none)."""
    return _per_landclass(_region_landclasses(
        tile, lonlat, region_tris, "the cliff overlay's slope bands"),
        _slope_bands)


def _shared_name(dds_path):
    """``xp_textures10_soil_cliff_wrm_dry.dds``: the texture's path under
    the world-terrain pack, flattened (two seasons share base names)."""
    path = dds_path.replace("\\", "/")
    marker = _WORLD_TERRAIN.replace("\\", "/").rsplit("/", 1)[-1] + "/"
    rest = path.split(marker, 1)[1] if marker in path else (
        path.rsplit("/", 1)[-1])
    return "xp_" + rest.replace("/", "_")


def install_texture(tile, cliff_texture):
    """Place X-Plane's texture ONCE per pack, never copied per tile (owner
    2026-11-15): in the build's ``textures/_shared/`` as a link to the
    user's own install (``O4_World_Pack.share_file``: symbolic link, else
    hard link, else a copy).  When the tiles' home is the World pack, the
    pack's own ``textures/_shared/`` file is placed first and the build's
    is linked to it, so even a copy is made once.  Returns the texture's
    path relative to ``textures/`` (what the ``.ter`` names) and how the
    build's file was placed."""
    import O4_File_Names as FNAMES
    import O4_World_Pack as WP
    name = _shared_name(cliff_texture[0])
    source = cliff_texture[0]
    world = FNAMES.world_home()
    if world:
        home = os.path.join(world, "textures", WP.SHARED_DIR, name)
        WP.share_file(source, home, symlink=True)
        source = home
    how = WP.share_file(source, os.path.join(
        tile.build_dir, "textures", WP.SHARED_DIR, name), symlink=True)
    return WP.SHARED_DIR + "/" + name, how
