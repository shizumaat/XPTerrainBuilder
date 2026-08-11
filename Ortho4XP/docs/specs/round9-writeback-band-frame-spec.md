# Round 9 — the writeback clamp reads THE band, in THE frame

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **bandfix**. Pre-ship mode
(docs/RULINGS.md "PRE-SHIP DEVELOPMENT MODE") — unit tests for changed
behaviour, run once; deviations STOP-and-report to the Fable lead, never
decided in-lane.

## Context (attributed 2026-08-11, ledgered evidence)

App 1.0.233 fails EVERY airport build at `assert_no_final_band_inversion`
(pipeline.py:6794): floor above its OWN hard runway/seam value by exactly
one crown (0.15–0.30 m per airport), zero route distance. Bisected to
Round 8 (`ab2c61a`), R8-2's `_writeback_reach_band`. Fastpath exonerated
(`O4_FLAT_SITE_FAST_PATH=0` changes nothing); G-RUNWAY-CONTACT only feeds
crowned nodes in (disarming it removed 1 of CYXY's 4).

TWO coupled defects, both in the writeback-time band REBUILD
(`solver_primitives._writeback_reach_band`):

1. **Crown-frame lift.** The rebuild runs AFTER `build_crown_drop_field`
   publishes `layout._crown_drop_key` (solve.py ~4559) but BEFORE the
   writeback stamps shapes, so `_decrowned_anchor_seeds` (premise:
   anchor values are emitted-space) adds `crown_drop_at` to values that
   are still PROFILE-space — every crowned runway-join seed node gets
   `floor = own hard value + crown`. The failing frames stamp
   `crown_keys=293` where solve-time band builds see an empty field.
2. **Snapshot overwrite.** `reach_band_unified` → `spine_value_fields` →
   `_record_band_inversions`, whose scope is "the LAST output of the
   build". The rebuilt, crown-shifted snapshot replaces the real final
   band record, and the post-solve law assert judges the wrong band.
   The R8-2 purity fence restores the two `_build_node_list` attrs but
   not `_final_band_inversions` / `_final_band_node_count` /
   `_band_anchor_provenance`.

Additionally the clamp as shipped compares EMITTED-space corner values
(`_elev_emit = z′ − c`, solve.py ~4725; final projection likewise applies
the crown transform back before its `_writeback`) against a PROFILE-space
band — a third frame error, masked at seed nodes by defect 1.

## The law

**One band.** The band the solve computed (`node_band`, solve.py:2264) is
THE band — the solve, the validator, the census, the envelope and now the
clamp all read it. A second band construction is a second law
(`_writeback_reach_band`'s own docstring); it is DELETED, not fenced.

### §1 Carriage: mint THE band once, unconditionally

* In `solve_route_profile`, immediately after `node_band = node_bands(...)`
  (solve.py:2264), mint the store artifact:

      _store_of(layout).mint(
          "env_band", "interval",
          {key: (float(b[0]), float(b[1])) for key, i in
           bucket_to_idx.items() if (b := node_band[i]) is not None},
          replace=True)

  (Adapt to the existing mint idiom at solve.py ~5174 — same artifact
  name, same kind, keyed by canonical key, PROFILE space.)
* REMOVE the `_ENV_FROM_BAND`-gated mint at ~5174 (subsumed — it minted
  the same list later and only under the gate; note the shipped ordering
  bug: it ran AFTER the stage-6 `_writeback`, so the clamp's primary call
  site could never have read it). The envelope CONSUMPTION in
  `final_grade_projection` (~7348) stays gated exactly as today.
* Recon fact you may rely on: `node_band` is never mutated after
  construction (reads only). If you find otherwise, STOP and report.
* Born-at-Z0 fast-path nodes are `None` in `node_band` (skip_idx) — they
  simply have no key; the clamp reads off-net there. No special case.

### §2 The clamp resolves the carried band

* `_writeback(layout, elev, bucket_to_idx, band=None)` keeps its
  signature. `band` remains a `(x, y) -> (floor, ceiling) | None`
  closure (hermetic tests pass one directly).
* When `band is None`, `_writeback` builds the closure from the store:
  `raw = _store_of(layout).raw("env_band")`; lookup by canonical
  registry `find_nearest(x, y, reg.tol_m)` → key → interval — the
  `crown.crown_drop_at` idiom verbatim (same registry, same tolerance).
  Registry or artifact absent/empty ⇒ closure is `None`:
  **no value is clamped** and ONE `[writeback-band]` vprint(1) WARN says
  so ("no carried band — writeback unclamped"), preserving R8-2's
  loud-when-inert doctrine.
* DELETE `_writeback_reach_band`, `_NODE_LIST_PUBLISHED_ATTRS`,
  `_BAND_ATTR_ABSENT` (no callers outside solver_primitives; tests do
  not reference them). No node-list rebuild, no graph build, no
  `reach_band_unified` call remains anywhere in the writeback path.

### §3 The frame conversion: clamp in profile space

In `_clamp_corner_elevs_to_band`, per corner point:

    c  = crown_drop_at(layout, x, y)        # 0.0 when field absent/empty
    v' = v_emitted + c                      # lift to profile space
    clamp v' into [floor, ceiling] with WRITEBACK_BAND_CLAMP_MATERIALITY_M
    stamped = clamped' − c                  # back to emitted space

* Identity when the crown field is empty (both call sites before crown
  computation, hermetic tests) — byte-identical to a frameless clamp.
* The finding tuple is unchanged in shape; `delta_m` stays
  `stamped − v_emitted` (emitted-space, same magnitude as profile-space).
* Import `crown_drop_at` lazily inside the function (import-weight law).

### §4 Scoping preserved (no behaviour change beyond the frames)

* ROLE_RUNWAY stays out of clamp scope (CIFP-hard, checker-exempt).
* `WRITEBACK_BAND_CLAMP_MATERIALITY_M = 0.01` unchanged.
* `band_clamp_findings` / `_record_band_clamp_findings` unchanged.

## Tests (tests/test_round9_writeback_band_frame.py, new; adapt
tests/test_round8_vhhh_closeout.py R8-2 cases to the carried-band API)

1. **Crowned-seam twin (the shipped regression):** layout with a
   crown field entry (+0.23) at a hard runway/seam seed node whose
   carried band floor equals its hard value; after `_writeback`:
   value unclamped, zero findings at that node, and
   `_final_band_inversions` / `_final_band_node_count` /
   `_band_anchor_provenance` are IDENTICAL objects/values before and
   after (the writeback records nothing).
2. **Frame round-trip twin:** at a point with c=0.30, an emitted value
   exactly at (profile floor − 0.30) is NOT clamped; the same value
   0.05 lower IS clamped up by 0.05 in emitted space.
3. **Canyon pin (R8-2's acceptance, preserved):** c=0 node, solved
   −12.5 against carried band (4.6, 9.4) clamps to 4.6 with one
   floor-side finding.
4. **Carriage twin:** after a solve with `O4_ENVELOPE_FROM_BAND` unset,
   `_store_of(layout).raw("env_band")` is non-empty and its values
   match `node_band` by canonical key.
5. **No-band twin:** empty store ⇒ writeback stamps exactly the
   pre-R8-2 values (no clamp), WARN emitted once.
6. Existing `tests/test_final_band_inversion.py` passes untouched.

## Acceptance (the blocker itself)

* Harness builds complete: `build_airport.py CYXY` (was 4 inverted
  nodes) and `build_airport.py KCLT` (was 26) — rc=0, sidecars written,
  zero `floor_above_own_hard_value` rows. Run via the run ledger.
* Unit tests above, once.

## Versions / bookkeeping

* Engine `1.50.1679` (src/O4_Version.py), app `1.0.234`
  (Sources/XPTerrainBuilder/Resources/VERSION) — bumped at merge, not in
  the lane.
* One DEFERRED_VERIFICATION.md line: verification limited to CYXY/KCLT
  builds + the unit twins; no battery A/B, no census, no timing arm
  (the deletion of two graph builds per airport is a cost REMOVAL and is
  not claimed as a measured speedup). The ledgered interventional
  band-escape attribution (which stage wrote −12.5 at VHHH) is
  UNCHANGED — the clamp is containment, this round fixes its frame.
