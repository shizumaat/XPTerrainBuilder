#!/usr/bin/env python3
"""THE PATCH TRANSECT — what the PATCH says the ground is along a line, and
what the DEM says under it, station by station.

The question is the owner's sim read: *walking east from the runway, does
the pavement stand where the ground is?*  A census prices PAIRS of values
(a body 6 m below its hill breaks no grade law and reports zero rows),
`arm_site_read.py` answers ONE named place, `osm_site.py` dumps one way and
`mesh_elevation_sampler.py` reads the BUILT MESH — which needs a tile build.
None of them walks a line across a patch naming, per station, the role that
covers it, the value that role's own shape carries there, and the DEM under
it.  This does, from the patch alone.

**It prices no law and counts no defects.**  Geometry, altitudes and the
role/ref of every way come from the harness library's own
`check_grade._parse_osm`; the metre frame is `check_grade._ll_to_m_factory`
about the sidecar's anchor when one is given.  Defect counts come from
`tools/harness/census.py` and nowhere else.

THE VALUE AT A STATION is the value of the SHAPE that covers it: the ways
are grouped by (role, ref) — the body the solve gave one datum — and the
station's value is the linear interpolation of that group's own emitted
node altitudes (nearest outside the hull).  Where several shapes cover a
station, the one highest in the ROLE ORDER wins (runway, then the taxi
family, then aprons, then roads, then structures, then the graded strip),
which is the precedence the reader wants: what an aircraft is standing on.
Bank/foot rings carry no value and never win.  A station covered by nothing
is reported as OUTSIDE PATCH.

THE DEM comes from the tile's own `.alt` raster through
`mesh_elevation_sampler.AltRaster` (`--alt`, with `--tile LAT LON`) — the
raster Triangle4XP was handed, read with its TRUE BILINEAR interpolation —
or, with `--dem-from-patch`, from the patch's own `dem_z` node tags where
the emitter published them.  A run with neither prints values only.

    venv/bin/python tools/patch_transect.py PATCH.osm --lat 60.71363 \
        --lon-from -135.06665 --lon-to -135.0545 --step 5 \
        --alt "…/Data+60-136.alt" --tile 60 -136 [--json OUT.json]

THE SPAN MAY RUN ANY BEARING (added for lane `v2aprontrend`, RULINGS
2026-09-10ar): `--from LAT,LON --to LAT,LON`, or `--from-ref REF --to
LAT,LON`, which starts at the ring node of the way `REF` NEAREST the
target — the "does the apron fall into the pit" read of 10an/10ar, which
runs from an apron ring node toward a rim vertex on no particular bearing.
It is the same station walk, the same value model and the same control-arm
column; only the direction is free.  `--lat/--lon-from/--lon-to` stands
unchanged (it is the CYXY 10o transect the tool was promoted on).

    venv/bin/python tools/patch_transect.py ARM.osm CONTROL.osm \
        --from-ref pav16 --to 40.49098918,-3.57037578 --step 1

Two patches may be passed: the second is the CONTROL arm and every station
reports both, with the delta — the arm-to-arm read a lane's bar is quoted
on.  Quote it on identical options, never as a verdict.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_grade import Way, _parse_osm  # noqa: E402

#: what an aircraft is standing on, highest authority first.  A role absent
#: from the table sorts last (a structure, a feature ring).
ROLE_ORDER: tuple[tuple[str, ...], ...] = (
    ("runway", "runway_crossing"),
    ("primary_parallel", "secondary_parallel", "stub", "junction",
     "cross_connector", "taxiway"),
    ("apron", "groundside_pavement", "parking_lot"),
    ("service_road", "service_junction", "road"),
    ("building",),
    ("graded_strip", "boundary"),
)


def _order(role: str) -> int:
    for k, group in enumerate(ROLE_ORDER):
        if role in group:
            return k
    return len(ROLE_ORDER)


def _inside(poly: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    """Even-odd point-in-polygon in (lon, lat)."""
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                c = not c
    return c


class Shape:
    """One BODY of the patch — every way sharing a (role, ref) — with its
    rings in (lon, lat) and its emitted node altitudes."""

    def __init__(self, role: str, ref: str) -> None:
        self.role, self.ref = role, ref
        self.rings: list[list[tuple[float, float]]] = []
        self.pts: list[tuple[float, float]] = []
        self.zs: list[float] = []

    def add(self, way: Way, nodes: dict[str, tuple[float, float]]) -> None:
        ring = [(nodes[n][1], nodes[n][0]) for n in way.nids if n in nodes]
        if len(ring) >= 3:
            self.rings.append(ring)
        seen: set[str] = set()
        for n, e in zip(way.nids, way.elevs):
            if n in seen or e is None or n not in nodes:
                continue
            seen.add(n)
            self.pts.append((nodes[n][1], nodes[n][0]))
            self.zs.append(float(e))

    def covers(self, lon: float, lat: float) -> bool:
        return sum(1 for r in self.rings if _inside(r, lon, lat)) % 2 == 1

    def value_at(self, lon: float, lat: float,
                 mlon: float) -> Optional[float]:
        """The shape's own surface at the station: inverse-distance over
        its three nearest emitted nodes (a plane where they bracket it,
        the nearest node where they do not) — the shape's OWN values, no
        outside authority and no law."""
        if not self.pts:
            return None
        d = [((lo - lon) * mlon, (la - lat) * 111320.0, k)
             for k, (lo, la) in enumerate(self.pts)]
        d.sort(key=lambda t: t[0] * t[0] + t[1] * t[1])
        near = d[:3]
        if math.hypot(near[0][0], near[0][1]) < 1e-6:
            return self.zs[near[0][2]]
        w = [1.0 / math.hypot(dx, dy) for dx, dy, _k in near]
        return sum(wi * self.zs[k] for wi, (_dx, _dy, k) in zip(w, near)) / sum(w)


def shapes_of(path: Path) -> tuple[dict[str, tuple[float, float]], list[Shape]]:
    nodes, ways = _parse_osm(path)
    by: dict[tuple[str, str], Shape] = {}
    for w in ways:
        if w.tags.get("o4_feature"):        # a feature ring carries no body
            continue
        key = (w.role or "?", w.ref or "")
        by.setdefault(key, Shape(*key)).add(w, nodes)
    return nodes, list(by.values())


def ring_node_nearest(path: Path, ref: str,
                      to: tuple[float, float]) -> tuple[float, float]:
    """The node of the way(s) tagged ``ref`` NEAREST ``to`` — station 0 of a
    ``--from-ref`` span.  REFUSES an unknown ref rather than guessing one."""
    nodes, ways = _parse_osm(path)
    cand = [nodes[n] for w in ways if (w.ref or "") == ref
            for n in w.nids if n in nodes]
    if not cand:
        raise SystemExit(f"REFUSING: no way with ref {ref!r} in {path}")
    mlon = 111320.0 * math.cos(math.radians(to[0]))
    return min(cand, key=lambda p: ((p[0] - to[0]) * 111320.0) ** 2
               + ((p[1] - to[1]) * mlon) ** 2)


def transect(path: Path, p0: tuple[float, float], p1: tuple[float, float],
             step_m: float) -> list[dict[str, Any]]:
    """The stations from ``p0`` to ``p1`` (both ``(lat, lon)``), ``step_m``
    apart along the straight line between them — any bearing."""
    nodes, shapes = shapes_of(path)
    mlon = 111320.0 * math.cos(math.radians(0.5 * (p0[0] + p1[0])))
    dy = (p1[0] - p0[0]) * 111320.0
    dx = (p1[1] - p0[1]) * mlon
    span = math.hypot(dx, dy)
    # EXACT STATIONS, as the east-west form has always walked them: every
    # station is a whole ``step_m`` from the start and the walk stops at or
    # before the end, so a span's last station is never stretched.
    n = int(math.floor(span / step_m + 1e-9)) if span > 0.0 else 0
    out: list[dict[str, Any]] = []
    for k in range(n + 1):
        f = 0.0 if span <= 0.0 else (k * step_m) / span
        lat = p0[0] + f * (p1[0] - p0[0])
        lon = p0[1] + f * (p1[1] - p0[1])
        hits = [s for s in shapes if s.covers(lon, lat)]
        hits.sort(key=lambda s: (_order(s.role), s.role, s.ref))
        rec: dict[str, Any] = {
            "dist_m": round(f * span, 1),
            "lat": lat,
            "lon": lon,
            "covered_by": "; ".join(f"{s.role}:{s.ref}" for s in hits)
                          or "OUTSIDE PATCH",
        }
        if hits:
            rec["role"] = hits[0].role
            rec["ref"] = hits[0].ref
            v = hits[0].value_at(lon, lat, mlon)
            rec["z_m"] = None if v is None else round(v, 3)
        else:
            rec["role"] = rec["ref"] = None
            rec["z_m"] = None
        out.append(rec)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch", type=Path, nargs="+",
                    help="the patch, and optionally the CONTROL arm second")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon-from", type=float)
    ap.add_argument("--lon-to", type=float)
    ap.add_argument("--from", dest="frm", metavar="LAT,LON",
                    help="a free-bearing span's start")
    ap.add_argument("--from-ref", metavar="REF",
                    help="start at this way's ring node nearest --to")
    ap.add_argument("--to", metavar="LAT,LON",
                    help="a free-bearing span's end")
    ap.add_argument("--step", type=float, default=5.0, help="metres")
    ap.add_argument("--alt", type=Path, help="the tile's Data<tile>.alt")
    ap.add_argument("--tile", type=float, nargs=2, metavar=("LAT", "LON"))
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    def _pt(s: str) -> tuple[float, float]:
        a, b = s.split(",")
        return float(a), float(b)

    free = args.to is not None or args.frm is not None or args.from_ref
    if free:
        if args.to is None or (args.frm is None and not args.from_ref):
            print("REFUSING: a free-bearing span needs --to and one of "
                  "--from / --from-ref", file=sys.stderr)
            return 2
        if args.lat is not None or args.lon_from is not None:
            print("REFUSING: --lat/--lon-from is the EAST-WEST form; a "
                  "free-bearing span uses --from/--from-ref and --to only",
                  file=sys.stderr)
            return 2
    else:
        if args.lat is None or args.lon_from is None or args.lon_to is None:
            print("REFUSING: give --lat --lon-from --lon-to, or --from/"
                  "--from-ref with --to", file=sys.stderr)
            return 2
        if args.lon_to <= args.lon_from:
            print("REFUSING: --lon-to must be east of --lon-from", file=sys.stderr)
            return 2
    if args.alt and not args.tile:
        print("REFUSING: --alt needs --tile LAT LON (the raster's own origin)",
              file=sys.stderr)
        return 2
    for p in args.patch:
        if not p.exists():
            print(f"REFUSING: no patch at {p}", file=sys.stderr)
            return 2

    if free:
        p1 = _pt(args.to)
        p0 = (_pt(args.frm) if args.frm
              else ring_node_nearest(args.patch[0], args.from_ref, p1))
    else:
        p0 = (args.lat, args.lon_from)
        p1 = (args.lat, args.lon_to)
    rows = [transect(p, p0, p1, args.step) for p in args.patch]
    dem: list[Optional[float]] = [None] * len(rows[0])
    if args.alt:
        from mesh_elevation_sampler import AltRaster
        raster = AltRaster(str(args.alt), int(args.tile[0]), int(args.tile[1]))
        dem = [raster.elevation_at(r["lat"], r["lon"]) for r in rows[0]]

    head = f"{'dist':>6} {'lon':>13} {'z':>9} {'DEM':>9} {'z-DEM':>8}"
    if len(rows) > 1:
        head += f" {'ctrl':>9} {'Δ':>7}"
    print(head + "   covered by")
    for k, r in enumerate(rows[0]):
        d = dem[k]
        z = r["z_m"]
        line = (f"{r['dist_m']:6.0f} {r['lon']:13.7f} "
                f"{'--' if z is None else f'{z:9.2f}'} "
                f"{'--' if d is None else f'{d:9.2f}'} "
                f"{'--' if (z is None or d is None) else f'{z - d:8.2f}'}")
        if len(rows) > 1:
            c = rows[1][k]["z_m"]
            line += (f" {'--' if c is None else f'{c:9.2f}'}"
                     f" {'--' if (z is None or c is None) else f'{z - c:7.2f}'}")
        print(line + "   " + r["covered_by"])
    if args.json:
        args.json.write_text(json.dumps(
            {"from": p0, "to": p1, "step_m": args.step,
             "patches": [str(p) for p in args.patch],
             "dem_m": dem, "arms": rows}, indent=1))
        print(f"[patch_transect] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
