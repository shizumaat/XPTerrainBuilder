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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", required=True, help="path to a .mesh file")
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
    ap.add_argument("--json", default=None, metavar="OUT.json",
                    help="also write the counts here, with the bbox and "
                         "band edges stamped alongside")
    args = ap.parse_args(argv)

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
        ap.error("give --bbox, --patch-osm, or --interp-alt-audit")

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
