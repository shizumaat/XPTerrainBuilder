# Spec #2197 rounds 2–3 — partial shells: the narrowed population, the patch half, the airside floor (lanes lpartshell2, lpartshell3, 2026-11-25)

Base `claude/lpartshell` 34c5814d2 (round 1, not merged) on `claude/project-thread-ddpu46` 302511b0c.
Owner 2026-11-20T14:20Z (ELLX, verbatim): "the terrain should meet it's outer edges flush all the way around so you can't see under it." Owner 2026-11-22T16:25Z (LDSP): "we need to recognize that and seat and grade things so it blends into the natural terrain correctly."

Round 1 recognises a PARTIAL SHELL (`airport/ground_rim`: an origin set whose ground sheet holds ≥ 0.5 of its plan and of its outer rim and models ≥ 5 m of relief beyond a plane), seats it rigid and grades the FREE tile raster to its rim stations (`airport/rim_grade`). Two defects keep it from merging: the population is too broad (§1), and the rim stays open where it lies inside the airport patch, whose postings the tile never moves (§2).

## 1. Narrowing (recognition): THE SHEET IS OUR GROUND, REMODELLED

Round 1's gates (plan ≥ 50 m; sheet ≥ 0.5 of the plan and of the outer rim; sheet relief ≥ 5 m beyond a plane) hold 152 origin sets in 64 packs of the owner's 1,482-pack library (one-worker census, §4.1; 56 of them in one simHeaven X-World pack): bridges and viaducts (EGLL, RJTT, KEWR, LIPV, KDEN, KLAX, EGSS, LGAV `Bridges1_00`), tunnels (VHHH, EDDF), elevated roads (KTPA, KBWI, KMEM, KPDX, EPWA), landmarks (Burj Al Arab, Opera House, mosques, stadiums), hangars and cargo sheds, BIKF's earth-covered bunkers, hills and rocks. Each models relief the AUTHOR added; ELLX's sets re-model the ground they stand on.

`airport/ground_rim._is_our_ground` adds three gates at the seat, read over the sheet cells (`g` our ground over the seat's zero):

| Gate | Constant | Reads | ELLX (4 sets) | Nearest refused |
|---|---|---|---|---|
| FOLLOW (RULINGS 25f: never a terrace far from credible terrain) | `MIN_FOLLOW_SHARE` 0.8 | share of the sheet with `|top − g| ≤ AT_GRADE_M` (1.5 m) | 0.85–0.96 | BIKF bunker 0.69/0.71, EDDH logo 0.70; the ONLY set failing this gate alone: X-World `Magdeburg_Kanalbruecke` (a canal bridge) 0.70 |
| RELIEF EXPLAINED (our ground has the sheet's relief) | `MAX_UNEXPLAINED` 0.5 | 5–95 % span beyond a plane of `top − g`, over that of `top` | 0.21–0.31 | EDDH logo 0.53, BIKF bunker 0.59/0.61; failing this gate alone: KMCI `Hangrao` 0.92, PHNL fuel farm 0.87, X-World Baton Rouge capitol 0.83 |
| SKIN (a ground surface, never a deck over a void) | `MIN_SKIN_SHARE` 0.9 at `SKIN_M` 0.5 m | share of the sheet with `top − low ≤ 0.5 m` | 0.95–1.00 | failing this gate alone: ENGM `Ham3` 0.81, KTPA `East2_ElevatedHWY` 0.52, KBNA taxiway bridge 0.06 (all three follow our ground at 0.93–0.97) |

Every gate is a share or a ratio; no pack, object or airport is named; each gate alone refuses at least one set the other two pass (load-bearing). Result: 4 sets in 1 pack (ELLX `Terminal-A` + SkyPark 49.635, 6.217; `Lux_Fuel_base` 49.634, 6.221; `firestation` 49.626, 6.201; `pool_5` 49.619, 6.186). Full table §4.1.

NOT KEPT, contrary to the round-2 brief's keep list: KSRQ `mesh_hill`, EBBR `hill_03`, LGSR `Colina`, CYAZ `Rock_1`, BGGH `Rocks3`. They are hills and rocks: relief the author added on top of the ground (relief not explained, 0.78–1.29; follow 0.35–0.70). No measured share separates them from the landmarks and blast fences (CYQB `APTjunk`, KTPA `Fedex_Blast`, EDDH `logo`, LGTS `lgts_libtextures1`, all skin 1.00 with rim-follow 0.84–0.90 above KSRQ's 0.93 … CYAZ's 0.24). A hill's flush rim is another witness (its RIM at grade, the body free) and an owner question (§6 Q1), not this module.

## 2. The patch half: a groundside face touching a rim takes the rim — MEASURED AND REFUTED (deleted)

**Status.** Implemented as `constraints/rim_pins` (draft below, kept for the record), replayed at ELLX in three arms (§4.2), and DELETED from the branch: as yielding pins it closes 20 of 1,460 open rim stations and still moves 82 stage-2 apron vertices up to 0.74 m; as hard pins it closes the groundside rim (pool_5 service roads 101 → 0 open, firestation lot 132 → 81, Terminal-A lots 189 → 102) but moves 2,342 stage-1 airside levels up to 0.32 m and 1,642 final airside heights up to 9.9 m. Airside is king, so neither arm can land. What carries the rim inside the patch is the frontage spec's rung L4 (`docs/specs/terminal-frontage-split-level-20261125.md`: the frontage level from the sheet, lots following it ≤ 5 %), not a pin; its consumer C23 is void. The draft rule as specified:


### 2.1 The rule
Per recognised set (`constraints/rim_pins.rim_sets`: every `TerrainModel.rim` of `airport.terrain_models`, once per set), every vertex of a GROUNDSIDE VALUE face (`constraints/groundside.groundside_face_roles`: `groundside_pavement`, `service_road`, `service_junction`, `parking_lot` — car lots included) that

* no face of any other role carries (an airside face, a strip band, a structure ramp: airside is king; a structure's rim is its own law), and
* stands on no open edge of the patch (the seam's `seam_pins` and the coverage edge's `roads.coverage_edge join` own those),

is pinned (`Pin`, generator `rim_pins`, ruling head `#2197 a groundside face meets a partial shell's ground rim`) at

1. UNDER THE SHEET — its plan point on a sheet cell: the author's ground there (`_RimSet.sheet_at`, the sheet's `z0 + top` kept on the record) less `geom/terrain_deck.UNDER_M` (0.1 m): the lot stands just under the shell's ground, never through it;
2. OUTSIDE THE PLAN within the stand-off reach (`constraints/gap_follow.reach_m`, the distance a groundside face welds to a standing ring across) of a rim station: the stations' inverse-distance-squared mean (the 8 nearest, `rim_grade`'s own target) less `UNDER_M`;
3. anywhere else (under the shell's buildings or decks, i.e. inside the plan off the sheet; beyond the reach): no pin. The face follows its own law from its pinned vertices (lot / road caps, 25e's ground-follow within the 5 % cap).

The rim is the AUTHORITY, ONE-WAY: the object never moves (round 1's rigid seat), our groundside conforms.

### 2.2 Airside never moves
The head is registered in `[design] groundside_pin_rulings` (`law/emit.toml`): §20b stage 1 treats every rim-pinned vertex (and its rigid class) as FOREIGN (`solve/design_stage._groundside_pinned`), so no lot / road / frontage row footed on it enters the airside problem — the airside solves free and the lot conforms in stage 2 (10-02v (1), #143). A pin whose rigid class contains an airside vertex is not groundside (design_stage's own rule) — `_candidates` never mints one on a vertex an airside face carries.

### 2.3 Conflicts yield
The head is registered in `[design] yielding_pin_rulings`: a rim pin its own hard rows cannot hold (a lot or road ceiling from a senior level, a seam reach) is released to a design target at its own value and REPORTED (`DesignReport.pin_yield`), as the coverage-edge join is (`solve/pin_yield`, 27a (10)). Never infeasible.

### 2.4 Coordination with RULINGS 2026-11-25e (lots follow their ground within 5 %; lane llot)
A lot touching a rim TAKES THE RIM: its rim-pinned vertices are constants; 25e's ground-follow applies to the lot's other vertices, which grade from the pinned ones within the lot's 5 % cap. Where the rim and the lot's DEM disagree by more than the cap allows, the pin wins at the rim (it is a constant) and the cap row carries the residual (one-sided penalty) — the visible edge is flush, the lot's body grades away.

### 2.5 Consumer census (RULINGS 2026-08-30l): region = groundside vertices under a recognised sheet or within the stand-off reach of its rim

| # | Consumer | Reads | Ruling here |
|---|---|---|---|
| 1 | `airport/ground_rim` (load, `obj8.read_placed_objects`) | the origin set | DERIVATION SITE: recognition + `sheet` surface on `_RimSet` |
| 2 | `terrain_model.seat_records` / object stage | the set's rows | rigid `OBJECT_MSL` at `z0 + lift`; unchanged |
| 3 | `auto_patch/terrain_cut_stage._grade_rims` → `rim_grade` (tile raster) | free postings | unchanged: never a patch posting (frozen) — the patch half is this spec |
| 4 | tile DUMMY constrained lines (`_rim_lines`) | rim rings | unchanged |
| 5 | NEW `constraints/rim_pins` | groundside value-face vertices | THE PINS (§2.1) |
| 6 | `solve/design_stage.stage_split` (`_groundside_pinned`) | pin ruling heads | rim pins FOREIGN to stage 1 (§2.2) |
| 7 | `solve/pin_yield` | yielding heads | rim pins yield on own conflict, reported (§2.3) |
| 8 | `constraints/groundside.groundside_ramps` (apron edge → groundside 5 %) | groundside ring vertices | row stays; footed on a pin it is a stage-2 row only (foreign) — the apron is never pulled |
| 9 | `constraints/pad_frontage_gs`, `roads`, `road_ramp`, `road_cross_section`, `pavement_cap`, `public_road_release` | road / lot vertices | rows stay; a pinned vertex is a constant they grade from |
| 10 | `constraints/car_lot_follow`, `pipeline/lot_follow` (late / follower stages) | lot vertices | a pinned car-lot / lot vertex is a constant (a pin outranks a stage substitution, `solve/rows._reduce`) |
| 11 | `solve/design_ground` ground datum | strip vertices (no pavement) | untouched: rim pins are never on a strip vertex |
| 12 | planar `Vertex.dem_z` substitutions (`object_ground`, `bridge_ground`, ...) | `dem_z` | untouched; the pin overrides only the solved value |
| 13 | seam pins, coverage-edge join pins | open-edge vertices | senior: rim pins never mint on an open edge |
| 14 | emit / heightfield | solved z | emittable: a pin is a vertex value, no new geometry |

### 2.6 Out of scope (named, not done)
* No rim breakline is inserted into the planar map: where a groundside face's ring crosses the rim far from any vertex, the face's own triangulation interpolates between pinned and free vertices (measured residual in §4).
* Ground strips (zone bands: `graded_strip`, clearances) are airside-side roles and are never pinned.

## 3. Build-time impact
Recognition adds three vectorised shares over the sheet cells already rasterised (`_is_our_ground`), only for a set that passed round 1's gates (152 in the whole library; 4 at ELLX, 0 at every other airport the census reads). No patch-side cost (rim_pins deleted).

## 4. Measurements

### 4.1 Population (one-worker census over 1,482 packs: `tmp/lps2/feat.py`, the round-1 gates plus the features; 2026-11-25)
152 sets / 64 packs pass round 1. Kept by §1: 4 sets / 1 pack, all ELLX:

| Set (first row) | Rows | lat, lon | follow | unexplained | skin | relief m | z0 m | rim stations |
|---|---|---|---|---|---|---|---|---|
| `Terminal-A` + SkyPark | 157 | 49.63502, 6.21678 | 0.85 | 0.30 | 0.97 | 7.9 | 374.74 | 3,117 |
| `Lux_Fuel_base` | 14 | 49.63412, 6.22076 | 0.87 | 0.26 | 0.95 | 12.9 | 376.45 | 744 |
| `firestation` | 17 | 49.62619, 6.20094 | 0.96 | 0.31 | 1.00 | 5.7 | 374.06 | 711 |
| `pool_5` | 12 | 49.61864, 6.18593 | 0.95 | 0.21 | 0.99 | 8.3 | 346.59 | 736 |

(z0 / stations from `tools/terrain_model_census.py` on the ELLX pack with the branch code: `rim` gate 4.) Refused, by the brief's list: EGLL 5/3/2/12/11/9.obj, VHHH tunnels, EDDF `Tunnel_1`/cargo, ENGM `Ham1-3`, KDEN train bridge/walls, KLAX `Bridge_T1`, KTPA (3), CYVR `BS2`, EPWA viaduct, KMEM, KPDX, KBWI `Highway`, LGAV `Bridges1_00`, Burj Al Arab, BIKF `bunker1` ×2 and `radar`, hangars (EGAA, KMCI), KSRQ / EBBR / LGSR hills and CYAZ / BGGH / XNZHN rocks (§1). Certified BIKF and LGAV hold no partial shell: their builds are unchanged by this branch (every rim code path is gated on a recognised set).

### 4.2 ELLX in-patch rim (capture `ELLX.pkl`, branch 3582e8679 + the §1 gates; replay `--from constraints`)
Gap = our solved patch surface at a rim station − the author's ground there. OPEN = gap < −0.5 m (the shell's edge stands over our ground: you see under it); BURIED = gap > +0.5 m.

| Set | in patch | arm | OPEN | max open | by role (OPEN / stations, p50 gap) |
|---|---|---|---|---|---|
| pool_5 | 486 / 751 | no pins | 103 | 1.42 | service_road 101/446 (+0.35) |
| | | yielding pins | 78 | 1.23 | service_road 76/446 (+0.25) |
| | | hard pins | 4 | 0.63 | service_road 0/446 (+0.08) |
| Lux_Fuel_base | 662 / 736 | no pins | 427 | 3.02 | building 398/630 (−2.96), service_road 29/32 |
| | | yielding | 431 | 3.67 | building 402/630 (−3.55) |
| | | hard | 485 | 12.72 | building 472/630 (−12.51) |
| firestation | 335 / 709 | no pins | 210 | 3.05 | parking_lot 132/245 (−2.08), apron 54/54 (−1.58), strip 23/27 |
| | | yielding | 210 | 2.81 | parking_lot 132/245 (−1.80) |
| | | hard | 157 | 2.81 | parking_lot 81/245 (−0.16) |
| Terminal-A + SkyPark | 2,253 / 3,139 | no pins | 720 | 6.31 | apron 420/1,642 (+3.72), parking_lot 189/296 (−3.55), service_road 104/297 (+0.48) |
| | | yielding | 721 | 5.65 | parking_lot 189/296 (−2.90) |
| | | hard | 594 | 5.37 | parking_lot 102/296 (−0.11), service_road 77/297 |

Airside: yielding pins 1,156 minted, 1,121 released (`PIN YIELD`), stage-1 levels identical, 82 stage-2 apron vertices moved (max 0.744 m at 49.63555, 6.21959, an apron|lot vertex east of Terminal-A); hard pins: all 1,156 hold, 2,342 stage-1 levels move (max 0.317 m), 1,642 final airside heights (max 9.89 m). A third arm, the author's ground substituted as the groundside vertices' `dem_z` (1,168 vertices, no pins), moves nothing (OPEN 1,460 → 1,460; airside 0): the lots do not read their DEM where they meet a rim.

The rim's in-patch share is 47–90 %; of the 3,736 in-patch stations, 1,696 stand on apron (airside: never moves) and 648 on building pads; only ~1,300 are groundside at all.

### 4.3 Free (tile-raster) rim, before the grade (census `gap` = station − our DEM outside, p5 / p95; over 0.5 m)
pool_5 −3.82 / +1.19 (558 of 736); fuel base −1.61 / +2.78 (416 of 744); firestation −2.34 / +1.16 (464 of 711); Terminal-A −3.10 / +1.59 (1,930 of 3,117). After the grade: not measured here (tile build; integration).

### 4.4 The seat (round 1) against main's
Round 1 seats each set as ONE rigid `terrain model` frame (rebake plan of this replay: `seat` "terrain model", elevation = z0). Main's last ELLX plan (`Patches/+40+000/+49+006`, 2026-11-19) seats the same rows by §16g units: `Terminal-A.001` "on pad building42 at 375.90" (here 374.85: −1.05 m), `firestation.001` "on pad building21 at 366.34", `Lux_Fuel_base.001` "connected group at 380.62", `pool_5.001` "seats within 0.5 m, at 344.28". Only the Terminal-A pair is plainly the same frame; the others are split bodies whose zeros are not directly comparable. A partial shell that carries an airside floor (Terminal-A: 1,642 rim stations on apron) is seated by our DEM, not by its pad: MERGE BLOCKER until the integration drawn gate at 49.6350, 6.2168 shows the terminal's airside floor unmoved (§6 Q2).

## 5. LDSP (RULINGS 2026-11-25f/h)
No LDSP set reaches round 1's gates (census: the Aerosoft LDSP packs yield no row), so this module neither seats LDSP's terminal nor grades our ground to its terrace: 25f holds by construction, and the FOLLOW gate (§1) refuses any later sheet standing off credible ground. The sky bridge (#2287): LDSP's terminal is ONE origin set (56 rows within 600 m of 43.5366, 16.2990 share the origin; main's plan: `unit:5`, 44 members, `connectors` empty), so the bridge and the lower-level building are authored in one rigid frame and already meet each other as authored. The existing skew (`airport/connector_warp`, RULINGS 2026-11-18h (3): the #2144 deck warp, piers vertical, capped at `[deck] shear_max_grade` 10 %) acts only on a connector between two SEPARATELY seated buildings. It can take the sky bridge only once the frame is split into two seats (the frontage spec's L5 linked building, or a §16g connector reading that names the bridge). A 5.8 m storey then needs ≥ 58 m of bridge at 10 %. The bridge body was not identified here (candidates by extent: `LDSP_NewTerminal_6` 100 × 227 m, y −2.7..9.7; `LDSP_NewTerminal_7`, y 0.6..18.0).

## 6. Owner questions
- **Q1.** Hills and rocks (KSRQ `mesh_hill`, EBBR `hill_03`, LGSR `Colina`, CYAZ `Rock_1`, BGGH `Rocks3`): their rim meeting our ground is a different witness (the body is relief we do not have). Should their RIM be graded to like a partial shell's, with a new witness to tell them from landmarks and blast fences?
- **Q2.** A partial shell that also carries an airside floor (ELLX Terminal-A + SkyPark): should its rigid frame take the PAD's seat (airside is king; the landside sheet then stands where the pad puts it, our ground graded up to it), or the DEM fit (round 1, −1.05 m against main)?

## 7. Round 3 (lane lpartshell3, 2026-11-25): the airside floor; why its rim is not graded yet

Owner target (RULINGS 2026-11-25k): the objects do not move (each stays on its airside pad as today); our ground OUTSIDE the patch meets each set's outer edge flush within 0.5 m, feathered back; inside the patch the edge is the frontage work's (L4); only the four ELLX sets qualify. Q2 is answered by 25k: the pad, never the DEM fit.

### 7.1 What landed
THE AIRSIDE FLOOR (`ground_rim`): a recognised set whose ground contacts touch apt.dat airside pavement (`airside_floor`'s witness, `TOUCH_M`) is NO rigid frame: its rows are read like any object (planar holds the pads, the object stage seats the bodies), and its `_RimSet` rides its first row (`PlacedObject.rim_set` → `Airport.rim_sets`, `ground_rim.rim_sets_of`, shared by `pack_stage` and the replay twin) and is named on the build log. All four ELLX sets carry an airside floor, so round 1's rigid frame applies to none of them. Their rim is NOT graded to (§7.3).

### 7.2 Measurements (capture `tmp/lps3/cap/ELLX.pkl`, branch on `claude/project-thread-ddpu46` 94516fd72; replay `--from constraints --emit --rebake-plan`; object stage `tools/obj8_split_report.py`)
- **Objects vs control.** Same capture replayed with the control code (`origin/claude/project-thread-ddpu46` src+tools): the patch .osm is byte-identical, every graded vertex identical (22,525, max |dz| 0), the rebake plan identical but for the rim records, and the object stage's 1,000+ bodies identical (0 differing, kept 132 = 132). Unit seats on both arms: Terminal-A `fu:99:4893` on building42 **375.86**, firestation `fu:76:3559` on building21 **367.14**, pool_5 on building8 **344.28**, Lux_Fuel_base `fu:131:6239` **376.23** (one member on building49). The 13:45 control numbers (374.76 / 366.34 / 380.62 / 344.28) are pre-lfront1 main: building42's flat seat moved 374.83 → 375.94 m on the merged base, in both arms (not this branch).
- **The pad zero is refuted (deleted).** WIP `rim_pad_seat` read the set's zero as the median, over its ground contacts on the pad holding most of them, of the pad plane less the contact's lowest authored surface. Result: Terminal-A 366.65 (−9.2 m off its unit), firestation 359.05 (−8.1), Lux 375.56 (−0.7), pool 348.38 (+4.1): the lowest surface of a covered cell is a deck or a basin floor, not the floor the object stage seats on. Restricting the contacts to the frame datum (|y| ≤ 0.5 m) on the graded surface: pool 344.43 (+0.15), Terminal-A 376.25 (+0.39), firestation 367.08 (but its bodies sit at 372.84–375.58 m on their median ground, not the pad), Lux 1 contact. No contact rule reproduces the object stage.
- **Why no pre-mesh zero exists.** The object stage splits each set into bodies with their own zeros (firestation.017: five bodies, 372.84 / 374.37 / 374.55 / 375.58 / 375.58; Lux_Fuel_base.014 rides a connected group at 376.23 though its pad is building47 at 375.56), and it runs after the mesh. The rim grade bakes the DEM before the mesh. A rim zero would have to come from the object stage itself.
- **Free rim gaps (acceptance number, offline).** a lane scratch script (first use, not promoted): the airport DEM (`tile_route.airport_ground`) at the tile posting (1/11016°), patch = union of the graded faces frozen, `rim_grade` run per set; gap = ground − station, free = outside the patch; over = |gap| > 0.5 m.

| Set | free stations | no grade: over (p5/p95) | grade at the OBJECT STAGE's zero (oracle): over (p5/p95) | grade at the refuted pad zero: over vs the real edge |
|---|---|---|---|---|
| pool_5 (344.28) | 135 | 133 (+1.00/+2.48) | 22 (−0.38/+1.08) | 133 |
| Lux_Fuel_base (376.23) | 60 | 54 (−3.13/+8.55) | 49 (−3.00/+3.97) | 59 |
| firestation (374.37, one of five) | 374 | 166 (−2.45/+2.38) | 118 (−1.85/+1.40) | 343 |
| Terminal-A (375.87) | 230 | 204 (−2.78/+2.53) | 158 (−2.04/+2.17) | 218 |

Even at the right zero the grade leaves 22–158 free stations past the bar: the stations next to the patch are bracketed by frozen postings, the target is an 8-station IDW mean, and a single zero does not fit a set split into several. **The acceptance bar (0 free stations over 0.5 m) is not met by any arm.**

### 7.3 Proposal (round 4; design, not done here)
1. **The rim's zero comes from the object stage**: grade per STATION at the zero of the body whose plan holds it (the station → body map is the object stage's split), never one set zero. Two homes: (a) the patch stage runs `placement_write.build_plan` over the graded surface for the units holding a rim set's rows (on a pad the mesh IS the patch, so pad and family zeros are mesh-free; bodies on their median ground read the DEM, which the grade then moves: one fixed-point pass); or (b) the rim grade moves to the object stage and the tile re-meshes the rim window. Cost to measure first (the whole ELLX object-stage replay is ~2.5 min).
2. **Stations next to the patch**: a free station within a posting of a frozen posting cannot be served by the tile raster; those belong with the in-patch edge (L4), and the acceptance number should count them apart.
3. Re-measure the table above with (1) and (2); the bar is the drawn gate at the four sites.
