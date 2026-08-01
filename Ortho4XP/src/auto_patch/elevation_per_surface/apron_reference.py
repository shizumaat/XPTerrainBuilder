"""The APRON REFERENCE SURFACE ``R`` — spec ``docs/specs/
apron-string-and-scheduling-spec.md`` Part B.4 (owner rulings 2026-07-30).

> "An apron's 'string' should be straight chords between taxiway
> connections, buildings, and all edges.  Essentially an apron *wants* to
> be flat across its whole surface, but is allowed to grade up to 1 %
> where necessary, no more."

``R`` is built per **connected apron component** (the union of welded
apron-role shapes — per-SHAPE ``R`` would mint a reference step at every
apron↔apron weld, and HECA's terminal fabric is one slice-born
931 k m² component made of many welded shapes).

Construction (spec B.4, verbatim):

* **Anchors** — ``R`` equals these:
  1. taxi-spine crossings (the spine carries the climb at its own
     per-letter cap; the apron grades out from it),
  2. building pad-face contacts at the pad's **rod level** (never the raw
     seat scalar — measured 21/25 HECA pads differ; see
     ``docs/specs/pad-rod-coupling-spec.md``),
  3. every welded boundary node against a graded neighbour (a node the
     apron shares with any non-apron pavement shape), and every node the
     caller holds hard in this pass (seam pins, runway, joins,
     groundside pins).
* **Between anchors: straight chords** — expressed as the **minimum
  DIRICHLET energy** surface (squared gradient) subject to the anchors.
  With edge weights ``1/length`` the 1-D restriction between two anchors
  is exactly the straight chord, which IS the ruling; the revision-1
  "minimise total gradient magnitude" (L1) is degenerate — it ties every
  monotone profile — and was corrected by the review.
* **Caps** — POCS projection onto the per-pair slabs ``|z_u − z_v| ≤
  budget`` where ``budget`` is the LANDED spine-frame allowance
  (``grade_graph._bake_edge`` under ``O4_SPINE_FRAME_PAIRS``: ``cL`` = the
  route's per-letter taxi cap ≤ 1.5 % longitudinally, ``cT`` = the pair's
  own cap — apron 1 % — laterally, in the ``ds_decompose`` spine frame).
  This module NEVER re-derives that cap: it reads the allowances
  ``grade_graph.build_unified_graph`` already baked and stashed on
  ``layout._lockstep_shape_bake``.  One derivation, two consumers
  (single-pass principle).
* **Edge set** — two distinct sets, and conflating them was measured
  wrong:
  - the DIRICHLET graph is ``grade_graph.mesh_edge_keys``, the declared
    single source for a shape's CDT edges (spec B.4: no new
    triangulation).  That is the surface's connectivity — which vertices
    are neighbours on the mesh X-Plane will render.
  - the CAP SLABS are the shape's FULL baked pair set.  ★ Spec B.4 says
    to POCS "onto the per-edge cap slabs ... on the existing CDT edge
    set"; taken literally that under-constrains R, because an APRON's
    law is the full visibility graph, not the mesh edges (only JUNCTIONS
    take the mesh-edge rule — ``grade_graph.shape_constraints``: "APRONS
    keep their full visibility graph (the geodesic flatness model
    catches aggregate slope a mesh edge misses)").  Measured at CYXY
    with CDT-only slabs: R minted 3 fresh within-shape violations on
    apron #43, all LONG chords (66-98 m) at 1.05-1.63 % against the 1 %
    cap — pairs the law binds and the CDT edge set does not contain.
    Since B's own acceptance is "no apron node exceeds its lateral 1 % /
    longitudinal 1.5 % against R", the slab set must be the law's.
* **Frame and sample time** — ``R`` carries no frame of its own: every
  anchor value is sampled from the CALLER's ``elev`` (or from the caller's
  already-resolved pad-rod levels), so ``R`` is by construction in
  whatever frame that pass runs in — the de-crowned solve frame at fp#8,
  the crown-lifted ``z′`` frame at ``final_grade_projection``.  Nothing is
  ever read from a raw ``elev`` snapshot taken in another pass, and
  nothing is read from the DEM (spec B.5: HECA's elevation source is a
  30.9 m pixel with 0 % inset coverage, so nothing there qualifies for
  draping — pavement CUTS THROUGH).
* ★ **Anchor honesty** (``O4_APRON_R_LAW_TRUE``, default ON — spec
  ``docs/specs/reference-honesty-and-terracing-spec.md`` Track 1 step 1;
  B.4's own ★ clause "never from raw ``elev`` at yield entry").  Being in
  the caller's frame is necessary but NOT sufficient: at both call sites
  the incoming ``elev`` has already been through a quarantine blend
  (``one_solve.feasibility_project``'s broken branch), and a blended value
  is by definition a value the law REFUSED to admit.  Anchoring ``R`` on
  one drags every free node around it (measured HECA 2026-07-30: incoming
  104.13 → R 95.88 at 2.5 m from the seam site).  So each candidate anchor
  is resolved through a priority ladder and a quarantined value is never
  used raw:

  1. ``hard_idx`` — this pass HOLDS the value, so it is the pass's own
     truth (priority 1) and is law-true by construction.
  2. a node the reach envelope did NOT quarantine (``broken_idx``) —
     ``elev`` is inside its own ``[floor, ceiling]`` envelope, law-true.
  3. a quarantined node carried by the §10 taut rod — the **rod-held
     string** value (``string_value``): the rod's Δ shape placed at the
     least-displacement level of the chain's own law-true members.  A rod
     slab is a DIFFERENCE constraint, so it survives the break region
     intact; this is the "sample from the rod-held string" clause.
  4. a quarantined node with a reach band — SOFTENED: the incoming value
     clamped into ``[floor, ceiling]`` of the band that seats it.  The
     band is a law-derived interval, so the clamped value is law-true even
     where the pointwise blend parked the node metres under it.
  5. otherwise **REFUSED** — the node stops being an anchor and becomes an
     ordinary free node of the Dirichlet solve.

  ★ Refusal is deliberately LAST: break regions cover 830 of 904 HECA
  mega-ring vertices, so a naive "refuse every broken anchor" strips the
  component's boundary conditions.  The surviving anchor count per class
  is reported (``stats_out`` / ``O4_STEP_DEBUG``) precisely so that
  over-stripping is visible rather than silent.
  ``O4_APRON_R_LAW_TRUE=0`` (or a caller that passes no ``broken_idx``)
  restores the raw-``elev`` sampling byte-identically.

``R`` supplies ``z_ref`` for the NON-anchor apron nodes through the landed
bounded-yield §7 reference machinery (``one_solve.feasibility_project``'s
``node_refs``).  It does not replace phase A and it is not a second
interpolator: the §7 term is what turns "any feasible point" into
"minimum displacement from ``R``".

Gate: ``O4_APRON_STRING`` (default ON).  Off ⇒ this module is never
imported and the reference field is byte-identically today's (proven by
body sha256 on CYXY, SPJC, SPLP and HECA, 2026-07-30).
``O4_APRON_R_DUMP=<path>`` writes a per-node CSV (R, incoming value,
anchor class, component) for offline acceptance work; unset ⇒ inert.

Measured at HECA 2026-07-30 (emitted patch, law-true validator):
the owner's hill peak fell from **chord + 3.17 m to chord + 1.39 m**, the
emitted surface sits **0.14 m from R** at the reported site, break-region
pairs fell 19,061 → 18,545 and the terrain-scan broken count 11,261 →
11,053.  What R does NOT do is close the hill to the ruled 0.3 m: R is a
harmonic surface and has no interior maximum, so the residual bulge is
its ANCHORS — the nearest ones to the hill are a groundside weld at
66.20 (105 m away) and a taxi spine at 70.5-73.7 (178 m away), and the
apron sitting level with its own spine IS the owner's spine-frame model.
8,093 of 31,051 apron cap slabs at HECA are ANCHOR-vs-ANCHOR and over
cap — contradictions no interior surface can resolve, and therefore the
measured B.6 answer: the 931 k m² component is still infeasible under
B.2/B.3, now with the deficit localised on the anchor set rather than
on the fabric.
"""
from __future__ import annotations

import math
import os

# POCS slab sweeps after the Dirichlet solve.  The Dirichlet minimiser
# already satisfies most slabs (a chord between anchors that are
# themselves cap-reachable is in-cap by construction); the sweeps exist
# for the pockets where the anchors are NOT mutually cap-reachable.
_POCS_MAX_SWEEPS = 400
_POCS_TOL_M = 1e-3

# Dirichlet fallback (no scipy): Gauss-Seidel sweeps.
_GS_MAX_SWEEPS = 4000
_GS_TOL_M = 1e-4


def _debug() -> bool:
    return os.environ.get("O4_STEP_DEBUG") == "1"


def _law_true_anchors() -> bool:
    """Gate ``O4_APRON_R_LAW_TRUE`` (default ON) — see the module docstring's
    "Anchor honesty" clause."""
    return os.environ.get("O4_APRON_R_LAW_TRUE", "1") == "1"


def _band_clamp(value, band):
    """The band-derived (SOFTENED) anchor value, or ``None`` when the band
    cannot supply one.  ``band`` is a ``(floor, ceiling)`` reach-band
    interval; an inverted or non-finite interval is no interval at all."""
    if band is None:
        return None
    try:
        lo = float(band[0])
        hi = float(band[1])
    except (TypeError, IndexError, ValueError):        # pragma: no cover
        return None
    if not (math.isfinite(lo) and math.isfinite(hi)) or lo > hi:
        return None
    return min(max(float(value), lo), hi)


class _ApronMesh:
    """The per-apron-shape CDT edge set + baked cap slabs, in RING-POSITION
    space, cached on the layout by ``id(shape.polygon)``.

    Ring positions (not node indices) because the cache must survive the
    node-list rebuild between the solve and ``final_grade_projection``,
    and because that is the space ``layout._lockstep_shape_bake`` already
    uses.  Guarded by the ring signature: a shape whose ring changed
    (post-solve conformance inserts) re-triangulates."""

    __slots__ = ("signature", "edges")

    def __init__(self, signature, edges):
        self.signature = signature
        self.edges = edges          # list[(pos_a, pos_b)]


def _ring_signature(ring) -> tuple:
    return tuple((round(x, 6), round(y, 6)) for (x, y) in ring)


def _apron_mesh_edges(layout, shape, ring):
    """The shape's CDT edge set as ring-position pairs, memoised."""
    from auto_patch.grade_graph import mesh_edge_keys
    store = getattr(layout, "_apron_mesh_cache", None)
    if store is None:
        store = {}
        try:
            layout._apron_mesh_cache = store
        except Exception:                              # pragma: no cover
            pass
    signature = _ring_signature(ring)
    cached = store.get(id(shape.polygon))
    if cached is not None and cached.signature == signature:
        return cached.edges
    positions = list(range(len(ring)))
    edges = [tuple(sorted(pair))
             for pair in mesh_edge_keys(ring, positions)
             if len(pair) == 2]
    store[id(shape.polygon)] = _ApronMesh(signature, edges)
    return edges


def _baked_budgets(layout, shape, ring):
    """``{(pos_a, pos_b): budget_m}`` from the allowances
    ``grade_graph.build_unified_graph`` baked for THIS shape (the landed
    spine-frame cap structure, B.2).  Empty when the stash is missing or
    its ring signature no longer matches — the Dirichlet graph then still
    connects those nodes, they just carry no slab (which is the correct
    reading of B.3: a pair the law dropped is governed transitively, not
    directly)."""
    store = getattr(layout, "_lockstep_shape_bake", None)
    if not store:
        return {}
    entry = store.get(id(shape))
    if entry is None:
        return {}
    _role, signature, baked_edges, _spine = entry
    if signature != _ring_signature(ring):
        return {}
    out: dict = {}
    for (pa, pb, allowance) in baked_edges:
        if pa == pb:
            continue
        ax, ay = ring[pa]
        bx, by = ring[pb]
        budget = float(allowance.at(math.hypot(ax - bx, ay - by), 0.0))
        key = (pa, pb) if pa < pb else (pb, pa)
        # Tightest wins — the same min-aggregation every other consumer of
        # the pair law uses when a pair is minted twice.
        if key not in out or budget < out[key]:
            out[key] = budget
    return out


def _dirichlet_solve(free, adjacency, fixed_value):
    """Minimum-Dirichlet-energy values on ``free`` given the fixed anchors.

    Minimises ``Σ_edges (z_u − z_v)² / d_uv`` (weights ``1/d``), whose
    Euler-Lagrange equations are the weighted graph Laplace equation
    ``Σ_v w_uv (z_u − z_v) = 0``.  Between two anchors along a chain this
    is exactly the straight chord (uniform gradient) — the ruling.

    Sparse direct solve when scipy is available; damped Gauss-Seidel
    otherwise (same fixed point, slower)."""
    order = {i: k for k, i in enumerate(free)}
    m = len(free)
    if m == 0:
        return {}
    try:
        import numpy as _np
        from scipy.sparse import coo_matrix as _coo
        from scipy.sparse.linalg import spsolve as _spsolve
    except Exception:                                  # pragma: no cover
        return _gauss_seidel(free, adjacency, fixed_value)
    rows: list = []
    cols: list = []
    data: list = []
    rhs = _np.zeros(m, dtype=float)
    for i in free:
        r = order[i]
        diagonal = 0.0
        for (j, w) in adjacency.get(i, ()):
            diagonal += w
            other = order.get(j)
            if other is None:
                rhs[r] += w * fixed_value[j]
            else:
                rows.append(r)
                cols.append(other)
                data.append(-w)
        if diagonal <= 0.0:                            # isolated free node
            diagonal = 1.0
        rows.append(r)
        cols.append(r)
        data.append(diagonal)
    matrix = _coo((data, (rows, cols)), shape=(m, m)).tocsr()
    try:
        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            solution = _spsolve(matrix, rhs)
    except Exception:                                  # pragma: no cover
        return _gauss_seidel(free, adjacency, fixed_value)
    out = {}
    for i in free:
        value = float(solution[order[i]])
        if not math.isfinite(value):                   # pragma: no cover
            return _gauss_seidel(free, adjacency, fixed_value)
        out[i] = value
    return out


def _gauss_seidel(free, adjacency, fixed_value):       # pragma: no cover
    """Laplace relaxation fallback (scipy absent / singular system)."""
    z = {i: 0.0 for i in free}
    # Warm start: mean of the component's anchors.
    anchors = [fixed_value[j] for i in free
               for (j, _w) in adjacency.get(i, ()) if j in fixed_value]
    if anchors:
        seed = sum(anchors) / len(anchors)
        for i in free:
            z[i] = seed
    for _sweep in range(_GS_MAX_SWEEPS):
        worst = 0.0
        for i in free:
            total_w = 0.0
            total = 0.0
            for (j, w) in adjacency.get(i, ()):
                total_w += w
                total += w * (fixed_value[j] if j in fixed_value else z[j])
            if total_w <= 0.0:
                continue
            new = total / total_w
            worst = max(worst, abs(new - z[i]))
            z[i] = new
        if worst <= _GS_TOL_M:
            break
    return z


def _pocs_slabs(z, fixed_value, slabs):
    """Project onto the per-pair cap slabs ``|z_u − z_v| ≤ budget``.

    A slab with one anchored endpoint moves only the free end (an anchor
    is by definition not negotiable); with both endpoints free the excess
    splits evenly (the minimum-displacement projection onto that slab);
    with both anchored the slab is INFEASIBLE and is skipped — that is a
    genuine anchor contradiction and belongs to the existing break-region
    quarantine, not to ``R``.

    AVERAGED (Cimmino) projection, vectorised: every violated slab
    contributes its own projection and a node takes the MEAN of the
    contributions touching it.  Sequential POCS over the apron law's
    O(n²) pair set would be minutes of Python at HECA scale; the averaged
    form is one numpy pass per sweep and converges to the same
    intersection.  Returns the number of both-anchored (infeasible)
    slabs."""
    try:
        import numpy as _np
    except Exception:                                  # pragma: no cover
        return _pocs_slabs_scalar(z, fixed_value, slabs)
    if not slabs:
        return 0
    # Compact index space over every node the slabs touch.
    order: dict = {}
    for (u, v, _b) in slabs:
        if u not in order:
            order[u] = len(order)
        if v not in order:
            order[v] = len(order)
    m = len(order)
    values = _np.empty(m, dtype=float)
    free_mask = _np.zeros(m, dtype=bool)
    for node, k in order.items():
        if node in z:
            values[k] = z[node]
            free_mask[k] = True
        else:
            fv = fixed_value.get(node)
            if fv is None:                             # pragma: no cover
                values[k] = 0.0
            else:
                values[k] = fv
    u_idx = _np.fromiter((order[s[0]] for s in slabs), dtype=_np.int64,
                         count=len(slabs))
    v_idx = _np.fromiter((order[s[1]] for s in slabs), dtype=_np.int64,
                         count=len(slabs))
    budget = _np.fromiter((s[2] for s in slabs), dtype=float,
                          count=len(slabs))
    u_free = free_mask[u_idx]
    v_free = free_mask[v_idx]
    both_fixed = ~(u_free | v_free)
    stuck = 0
    live = ~both_fixed
    if not live.any():
        # every slab is anchor-vs-anchor: nothing R can do, count them.
        delta = _np.abs(values[u_idx] - values[v_idx]) - budget
        return int((delta > _POCS_TOL_M).sum())
    u_idx_l = u_idx[live]
    v_idx_l = v_idx[live]
    budget_l = budget[live]
    u_free_l = u_free[live]
    v_free_l = v_free[live]
    # share of the correction each end absorbs (an anchor absorbs none).
    u_share = _np.where(u_free_l & v_free_l, 0.5,
                        _np.where(u_free_l, 1.0, 0.0))
    v_share = _np.where(u_free_l & v_free_l, 0.5,
                        _np.where(v_free_l, 1.0, 0.0))
    for _sweep in range(_POCS_MAX_SWEEPS):
        diff = values[u_idx_l] - values[v_idx_l]
        excess = _np.abs(diff) - budget_l
        hit = excess > _POCS_TOL_M
        if not hit.any():
            break
        sign = _np.where(diff[hit] >= 0.0, 1.0, -1.0)
        move = sign * excess[hit]
        delta = _np.zeros(m, dtype=float)
        count = _np.zeros(m, dtype=float)
        _np.add.at(delta, u_idx_l[hit], -move * u_share[hit])
        _np.add.at(count, u_idx_l[hit], 1.0)
        _np.add.at(delta, v_idx_l[hit], move * v_share[hit])
        _np.add.at(count, v_idx_l[hit], 1.0)
        touched = count > 0
        values[touched & free_mask] += (
            delta[touched & free_mask] / count[touched & free_mask])
    # anchor-vs-anchor contradictions, reported not resolved.
    if both_fixed.any():
        residual = (_np.abs(values[u_idx[both_fixed]]
                            - values[v_idx[both_fixed]])
                    - budget[both_fixed])
        stuck = int((residual > _POCS_TOL_M).sum())
    for node, k in order.items():
        if node in z:
            z[node] = float(values[k])
    return stuck


def _pocs_slabs_scalar(z, fixed_value, slabs):          # pragma: no cover
    """Sequential POCS fallback (numpy absent)."""
    stuck = 0
    for _sweep in range(_POCS_MAX_SWEEPS):
        worst = 0.0
        stuck = 0
        for (u, v, budget) in slabs:
            zu = z[u] if u in z else fixed_value.get(u)
            zv = z[v] if v in z else fixed_value.get(v)
            if zu is None or zv is None:
                continue
            excess = abs(zu - zv) - budget
            if excess <= _POCS_TOL_M:
                continue
            worst = max(worst, excess)
            u_free = u in z
            v_free = v in z
            if not u_free and not v_free:
                stuck += 1
                continue
            sign = 1.0 if zu > zv else -1.0
            if u_free and v_free:
                z[u] = zu - sign * excess * 0.5
                z[v] = zv + sign * excess * 0.5
            elif u_free:
                z[u] = zu - sign * excess
            else:
                z[v] = zv + sign * excess
        if worst <= _POCS_TOL_M:
            break
    return stuck


def _dump_reference(layout, label, free_values, fixed_value, pad_ref,
                    spine_idx, weld_idx, hard_idx, elev, component_free,
                    parent, root_of, class_of=None):
    """``O4_APRON_R_DUMP=<path>``: one CSV row per apron node — its R value
    (or anchor value), its anchor class, its component and the pass's own
    incoming value.  Diagnostic only; unset ⇒ inert, so the byte-identity
    proof is unaffected."""
    path = os.environ.get("O4_APRON_R_DUMP")
    if not path:
        return
    if label:
        stem, _dot, ext = path.rpartition(".")
        path = f"{stem}.{label.replace('#', '')}.{ext}" if stem else path
    try:
        rows = []
        component_size = {}
        for r, free in component_free.items():
            component_size[r] = len(free)
        for i, value in list(free_values.items()) + [
                (k, v) for k, v in fixed_value.items()]:
            if i in free_values and i in fixed_value:   # pragma: no cover
                continue
            cls = (class_of or {}).get(i)
            if cls is None:
                if i in pad_ref:
                    cls = "pad_rod"
                elif i in hard_idx:
                    cls = "hard"
                elif i in spine_idx:
                    cls = "spine"
                elif i in weld_idx:
                    cls = "weld"
                else:
                    cls = "free"
            try:
                la, lo = layout.m_to_ll(*layout_node_xy(layout, i))
            except Exception:
                la, lo = 0.0, 0.0
            rows.append((la, lo, value, elev[i] if i < len(elev) else 0.0,
                         cls, root_of(i) if i in parent else -1))
        with open(path, "w") as fh:
            fh.write("lat,lon,R,incoming,anchor_class,component\n")
            for (la, lo, value, incoming, cls, comp) in rows:
                fh.write(f"{la:.7f},{lo:.7f},{value:.4f},{incoming:.4f},"
                         f"{cls},{comp}\n")
        print(f"    [apron-R] dump {label} -> {path} ({len(rows)} row(s))")
    except Exception as exc:                           # pragma: no cover
        print(f"    [apron-R] dump failed: {exc}")


def layout_node_xy(layout, index):
    """The (x, y) of a solver node index, via the canonical-point registry
    the pass keyed its node list with (dump path only)."""
    table = getattr(layout, "_apron_R_xy", None)
    if table is None:
        raise KeyError("no node table")
    return table[index]


def apron_reference_values(layout, bucket_to_idx, elev, *, n,
                           hard_idx, spine_idx, pad_ref,
                           label: str = "", broken_idx=None,
                           string_value=None, band_of=None,
                           stats_out=None) -> dict:
    """The apron reference surface ``R``, as ``{node_index: z_ref}`` for the
    NON-anchor apron nodes (spec B.4).

    ``elev`` supplies every anchor value except the pad-face contacts,
    which the caller has already resolved to the pad's ROD level and
    passes in ``pad_ref`` — so ``R`` is in the caller's own frame by
    construction and nothing is sampled from a foreign snapshot.

    ``hard_idx`` — the nodes this pass holds hard (anchors, priority 1).
    ``spine_idx`` — nodes on a taxi spine (anchors: the spine crossings).
    ``pad_ref`` — ``{node_index: pad rod level}`` for pad-face contacts.

    ANCHOR HONESTY (``O4_APRON_R_LAW_TRUE``, spec Track 1 step 1 — see the
    module docstring).  The caller supplies the law-true context:

    ``broken_idx`` — the nodes the reach envelope QUARANTINED (their
    ``elev`` is a distance-weighted blend of contradictory anchors, not a
    law-admissible value).  ``None`` ⇒ the ladder is inert and every
    anchor is sampled from ``elev`` exactly as before.
    ``string_value`` — ``{node: rod-held string value}`` for the §10 taut-rod
    nodes (``solve._rod_string_values``).
    ``band_of`` — ``{node: (floor, ceiling)}`` reach band, in the caller's
    frame, used to SOFTEN a quarantined anchor.
    ``stats_out`` — optional dict; receives the per-class surviving-anchor
    counts (the ★ measurement the spec requires reported).
    """
    from auto_patch.grade_graph import _open_ring
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    from auto_patch.layout import ROLE_APRON

    cps = layout.canonical_points

    def _index(x, y):
        return bucket_to_idx.get(cps.get_or_add(float(x), float(y)))

    _dump_path = os.environ.get("O4_APRON_R_DUMP")
    _dump_xy: dict = {}
    if _dump_path:
        layout._apron_R_xy = _dump_xy
    # ── the apron fabric: rings, node indices, mesh edges, cap slabs ──────
    apron_nodes: set = set()
    non_apron_nodes: set = set()
    adjacency: dict = {}
    slab_by_pair: dict = {}
    shape_count = 0
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role not in PAVEMENT_ROLES:
            continue
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
        except Exception:                              # pragma: no cover
            continue
        if len(ring) < 3:
            continue
        if s.role != ROLE_APRON:
            # WELDED BOUNDARY (anchor class 3): any node this apron shares
            # with a graded neighbour is an ``R`` anchor at that
            # neighbour's value.
            for (x, y) in ring:
                i = _index(x, y)
                if i is not None and i < n:
                    non_apron_nodes.add(i)
            continue
        shape_count += 1
        idx = [_index(x, y) for (x, y) in ring]
        for p, i in enumerate(idx):
            if i is not None and i < n:
                apron_nodes.add(i)
                if _dump_path:
                    _dump_xy[i] = ring[p]
        # DIRICHLET graph: the shape's CDT edges (the mesh connectivity).
        for (pa, pb) in _apron_mesh_edges(layout, s, ring):
            u = idx[pa]
            v = idx[pb]
            if u is None or v is None or u == v or u >= n or v >= n:
                continue
            ax, ay = ring[pa]
            bx, by = ring[pb]
            d = math.hypot(ax - bx, ay - by)
            if d <= 1e-9:
                continue
            w = 1.0 / d
            adjacency.setdefault(u, []).append((v, w))
            adjacency.setdefault(v, []).append((u, w))
        # CAP SLABS: the shape's FULL baked pair set (see the module
        # docstring — an apron's law is its visibility graph, and R must
        # be projected onto the pairs the LAW binds, not onto the mesh
        # subset).  Tightest budget wins where a pair is minted twice.
        for (pa, pb), budget in _baked_budgets(layout, s, ring).items():
            u = idx[pa]
            v = idx[pb]
            if u is None or v is None or u == v or u >= n or v >= n:
                continue
            key = (u, v) if u < v else (v, u)
            if key not in slab_by_pair or budget < slab_by_pair[key]:
                slab_by_pair[key] = budget
    if not apron_nodes:
        return {}

    # ── anchors ──────────────────────────────────────────────────────────
    # ★ ANCHOR HONESTY LADDER (spec Track 1 step 1 / B.4 ★): hard hold →
    # un-quarantined ``elev`` → rod-held string → band-softened → REFUSED.
    # A quarantined value is never used raw; refusal is last because the
    # break regions are wide (830/904 HECA mega-ring vertices) and a naive
    # refusal strips the component's boundary conditions.
    _honest = _law_true_anchors() and broken_idx is not None
    _string_value = string_value or {}
    _band_of = band_of or {}
    fixed_value: dict = {}
    class_of: dict = {}
    tally: dict = {}

    def _keep(i, value, cls):
        fixed_value[i] = float(value)
        class_of[i] = cls
        tally[cls] = tally.get(cls, 0) + 1

    for i in apron_nodes:
        if i in pad_ref:                       # class 2 — pad ROD level
            _keep(i, pad_ref[i], "pad_rod")
            continue
        if i in hard_idx:                      # class 1 — this pass's truth
            _keep(i, elev[i], "hard")
            continue
        if not (i in spine_idx or i in non_apron_nodes):
            continue
        base = "spine" if i in spine_idx else "weld"
        if not _honest:
            _keep(i, elev[i], base)            # classes 1 and 3 (legacy)
            continue
        if i not in broken_idx:
            # inside its own [floor, ceiling] envelope — law-true.
            _keep(i, elev[i], base)
            continue
        _sv = _string_value.get(i)
        if _sv is not None:                    # rod-held string
            _keep(i, _sv, base + "_rod")
            continue
        _bv = _band_clamp(elev[i], _band_of.get(i))
        if _bv is not None:                    # band-SOFTENED
            _keep(i, _bv, base + "_band")
            continue
        # REFUSED: a quarantined value with no law-true substitute is not
        # an anchor.  The node joins the Dirichlet free set.
        tally["refused_" + base] = tally.get("refused_" + base, 0) + 1
    free_all = [i for i in apron_nodes if i not in fixed_value]
    if stats_out is not None:
        stats_out.update(tally)
        stats_out["anchors"] = len(fixed_value)
        stats_out["free"] = len(free_all)
        stats_out["honest"] = _honest
    if not free_all:
        return {}

    # ── connected components of the welded apron fabric ──────────────────
    parent: dict = {i: i for i in apron_nodes}

    def _root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for u, lst in adjacency.items():
        for (v, _w) in lst:
            ru, rv = _root(u), _root(v)
            if ru != rv:
                parent[rv] = ru
    component_free: dict = {}
    for i in free_all:
        component_free.setdefault(_root(i), []).append(i)
    # Slabs bucketed by component ONCE (a per-component scan of the whole
    # slab table is O(components × slabs) — 30 M string-free dict probes
    # at HECA scale).
    slabs_by_root: dict = {}
    for (u, v), budget in slab_by_pair.items():
        if u not in parent:                            # pragma: no cover
            continue
        slabs_by_root.setdefault(_root(u), []).append((u, v, budget))

    out: dict = {}
    components_solved = 0
    components_anchorless = 0
    stuck_total = 0
    for root, free in component_free.items():
        # a component with no anchor at all has no reference to build from
        # — leave those nodes on today's z_ref rather than inventing one.
        has_anchor = any(
            j in fixed_value
            for i in free for (j, _w) in adjacency.get(i, ()))
        if not has_anchor:
            components_anchorless += 1
            continue
        components_solved += 1
        z = _dirichlet_solve(free, adjacency, fixed_value)
        stuck_total += _pocs_slabs(z, fixed_value,
                                   slabs_by_root.get(root, ()))
        out.update(z)

    if stats_out is not None:
        stats_out["components_solved"] = components_solved
        stats_out["components_anchorless"] = components_anchorless
        stats_out["slabs"] = len(slab_by_pair)
        stats_out["anchor_contradiction_slabs"] = stuck_total
        stats_out["z_refs"] = len(out)
    _dump_reference(layout, label, out, fixed_value, pad_ref, spine_idx,
                    non_apron_nodes, hard_idx, elev, component_free,
                    parent, _root, class_of)
    if _debug():
        _breakdown = " ".join(f"{k} {v}" for k, v in sorted(tally.items()))
        print(f"    [apron-R]{(' ' + label) if label else ''} "
              f"{shape_count} apron shape(s), {len(apron_nodes)} node(s), "
              f"{len(fixed_value)} anchor(s) "
              f"[{'law-true' if _honest else 'raw-elev'}: {_breakdown}], "
              f"{components_solved} component(s) solved / "
              f"{components_anchorless} anchorless, "
              f"{len(out)} z_ref(s), {len(slab_by_pair)} slab(s), "
              f"{stuck_total} anchor-contradiction slab(s)")
    return out
