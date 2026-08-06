# Cycle 4 — final_grade_projection ingests the solve's law (target #1)

**Status: BINDING** (cycle-4 target #1, checkpoint ab00777 — ranked
first; lane/fix3b's merge waits on it). Mode: BUILD-COMPLETE-THEN-DEBUG.

## The defect (attributed, both fix-3 lanes)

`final_grade_projection` ([solve.py:5125], called twice from
`pipeline.py:5801` and `pipeline.py:6433`) is a SECOND AUTHOR: it
rebuilds a constraint set on the final rings (`_build_shape_constraints`
+ `build_unified_graph`) that is NOT the solve's law, then re-projects
the whole field against it.

Evidence:
- **fix-3A who_wrote** (HECA plateau, `who2/HECA_who_wrote.json`): the
  route solve writes a vertex (e.g. 95.98 m) and final_grade_projection
  overwrites it (70.57 m) — moves of ±9 to ±25 m on apron/junction
  vertices whose geometry the post-solve passes never touched. The
  checkpoint attributes ~10k of HECA plateau's 17.8k adjudicated rows to
  this pass.
- **fix-3B flat-world specimen**: the solve is handed the fan-ramp zone
  cap (5%, lane/fix3b `de2132e`), but this pass re-derives constraints
  without the handed budgets and re-projects the zone into
  median-10.24% surfaces — the fan acceptance failure that parked
  lane/fix3b.

Under the single-solve architecture (RULINGS 2026-08-03) every post-solve
value-writer is scheduled for ingestion or retirement. This pass's
legitimate residual job is exactly one thing: geometry that MUTATED after
the solve (planarize inserts, T-weld adoptions, merges, clip rebuilds)
acquires law pairs the solve never saw; those — and only those — need
projecting.

## The requirement (frozen: the ingestion pattern)

1. **One law, one source.** Every law input the solve consumed is
   captured ONCE at solve time as the carried law context on the layout
   — zone caps (fan-ramp handed budgets included), apron-terrace plan
   (already re-bound by shape identity — extend that pattern), rod/pair
   budgets, band anchors, crown space, ruleset. `final_grade_projection`
   consumes the CARRIED context verbatim. It may not re-derive any law
   input from raw shapes/roles where re-derivation can disagree with
   what the solve was handed. Carrying is by SHAPE IDENTITY and
   GEOMETRY, never node index (the rod-key lesson).
2. **Idempotence on untouched geometry.** A node whose ring geometry and
   law context did not change after the solve exits this pass within
   materiality (0.01 m) of its solved value. The projection's job is the
   post-solve mutation set, not a re-solve.
3. **No silent narrowing.** Where the pass finds a genuine law pair the
   solve never had (new inserted node), it projects with the SAME
   constraint constructors the solve used — shared code path, not a
   parallel implementation (the census-wrapper precedent).
4. Enumerate and close every divergence between the two constraint
   builds (the ±22 m class needs its divergent families NAMED in the
   report — which law input differed, per family). Fixing by deletion is
   allowed where the projection's constraint is simply wrong law.

## Acceptance

- **who_wrote is the reader** (harness `who_wrote.py`): on the HECA
  constant-DEM plateau, after the fix, no vertex outside the post-solve
  mutation set has `final_grade_projection` as its introducing author
  beyond materiality. Quote the before/after author table.
- HECA plateau adjudicated census (harness `census.py`, law-true):
  expected large drop from 17,806 (frame BASELINES.md); quote honestly
  whatever it is. Strictly decreasing is the debug-cycle bar.
- fix-3B fan specimen re-check: with the solve handed a 5% zone cap, the
  emitted zone censuses ≤5% + materiality after this pass (use the
  fix3b worktree's census `--zone-split` if helpful — read-only; do NOT
  merge fix3b in this lane).
- Unit suite: `tests/test_final_projection_snapshot_recapture.py`,
  `tests/test_kill_prep_round.py`, plus the solve twins blast.py names;
  fix forward any that encode the second-author behavior.
- HEAZ sentinel build stays green.

Build budget: 2× HECA plateau (before/after who_wrote) + HEAZ sentinel +
unit twins; canyon pair only if plateau lands. Materiality 0.01 m;
attempt cap 2 per divergence family; `.progress` heartbeat. Real-DEM
builds are gated off for this lane.
