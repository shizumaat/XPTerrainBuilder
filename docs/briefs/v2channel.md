# Brief pack — lane `v2channel`

Base: main `352c3761` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§45 THE OPEN CHANNEL: LGAV / KDFW / KPHX

## The brief

# THE BRIEF — implement spec §45 THE OPEN CHANNEL exactly (the section, its 19-row consumer census, the 8 twins and the closing test are in this pack verbatim). The scout's evidence report is beside this pack: `docs/briefs/channelscout-report.md` — read it whole; every site coordinate, way id, neck width and lidar depth you need is there with its source path.

# ORDER OF WORK (synthetic-first; the BUILD ECONOMY is law)
1. Confirm the §45.1 census by grep before editing anything (record any consumer row the table missed in your
   report; do not edit it silently). `tools/blast.py <file>` before each edit.
2. `Channel` record (§45 (2)) in `model/structures.py` — data only (`test_model.py`).
3. Identification (§45 (1)) in the planar stage: the hole-and-neck read of the apt.dat airside pavement union along
   road/rail ways is the FIRST witness to implement (it is free at all three airports); then `bridge=yes` (C2's
   existing read), then the pack wall/floor objects (C5/C7's existing readers, redirected).
4. The floor datum precedence (§45 (3)), the crest `"design"` (§45 (5)), no mouths (§45 (6)), the DEM-not-a-witness
   rule (§45 (7)), the rows (C11–C13), the verify families (C14, registered in `LAW_FAMILIES`).
5. Twins §45.2 (a)–(h). Then the three structure replays (§45.3) before/after — `python -m auto_patch_v2.planar ICAO
   --out DIR --stage structures` from Ortho4XP/ with PYTHONPATH=src; KDFW's data is warm (1 m 3DEP inset, mod-cache
   dump `+32-098.dsf.c8f5c313.text`); KPHX is on the owner's 30 m frame (his refresh is his act; do not fetch).
   If a replay refuses cold data, QUOTE the refusal and stop that arm.
6. ONE build: KDFW through `tools/harness/build_airport.py KDFW` (patch-only). Its last build was v1's 2026-08-15
   `BandInversionError` — a v2 baseline is a measurement in itself. Register the report (`frames.py register`).

# FACTS (from the scout, so you do not re-measure them)
- KDFW decks: OSM `-276` A, `-280` B, `-21`/`-1595` Z, `-23`/`-1593` Y (`aeroway=taxiway bridge=yes`, layer 1–2);
  apt.dat necks 29.1 / 29.9 / 30.3 / 35.0 m (Global) at lat 32.88488…32.91027, lon ≈ −97.041; the corridor hole is
  ring69 (Global) / ring80 (pack), 2,518 m × ~1,150 m; lidar floor 170.87 / 170.20 / 172.80 / 173.27 m under rims
  ~177–183 m; banks ≈ 1:4; the 121 m median between Z and Y is REAL fill (182.7 m) — keep it.
- KPHX: `-111` (ref T) and `-206` `bridge=yes layer=3`; road segments `-4248 -15974 -23949 -3936 -3937 -23804`
  `tunnel=building_passage`; necks 23.0 / 22.4 m (pack) at lon −112.00470 / −112.00383, 58 m apart; today's report
  `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+33-113/KPHX/KPHX.report.json` (bores 5, mouths 10, ALL refused
  "against building pad building16", decks 0, cells_cut 0).
- LGAV: pack origin 37.936563, 23.940627; `Trench_00…08.obj` (Trench_03 VT y −12.67…+5.73; Trench_06 plate 4,077 ×
  149 m roofed 6 %); 2026-09-14 report `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+37+023/LGAV/LGAV.report.json`;
  NOTE main now carries §44 (LGAV borrows 63 Global pavements) — the hole-and-neck read at LGAV stands on the
  BORROWED pavement (`Airport.pavements` after the borrow). OSM crossing `-379` TWY H `bridge=yes layer=1`.
- The mouth refusal string "the mouth stands against building pad …" is minted in the tunnel pass (grep the
  composed pieces: "stands against"); its law key is `[tunnel] ramp_crosses_pad`.
- `[tunnel] crest = "dem"` today (law/structures.toml :6–50); `bridge.clearance_m = 5.1`; `ramp_max_grade = 0.080`;
  `dual_carriageway_max_separation_m = 40`; `emit/graded.FLOOR_ROLES` already has `tunnel_trench`.

# BARS
- Existing bores (OTHH, LEMD, HECA, KCLT, CYXY, SPJC) byte-identical in their `Tunnel`/`Basin` records — prove by the
  structure replays (dry; no builds). No five-airport sweep. No `--refresh-data`. No fetch. No edits to
  `O4_Vector_Map.py` (lane `v2roadtags` owns the feed schema) or `O4_Airport_Elevation_Insets.py` (lane `v2insetneg`).
- Files under the 1,000-line guideline: a new planar module (`planar/channel.py`) + a new constraints module if
  `constraints/structures.py` would pass the cap; `test_model.py` keeps the model data-only.
- Every number you quote carries its source; a refusal is quoted verbatim.

# CLOSING (quote verbatim)
The three structure replays before/after (records + refusals), the KDFW build line (rc, wall, body_sha, shared repo
UNCHANGED), `faces_by_role` and census for KDFW, the suite `venv/bin/python -m pytest tests/auto_patch_v2
tests/test_harness.py -q` by FAILED lines, the commit sha on `claude/v2channel`, the frames lines. The session merges.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/model/structures.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_deck.py`, `Ortho4XP/src/auto_patch_v2/planar/basins.py`, `Ortho4XP/src/auto_patch_v2/planar/object_corridor.py`, `Ortho4XP/src/auto_patch_v2/constraints/structures.py`, `Ortho4XP/src/auto_patch_v2/verify/structures.py`, `Ortho4XP/src/auto_patch_v2/law/structures.toml`
Other lanes' (do not touch): `Ortho4XP/src/O4_Vector_Map.py`, `Ortho4XP/src/O4_Airport_Elevation_Insets.py`

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

## Spec (design-surface) §34 (5)

### §34 (5) NARROWED — NO UNDERPASS UNDER A JETWAY; §29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; RULINGS 2026-09-13bm) — lane `v2spjc`

SPJC (owner 1.0.327, 13bi): `is_aeroway_bridge` admitted 63 `aeroway=jet_bridge`
footways and bored 86 apron roads under 49–127 m "decks" read off the apron
cell; the −641/−2525 trunk tunnel's south mouths were dropped 168 / 191 m off
the field while 192 m beside runway 16R/34L at mid-length.

- **§34 (5):** an underpass is bored only under an aeroway a taxiing aircraft
  uses (`aeroway in {taxiway, runway}`, `apron` where mapped as a bridge);
  never `jet_bridge` / `parking_position`, never `highway=footway`.
  `_deck_half_width` refuses a cell wider than 4× the way's carriageway and
  falls back to the carriageway; `is_bridge_way` excludes `jet_bridge` so no
  jetway mints a terrain deck.
7. **THE RUNWAY LATERAL BAND (§29).** The field region is the cover ⊕
   `mouth_standoff_m` ∪ the approach corridors ∪ each runway's axis ⊕
   `runway_view_half_width_m` (design: 250 m) — one derivation shared with
   the cockpit block. A bore with one mouth built has its sibling admitted
   under the same test. `mouth_standoff_m` stays 150.

BARS: SPJC underpasses 19 → taxiway-only (named); tunnels at the owner's four
points 0; the four jetway `bridge_deck:` faces gone; −641/−2525 south mouths
built at −12.0202431, −77.129278; LEMD −6028's mouth by the same rule (dry);
LEMD F-6 and KCLT taxiway U unchanged; ONE SPJC build; suite twice.

**WHAT LANDED.**  `planar/cluster.py` (NEW) derives the clusters from the
pack partition at LOAD, beside the groups (`pipeline/build.py`), and they
travel on `Airport.clusters` because `constraints` may not import `planar`
(the layering twin).  `constraints/cluster_pad.py` (NEW, beside
`pad_frontage_gs.py` and for the same 1,000-line reason) holds both rows:
`plane_groups` — the groups a pad PLANE is priced over, a cluster's faces
as ONE entry, read by `pads._pad_rows` (`pad_flats` + the hard 1 % ceiling)
and by `pads.pad_frontage_level` — and `cluster_apron_level`, the reach.
The derivation itself is `airport.placement_family.plan_clusters`, the same
`_clusters` law §16g binds the objects with, at the same
`[placement] footprint_touch_m`.

**THE FRAME.**  ONE KCLT build through the harness, tag
`v2clusterpadKCLT2`, rc 0, **477.2 s**, status feasible, `body_sha
9f056cce3dc3`, `[harness] shared repo UNCHANGED`.  It earned NO ledger
entry: the code tree moved between key time and store time (the §16g (4)
edit), so the artifact ledger refused the store — correctly.  The "before"
column is the registered `v2familyKCLTframe` graded document (base
`864e7577`), which is NOT a matched arm: the base moved a full day of main
between them.  **A matched design base arm was NOT built** and every design
number below carries that confound.

| bar | before (`v2familyKCLTframe` graded) | after (`v2clusterpadKCLT2`) |
|---|---|---|
| the cluster, named | — | `unit:31#0`, 19 members (`paredes_*`, `techos_*`, `suelos_interiores_charlotte`, `vidrios_*`), footprint union **378,982 m²**, on `building80` + `building91`; and `unit:30#0`, 17 members, 15,334 m² |
| the CLUSTER PAD's plane | `building80` 221.15 … 222.32 (spread 1.17), `building91` **217.89** — 4.43 m below it | `building80` 221.68 … 223.14, `building91` **222.27 … 222.28**; union spread **4.43 → 1.46 m** — MET in kind: the pad inside the terminal no longer sits 3.6 m under the terminal |
| `building80`'s own flatness | spread 1.17 m | **1.46 m** — WORSE by 0.29 m, and named: the plate now carries `building91`'s frontage and the reach beside its own |
| the apron within `cluster_apron_reach_m` (60 m) | 70 vertices, median \|apron − pad\| **0.26 m**, max 1.16, **0** within 0.05 m | 90 vertices, median **0.16 m**, max 1.77, **38 of 90 within 0.05 m** — the bar (≤ 0.05 m inside the reach) is MET for 38 and NOT for the rest; the residue is the feasibility clause and the taxi-catchment exclusion |
| the taxiway family | — | NOT measurable without a matched base build; what IS exact is that no taxi- or runway-family vertex is ever a FOLLOWER of a reach row, and no apron vertex nearer such a face than the pad is in the population at all (both twinned) |
| solve | — | feasible, 593 active-set rounds, 93/238,729 hard rows violated (max 0.0877 m), `pad_flat` verify rows 47, total 420.13 s |

**THE TAXI-CATCHMENT CLAUSE, AND WHAT MEASURED IT.**  On the twin fixture
the reach lifted an apron and the taxiway welded to it followed by **2.20 m**
through the apron's own no-step law — the reach's rows never touched a taxi
vertex.  Striking the band's own vertices is therefore not enough, and an
apron vertex nearer a taxi- or runway-family face than the cluster pad is
now excluded outright.  On the fixture that arm read **3.51 m** instead of
2.20 — WORSE — but the fixture's taxi face carries no datum of its own and
swings metres between arms, so it measures the fixture and not the law.  The
clause is KEPT because it can only ever SHRINK what the reach touches, and
it is named here as UNMEASURED at an airport.

### §34 (5) NARROWED — NO UNDERPASS UNDER A JETWAY; §29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; RULINGS 2026-09-13bm) — lane `v2spjc`

SPJC (owner 1.0.327, 13bi): `is_aeroway_bridge` admitted 63 `aeroway=jet_bridge`
footways and bored 86 apron roads under 49–127 m "decks" read off the apron
cell; the −641/−2525 trunk tunnel's south mouths were dropped 168 / 191 m off
the field while 192 m beside runway 16R/34L at mid-length.

- **§34 (5):** an underpass is bored only under an aeroway a taxiing aircraft
  uses (`aeroway in {taxiway, runway}`, `apron` where mapped as a bridge);
  never `jet_bridge` / `parking_position`, never `highway=footway`.
  `_deck_half_width` refuses a cell wider than 4× the way's carriageway and
  falls back to the carriageway; `is_bridge_way` excludes `jet_bridge` so no
  jetway mints a terrain deck.
7. **THE RUNWAY LATERAL BAND (§29).** The field region is the cover ⊕
   `mouth_standoff_m` ∪ the approach corridors ∪ each runway's axis ⊕
   `runway_view_half_width_m` (design: 250 m) — one derivation shared with
   the cockpit block. A bore with one mouth built has its sibling admitted
   under the same test. `mouth_standoff_m` stays 150.

BARS: SPJC underpasses 19 → taxiway-only (named); tunnels at the owner's four
points 0; the four jetway `bridge_deck:` faces gone; −641/−2525 south mouths
built at −12.0202431, −77.129278; LEMD −6028's mouth by the same rule (dry);
LEMD F-6 and KCLT taxiway U unchanged; ONE SPJC build; suite twice.

**WHAT LANDED.**  `planar/cluster.py` (NEW) derives the clusters from the
pack partition at LOAD, beside the groups (`pipeline/build.py`), and they
travel on `Airport.clusters` because `constraints` may not import `planar`
(the layering twin).  `constraints/cluster_pad.py` (NEW, beside
`pad_frontage_gs.py` and for the same 1,000-line reason) holds both rows:
`plane_groups` — the groups a pad PLANE is priced over, a cluster's faces
as ONE entry, read by `pads._pad_rows` (`pad_flats` + the hard 1 % ceiling)
and by `pads.pad_frontage_level` — and `cluster_apron_level`, the reach.
The derivation itself is `airport.placement_family.plan_clusters`, the same
`_clusters` law §16g binds the objects with, at the same
`[placement] footprint_touch_m`.

**THE FRAME.**  ONE KCLT build through the harness, tag
`v2clusterpadKCLT2`, rc 0, **477.2 s**, status feasible, `body_sha
9f056cce3dc3`, `[harness] shared repo UNCHANGED`.  It earned NO ledger
entry: the code tree moved between key time and store time (the §16g (4)
edit), so the artifact ledger refused the store — correctly.  The "before"
column is the registered `v2familyKCLTframe` graded document (base
`864e7577`), which is NOT a matched arm: the base moved a full day of main
between them.  **A matched design base arm was NOT built** and every design
number below carries that confound.

| bar | before (`v2familyKCLTframe` graded) | after (`v2clusterpadKCLT2`) |
|---|---|---|
| the cluster, named | — | `unit:31#0`, 19 members (`paredes_*`, `techos_*`, `suelos_interiores_charlotte`, `vidrios_*`), footprint union **378,982 m²**, on `building80` + `building91`; and `unit:30#0`, 17 members, 15,334 m² |
| the CLUSTER PAD's plane | `building80` 221.15 … 222.32 (spread 1.17), `building91` **217.89** — 4.43 m below it | `building80` 221.68 … 223.14, `building91` **222.27 … 222.28**; union spread **4.43 → 1.46 m** — MET in kind: the pad inside the terminal no longer sits 3.6 m under the terminal |
| `building80`'s own flatness | spread 1.17 m | **1.46 m** — WORSE by 0.29 m, and named: the plate now carries `building91`'s frontage and the reach beside its own |
| the apron within `cluster_apron_reach_m` (60 m) | 70 vertices, median \|apron − pad\| **0.26 m**, max 1.16, **0** within 0.05 m | 90 vertices, median **0.16 m**, max 1.77, **38 of 90 within 0.05 m** — the bar (≤ 0.05 m inside the reach) is MET for 38 and NOT for the rest; the residue is the feasibility clause and the taxi-catchment exclusion |
| the taxiway family | — | NOT measurable without a matched base build; what IS exact is that no taxi- or runway-family vertex is ever a FOLLOWER of a reach row, and no apron vertex nearer such a face than the pad is in the population at all (both twinned) |
| solve | — | feasible, 593 active-set rounds, 93/238,729 hard rows violated (max 0.0877 m), `pad_flat` verify rows 47, total 420.13 s |

**THE TAXI-CATCHMENT CLAUSE, AND WHAT MEASURED IT.**  On the twin fixture
the reach lifted an apron and the taxiway welded to it followed by **2.20 m**
through the apron's own no-step law — the reach's rows never touched a taxi
vertex.  Striking the band's own vertices is therefore not enough, and an
apron vertex nearer a taxi- or runway-family face than the cluster pad is
now excluded outright.  On the fixture that arm read **3.51 m** instead of
2.20 — WORSE — but the fixture's taxi face carries no datum of its own and
swings metres between arms, so it measures the fixture and not the law.  The
clause is KEPT because it can only ever SHRINK what the reach touches, and
it is named here as UNMEASURED at an airport.

### §34 (5) (a), §24 (1) (a), §33 (2) (a), §33 (4)/§34.5 (6) AMENDED — FOUR DERIVATIONS FROM THE LEMD 1.0.336 READ (Fable 2026-09-14; RULINGS 2026-09-14bp) — lane `v2lemdstruct`

1. §34 (5) (a) THE UNDERPASS CLIP IS THE DECK CELL'S: the bored road is
   clipped to the deck cell's own footprint eroded by `wall_gap_m +
   wall_band_width_m + grid`; the centreline-symmetric ribbon only where no
   cell states the deck; `_deck_half_width` reads the same derivation.
2. §24 (1) (a) THE RIM IS THE WALL: a rim station with at-grade shell
   geometry within `footprint_close_m` snaps onto the shell's outer face;
   the region boundary stands only where no wall exists; `_rim_open`'s
   count becomes the derivation's own report (stations off the shell).
3. §33 (2) (a) THE PLATE MOUTH IS CLAMPED TO THE COVERED EXTENT: the mouth
   moves to the plate end or the bore way's end, whichever is nearer the
   mapped mouth along the axis; width takeover and the approach walk as
   before.
4. §33 (4) / §34.5 (6) AMENDED: a mapped bridge way's deck spans THE WAY
   (`ln.buffer(wd/2)` over its full length), the end equality at each
   mapped end (the governed cell within `deck_end_reach_m`); decks of
   parallel bridge ways sharing a crossing are one group — one transverse
   plane, no rim sliver.  §34.5 (6)'s refusal is withdrawn.
BARS (LEMD, ONE build): F-6 mouth within 3 m of 40.4609913,−3.5445335,
`pav157` uncut north of it; basin:0 stations beyond 2 m of the shell 58 →
≤ 11; the 40.4988 mouths within 3 m of 40.4980461,−3.5850118 and of the
segment 40.4960195,−3.585058 → 40.4960167,−3.5849289; the deck ends within
3 m of 40.4835967,−3.580923 / 40.4835412,−3.5799114, one plane across both
carriageways, the profile past the east end monotone (no notch), no rim
sliver; `road_cross_section` / `within_shape` on the approaches before →
after; airside 0; verify defects {}; five-frame dry: tunnels / basins /
plate mouths / decks before → after named.

## Spec (design-surface) §24

## §24 THE BASIN'S EDGE AND FLOOR (owner RULINGS 2026-09-11t) — lane `v2basinedge`

Owner, LEMD 1.0.315: "still a gap between the outer edge and the apron … the apron
elevation shape needs to be closer with less of a gap between the floor cutting
shape. The object also provides a floor … that should be visible instead of seeing
the terrain at the bottom of the basin."

1. **THE CUT HUGS THE WALL.** The basin's cut ring is the object's OUTER wall face at
   its top (the `basin_wall` ring of the floor witness's shell, read from the pack —
   not the OSM footprint, not a snap-out widening, not a buffer). The apron's rim
   vertices lie ON that ring at the rim level (§ rim_level: the rim IS the adjacent
   apron edge), so the pavement meets the wall top with no shelf outside it and no
   step down to it. Measured: horizontal distance from each rim vertex to the wall
   face ≤ `emit.weld_spacing_m` (1.0 m, the identity spacing); vertical step between
   the rim ring and the apron vertices it joins 0.00 m (materiality 0.01).
2. **THE FLOOR SITS UNDER THE OBJECT'S FLOOR.** The trench floor level = the object's
   floor-plate elevation (its authored y at the rim's zero, the 10bd depth) MINUS
   `[basin] floor_clearance_m` (new, default 0.5 m): the plate renders; the terrain
   is never seen through it. The basin's inner floor ring and every floor vertex
   take that level; the walls' bank between rim and floor is the object's wall
   (vertical in the object; the terrain bank is hidden behind it).
3. **Consumers**: the rim ring's derivation site (`planar/structures.py` basin /
   `basin_witness`), constraints `structures.rim_level` + the floor row, verify's
   basin family, `pad_level_report` leaders (a pad fronting the basin reads the rim),
   the placement anchor for a basin body (§6: a RIM point on the emitted ring). One
   table in the lane's report before any edit (08-30l).
4. **Measured first on the app's products** — `<Patches>/+40-010/+40-004/LEMD.graded.json`
   (T4S basin: rim ring vs the object's wall face, rim vs apron edge, floor vs plate) —
   then fixed, then LEMD once. Bars: (1) and (2) as stated; OTHH's Dewatering /
   tunnel basins unchanged by dry run; `> 3 m` unchanged.

**Measured** (lane `v2basinedge`, branch `claude/v2basinedge`; before = the app's
1.0.315 products, after = `LEMD_20260911T142115` `body_sha=0a6181fed68f`, rc 0,
360 s). T4S = `basin:0` (40.491701, −3.569256; members `Ground-FSX-LEMD36/37/85`),
the only basin LEMD admits:

| bar | before | after |
|---|---|---|
| (a) rim vertex → the object's outer wall face (≤ 1.0 m) | **+1.749 / +2.064 / +4.120 m, 56 of 56 OUTSIDE and over the bar** | **−0.251 / +0.010 / +0.264 m, 0 of 49 over** |
| rim ring area vs the shells' region | 28,971 m² over 27,557 m² (perimeter 705 vs 682 m) | 27,586 m² over 27,557 m² (682 vs 682 m) |
| (b) rim → apron vertical step (0.00, materiality 0.01) | 0.000 — all 71 rim vertices share their id with a ground face (23 apron, 51 pad) | 0.000 — all 59 do (14 apron, 47 pad) |
| (c) trench floor − the object's floor plate (−0.50 ± 0.01) | **+0.000 / +0.000 / +0.000 m** | **−0.510 / −0.500 / −0.500 m** |

Mechanism of (a): `planar/basins._rim` widened the region by whole grid steps until
it contained the floor (the plate ⊕ `floor_overlap_m`) and cleared it by the
stand-off; the T4S shell measures 0.00 m thick, so the loop ran to k = 4 = +2.0 m.
That is the owed `rim snap_out widening` item of RULINGS 08e deviation (2), now
closed: the rim is the region, and the stand-off comes out of the FLOOR
(`_floors_inside`, 1,066 m² trimmed at T4S).

OTHH dry run (planar replay of the new tree, no build): all **10** basins still
admitted, none refused; every rim vertex on its wall face (worst |0.494| m, 0 of
263 over the 1.0 m bar); the Dewatering pits' depths unchanged (13.142 m, the
04i/08d reading) and the drainage bowls' 3.816 / 4.201 m likewise, each now
+ 0.500 m of clearance. Basin verify families on the LEMD arm:
`basin_floor_declaration` 0, `basin_floor_at_declaration` 0, `structure_rim_gap` 0,
`wall_in_runway_strip` 0.

**DEVIATION REPORTED (§24 (1)), never decided by the lane.** A ZERO-THICKNESS
shell — LEMD's T4S, OTHH's drainage shells, and every synthetic box fixture —
cannot both keep the rim ON the wall face and give the floor its
`floor_overlap_m` outward past the plate: there is no wall thickness to spend.
The floor is therefore the plate TRIMMED to stand `rim_standoff` (0.5 m, the
identity spacing) inside the rim, which leaves a ≤ 0.5 m band of terrain inside
the wall line rising from the floor to the rim, its top standing up to the
clearance ABOVE the plate. The alternative is the shelf (1) exists to remove.

**NOT MEASURED by the lane**: `> 3 m` (the seat-feet census reads the object
stage, which needs the app's mesh) and a matched defect-gate control (the
1.0.315 products are a four-airport TILE build; a single-airport arm is a
different population, and a control build is a second build).

**MEASURED (lane `v2basinfoot`, 2026-09-13; branch `claude/v2basinfoot`, base
main `e5e04660`).** Before = the owner's 1.0.325 products (the four-airport TILE
build in the data repo: `Patches/+40-010/+40-004/LEMD.graded.json` +
`o4_v2_rebake_LEMD.json` + the copied patch); after = `LEMD --engine v2`
(`v2basinfoot3`, rc 0, 408 s, ledger `1c11f6fad3a2`, `body_sha 58a9ce7d3170`).

**(6) THE CONSUMER CENSUS, before any edit** — every pass that reads the basin
region / rim / floor, and what §24 (4)–(5) does to it:

| consumer | reads | ruling |
|---|---|---|
| `planar/basins.build_basins` | the region, the rim, the floors, the cut knife, the keep-outs | THE SINGLE DERIVATION SITE — both laws land here and nowhere else |
| `airport/obj8._witness` | the component's below-DEM clip (`FloorWitness.below`) | KEPT as rule 1's ADMISSION evidence; `outer` added beside it for the region |
| `constraints/structures.basins` | `faces_by_ref[floor_ref]` vertices, `wall_path`, `floor_below_rim_m` | EDITED: a floor vertex under a ramp corridor takes `deck − floor_clearance_m` (a senior pin); every other vertex keeps the 10ba relative row unchanged |
| `constraints/structures._rim_rows` / `rim_level` | the rim ring's vertices | UNCHANGED in form; the ring is a different (larger) ring, `rim_level` 11 design-target rows before and after |
| `planar/structures.py` `contact_band_m` reader (l. 352) | the LAW KNOB only, for tunnel-object wall bands | NO INTERACTION — it never reads the basin region |
| the pad cut (`cuts_pads`) | the knife vs `building` cells | UNCHANGED in form, and this is where the `building15` notch goes: the pad is now cut there (see below) |
| `building_pad.in_basin_sits_at_floor` | — | DEAD KNOB: declared in `law/structures.toml` + `law/model.py`, read by NO code (grepped). The pad is CUT, not lowered. Left alone, reported |
| `pipeline/build._plate_seats` | `Basin.ring` (the largest PLATE floor face) + `plate_y_m` | UNCHANGED: the ramp is a SEPARATE floor face (`basin_floor:0#1`), `ring` stays the plate's, so the witness's seat stations do not move onto the ramp |
| `pipeline/build._basin_polygon` | `b.region` (deck-signature evidence) | follows the larger region; LEMD deck families 0 before and after |
| `pipeline/publication.basin_facilities` | the record | EDITED: publishes `ramp_corridors` / `ramp_rings_ll` / `ramp_faces_ll` |
| `verify/structures.basin_floor_at_declaration` | the published depth vs every floor vertex | EDITED: under a corridor it expects `deck − clearance` (the SAME call, `model.structures.deck_z_on_faces`). Without this the law's own 42 pinned vertices report as violations — measured: 53 rows on the first arm |
| `verify/structures.basin_floor_declaration` / `structure_rim_gap` / `wall_in_runway_strip` | `solid_minimum_y_m` vs `body_depth_m`; rim-to-floor spacing; the strip | NO CHANGE: 0 / 0 / 0 before and after (the ramp floor is trimmed by the same `rim_standoff`) |
| `airport/basin_ring.py` (§14a arcs) | the EMITTED `basin_wall:0@k` ring from the graded doc | FOLLOWS AUTOMATICALLY, no edit: 6 arcs → 7, ring bar 0.19 → 0.18 m |
| `airport/placement_census` basin exemption | the plan's basin bodies | unchanged in form: basin carriers 24 → 25, exempt 20 → 20 |
| `tools/pad_level_report.py` | pads / refs in a solved pickle | no basin geometry of its own; reads whatever the pads became |
| harness `terrace_joints_ll` / `pad_relief` / `basin_floor_declaration` | the sidecar keys | `terrace_joints` 4 before and after, `basin_facilities` 1, `basin_floor_declaration` 0 |

**(4) THE RING IS THE SHELL'S OUTER FOOTPRINT.** Cause, reproduced on the
1.0.325 frame: `below` is `_clip_component` at ONE plane per component — the DEM
under the component's CENTROID, 593.00 for `Ground-FSX-LEMD85`, while the real
ground over the ramp runs 594.6 … 599.2. The road ramp is never above the DEM at
all (it lies 1.5 … 6.6 m under it its whole length); it leaves the REGION where it
climbs through 593.00, at **40.492259, −3.569411** — the exact closing point of
the below-clip, ~50 m short of the ramp's top.

| bar | before (1.0.325) | after |
|---|---|---|
| LEMD `basin:0` region | 27,557 m² | **28,345 m²** (+788: the notch) |
| rim ring | 59 nodes | **58 nodes**, Hausdorff **11.57 m** from the old ring |
| the notch at 40.4922455, −3.5695503 | `building/building15` z 598.36 … 598.48 | **`tunnel_trench/basin_floor:0` z 589.83 … 595.94** — the pad is cut, the ramp corridor is trench floor |
| §14a ring bar (`obj8_split_report --no-cut`, matched arms) | 0.19 m, 0 of 59 over 0.30 | **0.18 m, 0 of 58 over** |
| ring nodes the pit has NO WALL on (same instrument) | 3 (worst 1.11 m) | **3** (worst 1.31 m) |
| T4S tower cluster | `LEMDzaun`/`SWbaume` basin bodies on the rim, own-ground 7.59/7.57/7.55 m | **unchanged in kind** (7.71 m worst; the cluster stays on the rim) |
| OTHH, planar dry run, all 10 basins | — | **10 admitted, 41 refusals, rims moved (Hausdorff) 0.00 / 0.12 / 0.14 / 0.32 / 0.32 / 0.35 / 0.45 / 0.47 / 0.48 m — sub-grid, none over 0.48**; floor areas identical bar −15/−22 m² on the two Dewatering pits (rim re-snap) |

**(5) THE FLOOR FOLLOWS A RAMP.** The corridor is read off the shell's own
witness components: up-facing faces (`floor_plate_normal_y_min`) between the
floor and `R_est + contact_band_m`, joined in plan, admitted when the part SPANS
the pit (its own vertices reach within the band of both floor and rim) **and its
surface grade is drivable** — the area-weighted mean face slope, new law
`[basin] ramp_max_grade = 0.15`.

The grade test is not decoration: spanning alone admitted **three of OTHH
Drainage_01's banks (2,118 m², the pit's floor area 735 → 2,853 m²)**, because a
bowl's ring of banks climbs floor-to-rim like a ramp. Rise-over-plan-run does not
separate them either (that bank reads 3.61 m over 133.5 m = 0.03, a bowl
diameter apart); the SURFACE grade does: LEMD's ramp **0.09**, every OTHH bank
**0.20 … 0.29**. At 0.15 the LEMD ramp is the only deck either pack admits.

| bar | before | after |
|---|---|---|
| ramp corridors at LEMD `basin:0` | — | **1** (932 m² of floor, 36 deck faces; candidates refused: 2 m² × 2 "does not span", 101 m² "does not span", 2,043 m² `LEMD36` slab "does not span") |
| floor vertices on the ramp's profile | 0 | **42** (`basins.floor_ramp_vertices`) |
| emitted floor z vs `deck − floor_clearance_m` at every corridor vertex | — | **43 of 43 within 0.005 m** |
| the ramp deck vs the design surface under it | **−2.92 m worst over ~51 m (buried)** | **+0.50 m at every corridor floor vertex**; median +0.48 m over a 1 m grid inside the corridor |
| `basin_floor_at_declaration` | **5** | **4** |
| OTHH ramp corridors | — | **0 on all 10 basins** |

**Harness census (before = the 1.0.325 four-airport tile patch, after =
`v2basinfoot3`).** COCKPIT first: CRITICAL motion **2 → 3** (all three grade
BREAKS, worst 0.670 → 0.600 m, the same `strip_arc` site at 40.4625636,
−3.5525152 — nowhere near the basin), CRITICAL visual **0 → 0**. LAW-TRUE total
3,573 → 3,621; ADJUDICATED 1,143 → 1,172 (airside-for-acceptance 1,128 → 1,151);
`basin_floor_declaration` 0 → 0, `wall_in_runway_strip` 0 → 0.

**That census delta is NOT attributable to this change, and the lane says so.**
Two arms of THIS tree differing only in which deck faces the corridor publishes
(48 vs 42 pinned vertices) censused **1,089** and **1,172** adjudicated rows —
the LP's active set (`feasible`/"SET NOT SETTLED" vs `optimal`) moves more than
the basin does. The 1.0.325 arm is also a four-airport TILE build, a different
population from a single-airport arm (the same caveat §24 (1) recorded).

**NOT MET, with its cause named.** `_rim_open` read **57 of 69** open stations
before and **58 of 69** after (bar ≤ 5). The diagnostic's reference is
`at_grade_geometry`, whose linework is the shell clipped at ONE plane per
component — the very defect §24 (4) removed from the region. With LEMD's ground
running 593 … 599 across the pit and the plane at 592.00, the "at-grade line" is
a contour in the middle of the plate, not the wall top, so no ring can be close
to it. Fixing the rim diagnostic is a separate item and is OWED, not done here.

**NOT MEASURED by the lane.** The scout's `probe2.py` reading (11 of 59 ring
nodes 6.1–15.0 m from the nearest WRITTEN basin piece) needs
`o4_v2_placement_LEMD.json`, which only the app's write half produces; the
harness build entry stops at the patch, the graded doc and the rebake plan. The
engine's own §14a instrument (above, matched arms through `obj8_split_report`)
is what the lane could run, and it reads 3 → 3. A pack-geometry probe over the
nine basin resources' WALL faces reads the ring on the wall everywhere except
the new ramp stretch (nodes 15–20, 4.3 … 9.3 m), where the pack models a bare
deck and the mesh makes the trench's sides — which is the cut the owner asked
for. Also not measured: `> 3 m` seat feet against a matched control, and any
OTHH build (dry run only, as §24 (6) requires).

### §24 (4)–(6) The ring is the shell's OUTER footprint; the floor follows a ramp (Fable 2026-09-13; RULINGS 2026-09-13g) — lane `v2basinfoot`

Owner (13d item 2): the SE corner still gaps; the NW corner's cut must reach the
midpoint of the north edge so the modeled road ramp is visible rising to apron level.
Scout `v2lemd325b` on the 1.0.325 frame (ring `basin_wall:0@849`, 59 nodes): the gap
is HORIZONTAL — 11 of 59 ring nodes have no wall within 6–15 m (the engine's own
`_rim_open` reports "57 of 69 rim stations beyond 2.0 m of the shells' at-grade
geometry", diagnostic only); at node 1 the design drops 6.7 m one metre inside the ring
and the nearest pit wall tops out 4 m BELOW the apron edge; five `basin_floor_at_
declaration` rows. Cause: `planar/basins.py:356` builds the region from each solid
component's footprint clipped BELOW the local DEM (`obj8.py:765`), exterior only,
rim inset 0.00 (the shell reads 0.00 m thick) — not §24 (1)'s "OUTER wall face at its
top". The same clip drops the road ramp (`Ground-FSX-LEMD85__b2`: 100.5 m, 591.4 →
597.5, 6.1 % mean, reaching apron level at −3.56946 — 11 m from the owner's midpoint)
out of the region as it rises: a 51.9 × 11.0 m notch that the pad `building15` fills at
598.4, burying ~51 m of the ramp, worst 2.92 m; the floor is one depth below the
nearest rim vertex (`constraints/structures.py:588`), never a ramp profile.

4. **THE RING IS THE SHELL'S OUTER FOOTPRINT AT THE TOP OF ITS WALLS** — every
   component of the basin resource(s) incl. its ramp — never the below-DEM clip.
   Trims the SE overhang and keeps the ramp corridor inside the cut in one edit at
   the single derivation site (`basins.py` region + `_rim`).
5. **THE FLOOR FOLLOWS A RAMP**: floor vertices under a ramp corridor (a deck of the
   basin resource climbing from the floor to the rim) take the deck's authored
   elevation minus `floor_clearance_m` per station; elsewhere the one depth stands.
   Bar: deck − design ≥ 0 over the ramp's whole run (today −2.92 m worst); the 5
   declaration rows → 0.
6. **CONSUMER CENSUS at spec time (08-30l)** — one table before editing: the basin
   rows in `constraints/structures.py`, `planar/structures.py`'s `contact_band_m`
   reader, the pad cut (`cuts_pads`, `building_pad.in_basin_sits_at_floor` — the
   `building15` notch), verify's basin families, `pad_level_report`, `airport/
   basin_ring.py`'s arcs (§14a — the SE node-3 straddle resolves once nodes 0/1/4/5
   have wall within the band), the placement census's basin exemption. OTHH: its 10
   basins / 21 carriers have shells with real thickness (0.75–2.5 m) — the planar
   replay is dry-run BEFORE the edit and re-quoted after (rims moved, m); no OTHH
   build. Bars: SE corner wall base within 0.3 m of the ring at every walled node
   and unwalled nodes 11 → 0; the ramp visible (bar in (5)); harness census; ONE
   `--engine v2` LEMD build against the 1.0.325 base; twins; suite.

### §24 (7) THE FLOOR IS THE WHOLE ADMITTED REGION (owner RULINGS 2026-09-14n item 1; Fable 2026-09-14; RULINGS 2026-09-14p) — lane `v2othhfix`

Once a region is admitted as a pit, the trench floor covers the region minus
the rim stand-off; the witnessed plate DELIMITS NOTHING — it witnesses depth.
(a) The floor witness is read over the whole ADMITTED FAMILY: a sibling
placement whose deep horizontal plate lies inside an admitted region
contributes it even when its own shell never reaches grade (the
`buried_components` skip in `obj8.py` is a pit-SEED test and never
suppresses a plate inside another placement's pit); every skipped buried
component is NAMED in the report with its area and depth.  (b) Where no
plate lies under part of the region the floor still takes `floor_z`: a
rim-level island inside a pit is terrain standing inside the object's walls.
BARS (OTHH 1.0.332 frame): floor/region ≥ 0.95 on all ten basins (today
0.10–0.56; basin:6 879/4,330 m²); mesh stations inside basin:6's rim above
`solid_min_z` (−9.18) 270 of 393 → 0; LEMD basin:0 unchanged (97.4 %, the
control); ONE OTHH build.

### §24 (8) A BASIN'S RAMP CORRIDOR IS RE-NODED AT ITS STATIONS (Fable 2026-09-14; RULINGS 2026-09-14s) — lane `v2othhfix`

§24 (5)'s "the floor under a ramp corridor follows the deck per station"
has no vertices to land on: `constraints/structures.py` pins EXISTING
planar vertices only, so VHHH's `basin_floor:5#1` (2,794 m², 6.9 m of drop)
carried 4 interior vertices and a 42 % mouth step.  The basin pass re-nodes
the ramp corridor at `ramp_station_m` before emission (the structures pass's
stationed ramp is the model).  BAR: any basin ramp corridor ≥ 1 vertex per
`ramp_station_m` along its axis; the mouth grade within the ramp cap.

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

## 2026-09-05k — Owner RULED 05j-1 and 05j-2

* **05k-1 (tunnel wall objects).** The reading is confirmed: the placement seat is the tunnel FLOOR, the object's top plate is the wall CREST; the objects are the tunnel authority for shape, length and depth wherever one stands (OSM bores only where none does). Spec `docs/specs/auto-patch-v2/tunnel-wall-objects-spec.md`; lane `v2tunnelobj`.
* **05k-2 (flat-site datum).** Options (b) + (c): the flat datum (Z0, CIFP by default, pack seats or declared metres by table) is a LAW PREFERENCE the LP prices (`flat_datum`, below law, above seam), runway pins stay CIFP-absolute, and a `[declared]` table in `law/flat_site.toml` is the ONE declared register (the tile-cfg keys retire). Spec `docs/specs/auto-patch-v2/flat-site-datum-spec.md`; lane `v2flatsite`.

## 2026-09-03b — Owner ruling: TUNNEL WALL CREST = DEM ALL THE WAY ROUND THE RAMP

* **THE WALL STAYS AT DEM (owner sim read of 1.0.275, OTHH).** "The wall should stay at DEM all the way around the tunnel ramp allowing the tunnel to descend to its full depth"; the mouth wall node stands the bore datum (`BRIDGE_ROAD_CLEARANCE_M` 5.1 m) above the ramp's mouth node; "no service road shape running around the outside of the tunnel wall". Spec `docs/specs/tunnel-wall-crest-dem-spec.md`; merged `7c0513cf` (lane/wallcrest). SUPERSEDES for wall crest bands: round-4 spec R5 / lead ruling 2026-08-10 (the transition law graded the crest DOWN to the ramp — the flat 4.00 m crest R5 called the defect IS the ruled surface), R16-2a's crest convergence, and `retaining_wall` in `groundside.TRANSITION_ROLES`. The §F1 station law and 2026-09-01c/e (foot retired, 0.6 m gap, one corridor-top value per station) STAND — the corridor-top value is the DEM.
* **MECHANISM (attributed, not reasoned):** the crest was derived twice — `bridges._CrestProfile` applied `transition_law_altitudes` toward the ramp at emit, and `finalize` → `apply_below_grade_transition` re-graded `retaining_wall` (and every plate outside the wall) toward the ramp again; the approach road's annulus remainder (a 1.8–5.1 m ribbon around the wall) shared the wall's outer-edge nodes and outranked it in `to_osm`. The 2026-08-30 "host WHOLE" clause had retired with the `tunnel_road` claim (08-31) and nothing replaced it.
* **LAW:** L1 crest = DEM by station (transition law DELETED from both emitters, 29f); L2 wall out of `TRANSITION_ROLES` — the wall is the discontinuity; L3 a ramp with a registered wall (`wall_band_owners`) is not a below-grade source for the R5 transition (unwalled shallow ramps and `tunnel_trench` unchanged); L4 service-road-family hosts are taken WHOLE alongside the run — partitioned at the ramp's far-end line, no width/area tolerance; `groundside_pavement` hosts keep 25e. Unmasked by L2: `finalize.deconflict_road_features` clipped wall pieces and kept misaligned altitudes (emit dropped them) — now NN-resamples.
* **MEASURED (OTHH closing build e936a0cb6ab2):** owner wall node −1.10 → 4.00 vs ramp −1.12 (5.12 m); ribbon −10051 gone; census law-true 1,620 → 1,528 (airside 1,202 = 1,202, groundside 282 → 190); acceptance wall_top_flat 5.1 → 3.45 (one 0.47 m² SW-fork crumb), ramp_wall_gap 23 → 23 (pre-existing SW fork-crumb class at 25.2540,51.6034 — owed), mouth_inventory 1 non-canonical → 1 (same SW fork site; wall R cover 0.15 → 0.97), actionable_sites 32 → 17. Twelve L4 host pieces removed (largest service_road #48 1,157 m² at the SW fork — owner eyeball owed).

## Tool: frames

| `tools/harness/frames.py` | THE FRAMES REGISTRY (owner 2026-09-13): `register --icao KCLT --kind capture|rebake|patch|graded|mesh --path P --base SHA --lane L [--note]`, `list [ICAO] [--kind K]`, `latest ICAO --kind K` (newest EXISTING entry; a vanished path prints `[MISSING]` and is never served). Append-only JSONL at `docs/frames.jsonl` (merge-friendly across lane branches). A lane registers its capture / rebake plan / closing products at the end so the next lane does not hunt scratchpads. Twin in `Ortho4XP/tests/test_docq.py`. |

## Registered frames: KDFW

(none registered)

## Registered frames: LGAV

LGAV  rebake   base 98c94f86   lane v2drapedbind     2026-09-15T07:48:42  /Users/noah/XPTerrainBuilderData/Patches/+30+020/+37+023/o4_v2_rebake_LGAV.json  — owner's LGAV tile build 2026-09-14 23:14 (engine 1.50.1785); obj8_split_report replays it in 8.2 s plan stage — the frame that raises the _draped_components AttributeError on main
LGAV  graded   base 98c94f86   lane v2drapedbind     2026-09-15T07:48:42  /Users/noah/XPTerrainBuilderData/Patches/+30+020/+37+023/LGAV.graded.json  — the design surface for the LGAV rebake replay above
LGAV  patch    base 8b8b2afc   lane v2pavborrow      2026-09-15T08:00:03  /tmp/harness/v2pavborrow.v2/LGAV.report.json  — 44 pavement borrow ON: 63 Global pavements + boundary borrowed (coverage 1.35 pct); patch /tmp/harness/v2pavborrow.osm body_sha 88db87c72b4c ledger aae37551fddd
LGAV  patch    base 8b8b2afc   lane v2pavborrow      2026-09-15T08:04:11  /tmp/harness/v2pavborrow2.v2/LGAV.report.json  — 44 pavement borrow ON (shipped code): 63 Global pavements + boundary borrowed, coverage 1.35 pct; patch /tmp/harness/v2pavborrow2.osm body_sha 88db87c72b4c ledger dc9a0182d26d

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

