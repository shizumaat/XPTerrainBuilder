"""The DSF's second triangle pass -- land and inland water -- on arrays.

``build_dsf`` walks the mesh twice: the sea first, then every other
triangle (land, and inland water drawn as an ortho overlay over X-Plane
water).  The second walk was one Python iteration per triangle and per
corner, the largest share of the step on a large tile (issue #850).  This
module answers the same thing for the ``full_ortho`` texture mode from
whole-mesh arrays, and the bytes it leaves are the walk's:

* a corner's DSF point is keyed by ``(geometric pool, quantised lon, lat,
  terrain)``; the first corner (in triangle order, corners ``n1, n3, n2``)
  with a key makes the point, and points take their pool slots in that
  order, interleaved with the X-Plane water points exactly as the walk
  interleaved them (:meth:`O4_DSF_Pools.DsfPointPools.slots`);
* a point's texture coordinates are ``O4_Geo_Utils.st_coord``'s, the
  Mercator ratio taken with the same ``math`` functions per node;
* a triangle whose corners share a point is skipped (and draws no water);
* each terrain's triangle lists fill in triangle order, the lists keyed in
  the order they first appear.

Terrains are made by the caller's ``terrain_for`` in the order their first
triangle appears, as the walk made them.
"""
from __future__ import annotations

from math import log, pi, tan

import numpy

__all__ = ["LAND", "MASKED", "CONSTANT", "emit_land_and_inland_water"]

#: what a terrain's corner points carry: land (5 planes + s, t), a
#: feathered inland shore (5 planes + s, t, s, t) and an inland overlay of
#: constant blend (3 planes, flat normal, s, t, 0, ratio_water)
(LAND, MASKED, CONSTANT) = (0, 1, 2)

#: a ``65535 * t`` this close to a half is rounded from ``math``'s ratio
#: (a last-bit error in the ratio moves it by about 1e-7 at zoom level 19)
_ROUND_GUARD = 1e-4


def emit_land_and_inland_water(mesh, squares, terrain_for, state):
    """Emit every triangle of ``mesh`` that is not sea; return
    ``(new points, cross-pool triangles)``.

    ``mesh``: ``(corners, tri_types, node_icoords, pool_of_node, lons,
    lats)`` -- the ``(nbr_tris, 3)`` corner rows, the triangle types, the
    ``(nbr_nodes, 5)`` uint16 quantised nodes, each node's geometric pool
    (int64), and the node longitudes and latitudes as lists of floats.
    ``squares``: each row's ``(til_x, til_y)`` texture square, two arrays.
    ``terrain_for(square, tri_type)``: ``(terrain_idx, texture_attributes,
    kind)``, making the terrain when it is new.
    ``state``: ``(point_pools, pool_nbr, textured_tris, water_points,
    water_ratio, ratio_water)`` -- ``water_points`` holds the sea pass's
    water point of node ``n`` under the key ``(n, 0)``; ``water_ratio(n)``
    is the depth ratio of a new water point."""
    (corners, tri_types, icoords, pool_of_node, lons, lats) = mesh
    (point_pools, pool_nbr, textured_tris, water_points, water_ratio,
     ratio_water) = state
    tri_types = numpy.asarray(tri_types)
    rows = numpy.flatnonzero(tri_types != 2)
    if not len(rows):
        return (0, 0)
    tri_type = tri_types[rows].astype(numpy.int64)
    (terrain, kind, texture) = _row_terrains(
        squares[0][rows], squares[1][rows], tri_type, terrain_for)
    visit = corners[rows][:, [0, 2, 1]]
    (point_of_visit, land_first) = _land_points(
        visit, terrain, icoords, pool_of_node)
    kept = ~((point_of_visit[:, 0] == point_of_visit[:, 1])
             | (point_of_visit[:, 1] == point_of_visit[:, 2])
             | (point_of_visit[:, 2] == point_of_visit[:, 0]))
    # Inland water draws X-Plane water under its overlay (corners n1, n3,
    # n2 again), after its own corners in the walk's order.
    water_rows = numpy.flatnonzero(kept & (tri_type == 1))
    (water_of_visit, water_first, water_slot, water_new) = _water_points(
        visit[water_rows], water_points)
    # One slot per new point, in the walk's order: a triangle's three
    # corners, then its three water corners.
    land_row = land_first // 3
    land_node = visit.ravel()[land_first]
    land_kind = kind[land_row]
    water_node = visit[water_rows].ravel()[water_first]
    sequence = numpy.concatenate((
        land_row * 6 + land_first % 3,
        water_rows[water_first // 3] * 6 + 3 + water_first % 3))
    bases = numpy.concatenate((
        pool_of_node[land_node] + numpy.where(land_kind == LAND, 0, pool_nbr),
        pool_of_node[water_node] + 2 * pool_nbr))
    order = _stable_order(sequence)
    pool = numpy.empty_like(bases)
    position = numpy.empty_like(bases)
    (pool[order], position[order]) = point_pools.slots(bases[order])
    words = _point_words(land_node, land_kind, texture[land_row],
                         water_node, water_ratio, icoords, lons, lats,
                         ratio_water)
    _fill_pools(point_pools, pool[order], words[order])
    nbr_land = len(land_node)
    land_slot = numpy.stack((pool[:nbr_land], position[:nbr_land]), axis=1)
    water_slot[water_new] = numpy.stack(
        (pool[nbr_land:], position[nbr_land:]), axis=1)
    cross = _fill_triangles(textured_tris, terrain[kept],
                            land_slot[point_of_visit[kept]])
    cross += _fill_triangles(
        textured_tris, numpy.zeros(len(water_rows), dtype=numpy.int64),
        water_slot[water_of_visit])
    return (len(bases), cross)


def _row_terrains(til_x, til_y, tri_type, terrain_for):
    """Each row's ``(terrain_idx, kind, (tex_x, tex_y, zoomlevel))``;
    ``terrain_for`` asked once per square and type, in first-row order."""
    x0 = int(til_x.min())
    y0 = int(til_y.min())
    span = int(til_y.max()) - y0 + 1
    key = ((til_x - x0) * span + (til_y - y0)) * 3 + tri_type
    (first, inverse) = _first_seen(key)
    answers = [None] * len(first)
    for u in numpy.argsort(first, kind="stable").tolist():
        row = int(first[u])
        answers[u] = terrain_for((int(til_x[row]), int(til_y[row])),
                                 int(tri_type[row]))
    terrain = numpy.array([a[0] for a in answers], dtype=numpy.int64)
    kind = numpy.array([a[2] for a in answers], dtype=numpy.int64)
    texture = numpy.array([a[1][:3] for a in answers], dtype=numpy.int64)
    return (terrain[inverse], kind[inverse], texture[inverse])


def _land_points(visit, terrain, icoords, pool_of_node):
    """Each visit's point (a label per key) and the visit that first holds
    each point.  Keys are found per node and terrain first (most visits
    repeat one), then the pool and quantised position merge nodes."""
    nodes = visit.ravel()
    terrains = numpy.repeat(terrain, 3)
    width = int(terrain.max()) + 1
    (pair_first, pair_of_visit) = _first_seen(nodes * width + terrains)
    pair_node = nodes[pair_first]
    pools = pool_of_node[pair_node]
    columns = (pools, icoords[pair_node, 0].astype(numpy.int64),
               icoords[pair_node, 1].astype(numpy.int64),
               terrains[pair_first])
    if (int(pools.max()) + 1) * width < (1 << 31):
        key = ((columns[0] * 65536 + columns[1]) * 65536
               + columns[2]) * width + columns[3]
        (_, point_of_pair) = _first_seen(key)
    else:
        (_, point_of_pair) = numpy.unique(
            numpy.stack(columns, axis=1), axis=0, return_inverse=True)
        point_of_pair = point_of_pair.ravel()
    first = numpy.full(int(point_of_pair.max()) + 1, len(nodes),
                       dtype=numpy.int64)
    numpy.minimum.at(first, point_of_pair, pair_first)
    return (point_of_pair[pair_of_visit].reshape(-1, 3), first)


def _water_points(visit, water_points):
    """Each water visit's node (an index into the nodes met), the visits
    first meeting the new nodes (in visit order), every node's point --
    the sea pass's, or ``-1`` where it is new -- and the new nodes."""
    visits = visit.ravel()
    (first, inverse) = _first_seen(visits)
    nodes = visits[first]
    slot = numpy.full((len(nodes), 2), -1, dtype=numpy.int64)
    for (u, n) in enumerate(nodes.tolist()):
        found = water_points.get((n, 0))
        if found is not None:
            slot[u] = found
    new = numpy.flatnonzero(slot[:, 0] < 0)
    new = new[numpy.argsort(first[new], kind="stable")]
    return (inverse.reshape(-1, 3), first[new], slot, new)


def _point_words(land_node, land_kind, texture, water_node, water_ratio,
                 icoords, lons, lats, ratio_water):
    """The 16-bit words of every new point (land points, then water
    points), nine columns wide; a 7-plane point uses the first seven."""
    words = numpy.zeros((len(land_node) + len(water_node), 9),
                        dtype=numpy.uint16)
    (s, t) = _st_words(land_node, texture, lons, lats)
    land = words[:len(land_node)]
    full = land_kind != CONSTANT
    land[full, :5] = icoords[land_node[full]]
    masked = land_kind == MASKED
    land[masked, 7] = s[masked]
    land[masked, 8] = t[masked]
    flat = ~full
    land[flat, :3] = icoords[land_node[flat], :3]
    land[flat, 3:5] = 32768
    land[flat, 8] = int(round(ratio_water * 65535))
    land[:, 5] = s
    land[:, 6] = t
    water = words[len(land_node):]
    water[:, :3] = icoords[water_node, :3]
    water[:, 3:5] = 32768
    water[:, 5] = 65535
    water[:, 6] = [int(65535 * water_ratio(n)) for n in water_node.tolist()]
    return words


def _st_words(nodes, texture, lons, lats):
    """``round(65535 * st)`` of ``O4_Geo_Utils.st_coord`` for each node in
    its texture.  ``t`` takes numpy's Mercator ratio; where it lands so near
    a rounding boundary that a last-bit difference from the C library's
    ``log``/``tan`` could move it, the ratio is taken by ``math`` (the
    ``O4_Geo_Arrays`` rule)."""
    lon = numpy.array(lons, dtype=numpy.float64)[nodes]
    lat = numpy.array(lats, dtype=numpy.float64)[nodes]
    mult = numpy.ldexp(1.0, (texture[:, 2] - 5).astype(numpy.int32))
    s = (lon / 180 + 1) * mult - (texture[:, 0] // 16)
    ratio_y = numpy.log(numpy.tan((90 + lat) * numpy.pi / 360)) / numpy.pi
    t = _t_coord(ratio_y, mult, texture)
    near = numpy.flatnonzero(
        numpy.abs(t * 65535 - numpy.floor(t * 65535) - 0.5) < _ROUND_GUARD)
    if len(near):
        ratio_y[near] = [log(tan((90 + lats[n]) * pi / 360)) / pi
                         for n in nodes[near].tolist()]
        t[near] = _t_coord(ratio_y[near], mult[near], texture[near])
    return (numpy.rint(numpy.clip(s, 0, 1) * 65535),
            numpy.rint(t * 65535))


def _t_coord(ratio_y, mult, texture):
    """``st_coord``'s clamped ``t`` from the Mercator ratio."""
    return numpy.clip(1 - ((1 - ratio_y) * mult - texture[:, 1] // 16), 0, 1)


def _fill_pools(point_pools, pool, words):
    """Append the new points' words to their pools (``pool`` and
    ``words`` in slot order)."""
    if not len(pool):
        return
    order = _stable_order(pool)
    cuts = numpy.flatnonzero(numpy.diff(pool[order])) + 1
    for group in numpy.split(order, cuts):
        k = int(pool[group[0]])
        point_pools.points[k].frombytes(numpy.ascontiguousarray(
            words[group, :point_pools.plane[k]]).tobytes())


def _fill_triangles(textured_tris, terrain, slots):
    """Append triangles (``slots``: rows of three ``(pool, position)``) to
    their terrain's lists in order: the positions under the pool when the
    three share one, else the six words under ``"cross-pool"``; a list
    first met is keyed after the terrain's others.  Returns the number of
    cross-pool triangles."""
    if not len(terrain):
        return 0
    pools = slots[:, :, 0]
    same = (pools[:, 0] == pools[:, 1]) & (pools[:, 1] == pools[:, 2])
    target = numpy.where(same, pools[:, 0], -1)
    key = terrain * (int(target.max()) + 2) + (target + 1)
    (first, inverse) = _first_seen(key)
    rows_by_key = _stable_order(inverse)
    bounds = numpy.searchsorted(inverse[rows_by_key],
                                numpy.arange(len(first) + 1))
    for u in numpy.argsort(first, kind="stable").tolist():
        rows = rows_by_key[bounds[u]:bounds[u + 1]]
        row = int(first[u])
        lists = textured_tris[int(terrain[row])]
        if same[row]:
            lists[int(target[row])].frombytes(
                slots[rows, :, 1].astype(numpy.uint16).tobytes())
        else:
            lists["cross-pool"].frombytes(
                slots[rows].astype(numpy.uint16).tobytes())
    return int(numpy.count_nonzero(~same))


def _stable_order(key):
    """``numpy.argsort(key, kind="stable")`` of an integer array: one sort
    of the key packed above the index when both fit 62 bits."""
    key = numpy.asarray(key, dtype=numpy.int64)
    if not len(key):
        return numpy.zeros(0, dtype=numpy.int64)
    bits = max(1, (len(key) - 1).bit_length())
    low = int(key.min())
    if (int(key.max()) - low).bit_length() + bits > 62:
        return numpy.argsort(key, kind="stable")
    packed = ((key - low) << bits) | numpy.arange(len(key), dtype=numpy.int64)
    packed.sort()
    return packed & ((1 << bits) - 1)


def _first_seen(key):
    """``(first, label)``: a label per distinct key (in key order) for each
    element, and the first element holding each label."""
    order = _stable_order(key)
    ordered = numpy.asarray(key)[order]
    new = numpy.ones(len(order), dtype=bool)
    new[1:] = ordered[1:] != ordered[:-1]
    label = numpy.empty(len(order), dtype=numpy.int64)
    label[order] = numpy.cumsum(new) - 1
    return (order[new], label)
