"""The cliff overlay drawn with X-Plane's own terrain (#2096, ``xplane`` arm).

The ``synth`` arm (``O4_Cliff_DSF``) gives each cliff region a texture made
from the tile's photos.  This arm instead draws the cliff overlay with the
terrain X-Plane's DEFAULT mesh puts at that spot: the landclass ``.ter`` of
the default Global Scenery DSF (``O4_Default_Terrain_Map``), referenced by
its library path, so the simulator picks the regional variant and its own
slope textures.  Those terrains are ``PROJECTED`` (top-down, like the photo)
but carry ``AUTO_SLOPE_HILL`` / ``AUTO_SLOPE_CLIFF`` directives: past
~57-62 degrees X-Plane swaps in a rock-cliff texture aligned with the slope
heading (``AUTO_SLOPE_HEADING``) whose metre size is pre-squashed along the
fall line (e.g. 2160 x 1080 m), so it is unstretched near 60 degrees and
stretches again on steeper faces.

The overlay is X-Plane's own overlay form: a flag-2 patch whose points have
7 planes ``(lon, lat, elev, nx, ny, s, t)``, ``(s, t)`` reading the
terrain's ``BORDER_TEX`` (a ramp along ``s``: 0 transparent, 1 opaque), so
``s`` is the node's alpha and the cliff fades into the photo.  No texture is
made or shipped; the terrain lives in the simulator's library.
"""
from __future__ import annotations

import array
from collections import Counter

import numpy
import O4_Default_Terrain_Map as DEFTER
import O4_UI_Utils as UI

__all__ = ["PLANES", "emit_library_overlays"]

#: Plane count of an overlay point on a projected terrain with a border.
PLANES = 7


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
    terrain_map = DEFTER.DefaultTerrainMap.from_tile(tile.lat, tile.lon)
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
