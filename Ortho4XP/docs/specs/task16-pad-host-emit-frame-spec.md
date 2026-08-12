# Task #16 — Pad-host level family in the EMIT frame (Fable spec, 2026-08-12)

Lead: Fable session (this spec's author rules on any deviation — implementers
STOP and report, never improvise; `docs/RULINGS.md` is canonical law;
PRE-SHIP DEV MODE is in force).

## Context (evidence, all ledgered)

R19-1 (object-pad reconciliation) shipped KNOWN-OPEN. Three mechanisms were
built and measured (`docs/DEFERRED_VERIFICATION.md:62`):

1. Lip-run walk (`PAD_HOST_BODY_REACH_M` 10 m, on main) — MISSES building114
   (host body 16.59 m out in production); widening re-opens the measured
   neighbour-swap class (HECA 140↔141, 146↔151, 210↔211).
2. Host-surface field sample (`e6a8f5f`) — MISS + regression (building112
   dragged 85.63→86.45; 53% of HECA's 214 pads have no pad-free host vertex
   within 25 m).
3. Level family + agreeing coalition (`569bc5f`, branch `lane/r19-1-coalition`)
   — EXACT on the owner artifact (building114 88.50→85.63, building189
   86.27→85.63, five pads move, building112 UNMOVED), but production arm
   `r19fam` still misses building114.

One root cause behind all three production misses: **the level family is an
EMIT-TIME structure.** `relevel_pads_to_host_pavement` runs post-solve,
pre-emit (`pipeline.py:6235`, checkpoint `20_post_projection_conformance`),
but the shared ring vertices that chain building114→189→112/113 are minted
LATER, by the final epsilon-wedge weld (`enforce_conformance(tol=0.01)`,
`pipeline.py:6542-6603`). Only 11 of 214 HECA pads share a host vertex with
another pad even in the emitted frame — shared-ring-vertex adjacency at
relevel time cannot see the family the weld will create.

## Rulings (this spec settles the open questions)

1. **Remedy = derive the family from the weld candidates** (owner-offered
   option (ii)), NOT moving the pad law after the welds. Reasons: the R17
   band-clamp-last-author law (`tests/test_r17_band_clamp_last_author.py:216`)
   stays intact — no authorship reordering; no post-weld re-projection /
   re-weld hazard; single-pass principle — compute the weld identity once
   and let the family consume it.
2. **The family relation becomes "will weld together":** expose the final
   weld's candidate predicate from the conformance module as a public,
   side-effect-free accessor (the SAME implementation the weld itself uses
   at `pipeline.py:6542-6603` — one code path, never a parallel
   re-implementation; the census-wrapper precedent applies). `_pad_lip_index`
   (`anchors.py:3844`) consumes it: two vertices are one lip node iff the
   weld predicate identifies them (its own tol, currently 0.01 m — do NOT
   invent a new tolerance; a new proximity join is forbidden, reuse of the
   weld's own law is the point).
3. **The coalition re-lands as part of this task.** The #16 lane branches
   from current main and MERGES `lane/r19-1-coalition` first (coalition
   `weight_of`/`tiebreak_of` extension, 16 twins, retired
   `PAD_HOST_BODY_REACH_M` signpost). It does not land separately.
4. **R19-3 object pads:** no production instance exists in this tree
   (`DEFERRED_VERIFICATION.md:63`); the twin remains sufficient. Object-pad
   branch continues to move core + blend plates by ONE delta. No new claim
   owed.
5. **Mechanisms 1 and 2 retire** once the weld-candidate family lands:
   mechanism 1's walk code path is superseded (leave the dead constant
   signpost from the branch); mechanism 2's `_surface_value_at` stays as
   the branch retained it (field reader, other consumers).

## Implementation plan (one Opus implementer, coupled change-set)

1. Merge `lane/r19-1-coalition` into the lane worktree; resolve; run its 16
   twins once (`tests/test_pad_host_pavement_level.py`) to confirm the merge
   is clean. Guard test `test_round12_bridge_deck_datum` must stay green
   (bridge-deck caller passes no weights — R12 byte-unchanged).
2. In the conformance module (where `enforce_conformance` lives): factor the
   candidate-pair enumeration used by the final epsilon-wedge weld into a
   public accessor, e.g. `weld_candidate_pairs(layout, tol)` returning the
   vertex-identity classes the weld would create. It must be PURE (no
   mutation) and share the exact geometry/tol code path with
   `enforce_conformance` — a twin test asserts the shared implementation
   (calling both on a fixture and checking the weld actually identifies
   exactly the predicted pairs).
3. `anchors.py:3844 _pad_lip_index`: build lip adjacency over the
   weld-identity classes instead of raw shared ring vertices (a pad and a
   host chain iff any of their ring vertices fall in one identity class).
   `_level_family_members` (`:3882`) unchanged in structure: union-find over
   the new adjacency; weights stay AREA; arbitration stays pad-adopts-from-
   host; the value-based lip test stays scoped to `PAD_HOST_LEVEL_LIFT_M`.
4. Tests: keep all 16 twins; add (a) the weld-predicate twin from step 2;
   (b) a production-shaped twin: two pads + host whose rings come within
   weld tol but do NOT share a vertex pre-weld — family must form and the
   small pad adopt the host level; (c) the negative: rings separated by
   more than weld tol never family (two-families twin already covers the
   separate-chain case).
5. Run the per-law test files ONCE via `tools/run_with_ledger.py`
   (check `--history` first); quote `blast.py` for touched files.

## Acceptance (named claims, HECA tile +30+031, --patch-only arm)

- PRODUCTION arm (not the artifact): building114 88.5x → 85.63 ±0.01 m;
  building189 → 85.63 ±0.01 m; building112 UNMOVED (85.63, ±0.01);
  no pad moves by more than `PAD_HOST_LEVEL_LIFT_M`.
- The 14 `building|building` ~2.87 m rows on ring `-10189` → 0.
- Census before/after quoted under the honest instrument (law-true frame,
  `grade-check` skill — never bare check_grade); LAW-TRUE delta explained
  row-class by row-class if nonzero.
- Shared repo UNCHANGED (guard active); rc=0; arm named in the ledger line.
- Swap class: buildings 140/141, 146/151, 210/211 each keep their own
  levels (the AREA weight makes swap structurally impossible — assert it
  measured, not argued).
- Convergence guards: materiality floor 0.01 m; attempt cap 2 (second miss
  = STOP and report to the Fable lead); progress heartbeat via `.progress`
  stamps in the lane scratch dir.
- Build-time impact statement required (weld-candidate enumeration runs
  once more per build — expected O(final-weld cost) ≤ its existing pass;
  if measured ≥0.6 s the ledger tripwire escalates per the suspended law).

## Out of scope

Tile build (consolidated lead-owned acceptance covers it); object-pad
production claim (ruling 4); any change to `to_osm` authority consensus;
mechanism-2 field sampling behavior.
