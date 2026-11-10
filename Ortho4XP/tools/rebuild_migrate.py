#!/usr/bin/env python3
"""rebuild_migrate.py: move the rebuild data old builds left in installed
tile folders into the data folder's rebuild cache (owner RULINGS
2026-11-10d (4)), from Terminal.

A shell over ``src/O4_Rebuild_Cache.py`` (engine command
``rebuild_migrate``).  Moves only, never deletes; a file the cache
already holds stays where it is; a move from another volume stops while
it would leave the data folder's volume under 30 GB free.

    cd Ortho4XP
    # what would move from every tile X-Plane has installed (stat only)
    venv/bin/python tools/rebuild_migrate.py --dry-run "<X-Plane>/Custom Scenery"
    # the data folder's own Tiles
    venv/bin/python tools/rebuild_migrate.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Rebuild_Cache as REBUILD  # noqa: E402


def main(argv=None) -> int:
    import argparse

    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    parser = argparse.ArgumentParser(
        description="Move tile folders' rebuild data (Data*.mesh/.node/"
                    ".poly/.alt, step records, cfg backups) into the data "
                    "folder's rebuild cache (RULINGS 2026-11-10d). Moves "
                    "only; never deletes.")
    parser.add_argument("folders", nargs="*",
                        help="tiles folders or tile folders (default: the "
                             "data folder's Tiles)")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would move; move nothing")
    args = parser.parse_args(argv)
    out = REBUILD.rebuild_migrate(args.folders, args.dry_run)
    verb = "would move" if args.dry_run else "moved"
    for folder in out["folders"]:
        for row in folder["tiles"]:
            print("%s  %s %d file(s), %.1f MB -> %s%s%s" % (
                row["tile"], verb, len(row["moved"]), row["bytes"] / 1e6,
                row["cache"] or FNAMES.rebuild_root(),
                ("  (kept: %s)" % ", ".join(row["kept"]))
                if row["kept"] else "",
                ("  (no room: %d file(s))" % len(row["no_room"]))
                if row["no_room"] else ""))
    print("%s %d file(s), %.1f GB (%.1f GB from another volume); %d "
          "file(s) left for lack of room; %.1f GB free on the cache's "
          "volume" % (verb, out["moved_files"], out["bytes"] / 1e9,
                      out["copied_bytes"] / 1e9, out["no_room_files"],
                      out["free_bytes"] / 1e9))
    return 0


if __name__ == "__main__":
    sys.exit(main())
