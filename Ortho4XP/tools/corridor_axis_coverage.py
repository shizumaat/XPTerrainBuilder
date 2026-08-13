#!/usr/bin/env python3
"""CORRIDOR AXIS COVERAGE — does the law carry this corridor end-to-end?

    venv/bin/python tools/corridor_axis_coverage.py PATCH.osm.axes.json \\
        --corridor NAME=LAT,LON:LAT,LON [--corridor ...] [--halo M] [--json OUT]

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

__all__ = ["corridor_coverage", "parse_corridor", "load_axes"]

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
    ap.add_argument("--corridor", action="append", required=True,
                    metavar="NAME=LAT,LON:LAT,LON")
    ap.add_argument("--halo", type=float, default=DEFAULT_HALO_M)
    ap.add_argument("--all-axes", action="store_true",
                    help="score every axis, not only the SERVICE ones")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args(argv)
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
