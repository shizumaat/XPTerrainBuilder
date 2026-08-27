import time
import sys
import os
import pickle
import subprocess
import numpy
from math import cos, isfinite, pi
import O4_DEM_Utils as DEM
import O4_Airport_Elevation_Insets as INSETS
import O4_Elevation_Level as ELEVATION_LEVEL
import O4_UI_Utils as UI
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Proj_Runtime as PROJRT
import O4_Vector_Utils as VECT
import O4_OSM_Utils as OSM
import O4_Version

if "dar" in sys.platform:
    Triangle4XP_cmd = os.path.join(FNAMES.Utils_dir, "mac", "Triangle4XP ")
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "mac", "triangle ")
    sort_mesh_cmd = os.path.join(FNAMES.Utils_dir, "mac", "moulinette ")
    unzip_cmd = os.path.join(FNAMES.Utils_dir, "mac", "7zz")
    if not os.path.exists(unzip_cmd):
        unzip_cmd = "7z"
elif "win" in sys.platform:
    Triangle4XP_cmd = os.path.join(FNAMES.Utils_dir, "win", "Triangle4XP.exe ")
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "win", "triangle.exe ")
    sort_mesh_cmd = os.path.join(FNAMES.Utils_dir, "win", "moulinette.exe ")
    unzip_cmd = os.path.join(FNAMES.Utils_dir, "win", "7z.exe")
else:
    Triangle4XP_cmd = os.path.join(FNAMES.Utils_dir, "lin", "Triangle4XP ")
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "lin", "triangle ")
    sort_mesh_cmd = os.path.join(FNAMES.Utils_dir, "lin", "moulinette ")
    unzip_cmd = "7z "


community_server = False
if os.path.exists(FNAMES.resource_path("community_server.txt")):
    try:
        f = open(FNAMES.resource_path("community_server.txt"), "r")
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            if "#" in line:
                if line[0] == "#":
                    continue
                else:
                    line = line.split("#")[0].strip()
            if not line:
                continue
            community_server = True
            community_prefix = line
            break
    except:
        pass


##############################################################################


##############################################################################
def build_curv_tol_weight_map(tile, weight_array):
    if tile.apt_curv_tol != tile.curvature_tol and tile.apt_curv_tol > 0:
        UI.vprint(
            1, "-> Modifying curv_tol weight map according to runway locations."
        )
        try:
            f = open(FNAMES.apt_file(tile), "rb")
            dico_airports = pickle.load(f)
            f.close()
        except:
            UI.vprint(
                1,
                "   WARNING: File",
                FNAMES.apt_file(tile),
                "is missing (erased after Step 1?), cannot check airport info ",
                "for upgraded zoomlevel.",
            )
            dico_airports = {}
        for airport in dico_airports:
            (xmin, ymin, xmax, ymax) = dico_airports[airport]["boundary"].bounds
            x_shift = 1000 * tile.apt_curv_ext * GEO.m_to_lon(tile.lat)
            y_shift = 1000 * tile.apt_curv_ext * GEO.m_to_lat
            colmin = max(round((xmin - x_shift) * 1000), 0)
            colmax = min(round((xmax + x_shift) * 1000), 1000)
            rowmax = min(round(((1 - ymin) + y_shift) * 1000), 1000)
            rowmin = max(round(((1 - ymax) - y_shift) * 1000), 0)
            weight_array[rowmin : rowmax + 1, colmin : colmax + 1] = (
                tile.curvature_tol / tile.apt_curv_tol
            )
    if tile.coast_curv_tol != tile.curvature_tol:
        UI.vprint(
            1,
            "-> Modifying curv_tol weight map according to coastline location.",
        )
        sea_layer = OSM.OSM_layer()
        custom_coastline = FNAMES.custom_coastline(tile.lat, tile.lon)
        custom_coastline_dir = FNAMES.custom_coastline_dir(tile.lat, tile.lon)
        if os.path.isfile(custom_coastline):
            UI.vprint(1, "    * User defined custom coastline data detected.")
            sea_layer.update_dicosm(
                custom_coastline, input_tags=None, target_tags=None
            )
        elif os.path.isdir(custom_coastline_dir):
            UI.vprint(
                1,
                "    * User defined custom coastline data detected ",
                "(multiple files).",
            )
            for osm_file in os.listdir(custom_coastline_dir):
                UI.vprint(2, "      ", osm_file)
                sea_layer.update_dicosm(
                    os.path.join(custom_coastline_dir, osm_file),
                    input_tags=None,
                    target_tags=None,
                )
                sea_layer.write_to_file(custom_coastline)
        else:
            queries = ['way["natural"="coastline"]']
            tags_of_interest = []
            if not OSM.OSM_queries_to_OSM_layer(
                queries,
                sea_layer,
                tile.lat,
                tile.lon,
                tags_of_interest,
                cached_suffix="coastline",
            ):
                return 0
        for nodeid in sea_layer.dicosmn:
            (lonp, latp) = [float(x) for x in sea_layer.dicosmn[nodeid]]
            if (
                lonp < tile.lon
                or lonp > tile.lon + 1
                or latp < tile.lat
                or latp > tile.lat + 1
            ):
                continue
            x_shift = 1000 * tile.coast_curv_ext * GEO.m_to_lon(tile.lat)
            y_shift = tile.coast_curv_ext / (111.12)
            colmin = max(round((lonp - tile.lon - x_shift) * 1000), 0)
            colmax = min(round((lonp - tile.lon + x_shift) * 1000), 1000)
            rowmax = min(round((tile.lat + 1 - latp + y_shift) * 1000), 1000)
            rowmin = max(round((tile.lat + 1 - latp - y_shift) * 1000), 0)
            weight_array[
                rowmin : rowmax + 1, colmin : colmax + 1
            ] = numpy.maximum(
                weight_array[rowmin : rowmax + 1, colmin : colmax + 1],
                tile.curvature_tol / tile.coast_curv_tol,
            )
        del sea_layer
    # It could be of interest to write the weight file as a png for user
    # editing from PIL import Image
    # Image.fromarray((weight_array!=1).astype(numpy.uint8)*255).save(
    # 'weight.png')
    return


################################################################################
# Triangle's .ele format declares the triangle ATTRIBUTE column REAL, and
# Triangle4XP does write a genuine float in it when it had to mesh inside a
# degenerate sliver: tile +25+051 came back with two triangles carrying the
# attribute 1.4375, whose four corners are one and the same point down to the
# 11th decimal.  Vertex index columns are always ints and keep being read as
# such; only the attribute needs the real reading.  A NON-integral attribute
# is a measured degeneracy -- no combination of the dico_attributes bits can
# be meant by it -- so the triangle gets the dummy attribute, which asks for
# no post-treatment at all.  For a sliver whose corners are the same point to
# within a micron that is not an approximation, it is exact.
ATTRIBUTE_INTEGRAL_TOL = 1e-6


def read_triangle_attribute(text):
    """Read one triangle attribute column: (attribute, is_integral).

    The attribute comes back as an int in both integral cases -- plain
    integer text ("16") and an integral real ("16.0").  Anything else the
    REAL column may legally hold (a fractional value like "1.4375", or a
    non-finite one) reports the dummy attribute and False.
    """
    try:
        return (int(text), True)
    except ValueError:
        pass
    attribute = float(text)
    if isfinite(attribute):
        rounded = int(round(attribute))
        if abs(attribute - rounded) <= ATTRIBUTE_INTEGRAL_TOL:
            return (rounded, True)
    return (VECT.Vector_Map.dico_attributes["DUMMY"], False)


################################################################################
# R18-1b — NO VERTEX INSIDE A PATCH FACE ANSWERS WITH DEM
# (Fable lead amendment 1, 2026-08-12, docs/specs/round18-heca-mesh-and-
# pads-spec.md, on the round-18 refutation of the seeding hypothesis).
#
# THE DEFECT, measured interventionally on +30+031: every one of the
# 3,204 faces in HECA's patch coverage is INTERP_ALT-seeded (the round's
# sub-cell seeding pass adds ZERO), and the hill at 30.1170578,
# 31.4098155 still stood at 98.05 m inside an 86 m apron, with 54 free
# interior vertices more than 3 m above their 8 nearest patch nodes.
# The cause is the treatment itself: for an INTERP_ALT triangle the loop
# below assigns each vertex ITS OWN carried vector altitude
# (``vertices[6v+2] = vertices[6v+5]``).  For a vertex the vector map
# authored — a patch ring node, a road ribbon node — that value IS the
# patched surface.  For a FREE INTERIOR vertex, one Triangle4XP inserted
# to refine the face, it is the DEM the mesher sampled.  So the flood
# marks the face correctly and then hands its interior back to the DEM.
#
# THE LAW: such a vertex takes its altitude INTERPOLATED FROM THE
# PATCH-VALUED VERTICES of its face.  Implemented as the discrete
# HARMONIC extension over the INTERP_ALT sub-mesh: the authored vertices
# are Dirichlet data, every free vertex is the (uniformly) weighted mean
# of its neighbours, solved exactly as one sparse linear system.  That
# is planar on a face whose authored boundary is planar (it reproduces
# the plane exactly), smooth across a face whose boundary is not,
# deterministic, and costs one solve over the free vertices alone.
# No new marker, no new attribute, nothing written for any vertex the
# vector map authored.
_INTERPOLATED_INTERIOR_REPORT = {}


def interpolate_free_interior_altitudes(
    vertices, triangles, patch_valued_indices, report=None,
):
    """Harmonic-extend the PATCH-VALUED altitudes over everything else.

    ``vertices``   — the flat 6-per-vertex array
                     ``post_process_nodes_altitudes`` loads.  Column 5 is
                     each vertex's carried vector altitude; this function
                     writes column 5 ONLY, for free vertices only, and
                     the caller's existing ``z = column 5`` assignment
                     then does what it always did.  Every patch-valued
                     vertex comes out byte-identical.
    ``triangles``  — the INTERP_ALT-treated triangles, as
                     ``(v1, v2, v3)`` index tuples.
    ``patch_valued_indices`` — the vertices ON A PATCH RING, i.e. the
                     Dirichlet data.  MEASURED, not inferred from the
                     index: the first cut of this used "index below the
                     input-vertex count", which is the vector map's
                     AUTHORED set — and that set includes the orthogrid
                     and gluing-network nodes, which carry the DEM.
                     HECA's hill vertex is exactly one of those (input
                     node 138790, carried altitude 99.33 m, all four
                     incident edges DUMMY), so it was classified
                     untouchable and kept the DEM while 12,936 genuine
                     Steiner points were fixed.  A vertex is
                     patch-valued when it is an endpoint of a
                     ``PATCH_RING_MARKER`` edge — the amendment's own
                     words, "on a patch ring / constrained edge carrying
                     a patch value".

    A free vertex in a component that reaches NO patch-valued vertex has
    no data to interpolate from and keeps its own value — reported,
    never silent, as a legitimate survivor.  That is also what leaves a
    road ribbon outside any patch byte-unchanged.

    Returns the number of free vertices whose altitude was replaced.
    """
    if patch_valued_indices is None or not triangles:
        return 0
    import numpy as _np
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve

    # The sub-mesh: every vertex an INTERP_ALT triangle touches, and
    # every edge of those triangles.
    tri = _np.asarray(sorted(triangles), dtype=_np.int64)
    edges = _np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    edges.sort(axis=1)
    edges = _np.unique(edges, axis=0)
    touched = _np.unique(tri)
    patch_valued = _np.zeros(int(touched.max()) + 1, dtype=bool)
    fixed = _np.asarray(sorted(patch_valued_indices), dtype=_np.int64)
    fixed = fixed[(fixed >= 0) & (fixed < patch_valued.size)]
    if fixed.size == 0:
        if report is not None:
            report.update({"free": 0, "solved": 0, "isolated": 0,
                           "non_finite": 0})
        return 0
    patch_valued[fixed] = True
    free = touched[~patch_valued[touched]]
    if free.size == 0:
        if report is not None:
            report.update({"free": 0, "solved": 0, "isolated": 0})
        return 0

    # Compact indexing over the free vertices; patch-valued vertices
    # stay in the right-hand side as Dirichlet data.
    position = _np.full(int(touched.max()) + 1, -1, dtype=_np.int64)
    position[free] = _np.arange(free.size)
    a, b = edges[:, 0], edges[:, 1]
    a_free = position[a] >= 0
    b_free = position[b] >= 0

    rows, cols, data = [], [], []
    rhs = _np.zeros(free.size)
    # Degree (the diagonal) counts EVERY incident edge, so a patch-valued
    # neighbour pulls exactly as hard as a free one — that is what makes
    # the result the harmonic extension rather than a free-only average.
    degree = _np.zeros(free.size)
    both = a_free & b_free
    _np.add.at(degree, position[a[both]], 1.0)
    _np.add.at(degree, position[b[both]], 1.0)
    rows.extend(position[a[both]])
    cols.extend(position[b[both]])
    data.extend([-1.0] * int(both.sum()))
    rows.extend(position[b[both]])
    cols.extend(position[a[both]])
    data.extend([-1.0] * int(both.sum()))

    # MIXED edges (one patch-valued endpoint, one free) carry the
    # Dirichlet data.  ONE branch, written without assuming which side is
    # which — a two-branch version leaves half of it permanently
    # unexecuted, and unexecuted code is code no twin can check.
    #
    # ``authored_neighbours`` is counted SEPARATELY from ``rhs`` on
    # purpose: a patch-valued neighbour whose altitude is exactly 0.0 m
    # contributes nothing to the right-hand side, so "rhs is still zero"
    # cannot mean "no Dirichlet data" — an airport at sea level would
    # have had its whole interior declared isolated and left on the DEM.
    authored_neighbours = _np.zeros(free.size)
    mixed = a_free ^ b_free
    free_side = _np.where(a_free[mixed], a[mixed], b[mixed])
    authored_side = _np.where(a_free[mixed], b[mixed], a[mixed])
    _np.add.at(degree, position[free_side], 1.0)
    _np.add.at(authored_neighbours, position[free_side], 1.0)
    _np.add.at(rhs, position[free_side], vertices[6 * authored_side + 5])

    # A free vertex whose component never touches a patch-valued vertex has
    # no Dirichlet data at all.  Pin it to its own current value: the
    # system stays non-singular and the vertex is reported untouched.
    reachable = authored_neighbours > 0
    isolated = _np.zeros(free.size, dtype=bool)
    if not reachable.all():
        # Propagate reachability along free-free edges (the component
        # test) — a few sparse sweeps, bounded by the component diameter.
        adjacency = coo_matrix(
            (_np.ones(int(both.sum()) * 2),
             (_np.concatenate([position[a[both]], position[b[both]]]),
              _np.concatenate([position[b[both]], position[a[both]]]))),
            shape=(free.size, free.size)).tocsr()
        seen = reachable.copy()
        while True:
            grown = seen | (adjacency.dot(seen.astype(float)) > 0)
            if grown.sum() == seen.sum():
                break
            seen = grown
        isolated = ~seen
        if isolated.any():
            index = _np.nonzero(isolated)[0]
            degree[index] += 1.0
            rhs[index] += vertices[6 * free[index] + 5]

    rows.extend(range(free.size))
    cols.extend(range(free.size))
    data.extend(degree + 1e-12)          # keeps a 0-degree row solvable
    laplacian = coo_matrix(
        (data, (rows, cols)), shape=(free.size, free.size)).tocsr()
    solution = spsolve(laplacian, rhs)
    solution = _np.asarray(solution).ravel()
    good = _np.isfinite(solution)
    changed = good & ~isolated
    vertices[6 * free[changed] + 5] = solution[changed]
    if report is not None:
        report.update({"free": int(free.size),
                       "solved": int(changed.sum()),
                       "isolated": int(isolated.sum()),
                       "non_finite": int((~good).sum())})
    return int(changed.sum())


# PATCH_RING_MARKER, mirrored from ``O4_Vector_Map`` (importing it here
# would close an import cycle: the vector map is the mesh's producer).
# ``tests/test_r18_free_interior_altitudes.py`` twin-asserts the two
# agree, so a change on either side fails a test rather than silently
# re-scoping this law.
PATCH_RING_MARKER = (
    VECT.Vector_Map.dico_attributes["WATER"]
    | VECT.Vector_Map.dico_attributes["SEA"]
    | VECT.Vector_Map.dico_attributes["SEA_EQUIV"]
    | VECT.Vector_Map.dico_attributes["INTERP_ALT"]
)


def patch_valued_vertex_indices(tile, vertices):
    """The 0-based output-vertex indices that carry a PATCH value.

    A vertex is patch-valued exactly when it is an endpoint of a
    ``PATCH_RING_MARKER`` edge of the input ``.poly`` — that marker is
    what ``include_patches`` stamps on a closed patch way, and nothing
    else wears it.  MEASURED at +30+031: 39,260 of the 157,208 input
    nodes.  Everything else inside an INTERP_ALT face — the orthogrid
    nodes, the gluing network, the road ribbons, and every point the
    mesher inserted — is free, which is the point: HECA's hill was an
    ORTHOGRID node carrying 99.33 m with four DUMMY edges, and any
    discriminator based on "the vector map authored it" protects it.

    Input node ids are 1-based and Triangle writes the input vertices
    first, in order, so id ``i`` is output vertex ``i - 1``.  That is
    VERIFIED against the coordinates rather than trusted; a mismatch
    returns ``None``, which disables the interpolation and leaves the
    historical behaviour, with one loud line.

    Returns ``None`` when it cannot be established.
    """
    try:
        with open(FNAMES.input_node_file(tile)) as handle:
            count = int(handle.readline().split()[0])
            if count <= 0 or 6 * count > len(vertices):
                return None
            for index in range(count):
                columns = handle.readline().split()
                if (float(columns[1]) != vertices[6 * index]
                        or float(columns[2]) != vertices[6 * index + 1]):
                    UI.lvprint(
                        1,
                        "WARNING: the mesher did not preserve the input "
                        f"vertex order at index {index} — the "
                        "free-interior interpolation (R18-1b) is DISABLED "
                        "for this tile and interior vertices keep the DEM.")
                    return None
        indices = set()
        with open(FNAMES.input_poly_file(tile)) as handle:
            line = handle.readline()
            while line.strip() == "" or line.startswith("0 2"):
                line = handle.readline()
            nbr_edges = int(line.split()[0])
            for _ in range(nbr_edges):
                columns = handle.readline().split()
                if len(columns) < 4 or int(columns[3]) != PATCH_RING_MARKER:
                    continue
                indices.add(int(columns[1]) - 1)
                indices.add(int(columns[2]) - 1)
        return indices
    except Exception as error:
        UI.lvprint(
            1,
            "WARNING: could not read the vector inputs to find the "
            "patch-valued vertices — the free-interior interpolation "
            "(R18-1b) is disabled:", str(error))
        return None


################################################################################
def post_process_nodes_altitudes(tile):
    dico_attributes = VECT.Vector_Map.dico_attributes
    f_node = open(FNAMES.output_node_file(tile), "r")
    init_line_f_node = f_node.readline()
    nbr_pt = int(init_line_f_node.split()[0])
    vertices = numpy.zeros(6 * nbr_pt)
    UI.vprint(1, "-> Loading of the mesh computed by Triangle4XP.")
    for i in range(0, nbr_pt):
        vertices[6 * i : 6 * i + 6] = [
            float(x) for x in f_node.readline().split()[1:7]
        ]
    end_line_f_node = f_node.readline()
    f_node.close()
    UI.vprint(1, "-> Post processing of altitudes according to vector data")
    f_ele = open(FNAMES.output_ele_file(tile), "r")
    nbr_tri = int(f_ele.readline().split()[0])
    water_tris = set()
    sea_tris = set()
    interp_alt_tris = set()
    # R18-1b: the vector-authored patch/road regions alone (attribute
    # EXACTLY INTERP_ALT), which are what the free-interior
    # interpolation governs — see its note above.
    _interp_alt_only_tris = []
    degenerate_attr_nbr = 0
    degenerate_attr_sample = []
    for i in range(nbr_tri):
        line = f_ele.readline()
        # triangle attributes are powers of 2, except for the dummy attributed
        # which doesn't require post-treatment.  The test is on the last
        # FIELD, hence the space in front of the zero: the bare last-character
        # test this replaces also skipped "10" (INTERP_ALT|SEA), "20", "16.0"
        # and any other attribute merely ending in a zero.
        if line[-2] == "0" and line[-3] in " \t":
            continue
        columns = line.split()
        (v1, v2, v3) = [int(x) - 1 for x in columns[1:4]]
        (attr, attr_is_integral) = read_triangle_attribute(columns[4])
        if not attr_is_integral:
            # A degenerate triangle: dummy attribute, no post-treatment,
            # counted for the one loud line below.
            degenerate_attr_nbr += 1
            if len(degenerate_attr_sample) < 3:
                degenerate_attr_sample.append((i + 1, columns[4], v1))
            continue
        if attr >= dico_attributes["INTERP_ALT"]:
            interp_alt_tris.add((v1, v2, v3))
            if attr == dico_attributes["INTERP_ALT"]:
                _interp_alt_only_tris.append((v1, v2, v3))
        elif attr & dico_attributes["SEA"] and not (
            attr & dico_attributes["WATER"]
        ):
            # Mapped inland water WINS over coastline sea (see
            # O4_Mask_Utils.water_type_is_inland): a WATER|SEA triangle
            # keeps the inland smoothing below, so a lagoon behind cut
            # polygon rings holds its own level instead of being
            # flattened to sea zero.
            sea_tris.add((v1, v2, v3))
        elif (
            attr & dico_attributes["WATER"]
            or attr & dico_attributes["SEA_EQUIV"]
        ):
            water_tris.add((v1, v2, v3))
    if degenerate_attr_nbr:
        UI.lvprint(
            1,
            "WARNING:",
            degenerate_attr_nbr,
            "triangle(s) came back from Triangle4XP with a non-integral",
            "attribute, i.e. degenerate; they are left untreated (dummy",
            "attribute). First ones:",
            ", ".join(
                "#{} attr={} at ({:.9f}, {:.9f})".format(
                    tri_idx,
                    attr_text,
                    vertices[6 * v1] + tile.lon,
                    vertices[6 * v1 + 1] + tile.lat,
                )
                for (tri_idx, attr_text, v1) in degenerate_attr_sample
            ),
        )
    if tile.water_smoothing:
        UI.vprint(1, "   Smoothing inland water.")
        for j in range(tile.water_smoothing):
            for v1, v2, v3 in water_tris:
                zmean = (
                    vertices[6 * v1 + 2]
                    + vertices[6 * v2 + 2]
                    + vertices[6 * v3 + 2]
                ) / 3
                vertices[6 * v1 + 2] = zmean
                vertices[6 * v2 + 2] = zmean
                vertices[6 * v3 + 2] = zmean
    UI.vprint(1, "   Smoothing of sea water.")
    for v1, v2, v3 in sea_tris:
        if tile.sea_smoothing_mode == "zero":
            vertices[6 * v1 + 2] = 0
            vertices[6 * v2 + 2] = 0
            vertices[6 * v3 + 2] = 0
        elif tile.sea_smoothing_mode == "mean":
            zmean = (
                vertices[6 * v1 + 2]
                + vertices[6 * v2 + 2]
                + vertices[6 * v3 + 2]
            ) / 3
            vertices[6 * v1 + 2] = zmean
            vertices[6 * v2 + 2] = zmean
            vertices[6 * v3 + 2] = zmean
        else:
            vertices[6 * v1 + 2] = max(vertices[6 * v1 + 2], 0)
            vertices[6 * v2 + 2] = max(vertices[6 * v2 + 2], 0)
            vertices[6 * v3 + 2] = max(vertices[6 * v3 + 2], 0)
    UI.vprint(1, "   Treatment of airports, roads and patches.")
    # R18-1b: give every FREE INTERIOR vertex of an INTERP_ALT face the
    # value its face's PATCH-VALUED vertices imply, BEFORE the
    # assignment below copies column 5 into the altitude.  Scoped to the
    # triangles whose attribute is EXACTLY ``INTERP_ALT`` — the
    # vector-authored patch and road regions.  The apt.dat RUNWAY /
    # TAXIWAY / APRON / HANGAR regions (attributes 16/32/64/128, which
    # also satisfy the ``>= INTERP_ALT`` test above) are deliberately
    # left alone: their interiors ride the airport-smoothed DEM raster
    # on purpose.
    #
    # WIDENING THIS WAS TRIED AND MEASURED OUT (2026-08-12, the round's
    # last attempt).  The hypothesis was that HECA's patch faces are
    # flooded by the apt.dat APRON/TAXIWAY seeds and so were being
    # skipped.  A probe of the owner's own point reported its triangle's
    # attribute as **8** — plain INTERP_ALT, already in scope — so the
    # hypothesis is REFUTED.  Passing the whole ``>= INTERP_ALT`` set
    # instead then measured: the interpolated set was UNCHANGED (12,123
    # both ways, owner point 91.13 m and the class identical to the
    # decimal), while 49,717 vertices moved instead of 11,960, 3,771 of
    # them by more than 3 m and one by 32.19 m — the apt.dat surfaces
    # being re-derived from patch rings for no measured gain.  Widening
    # is therefore a deliberate, separately-measured act, not a default.
    if _interp_alt_only_tris:
        report = {}
        patch_valued = patch_valued_vertex_indices(tile, vertices)
        try:
            n_interpolated = interpolate_free_interior_altitudes(
                vertices, _interp_alt_only_tris, patch_valued, report=report)
        except Exception as error:
            # Never break a mesh build over a refinement: the historical
            # per-vertex copy below still runs.
            n_interpolated = 0
            UI.lvprint(
                1, "WARNING: free-interior interpolation (R18-1b) failed, "
                   "interior vertices keep the DEM:", str(error))
        if report:
            UI.vprint(
                1,
                f"   Patch/road interiors: {n_interpolated} free interior "
                f"vertex(es) of {report.get('free', 0)} took their face's "
                "interpolated altitude instead of the DEM"
                + (f"; {report['isolated']} kept their own value (no "
                   "authored vertex in their component)"
                   if report.get("isolated") else "")
                + ".")
    for v1, v2, v3 in interp_alt_tris:
        vertices[6 * v1 + 2] = vertices[6 * v1 + 5]
        vertices[6 * v2 + 2] = vertices[6 * v2 + 5]
        vertices[6 * v3 + 2] = vertices[6 * v3 + 5]
        vertices[6 * v1 + 3] = 0
        vertices[6 * v2 + 3] = 0
        vertices[6 * v3 + 3] = 0
        vertices[6 * v1 + 4] = 0
        vertices[6 * v2 + 4] = 0
        vertices[6 * v3 + 4] = 0
    UI.vprint(1, "-> Writing output nodes file.")
    f_node = open(FNAMES.output_node_file(tile), "w")
    f_node.write(init_line_f_node)
    for i in range(0, nbr_pt):
        f_node.write(
            str(i + 1)
            + " "
            + " ".join(
                ("{:.15f}".format(x) for x in vertices[6 * i : 6 * i + 6])
            )
            + "\n"
        )
    f_node.write(end_line_f_node)
    f_node.close()
    return vertices


################################################################################
def write_mesh_file(tile, vertices):
    mesh_file_name = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    UI.vprint(
        1,
        "-> Writing final mesh to the file " + mesh_file_name,
    )
    f_ele = open(FNAMES.output_ele_file(tile), "r")
    nbr_vert = len(vertices) // 6
    nbr_tri = int(f_ele.readline().split()[0])
    # Neighbor tile builds (step 2.5 masks) read this file concurrently
    # during parallel builds: write to a temporary file in the same
    # directory and atomically rename it into place so a reader can never
    # observe a half-written mesh.
    temporary_mesh_file_name = (
        mesh_file_name + ".tmp" + str(os.getpid())
    )
    f = open(temporary_mesh_file_name, "w")
    f.write("MeshVersionFormatted 2\n")
    f.write("Dimension 3\n\n")
    f.write("Vertices\n")
    f.write(str(nbr_vert) + "\n")
    for i in range(0, nbr_vert):
        f.write(
            "{:.15f}".format(vertices[6 * i] + tile.lon)
            + " "
            + "{:.15f}".format(vertices[6 * i + 1] + tile.lat)
            + " "
            + "{:.15f}".format(vertices[6 * i + 2] / 100000)
            + " 0\n"
        )
    f.write("\n")
    f.write("Normals\n")
    f.write(str(nbr_vert) + "\n")
    for i in range(0, nbr_vert):
        f.write(
            "{:.2f}".format(vertices[6 * i + 3])
            + " "
            + "{:.2f}".format(vertices[6 * i + 4])
            + " 0\n"
        )
    f.write("\n")
    f.write("Triangles\n")
    f.write(str(nbr_tri) + "\n")
    for i in range(0, nbr_tri):
        columns = f_ele.readline().split()[1:]
        if len(columns) > 3:
            # The .ele attribute column is REAL and a degenerate triangle
            # can hold a float in it (post_process_nodes_altitudes reports
            # those once, loudly); the mesh file's own column is read as an
            # int everywhere downstream -- read_mesh_file, the mask
            # builders, auto_patch's mesh_sampler -- so it is normalised
            # here rather than copied over verbatim.
            columns[3] = str(read_triangle_attribute(columns[3])[0])
        f.write(" ".join(columns) + "\n")
    f_ele.close()
    f.close()
    os.replace(temporary_mesh_file_name, mesh_file_name)
    return


################################################################################
def _auto_patch_post_mesh_rebake(tile):
    # auto_patch Phase 2: re-anchor DSF scenery objects against the mesh
    # just written (docs/dsf_object_integration_spec.md, amendment A4 —
    # the hook lives at the END of build_mesh / sort_mesh, not in their
    # callers, so the GUI's per-step Mesh button and Shift-click sort are
    # covered too).  Lazy import: the long-running GUI caches auto_patch
    # modules, so source edits need an Ortho4XP restart.  No-op unless
    # O4_DSF_OBJECT_REANCHOR=1.  Must NEVER fail the tile.
    try:
        from auto_patch import post_mesh as AUTO_PATCH_POST_MESH

        AUTO_PATCH_POST_MESH.rebake_dsf_objects(tile)
    except Exception as exception:
        UI.vprint(
            1, "auto_patch post-mesh object re-anchor failed:", exception
        )


################################################################################
def _terminate_mesh_process(process):
    """Stop a still-running external mesh child after a Stop request.

    Ask it to exit politely (``terminate()``), give it up to ~2 s, then
    force-kill.  Idempotent: a no-op for a process that has already
    exited, and never raises.
    """
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.wait(timeout=2)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=2)
        except Exception:
            pass


################################################################################
def _run_triangulation_process(mesh_cmd):
    """Launch ``mesh_cmd`` and stream its stdout, echoing each line.

    The ``O4_UI_Utils.red_flag`` cancellation flag is polled once per
    output line; when a Stop is requested mid-run the child is stopped
    (see :func:`_terminate_mesh_process`) and the now-dead process is
    returned immediately, without waiting for triangulation to finish.
    Callers detect the cancellation through ``UI.red_flag`` and report it
    via the standard interrupted path (``exit_message_and_bottom_line``).

    Returns the finished ``subprocess.Popen`` so callers can read
    ``returncode`` for the existing retry logic.  With no Stop request the
    behaviour is identical to the previous inline ``Popen`` + readline
    loop.
    """
    import select

    process = subprocess.Popen(
        mesh_cmd,
        stdout=subprocess.PIPE,
        bufsize=0,
        **UI.external_tool_keyword_arguments(),
    )
    while True:
        if UI.red_flag:
            _terminate_mesh_process(process)
            break
        # Triangle4XP goes quiet for minutes between phase lines; a bare
        # readline would sit blocked through a Stop click, so wait on
        # the pipe with a short timeout and re-poll the flag on silence.
        try:
            readable = select.select([process.stdout], [], [], 0.5)[0]
        except Exception:
            readable = [process.stdout]
        if not readable:
            continue
        line = process.stdout.readline()
        if not line:
            break
        try:
            print(line.decode("utf-8")[:-1])
        except Exception:
            pass
    return process


def _refuse_on_broken_proj() -> bool:
    """Report and abort the step when the PROJ runtime failed its self-check.

    A broken PROJ runtime silently degrades a tile (every elevation inset
    fetch fails and the build continues on base DEM only), so the step
    refuses instead — docs/specs/proj-runtime-robustness-spec.md.
    """
    reason = PROJRT.refuse_reason()
    if not reason:
        return False
    UI.lvprint(
        0,
        "ERROR: PROJ runtime is broken — builds are disabled to avoid a "
        "silently degraded tile.",
    )
    UI.lvprint(0, reason)
    UI.exit_message_and_bottom_line("")
    return True


################################################################################
def build_mesh(tile):
    if UI.is_working:
        return 0
    UI.is_working = 1
    UI.red_flag = False
    if _refuse_on_broken_proj():
        return 0
    VECT.scalx = cos((tile.lat + 0.5) * pi / 180)
    UI.logprint(
        "Step 2 for tile lat=", tile.lat, ", lon=", tile.lon, ": starting."
    )
    UI.vprint(
        0,
        "\nStep 2 : Building mesh for tile "
        + FNAMES.short_latlon(tile.lat, tile.lon)
        + " : \n--------\n",
    )
    UI.progress_bar(1, 0)
    poly_file = FNAMES.input_poly_file(tile)
    node_file = FNAMES.input_node_file(tile)
    alt_file = FNAMES.alt_file(tile)
    weight_file = FNAMES.weight_file(tile)
    if not os.path.isfile(node_file):
        UI.exit_message_and_bottom_line("\nERROR: Could not find ", node_file)
        return 0
    if not tile.iterate and not os.path.isfile(poly_file):
        UI.exit_message_and_bottom_line("\nERROR: Could not find ", poly_file)
        return 0
    if not tile.iterate:
        if not os.path.isfile(alt_file):
            UI.exit_message_and_bottom_line(
                "\nERROR: Could not find",
                alt_file,
                ". You must run Step 1 first.",
            )
            return 0
        try:
            fill_nodata = tile.fill_nodata or "to zero"
            # Re-derive the same airport-inset composite as step 1 from the
            # cache directory (disk-state-driven, idempotent) so both steps
            # agree on the elevation source. The first token stays the base,
            # so the raster dimension check below is unchanged; the baked
            # insets already live in the .alt file written in step 1.
            composite_dem = INSETS.assemble_inset_composite_source(
                tile, DEM.drop_missing_pinned_files(tile.custom_dem)
            )
            source = (
                (";" in composite_dem) and composite_dem.split(";")[0]
            ) or composite_dem
            tile.dem = DEM.DEM(
                tile.lat,
                tile.lon,
                source,
                fill_nodata,
                info_only=True,
                elevation_level=getattr(tile, "elevation_level", "auto"),
            )
            # Re-derive the same Phase C1 densification as step 1 (disk
            # state-driven), so nxdem/nydem match the .alt written densely
            # in step 1 and are handed to Triangle4XP at the finer posting.
            INSETS.densify_tile_dem_for_insets(tile)
            if (
                not os.path.getsize(alt_file)
                == 4 * tile.dem.nxdem * tile.dem.nydem
            ):
                UI.exit_message_and_bottom_line(
                    "\nERROR: Cached raster elevation does not match the ",
                    "current custom DEM specs.\n       You must run Step 1 ",
                    "and Step 2 with the same elevation base.",
                )
                return 0
        except Exception as e:
            print(e)
            UI.exit_message_and_bottom_line(
                "\nERROR: Could not determine the appropriate source. Please ",
                "check your custom_dem entry.",
            )
            return 0
    else:
        try:
            usable_dem = DEM.drop_missing_pinned_files(tile.custom_dem)
            source = (
                (";" in usable_dem)
                and usable_dem.split(";")[tile.iterate]
            ) or usable_dem
            tile.dem = DEM.DEM(
                tile.lat,
                tile.lon,
                source,
                fill_nodata=False,
                info_only=True,
                elevation_level=getattr(tile, "elevation_level", "auto"),
            )
            # Match step 1's densified posting for the raster-size check.
            INSETS.densify_tile_dem_for_insets(tile)
            if (
                not os.path.isfile(alt_file)
                or not os.path.getsize(alt_file)
                == 4 * tile.dem.nxdem * tile.dem.nydem
            ):
                tile.dem = DEM.DEM(
                    tile.lat,
                    tile.lon,
                    source,
                    fill_nodata=False,
                    info_only=False,
                    elevation_level=getattr(
                        tile, "elevation_level", "auto"
                    ),
                )
                # Iterative refinement rewrites the raster from the
                # tile.iterate-th user sub-DEM; densify to the Phase C1
                # working grid and re-bake the cached airport insets so the
                # refined raster keeps the meter-class airport terrain at
                # the finer posting (no-op when the feature is gated off --
                # and the bake guards base nodata cells, which this
                # fill_nodata=False load can contain).
                INSETS.densify_tile_dem_for_insets(tile)
                # Mirror the step-1 bake order: tile-wide elevation-level
                # overlay first (base terrain), airport insets last.
                ELEVATION_LEVEL.bake_tile_overlay_into_alt_dem(tile)
                INSETS.bake_airport_insets_into_alt_dem(tile)
                tile.dem.write_to_file(FNAMES.alt_file(tile))
        except Exception as e:
            print(e)
            UI.exit_message_and_bottom_line(
                "\nERROR: Could not determine the appropriate source. Please ",
                "check your custom_dem entry.",
            )
            return 0
    try:
        f = open(node_file, "r")
        input_nodes = int(f.readline().split()[0])
        f.close()
    except:
        UI.exit_message_and_bottom_line("\nERROR: In reading ", node_file)
        return 0

    timer = time.time()
    tri_verbosity = "Q" if UI.verbosity <= 1 else "V"
    output_poly = "P" if UI.cleaning_level else ""
    do_refine = "r" if tile.iterate else "A"
    try:
        max_tris = float(tile.limit_tris) * 1e6
    except:
        UI.vprint(1, "   Warning : limit_tris wrongly set, defaults to 5M.")
        max_tris = 5e6
    if max_tris <= 0 or max_tris >= 5e7:
        max_tris = 5e6
    max_steiner = max_tris / 1.9 - input_nodes
    max_steiner = max(max_steiner, 5e5)

    limit_tris = "S" + str(max_steiner)
    Tri_option = (
        "-pq" + "{:.9g}".format(tile.min_angle) + do_refine + 
        "uYB" + tri_verbosity + output_poly + limit_tris
    )

    weight_array = numpy.ones((1001, 1001), dtype=numpy.float32)
    build_curv_tol_weight_map(tile, weight_array)
    weight_array.tofile(weight_file)
    del weight_array

    # Hack
    # Better meshes by not modifying curv_tol but having limit_tris set
    # tu a reasonable value.
    # curv_tol_scaling = sqrt(tile.dem.nxdem / (3601 * (tile.dem.x1 - tile.dem.x0))
    # )

    mesh_cmd = [
        Triangle4XP_cmd.strip(),
        Tri_option.strip(),
        "{:.9g}".format(GEO.lon_to_m(tile.lat)),
        "{:.9g}".format(GEO.lat_to_m),
        # "{:d}", never "{:n}": the locale-aware "n" format inserts
        # grouping separators under a non-C LC_NUMERIC (e.g. in-process
        # Qt GUI builds, where QApplication calls setlocale(LC_ALL, ""))
        # and Triangle4XP's atoi("7,345") reads 7 — the mesh then samples
        # a 7x7 phantom DEM and the whole tile flattens.
        "{:d}".format(tile.dem.nxdem),
        "{:d}".format(tile.dem.nydem),
        "{:.9g}".format(tile.dem.x0),
        "{:.9g}".format(tile.dem.y0),
        "{:.9g}".format(tile.dem.x1),
        "{:.9g}".format(tile.dem.y1),
        "{:.9g}".format(tile.dem.nodata),
        "{:.9g}".format(tile.curvature_tol),
        alt_file,
        weight_file,
        poly_file,
    ]

    del tile.dem  # for machines with not much RAM, we do not need it anymore
    tile.dem = None
    UI.vprint(1, "-> Start of the mesh algorithm Triangle4XP.")
    UI.vprint(2, "   Mesh command:", " ".join(mesh_cmd))
    fingers_crossed = _run_triangulation_process(mesh_cmd)
    # A Stop click during triangulation terminates the child with a
    # non-zero returncode; report cancellation here so it does not look
    # like a quality failure and (re)start the lower-angle retry loop.
    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    time.sleep(0.3)
    fingers_crossed.poll()
    if fingers_crossed.returncode:
        min_angles = [8, 6, 4, 2, 0]
        for min_angle in min_angles:
            if tile.min_angle <= min_angle:
                continue
            UI.vprint(
                0,
                "\nWARNING: Triangle4XP could not achieve the requested quality ",
                "(min_angle) most likely due to an uncatched OSM error.\n",
                f"Reattempting with a lower angle constraint (min_angle={min_angle}).",
            )
            Tri_option = (
                "-pq"
                + "{:.9g}".format(min_angle)
                + do_refine
                + "uYB"
                + tri_verbosity
                + output_poly
                + limit_tris
            )
            mesh_cmd[1] = Tri_option
            fingers_crossed = _run_triangulation_process(mesh_cmd)
            # Do not launch a further retry attempt once cancelled.
            if UI.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
            time.sleep(0.3)
            fingers_crossed.poll()
            if fingers_crossed.returncode == 0:
                break
        else:
            UI.exit_message_and_bottom_line(
                "\nERROR: Triangle4XP really couldn't make it !\n\n",
                "If the reason is not due to the limited amount of ",
                "RAM please\n",
                "file a bug including the .node and .poly files that you\n",
                "will find in ",
                str(tile.build_dir),
                ".\n",
            )
            return 0

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    vertices = post_process_nodes_altitudes(tile)

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    write_mesh_file(tile, vertices)
    #
    if UI.cleaning_level:
        try:
            os.remove(FNAMES.weight_file(tile))
        except:
            pass
        try:
            os.remove(FNAMES.output_node_file(tile))
        except:
            pass
        try:
            os.remove(FNAMES.output_ele_file(tile))
        except:
            pass
    if UI.cleaning_level > 2:
        try:
            os.remove(FNAMES.alt_file(tile))
        except:
            pass
        try:
            os.remove(FNAMES.input_node_file(tile))
        except:
            pass
        try:
            os.remove(FNAMES.input_poly_file(tile))
        except:
            pass

    _auto_patch_post_mesh_rebake(tile)

    UI.timings_and_bottom_line(timer)
    UI.logprint(
        "Step 2 for tile lat=", tile.lat, ", lon=", tile.lon, ": normal exit."
    )
    return 1


################################################################################
def sort_mesh(tile):
    if UI.is_working:
        return 0
    UI.is_working = 1
    UI.red_flag = False
    if _refuse_on_broken_proj():
        return 0
    mesh_file = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    if not os.path.isfile(mesh_file):
        UI.exit_message_and_bottom_line("\nERROR: Could not find ", mesh_file)
        return 0
    if not os.path.isfile(sort_mesh_cmd.strip()):
        UI.exit_message_and_bottom_line(
            "\nERROR: moulinette is not bundled in this build (upstream binary"
            " has no license terms); mesh re-sort skipped."
        )
        return 0
    sort_mesh_cmd_list = [
        sort_mesh_cmd.strip(),
        str(tile.default_zl),
        mesh_file,
    ]
    UI.vprint(1, "-> Reorganizing mesh triangles.")
    timer = time.time()
    moulinette = _run_triangulation_process(sort_mesh_cmd_list)
    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    _auto_patch_post_mesh_rebake(tile)
    UI.timings_and_bottom_line(timer)
    UI.logprint(
        "Moulinette applied for tile lat=",
        tile.lat,
        ", lon=",
        tile.lon,
        " and ZL",
        tile.default_zl,
    )
    return 1


################################################################################
def triangulate(name, path_to_Ortho4XP_dir):
    Tri_option = " -pAYPQ "
    mesh_cmd = [
        os.path.join(path_to_Ortho4XP_dir, triangle_cmd).strip(),
        Tri_option.strip(),
        name + ".poly",
    ]
    fingers_crossed = subprocess.Popen(
        mesh_cmd, stdout=subprocess.PIPE, bufsize=0, **UI.external_tool_keyword_arguments()
    )
    while True:
        line = fingers_crossed.stdout.readline()
        if not line:
            break
        else:
            print(line.decode("utf-8")[:-1])
    fingers_crossed.poll()
    if fingers_crossed.returncode:
        print("\nERROR: triangle crashed, check osm mask data.\n")
        return 0
    return 1


##############################################################################
def read_mesh_file(mesh_file):
    
    f = open(mesh_file,"r")
    mesh_version = float(f.readline().strip().split()[-1])
    
    # skip 3 lines 
    for i in range(3):
        f.readline()
    
    nbr_nodes = int(f.readline())
    node_coords = numpy.zeros(5 * nbr_nodes)
    
    # read positions
    for i in range(nbr_nodes):
        node_coords[5 * i : 5 * i + 3] = [
            float(x) for x in f.readline().split()[:3]
        ]
    # altitutes are encoded in .mesh files with a 100000 scaling factor
    node_coords[2::5] *= 100000
    
    # skip 3 lines
    for i in range(3):
        f.readline()
    
    # read normals
    for i in range(nbr_nodes):
        node_coords[5 * i + 3 : 5 * i + 5] = [
            float(x) for x in f.readline().split()[:2]
        ]
    
    # skip 2 lines
    for i in range(0, 2): 
        f.readline()

    # read nbr of tris
    nbr_tris = int(f.readline())      

    tri_idx  = numpy.zeros(3 * nbr_tris, dtype = numpy.uint32)
    tri_types = numpy.zeros(nbr_tris, dtype = numpy.uint32)
    for i in range(nbr_tris):
        columns = f.readline().split()
        (n1, n2, n3) = [int(x) - 1 for x in columns[:3]]
        # the attribute column is REAL in the .ele this was copied from
        tri_idx[3 * i: 3 * i + 3] = (n1, n2, n3)
        tri_types[i] = read_triangle_attribute(columns[3])[0]
    f.close()

    return (mesh_version, nbr_nodes, node_coords, nbr_tris, tri_idx, tri_types)
##############################################################################
