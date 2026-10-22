"""ROAD-COURSE PROFILE — the grade a car feels along a mapped road over an
emitted patch (lane nlwfroad100, issue #100; promoted on its second use per
RULINGS `7e90032`).

For each OSM road way (``Airport.osm_ways`` of a ``v2_solve_replay``
capture) the course is sampled every ``--step`` metres; each sample reads the
PATCH surface (each emitted ``shapeID`` ring constrained-Delaunay
triangulated, z interpolated) where it lies inside a ring, else the capture's
DEM (what the mesh drapes outside the patch).  Printed per way: length, z
range, samples on the patch, and the five worst grades over ``--window``
metres (>= 30 m apart) with lat/lon.  ``--detail WAY:S0:S1`` lists every
sample of one stretch.

``--on-patch`` (spec road-exit-corridor §4 (1) v2): also the worst ON-PATCH
window (every sample of it on the patch — the acceptance read), the worst
PATCH-EDGE window (some samples on the patch, some on the DEM), and per
``road_exit:*`` corridor its END: the ring vertices at the far chainage
from its mouth (the vertices it shares with a ``graded_strip`` ring) and
their worst ``|z - DEM|`` (bar: within ``cockpit.visual_m``).

``--reach M`` (issue #1246, owner RULINGS 2026-10-22g) reads EVERY mapped
road of a ribbon class (``rules.toml [osm_roads] ribbon_highways``, at
grade, of the mint's feeds ``model.planar.OSM_RIBBON_FEEDS``) meeting the
aerodrome boundary buffered ``M`` metres: the metres of
it inside that reach, the metres of those on the patch, and every
PATCH-EDGE STEP along those ways — ``|dz|`` between the two consecutive
samples where the course leaves the patch for the DEM — worst five with
lat/lon and the count over 0.5 m (the ground bar), and apart the steps AT
THE REACH EDGE (the terrain-side sample outside the reach).  A step within 15 m of
a mapped STRUCTURE (any way tagged bridge / tunnel / covered, or a layer
other than 0) is counted apart: the course goes onto a deck or under a
roof there, not onto the terrain.  ``--ways`` is then optional.

A WELD GAP IS PATCH (lane roads609e): a sample off every ring but inside
the patch's CLOSING by ``--gap`` metres (default 1.5 — three identity
cells, the most a ribbon the arrangement could not weld to a rim node
stands off it; a crack between two decimated rings is centimetres) is read
at the nearest ring's level and labelled ``gap``: no vertex stands in such
a sliver, so the mesh spans it between its sides and never drapes the DEM
there.  MEASURED before (KCLT): way ``-6064``, one sample in the 0.7 m
sliver between a road end at 222.54 m and the pad it runs into at 222.68 m
read the DEM (218.32 m) — "44.3 % at the patch edge" over a surface that
steps 0.14 m; way ``-8190``, two samples 0.07 / 0.09 m outside every ring
on the seam of three road faces — "41.4 %".  A true patch edge is not
closed: the closing of a straight edge is the edge.

It is an INSTRUMENT: the triangulation approximates the mesher's, it prices
no law and counts no defects (``harness/census.py`` does).  Measured basis
(NLWF, capture base d5173ad6): road -1 along 07/25, 15.0 % -> 2.3 % with the
zone-class join (db463ea0); road -3 behind the terminal 66 % band->DEM step.

    venv/bin/python tools/road_course_profile.py PATCH.osm --capture CAP.pkl \
        --ways -3,-1 [--detail -3:1880:2240]
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``, ahead of every other import.
# Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import pickle
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import shapely
import shapely.ops
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def patch_surface(patch: str, crs: str):
    """(triangles, STRtree) of the patch's shape rings in the frame."""
    T = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    root = ET.parse(patch).getroot()
    N = {}
    for n in root.iter("node"):
        alt = n.find("tag[@k='alt_abs']")
        if alt is None:
            continue
        x, y = T.transform(float(n.get("lon")), float(n.get("lat")))
        N[n.get("id")] = (x, y, float(alt.get("v")))
    tris = []
    for w in root.iter("way"):
        if w.find("tag[@k='shapeID']") is None:
            continue
        P = [N[nd.get("ref")] for nd in w.iter("nd") if nd.get("ref") in N]
        if len(P) < 4:
            continue
        if P[0][:2] == P[-1][:2]:
            P = P[:-1]
        zmap = {(round(p[0], 3), round(p[1], 3)): p[2] for p in P}
        poly = Polygon([p[:2] for p in P])
        if not poly.is_valid:
            poly = poly.buffer(0)
        for tr in shapely.get_parts(shapely.constrained_delaunay_triangles(poly)):
            cs = list(tr.exterior.coords)[:3]
            # a ring that touches itself is repaired (``buffer(0)``) and may
            # carry a corner the ring has no node at: it takes the nearest
            # ring node's level instead of dropping the triangle (a dropped
            # triangle read the DEM inside a face — lane roads609e, KCLT
            # ``-8202``: "41 % at the patch edge" in the middle of a road)
            zs = [zmap.get((round(x, 3), round(y, 3))) for x, y in cs]
            for i, (x, y) in enumerate(cs):
                if zs[i] is None:
                    zs[i] = min(P, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)[2]
            tris.append((tr, cs, zs))
    return tris, shapely.STRtree([t[0] for t in tris])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch")
    ap.add_argument("--capture", required=True, help="v2_solve_replay --capture pickle")
    ap.add_argument("--ways", default="", help="comma-separated OSM way ids")
    ap.add_argument("--reach", type=float, default=None,
                    help="read every ribbon-class road within the boundary + M metres")
    ap.add_argument("--step", type=float, default=2.0)
    ap.add_argument("--window", type=float, default=10.0)
    ap.add_argument("--detail", default=None, help="WAY:S0:S1")
    ap.add_argument("--gap", type=float, default=1.5,
                    help="widest weld gap read as patch (m; 0 = off)")
    ap.add_argument("--on-patch", action="store_true",
                    help="worst on-patch / patch-edge windows + corridor-end |z-DEM|")
    a = ap.parse_args(argv)
    cap = pickle.load(open(a.capture, "rb"))
    airport = cap["airport"]
    dem, crs = airport.dem, airport.frame.crs
    Ti = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    tris, tree = patch_surface(a.patch, crs)

    def zat(x, y):
        p = Point(x, y)
        for i in tree.query(p):
            tr, cs, zs = tris[i]
            if tr.covers(p):
                (x1, y1), (x2, y2), (x3, y3) = cs
                det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
                l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
                l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
                return l1 * zs[0] + l2 * zs[1] + (1 - l1 - l2) * zs[2], "patch"
        return float(dem.z(x, y)), "dem"

    def zon(L, s):
        """``zat`` at chainage ``s`` of ``L``, a weld gap read as patch."""
        p = L.interpolate(s)
        z, src = zat(p.x, p.y)
        if src == "dem" and a.gap > 0.0:
            near = [tris[i] for i in tree.query(p.buffer(a.gap))]
            if near and shapely.union_all([t[0] for t in near]).buffer(
                    0.5 * a.gap).buffer(-0.5 * a.gap + 1e-6).covers(p):
                tr = min(near, key=lambda t: t[0].distance(p))
                q = shapely.ops.nearest_points(tr[0], p)[0]
                # a hair inside the triangle, so its own plane reads it
                c = tr[0].centroid
                z2, src2 = zat(q.x + 1e-6 * (c.x - q.x), q.y + 1e-6 * (c.y - q.y))
                if src2 == "patch":
                    return p, z2, "gap"
        return p, z, src

    ways = {w.id: w for w in airport.osm_ways}
    k = max(1, int(round(a.window / a.step)))
    if a.reach is not None:
        _reach_read(airport, a.reach, a.step, zon, Ti)
    for wid in (int(s) for s in a.ways.split(",") if s.strip()):
        L = LineString(ways[wid].points)
        prof = []
        for i in range(int(L.length / a.step) + 1):
            p, z, src = zon(L, i * a.step)
            prof.append((i * a.step, p.x, p.y, z, src))
        worst = sorted(((abs(prof[i + k][3] - prof[i][3]) / (k * a.step), prof[i])
                        for i in range(len(prof) - k)), key=lambda r: -r[0])
        zs = [q[3] for q in prof]
        print(f"road {wid} {ways[wid].tags.get('highway')} len {L.length:.0f} m  "
              f"z {min(zs):.2f}..{max(zs):.2f}  patch-samples "
              f"{sum(q[4] != 'dem' for q in prof)}/{len(prof)}")
        shown: list[float] = []
        for g, q in worst:
            if any(abs(q[0] - s) < 30 for s in shown):
                continue
            shown.append(q[0])
            lon, lat = Ti.transform(q[1], q[2])
            print(f"   grade over {a.window:.0f} m {100 * g:5.1f}%  s={q[0]:.0f}  "
                  f"z={q[3]:.2f} ({q[4]})  at {lat:.6f}, {lon:.6f}")
            if len(shown) >= 5:
                break
        if a.on_patch:
            for label, keep in (("ON-PATCH", lambda srcs: "dem" not in srcs),
                                ("PATCH-EDGE", lambda srcs: "dem" in srcs
                                 and len(set(srcs)) > 1)):
                best = None
                for i in range(len(prof) - k):
                    if not keep([prof[j][4] for j in range(i, i + k + 1)]):
                        continue
                    g = abs(prof[i + k][3] - prof[i][3]) / (k * a.step)
                    if best is None or g > best[0]:
                        best = (g, prof[i])
                if best is None:
                    print(f"   {label}: no window")
                    continue
                g, q = best
                lon, lat = Ti.transform(q[1], q[2])
                print(f"   {label} worst over {a.window:.0f} m {100 * g:5.1f}%  "
                      f"s={q[0]:.0f}  at {lat:.6f}, {lon:.6f}")
    if a.on_patch:
        _corridor_ends(a.patch, crs, dem, Ti, [LineString(w.points) for w in airport.osm_ways
                                              if w.tags.get("highway")])
    if a.detail:
        wid, s0, s1 = a.detail.split(":")
        L = LineString(ways[int(wid)].points)
        for s in np.arange(float(s0), float(s1), 2 * a.step):
            p, z, src = zon(L, s)
            lon, lat = Ti.transform(p.x, p.y)
            print(f"  s={s:.0f} {lat:.6f},{lon:.6f} z={z:.2f} {src} dem={dem.z(p.x, p.y):.2f}")
    return 0


def _reach_read(airport, reach_m: float, step: float, zon, Ti) -> None:
    """``--reach``: road metres in the boundary + ``reach_m``, on the patch,
    and the patch-edge steps along those roads (module doc)."""
    from shapely.ops import unary_union

    from auto_patch_v2.airport.road_ways import road_ways
    from auto_patch_v2.classify.evidence import polygon_from
    from auto_patch_v2.classify.rules import load_rules
    bs = [polygon_from(b.outer, b.holes) for b in getattr(airport, "boundaries", ())]
    bs = [b for b in bs if b is not None]
    if not bs:
        print("reach: the airport has no boundary (apt.dat 130)")
        return
    reach = unary_union(bs).buffer(reach_m, join_style="mitre", mitre_limit=2.0)
    shapely.prepare(reach)
    classes = set(load_rules().osm_roads.ribbon_highways)
    from auto_patch_v2.model.planar import OSM_RIBBON_FEEDS
    sel = [(w, ln) for w, ln in road_ways(airport.osm_ways)
           if (w.tags or {}).get("highway") in classes
           and getattr(w, "kind", "") in OSM_RIBBON_FEEDS and reach.intersects(ln)]
    structs = [LineString(w.points) for w in airport.osm_ways
               if len(w.points) >= 2 and _is_structure(w.tags or {})]
    struct = unary_union(structs).buffer(15.0) if structs else None
    if struct is not None:
        shapely.prepare(struct)
    total = on = 0.0
    steps = []
    for w, L in sel:
        prof = []
        for i in range(int(L.length / step) + 1):
            p, z, src = zon(L, i * step)
            inside = reach.covers(p)
            prof.append((p, z, src))
            if inside:
                total += step
                on += step if src != "dem" else 0.0
        for (p0, z0, s0), (p1, z1, s1) in zip(prof, prof[1:]):
            if (s0 == "dem") != (s1 == "dem"):
                q, d = (p1, p0) if s0 == "dem" else (p0, p1)
                at_struct = struct is not None and struct.covers(q)
                steps.append((abs(z1 - z0), w.id, q, reach.covers(d), at_struct))
    print(f"reach boundary+{reach_m:.0f} m: {len(sel)} roads, {total:.0f} m inside, "
          f"{on:.0f} m on the patch ({100.0 * on / total if total else 0.0:.1f} %)")
    steps.sort(key=lambda r: -r[0])
    ground = [r for r in steps if not r[4]]
    print(f"   patch-edge steps onto the terrain {len(ground)}, over 0.5 m "
          f"{sum(1 for r in ground if r[0] > 0.5)}; at a structure {len(steps) - len(ground)}, "
          f"over 0.5 m {sum(1 for r in steps if r[4] and r[0] > 0.5)}")
    edge = [r for r in ground if not r[3]]
    print(f"   AT THE REACH EDGE (the terrain side outside the reach) {len(edge)}, over "
          f"0.5 m {sum(1 for r in edge if r[0] > 0.5)}, worst "
          + (f"{edge[0][0]:.2f} m way {edge[0][1]} at "
             "{1:.6f}, {0:.6f}".format(*Ti.transform(edge[0][2].x, edge[0][2].y))
             if edge else "-"))
    for dz, wid, q, inside, _s in ground[:5]:
        lon, lat = Ti.transform(q.x, q.y)
        print(f"   step {dz:.2f} m  way {wid}  at {lat:.6f}, {lon:.6f}"
              f"  (terrain side {'inside' if inside else 'outside'} the reach)")


def _is_structure(tags: dict) -> bool:
    """A way the course leaves the terrain on: a deck, a bore or a roof."""
    return any(str(tags.get(k, "no")).lower() not in ("no", "") for k in
               ("bridge", "tunnel", "covered")) or str(tags.get("layer", "0")) not in ("0", "")


def _corridor_ends(patch: str, crs: str, dem, Ti, roads) -> None:
    """Per ``road_exit:*`` corridor: its far END vertices (the ring
    vertices within 1 m of the extreme chainage away from its mouth along
    the nearest OSM road) and their worst ``|z - DEM|``."""
    T = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    root = ET.parse(patch).getroot()
    N = {}
    for n in root.iter("node"):
        alt = n.find("tag[@k='alt_abs']")
        if alt is None:
            continue
        x, y = T.transform(float(n.get("lon")), float(n.get("lat")))
        N[n.get("id")] = (x, y, float(alt.get("v")))
    strip_nodes: set = set()
    exits = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        refs = [nd.get("ref") for nd in w.iter("nd") if nd.get("ref") in N]
        if tags.get("role") == "graded_strip":
            strip_nodes.update(refs)
        if (tags.get("ref") or "").startswith("road_exit:"):
            exits.append((tags["ref"], refs))
    for ref, refs in exits:
        mouth = [r for r in refs if r in strip_nodes]
        if not mouth or not roads:
            print(f"   {ref}: no mouth on a graded_strip ring")
            continue
        mx = sum(N[r][0] for r in mouth) / len(mouth)
        my = sum(N[r][1] for r in mouth) / len(mouth)
        road = min(roads, key=lambda L: L.distance(Point(mx, my)))
        ch = {r: road.project(Point(N[r][0], N[r][1])) for r in refs}
        mch = [ch[r] for r in mouth]
        # the free end: the chainage extreme with no mouth vertex within 3 m
        # (a corridor with a mouth at both extremes has no free end)
        ends = []
        for ext in (min(ch.values()), max(ch.values())):
            if all(abs(ext - m) > 3.0 for m in mch):
                ends.append(ext)
        if not ends:
            print(f"   corridor {ref}: a mouth at both ends (no free end)")
            continue
        s0 = sum(mch) / len(mch)
        ext = max(ends, key=lambda e: abs(e - s0))
        smax = abs(ext - s0)
        end = [r for r in refs if abs(ch[r] - ext) <= 1.0]
        worst = max(end, key=lambda r: abs(N[r][2] - float(dem.z(N[r][0], N[r][1]))))
        dz = N[worst][2] - float(dem.z(N[worst][0], N[worst][1]))
        lon, lat = Ti.transform(N[worst][0], N[worst][1])
        print(f"   corridor {ref} END at {smax:.0f} m from its mouth: "
              f"|z - DEM| {abs(dz):.2f} m ({dz:+.2f})  at {lat:.6f}, {lon:.6f}")


if __name__ == "__main__":
    raise SystemExit(main())
