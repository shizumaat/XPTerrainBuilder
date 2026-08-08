"""THE FABRIC MODEL — sparse lawful emission (Phase A, gate
``O4_FABRIC_SPARSE``, default OFF).

Charter: owner ruling 2026-08-08 "THE FABRIC MODEL" (docs/RULINGS.md) and
``docs/specs/fabric-model-spec.md``.  The owner's articulation, verbatim:

    "we have a base 'fabric' we're essentially deforming, there's no need
    to 'generate relief'… We simply need to grade our pavement and
    building pads, and Ortho4XP will automatically blend the surrounding
    terrain.  We only add our adjacent ground and drainage areas to
    ensure FAA regulations, but for unregulated areas I believe the
    answer is to do nothing.  I don't think we even need to grade apron
    fans."

and the second thought experiment, which is what this module implements:

    "…the nodes along the back edge of the apron should be welded to the
    building corners; if we place no nodes between the buildings, and
    each building is at its correct seat, then the back apron edge
    between the buildings will automatically slope between them."

PHASE A IS THE PROOF PAIR AND NOTHING ELSE.  The model is applied to two
declared CLUSTERS — HECA's apron ``-10447`` (plus its welded neighbours
and the pads fronting it) and CYXY's hillside building group — so the
acceptance measurements have a control that is the production surface
everywhere else.  With the gate off this module arms nothing, marks
nothing and answers ``False`` to every predicate: :func:`is_sparse` is
the ONLY thing any caller consults, and it short-circuits on ``_REGION
is None``.  Production emission is untouched until Phase B.

WHAT "SPARSE" MEANS HERE, mechanically, inside a cluster:

  * **no generic stationing** — the 60 m ``densify_long_edges`` pass
    (the "stationing density beyond the adequate-spine/curve floor" on
    the spec's retire list) does not run on cluster shapes;
  * **no fan zones** — ``apron_terrace`` declares none and panelizes
    none there (spec: "Fan-zone declarations and machinery" retire);
  * **no adjacent-ground bands, walls or feather** — the drape is the
    transition (spec §4, and the walls-to-carves ruling 2026-08-07);
  * **ring thinning to law vertices** — every ring vertex that is NOT a
    weld (shared with another shape: seats, mouths, junction shares,
    reg-feature shares), NOT a boundary direction change and NOT a spine
    station is removed BEFORE the solve, so the solve sees the same
    sparse fabric the census measures and the sim renders.

"ADEQUATE" IS MEASURED, NOT INVENTED (spec §2, owner rider).  Every
tolerance below is imported from the machinery that already owns it:

  ``emit_decimate.XY_TOL_M``        0.02 m — the house chord/curve band
                                    (the emit decimator's own
                                    Douglas-Peucker tolerance); a vertex
                                    whose removal moves the boundary by
                                    more than this IS a direction change.
  ``layout.SHARED_VERTEX_TOL_M``    0.5 m — the house weld tolerance, used
                                    for the spine-station proximity test.
  ``config.SPINE_STEP_M``           12 m — the spine station spacing the
                                    junction spine machinery already
                                    stations at; spine stations are
                                    force-kept, never re-derived here.
  ``layout.PAVEMENT_NODE_MAX_CHORD_M``  60 m — the generic stationing cap
                                    this model retires INSIDE a cluster
                                    (and only there).

No new constant is defined by this module.
"""

from __future__ import annotations

import math
import os

from shapely.geometry import Polygon, Point, MultiLineString, LineString
from shapely.ops import unary_union
from shapely.prepared import prep

__all__ = [
    "ENABLED",
    "arm",
    "disarm",
    "is_sparse",
    "thin_rings",
    "report",
]


# ── The gate ────────────────────────────────────────────────────────────
def _gate_on() -> bool:
    return os.environ.get("O4_FABRIC_SPARSE", "0") == "1"


ENABLED = _gate_on()


# ── The declared Phase-A clusters ───────────────────────────────────────
# Seeds are stated in LAT/LON (frame-independent; a layout-local metre
# literal would silently move with the anchor).  Each entry is
#   {"points": [(lat, lon), ...],   -> the shape CONTAINING each point
#    "boxes":  [(lat0, lon0, lat1, lon1), ...]}  -> shapes INTERSECTING it
# and the cluster is the seed set PLUS one hop of welded neighbours.
_PHASE_A_SEEDS = {
    # HECA — the apron the acceptance names (emitted way -10447): 610 x
    # 1089 m, 13.8 m of ring spread, 1.4-2.0 % against the 1.0 % apron
    # cap.  Seeded by an interior point so the selection does not depend
    # on emit-time way ids or on shape ordinals.
    "HECA": {"points": [(30.1264268, 31.4121720)], "boxes": []},
    # CYXY — the owner's named sim case: the hillside building group and
    # the aprons it fronts (pads seated 702.80 -> 706.29 m up the slope,
    # RULINGS 2026-08-08 "Frontage weld: measured ALREADY-TRUE").
    "CYXY": {"points": [],
             "boxes": [(60.7039809, -135.0801823,
                        60.7158386, -135.0687982)]},
}

# Roles a cluster may take in.  Runway-family surfaces are REG SET and are
# never thinned, never de-banded (Annex-14 graded strip, RESA/OFZ).
_CLUSTER_ROLES = frozenset({
    "apron", "junction", "service_junction", "building",
    "groundside_pavement", "service_road",
})
# Of those, the ones whose rings this module thins.  Buildings are pads:
# their footprint fidelity IS the seat (same exclusion the emit decimator
# makes), and roads carry their own carve geometry.
_THIN_ROLES = frozenset({"apron", "junction", "service_junction",
                         "groundside_pavement"})

# Module state, armed per build.  ``None`` == inert.
_REGION = None          # prepared shapely geometry, layout metre frame
_REGION_RAW = None
_STATS: dict = {}


def _reset() -> None:
    global _REGION, _REGION_RAW, _STATS
    _REGION = None
    _REGION_RAW = None
    _STATS = {}


def disarm() -> None:
    """Return the module to its inert state (tests, repeated builds)."""
    _reset()


def report() -> dict:
    """The armed cluster's measurement record (empty when inert)."""
    return dict(_STATS)


# ── Arming ──────────────────────────────────────────────────────────────
def arm(layout, icao: str = "") -> int:
    """Select the cluster for ``icao`` and freeze it as a REGION in the
    layout's metre frame.  Returns the number of shapes selected; 0 (and
    a fully inert module) when the gate is off or the airport carries no
    declared cluster.

    The region — not a shape LIST — is what is frozen, because shapes are
    born and re-cut after this point (clips, welds, groundside separation)
    and a stale reference set would silently stop covering them.  Any
    shape whose representative point lands in the region is sparse, ever
    after.
    """
    _reset()
    if not _gate_on():
        return 0
    seeds = _PHASE_A_SEEDS.get((icao or "").upper())
    if not seeds or layout is None or getattr(layout, "anchor", None) is None:
        return 0
    ll_to_m = getattr(layout, "ll_to_m", None)
    if ll_to_m is None:
        return 0

    shapes = [s for s in getattr(layout, "shapes", ())
              if getattr(s, "polygon", None) is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"
              and getattr(s, "role", None) in _CLUSTER_ROLES]
    if not shapes:
        return 0

    seed_idx: set[int] = set()
    for (lat, lon) in seeds.get("points", ()):
        px, py = ll_to_m(lat, lon)
        pt = Point(px, py)
        for i, s in enumerate(shapes):
            if s.polygon.contains(pt):
                seed_idx.add(i)
    for (la0, lo0, la1, lo1) in seeds.get("boxes", ()):
        x0, y0 = ll_to_m(la0, lo0)
        x1, y1 = ll_to_m(la1, lo1)
        box = Polygon([(min(x0, x1), min(y0, y1)), (max(x0, x1), min(y0, y1)),
                       (max(x0, x1), max(y0, y1)), (min(x0, x1), max(y0, y1))])
        for i, s in enumerate(shapes):
            if s.polygon.intersects(box):
                seed_idx.add(i)
    if not seed_idx:
        return 0

    # ONE HOP of welded neighbours — "the apron + its welded neighbors +
    # fronting pads".  A neighbour is a shape sharing a vertex with a
    # seed at the house weld key (millimetre-identical post-weld, the
    # same identity ``emit_decimate`` votes on).
    seed_keys: set[tuple] = set()
    for i in seed_idx:
        for (x, y) in shapes[i].polygon.exterior.coords:
            seed_keys.add(_key(x, y))
    cluster = set(seed_idx)
    for i, s in enumerate(shapes):
        if i in cluster:
            continue
        for (x, y) in s.polygon.exterior.coords:
            if _key(x, y) in seed_keys:
                cluster.add(i)
                break

    polys = [shapes[i].polygon for i in sorted(cluster)]
    try:
        region = unary_union(polys)
    except Exception:
        return 0
    if region.is_empty:
        return 0

    global _REGION, _REGION_RAW, _STATS
    _REGION_RAW = region
    _REGION = prep(region)
    _STATS = {
        "icao": (icao or "").upper(),
        "seeds": len(seed_idx),
        "cluster_shapes": len(cluster),
        "region_area_m2": float(region.area),
        "roles": _role_tally([shapes[i] for i in sorted(cluster)]),
    }
    return len(cluster)


def _role_tally(shapes) -> dict:
    out: dict = {}
    for s in shapes:
        out[s.role] = out.get(s.role, 0) + 1
    return out


def _key(x: float, y: float) -> tuple:
    """The house cross-shape vertex identity (``emit_decimate._key``)."""
    return (int(round(x * 1000.0)), int(round(y * 1000.0)))


# ── The predicate every caller consults ─────────────────────────────────
def is_sparse(shape) -> bool:
    """True iff ``shape`` lies inside the armed Phase-A cluster.

    Inert by construction: with the gate off nothing arms, ``_REGION`` is
    ``None``, and this returns ``False`` before touching the shape.
    """
    if _REGION is None:
        return False
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return False
    if getattr(shape, "role", None) not in _CLUSTER_ROLES:
        return False
    try:
        return bool(_REGION.contains(poly.representative_point()))
    except Exception:
        return False


def sparse_shapes(layout) -> list:
    """Every shape of ``layout`` inside the armed cluster."""
    if _REGION is None:
        return []
    return [s for s in getattr(layout, "shapes", ()) if is_sparse(s)]


# ── The thinning pass ───────────────────────────────────────────────────
def _spine_lines(layout):
    """Taxi/service axes in the layout's metre frame, as ONE geometry.

    Read from the machinery that already publishes them
    (``verification.taxi_axes_exact_ll`` — the same axis population the
    axes sidecar carries and the census reads), never re-derived.
    """
    try:
        from .verification import taxi_axes_exact_ll
        axes, _routes = taxi_axes_exact_ll(layout)
    except Exception:
        return None
    lines = []
    for entry in axes or ():
        pts_ll = entry[0] if isinstance(entry, (tuple, list)) else None
        if not pts_ll or len(pts_ll) < 2:
            continue
        try:
            pts = [layout.ll_to_m(la, lo) for (la, lo) in pts_ll]
            lines.append(LineString(pts))
        except Exception:
            continue
    if not lines:
        return None
    try:
        return MultiLineString(lines)
    except Exception:
        return None


def thin_rings(layout, icao: str = "") -> int:
    """Remove every NON-LAW ring vertex from the cluster's pavement
    shapes, PRE-SOLVE.  Returns the number of vertices removed.

    A vertex survives iff it is one of:

      * a **weld** — its millimetre key appears on another shape's ring
        (seats, mouths, pad corners, junction shares, reg-feature
        shares).  This is also what keeps the partition CONFORMING: a
        vertex no other shape references cannot mint a T-vertex when it
        goes.
      * a **boundary direction change** — ``emit_decimate._ring_keep_set``
        (the house Douglas-Peucker at ``XY_TOL_M`` = 0.02 m) says the
        ring cannot be reconstructed without it.  Called with the MAX
        CHORD CAP LIFTED, which is exactly the generic stationing this
        model retires; every other tolerance is the decimator's own.
      * a **spine station** — within ``SHARED_VERTEX_TOL_M`` of a
        published taxi/service axis (the owner rider: "as long as we keep
        adequate nodes on spines and at curves").
      * a **seam anchor** — the tile-seam keys the solver hard-holds.

    Altitudes ride along by index (the ``node_altitudes`` closed/open
    convention is read through ``emit_decimate._ring_and_alts``), and the
    XY test runs with ``alts=None`` on purpose: between law vertices,
    INTERPOLATION IS THE LAWFUL SURFACE, so a DEM wiggle is not a reason
    to keep a node.
    """
    if _REGION is None:
        return 0
    from .emit_decimate import _ring_and_alts, _ring_keep_set
    from .layout import SHARED_VERTEX_TOL_M

    targets = [s for s in getattr(layout, "shapes", ())
               if is_sparse(s) and getattr(s, "role", None) in _THIN_ROLES
               and s.polygon.geom_type == "Polygon"]
    if not targets:
        return 0

    # Every OTHER shape's vertex keys — the weld set.  Built over the
    # whole layout (a cluster shape welded to a non-cluster neighbour
    # must keep that vertex too).
    target_ids = {id(s) for s in targets}
    foreign: dict = {}
    for s in getattr(layout, "shapes", ()):
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        rings = [poly.exterior] + list(poly.interiors)
        for r in rings:
            for (x, y) in r.coords:
                k = _key(x, y)
                foreign.setdefault(k, set()).add(id(s))

    spines = _spine_lines(layout)
    seam_keys = set()
    for _sk in (getattr(layout, "_seam_anchor_keys", None) or ()):
        try:
            seam_keys.add(tuple(_sk))
        except Exception:
            pass

    removed = 0
    per_shape = []
    for s in targets:
        ring, alts, closed_conv = _ring_and_alts(s)
        n = len(ring)
        if n < 5:
            continue
        forced = set()
        for i, (x, y) in enumerate(ring):
            k = _key(x, y)
            owners = foreign.get(k) or set()
            if owners - {id(s)}:
                forced.add(i)
                continue
            if k in seam_keys or (x, y) in seam_keys:
                forced.add(i)
                continue
            if spines is not None:
                try:
                    if spines.distance(Point(x, y)) <= SHARED_VERTEX_TOL_M:
                        forced.add(i)
                        continue
                except Exception:
                    pass
        # XY-only reconstruction test with the generic 60 m stationing cap
        # LIFTED — the retire-list item.  z_tol is unused with alts=None.
        keep = _ring_keep_set(ring, None, 1.0, forced=forced,
                              max_chord=float("inf"))
        if len(keep) >= n:
            continue
        if len(keep) < 4:
            continue                      # degeneracy veto (house rule)
        idx = sorted(keep)
        new_ring = [ring[i] for i in idx]
        try:
            poly = Polygon(new_ring, [list(r.coords)
                                      for r in s.polygon.interiors])
            if not poly.is_valid or poly.is_empty:
                continue
        except Exception:
            continue
        dropped = n - len(idx)
        s.polygon = poly
        if alts is not None:
            new_alts = [alts[i] for i in idx]
            s.node_altitudes = (new_alts + [new_alts[0]] if closed_conv
                                else new_alts)
        removed += dropped
        per_shape.append({
            "role": s.role, "ref": getattr(s, "ref", ""),
            "before": n, "after": len(idx),
            "forced": len(forced),
            "area_m2": float(poly.area),
        })

    _STATS["thin"] = {
        "shapes_thinned": len(per_shape),
        "vertices_removed": removed,
        "vertices_before": sum(p["before"] for p in per_shape),
        "vertices_after": sum(p["after"] for p in per_shape),
        "law_vertices": sum(p["forced"] for p in per_shape),
        "per_shape": per_shape,
    }
    return removed


def note_restation(n: int) -> None:
    """Record how many spine stations the existing station passes put
    back after the thinning — the MEASURED answer to "adequate nodes on
    spines" (owner rider), and the number Phase B's spec revision
    carries."""
    if _STATS:
        _STATS.setdefault("thin", {})["spine_stations_restored"] = int(n)


def emit_summary(icao: str = "") -> str:
    """One log line for the build transcript (empty when inert)."""
    if not _STATS:
        return ""
    t = _STATS.get("thin") or {}
    return (f"  [fabric-sparse] {icao}: cluster "
            f"{_STATS.get('cluster_shapes', 0)} shape(s), "
            f"{_STATS.get('region_area_m2', 0.0):.0f} m^2; thinned "
            f"{t.get('shapes_thinned', 0)} ring(s) "
            f"{t.get('vertices_before', 0)} -> {t.get('vertices_after', 0)} "
            f"vertices ({t.get('vertices_removed', 0)} removed, "
            f"{t.get('law_vertices', 0)} law vertices held, "
            f"{t.get('spine_stations_restored', 0)} spine station(s) "
            f"restored by the station passes).")
