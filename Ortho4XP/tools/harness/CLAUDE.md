# Harness traps (moved from the root CLAUDE.md 2026-10-04)

The build and measure law itself lives in the root `CLAUDE.md`
("The standard test harness"). This file is the list of traps the
harness refuses on its own.

## Traps the harness now makes impossible (stop hand-checking these)

- Wrong build cwd — silently smaller layout, fake speedup: the build entry
  refuses.
- Cold DEM/inset cache, or a config frame diverging from production's
  (warm-vs-cold has moved terrain 12 m): the build entry refuses;
  `--allow-degraded-dem` is the explicit, recorded override.
- A patch emitted with no `.axes.json` sidecar, after which every census
  silently degrades to the context-free frame that overcounts: refused.
- A tile built with an empty `cifp_data_path`, which skips auto_patch
  entirely and still exits 0: `--tile` refuses.
- A lane worktree missing `OSM_data`, or with a COPIED `Elevation_data` (a
  second inset cache that warms on its own): `lane_worktree.sh` builds and
  audits it.
- A build on a PRIVATE data corpus, whose numbers no other lane can be
  compared with: refused; the corpus every data dir resolved to is recorded
  in `frame.json`.
- An implicit download or cache regeneration into the shared repo (the
  KCLT road-feed precedent): refused before the build, naming the artifact
  and the `--refresh-data` scope; and a full before/after snapshot after it
  reports any write that happened anyway, marking the run CONTAMINATED.
  Note `--allow-degraded-dem` does NOT authorise a write — accepting a
  worse measurement and authorising a change to everyone's data are
  different acts.
- Two lanes racing a cache regeneration: per-scope lock in the shared repo,
  refuse-and-report, never a silent block.
- A guard-blocked write inside DEM prep silently DEGRADING the frame
  (the engine's fallback was WARN + rc 0, `dem_inset_provenance` null,
  an 18.5k-vs-36k layout): refused before any patch is written, each
  blocked write named. The engine's `.lock` coordination files have a
  narrowly-scoped allowance (the lock primitive's create/remove only,
  recorded as churn, never contamination); no-op `mkdir`/`makedirs` on
  an existing shared dir is likewise allowed (mutates nothing). Real
  data writes beside either still refuse. `--allow-degraded-dem`
  covers this class too and still authorises NO write.
- A mesh-only tile run (`run_tile_mesh_only.py`) silently rewriting
  inset/bathymetry manifests in the shared repo (measured 2026-08-08,
  five files): it arms the same write guard as `build_airport.py` (one
  implementation, `tools/harness/shared_repo_guard.py`), audits
  before/after, joins the band prefetch before disarming, and fails on
  swallowed refusals; warm-pass manifest rewrites are engine-suppressed
  (byte-identical writes skip).
- A census that omits a law family, a sidecar key, or the ruleset:
  structurally impossible — the twins fail.
- A pytest suite writing the shared data repo (the class that refused a
  concurrent guarded HECA build for 646 s on 2026-08-08): every test now
  runs inside a refuse-mode `SharedRepoWriteGuard` (conftest autouse,
  library-index allowance withdrawn) — a shared-repo write fails ITS OWN
  test with a traceback naming the writer; the DSFTool dump cache and the
  whole `Airport_mod_cache` root resolve through env-overridden lane-local
  roots (`O4_DSF_CACHE_DIR`, `O4_AIRPORT_MOD_CACHE_DIR` — read inside
  `_apply_data_root`/at call time, so module reloads and `set_data_root`
  cannot un-redirect them; the mod cache is a symlink-seeded overlay, so
  warm reads stay warm and rewrites land lane-local); the suite's write-
  allowance register (`_SUITE_MAY_WARM`) is EMPTY; and the session
  detector backstops what no Python-level guard can see (subprocess /
  C-extension writes). Suites are CORPUS-CLEAN (verified 2026-08-08: two
  full-suite arms, before/after snapshots over 2,914 corpus files, zero
  deltas) — running a suite in parallel with guarded builds is lawful.
  Transient `.lock` coordination churn remains allowed and recorded; an
  inset the suite would have to CUT refuses loudly (a privately cut inset
  is a private measurement frame — warm it explicitly via
  `--refresh-data dem`). Timing runs stay exclusive per the standing law.

- A Qt test file swept into a PARALLEL pytest run (`pytest tests/` picks
  up `-n auto` from `pytest.ini`), where it hangs the controller — no
  `--timeout` from a dead worker, no log from a cancelled job — or goes
  red by neighbour load: `tests/conftest.py` refuses in seconds with one
  failing item naming the split CI uses (`-n0 tests/test_qt_*.py`, then
  `--ignore-glob='tests/test_qt_*.py' tests`). `O4_ALLOW_QT_XDIST=1` is
  the explicit override for measuring the hang itself.

- A test reaching the NETWORK wherever no corpus is mounted (every CI
  runner): a live Overpass request waits timeout + 30 s and retries 8×,
  which is the Windows 600 s hang of 2026-09-30 (#122). `tests/conftest.py`
  refuses any non-loopback DNS/connect at the socket with a RuntimeError the
  retry loops cannot wait on, and fails the test at teardown;
  `O4_SUITE_ALLOW_NETWORK=1` is the explicit override. Stub the call.

- An unbounded waiter (`until [ -s FILE ]; do sleep 60; done`) that
  outlives its producer: two ran 21 h and 24 h on 2026-09-13. The bash
  guard refuses a sleeping `while`/`until` loop with no `timeout N`,
  `$SECONDS` deadline or counter; size the bound to the wait.

