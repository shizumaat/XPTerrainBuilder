# Brief pack — lane `v2roadtags`

Base: main `352c3761` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§45 (9): the road feed keeps layer/cutting/covered/embankment

## The brief

# THE BRIEF — spec §45 (9): the road feed keeps OSM's depth witnesses

`Ortho4XP/src/O4_Vector_Map.py:48 ROADS_TAGS_OF_INTEREST = ["bridge", "tunnel", "width", "lanes"]` drops `layer`,
`cutting`, `covered`, `embankment` at download for every tile (scout `channelscout` §1a; the airports feed keeps
["all"] at :853). Owner 2026-09-15: "Bump the schema now" — keep the four tags for every FUTURE road-feed download;
existing tiles refresh only under an explicit `--refresh-data osm_layers` (the owner's act).

# THE FIX (one mechanism)
1. Add `layer`, `cutting`, `covered`, `embankment` to `ROADS_TAGS_OF_INTEREST` (and to the node-tag list only if the
   nodes carry them — they do not; leave `ROAD_NODE_TAGS_OF_INTEREST`). Bump `ROAD_CACHE_TAG_SCHEMA` (:59, today
   "2026-07-16") to "2026-09-15" and read the comment above it for what a bump means (a stale-schema feed is
   REFUSED/re-downloaded only under the explicit refresh — verify that the harness's `missing_shared_artifacts`
   names the `osm_layers` scope for a schema-stale road feed and does NOT download inside a build; if a build would
   silently re-download, that is a defect to name, not to fix here).
2. Twin: the tag list carries the four; the schema string changed; the reader (`tags_of_interest=` at :798) passes
   them through into the cached feed record (a fixture way with `cutting=yes layer=-1` survives the parse).
3. Grep every reader of the road feed's tag dict in `src/` and `auto_patch_v2/` for a hard-coded 4-key assumption
   (a `len(tags) == 4`, a positional tuple); list what you found in the commit message.

# BARS
- No downloads, no `--refresh-data`, no builds, no writes to `/Users/noah/XPTerrainBuilderData`. The suite from
  Ortho4XP/: `venv/bin/python -m pytest tests/auto_patch_v2 tests/test_harness.py -q` + the vector-map tests you find
  (`grep -rl ROADS_TAGS_OF_INTEREST tests`). Do not touch `O4_Airport_Elevation_Insets.py` (lane v2insetneg) or the
  planar/constraints tree (lane v2channel).

# CLOSING
The diff (tiny), the twin, the reader census, the suite by FAILED lines, the commit sha on `claude/v2roadtags`.
The session merges.

## Files

Yours: `Ortho4XP/src/O4_Vector_Map.py`
Other lanes' (do not touch): `Ortho4XP/src/O4_Airport_Elevation_Insets.py`

## Spec (design-surface) §45

## §45 THE OPEN CHANNEL — a road/rail corridor under a STATED CROSSING keeps its own floor through the field (owner 2026-09-15; RULINGS 2026-09-15i; Fable 2026-09-15; scout `channelscout`) — lane `v2channel`

**THE PATTERN (owner 2026-09-15).** "A below-grade road/rail channel cut through the
center of the airport that needs to be handled like an open tunnel" — LGAV (Attiki
Odos + Proastiakos rail between the runways), KPHX (E Sky Harbor Blvd under the
terminal taxiway bridges; never completed), KDFW (International Parkway between the
terminal horseshoes). One class, three WITNESS PROFILES (scout `channelscout`,
report in the session scratchpad; every number cited there):

| | LGAV | KDFW | KPHX |
|---|---|---|---|
| channel below grade | ~12 m (pack walls `Trench_03.obj` VT y −12.67…+5.73) | **8.6–9.9 m measured in the 1 m 3DEP DTM** at six bridges; banks ≈ 1:4; floor 170.9→173.3 over 2,790 m (0.09 %) | not measurable: 30 m Copernicus, flat to 0.1 m (the 3DEP fetch failed on a TNM 504, RULINGS 15i) |
| DEM sees it | no | yes | no |
| pack models walls/floor | **yes** (`Trench_0x.obj`; a 4,077 × 149 m plate roofed 6 % = the decks) | no (network-only roads pack; 0 objects) | no (28 placements, none) |
| OSM road carries depth | no | no | `tunnel=building_passage` ×6 under the bridges |
| OSM crossing `bridge=yes` + `layer` | 1 taxiway (`-379`) | **6 taxiway ways** A/B/Z/Y (layer 1–2, spans 84–106 m) | **2 taxiway ways** (layer 3, 148 m span, 87 m apart) |
| apt.dat pavement HOLE with paved NECKS | not read | **2,518 m corridor hole, exactly 4 necks 29.1 / 29.9 / 30.3 / 35.0 m** | unpaved corridor, **2 necks 23.0 / 22.4 m, 58 m apart** (Global reads them 42 / 64 m) |
| the engine today | 5 `tunnel_trench` faces (3,885 m²) + 1 basin; every Trench object refused (basin "shell rises 4.46 m above the ground"; sunken road "roofed 6 %"; tunnel object "roofed along its axis"; LAW C "law off") | not built on v2 (last build 2026-08-15 v1: `BandInversionError` 650 nodes) | §34 (5) bored 4 ways, then **all 8 mouths refused "against building pad building16"**: the airfield is paved FLAT at 342.2–342.9 m across a 147 m road crossing |

The one thing the three share: **the CROSSING is witnessed and the CHANNEL is not.**
The road feed keeps four tags (`bridge`, `tunnel`, `width`, `lanes`); the airports
feed keeps every tag. The mouth-centric tunnel model (one ramp climbing to the DEM
from each mouth, wall crest = DEM, RULINGS 09-03b) cannot express a road that never
climbs inside the field, and the DEM-relative gates of the basin / sunken-road /
tunnel-object passes refuse exactly the objects that model it.

**THE LAW (the owner's four answers, RULINGS 15i, in bold).**

(1) **IDENTIFICATION — "A deck states a crossing."** A channel crossing is stated by
ANY ONE of: (a) an aeroway way of §34 (5)'s taxied set (`taxiway`, `runway`, `apron`
mapped as a bridge) carrying `bridge=yes` over a road/rail way; (b) a PAVED NECK of
the apt.dat airside pavement union across an UNPAVED CORRIDOR that a road/rail way
follows (the hole's two edges are the corridor edges, the neck is the deck and its
plan width the deck width — KDFW 4 necks, KPHX 2); (c) the pack's wall/floor objects
along the way (the 05k-1 authority: seat = floor, plate = crest, hull = footprint).
Each witness is recorded on the record by name. The road/rail ways sharing the
corridor — both carriageways, the frontage roads, the rail — within
`[channel] merge_m` (= `dual_carriageway_max_separation_m`, 40) form ONE channel; the
corridor width is the hole's (b), else the pack walls' (c), else the lidar bank toes,
else the carriageways ⊕ `lane_width_m`. A crossing inside a channel is NEVER a bore
with mouths: §45 (6).

(2) **THE RECORD.** `Channel` beside `Tunnel` in `model/structures.py` (data only):
`ways`, `axis` (the merged centreline through the field; `s` from the field entry),
`profile` (`(s, z)` stations, the floor), `half_width(s)`, `decks` (`Deck` records:
`s0 < s1`, the neck ring, `datum = "design"`), `walls` (per side: `shape ∈ {face,
lidar, bank}`, the crest reference), `ends` (the two stations where the corridor
leaves the airside pavement union ⊕ `mouth_standoff_m`; beyond them the road law §37
governs and the floor rejoins the road's own profile at ≤ `ramp_max_grade`),
`witnesses`. The generator and the verifier read the record, never re-derive it.

(3) **THE FLOOR DATUM — precedence, then "Cut the road down."** (i) pack floor plates
along the axis (05k-1; LGAV); (ii) a CREDIBLE lidar inset (the inset's own
`lidar_credible` class; the DTM floor at each station; KDFW); (iii) neither: under
each deck the floor is the deck top − `bridge.clearance_m` (5.1 m, the existing bore
datum), and between decks the road's own longitudinal law (§37) clamped ≤ that datum
and ≤ `ramp_max_grade` — two decks closer than 2 × clearance / `ramp_max_grade` (KPHX,
58 m) keep the floor down between them. The datum source is on the record and in the
report; a lidar refresh (`--refresh-data dem`, the owner's act) moves a site from
(iii) to (ii) with no law change.

(4) **THE DECK IS AIRSIDE.** The neck's faces keep their airside role and law — the
taxiway surface runs across at the airside design surface; §34 (5)'s deck read is the
NECK itself (the "cell ≤ 4 × carriageway" test yields to a neck witness). Under the
deck the road is a BORE under cover: not emitted, the covering surface keeps its own
law (09-03b), `deck_z_on_faces` answers the deck, the existing `tunnel_deck_clearance`
family judges the soffit.

(5) **THE WALL CREST IS THE DESIGN SURFACE; the shape is "Witness first, 1:2
default."** `[tunnel] crest` gains the value `"design"`, used by channels: the crest at
each wall station is the solved surface of the governed cell at the corridor edge (the
airside pavement, or the adjacent-ground row) — never `DEM(x, y)`, which at LGAV stands
2–4 m under the real rim. Bores keep `"dem"` (no change to any existing tunnel). Shape:
where a pack wall face stands, the bank hides behind it at the identity spacing (§24
(1), near-vertical at the face); where the inset is credible lidar, the lidar bank
between crest and floor is KEPT (clamped monotone crest→floor); otherwise `[channel]
bank_slope = 0.5` (1:2) from crest to floor. The bank is emitted as the channel's own
faces (`retaining_wall` at a face, the bank's role otherwise); a heightfield cannot be
vertical and does not pretend to be.

(6) **NO MOUTH INSIDE THE FIELD.** A channel has no mouths at its decks: the
`mouth_standoff_m` field test, the approach-corridor / runway-lateral-band cockpit
tests (§29) and the "the mouth stands against building pad" refusal
(`ramp_crosses_pad`) are MOUTH rules for bores and are not applied to a channel's
decks (KPHX's eight refusals vanish by construction — `building16`, Terminal 4's
pad, abuts the corridor and takes the crest as its edge level, §20). The channel's
ends (2) lie outside the pavement union; §37 resumes there.

(7) **THE DEM IS NOT A WITNESS AGAINST A CHANNEL.** Inside an identified corridor the
ground reference of the object gates — `contact_band_m`, `rim_protrusion_max_fraction`,
the "buried" test, `authored_depth_min_m`, the sunken road's `roof_min_fraction` — is
the crest of (5), not the DEM; a wall/floor object standing along the axis is the
channel's witness (1)(c) and is never a basin seed, a sunken road, a tunnel-object
corridor or a door well (LGAV's 60 Trench refusals become one channel). Where the DEM
DOES see the cut (KDFW) it is the floor witness (3)(ii) and the bank witness (5); the
mesh never fills a witnessed cut and never digs an unwitnessed one wider than (1)'s
corridor.

(8) **EMISSION AND THE MESH.** Floor faces: `tunnel_trench` (already a `FLOOR_ROLE`);
walls: `retaining_wall` / the bank; decks: unchanged airside faces. The road ribbons
under a deck are the bore's (`O4_Vector_Map` deck-pinned ways); between decks the
ribbon follows the channel floor (§37 (8)'s cross-section on the floor). The flat-site
region EXCLUDES the corridor — a channel is never flattened. Emittable in a
heightfield: at every (x, y) exactly one of floor / bank / deck.

(9) **THE WITNESSES OSM CANNOT CARRY — "Bump the schema now."** `ROADS_TAGS_OF_INTEREST`
gains `layer`, `cutting`, `covered`, `embankment` and `ROAD_CACHE_TAG_SCHEMA` is bumped
(lane `v2roadtags`, separate, one commit); a tile's road feed re-downloads ONLY under
`--refresh-data osm_layers` (the owner's act) — until then the feed is as cached.
`cutting=yes` or `layer < 0` on a road/rail way crossing the airside pavement union is
then a fourth identification witness (1)(d), with the (3)(iii) depth.

### §45.1 CONSUMER CENSUS (owner RULINGS 2026-08-30l) — every pass that reads the corridor geometry, ruled BEFORE any edit; the lane confirms each row by grep and records any row it finds missing before editing

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `planar/structures.build_structures` (bores, mouths, tunnels) | OSM `tunnel` ways, crossings | EDIT: derive the `Channel` records (1)–(2) FIRST; a way inside a channel corridor is the channel's, never a bore seed; existing bores untouched (twin (e)). |
| C2 | `planar/structure_underpass` (§34 (5)) | `bridge=yes` aeroways, the 4× cell test | EDIT: the neck (1)(b) is the deck; a crossing that identifies a channel hands its deck to C1's record and mints no mouths (6). |
| C3 | `planar/structure_deck` / `model.Deck` | deck datum `dem` / `deck_top` | EDIT: datum `"design"` (4); `deck_z_on_faces` unchanged. |
| C4 | `planar/structure_approach` (§29 mouth field / cockpit tests), `ramp_crosses_pad`, `mouth_standoff_m` | mouths | UNAFFECTED for bores; NOT APPLIED to channel decks (6). |
| C5 | `planar/basins` (§24) + `basin_witness` | below-grade objects, the DEM under them | EDIT: inside a corridor the reference is the crest (7); a wall/floor object along the axis is a (1)(c) witness, not a seed. OTHH's 10 basins, LEMD's T4S unchanged (dry replays). |
| C6 | sunken roads (Law B) / door wells (Law A) in `planar/door_ramps` etc. | roofed plates, sills | EDIT (7): objects along a channel axis excluded from these passes by the channel's corridor; otherwise UNAFFECTED. |
| C7 | `planar/object_corridor` (05k-1 tunnel wall objects) | wall skirts, crest plates | EDIT: wall objects along a channel feed (1)(c)/(5), never a tunnel-object corridor; OTHH's object corridors unchanged. |
| C8 | `planar/wall_corridor_ramps` (LAW C, `law/airports.toml`) | kerb-wall pairs | UNAFFECTED (off everywhere but OTHH). |
| C9 | `planar/terrain_edge` (§19) | rim roads, crests | MEASURE: a channel crest is a terrain edge for the adjacent ground beside it; state whether §19's derivation already reads a structure edge; edit only if it does not. |
| C10 | `planar/zones`, `planar/shapes` | zone bands, shapes | UNAFFECTED (the corridor is not a zone; a deck stays in its shape). |
| C11 | `constraints/structures.structures()` (ramp/wall/deck rows), `wall_faces_of`, `ramp_faces_of` | `Tunnel` records | EDIT: channel rows — floor stations from (3), crest rows from (5) (`"design"` reads the governed cell's variable, not a constant), deck rows as today. |
| C12 | `constraints` road law §37 (6)–(10) | the road's profile through the field | EDIT: the channel's ways inside the ends take the channel floor as their profile; beyond the ends unchanged; the ramp cap is the join at each end. |
| C13 | `constraints/flat_site` (`FlatVerdict.region`) | pavement ∪ boundary ⊕ margin | EDIT: minus the corridor (8). |
| C14 | `verify/structures` (`tunnel_mouth_canonical`, `tunnel_deck_clearance`, `wall_in_runway_strip`, `basin_floor_at_declaration`) | the sidecar's structure shapes | EDIT: `tunnel_mouth_canonical` not judged on channels; `tunnel_deck_clearance` applies; NEW `channel_floor_at_declaration` (the floor equals the record's profile ± 0.01) and `channel_crest_at_edge` (crest = the adjacent cell's emitted level ± 0.01), registered in `LAW_FAMILIES` (the harness twin fails otherwise). |
| C15 | `emit/graded` roles (`FLOOR_ROLES`, `VOID_ROLE`) | roles | UNAFFECTED (roles exist); the bank role named by the lane if a new one is needed (prefer none). |
| C16 | the object stage (§16e decks, carried bodies, pads: LGAV `TowerTerm_Aera-Train*`/`Platform*` station objects in the trench; KPHX `building16`) | the design surface, structure rims | MEASURE on the replays: the station objects sit on the channel floor (their own seats), the T4 pad's edge takes the crest; edit only what the measurement names. |
| C17 | `O4_Vector_Map` / `O4_Vector_Utils` deck-pinned ways; `O4_Mesh_Utils` road ribbons, patch rings | the levelled road network | MEASURE: the ribbons under a deck at the bore datum, between decks on the floor; the mesh under a deck IS the deck (8). |
| C18 | the DSF road network under the deck | `tunnel`/layer rendering | UNAFFECTED (existing bore law). |
| C19 | the tile seam (§38), the Swift app | — | UNAFFECTED. |

### §45.2 Twins (synthetic, `tests/auto_patch_v2/test_v2channel.py`; `test_model.py` keeps `model/structures.py` data-only)

(a) a hole-and-neck fixture (apt.dat pavement with an unpaved corridor and two paved necks, a road way along it, no DEM relief): one channel, two decks at the airside surface, floor = deck top − 5.1 m, bank 1:2, no mouths, no `tunnel_mouth_canonical` rows; (b) the same with a 9 m lidar cut: floor = the DTM floor, bank = the DTM bank, decks unchanged; (c) pack wall/floor objects along the axis: floor = seat, crest = the adjacent cell's solved level, no basin seed, no sunken road, no tunnel-object corridor; (d) two decks 58 m apart: the floor stays at the datum between them; (e) the existing bore fixtures (a `tunnel=yes` way with two mouths) produce byte-identical `Tunnel` records; (f) beyond an end the road rejoins its §37 profile at ≤ `ramp_max_grade`; (g) the flat-site region excludes the corridor; (h) `LAW_FAMILIES` carries the two new families (harness twin).

### §45.3 Closing test

The structure replay (`python -m auto_patch_v2.planar ICAO --stage structures`, ~25 s) on LGAV, KDFW and KPHX BEFORE and AFTER, each record and refusal quoted (KPHX on the owner's 30 m frame today; after his `--refresh-data dem` the same replay must move KPHX from (3)(iii) to (3)(ii) with no code change). ONE build: **KDFW** (the lidar + the hole + six bridges; its last build was v1's 2026-08-15 `BandInversionError`, so the v2 baseline is itself a measurement — quote the refusal if the harness refuses cold data and stop). Bars: LGAV — the 5 `tunnel_trench` faces become the whole corridor (~4 km × ~100 m, one channel, `Trench_0x` as witnesses, zero Trench refusals); KPHX — the two necks at the airside surface with the road 5.1 m under them, the eight refusals gone; KDFW — four necks at the taxiway grade, the corridor floor at the lidar (170.9–173.3), the median fill kept, no fill in the cut; OTHH / LEMD / HECA / KCLT / CYXY / SPJC structure replays byte-identical in their `Tunnel` / `Basin` records (dry, no build). The owner reads LGAV's trench and KDFW in the sim; that read is the acceptance.

## RULINGS

## 2026-09-15i OWNER: the OPEN CHANNEL class (LGAV / KPHX / KDFW) — four intent answers; spec §45 written; lanes `v2channel`, `v2roadtags`

Owner 2026-09-15 (the LGAV read): "LGAV also has a similar pattern to
KPHX where there's a below grade road/rail channel cut through the center
of the airport that needs to be handled like an open tunnel." … "KPHX was
never completed, I haven't tested it in a long time, but it is a similar
pattern we need to be able to identify and model. KDFW also." Scout
`channelscout` (brief c2c96419) measured the three side by side — LGAV
(pack walls only, 30 m DEM blind), KDFW (8.6–9.9 m in 1 m lidar, six
`bridge=yes` taxiways, a 2,518 m apt.dat pavement hole with exactly four
paved necks 29–35 m), KPHX (`tunnel=building_passage` ×6, two `bridge=yes
layer=3` taxiways, two necks 23 m / 58 m apart; 30 m DEM; 1.0.340 paves
the crossing FLAT at 342.2–342.9 m because all eight mouths were refused
"against building pad building16") — and one feed fact: the road feed
drops `layer`/`cutting`/`covered`/`embankment` at download. Four
questions put with the data; the answers:
* Class rule → **"A deck states a crossing (Recommended)"** — a
  `bridge=yes` taxied aeroway over a road/rail way, or a paved neck across
  an unpaved corridor in the apt.dat pavement, IS a channel crossing; the
  depth comes from whichever witness exists (pack walls, credible lidar),
  else the clearance under the deck. KPHX is in.
* No-witness rule → **"Cut the road down (Recommended)"** — deck top −
  `bridge.clearance_m` (5.1 m) under the deck, the road's own grade beyond;
  the deck stays on the airside surface; the owner refreshes KPHX's 1 m
  3DEP (`--refresh-data dem --warm-insets KPHX`) and the lidar then
  supplies the real depth.
* Wall shape → **"Witness first, 1:2 default (Recommended)"** — a pack
  wall hides the bank behind it, credible lidar keeps its bank, otherwise
  1:2; the crest is the airside DESIGN SURFACE at the edge, never the DEM.
* Feed schema → **"Bump the schema now (Recommended)"** — keep
  `layer`/`cutting`/`covered`/`embankment` for every future road-feed
  download; existing tiles refresh only under `--refresh-data osm_layers`.
Spec §45 (nine clauses, §45.1 census of 19 consumers ruled before any
edit, §45.2 eight twins, §45.3 the three structure replays + ONE KDFW
build). Also recorded on the KPHX side: the 3DEP fetch failed on a USGS
TNM 504; the +33-112 tile keeps no negative and retries, the +33-113 tile
recorded `USGS3DEP = "no-coverage"` — a FALSE durable negative the app
never re-probes (TNM now lists four 1 m AZ_MaricopaPinal_2020 products);
lane `v2insetneg` attributes and fixes the writer (brief a9bf45fa).

## Tool: build_airport

| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo; guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. It also refuses a DEGRADATION THE ENGINE SWALLOWED (2026-08-07): `auto_patch.elevation._load_airport_dem` runs production's whole DEM prep inside one `except Exception`, so a write the shared-repo guard blocked became a WARN line, `dem_inset_provenance: null` and a build that exited 0 on 18.5 k nodes against production's 34-36 k (measured at HECA, `tmp/sliver_attrib`). Two independent detectors close it — a write the guard blocked during a build that nevertheless returned, and a laylane carrying no DEM provenance at all — and either refuses BEFORE the patch is written, so a DEM-less `.osm` never lands where a census would find it. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. The mod-cache redirect is also handed to v2's own loader (`inputs.mod_cache_root`), which `planar.__main__.default_inputs` cannot do for itself — it reads no environment by design, so before 2026-09-13 the pack-dump FRESHNESS guard (`airport/load.py:289`) judged the SHARED root and refused every KCLT / HECA v2 build and `explain` (RULINGS 2026-09-13q, "chip"); the build now reads and derives its DSF text dumps in the same lane-local overlay every other derived cache lands in. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. |

| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |

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

