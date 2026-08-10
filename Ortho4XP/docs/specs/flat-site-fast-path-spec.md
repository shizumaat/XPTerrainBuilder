# FLAT-SITE FAST PATH — spec (2026-08-10, FROZEN; pre-ship mode)

Author: lead (Fable). Charter: owner — "create the spec for the fast
path at flat airports and implement." Measured baseline (OTHH, the
11:43 build): steady-state patch ≈ 4.5 min of solver machinery over a
constant field — grade graph ~134 s, reach bands ~38 s, transition
features ~46 s, decimation ~21 s — while 71 % of emitted nodes sit
within 0.05 m of Z0. The answer is known before the solve starts.
PRE-SHIP MODE (docs/RULINGS.md): unit tests once; ONE OTHH patch
build allowed (solver change = sim-visible risk class).

## The law

On a `flat_candidate` / `flat_declared` site (gate
`FLAT_SITE_FAST_PATH`, default ON, env `O4_FLAT_SITE_FAST_PATH`; off
or non-flat = byte-identical to today), the solve PARTITIONS:

1. **ELIGIBLE shapes are born at Z0, not solved.** A shape is
   eligible when ALL of: (a) its role is a pavement/groundside/
   building family member (never runway/runway_crossing, never a
   tunnel/bridge/basin feature role, never boundary/adjacent-ground
   feature emission — those emit as today); (b) it lies entirely
   outside the runway strip envelope (runway_union ⊕ the strip
   margin the strip law already defines); (c) it lies beyond the
   below-grade transition reach (the R5 `transition_reach_m` distance
   from the below-grade union — ramps/trenches/portals/walls).
   Eligible shapes take the EXISTING fixed-plate route
   (`born_flat_solver_plate` idiom / equivalent fixed-value
   membership) at exactly Z0 — they contribute BOUNDARY VALUES but no
   free variables: no grade-graph rows, no reach bands, no route
   profile membership. A constant field satisfies every within/step
   law by construction.
2. **INELIGIBLE shapes solve fully** — runways keep the CIFP-absolute
   profile + crown machinery verbatim; strip/junction neighbors of
   runways reconcile the (sub-cap) transitions to the surrounding
   fixed Z0 exactly as they reconcile to any fixed neighbor today;
   below-grade features and their R5 transition surfaces solve their
   local laws against Z0 boundaries. THE SEAM IS EXACT: fast-pathed
   neighbors present the same Z0 the full solve would have converged
   to — proven by the equivalence twin, not assumed.
3. **Downstream cost follows:** reach-band computation skips eligible
   shapes; decimation treats constant spans at the chord cap (verify
   the existing `emit_decimate` already collapses constant interiors
   — if it keeps sub-cap nodes on constant spans, fix the tier
   there, don't add machinery).

CONSERVATIVE BY LAW: any shape the predicate cannot PROVE eligible
solves fully. Partition, never approximate.

## Tests (run once) — the equivalence twin is the spec

* Synthetic flat fixture (constant DEM, one runway, aprons/taxiways/
  service, one tunnel ramp): fast-path arm vs full-solve arm —
  every shared node within 0.01 m (solver quantum); eligible shapes
  exactly Z0; runway profile byte-identical between arms; transition
  surfaces identical within quantum.
* Eligibility partition cases: strip-adjacent junction ineligible;
  shape inside transition reach ineligible; plain apron eligible;
  gate off ⇒ byte-identical output.
* ONE OTHH harness patch build from the lane: report (a) phase times
  vs the 11:43 baseline (grade graph/reach bands expected to
  collapse; quote the ledger lines, non-comparative single run —
  no timing claims beyond order-of-magnitude); (b) node-value
  equivalence vs the owner's current patch on eligible-shape nodes
  (all Z0) and runway nodes (unchanged profile); (c) node/way count
  delta.

## Acceptance
Unit tests + the one build's three reports; owner sims OTHH on the
next rebuild. One deferred-verification line (battery inertness on
non-flat sites is by the gate + degeneracy twin, unmeasured on real
hilly builds until the ship gate).
