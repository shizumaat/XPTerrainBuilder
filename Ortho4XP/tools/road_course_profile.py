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

It is an INSTRUMENT: the triangulation approximates the mesher's, it prices
no law and counts no defects (``harness/census.py`` does).  Measured basis
(NLWF, capture base d5173ad6): road -1 along 07/25, 15.0 % -> 2.3 % with the
zone-class join (db463ea0); road -3 behind the terminal 66 % band->DEM step.

    venv/bin/python tools/road_course_profile.py PATCH.osm --capture CAP.pkl \
        --ways -3,-1 [--detail -3:1880:2240]
"""
from __future__ import annotations

import argparse
import pickle
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import shapely
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
            try:
                zs = [zmap[(round(x, 3), round(y, 3))] for x, y in cs]
            except KeyError:
                continue
            tris.append((tr, cs, zs))
    return tris, shapely.STRtree([t[0] for t in tris])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch")
    ap.add_argument("--capture", required=True, help="v2_solve_replay --capture pickle")
    ap.add_argument("--ways", required=True, help="comma-separated OSM way ids")
    ap.add_argument("--step", type=float, default=2.0)
    ap.add_argument("--window", type=float, default=10.0)
    ap.add_argument("--detail", default=None, help="WAY:S0:S1")
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

    ways = {w.id: w for w in airport.osm_ways}
    k = max(1, int(round(a.window / a.step)))
    for wid in (int(s) for s in a.ways.split(",")):
        L = LineString(ways[wid].points)
        prof = []
        for i in range(int(L.length / a.step) + 1):
            p = L.interpolate(i * a.step)
            z, src = zat(p.x, p.y)
            prof.append((i * a.step, p.x, p.y, z, src))
        worst = sorted(((abs(prof[i + k][3] - prof[i][3]) / (k * a.step), prof[i])
                        for i in range(len(prof) - k)), key=lambda r: -r[0])
        zs = [q[3] for q in prof]
        print(f"road {wid} {ways[wid].tags.get('highway')} len {L.length:.0f} m  "
              f"z {min(zs):.2f}..{max(zs):.2f}  patch-samples "
              f"{sum(q[4] == 'patch' for q in prof)}/{len(prof)}")
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
    if a.detail:
        wid, s0, s1 = a.detail.split(":")
        L = LineString(ways[int(wid)].points)
        for s in np.arange(float(s0), float(s1), 2 * a.step):
            p = L.interpolate(s)
            z, src = zat(p.x, p.y)
            lon, lat = Ti.transform(p.x, p.y)
            print(f"  s={s:.0f} {lat:.6f},{lon:.6f} z={z:.2f} {src} dem={dem.z(p.x, p.y):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
