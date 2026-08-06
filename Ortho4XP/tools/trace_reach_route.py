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
    venv/bin/python tools/trace_reach_route.py HECA --dem 10000 \
        --inverted-pairs
    # writes <out> (default /tmp/reach_route.kml) and prints the band, the
    # serving attachment, the binding anchor, and the per-cap route lengths.

``--dem M`` traces inside a CONSTANT-DEM oracle world (the same
``auto_patch.constant_dem.ConstantDEM`` ``harness/build_airport.py --dem``
installs — one authority, not a second constant-DEM path).  It exists
because real-DEM builds are gated on flat-green (RULINGS 2026-08-05), so the
canyon/plateau attribution may not reach for one.  The ruled pair is
``--dem -500`` (low) and ``--dem 10000`` (high): negatives are legal and are
the ruled low world (RULINGS 2026-08-06, "The low extreme is −500 m").

``--inverted-pairs`` traces the routes behind every contradictory anchor
pair ``assert_no_final_band_inversion`` named, INCLUDING on a build that
died on that law: the error is the thing being attributed, so the layout is
captured as the (real, unmodified) assertion runs.  ``--coord`` is
repeatable so one build answers many points (single-pass principle).
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


def _live_band(layout, _cache={}):
    """``(G, band, prov)`` from the LIVE band — built ONCE per layout.

    Every report below reads this one pass (single-pass principle): the
    band build is what RECORDS ``layout._band_anchor_provenance``, so a
    second build would be a second field as well as a second cost."""
    key = id(layout)
    if key in _cache:
        return _cache[key]
    from auto_patch import grade_graph as GG
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list)
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)

    nodes, b2i = _build_node_list(layout)
    if not nodes:
        _cache[key] = (None, None, {})
        return _cache[key]
    G = GG.build_unified_graph(layout, b2i)
    # THE band.  Building it also records the anchor provenance this report
    # reads (``spine_value_fields._record_anchor_provenance``) — one pass.
    band = reach_band_unified(layout, G)
    prov = getattr(layout, "_band_anchor_provenance", None) or {}
    _cache[key] = (G, band, prov)
    return _cache[key]


def _route_sides(G, prov, node):
    """The recorded ceiling/floor routes from solver ``node`` to its anchors.

    Shared by the coordinate report and ``--inverted-pairs``: the SAME
    walk over the SAME recorded field, so the two modes can never disagree
    about which route binds a node."""
    anchor_value = prov.get("anchor_value") or {}
    out = {}
    for side in ("ceiling", "floor"):
        prov_side = prov.get(side) or {}
        rec = prov_side.get(node)
        if rec is None:
            continue
        anchor, budget = int(rec[0]), float(rec[1])
        path, complete = _walk_to_anchor(G, prov_side, node, anchor)
        cap_len: dict = {}
        plan_len = 0.0
        for a, b in zip(path, path[1:]):
            bud = _edge_budget(G, a, b)
            pa, pb = G.pos.get(a), G.pos.get(b)
            if bud is None or pa is None or pb is None:
                continue
            seg = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if seg <= _EPS:
                continue
            plan_len += seg
            cap = round(bud / seg * 100, 2)
            cap_len[cap] = cap_len.get(cap, 0.0) + seg
        out[side] = {
            "anchor": anchor,
            "anchor_value": anchor_value.get(anchor),
            "anchor_pos": G.pos.get(anchor),
            "route_budget_m": budget,
            "path": [G.pos[n] for n in path if n in G.pos],
            "path_nodes": path,
            "path_complete": complete,
            "cap_len": cap_len,
            "plan_len_m": plan_len,
        }
    return out


def _binding_route(layout, x, y):
    """Everything the report needs at ``(x, y)``, read from the LIVE band."""
    G, band, prov = _live_band(layout)
    if G is None:
        return {"error": "layout has no solver nodes"}
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

    for side, s in _route_sides(G, prov, node).items():
        s["runway"] = _runway_at(layout, s["anchor_pos"])
        out[side] = s
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
        _print_caps(s)


def _print_caps(s, indent="           "):
    """The route's PHYSICAL length beside its priced budget.

    A budget alone cannot say whether it is under-priced: 24.66 m over
    1 600 m and 24.66 m over 400 m are different rulings.  The effective
    grade (budget ÷ plan length) is the number to compare against the
    caps the route actually crosses, so both are printed together."""
    if not s.get("cap_len"):
        return
    plan = s.get("plan_len_m") or 0.0
    eff = (s["route_budget_m"] / plan * 100.0) if plan > _EPS else float("nan")
    print(f"{indent}route plan length {plan:.1f} m; budget "
          f"{s['route_budget_m']:.4f} m ⇒ effective {eff:.4f}% of run")
    print(f"{indent}per-cap route length (m): {{"
          + ", ".join(f"{k}%: {v:.0f}"
                      for k, v in sorted(s["cap_len"].items())) + "}")


def _report_inverted_pairs(layout, captured=None):
    """Trace the routes behind every CONTRADICTORY ANCHOR PAIR the final
    band inversion named (``assert_no_final_band_inversion``).

    The error rolls 384 nodes up into three anchor pairs and one route
    budget each; this reads the SAME recorded field back out as the two
    routes that priced that budget — which taxi run, how long, at which
    per-edge caps — so the METRIC / CAP / TOPOLOGY ruling the error asks
    for can be made on measurements instead of on the summary line.

    IT MUST NOT REBUILD THE BAND.  Solver node ids are valid only inside
    the ONE ``_build_node_list`` call that assigned them
    (``_hard_truth_spine_seeds``' canonical-identity note), and the layout
    keeps growing after the final band pass — a rebuilt provenance is a
    DIFFERENT NODE SPACE, in which the inversion rows' node ids resolve to
    nothing (measured: all three HECA canyon pairs, "records no route").
    So the graph and the provenance are CAPTURED from the build's own
    recording call and read here; ``captured`` empty is reported, never
    silently papered over with a rebuild."""
    rows = list((captured or {}).get("rows")
                or getattr(layout, "_final_band_inversions", None) or [])
    if not rows:
        print("no recorded band inversions on this layout")
        return
    G = (captured or {}).get("G")
    prov = (captured or {}).get("prov")
    if G is None or not prov:
        print("!! the build's own band graph/provenance was not captured — "
              "refusing to rebuild it, because a rebuilt field is a "
              "different node space and the inversion rows do not resolve "
              "in it.  Run this on a build (not a stale layout).")
        return
    pairs: dict = {}
    for r in rows:
        fa, ca = r.get("floor_anchor"), r.get("ceil_anchor")
        if fa is None or ca is None:
            continue
        key = (int(fa), int(ca))
        cur = pairs.get(key)
        if cur is None or r["deficit_m"] > cur["worst"]["deficit_m"]:
            pairs[key] = {"n": pairs.get(key, {}).get("n", 0), "worst": r}
        pairs[key]["n"] = pairs[key].get("n", 0) + 1
    print(f"CONTRADICTORY ANCHOR PAIR(S): {len(pairs)} over "
          f"{len(rows)} recorded inverted node(s)")
    for (fa, ca), rec in sorted(pairs.items(),
                                key=lambda kv: -kv[1]["worst"]["deficit_m"]):
        r = rec["worst"]
        node = r["node"]
        fv, cv = r.get("floor_anchor_value"), r.get("ceil_anchor_value")
        fl, cl = r.get("floor_anchor_law"), r.get("ceil_anchor_law")
        print(f"\n=== pair floor-anchor {fa} vs ceiling-anchor {ca} — "
              f"{rec['n']} node(s), worst {r['deficit_m']:.4f} m at node "
              f"{node} @({r['x']:.1f},{r['y']:.1f})")
        print(f"    values  floor {fv:.4f}  ceiling {cv:.4f}  spread "
              f"{abs(fv - cv):.4f} m"
              + ("" if (fl is None or cl is None) else
                 f"   | LAW halves {fl:.4f} / {cl:.4f} spread "
                 f"{abs(fl - cl):.4f} m"))
        print(f"    recorded route split at the node: floor "
              f"{r['floor_route_m']:.4f} m + ceiling "
              f"{r['ceil_route_m']:.4f} m = "
              f"{r['floor_route_m'] + r['ceil_route_m']:.4f} m of budget")
        sides = _route_sides(G, prov, node)
        for side in ("floor", "ceiling"):
            s = sides.get(side)
            if not s:
                print(f"    {side.upper():<8} !! the rebuilt field records no "
                      f"{side} route for node {node} — the trace and the "
                      f"build's own field disagree; do not equate them")
                continue
            recorded = (r["floor_route_m"] if side == "floor"
                        else r["ceil_route_m"])
            drift = s["route_budget_m"] - recorded
            ap = s["anchor_pos"]
            print(f"    {side.upper():<8} anchor {s['anchor']} "
                  f"({_runway_at(layout, ap)})"
                  + (f" @({ap[0]:.0f},{ap[1]:.0f})" if ap else "")
                  + f" value {s['anchor_value']:.4f}, budget "
                    f"{s['route_budget_m']:.4f} m over "
                    f"{len(s['path_nodes'])} node(s)"
                  + ("" if s["path_complete"] else "  [PATH INCOMPLETE]")
                  + ("" if abs(drift) <= 1e-4 else
                     f"  [BUDGET DRIFT vs the build's own field "
                     f"{drift:+.4f} m — different frames, do not equate]"))
            _print_caps(s, indent="             ")


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


def _build(icao, const_dem=None):
    """The layout to trace — REAL DEM by default, a CONSTANT-DEM world with
    ``--dem`` (RULINGS: the flat oracle worlds; real DEM is gated on
    flat-green, so the canyon/plateau trace must not need a real-DEM build).

    ``ConstantDEM`` is imported from ``auto_patch.constant_dem`` — the SAME
    object ``harness/build_airport.py --dem`` installs, never a second
    constant-DEM implementation.

    Returns ``(layout, band_error, captured)``.  A ``BandInversionError`` is
    the very thing this tool exists to attribute, so the build's own layout
    is CAPTURED as the assertion runs and handed back with the error rather
    than lost with the traceback.  ``captured`` additionally holds the band
    graph, the anchor provenance and the inversion rows AS THE BUILD
    RECORDED THEM — one node space, the assert's own — because rebuilding
    any of the three post-build lands in a different one.  Production is
    untouched: both shims call straight through and only read."""
    from conftest import xplane_root
    from auto_patch.pipeline import build_airport_pavement
    from auto_patch.elevation_per_surface import building_feasibility as BF

    kw = {"compute_elevations": True}
    if const_dem is not None:
        from auto_patch.constant_dem import ConstantDEM
        kw["tile_dem"] = ConstantDEM(float(const_dem))
        print(f"[trace] CONSTANT-DEM world: {float(const_dem):g} m")

    seen: dict = {}
    real_assert = BF.assert_no_final_band_inversion
    real_record = BF._record_band_inversions

    def _capturing_assert(layout, icao="", *a, **k):
        seen["layout"] = layout
        return real_assert(layout, icao, *a, **k)

    def _capturing_record(layout, G, *a, **k):
        # LAST CALL WINS — exactly the rule the assertion reads by.
        out = real_record(layout, G, *a, **k)
        prov = getattr(layout, "_band_anchor_provenance", None) or {}
        seen["G"] = G
        seen["prov"] = {"anchor_value": dict(prov.get("anchor_value") or {}),
                        "ceiling": dict(prov.get("ceiling") or {}),
                        "floor": dict(prov.get("floor") or {})}
        seen["rows"] = list(getattr(layout, "_final_band_inversions", None)
                            or [])
        return out

    BF.assert_no_final_band_inversion = _capturing_assert
    BF._record_band_inversions = _capturing_record
    try:
        layout = build_airport_pavement(icao, xplane_root(), **kw)
        return layout, None, seen
    except BF.BandInversionError as exc:
        if "layout" not in seen:
            raise
        print("[trace] the build FAILED its final band-inversion law; "
              "tracing the layout it failed on.\n")
        return seen["layout"], exc, seen
    finally:
        BF.assert_no_final_band_inversion = real_assert
        BF._record_band_inversions = real_record


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("icao")
    ap.add_argument("--ref", help="shape ref (e.g. building5)")
    ap.add_argument("--coord", action="append", default=[],
                    help="local meters 'x,y' (repeatable — one build, many "
                         "traces)")
    ap.add_argument("--dem", type=float,
                    help="trace in a CONSTANT-DEM world of this elevation "
                         "(the oracle worlds; same ConstantDEM the harness "
                         "build entry installs).  The ruled pair is -500 "
                         "(low) and 10000 (high) — negatives are legal")
    ap.add_argument("--inverted-pairs", action="store_true",
                    help="trace the routes behind every contradictory anchor "
                         "pair the FINAL BAND INVERSION named (works on a "
                         "build that failed that law)")
    ap.add_argument("--out", default="/tmp/reach_route.kml")
    args = ap.parse_args()

    layout, band_err, captured = _build(args.icao, args.dem)

    if args.inverted_pairs:
        _report_inverted_pairs(layout, captured)
        if not args.coord and not args.ref:
            return 0

    targets = []
    for c in args.coord:
        x, y = (float(v) for v in c.split(","))
        targets.append((x, y, c))
    if args.ref:
        s = next((s for s in layout.shapes if str(s.ref) == args.ref), None)
        if s is None or s.polygon is None:
            sys.exit(f"ref {args.ref} not found / no polygon")
        targets.append((s.polygon.centroid.x, s.polygon.centroid.y, args.ref))
    if not targets and not args.inverted_pairs:
        sys.exit("give --ref, --coord or --inverted-pairs")

    rc = 0
    for i, (x, y, label) in enumerate(targets):
        r = _binding_route(layout, x, y)
        _report(r, x, y)
        out = (args.out if len(targets) == 1
               else args.out.replace(".kml", f".{i}.kml"))
        _kml(layout, r, x, y, label, out)
        if r.get("error"):
            rc = 1
    # EXIT CODE IS ABOUT THE TOOL, NOT THE POINT.  An off-net point is an
    # ANSWER ("the local within-shape law governs it"), not a failure — the
    # old tool exited 1 on it and that is what made it read as a refusal.
    # A build that failed the band law is likewise an ANSWER here.
    return rc


if __name__ == "__main__":
    sys.exit(main())
