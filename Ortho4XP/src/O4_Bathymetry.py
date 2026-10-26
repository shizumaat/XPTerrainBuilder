import os
import array
import numpy
from PIL import Image
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO

def set_depth_ratio(n, node_is_coast, node_bathy, tile):
    if node_is_coast[n]:
        return 0
    else:
        return max(
            min(10 * tile.ratio_bathy * node_bathy[n] / 255, 1),
            0.1)

def recut_water_tris(node_coords, tri_idx, tri_types):

    assert(len(node_coords) % 5 == 0)
    nbr_nodes = len(node_coords) // 5;
    assert(len(tri_idx) % 3 == 0)
    assert(len(tri_idx) // 3 == len(tri_types))
    nbr_tris  = len(tri_types)

    # Fill node types using a boolean or on a bit field.
    # Coastline nodes are those that will have both a land and water bits set. 
    # Assumes that tri_types[n] is already in the range {0, 1, 2}
    node_types = numpy.zeros(nbr_nodes, dtype = numpy.uint8)
    for i in range(nbr_tris):
        t = 1 << tri_types[i]
        node_types[tri_idx[3 * i + 0]] |= t 
        node_types[tri_idx[3 * i + 1]] |= t 
        node_types[tri_idx[3 * i + 2]] |= t
    node_is_coast = ((node_types & 1) != 0) & ((node_types & 6) != 0)

    # Count the number of coastline tris (i.e. with at least one coastline vtx)
    # The latter are the only ones with a potential recut).
    tri_is_coast = numpy.zeros(nbr_tris, dtype = bool)
    for i in range(nbr_tris):
        tri_is_coast[i] |= node_is_coast[tri_idx[3 * i + 0]]
        tri_is_coast[i] |= node_is_coast[tri_idx[3 * i + 1]]
        tri_is_coast[i] |= node_is_coast[tri_idx[3 * i + 2]]
    coast_tri_count = numpy.sum(tri_is_coast)

    # Classify edges of coastline tris
    edge_type = {}
    for i in range(nbr_tris):
        if not tri_is_coast[i]:
            continue
        t = 1 << tri_types[i]
        (a,b,c) = tri_idx[3 * i: 3 * i + 3]
        for (m,n) in ((a,b), (b,c), (c,a)):
            if (m,n) in edge_type or (n,m) in edge_type:
                edge_type[(m,n)] |= t
                edge_type[(n,m)] |= t
            else:
                edge_type[(m,n)] = t
                edge_type[(n,m)] = t

    # Copy and increase size for node_coords, node_types, node_is_coast
    node_max_count = nbr_nodes + 3 * coast_tri_count
    node_coords = numpy.resize(node_coords, 5 * node_max_count)
    node_types   = numpy.resize(node_types, node_max_count)
    node_is_coast = numpy.resize(node_is_coast, node_max_count)

    # Cut edges that need to : i.e. have no land bit but their 
    # end-points are coastline.
    edge_cut = {}
    next_n = nbr_nodes
    for ((a, b), t) in edge_type.items():
        if b < a:
            # do not do twice the work we have both pairs anyway
            continue
        if (t & 1 == 0) and node_is_coast[a] and node_is_coast[b]:
            edge_cut[(a,b)] = next_n
            edge_cut[(b,a)] = next_n
            node_coords[5 * next_n: 5 * next_n + 5] = (
                    node_coords[5 * a: 5 * a + 5] +
                    node_coords[5 * b: 5 * b + 5]
                    ) / 2.0
            node_types[next_n] = t
            node_is_coast[next_n] = False
            next_n += 1

    # Copy and increase size for node_coords, node_types, node_is_coast
    tri_max_count = nbr_tris + 3 * coast_tri_count
    tri_idx = numpy.resize(tri_idx, 3 * tri_max_count)
    tri_types = numpy.resize(tri_types, tri_max_count)

    next_t = nbr_tris

    # Cut the tris that need to.
    # When cutting a tri, its place in tri_idx is taken by one of the 
    # newly created ones, and the other ones are appended at the end.
    for i in range(nbr_tris):
        if not tri_types[i] or not tri_is_coast[i]:
            continue
        (a,b,c) = tri_idx[3 * i: 3 * i + 3]
        C = (a,b) in edge_cut
        A = (b,c) in edge_cut
        B = (c,a) in edge_cut
        cuts = A + B + C
        if (not cuts):
            # We might still need to cut the tri if all its edges are coastline 
            # Note : this is a water tri so edges surely have water bit(s)
            if ((edge_type[(a,b)] & 1 == 0) or (edge_type[(b,c)] & 1 == 0) or 
               (edge_type[(c,a)] & 1 == 0)):
                   continue
            # Cut the tri at its barycenter
            node_coords[5 * next_n: 5 * next_n + 5] = (
                   node_coords[5 * a: 5 * a + 5] + 
                   node_coords[5 * b: 5 * b + 5] +
                   node_coords[5 * c: 5 * c + 5]
                   ) / 3.0
            node_types[next_n] = tri_types[i]
            node_is_coast[next_n] = False
            tri_idx[3 * i: 3 * i + 3] = (a,b,next_n)
            tri_idx[3 * next_t: 3 * next_t + 6] = (b,c,next_n,c,a,next_n)
            tri_types[next_t] = tri_types[next_t + 1] = tri_types[i]
            next_n += 1
            next_t += 2
        else:
            # Make a drawing ! a, b, c are the triangles vertices, A, B, C
            # are the potential cut vertices opposed respectively to a, b, c.
            L = array.array('i')
            L.append(a)
            if C:
                s1 = len(L)
                L.append(edge_cut[(a,b)])
            else:
                s2 = len(L) - 1
            L.append(b)
            if A:
                s1 = len(L)
                L.append(edge_cut[(b,c)])
            else:
                s2 = len(L) - 1
            L.append(c)
            if B:
                s1 = len(L)
                L.append(edge_cut[(c,a)])
            else:
                s2 = len(L) - 1
            L = L + L
            
            if (cuts == 2):
                # By def of s2 (x,y) is the one edge with no cut
                # Make a drawing !
                (x,y,z,t,u) = L[s2:s2+5]
                tri_idx[3 * i: 3 * i + 3] = (x,y,z)
                tri_idx[3 * next_t: 3 * next_t + 6] = (z,t,u,x,z,u)
                tri_types[next_t: next_t + 2] = tri_types[i]
                next_t += 2
            elif (cuts == 1):
                # By def of s1 x is the cut node
                # Make a drawing !
                (x,y,z,t) = L[s1:s1+4]
                tri_idx[3 * i: 3 * i + 3] = (x,y,z)
                tri_idx[3 * next_t: 3 * next_t + 3] = (x,z,t)
                tri_types[next_t] = tri_types[i]
                next_t += 1
            else: # cuts == 3
                # By def of s1 x is some cut node
                # Make a drawing !
                (x,y,z,t,u,v) = L[s1:s1+6]
                tri_idx[3 * i: 3 * i + 3] = (x,y,z)
                tri_idx[3 * next_t: 3 * next_t + 9] = (z,t,u,u,v,x,x,z,u)
                tri_types[next_t: next_t + 3] = tri_types[i]
                next_t += 3

    nbr_nodes = next_n
    assert(node_max_count >= nbr_nodes)
    node_coords = numpy.resize(node_coords, 5 * nbr_nodes)
    node_types  = numpy.resize(node_types, nbr_nodes)
    node_is_coast = numpy.resize(node_is_coast, nbr_nodes)
    
    nbr_tris = next_t
    assert(tri_max_count >= nbr_tris)
    tri_idx = numpy.resize(tri_idx, 3 * nbr_tris)
    tri_types = numpy.resize(tri_types, nbr_tris)

    return (nbr_nodes, node_coords, node_types, node_is_coast, 
            nbr_tris, tri_idx, tri_types)
    



def compute_depth_ratio_bounds_from_masks(
        nbr_nodes, node_coords, node_types, tile):

    water_nodes = [n for n in range(nbr_nodes) if (node_types[n] & 4 != 0)]

    node_bathy = 255 * numpy.ones(nbr_nodes, dtype = numpy.uint8)

    # Key is texture attribute at mask_zl
    # Value is an array of vertex integers
    mask_to_nodes = {}

    for n in water_nodes:
        lon = node_coords[5 * n + 0]
        lat = node_coords[5 * n + 1]
        mask_attr = GEO.wgs84_to_orthogrid(lat, lon, tile.mask_zl)
        if (mask_attr) in mask_to_nodes:
            mask_to_nodes[mask_attr].append(n)
        else:
            mask_to_nodes[mask_attr] = array.array('i',(n,))

    for mask_attr in mask_to_nodes:
        mask_file = os.path.join(FNAMES.mask_dir(tile.lat, tile.lon),
                FNAMES.distance_mask(*mask_attr))
        if not os.path.isfile(mask_file):
            continue
        img = Image.open(mask_file)
        mask_val = numpy.array(img, dtype=numpy.uint8)
        mask_nodes = mask_to_nodes[mask_attr]
        for n in mask_nodes:
            lon = node_coords[5 * n + 0]
            lat = node_coords[5 * n + 1]
            (s, t) = GEO.st_coord(lat, lon, *mask_attr, tile.mask_zl, None)
            pixx = int(s * 4095)
            pixy = int((1-t) * 4095)
            node_bathy[n] = mask_val[pixy, pixx]

    return node_bathy
            










# The ZL16 pixel at the equator, in metres: the unit of ``node_bathy``.
# ``distance_masks_too`` writes the distance to the coastline in mask
# pixels times 2**(16 - mask_zl), i.e. in ZL16 pixels, capped at 255.
ZL16_PIXEL_EQUATOR_M = 2 * numpy.pi * 6378137.0 / (256 * 2 ** 16)


def shore_segments(node_coords, tri_idx, tri_types):
    """The inland shoreline: every edge one LAND triangle and one INLAND
    water triangle share, as ``(k, 2, 2)`` lon/lat endpoint pairs.

    ``tri_types`` must already be remapped to the DSF classes 0 = land,
    1 = inland, 2 = sea (:func:`O4_DSF_Utils.remap_water_tri_type`).
    """
    tris = numpy.asarray(tri_idx, dtype=numpy.int64).reshape(-1, 3)
    types = numpy.asarray(tri_types)
    # Only triangles with a vertex on inland water can hold a shore edge.
    wet = numpy.zeros(int(tris.max()) + 1 if tris.size else 0, dtype=bool)
    wet[tris[types == 1].ravel()] = True
    near = wet[tris].any(axis=1)
    (tris, types) = (tris[near], types[near])

    def edge_keys(cls):
        t = tris[types == cls]
        pairs = numpy.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]))
        pairs.sort(axis=1)
        return pairs[:, 0] * (1 << 32) + pairs[:, 1]

    keys = numpy.intersect1d(edge_keys(0), edge_keys(1))
    a, b = keys >> 32, keys & ((1 << 32) - 1)
    xy = numpy.asarray(node_coords, dtype=float).reshape(-1, 5)[:, :2]
    return numpy.stack((xy[a], xy[b]), axis=1)


def inland_depth_from_shore(node_bathy, node_coords, tri_idx, tri_types,
                            tile_lat):
    """Give every inland water vertex its distance to the shoreline as its
    ``node_bathy`` (#1336), so that :func:`set_depth_ratio` ramps the
    drawn depth of a lake or pond up from its shore instead of stepping it.

    X-Plane 12 draws the bed of ``terrain_Water`` at the per-vertex depth
    ratio times the depth below the mesh's water surface down to the
    DSF ``sea_level`` raster.  The ratio is 0 on the shore and, with no
    distance mask, 1 at the first vertex off it — which
    :func:`recut_water_tris` places half an edge from the shore — so a
    60 m pond whose raster bed sits 7 m below its surface was drawn as a
    7 m pit with walls one triangle wide.  The sea gets its ramp from the
    ``distance_masks_too`` masks ("avoid steep walls close to piers or
    rocks"); inland water never reads them.  This is the same ramp for
    inland water, measured from the mesh's own shoreline in the same unit
    (ZL16 pixels, capped at 255), so ``set_depth_ratio`` is unchanged and
    full depth is reached ``25.5 / ratio_bathy`` ZL16 pixels from the
    shore, as at sea.  Only vertices of inland water alone are touched:
    shore vertices stay at ratio 0 and anything touching the sea keeps
    the sea's rule.  The classes are read from the triangles, never from
    ``recut_water_tris``' ``node_types``, which files a barycentre it adds
    under its triangle's class instead of that class's bit.  Returns the
    number of vertices given a distance.
    """
    import shapely

    tris = numpy.asarray(tri_idx, dtype=numpy.int64).reshape(-1, 3)
    types = numpy.asarray(tri_types)
    touches = numpy.zeros((3, len(node_bathy)), dtype=bool)
    for cls in (0, 1, 2):
        touches[cls, tris[types == cls].ravel()] = True
    inland_only = numpy.flatnonzero(touches[1] & ~touches[0] & ~touches[2])
    if not inland_only.size:
        return 0
    segments = shore_segments(node_coords, tri_idx, tri_types)
    if not len(segments):
        return 0
    pixel_m = ZL16_PIXEL_EQUATOR_M * numpy.cos(numpy.radians(tile_lat))
    # Local metres, east scaled by the cosine at the tile's latitude: a
    # 1 degree tile moves the scale by under 2 %, far below the ramp's
    # 1.8 m step.
    scale = numpy.array((111319.49 * numpy.cos(numpy.radians(tile_lat)),
                         111319.49))
    lines = shapely.linestrings(segments * scale)
    xy = numpy.asarray(node_coords, dtype=float).reshape(-1, 5)[
        inland_only, :2] * scale
    points = shapely.points(xy)
    cap_m = 255 * pixel_m
    tree = shapely.STRtree(lines)
    (pairs, distances) = tree.query_nearest(
        points, max_distance=cap_m, return_distance=True, all_matches=False)
    pixels = numpy.full(inland_only.size, 255.0)
    pixels[pairs[0]] = numpy.minimum(distances / pixel_m, 255.0)
    node_bathy[inland_only] = numpy.round(pixels).astype(numpy.uint8)
    return int(inland_only.size)
