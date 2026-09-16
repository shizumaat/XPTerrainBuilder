# Brief pack — lane `v2insetmanifest`

Base: main `1c9eb80c` · generated 2026-09-16 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§45 (18): the inset manifest reader falls back to the inset's own sidecar

## The brief

# §45 (18) — the inset manifest reader (engine side; independent of the channel lane)

DEFECT (RULINGS 15bm (15)(a), measured by lane v2channel on the KDFW build of 2026-09-15): the tile's
`inset_provenance` entry for KDFW reads `"native_resolution_m": null` with NO `resolution_m` key (every one of the
55 N32W098 sidecars written 2026-08-15; LEMD's/LGAV's newer writer carries the key), while the inset's own sidecar
`Elevation_data/+30-100/N32W098_airport_insets/KDFW_usgs3dep.json` says `"resolution_m": 1.0`. `ProductionDem.
source_pixel_m` (`auto_patch_v2/airport/dem_production.py`) reads only those two keys → `(None, 'base_tier')` →
`_source_class` → `('coarse', None, 'base_tier')` → `_lidar_credible` False → the flat-site detector and every
consumer treat a 1 m lidar frame as coarse (the engine's own line: `[flat-site] KDFW: not_flat — … DEM
coarse[base_tier]`).

FIX (one derivation): `source_pixel_m` takes `native_resolution_m`, else `resolution_m`, else the inset's OWN
sidecar (`<inset>.json` beside the tif the provenance entry names — `resolution_m` / `native_resolution_m`), else
`None` as today; log ONE line when the fallback fired (which key, which file). The WRITER (find where
`inset_provenance` entries are minted — `O4_Airport_Elevation_Insets` / the composer) stamps BOTH keys on every new
entry. Twins: a 08-15-shaped manifest (null + missing key) with a sidecar → 1.0 and `lidar_credible`; a manifest
with the key → unchanged; no sidecar → None. Consumer census by grep: every reader of `source_pixel_m` /
`_source_class` / `lidar_credible` (flat_site, channel (3)(ii), the DEM provenance report) — list them; none should
need an edit. No builds, no fetches, no shared-repo writes; the KDFW manifest on disk is NOT edited (the reader fix
makes it moot). Suite from Ortho4XP/: `venv/bin/python -m pytest tests/auto_patch_v2 tests/test_harness.py -q`
by FAILED lines; commit on `claude/v2insetmanifest`; the session merges.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/dem_production.py`, `Ortho4XP/src/O4_Airport_Elevation_Insets.py`

## Spec (design-surface) §45

## §45 THE OPEN CHANNEL — a road/rail corridor under a STATED CROSSING keeps its own floor through the field (owner 2026-09-15; RULINGS 2026-09-15p; Fable 2026-09-15; scout `channelscout`) — lane `v2channel`

**THE PATTERN (owner 2026-09-15).** "A below-grade road/rail channel cut through the
center of the airport that needs to be handled like an open tunnel" — LGAV (Attiki
Odos + Proastiakos rail between the runways), KPHX (E Sky Harbor Blvd under the
terminal taxiway bridges; never completed), KDFW (International Parkway between the
terminal horseshoes). One class, three WITNESS PROFILES (scout `channelscout`,
report in the session scratchpad; every number cited there):

| | LGAV | KDFW | KPHX |
|---|---|---|---|
| channel below grade | ~12 m (pack walls `Trench_03.obj` VT y −12.67…+5.73) | **8.6–9.9 m measured in the 1 m 3DEP DTM** at six bridges; banks ≈ 1:4; floor 170.9→173.3 over 2,790 m (0.09 %) | not measurable: 30 m Copernicus, flat to 0.1 m (the 3DEP fetch failed on a TNM 504, RULINGS 15p) |
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

**THE LAW (the owner's four answers, RULINGS 15p, in bold).**

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

(9) **THE WITNESSES OSM CANNOT CARRY — "Bump the schema now."** (owner 15p) `ROADS_TAGS_OF_INTEREST`
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

### §45 (10)–(12) AMENDED after lane `v2channel` round 1 (Fable 2026-09-15; RULINGS 2026-09-15s)

Round 1 (branch `claude/v2channel` 399d7ecb) measured LGAV only: KDFW refused on the
COLD neighbour tile N32W097 (its pack reaches into it), KPHX on a stale pack dump
(`+33-113.dsf.anchor_bak` newer than every cached text dump) — both are the owner's
`--refresh-data` acts (osm_layers + dem for +32-097; airport_mod_cache for KPHX). At
LGAV the pass found two channels, neither the trench: `channel:2` (ways −7021 −4017
−2914 −1343, witnesses bridge + pack, floor 63.43 from "5 placements") and
`channel:0` (way −4003, neck only, cut down 5.1 m); the `Trench_0x` family did not
fire as a witness, the 75 tunnel-object refusals stand, and LGAV's two 20 m²
covered pits were refused as channel witnesses. The lane also found §45 (1)'s width
rule wrong at the one measured site and reported it instead of deciding it. RULED:

(10) **THE HOLE IS A CROSSING WITNESS, NOT A WIDTH.** At KDFW the apt.dat hole is
2,518 × ~1,150 m — the whole gap between the terminal horseshoes, groundside roads
and garages included — while the 1 m DTM measures the cut 84–106 m wall to wall.
§45 (1)'s "the hole's two edges are the corridor edges" is DELETED. The hole and its
necks state that a crossing exists and where the decks are; the corridor WIDTH takes
its own precedence: (i) the pack's wall objects along the axis (LGAV: the outer faces
of `Trench_0x`); (ii) credible lidar — the bank toes on the axis normal (KDFW); (iii)
the carriageways ⊕ `lane_width_m`, with (5)'s bank beyond; all capped by `[channel]
corridor_max_half_width_m` (120 m — the widest bridge span measured is 148 m across).
The lane's implementation of (iii) + the cap stands; (i) and (ii) are round 2.

(11) **A CHANNEL IS ONE CORRIDOR, NOT A TRANSITIVE CHAIN.** Ways merge into a channel
only while the merged group's spread across the axis stays under
`corridor_max_half_width_m`; union-find over "within `merge_m`" with no diameter bound
chained `channel:2` 404.7 m off its axis. §45 (7)'s exclusion applies ONLY to objects
whose below-grade footprint lies INSIDE the corridor of (10) and reaches
`object_min_depth_m` under the crest; a pit beside the corridor keeps its basin
(LGAV's `basin:2`/`basin:3` return).

(12) **THE LGAV BAR IS THE TRENCH.** The pack witness (1)(c) must read the `Trench_0x`
family: `Trench_03.obj` (VT y −12.67…+5.73, 7,012 vertices), `Trench_06.obj` (the
4,077 × 149 m plate roofed 6 % — its roofed pieces ARE the decks, (4)), `Trench_01/07/
08.obj` (the wall bands LAW C saw as 16/20/8-band candidates). Round 2 attributes WHY
they did not fire in round 1 (the below-grade-footprint read, the `object_min_depth_m`
gate, the axis they are tested against — all placed at the pack origin 37.936563,
23.940627 with the geometry 2 km long) before changing anything, then meets the bar:
ONE channel along the motorway + rail through the field (entry/exit where the corridor
leaves the airside pavement union), floor from the Trench floors (3)(i), width from
the Trench walls (10)(i), decks = the roofed pieces + the `-379` TWY H bridge, zero
Trench refusals in the basin / sunken-road / tunnel-object passes, tunnels 8 → 8
elsewhere. `channel:0` (way −4003) is named with its coordinates and its crossing
pavement, or refused with the reason. The KDFW build and the KPHX replay stay the
closing tests, run AFTER the owner's data acts and AFTER the concurrent session's
four structure lanes merge (rebase first).

### §45 (13) A CHANNEL NEVER TAKES A MODELLED CROSSING (Fable 2026-09-15; RULINGS 2026-09-15aa) — lane `v2channel` round 4

Round 3's six dry replays (base main 46b219d8 vs the branch) showed the channel pass
claiming crossings the engine already models: KCLT taxiway U's four bores
(`tunnel:-14074@0..3`, §34 (5)'s canonical underpass) became a bridge-witness channel;
LEMD's F-6 service roads and five more bores, and OTHH's `tunnel west 2/3.obj` object
corridors, lost their ways to neck-witness channels; LEMD's `basin:0` then fell to the
channel's own cells. RULED, as PRECEDENCE at the channel's admission (one site,
`planar/channel.identify_channels`):

(a) **A bridge-only witness is §34 (5)'s underpass, not a channel.** A crossing
witnessed by an aeroway `bridge=yes` way ALONE — no neck, no pack wall/floor object, no
credible lidar — keeps the existing bore-with-mouths model. §45 (1)(a) is a witness only
in COMPANY (LGAV: bridge + pack).

(b) **A way already claimed is never a channel's.** A way that a tunnel-object corridor
(05k-1, `tunnel_objects.read_corridors`) or an OSM `tunnel=yes` bore (`build_structures`)
claims is excluded from every channel candidate; the channel is the model for crossings
the engine could NOT otherwise model. A pack-wall or lidar witness does not override
this: at LGAV the trench ways carry no `tunnel` tag and no object corridor, so nothing
competes.

(c) **A depth witness or two necks.** With (a) and (b), a channel needs a pack or lidar
witness, or a neck witness with ≥ `min_decks_without_depth` (2) decks (§45 (12) ratified).

BAR: the six dry replays byte-identical in `Tunnel` / `Basin` records AND in
`replaced_ways` (OTHH's provenance field included); LGAV unchanged from round 2 once
main's `shell_corridor` crash (v2objcut's, RULINGS 15aa) is fixed; KDFW and KPHX by
their witnesses (neck + lidar; neck ×2) after the owner's refreshes.

### §45 (13)(d) A BASIN'S OWN SHELL IS NEVER A CHANNEL'S WALL (Fable 2026-09-15; RULINGS 2026-09-15ac) — lane `v2channel` round 5

Round 4 (90708ba1): OTHH / HECA / KCLT / CYXY / SPJC byte-identical, LGAV's one channel
unchanged on the current main (`tunnels 11` on both arms), LEMD's tunnels identical
(51 → 51) — and LEMD's `basin:0` (T4S, §24's owner-accepted basin) lost: `channel:5`
(way −5989, neck + pack, ONE deck) took `dsf:obj7` / `dsf:obj10` — two of the basin's
three members `Ground-FSX-LEMD36/37/85` — as its §45 (1)(c) wall witnesses, and the
basin then fell to "overlaps a tunnel structure". Basins are built AFTER channels, so
(13)(b)'s "already claimed" set does not exist for objects. RULED: the object side is
decided by the object's own KIND, at one derivation site the basin pass already owns —
`airport/basin_witness.basin_member_ids(airport, law)`: a placement in that set is a pit
shell (its rim tops out at grade, §24 (1)) and is NEVER a channel's (1)(c) witness. A
channel left without a depth witness then faces (13)(c) (LEMD's `channel:5`: neck + one
deck → refused). BAR: the six dry replays byte-identical in `Tunnel` AND `Basin` records
(LEMD basins 1 → 1); LGAV unchanged; the suite; then the merge.

### §45 (13)(d) AMENDED — a member of a BUILT basin, basins before channels (Fable 2026-09-15; RULINGS 2026-09-15aw) — lane `v2channel` round 6

Round 5 (0531ab07) implemented (13)(d) with `basin_witness.basin_member_ids`, which is
basin rule 1's CANDIDATE set, not "a basin's own shell": at LEMD it removed `channel:5`'s
witnesses (`Ground-FSX-LEMD36/37/85`, members of the BUILT `basin:0`) — the ruling's own
site, met exactly — and at LGAV it removed `Trench_07.obj` / `Trench_08.obj` (candidates
that never build a basin: LGAV's built basins on both arms are the two 20 m² Fence1 pits)
and the trench channel fell to (13)(a). The lane reported the conflict instead of
narrowing it. RULED: (13)(d) keys on membership of a BUILT basin. ORDER: the basin pass
runs FIRST on the unfiltered objects (it needs nothing from channels), channels second
with the built basins' member ids as the (13)(d) exclusion, and §45 (7)/(11)'s "inside
the corridor" exclusion becomes a POST-FILTER on built basins whose region lies inside a
channel corridor of (10) and whose members are that channel's witnesses (expected empty
at LGAV and LEMD; reported by name when it fires). The `claimed=` / `channels=` intake
of `build_basins` stays for the post-filter's site. BAR (both): LGAV ONE channel (ways
−1343/−7021/−2914/−4017, floor 66.47 from `Trench_07`, half-width 62.8 from the Trench
walls, 4 decks, basins 2, tunnels = base); LEMD basins 1 → 1, tunnels identical,
`channel:5` refused; the seven dry replays `ALL IDENTICAL` (`tools/structure_replay_diff.py`,
promoted in round 5). Also RULED from round 5's findings: `Corridor.bore_ways` has no
producer — (13)(b)'s object-corridor half is inert until 05k-1's reader publishes its
claimed ways (owed to the tunnel-object line, not this lane); the KDFW / KPHX replays
refuse on NEIGHBOUR tiles' superseded road layers (the loader reads the 3 × 3
neighbourhood: KDFW +33-098, KPHX +33-112/+33-113) — the owner's refresh act per tile.

### §45 (14) A NOTCH IS A CORRIDOR TOO; the KDFW datum and floor rows are ATTRIBUTED before the merge (Fable 2026-09-15; RULINGS 2026-09-15bk) — lane `v2channel` round 7

Round 6 (da91d7d8) met the LGAV and LEMD bars under (13)(d) as amended (basins decide
first, only where a channel took a pack witness; §45 (7)/(11) a post-filter on a built
basin, firing nowhere) and five replays identical. Two closing tests were not clean:

(14) **THE NOTCH.** At KPHX the two decks are read (`-206`, `-111`), the six E Sky Harbor
ways are road candidates (`tunnel=building_passage` is rightly not a bore), and every one
reads `necks = 0`: the corridor is a NOTCH — an indentation of the airside pavement union
from its outer edge — not an interior ring, and (1)(b)'s `_hole_region` sees interior
holes only. RULED: the unpaved corridor of (1)(b) is the complement of the airside
pavement union INSIDE THE FIELD — the field being the union's boundary polygon (§44's
row-130 boundary where the pack has one, else the union's convex hull ⊕ `mouth_standoff_m`)
— so a notch and a hole are one class; the neck test is unchanged (an unpaved flank of
`corridor_min_length_m` on both sides of a paved neck, along the way). Bar: KPHX ONE
channel through the two necks (23.0 / 22.4 m, 58 m apart), floor by (3)(ii) if the lidar
is credible else (3)(iii); OTHH / HECA / KCLT / CYXY / LEMD / LGAV replays unchanged from
round 6.

(15) **THE KDFW DATUM AND THE FLOOR ROWS ARE ATTRIBUTED, NOT SHIPPED.** The KDFW build
(rc 0, 355 s, shared repo UNCHANGED) emitted four channels, all on (3)(iii) — the
engine's own `[flat-site] KDFW: … DEM coarse[base_tier]` says the 1 m 3DEP inset
(`N32W098_airport_insets/KDFW_usgs3dep.tif`, present since 08-15) was NOT the frame the
replay read — and `channel_floor_at_declaration` fired 378 rows, worst 12.626 m at
32.8849810, −97.0398638: the solved surface does not hold the declared floor. Mechanism
before fix (memory `mechanism-before-fix`): (a) WHY is the KDFW inset not credible /
not read — the inset tier chosen, `lidar_credible`'s predicate, the index record's
version (15ay), quoted from the run; (b) WHICH rows fight the floor — the prime suspect
is C12, `airport/road_profile._osm_levelled` core-levelling the channel's road inside
the field (owed since round 1, deferred by the owner to "after the reads"; a measured
12.6 m conflict is not a read, it is a defect): prove it by `v2_solve_replay --probe-site
32.8849810,-97.0398638` on the KDFW capture with the road rows named, then fix C12 as
§45 (2)/(8) state (the channel's ways inside the ends take the channel floor as their
profile) if that is the mechanism, or name the other. Bar: `channel_floor_at_
declaration` 0 rows at KDFW on the lidar datum (after the owner's `--refresh-data dem
--warm-insets KDFW` if (a) says the inset must be re-cut), the four necks at the taxiway
grade, the corridor floor at the lidar 170.9–173.3, the median fill kept.

### §45 (16)–(18) THE ENDS, THE SEPARATION, THE MANIFEST (Fable 2026-09-16; RULINGS 2026-09-15bo) — lane `v2channel` round 8, lane `v2insetmanifest`

Round 7's checkpoint (b0a86405, RULINGS 15bm) attributed three things; each is ruled here.

(16) **A CHANNEL ENDS AT ITS OUTERMOST CROSSINGS.** §45 (2)'s "where the corridor leaves
the airside pavement union ⊕ standoff" was written for a hole; a notch has no such exit
and (14) wired as written ran corridors to the field boundary (KPHX 5,750 m, HECA
14,562 m, CYXY 5,646 m). RULED: the corridor's two ENDS are its outermost crossings
(decks by (1)(a)/(b)) each extended by ONE deck width along the axis — and where a depth
witness ((1)(c) pack walls, (3)(ii) lidar) reaches further along the way, to the end of
that witness. Beyond the ends §37 governs as before. A candidate with fewer than two
crossings and no depth witness is refused by (13)(c) unchanged. With the ends so bounded
(14) is WIRED (`field=` at the one call site). And the CLAIMED SET of (13)(b) includes the
§34 (5) SYNTHESISED underpass bores (the four at KCLT taxiway U) — every way a bore of
any provenance names — so a channel never takes what §34 (5) already built. Bar: the
seven replays byte-identical (KCLT tunnels 23, LGAV channels 1, LEMD 3 → the round-6
count, HECA/CYXY no new channel), KPHX ONE channel through its two necks bounded by
them (~150 m of corridor, not 5,750), CYXY's planar twins green.

(17) **THE FLOOR AND THE AIRSIDE SURFACE NEVER SHARE A VERTEX.** The KDFW floor rows
(378, worst 12.626 m) are `pavement_ceiling` on vertices shared between the channel floor
and airside cells (v14070: roles cross_connector / retaining_wall / tunnel_trench, 169.40
vs 182.28 over ~23 m) — an infeasible set by construction, not a solver failure. RULED:
the channel emits its own WALL BAND between the floor and every airside or adjacent-
ground cell, exactly as a bore does (`[tunnel] wall_gap_m` + `wall_band_width_m`: the
floor's ring stands `wall_gap_m` inside the corridor edge, the band's outer ring IS the
corridor edge and carries the crest rows of (5)); the floor faces share vertices only
with the band, never with a pavement cell; a deck's faces are airside and meet the band's
crest, not the floor. And `verify/channel._declared_at` reads the floor's declaration
the way the floor was STATED: the profile z(s) at the vertex's axis station, over the
floor faces only (never the band). Bar: `channel_floor_at_declaration` 0 rows and
`channel_crest_at_edge` ≤ 0.01 m at KDFW; the hard set feasible (0 violated hard rows
in the channel's families).

(18) **THE INSET MANIFEST READER FALLS BACK TO THE INSET'S OWN SIDECAR.** KDFW's 1 m
3DEP inset is composed and present, yet the tile's `inset_provenance` entry carries
`native_resolution_m: null` and no `resolution_m` (every N32W098 sidecar of 08-15; the
newer writer stamps it), so `ProductionDem.source_pixel_m` reads `(None, 'base_tier')`,
`_source_class` says `coarse`, `_lidar_credible` is False and every channel falls to
(3)(iii). RULED (lane `v2insetmanifest`, engine side, independent of the channel):
the reader takes `native_resolution_m`, else `resolution_m`, else the inset's OWN
`<inset>.json` `resolution_m` / `native_resolution_m` (the file the provenance entry
names), else `None` as today — one derivation, twinned on a 08-15-shaped manifest;
and the WRITER stamps both keys on every new entry. No re-warm needed; the owner's
KDFW read then stands on the lidar datum with no law change.

## RULINGS

## 2026-09-15bo RESUME 2026-09-16 (PM line): §45 (16)–(18) RULED from the round-7 checkpoint — a channel ends at its outermost crossings (synthesised bores join the claimed set), the floor never shares a vertex with airside (its own wall band, as a bore), the inset manifest reader falls back to the inset's sidecar — lanes `v2channel` r8 (fresh) and `v2insetmanifest`

Resumed on main 756785ca (clean; no locks; no builds; the peer's
shutdown record 15bt read: app 1.0.341 in the owner's hands, VHHH
regression known, v2shellwall r2 checkpointed). From 15bm: (16) ENDS —
the outermost crossings ⊕ one deck width, extended by a depth witness;
(14) wired with them; (13)(b)'s claimed set includes §34 (5) synthesised
bores; bars: seven replays identical, KPHX ONE bounded channel, CYXY
twins green. (17) SEPARATION — the channel emits a bore-style wall band
between floor and airside (`wall_gap_m` + `wall_band_width_m`); floor
faces never share a vertex with a pavement cell; verify reads the
profile at the station over floor faces only; bars: 0 floor rows, crest
≤ 0.01 m, hard set feasible at KDFW. (18) MANIFEST — `source_pixel_m`
falls back to `resolution_m`, then the inset's own sidecar; the writer
stamps both keys; twin on a 08-15-shaped manifest; the owner's KDFW read
then stands on lidar with no re-warm. Round 8 is a FRESH lane (the
round-7 agent died with the session) on the branch at b0a86405.

## 2026-09-15bm v2channel ROUND 7 CHECKPOINT (b0a86405, shutdown): §45 (14) written but NOT wired (it regresses everywhere — a notch corridor needs ENDS at its crossings); the KDFW datum is a MANIFEST defect (08-15 sidecars lack `native_resolution_m`); C12 REFUTED — the floor rows are `pavement_ceiling` on vertices SHARED between the channel floor and airside cells

(14) `channel_geometry._field_region` + `_hole_region(union, field)` exist,
twinned, call site `field=None`: wired in, KPHX 0 → 1 channel but KCLT
tunnels 23 → 19 (four §34 (5) SYNTHESISED underpass bores that (13)(b)'s
claimed set does not cover), LGAV channels 1 → 4, LEMD 3 → 6, HECA a
14,562 m channel, CYXY 5,646 m, KPHX 5,750 m with a (3)(iii) floor
332.76–563.14 m, CYXY planar twins red (6,856 vs 6,660 vertices). §45
(2)'s ends do not bound a notch corridor — OWNER/Fable ruling needed: a
corridor ENDS at its outermost crossings (plus one deck-width), never at
the field boundary; and (13)(b)'s claimed set must include synthesised
underpass bores. (15)(a) the 1 m inset IS composed (`insets=…,KDFW:
USGS3DEP`) but the tile's `inset_provenance` entry reads `native_
resolution_m: null` with no `resolution_m` (all 55 N32W098 sidecars of
08-15; LEMD/LGAV's newer writer carries it) → `ProductionDem.source_
pixel_m` → `coarse/base_tier` → `_lidar_credible` False. Fix at the
manifest READER (fall back to the inset's own sidecar `resolution_m`) or
the owner re-warms KDFW if today's writer stamps it — a lane, not a
refresh. (15)(b) C12 REFUTED (`road_fit_vertices: 0`; `--why-vertex
14070`: the only binding row is the channel's own pin, held to 0.000):
the fight is `pavement_ceiling` (`pavement_max_grade`) on vertices
SHARED between the channel floor and airside cells (v14070 roles
cross_connector/retaining_wall/tunnel_trench: 169.40 vs 182.28 over
~23 m = 13.41 m; 131 of 482 violated hard rows an infeasible set) — the
floor and the airside surface must NOT share vertices (the wall band /
weld spacing between them, as bores have); and `verify/channel._
declared_at` compares a 2-D floor region to a 1-D axis profile. Suite
1729/0; LGAV byte-identical to round 6. KDFW capture + solved pickle and
the KPHX (14)-wired arm registered in frames. NEXT (fresh lane after
resume): rule the ends + the synthesised-bore claims, wire (14), the
floor/airside vertex separation, the manifest reader; seven replays;
ONE KDFW build; merge; app 1.0.342.
15bt addendum 2 (the lane's own checkpoint report, verbatim resume points): revert 07cb9794 (the (2) cover subtraction: `structure_service.cover_region`, `Corridor.cover`, the `covered=` path, the two twin classes); KEEP r1's walled trench (4382c4a7 + 3ba0a4d1) = (3)(a). (3)(b) — the exclusion of surface elements over an object-decked trench — lives where airside faces and rows are MADE, not in structure_geometry: `planar/structures.build_structures` (the knife / `new_cells`) and the row sites `constraints/taxi.taxi_centerlines` (walks `planar.breaklines` kind `taxi_centerline` — the generator in the attributed chain) + `constraints/taxi.taxi_chain` (`routes()`); reuse `planar/structure_underpass.py` + `structure_deck.emit_decks` / `deck_witness_for` (they already exclude decked pavement from a trench) — do not fork. Consumer census first. Cheap arm: the registered VHHH capture `scratchpad/v2shellwall/cap/VHHH.pkl` (+ `.solved.pkl`) reproduces the regression and carries the `--why-at` chain; the dry structures dump publishes `trench_ll`/`footprint_ll`/`rim_ll`. OTHH reads 0 signature-B cuts; the OTHH/LEMD byte-identity base arm (`scratchpad/v2shellwall/basesrc`, `dry_base.py`) is set up, not completed. Note the scratchpad is session-local (/private/tmp/claude-501/…/3fc455a9…) — the next session re-registers or re-cuts those arms.

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

