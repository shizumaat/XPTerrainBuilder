#!/usr/bin/env python
"""Visualise how a building's FLAT SEAT level is chosen from the reach band.

``build_building_seats`` (route_profile/anchors.py) seats each airside building
FLAT at the MEDIAN of ``reach_band_sampler.band(x, y)[1]`` (the ceiling) taken
over the building's WHOLE exterior ring, clamped to DEM.  When the band ceiling
varies a lot around the ring (the side facing the taxi route is LOW, the far side
is HIGH), the whole-ring median can seat the pad well ABOVE what its taxi-facing
FRONTAGE can reach — over-pinning the apron in front of it (the CYXY A2-end apron
cliff: building15 seated 709.4 while its frontage band ceiling is 707.6).

This tool emits a KML that shows, for one building:
  * the building outline (name carries the current seat level),
  * every ring vertex as a placemark labelled with its band ceiling,
  * the FRONTAGE edge — the building edge whose midpoint is closest to the
    serving taxi centerline (``--frontage`` flat side) — highlighted,
  * the serving taxi centerline (the one ``_nearest_visible_centerline`` picks,
    exactly as the seat logic does), and
  * the binding reach route from its runway contact to the frontage midpoint.

and PRINTS the sorted ring ceilings with the whole-ring median (what is used
today) vs the frontage-only median/min (the candidate fix), so you can see
whether the median is being taken over the wrong part of the building.

BAND SOURCE: the ring ceilings are read from THE band of record — the object
the solve itself published (``publish_band_of_record``, RULINGS 2026-08-11b:
one band construction per solve, every consumer reads THAT band) and the one
``build_building_seats`` actually seated the pad from.  Only a layout that
never solved gets a rebuild, and then through ``trace_reach_route._live_band``
so this report and the route section share ONE construction.  The route
section (``trace_reach_route._binding_route``) reads that tool's own live-band
walk, which on a solved layout is a REBUILT frame — stated in the output.

Usage:
    venv/bin/python tools/trace_building_frontage.py CYXY --ref building15
    venv/bin/python tools/trace_building_frontage.py CYXY --ref building15 \
        --out /tmp/building15_frontage.kml
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "src"),
                os.path.join(os.path.dirname(__file__), ".."),
                os.path.join(os.path.dirname(__file__), "..", "tests")]


def _open_ring(coords):
    p = list(coords)
    if len(p) > 1 and p[0] == p[-1]:
        p = p[:-1]
    return p


#: The keys this tool reads out of ``trace_reach_route._binding_route``'s
#: report dict, and out of each per-side route record it carries.  Pinned by
#: ``tests/test_forensic_tools_instrument.py`` against the producer, so the
#: next contract change over there fails a TEST instead of a trace (the way
#: ``reach_band_for``'s tuple widening broke this tool on 2026-08-27).
BINDING_ROUTE_KEYS = ("band", "attachment_node", "attachment_pos",
                      "ceiling_at_node", "ceiling", "why_none", "error")
ROUTE_SIDE_KEYS = ("runway", "anchor_pos", "anchor_value", "path",
                   "cap_len", "plan_len_m")


def acquire_band(layout):
    """``(band, source)`` — THE live band, with its frame stated.

    ``source == "band-of-record"``: the solve's own construction
    (``band_of_record``), i.e. the very object ``build_building_seats``
    seated the pads from — never a rebuild (one-band-construction law,
    RULINGS 2026-08-11b).  ``source == "rebuilt"``: the layout never
    solved (a probe / hermetic fixture), so the FIRST construction is
    made — through ``trace_reach_route._live_band``, which caches per
    layout, so the route section below reads the SAME rebuild rather
    than minting a second one.  ``band`` may be ``None`` (no solver
    nodes)."""
    from auto_patch.elevation_per_surface.building_feasibility import (
        band_of_record)
    band = band_of_record(layout)
    if band is not None:
        return band, "band-of-record"
    from tools.trace_reach_route import _live_band
    _g, band, _prov = _live_band(layout)
    return band, "rebuilt"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("icao")
    ap.add_argument("--ref", required=True, help="building ref (e.g. building15)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or f"/tmp/{args.ref}_frontage.kml"

    from shapely.geometry import Point, LineString
    from conftest import xplane_root
    from auto_patch.pipeline import build_airport_pavement
    from auto_patch.config import VISIBLE_CHORD_CONNECT
    from auto_patch.elevation import _load_airport_dem, _sample_dem
    from auto_patch.elevation_per_surface.building_feasibility import (
        _nearest_visible_centerline, _pavement_visibility)
    from tools.trace_reach_route import _binding_route

    layout = build_airport_pavement(args.icao, xplane_root(),
                                    compute_elevations=True)
    s = next((s for s in layout.shapes
              if getattr(s, "ref", None) == args.ref), None)
    if s is None or s.polygon is None or s.polygon.is_empty:
        sys.exit(f"ref {args.ref} not found / no polygon")

    lat0, lon0 = layout.anchor
    tl, tn = int(math.floor(lat0)), int(math.floor(lon0))
    dem = _load_airport_dem(lat0, lon0)
    band, band_src = acquire_band(layout)
    if band is None:
        sys.exit(f"{args.icao}: no reach band — the layout carries no band "
                 "of record and the rebuild found no solver nodes (empty "
                 "G.pos).  A solved build publishes its band; a layout that "
                 "cannot produce one has nothing this tool can trace.")
    print(f"[band] source: {band_src}"
          + ("  (the solve's own construction — the one that seated the pads)"
             if band_src == "band-of-record" else
             "  (layout never solved; first construction, shared with the "
             "route section)"))

    # The serving centerline EXACTLY as the seat logic picks it (nearest VISIBLE
    # centerline to the centroid, not the geometric nearest).  The filter is
    # production's own (anchors.py seat path): ``TaxiCenterline.is_service``,
    # never the retired SVC name-prefix test — the name is a label only.
    tcls = [cl for cl in (getattr(layout, "apt_taxi_centerlines", None) or [])
            if cl.line is not None and not cl.line.is_empty
            and not cl.is_service]
    if not tcls:
        sys.exit(f"{args.icao}: no non-service taxi centerlines — nothing "
                 "serves this building")
    cls = [cl.line for cl in tcls]
    vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None
    c = s.polygon.centroid
    serving = (_nearest_visible_centerline(c, cls, vis) if vis is not None
               else min(cls, key=lambda L: L.distance(c)))

    # full centerline list WITH names, for per-vertex nearest-route reporting.
    cls_named = [(cl.line, str(cl.name or "?")) for cl in tcls]

    def _nearest_named(px, py):
        P = Point(px, py)
        nl = (_nearest_visible_centerline(P, cls, vis) if vis is not None
              else min(cls, key=lambda L: L.distance(P)))
        # name of the visible-nearest line, and the GEOMETRIC nearest (+dist).
        nm = next((n for (ln, n) in cls_named if ln is nl), "?")
        gln, gnm = min(((ln, n) for (ln, n) in cls_named),
                       key=lambda t: t[0].distance(P))
        return nm, nl.distance(P), gnm, gln.distance(P)

    ring = _open_ring(list(s.polygon.exterior.coords))
    ceils = []                       # (i, x, y, ceiling)
    for i, (x, y) in enumerate(ring):
        b = band(x, y)
        ceils.append((i, x, y, None if b is None else b[1]))

    # FRONTAGE = the building EDGE whose midpoint is closest to the serving
    # centerline (the flat side facing the taxi route).
    n = len(ring)
    best_e = None
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        midx, midy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        elen = math.hypot(x1 - x0, y1 - y0)
        d = serving.distance(Point(midx, midy))
        if best_e is None or d < best_e[0]:
            best_e = (d, i, (i + 1) % n, elen, (midx, midy))
    fd, fi0, fi1, flen, fmid = best_e

    # APRON-SHARED FRONTAGE: the ring vertices the fronting apron(s) actually
    # touch (share a node with) — the side the apron must grade up to.  This is
    # the operative frontage, distinct from "edge nearest the centerline".
    from auto_patch.layout import ROLE_APRON as _RA
    apron_keys = set()
    for a in layout.shapes:
        if (a.role != _RA or a.polygon is None or a.polygon.is_empty
                or a.polygon.distance(s.polygon) > 2.0):
            continue
        for (x, y) in _open_ring(list(a.polygon.exterior.coords)):
            apron_keys.add((round(x, 2), round(y, 2)))
    shared = [i for (i, x, y, _v) in ceils
              if (round(x, 2), round(y, 2)) in apron_keys]
    shared_vals = sorted(v for (i, _x, _y, v) in ceils
                         if v is not None and i in shared)

    cvals = sorted(v for (_i, _x, _y, v) in ceils if v is not None)

    def _median(vals):
        if not vals:
            return None
        m = len(vals)
        return (vals[m // 2] if m % 2
                else 0.5 * (vals[m // 2 - 1] + vals[m // 2]))

    ring_med = _median(cvals)
    front_vals = sorted(v for (i, _x, _y, v) in ceils
                        if v is not None and i in (fi0, fi1))
    de = _sample_dem(dem, tl, tn, *layout.m_to_ll(c.x, c.y))

    print(f"=== {args.ref} @ centroid ({c.x:.0f},{c.y:.0f})  DEM={de:.1f} ===")
    serv_nm = next((n for (ln, n) in cls_named if ln is serving), "?")
    print(f"serving centerline (nearest-visible to CENTROID) = {serv_nm}")
    print("ring vertex band ceilings + nearest taxi route per vertex:")
    for (i, x, y, v) in ceils:
        tag = "  <FRONTAGE" if i in (fi0, fi1) else ""
        vnm, vd, gnm, gd = _nearest_named(x, y)
        print(f"  v{i:<2} ({x:7.0f},{y:7.0f})  ceil="
              f"{'n/a' if v is None else f'{v:6.1f}'}"
              f"  vis-nearest={vnm}@{vd:.0f}m  geom-nearest={gnm}@{gd:.0f}m{tag}")
    print(f"\nsorted ring ceilings: {[round(v, 1) for v in cvals]}")
    print(f"WHOLE-RING median (USED TODAY) = {ring_med:.2f}"
          f"  -> seat = min(DEM {de:.1f}, {ring_med:.2f}) = "
          f"{min(de, ring_med):.2f}")
    print(f"FRONTAGE edge v{fi0}-v{fi1} (len {flen:.0f} m, "
          f"{fd:.0f} m from serving centerline)")
    print(f"  frontage ceilings = {[round(v, 1) for v in front_vals]}  "
          f"median={_median(front_vals):.2f}  min={min(front_vals):.2f}")
    print(f"APRON-SHARED frontage vertices = {shared}")
    if shared_vals:
        print(f"  apron-shared ceilings = {[round(v, 1) for v in shared_vals]}"
              f"  median={_median(shared_vals):.2f}  min={min(shared_vals):.2f}"
              f"   (<- the level the fronting apron must grade up to)")
    else:
        print("  (no apron shares a node with this building)")

    # Route forensics: trace_reach_route's OWN live-band walk.  On a solved
    # layout this is a REBUILT frame (different node space from the band of
    # record above) — a route detail here is a direction, not the build's
    # own number; the ceilings above ARE the build's own.
    r = _binding_route(layout, *fmid)

    # ---- KML ----
    R = 6378137.0
    cos0 = math.cos(math.radians(lat0))

    def ll(px, py):
        return (lon0 + math.degrees(px / (R * cos0)),
                lat0 + math.degrees(py / R))

    def line_coords(pts):
        return " ".join(f"{ll(px, py)[0]:.7f},{ll(px, py)[1]:.7f},0"
                        for (px, py) in pts)

    parts = ['<?xml version="1.0"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             f'<name>{args.ref} frontage / reach band</name>',
             '<Style id="bldg"><LineStyle><color>ff0000ff</color><width>2</width>'
             '</LineStyle><PolyStyle><color>3000ffff</color></PolyStyle></Style>',
             '<Style id="front"><LineStyle><color>ff00ff00</color><width>6</width>'
             '</LineStyle></Style>',
             '<Style id="cl"><LineStyle><color>ffffffff</color><width>3</width>'
             '</LineStyle></Style>',
             '<Style id="route"><LineStyle><color>ff00ffff</color><width>4</width>'
             '</LineStyle></Style>']

    # building polygon
    bring = line_coords(ring + [ring[0]])
    parts.append(
        f'<Placemark><name>{args.ref} seat={min(de, ring_med):.2f} '
        f'(ring-med {ring_med:.2f})</name><styleUrl>#bldg</styleUrl>'
        f'<Polygon><outerBoundaryIs><LinearRing><coordinates>{bring}'
        '</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>')
    # frontage edge
    parts.append(
        f'<Placemark><name>FRONTAGE v{fi0}-v{fi1} '
        f'med={_median(front_vals):.1f} min={min(front_vals):.1f}</name>'
        f'<styleUrl>#front</styleUrl><LineString><coordinates>'
        f'{line_coords([ring[fi0], ring[fi1]])}'
        '</coordinates></LineString></Placemark>')
    # serving centerline + every other centerline within 90 m of the building
    parts.append(
        f'<Placemark><name>SERVING centerline {serv_nm}</name>'
        f'<styleUrl>#cl</styleUrl><LineString><coordinates>'
        f'{line_coords(list(serving.coords))}'
        '</coordinates></LineString></Placemark>')
    parts.append('<Style id="cl2"><LineStyle><color>ffaaaaaa</color>'
                 '<width>2</width></LineStyle></Style>')
    for (ln, nm) in cls_named:
        if ln is serving or ln.distance(s.polygon) > 90:
            continue
        parts.append(
            f'<Placemark><name>{nm} ({ln.distance(s.polygon):.0f} m)</name>'
            f'<styleUrl>#cl2</styleUrl><LineString><coordinates>'
            f'{line_coords(list(ln.coords))}'
            '</coordinates></LineString></Placemark>')
    # apron(s) the building touches (the surface that must grade to it)
    parts.append('<Style id="apron"><LineStyle><color>ffff8800</color>'
                 '<width>2</width></LineStyle><PolyStyle><color>20ff8800'
                 '</color></PolyStyle></Style>')
    from auto_patch.layout import ROLE_APRON
    for a in layout.shapes:
        if (a.role != ROLE_APRON or a.polygon is None or a.polygon.is_empty
                or a.polygon.distance(s.polygon) > 2.0):
            continue
        ar = _open_ring(list(a.polygon.exterior.coords))
        parts.append(
            f'<Placemark><name>apron {a.polygon.area:.0f} m2</name>'
            f'<styleUrl>#apron</styleUrl><Polygon><outerBoundaryIs><LinearRing>'
            f'<coordinates>{line_coords(ar + [ar[0]])}'
            '</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>')
    # per-vertex ceiling labels
    for (i, x, y, v) in ceils:
        lo, la = ll(x, y)
        nm = f'v{i} {"n/a" if v is None else f"{v:.1f}"}'
        parts.append(f'<Placemark><name>{nm}</name><Point><coordinates>'
                     f'{lo:.7f},{la:.7f},0</coordinates></Point></Placemark>')
    # binding reach route to the frontage midpoint (rebuilt-frame forensics —
    # see the note at the _binding_route call above)
    if r.get("error"):
        print(f"\nroute section unavailable: {r['error']}")
    elif r.get("band") is None:
        print(f"\nno band at the FRONTAGE midpoint: "
              f"{r.get('why_none', 'off-net (within-shape law governs)')}")
    elif r.get("attachment_node") is None or not r.get("ceiling"):
        print("\nband present at the FRONTAGE midpoint but no recorded "
              "ceiling route to walk (no attachment / provenance side)")
    else:
        side = r["ceiling"]
        apos = side.get("anchor_pos") or (float("nan"), float("nan"))
        aval = side.get("anchor_value")
        ceil_at = r.get("ceiling_at_node")
        cap_len = side.get("cap_len") or {}
        print(f"\nbinding CEILING route to FRONTAGE midpoint "
              f"[rebuilt frame]: runway {side.get('runway', '?')} "
              f"anchor ({apos[0]:.0f},{apos[1]:.0f}) "
              f"value {'n/a' if aval is None else f'{aval:.1f}'}  "
              f"ceiling@attachment="
              f"{'n/a' if ceil_at is None else f'{ceil_at:.1f}'}")
        print(f"  per-cap length (m): "
              f"{{{', '.join(f'{k}%: {v:.0f}' for k, v in sorted(cap_len.items()))}}}")
        path = side.get("path") or []
        if len(path) >= 2:
            nm_ceil = "n/a" if ceil_at is None else f"{ceil_at:.1f}"
            parts.append(
                f'<Placemark><name>reach route -> frontage '
                f'(ceil {nm_ceil})</name>'
                f'<styleUrl>#route</styleUrl><LineString><coordinates>'
                f'{line_coords(path)}</coordinates></LineString></Placemark>')
        foot = r.get("attachment_pos")
        if foot is not None:
            lo, la = ll(*foot)
            parts.append(f'<Placemark><name>frontage foot (attachment)</name>'
                         f'<Point><coordinates>{lo:.7f},{la:.7f},0'
                         '</coordinates></Point></Placemark>')

    parts.append('</Document></kml>')
    with open(out, "w") as f:
        f.write("\n".join(parts) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
