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

    venv/bin/python tools/trace_reach_route.py --from-sidecar \
        Patches/+30+031/HECA_auto.patch.osm --ref building25 \
        --out /tmp/building25.kml
    # NO BUILD.  Renders the pad BINDING ROUTES the engine PUBLISHED into
    # the patch's ``.axes.json`` (key ``pad_binding_routes``, spec
    # ``docs/specs/pad-binding-routes-spec.md``).

``--from-sidecar`` exists because the live modes above answer "which route
binds this pad?" only by REBUILDING the whole airport: the band is live
solver state, and re-deriving it offline is exactly the second engine this
tool was rewritten to stop being.  So the engine publishes, at emit time,
the route evidence it already computed, and this mode renders it — one
capture, N consumers.  ``--out`` picks the format by extension (``.kml``
or ``.osm``); the OSM render is a JOSM viewer artifact and the writer
REFUSES an ``--out`` ending in ``.patch.osm`` (the patch loader globs it).

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

#: THE TWO-INSTRUMENT AGREEMENT CONTRACT for one route budget (RULINGS
#: 2026-08-06 binding point 4).  Two independent readings of the SAME
#: quantity: the walk re-reads it hop by hop out of the recorded field
#: (``_route_sides`` → ``_walk_to_anchor``), and
#: ``assert_no_final_band_inversion`` recorded its own at the node.  They
#: must agree to within this many metres.  This is a RECONCILIATION
#: tolerance, not a law materiality floor — both numbers are the same float
#: additions in a different order, so the only slack it may absorb is
#: accumulation.
ROUTE_BUDGET_AGREEMENT_M = 1e-4

#: The CROWN SPACE every band / budget / anchor value printed by this tool
#: lives in.  Stated because the repo's standing trap is exactly this: an
#: emitted step can be level in projection space and look like a defect.
CROWN_SPACE_NOTE = (
    "crown space: the ONE UNCROWNED profile space — "
    "building_feasibility._decrowned_anchor_seeds lifts each runway-edge "
    "anchor by its own crown drop before seeding, so bands, route budgets "
    "and anchor values below are UNCROWNED.  EMITTED vertex altitudes are "
    "crown-LIFTED: subtract crown.crown_drop_at(layout, x, y) before "
    "comparing an emitted altitude with any number here.")


def _nodespace(G):
    """A token identifying the NODE SPACE of ``G``.

    Solver node ids are valid only inside the one ``_build_node_list`` call
    that assigned them, so a node id is meaningless without the graph it was
    assigned in.  Object identity plus node count is the strongest
    identifier available WITHOUT re-deriving anything — and not re-deriving
    is the whole point of this tool.  Two reports carrying the same token
    are in one node space; two carrying different tokens are not, and that
    is a fact, not an interpretation.
    """
    if G is None:
        return "none"
    return f"G@{id(G):x}/n={len(getattr(G, 'pos', None) or ())}"


# ── THE WALK LIVES IN THE ENGINE ─────────────────────────────────────────
# ``_walk_to_anchor`` / ``_edge_budget`` used to be private copies here.
# They are now ``building_feasibility.walk_to_anchor`` /
# ``.spine_edge_budget`` (spec ``docs/specs/pad-binding-routes-spec.md``
# §1.1): the engine PUBLISHES pad binding routes with the same walk this
# tool reports, and one implementation is what stops the two drifting into
# separate opinions about which route bound a node.
#
# Bound lazily (PEP 562) rather than by a module-level ``from … import``:
# ``--from-sidecar`` may not pull the solver in AT ALL (§2.1), and a
# top-level import would do exactly that at module load.  The names are
# production's own objects — ``trace_reach_route.walk_to_anchor is
# building_feasibility.walk_to_anchor`` — so there is nothing to fork.
_ENGINE_WALK_NAMES = ("walk_to_anchor", "spine_edge_budget")


def __getattr__(name):
    if name in _ENGINE_WALK_NAMES:
        from auto_patch.elevation_per_surface import building_feasibility
        return getattr(building_feasibility, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    from auto_patch.elevation_per_surface.building_feasibility import (
        walk_to_anchor as _walk_to_anchor,
        spine_edge_budget as _edge_budget)
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


def _why_band_none(band, att):
    """WHY the band answered ``None`` — discriminated by ASKING THE BAND,
    never asserted as a disjunction the code did not test.

    ``band`` answers None on five distinct paths
    (``raster_reach_band.py`` ~:541-561): the query cell is outside the
    grid; the cell is paved but its ceiling is not finite; the cell is
    off-mask with no distance transform; it is off-mask beyond
    ``RASTER_REACH_BAND_OFFNET_RADIUS_M``; or the nearest paved cell's
    ceiling is not finite.  ``attachment_at`` answers None on the first,
    third and fourth and a dict otherwise, which splits the five into one
    MEASURED case and an undiscriminated group of three — reported as such.
    """
    tail = ("The LOCAL within-shape law governs such a point — this is the "
            "band's answer, not a refusal.")
    if not hasattr(band, "attachment_at"):
        return ("the band answers None here; cause NOT DISCRIMINATED — this "
                "band exposes no attachment_at lookup to ask.  " + tail)
    if att is None:
        return ("the band answers None here and the lookup serves NO "
                "attachment; cause NOT DISCRIMINATED among: the query cell "
                "is outside the band grid / the point is off the paved mask "
                "beyond RASTER_REACH_BAND_OFFNET_RADIUS_M / its cell carries "
                "no route attachment (source cid < 0).  " + tail)
    c = att.get("ceiling_at_attachment")
    where = ("paved" if att.get("query_cell_paved")
             else f"off-mask by {att.get('off_mask_m', float('nan')):.2f} m")
    if c is None or not math.isfinite(c):
        return (f"the band answers None while the lookup DOES serve "
                f"attachment cid {att.get('attachment_cid')} (query cell "
                f"{where}): that attachment's own ceiling is not finite "
                f"(measured) — the route attachment serving this cell is not "
                f"anchor-reachable.  " + tail)
    return (f"the band answers None while the lookup DOES serve attachment "
            f"cid {att.get('attachment_cid')} (query cell {where}) with a "
            f"FINITE ceiling {c:.4f}; the cell's own ceiling is not finite. "
            f"Cause not discriminated further.  " + tail)


def _binding_route(layout, x, y):
    """Everything the report needs at ``(x, y)``, read from the LIVE band."""
    G, band, prov = _live_band(layout)
    if G is None:
        return {"error": "layout has no solver nodes"}
    att = band.attachment_at(x, y) if hasattr(band, "attachment_at") else None
    out: dict = {"G": G, "layout": layout, "band": band(x, y),
                 "attachment": att, "nodespace": _nodespace(G)}
    if out["band"] is None:
        out["why_none"] = _why_band_none(band, att)
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


def _anchor_class(layout, G, node, pos=None):
    """WHAT KIND OF ANCHOR this is — ``"surface-lawful"`` or a named
    BELOW-GRADE body membership.

    R17b-1's instrument half.  The canyon question the base round could
    not answer from this tool was never "which anchor" (it printed that)
    but "is that anchor LAWFUL AT THE SURFACE" — a below-grade seed
    (tunnel bore, ramp, claimed plate) binds a ceiling MIN that has no
    business governing surface pavement, and the printout looked exactly
    like a legitimate runway anchor.

    THE CLASSIFICATION IS PRODUCTION'S OWN
    (``building_feasibility.below_grade_anchor_bodies`` over
    ``groundside.below_grade_family_shapes``) — the tool must never carry
    a second opinion about what is below grade, which is how the law and
    the instrument drift apart.
    """
    from auto_patch.elevation_per_surface.building_feasibility import (
        below_grade_anchor_bodies, BELOW_GRADE_BODY_TOL_M)
    if node is None:
        return "?"
    bodies = below_grade_anchor_bodies(layout, G, {int(node): 0.0})
    body = bodies.get(int(node))
    if body is None:
        return "surface-lawful"
    if pos is None:
        pos = (getattr(G, "pos", None) or {}).get(int(node))
    owner = "?"
    if pos is not None:
        from shapely.geometry import Point
        from auto_patch.groundside import below_grade_family_shapes
        p = Point(float(pos[0]), float(pos[1]))
        best = None
        for s in below_grade_family_shapes(layout):
            try:
                d = s.polygon.distance(p)
            except Exception:                           # pragma: no cover
                continue
            if best is None or d < best[0]:
                best = (d, s)
        if best is not None and best[0] <= BELOW_GRADE_BODY_TOL_M:
            owner = f"{best[1].ref}/{best[1].role}"
        elif best is not None:
            owner = f"{best[1].ref}/{best[1].role} (+{best[0]:.3f} m)"
    return (f"BELOW-GRADE body {owner}, body area {body.area:.0f} m2 "
            f"— R17b-1: governs only nodes inside this body")


def _owning_shape(layout, pos, limit=5):
    """EVERY shape whose polygon owns ``pos`` — the plain "what IS this
    anchor standing on" question.

    ALL of them, never the first hit: airport shapes OVERLAP (a claimed
    tunnel plate under a junction, adjacent-ground under everything), and
    a single-owner answer silently picks whichever the shape list happens
    to reach first.  That is how a below-grade plate hides behind the
    junction drawn over it."""
    if pos is None:
        return "?"
    from shapely.geometry import Point
    p = Point(float(pos[0]), float(pos[1]))
    hits, nearest = [], None
    for s in getattr(layout, "shapes", ()) or ():
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            d = poly.distance(p)
        except Exception:                               # pragma: no cover
            continue
        if d <= 1e-6:
            hits.append(f"{getattr(s, 'ref', '?')}/{getattr(s, 'role', '?')}")
        elif nearest is None or d < nearest[0]:
            nearest = (d, s)
    if hits:
        extra = "" if len(hits) <= limit else f" (+{len(hits) - limit} more)"
        return ", ".join(hits[:limit]) + extra
    if nearest is None:
        return "?"
    return (f"{getattr(nearest[1], 'ref', '?')}/"
            f"{getattr(nearest[1], 'role', '?')} (+{nearest[0]:.2f} m, "
            f"NO shape owns this point)")


def _in_flat_extent(layout, pos):
    """Is ``pos`` inside the flat site's substituted extent / its provable
    constant core?  A submarine DEM sample OUTSIDE the extent is a wholly
    different story from a below-grade STRUCTURE inside it."""
    if pos is None:
        return "?"
    try:
        from auto_patch import flat_fast_path as FFP
        entry = FFP.substitution_entry(layout)
        if entry is None:
            return "no flat-site substitution on this build"
        from shapely.geometry import Point
        p = Point(float(pos[0]), float(pos[1]))
        core = FFP.constant_core(layout, entry)
        z0 = entry.get("z0_m")
        inside = core is not None and core.contains(p)
        return (f"{'INSIDE' if inside else 'OUTSIDE'} the constant core "
                f"(Z0={z0})")
    except Exception as exc:                            # pragma: no cover
        return f"? ({type(exc).__name__})"


class _WriteTracedElev(list):
    """The solve's ``elev`` list, with a WRITE LOG for the values that
    matter (R17c-1).

    r17b named the poisoned SEED (node 419 at −12.537, a surface-lawful
    junction node inside a flat site's Z0 core) but not its WRITER: the
    seed set the band reads is ``elev`` at the moment
    ``route_profile.solve`` publishes ``_seed_hard_truth_values``, and
    between ``_seed_elevations`` and that publication a dozen passes may
    write it.  Attribution by code reading is exactly the "attribution
    reads are not causal" trap; this records the writer.

    Only writes whose VALUE crosses ``thresh`` (default 0.0 — the
    question is "who wrote a below-sea-level number onto a surface
    node") or that land on a WATCHED index are logged, so the log stays
    small while the solve's millions of ordinary writes cost one
    comparison each."""

    __slots__ = ("log", "thresh", "watch")

    def __init__(self, seq, thresh=0.0, watch=()):
        super().__init__(seq)
        self.log: dict = {}
        self.thresh = float(thresh)
        self.watch = set(watch)

    def __setitem__(self, i, v):
        try:
            if type(i) is int and (v < self.thresh or i in self.watch):
                f = sys._getframe(1)
                self.log.setdefault(i, []).append(
                    (f"{os.path.basename(f.f_code.co_filename)}:"
                     f"{f.f_lineno} {f.f_code.co_name}",
                     float(list.__getitem__(self, i)), float(v)))
        except Exception:                                   # pragma: no cover
            pass
        list.__setitem__(self, i, v)


def _branch_of(call, idx):
    """The SEEDING BRANCH that supplied node ``idx``'s value, from the
    call's own ``O4_SEED_BRANCH_ATTRIB`` map — the measurement that
    settles CONSTANT FILL vs PER-VERTEX SAMPLE, which select different
    fixes and which no amount of code reading can separate."""
    rec = (call.get("branch") or {}).get(int(idx))
    if rec is None:
        return ("(no branch recorded — run with O4_SEED_BRANCH_ATTRIB=1)")
    return ("{0}   shape {1}/{2} ring#{3}".format(
        rec.get("branch"), rec.get("ref"), rec.get("role"),
        rec.get("ring_index")))


def _seed_pin_family(layout, idx, extra):
    """WHICH PIN FAMILY hardened node ``idx`` inside ``_seed_elevations``.

    Production publishes each family's own index set (``_seam_pin_idx``
    is the UNION protection set, ``_eat_anchor_pin_idx`` is exact, and
    the tunnel-road / flat-fast-path families are captured from their own
    builders by the shim) — this reads those, never a second opinion
    about what a pin is."""
    hits = [name for (name, s) in extra.items() if idx in s]
    if idx in (getattr(layout, "_eat_anchor_pin_idx", None) or {}):
        hits.append("eat_anchor_rect")
    prot = getattr(layout, "_seam_pin_idx", None) or set()
    if idx in prot and not hits:
        hits.append("seam/deck/skirt pin (protection set, family not "
                    "separately published)")
    return ", ".join(hits) if hits else "runway/CIFP block or later pass"


def _report_hard_seed_writers(layout, captured, thresh=0.0, worst=12):
    """R17c-1's ATTRIBUTION: who wrote the below-``thresh`` value that the
    band reads as a seed.

    Two facts per poisoned node, both measured on the build's own solve:
    (a) was the value already there when ``_seed_elevations`` RETURNED
    (born in seeding) or written by a later pass; (b) the write log —
    ``file:line function`` for every write that crossed the threshold."""
    calls = list((captured or {}).get("seed_calls") or [])
    if not calls:
        print("!! no _seed_elevations call was captured — run this on a "
              "build")
        return
    print(f"\n=== HARD-SEED WRITERS (threshold {thresh:+.3f} m) ===")
    for c in calls:
        print(f"\n-- seed call #{c['i']}: {c['n']} node(s), "
              f"{c['n_hard']} hard, {len(c['born'])} of them BELOW "
              f"{thresh:+.3f} m at _seed_elevations RETURN")
        for name, s in sorted(c["extra"].items()):
            print(f"     family {name}: {len(s)} node(s) pinned")
        print(f"     published sets: eat_anchor_rect="
              f"{len(c.get('eat_pin_idx') or {})}, seam-family protection="
              f"{len(c.get('seam_pin_idx') or set())}")
        _tally: dict = {}
        for _i in c["born"]:
            _rec = (c.get("branch") or {}).get(int(_i)) or {}
            _tally[_rec.get("branch")] = _tally.get(_rec.get("branch"), 0) + 1
        # THE UNION'S OWN COMPOSITION (lead question, round 17c): the
        # BAND-SEED COMPLETENESS law unions EVERY ``base_hard`` node into
        # the band's seed set, while its STATED law is runway anchors plus
        # tile-seam pins.  This is what closing the union to its stated
        # law would LOSE, branch by branch.
        _all: dict = {}
        for _i in c.get("hard_idx") or ():
            _rec = (c.get("branch") or {}).get(int(_i)) or {}
            _b = _rec.get("branch")
            _all[_b] = _all.get(_b, 0) + 1
        print("     BRANCH TALLY over ALL base_hard node(s) — what the "
              "seed-completeness union carries:")
        for (_k, _v) in sorted(_all.items(), key=lambda kv: -kv[1]):
            print(f"       {_v:7d}  {_k}")
        _stated = sum(_v for (_k, _v) in _all.items()
                      if _k in ("runway_cifp_profile", "tile_seam_pin"))
        print(f"       STATED LAW (runway anchors + tile-seam pins) = "
              f"{_stated} of {sum(_all.values())}; closing the union to it "
              f"would drop {sum(_all.values()) - _stated} seed(s)")
        print("     BRANCH TALLY over the born-below set: "
              + (", ".join(f"{k}={v}" for (k, v) in sorted(
                  _tally.items(), key=lambda kv: -kv[1]))
                 or "(none)"))
        born = sorted(c["born"].items(), key=lambda kv: kv[1][0])[:worst]
        for idx, (val, pos) in born:
            print(f"   node {idx} @({pos[0]:.1f},{pos[1]:.1f}) = "
                  f"{val:.4f}  BORN IN SEEDING")
            print(f"       BRANCH: {_branch_of(c, idx)}")
            print(f"       pin set: "
                  + ("eat_anchor_rect" if idx in (c.get("eat_pin_idx") or {})
                     else "seam-family protection set"
                     if idx in (c.get("seam_pin_idx") or set())
                     else "none of the published pin sets")
                  + f"  [{_seed_pin_family(layout, idx, c['extra'])}]")
            print(f"       shapes: {_owning_shape(layout, pos)}")
            print(f"       extent: {_in_flat_extent(layout, pos)}")
            print(f"       DEM at this point: {_dem_at(layout, c, pos)}")
        log = c.get("log") or {}
        late = {i: rec for (i, rec) in log.items() if i not in c["born"]}
        print(f"   post-seeding writes below {thresh:+.3f} m: "
              f"{len(late)} node(s)")
        for idx in sorted(late, key=lambda k: min(r[2] for r in late[k]))[:worst]:
            pos = c["nodes"][idx] if idx < len(c["nodes"]) else None
            print(f"   node {idx}"
                  + (f" @({pos[0]:.1f},{pos[1]:.1f})" if pos else "")
                  + f" — {len(late[idx])} write(s)")
            for (where, old, new) in late[idx][:6]:
                print(f"       {old:10.4f} -> {new:10.4f}   by {where}")
            if pos is not None:
                print(f"       shapes: {_owning_shape(layout, pos)}")
                print(f"       extent: {_in_flat_extent(layout, pos)}")


def _dem_at(layout, call, pos):
    """The DEM value the solve's own seeding would sample at ``pos`` —
    the test of "is this number the terrain, or something the pipeline
    minted".  Uses the DEM object the captured seed call was handed."""
    dem = call.get("dem")
    if dem is None or pos is None:
        return "no DEM handed to the seed call"
    try:
        from auto_patch.elevation import _sample_dem
        lat, lon = layout.m_to_ll(float(pos[0]), float(pos[1]))
        v = _sample_dem(dem, call.get("tile_lat", 0), call.get("tile_lon", 0),
                        lat, lon)
        return ("None (no sample)" if v is None
                else f"{float(v):.4f} m at ({lat:.6f},{lon:.6f})")
    except Exception as exc:                                # pragma: no cover
        return f"? ({type(exc).__name__}: {exc})"


def _report_anchor_seed_classes(layout, captured=None, worst=12):
    """THE ANCHOR-SEED CLASSIFICATION — R17b-1's attribution deliverable.

    Which seeds does the value field carry, which of them are BELOW
    GRADE, and — the question the canyon actually asks — which seed
    carries the LOWEST value, since the ceiling is a MIN over anchors and
    a min never forgets.

    IT READS THE BUILD'S OWN PASSES, never a rebuild.  The field is
    rebuilt several times during one build and the layout GROWS between
    them, so the post-build rebuild a bare ``reach_band_unified`` gives
    is a different node space AND a different seed set from the one the
    writeback clamp obeyed (measured VHHH 2026-08-11: the rebuild's
    worst seed is Z0 7.315 while the clamp reports a carried ceiling of
    −12.14 at the same point).  ``_build`` captures every
    ``spine_value_fields`` pass; this reports them all and singles out
    the pass with the most-negative seed — the poisoned one.
    """
    from auto_patch.elevation_per_surface.building_feasibility import (
        below_grade_anchor_bodies)
    passes = list((captured or {}).get("passes") or [])
    if not passes:
        print("!! no band pass was captured — run this on a build")
        return
    print(f"band passes captured: {len(passes)}")
    for p in passes:
        print(f"  pass {p['i']}: {len(p['seeds'])} seed(s), "
              f"{p['nodes']} node(s), seed value min {p['seed_min']:.4f} "
              f"max {p['seed_max']:.4f}; ceiling min "
              f"{p['ceil_min']:.4f}  [{p['nodespace']}]")
    worst_pass = min(passes, key=lambda p: p["seed_min"])
    print(f"\n=== POISON CANDIDATE: pass {worst_pass['i']} "
          f"(lowest seed {worst_pass['seed_min']:.4f}) ===")
    G = worst_pass["G"]
    seeds = worst_pass["seeds"]
    pos = getattr(G, "pos", None) or {}
    bound: dict = {}
    for _u, rec in (worst_pass["ceiling"] or {}).items():
        bound[int(rec[0])] = bound.get(int(rec[0]), 0) + 1
    bodies = below_grade_anchor_bodies(layout, G, seeds)
    n_ceil = len(worst_pass["ceiling"] or {})
    sub = [a for a in seeds if seeds[a] < 0.0]
    sub_ceil = sum(bound.get(int(a), 0) for a in sub)
    print(f"anchor seeds: {len(seeds)};  BELOW-GRADE by body membership: "
          f"{len(bodies)};  seeds with a NEGATIVE value: {len(sub)} "
          f"(authoring {sub_ceil} of {n_ceil} ceilings)")
    order = sorted(seeds, key=lambda k: seeds[k])[:worst]
    print(f"the {len(order)} LOWEST-VALUED seed(s) — a ceiling MIN "
          f"propagates each of these along every route it can reach:")
    for a in order:
        p = pos.get(int(a))
        print(f"  anchor {a} value {seeds[a]:.4f}"
              + (f" @({p[0]:.1f},{p[1]:.1f})" if p else "")
              + f"  authored {bound.get(int(a), 0)} ceiling(s) of {n_ceil}")
        print(f"      shapes: {_owning_shape(layout, p)}")
        print(f"      extent: {_in_flat_extent(layout, p)}")
        print(f"      class:  {_anchor_class(layout, G, a, p)}")


def _report_pass_bands_at(layout, captured, x, y):
    """THE BAND AT ONE POINT, PASS BY PASS, with the anchor that authored
    it — the link between a clamp's reported band and the seed behind it.

    The writeback clamp obeys the band CARRIED out of the solve; naming
    the seed behind a clamped value therefore means asking the pass the
    clamp saw, not the post-build rebuild.
    """
    import math as _math
    passes = list((captured or {}).get("passes") or [])
    if not passes:
        print("!! no band pass was captured — run this on a build")
        return
    print(f"\n=== BAND AT ({x:.1f},{y:.1f}) PASS BY PASS ===")
    for p in passes:
        G = p["G"]
        pos = getattr(G, "pos", None) or {}
        ceil_side = p["ceiling"] or {}
        seeds = p["seeds"]
        best = None
        for n in ceil_side:
            q = pos.get(int(n))
            if q is None:
                continue
            d = _math.hypot(q[0] - x, q[1] - y)
            if best is None or d < best[0]:
                best = (d, int(n), q)
        if best is None:
            print(f"  pass {p['i']}: no ceiling-carrying node at all")
            continue
        d, node, q = best
        rec = ceil_side[node]
        anchor, budget = int(rec[0]), float(rec[1])
        ceiling = seeds.get(anchor, 0.0) + budget
        ap = pos.get(anchor)
        print(f"  pass {p['i']}: nearest ceiling node {node} "
              f"@({q[0]:.1f},{q[1]:.1f}) {d:.1f} m away — ceiling "
              f"{ceiling:.4f} = anchor {anchor} value "
              f"{seeds.get(anchor, float('nan')):.4f} + budget {budget:.4f}")
        print(f"      anchor shapes: {_owning_shape(layout, ap)}")
        print(f"      anchor extent: {_in_flat_extent(layout, ap)}")
        print(f"      anchor class:  {_anchor_class(layout, G, anchor, ap)}")


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
    print(f"  node space: {r.get('nodespace', 'none')}")
    band = r.get("band")
    if band is None:
        print("  reach band: None (OFF-NET)")
        print(f"  {r.get('why_none', '')}")
    else:
        print(f"  reach band: floor={band[0]:.4f}  ceiling={band[1]:.4f}"
              f"  (width {band[1] - band[0]:+.4f} m)")
    att = r.get("attachment")
    if att is None:
        print("  attachment: None — the grid lookup serves no attachment at "
              "this cell (off-net)")
        print("  frame note: the route band does not reach a point with no "
              "attachment; the LOCAL within-shape law (grade_law's "
              "within-shape family) is the frame to read it in")
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
        print("  !! no anchor provenance recorded on this layout "
              "(layout._band_anchor_provenance absent or empty) — the "
              "binding anchor cannot be named from it")
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
        print(f"           anchor class: "
              f"{_anchor_class(r.get('layout'), r.get('G'), s['anchor'], ap)}")
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
    cap = captured or {}
    rows_from_capture = bool(cap.get("rows"))
    rows = list(cap.get("rows")
                or getattr(layout, "_final_band_inversions", None) or [])
    if not rows:
        print("no recorded band inversions on this layout")
        return
    G = cap.get("G")
    prov = cap.get("prov")
    if G is None or not prov:
        print("!! the build's own band graph/provenance was not captured — "
              "refusing to rebuild it, because a rebuilt field is a "
              "different node space and the inversion rows do not resolve "
              "in it.  Run this on a build (not a stale layout).")
        return
    # ── NODE-SPACE STAMP ON BOTH SIDES, then a MEASURED verdict ────────
    # The walk reads ``G``/``prov``; the recorded budgets come from the
    # inversion rows.  Whether those are the same node space is a FACT the
    # capture can answer (G, prov and rows are all taken inside ONE
    # ``_record_band_inversions`` call), so it is measured here and stated,
    # not asserted as a cause of any number below.
    walk_ns = _nodespace(G)
    rows_ns = cap.get("nodespace") if rows_from_capture else None
    if rows_ns is None:
        frames = ("frames NOT COMPARED (the rows came from the layout "
                  "attribute and carry no node-space stamp)")
        frames_short = "frames not compared"
    elif rows_ns == walk_ns:
        frames = f"frames match ({walk_ns})"
        frames_short = "frames match"
    else:
        frames = (f"frames differ (walk {walk_ns} vs recorded rows {rows_ns})")
        frames_short = "frames differ"
    print(f"node space: walk {walk_ns}; recorded rows "
          f"{rows_ns or 'unstamped'} — {frames}")
    print(f"budget agreement contract: {ROUTE_BUDGET_AGREEMENT_M:g} m")
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
                print(f"    {side.upper():<8} !! the recorded field holds no "
                      f"{side} route for node {node}, which the inversion "
                      f"rows do name — the two readings disagree "
                      f"({frames_short})")
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
                  + ("" if abs(drift) <= ROUTE_BUDGET_AGREEMENT_M else
                     f"  [BUDGET DRIFT vs the build's own field "
                     f"{drift:+.4f} m > contract "
                     f"{ROUTE_BUDGET_AGREEMENT_M:g} m; {frames_short}]"))
            print(f"             anchor class: "
                  f"{_anchor_class(layout, G, s['anchor'], ap)}")
            _print_caps(s, indent="             ")


# ── ONE KML SKELETON, TWO MODES ──────────────────────────────────────────
# Factored out of ``_kml`` (spec ``docs/specs/pad-binding-routes-spec.md``
# §2.2): the live mode and ``--from-sidecar`` render the same document
# vocabulary — same styles, same LineString/Placemark spelling, same 7-dp
# coordinates — so a reader who knows one render knows the other.  Extend
# the near-fit, never fork (RULINGS ``7e90032``).
#
# The skeleton speaks LAT/LON only.  The live mode holds local metres and
# converts on the way in (it is the only side that has a layout anchor to
# convert with); the sidecar mode already has lat/lon and hands them
# straight over.
_KML_STYLES = (
    ('r', 'ff00ffff', 5, None),        # ceiling route — yellow, fat
    ('f', 'ff00ff00', 3, None),        # floor route — green
    ('ap', 'ffff8800', 2, '20ff8800'),  # apron ring
    ('bl', 'ff0000ff', 2, '300000ff'),  # building ring
)


def _xq(text):
    """XML text escape for a Placemark name.

    Shape refs are free text out of OSM; an unescaped ``&`` makes the
    whole document unparseable, which is a render that silently fails in
    the viewer rather than at the writer."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


class _KmlDoc:
    """The KML document both modes build (see the block above)."""

    def __init__(self):
        self.parts = ['<?xml version="1.0"?>',
                      '<kml xmlns="http://www.opengis.net/kml/2.2">'
                      '<Document>']
        for (sid, color, width, poly) in _KML_STYLES:
            self.parts.append(
                f'<Style id="{sid}"><LineStyle><color>{color}</color>'
                f'<width>{width}</width></LineStyle>'
                + ('' if poly is None else
                   f'<PolyStyle><color>{poly}</color></PolyStyle>')
                + '</Style>')

    @staticmethod
    def _coords(lls):
        """KML's ``lon,lat,0`` triples from ``(lat, lon)`` pairs."""
        return " ".join(f"{float(lo):.7f},{float(la):.7f},0"
                        for (la, lo) in lls)

    def folder(self, name):
        self.parts.append(f'<Folder><name>{_xq(name)}</name>')

    def end_folder(self):
        self.parts.append('</Folder>')

    def point(self, name, lat, lon):
        self.parts.append(
            f'<Placemark><name>{_xq(name)}</name><Point><coordinates>'
            f'{float(lon):.7f},{float(lat):.7f},0'
            f'</coordinates></Point></Placemark>')

    def note(self, name):
        """A geometry-less Placemark — the honest render of a record that
        carries no coordinates at all (an off-network pad: the schema has
        a seat and a verdict, and deliberately no position).  It shows in
        the viewer's places list, which is where such an ANSWER belongs."""
        self.parts.append(f'<Placemark><name>{_xq(name)}</name></Placemark>')

    def line(self, name, style, lls):
        self.parts.append(
            f'<Placemark><name>{_xq(name)}</name>'
            f'<styleUrl>#{style}</styleUrl><LineString><coordinates>'
            f'{self._coords(lls)}</coordinates></LineString></Placemark>')

    def ring(self, name, style, lls):
        self.parts.append(
            f'<Placemark><name>{_xq(name)}</name>'
            f'<styleUrl>#{style}</styleUrl>'
            f'<Polygon><outerBoundaryIs><LinearRing><coordinates>'
            f'{self._coords(lls)}</coordinates></LinearRing>'
            f'</outerBoundaryIs></Polygon></Placemark>')

    def write(self, out_path):
        self.parts.append('</Document></kml>')
        with open(out_path, "w") as f:
            f.write("\n".join(self.parts) + "\n")
        print(f"wrote {out_path}")


def _kml(layout, r, x, y, label, out_path):
    lat0, lon0 = layout.anchor
    R = 6378137.0
    cos0 = math.cos(math.radians(lat0))

    def ll(px, py):
        """Local metres → ``(lat, lon)`` — the skeleton's own vocabulary."""
        return (lat0 + math.degrees(py / R),
                lon0 + math.degrees(px / (R * cos0)))

    from shapely.geometry import Point as _P
    from auto_patch.grade_graph import _open_ring
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING

    doc = _KmlDoc()
    band = r.get("band")
    _la, _lo = ll(x, y)
    doc.point(f"target {label}" + ("" if band is None else
                                   f" band [{band[0]:.2f}, {band[1]:.2f}]"),
              _la, _lo)
    for side, style in (("ceiling", "r"), ("floor", "f")):
        s = r.get(side)
        if not s or len(s["path"]) < 2:
            continue
        doc.line(f'{side} route {s["runway"]} {s["anchor_value"]:.2f} + '
                 f'{s["route_budget_m"]:.2f} m', style,
                 [ll(*p) for p in s["path"]])
        ap = s["anchor_pos"]
        if ap:
            doc.point(f"{side} anchor {s['runway']} {s['anchor_value']:.2f}",
                      *ll(ap[0], ap[1]))
    pos = r.get("attachment_pos")
    if pos:
        doc.point(f"attachment node {r['attachment_node']}",
                  *ll(pos[0], pos[1]))
    near = _P(x, y)
    for s in layout.shapes:
        if (s.polygon is None or s.polygon.is_empty
                or s.polygon.distance(near) > 120):
            continue
        if s.role in (ROLE_APRON, ROLE_BUILDING):
            ring = _open_ring(list(s.polygon.exterior.coords))
            doc.ring(f"apron {s.polygon.area:.0f}m2"
                     if s.role == ROLE_APRON else str(s.ref),
                     "ap" if s.role == ROLE_APRON else "bl",
                     [ll(*p) for p in ring + [ring[0]]])
    doc.write(out_path)


# ══════════════════════════════════════════════════════════════════════
# ``--from-sidecar`` — the OFFLINE render (spec §2).  NO BUILD, NO SOLVE,
# NO LAYOUT: it reads the ``pad_binding_routes`` the engine published into
# the patch's ``.axes.json`` and draws it.  Nothing below may import the
# solver — that is the whole point of the mode, and the reason the live
# modes keep their imports inside their own functions.
# ══════════════════════════════════════════════════════════════════════

#: What a sidecar without the key means, and what to do about it.
_NO_KEY_MSG = (
    "this patch predates route publication — its sidecar carries no "
    "'pad_binding_routes' key.  Rebuild it (tools/harness/build_airport.py "
    "ICAO) to get the published routes, or use the LIVE modes of this tool "
    "(they build the airport and read the band in-process).")


def _sidecar_path(arg):
    """``X.osm`` → ``X.osm.axes.json``; an ``.axes.json`` path passes
    through.  Both spellings are accepted because both are what a reader
    has in hand (§2.1)."""
    s = str(arg)
    return s if s.endswith(".axes.json") else s + ".axes.json"


def _sidecar_records(path, refs):
    """``(records, container)`` for the requested pads, or ``sys.exit`` with
    the fact and its remedy.

    Every "nothing to draw" case is NAMED — a missing key, a capture that
    could not run, a build with no pads, a filter that matched nothing —
    because an empty render that says nothing is how an instrument becomes
    untrustworthy."""
    import json as _json
    if not os.path.exists(path):
        sys.exit(f"no sidecar at {path} — every emit writes one, so a "
                 f"missing sidecar means this patch was not emitted by "
                 f"this tree.")
    data = _json.loads(open(path).read())
    if "pad_binding_routes" not in data:
        sys.exit(_NO_KEY_MSG)
    box = data["pad_binding_routes"] or {}
    ns = box.get("nodespace")
    recs = list(box.get("records") or [])
    print(f"sidecar {path}")
    if ns is None:
        print("pad_binding_routes: nodespace=null — the CAPTURE COULD NOT "
              "RUN on this build (no unified graph handed to the seat pass, "
              "a band with no attachment lookup, no recorded anchor "
              "provenance, or the pass-identity guard refused).  Nothing to "
              "render; this is an answer, not a failure.")
        return [], box
    print(f"pad_binding_routes: node space {ns}, {len(recs)} pad record(s)")
    if not recs:
        print("the capture RAN and recorded no pads (records: []) — this "
              "build seated no building pad off a served frontage.")
        return [], box
    if refs:
        want = set(refs)
        got = [r for r in recs if r.get("pad") in want]
        if not got:
            sys.exit(f"--ref {sorted(want)} matches no published pad.  This "
                     f"sidecar names: "
                     f"{', '.join(sorted(str(r.get('pad')) for r in recs))}")
        recs = got
    return recs, box


def _print_sidecar_records(recs):
    """The record, in words — the render is the map, this is the answer."""
    for r in recs:
        print(f"\npad {r.get('pad')}  seat "
              f"{float(r.get('seat_m', 0.0)):.4f} m")
        if r.get("off_network"):
            print("  OFF-NETWORK: the band serves none of this pad's "
                  "frontage points, so no route bound its seat — the "
                  "within-shape law governs it.  An answer, not a refusal.")
            continue
        for side in ("ceiling", "floor"):
            s = (r.get("sides") or {}).get(side)
            if not s:
                print(f"  {side.upper():<8} not published (the binding "
                      f"frontage point carries no {side}-side "
                      f"provenance-known node)")
                continue
            print(f"  {side.upper():<8} anchor node {s['anchor_node']} @"
                  f"{s['anchor_ll']} value {s['anchor_value_m']:.4f} m, "
                  f"route budget {s['route_budget_m']:.4f} m over "
                  f"{len(s['route_ll'])} node(s) / {s['plan_len_m']:.1f} m "
                  f"of plan"
                  + ("" if s["route_complete"] else
                     "  [ROUTE INCOMPLETE — the recorded budgets do not "
                     "reconcile through the graph; the anchor and budget "
                     "are still the field's own]"))
            print(f"           binding frontage {s['frontage_ll']} band "
                  f"[{s['band_floor_m']:.4f}, {s['band_ceiling_m']:.4f}]")


def _kml_from_sidecar(recs, out_path):
    doc = _KmlDoc()
    for r in recs:
        pad = r.get("pad")
        seat = float(r.get("seat_m", 0.0))
        doc.folder(f"pad {pad} seat {seat:.2f}")
        if r.get("off_network"):
            doc.note(f"pad {pad} OFF-NETWORK — no frontage the band serves; "
                     f"the within-shape law governs this seat ({seat:.2f} m)")
            doc.end_folder()
            continue
        for side, style in (("ceiling", "r"), ("floor", "f")):
            s = (r.get("sides") or {}).get(side)
            if not s:
                continue
            lls = [tuple(p) for p in (s.get("route_ll") or ())]
            if len(lls) >= 2:
                doc.line(f"{pad} {side} route {s['route_budget_m']:.2f} m "
                         f"over {s['plan_len_m']:.0f} m", style, lls)
            if s.get("anchor_ll"):
                doc.point(f"{pad} {side} anchor node {s['anchor_node']} "
                          f"value {s['anchor_value_m']:.2f} + budget "
                          f"{s['route_budget_m']:.2f} m over "
                          f"{s['plan_len_m']:.0f} m, complete="
                          f"{bool(s['route_complete'])}",
                          s["anchor_ll"][0], s["anchor_ll"][1])
            if s.get("frontage_ll"):
                doc.point(f"{pad} {side} frontage band "
                          f"[{s['band_floor_m']:.2f}, "
                          f"{s['band_ceiling_m']:.2f}] seat {seat:.2f}",
                          s["frontage_ll"][0], s["frontage_ll"][1])
        doc.end_folder()
    doc.write(out_path)


def _osm_from_sidecar(recs, out_path):
    """A VIEWER artifact (JOSM), never a patch (spec §2.2).

    The patch loader globs ``*.patch.osm``; an ``--out`` that would land in
    that glob is REFUSED at the writer, because a render that can be loaded
    as scenery is a render that eventually will be.  No ``.axes.json`` is
    written beside it for the same reason."""
    if str(out_path).endswith(".patch.osm"):
        sys.exit(f"refusing to write {out_path}: the patch loader globs "
                 f"*.patch.osm, and this render is a VIEWER artifact, not "
                 f"scenery.  Choose another name (e.g. "
                 f"{str(out_path)[:-len('.patch.osm')]}.route.osm).")
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<osm version="0.6" generator="trace_reach_route --from-'
             'sidecar">']
    nid, wid = -1, -1
    for r in recs:
        pad = r.get("pad")
        if r.get("off_network"):
            continue
        for side in ("ceiling", "floor"):
            s = (r.get("sides") or {}).get(side)
            if not s:
                continue
            lls = [tuple(p) for p in (s.get("route_ll") or ())]
            if len(lls) < 2:
                continue
            ids = []
            for (la, lo) in lls:
                parts.append(f'  <node id="{nid}" lat="{float(la):.7f}" '
                             f'lon="{float(lo):.7f}" version="1"/>')
                ids.append(nid)
                nid -= 1
            parts.append(f'  <way id="{wid}" version="1">')
            wid -= 1
            for i in ids:
                parts.append(f'    <nd ref="{i}"/>')
            for (k, v) in (("pad_binding_route", side),
                           ("pad", pad),
                           ("anchor_node", s["anchor_node"]),
                           ("route_budget_m", f"{s['route_budget_m']:.4f}"),
                           ("plan_len_m", f"{s['plan_len_m']:.4f}"),
                           ("route_complete",
                            "true" if s["route_complete"] else "false"),
                           ("band_floor_m", f"{s['band_floor_m']:.4f}"),
                           ("band_ceiling_m", f"{s['band_ceiling_m']:.4f}")):
                parts.append(f'    <tag k="{k}" v="{_xq(v)}"/>')
            parts.append('  </way>')
    parts.append('</osm>')
    with open(out_path, "w") as f:
        f.write("\n".join(parts) + "\n")
    print(f"wrote {out_path}")


def _from_sidecar(args):
    """The whole ``--from-sidecar`` mode: read, report, render.  No build."""
    conflicts = [name for (name, on) in (
        ("the ICAO positional", bool(args.icao)),
        ("--dem", args.dem is not None),
        ("--coord", bool(args.coord)),
        ("--inverted-pairs", bool(args.inverted_pairs)),
        ("--below-grade-anchors", bool(args.below_grade_anchors)),
        ("--hard-seed-writers", args.hard_seed_writers is not None),
    ) if on]
    if conflicts:
        sys.exit(f"--from-sidecar reads a published patch and never builds; "
                 f"it is mutually exclusive with the build modes "
                 f"({', '.join(conflicts)}).  --ref in this mode is a FILTER "
                 f"on the published pads.")
    out = args.out
    if str(out).endswith(".patch.osm"):
        sys.exit(f"refusing to write {out}: the patch loader globs "
                 f"*.patch.osm, and this render is a VIEWER artifact, not "
                 f"scenery.")
    recs, _box = _sidecar_records(_sidecar_path(args.from_sidecar),
                                  list(args.ref or []))
    if not recs:
        return 0
    _print_sidecar_records(recs)
    if str(out).endswith(".osm"):
        _osm_from_sidecar(recs, out)
    else:
        _kml_from_sidecar(recs, out)
    return 0


def _install_seed_writer_capture(seen, thresh=0.0):
    """Capture WHO wrote each below-``thresh`` hard seed (R17c-1).

    Three shims, all read-only pass-throughs:

      * ``solver_primitives._seed_elevations`` — on return, snapshot the
        hard nodes already below ``thresh`` (BORN IN SEEDING) and hand
        the solve a :class:`_WriteTracedElev` in place of its plain
        ``elev`` list, so every LATER write is attributed to its
        ``file:line``.  ``readonly=True`` calls (measurement probes)
        are passed straight through untouched — instrumenting a probe
        would attribute the probe;
      * ``flat_fast_path.apply_seed_pins`` and
        ``solver_primitives._build_tunnel_road_pins`` — the two pin
        families that do NOT publish a private index set, captured from
        their own arguments/returns so the family report is production's
        own answer.

    Returns the ``restore()`` callable."""
    from auto_patch.elevation_per_surface import solver_primitives as SP
    from auto_patch import flat_fast_path as FFP

    real_seed = SP._seed_elevations
    real_apply = FFP.apply_seed_pins
    real_tunnel = SP._build_tunnel_road_pins
    pending: dict = {}

    def _apply_shim(layout, plan, nodes, bucket_to_idx, elev, is_hard,
                    *a, **k):
        before = {i for i, h in enumerate(is_hard) if h}
        out = real_apply(layout, plan, nodes, bucket_to_idx, elev, is_hard,
                         *a, **k)
        pending.setdefault("flat_fast_path", set()).update(
            {i for i, h in enumerate(is_hard) if h} - before)
        return out

    def _tunnel_shim(layout, bucket_to_idx, elev, is_hard, intern,
                     *a, **k):
        out = real_tunnel(layout, bucket_to_idx, elev, is_hard, intern,
                          *a, **k)
        pending.setdefault("tunnel_road_pin", set()).update(
            int(i) for i in (out or {}))
        return out

    def _seed_shim(layout, nodes, bucket_to_idx, dem=None, tile_lat=0,
                   tile_lon=0, *, readonly=False):
        pending.clear()
        elev, is_hard, have = real_seed(layout, nodes, bucket_to_idx, dem,
                                        tile_lat, tile_lon,
                                        readonly=readonly)
        if readonly:
            return elev, is_hard, have
        born = {i: (float(elev[i]), tuple(nodes[i][:2]))
                for i in range(min(len(elev), len(is_hard), len(nodes)))
                if is_hard[i] and elev[i] < thresh}
        hard_idx = [i for i in range(min(len(elev), len(is_hard)))
                    if is_hard[i]]
        # THE BRANCH THAT SUPPLIED EACH VALUE, in the CALL'S OWN node
        # space (``O4_SEED_BRANCH_ATTRIB=1``).  Snapshotted here rather
        # than read at report time: a solve's node indices are valid only
        # inside the ``_build_node_list`` call that assigned them, and
        # reading a later solve's map against this call's indices is the
        # index-join-across-a-rebuild trap this repo has a law about.
        branch = dict(getattr(layout, "_seed_branch_attrib", None) or {})
        traced = _WriteTracedElev(elev, thresh, watch=born)
        seen.setdefault("seed_calls", []).append({
            "i": len(seen.get("seed_calls") or []),
            "n": len(elev),
            "n_hard": sum(1 for h in is_hard if h),
            "born": born,
            "branch": branch,
            "hard_idx": hard_idx,
            "seam_pin_idx": set(getattr(layout, "_seam_pin_idx", None)
                                or ()),
            "eat_pin_idx": dict(getattr(layout, "_eat_anchor_pin_idx",
                                        None) or {}),
            "extra": {k2: set(v) for (k2, v) in pending.items()},
            "nodes": nodes,
            "dem": dem,
            "tile_lat": tile_lat,
            "tile_lon": tile_lon,
            "log": traced.log,
        })
        return traced, is_hard, have

    SP._seed_elevations = _seed_shim
    FFP.apply_seed_pins = _apply_shim
    SP._build_tunnel_road_pins = _tunnel_shim

    def _restore():
        SP._seed_elevations = real_seed
        FFP.apply_seed_pins = real_apply
        SP._build_tunnel_road_pins = real_tunnel
    return _restore


def _build(icao, const_dem=None, seed_writers=None):
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
    # THE ARMING COMPOSITION, imported from the harness build entry and
    # never re-assembled here (``build_airport.arm_shared_repo_protection``
    # — the classify_report precedent: a tool that built the engine
    # in-process with NEITHER half wrote ten files into the shared corpus
    # on 2026-08-11).  The redirect must land BEFORE the engine import, so
    # it happens first and ``auto_patch.pipeline`` is imported after it.
    _harness = os.path.join(os.path.dirname(__file__), "harness")
    if _harness not in sys.path:
        sys.path.insert(0, _harness)
    import build_airport as _HB
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    _tag = f"trace_{icao}"
    _out_dir = os.environ.get("O4_TRACE_OUT_DIR") or "/tmp/harness"
    guard, redirects = _HB.arm_shared_repo_protection(_root, _out_dir, _tag)
    print(f"[trace] shared-repo write guard ARMED (enabled={guard.enabled}); "
          f"engine cache redirects: {sorted(redirects)}")

    from auto_patch.pipeline import build_airport_pavement
    from auto_patch.elevation_per_surface import building_feasibility as BF

    kw = {"compute_elevations": True}
    # WORLD/DEM FRAME — printed on EVERY run.  It used to print only under
    # ``--dem``, so a real-DEM trace carried no world stamp at all and its
    # numbers were indistinguishable from an oracle world's in a transcript.
    if const_dem is not None:
        from auto_patch.constant_dem import ConstantDEM
        kw["tile_dem"] = ConstantDEM(float(const_dem))
        print(f"[trace] world: CONSTANT-DEM oracle, DEM = "
              f"{float(const_dem):g} m everywhere "
              f"(auto_patch.constant_dem.ConstantDEM)")
    else:
        print("[trace] world: REAL DEM — the production tile DEM for this "
              "airport (no --dem override)")
    print(f"[trace] {CROWN_SPACE_NOTE}")

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
        # EVERY PASS, not only the last (R17b-1).  The clamp obeys the
        # band CARRIED out of the solve, which an intermediate pass
        # built; the last pass is the post-emit rebuild, on a layout
        # that has since grown.  Attributing the clamp from the last
        # pass is the two-instruments trap.
        _seeds = {int(k2): float(v) for (k2, v)
                  in (prov.get("anchor_value") or {}).items()}
        _ceil = dict(prov.get("ceiling") or {})
        if _seeds:
            _cvals = [(_seeds.get(int(r[0]), 0.0) + float(r[1]))
                      for r in _ceil.values()] or [float("nan")]
            seen.setdefault("passes", []).append({
                "i": len(seen.get("passes") or []),
                "G": G,
                "seeds": _seeds,
                "ceiling": _ceil,
                "nodes": len(getattr(G, "pos", None) or ()),
                "seed_min": min(_seeds.values()),
                "seed_max": max(_seeds.values()),
                "ceil_min": min(_cvals),
                "nodespace": _nodespace(G),
            })
        seen["G"] = G
        seen["prov"] = {"anchor_value": dict(prov.get("anchor_value") or {}),
                        "ceiling": dict(prov.get("ceiling") or {}),
                        "floor": dict(prov.get("floor") or {})}
        seen["rows"] = list(getattr(layout, "_final_band_inversions", None)
                            or [])
        # G, prov and rows are all taken INSIDE this one call, so they share
        # one node space by construction; stamping it here is what lets the
        # report say "frames match" as a measured fact instead of assuming it.
        seen["nodespace"] = _nodespace(G)
        return out

    BF.assert_no_final_band_inversion = _capturing_assert
    BF._record_band_inversions = _capturing_record
    _restore_seed = (_install_seed_writer_capture(seen, seed_writers)
                     if seed_writers is not None else None)
    try:
        with guard:
            layout = build_airport_pavement(icao, xplane_root(), **kw)
        _HB.require_no_swallowed_write_block(guard.blocked)
        _HB.report_guard_churn(guard)
        return layout, None, seen
    except BF.BandInversionError as exc:
        if "layout" not in seen:
            raise
        print("[trace] the build FAILED its final band-inversion law; "
              "tracing the layout it failed on.\n")
        # The guard's own verdict still has to be reported: a refusal the
        # engine SWALLOWED would make this trace a different frame from
        # production's, band error or not.
        _HB.require_no_swallowed_write_block(guard.blocked)
        _HB.report_guard_churn(guard)
        return seen["layout"], exc, seen
    finally:
        BF.assert_no_final_band_inversion = real_assert
        BF._record_band_inversions = real_record
        if _restore_seed is not None:
            _restore_seed()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("icao", nargs="?",
                    help="the airport to BUILD and trace live (omit with "
                         "--from-sidecar, which builds nothing)")
    ap.add_argument("--from-sidecar", metavar="PATCH.osm",
                    help="render the pad BINDING ROUTES an emitted patch "
                         "published (its .axes.json 'pad_binding_routes' "
                         "key; the .axes.json path itself is accepted too). "
                         "NO build, NO solve — the engine already computed "
                         "these routes and wrote them down.  --ref filters "
                         "the pads; --out picks the format by extension "
                         "(.kml, .osm)")
    ap.add_argument("--ref", action="append", default=[],
                    help="shape ref (e.g. building5).  Repeatable — in the "
                         "live modes one trace per ref, with --from-sidecar "
                         "a filter on the published pads (default: all)")
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
    ap.add_argument("--below-grade-anchors", action="store_true",
                    help="classify every anchor seed of the live field and "
                         "name the BELOW-GRADE ones (R17b-1): value, body, "
                         "governed nodes, ceilings authored")
    ap.add_argument("--hard-seed-writers", nargs="?", type=float,
                    const=0.0, default=None, metavar="THRESH",
                    help="attribute WHO wrote each hard seed below THRESH "
                         "metres (default 0.0) — born-in-seeding vs a later "
                         "pass, with the writing file:line (R17c-1)")
    ap.add_argument("--out", default="/tmp/reach_route.kml")
    args = ap.parse_args()

    # THE OFFLINE MODE FIRST, and before ANY engine import (spec §2.1):
    # reading a published record must never pay for — or depend on — the
    # solver being importable.
    if args.from_sidecar:
        return _from_sidecar(args)
    if not args.icao:
        ap.error("give an ICAO to build and trace, or --from-sidecar "
                 "PATCH.osm to render what a patch already published")

    layout, band_err, captured = _build(args.icao, args.dem,
                                        seed_writers=args.hard_seed_writers)

    if args.hard_seed_writers is not None:
        _report_hard_seed_writers(layout, captured, args.hard_seed_writers)
        if (not args.coord and not args.ref and not args.inverted_pairs
                and not args.below_grade_anchors):
            return 0

    if args.below_grade_anchors:
        _report_anchor_seed_classes(layout, captured)
        for c in args.coord:
            _x, _y = (float(v) for v in c.split(","))
            _report_pass_bands_at(layout, captured, _x, _y)
        if not args.coord and not args.ref and not args.inverted_pairs:
            return 0

    if args.inverted_pairs:
        _report_inverted_pairs(layout, captured)
        if not args.coord and not args.ref:
            return 0

    targets = []
    for c in args.coord:
        x, y = (float(v) for v in c.split(","))
        targets.append((x, y, c))
    for ref in (args.ref or []):
        s = next((s for s in layout.shapes if str(s.ref) == ref), None)
        if s is None or s.polygon is None:
            sys.exit(f"ref {ref} not found / no polygon")
        targets.append((s.polygon.centroid.x, s.polygon.centroid.y, ref))
    if not targets and not args.inverted_pairs:
        sys.exit("give --ref, --coord, --inverted-pairs or "
                 "--below-grade-anchors")

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
