#!/usr/bin/env python3
"""CORRIDOR AXIS COVERAGE — does the law carry this corridor end-to-end?

    venv/bin/python tools/corridor_axis_coverage.py PATCH.osm.axes.json \\
        --corridor NAME=LAT,LON:LAT,LON [--corridor ...] [--halo M] [--json OUT]
    venv/bin/python tools/corridor_axis_coverage.py PATCH.osm.axes.json \\
        --free-ends PATCH.osm [--transect M] [--json OUT]

Run it from ``Ortho4XP/``.

THE QUESTION.  A service corridor is ONE law object end-to-end (owner ruling
2026-08-12b, "APT.DAT TRUCK ROUTES ARE A SERVICE-CORRIDOR SOURCE": never
fragmented per-junction axes).  Whether a build honoured that is a question
about the LAW's own axis set, not about pavement: how much of the corridor's
run carries an axis at all, where the AXIS-FREE GAPS are, and how many
distinct chains it takes to cover it.  Nothing read that back — the census
counts law rows, `spine_coverage.py` answers the AIRCRAFT centerline's
node coverage, and neither can say "this corridor is four disjoint 2-node
axes with a 157 m hole in the middle", which is the named HECA defect.

**IT MEASURES NO LAW AND COUNTS NO DEFECTS.**  Every number is read verbatim
out of the patch's axes sidecar — `axes_exact`, which IS
``grade_graph.centerline_specs``' published enumeration (the same list the
solver's context and the census's `axes_exact` reader consume), so this tool
and the law cannot disagree about which roads are roads.  Defect counts come
from `harness/census.py` and nowhere else.

THE FRAME, stated on every report because it is an approximation the reader
must see: a corridor is named by its two ENDPOINTS and measured along the
straight CHORD between them, with an axis vertex counted as "on the corridor"
when it lies within ``--halo`` metres of that chord.  A real corridor bends
away from its chord (measured at HECA: 9.0 m and 1.8 m maximum lateral
deviation on the two spine roads), so the halo must exceed the bend or the
tool reports a gap the law does not have.  Two runs at two halos are two
populations.  A corridor whose bend exceeds any sane halo needs its own
intermediate points — pass them as several `--corridor` segments.

``--free-ends`` answers the corridor's OTHER end-to-end question (the
corridor-joins round, spec ruling 4(b)): DOES THE ROAD REACH GROUND?  A
corridor end that does not terminate on pavement ties to ambient DEM under
the road cap (RULINGS 2026-08-12b), so the acceptance number is the emitted
altitude MINUS the DEM at that terminus, and it must be ≤ 0.01 m unless the
terrain is out of the cap's reach (a CLAMPED end, which the build records as
such).  The DEM comes from the sidecar's ``svc_free_ends`` records — THE
BUILD'S OWN DEM FRAME, published by the build that read it — because an
offline DEM read is a different frame (warm-vs-cold has moved terrain 12 m)
and would answer a different question.  The emitted altitude is read from the
patch through the harness library's own parser.  A TRANSECT of the road-family
nodes around each terminus is printed with it: the profile that must stay
inside the road cap, which is where "no cliff on the old wall's footprint" is
read off.

REFUSALS (never a silent wrong answer): a sidecar with no ``axes_exact`` key
is REFUSED (the legacy ``axes`` spelling is a different, per-size-split
export and would under-report chains); a corridor whose two endpoints are
closer than the halo is REFUSED; a `--corridor` spec that does not parse is
REFUSED naming the token.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

__all__ = ["corridor_coverage", "parse_corridor", "load_axes",
           "load_free_ends", "free_end_offsets", "FREE_END_FLOOR_M"]

#: Materiality floor for a free-end DEM offset (the standing 0.01 m
#: elevation floor).  An UNCLAMPED end owes the terrain to within this;
#: a CLAMPED end (terrain out of the road cap's reach from the mouth) is
#: lawful wherever the cap left it and is reported, never failed.
FREE_END_FLOOR_M = 0.01

#: Default half-width of the chord corridor, metres.  Exceeds the measured
#: HECA spine-road lateral deviation (9.0 m) with margin.
DEFAULT_HALO_M = 12.0

#: Metres per degree of latitude, the flat-earth constant this repo's
#: patch readers already use for local metre work.
_M_PER_DEG = 111320.0


class CoverageRefusal(RuntimeError):
    """A question this tool will not answer with a guess."""


def load_axes(sidecar_path) -> list:
    """The sidecar's ``axes_exact`` list, or a refusal.

    ``axes_exact`` entries are ``(latlon_pts, seg_caps, route_ordinal,
    is_service)`` — ``verification.taxi_axes_exact_ll``'s export.
    """
    path = Path(sidecar_path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise CoverageRefusal(f"cannot read {path}: {exc}") from exc
    axes = data.get("axes_exact")
    if not isinstance(axes, list):
        raise CoverageRefusal(
            f"{path} carries no 'axes_exact' — this reader will not fall back "
            f"to the legacy 'axes' export (a different, per-size-split list "
            f"that would under-report chains)")
    return axes


def parse_corridor(spec: str):
    """``NAME=LAT,LON:LAT,LON`` -> ``(name, (lat, lon), (lat, lon))``."""
    try:
        name, rest = spec.split("=", 1)
        a_s, b_s = rest.split(":", 1)
        a = tuple(float(v) for v in a_s.split(","))
        b = tuple(float(v) for v in b_s.split(","))
    except ValueError as exc:
        raise CoverageRefusal(
            f"cannot parse --corridor {spec!r}; expected "
            f"NAME=LAT,LON:LAT,LON") from exc
    if len(a) != 2 or len(b) != 2:
        raise CoverageRefusal(f"--corridor {spec!r} needs two lat,lon points")
    return name, a, b


def _projector(lat0: float, lon0: float):
    cos = math.cos(math.radians(lat0))

    def to_m(lat, lon):
        return ((lon - lon0) * _M_PER_DEG * cos, (lat - lat0) * _M_PER_DEG)
    return to_m


def corridor_coverage(axes, a, b, *, halo_m: float = DEFAULT_HALO_M,
                      service_only: bool = True) -> dict:
    """Coverage of the chord ``a``→``b`` by the sidecar's axes.

    Returns the chord length, the number of distinct axes touching it, the
    merged covered intervals, the AXIS-FREE gaps, and the per-axis spans
    (longest first) — every value in metres along the chord.
    """
    to_m = _projector(a[0], a[1])
    ax, ay = to_m(*a)
    bx, by = to_m(*b)
    length = math.hypot(bx - ax, by - ay)
    if length <= halo_m:
        raise CoverageRefusal(
            f"corridor endpoints are {length:.1f} m apart, at or under the "
            f"{halo_m:.1f} m halo — that is not a corridor, it is one point")
    ux, uy = (bx - ax) / length, (by - ay) / length

    spans, covered, n_axes = [], [], 0
    for entry in axes:
        if not entry:
            continue
        pts = entry[0]
        is_service = bool(entry[3]) if len(entry) > 3 else False
        if service_only and not is_service:
            continue
        run, runs = [], []
        for p in pts:
            px, py = to_m(p[0], p[1])
            dx, dy = px - ax, py - ay
            s = dx * ux + dy * uy
            t = -dx * uy + dy * ux
            if abs(t) <= halo_m and -halo_m <= s <= length + halo_m:
                run.append(s)
            else:
                if len(run) >= 2:
                    runs.append((min(run), max(run)))
                run = []
        if len(run) >= 2:
            runs.append((min(run), max(run)))
        if not runs:
            continue
        n_axes += 1
        lo = min(r[0] for r in runs)
        hi = max(r[1] for r in runs)
        spans.append({"span_m": round(hi - lo, 1), "s0_m": round(lo, 1),
                      "s1_m": round(hi, 1), "n_vertices": len(pts)})
        covered.extend(runs)

    clipped = sorted((max(0.0, s0), min(length, s1)) for (s0, s1) in covered
                     if s1 > 0.0 and s0 < length)
    merged: list = []
    for iv in clipped:
        if merged and iv[0] <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], iv[1])
        else:
            merged.append([iv[0], iv[1]])
    gaps, cursor = [], 0.0
    for (s0, s1) in merged:
        if s0 > cursor + 1.0:
            gaps.append([round(cursor, 1), round(s0, 1)])
        cursor = max(cursor, s1)
    if cursor < length - 1.0:
        gaps.append([round(cursor, 1), round(length, 1)])
    spans.sort(key=lambda d: -d["span_m"])
    return {
        "chord_len_m": round(length, 1),
        "halo_m": halo_m,
        "scope": "service" if service_only else "all",
        "axes_touching": n_axes,
        "covered_m": round(sum(s1 - s0 for (s0, s1) in merged), 1),
        "covered": [[round(s0, 1), round(s1, 1)] for (s0, s1) in merged],
        "gaps": gaps,
        "axes": spans[:8],
    }


def load_free_ends(sidecar_path) -> list:
    """The sidecar's ``svc_free_ends`` records, or a refusal.

    Each record is the BUILD's own: ``lat``/``lon`` of an anchored corridor
    terminus, ``dem_m`` (the ambient DEM the build read there), ``target_m``
    (what the tie anchored it at), ``clamped`` (terrain out of the cap's
    reach) and ``nodes`` (the terminal cross-section's node count).
    """
    path = Path(sidecar_path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise CoverageRefusal(f"cannot read {path}: {exc}") from exc
    if "svc_free_ends" not in data:
        raise CoverageRefusal(
            f"{path} carries no 'svc_free_ends' key — it was built before "
            f"the corridor-joins round; there is no DEM frame to measure "
            f"against and this reader will not substitute one")
    recs = data.get("svc_free_ends")
    if recs is None:
        raise CoverageRefusal(
            f"{path} has svc_free_ends = null — that patch solved no "
            f"elevations, so a free-end offset is not defined for it")
    return list(recs)


def _road_nodes(patch_path):
    """``[(lat, lon, alt), …]`` for every ROAD-FAMILY node in the patch.

    Read through the harness library's own parser (``check_grade._parse_osm``)
    so this tool and the census read one file one way.  The road family is
    the census's own ``_ROAD_FAMILY_ROLES``.
    """
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    spec = importlib.util.spec_from_file_location(
        "corridor_axis_check_grade", root / "tools" / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    roles = set(getattr(mod, "_ROAD_FAMILY_ROLES",
                        {"service_road", "service_junction"}))
    nodes, ways = mod._parse_osm(Path(patch_path))
    out = []
    for w in ways:
        if w.role not in roles:
            continue
        for nid, a in zip(w.nids, (w.elevs or [])):
            p = nodes.get(nid)
            if p is not None and a is not None:
                out.append((p[0], p[1], float(a)))
    return out


def free_end_offsets(records, road_nodes, *, transect_m: float = 40.0,
                     match_m: float = 8.0) -> list:
    """Per free-end record: the EMITTED altitude at the terminus, the offset
    against the build's own DEM there, and the transect around it.

    The emitted value is the road-family node NEAREST the terminus (within
    ``match_m`` — the terminal cross-section's own radius); the transect is
    every road node within ``transect_m``, ordered by distance, with the
    grade each consecutive pair implies.  An end with no road node in reach
    reports ``emitted_m = None`` — never a silent zero.
    """
    out = []
    for rec in records:
        lat, lon = rec.get("lat"), rec.get("lon")
        if lat is None or lon is None:
            out.append({**rec, "emitted_m": None, "offset_m": None,
                        "note": "record carries no lat/lon"})
            continue
        near = sorted(((math.hypot((la - lat) * _M_PER_DEG,
                                   (lo - lon) * _M_PER_DEG
                                   * math.cos(math.radians(lat))), la, lo, a)
                       for (la, lo, a) in road_nodes),
                      key=lambda t: t[0])
        hit = [t for t in near if t[0] <= match_m]
        emitted = hit[0][3] if hit else None
        dem = rec.get("dem_m")
        transect = [{"d_m": round(d, 2), "alt_m": round(a, 3)}
                    for (d, _la, _lo, a) in near if d <= transect_m][:24]
        # The CLIFF read: the altitude spread the road carries within the
        # transect radius.  Deliberately NOT a "worst grade" between two
        # arbitrary nodes — nodes ranked by distance from the terminus are
        # not a profile along the road, and pairs metres apart across the
        # carriageway would report grades in the hundreds of percent.  The
        # law's own grade counts come from the census; this is the "is
        # there a 10 m step here" number the ruling asks for.
        alts = [t["alt_m"] for t in transect]
        spread = (max(alts) - min(alts)) if alts else None
        match_d = hit[0][0] if hit else None
        # A match is a road node NEAR the terminus, not the terminus
        # itself: over that distance the road's OWN cap lawfully carries
        # it away from the terminus value, so the slack the offset is
        # judged against is the cap over the match distance, plus the
        # materiality floor.
        slack = (_road_cap() * match_d + FREE_END_FLOOR_M
                 if match_d is not None else None)
        offset = (emitted - dem
                  if (emitted is not None and dem is not None) else None)
        out.append({
            **rec,
            "emitted_m": (round(emitted, 3) if emitted is not None else None),
            "offset_m": (round(offset, 3) if offset is not None else None),
            "match_m": (round(match_d, 2) if match_d is not None else None),
            "lawful_slack_m": (round(slack, 3) if slack is not None else None),
            # A CLAMPED end is lawful wherever the cap left it — its
            # offset is reported, never failed — so it is not a floor
            # breach and this field says so (the printed verdict and this
            # flag are ONE judgement, not two).
            "over_floor": (not rec.get("clamped")
                           and offset is not None and slack is not None
                           and abs(offset) > slack),
            "transect_spread_m": (round(spread, 3)
                                  if spread is not None else None),
            "transect": transect,
        })
    return out


def _road_cap() -> float:
    """``config.SERVICE_ROAD_MAX_GRADE`` — the production constant, read
    from production (never a second spelling of the number)."""
    root = Path(__file__).resolve().parents[1]
    if str(root / "src") not in sys.path:
        sys.path.insert(0, str(root / "src"))
    from auto_patch.config import SERVICE_ROAD_MAX_GRADE
    return float(SERVICE_ROAD_MAX_GRADE)


def _report(name: str, res: dict) -> str:
    head = (f"  {name}: chord {res['chord_len_m']} m, "
            f"{res['axes_touching']} axis/axes touching, "
            f"covered {res['covered_m']} m")
    if res["gaps"]:
        head += (f"  — AXIS-FREE GAPS: "
                 + ", ".join(f"[{g[0]}, {g[1]}]" for g in res["gaps"]))
    else:
        head += "  — NO axis-free gap"
    lines = [head]
    for sp in res["axes"]:
        lines.append(f"      span {sp['span_m']:8.1f} m  "
                     f"s {sp['s0_m']:8.1f} → {sp['s1_m']:8.1f}  "
                     f"({sp['n_vertices']} vertices)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sidecar", help="PATCH.osm.axes.json")
    ap.add_argument("--corridor", action="append", default=[],
                    metavar="NAME=LAT,LON:LAT,LON")
    ap.add_argument("--halo", type=float, default=DEFAULT_HALO_M)
    ap.add_argument("--all-axes", action="store_true",
                    help="score every axis, not only the SERVICE ones")
    ap.add_argument("--free-ends", dest="free_ends", metavar="PATCH.osm",
                    help="report the FREE-END DEM offsets recorded by the "
                         "build, read against this patch's emitted values")
    ap.add_argument("--transect", type=float, default=40.0,
                    help="transect radius around each free end, metres")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)
    if not args.corridor and not args.free_ends:
        print("REFUSED: nothing asked — pass --corridor and/or --free-ends",
              file=sys.stderr)
        return 2
    if args.free_ends:
        try:
            recs = load_free_ends(args.sidecar)
            rows = free_end_offsets(recs, _road_nodes(args.free_ends),
                                    transect_m=args.transect)
        except CoverageRefusal as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        print(f"=== corridor FREE-END DEM offsets: {args.free_ends}")
        print(f"  frame: DEM is the BUILD's own, published per terminus in "
              f"{args.sidecar} (never an offline DEM read — a different "
              f"frame); emitted altitude is the nearest road-family node "
              f"and the offset is judged against the road cap over THAT "
              f"match distance ({_road_cap() * 100:.1f}% + "
              f"{FREE_END_FLOOR_M} m); a CLAMPED end is lawful wherever the "
              f"cap left it")
        bad = 0
        for r in sorted(rows, key=lambda d: -(abs(d["offset_m"] or 0.0))):
            off = r["offset_m"]
            flag = "—"
            if off is None:
                flag = "NO ROAD NODE IN REACH"
            elif r.get("clamped"):
                flag = "clamped (cap-limited)"
            elif r.get("over_floor"):
                flag = "OVER FLOOR"
                bad += 1
            print(f"    {r.get('lat')},{r.get('lon')}  dem "
                  f"{r.get('dem_m')}  target {r.get('target_m')}  emitted "
                  f"{r.get('emitted_m')}  offset "
                  f"{'None' if off is None else f'{off:+.3f}'} m "
                  f"@{r.get('match_m')} m (slack {r.get('lawful_slack_m')})  "
                  f"transect spread {r.get('transect_spread_m')} m  {flag}")
        print(f"  {len(rows)} free end(s); "
              f"{sum(1 for r in rows if r.get('clamped'))} clamped; "
              f"{bad} over the floor")
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(
                {"sidecar": str(args.sidecar), "patch": args.free_ends,
                 "floor_m": FREE_END_FLOOR_M, "free_ends": rows}, indent=2))
            print(f"  -> {args.json_out}")
        if not args.corridor:
            return 0
    try:
        axes = load_axes(args.sidecar)
        out = {}
        for spec in args.corridor:
            name, a, b = parse_corridor(spec)
            out[name] = corridor_coverage(
                axes, a, b, halo_m=args.halo,
                service_only=not args.all_axes)
    except CoverageRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"=== corridor axis coverage: {args.sidecar}")
    print(f"  frame: straight CHORD between the named endpoints, halo "
          f"{args.halo} m, scope "
          f"{'all axes' if args.all_axes else 'SERVICE axes'}; "
          f"{len(axes)} axis/axes in the sidecar's axes_exact")
    for name, res in out.items():
        print(_report(name, res))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"sidecar": str(args.sidecar), "corridors": out}, indent=2))
        print(f"  -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
