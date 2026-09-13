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


def _principal_axis(pts):
    """``(a, b, unit, length, width)`` — the same fit
    ``auto_patch_v2.constraints.geometry.principal_axis`` makes (largest-
    variance axis, its extreme stations, the transverse EXTENT)."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = syy = sxy = 0.0
    for x, y in pts:
        dx, dy = x - cx, y - cy
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    tr = sxx + syy
    lam = 0.5 * tr + math.sqrt(max(0.0, (0.5 * tr) ** 2 - (sxx * syy - sxy * sxy)))
    ux, uy = (lam - syy, sxy) if abs(sxy) > 1e-9 else \
             ((1.0, 0.0) if sxx >= syy else (0.0, 1.0))
    norm = math.hypot(ux, uy)
    ux, uy = ux / norm, uy / norm
    along = [(x - cx) * ux + (y - cy) * uy for x, y in pts]
    across = [-(x - cx) * uy + (y - cy) * ux for x, y in pts]
    s0, s1 = min(along), max(along)
    return ((cx + s0 * ux, cy + s0 * uy), (cx + s1 * ux, cy + s1 * uy),
            (ux, uy), s1 - s0, max(across) - min(across))


def _nearest_on_segment(px, py, ax, ay, bx, by):
    """``(x, y, wa, wb)`` — the nearest point of the SEGMENT (``t``
    clamped) and the two endpoint weights that interpolate it."""
    ex, ey = bx - ax, by - ay
    l2 = ex * ex + ey * ey
    if l2 < 1e-9:
        return ax, ay, 1.0, 0.0
    t = ((px - ax) * ex + (py - ay) * ey) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return ax + t * ex, ay + t * ey, 1.0 - t, t


def corners(patch, icao):
    """THE RUNWAY-END CORNER QUADRANT of a shipped patch (§35, RULINGS
    2026-09-13q item 1), per runway end and per SIDE — twelve rows for a
    three-runway airport.

    The quadrant is the graded-strip vertices BEYOND an end, LATERAL of
    the runway's own half-width, inside the zone-2 half-width and inside
    ``end_skirt.corridor_length_m``.  Each is priced the way §35 states
    the law: the step to the NEAREST POINT of the runway's end edge over
    the true plan distance ``d``, against
    ``end_skirt.max_down_grade × d + q`` (``q`` the strip-edge instrument
    allowance every end-skirt row carries).

    The runway axis is fitted from the patch's OWN runway rings, so there
    is no baked end table here either (module docstring); the ruleset is
    the airport's, so an FAA airport is judged under FAA law.
    """
    from check_grade import _parse_osm
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import zone2_half_width_m
    from auto_patch_v2.constraints.strips import runway_code_number

    law = Law.for_airport(icao)
    cap = law.ruleset.end_skirt.max_down_grade
    corridor = law.ruleset.end_skirt.corridor_length_m
    q = (law.tables.emit.instrument.strip_edge_noise_m
         - law.tables.emit.materiality.elevation_m)
    nodes, ways = _parse_osm(Path(patch))
    lat0 = sum(v[0] for v in nodes.values()) / len(nodes)
    lon0 = sum(v[1] for v in nodes.values()) / len(nodes)
    k = math.pi / 180.0 * R_EARTH
    kx = k * math.cos(math.radians(lat0))

    def xy(nid):
        la, lo = nodes[nid]
        return ((lo - lon0) * kx, (la - lat0) * k)

    runways, strip, z = {}, set(), {}
    for way in ways:
        for nid, elevation in zip(way.nids, way.elevs):
            if elevation is not None:
                z[nid] = float(elevation)
        if way.role == "runway":
            runways.setdefault(way.ref or way.wid, set()).update(way.nids)
        elif way.role == "graded_strip":
            strip.update(way.nids)
    rows = []
    for ref, ids in sorted(runways.items()):
        pts = [xy(n) for n in ids]
        if len(pts) < 3:
            continue
        a, _b, (ux, uy), length, width = _principal_axis(pts)
        code = runway_code_number(length, law)
        half2 = zone2_half_width_m(law, "runway", code, None) or 0.0
        end_len = (corridor.value(code, None) if corridor is not None else 0.0) or 0.0
        for end, s_end in ((1, 0.0), (2, length)):
            edge = [n for n in ids if n in z
                    and abs(((xy(n)[0] - a[0]) * ux + (xy(n)[1] - a[1]) * uy)
                            - s_end) <= 2.0]
            edge.sort(key=lambda n: -(xy(n)[0] * -uy + xy(n)[1] * ux))
            pairs = [(edge[i], edge[i + 1]) for i in range(len(edge) - 1)]
            if not pairs:
                continue
            for side in (-1, 1):
                pop = over = 0
                worst = None
                for n in strip:
                    if n not in z:
                        continue
                    x, y = xy(n)
                    s = (x - a[0]) * ux + (y - a[1]) * uy
                    off = -(x - a[0]) * uy + (y - a[1]) * ux
                    beyond = (s_end - s) if end == 1 else (s - s_end)
                    if not (1.0 <= beyond <= end_len):
                        continue
                    if not (width / 2.0 < abs(off) <= half2):
                        continue
                    if (1 if off >= 0.0 else -1) != side:
                        continue
                    pop += 1
                    best = None
                    for p_, r_ in pairs:
                        (px, py), (rx, ry) = xy(p_), xy(r_)
                        nx, ny, wa, wb = _nearest_on_segment(x, y, px, py, rx, ry)
                        d = math.hypot(x - nx, y - ny)
                        if best is None or d < best[0]:
                            best = (d, z[p_] * wa + z[r_] * wb)
                    d, z_edge = best
                    step = abs(z[n] - z_edge)
                    excess = step - (cap * d + q)
                    if excess > 0.0:
                        over += 1
                    if worst is None or excess > worst["excess_m"]:
                        worst = {"node": n, "lat": nodes[n][0], "lon": nodes[n][1],
                                 "step_m": round(step, 3), "d_m": round(d, 2),
                                 "bound_m": round(cap * d + q, 3),
                                 "excess_m": round(excess, 3),
                                 "z_m": round(z[n], 2), "edge_z_m": round(z_edge, 2)}
                rows.append({"runway": ref, "end": end,
                             "side": "L" if side < 0 else "R",
                             "population": pop, "over_bound": over,
                             "worst": worst})
    return {"patch": os.fspath(patch), "icao": icao,
            "ruleset": law.ruleset_key, "max_down_grade": cap,
            "instrument_allowance_m": round(q, 3), "corners": rows,
            "total_over_bound": sum(r["over_bound"] for r in rows)}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("patch")
    parser.add_argument("--corners", metavar="ICAO", default=None,
                        help="report the §35 runway-end CORNER quadrant of "
                             "this patch under ICAO's ruleset instead of the "
                             "--end level read (no --end needed: the axis is "
                             "fitted from the patch's own runway rings)")
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
    if args.corners:
        out = corners(args.patch, args.corners)
        print("=== RUNWAY-END CORNERS (§35)  %s" % out["patch"])
        print("    %s | ruleset %s | cap %.3f | instrument allowance %.2f m"
              % (out["icao"], out["ruleset"], out["max_down_grade"],
                 out["instrument_allowance_m"]))
        for row in out["corners"]:
            w = row["worst"]
            head = ("  %-9s end%d%s  pop %4d  over %3d"
                    % (row["runway"], row["end"], row["side"],
                       row["population"], row["over_bound"]))
            if w is None:
                print(head + "   (no corner vertex)")
            else:
                print(head + ("   worst %6.2f m over %6.2f m (bound %5.2f, "
                              "excess %+6.2f)  %s %.7f,%.7f z=%.2f edge=%.2f"
                              % (w["step_m"], w["d_m"], w["bound_m"],
                                 w["excess_m"], w["node"], w["lat"], w["lon"],
                                 w["z_m"], w["edge_z_m"])))
        print("  TOTAL corner vertices over their own bound: %d"
              % out["total_over_bound"])
        if args.json:
            Path(args.json).write_text(json.dumps(out, indent=1))
            print("JSON -> %s" % args.json)
        return 0
    if not args.end:
        parser.error("give at least one --end NAME LAT LON, or --corners ICAO")
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
