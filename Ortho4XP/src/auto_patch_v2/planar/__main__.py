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
    return Inputs(xplane_root=xplane_root, cifp_dir=cifp_dir,
                  osm_root=str(root / "OSM_data"),
                  elevation_root=str(root / "Elevation_data"),
                  mod_cache_root=str(root / "Airport_mod_cache"),
                  feather_m=feather_m, dem_frame=dem_frame,
                  allow_degraded_dem=allow_degraded_dem)


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


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items()))


if __name__ == "__main__":
    sys.exit(main())
