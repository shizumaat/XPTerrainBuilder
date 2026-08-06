# Cycle 5 — One coordinate per solve node (the node-identity spec)

**Status: BINDING.** Rules the law question the c5split STOP escalated
(dossier: c5split worktree tmp/, instruments preserved there; the §12
"ramp growth" premise is FALSIFIED for CYXY — measured overlap
0.0012 m²; all 193 solver↔validator budget-key mismatches are
vertex-identity defects). Mode: BUILD-COMPLETE-THEN-DEBUG.

## The law

**A canonical solve node has exactly ONE plan coordinate.** The
canonical registry already treats coordinates within its weld tolerance
(0.5 m) as one identity — therefore any pass that mints a vertex within
that tolerance of an existing settled vertex is creating a
two-coordinate node, which is the defect (one node, two ring positions
⇒ the solver and the coordinate-keyed validator read different laws on
the same pair). Geometry that relies on sub-tolerance distinctions is
already identity-merged by the registry and cannot be load-bearing.

## RULING (2026-08-06, spec author — resolves the lane's STOP)

The lane falsified Fix P's literal premise (2 pairs near settled
vertices; 884 pairs minted by the cut itself against the corridor
cover's `buffer()` arc, whose vertices are spaced ≈ the weld
tolerance) and proved the direct collapse (193→5) pushes 1.289 m² of
ramp inside the movement corridor. The keep-out vs node-identity
contradiction resolves by construction:

1. **The movement-surface keep-out binds at ZERO tolerance against the
   TRUE cover, always** — no ramp inside it, the structural law is
   untouched, and the existing twin stays as-is.
2. **The fan/terrace zone is CONSTRUCTED against a lattice-coarse
   SUPERSET of the true cover** — e.g. `cover.buffer(t·1.01).simplify(t)`
   (implementer picks the exact coarsening) with two proven
   properties: (a) it CONTAINS the true cover (keep-out strictly
   holds — a superset only protects more), (b) its boundary vertex
   spacing exceeds the weld tolerance (the cut is born satisfying the
   node-identity law). Twin both properties.
3. Consequence, accepted: the declared 5% zone area shrinks slightly.
   Lawful — the wall/step fallback covers whatever the smaller zone
   cannot span (fan-ramp law precedence, RULINGS 21f0980).

## Fix P — pre-solve half (99 of 193): cut on the settled lattice

`split_aprons_at_fan_zones` (and the terrace panel cut) runs AFTER
`_unify_airside_geometry` settled the airside node set, and its boolean
difference mints near-twin vertices (measured: 23 welded-but-distinct
at cut time, worst 0.4756 m). Required: SNAP the zone polygon's
vertices to existing settled vertices (within the canonical tolerance)
BEFORE the boolean difference, so the cut is born on the settled
lattice and no sub-tolerance vertex is ever minted. The ramp/panel
boundary is then shared by construction — nothing to re-derive, no
tear. The falsified alternative (weld AFTER the cut without
re-deriving the partition) is FORBIDDEN: it measurably tears the
boundary (0.1384 m² self-overlap, attempt-1 evidence).

## Fix Q — post-solve half (94 of 193): planarize snaps, never twins

`conformance.planarize_airside` inserts vertices within the weld
tolerance of existing ring vertices (+670 near-duplicate pairs at
stage 09), and `_dedup_coincident_ring_vertices` cleans only at
0.05 m. Required: an insert landing within the canonical weld
tolerance of an existing ring vertex REUSES that vertex (snap), never
mints a twin. Do NOT raise the dedup tolerance to 0.5 m ring-wide
(that deletes legitimate short edges); the dedup keeps its 0.05 m and
the tolerance mismatch gets a comment stating this spec's rule.
Value handling on snap follows the existing insert-value law
(interpolated along the ring edge — crown-consistent, see
crown.extend_field_to_new_ring_nodes).

## Acceptance

- `test_single_graph_acceptance.py::test_solver_validator_same_edge_budgets@CYXY`
  GREEN (193 → 0; quote the residual if any survives with its half).
- `test_pavement_geometry.py::test_no_self_overlap` stays GREEN at
  CYXY (the invariant attempt 1 broke). SPJC's PRE-EXISTING 1.5289 m²
  self-overlap failure is a standing defect — report whether these
  fixes move it (same mechanism family is plausible); do not chase
  beyond attempt cap.
- Census A/B on the CYXY fixture patch: expected ≈zero-delta (the
  mismatched pairs already satisfy the strict 1% reading); quote it.
- Fan/terrace twins + harness twins + the divergence-summary
  instrument (94/94 intra-ring class) reading 0 on minted pieces and
  on final rings.
- Reuse the preserved instruments in the c5split worktree tmp/
  (attrib_edges.py, ring_timeline.py, ckpt_probe.py); the CANDIDATE
  diff is evidence of the falsified approach, not a starting point.

Budget: CYXY fixture builds (~40 s each) + suite subset + one census
A/B. Materiality 0.01 m; attempt cap 2 per half; heartbeat.
