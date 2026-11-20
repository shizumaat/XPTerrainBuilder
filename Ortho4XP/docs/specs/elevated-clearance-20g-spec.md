# 20g — Elevated pack structures keep their clearance over mapped roads and rails

Owner RULINGS 2026-11-20g (#2192 KMCO; KDFW sky bridges). Lane `lskyclear`, base
`claude/test-568` 43a0fbf60. Status: **CENSUS + ATTRIBUTION DONE; MECHANISM HELD FOR TWO
OWNER QUESTIONS (§5)** — the measured scale at both airports makes either remedy a large
visible change, and at KDFW the loss is a seating defect in a file another lane may hold.

Ruling (verbatim head, owner 2026-11-20T16:59Z): "When a pack has buildings connected by
elevated structures that cross mapped roads or rails ... we want to grade terrain and seat
buildings (where airside grading allows) so that they maintain enough elevation to have
minimum clearance over those roads and rails. If it's not possible, then the road or rail
needs a graded ramp under the object to ensure clearance."  RULED (1) the soffit keeps the
class minimum; (2) first by grading terrain and seating the connected buildings high enough,
as far as airside grade law allows; (3) otherwise the road/rail is lowered on a graded ramp
within road/rail grade law.

## §1 Consumer census (RULINGS 2026-08-30l) — every pass that reads an elevated structure over a road or rail

| # | Pass (module) | Reads | Decides | 20g bearing |
|---|---|---|---|---|
| 1 | Touch groups `airport/touch_graph`, `touch_seat` (16u/16v) | final bodies' part rings; connectors (footless bodies: roofs, sky bridges) join groups | a group with spread S ≤ 1 m seats at its LOWEST building vote, authored offsets kept | sets the zero every soffit of the group hangs from; KMCO main terminal: 145 bodies at 26.349, S 0.835 |
| 2 | Stacked deck `stacked_deck` (18h (2)) | a deck standing on walls | rides the walls' zero | none (rides) |
| 3 | Connector warp `connector_warp` + `deck_profile.warp_decks` (18h (3)) | a connector between two seats at different zeros | warped to meet both (shear ≤ 0.10) | a warped sky bridge's soffit varies along it: a crossing is read AFTER the warp |
| 4 | Split bar `split_bar.keep_whole` (19j) | final zeros, last | placement whole at one zero within 0.5 m | any 20g seat move must precede it |
| 5 | Tilt float `tilt_float` (18h (4)) | seat tilts | undone where a foot floats | none |
| 6 | One zero per connected group `open_frame_seat` (22o) | contact groups | one zero | groups the elevated pieces with their buildings |
| 7 | §16g units / connector `footprint_unit`, `footprint_connector`, `footprint_seats` | unit footprints; a long connector (elevated rail) between two units | unit seats; the connector keeps its datum | the elevated rail / APM guideway case |
| 8 | Cross-placement abutment `contact` pass 3, `placement_carrier` (09-10ay) | shared-datum abutments | the elevated road bridge takes the terminal's delta, its ends may bury | holds at KMCO (§3.1): the elevated pieces are AT the group datum |
| 9 | Airside group seat `airside_group_seat` (22q) | a group touching airside | seated on the airside floor | the (a) limit: such a group moves with the airside (≤ 0.5 m, 20b) |
| 10 | Carriers / footless `placement_carrier`, `free_column` (§13/§14) | elevated parts and their carriers | a footless piece rides its carrier | the soffit body's zero is its carrier's |
| 11 | Bridge law `bridge_class`, `free_bridge_seat`, `airside_deck_seat`, `planar/overpass_deck`, `deck_riders` | pack decks over mapped roads / airside | the deck's seat (on the road beneath for an overpass) | pack BRIDGES are this law's (KMCO `puente`/`puente2`, hidden under generated decks since 20a) — outside 20g's population |
| 12 | Generated road bridge ceiling `constraints/road_bridge_ceiling` | lower road under a generated deck | hard ceiling = deck line − class clearance on the lower road's vertices | the template for (b); generated decks are lcross21's |
| 13 | Passage witness `planar/structure_service._PackBuildings.passage` (§34 (12) (5) (e)) | a tunnel-tagged way under an ELEVATED pack part (base y > `[rebake] elevated_base_m`) | not a terrain tunnel: the road runs at grade | reads the authored clear space only (KMCO -1878: "4.8 m"), never the seated one |
| 14 | Two-level regions `planar/level_regions`, `level_underside`, `low_level`, `viaduct_road`, `constraints/viaduct_floor` (#1852, R6) | walls below a unit's zero with at-grade roads through it; its soffit | a lower level at the walls' depth; soffit vs `[tunnel] clearance_m` REPORTED | overlaps (b) for passages through stations: a 20g ceiling must not fight a minted lower level |
| 15 | Road grading `road_profile`, `airport/road_ramp` + `constraints/road_ramp`, `public_road` | road ribbons | road grade law (design 5 %, cap 10 %) | builds (b)'s ramp |
| 16 | Pads `constraints/pads`, `cluster_pad`, `group_level`, `pad_level_group`, `planar/cluster` | building pads | pad levels | (a)'s terrain grading |
| 17 | Grade separation `planar/grade_separation` | road over road | crossing levels | roads only (no pack structure) |
| 18 | MSL conversions / feet seats `dsf_write.conversions_for_dump`, `msl_feet` | `OBJECT_MSL` rows by origin set | on-ground at the anchor, or the set by its feet | KDFW's whole terminal; NOT in the rebake plan's units, so passes 1–10 never see it (§3.2) |
| 19 | Rail ramps `[tunnel] rail_ramp_grade` 1.25 % / `rail_ramp_max_grade` 3.5 % | rail bores | rail grade law | (b) over a rail; rails carry NO planar faces today (no ribbon class) |
| 20 | Census tools `drawn_site --roads`, `--clearance-only`, NEW `--crossings` | the drawn products | — | the 20g measurement (§2) |

## §2 The crossing read (ONE derivation) — `auto_patch_v2/airport/elevated_crossing.py`

* A WAY a structure may stand over: `highway` or `railway`, no bridge itself
  (`deck_signature.is_bridge_way`); a tunnel-tagged way is kept (a road the map says passes
  under a building is exactly a crossing).
* Its CARRIAGEWAY: centreline ± half `model/road_clearance.carriageway_width_m`, flat ends;
  its NEED `design_clearance_m`: 4.2 m over a small road, 5.0 m over every other road and rail.
* A CROSSING CELL (1 m grid on the carriageway): the LOWEST static solid face of one placed
  structure over the cell (`geom/lowest_face.every_z_at`) stands over the structure's floor
  (the object stage's frame zero + `elevated_base_m`) or, with no floor known, 0.5 m over the
  ground; a face at grade is a building the road enters, no crossing.
* A structure CROSSES only at the stations where it SPANS 0.8 of the carriageway (a car at the
  kerb, a canopy over one lane, a crown is none).  Clearance = soffit − ground at the least cell.
* The tool `drawn_site --crossings` (library `tools/drawn_site_crossings.py`) runs it on the
  WRITTEN pack rows over the DRAWN mesh, tagging rows `pack` / `generated` / `library`.
  Twin `tests/auto_patch_v2/test_elevated_crossing.py`.

## §3 MEASURED (owner's 11-19 world build: installed pack DSFs + installed tile DSFs)

### §3.1 KMCO (+28-082; 900 m about 28.4300,-81.3070; replay `v2_rebake_replay plan` on test-568 reproduces the terminal group: 145 bodies at 26.349, S 0.835)

156 pack crossings, 75 short; excluding the pack bridges `puente`/`puente2` (bridge law):
**the main-terminal complex (unit:6: centro_1/2, techos_1, estacion_1/3, interiores, via_tren)
116 crossings, 58 short, over 30 roads and 4 rails; E3T 2 short.**

Owner site 28.42998,-81.30440 (the rails into the station and the service road beside them):

| structure (body) | under it | least clearance | need | short |
|---|---|---|---|---|
| centro_2 b28 (elevated road deck) | railway -11396 | 2.69 | 5.0 | 2.31 |
| centro_2 b28 | railway -11406 | 2.70 | 5.0 | 2.31 |
| centro_2 b28 | service -4708 | 2.74 | 4.2 | 1.46 |
| centro_2 b28 | tertiary -4821 | 3.89 | 5.0 | 1.11 |
| via_tren b0 (APM guideway) | railway -11396 / -11406 | 3.71 / 3.71 | 5.0 | 1.29 |
| via_tren b0 | service -4708 | 3.69 | 4.2 | 0.51 |
| via_tren b0 | tertiary -4821 | 4.80 | 5.0 | 0.20 |
| centro_1 b12 | service -4340 | 1.81 | 4.2 | 2.39 |

ATTRIBUTION (#2192's hypothesis "the elevated pieces drop with the low ground" is REFUTED):
every body over the site is at the group datum (`surface_z − y_zero` = 26.349 for all 145;
the "24.7–29.4 m" of the issue are body BASES, not zeros) — 09-10ay and 16u hold.  The
clearance is lost because the pack AUTHORED its elevated decks 2.9–4.4 m over its own datum
(b28's soffit y +3.32, via_tren's +4.35) while the lidar ground under them stands 0.64–0.85 m
over that datum (26.99–27.20 against 26.349): seated anywhere on its own ground (its lowest
to its highest vote) the complex leaves 46–58 of its crossings short.

What each remedy costs at KMCO (the complex's 58 short crossings):

| lift of the whole group (a) | 0 | 0.5 | 0.835 (= seat at its HIGHEST vote) | 1.5 | 2.31 (owner site) | 3.0 | 3.67 |
|---|---|---|---|---|---|---|---|
| crossings still short | 58 | 50 | 46 | 28 | 12 | 5 | 0 |

(b): lower 30 roads (median 1.67 m, worst 3.67 m: ramps ≤ 73 m a side at the 5 % design
grade) and 4 rails (2.29–2.31 m: 183–185 m ramps at the 1.25 % rail design grade, one-sided:
they end in the station).  Rails are no planar faces today: (b) over a rail needs a rail
corridor minted (no ribbon class carries a rail: an at-grade rail has no face a ceiling
row could bind), not a ceiling row on an existing face.

### §3.2 KDFW (+32-098; 1600 m about 32.8990,-97.0400)

426 pack crossings, 117 short (jetway kits over apron service roads 0.2–1.4 m short are
airside: never lowered).  The pack places EVERY object at ONE anchor (32.887477588,
-97.048995289, the field's SW corner) as `OBJECT_MSL` sets by elevation; the engine seats
them as separate origin sets (`msl_feet`):

| MSL set (authored) | rows | seat | seat − authored | guard witness |
|---|---|---|---|---|
| 184.570 | 57 | on-ground conversion at the anchor: 175.31 | −9.26 | `118.obj` has NO static solid (a lights file) |
| 184.270 | 26 | on-ground conversion at the anchor: 175.31 | −8.96 | `154.obj`, `240.obj` no static solid; `250.obj` "built around origin" by its BOX (6.4 × 5.9 km layer; its nearest below-origin vertex 1,084 m from the origin) |
| 184.360 | 20 | feet seat 176.69 | −7.67 | none |

The terminal-area ground under the loop roads reads 176.835.  The walkway / sky-bridge floor
layers are authored 4.25–4.34 m over their datum — the pack's own clearance over its ground —
and read: `161`/`162` (184.36 set) 4.10 m over service -2388 / -2018 (short 0.10);
`133` (184.27 set) 1.60–3.00 m over 14 service roads (short 1.20–2.60); `70`/`71` (184.57 set)
2.82 m (short 1.38).  ATTRIBUTION: sets authored 0.09–0.30 m apart are seated 1.38 m apart
because the guard pins two of them on the far anchor's ground; the loss is a SEAT of the
pack's one authored frame, not the geometry.  Skylink (184.36 set) over International
Parkway (`168`: a 2.2 km elevated layer, y 3.75–16, by its course the Skylink guideway)
reads 1.22–3.60 m (need 5.0) where the parkway's ground stands 179.07–179.21, 2.3 m over
the terminal flat.

## §4 Mechanism (designed; held for §5)

(a) THE SEAT — post-mesh, after the touch pass, before the warp and the split bar: a group
holding a short crossing takes the zero that clears it, capped by (i) airside: a group whose
seat the airside holds (`airside_group_seat`, or any member touching airside) moves ≤ 0.5 m
with it (20b), and (ii) the terrain the patch graded for it: pre-mesh, the crossing frames'
building pads (`constraints/pads`, `cluster_pad`) take the lift as a lower bound so no member
floats.  This needs the crossing read in the patch (the partition + `airport.osm_ways`) and
the zero it promised published on the rebake plan (the `overpass_deck` precedent: the patch
decides the zero, the object stage reads it off the plan).

(b) THE RAMP — pre-mesh: every planar vertex of the crossed way's carriageway under the soffit
takes ONE hard ceiling `Band` (the `road_bridge_ceiling` form): predicted zero + authored soffit
y − need; the road profile / ramp rows (5 % design, 10 % cap) carry the ramp; a rail needs its
corridor minted first (rail grades 1.25 % / 3.5 %).

KDFW (a) is a seating law of its own: the `OBJECT_MSL` rows of ONE anchor are one authored
frame — their elevations are their relative heights — seated as one rigid set (16u for MSL
rows), the guard asked only of geometry AT the origin (a member with no static solid neither
guards nor seats).  Seated at the 184.36 set's feet (176.69 + (z − 184.36)): `133` soffit 180.85,
4.01 m over 176.835 (short 0.19); `70`/`71` 181.24, 4.40 m (clear); `161`/`162` unchanged 4.10.

## §5 OWNER QUESTIONS (with the recommendation)

* **Q1 (KMCO, a landside complex):** the main-terminal complex is held by no airside, so 20g
  (2) reads "lift it": clearing every crossing needs 3.67 m (2.31 m for the owner's site) — the
  whole complex (its at-grade kerbs, garages and the 1.2 km APM guideway `via_tren` with it;
  wherever the guideway meets an airside-held building, 20b caps the lift at 0.5 m there).  (b) lowers 30 roads by
  ≤ 3.67 m (median 1.67) and the 4 station rails by 2.3 m on 185 m ramps.  RECOMMENDATION:
  (a) only up to the group's own spread (seat at its HIGHEST vote, +0.835 m, the terrain graded
  under the low members), the rest by (b) — the lift a complex takes is bounded by the ground it
  already stands on; a road dips where the structure demands it.
* **Q2 (KDFW):** seat the pack's `OBJECT_MSL` sets of one anchor as ONE rigid authored frame
  (lifts the walkway floors 1.3–1.7 m; touches every MSL pack: KBNA, KMCI, KDFW), then (b) the
  residual 0.1–0.2 m and Skylink over the parkway?  RECOMMENDATION: yes, in a lane of its own
  (`airport/msl_feet` — coordinate with the ELLX seating lane), measured at KDFW / KBNA / KMCI
  before any ramp is cut.

## §6 This lane did NOT

Implement (a) or (b); run any tile build; measure certified-airport movers (no seat moved:
0 by construction); census rails as ribbon candidates; read KDFW's other four packs.
