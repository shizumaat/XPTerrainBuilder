"""The cliff overlay carried over the photo's shadow (#2102).

An orthophoto of a mountain often has the face and its foot in shadow,
nearly black.  The cliff overlay (``O4_Cliff_DSF``) covers only what is
steep enough for X-Plane's cliff texture, so a pilot saw rock, then a black
band of photo, then the lit photo.  This module reads the photo under and
around each cliff region and returns an extra opacity per mesh node that
carries the overlay across that dark band and fades it out as the photo
brightens:

* **dark is relative**: the tile's own land luminance is sampled (triangle
  centroids, at a small mip of each photo); a node is fully dark at or
  below ``DARK_FRACTION`` of its median and not dark at all from
  ``LIT_FRACTION`` of it (smoothstep between);
* **only the dark that touches a cliff**: the dark nodes connected to a
  region's nodes through dark nodes, along land edges, at most ``REACH_M``
  from the region (tapered over its last ``RAMP_M``);
* **only below the rim**: a node above its nearest region's mid-height
  is the land on top of the cliff, never its shadow
  (:func:`_below_the_rim`);
* **only where the sun casts it**: a dark region whose face turns toward
  the sun the photo shows (``O4_Cliff_Sun``) is dark rock -- it seeds no
  carry, its nodes are never shadow, and it is named in
  ``stats.rock_regions`` for the caller to leave to the photo;
* **a soft end**: beyond that dark set the opacity ramps from 1 to 0 over
  ``RAMP_M`` of mesh edges, so the overlay never ends on a sharp line.

A region with no dark photo at its nodes gets nothing: :func:`shadow_alpha`
returns None when no region does, and the layout is the one without this
module, byte for byte.  Photos are read through the caller's ``read_photo``
(``O4_Cliff_DSF`` reads a texture's small mip, or its cached JPEG at 1/8
scale); a photo it cannot give is simply not sampled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy
import O4_Cliff_Sun as SUN

__all__ = ["DARK_FRACTION", "LIT_FRACTION", "REACH_M", "RAMP_M",
           "photo_pixel_coords", "shadow_alpha"]

#: Fully dark at or below this fraction of the tile's median land luminance.
DARK_FRACTION = 0.35
#: ... and not dark at all from this fraction up.
LIT_FRACTION = 0.6
#: The overlay is carried at most this far (m, along mesh edges) beyond a
#: cliff region over dark photo ...
REACH_M = 500.0
#: ... and fades out over this distance (m): past the dark band, and over
#: the last part of the reach.
RAMP_M = 80.0
#: Land samples of the tile's reference luminance ...
REFERENCE_SAMPLES = 4000
#: ... read from at most this many photos (the most-sampled first) ...
REFERENCE_PHOTOS = 96
#: ... and below this many readable samples there is no reference.
MIN_REFERENCE = 200


@dataclass
class ShadeStats:
    """What :func:`shadow_alpha` did: ``extension_m`` holds, per extended
    region, how far (m along mesh edges) the overlay now reaches beyond it;
    ``median`` is the tile's land luminance (0..255) and ``dark`` / ``lit``
    the levels the ramp runs between."""
    regions: int = 0
    extension_m: list = field(default_factory=list)
    photos: int = 0
    median: float = float("nan")
    dark: float = float("nan")
    lit: float = float("nan")
    nodes: int = 0
    sun_azimuth: float = float("nan")
    rock_regions: list = field(default_factory=list)

    def line(self):
        ext = numpy.asarray(self.extension_m, float)
        far = ("; reach median %.0f m, max %.0f m" % (numpy.median(ext),
                                                       ext.max())
               if len(ext) else "")
        return ("%d of %d region(s) carried over dark photo (%d node(s))%s;"
                " land luminance median %.0f, dark <= %.0f, lit >= %.0f;"
                " %d photo(s) read%s." % (
                    len(ext), self.regions, self.nodes, far, self.median,
                    self.dark, self.lit, self.photos, self._sun()))

    def _sun(self):
        if not numpy.isfinite(self.sun_azimuth):
            return "; no sun in the photo (no dark-rock witness)"
        return ("; sun azimuth %.0f deg, %d dark sun-facing region(s) are"
                " dark rock, left to the photo" % (self.sun_azimuth,
                                                   len(self.rock_regions)))


def photo_pixel_coords(lonlat, attrs, size):
    """(..., 2) pixel (col, row) of lon/lat points in a ``size``-pixel
    rendering of photo ``attrs`` ``(til_x, til_y, zl, provider)``; beyond
    its edges for points beyond."""
    til_x, til_y, zl = attrs[0], attrs[1], attrs[2]
    lon, lat = lonlat[..., 0], lonlat[..., 1]
    mult = 2 ** (zl - 5)
    s = (lon / 180 + 1) * mult - til_x // 16
    ratio_y = numpy.log(numpy.tan((90 + lat) * numpy.pi / 360)) / numpy.pi
    t = 1 - ((1 - ratio_y) * mult - til_y // 16)
    return numpy.stack((s * size, (1 - t) * size), -1)


def _smoothstep(x):
    x = numpy.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class _Luminance:
    """Rec. 709 luma (0..255) of photo points, box-blurred over 3 x 3 mip
    pixels; each photo read once (a photo a reader could not give is asked
    again of the next reader)."""

    def __init__(self, photo_at):
        self.photo_at = photo_at
        self.cache = {}

    def _image(self, attrs, reader):
        if self.cache.get(attrs) is None:
            rgb = reader(attrs)
            if rgb is None:
                return None
            y = numpy.asarray(rgb, float)[..., :3] @ numpy.array(
                (0.2126, 0.7152, 0.0722))
            pad = numpy.pad(y, 1, mode="edge")
            self.cache[attrs] = sum(pad[i:i + y.shape[0], j:j + y.shape[1]]
                                    for i in range(3) for j in range(3)) / 9.0
        return self.cache[attrs]

    def photos_read(self):
        return len(self.cache)

    def at(self, lonlat, reader, max_photos=None):
        """Luminance of each (lon, lat) point; NaN where no photo."""
        lonlat = numpy.asarray(lonlat, float).reshape(-1, 2)
        out = numpy.full(len(lonlat), numpy.nan)
        groups = {}
        for i, attrs in enumerate(self.photo_at(lonlat)):
            if attrs is not None:
                groups.setdefault(attrs, []).append(i)
        order = sorted(groups, key=lambda a: -len(groups[a]))
        for attrs in order[:max_photos]:
            lum = self._image(attrs, reader)
            if lum is None:
                continue
            idx = numpy.asarray(groups[attrs])
            px = photo_pixel_coords(lonlat[idx], attrs, lum.shape[0])
            c = numpy.clip(px[:, 0].astype(int), 0, lum.shape[1] - 1)
            r = numpy.clip(px[:, 1].astype(int), 0, lum.shape[0] - 1)
            out[idx] = lum[r, c]
        return out


def _land_graph(xyz, tri_idx, land):
    """Sparse symmetric graph of the land triangles' edges, weighted by
    their horizontal length (m)."""
    from scipy.sparse import coo_matrix
    t = tri_idx[land]
    e = numpy.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]))
    e.sort(axis=1)
    e = numpy.unique(e, axis=0)
    w = numpy.maximum(numpy.linalg.norm(xyz[e[:, 0], :2] - xyz[e[:, 1], :2],
                                        axis=1), 1e-3)
    n = len(xyz)
    return coo_matrix((numpy.concatenate((w, w)),
                       (numpy.concatenate((e[:, 0], e[:, 1])),
                        numpy.concatenate((e[:, 1], e[:, 0])))),
                      shape=(n, n)).tocsr()


def _reference(lum, lonlat_tris, land, reader):
    """``(median, ids, values)``: the median land luminance from up to
    REFERENCE_SAMPLES triangle centroids spread over the tile (NaN when
    too few are readable), the sampled triangles and their luminance."""
    ids = numpy.nonzero(land)[0]
    if not len(ids):
        return float("nan"), ids, numpy.zeros(0)
    ids = ids[:: max(1, len(ids) // REFERENCE_SAMPLES)]
    values = lum.at(lonlat_tris[ids].mean(1), reader,
                    max_photos=REFERENCE_PHOTOS)
    read = values[numpy.isfinite(values)]
    if len(read) < MIN_REFERENCE:
        return float("nan"), ids, values
    return float(numpy.median(read)), ids, values


def _rock(stats, layout, xyz, tri_idx, ref_ids, ref_values, near, values):
    """(r,) bool dark-rock regions (``O4_Cliff_Sun``); fills ``stats``."""
    import O4_Cliff_Faces as FACES
    slopes, normals, areas = FACES.triangle_slopes(xyz, tri_idx)
    sun = SUN.sun_direction(ref_values, normals[ref_ids], slopes[ref_ids])
    node_lum = numpy.full(len(xyz), numpy.nan)
    node_lum[near] = values
    rock = SUN.dark_rock_regions(layout.region_tris, tri_idx, node_lum,
                                 stats.median, sun, normals, areas, slopes)
    if sun is not None:
        stats.sun_azimuth = float(numpy.degrees(numpy.arctan2(*sun)) % 360)
    stats.rock_regions = numpy.nonzero(rock)[0].tolist()
    return rock


def _region_reach(layout, tri_idx, new, dist, source):
    """Per extended region (in region order) the farthest new node's
    distance (m) from it."""
    node_region = {}
    for r, tris in enumerate(layout.region_tris):
        for n in numpy.unique(tri_idx[tris]).tolist():
            node_region.setdefault(n, r)
    reach = {}
    for n in new.tolist():
        r = node_region.get(int(source[n]))
        if r is not None:
            reach[r] = max(reach.get(r, 0.0), float(dist[n]))
    return [reach[r] for r in sorted(reach)]


def _below_the_rim(layout, xyz, tri_idx, source):
    """(n,) bool: the node lies no higher than the MID-HEIGHT of the
    cliff region nearest it.  A shadow lies on a face and at its FOOT; dark
    ground at or above a cliff's rim is the land on top (a bluff's dark
    vegetation, an airfield's grass and asphalt -- LPPD 2026-11-17, where
    the carry painted X-Plane's land textures up to 500 m over the bluff
    top and the airport), never the cliff's shadow."""
    n = len(xyz)
    mid_of_node = numpy.full(n, numpy.inf)
    for tris in layout.region_tris:
        nodes = numpy.unique(tri_idx[tris])
        z = xyz[nodes, 2]
        mid_of_node[nodes] = numpy.minimum(mid_of_node[nodes],
                                           0.5 * (z.min() + z.max()))
    src = numpy.asarray(source)
    ok = src >= 0
    mid = numpy.full(n, -numpy.inf)
    mid[ok] = mid_of_node[src[ok]]
    return xyz[:, 2] <= mid


def _dark_core(graph, dark, region_nodes):
    """The dark nodes connected to a region node through dark nodes."""
    from scipy.sparse.csgraph import connected_components
    ids = numpy.nonzero(dark)[0]
    _count, label = connected_components(graph[dark][:, dark],
                                         directed=False)
    seeded = numpy.unique(label[numpy.isin(ids, region_nodes)])
    return ids[numpy.isin(label, seeded)]


def shadow_alpha(layout, xyz, lonlat, tri_idx, land, photo_at, read_photo,
                 read_reference=None):
    """``(extra, stats)``: ``extra`` the (n,) opacity to add (by maximum) to
    the layout's node alpha, or None when no region touches dark photo;
    ``stats`` a :class:`ShadeStats`.

    ``layout`` is the ``O4_Cliff_Faces.CliffLayout`` found without it,
    ``xyz`` (n, 3) node metres, ``lonlat`` (n, 2) node degrees, ``tri_idx``
    (m, 3), ``land`` (m,) bool; ``photo_at(lonlat (k, 2))`` the photo
    attributes ``(til_x, til_y, zl, provider)`` of each point (None: no
    photo) and ``read_photo(attrs)`` its pixels ((s, s, 3), any small mip)
    or None.  ``read_reference`` (default ``read_photo``) reads the photos
    of the tile-wide reference, after the regions' own: a reader that only
    reads what is on disk keeps a fresh build from fetching the tile."""
    from scipy.sparse.csgraph import dijkstra
    stats = ShadeStats(regions=len(layout.region_tris))
    if not len(layout.tris):
        return None, stats
    tri_idx = numpy.asarray(tri_idx).reshape(-1, 3)
    land = numpy.asarray(land, bool)
    graph = _land_graph(xyz, tri_idx, land)
    region_nodes = numpy.unique(tri_idx[layout.tris])
    dist, _pred, source = dijkstra(graph, indices=region_nodes,
                                   min_only=True, return_predecessors=True,
                                   limit=REACH_M + RAMP_M)
    near = numpy.nonzero(numpy.isfinite(dist))[0]
    lum = _Luminance(photo_at)
    values = lum.at(lonlat[near], read_photo)
    stats.median, ref_ids, ref_values = _reference(
        lum, lonlat[tri_idx], land, read_reference or read_photo)
    stats.photos = lum.photos_read()
    stats.dark = DARK_FRACTION * stats.median
    stats.lit = LIT_FRACTION * stats.median
    if not stats.median > 0:
        return None, stats
    ok = numpy.isfinite(values)
    shade = numpy.zeros(len(xyz))
    shade[near[ok]] = 1.0 - _smoothstep(
        (values[ok] - stats.dark) / (stats.lit - stats.dark))
    below = _below_the_rim(layout, xyz, tri_idx, source)
    dark = (shade > 0) & (dist <= REACH_M) & below
    rock = _rock(stats, layout, xyz, tri_idx, ref_ids, ref_values, near,
                 values)
    seeds = region_nodes
    if rock.any():
        rock_nodes = numpy.unique(numpy.concatenate(
            [tri_idx[layout.region_tris[r]] for r in numpy.nonzero(rock)[0]]
        ).ravel())
        dark[rock_nodes] = False
        seeds = numpy.setdiff1d(region_nodes, rock_nodes)
    if not dark[seeds].any():
        return None, stats
    core = _dark_core(graph, dark, seeds)
    extra = numpy.zeros(len(xyz))
    extra[core] = shade[core] * (1.0 - _smoothstep(
        (dist[core] - (REACH_M - RAMP_M)) / RAMP_M))
    full = core[extra[core] >= 0.5]
    if len(full):
        d_out = dijkstra(graph, indices=full, min_only=True, limit=RAMP_M)
        ramp = numpy.where(numpy.isfinite(d_out) & below,
                           1.0 - _smoothstep(d_out / RAMP_M), 0.0)
        extra = numpy.maximum(extra, numpy.where(numpy.isfinite(dist),
                                                 ramp, 0.0))
    if not extra.any():
        return None, stats
    is_region = numpy.zeros(len(xyz), bool)
    is_region[region_nodes] = True
    new = numpy.nonzero((extra > 0) & ~is_region)[0]
    stats.extension_m = _region_reach(layout, tri_idx, new, dist, source)
    stats.nodes = len(new)
    return extra, stats
