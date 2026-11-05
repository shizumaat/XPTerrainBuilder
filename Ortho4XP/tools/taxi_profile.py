"""THE TAXIWAY CENTRELINE PROFILE — the longitudinal grade along every taxi
centreline of a v2 build, read over the law's OWN distance (issue #1893).

    venv/bin/python tools/taxi_profile.py ICAO.graded.json [--axes PATCH.osm.axes.json]
        [--window 30 100] [--site LAT,LON ...] [--radius 150] [--top 10] [--json OUT]

The taxiway longitudinal law (ICAO Annex 14 §3.9.10, FAA AC 150/5300-13B §4,
``rulesets.<authority>.taxi``) is stated per CENTRELINE EDGE
(``constraints/taxi.taxi_centerlines``).  The census reads the taxi family
through PAIR rows (``taxi_box``, ``airside_no_step``) at pair caps, so a
"max within 30 m" off census rows is a pair reading — HECA's 10.19 % "over
4 m" was one — not the centreline law.  This reads the centreline itself:
the ``taxi_centerline`` breaklines of the graded surface (the solve's own
vertices and levels), every edge's |dz| / length against its stretch cap
(the sidecar's ``stretches``, by ref; ``--cap`` where there is none), and
sliding windows of ``--window`` metres along each breakline (5 m steps,
arc-length interpolated) — the grade a taxiing aircraft feels over that run.

Instrument only: prices no law and counts no defects (``harness/census.py``
does).  Born in lane hecagrade's scratch (#1893), promoted on its second use.
Twin: ``tests/test_taxi_profile.py``.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import bisect
import json
import math
from pathlib import Path
from typing import Mapping, Optional, Sequence

_R = 6371008.8
#: a reading within this many metres of the cap x length is rounding (the
#: patch writes levels at 1 cm)
TOL_M = 0.02


def metres(a: Sequence[float], b: Sequence[float]) -> float:
    """Plan distance between two (lat, lon, ...) points (local equirectangular)."""
    la = math.radians((a[0] + b[0]) / 2.0)
    return _R * math.hypot(math.radians(b[0] - a[0]),
                           math.radians(b[1] - a[1]) * math.cos(la))


def stretch_caps(axes: Optional[Mapping]) -> dict[str, float]:
    """Centreline ref -> its strictest stretch cap (sidecar ``stretches``:
    ``[points, cap, letter, ref]``)."""
    out: dict[str, float] = {}
    for st in (axes or {}).get("stretches", ()):
        cap, ref = float(st[1]), str(st[-1])
        out[ref] = min(cap, out.get(ref, cap))
    return out


def _at(s: Sequence[float], pts: Sequence[tuple], t: float) -> tuple:
    """The (lat, lon, z) at arc length ``t`` of a polyline whose stations are ``s``."""
    i = min(max(bisect.bisect_right(s, t) - 1, 0), len(s) - 2)
    f = 0.0 if s[i + 1] == s[i] else (t - s[i]) / (s[i + 1] - s[i])
    p, q = pts[i], pts[i + 1]
    return tuple(p[k] + f * (q[k] - p[k]) for k in range(3))


def read(graded: Mapping, caps: Mapping[str, float], default_cap: float,
         windows: Sequence[float] = (30.0, 100.0), step_m: float = 5.0) -> dict:
    """Every centreline edge and every window: ``{"edges": [...],
    "windows": {W: [...]}}``; each record ``(grade, metres, ref, cap, a, b)``
    with ``a``/``b`` the (lat, lon, z) ends (a window: its start and end)."""
    V = {int(v[0]): (float(v[1]), float(v[2]), float(v[3])) for v in graded["vertices"]}
    edges: list[tuple] = []
    wins: dict[float, list[tuple]] = {float(w): [] for w in windows}
    for b in graded["breaklines"]:
        if b.get("kind") != "taxi_centerline":
            continue
        ref = str(b.get("ref"))
        cap = float(caps.get(ref, default_cap))
        pts = [V[int(v)] for v in b["vertices"]]
        s = [0.0]
        for p, q in zip(pts, pts[1:], strict=False):
            d = metres(p, q)
            s.append(s[-1] + d)
            if d > 0.0:
                edges.append((abs(q[2] - p[2]) / d, d, ref, cap, p, q))
        for w in wins:
            t = 0.0
            while len(pts) > 1 and t + w <= s[-1] + 1e-9:
                p, q = _at(s, pts, t), _at(s, pts, t + w)
                wins[w].append((abs(q[2] - p[2]) / w, w, ref, cap, p, q))
                t += step_m
    return {"edges": edges, "windows": wins}


def over(recs: Sequence[tuple], min_m: float = 0.0) -> list[tuple]:
    """The records over their cap by more than :data:`TOL_M`, worst first."""
    out = [r for r in recs if r[1] >= min_m and r[0] * r[1] > r[3] * r[1] + TOL_M]
    return sorted(out, key=lambda r: -r[0])


def _line(r: tuple) -> str:
    g, d, ref, cap, p, q = r
    return (f"{100 * g:5.2f} % over {d:6.1f} m (cap {100 * cap:.2f} %) {ref:>10} "
            f"{p[0]:.6f},{p[1]:.6f} z {p[2]:.2f} -> {q[0]:.6f},{q[1]:.6f} z {q[2]:.2f}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("graded", type=Path, help="ICAO.graded.json of the build")
    ap.add_argument("--axes", type=Path, help="the patch's .axes.json (stretch caps)")
    ap.add_argument("--cap", type=float, default=0.015, help="cap where no stretch names one")
    ap.add_argument("--window", type=float, nargs="+", default=[30.0, 100.0])
    ap.add_argument("--min-edge", type=float, default=10.0,
                    help="edges shorter than this are listed apart (default 10 m)")
    ap.add_argument("--site", action="append", default=[], metavar="LAT,LON")
    ap.add_argument("--radius", type=float, default=150.0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    graded = json.loads(a.graded.read_text(encoding="utf-8"))
    axes = json.loads(a.axes.read_text(encoding="utf-8")) if a.axes else None
    res = read(graded, stretch_caps(axes), a.cap, a.window)
    e = res["edges"]
    ov, ov_long = over(e), over(e, a.min_edge)
    print(f"{a.graded.name}: {len(e)} centreline edges, {len(ov)} over their cap "
          f"(+{TOL_M} m), {len(ov_long)} of them >= {a.min_edge:g} m")
    for r in ov_long[:a.top]:
        print("  " + _line(r))
    out = {"edges": len(e), "over": len(ov), "over_long": len(ov_long), "windows": {}, "sites": {}}
    for w, recs in res["windows"].items():
        o = over(recs)
        print(f"  {w:g} m windows: {len(recs)}, over their cap {len(o)}"
              + (f"; worst {_line(o[0])}" if o else ""))
        out["windows"][str(w)] = {"windows": len(recs), "over": len(o),
                                 "worst_pct": round(100 * o[0][0], 2) if o else None}
    for site in a.site:
        c = tuple(float(x) for x in site.split(","))
        near = [r for r in e if r[1] >= a.min_edge
                and min(metres(c, r[4]), metres(c, r[5])) < a.radius]
        rec = {"worst_edge_pct": round(100 * max((r[0] for r in near), default=0.0), 2)}
        print(f"  site {site} (edges >= {a.min_edge:g} m within {a.radius:g} m): "
              + (_line(max(near, key=lambda r: r[0])) if near else "none"))
        for w, recs in res["windows"].items():
            nw = [r for r in recs if metres(c, r[4]) < a.radius]
            if nw:
                rec[f"{w:g}m_pct"] = round(100 * max(r[0] for r in nw), 2)
                print(f"    {w:g} m window max {rec[f'{w:g}m_pct']:.2f} %")
        out["sites"][site] = rec
    if a.json:
        a.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
