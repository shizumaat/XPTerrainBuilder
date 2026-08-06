#!/usr/bin/env python
"""Trace the BINDING reach route to a pavement point and emit it as KML.

The companion to ``building_feasibility.reach_band_unified`` — THE one reach
band (route-metric value on the unified spine graph + a grid LOOKUP for the
local off-route leg).  It answers "which runway anchor, over which route,
binds this point's ceiling and floor, and what does that route look like on
the map?".

REVIVED 2026-08-06 (cycle-5 instrument-fix spec item 4).  This tool used to
REPLAY a band engine that no longer exists: nearest-visible-centerline,
perpendicular foot, the two spine nodes bracketing the foot, a perp climb.
That engine was DELETED on 2026-07-29 (the one-engine ruling, spec
``rod-compose-and-band-single-source`` §B), so the tool's docstring claim that
"its ceiling/floor match ``reach_band_unified`` exactly" had become false and
it REFUSED coordinates the live band serves: asked for the binding route at
SPJC's worst route-band vertex it exited ``point is not taxi-reachable from
any runway contact`` while ``reach_band_unified`` returned ``(8.8941,
16.3459)`` at that exact coordinate in the same build.  ``tools/INDEX.md``
listed it as *the* tool for the question, so the index was false too.

It now READS the live band instead of re-deriving it — the difference that
matters, because a re-derivation is a second engine and a second engine is
how this tool became wrong in the first place:

  * ``reach_band_unified(layout, G)`` gives the band at the point;
  * ``band.attachment_at(x, y)`` gives the LOOKUP's own answer — which route
    attachment serves the point and what the local off-route leg costs;
  * ``layout._band_anchor_provenance`` (recorded by
    ``building_feasibility.spine_value_fields`` on the same pass) gives WHICH
    ANCHOR authored the ceiling and the floor at that attachment and the route
    budget it spent — so the binding anchor is read, never re-searched;
  * the route path is reconstructed by walking that recorded field
    (each step must reproduce the recorded budget exactly), never by a second
    Dijkstra with its own opinion.

Usage:
    venv/bin/python tools/trace_reach_route.py SPJC --coord 536.64,-625.53
    venv/bin/python tools/trace_reach_route.py CYXY --ref building5
    # writes <out> (default /tmp/reach_route.kml) and prints the band, the
    # serving attachment, the binding anchor, and the per-cap route lengths.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "src"),
                os.path.join(os.path.dirname(__file__), ".."),
                os.path.join(os.path.dirname(__file__), "..", "tests")]

_EPS = 1e-6


def _edge_budget(G, a, b):
    """The spine edge's own budget (metres of value it may carry), or None."""
    for (v, budget) in G.spine_adj.get(a, ()):
        if v == b:
            return float(budget)
    return None


def _walk_to_anchor(G, prov_side, node, anchor, limit=100000):
    """The recorded route ``node → anchor``, read out of the field.

    ``prov_side`` is ``{node: (anchor, route_budget)}`` as
    ``spine_value_fields`` recorded it.  Each hop must reproduce the recorded
    budget through the edge it crosses, so this REPLAYS the winning route
    rather than searching for one: a hop that does not reconcile stops the
    walk and is reported, instead of a second metric quietly inventing a path.
    """
    path = [node]
    u = node
    seen = {node}
    while u != anchor and len(path) < limit:
        cur = prov_side.get(u)
        if cur is None:
            return path, False
        best = None
        for (v, budget) in G.spine_adj.get(u, ()):
            if v in seen:
                continue
            rec = prov_side.get(v)
            if rec is None or rec[0] != cur[0]:
                continue
            if abs(rec[1] + float(budget) - cur[1]) <= 1e-6:
                if best is None or rec[1] < prov_side[best][1]:
                    best = v
        if best is None:
            return path, False
        seen.add(best)
        path.append(best)
        u = best
    path.reverse()                                  # anchor → point
    return path, (u == anchor)


def _binding_route(layout, x, y):
    """Everything the report needs at ``(x, y)``, read from the LIVE band."""
    from auto_patch import grade_graph as GG
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list)
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)

    nodes, b2i = _build_node_list(layout)
    if not nodes:
        return {"error": "layout has no solver nodes"}
    G = GG.build_unified_graph(layout, b2i)
    # THE band.  Building it also records the anchor provenance this report
    # reads (``spine_value_fields._record_anchor_provenance``) — one pass.
    band = reach_band_unified(layout, G)
    out: dict = {"G": G, "band": band(x, y)}
    if out["band"] is None:
        out["why_none"] = (
            "the band answers None here: the point is off the paved mask "
            "beyond RASTER_REACH_BAND_OFFNET_RADIUS_M, or its cell carries no "
            "route attachment (off-net).  The LOCAL within-shape law governs "
            "such a point — this is the band's answer, not a refusal.")
    att = None
    if hasattr(band, "attachment_at"):
        att = band.attachment_at(x, y)
    out["attachment"] = att
    prov = getattr(layout, "_band_anchor_provenance", None) or {}
    out["provenance_present"] = bool(prov)
    if not att or not prov:
        return out

    anchor_value = prov.get("anchor_value") or {}
    ceil_side = prov.get("ceiling") or {}
    floor_side = prov.get("floor") or {}

    def _ceil_of(n):
        rec = ceil_side.get(n)
        return None if rec is None else anchor_value.get(rec[0], 0.0) + rec[1]

    def _floor_of(n):
        rec = floor_side.get(n)
        return None if rec is None else anchor_value.get(rec[0], 0.0) - rec[1]

    # THE SERVING ATTACHMENT: the band takes the MIN ceiling over the route
    # nodes seeding that cell, so the binding one is the argmin — the same
    # rule, read off the same values.
    cands = [n for n in att["attachment_nodes"] if _ceil_of(n) is not None]
    if not cands:
        return out
    node = min(cands, key=lambda n: (_ceil_of(n), n))
    out["attachment_node"] = node
    out["attachment_pos"] = G.pos.get(node)
    out["ceiling_at_node"] = _ceil_of(node)
    out["floor_at_node"] = _floor_of(node)

    for side, prov_side in (("ceiling", ceil_side), ("floor", floor_side)):
        rec = prov_side.get(node)
        if rec is None:
            continue
        anchor, budget = int(rec[0]), float(rec[1])
        path, complete = _walk_to_anchor(G, prov_side, node, anchor)
        cap_len: dict = {}
        for a, b in zip(path, path[1:]):
            bud = _edge_budget(G, a, b)
            pa, pb = G.pos.get(a), G.pos.get(b)
            if bud is None or pa is None or pb is None:
                continue
            seg = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if seg <= _EPS:
                continue
            cap_len[round(bud / seg * 100, 2)] = \
                cap_len.get(round(bud / seg * 100, 2), 0.0) + seg
        out[side] = {
            "anchor": anchor,
            "anchor_value": anchor_value.get(anchor),
            "anchor_pos": G.pos.get(anchor),
            "route_budget_m": budget,
            "path": [G.pos[n] for n in path if n in G.pos],
            "path_complete": complete,
            "cap_len": cap_len,
            "runway": _runway_at(layout, G.pos.get(anchor)),
        }
    return out


def _runway_at(layout, pos):
    """The runway ref whose polygon owns ``pos`` — scoped by the JOIN/CONTACT
    law's own reach (``grade_law``), never a magic radius."""
    if pos is None:
        return "?"
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING
    from auto_patch.grade_law import RUNWAY_CONTACT_M, RUNWAY_JOIN_NEAR_M
    reach = RUNWAY_CONTACT_M + RUNWAY_JOIN_NEAR_M
    p = Point(pos[0], pos[1])
    best, best_d = "?", reach
    for s in layout.shapes:
        if (s.role not in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)
                or s.polygon is None or s.polygon.is_empty):
            continue
        d = s.polygon.distance(p)
        if d <= best_d:
            best, best_d = str(s.ref), d
    return best


def _report(r, x, y):
    print(f"target ({x:.2f},{y:.2f})")
    if r.get("error"):
        print(f"  ERROR: {r['error']}")
        return
    band = r.get("band")
    if band is None:
        print("  reach band: None (OFF-NET)")
        print(f"  {r.get('why_none', '')}")
    else:
        print(f"  reach band: floor={band[0]:.4f}  ceiling={band[1]:.4f}"
              f"  (width {band[1] - band[0]:+.4f} m)")
    att = r.get("attachment")
    if att is None:
        print("  attachment: none — the grid lookup serves no attachment "
              "here (off-net).  Nothing binds this point; the local "
              "within-shape law governs it.")
        return
    where = ("paved" if att["query_cell_paved"]
             else f"OFF-MASK, snapped {att['off_mask_m']:.2f} m")
    print(f"  lookup: query cell {att['cell']} ({where}), off-route leg "
          f"{att['leg_m']:.4f} m at {att['cell_m']:.1f} m cells")
    print(f"  serving attachment cell {att['attachment_cid']} "
          f"@{att['attachment_cell']} seeded by "
          f"{len(att['attachment_nodes'])} route node(s); its band "
          f"[{att['floor_at_attachment']:.4f}, "
          f"{att['ceiling_at_attachment']:.4f}]")
    if not r.get("provenance_present"):
        print("  !! the band recorded no anchor provenance — cannot name the "
              "binding anchor (spine_value_fields did not run on this layout)")
        return
    node = r.get("attachment_node")
    if node is None:
        print("  !! no attachment node carries a recorded ceiling")
        return
    pos = r.get("attachment_pos")
    print(f"  binding attachment node {node}"
          + (f" @({pos[0]:.2f},{pos[1]:.2f})" if pos else "")
          + f"  ceiling {r['ceiling_at_node']:.4f}  "
            f"floor {r['floor_at_node']:.4f}")
    for side in ("ceiling", "floor"):
        s = r.get(side)
        if not s:
            continue
        ap = s["anchor_pos"]
        print(f"  {side.upper():<8} anchor node {s['anchor']} "
              f"({s['runway']})"
              + (f" @({ap[0]:.0f},{ap[1]:.0f})" if ap else "")
              + f" value {s['anchor_value']:.4f}, route budget "
                f"{s['route_budget_m']:.4f} m over {len(s['path'])} node(s)"
              + ("" if s["path_complete"] else "  [PATH INCOMPLETE — the "
                 "recorded budgets do not reconcile through the graph; the "
                 "anchor and budget above are still the field's own]"))
        if s["cap_len"]:
            print("           per-cap route length (m): {"
                  + ", ".join(f"{k}%: {v:.0f}"
                              for k, v in sorted(s["cap_len"].items())) + "}")


def _kml(layout, r, x, y, label, out_path):
    from shapely.geometry import Point as _P
    from auto_patch.grade_graph import _open_ring
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING
    lat0, lon0 = layout.anchor
    R = 6378137.0
    cos0 = math.cos(math.radians(lat0))

    def ll(px, py):
        return (lon0 + math.degrees(px / (R * cos0)),
                lat0 + math.degrees(py / R))

    def line(pts):
        return " ".join(f"{ll(*p)[0]:.7f},{ll(*p)[1]:.7f},0" for p in pts)

    def pm(name, px, py):
        lo, la = ll(px, py)
        return (f'<Placemark><name>{name}</name><Point><coordinates>'
                f'{lo:.7f},{la:.7f},0</coordinates></Point></Placemark>')

    band = r.get("band")
    parts = [
        '<?xml version="1.0"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        '<Style id="r"><LineStyle><color>ff00ffff</color><width>5</width>'
        '</LineStyle></Style>',
        '<Style id="f"><LineStyle><color>ff00ff00</color><width>3</width>'
        '</LineStyle></Style>',
        '<Style id="ap"><LineStyle><color>ffff8800</color><width>2</width>'
        '</LineStyle><PolyStyle><color>20ff8800</color></PolyStyle></Style>',
        '<Style id="bl"><LineStyle><color>ff0000ff</color><width>2</width>'
        '</LineStyle><PolyStyle><color>300000ff</color></PolyStyle></Style>',
        pm(f"target {label}" + ("" if band is None else
                                f" band [{band[0]:.2f}, {band[1]:.2f}]"), x, y),
    ]
    for side, style in (("ceiling", "r"), ("floor", "f")):
        s = r.get(side)
        if not s or len(s["path"]) < 2:
            continue
        parts.append(
            f'<Placemark><name>{side} route {s["runway"]} '
            f'{s["anchor_value"]:.2f} + {s["route_budget_m"]:.2f} m</name>'
            f'<styleUrl>#{style}</styleUrl><LineString><coordinates>'
            f'{line(s["path"])}</coordinates></LineString></Placemark>')
        ap = s["anchor_pos"]
        if ap:
            parts.append(pm(f"{side} anchor {s['runway']} "
                            f"{s['anchor_value']:.2f}", ap[0], ap[1]))
    pos = r.get("attachment_pos")
    if pos:
        parts.append(pm(f"attachment node {r['attachment_node']}",
                        pos[0], pos[1]))
    near = _P(x, y)
    for s in layout.shapes:
        if (s.polygon is None or s.polygon.is_empty
                or s.polygon.distance(near) > 120):
            continue
        if s.role in (ROLE_APRON, ROLE_BUILDING):
            ring = _open_ring(list(s.polygon.exterior.coords))
            style = "ap" if s.role == ROLE_APRON else "bl"
            name = (f"apron {s.polygon.area:.0f}m2"
                    if s.role == ROLE_APRON else str(s.ref))
            parts.append(
                f'<Placemark><name>{name}</name><styleUrl>#{style}</styleUrl>'
                f'<Polygon><outerBoundaryIs><LinearRing><coordinates>'
                f'{line(ring + [ring[0]])}</coordinates></LinearRing>'
                f'</outerBoundaryIs></Polygon></Placemark>')
    parts.append('</Document></kml>')
    with open(out_path, "w") as f:
        f.write("\n".join(parts) + "\n")
    print(f"wrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("icao")
    ap.add_argument("--ref", help="shape ref (e.g. building5)")
    ap.add_argument("--coord", help="local meters 'x,y'")
    ap.add_argument("--out", default="/tmp/reach_route.kml")
    args = ap.parse_args()

    from conftest import xplane_root
    from auto_patch.pipeline import build_airport_pavement
    layout = build_airport_pavement(args.icao, xplane_root(),
                                    compute_elevations=True)

    if args.coord:
        x, y = (float(v) for v in args.coord.split(","))
    elif args.ref:
        s = next((s for s in layout.shapes if str(s.ref) == args.ref), None)
        if s is None or s.polygon is None:
            sys.exit(f"ref {args.ref} not found / no polygon")
        x, y = s.polygon.centroid.x, s.polygon.centroid.y
    else:
        sys.exit("give --ref or --coord")

    r = _binding_route(layout, x, y)
    _report(r, x, y)
    _kml(layout, r, x, y, args.ref or args.coord, args.out)
    # EXIT CODE IS ABOUT THE TOOL, NOT THE POINT.  An off-net point is an
    # ANSWER ("the local within-shape law governs it"), not a failure — the
    # old tool exited 1 on it and that is what made it read as a refusal.
    return 0 if not r.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
