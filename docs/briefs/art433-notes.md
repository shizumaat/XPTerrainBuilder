# art433 continuation notes (issue #433, RULINGS 2026-10-06c / 06b)

WIP handed back early (machine shutdown 2026-10-06). Branch `claude/art433`.
State: the five touched Python files COMPILE; NOTHING below has been run under
pytest; no twin exists yet; no UI, protocol or harness edit has been made.
`UI.pack_missing_art` (called from `engine_v2._announce_pack_art`) DOES NOT
EXIST YET - the engine stage raises AttributeError (caught per airport as
"placement failed") until step N1 below lands. Do that first.

## Items 1-8
1. CENSUS - partial (table below; not finished for the Qt/Swift readers).
2. THE CHECK - DONE in code, proven on the OTHH dump, NO twins yet.
   `Ortho4XP/src/auto_patch_v2/airport/pack_art.py`:
   `missing_definitions(pack_root, dump_path_or_rows, index, also_exported=None)`.
3. THE WARNING - partial: log line + event call written in
   `auto_patch/engine_v2.py` (`_announce_pack_art`); the event class, the
   `O4_UI_Utils` hook, the session method, the parallel forwarder and both UIs
   are NOT written.
4. THE OFFER - partial: pure omission `pack_art.omit_definitions`; write path
   `dsf_write.write_pack(..., omit=)` + `placement_write.apply_plan(..., omit=)`;
   record `omitted_art` in `o4_placement_provenance.json`; engine stage
   `_art_stage` / `_write_art_only` / `omit_missing_art` in `engine_v2.py`.
   Unrun, untwinned. Build keyword and command NOT plumbed.
5. OTHH PROOF - DONE offline (numbers below).
6. UI - not started.  7. HECA closing build - not started.
8. Suites / ratchets / PR - not started. No PR was opened.

## Census (as far as it got)
| site | reads / writes | note |
|---|---|---|
| `auto_patch_v2/airport/dsf.py` `find_text_dump` / `content_keyed_dump` / `read_dump` | reads the cached DSFTool text dump (content-tagged) | reads only OBJECT_DEF, POLYGON_DEF, OBJECT*, polygons; ignores NETWORK_DEF / TERRAIN_DEF |
| `auto_patch_v2/airport/load.py` ~430-530 | reads dump + `obj8.read_library_index` + `obj8.resolve_resource` | the build's loader; library index read-only from the mod cache |
| `auto_patch/dsf_reader.py` `ensure_dsf_text_path` | RUNS DSFTool, writes a dump into `Airport_mod_cache/<pack>/` | used by the object stage; not for read-only (lane) paths |
| `auto_patch/engine_v2.py` `rebake_after_mesh` -> `_place_objects` | post-mesh object stage, per plan file `o4_v2_rebake_<ICAO>.json`; silent when `modify_custom_airports` is off; measure-only under `O4_PACK_WRITES=measure_only` (every harness build) | the check now sits here, BEFORE the `not plan_.units` skip |
| `placement_write.apply_plan` -> `restore_pack_objects`, `write_files`, `dsf_write.write_pack` | restores .obj from `.anchor_bak`, writes cut bodies, rewrites the DSF | ONE DSF writer |
| `dsf_write.write_pack` | dump(pristine backup) -> `edit_dump` -> [NEW `pack_art.omit_definitions`] -> DSFTool encode -> `verify_roundtrip` (vs the edited text) -> record -> move | pristine kept once as `<dsf>.anchor_bak`; always the source |
| `backup_state.py` `read_record` / `dsf_entry` / `update_dsf_entry` | `o4_placement_provenance.json` beside the DSF, per-DSF entries under `dsfs` | NEW key `omitted_art` per DSF entry (None when no omission) |
| `auto_patch/agp_reader.py` `get_library_index` / `_parse_library_txt` | merged library.txt index, sidecar `o4_library_index_<sha1(xplane_root)[:16]>.cache`; enabled packs only; merges EXPORT, EXPORT_EXTEND, EXPORT_BACKUP, EXPORT_RATIO only | NEW `other_export_names(xplane_root)` (check-only, never merged) |

Definition kinds in a DSFTool dump: OBJECT_DEF (used by OBJECT / OBJECT_MSL /
OBJECT_AGL idx), POLYGON_DEF (BEGIN_POLYGON idx .. END_POLYGON), NETWORK_DEF
(BEGIN_SEGMENT[_CURVED] idx .. END_SEGMENT[_CURVED]), TERRAIN_DEF (BEGIN_PATCH
idx .. END_PATCH), RASTER_DEF (a layer NAME, not a file - never checked).
Resolution: pack-relative file first, then the library index
(`obj8.resolve_resource`, exact key then lower-cased key).

WHAT COUNTS AS MISSING (decided, in the module doc):
- the file system answers (`os.path.isfile`), as it answers X-Plane's open: a
  case-only mismatch is present on a case-insensitive volume, missing on a
  case-sensitive one; `\` and `:` read as `/`;
- `terrain_Water` built in; RASTER_DEF never checked;
- a STOCK `lib/...` path is NEVER called missing. FINDING: the merged index
  does not model all of X-Plane's exports - over the 216 cached pack dumps in
  the corpus, 437 distinct `lib/` defs are absent from the index
  (`lib/g10/autogen/*.ags`, `lib/vegetation/trees/deciduous/*.for`, ...) in
  packs that load. Cause NOT established (EXPORT_SEASON / EXPORT_EXCLUDE
  suspected; the install was not read). Consequence: a genuinely missing stock
  path is not reported;
- any name another `EXPORT*` directive mentions (`other_export_names`,
  over-inclusive, asked only when something looks missing) is not missing;
- no library index (None) -> the check answers None (says nothing);
- a missing TERRAIN_DEF is reported but NOT omittable (`can_omit` False): its
  patches are the mesh. OPEN QUESTION for the master/owner: with
  `can_omit=False` the UIs should show the warning without the primary button
  - yes/no? (recommend yes.)
NOT VERIFIED without X-Plane: that every def kind cancels the pack the way a
.pol did; X-Plane's case behaviour on Linux; PRIVATE / REGION export handling;
that the cleaned DSF loads (owner's sim test).

## Design decisions
- Event: `PackMissingArt` (ADD to `o4_engine/events.py`, protocol 1.8 -> 1.9,
  add to `parallel._FORWARDED_EVENT_TYPES`, match as a string literal in
  `Sources/SceneryKit/OrthoEngineClient.swift`). Fields:
  `pack, pack_root, lat, lon, total, kinds{kind:n}, uses, first_paths(<=5),
  can_omit, state("found"|"omitted"|"failed"|"none"), error`
  (= `pack_art.summary()` + the six others; see `engine_v2._announce_pack_art`).
- Where the check sits: `engine_v2.rebake_after_mesh`, per plan, before the
  `not plan_.units` skip (`_art_stage`); only for an existing, unprotected,
  ENABLED Custom Scenery pack with a tile DSF and a dump; silent with
  `modify_custom_airports` off (the whole stage stands down, #42).
  Read-only arm (harness / measure-only / DSF_OBJECT_REANCHOR off) uses
  `find_text_dump` (never DSFTool) and ONLY REPORTS.
- How the choice travels: (a) build keyword `missing_art` = "omit" | "leave" |
  absent (absent = warn, leave the pack) on build / enqueue_build, mirroring
  `boundary_policy` (session.py:690/716/748/789, parallel.py:810/899/926/1028/
  1206 `configuration.missing_art = ...`; in-process:
  `engine_v2.set_missing_art_policy`); (b) UI flow: the event arrives during
  the build, the UI shows the fixed copy, the primary button sends a NEW
  command `omit_missing_art {pack_root, lat, lon}` ->
  `engine_v2.omit_missing_art()` on a worker thread (never the read loop) ->
  a second `PackMissingArt(state="omitted"|"failed")`. No rebuild needed.
  (c) the acceptance is remembered in the pack's record: `omitted_art.key` =
  `pack_art.decision_key(sha256(pristine DSF), missing set)`; a later build
  whose key matches omits again without asking; a different key (pack updated,
  art restored or lost) asks again, and `_PackArt.stale` forces a write that
  puts the definitions back.
- Omission is applied AFTER `edit_dump` (plan ordinals count pristine rows).
  A plan with icao "" = the omission alone: recorded airports' edits are
  re-applied via `_sibling_plans`, none re-recorded.
- Fixed UI copy: in the lane brief (title / body / two buttons / detail line);
  log line implemented verbatim in `pack_art.log_line`.

## OTHH proof (offline; dump tag 4229c95f; synthetic pack root without Imagery/, synthetic index built from key lookups of the cached index)
- declared: 1,397 OBJECT_DEF, 228 POLYGON_DEF, 0 NETWORK_DEF, 0 TERRAIN_DEF;
  236,778 lines, 10.9 MB.
- check: 108 missing, all polygon, all under `Imagery/test/`, each used by
  exactly 1 polygon (108 uses); first: `Imagery/test/test1_ref+10k+10k.pol`,
  then +10k+8k, +10k+6k, +10k+4k, +10k+2k.
- cost: head-only read 0.27 ms; nothing missing 2.7 ms; 108 missing incl. the
  use count 28 ms; omission 67 ms.
- cleaned text: POLYGON_DEF 228 -> 120; BEGIN_POLYGON / END_POLYGON 18,196 ->
  18,088; BEGIN_WINDING 18,483 -> 18,375; POLYGON_POINT 125,147 -> 124,715;
  OBJECT_DEF 1,397, OBJECT 21,524, OBJECT_AGL 14,884, PROPERTY 179, FILTER 5
  unchanged and every such line byte-equal in order.
- through `dsf.read_dump` (accept all): polygons 12,761 -> 12,653, placements
  36,408 -> 36,408 identical, surviving polygons identical in order; re-check
  of the cleaned text: nothing missing.
- 103 defs resolve through the library; 1 stock path the index lacks:
  `lib/vegetation/trees/deciduous/aspen_medium.for` (the finding above).
- Loading the cleaned DSF in X-Plane is the owner's test. Script (not
  committed): scratchpad `art433/prove_othh.py`.

## Next lane, in order
N1. `O4_UI_Utils.pack_missing_art(**fields)` (pattern: `auto_patch_failed`),
    `EngineSession.pack_missing_art`, event class, protocol 1.9, forwarder.
N2. build keyword `missing_art` + command `omit_missing_art` (jsonl.py command
    table + capabilities; worker thread).
N3. twins (tests/auto_patch_v2/test_pack_art.py): all present; one missing
    object; missing polygons; library path resolving / not; case-only mismatch
    (assert == what the volume says); omission round trip, renumbering, byte-
    equal survivors, ValueError on a stale list, record + accepted(),
    restore; `_art_stage` read-only arm writes nothing.
N4. harness: confirm `build_airport.py` only reports (measure-only already).
N5. Swift (`OrthoEngineClient.swift`, BuildModel) + Qt (`O4_Qt_GUI.py` event
    map ~line 713) alert with the fixed copy.
N6. HECA closing build `--tag art433_HECA`, suites, ratchets, blast.py wire
    drift, frozen spec parity (pack_art is statically imported by dsf_write).
Review before trusting: `_art_stage` state logic when a placement write
follows and then fails; `write_pack` top-level `icao` for the icao-less plan.
