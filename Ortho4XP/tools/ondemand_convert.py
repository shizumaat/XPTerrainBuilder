#!/usr/bin/env python3
"""ondemand_convert.py: convert the ortho tiles a Custom Scenery folder
already has to on-demand form (#1992 P1c), from Terminal.

A shell over ``src/o4_engine/imagery_convert.py`` (engine command
``imagery_ondemand_convert``).  Each ``zOrtho4XP_<tile>`` entry (a symlink
onto a library volume, or a local folder) gets a local copy with
placeholder textures cut from its own full DDS, the DSF 7z-compressed and
no build intermediates; the full textures stay where they are and the
follow job lands from them while they are mounted.

    cd Ortho4XP
    # sizing of every tile (reads headers only), placeholder widths compared
    venv/bin/python tools/ondemand_convert.py dry-run --px 256,512
    # one tile into a scratch root, the Custom Scenery entry untouched
    venv/bin/python tools/ondemand_convert.py convert --tiles zOrtho4XP_+00+029 \\
        --local-root /tmp/scratch --no-register
    # all tiles, each entry swapped for its copy (X-Plane must be closed)
    venv/bin/python tools/ondemand_convert.py convert --swap
    # undo one swap
    venv/bin/python tools/ondemand_convert.py revert zOrtho4XP_+00+029

Nothing on the source is ever written.  ``scenery_packs.ini`` is never
edited (an entry keeps its name, so its order and enabled state hold).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))


def _gb(value: float) -> str:
    return f"{value / 1e9:,.1f} GB"


def _custom_scenery(given: str) -> str:
    """``--custom-scenery``, else the ``custom_scenery_dir`` setting."""
    found = given
    if not found:
        from o4_engine.storage_redundant import _custom_scenery_dir
        found = _custom_scenery_dir()
    if not found or not os.path.isdir(found):
        raise SystemExit("pass --custom-scenery (no custom_scenery_dir set)")
    return found


def print_dry_run(result: dict, widths) -> None:
    """The dry run's totals table."""
    t = result["totals"]
    print(f"entries {t['entries']}  {t['by_kind']}  enabled {t['enabled']}")
    print(f"textures {t['textures']:,}  full source textures "
          f"{_gb(t['source_texture_bytes'])}  copied whole (no mip) "
          f"{t['whole_copies']}")
    print(f"DSF raw {_gb(t['dsf_bytes'])}  ->  7z est "
          f"{_gb(t['dsf_compressed_bytes_est'])} (ratio {t['dsf_ratio']} over "
          f"{t['dsf_ratio_sample']} DSFs; {t['dsf_already_7z']} already 7z)")
    print(f"copied as is (.ter, borders, cfg) {_gb(t['copy_bytes'])}  "
          f"left out (intermediates, .bak) {_gb(t['skipped_bytes'])}")
    for px in widths:
        print(f"  {px:4d} px: placeholders {_gb(t[f'placeholder_bytes_{px}'])}"
              f"  total local {_gb(t[f'total_bytes_{px}_est'])}")
    print(f"dry run took {t['seconds']} s")


def main(argv=None) -> int:
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--custom-scenery", default="",
                        help="X-Plane's Custom Scenery folder (default: "
                             "the custom_scenery_dir setting)")
    parser.add_argument("--data-root", default="",
                        help="engine data root (index, placeholder store)")
    parser.add_argument("--json", default="", help="write the result here")
    sub = parser.add_subparsers(dest="action", required=True)
    dry = sub.add_parser("dry-run", help="sizing only, writes nothing")
    dry.add_argument("--tiles", nargs="*", default=None)
    dry.add_argument("--px", default="512",
                     help="placeholder widths to size, comma separated")
    dry.add_argument("--workers", type=int, default=8)
    dry.add_argument("--sample-dsf", type=int, default=6)
    run = sub.add_parser("convert", help="write the on-demand copies")
    run.add_argument("--tiles", nargs="*", default=None)
    run.add_argument("--px", type=int, default=512)
    run.add_argument("--local-root", default="",
                     help="where copies live (default: in place of the entry)")
    run.add_argument("--work-dir", default="")
    run.add_argument("--swap", action="store_true",
                     help="exchange each entry for its copy (atomic)")
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--threads", type=int, default=4)
    run.add_argument("--no-register", action="store_true",
                     help="do not write index rows or the placeholder store")
    back = sub.add_parser("revert", help="swap an entry back")
    back.add_argument("name")
    back.add_argument("--work-dir", default="")
    args = parser.parse_args(argv)
    if args.data_root:
        import O4_File_Names as FNAMES
        FNAMES.set_data_root(args.data_root)
    from o4_engine import imagery_convert as CONVERT
    scenery = _custom_scenery(args.custom_scenery)
    if args.action == "dry-run":
        widths = tuple(int(p) for p in args.px.split(","))
        result = CONVERT.dry_run(scenery, args.tiles, widths=widths,
                                 workers=args.workers,
                                 sample_dsf=args.sample_dsf)
        print_dry_run(result, widths)
    elif args.action == "convert":
        result = CONVERT.convert(scenery, args.tiles, px=args.px,
                                 local_root=args.local_root or None,
                                 swap=args.swap, work_dir=args.work_dir or None,
                                 workers=args.workers, threads=args.threads,
                                 register=not args.no_register)
        for row in result["rows"]:
            print(f"{row['name']}: {row['status']}  "
                  f"{_gb(row.get('bytes_written', 0))}  "
                  f"{row.get('seconds', 0)} s  {row.get('problems') or ''}")
        print(f"total {_gb(result['bytes_written'])} in {result['seconds']} s")
    else:
        result = CONVERT.revert(scenery, args.name,
                                work_dir=args.work_dir or None)
        print(json.dumps(result, indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
