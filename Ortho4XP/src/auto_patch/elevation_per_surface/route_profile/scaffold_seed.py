"""THE SCAFFOLD SEED — the apron interior starts as a TAUT MEMBRANE on the
centerline scaffold, not as a tracing of the terrain.

OWNER RULING RULINGS 2026-08-24c: *"Aprons are graded like taxiways and
runways — the taut membrane on the scaffold, never a DEM drape.  The
apron's reference surface is the SCAFFOLD INTERPOLATION — taxi centerline
profiles + seated building pads as anchors, taut-string/smooth-plane
between them — with NO DEM attraction on the apron interior."*

ADDENDUM (owner 2026-08-24c): *"Where an apron has NO building pads, its
edge nodes farthest from any taxi centerline may SEED at DEM — but they are
NEVER hard anchors: they stay FREE in the projection, and the membrane cuts
into hills or raises fills as needed to stay within the grade caps."*  So
the interpolation DEGRADES GRACEFULLY: the anchors are centerline profiles
and seated pads ONLY, and DEM survives solely as the pre-existing soft seed
of a node no anchor reaches.  Nothing here writes ``base_hard``.

WHY THIS IS A RE-SEED AND NOT THE SEED (a deviation, recorded).  The
ruling says the apron interior's SEED becomes the scaffold interpolation.
It cannot be produced inside ``solver_primitives._seed_elevations``:
neither anchor source exists there.  Taxi centerline profile values are
minted by ``_solve_spine_profile`` (phase A) and pad seats by
``anchors.build_building_seats``, both hundreds of lines LATER in
``solve_route_profile``, and both structurally depend on the reach band and
the unified graph, which depend on the node list the seeder is producing.
The solver runs exactly once, so no warm start carries them either.  The
only alternative would be a second, pre-solve taxi-profile authority, which
the engine's single-source law forbids.  So the scaffold value is applied
as an OVERRIDE one statement after the anchors exist — the same idiom the
adjacent-ground zone seed already uses right after the seeder — and the
DEM branch in the seeder becomes a placeholder the scaffold overwrites.

NO NEW INTERPOLATOR.  The taut value comes from
``law_graph_budget.build_anchor_envelope`` — the engine's own value-seeded
multi-source Dijkstra that turns scattered anchors into a per-node
cap-Lipschitz ``[floor, ceiling]``.  A node's taut level is the CHEBYSHEV
CENTRE of that interval: the level furthest from both binding anchors, i.e.
the flattest membrane the scaffold admits there.  Where the interval is a
point the anchors decide outright; where the anchors do not reach, there is
no interval and the node keeps whatever it had.
"""

from __future__ import annotations

import os as _os
from typing import Dict, Optional

from .law_graph_budget import build_anchor_envelope

#: Kill switch (default ON in this lane, owner order).  ``0`` restores the
#: DEM-seeded apron interior exactly — the scaffold pass does not run and
#: writes nothing.
APRON_SCAFFOLD_SEED = (
    _os.environ.get("O4_APRON_SCAFFOLD_SEED", "1") != "0")

#: Values closer together than this are the same level (the convergence
#: guards' standing 0.01 m elevation floor).  A scaffold value within it of
#: the seed it replaces is counted as unmoved rather than reported.
_SEED_MOVE_TOL_M = 0.01

#: Jacobi sweeps for the Dirichlet fill of nodes the envelope cannot bound.
#: The fill propagates one graph ring per sweep, so this is a REACH IN
#: HOPS, not in metres — and it is bounded only so a pathological graph
#: cannot spin.  Anything still unfilled after it belongs to an apron with
#: no anchors at all.
_FILL_SWEEPS = 64


def scaffold_anchor_values(anchor_nodes, elev, building_seats=None,
                           n: Optional[int] = None) -> Dict[int, float]:
    """THE SCAFFOLD'S ANCHORS: ``{node: level}`` from the two authorities
    the ruling names, and no others.

    ``anchor_nodes``    the SPINE nodes whose phase-A centerline profile
                        has just been solved — their values are read out of
                        ``elev``, so this mints no second profile authority.
    ``building_seats``  ``{pad_node: flat_level}`` from
                        ``anchors.build_building_seats``.

    THE DEM IS NOT AN ANCHOR and never enters here — that is the ruling's
    whole point.  A pad seat wins a shared node: it is a flat datum the
    surface must meet exactly, while a spine value is a profile the apron
    grades along.
    """
    out: Dict[int, float] = {}
    for i in (anchor_nodes or ()):
        k = int(i)
        if n is not None and not (0 <= k < n):
            continue
        try:
            v = float(elev[k])
        except (IndexError, TypeError, ValueError):        # pragma: no cover
            continue
        if v == v:                                         # not NaN
            out[k] = v
    for i, v in (building_seats or {}).items():
        k = int(i)
        if n is not None and not (0 <= k < n):
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):                    # pragma: no cover
            continue
    return out


def taut_level(box) -> Optional[float]:
    """The TAUT level inside a cap-Lipschitz ``(floor, ceiling)``: its
    CHEBYSHEV CENTRE.

    That is the level furthest from both binding anchors, so it is the
    flattest membrane the scaffold admits at this node — a string pulled
    taut between its pegs, which is the ruling's own image.  An INVERTED
    interval (floor above ceiling) means the anchors contradict each other
    there; it is not silently resolved, it is declined, and the caller
    counts it.
    """
    if box is None:
        return None
    lo, hi = box
    if lo is None or hi is None:
        return None
    lo, hi = float(lo), float(hi)
    if lo != lo or hi != hi:                               # pragma: no cover
        return None
    if lo > hi:
        return None
    return 0.5 * (lo + hi)


def scaffold_seed_apron_interior(elev, *, adjacency, anchor_values,
                                 interior_nodes, node_band=None,
                                 horizon_m: Optional[float] = None) -> dict:
    """Re-seed the APRON INTERIOR onto the scaffold membrane, in place.

    Writes ``elev`` ONLY.  ``base_hard`` is never touched: every re-seeded
    node stays FREE in the projection, which is the owner's addendum and
    is what lets the caps afterwards cut the membrane into a hill or raise
    it over a hollow.

    ``adjacency``      ``{i: [(j, budget), ...]}``, the projection's own
                       law-edge adjacency (``one_solve._build_adjacency``).
                       Budgets are ``cap x length``, so the envelope this
                       produces is exactly "what the caps permit from the
                       anchors" — no second notion of reach.
    ``interior_nodes`` the apron-interior node set to re-seed.  Anchors are
                       excluded by construction below: an anchor's own
                       value is the authority, never a thing to interpolate.
    ``node_band``      the ONE reach band, per node, when the caller has it.
                       The scaffold value is clamped into it — there is one
                       band and a seed outside it would be a level the
                       projection cannot honour anywhere.

    Returns a report dict; nothing is printed here.
    """
    report = {"seeded": 0, "no_anchor_reach": 0, "contradicted": 0,
              "band_clamped": 0, "worst_move_m": 0.0, "anchors": 0,
              "dirichlet_filled": 0}
    if not APRON_SCAFFOLD_SEED or not interior_nodes:
        return report
    env = build_anchor_envelope(adjacency, anchor_values,
                                horizon_m=horizon_m)
    if env is None:
        return report
    report["anchors"] = env.anchor_count
    unreached = []
    for i in interior_nodes:
        k = int(i)
        if k in anchor_values or not (0 <= k < len(elev)):
            continue
        box = env.box(k)
        if box is None:
            # ── NO "REACH" (lead ruling 2026-08-24, correcting this
            # lane's first cut) ─────────────────────────────────────────
            # The membrane is a BOUNDARY-VALUE problem: the anchors are
            # DIRICHLET data and the harmonic surface exists at EVERY
            # interior node.  Cap-budget reach was a misreading — the
            # owner's "cut into hills or raise fills" says distance never
            # ORPHANS a node.  So a node the envelope cannot bound is not
            # abandoned to the DEM; it is collected and filled below by
            # relaxation from its own neighbours.  DEM survives only for
            # an apron with ZERO anchors, where the fill has nothing to
            # propagate and every node stays where it was.
            unreached.append(k)
            continue
        lvl = taut_level(box)
        if lvl is None:
            report["contradicted"] += 1
            continue
        if node_band is not None:
            nb = node_band[k] if k < len(node_band) else None
            if nb is not None:
                blo, bhi = nb
                if blo is not None and bhi is not None and blo <= bhi:
                    clamped = min(max(lvl, float(blo)), float(bhi))
                    if clamped != lvl:
                        report["band_clamped"] += 1
                        lvl = clamped
        move = abs(lvl - float(elev[k]))
        elev[k] = lvl
        if move > _SEED_MOVE_TOL_M:
            report["seeded"] += 1
            if move > report["worst_move_m"]:
                report["worst_move_m"] = move

    # ── THE DIRICHLET FILL: every remaining interior node ─────────────
    # Jacobi relaxation of the discrete Laplacian over the law graph, with
    # the anchors and the already-placed nodes as the boundary — the
    # harmonic surface the ruling names, and the same relaxation
    # ``one_profile_solve`` runs afterwards (it is a fixed point of that
    # sweep, so this only starts it closer).  A node with no placed
    # neighbour yet simply waits for a later sweep; one that never gets a
    # neighbour belongs to an apron with no anchors at all and keeps its
    # DEM seed, which is the ruling's one surviving DEM case.
    if unreached:
        placed = {k for k in interior_nodes
                  if int(k) not in unreached} | set(anchor_values)
        pending = set(unreached)
        for _sweep in range(_FILL_SWEEPS):
            if not pending:
                break
            updates = {}
            for k in pending:
                vals = [float(elev[j]) for (j, _b) in adjacency.get(k, ())
                        if j in placed and 0 <= j < len(elev)]
                if vals:
                    updates[k] = sum(vals) / len(vals)
            if not updates:
                break
            for k, v in updates.items():
                if node_band is not None and k < len(node_band):
                    nb = node_band[k]
                    if nb is not None and nb[0] is not None \
                            and nb[1] is not None and nb[0] <= nb[1]:
                        v = min(max(v, float(nb[0])), float(nb[1]))
                move = abs(v - float(elev[k]))
                elev[k] = v
                if move > _SEED_MOVE_TOL_M:
                    report["seeded"] += 1
                    if move > report["worst_move_m"]:
                        report["worst_move_m"] = move
            placed |= set(updates)
            pending -= set(updates)
        report["no_anchor_reach"] = len(pending)
        report["dirichlet_filled"] = len(unreached) - len(pending)
    return report


def format_report(icao: str, report: dict) -> str:
    """The build log's one line — named so a reader can tell a scaffold
    membrane from a DEM drape without opening the patch."""
    return (f"  [scaffold-seed] {icao}: {report['seeded']} apron-interior "
            f"node(s) re-seated on the centerline scaffold from "
            f"{report['anchors']} anchor(s) (worst move "
            f"{report['worst_move_m']:.2f} m); "
            f"{report.get('dirichlet_filled', 0)} filled by Dirichlet "
            f"relaxation; {report['no_anchor_reach']} node(s) on "
            f"anchor-less aprons kept their DEM seed (FREE, never pinned "
            f"— owner addendum); "
            f"{report['band_clamped']} clamped into the reach band, "
            f"{report['contradicted']} left alone on contradicting anchors "
            f"— RULINGS 2026-08-24c")
