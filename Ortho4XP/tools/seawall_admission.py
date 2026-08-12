#!/usr/bin/env python3
"""WHERE THE SEAWALL IS ADMITTED, and how much of the shoreline it covers.

The instrument behind Round 7 (`docs/specs/round7-seawall-spec.md`) and
Round 17 §R17-3: a patch's emitted coverage meets water somewhere, and
the question is always the same three numbers — how long the admitted
wall is, how long the shoreline beside the coverage is, and what
fraction of it the wall covers.

    venv/bin/python tools/seawall_admission.py LAT LON [--icao VHHH]
        [--patch FILE.osm ...] [--admission MODE] [--near-m 300]
        [--json OUT.json]

IT MEASURES NOTHING ITSELF.  Every geometric answer comes from
production's own functions — ``O4_Vector_Map.seawall_breaklines`` (the
admission law), ``sea_seed_areas`` (the cutter), ``graded_coverage_area``
(the R17-3 admission union and its role vocabulary),
``O4_Vector_Utils.coastline_to_MultiPolygon`` (the sea) — and the patch
is read with the harness library's own parser
(``tools/check_grade._parse_osm``), so this tool and the census read one
geometry.  A private re-implementation of any of them is the
census-wrapper defect.

``--admission`` selects WHICH union is offered to the wall law, because
the answer differs and the difference is the point:

  * ``graded-coverage`` (default) — production's R17-3 admission set:
    the closed rings whose role carries a LAND altitude
    (``O4_Vector_Map.GRADED_COVERAGE_ROLES``), the aerodrome boundary
    ribbon and the water-spanning ribbon roles excluded.
  * ``all-rings`` — every valid closed way in the patch: the union
    ``include_patches`` builds as ``patches_area`` (the LAND cutter),
    which is what the wall law consumed before R17-3.
  * ``pavement`` — the airside pavement roles alone, the narrowest
    reading of the Round 7 text.

READ-ONLY: cached OSM layers only, no DEM composition, no network, no
writes (bar ``--json``).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R_EARTH = 6378137.0
DEG_M = R_EARTH * math.pi / 180.0


def metre_length(geom, cos_lat: float) -> float:
    """Length in metres of a tile-relative (degree) geometry."""
    if geom is None or getattr(geom, "is_empty", True):
        return 0.0
    from shapely import affinity
    return affinity.scale(geom, xfact=cos_lat * DEG_M, yfact=DEG_M,
                          origin=(0, 0)).length


def coverage_union(patch_files, lat: int, lon: int, mode: str, tile=None):
    """The admission union for ``mode``, tile-relative, from the patches.

    Rings come from ``check_grade._parse_osm`` (the harness library's
    reader) and the role vocabulary from ``O4_Vector_Map`` — nothing is
    re-typed here."""
    from shapely import geometry, ops
    import O4_Vector_Map as VMAP
    from check_grade import _parse_osm

    if mode == "graded-coverage":
        roles = VMAP.GRADED_COVERAGE_ROLES
    elif mode == "pavement":
        roles = VMAP.SEAWALL_PAVEMENT_ROLES
    else:
        roles = None                       # all-rings
    polys = []
    n_rings = n_kept = 0
    for path in patch_files:
        nodes, ways = _parse_osm(Path(path))
        for way in ways:
            nids = way.nids
            if len(nids) < 4 or nids[0] != nids[-1]:
                continue
            n_rings += 1
            if roles is not None and way.role not in roles:
                continue
            try:
                ring = [(nodes[nid][1] - lon, nodes[nid][0] - lat)
                        for nid in nids]
            except KeyError:
                continue
            try:
                pol = geometry.Polygon(ring)
            except Exception:
                continue
            if pol.is_valid and pol.area:
                polys.append(pol)
                n_kept += 1
    # THE DECLARED CORRIDORS (R17-2) are part of the coverage in
    # production (``include_patches`` inserts their rings), so they are
    # part of it here — through production's own generator, with the
    # same cfg parser, or the tool would measure a different island.
    if mode != "pavement":
        corridor_tile = tile or type(
            "_TileStub", (), {"lat": lat, "lon": lon})()
        for (pol, _box) in VMAP.declared_corridor_rings(corridor_tile):
            polys.append(pol)
            n_kept += 1
    if not polys:
        return geometry.Polygon(), n_rings, 0
    return ops.unary_union(polys), n_rings, n_kept


def sea_area_for_tile(tile, lat: int, lon: int):
    """The tile's sea polygon — production's coastline path verbatim."""
    from shapely import geometry, ops
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP
    import O4_Vector_Utils as VECT

    layer = OSM.OSM_layer()
    if not OSM.OSM_queries_to_OSM_layer(
            VMAP.COASTLINE_QUERIES, layer, lat, lon, [],
            cached_suffix="coastline"):
        raise SystemExit("no cached coastline for this tile — refusing "
                         "(a download is an owner act, --refresh-data)")
    coastline = OSM.OSM_to_MultiLineString(layer, lat, lon)
    loops = geometry.MultiLineString(
        [ln for ln in coastline.geoms if ln.is_ring])
    remainder = VECT.ensure_MultiLineString(VECT.cut_to_tile(
        geometry.MultiLineString(
            [ln for ln in coastline.geoms if not ln.is_ring]),
        strictly_inside=True))
    if not remainder.is_empty:
        remainder = VECT.ensure_MultiLineString(ops.linemerge(remainder))
    coastline = geometry.MultiLineString(
        list(remainder.geoms) + list(loops.geoms))
    return VECT.ensure_MultiPolygon(
        VECT.coastline_to_MultiPolygon(coastline, lat, lon, False))


def flat_site_inset_stamp(tile):
    """Stamp the tile's DEM stub with the flat-site inset extents.

    R17b-2's admission is ``coastline ∩ constant-inset coverage``, and
    production reads that footprint from the provenance
    ``O4_Airport_Elevation_Insets.overlay_flat_site_insets`` writes while
    BAKING.  This tool never runs DEM prep (read-only, no DEM
    composition), so it asks production's own extent generator —
    ``auto_patch.flat_site_mode.flat_site_substitutions``, the same call
    the bake consumes — and stamps the entries in the same shape, so
    ``O4_Vector_Map.constant_inset_area`` reads them unmodified.

    TWO DIFFERENCES, BOTH STATED RATHER THAN SWALLOWED:

    * the bake DROPS a claimed-object cluster whose feather ring fails
      the R11-2 datum check, and that refusal is a DEM measurement this
      tool cannot make;
    * the detector CLASSIFIES AGAINST THE DEM (``flat_site_substitutions``
      returns ``[]`` outright when the tile carries no composed
      ``alt_dem``), and this tool composes no DEM by design.  A bare
      "0 entries" would then read exactly like "this tile has no flat
      site", which is the silent-degradation class this repo refuses —
      so the caller gets a NOTE saying which of the two it is.

    Returns ``(entry_count, unchecked_cluster_count, note)``.
    """
    from auto_patch import flat_site_mode as FLAT
    dem = getattr(tile, "dem", None)
    if dem is None or getattr(dem, "alt_dem", None) is None:
        return 0, 0, ("NOT MEASURED — the flat-site detector classifies "
                      "against the composed tile DEM and this tool composes "
                      "none.  Read the footprint off a real build's "
                      "[flat-site] lines instead; this is not evidence that "
                      "the tile has no flat site.")
    subs = FLAT.flat_site_substitutions(tile)
    entries = []
    for sub in subs or ():
        entries.append({"kind": "synthetic_flat_site",
                        "icao": sub.get("icao"),
                        "z0_m": sub.get("z0_m"),
                        "extent_tile_degrees": list(sub["extent_deg"])})
        for cluster in (sub.get("object_clusters") or ()):
            entries.append({"kind": "synthetic_flat_site_object_cluster",
                            "icao": sub.get("icao"),
                            "z0_m": sub.get("z0_m"),
                            "extent_tile_degrees": list(
                                cluster["extent_deg"])})
        for corridor in (sub.get("declared_corridors") or ()):
            entries.append({"kind": "declared_corridor",
                            "icao": sub.get("icao"),
                            "z0_m": sub.get("z0_m"),
                            "extent_tile_degrees": list(
                                corridor["extent_deg"])})
    if getattr(tile, "dem", None) is None:
        tile.dem = type("_DemStub", (), {})()
    tile.dem.synthetic_flat_site_provenance = entries
    n_cluster = sum(1 for e in entries
                    if e["kind"] == "synthetic_flat_site_object_cluster")
    return len(entries), n_cluster, ("measured from the detector's own "
                                     "extents; cluster datum refusals not "
                                     "reproduced")


def measure(lat: int, lon: int, patch_files, mode: str, near_m: float,
            build_dir: str = "", flat_site_inset: bool = False):
    """The three numbers, plus the geometry that produced them."""
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    from shapely import geometry

    tile = CFG.Tile(lat, lon, build_dir or "")
    if build_dir:
        # The DECLARED corridors live in the tile cfg (R17-2), which lands
        # on the Tile instance — read it, or the tool measures an island
        # production does not build.
        tile.read_from_config()
    coverage, n_rings, n_kept = coverage_union(patch_files, lat, lon, mode,
                                               tile=tile)
    if coverage.is_empty:
        return {"error": "no coverage rings in the given patches",
                "rings_seen": n_rings, "admission_mode": mode}
    (minx, miny, maxx, maxy) = coverage.bounds
    cos_lat = math.cos(math.radians(lat + (miny + maxy) / 2))
    sea = sea_area_for_tile(tile, lat, lon)
    tidal = VMAP._tidal_water_area(tile)
    seed = VMAP.sea_seed_areas(sea, tidal, patch_pavement_area=coverage)
    # R17b-2: the wall admission may also carry the CONSTANT-INSET
    # coastline.  The DENOMINATOR below stays on the graded coverage, so
    # the percentage remains comparable with the pre-R17b recon number.
    wall_admission = coverage
    inset_entries = inset_clusters = 0
    inset_note = "not requested"
    if flat_site_inset:
        inset_entries, inset_clusters, inset_note = (
            flat_site_inset_stamp(tile))
        coastal = VMAP.coastline_wall_admission(tile, sea)
        if not coastal.is_empty:
            from shapely import ops as _ops
            wall_admission = _ops.unary_union([coverage, coastal])
    lines = VMAP.seawall_breaklines(wall_admission, seed, float(lat))
    wall_m = sum(metre_length(geometry.LineString(c), cos_lat)
                 for c in lines if len(c) >= 2)
    # THE DENOMINATOR: the shoreline BESIDE the coverage — the coastline
    # within ``near_m`` of it (the recon's 20,873 m read at VHHH).
    env = coverage.buffer(near_m / DEG_M)
    shore = sea.boundary.intersection(env)
    shore_m = metre_length(shore, cos_lat)
    polys = list(getattr(coverage, "geoms", [coverage]))
    perim = metre_length(
        geometry.MultiLineString([p.exterior for p in polys
                                  if p.exterior is not None]), cos_lat)
    return {
        "admission_mode": mode + ("+flat-site-inset" if flat_site_inset
                                  else ""),
        "flat_site_inset_entries": inset_entries,
        "flat_site_inset_clusters_unchecked": inset_clusters,
        "flat_site_inset_note": inset_note,
        "rings_seen": n_rings,
        "rings_admitted": n_kept,
        "coverage_km2": round(coverage.area * DEG_M * DEG_M * cos_lat / 1e6,
                              4),
        "coverage_perimeter_m": round(perim, 1),
        "wall_lines": len(lines),
        "wall_m": round(wall_m, 1),
        "shoreline_near_m": round(shore_m, 1),
        "near_m": float(near_m),
        "coverage_pct": (round(100.0 * wall_m / shore_m, 1)
                         if shore_m else None),
        "longest_walls_m": [round(m, 1) for m in sorted(
            (metre_length(geometry.LineString(c), cos_lat)
             for c in lines if len(c) >= 2), reverse=True)[:8]],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lat", type=int)
    ap.add_argument("lon", type=int)
    ap.add_argument("--icao", default=None,
                    help="patch file <ICAO>_auto.patch.osm in the tile's "
                         "patch dir (repeatable via --patch instead)")
    ap.add_argument("--patch", action="append", default=[],
                    help="explicit patch .osm path (repeatable)")
    ap.add_argument("--admission", default="graded-coverage",
                    choices=("graded-coverage", "all-rings", "pavement"))
    ap.add_argument("--near-m", type=float, default=300.0,
                    help="shoreline denominator band (default 300 m)")
    ap.add_argument("--build-dir", default="",
                    help="tile build dir holding Ortho4XP_+LL+LLL.cfg — read "
                         "for the DECLARED corridors (R17-2)")
    ap.add_argument("--flat-site-inset", action="store_true",
                    help="R17b-2: also admit the COASTLINE inside the "
                         "flat-site constant-inset footprint (the reclaimed "
                         "island).  The denominator stays on the graded "
                         "coverage so the percentage stays comparable")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    import O4_File_Names as FNAMES
    patch_files = [Path(p) for p in args.patch]
    if args.icao:
        patch_files.append(Path(FNAMES.patch_dir(args.lat, args.lon))
                           / f"{args.icao.upper()}_auto.patch.osm")
    if not patch_files:
        pdir = Path(FNAMES.patch_dir(args.lat, args.lon))
        patch_files = sorted(pdir.glob("*.patch.osm"))
    missing = [p for p in patch_files if not p.is_file()]
    if missing:
        print("REFUSING — patch file(s) not found: "
              + ", ".join(str(p) for p in missing))
        return 2
    out = measure(args.lat, args.lon, patch_files, args.admission,
                  args.near_m, build_dir=args.build_dir,
                  flat_site_inset=args.flat_site_inset)
    out["patches"] = [str(p) for p in patch_files]
    print(f"=== SEAWALL ADMISSION  tile +{args.lat:02d}+{args.lon:03d}  "
          f"[{out['admission_mode']}] ===")
    for key in ("patches", "flat_site_inset_entries",
                "flat_site_inset_clusters_unchecked", "flat_site_inset_note",
                "rings_seen", "rings_admitted", "coverage_km2",
                "coverage_perimeter_m", "wall_lines", "wall_m",
                "shoreline_near_m", "near_m", "coverage_pct",
                "longest_walls_m", "error"):
        if key in out:
            print(f"  {key:24s} {out[key]}")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1))
        print(f"JSON -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
