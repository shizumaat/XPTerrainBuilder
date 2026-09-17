# Brief pack — lane `insetbounds`

Base: main `5f68c961` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Round 4 lane insetbounds

## The brief

## Lane insetbounds — an airport elevation inset is judged against what THIS airport needs, and says what it was cut from

OWNER RULINGS (2026-09-17c (2), answered 2026-09-17 evening; the session records them at merge):
 1. record the contributing pack NAMES in the inset manifest NOW;
 2. the APP MAY re-cut a STALE inset automatically (as it already re-cuts a missing one);
 3. inset extents go into `frame.json` IF that is useful — the session's reading: the
    quick "does it need a re-cut" test is the inset's OWN recorded bounds (already in
    every manifest, and better, the GeoTIFF's geotransform); `frame.json` is the
    harness's per-build RECORD, not a cache the engine consults, so extents there buy
    COMPARABILITY between arms, not the re-cut test. Add them as ADDITIVE metadata
    only if that is digest-neutral (see 6) — otherwise leave frame.json alone and say so.

THE CENSUS IS DONE (scout, main 2dc9c959; verify a line only when you edit it). In
`Ortho4XP/src/O4_Airport_Elevation_Insets.py` (~11k lines — navigate by grep, NEVER
read it whole):
- The persisted inset's required extent = OSM aerodrome boundary + `airport_elevation_inset_margin_m`
  (default 2000 m): `_airport_bounding_boxes(tile, dico_airports)` :8188-8229 — pure
  arithmetic, no network, no writes; `dico_airports` comes from
  `O4_Vector_Map.build_airports_dico` (:1313) and is ALREADY built at every airport
  build (`auto_patch_v2/airport/dem_production.py:679 _compose`, `:719 _warm_tile`).
  It is NOT apt.dat-derived: a pack toggle cannot move it.
- CONTAINMENT ALREADY EXISTS: `_bounding_box_extends_beyond(required, recorded)` :6940,
  tolerance `INSET_BOUNDING_BOX_TOLERANCE_DEGREES = 1e-6` :6936, fed by
  `_fetched_bounding_box` :6989 (manifest `bounding_box_wgs84`, order west,south,east,north),
  applied per airport per provider at :7229-7237 (`cached_inset_is_stale`; a superset
  raster stays valid :6949; refetch logs "covers a smaller area than the requested
  margin" :7271). Other reuse tests at the same site: `_sidecar_residual_masking_mismatch`
  :6964, `_cached_inset_oversamples` :7017, `_void_inset_record_reason` :7080.
- Tile admission `is_cached(tile)` :8521 compares only `_inset_completion_key` :8385
  (schema, margin_m, providers, level, airports-layer (size, mtime)) — no per-airport box.
- THE MASK is the one pack-sensitive axis: `_collect_inset_building_footprints` :6587,
  `package_object_footprints` :6492 → `_airport_pack_dsf_paths` :6451 (already honours
  the ini; since merge 8d64a786 through `O4_Scenery_Packs`), `mask_building_footprints_in_surface_model`
  :6681; the manifest block `surface_model_building_masking` :6816-6827 records
  `footprint_source` (a PROSE label), `footprint_count`, buffer, masked counts — NO pack names.

THE FOUR GAPS TO CLOSE (none is caused by a pack toggle):
 (i)  `dem_production.frame_state` (:74-103) tests only `os.path.isdir(ins_dir)` (:85);
      it takes `icao` and never uses it for the inset. It cannot see a MISSING or STALE
      inset for this airport inside a present directory. Give it the required box (the
      caller has `dico`) and the containment test, reporting a new problem class:
      `STALE airport elevation inset <path> — it covers <recorded box> but <ICAO> now
      requires <required box> (--refresh-data dem)`.
      PRODUCTION: `_compose` → `_may_warm` → `_warm_tile` (:648-655, :685-728) already
      re-cuts a COLD frame (owner 2026-09-10); a stale inset joins the same problems
      list and is re-cut by the same path (ruling 2) — no new code path.
      HARNESS: `_may_warm` is False for `core_hosted=False` (:690): it must REFUSE by
      name with the scope and never re-cut — add the stale case to
      `tools/harness/build_airport.py` `dem_cache_problems` (:505-545; the cold-insets
      refusal text is at :527-533, its frame-note twin :620-625). `--allow-degraded-dem`
      covers it like the rest and authorises NO write.
 (ii) SILENT COVERAGE SHORTFALL: `inset_coverage_of_airport_mask` :9964 reads the
      GeoTIFF geotransform and returns a fraction; `resolve_airport_smoothing_radius`
      (:10136, :10178-10183, `INSET_COVERAGE_THRESHOLD = 0.8` :9929) only uses it to pick
      a radius and RETURNS SILENTLY below threshold — uncovered airport ground stays on
      the base DEM with no warning. Make it LOUD: one `UI.loud_warning` line per airport
      naming the inset, the covered fraction and that the ground outside is on the base
      source; and let (i) treat "does not contain the required box" as stale so the app
      heals it. Do not change the threshold.
 (iii) THE MANIFEST OVERSTATES THE RASTER: measured over 559 tif/json pairs — median
      |Δ| 5.1e-6°, max 2.45e-4° (~27 m ≈ one 30 m source pixel), 547 pairs over the 1e-6°
      tolerance, in BOTH directions (BGGH's raster is ~12 m short of the box its manifest
      claims). TRUST THE FILE: judge containment against the GeoTIFF's own geotransform
      (the coverage function at :10018-10024 already opens it that way); fall back to the
      manifest only when the raster cannot be opened, and then with a tolerance of one
      source pixel (`native_resolution_m` is in every manifest) floored at the present
      1e-6°. Going forward write BOTH boxes to the manifest: the REQUESTED box and the
      DELIVERED box (from the written raster). 22 existing manifests carry no
      `bounding_box_wgs84`: unjudgeable ⇒ reuse (as `_fetched_bounding_box` :7003-7013
      already does).
 (iv) RECORD THE PACKS (ruling 1): add `footprint_packs` — the SORTED list of pack
      directory names that actually contributed object footprints — inside
      `surface_model_building_masking`. On reuse recompute that list (`_airport_pack_dsf_paths`
      is a directory scan + `os.path.isfile` per pack, :6462 "no file is parsed here")
      and compare SETS: equal ⇒ reuse; different ⇒ stale. A manifest WITHOUT the key
      reads as unknown-and-REUSABLE (the established leave-alone policy, :6971) and is
      stamped lazily the next time it is derived — NO corpus-wide re-cut. Measured
      corpus: 587 manifests; 570 carry no package footprints at all; 17 are
      package-touched (MMOX×2, Doha Intl Air Base, OTBD, OTHH, VHHH, ZGSZ, LGAV, KPHX×2,
      Papago AAF, LEMD, BGGH, SPJC, Base de Aviacion Naval, NZGY, NZQN), none served by a
      currently disabled pack. Never hash footprint geometry (that needs the OBJ8 parse
      the cheap scan exists to avoid).
 6.  frame.json (ruling 3, conditional): `tools/harness/build_airport.py` writes
      `dem_inset_provenance` at :3753 / :2776. If — and only if — adding per baked inset
      `delivered_bounding_box`, `required_bounding_box` and `footprint_packs` is additive
      and does NOT move `v2_law_tables_digest` (:2818) or any frame-identity comparison a
      campaign control depends on, add them. Prove neutrality with a twin; if it is not
      neutral, do not add them and report.

HARD LAW FOR THIS LANE (CLAUDE.md "One shared data repo"): `/Users/noah/XPTerrainBuilderData`
is THE corpus. You WRITE NOTHING there: no re-cut, no restamp, no `--refresh-data`, no
manifest rewrite. Every test builds its own tmp corpus (tests/test_airport_elevation_insets.py
is the pattern; the conftest per-test SharedRepoWriteGuard will fail any test that
writes the real corpus). Your read-only measurement on the real corpus is allowed and
wanted: over the 565 existing rasters, how many would the NEW test (file geotransform
vs today's required box for the airports whose airports-layer is cached) mark stale?
Report the count and the names; if it is more than a handful, STOP and report before
finishing — a corpus that goes stale under a new rule is an owner decision
(`dem-inset-cache-shifts-measurements`: a warm-vs-cold inset has moved terrain 12 m).

Closing: `tools/blast.py` for every edited src file and what it names;
tests/test_airport_elevation_insets.py, tests/test_harness.py, the dem_production twins
under tests/auto_patch_v2/, tests/test_silent_tile_death.py; the standing suite once
(`tools/brief_pack.py` STANDING line), FAILED lines verbatim. No airport build unless a
twin cannot express something — and then ONE `tools/harness/build_airport.py CYXY` with
the `[harness] shared repo UNCHANGED` line quoted.

Rules: worktree from Ortho4XP/ `tools/harness/lane_worktree.sh up insetbounds`; merge main
first. The bash guard refuses engine test commands whose effective cwd is not an Ortho4XP/
with venv and OSM_data (run tests from your worktree's Ortho4XP/ in their own call),
pattern-matches test-runner words inside heredocs (write files with the Write tool) and
refuses `git stash`. Release Xcode only; never quit the owner's app; never run
make_app/make_engine; no push; commit early, one commit per gap; do not merge; no RULINGS
entry. Other lanes this round: betaappimagert (scripts/make_appimage.sh, release.yml),
xplatspread (scripts/check_frozen_tile.py, auto_patch_v2/pipeline/xplat.py) — not your
files. Report branch + sha, the stale-count measurement, each closing check's pass line
with FAILED names verbatim, whether frame.json was touched and why, and everything not done.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

