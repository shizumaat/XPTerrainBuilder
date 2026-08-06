"""Validate the AS-BUILT within-shape grade with the unified grade graph.

This is the validator side of the single grade graph (docs/single_grade_graph.md):
it builds the SAME :mod:`auto_patch.grade_graph` constraints the solver used —
from the emitted ``layout.shapes`` (apron/junction rings + their elevations) —
and checks each constrained pair against the realised surface.  Because both the
solver and this validator call ``grade_graph.shape_constraints``, the surface we
BUILD and the surface we CHECK cannot drift for apron/junction shapes.

Rects / runways / terminals / groundside are NOT owned by the grade graph; the
caller's existing per-role audit keeps validating those.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from . import grade_graph as GG
from .config import (ELEV_ROUNDING_NOISE_M,
                     SLOPED_QUAD_ROUNDING_NOISE_M as _SLOPED_QUAD_NOISE_M,
                     taxi_grade_cap_for_letter)
from .grade_law import pair_grade_budget_m


from .grade_graph import _open_ring


def _shape_elevs(s, n):
    """Per-vertex emitted elevations for a shape ring (open, length n) or None."""
    if s.altitude is not None:
        return [float(s.altitude)] * n
    na = s.node_altitudes
    if na is not None:
        na = list(na)
        if len(na) == n + 1:
            na = na[:-1]
        if len(na) == n and all(e is not None for e in na):
            return [float(e) for e in na]
    # Sloping 4-corner rect emitted as a tilted plane: the canonical convention
    # (``_writeback``/``_canonicalise_rect``) is corners [0,3]=HIGH, [1,2]=LOW.
    if (s.altitude_high is not None and s.altitude_low is not None and n == 4):
        hi, lo = float(s.altitude_high), float(s.altitude_low)
        return [hi, lo, lo, hi]
    return None


def _iter_checked_pairs(layout):
    """Yield EVERY within-shape constrained pair the validator checks, as
    ``(role, is_spine, (xa, ya), za, (xb, yb), zb, cap)``:

      * apron / junction within-shape edges (body + spine, ``grade_graph``).

    The single source ``within_violations`` (which applies the cap check)
    consumes, so the checker cannot drift from the law.  Runway joins are
    handled separately (one side is a runway-surface sample, not a node)."""
    ctx = GG.build_context(layout)

    # apron / junction within-shape (body + spine).
    _lockstep_bake = getattr(layout, "_lockstep_shape_bake", None) or {}
    for s in layout.shapes:
        if (s.role not in GG.SOFT_VISIBILITY_ROLES or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        nlen = len(ring)
        if nlen < 3:
            continue
        elevs = _shape_elevs(s, nlen)
        if elevs is None:
            continue
        # LOCKSTEP BAKE ADOPTION (2026-07-17): when the solver exported
        # this shape's baked decomposition (``build_unified_graph``,
        # ring-position space) and the ring is UNCHANGED, consume it
        # verbatim — the validator then checks the exact allowances the
        # solve enforced, and the two sides cannot drift (measured
        # CYXY: 29/9,915 edges differed on re-bake).  A mutated ring
        # (post-solve clip/weld) misses the guard and falls through to
        # the fresh bake below.
        baked = _lockstep_bake.get(id(s))
        if baked is not None:
            baked_role, baked_signature, baked_edges, baked_spine = baked
            ring_signature = tuple(
                (round(x, 6), round(y, 6)) for (x, y) in ring)
            if baked_role == s.role and baked_signature == ring_signature:
                for (a, b, cap) in baked_edges:
                    if a < nlen and b < nlen:
                        is_spine = (min(a, b), max(a, b)) in baked_spine
                        yield (s.role, is_spine, ring[a], elevs[a],
                               ring[b], elevs[b], cap)
                continue
        gs = GG.GradeShape(role=s.role, ring=[(x, y) for (x, y) in ring],
                           keys=list(range(nlen)),
                           fan_ramp_zone=getattr(s, "fan_ramp_zone", False))
        # Activate the building-step exemption in INDEX key-space: ctx.building_keys
        # are rounded coords (validator mode) but this shape's keys are ring
        # indices, so resolve which ring vertices sit on a building pad and pass a
        # per-shape index set.  Matches the solver (whose global node-index keys
        # make the exemption active) and the grade test (check_grade, nid keys).
        bld_idx = frozenset(
            i for i, (x, y) in enumerate(ring)
            if (round(x, 3), round(y, 3)) in ctx.building_keys)
        ctx_s = _dc.replace(ctx, building_keys=bld_idx) if bld_idx else ctx
        sc = GG.shape_constraints(gs, ctx_s)
        spine_pairs = set()
        for chain in sc.spine_chains:
            for a, b in zip(chain, chain[1:]):
                spine_pairs.add((min(a, b), max(a, b)))
        for (a, b, cap) in sc.edges:
            is_spine = (min(a, b), max(a, b)) in spine_pairs
            yield (s.role, is_spine, ring[a], elevs[a], ring[b], elevs[b], cap)

    # (2026-07-29) The sloping-rect + end-cap all-pair stage was retired
    # with the rect machinery — no live shape carries a rect role or the
    # ``is_rect_cap`` flag, so the checker mirrors the solver exactly with
    # the within-shape stage above alone.


def within_violations(layout, noise=ELEV_ROUNDING_NOISE_M):
    """Return the apron/junction within-shape grade violations of the emitted
    ``layout``, as ``[(pct, cap, dist, role, is_spine, x, y), ...]`` (worst
    first).  Uses the unified grade graph — identical constraints to the solver.

    SPINE CROWN (part 30): a pair's budget re-centres on the crown target
    ``grade_law.crown_pair_offset`` — the same per-node drop field the
    solver's writeback applied (``layout._crown_drop_key``), so a crowned
    cross-section spends none of its longitudinal budget on the designed
    drop.  Empty field (gate off / old layout) ⇒ byte-identical check."""
    from .grade_law import crown_pair_offset
    _crown_field = getattr(layout, "_crown_drop_key", None) or {}
    if _crown_field:
        from .crown import crown_drop_at

        def _drop(x, y):
            return crown_drop_at(layout, x, y)
    else:
        def _drop(x, y):
            return 0.0
    # BREAK-REGION SCOPING — DELETED 2026-08-04 (spec ``docs/specs/kill-
    # half-spec.md`` §2).  A pair touching a solver-declared broken node
    # used to be skipped here, exactly as ``check_grade.run_checks`` split
    # it out of the actionable count.  Both readers are now full-census:
    # quarantine is unauthorized (docs/RULINGS.md) and "all counts are
    # full-census, never quarantine-excluded", so every pair this frame
    # can price is priced.  The law's own exemptions (lawful terraces, the
    # open-boundary floor, materiality) still adjudicate — a census row is
    # not automatically a violation ("the goal is LAW COMPLIANCE, not
    # instrument-zero").
    viol = []
    for (role, is_spine, (xa, ya), za, (xb, yb), zb, cap) in \
            _iter_checked_pairs(layout):
        d = math.hypot(xa - xb, ya - yb)
        if d < 1e-6:
            continue
        de = abs((za - zb) - crown_pair_offset(_drop(xa, ya),
                                               _drop(xb, yb)))
        # Budget = grade_law.pair_grade_budget_m (max of the anisotropic
        # bake and the flat cap × run — the ONE formula shared with
        # tools/check_grade.py, 2026-07-17) plus this frame's
        # quantization envelope: junction-family rings are the emit
        # weld-hubs whose conformance inserts displace short edges up
        # to a decimetre (SLOPED_QUAD_ROUNDING_NOISE_M), every other
        # role keeps the per-node envelope (``noise``).
        _pair_noise = (
            _SLOPED_QUAD_NOISE_M
            if role in ("junction", "service_junction") else noise)
        if de > pair_grade_budget_m(cap, d) + _pair_noise:
            viol.append(((de / d) * 100.0, cap.flat_cap() * 100.0, d, role,
                         is_spine, 0.5 * (xa + xb), 0.5 * (ya + yb)))
    # The taxi spine also ANCHORS into the runway (one side is a runway-surface
    # sample, not a node) — checked separately, flagged is_spine.
    viol.extend(_spine_runway_join_violations(layout, noise))
    viol.sort(reverse=True)
    return viol


def _spine_runway_join_violations(layout, noise):
    """The taxi spine ANCHORS into the runway (user 2026-06-25): where a taxi
    centerline meets a runway, the grade from the runway SURFACE at the contact to
    the nearest emitted taxiway/junction node must be ≤ the centerline's per-letter
    cap.  Catches a spine that drops below the runway at the join (the F/14R
    valley) — invisible to the per-shape graph because the runway is not in it."""
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING
    from auto_patch.pavement.runways import _sample_runway_segment_elev
    import os as _os
    from auto_patch.grade_law import (
        RUNWAY_CONTACT_M, RUNWAY_JOIN_COINCIDENT_TOL_M,
        RUNWAY_JOIN_NEAR_M, runway_join_contact)
    _CONTACT_M = RUNWAY_CONTACT_M
    _NEAR_M = RUNWAY_JOIN_NEAR_M
    _edge_contact = _os.environ.get("O4_RUNWAY_EDGE_CONTACT", "1") == "1"
    # A runway_crossing is RUNWAY surface (a taxiway crossing ON the runway), not a
    # taxi-spine node — comparing it to a runway's profile is runway-vs-runway (the
    # runway profile's job at an intersection: the crossing sits at a compromise
    # between the two runways), NOT a taxi runway-join.  Exclude it from the
    # taxi-node search so the join is measured to the real spine node (user
    # 2026-06-26: a marginal ~U11/14L-32R join was mis-flagged on the crossing).
    _RUNWAY_SURFACE = (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)

    # ANCHOR TARGET SET — LOCKSTEP with ``grade_graph._runway_anchors``
    # (user 2026-07-16, KBNA 13/31 defect H): the solver anchors joins
    # against runways AND runway-crossing slabs (the slab replaced the
    # runway surface at an intersection), gate O4_RUNWAY_CROSSING_ANCHOR.
    # The validator must resolve each contact against the SAME target set
    # or it samples a t-clamped runway piece where the join actually
    # terminates on the slab (KBNA 31 threshold: a 0.23 m phantom step
    # vs the extrapolated piece while the join sat flush on the slab).
    _crossing_target = _os.environ.get(
        "O4_RUNWAY_CROSSING_ANCHOR", "1") == "1"
    _target_roles = ((ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)
                     if _crossing_target else (ROLE_RUNWAY,))
    runways = [s for s in layout.shapes
               if s.role in _target_roles and s.polygon is not None
               and not s.polygon.is_empty]
    if not any(s.role == ROLE_RUNWAY for s in runways):
        return []
    # emitted taxiway / junction nodes (the spine side of the join).
    nx, ny, ne = [], [], []
    for s in layout.shapes:
        if (s.role in _RUNWAY_SURFACE or s.polygon is None or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        elevs = _shape_elevs(s, len(ring))
        if elevs is None:
            continue
        for (x, y), e in zip(ring, elevs):
            nx.append(x); ny.append(y); ne.append(e)
    if not nx:
        return []

    out = []
    for entry in (getattr(layout, "apt_taxi_centerlines", []) or []):
        ln = entry.line if hasattr(entry, "line") else (entry[0] if isinstance(entry, (tuple, list)) else entry)
        is_svc = (entry.is_service if hasattr(entry, "is_service")
                  else str((entry[1] if isinstance(entry, (tuple, list))
                            and len(entry) > 1 else "") or "").upper().startswith("SVC"))
        if ln is None or ln.is_empty or is_svc:
            continue
        cs = list(ln.coords)
        # Per-segment cap at the ENDPOINT touching the runway (a route may change
        # width along its length; the join cap is the size at the contact end).
        for (ex, ey), _arc in ((cs[0], 0.0), (cs[-1], ln.length)):
            cap = float(taxi_grade_cap_for_letter(
                entry.size_at_arc(_arc) if hasattr(entry, "size_at_arc")
                else (entry.dominant_size() if hasattr(entry, "dominant_size")
                      else None)))
            P = Point(ex, ey)
            rwy = min(runways, key=lambda r: r.polygon.distance(P))
            if rwy.polygon.distance(P) > _CONTACT_M:
                continue
            # Contact at the runway EDGE crossing (shared law), not the interior
            # centerline endpoint — mirrors the solver anchor exactly (lockstep).
            if _edge_contact:
                c = runway_join_contact(ln, (ex, ey), rwy.polygon)
                cx, cy = c if c is not None else (ex, ey)
            else:
                cx, cy = ex, ey
            re = _sample_runway_segment_elev(rwy, cx, cy)
            if re is None:
                continue
            # nearest emitted taxiway/junction node to the contact
            best_d2, best_e = _NEAR_M * _NEAR_M, None
            for k in range(len(nx)):
                d2 = (nx[k] - cx) ** 2 + (ny[k] - cy) ** 2
                if d2 < best_d2:
                    best_d2, best_e = d2, ne[k]
            if best_e is None:
                continue
            d = math.sqrt(best_d2)
            de = abs(re - best_e)
            if d < 1e-6:
                # COINCIDENT pair (user ruling 2026-07-16): the join
                # vertex IS the contact — it must sit AT the crowned
                # runway edge value (``re``, sampled from the emitted —
                # crowned — runway ring).  This class was previously
                # SKIPPED, hiding joins anchored at the centerline
                # profile while the edge crowned 0.24-0.31 m lower
                # (KBNA 13/31).  Reported with the step in the pct slot
                # per metre of tolerance so the worst joins sort first.
                if de > RUNWAY_JOIN_COINCIDENT_TOL_M:
                    out.append((de * 100.0, cap * 100.0, d,
                                "runway_join", True, cx, cy))
                continue
            if de > cap * d + noise:
                out.append(((de / d) * 100.0, cap * 100.0, d, "runway_join",
                            True, cx, cy))
    return out


def route_reach_violations(layout, noise=ELEV_ROUNDING_NOISE_M):
    """Flag a soft airside shape (apron / junction) whose AIRSIDE-ROUTE CONTACTS
    are at mutually UNREACHABLE elevations.

    User model (2026-06-26): a no-building apron must get a single base elevation
    that is within-cap reachable via ALL the taxiways that feed it.  If two of its
    route contacts ``a, b`` (the taxiway/junction shapes that abut it) sit at
    elevations whose difference exceeds ``cap · dist(a, b)`` — where ``cap`` is the
    shape's own body cap and ``dist`` is the straight-line gap between the contacts
    (a LOWER bound on the in-pavement route distance) — then NO cap-compliant
    surface can connect them through the shape, so the shape is forced to a steep,
    partly-unreachable elevation (CYXY apron #85: TX2 690.2 vs TX3 677.0 = 13.2 m
    over 478 m = 2.76 % ≫ the 1 % apron cap).  The fix is upstream — the taxiways
    must converge toward a shared reachable level — so this is reported as a
    ``route_reach`` violation, not a within-shape one.

    Returns ``[(pct, cap_pct, dist, role, is_spine=True, x, y), ...]`` (worst
    first), matching ``within_violations``' tuple shape so callers can merge."""
    from auto_patch.layout import (ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION,
                                   ROLE_RUNWAY)
    from auto_patch.config import (APRON_MAX_GRADE, taxi_grade_cap_for_letter)

    # the route shapes whose contact elevation feeds an apron/junction: the
    # taxi network — corridor faces are ROLE_JUNCTION under the global slice
    # (the rect roles are retired, owner 2026-07-29) — NOT service roads
    # (own datum) and NOT runways (handled by the runway-join check; a runway
    # contact is not a flat-apron constraint, it is the hard anchor itself).
    route_roles = {ROLE_JUNCTION}

    routes = []                 # (shape, elevs)
    for s in layout.shapes:
        if (s.role not in route_roles or s.polygon is None or s.polygon.is_empty
                or str(s.ref or "").upper().startswith("SVC")):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        elevs = _shape_elevs(s, len(ring))
        if elevs is None:
            continue
        routes.append((s, ring, elevs))

    buildings = [t.polygon for t in layout.shapes
                 if t.role == ROLE_BUILDING and t.polygon is not None
                 and not t.polygon.is_empty]

    out = []
    for s in layout.shapes:
        if (s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty):
            continue
        if any(s.polygon.distance(b) < 1.0 for b in buildings):
            continue                          # a building anchors the level
        cap = APRON_MAX_GRADE
        # contacts: the nearest route vertex to this apron, per touching route.
        contacts = []                         # (ref, elev, (x, y))
        for (t, tring, televs) in routes:
            if t is s or s.polygon.distance(t.polygon) > 1.5:
                continue
            best = None
            for (x, y), e in zip(tring, televs):
                d2 = s.polygon.exterior.distance(_pt(x, y))
                if best is None or d2 < best[0]:
                    best = (d2, e, (x, y))
            if best is not None:
                contacts.append((str(t.ref), best[1], best[2]))
        if len(contacts) < 2:
            continue
        worst = None
        for i in range(len(contacts)):
            for j in range(i + 1, len(contacts)):
                (_ra, ea, pa), (_rb, eb, pb) = contacts[i], contacts[j]
                dist = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                if dist < 1e-3:
                    continue
                de = abs(ea - eb)
                if de > cap * dist + noise:
                    g = de / dist
                    if worst is None or g > worst[0]:
                        c = s.polygon.centroid
                        worst = (g, dist, c.x, c.y)
        if worst is not None:
            g, dist, cx, cy = worst
            out.append((g * 100.0, cap * 100.0, dist, "route_reach", True,
                        cx, cy))
    out.sort(reverse=True)
    return out


# ── TILE-seam terrain-matching corridor ─────────────────────────────────────
# THE TILE SEAM, not the STRIP seam (spec seam-continuity-v2 §1 — the v1 round
# died of exactly this conflation).  This is the GRATICULE corridor: where the
# patch is cut by an integer lat/lon tile boundary and must match the
# neighbouring tile's terrain.  The unrelated GRADED-STRIP seam law (tears
# between two ``graded_strip`` shapes, typically kilometres from any graticule
# line) lives in ``auto_patch.strip_seam_law`` — never mix the two
# vocabularies, and never name a new identifier a bare ``seam``.
#
# Mirrors ``tools/check_grade.py``'s ``TILE_SEAM_LL_TOL_DEG`` /
# ``TILE_SEAM_ZONE_M`` (owner ruling 2026-06-20) — the SAME scope the
# retired ``tools/attic/grade_feasibility_audit`` used to exclude tile-seam
# nids from its route-band intervals (atticked by the cycle-7.5 instrument
# sweep; the live reader of that scope is ``check_grade``).
# Duplicated rather than imported because ``tools/``
# is a script directory, not an importable package, and ``src/`` must not
# depend on it (same precedent as ``crown.py``'s ``_XEDGE_SEAM_TOL_M ==
# tile_cut._SEAM_LINE_TOL_M``).  Keep the two copies in sync.
TILE_SEAM_LL_TOL_DEG = 1e-4        # == check_grade.TILE_SEAM_LL_TOL_DEG (~11 m)
TILE_SEAM_ZONE_M = 400.0           # == check_grade.TILE_SEAM_ZONE_M


def _crossed_seam_lines(layout, lat, lon):
    """The integer tile-boundary line(s) a seam pin at ``(lat, lon)`` sits on,
    as ``[(axis, coord_m), ...]`` in this layout's LOCAL METRE frame (``axis``
    is ``"x"`` for an integer-LON line, ``"y"`` for an integer-LAT one).

    ``layout.ll_to_m`` is affine and axis-separable (x depends only on lon, y
    only on lat), so an integer lat/lon line is a constant y / x and the
    corridor test downstream is a plain metre distance in the frame the rest of
    this check already works in.  Line MEMBERSHIP is decided in lat/lon with
    ``TILE_SEAM_LL_TOL_DEG``, exactly as ``check_grade._seam_lines`` does."""
    out = []
    if abs(lat - round(lat)) <= TILE_SEAM_LL_TOL_DEG:
        out.append(("y", layout.ll_to_m(float(round(lat)), lon)[1]))
    if abs(lon - round(lon)) <= TILE_SEAM_LL_TOL_DEG:
        out.append(("x", layout.ll_to_m(lat, float(round(lon)))[0]))
    return out


def _seam_pin_band_slack(layout, band, noise, crown_at):
    """MEASURE how far this layout's AIRSIDE tile-seam pins sit OUTSIDE the
    runway-reach ``band``, per crossed seam LINE.

    Returns ``[(axis, coord_m, d_floor, d_ceil), ...]``: for each integer
    tile-boundary line the airport actually crosses, the largest floor DEFICIT
    (``band_floor(pin) − pin_value``) and the largest ceiling EXCESS
    (``pin_value − band_ceiling(pin)``) over that line's airside pins, each
    clamped at 0.  Empty list when the layout carries no seam pins at all — a
    single-tile airport gets NO allowance and is byte-identical.

    The pins are the solver's own hard anchors (``layout._seam_pin_ll``,
    published by ``solver_primitives``' seam block).  "Airside" is
    ``seam_anchors.SEAM_CLAMP_ROLES`` (the repo's airside seam-pin roles)
    intersected with the roles the route band governs (:func:`_band_roles`): a
    runway / graded-strip / service-network pin is not band-governed, so it can
    never excuse a band-governed vertex.  ``band`` is the SAME
    ``reach_band_unified`` closure this check enforces, so the bound is the
    geodesic cap-Dijkstra band — never a straight-line ``runway_clamp_floor``
    style proxy (a prior review measured that form over-reporting 3-4×).

    A pin whose band is EMPTY (``floor > ceiling``) contributes NOTHING: that
    is the ``pinned`` class — a mutually-unreachable-anchor infeasibility this
    yield does not address — and letting it feed both sides at once would break
    the side-specificity the rule depends on."""
    pins_ll = getattr(layout, "_seam_pin_ll", None) or []
    if not pins_ll:
        return []
    from auto_patch.layout import SHARED_VERTEX_TOL_M
    from auto_patch.seam_anchors import SEAM_CLAMP_ROLES
    airside = frozenset(SEAM_CLAMP_ROLES) & _band_roles()
    # AS-BUILT value of every airside vertex, hashed into SHARED_VERTEX_TOL_M
    # cells so each pin resolves to the elevation actually emitted at it (the
    # pin is a ring vertex of the shapes that own it).  De-crowned into the
    # band's uncrowned space, like the vertices in the main loop.
    cell = float(SHARED_VERTEX_TOL_M)
    vhash: dict = {}
    for s in layout.shapes:
        if (s.role not in airside or s.polygon is None or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        elevs = _shape_elevs(s, len(ring))
        if elevs is None:
            continue
        for (x, y), e in zip(ring, elevs):
            vhash.setdefault((int(x // cell), int(y // cell)), []).append(
                (x, y, float(e) + crown_at(layout, x, y)))
    if not vhash:
        return []
    lines: dict = {}                     # (axis, coord_m) -> [d_floor, d_ceil]
    for (pla, plo) in pins_ll:
        px, py = layout.ll_to_m(pla, plo)
        gx, gy = int(px // cell), int(py // cell)
        best = None
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                for (vx, vy, ve) in vhash.get((gx + ox, gy + oy), ()):
                    d = math.hypot(vx - px, vy - py)
                    if d <= cell and (best is None or d < best[0]):
                        best = (d, ve)
        if best is None:
            continue                     # not an AIRSIDE pin (or not emitted)
        b = band(px, py)
        if b is None:
            continue                     # off the spine network — unbounded
        lo, hi = b
        if lo > hi + noise:
            continue                     # EMPTY band: the ``pinned`` class
        e = best[1]
        d_floor = max(0.0, lo - e)
        d_ceil = max(0.0, e - hi)
        if d_floor <= 0.0 and d_ceil <= 0.0:
            continue                     # a FEASIBLE pin explains nothing
        for line in _crossed_seam_lines(layout, pla, plo):
            slot = lines.setdefault(line, [0.0, 0.0])
            slot[0] = max(slot[0], d_floor)
            slot[1] = max(slot[1], d_ceil)
    return [(axis, coord, df, dc)
            for ((axis, coord), (df, dc)) in lines.items()]


def _seam_contract_yield(layout, viol, band, noise, crown_at):
    """Drop the ``floor`` / ``ceil`` route-band violations the TILE-SEAM TERRAIN
    CONTRACT explains — see the ruling note at the call site in
    :func:`route_band_violations`.  ``pinned`` violations are never yielded.

    Cheap by construction: no violations ⇒ returned unchanged without touching
    the pins; no seam pins ⇒ ``_seam_pin_band_slack`` returns an empty bound and
    the verdicts are bit-for-bit what they were."""
    if not viol:
        return viol
    slack = _seam_pin_band_slack(layout, band, noise, crown_at)
    if not slack:
        return viol
    kept = []
    for t in viol:
        excess, side, x, y = t[0], t[1], t[3], t[4]
        keep = True
        if side in ("floor", "ceil"):
            for (axis, coord, d_floor, d_ceil) in slack:
                # (a) inside THIS line's terrain-matching corridor …
                if abs((x if axis == "x" else y) - coord) > TILE_SEAM_ZONE_M:
                    continue
                # … and (b) no deeper out of band than that line's own pins.
                # SIDE-SPECIFIC: a floor deficit at the pins never excuses a
                # ceiling violation, nor the other way round.
                bound = d_floor if side == "floor" else d_ceil
                if excess <= bound + noise:
                    keep = False
                    break
        if keep:
            kept.append(t)
    return kept


def _band_roles():
    """Airside roles whose vertices must sit inside the runway-reach ROUTE BAND:
    the taxi network + the apron / junction / building surfaces it grades to.
    Runways are the band ANCHORS (excluded); groundside / service / boundary /
    clearance carry their own datum and are not runway-reach constrained."""
    from auto_patch.layout import (
        ROLE_APRON, ROLE_BUILDING, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
        ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB)
    return frozenset({
        ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
        ROLE_CROSS_CONNECTOR, ROLE_APRON, ROLE_JUNCTION, ROLE_BUILDING})


def route_band_violations(layout, noise=ELEV_ROUNDING_NOISE_M, G=None,
                          stats=None):
    """Confirm the runway-reach ROUTE BAND on THE unified grade graph ``G``.

    The solver bounds every airside node by the reach band
    (``building_feasibility.reach_band_unified``: a cap-Dijkstra over
    ``G.spine_adj`` from the runway anchors ``G.runway_anchor``); this is the
    AS-BUILT CONFIRMATION of that rule on the SAME graph ``G`` — one graph, no
    separate route-field.  For every airside taxi / apron / junction / building
    vertex, the emitted elevation must lie inside ``band(x, y) = (floor,
    ceiling)``: above the ceiling means the vertex is higher than the steepest
    cap-compliant climb from any runway can reach; below the floor, lower than
    any descent can reach.

    Vertices off the spine network (``band`` returns ``None`` — a coverage hole
    / weak band) are NOT constrained here; their local within-shape law
    (``within_violations``) still applies.  This is the in-memory home of the
    check (the layout carries the global spine ``G`` reach_band needs); rebuilding
    ``G`` from the shipped OSM is a documented follow-up (handover item 1).

    Three failure modes, all REPORTED (no airport is legitimately infeasible —
    every one is a solver bug, a missing rule, or a rule that needs adjusting, so
    none are silently dropped; the class just tells us which FIX it needs):

      * ``"ceil"`` — elev above the band ceiling (higher than any cap-compliant
        climb from a runway can reach).
      * ``"floor"`` — elev below the band floor (lower than any descent reaches).
      * ``"pinned"`` — the band itself is EMPTY (``floor > ceiling``): no single
        elevation is within-cap reachable from every runway at once.  A
        FUNDAMENTAL multi-anchor infeasibility — whatever the solver emits here
        violates the reach law from some anchor.  ``excess_m`` is the band
        deficit ``floor - ceiling`` (how over-constrained the point is); the
        FIX is upstream (a transition/relaxation rule, a yielded anchor, or a
        geometry bug), tracked alongside ``route_reach_violations``.

    TILE-SEAM YIELD (owner rulings 2026-06-20 / 2026-07-24): inside the seam
    terrain-matching corridor the band yields to the DEM-anchored seam pins by
    exactly the MEASURED amount those pins themselves sit out of band, per
    crossed seam line and per side — see the long note at the yield site below.
    No seam pins ⇒ no allowance ⇒ byte-identical verdicts.

    Vertices off the spine network (``band`` returns ``None`` — a coverage hole
    / weak band) are NOT constrained here; their local within-shape law
    (``within_violations``) still applies.  This is the in-memory home of the
    check (the layout carries the global spine ``G`` reach_band needs); rebuilding
    ``G`` from the shipped OSM is a documented follow-up (handover item 1).

    ``stats`` — an optional dict this fills with the POPULATION the verdict
    is about (cycle-7.5 instrument sweep; RULINGS 2026-08-06 binding points
    1-3).  It is a pure OUT parameter: nothing here reads it, no decision
    depends on it, and with ``stats=None`` (the default) not one branch
    changes.  It exists because "no violations" and "no vertices examined"
    render identically without it — measured live at HEAZ, where the band
    field cannot be built at all, EVERY vertex reads off-net, and the
    membership line still printed "every airside vertex INSIDE its band".
    Keys: ``candidates`` (airside ring vertices reached), ``deduped``
    (welded corners already counted at a shared coordinate), ``off_net``
    (``band`` returned None — NOT constrained here), ``examined``
    (``band`` returned an interval, i.e. the population the verdict is
    about), ``in_band``, ``exempt_small_pad``, ``exempt_runway_datum``,
    ``flagged_before_seam_yield``, ``seam_yielded``, ``noise_m``.

    Returns ``[(excess_m, side, role, x, y, elev, lo, hi), ...]`` worst (largest
    ``excess_m``) first."""
    from .elevation_per_surface.solver_primitives import _build_node_list
    from .elevation_per_surface.building_feasibility import reach_band_unified
    if G is None:
        nodes, b2i = _build_node_list(layout)
        if not nodes:
            return []
        G = GG.build_unified_graph(layout, b2i)
    band = reach_band_unified(layout, G)
    roles = _band_roles()

    # SMALL buildings (grade_law.building_requires_full_frontage == False) are
    # LOCAL reach ANCHORS: ``build_building_seats`` seats such a pad at its
    # central-chord level and the body solve grades the surrounding apron FROM the
    # pad at the apron cap, so those points are reachable from the PAD, not the
    # runway route.  Recognise that here (the SAME reach the solver enforced, one
    # rule via ``building_requires_full_frontage``) so the looser small-building
    # frontage — its non-central pad and the apron stepping up to it — is not
    # falsely flagged.  A LARGE building is NOT an anchor: its whole frontage must
    # be route-reachable, so its pads stay checked per-vertex.
    from auto_patch.grade_law import (
        building_requires_full_frontage, BUILDING_REACH_CORRIDOR_M)
    from auto_patch.layout import ROLE_BUILDING
    from auto_patch.config import APRON_MAX_GRADE, VISIBLE_CHORD_CONNECT
    from .elevation_per_surface.building_feasibility import (
        _pavement_visibility, _VIS_ON_PAV_FRAC)
    small_pads = []                          # (polygon, seat)
    for s in layout.shapes:
        if (s.role == ROLE_BUILDING and s.polygon is not None
                and not s.polygon.is_empty
                and not building_requires_full_frontage(s.polygon.area)):
            ring = _open_ring(list(s.polygon.exterior.coords))
            el = _shape_elevs(s, len(ring))
            if el:
                small_pads.append((s.polygon, sum(el) / len(el)))
    _vis = (_pavement_visibility(layout)
            if (small_pads and VISIBLE_CHORD_CONNECT) else None)

    def _reached_from_small_pad(x, y, e):
        """True when ``(x, y, e)`` sits within the apron cap of a SMALL building's
        seat over an ON-PAVEMENT chord — the surface grades to it from the local
        pad (the looser small-building rule), not the runway route."""
        if not small_pads:
            return False
        from shapely.geometry import Point as _P, LineString as _LS
        from shapely.ops import nearest_points as _np
        p = _P(x, y)
        for (poly, seat) in small_pads:
            d = poly.distance(p)
            if d > BUILDING_REACH_CORRIDOR_M:
                continue
            if abs(e - seat) > APRON_MAX_GRADE * d + noise:
                continue
            if _vis is None:
                return True
            near = _np(poly, p)[0]
            chord = _LS([(x, y), (near.x, near.y)])
            if chord.length < 1e-6 or _vis.contains(chord):
                return True
            try:
                if (chord.intersection(_vis.context).length / chord.length
                        >= _VIS_ON_PAV_FRAC):
                    return True
            except Exception:                                  # pragma: no cover
                pass
        return False

    # SPINE CROWN (part 30): the reach band was solved in UNCROWNED space —
    # de-crown each vertex (e + drop) before the band comparison, or every
    # crowned edge node reads up to its designed drop below the floor.
    _crown_field = getattr(layout, "_crown_drop_key", None) or {}
    if _crown_field:
        from .crown import crown_drop_at as _crown_at
    else:
        def _crown_at(_l, _x, _y):
            return 0.0

    # RUNWAY-DATUM EXEMPTION (2026-07-17): a vertex ON the runway boundary
    # carries the runway surface value — the taxi-join /
    # runway-edge-contact rulings make the runway THE datum there (the
    # solver seeds these nodes HARD from the runway ring:
    # ``seed_rwy_seam``).  The reach band is the intersection of
    # per-anchor reach intervals over the ANCHOR SET (centerline→runway
    # joins), so a contact point ≥1 join-spacing away from any join reads
    # a ceiling BELOW the runway surface itself and flags a value the
    # solver was never allowed to move (measured SPJC 16L/34R: 4 hard
    # ``seed_rwy_seam`` junction vertices + 1 vertex interpolated between
    # them, 0.10-0.38 m out of band).  VALUE-GATED, like
    # ``_reached_from_small_pad``: exempt only a vertex whose de-crowned
    # value grades at cap from a nearby runway ring vertex's de-crowned
    # value — the runway contact is a LOCAL anchor.  A vertex merely NEAR
    # the runway with an off-value elevation stays flagged.  The band
    # governs the network AWAY from the runway; mutual-anchor tension
    # along the runway is the pinned/route-reach checks' domain.
    #
    # THE RADIUS IS THE JOIN/CONTACT LAW'S OWN REACH (cycle-5 instrument-fix
    # spec item 1) — never a magic number.  ``grade_law`` already defines
    # where a runway datum can sit: a taxi centerline endpoint within
    # ``RUNWAY_CONTACT_M`` of the runway polygon IS a contact, and the
    # anchored join node is the nearest EMITTED node within
    # ``RUNWAY_JOIN_NEAR_M`` of that contact (``runway_join_contacts`` /
    # ``grade_graph._runway_anchors``).  So the furthest a node the solver
    # hard-seeds from the runway can lawfully sit from the runway itself is
    # exactly the sum, and that is the scope of "near a runway" here.  The
    # literal 15.0 that stood here was calibrated against nothing and cut
    # the exemption at less than half the law's reach: SPJC's
    # ``floor 0.253 @(1477.84,−493.06)`` sits 19.45 m from a 16L/34R ring
    # vertex and grades to it at 1.24 % — inside TAXI_MAX_GRADE, i.e. the
    # citable per-edge law is satisfied from the runway datum right beside
    # it — and was flagged only because the magic radius missed the runway
    # (spjcverd report F2/F3; CYXY's two rows are the same class at
    # 17.36 m / 26.04 m).  ONE authority for "near a runway".
    from auto_patch.layout import ROLE_RUNWAY as _R_RWY
    from auto_patch.layout import ROLE_RUNWAY_CROSSING as _R_RWX
    from auto_patch.config import TAXI_MAX_GRADE as _RWD_CAP
    from auto_patch.grade_law import (RUNWAY_CONTACT_M as _RWD_CONTACT_M,
                                      RUNWAY_JOIN_NEAR_M as _RWD_JOIN_NEAR_M)
    _RWD_RADIUS_M = _RWD_CONTACT_M + _RWD_JOIN_NEAR_M
    _rwy_datum_pts: list = []
    _rwy_datum_vals: list = []
    for _s in layout.shapes:
        if (_s.role not in (_R_RWY, _R_RWX) or _s.polygon is None
                or _s.polygon.is_empty):
            continue
        _ring = _open_ring(list(_s.polygon.exterior.coords))
        _els = _shape_elevs(_s, len(_ring))
        if _els is None:
            continue
        for (_rx, _ry), _re in zip(_ring, _els):
            if _re is None:
                continue
            _rwy_datum_pts.append((_rx, _ry))
            _rwy_datum_vals.append(
                float(_re) + _crown_at(layout, _rx, _ry))
    _rwy_tree = None
    if _rwy_datum_pts:
        from shapely.strtree import STRtree as _RwyTree
        from shapely.geometry import Point as _RwyPt
        _rwy_tree = _RwyTree([_RwyPt(px, py)
                              for (px, py) in _rwy_datum_pts])

    def _grades_from_runway_datum(x, y, e):
        if _rwy_tree is None:
            return False
        from shapely.geometry import Point as _RwyPt2
        try:
            hits = _rwy_tree.query_nearest(
                _RwyPt2(x, y), max_distance=_RWD_RADIUS_M, all_matches=False)
        except Exception:                                  # pragma: no cover
            return False
        for _hi in hits:
            _px, _py = _rwy_datum_pts[int(_hi)]
            _d = math.hypot(_px - x, _py - y)
            if abs(e - _rwy_datum_vals[int(_hi)]) \
                    <= _RWD_CAP * _d + noise:
                return True
        return False

    out = []
    seen = set()
    # POPULATION COUNTERS — write-only (see the ``stats`` note in the
    # docstring).  Kept in locals and published once at the end so the
    # per-vertex loop is unchanged in cost when nobody asked for them.
    _n_candidates = _n_dedupe = _n_offnet = _n_examined = 0
    _n_in_band = _n_small_pad = _n_rwy_datum = 0
    for s in layout.shapes:
        if (s.role not in roles or s.polygon is None or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        elevs = _shape_elevs(s, len(ring))
        if elevs is None:
            continue
        for (x, y), e in zip(ring, elevs):
            e = e + _crown_at(layout, x, y)
            _n_candidates += 1
            # dedupe by shared canonical node — the band is positional, so a
            # welded corner shared by N shapes is ONE band check, not N.
            key = (round(x, 2), round(y, 2))
            if key in seen:
                _n_dedupe += 1
                continue
            seen.add(key)
            b = band(x, y)
            if b is None:
                # OFF-NET: this vertex is NOT constrained here, and it is
                # NOT evidence of compliance.  Counted so the report can
                # say how large the examined population actually was.
                _n_offnet += 1
                continue
            _n_examined += 1
            lo, hi = b
            # within a feasible runway-reach band → fine.
            if lo <= hi + noise and (lo - noise) <= e <= (hi + noise):
                _n_in_band += 1
                continue
            # else reachable from a local SMALL-building pad → fine (the apron
            # grades from the pad at the apron cap; the small-building rule).
            if _reached_from_small_pad(x, y, e):
                _n_small_pad += 1
                continue
            # runway-datum reach (see the exemption note above): the
            # vertex grades at cap from a local runway contact — the
            # runway is the datum there, never band-judged.
            if _grades_from_runway_datum(x, y, e):
                _n_rwy_datum += 1
                continue
            if lo > hi + noise:
                # EMPTY band — no compliant elevation exists at this vertex
                # (mutually-unreachable runway anchors).  Reported, never
                # dropped: it is a fundamental infeasibility to root-cause.
                out.append((lo - hi, "pinned", s.role, x, y, e, lo, hi))
            elif e > hi + noise:
                out.append((e - hi, "ceil", s.role, x, y, e, lo, hi))
            else:  # e < lo - noise
                out.append((lo - e, "floor", s.role, x, y, e, lo, hi))
    # ── TILE-SEAM TERRAIN CONTRACT — the route band YIELDS here (owner
    #    rulings 2026-06-20 and 2026-07-24) ────────────────────────────────
    # 2026-06-20 (the seam terrain-matching zone, ``tools/check_grade.py``
    # ``TILE_SEAM_ZONE_M``): where pavement crosses a tile boundary it must MATCH
    # the neighbour tile's terrain mesh — so it follows the DEM inward from the
    # seam instead of the designed surface — and the ruling names BOTH the
    # within-shape cap and the runway-anchored route-band law as yielding inside
    # that zone.  2026-07-24 (``config.SEAM_PIN_RUNWAY_CLAMP`` now OFF, commit
    # 1d5e6dd): an AIRSIDE cut-back seam pin takes the RAW DEM, full stop — no
    # clamp back toward the runway — because a clamped pin floats above the
    # terrain the neighbouring strip renders (the SPLP gutter).
    #
    # Consequence this yield exists for: where a CIFP-profiled runway
    # legitimately sits above the local smoothed DEM at a seam-crossing end, the
    # DEM-anchored pin sits BELOW the runway-anchored reach band, and the solver
    # correctly grades the pin's neighbours down toward that hard anchor.  Those
    # neighbours then read as "below the floor" of a band that never knew about
    # the terrain contract.
    #
    # WHY THE BAND YIELDS AND THE PER-EDGE GRADE CAP DOES NOT.  The 1.5 % taxi
    # cap is a CITABLE aerodrome standard (docs/STANDARDS.md → ``config.py``
    # ``ROLE_GRADE_LIMITS``; enforced by ``within_violations`` and
    # ``tools/check_grade.py``) — it describes a real aircraft on a real slope —
    # and it still binds every pair here: the ramp from the seam pin up to the
    # network must be GRADED, not stepped (that is exactly why
    # ``grade_law.classify_pair`` keeps a one-seam-endpoint pair in the law).
    # The route band is NOT in docs/STANDARDS.md; it is a DERIVED transitive
    # self-consistency device (docs/route_field_model.md) asking "is this value
    # reachable at cap from a runway", built from ONE anchor class — the
    # runways.  A seam pin is a SECOND, owner-recognised anchor class the band's
    # construction simply omits, so at a seam it is the BAND that is incomplete,
    # not the surface.  Every other reader already yields to that class:
    # ``check_grade`` (the 2026-06-20 zone) and ``grade_law.classify_pair``
    # (both-pinned pairs SKIP); so did the now-retired
    # ``tools/attic/grade_feasibility_audit`` (seam nids excluded from its
    # route-band intervals and treated as HARD anchors).  This
    # in-memory frame is the one that had no such yield; this is it catching up.
    #
    # The allowance is a MEASURED PHYSICAL QUANTITY, never a constant: per
    # crossed seam LINE it is exactly how far that line's own airside pins sit
    # outside the SAME geodesic band (``_seam_pin_band_slack``).  It is
    # identically zero with no seam pins and zero once the pins are feasible, it
    # is SIDE-SPECIFIC, and it is the ONLY allowance this check grants: the
    # ``RASTER_REACH_BAND_GRID_RESIDUAL_M`` excuse it used to share the stage
    # with was DELETED (cycle-5 instrument-fix item 2 — its grid-error
    # mechanism was falsified under a cell sweep).  A vertex further out of
    # band than the seam contract can explain STILL flags.
    _n_flagged = len(out)
    out = _seam_contract_yield(layout, out, band, noise, _crown_at)
    out.sort(reverse=True, key=lambda t: t[0])
    if stats is not None:
        stats.update({
            "candidates": _n_candidates,
            "deduped": _n_dedupe,
            "off_net": _n_offnet,
            "examined": _n_examined,
            "in_band": _n_in_band,
            "exempt_small_pad": _n_small_pad,
            "exempt_runway_datum": _n_rwy_datum,
            "flagged_before_seam_yield": _n_flagged,
            "seam_yielded": _n_flagged - len(out),
            "noise_m": float(noise),
        })
    return out


#: Materiality floor for the band-EXCESS report (the convergence guards'
#: elevation floor, the same 0.01 m ``FINAL_BAND_INVERSION_TOL_M`` uses).
FINAL_BAND_EXCESS_MATERIALITY_M = 0.01


def final_band_excess_report(layout, icao="",
                             tol=FINAL_BAND_EXCESS_MATERIALITY_M, G=None):
    """REPORT — never a gate — on final band MEMBERSHIP (cycle-5
    instrument-fix spec item 7).

    THE HOLE THIS FILLS.  The build's post-solve band law is INVERSION-ONLY:
    ``building_feasibility.assert_no_final_band_inversion`` fails a build on
    ``floor > ceiling`` and says nothing about a value that simply sits
    OUTSIDE its band.  So a patch could log
    ``final reach band — 2 sub-materiality inversion(s) (≤ 0.01 m),
    PASS-with-residual`` and ship with 0.3 m of ceiling excess on a junction
    complex, invisible until somebody ran pytest (measured at SPJC; the
    author is ``final_grade_projection``).  A defect the build itself cannot
    see is a defect nobody is accountable for.

    IT IS A REPORT, DELIBERATELY.  Band membership is a derived
    self-consistency device, not a citable aerodrome standard, and the owner's
    law is that instruments REPORT while the law ADJUDICATES — the census and
    ``tests/test_route_band.py`` are where the verdict lives.  Making this a
    build error would also gate every build on a population the solve round
    is still landing.  So: it logs, it lands in the sidecar as EVIDENCE, and
    it never raises.

    ONE AUTHORITY.  The rows come from :func:`route_band_violations` — the
    same checker the suite runs, on the same graph, with the same exemptions
    (runway datum, small pads, tile-seam yield).  Nothing is re-derived.

    THE POPULATION IS PART OF THE REPORT (cycle-7.5 instrument sweep,
    RULINGS 2026-08-06 binding points 1-3).  ``material`` on its own cannot
    distinguish "nothing is out of band" from "nothing was examined": at
    HEAZ the band field cannot be built at all, so every vertex reads
    off-net and this report rendered a clean universal pass over a
    population of ZERO.  ``examined`` / ``off_net`` / the two exemption
    counts come straight out of the checker's own ``stats`` out-dict — a
    count, not a second opinion.

    TWO FLOORS GOVERN, and both are stamped.  ``materiality_m`` (0.01 m,
    the convergence guards') is the one this report quotes; the checker's
    own ``ELEV_ROUNDING_NOISE_M`` (0.03 m) is the one that actually decides
    which vertices become rows.  The larger wins, so with the shipped
    constants ``sub_materiality`` is STRUCTURALLY ZERO — no row the checker
    can return lands under 0.01 m.  ``sub_materiality_structurally_zero``
    carries that fact to every consumer rather than leaving each to
    rediscover it (``tests/test_route_band.py`` proves the inequality).

    Returns the summary dict (also stashed on ``layout._final_band_excess``
    for the sidecar), or ``None`` when the check could not run.
    """
    stats: dict = {}
    try:
        rows = route_band_violations(layout, G=G, stats=stats)
    except Exception as exc:                                   # pragma: no cover
        summary = {"error": f"{type(exc).__name__}: {exc}",
                   "materiality_m": float(tol),
                   "noise_floor_m": float(ELEV_ROUNDING_NOISE_M),
                   "frame": _band_frame(layout)}
        try:
            layout._final_band_excess = summary
        except AttributeError:
            pass
        return summary
    over = [t for t in rows if t[0] > tol]
    by_side: dict = {"ceil": 0, "floor": 0, "pinned": 0}
    by_role: dict = {}
    for t in over:
        by_side[t[1]] = by_side.get(t[1], 0) + 1
        by_role[t[2]] = by_role.get(t[2], 0) + 1
    summary = {
        "icao": str(icao or ""),
        "materiality_m": float(tol),
        # The floor that actually governs which vertices become rows.
        "noise_floor_m": float(ELEV_ROUNDING_NOISE_M),
        "sub_materiality_structurally_zero": bool(
            ELEV_ROUNDING_NOISE_M > tol),
        "rows": len(rows),
        "material": len(over),
        "sub_materiality": len(rows) - len(over),
        # THE POPULATION the verdict is about, from the checker itself.
        "examined": int(stats.get("examined", 0) or 0),
        "off_net": int(stats.get("off_net", 0) or 0),
        "candidates": int(stats.get("candidates", 0) or 0),
        "deduped": int(stats.get("deduped", 0) or 0),
        "in_band": int(stats.get("in_band", 0) or 0),
        "exempt_small_pad": int(stats.get("exempt_small_pad", 0) or 0),
        "exempt_runway_datum": int(stats.get("exempt_runway_datum", 0) or 0),
        "seam_yielded": int(stats.get("seam_yielded", 0) or 0),
        "frame": _band_frame(layout),
        "by_side": by_side,
        "by_role": dict(sorted(by_role.items(), key=lambda kv: -kv[1])),
        "worst_m": (round(float(over[0][0]), 4) if over else 0.0),
        "worst": [{"excess_m": round(float(t[0]), 4), "side": t[1],
                   "role": t[2], "x": round(float(t[3]), 2),
                   "y": round(float(t[4]), 2), "elev": round(float(t[5]), 3),
                   "lo": round(float(t[6]), 3), "hi": round(float(t[7]), 3)}
                  for t in over[:10]],
    }
    try:
        layout._final_band_excess = summary
    except AttributeError:                                     # pragma: no cover
        pass
    return summary


def _band_frame(layout) -> str:
    """The frame stamp for the band-membership numbers (binding point 3).

    ONE stamp, borrowed from ``building_feasibility`` rather than spelled a
    second time here — two spellings of one frame is the two-instruments
    trap by construction.  The node space is POSITIONAL: this checker
    dedupes by rounded ``(x, y)`` and never touches a solver node id."""
    try:
        from .elevation_per_surface.building_feasibility import (
            instrument_frame)
        return instrument_frame(
            layout,
            node_space=("positional (x,y) rounded to 0.01 m in "
                        "layout-local metres — NOT solver node ids"),
        )
    except Exception:                                          # pragma: no cover
        return "[frame unavailable]"


def format_final_band_excess(summary, icao="") -> str:
    """The one-line (plus worst-rows) build-log rendering of
    :func:`final_band_excess_report`.  Formatting lives with the report so the
    log line and the sidecar can never describe different numbers."""
    if not summary:
        return f"  [pav-builder] {icao}: final band excess — NOT EVALUATED."
    if summary.get("error"):
        return (f"  [pav-builder] {icao}: final band EXCESS report failed "
                f"({summary['error']}) — membership NOT measured this build.")
    # THE POPULATION LINE — printed in every case, because the counts are
    # what tell a "0 material" line apart from a line about nothing.
    _pop = (f"examined {summary.get('examined', 0)} of "
            f"{summary.get('candidates', 0)} airside ring vertex(es) "
            f"[{summary.get('deduped', 0)} welded duplicate(s), "
            f"{summary.get('off_net', 0)} off-net (band None — NOT "
            f"constrained here)]; exempt: "
            f"{summary.get('exempt_small_pad', 0)} small-pad reach, "
            f"{summary.get('exempt_runway_datum', 0)} runway datum, "
            f"{summary.get('seam_yielded', 0)} tile-seam yield")
    # BOTH FLOORS (binding point 3): the one quoted, and the one that
    # actually decides which vertices become rows.
    _floors = (f"floors: materiality {summary.get('materiality_m', 0):g} m, "
               f"checker rounding noise "
               f"{summary.get('noise_floor_m', 0):g} m")
    _sub = (f"{summary.get('sub_materiality', 0)} sub-materiality row(s)"
            + (" — STRUCTURALLY ZERO at these constants: the checker's "
               "rounding noise already exceeds the materiality floor, so no "
               "row it returns can land under it (this number is not "
               "evidence about the surface)"
               if summary.get("sub_materiality_structurally_zero") else ""))
    _frame = summary.get("frame") or ""
    if not summary.get("examined", 0):
        # ZERO-OF-ZERO IS NOT A PASS.  Measured live at HEAZ: the band
        # field could not be built, every query read off-net, and this
        # branch used to print "every airside vertex INSIDE its band"
        # immediately under the ``[reach-band] NO FIELD`` line.
        return (f"  [pav-builder] {icao}: final reach band — NOT MEASURED: "
                f"ZERO vertices were examined ({_pop}).  Band membership is "
                f"unknown for this build; a zero violation count here is "
                f"the size of the population, not a property of the "
                f"surface.  {_floors}.  {_frame}")
    if not summary["material"]:
        return (f"  [pav-builder] {icao}: final reach band — 0 of "
                f"{summary['examined']} EXAMINED vertex(es) outside their "
                f"band by > {summary['materiality_m']:g} m "
                f"({summary.get('in_band', 0)} inside).  {_pop}.  "
                f"{_sub}.  {_floors}.  {_frame}")
    s = summary["by_side"]
    lines = [
        f"  [pav-builder] {icao}: final reach band — {summary['material']} "
        f"of {summary['examined']} EXAMINED vertex(es) OUTSIDE their band "
        f"by > {summary['materiality_m']:g} m (ceil={s.get('ceil', 0)}, "
        f"floor={s.get('floor', 0)}, pinned={s.get('pinned', 0)}; worst "
        f"{summary['worst_m']:.4f} m).  REPORT, not a gate — the census and "
        f"tests/test_route_band.py adjudicate.",
        f"      {_pop}.  {_sub}.  {_floors}.",
        f"      {_frame}",
    ]
    for r in summary["worst"][:5]:
        lines.append(
            f"      {r['side']} {r['excess_m']:.4f} m {r['role']}"
            f"@({r['x']:.0f},{r['y']:.0f}) elev {r['elev']:.3f} vs band "
            f"[{r['lo']:.3f}, {r['hi']:.3f}]")
    return "\n".join(lines)


def _pt(x, y):
    from shapely.geometry import Point
    return Point(x, y)
