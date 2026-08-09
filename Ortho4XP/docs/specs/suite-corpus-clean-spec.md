# Suite-corpus-clean spec — the full pytest suite writes NOTHING into the shared data repo

Lane: `lane/suiteclean` (worktree `.claude/worktrees/suiteclean`, base `e2662ae`).
Author: Fable lead (design artifact; implementation is delegated per
`Ortho4XP/CLAUDE.md` §"Working style").  Owner-law canon: `docs/RULINGS.md`
(one-shared-data-repo `e9daef5`, consult-before-create `7e90032`,
instrument-truth 2026-08-06).  A brief that would violate a listed ruling is
invalid — stop and report.

## 1. Problem and goal

`/Users/noah/XPTerrainBuilderData` is THE corpus every lane mounts.  The
cycle-7.5 hygiene round redirected ONE suite leak (the `test_dsf_texture_modes`
path-keyed DSF dump cache) and left the rest as a *registered allowance*:
`tests/conftest.py::_SUITE_MAY_WARM` still authorises the suite to write the
`airport_mod_cache` and `dem` scopes.  Consequence, measured 2026-08-08: a
guarded HECA harness build running concurrently with the suite was refused
after suite tests rewrote `Airport_mod_cache` paths (an SPJC cache path in the
blocked list; 646 s wasted).  The trap lives in the root `CLAUDE.md` under
"Traps still on you" only because of this.

GOAL: the full suite (`venv/bin/python -m pytest tests/ -q`) is CORPUS-CLEAN —
zero writes under the shared repo — and the property is ENFORCED per test, not
asserted per session, so suite-parallel-to-guarded-builds becomes lawful and
the trap moves to the "harness now makes impossible" list.

Non-goals: no change to what any test MEASURES (reads stay warm from the
shared corpus); no change to harness build behaviour; no timing claims
(per-change timing gates are SUSPENDED, RULINGS 2026-08-04 — the ledger
tripwire covers anomalies).

## 2. Phase A — instrumentation (enumerate every offender)

### 2.1 `SharedRepoWriteGuard` gains a record-only mode (extend, never fork)

`tools/harness/build_airport.py::SharedRepoWriteGuard.__init__` gains one
keyword parameter, `record_only: bool = False` (frozen public API; do not
rename existing parameters).  Behaviour: in `_refuse`, after appending the
`{"path", "scope", "via"}` entry to `self.blocked`, if `self.record_only`
return WITHOUT raising, so the intercepted call PROCEEDS.  Everything else —
prefix matching, symlink resolution, the `.lock` and library-index allowances,
hook restore — is byte-identical.  Rationale: the audit must observe the
suite's TRUE current behaviour; blocking would change test outcomes and
measure a different suite.

### 2.2 Per-test audit fixture in `tests/conftest.py`

New function-scoped autouse fixture `_shared_repo_write_audit`, active ONLY
when `O4_SUITE_WRITE_AUDIT=1`:

* Obtains the guard class through `_harness_build_module()` (the detector's
  own loader — ONE code path, never a second import route).
* Wraps each test in `SharedRepoWriteGuard(set(), root=<engine root>,
  repo=DATA_REPO, record_only=True)` where `<engine root>` is
  `os.path.dirname(_HERE)` (the `Ortho4XP/` dir whose mounted data-dir
  symlinks the guard needs for its prefix set).
* On teardown, for every entry in `guard.blocked`, `guard.lock_churn`, and
  `guard.library_index_churn`, appends one JSON line
  `{"nodeid", "kind": "blocked"|"lock_churn"|"lib_index_churn", "path",
  "scope", "via"/"op"}` to the file
  `${O4_SUITE_WRITE_AUDIT_OUT}.${PYTEST_XDIST_WORKER-master}` (one file per
  xdist worker; `O4_SUITE_WRITE_AUDIT_OUT` is a required absolute path when
  the audit is on — refuse loudly if unset).
* Nesting is safe by construction (pytest fixture LIFO + the guard's saved
  originals); `test_harness.py`'s own guard tests install inner guards on tmp
  repos and must keep passing unchanged.

The audit is expected to catch Python-level writes; the session detector
(`_the_shared_data_repo_survives_the_suite`) stays as the C-extension backstop
during the audit arm — defence in depth, per the guard's own docstring.

### 2.3 The audit arm

One full suite run, in THIS lane, cwd `<lane>/Ortho4XP`:

    O4_SUITE_WRITE_AUDIT=1 O4_SUITE_WRITE_AUDIT_OUT=<lane>/Ortho4XP/tmp/suite_write_audit.jsonl \
      venv/bin/python tools/run_with_ledger.py --label suiteclean-audit -- \
      venv/bin/python -m pytest tests/ -q

Before launching: verify no guarded harness build is running (`ps` for
`build_airport.py` / `Ortho4XP.py`) — the audit arm is still an UNGUARDED
suite on the shared corpus and the concurrency trap is exactly what this lane
is removing.  Expected wall ≈ 13 min (ledger precedent: 11 failed, 5481
passed, ~750 s).  The standing-red set from the ledger arm is the baseline
FAILED list; record it.

DELIVERABLE: the offender table — `nodeid → path → op → scope`, aggregated to
(test module, path-class, scope) with counts, plus the raw JSONL retained in
the lane.

## 3. Phase B — redirects (decision rules; final per-class calls are a Fable
## review of the offender table, not an implementer's choice)

* **R1 — FNAMES-rooted derived caches** (expected: the `Airport_mod_cache`
  sidecar writers in `auto_patch/{dsf_reader,agp_reader,
  object_terrain_assembly,post_mesh}.py`, `O4_Airport_Elevation_Insets.py`):
  introduce ONE module-global cache root per family in `O4_File_Names.py`,
  following the existing `Default_dsf_cache_dir` pattern exactly (assigned in
  `_apply_data_root`, session-redirected in conftest, re-applied after module
  reload via the existing `reapply_dsf_dump_cache_redirect` mechanism —
  extend that function rather than adding a sibling).  Call sites switch from
  `data_path("Airport_mod_cache", …)` composition to the global.  Run
  `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each file.
* **R2 — warm-read preservation**: where a redirected root would make a warm
  shared artifact invisible (cold rebuild per session), the session fixture
  SEEDS the lane-local root read-through: copy the specific SMALL derived
  sidecars the suite needs (measure sizes in the audit review; hard cap
  ~64 MB total copied per session — above that, escalate to the lead, do not
  improvise).  Large payloads are never copied; if a reader needs one, that
  is a per-offender design question for the Fable review.
* **R3 — path-keyed junk writes** (the DSF-dump class): plain tmp redirect,
  no seeding (nothing ever reads them back).
* **R4 — test-local bugs** (a test writing a shared absolute path directly):
  fix the test to `tmp_path`.
* `_SUITE_MAY_WARM` shrinks to `{}` IN THE SAME COMMIT as the redirects, and
  the two conftest docstrings + the detector's failure text stop describing
  mod-cache/dem as registered exceptions.

## 4. Phase C — the permanent per-test guard (enforced, not asserted)

New function-scoped autouse fixture `_no_test_writes_the_shared_repo`,
default ON for every test:

* Installs `SharedRepoWriteGuard(set(), root=<engine root>, repo=DATA_REPO)`
  in normal REFUSE mode — a shared-repo write raises
  `SharedRepoWriteBlocked` at the call site, failing exactly the test that
  wrote, with a traceback naming the writer (per-test attribution; the
  session detector's `-n0` re-run dance becomes unnecessary for Python-level
  writes).
* The class's built-in allowances stand: `.lock` coordination churn and no-op
  ensure-dirs pass (recorded on the guard instance).  The LIBRARY-INDEX
  allowance is guard-internal and stays for harness builds, but for the suite
  the acceptance bar is zero persistent deltas — if the audit shows the suite
  rewriting `o4_library_index*`, that class is redirected in Phase B like any
  other offender, not allowed through.
* `O4_ALLOW_SHARED_REPO_WRITES=1` disables this fixture AND (as today)
  downgrades the session detector — one knob for the rare deliberate case.
* When `O4_SUITE_WRITE_AUDIT=1`, this fixture yields to the audit fixture
  (record-only) — never two guards stacked.
* The session-scoped detector STAYS, with an EMPTY allowance register: it is
  the only instrument that sees C-extension writes and session-fixture-window
  writes.  Its message drops the "registered, explained exceptions" language.

## 5. Twins (instrument-truth law: no instrument without a known-answer twin)

In `tests/test_harness.py` (extend the existing §§ around lines 1451–2230):

1. `record_only=True`: a tmp-repo write is RECORDED in `guard.blocked` AND
   PROCEEDS (file exists afterwards), and no exception is raised.
2. The audit fixture's pure core (factor the "guard results → JSONL rows"
   step into a plain function) gets a known-answer twin: given a guard with
   one blocked entry + one lock-churn entry, exactly two rows with the right
   `kind` come back.
3. The permanent guard is LIVE during tests: a test asserts
   `builtins.open` is not the interpreter original while it runs (mirror
   `test_the_dsf_dump_cache_is_not_the_shared_repo_during_tests`'s live-assert
   style), and a tmp-repo refusal twin proves the mode.
4. `_SUITE_MAY_WARM == {}`: rewrite
   `test_every_suite_warm_scope_is_a_real_scope_with_a_reason` into the
   stronger `test_the_suite_has_no_standing_write_allowance` (empty dict, and
   the docstring records WHY it emptied — this lane, the 646 s precedent).
5. Update `test_the_shared_repo_detector_flags_a_test_written_cache`: the
   mod-cache and inset rows in its synthetic diff are now UNAUTHORISED — the
   known answer becomes all three paths, sorted.
6. Existing guard twins (BLOCKS/ALLOWS/noop-ensure-dir/symlink-follow/restore)
   must pass UNCHANGED — they are the regression net for the `record_only`
   extension.

## 6. Acceptance (the lane's exit bar)

1. Two full suite runs, post-redirect, via
   `venv/bin/python tools/run_with_ledger.py -- venv/bin/python -m pytest
   tests/ -q`, from `<lane>/Ortho4XP`, NOT concurrent with any guarded build
   (ps-check before each; standing reds make the runs re-execute rather than
   ledger-skip, which is what we want here).
2. Around EACH run, an independent before/after corpus snapshot using the
   harness's own `shared_repo_snapshot`/`snapshot_diff` via `python -c`
   (harness functions, no new tool file — consult-before-create satisfied);
   REQUIRED RESULT: zero added / zero modified / zero removed, both runs.
3. The FAILED set of each run is compared, sorted, against the standing
   11-red baseline (matched control = the audit arm's own FAILED list on this
   same tree; memory law: failure counts need a matched control) — UNCHANGED,
   or the difference is attributed line by line before merge.
4. All new twins green; `pytest tests/test_harness.py -q` green except
   standing reds (none expected in that module).
5. Root `CLAUDE.md`: the "Traps still on you" guarded-vs-unguarded entry
   moves to "Traps the harness now makes impossible", rewritten to name the
   per-test guard, the emptied allowance register, and that suite-parallel-
   to-builds is now lawful (timing runs still exclusive per standing law).

Budget statement (build-budget discipline): three full-suite runs
(~13 min each ≈ 40 min wall) + unit-twin runs (<2 min).  ZERO harness airport
builds.  Build-time impact: none on production paths — the guard exists only
under pytest (conftest fixtures); the R1 call-site change replaces a
`data_path()` string-join with a module-global read.

## 7. Convergence guards (mandatory, CLAUDE.md 2026-08-02)

Materiality floor: n/a (no elevation/grade targets).  ATTEMPT CAP: 2 fix
iterations per phase; a second miss is STOP-and-report.  PROGRESS HEARTBEAT:
long stages write START/step/EXIT stamps to `<lane>/Ortho4XP/tmp/.progress/`.
Any deviation from this spec is reported back for a Fable ruling, never
decided by the implementer.

## 8. Post-audit rulings (Fable review of the Phase A offender table, 2026-08-08)

### 8.1 Evidence

Audit arm (ledger label `suiteclean-audit`, rc=1, 733 s): **zero `blocked`
rows** suite-wide; 178 `lock_churn` rows = `os_open`+`remove` pairs on
`Elevation_data/<tile>/.lock_*` from `ensure_base_tile` (ruled coordination
state, transient); zero `lib_index_churn`.  ONE real leak, caught only by the
session detector (4 errors, one per worker):
`Default_DSF_cache/2e32f218/+50+010.dsf.tmp.text` — written by the DSFTool
SUBPROCESS, structurally invisible to any Python-level guard, and
interleaving-dependent (a `-n0` control of the two suspect modules leaked
nothing).  Baseline: 11 failed / 5569 passed / 23 skipped / 12 xfailed
(`tmp/failed_set.txt`, `tmp/error_set.txt`).

### 8.2 The zero is state-dependent, not structural

Per-pack sidecars (`o4_object_*`, `o4_dsf_*`) and the library index are
fingerprint/version-keyed derived caches: a tree whose cache keys drift from
what the shared corpus is warm for REWRITES them — that is the 2026-08-08
morning incident's class ("an SPJC cache path refused a HECA build", 646 s),
and it is invisible to an audit run from a tree whose keys match.  Redirect
decisions therefore key on class structure:

* **R-a `Default_DSF_cache` — env-override redirect.**  `_apply_data_root()`
  honors `O4_DSF_CACHE_DIR`: `Default_dsf_cache_dir = os.environ.get(
  "O4_DSF_CACHE_DIR") or data_path("Default_DSF_cache")`.  Every recompute
  path (module reload, `set_data_root`) flows through `_apply_data_root`, so
  the redirect survives them BY CONSTRUCTION.  The session fixture sets the
  env var (keeping the direct assignment + `reapply_dsf_dump_cache_redirect`
  as belt).  TWIN: in-test `importlib.reload(O4_File_Names)` with NO reapply
  call → `Default_dsf_cache_dir` still lane-local.  That twin is the
  interventional proof for the whole clobber class; the exact worker
  interleaving behind `2e32f218` is deliberately not reproduced (lead ruling:
  the fix immunizes every class member, and the reload twin proves it).
* **R-b `Airport_mod_cache` — env-override + symlink-seeded overlay.**  New
  FNAMES accessor `airport_mod_cache_root()` = `O4_AIRPORT_MOD_CACHE_DIR` env
  or `data_path("Airport_mod_cache")` — resolved AT CALL TIME (the
  cwd-following behavior `dsf_reader.airport_mod_cache_dir`'s docstring marks
  load-bearing is preserved when the env is absent).  Adopters: that helper,
  and `agp_reader`'s `cache_directory` (the library index rides along).
  Suite session fixture, per worker: create a tmp overlay root, mirror the
  shared cache's directory tree, symlink every regular file (~991 measured —
  instant), set the env.  Sidecar writers are `tempfile` + `os.replace`
  (verified: agp_reader 343, post_mesh 347, object_terrain_assembly 882 —
  `os.replace` swaps the symlink and never follows it; VERIFY dsf_reader's
  own sidecar writers during implementation and report any direct-write
  pattern found).  DSFTool pack-dump subprocess writes also land in the
  overlay because their target path comes from the accessor.  Interaction
  noted for the merge report: the parked idxchurn lane (`9e54727`) codifies
  library-index placement for HARNESS builds; this is suite-side only and
  does not conflict.
* **R-c `Elevation_data` — NO redirect; refuse loud.**  A privately-cut
  inset is a private measurement FRAME — the two-corpora defect itself
  (warm-vs-cold has moved terrain 12 m).  A suite build needing a cold or
  frame-drifted inset must FAIL, naming the path and the explicit harness
  refresh (`build_airport.py --refresh-data dem`).  The `.lock` allowance
  keeps `ensure_base_tile` cross-process coordination lawful.
* **R-d lock churn** — allowance stands in the suite guard; transient by
  construction; the acceptance snapshots must show zero PERSISTENT deltas.
* **R-e library-index allowance** — `SharedRepoWriteGuard` gains
  `allow_library_index: bool = True`; the Phase C suite guard passes False.
  With R-b in place nothing should reach it; the param turns any bypass into
  a loud refusal instead of a silent shared write.

### 8.3 Phase C amendments

§4 stands, amended by R-e.  `_SUITE_MAY_WARM` → `{}`; the detector's message
and both conftest docstrings drop the "registered exceptions" language; the
audit fixture and the permanent guard never stack (audit env wins).

### 8.4 Twin deltas

§5 twins stand, plus: the R-a reload-immunity twin; an accessor twin
(env set → override path; env absent → `data_path` cwd-following); a
seeding twin (pure mirror+symlink function against a synthetic shared tree,
known answer); an `allow_library_index=False` refusal twin; the detector
known-answer update (all three synthetic paths now unauthorised, sorted).

### 8.5 Acceptance amendments

§6 stands, plus: ZERO session-detector errors in both arms (the 4-error
class dies with R-a); counts compared against the audit-arm baseline
(11 / 5569 / 23 / 12).  Arms run SERIALLY, never concurrent with each other
or any guarded build.
