"""Per-building route-feasibility elevation (user model, 2026-06-22).

A building that touches airside pavement is seated FLAT at the elevation
closest to its DEM that keeps it reachable WITHIN GRADE from EVERY runway
threshold along the real taxi route — the "heaviest anchor" the rest of the
network then grades to (docs/taxi_centerline_grading_plan.md §9).

The route to a building (user's definition, validated on CYXY):

  1. a PERPENDICULAR from the building centroid to the NEAREST taxi
     centerline (named or not — geometry only).  The part of that
     perpendicular inside the taxiway-width corridor climbs at the
     taxiway's own cap; the part beyond (real apron) at the apron cap (1%).
  2. from the foot point, the taxi-route to each threshold along the
     centerline graph at the PER-EDGE per-letter caps (narrow A/B = 3 %,
     wide C–F = 1.5 %) — including the partial first edge from the foot
     point to its graph node (the bit that snapping to the node would drop).

The feasibility BAND is the intersection over ALL thresholds:

  ceiling = min_t ( thr_elev_t + climb_t )
  floor   = max_t ( thr_elev_t − climb_t )

and the seated level is ``clamp(DEM, floor, ceiling)`` — closest to DEM,
could be above or below it.  Buildings NOT touching airside pavement are
omitted (the caller leaves them at their DEM).

A narrow code-A/B arm contributes its 3 % cap.  The ICAO size travels
PER-SEGMENT on each ``apt_dat_reader.TaxiCenterline`` (``seg_sizes``), so the
per-letter cap at the foot is read off the geometry — no name→letter table.
"""

from __future__ import annotations

import heapq
import math
import os
from typing import Callable, Dict, List, Tuple

from shapely.errors import GEOSException

from auto_patch.config import (
    BUILDING_AIRSIDE_CONTACT_MIN_COMPONENT_M2,
    BUILDING_FULL_FRONTAGE,
    BUILDING_FULL_FRONTAGE_AREA_M2,
    BUILDING_SEAT_FLATNESS_TOLERANCE_M,
    FLAT_CERTIFICATE_COVERAGE,
    VISIBLE_CHORD_CONNECT,
)
from auto_patch.grade_law import APRON_MAX_GRADE, BUILDING_REACH_CORRIDOR_M
from auto_patch.layout import (
    ROLE_APRON, ROLE_BUILDING, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL, ROLE_RUNWAY, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
)

__all__ = ["building_feasible_levels", "reach_band_unified",
           "runway_edge_anchors", "spine_value_fields",
           "BandInversionError", "assert_no_final_band_inversion",
           "FINAL_BAND_INVERSION_TOL_M"]

# ── BAND-SEED COMPLETENESS — STANDING LAW ────────────────────────────────
# (seed-fix round §2; formerly gate ``O4_BAND_SEED_COMPLETE``, retired
# 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG": every believed-in
# law becomes standing law and its env override is deleted.)
#
# THE LAW.  :func:`spine_value_fields` seeds from ``G.runway_anchor`` UNION
# the on-spine ``seed_rwy_seam`` HARD TRUTH — the runway/CIFP profile
# values and tile-seam DEM pins the solve already holds immovable — and
# the post-solve band law adjudicates the FLOOR-ABOVE-OWN-HARD-VALUE class.
#
# THE DEFECT IT CLOSES.  A node can be HARD runway truth and still be
# absent from the value fields' seed set, because ``G.runway_anchor`` is
# the runway-JOIN anchor map, not the hard-truth set.  Measured at HECA
# (``seed_attrib/``): 8 of the 31 on-spine ``seed_rwy_seam`` nodes are
# missing (2863, 3610, 3631, 4818, 6907, 7236, 7298, 7493), and the band
# floor then sits ABOVE a node's own hard runway value at 2 of them (4818
# by +2.344 m, 2863 by +1.522 m).  A band whose own seeds are the runway
# anchors cannot lawfully floor a runway node above its own runway value —
# that is one instrument contradicting itself, and every consumer that
# clamps a target INTO the band (the apron-contact seats) inherits it.
#
# The inversion assert stays LOUD: certify-or-fail is the architecture
# (RULINGS 2026-08-05 §1 keeps "certify-or-fail-loud in the solve").

# ── THE LOUD ERROR (spec ``docs/specs/kill-half-spec.md`` §3) ────────────
# The band quarantine is deleted (§2), and what replaces it is not a
# quieter quarantine but an ERROR.  Owner law (docs/RULINGS.md,
# feasibility-is-guaranteed): a real airport with real thresholds HAS a
# lawful surface, so a FINAL band the anchors contradict through is a law
# defect — a wrong metric, a wrong anchor value, a wrong role/cap or a
# false topology — and the build must say so instead of painting over it.
#
# Scope: the LAST ``spine_value_fields`` output of the build (earlier
# calls are intermediate states of an unfinished solve, and their
# inversions are expected to close as anchors settle).
# Threshold: the campaign's 0.01 m materiality floor (CLAUDE.md
# convergence guards) — below it a residual is PASS-with-residual, never a
# defect.  Measured at the new defaults before this landed: HECA 0 of
# 18,073 nodes inverted, HEAZ worst 0.00035 m.
FINAL_BAND_INVERSION_TOL_M = 0.01


class BandInversionError(RuntimeError):
    """The FINAL reach band is inverted beyond the materiality floor.

    Deliberately NOT a ``ValueError``/shapely error: the pipeline's
    geometry guards (``_GEOM_EXC``) swallow those to keep a build alive,
    and this one must never be swallowed."""


# ── FRAME STAMPS (RULINGS 2026-08-06 "Instrument truth is law", binding
#    point 3: every reported NUMBER carries its FRAME — tree sha, node
#    space, world, crown space) ────────────────────────────────────────
#
# ONE stamp for the band / seat instruments, because two stamps that
# spell the same frame differently are the two-instruments trap with
# extra steps.  Absent facets are stamped EXPLICITLY (``?``) rather than
# omitted — the rule ``provenance.provenance_tags`` already follows, so a
# reader can tell "not determinable" from "nobody stamped it".
_TREE_SHA_CACHE: list = []


def instrument_tree_sha() -> str:
    """``<short sha>`` (``*`` = dirty working tree), or ``?``.

    Memoised per PROCESS: the source tree cannot change mid-build, and a
    tile build reports many airports.  Measured cost of the two git calls
    on this checkout: 0.008 s + 0.013 s, paid once."""
    if not _TREE_SHA_CACHE:
        stamp = "?"
        try:
            from auto_patch.provenance import git_provenance
            g = git_provenance() or {}
            sha = g.get("sha")
            if sha:
                stamp = str(sha) + ("*" if g.get("dirty") else "")
        except Exception:                                  # pragma: no cover
            stamp = "?"
        _TREE_SHA_CACHE.append(stamp)
    return _TREE_SHA_CACHE[0]


def instrument_world(layout) -> str:
    """The DEM WORLD the reported values were seeded from.

    Read from what the build recorded on the layout, never re-derived: a
    second reading of the DEM is a second instrument.  ``pipeline`` stamps
    ``_dem_world_label`` (the DEM object's own ``source_path``, which is
    how a ``ConstantDEM`` oracle world announces itself — ``base RAW``
    alone cannot tell a real raw DEM from ``<constant-dem 10000 m>``); the
    baked-inset record is the second half."""
    label = getattr(layout, "_dem_world_label", None)
    if not label:
        label = "?"
    inset = getattr(layout, "dem_inset_provenance", None)
    if inset is not None:
        try:
            from auto_patch.provenance import dem_label
            label = f"{label} [{dem_label(inset)}]"
        except Exception:                                  # pragma: no cover
            pass
    return str(label)


def instrument_crown(layout) -> str:
    """The CROWN SPACE stamp: how many crown-drop keys the layout carries.

    A number, not an adjective — ``crown_keys=0`` means crowned and
    uncrowned space coincide, and any nonzero count means the reader must
    know which of the two a value is quoted in (memory: an emitted step
    can be z'-level; scans that skip ``_crown_of`` chase ghosts)."""
    field = getattr(layout, "_crown_drop_key", None) or {}
    try:
        return f"crown_keys={len(field)}"
    except Exception:                                      # pragma: no cover
        return "crown_keys=?"


def instrument_frame(layout, node_space: str = "?", crown: str = "") -> str:
    """One-line frame stamp: tree sha, world, node space, crown space."""
    return (f"[frame tree={instrument_tree_sha()} "
            f"world={instrument_world(layout)} "
            f"nodes={node_space} "
            f"{crown or instrument_crown(layout)}]")


#: THE node space every ``_final_band_*`` number is expressed in.  The
#: ids are the indices ``_build_node_list`` assigned inside the ONE call
#: that built this field; a rebuilt field is a DIFFERENT space in which
#: they resolve to nothing (measured: all three HECA canyon pairs, "records
#: no route" — ``tools/trace_reach_route.py``, which documents the hazard
#: on the CONSUMER side).  This is the producer side of that stamp.
BAND_NODE_SPACE = ("solve _build_node_list ids as recorded by "
                   "spine_value_fields; a REBUILT field is a different "
                   "space (tools/trace_reach_route.py)")

# Pavement a building must touch to count as airside-served (else → DEM).
_AIRSIDE_ROLES = frozenset({
    ROLE_APRON, ROLE_JUNCTION, ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
})
_TOUCH_TOL_M = 2.0         # building↔airside distance to count as "touching"
_INF = float("inf")
_UNSET = object()          # build-wide-cache sentinel (distinguishes None result)


_VIS_BUFFER_M = 0.5        # bridge weld-seam slivers between abutting shapes
_VIS_ON_PAV_FRAC = 0.97    # chord counts as visible if ≥ this fraction is paved
# Minimum paved mid-cell samples (of n) for float(paved/n) >= _VIS_ON_PAV_FRAC —
# the integer form of the _paved_frac accept comparison, replicated exactly so
# the two-stage sampler in _accept_flags can early-reject without changing any
# accept decision.
_ACCEPT_MIN_PAVED = {
    n: next(p for p in range(n + 1) if (p / n) >= _VIS_ON_PAV_FRAC)
    for n in range(1, 97)
}


def _pavement_visibility(layout):
    """Prepared airside-pavement geometry (∪ building pads) for the visible-chord
    test — a building→taxiway connection is legal only if its chord stays within
    pavement (the user's rule: never taxi across grass / a service road; a spine
    is a centerline, so apron pavement counts).  Building pads are included so a
    chord may start inside the building's own pad.  Buffered slightly to bridge
    numerical weld-seam slivers between abutting shapes.

    PERF (build-wide cache): the prepared union is a pure function of the airside
    pavement + building 2D geometry, which is FROZEN after phase-1 layout — the
    solve moves only elevations and the emit only appends ``graded_strip`` pieces
    (not in ``_AIRSIDE_ROLES``), so ``vis`` is byte-identical across the
    construct / solve / emit ``reach_band_unified`` calls.  The union+buffer+prep
    was rebuilt on every call (≥3×/build); cache it on the layout so it is built
    once.  Same object each call ⇒ no output change."""
    cached = getattr(layout, "_pav_vis_cache", _UNSET)
    if cached is not _UNSET:
        return cached
    from shapely.ops import unary_union
    from shapely.prepared import prep
    polys = [s.polygon for s in layout.shapes
             if (s.role in _AIRSIDE_ROLES or s.role == ROLE_BUILDING)
             and s.polygon is not None and not s.polygon.is_empty]
    vis = None
    if polys:
        try:
            u = unary_union(polys).buffer(_VIS_BUFFER_M)
            vis = prep(u)
        except Exception:                                  # pragma: no cover
            vis = None
    try:
        layout._pav_vis_cache = vis
    except Exception:                                      # pragma: no cover
        pass
    return vis


def _cl_by_distance(c, cls, tree=None, max_r=None):
    """Iterate centerlines in true-distance order from ``c`` — STRtree-backed
    when a ``tree`` (``STRtree(cls)``) is given, so a query touches the
    handful of nearby lines instead of distance-scanning the whole list (the
    reach band runs ~10k queries × ~500 lines; the full scans were ~half the
    solve time).  With ``max_r`` only lines within that distance are yielded.
    Without a tree this is the plain full sort, so behaviour is identical."""
    if tree is None:
        for L in sorted(cls, key=lambda L: L.distance(c)):
            if max_r is not None and L.distance(c) > max_r:
                break
            yield L
        return
    if max_r is not None:
        try:
            idxs = tree.query(c.buffer(max_r))
        except Exception:                                  # pragma: no cover
            idxs = range(len(cls))
        cand = sorted((cls[int(k)].distance(c), int(k)) for k in idxs)
        for d, k in cand:
            if d <= max_r:
                yield cls[k]
        return
    # expanding rings: everything within r is in the candidate set, so the
    # ≤r prefix of each round is exact global distance order.
    seen: set = set()
    r = 60.0
    while True:
        try:
            idxs = tree.query(c.buffer(r))
        except Exception:                                  # pragma: no cover
            for L in sorted(cls, key=lambda L: L.distance(c)):
                yield L
            return
        cand = sorted((cls[int(k)].distance(c), int(k))
                      for k in idxs if int(k) not in seen)
        for d, k in cand:
            if d <= r:
                seen.add(k)
                yield cls[k]
        if r > 1e5:                    # exhausted: yield any stragglers
            rest = sorted((cls[k].distance(c), k)
                          for k in range(len(cls)) if k not in seen)
            for _d, k in rest:
                yield cls[k]
            return
        r *= 4.0


def _paved_frac(chord, vis) -> float:
    """Fraction of ``chord`` on pavement, by VECTORIZED point sampling
    (``shapely.contains_xy`` on the prepared pavement — one C call) instead
    of an exact line∩polygon overlay (~0.5 ms each).  The overlay was 60 %
    of the whole CYUL build: the visible-chord walk tries ~50 candidates
    per node on a fragmented centerline network and paid it on every miss
    (1.27 M calls, 650 s).  Per-point *Python* shapely calls are no cheaper
    than the overlay (call overhead dominates) — the batch call is.
    Sampling at ≤1 m (capped 96 points) resolves ``_VIS_ON_PAV_FRAC``
    comfortably (a 3 % gap on a 30 m chord is ~1 m)."""
    import numpy as _np
    import shapely as _sh
    coords = list(chord.coords)
    (ax, ay), (bx, by) = coords[0], coords[-1]
    L = chord.length
    if L < 1e-9:
        return 1.0
    n = min(96, max(8, int(L)))
    t = (_np.arange(n) + 0.5) / n
    geom = getattr(vis, "context", vis)
    try:
        _sh.prepare(geom)          # idempotent; cached on the geometry
        hits = _sh.contains_xy(geom, ax + (bx - ax) * t, ay + (by - ay) * t)
        return float(hits.mean())
    except Exception:              # pragma: no cover — old shapely fallback
        from shapely.geometry import Point as _P
        hit = sum(1 for k in range(n)
                  if vis.contains(_P(ax + (bx - ax) * t[k],
                                     ay + (by - ay) * t[k])))
        return hit / n


def _nearest_visible_centerline(c, cls, vis, tree=None, cache=None,
                                cls_arr=None):
    """The nearest centerline to point ``c`` whose connecting chord stays within
    pavement (``vis``).  Falls back to the straight-line nearest if none is
    visible (e.g. a building wholly off pavement — the caller's touch test has
    already gated that out).  ``tree``: optional ``STRtree(cls)`` (see
    :func:`_cl_by_distance`).

    ``cache`` (build-wide reach-band memo, optional ``dict``): the result is a
    pure function of ``(c, cls, vis)`` — the taxi-centerline set and the airside
    pavement union, both FROZEN 2D geometry for the whole build — so the same
    query point yields the same serving centerline in the construct, the solve,
    and the emit.  Keyed on the exact float coordinates ⇒ identical result ⇒ no
    output change.  The returned ``ln`` is one of the persistent ``cl.line``
    objects (stable across the per-stage ``cls`` rebuilds), so downstream
    ``id(ln)`` lookups stay valid.  Callers that do NOT pass a cache (e.g. the
    gated building-frontage-spine anchor) are byte-identical to before.

    PERF (vectorised candidate scan): this walk was ~77 % of a KBNA build
    (cProfile) — the per-vertex reach-band query tests centerlines in distance
    order until a ≥ ``_VIS_ON_PAV_FRAC`` visible chord is found, and the
    "phantom" vertices (no visible centerline; isolated apron/pavement pieces)
    march the WHOLE centerline set.  The old loop paid a full stack of Python
    shapely wrappers PER candidate (``nearest_points`` → ``shortest_line``,
    ``LineString`` construction, ``vis.contains``): ~35 M wrapped calls, ~100 s
    of the 175 s CYXY replay were wrapper overhead alone.  Pull the
    distance-ordered generator in GROWING chunks and evaluate each chunk with
    ONE vectorised ``shapely.shortest_line`` + ONE prepared ``shapely.contains``
    (``vis.contains(x)`` is exactly ``shapely.contains(vis.context, x)``), then
    fall to the per-chord ``_paved_frac`` seam-gap test only for the chords that
    fail the exact test — in the SAME distance order, returning the SAME first
    acceptable centerline.  ``shapely.shortest_line(ln, c)`` returns the chord
    ``[foot_on_ln, c]`` — the reverse of the old ``[c, foot]`` — but chord length,
    prepared containment and ``_paved_frac`` (whose mid-point sample set is
    symmetric about the chord centre) are all orientation-invariant, so the
    accept/reject decision is bit-identical.  Growing the chunk keeps the common
    median-1-candidate query cheap while the phantom tail is batched."""
    import shapely as _sh
    import numpy as _np
    from itertools import islice as _islice
    key = None
    if cache is not None:
        key = (c.x, c.y)
        hit = cache.get(key, _UNSET)
        if hit is not _UNSET:
            return hit

    def _cache_and_return(result):
        if key is not None:
            cache[key] = result
        return result

    vis_ctx = getattr(vis, "context", vis)
    # ENDPOINT-MARGIN PRUNE (perf 2026-07-15, KBNA profile): the query point's
    # distance to the pavement union, ``m_c``, is an exact lower bound on every
    # candidate chord's unpaved length — the chord ENDS at ``c``, and no point
    # within ``m_c`` of ``c`` is on pavement.  Two bit-exact consequences used
    # in the accept loops below:
    #   * exact contains is ALWAYS False when ``m_c > 0`` (the endpoint is
    #     strictly outside the polygon), so the GEOS line-contains test is
    #     skipped wholesale — profiling showed 1.5 M scalar contains calls on
    #     the deep walkers;
    #   * the sampled paved fraction of a chord of length L has at least
    #     ``floor(n·m_c/L)`` off-pavement mid-cell samples, so any candidate
    #     with ``(n - (floor(n·m_c/L) - 1)) / n < _VIS_ON_PAV_FRAC`` cannot
    #     accept and is rejected WITHOUT sampling (the -1 absorbs alignment
    #     and float-rounding slack; the 1/n quantum dwarfs any ULP effect).
    # A phantom point 40 m out in grass thus rejects every candidate nearer
    # than ~1 km with plain numpy arithmetic — this was ~85 % of the reach-band
    # wall (170 M contains_xy samples per KBNA build).
    m_c = float(_sh.distance(vis_ctx, c))

    def _viable_mask(lens):
        if m_c <= 0.0:
            return None
        n_s = _np.minimum(96, _np.maximum(8, lens.astype(_np.int64)))
        u_safe = _np.maximum(
            _np.floor(n_s * (m_c / _np.maximum(lens, 1e-12))) - 1.0, 0.0)
        return ((n_s - u_safe) / n_s) >= _VIS_ON_PAV_FRAC

    def _accept_flags(chords, lens, count):
        """Per-candidate boolean of ``paved_frac >= _VIS_ON_PAV_FRAC`` — the
        only thing the accept loop consumes — computed with two bit-exact
        volume cuts over :func:`_paved_fracs`:

        * candidates failing the endpoint-margin prune are False outright;
        * the fraction test on n mid-cell samples is equivalent to the
          INTEGER test ``paved_count >= _ACCEPT_MIN_PAVED[n]`` (the table
          replicates the float ``mean() >= 0.97`` comparison exactly), so a
          chord is rejected as soon as its unpaved count exceeds
          ``n - _ACCEPT_MIN_PAVED[n]`` (≤ 3 samples at n = 96).  Stage 1
          evaluates only the first 16 mid-cells of the SAME sample set —
          enough to reject nearly every grass-crossing chord — and only the
          undecided minority pays for the remaining samples.  Same sample
          points, same total counts, same accept set.

        Returns ``(flags, needs_exact)``.  ``needs_exact`` (``m_c == 0``
        queries only, else None) marks the rejected chords for which the
        exact line-contains RESCUE could still differ from the sampled
        verdict: containment requires every chord point in the polygon's
        closure, so a rejected chord with ANY unpaved sample strictly
        outside the closure is provably not contained — and a prepared
        point-``intersects`` on each rejected chord's first unpaved sample
        (one batched C call; on-boundary ⟺ True) separates the two cases
        exactly.  Only boundary-degenerate chords (in practice none) keep
        ``needs_exact`` and pay the expensive line-contains, which on long
        walker chords measures ~2.4 ms even prepared.
        """
        viable = _viable_mask(lens)
        kept = (list(range(count)) if viable is None
                else [j for j in range(count) if viable[j]])
        flags = [False] * count
        track_exact = (m_c == 0.0)
        reject_pts = []
        if not kept:
            return flags, ([False] * count if track_exact else None)
        cc = _sh.get_coordinates(chords[kept] if len(kept) < count
                                 else chords)
        a, b = cc[0::2], cc[1::2]
        geom = vis_ctx
        _sh.prepare(geom)
        n_per = []
        for jj, j in enumerate(kept):
            L = float(lens[j])
            if L < 1e-9:
                flags[j] = True         # _paved_frac returns 1.0 for these
                n_per.append(0)
                continue
            n_per.append(min(96, max(8, int(L))))
        # Stage 1: first min(16, n) mid-cells of each kept chord, one batch.
        xs, ys, segs = [], [], []
        for jj, j in enumerate(kept):
            n = n_per[jj]
            if n == 0:
                continue
            k1 = min(16, n)
            t = (_np.arange(k1) + 0.5) / n
            xs.append(a[jj, 0] + (b[jj, 0] - a[jj, 0]) * t)
            ys.append(a[jj, 1] + (b[jj, 1] - a[jj, 1]) * t)
            segs.append((jj, j, k1))
        undecided = []
        if segs:
            hits = _sh.contains_xy(geom, _np.concatenate(xs),
                                   _np.concatenate(ys))
            off = 0
            for si, (jj, j, k1) in enumerate(segs):
                n = n_per[jj]
                h1 = hits[off:off + k1]
                paved1 = int(h1.sum())
                off += k1
                min_paved = _ACCEPT_MIN_PAVED[n]
                if (k1 - paved1) > n - min_paved:
                    if track_exact:     # first unpaved sample of the reject
                        u = int(h1.argmin())
                        reject_pts.append((j, xs[si][u], ys[si][u]))
                    continue            # early exact reject
                if k1 == n:
                    flags[j] = paved1 >= min_paved
                    if track_exact and not flags[j]:
                        u = int(h1.argmin())
                        reject_pts.append((j, xs[si][u], ys[si][u]))
                else:
                    undecided.append((jj, j, k1, paved1,
                                      (int(h1.argmin()), xs[si], ys[si])
                                      if paved1 < k1 else None))
        # Stage 2: remaining mid-cells of the undecided chords, one batch.
        if undecided:
            xs2, ys2 = [], []
            for (jj, j, k1, _p, _u1) in undecided:
                n = n_per[jj]
                t = (_np.arange(k1, n) + 0.5) / n
                xs2.append(a[jj, 0] + (b[jj, 0] - a[jj, 0]) * t)
                ys2.append(a[jj, 1] + (b[jj, 1] - a[jj, 1]) * t)
            hits = _sh.contains_xy(geom, _np.concatenate(xs2),
                                   _np.concatenate(ys2))
            off = 0
            for si, (jj, j, k1, paved1, u1) in enumerate(undecided):
                n = n_per[jj]
                h2 = hits[off:off + n - k1]
                paved = paved1 + int(h2.sum())
                off += n - k1
                flags[j] = paved >= _ACCEPT_MIN_PAVED[n]
                if track_exact and not flags[j]:
                    if u1 is not None:  # first unpaved was in stage 1
                        ui, uxs, uys = u1
                        reject_pts.append((j, uxs[ui], uys[ui]))
                    else:               # all of stage 1 paved → in stage 2
                        u = int(h2.argmin())
                        reject_pts.append((j, xs2[si][u], ys2[si][u]))
        needs_exact = None
        if track_exact:
            needs_exact = [False] * count
            if reject_pts:
                plaus = _sh.intersects(
                    geom, _sh.points([q[1] for q in reject_pts],
                                     [q[2] for q in reject_pts]))
                for k, (j, _x, _y) in enumerate(reject_pts):
                    if plaus[k]:
                        needs_exact[j] = True
        return flags, needs_exact

    gen = _cl_by_distance(c, cls, tree)
    first = None
    chunk_size = 4
    tested = 0
    while True:
        # VECTORIZED DEEP WALK (perf 2026-07-15, KBNA profile): a query still
        # rejecting after its first ~28 candidates is a long-tail walker (a
        # phantom point or a far seam station), and the per-candidate Python
        # overhead of the generator walk — not the GEOS predicates, which
        # measure ~1-8 µs each — is what made these walks ~12 ms.  The
        # expanding-ring generator yields candidates in exact global
        # ``(distance, index)`` order (see _cl_by_distance), so ONE stable
        # argsort over ONE vectorized ``shapely.distance`` call reproduces
        # that order bit-for-bit; resume at position ``tested`` and stride
        # through the tail in large blocks with the same per-candidate accept
        # rule.  Same order, same rule, same fallback ⇒ identical results.
        if tested >= 28 and tree is not None and cls_arr is not None:
            dists = _sh.distance(cls_arr, c)
            order = _np.argsort(dists, kind="stable")
            pos, stride, n_all = tested, 64, len(order)
            while pos < n_all:
                take = order[pos:pos + stride]
                chords = _sh.shortest_line(cls_arr[take], c)
                lens = _sh.length(chords)
                try:
                    acc, needs_exact = _accept_flags(chords, lens, len(take))
                except Exception:                          # pragma: no cover
                    acc = needs_exact = None
                if acc is None:                            # pragma: no cover
                    exact = _sh.contains(vis_ctx, chords)
                    for j in range(len(take)):
                        if lens[j] < 1e-6 or exact[j]:
                            return _cache_and_return(cls[int(take[j])])
                else:
                    for j in range(len(take)):
                        if (lens[j] < 1e-6 or acc[j]
                                or (needs_exact is not None
                                    and needs_exact[j]
                                    and _sh.contains(vis_ctx, chords[j]))):
                            return _cache_and_return(cls[int(take[j])])
                pos += stride
                stride = min(stride * 4, 1024)
            break                       # exhausted: fall through to fallback
        chunk = list(_islice(gen, chunk_size))
        if not chunk:
            break
        if first is None:
            first = chunk[0]
        tested += len(chunk)
        arr = _np.empty(len(chunk), dtype=object)
        for _i, _ln in enumerate(chunk):
            arr[_i] = _ln
        chords = _sh.shortest_line(arr, c)          # [foot_on_ln, c] per candidate
        lens = _sh.length(chords)
        # The accept is the FIRST candidate (distance order) that is coincident
        # (zero-length chord) OR exact-visible (contained) OR ≥ _VIS_ON_PAV_FRAC
        # paved — a plain OR per candidate, so evaluation order is free.
        # PAVED-FRACTION FIRST (perf 2026-07-15, KBNA profile): the sampled
        # fraction (≤96 ``contains_xy`` points, ~tens of µs) is ~20× cheaper
        # than an exact prepared line-contains on the huge airside union
        # (~ms), and on pavement it accepts almost every candidate the exact
        # test would.  Batch the fraction over the WHOLE chunk, then pay the
        # expensive exact test ONLY for candidates the sampling rejects — a
        # chord grazing the polygon boundary can sample a boundary point as
        # outside yet still be exactly contained, so the exact test stays as
        # the rescue.  Same accept set in the same distance order ⇒ the same
        # centerline is returned, bit-identically.
        try:
            acc, needs_exact = _accept_flags(chords, lens, len(chunk))
        except Exception:                                  # pragma: no cover
            acc = needs_exact = None
        if acc is None:                                    # pragma: no cover
            exact = _sh.contains(vis_ctx, chords)
            for j in range(len(chunk)):
                if lens[j] < 1e-6 or exact[j]:
                    return _cache_and_return(chunk[j])
        else:
            for j in range(len(chunk)):
                if (lens[j] < 1e-6 or acc[j]
                        or (needs_exact is not None and needs_exact[j]
                            and _sh.contains(vis_ctx, chords[j]))):
                    return _cache_and_return(chunk[j])
        chunk_size = min(chunk_size * 2, 512)
    return _cache_and_return(
        first if first is not None else min(
            cls, key=lambda L: L.distance(c)))


def _decrowned_anchor_seeds(layout, G, anchor_elev):
    """Lift CROWNED runway-edge anchor values into the ONE uncrowned profile
    space the reach band is documented to solve in.

    The runway-join anchors are VALUE-DERIVED from the EMITTED runway edge
    (2026-07-16 edge-anchor ruling), so on a wide runway each carries the
    profile MINUS the transverse crown drop (``RUNWAY_CROWN_TRANSVERSE`` ×
    half-width).  The band, however, is the in-solve profile field and its
    consumer ``grade_graph_validate.route_band_violations`` de-crowns each
    vertex by ``+crown_drop`` before comparing — the ONE uncrowned space the
    space invariant declares.  Adding the crown drop back at each anchor's
    own position puts the seed in that same space (``crown_drop_at`` returns
    0.0 with no crown field, so non-crowned airports stay byte-identical).

    ``anchor_elev`` is ``{node_index: crowned_elev}``; returns a new dict with
    the same keys and de-crowned values."""
    from auto_patch.crown import crown_drop_at
    out = {}
    for k, ae in anchor_elev.items():
        p = G.pos.get(k)
        out[k] = float(ae) + (crown_drop_at(layout, p[0], p[1]) if p else 0.0)
    return out


def spine_value_fields(layout, G):
    """The ROUTE-METRIC reach value fields on the unified spine graph — the
    ONE producer of reach VALUE in the tree (spec rod-compose-and-band-
    single-source §B).

    ``ceiling[i] = min over runway anchors a ( value_a + Σ per-edge budget
    along the cheapest NON-SERVICE spine route a→i )``; the floor mirrors
    with ``−``.  This is the pair-pricing oracle's and the seats'
    reachability semantic verbatim: *"airside reachability never rides
    service roads or groundside; the taxi route graph is the metric"*
    (owner ruling 2026-07-29).  It is a ROUTE metric — reach travels along
    routes, never across the paved AREA — which is why the raster grid may
    only accelerate LOOKUPS (nearest attachment + the local off-route leg)
    and must never carry the value itself.

    The anchor seeds are de-crowned into the ONE uncrowned profile space
    the band lives in (:func:`_decrowned_anchor_seeds`).  Edges woven from
    a SERVICE-road centerline are skipped
    (``UnifiedGraph.service_spine_pairs``, gate
    ``config.REACH_NO_SERVICE_SPINES`` — the LAW gate, which stays); a node
    reachable ONLY through service paths gets no entry and reads as off-net,
    the same policy as any unanchored fragment.

    Value-seeded multi-source Dijkstra per direction (perf 2026-07-04): the
    per-anchor passes were only ever consumed as ``min over anchors (ae +
    dist)`` / ``max over anchors (ae − dist)``, so ONE pass per field gives
    the same answer by commutation, with the same float expression.

    Returns ``(ceiling, floor)`` as ``{node_index: value}`` (both fields
    cover exactly the anchor-reachable non-service node set)."""
    if not getattr(G, "runway_anchor", None) or not getattr(G, "spine_adj",
                                                            None):
        return {}, {}
    from auto_patch.config import REACH_NO_SERVICE_SPINES
    # SEED COMPLETENESS (standing law): the field's seed set is
    # ``G.runway_anchor`` UNION the on-spine ``seed_rwy_seam`` hard truth
    # the solve publishes.  ``setdefault`` — a genuine runway-JOIN anchor
    # at a shared node keeps datum authority (the same precedence the EAT
    # anchor-rect registration uses).  A context that has not published the
    # hard-truth map yet (the pre-solve construct band) contributes an
    # empty extra map, so ``anchor_elev`` is ``G.runway_anchor`` with its
    # insertion order intact there.
    anchor_elev = dict(G.runway_anchor)
    for _hi, _hv in _hard_truth_spine_seeds(layout, G).items():
        anchor_elev.setdefault(_hi, float(_hv))
    anchor_seeds = _decrowned_anchor_seeds(layout, G, anchor_elev)
    svc_pairs = (getattr(G, "service_spine_pairs", None) or set()
                 if REACH_NO_SERVICE_SPINES else set())

    def _field(sign):
        best: dict = {}
        # ROUTE DISTANCE per node, write-only: the budget-metric length of
        # the winning route (spec kill-half §3 — the loud error names the
        # route distances, so the field that already has them records
        # them instead of a second pass re-deriving them).  No value is
        # read from it here; ``best`` is byte-identical either way.
        dist: dict = {}
        # WHICH ANCHOR WON, write-only (fix-2 lane A): the field already
        # carries the anchor's VALUE through the frontier, so the anchor's
        # own node costs one tuple slot to carry with it.  Nothing here
        # reads it; it is the provenance the loud band error and the
        # apron-terrace CERTIFICATE quote, so neither has to re-run a
        # Dijkstra to name the anchor pair it is talking about
        # (``single-pass-principle``).  ``src`` sits between ``ae`` and
        # ``u`` in the heap key: two entries that tie through ``ae``
        # necessarily tie through ``dd`` too (``key = ae ± dd``), so they
        # write identical values and the extra tie-break cannot move a
        # number.
        via: dict = {}
        pq = [((ae if sign > 0 else -ae), 0.0, ae, k, k)
              for (k, ae) in anchor_seeds.items()]
        heapq.heapify(pq)
        while pq:
            _key, dd, ae, src, u = heapq.heappop(pq)
            if u in best:
                continue
            best[u] = (ae + dd) if sign > 0 else (ae - dd)
            dist[u] = dd
            via[u] = src
            for (v, budget) in G.spine_adj.get(u, ()):
                if v in best:
                    continue
                if svc_pairs and ((u, v) if u < v else (v, u)) in svc_pairs:
                    continue
                nd = dd + budget
                heapq.heappush(
                    pq, (((ae + nd) if sign > 0 else -(ae - nd)),
                         nd, ae, src, v))
        return best, dist, via

    ceiling, ceil_dist, ceil_via = _field(+1)
    floor, floor_dist, floor_via = _field(-1)
    _record_anchor_provenance(layout, anchor_seeds, ceil_via, ceil_dist,
                              floor_via, floor_dist)
    _record_band_inversions(layout, G, ceiling, floor, ceil_dist, floor_dist,
                            hard_truth=_hard_truth_spine_seeds(layout, G),
                            ceil_via=ceil_via, floor_via=floor_via,
                            anchor_seeds=anchor_seeds,
                            anchor_law=_anchor_law_values(layout, G,
                                                          anchor_seeds),
                            anchor_cifp=_anchor_cifp_envelopes(layout, G,
                                                               anchor_seeds))
    return ceiling, floor


def service_mouths(layout, G, ceiling=None, floor=None,
                   airside_band=None) -> dict:
    """THE MOUTHS — ``{node: (floor, ceiling)}`` (RULINGS 2026-08-06,
    "Service-road mouths seat like apron-edge buildings").

    A MOUTH is a node where a SERVICE-road spine edge meets the airside
    route network: an endpoint of a ``UnifiedGraph.service_spine_pairs``
    edge that the airside value field (``spine_value_fields`` — service
    -excluded, so its values are airside law by construction) reaches.

    Its band IS the airside band there.  That is the owner's ruling in
    one line: the mouth is *"seated where it's feasible for the airside
    apron to meet it, then the road and everything else is graded per its
    law"* — airside wins the seat, exactly as an apron-edge building's
    frontage is seated by the apron it fronts.  Nothing is minted here:
    the interval is READ from the airside field, so no groundside value
    can enter an airside constraint set through this door (receiver-only,
    structurally).

    ``REACH_NO_SERVICE_SPINES`` is INVERTED here rather than disabled: the
    airside field still never rides a service pair (that call is
    untouched), and this reads only its endpoints.  Direction, not
    deletion.

    ``airside_band`` — THE APRON-EDGE MOUTH (cycle 8, measured).  The
    VALUE FIELD covers only nodes a taxi centerline strung, so a road that
    meets airside pavement AWAY from a centerline — which is the normal
    case: measured at the cycle-8 baseline, KCLT had 117 service spine
    pairs and ZERO field-covered endpoints — has no field value anywhere
    on it and mints no mouth at all.  The owner's ruling does not say "at
    a spine node"; it says the mouth is *"seated where it's feasible for
    the airside apron to meet it"*, and THE AIRSIDE BAND
    (:func:`reach_band_unified`, the same band the solve and the validator
    use) is exactly that interval.  So a field-less endpoint asks the
    band, and the band's own domain decides: its propagation mask is
    AIRSIDE pavement + pads and it answers ``None`` past its off-net
    radius, so only an endpoint genuinely at/near airside pavement — an
    apron-edge contact — becomes a mouth.  Read-only in both directions:
    no groundside value enters the band or any airside constraint set.
    ``None`` ⇒ field-only mouths, i.e. the pre-clause behaviour.

    PROBE GATE, DEFAULT OFF — ``O4_PROBE_NO_MOUTHS=1`` WITHHOLDS every
    mouth seat, so nothing groundside can reach a band from airside (the
    cycle-9 mouth knife, committed instead of living in a dirty tree).
    """
    if os.environ.get("O4_PROBE_NO_MOUTHS") == "1":
        return {}
    if ceiling is None or floor is None:
        ceiling, floor = spine_value_fields(layout, G)
    pos = getattr(G, "pos", None) or {}
    out: dict = {}
    for pair in (getattr(G, "service_spine_pairs", None) or ()):
        for m in pair:
            if m in out:
                continue
            if m in ceiling and m in floor:
                out[m] = (float(floor[m]), float(ceiling[m]))
            elif airside_band is not None and m in pos:
                b = airside_band(pos[m][0], pos[m][1])
                if b is not None:
                    out[m] = (float(b[0]), float(b[1]))
    return out


def groundside_reach_band(layout, G, offnet_radius_m=None, cap=None):
    """THE GROUNDSIDE half of the ONE band — ``band(x, y) -> (floor,
    ceiling) | None`` (RULINGS 2026-08-06, "ONE graph: groundside joins
    the route graph").

    NOT A SECOND GRAPH AND NOT A SECOND METRIC.  It is the same
    ``spine_value_fields`` route metric on the same ``UnifiedGraph``, run
    in the other DIRECTION:

    1. the AIRSIDE field solves first, untouched (service-excluded — the
       standing law, and the reason airside can never be pulled by any of
       this);
    2. its values at the MOUTHS (:func:`service_mouths`) seed a second
       multi-source Dijkstra that rides the spine graph OUTWARD from
       there, at the SAME per-edge budgets the graph already carries —
       which for a service centerline is its own 8 % cap (``config.
       PAVEMENT_MAX_GRADE['service_road']``), the "built the same as
       taxiways with a higher cap" half of the ruling;
    3. a point is answered by the nearest node that has a band — airside
       -valued nodes included, since a lot welded to an apron is coupled
       to it — with the local off-route leg priced at the GROUNDSIDE cap
       (5 %), the lawful chord across the lot's own surface.  Beyond
       ``offnet_radius_m`` there is no coupling and the answer is
       ``None``: that is the ruling's "truly disconnected … just gets
       left at DEM" and it is the SAME predicate the census adjudicates
       with (the emitted sidecar carries this function's answer, never a
       re-derivation).

    AIRSIDE WINS where both fields cover a node: the airside interval is
    the law there and the outward field may only be consulted where the
    airside field has nothing to say.

    The DEM is not read anywhere in here.  It chooses WHERE INSIDE the
    returned interval a vertex seats, which is the seat's job, never the
    band's.
    """
    from auto_patch.config import (GROUNDSIDE_BAND_OFFNET_RADIUS_M,
                                   GROUNDSIDE_MAX_GRADE)
    radius = float(GROUNDSIDE_BAND_OFFNET_RADIUS_M if offnet_radius_m is None
                   else offnet_radius_m)
    leg_cap = float(GROUNDSIDE_MAX_GRADE if cap is None else cap)
    pos = getattr(G, "pos", None) or {}
    adj = getattr(G, "spine_adj", None) or {}
    if not pos:
        return None
    ceiling, floor = spine_value_fields(layout, G)
    # THE AIRSIDE BAND, for the apron-edge mouths the value field cannot
    # answer (see :func:`service_mouths`).  Read-only, single source — the
    # same band the solve and the validator consume.  A failure degrades to
    # field-only mouths rather than killing the groundside band build.
    try:
        airside_band = reach_band_unified(layout, G)
    except Exception:                                       # pragma: no cover
        airside_band = None
    mouths = service_mouths(layout, G, ceiling, floor,
                            airside_band=airside_band)

    def _outward(seeds, sign):
        """min-plus (sign +1) / max-plus (−1) field from the mouths."""
        best: dict = {}
        pq = [((v if sign > 0 else -v), 0.0, v, k)
              for (k, v) in seeds.items()]
        heapq.heapify(pq)
        while pq:
            _key, dd, ae, u = heapq.heappop(pq)
            if u in best:
                continue
            best[u] = (ae + dd) if sign > 0 else (ae - dd)
            for (v, budget) in adj.get(u, ()):
                if v in best:
                    continue
                nd = dd + budget
                heapq.heappush(pq, (((ae + nd) if sign > 0 else -(ae - nd)),
                                    nd, ae, v))
        return best

    gs_ceiling = _outward({k: v[1] for k, v in mouths.items()}, +1)
    gs_floor = _outward({k: v[0] for k, v in mouths.items()}, -1)

    # ONE source table: the airside field where it exists (airside is
    # king), the mouth-propagated field everywhere else it reached.
    src: dict = {}
    for i, c in gs_ceiling.items():
        f = gs_floor.get(i)
        if f is not None and i in pos:
            src[i] = (f, c)
    for i, c in ceiling.items():
        f = floor.get(i)
        if f is not None and i in pos:
            src[i] = (f, c)
    if not src:
        return None

    # Uniform-grid index at the off-net radius: a query scans its own cell
    # and the eight around it, which covers every source within ``radius``.
    cell = max(radius, 1.0)
    grid: dict = {}
    for i, (f, c) in src.items():
        x, y = pos[i]
        grid.setdefault((int(math.floor(x / cell)),
                         int(math.floor(y / cell))), []).append((x, y, f, c))

    def band(x, y):
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        best = None
        bd = radius
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py, f, c) in grid.get((cx + dx, cy + dy), ()):
                    d = math.hypot(px - x, py - y)
                    if d <= bd:
                        bd, best = d, (f, c)
        if best is None:
            return None
        slack = leg_cap * bd
        return (best[0] - slack, best[1] + slack)

    band.sources = len(src)                 # type: ignore[attr-defined]
    band.mouths = len(mouths)               # type: ignore[attr-defined]
    band.offnet_radius_m = radius           # type: ignore[attr-defined]
    return band


def _record_anchor_provenance(layout, anchor_seeds, ceil_via, ceil_dist,
                              floor_via, floor_dist):
    """Stash WHICH ANCHOR authored each node's ceiling and floor.

    Write-only, last call wins — the same discipline as
    :func:`_record_band_inversions`.  ``layout._band_anchor_provenance``:

        {"anchor_value": {anchor_node: seed_elev},
         "ceiling": {node: (anchor_node, route_budget_m)},
         "floor":   {node: (anchor_node, route_budget_m)}}

    THE POINT.  An envelope shortfall is always a statement about an
    ANCHOR PAIR and the route between them — ``v_a − v_b > d(a,b)`` — and
    without this map every consumer that wants to name that pair has to
    re-run the two Dijkstras it was just handed the answer of.  Both the
    loud band error and the apron-terrace certificate read it."""
    try:
        layout._band_anchor_provenance = {
            "anchor_value": {int(k): float(v)
                             for (k, v) in anchor_seeds.items()},
            "ceiling": {int(u): (int(a), float(ceil_dist.get(u, 0.0)))
                        for (u, a) in ceil_via.items()},
            "floor": {int(u): (int(a), float(floor_dist.get(u, 0.0)))
                      for (u, a) in floor_via.items()},
        }
    except (AttributeError, TypeError, ValueError):         # pragma: no cover
        pass


def _hard_truth_spine_seeds(layout, G):
    """``{node: hard_elev}`` — the on-spine ``seed_rwy_seam`` HARD TRUTH
    (standing law; see the BAND-SEED COMPLETENESS block above).  ``{}`` in
    any context that has not published the map (the pre-solve construct
    band runs BEFORE the solve seeds elevations, so it honestly keeps the
    runway-anchor-only field it has always had).

    The publisher is ``route_profile.solve`` — the ONE place that knows
    which nodes ``_seed_elevations`` hardened; nothing is re-derived here
    (``single-pass-principle``).

    CANONICAL-IDENTITY JOIN (debug lane A 2026-08-05).  The published map
    is keyed by CANONICAL POINT, and this resolves it against ``G.pos``
    through the SAME registry, so the value lands on the node it was
    measured at no matter how many times the node list has been rebuilt
    since.  It used to be keyed by the solve's node INDEX, which is valid
    only inside the one ``_build_node_list`` call that assigned it: every
    post-solve consumer rebuilds that list on a layout that has since
    grown, and the seeds then landed on unrelated nodes (SPJC: 448 of 455,
    |Δ| up to 16.96 m — 795 inverted band nodes and 1,208 spurious
    route-band violations).  A registry-less caller (the hermetic tests)
    joins on the raw position tuple, which is exact there by
    construction."""
    truth = getattr(layout, "_seed_hard_truth_values", None) or {}
    spine = getattr(G, "spine_adj", None) or {}
    if not truth or not spine:
        return {}
    cps = getattr(layout, "canonical_points", None)
    pos = getattr(G, "pos", None) or {}
    out: dict = {}
    for i in spine:
        p = pos.get(i)
        if p is None:
            continue
        px, py = float(p[0]), float(p[1])
        v = None
        if cps is not None:
            try:
                k = cps.get(px, py)
            except Exception:                              # pragma: no cover
                k = None
            if k is not None:
                v = truth.get(k)
        if v is None:
            v = truth.get((px, py))
        if v is None:
            continue
        out[int(i)] = float(v)
    return out


def _anchor_station_owner(G, profiles, anchor_seeds, eligible):
    """``{anchor_node: (ref, t)}`` — which runway profile owns each anchor
    station, and at what axis fraction.

    ONE authority for "which runway is this anchor a station of", shared by
    :func:`_anchor_law_values` and :func:`_anchor_cifp_envelopes`
    (consult-before-create: the second reader extends the first's geometry
    rather than copying it).  ``eligible`` is the ORDERED list of refs the
    caller will accept; the nearest in LATERAL distance wins, and ties
    resolve in that order exactly as the single-reader version did.

    A JOIN anchor sits at the runway EDGE, so the lateral test allows the
    ring's own half-width plus a contact margin."""
    pos = getattr(G, "pos", None) or {}
    out: dict = {}
    for k in anchor_seeds:
        pt = pos.get(k)
        if pt is None:
            continue
        px, py = float(pt[0]), float(pt[1])
        best = None                       # (lateral, ref, t)
        for ref in eligible:
            p = profiles.get(ref) or {}
            ax, ay = p["axis_a"]
            dx, dy = p["axis_d"]
            len2 = float(p["axis_len2"])
            if len2 <= 0.0:
                continue
            t = ((px - ax) * dx + (py - ay) * dy) / len2
            if not (-0.02 <= t <= 1.02):
                continue
            axis_len = math.sqrt(len2)
            lateral = abs(-(px - ax) * (dy / axis_len)
                          + (py - ay) * (dx / axis_len))
            if lateral > float(p.get("half_width_m") or 0.0) + 40.0:
                continue
            if best is None or lateral < best[0]:
                best = (lateral, ref, min(1.0, max(0.0, t)))
        if best is not None:
            out[int(k)] = (best[1], best[2])
    return out


def _anchor_cifp_envelopes(layout, G, anchor_seeds):
    """``{anchor_node: (lo, hi, ref)}`` — the WORLD-INVARIANT band the CIFP
    thresholds alone force at each runway anchor's own station.

    WHY THIS EXISTS (cycle-5 canyon-flex spec, fix 1 — a (d) BROKEN
    INSTRUMENT).  :func:`_anchor_law_values` reports the profile's LAW LINE,
    which the cycle-4 ruling correctly defines as anchored ∪ flex-applied
    stations ("anything within the law is legal by definition").  That
    ruling stands — but a law line so defined is FULL of world-dependent
    content: flex-applied targets are computed from an envelope seeded off
    other runways' DEM-seated surfaces, seam anchors ARE the DEM, and
    crossing anchors are the partner runway's emitted surface.  So the
    "ride" that line reports is only the DEM-follow decoration BETWEEN the
    anchors, and the band error nevertheless printed "the CIFP thresholds
    themselves do not reach each other … the DEM cannot be blamed" for a
    HECA anchor pair measured 5.31 m / 6.24 m DEM-driven (the plateau world
    carries the same pair's spread with 3.13 m of slack on IDENTICAL CIFP
    thresholds — c5tip report, Job 2).

    WHAT IS WORLD-INVARIANT, by construction: the CIFP threshold
    elevations (``profile['cifp_pins']``, captured at the emit site before
    any seam shift), the station geometry (fractions, axis length) and the
    runway's OWN law caps (``grade_law.runway_profile_law``, resolved from
    code number / letter / ruleset — geometry and jurisdiction, never
    terrain).  The envelope is

        lo = max_p (e_p − budget(t, t_p)),   hi = min_p (e_p + budget(t, t_p))

    over the CIFP pins ``p``, with ``budget`` the per-segment law integrated
    along the span (the same ``_lawful_ramp_budget`` the flex prices with).
    Any value inside ``[lo, hi]`` is reachable from the CIFP pins under
    runway grade law; a value outside is not.

    PRICED AT THE LAW CAPS, not at the profile's as-solved caps.  A profile
    whose end zone ESCALATED above the law's 0.8 % escalated because of
    world-dependent anchors (seams, crossings), so folding that escalation
    in would let terrain widen the "world-invariant" envelope.  The
    consequence is a conservative envelope near the thresholds; the reader
    names the escalation when one exists.

    ``{}`` when no profile carries CIFP pins (a synthetic layout, or a
    build whose profiles predate the pins), so a caller without them makes
    no CIFP claim at all rather than a false one."""
    from auto_patch.runway_redistribute import (_lawful_ramp_budget,
                                                _profile_law)
    from auto_patch.config import RUNWAY_END_FRACTION
    profiles = getattr(layout, "_runway_redistributed_profiles", None) or {}
    pos = getattr(G, "pos", None) or {}
    if not profiles or not pos:
        return {}
    eligible = [ref for ref, p in profiles.items()
                if p and len(p.get("cifp_pins") or ()) >= 1]
    if not eligible:
        return {}
    out: dict = {}
    for k, (ref, t) in _anchor_station_owner(
            G, profiles, anchor_seeds, eligible).items():
        p = profiles[ref]
        axis_len = math.sqrt(float(p["axis_len2"]))
        # The runway's OWN law, through the ONE resolver that reads it off
        # the profile (``_profile_law``) — never a second copy, and never
        # the escalated as-solved caps.
        _law = _profile_law(p)
        cap_kw = dict(
            grade_cap=_law["max_grade"],
            end_grade_cap=_law["end_grade"],
            end_fraction=RUNWAY_END_FRACTION,
            threshold_strict_cap=None,
            threshold_strict_fraction=0.0)
        if cap_kw["grade_cap"] <= 0.0:
            continue
        lo, hi = -float("inf"), float("inf")
        for (pt, pe) in (p.get("cifp_pins") or ()):
            budget = _lawful_ramp_budget(t, float(pt), axis_len, cap_kw)
            lo = max(lo, float(pe) - budget)
            hi = min(hi, float(pe) + budget)
        if lo == -float("inf") or hi == float("inf"):
            continue
        out[int(k)] = (float(lo), float(hi), str(ref))
    return out


def _anchor_law_values(layout, G, anchor_seeds):
    """``{anchor_node: law_baseline_value}`` — what LAW alone puts at each
    runway anchor's own station, with the DEM-follow ride removed.

    WHY THIS EXISTS (fix-3 lane A, measured at HECA).  A runway-join
    anchor value is sampled off the EMITTED runway surface, and that
    surface's interior is a DEM-FOLLOW SEED: every station that is not a
    CIFP threshold / seam / crossing anchor is set to ``clamp(DEM, base ±
    min(RUNWAY_DEM_FOLLOW_LAW_BAND_M, ½·K·d²))`` in
    ``runway_segments.generate_patch_osm``.  So the same station reads up
    to ``2 × 10 m`` apart in two constant-DEM worlds (HECA measured:
    exactly +20.000 m on 71 of 75 stations of 05C/23C), and the band
    seeded from it inherits every one of those metres as if it were law.

    The band error is the ONE place that difference has to be legible: a
    shortfall that is law (the CIFP thresholds genuinely do not reach each
    other within the route budget) needs a metric / cap / topology ruling,
    while a shortfall the DEM ride ADDED needs neither.  Without this the
    two are one number and the reader cannot tell them apart — HECA's
    canyon failure reads as 12.84 m of law defect when 6.00 m of it is
    ride.

    THE LAW LINE IS ANCHORED ∪ FLEX-APPLIED (spec-author ruling, cycle 4;
    owner ruling 2026-08-05 "Runway flex: the LAW is the only bound" —
    "anything within the law is legal by definition", and
    ``docs/specs/cycle4-anchor-law-spec.md`` requirement 1 names
    "flex-applied targets, which are lawful hard moves" as part of the law
    line).  So the baseline is the profile interpolated over its ANCHORED
    stations, flex-minted ones INCLUDED: a flexed station is law that has
    moved, not authority that has evaporated, and the ride this function
    reports is ONLY the DEM-follow decoration between the anchors.

    WHAT THIS REPLACES, and why it was a (d) BROKEN INSTRUMENT.  The
    original cut (``e5c8443``) EXCLUDED ``flex_minted`` stations, which was
    right for its diagnostic purpose — isolating the PRE-FLEX law to prove
    the ride mechanism existed — and wrong as a standing reader: it books
    lawful flex displacement as "DEM-follow ride".  Measured at HECA canyon
    (cycle-4 lane, after the join stations became zero-band): two anchors
    read −1.461 m and −2.735 m of "ride" in a world where the DEM is
    10 000 m and can therefore only push a value UP — the deviations are
    NEGATIVE, so they cannot be DEM-follow at all; they are the flex's own
    lawful move (551.22 m drained across 05C/23C, 05L/23R, 05R/23L in that
    build), and two anchor pairs were consequently mis-classified as
    "LAW ALONE IS FEASIBLE".

    NOT WORLD-INVARIANT, and that is the point of the companion reader
    (cycle-5 fix 1).  The law line is anchored ∪ flex-applied, and both
    seam anchors and flex-applied targets are world-DEPENDENT — so this
    function's output legitimately moves between two constant-DEM worlds
    and may never carry a verdict about the CIFP thresholds.  The
    world-invariant half is :func:`_anchor_cifp_envelopes`; the band error
    prints both and blames CIFP only on the latter.

    ``{}`` whenever the profiles are absent, so a caller without them is
    unchanged.
    """
    profiles = getattr(layout, "_runway_redistributed_profiles", None) or {}
    pos = getattr(G, "pos", None) or {}
    if not profiles or not pos:
        return {}
    lawful: dict = {}
    for ref, p in profiles.items():
        if not p:
            continue
        fr = p.get("fractions") or ()
        el = p.get("elevs") or ()
        an = p.get("anchored") or ()
        pairs = [(float(fr[i]), float(el[i])) for i in range(len(fr))
                 if i < len(an) and an[i]]
        if len(pairs) >= 2:
            lawful[ref] = sorted(pairs)
    if not lawful:
        return {}

    def _interp(pairs, t):
        if t <= pairs[0][0]:
            return pairs[0][1]
        if t >= pairs[-1][0]:
            return pairs[-1][1]
        for k in range(len(pairs) - 1):
            t0, e0 = pairs[k]
            t1, e1 = pairs[k + 1]
            if t0 <= t <= t1:
                if t1 - t0 < 1e-12:
                    return e0
                return e0 + (t - t0) / (t1 - t0) * (e1 - e0)
        return pairs[-1][1]

    out: dict = {}
    for k, (ref, t) in _anchor_station_owner(
            G, profiles, anchor_seeds, list(lawful)).items():
        out[int(k)] = float(_interp(lawful[ref], t))
    return out


def _record_band_inversions(layout, G, ceiling, floor, ceil_dist,
                            floor_dist, hard_truth=None, ceil_via=None,
                            floor_via=None, anchor_seeds=None,
                            anchor_law=None, anchor_cifp=None):
    """Stash THIS call's INVERTED rows on the layout (spec kill-half §3,
    extended by the seed-fix round §2).

    Two classes, one law:

    * ``floor_above_ceiling`` — the original: the two value fields cross,
      so no elevation satisfies both.
    * ``floor_above_own_hard_value`` (§2) — the band FLOORS a node above
      its OWN hard truth.  A band seeded from the runway anchors cannot
      lawfully demand that a runway/seam node sit above the runway value
      it is pinned at; that is one instrument contradicting itself, and
      it is invisible to the first class whenever the ceiling happens to
      sit higher still (HECA today: 4818 +2.344 m and 2863 +1.522 m read
      as perfectly ordered bands).  ``hard_truth`` empty (gate off, or a
      caller with no published hard set) ⇒ the class is never recorded ⇒
      behaviour identical.

    Last call wins — ``assert_no_final_band_inversion`` reads the FINAL
    build's field.  Write-only: nothing in the solve reads it back, so a
    build that never reaches the assertion behaves exactly as before."""
    rows = []
    if ceiling and floor:
        pos = getattr(G, "pos", None) or {}
        seeds = anchor_seeds or {}
        laws = anchor_law or {}
        cifp = anchor_cifp or {}
        cvia = ceil_via or {}
        fvia = floor_via or {}
        for node, lo in floor.items():
            hi = ceiling.get(node)
            if hi is None:
                continue
            deficit = lo - hi
            if deficit <= 0.0:
                continue
            xy = pos.get(node)
            # THE CONTRADICTORY ANCHOR PAIR.  ``floor > ceiling`` at a node
            # is never a property OF the node: it says the floor's author
            # ``a`` and the ceiling's author ``b`` are further apart in
            # VALUE than the route between them can carry, and the deficit
            # IS that shortfall.  Naming a/b turns "3 169 nodes inverted"
            # into one sentence about two anchors and one route.
            fa = fvia.get(node)
            ca = cvia.get(node)
            rows.append({
                "node": node,
                "klass": "floor_above_ceiling",
                "floor": float(lo),
                "ceiling": float(hi),
                "deficit_m": float(deficit),
                "floor_route_m": float(floor_dist.get(node, 0.0)),
                "ceil_route_m": float(ceil_dist.get(node, 0.0)),
                "floor_anchor": (None if fa is None else int(fa)),
                "ceil_anchor": (None if ca is None else int(ca)),
                "floor_anchor_value": (None if fa is None
                                       else float(seeds.get(fa, float("nan")))),
                "ceil_anchor_value": (None if ca is None
                                      else float(seeds.get(ca, float("nan")))),
                # THE LAW HALF of each anchor value (``_anchor_law_values``):
                # the same station with the DEM-follow ride removed.  None
                # for an anchor no runway profile owns (seam pin, seat).
                "floor_anchor_law": (None if fa is None
                                     else laws.get(int(fa))),
                "ceil_anchor_law": (None if ca is None
                                    else laws.get(int(ca))),
                # THE WORLD-INVARIANT HALF (``_anchor_cifp_envelopes``):
                # ``(lo, hi, ref)`` — the band the CIFP thresholds alone
                # force at this anchor's station under runway grade law.
                # None for an anchor no runway profile owns, or a build
                # whose profiles carry no CIFP pins: then no CIFP claim
                # is made at all.
                "floor_anchor_cifp": (None if fa is None
                                      else cifp.get(int(fa))),
                "ceil_anchor_cifp": (None if ca is None
                                     else cifp.get(int(ca))),
                "x": (None if xy is None else float(xy[0])),
                "y": (None if xy is None else float(xy[1])),
            })
        for node, own in (hard_truth or {}).items():
            lo = floor.get(node)
            if lo is None:
                continue
            deficit = lo - float(own)
            if deficit <= 0.0:
                continue
            xy = pos.get(node)
            rows.append({
                "node": node,
                "klass": "floor_above_own_hard_value",
                "floor": float(lo),
                "ceiling": float(ceiling.get(node, float(own))),
                "own_hard_value": float(own),
                "deficit_m": float(deficit),
                "floor_route_m": float(floor_dist.get(node, 0.0)),
                "ceil_route_m": float(ceil_dist.get(node, 0.0)),
                "x": (None if xy is None else float(xy[0])),
                "y": (None if xy is None else float(xy[1])),
            })
        rows.sort(key=lambda r: -r["deficit_m"])
    try:
        layout._final_band_inversions = rows
        layout._final_band_node_count = len(ceiling)
    except AttributeError:                                 # pragma: no cover
        pass


def assert_no_final_band_inversion(layout, icao="",
                                   tol=FINAL_BAND_INVERSION_TOL_M):
    """POST-SOLVE LAW (spec kill-half §3) — ungated, it IS the law.

    Raises :class:`BandInversionError` naming every node whose FINAL
    reach band is inverted by more than ``tol`` metres, with its floor,
    ceiling, deficit and both route distances.  Returns the number of
    sub-materiality inversions it tolerated (a PASS-with-residual count,
    per the convergence guards' materiality floor)."""
    rows = list(getattr(layout, "_final_band_inversions", None) or [])
    if not rows:
        return 0
    over = [r for r in rows if r["deficit_m"] > tol]
    if not over:
        return len(rows)
    lines = [
        f"{icao or 'airport'}: the FINAL reach band is INVERTED at "
        f"{len(over)} node(s) of "
        f"{int(getattr(layout, '_final_band_node_count', 0) or 0)} "
        f"band-covered node(s) "
        f"(floor − ceiling > {tol:g} m).  A real airport with real "
        f"thresholds has a lawful surface (docs/RULINGS.md, "
        f"feasibility-is-guaranteed): this is a law defect to attribute — "
        f"a wrong metric, a wrong anchor value, a wrong role/cap or a "
        f"false topology — never a region to quarantine.",
        # FRAME STAMP (RULINGS 2026-08-06 binding point 3).  Both counts
        # above and every node id below are in ONE node space; the
        # values are in the band's own de-crowned profile space.
        f"  {instrument_frame(layout, BAND_NODE_SPACE)}",
    ]
    # THE ANCHOR PAIRS, FIRST.  Every inverted node is downstream of ONE
    # anchor pair whose values are further apart than the route between
    # them can carry; rolling the nodes up by that pair turns a wall of
    # coordinates into the two anchors and the one route budget that
    # actually have to be attributed.
    pairs: dict = {}
    for r in over:
        fa, ca = r.get("floor_anchor"), r.get("ceil_anchor")
        if fa is None or ca is None:
            continue
        key = (int(fa), int(ca))
        row = pairs.setdefault(key, {"n": 0, "worst": 0.0, "r": r})
        row["n"] += 1
        if r["deficit_m"] > row["worst"]:
            row["worst"] = r["deficit_m"]
            row["r"] = r
    if pairs:
        lines.append(f"  contradictory ANCHOR PAIR(S): {len(pairs)}")
        for (fa, ca), row in sorted(pairs.items(),
                                    key=lambda kv: -kv[1]["worst"])[:6]:
            r = row["r"]
            fv = r.get("floor_anchor_value")
            cv = r.get("ceil_anchor_value")
            spread = (None if (fv is None or cv is None) else abs(fv - cv))
            budget = r["floor_route_m"] + r["ceil_route_m"]
            lines.append(
                f"    anchors {fa} ({'?' if fv is None else f'{fv:.3f}'} m) "
                f"vs {ca} ({'?' if cv is None else f'{cv:.3f}'} m): value "
                f"spread {'?' if spread is None else f'{spread:.3f}'} m "
                f"over a route budget of {budget:.3f} m ⇒ shortfall "
                f"{row['worst']:.4f} m at {row['n']} node(s)")
            # THE LAW / RIDE SPLIT.  What of this shortfall survives with
            # the runway profiles' DEM-FOLLOW SEED removed (see
            # ``_anchor_law_values``)?  This half is REPORTED, never
            # verdicted: its law line is anchored ∪ flex-applied, which is
            # lawful (cycle-4 ruling) and world-DEPENDENT, so a remainder
            # here says nothing about the CIFP thresholds.  The verdict
            # belongs to the CIFP-forced half below (cycle-5 fix 1).
            fl = r.get("floor_anchor_law")
            cl = r.get("ceil_anchor_law")
            if fl is not None or cl is not None:
                fl_v = fv if fl is None else fl
                cl_v = cv if cl is None else cl
                if fl_v is not None and cl_v is not None:
                    law_spread = abs(fl_v - cl_v)
                    law_short = law_spread - budget
                    lines.append(
                        f"      LAW-LINE half (anchored ∪ flex-applied; "
                        f"WORLD-DEPENDENT, no verdict): anchors "
                        f"{'?' if fl is None else f'{fl:.3f}'} m vs "
                        f"{'?' if cl is None else f'{cl:.3f}'} m "
                        f"(DEM-follow ride "
                        f"{0.0 if fl is None else fv - fl:+.3f} / "
                        f"{0.0 if cl is None else cv - cl:+.3f} m) ⇒ law "
                        f"spread {law_spread:.3f} m, remainder "
                        f"{law_short:+.4f} m")
            # ── THE CIFP-FORCED HALF — THE ONLY CIFP VERDICT (cycle-5
            # canyon-flex spec, fix 1) ────────────────────────────────
            # ``forced`` is WORLD-INVARIANT by construction: the CIFP
            # threshold elevations, the station geometry and the runway's
            # own law caps.  ``lo_f − hi_c`` is the SMALLEST value spread
            # the CIFP pins can be made to hold at these two stations
            # under runway grade law.  The BUDGET it is compared against
            # is not: it is a route metric on the solved graph, so the
            # SHORTFALL is a mixed quantity and the line says so
            # (cycle-7.5 sweep, RULINGS 2026-08-06 binding point 3).
            # When the forced spread FITS the budget, a lawful pair of
            # profiles closes this route and CIFP forces nothing — the
            # remainder is world-dependent content (seating, flex-applied
            # targets, seam / crossing anchors).  THE REPORT STOPS AT
            # THAT NUMBER: naming which verdict class the remainder falls
            # in is the law layer's call, not report code's (binding
            # point 2; the "verdict (a) BUG" clause that stood here was
            # exactly such an interpretation).  This whole half replaces
            # a sentence that blamed CIFP for a spread measured 5.31 m
            # DEM-driven (c5tip Job 2).
            fc = r.get("floor_anchor_cifp")
            cc = r.get("ceil_anchor_cifp")
            if fc is not None and cc is not None:
                f_lo, f_hi, f_ref = fc
                c_lo, c_hi, c_ref = cc
                forced = max(0.0, f_lo - c_hi)
                cifp_short = forced - budget
                lines.append(
                    f"      CIFP-FORCED half (MIXED FRAME — the forced "
                    f"spread below is WORLD-INVARIANT, the route budget "
                    f"it is compared against is WORLD-DEPENDENT): floor "
                    f"anchor {fa} on {f_ref} may lawfully seat in "
                    f"[{f_lo:.3f}, {f_hi:.3f}] m (emitted "
                    f"{'?' if fv is None else f'{fv:.3f}'}); ceiling anchor "
                    f"{ca} on {c_ref} in [{c_lo:.3f}, {c_hi:.3f}] m "
                    f"(emitted {'?' if cv is None else f'{cv:.3f}'})")
                # THE TWO HALVES CARRY DIFFERENT FRAMES, and the label has
                # to say so (RULINGS 2026-08-06 binding point 3).
                # ``forced = max(0, f_lo − c_hi)`` is WORLD-INVARIANT: CIFP
                # threshold elevations + station geometry + the runway's
                # own law caps, and the two-world twin
                # (``test_the_cifp_forced_envelope_is_IDENTICAL_IN_BOTH_
                # WORLDS``) asserts it.  ``budget = floor_route_m +
                # ceil_route_m`` is a ROUTE metric measured on the SOLVED
                # graph — WORLD-DEPENDENT.  Their difference is therefore
                # a MIXED quantity, and the old bare "(WORLD-INVARIANT)"
                # label over-claimed the comparison.
                _rest = (None if spread is None
                         else max(0.0, spread - forced))
                lines.append(
                    f"      ⇒ CIFP-forced minimum spread {forced:.4f} m "
                    f"(WORLD-INVARIANT) over a route budget of "
                    f"{budget:.3f} m (WORLD-DEPENDENT: a route metric on "
                    f"the solved graph) ⇒ CIFP shortfall "
                    f"{cifp_short:+.4f} m (MIXED) — "
                    + ("the CIFP thresholds themselves do not reach each "
                       "other within this route budget (a METRIC / CAP / "
                       "TOPOLOGY defect: rule on it, the DEM cannot be "
                       "blamed)"
                       if cifp_short > tol else
                       # NUMBERS ONLY.  ``forced ≤ budget`` is derivable
                       # and stays; the closed-vocabulary verdict this
                       # clause used to assign ("verdict (a) BUG, never a
                       # law shortfall") was an INTERPRETATION printed by
                       # report code, which RULINGS 2026-08-06 binding
                       # point 2 reserves for the law layer.
                       f"CIFP-forced spread FITS the budget "
                       f"({forced:.4f} ≤ {budget:.3f} m), so a lawful "
                       f"pair of profiles closes this route; of the "
                       f"emitted spread "
                       f"{'?' if spread is None else f'{spread:.3f}'} m, "
                       f"{'?' if _rest is None else f'{_rest:.3f}'} m is "
                       f"not CIFP-forced (WORLD-DEPENDENT content: "
                       f"seating, flex-applied targets, seam / crossing "
                       f"anchors)"))
            elif fc is not None or cc is not None:
                lines.append(
                    f"      CIFP-FORCED half: anchor "
                    f"{ca if fc is not None else fa} is not a runway-"
                    f"profile station, so no CIFP-forced spread exists "
                    f"for this pair — CIFP is NOT blamable here; classify "
                    f"from the world-dependent half")
    # NODE-SPACE STAMP for the per-node rows below.  The ids were BARE
    # here while the consumer (``tools/trace_reach_route.py``) carried the
    # whole hazard in its own docstring — an unstamped producer feeding a
    # stamped consumer is binding point 3's failure mode.  ``@(x, y)`` is
    # in layout-local metres relative to ``layout.anchor``.
    lines.append(
        f"  node ids: {BAND_NODE_SPACE}; @(x,y) in layout-local metres "
        f"about layout.anchor")
    for r in over[:20]:
        where = ("" if r["x"] is None
                 else f" @({r['x']:.1f},{r['y']:.1f})")
        if r.get("klass") == "floor_above_own_hard_value":
            lines.append(
                f"  node {r['node']}{where}: floor {r['floor']:.3f} > its "
                f"OWN hard runway/seam value "
                f"{r.get('own_hard_value', float('nan')):.3f} by "
                f"{r['deficit_m']:.4f} m "
                f"(route: floor {r['floor_route_m']:.2f} m of budget, "
                f"ceiling {r['ceil_route_m']:.2f} m)")
            continue
        lines.append(
            f"  node {r['node']}{where}: floor {r['floor']:.3f} > ceiling "
            f"{r['ceiling']:.3f} by {r['deficit_m']:.4f} m "
            f"(route: floor {r['floor_route_m']:.2f} m of budget, "
            f"ceiling {r['ceil_route_m']:.2f} m)")
    if len(over) > 20:
        lines.append(f"  … {len(over) - 20} more")
    raise BandInversionError("\n".join(lines))


def reach_band_unified(layout, G):
    """THE reach band — ONE engine, route-metric, service-excluded.

    Contract: ``band(x, y) -> (floor, ceiling) | None``.

    SINGLE SOURCE (owner directive 2026-07-29, spec rod-compose-and-band-
    single-source §B).  This factory used to contain THREE band engines —
    a raster field, a per-query nearest-visible-centerline path serving the
    raster's ``None`` answers, and a ``_build_skeleton_band`` fallback with
    no service filter — and mixed them PER QUERY inside one building's ring.
    Two of them are gone; what remains is:

      * VALUE — :func:`spine_value_fields`: anchor values propagated along
        NON-SERVICE airside routes at the applicable caps, on the unified
        graph the spine solves and the validator checks.  A route metric.
      * LOOKUP — :func:`raster_reach_band.build_raster_reach_band`: a grid
        that answers "which route attachment serves this point, and what
        does the local off-route leg to it cost".  Grid/raster is a QUERY
        ACCELERATION only; it does not carry the metric (the audited bug it
        used to have: propagating VALUE through the paved grid is an AREA
        metric, and it under-credited 8.7 m on the U-fixture whenever a
        service route crossed apron pavement — biasing seats LOW, exactly
        HECA's shape).

    The ``O4_RASTER_REACH_BAND`` selector went with the deleted engines —
    one engine needs no selector.  ``config.REACH_NO_SERVICE_SPINES``
    STAYS: it gates the LAW (which edges reachability may ride), not the
    engine.  A point off the pavement mask beyond the bounded off-net
    radius reads ``None`` (the local within-shape law governs it) — there
    is no fallback path left to mix in.

    ``band.batch(nodes, limit)`` is the list form ``node_bands`` may
    dispatch to; with O(1) lookups it is exactly the per-point scan (the
    cluster amortization existed only to share the deleted nvc scan)."""
    from auto_patch.elevation_per_surface.raster_reach_band import (
        build_raster_reach_band)
    band = None
    band_exc = None
    try:
        band = build_raster_reach_band(layout, G)
    except Exception as _exc:
        band_exc = _exc
        band = None
    if band is None:
        # With one engine there is nothing to fall back TO — every query
        # reads off-net and the within-shape law governs.  Loud, because a
        # silently band-less airport used to be masked by the fallbacks.
        #
        # THE LINE THAT STOOD HERE WAS A CATCH-ALL BUCKET LABELLED WITH
        # THREE CANDIDATE CAUSES ("no anchors / no pavement / grid over
        # cap"), none of them distinguished and the ``except Exception``
        # above swallowing everything on top — RULINGS 2026-08-06 binding
        # point 2's named defect pattern.  Two conditions are being fused
        # and they have opposite dispositions:
        #
        #   * the builder RAISED — a DEFECT (the exception is named);
        #   * the builder RETURNED None — a layout for which no band
        #     exists, which is a legitimate answer.
        #
        # What we can NAME is what this frame can observe: the graph-side
        # preconditions ``build_raster_reach_band`` documents.  Anything
        # left is inside the builder (pavement domain empty, paved mask
        # empty, grid over ``RASTER_REACH_BAND_MAX_CELLS`` — that last one
        # logs its own ``[raster-reach-band]`` line), and the report says
        # so instead of guessing between them.  Measured live at HEAZ,
        # which ships this line on every build.
        try:
            import O4_UI_Utils as _UI
            n_pos = len(getattr(G, "pos", None) or {})
            n_anchor = len(getattr(G, "runway_anchor", None) or {})
            n_adj = len(getattr(G, "spine_adj", None) or {})
            if band_exc is not None:
                _why = (f"the band BUILDER RAISED "
                        f"{type(band_exc).__name__}: {band_exc}")
            else:
                failed = []
                if not n_pos:
                    failed.append("G.pos is empty (no node positions)")
                if not n_anchor:
                    failed.append("G.runway_anchor is empty "
                                  "(no runway anchor to seed from)")
                if not n_adj:
                    failed.append("G.spine_adj is empty "
                                  "(no spine adjacency)")
                if failed:
                    _why = ("the builder RETURNED None; failing "
                            "precondition(s): " + "; ".join(failed))
                else:
                    _why = ("the builder RETURNED None and no graph-side "
                            "precondition is falsified — the remaining "
                            "ones are internal to build_raster_reach_band "
                            "(empty pavement domain, empty paved mask, or "
                            "grid over RASTER_REACH_BAND_MAX_CELLS, which "
                            "logs its own [raster-reach-band] line)")
            _UI.vprint(1,
                       f"  [reach-band] NO FIELD — {_why}.  "
                       f"G: nodes={n_pos}, runway anchors={n_anchor}, "
                       f"spine-adjacent nodes={n_adj}.  Every query reads "
                       f"off-net (band None), so every band-scoped "
                       f"instrument examines ZERO vertices this build.  "
                       f"{instrument_frame(layout, BAND_NODE_SPACE)}")
        except Exception:                                  # pragma: no cover
            pass
        return lambda x, y: None

    def _batch(nodes, limit):
        """The per-point scan as a list — bit-identical by construction."""
        n = len(nodes)
        lim = n if limit is None else min(limit, n)
        out = [None] * n
        for i in range(max(0, lim)):
            out[i] = band(nodes[i][0], nodes[i][1])
        return out

    band.batch = _batch                                    # type: ignore
    return band


def _has_visible_corridor(px, py, cls, vis, max_m):
    """True when a taxi corridor lies within ``max_m`` of ``(px, py)`` AND a chord
    from the point to that corridor's spine stays on pavement (a VISIBLE chord —
    the user's gate, 2026-06-27).  ``vis`` None (visibility disabled) → distance
    gate only."""
    from shapely.geometry import Point, LineString
    from shapely.ops import nearest_points
    c = Point(px, py)
    cand = [L for L in cls if L.distance(c) <= max_m]
    if not cand:
        return False
    if vis is None:
        return True
    for ln in sorted(cand, key=lambda L: L.distance(c)):
        foot = nearest_points(ln, c)[0]
        chord = LineString([(px, py), (foot.x, foot.y)])
        if chord.length < 1e-6 or vis.contains(chord):
            return True
        try:                                 # tolerate tiny weld-seam gaps
            if _paved_frac(chord, vis) >= _VIS_ON_PAV_FRAC:
                return True
        except Exception:                                  # pragma: no cover
            pass
    return False


def _frontage_band(poly, band, cls, vis, max_corridor_m):
    """Intersect the route-feasibility ``band`` over the building's ENTIRE
    qualifying FRONTAGE (user 2026-06-27, large buildings only).

    A frontage SAMPLE (every ring vertex + each edge midpoint) qualifies when a
    taxi corridor lies within ``max_corridor_m`` AND a visible on-pavement chord
    reaches that corridor's spine (:func:`_has_visible_corridor`) — i.e. every
    SIDE flanked by a taxi route, not only the apron the building abuts.  The
    band is sampled at every qualifying point and the feasible interval is the
    INTERSECTION — ``(max floor, min ceiling)`` — so the seated flat level keeps
    EVERY such frontage point gradeable to the spine at ≤1 % (not just the central
    chord).  Returns ``(floor, ceiling)`` or ``None`` when no side qualifies
    (caller falls back to the central chord)."""
    ring = list(poly.exterior.coords)
    floor, ceil = -_INF, _INF
    got = False
    for i in range(len(ring) - 1):
        ax, ay = ring[i]
        bx, by = ring[i + 1]
        mx, my = 0.5 * (ax + bx), 0.5 * (ay + by)
        for (px, py) in ((ax, ay), (mx, my), (bx, by)):
            if not _has_visible_corridor(px, py, cls, vis, max_corridor_m):
                continue
            bb = band(px, py)
            if bb is None:
                continue
            floor = max(floor, bb[0])
            ceil = min(ceil, bb[1])
            got = True
    return (floor, ceil) if got else None


def _footprint_dem_relief(poly, dem_sampler):
    """DEM mean and relief (``max − min``) over a building footprint — its ring
    vertices plus its centroid — through the SAME ``dem_sampler`` the seat path
    uses (so the mean is bit-identical to what the band path would sample).

    Returns ``(mean, relief)`` or ``None`` on ANY sampling gap (off-tile, DEM
    error, NaN) — the seat certificate then refuses and the normal band path
    runs, failing toward correctness (spec §2.2)."""
    values = []
    centroid = poly.centroid
    ring = list(poly.exterior.coords)
    for (x, y) in ring + [(centroid.x, centroid.y)]:
        value = dem_sampler(x, y)
        if value is None or value != value:
            return None
        values.append(float(value))
    if not values:
        return None
    return (sum(values) / len(values), max(values) - min(values))


def _footprint_radius(poly, centroid):
    """Largest distance from ``centroid`` to any footprint ring vertex (the
    reach the band-margin soundness guard must cover)."""
    radius = 0.0
    for (x, y) in poly.exterior.coords:
        distance = math.hypot(x - centroid.x, y - centroid.y)
        if distance > radius:
            radius = distance
    return radius


def building_feasible_levels(
        layout,
        runway_pts_xyz: List[Tuple[float, float, float]],
        dem_sampler: Callable[[float, float], "float | None"],
        band=None,
) -> Dict[int, float]:
    """Return ``{id(building_shape): seated_level_m}`` for every
    ``ROLE_BUILDING`` that touches airside pavement.

    ``runway_pts_xyz``: ``[(x_m, y_m, elev_m)]`` every runway ring vertex at its
    solved elevation (the runway-edge anchors — see :func:`runway_edge_anchors`).
    ``dem_sampler(x, y)``: DEM (m) at a layout-local point, or None.  The level
    is ``clamp(DEM, floor, ceiling)`` from the shared route-feasibility band — if
    DEM is not reachable within grade from every runway route, the level is
    pulled into the band (the building is adjusted to be feasible).  Buildings
    not touching airside pavement are omitted (the caller keeps them at DEM).

    ``band``: the pre-built unified-graph band from :func:`reach_band_unified`
    (required) — buildings are placed on the SAME graph the spine is graded on
    (the single graph; they then agree by construction)."""
    from shapely.ops import unary_union

    if band is None:
        raise ValueError(
            "building_feasible_levels requires a prebuilt band "
            "(reach_band_unified); the legacy route-graph sampler was removed")
    polys = [s.polygon for s in layout.shapes
             if s.role in _AIRSIDE_ROLES and s.polygon is not None
             and not s.polygon.is_empty]
    if not polys:
        return {}
    try:
        airside = unary_union(polys)
    except GEOSException:
        # GEOS can hit a non-noded intersection on nearly-collinear
        # sliver edges (KDFW 2026-07-10, two ~0.1 m-apart parallel
        # segments).  buffer(0) renodes each input; the union of the
        # repaired polygons is geometrically the same airside region.
        airside = unary_union([p.buffer(0) for p in polys])
    # Significance gate (user 2026-07-17, KBNA SE lot): a pad only
    # counts as airside-served when the airside COMPONENT it touches is
    # big enough to serve aircraft.  KBNA building23 touched an
    # ISOLATED 66 m² apron scrap and inherited the runway reach floor,
    # emitting 11.6 m above its own ground.  Components come from the
    # union (touching/overlapping shapes merge), so a connected apron
    # complex passes regardless of how the slice fragmented it, while
    # an isolated scrap fails alone.
    airside_components = [
        part for part in (airside.geoms
                          if airside.geom_type == "MultiPolygon"
                          else [airside])
        if not part.is_empty
        and part.area >= BUILDING_AIRSIDE_CONTACT_MIN_COMPONENT_M2]
    if not airside_components:
        return {}
    airside = unary_union(airside_components)

    # Buildings ≥ this footprint must clear their ENTIRE frontage, not just a
    # single central chord (user 2026-06-27); small buildings keep the centroid
    # chord.  ``config.BUILDING_FULL_FRONTAGE`` is the law's own switch.
    full_frontage = BUILDING_FULL_FRONTAGE
    # Taxi corridors + pavement-visibility for the frontage qualifier (a side
    # grades at 1 % only when a corridor is within range AND visibly chord-reachable).
    cls = vis = None
    if full_frontage:
        cls = [cl.line for cl in
               (getattr(layout, "apt_taxi_centerlines", None) or [])
               if cl.line is not None and not cl.line.is_empty
               and not cl.is_service]
        vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None

    # SEAT CERTIFICATE (Tier 1, spec §3.2 + §2.4 "buildings are FLAT"): a
    # building whose whole footprint DEM relief fits the seat flatness tolerance
    # is feasible FLAT at its DEM mean by inspection, so it skips the expensive
    # per-building reach-band frontage construction and records that mean as its
    # seated level.  Sound guard: the DEM mean must also sit inside the central
    # reach band with a margin ≥ ``footprint_radius · APRON_MAX_GRADE`` (so the
    # whole flat footprint stays reachable — a building near a constraining, and
    # thus tight, route band refuses and takes the normal clamp).  Switched by
    # ``config.FLAT_CERTIFICATE_COVERAGE``.
    seat_certificate_enabled = FLAT_CERTIFICATE_COVERAGE
    try:
        from auto_patch.elevation_per_surface.solver_primitives import (
            _record_flat_certificate, _report_flat_certificate_counts)
    except Exception:                                      # pragma: no cover
        _record_flat_certificate = None
        _report_flat_certificate_counts = None

    def _record(outcome):
        if _record_flat_certificate is not None:
            _record_flat_certificate(layout, "seat", outcome)

    out: Dict[int, float] = {}
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        if airside.is_empty or s.polygon.distance(airside) > _TOUCH_TOL_M:
            continue                            # not airside-served → DEM
        c = s.polygon.centroid
        # Seat certificate: a flat footprint seats at its DEM mean, skipping the
        # frontage band, when the mean is comfortably inside the central band.
        if seat_certificate_enabled:
            _record("candidate")
            relief = _footprint_dem_relief(s.polygon, dem_sampler)
            certified_seat = None
            if relief is not None and relief[1] <= BUILDING_SEAT_FLATNESS_TOLERANCE_M:
                seat_mean = relief[0]
                central = band(c.x, c.y)
                if central is not None:
                    floor_c, ceil_c = central
                    margin = APRON_MAX_GRADE * _footprint_radius(s.polygon, c)
                    if floor_c + margin <= seat_mean <= ceil_c - margin:
                        certified_seat = seat_mean
            if certified_seat is not None:
                _record("certified")
                out[id(s)] = certified_seat
                continue
            _record("refused")
        # LARGE building → intersect the band over the whole frontage; SMALL (or no
        # qualifying frontage side) → the single central chord from the centroid.
        b = None
        if (full_frontage and cls
                and s.polygon.area >= BUILDING_FULL_FRONTAGE_AREA_M2):
            b = _frontage_band(s.polygon, band, cls, vis,
                               BUILDING_REACH_CORRIDOR_M)
        if b is None:
            b = band(c.x, c.y)
        if b is None:
            continue
        floor, ceil = b
        de = dem_sampler(c.x, c.y)
        if de is None:
            continue
        if floor > ceil:                        # infeasible → midpoint (adjust)
            out[id(s)] = 0.5 * (floor + ceil)
        else:
            out[id(s)] = min(max(de, floor), ceil)
    # One per-airport certificate summary line (spec §2 item 7), printed once —
    # after the building-seat pass, so rect/apron/junction counts from the
    # preceding constraint build and the seat counts here are all present.
    if (_report_flat_certificate_counts is not None
            and not getattr(layout, "_flat_certificate_reported", False)):
        try:
            _report_flat_certificate_counts(layout, getattr(layout, "icao", ""))
            layout._flat_certificate_reported = True
        except Exception:                                  # pragma: no cover
            pass
    return out
