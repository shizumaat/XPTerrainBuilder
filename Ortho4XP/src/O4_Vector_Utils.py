import ctypes
from math import ceil, sqrt, atan2
import numpy
from shapely import geometry, affinity
from shapely import ops
from rtree import core as rtree_core
from rtree import index
import O4_UI_Utils as UI
import O4_Geo_Utils as GEO

_RTREE_DOUBLE2 = ctypes.c_double * 2


class Edge_Index(index.Index):
    """``rtree.index.Index`` plus an id-only query with the wrapper's
    per-call Python taken out.

    THE SAME C QUERY WITH THE SAME VALUES, hence the same ids IN THE SAME
    ORDER — and the order is the whole reason this class is careful: it
    decides which encroachment :meth:`Vector_Map.insert_edge` resolves
    first, hence which node ids get minted, hence the bytes of
    ``Data+XX+YYY.node``.

    ``insert_edge`` used to ask for ``objects=True`` and read only
    ``hit.id`` off each :class:`rtree.index.Item`.  Building those Items
    — one Python object per hit, each carrying the stored bounds — is
    most of the query's cost, and the bounds it carried are
    ``bbox_from_node_ids(id2, id3)`` recomputed exactly, since a node's
    coordinates never change once minted.  Measured here (interleaved
    arms, 60 k boxes / 20 k queries, five rounds, medians): **17.93 us
    per query with ``objects=True``, 7.14 us through this method.**

    ``insert`` and ``delete`` are deliberately NOT specialised.  The same
    measurement priced stock ``insert`` at 16.42 us against 16.48 us for
    a direct ``Index_InsertData`` call: libspatialindex's own tree work
    is the cost there, the Python wrapper is noise, and an override would
    have been risk for nothing.

    Only the 2-D interleaved non-TPR case is specialised; anything else
    falls through to the stock method.  Twin:
    ``tests/test_vector_edge_index.py`` holds the ids AND THEIR ORDER
    equal to both stock spellings, including after a delete/re-insert
    history.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asked ONCE, here: ``properties.dimension`` and
        # ``properties.type`` are ctypes round-trips into the library,
        # which stock re-pays on every call.
        self.fast_path = bool(
            self.properties.dimension == 2
            and self.properties.type != index.RT_TPRTree
            and self.interleaved
        )

    def intersection_ids(self, coordinates):
        """The ids meeting ``coordinates`` — the same ids, in the same
        order, as ``self.intersection(coordinates)``.

        A separate name rather than an ``intersection`` override: the
        stock signature also serves ``objects=True``/``"raw"`` callers,
        and a method that quietly ignored that argument would be the
        silently-different-copy defect.
        """
        if not self.fast_path:
            return self.intersection(coordinates)
        n_results = ctypes.c_uint64(0)
        it = ctypes.pointer(ctypes.c_int64())
        rtree_core.rt.Index_Intersects_id(
            self.handle,
            _RTREE_DOUBLE2(coordinates[0], coordinates[1]),
            _RTREE_DOUBLE2(coordinates[2], coordinates[3]),
            2, ctypes.byref(it), ctypes.byref(n_results))
        return self._get_ids(it, n_results.value)


# Some functions further down rely not only on a vector structure but also on a
# metric (distances of course but more importantly angles and normals).
# Since our base coordinates x,y will eventually be lon/lat (shifted into
# the interval [0,1] for maximal floating point precision), we need to introduce
# a metric for that purpose. We assume the base coordinates are orthogonal and
# simple potentially have different scales.
scalx = 1
scaly = 1
# These parameters are meant to be updated at runtime by the program, typically
# with scaly=1 and scalx=cos(lat*pi/180).


# The first class we introduce is a vector map: this is simply a set of nodes
# and edges with an insert_edge function that will compute and resolve all edge
# intersections in order to maintain the property that any two edges of the
# vector map either don't intersect or have exactly one point of intersection
# being a common end-point of both.
# Edges in a vector map have attributes, the goal of which being to determine
# bounding regions with these attributes. Indeed the topology problem we will
# eventually have to face is to pass a vector based geographical information
# (mostly OSM way tags) into a region based information (mesh triangles).
# This is achieved by droping seeds with given attributes on appropriate
# locations and letting them plague the mesh triangles untill they are blocked
# by edges of that same attribute (side note :attributes are actally powers of
# two and the blocking uses bitwise arthmetic, this allows to have regions with
# multiple attributes with no risk of leaking during the plague algorithm in
# Triangle4XP).

# Large collections of edges for insertion can be sent in the form of
# MultiLineStrings or MultiPolygons as defined in the SHAPELY Python module by
# Sean Gillies.

################################################################################
class Vector_Map:

    dico_attributes = {
        "DUMMY": 0,
        "WATER": 1,
        "SEA": 2,
        "SEA_EQUIV": 4,
        "INTERP_ALT": 8,
        "RUNWAY": 16,
        "TAXIWAY": 32,
        "APRON": 64,
        "HANGAR": 128,
    }

    def __init__(self):
        self.dico_nodes = {}
        # keys are tuples of 2 floats (in our case (lon-base_lon), lat-base_lat)
        # and values are ints (ids)
        self.dico_edges = {}
        # keys are tuples of 2 ints (end-points ids) and values are ints (ids).
        # An egde id is needed for the index (bbox)
        self.nodes_dico = {}
        # inverse of dico_nodes : ids to 2-uples (coordinates)
        self.edges_dico = {}
        # inverse of dico_edges : ids to 2-uples (end-points ids)
        self.ebbox = Edge_Index()
        self.data_nodes = {}
        # keys are ints (ids) and values are floats (vector altitude)
        # could easily be upgraded to arrays if necessary
        self.data_edges = {}
        # keys are ints (ids) and values are ints (attribute)
        self.next_node_id = 1
        self.next_edge_id = 1
        self.holes = []
        self.seeds = {}

    def insert_node(self, x, y, z):
        # One tuple and one hash lookup instead of two of each: node ids
        # start at 1, so ``None`` cannot be a stored id.
        key = (x, y)
        node_id = self.dico_nodes.get(key)
        if node_id is None:
            node_id = self.next_node_id
            self.dico_nodes[key] = node_id
            self.nodes_dico[node_id] = key
            self.data_nodes[node_id] = z
            self.next_node_id += 1
        return node_id

    def update_edge(self, nodeid0, nodeid1, marker):
        if nodeid0 == nodeid1:
            return 1
        # Same two orientations, same order, one lookup each (edge ids
        # start at 1, so ``None`` cannot be a stored id).
        dico_edges = self.dico_edges
        edge_id = dico_edges.get((nodeid0, nodeid1))
        if edge_id is None:
            edge_id = dico_edges.get((nodeid1, nodeid0))
            if edge_id is None:
                return 0
        self.data_edges[edge_id] = (
            self.data_edges[edge_id] | marker
        )  # bitwise add new marker if necessary
        return 1

    def create_edge(self, nodeid0, nodeid1, marker):
        if self.update_edge(nodeid0, nodeid1, marker):
            return
        edge_id = self.next_edge_id
        self.next_edge_id += 1
        self.dico_edges[(nodeid0, nodeid1)] = edge_id
        self.edges_dico[edge_id] = (nodeid0, nodeid1)
        self.data_edges[edge_id] = marker
        self.ebbox.insert(edge_id, self.bbox_from_node_ids(nodeid0, nodeid1))
        return

    def insert_edge(self, id0, id1, marker, check=True):
        if not check:
            self.create_edge(id0, id1, marker)
        if self.update_edge(id0, id1, marker):
            return
        weight_list = []

        # affine coordinates of points in between pts id0 and id1 that belong
        # to existing edges
        id_list = []  # ids of these points
        nodes_dico = self.nodes_dico
        edges_dico = self.edges_dico
        data_edges = self.data_edges
        # a, b and everything derived from them are INVARIANT across the
        # hits — they used to be rebuilt, and their norm recomputed, once
        # per candidate edge.  Built lazily so an edge with no hit at all
        # (the common case) pays for none of it.
        a = b = ab = norm_ab = None
        # ``intersection_ids`` over ``intersection(..., objects=True)``:
        # the loop needs only the id, and the bbox it used to read off the
        # Item is ``bbox_from_node_ids(id2, id3)`` recomputed exactly —
        # node coordinates never change once minted — which is wanted only
        # on the rare branches that actually split an edge.
        for edge_id in self.ebbox.intersection_ids(
            self.bbox_from_node_ids(id0, id1)
        ):  # which other edges to search for instersection
            (id2, id3) = edges_dico[edge_id]
            c_marker = data_edges[edge_id]
            if a is None:
                a = numpy.array(nodes_dico[id0], dtype=float)
                b = numpy.array(nodes_dico[id1], dtype=float)
                ab = b - a
                norm_ab = numpy.linalg.norm(ab)
            # check for encroachment, slightly different than intersection, see
            # the details below in the function definition
            coeffs = self.are_encroached(
                a,
                b,
                numpy.array(nodes_dico[id2], dtype=float),
                numpy.array(nodes_dico[id3], dtype=float),
                ab=ab,
                norm_ab=norm_ab,
            )
            # coeffs=[]
            if not coeffs:
                continue
            if len(coeffs) == 2:  # transverse encroachment
                (alpha, beta) = coeffs
                if beta not in (0, 1):
                    c_x = (1 - alpha) * self.nodes_dico[id0][
                        0
                    ] + alpha * self.nodes_dico[id1][0]
                    c_y = (1 - alpha) * self.nodes_dico[id0][
                        1
                    ] + alpha * self.nodes_dico[id1][1]
                    # ! important to rely on the old id2 id3 for the z value !
                    c_z = (1 - beta) * self.data_nodes[
                        id2
                    ] + beta * self.data_nodes[id3]
                    c_id = self.insert_node(c_x, c_y, c_z)
                    # destroy old edge
                    del self.dico_edges[(id2, id3)]
                    del self.edges_dico[edge_id]
                    del self.data_edges[edge_id]
                    self.ebbox.delete(
                        edge_id, self.bbox_from_node_ids(id2, id3))
                    # and create two new ones
                    self.create_edge(id2, c_id, c_marker)
                    self.create_edge(c_id, id3, c_marker)
                elif beta == 0:  # the intersection is an existing node (id2)
                    c_id = id2
                else:  # the intersection is an existing node (id3)
                    c_id = id3
                weight_list.append(alpha)
                id_list.append(c_id)
            else:  # parallel encroachment
                (alpha0, alpha1, beta0, beta1) = coeffs
                ordered_data = sorted(
                    zip((beta0, beta1, 0, 1), (id0, id1, id2, id3))
                )
                for i in range(1, 3):
                    if ordered_data[i][0] > 0 and ordered_data[i][0] < 1:
                        # destroy old edge
                        del self.dico_edges[(id2, id3)]
                        del self.edges_dico[edge_id]
                        del self.data_edges[edge_id]
                        self.ebbox.delete(
                        edge_id, self.bbox_from_node_ids(id2, id3))
                        # create new ones as needed
                        self.create_edge(
                            ordered_data[i - 1][1], ordered_data[i][1], c_marker
                        )
                        self.create_edge(
                            ordered_data[i][1], ordered_data[i + 1][1], c_marker
                        )
                        if ordered_data[i + 1][0] < 1:
                            self.create_edge(
                                ordered_data[i + 1][1],
                                ordered_data[i + 2][1],
                                c_marker,
                            )
                        break
                if alpha0 > 0 and alpha0 < 1:
                    weight_list.append(alpha0)
                    id_list.append(id2)
                if alpha1 > 0 and alpha1 < 1:
                    weight_list.append(alpha1)
                    id_list.append(id3)
        if (
            not weight_list
        ):  # nothing inside and we have already checked for update -> create
            self.create_edge(id0, id1, marker)
            return
        if 0 not in weight_list:
            weight_list.append(0)
            id_list.append(id0)
        if 1 not in weight_list:
            weight_list.append(1)
            id_list.append(id1)
        id_list = list(zip(*(sorted(zip(weight_list, id_list)))))[1]
        for i in range(0, len(id_list) - 1):
            if (id_list[i], id_list[i + 1]) in self.dico_edges:
                edge_id = self.dico_edges[(id_list[i], id_list[i + 1])]
                self.data_edges[edge_id] = self.data_edges[edge_id] | marker
            elif (id_list[i + 1], id_list[i]) in self.dico_edges:
                edge_id = self.dico_edges[(id_list[i + 1], id_list[i])]
                self.data_edges[edge_id] = self.data_edges[edge_id] | marker
            else:
                self.create_edge(id_list[i], id_list[i + 1], marker)

    def insert_way(self, way, marker, check=True):
        if isinstance(marker, str):
            marker = self.dico_attributes[marker]
        node0_id = self.insert_node(*way[0])
        for node_array in way[1:]:
            node1_id = self.insert_node(*node_array)
            self.insert_edge(node0_id, node1_id, marker, check)
            node0_id = node1_id

    def bbox_from_node_ids(self, id0, id1):
        # takes the ids of two nodes
        # returns a 4-uple of the form (xmin,ymin,xmax,ymax) taken from the
        # nodes coords
        # Two dict lookups, not eight, and no tuple built to be thrown
        # away: the same values, ordered by the same comparisons (a tuple
        # is always truthy, so the old ``and``/``or`` chain WAS an
        # if/else).  Called two to three times per constrained edge.
        (x0, y0) = self.nodes_dico[id0]
        (x1, y1) = self.nodes_dico[id1]
        if x0 <= x1:
            (xmin, xmax) = (x0, x1)
        else:
            (xmin, xmax) = (x1, x0)
        if y0 <= y1:
            (ymin, ymax) = (y0, y1)
        else:
            (ymin, ymax) = (y1, y0)
        return (xmin, ymin, xmax, ymax)

    def are_encroached(self, a, b, c, d, ab=None, norm_ab=None):
        # A crucial one !
        # returns False if the only mutual points of the closed segments a->b
        #    and c->d are in {a,b,c,d}
        # returns [alpha,beta] where (1-alpha)*a * alpha*b =
        #    (1-beta)*c+beta*d otherwise and if the segments otherwise cut each
        #    other transversally (possibly only in one point)
        # returns [alpha0,alpha1,beta0,beta1] where
        #    alpha0*(a-b)=(a-c), alpha1*(a-b)=(a-d),
        #    beta0*(c-d)=(c-a), beta1*(c-d)=(c-b)
        #    otherwise and if the segments are colinear.
        # In the last case we hence have :
        #    c=(1-alpha0)*a+alpha0*b, d=(1-alpha1)*a+alpha1*b,
        #    a=(1-beta0)*c+beta0*d, b=(1-beta1)*c+beta1*d
        # First a speed check when a==d (should happen for any new edge within
        # insert_way) or when (b==c) (should happen once at closing within
        # insert_way)
        #
        # ``ab`` / ``norm_ab`` may be supplied by the caller: within one
        # ``insert_edge`` they are the SAME two values for every candidate
        # edge, and recomputing them per candidate is the whole of their
        # cost.  Bit-for-bit the same values either way (``b - a``,
        # ``numpy.linalg.norm(ab)``) — nothing here is re-associated.
        if ab is None:
            ab = b - a
        dc = c - d
        if norm_ab is None:
            norm_ab = numpy.linalg.norm(ab)
        pnorm = norm_ab * numpy.linalg.norm(dc)
        ac = c - a
        ab_dot_dc = numpy.dot(ab, dc)
        # ``(a == d).all()`` builds a bool array and reduces it; the
        # component spelling is the same predicate on the same floats
        # (including under NaN, where both are False) without the two
        # temporaries — and these four tests run on every candidate edge.
        if ((a[0] == d[0] and a[1] == d[1])
                or (b[0] == c[0] and b[1] == c[1])) \
                and ab_dot_dc < 0.9999 * pnorm:
            return False
        if ((a[0] == c[0] and a[1] == c[1])
                or (b[0] == d[0] and b[1] == d[1])) \
                and ab_dot_dc > -0.9999 * pnorm:
            return False
        eps = 1e-8
        oneminuseps = 1.0 - eps
        # ``numpy.column_stack`` for a 2x2 is several microseconds of pure
        # Python (atleast_2d + concatenate).  A C-contiguous (2, 2) filled
        # column-wise holds the identical bytes, so LAPACK below sees the
        # identical matrix.
        A = numpy.empty((2, 2))
        A[:, 0] = ab
        A[:, 1] = dc
        if abs(numpy.linalg.det(A)) > eps * pnorm:
            # ad and bc are not considered parallel
            [alpha, beta] = numpy.linalg.solve(A, ac)
            return (
                (alpha >= 0 and alpha <= 1)
                and (beta >= 0 and beta <= 1)
                and (
                    (alpha > eps and alpha < oneminuseps)
                    or (beta > eps and beta < oneminuseps)
                )
                and (alpha, beta)
            )
        elif abs(ab[0] * ac[1] - ab[1] * ac[0]) > eps * numpy.linalg.norm(ab) * numpy.linalg.norm(ac):
            # ad and bc are parallel but not colinear
            return False
        else:
            # ad and bc are parallel and colinear
            g_idx = numpy.argmax(abs(ab))
            d_idx = numpy.argmax(abs(dc))
            alpha0, alpha1 = ac[g_idx] / ab[g_idx], (d - a)[g_idx] / ab[g_idx]
            beta0, beta1 = ac[d_idx] / dc[d_idx], (c - b)[d_idx] / dc[d_idx]
            return (
                (alpha0 > eps or alpha1 > eps)
                and (alpha0 < oneminuseps or alpha1 < oneminuseps)
                and (alpha0, alpha1, beta0, beta1)
            )
    
    def are_encroached_old(self, a, b, c, d):
        # A crucial one !
        # returns False if the only mutual points of the closed segments a->b
        #    and c->d are in {a,b,c,d}
        # returns [alpha,beta] where (1-alpha)*a * alpha*b =
        #    (1-beta)*c+beta*d otherwise and if the segments otherwise cut each
        #    other transversally (possibly only in one point)
        # returns [alpha0,alpha1,beta0,beta1] where
        #    alpha0*(a-b)=(a-c), alpha1*(a-b)=(a-d),
        #    beta0*(c-d)=(c-a), beta1*(c-d)=(c-b)
        #    otherwise and if the segments are colinear.
        # In the last case we hence have :
        #    c=(1-alpha0)*a+alpha0*b, d=(1-alpha1)*a+alpha1*b,
        #    a=(1-beta0)*c+beta0*d, b=(1-beta1)*c+beta1*d
        # First a speed check when a==d (should happen for any new edge within
        # insert_way) or when (b==c) (should happen once at closing within
        # insert_way)
        if ((a == d).all() or (b == c).all()) and numpy.dot(b - a, c - d) / (
            numpy.linalg.norm(b - a) * numpy.linalg.norm(c - d)
        ) < 0.999:
            return False
        if ((a == c).all() or (b == d).all()) and numpy.dot(b - a, d - c) / (
            numpy.linalg.norm(b - a) * numpy.linalg.norm(c - d)
        ) < 0.999:
            return False
        eps = 1e-14
        A = numpy.column_stack((b - a, c - d))
        F = c - a
        if abs(numpy.linalg.det(A)) > eps:
            [alpha, beta] = numpy.linalg.solve(A, F)
            enc_lim = 1e-7
            return (
                (alpha >= 0 and alpha <= 1)
                and (beta >= 0 and beta <= 1)
                and (
                    (alpha > enc_lim and alpha < 1 - enc_lim)
                    or (beta > enc_lim and beta < 1 - enc_lim)
                )
                and [alpha, beta]
            )
        elif abs(numpy.linalg.det(numpy.column_stack((b - a, c - a)))) > eps:
            return False
        else:
            g_idx = numpy.argmax(abs(a - b))
            d_idx = numpy.argmax(abs(c - d))
            alpha0, alpha1 = (a - c)[g_idx] / (a - b)[g_idx], (a - d)[g_idx] / (
                a - b
            )[g_idx]
            beta0, beta1 = (c - a)[d_idx] / (c - d)[d_idx], (c - b)[d_idx] / (
                c - d
            )[d_idx]
            return (
                (alpha0 > 0 or alpha1 > 0)
                and (alpha0 < 1 or alpha1 < 1)
                and [alpha0, alpha1, beta0, beta1]
            )

    def encode_MultiPolygon(
        self,
        multipol,
        pol_to_alt,
        marker,
        area_limit=1e-10,
        check=True,
        simplify=False,
        refine=False,
        cut=True,
    ):
        UI.progress_bar(1, 0)
        if isinstance(multipol, dict):
            iterloop = multipol.values()
            todo = len(multipol)
        else:
            iterloop = list(ensure_MultiPolygon(multipol).geoms)
            todo = len(iterloop)
        step = int(todo / 100) + 1
        done = 0
        for pol in iterloop:
            if cut:
                pol = cut_to_tile(pol)
            if simplify:
                pol = pol.simplify(simplify)
            for polygon in ensure_MultiPolygon(pol).geoms:
                if polygon.area <= area_limit:
                    continue
                try:
                    polygon = geometry.polygon.orient(
                        polygon
                    )  # important for certain pol_to_alt instances
                except:
                    continue
                way = numpy.array(polygon.exterior.coords)
                if refine:
                    way = refine_way(way, refine)
                alti_way = pol_to_alt(way).reshape((len(way), 1))
                self.insert_way(numpy.hstack([way, alti_way]), marker, check)
                for linestring in polygon.interiors:
                    if linestring.is_empty:
                        continue
                    way = numpy.array(linestring.coords)
                    if refine:
                        way = refine_way(way, refine)
                    alti_way = pol_to_alt(way).reshape((len(way), 1))
                    self.insert_way(
                        numpy.hstack([way, alti_way]), marker, check
                    )
                try:
                    if marker in self.seeds:
                        self.seeds[marker].append(
                            numpy.array(polygon.representative_point().coords[0])
                        )
                    else:
                        self.seeds[marker] = [
                            numpy.array(polygon.representative_point().coords[0])
                        ]
                except Exception as e:
                    UI.lvprint(
                        2,
                        "Topologal inconsistency trying to tag a polygon ",
                        "with node ",
                        list(polygon.exterior.coords)[0],
                    )
            done += 1
            if done % step == 0:
                UI.progress_bar(1, int(100 * done / todo))
                if UI.red_flag:
                    return 0
        return 1

    def encode_MultiLineString(
        self,
        multilinestring,
        line_to_alt,
        marker,
        check=True,
        refine=False,
        skip_cut=False,
    ):
        UI.progress_bar(1, 0)
        multilinestring = ensure_MultiLineString(multilinestring)
        todo = len(multilinestring.geoms)
        step = int(todo / 100) + 1
        done = 0
        for line in multilinestring.geoms:
            if not skip_cut:
                line = cut_to_tile(line)
            for linestring in ensure_MultiLineString(line).geoms:
                if linestring.is_empty:
                    continue
                way = numpy.array(linestring.coords)
                if refine:
                    way = refine_way(way, refine)
                alti_way = line_to_alt(way).reshape((len(way), 1))
                self.insert_way(numpy.hstack([way, alti_way]), marker, check)
            done += 1
            if done % step == 0:
                UI.progress_bar(1, int(100 * done / todo))
                if UI.red_flag:
                    return 0
        return 1

    def snap_to_grid(self, digits):
        next_node_id = 1
        next_edge_id = 1
        dico_nodes_new = {}
        dico_edges_new = {}
        nodes_dico_new = {}
        edges_dico_new = {}
        data_nodes_new = {}
        data_edges_new = {}
        dico_old_to_new = {}
        data_nodes = self.data_nodes
        data_edges = self.data_edges
        # ``.items()`` in both loops: the old id and the old edge id were
        # each re-looked-up two or three times per entry, on dicts with a
        # million-plus entries.  Same iteration order (insertion order),
        # same values.
        for key, old_id in self.dico_nodes.items():
            key_new = (round(key[0], digits), round(key[1], digits))
            if key_new in dico_nodes_new:
                idx_new = dico_nodes_new[key_new]
            else:
                idx_new = next_node_id
                dico_nodes_new[key_new] = idx_new
                next_node_id += 1
                nodes_dico_new[idx_new] = key_new
                data_nodes_new[idx_new] = data_nodes[old_id]
            dico_old_to_new[old_id] = idx_new
        for (id0, id1), old_edge_id in self.dico_edges.items():
            (id0n, id1n) = (dico_old_to_new[id0], dico_old_to_new[id1])
            if id0n == id1n:
                continue
            marker = data_edges[old_edge_id]
            if (id0n, id1n) in dico_edges_new:
                eid = dico_edges_new[(id0n, id1n)]
                data_edges_new[eid] = (
                    data_edges_new[eid] | marker
                )  # bitwise add new marker if necessary
            elif (id1n, id0n) in dico_edges_new:
                eid = dico_edges_new[(id1n, id0n)]
                data_edges_new[eid] = (
                    data_edges_new[eid] | marker
                )  # bitwise add new marker if necessary
            else:
                dico_edges_new[(id0n, id1n)] = next_edge_id
                edges_dico_new[next_edge_id] = (id0n, id1n)
                data_edges_new[next_edge_id] = marker
                next_edge_id += 1
        UI.vprint(
            2,
            "Simplified ",
            len(self.dico_nodes) - len(dico_nodes_new),
            "duplicate nodes and",
            len(self.dico_edges) - len(dico_edges_new),
            "zero length edges.",
        )
        (
            self.dico_nodes,
            self.nodes_dico,
            self.dico_edges,
            self.edges_dico,
            self.data_nodes,
            self.data_edges,
        ) = (
            dico_nodes_new,
            nodes_dico_new,
            dico_edges_new,
            edges_dico_new,
            data_nodes_new,
            data_edges_new,
        )

    def write_node_file(self, node_file_name):
        # note that Triangle4XP too is writing a(nother) node file, which as
        # more node attributes
        total_nodes = len(self.dico_nodes)
        f = open(node_file_name, "w")
        f.write(str(total_nodes) + " 2 1 0\n")
        # Same text, same ``.9f`` conversion (``format(v, '.9f')`` IS what
        # ``"{:.9f}".format(v)`` calls), assembled in blocks: this loop
        # runs once per node — a million times on a KCLT-class tile — and
        # was paying for a list, a join and a stream write per line.
        nodes_dico = self.nodes_dico
        data_nodes = self.data_nodes
        block = []
        append = block.append
        for idx in sorted(nodes_dico.keys()):
            (x, y) = nodes_dico[idx]
            append(f"{idx} {x:.9f} {y:.9f} {data_nodes[idx]:.9f}\n")
            if len(block) >= 8192:
                f.write("".join(block))
                block = []
                append = block.append
        if block:
            f.write("".join(block))
        f.close()

    def write_poly_file(self, poly_file_name):
        f = open(poly_file_name, "w")
        f.write("0 2 1 0\n")
        f.write("\n")
        total_edges = len(self.edges_dico)
        f.write(str(total_edges) + " 1\n")
        idx = 1
        # Blocked for the same reason as write_node_file, and reading the
        # endpoints once instead of twice.  Identical text: every field is
        # an int spelled by str().
        data_edges = self.data_edges
        block = []
        append = block.append
        for edge_id, (end0, end1) in self.edges_dico.items():
            append(f"{idx} {end0} {end1} {data_edges[edge_id]}\n")
            idx += 1
            if len(block) >= 8192:
                f.write("".join(block))
                block = []
                append = block.append
        if block:
            f.write("".join(block))
        f.write("\n" + str(len(self.holes)) + "\n")
        idx = 1
        for hole in self.holes:
            f.write(
                str(idx)
                + " "
                + " ".join(["{:.15f}".format(h) for h in hole])
                + "\n"
            )
            idx += 1
        total_seeds = numpy.sum([len(self.seeds[key]) for key in self.seeds])
        if total_seeds == 0:
            f.write("\n0\n")
        else:
            f.write("\n" + str(total_seeds) + "\n")
            idx = 1
            for long_key in sorted(
                self.dico_attributes.items(), key=lambda item: item[1]
            ):
                (key, marker) = long_key
                if key not in self.seeds:
                    continue
                for seed in self.seeds[key]:
                    f.write(
                        str(idx)
                        + " "
                        + " ".join(["{:.15f}".format(s) for s in seed])
                        + " "
                        + str(marker)
                        + "\n"
                    )
                    idx += 1
        f.close()
        return


################################################################################
def MultiPolygon_to_Indexed_Polygons(multipol, merge_overlappings=True):
    def merge_pol(pol, id_pol):
        ids_to_merge = []
        for polid in idx_pol.intersection(pol.bounds):
            if pol.intersection(dico_pol[polid]).area:
                ids_to_merge.append(polid)
        if not ids_to_merge:
            idx_pol.insert(id_pol, pol.bounds)
            dico_pol[id_pol] = pol
            id_pol += 1
            return id_pol
        try:
            merged_pols = ops.unary_union(
                [dico_pol[polid] for polid in ids_to_merge] + [pol]
            )
        except Exception as e:
            UI.bug_report()
            UI.vprint(2, e)
            return id_pol
        for polid in ids_to_merge:
            idx_pol.delete(polid, dico_pol[polid].bounds)
            dico_pol.pop(polid, None)
        for pol in (
            merged_pols.geoms
            if "Multi" in merged_pols.geom_type
            else [merged_pols]
        ):
            assert isinstance(pol, geometry.Polygon)
            for subpol in [pol]:  # in split_polygon(merged_pols,10):
                idx_pol.insert(id_pol, subpol.bounds)
                dico_pol[id_pol] = subpol
                id_pol += 1
        return id_pol

    def add_pol(pol, id_pol):
        dico_pol[id_pol] = pol
        id_pol += 1
        return id_pol

    UI.progress_bar(1, 0)
    idx_pol = index.Index()
    dico_pol = {}
    id_pol = 0
    todo = len(multipol.geoms) if "Multi" in multipol.geom_type else 1
    step = int(todo / 100) + 1
    done = 0
    # we sort the geometries according to the area of their bounding box,
    # larger first since it is probably more efficient this way
    iterloop = (
        sorted(
            multipol.geoms,
            key=lambda geom: geometry.box(*geom.bounds).area,
            reverse=True,
        )
        if "Multi" in multipol.geom_type
        else [multipol]
    )
    for pol in iterloop:
        if not pol.area:
            done += 1
            continue
        if not pol.is_valid:
            UI.logprint(
                "Invalid polygon detected at", list(pol.exterior.coords)[0]
            )
            done += 1
            continue
        if merge_overlappings:
            id_pol = merge_pol(pol, id_pol)
        else:
            id_pol = add_pol(pol, id_pol)
        done += 1
        if done % step == 0:
            UI.progress_bar(1, int(100 * done / todo))
            if UI.red_flag:
                return 0
    return (idx_pol, dico_pol)


################################################################################
def cut_to_tile(
    input_geometry, xmin=0, xmax=1, ymin=0, ymax=1, strictly_inside=False
):
    if not strictly_inside:
        return input_geometry.intersection(
            geometry.Polygon(
                [
                    (xmin, ymin),
                    (xmax, ymin),
                    (xmax, ymax),
                    (xmin, ymax),
                    (xmin, ymin),
                ]
            )
        )
    else:
        return input_geometry.intersection(
            geometry.Polygon(
                [
                    (xmin, ymin),
                    (xmax, ymin),
                    (xmax, ymax),
                    (xmin, ymax),
                    (xmin, ymin),
                ]
            )
        ).difference(
            geometry.LineString(
                [
                    (xmin, ymin),
                    (xmax, ymin),
                    (xmax, ymax),
                    (xmin, ymax),
                    (xmin, ymin),
                ]
            )
        )


################################################################################
def ensure_MultiPolygon(input_geometry):
    if input_geometry.is_empty:
        return geometry.MultiPolygon()
    elif input_geometry.geom_type == "MultiPolygon":
        return input_geometry
    elif input_geometry.geom_type == "Polygon":
        return geometry.MultiPolygon([input_geometry])
    elif "Collection" in input_geometry.geom_type:
        return geometry.MultiPolygon(
            (pol for pol in input_geometry.geoms if pol.geom_type == "Polygon")
        )
    else:
        return geometry.MultiPolygon()


################################################################################
def ensure_MultiLineString(input_geometry):
    if input_geometry.is_empty:
        return geometry.MultiLineString()
    elif input_geometry.geom_type == "MultiLineString":
        return input_geometry
    elif input_geometry.geom_type in ["LineString", "LinearRing"]:
        return geometry.MultiLineString([input_geometry])
    elif "Collection" in input_geometry.geom_type:
        valid_lines = [line for line in input_geometry.geoms
                        if line.geom_type in ["LineString", "LinearRing"]]
        return geometry.MultiLineString(valid_lines or [])
    else:
        return geometry.MultiLineString()


################################################################################
def indexed_difference(idx_pol1, dico_pol1, idx_pol2, dico_pol2):
    idx_out = index.Index()
    dico_out = {}
    idnew = 0
    for polid1, pol1 in dico_pol1.items():
        for polid2 in idx_pol2.intersection(pol1.bounds):
            if pol1.intersects(dico_pol2[polid2]):
                pol1 = pol1.difference(dico_pol2[polid2])
        if pol1.area:
            for pol in pol1 if "Multi" in pol1.geom_type else [pol1]:
                idx_out.insert(idnew, pol.bounds)
                dico_out[idnew] = pol
                idnew += 1
    return idx_out, dico_out


################################################################################
def coastline_to_MultiPolygon(coastline, lat, lon, custom_source=False):
    def encode_to_next(coord, new_way, remove_coords):
        UI.vprint(3, "Computing next  coord for", coord)
        if coord in inits:
            UI.vprint(3, "    This is an init one")
            idx = inits.index(coord)
            new_way += segments[idx][2]
            next_coord = segments[idx][1]
            UI.vprint(3, "    End one is", next_coord)
            remove_coords.append(coord)
            remove_coords.append(next_coord)
        else:
            UI.vprint(3, "    This is and end one")
            idx = bdcoords.index(coord)
            if idx < len(bdcoords) - 1:
                next_coord = bdcoords[idx + 1]
                UI.vprint(3, "    The following one is", next_coord)
                next_coord_loop = next_coord
            else:
                next_coord = bdcoords[0]
                next_coord_loop = next_coord + 4
            interp_coord = ceil(coord)
            while interp_coord < next_coord_loop:
                new_way += bd_point(interp_coord)
                UI.vprint(3, "Interp coord", bd_point(interp_coord))
                interp_coord += 1
        return next_coord

    coastline = ensure_MultiLineString(coastline)
    islands = []
    interior_seas = []
    segments = []
    bdpolys = []
    ends = []
    inits = []
    osm_error = False
    osm_badpoints = []
    for line in coastline.geoms:
        if line.is_ring:
            if custom_source or geometry.LinearRing(line).is_ccw:
                islands.append(list(line.coords))
            else:
                interior_seas.append(list(line.coords))
        else:
            tmp = list(line.coords)
            if (
                numpy.min(
                    numpy.abs(
                        [tmp[0][0] - int(tmp[0][0]), tmp[0][1] - int(tmp[0][1])]
                    )
                )
                > 0.00001
            ):
                osm_error = True
                osm_badpoints.append((tmp[0][1] + lat, tmp[0][0] + lon))
            if (
                numpy.min(
                    numpy.abs(
                        [
                            tmp[-1][0] - int(tmp[-1][0]),
                            tmp[-1][1] - int(tmp[-1][1]),
                        ]
                    )
                )
                > 0.00001
            ):
                osm_error = True
                osm_badpoints.append((tmp[-1][1] + lat, tmp[-1][0] + lon))
            segments.append([bd_coord(tmp[0]), bd_coord(tmp[-1]), tmp])
            ends.append(bd_coord(tmp[-1]))
            inits.append(bd_coord(tmp[0]))
    if osm_error:
        UI.lvprint(
            1,
            "ERROR in OSM coastline data. Coastline abruptly stops at",
            osm_badpoints,
        )
        return geometry.MultiPolygon()
    bdcoords = sorted(ends + inits)
    UI.vprint(3, "bdcoords=", bdcoords)
    UI.vprint(3, "inits=", ends)
    UI.vprint(3, "ends=", inits)
    while bdcoords:
        UI.vprint(3, "new loop")
        new_way = []
        remove_coords = []
        first_coord = bdcoords[0]
        next_coord = encode_to_next(first_coord, new_way, remove_coords)
        count = 0
        while next_coord != first_coord:
            count += 1
            UI.vprint(3, next_coord)
            next_coord = encode_to_next(next_coord, new_way, remove_coords)
            if count == 1000:  # dead loop caused by faulty osm coastline data
                UI.lvprint(
                    1,
                    "ERROR is OSM coastline data, probably caused by a ",
                    "coastline way with wrong orientation.",
                )
                return geometry.MultiPolygon()
        bdpolys.append(new_way)
        for coord in remove_coords:
            try:
                bdcoords.remove(coord)
            except:
                (x, y) = bd_point(coord)
                UI.lvprint(
                    1,
                    "ERROR is OSM coastline data, probably caused by a ",
                    "triple junction around lat=",
                    str(y + lat),
                    " lon=",
                    str(x + lon),
                )
                return geometry.MultiPolygon()
    if not bdpolys:  # and islands:
        bdpolys.append([(0, 0), (0, 1), (1, 1), (1, 0)])
    outpol = ops.unary_union(
        [geometry.Polygon(bdpoly).buffer(0) for bdpoly in bdpolys]
    )
    inpol = ensure_MultiPolygon(
        cut_to_tile(
            ops.unary_union(
                [
                    geometry.Polygon(loop).buffer(0)
                    for loop in islands + interior_seas
                ]
            )
        )
    )
    return ensure_MultiPolygon(outpol.symmetric_difference(inpol))


################################################################################
def bd_coord(pt):
    # distance along the boundary of the unit square in cw direction starting
    # from (0,0)
    return geometry.LineString(
        [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
    ).project(geometry.Point(pt))


################################################################################
def bd_point(coord):
    # point a coord distance along the boundary of the unit square in
    # cw direction starting from (0,0)
    return list(
        geometry.LineString([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
        .interpolate(coord % 4)
        .coords
    )


################################################################################
def length_in_meters(way_or_geometry):
    if isinstance(way_or_geometry, numpy.ndarray):
        return (
            affinity.scale(
                geometry.LineString(way_or_geometry), scalx, 1
            ).length
            * GEO.lat_to_m
        )
    else:
        return affinity.scale(way_or_geometry, scalx, 1).length * GEO.lat_to_m


################################################################################
# When we buffer a collection of polygon they might become very close to each
# others or form very small inner holes. The next function will first grow them
# by a larger amount than the goal one, and then shrink the resulting set by the
# difference. This has the desired effect has small holes are note recreated
# once filled.
################################################################################
def improved_buffer(
    input_geometry,
    buffer_width,
    separation_width,
    simplify_length,
    show_progress=False,
):
    buffer_width *= GEO.m_to_lat
    separation_width *= GEO.m_to_lat
    simplify_length *= GEO.m_to_lat
    if show_progress:
        UI.progress_bar(1, 0)
    input_geometry = affinity.affine_transform(
        input_geometry, [scalx, 0, 0, 1, 0, 0]
    )
    output_geometry = input_geometry.buffer(
        buffer_width + separation_width,
        join_style=2,
        mitre_limit=1.5,
        resolution=1,
    )
    if show_progress:
        UI.progress_bar(1, 40)
    if UI.red_flag:
        return geometry.Polygon()
    output_geometry = output_geometry.buffer(
        -1 * separation_width, join_style=2, mitre_limit=1.5, resolution=1
    )
    if show_progress:
        UI.progress_bar(1, 80)
    if UI.red_flag:
        return geometry.Polygon()
    if simplify_length:
        output_geometry = output_geometry.simplify(simplify_length)
    if show_progress:
        UI.progress_bar(1, 100)
    if UI.red_flag:
        return geometry.Polygon()
    output_geometry = affinity.affine_transform(
        output_geometry, [1 / scalx, 0, 0, 1, 0, 0]
    )
    return output_geometry


################################################################################
# Computes the normal vectors along a way, obtained at each node as the mean
# between the normals to the segments departing and arriving at that node.
# The parameter scalx is inteded to account for orthogonal but non euclidean
# metrics, in the case of geographic coordinates this is just cos(lat*pi/180)
################################################################################
def weighted_normals(way, side="left"):  # normalized in the given metric
    N = len(way)
    if N < 2:
        return numpy.zeros(N)
    sign = (
        numpy.array([[-1 / scalx, 1]])
        if side == "left"
        else numpy.array([[1 / scalx, -1]])
    )
    tg = way[1:] - way[:-1]
    tg[:, 0] *= scalx
    tg = tg / (1e-6 + numpy.linalg.norm(tg, axis=1)).reshape(N - 1, 1)
    tg = numpy.vstack([tg, tg[-1]])
    if N > 2:
        scale = 1e-6 + numpy.linalg.norm(tg[1:-1] + tg[:-2], axis=1).reshape(
            N - 2, 1
        )
        tg[1:-1] = (tg[1:-1] + tg[:-2]) / (scale)
        if (way[0] == way[-1]).all():
            scale = 1e-6 + numpy.linalg.norm(tg[0] + tg[-1])
            tg[0] = tg[-1] = (tg[0] + tg[-1]) / (scale)
    return numpy.roll(tg, 1, axis=1) * sign


################################################################################
def shift_way(way, shift, side="left"):  # shift in m
    return way + shift * GEO.m_to_lat * weighted_normals(way, side)


################################################################################
def buffer_simple_way(way, width):  # width assumed in meter
    width *= GEO.m_to_lat
    way_normals = weighted_normals(way, "left")
    return numpy.concatenate(
        (
            way - 0.5 * width * way_normals,
            (way + 0.5 * width * way_normals)[::-1],
            way[:1] - 0.5 * width * way_normals[:1],
        )
    )


################################################################################
def refine_way(way, max_length):  # max_length assumed in meter
    new_way = []
    for i in range(len(way) - 1):
        new_way.append(way[i])
        ins = int(
            sqrt(
                numpy.sum(
                    (way[i] - way[i + 1]) ** 2 * numpy.array([[scalx ** 2, 1]])
                )
            )
            * GEO.lat_to_m
            // max_length
        )
        new_way.extend(
            [
                (
                    j / (ins + 1) * way[i + 1][0]
                    + (ins + 1 - j) / (ins + 1) * way[i][0],
                    j / (ins + 1) * way[i + 1][1]
                    + (ins + 1 - j) / (ins + 1) * way[i][1],
                )
                for j in range(1, ins + 1)
            ]
        )
    new_way.append(way[-1])
    return numpy.array(new_way)


################################################################################
#  THE LONGITUDINAL ROAD CLAMP
#  (owner RULINGS 2026-08-31b "ROAD PROFILE LAW" + "LEVERAGE THE CORE";
#  docs/specs/linear-transport-redesign-spec.md §2 item 1)
#
#  The law in one line: a road FOLLOWS TERRAIN, and where terrain exceeds
#  the road's grade cap it LIFTS or CUTS the MINIMUM needed to hold the
#  cap.  Everything below is that sentence, per way, on the CENTERLINE.
################################################################################

#: Station spacing of the clamp (metres).  <= 20 m on purpose: the
#: instrument that prices the clamp must OUTRESOLVE ``emit_decimate``'s
#: 60 m chords (census #112), and a profile law sampled coarser than the
#: geometry it governs cannot see the step it creates.
DEFAULT_ROAD_STATION_M = 20.0


def cap_lipschitz_profile(stations_s, values, cap):
    """THE CLAMP, geometry-free so a twin can state it directly.

    ``stations_s`` are ascending arclengths (metres) along ONE way,
    ``values`` its per-station terrain altitude, ``cap`` the longitudinal
    grade limit as a fraction (0.08 = 8 %).  Returns the per-station
    clamped altitude.

    THE ALGORITHM is ``auto_patch.free_road_profile.chain_profile``'s
    ENVELOPE branch (ported, not imported — that module retires in
    Batch 2), with every station its own source instead of a pin set,
    which is what a core road with no pins means:

        ceil(s)  = min over stations ( z_j + cap·|s − s_j| )   (minorant)
        floor(s) = max over stations ( z_j − cap·|s − s_j| )   (majorant)
        clamped  = (floor + ceil) / 2

    ``floor`` is the smallest cap-Lipschitz function that is >= the
    terrain (the LIFT-ONLY answer, an embankment everywhere) and
    ``ceil`` the largest that is <= it (the CUT-ONLY answer, a cutting
    everywhere).  Their mid-profile is cap-Lipschitz because both are,
    and it is the MINIMUM intervention in the sup norm: for a chain,
    ``max(floor − ceil)`` is exactly the profile's worst cap violation
    ``max_{j,k}(|z_j − z_k| − cap·d_jk)``, and no cap-lawful profile can
    sit closer than half of that to the terrain.  So the clamp lifts the
    low side and cuts the high side by the same, smallest possible
    amount — "lift or cut the minimum needed to hold the cap".

    WHERE THE TERRAIN IS ALREADY CAP-LAWFUL THE RESULT IS THE TERRAIN,
    identically: terrain is then its own smallest majorant and largest
    minorant, so ``floor == ceil == z``.  That identity is the owner's
    "a road capped below 8 % into a cutting is a defect" expressed as a
    property of the code, and it is the first twin.

    Both envelopes are computed in two vectorised sweeps each (the
    max-plus/min-plus distance transform along the chain), so the pass
    is O(n) in numpy with no Python loop over stations.
    """
    s = numpy.asarray(stations_s, dtype=numpy.float64).ravel()
    z = numpy.asarray(values, dtype=numpy.float64).ravel()
    if len(z) < 2 or not numpy.isfinite(cap) or cap <= 0:
        return z.copy()
    cs = float(cap) * s
    # Smallest cap-Lipschitz MAJORANT: max_j (z_j - cap*|s-s_j|).
    fwd = numpy.maximum.accumulate(z + cs) - cs           # over j <= i
    bwd = numpy.maximum.accumulate((z - cs)[::-1])[::-1] + cs  # over j >= i
    floor = numpy.maximum(fwd, bwd)
    # Largest cap-Lipschitz MINORANT: min_j (z_j + cap*|s-s_j|).
    fwd = numpy.minimum.accumulate(z - cs) + cs
    bwd = numpy.minimum.accumulate((z + cs)[::-1])[::-1] - cs
    ceil_ = numpy.minimum(fwd, bwd)
    return 0.5 * (floor + ceil_)


def way_arclengths(way):
    """Cumulative arclength (metres) along a tile-relative way.

    The SAME metric ``refine_way`` measures its own spacing with
    (``scalx``-scaled degrees × ``GEO.lat_to_m``) — one length
    convention for the clamp's stations and the sampling that made
    them, never two.
    """
    pts = numpy.asarray(way, dtype=numpy.float64)
    if len(pts) < 2:
        return numpy.zeros(len(pts))
    d = numpy.diff(pts, axis=0) * numpy.array([[scalx, 1.0]])
    seg = numpy.sqrt((d ** 2).sum(axis=1)) * GEO.lat_to_m
    return numpy.concatenate(([0.0], numpy.cumsum(seg)))


class Levelled_Roads:
    """The clamped centerline stations of a tile's banked road network.

    ONE WAY IS ONE PROFILE (census #111 option i, and the trap it names).
    The clamp runs PER WAY on the CENTERLINE — never on the merged
    buffered ring, whose vertex order walks up one side of a road and
    back down the other and then jumps to an unrelated road: a profile
    law run in that order would fuse two roads that merely share a ring,
    and would read a road's two kerbs as a 4 m-long climb.  Ways are held
    in separate profiles here and are never concatenated; the KD-tree
    below is only an ANSWERING index (nearest station), never a chain.

    ``answer`` is what ``include_roads``' ``alt_vec_shift`` calls: the
    nearest clamped station within ``radius_m`` wins, and beyond it the
    shifted DEM answers unchanged, so ground the clamp never stationed
    is never invented.
    """

    def __init__(self, cap, lane_width, station_m=DEFAULT_ROAD_STATION_M,
                 materiality_m=0.01):
        self.cap = float(cap)
        self.lane_width = float(lane_width)
        self.station_m = float(station_m)
        self.materiality_m = float(materiality_m)
        self.radius_m = 2.0 * float(lane_width)
        self.ways = []
        self._tree = None
        self._alts = numpy.zeros(0)

    def add_way(self, points, dem_alt, clamped_alt, s_m):
        self.ways.append({
            "points": numpy.asarray(points, dtype=numpy.float64),
            "dem": numpy.asarray(dem_alt, dtype=numpy.float64),
            "alt": numpy.asarray(clamped_alt, dtype=numpy.float64),
            "s_m": numpy.asarray(s_m, dtype=numpy.float64),
        })

    @property
    def station_count(self):
        return int(sum(len(w["alt"]) for w in self.ways))

    def finalize(self):
        """Build the nearest-station index (cKDTree, one per tile)."""
        from scipy.spatial import cKDTree

        if not self.ways:
            self._tree = None
            return self
        pts = numpy.concatenate([w["points"] for w in self.ways])
        self._alts = numpy.concatenate([w["alt"] for w in self.ways])
        # The tree lives in the scalx-scaled degree frame, where a
        # distance is degrees of LATITUDE — the frame every metre
        # constant in this module converts into via GEO.m_to_lat.
        self._tree = cKDTree(pts * numpy.array([[scalx, 1.0]]))
        return self

    def answer(self, query_points, dem_alt):
        """Clamped altitude at ``query_points``, DEM beyond the radius."""
        out = numpy.array(dem_alt, dtype=numpy.float64, copy=True)
        if self._tree is None or not len(out):
            return out
        q = numpy.asarray(query_points, dtype=numpy.float64)
        q = q * numpy.array([[scalx, 1.0]])
        dist, idx = self._tree.query(
            q, distance_upper_bound=self.radius_m * GEO.m_to_lat
        )
        hit = numpy.isfinite(dist)
        if hit.any():
            out[hit] = self._alts[idx[hit]]
        return out

    def summary(self):
        """Population + intervention counts (the measurability read)."""
        n_st = 0
        n_moved = 0
        lift = 0.0
        cut = 0.0
        for w in self.ways:
            delta = w["alt"] - w["dem"]
            n_st += len(delta)
            n_moved += int((numpy.abs(delta) > self.materiality_m).sum())
            if len(delta):
                lift = max(lift, float(delta.max()))
                cut = max(cut, float((-delta).max()))
        return {
            "ways": len(self.ways),
            "stations": n_st,
            "clamped_stations": n_moved,
            "max_lift_m": round(max(lift, 0.0), 4),
            "max_cut_m": round(max(cut, 0.0), 4),
        }

    def sidecar(self, lat, lon):
        """The ``o4_levelled_roads.json`` payload (absolute lat/lon).

        Parallel arrays per way, not a dict per station: the tile-wide
        banked network runs to 10^5 stations and a station object each
        would make the instrument's own input the build's biggest file.
        """
        ways = []
        for i, w in enumerate(self.ways):
            delta = w["alt"] - w["dem"]
            ways.append({
                "index": i,
                "stations": len(w["alt"]),
                "length_m": round(float(w["s_m"][-1]) if len(w["s_m"])
                                  else 0.0, 2),
                "clamped_stations": int(
                    (numpy.abs(delta) > self.materiality_m).sum()),
                "max_lift_m": round(float(delta.max()) if len(delta)
                                    else 0.0, 4),
                "max_cut_m": round(float((-delta).max()) if len(delta)
                                   else 0.0, 4),
                "lat": [round(float(lat + p[1]), 7) for p in w["points"]],
                "lon": [round(float(lon + p[0]), 7) for p in w["points"]],
                "s_m": [round(float(v), 2) for v in w["s_m"]],
                "dem_alt": [round(float(v), 3) for v in w["dem"]],
                "alt": [round(float(v), 3) for v in w["alt"]],
            })
        return {
            "version": 1,
            "producer": "O4_Vector_Map.include_roads",
            "lat": int(lat),
            "lon": int(lon),
            "grade_cap": self.cap,
            "station_max_m": self.station_m,
            "lane_width_m": self.lane_width,
            "answer_radius_m": self.radius_m,
            "materiality_m": self.materiality_m,
            "summary": self.summary(),
            "ways": ways,
        }


def clamp_road_network(road_network, alt_vec, cap, lane_width,
                       station_m=DEFAULT_ROAD_STATION_M):
    """Clamp every way of a banked-road MultiLineString, INDEPENDENTLY.

    ``alt_vec`` is the tile DEM sampler (an ``(n, 2)`` tile-relative
    array in, ``n`` altitudes out) — the SAME surface ``alt_vec_shift``
    answers from, so a station and the ring vertex that reads it stand
    on one DEM.  Returns a finalized :class:`Levelled_Roads`.
    """
    out = Levelled_Roads(cap, lane_width, station_m)
    geoms = getattr(road_network, "geoms", None)
    if geoms is None:
        geoms = [road_network] if road_network is not None else []
    for geom in geoms:
        try:
            coords = numpy.array(geom.coords, dtype=numpy.float64)
        except (AttributeError, ValueError):            # pragma: no cover
            continue
        if len(coords) < 2:
            continue
        stations = refine_way(coords, station_m)
        s = way_arclengths(stations)
        dem = numpy.asarray(alt_vec(stations), dtype=numpy.float64)
        # ONE WAY, ONE CALL: the clamp never sees another way's stations.
        clamped = cap_lipschitz_profile(s, dem, cap)
        out.add_way(stations, dem, clamped, s)
    return out.finalize()


################################################################################
def least_square_fit_altitude_along_way(way, steps, dem, weights=False):
    linestring = affinity.affine_transform(
        geometry.LineString(way), [scalx, 0, 0, 1, 0, 0]
    )
    tmp = dem.alt_vec(
        numpy.array(
            geometry.LineString(
                [
                    linestring.interpolate(x, normalized=True)
                    for x in numpy.arange(steps + 1) / steps
                ]
            ).coords
            * numpy.array([1 / scalx, 1])
        )
    )
    if not weights:
        return (
            linestring,
            numpy.polyfit(numpy.arange(steps + 1) / steps, tmp, 7),
        )
    else:
        w = (
            numpy.maximum(
                numpy.arange(steps + 1), steps - numpy.arange(steps + 1)
            )
            + steps // 2
        ) ** 2
        return (
            linestring,
            numpy.polyfit(numpy.arange(steps + 1) / steps, tmp, 7, w=w),
        )


################################################################################
# def spline_fit_altitude_along_way(way, steps, dem, weights=False):
#     linestring = affinity.affine_transform(
#         geometry.LineString(way), [scalx, 0, 0, 1, 0, 0]
#     )
#     tmp = dem.alt_vec(
#         numpy.array(
#             geometry.LineString(
#                 [
#                     linestring.interpolate(x, normalized=True)
#                     for x in numpy.arange(steps + 1) / steps
#                 ]
#             )
#             * numpy.array([1 / scalx, 1])
#         )
#     )
#     if not weights:
#         return (
#             linestring,
#             scipy.interpolate.splrep(numpy.arange(steps + 1) / steps, tmp, s=0),
#         )
#     else:
#         w = (
#             numpy.maximum(
#                 numpy.arange(steps + 1), steps - numpy.arange(steps + 1)
#             )
#             + steps // 2
#         ) ** 2
#         w /= numpy.sum(w)
#         return (
#             linestring,
#             scipy.interpolate.splrep(numpy.arange(steps + 1) / steps, tmp, w=w),
#         )

################################################################################
def weighted_alt(node, alt_idx, alt_dico, dem):
    eps1 = 0.003
    eps2 = 0.0003
    alti = 0
    weights = 0
    (x, y) = (node[0] * scalx, node[1])
    pt = geometry.Point((x, y))
    for idx in alt_idx.intersection((x - eps1, y - eps1, x + eps1, y + eps1)):
        (linestring, leastsquarefit, width) = alt_dico[idx]
        dist = pt.distance(linestring) * GEO.lat_to_m
        weight = numpy.exp(-dist / (2 * width))
        alti += (
            numpy.polyval(
                leastsquarefit, linestring.project(pt, normalized=True)
            )
            * weight
        )
        # alti+=scipy.interpolate.splev(linestring.project(
        # pt,normalized=True),splinefit,der=0)*weight
        weights += weight
    if weights < 1e-6:
        return dem.alt(node)
    if x < eps2 or x > 1 - eps2 or y < eps2 or y > 1 - eps2:
        alpha = min(x / eps2, (1 - x) / eps2, y / eps2, (1 - y) / eps2)
        return alpha * alti / weights + (1 - alpha) * dem.alt(node)
    else:
        return alti / weights


################################################################################
def min_bounding_rectangle(pol):
    pol = affinity.affine_transform(pol, [scalx, 0, 0, 1, 0, 0]).convex_hull
    way = numpy.array(pol.exterior.coords)
    edges = way[1:] - way[:-1]
    min_area = 9999
    for i in range(len(edges)):
        angle = atan2(edges[i, 1], edges[i, 0])
        (xmin, ymin, xmax, ymax) = affinity.rotate(
            pol, -1 * angle, origin=tuple(way[i]), use_radians=True
        ).bounds
        test_area = (ymax - ymin) * (xmax - xmin)
        if test_area < min_area:
            min_area = test_area
            ret_val = (i, angle, xmin, ymin, xmax, ymax)
    (i, angle, xmin, ymin, xmax, ymax) = ret_val
    return affinity.affine_transform(
        affinity.rotate(
            geometry.box(xmin, ymin, xmax, ymax),
            angle,
            origin=tuple(way[i]),
            use_radians=True,
        ),
        [1 / scalx, 0, 0, 1, 0, 0],
    )


################################################################################
def dummy_alt(way):
    return numpy.zeros(way.shape[0])
