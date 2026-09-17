# Brief pack — lane `aptstamp`

Base: main `2ce998f4` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

freshness stamp watches the apt.dat v2 read

## The brief

## Lane aptstamp — the freshness stamp must watch the apt.dat v2 READ

FINDING (scout 2026-09-17, inferred from code, NOT yet measured): auto_patch has
two apt.dat selectors and the freshness stamp watches the wrong one.

- GATE: `Ortho4XP/src/auto_patch/driver.py` ~:1456-1474 (per-airport loop of
  `generate_auto_patches`) selects with v1 policy
  `_pick_best_apt_dat_against_osm` (`src/auto_patch/osm_load.py:596-668`):
  prefers a custom pack carrying a 1201/1202 taxi-routing network, otherwise
  FALLS BACK to Global Airports (the MKStudios LPPT case in its docstring).
  Stored as `task["apt_dat_path"]` (driver.py ~:1576).
- BUILD: `src/auto_patch/engine_v2.py:270-278` builds `Inputs(...)` WITHOUT
  `apt_dat_path`; v2 re-selects with `auto_patch_v2/airport/apt_dat.find_apt_dat`
  (apt_dat.py:270-304): first custom pack with row-110 pavement, never the Global
  fallback for routing (§44 policy, apt_dat.py:277-282).
- STAMP: `engine_v2._stamp_header(task)` (:142-170) stamps
  `task["apt_dat_path"]` + its mtime + `_dsf_identities_now(apt, tiles_key)`;
  its docstring (:153-157) acknowledges the split. Where the policies disagree
  the gate (`layout.read_patch_source` → `driver._auto_patch_is_current`)
  watches a file the build did not read: editing the pack v2 DID read does not
  invalidate the patch; a stale patch is reused.
- NOTE (PM, verified): `_stamp_header(task)` is evaluated BEFORE v2 runs
  (`Config(header_extra=_stamp_header(task))`, engine_v2.py ~:282), so "v2's
  report carries it" is not available at that moment. Either resolve the path
  v2 will read up front through v2's OWN selector (one call, the same function
  the build calls — not a re-implementation), or stamp after the load. Choose
  the form that keeps ONE selector call site of truth; say which and why.
  Mind §44: under a borrow v2 reads TWO apt.dat blocks (the pack's and Global
  Airports'). Decide from the code what the stamp must watch in that case and
  REPORT it (if the header can only carry one path, say what is unwatched —
  do not silently leave the borrowed file unwatched without reporting).
- The gate side must then COMPARE against the same datum: read
  `_auto_patch_is_current` — if it re-derives the path with
  `_pick_best_apt_dat_against_osm` and compares to the stamped path, a stamp
  of v2's path makes every disagreeing airport permanently stale (rebuilt every
  run). Fix the datum at ONE site so gate and stamp agree; v1-engine patches
  must keep their current behaviour.
- ENCODING asymmetry: `auto_patch_v2/airport/apt_dat.py:216` opens apt.dat with
  the locale default encoding; `apt_dat_reader.py:837` pins utf-8. A frozen app
  with no LANG could differ. Pin utf-8 in apt_dat.py (match the reader's
  `errors=` handling).

### DO, in order
1. MEASURE FIRST (mechanism before fix). Find installed airports where the two
   selectors DISAGREE: a READ-ONLY script over the owner's X-Plane install
   (root from the engine tree's `Ortho4XP.cfg` `custom_scenery_dir`), calling
   BOTH selectors per CIFP ICAO on one or two tiles (pick tiles with custom
   packs installed — e.g. the LEMD / LGAV / LPPT tiles if present). Consult
   `tools/INDEX.md` via `tools/docq.py index <name>` BEFORE writing any tool;
   extend a near-fit; a new tool lands with its INDEX row + a twin in the same
   commit. Report: airports examined, how many disagree, which, and both paths
   for each. If ZERO disagree on the install, say so plainly and widen to all
   tiles with a custom pack before concluding; the fix still lands (the twin
   is the proof), but the report must state the measured population.
   No writes to the shared data repo or the X-Plane install.
2. FIX at ONE site: the stamp records the apt.dat v2 actually read. Do NOT pass
   `apt_dat_path` into `Inputs` (that bypasses pack discovery and the §44
   borrow). Pin utf-8 in apt_dat.py.
3. TWIN: two fake packs where the policies disagree (e.g. pack A: row-110
   pavement, no 1201/1202; v1 falls back to a fake Global Airports, v2 reads
   A). Editing the pack v2 read invalidates the patch; editing the other does
   NOT. Plus an encoding twin if cheap (a non-ASCII byte in apt.dat under
   `LANG=C` / `PYTHONUTF8=0`).
4. CLOSING: `tests/test_auto_patch_freshness.py`,
   `tests/test_auto_patch_engine_dispatch.py`, whatever
   `Ortho4XP/venv/bin/python tools/blast.py <file>` names for every file you
   touch, then the standing suite ONCE — quote every `FAILED` line verbatim
   (never `tail -1`). No airport build is required for this lane (no geometry
   changes); NO five-airport sweep.
5. RULINGS: do NOT append to RULINGS.md yourself — the PM appends at merge
   time (keys collide with the concurrent peer session). Put the DRAFT entry
   text in your final report.

### Worktree
`cd /Users/noah/XPTerrainBuilder/Ortho4XP && tools/harness/lane_worktree.sh up aptstamp claude/unruffled-poitras-3c6a27`
then work ONLY in that worktree; commit on its branch by explicit path (never
`git add -A`); do NOT merge to main — report branch + sha. A peer session
merges on main concurrently: never run git ops in the main tree.

### OPEN OWNER QUESTION (surface, do not decide, do not implement)
driver.py ~:1471-1473's skip line says "no enabled scenery pack defines it",
but neither selector reads `scenery_packs.ini` (only
`driver._scenery_pack_state`, ~:367, for freshness). A pack DISABLED in the ini
still supplies the apt.dat to both the gate and v2. While measuring (1), ALSO
count: how many selected packs (either selector) are `SCENERY_PACK_DISABLED` in
the install's ini — a number for the owner, nothing more.

## Bars

- Measurement table reported BEFORE the fix commit (airports examined / disagree / which / both paths; disabled-pack count).
- Twin: edit v2-read pack → patch NOT current; edit the other pack → patch current. Red before the fix, green after (show both).
- Agreeing airports: stamp bytes unchanged vs base (no mass invalidation of owners' existing patches) — state how verified. If the fix DOES invalidate existing patches for disagreeing airports only, say so; that is expected.
- `test_auto_patch_freshness.py`, `test_auto_patch_engine_dispatch.py`, blast-named tests: 0 FAILED. Standing suite once: FAILED lines verbatim.
- apt_dat.py open() pins utf-8.
- No `apt_dat_path` passed into `Inputs`. No second selector implementation.

## Files

Yours: `Ortho4XP/src/auto_patch/engine_v2.py`, `Ortho4XP/src/auto_patch/driver.py`, `Ortho4XP/src/auto_patch_v2/airport/apt_dat.py`, `Ortho4XP/tests/test_auto_patch_freshness.py`, `Ortho4XP/tests/test_auto_patch_engine_dispatch.py`

## Spec (design-surface) §44

## §44 A PACK WITHOUT PAVEMENT BORROWS THE GLOBAL AIRPORT'S (owner 2026-09-15; RULINGS 2026-09-15m; Fable 2026-09-15) — lane `v2pavborrow`

**THE DEFECT (LGAV, the owner's tile build 2026-09-14 23:14, engine 1.50.1785).**
The FlyTampa LGAV pack authored NO taxiway or apron pavement: its apt.dat block
carries two row-110 polygons, both runway-length strips (369,545 m²), and the
airport's pavement is IMAGERY — 41 draped `Overlays_orthos/Ground_*.obj` pages
declared `ATTR_layer_group_draped markings -2`, which §42's gate rightly refuses
(`report.load.object_pavements.refused["layer group markings"] = 21`). The
engine's pack precedence (`airport/apt_dat.find_apt_dat`, v1's rule) is "a
Custom Scenery pack carrying the airport WITH row-110 pavement wins", and two
polygons are row-110 pavement — so LGAV was graded with `faces_by_role =
{runway 4, graded_strip 4, junction 15, tunnel_ramp 2, retaining_wall 6,
door_ramp 1, tunnel_trench 5}`: ZERO taxiways, ZERO aprons, every apron object
on raw 30 m DEM. The Global Airports block for LGAV carries 63 pavement polygons
(2,409,902 m² as a union) and one row-130 boundary; the custom block's pavement
covers 1.3 % of it.

**THE LAW.**

(1) **THE PACK IS STILL THE PACK.** The selected pack is the first Custom
Scenery pack (sorted, `Global Airports` excluded) whose apt.dat carries the
ICAO — that is what X-Plane renders: its runways, lights, lines, startups,
metadata, and its DSF objects (the object stage, the pads, the seats). The old
tail of the precedence rule — "a pack without pavement is the fallback of last
resort", under which a pavement-less custom pack LOST the selection to Global
Airports and its objects were never read — is DELETED; §44 (2) does that work.
Among several custom packs the precedence stays as today (the first with row-110
pavement, else the first).

(2) **THE BORROW TRIGGER — COVERAGE (owner 15m: "Coverage < 25 %").** With the
selected custom block parsed, the Global Airports block for the same ICAO is
parsed too (XP12 `Global Scenery/Global Airports`, then XP11 `Custom
Scenery/Global Airports`, then the stock default; the first that carries the
ICAO). `coverage = area(custom_pavement_union ∩ global_pavement_union) /
area(global_pavement_union)`, in the airport frame. When `coverage <
[load] pavement_borrow_coverage_max` (0.25) the pack BORROWS. A custom block
with no row-110 rows has coverage 0 and borrows; no Global block → nothing
borrowed and the custom stands; the key at 0 never borrows, at 1 always does
when a Global block exists. The number is law (`law/structures.toml [load]`,
`LoadLaw.pavement_borrow_coverage_max`, validated 0 ≤ x ≤ 1).

(3) **WHAT IS BORROWED (owner 15m: "Pavement + boundary").** The Global block's
row-110 pavement polygons, parsed by the same parser, APPENDED to the custom
block's own (borrowing adds, never removes — LGAV's two runway strips are real
pavement and §40 classifies them as the runway's; overlaps between polygons are
the planar partition's business, as they already are among Global's own 63);
and the Global block's row-130 boundary ONLY when the custom block has none.
NOT borrowed: runways, lines (row 120), the taxi network (1201/1202 — the
pack's own, authored on its imagery, stays: 226 nodes / 290 edges at LGAV),
startups, metadata, the DSF. Every borrowed record says so (`Pavement.source
= "global_airports"` or the model's equivalent — the lane names it).

(4) **IDENTITY.** `SceneryPack` gains `borrowed_apt_dat_path: str` and
`borrowed_block_sha256: str` (both "" when nothing was borrowed); the signature
carries them; every cache keyed on the apt.dat path — the partition cache's key
list (`airport/partition_cache.py` ~:178) — includes the borrowed sha, so a
Global Airports update invalidates it; the patch header gains
`o4_apt_dat_borrowed`. `report.load.pavement_source = {"pack": …,
"borrowed_from": … | null, "coverage": 0.013, "custom_pavements": 2,
"borrowed_pavements": 63, "borrowed_boundary": true}` and ONE log line:
`[load] LGAV: the pack's apt.dat carries 2 pavement(s) covering 1.3 % of Global
Airports' 63 (< 25 %): pavement + boundary BORROWED from <path> (§44)`.

(5) **ONE DERIVATION SITE.** The borrow is decided in `airport/pack.py`
(`select_pack` → `PackSelection` gains the borrowed path / reason) and composed
in `airport/load.py` at the one place the block is parsed (:198–:211). No
consumer re-derives it.

### §44.1 CONSUMER CENSUS (owner RULINGS 2026-08-30l) — every reader of the affected geometry, ruled before any edit

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `airport/apt_dat.find_apt_dat` | pack precedence | EDIT: the "last resort" tail deleted (§44 (1)); returns the custom candidate first as today. |
| C2 | `airport/pack.select_pack` / `PackSelection` | the selection | EDIT: the single derivation site of the borrow (§44 (2), (5)); `PackSelection` gains `borrowed_apt_dat_path`, `borrow_reason`. |
| C3 | `airport/load.load_with_report` :198–:211, :241–:253 | parses the block; builds `pavements`, `boundaries` | EDIT: parse the borrowed block, append (§44 (3)); report + log (§44 (4)). |
| C4 | `model/airport.SceneryPack`; `airport/pack.signature` | the signature | EDIT: two fields (§44 (4)). |
| C5 | `airport/partition_cache` key list ~:178 | apt path in the key | EDIT: borrowed sha in the key. |
| C6 | `airport/pack_partition` :473 (`pack_root` from the apt path) | the pack root for object resolution | UNAFFECTED: the root is the CUSTOM pack's (objects resolve there) — that is §44 (1)'s point. |
| C7 | `pipeline/build.py` :875 patch header | `o4_apt_dat`, `o4_pack` | EDIT: `o4_apt_dat_borrowed` beside them. |
| C8 | `airport/load.LoadReport` | the load report | EDIT: `pavement_source`. |
| C9 | flat-site region (`FlatVerdict.region` = pavement ∪ boundary ⊕ margin), `_own_extent`, the DSF pavement admission gate (1 km of own pavement), §42 object pavements | pavement / boundary sets | UNAFFECTED in code; CHANGED BY DATA as intended — the region, extent and gate now stand on the borrowed pavement. |
| C10 | the DEM-inset stage's OWN apt.dat resolver (`auto_patch/osm_load.py` :624–:663 via v1 `apt_dat_reader.find_airport_apt_dat`, reached from `O4_Airport_Elevation_Insets`) — a SECOND resolver | the inset extent | MEASURE, not edit: after the borrow, does LGAV's inset still cover the layout 100 % (the log's "inset coverage", `report.load.dem_provenance`)? If the extent falls short of the borrowed pavement, REPORT it — the inset regenerates only under `--refresh-data dem`, the owner's act; the resolver unification belongs to stage B of the v1 retirement. |
| C11 | the mod-cache directory (`sel.name`), `airport/dsf.find_text_dump` | the custom pack's name | UNAFFECTED. |
| C12 | `O4_Airport_Index` (Global-only index), the Swift app | apt.dat paths | UNAFFECTED: no wire event changes; the log line is plain text. |
| C13 | the `.axes.json` sidecar / census keys | any key naming the apt.dat | The lane greps `apt_dat` in `emit/` and `tools/harness/`: a key that names the path carries the borrowed path beside it; otherwise UNAFFECTED (state which). |

### §44.2 Twins (`tests/auto_patch_v2/test_airport_load.py`, beside `test_pack_selection_prefers_custom_pack_with_pavement`)

(a) a fixture root with a custom pack carrying the ICAO with two runway-strip
polygons and a Global Airports file with N polygons + one boundary → borrow
fires; pavements = 2 + N; boundary borrowed; signature and partition key carry
the borrowed sha; `pavement_source.coverage` < 0.25. (b) coverage ≥ 0.25 →
nothing borrowed, byte-identical to today (the CYXY fixture stays green). (c)
no Global block → nothing borrowed, no exception. (d) the custom block has a
row-130 boundary → the boundary is NOT borrowed. (e) the key at 0 → never.
`tests/test_harness.py` stays green (no census key changes unless C13 says so).

### §44.3 Closing test

ONE LGAV patch build through `tools/harness/build_airport.py LGAV` (the inset
is warm from the owner's 2026-09-14 build; the DEM is COPERNICUSGLO30 30 m —
LGAV's production frame). Expected: `planar.faces_by_role` gains `taxiway` /
`apron` faces against the before-column above; `report.load.pavement_source`
as in §44 (4); the object stage's pads now stand beside graded aprons (§20);
the census through `tools/harness/census.py`; NO shared-repo write. Register
the report with `tools/harness/frames.py`.

## RULINGS

## 2026-09-15m OWNER: a custom pack whose apt.dat authored no pavement borrows the Global Airports pavement (+ boundary) and keeps its own objects — the trigger is COVERAGE < 25 % (spec §44, lane `v2pavborrow`)

Owner 2026-09-15 on the LGAV read: "It's a case where the author included
no pavement at all and relied only on imagery. In this case we should
fall back to default global scenery airport package just for pavement,
but still use the custom scenery for objects/pads/ and seat buildings
where needed." Two decisions put with the data (FlyTampa LGAV: 2
runway-strip polygons, 1.3 % coverage of the Global block's 63 /
2,409,902 m²; the engine's "any row-110 polygon wins" rule graded LGAV
with zero taxiways and aprons):
* **Trigger → "Coverage < 25 % (Recommended)"**: borrow when the custom
  block's pavement covers under 25 % of the Global block's pavement
  area for the same ICAO (`[load] pavement_borrow_coverage_max = 0.25`).
* **What borrows → "Pavement + boundary (Recommended)"**: the row-110
  polygons and the row-130 boundary (only when the pack has none);
  runways, lights, lines, startups, metadata, the taxi network and the
  DSF objects stay the custom pack's.
The old "a pack without pavement is the fallback of last resort" tail of
the precedence rule is deleted (the pack stays the pack; its objects are
read). Consumer census §44.1 (13 rows) written before any edit per
RULINGS 2026-08-30l; C10 (the DEM-inset stage's own v1 resolver) is a
MEASURE row, its unification deferred to stage B of the v1 retirement.

## Tool: build_airport

| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo (including a SCHEMA-STALE cached OSM layer — `schema_stale_osm_layers`, 2026-09-15: a road cache written under an older `ROAD_CACHE_TAG_SCHEMA` is re-downloaded by the tile build's background prefetch and REWRITTEN mid-build, so it is named under `osm_layers` and refused up front; and a pack DSF whose sha has NO cached DSFTool text dump in either the shared corpus or this lane's overlay — `missing_pack_dsf_dumps`, scope `airport_mod_cache`, the engine's own `airport/dsf.find_text_dump` / `dsf_write.pristine_dsf_path`: the dump is a SUBPROCESS write no Python guard can refuse at the call, so the only honest defence is up front; the judge is the READER's own — `superseded_road_feeds` asks `auto_patch_v2/airport/osm.ROAD_FEEDS` / `feed_path` / `feed_tag_schema` over the SAME 3x3 neighbourhood `load_feed` merges, because the build's own tile is not the square the loader reads: KDFW died 54 s in on the NEIGHBOUR +33-098's feed, KPHX owes +33-112. `--refresh-data osm_layers` then CLEARS it — `refresh_stale_osm_layers` moves each named layer aside as `<name>.stale-<schema>` inside the scope lock and the armed guard, lets the ENGINE's own `start_background_osm_prefetch`/`wait_for_background_osm_prefetch` re-derive it before the build, removes the aside copy on success and puts it BACK (refusing) when nothing schema-current came back.  An AUTHORISED scope is no longer a cold-frame refusal (`require_dem_frame(requested=…)`): the run proceeds to the derivation and the frame is RE-JUDGED with nothing authorised afterwards, so `--refresh-data osm_layers,dem` can warm a COLD tile — absent layers and the airports layer through the engine's prefetch pair, the base raster and the tile's insets through `refresh_tile_dem` (`O4_DEM_Utils.DEM` + `ensure_insets_for_tile(refresh=True)`, so `--warm-insets ICAO` is no longer needed for a cold tile and stays for the per-ICAO case). `--refresh-only` does exactly those refreshes for the named tile, stamps the ledger and EXITS without building — its pre-flight STANDS DOWN (a warm run reads nothing and builds nothing; refusing there stopped KDFW +33-098 warming anything over 31 unrelated `dem` items) and its exit code is decided AFTER the derivations by `require_refreshed_frame`, on the REQUESTED scopes alone. The derivations, the re-judge and the build all sit inside ONE try whose `finally` snapshots, stamps the ledger and releases every scope lock on EVERY exit path — before round 6 a refusal after a derivation lost the `REFRESH RECORDED` line (KPHX's +33-112_big_roads, re-derived 13:48, unledgered) and leaked `.harness/locks/osm_layers.lock`. `--reconcile-ledger` stamps the CURRENT hash of any artefact of the requested scopes that the ledger does not account for — `never-ledgered` (no line names it at all) or `stale-line` (the newest line naming it predates its mtime), per path in `reconciled_paths`, one record per scope marked `reconciled: true`. The paths are SHARED-REPO-relative (`corpus_base`): a lane's `OSM_data` is a symlink into the repo, and relativising against the lane root silently emptied the whole list (measured at +33-112, round 7) — explicit, never automatic, because another lane's authorised refresh looks identical from outside — the way to warm a neighbour tile without paying for a whole `--tile` build. Without this the authorised refresh was a no-op: measured at VMMC 2026-09-15, rc 0 in 23 s, "authorised but wrote NOTHING — the artifact was already present", and the next plain build refused on the same file); guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. It also refuses a DEGRADATION THE ENGINE SWALLOWED (2026-08-07): `auto_patch.elevation._load_airport_dem` runs production's whole DEM prep inside one `except Exception`, so a write the shared-repo guard blocked became a WARN line, `dem_inset_provenance: null` and a build that exited 0 on 18.5 k nodes against production's 34-36 k (measured at HECA, `tmp/sliver_attrib`). Two independent detectors close it — a write the guard blocked during a build that nevertheless returned, and a laylane carrying no DEM provenance at all — and either refuses BEFORE the patch is written, so a DEM-less `.osm` never lands where a census would find it. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. The mod-cache redirect is also handed to v2's own loader (`inputs.mod_cache_root`), which `planar.__main__.default_inputs` cannot do for itself — it reads no environment by design, so before 2026-09-13 the pack-dump FRESHNESS guard (`airport/load.py:289`) judged the SHARED root and refused every KCLT / HECA v2 build and `explain` (RULINGS 2026-09-13q, "chip"); the build now reads and derives its DSF text dumps in the same lane-local overlay every other derived cache lands in. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. |

| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |

## Tool: brief_pack

| `tools/brief_pack.py` | A SELF-CONTAINED LANE BRIEF (owner 2026-09-13): `--lane L --base SHA --spec '§37 (6)' --rulings 13aj 13ab --index road_terrain_conformance --frames KCLT --notes n.md --bars b.md --files … --avoid … > docs/briefs/L.md` — pulls every section VERBATIM through `docq.py` and `frames.py` and appends the standing discipline block, so the session never retypes law and the lane reads one file. `docs/briefs/README.md` is the protocol. Twin in `Ortho4XP/tests/test_docq.py`. |

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

