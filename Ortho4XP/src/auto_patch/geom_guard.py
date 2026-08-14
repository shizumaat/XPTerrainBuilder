"""Pre-solve geometry guard (dev instrumentation).

Enforces the invariant of the pre-solve-geometry refactor
(``docs/presolve_geometry_refactor.md``): every geometry change to a
**solver-graded (airside)** shape must happen BEFORE ``per_surface_solve``.
After the solve, only *altitude* is assigned (to non-graded terrain
features) and new *non-airside* shapes are added (clearance).  No airside
vertex may be moved, inserted, welded, snapped, or clipped post-solve.

Usage (env-gated, no behaviour change):

    from .geom_guard import snapshot_airside_geometry, report_post_solve_changes
    snap = snapshot_airside_geometry(layout)        # right before the solve
    ...                                             # solve + post-solve passes
    report_post_solve_changes(layout, snap, icao)   # at emit

The guard is active only when ``O4_GEOM_GUARD=1``.  ``snapshot_airside_geometry``
returns ``None`` (and stamps nothing) when disabled, and
``report_post_solve_changes`` is then a no-op.

Identity tracking: each airside shape is stamped with a unique token at
snapshot time.  Passes that mutate ``shape.polygon`` in place keep the
token (so we compare ring hashes); passes that REPLACE shapes with fresh
``BuiltShape`` objects, drop shapes, or reclassify them out of airside lose
the token — all of which are reported as post-solve geometry changes.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import O4_UI_Utils as UI

from .layout import (
    ROLE_APRON,
    ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_STUB,
    ROLE_BUILDING,
)

if TYPE_CHECKING:
    from .layout import BuiltShape, PavementLayout


# Roles the per-surface solver grades — the only shapes whose geometry must
# be final before the solve.  Matches the refactor doc's invariant list.
_AIRSIDE_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_SERVICE_JUNCTION,
    ROLE_APRON, ROLE_BUILDING,
})

# Round ring coords to this many metres when hashing, so float jitter from
# re-projecting identical geometry does not register as a change while a
# genuine weld/snap (≥ 1 mm) or vertex insert does.
_HASH_ROUND_M = 3

# UNCONDITIONAL 2026-08-05 (``O4_GEOM_GUARD`` deleted).  RULINGS
# "BUILD-COMPLETE-THEN-DEBUG" keeps "certify-or-fail-loud in the solve",
# and the airside post-solve invariant this guard reports is the metric the
# campaign drives to zero — a verification either runs always or does not
# exist.
_ENABLED = True


def _canonical_ring(coords) -> tuple:
    """Rotation- and reflection-invariant canonical form of a ring's rounded
    vertices.  A ring's VERTEX SET + cyclic adjacency is the geometry; the
    starting vertex and winding direction are not — the solver / emit may
    rotate a rect's ring (e.g. to the [high, low, low, high] convention) when
    it assigns altitudes, which is NOT a geometry change.  Canonicalising by
    the lexicographically smallest rotation (over both directions) makes the
    guard immune to that re-ordering while still detecting a real insert /
    move / drop (which changes the vertex set or count)."""
    pts = [(round(x, _HASH_ROUND_M), round(y, _HASH_ROUND_M)) for x, y in coords]
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n == 0:
        return ()
    best = None
    for seq in (pts, pts[::-1]):
        for i in range(n):
            rot = tuple(seq[i:] + seq[:i])
            if best is None or rot < best:
                best = rot
    return best


def _ring_hash(shape: BuiltShape) -> int:
    """Hash of a shape's 2-D ring geometry (exterior + holes), ignoring
    altitude AND ring start/winding (see :func:`_canonical_ring`).  Vertex
    count, set, and cyclic adjacency all contribute."""
    poly = shape.polygon
    if poly is None or poly.is_empty:
        return 0
    parts: list = []
    geoms = poly.geoms if poly.geom_type == "MultiPolygon" else (poly,)
    for g in geoms:
        rings = [g.exterior] + list(g.interiors)
        for ring in rings:
            parts.append(_canonical_ring(ring.coords))
        parts.append(None)  # geom separator
    return hash(tuple(parts))


def snapshot_airside_geometry(layout: PavementLayout) -> dict | None:
    """Stamp every airside shape with a unique token and record its ring
    hash.  Returns the ``{token: (role, ring_hash)}`` snapshot, or ``None``
    when the guard is disabled."""
    if not _ENABLED:
        return None
    snap: dict[int, tuple[str, int]] = {}
    for i, s in enumerate(layout.shapes):
        if s.role not in _AIRSIDE_ROLES:
            continue
        token = i
        s._geom_guard_token = token  # type: ignore[attr-defined]
        snap[token] = (s.role, _ring_hash(s))
    UI.vprint(1,
        f"  [geom-guard] snapshot: {len(snap)} airside shape(s) "
        f"recorded pre-solve.")
    return snap


def report_post_solve_changes(layout: PavementLayout, snapshot: dict | None,
                              icao: str) -> int:
    """Compare current airside geometry against the pre-solve snapshot and
    log how many airside shapes changed geometry post-solve (the metric the
    refactor drives to 0).  Returns that count.  No-op when disabled."""
    if not _ENABLED or snapshot is None:
        return 0

    seen: set[int] = set()
    changed_hash = 0           # same object, ring geometry mutated in place
    new_airside = 0            # airside shape created/replaced post-solve
    changed_by_role: dict[str, int] = {}

    def _bump(role: str) -> None:
        changed_by_role[role] = changed_by_role.get(role, 0) + 1

    for s in layout.shapes:
        if s.role not in _AIRSIDE_ROLES:
            continue
        token = getattr(s, "_geom_guard_token", None)
        if token is None or token not in snapshot:
            new_airside += 1
            _bump(f"{s.role}(new)")
            continue
        seen.add(token)
        old_role, old_hash = snapshot[token]
        if _ring_hash(s) != old_hash:
            changed_hash += 1
            _bump(s.role)

    # Tokens in the snapshot no longer present as airside shapes: dropped or
    # reclassified out of airside (a geometry/role change either way).
    removed = 0
    for token, (old_role, _h) in snapshot.items():
        if token not in seen:
            removed += 1
            _bump(f"{old_role}(removed)")

    total = changed_hash + new_airside + removed
    if total:
        detail = ", ".join(
            f"{role}:{n}" for role, n in sorted(changed_by_role.items()))
        UI.vprint(1,
            f"  [geom-guard] {icao}: {total} airside shape(s) changed "
            f"geometry POST-SOLVE "
            f"(mutated={changed_hash}, new={new_airside}, removed={removed}) "
            f"[{detail}]")
    else:
        UI.vprint(1,
            f"  [geom-guard] {icao}: 0 airside shapes changed geometry "
            f"post-solve — invariant HOLDS.")
    return total


# ── THE GEOMETRY SEAM AUDIT (S1e phase 1) ────────────────────────────
#
# ``report_post_solve_changes`` gives the SIZE of the post-solve airside
# mutation (HECA: 914 shapes, mutated 897 / new 9 / removed 8) but not its
# AUTHOR: its window spans every stage between the pre-solve snapshot and
# the report.  This audit splits that window at the seams the pipeline
# ALREADY marks (``pipeline._rod_ckpt``) — the same seam list the rod-carry
# and mutation-seam audits hang off, no invented seam — and answers the two
# questions the double-projection retirement turns on:
#
#   1. WHICH STAGE mutated airside geometry, and of what KIND (pure vertex
#      INSERT / pure DROP / MOVE / new shape / removed shape).
#   2. Did that stage CARRY the solved values through the mutation?  For a
#      pure insert the law is interpolation along the edge the vertex
#      landed on, so the audit checks each inserted vertex against the lerp
#      of its bracketing survivors and reports LERP-exact / near / OFF /
#      valueless.  For every surviving vertex it reports whether its value
#      moved.  A stage whose inserts are all lerp-exact and whose survivors
#      never move is VALUE-PRESERVING and needs no re-projection.
#
# REPORT-ONLY and GATED (``O4_GEOM_SEAM_AUDIT=1``): with the gate off the
# checkpoint is one environment read and a return, so a default build is
# byte-identical.
#
_SEAM_ENV = "O4_GEOM_SEAM_AUDIT"

#: Optional path the armed audit dumps its whole seam ledger to as JSON
#: (S1f).  Same data the report prints, without the top-5 truncation, so a
#: per-SITE "which stage moved this vertex" join is possible; unset ⇒ one
#: dict lookup at report time and no file.
_SEAM_JSON_ENV = "O4_GEOM_SEAM_AUDIT_JSON"

#: Roles this guard calls airside that the SOLVE partitions as groundside
#: (``layout.GROUNDSIDE_ROLES``, the projection's receiver set).  Their
#: post-solve value authorship is stage-B law seating, not a failed carry.
_GROUNDSIDE_SIDE_ROLES = frozenset({ROLE_SERVICE_JUNCTION})

#: A value move under this is float noise, not a re-authoring.
SEAM_EXACT_M = 1e-6
#: The round's standing materiality floor for elevation classes.
SEAM_MATERIAL_M = 0.01


def seam_audit_enabled() -> bool:
    """True when the geometry seam audit is armed."""
    return os.environ.get(_SEAM_ENV) == "1"


def _shape_state(shape) -> tuple | None:
    """``(ring, alts)`` for one shape's exterior, or ``None``.

    ``ring`` is the OPEN ring of vertices rounded to ``_HASH_ROUND_M``;
    ``alts`` the matching per-vertex altitudes (``None`` where the shape
    carries no per-vertex value).
    """
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return None
    g = poly.geoms[0] if poly.geom_type == "MultiPolygon" else poly
    try:
        coords = list(g.exterior.coords)
    except Exception:                                      # pragma: no cover
        return None
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    ring = tuple((round(float(x), _HASH_ROUND_M), round(float(y), _HASH_ROUND_M))
                 for x, y in coords)
    na = getattr(shape, "node_altitudes", None)
    alts: tuple
    if na is not None and len(na) >= len(ring):
        alts = tuple(
            (float(v) if v is not None else None) for v in list(na)[:len(ring)])
    else:
        alts = tuple(None for _ in ring)
    return (ring, alts)


def _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts,
                            shared_at=None, self_key=None) -> dict:
    """Value verdict for the vertices a PURE INSERT added.

    TWO LAWFUL CARRIES, because the round's own text names two (RULINGS
    2026-08-14: "a cut vertex interpolates along its edge, a weld adopts
    the precedence winner's value"):

      * INTERPOLATION — the altitude equals the linear interpolation of
        the two SURVIVING vertices bracketing it on the current ring, at
        its own parameter along that chord.  This is the cut / densify /
        planarize-crossing law.  Bracketing survivors are read at their
        CURRENT values, so a stage that moved a survivor is judged against
        what it actually left behind (that move is counted separately).
      * WELD ADOPTION — the altitude equals the value ANOTHER shape
        already carries at that exact coordinate.  A T-vertex weld exists
        precisely to make two shapes share a node, and a shared node has
        ONE value; scoring that against the host edge's lerp would demand
        the weld re-tear the seam it was run to close.

    An insert that is neither is genuinely un-carried — a value only a
    projection can justify.
    """
    prev_at = dict(zip(prev_ring, prev_alts))
    out = {"inserted": 0, "lerp_exact": 0, "lerp_near": 0, "weld_adopt": 0,
           "off_lerp": 0, "no_value": 0, "worst_m": 0.0, "sites": []}
    n = len(cur_ring)

    def _welded(pt, a) -> bool:
        """True when another shape already carries ``a`` at ``pt``."""
        if shared_at is None:
            return False
        for k, v in (shared_at.get(pt) or {}).items():
            if k != self_key and v is not None and abs(v - a) <= SEAM_EXACT_M:
                return True
        return False

    for i, pt in enumerate(cur_ring):
        if pt in prev_at:
            continue
        out["inserted"] += 1
        a = cur_alts[i]
        if a is None:
            out["no_value"] += 1
            continue
        # Nearest surviving vertex each way around the current ring.
        lo = hi = None
        for k in range(1, n):
            j = (i - k) % n
            if cur_ring[j] in prev_at:
                lo = j
                break
        for k in range(1, n):
            j = (i + k) % n
            if cur_ring[j] in prev_at:
                hi = j
                break
        if lo is None or hi is None or lo == hi:
            if _welded(pt, a):
                out["weld_adopt"] += 1
            else:
                out["no_value"] += 1
            continue
        ax, ay = cur_ring[lo]
        bx, by = cur_ring[hi]
        za, zb = cur_alts[lo], cur_alts[hi]
        if za is None or zb is None:
            if _welded(pt, a):
                out["weld_adopt"] += 1
            else:
                out["no_value"] += 1
            continue
        ex, ey = bx - ax, by - ay
        L2 = ex * ex + ey * ey
        t = 0.5 if L2 <= 0.0 else (
            ((pt[0] - ax) * ex + (pt[1] - ay) * ey) / L2)
        t = min(1.0, max(0.0, t))
        d = abs(a - (za + t * (zb - za)))
        if d <= SEAM_EXACT_M:
            out["lerp_exact"] += 1
        elif _welded(pt, a):
            # The WELD law wins over the lerp law wherever both could
            # apply: the vertex is shared, and a shared node has one value.
            out["weld_adopt"] += 1
            continue
        elif d <= SEAM_MATERIAL_M:
            out["lerp_near"] += 1
        else:
            out["off_lerp"] += 1
            out["sites"].append((round(d, 4), pt[0], pt[1],
                                 round(a, 3),
                                 round(za + t * (zb - za), 3)))
        out["worst_m"] = max(out["worst_m"], d)
    return out


def seam_checkpoint(layout, name: str) -> None:
    """Diff AIRSIDE plan geometry + values against the previous seam.

    Called from ``pipeline._rod_ckpt`` at every named post-solve seam.
    Gate off ⇒ one env read.  Never raises: an audit that can fail a build
    is a worse instrument than no audit.
    """
    if not seam_audit_enabled():
        return
    # THE BASELINE IS THE SOLVE'S EXIT.  Seams before ``00_post_solve``
    # (the pre-solve fabric thinning) are not post-solve stages, and
    # diffing across the solve itself would book the solve's own work as a
    # value move — the thing this audit exists NOT to confuse.
    if getattr(layout, "_geom_seam_prev", None) is None and \
            name != "00_post_solve":
        return
    try:
        cur: dict = {}
        # EVERY shape's values by coordinate — the weld law's evidence.
        # Built over the WHOLE layout, not the audited population: a
        # pavement vertex is routinely welded to a feature (ribbon,
        # bridge, strip), and that is still one shared node with one value.
        shared_at: dict = {}
        for i, s in enumerate(layout.shapes):
            st = _shape_state(s)
            if st is None:
                continue
            token = getattr(s, "_geom_guard_token", None)
            key = token if token is not None else f"post#{i}"
            for pt, a in zip(st[0], st[1]):
                shared_at.setdefault(pt, {})[key] = a
            if s.role not in _AIRSIDE_ROLES:
                continue
            cur[key] = (s.role, st[0], st[1])
        prev = getattr(layout, "_geom_seam_prev", None)
        log = list(getattr(layout, "_geom_seam_log", None) or [])
        if prev is None:
            layout._geom_seam_prev = cur
            layout._geom_seam_log = log
            UI.vprint(1, f"  [geom-seam] {name}: BASELINE — {len(cur)} "
                         f"airside shape(s), "
                         f"{sum(len(v[1]) for v in cur.values())} vertex(es).")
            return

        rec = {"seam": name, "shapes": len(cur), "changed": 0,
               "pure_insert": 0, "pure_drop": 0, "moved": 0,
               "new_shape": 0, "removed_shape": 0,
               "survivors": 0, "survivor_moved": 0,
               "survivor_moved_material": 0, "survivor_worst_m": 0.0,
               "inserted": 0, "lerp_exact": 0, "lerp_near": 0,
               "weld_adopt": 0,
               "off_lerp": 0, "no_value": 0, "insert_worst_m": 0.0,
               "dropped_verts": 0,
               # SOLVE-PARTITION SIDE.  ``_AIRSIDE_ROLES`` here is the
               # pre-solve guard's population and is BROADER than the
               # solve's airside partition: ``service_junction`` is in
               # ``layout.GROUNDSIDE_ROLES`` (a projection RECEIVER, stage
               # B).  Booking a stage-B seating as an airside carry failure
               # is the two-instruments/one-population trap, so the side is
               # split at the source.
               "gs_survivor_moved": 0,
               # Worst offending SITES, so the stage map names a place a
               # human can look at, not just a count (attribution-first).
               "mv_sites": [], "ins_sites": []}
        def _carry(pt, role, a, b) -> None:
            """Book one surviving vertex's value carry (``b`` -> ``a``)."""
            if a is None or b is None:
                return
            rec["survivors"] += 1
            d = abs(a - b)
            if d <= SEAM_EXACT_M:
                return
            rec["survivor_moved"] += 1
            if role in _GROUNDSIDE_SIDE_ROLES:
                rec["gs_survivor_moved"] += 1
            if d > SEAM_MATERIAL_M:
                rec["survivor_moved_material"] += 1
            rec["survivor_worst_m"] = max(rec["survivor_worst_m"], d)
            rec["mv_sites"].append(
                (round(d, 4), pt[0], pt[1], role, round(b, 3), round(a, 3)))

        for key, (role, ring, alts) in cur.items():
            old = prev.get(key)
            if old is None:
                rec["new_shape"] += 1
                continue
            _orole, oring, oalts = old
            if ring == oring:
                # Geometry identical — still audit the value carry.
                for pt, a, b in zip(ring, alts, oalts):
                    _carry(pt, role, a, b)
                continue
            rec["changed"] += 1
            oset, cset = set(oring), set(ring)
            if oset <= cset and len(cset) > len(oset):
                rec["pure_insert"] += 1
            elif cset <= oset and len(oset) > len(cset):
                rec["pure_drop"] += 1
                rec["dropped_verts"] += len(oset) - len(cset)
            else:
                rec["moved"] += 1
            # Value carry over the vertices that survived, by position.
            oalt_at = dict(zip(oring, oalts))
            for pt, a in zip(ring, alts):
                _carry(pt, role, a, oalt_at.get(pt))
            if len(cset) > len(oset):
                ins = _classify_insert_values(oring, oalts, ring, alts,
                                              shared_at=shared_at,
                                              self_key=key)
                for k in ("inserted", "lerp_exact", "lerp_near",
                          "weld_adopt", "off_lerp", "no_value"):
                    rec[k] += ins[k]
                rec["insert_worst_m"] = max(rec["insert_worst_m"],
                                            ins["worst_m"])
                rec["ins_sites"].extend(
                    (d, x, y, role, got, want)
                    for (d, x, y, got, want) in ins["sites"])
        rec["removed_shape"] = sum(1 for k in prev if k not in cur)

        if (rec["changed"] or rec["new_shape"] or rec["removed_shape"]
                or rec["survivor_moved"]):
            UI.vprint(1,
                f"  [geom-seam] {name}: {rec['changed']} airside shape(s) "
                f"mutated (insert {rec['pure_insert']}, drop "
                f"{rec['pure_drop']}, move {rec['moved']}), "
                f"{rec['new_shape']} new, {rec['removed_shape']} removed; "
                f"VALUES: {rec['survivor_moved']} of {rec['survivors']} "
                f"survivor(s) moved ({rec['survivor_moved_material']} "
                f"material, worst {rec['survivor_worst_m']:.4f} m), "
                f"{rec['inserted']} inserted vertex(es) "
                f"[lerp-exact {rec['lerp_exact']}, near {rec['lerp_near']}, "
                f"OFF {rec['off_lerp']}, valueless {rec['no_value']}, "
                f"worst {rec['insert_worst_m']:.4f} m], "
                f"{rec['dropped_verts']} vertex(es) dropped.")
        else:
            UI.vprint(1, f"  [geom-seam] {name}: airside INERT.")
        log.append(rec)
        layout._geom_seam_log = log
        layout._geom_seam_prev = cur
    except Exception as exc:                               # pragma: no cover
        UI.vprint(1, f"  [geom-seam] {name}: audit FAILED {exc!r}")


def seam_report(layout, icao: str = "") -> None:
    """The seam ledger: which stage mutated airside, and did it carry values.

    ``RE-PROJECTION CLASS`` is the acceptance number of the double-
    projection retirement: a stage that moved a SURVIVING vertex's value,
    left an inserted vertex OFF the lerp, or left one valueless, did not
    carry its values through the geometry operation and is therefore a
    stage a projection has to come back and fix.
    """
    if not seam_audit_enabled():
        return
    log = list(getattr(layout, "_geom_seam_log", None) or [])
    if not log:
        return
    UI.vprint(1, f"  [geom-seam] {icao}: STAGE LEDGER (post-solve airside "
                 f"geometry + value carry) —")
    tot_reproj = 0
    tot_gs = 0
    for r in log:
        # THE CLASS, stated exactly: an AIRSIDE-partition value that moved
        # without a carry law, an insert that matched neither carry law,
        # or an insert left with no value at all.  Stage-B (service
        # junction) seating is broken out, never counted here.
        reproj = (r["survivor_moved"] - r["gs_survivor_moved"]
                  + r["off_lerp"] + r["no_value"])
        tot_gs += r["gs_survivor_moved"]
        # A PROJECTION seam is the projection's OWN authorship, not a
        # refinement stage that failed to carry — it is the thing being
        # counted out of the pipeline, so it never enters the class it is
        # measured against.
        is_proj = "final_projection" in r["seam"]
        if not is_proj:
            tot_reproj += reproj
        if not (r["changed"] or r["new_shape"] or r["removed_shape"]
                or reproj):
            continue
        UI.vprint(1,
            f"      {r['seam']}: shapes changed {r['changed']} "
            f"(ins {r['pure_insert']}/drop {r['pure_drop']}/move "
            f"{r['moved']}), new {r['new_shape']}, removed "
            f"{r['removed_shape']}; "
            + (f"PROJECTION AUTHORED {reproj} value(s)"
               if is_proj else
               f"RE-PROJECTION CLASS {reproj} "
               f"(airside survivor moves "
               f"{r['survivor_moved'] - r['gs_survivor_moved']}, off-lerp "
               f"{r['off_lerp']}, valueless {r['no_value']}); CARRIED "
               f"lerp {r['lerp_exact'] + r['lerp_near']}, weld "
               f"{r['weld_adopt']}, dropped {r['dropped_verts']}; "
               f"stage-B seating {r['gs_survivor_moved']}"))
        if is_proj:
            continue
        for d, x, y, role, was, now in sorted(
                r["mv_sites"], reverse=True)[:5]:
            UI.vprint(1, f"          MOVED {role} ({x:.1f},{y:.1f}) "
                         f"{was:.3f} -> {now:.3f} (|dz| {d:.4f} m)")
        for d, x, y, role, got, want in sorted(
                r["ins_sites"], reverse=True)[:5]:
            UI.vprint(1, f"          OFF-LERP {role} ({x:.1f},{y:.1f}) "
                         f"got {got:.3f}, lerp wanted {want:.3f} "
                         f"(|d| {d:.4f} m)")
    UI.vprint(1, f"  [geom-seam] {icao}: TOTAL RE-PROJECTION CLASS "
                 f"{tot_reproj} (target 0 — every post-solve airside "
                 f"geometry change carries its values by interpolation or "
                 f"weld, or is additive emission); stage-B service seating "
                 f"{tot_gs} (lawful, groundside partition); the projection "
                 f"seams' own authorship is excluded and counted above.")
    # THE LEDGER AS DATA (S1f).  The printed report keeps the top 5 sites
    # per seam, which answers "which stage" and cannot answer "which stage
    # moved THIS vertex" — the question an attribution of an emitted row
    # back to its minting stage has to ask, per site, for every site.  The
    # dump is the SAME ``log`` the lines above are printed from (one
    # ledger, one authority; it derives nothing and re-measures nothing),
    # written only when the path is given.  A failure here is reported and
    # never raised: an audit that can fail a build is a worse instrument
    # than no audit.
    _json_path = os.environ.get(_SEAM_JSON_ENV)
    if _json_path:
        try:
            import json as _json
            with open(_json_path, "w") as _fh:
                _json.dump({"icao": icao, "seams": log}, _fh)
            UI.vprint(1, f"  [geom-seam] {icao}: ledger written to "
                         f"{_json_path} ({len(log)} seam(s)).")
        except Exception as exc:                           # pragma: no cover
            UI.vprint(1, f"  [geom-seam] {icao}: ledger dump FAILED "
                         f"{exc!r}")


# ── Coverage probe (env O4_COVERAGE_PROBE, debug aid) ────────────────
def coverage_probe(layout, tag: str) -> None:
    """Print which pavement shapes own each probe point, labelled ``tag``.

    ``O4_COVERAGE_PROBE="lat,lon;lat,lon"`` — call sites sprinkle this
    after each post-slice pipeline pass, so a point that LOSES its owner
    between two tags names the pass that deleted the coverage (the SPJC
    service-strip loss took a day to bisect by hand).  No-op without the
    env var; never raises.
    """
    spec = os.environ.get("O4_COVERAGE_PROBE")
    if not spec:
        return
    try:
        from shapely.geometry import Point
        from .layout import _projection
        to_m = _projection(layout.anchor)
        _ROLES = ("apron", "junction", "service_junction", "service_road",
                  "building", "groundside_pavement", "runway",
                  "runway_crossing", "terminal", "stub", "primary_parallel",
                  "secondary_parallel", "cross_connector")
        out = []
        for part in spec.split(";"):
            la, lo = (float(v) for v in part.split(","))
            x, y = to_m(lo, la)
            pt = Point(x, y)
            owners = [
                f"{s.role}#{i}"
                for i, s in enumerate(layout.shapes)
                if s.role in _ROLES and s.polygon is not None
                and not s.polygon.is_empty and s.polygon.contains(pt)]
            out.append(f"({la:.5f},{lo:.5f})→{owners or ['LOST']}")
        print(f"  [coverage-probe] {tag}: " + " | ".join(out))
    except Exception as _e:                          # pragma: no cover
        print(f"  [coverage-probe] {tag}: ERROR {_e!r}")


def insert_probe_nodes(layout, spec: str, radius_m: float = 10.0) -> int:
    """Insert DIAGNOSTIC ring vertices near probe points (user 2026-07-07).

    ``O4_PROBE_NODES="lat,lon;lat,lon"`` — for each probe point, every
    pavement ring EDGE passing within ``radius_m`` gains a vertex at the
    point's perpendicular projection, with the altitude LINEARLY
    INTERPOLATED along that edge — elevation-neutral by construction
    (the rendered surface is unchanged; the mesh merely gains a
    constraint there), but the emitted patch then carries an explicit
    node + alt_abs at the spot, so long node-free straightaways become
    verifiable in JOSM / in-sim (CYXY service-road "ridge" report: the
    nearest emitted vertices were 71-107 m away — nothing to inspect).

    Runs at the very END of the build (after decimation, projection,
    and skirts — a lerped point on a straight edge is exactly the
    3D-collinear class emit decimation removes, so it must be inserted
    after).  Both shapes sharing an edge get the same XY and the same
    lerp, so the emit-time consensus merges them into one node.
    No-op without the env var; never raises.
    """
    try:
        from shapely.geometry import Polygon as _Poly
        from .layout import _projection
        to_m = _projection(layout.anchor)
        pts = []
        for part in spec.split(";"):
            la, lo = (float(v) for v in part.split(","))
            pts.append(to_m(lo, la))
        n_inserted = 0
        for s in layout.shapes:
            poly = s.polygon
            if (poly is None or poly.is_empty
                    or poly.geom_type != "Polygon"):
                continue
            ring = list(poly.exterior.coords)      # closed
            alts = (list(s.node_altitudes)
                    if s.node_altitudes is not None else None)
            if alts is not None and len(alts) != len(ring):
                continue                            # malformed; skip
            insertions = []                         # (seg_idx, (x,y), alt)
            for (px, py) in pts:
                for i in range(len(ring) - 1):
                    ax, ay = ring[i]
                    bx, by = ring[i + 1]
                    ex, ey = bx - ax, by - ay
                    L2 = ex * ex + ey * ey
                    if L2 < 4.0:                    # short seg: has nodes
                        continue
                    t = ((px - ax) * ex + (py - ay) * ey) / L2
                    if not (0.05 < t < 0.95):       # off-end: node nearby
                        continue
                    qx, qy = ax + t * ex, ay + t * ey
                    dx, dy = px - qx, py - qy
                    if dx * dx + dy * dy > radius_m * radius_m:
                        continue
                    a = None
                    if alts is not None:
                        a = alts[i] + t * (alts[i + 1] - alts[i])
                    insertions.append((i, (qx, qy), a))
            if not insertions:
                continue
            for i, q, a in sorted(insertions, reverse=True):
                ring.insert(i + 1, q)
                if alts is not None:
                    alts.insert(i + 1, a)
            try:
                new_poly = _Poly(ring)
                if new_poly.is_empty or not new_poly.is_valid:
                    continue
            except Exception:
                continue
            s.polygon = new_poly
            if alts is not None:
                s.node_altitudes = alts
            n_inserted += len(insertions)
        if n_inserted:
            print(f"  [probe-nodes] inserted {n_inserted} diagnostic "
                  f"vertex(es) at {len(pts)} probe point(s).")
        return n_inserted
    except Exception as _e:                          # pragma: no cover
        print(f"  [probe-nodes] ERROR {_e!r}")
        return 0
