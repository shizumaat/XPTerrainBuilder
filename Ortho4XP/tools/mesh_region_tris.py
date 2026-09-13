"""Count Triangle4XP mesh triangles overall and inside an airport region.

X-Plane load/render cost scales with the TILE MESH triangle count produced
by Triangle4XP — NOT with the patch's node count (the airport mesh is
AREA-refined, so it has far more triangles than the patch has vertices).
This tool reads a built Ortho4XP ``.mesh`` (MEDIT format) and reports the
total triangle count plus how many fall in the airport's bounding box —
the patch's real triangle footprint, the number to optimize against.

Pair each measurement with a measured X-Plane load time to find the
triangle↔load-time curve and the right density compromises.

Usage:
    # bbox from an emitted patch OSM (single- or double-quoted):
    venv/bin/python tools/mesh_region_tris.py \
        --mesh "/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+30+031/Data+30+031.mesh" \
        --patch-osm /tmp/HECA_auto.patch.osm

    # or an explicit bbox lat0,lat1,lon0,lon1:
    venv/bin/python tools/mesh_region_tris.py --mesh <file> --bbox 30.08,30.15,31.37,31.46
"""
from __future__ import annotations

import argparse
import array
import math
import re
import time

R_EARTH_M = 6_378_137.0


_EQUI_NORM = 2.0 * 3.0 ** 0.5   # normalises an EQUILATERAL to exactly 1.0


def texel_m(lat_deg: float, zl: int = 16) -> float:
    """ZL ground resolution in metres at a latitude (web Mercator).

    ``2*pi*R*cos(lat) / (256 * 2**zl)`` — 2.3887 m at the equator for
    ZL16, 2.0662 m at HECA's 30.118 deg.  A triangle smaller than one
    texel cannot be resolved by the orthophoto at all, so it is the
    honest floor to measure "invisible geometry" against.
    """
    return (2.0 * math.pi * R_EARTH_M * math.cos(math.radians(lat_deg))
            / (256.0 * 2 ** zl))


def parse_area_bands(spec: str) -> list[float]:
    """Ascending metre-squared band edges, or a SystemExit."""
    try:
        edges = [float(x) for x in spec.split(",") if x.strip()]
    except ValueError:
        raise SystemExit(f"REFUSING: --area-bands {spec!r} is not a list "
                         f"of numbers")
    if not edges:
        raise SystemExit("REFUSING: --area-bands needs at least one edge")
    if any(b <= a for a, b in zip(edges, edges[1:])):
        raise SystemExit(f"REFUSING: --area-bands must ASCEND, got {edges}")
    if edges[0] <= 0:
        raise SystemExit("REFUSING: --area-bands edges must be positive")
    return edges


def band_index(area_m2: float, edges: list[float]) -> int:
    """Which band an area falls in — ``len(edges)`` is the top band."""
    for i, e in enumerate(edges):
        if area_m2 < e:
            return i
    return len(edges)


def band_labels(edges: list[float], texel_area: float | None) -> list[str]:
    """Human labels for ``len(edges) + 1`` bands, texel-aware."""
    def _fmt(v: float) -> str:
        if texel_area is not None and abs(v - texel_area) < 1e-9:
            return "1 texel^2"
        return f"{v:g} m^2"
    out = [f"< {_fmt(edges[0])}"]
    out += [f"{_fmt(a)} - {_fmt(b)}" for a, b in zip(edges, edges[1:])]
    out += [f">= {_fmt(edges[-1])}"]
    return out


# ── THE INTERP_ALT AUDIT (CYXY round, 2026-08-28) ─────────────────────
#
# "The mesh contradicts its own .alt by 60 m over 50 x 39 km" has THREE
# candidate owners and they are answered in three different artifacts.
# Reading only one of them is how the +60-136 defect was first attributed
# to a Triangle4XP plague leak that measurement then refuted:
#
#   1. THE SEAL (input .poly).  Triangle4XP's regionplague crosses any
#      segment whose mark shares no bit with the flood's attribute, so an
#      INTERP_ALT seed is contained exactly when it sits in a BOUNDED
#      face of the arrangement of the INTERP_ALT-marked edges.  An
#      unsealed seed floods the whole uncut land component — the VMMC
#      class.
#   2. THE PLAGUE (built .mesh vs that arrangement).  Every attr-8
#      triangle must land inside the same envelope; one that does not
#      means a marked edge did not survive the CDT.
#   3. THE DOMAIN (built .mesh vs the PATCH COVERAGE).  R18-1b harmonic-
#      extends the patch ring altitudes over the CONNECTED attr==8
#      sub-mesh, and ``include_roads`` marks the banked road network with
#      the same bit — so wherever a levelled road touches the patch the
#      domain is the road network, not the patch.  THAT is what +60-136
#      had: seal clean, plague clean, domain 10.2 km wide against a
#      1.94 km^2 patch coverage.
#
# All three read the same MEDIT parse this tool already owns, so they
# live here rather than in a fourth mesh reader (tool discipline,
# RULINGS 7e90032).
PATCH_RING_MARKER = 15          # INTERP_ALT|WATER|SEA|SEA_EQUIV
INTERP_ALT_BIT = 8


def read_poly_inputs(prefix):
    """``(nodes, segments, seeds)`` of a Triangle input pair.

    ``nodes`` maps the 1-based id to its tile-relative ``(x, y)``;
    ``segments`` is a list of ``(id0, id1, marker)``; ``seeds`` a list of
    ``(x, y, attribute)``.  Exactly the reading
    ``O4_Mesh_Utils.patch_valued_vertex_indices`` and
    ``patch_coverage_polygon`` do, so the audit and the engine cannot
    drift on the file format.
    """
    nodes = {}
    with open(prefix + ".node") as handle:
        count = int(handle.readline().split()[0])
        for _ in range(count):
            columns = handle.readline().split()
            nodes[int(columns[0])] = (float(columns[1]), float(columns[2]))
    segments, seeds = [], []
    with open(prefix + ".poly") as handle:
        line = handle.readline()
        while line.strip() == "" or line.startswith("0 2"):
            line = handle.readline()
        for _ in range(int(line.split()[0])):
            columns = handle.readline().split()
            segments.append((int(columns[1]), int(columns[2]),
                             int(columns[3])))
        line = handle.readline()
        while line.strip() == "":
            line = handle.readline()
        for _ in range(int(line.split()[0])):      # holes
            handle.readline()
        line = handle.readline()
        while line.strip() == "":
            line = handle.readline()
        for _ in range(int(line.split()[0])):
            columns = handle.readline().split()
            seeds.append((float(columns[1]), float(columns[2]),
                          int(columns[3])))
    return (nodes, segments, seeds)


def _arrangement(nodes, segments, keep):
    """``(faces, envelope)`` of the segments whose marker passes ``keep``."""
    from shapely import geometry, ops

    lines = [geometry.LineString([nodes[a], nodes[b]])
             for (a, b, m) in segments if keep(m)]
    if not lines:
        return ([], geometry.Polygon())
    faces = list(ops.polygonize(ops.unary_union(lines)))
    return (faces, ops.unary_union(faces) if faces else geometry.Polygon())


def _read_mesh_attributed(path):
    """``(nv, lon, lat, z_m, triangles, attributes)`` from a MEDIT mesh."""
    lon, lat, zed = array.array("d"), array.array("d"), array.array("d")
    tri, att = array.array("i"), array.array("i")
    with open(path) as handle:
        line = handle.readline()
        while line and not line.startswith("Vertices"):
            line = handle.readline()
        nv = int(handle.readline())
        for _ in range(nv):
            p = handle.readline().split()
            lon.append(float(p[0])); lat.append(float(p[1]))
            zed.append(float(p[2]) * 100000.0)
        while line and not line.startswith("Triangles"):
            line = handle.readline()
        nt = int(handle.readline())
        for _ in range(nt):
            p = handle.readline().split()
            tri.append(int(p[0]) - 1); tri.append(int(p[1]) - 1)
            tri.append(int(p[2]) - 1)
            att.append(int(float(p[3])))
    return (nv, lon, lat, zed, tri, att)


def interp_alt_audit(mesh_path, prefix, tile_lat, tile_lon):
    """Print the seal / plague / domain audit; return its payload dict."""
    import collections
    from shapely import geometry
    from shapely.prepared import prep

    (nodes, segments, seeds) = read_poly_inputs(prefix)
    markers = collections.Counter(m for (_, _, m) in segments)
    seed_attrs = collections.Counter(s[2] for s in seeds)
    print(f"input: {len(nodes):,} nodes, {len(segments):,} segments, "
          f"{len(seeds):,} seeds")
    print(f"  segment markers: {dict(sorted(markers.items()))}")
    print(f"  seed attributes: {dict(sorted(seed_attrs.items()))}")

    m_lat = math.pi * R_EARTH_M / 180.0
    m_lon = m_lat * math.cos(math.radians(tile_lat + 0.5))
    deg2_to_km2 = m_lat * m_lon / 1e6

    # 1. THE SEAL
    (faces, envelope) = _arrangement(
        nodes, segments, lambda m: m & INTERP_ALT_BIT)
    sealed = prep(envelope) if not envelope.is_empty else None
    interp_seeds = [s for s in seeds if s[2] == INTERP_ALT_BIT]
    unsealed = [s for s in interp_seeds
                if sealed is None
                or not sealed.contains(geometry.Point(s[0], s[1]))]
    print(f"SEAL: {len(faces):,} bounded face(s) of the INTERP_ALT "
          f"arrangement, {envelope.area * deg2_to_km2:.3f} km^2; "
          f"{len(unsealed)} of {len(interp_seeds)} INTERP_ALT seed(s) "
          f"UNSEALED")
    for seed in unsealed[:5]:
        print(f"   UNSEALED seed ({seed[0] + tile_lon:.7f}, "
              f"{seed[1] + tile_lat:.7f})")

    # 2. THE PLAGUE
    (nv, vlon, vlat, vz, tri, att) = _read_mesh_attributed(mesh_path)
    nt = len(att)
    population = dict(sorted(collections.Counter(att).items()))
    print(f"mesh: {nv:,} vertices, {nt:,} triangles; attr population "
          f"{population}")
    escaped = []
    marked = [i for i in range(nt) if att[i] & INTERP_ALT_BIT]
    for i in marked:
        a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
        x = (vlon[a] + vlon[b] + vlon[c]) / 3.0 - tile_lon
        y = (vlat[a] + vlat[b] + vlat[c]) / 3.0 - tile_lat
        if sealed is None or not sealed.contains(geometry.Point(x, y)):
            escaped.append(i)
    print(f"PLAGUE: {len(marked):,} bit-{INTERP_ALT_BIT} triangle(s), "
          f"{len(escaped):,} OUTSIDE the arrangement envelope "
          f"(a mark that did not survive the CDT)")

    # 3. THE DOMAIN
    (_, coverage) = _arrangement(
        nodes, segments, lambda m: m == PATCH_RING_MARKER)
    covered = prep(coverage) if not coverage.is_empty else None
    patch_valued = set()
    for (a, b, m) in segments:
        if m == PATCH_RING_MARKER:
            patch_valued.add(a - 1)
            patch_valued.add(b - 1)
    only = [i for i in range(nt) if att[i] == INTERP_ALT_BIT]

    # THE EXACT FRAME.  ``snap_to_grid(9)`` and ``write_node_file``'s
    # ``{:.9f}`` make every INPUT vertex a 9-decimal tile-relative value,
    # and the rings are built from those same values — so a vertex ON a
    # ring is exactly on it.  The .mesh stores ABSOLUTE lon/lat, and
    # ``absolute - tile_origin`` does not return exactly to the 9-decimal
    # value: at +60-136 that alone moved 2,000 on-ring vertices to the
    # outside.  Input vertices are therefore read from the .node file;
    # only the mesher's own Steiner points go through the mesh frame,
    # which is why this count can differ from the ENGINE's own
    # "Patch coverage: N of M" log line by a few tenths of a percent
    # (16,527 here against 16,594 there at +60-136).  THE ENGINE'S LINE
    # IS THE AUTHORITY for the scoped domain size; this one is the
    # instrument's estimate of the same thing and is labelled as such.
    def relative(v):
        if v + 1 in nodes and v < len(nodes):
            return nodes[v + 1]
        return (vlon[v] - tile_lon, vlat[v] - tile_lat)

    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent.setdefault(x, x); parent.setdefault(y, y)
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    straddling = 0
    for i in only:
        a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
        union(a, b); union(b, c)
        if covered is not None and not all(
                covered.covers(geometry.Point(*relative(v)))
                for v in (a, b, c)):
            straddling += 1
    components = collections.defaultdict(list)
    for v in parent:
        components[find(v)].append(v)
    rows = []
    for members in components.values():
        anchored = sum(1 for v in members if v in patch_valued)
        los = [vlon[v] for v in members]
        las = [vlat[v] for v in members]
        span = max((max(los) - min(los)) * m_lon,
                   (max(las) - min(las)) * m_lat) / 1000.0
        rows.append((len(members), anchored, span,
                     min(los), max(los), min(las), max(las)))
    rows.sort(reverse=True)
    reached = sum(r[0] - r[1] for r in rows if r[1] > 0)
    isolated = sum(r[0] for r in rows if r[1] == 0)
    print(f"DOMAIN: patch coverage {coverage.area * deg2_to_km2:.3f} km^2, "
          f"{len(patch_valued):,} patch-valued vertex(es); attr=="
          f"{INTERP_ALT_BIT} sub-mesh {len(parent):,} vertex(es) in "
          f"{len(rows)} component(s); {straddling:,} of {len(only):,} "
          f"triangle(s) NOT wholly inside the coverage")
    print(f"  {'vertices':>9} {'patch-valued':>13} {'span km':>8}   bbox")
    for r in rows[:6]:
        print(f"  {r[0]:>9,} {r[1]:>13,} {r[2]:>8.1f}   "
              f"lon {r[3]:.4f}..{r[4]:.4f} lat {r[5]:.4f}..{r[6]:.4f}")
    print(f"  free vertices REACHING a patch-valued vertex (the UNSCOPED "
          f"R18-1b domain would move these): {reached:,}; reaching none: "
          f"{isolated:,}")
    # The same count under R18-1c, whose domain is the coverage — the
    # red/green pair in one read, and it reproduces the engine's own
    # "N free interior vertex(es) of M" line on both sides.
    scoped_parent = {}
    scoped_only = []
    if covered is not None:
        inside_vertex = {}
        for i in only:
            a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
            for v in (a, b, c):
                if v not in inside_vertex:
                    inside_vertex[v] = covered.covers(
                        geometry.Point(*relative(v)))
            if inside_vertex[a] and inside_vertex[b] and inside_vertex[c]:
                scoped_only.append(i)
        parent = scoped_parent
        for i in scoped_only:
            a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
            union(a, b); union(b, c)
    scoped_components = collections.defaultdict(list)
    for v in scoped_parent:
        scoped_components[find(v)].append(v)
    scoped_reached = 0
    scoped_isolated = 0
    scoped_span = 0.0
    for members in scoped_components.values():
        anchored = sum(1 for v in members if v in patch_valued)
        if anchored:
            scoped_reached += len(members) - anchored
        else:
            scoped_isolated += len(members)
        los = [vlon[v] for v in members]
        las = [vlat[v] for v in members]
        scoped_span = max(scoped_span,
                          max((max(los) - min(los)) * m_lon,
                              (max(las) - min(las)) * m_lat) / 1000.0)
    print(f"  under R18-1c (domain = the coverage): {len(scoped_only):,} "
          f"triangle(s), {scoped_reached:,} free vertex(es) reach a "
          f"patch-valued one, {scoped_isolated:,} reach none; widest "
          f"component {scoped_span:.1f} km")
    print("  (the scoped counts are this instrument's ESTIMATE — the "
          "mesh file stores absolute lon/lat and cannot place an on-ring "
          "Steiner point exactly; the ENGINE's own \"Patch coverage: N of "
          "M\" line is the authority, and the two agree to a few tenths "
          "of a percent)")
    return {
        "segment_markers": {str(k): v for k, v in markers.items()},
        "seed_attributes": {str(k): v for k, v in seed_attrs.items()},
        "seal_faces": len(faces),
        "seal_envelope_km2": envelope.area * deg2_to_km2,
        "seeds_interp_alt": len(interp_seeds),
        "seeds_unsealed": len(unsealed),
        "mesh_attr_population": {str(k): v for k, v in population.items()},
        "bit8_triangles": len(marked),
        "bit8_triangles_outside_envelope": len(escaped),
        "patch_coverage_km2": coverage.area * deg2_to_km2,
        "patch_valued_vertices": len(patch_valued),
        "domain_components": len(rows),
        "domain_largest_span_km": rows[0][2] if rows else 0.0,
        "domain_triangles_straddling_coverage": straddling,
        "domain_free_reaching": reached,
        "domain_free_isolated": isolated,
        "scoped_triangles": len(scoped_only),
        "scoped_free_reaching": scoped_reached,
        "scoped_free_isolated": scoped_isolated,
        "scoped_widest_component_km": scoped_span,
    }


#: The water bits of ``O4_Vector_Utils.Vector_Map.dico_attributes``
#: The two bits the SEA / inland split reads (``O4_Vector_Map`` values).
WATER_BIT = 1
SEA_BIT = 2
#: (WATER 1 | SEA 2 | SEA_EQUIV 4).  Spelled here so the tool reads a
#: mesh with no engine import; ``tests/test_mesh_water_audit.py``
#: twin-asserts it against the engine's own table.
WATER_BITS = 7


def water_audit(mesh_path, step_flag_m=1.0, zero_tol_m=1e-3, near=None):
    """IS THE WATER FLAT, AND AT ITS DATUM? (owner RULINGS 2026-09-09m;
    mechanism 09o).

    The acceptance read for the water round, over the built mesh's WATER
    triangles (any of :data:`WATER_BITS`):

    * every water VERTEX's z — how many stand at 0.000 and how many do
      not, with the commonest non-zero values named (at OTHH on 1.0.297
      they were 699 at 0.000 and 782 at exactly 3.962, interleaved along
      the canal at 0.9 m: the flat-site plateau);
    * every water TRIANGLE's z-STEP (max − min over its three corners) —
      how many exceed ``step_flag_m`` (1,692 of 2,197 on 1.0.297): a
      one-triangle-wide step in open water is the sawtooth the owner saw;
    * the same two, restricted to ``near = (lat, lon, radius_m)`` when
      given — the owner's site.

    Attributes are reported as a histogram beside the counts, because
    ``SEA|INTERP_ALT`` (10) versus bare ``SEA`` (2) is the whole
    attribution: 10 means an INTERP_ALT seed reached that water.

    Returns the payload dict; prints it.
    """
    import collections

    (nv, lon, lat, zed, tri, att) = _read_mesh_attributed(mesh_path)
    nt = len(att)
    wet_tris = [i for i in range(nt) if att[i] & WATER_BITS]
    payload = {"triangles_tile": nt, "water_triangles": len(wet_tris),
               "step_flag_m": step_flag_m, "zero_tol_m": zero_tol_m}
    print(f"water audit — mesh {mesh_path}")
    print(f"  triangles {nt}, water (attr & {WATER_BITS}) {len(wet_tris)}")
    if not wet_tris:
        print("  no water triangles in this mesh")
        return payload
    attrs = collections.Counter(att[i] for i in wet_tris)
    payload["water_attributes"] = {str(k): v for k, v in attrs.most_common()}
    print("  attributes: " + ", ".join(f"{k}x{v}" for k, v in attrs.most_common()))

    def _report(label, idx, split=True):
        # THE SEA IS LEVELLED, INLAND WATER IS NOT (owner RULINGS
        # 2026-09-09o (3) / 09z (3)): ``sea_smoothing_mode=zero`` drives a
        # SEA-without-WATER triangle to 0.000, while a mapped inland body
        # (WATER, SEA_EQUIV) converges to ITS OWN level.  Lumping them
        # makes "how many water vertices are off zero" unreadable — every
        # lake is off zero lawfully — so the SEA class is reported on its
        # own line.  That count is the round's acceptance figure.
        if split:
            sea_only = [i for i in idx
                        if (att[i] & SEA_BIT) and not (att[i] & WATER_BIT)]
            inland = [i for i in idx if i not in set(sea_only)]
            if sea_only and inland:
                out = _report(label, idx, split=False)
                out["sea"] = _report(label + " SEA (levelled)", sea_only,
                                     split=False)
                out["inland"] = _report(label + " inland/equiv", inland,
                                        split=False)
                return out
        verts = set()
        steps = []
        for i in idx:
            a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
            verts.update((a, b, c))
            zs = (zed[a], zed[b], zed[c])
            steps.append(max(zs) - min(zs))
        zs = [zed[v] for v in sorted(verts)]
        at_zero = sum(1 for z in zs if abs(z) <= zero_tol_m)
        non_zero = collections.Counter(round(z, 3) for z in zs
                                       if abs(z) > zero_tol_m)
        stepped = sum(1 for s in steps if s > step_flag_m)
        out = {"triangles": len(idx), "vertices": len(zs),
               "vertices_at_zero": at_zero,
               "vertices_not_zero": len(zs) - at_zero,
               "vertices_not_zero_top": [[v, n] for v, n in
                                         non_zero.most_common(5)],
               "triangles_stepped": stepped,
               "max_step_m": round(max(steps), 3) if steps else 0.0}
        print(f"  [{label}] {len(idx)} triangle(s), {len(zs)} vertex(es): "
              f"{at_zero} at 0.000, {len(zs) - at_zero} NOT"
              + (" (" + ", ".join(f"{v:.3f}x{n}" for v, n in
                                  non_zero.most_common(5)) + ")"
                 if non_zero else ""))
        print(f"  [{label}] z-step > {step_flag_m:g} m: {stepped} triangle(s); "
              f"max step {out['max_step_m']:.3f} m")
        return out

    payload["frame"] = _report("frame", wet_tris)
    if near:
        (nlat, nlon, radius_m) = near
        m_lat = math.pi * R_EARTH_M / 180.0
        m_lon = m_lat * math.cos(math.radians(nlat))
        sel = []
        for i in wet_tris:
            a, b, c = tri[3 * i], tri[3 * i + 1], tri[3 * i + 2]
            cx = (lon[a] + lon[b] + lon[c]) / 3.0
            cy = (lat[a] + lat[b] + lat[c]) / 3.0
            if math.hypot((cx - nlon) * m_lon, (cy - nlat) * m_lat) <= radius_m:
                sel.append(i)
        payload["near"] = {"lat": nlat, "lon": nlon, "radius_m": radius_m}
        payload["near"].update(_report(f"within {radius_m:g} m of "
                                       f"{nlat:.4f},{nlon:.4f}", sel)
                               if sel else {"triangles": 0})
    return payload


# ── THE EDGE AUDIT (owner RULINGS 2026-09-10g) ────────────────────────
#
# "Latest build of CYXY probably has overlapping nodes at different
# elevations causing texture tearing" — the owner, on the plateau slope
# below the 32L end, the first build carrying the terrain edge (spec
# §19).  The lane's own round-1 bar was ONE TRANSECT, and a transect
# cannot see a fold beside it: this is that bar as an AREA read over
# every triangle in a radius, in the three classes the tearing can come
# from.
#
#   (a) OVERLAPPING NODES — two mesh vertices closer in PLAN than
#       ``identity.min_distinct_spacing_m`` but more than ``--overlap-dz``
#       apart in z.  Two nodes at one plan position with different
#       heights is the sim's texture tear, exactly as the owner named it.
#   (b) WALLS — a triangle whose own plan slope exceeds ``--wall-slope``
#       where the DEM's slope over the SAME footprint is gentler by more
#       than ``--dem-slope-factor``.  A cliff the terrain itself has is
#       not a defect; a cliff only the patch has is.
#   (c) THE GROUND PAST THE EDGE — every vertex of a triangle the patch
#       did NOT value (no INTERP_ALT bit) must stand within ``--dem-bar``
#       of the DEM the mesher was handed (the tile's own ``.alt``): §19
#       (3), "beyond the edge: nothing — the DEM's own slope IS the bank".
#
# The instrument is proved on the CONTROL mesh, which must read ZERO
# overlapping pairs: a class the audit reports on both arms is the
# audit's own artefact, not the change's.
def _alt_reader(alt_path, tile_lat, tile_lon):
    """The tile's own ``.alt`` raster, read exactly as Triangle4XP read
    it — the SINGLE implementation in ``mesh_elevation_sampler.AltRaster``
    (bilinear, extent [-0.01, 1.01]^2), never a second one here."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from mesh_elevation_sampler import AltRaster
    return AltRaster(alt_path, tile_lat, tile_lon)


def _tri_plane_slope(x, y, z):
    """|grad z| of the plane through three (x, y, z) points, in metres
    per metre; ``inf`` for a degenerate footprint."""
    (x0, x1, x2), (y0, y1, y2), (z0, z1, z2) = x, y, z
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(det) < 1.0e-12:
        return float("inf") if max(z) - min(z) > 1.0e-9 else 0.0
    dzdx = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / det
    dzdy = ((z2 - z0) * (x1 - x0) - (z1 - z0) * (x2 - x0)) / det
    return math.hypot(dzdx, dzdy)


def _kml_edge_audit(path, site, walls, pairs, tris_lonlat, cap=2000):
    """The offending triangles as one KML the owner can open beside the
    sim: a red polygon per WALL, a yellow pin per OVERLAPPING PAIR."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
           '<name>terrain-edge mesh audit</name>',
           '<Style id="wall"><LineStyle><color>ff0000ff</color>'
           '<width>2</width></LineStyle>'
           '<PolyStyle><color>7d0000ff</color></PolyStyle></Style>',
           '<Style id="pair"><IconStyle><color>ff00ffff</color>'
           '</IconStyle></Style>']
    if site:
        out.append(f'<Placemark><name>site</name><Point><coordinates>'
                   f'{site[1]:.9f},{site[0]:.9f},0</coordinates></Point>'
                   f'</Placemark>')
    for (idx, slope, dem_slope) in walls[:cap]:
        ring = tris_lonlat[idx]
        coords = " ".join(f"{lo:.9f},{la:.9f},{zz:.3f}"
                          for (lo, la, zz) in ring + ring[:1])
        out.append(f'<Placemark><name>wall {idx} slope {slope:.2f} '
                   f'(DEM {dem_slope:.2f})</name><styleUrl>#wall</styleUrl>'
                   f'<Polygon><altitudeMode>absolute</altitudeMode>'
                   f'<outerBoundaryIs><LinearRing><coordinates>{coords}'
                   f'</coordinates></LinearRing></outerBoundaryIs>'
                   f'</Polygon></Placemark>')
    for (la, lo, za, zb, dist) in pairs:
        out.append(f'<Placemark><name>overlap dz {abs(za - zb):.2f} m at '
                   f'{dist:.2f} m</name><styleUrl>#pair</styleUrl>'
                   f'<Point><coordinates>{lo:.9f},{la:.9f},0</coordinates>'
                   f'</Point></Placemark>')
    out.append("</Document></kml>")
    with open(path, "w") as handle:
        handle.write("\n".join(out))


def edge_audit(mesh_path, near, alt_path=None, tile=None,
               spacing_m=0.5, dz_m=0.5, wall_slope=1.0,
               dem_slope_factor=2.0, dem_bar_m=1.0, kml_path=None,
               kml_cap=2000):
    """THE AREA READ of a terrain edge (module note above).  ``near`` is
    ``(lat, lon, radius_m)``; returns the payload dict and prints it."""
    import collections

    (nlat, nlon, radius_m) = near
    (nv, lon, lat, zed, tri, att) = _read_mesh_attributed(mesh_path)
    nt = len(att)
    m_lat = 111_120.0
    m_lon = m_lat * math.cos(math.radians(nlat))

    def _xy(i):
        return ((lon[i] - nlon) * m_lon, (lat[i] - nlat) * m_lat)

    inside = [False] * nv
    for i in range(nv):
        (dx, dy) = _xy(i)
        if abs(dx) <= radius_m and abs(dy) <= radius_m:
            inside[i] = math.hypot(dx, dy) <= radius_m
    sel = [k for k in range(nt)
           if inside[tri[3 * k]] or inside[tri[3 * k + 1]]
           or inside[tri[3 * k + 2]]]
    payload = {"mesh": mesh_path, "site": [nlat, nlon], "radius_m": radius_m,
               "triangles_tile": nt, "triangles_near": len(sel),
               "spacing_m": spacing_m, "dz_m": dz_m,
               "wall_slope": wall_slope, "dem_slope_factor": dem_slope_factor,
               "dem_bar_m": dem_bar_m}
    print(f"edge audit — mesh {mesh_path}")
    print(f"  site {nlat:.6f},{nlon:.6f} r={radius_m:g} m: "
          f"{len(sel):,} of {nt:,} triangle(s)")
    if not sel:
        print("  no triangles near the site")
        return payload

    used = sorted({tri[3 * k + j] for k in sel for j in range(3)})
    payload["vertices_near"] = len(used)

    # (a) OVERLAPPING NODES, by a plan-grid bucket of the spacing
    buckets = collections.defaultdict(list)
    for i in used:
        (dx, dy) = _xy(i)
        buckets[(int(math.floor(dx / spacing_m)),
                 int(math.floor(dy / spacing_m)))].append((i, dx, dy))
    pairs = []
    for (bx, by), items in buckets.items():
        near_items = list(items)
        for ox in (0, 1):
            for oy in (-1, 0, 1):
                if (ox, oy) == (0, 0) or (ox == 0 and oy < 0):
                    continue
                near_items.extend(buckets.get((bx + ox, by + oy), ()))
        for a in range(len(items)):
            (ia, ax, ay) = items[a]
            for b in range(len(near_items)):
                (ib, bx2, by2) = near_items[b]
                if ib <= ia:
                    continue
                dist = math.hypot(ax - bx2, ay - by2)
                if dist < spacing_m and abs(zed[ia] - zed[ib]) > dz_m:
                    pairs.append((lat[ia], lon[ia], zed[ia], zed[ib], dist))
    pairs.sort(key=lambda p: -abs(p[2] - p[3]))
    payload["overlapping_pairs"] = len(pairs)
    payload["overlapping_worst_dz_m"] = (
        round(abs(pairs[0][2] - pairs[0][3]), 3) if pairs else 0.0)
    print(f"  (a) OVERLAPPING NODES (< {spacing_m:g} m apart in plan, "
          f"> {dz_m:g} m apart in z): {len(pairs)}"
          + (f", worst dz {abs(pairs[0][2] - pairs[0][3]):.2f} m at "
             f"{pairs[0][0]:.6f},{pairs[0][1]:.6f}" if pairs else ""))

    # (b) WALLS, against the DEM's own slope over the same footprint
    alt = None
    if alt_path:
        (tl, tn) = tile if tile else _tile_origin(mesh_path)
        alt = _alt_reader(alt_path, tl, tn)
    walls = []
    steep = 0
    tris_lonlat = {}
    for k in sel:
        (a, b, c) = (tri[3 * k], tri[3 * k + 1], tri[3 * k + 2])
        xs = [_xy(a)[0], _xy(b)[0], _xy(c)[0]]
        ys = [_xy(a)[1], _xy(b)[1], _xy(c)[1]]
        zs = [zed[a], zed[b], zed[c]]
        slope = _tri_plane_slope(xs, ys, zs)
        if slope <= wall_slope:
            continue
        steep += 1
        dem_slope = float("nan")
        if alt is not None:
            dzs = [alt.elevation_at(lat[i], lon[i]) for i in (a, b, c)]
            dem_slope = _tri_plane_slope(xs, ys, dzs)
            if math.isfinite(dem_slope) and dem_slope * dem_slope_factor >= slope:
                continue        # the terrain itself is that steep here
        walls.append((k, slope, dem_slope))
        tris_lonlat[k] = [(lon[i], lat[i], zed[i]) for i in (a, b, c)]
    walls.sort(key=lambda w: -w[1])
    payload["steep_triangles"] = steep
    payload["walls"] = len(walls)
    payload["wall_worst_slope"] = round(walls[0][1], 3) if walls else 0.0
    print(f"  (b) WALLS (plan slope > {wall_slope:g} and the DEM under them "
          f"gentler than 1/{dem_slope_factor:g} of it): {len(walls)} of "
          f"{steep} steep triangle(s)"
          + (f", worst {walls[0][1]:.2f} over a DEM {walls[0][2]:.2f}"
             if walls else ""))

    # (c) THE GROUND PAST THE EDGE: no INTERP_ALT bit -> the DEM's own
    if alt is None:
        print("  (c) mesh vs DEM: SKIPPED (no --alt raster given)")
    else:
        natural = [i for i in sorted({tri[3 * k + j] for k in sel
                                      for j in range(3)
                                      if not att[k] & INTERP_ALT_BIT})]
        valued = {tri[3 * k + j] for k in sel for j in range(3)
                  if att[k] & INTERP_ALT_BIT}
        past = [i for i in natural if i not in valued]
        diffs = [(abs(zed[i] - alt.elevation_at(lat[i], lon[i])), i)
                 for i in past]
        diffs.sort(reverse=True)
        over = [d for d in diffs if d[0] > dem_bar_m]
        payload["past_edge_vertices"] = len(past)
        payload["past_edge_max_abs_diff_m"] = (round(diffs[0][0], 3)
                                               if diffs else 0.0)
        payload["past_edge_over_bar"] = len(over)
        print(f"  (c) PAST THE EDGE ({len(past):,} vertex(es) on no "
              f"patch-valued triangle): max |mesh - DEM| "
              f"{diffs[0][0]:.2f} m" if diffs else
              "  (c) PAST THE EDGE: no unvalued vertex near the site")
        if diffs:
            print(f"      over the {dem_bar_m:g} m bar: {len(over)}"
                  + (f", worst at {lat[over[0][1]]:.6f},"
                     f"{lon[over[0][1]]:.6f}" if over else ""))
    if kml_path:
        _kml_edge_audit(kml_path, (nlat, nlon), walls, pairs[:400],
                        tris_lonlat, cap=kml_cap)
        payload["kml"] = kml_path
        print(f"  KML -> {kml_path}")
    return payload


def _tile_origin(path):
    match = re.search(r"([-+]\d{2})([-+]\d{3})", path)
    if not match:
        raise SystemExit(f"REFUSING: no tile origin in {path!r} — pass "
                         f"--tile LAT LON")
    return (int(match.group(1)), int(match.group(2)))


def _patch_bbox(path, margin=0.002):
    txt = open(path).read()
    lats = [float(m) for m in re.findall(r"lat=['\"](-?[\d.]+)['\"]", txt)]
    lons = [float(m) for m in re.findall(r"lon=['\"](-?[\d.]+)['\"]", txt)]
    if not lats or not lons:
        raise SystemExit(f"no lat/lon nodes found in {path}")
    return (min(lats) - margin, max(lats) + margin,
            min(lons) - margin, max(lons) + margin)


def hairline_audit(prefix, tile_lat, tile_lon, spacing_m, parallel_deg,
                   slenderness, boundary_gap_m=0.1):
    """§39 (3) THE HAIRLINE AUDIT of a build's Triangle input.

    THE ONE IMPLEMENTATION is the engine's — ``O4_Mesh_Utils.hairline_pairs``
    / ``hairline_refusals``, which is what the MESH PRE-FLIGHT itself runs
    before every Triangle4XP call.  This is the instrument half of the same
    reading, promoted from the scouts' ``nearpar.py`` on its second use
    (13an's SPLP read, then 13bk's LEMD read): a second spelling of the pair
    test here would be the census-wrapper defect one artefact over.

    Reports every non-adjacent constrained pair of the ``.poly`` within
    ``spacing_m`` and ``parallel_deg`` of parallel, and marks the UNMESHABLE
    subset the pre-flight refuses on — a pair against the OUTER boundary
    (Triangle4XP's ``-Y`` forbids Steiner points there, so the wedge can
    only be relieved by splitting the other segment: 16,298 splits at SPLP)
    or one whose Steiner cascade would run to ``slenderness`` splits
    (LEMD's worst pair reads 24.88 m / 0.0595 mm = 417,901).
    """
    import sys as _sys
    from pathlib import Path as _Path
    src = str(_Path(__file__).resolve().parents[1] / "src")
    if src not in _sys.path:
        _sys.path.insert(0, src)
    import O4_Mesh_Utils as MESH
    rows = MESH.hairline_pairs(prefix + ".poly", tile_lat,
                               spacing_m=spacing_m, parallel_deg=parallel_deg)
    bad = MESH.hairline_refusals(rows, slenderness=slenderness,
                                 boundary_gap_m=boundary_gap_m)
    by_marker = {}
    for r in rows:
        key = "/".join(str(x) for x in sorted((r["marker_a"], r["marker_b"])))
        by_marker[key] = by_marker.get(key, 0) + 1
    print(f"hairline audit — {prefix}.poly, tile {tile_lat:+03d}{tile_lon:+04d}")
    print(f"  pairs within {spacing_m} m and {parallel_deg} deg of parallel: "
          f"{len(rows)}")
    print("  by marker pair: " + ", ".join(
        f"{k} {v}" for k, v in sorted(by_marker.items(), key=lambda kv: -kv[1])))
    print(f"  UNMESHABLE (outer boundary, or slenderness >= {slenderness:g}): "
          f"{len(bad)}")
    for r in (bad or rows)[:20]:
        print("   gap {:9.4f} mm  ang {:6.3f}  len {:8.2f}/{:8.2f} m  "
              "mk {}/{}  {:<22} at {:.7f},{:.7f}".format(
                  r["gap_m"] * 1000.0, r["angle_deg"], r["len_a_m"],
                  r["len_b_m"], r["marker_a"], r["marker_b"],
                  "OUTER BOUNDARY (-Y)" if r["on_boundary"]
                  else "slenderness {:.0f}".format(r["slenderness"]),
                  tile_lat + r["lat"], tile_lon + r["lon"]))
    return {"pairs": len(rows), "unmeshable": len(bad),
            "by_marker": by_marker, "spacing_m": spacing_m,
            "parallel_deg": parallel_deg, "slenderness": slenderness,
            "rows": rows[:500], "refused": bad[:500]}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", default=None,
                    help="path to a .mesh file (not needed for "
                         "--hairline-audit, which reads the .poly)")
    ap.add_argument("--hairline-audit", action="store_true",
                    help="§39 (3): report every NON-ADJACENT constrained "
                         "pair of the build's .poly laid within the identity "
                         "spacing of, and near parallel to, another — the "
                         "hairline Triangle4XP fills with a Steiner cascade "
                         "(LEMD 13bk: 2.30 M sliver triangles; SPLP 13an: "
                         "16,298 splits of one 5.32 m segment).  Runs the "
                         "ENGINE's own pre-flight reader, so the instrument "
                         "and the refusal can never disagree.")
    ap.add_argument("--hairline-spacing", type=float, default=0.5, metavar="M",
                    help="the identity spacing the pair test runs at "
                         "(default 0.5 = emit.identity.min_distinct_spacing_m)")
    ap.add_argument("--hairline-parallel", type=float, default=5.0,
                    metavar="DEG", help="how near parallel a pair must be "
                                        "(default 5)")
    ap.add_argument("--hairline-boundary-gap", type=float, default=0.1,
                    metavar="M",
                    help="a pair against the OUTER boundary under this gap is "
                         "unmeshable whatever its slenderness (-Y forbids "
                         "Steiner points there; SPLP 13an: 0.0237 m, 16,298 "
                         "splits).  Also an assumption, never a law.")
    ap.add_argument("--hairline-slenderness", type=float, default=1.0e4,
                    metavar="N",
                    help="REPORTING/refusal threshold: shorter segment over "
                         "gap, i.e. the Steiner cascade Triangle would build "
                         "(default 1e4; an assumption, never a law — two runs "
                         "quoted at two thresholds are not comparable)")
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--patch-osm", help="derive airport bbox from this patch OSM")
    g.add_argument("--bbox", help="lat0,lat1,lon0,lon1")
    ap.add_argument("--interp-alt-audit", action="store_true",
                    help="audit the INTERP_ALT altitude authorities instead "
                         "of the bbox counts: the SEAL (is every INTERP_ALT "
                         "seed enclosed by INTERP_ALT edges?), the PLAGUE "
                         "(did every attr-8 triangle stay inside that "
                         "arrangement?) and the DOMAIN (how far does the "
                         "connected attr==8 sub-mesh R18-1b harmonic-extends "
                         "over reach beyond the patch coverage?).  Needs the "
                         "build's .node/.poly — see --inputs")
    ap.add_argument("--inputs", default=None, metavar="PREFIX",
                    help="Triangle input prefix for --interp-alt-audit, i.e. "
                         "the path without .node/.poly (default: the --mesh "
                         "path with .mesh stripped)")
    ap.add_argument("--tile", nargs=2, type=int, default=None,
                    metavar=("LAT", "LON"),
                    help="tile origin for --interp-alt-audit (default: "
                         "parsed from the mesh filename)")
    ap.add_argument("--area-bands", nargs="?", const="0.1,1,TEXEL",
                    default=None, metavar="EDGES",
                    help="also bucket the triangles by AREA, in and out of "
                         "the bbox.  Default edges 0.1,1,TEXEL m^2 — the "
                         "near-degenerate SLIVER class (< 0.1 m^2, which "
                         "carries no visible ground and costs load time "
                         "outright), then up to one orthophoto texel, then "
                         "the visible class.  Pass your own ascending "
                         "comma-separated m^2 list; the literal TEXEL "
                         "resolves to one texel^2 at the bbox's mid "
                         "latitude.  A/B WARNING: derive the bbox with "
                         "--bbox, not --patch-osm — two arms' patches give "
                         "two different boxes, which is two populations")
    ap.add_argument("--zl", type=int, default=16,
                    help="zoom level the texel is computed at (default 16)")
    ap.add_argument("--aspect", action="store_true",
                    help="also report the triangle SHAPE distribution in the "
                         "bbox — the LONG-TRIANGLE class an area band cannot "
                         "see (a 40 m x 0.5 m needle and a 4.5 m equilateral "
                         "share an area band).  Ratio = longest edge / "
                         "(2*sqrt(3) x inradius): 1.0 is equilateral, "
                         "and it rises "
                         "without bound as a triangle degenerates.  Reports "
                         "p50/p90/p99/max plus the count over --aspect-flag.")
    ap.add_argument("--aspect-flag", type=float, default=20.0,
                    metavar="RATIO",
                    help="a triangle at or above this ratio is counted as a "
                         "NEEDLE (default 20.0 — a REPORTING threshold and an "
                         "assumption, never a law; two runs quoted at two "
                         "thresholds are not comparable)")
    ap.add_argument("--water-audit", action="store_true",
                    help="audit the WATER instead of the bbox counts (owner "
                         "RULINGS 2026-09-09m): every water vertex's z (how "
                         "many at 0.000, how many not, the commonest values) "
                         "and every water triangle's z-step, with the "
                         "attribute histogram beside them.  Needs the mesh "
                         "only")
    ap.add_argument("--water-step-flag", type=float, default=1.0,
                    metavar="M", help="a water triangle whose corners span "
                                      "more than this many metres is counted "
                                      "as STEPPED (default 1.0)")
    ap.add_argument("--near", nargs=3, type=float, default=None,
                    metavar=("LAT", "LON", "RADIUS_M"),
                    help="with --water-audit, repeat the read for the water "
                         "within RADIUS_M of a site; with --edge-audit, THE "
                         "region audited (required)")
    ap.add_argument("--edge-audit", action="store_true",
                    help="THE AREA READ of a terrain edge (owner RULINGS "
                         "2026-09-10g, the CYXY texture tearing): over every "
                         "triangle within --near, (a) OVERLAPPING NODES — "
                         "vertex pairs closer in plan than --overlap-spacing "
                         "but more than --overlap-dz apart in z; (b) WALLS — "
                         "triangles whose plan slope exceeds --wall-slope "
                         "where the DEM under the same footprint is gentler "
                         "by --dem-slope-factor; (c) PAST THE EDGE — every "
                         "vertex on no patch-valued (INTERP_ALT) triangle "
                         "against the tile's own .alt raster, flagged over "
                         "--dem-bar.  A transect cannot see a fold beside it; "
                         "this can.  Prove the instrument on the CONTROL mesh "
                         "first: it must read 0 overlapping pairs")
    ap.add_argument("--alt", default=None, metavar="DATA<tile>.alt",
                    help="the DEM reference for --edge-audit's (b) and (c): "
                         "the tile's own .alt raster, the surface "
                         "Triangle4XP was handed (default: the --mesh path "
                         "with .mesh -> .alt, when it exists)")
    ap.add_argument("--overlap-spacing", type=float, default=0.5, metavar="M",
                    help="plan distance under which two vertices are one "
                         "position (default 0.5 = the law's "
                         "identity.min_distinct_spacing_m)")
    ap.add_argument("--overlap-dz", type=float, default=0.5, metavar="M",
                    help="height difference over which two such vertices are "
                         "an OVERLAP (default 0.5)")
    ap.add_argument("--wall-slope", type=float, default=1.0, metavar="SLOPE",
                    help="plan slope (m/m) at which a triangle is a WALL "
                         "(default 1.0 = 45 deg)")
    ap.add_argument("--dem-slope-factor", type=float, default=2.0,
                    metavar="X", help="a steep triangle is EXCUSED when the "
                                      "DEM under it is within this factor of "
                                      "its slope (default 2.0)")
    ap.add_argument("--dem-bar", type=float, default=1.0, metavar="M",
                    help="|mesh - DEM| past the edge counted as over the bar "
                         "(default 1.0)")
    ap.add_argument("--kml", default=None, metavar="OUT.kml",
                    help="write the offending triangles and overlapping "
                         "pairs here, for the owner's sim read")
    ap.add_argument("--kml-cap", type=int, default=2000, metavar="N",
                    help="at most this many WALL polygons in the KML, worst "
                         "first (default 2000 — a fold can mint tens of "
                         "thousands and a KML no viewer opens is no evidence)")
    ap.add_argument("--json", default=None, metavar="OUT.json",
                    help="also write the counts here, with the bbox and "
                         "band edges stamped alongside")
    args = ap.parse_args(argv)
    if not args.mesh and not args.hairline_audit:
        ap.error('--mesh is required (only --hairline-audit reads the .poly '
                 'alone, via --inputs PREFIX)')

    if args.edge_audit:
        if not args.near:
            raise SystemExit("REFUSING: --edge-audit needs --near LAT LON "
                             "RADIUS_M — the audit is an AREA read, and an "
                             "unbounded one over a whole tile is not the "
                             "acceptance any owner asked for")
        alt_path = args.alt
        if alt_path is None and args.mesh.endswith(".mesh"):
            import os
            guess = args.mesh[:-len(".mesh")] + ".alt"
            alt_path = guess if os.path.isfile(guess) else None
        payload = edge_audit(
            args.mesh, tuple(args.near), alt_path=alt_path,
            tile=tuple(args.tile) if args.tile else None,
            spacing_m=args.overlap_spacing, dz_m=args.overlap_dz,
            wall_slope=args.wall_slope,
            dem_slope_factor=args.dem_slope_factor,
            dem_bar_m=args.dem_bar, kml_path=args.kml,
            kml_cap=args.kml_cap)
        if args.json:
            import json
            with open(args.json, "w") as fh:
                json.dump(payload, fh, indent=1)
            print(f"JSON -> {args.json}")
        return 0

    if args.hairline_audit:
        prefix = args.inputs
        if prefix is None:
            if not (args.mesh or "").endswith(".mesh"):
                raise SystemExit("REFUSING: --inputs PREFIX is required when "
                                 "no --mesh path ending in .mesh is given")
            prefix = args.mesh[:-len(".mesh")]
        (tile_lat, tile_lon) = (tuple(args.tile) if args.tile
                                else _tile_origin(prefix + ".poly"))
        payload = hairline_audit(prefix, tile_lat, tile_lon,
                                 args.hairline_spacing, args.hairline_parallel,
                                 args.hairline_slenderness,
                                 args.hairline_boundary_gap)
        payload.update({"inputs": prefix, "tile": [tile_lat, tile_lon]})
        if args.json:
            import json
            with open(args.json, "w") as fh:
                json.dump(payload, fh, indent=1)
            print(f"JSON -> {args.json}")
        return 0

    if args.water_audit:
        payload = water_audit(args.mesh, step_flag_m=args.water_step_flag,
                              near=tuple(args.near) if args.near else None)
        payload["mesh"] = args.mesh
        if args.json:
            import json
            with open(args.json, "w") as fh:
                json.dump(payload, fh, indent=1)
            print(f"JSON -> {args.json}")
        return 0

    if args.interp_alt_audit:
        prefix = args.inputs
        if prefix is None:
            if not args.mesh.endswith(".mesh"):
                raise SystemExit("REFUSING: --inputs is required when the "
                                 "mesh path does not end in .mesh")
            prefix = args.mesh[:-len(".mesh")]
        (tile_lat, tile_lon) = (tuple(args.tile) if args.tile
                                else _tile_origin(args.mesh))
        print(f"INTERP_ALT audit — mesh {args.mesh}, inputs {prefix}.*, "
              f"tile {tile_lat:+03d}{tile_lon:+04d}")
        t = time.time()
        payload = interp_alt_audit(args.mesh, prefix, tile_lat, tile_lon)
        payload.update({"mesh": args.mesh, "inputs": prefix,
                        "tile": [tile_lat, tile_lon]})
        print(f"(audited in {time.time() - t:.0f}s)")
        if args.json:
            import json
            with open(args.json, "w") as fh:
                json.dump(payload, fh, indent=1)
            print(f"JSON -> {args.json}")
        return 0
    if not (args.bbox or args.patch_osm):
        ap.error("give --bbox, --patch-osm, --interp-alt-audit, "
                 "--water-audit or --hairline-audit")

    if args.bbox:
        la0, la1, lo0, lo1 = (float(x) for x in args.bbox.split(","))
    else:
        la0, la1, lo0, lo1 = _patch_bbox(args.patch_osm)
    print(f"airport bbox: lat {la0:.4f}..{la1:.4f}  lon {lo0:.4f}..{lo1:.4f}")

    mid_lat = 0.5 * (la0 + la1)
    tex = texel_m(mid_lat, args.zl)
    tex_area = tex * tex
    edges = None
    if args.area_bands is not None:
        edges = parse_area_bands(
            args.area_bands.replace("TEXEL", repr(tex_area)))
        print(f"area bands: ZL{args.zl} texel {tex:.4f} m "
              f"(area {tex_area:.3f} m^2); edges {edges}")
    # Local metre scale at the bbox centre — the same equirectangular
    # frame the patch's own layout-local metres use.  Triangle areas here
    # are only ever compared with each other and with a texel computed at
    # the same latitude, so the projection cancels.
    m_per_deg_lat = math.pi * R_EARTH_M / 180.0
    m_per_deg_lon = m_per_deg_lat * math.cos(math.radians(mid_lat))

    t = time.time()
    vlon, vlat = array.array("d"), array.array("d")
    with open(args.mesh) as f:
        line = f.readline()
        while line and not line.startswith("Vertices"):
            line = f.readline()
        nv = int(f.readline())
        for _ in range(nv):
            p = f.readline().split()
            vlon.append(float(p[0]))
            vlat.append(float(p[1]))
        line = f.readline()
        while line and not line.startswith("Triangles"):
            line = f.readline()
        nt = int(f.readline())
        in_box = 0
        nb = 0 if edges is None else len(edges) + 1
        bands_in = [0] * nb
        bands_out = [0] * nb
        area_in = [0.0] * nb
        aspects = array.array("d") if args.aspect else None
        for _ in range(nt):
            p = f.readline().split()
            a, b, c = int(p[0]) - 1, int(p[1]) - 1, int(p[2]) - 1
            cx = (vlon[a] + vlon[b] + vlon[c]) / 3.0
            cy = (vlat[a] + vlat[b] + vlat[c]) / 3.0
            inside = lo0 <= cx <= lo1 and la0 <= cy <= la1
            if inside:
                in_box += 1
            if edges is None and not (args.aspect and inside):
                continue
            ax = (vlon[a] - lo0) * m_per_deg_lon
            ay = (vlat[a] - la0) * m_per_deg_lat
            bx = (vlon[b] - lo0) * m_per_deg_lon
            by = (vlat[b] - la0) * m_per_deg_lat
            cx2 = (vlon[c] - lo0) * m_per_deg_lon
            cy2 = (vlat[c] - la0) * m_per_deg_lat
            ar = abs((bx - ax) * (cy2 - ay) - (cx2 - ax) * (by - ay)) * 0.5
            if aspects is not None and inside:
                # longest edge / (2*sqrt(3) * inradius), with inradius =
                # area / semiperimeter.  The sqrt(3) is the normalisation
                # that makes an EQUILATERAL read exactly 1.0 (its own
                # longest-edge/2r is sqrt(3)); a needle diverges.
                # Scale-free, so it separates SHAPE from SIZE — which is
                # exactly what an area band cannot do.
                e0 = math.hypot(bx - ax, by - ay)
                e1 = math.hypot(cx2 - bx, cy2 - by)
                e2 = math.hypot(ax - cx2, ay - cy2)
                s = 0.5 * (e0 + e1 + e2)
                aspects.append(max(e0, e1, e2) * s / (_EQUI_NORM * ar)
                               if ar > 0.0 else float("inf"))
            if edges is None:
                continue
            i = band_index(ar, edges)
            if inside:
                bands_in[i] += 1
                area_in[i] += ar
            else:
                bands_out[i] += 1
    print(f"vertices: {nv:,}")
    print(f"total tile triangles: {nt:,}")
    print(f"triangles in airport bbox: {in_box:,}  "
          f"({100.0 * in_box / nt:.1f}% of tile)  ← patch footprint")
    payload = {"mesh": args.mesh, "bbox": [la0, la1, lo0, lo1],
               "zl": args.zl, "texel_m": tex, "texel_area_m2": tex_area,
               "vertices": nv, "triangles_tile": nt,
               "triangles_in_bbox": in_box}
    if edges is not None:
        labels = band_labels(edges, tex_area)
        print(f"  {'area class':<24} {'in bbox':>12} {'share':>8} "
              f"{'ground m^2':>14} {'outside':>12}")
        for i, lab in enumerate(labels):
            share = (100.0 * bands_in[i] / in_box) if in_box else 0.0
            print(f"  {lab:<24} {bands_in[i]:>12,} {share:>7.1f}% "
                  f"{area_in[i]:>14,.1f} {bands_out[i]:>12,}")
        payload["area_band_edges_m2"] = edges
        payload["area_band_labels"] = labels
        payload["area_bands_in_bbox"] = bands_in
        payload["area_bands_outside"] = bands_out
        payload["area_bands_ground_m2_in_bbox"] = area_in
    if aspects is not None and len(aspects):
        srt = sorted(aspects)
        n = len(srt)

        def _q(p):
            return srt[min(n - 1, max(0, int(round(p * (n - 1)))))]
        needles = sum(1 for v in srt if v >= args.aspect_flag)
        print(f"  aspect (longest edge / 2*sqrt(3)*inradius; "
              f"1.0 = equilateral), "
              f"{n:,} triangle(s) in bbox:")
        print(f"    p50 {_q(0.50):.2f}  p90 {_q(0.90):.2f}  "
              f"p99 {_q(0.99):.2f}  max {srt[-1]:.2f}")
        print(f"    needles >= {args.aspect_flag:g}: {needles:,} "
              f"({100.0 * needles / n:.3f}% of in-bbox)")
        payload["aspect_flag"] = args.aspect_flag
        payload["aspect_in_bbox"] = {
            "n": n, "p50": _q(0.50), "p90": _q(0.90), "p99": _q(0.99),
            "max": srt[-1], "needles": needles}
    print(f"(parsed in {time.time() - t:.0f}s)")
    if args.json:
        import json
        with open(args.json, "w") as fh:
            json.dump(payload, fh, indent=1)
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
