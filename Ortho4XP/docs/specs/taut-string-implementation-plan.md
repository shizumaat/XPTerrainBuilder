# Taut-string consolidation — implementation plan (Opus-executable)

2026-07-30.  Companion to `taut-string-model-spec.md` (the model, the
measurements, the step definitions) and `node-space-unification-spec.md`
(U1).  Written by the Fable lead under the owner's scope ruling: **Fable
agents design and review; Opus agents implement.**  Owner's second
ruling: code already built during this design session **stays** ("no
sense throwing away code it already built") — steps below marked
STARTED point at it; do not rebuild what exists (single-pass principle).

Every implementing agent MUST read, in order, before touching anything:
`/Users/noah/XPTerrainBuilder/CLAUDE.md`, `Ortho4XP/CLAUDE.md`
(HARD LAW item 6 binds every step; working-style item 1a binds this
plan's loop), `Ortho4XP/src/auto_patch/CLAUDE.md`, the two companion
specs, and this plan's step section.  Then run
`Ortho4XP/venv/bin/python tools/blast.py <file>` for every file to be
edited.  Frozen public APIs may NOT be changed by an implementing
agent — if blocked, report back; do not improvise.

## THE DEVIATION RULE (owner ruling, canonical in CLAUDE.md item 1a)

**If reality does not match this spec or plan, STOP and report the
deviation for Fable review — do not improvise, do not "fix it while
you are in there."**  Implementers stop and report; they do not
decide.  The Fable lead is resumable with full context; a deviation
report costs minutes, a silent deviation costs an attribution round.
A deviation report contains: the step, the spec/plan text as written,
the observed reality (with the command/output that shows it), and the
options you see — and NO code written past the point of divergence.

Each step below carries an **EXPECT DIVERGENCE** block naming where I
already believe reality may not match — those escalate with zero shame
and zero hesitation — and a **FROZEN / DISCRETION** block so the
boundary between "escalate" and "your call" is explicit.  Anything not
listed as discretion is frozen by default.

**Spec authorship rule (owner, same ruling): Fable writes ALL specs.**
No Opus implementer authors or extends a spec, and no spec is
improvised inside an implementation brief.  Sub-spec registry
(2026-07-30 — the three anticipated specs are now WRITTEN):
* **S1 constructor** — `s1-taut-chord-constructor-spec.md` (step P3b);
* **R2 tube** — `r2-reference-tube-spec.md` (step P4);
* **R3 deletion diff** — `r3-flip-and-deletion-spec.md` (step P5);
* **U2** — unwritten, only if node-space phase 3 is ever pursued.
If a step uncovers the need for any OTHER spec, that is itself a
deviation: stop and report.

## Standing constraints (bind every step)

* Main tree `/Users/noah/XPTerrainBuilder`, cwd `Ortho4XP/` for builds,
  python `venv/bin/python` (no system python; `venv/bin/pip` broken —
  `python -m pip`).  The tree is DIRTY and SHARED: never `git stash`,
  never `git checkout`/`restore` files you did not edit, never commit
  without the owner asking.
* Correctness runs through the ledger: `venv/bin/python
  tools/run_with_ledger.py -- <cmd>`; check `--history` first.  Timing
  NEVER through the ledger: `tools/check_build_time.py --run --runs 3`.
* One build per process; build output to files, never pipes; no
  overlapping builds anywhere in the session.  NEVER build KCLT (OOM).
  **Waiter rule (P0c hit the failure):** a background waiter arms on
  the EXACT PID and re-verifies with `kill -0` after its loop exits,
  BEFORE acting on a clear — a false CLEAR while a build is alive is
  how a foreign run lands on an authorized build and corrupts both.
* Byte-identity = BODY hash (`tail -n +3 | shasum -a 256`), copied
  `src/` trees via `/tmp/gsw/build_alt_src.py <tree> <ICAO> <tag>` (cwd
  Ortho4XP/), three-way protocol (pre, post, pre again) so cache state
  is provably irrelevant.
* Validation ladder (taut-string spec §5.0) climbed IN ORDER; each
  step's build budget below is an honest total.  Escalate to the
  reviewer instead of exceeding a budget.
* Build-time law: any new code costing ≥ 0.6 s airport / 3 s tile needs
  the Fable-5 optimization review BEFORE landing; every step report
  carries a build-time statement.

## Hand-off artifacts (already on disk — verify, then reuse)

| artifact | where | what |
|---|---|---|
| U1 store + migration | in-tree (see P1) | landed, byte-identity proven |
| pre-U1 reconstruction | `/tmp/tautstring/src_pre/` | current tree minus the 16 U1 hunks |
| frozen post-U1 tree | `/tmp/tautstring/src_post/` | the proven arm |
| U1 hunk ledger | `/tmp/tautstring/u1_hunk_ledger.py` | every U1 edit as (file, new→old); its inverse is the exact change list |
| identity evidence | `/tmp/SPLP_u1_{pre1,post,pre2}.osm`, `/tmp/CYXY_u1_…`, logs in `/tmp/tautstring/` | SPLP `d8d0f065…` ×3, CYXY `dcebb6ff…` ×3 |
| build-time statement | `/tmp/tautstring/cbt_postU1.log` | CYXY 35.97 s median (3 runs), PASS, −8.44 vs baseline |
| witness tool | `tools/probes_heca_burial_20260729/owner_chord_probe.py` | W-CHORD1/W-CHORD2 gates; run on any emitted HECA patch |
| round patches | `/tmp/HECA_eb{OFF,ON,PRE1,PRE2,DIAG}.osm` + `.axes.json` | zero-build measurement inputs |
| solve-state dumps | `/tmp/bandq/heca_band.{01_fp8,02_final,03_final}.pkl`, `tools/probes_heca_burial_20260729/heca_spineframe_state.pkl` | offline replay inputs |
| owner KML | `/private/tmp/HECA_seam_site.kml` | dip corridor + seam sites |

`/tmp` is volatile across reboots: if any `/tmp/tautstring` artifact is
missing, the hunk ledger's inverse + the in-tree files reproduce
`src_pre`/`src_post`; the patches/dumps regenerate only via builds —
ask the reviewer before minting one.

## Step P0 — suite baseline + R0-v  [COMPLETE 2026-07-30]

**RESULT (measured, two independent clean full-suite runs, tree
`50f45b49d849`):** 25F/3848P/18S/7xf (`taut-P0-baseline`, 515.11 s)
and 24F/3849P (validated harvest).  Diff: 24 shared, one unique flake
(`test_layout.py::test_to_osm_is_idempotent`).  **CORRECTED by P0b
2026-07-31: the "3/3 in isolation ⇒ suite-context dependent" reading
recorded here was FALSIFIED — the true isolated failure rate is
~2/20 (~5-10 %/execution), which alone explains the suite
observations; the 3/3 was an underpowered sample (see the spec
§5.0's powered-sample rule).  Cache warmth and xdist context are
definitively EXCLUDED (audit-hook trace: the test writes only in
$TMPDIR, touches no caches, runs no builds).**  **The 24F comparator
is confirmed and normative (spec §5.0).**  `test_node_space.py` 49/49 in
both → P1's outstanding acceptance item CLOSED.  **R0-v answer: the
10 airport-build tests fail at OFF too — §1.7's "green suite" leg is
falsified (see the spec's P0 falsification note); R0 stands on the
lawfulness grounds alone (Fable ruling 1).**  The original step text
follows for the record.

## Step P0b — emission-determinism probe  [CLOSED 2026-07-31 BY
ATTRIBUTION — clean interventional pair, zero builds]

**Attribution:** `to_osm` stamps `o4_provenance_built` — a
whole-second wall-clock timestamp (`provenance.py:285`) — into the
OSM ROOT element; the test compares FULL file text; two emissions
straddling a second boundary differ in exactly that attribute.  All
9 captured failures: 2 changed lines, both the timestamp, geometry
byte-identical.  Clean pair: forced boundary-straddle 8/20 fail;
clock frozen 0/20 (and 0/100 on the live path) with emit slightly
SLOWER frozen — the null is not speed.  Predicted rate from the emit
window (54-59 ms) 5.4-5.9 % vs observed 7.5 % — consistent.
Confounded arms (provenance off — also removes the git subprocesses,
emit 54 → 1.8 ms) were discarded, correctly.
**Consequences:** (i) the P0 "suite-context" premise corrected above;
(ii) **R3's precondition is SATISFIED BY MECHANISM** — the
nondeterminism is confined to the root line that the body hash
(`tail -n +3`) excludes, so U1's six matches and every identity
proof in this line stand by mechanism, not just protocol (this stamp
is the very reason `patch-ab-integrity` mandates body hashing);
(iii) the test fix is step P0c; (iv) the 52-of-54 ms git-subprocess
emit overhead + the should-output-carry-wall-time design question go
to P6/R6.  The original probe protocol follows for the record.

## Step P0c — idempotency-test fix  [NEW, SPEC'D HERE — Opus-
executable, zero builds, land any time before P5]

**Fix (Part 1, test-only; no emission change):** rewrite
`test_to_osm_is_idempotent` to assert the institution's identity
contract: (1) the two emissions' BODIES (`tail -n +3` semantics) are
byte-identical; (2) the root-line diff, if any, is confined to
EXACTLY the `o4_provenance_built` attribute — so a real root-line
regression cannot hide behind the exclusion; (3) the assertion
message states the true semantics (provenance stamp is wall-clock
metadata; the body is the identity object) — the current message
("the first call mutated layout state") asserts a cause the captured
diff falsifies and is part of why this resisted attribution.
**Acceptance:** the P0b reproduction technique INVERTED — with a
forced second-boundary straddle the test must now PASS; 100
double-emissions green; the three assertions each independently
trip on a synthetic violation (mutate a body byte; mutate a non-
timestamp root attribute; both must fail the test).
**EXPECT DIVERGENCE:** if the test's fixture layout emits MORE
root-line variance than the timestamp (it should not, per the
captured diffs), STOP — that is a new finding, not something to
widen the exclusion for.
**FROZEN:** the three assertions; no emission-side change in this
step.  **DISCRETION:** implementation of the root-line comparison.
**Part 2 (NOT this step):** whether emitted output should carry
wall-clock time at all — R6's question (P6), with the per-build
provenance cache as the candidate that kills both the variance and
the 52 ms/emission git overhead in one change; owner-visible output
format, so owner decides.

## [P0b original probe text — for the record; superseded above]

**Why:** the P0 flake sits on the determinism assumption every
byte-identity proof in this line uses.  U1's proof stands (sequential
copied-tree protocol); R3's battery-scale gate-off identity cannot be
trusted under an unattributed flake.
**Do:** (1) reproduce: run the flaked test under suite-like conditions
(20-worker xdist, warm caches — re-running the full suite is
acceptable if a narrower harness cannot reproduce; ledger-label it)
up to N = 20 attempts; (2) on any failure, CAPTURE the failing diff
(the two emissions, byte-diffed) — the diff CONTENT is the
attribution: ordering (set/dict iteration) vs partial state (shared
cache/file race) vs environment; (3) report the attribution table or
the N-run non-reproduction.
**Acceptance:** attribution or N ≥ 20 non-reproduction, in the report.
**EXPECT DIVERGENCE:** the flake may need the exact P0 context (a
foreign warm cache) — if it will not reproduce, say so and stop at
the non-reproduction record; do NOT escalate to build-scale hunting.
**FROZEN:** the deadline (before P5's battery); diff capture on
failure; no fixes without Fable review of the attribution.
**DISCRETION:** the reproduction harness.
**Gate:** none.  **Budget:** suite-scale wall only (~9-14 min per
attempt batch), 0 airport builds.  **Build-time statement:** n/a.

## [P0 original text — for the record; superseded above]

**Why:** two suite runs were started and KILLED during the design
session (`/tmp/tautstring/suite_preU1.log`, `suite_postU1.log` — both
empty/invalid; the first was additionally a mixed-tree run: conftest
imports auto_patch lazily per xdist worker, so a suite is only a valid
baseline if it FINISHES before any src edit).  The tree currently has
NO completed suite run.  R0-v (taut-string spec §5) is also owed: §1.2
recorded 10 airport-build tests failing with the envelope default ON;
the default is now OFF and their disposition must be recorded.

**Do:**
1. `venv/bin/python tools/run_with_ledger.py --label taut-P0-baseline
   -- venv/bin/python -m pytest tests/ -q > /tmp/tautstring/P0_suite.log
   2>&1` (foreground or polled; ~9-14 min; no other builds anywhere
   while it runs).
2. Record the failure list verbatim.  Reference sets: the 20260730b
   STATUS block's 24F (pavement_grade 5, crown_seam_ramp 5,
   supporter_fate 3, runway_end_resa_cut 3, compare_target 3,
   supporter_smallest 2, tile_cut_parity/object_bake_span_limit/
   msfs_xplane_pack 1 each) of which 14 reproduce with concurrent
   changes reverted (pre-existing) and 10 were attributed to the
   then-ON envelope arm.
3. Disposition table: for each recorded failure — still failing /
   now passing / new.  `tests/test_node_space.py` (49) must pass.

**Acceptance:** the table exists and is in the step report.  If
failures DIFFER from the recorded set: REPORT, do not fix — P0 is
measurement.  If `test_node_space.py` fails: STOP, escalate (that
contradicts this session's runs).
**EXPECT DIVERGENCE:** (i) the failure set very plausibly does NOT
match the recorded 24F — the tree has moved since that run (OTHH
object work + U1) and the "10 airport-build failures heal at OFF" is
an INFERENCE from byte-identity, never yet observed; a different set
is a finding to report, not a problem to solve.  (ii) The ledger may
serve some sub-runs from history — a `[ledger]` replay is fine, note
it.  (iii) Concurrent sessions: if `git status` shows new src changes
mid-step, say so — the run then baselines THAT tree, and the report
must name the tree state (`git log -1` + dirty-file count).
**FROZEN:** the command and label; the report format; the do-not-fix
rule.  **DISCRETION:** log paths, polling method, when in the day to
run it (builds exclusive).
**Gate:** none.  **Ladder rung:** (e)-lite (one suite).  **Budget:**
one suite (~9-14 min wall), 0 extra builds.  **Build-time statement:**
n/a (no code).

## Step P1 — U1 node-space store  [STARTED AND FUNCTIONALLY COMPLETE]

**See:** `node-space-unification-spec.md` for design;
`taut-string-model-spec.md` §5 U1.  ALL CODE EXISTS — do not rebuild:

* `src/auto_patch/elevation_per_surface/node_space.py` — NEW module,
  the frozen API (NodeSpaceStore: mint/open_map/has/raw/mint_count +
  view_interval/view_positional_interval/view_keyset/view_relation;
  store_of(layout)).  COMPLETE.
* `src/auto_patch/elevation_per_surface/route_profile/solve.py` — 12
  edits: store import; `pad_weld_refs` relation mint; fp#8 seat-box
  view (intersect); `apron_spine_keys` mint; `apron_band_broken` +
  `env_band` mints; final-site box view (crown lift), pad-weld
  relation view (×2 consumers), spine keyset view, broken-band view,
  env-band positional view; one comment.  COMPLETE.
* `src/auto_patch/elevation_per_surface/route_profile/anchors.py` — 4
  edits: store import; seat-box reset (`open_map(..., reset=True)`);
  reader via `raw`; nobuilding-apron merge via `open_map`.  COMPLETE.
* `tests/test_node_space.py` — 49 tests, green (`-n0` and default
  addopts); mutant sweep 16/16 killed.  COMPLETE.
* `tools/probes_heca_burial_20260729/heca_diag_build.py` — 1-line
  store read with legacy fallback.  COMPLETE.

Evidence already produced: three-way byte-identity SPLP+CYXY (tables
above); rod chain-end ledger line identical both arms (126/128 kept);
`check_build_time` PASS.  The rod EDGE family is deliberately NOT
migrated (U1b — rides P2; spec §3.1).

**ACCEPTANCE CLOSED 2026-07-30:** P0's two runs pass
`test_node_space.py` (49) with zero failures outside the 24F
comparator — U1a is ACCEPTED (see the U1 spec's status block, incl.
the determinism yellow flag → P0b).  Residual housekeeping for any
later agent touching these files: keep the grep gate clean
(`grep -rn "_env_band_keys\|_apron_band_keys\|_seat_boxes\|_pad_weld_refs\|_apron_spine_keys" src/`
returns only comments).

**Frozen API:** `node_space.py` in full.  P2 is pre-authorized to ADD
`view_scalar` (signature in P2) — nothing else changes.
**EXPECT DIVERGENCE:** (i) the grep gate may hit NEW attr uses if a
concurrent session stashed something since 2026-07-30 — report the
hit, do not migrate it yourself (that is a new U1 consumer and Fable
decides).  (ii) Known API sharp edges, pinned by the test suite as
CURRENT behavior, none load-bearing today: `combine` validated only on
non-empty payloads; `open_map`'s get path ignores `kind`;
`open_map(reset=True)` bypasses the non-dict guard; every view treats
minted-empty as absent (`has()`/`mint_count()` still distinguish) —
if P2+ needs the empty-vs-absent distinction, that is a deviation
report, not a quiet API edit.
**FROZEN:** the API; the no-rebuild instruction; the evidence set.
**DISCRETION:** STATUS wording; where the grep-gate output lives in
the report.
**Gate:** none by design (gateless byte-identity refactor; the
deviation is argued in the U1 spec §4).  **Budget:** 0 builds.
**Build-time statement:** measured, PASS (`cbt_postU1.log`); U1's own
effect bounded by the 0.2 s run spread with identical output hashes.

## Step P2 — R1 reference field  [NOT STARTED — Opus-implementable
against this design, with two mandatory report-back checkpoints]

**Model:** taut-string spec §4.1/§4.3 (field), §3.1(a)/(b) (the
ratchet this deletes), §5 R1.  Expected direction only: the §1.3
ratchet class closes; the seam stays in the ~108.5 class at R1 (the
descent to the owner band is S1's, not R1's).

**New module** `src/auto_patch/elevation_per_surface/reference_field.py`
— frozen public API:

```python
def build_reference_field(
    layout,
    *,
    bucket_to_idx: dict,      # solve-space canonical key -> index
    n: int,
    elev: list,               # LIVE assembly-moment state (layer 4)
    elev_entry: list,         # the A-copy (layers 2/3/6) — CP1 part 2
    hard: set,                # hard set at the field moment
    pad_groups: list,         # movable pad groups (index sets)
    pad_weld_idx: dict,       # contact idx -> (seat_level, pad idx) | {}
    rod_edges,                # §10 slabs for _rod_string_values
    broken: set,              # yield_broken at the moment (may be empty)
    u_spine_nodes: set,
    service_nodes: set,       # layer-4b domain: service-ring indexes —
                              # live-elev reference (the follow shape);
                              # never rod-string, never entry.  RENAMED
                              # from `service_skip` 2026-07-31 (the old
                              # name said the opposite of the behavior)
) -> None:
    """Mint, ONCE per build, into the node-space store:
    'reference_field'        scalar: canonical key -> z_ref (uncrowned)
    'reference_field_pad'    scalar: pad-ring key -> its group level
    Layered per spec §4.1 (higher wins): pads (group seat level, from
    elev_entry) > pad-face weld shadow > spine strings
    (_rod_string_values over LIVE elev — the B-moment read; service
    keeps entry elev) > aprons (apron_reference_values called HERE,
    once) > everything else (elev_entry)."""
    # ``node_band`` DROPPED from this signature (Fable 2026-07-31,
    # pre-wiring; it was unused): its only consumer was honesty-ladder
    # rule 2, which §4.6 deletes — and U1 makes the parameter
    # permanently unnecessary (the band is a store artifact; any
    # future field-side consumer reads a store view, no signature
    # change).
```

**Store API extension (pre-authorized):**

```python
def view_scalar(self, name, b2i, n, *, crown_of=None) -> Dict[int, float]
```

same resolution semantics as `view_interval` (crown added, keys not in
`b2i` or ≥ n skipped; last-write-wins is irrelevant — keys are unique).

**Call-site rewiring** (all in `route_profile/solve.py`; gate
`O4_REFERENCE_FIELD`, default "0" until checkpoint 2 passes, then "1";
OFF branch = today's code untouched, byte-identical — prove it):

* fp#8 (the `_yield_node_refs` block): gate ON ⇒ replace the
  entry-elev snapshot + corridor-ref-string overlay + pad-coupling
  overlay + per-pass R call with
  `refs = store.view_scalar("reference_field", bucket_to_idx, n)`
  filtered to movable (`i not in yield_hard`), and group refs derived
  from `reference_field_pad` (any member key's level).  Field-absent
  index ⇒ fall back to entry elev (that is today's semantics and
  covers late-minted nodes).
* final #1 and #2: gate ON ⇒ replace the `_fp_node_refs = {i: elev[i]}`
  snapshot + pad-coupling + the per-pass `apron_reference_values`
  rebuild with the same two views, `crown_of=_crown_of` lifted,
  entry-elev fallback for field-absent nodes.  The R rebuild and the
  honesty-ladder rule 2 die under the gate (spec §4.6); `_BandView`
  resampling goes with them.
* The three deleted snapshot builders stay reachable under gate OFF
  for one release (spec §4.6), then die at R3.

**The FIELD MOMENT is checkpoint 1's decision, not the agent's.**

**P2-CP1 DEVIATION RESOLVED (Fable ruling 2026-07-30; EVIDENCE
CORRECTED 2026-07-31 — the 106.717 figure was a CROSS-TREE ARTIFACT
(Jul-29 dump vs Jul-30 finals; see the spec §5.0 single-tree rule);
the original rung text below is superseded).**  P2 measured that the
`/tmp/bandq` "fp#8" dump is MID-PROJECTION, not fp#8 entry; candidate
A existed in no dump; the ~108.5 is MANUFACTURED per pass by the §7
broken hold against the hard-neighbour interval; the seam is class
spine (layer-4-governed) with rod edges in no dump.  Single-tree
instrumented build (validated: reproduces §1.3's triple; seam
resolves 0.31 m): **A = 108.454 (in class), B = 109.266 (above
class), finals 108.500/108.450** — the A-for-layer-6 conclusion
SURVIVES with corrected evidence and direction.  Rulings:
* the model's shape STANDS; spec §4.1 now carries the sharpened layer
  domains (layer 4 owns ALL strung vertices; layer 6's source is
  candidate A, captured as one `elev` list-copy before the fp#8
  projections; assembly at B's code location consuming the A-copy;
  candidate B is falsified as a layer-6 source);
* the frozen `build_reference_field` signature is UNCHANGED (`elev` =
  the A-copy — it serves layers 2/4/6 self-consistently);
* **one instrumented HECA build is authorized** (coordinator, owner
  directive): extend the EXISTING `O4_DUMP_SOLVE_STATE` payload with
  `elev_entry_A` and the rod slab tuples (+ chain ids if cheap) — no
  new dump mechanism; dump once, reused by P2-CP1, P3c, and S1;
  **payload additions ordered after P3 (same build, no second
  authorization): `spine_floor`, `couple_adj` (P3's bounds caveat),
  five `elev` snapshots inside `_solve_spine_profile` (the
  post-phase-A 2.2 m drag attribution), and the remaining
  `reach_band_unified` INPUTS (seat/gs-pin anchor value sets +
  attachment-leg data; `spine_adj`/`runway_anchor` are already in
  the payload) so P3c's ceiling attribution runs OFFLINE;**
* revised CP1 gates on the instrumented dump — **MEASURED
  2026-07-31**: (i) field(seam) via layer 4 in the 108.5 class —
  PASS at both moments (string(A) 108.458 / string(B) 108.504; the
  rod string is Δ-robust, so this gate cannot discriminate moments);
  (iii) fabric A-vs-B distribution — MEASURED: p50 0.000 / p90
  0.259 / max 19.199, 14.78 % moving ⇒ the A-copy is LOAD-BEARING;
  (iv) spine |field − final#2| — layer 4 from A p50 0.628 FAILS,
  from B p50 0.077 PASSES.  Gate (ii) (replayed finals consume the
  field without pass-entry state) remains for the wiring.

**P2-CP1 PART 2 (Fable rulings 2026-07-31, on the single-tree
measurement):**
* **Split-source field (a model refinement, gate (iv) as the
  pre-registered arbiter): layer 4 reads the ASSEMBLY-moment (B)
  strung state — the level the passes demonstrably enforce; layers
  2/3/6 read the A-copy** (seat semantics + pre-drag fabric; the
  max-19.2 m mover class is exactly what references must not
  inherit).  Express caveat: pre-S1 the B-read embeds chord-1's
  attributed sag level, and that is CORRECT for R1 (no scope-sneak;
  S1 replaces the construction, after which the same read carries
  the taut string).  Spec §4.1 updated to match.
* **Authorized interface changes (frozen-interface decisions,
  Fable's; option ruling 2026-07-31):** (1) `build_reference_field`
  gains `elev_entry` (the A-copy) alongside live `elev` — layers
  2/3/6 read `elev_entry`, layer 4 reads live; (2) **Option 1**:
  `_solve_spine_profile` gains keyword-only
  `probe_out: dict | None = None` (named for the in-file
  `pieces_out=` out-param precedent this very function already
  uses) — `None` ⇒ no copies, no behavior change; a dict (requested
  only under the dump gate) receives `couple_adj` + the five
  stage-labelled `elev` snapshots at the measured natural
  boundaries: (1) entry/DEM-seeded, (2) post harmonic
  min-curvature, (3) post taut-string pass, (4) post fairing,
  (5) post final exact cap projection (= returned state) — the
  stages that name the post-phase-A 2.2 m drag.  Option 2
  (module-global stash) REJECTED — it resurrects the bespoke-carry
  pattern U1 deleted; Option 3 (return-tuple change) rejected —
  breaks the call site for no gain.  Blast radius is measured
  (module-private, one production call site at solve.py:897; probe
  kit wraps via hasattr): pre-landing check — `heca_trace_build.py`'s
  wrapper must forward `**kwargs`; if not, the one-line probe-kit
  fix is in-scope.
* **THE ONE FINAL INSTRUMENTED BUILD — complete payload (authorize
  exactly one; nothing rides later).**  STAGED STATE 2026-07-31:
  P2 folded the instrumentation onto the existing
  `O4_DUMP_SOLVE_STATE` payload (separate gate/file deleted, per the
  shape ruling); `elev_entry_A`, `rod_edges`, `rod_piece_spans`,
  `yield_broken`, `yield_hard`, `spine_floor` are LANDED, gate-off
  identity re-proven three-way (SPLP `d8d0f065…` = U1's arm), and
  the gate-on payload verified end-to-end on SPLP (`elev_entry_A`
  distinct from `elev` at 475/16024 nodes; `rod_piece_spans`
  consistent with the slabs).  **Candidate B needs no field — it is
  the payload's existing `elev` key (proven unwritten between the
  snapshot point and the dump site).**  REMAINING additions for the
  authorized build: `couple_adj` + the five snapshots (via
  `probe_out`, above); the `reach_band_unified` INPUTS for P3c not
  already in the base payload (seat/gs-pin anchor value sets,
  attachment-leg data; `spine_adj`/`runway_anchor`/`node_band`/
  `seat_boxes`/`pad_weld_refs`/`pad_groups` are already carried) —
  P2 lists the band builder's actual reads and dumps each, reporting
  any un-dumpable live object as a deviation; and, for R2's later
  design where cheap at the same site: `_relax_node_bounds`, the
  service ring sets.  Final-pass states are NOT re-instrumented for
  this build (the spent build's four dumps carry them; CP2 dev
  builds re-measure them live) — do not add a second dump mechanism
  for finals.  **Practice rule (adopted from P2): prove any payload
  change gate-on AND gate-off on SPLP before spending the HECA.**
* **budget correction, honest (supersedes "5 builds"):** P2's HECA
  budget is **6 builds total** — 1 instrumented SPENT (718.7 s, four
  dumps on disk), 1 final instrumented AUTHORIZED against the payload
  above, ≤ 4 checkpoint-2 dev loop.  Side spend so far: 7 SPLP
  (~85 s — two three-way gate-off identity rounds, `d8d0f065…` =
  U1's arm both times, + the gate-on payload verification).

**P2 STATE 2026-07-31 (after the authorized final build):** LANDED —
`probe_out` on `_solve_spine_profile` (Option 1; the probe-kit
`**kwargs` gate passed), `view_scalar` in `node_space.py` (store
suite 55 green), `reference_field.py` implementing the split-source
layering (`elev_entry` → layers 2/3/6, live `elev` → layer 4; the
anti-scope-sneak caveat is a docstring clause; nothing special-cases
chord 1); gate-off three-way identity re-proven (`d8d0f065…`);
SPLP-first payload verification followed the plan rule.  The five
snapshots delivered the drag attribution (harmonic 67.1 % — see
P3b); `couple_adj` came through (7,112 nodes / 118,531 couplings);
stage-5 seam = `elev_entry_A` across two independent builds
(cross-validation).  **WIRING LANDED AND REVIEWED (2026-07-31,
later — supersedes the earlier "unwired" state):** gate
`O4_REFERENCE_FIELD` default "0" at all three sites in the
minimal-diff shape (legacy condition gains `and not _ref_field_on`,
field path is an `elif`, NO existing line re-indented — the OFF path
is character-for-character today's code); fp#8 builds the field once
at the assembly point; both finals resolve via `view_scalar`
crown-lifted, no re-snapshot, no per-pass R rebuild; `node_band`
gone everywhere.  Gate-off identity: SPLP ×3 + CYXY pre==post,
matching U1's evidence hashes.  66 unit tests green,
mutation-checked (collapsing the source split fails the layer-4
test); the synthetic-tests-cannot-see list (assembly moment in a
real solve, R on real rings, real branch splitting,
crown/band/projection interaction) is named in the module
docstring — CP2's HECA arms carry exactly that burden.  Build-time
PASS (CYXY 34.57 s median; the −9.84 s is disclaimed as not P2's,
gate-off being byte-identical).  Suite `taut-P2-suite`:
**24F/3876P, tree `6b019fdee962`, diffed against its own P0 run —
the only delta in either direction is the flake, healed (P0c
working): clean against the corrected live comparator of 24.**
Spend: 2 HECA + 20 SPLP + 3 CYXY + 1 suite; ≤ 4 HECA remain,
reserved for checkpoint 2 (correctly not started: HECA arms,
W-CHORD gates, seam class, building199 weld, the default flip).

**CP2 MEASURED 2026-07-31 — DO-NOT-FLIP (default held at "0";
nothing tuned):** gate-off body hash PASS (`d4f52f02…` = fresh
gate-off); W-CHORD2 law PASS both arms (1.44 %).  FAILING on ON:
seam 108.23 (3 cm under the 108.26-108.59 class — marginal, gate
NOT widened, rides the attribution); building199 weld 0.490 → 0.890;
W-CHORD1 −11.07 → −11.28; law-true 5 → 6 with ONE new failure,
`test_cyxy_spine_zero_no_bowl` — the only arm difference across all
four airports.  **Gate correction, owned by Fable: the "≤ 0.2 m"
weld gate was IMPOSSIBLE at this step (OFF itself is 0.490; ≤ 0.2
is R2's deliverable) — restated as "not worse than 0.490", which ON
still fails; verdict unchanged, credibility repaired.**
**Synthetic-limits discharge:** assembly moment PASS (field minted
once, 131,055 entries; field-absent 0.00/0.05/0.14 % vs the 5 %
threshold); rod chains PASS (7,347 slabs); crown/band PASS
(126,163/126,169 resolved).  **The hit is the one P2 named in
advance: R on real apron rings (layer 5).**  Mechanism observation
(hypothesis, NOT attribution): building199's apron rose while the
pad ring held its A-copy seat — layers 2/3 behaving, layer 5/6
diverging.
**P2-CP2b — attribution directed (Fable ruling; interventional
before any fix):** (1) ZERO-BUILD reference-diff at the two failure
sites (building199 apron ring; CYXY violating spine nodes) from the
dumps/CP2 artifacts — name WHICH layer authored the moved refs;
(2) masked arms only if (1) implicates: ARM-5 (legacy per-pass R
under ON — isolates R-once vs R-per-pass), ARM-5v (R-in-field on
pass-entry anchors — isolates anchor source vs moment), ARM-6
(layer 6 from live-B — isolates the A-copy).  Authorized: the 2
remaining CP2 HECA + CYXY builds for the invariant; escalate before
exceeding.  NO fix or redesign before an arm lands.  R1's flip is
BLOCKED on CP2b; **S1 is NOT** (its gates measure against OFF at
default env) — the box handover to S1 was correct.

**CP2b CYXY HALF MEASURED AND RULED (2026-07-31):** step (1)
delivered at REFERENCE level — the ON reference itself prescribes
6.03 % at a 5.0 %-cap `service_road` pair (both endpoints layer-6/
A-sourced; OFF's legacy refs lawful at 4.48 %/3.31 %; the layer-4
pair byte-identical across arms = the validating control).  CYXY:
OFF 0 spine violations, ON 1, reproduced on two ~35 s builds.
**Ruling: SPEC-CONFORMANCE DEFECT, not a design question — §4.1
layer 4's service sub-domain ("service corridors from
`apply_service_road_dem_follow`'s shape") was skipped by the
implementation, dropping service nodes to the A-copy; the absorbed
legacy ★ comment warned of exactly this failure at exactly this
airport.  ARM-6 RETIRED UNSPENT** (as a fix it would also have
overreached — swapping ALL fabric to B undoes the load-bearing
A-copy ruling to fix a service-only defect).  **Fix directive (P2;
no API change — `elev`/`elev_entry`/`service_skip` already in the
signature):** service nodes take live-`elev` (the follow shape
operationally; never rod strings, never `elev_entry`); unit tests:
service field == live-at-assembly, non-service unchanged, layer-4
control pair stays identical.  **Verification sequence:** fix +
tests (0 builds) → 1 CYXY (invariant must heal ON 1→0) → 1 HECA
re-arm (of the 2 remaining; re-measure the four gates) → **ARM-5
only if** building199/W-CHORD1 still fail (the last HECA, now
cleanly scoped to "does layer 5 own the HECA half"; ARM-6 provably
inert there, A==B==88.422).  HECA's half of CP2b remains OPEN
pending that sequence.

**SEQUENCE EXECUTED (2026-07-31):** fix landed per spec (layer 4
split 4a taxi/rod-string + 4b service/live-elev, 4b independent of
slab existence; 67 tests; mutation-checked — deleting 4b fails
exactly the two service tests; fixture rewritten so live ≠ string ≠
entry, no silent pass; register 16 first outing — the ★ obligation
carried at code site + test docstring).  **CYXY spine invariant
HEALED 1 → 0.**  HECA re-arm: all three gates unchanged TO THE
DIGIT (weld 0.890, W-CHORD1 −11.28, seam 108.23) — **the two
defects are INDEPENDENT, as the two-site disagreement predicted**.
Hashes: OFF `d4f52f02…` (comparator still valid — the fix lives in
the ON branch), ON pre-fix `606c7d70…`, ON post-fix `71b8e944…`.
**RULINGS (Fable, 2026-07-31):**
* **ARM-5 = shape (A)** — overlay layer 5 only (legacy per-pass R
  overlaid; layers 1-4/6 field-sourced).  Riders: (1) (A) BUNDLES
  moment + anchor-source + rule-2 — a HEAL implicates layer 5 as
  owner, the decomposition then runs OFFLINE from the dumps before
  any fix design; a NO-HEAL exonerates layer 5 and the residual
  returns to zero-build reference-diff.  Neither outcome licenses a
  fix by itself.  (2) INSTRUMENT the arm: dump R's per-pass values
  at building199 + the seam + the W-CHORD1 dip stations — the last
  HECA doubles as the decomposition input, never a bare boolean.
  ARM-5 queues behind S1's arm 2 (box discipline).
* **The +4 non-spine CYXY violations (total 7 → 11 under ON
  post-fix): the CP2 gate reads the TOTAL — it was never
  spine-scoped.**  Spine-only pass is necessary, not sufficient.
  Directed (zero builds): CP2b-step-1 reference-diff on the 4
  pairs — authoring layer + lawful-pre-solve-or-not; surfaced vs
  fix-minted.  CYXY status: **healed-spine, +4 PENDING ATTRIBUTION
  — reported, not accepted; does not block ARM-5, does block
  closing the CYXY half.**
* **`service_skip` RENAMED `service_nodes`** (frozen-API owner's
  revision at the cheapest possible moment): a name stating the
  opposite of the behavior is the register-16 trap in miniature.

**ARM-5 MEASURED AT BOTH SITES (2026-07-31; the last CP2 HECA
398.2 s + the authorized CYXY 37.8 s) — THE BUNDLE IS DECOMPOSED:**
HECA: building199 0.890 → **0.480 HEALED** (passes the corrected
gate); W-CHORD1 −11.28 unchanged to the digit; seam 108.21 (marginal
creep 108.26 → 108.23 → 108.21, rides the decomposition); W-CHORD2
law PASS.  CYXY: 7 → 11 → **14 — per-pass R actively HARMFUL**.
**Three failures, three owners:** building199 = LAYER 5 OWNS
(ownership not mechanism; the moment/anchor-source/rule-2
decomposition proceeds OFFLINE from the six banked `_a5_dump` R
dumps, rider-1-authorized, zero builds); W-CHORD1 = layer 5
EXONERATED (the sag rides layer 4's faithful string read — S1's to
dissolve, as standing); CYXY +N = layer 5 EXONERATED AND
COUNTER-INDICATED (residual stays with the A-copy attribution).
**R-FIX SHAPE CONSTRAINT (Fable, stated ahead of the
decomposition): any layer-5 fix must preserve CROSS-LAYER
MOMENT-CONSISTENCY at interfaces** — ARM-5's harm signature is
pass-entry-moment R beside pre-projection-moment fabric refs, a
cross-moment mix legacy never had, measured harmful at CYXY.  A
global per-pass-R fix is counter-indicated by measurement; the
building199 fix scopes to the decomposed mechanism.  Consistent
with, but NOT hardening, the logged interface hypothesis.
Arm construction clean: `O4_REF_FIELD_ARM5` default "0", shape (A)
exact, rider-2 instrumented, SPLP smoke + gate-off identity
`d8d0f065…` ×3 BEFORE the last HECA (the prove-first rule working).
**BUDGET: CP2 EXHAUSTED (4/4 HECA + the CYXY).  Session total:
5 HECA, 5 CYXY, 24 SPLP, 1 suite, 1 law-true run.  Posture: every
further build returns to the coordinator BEFORE spending;
insufficient dumps are a finding to price, never a build licence.**

**BUILDING199 DECOMPOSED TO THE MOMENT AXIS (2026-07-31, zero
builds; six banked R dumps, site-matched):** R at the site fp#8
90.165 / final#1 90.188 / final#2 88.792 — spread 1.397 m;
systematic across 812 tri-pass sites (p50 0.299 / p90 1.898 / max
7.589 m).  Closure to millimetres: field arm emitted 90.160 =
fp#8's R + 5 mm (the field froze fp#8-time R); ARM-5 emitted
88.790 = final#2's R + 2 mm.  Anchor-source + rule-2 unseparable
from these dumps, bounded TOGETHER at ≲ 0.01 m here — a consistency
argument, not proof; the two isolation builds were correctly NOT
requested.  **FABLE RULING (in spec §4.1): "built once" RETAINED
as a measured choice** — the moment axis explains the ARM DELTA,
never the LAWFUL VALUE (pad 89.27, weld target ≤ 0.2: frozen R is
0.9 HIGH, final-pass R 0.48 LOW = legacy's steady state; ARM-5's
"heal" passes only the corrected not-worse gate); per-pass
referencing is the §1.3 amplifier (worsens CYXY 11 → 14, measured)
and stays retired; no per-site moment rules (drape-tuning in a
moment's clothes).  HYPOTHESIS logged (§1a discipline): R's
assembly-moment construction inputs at pad faces (layer-3 shadow
reach into R's Dirichlet set); offline-testable riding the next
authorized build's layout dump — NO new spend.  building199
disposition: ATTRIBUTED (moment axis, arm delta); fix deferred
into R2's design frame under the standing constraints
(moment-consistency at interfaces; no global per-pass R).  R1's
flip criteria unchanged — still blocked.

**THE +N ATTRIBUTED (2026-07-31, zero builds):** both frames
reported (check_grade 7 → 10; `within_violations` 7 → 11; overcount
caveat held) — ALL movement is ONE service↔apron interface cluster
(z′ ≈ 701.6-702.2, the healed spine violation's neighbourhood):
3 new pairs + all 7 pre-existing worsened, none healed.  Pre-solve
prescription table: the A-SOURCED field prescribes 13.17-27.90 %
against 5 % caps at the cluster pairs; legacy B-sourced refs lawful
≤ 4.6 %; 4b restores legacy EXACTLY on the service members.  **The
+N are the SAME A-copy defect 4b fixed, on the half 4b was scoped
not to touch (the apron members)** — vindicating the total-scope
gate ruling (a spine-only gate would have closed CYXY over a live
defect).  P2's script mislabelled its own column ("FIX-MINTED" for
what models the PRE-fix field) and P2 inverted its own reading —
the line's third self-catch (register 17).  HONEST LIMIT: the
offline model LUMPS layers 5 and 6 on the apron side (R needs a
layout) — precisely ARM-5's question, now with a second site.
**RULING — ARM-5 EXTENDED TO TWO SITES:** the scoped instrumented
HECA (last CP2 HECA) PLUS one instrumented CYXY (~40 s; NEW
allocation, authorized here; cluster instrumentation = R per-pass
values at the z′ 701.6-702.2 pairs).  Two-site disagreement is
decomposition evidence — the pattern that exposed the service
defect — and it hedges rider 1's bundling directly.  CYXY half
status: **healed-spine, +N attributed, NOT CLOSED** (closure = the
5/6 separation ARM-5 delivers).  HYPOTHESIS (named for the frame,
NOT an attribution, §1a discipline): the A-copy may be
pre-reconciliation at CROSS-SOURCE INTERFACES (the projections
reconcile interfaces candidate A predates); if ARM-5 confirms at
both sites, the fix shape may be interface-scoped rather than
layer-scoped.  Not designed, not acted on.
  Docstring carries the 4a/4b domain note.

Original rung text (superseded, kept for the record): Candidates:
(A) fp#8 entry BEFORE the two `feasibility_project` calls
that apply the quarantine blend (today ~solve.py:1288-1296 — the blend
is why the corridor-ref-string overlay exists at all); (B) today's
post-projection snapshot point.  Replay both against
`/tmp/bandq/heca_band.01_fp8.pkl` + the two final dumps: reconstruct
each candidate's field at matched node coordinates, apply it as z_ref
in an offline pass reconstruction, and measure (i) the seam node's
reference across passes (must hold the 108.5 class), (ii) p50/p90
|z_ref − final elev| over the fabric classes.  REPORT the table to the
reviewer and WAIT for the moment ruling before wiring.  ~1 s/variant,
0 builds.

**Checkpoint 2 (after wiring, before default flip):** ONE HECA build
per arm (OFF then ON), gate-off body hash == the P1-era baseline
(`/tmp/HECA_ebOFF.osm` body is NOT the comparator — tree has moved;
compare against a fresh gate-off build), then gates: W-CHORD2 law PASS
retained (`owner_chord_probe.py`), seam value in the 108.26-108.59
class, building199 weld ≤ 0.2 m (`/tmp/envband/probe.out` method),
W-CHORD1 worst-bin not worse than −11.07, no new law-true violations
(`O4_TEST_AIRPORTS=HECA test_pavement_grade`, ledger; CAUTION
register 14 — prices as a FOUR-airport run, ~710 s).  Budget: ≤ 4
dev-loop HECA iterations including these two, PLUS the one authorized
instrumented dump build — 5 HECA builds total for P2 (the P2-CP1
deviation resolution above); escalate, don't exceed.

**Unit tests (new `tests/test_reference_field.py`):** synthetic layout
covering layer priority (pad beats string beats entry), weld shadow
equals pad level, service nodes keep entry elev, detached-pad DEM,
absent-field fallback, single-mint (`mint_count == 1`), and gate-off
import-neutrality (module not imported when OFF).
**U1b rides here:** when touching the rod region, move the rod edge
artifact into the store IF AND ONLY IF the diff stays mechanical;
otherwise leave and note.
**EXPECT DIVERGENCE (this step has the most — escalate freely):**
(i) Every solve.py line number in this plan and the spec is against
the 2026-07-30 dirty tree and WILL have drifted — locate sites by the
code content quoted here (`_yield_node_refs = {`, the corridor-ref
overlay, `_fp_node_refs = {`), never by line.  (ii) The pad-group
reference construction assumes pads sit FLAT at the field moment
(group level = mean of entry elev = seat level); if the replay shows a
pad group non-flat at the moment chosen, the mean is not the seat —
report it with the group and spread.  (iii) `pad_weld_idx` exists only
under `O4_PAD_ROD_COUPLING=1` — the field build must behave under
either gate state; if the interplay is unclear at the call site,
report rather than guess.  (iv) `apron_reference_values`' signature is
owned by a file concurrent sessions edit (`apron_reference.py`) — if
its parameters have moved since this plan, STOP (that signature is
part of R1's design surface, not yours to adapt to silently).
(v) At the finals, nodes minted after the solve have no field key and
take the entry-elev fallback BY DESIGN — but if more than ~5 % of the
movable set is field-absent there, the field governs too little to
mean anything: report the coverage number before flipping any default.
(vi) Checkpoint 1 may show NEITHER candidate moment holds the seam's
108.5 class — that outcome is precisely what the checkpoint exists to
catch; it comes back to Fable as a design question (a third moment or
a layered snapshot), not as something to tune through.
**FROZEN:** the module path and public signature; the store artifact
names; `view_scalar`'s signature; the gate name and its "0" default
until checkpoint 2; every checkpoint gate and threshold; the 4-HECA
budget; the entry-elev fallback rule.  **DISCRETION:** internal
helper decomposition inside `reference_field.py`; the replay script's
structure; unit-test parametrization; whether U1b lands (mechanical
test above).
**Build-time statement:** field build is
one linear pass over ~130k nodes + one R construction (replacing TWO
per-pass R builds and three snapshot dict builds) — expected ≤ today;
measure with `check_build_time --run --runs 3 CYXY` and report; ≥0.6 s
regression ⇒ stop, optimization review.
**Ladder:** (a) dumps → (b) replay (checkpoint 1) → (c) unit tests →
(d) HECA ≤4 (checkpoint 2).  No flats, no battery (R3's).

## Step P3 — S1 interventional measurement  [COMPLETE 2026-07-30 —
zero builds; full table + verdicts in
`s1-taut-chord-constructor-spec.md` §1a]

**Result:** classes (a)-(c) exonerated (anchor-set swap moves
nothing; zero hard nodes within 100 m of the chord), (d) not the
source (DEM seed gives SHALLOWER sag), (e) LATENT not binding
(masking the ceiling alone moves 0.00 m; 21/43 dip nodes sit ON
their band floor).  Attributed: **class (f), corridor decomposition +
peg inheritance** — 62 corridors over one 3,980 m chord, 59 endpoint
pegs carry 100 % of the movable defect (A8 ≡ A3), constructor holds
the owner's line at −0.05 m with pegs freed + ceiling masked (upper
bounds: spine_floor/couple_adj absent from the dump).
**Deviation resolutions (both were Fable-spec defects, both fixed in
the S1 spec):** (1) the frozen class list lacked the attributed
class — folded in as (f); P3's report-don't-decide handling was
correct.  (2) The early-stop licence in S1's EXPECT-DIVERGENCE (iii)
would have blessed the falsified correlational ceiling reading —
replaced by the normative attribution rule: *latent vs binding is
decided only by masking; position relative to the string is never an
attribution.*
**Consequences:** S1 spec revised (Stage 0 maximal-string assembly;
pegs dissolve; API extended; chord-1 single-string acceptance gate);
S1-CP1 SATISFIED by this table + ruling; new step P3c below; two
open attributions ordered into P2's instrumented build (the
post-phase-A 2.2 m drag via five `_solve_spine_profile` elev
snapshots; `spine_floor` + `couple_adj` into the dump payload).
The original step text follows for the record.

**Question (spec §1.8):** what pulls the chord-1 dip (along ~1000-2200,
worst −11.07 m at 1800) below the straight 111→113 string in the
envOFF arm?  A local V that recovers is not facially reach-justified.

**Protocol:** enumerate candidate pullers as maskable anchor/reference
classes at fp#8: (a) runway-crossing anchors on chord 1's crossings,
(b) apron/pad seats welded to the corridor, (c) groundside pins within
witness range, (d) the DEM-seeded phase-A profile itself (mask = seed
the corridor from the chord line instead), (e) band ceilings below the
string (measure directly from the dump's `band`).  For each: offline
replay on `/tmp/bandq/heca_band.01_fp8.pkl` (+
`heca_spineframe_state.pkl` for the spine adjacency), re-projecting
the corridor profile with that class masked, then measure the replayed
W-CHORD1 profile.  Deliverable: attribution table (class → worst-bin
departure with class masked) + the band-ceiling-vs-string overlay.
REPORT to the reviewer; the S1 constructor (taut chords, declared
bends) is designed by Fable from this table.  0 builds; escalate if
the dumps cannot answer (a new instrumented HECA dump costs one build
— ask first).
**EXPECT DIVERGENCE:** (i) the dumps may not carry enough state to
re-project the corridor under a mask (they were made for envelope
attribution, not for this) — that is the ask-first case above, not a
licence to approximate; (ii) the puller classes overlap (a seat that
is also band-limited): report joint effects rather than forcing a
single-class attribution; (iii) class (e) may answer trivially if the
band ceiling sits below the string along the dip — if so, say so and
stop early; the table is still the deliverable.
**FROZEN:** the class list; the deliverable format; the 0-build rule;
no fix design.  **DISCRETION:** replay implementation details;
station binning within the measured 200 m convention.

## Step P3c — band-ceiling provenance, OFFLINE  [NEW after P3 —
analysis only; a build for this is NOT authorized]

**Question:** what authors the band ceiling that sits 0.66-5.94 m
below the owner's string over chord-1 along 1000-2400 (latent today,
binding after S1's Stage 0, worth ~5.7 m)?  Seats and gs pins are
exonerated as DIRECT pins only; whether they depress the ceiling
THROUGH the band build is open.
**Do:** recompute `reach_band_unified` OFFLINE from P2's enriched
dump (its inputs are ordered into the payload above), masking one
candidate class per arm during recomputation (seats; gs pins; each
anchor-value family), and read the chord-1 ceiling per arm.
Deliverable: the ceiling-attribution table → feeds owner ruling §6.6.
**EXPECT DIVERGENCE:** the offline band reconstruction may not be
faithful (the band builder reads layout+G state beyond the dumped
inputs) — if fidelity cannot be demonstrated against the dumped
band (control arm must reproduce it), STOP and report; ONLY then is
a masked-build authorization question put to Fable, with the
fidelity gap as the evidence.
**FROZEN:** mask-one-class-per-arm; control-arm fidelity proof
before any masked arm is read; no fixes.  **DISCRETION:** harness
internals.  **Budget:** 0 builds.

## Step P3b — S1 taut-chord constructor  [IN PROGRESS; spec REVISED
2026-07-31 twice — Stage-0 mechanism replaced after a fired STOP,
and the §1b ordering ruling added]

**Deviation record (S1 spec §10(vi) FIRED, resolved by Fable):** the
heading-based Stage 0 was falsified on real geometry (zero chord
merges at any threshold; half the needed piece junctions do not
exist; endpoint headings peel onto crossers) while the owner's chord
is graph-reachable (3,992 m through-path).  Mechanism replaced:
**centerline-identity assembly** (level 1 authorship grouping from
the `_build_global_spine` walk — authorized plumbing; level 2
centerline-scale windowed continuation; unauthored fallback).
Options A/C falsified by measurement, B insufficient, E rejected on
principle.  Mechanism-before-wiring gate: the replay harness must
show the chord-1 authorship census and a ONE-string assembly
covering the through-path class BEFORE further wiring.  §6's
assembly gate disambiguated (through-path, not corridor cloud);
test 8(iii) replaced by a real-geometry fixture (the synthetic
chain PASSED under the broken mechanism — false confidence).
**Drag attribution folded in (P2's five snapshots): the harmonic
min-curvature solve owns 67.1 % of strung motion; the internal taut
pass is an 11 % corrector.  Ordering ruled (S1 spec §1b): S1's hook
SUPERSEDES the harmonic on string interiors (α); ends hardened so
no assembled string inherits post-harmonic values; step S1b ordained
(constructor first-class inside phase A, harmonic demoted to
gap-filler) — Fable-designed AFTER S1's measurement, never
implementer-initiated.**
**Landed (gate-off inert, verified):** the §4 API in the EXISTING
`taut_string.py` (extended, not duplicated — spec corrected),
`TAUT_STRING_FOLLOW_THROUGH_DEG` 15.0, the gated hook
(function-local import; `O4_TAUT_STRING_CONSTRUCTION` default "0"),
`_build_spine_corridors` untouched, 23 tests green.  Two
replay-found bugs fixed (heading sign error; the `base_hard`
silent-no-op hazard — now spec-normative hook contract).  Owed and
correctly deferred to builds: gate-off body-hash identity, suite
delta, W-CHORD1, ON-arm build time.  S1 yielded all HECA builds to
P2 this session — correct.
**Part (ii) PASSED (2026-07-31, zero builds):** chord 1 assembles as
ONE string — 36 fragments / 293 nodes / 99.9 % along-span
(1 → 3,966 m of 3,968) / **0 of 463 chord nodes orphaned** — the
two-sided §6 gate holds.  The window is the mechanism
(interventional: window 0 → 59.8 %, 37 m → 99.9 %; thresholds
10/15/20° byte-identical).  Rulings landed: gate currency = ALONG-
SPAN for coverage, POLYLINE arc-length for stations/caps (excess
reported per trunk); `window_m: float = 0.0` RATIFIED (keyword-only
additive; production passes `TAUT_STRING_HEADING_WINDOW_M = 37.0`
explicitly); the COMPETITION CLAUSE adopted (register 13; the
landed fixture freezes all 647 non-service fragments with the
window-necessity test as its negative control).  25 tests green.
Next for S1: level-2 wiring into `construct_taut_strings` + the
hardened end policy; identity proof queued behind P2's CP2 arms
(pre-flight guard armed).  Spend still 0 of ≤ 4 HECA.

**Census in, gate ruled (2026-07-31):** chord 1 is authored by 75
chains — the count expectation failed — but 36 collinear chains tile
it at 95.9 % metres with ZERO-length gaps; Fable ruled the gate
PASSED and RESTATED it in property terms (bridgeless concatenability:
collinear + ≥95 % metre tiling + zero-length gaps; metre extents are
gate currency, node percentages never; level-2 heading =
whole-fragment bearing).  S1 stopped at the literal words and did
not bridge — correct; the proxy was the defect and is owned by
Fable.  Part (ii) — the one-string assembly demonstration on the
real-geometry fixture — is now unblocked and remains required.
HECA's 0/5,085 unauthored pairs recorded as a measured zero (the
fallback stays for other airports).  Export build-time MEASURED:
0.080 ms (~75× under the review line).  The grade_graph identity
proof is staged with the pre-flight guard having correctly aborted
on P2's live HECA (exact-PID waiter armed); it runs when the box
clears.  S1 spend: 0 of ≤ 4 HECA.
**ARM 1 MEASURED (2026-07-31; 1 of ≤ 4 HECA) — clean negative,
nothing tuned:** the emitted chord is bit-identical to baseline
(W-CHORD1 exactly −11.07) because **chord 1 FELL BACK** — 239/296
strings (81 %) fell back under the whole-chain policy, driven by
179 `infeasible_station` defects (+ 21 `no_datum`; 0 band-inverted,
0 off-net, 0 unauthored) whose binding class is ANCHOR-vs-ANCHOR
through the cap at a clustered gap (median 1.515 m, max 1.618 m).
Gate-off identity PASS (`d8d0f065…`).  Assembly at build density
reached 2,366 m max vs the fixture's 99.9 % prediction.
**Rulings (Fable):** §2.2 fallback REVISED to MINIMAL (split at the
declared defect, string the feasible spans, no blending across the
gap — whole-chain fallback retired; the granularity question was
never considered at authoring, owned); §2.2b surfaces-vs-creates
ARITHMETIC directed (zero builds: |z_A − z_B| vs g·d per defect
pair, authors classed by clause-1 type; pre-existing → §6.4 owner
pathway per feasibility-is-guaranteed, manufactured → S1 bugs);
taxonomy ENTRY FIVE (density sibling, register 15) with the
fixture re-base ORDERED as census-then-rebase-then-negative-control.
**Arm 2 waits for all three zero-build items.**  Cross-arm note
recorded: S1 leaves W-CHORD1 at −11.07, P2's R1 arm moved it to
−11.28 — two independent levers, neither improving, no
cross-tuning; both defaults "0".  P2 holds the box (CYXY dump +
ARM-5).

**ARM 2 MEASURED (2026-07-31; S1's 2nd of ≤ 4 HECA) + rulings:**
histogram at build density, canonical IDs: α 522/592 (88 %: 478
deviation-rejected at median best-deviation 29.9° vs the 15°
window + 44 taken-by-earlier-string), **β = 0** (registry CLEAN —
interning exonerated), γ = 70 (12 %) at median 112.9 m — genuine
terminals, **Fable's dropped-junction-node hypothesis FALSIFIED**
(register 18).  S1's honest limit honoured: most α rejections are
CORRECT (crossers); no admission change on an unsplit bucket —
**α-SPLIT ANALYSIS DIRECTED** (offline: should-have-merged vs
correctly-rejected via the probes' chord-corridor definition; a
material ~30° should-have-merged class brings the level-2 window
semantics back to Fable WITH data).  **§2.2b CLOSED: ≥ 159/168
SURFACED** (band-vs-anchor 137, genuine anchor-vs-anchor 22,
band-vs-xstring 9 — each with a pre-existing band author; ZERO
xstring-vs-xstring: S1 manufactures no contradictions).  Minimal
fallback verdict: WORKING AS SPECIFIED (81 → 78 %), not the
limiter — **DATUM SCARCITY is** (split spans inherit no datums;
`no_datum` 21 → 32; chord corridors carry zero interior hard
anchors).  **Datum ruling: class (ii-b) trunk-end datums added to
the S1 spec §3 (anchor-governed complex fabric at the trunk's
extremities; PROPOSED-PENDING-OWNER-CONFIRMATION); trunk-first
ordering STANDS (the owner's worked example falsifies
anchor-distance reordering); mid-trunk split spans stay datum-poor
pending §6.4 — counted consequences, never engineered around.**
**THE OWNER PRESENTATION now carries THREE items in one filing:**
the ≥ 159 surfaced contradictions (§2.2b), P3c's band provenance,
and the (ii-b) datum-flow confirmation — all one anchor subject.
W-CHORD1 −11.07 unchanged to the digit for the second consecutive
arm (expected: chord 1 still falls back pending the rulings).  S1
HOLDS its remaining ≤ 2 HECA until (ii-b) + the α-split report;
**ARM-5 UNBLOCKED (box free).**

**THE OWNER'S VERDICT + THE SPINE-WALK + AN AUTHORITY OUTAGE
(2026-07-31; two waves, folded together after recovery):** the
owner's tagged-run verdict attributed "pretty much all" 32
unmatched-ours to ONE defect (runs cutting open terrain between
spines) and supplied the algorithm (follow the spine; stop at
turns; curves get no string; emit > 100 m segments).  FIVE RULINGS
(delivered in the report body before a monthly-spend termination;
preserved verbatim by the coordinator in a marked non-spec file —
the loop held open, nothing authored in Fable's place; folded into
the specs on recovery and the preservation file deleted):
S1 un-held for the spine-walk; the walk adopted as a DOMAIN change
(chord core survives; open-terrain UNREPRESENTABLE); the
contamination re-measure directed with pre-registered outcome
(register 21's FIFTH strike below); S1-06/09/12 named fixtures;
P7 step 0 joins the construction fork's critical path (holes are a
hard blocker), walk work parallel.
**THE WALK LANDED (33/34 green): open-terrain crossing VERIFIED
UNREPRESENTABLE; spine gaps never bridged; selection layering
preserved.  The failing curve test exposed a REAL ruling-2 gap
("sustained"/"straightens" undefined — owned by Fable), and S1's
refusal to invent the criterion was the deviation loop working
UNDER the outage.  CURVE-EXIT RULED (S1 spec §2): the criteria are
EMERGENT (bound-departure segmentation + ≥ 100 m emission discards
curve segments) and the actual fix is DIRECTION SYMMETRY —
forward/backward consensus, parameter-free; zero new constants.
`min_len_m` defaults to the owner's constant; `bound_m`
required-explicit until the re-measure.**

**S1's FINAL SUBSTANTIVE RESULT (2026-07-31) — (b) DISSOLVES; NO
CONFIRMED BUILD FAILURES; THE LINE FORKS:** none of (b)'s six is a
build failure (every spine node CLAIMED by minted runs — surv/drop,
never unclaimed; mechanisms: correspondence near-misses, TRANSVERSE
claims, shared-with-drops; (b) < 6 and overlaps (a)); the
fragmentation family is ~6, not 2; the SEVENTH refusal (no unpinned
re-bucketing — the owner's way-id+reason verdict supersedes)
endorsed.  **Canonical table PINNED: lateral = max perpendicular of
OUR endpoints from HIS chord — 32/16 under this definition or not
at all** (the canonical definition restores the ORIGINAL figures —
the number was never the problem, the unpinned definition was).
**SCHEDULING RULING: P7 is the CONSTRUCTION fork's critical path
(P7 → owner verdict → re-scoped re-acceptance → arm 3), and FORK B
— the LAW-DEFECT FILING — RESUMES NOW, independent of P7:**
(i) P3c runs immediately (band-ceiling provenance, offline on the
enriched capture inputs — authorized long ago, quiescent through
the S1 waves); (ii) class D RE-MEASURES on the frozen constructor
at filing time (its 1,629-sampled-45 predates the run-based and
≥ 100 m pivots — stale numbers are not filed to the owner) with the
authorized provenance instrumentation, offline on the capture —
measurement on a frozen constructor, expressly NOT a violation of
S1's hold.  The §6.4 filing assembles from P3c + current class D +
the ≥ 159 surfaced.  S1 HOLDING; 3 of ≤ 4 HECA, 1 held; arm 3
gated; nothing tuned.

**STEP 1 MEASURED (2026-07-31) — THE DEFECT REFRAMES TO SPINE
COVERAGE (all counts ±2, sixth self-catch: lateral unspecified by
direction — one canonical definition directed, table re-emitted
once):** HIS 16: (c) NO SPINE = 8 (five ~zero along their length);
(b) spine present, no run minted = 6 (OURS — S1's next item);
(a) dropped-sub-100 = 2 (fragmentation family).  CHORD-1 ≈ 368 =
**a spine-graph CONNECTIVITY HOLE** (zero edges between the runs) —
membership retired for the 375 m; explains every
tolerance-insensitive sweep.  Parallel-neighbour 3/33; the 30 await
the owner's verdict.  **RULINGS: the SPINE-COVERAGE defect is
NAMED as step P7 (upstream, grade_graph domain, step 0 =
source-presence in OUR inputs); the splitter code-read is PROMOTED
into P7; S1's constructor remainder = attribute (b)'s 6 + fold
(a)'s 2, then HOLD; stage-1 re-acceptance RE-SCOPED to the
spine-reachable subset (impossible-gate lesson) with full-map as
the joint gate.**  The constructor is closer to correct than the
counts implied — wrong-merge zero, wrong-split mostly the hole,
neighbour-tracking a tenth.

**STEP 0 RUN (2026-07-31) — THE INFERENCE SURVIVES; BASELINE
CORRECTED:** triple-loosened rule recovers only 3 pairs (~90 % of
both columns stand — the different-geometry question is REAL, not a
match-rule artefact; the 3 artefacts were still worth removing
first).  **Baseline is 31/15, never 32/16** (S1's FIFTH self-catch:
a `min`-vs-`max` lateral inconsistency between its own scripts, led
with).  Binding over-strictness = LATERAL (33-34 m vs 25; 1.0° and
14.3°), NOT the flagged overlap asymmetry — measurement over
intuition.  S1-15 re-classed WRONG-SPLIT (matched 38, wrong-split
8, columns 28/12).  Fourth fit-the-rule refusal endorsed.
**RULING on the budget question: the coordinator's keep-step-1-cheap
call STANDS with one carve-out — two cheap decisive filters run
NOW** (the PARALLEL-NEIGHBOUR scan on ours — S1-09's ~34 m/1.0°/
0.99-overlap signature, a named sub-class the owner's verdict
cannot decide in either direction; and the SPINE-EXISTENCE check on
his 12 — a source-data finding his verdict cannot supersede); the
full substrate bucketing holds for the owner's tagged-file verdict.
≈ 368 stop reason still owed (one line).  3 of ≤ 4 HECA, 1 held;
arm 3 gated; nothing tuned.

**THE CORRESPONDENCE TABLE (2026-07-31, zero builds) — THE COUNT
WAS HIDING A CANCELLATION:** matched 37/69 ours ↔ 30/46 his;
**wrong-merge ZERO** (suspicion class RETIRED — the construction
never over-merges at HECA); wrong-split 7 excess; dominant: **32
unmatched-OURS vs 16 unmatched-HIS, opposite directions, partially
cancelling** (7+32 vs the visible 23, reconciled by the 16) —
register 23.  **Chord-1's 375 m ATTRIBUTED: wrong-split at ≈ 368**
(179.3 m head orphan + ~20 m break + complete 3,599.6 m body); the
margin hypothesis PRE-EMPTIVELY KILLED by the existing 15-30 sweep
— no cycles.  **RULINGS:** the GEOMETRY-PARTITION test is the
priority zero-build item WITH MANDATORY STEP 0 (publish the match
rule; cross-match the 32 vs the 16 under looser correspondence
FIRST — the cheapest kill of the different-geometry inference,
register 21 applied to matching); step 1 buckets decide the fix
locus (match rule / membership / stop-conditions / SOURCE DATA —
his unmatched 16 may sit on routes the centerline data LACKS);
the ≈ 368 stop reason named from the table (one line); splitter
code-read queues BEHIND the test.  S1's inference held unacted —
correct.  3 of ≤ 4 HECA, 1 held; arm 3 gated; nothing tuned.

**THE 100 m FILTER MEASURED + ACCEPTANCE RESTATED (2026-07-31):**
286 → 69 survivors (≤ 50 FAIL as stated), dropped 217; **surviving
total 37,543 m vs owner 37,327 m = 0.6 %, UNTARGETED** — correct
geometry, split too fine; chord 1 untouched; the drop distribution
shows a GENUINE VALLEY (144 @ 25-50 m, then 4/2/2 to 125 m —
threshold robust ~60-130 m, corroborated not applied).  RULINGS:
(1) construction-vs-selection was ruled SELECTION in the crossing
turn (inventory minted unfiltered as measurement; string duty
≥ 100 m via owner-supplied `TAUT_STRING_MIN_LENGTH_M`, never
recalibrated by us; dropped runs' nodes = non-string spine — 
unchanged today, draw-toward at S1b).  (2) ACCEPTANCE RESTATED
three-part — length agreement (~2 %), coverage (end-to-end class),
count ≤ 50 vs the CORRECTED owner count (~51-56: the 5 real-offset
anomalies are 2-3 strings each under his own definition; the
anomaly track FEEDS the count gate — the independence claim is
corrected) — the count is NOT softened: fragmentation is the peg
mechanism (two endpoint datums per boundary; P3's 59-peg class).
Directed, one zero-build instrument: the SURVIVOR-TO-OWNER
correspondence table (corrected comparison + ~19-excess
attribution + wrong-merge/wrong-split + the 375 m gap in context).
(3) The SPLITTER QUESTION RE-OPENED bounded (Fable's "moot"
corrected on S1's evidence — the filter did not close the count):
code-reading only, does the route builder emit 1:1 by
construction; no redesign.  S1's refusal to force 50 endorsed
again.  3 of ≤ 4 HECA, 1 held; arm 3 gated; nothing tuned.

**RUN-BASED CONSTRUCTION MEASURED (2026-07-31) — THE MOTIVATING
CASE RECOVERS; THE COUNT GAP IS A SELECTION QUESTION:** chord-1
coverage 58.5 % → **89.8 %**, 2,366 → **3,599.6 m as ONE run** (the
0.86 m terminus dissolved — the run-vs-pair correction confirmed on
exactly the case that produced it); constants landed
(`TAUT_STRING_RUN_MARGIN_M = 20.0`,
`TAUT_STRING_ROUTE_ALIGN_DEG = 15.0`, correction chain at the
constant; pairwise gate carried forward in NO form; 29 tests).
**Count: 286 runs vs the owner's 46 — TOLERANCE-INSENSITIVE**
(286 across margin 15-30 m and align 10-15°; coverage identically
89.8 %): the honest reading, recorded — seated-in-empty-interval
constants SHOULD be insensitive (populations separated); the real
discriminators are authorship, maximality, and now SELECTION.  The
excess ~240 runs are STUB-SCALE (~28 m mean vs the owner's 811 m).
**RULINGS:** (1) the ~375 m chord-1 gap (89.8 % ≠ end-to-end) is
OPENED as its own item — extent attribution directed (zero-build,
the 1652 discipline: which end/span unclaimed; what stops
extension — margin, align, continuity, or a real spine end);
precedes re-acceptance; never absorbed into the count question.
(2) The SELECTION question goes to the owner (coordinator's ask
endorsed) with a three-reading frame ready, NONE asserted:
(a) STRUCTURAL — fillets/stubs/connectors are not routes (level-1
membership refinement beside the service exclusion);
(b) DIMENSIONAL — the owner's own selection rule, recorded as HIS,
never fitted; (c) TARGET-FIELD NEED — under strings-are-targets, a
28 m connector between trunks may need no string (its nodes draw
toward the trunks' targets); the map may be "the strings the target
field needs" — the reading that dissolves the gap without any
filter.  (3) S1's REFUSAL of a length/node-count filter is endorsed
normatively — the shape of the four retired proxies.  Nothing
re-based, nothing tuned.  Pending: join-vs-run confirmation
(zero-build); provenance + class-D (need the arm); arm 3 held
(3 of ≤ 4, 1 held).

**THE MARGIN CALIBRATED + THE CORRECTION CHAIN (2026-07-31):**
frame-checked, no-cutoff, spine-nodes-vs-owner-strings (the only
valid population — register 21): overall p50 8.48 / p90 15.45;
chord-1 p50 9.02 / p90 14.06 / max 18.43; clean set p90 11-18 /
max 13-21 m.  **"Small margin" ≈ 15-20 m, NOT sub-metre** — the
owner drew idealised runs through a spine that meanders around
them; the earlier ≤ 0.06 m was the map's INTERNAL straightness
(~250× too tight; coordinator corrected itself, S1 caught the
distinction).  RULED: `TAUT_STRING_RUN_MARGIN_M = 20.0` (derivation
recorded); MEMBERSHIP = three tests (margin + authored-direction at
the census-validated 15° + spine-path connectivity — margin alone
would claim crosser approaches); **Fable's flatline epitaph
WITHDRAWN as under-ranged** (the 0-5 m sweep sat in the bottom
quarter of the distribution — 23.4 % coverage at 5 m); the pairwise
design's death rests on the owner's rule + the 305-vs-40 count; the
5-20 m re-sweep is NOT OWED (the quantity no longer exists in the
run-based design).  Anomaly batch to the owner as ONE question — 8
ways (5 offset + 3 p50-level); expected-count gate 46 ± 8 pending.
S1 tuned nothing to these numbers; merge machinery stopped per the
hold; 3 of ≤ 4 HECA, 1 held.

**THE OWNER'S MAP + THE TERMINUS ATTRIBUTION (2026-07-31; four
rulings):** `/Users/noah/heca_strings.osm` — 40 strings / 88 nodes /
37,327 m; **chord 1 = ONE string, 3,974.8 m, max interior bend
0.00° ⇒ NO turn at 1652; the 58.5 % was an ASSEMBLY DEFECT,
definitively** (S1's 296 ≈ 7× over-assembly).  Terminus attribution:
at along-1652, ZERO candidates at the canonical ID; nearest
continuation 0.86 m away under a DIFFERENT ID (γ) — **the
endpoint-selection hypothesis is CONFIRMED**; 0.86 m is the second
sub-metre γ (with 0.54) against a γ median of 112.9 m.
**RULINGS:** (1) **membership goes COLLINEARITY-FIRST** — the
owner's object is the straight RUN (he drew independent runs: 2
shared endpoint pairs across 80 endpoints); chaining serves the
DATA's fragmentation, not the model's connectivity;
endpoint-identity demoted to one evidence source; membership =
collinear within threshold + along-contiguous within a RECOGNITION
tolerance.  (2) **the 0.86 m gap is a SOURCE-DATA NEAR-MISS, not a
grade_graph identity defect** (coordinator's read rejected on the
registry's own evidence: β = 0 and 0.86 > 0.5 — the registry is
CORRECT; in-repo precedent `BUILDING_FRONTAGE_NEAR_MISS_M`,
value-side recognition that mints no identity; widening the
interning radius would be the fifth proxy — refused).  IDENTITY ≠
MEMBERSHIP ≠ BRIDGING is normative (S1 spec §2); bridging stays
forbidden.  (3) **`TAUT_STRING_TURN_DEG = 6.0`** — one constant,
both uses (turn ≡ merge), calibrated on the 36 clean ground-truth
strings (≤ 5.0° interior), seated in the empty interval (5.0,
7.54), NEVER on the disputed outliers (7.54/67.4/90.9/119.1° —
**referred to the owner: "should these have been split?"**);
recognition tolerance fitted jointly so assembly reproduces the
owner's inventory (count 40 ± outliers; wrong-merge vs wrong-split
decomposed).  (4) **cap lift + class-D provenance instrumentation
AUTHORIZED** (both dump-only, offline on the capture): class D is
**~1,629 sampled-at-45** (45/45 datum-vs-anchor; excess median
2.618 m ≈ 1.7× the surfaced band-vs-anchor median) — the §6.4
filing states the sampling and the scale, never "45"; provenance
(adopted value + source node per defect) decides the radius-proxy
hypothesis before the filing claims anything.
**REVISED ARM-3 GATE CHAIN:** collinearity-first revision +
calibration → provenance table → class-D resolution (fix if the
proxy failed / file if genuinely contradictory) → stage-1
re-acceptance AGAINST THE MAP (count 40 ± outliers; chord-1
end-to-end; zero unresolved class D) → arm 3 spends the last HECA.
The assembly fixture re-bases to the map.

**STAGE 1 MEASURED — FAIL ON BOTH CLAUSES; THE GATE WORKED
(2026-07-31; capture = S1's 3rd of ≤ 4):** `/tmp/s1/s1_state.pkl`
(131,055 nodes, 645 authored chains, 3,741 clause-1 anchors, spine
7,126) — authorship + solve-state coexist for the first time.
**ATTACHMENT CENSUS: 100 % of spine nodes attach to an authored
route** (7,126/7,126; chord 1 707/707; multiplicity tail = junction
crossings) — the owner's coverage premise MEASURED TRUE at build
density; zero orphan fabric; no geometric fallback exists to tempt;
segmentation-independent, survives the turn ruling.  (ii-b) live:
137 adopted / 281 free-and-counted / fallbacks 231→197 / rewrites
1478→2257 / bends 122→165.  **Chord-1 acceptance FAILS:** largest
string 22 fragments / 225 nodes / along 1652→3977 = 58.5 % (orphans
0 — clause 2 holds); **45 `datum_infeasible` vs required ZERO**,
declared and routed, no softening path — as specced.  Arm 3 HELD.
**Coordinator's north-end measurement recorded with its limits:**
bins 1000-1400 hold segments DEAD-PARALLEL to the chord (median AND
max 0.0°) inside the uncovered region — WEAKENS the correct-cut
reading, does not refute it (25 m window cannot isolate the
authored route); the map settles.  Burden stays on ASSEMBLY,
provisionally.
**RULINGS:** (1) the 45 are **CLASS D — the first defects authored
by an owner-ruled mechanism** — and get the §2.2b-style
classification BEFORE filing (zero builds, on the capture: adopted
value vs other binding author over d at g; author classes named).
HYPOTHESIS framed, not acted on: the radius gate is a PROXY for
governance (proximity ≠ anchor-governance; a gated neighbour can
carry drape).  No radius tuning in either direction pending the
table (do-not-widen AND do-not-narrow).  The §6.4 filing is now:
≥ 159 surfaced + P3c band provenance + **class D with
sub-classification, presented as the "we can try" report-back the
owner asked for**.  (2) **The 1652 STOP ATTRIBUTION directed** —
offline on the capture (Stage 0 is pure; per-end stop reasons +
candidate inventory at fragment-scale bearings at the terminus) —
attributes WHY assembly stops without the map (the map rules
whether it SHOULD); the direct test of the endpoint-selection
hypothesis.  (3) Arm 3 held for the map + both classifications.

**OWNER SEGMENTATION REFINEMENT + GROUND-TRUTH OFFER (2026-07-31;
rulings):** the owner refines: strings are STRAIGHT TRUNKS, ending
at a turn, and offers to COUNT and MAP HECA's strings (KML/OSM).
RULED: authorship = MEMBERSHIP, straightness = SEGMENTATION (turns
cut authored routes into strings); axis separation normative
(straight in PLAN; bends only in ELEVATION where grade forces);
turn-criterion STRUCTURE ruled (authored-segment bearings at
fragment scale; junctions are not turns; authored breaks are not
turns; dense-node bearings never), THRESHOLD calibrated against the
owner's map then frozen — never invented.  **THE OFFER IS TAKEN —
request to relay:** KML LineStrings, one per string,
chord-1/chord-2 placemark style; a sequential name per string
(taxiway designator if convenient); TAXIWAYS ONLY (no service
roads, no runways); turns wherever THE OWNER considers the trunk to
change — his judgment IS the criterion, no threshold of ours; the
total COUNT stated as its own number; partial coverage fine (major
trunks alone are ground truth for those).  Uses: expected-count
assembly gate; wrong-merge vs wrong-split decomposition;
turn-threshold calibration set; assembly-fixture re-base target
(supersedes the dump-derived reconstruction for segmentation;
the capture fixture remains for density/endpoint mechanics);
negative controls with teeth (terminal-segment heading AND
dense-node bearing must FAIL against it).
**SEQUENCING — HOLD, SPLIT BY ROBUSTNESS:** the capture completes
(design-independent).  Stage-1 acceptance SPLITS: the
CHORD-1-SCOPED (ii-b) acceptance + the attachment census PROCEED
offline on the capture (chord 1 is straight end-to-end — a string
under every criterion on the table; authorship membership is
segmentation-independent); the FULL-INVENTORY assembly acceptance
HOLDS for the map + turn ruling (it would measure a segmentation
about to change).  **ARM 3 HOLDS** — the one held HECA carries the
FINAL segmentation; its three questions are re-confirmed at the
turn ruling.

**OWNER MODEL RULING + (ii-b) IMPLEMENTATION + THE STAGE-1 BLOCKER
(2026-07-31; three crossing waves resolved):**
* **The owner's "only long strings" question is RULED CONFIRMED**
  (spec §4.1 owner-model block; S1 spec §1b expanded): master
  strings = AUTHORED routes with datums, never an extent class
  (chord 2 at ~565 m IS a string; densification fragments never
  found strings; dense nodes attach BY AUTHORSHIP); "everything
  draws toward the master string" = the S1b end-state (fabric
  reference = grade-law projection from the string web; R
  re-founded as its apron instance; layer 6 shrunk to off-web
  fallback; harmonic gains string Dirichlet BCs), designed by Fable
  after S1's numbers.  S1's current work SURVIVES INTACT (not
  pausing it was right).  Fallback metrics re-scope to the trunk
  set; the ≥ 159 contradictions stay §6.4 defects (non-laundering
  clause).
* **Stage-1 blocker:** authorship and solve-state had NEVER
  coexisted in one dump — the §3 acceptance text asserted a graph
  nobody had (JOINT blind spot: spec-asserted artifact sufficiency
  without inventory, the P2-CP1 "no new dump needed" pattern
  recurring).  Fix: `O4_STRING_STATE_DUMP` (elev, hard, node_band,
  pos, spine_adj, chains, fabric/spine edges, bucket_to_idx),
  ★-marked with its reason — register 16 forward, second instance.
  **Coordinator's option-(a) call ENDORSED with true current
  grounds**: at decision time the design-independence asymmetry was
  correct; post-ruling the staleness risk didn't materialize (chord
  1 stays a master string), and (a) stands on its surviving ground —
  inputs-only capture + OFFLINE-FIRST so stage-1 acceptance GATES
  arm 3 instead of diagnosing it.  (c) (synthesized-elev proxy)
  rejected — endorsed.  S1 budget: 3 of ≤ 4 spent, 1 held.
* **(ii-b) implementation REVIEW: CONFORMS** — no band read;
  bounded spine-graph Dijkstra anchor gate; no-anchor ⇒ free +
  counted; ends only (split-span ends skipped; the 32 interior
  `no_datum` persist by design); adopted ends re-kind to
  `datum_infeasible` for §6.4; NO softening path or band-seat
  retreat in code; do-not-widen at the constant; 29 tests.
  Operationalization annotated in the spec (nearest non-spine
  neighbour, deterministic tie-break).
* **Arm 3 re-shaped by the capture:** the ATTACHMENT CENSUS runs
  OFFLINE on the capture dump (authorship + solve-state now
  coexist — zero-build); arm 3 carries (ii-b)'s W-CHORD1
  measurement + the build-scoped α-split, census confirmation only
  if the offline result needs it.

**α-SPLIT COMPLETE + (ii-b) OWNER-CONFIRMED (2026-07-31, zero
builds):** the split at phase-1 scope: **0 of 452 genuine α
rejections wrong** (452 correct crossers / 24 taken-by-earlier /
36 not-α; totals reconcile; the zero is a sub-bucket of 452, not an
empty total) — **admission exonerated AT PHASE-1 SCOPE ONLY**: the
split is measurable offline only in the arm where the defect is
absent (99.9 % assembly); build density's α population is
unseeable by it — the qualifier is mandatory wherever 0/452 is
quoted.  NEW HYPOTHESIS (S1's, inferred not measured, not acted
on — sharpens register 15): the build-density shortfall likely
sits in WHICH NODES the centerline projection selects as fragment
ENDPOINTS at density (denser `on_line` sets shift first/last
nodes), not in admission — and S1 identified why its own ×3/×6
experiment could not catch this: subdivision was WITHIN-fragment
and PRESERVED endpoints, so "density has zero effect" was always
scoped narrower than its label.  ZERO-COST PRICING: the
build-scoped α-split needs only piece IDs in the dump —
serialization only; S1 added `pieces` + `cand_pieces` ★-MARKED per
register 16 PROACTIVELY (the rule working forward, first
instance); 29 tests green; the split rides the next authorized arm
free.  **(ii-b) OWNER-CONFIRMED and SPEC'D** (S1 spec §3: adopted
anchor-governed fabric at trunk ends, live hook-moment value gated
by anchor-proximity `TAUT_STRING_END_DATUM_ANCHOR_RADIUS_M`
= 250.0; "we can try" = MEASURE directive — failure declares
`datum_infeasible` to the §6.4 filing, never a softened datum or
band-seat retreat; anti-band-seat rationale recorded: adopted
fabric carries no band read, cannot inherit the 137 band-vs-anchor
contradictions).  **S1 UNBLOCKED**: implement (ii-b) + tests +
offline acceptance (zero builds); **arm 3 = ONE held HECA**
carrying the (ii-b) emitted measurement (W-CHORD1 strictly
improves from −11.07, residuals witness-covered) + the
build-scoped α-split via the ★-marked payload — two questions, one
build, per register 19's yield rule.

**THE THREE ZERO-BUILD ITEMS DONE (2026-07-31) + rulings:**
minimal fallback INSTALLED as ruled (worklist spans, free-solved
facing ends, no blending; `fell_back` only when nothing strung;
29 tests).  §2.2b arithmetic DONE via the correct recognition that
the recorded `lo−hi` excess IS |z_A−z_B| − g·d: **≥ 146/179
SURFACED** (band authors provably predate the hook —
`node_band` built at solve.py:683; median excess 1.515 m is
material law contradiction, only 2/179 numerical) → the §6.4 owner
pathway, MERGED with P3c's band-provenance question into ONE owner
presentation (both are plausibly the same band-input defect); the
33 anchor-vs-anchor cases are honestly UNDECIDABLE until arm 2's
`anchor`/`xstring` relabel (installed at the call site, frozen
signature untouched) — claimed neither way.  Register 15 FALSIFIED
and re-recorded (endpoint sharing, not density — see the register).
**Endpoint-identity RULED: canonical-registry ID is the zero-length
definition; no chaining beyond it; arm 2 carries the α/β/γ
instrumentation (compared-wrongly / within-0.5 m / real-gap→STOP)
plus per-end stop reasons.  Part (ii)'s pass DEMOTED to phase-1
scope — bridgeless concatenability UNVERIFIED at build density
(22 fragments max vs the fixture's 36); third proxy in the
lineage.**  Fixture still NOT re-based (attribution first).
Remaining checkpoint: S1-CP2.  P3c blocks only the §6.6 owner
ruling.

## Step P4 — R2 reference tube  [SPEC READY 2026-07-30 —
`r2-reference-tube-spec.md`]

Opus-implementable.  Strictly after P3b (tube around a draped string
would lock the sag in).  One Fable checkpoint (R2-CP1) rules the flip.

## Step P5 — R3 flip + deletion + battery  [SPEC READY 2026-07-30 —
`r3-flip-and-deletion-spec.md`]

Opus-implementable, two-stage (flip-with-legacy, then row-by-row
hash-proven deletion).  Preconditions: P3b + P4 landed; **P0b —
SATISFIED 2026-07-31 by attribution** (root-line-only nondeterminism,
excluded by the body hash; P0c's test fix should land before the
battery as hygiene but no longer gates it mechanically).  Three Fable
checkpoints; the `one_solve.py` diff is reviewed by Fable personally;
battery sign-off is Fable + owner.

## Step P7 — SPINE-COVERAGE upstream defect track  [NEW 2026-07-31 —
named by Fable after S1's step-1 bucketing; plausibly the largest
single item remaining on this line]

**The defect class:** the spine graph lacks nodes/edges under real,
owner-traced taxiway centerlines — measured: 8 of the owner's 16
unmatched strings have NO spine under them (five with ~zero along
their entire length), and chord-1's ≈ 368 break is ZERO spine edges
between two runs on one continuous drawn taxiway.  One substrate
class, two presentations.  Three symptoms plausibly one mechanism:
missing spine, the connectivity hole, and `RouteChain` 1:1 (no
aggregation populated).
**Owner:** `grade_graph`/extraction domain — ABOVE S1's brief; the
fix is Fable-spec'd before anyone touches code.
**STEP 0 (pinned against the asserted-sufficiency trap; REFINED
2026-07-31 per the (c)-density signal):** for each of the 8 lines —
does centerline data exist in OUR SOURCE INPUTS (the OSM extract +
apt.dat) under his coordinates?  YES ⇒ loader/splitter/
graph-assembly defect (ours, upstream); NO ⇒ the owner's tracing
substrate exceeds our ingested sources — a source-ACQUISITION
question for the owner, not an extraction bug.  "They all trace
centerlines" proves data exists under his lines SOMEWHERE; step 0
establishes whether it exists in OUR inputs before any attribution.
**(c) is a DENSITY question, not a binary** (two "no-spine" ways
retain 17 and 5 nodes; the bucket was a within-25 m percentage) —
step 0 reports PER-LINE DENSITY PROFILES, never yes/no: partial
extraction/THINNING and ABSENT INPUT are different findings with
different fix loci.  **The ≈ 368 connectivity hole joins the same
profiling instrument** — a thinned region and a clean cut are
different mechanisms; the hole and the 8 lines are measured by ONE
tool in ONE pass.  Zero builds.
**The SPLITTER CODE-READ is PROMOTED into this track (from
queued):** (i) does the route builder emit 1:1 by construction;
(ii) where along source → loader → splitter → graph could whole
centerlines drop — a bounded READ (blast-first, no redesign),
reporting mechanism candidates.

**SECOND OUTAGE RECONCILED + OWNER RULINGS FOLDED (2026-07-31):**
the credit ran out MID-STREAM, and the coordinator's preserved
queue (`PENDING-unruled-queue.md`) was captured against the
unfinished turn — **verification on disk shows all six items were
in fact ruled and folded by the streamed edits** (disposition:
item 1 R3 commit → the model spec's R3-COMMITTED block + the S1
spec's COMMITTED block; item 2 dead primitive → NOT revived,
prior-art + register-16 harvest; item 3 added arcs → not a
tolerance defect, wrong scope, unasserted context; item 4 fixture
premise → the FIXTURE-PREMISE RULING block, a turn earlier; item 5
route_line=None → recorded as the manufacturing site, routed below
by the substrate; item 6 dead branch → spawned out, now running as
its own session — coordinate, don't duplicate).  The queue file is
DELETED after this reconciliation.  Register 24's protocol worked
again, with the refinement that a capture against a live stream
needs the disk verified before anything is re-ruled.
**THE OWNER'S THREE RULINGS:** ±8 m (constant chain 20 → 5 → 8,
each source recorded; `bound_m` wires at 8.0); the APT+OSM UNION
approved verbatim; **ACCEPTANCE REFRAMED — majority coverage of
long straight sections, explicitly NOT 100 %, not inventory
equality** (his purpose: smooth long straights to the string —
more faithful to a real airport).  Gates restated (model spec +
S1 spec): GATE A length-weighted majority coverage at ±8 (measured
state 95.6 % length-weighted, 12/12 ≥ 1000 m); GATE B chord-1
end-to-end; GATE C the W-CHORD witnesses; ≤ 50 as sanity.
Count-matching and correspondence equality DEMOTE to diagnostics;
the 8-anomaly answer to denominator hygiene.  S1 runs the
acceptance measurement itself (zero-build) — characterization
instruments are not acceptance instruments.

**THE CHARACTERIZATION LANDS — R3 COMMITS (2026-07-31):** the raw
tier IS the owner's model as-ingested (151 routes → 196 pieces,
−2 vertices/−0.1 m through the bend-split; **161/196 already
two-point straights**; no beziers); the fragmentation is
MANUFACTURED at ONE stage (`apply_route_arc_spine`: 151 → 653 ways;
`route_line=None` at `route_arcs.py:556-564` — one line explaining
BOTH RouteChain 1:1 and the 36-fragment tiling); ±5 m in the
processed spine is violated by ADDED synthetic arcs (junction
fillets to ~15 m; 120-550 m runway blends), not moved geometry; the
owner-described primitive already exists as DEAD CODE
(`_collapse_straight_edges` + five siblings, attic-only); the
discovery branch is DEAD (snapshot at pipeline:2253 precedes
discovery at :2540 — five of eight log lines describe discarded
output; (b3) retired WITH mechanism); effective input 287 edges /
255 nodes, not the logged 366/311; `len(on_line)<2` drops are
SILENT.  **RULINGS:** (1) R3 COMMITS — substrate = S2 ∪ OSM-linear
per D1, apt.dat-first dedup within ±5 m; `bound_m` WIRES at 5.0;
walk-claim census + settling test CLOSED as superseded; fixtures
re-freeze from S2; stage-1 acceptance returns to the FULL map.
(2) `_collapse_straight_edges` NOT revived — the walk is the
validated primitive; dead family = PRIOR ART with a register-16
harvest obligation.  (3) The added arcs are NOT a ±5 m conformance
defect (wrong scope — strings ruling; under S2 strings never see
them); recorded unasserted for other consumers, with the
`[w.size]*nseg` cap collapse noted as §6.4-filing context.
(4) Hygiene routed OUT of this line via a spawned task (the dead
discovery branch + misleading logs + the silent drop counter).

**D1 RULED BY THE OWNER + THE ±5 m MARGIN + THE SIMPLIFICATION
FRAMING (2026-07-31; three Fable rulings):**
* **R1 — per-consumer source policy** (the owner's distinction,
  cleaner than our (b1)): the May apt.dat-only ruling STANDS where
  aimed (clipping); strings are clipped against nothing, so they
  admit OSM linear where useful.  Recorded as a general principle —
  source admission is per-consumer, keyed to the consumer's failure
  mode — never as "the May ruling was relaxed".
* **R2 — the margin is OWNER-SUPPLIED: ±5 m**
  (`TAUT_STRING_SPINE_TOLERANCE_M = 5.0`; supersedes the 20 m
  directly; the contamination re-measure DOWNGRADES to explanatory
  — still run, register 21's fifth strike keeps its lesson;
  `SPINE_PERP_TOL_M = 1.0` consistent inside).  `bound_m` stays
  unwired pending R3 — the coordinator's hold was right.
* **R3 — the MECHANISM survives, the SUBSTRATE moves,
  CONDITIONALLY:** "the strings should BE the existing route
  network minus curves and intermediate nodes" = simplification of
  the EARLIEST-STAGE network; the walk's chord-growing +
  emergent-curve-discard + consensus IS the simplifier; the input
  tier moves from the processed spine to the RAW route network
  (apt.dat + OSM-for-strings).  COMMIT GATE pre-registered (the
  pattern that correctly killed the route-tier pivot): P7's
  raw-network characterization must show per-route polylines
  covering the owner's string-inventory class; an incoherent raw
  tier returns the ruling for redesign.  If committed: the
  processed-tier artifact classes dissolve (interning inter-chain
  edges — the 0.05-vs-0.5 question moots; the density/endpoint
  saga; plausibly bend-split fragmentation).  Spine-provenance
  answer relayed to the owner as measured (apt.dat; +0.953;
  76.2 %-within-1 m; the 110 edgeless at 0.0 %).  P7's
  characterization is now the construction fork's GATING item.

**STEP 0 + CODE-READ ANSWERED (2026-07-31) — THREE DEVIATIONS
RULED:**
* **D1 — the third branch neither fork named: the data EXISTS in
  our inputs (OSM linear `aeroway=taxiway`, 95.6 % mean over the 8
  lines vs 34.3 % apt.dat) and is DELIBERATELY EXCLUDED by the
  owner's 2026-05-27 ruling** (apt.dat-only; OSM fallback removed
  for then-unmeasurable misalignment — `pipeline.py:2188-2193`).
  The apt.dat taxi graph at HECA is 366 nodes / 311 edges /
  **111 components**; spine↔apt.dat correlation +0.953 (NOT an
  intervention — settling needs a build, and NO build is spent
  before D1 is ruled).  **RULED (b): to the OWNER** (register 22,
  doubly — his ruling, and its motivating evidence changed
  epistemic status: alignment is now MEASURABLE per-line).  The
  ask, shaped from his ruling's own logic: facts + three options —
  (b1) CONDITIONED re-admission (OSM linear admitted only where
  measured-aligned; honors the ruling's intent), (b2) keep the
  ruling, the 8 become apt.dat input defects, (b3) medial-axis
  (measured-not-covering: 595 centerlines yet zero spine here).
  Fable's read, flagged as ours: (b1).
* **D2 — the chord-1 "connectivity hole" is REFUTED** (raw spine
  under the owner's chord: full coverage, ONE component, a 19-node
  path through the 375 m region at max lateral 2.7 m): the hole
  was a property of the RUN-MEMBERSHIP population (~362 of 652),
  not the spine — **membership is BACK on the table for the
  375 m**; the coordinator's retirement claim was corrected to the
  owner.  DIRECTED, zero-build: (i) the settling test
  (shortest-path the two run node-sets through `spine_adj`; list
  the excluded intermediates with the predicate each failed —
  closes the assemble_runs-era attribution); (ii) **the WALK-CLAIM
  CENSUS** — the forward question: what does `walk_spine_runs`
  claim over the same corridor?  Heals ⇒ the miss closes as
  construction-specific; doesn't ⇒ the walk's stop reason is the
  live defect, with **M-new ranked** (`_NODE_KEY_M = 0.05` at
  `spine_synthesis.py` — 10× tighter than the canonical 0.5 m; the
  0.86 m near-miss ⇒ no shared node ⇒ no inter-chain edge — the
  code-read confirms NO rule ever creates one: 669 intra / 0 inter
  on chord 1).  The interning-alignment question (0.05 local vs
  0.5 canonical — conformance, not proxy-widening) is FLAGGED for
  after the census; no radius moves to swallow a number.
* **D3 — the sparse bucket is 6, not 8** (two ways fully covered in
  raw spine; the "17 nodes" figure was a RESIDUAL population, not
  raw spine — another register-21 instance, self-corrected to the
  owner).  `SPINE_PERP_TOL_M = 1.0` noted and HELD against the
  20 m margin re-measure (spine membership was always in the
  owner's "few meters" register).
* **Q1: `RouteChain` 1:1 is BY CONSTRUCTION** (memo on
  `id(route_line)` never hits — `route_arcs.py:564,567` rebuilds
  with `route_line=None`): symptom 3 RETIRED as evidence; the
  three-symptoms-one-cause framing is DEAD — the remaining two
  symptoms have DIFFERENT causes (D1's source question; M-new/
  membership), and P7 step 1 proceeds on the split.  M7 refuted;
  M2 ranked low; the wrong-quantity pavement column self-caught
  and not quoted (all sparse lines sit on REAL row-110 pavement —
  the valid result).
**Gate interaction (the impossible-gate lesson, applied
proactively):** stage-1 re-acceptance measures S1's constructor
against the SPINE-REACHABLE subset of the map until this track
lands; the FULL-MAP acceptance is the JOINT gate of both tracks —
no gate stands that the constructor cannot pass for upstream
reasons.

## Step P6 — R6 build-time review  [NOT Opus — Fable-5 agent BY LAW]

CLAUDE.md item 6: a Fable-5 optimization agent (lead-session-class)
reviews the accumulated stack whole-pipeline; already owed
independent of these steps.  Notes for it: (i) at OFF default the
§1.6 phase regression is absent (26.18 vs 27.65 baseline measured
2026-07-30); the ON-arm cost re-enters at P5 Stage A and is measured
there.  (ii) From P0b: every `to_osm` spawns two git subprocesses
(`rev-parse`, `status --porcelain`) costing ~52 of the ~54 ms emit
(vs 1.8 ms provenance-off) — under the 0.6 s hard-law line but pure
per-emission overhead AND the mechanism that widens the timestamp
flake window.  Candidate: per-build provenance cache (compute once
per process/(cwd, HEAD)), which also enables dropping wall-clock
time from the stamp — an owner-visible output-format question (P0c
Part 2) the review should carry to the owner with these numbers.

## Sequencing and parallelism

```
P0 DONE ── P1 ACCEPTED ── P3 DONE (class f; S1-CP1 ✓) ── P0b CLOSED
P0c (test fix, spec'd; any time before P5)
P2 (R1): CP1 ✓ (split-source ruled) ► final dump build ► wiring ► CP2
P2's dump ──► P3c (ceiling provenance, offline) ──► owner ruling §6.6
P2 ──► P3b (S1 impl; CP2 only) ──► P4 (R2, spec ready)
P3b/P4 ──► P5 (R3 two-stage + THE battery) ──► P6 (Fable-5)
```

Strictly ordered: P2 before P3b; P3b before P4; P4 + P0b before P5;
P5's battery last.  P3c needs P2's dump but blocks only the §6.6
owner ruling, not P3b.  Parallel-safe: any 0-build rung against
on-disk artifacts (P3c, P0b's analysis leg).  Builds are globally
exclusive across ALL agents — coordinate through the step reports.

## Risk register

1. **The S1 constructor** — now specified
   (`s1-taut-chord-constructor-spec.md`); residual risk lives at its
   two checkpoints (tube composition ruling; default flip).
2. **R3's pair-closure deletion** — now specified
   (`r3-flip-and-deletion-spec.md`, row-by-row hash proof); the
   `one_solve.py` diff is still reviewed by Fable personally (R3-CP2).
3. **The honesty-ladder deletion** (R1 scope) — rule 2's death changes
   `apron_reference.py` semantics; the R1 agent implements it ONLY
   under the gate, and the reviewer diffs that file personally.
4. **The field-moment decision** — checkpoint 1 is a ruling, not a
   coin flip; wiring before the ruling is wasted work at best.
5. **Anything touching `emit_decimate.py` chord tolerances** — out of
   scope entirely (spec §4.4 non-implication); flag any temptation.
6. **The P0b emission flake — CLOSED 2026-07-31**: attributed to the
   `o4_provenance_built` wall-clock stamp (root line only; geometry
   deterministic).  The body-hash protocol was never exposed to it —
   U1's proof stands by mechanism.  Residue: P0c test fix; the
   R6-carried output-format question.  The standing rule survives:
   suite-context full-file hashes are never identity evidence.
7. **The correlational-attribution trap** — P3 proved a constraint
   can sit exactly where the defect is and contribute NOTHING (the
   latent ceiling; masking moved 0.00 m).  Spec text must never
   licence stopping at a correlational reading; the S1 spec's §1a
   attribution rule is the canonical wording.  This was nearly the
   TENTH falsified mechanism on this line, and the trap was written
   by the reviewer — treat spec-authored shortcuts with the same
   suspicion as implementer improvisation.
8. **Open attributions in flight:** ~~the post-phase-A 2.2 m drag~~
   RESOLVED 2026-07-31 — the harmonic min-curvature solve (67.1 % of
   strung motion; S1 spec §1b; ordering ruled, S1b ordained).  Still
   open: the ceiling provenance (P3c).
9. **False-confidence fixtures** — S1's synthetic 62-piece chain
   PASSED under a mechanism the real geometry falsifies outright.
   Synthetic fixtures test the code's INTENT; only real-geometry
   fixtures test the MECHANISM against the world.  Rule: any
   assembly/recognition-class acceptance gate must run on a
   real-geometry fixture (frozen from a dump into `tests/fixtures/`);
   synthetic fixtures are unit tests of semantics only.  (S1 spec
   §6 test 8(iii) is the worked example.)
10. **Background waiters false-CLEAR** — P0c's waiter reported clear
   while the watched build was alive (re-armed on the exact PID and
   held five minutes).  The standing-constraints waiter rule (exact
   PID + `kill -0` re-verify after loop exit) is normative; a waiter
   that cannot name its PID does not gate a build.
11. **Rulings 2026-07-31 (small, interface-shaped, recorded):** the
   S1 level-1 authorship export is UNGATED with three conditions
   (S1 spec §2 — identity-with-revert proof, build-time statement,
   a reader lands with it); the suite comparator is ATTRIBUTED-DELTA
   (spec §5.0 rebase semantics — additions are Fable rulings only).
   **CORRECTED same day: the live set is 24, not 23** — ledger entry
   1 removed a member the 24F set never contained (the flake; the
   nine-file breakdown sums to 24 with zero `test_layout.py`
   entries; P0's 25 = 24F + flake).  Entry VOIDED in place; the
   reconciliation rule (per-file counts vs membership claim BEFORE
   any ledger write) is now part of §5.0's discipline.  The failure
   mode: a reconciliation never performed, with the breakdown in
   front of us.  Underspecified-authorization lesson stands: an
   interface authorization that does not state gated-or-ungated is
   INCOMPLETE — implementers ask, Fable answers, THEN it lands.
12. **Proxy gates** — a gate stated as an easy proxy (centerline
   COUNT) for the real property (bridgeless concatenability) forced
   a stop-and-rule when the proxy failed while the property held
   (S1's authorship census: 75 authors, yet zero-length-gap
   collinear tiling at 95.9 % of metres).  Rule: gates are stated in
   the property's own terms — metre extents and gap structure, never
   member counts; node-count percentages are never gate currency
   across layout densities.  Companion to items 7 (correlational
   attribution) and 9 (false-confidence fixtures): three ways a
   measurement can be honest while the CLAIM it feeds is wrong.
13. **Subset fixtures lose the competition** (the fourth taxonomy
   entry; S1's self-catch, adopted verbatim): *a real-geometry
   fixture must preserve the COMPETITION, not just the geometry.*
   S1's first fixture froze only the chord-touching fragments and
   the FALSIFIED window-0 mechanism passed at 99.9 % on it —
   subsetting removed the competing junction candidates, so real
   geometry tested intent again (items 9/12's pattern one level
   down).  Corollary: a mechanism fixture carries its own NEGATIVE
   CONTROL — the test proving the mechanism necessary (window 0
   FAILS) doubles as the fixture's validity proof.  Found via a
   FAILING test, not a weakened assertion — the right way.
14. **`O4_TEST_AIRPORTS` does not scope what our guidance says**
   (measured 2026-07-31): a `O4_TEST_AIRPORTS=HECA` law-true run
   built CYXY, SPJC and SPLP too (708.88 s, four airports).  The
   conftest reads the variable (~line 220) and documents it as an
   ICAO list that "takes precedence", but it does not restrict every
   parametrized law-true test.  BUDGET RULE until fixed: price a
   "single-airport" law-true run as FOUR airports (~710 s).  The
   leak was beneficial here (it surfaced the CYXY invariant
   regression), so the fix shape — strict scoping vs documented
   partial scoping plus a stricter opt-in — is a DESIGN question for
   a small Fable-spec'd hygiene step, deliberately not scheduled by
   an implementer.  Every spec mention of the variable now carries
   this caution.
15. **~~Fixtures must preserve DENSITY too~~ — FALSIFIED BY ITS OWN
   AUTHOR, RE-RECORDED (2026-07-31): fixtures must preserve
   ENDPOINT-NODE SHARING.**  Interventional, one variable: density
   ×1/×3/×6 → identical assembly (256 strings, 36 fragments,
   99.9 %); endpoints NOT shared → 647 strings, 1 fragment, 15.9 %.
   Density had ZERO effect; endpoint sharing has TOTAL effect — the
   build-density shortfall is a TILING failure.  DOUBLE OWNERSHIP,
   on the record: S1 supplied a plausible label instead of an
   attributed one (its own words), and **Fable RATIFIED it into
   normative text without demanding the mask** — the register's own
   correlational-attribution rule, violated by author AND ratifier
   one entry after writing it.  The corollary survives corrected:
   fixture re-basing requires the attribution FIRST, and the
   re-based fixture preserves ENDPOINT-SHARING STRUCTURE at build
   density with the terminal-segment negative control
   re-established.  Kept in-place as the audit trail's second
   worked example (with the comparator ledger's entry 1).
   **SHARPENED by the α-split (2026-07-31; hypothesis, not
   measurement):** the ×3/×6 "zero effect" arm SUBDIVIDED WITHIN
   fragments and PRESERVED endpoints — its scope was always
   narrower than its label.  Candidate mechanism: ENDPOINT
   SELECTION — the centerline projection may pick different
   first/last nodes at build density, changing the sharing pattern
   without any endpoint drifting.  Unacted-on; decided by arm 3's
   build-scoped α-split (rides free via the ★-marked piece IDs).
16. **Warning comments are load-bearing spec** (CP2b's CYXY half):
   R1 absorbed four mechanisms; one carried a ★ comment naming the
   exact failure mode at the exact airport that the absorption then
   reproduced (service refs re-importing the pre-follow profile —
   CYXY service pairs, 8.95 % then, 5.47 % now).  Rule: when a step
   ABSORBS or DELETES a mechanism, its warning/★ comments are
   harvested FIRST as conformance obligations on the replacement —
   a checklist artifact in the step report, not a hope.  Binding on
   P5/R3's row-by-row deletions (obligation added to that spec).
17. **Output labels are claims** (the +N attribution; third
   self-catch of the line): a script's column label is itself a
   claim that must be RECONCILED against what the computation
   actually models — P2's "FIX-MINTED" column modelled the PRE-fix
   A-sourced field, and the honest reading inverts the label.  P2
   reported the inversion rather than the tidier reading.  Sits
   with 7/9/12/13/15 in the taxonomy; the reconciliation rule
   applies to labels, not just member counts.
18. **Falsified-by-arm-2 (recorded per the register's own
   discipline):** the γ dropped-junction-node hypothesis (Fable's,
   from the identity ruling) — γ endpoints sit at median 112.9 m
   (genuine terminals: apron edges, boundary), not sub-metre; and
   the registry-interning question — β = 0 at build density, the
   registry is clean.  Both labeled plausibly at authoring, both
   killed by the histogram, neither acted on before it.
19. **Two-site arms are a METHOD, not a lucky habit** (named after
   the second proof): an arm that can run at a second independent
   failure site for marginal cost MUST (ARM-5's second site cost
   38 s against a 398 s primary); a single-site heal is an
   ownership claim AT THAT SITE ONLY, and cross-site disagreement
   is decomposition evidence, not noise.  Proof 1: the step-1
   HECA/CYXY disagreement exposed the service sub-domain defect.
   Proof 2 (P2's words): "Had I run only HECA, the building199
   heal would have read as 'found it'; CYXY is what prevents
   that."  Corollary: an arm's YIELD is sites × instrumentation —
   rider-2 dumps and a second site turn one build into a
   decomposition, which is how CP2b resolved three failures to
   three owners inside an exhausted budget.
20. **Analysis joins obey production key discipline** (the fourth
   self-catch, and it would have INVERTED the decomposition): P2's
   first script keyed R by INDEX across passes whose node lists are
   REBUILT (131055/126175/128163) — every cross-pass lookup was
   n/a and it printed `spread = 0.000 m`, i.e. "R is stable across
   passes", the exact inverse of the measured 1.397 m, which would
   have exonerated the moment axis and sent the decomposition to
   the wrong layer.  Caught before reporting (register 17 catching
   a LIVE error).  Rule: cross-pass/cross-space joins in ANALYSIS
   scripts key by site/canonical identity, never by index — the
   rod-key lesson applies to measurement code, not just production
   carries.
21. **A margin is only as valid as its population** (four
   near-instances in ONE wave, different agents, same trap):
   emitted polygon nodes saturating at pavement half-width
   (coordinator, discarded); nearest-string assignment admitting
   taxiways not in the map at all, p90 196 m (S1, discarded and
   self-named); the map's INTERNAL straightness (≤ 0.06 m) quoted
   as the spine-to-string margin — a ~250× error (coordinator,
   corrected: the owner drew idealised runs through a spine that
   MEANDERS ~15-20 m around them); and a report-level "jitter
   scale ~1-2 m" guess (Fable, wrong mental population).  Rule:
   before ANY distance distribution is quoted as a tolerance, name
   the population and verify it is the quantity the algorithm
   consumes.  Companion to 17 (labels are claims): a number can be
   correct for what it measured and meaningless for what it is
   quoted as.
   **FIFTH STRIKE — THE SHIPPED-CONSTANT EDITION (2026-07-31, full
   weight; the ratification was Fable's):**
   `TAUT_STRING_RUN_MARGIN_M = 20.0` was calibrated from
   owner-string-to-spine distances **while the sibling track (P7)
   was investigating MISSING SPINE** — the population plausibly
   contained the very holes under investigation, inflating the
   distances (the owner's own bound: "within a few meters"; S1-09
   rejected at 34.1 m).  First time this trap reached a LANDED
   VALUE rather than a report.  NEW COROLLARY, normative: **a
   calibration population must be checked for the defect class
   under investigation** — especially when a sibling track exists
   for exactly that defect.  The contamination re-measure
   (clean-coverage stations only, sharing P7's density profiles) is
   directed with the outcome pre-registered; the constant's epitaph
   is written only when the clean distribution lands.
22. **Intent questions route to the source** (the selection
   hypothesis, killed by one owner sentence where measurement would
   have cost a build and rounds): the line's measure-first
   discipline is for MECHANISMS; hypotheses about OWNER INTENT
   ("did he draw every run or a curated set?") have a cheaper
   oracle — ask.  The complement of ground-truth-beats-proxy, not a
   contradiction of mechanism-before-fix: reaching for an
   interventional arm before the ask is its own waste shape.
   (Worked example: "runs the owner simply did not draw" —
   falsified by "I drew almost every straight run"; the ~240 excess
   became SPURIOUS over-fragmentation, and the selection frame
   retired without a single build.)
23. **Aggregates cancel — decompose before diagnosing** (the
   correspondence table): the 69-vs-46 count hid TWO
   opposite-direction defect classes (7 wrong-splits + 32
   unmatched-ours, offset by 16 unmatched-his) — the bare gap of 23
   UNDERSTATED the defect mass because the classes partially
   cancelled.  Gates may be aggregates (the owner's ≤ 50 stands);
   DIAGNOSIS never is.  Corollary, register 21 applied to matching:
   an unmatched column is only as valid as the match rule that
   produced it — cross-match the unmatched sets against each other
   BEFORE claiming "different geometry" (a too-strict rule counts
   one same-geometry pair once in EACH column).  Companion to 17
   and 21: correct as a gate, misleading as a diagnostic.
24. **Design-authority continuity** (the 2026-07-31 spend-limit
   outage, survived): the Fable lead terminated mid-fold; what made
   it survivable was that the rulings had been DELIVERED VERBATIM
   IN THE REPORT BODY before the doc edits ran.  Made deliberate,
   two rules: (i) rulings are always delivered in full in the
   report body — the report is the survivable copy, the docs are
   the durable one; (ii) the RECOVERY PROTOCOL is named: the
   coordinator preserves pending rulings verbatim in a marked
   NON-SPEC file, authors nothing, rules nothing, queues deviations
   — the loop is held open, never bypassed — and the returning
   authority folds and deletes the preservation file.  Executed
   once, worked (`PENDING-fable-rulings-spine-walk.md`, folded and
   deleted 2026-07-31).

## Review contract (what the reviewer checks per step)

Byte-identity method and hashes (not claims); gate-off equivalence;
the measured gate table vs this plan's acceptance lines; build-time
statement numbers; blast.py output for every edited file; the step
report's PARTIAL/COMPLETE honesty against the diff; no new ad-hoc
`layout._*` artifact stashes (grep gate); no scope creep past the
step's ladder rung.

**Deviation loop mechanics:** the implementer files the deviation
report (format in THE DEVIATION RULE above) and STOPS that step; the
coordinator resumes the Fable lead, whose approval — or redesign —
lands BEFORE any code past the divergence point.  Approved deviations
are recorded in the step report AND, when they change normative text,
folded into the spec by Fable (never by the implementer).  An
implementer who is unsure whether something is a deviation treats it
as one — the false-positive costs minutes.
