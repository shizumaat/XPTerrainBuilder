"""Anchors + bounds for the one-profile solve — all from THE ONE graph.

There is a single reachability graph: the reach band computed on THE unified
grade graph (``building_feasibility.reach_band_unified``).  It sets the building
levels AND bounds every apron / spine / rect node, so they agree by
construction.  This module never builds a second graph.

* ``reach_band_for`` — build the band (+ a DEM sampler + the runway-edge anchors)
  once per solve.
* ``build_building_seats`` — seat each airside building FLAT at the level its
  FRONTAGE can reach (the band intersected over the pad ring), not the centroid:
  the band is a per-point envelope and a serving centerline climbs along a pad,
  so the centroid may reach higher than the apron around the pad can grade to.
* ``node_bands`` — the per-node ``(floor, ceiling)`` the solve clamps into.
* ``apron_body_nodes`` — apron-body vs taxi-route role split (target only).

PADS ARE BAND-BOUNDED VARIABLES (spec
``docs/specs/pads-as-band-variables-spec.md``, owner rulings RULINGS
2026-08-27 late).  Under ``O4_PADS_BAND_VARIABLES`` (default ON) a DERIVED
airside pad is ONE FREE FLAT VARIABLE whose DOMAIN is the INTERSECTION of
the narrowed band intervals over its RING VERTICES, and its seat is the
value the joint pass settles on INSIDE that domain — not a level chosen
first (ring median / frontage box, clamped to DEM) and defended
afterwards.  The domain arithmetic and the authored-datum group arithmetic
live in ``auto_patch.pad_variables``; this module owns the band, the rings
and the coupling, and calls into it.  OFF restores the pre-ruling seat pass
byte-identically.
"""
from __future__ import annotations

import math
import os as _os

from auto_patch.layout import (
    ROLE_APRON, ROLE_BUILDING, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD, ROLE_STUB,
)
from ..node_space import store_of as _store_of

_INF = float("inf")

#: PAD-SEAT FEASIBILITY GATE materiality floor (owner ruling RULINGS
#: 2026-08-24c; the standing 0.01 m elevation floor of the convergence
#: guards).  A seat inside its reach interval by less than this is a
#: rounding residual, not a seat defect.
_SEAT_FEASIBILITY_TOL_M = 0.01


def seat_feasibility_gap(level, lo, hi):
    """THE PAD-SEAT FEASIBILITY PREDICATE (owner ruling RULINGS
    2026-08-24c), as one pure function so the gate and its twin cannot
    describe different populations.

    ``(gap_m, side)`` — how far the seat lies OUTSIDE the interval of
    levels its governing centerline anchor permits at 1 % x chord (which
    is what the reach band measures), and which side it fell off.
    ``(0.0, None)`` when the seat is inside, or when the interval is not
    finite (an off-network pad has no governing anchor to be judged
    against, and inventing one would be the very long-pair class A4
    exists to remove).

    NOT a verdict on the surface: a seat defect is caught at seating time
    and is never surface debt.
    """
    if lo is None or hi is None:
        return 0.0, None
    try:
        lo_f, hi_f, lv = float(lo), float(hi), float(level)
    except (TypeError, ValueError):                        # pragma: no cover
        return 0.0, None
    if not (math.isfinite(lo_f) and math.isfinite(hi_f)
            and math.isfinite(lv)):
        return 0.0, None
    short, over = lo_f - lv, lv - hi_f
    if short >= over:
        return (short, "below_floor") if short > 0.0 else (0.0, None)
    return (over, "above_ceiling") if over > 0.0 else (0.0, None)


def _publish_seat_infeasible(layout, records, report) -> None:
    """THE PAD-SEAT FEASIBILITY GATE's read-out (RULINGS 2026-08-24c).

    A seat that cannot reach its governing centerline anchor within
    1 % x chord is a SEAT DEFECT caught at seating time — the
    anchor-placement law's analogue ("a misplaced anchor is itself the
    defect") — and is NEVER surface debt.  So it is named here and
    published for the census as EVIDENCE rather than left to appear
    downstream as a pile of over-cap apron rows nobody can attribute.

    REPORT-FIRST BY ORDER: nothing is moved.  The count and the names are
    this round's deliverable; the fix policy is the next ruling.
    """
    setattr(layout, "_pad_seat_infeasible", list(records))
    if not records:
        return
    worst = sorted(records, key=lambda r: -r["gap_m"])
    below = sum(1 for r in records if r["side"] == "below_floor")
    report(f"  [pad-seat] {len(records)} pad seat(s) OUTSIDE their own "
           f"reach interval ({below} below the floor, "
           f"{len(records) - below} above the ceiling) — SEAT DEFECTS, not "
           f"surface debt (RULINGS 2026-08-24c); worst "
           f"{worst[0]['gap_m']:.3f} m.  Report-only this round: no seat "
           f"is moved.")
    for r in worst[:12]:
        report(f"  [pad-seat]   {r['ref']}: seat {r['seat_m']:.3f} vs reach "
               f"[{r['reach_lo_m']:.3f},{r['reach_hi_m']:.3f}] "
               f"({r['side']}, {r['gap_m']:+.3f} m, "
               f"{r['area_m2']:,.0f} m2)")


# ── THE PART-C MOUTH ALLOWANCE (one definition, two consumers) ───────────
# ``MOUTH_ALLOWANCE_M = 15 m`` — justification (spec
# ``apron-string-and-scheduling-spec.md`` §C): the physical mouth zone is the
# connector throat, whose scale is already named in ``apply_groundside_reach``
# as ``RAISE_W = 14 m`` (the truck-route corridor half-width the raise pass
# uses); 15 m is one throat-width, rounded.
#
# It bounds groundside twice, and the two bounds must never drift apart:
#   * Part C bounds the pin's VALUE — a pin may not sit more than
#     ``cap · MOUTH_ALLOWANCE_M`` above the WELD DATUM it serves
#     (``gs_pin_float_cap``; the datum is a SOLVED pavement variable —
#     see :func:`gs_pin_law_ceiling`);
#   * the groundside FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30,
#     memory ``groundside-terrace-law``) bounds the pin's ROLE — it may
#     witness an airside node's ``[floor, ceiling]`` only inside the same
#     one-throat reach, expressed in the envelope's BUDGET metric
#     (``gs_witness_horizon``, the identical scalar).
# Single-pass principle: one definition, so a change to the allowance moves
# both bounds together.
def gs_mouth_allowance_m() -> float:
    """The Part-C mouth allowance, in metres of route length."""
    return 15.0


def gs_pin_float_cap(cap: float) -> float:
    """Part C's ALLOWANCE: how far above its WELD DATUM a groundside pin
    may float (metres of elevation) — one connector throat of reach at
    ``cap``.

    THE DATUM IS NOT THE DEM (item 3(a), 2026-08-05, RULINGS "DEM's role,
    and the constant-DEM invariant": *"DEM chooses WHERE in the lawful
    band a thing seats.  It never shapes the band, never constrains,
    never blocks."*).  This scalar used to be added to the pin's OWN DEM
    SAMPLE and published as a real solver bound, so raw ground decided
    how high a lawful groundside surface could sit.  The allowance is
    unchanged; the datum is now :func:`gs_pin_law_ceiling`'s solved
    host-pavement variable.

    WHY THE OLD DATUM FAILED THE CONSTANT-DEM ORACLE (the inspection
    argument, kept because it is the reason this function's contract
    changed): on a DEM ≡ c build the ceiling collapsed to the flat
    ``c + cap·15 m`` for every pin — ≈0.75 m above the constant at the
    service-road cap — so any lot that must weld to pavement higher than
    that was clamped below its lawful level and emitted a violation on
    ground with no relief at all.  The replacement contains no DEM term
    whatsoever, so it is IDENTICAL in the plateau and canyon worlds."""
    return cap * gs_mouth_allowance_m()


def gs_pin_law_ceiling(host_datum: float, route_len_m: float,
                       cap: float) -> float:
    """THE groundside mouth ceiling, from a LAW datum only.

    ``host_datum`` — the SOLVED elevation of the pavement the mouth welds
    toward (the apron at the deep end of the truck route, or the
    connector's own apron-ward mouth when no centerline serves it).  A
    solver variable, never a DEM sample.
    ``route_len_m`` — the truck-route length the reach law budgets over.
    ``cap`` — the governing (service-road) grade cap.

    ``host_datum + cap · (route_len + MOUTH_ALLOWANCE_M)`` — the reach law
    from the weld datum, plus exactly one throat of reach
    (:func:`gs_pin_float_cap`) because the weld point is not the datum
    point.  This is the LAW's own statement of how high the mouth may sit
    and contains no terrain term, so:

    CONSTANT-DEM ORACLE, BY INSPECTION.  Every input is either a solved
    pavement variable or a law constant.  With DEM ≡ 1 m and with
    DEM ≡ 10 000 m the ceiling is computed by the same expression from the
    same law, so it cannot differ between the two worlds by anything the
    DEM did; it can only move with the host pavement the airside solve
    placed.  It therefore never clamps a lawful mouth in either world, and
    the seat inside ``[base − cap·route_len, base + cap·route_len]``
    lands on the interval end nearest the seed — the FLOOR in the plateau
    world, the CEILING in the canyon world, which is the ADDENDUM's
    extreme-seating assertion."""
    return float(host_datum) + float(cap) * (
        float(route_len_m) + gs_mouth_allowance_m())


def gs_witness_horizon(cap: float) -> float:
    """The witness clause's ROLE bound: how far a groundside pin's envelope
    label may travel, in metres of BUDGET distance (the reach-envelope
    Dijkstra's own metric, ``Σ cap_e · len_e``).  Numerically the same scalar
    as :func:`gs_pin_float_cap` — one throat of reach at cap — because a
    label that has spent ``cap · MOUTH_ALLOWANCE_M`` of budget has left the
    mouth zone by exactly the distance Part C allows the mouth to float."""
    return gs_pin_float_cap(cap)

# ── Parallel-road station coupling (part 30m OPEN item (a), DEFAULT OFF) ──
# The queued fix for the "two NON-touching parallel service roads seat a
# metre-scale wall across the gap" defect (#576↔#584): widen the spine-station
# merge past its 2 m sliver window (the O4_SVC_PROXIMITY_COUPLE analogue, which
# misses a several-metre gap) so a near-parallel pair a few metres apart shares
# ONE DEM seed + ONE reach-band intersection — a single-valued cross-section the
# wall cannot be seeded on.  A TANGENT guard (|cos∠(tangent_a, tangent_b)| above
# the threshold — antiparallel loop returns count, a crossing road ≈90° never
# does) keeps it to genuine parallel pairs.
#
# SHIPPED OFF (measured 2026-07-08).  The documented #576↔#584 site no longer
# exists at HEAD (intervening commits — the off-source SOURCE CLIP and adjacent-
# ground work — reshaped HECA's service net; the equivalent HECA pair is now
# 0.19 m, resolved).  Where this coupling actually FIRES (CYXY -10045↔-10195,
# 6.7 m apart) the two roads differ by ~1.5 m for GENUINE terrain reasons
# (non-overlapping reach bands — the SAME physics part-30m recorded for
# #576↔#584: "each road on its OWN spine regime"); forcing a shared seed there
# REGRESSED CYXY (worst service tear 22.2→23.2 %, facing step 1.523→1.587 m).
# Proximity + parallelism alone cannot tell a "coincidental wall that should be
# flat" from "two roads terrain genuinely holds apart" — they are identical
# geometry — so no guard makes the coupling both effective and non-regressing.
# Kept behind the gate (idiomatic default-off experiment) for a future revisit
# that carries the missing signal (e.g. a shared groundside connection proving
# the pair SHOULD be co-level).  ``O4_SVC_PARALLEL_STATION_MERGE=1`` enables it;
# default (unset / 0) ⇒ byte-identical to the 2 m window.  Standalone tuning
# knobs (not aerodrome standards; anchors.py owns them per the part-32 split).
# BELIEVED-IN STATE: OFF (2026-08-05).  The experiment above never found
# the missing signal, and a gate is no longer how an unbelieved branch is
# carried — this constant is the switch, and it is False.
PARALLEL_SERVICE_STATION_MERGE = False
# Max XY gap between the two lines' stations to couple them (m).
PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M = 7.0
# Near-parallel guard: |cos(angle between the host-line tangents)| must be at
# least this (cos 25° ≈ 0.906) — a crossing road (≈90°, cos≈0) never couples.
PARALLEL_SERVICE_STATION_MERGE_MIN_ABS_COS = 0.906

# The TAXI ROUTE (smoothness target, bounded by the reach band): taxi rects +
# junctions.  A node shared by an apron AND a route shape is a route node.
_ROUTE_ROLES = frozenset({
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
    ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
})
# DEM-FOLLOWING body (closest-to-DEM target, NO taxi-band bound): aprons AND
# service roads/junctions.  A service road is NOT a taxiway — it grades at 4% and
# ties to the ground road network / terrain, so it must NOT be clamped to the
# taxi reach band (which would cap it metres below DEM — user 2026-06-25).
_DEM_BODY_ROLES = frozenset({
    ROLE_APRON, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
})


def _open_ring(coords):
    if coords and coords[0] == coords[-1]:
        return list(coords[:-1])
    return list(coords)


def reach_band_for(layout, elev, bucket_to_idx, dem, tile_lat, tile_lon,
                   unified_graph=None):
    """Build the one reach band, a DEM sampler, and the runway-edge anchors.

    The band is computed on THE unified grade graph the spine solves on
    (``reach_band_unified``) — one graph, no route-graph drift, no
    ceiling-consistency bridge.  ``unified_graph`` is the prebuilt
    ``build_unified_graph`` (the caller already needs it); also returned so the
    solve reuses the same object."""
    from auto_patch.elevation import _sample_dem
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    from auto_patch.elevation_per_surface.solver_primitives import _runway_edge_pts

    runway_pts = _runway_edge_pts(layout, elev, bucket_to_idx)
    G = unified_graph
    # THE BAND OF RECORD (round 17 §R17-1(c), owner ruling 2026-08-11b).
    # This is the solve's own construction — the line the carried
    # ``env_band`` store is minted from — so it is the object every later
    # consumer must read rather than build a second one of.
    from auto_patch.elevation_per_surface.building_feasibility import (
        publish_band_of_record)
    band = publish_band_of_record(layout, reach_band_unified(layout, G))

    def _dem(x, y):
        try:
            lat, lon = layout.m_to_ll(x, y)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except Exception:                                     # pragma: no cover
            return None

    return band, _dem, runway_pts, G


def _seat_node_band(ring, band, cps, bucket_to_idx):
    """The NODE-BAND interval at a pad's CONTACT NODES — the intersection of
    ``band(x, y)`` over exactly those ring vertices that are registered solve
    nodes (``bucket_to_idx``), i.e. the nodes the seat is actually stamped on
    and that ``node_bands`` later clamps.

    Read-only on the canonical registry (``cps.get``, never ``get_or_add``):
    interning a point changes which LATER points intern together and would
    move the emitted surface — this is a measurement, so it uses the
    measurement query (``canonical_points.get`` docstring).

    Returns ``(floor, ceiling, contacts)``; ``contacts == 0`` ⇒ nothing to
    say (off-net pad) and the interval is ``(-inf, +inf)``."""
    nlo, nhi, contacts = -_INF, _INF, 0
    for (x, y) in ring:
        k = cps.get(float(x), float(y))
        if k is None or bucket_to_idx.get(k) is None:
            continue
        nb = band(x, y)
        if nb is None:
            continue
        nlo = max(nlo, nb[0])
        nhi = min(nhi, nb[1])
        contacts += 1
    return nlo, nhi, contacts


# ── PAD BINDING ROUTES (spec ``docs/specs/pad-binding-routes-spec.md``) ──
# PUBLICATION ONLY.  Everything below reads the band the seat consumed and
# the provenance THAT band recorded; nothing is re-derived, no field is
# rebuilt, no law is changed.  The one production consumer is
# :func:`build_building_seats`, which captures beside its existing
# ``_frontage_band_records`` block — ONE capture, N consumers.


def _pad_binding_route_context(layout, band, G, report):
    """``(provenance, nodespace, reason)`` for the binding-route capture —
    ``(None, None, "degraded"|"foreign")`` when it cannot lawfully run
    (spec §1.6).  The REASON is returned so the pad-variable domain
    publication can share THIS verdict instead of computing a second one
    (pads-as-band-variables Amendment 1 §3): "foreign" suppresses domains
    too (a second engine's answer); "degraded" suppresses only routes
    (node ids do not exist), because domains are metric intervals from
    the band the seats actually consumed.

    THREE degraded contexts, all answered the same way and all
    distinguishable by a reader (``nodespace: null`` = "capture could not
    run", which is not "ran, no pads" and not "patch predates the key"):
    no unified graph was handed in (every test caller), a band with no
    ``attachment_at`` accessor (hand-made bands), or a layout carrying no
    ``_band_anchor_provenance`` (nothing recorded a field).

    THE PASS-IDENTITY GUARD (spec §1.2).  Node ids are valid only inside
    the ``_build_node_list`` call that assigned them, and
    ``_band_anchor_provenance`` is write-only/last-call-wins — so routes
    are published ONLY when the band in hand IS this layout's band of
    record.  A mismatch is reported LOUD and publishes nothing; it never
    raises, because evidence must not kill a build the law would accept.
    """
    from auto_patch.elevation_per_surface.building_feasibility import (
        band_of_record)
    if G is None or getattr(band, "attachment_at", None) is None:
        return None, None, "degraded"
    prov = getattr(layout, "_band_anchor_provenance", None) or {}
    if not prov:
        return None, None, "degraded"
    if band is not band_of_record(layout):
        report("  [pad-routes] NOT publishing binding routes: the band the "
               "seats are reading is NOT this layout's band of record, so "
               "its node ids may belong to a foreign node space — a route "
               "published from one would be a second engine's answer. "
               "pad_binding_routes = {nodespace: null, records: []}")
        return None, None, "foreign"
    return prov, "n=%d" % len(getattr(G, "pos", None) or ()), "ok"


def _pad_binding_route_record(layout, G, prov, ref, level, recs):
    """ONE pad's published binding routes (spec §1.3 / §1.4).

    ``recs`` are this pad's ``_frontage_band_records`` — the SAME frontage
    points the seat interval was intersected over, so the route published
    is the one the seat was actually clamped by.

    THE BINDING NODE RULE, stated once and shared with
    ``tools/trace_reach_route.py``'s ``_binding_route`` so the two can
    never drift: the band takes the MIN ceiling over the route nodes
    seeding a cell, so the ceiling-binding attachment node is the argmin
    of ``anchor_value[anchor] + budget`` over the frontage point's
    attachment nodes (ties → lowest node id); the floor mirrors with the
    argmax of ``anchor_value[anchor] − budget``.  Per side the frontage
    point published is the one that BINDS the pad's box — the minimum
    ceiling / maximum floor among the pad's apron-shared edge centres.
    One route per side per pad: bounded, and the route the question is
    about.
    """
    from auto_patch.elevation_per_surface.building_feasibility import (
        walk_to_anchor)
    anchor_value = prov.get("anchor_value") or {}
    pos = getattr(G, "pos", None) or {}
    sides: dict = {}
    for side in ("ceiling", "floor"):
        prov_side = prov.get(side) or {}
        if not prov_side or not recs:
            continue
        fr = (min(recs, key=lambda r: r["ceiling"]) if side == "ceiling"
              else max(recs, key=lambda r: r["floor"]))
        cands = [int(n) for n in (fr.get("anchor_nodes") or ())
                 if int(n) in prov_side]
        if not cands:
            continue

        def _value_at(n, _side=side, _ps=prov_side):
            a, budget = _ps[n]
            v = float(anchor_value.get(int(a), 0.0))
            b = float(budget)
            return v + b if _side == "ceiling" else v - b

        node = min(cands, key=lambda n: ((_value_at(n), n) if side == "ceiling"
                                         else (-_value_at(n), n)))
        anchor = int(prov_side[node][0])
        budget = float(prov_side[node][1])
        path, complete = walk_to_anchor(G, prov_side, node, anchor)
        route_ll: list = []
        plan_len = 0.0
        prev = None
        for n in path:
            p = pos.get(int(n))
            if p is None:
                continue
            if prev is not None:
                plan_len += math.hypot(p[0] - prev[0], p[1] - prev[1])
            prev = p
            la, lo = layout.m_to_ll(float(p[0]), float(p[1]))
            route_ll.append([round(float(la), 7), round(float(lo), 7)])
        ap = pos.get(anchor)
        sides[side] = {
            "anchor_node": anchor,
            "anchor_ll": (None if ap is None else
                          [round(float(v), 7) for v in
                           layout.m_to_ll(float(ap[0]), float(ap[1]))]),
            "anchor_value_m": float(anchor_value.get(anchor, 0.0)),
            "route_budget_m": budget,
            "plan_len_m": float(plan_len),
            "route_complete": bool(complete),
            "route_ll": route_ll,
            "frontage_ll": [round(float(v), 7) for v in (fr.get("ll") or ())],
            "band_floor_m": float(fr["floor"]),
            "band_ceiling_m": float(fr["ceiling"]),
        }
    if not sides:
        # AN ANSWER, not a refusal (the tool's own doctrine): a pad whose
        # frontage the band does not serve — or whose attachment carries no
        # provenance-known node — is governed by the within-shape law, and
        # that is what ``off_network`` says.
        return {"pad": ref, "seat_m": float(level), "off_network": True}
    return {"pad": ref, "seat_m": float(level), "off_network": False,
            "sides": sides}


def _report(line):
    """One line out of a seat-law attribution, on the production channel.

    ``O4_UI_Utils`` is the GUI↔core contract and is what a production build
    reads; a standalone/probe build has no such module, and an attribution
    that disappears there would be exactly the silence these reports exist
    to remove — so it falls back to ``print``."""
    try:
        import O4_UI_Utils as _UI
        _UI.vprint(1, line)
    except Exception:                                    # pragma: no cover
        print(line)


# ── ROUTE-DISTANCE SEAT COUPLING (spec
# ``docs/specs/route-distance-seat-coupling-spec.md``) ────────────────────
# The owner dial for pair admission.  It stays a DISTANCE and mirrors
# ``config.BUILDING_REACH_CORRIDOR_M`` — the spec's "provisional 200 m to
# preserve today's reach intent" — and is converted ONCE, at the apron cap,
# into the metric the projection actually enforces (see
# :func:`route_coupling_horizon_m`).
ROUTE_COUPLING_MAX_DIST_M: float | None = None      # None ⇒ the corridor

# ── THE COUPLER IS ROUTE-PRICED — STANDING LAW ───────────────────────────
# (spec ``docs/specs/route-distance-seat-coupling-spec.md``; formerly gates
# ``O4_SEAT_COUPLE_ROUTE_METRIC`` + ``O4_SEAT_COUPLE_SHARED_SURFACE``, both
# retired 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG".)
#
# THE LAW.  The seat coupler admits and prices pairs on the WITHIN-SHAPE
# LAW GRAPH the projection enforces, never on a straight chord: a pair's
# budget is the per-edge budget sum along the minimum-budget path, priced
# exactly as ``feasibility_project`` prices its edges.  There is ONE
# metric.  The chord corridor cutoff and the pavement-visibility fraction
# are RETIRED as admission predicates — the chord is still MEASURED, purely
# as the census that makes each pair's tightening adjudicable.
#
# THE DEFECT IT CLOSES (dossier §2, HEAZ).  Pads building4↔building5 are
# 17.6 m apart by chord (limit 0.176 m) but bound by the 2-hop chain
# ``35 —0.0578— 1295 —0.1015— 37``: the REAL budget is 0.1593 m, and the
# pair stalled 8 000 sweeps.  The visibility fraction is a FALSE-NEGATIVE
# pair predicate on top of that — those two pads' ring nodes sit on ONE
# apron ring and the projection enforces the chain between them regardless,
# yet the coupler rejected the pair as "separated by grass" at frac=0.057.
# Two instruments over one population: the coupler's adjacency was a
# visible straight chord, the projection's is the within-shape law graph.
# ``O4_SEAT_COUPLE_SHARED_SURFACE`` is SUBSUMED, not merged: ring-sharing
# pads have a through-surface path, so route admission already offers every
# pair that predicate was invented to rescue (measured: byte-identical
# route arms with and without it at CYXY and HEAZ).
#
# MEASURED SURFACE COST IN THE OLD (GATED, PRE-COMPOSED) WORLD: KCLT +121
# law-true ``within`` at the 2026-08-04 tip, breadth not depth — the
# corridor faces around the 63-of-69 pads that moved could not grade to
# their new law-true joint levels.  That number was taken against a
# chord-priced surface that no longer exists; it is a DEBUG-PHASE target,
# not a reason to keep two metrics.  Full arm table: coupling/RESULTS.md.


def route_coupling_horizon_m() -> tuple:
    """``(budget_horizon_m, dial_distance_m)`` for pair admission.

    UNIT NOTE (declared, never silent).  The dial is a DISTANCE — today's
    ``BUILDING_REACH_CORRIDOR_M`` — and admission is tested in the BUDGET
    metric at the apron cap, so the gate is exactly today's rule with route
    distance substituted for chord distance under the same cap
    (``gap ≤ 200 m`` ⇔ ``APRON_MAX_GRADE·gap ≤ 2.0 m``).  Testing
    reachability in metres of LENGTH instead would re-introduce a second
    metric the projection does not enforce, and would reject pairs whose
    budget genuinely binds: a minimum-BUDGET route may take a long detour
    over cheap pavement, and it is that route the law walks."""
    from auto_patch.config import APRON_MAX_GRADE, BUILDING_REACH_CORRIDOR_M
    dial = ROUTE_COUPLING_MAX_DIST_M
    if dial is None:
        dial = float(BUILDING_REACH_CORRIDOR_M)
    return float(APRON_MAX_GRADE) * float(dial), float(dial)


def _pad_route_budgets(law_graph, pad_nodes, n_nodes=None):
    """``(budgets, diag)`` — the min-budget route between every pair of pads
    on the graph ``feasibility_project`` enforces.

    ``law_graph`` — the solve's own ``shape_constraints`` list (the object
    handed to the projection, never a re-derivation).  ``pad_nodes`` — one
    node-index set per pad, in the coupler's pad order.

    THE PRICING IS THE PROJECTION'S OWN, clause for clause
    (``one_solve._build_adjacency``):

      * SYMMETRIC 3-tuple edges only.  An INTERVAL 4-tuple is a one-sided
        slab (adjacent-ground zone, RESA cut) and has no symmetric route
        price; routing a pad↔pad chord through terrain would also
        contradict ``reach-follows-centerlines`` (RULINGS 2026-07-30).
      * ``lim is None`` / negative = unregulated ⇒ dropped; ``i >= n`` when
        the caller states ``n_nodes`` ⇒ dropped.
      * FLAT-GROUP CONTRACTION: each pad collapses to one representative
        (``rep = min(group)``, overlapping groups merged first — two
        touching pads sharing a ring vertex are ONE rigid unit), exactly
        the collapse the projection performs on ``flat_groups``.
      * TIGHTEST-BUDGET-WINS per canonical pair after the remap.
      * the per-edge budget is the RAW law budget — exactly what the
        projection sweeps.  The emit-quantization margin that used to
        split these into two frames is RETIRED (docs/RULINGS.md
        2026-08-05; see the ``one_solve`` module head): there is one law
        frame, so the coupler and the projection agree by construction
        rather than by keeping a subtraction in sync.  The dossier's
        certificate (0.0578 over 6.78 m, 0.1015 over 11.15 m, budget
        0.1593) is that frame.

    The Dijkstra itself is NOT written here: it is
    ``law_graph_budget.build_anchor_envelope``, the seed-fix round's oracle,
    seeded ``{rep_i: 0.0}`` so its ``ceil_route_m[rep_j]`` IS ``d(i, j)``
    (``single-pass-principle`` — one metric, built once, consumed twice).

    ``diag`` carries the census the round reports: pair counts, the
    certified-lazy entry count (those contribute ring edges only — the
    approximation is declared, not hidden), and the BUDGET-IDENTITY
    measurement (§4): every pair is priced from BOTH endpoints and the
    disagreement reported; >1 % is the spec's STOP."""
    from .law_graph_budget import build_anchor_envelope

    # ── STAGE A PRICES THROUGH AIRSIDE SURFACES ONLY (S1c, coupling 20)
    # Building pads are airside.  Under ``SVC_SPINE_FIRST`` the
    # within-shape law graph carries SERVICE_ROAD edges at
    # ``SERVICE_ROAD_MAX_GRADE``, so a pad↔pad pair could be priced
    # THROUGH a groundside surface — a groundside cap authoring an
    # airside seat coupling, which "airside is king" forbids and which
    # the chord-era coupler could not even express.  The stage tag every
    # entry now carries (S1b) makes the restriction exact: stage-A
    # entries only, which is the same law graph minus the groundside
    # surfaces.  Entries are the SOLVE'S OWN objects, still never
    # re-derived; an untagged one raises rather than being priced.
    from auto_patch.solve_stage import (STAGE_A as _ST_A,
                                        STAGE_KEY as _ST_K,
                                        assert_tagged as _assert_tagged)
    if law_graph:
        _assert_tagged(law_graph, "_pad_route_budgets")
        law_graph = [sc for sc in law_graph if sc[_ST_K] == _ST_A]

    horizon, dial = route_coupling_horizon_m()
    # ── flat-group contraction (mirrors one_solve's merge exactly) ──────
    merged: list = []
    owner: list = []                      # pad index -> merged-group index
    for g in pad_nodes:
        g = set(g)
        hit = None
        for mi, mg in enumerate(merged):
            if mg & g:
                mg |= g
                hit = mi
                break
        if hit is None:
            merged.append(set(g))
            hit = len(merged) - 1
        owner.append(hit)
    gmap: dict = {}
    rep_of_group: list = []
    for mg in merged:
        if not mg:
            rep_of_group.append(None)
            continue
        rep = min(mg)
        rep_of_group.append(rep)
        for m in mg:
            gmap[m] = rep
    rep_of_pad = [rep_of_group[owner[k]] for k in range(len(pad_nodes))]

    # ── the projection's edge set, deduped, at RAW law budgets ──────────
    edge_lim: dict = {}
    lazy_entries = 0
    interval_edges = 0
    for sc in law_graph:
        if sc.get("lazy_expand") is not None:
            lazy_entries += 1
        for edge in sc["edges"]:
            if len(edge) >= 4:
                interval_edges += 1
                continue
            i, j, lim = edge
            if lim is None or lim < 0:
                continue
            if n_nodes is not None and (i >= n_nodes or j >= n_nodes):
                continue
            i = gmap.get(i, i)
            j = gmap.get(j, j)
            if i == j:
                continue
            e = (i, j) if i < j else (j, i)
            prev = edge_lim.get(e)
            if prev is None or lim < prev:
                edge_lim[e] = lim
    # ONE FRAME.  The margin that once split this into an enforced
    # (margined) graph and a report-only RAW twin is retired, so the
    # second Dijkstra field is DELETED rather than recomputed to the same
    # answer (single-pass-principle).  ``diag["raw_budgets"]`` is still
    # published — it is now literally the law route price.
    adj: dict = {}
    for (i, j), lim in edge_lim.items():
        adj.setdefault(i, []).append((j, lim))
        adj.setdefault(j, []).append((i, lim))

    # ── one oracle field per pad; the pair budget is read off it ────────
    fields: dict = {}
    for rep in rep_of_pad:
        if rep is None or rep in fields or rep not in adj:
            continue
        fields[rep] = build_anchor_envelope(adj, {rep: 0.0},
                                            horizon_m=horizon)
    budgets: dict = {}
    raw_budgets: dict = {}
    merged_pairs = 0
    ident_worst = 0.0
    ident_worst_pair = None
    ident_over = []
    unreachable = 0
    off_graph = 0
    for a in range(len(pad_nodes)):
        ra = rep_of_pad[a]
        for b in range(a + 1, len(pad_nodes)):
            rb = rep_of_pad[b]
            if ra is None or rb is None:
                off_graph += 1
                continue
            if ra == rb:
                # MERGED RIGID UNIT.  Two pads sharing a ring vertex are ONE
                # flat group in the projection, and the merge is transitive —
                # a chain of touching buildings is a single rigid body that
                # the projection seats at ONE level (it broadcasts the
                # group's mean).  Their coupling budget is 0 by law, at any
                # separation: a chord-priced coupler that let them differ was
                # choosing levels the projection would overwrite.
                budgets[(a, b)] = 0.0
                merged_pairs += 1
                continue
            fa, fb = fields.get(ra), fields.get(rb)
            dab = None if fa is None else fa.ceil_route_m.get(rb)
            dba = None if fb is None else fb.ceil_route_m.get(ra)
            if dab is None and dba is None:
                if ra not in adj or rb not in adj:
                    off_graph += 1
                else:
                    unreachable += 1
                continue
            # ── §4 BUDGET IDENTITY: the same pair priced from both ends.
            if dab is not None and dba is not None:
                scale = max(abs(dab), abs(dba), 1e-9)
                rel = abs(dab - dba) / scale
                if rel > ident_worst:
                    ident_worst, ident_worst_pair = rel, (a, b)
                if rel > 0.01:
                    ident_over.append((a, b, dab, dba))
            d = min(x for x in (dab, dba) if x is not None)
            budgets[(a, b)] = float(d)
            # ONE FRAME: the route price IS the raw law price.
            raw_budgets[(a, b)] = float(d)
    diag = {"horizon_m": horizon, "dial_m": dial,
            "raw_budgets": raw_budgets, "merged_pairs": merged_pairs,
            "merged_groups": sum(1 for gi in set(owner)
                                 if owner.count(gi) > 1),
            "merged_pads": sum(1 for gi in owner if owner.count(gi) > 1),
            "pairs": len(budgets), "unreachable": unreachable,
            "off_graph": off_graph, "lazy_entries": lazy_entries,
            "interval_edges": interval_edges, "graph_nodes": len(adj),
            "graph_edges": len(edge_lim),
            "ident_worst": ident_worst, "ident_worst_pair": ident_worst_pair,
            "ident_over": ident_over}
    return budgets, diag


def _merge_rigid_units(pads, cps):
    """MERGED RIGID UNITS (owner law) — collapse ``pads`` into the flat
    groups the projection will enforce, TRANSITIVELY.

    ``pads`` — the coupler's ``(shape, ring, level, lo, hi)`` rows.
    Returns ``(units, unit_of, rows)``:

      * ``units`` — one dict per rigid unit, in ascending order of its
        lowest member index (deterministic): ``members`` (pad indices),
        ``refs``, ``ref`` (the report label), ``polygon`` (the union of the
        member footprints), ``level``, ``lo``, ``hi``;
      * ``unit_of[pad_index]`` — the unit that pad belongs to;
      * ``rows`` — one report row per MULTI-member unit (single pads are
        not news).

    THE RELATION is "shares a ring vertex", read through the CANONICAL
    REGISTRY (``cps.get_or_add``) — the same interning ``build_building_seats``
    uses to stamp seats and the same one ``bucket_to_idx`` is keyed on, so
    two ring vertices that weld to one canonical point count as shared even
    when their raw coordinates differ.  That makes this relation identical
    to the node-set overlap ``_pad_route_budgets`` contracts on for every
    pad whose ring vertices are registered solve nodes, and STRICTLY WIDER
    for pads that touch only at an OFF-NET vertex — which is the owner's
    law as stated ("pads sharing a ring vertex"), not the projection's
    node-graph accident.

    THE UNIT'S BOX is the INTERSECTION of its members' boxes: a rigid body
    may not yield outside a level any member's own frontage can reach.  An
    EMPTY intersection is a genuine law defect (``feasibility-is-guaranteed``
    — two touching pads whose reachable levels do not overlap), so it is
    REPORTED and the unit degenerates to the most-constrained CEILING: the
    lowest member ceiling is the highest level every member's frontage can
    actually grade to, and seating above it is unreachable by construction.

    THE UNIT'S TARGET is the AREA-WEIGHTED mean of its members' independent
    targets, clamped into the unit box.  The projection broadcasts an
    unweighted mean over NODES (i.e. perimeter-weighted); area weighting is
    the deliberate deviation — a shed welded to a terminal must not drag
    the terminal's level — and it is the value the projection then finds
    already satisfied instead of minting one.
    """
    n = len(pads)
    parent = list(range(n))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:                       # smallest index wins -> stable
            parent[max(ra, rb)] = min(ra, rb)

    owner_of_key: dict = {}
    for k, (_s, ring, *_r) in enumerate(pads):
        for (x, y) in ring:
            key = cps.get_or_add(float(x), float(y))
            prev = owner_of_key.get(key)
            if prev is None:
                owner_of_key[key] = k
            elif prev != k:
                _union(prev, k)

    groups: dict = {}
    for k in range(n):
        groups.setdefault(_find(k), []).append(k)

    units: list = []
    unit_of = [0] * n
    rows: list = []
    for root in sorted(groups):
        members = groups[root]
        for k in members:
            unit_of[k] = len(units)
        if len(members) == 1:
            (s, _ring, level, lo, hi) = pads[members[0]]
            units.append({"members": members,
                          "refs": [s.ref or "?"],
                          "ref": s.ref or "?",
                          "polygon": s.polygon,
                          "level": float(level),
                          "lo": float(lo), "hi": float(hi)})
            continue
        refs = [pads[k][0].ref or "?" for k in members]
        lo = max(float(pads[k][3]) for k in members)
        hi = min(float(pads[k][4]) for k in members)
        empty = lo > hi
        if empty:
            hi = min(float(pads[k][4]) for k in members)
            lo = hi
        wsum = 0.0
        vsum = 0.0
        for k in members:
            w = float(pads[k][0].polygon.area) if pads[k][0].polygon else 0.0
            w = max(w, 1e-9)
            wsum += w
            vsum += w * float(pads[k][2])
        level = min(max(vsum / wsum, lo), hi)
        # The unit's footprint is the UNION of its members — but only when
        # that union is a single Polygon: every consumer here
        # (``polygon.distance``, ``_footprint_dem_relief``) reads
        # ``.exterior``, and pads that touch at a single point can union to
        # a MultiPolygon.  Fall back to the LARGEST member, which is the
        # footprint whose relief the split-level law would threshold on.
        poly = max((pads[k][0].polygon for k in members
                    if pads[k][0].polygon is not None),
                   key=lambda g: g.area, default=None)
        try:
            from shapely.ops import unary_union
            u = unary_union([pads[k][0].polygon for k in members
                             if pads[k][0].polygon is not None])
            if (u is not None and not u.is_empty
                    and getattr(u, "geom_type", "") == "Polygon"):
                poly = u
        except Exception:                            # pragma: no cover
            pass
        units.append({"members": members, "refs": refs,
                      "ref": "{" + "+".join(refs[:3])
                             + ("+…" if len(refs) > 3 else "") + "}",
                      "polygon": poly, "level": float(level),
                      "lo": float(lo), "hi": float(hi)})
        rows.append({"members": members, "refs": refs, "level": float(level),
                     "lo": float(lo), "hi": float(hi), "empty": bool(empty)})
    return units, unit_of, rows


def _apply_authored_datum_groups(layout, units, pairs, enabled,
                                 solve_pack_groups):
    """§1.3 — tie the units of each AUTHORED-DATUM group into ONE variable,
    accommodate if lawful, SPLIT if not.  Returns the ledger rows.

    THE DECLARATION.  ``layout._authored_datum_groups`` — a list of
    ``{"key": str, "members": [pad ref, ...], "offsets": {ref: metres}}``
    published by whichever pass KNOWS the pack's authoring (identity is
    declared by the pass that has it; a proximity or equal-value join
    would be exactly the identity guess ``canonical-identity-join``
    forbids).  Absent ⇒ no group, and the ledger's honest answer is "every
    authored-datum pack group ACCOMMODATED", because none reached here.

    THE UNIT IS THE VARIABLE, not the pad: pads sharing a ring vertex are
    already ONE flat body (the merged-rigid-unit law), so a group whose
    members land in one unit is already one value and cannot shear.  A
    group is therefore priced over the UNITS its member pads belong to.

    ``over_cap`` is the ruling's second trigger, priced on the SAME pair
    budgets the projection enforces: a candidate assignment that leaves a
    coupled pair over its limit — or a unit outside its own domain — is
    not "the best available", it is a SPLIT.
    """
    if not enabled or not units:
        return [], 0
    decl = list(getattr(layout, "_authored_datum_groups", None) or ())
    if not decl:
        return [], 0
    unit_of_ref: dict = {}
    for k, u in enumerate(units):
        for r in u.get("refs") or ():
            unit_of_ref.setdefault(str(r), k)
    domains = {k: (float(u["lo"]), float(u["hi"]))
               for k, u in enumerate(units)}
    targets = {k: float(u["level"]) for k, u in enumerate(units)}
    weights = {k: float(getattr(u.get("polygon"), "area", 0.0) or 0.0)
               for k, u in enumerate(units)}
    polygons = {k: u.get("polygon") for k, u in enumerate(units)}

    def _over_cap(assignment):
        rows = []
        for (i, lvl) in assignment.items():
            d = domains.get(i)
            if d is None:
                continue
            if lvl < d[0] - 0.01 or lvl > d[1] + 0.01:
                rows.append({"why": "member_outside_own_domain",
                             "unit": units[i]["ref"], "level": float(lvl),
                             "domain": [d[0], d[1]],
                             "deficit_m": round(max(d[0] - lvl, lvl - d[1]),
                                                6)})
        for ((a, b), lim) in (pairs or {}).items():
            va = assignment.get(a, targets.get(a))
            vb = assignment.get(b, targets.get(b))
            if va is None or vb is None:
                continue
            ex = abs(float(va) - float(vb)) - float(lim)
            if ex > 0.01:
                rows.append({"why": "coupled_pair_over_cap",
                             "units": [units[a]["ref"], units[b]["ref"]],
                             "limit_m": float(lim),
                             "excess_m": round(float(ex), 6)})
        return rows

    groups = []
    offsets: dict = {}
    for g in decl:
        members: list = []
        for r in (g.get("members") or ()):
            k = unit_of_ref.get(str(r))
            if k is None or k in members:
                continue
            members.append(k)
            offsets[k] = float((g.get("offsets") or {}).get(str(r), 0.0))
        if members:
            groups.append({"key": str(g.get("key") or "?"),
                           "members": members})
    if not groups:
        return [], 0
    out = solve_pack_groups(groups, domains, targets, offsets=offsets,
                            weights=weights, polygons=polygons,
                            over_cap=_over_cap)
    for (k, lvl) in out.values.items():
        units[k]["level"] = float(lvl)
        # THE GROUP VALUE IS PLACED, so the coupling that follows may not
        # shear it: the unit's box collapses to the value.  (A group that
        # SPLIT has already been re-solved piece by piece in each piece's
        # own domain, so this pins the split result, not the torn one.)
        units[k]["lo"] = units[k]["hi"] = float(lvl)
    # The ledger rows name UNIT labels; re-spell them as the pad refs the
    # owner reviews (a split shears authored geometry and the review is
    # per object, not per solver variable).
    for row in out.rows:
        row["members"] = [units[int(m)]["ref"] for m in row["members"]]
        row["pieces"] = [[units[int(m)]["ref"] for m in p]
                         for p in row["pieces"]]
    return out.rows, len(groups)


def build_building_seats(layout, bucket_to_idx, band, dem_fn, runway_pts,
                         *, law_graph=None, n_nodes=None, unified_graph=None):
    """``{pad_node_idx: flat_level}`` for every airside-touching building, seated
    at the level its FRONTAGE can reach (the band intersected over the pad ring)
    closest to DEM.

    ``law_graph`` / ``n_nodes`` — the solve's own ``shape_constraints`` and
    node count, consumed ONLY by the route-distance coupling gate
    (:func:`seat_couple_route_metric_enabled`).  Absent, the gate cannot
    price on the law graph and says so rather than pricing on a chord in
    silence.

    ``unified_graph`` — THE graph ``band`` was built on
    (``reach_band_for``'s fourth return value).  Consumed ONLY by the pad
    BINDING-ROUTE publication (spec
    ``docs/specs/pad-binding-routes-spec.md`` §1.2): with it the seat pass
    publishes, per pad, the recorded route that bound the seat; without it
    the capture publishes the degraded ``{"nodespace": null, "records":
    []}`` and nothing else changes.  Evidence, never law input."""
    import os as _os
    from auto_patch.layout import ROLE_APRON
    from auto_patch.elevation_per_surface.building_feasibility import (
        building_feasible_levels)

    cps = layout.canonical_points
    # BOUNDED YIELD box registry (owner ruling 2026-07-29: "Any yield
    # absolutely needs to stay within the feasibility box"): whatever seats
    # a node also records the reach-band interval the seat was chosen from,
    # keyed by CANONICAL KEY (the ``canonical_points`` registry point) —
    # never by node index: the final projection runs on a REBUILT node
    # list (the rod-key lesson), so only the key survives.  Lives in the
    # NODE-SPACE STORE (U1, ``node_space.py``): consumers (solve.py fp#8 +
    # final_grade_projection) resolve it through ``view_interval`` into
    # their own index space and clamp every freed value inside its box.
    # Reset here — this is the first seat producer of a solve;
    # ``build_nobuilding_apron_seats`` merges its contact boxes into the
    # same payload afterwards.
    _store_of(layout).open_map("seat_boxes", "interval", reset=True)
    # ``building_feasible_levels`` decides WHICH buildings are airside-served (its
    # touch test) + gives the centroid level as a fallback for off-network pads.
    levels = building_feasible_levels(layout, runway_pts, dem_fn, band=band)

    # FRONTAGE-EDGE seat (user 2026-06-27): seat the flat pad at the feasible level
    # reachable at the CENTRE of its FRONTAGE edge — the apron-shared building edge
    # facing the MOST-CONSTRAINED taxi route (the lowest band ceiling among the
    # apron-shared edges).  The straight route from that centre to the binding
    # taxiway IS what ``band`` measures, so the apron can grade ≤1 % from the
    # frontage down to the taxiway and the far frontages descend to the pad.  This
    # supersedes the whole-ring MEDIAN, which over-pinned the low (route-limited)
    # frontage corner by averaging in the far high corners — CYXY building15 was
    # seated 709.4 (median over 707.6..712.5) while its A2 frontage centre reaches
    # only 708.4, pinning the A2-end apron 1.8 m high → the 20 % apron cliff.
    # STANDING LAW (owner 2026-06-27; former gate O4_BUILDING_FRONTAGE_SEAT
    # retired 2026-08-05): the whole-ring MEDIAN fallback survives only for
    # a pad with NO apron-shared edge, where there is no frontage to read.
    # ── SEAT-vs-BAND CONSISTENCY — STANDING LAW ─────────────────────────
    # (spec dossier-fixes §2; former gate ``O4_SEAT_BAND_CONSISTENT``,
    # retired 2026-08-05.)
    # Two band instruments over one population: a large pad's seat is
    # chosen inside ``_frontage_band`` (a corridor band sampled along the
    # frontage), but the projection bounds the pad's ring nodes by
    # ``node_bands`` = the SAME band sampled PER NODE.  The two disagree:
    # HECA building181 ships seated 105.772 while 2 of its 12 ring nodes
    # have a node-band ceiling of 103.914 — the seat is 1.858 m above a
    # level the band the solve enforces cannot reach, so no surface can
    # honour it anywhere (carrier_attrib/DOSSIER.md §5).
    # Per ``band-lawful-displacement-trumps-DEM`` there is ONE band: the
    # seat clamps into the INTERSECTION of the frontage interval and the
    # node-band interval at its contact nodes.  An EMPTY intersection is
    # not silently resolved — it is the split-level-seat law's trigger
    # (RULINGS 2026-08-04) and is reported, with today's value kept.
    # Measured when it flipped ON (2026-08-04): HECA 9 952 → 9 649 law-true
    # within (−303; ``building|building`` 440→393 AND the surrounding
    # ``apron`` 6822→6665 / ``junction`` 1856→1781 follow it down), every
    # other battery airport byte-identical.
    # ── PADS AS BAND-BOUNDED VARIABLES (spec §1.1/§1.2) ─────────────────
    # Read at CALL time, once per solve — the harness arms the flag per
    # build.  OFF ⇒ every branch below is inert and this function is
    # byte-identical to the pre-ruling pass (spec §1.5).
    from auto_patch.pad_variables import (
        PAD_LAW_TOL_M, clamp_into, domain_empty, format_pack_group_splits,
        pads_band_variables_enabled, publish_pack_group_splits,
        publish_pad_variable_provenance, record_pad_domain_contradiction,
        refuse_on_empty_pad_domains, ring_domain_detail, solve_pack_groups)
    _PBV = pads_band_variables_enabled()
    _pv_domains: list = []      # index-aligned with ``pads``; None = legacy
    _pv_empty: list = []        # pads whose DOMAIN is empty (§1.4)
    _pv_offnet = 0
    _sb_moved: list = []
    _sb_empty: list = []
    # PAD-SEAT FEASIBILITY GATE (RULINGS 2026-08-24c) — see the check at
    # the foot of the per-pad loop.
    _seat_infeasible: list = []
    # Large buildings (≥ area) seat at the FULL-FRONTAGE feasible level (user
    # 2026-06-27): the entire frontage must grade to the spine ≤1 %, so the seat is
    # the band intersected over the whole frontage (computed by
    # ``building_feasible_levels``), not the single lowest-ceiling frontage edge.
    from auto_patch.grade_law import building_requires_full_frontage
    apron_keys: set = set()
    # Frontage = a building edge shared with any SOFT pavement ring.
    # Under the route-arc GLOBAL SLICE the face a building fronts onto is
    # usually ROLE_JUNCTION (a corridor face), not ROLE_APRON — apron-only
    # keys silently dropped every such frontage back to the legacy
    # whole-ring MEDIAN seat, re-creating the over-pinned frontage
    # conflicts the frontage seat was built to fix (CYXY pads seated
    # 1-2 m apart at close quarters).
    #
    # R7b (owner ruling 2026-08-15, the sink ruling): ``service_junction``
    # LEFT this set.  "A road NEVER welds to a building (a building pad
    # datum is legitimate for its own footprint and must not propagate
    # into the road network)" — and this recognition is precisely what
    # made a road a building's frontage, seating the pad ON the road's
    # band and the road on the pad's.  It is the third of the three
    # pad→road channels the CYXY lot-377 sink ran through (the others are
    # ``groundside.law_anchor_values`` and
    # ``config.NEAR_MISS_FRONTAGE_SOFT_ROLES``).  AIRSIDE frontage —
    # ``apron`` and ``junction`` — is untouched: a building fronting
    # aircraft pavement keeps its own standing ruling (2026-08-08), and
    # the corridor-face reason this set was widened in the first place
    # (the global slice roles a fronted face ``junction``) is airside and
    # still here.  A building that fronts ONLY a road now falls back to
    # the whole-ring band seat — its own footprint, which is the ruling.
    from auto_patch.layout import ROLE_JUNCTION as _RJ
    for a in layout.shapes:
        if (a.role in (ROLE_APRON, _RJ) and a.polygon is not None
                and not a.polygon.is_empty):
            for (x, y) in _open_ring(list(a.polygon.exterior.coords)):
                apron_keys.add((round(x, 2), round(y, 2)))

    def _median(ring, de):
        ceils = sorted(b[1] for (x, y) in ring if (b := band(x, y)) is not None)
        if not ceils:
            return None
        m = len(ceils)
        med = (ceils[m // 2] if m % 2
               else 0.5 * (ceils[m // 2 - 1] + ceils[m // 2]))
        return min(de, med) if de is not None else med

    def _frontage_box(ring):
        """Feasible seat interval from the centres of the building's apron-shared
        edges (both endpoints shared with an apron): ``(max floor, min ceiling)``
        — the ceiling is the most-constrained frontage (the legacy seat rule),
        the floor the highest any frontage must stay above.  None when no edge
        is apron-shared (→ caller falls back)."""
        n = len(ring)
        flo, fhi = None, None
        for i in range(n):
            a = (round(ring[i][0], 2), round(ring[i][1], 2))
            b = (round(ring[(i + 1) % n][0], 2), round(ring[(i + 1) % n][1], 2))
            if a in apron_keys and b in apron_keys:
                cx = 0.5 * (ring[i][0] + ring[(i + 1) % n][0])
                cy = 0.5 * (ring[i][1] + ring[(i + 1) % n][1])
                bc = band(cx, cy)
                if bc is not None:
                    flo = bc[0] if flo is None else max(flo, bc[0])
                    fhi = bc[1] if fhi is None else min(fhi, bc[1])
        if fhi is None:
            return None
        return (min(flo, fhi) if flo is not None else -_INF, fhi)

    def _frontage_band_records(shape, ring):
        """THE BAND, AT THIS PAD'S FRONTAGE POINTS — evidence for the owner
        (lead order 2026-08-24), read from the band the SOLVE is using.

        ``band.attachment_at`` is the raster band's OWN read-only
        provenance accessor: it hands out the lookup that ran rather than
        re-deriving one, which is precisely the "never a replay" clause —
        a tool that re-derives a lookup is a second engine.

        One record per APRON-SHARED edge centre — the same points
        ``_frontage_box`` samples to choose the seat, so the exported
        interval is the one the seat was actually chosen from.
        """
        out = []
        n = len(ring)
        for i in range(n):
            a = (round(ring[i][0], 2), round(ring[i][1], 2))
            b = (round(ring[(i + 1) % n][0], 2), round(ring[(i + 1) % n][1], 2))
            if a not in apron_keys or b not in apron_keys:
                continue
            cx = 0.5 * (ring[i][0] + ring[(i + 1) % n][0])
            cy = 0.5 * (ring[i][1] + ring[(i + 1) % n][1])
            bc = band(cx, cy)
            if bc is None:
                continue
            rec = {"pad": shape.ref or "?",
                   "ll": list(layout.m_to_ll(cx, cy)),
                   "floor": float(min(bc)), "ceiling": float(max(bc))}
            at = getattr(band, "attachment_at", None)
            info = at(cx, cy) if at is not None else None
            if info:
                rec["anchor_nodes"] = [int(v) for v in
                                       (info.get("attachment_nodes") or ())]
                rec["route_m"] = float(info.get("leg_m") or 0.0)
                rec["off_mask_m"] = float(info.get("off_mask_m") or 0.0)
                rec["floor_at_anchor"] = float(info["floor_at_attachment"])
                rec["ceiling_at_anchor"] = float(info["ceiling_at_attachment"])
            out.append(rec)
        return out

    _frontage_band_ll: list = []
    # ── PAD BINDING ROUTES (spec docs/specs/pad-binding-routes-spec.md §1)
    # The route evidence the band ALREADY computed, published at emit time
    # so "show me the calculated route for this pad" is answerable from a
    # patch instead of only from a full in-process rebuild.  Read from the
    # band the seat consumed and the provenance THAT band recorded — never
    # a replay.  ``(None, None)`` = a degraded context (§1.6) or the
    # pass-identity guard refusing; both publish the null-nodespace shape.
    _routes_prov, _routes_ns, _routes_reason = _pad_binding_route_context(
        layout, band, unified_graph, _report)
    _pad_routes: list = []
    # ── PAD-SEAT CONSISTENCY PROVENANCE (spec pad-seat-consistency-spec.md,
    # implementation ruling §2) ─────────────────────────────────────────
    # "Provenance is captured AT SEAT TIME, per PAD UNIT: the governing
    # anchor node(s) + ``route_m`` from ``band.attachment_at`` at the SAME
    # frontage points the seat interval is intersected over
    # (``_frontage_band_records`` already reads exactly this — one capture,
    # two consumers).  Never a replay, never a re-derived lookup."
    # The corridor VALUES those anchors carry do not exist yet (phase A
    # mints them AFTER this function runs), so what is captured here is the
    # provenance only; the intersection binds in the post-phase-A slot
    # (``solve.py``, ``pad_seat_consistency.apply_pad_seat_consistency``).
    # ONE READER for both consumers of this capture (spec
    # ``apron-chord-anchor-target-spec.md`` §2): the frontage-subset
    # narrowing (its own flag, default OFF) and the §2 DEM-LAST SEAT BIAS
    # (its own flag, also default OFF after the 2026-08-25 acceptance
    # miss) both need the unit's node set and its band box,
    # and this is the only place either can get them.  The FRONTAGE
    # records keep being captured beside them and stay unread by §2 —
    # capture is provenance, not law.
    from .pad_seat_consistency import seat_provenance_wanted
    _consist_on = seat_provenance_wanted()
    _pad_prov: list = []            # index-aligned with ``pads`` below

    # ── Per-pad independent target + feasible box ────────────────────────────
    # target = the legacy independent seat (DEM biased into the frontage band);
    # box    = the reach-band interval the seat may move within when the JOINT
    #          projection below reconciles neighbouring pads.
    pads: list = []             # (shape, ring, target_level, lo, hi)
    for s in layout.shapes:
        lv = levels.get(id(s))
        if lv is None or s.polygon is None or s.polygon.is_empty:
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        de = dem_fn(s.polygon.centroid.x, s.polygon.centroid.y)
        if building_requires_full_frontage(s.polygon.area):
            # ``lv`` IS the full-frontage feasible level for a large building;
            # its box is the frontage-band intersection ``lv`` was clamped into.
            from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
            from auto_patch.elevation_per_surface.building_feasibility import (
                _frontage_band, _pavement_visibility)
            from auto_patch.config import VISIBLE_CHORD_CONNECT
            level = float(lv)
            _cls = [cl.line for cl in
                    (getattr(layout, "apt_taxi_centerlines", None) or [])
                    if cl.line is not None and not cl.line.is_empty
                    and not cl.is_service]
            _vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None
            fb = (_frontage_band(s.polygon, band, _cls, _vis,
                                 BUILDING_REACH_CORRIDOR_M) if _cls else None)
            if fb is None:
                fb = band(s.polygon.centroid.x, s.polygon.centroid.y)
            lo, hi = (min(*fb), max(*fb)) if fb is not None else (level, level)
            nlo, nhi, _nc = _seat_node_band(ring, band, cps, bucket_to_idx)
            if _nc:
                ilo, ihi = max(lo, nlo), min(hi, nhi)
                if ilo > ihi:
                    # LOUD, never silently shipped: the frontage band and
                    # the node band have no common level, which is
                    # precisely the split-level-seat trigger.
                    # SUPERSEDED under the pad-variable law: the two
                    # instruments become ONE domain (the ring-vertex
                    # intersection), so this report would describe a seat
                    # that is about to be replaced.
                    if not _PBV:
                        _sb_empty.append((s.ref or "?", lo, hi, nlo, nhi,
                                          level, _nc))
                else:
                    new = min(max(level, ilo), ihi)
                    if new != level and not _PBV:
                        _sb_moved.append((s.ref or "?", level, new,
                                          nlo, nhi, _nc))
                    # The box is documented as "the interval the seat was
                    # chosen from"; narrowing it with the level is what
                    # stops the coupler putting the seat straight back
                    # above the node ceiling.
                    level, lo, hi = new, ilo, ihi
        else:
            box = _frontage_box(ring)
            if box is not None:
                lo, hi = box
                level = min(de, hi) if de is not None else hi
            else:                                    # no apron-shared edge / off
                level = _median(ring, de)
                if level is None:
                    level = float(lv)                # off-network → fallback
                # Box = the band intersected over the pad's own ring, so the
                # coupling can still move a fallback pad within its reachable
                # range (an immovable DEM-low seat forced the serving spine
                # 5 m below its own profile — building26).
                blos = [b[0] for (x, y) in ring
                        if (b := band(x, y)) is not None]
                bhis = [b[1] for (x, y) in ring
                        if (b := band(x, y)) is not None]
                if bhis:
                    lo, hi = min(max(blos), min(bhis)), min(bhis)
                else:
                    lo = hi = level                  # off-network: immovable
        # ── §1.1/§1.2 — THE DOMAIN, AND THE SEAT CHOSEN UNDER IT ────────
        # THE RING-MEDIAN SEAT PASS RETIRES FOR THIS CLASS (spec §1.2).
        # Everything above chose a level FIRST — the ring median, or the
        # frontage-edge box clamped to DEM — from a SUBSET of the pad's
        # geometry, and then defended it.  The founding refutation
        # (``config.BAND_SEAT_ANCHORS``, +4,069 rows at SPJC) is that a
        # rigid pre-committed seat contradicts the narrowing computed
        # after it.  So under this law the pad is ONE FLAT VARIABLE and
        # its DOMAIN is the intersection of the narrowed band over EVERY
        # ring vertex — a flat pad must be lawful at all of them — and
        # the seat is the value chosen inside that domain.  The DEM is
        # the preference (DEM-LAST, RULINGS 2026-08-25) and the domain is
        # the law; where they disagree the domain wins, which is the
        # difference from ``min(de, hi)`` (bounded above and NOT below).
        if _PBV:
            _dd = ring_domain_detail(ring, band)
            _dlo, _dhi, _dn = _dd["lo"], _dd["hi"], _dd["sampled"]
            if _dn == 0:
                # OFF-NETWORK.  The band says nothing here, which is not
                # "nothing is lawful here" — keep the legacy fallback
                # rather than invent a domain (the honest reading of
                # ``ring_domain``'s ``sampled == 0``).
                _pv_offnet += 1
                _pv_domains.append(None)
            elif domain_empty(_dlo, _dhi, PAD_LAW_TOL_M):
                # §1.4 — AN EMPTY DOMAIN IS A CONTRADICTION, not a band
                # to clamp into: no single level is lawful at every ring
                # vertex of a pad that must be flat.  REPORT-FIRST (the
                # unified-law-band Amendment 1 mechanics, SAME ledger):
                # the row lands in ``law_band_contradictions`` and this
                # pad keeps its PRE-SPEC box, so the rest of the airport
                # still gets the narrowing.
                _pv_empty.append((s.ref or "?", _dlo, _dhi, _dn,
                                  float(level)))
                try:
                    _cll = layout.m_to_ll(float(s.polygon.centroid.x),
                                          float(s.polygon.centroid.y))
                except Exception:                    # pragma: no cover
                    _cll = None
                record_pad_domain_contradiction(
                    layout, ref=s.ref or "?", ll=_cll,
                    lo=_dlo, hi=_dhi, sampled=_dn, kept=float(level))
                _pv_domains.append(None)
            else:
                lo, hi = float(_dlo), float(_dhi)
                level = clamp_into(de if de is not None else level, lo, hi)
                _pv_domains.append(_dd)
        pads.append((s, ring, float(level), lo, hi))
        # THE BAND EVIDENCE for this pad (lead order 2026-08-24), recorded
        # with the seat so a reader can put the two side by side.
        _prov_k: list = []
        # ONE READ of the pad's frontage records, THREE consumers: the
        # evidence export, the consistency provenance, and the binding-route
        # publication below.  A second read would be a second sample set.
        _fr_recs = _frontage_band_records(s, ring)
        for _fr in _fr_recs:
            _fr["seat_m"] = float(level)
            _frontage_band_ll.append(_fr)
            # ONE capture, TWO consumers: the same record object carries the
            # evidence export AND the consistency provenance, so the two can
            # never describe different frontage points.
            if _consist_on and "anchor_nodes" in _fr:
                _fr["seat_final_m"] = float(level)   # overwritten if narrowed
                _prov_k.append(_fr)
        _pad_prov.append(_prov_k)
        # THE BINDING ROUTE for this pad, per side (spec §1.3/§1.4) — two
        # recorded-provenance walks along an already-chosen chain, no
        # Dijkstra and no band rebuild.
        if _routes_prov is not None:
            _pad_routes.append(_pad_binding_route_record(
                layout, unified_graph, _routes_prov, s.ref or "?", level,
                _fr_recs))
        # ── PAD-SEAT FEASIBILITY GATE (owner ruling RULINGS 2026-08-24c)
        # "A pad seat that cannot reach its governing centerline anchor
        # within 1 % x chord is a SEAT DEFECT caught at seating time
        # (anchor-placement law analogue), NEVER surface debt."
        #
        # THE BAND IS THAT TEST, ALREADY COMPUTED.  ``band(x, y)`` is the
        # interval of levels reachable at cap from the routes that serve
        # this point — the frontage band ``lo``/``hi`` above is exactly
        # "what the governing centerline anchor permits at 1 % x chord",
        # measured along the straight route the band is built on.  So the
        # gate is: does the seat we are about to ship lie INSIDE its own
        # reach interval?
        #
        # This catches a class nothing reported before.  The full-frontage
        # path CLAMPS into the interval, and an empty intersection is the
        # split-level trigger above — but the SMALL-pad path seats at
        # ``min(de, hi)``, which is bounded above and NOT below: a pad
        # whose DEM centroid sits under the reach floor ships BELOW every
        # level its frontage can reach, and no surface can honour it.
        #
        # REPORT-FIRST, BY ORDER: the seat is NOT moved this round.  The
        # count and the names are the deliverable; the fix policy is the
        # next ruling if the count is material.
        _gap, _side = seat_feasibility_gap(level, lo, hi)
        if _gap > _SEAT_FEASIBILITY_TOL_M:
            _seat_infeasible.append({
                "ref": s.ref or "?",
                "seat_m": float(level),
                "reach_lo_m": float(lo),
                "reach_hi_m": float(hi),
                "gap_m": float(_gap),
                "side": _side,
                "centroid": (float(s.polygon.centroid.x),
                             float(s.polygon.centroid.y)),
                "area_m2": float(s.polygon.area),
            })

    # THE BAND EVIDENCE, published for the census (lead order 2026-08-24):
    # the interval the SOLVE's own band offered at each pad frontage point,
    # beside the seat that was chosen from it.  Evidence, never law.
    setattr(layout, "_frontage_band_ll", _frontage_band_ll)
    # THE BINDING ROUTES, published for the sidecar (spec §1.4) — through
    # the MERGE-BY-PAD-REF publisher, never assignment (pads-as-band-
    # variables Amendment 1 §3): this container has two producers (the
    # route capture here, the pad-variable domains in
    # ``pad_variables``), and an assignment would make whichever ran
    # second delete the other's answer.  ``nodespace: null`` says the
    # capture could not run; ``records: []`` says it ran and found no
    # pads; an absent sidecar key says the patch predates the law.
    from ...pad_variables import publish_pad_variable_provenance as _pub_pbr
    _pub_pbr(layout, _pad_routes, nodespace=_routes_ns)
    if _pad_routes:
        _n_off = sum(1 for r in _pad_routes if r.get("off_network"))
        _report(f"  [pad-routes] {len(_pad_routes)} pad(s) carry a published "
                f"binding route ({_n_off} off-network) in node space "
                f"{_routes_ns} — the band's own recorded route, not a replay")
    if _frontage_band_ll:
        _n_pads = len({r["pad"] for r in _frontage_band_ll})
        _report(f"  [frontage-band] {len(_frontage_band_ll)} band "
                f"interval(s) recorded at the frontage points of "
                f"{_n_pads} pad(s) — evidence for the seat adjudication "
                f"(the band the solve used, not a replay)")

    # THE GATE'S READ-OUT.  Loud, named, and published for the census —
    # a seat defect is not surface debt and must never be read as one.
    _publish_seat_infeasible(layout, _seat_infeasible, _report)

    if _sb_moved or _sb_empty:
        _report(f"  [seat-band] clamped {len(_sb_moved)} full-frontage seat(s)"
                f" into their own node band; {len(_sb_empty)} pad(s) have NO "
                f"common level (split-level-seat trigger)")
        for (ref, was, now, nlo, nhi, nc) in sorted(
                _sb_moved, key=lambda r: -abs(r[2] - r[1]))[:12]:
            _report(f"  [seat-band]   {ref}: {was:.3f} -> {now:.3f} "
                    f"({now - was:+.3f} m) node band [{nlo:.3f},{nhi:.3f}] "
                    f"over {nc} contact node(s)")
        for (ref, lo_, hi_, nlo, nhi, lvl, nc) in _sb_empty:
            _report(f"  [seat-band]   EMPTY {ref}: frontage [{lo_:.3f},"
                    f"{hi_:.3f}] vs node band [{nlo:.3f},{nhi:.3f}] over "
                    f"{nc} contact node(s); seat kept at {lvl:.3f} "
                    f"— NOT a lawful level, needs sectioned seats")

    # ── THE PAD-VARIABLE READ-OUT (spec §1.1/§1.2/§1.4) ─────────────────
    if _PBV:
        _n_dom = sum(1 for d in _pv_domains if d is not None)
        _widths = sorted(d["hi"] - d["lo"]
                         for d in _pv_domains if d is not None)
        _wmed = (0.0 if not _widths else
                 (_widths[len(_widths) // 2] if len(_widths) % 2 else
                  0.5 * (_widths[len(_widths) // 2 - 1]
                         + _widths[len(_widths) // 2])))
        _report(
            f"  [pad-vars] {_n_dom} derived pad(s) are BAND-BOUNDED "
            f"VARIABLES — domain = the narrowed band intersected over "
            f"every ring vertex, seat chosen UNDER it (median width "
            f"{_wmed:.3f} m, narrowest {(_widths[0] if _widths else 0.0):.3f} "
            f"m, widest {(_widths[-1] if _widths else 0.0):.3f} m); "
            f"{_pv_offnet} pad(s) off-network keep the pre-spec box; "
            f"{len(_pv_empty)} pad(s) have an EMPTY domain")
        for (_ref, _dlo, _dhi, _dn, _kept) in sorted(
                _pv_empty, key=lambda r: r[1] - r[2], reverse=True)[:12]:
            _report(
                f"  [pad-vars]   EMPTY DOMAIN {_ref}: floor {_dlo:.3f} > "
                f"ceiling {_dhi:.3f} (empty by {_dlo - _dhi:.3f} m) over "
                f"{_dn} ring vertex(es) — no single level is lawful at "
                f"every vertex of a pad that must be FLAT.  REPORT-FIRST: "
                f"the row is in `law_band_contradictions`, this pad keeps "
                f"its pre-spec box at {_kept:.3f} m and the rest of the "
                f"airport keeps the narrowing")
        # THE REFUSE ARM (spec §1.4 / §2): the SAME sites, the same
        # ledger, one flag apart.  Raised BEFORE any patch is written.
        refuse_on_empty_pad_domains(
            layout, [(r[0], r[1], r[2], r[3]) for r in _pv_empty],
            getattr(layout, "icao", "") or "")

    # ── MERGED RIGID UNITS — STANDING LAW (owner; the coupling lane's
    # recorded defect class) ────────────────────────────────────────────
    # Pads that share a ring vertex are ONE flat group in the projection,
    # and the relation is TRANSITIVE — a chain of touching buildings is a
    # single rigid body.  The projection seats such a body at ONE level (it
    # broadcasts the group's mean), so a coupler that let its members take
    # different levels was choosing values the projection would overwrite.
    # KCLT: one 6-pad chain, 15 pairs at budget 0.  HECA: more.
    #
    # The law is enforced STRUCTURALLY here, not as an inequality the POCS
    # has to converge to: the members collapse into ONE seat variable with
    # ONE box, so there is no |L_i − L_j| ≤ 0 pair left to approximate and
    # no group mean for the projection to mint afterwards.
    units, unit_of, _u_rows = _merge_rigid_units(pads, cps)
    if _u_rows:
        _report(f"  [seat-rigid] {len(_u_rows)} MERGED RIGID unit(s) "
                f"covering {sum(len(r['members']) for r in _u_rows)} pad(s) "
                f"seated at ONE level each (pads sharing a ring vertex, "
                f"transitively)")
        for r in sorted(_u_rows, key=lambda r: -len(r["members"]))[:12]:
            _report(f"  [seat-rigid]   {{{', '.join(r['refs'])}}} target "
                    f"{r['level']:.3f} m, box [{r['lo']:.3f},{r['hi']:.3f}]"
                    f"{'  EMPTY member-box intersection' if r['empty'] else ''}")

    # ── SEAT COUPLING (user 2026-07-03): jointly-feasible unit levels ────────
    # Each pad pins nearby spine/apron nodes to ``seat ± 1%·d`` (the building↔
    # spine law, never blended/relaxed), so two units across shared pavement
    # must satisfy ``|L_i − L_j| ≤ budget`` — independent seats left
    # neighbouring pads ≤2.6 m apart and made the surrounding faces infeasible
    # (the SPJC >3% class; the feasibility audit proves joint levels exist).
    # Project the independent targets onto the coupled polytope (POCS, same
    # solver as the no-building apron seats).
    #
    # THE BUDGET IS THE ROUTE BUDGET — the min-budget path on the
    # within-shape law graph ``feasibility_project`` enforces (see the
    # ROUTE-PRICED banner at the top of this module).  Admission is route
    # reachability inside the horizon; the chord corridor and the
    # pavement-visibility fraction are RETIRED as predicates and survive
    # only as the census that makes each pair's tightening adjudicable.
    _pack_rows: list = []
    _pack_declared = 0
    if len(units) >= 2:
        from auto_patch.config import APRON_MAX_GRADE
        from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
        if law_graph is None:
            # NOT a fallback.  The coupler has exactly one metric; without
            # the law graph it cannot price at all, and pricing on a chord
            # instead is the two-instrument defect this law removed.
            _report("  [seat-couple] WIRING DEFECT: the solve passed no law "
                    "graph — the coupler cannot price on the metric the "
                    "projection enforces, so NO pair is coupled this build")
            pairs: dict = {}
            _rdiag = None
        else:
            _unit_nodes = [set() for _ in units]
            for k, (_s, _ring, *_r) in enumerate(pads):
                _g = _unit_nodes[unit_of[k]]
                for (x, y) in _ring:
                    _i = bucket_to_idx.get(
                        cps.get_or_add(float(x), float(y)))
                    if _i is not None:
                        _g.add(_i)
            pairs, _rdiag = _pad_route_budgets(law_graph, _unit_nodes,
                                               n_nodes=n_nodes)
        _chord_lim: dict = {}
        if _rdiag is not None:
            # THE CHORD CENSUS (report only — it admits nothing).  The
            # rejection frame the dossier quoted (HECA 2 613 `gap>corridor`,
            # HEAZ 7) is re-quoted here against route admission, and
            # `not_visible` is 0 BY CONSTRUCTION: the predicate is gone.
            _chord_far = 0
            _far_admitted = 0
            _far_worst = 0.0
            for i in range(len(units)):
                pi = units[i]["polygon"]
                for j in range(i + 1, len(units)):
                    gap = pi.distance(units[j]["polygon"])
                    if gap > BUILDING_REACH_CORRIDOR_M:
                        _chord_far += 1
                    if (i, j) in pairs:
                        _chord_lim[(i, j)] = APRON_MAX_GRADE * gap
                        if gap > BUILDING_REACH_CORRIDOR_M:
                            _far_admitted += 1
                            _far_worst = max(_far_worst, gap)
            _tight = [(k, pairs[k], _chord_lim[k]) for k in pairs
                      if k in _chord_lim and pairs[k] < _chord_lim[k] - 1e-9]
            _loose = [k for k in pairs
                      if k in _chord_lim and pairs[k] > _chord_lim[k] + 1e-9]
            _npairs_all = len(units) * (len(units) - 1) // 2
            _report(
                f"  [seat-couple] ROUTE METRIC: {len(units)} unit(s) over "
                f"{len(pads)} pad(s), {len(pairs)} coupled pair(s) of "
                f"{_npairs_all} (horizon {_rdiag['horizon_m']:.2f} m of "
                f"budget = {_rdiag['dial_m']:.0f} m at the apron cap; law "
                f"graph {_rdiag['graph_nodes']} node(s) / "
                f"{_rdiag['graph_edges']} edge(s), RAW law budgets)")
            _report(
                f"  [seat-couple]   rejection census: route-unreachable "
                f"{_rdiag['unreachable']}, unit off the law graph "
                f"{_rdiag['off_graph']}, not_visible 0 (predicate retired); "
                f"the chord frame would have rejected {_chord_far} as "
                f"gap>corridor")
            if _rdiag["merged_pairs"]:
                # The rigid-unit collapse above already merged every pad
                # pair that shares a ring vertex, so the projection's own
                # node-set contraction must find nothing left to merge.
                # If it does, the two relations disagree — name it.
                _report(
                    f"  [seat-couple]   WIRING DEFECT: the law graph's "
                    f"flat-group contraction merged {_rdiag['merged_pairs']} "
                    f"further pair(s) across {_rdiag['merged_groups']} "
                    f"group(s) that the rigid-unit law did not — the two "
                    f"share-relations disagree")
            # THE DIAL'S UNITS, MEASURED (never assumed).  Admission is the
            # 200 m corridor expressed in the BUDGET metric, so a route over
            # cheap pavement — flat-cross edges, and the FLAT shapes and
            # merged pad chains that cost nothing at all — can reach far past
            # 200 m of ground distance.  That population is counted here so
            # the dial's unit choice is adjudicable on evidence.
            _report(
                f"  [seat-couple]   reach: {_far_admitted} admitted pair(s) "
                f"lie beyond the {BUILDING_REACH_CORRIDOR_M:.0f} m chord "
                f"corridor (worst {_far_worst:.0f} m apart)")
            _report(
                f"  [seat-couple]   budget vs chord: {len(_tight)} "
                f"TIGHTENED, {len(_loose)} loosened, "
                f"{len(pairs) - len(_tight) - len(_loose)} equal; "
                f"{_rdiag['lazy_entries']} certified-lazy entry(ies) "
                f"contribute ring edges only, {_rdiag['interval_edges']} "
                f"interval edge(s) excluded (one-sided slabs)")
            # TIGHTENING, ATTRIBUTED (never consumed).  The margin frame is
            # retired, so there is nothing left to split: every metre of
            # tightening below is the LAW's route being shorter than the
            # chord.  The line stays because the magnitude is the evidence
            # that the route metric — not the chord — is what binds.
            _tot_tight = sum(cb - rb for (_k, rb, cb) in _tight)
            _report(
                f"  [seat-couple]   tightening attribution: "
                f"{_tot_tight:.3f} m total across {len(_tight)} pair(s), "
                f"ALL of it the RAW law route (no margin frame exists)")
            for ((i, j), rb, cb) in sorted(_tight,
                                           key=lambda r: r[1] - r[2])[:12]:
                _report(f"  [seat-couple]     tightened "
                        f"{units[i]['ref']} <-> {units[j]['ref']}"
                        f" route {rb:.4f} m vs chord {cb:.4f} m "
                        f"({rb - cb:+.4f})")
            # ── BUDGET IDENTITY — the coupler's own certificate ─────────
            if _rdiag["ident_over"]:
                _report(f"  [seat-couple]   BUDGET-IDENTITY VIOLATION: "
                        f"{len(_rdiag['ident_over'])} pair(s) disagree by "
                        f">1 % between their two endpoints — this is a STOP, "
                        f"not a tolerance to widen")
                for (i, j, dab, dba) in _rdiag["ident_over"][:12]:
                    _report(f"  [seat-couple]     {units[i]['ref']} "
                            f"<-> {units[j]['ref']}: {dab:.6f} vs "
                            f"{dba:.6f} m")
            else:
                _report(f"  [seat-couple]   budget identity OK: worst "
                        f"disagreement {100.0 * _rdiag['ident_worst']:.4f} % "
                        f"over {len(pairs)} pair(s) (limit 1 %)")
        # ── §1.3 AUTHORED-DATUM GROUPS: ACCOMMODATE, ELSE SPLIT ─────────
        # (owner ruling RULINGS 2026-08-27 late, "GRADE LAW OUTRANKS
        # SHARED-DATUM PRESERVATION — PACK GROUPS SPLIT WHEN THEY MUST";
        # this amends basin docket-B rigid group seating.)
        #
        # HERE, and not before the pair pricing, because the ruling's
        # SECOND trigger is priced on the pairs: a group whose
        # intersection is NON-empty still splits when its optimum leaves
        # any member's frontage / no-step law over cap.  Preservation is
        # the TIEBREAKER among lawful placements, never the authority.
        _pack_rows, _pack_declared = _apply_authored_datum_groups(
            layout, units, pairs, _PBV, solve_pack_groups)
        if pairs:
            targets = [u["level"] for u in units]
            boxes = [(u["lo"], u["hi"]) for u in units]
            L = _pocs_project_levels(targets, boxes, pairs)
            _dbg = _os.environ.get("O4_SEAT_DEBUG") == "1"
            if _dbg:
                pre = sorted(
                    ((abs(targets[i] - targets[j]) - lim, i, j, lim)
                     for (i, j), lim in pairs.items()), reverse=True)
                print(f"  [seats] {len(units)} units, {len(pairs)} coupled "
                      f"pairs, polytope "
                      f"{'FEASIBLE' if L is not None else 'EMPTY'}")
                for ex, i, j, lim in pre[:8]:
                    if ex <= 0:
                        break
                    print(f"    pre-conflict {ex:+.2f}m over lim {lim:.2f}: "
                          f"{units[i]['ref']} t={targets[i]:.2f} "
                          f"box=({units[i]['lo']:.2f},{units[i]['hi']:.2f})"
                          f"  vs  {units[j]['ref']} t={targets[j]:.2f} "
                          f"box=({units[j]['lo']:.2f},{units[j]['hi']:.2f})")
            if L is not None:
                moved = sum(1 for k in range(len(units))
                            if abs(L[k] - targets[k]) > 0.01)
                if moved:
                    _report(f"  [seats] coupled {len(units)} unit(s) / "
                            f"{len(pairs)} pairs: moved {moved}, max "
                            f"{max(abs(L[k] - targets[k]) for k in range(len(units))):.2f} m")
                for k in range(len(units)):
                    units[k]["level"] = float(L[k])
            else:
                # ── EMPTY POLYTOPE → LOUD ATTRIBUTION (spec dossier-fixes
                # §4; RULINGS 2026-08-04 split-level building seats: "an
                # empty coupling polytope is LOUD attribution, never a
                # silent ship") ────────────────────────────────────────
                # The values are UNCHANGED — the fix is the sectioned seat,
                # its own spec.  What changes is that the ship is no longer
                # silent: ``feasibility-is-guaranteed`` forbids
                # infeasibility as an ANSWER, so the units, the gap and the
                # footprint RELIEF (the quantity the split-level law
                # thresholds on) are named.
                if _dbg:
                    print("  [seats] EMPTY polytope -> independent seats kept")
                from auto_patch.elevation_per_surface.building_feasibility \
                    import _footprint_dem_relief
                _relief: dict = {}

                def _rel(k):
                    if k not in _relief:
                        r = _footprint_dem_relief(units[k]["polygon"], dem_fn)
                        _relief[k] = None if r is None else float(r[1])
                    return _relief[k]

                conflicts = sorted(
                    ((abs(targets[i] - targets[j]) - lim, i, j, lim)
                     for (i, j), lim in pairs.items()
                     if abs(targets[i] - targets[j]) - lim > 0.0),
                    reverse=True)
                _report(f"  [seat-couple] EMPTY POLYTOPE: {len(units)} "
                        f"unit(s) / {len(pairs)} coupled pair(s) admit NO "
                        f"jointly-feasible seat set; independent seats kept, "
                        f"so {len(conflicts)} pair(s) SHIP violating their "
                        f"own coupling limit")
                # Every conflict row also carries the CHORD limit it would
                # have had, so a rise in shipping-in-violation is accounted
                # pair by pair as honestly-tightened budget rather than
                # waved through.
                for (ex, i, j, lim) in conflicts[:200]:
                    ri, rj = _rel(i), _rel(j)
                    gap_ij = units[i]["polygon"].distance(units[j]["polygon"])
                    cb = _chord_lim.get((i, j))
                    if cb is None:
                        split = ""
                    else:
                        if lim < cb - 1e-9:
                            _tag = "TIGHTENED"
                        elif lim > cb + 1e-9:
                            _tag = "loosened"
                        else:
                            _tag = "equal"
                        split = f" chord_lim={cb:.3f} ({_tag})"
                    _report(
                        f"  [seat-couple]   {units[i]['ref']} "
                        f"{targets[i]:.3f} <-> {units[j]['ref']} "
                        f"{targets[j]:.3f}  gap={gap_ij:.1f} m "
                        f"|dL|={abs(targets[i] - targets[j]):.3f} "
                        f"lim={lim:.3f}{split} excess={ex:+.3f} m  ring relief"
                        f" {'n/a' if ri is None else format(ri, '.2f')} / "
                        f"{'n/a' if rj is None else format(rj, '.2f')} m")

    # THE SPLIT LEDGER, published (spec §1.3).  EVIDENCE, never law
    # (§1.7, the contradiction-ledger precedent): the census prints the
    # count and the worst site, and the existing frontage / no-step /
    # within-shape families price the result.  Published UNCONDITIONALLY
    # under the flag so an empty list reads as "every group
    # accommodated" and never as "the pass did not run".
    if _PBV:
        publish_pack_group_splits(layout, _pack_rows,
                                  declared=_pack_declared)
        _report(format_pack_group_splits(
            getattr(layout, "icao", "") or "", _pack_rows,
            declared=_pack_declared))

    # THE UNIT'S LEVEL IS THE PAD'S LEVEL.  A merged rigid unit broadcasts
    # ONE value to every member pad — that IS the law; the box narrows to
    # the unit's box for the same reason (a member may not yield outside
    # the interval the unit was seated from).
    pads = [(s, ring, float(units[unit_of[k]]["level"]),
             units[unit_of[k]]["lo"], units[unit_of[k]]["hi"])
            for k, (s, ring, _t, _lo, _hi) in enumerate(pads)]

    # ── §1.6 PROVENANCE — the per-pad publication EXTENDS the
    # ``pad_binding_routes`` container (owner ruling RULINGS 7e90032,
    # extend the near-fit, never fork): the DOMAIN the pad's variable
    # lives in, the SOLVED value, and WHICH ring vertex binds each side of
    # the domain, so "why is this pad here" stays a single file read
    # beside the route that bound it.
    if _PBV:
        _prov_recs: list = []
        for _pk, (s, _ring, _lvl, _blo, _bhi) in enumerate(pads):
            _d = _pv_domains[_pk] if _pk < len(_pv_domains) else None
            _u = units[unit_of[_pk]]
            _rec = {
                "pad": s.ref or "?",
                "pad_variable": _d is not None,
                "solved_m": float(_lvl),
                "domain": (None if _d is None
                           else [float(_d["lo"]), float(_d["hi"])]),
                "binding": {
                    "unit": _u["ref"],
                    "unit_members": list(_u.get("refs") or ()),
                    "ring_vertices_sampled": (0 if _d is None
                                              else int(_d["sampled"])),
                    "seat_box": [float(_blo), float(_bhi)],
                },
            }
            if _d is not None:
                for (_side, _vk) in (("floor", "floor_vertex"),
                                     ("ceiling", "ceiling_vertex")):
                    _v = _d.get(_vk)
                    if _v is None:
                        continue
                    try:
                        _rec["binding"][f"{_side}_ll"] = [
                            round(float(_c), 7)
                            for _c in layout.m_to_ll(_v[0], _v[1])]
                    except Exception:                    # pragma: no cover
                        pass
                _rec["binding"]["at_ceiling"] = bool(
                    abs(float(_lvl) - float(_d["hi"])) <= PAD_LAW_TOL_M)
                _rec["binding"]["at_floor"] = bool(
                    abs(float(_lvl) - float(_d["lo"])) <= PAD_LAW_TOL_M)
            _prov_recs.append(_rec)
        # PASS-IDENTITY COMPOSITION (pads-as-band-variables Amendment 1
        # §3 merge).  Two distinct degraded cases, ruled apart: a
        # FOREIGN band (a band of record exists and this is not it)
        # publishes NEITHER routes nor domains — either would be a
        # second engine's answer.  A CAPTURE-DEGRADED context (no
        # unified graph / no attachment_at / no recorded provenance)
        # suppresses only the ROUTES, which need that band's node ids;
        # the DOMAINS are metric intervals read from the band the seats
        # actually consumed, and publishing them stays honest evidence.
        if _routes_reason == "foreign":
            _report("  [pad-vars] NOT publishing pad-variable provenance: "
                    "the band in hand is not this layout's band of "
                    "record — same pass-identity guard, same verdict as "
                    "[pad-routes] above (one check, two consumers).")
        else:
            publish_pad_variable_provenance(
                layout, _prov_recs, pack_groups_declared=_pack_declared)
        _n_at = sum(1 for r in _prov_recs
                    if (r["binding"].get("at_ceiling")
                        or r["binding"].get("at_floor")))
        _report(f"  [pad-vars] provenance published for {len(_prov_recs)} "
                f"pad(s) into `pad_binding_routes` (domain, solved value, "
                f"binding ring vertex per side); {_n_at} pad(s) sit ON a "
                f"domain bound — those are the pads the law, not the DEM, "
                f"placed")

    seats: dict = {}
    #: The ring nodes of pads that ARE band-bounded variables (spec §1.1).
    #: Published for the solve, which reads it to keep those nodes OUT of
    #: the senior tier — a derived pad's law edges enter symmetrically with
    #: the membrane, bounded by its domain through ``seat_boxes``.
    _pv_node_idx: set = set()
    seat_boxes = _store_of(layout).raw("seat_boxes")
    # THE UNIT-KEYED CONSISTENCY PROVENANCE (spec ruling §2): a pad is one
    # flat level, so the narrowing keys per UNIT — and it must survive into
    # the same two spaces the seat itself lives in, the solve's node
    # indices (``elev`` / ``building_seats``) and the CANONICAL keys the
    # ``seat_boxes`` store is keyed by (a node index is meaningful only
    # inside one ``_build_node_list`` call — canonical-identity law).
    _units_prov: list = ([{"ref": u["ref"], "refs": list(u["refs"]),
                           "level": float(u["level"]),
                           "lo": float(u["lo"]), "hi": float(u["hi"]),
                           "records": [], "nodes": [], "keys": []}
                          for u in units] if _consist_on else [])
    if _consist_on:
        for _pk in range(len(_pad_prov)):
            _units_prov[unit_of[_pk]]["records"].extend(_pad_prov[_pk])
    for _pk, (s, ring, level, lo, hi) in enumerate(pads):
        # BOUNDED YIELD box (owner ruling 2026-07-29): the pad's box is the
        # ``[lo, hi]`` its seat was chosen from, WIDENED to include the
        # chosen level — an uncoupled seat is ``min(DEM, hi)`` and may rest
        # below ``lo``, and the box must never move a resting seat (the
        # clamp refines the yield, it is not a new hold).  A ring node
        # shared by two pads keeps the tighter interval per side.
        blo = min(float(lo), float(level))
        bhi = max(float(hi), float(level))
        # THE SYMMETRY MEMBERSHIP (spec §1.1): a pad that really is a
        # band-bounded VARIABLE — it has a domain — carries no seniority
        # over the membrane.  A pad that fell back (off-network, or an
        # empty domain reported under §1.4) is NOT one and keeps the
        # pre-spec disposition; naming the two apart is what stops a
        # fallback silently inheriting a law it was never given.
        _pv_this_is_var = bool(
            _PBV and _pk < len(_pv_domains) and _pv_domains[_pk] is not None)
        _up = _units_prov[unit_of[_pk]] if _consist_on else None
        for (x, y) in ring:
            k = cps.get_or_add(float(x), float(y))
            i = bucket_to_idx.get(k)
            if i is not None:
                seats[i] = float(level)
                if _pv_this_is_var:
                    _pv_node_idx.add(i)
                if _up is not None:
                    _up["nodes"].append(i)
            if _up is not None:
                _up["keys"].append(k)
            prev = seat_boxes.get(k)
            seat_boxes[k] = ((blo, bhi) if prev is None
                             else (max(prev[0], blo), min(prev[1], bhi)))
    setattr(layout, "_pad_variable_idx", _pv_node_idx)
    if _consist_on:
        for _up in _units_prov:
            _up["nodes"] = sorted(set(_up["nodes"]))
            _up["keys"] = list(dict.fromkeys(_up["keys"]))
        # A unit needs NODES to be narrowable at all.  It needs frontage
        # RECORDS only for the frontage-subset mechanism: §2 sources its
        # interval from the §1 anchor neighbourhood, so a pad with no
        # frontage record is still a candidate there (and is reported as
        # unanchored if no §1 chord reaches it either).
        from .pad_seat_consistency import dem_last_seat_bias_enabled
        _keep_recordless = dem_last_seat_bias_enabled()
        _units_prov = [u for u in _units_prov
                       if u["nodes"] and (u["records"] or _keep_recordless)]
        setattr(layout, "_pad_seat_consistency_units", _units_prov)
        if _units_prov:
            _report(f"  [pad-seat-consistency] provenance captured for "
                    f"{len(_units_prov)} pad unit(s) "
                    f"({sum(len(u['records']) for u in _units_prov)} frontage "
                    f"band record(s)); the consistency intersection binds "
                    f"after the corridor profiles solve")
    else:
        setattr(layout, "_pad_seat_consistency_units", [])

    # ── A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR ────────────────
    # (owner RULINGS 2026-08-25f; spec ``basin-pad-floor-seating-spec``
    # §1.1: "its flat level is the facility's floor elevation, not the
    # surrounding grade; downstream consumers (seats, chords, strip
    # adoption) see the floor value".)
    #
    # The declaration is made PRE-SOLVE, by the same pass that births
    # the floor pan and from the same ``floor_elevation``
    # (``object_terrain_assembly.build_tunnel_layout_shapes`` →
    # ``BuiltShape.basin_floor_seat_m``).  It is DECLARED TERRAIN, in
    # exactly the sense the trench floor pan is — not a route-
    # reachability choice — so it OVERRIDES whatever the frontage /
    # whole-ring band chose above rather than being intersected with
    # it: a pit floor is not reachable at ≤ 1 % from a taxiway, and
    # that is the point of the pit.
    #
    # THE BOX IS A POINT.  ``seat_boxes`` is the bounded-yield registry
    # every later freeing pass clamps into (owner ruling 2026-07-29);
    # a declared floor that any pass may yield 8 m upward is not
    # declared.  The node set is published for the solve's seat guards
    # (``solve.py``), which must not send a declared floor into
    # yield-hard for being outside the airside band — it is outside the
    # airside band BY CONSTRUCTION.
    _basin_seat_idx: set = set()
    _basin_seat_pads = 0
    # ── A DECLARED PAD WELDED TO AN UNDECLARED ONE CANNOT SEAT ──────
    # (measured at LEMD, 2026-08-25, arm 1 of this round.)  The MERGED
    # RIGID UNIT law is standing law: pads sharing a ring vertex are ONE
    # flat body at ONE level, transitively.  A rigid body cannot be at
    # two levels — so a declared pad welded to an UNDECLARED neighbour
    # has exactly two consistent outcomes, and BOTH are wrong here:
    # either the neighbour sinks to the basin floor with it, or the
    # declaration is discarded.
    #
    # LEMD is the exemplar and the numbers are the argument.
    # ``building8`` (33,237 m², the declared pad) shares its WHOLE east
    # edge — three canonical ring nodes — with ``building18``
    # (75,885 m²), which is outside the basin entirely; the build's own
    # rigid-unit report reads "{building8, building18} target 599.345 m".
    # Seating the unit would put a 16 m cliff through a terminal complex
    # and sink a 75,885 m² pad for the sake of an 11,805 m² basin.  Arm 1
    # made the declaration anyway and the projection SILENTLY discarded
    # it (both pads emitted 600.40 m) — the exact silent class §2 of this
    # spec exists to kill.
    #
    # So the seat is WITHDRAWN, LOUDLY, naming both pads and the
    # neighbour's area — the same disposition R13's restore guard gives a
    # cut that bought nothing.  THE FLOOR EXCLUSION IS UNAFFECTED: the
    # basin still cuts through the pad's ground and the floor pan still
    # emits (LEMD: 11,805 m² at 584.50 m).  What is withdrawn is only the
    # claim that the PAD moves.  Which resolution the ruling wants —
    # sink the whole rigid unit, or CUT the pad at the facility
    # footprint the way R13 cuts pavement — is a design decision, and
    # this line is what puts the numbers in front of it.
    _decl_pads = [s for s in layout.shapes
                  if getattr(s, "basin_floor_seat_m", None) is not None
                  and s.polygon is not None and not s.polygon.is_empty]
    if _decl_pads:
        _decl_ids = {id(s) for s in _decl_pads}
        _undecl_by_key: dict = {}
        for s in layout.shapes:
            if (s.role != ROLE_BUILDING or id(s) in _decl_ids
                    or s.polygon is None or s.polygon.is_empty):
                continue
            try:
                _r = _open_ring(list(s.polygon.exterior.coords))
            except (ValueError, TypeError):
                continue
            for (x, y) in _r:
                _undecl_by_key.setdefault(
                    cps.get_or_add(float(x), float(y)), s)
    for s in _decl_pads:
        _decl = getattr(s, "basin_floor_seat_m", None)
        try:
            _ring = _open_ring(list(s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        _keys = [cps.get_or_add(float(x), float(y)) for (x, y) in _ring]
        _welded = {}
        for k in _keys:
            _n = _undecl_by_key.get(k)
            if _n is not None:
                _welded.setdefault(id(_n), [_n, 0])[1] += 1
        if _welded:
            for (_n, _shared) in _welded.values():
                _report(
                    f"  [seats] BASIN PAD SEAT WITHDRAWN: {s.ref!r} "
                    f"({s.polygon.area:.0f} m2) is declared at its basin "
                    f"floor {float(_decl):.2f} m but shares {_shared} ring "
                    f"node(s) with UNDECLARED pad {_n.ref!r} "
                    f"({_n.polygon.area:.0f} m2) — one rigid flat body "
                    f"cannot be at two levels, and seating the unit would "
                    f"take the neighbour down with it.  The basin floor "
                    f"still cuts and emits; the PAD stays at grade.")
            s.basin_floor_seat_m = None
            continue
        _basin_seat_pads += 1
        _lv = float(_decl)
        for k in _keys:
            i = bucket_to_idx.get(k)
            if i is not None:
                seats[i] = _lv
                _basin_seat_idx.add(i)
            seat_boxes[k] = (_lv, _lv)
    setattr(layout, "_basin_pad_seat_idx", _basin_seat_idx)
    if _basin_seat_pads:
        _report(f"  [seats] {_basin_seat_pads} building pad(s) inside a "
                f"basin facility seated at the DECLARED facility floor "
                f"({len(_basin_seat_idx)} ring node(s)); the airside band "
                f"does not bind a pad in a pit")

    # ── §1.5(d) — A PLACED SEAT JOINS THE ANCHOR SET, INCREMENTALLY ────
    # (spec docs/specs/unified-law-band-spec.md §1.5d; owner ruling
    # RULINGS 2026-08-27 "REFINE THE REACH BAND FIRST".)
    #
    # WHY HERE AND NOT INSIDE THE PER-PAD LOOP.  A pad's level is not
    # PLACED until the joint coupler has run: the per-pad pass computes a
    # target and a box, and the POCS projection above reconciles the
    # units against each other ON THE SAME LAW GRAPH.  Anchoring a target
    # mid-loop would seed the band with a value the coupler is about to
    # overwrite — a second authority on the seat, which is precisely what
    # this ruling removes.  The seats that exist HERE are the placed ones.
    #
    # WHY IT IS AN INCREMENT AND NEVER A RECOMPUTE.  The fields are a min
    # over anchors of ``v_a + d_law(a, .)``; a new anchor adds one term,
    # so the answer is ``min(old, v_s + d(s, .))`` — a bounded Dijkstra
    # from the new source that stops the moment a node's bound is not
    # tightened (non-negative budgets mean nothing beyond it can tighten
    # either).  ``tests/test_law_band.py`` pins incremental == full
    # recompute on a fixture.
    #
    # Sub-gate OFF, band without the facility, or no seat ⇒ inert.
    _add_seats = getattr(band, "add_seat_anchors", None)
    if _add_seats is not None and seats:
        try:
            # ONE statement for the whole placed-seat set: the ceiling is
            # a MIN over anchors, so the batch is one multi-source pruned
            # walk and one grid refresh.  Per-seat calls are the arm that
            # cost a killed 20-minute HECA build.
            _add_seats({int(_i): float(_lv) for _i, _lv in seats.items()})
        except Exception as _sa_exc:                   # pragma: no cover
            _report(f"  [law-band] the placed-seat anchors FAILED "
                    f"({type(_sa_exc).__name__}: {_sa_exc}) — the band "
                    f"keeps its pre-seat values")
        _sm = getattr(band, "seat_anchor_meta", None) or {}
        if _sm.get("anchors"):
            _report(f"  [law-band] {_sm['anchors']} placed seat node(s) "
                    f"joined the band's anchor set incrementally (spec "
                    f"§1.5d): {_sm['nodes_tightened']} node bound(s) "
                    f"tightened over {_sm['relaxations']} relaxation(s), "
                    f"{_sm['cells_refreshed']} grid cell(s) refreshed, "
                    f"{_sm['off_graph']} seat node(s) not on the law graph "
                    f"— no field recompute")
    return seats


# ══════════════════════════════════════════════════════════════════════
# DETACHED (NON-AIRSIDE-SERVED) BUILDING PADS — THE GROUNDSIDE LAW
# ══════════════════════════════════════════════════════════════════════
# Item 3(b), 2026-08-05.  ``build_detached_pad_dem_pins`` lived here: it
# HARD-pinned every non-airside-served ROLE_BUILDING pad at the MEDIAN of
# its raw DEM samples for the whole solve.  That is DEM as a constraint by
# the ruling's own definition ("DEM chooses WHERE in the lawful band a
# thing seats.  It never shapes the band, never constrains, never
# blocks."), and it fails the constant-DEM oracle head-on: with DEM ≡ c
# every detached pad is frozen at ``c`` while the groundside pavement it
# is welded into sits wherever the airside solve put it — an arbitrarily
# large step at a shared node, on ground with no relief.
#
# ── THE DEFECT THE PIN WAS MASKING, ATTRIBUTED ───────────────────────
# The pin's justification was measured and real: unpinned, "the
# route-profile blend paints them with the surrounding airside level"
# (KBNA: pads emitted flat at 170-172 over 158-167 ground).  The writer
# is NOT the blend.  Read in order:
#
#   1. ``raster_reach_band._domain_geom`` puts ROLE_BUILDING in the reach
#      band's PROPAGATION DOMAIN unconditionally — with no airside-service
#      test of any kind — and the propagation is a GRID walk over the
#      paved mask (plus a bounded off-mask radius,
#      ``RASTER_REACH_BAND_OFFNET_RADIUS_M``).
#   2. ``building_feasibility.spine_value_fields`` gives that grid its
#      values: ``floor[i] = max over runway anchors (value_a − route
#      budget)`` — the level a node must be AT LEAST for the runway to be
#      reachable within grade.  An airside law, about airside pavement.
#   3. So a pad that ``building_feasible_levels`` REFUSED to seat (its
#      airside-touch test: distance to a ≥``BUILDING_AIRSIDE_CONTACT_MIN_
#      COMPONENT_M2`` airside component ≤ ``_TOUCH_TOL_M``) still receives
#      a ``node_band`` whose FLOOR is that airside floor.  Two instruments,
#      one assumed population — the seat's notion of "served" is a route /
#      component test, the band's is grid connectivity over a mask the pad
#      is itself a member of.
#   4. ``one_solve.one_profile_solve`` then WRITES it, twice: the warm
#      start ``elev[i] = _dem_target(i) = clamp(DEM, floor, ceil)`` lifts
#      the pad's DEM straight to that airside floor, and every sweep
#      re-clamps into ``lo_e = max(n_lo, floor[i])`` so it stays there.
#      The pad emits FLAT at the airside level because all its ring nodes
#      share (nearly) the same floor.
#
# The harmonic/mean blend has no altitude preference of its own (solve.py
# says so where it owns 67.1 % of the corridor's DEM departure); the BAND
# FLOOR is the writer.  Fixing it at source therefore means: a pad the
# airside law does not serve does not get the airside band.
#
# ── THE LAW THAT REPLACES THE PIN ────────────────────────────────────
# A detached pad is a GROUNDSIDE object (owner: groundside terrace law +
# adjacent-ground zone law).  Its datum is the surface it actually abuts —
# the groundside pavement / service road / apron ring it welds into — read
# as SOLVED VARIABLES, the same datum family as the groundside mouth
# ceiling (item 3(a)) and the same resolution pattern as
# the adjacent-ground FOOT rule (foot on the host ring, interpolated between
# two solved ring variables; identity when the pad shares the host's
# vertex).  Buildings are FLAT, so the pad's lawful levels are the
# INTERSECTION over its contacts of ``[datum − cap·d, datum + cap·d]``,
# and the DEM seed picks the point inside it.
#
# CONSTANT-DEM ORACLE, BY INSPECTION.  Every term of the box is a solved
# pavement variable or a law constant — no DEM appears in it, so the box
# is whatever the law grants in BOTH worlds.  The only DEM-dependent step
# is which point of the box the pad seats at, which is precisely the role
# the ruling assigns the DEM: with DEM ≡ 1 m the seed is below the box and
# the pad seats at ``lo`` (its FLOOR); with DEM ≡ 10 000 m it seats at
# ``hi`` (its CEILING) — the ADDENDUM's extreme-seating assertion, and the
# band-width field at those nodes reads exactly ``hi − lo``.  A pad with NO
# resolvable host has an unbounded box and simply keeps its seed: no law
# binds it, and a missing datum never becomes a terrain bound.

#: Solved pavement roles a DETACHED pad may take its datum from.  Wider
#: than ``_PAD_HOST_ROLES`` (which serves the post-solve airside re-level)
#: by exactly the groundside classes — a detached pad's host is normally a
#: lot or a service road, which is why that pass never found one for it.
_DETACHED_PAD_HOST_ROLES = None       # bound lazily (import cycle-free)


def _detached_pad_host_roles():
    from auto_patch.layout import (
        ROLE_APRON, ROLE_CROSS_CONNECTOR, ROLE_GROUNDSIDE_PAVEMENT,
        ROLE_JUNCTION, ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
        ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD, ROLE_STUB)
    global _DETACHED_PAD_HOST_ROLES
    if _DETACHED_PAD_HOST_ROLES is None:
        _DETACHED_PAD_HOST_ROLES = frozenset({
            ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD,
            ROLE_SERVICE_JUNCTION, ROLE_APRON, ROLE_JUNCTION,
            ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
            ROLE_STUB, ROLE_CROSS_CONNECTOR})
    return _DETACHED_PAD_HOST_ROLES


#: Contact radius (m) for the pad→host datum march.  The pad and its host
#: normally share ring geometry outright (d = 0); this only has to bridge
#: the slice's weld tolerance, so it is the same 2.5 m the landed
#: ``PAD_HOST_LEVEL_CONTACT_M`` uses for the airside twin.
DETACHED_PAD_HOST_CONTACT_M = 2.5


def detached_pad_nodes(layout, bucket_to_idx, building_seats):
    """``[(shape, [node_idx, ...])]`` — every ROLE_BUILDING pad that is NOT
    airside-served (no ring node in ``building_seats``).

    The membership test is unchanged from the deleted DEM-pin builder: the
    seat producer (``building_feasible_levels``) owns the airside-service
    decision, and this reads its verdict rather than re-deriving it (one
    instrument, one population)."""
    from auto_patch.layout import ROLE_BUILDING
    cps = layout.canonical_points
    out: list = []
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        idx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
               for (x, y) in ring]
        idx = [i for i in idx if i is not None]
        if not idx:
            continue
        if any(i in building_seats for i in idx):
            continue                        # airside-served → seated
        out.append((s, sorted(set(idx))))
    return out


#: Shape roles whose law edges constitute AIRSIDE FRONTAGE for a building
#: (owner ruling 2026-08-06, "Frontage coupling ⇒ band seating").  A
#: building chord to one of these is the frontage relationship the apron
#: has to grade smoothly to; groundside lots and service roads are NOT —
#: a building that only abuts those is the pure groundside citizen the
#: ruling exempts.
_FRONTAGE_AIRSIDE_FAMILY_PREFIXES = (
    "unified:apron", "unified:junction", "unified:runway",
    "unified:primary_parallel", "unified:secondary_parallel",
    "unified:stub", "unified:cross_connector", "unified:taxiway",
    "unified:graded_strip",
)


def detached_pad_frontage_coupling(pads, unified_graph, near_miss_edges=None):
    """``{pad_ordinal: ((partner_node, budget_m), ...)}`` — each detached
    pad's FRONTAGE COUPLING to airside, or an absent entry when it has
    none.

    OWNER RULING 2026-08-06 ("Frontage coupling ⇒ band seating"): *"A
    building close enough to have frontage and be coupled with the apron
    has to be seated based on the route graph that allows the apron to
    grade smoothly to its frontage within the apron's grade law."*  The
    ruling also re-keys the band withholding itself: it keys on FRONTAGE
    COUPLING, not on touch.

    Two couplings count, and the ruling names both:

    * TOUCHING — the pad's ring node carries a law chord owned by an
      airside pavement shape (``_FRONTAGE_AIRSIDE_FAMILY_PREFIXES``).
      That chord IS the frontage chord: the unified graph mints it from
      the owning shape's own all-pair law.
    * NEAR-MISS — the pad↔apron edge the near-miss frontage law mints
      across a sub-metre unpaved sliver
      (:func:`near_miss_building_frontage_edges`).  Ruling item 3 names
      this as the half-landed law: the EDGE was minted without extending
      the SEAT derivation.  This function is that missing half's input.

    The budget carried back is the edge's own — the apron cap over the
    chord — so the caller can price exactly how far off the partner's
    band the pad may lawfully sit.  Tightest budget wins on a duplicate
    pair, the same rule the projection applies.

    Pure lookup over edge lists already built; no geometry pass.
    """
    pad_of: dict = {}
    for ordinal, (_s, idx) in enumerate(pads):
        for i in idx:
            pad_of[i] = ordinal
    if not pad_of:
        return {}
    out: dict = {}

    def _note(ordinal, partner, budget):
        if budget is None or budget < 0:
            return
        row = out.setdefault(ordinal, {})
        prev = row.get(partner)
        if prev is None or budget < prev:
            row[partner] = float(budget)

    edges = getattr(unified_graph, "edges", None) or ()
    families = getattr(unified_graph, "edge_family", None) or ()
    for (a, b, cap, _sp), fam in zip(edges, families):
        if not str(fam).startswith(_FRONTAGE_AIRSIDE_FAMILY_PREFIXES):
            continue
        pa, pb = pad_of.get(a), pad_of.get(b)
        if (pa is None) == (pb is None):
            continue                    # both pad nodes, or neither
        pos = getattr(unified_graph, "pos", {})
        if a not in pos or b not in pos:
            continue
        from auto_patch import grade_graph as _GGf
        budget = cap.at(_GGf._dist(pos[a], pos[b]), 0.0)
        if pa is not None:
            _note(pa, b, budget)
        else:
            _note(pb, a, budget)
    for (apron_node, pad_node, budget) in (near_miss_edges or ()):
        ordinal = pad_of.get(pad_node)
        if ordinal is not None:
            _note(ordinal, apron_node, budget)
    return {k: tuple(v.items()) for k, v in out.items()}


def withhold_airside_band_from_detached_pads(node_band, pads, n=None,
                                             frontage_coupled=None):
    """Hand every detached-pad node ``None`` in ``node_band`` — the AIRSIDE
    reach band is not its law.  Returns ``(withheld_nodes, n_kept_pads)``.

    This was the source fix for the plateau defect attributed above: the
    band floor is what wrote the surrounding airside level onto a pad no
    airside route serves.  ``None`` is the band's own established value
    for "this node's law is elsewhere" — the identical treatment
    ``node_bands(skip_from=...)`` gives adjacent-ground zone vertices.

    CYCLE-7 FIX 2, OWNER RULING 2026-08-06: the withholding KEYS ON
    FRONTAGE COUPLING, NOT ON TOUCH.  The unconditional form was
    over-broad — HECA's ``building172`` carries an ordinary 1 %-cap apron
    chord (budget 0.0646 m over 6.46 m) and still had its band withheld,
    which left it seated on a groundside/DEM datum at 1.6576 m against an
    apron banded from 62.495 m: a permanent clamp/sweep 2-cycle worth
    60.772738 m, the worst residual in the whole solve.  A pad WITH
    frontage coupling keeps its band and is seated from it
    (:func:`seat_detached_pads_by_law`); only a pad with NO frontage
    coupling is the pure groundside citizen the ruling exempts — it seats
    at DEM, terraces freely and affects nothing airside.

    ``frontage_coupled=None`` restores the unconditional pre-ruling
    behaviour (no coupling information ⇒ nothing can be exempted).
    """
    limit = len(node_band) if n is None else min(n, len(node_band))
    withheld: set = set()
    kept = 0
    for ordinal, (_s, idx) in enumerate(pads):
        if frontage_coupled and frontage_coupled.get(ordinal):
            kept += 1
            continue                    # frontage-coupled: the band IS its law
        for i in idx:
            if 0 <= i < limit:
                node_band[i] = None
                withheld.add(i)
    return withheld, kept


def _foot_on_ring(px, py, coords):
    """``(t, ia, ib, d)`` — the nearest point on a closed ring polyline to
    ``(px, py)``: the bracketing vertex INDEXES into ``coords`` (open
    ring), the segment parameter, and the distance.  ``None`` for a
    degenerate ring."""
    n = len(coords)
    if n < 2:
        return None
    best = None
    for a in range(n):
        b = (a + 1) % n
        ax, ay = coords[a]
        bx, by = coords[b]
        vx, vy = bx - ax, by - ay
        vv = vx * vx + vy * vy
        if vv <= 1e-12:
            t = 0.0
            fx, fy = ax, ay
        else:
            t = ((px - ax) * vx + (py - ay) * vy) / vv
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            fx, fy = ax + t * vx, ay + t * vy
        d = math.hypot(px - fx, py - fy)
        if best is None or d < best[3]:
            best = (t, a, b, d)
    return best


def detached_pad_law_box(layout, bucket_to_idx, elev, pad_shape, pad_idx,
                         cap, contact_m=None):
    """``(lo, hi, n_contacts, n_conflict)`` — the lawful FLAT levels of one
    detached pad, from SOLVED host-pavement variables only.

    For every pad ring vertex the march finds the nearest point on a
    neighbouring non-building pavement ring within ``contact_m`` and reads
    the datum as ``(1−t)·elev[a] + t·elev[b]`` — two solved ring variables,
    exactly the adjacent-ground foot rule (and its identity case
    when the pad shares the host's vertex, where ``t`` lands on an end and
    ``d`` is 0).  Each contact contributes ``[datum − cap·d, datum + cap·d]``
    and the box is their INTERSECTION.

    An EMPTY intersection is a DECLARED CONFLICT, never silently resolved:
    it is the split-level-seat law's trigger (RULINGS 2026-08-04 — a pad
    whose contacts cannot all be met by one flat level needs sectioning).
    As the retired zone box did, the first claimant's box is kept and
    the conflict is counted for the caller to report.

    ``(None, None, 0, 0)`` when no host resolves — NO BOX, not a DEM
    fallback."""
    cps = layout.canonical_points
    contact = (DETACHED_PAD_HOST_CONTACT_M if contact_m is None
               else float(contact_m))
    poly = pad_shape.polygon
    # BBOX PREFILTER before the shapely distance: a big airport carries
    # thousands of candidate-role shapes and this runs per pad, so the
    # exact test is only paid by the handful that could possibly touch.
    p_minx, p_miny, p_maxx, p_maxy = poly.bounds
    p_minx -= contact
    p_miny -= contact
    p_maxx += contact
    p_maxy += contact
    hosts = []
    for h in layout.shapes:
        if h.role not in _detached_pad_host_roles():
            continue
        if h.polygon is None or h.polygon.is_empty or h is pad_shape:
            continue
        h_minx, h_miny, h_maxx, h_maxy = h.polygon.bounds
        if (h_minx > p_maxx or h_maxx < p_minx
                or h_miny > p_maxy or h_maxy < p_miny):
            continue
        try:
            if poly.distance(h.polygon) > contact:
                continue
        except Exception:                              # pragma: no cover
            continue
        hcoords = _open_ring(list(h.polygon.exterior.coords))
        if len(hcoords) < 2:
            continue
        hidx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                for (x, y) in hcoords]
        hosts.append((hcoords, hidx))
    if not hosts:
        return None, None, 0, 0

    n_elev = len(elev)
    lo = hi = None
    n_contacts = n_conflict = 0
    ring = _open_ring(list(poly.exterior.coords))
    for (px, py) in ring:
        best = None
        for (hcoords, hidx) in hosts:
            foot = _foot_on_ring(px, py, hcoords)
            if foot is None:
                continue
            t, ia, ib, d = foot
            if d > contact:
                continue
            i_a, i_b = hidx[ia], hidx[ib]
            if i_a is None or i_b is None or i_a >= n_elev or i_b >= n_elev:
                continue
            datum = (1.0 - t) * elev[i_a] + t * elev[i_b]
            if best is None or d < best[1]:
                best = (float(datum), float(d))
        if best is None:
            continue
        datum, d = best
        n_contacts += 1
        c_lo, c_hi = datum - cap * d, datum + cap * d
        if lo is None:
            lo, hi = c_lo, c_hi
            continue
        n_lo, n_hi = max(lo, c_lo), min(hi, c_hi)
        if n_lo > n_hi:
            n_conflict += 1                 # declared, first claimant kept
            continue
        lo, hi = n_lo, n_hi
    if lo is None:
        return None, None, 0, 0
    return lo, hi, n_contacts, n_conflict


def frontage_band_seat_interval(pad_idx, coupling, node_band):
    """``(lo, hi, n_couplings)`` — the flat levels the FRONTAGE BAND admits
    for one detached pad, or ``(None, None, 0)`` when nothing resolves.

    CYCLE-7 FIX 2, and the measurement that forced it.  A detached pad's
    seat box is built by ``detached_pad_law_box``'s CONTACT MARCH, whose
    horizon is ``DETACHED_PAD_HOST_CONTACT_M`` = 2.5 m.  The LAW GRAPH has
    no such horizon: HECA's ``building172`` sits 6.46 m from apron node
    5037 and carries an ordinary 1 %-cap law edge to it (budget 0.0646 m)
    — outside the march, inside the law.  The march therefore saw only
    groundside pieces at d ≈ 0, minted the box ``[datum, datum]`` (ZERO
    WIDTH, at 1.6576 m in a DEM ≡ 1 world), and the projection then had a
    groundside/DEM datum installed as a HARD bound on an airside apron
    edge whose own band floors at 62.495 m.  Every sweep moved both ends
    by ±30.4 m and the clamps restored them exactly: a permanent 2-cycle,
    residual 60.772738 m, bit-identical at sweep 1 and at sweep 49,600 —
    100 % of the worst residual in the whole HECA solve, and invisible to
    any amount of convergence work.

    That box violates two standing rulings at once — "DEM is a seed,
    never a constraint" and "groundside must never pull airside" — and
    cycle-6 Part P's band-wins door does not cover it, because the pad
    has no band AT ALL (``withhold_airside_band_from_detached_pads``
    hands every detached pad ``None``).

    THE LAW THIS FUNCTION STATES (owner ruling 2026-08-06, "Frontage
    coupling ⇒ band seating"): *"A building close enough to have frontage
    and be coupled with the apron has to be seated based on the route
    graph that allows the apron to grade smoothly to its frontage within
    the apron's grade law."*  Read forward, that is arithmetic: a pad
    coupled to a banded partner by a frontage chord of budget ``B`` may
    lawfully sit anywhere in ``[band_lo − B, band_hi + B]`` — any level
    in there lets the chord grade within the apron's own law to some
    in-band partner value — and the pad's seat is the INTERSECTION of
    that over all its frontage couplings.

    ONE band (``reach_band_unified``) is the authority for a partner's
    lawful range — never its current VALUE, which is a solve state and
    not a law.  ``coupling`` is the pad's frontage set from
    :func:`detached_pad_frontage_coupling`, which has already excluded
    intra-pad pairs (a rigid flat group cannot constrain its own level).

    An EMPTY intersection (``lo > hi``) means two frontage couplings no
    single flat level can meet — the SPLIT-LEVEL SEAT law's trigger
    (RULINGS 2026-08-04), reported LOUD by the caller, never silently
    resolved.  ``n_couplings == 0`` with a non-empty ``coupling`` means
    the frontage band could not be DERIVED (no banded partner): also
    loud, and never a fallback to the DEM datum pin.
    """
    lo = hi = None
    n_couplings = 0
    for (j, budget) in coupling or ():
        band = node_band[j] if 0 <= j < len(node_band) else None
        if band is None or band[0] is None or band[1] is None:
            continue
        n_couplings += 1
        b_lo = float(band[0]) - float(budget)
        b_hi = float(band[1]) + float(budget)
        lo = b_lo if lo is None else max(lo, b_lo)
        hi = b_hi if hi is None else min(hi, b_hi)
    if not n_couplings:
        return None, None, 0
    return lo, hi, n_couplings


def seat_detached_pads_by_law(layout, bucket_to_idx, elev, pads, cap,
                              frontage_coupled=None, node_band=None):
    """Seat every detached pad FLAT at the law level nearest its seed.

    Runs AFTER the groundside passes (``apply_groundside_reach`` /
    ``apply_service_road_dem_follow``), because a groundside object's datum
    is a SOLVED groundside variable and groundside conforms to airside —
    the pad is therefore the last thing seated, which is the architectural
    order, not a convenience.

    Writes ``elev`` for the pad's ring nodes, registers the lawful box in
    the ``seat_boxes`` node-space store (the ratified bounded-yield channel
    — the pad then rides fp#8's and the final projection's group bounds
    with no new machinery), and returns
    ``({node_idx: level}, stats)`` with ``stats = (n_seated, n_unhosted,
    n_conflict)``.

    NOT HARD.  The pad joins the ordinary movable FLAT pad groups — it is a
    building, flatness is its law, and its box is what keeps it lawful.
    The deleted DEM pin's ``layout._detached_pad_node_idx`` exclusion
    existed only to protect a value the law did not choose.

    ``frontage_coupled`` / ``node_band`` — CYCLE-7 FIX 2, OWNER RULING
    2026-08-06 ("Frontage coupling ⇒ band seating").  A pad that carries
    a FRONTAGE COUPLING (touching or near-miss) is not a groundside
    citizen at all: it is seated FROM THE ROUTE-GRAPH BAND through its
    frontage chord (:func:`frontage_band_seat_interval`), and **no
    DEM-datum value may be a bound on it** — the contact box is not
    intersected in, it is not consulted, it is simply not its law.  DEM
    still chooses WHERE inside the derived range, which is the standing
    seed-not-bound rule.

    A frontage-coupled pad whose band interval cannot be DERIVED (no
    banded partner) or is EMPTY (two couplings no single flat level
    meets) is a LOUD DEFECT REPORT, and the pad is left UNBOUNDED on its
    seed — never falling back to the datum pin, which is the failure this
    fix exists to delete.  An empty interval is additionally the
    split-level sectioned-seat law's trigger (RULINGS 2026-08-04), which
    remains the relief for large intra-footprint relief.

    Omit either argument and no pad is treated as frontage-coupled, which
    is exactly the pre-ruling behaviour.

    Returns ``stats = (n_seated, n_unhosted, n_conflict, n_frontage_seated,
    n_frontage_underivable, n_split_level)``."""
    seats: dict = {}
    boxes = _store_of(layout).open_map("seat_boxes", "interval")
    cps = layout.canonical_points
    n_seated = n_unhosted = n_conflict = 0
    n_frontage = n_underivable = n_split = 0
    reconcile = frontage_coupled is not None and node_band is not None
    for ordinal, (s, idx) in enumerate(pads):
        coupling = (frontage_coupled or {}).get(ordinal) if reconcile else None
        if coupling:
            # ── THE FRONTAGE-COUPLED PATH: the band is its law ────────
            f_lo, f_hi, n_cpl = frontage_band_seat_interval(
                idx, coupling, node_band)
            if not n_cpl:
                n_underivable += 1      # LOUD; unbounded on its seed
                continue
            if f_lo > f_hi:
                n_split += 1            # LOUD; unbounded on its seed
                continue
            lo, hi = f_lo, f_hi
            n_frontage += 1
        else:
            lo, hi, n_c, n_x = detached_pad_law_box(
                layout, bucket_to_idx, elev, s, idx, cap)
            n_conflict += n_x
            if lo is None:
                n_unhosted += 1             # no datum → no box, no write
                continue
        vals = [elev[i] for i in idx if i < len(elev)]
        if not vals:
            continue
        seed = sum(vals) / len(vals)        # the DEM-seeded free value
        level = min(max(seed, lo), hi)      # DEM picks WHERE in the box
        for i in idx:
            if i < len(elev):
                elev[i] = level
                seats[i] = level
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            k = cps.get_or_add(float(x), float(y))
            prev = boxes.get(k)
            boxes[k] = ((lo, hi) if prev is None
                        else (max(prev[0], lo), min(prev[1], hi)))
        n_seated += 1
    return seats, (n_seated, n_unhosted, n_conflict,
                   n_frontage, n_underivable, n_split)


def _pocs_project_levels(targets, boxes, pairs, max_iter=300, tol=1e-4):
    """Project per-item target levels onto (box ∩ pairwise-coupling polytope).

    Find ``L_i`` minimising ``Σ(L_i − t_i)²`` s.t. ``|L_i − L_j| ≤ pairs[(i,j)]``
    and ``f_i ≤ L_i ≤ ce_i``.  Cyclic projection (POCS): push each violated pair
    together by half the excess, then re-clamp to the boxes; repeat.  Returns
    ``[L_i]`` on convergence, or ``None`` when the polytope is EMPTY (boxes
    incompatible with the couplings = the FUNDAMENTAL case)."""
    n = len(targets)
    L = [min(max(targets[i], boxes[i][0]), boxes[i][1]) for i in range(n)]
    for _ in range(max_iter):
        worst = 0.0
        for (i, j), lim in pairs.items():
            d = L[i] - L[j]
            if d > lim:
                e = 0.5 * (d - lim)
                L[i] -= e
                L[j] += e
                worst = max(worst, d - lim)
            elif -d > lim:
                e = 0.5 * (-d - lim)
                L[i] += e
                L[j] -= e
                worst = max(worst, -d - lim)
        for i in range(n):
            L[i] = min(max(L[i], boxes[i][0]), boxes[i][1])
        if worst <= tol:
            break
    ok = all(abs(L[i] - L[j]) <= lim + 1e-3
             for (i, j), lim in pairs.items())
    return L if ok else None


def _project_apron_contacts(targets, boxes, positions, cap,
                            max_iter=300, tol=1e-4):
    """Project per-feeder target levels onto (box ∩ apron-cap polytope):
    ``|L_i − L_j| ≤ cap·d_ij`` with ``d_ij`` = straight gap (a LOWER bound on
    the in-apron route, so the cap constraint is conservative).  See
    :func:`_pocs_project_levels` for the projection itself."""
    import math
    n = len(targets)
    pairs = {(i, j): cap * math.hypot(positions[i][0] - positions[j][0],
                                      positions[i][1] - positions[j][1])
             for i in range(n) for j in range(i + 1, n)}
    return _pocs_project_levels(targets, boxes, pairs,
                                max_iter=max_iter, tol=tol)


# Minimum apron area to ANCHOR a no-building apron (user 2026-06-30).  A
# sub-threshold apron is a decomposition fragment of a larger apron-blob, not a
# real expanse; pinning it to its DEM-feasible level over-constrains the network
# for no benefit, so it is left to flex with its feeders instead.  This replaces
# the old apron→junction demotion (which mutated role purely to dodge anchoring
# and broke the junction invariants on non-HECA airports).
_NOBUILD_APRON_SEAT_MIN_AREA_M2 = 2000.0


# ── APRON-CONTACT ANCHOR CAP — STANDING LAW ───────────────────────
# (seed-fix round §3; former gate ``O4_APRON_CONTACT_ANCHOR_CAP``, retired
# 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG".)
#
# THE LAW.  :func:`build_nobuilding_apron_seats` prices every feeder
# contact against the HARD RUNWAY/SEAM ANCHORS on the SAME spine graph
# phase A projects on (``law_graph_budget.build_anchor_envelope``), and the
# silent clamp-up is gone: a DEM target clamped into the band by more than
# the materiality floor is REPORTED, and an EMPTY band ∩ envelope is
# reported as the contradiction it is.
#
# THE DEFECT IT CLOSES (HECA, measured from the phase-A npz).  Feeder
# 2861's DEM is 60.200; it is clamped UP into a band floor of 62.119 and
# then PROJECTED to 65.749 by a polytope whose only cap constraints are
# feeder↔feeder at straight gap — with NO constraint against hard runway
# anchor 2863, which sits at 60.790 only 0.1928 m of route budget away.
# The seat is then stamped immovable, and the phase-A projection burns
# 3983 sweeps on an anchor pair that cannot both hold (residual 4.766 m).
# An anchor 0.19 m of budget away is not a distant consideration; it is
# the binding constraint.
#
# OLD-WORLD MEASURED COST: one severity item at +1.27 (recorded when the
# gate was flipped in the pre-composed world).  DEBUG-PHASE TARGET — noted,
# not a reason to keep the gate.
#
# The law is INACTIVE only where it has no input: ``anchor_envelope=None``
# means the caller holds no hard anchors on the spine graph, and an
# envelope that does not exist cannot bound anything.


def build_nobuilding_apron_seats(layout, bucket_to_idx, band, dem_fn,
                                 anchor_envelope=None, icao=""):
    """``{feeder_contact_node_idx: feasible_level}`` for every NO-BUILDING apron —
    the FEEDER-CONVERGENCE rule (user 2026-06-26 directive #3; tilt model
    2026-06-28).

    A no-building apron has no pad to anchor it, so its feeder taxiways each grade
    to their own DEM-driven level and can arrive INCOMPATIBLE (the ``route_reach``
    violation: feeder contacts whose elevation gap exceeds the apron cap over their
    separation).  Rather than force the apron FLAT (one level for all feeders, which
    over-constrains and wastes the apron's own grade budget), anchor EACH feeder
    contact at the level feasible THERE — its reach band, biased to DEM — projected
    onto the apron-cap polytope so the apron TILTS ≤cap between contacts:

        minimise Σ(L_i − t_i)²  s.t.  |L_i − L_j| ≤ cap·d_ij  and  f_i ≤ L_i ≤ ce_i

    (:func:`_project_apron_contacts`).  ``t_i = clamp(DEM_i, band_i)`` pulls a feeder
    floating ABOVE its reach band back down to a reachable level; the projection
    then shares the apron's cap so close feeders need not be equal, only gradeable.
    A solution clears ``route_reach`` BY CONSTRUCTION (the constraints ARE its
    condition); an EMPTY polytope (a feeder's band can't reconcile with another's
    across the cap) is FUNDAMENTAL → skipped (documented transition, not a gate).

    Aprons that abut a building are skipped (the pad anchors the level).  The caller
    (``solve.py``) ANCHORS the returned ``{contact_node: L_i}`` like a building seat
    (heaviest), so the feeder SPINES grade to meet the apron (user 2026-06-28 — the
    apron must anchor for the spines to adjust to it; a SOFT ``node_band`` clamp let
    whatever pinned a feeder win and didn't converge).  Only the per-feeder CONTACTS
    are anchored — at their OWN reachable level — so the apron body still flexes and
    the feeder reaches L_i without an over-cap step (the earlier FLAT whole-ring seat
    forced unreachable levels → regressed ``cyxy_spine_zero`` + HECA runway).  Gate

    ``anchor_envelope`` (seed-fix round §3, STANDING LAW) — a
    ``law_graph_budget.AnchorEnvelope`` over the HARD runway/seam anchors
    on the SAME spine graph phase A projects on.  Each feeder's box is
    intersected with its envelope, which is the EXACT intersection of the
    cap constraints ``|L_i − v_a| ≤ d(a, i)`` over every hard anchor
    within reach (the anchor values are FIXED, so each such constraint is
    an interval on ``L_i``).  Two things follow, both required by the
    spec: a feeder can no longer be projected metres away from a runway
    truth it is centimetres of budget from; and the DEM target's clamp
    into the band stops being SILENT — a clamp beyond the materiality
    floor is reported with the bound that demanded it, and an EMPTY box
    (band ∩ envelope) is reported as the contradiction it is instead of
    being skipped without a word.  ``None`` ⇒ the caller holds no hard
    anchors on the spine graph, so there is no envelope to intersect."""
    import os as _os
    _cap_on = anchor_envelope is not None
    _clamp_rows: list = []
    _empty_rows: list = []
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION
    from auto_patch.config import APRON_MAX_GRADE
    cps = layout.canonical_points
    buildings = [b.polygon for b in layout.shapes
                 if b.role == ROLE_BUILDING and b.polygon is not None
                 and not b.polygon.is_empty]
    # The taxi-network shapes whose contact feeds an apron (the SAME set
    # ``route_reach_violations`` measures): corridor junctions, not SVC
    # (the rect roles are retired, owner 2026-07-29).
    route_roles = {ROLE_JUNCTION}
    routes = [t for t in layout.shapes
              if t.role in route_roles and t.polygon is not None
              and not t.polygon.is_empty
              and not str(t.ref or "").upper().startswith("SVC")]
    seats: dict = {}
    for s in layout.shapes:
        if (s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty):
            continue
        if s.polygon.area <= _NOBUILD_APRON_SEAT_MIN_AREA_M2:
            continue            # too small to anchor — flexes with its feeders
        if any(s.polygon.distance(b) < 1.0 for b in buildings):
            continue                            # a building anchors the level
        # Each feeder's CONTACT = its nearest vertex to the apron (what route_reach
        # measures), with its reach band + DEM-biased target.
        idxs, tgts, boxes, poss, keys = [], [], [], [], []
        for t in routes:
            if t is s or s.polygon.distance(t.polygon) > 1.5:
                continue
            best = None
            for (x, y) in _open_ring(list(t.polygon.exterior.coords)):
                d2 = s.polygon.exterior.distance(Point(x, y))
                if best is None or d2 < best[0]:
                    best = (d2, (x, y))
            if best is None:
                continue
            px, py = best[1]
            b = band(px, py)
            if b is None:
                continue
            k = cps.get_or_add(float(px), float(py))
            i = bucket_to_idx.get(k)
            if i is None:
                continue
            de = dem_fn(px, py)
            tgt = de if de is not None else 0.5 * (b[0] + b[1])
            # ── §3: the anchor-cap box + the LOUD clamp ────────────────
            if _cap_on:
                env = anchor_envelope.box(i)
                if env is not None:
                    lo_b = max(float(b[0]), float(env[0]))
                    hi_b = min(float(b[1]), float(env[1]))
                    if lo_b > hi_b:
                        # band ∩ hard-anchor envelope is EMPTY.  Report it
                        # (feasibility-is-guaranteed: a contradiction is a
                        # law defect to attribute), and take the ANCHOR
                        # envelope — it is the constraint the phase-A
                        # projection will actually enforce, and seating
                        # inside the band instead is precisely what mints
                        # the immovable-vs-runway pair.
                        _empty_rows.append((i, float(b[0]), float(b[1]),
                                            float(env[0]), float(env[1])))
                        lo_b, hi_b = float(env[0]), float(env[1])
                    b = (lo_b, hi_b)
            clamped = min(max(tgt, b[0]), b[1])
            if _cap_on and abs(clamped - tgt) > 0.01:
                _clamp_rows.append((i, float(tgt), float(clamped),
                                    float(b[0]), float(b[1])))
            idxs.append(i)
            tgts.append(clamped)
            boxes.append(b)
            poss.append((px, py))
            keys.append(k)
        if len(idxs) < 2:
            continue
        L = _project_apron_contacts(tgts, boxes, poss, APRON_MAX_GRADE)
        if L is None:
            continue                            # fundamental → documented transition
        # BOUNDED YIELD box (owner ruling 2026-07-29): a contact seat's box
        # is the band interval that seated it (``band(x, y)`` at the contact
        # — the same lookup), widened to include the projected level (POCS
        # keeps ``L_i`` in-box; the widen is a no-op guard).  Keyed by
        # CANONICAL KEY (see ``build_building_seats``); merged into the
        # registry that function reset (it runs first).
        seat_boxes = _store_of(layout).open_map("seat_boxes", "interval")
        for i, Li, b, k in zip(idxs, L, boxes, keys):
            seats[i] = float(Li)
            blo = min(float(b[0]), float(Li))
            bhi = max(float(b[1]), float(Li))
            prev = seat_boxes.get(k)
            seat_boxes[k] = ((blo, bhi) if prev is None
                             else (max(prev[0], blo), min(prev[1], bhi)))
    if _cap_on:
        _report(f"  [apron-contact] {icao or 'airport'}: hard-anchor cap ON "
                f"({anchor_envelope.anchor_count} anchor(s) over "
                f"{anchor_envelope.node_count} spine node(s)); "
                f"{len(_clamp_rows)} DEM target(s) clamped by >0.01 m, "
                f"{len(_empty_rows)} feeder box(es) EMPTY "
                f"(band vs hard-anchor envelope).")
        for (i, lo_band, hi_band, lo_env, hi_env) in _empty_rows[:10]:
            _report(f"  [apron-contact]   node {i}: band "
                    f"[{lo_band:.3f}, {hi_band:.3f}] does not meet the "
                    f"hard-anchor envelope [{lo_env:.3f}, {hi_env:.3f}] — "
                    f"seated against the ENVELOPE (the constraint phase A "
                    f"enforces); attribute the band.")
        for (i, tgt, clamped, lo_b, hi_b) in sorted(
                _clamp_rows, key=lambda r: -abs(r[2] - r[1]))[:10]:
            _report(f"  [apron-contact]   node {i}: DEM target {tgt:.3f} "
                    f"clamped to {clamped:.3f} ({clamped - tgt:+.3f} m) by "
                    f"box [{lo_b:.3f}, {hi_b:.3f}].")
    return seats


# NEAR-MISS building-frontage recognition tolerance (2026-07-08).  A DSF
# building-pad outline and the apt.dat apron edge it fronts can be offset by a
# sub-metre source mismatch (SPJC building29 vs its SW apron: 0.68 m measured),
# leaving a thin unpaved sliver that defeats EVERY exact-identity reconciler
# (pre-solve weld, stitch_pavement_to_terminals, the 2-dp frontage-key match) —
# all of which correctly key off ``SHARED_VERTEX_TOL_M`` (0.5 m, the ONE
# canonical identity; never widened per the solver+validator single-registry
# ruling).
#
# THE VALUE NOW LIVES IN ``config.py`` — the standards single source — taking
# this constant's own standing TODO (cycle-5 instrument-fix item 6).  It had to
# move the moment the law grew a SECOND reader: ``tools/check_grade``'s
# ``frontage_near_miss`` census family judges emitted patches against exactly
# this radius and this budget, and a rule value read from a solver-internal
# module is the two-copies defect the lockstep standard forbids.  Re-exported
# here under its historical name so every existing reader (and
# ``tests/test_building_frontage_near_miss.py``) is unaffected.
from auto_patch.config import (                            # noqa: E402
    BUILDING_FRONTAGE_NEAR_MISS_M,                         # noqa: F401
    SVC_PROFILE_REVERSAL_MIN_M,                            # noqa: F401
    near_miss_frontage_budget as _near_miss_frontage_budget)


def near_miss_building_frontage_floors(layout, bucket_to_idx, band,
                                       building_seats):
    """``{apron_node_idx: floor_level}`` for soft-pavement edges that face a
    building pad across a NEAR-MISS gap — so the pavement grades UP to the flat
    pad instead of cliffing ~0.5–1 m below it across a thin unpaved sliver.

    THE DEFECT (SPJC pavement_grade step gate, 2026-07-08): building29's flat
    pad (seat 25.56) runs parallel to a large apron 0.68 m away at ~24.9 — a
    0.66 m visible step.  The 0.68 m source offset (DSF pad outline vs apt.dat
    apron edge) is just over ``SHARED_VERTEX_TOL_M`` (0.5 m), so no vertices
    are shared: the pre-solve weld and ``stitch_pavement_to_terminals`` never
    fire, the pad's frontage-seat recognition (exact 2-dp key match in
    ``build_building_seats``) never sees the edge, and
    ``build_nobuilding_apron_seats`` SKIPS the apron ("a building anchors the
    level" — within 1 m of a pad) even though the pad anchors nothing there.
    The apron falls through every regime and solves to its own low DEM.

    THE FIX is raise-biased and value-side only, and it is per-EDGE: the
    solve-time ring is SPARSE along a long frontage (SPJC's apron faces the
    90 m pad with one 49 m straight edge whose endpoints sit 1.5 m and 10 m
    away — no ring vertex lies inside any sub-metre radius; the near-pad OSM
    vertices are post-solve planarize/T-weld inserts that INTERPOLATE along
    that edge).  So the value-controlling nodes are the near-miss edge's
    ENDPOINTS.  For every soft-pavement ring edge whose segment passes within
    ``BUILDING_FRONTAGE_NEAR_MISS_M`` of a pad and whose endpoints are BOTH
    canonically unshared with the pad (a true near-miss run — an edge with a
    pad-shared endpoint is already reconciled by weld/stitch/seat identity
    and legitimately grades away from the seat), floor BOTH endpoints at
    ``seat − APRON_MAX_GRADE·d`` with ``d`` each endpoint's own distance to
    the pad (the building↔apron law: the level the pavement must reach to
    grade ≤cap up to the flat pad; the floor decays at the apron-law rate, so
    a far endpoint gets a proportionally lower floor and the interpolated
    near-pad run lands at ~seat), clamped to the endpoint's reach-band
    ceiling so it stays runway-reachable.  ORDERING: the pad seat is read from
    ``building_seats`` AS ALREADY CHOSEN by ``build_building_seats`` (seats +
    POCS coupling run first; ``solve.py`` calls this afterwards, before the
    no-building apron seats merge) — the near-miss edge must NEVER feed the
    pad's ``_frontage_box`` ceiling, so the pad seat cannot be pulled DOWN by
    the lower apron (which would just move the step to the pad's other,
    genuinely-shared frontage).  SOFT floors through the one ``spine_floor``
    channel (never hard seats): one raise-biased regime the solver resolves
    with its neighbour cap slabs — per-vertex hard anchors from a second
    regime are the documented unresolvable-tear pattern.  Feasibility is not
    at risk: floors are ≤ seat by construction (cap·d ≥ 0), decay at the
    apron-law rate, and are band-ceiling-clamped.

    STANDING LAW (former gate ``O4_BUILDING_FRONTAGE_NEAR_MISS``, retired
    2026-08-05); recognition is unconditional (was: no floors,
    byte-identical)."""
    from auto_patch.config import APRON_MAX_GRADE
    floors: dict = {}
    for contact in _near_miss_frontage_contacts(layout, bucket_to_idx,
                                                building_seats):
        (i, _pad_node, d, seat, x, y, _soft) = contact
        floor_level = seat - APRON_MAX_GRADE * d    # ≤ seat by construction
        bnd = band(x, y)
        if bnd is not None:                         # stay runway-reachable
            floor_level = min(floor_level, bnd[1])
        if floor_level > floors.get(i, -_INF):
            floors[i] = float(floor_level)
    return floors


def near_miss_building_frontage_edges(layout, bucket_to_idx, building_seats,
                                      weld_refs_out=None, stage_out=None):
    """``[(apron_node_idx, pad_node_idx, budget_m)]`` — the near-miss frontage
    relationship as LAW EDGES for the joint feasibility projections.

    The floors above shape phases A/B, but every ``feasibility_project`` pass
    (cap edges only, floors unknown) resolves by MINIMUM DISPLACEMENT — one
    floor-lifted endpoint against several low free neighbours loses, and the
    lift is projected away before writeback (measured at SPJC: phase B honours
    the floor at 25.30, the first projection pulls it to 25.05, the final
    yield GS lands back at 24.84).  The durable expression of "feature-weld
    needs VALUE AGREEMENT" is therefore an EDGE in the projections' own edge
    set: ``|z(apron_endpoint) − z(pad_node)| ≤ APRON_MAX_GRADE·d`` with ``d``
    the endpoint's distance to the pad polygon (the building↔apron law across
    the sliver).  The pad node is the pad's nearest ring node — pads are hard
    through phases A/B and MOVABLE FLAT GROUPS in the final yield GS, so the
    joint projection settles pad level and apron edge together (min
    displacement, pad stays flat) instead of un-doing the floor.

    Same recognition and gate as :func:`near_miss_building_frontage_floors`
    (STANDING LAW; the former ``O4_BUILDING_FRONTAGE_NEAR_MISS`` gate is gone.)

    ``weld_refs_out`` — PAD ROD COUPLING (owner approval 2026-07-29,
    ``docs/specs/pad-rod-coupling-spec.md``; completes bounded-yield-spec §7.3
    at building faces).  When a dict is passed it is filled with
    ``{apron_node_idx: (pad_seat_level, pad_node_idx)}`` over THIS SAME
    contact set: the §7 reference value (``z_ref``) of a soft-fabric vertex
    welded to a pad face IS the pad's seat, not the fabric's yield-entry state
    (the pad-weld ruling — "airside pavement welds SMOOTH to a building's
    airside face" — and "the seat is the rod for the building").  A vertex
    facing TWO pads takes the NEARER contact (pads may legitimately differ;
    the inter-pad step exemption is unchanged).  The PAD NODE rides along
    because the seat level recorded here is read BEFORE the no-building apron
    seat merge and the groundside/service passes: the value the pad's own §7
    rod holds at yield entry is the one the weld must reference, and the call
    site resolves it through this node (measured 2026-07-29: 21 of 25 HECA
    pads emit off this scalar, by up to 8.7 m — referencing the scalar OPENS
    the frontage it is supposed to weld).  Filled from the ONE recognition
    pass the edges already run — no second geometry sweep, no measurable
    build-time cost."""
    edges: list = []
    nearest: dict = {}          # apron node -> (distance_m, seat, pad_node)
    for contact in _near_miss_frontage_contacts(layout, bucket_to_idx,
                                                building_seats,
                                                log_firings=True):
        (i, pad_node, d, seat, _x, _y, _soft) = contact
        if weld_refs_out is not None:
            prev = nearest.get(i)
            if prev is None or d < prev[0]:
                nearest[i] = (float(d), float(seat), pad_node)
        if pad_node is None:
            continue
        # THE BUDGET, from the law's one authority (config) — the same
        # function ``check_grade._check_frontage_near_miss`` judges with.
        edges.append((i, pad_node, float(_near_miss_frontage_budget(d))))
        # STAGE AT MINT (staged-solve S1b).  These pairs are APPENDED to
        # the unified edge set, which reaches every projection as one
        # untagged entry — so the pair's stage is registered HERE, by the
        # constructor that knows the SOFT SHAPE the frontage belongs to.
        # ``NEAR_MISS_FRONTAGE_SOFT_ROLES`` includes ``service_junction``:
        # a pad↔service-junction frontage is GROUNDSIDE law and must not
        # bind the airside pad in stage A.
        if stage_out is not None:
            from auto_patch.solve_stage import pair_key as _pk
            from auto_patch.solve_stage import stage_of_shape as _sos
            stage_out[_pk(i, pad_node)] = _sos(_soft)
    if weld_refs_out is not None:
        for i, (_d, seat, pad_node) in nearest.items():
            weld_refs_out[i] = (seat, pad_node)
    return edges


def _near_miss_frontage_contacts(layout, bucket_to_idx, building_seats,
                                 log_firings=False):
    """The shared NEAR-MISS recognition (see the two consumers above).

    Yields one contact per (soft-pavement near-miss edge endpoint, pad):
    ``(endpoint_node_idx, nearest_pad_node_idx, distance_to_pad_m,
    pad_seat_level, endpoint_x, endpoint_y)``.  ``log_firings`` prints the
    per-pad firing line (the EDGES consumer passes True — it runs once per
    solve, so each recognized pad↔pavement pair logs once)."""
    from shapely.geometry import LineString, Point
    cps = layout.canonical_points
    near_miss_m = BUILDING_FRONTAGE_NEAR_MISS_M

    # Building pads with a CHOSEN seat (post-coupling), with their canonical
    # ring-node index sets for the shared-vertex (already-reconciled) test.
    pads: list = []       # (shape, pad_node_idx_set, seat_level, ring_nodes)
    for b in layout.shapes:
        if (b.role != ROLE_BUILDING or b.polygon is None
                or b.polygon.is_empty):
            continue
        ring = _open_ring(list(b.polygon.exterior.coords))
        ring_nodes = [((x, y), bucket_to_idx.get(
            cps.get_or_add(float(x), float(y)))) for (x, y) in ring]
        idxs = {i for (_pt, i) in ring_nodes if i is not None}
        seat = next((building_seats[i] for i in idxs
                     if building_seats.get(i) is not None), None)
        if seat is not None:
            pads.append((b, idxs, float(seat), ring_nodes))
    if not pads:
        return

    # The frontage-bearing soft-pavement roles (the same set
    # ``build_building_seats``' frontage recognition keys on) — read from the
    # law's one authority so the census twin
    # (``check_grade._check_frontage_near_miss``) recognizes the same
    # population.  ``tests/test_harness.py`` twin-asserts the tuple still
    # equals ``(ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION)``, which is
    # what makes a ROLE_* rename loud instead of silent.
    from auto_patch.config import NEAR_MISS_FRONTAGE_SOFT_ROLES as soft_roles
    for s in layout.shapes:
        if (s.role not in soft_roles or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = None
        ring_idx = None
        for (pad, pad_idx_set, seat, pad_ring_nodes) in pads:
            if pad.polygon.distance(s.polygon) > near_miss_m:
                continue
            if ring is None:
                ring = _open_ring(list(s.polygon.exterior.coords))
                ring_idx = [bucket_to_idx.get(
                    cps.get_or_add(float(x), float(y))) for (x, y) in ring]
            fired: list = []
            emitted: set = set()
            ring_length = len(ring)
            for edge_start in range(ring_length):
                edge_end = (edge_start + 1) % ring_length
                # A near-miss FRONTAGE edge: passes within the radius, with
                # BOTH endpoints canonically unshared with the pad.  A
                # pad-shared endpoint means identity already reconciles that
                # corner (weld / stitch / seat anchor) and the edge
                # legitimately grades away from the seat — not a near miss.
                if (ring_idx[edge_start] in pad_idx_set
                        or ring_idx[edge_end] in pad_idx_set):
                    continue
                segment = LineString([ring[edge_start], ring[edge_end]])
                if segment.distance(pad.polygon) > near_miss_m:
                    continue
                for endpoint in (edge_start, edge_end):
                    i = ring_idx[endpoint]
                    if (i is None or i in building_seats
                            or (i, id(pad)) in emitted):
                        continue    # unregistered / hard-anchored / done
                    emitted.add((i, id(pad)))
                    x, y = ring[endpoint]
                    point = Point(x, y)
                    d = pad.polygon.distance(point)
                    pad_node = min(
                        (pn for pn in pad_ring_nodes if pn[1] is not None),
                        key=lambda pn: ((pn[0][0] - x) ** 2
                                        + (pn[0][1] - y) ** 2),
                        default=(None, None))[1]
                    if _os.environ.get("O4_NEAR_MISS_DEBUG") == "1":
                        print(f"    [near-miss dbg] node {i} ({x:.1f},{y:.1f})"
                              f" d={d:.2f} seat={seat:.3f}"
                              f" pad_node={pad_node}")
                    fired.append(d)
                    yield (i, pad_node, d, seat, x, y, s)
            if fired and log_firings:
                try:
                    import O4_UI_Utils as _UI
                    _UI.vprint(
                        1, f"  [near-miss frontage] pad "
                        f"{pad.ref or '?'} seat {seat:.2f} <-> "
                        f"{s.role} ({s.polygon.area:.0f} m2) gap "
                        f"{pad.polygon.distance(s.polygon):.2f} m: "
                        f"{len(fired)} edge endpoint(s), d "
                        f"{min(fired):.2f}..{max(fired):.2f} m")
                except Exception:               # pragma: no cover
                    pass


def build_apron_contact_floors(layout, bucket_to_idx, band, dem_fn, building_seats):
    """``{feeder_contact_node_idx: floor_level}`` for taxiways/junctions that meet a
    BUILDING-ANCHORED apron's edge — so the feeder SPINE grades UP to the apron
    instead of the (senior) apron sagging down to the feeder's DEM-low mouth.

    The complement of :func:`build_nobuilding_apron_seats`, which handles ONLY
    no-building aprons (it bails on any apron within 1 m of a building).  A building
    apron is held high by its pad seat, but where the apron edge is FAR from the
    building (beyond ``BUILDING_REACH_CORRIDOR_M``, so the building-frontage spine
    floor never reaches it) a feeder taxiway contacting that edge falls through every
    floor rule and solves to its own low DEM — dragging the apron edge into a cliff
    (OEMA TX8 #275: apron #198 held at 639 by a building 310 m away, TX8 mouth at the
    DEM 629 → a 96 % within-apron step).  This was the documented authority inverted:
    "a taxiway/apron node is apron-owned; the taxi yields", not the reverse.

    The floor is the apron's OWN guaranteed-reachable level at the contact: the apron
    grades ≤ ``APRON_MAX_GRADE`` from each adjacent building seat, so at a contact
    ``d`` metres from a building seated at ``S`` the apron is at least ``S − cap·d``.
    Taking the max over the apron's buildings and clamping to the contact's reach band
    gives the level the feeder must rise to (never above the band ceiling, so it stays
    runway-reachable; never below the band floor).  A FLOOR (not a hard seat) so the
    feeder spine still grades smoothly up from its runway anchor and the apron body
    flexes — the taxi yields UP, the apron keeps its cap.  Gate
    STANDING LAW: the former ``O4_APRON_CONTACT_FLOOR`` gate is gone.

    Also carries the NEAR-MISS building-frontage floors
    (:func:`near_miss_building_frontage_floors`, its own gate) — the same soft
    ``spine_floor`` channel, merged max-wise like every floor."""
    near_miss_floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, band, building_seats)
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION
    from auto_patch.config import APRON_MAX_GRADE
    cps = layout.canonical_points
    cap = APRON_MAX_GRADE

    # Each building's seat level (its pad nodes all share one seat in building_seats)
    # paired with its polygon, for the seat − cap·d reach bound.
    bseats: list = []
    for b in layout.shapes:
        if (b.role != ROLE_BUILDING or b.polygon is None or b.polygon.is_empty):
            continue
        lv = None
        for (x, y) in _open_ring(list(b.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and building_seats.get(i) is not None:
                lv = building_seats[i]
                break
        if lv is not None:
            bseats.append((b.polygon, float(lv)))
    if not bseats:
        return near_miss_floors

    route_roles = {ROLE_JUNCTION}
    routes = [t for t in layout.shapes
              if t.role in route_roles and t.polygon is not None
              and not t.polygon.is_empty
              and not str(t.ref or "").upper().startswith("SVC")]

    floors: dict = dict(near_miss_floors)
    for s in layout.shapes:
        if (s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty):
            continue
        # Only BUILDING-anchored aprons (no-building ones use the seat path above).
        near = [(poly, lv) for (poly, lv) in bseats if s.polygon.distance(poly) < 1.0]
        if not near:
            continue
        for t in routes:
            if t is s or s.polygon.distance(t.polygon) > 1.5:
                continue
            # contact = the feeder vertex nearest the apron (what route_reach measures)
            best = None
            for (x, y) in _open_ring(list(t.polygon.exterior.coords)):
                d2 = s.polygon.exterior.distance(Point(x, y))
                if best is None or d2 < best[0]:
                    best = (d2, (x, y))
            if best is None:
                continue
            px, py = best[1]
            bnd = band(px, py)
            if bnd is None:
                continue
            cpt = Point(px, py)
            # the apron's guaranteed-reachable level here: max_b(seat_b − cap·d_b),
            # i.e. the lowest level the apron still grades to each building within cap.
            reach = max(lv - cap * poly.distance(cpt) for (poly, lv) in near)
            floor = min(max(reach, bnd[0]), bnd[1])         # clamp into reach band
            i = bucket_to_idx.get(cps.get_or_add(float(px), float(py)))
            if i is None:
                continue
            if floor > floors.get(i, -float("inf")):
                floors[i] = float(floor)
    return floors


def node_bands(nodes, band, skip_from=None, skip_idx=None):
    """Per-node ``(floor, ceiling)`` from the one reach band (``None`` off-net).

    ``skip_idx`` (flat-site fast path, docs/specs/flat-site-fast-path-spec.md
    §3): an explicit SET of node indices handed ``None`` instead of a scan —
    the born-at-Z0 nodes used by no shape outside the partition.  Same
    argument as ``skip_from`` below, on a set rather than a threshold: such a
    node is a HARD PIN no pass may move, so nothing ever consumes its band,
    and scanning it is the cost the partition exists to remove.  A node
    SHARED with an ineligible shape is deliberately NOT in the set — that
    shape's own law reads it.  ``None`` ⇒ byte-identical to before.

    ``skip_from`` (Slice B stage B3 performance lever, gated at the call
    site): indices ``>= skip_from`` are the adjacent-ground ZONE nodes —
    graded_strip terrain variables whose value law is a pure per-vertex DEM
    envelope clamp to their host pavement edge (``ROLE_GRADE_LIMITS
    ['graded_strip'] is None`` — no reach coupling), encoded as the zone
    interval edge in ``_build_adjacent_ground_zone_constraints``.  Their reach
    band is NEVER consumed by that law, yet computing it is the KBNA gate-ON
    scaling wall: a zone node sits OFF the pavement net, so ``band()`` takes
    the expensive skeleton-``_fallback`` path (~74 ms/node vs ~12 ms on-net),
    and there are 45k of them (node_bands ≈ 60 min at KBNA, ~55 min of it the
    zone tail).  Handing those nodes ``None`` (off-net, the honest value for a
    terrain vertex) skips the scan.  ``skip_from=None`` restores the
    all-nodes scan (the gate-OFF path, byte-inert).

    CLUSTER AMORTIZATION (Tier 3 wave 1, ``O4_REACH_BAND_CLUSTERS``): when the
    band closure exposes a ``.batch`` method (``building_feasibility.
    reach_band_unified``), the per-node serving-centerline scan — the dominant
    reach-band cost — is amortized across spatial buckets: it runs once per
    bucket and every member the representative's line PROVABLY also serves
    reuses it, computing an EXACT, bit-identical band without its own scan (see
    ``reach_band_unified._batch``).  The result is identical to the per-node
    scan below; only the scan work is shared.  Gate OFF
    (``config.REACH_BAND_CLUSTERS`` off) or a band without ``.batch`` → the
    exact per-node scan, byte-identical.  The env override died 2026-08-05;
    the config constant is the switch."""
    from auto_patch.config import REACH_BAND_CLUSTERS
    batch = getattr(band, "batch", None)
    if batch is not None and REACH_BAND_CLUSTERS:
        return batch(nodes, skip_from, skip_idx)
    if skip_from is None and not skip_idx:
        return [band(x, y) for (x, y) in nodes]
    limit = len(nodes) if skip_from is None else min(skip_from, len(nodes))
    out = [None] * len(nodes)
    for i in range(limit):
        if skip_idx and i in skip_idx:
            continue
        out[i] = band(nodes[i][0], nodes[i][1])
    return out


def _spine_floor_per_node(layout, nodes, bucket_to_idx, building_seats,
                          node_band, spine_adj):
    """``{spine_node_idx: floor}`` — floor EVERY spine node directly from its own
    VISIBLE chord to the nearest spine-facing building edge (user 2026-06-27,
    replacing the single centroid foot).

    For each spine node, take the straight chord to the closest point on each
    building within the frontage corridor; if that chord stays on pavement (a real
    apron path, not across grass / through another building) the node is floored at
    ``seat − 1%·chord`` — the elevation the spine must reach so the apron grades
    ≤1 % up to the flat pad.  A node takes the MAX over the buildings it faces.
    No centroid, no cap-decay propagation: ``seat − 1%·dist`` sampled per node is
    already cap-Lipschitz along the spine (adjacent nodes differ by ≤1 %·spacing ≤
    cap·spacing), so a big terminal's WHOLE frontage lifts the spine, not just one
    foot.  Each floor is clamped to the node's band ceiling (never above what the
    runway route reaches)."""
    from shapely.geometry import Point, LineString
    from shapely.ops import nearest_points
    from auto_patch.config import APRON_MAX_GRADE, VISIBLE_CHORD_CONNECT
    from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
    from auto_patch.layout import ROLE_BUILDING
    from auto_patch.elevation_per_surface.building_feasibility import (
        _pavement_visibility, _VIS_ON_PAV_FRAC)

    cps = layout.canonical_points
    vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None
    # The lift reaches a building over a VISIBLE on-pavement chord at any range up
    # to THE single reach corridor (the visibility gate below, not the distance, is
    # the real limit) — so a building anchors its serving spine even across a wide
    # single apron (CYXY building22 at 219 m).  ONE rule, shared with the seat band.
    corridor = BUILDING_REACH_CORRIDOR_M

    builds = []
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        lv = None
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i in building_seats:
                lv = building_seats[i]
                break
        if lv is not None:
            builds.append((s.polygon, float(lv)))
    if not builds:
        return {}

    floor: dict = {}
    for i in spine_adj:
        if i >= len(nodes):
            continue
        px, py = nodes[i]
        p = Point(px, py)
        best = None
        for (poly, lv) in builds:
            d = poly.distance(p)
            if d > corridor:
                continue
            near = nearest_points(poly, p)[0]   # spine-facing building edge point
            chord = LineString([(px, py), (near.x, near.y)])
            if vis is not None and chord.length > 1e-6 and not vis.contains(chord):
                try:                            # tolerate tiny weld-seam gaps
                    frac = chord.intersection(vis.context).length / chord.length
                except Exception:               # pragma: no cover
                    frac = 0.0
                if frac < _VIS_ON_PAV_FRAC:
                    continue                    # chord leaves pavement → not facing
            t = lv - APRON_MAX_GRADE * d        # 1 % apron from spine up to the pad
            if best is None or t > best:
                best = t
        if best is None:
            continue
        nb = node_band[i] if i < len(node_band) else None
        if nb is not None and best > nb[1]:
            best = nb[1]                        # never above the reachable ceiling
        floor[i] = best
    return floor


def building_spine_floor(layout, nodes, bucket_to_idx, building_seats,
                         node_band, spine_adj):
    """``{spine_node_idx: floor}`` — make the serving spine RISE to serve its
    buildings (user 2026-06-25): the taxi arm exists to serve its pads, so the
    SAME trace that set a building's feasible level anchors the spine at the
    precise elevation it must reach there, and that anchor is GRADED SMOOTHLY
    along the centerline chain ("grade smoothly between anchors").

    User 2026-06-27: the default is now :func:`_spine_floor_per_node` — every
    spine node floored directly from its own visible chord to the spine-facing
    building edge (the centroid foot under-covered large terminals).  The legacy
    centroid/full-frontage-foot path below is kept for A/B
    (the former ``O4_SPINE_FLOOR_PER_NODE`` gate is retired; the per-node
    floor is the standing law and the legacy body is deleted).

    For each airside building, the serving centerline is the one the reach band
    used (``_nearest_visible_centerline`` across the continuous apron — NOT the
    geometric nearest, so the anchor is exactly the point the building was made
    consistent with).  The spine node nearest the building's perpendicular FOOT
    is anchored at ``seat − APRON_MAX_GRADE·dist`` — the elevation the spine needs
    so the apron grades ≤1 % up to the flat pad.

    That foot anchor is then propagated along the CONSECUTIVE centerline chain
    (``spine_adj``, budget ``cap·dist``) as a floor that DECREASES at exactly the
    cap rate: ``floor_j = anchor − capdist(foot → j)``.  This builds the whole
    climbing ramp, and because the floor is cap-Lipschitz along the chain it is
    grade-consistent BY CONSTRUCTION — it can never force a spine grade break, and
    (since every chain node's neighbour is also floored) the solve's "envelope
    yields" fallback no longer drops it.  A single un-propagated floor was dropped
    whenever the foot's flat runway-side neighbour capped it low → the arm stayed
    flat (CYXY ~U12 694.5 vs building19 700.2, 106 m away).  Each floor is clamped
    to the node's band ceiling (never above what the runway route reaches)."""
    return _spine_floor_per_node(
        layout, nodes, bucket_to_idx, building_seats, node_band, spine_adj)

    # THE LEGACY WHOLE-GRAPH SPINE FLOOR was deleted 2026-08-05: the
    # per-node floor is the standing law and the old body was unreachable
    # dead code behind the retired ``O4_SPINE_FLOOR_PER_NODE`` gate.


def apply_groundside_reach(layout, bucket_to_idx, elev, cap):
    """Re-level each groundside piece a service road connects to an apron, to the
    elevation the connector can REACH within the service-road grade cap — so the
    connector grades <=cap instead of ramping steeply to the groundside's raw DEM
    (user 2026-06-27, refining the accept-the-ramp model).

    "After buildings and aprons are anchored, check groundside pieces: if they have
    a service road, and if that road reaches an apron, follow that route to find
    what elevation the groundside can reach within grade and anchor it there.  If it
    has no service roads they just stay DEM."

    The service road that meets a groundside piece may reach the apron through a
    CHAIN of service roads/junctions (an out-and-back route, a yard loop), so the
    binding reference is the connector's OWN apron-ward mouth elevation (already
    solved), not the distant apron: the groundside mouth can sit at most
    ``cap * route_len`` from it (``route_len`` = the binding apron-ward->groundside
    edge).  Whether to re-level at all is gated by APRON REACHABILITY — the piece's
    service road must connect (directly or through the service network) to an apron;
    a groundside-only yard road never re-levels its piece.

    The piece is shifted by a UNIFORM offset (preserving its DEM relief) so its
    mouth(s) sit at the closest-to-DEM reachable level; the connector then grades the
    short climb at <=cap.  A piece reached by several connectors must satisfy them
    ALL (interval INTERSECTION of the per-connector shift bounds).

    Mutates groundside ``node_altitudes`` in place and returns ``(n_relevelled,
    welds)`` where ``welds = {node_idx: shifted_groundside_alt}`` for the mouths of
    the APRON-REACHABLE connectors only (the caller pins ``elev`` to these so the
    connector and groundside emit as one welded node).  A service road that does NOT
    reach an apron is left untouched — its piece stays DEM and its mouth is not
    pinned (the user's "stays DEM" case).  Safe to shift a whole piece because a
    groundside lot shares no nodes with airside (a clearance gap separates them) —
    only the connector mouth, which is welded to the shifted level."""
    import math
    import os as _os
    from auto_patch.layout import (
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_APRON,
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)

    cps = layout.canonical_points

    def _key(x, y):
        return cps.get_or_add(float(x), float(y))

    # apron-owned canonical node keys (a service road TOUCHES the apron here).
    apron_keys: set = set()
    for s in layout.shapes:
        if s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            apron_keys.add(_key(x, y))

    # groundside pieces: per-key DEM altitude (the connector mouth shares a key);
    # plus the UNION of every groundside key (to split a connector's nodes into
    # groundside-mouth vs apron-ward).
    gs_pieces = []
    gs_all_keys: set = set()
    for g in layout.shapes:
        if (g.role != ROLE_GROUNDSIDE_PAVEMENT or g.polygon is None
                or g.polygon.is_empty or not g.node_altitudes):
            continue
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes)
        kalt: dict = {}
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is not None:
                kalt.setdefault(_key(*gcoords[k]), float(galts[k]))
        if kalt:
            gs_pieces.append((g, kalt))
            gs_all_keys |= set(kalt)
    if not gs_pieces:
        return 0, set()

    # Service-road network: each shape's node keys, an apron-touch flag, and an
    # adjacency (two service shapes are adjacent when they share a node key).  BFS
    # from the apron-touching shapes marks every APRON-REACHABLE service shape.
    svc = []                   # [(shape, keyset)]
    for c in layout.shapes:
        if c.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            continue
        if c.polygon is None or c.polygon.is_empty:
            continue
        ks = {_key(x, y) for (x, y) in _open_ring(list(c.polygon.exterior.coords))}
        svc.append((c, ks))
    if not svc:
        return 0, set()
    key_to_svc: dict = {}
    for si, (_c, ks) in enumerate(svc):
        for k in ks:
            key_to_svc.setdefault(k, []).append(si)
    reachable: set = set()
    stack = [si for si, (_c, ks) in enumerate(svc) if ks & apron_keys]
    reachable.update(stack)
    while stack:
        si = stack.pop()
        for k in svc[si][1]:
            for sj in key_to_svc.get(k, ()):
                if sj not in reachable:
                    reachable.add(sj)
                    stack.append(sj)

    from shapely.geometry import Point

    MAX_ROUTE = 90.0           # cap the route distance budgeted (m)
    RAISE_W = 14.0             # half-width of the truck-route corridor to raise

    # ── GROUNDSIDE PIN LAW BOUND (item 3(a); was the §C DEM bound) ───────
    # Measured defect 2026-07-30: ``gs_pin`` anchors sit +7.76 m MEDIAN
    # above their own DEM (max +9.88), and they are independently the floor
    # witness for 4,213 broken nodes.  Mechanism: ``lo = base_elev −
    # cap·route_len − dem_gs`` below caps ``route_len`` at ``MAX_ROUTE``
    # but leaves the LIFT ITSELF unbounded — a high apron launders its own
    # error into a HARD pin that then locks the error in.
    #
    # THE BOUND IS ON THE VALUE, AND ITS DATUM IS THE WELD.  §C answered
    # the defect with "a pin may not exceed its OWN DEM by more than
    # ``cap · MOUTH_ALLOWANCE_M``".  That made raw ground a solver bound,
    # which the 2026-08-05 ruling forbids and which the constant-DEM oracle
    # fails by inspection (DEM ≡ c ⇒ every pin ceilinged at c + 0.75 m, so
    # a lot welding to pavement above that is clamped BELOW its lawful
    # level and emits a violation on ground with no relief).  The datum is
    # now the surface the pin welds to — ``base_elev``, the SOLVED apron /
    # connector variable at the deep end of the truck route — carrying the
    # reach law plus the SAME one-throat allowance
    # (:func:`gs_pin_law_ceiling`).  Where the connector cannot reach the
    # apron mouth inside that bound the deficit still surfaces AIRSIDE (an
    # over-cap connector chord / mouth step) and is never resolved by
    # lifting groundside.
    #
    # ``MOUTH_ALLOWANCE_M`` is defined ONCE at module level
    # (:func:`gs_mouth_allowance_m`) because the groundside FEASIBILITY-
    # WITNESS CLAUSE reads the same scalar — see the module header.
    _gs_float_cap = gs_pin_float_cap(cap)

    # Apron nodes (x, y, idx) — for the route ANCHOR elevation (apron at the deep
    # end of the truck route) and for the apron-arm RAISE along the route; plus the
    # connector/service nodes (the corridor includes the connector itself).
    apron_pts = []
    pav_pts = []
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role == ROLE_APRON:
            tgt_apron = True
        elif s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            tgt_apron = False
        else:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(_key(x, y))
            if i is not None and i < len(elev):
                pav_pts.append((x, y, i))
                if tgt_apron:
                    apron_pts.append((x, y, i))
    centerlines = [cl.line for cl in
                   (getattr(layout, "apt_service_centerlines", None) or [])
                   if cl.line is not None and not cl.line.is_empty]

    def _nearest_apron_elev(px, py, tol=16.0):
        best = None
        for (ax, ay, ai) in apron_pts:
            d = math.hypot(ax - px, ay - py)
            if d <= tol and (best is None or d < best[0]):
                best = (d, elev[ai])
        return best[1] if best else None

    # ── Per apron-reachable connector: follow its TRUCK ROUTE to the apron ────
    # The route is the truck centerline through the connector; budget the reach
    # over its FULL length (groundside edge → apron base, ~55 m) against the apron's
    # elevation at that base — NOT just the connector's own span — so the groundside
    # can sit ``cap·route_len`` above the apron (user 2026-06-27).  Stash each route
    # (with its groundside-mouth arc + direction) for the RAISE pass.
    bounds: dict = {}          # id(g) -> [g, lo, hi]
    routes = []                # (id(g), ln, gm_s, apron_dir, route_len, dem_mouth)
    # THE LAW CEILING per piece (item 3(a)): ``min`` over the serving
    # routes of :func:`gs_pin_law_ceiling` — an ABSOLUTE elevation built
    # from ``base_elev`` (a SOLVED apron / connector variable) and the
    # reach law.  A piece with no serving route never gets an entry, and a
    # missing entry means NO CEILING (see the enforcement pass below) —
    # never a fall back to the DEM sample.
    law_ceiling: dict = {}     # id(g) -> absolute ceiling (m)
    for si in reachable:
        c, _ks = svc[si]
        cnodes = [(x, y, bucket_to_idx.get(_key(x, y)))
                  for (x, y) in _open_ring(list(c.polygon.exterior.coords))]
        cen = c.polygon.centroid
        # the SHORTEST centerline that actually runs through this connector (avoid a
        # long through-airport route whose far end is hundreds of metres away).
        local = [L for L in centerlines if L.distance(cen) <= 8.0]
        ln = min(local, key=lambda L: L.length) if local else None
        for (g, kalt) in gs_pieces:
            gmouth = [(x, y) for (x, y, _i) in cnodes if _key(x, y) in kalt]
            if not gmouth:
                continue
            gmx = sum(p[0] for p in gmouth) / len(gmouth)
            gmy = sum(p[1] for p in gmouth) / len(gmouth)
            dem_gs = sum(kalt[_key(x, y)] for (x, y) in gmouth) / len(gmouth)
            gm_s = apron_dir = route_len = base_elev = None
            if ln is not None:
                gm_s = ln.project(Point(gmx, gmy))
                # apron side = the centerline end FARTHER from the groundside piece.
                e0, e1 = ln.coords[0], ln.coords[-1]
                apron_end_s = (0.0 if g.polygon.distance(Point(e0))
                               >= g.polygon.distance(Point(e1)) else ln.length)
                apron_dir = 1.0 if apron_end_s > gm_s else -1.0
                route_len = min(abs(apron_end_s - gm_s), MAX_ROUTE)
                bp = ln.interpolate(max(0.0, min(ln.length,
                                                 gm_s + apron_dir * route_len)))
                base_elev = _nearest_apron_elev(bp.x, bp.y)
            if base_elev is None:
                # Fallback: no usable centerline → reference the connector's own
                # apron-ward mouth, budget over its span (the earlier model).
                ref_nodes = [i for (x, y, i) in cnodes
                             if i is not None and i < len(elev)
                             and _key(x, y) not in gs_all_keys]
                if not ref_nodes:
                    continue
                base_elev = sum(elev[i] for i in ref_nodes) / len(ref_nodes)
                route_len = min(math.hypot(x - gmx, y - gmy)
                                for (x, y, i) in cnodes if i in ref_nodes)
                ln = None
            if route_len < 1e-6:
                continue
            budget = cap * route_len
            lo = base_elev - budget - dem_gs
            hi = base_elev + budget - dem_gs
            b = bounds.get(id(g))
            if b is None:
                bounds[id(g)] = [g, lo, hi]
            else:
                b[1] = max(b[1], lo)
                b[2] = min(b[2], hi)
            # LAW CEILING (item 3(a)): the weld datum is ``base_elev`` — a
            # SOLVED pavement variable — never ``dem_gs``.  Several routes
            # serve one piece; the ceiling is the tightest of them (the
            # same INTERSECTION rule the shift bounds use one line above).
            _lc = gs_pin_law_ceiling(base_elev, route_len, cap)
            _prev_lc = law_ceiling.get(id(g))
            law_ceiling[id(g)] = (_lc if _prev_lc is None
                                  else min(_prev_lc, _lc))
            routes.append((id(g), ln, gm_s, apron_dir, route_len, dem_gs,
                           (gmx, gmy)))

    n = 0
    # Groundside-mouth points per piece (stashed with each route above) —
    # the anchor geometry for the mouth-decay relevel below.
    mouth_pts: dict = {}
    for (gid, _ln, _gm_s, _dir, _rl, _dm, (gmx, gmy)) in routes:
        mouth_pts.setdefault(gid, []).append((gmx, gmy))
    _mouth_decay = _os.environ.get(
        "O4_GROUNDSIDE_MOUTH_DECAY", "1") == "1"
    deltas: dict = {}
    for gid, (g, lo, hi) in bounds.items():
        # Closest-to-DEM shift inside the feasible band; if the connectors'
        # reaches don't overlap (no uniform shift keeps them all <=cap) fall back
        # to the band midpoint, which minimises the worst residual.
        delta = (min(max(0.0, lo), hi) if lo <= hi else 0.5 * (lo + hi))
        # LAW BOUND (item 3(a), replacing the §C.2 DEM bound): the shift
        # may never lift the piece past the REACH CEILING its connectors
        # justify, plus one throat of allowance.  ``hi`` is already that
        # ceiling expressed in shift space (``min`` over the serving
        # routes of ``base_elev + cap·route_len − dem_mouth``), so the
        # bound is ``hi + cap·MOUTH_ALLOWANCE_M`` — the same allowance,
        # measured from the SOLVED weld datum instead of the ground.
        # ``min`` only: a LOWERING shift (the apron sits below the lot's
        # seed) is honest and stays.
        #
        # WHAT ACTUALLY BINDS.  For a consistent piece (``lo <= hi``) the
        # shift is already ``<= hi``, so this is inert — the reach law is
        # the bound, as it should be.  It binds exactly the contradictory
        # case (``lo > hi``, connectors that cannot all be satisfied),
        # whose mid-point fallback was the widest float in the measured
        # set; that case is now capped by law rather than by terrain.
        _shift_ceiling = hi + _gs_float_cap
        if delta > _shift_ceiling:
            delta = _shift_ceiling
        deltas[gid] = delta
        if abs(delta) < 1e-6:
            continue
        mpts = mouth_pts.get(gid) or []
        if _mouth_decay and mpts:
            # MOUTH-DECAY relevel (user 2026-07-04, CYXY lot #35): the
            # UNIFORM shift sank a 12 k m² lot 3.8 m below terrain
            # everywhere because its 53 m route can only climb
            # ``cap·53`` — but only the MOUTH must meet the road; the
            # lot interior is existing terrain-level pavement.  Each
            # node takes the shift the mouth needs, decayed toward zero
            # at ``cap`` per metre of distance from the nearest mouth —
            # the mouth still sits exactly at the reachable level (the
            # weld + RAISE below read the shifted ring), the interior
            # stays at DEM, and the in-between ramps at ≤cap.  A small
            # piece (everything within ``|delta|/cap`` of its mouth)
            # degenerates to the uniform shift.
            coords = list(g.polygon.exterior.coords)
            new_alts = []
            for k, a in enumerate(g.node_altitudes):
                if a is None:
                    new_alts.append(None)
                    continue
                x, y = coords[min(k, len(coords) - 1)]
                d = min(math.hypot(x - mx, y - my) for (mx, my) in mpts)
                mag = max(0.0, abs(delta) - cap * d)
                new_alts.append(a + math.copysign(mag, delta)
                                if mag > 0.0 else a)
            g.node_altitudes = new_alts
        else:
            g.node_altitudes = [
                (a + delta) if a is not None else None
                for a in g.node_altitudes]
        n += 1

    # CHORD-LIMIT every welded piece BEFORE the weld reads it (lockstep
    # with the post-solve ``_grade_limit_groundside_chords``): the weld
    # pins service-road nodes to these ring values, and the late limiter
    # rewrites the LOT ring only — two writers for the same physical
    # node left the road pinned 1.5 m off the emitted lot (CYXY #41,
    # 15 % road chords after emit consensus).  Limiting here makes the
    # solve-time field the FINAL field (the late pass is idempotent on
    # an already-limited ring).
    from auto_patch.groundside import chord_limit_ring_altitudes
    from auto_patch.config import GROUNDSIDE_MAX_GRADE
    for (g, _lo, _hi) in bounds.values():
        if not g.node_altitudes:
            continue
        g.node_altitudes = chord_limit_ring_altitudes(
            list(g.polygon.exterior.coords), g.node_altitudes,
            cap=GROUNDSIDE_MAX_GRADE)

    # ── LOT↔LOT WELD RECONCILIATION on service rings ─────────────────────
    # (user 2026-07-06, HECA service_road #522).  One road ring can weld to
    # TWO different lots whose re-levelled mouth values disagree beyond the
    # road cap * distance — an unfixable step between two hard welds (the
    # DEM-follow break blend only evaluates INTERIOR nodes, and both ends
    # are anchors).  Lots are FINAL at this point (only the connector reach
    # above moves them), so reconciling here is sound: the SMALLER lot
    # adopts the larger's ±cap·d band (largest-piece-first precedent
    # below), applied as a decay cone (fading at the groundside cap toward
    # the lot interior) so the ring stays Lipschitz and the chord limiter
    # stays idempotent.  Conflicts against BUILDING PADS / APRON bodies are
    # NOT handled here — those move later in the movable-pad yield
    # projection, so they are verified and relaxed post-yield instead
    # (``solve.py`` mouth verify-and-relax).
    _BAND_MARGIN_M = 0.01      # stay inside the band after emit rounding
    svc_ring_pts = []          # per service shape: [(key, (x, y)), ...]
    for (_c, _ks) in svc:
        _pts = [(_key(x, y), (x, y))
                for (x, y) in _open_ring(list(_c.polygon.exterior.coords))]
        svc_ring_pts.append(_pts)
    # Current (post-decay, post-limit) lot value per key; largest lot
    # owns a shared key, mirroring the gs_key_alt precedence below.
    lot_key_val: dict = {}     # key -> (area, lot shape, current value)
    for (g, _kalt) in sorted(gs_pieces,
                             key=lambda t: -t[0].polygon.area):
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes or [])
        for kidx in range(min(len(gcoords), len(galts))):
            if galts[kidx] is None:
                continue
            kk = _key(*gcoords[kidx])
            if kk not in lot_key_val:
                lot_key_val[kk] = (g.polygon.area, g, float(galts[kidx]))
    # Collect per-lot clamp deltas from lot↔lot pairs that share a
    # service ring (the pair the within-shape law measures).
    adjustments: dict = {}     # id(lot) -> [lot, [((x, y), delta)]]

    def _clamp_into(target_list, pt, cur, lo_b, hi_b):
        tgt = min(max(cur, lo_b), hi_b)
        if abs(tgt - cur) > 1e-4:
            target_list.append((pt, tgt, tgt - cur))

    for _pts in svc_ring_pts:
        lots = [(k, p, lot_key_val[k]) for (k, p) in _pts
                if k in lot_key_val]
        if len({id(v[1]) for (_k, _p, v) in lots}) < 2:
            continue
        for ai in range(len(lots)):
            for bi in range(ai + 1, len(lots)):
                (_ka, pa, (aa, ga, va)) = lots[ai]
                (_kb, pb, (ab, gb, vb)) = lots[bi]
                if ga is gb:
                    continue   # same ring: its own chord limit governs
                d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                band = max(0.0, cap * d - _BAND_MARGIN_M)
                if abs(va - vb) <= band:
                    continue
                if aa >= ab:   # smaller lot adopts the larger's band
                    entry = adjustments.setdefault(id(gb), [gb, []])
                    _clamp_into(entry[1], pb, vb, va - band, va + band)
                else:
                    entry = adjustments.setdefault(id(ga), [ga, []])
                    _clamp_into(entry[1], pa, va, vb - band, vb + band)
    n_reconciled = 0
    for (g, adjs) in adjustments.values():
        if not adjs:
            continue
        gcoords = list(g.polygon.exterior.coords)
        new_alts = list(g.node_altitudes)
        # ABSOLUTE Lipschitz support around each moved mouth (not a
        # relative delta cone): the ring near a mouth typically sits
        # exactly at the cap already, so ``old + (delta − cap·d)``
        # under-raises neighbours by the pre-existing slope and leaves
        # the mouth pair over cap (CYXY #184: an at-cap 4.00 % pair
        # re-emitted at 4.64 %).  Support = the new mouth value minus
        # (plus) cap·distance — the tightest field containing the
        # adopted mouth.
        for j in range(min(len(gcoords), len(new_alts))):
            if new_alts[j] is None:
                continue
            xj, yj = gcoords[j]
            val = new_alts[j]
            for ((ax, ay), tgt, dv) in adjs:
                dd = math.hypot(xj - ax, yj - ay)
                if dv > 0.0:
                    val = max(val, tgt - GROUNDSIDE_MAX_GRADE * dd)
                else:
                    val = min(val, tgt + GROUNDSIDE_MAX_GRADE * dd)
            new_alts[j] = val
        g.node_altitudes = chord_limit_ring_altitudes(
            gcoords, new_alts, cap=GROUNDSIDE_MAX_GRADE)
        n_reconciled += 1
    if n_reconciled and _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"  [groundside-reach] mouth reconciliation adjusted "
              f"{n_reconciled} lot ring(s).")

    # ── ENFORCE THE LAW CEILING ON THE FINAL RING (item 3(a)) ────────────
    # The shift clamp above bounds the RELEVEL; two later writers can still
    # push a ring vertex up — the lot↔lot mouth reconciliation (a smaller
    # lot adopts a larger lot's band) and the absolute-Lipschitz support it
    # paints.  The bound is a VALUE bound, so enforce it on the value that
    # is actually welded.
    #
    # THE DATUM IS THE WELD, NOT THE GROUND.  The ceiling at a ring vertex
    # is ``law_ceiling[piece] + GROUNDSIDE_MAX_GRADE · d`` where ``d`` is
    # the distance to the piece's nearest MOUTH — the tightest field that
    # contains the lawful mouth value and grades away from it at the lot's
    # own cap (the same absolute-Lipschitz support the lot↔lot
    # reconciliation above paints, so the two agree by construction).  A
    # vertex above that field is over-cap from its own mouth and would be
    # cut by ``chord_limit_ring_altitudes`` anyway; the lot INTERIOR, which
    # the terrace law leaves free, is never clamped by a distant mouth.
    #
    # NO DATUM ⇒ NO CEILING (owner-directed disposition, item 3(a)): a
    # piece with no serving route has no weld datum, so nothing bounds it
    # from above.  It must NEVER fall back to its DEM sample — that is the
    # exact defect this replaces.  Such a piece is also never re-levelled
    # (it is not in ``bounds``), so it simply stays at its seed.
    #
    # ``law_ceiling_key`` is stashed per canonical key for the post-yield
    # mouth-relax, whose re-projection would otherwise re-open the same
    # door (spec §C.2 ★).
    law_ceiling_key: dict = {}
    for (g, _kalt) in gs_pieces:            # the piece's DEM map is not read
        gid = id(g)
        base_ceil = law_ceiling.get(gid)
        mpts = mouth_pts.get(gid) or []
        if base_ceil is None or not mpts:
            continue                       # no weld datum → unbounded above
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes or [])
        new_alts = list(galts)
        touched = False
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is None:
                continue
            gx, gy = gcoords[k]
            d = min(math.hypot(gx - mx, gy - my) for (mx, my) in mpts)
            ceil_k = base_ceil + GROUNDSIDE_MAX_GRADE * d
            kk = _key(gx, gy)
            if kk not in law_ceiling_key or ceil_k < law_ceiling_key[kk]:
                law_ceiling_key[kk] = ceil_k
            if galts[k] > ceil_k:
                new_alts[k] = ceil_k
                touched = True
        if touched:
            g.node_altitudes = chord_limit_ring_altitudes(
                gcoords, new_alts, cap=GROUNDSIDE_MAX_GRADE)

    # (now-shifted) groundside altitude per key, for the weld.  LARGEST
    # piece first: where a big lot and a sliver connector piece share a
    # mouth key with different altitudes, the mouth serves the LOT
    # (user 2026-07-04, CYXY P4: welding to the 100 m² demoted
    # connector at 698.5 left the road 3 m under the 49 k m² lot).
    gs_key_alt: dict = {}
    gs_key_owner: dict = {}
    for (g, _kalt) in sorted(gs_pieces,
                             key=lambda t: -t[0].polygon.area):
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes)
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is not None:
                kk = _key(*gcoords[k])
                if kk not in gs_key_alt:
                    gs_key_alt[kk] = float(galts[k])
                    gs_key_owner[kk] = id(g)

    # ``hard`` = the returned truth-pin set.  Only WELDS go in it (shared
    # road/apron↔lot geometry takes the lot's value — physical identity).
    # The RAISE below writes elevation SEEDS but does NOT pin: a raised
    # taper value is a heuristic floor, and pinning it hard froze arm
    # nodes 1.3 m under the adjacent welded mouth (CYXY route D, 61 %
    # chord after planarize mixed the two fields into one ring) — the
    # post-reach projections grade the arm into the welds instead.
    hard: set = set()

    # ── RAISE the apron arm + connector along the truck route ────────────────
    # The narrow apron arm is welded to the connector, so as the connector climbs at
    # <=cap to the (now higher) groundside, that climb is carried BACK along the
    # truck route: every apron/connector node in the route corridor takes the
    # SELF-TAPERING profile ``gs_level − cap·(arc back from the groundside mouth)``.
    # The taper auto-stops where it drops below the apron's own elevation (the base),
    # so the raise is confined to the arm; the caller grades the apron body into it.
    for (gid, ln, gm_s, apron_dir, route_len, dem_mouth, (gmx, gmy)) in routes:
        delta = deltas.get(gid, 0.0)
        gs_level = dem_mouth + delta
        # The arm must rise whenever the groundside ends up ABOVE the apron base —
        # even when the piece was LOWERED toward a reachable level (delta < 0, its
        # DEM was higher than reachable).  The self-taper raises only where needed.
        if ln is None:
            continue
        for (px, py, pi) in pav_pts:
            p = Point(px, py)
            if ln.distance(p) > RAISE_W:
                continue
            # corridor membership = along the route (apron side, within route_len);
            # but the PROFILE tapers by STRAIGHT distance from the groundside mouth,
            # so the connector rect (graded on its straight span, not the curved
            # centerline arc) comes out at exactly <=cap, not the arc-inflated rate.
            s = ln.project(p)
            if (s - gm_s) * apron_dir < -2.0 or (s - gm_s) * apron_dir \
                    > route_len + 5.0:
                continue
            straight = math.hypot(px - gmx, py - gmy)
            tgt = gs_level - cap * straight
            if tgt > elev[pi] + 1e-3:
                elev[pi] = tgt

    # ── WELD each connector's groundside mouth to the shifted groundside ─────
    # Reachable connectors weld as before.  An UNREACHABLE connector still
    # welds where its truck ROUTE ENDS at the lot — a destination road must
    # CLIMB to the lot it serves (user 2026-07-04, CYXY P4: the road emitted
    # 3.1 m below the lot at coincident nodes).  Blanket-welding every
    # unreachable lot-touching connector measured +215 within-shape pairs
    # (mouth pins fighting DEM-followed road surfaces mid-network); the
    # route-END scope pins only the served destination mouth.
    route_end_points = []
    for ln in centerlines:
        try:
            route_end_points.append(Point(*ln.coords[0]))
            route_end_points.append(Point(*ln.coords[-1]))
        except (ValueError, IndexError):
            continue
    # Coordinate keys this pass welded (rounded like the emit consensus) —
    # persisted on the layout so the POST-solve groundside chord limiter
    # can re-adopt its re-limited values onto exactly these nodes (and no
    # others: a road passing a DEM-stay lot keeps its by-design seam).
    weld_coord_keys: set = set()
    for si in range(len(svc)):
        c, _ks = svc[si]
        is_reachable = si in reachable
        for (x, y) in _open_ring(list(c.polygon.exterior.coords)):
            k = _key(x, y)
            a = gs_key_alt.get(k)
            if a is None:
                continue
            if not is_reachable:
                p = Point(x, y)
                if not any(p.distance(ep) <= 15.0
                           for ep in route_end_points):
                    continue
            i = bucket_to_idx.get(k)
            if i is not None and i < len(elev):
                elev[i] = a
                hard.add(i)
                weld_coord_keys.add((round(x, 2), round(y, 2)))

    # ── WELD every pavement node ON a re-levelled lot ring ───────────────────
    # The svc-ring weld above misses the MOUTH vertex when it lives on the
    # APRON arm instead of a service shape (CYXY route D: the shared lot
    # vertex belonged to the apron at solve time, the RAISE floored it
    # 1.3 m under the lot's welded level, and post-solve planarize copied
    # that value into the road ring → 15 % mixed-field chords).  The
    # road↔lot connection is FIRST-CLASS shared geometry no matter which
    # role carries the vertex: any solver node whose canonical key lies on
    # a re-levelled piece's ring takes that ring's value.  Scoped to
    # pieces the reach actually processed (``bounds``) — pieces with no
    # reachable connector stay DEM and pin nothing (the blanket-weld
    # regression class, +215).
    relevelled_gids = {gid for gid in bounds}
    for (px, py, pi) in pav_pts:
        k = _key(px, py)
        a = gs_key_alt.get(k)
        if a is None or gs_key_owner.get(k) not in relevelled_gids:
            continue
        if pi < len(elev):
            elev[pi] = a
            hard.add(pi)
            weld_coord_keys.add((round(px, 2), round(py, 2)))
    layout._groundside_weld_keys = weld_coord_keys
    # Per-PIN LAW ceiling in solver-index space — consumed by the post-yield
    # mouth verify-and-relax (spec §C.2 ★: a bounded pin's ADOPTED profile
    # must be bounded the same way or the lift returns through that door).
    # Also the measurement handle for the §C acceptance gate.
    #
    # RENAMED from ``_gs_pin_dem_ceiling_idx`` (item 3(a)): the datum is no
    # longer the DEM, so the name may not say so.  A pin whose piece has no
    # weld datum carries NO entry — the consumer leaves it unbounded above
    # rather than inventing a terrain bound.
    _pin_ceiling_idx: dict = {}
    for kk, ceil_k in law_ceiling_key.items():
        i = bucket_to_idx.get(kk)
        if i is None or i not in hard:
            continue
        if i not in _pin_ceiling_idx or ceil_k < _pin_ceiling_idx[i]:
            _pin_ceiling_idx[i] = float(ceil_k)
    layout._gs_pin_law_ceiling_idx = _pin_ceiling_idx
    # GROUNDSIDE FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30) — the
    # pinned mouth/weld nodes by CANONICAL KEY, so the later passes that
    # rebuild the node space (``final_grade_projection``) can still name the
    # anchors whose witness role the clause withdraws.  A key set only; it
    # asserts nothing on its own.
    _key_of = {i: k for k, i in bucket_to_idx.items()}
    layout._gs_pin_keys = {_key_of[i] for i in hard if i in _key_of}
    if _os.environ.get("O4_STEP_DEBUG") == "1" and _pin_ceiling_idx:
        # SLACK against the LAW ceiling (item 3(a)): the old line reported
        # float above DEM, a number the law no longer has an opinion about.
        floats = sorted(elev[i] - c for i, c in _pin_ceiling_idx.items()
                        if i < len(elev))
        if floats:
            _m50 = floats[len(floats) // 2]
            _nover = sum(1 for f in floats if f > 1e-6)
            print(f"  [gs-pin-law] {len(floats)} pin(s) with a law "
                  f"ceiling: value−ceiling median={_m50:+.2f} "
                  f"max={floats[-1]:+.2f} "
                  f"min={floats[0]:+.2f}; allowance="
                  f"{_gs_float_cap:.2f} over-ceiling={_nover}")
    return n, hard


def _line_unit_tangent(line, s):
    """Unit tangent (dx, dy) of a shapely ``LineString`` at arclength ``s``,
    from a symmetric ±(¼-length, capped 1 m) difference; ``None`` for a
    degenerate line.  Used by the parallel-road station merge's tangent guard."""
    import math
    length = line.length
    if length <= 1e-6:
        return None
    eps = min(1.0, length * 0.25)
    a = line.interpolate(max(0.0, s - eps))
    b = line.interpolate(min(length, s + eps))
    dx, dy = b.x - a.x, b.y - a.y
    norm = math.hypot(dx, dy)
    return (dx / norm, dy / norm) if norm > 1e-9 else None


def _parallel_station_merge_pairs(st_xy, station_line, tangent_at,
                                  max_gap, min_abs_cos):
    """Station-id pairs ``[(a, b), …]`` to couple for the WIDE parallel-road
    station merge (part 30m follow-up, candidate (a)).

    A pair qualifies iff the two stations are on DIFFERENT host lines, their XY
    gap is ``<= max_gap``, and their host-line tangents are NEAR-PARALLEL
    (``|cos∠(tangent_a, tangent_b)| >= min_abs_cos``).  The absolute cosine
    admits an antiparallel loop-return leg (|cos|≈1) while a distinct crossing
    road (≈90°, |cos|≈0) never qualifies — the guard that keeps the coupling to
    genuine parallel pairs.  Pure: no elevation, no I/O — unit-testable."""
    import math
    pairs = []
    grid: dict = {}
    for sid, (x, y) in st_xy.items():
        grid.setdefault((int(x // max_gap), int(y // max_gap)), []).append(sid)
    for (cx, cy), cell in grid.items():
        neigh = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neigh.extend(grid.get((cx + ox, cy + oy), ()))
        for a in cell:
            ax, ay = st_xy[a]
            ta = tangent_at.get(a)
            if ta is None:
                continue
            for b in neigh:
                if b <= a or station_line[b] == station_line[a]:
                    continue
                bx, by = st_xy[b]
                if math.hypot(ax - bx, ay - by) > max_gap:
                    continue
                tb = tangent_at.get(b)
                if tb is None:
                    continue
                if abs(ta[0] * tb[0] + ta[1] * tb[1]) < min_abs_cos:
                    continue                # crossing / divergent → distinct
                pairs.append((a, b))
    return pairs


def service_seed_lines(layout) -> list:
    """THE service centerline set this module seeds and ties against.

    RULING 3 (corridor-joins round, Fable spec 2026-08-12c): the seeder
    consumes the SAME chain set the grade graph registers —
    ``grade_graph.service_chain_lines``, i.e. the service half of
    ``centerline_specs``, corridor chains and feed chains included — never
    a second enumeration of its own.  The measured defect it closes: this
    function used to read ``apt_taxi_centerlines`` filtered on
    ``is_service`` (the row-1206 routes ONLY), so KCLT's feed-sourced lot
    road had no spine here at all, fell through to the per-vertex fallback,
    and ended 6.31 m proud of DEM at the owner's acceptance coordinate.

    ``config.SERVICE_CORRIDOR_FREE_END_ANCHOR`` off ⇒ the row-1206 walk,
    byte-identically.
    """
    from auto_patch.config import SERVICE_CORRIDOR_FREE_END_ANCHOR
    from shapely.geometry import LineString
    if SERVICE_CORRIDOR_FREE_END_ANCHOR:
        try:
            from auto_patch.grade_graph import service_chain_lines
            return service_chain_lines(layout)
        except Exception:                                # pragma: no cover
            pass
    lines = []
    for cl in (getattr(layout, "apt_taxi_centerlines", None) or []):
        if not getattr(cl, "is_service", False):
            continue
        ln = getattr(cl, "line", None)
        if ln is None or getattr(ln, "is_empty", True):
            continue
        try:
            cs = list(ln.coords)
        except Exception:                                # pragma: no cover
            continue
        if len(cs) >= 2:
            lines.append(LineString(cs))
    return lines


def free_end_targets(layout, svc_nodes, node_pos, anchors, dem_elev,
                     ceil, floor, *, radius_m: float):
    """The HARD free-end DEM ties: ``({node: target}, [record, …])``.

    RULING 3 (corridor-joins round).  A corridor chain TERMINUS that does
    not land on pavement ties to AMBIENT DEM — R20-2's walk-to-ground law
    made general (RULINGS 2026-08-12b: "where a road reaches its free end
    at ambient terrain it GRADES to DEM under the road cap"; walls may not
    cut across its course, so the road's own descending surface owns the
    level change).

    * A terminus is FREE when no service node within ``radius_m`` of it is
      already an anchor — i.e. it welds to neither aircraft pavement nor a
      groundside piece.  Anchored ends keep their weld: this pass never
      competes with an existing authority.
    * The whole terminal cross-section takes ONE value (the mean DEM of its
      member nodes), so the tie cannot seat a tear across the road.
    * The value is CLAMPED INTO the existing reach band (``ceil``/``floor``
      from the mouth anchors at the road cap) before it is anchored, so the
      end descends AS FAR AS THE CAP ALLOWS and never mints an
      infeasibility: on terrain the cap can reach — the KCLT case, 6.31 m
      over a long road — the clamp is inert and the end lands ON DEM.

    Pure: reads the graph, writes nothing.  The caller anchors the targets
    (which is what makes them survive, unlike the soft per-vertex seed).
    """
    import math as _m
    lines = service_seed_lines(layout)
    if not lines:
        return {}, []
    ends: list = []
    for ln in lines:
        try:
            cs = list(ln.coords)
        except Exception:                                # pragma: no cover
            continue
        if len(cs) >= 2:
            ends.append(cs[0])
            ends.append(cs[-1])
    targets: dict = {}
    records: list = []
    claimed: set = set()
    # ── §3 (RULINGS 2026-08-30c): A DECK ABUTMENT IS NOT A TERMINUS ──
    # "Nor is the deck a corridor terminus: no free-end DEM tie is
    # minted at either abutment, because the road runs THROUGH."  The
    # keep-out is the deck corridors themselves, so both abutments and
    # the span between them are covered by one test.  ``None`` wherever
    # the law found no deck, which makes this inert everywhere else.
    from auto_patch.road_bridge_deck import abutment_keep_out as _dko
    _deck_keep_out = _dko(layout)
    _n_deck_ends = 0
    for (tx, ty) in ends:
        if _deck_keep_out is not None:
            try:
                from shapely.geometry import Point as _Pt
                # COVERS, not CONTAINS: an abutment sits exactly ON the
                # corridor's end cap, and ``contains`` excludes the
                # boundary — which would leave the tie standing at the
                # one point §3 exists to protect.
                if _deck_keep_out.covers(_Pt(tx, ty)):
                    _n_deck_ends += 1
                    continue
            except Exception:                            # pragma: no cover
                pass
        members = [i for i in svc_nodes
                   if i in node_pos
                   and _m.hypot(node_pos[i][0] - tx,
                                node_pos[i][1] - ty) <= radius_m]
        if not members or any(i in anchors for i in members):
            continue                     # welded end — not a free end
        if all(i in claimed for i in members):
            continue                     # two chains sharing one terminus
        dems = [dem_elev[i] for i in members
                if i < len(dem_elev) and dem_elev[i] is not None]
        if not dems:
            continue
        de = sum(dems) / len(dems)
        # Descend AT MOST at the cap: the band the mouth anchors already
        # define is the road's own law, so the tie is clamped into it.
        c = min((ceil[i] for i in members if i in ceil), default=None)
        f = max((floor[i] for i in members if i in floor), default=None)
        tgt = de
        if c is not None and f is not None and f > c + 1e-9:
            continue                     # contradicted end — leave the
            #                              existing break machinery to it
        if c is not None:
            tgt = min(tgt, c)
        if f is not None:
            tgt = max(tgt, f)
        for i in members:
            targets[i] = tgt
            claimed.add(i)
        records.append({"x": float(tx), "y": float(ty),
                        "dem_m": round(float(de), 3),
                        "target_m": round(float(tgt), 3),
                        "clamped": bool(abs(tgt - de) > 1e-6),
                        "nodes": len(members)})
    if _n_deck_ends:
        import O4_UI_Utils as _UI_deck
        _UI_deck.vprint(1,
            f"  [bridge-deck] §3: {_n_deck_ends} corridor end(s) inside a "
            f"road-bridge-deck span take NO free-end DEM tie — the road "
            f"runs THROUGH a deck, so its abutments are not termini.")
    return targets, records


def _profile_law_release(conflicts, run_sid) -> set:
    """R1 (service-road law spec, 2026-08-15): A HELD PROFILE MUST BE
    LAWFUL OR IT IS NOT HELD — the anchor-placement law applied to
    ``svc_profile``.

    The corridor profile's OWN audit already names every unlawful spot
    (``corridor_profile``): an ``over_cap_segment`` conflict (a strung
    segment steeper than the cap, only reachable through a relaxed
    inverted tube) and an ``inverted_tube`` conflict (a station whose
    tube ``_relax_tube`` levelled because two anchor regimes
    contradict).  Every station in such a segment/tube is RELEASED from
    the hold: it never enters the ``svc_profile`` keyset, keeps the
    profile value as its SEED, and solves under the road's own law
    edges — exactly the mechanism of the 1-D validity release below.
    Stations whose audit is clean stay held (the smooth majority must
    not loosen).  The release conditions are EXACTLY the audit's two
    conflict classes — no new thresholds (spec, pre-delegated
    decisions; ``peg_pair`` conflicts name an end-tie tension, not a
    held-station value, and do not release).

    ``conflicts``  one run's ``RunProfile.conflicts``.
    ``run_sid``    the run's station ids, indexed by the conflicts'
                   ``station_index`` (the run-local station ordinal).
    Returns the set of station ids released.
    """
    rel: set = set()
    for cf in conflicts:
        kind = getattr(cf, "kind", None)
        k = getattr(cf, "station_index", None)
        if k is None:
            continue
        if kind == "over_cap_segment":
            # segment k-1 -> k: BOTH stations of the over-cap segment.
            for kk in (k - 1, k):
                if 0 <= kk < len(run_sid):
                    rel.add(run_sid[kk])
        elif kind == "inverted_tube":
            if 0 <= k < len(run_sid):
                rel.add(run_sid[k])
    return rel


def _r4_pegged_span(run_pegs: dict) -> tuple | None:
    """R4 (service-road law spec, 2026-08-15): THE STRING HOLDS ON THE
    PEGGED SPAN ONLY.

    Pegs are the corridor run's LAW TARGETS; the 1-D string is the law
    object BETWEEN targets.  Returns the closed station-index span
    ``(lo, hi)`` of the outermost pegged stations, or ``None`` when the
    run has fewer than two law targets (or a degenerate single-station
    span) — in which case the run is not strung at all and every
    station keeps the pointwise spine-first DEM-follow rule.

    Measured defect this encodes: HECA run (46,0), 2,364.6 m of
    corridor with pegs only at s=0/3.0/7.2 m, strung FLAT at 127.21
    end to end (37.6 m over ambient at the far junction).  A synthetic
    far-end DEM tie is refused as the fix: it re-draws the run as a
    km-scale chord — the census-invisible ridge class the warm-start
    retirement named.
    """
    if len(run_pegs) < 2:
        return None
    lo, hi = min(run_pegs), max(run_pegs)
    if hi - lo < 1:
        return None
    return lo, hi


def _corridor_colevel_rehome(lines, node_pos, node_station_raw,
                             node_shapes, anchors, reach_m) -> int:
    """R5c(2) — CORRIDOR CO-LEVEL ACROSS THE COMPOSITE.

    The visible "road" is a COMPOSITE: CYXY's owner site is
    ``service_road`` 349 and ``service_junction`` 63 on ONE corridor.
    Each shape's vertices pick their OWN nearest chain, so the two
    pieces take station values from two different chain projections and
    the corridor can slope LATERALLY across itself — even though every
    single shape is cross-section-flat (each station value is shared by
    its whole cluster, the spine-first law, which is why the defect is
    invisible to a per-shape instrument).

    The fix is membership, not a second value rule: a junction vertex
    that can project onto the chain of an ADJOINING road — within the
    same station reach the seeder already uses — joins THAT chain's
    station cluster instead of its own, so road and junction pieces at
    equal arclength take one value by construction.

    THE JUNCTION RULE for a junction hosting MULTIPLE chains (spec):

    1. MOUTH WELDS WIN — the chain carrying the most of the junction's
       welded (anchor) vertices is the corridor the junction belongs to;
       a weld is a law target and it names its own corridor.
    2. Otherwise the THROUGH-CHAIN OF ITS WIDEST ROAD — measured with
       the layout's own width instrument (``_rect_short_edge_width_m``),
       never a second one.

    Vertices farther than ``reach_m`` from the chosen chain are left
    alone (the reach is the seeder's, unchanged), as are vertices that
    carry no station at all — they keep the per-vertex fallback exactly
    as before.  Mutates ``node_station_raw`` in place; returns the
    number of vertices re-homed.
    """
    from auto_patch.layout import (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
                                   _rect_short_edge_width_m)
    if not node_shapes or not lines:
        return 0
    try:
        from shapely.geometry import Point
    except Exception:                                   # pragma: no cover
        return 0

    # shape identity -> (shape, its stationed vertices)
    by_shape: dict = {}
    for i, shs in node_shapes.items():
        if i not in node_pos:
            continue
        for s in shs:
            e = by_shape.get(id(s))
            if e is None:
                by_shape[id(s)] = e = (s, [])
            e[1].append(i)

    _width_cache: dict = {}

    def _width(o):
        w = _width_cache.get(id(o))
        if w is None:
            w = _rect_short_edge_width_m(getattr(o, "polygon", None)) or 0.0
            _width_cache[id(o)] = w
        return w

    def _chain_of(o):
        """The road's THROUGH-CHAIN: the line its vertices mostly
        project onto (ties break on the lower line index, so the choice
        is deterministic across runs)."""
        counts: dict = {}
        for i in by_shape.get(id(o), (None, ()))[1]:
            e = node_station_raw.get(i)
            if e is not None:
                counts[e[0]] = counts.get(e[0], 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]

    moved = 0
    for _sid, (s, nodes) in by_shape.items():
        if getattr(s, "role", None) != ROLE_SERVICE_JUNCTION:
            continue
        # ADJOINING roads share a vertex with the junction — the weld
        # that makes the two pieces one corridor in the first place.
        roads: dict = {}
        for i in nodes:
            for o in node_shapes.get(i, ()):
                if o is s or getattr(o, "role", None) != ROLE_SERVICE_ROAD:
                    continue
                roads.setdefault(id(o), o)
        if not roads:
            continue
        cand: dict = {}                 # chain -> widest road on it
        for o in roads.values():
            li = _chain_of(o)
            if li is None or li >= len(lines):
                continue
            w = _width(o)
            if li not in cand or w > cand[li]:
                cand[li] = w
        if not cand:
            continue
        weld_votes: dict = {}
        for i in nodes:
            if i not in anchors:
                continue
            e = node_station_raw.get(i)
            if e is not None and e[0] in cand:
                weld_votes[e[0]] = weld_votes.get(e[0], 0) + 1
        if weld_votes:                  # 1. mouth welds win
            target = max(weld_votes.items(),
                         key=lambda kv: (kv[1], cand[kv[0]], -kv[0]))[0]
        else:                           # 2. the widest road's through-chain
            target = max(cand.items(), key=lambda kv: (kv[1], -kv[0]))[0]

        ln = lines[target]
        for i in nodes:
            e = node_station_raw.get(i)
            if e is None or e[0] == target:
                continue
            P = Point(node_pos[i])
            if ln.distance(P) > reach_m:
                continue                # out of the seeder's station reach
            node_station_raw[i] = (target, ln.project(P))
            moved += 1
    return moved


def service_station_map(lines, svc_nodes, node_pos, node_shapes, anchors,
                        R, *, quiet: bool = True):
    """``(stations, node_station)`` — THE service-corridor STATION map.

    Extracted verbatim from :func:`_svc_spine_station_seeds` (round 5b) so
    the two readers of the road's PATH COORDINATE share ONE derivation:
    the seeder here, which runs inside the solve, and
    the road TRANSITION profiler (``road_transition``), which runs
    POST-solve in the emitted node space.  A second projection/clustering convention
    would be two instruments describing two station sets — the
    census-wrapper defect at one remove — and the round-5b spec forbids
    it in as many words ("reuse the route-metric-within-shape machinery,
    never a second derivation").

    ``stations[sid]`` is ``{"line", "s", "members", …}``; ``node_station``
    maps a node index to its ``sid``.  Nodes with no service line within
    ``R`` are absent from both — the caller's own fallback owns them.

    ``quiet`` suppresses the R5c co-level log line (the post-solve reader
    re-runs the same rehome on the same data and must not double-report
    it).
    """
    import math as _m                                    # noqa: F401
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    tree = STRtree(lines)
    # node → (line_idx, arclength) for the nearest service line within R.
    node_station_raw: dict = {}
    for i in sorted(svc_nodes):
        p = node_pos.get(i)
        if p is None:
            continue
        P = Point(p)
        try:
            cand = tree.query(P.buffer(R))
        except Exception:
            continue
        best = None
        for qi in cand:
            li = int(qi)
            d = lines[li].distance(P)
            if d <= R and (best is None or d < best[0]):
                best = (d, li, lines[li].project(P))
        if best is not None:
            node_station_raw[i] = (best[1], best[2])
    if not node_station_raw:
        return [], {}

    # R5c(2) — CORRIDOR CO-LEVEL: junction pieces join the ADJOINING
    # road's chain before the clusters are cut, so a corridor's road and
    # junction shapes take ONE station value at equal arclength instead
    # of two chain projections that can slope laterally across it
    # (owner in-sim, CYXY 60.7087015,-135.0746305).  See
    # ``_corridor_colevel_rehome`` for the junction rule.
    _colevel_moved = _corridor_colevel_rehome(
        lines, node_pos, node_station_raw, node_shapes, anchors, R)
    if not quiet:
        try:
            import O4_UI_Utils as _UI_cl
            _UI_cl.vprint(1,
                f"  [pav-builder] R5c corridor co-level: {_colevel_moved} "
                f"service_junction vertex/vertices re-homed onto an "
                f"adjoining road's chain (mouth welds win, then the "
                f"widest road's through-chain) — road and junction pieces "
                f"of one corridor now share a station value at equal "
                f"arclength.")
        except Exception:                               # pragma: no cover
            pass

    # Cluster per-line arclengths into stations (cross-section partners
    # project to near-identical s; 2.0 m absorbs foot/weld noise while
    # staying far under the ~12 m station spacing).
    _CLUSTER_GAP_M = 2.0
    by_line: dict = {}
    for i, (li, s) in node_station_raw.items():
        by_line.setdefault(li, []).append((s, i))
    stations: list = []          # station → dict(line, s, members)
    node_station: dict = {}
    for li, lst in by_line.items():
        lst.sort()
        cur = None
        for (s, i) in lst:
            if cur is None or s - cur["s_max"] > _CLUSTER_GAP_M:
                cur = {"line": li, "s_sum": 0.0, "s_max": s, "n": 0,
                       "members": []}
                stations.append(cur)
            cur["s_sum"] += s
            cur["s_max"] = max(cur["s_max"], s)
            cur["n"] += 1
            cur["members"].append(i)
            node_station[i] = len(stations) - 1
    for st in stations:
        st["s"] = st["s_sum"] / st["n"]
    return stations, node_station


def _svc_spine_station_seeds(layout, svc_nodes, node_pos, anchors,
                             dem_elev, cap, node_ceil, node_floor,
                             node_ceil_dist, node_floor_dist,
                             prox_pairs=(), node_shapes=None):
    """SPINE-FIRST seed field (config.SVC_SPINE_FIRST, part 30m): the service
    network's DEM-follow computed per spine STATION and shared by the whole
    cross-section, instead of per ring vertex.

    Per-vertex DEM-follow let a road's two long edges bind to DIFFERENT
    anchor regimes (each side clamps into the reach band of ITS nearest
    welds), which rendered a cross-road tear — CYXY 2.49 m at
    60.7092306,-135.0738928.  Here the ROAD HUGS TERRAIN LONGITUDINALLY
    within its cap along the spine, and every ring vertex of a cross-section
    takes the SAME station value, so a tear across the road cannot even be
    seeded.  These are SEEDS ONLY (soft): the road's within-shape law edges
    (``grade_graph.SOFT_VISIBILITY_ROLES`` + the service lateral pass, same
    gate) are the authority and the solve's final projections remain the
    sole writer.

    Mechanism, mirroring the per-vertex operator 1:1 but on stations:
      * stations = clusters of the service ring vertices' perpendicular
        projections onto the service (truck-route) centerlines — the spine
        arclength is the station coordinate, so opposite-edge partners
        (aligned by ``insert_service_lateral_nodes``) share one station.
        R5c(2): cluster membership crosses SHAPE boundaries — a
        ``service_junction`` vertex within station reach of an adjoining
        road's chain joins THAT chain (``_corridor_colevel_rehome``), so
        one corridor's road and junction pieces are co-levelled at equal
        arclength instead of taking two chain projections;
      * station DEM = mean vertex DEM of the cluster, LOW-PASSED along the
        line (±~1.5 station steps) — the seed follows terrain at station
        wavelength, not raster noise (a lone unpaired station otherwise
        imprints its own DEM sample as a cross/diagonal step);
      * station band = the INTERSECTION of the member vertices' node-graph
        reach bands (``[max member floor, min member ceil]``) — the SAME
        cap-Lipschitz reach the per-vertex operator used, so connectivity
        to the mouth welds is inherited from the proven node graph (an
        earlier separate station-graph Dijkstra left whole chains
        anchor-unreachable), while the INTERSECTION makes both edges obey
        BOTH sides' anchors at once;
      * clamp + the SAME distance-weighted break blend as the per-vertex
        path (an empty intersection is exactly the old two-regime
        contradiction, now surfaced once per cross-section); broken
        stations quarantine their members through the existing
        ``service_break`` machinery.

    Returns ``(node_target, broken_nodes)``: seed values for the non-anchor
    vertices that found a station (vertices with no spine within reach — wide
    service-junction yards — keep the legacy per-vertex path), and the subset
    belonging to genuinely broken stations."""
    import math as _m
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M, SPINE_STEP_M

    try:
        from shapely.geometry import LineString, Point
        from shapely.strtree import STRtree
    except Exception:                                   # pragma: no cover
        return {}, set()

    lines = service_seed_lines(layout)
    if not lines:
        return {}, set()

    R = ROAD_CARVE_MAX_WIDTH_M / 2.0 + 2.0
    stations, node_station = service_station_map(
        lines, svc_nodes, node_pos, node_shapes, anchors, R, quiet=False)
    if not stations:
        return {}, set()

    # Station XY + per-line ordered station lists.
    st_xy = {}
    for sid, st in enumerate(stations):
        q = lines[st["line"]].interpolate(st["s"])
        st_xy[sid] = (q.x, q.y)
    by_line_sid: dict = {}
    for sid, st in enumerate(stations):
        by_line_sid.setdefault(st["line"], []).append(sid)

    # PARALLEL-ROAD STATION MERGE — the station-level analogue of the node
    # graph's O4_SVC_PROXIMITY_COUPLE (part 27, HECA #510↔#517): two service
    # lines running < ~2 m apart carry separate station chains, so each
    # road's cross-section would seed from ITS line alone and the pair can
    # re-open the metre-scale wall the node coupling closed (measured at
    # HECA #576↔#584: cross-shape 0.16 m → 0.84 m without this merge).
    # Stations of DIFFERENT lines within the window share ONE merged member
    # set → one DEM mean, one band intersection, one target.  Union-find;
    # the merged station keeps the first sid as root.
    _PROX_M = 2.0
    parent = list(range(len(stations)))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    _grid: dict = {}
    for sid, (x, y) in st_xy.items():
        _grid.setdefault((int(x // _PROX_M), int(y // _PROX_M)),
                         []).append(sid)
    for (cx, cy), cell in _grid.items():
        neigh = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neigh.extend(_grid.get((cx + ox, cy + oy), ()))
        for a in cell:
            ax, ay = st_xy[a]
            for b in neigh:
                if b <= a or stations[b]["line"] == stations[a]["line"]:
                    continue
                bx, by = st_xy[b]
                if _m.hypot(ax - bx, ay - by) <= _PROX_M:
                    ra, rb = _find(a), _find(b)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    # … and through the NODE couples (the exact part-27 proximity notion):
    # two parallel lines' stations are longitudinally OFFSET in general, so
    # the XY merge above can miss them (HECA #576↔#584 stayed 0.84 m apart
    # with XY-merge alone) — but their RING nodes across the sliver are
    # coupled, and coupled nodes' stations must share one cross-section.
    for (i, j) in prox_pairs:
        si, sj = node_station.get(i), node_station.get(j)
        if si is None or sj is None or si == sj:
            continue
        ra, rb = _find(si), _find(sj)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # WIDE PARALLEL-ROAD STATION MERGE (part 30m follow-up, candidate (a)):
    # the 2 m XY window and the node proximity couple (both ~2 m) MISS a
    # several-metre rendered gap, so two NON-touching but near-parallel service
    # ways a few metres apart still seed from SEPARATE spine regimes and seat a
    # metre-scale wall across the gap (HECA -10494 service_road ↔ -10108
    # service_junction, ~6.7 m gap: per-vertex 0.845 m).  Couple their stations
    # out to ``PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M`` when the two host
    # lines run NEAR-PARALLEL at those stations — a TANGENT guard so a distinct
    # crossing road (≈90°) never couples, only a genuine parallel pair (a loop
    # road's return leg counts: antiparallel, |cos|≈1).  The merge shares one
    # DEM seed + one band INTERSECTION across the cross-section, so the wall is
    # single-valued (unseedable), not merely reduced.  Gate off ⇒ untouched.
    if PARALLEL_SERVICE_STATION_MERGE and len(stations) > 1:
        tangent_at = {
            sid: _line_unit_tangent(lines[st["line"]], st["s"])
            for sid, st in enumerate(stations)}
        station_line = {sid: st["line"] for sid, st in enumerate(stations)}
        for (a, b) in _parallel_station_merge_pairs(
                st_xy, station_line, tangent_at,
                PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M,
                PARALLEL_SERVICE_STATION_MERGE_MIN_ABS_COS):
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

    _merged = 0
    for sid in range(len(stations)):
        r = _find(sid)
        if r != sid:
            stations[r]["members"].extend(stations[sid]["members"])
            for i in stations[sid]["members"]:
                node_station[i] = r
            stations[sid]["members"] = []
            _merged += 1

    # Raw station DEM = mean member DEM; then LOW-PASS along each line so a
    # lone unpaired station cannot imprint a raster-noise step on the seed
    # (measured at CYXY -10193: adjacent raw stations 718.86/719.07/718.99
    # → a 4.4 % diagonal pair the projections had already frozen into the
    # clearance welds by emit time).
    raw_de: dict = {}
    for sid, st in enumerate(stations):
        dems = [dem_elev[i] for i in st["members"]
                if i < len(dem_elev) and dem_elev[i] is not None]
        if dems:
            raw_de[sid] = sum(dems) / len(dems)
    _SMOOTH_M = 1.5 * SPINE_STEP_M
    smooth_de: dict = {}
    for li, sids in by_line_sid.items():
        sids.sort(key=lambda k: stations[k]["s"])
        with_de = [k for k in sids if k in raw_de]
        for k in with_de:
            s0 = stations[k]["s"]
            window = [raw_de[j] for j in with_de
                      if abs(stations[j]["s"] - s0) <= _SMOOTH_M]
            smooth_de[k] = sum(window) / len(window)

    # Station reach band = INTERSECTION of the member vertices' node-graph
    # bands — the same anchors, the same cap-Lipschitz metric, the proven
    # connectivity (ring edges + proximity couples), but binding BOTH edges
    # of the cross-section to BOTH sides' anchors at once.
    import os as _os
    _dbg_spec = _os.environ.get("O4_SVC_SPINE_DEBUG_LL")
    _dbg_xy = None
    if _dbg_spec:
        try:
            _dla, _dlo = (float(v) for v in _dbg_spec.split(","))
            _dbg_xy = layout.ll_to_m(_dla, _dlo)
        except Exception:
            _dbg_xy = None

    node_target: dict = {}
    broken_nodes: set = set()

    # ── THE WHOLE-RUN CORRIDOR PROFILE (staged-solve round, lane S2) ──
    # ONE corridor is ONE law object end to end, and its VERTICAL half is
    # solved as one 1-D constrained problem over the whole run: pegs at
    # the mouth welds (stage-A airside values, read-only) and at the
    # free-end DEM ties, tube = the station reach band, cap = the road
    # cap — drawn by the SAME taut string the airside spine profile uses
    # (``corridor_profile.solve_run_profile`` -> ``string_with_pegs``;
    # one construction, never a second solver).
    #
    # What it replaces is the POINTWISE rule kept below as the fallback:
    # ``tgt = min(max(de, lo), c)`` clamps each station's own DEM sample
    # into its own band, independently of the run it belongs to.  Against
    # a cap-Lipschitz envelope that is a bang-bang operator by
    # construction, and it is what HECA's spines measured — a 6.18 m
    # cap-ridden hump at 30.11268,31.40684 with no anchor within 60 m,
    # +/-8 % cap-riding flank runs, and -25 %/-19 % discharge pockets
    # (the ``floor > ceiling`` distance-weighted blend, which was a
    # quarantine export, not a profile).
    #
    # Band-lawful displacement TRUMPS DEM in the interior, so DEM enters
    # only as an end tie on an under-pegged run and as a reported
    # displacement.  FLAT IS LAWFUL (owner 2026-08-14, drainage scope):
    # no minimum slope is minted here.  Conflicts — an inverted tube, a
    # peg pair whose rise the run cannot absorb at the cap — are RECORDED
    # with their numbers on ``layout._svc_profile_conflicts`` and never
    # blended away (feasibility-is-guaranteed: report, never quarantine).
    # R5 — ROAD RUNS TRACK TERRAIN (service-road law spec, owner-ratified
    # 2026-08-15).  The taut string draws the STRAIGHTEST lawful profile;
    # for a ROAD that is a causeway over every dip and a canyon through
    # every rise (CYXY 349: 5.2 m over a 2.7 % dip at 0.4 % grade; the
    # junction-190 complex flat at ~706 under 718-722 m HRDEM; HECA an
    # elevated plateau).  A service-road run's profile is the
    # CAP-CONSTRAINED LEAST-DEVIATION TRACKER of its low-passed station
    # DEM — same tube, same pegs, same cap, same audit, terrain as the
    # objective.  The taut string stays the AIRSIDE spine form
    # (``construct_taut_strings``), untouched.
    from .corridor_profile import track_dem_profile as _track_run

    # A LINE IS NOT A RUN.  A service seed line is an OSM/apt course that
    # may run kilometres past the airport; stations exist only where the
    # build actually emitted road pavement.  Two station groups separated
    # by a hole in the pavement are two law objects, not one corridor
    # with a very long span — stringing across the hole would make the
    # solve draw a chord over ground it paves nothing on.  The split is
    # STRUCTURAL, not tuned: stations are laid at ``SPINE_STEP_M`` (the
    # step ``insert_lateral_spine_nodes`` densifies to), so a gap wider
    # than two steps means at least one station is MISSING — no
    # cross-section there, no pavement, no run.
    from auto_patch.config import SPINE_STEP_M as _STEP
    _RUN_BREAK_M = 2.0 * _STEP
    _free_end_idx = getattr(layout, "_svc_free_end_idx", None) or set()
    _by_line: dict = {}
    for sid, st in enumerate(stations):
        if not st["members"]:
            continue                    # merged away — its root carries it
        _by_line.setdefault(st["line"], []).append(sid)
    runs: dict = {}
    for _ln, _all in _by_line.items():
        _all.sort(key=lambda k: stations[k]["s"])
        _part = 0
        for _n, sid in enumerate(_all):
            if _n and (stations[sid]["s"] - stations[_all[_n - 1]]["s"]
                       > _RUN_BREAK_M):
                _part += 1
            runs.setdefault((_ln, _part), []).append(sid)

    conflicts_out = list(getattr(layout, "_svc_profile_conflicts", None) or ())
    audits_out = list(getattr(layout, "_svc_profile_audits", None) or ())
    _m_to_ll = getattr(layout, "m_to_ll", None)
    profiled: set = set()
    # R1 (service-road law spec): stations the run's own audit releases
    # from the hold, and the per-run report rows (run id, count, worst
    # grade) the spec requires.
    _law_release: set = set()
    _law_release_runs: list = []
    # R5 SCOPE: stations the R4 span rule leaves UNSTRUNG (a run with
    # <= 1 law target, and the stretches outside a run's pegged span)
    # now take the SAME tracker with whatever pegs are in their scope
    # (outside a span: none) instead of the pointwise station clamp —
    # "strung and unstrung stretches converge in character, healing
    # their seam".  R4's other half STANDS: these stations join no
    # ``svc_profile`` hold and no R1 accounting; the tracker replaces
    # only their VALUE rule, and they stay seeds exactly as the
    # pointwise clamp left them (they keep their fallback cross-section
    # group for the neighbour-term pass).
    _tracked_free: set = set()
    _tracked_free_groups: list = []

    def _track_unpegged(_li, a, b, run_s, run_f, run_c, run_de, run_xy,
                        run_sid, run_pegs):
        """Track [a..b] (run-local indices) as terrain, in maximal
        contiguous stretches of stations that HAVE a DEM sample — a
        station without one has no terrain to track and keeps the
        existing fallback."""
        if b < a:
            return
        k = a
        while k <= b:
            if run_de[k] is None:
                k += 1
                continue
            j = k
            while j + 1 <= b and run_de[j + 1] is not None:
                j += 1
            if j > k:
                _pg = {q - k: run_pegs[q] for q in run_pegs if k <= q <= j}
                _pr = _track_run(run_s[k:j + 1], run_f[k:j + 1],
                                 run_c[k:j + 1], _pg, cap,
                                 dem=run_de[k:j + 1], xy=run_xy[k:j + 1])
                if _pr is not None:
                    for _q, _sid in enumerate(run_sid[k:j + 1]):
                        _tgt = float(_pr.z[_q])
                        for _i in stations[_sid]["members"]:
                            node_target[_i] = _tgt
                        _tracked_free.add(_sid)
                        _tracked_free_groups.append(
                            frozenset(stations[_sid]["members"]))
                    _a = _pr.audit
                    audits_out.append({
                        "line": _li[0], "part": _li[1], "scope": "unpegged",
                        "stations": j - k + 1, "segments": _a.segments,
                        "length_m": run_s[j] - run_s[k],
                        "pegs": len(_pr.pegs), "synthetic_end_ties": 0,
                        "worst_grade": _a.worst_grade,
                        "over_cap_segments": _a.over_cap_segments,
                        "cap_ride_runs": _a.cap_ride_runs,
                        "cap_ride_segments": _a.cap_ride_segments,
                        "cap_ride_length_m": _a.cap_ride_length_m,
                        "dem_departure_stations": _a.dem_departure_stations,
                        "dem_departure_max_m": _a.dem_departure_max_m,
                        "reversals_collapsed": _a.reversals_collapsed,
                        "reversals_kept": _a.reversals_kept,
                        "reversal_max_amplitude_m":
                            _a.reversal_max_amplitude_m})
            k = j + 1

    for _li, _sids in runs.items():
        run_s: list = []
        run_f: list = []
        run_c: list = []
        run_de: list = []
        run_xy: list = []
        run_sid: list = []
        run_pegs: dict = {}
        for sid in _sids:
            st = stations[sid]
            s_val = float(st["s"])
            if run_s and s_val <= run_s[-1] + 1e-9:
                continue                # coincident station — one entry
            m_ceil = [node_ceil[i] for i in st["members"] if i in node_ceil]
            m_floor = [node_floor[i] for i in st["members"] if i in node_floor]
            av = [anchors[i] for i in st["members"] if i in anchors]
            k = len(run_s)
            run_s.append(s_val)
            run_c.append(min(m_ceil) if m_ceil else float("inf"))
            run_f.append(max(m_floor) if m_floor else float("-inf"))
            run_de.append(smooth_de.get(sid))
            run_xy.append(st_xy[sid])
            run_sid.append(sid)
            if av:
                # A station's welds are ONE cross-section value (the
                # spine-first law); their mean is that value.  EXCEPT at
                # a FREE END: that tie is a LAW TARGET (the corridor
                # terminus grades to ambient DEM under its own cap,
                # RULINGS 2026-08-12b), so it is the station's value
                # outright — averaging it against a neighbouring weld
                # left the cross-section partners off the tie and the
                # acceptance instrument read the partner, not the tie
                # (measured: HECA free ends over the floor 36 -> 40,
                # worst 3.256 m at 30.1119707,31.3731240).
                _fe = [anchors[i] for i in st["members"] if i in anchors
                       and i in _free_end_idx]
                run_pegs[k] = (sum(_fe) / len(_fe) if _fe
                               else sum(av) / len(av))
        if len(run_s) < 2:
            continue
        # R4 (service-road law spec): THE STRING HOLDS ON THE PEGGED
        # SPAN ONLY.  Pegs are the corridor's law targets, and the 1-D
        # string is the law object BETWEEN targets; beyond the
        # outermost pegged stations there is nothing lawful to string
        # to, so those stations keep the pointwise station rule below
        # (DEM-follow — the band is wide there by construction).
        # Measured: run (46,0) at HECA, 2,364.6 m with pegs only at
        # s=0/3.0/7.2 m, strung FLAT at the south mouths' 127.21 across
        # its whole length and stamped the -11585 junction 37.6 m over
        # ambient; a synthetic far-end DEM tie instead re-draws the run
        # as a km-scale chord (the census-invisible ridge class the
        # warm-start retirement named).  A run with <= 1 peg is not
        # strung at all — same principle, zero targets to string
        # between.
        _span = _r4_pegged_span(run_pegs)
        if _span is None:
            # <= 1 law target: R4 leaves the run unstrung — R5 tracks it.
            _track_unpegged(_li, 0, len(run_s) - 1, run_s, run_f, run_c,
                            run_de, run_xy, run_sid, run_pegs)
            continue
        _lo_k, _hi_k = _span
        # Outside the pegged span there is nothing lawful to string to;
        # the tracker applies there with NO pegs in scope (R5 SCOPE).
        _track_unpegged(_li, 0, _lo_k - 1, run_s, run_f, run_c,
                        run_de, run_xy, run_sid, run_pegs)
        _track_unpegged(_li, _hi_k + 1, len(run_s) - 1, run_s, run_f,
                        run_c, run_de, run_xy, run_sid, run_pegs)
        run_s = run_s[_lo_k:_hi_k + 1]
        run_f = run_f[_lo_k:_hi_k + 1]
        run_c = run_c[_lo_k:_hi_k + 1]
        run_de = run_de[_lo_k:_hi_k + 1]
        run_xy = run_xy[_lo_k:_hi_k + 1]
        run_sid = run_sid[_lo_k:_hi_k + 1]
        run_pegs = {k - _lo_k: v for k, v in run_pegs.items()}
        prof = _track_run(run_s, run_f, run_c, run_pegs, cap,
                          dem=run_de, xy=run_xy)
        if prof is None:
            continue                    # under-determined run → fallback
        for k, sid in enumerate(run_sid):
            tgt = float(prof.z[k])
            for i in stations[sid]["members"]:
                node_target[i] = tgt
            profiled.add(sid)
        _rel = _profile_law_release(prof.conflicts, run_sid)
        if _rel:
            _law_release |= _rel
            _law_release_runs.append(
                {"line": _li[0], "part": _li[1], "released": len(_rel),
                 "worst_grade": prof.audit.worst_grade})
        for cf in prof.conflicts:
            rec = {
                "line": _li[0], "part": _li[1], "kind": cf.kind, "s_m": cf.station_s_m,
                "cap": cf.cap, "floor": cf.floor, "ceiling": cf.ceiling,
                "deficit_m": cf.deficit_m, "rise_m": cf.rise_m,
                "run_m": cf.run_m, "required_grade": cf.required_grade,
                "text": cf.describe()}
            if cf.xy is not None and _m_to_ll is not None:
                try:
                    _la, _lo = _m_to_ll(cf.xy[0], cf.xy[1])
                    rec["lat"], rec["lon"] = round(_la, 11), round(_lo, 11)
                except Exception:                        # pragma: no cover
                    pass
            conflicts_out.append(rec)
        a = prof.audit
        audits_out.append({
            "line": _li[0], "part": _li[1], "scope": "pegged",
            "stations": len(run_s), "segments": a.segments,
            "length_m": run_s[-1] - run_s[0], "pegs": len(prof.pegs),
            "synthetic_end_ties": prof.synthetic_end_ties,
            "worst_grade": a.worst_grade,
            "over_cap_segments": a.over_cap_segments,
            "cap_ride_runs": a.cap_ride_runs,
            "cap_ride_segments": a.cap_ride_segments,
            "cap_ride_length_m": a.cap_ride_length_m,
            "dem_departure_stations": a.dem_departure_stations,
            "dem_departure_max_m": a.dem_departure_max_m,
            "reversals_collapsed": a.reversals_collapsed,
            "reversals_kept": a.reversals_kept,
            "reversal_max_amplitude_m": a.reversal_max_amplitude_m})

    layout._svc_profile_conflicts = conflicts_out
    layout._svc_profile_audits = audits_out
    # THE PROFILE IS THE CORRIDOR'S BAND (round spec: "the corridor
    # profile then enters stage B as ONE band consumed by seats/
    # endpoints").  Membership is published here; the caller mints it as
    # a canonical keyset and the projections hold it, exactly as the
    # free-end DEM tie is held — and for the same measured reason: as a
    # SOFT seed the whole-run profile is written and then written over
    # (measured at HECA, arm 86903a2b43f3: 37 cap-riding runs and a
    # 16.1 m hump still emitted from a profile that had neither).
    # ── THE 1-D VALIDITY TEST (Fable ruling 2026-08-14: the profile
    # holds only where the corridor is GENUINELY one-dimensional) ─────
    # A profile is 1-D in ARCLENGTH; the within-shape law is 2-D in
    # PLAN.  Where a run doubles back — a loop road's return leg, a ramp
    # switchback, a junction ribbon that wraps — two stations far apart
    # in arclength sit within a road width of each other in plan, and
    # their arclength-lawful values are a within-shape violation the
    # HOLD would freeze in.  Measured at KCLT: +187 new
    # ``within_shape::service_junction`` rows on shapes of mean width
    # 3.8-9.3 m — LINEAR ribbons, not yards, so the run/yard scoping
    # cannot see them.  (The existing station merge cannot either: its
    # XY window skips pairs of the SAME line by construction.)
    #
    # The test is the law itself: a plan pair whose profile values
    # exceed the cap over their plan distance is not one-dimensional
    # there.  Both stations are RELEASED from the hold — they keep the
    # profile as their seed and solve as a surface — and the pair is
    # recorded.  Nothing is quarantined.
    _not_1d: set = set()
    if profiled:
        _CELL = ROAD_CARVE_MAX_WIDTH_M
        _grid2: dict = {}
        for sid in profiled:
            x, y = st_xy[sid]
            _grid2.setdefault((int(x // _CELL), int(y // _CELL)),
                              []).append(sid)
        _seen: set = set()
        for (cx, cy), cell in _grid2.items():
            neigh = []
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    neigh.extend(_grid2.get((cx + ox, cy + oy), ()))
            for a in cell:
                ax, ay = st_xy[a]
                za = node_target.get(next(iter(stations[a]["members"]), None))
                if za is None:
                    continue
                for b in neigh:
                    if b <= a or (a, b) in _seen:
                        continue
                    _seen.add((a, b))
                    bx, by = st_xy[b]
                    d = _m.hypot(ax - bx, ay - by)
                    if d > _CELL or d < 1e-6:
                        continue
                    zb = node_target.get(
                        next(iter(stations[b]["members"]), None))
                    if zb is None:
                        continue
                    if abs(za - zb) > cap * d + 0.01:
                        _not_1d.add(a)
                        _not_1d.add(b)
                        conflicts_out.append({
                            "line": stations[a]["line"], "part": None,
                            "kind": "not_one_dimensional",
                            "s_m": stations[a]["s"], "cap": cap,
                            "rise_m": abs(za - zb), "run_m": d,
                            "required_grade": abs(za - zb) / d,
                            "text": (f"plan pair {d:.1f} m apart carries "
                                     f"{abs(za - zb):.2f} m — the run is "
                                     f"not 1-D here; released from the "
                                     f"hold")})
        layout._svc_profile_conflicts = conflicts_out
    layout._svc_profile_not_1d_stations = len(_not_1d)
    # R1 (service-road law spec): the audit-released stations leave the
    # hold membership exactly as the not-1-D stations do — they never
    # enter the ``svc_profile`` keyset; ``node_target`` keeps the
    # profile value as their seed.
    layout._svc_profile_law_released_stations = len(_law_release)
    layout._svc_profile_law_release_runs = _law_release_runs
    layout._svc_profile_members = {
        i for sid in profiled if sid not in _not_1d
        and sid not in _law_release
        for i in stations[sid]["members"]}
    if _law_release_runs:
        import O4_UI_Utils as _UI_r1
        _per_run = "; ".join(
            f"run ({r['line']},{r['part']}): {r['released']} station(s), "
            f"worst {r['worst_grade'] * 100:.2f} %"
            for r in _law_release_runs)
        _UI_r1.vprint(1,
            f"  [pav-builder] R1 held-profile validity release: "
            f"{len(_law_release)} station(s) released from the "
            f"svc_profile hold on {len(_law_release_runs)} run(s) "
            f"(over-cap segment / relaxed inverted tube — values stay "
            f"as seeds): {_per_run}")
    if audits_out:
        import O4_UI_Utils as _UI_cp
        _n_over = sum(x["over_cap_segments"] for x in audits_out)
        _n_ride = sum(x["cap_ride_runs"] for x in audits_out)
        _worst = max((x["worst_grade"] for x in audits_out), default=0.0)
        _n_dep = sum(x.get("dem_departure_stations", 0) for x in audits_out)
        _worst_dep = max((x.get("dem_departure_max_m", 0.0)
                          for x in audits_out), default=0.0)
        _n_rev = sum(x.get("reversals_collapsed", 0) for x in audits_out)
        _n_kept = sum(x.get("reversals_kept", 0) for x in audits_out)
        _worst_rev = max((x.get("reversal_max_amplitude_m", 0.0)
                          for x in audits_out), default=0.0)
        _UI_cp.vprint(1,
            f"  [pav-builder] R5c reversal suppression: {_n_rev} grade "
            f"reversal(s) collapsed into monotone bridges (worst interior "
            f"amplitude {_worst_rev:.3f} m, floor "
            f"{SVC_PROFILE_REVERSAL_MIN_M:.2f} m); {_n_kept} real "
            f"direction change(s) kept.")
        _UI_cp.vprint(1,
            f"  [pav-builder] whole-run corridor profile (R5: roads TRACK "
            f"terrain): {len(audits_out)} run(s), {len(profiled)} held "
            f"station(s) + {len(_tracked_free)} unpegged tracked; "
            f"worst grade {_worst * 100:.2f} % (cap {cap * 100:.2f} %), "
            f"{_n_over} over-cap segment(s), {_n_ride} cap-riding run(s), "
            f"{len(conflicts_out)} reported conflict(s); cap-departure "
            f"from DEM at {_n_dep} station(s), worst {_worst_dep:.2f} m "
            f"(audit only — DEM deviation is not a reported defect).")
        for _c in conflicts_out[:8]:
            _UI_cp.vprint(2,
                f"      [corridor-profile] line {_c['line']}: {_c['text']}"
                + (f" at {_c['lat']},{_c['lon']}" if "lat" in _c else ""))

    # ── FALLBACK: the pointwise station clamp, for stations no run
    # profiled (a line with a single usable station, or no peg and no DEM
    # to tie an end to).  Unchanged behaviour, including its break blend
    # and its quarantine export — those stations are not corridors the
    # whole-run law can reach.  Each non-broken fallback STATION is
    # recorded as one cross-section GROUP for the caller's neighbour-term
    # pass (finalarch item 4): the clamp below is a per-station band
    # clamp with no neighbour term, so DEM-follow noise between ADJACENT
    # stations is unbounded by cap exactly where the whole-run law never
    # reached.
    _fb_groups: list = list(_tracked_free_groups)
    layout._svc_station_fallback_groups = _fb_groups
    layout._svc_profile_tracked_free_stations = len(_tracked_free)
    for sid, st in enumerate(stations):
        if not st["members"] or sid in profiled or sid in _tracked_free:
            continue
        de = smooth_de.get(sid)
        if de is None:
            continue                    # no DEM sample → legacy per-vertex
        m_ceil = [node_ceil[i] for i in st["members"] if i in node_ceil]
        m_floor = [node_floor[i] for i in st["members"] if i in node_floor]
        c = min(m_ceil) if m_ceil else None
        f = max(m_floor) if m_floor else None
        broken = False
        if c is None:                   # unreachable from any anchor → DEM
            tgt = de
        elif f is not None and f > c + 1e-9:
            # genuine break — SAME distance-weighted blend as the
            # per-vertex operator, computed once for the cross-section
            # (weights = mean member reach distances to each regime).
            dcs = [node_ceil_dist[i] for i in st["members"]
                   if i in node_ceil_dist]
            dfs = [node_floor_dist[i] for i in st["members"]
                   if i in node_floor_dist]
            dc = (sum(dcs) / len(dcs)) if dcs else 0.0
            df = (sum(dfs) / len(dfs)) if dfs else 0.0
            t = dc / (dc + df) if (dc + df) > 1e-9 else 0.5
            tgt = c + (f - c) * t
            broken = True
        else:
            lo = f if f is not None else -float("inf")
            tgt = min(max(de, lo), c)
        for i in st["members"]:
            node_target[i] = tgt
            if broken:
                broken_nodes.add(i)
        if not broken:
            _fb_groups.append(frozenset(st["members"]))
        if _dbg_xy is not None:
            sx, sy = st_xy[sid]
            if _m.hypot(sx - _dbg_xy[0], sy - _dbg_xy[1]) < 12.0:
                print(f"    [svc-spine-dbg] sid={sid} line={st['line']} "
                      f"s={st['s']:.1f} n={st['n']} de_raw={raw_de.get(sid)} "
                      f"de={de:.2f} ceil={c} floor={f} "
                      f"tgt={tgt:.2f} broken={broken} FALLBACK "
                      f"members={sorted(st['members'])}")
    if _dbg_xy is not None:
        for sid in sorted(profiled):
            sx, sy = st_xy[sid]
            if _m.hypot(sx - _dbg_xy[0], sy - _dbg_xy[1]) < 12.0:
                st = stations[sid]
                any_m = st["members"][0] if st["members"] else None
                print(f"    [svc-spine-dbg] sid={sid} line={st['line']} "
                      f"s={st['s']:.1f} n={st['n']} de={smooth_de.get(sid)} "
                      f"tgt={node_target.get(any_m)} WHOLE-RUN "
                      f"members={sorted(st['members'])}")
    return node_target, broken_nodes


def reseat_service_mouths(layout, b2i, elev, n, *, crown_of=None):
    """RE-DERIVE every held service-road mouth seat from the airside
    edge's CURRENT value — the last airside-final moment.

    Owner law 2026-08-15 ("a service road meeting a taxiway must arrive
    AT that pavement's elevation") + the timing adjudication that
    followed this lane's attempt-2 measurement.  The seat itself was
    never wrong; WHEN it was taken was.  ``apply_service_road_dem_follow``
    runs while the airside surface is still moving: at every failing HECA
    site the seat moved the road 0.03-0.28 m — the two agreed at the time
    — and the apron then travelled 5-9 m before emit, so the hold pinned
    a stale value with perfect fidelity.

    THE RULE LIVES HERE, at module level, so the twins drive the rule the
    pass applies instead of re-implementing it (``classify_projection_
    hard``'s discipline).  It is a PURE LOOKUP: the recipe minted by the
    DEM-follow pass is the edge's two endpoint canonical KEYS and the
    interpolation parameter of the perpendicular foot, resolved through
    the one resolver, so this never rebuilds an index — the geometry is
    frozen by now, only values moved.

    ``crown_of`` is the caller's z′ frame: endpoints are read UNCROWNED
    (the runway partner's crown is a designed sub-cap offset, not part of
    the value a truck arrives at) and the seat is written back into the
    caller's frame — the ``elev[i] - _crown_of[i]`` / ``+ _crown_of[i]``
    spelling ``final_grade_projection`` already uses.

    Returns ``(reseated, worst_move_m)``; an unresolvable side is skipped,
    never guessed.
    """
    store = _store_of(layout)
    edge_a = store.view_relation("svc_mouth_edge_a", b2i, n)
    if not edge_a:
        return (0, 0.0)
    edge_b = store.view_relation("svc_mouth_edge_b", b2i, n)
    t_of = store.view_scalar("svc_mouth_t", b2i, n)
    crown = crown_of or {}
    reseated = 0
    worst = 0.0
    for i, ai in sorted(edge_a.items()):
        bi = edge_b.get(i)
        t = t_of.get(i)
        if (ai is None or bi is None or t is None
                or i >= len(elev) or ai >= len(elev) or bi >= len(elev)):
            continue
        za = float(elev[ai]) - crown.get(ai, 0.0)
        zb = float(elev[bi]) - crown.get(bi, 0.0)
        z = za + float(t) * (zb - za) + crown.get(i, 0.0)
        move = abs(z - float(elev[i]))
        if move > 1e-9:
            elev[i] = z
            reseated += 1
            worst = max(worst, move)
    return (reseated, worst)


def apply_service_road_dem_follow(layout, bucket_to_idx, elev, dem_elev, cap,
                                  anchor_extra=()):
    """Grade the service-road network to FOLLOW DEM at <=cap (user 2026-06-27).

    A ground-vehicle road is NOT airside: it rises/falls toward terrain, anchored
    only where it WELDS to the airside (taxi/apron/runway, kept at their solved
    bowl elevation) or to a groundside piece (``anchor_extra``).  Every other
    service node sits at ``clamp(DEM, reach-band-from-anchors-at-cap)`` where the
    reach band is the cap-Lipschitz envelope along the SERVICE graph (axial, edge by
    edge) — so a road ramps from its airside connection toward DEM at <=4% instead
    of being held flat in the bowl (SVC4 was ~6-11 m below terrain).  The
    road-vs-airside seam is by design (``check_grade._airside_groundside_pair``), so
    rising past a flat neighbour is not a step.

    SPINE-FIRST (config.SVC_SPINE_FIRST, default ON, part 30m): the DEM target
    is computed per spine STATION (shared by the whole cross-section) instead
    of per vertex — see ``_svc_spine_station_seeds``.  ``O4_SVC_SPINE_FIRST=0``
    restores the per-vertex behaviour below byte-identically.

    Mutates ``elev`` in place; returns the set of node indices it moved."""
    import heapq
    import os as _os
    from collections import defaultdict
    from auto_patch.layout import (
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION, ROLE_GROUNDSIDE_PAVEMENT)

    cps = layout.canonical_points

    def _key(x, y):
        return cps.get_or_add(float(x), float(y))

    SVC = (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
    # THE ONE LAW'S CAP (owner 2026-08-03, docs/RULINGS.md
    # "lateral-contiguity absorption is class-universal"; spec §1).  A road
    # stretch that is laterally contiguous with another paved class is part
    # of THAT surface: the stretch the emitter could absorb is not a service
    # shape at all any more, and a stretch it could only CAP carries the
    # cross-section's strictest cap in ``BuiltShape.lateral_cap``.  This
    # envelope consumes that number instead of its private service cap — one
    # surface, one cap, one authority — and stops exporting those nodes to
    # the break quarantine (a residual there is the contiguous surface's
    # law, i.e. a VISIBLE violation, not a second authority's pocket).
    # Gate off ⇒ ``lat_cap`` stays empty ⇒ the scalar ``cap`` arithmetic and
    # the export are unchanged, byte for byte.
    from auto_patch.config import SERVICE_LOT_ABSORPTION as _CLASS_UNIVERSAL
    lat_cap: dict = {}
    svc_nodes: set = set()
    adj = defaultdict(list)
    node_pos: dict = {}
    node_shape: dict = {}
    # R5c(2): EVERY service shape a vertex belongs to (``node_shape``
    # above keeps only the first — it exists to answer "same shape?").
    # A weld vertex is shared by a road and the junction it feeds, and
    # that shared membership is exactly what makes them ONE corridor.
    node_shapes: dict = {}
    for s in layout.shapes:
        if s.role not in SVC or s.polygon is None or s.polygon.is_empty:
            continue
        _lc = getattr(s, "lateral_cap", None) if _CLASS_UNIVERSAL else None
        # Amendment 2 clause 1 — READER 2 of the PER-STATION vector: a
        # node's envelope cap is the cap of the station it stands in, not
        # the ring-wide scalar, so a road's free stretch is not held at
        # the apron's 1 % just because its other end runs alongside one.
        _sv = list(getattr(s, "station_cap_vector", None) or ())
        ring = _open_ring(list(s.polygon.exterior.coords))
        idxs = [bucket_to_idx.get(_key(x, y)) for (x, y) in ring]
        for k in range(len(ring)):
            i, j = idxs[k], idxs[(k + 1) % len(ring)]
            if i is None or i >= len(elev):
                continue
            svc_nodes.add(i)
            _node_cap = _lc
            if _sv:
                from auto_patch.lateral_contiguity import cap_at as _cap_at
                _sc = _cap_at(_sv, float(ring[k][0]), float(ring[k][1]),
                              None)
                if _sc is not None:
                    _node_cap = (float(_sc) if _lc is None
                                 else min(float(_lc), float(_sc)))
            if _node_cap is not None:
                _prev = lat_cap.get(i)
                lat_cap[i] = (float(_node_cap) if _prev is None
                              else min(_prev, float(_node_cap)))
            node_pos.setdefault(i, ring[k])
            node_shape.setdefault(i, id(s))
            _ns = node_shapes.setdefault(i, [])
            if not any(o is s for o in _ns):
                _ns.append(s)
            if j is not None and j != i and j < len(elev):
                import math as _m
                dd = _m.hypot(ring[k][0] - ring[(k + 1) % len(ring)][0],
                              ring[k][1] - ring[(k + 1) % len(ring)][1])
                adj[i].append((j, dd))
                adj[j].append((i, dd))
    if not svc_nodes:
        return set()

    # PROXIMITY COUPLING between near-parallel roads (user 2026-07-06,
    # HECA #510↔#517): two service shapes whose free edges run < ~2 m
    # apart carry NO shared node, so each grades to its OWN anchors and
    # the pair can emit a metre-scale wall across an unrenderable sliver
    # (measured 1.8 m over 0.9 m).  Couple nodes of DIFFERENT service
    # shapes within the window into the reach graph — both roads then
    # grade against the union of their anchors at ≤cap across the gap,
    # and genuinely contradictory anchors resolve through the same
    # break blend as any interior node.
    prox_pairs: list = []       # (i, j) couples — also merges spine stations
    import math as _m
    _PROX_M = 2.0
    _cell = _PROX_M
    _grid: dict = {}
    for i, (px, py) in node_pos.items():
        _grid.setdefault((int(px // _cell), int(py // _cell)),
                         []).append(i)
    for (cx, cy), members in _grid.items():
        neighbors = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neighbors.extend(_grid.get((cx + ox, cy + oy), ()))
        for i in members:
            (ix, iy) = node_pos[i]
            for j in neighbors:
                if (j <= i
                        or node_shape.get(j) == node_shape.get(i)):
                    continue
                (jx, jy) = node_pos[j]
                dd = _m.hypot(ix - jx, iy - jy)
                if 1e-6 < dd <= _PROX_M:
                    adj[i].append((j, dd))
                    adj[j].append((i, dd))
                    prox_pairs.append((i, j))

    # Anchors = service nodes that are ALSO a corner of a NON-service pavement shape
    # (the road welds to the airside there), held at their solved elevation; plus
    # any groundside-welded nodes passed in.
    #
    # ── STAGE-AWARE (finalarch item 5; S1f dossier item 5b) ──────────
    # Every anchor carries the STAGE of the ring(s) that minted it — the
    # first-class tag, never a role literal (``solve_stage``).  The two
    # reach regimes (``_reach(+1)`` / ``_reach(-1)``) used to run over
    # one stage-blind anchor set, so a stage-A weld and a stage-B weld
    # whose values are incompatible under the cap metric met inside the
    # tube as ``floor > ceil`` — 1,631 recorded inverted-tube conflicts
    # at HECA that could not be partitioned into real-vs-cross-stage.
    # Airside is king: a node ANY airside ring claims is stage A
    # (``stage_of_roles``' own rule).
    from auto_patch.solve_stage import STAGE_A, STAGE_B, stage_of_shape
    # ── PROXIMITY MOUTH ANCHORS (owner law 2026-08-15) ────────────────
    # "A service road meeting a taxiway (or any airside pavement) must
    # arrive AT that pavement's elevation — exactly like roads meeting
    # runways."  AIRSIDE IS KING: the road conforms, the airside value is
    # read-only.
    #
    # THE MEASURED DEFECT: the exact-vertex loop below anchors a service
    # node only where it IS a canonical vertex of a non-service ring.  A
    # road that ABUTS without a weld gets no anchor at all — and abutting
    # without a weld is the NORMAL state, not the exception: the corridor
    # minter cuts the body back from aircraft pavement by
    # ``_PAV_CLEAR_TOL_M`` = 1.0 m while conformance welds only within
    # ``SHARED_VERTEX_TOL_M`` = 0.5 m, and the mouth fill that closes that
    # annulus has a terminus hole.  Measured at HECA: of 187 road↔airside
    # contact sites, all 127 WELDED ones step 0.000 m, while 34 of the 60
    # unwelded ones step > 0.3 m (max 9.135 m — a cliff at the kerb).
    #
    # THE FIX: anchor any service node within ``_PAV_CLEAR_TOL_M +
    # SHARED_VERTEX_TOL_M`` of an AIRCRAFT-PAVEMENT ring EDGE — the widest gap
    # the cut-back can open plus the weld tolerance it fails to reach, so
    # the number is DERIVED from the two constants that mint the gap, not
    # a new one — at that edge's INTERPOLATED already-solved elevation at
    # the node's perpendicular foot, tagged with the minting ring's stage
    # exactly as an exact-vertex anchor is.  Exact-vertex anchors keep
    # precedence (a node already anchored is never re-read).  From there
    # the existing ``_reach`` band does the rest: the road ramps away
    # from the mouth value at <= its own cap.
    #
    # ── THE CARRIER IS AIRCRAFT PAVEMENT ONLY (adjudication 2026-08-15,
    # on this lane's attempt-1 measurement) ──────────────────────────
    # The seat's authority is the owner's law — "arrive AT the TAXIWAY's
    # (runway's, apron's) elevation" — so the edge index is built from
    # ``enclaves.ENCLAVE_AIRSIDE_ROLES``, THE canonical airside-pavement
    # family (imported, never re-spelled: blast.py's role-literal
    # hazard), and from nothing else.  Attempt 1 indexed the whole
    # non-service population the exact-vertex loop walks, and measured
    # the cost at HECA: of 141 seats, 52 were minted by a
    # ``graded_strip`` and 42 by a ``building`` ring against only 35 from
    # real pavement.  A graded strip is the road's OWN grading product
    # riding at the road's own level, so such a seat PINS the road at
    # exactly the value the law wants replaced (measured: seat 102.079 at
    # d = 0.00 m from strip -13003, facing an apron at 93.01).  Buildings
    # are stage-B seats, not a surface a truck arrives at.  The
    # exact-vertex loop's population is UNCHANGED — a genuinely shared
    # vertex is a weld, and a weld's value is authoritative whatever
    # welded it.
    # ``O4_SVC_MOUTH_PROX_ANCHOR=0`` restores the exact-vertex-only
    # anchor set byte-identically.
    from auto_patch.config import SVC_MOUTH_PROX_ANCHOR as _MOUTH_PROX
    from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES as _MOUTH_ROLES
    from auto_patch.layout import SHARED_VERTEX_TOL_M as _WELD_TOL_M
    from auto_patch.pavement.service_roads import (
        _PAV_CLEAR_TOL_M as _PAV_CLEAR_M)
    _MOUTH_TOL_M = _PAV_CLEAR_M + _WELD_TOL_M            # 1.5 m, derived
    # Grid cell for the edge index — the ``_PROX_M`` pattern above.  The
    # stamp walks each segment at one CELL per step, so the sample
    # nearest a node's perpendicular foot is within
    # ``hypot(_MOUTH_TOL_M, CELL/2)`` = 1.803 m of the node, which the
    # 3x3 cell window (radius CELL = 2.0 m, L-infinity) contains: the
    # query is exact, not approximate.
    _MOUTH_CELL = 2.0
    _mouth_segs: list = []     # (ax, ay, az, bx, by, bz, stage)
    _mouth_grid: dict = {}
    _mouth_cells: set = set()  # only cells a service node can query
    if _MOUTH_PROX:
        for (_px, _py) in node_pos.values():
            _cx, _cy = int(_px // _MOUTH_CELL), int(_py // _MOUTH_CELL)
            for _ox in (-1, 0, 1):
                for _oy in (-1, 0, 1):
                    _mouth_cells.add((_cx + _ox, _cy + _oy))
    anchors: dict = {}
    anchor_stage: dict = {}
    for s in layout.shapes:
        if (s.role in SVC or s.role == ROLE_GROUNDSIDE_PAVEMENT
                or s.polygon is None or s.polygon.is_empty):
            continue
        _s_stage = stage_of_shape(s)
        _ring = _open_ring(list(s.polygon.exterior.coords))
        _ring_idx: list = []
        for (x, y) in _ring:
            i = bucket_to_idx.get(_key(x, y))
            _ring_idx.append(i)
            if i in svc_nodes:
                anchors[i] = elev[i]
                if anchor_stage.get(i) != STAGE_A:
                    anchor_stage[i] = _s_stage
        if not _mouth_cells or s.role not in _MOUTH_ROLES:
            continue
        # ONE pass over the ring builds both the exact-vertex anchors and
        # the proximity edge index (single-pass principle).  Only an
        # AIRCRAFT-PAVEMENT ring reaches this point.
        _nr = len(_ring)
        for k in range(_nr):
            _i, _j = _ring_idx[k], _ring_idx[(k + 1) % _nr]
            if (_i is None or _j is None
                    or _i >= len(elev) or _j >= len(elev)):
                continue
            (_ax, _ay) = _ring[k]
            (_bx, _by) = _ring[(k + 1) % _nr]
            _sd = _m.hypot(_bx - _ax, _by - _ay)
            _sid = None
            _nst = int(_sd // _MOUTH_CELL) + 1
            for _st in range(_nst + 1):
                _f = min(1.0, (_st * _MOUTH_CELL) / _sd) if _sd > 0.0 else 0.0
                _ck = (int((_ax + _f * (_bx - _ax)) // _MOUTH_CELL),
                       int((_ay + _f * (_by - _ay)) // _MOUTH_CELL))
                if _ck not in _mouth_cells:
                    continue
                if _sid is None:
                    _sid = len(_mouth_segs)
                    # The endpoints' CANONICAL KEYS travel with the
                    # segment: the seat's recipe must outlive this node
                    # space (node_space's law), and the re-derivation
                    # below re-reads these two values, never the
                    # geometry, so nothing rebuilds the index later.
                    _mouth_segs.append((_ax, _ay, float(elev[_i]),
                                        _bx, _by, float(elev[_j]),
                                        _s_stage,
                                        _key(_ax, _ay), _key(_bx, _by)))
                _bucket = _mouth_grid.setdefault(_ck, [])
                if not _bucket or _bucket[-1] != _sid:
                    _bucket.append(_sid)
    _mouth_moved: set = set()
    _mouth_records: list = []
    if _mouth_grid:
        for i in sorted(svc_nodes):
            if i in anchors or i >= len(elev):
                continue
            _p = node_pos.get(i)
            if _p is None:
                continue
            (_px, _py) = _p
            _cx, _cy = int(_px // _MOUTH_CELL), int(_py // _MOUTH_CELL)
            _best = None
            _seen: set = set()
            for _ox in (-1, 0, 1):
                for _oy in (-1, 0, 1):
                    for _sid in _mouth_grid.get((_cx + _ox, _cy + _oy), ()):
                        if _sid in _seen:
                            continue
                        _seen.add(_sid)
                        (_ax, _ay, _az, _bx, _by, _bz,
                         _sstage, _akey, _bkey) = _mouth_segs[_sid]
                        _dx, _dy = _bx - _ax, _by - _ay
                        _l2 = _dx * _dx + _dy * _dy
                        _t = (0.0 if _l2 <= 0.0 else
                              max(0.0, min(1.0, ((_px - _ax) * _dx
                                                 + (_py - _ay) * _dy) / _l2)))
                        _dd = _m.hypot(_px - (_ax + _t * _dx),
                                       _py - (_ay + _t * _dy))
                        if _dd > _MOUTH_TOL_M:
                            continue
                        # Nearest edge wins; ties break on index order, so
                        # the choice is deterministic.
                        if _best is None or (_dd, _sid) < (_best[0], _best[1]):
                            _best = (_dd, _sid, _az + _t * (_bz - _az),
                                     _sstage, _akey, _bkey, _t)
            if _best is None:
                continue
            (_dd, _sid, _z, _sstage, _akey, _bkey, _tfoot) = _best
            _step = abs(_z - float(elev[i]))
            anchors[i] = _z
            if anchor_stage.get(i) != STAGE_A:
                anchor_stage[i] = _sstage
            if _step > 1e-9:
                elev[i] = _z
                _mouth_moved.add(i)
            _mouth_records.append({"i": i, "gap_m": round(_dd, 4),
                                   "value_m": round(_z, 4),
                                   "step_m": round(_step, 4),
                                   "stage": _sstage, "xy": (_px, _py),
                                   "edge_a": _akey, "edge_b": _bkey,
                                   "t": _tfoot})
    layout._svc_mouth_prox_idx = {r["i"] for r in _mouth_records}
    layout._svc_mouth_prox_records = _mouth_records
    # ── THE MOUTH SEAT IS HELD (adjudication 2026-08-15) ──────────────
    # Attempt 1 seated the mouths and let the downstream projections
    # write over them: of 141 seats only 35 survived to emit within
    # 0.01 m, 96 were moved off (median 0.134 m, worst 9.069 m).  That is
    # the free-end tie's OWN measured failure — the SOFT spelling that
    # lost 6.31 m at KCLT — so the cure is its spelling too, not a new
    # mechanism: MEMBERSHIP ONLY, no value write, minted by CANONICAL KEY
    # so it survives the final pass's node-list rebuild (node_space's
    # law), consumed beside ``svc_free_end`` in the yield-hard set and in
    # ``final_grade_projection``'s hard set.  What the hold protects is
    # the owner's law itself: the road ARRIVES at the pavement's value.
    # Everything downstream of the mouth still yields — the road ramps
    # away under its own cap exactly as before.
    # ── …AND RE-DERIVED AT THE LAST AIRSIDE-FINAL MOMENT ─────────────
    # Attempt 2 measured the hold working (64 of 69 seats emitted within
    # 0.01 m) and the ACCEPTANCE still missing, and named why: this pass
    # runs while the airside surface is still moving.  At every failing
    # HECA site the seat moved the road only 0.03-0.28 m — road and apron
    # edge AGREED here — and the apron then travelled 5-9 m before emit,
    # so a perfectly held seat is a perfectly held STALE value.
    #
    # A value seat cannot track a surface that keeps moving, so the seat
    # is re-derived where the surface has stopped: the RECIPE (the edge's
    # two endpoint canonical keys + the interpolation parameter of the
    # perpendicular foot) is minted here, and
    # ``reseat_service_mouths`` re-reads the two CURRENT endpoint values
    # immediately before ``final_grade_projection`` freezes the hold.
    # The geometry is frozen by then — only values moved — so the
    # re-derivation is a pure lookup and no index is ever rebuilt.
    # This is the OBJECT PADS posture (RULINGS 2026-08-14: resolve
    # against the surface's own final value, downstream of the movers)
    # applied to road mouths.  The one-graph alternative — a node-vs-edge
    # LAW PAIR, so road and pavement move together by construction — is
    # the eventual posture and is out of this round's scope.
    if _mouth_records:
        try:
            _store = _store_of(layout)
            _store.mint(
                "svc_mouth", "keyset",
                {_key(*node_pos[i]) for i in layout._svc_mouth_prox_idx
                 if i in node_pos},
                replace=True)
            _rk = {r["i"]: _key(*node_pos[r["i"]]) for r in _mouth_records
                   if r["i"] in node_pos}
            _store.mint("svc_mouth_edge_a", "relation",
                        {_rk[r["i"]]: r["edge_a"] for r in _mouth_records
                         if r["i"] in _rk}, replace=True)
            _store.mint("svc_mouth_edge_b", "relation",
                        {_rk[r["i"]]: r["edge_b"] for r in _mouth_records
                         if r["i"] in _rk}, replace=True)
            _store.mint("svc_mouth_t", "scalar",
                        {_rk[r["i"]]: float(r["t"]) for r in _mouth_records
                         if r["i"] in _rk}, replace=True)
        except Exception:                                # pragma: no cover
            pass
    # ATTRIBUTION DUMP (default off, one env read when unset): the seat this
    # pass wrote, in lat/lon, so a patch-side census can separate "never
    # anchored" from "anchored, then overwritten downstream" without a
    # second instrument of its own.
    _mp_dump = _os.environ.get("O4_SVC_MOUTH_DUMP")
    if _mp_dump and _mouth_records:
        try:
            import json as _json_mp
            _m_to_ll_mp = getattr(layout, "m_to_ll", None)
            _out = []
            for _r in _mouth_records:
                _d = dict(_r)
                if _m_to_ll_mp is not None:
                    _la, _lo = _m_to_ll_mp(*_r["xy"])
                    _d["lat"], _d["lon"] = round(_la, 11), round(_lo, 11)
                _out.append(_d)
            with open(_mp_dump, "w") as _fh:
                _json_mp.dump(_out, _fh, indent=1)
        except Exception:                                # pragma: no cover
            pass
    if _mouth_records:
        import O4_UI_Utils as _UI_mp
        _worst = max(r["step_m"] for r in _mouth_records)
        _UI_mp.vprint(1,
            f"  [pav-builder] service mouth PROXIMITY anchors (owner law "
            f"2026-08-15, airside is king): {len(_mouth_records)} road "
            f"node(s) within {_MOUTH_TOL_M:.1f} m of an AIRCRAFT-PAVEMENT "
            f"ring edge seated AT that edge's interpolated solved value "
            f"and HELD through the projections ({len(_mouth_moved)} moved, "
            f"worst {_worst:.3f} m; {len(_mouth_segs)} indexed edge(s) "
            f"over {len(_MOUTH_ROLES)} airside role(s)).")
    for i in anchor_extra:
        if i in svc_nodes and i < len(elev):
            anchors[i] = elev[i]
            # A groundside-welded node an airside ring also claims keeps
            # its stage-A tag; otherwise it is a stage-B authority.
            anchor_stage.setdefault(i, STAGE_B)

    def _reach(sign, src=None):             # +1 → ceil, −1 → floor
        # Lazy Dijkstra over the (positive) cap·distance metric: the heap
        # pops each node first at its OPTIMAL value, so every later pop
        # is skipped (>= / <=, NO epsilon — an epsilon-tolerant skip lets
        # equal-value duplicates re-expand, which goes combinatorial on
        # service networks with many equal-length parallel paths: CYXY
        # hung for 27 min here).  Each node therefore expands exactly
        # once and pushes are bounded by the edge count.
        best: dict = {}
        dist: dict = {}                     # graph distance to the
        src = anchors if src is None else src
        pq = [((av if sign > 0 else -av), 0.0, a)   # value-optimal anchor
              for a, av in src.items()]
        heapq.heapify(pq)
        while pq:
            v, dk, k = heapq.heappop(pq)
            t = v if sign > 0 else -v
            if k in best:
                continue
            best[k] = t
            dist[k] = dk
            for (j, dd) in adj[k]:
                if j in best:
                    continue
                # ONE cap: where the lateral-contiguity law bound either end
                # of this edge to a contiguous surface, that surface's
                # (strictest) cap prices the leg.  Empty map ⇒ the service
                # cap, exactly as before.
                e_cap = cap
                if lat_cap:
                    e_cap = min(lat_cap.get(k, cap), lat_cap.get(j, cap))
                nt = t + sign * e_cap * dd
                heapq.heappush(pq, ((nt if sign > 0 else -nt),
                                    dk + dd, j))
        return best, dist

    # ── STAGE COMPOSITION AT THE BOUNDARY (finalarch item 5) ─────────
    # Stage A's envelope is computed FIRST, from stage-A anchors alone —
    # the frozen airside reach.  Stage B then reads those values as
    # IMMUTABLE boundary data (the corridor-mouth weld posture, RULINGS
    # 2026-08-14 rim-pocket ruling): a stage-B anchor whose value lies
    # OUTSIDE the stage-A envelope at its own node is two stages
    # disagreeing — it is RECORDED (attribution, ``layout._svc_cross_
    # stage_conform``) and its PROPAGATED value conforms to the
    # envelope, so the contradiction can no longer meet a stage-A wall
    # inside the tube as an uninterpretable ``floor > ceil``.  Residual
    # inversions after this composition are WITHIN-regime conflicts —
    # real, and now attributable as such.  The anchor node's own held
    # elevation is untouched: the disagreement's mint (solve/seat side)
    # stays visible to the census; only the band construction stops
    # propagating it into airside territory.
    from .corridor_profile import MATERIALITY_M as _STAGE_MAT_M
    _stage_a_env = (None, None)
    _cross_stage_records: list = []

    def _composed_anchor_values():
        a_src = {i: v for i, v in anchors.items()
                 if anchor_stage.get(i, STAGE_A) == STAGE_A}
        b_src = {i: v for i, v in anchors.items() if i not in a_src}
        if not a_src or not b_src:
            return dict(anchors)
        nonlocal _stage_a_env
        if _stage_a_env == (None, None):
            _stage_a_env = (_reach(+1, a_src), _reach(-1, a_src))
        (cA, _cAd), (fA, _fAd) = _stage_a_env
        out = dict(a_src)
        for i, v in b_src.items():
            hi = cA.get(i)
            lo = fA.get(i)
            w = float(v)
            if hi is not None and w > hi:
                w = float(hi)
            if lo is not None and w < lo:
                w = float(lo)
            if abs(w - float(v)) > _STAGE_MAT_M:
                _cross_stage_records.append(
                    {"i": i, "value": round(float(v), 3),
                     "conformed": round(w, 3),
                     "xy": node_pos.get(i)})
            out[i] = w
        return out

    _anchor_field = _composed_anchor_values() if anchors else {}
    ceil, ceil_dist = _reach(+1, _anchor_field) if anchors else ({}, {})
    floor, floor_dist = _reach(-1, _anchor_field) if anchors else ({}, {})

    # ── HARD FREE-END DEM TIE (corridor-joins round, ruling 3) ─────────
    # A corridor terminus over open terrain is a LAW TARGET, not a soft
    # seed: the per-vertex seed below already wrote DEM there and the
    # projections downstream simply wrote over it (measured at KCLT
    # 35.2077054,-80.9290667 — 6.31 m proud of DEM, the wall that used to
    # hold the bench removed by the wall-course exclusion with nothing
    # grading the transition).  Anchoring the end does three things the
    # seed could not: the reach band DESCENDS to it at the cap (every
    # interior node inherits the descent), the value is not reseeded here,
    # and the caller carries the node set into the projections that follow.
    # Gate off ⇒ no ties ⇒ this block costs one config read.
    from auto_patch.config import (
        SERVICE_CORRIDOR_FREE_END_ANCHOR as _FREE_END_ANCHOR,
        SERVICE_ROAD_WIDTH_M as _SVC_W)
    free_end_nodes: set = set()
    _fe_moved: set = set()
    layout._svc_free_end_idx = free_end_nodes
    if _FREE_END_ANCHOR and anchors:
        _fe_targets, _fe_records = free_end_targets(
            layout, svc_nodes, node_pos, anchors, dem_elev, ceil, floor,
            radius_m=max(_SVC_W, 8.0))
        if _fe_targets:
            for i, tgt in _fe_targets.items():
                if i < len(elev) and abs(tgt - elev[i]) > 1e-9:
                    elev[i] = tgt
                    _fe_moved.add(i)
                anchors[i] = tgt
                # A free-end DEM tie is a groundside-corridor authority:
                # stage B unless an airside ring claims the node.
                anchor_stage.setdefault(i, STAGE_B)
                free_end_nodes.add(i)
            # The band must reflect the new anchors — the interior nodes
            # between mouth and free end descend against BOTH ends now.
            # Recomposed through the stage boundary (the A envelope is
            # cached; free ends are stage-B and conform like any other
            # stage-B authority).
            _anchor_field = _composed_anchor_values()
            ceil, ceil_dist = _reach(+1, _anchor_field)
            floor, floor_dist = _reach(-1, _anchor_field)
            # Publish: the keyset the projections hold hard (canonical
            # keys, so it survives every node-list rebuild — node_space's
            # law), and the lat/lon records the acceptance instrument
            # reads back off the patch's sidecar.
            try:
                _store_of(layout).mint(
                    "svc_free_end", "keyset",
                    {_key(*node_pos[i]) for i in free_end_nodes
                     if i in node_pos},
                    replace=True)
            except Exception:                            # pragma: no cover
                pass
            _m_to_ll = getattr(layout, "m_to_ll", None)
            if _m_to_ll is not None:
                for _r in _fe_records:
                    try:
                        _la, _lo = _m_to_ll(_r["x"], _r["y"])
                        _r["lat"], _r["lon"] = round(_la, 11), round(_lo, 11)
                    except Exception:                    # pragma: no cover
                        pass
            layout._svc_free_end_records = _fe_records
            import O4_UI_Utils as _UI_fe
            _UI_fe.vprint(1,
                f"  [pav-builder] service free-end DEM tie: "
                f"{len(_fe_records)} corridor terminus/termini anchored to "
                f"ambient DEM ({len(free_end_nodes)} node(s); "
                f"{sum(1 for _r in _fe_records if _r['clamped'])} clamped "
                f"into the road cap's reach).")
    _dbg_spec = _os.environ.get("O4_SVC_DEBUG_LL")
    if _dbg_spec:
        try:
            import math as _dbg_m
            _dla, _dlo = (float(v) for v in _dbg_spec.split(","))
            _dx, _dy = layout.ll_to_m(_dla, _dlo)
            for _i in sorted(svc_nodes):
                _p = node_pos.get(_i)
                if _p is None or _dbg_m.hypot(_p[0] - _dx,
                                              _p[1] - _dy) > 8.0:
                    continue
                print(f"    [svc-dbg] i={_i} pos=({_p[0]:.1f},{_p[1]:.1f})"
                      f" anchor={_i in anchors}"
                      f" elev={elev[_i]:.2f}"
                      f" dem={dem_elev[_i] if _i < len(dem_elev) else None}"
                      f" ceil={ceil.get(_i)} floor={floor.get(_i)}")
        except Exception as _e:
            print(f"    [svc-dbg] error {_e!r}")
    changed: set = set(_fe_moved) | _mouth_moved   # ties + mouth seats
    # BREAK-BLEND EXPORT (user 2026-07-06, handover fix (b)): nodes whose
    # welded anchors contradict (floor > ceil) render the designed blend
    # below — persist them so the caller can quarantine their over-cap
    # pairs/steps instead of reporting the contained blend as actionable
    # (HECA #578↔#64: a junction weld 1 m from a road capped 0.8 m lower).
    service_break: set = getattr(layout, "_service_break_idx", None) or set()
    layout._service_break_idx = service_break
    # SPINE-FIRST (config.SVC_SPINE_FIRST, part 30m): DEM-follow computed per
    # spine STATION and shared by the whole cross-section — see
    # ``_svc_spine_station_seeds``.  Vertices with no station (wide
    # service-junction yards beyond spine reach) keep the legacy per-vertex
    # path below; anchor (weld) vertices are never reseeded on either path.
    from auto_patch.config import SVC_SPINE_FIRST as _SPINE_FIRST
    spine_target: dict = {}
    spine_broken: set = set()
    if _SPINE_FIRST:
        spine_target, spine_broken = _svc_spine_station_seeds(
            layout, svc_nodes, node_pos, anchors, dem_elev, cap,
            ceil, floor, ceil_dist, floor_dist, prox_pairs,
            node_shapes=node_shapes)
    _lat_bound_breaks = 0
    _fallback_legacy: set = set()
    # ── APRON-CONTACT SEEDING: THE DATUM, NOT THE TERRAIN ─────────────
    # (RULINGS 2026-08-25b, spec ``road-band-seal-scope-spec.md`` §2 as
    # amended — Amendment 1 clause 2(c).)  A ring that shares an edge
    # with an apron "conforms to the strictest grade".  Two thirds of
    # that are already structural here: its cap arrives through
    # ``lat_cap`` (clause 2(a)), and its shared-edge vertices are
    # ANCHORS by identity — the loop above reads ``anchors[i] = elev[i]``
    # for every service node that is also a canonical vertex of a
    # non-service ring, so those nodes already carry the apron's own
    # values (clause 2(b)).
    #
    # The missing third is the SEED.  Every non-anchor service node
    # below takes ``clamp(DEM, band)`` — it FOLLOWS THE TERRAIN, which
    # inside a contact ring is precisely the DEM-follow the ruling
    # forbids: the ring is pulled to the ground while its shared edge is
    # pinned to the apron, and the difference emits as the step at the
    # contact.  Here the contact ring seeds from its OWN shared-edge
    # anchors instead, carried outward under its (now-apron) cap: the
    # midpoint of the interval those anchors alone allow, which for a
    # single governing anchor IS that anchor's value carried flat, and
    # for several is the taut level between them.  It is then clamped
    # into the FULL band exactly as the DEM target is, so no feasibility
    # law changes — only what the ring reaches for inside it.
    #
    # A contact node no contact anchor reaches keeps the DEM target and
    # is counted: the fallback is honest, never silent.
    from auto_patch import config as _cfg_contact
    _CONTACT_SEED = getattr(_cfg_contact, "ROAD_APRON_EDGE_CONFORMANCE", True)
    contact_datum: dict = {}
    _contact_nodes: set = set()
    if _CONTACT_SEED:
        for i, _shs in node_shapes.items():
            if any(getattr(o, "apron_contact", False) for o in _shs):
                _contact_nodes.add(i)
        _c_src = {i: v for i, v in anchors.items() if i in _contact_nodes}
        if _c_src:
            _c_ceil, _ = _reach(+1, _c_src)
            _c_floor, _ = _reach(-1, _c_src)
            for i in _contact_nodes:
                if i in anchors:
                    continue
                hi, lo_ = _c_ceil.get(i), _c_floor.get(i)
                if hi is None and lo_ is None:
                    continue
                if hi is None:
                    contact_datum[i] = float(lo_)
                elif lo_ is None:
                    contact_datum[i] = float(hi)
                elif lo_ <= hi + 1e-9:
                    contact_datum[i] = 0.5 * (float(hi) + float(lo_))
                # lo_ > hi is a genuine contradiction among the ring's own
                # apron anchors — no datum; the DEM path below applies and
                # the break machinery reports it, as it does for any road.
    _contact_seeded: set = set()
    for i in svc_nodes:
        if i in anchors:
            continue
        if i in spine_target and i not in contact_datum:
            tgt = spine_target[i]
            if i in spine_broken:
                # Laterally bound (spec §1): this node belongs to the
                # contiguous surface, whose law adjudicates it — the
                # envelope has no standing to quarantine it.  The blend
                # target below is still applied; the deficit, if any, is
                # visible to the validator.
                if i in lat_cap:
                    _lat_bound_breaks += 1
                else:
                    service_break.add(i)
            if abs(tgt - elev[i]) > 1e-3:
                elev[i] = tgt
                changed.add(i)
            continue
        de = contact_datum.get(i)
        if de is not None:
            _contact_seeded.add(i)
        else:
            de = dem_elev[i] if i < len(dem_elev) else None
        if de is None:
            continue
        c = ceil.get(i)
        f = floor.get(i)
        if c is None:                       # unreachable from any anchor → DEM
            tgt = de
            _fallback_legacy.add(i)
        elif f is not None and f > c + 1e-9:
            # GENUINE break: the road's welded anchors (airside mouth vs
            # groundside/other weld) contradict through this node — no
            # <=cap profile connects them (user 2026-07-04: break-blend
            # support for service roads).  Same operator as
            # ``feasibility_project``'s broken-node fill: the
            # distance-weighted blend puts the surface ON the descent
            # field of each anchor at that anchor (t→0 ⇒ z=ceil field,
            # t→1 ⇒ z=floor field, continuous at the region boundary)
            # and spreads the deficit between them as one gentle
            # over-cap ramp.  Ceiling-clamping instead (the previous
            # behaviour, silently) parked the WHOLE deficit as a wall
            # at the floor-side anchor — typically the groundside mouth.
            dc = ceil_dist.get(i, 0.0)
            df = floor_dist.get(i, 0.0)
            t = dc / (dc + df) if (dc + df) > 1e-9 else 0.5
            tgt = c + (f - c) * t
            if i in lat_cap:                # laterally bound — see above
                _lat_bound_breaks += 1
            else:
                service_break.add(i)
        else:
            lo = f if f is not None else -float("inf")
            tgt = min(max(de, lo), c)
            _fallback_legacy.add(i)
        if abs(tgt - elev[i]) > 1e-3:
            elev[i] = tgt
            changed.add(i)
    if _contact_nodes:
        import O4_UI_Utils as _UI_ct
        _ct_free = len(_contact_nodes) - sum(
            1 for i in _contact_nodes if i in anchors)
        _UI_ct.vprint(1,
            f"  [pav-builder] apron-CONTACT seeding (RULINGS 2026-08-25b, "
            f"Amendment 1): {len(_contact_nodes)} node(s) on edge-sharing "
            f"road ring(s) — {len(_contact_nodes) - _ct_free} hold the "
            f"apron's value BY IDENTITY (shared vertices), "
            f"{len(_contact_seeded)} seeded from that datum outward under "
            f"the apron cap, {_ct_free - len(_contact_seeded)} with no "
            f"contact anchor in reach kept the DEM target.")
    # ── THE WHOLE-RUN CORRIDOR PROFILE IS HELD, NOT SEEDED ────────────
    # Membership only, no value write — the same spelling as the
    # free-end tie (``svc_free_end``) and for the same measured reason.
    # A corridor is ONE law object whose profile was solved over its
    # whole run; a downstream pointwise projection re-humping it is the
    # defect this round closes, not a refinement of it.  Minted by
    # CANONICAL KEY so it survives the final pass's node-list rebuild
    # (node_space's law).  Anchors are excluded: they are stage-A weld
    # values and are already hard by their own law.
    # ── RUN / YARD SCOPING (Fable ruling 2026-08-14, S2's STOP 1) ─────
    # "The 1-D profile HOLDS on the corridor's LINEAR RUNS only.  A 2-D
    # service surface (junction yard, service apron) is never held to a
    # line: it solves as a surface with the profile's values as BOUNDARY
    # SEEDS at its mouths."  This is a scoping of the ONE band, not a
    # second band.
    #
    # THE TEST IS THE SHAPE'S OWN GEOMETRY, not its role literal — a
    # service_junction can be a narrow connector or a 40 m yard, and it
    # was the YARDS that made within-shape pairs unsatisfiable (measured
    # at KCLT: +157 within_shape::service_junction rows from holding a
    # line over a surface).  Mean width ``2·area/perimeter`` is the
    # width of a long thin polygon (w·L/(w+L) → w for L ≫ w); a shape
    # wider than ``ROAD_CARVE_MAX_WIDTH_M`` — the widest thing the road
    # carve itself treats as a road — is a SURFACE.  Existing constant,
    # no new number.
    #
    # A node any LINEAR shape claims is held: that is the run, and where
    # a run meets a yard it is the yard's MOUTH — held exactly as a
    # corridor mouth is held at airside.  A node only surfaces claim is
    # released to the surface solve.
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M as _CARVE_W
    _linear_nodes: set = set()
    _n_linear = _n_surface = 0
    for _s in layout.shapes:
        _poly = getattr(_s, "polygon", None)
        if _poly is None or _poly.is_empty or _poly.length <= 0.0:
            continue
        if (2.0 * _poly.area / _poly.length) > _CARVE_W:
            _n_surface += 1
            continue                    # a 2-D surface — never held
        _n_linear += 1
        for (_x, _y) in _open_ring(list(_poly.exterior.coords)):
            _i = bucket_to_idx.get(_key(_x, _y))
            if _i is not None:
                _linear_nodes.add(_i)
    _prof_members = getattr(layout, "_svc_profile_members", None) or set()
    _prof_released = {i for i in _prof_members
                      if i in svc_nodes and i not in anchors
                      and i not in _linear_nodes}
    _prof_idx = {i for i in _prof_members
                 if i in svc_nodes and i not in anchors
                 and i in _linear_nodes}
    layout._svc_profile_released_idx = _prof_released
    layout._svc_profile_idx = _prof_idx
    if _prof_idx:
        try:
            _store_of(layout).mint(
                "svc_profile", "keyset",
                {_key(*node_pos[i]) for i in _prof_idx if i in node_pos},
                replace=True)
        except Exception:                                # pragma: no cover
            pass
        import O4_UI_Utils as _UI_ph
        _UI_ph.vprint(1,
            f"  [pav-builder] whole-run corridor profile HELD on LINEAR "
            f"RUNS: {len(_prof_idx)} node(s) enter stage B as the "
            f"corridor's own band (membership only, the free-end tie's "
            f"spelling); {len(_prof_released)} node(s) RELEASED to the "
            f"2-D surface solve with the profile as their boundary seed "
            f"({_n_linear} linear shape(s), {_n_surface} surface(s) at "
            f"mean width > {_CARVE_W} m).")
    if _lat_bound_breaks:
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [pav-builder] service DEM-follow: {_lat_bound_breaks} "
            f"contradiction(s) at laterally-bound node(s) NOT quarantined "
            f"— the contiguous surface's law owns them (of "
            f"{len(lat_cap)} node(s) carrying a lateral cap).")

    # ── THE FALLBACK NEIGHBOUR TERM (finalarch item 4) ────────────────
    # The two fallback writers — the pointwise station clamp and the
    # legacy per-vertex path — clamp into the BAND only: ``tgt =
    # min(max(de, lo), c)`` bounds each node against the ANCHORS but
    # says nothing about its neighbour, so DEM-follow noise between
    # adjacent fallback nodes is unbounded by cap on exactly the nodes
    # the whole-run law never reaches (S1f dossier item 5a).  The
    # neighbour term the profile's own law implies is the cap metric
    # ``_reach`` already prices (``e_cap·dd`` — the lateral-contiguity
    # cap where present, the road cap otherwise; NO new constant): the
    # largest cap-Lipschitz minorant of the seeded field,
    #
    #     D(i) = min_j ( z_j + e_cap·d_graph(i, j) ),
    #
    # computed EXACTLY by one multi-source Dijkstra over the same
    # adjacency.  D is fully Lipschitz under the metric (inf-convolution
    # triangle inequality), never moves a node that has no over-cap
    # descent toward a neighbour, and only lowers the UPPER side of an
    # over-cap pair — grading the step along the run, which is what the
    # whole-run profile does where it reaches.  Held/profiled nodes,
    # anchors, free-end ties, released yard nodes and break-blend nodes
    # are SOURCES but never move; fallback STATIONS move as one
    # cross-section (the spine-first law: a per-node update would seed
    # the cross-road tear the station machinery exists to prevent).
    # Deviation from DEM is not a reported consideration (owner
    # 2026-08-14, DEM-NOT-REPORTED).
    _pinned = (set(anchors) | free_end_nodes | set(_prof_idx)
               | set(_prof_released) | set(service_break)
               | set(spine_broken))
    _node_gid: dict = {}
    _free_groups: dict = {}
    for _gn, _grp in enumerate(
            getattr(layout, "_svc_station_fallback_groups", ()) or ()):
        _members = {i for i in _grp
                    if i in svc_nodes and i not in _pinned
                    and i < len(elev)}
        if not _members:
            continue
        _gid = ("st", _gn)
        for i in _members:
            _node_gid[i] = _gid
        _free_groups[_gid] = _members
    for i in _fallback_legacy:
        if i in _pinned or i in _node_gid or i >= len(elev):
            continue
        _gid = ("n", i)
        _node_gid[i] = _gid
        _free_groups[_gid] = {i}
    if _free_groups:
        _gval: dict = {}
        _gadj: dict = {}
        for i in svc_nodes:
            if i >= len(elev):
                continue
            _gi = _node_gid.get(i, ("p", i))
            if _gi not in _gval:
                _gval[_gi] = float(elev[i])
            for (j, dd) in adj.get(i, ()):
                if j >= len(elev):
                    continue
                _gj = _node_gid.get(j, ("p", j))
                if _gj == _gi:
                    continue
                _e_cap = cap
                if lat_cap:
                    _e_cap = min(lat_cap.get(i, cap), lat_cap.get(j, cap))
                _gadj.setdefault(_gi, []).append((_gj, _e_cap * dd))
        _best: dict = {}
        _pq = [(v, g) for g, v in _gval.items()]
        heapq.heapify(_pq)
        while _pq:
            v, g = heapq.heappop(_pq)
            if g in _best:
                continue
            _best[g] = v
            for (h, w) in _gadj.get(g, ()):
                if h not in _best:
                    heapq.heappush(_pq, (v + w, h))
        _n_lip_moved = 0
        _worst_lip = 0.0
        for _gid, _members in _free_groups.items():
            nv = _best.get(_gid)
            if nv is None:
                continue
            for i in _members:
                drop = float(elev[i]) - nv
                if drop > 1e-3:
                    elev[i] = nv
                    changed.add(i)
                    _n_lip_moved += 1
                    _worst_lip = max(_worst_lip, drop)
        layout._svc_fallback_lipschitz = {
            "free_groups": len(_free_groups), "moved": _n_lip_moved,
            "worst_drop_m": round(_worst_lip, 3)}
        if _n_lip_moved:
            import O4_UI_Utils as _UI_lip
            _UI_lip.vprint(1,
                f"  [pav-builder] service fallback neighbour term: "
                f"{_n_lip_moved} node(s) graded to the cap metric across "
                f"{len(_free_groups)} fallback group(s) (worst descent "
                f"{_worst_lip:.3f} m; e_cap·d Lipschitz envelope, no new "
                f"constant).")

    # ── CROSS-STAGE CONFORMANCE REPORT (finalarch item 5) ────────────
    if _cross_stage_records:
        _m_to_ll_cs = getattr(layout, "m_to_ll", None)
        for _r in _cross_stage_records:
            _p = _r.pop("xy", None)
            if _p is not None and _m_to_ll_cs is not None:
                try:
                    _la, _lo = _m_to_ll_cs(_p[0], _p[1])
                    _r["lat"], _r["lon"] = round(_la, 11), round(_lo, 11)
                except Exception:                        # pragma: no cover
                    pass
    layout._svc_cross_stage_conform = _cross_stage_records
    _n_a = sum(1 for i in anchors
               if anchor_stage.get(i, STAGE_A) == STAGE_A)
    import O4_UI_Utils as _UI_stage
    _UI_stage.vprint(1,
        f"  [pav-builder] service reach anchors are STAGE-AWARE: "
        f"{_n_a} stage-A / {len(anchors) - _n_a} stage-B anchor(s); "
        f"{len(_cross_stage_records)} stage-B authorit(y/ies) conformed "
        f"to the frozen stage-A envelope (recorded, values held).")
    return changed


def _groundside_lot_rings(layout, bucket_to_idx):
    """Per groundside lot with per-vertex altitudes: the ring vertex list
    ``[(ring_index, solver_index_or_None, (x, y)), ...]`` (open ring)."""
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    cps = layout.canonical_points
    out = []
    for g in layout.shapes:
        if (g.role != ROLE_GROUNDSIDE_PAVEMENT or g.polygon is None
                or g.polygon.is_empty or not g.node_altitudes):
            continue
        coords = list(g.polygon.exterior.coords)
        verts = []
        for j in range(min(len(coords), len(g.node_altitudes))):
            x, y = coords[j]
            idx = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            verts.append((j, idx, (float(x), float(y))))
        out.append((g, verts))
    return out


def expand_mouth_cluster(layout, bucket_to_idx, conflicted, welded_idx,
                         window_m: float = 12.0):
    """Grow a conflicted-mouth set to the full mouth CLUSTER: every welded
    solver node on the SAME groundside lot ring within ``window_m`` of a
    conflicted node.  Freeing the whole cluster lets the joint solve place
    one consistent mouth profile instead of wedging a single freed vertex
    between its still-hard neighbours."""
    import math as _m
    freed = set(conflicted)
    for (_g, verts) in _groundside_lot_rings(layout, bucket_to_idx):
        ring_welded = [(j, idx, p) for (j, idx, p) in verts
                       if idx is not None and idx in welded_idx]
        seeds = [(j, idx, p) for (j, idx, p) in ring_welded
                 if idx in conflicted]
        if not seeds:
            continue
        for (_j, idx, p) in ring_welded:
            if idx in freed:
                continue
            if any(_m.hypot(p[0] - sp[0], p[1] - sp[1]) <= window_m
                   for (_sj, _si, sp) in seeds):
                freed.add(idx)
    return freed


def adopt_projected_mouths(layout, bucket_to_idx, elev, freed, welded_idx):
    """LOT ADOPTS THE SOLVED MOUTH (user 2026-07-06, HECA #541/#546): after
    the mouth verify-and-relax re-projection, write the projected values of
    the freed mouth vertices back onto their groundside lot rings — exact at
    each freed vertex, cap-decay filled across non-welded ring vertices.
    Non-freed welded vertices are held fixed during the fill (their solver
    values did not move).  Deliberately NO chord-limit here: the downward-
    only limiter would drag an adopted-high mouth toward the lot's low DEM
    interior (measured: HECA #522 mouth 103.9 → 101.8, a 2.1 m weld tear);
    ring lawfulness stays with the post-solve groundside chord limiter,
    which re-adopts welded values properly.  Returns the count of adopted
    lot rings."""
    import math as _m
    from auto_patch.config import GROUNDSIDE_MAX_GRADE
    n_adopted = 0
    for (g, verts) in _groundside_lot_rings(layout, bucket_to_idx):
        alts = list(g.node_altitudes)
        freed_verts = [(j, idx, p) for (j, idx, p) in verts
                       if idx is not None and idx in freed
                       and j < len(alts) and alts[j] is not None]
        if not freed_verts:
            continue
        held = {j for (j, idx, _p) in verts
                if idx is not None and idx in welded_idx
                and idx not in freed}
        # ABSOLUTE Lipschitz support around each adopted mouth (see the
        # reach-time reconciliation for why a relative delta cone is
        # wrong: an at-cap ring re-emits over cap).
        sources = [(p, float(elev[idx]), float(elev[idx]) - float(alts[j]))
                   for (j, idx, p) in freed_verts]
        new_alts = list(alts)
        for (j, _idx, p) in [(j, i, p) for (j, i, p) in verts
                             if j < len(alts) and alts[j] is not None]:
            if j in held:
                continue
            val = float(alts[j])
            for (fp, tgt, dv) in sources:
                dd = _m.hypot(p[0] - fp[0], p[1] - fp[1])
                if dv > 0.0:
                    val = max(val, tgt - GROUNDSIDE_MAX_GRADE * dd)
                elif dv < 0.0:
                    val = min(val, tgt + GROUNDSIDE_MAX_GRADE * dd)
            new_alts[j] = val
        # exact adoption at the freed vertices themselves
        for (j, idx, _p) in freed_verts:
            new_alts[j] = float(elev[idx])
        # keep a closed ring closed (mirrors chord_limit's own handling)
        coords = list(g.polygon.exterior.coords)
        if (len(new_alts) == len(coords) and len(coords) > 1
                and tuple(coords[0]) == tuple(coords[-1])
                and new_alts[0] is not None):
            new_alts[-1] = new_alts[0]
        g.node_altitudes = new_alts
        n_adopted += 1
    return n_adopted


def apron_body_nodes(layout, bucket_to_idx):
    """Node indices that follow DEM (apron bodies + service roads/junctions) and
    are NOT part of the taxi route — closest-to-DEM target, no taxi-band bound.
    The rest of airside is the taxi route (smooth, band-bounded)."""
    cps = layout.canonical_points
    body: set = set()
    route: set = set()
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role in _DEM_BODY_ROLES:
            tgt = body
        elif s.role in _ROUTE_ROLES:
            tgt = route
        else:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None:
                tgt.add(i)
    return body - route


# Solved-pavement roles a building pad may be embedded in / abut.  A pad's flat
# value adopts the HOST level from any of these; buildings and terrain-follow
# roles are excluded (a pad never adopts from another pad, and DEM-follow bodies
# are the pad's own frontage terrain, not a solved host surface).
_PAD_HOST_ROLES = frozenset({
    ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
})


def _is_airside_role(role) -> bool:
    """Is ``role`` an AIRSIDE pavement role?

    ONE partition, the law's own: ``layout.GROUNDSIDE_ROLES`` (the same set
    ``grade_graph._reads_service_spines`` asks).  Everything a pad may host
    on that is not groundside is airside — apron, junction, the parallels,
    stub, cross_connector.
    """
    from auto_patch.layout import GROUNDSIDE_ROLES
    return role not in GROUNDSIDE_ROLES


def _pad_has_airside_host(pad, host_shapes, pad_ring, lift_r2) -> bool:
    """Does an AIRSIDE-role host ring come within the lip radius of this pad?

    The same proximity test the lip lift itself uses, asked before the
    adoption decision so rule 1 of AMENDMENT 1 can be enforced where the
    decision is made rather than after the value is written.
    """
    for h in host_shapes:
        if not _is_airside_role(h.role):
            continue
        try:
            hcoords = list(h.polygon.exterior.coords)
        except (ValueError, TypeError):
            continue
        for (hx, hy) in hcoords:
            for (px, py) in pad_ring:
                ddx = hx - px
                ddy = hy - py
                if ddx * ddx + ddy * ddy <= lift_r2:
                    return True
    return False


def _shape_vertex_alt(s, idx, n_open):
    """Solved altitude at ring-vertex ``idx`` of a pavement shape, or None.

    Reads whichever elevation representation the writeback left on the shape:
    per-vertex ``node_altitudes`` (apron/junction), a single flat ``altitude``,
    or a 4-corner ``altitude_high``/``altitude_low`` plane (mean is a sound
    local proxy for a pad-adjacency reference — rects rarely embed a pad)."""
    na = s.node_altitudes
    if na:
        na_open = na[:-1] if len(na) == n_open + 1 else na
        if 0 <= idx < len(na_open) and na_open[idx] is not None:
            return float(na_open[idx])
    if s.altitude is not None:
        return float(s.altitude)
    if s.altitude_high is not None and s.altitude_low is not None:
        return 0.5 * (float(s.altitude_high) + float(s.altitude_low))
    return None


def _building_flat_level(s):
    """Current flat level of a building pad (post-writeback), or None."""
    if s.altitude is not None:
        return float(s.altitude)
    na = s.node_altitudes
    if na:
        vals = [float(v) for v in na if v is not None]
        if vals:
            return sum(vals) / len(vals)
    return None


#: THE COALITION WINDOW.  R12 amendment 4's ratified constant, reused
#: verbatim for the pad level family (lead ruling 2026-08-12: "reuse
#: R12's window constant/idiom, 0.25 m class").  One definition, two
#: laws: ``post_mesh._MEMBER_DELTA_AGREEMENT_WINDOW_M``.
def _coalition_window_m() -> float:
    from auto_patch.post_mesh import _MEMBER_DELTA_AGREEMENT_WINDOW_M
    return float(_MEMBER_DELTA_AGREEMENT_WINDOW_M)


def _AGREEING_COALITION(members, window_m, weight_of=None,
                        tiebreak_of=None):
    """R12 amendment 4's own function (``post_mesh.agreeing_coalition``),
    imported at call time so this module carries no copy of it."""
    from auto_patch.post_mesh import agreeing_coalition
    return agreeing_coalition(members, window_m, weight_of=weight_of,
                              tiebreak_of=tiebreak_of)


def _median_of(values):
    vals = sorted(float(v) for v in values)
    m = len(vals)
    if not m:
        return None
    return (vals[m // 2] if m % 2
            else 0.5 * (vals[m // 2 - 1] + vals[m // 2]))


def _pad_lip_index(layout, host_rings, host_shapes_by_rid, weld_tol):
    """``{ring_id: {vertex_index: {pad_shape_id, ...}}}`` — which pads the
    FINAL EPSILON-WEDGE WELD makes one node with each host ring vertex
    (R19-1 as re-ruled by task #16).

    This is the LEVEL FAMILY's only membership relation: two pads are in
    one family when they reach a common host ring vertex, transitively.
    It is structural — a shared piece of the host's own boundary — so no
    distance between two pads can put them in one family, and no distance
    can keep two welded neighbours out of one.

    WHY THE WELD AND NOT A CONTACT RADIUS (task #16).  The level family is
    an EMIT-TIME structure.  This pass runs post-solve, pre-emit, and the
    shared ring vertices that chain a pad to its host are minted LATER, by
    ``conformance.enforce_conformance(tol=0.01)`` — the final weld
    (``pipeline.py``, part 30j) — after ``decimate_emit_nodes`` has just
    dropped each shape's ring vertices independently.  Read at relevel
    time, "shares a vertex" is therefore blind to the family the weld will
    create, and the 2.5 m contact radius that stood in for it was a
    proximity join with a tolerance of its own (HECA building114: nothing
    inside 2.5 m, host body 16.59 m out, the pad never re-levelled).  The
    relation is now **"will weld together"**, read from the weld's OWN law
    through ``conformance.weld_candidate_pairs`` — one code path, no
    tolerance of ours:

    * ALREADY ONE NODE — a pad ring vertex inside the weld's own node
      identity radius (``weld_node_identity_tol``) of a host ring vertex;
      the weld treats such a pair as one node and inserts nothing.
    * THE PAD WELDS INTO THE HOST — a pad ring vertex the weld will insert
      into host ring edge ``i → i+1``.  Post-weld that node sits ON that
      edge, i.e. on the host boundary BETWEEN vertices ``i`` and ``i+1``,
      so the pad reaches both of its ends: the lip run the family walks is
      that edge.  (Two pads welding into one long apron edge therefore
      land in one family — which is what the emitted ring says, since the
      weld leaves their nodes consecutive on it with no host body vertex
      between them.  Level arbitration is the coalition's job, and its
      weight is AREA.)
    * THE HOST WELDS INTO THE PAD — a host ring vertex ``i`` the weld will
      insert into the PAD's ring; the pad adopts that exact node.

    ``weld_tol`` is the final weld's own tolerance, passed down from the
    caller — never a constant of this module's.
    """
    from auto_patch.layout import ROLE_OBJECT_PAD
    from auto_patch.conformance import (weld_candidate_pairs,
                                        weld_node_identity_tol,
                                        _open_ring as _conf_open_ring)
    out: dict = {}

    def _mark(rid, i, sid):
        out.setdefault(rid, {}).setdefault(i, set()).add(sid)

    # The pads, and their ring vertices as the WELD sees them (the same
    # ring expression conformance builds its donor index from, so a donor
    # point compares exactly).
    pad_pt_owner: dict = {}
    pad_ids: set = set()
    for sh in (getattr(layout, "shapes", ()) or ()):
        if sh.role not in (ROLE_BUILDING, ROLE_OBJECT_PAD):
            continue
        if sh.polygon is None or sh.polygon.is_empty:
            continue
        pring = _conf_open_ring(sh.polygon)
        if pring is None:
            continue
        pad_ids.add(id(sh))
        for pt in pring:
            pad_pt_owner.setdefault(pt, set()).add(id(sh))

    # ── (a) ALREADY ONE NODE, at the weld's own identity radius ───────
    ident = weld_node_identity_tol(weld_tol)
    ident2 = ident * ident
    cells: dict = {}
    for rid, (pts, _alts) in enumerate(host_rings):
        for i, (x, y) in enumerate(pts):
            cells.setdefault((int(x // ident), int(y // ident)), []).append(
                (x, y, rid, i))
    for (px, py), sids in pad_pt_owner.items():
        cx = int(px // ident)
        cy = int(py // ident)
        for dx_ in (-1, 0, 1):
            for dy_ in (-1, 0, 1):
                for (hx, hy, rid, i) in cells.get((cx + dx_, cy + dy_), ()):
                    if (hx - px) ** 2 + (hy - py) ** 2 <= ident2:
                        for sid in sids:
                            _mark(rid, i, sid)

    # ── (b)/(c) THE WELD'S OWN CANDIDATE PAIRS ───────────────────────
    # Same arguments as the final weld (``pipeline.py`` part 30j), so the
    # pairs read here are the pairs it will make.
    host_pt_key: dict = {}
    for rid, (pts, _alts) in enumerate(host_rings):
        for i, pt in enumerate(pts):
            host_pt_key.setdefault(pt, []).append((rid, i))
    rid_of_host = {id(hs): rid
                   for rid, hs in enumerate(host_shapes_by_rid)}
    import time as _time
    _t0 = _time.perf_counter()
    _pairs = weld_candidate_pairs(layout, tol=weld_tol,
                                  include_overlay_refs=True)
    # The build-time line this law owes: the enumeration runs ONCE more
    # per build (the weld itself is unchanged), so its cost is stated
    # where it is paid rather than inferred from a wall-clock A/B.
    try:
        import O4_UI_Utils as _UI
        _UI.vprint(1,
                   f"  [pav-builder] pad-host level family: weld candidate "
                   f"enumeration {len(_pairs)} pair(s) in "
                   f"{_time.perf_counter() - _t0:.2f} s")
    except Exception:
        pass
    for pair in _pairs:
        rid = rid_of_host.get(id(pair.receiver))
        if rid is not None:
            sids = pad_pt_owner.get(pair.donor_point)
            if not sids:
                continue
            n = len(host_rings[rid][0])
            if n < 2:
                continue
            for sid in sids:
                _mark(rid, pair.edge_index, sid)
                _mark(rid, (pair.edge_index + 1) % n, sid)
        elif id(pair.receiver) in pad_ids:
            for (rid_h, i_h) in host_pt_key.get(pair.donor_point, ()):
                _mark(rid_h, i_h, id(pair.receiver))
    return out


def _level_family_members(group, pad_by_id, host_rings, host_areas,
                          host_lip, pad_lips_by_ring, trigger,
                          drift_r2):
    """The LEVEL FAMILY of one pad, as coalition members (R19-1).

    Members are ``{"delta_m": level, "weight": area, "kind": ...}`` — the
    shape ``post_mesh.agreeing_coalition`` reads — and they are:

    * every PAD chained to this one by LIP ADJACENCY on a shared host
      ring (transitively: a host ring vertex both pads' contact radii
      touch), weighted by its polygon AREA;
    * the HOST'S OWN BODY VERTICES on that chain — ring vertices inside
      the span the family covers that are neither TOUCHED by a pad nor
      carrying a family pad's own VALUE — each weighted by the host's
      area per ring vertex, so a host votes in proportion to how much of
      it the family actually spans.

    Both lip tests are needed, and each is scoped by what it is for.
    The GEOMETRIC test catches the weld itself (contact radius).  The
    VALUE test catches a weld that DRIFTED — a shared node sitting
    decimetres off the pad vertex on a ring denser than the contact
    radius, the class that defeated the first mechanism — so it applies
    only within the weld-drift neighbourhood
    (``PAD_HOST_LEVEL_LIFT_M``) of a family pad.  Unscoped it would
    strip a host of its own body wherever a pad has ALREADY conformed to
    it, which is the normal state of a healthy airport: measured here,
    it emptied a family of every host member the moment its neighbour
    adopted the host's level.

    ``None`` when the pad touches no host ring (nothing to conform to).
    The pad being levelled is always a member, so the family always has
    something to compare it against.

    MEMBERSHIP IS STRUCTURAL.  A pad joins only through the host
    boundary it is welded into, so no distance can merge two families on
    separate chains, and none can keep two welded neighbours apart."""
    own_ids = {id(g) for g in group}
    seeds = [(rid, i)
             for rid, verts in pad_lips_by_ring.items()
             for i, ids in verts.items() if ids & own_ids]
    if not seeds:
        return None

    # Which vertices each pad touches — the reverse index, built once per
    # call over the same table (small: only pads that touch a host ring).
    verts_of_pad: dict = {}
    for rid, verts in pad_lips_by_ring.items():
        for i, ids in verts.items():
            for sid in ids:
                verts_of_pad.setdefault(sid, []).append((rid, i))

    pad_ids = set(own_ids)
    family_vertices = set(seeds)
    frontier = list(seeds)
    while frontier:
        rid, i = frontier.pop()
        for sid in pad_lips_by_ring.get(rid, {}).get(i, ()):
            if sid in pad_ids:
                continue
            pad_ids.add(sid)
            for key in verts_of_pad.get(sid, ()):
                if key not in family_vertices:
                    family_vertices.add(key)
                    frontier.append(key)

    members: list = []
    pad_levels: list = []
    family_pad_pts: list = []
    for sid in pad_ids:
        sh = pad_by_id.get(sid)
        if sh is None or sh.polygon is None or sh.polygon.is_empty:
            continue
        lvl = _building_flat_level(sh)
        if lvl is None:
            continue
        members.append({"delta_m": float(lvl),
                        "weight": float(sh.polygon.area),
                        "kind": "pad", "id": sid})
        pad_levels.append(float(lvl))
        try:
            family_pad_pts.extend(
                _open_ring(list(sh.polygon.exterior.coords)))
        except (ValueError, TypeError):
            pass

    # THE HOST'S OWN BODY ON THIS CHAIN: the non-lip vertices inside the
    # ring span the family covers (the shorter arc between its extreme
    # family vertices, so a family on one side of a big apron does not
    # annex the whole ring).
    by_ring: dict = {}
    for (rid, i) in family_vertices:
        by_ring.setdefault(rid, []).append(i)
    for rid, idxs in by_ring.items():
        pts, alts = host_rings[rid]
        n = len(pts)
        if n < 3:
            continue
        idxs = sorted(set(idxs))
        lo, hi = idxs[0], idxs[-1]
        forward = list(range(lo, hi + 1))
        backward = list(range(hi, n)) + list(range(0, lo + 1))
        span = forward if len(forward) <= len(backward) else backward
        # THE CHAIN'S ENDS.  A family's own vertices are all lips by
        # construction, so the host's body on this chain begins at the
        # first ring vertex past each end of the lip run.  Extend the
        # span outward through consecutive lips and take that vertex on
        # each side — structural (where the host's own surface resumes),
        # never a search for a value.
        def _is_weld(i, _rid=rid, _alts=alts, _pts=pts):
            """Indistinguishable from a pad's weld: touched by a pad, or
            carrying a family pad's value INSIDE that pad's weld-drift
            neighbourhood."""
            if host_lip[_rid][i]:
                return True
            if _alts[i] is None:
                return True
            if not any(abs(float(_alts[i]) - lvl) <= trigger
                       for lvl in pad_levels):
                return False
            hx, hy = _pts[i]
            return any((hx - px) ** 2 + (hy - py) ** 2 <= drift_r2
                       for (px, py) in family_pad_pts)

        for step in (1, -1):
            k = span[-1] if step == 1 else span[0]
            for _ in range(n - len(span)):
                k = (k + step) % n
                if k in span:
                    break
                span = (span + [k]) if step == 1 else ([k] + span)
                if not _is_weld(k):
                    break
        per_vertex_area = (float(host_areas[rid]) / n) if n else 0.0
        for i in span:
            if _is_weld(i):
                continue          # a weld, not the host's own body
            members.append({"delta_m": float(alts[i]),
                            "weight": per_vertex_area,
                            "kind": "host", "id": (rid, i)})
    return members


def _surface_value_at(field, px, py):
    """The value of a solved surface at ``(px, py)`` (R19-1).

    ``field`` is ``[(x, y, value)]`` — the ring positions of ONE host
    shape and the altitudes the solve wrote on them, with the pad's own
    shared-boundary lips already removed by the caller.  Returns the
    surface's value at the query point by inverse-SQUARE distance
    weighting, or ``None`` for an empty field.

    Why this reading: the emit / mesh frame interpolates a shape's
    surface linearly between its ring values, so on a locally planar
    host (an apron plateau — the class this law is about) the weighted
    value IS the mesh's value.  A triangulation would be the exact
    frame, but the field is a PUNCTURED ring once the lips are removed
    and no triangulation of it is well defined; inverse-square weighting
    is total over any vertex set, is exact AT a vertex, and decays fast
    enough that a far part of the same apron cannot outvote the ground
    the pad actually stands on.  There is deliberately NO radius here:
    a surface has a value everywhere, which is the whole point of the
    re-ruling.
    """
    num = 0.0
    den = 0.0
    for (hx, hy, v) in field:
        dx = hx - px
        dy = hy - py
        d2 = dx * dx + dy * dy
        if d2 <= 1e-6:
            return v
        w = 1.0 / d2
        num += w * v
        den += w
    return (num / den) if den else None


def _object_pad_groups(layout):
    """``[(core_shape, [core + blend shapes])]`` — one entry per emitted
    object-pad REQUEST (R19-3).

    An object pad is not one shape: ``object_pads.emit_object_pads``
    writes a flat CORE (``ref="object_pad:<i>"``) and the blend plates
    that ramp it out to DEM (``ref="object_pad_blend:<i>"``), all under
    ``ROLE_OBJECT_PAD``.  The request's LEVEL is the core's; the whole
    group moves together.  A blend with no surviving core (the pad the
    clip left as a bare ramp) governs no level and is skipped."""
    from auto_patch.layout import ROLE_OBJECT_PAD
    cores: dict = {}
    members: dict = {}
    for s in layout.shapes:
        if s.role != ROLE_OBJECT_PAD:
            continue
        ref = str(getattr(s, "ref", "") or "")
        kind, _, idx = ref.partition(":")
        if not idx:
            continue
        members.setdefault(idx, []).append(s)
        if kind == "object_pad" and s.polygon is not None \
                and not s.polygon.is_empty:
            cores.setdefault(idx, s)
    return [(cores[idx], members[idx]) for idx in sorted(cores)]


def relevel_pads_to_host_pavement(layout, *, pad_role=None):
    """POST-SOLVE: re-level every building pad embedded in / abutting SOLVED
    pavement to the level the HOST pavement solved to at the contact.

    The frontage seat (``build_building_seats``) is a route-reachability
    envelope biased toward raw DEM.  When the host apron/junction around a pad
    solves ABOVE that envelope, a DEM-low seat leaves the flat pad in a pit and
    the host humps around it (CYXY apron #129 → building8, a -333 %/1.1 m step).

    For each pad, sample the host pavement's solved vertex altitudes within
    ``PAD_HOST_LEVEL_CONTACT_M`` of the pad ring and classify them BY VALUE: a
    node whose level agrees with the pad's current (pit) level is a shared-
    boundary lip (already carries the pad's own value — the contamination); a
    node that DIFFERS by more than ``PAD_HOST_LEVEL_TRIGGER_M`` is the genuine
    step partner = the HOST BODY.  When such a body exists, seat the pad FLAT at
    its median and lift the pit-value lip (within ``PAD_HOST_LEVEL_LIFT_M``) to
    the same level so pad and host weld at one flat level (no emit cliff).  The
    pad adopts FROM the host, never the reverse; the host BODY is untouched.

    ``pad_role`` (R19-3) selects WHICH pads this pass reconciles — ONE
    implementation, two roles:

    * ``ROLE_BUILDING`` (default): the law above, at
      ``PAD_HOST_LEVEL_TRIGGER_M``.
    * ``ROLE_OBJECT_PAD``: the object-pad half.  A pad's target comes from
      the OBJECT's rendered/draped ground (``object_anchor``'s
      ``target_ground_metres``) and nothing reconciled it with the solved
      host — HECA's ``object_pad:56`` sat at 105.51 welded to an apron
      that solved to ~93.5, and the apron ring carried the pad's 106 m
      values into two of the airport's worst edges (148.4 % over 8.49 m,
      55.6 % over 22.39 m).  The law: an object pad whose level exceeds
      the host's solved level at its ring by more than THE PAD'S OWN
      RELIEF BUDGET (``DSF_OBJECT_PAD_MAX_RELIEF_M`` — the same budget
      that decides admissibility against DEM) ADOPTS the host level.  The
      whole pad group moves — core AND its blend plates, by one delta, so
      the blend keeps the ramp it was built with — and the host body is
      untouched.  Within the budget the pad keeps its own target: an
      object seated a metre or two above its apron is the relief the pad
      exists to build.

    ``config.PAD_HOST_PAVEMENT_LEVEL`` off → no-op (byte-identical; the env
    override died 2026-08-05).  Returns
    the count of pads re-levelled."""
    from auto_patch.config import (
        PAD_HOST_PAVEMENT_LEVEL, PAD_HOST_LEVEL_CONTACT_M,
        PAD_HOST_LEVEL_LIFT_M, PAD_HOST_LEVEL_TRIGGER_M,
        DSF_OBJECT_PAD_MAX_RELIEF_M,
    )
    from auto_patch.layout import ROLE_OBJECT_PAD
    if not PAD_HOST_PAVEMENT_LEVEL:
        return 0
    pad_role = pad_role or ROLE_BUILDING
    object_pads = (pad_role == ROLE_OBJECT_PAD)

    # Host pavement vertices with a solved altitude: (x, y, alt, ring_id,
    # vertex_index).  ``host_rings`` carries each host's own SOLVED
    # SURFACE — the ring positions and the values the solve wrote on them
    # — because the probe below samples that surface AT the pad ring
    # (R19-1, re-ruled 2026-08-12) rather than hunting for a vertex.
    host_verts: list = []
    host_rings: list = []          # [(pts, alts)] indexed by ring_id
    host_shapes_by_rid: list = []  # the shape each ring_id came from
    for s in layout.shapes:
        if s.role not in _PAD_HOST_ROLES:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        n_open = len(ring)
        rid = len(host_rings)
        host_shapes_by_rid.append(s)
        r_pts = [(float(x), float(y)) for (x, y) in ring]
        r_alts = [_shape_vertex_alt(s, idx, n_open) for idx in range(n_open)]
        host_rings.append((r_pts, r_alts))
        for idx, (x, y) in enumerate(r_pts):
            a = r_alts[idx]
            if a is not None:
                host_verts.append((x, y, a, rid, idx))
    if not host_verts:
        return 0

    r = float(PAD_HOST_LEVEL_CONTACT_M)
    r2 = r * r
    lift_r2 = float(PAD_HOST_LEVEL_LIFT_M) ** 2
    trigger = float(PAD_HOST_LEVEL_TRIGGER_M)

    # ── THE FIELD'S PURITY FILTER (R19-1) ────────────────────────────
    # A host ring vertex within the contact radius of ANY pad ring is
    # SOMEBODY'S LIP: it carries that pad's value, written into the host
    # ring by the weld, and it is not a sample of the host's own solved
    # surface.  Removing every pad's lips — not just the lips of the pad
    # being levelled — is what makes the field swap-proof: a neighbouring
    # pad's value is not in the host's field at all, however near it
    # sits.  (Measured while writing this law: with only the levelled
    # pad's own lips removed, a neighbour lip 4 m away outvoted the
    # host's body 34 m away and the pad took the neighbour's level.)
    #
    # Gridded at the contact radius so this stays linear in the corpus:
    # HECA is ~10k host vertices against ~2k pad ring positions.
    pad_cells: dict = {}
    for _s in layout.shapes:
        if _s.role not in (ROLE_BUILDING, ROLE_OBJECT_PAD):
            continue
        if _s.polygon is None or _s.polygon.is_empty:
            continue
        try:
            _pring = _open_ring(list(_s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        for (_px, _py) in _pring:
            pad_cells.setdefault((int(_px // r), int(_py // r)),
                                 []).append((float(_px), float(_py)))

    def _touched_by_a_pad(hx, hy):
        cx = int(hx // r)
        cy = int(hy // r)
        for dx_ in (-1, 0, 1):
            for dy_ in (-1, 0, 1):
                for (px, py) in pad_cells.get((cx + dx_, cy + dy_), ()):
                    if (hx - px) ** 2 + (hy - py) ** 2 <= r2:
                        return True
        return False

    host_lip = [[_touched_by_a_pad(x, y) for (x, y) in _pts]
                for (_pts, _alts) in host_rings]
    # The LEVEL FAMILY's membership table and the per-host area the
    # host's own body vertices vote with (R19-1).
    # ATTRIBUTION PROBE (task #16).  ``O4_PAD_FAMILY_DEBUG=ref[,ref...]``
    # reports each named pad's SEEDS, its family MEMBERS and the
    # COALITION — the reading that says why a pad did or did not adopt.
    # It is what measured the task-#16 finding (2026-08-12): at HECA the
    # family forms and building114 DOES adopt 85.59 here, and the LATE
    # final grade projection (``pipeline.py``, ``O4_FINAL_PROJECTION_LATE``)
    # re-stamps 88.5 over it afterwards.  Off ⇒ zero cost.
    # ``*`` reports EVERY group (the attribution reading: which door the
    # groups that did not adopt left by), a ref list reports those refs.
    _dbg = {r for r in _os.environ.get("O4_PAD_FAMILY_DEBUG", "").split(",")
            if r}
    _dbg_all = "*" in _dbg

    def _dbg_line(msg):
        try:
            import O4_UI_Utils as _UI
            _UI.vprint(1, "  " + msg)
        except Exception:
            pass

    # THE WELD'S OWN TOLERANCE — the membership relation is "will weld
    # together" (task #16); this module never spells the number itself.
    from auto_patch.conformance import FINAL_WELD_TOL_M as _WELD_TOL_M
    pad_lips_by_ring = _pad_lip_index(layout, host_rings,
                                      host_shapes_by_rid, _WELD_TOL_M)
    host_areas = []
    _hi = 0
    for _s in layout.shapes:
        if _s.role not in _PAD_HOST_ROLES:
            continue
        if _s.polygon is None or _s.polygon.is_empty:
            continue
        try:
            _open_ring(list(_s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        host_areas.append(float(_s.polygon.area))
        _hi += 1
    pad_by_id = {id(_s): _s for _s in layout.shapes
                 if _s.role in (ROLE_BUILDING, ROLE_OBJECT_PAD)}
    _COALITION_WINDOW_M = _coalition_window_m()

    # Host shapes indexed by role for the shared-boundary lift below.
    host_shapes = [s for s in layout.shapes
                   if s.role in _PAD_HOST_ROLES
                   and s.polygon is not None and not s.polygon.is_empty]

    # THE PAD GROUPS.  A building pad is one shape; an OBJECT pad is a
    # request — a flat CORE plus the blend plates that ramp it out — and
    # the group moves together or not at all (R19-3: "pad + blend").
    # ``adopt_delta`` is the role's own threshold: the trigger for a
    # building, the pad's RELIEF BUDGET for an object pad.
    if object_pads:
        groups = _object_pad_groups(layout)
        adopt_delta = float(DSF_OBJECT_PAD_MAX_RELIEF_M)
    else:
        groups = [(s, [s]) for s in layout.shapes
                  if s.role == ROLE_BUILDING
                  and s.polygon is not None and not s.polygon.is_empty]
        adopt_delta = trigger

    n_relevelled = 0
    # THE PASS'S OWN CENSUS (2026-08-12).  Every group leaves this loop
    # through exactly one of these counters, so "0 pads adopted" is
    # ATTRIBUTED by the build that produced it instead of being inferred
    # from the emitted patch afterwards — the reading that cost this law
    # a whole round when 0 of 139 HECA object pads adopted and nothing in
    # the log said which door they left by.
    _cen = {"groups": len(groups), "no_level": 0, "no_seeds": 0,
            "refused": 0, "within": 0, "adopted": 0}
    _worst = 0.0
    for (s, group) in groups:
        if s.polygon is None or s.polygon.is_empty:
            _cen["no_level"] += 1
            continue
        if getattr(s, "basin_floor_seat_m", None) is not None:
            # A PAD INSIDE A BASIN DOES NOT ADOPT ITS HOST (owner
            # RULINGS 2026-08-25f).  This pass exists to lift a pad the
            # DEM-biased frontage seat left in a PIT while its host
            # humped around it — and a pad inside a basin is in a pit
            # BY DECLARATION.  Adopting the host's grade here is
            # precisely the erasure this ruling reverses.
            _cen["refused"] += 1
            continue
        cur = _building_flat_level(s)
        if cur is None:
            _cen["no_level"] += 1
            continue
        ring = []
        for g in group:
            # An object-pad request's contact with the host is made by
            # whichever of its plates reaches the pavement, so the probe
            # ring is the whole GROUP's boundary (for a building pad the
            # group is the pad itself, so this is the same ring as before).
            if g.polygon is None or g.polygon.is_empty:
                continue
            try:
                ring.extend(_open_ring(list(g.polygon.exterior.coords)))
            except (ValueError, TypeError):
                continue
        if not ring:
            _cen["no_level"] += 1
            continue
        # Host pavement nodes within reach of the pad ring.  The pad ring and
        # the host share a boundary, and after the post-solve welds/decimation
        # a shared "lip" node may drift a few decimetres off the pad vertex —
        # so a GEOMETRIC coincidence test is unreliable here.  Classify by
        # VALUE instead: a host node whose level agrees with the pad's current
        # (possibly pit) level is a shared-boundary lip (the contamination); a
        # host node that DIFFERS by more than the trigger is the genuine step
        # partner = the HOST BODY the pad must adopt.
        # THE PAD'S OWN VALUE ENVELOPE.  A flat building pad is a single
        # value, so ``[cur, cur]``; an object-pad request spans its core
        # AND its blend plates (the ramp out to DEM), and a host node
        # welded anywhere along that ramp carries a PAD value — HECA's
        # apron -10629 held 106.05 / 106.12 at object_pad:56's contact,
        # half a metre off the core's 105.51, which a ``cur``-only lip
        # test reads as neither lip nor body and the probe then walks
        # nowhere.  For a building pad the envelope collapses to the
        # existing test exactly.
        grp_vals = [float(v) for g in group
                    for v in ((g.node_altitudes or [])
                              + ([g.altitude] if g.altitude is not None
                                 else []))
                    if v is not None]
        grp_lo = min(grp_vals) if grp_vals else cur
        grp_hi = max(grp_vals) if grp_vals else cur

        # ── THE LEVEL FAMILY AND ITS AGREEING COALITION (R19-1) ─────
        # Re-ruled 2026-08-12 (lead), after a contact probe, a bounded
        # ring walk and a host-surface field sample each missed: do not
        # read the host's surface at all.  Pads WELDED INTO ONE HOST
        # RING, chained by lip adjacency, are one LEVEL FAMILY together
        # with the host's own body vertices on that chain, and the
        # family's level is the AGREEING COALITION — R12 amendment 4's
        # ratified idiom (``post_mesh.agreeing_coalition``), reused here
        # with its window constant class (0.25 m,
        # ``post_mesh._MEMBER_DELTA_AGREEMENT_WINDOW_M``) and its
        # ≥2-member / no-tie refusals.  Members outside the coalition
        # ADOPT it.
        #
        # THE WEIGHT IS AREA, which is what makes swap impossible.  A
        # member votes with the ground it owns: HECA building114 is
        # 181.3 m² and building112 is 15,298.4 m², so the small pad can
        # never drag the big one whatever it reads, and the coalition at
        # that site is 112 + 113 + the apron's own corners at 85.63.  The
        # previous mechanism had no such floor and moved building112 off
        # its host level (85.63 → 86.45, measured, arm r19field).
        #
        # MEMBERSHIP IS STRUCTURAL, never a distance: a pad joins only
        # through host-ring vertices its own contact radius touches, so
        # two families on separate chains cannot merge however near they
        # sit.
        members = _level_family_members(
            group, pad_by_id, host_rings, host_areas, host_lip,
            pad_lips_by_ring, trigger, lift_r2)
        if _dbg_all or (_dbg and (getattr(s, "ref", None) or "") in _dbg):
            _own = {id(g) for g in group}
            _seeds = [(rid, i)
                      for rid, verts in pad_lips_by_ring.items()
                      for i, ids in verts.items() if ids & _own]
            _mm = ("None" if members is None else
                   "; ".join(f"{e['kind']}:{e['delta_m']:.2f}"
                             f"@{e['weight']:.0f}" for e in members[:12]))
            _dbg_line(f"[padfam] {s.ref} cur={cur:.2f} seeds={_seeds[:8]} "
                      f"n_seeds={len(_seeds)} members={_mm}")
        if members is None:
            _cen["no_seeds"] += 1
            continue
        coalition, _outliers, refusal = _AGREEING_COALITION(
            members, _COALITION_WINDOW_M,
            weight_of=lambda entry: entry["weight"],
            # THE ARBITRATION DIRECTION, when two rival levels weigh the
            # same: the pad adopts FROM the host, never the reverse, so
            # the side carrying the host's own ground wins.
            tiebreak_of=lambda entry: (entry["weight"]
                                       if entry["kind"] == "host" else 0.0))
        if _dbg_all or (_dbg and (getattr(s, "ref", None) or "") in _dbg):
            _dbg_line(f"[padfam] {s.ref} coalition="
                      f"{[round(e['delta_m'], 2) for e in coalition][:8]} "
                      f"refusal={refusal} adopt_delta={adopt_delta}")
        if refusal is not None or not coalition:
            _cen["refused"] += 1
            continue      # genuine ambiguity — the pad stays put
        level = _median_of([e["delta_m"] for e in coalition])
        body_vals = [level] if abs(level - cur) > adopt_delta else []
        if not body_vals:                     # agrees with host / not adjacent
            _cen["within"] += 1
            continue
        body_vals.sort()
        m = len(body_vals)
        med = (body_vals[m // 2] if m % 2
               else 0.5 * (body_vals[m // 2 - 1] + body_vals[m // 2]))
        new_level = round(float(med), 2)
        # ── AMENDMENT 1 (Fable lead 2026-08-12b), rules 1 + 2 ──────────
        # Measured defect: a 0.16 m upstream shift at HECA building211
        # crossed ``PAD_HOST_LEVEL_TRIGGER_M`` and TELEPORTED the seat
        # +0.82 m; the lip carried it into apron -10634 (the apron node at
        # the pad reads exactly the pad seat), and the apron's 425 m
        # chords took +203 within-shape rows — a groundside object moving
        # airside, which "airside is king" forbids.
        #
        # (2) ADOPTION IS CONTINUOUS in the host-pad delta: zero at the
        #     trigger, full at 2x the trigger.  The trigger is reused as
        #     the ramp width — no second constant.  Building pads only:
        #     an OBJECT pad's threshold is its RELIEF BUDGET under R19-3
        #     ("within the budget the pad keeps its own target"), a
        #     different law with a different meaning, left untouched.
        # (1) AN AIRSIDE VERTEX NEVER CARRIES A PAD-AUTHORED VALUE.  In
        #     the ramp region the pad would land BETWEEN its own value and
        #     the host's, so the lip could only be reconciled by writing a
        #     pad-authored number onto an airside ring — forbidden.  On an
        #     airside host the pad therefore moves only when it can adopt
        #     the host level IN FULL, which is what makes the amendment's
        #     "the lip is equal by construction" true: the only value the
        #     lip lift can then write is the host's OWN body level.  Below
        #     that the pad stays put (strictly less airside movement than
        #     before, never more).  A groundside host (service_junction)
        #     keeps the ramp and its lip lift — nothing airside is written
        #     either way.
        if not object_pads:
            _delta = new_level - cur
            _mag = abs(_delta)
            _w = (1.0 if _mag >= 2.0 * trigger
                  else max(0.0, (_mag - trigger) / trigger))
            if _pad_has_airside_host(s, host_shapes, ring, lift_r2):
                if _w < 1.0:
                    continue          # rule 1: no partial adoption airside
            elif _w < 1.0:
                new_level = round(float(cur + _w * _delta), 2)
                if abs(new_level - cur) <= 1e-9:
                    continue
        if object_pads:
            # THE OBJECT-PAD ADOPTION (R19-3): the whole request moves by
            # ONE delta — the flat core to the host level, every blend
            # plate by the same amount, so the ramp the blend was built
            # with (core value → DEM) is preserved rather than re-derived
            # from a value the emitter no longer has.  The host body is
            # untouched and NO lip lift runs: an object pad's contact with
            # pavement is made at emit time (the pad is clipped out of
            # every pavement ring before it is written), so the apron
            # nodes that carried the pad's value are welds of the pad's
            # own number and follow it down by construction.
            delta = new_level - cur
            for g in group:
                if g.altitude is not None:
                    g.altitude = round(float(g.altitude) + delta, 2)
                if g.node_altitudes:
                    g.node_altitudes = [
                        (None if v is None else round(float(v) + delta, 2))
                        for v in g.node_altitudes]
                if g.altitude_high is not None:
                    g.altitude_high = round(float(g.altitude_high) + delta, 2)
                if g.altitude_low is not None:
                    g.altitude_low = round(float(g.altitude_low) + delta, 2)
            n_relevelled += 1
            _cen["adopted"] += 1
            _worst = max(_worst, abs(delta))
            continue
        # (1) The pad seats FLAT at the host body level.
        s.altitude = new_level
        if s.node_altitudes:
            closed = (s.node_altitudes[0] == s.node_altitudes[-1]
                      and len(s.node_altitudes) > 1)
            s.node_altitudes = [new_level] * len(s.node_altitudes)
            if closed:
                s.node_altitudes[-1] = new_level
        s.altitude_high = None
        s.altitude_low = None
        n_relevelled += 1
        _cen["adopted"] += 1
        _worst = max(_worst, abs(new_level - cur))
        # (2) Un-contaminate the host's SHARED boundary lip: every host ring
        # vertex within reach of the pad ring that still carries the pad's old
        # pit value is a shared-boundary node dragged down by the old DEM seat.
        # Lift it to ``new_level`` (= the host body level) — otherwise the
        # emit's per-bucket merge sees the pad's new value and the host's stale
        # pit value disagree by > merge tol and mints a fresh cliff node at the
        # shared lat/lon (a vertical wall at the pad edge).  Lifting the lip to
        # the body level welds pad and host at one flat level — the step goes.
        for h in host_shapes:
            # AMENDMENT 1 rule 1, enforced at the write itself as well as at
            # the decision: an airside lip is only ever written when the pad
            # adopted the host level IN FULL, so the value going onto the
            # airside ring is the HOST's own body level — never a
            # pad-authored one.  (``_w`` is 1.0 on every airside path by the
            # decision above; the guard is the structural statement of it,
            # so a future edit there cannot silently re-open the channel.)
            if (not object_pads and _is_airside_role(h.role)
                    and abs(new_level - level) > 1e-9):
                continue
            try:
                hcoords = list(h.polygon.exterior.coords)
            except (ValueError, TypeError):
                continue
            hring = hcoords[:-1] if (hcoords and hcoords[0] == hcoords[-1]) \
                else hcoords
            n_hopen = len(hring)
            hna = h.node_altitudes
            for hidx, (hx, hy) in enumerate(hring):
                hval = _shape_vertex_alt(h, hidx, n_hopen)
                if hval is None or abs(hval - cur) > trigger:
                    continue                  # not a pit-lip node → leave it
                near_pad = False
                for (px, py) in ring:
                    ddx = hx - px
                    ddy = hy - py
                    if ddx * ddx + ddy * ddy <= lift_r2:
                        near_pad = True
                        break
                if not near_pad:
                    continue
                if hna and len(hna) >= n_hopen:
                    hna[hidx] = new_level
                    if len(hna) == n_hopen + 1 and hidx == 0:
                        hna[-1] = new_level
                elif h.altitude is not None:
                    # Flat host shape: promote to per-vertex so the shared lip
                    # carries the body level without flattening the whole host.
                    base = [float(h.altitude)] * n_hopen
                    base[hidx] = new_level
                    h.node_altitudes = base + [base[0]]
                    hna = h.node_altitudes
                    h.altitude = None
    if _cen["groups"]:
        _dbg_line(
            f"[pav-builder] pad-host level census "
            f"({'object_pad' if object_pads else 'building'}): "
            f"{_cen['groups']} group(s) — {_cen['adopted']} adopted "
            f"(worst |delta| {_worst:.2f} m), {_cen['within']} within "
            f"{adopt_delta:.2f} m of the host, {_cen['refused']} no "
            f"agreeing coalition, {_cen['no_seeds']} no family (the pad "
            f"welds to no host ring), {_cen['no_level']} no level.")
    return n_relevelled
