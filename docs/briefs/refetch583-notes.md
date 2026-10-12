# refetch583 — lane notes (issue #583)

## Step 1 — attribution (read + app log, 2026-10-12)

- WHY a re-fetch was pending at all: KGRF / KTCM sidecars (shared corpus,
  read only) carry `delivered_rung 0` with airport cover 0.00 / 0.54
  (< 0.80), so `ladder_recheck` re-asks the same-resolution rungs (#153).
  Rung 3 `USGSLPC` is `unavailable` by CAP (54 tiles / 26.1 GB vs 40 /
  3.0 GB) and records `listing_ids: None`, so `_stored_rung_listing`
  answers "cannot say" and EVERY id discovery lists is new: the re-check
  is `new-listing` on every build, forever. RULINGS 2026-09-30bv REPORTED
  (2) named this class and left it undecided. The owner's app log
  (`~/Library/Logs/XPTerrainBuilder/engine-stderr.log` lines 139/148 and
  712/714) shows the same two airports re-fetched by two consecutive app
  builds of +47-123 (hundreds of MB each time).
- WHY the pre-flight was silent: `build_airport.py main` passes
  `None if args.tile else args.icao` to `this_airports_inset_problem`,
  which returns None with no icao ("a --tile run judges the whole tile");
  nothing judges the other airports of the tile. Only the index negatives
  (`unverified_inset_negatives`) are tile-wide.
- WHY the guard let the writes through: the strategies cut their scratch
  beside the destination (`<inset>.tif.refetch.rungN`, `.tnmN.zip`,
  `.prefetchN.tif`, `.surroundN`, …) and GDAL writes them in C; the guard
  patches Python `open` / `os.*` only. The Python `os.remove` of each
  scratch file was then the first call it saw.
  Count check against the lane's 74 files: KGRF 10 = `.refetch` +
  `.refetch.rung2` + 8 USGSOPR sources; KTCM 64 = 2 + 62 sources. The six
  blocked removes are three per airport (strategy `finally`, ladder
  `finally`, fetch-loop cleanup).
- REPRODUCED on tmp dirs only (scratchpad `refetch583/repro.py`, a fake
  provider whose scratch is written by GDAL and removed in Python, a
  `SharedRepoWriteGuard` over a tmp corpus). Base tree (`git archive` of
  012ac5899): `fetch_calls=1`, three `KASE_fakescr.tif.refetch*` files in
  the guarded cache, `blocked=[os.remove, os.remove]`. This branch:
  `fetch_calls=0`, nothing written, `blocked=[spawn the airport inset
  fetch writing KASE_fakescr.tif, open for writing index.json]`.

## Step 2 — engine (commit 871d6cd48)

- `src/elevation_access/fetch_scratch.py` (new): every inset fetch works
  in a private folder under `<Tmp_dir>/inset_fetch` (`O4_INSET_SCRATCH_DIR`
  overrides); only the finished raster is moved onto the cache
  (`land`: rename, or copy + rename across volumes). The fetch loop
  declares the cache path through `O4_External_Writes` before a byte is
  asked for. `sweep_stale` removes scratch folders and — where the run
  may write the cache — `<raster>.tif.<more>` siblings older than 24 h
  (not `.aux.xml`, not `.lock`).
- A failed re-fetch or a failed `refresh=True` fetch now leaves the cached
  raster alone (it was fetched over and then deleted).
- CAP-DECLINED RUNG: `ProviderUnavailable.declined_by_cap`
  (`cap_exceeded_unavailable`, LAS `_check_caps`); the ladder records the
  rung's `listing_ids` and `declined_under` (definition digest + engine
  version + capabilities); `_stored_rung_listing` honours the listing only
  under the same signature. Every other `unavailable` is still asked on
  every build (13b). DEVIATION for the spec author: RULINGS 2026-09-30bv
  reported (2) left this undecided.

## Step 3 — harness (commit 7c5db4435)

- `tools/harness/inset_preflight.py` (new) + `build_airport.
  tile_inset_refetch_rows`: a `--tile` pre-flight asks the engine's
  per-airport verdict and ladder re-check for every selected aerodrome.
- `refresh_tile_dem` → `_complete_pending_insets`: the stale negatives
  (any run) and the tile-wide pending re-fetches (a `--tile` run) go
  through `warm_airport_insets(..., refresh=False)`; a surviving row
  refuses.
- Guard: `OWN_TEMPORARY_OPS` — `os.remove` / `os.unlink` of a
  `*.tmp-<own pid>*` file created after the guard armed is allowed and
  recorded in `blocked` (`UNSEEN_WRITE_VIA`), so the run still fails.

## Step 4 — closing reads (2026-10-12)

- `build_airport.py KBFI --tile 47 -123 --no-ledger` on this branch:
  rc 1 at the PRE-FLIGHT in 22 s, nothing built, nothing written
  (shared inset dir still 20 entries). It names THREE pending re-fetches:
  KGRF [ladder], KTCM [ladder] and KPWT [stale] (cut for
  …47.452948… , now requires …47.452928…: a re-cut nobody had seen).
  Log: scratchpad `refetch583/kbfi_tile_preflight.log`.
- Real-provider witness, lane-local (`fetch_airport_elevation_insets.py
  --witness KGRF --elevation-data-dir <scratchpad>`), twice: run 1
  fetched the ladder (USGSLPC declined by cap, 54 tiles / 26.1 GB) and
  left only `KGRF_usgs3dep.tif/.json` + `index.json` in the inset dir;
  the sidecar's rung 3 carries 54 `listing_ids` and `declined_under`.
  Run 2: zero fetches, `recheck.result = unchanged` (rungs 2, 3 asked).
  On the base tree that re-check is `new-listing` on every build.

## App side

- An interrupted app build DID leave litter and nothing removed it: four
  `*_copernicusglo30.tif.refetch` files of 2026-09-18 are still in
  `Elevation_data/+10-070/N17W063_airport_insets/` of the shared corpus
  (TFFJ, TNCE, TKPN, TKPK). The next build removed a `.refetch` only if
  it re-fetched that same inset. Now: no scratch is cut beside the cache,
  and each inset pass sweeps what older engines left (24 h bound).
- The app re-downloaded KGRF and KTCM on every build of +47-123
  (engine-stderr.log lines 139/148 and 712/714). After one more
  re-fetch (which records the listing) the re-check answers `unchanged`.

## Step 5 — master correction (PR #594 red), 2026-10-12

- CI red: `test_a_schema_stale_road_layer_refuses_and_names_osm_layers`
  reached the network. Cause: the tile-wide check trusted
  `state["airports_layer"]` (that test fakes it True) and read a layer
  that is not on disk — `OSM_queries_to_OSM_layer` then QUERIES overpass.
  The ladder discovery query in the same path was the second network
  reach. Both are gone from the pre-flight:
  - `inset_preflight.airports_layer_is_cached` asks the file itself;
  - the ladder is judged from the sidecar alone
    (`INSETS.ladder_recheck_owed`, new; `_ladder_recheck_rungs` is the one
    rung selection it shares with `ladder_recheck`): a re-asked rung with
    no recorded listing (never answered; `unavailable` that is no cap; a
    cap-declined rung whose definition/engine/capabilities moved) owes a
    re-check, unless the sidecar's `recheck` stamp says `unchanged`.
  - The asking (`_ladder_recheck_problem`) runs only inside
    `--refresh-data dem` (`_complete_pending_insets`).
- NOT changed: the AIRPORT build's own pre-flight re-check
  (`this_airports_inset_problem` → `_ladder_recheck_problem`, RULINGS
  2026-09-30aw (2), `frame.json: ladder_recheck`) still asks the
  providers' indexes for the one named airport. It is ratified spec
  behaviour with its own twins; reported for a ruling.
- `dsf_write._sweep_stale_partials` (now on main) is NOT folded with
  `fetch_scratch.sweep_stale`: one matches `<dump>.*.partial` files of one
  dump, the other whole folders and `<raster>.tif.<more>` siblings, and a
  shared helper would be a third module for one `mtime` comparison.
