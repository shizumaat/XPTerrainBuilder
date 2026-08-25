#!/usr/bin/env python3
"""APRON DRAPE READ — how far an emitted apron stands OFF the raw terrain,
and how bumpy it is once it is up there.

WHY THIS EXISTS.  A census answers "is the surface LAWFUL"; it cannot
answer "did the surface stop being a surface".  When the apron law's
interior cap was widened to 5 % (RULINGS 2026-08-21c) every census stayed
green while whole apron rings sank onto the DEM — the plateau simply had
no authority any more, and the defect the owner saw in the sim
("harsh cliffs, uneven hills and valleys in aprons") emitted NO ROW by
construction.  The three numbers below are that failure made measurable,
and they are what the 2026-08-24 back-edge rescope is accepted against.

THE THREE NUMBERS, all over APRON ring vertices, all in metres:

  height_above_dem   the vertex's emitted elevation minus the DEM under
                     it.  Its MEDIAN is "how high the plateau stands".  A
                     draping apron drops toward 0.
  ring_relief        per apron RING, p95 - p5 of that height.  Its median
                     is "how much the plateau tilts and rolls across one
                     apron".  A draping apron inherits the terrain's own
                     relief and this rises.
  amp50              per vertex, the peak-to-peak of that height inside a
                     50 m window along its own ring (both directions).
                     Its median is the LOCAL bumpiness — the "uneven hills
                     and valleys" reading.  Reported with its p95, because
                     a few bad rings are exactly what a median hides.

IT MEASURES ONLY WHAT IT SAYS.  Every elevation is read verbatim from the
patch (``check_grade._parse_osm``, the harness library's own parser — a
private parser here would be the census-wrapper defect); the DEM comes
from ``flat_site_sweep``'s own loaders, so this tool sees exactly the
surface that tool and a build see and never composes, densifies, fetches
or writes anything.  The metre frame for the 50 m window is
``check_grade._ll_to_m_factory`` about the sidecar's own anchor.

NUMBERS FROM THIS TOOL ARE NOT DEFECT COUNTS and never adjudicate: they
are a SHAPE reading, comparable ARM TO ARM on identical options and
nowhere else (the DEM source, the window and the percentiles are all
choices, and two arms taken on two DEM sources are not comparable).  Pass
two or more patches and the table prints the delta between the first and
each later one, which is the only form in which these numbers mean
anything.

    venv/bin/python tools/apron_drape_read.py A.osm [B.osm ...]
        [--dem-source airport-inset|base] [--window-m 50] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT / "src"), str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as CG                                       # noqa: E402
import flat_site_sweep as FSS                                  # noqa: E402

#: The role the reading is scoped to.  The ruling is about APRONS.
APRON_ROLE = "apron"

#: Default along-ring window for ``amp50`` (metres, each side).
DEFAULT_WINDOW_M = 50.0

#: The percentiles ``ring_relief`` spans.  Named so a report can state
#: them: a p95-p5 relief and a max-min relief are different numbers.
RELIEF_LO_PCT, RELIEF_HI_PCT = 5.0, 95.0


def _pct(values, q: float) -> float:
    """Linear-interpolated percentile over a sorted-able sequence."""
    xs = sorted(float(v) for v in values)
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (q / 100.0)
    lo = int(math.floor(k))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def _median(values) -> float:
    return _pct(values, 50.0)


def _tile_of(nodes) -> "tuple[int, int]":
    lats = [v[0] for v in nodes.values()]
    lons = [v[1] for v in nodes.values()]
    lat0 = sum(lats) / len(lats)
    lon0 = sum(lons) / len(lons)
    return int(math.floor(lat0)), int(math.floor(lon0))


def _load_dem(tile_lat: int, tile_lon: int, icao: str, dem_source: str):
    """The DEM, through ``flat_site_sweep``'s own loaders — read-only,
    never composed.  Returns ``(dem, path, origin)``; ``dem`` None when
    the requested surface is not cached, which is REPORTED, never
    silently substituted with the other one."""
    if dem_source == "airport-inset":
        dem, path, _meta = FSS._load_airport_inset_dem(
            tile_lat, tile_lon, icao, "auto")
        return dem, path, ("shared corpus (inset cache)" if dem else None)
    dem, path, origin = FSS._load_base_dem(tile_lat, tile_lon, "auto")
    return dem, path, origin


def _dem_at(dem, lat: float, lon: float, tile_lat: int, tile_lon: int
            ) -> Optional[float]:
    """The DEM value under one lat/lon, through the ENGINE's own call.

    ``dem.alt((lon - tile_lon, lat - tile_lat))`` is verbatim what
    ``auto_patch.elevation`` and ``auto_patch.tile_cut`` use — the DEM
    addresses itself in TILE-RELATIVE degrees with y measured NORTH from
    the tile's south edge.  Spelling the indexing differently here would
    be a second sampler, and a second sampler is the census-wrapper
    defect.  A point outside the raster's own extent (an inset covers the
    airport, not the tile) is reported UNCOVERED rather than clamped to
    an edge value."""
    x = lon - tile_lon
    y = lat - tile_lat
    if not (dem.x0 <= x <= dem.x1 and dem.y0 <= y <= dem.y1):
        return None
    try:
        f = float(dem.alt((x, y)))
    except Exception:                                          # pragma: no cover
        return None
    if not math.isfinite(f) or f <= dem.nodata + 1.0:
        return None
    return f


def _open_ring(seq):
    return seq[:-1] if len(seq) > 1 and seq[0] == seq[-1] else seq


def read_one(patch: Path, *, dem_source: str = "airport-inset",
             window_m: float = DEFAULT_WINDOW_M) -> dict:
    """THE reading for one patch.  One implementation — the CLI, an A/B
    and the twin all call this, so a table and a twin cannot disagree."""
    nodes, ways = CG._parse_osm(patch)
    if not nodes:
        raise SystemExit(f"{patch}: no nodes parsed")

    anchor = None
    side = Path(str(patch) + ".axes.json")
    if side.is_file():
        try:
            anchor = json.loads(side.read_text()).get("anchor") or None
        except Exception:                                      # pragma: no cover
            anchor = None
    ll_to_m = CG._ll_to_m_factory(nodes, anchor=tuple(anchor) if anchor else None)

    tile_lat, tile_lon = _tile_of(nodes)
    icao = patch.name.split("_")[0].upper()
    dem, dem_path, dem_origin = _load_dem(tile_lat, tile_lon, icao, dem_source)
    if dem is None:
        raise SystemExit(
            f"{patch}: no {dem_source} DEM cached for {icao} "
            f"(tile {tile_lat:+03d}{tile_lon:+04d}) — refusing to "
            f"substitute the other surface; the two are not comparable")

    rings: list[dict] = []
    uncovered = 0
    for w in ways:
        if (w.tags.get("role") or "") != APRON_ROLE:
            continue
        nids = _open_ring(list(w.nids))
        elevs = _open_ring(list(w.elevs))
        hs: list[Optional[float]] = []
        xy: list[tuple[float, float]] = []
        for nid, ele in zip(nids, elevs):
            ll = nodes.get(nid)
            if ll is None or ele is None:
                hs.append(None)
                xy.append((0.0, 0.0))
                continue
            d = _dem_at(dem, ll[0], ll[1], tile_lat, tile_lon)
            if d is None:
                uncovered += 1
                hs.append(None)
            else:
                hs.append(float(ele) - d)
            xy.append(ll_to_m(ll[0], ll[1]))
        if sum(1 for h in hs if h is not None) < 3:
            continue
        rings.append({"wid": w.wid, "ref": w.ref, "h": hs, "xy": xy})

    heights = [h for r in rings for h in r["h"] if h is not None]
    reliefs = []
    for r in rings:
        vals = [h for h in r["h"] if h is not None]
        if len(vals) >= 3:
            reliefs.append(_pct(vals, RELIEF_HI_PCT) - _pct(vals, RELIEF_LO_PCT))

    amps: list[float] = []
    for r in rings:
        hs, xy = r["h"], r["xy"]
        n = len(hs)
        # Cumulative along-ring arc, closed: the window is a WALK along
        # the ring, not a disc in the plane — two vertices metres apart
        # across a narrow apron are not 50 m of pavement apart.
        seg = [math.dist(xy[i], xy[(i + 1) % n]) for i in range(n)]
        for i in range(n):
            if hs[i] is None:
                continue
            win = [hs[i]]
            for direction in (1, -1):
                acc, j = 0.0, i
                while acc < window_m:
                    k = (j + 1) % n if direction > 0 else (j - 1) % n
                    acc += seg[j] if direction > 0 else seg[(j - 1) % n]
                    if k == i or acc > window_m:
                        break
                    if hs[k] is not None:
                        win.append(hs[k])
                    j = k
            if len(win) >= 2:
                amps.append(max(win) - min(win))

    return {
        "patch": str(patch),
        "icao": icao,
        "dem_source": dem_source,
        "dem_path": dem_path,
        "dem_origin": dem_origin,
        "window_m": window_m,
        "relief_pct": [RELIEF_LO_PCT, RELIEF_HI_PCT],
        "apron_rings": len(rings),
        "apron_vertices": len(heights),
        "vertices_uncovered_by_dem": uncovered,
        "height_above_dem_median_m": _median(heights) if heights else None,
        "height_above_dem_p05_m": _pct(heights, 5.0) if heights else None,
        "height_above_dem_p95_m": _pct(heights, 95.0) if heights else None,
        "ring_relief_median_m": _median(reliefs) if reliefs else None,
        "ring_relief_p95_m": _pct(reliefs, 95.0) if reliefs else None,
        "amp50_median_m": _median(amps) if amps else None,
        "amp50_p95_m": _pct(amps, 95.0) if amps else None,
    }


_ROWS = (
    ("height_above_dem_median_m", "apron median height above DEM"),
    ("height_above_dem_p05_m", "  ... p05"),
    ("height_above_dem_p95_m", "  ... p95"),
    ("ring_relief_median_m", "ring relief (p95-p05), median"),
    ("ring_relief_p95_m", "  ... p95 across rings"),
    ("amp50_median_m", "amp50 (50 m along-ring), median"),
    ("amp50_p95_m", "  ... p95 across vertices"),
)


def _fmt(v) -> str:
    return "-" if v is None else f"{v:8.3f}"


def print_table(reads: list) -> None:
    base = reads[0]
    print("=== APRON DRAPE READ ===")
    print(f"  DEM source: {base['dem_source']}  "
          f"({base.get('dem_origin') or 'n/a'})")
    print(f"  window {base['window_m']:g} m along-ring; relief spans "
          f"p{base['relief_pct'][0]:g}-p{base['relief_pct'][1]:g}")
    print("  NOT defect counts and never adjudicated — a SHAPE reading, "
          "comparable arm-to-arm on identical options only.")
    for r in reads:
        print(f"    arm: {Path(r['patch']).name}  "
              f"rings={r['apron_rings']} vertices={r['apron_vertices']} "
              f"uncovered={r['vertices_uncovered_by_dem']}")
    print()
    head = f"  {'METRIC':34s}" + "".join(
        f" {Path(r['patch']).name[:16]:>16s}" for r in reads)
    if len(reads) > 1:
        head += "".join(f" {'delta':>10s}" for _ in reads[1:])
    print(head)
    print("  " + "-" * (len(head) - 2))
    for key, label in _ROWS:
        line = f"  {label:34s}" + "".join(
            f" {_fmt(r.get(key)):>16s}" for r in reads)
        for r in reads[1:]:
            a, b = base.get(key), r.get(key)
            line += (f" {b - a:+10.3f}" if (a is not None and b is not None)
                     else f" {'-':>10s}")
        print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("patches", nargs="+", type=Path)
    ap.add_argument("--dem-source", default="airport-inset",
                    choices=("airport-inset", "base"),
                    help="'airport-inset' (default) is THE SURFACE "
                         "PRODUCTION GRADES ON where an inset is cached; "
                         "'base' reads the tile's own .hgt.  Two arms on "
                         "two sources are NOT comparable.")
    ap.add_argument("--window-m", type=float, default=DEFAULT_WINDOW_M)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    os.environ.setdefault("O4_SUPPRESS_UI", "1")
    reads = [read_one(p, dem_source=a.dem_source, window_m=a.window_m)
             for p in a.patches]
    print_table(reads)
    if a.json:
        a.json.write_text(json.dumps(reads, indent=2))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
