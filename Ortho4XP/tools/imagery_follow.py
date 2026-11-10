#!/usr/bin/env python3
"""imagery_follow.py: run the on-demand imagery follow job from Terminal
(#1992 P3b), before the apps have a switch for it (P4).

A shell over the engine command ``imagery_follow_start`` /
``imagery_follow_stop`` (``src/o4_engine/imagery_commands.py``): it rescans
the named on-demand tile folders into the index, follows X-Plane's camera
through its Web API, fetches finer imagery tiers ahead of it and prints
one status line every ``--every`` seconds, until ``--minutes`` or Ctrl-C.
X-Plane must be running with the tile's pack installed.  After a spawn
or jump whose imagery missed X-Plane's flight-start window the job asks
X-Plane to reload its scenery, once (#1992 P5); ``--no-reload`` never does.

    cd Ortho4XP && venv/bin/python tools/imagery_follow.py \\
        --tile-dir "Tiles/zOrtho4XP_+60-136" --minutes 60

The tile folder's name carries its tile (``zOrtho4XP_+60-136``); a folder
named otherwise takes ``--tile +60-136``.  Swaps are logged in
``<data root>/logs/imagery_on_demand.log``.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

from o4_engine import imagery_commands as CMDS  # noqa: E402

_TILE = re.compile(r"([+-]\d{2})([+-]\d{3})")


def tile_of(folder: str, tile: str = "") -> tuple[int, int]:
    """``(lat, lon)`` from ``--tile`` or the folder's own name."""
    found = _TILE.search(tile or os.path.basename(os.path.normpath(folder)))
    if not found:
        raise SystemExit(f"cannot tell the tile of {folder!r}: pass --tile")
    return int(found.group(1)), int(found.group(2))


def line(event) -> str:
    """One status line of an ``ImageryFollowStatus``."""
    buffer = "-" if event.buffer_s < 0 else f"{event.buffer_s:.0f}s"
    text = (f"{time.strftime('%H:%M:%S')} {event.state:<9} "
            f"{event.speed_ms * 1.944:4.0f} kt  queued {event.queued:3d}  "
            f"in flight {event.in_flight}/{event.slots}  buffer {buffer:>5}  "
            f"sharp {event.sharp}/{event.textures}  landed {event.landed}  "
            f"late {event.late}  failed {event.failed}  "
            f"flight loads {event.flight_loads}  jumps {event.jumps}  "
            f"reloads {event.reloads}")
    return text + (f"  ({event.reason})" if event.reason else "")


def main(argv=None) -> int:
    # The console is UTF-8 before the parser can print (#171, #125).
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tile-dir", action="append", required=True,
                        help="an on-demand tile's build folder (repeatable)")
    parser.add_argument("--tile", default="",
                        help="e.g. +60-136, when one folder's name lacks it")
    parser.add_argument("--port", type=int, default=8086,
                        help="X-Plane Web API port (default 8086)")
    parser.add_argument("--lead", type=float, default=None,
                        help="seconds a tier starts before its crossing")
    parser.add_argument("--no-reload", action="store_true",
                        help="never ask X-Plane to reload its scenery")
    parser.add_argument("--minutes", type=float, default=240.0)
    parser.add_argument("--every", type=float, default=10.0,
                        help="seconds between printed status lines")
    a = parser.parse_args(argv)
    tiles = [[os.path.abspath(d), *tile_of(d, a.tile)] for d in a.tile_dir]
    from o4_engine.jsonl import _initialize_pipeline_registries
    _initialize_pipeline_registries()
    latest, guard = {}, threading.Lock()

    def emit(event) -> None:
        with guard:
            latest["event"] = event

    print(CMDS.start_imagery_follow(emit, port=a.port, lead_s=a.lead,
                                    tiles=tiles, reload=not a.no_reload),
          flush=True)
    deadline = time.time() + a.minutes * 60
    try:
        while time.time() < deadline:
            time.sleep(a.every)
            with guard:
                event = latest.get("event")
            if event is not None:
                print(line(event), flush=True)
        print("TIMED_OUT: --minutes reached", flush=True)
    except KeyboardInterrupt:
        pass
    print(CMDS.stop_imagery_follow(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
