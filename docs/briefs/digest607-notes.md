# digest607 — notes (issue #607)

## Mechanism
- `provenance.config_digest()` hashed every set `O4_` variable except seven
  names. `O4_PARENT_PROCESS_ID` and `O4_PARALLEL_BUILD_SIBLINGS` were hashed.
- Gate twin (`test_run_identity_is_not_a_build_input`, 7 cases) was red on
  main at 31fd980e7: a patch stamped under one value read `o4_cfg changed`
  under another.
- Owner's case: `engine-stderr.1.log` ends 16:38:37 with
  `[worker 0..4] Engine process exiting (standard input closed)` — the app's
  engine ended after the first build. The 17:14 build ran on a NEW engine
  process. A tile worker's `O4_PARENT_PROCESS_ID` is the orchestrator
  engine's pid (`parallel.py` spawn), so it differed. The sibling value is
  the configured slot count (`session.py`: the run gets the full slot count,
  not the batch size), so it did not differ unless the setting was changed.
  The texture-mode switch was not the cause.

## Reason line
- `driver.generate_auto_patches` sets `UI.verbosity = config.LOG_VERBOSITY`
  (0) for the airport loop. `_rebuild_reason` was `vprint(1)`; the reuse line
  is `lvprint(0)`. The reason was never printable in a tile build. The old
  twin called the gate directly with verbosity 1.

## Other stamps (read, no leak of this class found)
- `o4_solve_cfg`: `road_grade_limit`, `lane_width` off the tile.
- `o4_dem`: DEM source string, identities of its files, 13 tile elevation
  settings, base-fallback records, app base elevation source; inset
  identities for the airport.
- `o4_code` / partition-cache code digest: source bytes of listed modules.
- partition-cache key: pack file stamps, law-table digest, ruleset key,
  resolved-placement digest, bridge ways. No environment, no pid.
- `o4_engine` version; `o4_ap_engine` constant; `o4_cifp`, `o4_dsf`,
  `o4_pack`: file identities and scenery_packs.ini state.

## Not done
- `Ortho4XP/tools` outside `harness`, repo `tools/`, `.claude/hooks`: their
  `O4_` variables (`O4_CROSSING_ZONE_DUMP`, `O4_DATA_OVERLAY`,
  `O4_PACK_STAGE_TREE`, `O4_ROUND_TAG`, `O4_SUPPRESS_UI`,
  `O4_TRANSVERSE_HYPER`, `O4_STASH_OK`) are outside the twin's walk.
- Mesh-stage, cache-toggle and dump variables stay digested (safe side).
