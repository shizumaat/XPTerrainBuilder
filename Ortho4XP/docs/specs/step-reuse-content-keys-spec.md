# Step reuse on content keys — spec (2026-10-17, Beta 3 W1)

Status: PROPOSAL; extends `src/O4_Step_Reuse.py` (#615, owner 2026-10-12) and
its twin `tests/test_step_reuse.py`. Plan: `beta3-build-speed-plan-20261017.md`
W1. Issues: manifest B3-04 … B3-07. Prior art: E `graph/keys.py` (key = recipe
of input content digests; early cutoff for free), `graph/digest.py` (mmap file
digests), `graph/store.py` (commit by rename).

## 1. Problem (verified 2026-10-17)

`O4_Step_Reuse` reuses `vector`, `mesh` and `masks` by name when a record
matches (`REUSABLE_STEPS`, `:63`). Four properties keep it from hitting in
practice:

1. **Whole-tree code identity.** `_code_identity()` (`:211-215`) keys every
   step on `provenance_code.code_digest()` — one digest over every `.py`/`.toml`
   under `src` (`provenance_code.py:10-16`). Any commit stales every step; a
   no-op rebuild never hits during development, and every engine update
   re-runs vector+mesh+masks for every user.
2. **Record identity, not output content.** A step's `previous` input is the
   predecessor's RECORD digest (`_previous_digest`, `:269-274`), so a vector
   step that reran and produced the SAME bytes still stales the mesh. E gets
   early cutoff for free by keying on the predecessor's output digest.
3. **Outputs by stat.** `_outputs()` identifies files by `provenance.identity_list`
   = path|size|mtime (`provenance.py:663-678`); a touched file reads as changed,
   and a file with the same mtime and size but new content reads as unchanged.
4. **Commit at the end only.** Records are PENDING until the scenery-file step
   completes (`commit`, module doc); a Stop commits nothing.

Not reusable at all: the scenery-file step (DSF build + imagery + conversion),
although `O4_DSF_Utils.py:1229-1233` already skips the download of a texture
whose `.dds` is whole (`DDS.is_whole`) — a NAME-level reuse inside one build dir,
nothing across build dirs or neighbour tiles.

## 2. Design

### 2.1 Per-step code identity (B3-04)

Replace `_code_identity()["code"]` with a per-step digest:
`O4_Step_Code.py` (new, stdlib-only like `partition_code.py`, run by the `.spec`
files with `runpy` at freeze) declaring `ENTRY_MODULES` per step —

- `vector`: `O4_Vector_Map`, `O4_Vector_Utils`, `O4_OSM_Utils`,
  `O4_Airport_Utils`, `auto_patch.driver` (whose closure reaches most of the
  tree: the vector step keeps a near-whole-tree digest, and that is the truth);
- `mesh`: `O4_Mesh_Utils`, `O4_DEM_Utils`, `O4_Airport_Elevation_Insets`,
  `auto_patch.post_mesh` (the object stage runs inside the mesh step);
- `masks`: `O4_Mask_Utils`, `O4_Bathymetry_Band`;

the closure computed as `partition_code` does (every `import`, function-level
included), held by a twin, written at freeze as `step_code.sha256`. The
`auto_patch_cfg` and `engine` keys stay. Patch freshness (`driver.
_auto_patch_is_current`, `o4_code`) is NOT changed: #346 chose the whole tree
for the patch on purpose ("a rule has no holes"), and the patch closure reaches
402/437 modules anyway.

Expected effect (hypothesis): a commit touching `auto_patch_v2/` or the DSF/
imagery modules no longer stales mesh or masks; a commit touching
`O4_Mesh_Utils` stales mesh and masks and not vector.

### 2.2 Output-content keys and early cutoff (B3-05)

- `_outputs()` records, per file, `path|size|sha256` where the digest is
  `hashlib.file_digest(f, "sha256")` (stdlib, 3.11+; `blake3` admitted later
  only if measured faster — owner Q4). Size+mtime are kept in the record as a
  pre-check: equal stat → digest skipped (the hit path costs stats only);
  differing stat → digest decides. The `.mesh` is written atomically already
  (`write_mesh_file`, temp + `os.replace`).
- `previous` becomes the predecessor's OUTPUT digest (its `outputs` field),
  not its record digest. A vector step that reran and wrote identical files
  therefore leaves the mesh reusable (early cutoff).
- Cost: hashing the vector outputs (`Data<tile>.node/.poly/.apt/.alt` +
  patches) and the `.mesh` once per step run. Hypothesis ≤ 1 s per tile for
  100–300 MB at NVMe speed; the law's 1 % is 3 s; measured on one tile ×3.
  The `.alt` raster is large (float32 DEM); its digest may be replaced by the
  DEM fingerprint the patch gate already computes (`provenance.dem_fingerprint`,
  `provenance.py:869`) if measured over 0.5 s.

### 2.3 Commit per step, resume after a stop (B3-06a; owner Q3)

`record()` writes PENDING today and `commit()` promotes at the end. Change:
a step's record is committed WHEN THE STEP ENDS and its outputs are on disk,
because its outputs are a function of its inputs regardless of what happens
later. The invariants that protected the old rule still hold:

- `forget_from(step)` runs before a step starts (unchanged): a build that
  reruns vector drops mesh and masks records first;
- the mesh record keys its pack-DSF outputs (`pack_dsfs`, journalled); a Stop
  that puts the packs back (`O4_Stopped_Build`) changes those files, so the
  mesh record correctly misses on the next build while vector hits;
- the scenery-file step's completion no longer commits anything (nothing is
  pending).

Twin: Stop after mesh → next build reuses vector, reruns mesh (pack put back)
and masks; Stop during vector → nothing reused.

### 2.4 The scenery-file step as a reusable step (B3-06b)

`dsf` joins `REUSABLE_STEPS` with inputs: masks output digest, `list_dsf_vars`
+ imagery source/zoom/zone settings (the texture settings the module doc
excludes from the earlier steps), the DSF code digest, and the SET of texture
files present and whole (`DDS.is_whole`) — outputs: the `.dsf`, the `terrain/`
and `textures/` listings by content. A hit means a no-op rebuild. Value is
development-time mainly (the user changes something before rebuilding); it is
the LAST landing of W1 and may be dropped if the measured no-op rebuild is
already dominated by the imagery check. The activation step (rename into the
scenery pack) is never skipped.

### 2.5 Per-texture DDS content cache (B3-07)

Today a texture is converted when its `.dds` is not whole in THIS build dir.
Textures are 16×16 tile groups on the zoom level's grid, so a neighbour tile
shares the grid-aligned textures along its edge, and a cleared build dir
reconverts everything. Design:

- key = sha256 of the source orthophoto JPEG(s) the texture is built from +
  the mask PNG (when masked) + the colour-filter name + the harmonization field
  digest + the converter identity (DDSTool/nvcompress binary digest and the
  `--png2dxt1/5` or `-bc1/-bc3 -fast` arguments) + `dxt5` flag;
- store `<data root>/DDS_cache/<key[:2]>/<key>.dds` (derived, never corpus;
  under the harness it is a lane-local root like `O4_DSF_CACHE_DIR`); the
  conversion writes its partial beside the final name as today (#600) and
  ALSO hardlinks (fallback: copies) the finished file into the cache;
  `convert_texture` checks the cache before launching the converter;
- LRU sweep with a size cap (default 20 GB; owner Q1 class of decision);
- `O4_DDS_CACHE=0` turns it off.

Gate: `.dds` sha256-identical whether served from the cache or converted.

## 3. Interfaces and files touched (`tools/blast.py`, 2026-10-17)

| File | Hazards from blast |
|---|---|
| `src/O4_Step_Reuse.py` | imported by `O4_Tile_Utils.py`, `o4_engine/session.py`; env flag `O4_STEP_REUSE` (default ON, read in no test) — the new flags `O4_DDS_CACHE` must get a test |
| `src/O4_Step_Code.py` (new) | stdlib only; run by `Ortho4XP.spec` / `Ortho4XP_Qt.spec` at freeze |
| `src/auto_patch/provenance.py` | `identity_list` shared by the patch gate — ADD `content_identity_list`, do not change `identity_list` (the `<osm>` stamp format is a wire the gate reads back) |
| `src/O4_Tile_Utils.py` | the step dispatcher; imported by `O4_Config_Utils`, `session.py` |
| `src/O4_Imagery_Utils.py` (B3-07) | imported by 25 files; `convert_texture` at `:2727` |
| `src/O4_DDS_File.py` | `is_whole`, `partial_name`, `land` are the shared DDS helpers — extend here |
| `src/o4_engine/session.py` | reads `predicted_reuse` for the progress bar (`test_session_skips_reused_steps_by_name`); the `StepProgress` wire event is unchanged |

No wire-protocol change; no role literal; no law table.

## 4. Tests and twins

Extend `tests/test_step_reuse.py` (17 tests today): an unrelated module edit
keeps mesh and masks reusable (per-step closure); the vector step rerun with
identical outputs keeps the mesh reusable (early cutoff); a touched file with
identical content is not a change; a changed file with equal size+mtime IS a
change; commit-per-step and the Stop twins of §2.3; the `dsf` step's inputs
exclude nothing the module doc's exclusion test covers
(`test_no_texture_setting_is_an_input_of_the_earlier_steps` stays).
New `tests/test_step_code_closure.py` (the `partition_code` twin pattern).
New `tests/test_dds_cache.py`: hit serves identical bytes; a filter or
harmonization change misses; cache off converts.

## 5. Acceptance and rollback

- One tile, two builds with an unrelated commit between: the second build's
  step records show vector/mesh/masks reused; `.mesh` and `.dsf` sha256
  identical to the first build's.
- `run_tile_mesh_only.py` ×3 before/after B3-05: the added digest cost
  reported; ≥ 3 s median triggers the review.
- B3-07: one tile, cleared `textures/`, second build converts zero textures;
  `.dds` set sha256-identical.
- Rollback: `O4_STEP_REUSE=0` / `O4_DDS_CACHE=0`, then `git revert`.

## 6. Out of scope

Reusing the activation step; a graph scheduler; changing the patch freshness
gate's keying; the imagery prefetch step (#622 item 3, its own plan).

## Licence

Re-implemented; no E code. `Ortho4XP/` (GPL-3).
