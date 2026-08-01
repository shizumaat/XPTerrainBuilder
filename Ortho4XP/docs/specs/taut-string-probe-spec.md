# Taut-string probes: the mover ledger and hook-time attribution

Fable spec, 2026-08-01. Serves Ruling 55 separation (ii) (the mover ledger)
and HANDOVER §5 defect 4 (hook-time band violations). Both probes are
**measurement instruments**: gated off by default, write-only, zero behaviour
change. Line numbers are against branch `taut-string-chord-model` @ `d424c9d`
and were verified by reconnaissance on 2026-08-01.

## 0. Non-negotiable constraints

1. **No behaviour change when gates are off or on.** Probes read `elev` and
   copy; they never write it, never mutate `u_spine_adj`, `_hard_cat`,
   `bucket_to_idx`, or any set the solver iterates.
2. **No module-global state** — `feasibility_project` is re-entered from
   `final_grade_projection` (solve.py:4535), `_solve_spine_profile` (:5952)
   and the flat fast path. All probe state passes as an out-parameter dict,
   following the existing `probe_out` / `broken_out` idiom
   (write-only inside the callee; `None` in production).
3. **No snapshot inside the `_t_fp8` timing window** (solve.py:1981/:1996) —
   the `[spine-yield]` line is a published A/B number.
4. Role filters (if any) go through the `ROLE_*` constants, never fresh
   string literals (blast.py hazard: 11 role literals in solve.py).
5. Gate-off byte identity must be re-proven after landing (SPLP + CYXY body
   hash, `tail -n +3` past the provenance stamp — HANDOVER §3 hashes).
6. Build-time impact statement: gate-off cost is a handful of `None`-checks;
   gate-on cost ≈ tens of ms (watch-set diffs over ~10k nodes at ~7
   boundaries). Both are far under the 1 % / 0.6 s review trigger; the
   gated-off default keeps the hard law satisfied.

## 1. Probe A — the mover ledger (Ruling 55 separation (ii))

**Question answered:** for each `pin_yield_conflicts` row, which stage last
moved the **free member** to its conflicting value before the ledger is
computed at solve.py:1461-1490.

**Identity:** none needed. Pins (`_string_pins` keys), conflict `pin` /
`neighbour` fields, and `elev` indices are all raw solver node indices in one
space. Additionally add `pin_key` / `neighbour_key` (canonical keys) to each
conflict row for offline geometry, reusing one of the two reverse maps
already built nearby (solve.py:1307, :1832) — never build a third.

**Gate:** new env var `O4_STRING_MOVER_LEDGER`, default `"0"`. Active only
when `"1"`. Output rides the existing `string_domains` sidecar (needs
`O4_STRING_WITNESS_DUMP` set, as today); no new artifact file.

**Mechanism — stage-boundary diff over a watch set:**

* Watch set `W` = conflict-eligible population = every spine node that is a
  kept pin ∪ its `u_spine_adj` neighbours (~10k at HECA). Built once, right
  after `yield_hard |= kept pins` (solve.py:1407-1409).
* Baseline snapshot `{i: elev[i] for i in W}` taken immediately **before**
  the first spine-yield projection (solve.py:1447). Stages B–F cannot move
  spine nodes (spine is `base_hard` from :1000-1002), so no earlier
  boundary is needed.
* Stage G (`apply_service_road_dem_follow`, solve.py:1187) already returns
  its moved set `_svc_moved` — record `W ∩ _svc_moved` as label
  `svc_dem_follow` without any diff.
* Diff-and-stamp after each of these four boundaries, in order:
  1. `proj_shape.blend` — inside the :1447 call, at the blend/sweep boundary
     (one_solve.py:2084), via the out-param: callee copies
     `{i: elev[i] for i in probe_out["watch"]}` into
     `probe_out["post_blend"]`. Caller diffs it against baseline.
  2. `proj_shape.sweep` — after the :1447 call returns.
  3. `proj_u.blend` — same out-param mechanism on the :1452 call.
  4. `proj_u.sweep` — after the :1452 call returns.
* A watch node whose z at every boundary equals baseline gets
  `unchanged_since_freeze` (its value is phase A's; the existing
  `O4_DUMP_SOLVE_STATE` `spine_stages` labels resolve further if ever
  needed — do not duplicate that machinery here).
* Comparison is exact float equality (`!=`), matching the recon's model —
  these are pointer-identical unless written.

**Delivery:** each `pin_yield_conflicts` row gains
`"neighbour_last_writer": <label>` (and `"pin_last_writer"` — same cost,
and the 88 law_anchor rows make the pin side interesting too), where
label ∈ {`unchanged_since_freeze`, `svc_dem_follow`, `proj_shape.blend`,
`proj_shape.sweep`, `proj_u.blend`, `proj_u.sweep`}. The sidecar summary
gains `mover_ledger_counts`: the label histogram over conflict rows.
`write_string_sidecar` is already last-call-wins (solve.py:1485-1486);
stamp before that call, exactly as the conflict rows are today.

**Extension (added 2026-08-01 after separation (i) landed): the pin-drag
tail.** Separation (i) proved G2 pin drag is REAL (identity-joined median
0.2520 m) and **broad — not concentrated on conflict rows** (with-conflict
median 0.2715 vs without 0.2450). The ledger-time window above therefore
cannot attribute it; the drag accrues somewhere between the conflict ledger
and emit. Under the same gate, keep diffing the watch set through every
subsequent `elev`-writing stage in the recon map, one boundary each:
`fp8` (solve.py:1982), `mouth_relax` (:2078-2091), `ring_fairing` (:2156),
`gap_spine_fairing` (:2183), **and both final-grade-projection passes**
(`final_proj_1`, `final_proj_2`) — amendment 2026-08-01: offline attribution
proved a both-ends-kept-pin violation (HECA nodes 16957/16958, pins lawful
at dz 0.000) was minted **inside final pass #2**, after every existing dump;
pins are Dirichlet only in the phase-A spine solve and nothing downstream
holds them, so a tail that stops at the emit copy cannot attribute the drag.
Take the final-pass boundaries at each pass's entry and exit in the
uncrowned frame (the crown is added/subtracted inside that machinery —
diff crown-free values only). The LAST boundary must equal the values the
.osm will spell (post-rounding excluded; quantisation is not a mover).
Deliver in the sidecar summary: `pin_drag` = per-kept-pin
rows `{vertex, pin_z, z_at_emit_copy, last_writer}` (~3.8k rows, same order
of size as the conflict table) plus a `pin_drag_counts` histogram
(label → count, and label → median |Δz|). Crown is not in this frame —
`elev` is uncrowned until the writeback, matching G2's frame.

## 1x. PURITY AMENDMENT (2026-08-01, round 6) — the stage-boundary probe
MUTATES and must be fixed

Round 6 proved interventionally that `O4_STRING_MOVER_LEDGER=1` changes
the emitted surface at SPJC (+1 node, 86 altitudes, |dz| ≤ 0.21 m):
`mover_stage_boundary` (solve.py:620 region) calls
`solver_primitives._build_node_list(layout)`, which calls the MUTATING
`layout.canonical_points.get_or_add(x, y)` — an extra insertion (and its
order) changes which vertices intern at the 0.5 m snap, and the registry
feeds `emit_stacked_conflict_walls` and `to_osm` consensus. The probe's
own helpers are read-only as documented; the leak is the node-list
rebuild.

**The fix (required before any further probe-on arm is quoted as
production):** `mover_stage_boundary` must resolve its watch keys through
a READ-ONLY view — look keys up in the registry's existing contents
(a get-without-add query; add one to the registry API if none exists,
itself read-only) and skip keys not present. A watched key absent from
the registry at that seam is reported as `n_unresolved`, never inserted.
Acceptance: with `O4_STRING_MOVER_LEDGER=1`, the emitted body hash
equals the probes-off hash at SPJC (the airport that caught it) AND at
HECA; the ledger still stamps (stage_moves populated); a unit test locks
the no-mutation property (registry size before == after every
`mover_stage_boundary` call).

## 2. Probe B — hook-time band-violation attribution (defect 4)

**Question answered:** which upstream writer put 90 of 966 banded corridor
nodes above their own ceiling before the S1 hook.

**Fact base (recon-verified):** the band is frozen at solve.py:660-683 and
is not a function of `elev`; the only `elev` writers before the hook are
P0 (`_seed_elevations`) and P1-P5 hard-anchor stamps, of which P2-P5 run
after the band froze; `_hard_cat` (solve.py:762-892) already names the
stamp category per hard node; the hook-entry state dump already exists
(`O4_STRING_STATE_DUMP`, taut_string.py:1818-1834) and
`construct_taut_strings` never writes `elev`.

**Change (minimal):**

1. Pass `hard_cat` into `construct_taut_strings` as a new optional
   keyword (default `None`), supplied at the solve.py call site (:945) as a
   **copy**: `dict(_hard_cat)`.
2. The `O4_STRING_STATE_DUMP` pickle gains two fields:
   `"hard_cat"` (that copy) and `"have_initial"` (the third return of
   `_seed_elevations`, currently bound unused at solve.py:427 — it splits
   P0 into layout-warm-start vs DEM-sample).
3. No new gate, no new snapshot, no other change. Attribution runs offline
   from the one pickle: every violator is either in `hard_cat` (category
   names the writer) or is a P0 seed (split by `have_initial`).

## 3. Acceptance criteria

1. Full existing suite for solve.py's test set passes (blast.py list:
   test_final_projection_snapshot_recapture, test_late_hard_set_vectorization,
   test_one_solve_gap_spine, test_reference_honesty, test_rod_compose,
   test_runway_end_resa_admission, test_spine_fair_through_welds,
   test_torn_datum_pin_release) plus test_spine_taut_string_heca. Run via
   `venv/bin/python tools/run_with_ledger.py -- ...`. Known-red context:
   24 stable comparator failures across 9 files and 5 test_crown_seam_ramp
   reds predate this work — do not chase them, do not add to them.
2. One new headless test (tmp_path-based) asserting: gates off ⇒ sidecar
   rows carry no `neighbour_last_writer` and the state dump carries no
   `hard_cat`; gates on (synthetic or smallest-fixture path) ⇒ both fields
   present and label values within the closed label set.
3. Gate-off byte identity re-proven: SPLP body `d8d0f065…`, CYXY body
   `dcebb6ff…` (or, if a sibling change landed first, three-way identity
   against a freshly-hashed pre-change baseline from the same tree).
4. One gate-on HECA build (`O4_TAUT_STRING_CONSTRUCTION=1`,
   `O4_STRING_MOVER_LEDGER=1`, `O4_STRING_WITNESS_DUMP` and
   `O4_STRING_STATE_DUMP` set) produces: conflict rows with both
   last-writer fields, the `mover_ledger_counts` histogram, and a pickle
   with `hard_cat`/`have_initial`.

## 4. Deliverable readings (measurement, after implementation)

* **(ii):** the `mover_ledger_counts` histogram over all conflicts, and
  separately over: the 88-class (`law_anchor`) rows, and chord 1's
  1400-1800 bin rows. Pre-registered expectation (Ruling 55): the free
  members concentrate in `proj_*.blend` / `proj_*.sweep` — i.e. a stage
  that manufactures an over-cap pair against a hard node.
* **(B):** the 90 violators split by `hard_cat` category ∪ P0-seed class,
  worst-case magnitude per category, and whether the dip-window 49 fall in
  a single category. No fix, no effect-size prediction — attribution only
  (mechanism before fix).
