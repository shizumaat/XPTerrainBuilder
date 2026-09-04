"""``venv/bin/python -m auto_patch_v2 build ICAO --out DIR`` — the v2
build: load → classify → planar → constraints → solve → emit → verify,
counts and per-stage wall time on stdout, ``<ICAO>.report.json`` in DIR.
Inputs default to the engine tree's mounts and its ``Ortho4XP.cfg``
install paths exactly as ``auto_patch_v2.planar`` resolves them (M1); no
environment reads.
"""
from __future__ import annotations

import argparse
import sys

from ..planar.__main__ import default_inputs
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
    b.add_argument("--no-verify", action="store_true")
    b.add_argument("--no-iis", action="store_true")
    b.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    inputs = default_inputs(args.xplane_root, args.cifp_dir, args.data_root,
                            args.feather_m)
    cfg = Config(options=Options(diagnose_iis=not args.no_iis,
                                 verbose=args.verbose),
                 verify=not args.no_verify, feather_m=args.feather_m)
    res = build(args.icao.upper(), inputs, args.out, cfg)
    return 0 if res.solution.status.value in ("optimal", "feasible") else 1


if __name__ == "__main__":
    sys.exit(main())
