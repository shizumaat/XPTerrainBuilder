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

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Self-contained and ahead of every
# other import because a tool's own ``--help`` carries the house spelling
# (``Δ``, ``ε``, ``≥``, ``→``) and a Windows console RAISES on those
# rather than mangling them.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

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

from auto_patch_v2.constraints.geometry import (                 # noqa: E402
    principal_axis as _principal_axis_law)

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
    """``(a, b, unit, length, width)`` — the ENGINE's own fit, adapted to
    this tool's tuple shape.

    It carried its own transcription of the largest-variance closed form
    until 2026-10-02.  Issue #190 made that fit insertion-invariant
    (convex-hull minimum-area rectangle), and a tool that must not "fit
    the runway differently from the law that priced it"
    (``tests/test_runway_end_corners.py``) cannot hold a second copy
    through a change of the fit — so it binds the law instead.
    ``None`` for a cloud with no two distinct points.
    """
    ax = _principal_axis_law(pts)
    if ax is None:
        return None
    a, b, width = ax
    length = math.dist(a, b)
    if length <= 0.0:
        return None
    return (a, b, ((b[0] - a[0]) / length, (b[1] - a[1]) / length),
            length, width)


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
    from auto_patch_v2.law.tables import runway_safety_area_length_m, zone2_half_width_m
    from auto_patch_v2.law.reference_code import runway_code_letter, runway_code_number

    law = Law.for_airport(icao)
    cap = law.ruleset.end_skirt.max_down_grade
    corridor = law.ruleset.end_skirt.corridor_length_m
    from auto_patch_v2.law.tables import end_profile_noise_m
    q = end_profile_noise_m(law)
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
        ax = _principal_axis(pts)
        if ax is None:
            continue
        a, _b, (ux, uy), length, width = ax
        code = runway_code_number(law, length)
        letter = runway_code_letter(law, width)
        half2 = zone2_half_width_m(law, "runway", code, letter) or 0.0
        end_len = runway_safety_area_length_m(law, code, letter)
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


def _axes_from_sidecar(patch):
    """``[(ref, (lat0, lon0), (lat1, lon1), width_m, code_number, code_letter,
    instrument)]``
    from the patch's own sidecar (``runway_axes`` + ``runway_caps``) — the
    build's axis, never a second fit."""
    from auto_patch_v2.verify.strips import published_instrument
    side = Path(str(patch) + ".axes.json")
    if not side.is_file():
        return None, None
    d = json.loads(side.read_text())
    caps = {c.get("ref"): c for c in d.get("runway_caps") or []}
    out = []
    for row in d.get("runway_axes") or []:
        ref, lat0, lon0, lat1, lon1, width = row[:6]    # [6:] the overruns
        c = caps.get(ref) or {}
        out.append((ref, (lat0, lon0), (lat1, lon1), float(width),
                    c.get("code_number"), c.get("code_letter"),
                    # RULINGS 2026-10-15k (3): the published instrument status
                    published_instrument([row], ref)))
    return out, str(d.get("ruleset") or "icao")


def profile(patch, corridor_m=8.0, law_dir=None):
    """THE END PROFILE (#620; owner RULINGS 2026-10-12q (1)): per runway
    end, the emitted NODES on the extended centre line (within
    ``corridor_m`` laterally) beyond the last runway-role node, by
    distance ``d``: altitude, role, the grade of each segment, and each
    node against the ruleset's :class:`law.tables.EndProfile` — how far
    it stands below the end (``fall``) against ``fall_m(d)`` or above it
    against ``rise_m(d)``.  ``break_m`` is where the strip's cap hands
    over to the skirt's.  Reports; prices no law and counts no defects
    (the census family is ``runway_end_skirt``)."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import runway_end_profile
    from check_grade import _parse_osm
    axes, ruleset = _axes_from_sidecar(patch)
    if not axes:
        raise SystemExit("no sidecar runway_axes beside %s" % patch)
    law = Law.load(ruleset=ruleset, law_dir=law_dir) if law_dir else Law.load(ruleset=ruleset)
    nodes, ways = _parse_osm(Path(patch))
    pts = {}
    for w in ways:
        for nid, e in zip(w.nids, w.elevs):
            if e is None or nid not in nodes:
                continue
            pts.setdefault(nid, (nodes[nid], float(e), set()))[2].add(w.role)
    out = []
    for ref, (la0, lo0), (la1, lo1), width, cn, cl, ins in axes:
        prof = runway_end_profile(law, cn, cl, ins)
        cos0 = math.cos(math.radians(la0))
        ux = (lo1 - lo0) * math.pi / 180.0 * R_EARTH * cos0
        uy = (la1 - la0) * math.pi / 180.0 * R_EARTH
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        st = []
        for nid, ((la, lo), z, roles) in pts.items():
            x = (lo - lo0) * math.pi / 180.0 * R_EARTH * cos0
            y = (la - la0) * math.pi / 180.0 * R_EARTH
            s, t = x * ux + y * uy, -x * uy + y * ux
            if abs(t) <= corridor_m:
                st.append((s, t, z, nid, roles, la, lo))
        rw = [p for p in st if "runway" in p[4]]
        if not rw:
            continue
        for end_name, sign, pav in ((ref.split("/")[0], -1.0, min(rw)[0]),
                                    (ref.split("/")[-1], 1.0, max(rw)[0])):
            z_end = [p for p in rw if abs(p[0] - pav) < 0.5]
            z_end = min(z_end, key=lambda p: abs(p[1]))[2]
            beyond = sorted(((sign * (p[0] - pav),) + p[1:] for p in st
                             if sign * (p[0] - pav) > 0.5 and "runway" not in p[4]),
                            key=lambda p: p[0])
            # one node per station: the one nearest the centre line
            rows = []
            for d, t, z, nid, roles, la, lo in beyond:
                if rows and abs(rows[-1]["d_m"] - d) < 0.5:
                    if abs(t) < rows[-1]["t_m"]:
                        rows.pop()
                    else:
                        continue
                fall = z_end - z
                r = prof.rise_m(d)
                rows.append({"d_m": round(d, 1), "t_m": round(abs(t), 1), "z": round(z, 2),
                             "dz_end_m": round(z - z_end, 2), "roles": "|".join(sorted(roles)),
                             "node": nid, "lat": la, "lon": lo,
                             "fall_allowed_m": round(prof.fall_m(d), 2),
                             "rise_allowed_m": None if r is None else round(r, 2),
                             "over_m": round(max(0.0, fall - prof.fall_m(d),
                                                 0.0 if r is None else (-fall) - r), 2)})
            segs = []
            prev = (0.0, z_end)
            for r in rows:
                if r["d_m"] - prev[0] >= 0.5:
                    segs.append((round(prev[0], 1), r["d_m"],
                                 round(100.0 * (r["z"] - prev[1]) / (r["d_m"] - prev[0]), 2)))
                prev = (r["d_m"], r["z"])
            brk = prof.break_m

            def z_at(d):
                p0 = (0.0, z_end)
                for r in rows:
                    if r["d_m"] >= d:
                        return p0[1] + (r["z"] - p0[1]) * (d - p0[0]) / max(r["d_m"] - p0[0], 1e-9)
                    p0 = (r["d_m"], r["z"])
                return None
            zb = z_at(brk) if brk else None
            out.append({"runway": ref, "end": end_name, "code": cn, "letter": cl,
                        "ruleset": ruleset, "z_end": round(z_end, 2),
                        "pavement_end_s": round(pav, 1), "break_m": brk,
                        "segments": segs,
                        "grade_to_break_pct": (None if zb is None else round(100.0 * (zb - z_end) / brk, 2)),
                        "dz_at_break_m": (None if zb is None else round(zb - z_end, 2)),
                        "band_end_m": rows[-1]["d_m"] if rows else None,
                        "dz_at_band_end_m": rows[-1]["dz_end_m"] if rows else None,
                        "over_rows": sum(1 for r in rows if r["over_m"] > 0.0),
                        "nodes": rows})
    return {"patch": os.fspath(patch), "ruleset": ruleset, "ends": out}


def _print_profile(out):
    print("=== RUNWAY-END PROFILE  %s  (ruleset %s)" % (out["patch"], out["ruleset"]))
    for e in out["ends"]:
        print("  %s end %-4s code %s%s  z_end %.2f  break %s m: grade to break %s %%, dz %s m; "
              "band end %s m dz %s m; nodes over the profile: %d"
              % (e["runway"], e["end"], e["code"], e["letter"] or "", e["z_end"],
                 e["break_m"], e["grade_to_break_pct"], e["dz_at_break_m"],
                 e["band_end_m"], e["dz_at_band_end_m"], e["over_rows"]))
        print("    segments (from, to, grade %%): %s" % e["segments"])
        for r in e["nodes"]:
            print("    d=%6.1f t=%4.1f z=%8.2f dz=%+6.2f  allowed fall %5.2f rise %s  over %4.2f  %s"
                  % (r["d_m"], r["t_m"], r["z"], r["dz_end_m"], r["fall_allowed_m"],
                     r["rise_allowed_m"], r["over_m"], r["roles"]))


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
    parser.add_argument("--profile", action="store_true",
                        help="THE END PROFILE (#620): the emitted nodes on each "
                             "runway's extended centre line beyond its ends, "
                             "against the ruleset's runway-end profile "
                             "(law.tables.runway_end_profile); axes from the "
                             "patch's own sidecar, no --end needed")
    parser.add_argument("--corridor-m", type=float, default=8.0,
                        help="--profile: lateral half-width of the centre-line corridor (m)")
    parser.add_argument("--radius-m", type=float, default=500.0)
    parser.add_argument("--level-m", type=float, default=0.0)
    parser.add_argument("--roles", default=",".join(DEFAULT_ROLES))
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)
    if args.profile:
        out = profile(args.patch, args.corridor_m)
        _print_profile(out)
        if args.json:
            Path(args.json).write_text(json.dumps(out, indent=1))
            print("JSON -> %s" % args.json)
        return 0
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
        parser.error("give at least one --end NAME LAT LON, --corners ICAO or --profile")
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
