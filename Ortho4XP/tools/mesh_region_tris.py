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
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--patch-osm", help="derive airport bbox from this patch OSM")
    g.add_argument("--bbox", help="lat0,lat1,lon0,lon1")
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
    ap.add_argument("--json", default=None, metavar="OUT.json",
                    help="also write the counts here, with the bbox and "
                         "band edges stamped alongside")
    args = ap.parse_args(argv)

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
        for _ in range(nt):
            p = f.readline().split()
            a, b, c = int(p[0]) - 1, int(p[1]) - 1, int(p[2]) - 1
            cx = (vlon[a] + vlon[b] + vlon[c]) / 3.0
            cy = (vlat[a] + vlat[b] + vlat[c]) / 3.0
            inside = lo0 <= cx <= lo1 and la0 <= cy <= la1
            if inside:
                in_box += 1
            if edges is None:
                continue
            ax = (vlon[a] - lo0) * m_per_deg_lon
            ay = (vlat[a] - la0) * m_per_deg_lat
            bx = (vlon[b] - lo0) * m_per_deg_lon
            by = (vlat[b] - la0) * m_per_deg_lat
            cx2 = (vlon[c] - lo0) * m_per_deg_lon
            cy2 = (vlat[c] - la0) * m_per_deg_lat
            ar = abs((bx - ax) * (cy2 - ay) - (cx2 - ax) * (by - ay)) * 0.5
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
    print(f"(parsed in {time.time() - t:.0f}s)")
    if args.json:
        import json
        with open(args.json, "w") as fh:
            json.dump(payload, fh, indent=1)
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
