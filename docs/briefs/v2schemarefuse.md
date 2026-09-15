# Brief pack — lane `v2schemarefuse`

Base: main `9c313551` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

A schema-stale road layer is a REFRESH, never a build side effect — refuse before the build

## The brief

# THE DEFECT — a schema-stale cached road layer is REWRITTEN INSIDE A GUARDED BUILD (the KCLT 2026-08-05 precedent's shape)

Lane `v2roadtags` (RULINGS 15r, d4729dfc) bumped `O4_Vector_Map.ROAD_CACHE_TAG_SCHEMA` "2026-07-16" → "2026-09-15".
Its brief asked "verify that the harness names the `osm_layers` scope for a schema-stale road feed and does NOT
download inside a build"; the lane answered that a stale-schema road cache inside a harness build is "a loud guard
refusal" — WRONG. The first guarded build after the bump (the concurrent session's lane `v2lemdstruct2`, LEMD,
2026-09-15 09:03) REWROTE `/Users/noah/XPTerrainBuilderData/OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2`
(2,197,226 → 2,199,670 bytes) and the harness marked the run CONTAMINATED (scope osm_layers) — the guard REPORTED
after the fact instead of REFUSING before the build (RULINGS 15u, the peer session's record; read it). The engine's
recycle path (`O4_Vector_Map.py` ~:765–830, `_cached_osm_schema_matches`, the per-layer re-download when the schema
tag is stale) writes through the engine's own file path, which the write guard classifies as churn/report, not refuse.

# THE LAW (owner ruling e9daef5, CLAUDE.md "Traps the harness now makes impossible"): a download or cache
# regeneration into the shared repo is an EXPLICIT, locked, hash-stamped `--refresh-data` event, NEVER a build side
# effect; the harness REFUSES BEFORE the build, naming the artifact and the scope.

# THE FIX (one mechanism, two halves at their single derivation sites)
1. `tools/harness/build_airport.py::missing_shared_artifacts` (~:579): for every cached road layer the build will
   read (`big_roads`, `airport_small_roads`/`small_roads` per tile, the merged airport_small_roads if it carries a
   schema — see the chip on its missing gate), compare its stored `o4_tag_schema` with the engine's
   `ROAD_CACHE_TAG_SCHEMA` (import the engine's predicate `_cached_osm_schema_matches`, never copy it) and name a
   stale layer as an `("osm_layers", <path>, "cached under schema X, engine expects Y — a refresh, not a build side
   effect")` triple so the build REFUSES up front with `--refresh-data osm_layers`. Same for a tile build (`--tile`).
2. `tools/harness/shared_repo_guard.py`: a write to `OSM_data/**/*_roads.osm.bz2` (any road layer) inside a build
   that did not authorise `osm_layers` is a REFUSAL (raise inside the engine's write), not a reported contamination —
   check why the engine's path was classified as churn (the `.lock`-family allowance? the library-index allowance? a
   bz2 temp-then-rename that the guard sees as a new file?) and close exactly that gap. If the engine writes via a
   C-extension/subprocess path the Python guard cannot see, say so and make half 1 the sole defence.
3. Twins in `tests/test_harness.py` (the harness twin file — `LAW_FAMILIES`-style twins live there) or the fetch-cache
   tests: a tmp data-root with a road layer stamped with the OLD schema → `missing_shared_artifacts` names it under
   `osm_layers`; with the CURRENT schema → not named; the guard refuses a road-layer write when the scope is not
   authorised and allows it when it is.

# BARS
- No builds against the shared repo, no downloads, no `--refresh-data`; tmp fixtures only. Do not edit
  `O4_Vector_Map.py`'s schema constants or tag lists. Files under the 1,000-line guideline (build_airport.py is large —
  add the check as a function beside `missing_shared_artifacts`, not inline).
- Cross-reference RULINGS 15r (the bump) and 15u (the contamination) in your commit message.

# CLOSING
The diff, the twins, `venv/bin/python -m pytest tests/test_harness.py tests/test_road_tag_schema.py
tests/test_fetch_cache_predicates.py tests/auto_patch_v2 -q` by FAILED lines, the commit sha on `claude/v2schemarefuse`.
The session merges.

## Files

Yours: `Ortho4XP/tools/harness/build_airport.py`, `Ortho4XP/tools/harness/shared_repo_guard.py`, `Ortho4XP/tests/test_harness.py`
Other lanes' (do not touch): `Ortho4XP/src/O4_Vector_Map.py`

## RULINGS

## 2026-09-15r v2roadtags MERGED (d4729dfc): the road feed keeps `layer` / `cutting` / `covered` / `embankment` (§45 (9)); schema `2026-09-15`

Lane `v2roadtags` (f6bd825d): `O4_Vector_Map.ROADS_TAGS_OF_INTEREST` gains
the four depth witnesses, `ROAD_CACHE_TAG_SCHEMA` "2026-07-16" → "2026-09-15";
node tags untouched. Reader census: every road-way tag access in `src/` and
`tools/` is name-addressed; no four-key or positional assumption anywhere.
Twins `tests/test_road_tag_schema.py` (7): the tags, the schema, an
old-schema cache stops matching, a fixture way `cutting=yes layer=-1
covered=no embankment=yes` survives production's own target-tags derivation
(`maxspeed` still dropped). Suite ON MAIN after the merge: `1613 passed, 1
skipped` (schema + fetch-cache + campaign), 0 failed. A harness build never
re-downloads on a stale schema (the shared-repo guard refuses under
`osm_roadfeed`/`osm_layers`); the owner's app builds re-download a
schema-stale TILE road cache on their next run — the intent. TWO
CONSEQUENCES NAMED: (1) `layer` goes live on the tile-cache path —
`bridges._has_tunnel_tag_evidence`, `osm_crossing_level`,
`pavement_classification._is_below_grade` already read it and now see it
(the correct behaviour change). (2) The PER-AIRPORT road feed has its OWN
whitelist `auto_patch/osm_load._ROAD_FEED_WAY_TAGS` (hashes itself into the
sidecar fingerprint): it carries `layer` but NOT `cutting`/`covered`/
`embankment`; widening it re-cuts every airport's feed — a shared-repo
write under scope `osm_roadfeed`, the OWNER's act (question below). DEFECT
NAMED, not fixed (chip): the auto-mode merged `airport_small_roads` cache
has NO schema gate (`O4_Vector_Map.py` ~:768 recycles on `isfile` alone,
`write_to_file` stamps no `o4_tag_schema`, `OSM_query_to_OSM_layer` takes no
`cache_schema`) — a pre-existing cache keeps serving four-key ways silently.

## 2026-09-15u v2lemdstruct2 r1 MERGED (287f9b5b): item 5's mouth is 5.07 m deep (an EQUALITY ROW WAS NEVER HARD — `_law_sides` bucketed lo == hi Linears as `eqs` at law weight), item 7's trench is beyond the taxiway strip; the closing LEMD build CONTAMINATED the shared repo (v2roadtags' schema bump rewrote `+40-004_big_roads.osm.bz2`) — owner: `--refresh-data osm_layers`

Lane @ 287f9b5b (base da8e5d7f, main merged twice); suite 1,587 passed
twice, 0 FAILED; fresh registered LEMD capture (20,608 vertices) +
matched replay arms; ONE LEMD build rc 0, 551.8 s, optimal. Item 5:
floor 599.25 → 597.09 under rim 602.16 = 5.07 m (bar 5.10 ± 0.05). ROOT
CAUSE, general: the planar record was right (`mouth_z` 597.075) but
`solve/rows._law_sides` routes a `lo == hi` Linear into the `eqs`
bucket, which `solve/design` adds at the LAW WEIGHT — only the one-sided
bucket passes through `hard_rulings`; the row sat 2.16 m out while the
solve reported 0/103,840 hard rows violated; registering the head alone
was byte-identical (the proof). Fix: two one-sided rows + the head.
Price: +106 hard rows; `within_shape` 406 → 469 (the plan-chord
misreading, §34 (13) (1)); `tunnel_mouth_canonical` 32 → 28. Item 5
road: OSM −5944 identified, NOT admitted (08-30l census first — r2);
the pull REFUTED as stated (ground ≥ DEM); the DEM's own 611 × 88.7 m
plateau between the rims is what the owner sees. Hole ring unchanged
(13 rings > 10,000 m²). Item 7: mouth 12.77/15.46 → 31.06/33.43 m from
the node (code-E strip 19 m), zones intact, clip 772 → 3,316 m², every
TAXI `ramp_in_strip` row gone; residual 8 rows against runway 14R/32L's
75 m strip (`strip_transverse [runway|tunnel_ramp]` 5.59 → 13.87 m) →
§34 (13) (2); crossfall at pav157 = junction|runway pairs 4.957 % (no
transverse row) → 4.296 / 2.479 % → §34 (13) (3). `ramp_in_strip` in
LAW_FAMILIES + families.toml (keepout), 6 twins; holes applied, the
pavement solid subtracted (the ring-blind form read 52 false rows).
Census: ADJUDICATED 1,341 → 1,404 (+4.7 %); `road_cross_section` 8 → 9
the one > 5 % family (groundside, one row). CONTAMINATION: the harness
flagged the closing build — `OSM_data/+40-010/+40-004/+40-004_big_roads
.osm.bz2` rewritten 2,197,226 → 2,199,670 bytes (09:03), scope
`osm_layers`; the lane touched no road code — v2roadtags (d4729dfc,
peer session) bumped `ROAD_CACHE_TAG_SCHEMA`, so the FIRST build after
that merge rewrites every cached road layer: the KCLT 2026-08-05
precedent's shape. The guard reported, it did not refuse (the engine
write path). OWNER'S ACT: `build_airport.py LEMD --refresh-data
osm_layers` (and KCLT, and any airport built before the next
measurement) so the rewrite is a recorded, hash-stamped event; until
then LEMD/KCLT measurements are on a mixed corpus. r2 resumed: §34 (13)
(1)–(4).

## Tool: shared_repo_guard

| `Ortho4XP/tools/harness/shared_repo_guard.py` | Not a CLI. THE single implementation of the shared-repo write law (owner ruling e9daef5): the write guard, the lock-file and library-index churn allowances, the snapshot/diff audit, the swallowed-refusal detector, and the refresh scopes/locks/ledger. `build_airport.py` re-exports it; `run_tile_mesh_only.py` arms it. A second copy of any of this is a defect (the census-wrapper precedent). It also owns `mirror_tree_as_overlay` (was `mirror_tree_as_symlinks`, kept as a deprecated alias for `repro_cut.py`), the read-through overlay's pure core (moved from `tests/conftest.py` 2026-08-11; conftest delegates to it). **Both halves of the OVERLAY WRITE-THROUGH law landed 2026-08-12** after the hole was measured three times in one session (two SQ2 classify runs, the r18 KMCI overlay, the r20 parallel arms — seven OTHH sidecars rewritten): (1) the overlay seeds COPY-ON-WRITE (`clonefile(2)`, falling back to a real copy — never a symlink, never a hardlink), because the engine's sidecar writers (`dsf_reader` ×3, `object_terrain_assembly` ×2, `post_mesh`) open the cache path as `open(path, "wb")`, a TRUNCATE IN PLACE that followed the seeded symlink and emptied the shared file; and (2) `_violation` judges the RESOLVED path, so a write whose open path is lane-local but whose target is in the corpus refuses — before this the guard compared the lane-local string and reported `blocked: []`, blind by construction. Measured seeding cost on the real corpus: 1,131 files / 22 GB apparent in 0.10 s for ~420 KB of real disk. |

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

