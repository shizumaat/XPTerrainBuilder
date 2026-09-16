# Brief pack — lane `v2usgsbox`

Base: main `97430203` · generated 2026-09-16 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

USGS3DEP's coverage box is US-only (owner 16c)

## The brief

# OWNER DECISION (2026-09-16, relayed through the peer session's interview; recorded RULINGS 16c): fix USGS3DEP's declared COVERAGE BOX so non-US airports are out-of-box and never re-asked

`Providers/Elevation/USGS3DEP.elv:26  coverage_bbox=-180.0,15.0,-64.0,72.0` — that box covers all of Canada,
Mexico, Central America and the Caribbean. USGS 3DEP is US-only (CONUS, Alaska, Hawaii, Puerto Rico / USVI,
Guam / CNMI / American Samoa). CYXY (Whitehorse, 60.71 −135.07) therefore carries two "version-stale USGS3DEP
no-coverage" records that 15ay's once-per-version door re-asks and the harness refuses on (`--refresh-only dem`
on 1.50.1788: "nothing to derive … 2 artifact(s) STILL not current"). 15ay's predicate already treats an
OUT-OF-BOX negative as never stale — so the fix is the box, not the door.

# THE MECHANISM
1. Read how `coverage_bbox` is parsed and used (`O4_Airport_Elevation_Insets.py`: `_coverage_bbox_intersects`,
   `negative_is_version_stale`, `negative_is_unverified`; the `.elv` reader). If the format is ONE box, extend it to a
   LIST of boxes (`coverage_bbox=` repeated, or a `;`-separated list — pick the one the reader accepts most
   naturally and say why) so a provider can declare disjoint regions; every existing single-box provider keeps
   working unchanged (twin).
2. Declare USGS3DEP's boxes: CONUS (−125.0,24.0,−66.0,49.5), Alaska (−180.0,51.0,−129.0,71.5 and 172.0,51.0,180.0,
   53.5 for the Aleutians west of the antimeridian if the reader can hold a box crossing it — else name it as
   uncovered), Hawaii (−161.0,18.5,−154.5,22.5), Puerto Rico + USVI (−68.0,17.5,−64.5,18.6), Guam/CNMI (144.5,13.2,
   146.2,20.6), American Samoa (−171.2,−14.5,−169.4,−13.8). Every box cited to a USGS/3DEP coverage statement in
   the .elv comment.
3. Measure (read-only) which cached inset indexes in the shared repo carry a USGS3DEP negative for an airport
   that is now OUT-OF-BOX: at least CYXY's two on N60W136; sweep `Elevation_data/**/index.json` and report the
   count per tile — those records become "never re-asked" by 15ay's predicate WITHOUT any edit to the corpus
   (verify with the predicate on CYXY's real record). Also report which campaign tiles are INSIDE the new boxes
   (KCLT, KDFW, KPHX, KMCI …) and which are not (CYXY, OTHH, VHHH, VMMC, HECA, LEMD, SPJC, LGAV).
4. The frozen engine: `Ortho4XP_Data/Providers/Elevation/USGS3DEP.elv` ships from `Providers/` — confirm the
   spec/collection copies the file (it must; a stale copy under `dist/` is not yours to edit).
5. Twins: the multi-box parser; CYXY out-of-box → `negative_is_version_stale` False and `_coverage_bbox_intersects`
   False; KDFW in-box → unchanged; a single-box provider unchanged.

# BARS
No builds, no fetches, no writes to the shared repo (the CYXY index is read only; the owner's next build or
refresh judges it). Suite from Ortho4XP/: `venv/bin/python -m pytest tests/test_airport_elevation_insets.py
tests/test_base_elevation_providers.py tests/auto_patch_v2 tests/test_harness.py -q` by FAILED lines. Commit on
`claude/v2usgsbox`; the session merges.

## Files

Yours: `Ortho4XP/Providers/Elevation/USGS3DEP.elv`, `Ortho4XP/src/O4_Airport_Elevation_Insets.py`, `Ortho4XP/tests/test_airport_elevation_insets.py`

## RULINGS

## 2026-09-16c OWNER (relayed by the peer session's interview): CYXY's two version-stale USGS3DEP negatives are fixed by the PROVIDER'S COVERAGE BOX, not by re-asking — USGS 3DEP is US-only; lane `v2usgsbox`

`Providers/Elevation/USGS3DEP.elv` declares `coverage_bbox=-180.0,15.0,
-64.0,72.0`, which reaches all of Canada, Mexico, Central America and
the Caribbean; CYXY (Whitehorse) therefore carries two USGS3DEP
`no-coverage` records that 15ay's once-per-version door re-asks and the
harness refuses on (`--refresh-only dem` on 1.50.1788: "2 artifact(s)
STILL not current"). Owner: fix the box. 15ay's predicate already
treats an out-of-box negative as never stale, so a correct declaration
(CONUS, Alaska, Hawaii, PR/USVI, Guam/CNMI, American Samoa — a LIST of
boxes if the `.elv` reader holds one) makes CYXY's records inert with
no corpus edit. The lane also censuses every cached index for
now-out-of-box USGS3DEP negatives and names the campaign tiles inside
the new boxes. KCLT needed nothing (rc 0); the KPHX item is closed by
15au.

## 2026-09-15ay v2insetreprobe MERGED (5b4ea55e): a capability-free provider's `no-coverage` is re-probed ONCE PER ENGINE VERSION (owner 15aq (4)); 19 stale Phoenix negatives named; the harness names them under `dem` and never fetches

Lane `v2insetreprobe` (2811624a). One predicate,
`negative_is_version_stale(record, code, definition, bbox)`: true only
for a `no-coverage` of a provider with NO required capability, whose
declared coverage box reaches the airport, recorded under a version ≠
the running one (an out-of-box negative is re-derived from the boxes
and never re-asked, so a release churns no index). `run_capability_
record` now stamps capability-free providers too (`{"engine": v,
"capabilities": []}` in the index's existing `capabilities` JSON — no
new file, no new key; the unstampable record was WHY the negative was
permanent). The provider loop's third door beside `refresh` and
`unverified` logs both versions and re-stamps whatever the answer;
13b's door untouched; `is_cached` is False for a tile carrying one;
`engine_version()` public. Harness: `unverified_inset_negatives` names
a version-stale capability-free negative under `dem` with both
versions and `--refresh-data dem`, never fetching (imported predicate).
Measured read-only at engine 1.50.1788: +33-113 16, +33-112 3 (the 19 of
15q's 20 not already cleared by 15au's KPHX refresh). Twins (a)–(f);
`test_legacy_caches_without_recorded_box_are_reused` re-stamped (its
unstamped negative was re-asked once — the law working). Merge conflict
in `tests/test_harness.py` (both sessions append twins; kept both).
Suite ON MAIN: `1877 passed, 1 skipped, 1 xpassed`, 0 failed. NOTED,
not mine: the SUITE's session detector has no external-candidate
downgrade (unlike the build audit's `BuildInputScope`), so a concurrent
authorised refresh lands as teardown ERRORs in any suite running at the
time (18 today, twice) — chip-worthy.

## 2026-09-15q v2insetneg MERGED (5202d381): a TNM HTTP 200 error envelope was read as "zero products" and written as a DURABLE no-coverage — 20 false negatives on the two KPHX tiles

Attributed (lane `v2insetneg`, 755d5cd2), not guessed: the writer is
`ensure_airport_insets` (`O4_Airport_Elevation_Insets.py` ~:7229, the
`provenance is None and not fetch_raised` branch); the cause is
`TnmCloudOptimizedGeoTiffStrategy.discover` (~:1419): `items =
payload.get("items") or []` on a 2xx body that was NOT a product listing
(a gateway error envelope during the 504 outage) → `return None` with no
log line → recorded `no-coverage`. Counts match per tile: +33-113 33
attempts / 16 transient / 17 `no-coverage`; +33-112 15 / 12 / 3; zero
`USGS3DEP: ok` anywhere (TNM degraded for the whole pass). Ruled out:
the warp path (`gdal.UseExceptions()` on), `_coverage_bbox_intersects`,
`ProviderUnavailable`, the probe/`checked` stamps. The 13b re-probe door
(`unverified_capability_negatives`) cannot reach it — USGS3DEP declares
no required capability. FIX: `discovery_listing_items(...)` — only a
well-formed, complete zero-products answer is durable; a non-mapping
body, a body without an `items` LIST, an `error`/`errors`/`fault`/
`exception` key, or `total > 0` with no items raises
`TransientFetchError` (nothing recorded, retried next run); a listing
whose items carry no download URL likewise transient. Twins on fixture
bytes (five response classes, two controls, an index-level twin through
`ensure_airport_insets(33, -113, {"KPHX": …})`). Suite ON MAIN after the
merge: `1768 passed, 1 skipped` (inset file + campaign suite), 0 failed.
NOT retro-scrubbed: the 20 stale `no-coverage` records on
`Elevation_data/+30-120/N33W113_airport_insets/index.json` and
`N33W112_…` stay until the owner's `--refresh-data dem --warm-insets`
(KPHX only) or his deletion of the two index files (all 20 airports).
OPEN (owner intent): should an existing `no-coverage` for a CAPABILITY-
FREE provider ever be re-probed (13b's door covers capability-gated
providers only)? Today such a record is permanent. Chip-worthy: the
transient WARN cannot name its airport (the strategy is handed no ICAO).

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

