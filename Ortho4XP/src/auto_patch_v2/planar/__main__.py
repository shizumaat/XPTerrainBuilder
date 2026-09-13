"""``venv/bin/python -m auto_patch_v2.planar ICAO --out DIR``

Loads the airport, classifies, builds the planar map, writes
``faces.geojson`` / ``breaklines.geojson`` / ``report.json`` into DIR
and prints the counts and the wall time.  Input roots default to the
engine tree's mounted data dirs (``Elevation_data``, ``OSM_data``,
``Airport_mod_cache`` — the shared corpus the lane ritual mounts) and
the X-Plane install named by ``custom_scenery_dir`` in the engine's
``Ortho4XP.cfg`` (a convenience of THIS entry point only; the library
takes explicit paths).  No environment reads.
"""
from __future__ import annotations

import argparse
import dataclasses as _dc
import json
import os
import sys
import time
from pathlib import Path

from ..airport.load import Inputs, load_with_report
from ..classify import classify, load_rules
from ..law import Law
from .build import build
from .index import to_geojson

ENGINE_DIR = Path(__file__).resolve().parents[3]


def _cfg_value(key: str) -> str:
    cfg = ENGINE_DIR / "Ortho4XP.cfg"
    if not cfg.is_file():
        return ""
    for line in cfg.read_text(errors="replace").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def default_inputs(xplane_root: str | None = None, cifp_dir: str | None = None,
                   data_root: str | None = None, feather_m: float = 60.0,
                   dem_frame: str = "production", allow_degraded_dem: bool = False
                   ) -> Inputs:
    """The engine tree's mounts and the cfg-named install."""
    if xplane_root is None:
        custom = _cfg_value("custom_scenery_dir")
        xplane_root = os.path.dirname(custom.rstrip("/")) if custom else \
            os.path.expanduser("~/X-Plane 12")
    if cifp_dir is None:
        cifp_dir = _cfg_value("cifp_data_path") or os.path.join(
            xplane_root, "Custom Data", "CIFP")
    root = Path(data_root) if data_root else ENGINE_DIR

    def _num(key: str) -> float | None:
        v = _cfg_value(key)
        try:
            return float(v) if v else None
        except ValueError:
            return None
    return Inputs(xplane_root=xplane_root, cifp_dir=cifp_dir,
                  osm_root=str(root / "OSM_data"),
                  elevation_root=str(root / "Elevation_data"),
                  mod_cache_root=str(root / "Airport_mod_cache"),
                  feather_m=feather_m, dem_frame=dem_frame,
                  allow_degraded_dem=allow_degraded_dem,
                  # the core's road clamp knobs, as the tile build reads them
                  road_grade_limit=_num("road_grade_limit"),
                  lane_width_m=_num("lane_width"))


def add_dem_frame_args(ap: argparse.ArgumentParser) -> None:
    """The DEM-frame flags both CLIs share (03j)."""
    ap.add_argument("--dem-frame", choices=("production", "authored"),
                    default="production",
                    help="production: the core's composed tile DEM the mesh "
                         "drapes on (default); authored: raw .hgt + inset")
    ap.add_argument("--allow-degraded-dem", action="store_true",
                    help="accept a COLD production frame knowingly (recorded; "
                         "authorises no write)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="auto_patch_v2.planar")
    ap.add_argument("icao")
    ap.add_argument("--out", required=True)
    ap.add_argument("--xplane-root")
    ap.add_argument("--cifp-dir")
    ap.add_argument("--data-root", help="root holding Elevation_data/, OSM_data/, "
                    "Airport_mod_cache/ (default: the engine tree's mounts)")
    ap.add_argument("--feather-m", type=float, default=60.0)
    add_dem_frame_args(ap)
    ap.add_argument("--grid-m", type=float, default=None,
                    help="identity snap grid (default: law min_distinct_spacing_m)")
    ap.add_argument("--stage", choices=("planar", "structures"), default="planar",
                    help="structures: STOP after the structure stages (objects, "
                         "corridors, tunnels, basins) and write structures.json — the "
                         "synthetic-first replay of a site's structure readings, no "
                         "arrangement, no solve (lane v2lemd4, 2026-09-06)")
    ap.add_argument("--kml", default=None,
                    help="with --stage structures: also write a KML of every structure "
                         "reading (wall corridors by class with widths / depths / grades / "
                         "mouths, object corridors, door wells, sunken roads, basins) for "
                         "the owner's read (RULINGS 2026-09-08n: the inventory BEFORE a cut)")
    args = ap.parse_args(argv)
    os.chdir(ENGINE_DIR)   # the core's resource/data contract (production DEM frame)

    t0 = time.perf_counter()
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            args.feather_m, args.dem_frame, args.allow_degraded_dem)
    law = Law.for_airport(args.icao)
    airport, lrep = load_with_report(args.icao, inputs, law)
    t1 = time.perf_counter()
    cl = classify(airport, law, load_rules())
    t2 = time.perf_counter()
    if args.stage == "structures":
        rec = structure_records(airport, cl, law)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        rec["wall_s"] = {"load": round(t1 - t0, 3), "classify": round(t2 - t1, 3),
                         "structures": round(time.perf_counter() - t2, 3)}
        (out / "structures.json").write_text(json.dumps(rec, indent=1, default=str))
        if args.kml:
            write_kml(rec, Path(args.kml))
            print(f"  KML -> {args.kml}")
        print(f"{airport.icao} structures: corridors {len(rec['corridors'])}  door wells "
              f"{len(rec['door_wells'])} (refused {len(rec['door_refused'])})  sunken roads "
              f"{len(rec['sunken_roads'])} (refused {len(rec['sunken_refused'])})  tunnels "
              f"{len(rec['tunnels'])}  basins {len(rec['basins'])}  corridor refusals "
              f"{len(rec['corridor_refused'])}  tunnel refusals {len(rec['tunnel_refused'])}  "
              f"basin refusals {len(rec['basin_refused'])}  -> {out / 'structures.json'}")
        for c in rec["corridors"]:
            print(f"  corridor {c['id']}: edge_wall {c['edge_wall']}  mouth {c['mouth_kind']}  "
                  f"ends {c['ends']}  length {c['length_m']:.1f} m  width {c['width_m']:.1f} m  "
                  f"depth {c['depth_m']:.2f}  crest {c['plate_y']:+.2f}  mouth ground "
                  f"{c['mouth_dem_z']:.2f}  floor {c['floor_z']:.2f}")
        for w in rec["door_wells"]:
            print(f"  door well {w['id']}: sill {w['sill_z']:.2f} ({w['depth_m']:.2f} m under "
                  f"{w['ground_z']:.2f}) width {w['sill_width_m']:.2f} m out {w['plate_out_m']:.2f}/"
                  f"{w['well_out_m']:.2f} m plate cover {w['plate_cover']:.2f} at {w['sill_ll']}")
        for r in rec["door_refused"]:
            print(f"  door refused {r}")
        for r in rec["sunken_roads"]:
            print(f"  sunken road {r['id']}: cut {r['floor_z']:.2f} ({r['depth_m']:.2f} m under "
                  f"{r['mouth_dem_z']:.2f}) top {r['top_z']:.2f} length {r['length_m']:.1f} m width "
                  f"{r['width_m']:.1f} m cover {r['cover']:.2f} "
                  f"cut at {r['cut_ll']} top at {r['top_ll']}")
        for r in rec["sunken_refused"]:
            print(f"  sunken refused {r}")
        wcs = rec["wall_corridors"]
        by = {}
        for w in wcs:
            by[w["cls"]] = by.get(w["cls"], 0) + 1
        print(f"  wall corridors (Law C): {len(wcs)} records — "
              + ", ".join(f"{k} {n}" for k, n in sorted(by.items()))
              + f"; refused {len(rec['wall_corridor_refused'])}")
        for w in wcs:
            print(f"  wall corridor {w['id']}: {w['cls']} ends {w['ends']} length {w['length_m']:.1f} m "
                  f"width {w['width_m']:.1f} m floor {w['floor_min_z']:.2f}..{w['floor_max_z']:.2f} "
                  f"(ground {w['mouth_dem_z']:.2f}, depth {w['depth_m']:.2f} m) authored grade "
                  f"{100.0 * w['max_authored_grade']:.1f} % headroom {w['headroom_m']} "
                  f"mouth {w['mouth_ll']} far {w['far_ll']}")
        for r in rec["wall_corridor_refused"]:
            print(f"  wall corridor refused {r}")
        # RULINGS 2026-09-10w: the three admission clauses per CANDIDATE
        for a in rec["wall_corridor_admission"]:
            print(f"  wall corridor admission {a}")
        # RULINGS 2026-09-10ab: ONE TABLE of the two discriminators
        rows = rec["wall_corridor_floor_probe"]
        if rows:
            print(f"  wall corridor floor probe ({len(rows)} candidates with a mouth): "
                  f"airport | placement@bands | floor | road level | delta | ramp-reachable "
                  f"| slab | road witness")
            for r in rows:
                d = "     -" if r["delta_m"] is None else f"{r['delta_m']:+7.2f}"
                lv = "     -" if r["road_level_z"] is None else f"{r['road_level_z']:7.2f}"
                dist = "  -" if r["road_dist_m"] is None else f"{r['road_dist_m']:5.1f} m"
                print(f"  PROBE {r['airport']} | {r['resource']}@{r['bands']} at {r['site']} | "
                      f"floor {r['floor_min_z']:.2f}..{r['floor_max_z']:.2f} "
                      f"(mouth {r['mouth_floor_z']}) | road {lv} at {dist} | delta {d} | "
                      f"tol {'Y' if r['within_tol'] else 'n'} | ramp "
                      f"{'Y' if r['ramp_reachable'] else 'n'} | slab "
                      f"{'Y' if r['slab'] else 'n'} ({r['slab_cover']:.2f}) | "
                      f"len {r['length_m']:.1f} m | {r['road_source']}: {r['road_witness']} | "
                      f"{r['slab_witness']}")
        # RULINGS 2026-09-10af: ONE TABLE — spacing, below-zero perimeter
        # fraction, cut width vs footprint width, current admission
        ncs = rec["wall_corridor_narrow_cut"]
        if ncs:
            print(f"  wall corridor narrow-cut table ({len(ncs)} candidates): airport | "
                  f"placement@bands | spacing | width | below-zero perimeter fraction | "
                  f"cut width / footprint width | admitted")
            for r in ncs:
                w = "    -" if r["width_m"] is None else f"{r['width_m']:5.1f}"
                wr = "    -" if r["width_ratio"] is None else f"{r['width_ratio']:5.3f}"
                print(f"  NARROW {r['airport']} | {r['resource']}@{r['bands']} at {r['site']} | "
                      f"spacing {r['spacing_m']:6.2f} m | width {w} m | frac "
                      f"{r['fraction']:5.3f} ({r['below_perimeter_m']:.1f}/"
                      f"{r['perimeter_m']:.1f} m) | obj frac {r['fraction_total']:5.3f} "
                      f"({r['total_below_perimeter_m']:.1f}/{r['total_perimeter_m']:.1f} m)"
                      f" | site {r['site_area_m2']:9.1f} m2 thick {r['site_thickness_m']:7.2f} m "
                      f"inside {r['axis_inside_frac']:5.3f} | cut {r['cut_width_m']:7.1f} / "
                      f"{r['footprint_width_m']:7.1f} m = {wr} | "
                      f"{'ADMITTED' if r['admitted'] else 'refused'}")
            # RULINGS 2026-09-10ao — THE WALL HEIGHT TABLE: per candidate,
            # how far the wall rises above the OBJECT'S OWN zero (its own
            # component's max_y; the wall connected above it).
            print(f"  wall HEIGHT above the object's zero ({len(ncs)} candidates): "
                  f"airport | placement@bands | own | one step | connected "
                  f"(max of the two bands) | connected (min) | admitted")
            for r in ncs:
                print(f"  HEIGHT {r['airport']} | {r['resource']}@{r['bands']} at "
                      f"{r['site']} | own {r.get('wall_own_m', 0.0):7.2f} | step "
                      f"{r.get('wall_step_m', 0.0):7.2f} | conn "
                      f"{r.get('wall_connected_m', 0.0):7.2f} | conn_min "
                      f"{r.get('wall_connected_min_m', 0.0):7.2f} | A "
                      f"{r.get('wall_a_m')} B {r.get('wall_b_m')} | "
                      f"{'ADMITTED' if r['admitted'] else 'refused'}")
        for t in rec["tunnels"]:
            print(f"  tunnel {t['id']}: mouth_z {t['mouth_z']:.2f}  top_s {t['top_s']:.1f}  "
                  f"climb_from {t['climb_from_s']:.1f}  grade {t['design_grade']:.4f}  "
                  f"decks {t['decks']}  clipped '{t['clipped_by']}'  outside "
                  f"{t['trench_outside_max_m']:.3f}  mouth {t['mouth_ll']} top {t['top_ll']}")
        for b in rec["basins"]:
            print(f"  basin {b['id']}: floor {b['floor_z']:.2f}  area {b['area_m2']:.0f} m2  "
                  f"{b['kind']}  {', '.join(o.split('/')[-1] for o in b['objects'])}")
        return 0
    pm, stats = build(airport, cl, law, args.grid_m)
    t3 = time.perf_counter()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    faces, lines = to_geojson(pm, airport.frame)
    (out / "faces.geojson").write_text(json.dumps(faces))
    (out / "breaklines.geojson").write_text(json.dumps(lines))
    t4 = time.perf_counter()
    report = {
        "icao": airport.icao, "name": airport.name, "ruleset": law.ruleset_key,
        "frame": {"origin": airport.frame.origin, "crs": airport.frame.crs,
                  "identity_dp": airport.frame.identity_dp},
        "load": _dc.asdict(lrep), "classification": dict(cl.stats),
        "classification_notes": list(cl.notes),
        "cells_by_role": _count(c.role for c in cl.cells),
        "planar": _dc.asdict(stats),
        "wall_s": {"load": round(t1 - t0, 3), "classify": round(t2 - t1, 3),
                   "planar": round(t3 - t2, 3), "write": round(t4 - t3, 3),
                   "total": round(t4 - t0, 3)},
        "pack": _dc.asdict(airport.pack),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"{airport.icao} planar map: faces {stats.faces}  edges {stats.edges}  "
          f"vertices {stats.vertices}  breaklines {stats.breaklines}  "
          f"T-vertices {stats.t_vertices}  dropped faces {stats.dropped_faces}  "
          f"min spacing {stats.min_vertex_spacing_m:.2f} m  "
          f"max chord {stats.max_chord_m:.1f} m")
    print("  faces by role: " + ", ".join(
        f"{r} {n}" for r, n in sorted(stats.faces_by_role.items())))
    print(f"  wall: load {t1 - t0:.2f} s  classify {t2 - t1:.2f} s  "
          f"planar {t3 - t2:.2f} s  write {t4 - t3:.2f} s  total {t4 - t0:.2f} s")
    print(f"  wrote {out / 'faces.geojson'}, breaklines.geojson, report.json")
    return 0


def structure_records(airport, cl, law) -> dict:
    """The structure stages alone — objects read, corridors, tunnels,
    basins — as plain records with every refusal (the ``--stage
    structures`` replay: what a site's objects state, before any
    arrangement or solve).  Runs the same passes in the same order as
    ``planar.build.build``."""
    from ..airport import obj8
    from ..airport.tunnel_objects import read_corridors
    from .basins import build_basins, read_objects
    from .structures import build_structures
    to_ll = airport.frame.transformers()[1]
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, orep = read_objects(airport, law, cache)
    from ..airport.door_wells import read_door_wells
    from ..airport.sunken_roads import read_sunken_roads
    from .door_ramps import door_groups, sunken_groups
    from ..airport.wall_corridors import read_wall_corridors
    from .wall_corridor_ramps import wall_corridor_groups
    corridors, tstats = read_corridors(airport, objects, cache, law)
    from ..airport.thin_plates import read_plates
    plates, pstats = read_plates(airport, objects, cache, law,
                                 {c.resource for c in corridors})
    tstats.plates = pstats.plates
    tstats.refused.extend(pstats.refused)
    wells, dstats = read_door_wells(airport, objects, cache, law)
    roads, rstats = read_sunken_roads(airport, objects, cache, law)
    walls_c, wstats = read_wall_corridors(airport, objects, cache, law, cl,
                                          measure=True)
    extra = door_groups(wells, law) + sunken_groups(roads, law, rstats.refused) \
        + wall_corridor_groups(walls_c, law)
    cl2, tunnels, sstats = build_structures(airport, cl, law, objects, corridors, extra,
                                            plates)
    cl3, basins, bstats = build_basins(airport, cl2, law, tunnels, objects, cache, report=orep)

    def ll(p):
        la, lo = to_ll(p[0], p[1])
        return (round(la, 7), round(lo, 7))
    return {
        "icao": airport.icao,
        "objects": {"placements": orep.placements, "below_grade": orep.below_grade_objects,
                    "through_grade": {k.split("/")[-1]: v for k, v in orep.through_grade.items()},
                    "no_floor": {k.split("/")[-1]: v for k, v in orep.no_floor.items()},
                    "rim_protrusions": {k.split("/")[-1]: v
                                        for k, v in orep.rim_protrusions.items()}},
        "corridors": [{"id": c.id, "resource": c.resource, "objects": list(c.objects),
                       "edge_wall": c.edge_wall, "mouth_kind": c.mouth_kind, "ends": c.ends,
                       "length_m": c.length_m, "width_m": c.width_m, "depth_m": c.depth_m,
                       "plate_y": c.plate_y, "mouth_dem_z": c.mouth_dem_z, "floor_z": c.floor_z,
                       "mouth_ll": ll(c.axis[0]), "far_ll": ll(c.axis[-1]),
                       "notes": list(c.notes)} for c in corridors],
        "corridor_refused": list(tstats.refused),
        # spec §33 (2): the THIN-PLATE wall objects read
        "plates": [{"id": p.id, "resource": p.resource, "object_id": p.object_id,
                    "kind": p.kind, "length_m": p.length_m, "width_m": p.width_m,
                    "span_m": p.span_m, "top_y_m": p.top_y_m, "top_z": p.top_z,
                    "bore_ways": [list(t) for t in p.bore_ways],
                    "bridge_ways": [list(t) for t in p.bridge_ways],
                    "end0_ll": ll(p.ends[0]), "end1_ll": ll(p.ends[1]),
                    "plan_ll": [ll(q) for q in p.plan.exterior.coords],
                    "notes": list(p.notes)} for p in plates],
        "plate_refused": list(pstats.refused),
        "plate_stats": {k: v for k, v in _dc.asdict(pstats).items()
                        if not isinstance(v, list)},
        "plate_mouths": list(sstats.plate_mouths),
        "crest_from_approach": list(sstats.crest_from_approach),
        "tunnel_object_stats": {k: v for k, v in _dc.asdict(tstats).items()
                                if not isinstance(v, list)},
        "tunnels": [{"id": t.id, "source": t.source, "mouth_z": t.mouth_z,
                     "mouth_dem_z": t.mouth_dem_z, "top_s": t.top_s,
                     "climb_from_s": t.climb_from_s, "design_grade": t.design_grade,
                     "wall_length_m": t.wall_length_m, "decks": [d.ref for d in t.decks],
                     "replaced_ways": list(t.replaced_ways), "notes": list(t.notes),
                     "width_m": t.hull_width_m, "depth_m": t.depth_m, "clipped_by": t.clipped_by,
                     "top_ground_z": t.top_ground_z, "profile": list(t.profile),
                     "mouth_ll": ll(t.axis[0]), "top_ll": ll(t.axis[-1]),
                     "trench_outside_max_m": t.trench_outside_max_m}
                    for t in tunnels],
        # RULINGS 2026-09-08b/c: the door wells and sunken roads read
        "door_wells": [{"id": w.id, "resource": w.resource, "objects": list(w.objects),
                        "sill_z": w.sill_z, "ground_z": w.ground_z, "depth_m": w.depth_m,
                        "sill_width_m": w.sill_width_m, "plate_out_m": w.plate_out_m,
                        "well_out_m": w.well_out_m, "plate_cover": w.plate_cover,
                        "sill_ll": ll(w.sill_mid),
                        "notes": list(w.notes)} for w in wells],
        "door_refused": list(dstats.refused),
        "door_stats": {k: v for k, v in _dc.asdict(dstats).items() if not isinstance(v, list)},
        "sunken_roads": [{"id": r.id, "resource": r.resource, "objects": list(r.objects),
                          "floor_z": r.floor_z, "mouth_dem_z": r.mouth_dem_z, "depth_m": r.depth_m,
                          "top_z": r.top_z, "top_ground_z": r.top_ground_z, "length_m": r.length_m,
                          "width_m": r.width_m,
                          "cover": r.cover, "cut_ll": ll(r.axis[0]), "top_ll": ll(r.axis[-1]),
                          "profile": list(r.profile), "notes": list(r.notes)} for r in roads],
        "sunken_refused": list(rstats.refused),
        "sunken_stats": {k: v for k, v in _dc.asdict(rstats).items() if not isinstance(v, list)},
        # RULINGS 2026-09-08m/08n Law C: the wall corridors read (the inventory)
        "wall_corridors": [{"id": w.id, "resource": w.resource, "objects": list(w.objects),
                            "family": w.family, "cls": w.cls, "ends": w.ends,
                            "length_m": w.length_m, "width_m": w.width_m,
                            "floor_z": w.floor_z, "floor_min_z": min(w.floors),
                            "floor_max_z": max(w.floors), "mouth_dem_z": w.mouth_dem_z,
                            "depth_m": w.depth_m, "headroom_m": w.headroom_m,
                            "max_authored_grade": w.max_authored_grade,
                            "mouth_ll": ll(w.axis[0]), "far_ll": ll(w.axis[-1]),
                            "axis_ll": [ll(p) for p in w.axis],
                            "trench_ll": [ll(p) for p in w.trench.exterior.coords]
                            if w.trench.geom_type == "Polygon" else [],
                            "profile": list(w.profile), "sibling": w.sibling,
                            "notes": list(w.notes)} for w in walls_c],
        "wall_corridor_refused": list(wstats.refused),
        # RULINGS 2026-09-10z: (a) authored depth / (b'') the mouth opens
        # onto groundside — the verdict and witness per candidate
        "wall_corridor_admission": list(wstats.admission),
        # RULINGS 2026-09-10ab: the two round-4 discriminators MEASURED
        # per candidate (floor vs the mouth road's level; the floor slab)
        "wall_corridor_floor_probe": list(wstats.floor_probe),
        # RULINGS 2026-09-10af: the NARROW-CUT reading per candidate
        "wall_corridor_narrow_cut": list(wstats.narrow_cut),
        "wall_corridor_stats": {k: v for k, v in _dc.asdict(wstats).items()
                                if not isinstance(v, list)},
        "tunnel_refused": list(sstats.refused),
        "structure_stats": {k: v for k, v in _dc.asdict(sstats).items()
                            if not isinstance(v, list)},
        "basins": [{"id": b.id, "objects": list(b.objects), "floor_z": b.floor_z,
                    "rim_estimate_m": b.rim_estimate_m, "area_m2": b.area_m2, "kind": b.kind,
                    "covered_fraction": b.covered_fraction, "site_ll": list(b.anchor_ll),
                    "notes": list(b.notes)} for b in basins],
        "basin_refused": list(bstats.refused),
        "cells_cut": {"structures": sstats.cells_cut, "basins": bstats.cells_cut},
    }


def _kml_ring(pts) -> str:
    return " ".join(f"{lo:.7f},{la:.7f},0" for la, lo in pts)


def write_kml(rec: dict, path: Path) -> None:
    """The structure readings as KML placemarks for the owner's read
    (RULINGS 2026-09-08n: every wall-corridor candidate by class with its
    widths, depths, grades and mouths; the other structures beside)."""
    from xml.sax.saxutils import escape
    styles = {"level": "ff00ff00", "bay": "ff00ffff", "garage_ramp": "ffff00ff",
              "object": "ffffff00", "door": "ff0088ff", "sunken_road": "ff8800ff",
              "basin": "ffff8800", "refused": "ff0000ff"}
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
           f"<name>{escape(rec['icao'])} structure inventory</name>"]
    for k, colour in styles.items():
        out.append(f'<Style id="{k}"><LineStyle><color>{colour}</color><width>3</width></LineStyle>'
                   f'<PolyStyle><color>66{colour[2:]}</color></PolyStyle></Style>')

    def folder(name: str, items: list[str]) -> None:
        if items:
            out.append(f"<Folder><name>{escape(name)}</name>" + "".join(items) + "</Folder>")

    def placemark(name: str, desc: str, style: str, ring=None, line=None, point=None) -> str:
        geo = ""
        if ring:
            geo += (f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{_kml_ring(ring)}"
                    f"</coordinates></LinearRing></outerBoundaryIs></Polygon>")
        if line:
            geo += f"<LineString><coordinates>{_kml_ring(line)}</coordinates></LineString>"
        if point:
            geo += f"<Point><coordinates>{_kml_ring([point])}</coordinates></Point>"
        if ring or line:
            geo = f"<MultiGeometry>{geo}</MultiGeometry>" if (ring and line) or point else geo
        return (f"<Placemark><name>{escape(name)}</name><description>{escape(desc)}</description>"
                f"<styleUrl>#{style}</styleUrl>{geo}</Placemark>")
    wc_items = []
    for w in rec["wall_corridors"]:
        desc = (f"class {w['cls']}; ends {w['ends']}; length {w['length_m']:.1f} m; width "
                f"{w['width_m']:.1f} m; floor {w['floor_min_z']:.2f}..{w['floor_max_z']:.2f} m "
                f"(ground {w['mouth_dem_z']:.2f}, depth {w['depth_m']:.2f} m); authored grade "
                f"{100.0 * w['max_authored_grade']:.1f} %; headroom {w['headroom_m']}; objects "
                f"{', '.join(o.split('/')[-1] for o in w['objects'])}; " + "; ".join(w["notes"]))
        wc_items.append(placemark(f"{w['cls']}: {w['id']}", desc, w["cls"], ring=w["trench_ll"],
                                  line=w["axis_ll"], point=w["mouth_ll"]))
    folder("wall corridors (Law C)", wc_items)
    import re as _re

    def site_of(text: str):
        m = _re.search(r"at (-?\d+\.\d+),(-?\d+\.\d+)", text)
        return (float(m.group(1)), float(m.group(2))) if m else None
    folder("wall corridors refused", [placemark(f"refused {i}", r, "refused", point=site_of(r))
                                      for i, r in enumerate(rec["wall_corridor_refused"])])
    folder("tunnels refused", [placemark(f"tunnel refused {i}", r, "refused")
                               for i, r in enumerate(rec["tunnel_refused"])])
    folder("thin-plate wall objects (§33 (2))",
           [placemark(f"{p['kind']}: {p['id']}",
                      f"{p['length_m']:.1f} x {p['width_m']:.1f} m, solids span "
                      f"{p['span_m']:.2f} m, top_y {p['top_y_m']:+.2f} "
                      f"(absolute {p['top_z']}); bores {p['bore_ways']}; bridges "
                      f"{p['bridge_ways']}; " + "; ".join(p["notes"]), "object",
                      ring=p["plan_ll"], line=[p["end0_ll"], p["end1_ll"]],
                      point=p["end0_ll"]) for p in rec["plates"]])
    folder("tunnel objects refused (§33 (1): every screened resource)",
           [placemark(f"refused {i}", r, "refused", point=site_of(r))
            for i, r in enumerate(rec["corridor_refused"])])
    folder("thin plates refused (§33 (1))",
           [placemark(f"plate refused {i}", r, "refused", point=site_of(r))
            for i, r in enumerate(rec["plate_refused"])])
    folder("mouths taken by a wall object (§33 (2))",
           [placemark(f"plate mouth {i}", r, "object") for i, r in enumerate(rec["plate_mouths"])])
    folder("mouth crest from the approach (§33 (3))",
           [placemark(f"crest {i}", r, "object") for i, r in enumerate(rec["crest_from_approach"])])
    folder("tunnel wall objects", [placemark(c["id"], f"{c['mouth_kind']} {c['ends']} depth "
                                             f"{c['depth_m']:.2f} floor {c['floor_z']:.2f}; "
                                             + "; ".join(c["notes"]), "object",
                                             line=[c["mouth_ll"], c["far_ll"]], point=c["mouth_ll"])
                                   for c in rec["corridors"]])
    folder("tunnels built", [placemark(t["id"], f"{t['source']} mouth_z {t['mouth_z']:.2f} top_s "
                                       f"{t['top_s']:.1f} grade {100.0 * t['design_grade']:.2f} % "
                                       f"clipped '{t['clipped_by']}'; " + "; ".join(t["notes"]),
                                       "object" if t["source"] == "object" else t["source"]
                                       if t["source"] in styles else "level",
                                       line=[t["mouth_ll"], t["top_ll"]], point=t["mouth_ll"])
                             for t in rec["tunnels"]])
    folder("door wells", [placemark(w["id"], f"sill {w['sill_z']:.2f} width {w['sill_width_m']:.1f}",
                                    "door", point=w["sill_ll"]) for w in rec["door_wells"]])
    folder("sunken roads", [placemark(r["id"], f"cut {r['floor_z']:.2f} top {r['top_z']:.2f}",
                                      "sunken_road", line=[r["cut_ll"], r["top_ll"]])
                            for r in rec["sunken_roads"]])
    folder("basins", [placemark(b["id"], f"{b['kind']} floor {b['floor_z']:.2f} area {b['area_m2']:.0f}",
                                "basin", point=tuple(b["site_ll"])) for b in rec["basins"]])
    out.append("</Document></kml>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items()))


if __name__ == "__main__":
    sys.exit(main())
