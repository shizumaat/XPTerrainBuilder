# Brief pack — lane `v2pavborrow`

Base: main `8b8b2afc` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§44 the pavement borrow: LGAV keeps its objects, grades the Global Airports pavement

## The brief

# THE BRIEF — implement spec §44 exactly (the section is in this pack verbatim; the owner's two answers are RULINGS 15f)

One mechanism: the BORROW. Decided in `airport/pack.py` (one derivation site), composed in `airport/load.py` at
the one parse site, identity carried in `SceneryPack` + the partition-cache key + the patch header, reported in
`report.load.pavement_source` and ONE log line. Every §44.1 census row is ruled — do what each row says, nothing
more; C10 is a MEASUREMENT (report the inset coverage after the borrow, do not edit the v1 resolver), C13 is a
grep whose answer you state.

# FACTS YOU DO NOT NEED TO RE-DERIVE
- LGAV custom apt.dat: `/Users/noah/X-Plane 12/Custom Scenery/c_GRC - 100_airport - LGAV Athens_0_airport (FlyTampa)/Earth nav data/apt.dat`
  — 2 row-110 polygons (runway strips, 369,545 m² union), 0 row-130, 226/290 taxi network, 82 startups.
- Global Airports block for LGAV: 63 row-110 (2,409,902 m² union), 1 row-130; coverage of custom over global 1.3 %.
- Before-column for the closing test (LGAV report 2026-09-14, `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+37+023/LGAV/LGAV.report.json`):
  `faces_by_role = {runway 4, graded_strip 4, junction 15, tunnel_ramp 2, retaining_wall 6, door_ramp 1, tunnel_trench 5}`.
- `AptPavement.rings[0]` is a tuple of `(lon, lat)` tuples; `parse_airport_block`/`read_airport_block`/`file_has_airport`
  are in `airport/apt_dat.py`; the CYXY fixture test `test_pack_selection_prefers_custom_pack_with_pavement` is the
  neighbour of your twins.
- Coverage is computed in the airport frame (metres); use the frame the loader already builds from the CUSTOM block's
  reference point (the borrow does not move the frame).

# BARS
- Do not touch the trench/channel/structure passes, the object stage, or `auto_patch/osm_load.py` (C10 is measure-only).
- Files stay under the 1,000-line guideline (`load.py` 551, `apt_dat.py` 627, `pack.py` 112 today); if `load.py`
  would pass 1,000, the composition goes in a new `airport/borrow.py` with its own header.
- No five-airport sweep; ONE LGAV build as the closing test; no `--refresh-data`; no shared-repo write (the build
  entry refuses and reports — quote any refusal).
- The lane worktree mounts the shared data repo through `tools/harness/lane_worktree.sh up v2pavborrow`.

# CLOSING (quote verbatim in your final message)
1. `cd Ortho4XP && venv/bin/pytest tests/auto_patch_v2 tests/test_harness.py -q` — the FAILED lines or "0 failed".
2. The LGAV build's `report.load.pavement_source`, the new `planar.faces_by_role`, the census line, the inset
   coverage line (C10), and the `[load] LGAV: …` log line.
3. The commit sha on branch `claude/v2pavborrow`; `frames.py register` line for the report. The session merges.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/pack.py`, `Ortho4XP/src/auto_patch_v2/airport/apt_dat.py`, `Ortho4XP/src/auto_patch_v2/airport/load.py`, `Ortho4XP/src/auto_patch_v2/model/airport.py`, `Ortho4XP/src/auto_patch_v2/airport/partition_cache.py`, `Ortho4XP/src/auto_patch_v2/pipeline/build.py`, `Ortho4XP/src/auto_patch_v2/law/structures.toml`, `Ortho4XP/src/auto_patch_v2/law/model.py`, `Ortho4XP/tests/auto_patch_v2/test_airport_load.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/airport/placement_geom.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_cut.py`

## Spec (design-surface) §44

## §44 A PACK WITHOUT PAVEMENT BORROWS THE GLOBAL AIRPORT'S (owner 2026-09-15; RULINGS 2026-09-15f; Fable 2026-09-15) — lane `v2pavborrow`

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

(2) **THE BORROW TRIGGER — COVERAGE (owner 15f: "Coverage < 25 %").** With the
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

(3) **WHAT IS BORROWED (owner 15f: "Pavement + boundary").** The Global block's
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

## Spec (design-surface) §42

## §42 OBJECT-BASED PAVEMENT IS A SOURCE (owner RULINGS 2026-09-13cv; Fable 2026-09-13) — lane `v2drapedsrc`

**THE DEFECT (RULINGS 2026-09-13cu, HECA).**  `Airport/ground/Concrete_Polygon_1.obj`
is a draped OBJ8 ground polygon (`TEXTURE_DRAPED`, 1,137 vertices all at local
Y = 0, 379 triangles, 29 disjoint bodies, 580,331 m²) placed once at the pack
origin.  X-Plane drapes it correctly; the LAYOUT never sees it — pavement
sources are apt.dat 110 polygons and `.pol` POLYGON_DEF pages only
(`airport/load.py:309-381`), object footprints enter only as `building` pads.
The owner's apron at 30.1235047, 31.4160956 (body 6, 25,012 m²) drapes on raw
mesh at 95.09 while the mapped apron `pav132` is graded 82 m away.

1. **IDENTIFICATION.**  A placed OBJ8 whose draped geometry (a `TRIS` block
   under `TEXTURE_DRAPED` / `ATTR_draped`, every vertex within `draped_y_tol_m`
   (0.05) of Y = 0) covers ≥ `object_pavement_min_m2` (200) is OBJECT-BASED
   PAVEMENT.  Its footprint is the union of its draped triangles, transformed
   by the placement (origin, heading), split into DISJOINT BODIES; each body
   is one source polygon with `source = "dsf:object_pavement"`, the object's
   resource path as its description, and the pack's texture name as
   evidence.  A body that is also a solid object's footprint (`building` pad)
   is not double-counted: pads win where they overlap.
2. **CLASSIFICATION.**  An object-pavement body enters `classify/sources.py`
   as a `lot`/`open` source exactly like a `.pol` page and is kinded by the
   same evidence rules (§40's apron-cover refusal, corridor width, taxi
   length, runway shoulder); it carries no privileged role.  Where it
   overlaps an apt.dat or `.pol` page, the mapped page's evidence governs and
   the object body extends it (union), never a second surface (§41).
3. **THE CENSUS.**  `load` reports `object_pavements` (bodies, m², per
   resource) beside `dsf_pavements`; `explain --shape` names the resource for
   a cell born of one; the object-footprints cache gains the draped bodies
   under a separate key so the `building` pad path is untouched.

BARS: HECA the 1.0.329 frame dry: 29 bodies / ~580 k m² admitted from
`Concrete_Polygon_1.obj`, body 6 classified (apron by evidence, named); the
cell census before → after (no `building` pad lost, no cell duplicated);
CYXY/SPJC/KCLT/OTHH/LEMD dry from registered frames: every admitted object
pavement named with its resource and m² (a pack with none stays byte-identical);
ONE HECA build: the ground under body 6 graded, `pav132` and body 6 one apron
surface, no step at their seam; load stage not worse than +5 %; suite twice.

### §42 AMENDED — PAVEMENT DECLARES ITS LAYER GROUP; AN ADJACENT OBJECT BODY IS ITS OWN FACE (Fable 2026-09-13; RULINGS 2026-09-13dc) — lane `v2drapedsrc`

MEASURED (round 1, HECA 1.0.329 frame): §42 (1) as written admitted 27
placements / 937 bodies / 31.9 M m² — three times the airport — because baked
ambient-occlusion shadows (`AO.obj` 7.75 M m²), dirt decals (`ground/d1..d9`)
and painted markings (`asphalt_white`, `car_parking`) are all draped Y = 0
geometry.  And §42 (2)'s "union into the mapped page" made `pav132` one apron
ring of 2,687 nodes spanning 63.85–154.79 m of DEM (off-DEM max 11.73 m,
joint steps to 5.38 m) — a surface no apron cap can hold.

1. (1) amended: object-based pavement DECLARES ITSELF — the OBJ8 carries
   `ATTR_layer_group_draped` in a pavement group at offset ≤ 1 and no
   decorative basename token (v1's `_is_pavement_object` discriminator, now
   law: `[load] object_pavement_layer_groups`).  A shadow declares no draped
   group; a decal declares `markings`; a marking declares `runways +2`.  HECA:
   8 resources / 221 authored bodies / 5.69 M m².  A resource with SOLID
   triangles is not disqualified: its draped part is a source, its solid
   stays the pad path's; pads win where they overlap.
2. (2) amended: an object body UNIONS into a mapped page only where §41 (1)
   holds (the body lies ≥ 95 % inside the page's exterior ring).  An
   ADJACENT body is its OWN FACE — apron/lot/corridor by evidence — welded to
   the mapped page at the seam under the ordinary shape-joint and
   no-step laws, each face inside its own cap.  One field-wide apron is not
   the intent; classification is.

BARS (round 2): HECA dry — body 6 its own apron face adjacent to `pav132`
(or inside it: named); no apron face spanning > `apron_relief_max_m` (the
existing tier law's reach) of DEM; the role census before → after against a
BASE ARM built at the lane's base sha (not the 1.0.329 products — 13dc); ONE
HECA build; joint steps and off-DEM at the new seams named; load ≤ +5 % or the
cost named (the +0.25 s is under the 1 % review floor).

## RULINGS

## 2026-09-15f OWNER: a custom pack whose apt.dat authored no pavement borrows the Global Airports pavement (+ boundary) and keeps its own objects — the trigger is COVERAGE < 25 % (spec §44, lane `v2pavborrow`)

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

## 2026-09-13cv Owner: "Yes, lets try and identify object based pavement so we can classify it correctly" — §42 written, lane `v2drapedsrc`

* §42 OBJECT-BASED PAVEMENT IS A SOURCE: a placed OBJ8's draped, Y = 0
  geometry ≥ 200 m², per disjoint body, is a `dsf:object_pavement` source
  polygon classified by the same evidence rules as a `.pol` page; pads win
  on overlap; a mapped page's evidence governs where they meet (union,
  never a second surface). Census `object_pavements` in load; `explain`
  names the resource.
* Lane `v2drapedsrc` (Opus, brief pack), HECA closing build; the other
  frames dry.

## Tool: frames

| `tools/harness/frames.py` | THE FRAMES REGISTRY (owner 2026-09-13): `register --icao KCLT --kind capture|rebake|patch|graded|mesh --path P --base SHA --lane L [--note]`, `list [ICAO] [--kind K]`, `latest ICAO --kind K` (newest EXISTING entry; a vanished path prints `[MISSING]` and is never served). Append-only JSONL at `docs/frames.jsonl` (merge-friendly across lane branches). A lane registers its capture / rebake plan / closing products at the end so the next lane does not hunt scratchpads. Twin in `Ortho4XP/tests/test_docq.py`. |

## Registered frames: LGAV

(none registered)

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

