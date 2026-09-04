"""``venv/bin/python -m auto_patch_v2 build ICAO --out DIR`` — the v2
build: load → classify → planar → constraints → solve → emit → verify,
counts and per-stage wall time on stdout, ``<ICAO>.report.json`` in DIR.
Inputs default to the engine tree's mounts and its ``Ortho4XP.cfg``
install paths exactly as ``auto_patch_v2.planar`` resolves them (M1); no
environment reads.

``python -m auto_patch_v2 explain ICAO --shape N [--patch P] | --at
LAT,LON`` (owner 2026-09-04j): the classification verdict at a shipped
patch's ``shapeID`` (default patch: the engine tree's
``Patches/<block>/<tile>/<ICAO>_auto.patch.osm``) or at a coordinate —
role, the evidence record, the source polygons under it with their own
records, the centrelines that touch it (``classify/explain.py``).
"""
from __future__ import annotations

import argparse
import os
import sys

from ..planar.__main__ import ENGINE_DIR, add_dem_frame_args, default_inputs
from ..law import Law
from ..solve import Options
from .build import Config, build


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="auto_patch_v2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build one airport's v2 patch")
    b.add_argument("icao")
    b.add_argument("--out", required=True)
    b.add_argument("--xplane-root")
    b.add_argument("--cifp-dir")
    b.add_argument("--data-root")
    b.add_argument("--feather-m", type=float, default=60.0)
    add_dem_frame_args(b)
    b.add_argument("--law-dir", help="an ALTERNATIVE law-table directory (a "
                   "labelled measurement arm; the shipped tables are law/)")
    b.add_argument("--no-verify", action="store_true")
    b.add_argument("--no-iis", action="store_true")
    b.add_argument("--verbose", action="store_true")
    e = sub.add_parser("explain", help="the classification verdict at a shapeID or coordinate")
    e.add_argument("icao")
    e.add_argument("--shape", type=int, help="shapeID of a way in the shipped patch")
    e.add_argument("--at", help="LAT,LON (WGS84)")
    e.add_argument("--patch", help="the patch to read --shape from (default: "
                   "Patches/<block>/<tile>/<ICAO>_auto.patch.osm in the engine tree)")
    e.add_argument("--xplane-root")
    e.add_argument("--cifp-dir")
    e.add_argument("--data-root")
    add_dem_frame_args(e)
    args = ap.parse_args(argv)
    os.chdir(ENGINE_DIR)   # the core's resource/data contract (production DEM frame)
    if args.cmd == "explain":
        return explain_main(args)
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            args.feather_m, args.dem_frame, args.allow_degraded_dem)
    cfg = Config(options=Options(diagnose_iis=not args.no_iis,
                                 verbose=args.verbose),
                 verify=not args.no_verify, feather_m=args.feather_m)
    law = Law.for_airport(args.icao.upper(), law_dir=args.law_dir) if args.law_dir else None
    with shared_repo_guard() as guard:
        res = build(args.icao.upper(), inputs, args.out, cfg, law)
    blocked = list(getattr(guard, "blocked", ()))
    if blocked:
        print(f"[{args.icao.upper()}] REFUSED: {len(blocked)} write(s) into the "
              f"shared data repo were blocked during the build: {blocked[:5]}")
        return 2
    return 0 if res.solution.status.value in ("optimal", "feasible") else 1


def explain_main(args) -> int:
    """``explain``: classify once (read-only, degraded DEM accepted — the
    verdict does not read elevations) and print the verdict."""
    from ..airport.load import load
    from ..classify import classify, load_rules
    from ..classify.evidence import build_evidence
    from ..classify.explain import explain_at, explain_polygon, render, shape_polygon
    if (args.shape is None) == (args.at is None):
        print("explain: exactly one of --shape N / --at LAT,LON")
        return 2
    icao = args.icao.upper()
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            60.0, args.dem_frame, True)
    law = Law.for_airport(icao)
    airport = load(icao, inputs, law)
    rules = load_rules()
    cl = classify(airport, law, rules)
    ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2)
    print(f"[{icao}] {len(cl.cells)} cells; sources: "
          + ", ".join(f"{k} {v}" for k, v in sorted(
              {c: sum(1 for r in cl.sources if r.cls == c) for c in ("strip", "lot", "open")}.items())))
    if args.at is not None:
        lat, lon = (float(v) for v in args.at.split(","))
        to_xy, _ = airport.frame.transformers()
        print(render(explain_at(to_xy(lon, lat), cl, ev, airport)))
        return 0
    patch = args.patch
    if patch is None:
        lat0, lon0 = airport.frame.origin
        import math
        blat, blon = int(math.floor(lat0)), int(math.floor(lon0))
        patch = str(ENGINE_DIR / "Patches" / f"{(blat // 10) * 10:+03d}{(blon // 10) * 10:+04d}"
                    / f"{blat:+03d}{blon:+04d}" / f"{icao}_auto.patch.osm")
    found = shape_polygon(patch, args.shape, airport)
    if found is None:
        print(f"explain: no way with shapeID={args.shape} and a role in {patch}")
        return 1
    poly, tags = found
    print(f"shape {args.shape} in {patch}: shipped role={tags.get('role')} "
          f"class={tags.get('class', '-')} ref={tags.get('ref')} area={poly.area:,.0f} m2")
    print(render(explain_polygon(poly, cl, ev, airport)))
    return 0


def shared_repo_guard():
    """THE shared-repo write guard (``tools/harness/shared_repo_guard.py``,
    the single implementation), armed in refuse mode around the build so
    the production DEM prelude can never write the corpus (RULINGS
    ``e9daef5``).  A tree without the harness (a packaged engine) runs
    unguarded — the guard is a lane instrument, and the pipeline reads no
    environment to find it."""
    harness = ENGINE_DIR / "tools" / "harness"
    if not (harness / "shared_repo_guard.py").is_file():
        import contextlib
        return contextlib.nullcontext()
    if str(harness) not in sys.path:
        sys.path.insert(0, str(harness))
    from shared_repo_guard import SharedRepoWriteGuard
    return SharedRepoWriteGuard(set(), str(ENGINE_DIR))


if __name__ == "__main__":
    sys.exit(main())
