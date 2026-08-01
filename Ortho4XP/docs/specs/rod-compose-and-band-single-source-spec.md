# Rod composition at decimation + reach-band single source

Owner approvals 2026-07-29 (post-audit): (1) the rod fix is the
COMPOSE-AT-DECIMATION design; (2) fix the raster engine's exclusion and
converge the reach band to a SINGLE SOURCE, deleting the legacy paths.
Both parts execute under the standing single-pass principle (memory
`single-pass-principle`) and the audited facts in memory
`rod-carry-loss-is-emit-decimation` + spec
`single-space-string-audit-spec.md` (its instrumentation and tests are
in the tree and are the measurement harness for this work).

## Part A — rod links compose across decimated runs (APPROVED design)

Audited fact: 100 % of rod-link loss into `final_grade_projection` is
`emit_decimate.decimate_emit_nodes` DELETING strung 3D-collinear ring
vertices (13,680 at HECA); registry stable, all other passes clean.

**Semantics (fixed):** when decimation removes a run of strung vertices
between survivors S1..S2, the rod links spanning the run are replaced
by ONE link (S1, S2) with interval `[ΣΔᵢ − Σεᵢ, ΣΔᵢ + Σεᵢ]` — the
exact interval sum of the removed chain (the pass's own kept-pair
grade is already the length-weighted mean of the removed sub-segments,
so composition is exact, not approximate).  A corridor whose vertices
survive keeps its links untouched.  No re-stringing, no transport
machinery, no new spaces.

**Implementation freedom:** compose either inside `decimate_emit_nodes`
(it knows the runs) or at the carry site consuming a removed-run record
the decimator emits — whichever keeps the rod store single-writer.
Gate `O4_ROD_COMPOSE` default ON, `=0` restores today byte-identically.

**Acceptance (measure, don't assume):**
* Re-run the rod audit (`O4_ROD_CARRY_AUDIT=1`): dropped-by-decimation
  = 0; carried + composed accounts for every minted link (report the
  composed count).
* HECA emitted patch: seam site stays in the ~106 class
  (`seam_site_probe.py`); corridor sag vs the taut chord improves from
  the current 2.29 m toward the ≤0.5 m class — report the number
  (residual sag beyond the rod is a finding, not a silent pass).
* CYXY carry (was 25 %) — report the new figure.

## Part B — reach band: one engine, route-metric, service-excluded

Audited facts: `reach_band_unified` contains a raster engine
(config-default ON while the adjacent comment claims OFF), a legacy
nearest-visible-centerline path serving raster-None queries (per-query
ENGINE MIXING within one building's ring), and a `_build_skeleton_band`
fallback with no service filter.  The raster engine under-credits 8.7 m
on the U-fixture when a service route crosses APRON pavement (strict
xfail in `tests/test_service_spine_feasibility_exclusion.py`) — it
propagates through the paved GRID, an area metric, where the legacy
band propagates along centerlines, a route metric.  This is the same
area-vs-route class as the burial's pair web, on the seat side, biasing
seats LOW.

**Semantics (fixed — matches every 2026-07-29 ruling):** the band at a
point = anchor values propagated along NON-SERVICE airside routes at
the applicable caps, plus the local off-route leg — the same
route-metric semantic as the pair-pricing oracle and the seats'
reachability ruling ("airside reachability never rides service roads or
groundside; the taxi route graph is the metric").  Grid/raster remains
legitimate as a QUERY/lookup acceleration; it must not change the
metric.

**Work:**
1. Make the raster engine route-metric and service-excluded: propagate
   the value fields on the unified spine graph minus
   `service_spine_pairs` (exactly the set the legacy value-field path
   honors), and use the raster only to answer point lookups
   (nearest-attachment reads).  The strict xfail MUST become a PASS.
2. SINGLE SOURCE: delete the legacy per-query nearest-visible-
   centerline path, the raster→legacy fall-through (engine mixing), and
   `_build_skeleton_band` + its call sites.  Owner directive: legacy
   paths are deleted, not gated.  The `O4_RASTER_REACH_BAND` gate goes
   with them (one engine needs no selector); `O4_REACH_NO_SERVICE_
   SPINES` stays (it gates the LAW, not the engine).
3. Reconcile the config-default/comment/STATUS contradiction in
   whichever direction survives (there is only one engine afterwards —
   fix the stale comments).

**Acceptance:**
* `tests/test_service_spine_feasibility_exclusion.py` — all 6 PASS
  (xfail promoted; A/B refutation test updated if it patched the gate).
* Unit suites green (`-k "grade_graph or grade_law or taut or
  pavement_scoring or feasibility or bounded"`).
* HECA: report seat levels for building199/building199-class pads
  (expected ≥ the current 101.13 — the under-credit removal can only
  raise band ceilings) and the seam site.  Flat fixtures CYXY/SPJC/
  SPLP: report within-shape counts + step/tear sections (semantic
  change — deltas are expected and must be REPORTED, not hidden;
  byte-identity is explicitly NOT a goal here).

## Sequencing and the one full battery

Part A first (small, independently verifiable via the audit), then
Part B, then ONE full battery on the final state (owner: tests run
once, on the final architecture): `O4_TEST_AIRPORTS=HECA pytest
tests/test_spine_taut_string_heca.py tests/test_pavement_grade.py -k
HECA -n0 -s` + the flat fixture builds.  Report the complete matrix.

## Constraints (all have bitten)

Main tree `/Users/noah/XPTerrainBuilder/Ortho4XP`, venv python, builds
from that cwd only, output to files never pipes, one build per process,
no KCLT.  ANOTHER SESSION IS LIVE-EDITING THIS TREE (its 16:48 commit
`16d30c9` swept audit files): `git log --oneline -2 && git status
--short` before AND after every build; if the tree changed mid-
measurement, re-run the arm (memory: concurrent tree edits confound
A/Bs; omnibus commits sweep — clean status ≠ lost work).  Never
commit/stash/revert.  Do not modify the bounded-yield/§7 semantics
(`bounded-yield-spec.md`); the rod store you compose into is its
neighbor — extend, don't alter.  PID/artifact-verify every wait with a
timeout arm.  STATUS.md: top blocks only.  STATUS/memory documentation
is the parent session's job — report, don't write there.
