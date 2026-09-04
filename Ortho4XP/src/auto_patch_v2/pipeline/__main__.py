"""``venv/bin/python -m auto_patch_v2 build ICAO --out DIR`` — the v2
build: load → classify → planar → constraints → solve → emit → verify,
counts and per-stage wall time on stdout, ``<ICAO>.report.json`` in DIR.
Inputs default to the engine tree's mounts and its ``Ortho4XP.cfg``
install paths exactly as ``auto_patch_v2.planar`` resolves them (M1); no
environment reads.
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
    args = ap.parse_args(argv)
    os.chdir(ENGINE_DIR)   # the core's resource/data contract (production DEM frame)
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
