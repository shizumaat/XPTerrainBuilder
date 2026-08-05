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


def _paved_fracs(chords, vis):
    """Vectorised :func:`_paved_frac` over a LIST of chord LineStrings — the
    seam-gap paved fraction for each, returned as a ``list[float]`` in input
    order.  Every chord's sample points (the SAME ``(arange(n)+0.5)/n`` mid-cell
    sampling, same ``n = min(96, max(8, int(L)))``) are concatenated into ONE
    ``shapely.contains_xy`` call, then the per-chord mean is sliced back out —
    bit-identical to calling :func:`_paved_frac` on each chord, but paying the
    numpy/GEOS call overhead ONCE per batch instead of once per candidate (the
    phantom reach-band tail ran this ~2 M times, one candidate at a time)."""
    import numpy as _np
    import shapely as _sh
    geom = getattr(vis, "context", vis)
    _sh.prepare(geom)
    m = len(chords)
    fracs = [1.0] * m
    if m == 0:
        return fracs
    chords_arr = (chords if isinstance(chords, _np.ndarray)
                  else _np.asarray(chords, dtype=object))
    # Endpoints + lengths in ONE vectorised call each (each chord is a 2-point
    # LineString ``[foot, c]``): coords rows are [foot0, c, foot1, c, ...].
    cc = _sh.get_coordinates(chords_arr)
    a = cc[0::2]                    # feet  (chord start)
    b = cc[1::2]                    # c     (chord end)
    Ls = _sh.length(chords_arr)
    segs = []                      # (out_index, start, n)
    xs_parts = []
    ys_parts = []
    total = 0
    for idx in range(m):
        L = float(Ls[idx])
        if L < 1e-9:
            continue               # frac stays 1.0 (matches _paved_frac)
        n = min(96, max(8, int(L)))
        t = (_np.arange(n) + 0.5) / n
        ax, ay = a[idx, 0], a[idx, 1]
        bx, by = b[idx, 0], b[idx, 1]
        xs_parts.append(ax + (bx - ax) * t)
        ys_parts.append(ay + (by - ay) * t)
        segs.append((idx, total, n))
        total += n
    if total:
        hits = _sh.contains_xy(geom, _np.concatenate(xs_parts),
                               _np.concatenate(ys_parts))
        for (idx, start, n) in segs:
            fracs[idx] = float(hits[start:start + n].mean())
    return fracs


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
        pq = [((ae if sign > 0 else -ae), 0.0, ae, k)
              for (k, ae) in anchor_seeds.items()]
        heapq.heapify(pq)
        while pq:
            _key, dd, ae, u = heapq.heappop(pq)
            if u in best:
                continue
            best[u] = (ae + dd) if sign > 0 else (ae - dd)
            dist[u] = dd
            for (v, budget) in G.spine_adj.get(u, ()):
                if v in best:
                    continue
                if svc_pairs and ((u, v) if u < v else (v, u)) in svc_pairs:
                    continue
                nd = dd + budget
                heapq.heappush(
                    pq, (((ae + nd) if sign > 0 else -(ae - nd)),
                         nd, ae, v))
        return best, dist

    ceiling, ceil_dist = _field(+1)
    floor, floor_dist = _field(-1)
    _record_band_inversions(layout, G, ceiling, floor, ceil_dist, floor_dist,
                            hard_truth=_hard_truth_spine_seeds(layout, G))
    return ceiling, floor


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


def _record_band_inversions(layout, G, ceiling, floor, ceil_dist,
                            floor_dist, hard_truth=None):
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
        for node, lo in floor.items():
            hi = ceiling.get(node)
            if hi is None:
                continue
            deficit = lo - hi
            if deficit <= 0.0:
                continue
            xy = pos.get(node)
            rows.append({
                "node": node,
                "klass": "floor_above_ceiling",
                "floor": float(lo),
                "ceiling": float(hi),
                "deficit_m": float(deficit),
                "floor_route_m": float(floor_dist.get(node, 0.0)),
                "ceil_route_m": float(ceil_dist.get(node, 0.0)),
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
        f"(floor − ceiling > {tol:g} m).  A real airport with real "
        f"thresholds has a lawful surface (docs/RULINGS.md, "
        f"feasibility-is-guaranteed): this is a law defect to attribute — "
        f"a wrong metric, a wrong anchor value, a wrong role/cap or a "
        f"false topology — never a region to quarantine.",
    ]
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
    try:
        band = build_raster_reach_band(layout, G)
    except Exception:                                      # pragma: no cover
        band = None
    if band is None:
        # No anchors / no pavement / no scipy / grid over the cell cap.
        # With one engine there is nothing to fall back TO — every query
        # reads off-net and the within-shape law governs.  Loud, because a
        # silently band-less airport used to be masked by the fallbacks.
        try:
            import O4_UI_Utils as _UI
            _UI.vprint(1, "  [reach-band] no field could be built "
                          "(no anchors / no pavement / grid over cap) — "
                          "every query reads off-net (band None).")
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
