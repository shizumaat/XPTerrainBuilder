#!/usr/bin/env python3
"""ROAD TERRAIN CONFORMANCE — does the emitted road FOLLOW the ground, or
does it cut through it?

WHY THIS EXISTS (owner ruling RULINGS 2026-08-31a, "TERRAIN-CONFORMANCE
INSTRUMENT REQUIRED").  The owner's road law is: a road FOLLOWS TERRAIN up
to ``SERVICE_ROAD_MAX_GRADE`` (8 %) and is PINNED ONLY where it meets
airside pavement; "a road capped below 8 % into a cutting is a defect".  A
census cannot see that defect — it counts law ROWS, and a road planed flat
through a hill breaks no grade law at all; it is the most lawful surface
there is.  The 2026-08-30 mega-round shipped exactly that regression under
a green census (docs/POSTMORTEM-20260831.md).  This is the reading that
would have caught it.

WHAT IT READS, per road CHAIN (a connected run of ``service_road`` /
``service_junction`` rings), all metres unless marked:

  dem_relief_m       max-min of the DEM under the chain: how much hill the
                     road crosses.  This is what makes a site a HILL SITE.
  emitted_relief_m   max-min of the chain's own emitted profile.
  follow_ratio       emitted_relief / dem_relief.  1.0 = the road rides the
                     hill; 0.0 = the road is a plane through it.  THE
                     HEADLINE: the owner's defect is this number near 0 on
                     a chain whose terrain is followable.
  cut_max_m          max(DEM - emitted) — the deepest CUTTING.
  fill_max_m         max(emitted - DEM) — the highest EMBANKMENT.
  dev_median_m       median |emitted - DEM| over the chain's own vertices.
  emitted_grade_max  steepest emitted step along the chain (%).
  dem_grade_max      steepest DEM step along the same steps (%).
  dem_followable_pct percentage of steps whose DEM grade is AT OR UNDER the
                     road cap — i.e. how much of this hill the law says the
                     road MAY follow.  A chain that is 100 % followable and
                     reads follow_ratio 0.05 is the defect in one line.

IT MEASURES NO LAW AND COUNTS NO DEFECTS.  Geometry and emitted altitudes
come from ``check_grade._parse_osm`` and the role from
``check_grade.law_role`` (the harness library's own parser and role
accessor); the road family is ``check_grade._ROAD_FAMILY_ROLES``, which IS
``grade_law.ROAD_ROLES``; the metre frame is
``check_grade._ll_to_m_factory`` about the sidecar's anchor; and the DEM is
sampled through ``apron_drape_read``'s loaders and ``_dem_at`` — the
engine's own ``dem.alt`` call, the same surface that tool and a build see.
Nothing here re-spells a set, a parser or a sampler (the census-wrapper
defect, CLAUDE.md).  Read-only: nothing is composed, densified, fetched or
written.

THE FRAME, printed on every report:
* A CHAIN is the connected component of road rings joined by SHARED NODE
  IDs, walked along its own longest path (a double-BFS diameter over the
  ring-adjacency graph).  Its SPINE is that path's ring-centroid
  polyline, so the station coordinate is the road's own PATH, never a
  plan chord — a U-turn is long here however short its chord (the frame
  ``free_road_profile`` solves in).
* THE PROFILE IS BINNED BY VERTEX, not by ring: every road vertex is
  projected onto the spine and each ``--bin-m`` (default 25 m) of road
  reports the MEDIAN emitted value and MEDIAN DEM of the vertices in it,
  at their MEAN station.  A ring is not a granularity — a corridor rect
  can be one metre or one kilometre long, and its own median would make a
  kilometre of road a single profile point.  Binning by median also means
  a crowned or tilted cross-section cannot masquerade as a profile step.
  Two arms on two bin sizes are not comparable.
* ``--dem-source airport-inset`` (default) is THE SURFACE PRODUCTION
  GRADES ON.  Two arms on two DEM sources are NOT comparable and the
  missing surface REFUSES rather than substituting the other.
* Numbers are comparable ARM TO ARM on identical options and nowhere else.

TWO MODES, the same reading:

    # DISCOVERY — rank the hill sites of a patch (way ids + lat/lon)
    venv/bin/python tools/road_terrain_conformance.py PATCH.osm --rank
        [--min-relief 10] [--top 5] [--min-span 100]

    # ARM TO ARM — one named site across arms, control first
    venv/bin/python tools/road_terrain_conformance.py CTL.osm ARM.osm ...
        --site hillA=30.1234567,31.4234567 [--site hillB=...]
        [--profile]            # print the station/emitted/DEM profile
        [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT / "src"), str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as CG                                       # noqa: E402
import apron_drape_read as ADR                                 # noqa: E402

#: The road cap the report judges "followable" against — the owner
#: constant, read from production and never re-spelled here.
try:                                                           # pragma: no cover
    from auto_patch.config import SERVICE_ROAD_MAX_GRADE as ROAD_CAP
except Exception:                                              # pragma: no cover
    ROAD_CAP = 0.080

#: A site's chain is the one whose vertices reach within this of the named
#: point.  Wider than a weld tolerance on purpose: a site is a PLACE.
DEFAULT_SITE_RADIUS_M = 40.0

#: Discovery defaults: the spec's "longest chains crossing >= 10 m relief".
DEFAULT_MIN_RELIEF_M = 10.0
DEFAULT_MIN_SPAN_M = 100.0

#: The profile BIN — a fixed length of ROAD, so one granularity reads
#: every chain and every arm (a ring is not a granularity: a corridor
#: rect can be one metre or one kilometre long).
DEFAULT_BIN_M = 25.0


def _open_ring(seq):
    return seq[:-1] if len(seq) > 1 and seq[0] == seq[-1] else seq


def _road_rings(patch: Path, dem_at: Callable[[float, float], Optional[float]],
                ll_to_m, nodes, ways) -> list:
    """One record per ROAD-FAMILY ring: its nodes, plan positions, emitted
    altitudes and the DEM under each vertex."""
    out = []
    for w in ways:
        if CG.law_role(w) not in CG._ROAD_FAMILY_ROLES:
            continue
        nids = _open_ring(list(w.nids))
        elevs = _open_ring(list(w.elevs))
        pts, zs, ds, lls = [], [], [], []
        for nid, ele in zip(nids, elevs):
            ll = nodes.get(nid)
            if ll is None:
                continue
            pts.append(ll_to_m(ll[0], ll[1]))
            lls.append((ll[0], ll[1]))
            zs.append(None if ele is None else float(ele))
            ds.append(dem_at(ll[0], ll[1]))
        if len(pts) < 3:
            continue
        zv = [z for z in zs if z is not None]
        dv = [d for d in ds if d is not None]
        if not zv or not dv:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        out.append({
            "wid": w.wid, "role": CG.law_role(w), "ref": w.ref,
            "nids": set(nids), "xy": pts, "ll": lls, "z": zs, "d": ds,
            "level": ADR._median(zv), "ground": ADR._median(dv),
            "c": (cx, cy),
        })
    return out


def _components(rings) -> list:
    """Connected components of the ring graph — rings joined by a SHARED
    NODE ID, which is the emitter's own identity (never proximity)."""
    by_nid: dict = {}
    for i, r in enumerate(rings):
        for nid in r["nids"]:
            by_nid.setdefault(nid, []).append(i)
    adj: dict = {i: set() for i in range(len(rings))}
    for members in by_nid.values():
        for a in members:
            for b in members:
                if a != b:
                    adj[a].add(b)
    seen: set = set()
    comps = []
    for i in range(len(rings)):
        if i in seen:
            continue
        stack, comp = [i], []
        seen.add(i)
        while stack:
            k = stack.pop()
            comp.append(k)
            for j in adj[k]:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
        comps.append((comp, adj))
    return comps


def _longest_path(comp, adj, rings) -> list:
    """The component's own longest run — double BFS (graph diameter), the
    standard tree heuristic, applied to a graph that is a corridor chain in
    all but the rare loop.  A loop simply yields its longest walk."""
    def _bfs(src):
        dist = {src: 0.0}
        prev = {src: None}
        q = deque([src])
        far, fard = src, 0.0
        while q:
            k = q.popleft()
            for j in adj[k]:
                if j in dist or j not in comp_set:
                    continue
                dist[j] = dist[k] + math.dist(rings[k]["c"], rings[j]["c"])
                prev[j] = k
                if dist[j] > fard:
                    far, fard = j, dist[j]
                q.append(j)
        return far, prev

    comp_set = set(comp)
    if len(comp) == 1:
        return list(comp)
    a, _ = _bfs(comp[0])
    b, prev = _bfs(a)
    path = []
    k = b
    while k is not None:
        path.append(k)
        k = prev[k]
    path.reverse()
    return path


def _station_on_spine(spine, cum, p) -> Optional[float]:
    """The point's arclength station along the chain's SPINE polyline —
    its projection onto the nearest segment.  Stationing by projection,
    not by ring index, is what makes a LONG corridor rect (one ring
    spanning hundreds of metres) carry a profile at all: its own vertices
    spread along the run instead of collapsing to one centroid."""
    best_s, best_d = None, None
    for k in range(len(spine) - 1):
        ax, ay = spine[k]
        bx, by = spine[k + 1]
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        if L2 <= 1e-12:
            continue
        t = ((p[0] - ax) * vx + (p[1] - ay) * vy) / L2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        qx, qy = ax + t * vx, ay + t * vy
        d = math.hypot(p[0] - qx, p[1] - qy)
        if best_d is None or d < best_d:
            best_d, best_s = d, cum[k] + t * math.sqrt(L2)
    return best_s


def _chain_read(path_idx, rings, bin_m: float = DEFAULT_BIN_M) -> dict:
    """THE reading for one chain — the profile and its numbers.

    THE PROFILE IS BINNED BY VERTEX STATION, not by ring: every road
    vertex of the chain is projected onto the chain's spine (the ring-
    centroid polyline walked along the component's longest path) and the
    profile is the per-bin MEDIAN emitted value and MEDIAN DEM.  A ring's
    own median would make a kilometre-long corridor rect one station and
    its profile meaningless; a bin is a fixed length of ROAD, so two arms
    and two chains are read at one granularity.
    """
    spine = [rings[i]["c"] for i in path_idx]
    cum = [0.0]
    for a, b in zip(spine, spine[1:]):
        cum.append(cum[-1] + math.dist(a, b))

    dev_v, cut_v, fill_v = [], [], []
    samples: list = []
    for i in path_idx:
        for xy, ll, z, d in zip(rings[i]["xy"], rings[i]["ll"],
                                rings[i]["z"], rings[i]["d"]):
            if z is None or d is None:
                continue
            dev_v.append(abs(z - d))
            cut_v.append(d - z)
            fill_v.append(z - d)
            s = _station_on_spine(spine, cum, xy)
            if s is not None:
                samples.append((s, z, d, ll))

    bins: dict = {}
    for s, z, d, ll in samples:
        k = int(s // bin_m)
        bins.setdefault(k, []).append((s, z, d, ll))
    keys = sorted(bins)
    st, lev, gnd, lls = [], [], [], []
    for k in keys:
        rows = bins[k]
        # THE BIN'S STATION IS ITS MEMBERS' MEAN, not the bin centre: road
        # vertices are not evenly spaced (a corridor rect contributes four
        # corners and nothing between), and pricing a grade over the bin
        # CENTRE would read a step across two half-empty bins as a slope
        # it never had.
        st.append(sum(r[0] for r in rows) / len(rows))
        lev.append(ADR._median([r[1] for r in rows]))
        gnd.append(ADR._median([r[2] for r in rows]))
        lls.append(rows[0][3])
    if len(st) < 2:                                        # pragma: no cover
        st = [0.0, cum[-1]]
        lev = [rings[path_idx[0]]["level"], rings[path_idx[-1]]["level"]]
        gnd = [rings[path_idx[0]]["ground"], rings[path_idx[-1]]["ground"]]
        lls = [rings[path_idx[0]]["ll"][0], rings[path_idx[-1]]["ll"][0]]

    steps = []
    for k in range(len(st) - 1):
        ds = st[k + 1] - st[k]
        if ds <= 1e-6:
            continue
        steps.append({
            "s0": st[k], "s1": st[k + 1], "ds": ds,
            "eg": (lev[k + 1] - lev[k]) / ds,
            "dg": (gnd[k + 1] - gnd[k]) / ds,
        })
    followable = [s for s in steps if abs(s["dg"]) <= ROAD_CAP + 1e-12]

    dem_relief = (max(gnd) - min(gnd)) if gnd else 0.0
    emit_relief = (max(lev) - min(lev)) if lev else 0.0
    return {
        "wids": [rings[i]["wid"] for i in path_idx],
        "roles": sorted({rings[i]["role"] for i in path_idx}),
        "rings": len(path_idx),
        "bin_m": bin_m,
        "bins": len(st),
        "span_m": cum[-1],
        "station_m": st,
        "emitted_m": lev,
        "dem_m": gnd,
        "ll": [ll for ll in lls],
        "ring_ll": [rings[i]["ll"][0] for i in path_idx],
        # Every vertex lat/lon of the chain, for PLACE matching only.
        # Underscored so ``--json`` never carries it (a site lookup needs
        # the full population; a report does not).
        "_vll": [r[3] for r in samples],
        "dem_relief_m": dem_relief,
        "emitted_relief_m": emit_relief,
        "follow_ratio": (emit_relief / dem_relief) if dem_relief > 1e-9 else None,
        "cut_max_m": max(cut_v) if cut_v else None,
        "fill_max_m": max(fill_v) if fill_v else None,
        "dev_median_m": ADR._median(dev_v) if dev_v else None,
        "dev_p95_m": ADR._pct(dev_v, 95.0) if dev_v else None,
        "vertices": len(dev_v),
        "emitted_grade_max_pct": (100.0 * max(abs(s["eg"]) for s in steps)
                                  if steps else None),
        "dem_grade_max_pct": (100.0 * max(abs(s["dg"]) for s in steps)
                              if steps else None),
        "emitted_grade_median_pct": (100.0 * ADR._median(
            [abs(s["eg"]) for s in steps]) if steps else None),
        "dem_grade_median_pct": (100.0 * ADR._median(
            [abs(s["dg"]) for s in steps]) if steps else None),
        "steps": len(steps),
        "dem_followable_pct": (100.0 * len(followable) / len(steps)
                               if steps else None),
        "deepest_cut_ll": _deepest_ll(path_idx, rings),
    }


def _deepest_ll(path_idx, rings):
    worst, worst_ll = None, None
    for i in path_idx:
        for ll, z, d in zip(rings[i]["ll"], rings[i]["z"], rings[i]["d"]):
            if z is None or d is None:
                continue
            if worst is None or (d - z) > worst:
                worst, worst_ll = d - z, ll
    return None if worst_ll is None else [round(worst_ll[0], 9),
                                          round(worst_ll[1], 9),
                                          round(float(worst), 3)]


def read_patch(patch: Path, *, dem_source: str = "airport-inset",
               dem_at: "Optional[Callable]" = None,
               bin_m: float = DEFAULT_BIN_M) -> dict:
    """THE reading for one patch: every road chain, unranked.

    ``dem_at`` (lat, lon) -> metres or None: injected by the twin so the
    law can be stated on a synthetic surface.  Production passes None and
    gets the cached inset through ``apron_drape_read``'s own loaders.
    """
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
    ll_to_m = CG._ll_to_m_factory(
        nodes, anchor=tuple(anchor) if anchor else None)

    dem_path = dem_origin = None
    if dem_at is None:
        tile_lat, tile_lon = ADR._tile_of(nodes)
        icao = patch.name.split("_")[0].upper()
        dem, dem_path, dem_origin = ADR._load_dem(
            tile_lat, tile_lon, icao, dem_source)
        if dem is None:
            raise SystemExit(
                f"{patch}: no {dem_source} DEM cached for {icao} "
                f"(tile {tile_lat:+03d}{tile_lon:+04d}) — refusing to "
                f"substitute the other surface; the two are not comparable")

        def dem_at(lat, lon, _d=dem, _tl=tile_lat, _tn=tile_lon):
            return ADR._dem_at(_d, lat, lon, _tl, _tn)

    rings = _road_rings(patch, dem_at, ll_to_m, nodes, ways)
    chains = []
    for comp, adj in _components(rings):
        p = _longest_path(comp, adj, rings)
        if len(p) < 2:
            continue
        chains.append(_chain_read(p, rings, bin_m=bin_m))
    return {
        "patch": str(patch), "dem_source": dem_source,
        "dem_path": dem_path, "dem_origin": dem_origin,
        "road_rings": len(rings), "chains": chains, "bin_m": bin_m,
        "road_cap_pct": 100.0 * ROAD_CAP,
        "sidecar_anchor": anchor,
    }


def chain_at_site(read: dict, lat: float, lon: float,
                  radius_m: float = DEFAULT_SITE_RADIUS_M):
    """The chain whose emitted vertices reach nearest the named point, or
    None.  Sites are matched by PLACE, never by way id — ids are
    arm-dependent (``arm_site_read``'s own frame rule)."""
    best, bestd = None, None
    for ch in read["chains"]:
        for (la, lo) in (ch.get("_vll") or ch["ll"]):
            d = math.hypot((la - lat) * 111320.0,
                           (lo - lon) * 111320.0 * math.cos(math.radians(lat)))
            if bestd is None or d < bestd:
                best, bestd = ch, d
    if best is None or bestd is None or bestd > radius_m:
        return None, bestd
    return best, bestd


def rank(read: dict, *, min_relief_m: float = DEFAULT_MIN_RELIEF_M,
         min_span_m: float = DEFAULT_MIN_SPAN_M, top: int = 5) -> list:
    """The HILL SITES of a patch: chains crossing at least ``min_relief_m``
    of DEM, longest first — the spec's own site-selection rule."""
    sel = [c for c in read["chains"]
           if (c["dem_relief_m"] or 0.0) >= min_relief_m
           and (c["span_m"] or 0.0) >= min_span_m]
    sel.sort(key=lambda c: -(c["span_m"] or 0.0))
    return sel[:top]


def _f(v, w=8, p=3) -> str:
    return "-".rjust(w) if v is None else f"{v:{w}.{p}f}"


_ROWS = (
    ("span_m", "chain span (m, along path)"),
    ("dem_relief_m", "DEM relief across chain (m)"),
    ("emitted_relief_m", "emitted relief (m)"),
    ("follow_ratio", "FOLLOW RATIO (emitted/DEM relief)"),
    ("cut_max_m", "deepest cutting DEM-emitted (m)"),
    ("fill_max_m", "highest fill emitted-DEM (m)"),
    ("dev_median_m", "|emitted-DEM| median (m)"),
    ("dev_p95_m", "  ... p95"),
    ("emitted_grade_max_pct", "emitted grade max (%)"),
    ("emitted_grade_median_pct", "emitted grade median (%)"),
    ("dem_grade_max_pct", "DEM grade max (%)"),
    ("dem_grade_median_pct", "DEM grade median (%)"),
    ("dem_followable_pct", "DEM steps within road cap (%)"),
)


def print_site(name: str, per_arm: list, cap_pct: float,
               profile: bool = False) -> None:
    print(f"\n=== SITE {name} ===")
    for label, ch, dist in per_arm:
        if ch is None:
            print(f"    arm {label:16s}: NO ROAD CHAIN within the site "
                  f"radius (nearest {_f(dist, 6, 1)} m) — reported, never zero")
        else:
            print(f"    arm {label:16s}: {ch['rings']} ring(s), "
                  f"{ch['steps']} step(s), nearest vertex {_f(dist, 6, 1)} m, "
                  f"roles={','.join(ch['roles'])}")
    arms = [(l, c) for (l, c, _d) in per_arm]
    head = f"  {'METRIC':36s}" + "".join(f" {l[:14]:>14s}" for l, _ in arms)
    print(head)
    print("  " + "-" * (len(head) - 2))
    base = arms[0][1]
    for key, label in _ROWS:
        line = f"  {label:36s}" + "".join(
            f" {_f(c.get(key) if c else None, 14):>14s}" for _, c in arms)
        print(line)
    if base is not None and base.get("deepest_cut_ll"):
        la, lo, dm = base["deepest_cut_ll"]
        print(f"  deepest cut (first arm): {dm:.2f} m at {la},{lo}")
    print(f"  road cap = {cap_pct:.1f} %  (SERVICE_ROAD_MAX_GRADE)")
    if profile:
        for label, ch, _d in per_arm:
            if ch is None:
                continue
            print(f"\n  -- profile, arm {label} "
                  f"(station m / emitted m / DEM m / emitted-DEM) --")
            for s, z, d in zip(ch["station_m"], ch["emitted_m"], ch["dem_m"]):
                print(f"     {s:9.1f} {z:9.2f} {d:9.2f} {z - d:+8.2f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("patches", nargs="+", type=Path,
                    help="control first; later patches are compared to it")
    ap.add_argument("--dem-source", default="airport-inset",
                    choices=("airport-inset", "base"),
                    help="'airport-inset' (default) is THE SURFACE "
                         "PRODUCTION GRADES ON; two arms on two sources "
                         "are NOT comparable")
    ap.add_argument("--rank", action="store_true",
                    help="DISCOVERY: list the patch's hill chains "
                         "(way ids + lat/lon), longest first")
    ap.add_argument("--min-relief", type=float, default=DEFAULT_MIN_RELIEF_M)
    ap.add_argument("--min-span", type=float, default=DEFAULT_MIN_SPAN_M)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--site", action="append", default=[],
                    metavar="NAME=LAT,LON",
                    help="a named place; the chain reaching it is read in "
                         "every arm")
    ap.add_argument("--site-radius", type=float,
                    default=DEFAULT_SITE_RADIUS_M)
    ap.add_argument("--bin-m", type=float, default=DEFAULT_BIN_M,
                    help="profile bin along the chain (m); two arms on "
                         "two bin sizes are NOT comparable")
    ap.add_argument("--profile", action="store_true",
                    help="print each arm's station/emitted/DEM profile")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)

    os.environ.setdefault("O4_SUPPRESS_UI", "1")
    reads = [read_patch(p, dem_source=a.dem_source, bin_m=a.bin_m)
             for p in a.patches]
    base = reads[0]
    print("=== ROAD TERRAIN CONFORMANCE ===")
    print(f"  DEM source: {base['dem_source']}  "
          f"({base.get('dem_origin') or 'n/a'})")
    print("  chain = road rings joined by SHARED NODE IDs, walked along "
          "the component's longest path; every road VERTEX is stationed "
          f"by projection onto that spine and the profile is the median "
          f"emitted / median DEM per {base['bin_m']:g} m bin")
    print("  NOT defect counts and never adjudicated — a CONFORMANCE "
          "reading, comparable arm-to-arm on identical options only.")
    for r in reads:
        print(f"    arm: {Path(r['patch']).name}  "
              f"road_rings={r['road_rings']} chains={len(r['chains'])}")

    if a.rank:
        for r in reads:
            print(f"\n=== HILL CHAINS — {Path(r['patch']).name} "
                  f"(DEM relief >= {a.min_relief:g} m, span >= "
                  f"{a.min_span:g} m, longest first) ===")
            top = rank(r, min_relief_m=a.min_relief,
                       min_span_m=a.min_span, top=a.top)
            if not top:
                print("    none — reported, never zero-by-omission")
            for k, ch in enumerate(top, 1):
                la, lo = ch["ll"][0]
                lb, lob = ch["ll"][-1]
                print(f"  [{k}] span {ch['span_m']:8.1f} m  rings "
                      f"{ch['rings']:3d}  DEM relief "
                      f"{ch['dem_relief_m']:6.2f} m  emitted relief "
                      f"{ch['emitted_relief_m']:6.2f} m  follow "
                      f"{_f(ch['follow_ratio'], 5, 2)}")
                print(f"      cut_max {_f(ch['cut_max_m'], 6, 2)} m  "
                      f"fill_max {_f(ch['fill_max_m'], 6, 2)} m  "
                      f"emitted grade max "
                      f"{_f(ch['emitted_grade_max_pct'], 5, 2)} %  "
                      f"DEM grade max "
                      f"{_f(ch['dem_grade_max_pct'], 5, 2)} %  "
                      f"followable {_f(ch['dem_followable_pct'], 5, 1)} %")
                print(f"      ends {la},{lo} -> {lb},{lob}")
                print(f"      ways {' '.join(ch['wids'][:12])}"
                      f"{' ...' if len(ch['wids']) > 12 else ''}")
                if ch.get("deepest_cut_ll"):
                    dla, dlo, ddm = ch["deepest_cut_ll"]
                    print(f"      deepest cut {ddm:.2f} m at {dla},{dlo}")

    for spec in a.site:
        if "=" not in spec or "," not in spec:
            raise SystemExit(f"--site {spec!r}: expected NAME=LAT,LON")
        name, ll = spec.split("=", 1)
        lat, lon = (float(v) for v in ll.split(",", 1))
        per_arm = []
        for r in reads:
            ch, dist = chain_at_site(r, lat, lon, a.site_radius)
            per_arm.append((Path(r["patch"]).name, ch, dist))
        print_site(name, per_arm, base["road_cap_pct"], profile=a.profile)

    if a.json:
        _dump = [{k: ({kk: vv for kk, vv in c.items()
                       if not kk.startswith("_")} if isinstance(c, dict) else c)
                  for k, c in r.items() if k != "chains"}
                 | {"chains": [{kk: vv for kk, vv in c.items()
                                if not kk.startswith("_")}
                               for c in r["chains"]]}
                 for r in reads]
        a.json.write_text(json.dumps(_dump, indent=2))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
