# Single-space string audit — why do 54% of rod links die in transit,
# and what stops the pipeline from stringing exactly once?

Owner rulings 2026-07-29 (rod key-carry discussion):

1. **Single-pass principle:** "We DEFINITELY want to avoid doing any
   task more than once whenever possible to maximize performance and
   quality." Target architecture: geometry settles → the string is set
   through the graph once → the solver applies elevations. No
   re-stringing, no transport across rebuilt spaces.
2. **Service roads are not feasibility paths.** They stay in the woven
   graph ONLY as the grading handle for the roads themselves; every
   feasibility consumer must exclude `service_spine_pairs`. The raster
   reach band (`O4_RASTER_REACH_BAND`, default OFF) is a KNOWN
   violator (does not honor the exclusion yet — STATUS 2026-07-29).

## 1. The defect this audits

The §10 taut-string rod carries only ~46% of its links into
`final_grade_projection`'s rebuilt node space at HECA (3,224 carried /
3,809 dropped; ~27% carry at CYXY). Links re-attach by rounded-position
"canonical keys"; a link needs BOTH endpoints to resolve. The measured
consequence is the residual 2.3 m corridor sag (taut-string test
failure) that survives every 2026-07-29 law fix. NOBODY HAS ATTRIBUTED
THE DROPS: we do not know which corridors lose links (taxi vs
service), nor whether endpoints physically MOVE between stringing and
the rebuild or merely RE-KEY (canonical-registry re-interning /
rounding differences — a documented behavior class: registry
renumbering has legitimately moved HECA's fixpoint before).

## 2. Probe (phase 1 — measurement only, no fixes)

1. **Instrument the carry** (gate `O4_ROD_CARRY_AUDIT=1`, default OFF,
   byte-identical when off): at the carry site (the taut-string code in
   `route_profile/solve.py` that prints `rod carried=N dropped=M`), for
   every DROPPED link log: both endpoint coordinates at mint time,
   which endpoint(s) failed to resolve, the corridor id, and whether
   the corridor's centerline `is_service`.
2. **One instrumented HECA build** (main tree cwd, venv python, output
   to a file never a pipe, no overlapping builds).
3. **Classify every drop:**
   * taxi vs service corridor;
   * for each failed endpoint: does ANY vertex exist in the rebuilt
     space within 1 mm of the mint coordinate?  YES → RE-KEYED (same
     physical vertex, different bucket/registry identity); NO → find
     the nearest rebuilt vertex and its distance → MOVED (report the
     distance distribution);
   * for MOVED endpoints: attribute the mover — bisect by dumping the
     vertex's coordinate after each candidate pass (junction repair,
     tile-cut seam nudge, emit-side T-weld/conformance, groundside
     mouth/parallel conformance, crown writeback) via targeted debug
     prints or a coordinate-watch hook; name the pass per drop class.
4. **Deliver the three-bin table** for every pass found to move or
   re-key strung vertices: (a) movable before phase A, (b)
   elevation-dependent — needs identity preservation, (c) removable /
   deferrable to emitted output.  Plus the headline verdict:
   MOVED vs RE-KEYED percentages, taxi vs service percentages.

## 3. Hardening (phase 1 deliverable, small and safe)

* New unit test: every feasibility-side consumer of the unified graph
  (reach band value fields, nearest-node lookup, route-distance oracle,
  raster reach band when enabled) REFUSES `service_spine_pairs` edges —
  so a future consumer cannot silently reintroduce service-road
  feasibility.  Expect the raster band case to FAIL initially (known
  violator): mark it xfail with a pointer here, or fix it if the fix is
  a filter-plumbing one-liner; do NOT redesign the raster band.

## 4. Explicitly out of scope (owner review comes first)

* Pipeline reordering, identity-preservation plumbing, registry
  unification, deleting the rebuilt space — phase 2, designed from the
  probe's table, after owner sign-off.
* Everything in `docs/specs/bounded-yield-spec.md` (landed,
  uncommitted): do not modify its semantics; instrumentation must not
  change any default-env behavior (hash-verify one flat fixture,
  audit gate OFF, against a fresh no-edit build if in doubt).

## 5. Context to read first

`Ortho4XP/CLAUDE.md`; STATUS.md TOP two blocks ONLY (~90k-token file,
never load whole); memories `heca-burial-composed-apron-law`,
`single-pass-principle`; probe kit
`tools/probes_heca_burial_20260729/` (seam/corridor probes, solve-state
dumps `heca_spineframe_state.pkl`).  Measurement traps: emitted patch
not dump; wall times contention-noisy, counts are not; KCLT builds OOM
— never build KCLT.
