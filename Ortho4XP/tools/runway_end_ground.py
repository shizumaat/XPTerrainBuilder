#!/usr/bin/env python3
"""THE GROUND OFF A RUNWAY END, as the patch emitted it.

The acceptance question rounds 17 / 17b / 17c all ask: "how much of the
graded ground within N metres of a runway end is AT OR BELOW a level it
has no business being at?".  At VHHH that population was 1,681 vertices
at or below 0 m — the runway-end canyons — and the round's target is
~0.

    venv/bin/python tools/runway_end_ground.py PATCH.osm \
        [--end ICAO_END LAT LON ...] [--radius-m 500] [--level-m 0.0] \
        [--roles graded_strip,junction,service_junction,apron] [--json OUT]

IT MEASURES NOTHING A LAW INSTRUMENT OWNS.  This is not a grade law and
it is not a census family: it reports EMITTED ALTITUDES near named
points.  The patch is read with the harness library's own parser
(``tools/check_grade._parse_osm``), so this tool and the census read one
geometry — a private reader is the census-wrapper defect.

ROLE SCOPE is the SURFACE roles: ``tunnel_trench`` and the rest of the
below-grade family are deliberately absent, because their below-grade
population is LAWFUL and counting it would drown the signal.

The runway ends come from ``--end`` (repeatable).  There is no default
list: an end table baked into an instrument is a second source of truth
about where a runway is.
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

#: The SURFACE roles the question is about (below-grade families excluded
#: on purpose — see the module docstring).
DEFAULT_ROLES = ("graded_strip", "junction", "service_junction", "apron")


def metres(lat0, lon0, lat1, lon1):
    """Local flat-earth distance in metres — the same small-angle form
    every acceptance read in this repo uses at airport scale."""
    return math.hypot((lat1 - lat0) * math.pi / 180.0 * R_EARTH,
                      (lon1 - lon0) * math.pi / 180.0 * R_EARTH
                      * math.cos(math.radians(lat0)))


def measure(patch, ends, radius_m=500.0, level_m=0.0, roles=DEFAULT_ROLES):
    """``{"ends": [...], "total_at_or_below": n, ...}``."""
    from check_grade import _parse_osm
    nodes, ways = _parse_osm(Path(patch))
    roles = tuple(roles)
    rows = []
    total = 0
    for (name, lat, lon) in ends:
        population = []
        for way in ways:
            if way.role not in roles:
                continue
            for nid, elevation in zip(way.nids, way.elevs):
                if elevation is None:
                    continue
                node_lat, node_lon = nodes[nid]
                d = metres(lat, lon, node_lat, node_lon)
                if d <= radius_m:
                    population.append((float(elevation), way.role, d))
        under = [p for p in population if p[0] <= level_m]
        total += len(under)
        worst = min(population) if population else None
        rows.append({
            "end": name,
            "n": len(population),
            "at_or_below": len(under),
            "min_m": (None if worst is None else round(worst[0], 3)),
            "min_role": (None if worst is None else worst[1]),
            "min_dist_m": (None if worst is None else round(worst[2], 1)),
        })
    return {"patch": os.fspath(patch),
            "radius_m": float(radius_m),
            "level_m": float(level_m),
            "roles": list(roles),
            "ends": rows,
            "total_at_or_below": total}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patch")
    parser.add_argument("--end", nargs=3, action="append", default=[],
                        metavar=("NAME", "LAT", "LON"),
                        help="a runway end (repeatable); REQUIRED — an end "
                             "table baked into an instrument would be a "
                             "second source of truth about the runway")
    parser.add_argument("--radius-m", type=float, default=500.0)
    parser.add_argument("--level-m", type=float, default=0.0)
    parser.add_argument("--roles", default=",".join(DEFAULT_ROLES))
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    if not args.end:
        parser.error("give at least one --end NAME LAT LON")
    ends = [(name, float(lat), float(lon))
            for (name, lat, lon) in args.end]
    roles = tuple(r.strip() for r in args.roles.split(",") if r.strip())
    out = measure(args.patch, ends, args.radius_m, args.level_m, roles)
    print("=== RUNWAY-END GROUND  %s" % out["patch"])
    print("    roles %s | radius %.0f m | level %+.2f m"
          % (",".join(out["roles"]), out["radius_m"], out["level_m"]))
    for row in out["ends"]:
        print("  %-5s n=%5d  <=%+.2f m: %5d  min %8s%s"
              % (row["end"], row["n"], out["level_m"], row["at_or_below"],
                 ("%.2f" % row["min_m"]) if row["min_m"] is not None else "-",
                 ("   (role %s at %.0f m)" % (row["min_role"],
                                              row["min_dist_m"]))
                 if row["min_role"] else ""))
    print("  TOTAL <=%+.2f m within %.0f m of an end (%d role(s)): %d"
          % (out["level_m"], out["radius_m"], len(out["roles"]),
             out["total_at_or_below"]))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1))
        print("JSON -> %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
