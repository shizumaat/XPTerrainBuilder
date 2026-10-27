# Road cuts and tunnels from the owner's LFPG hand patch: the rules that generalise it

Status: RULED — owner Q226–Q233, 2026-10-27T15:56:40Z (RULINGS 2026-10-28k);
§5 and §7 revised to the rulings (lane `llfpgcut`, 2026-10-27). Drafted by
lane `llfpgspec`, branch `claude/llfpgspec-cuts-tunnels`, base `origin/main`
f8e877b7d.

Asked by the owner (2026-10-27T15:04Z): LFPG built with 1.0.436 "does not look
much better in regards to road cuts and tunnels. Please review my hand made
patch ... so you can better understand where all the cuts and tunnels should be,
and their size and depth. From this develop the rules need to generalize it".

LFPG is the TEST CASE. Every rule below reads the map, the survey and the pack;
none asks which airport it is building (RULINGS 2026-10-05e,
`test_no_airport_specific_code`).

Rulings it reads: 2026-08-30l (consumer census first), 09-16g (the credible-lidar
cut reading), 10-14f (mouth depth 7.5 m from the ground), 10-14o (no bore under
an elevated pack part), 10-19e / 19n / 19s / 20as (mouths stop at pavement;
slide ≤ 150 m), 10-20am (trench under a pack taxiway bridge matches the object),
10-22g (road reach graded), 10-22n (#1138 held; LFPG's hard-deck bridges "should
have full cut outs under them"), 10-26p (roofed pack tunnels), 10-27g (Q187,
#1280: a surveyed road under a deck is kept if it clears 5 m), 10-27l (Q192),
10-27o / 27q (Q194/Q206: lidar decides a mouth), 10-27z (Q204: no witness, no
tunnel).

## 1. Sources and how they were read

| source | what | path (read-only) |
|---|---|---|
| owner's hand patch | 134 ways, 1,874 nodes; Ortho4XP `altitude` flats and 4-node `altitude_high/low` ramps (`plane`, `spline`, one `atan`), `cell_size` 2 | `~/Library/CloudStorage/Dropbox/X-Plane/Scenery Dev/LFPG/LFPG Ortho4XP_Patch/+40+000/+49+002/LFPG.patch.osm` (2025-01-30) |
| auto patch, 1.0.436 build | engine 1.50.1882, `o4_dem` = `LFPG_france1m.tif` (IGN 1 m tier: the LiDAR-HD 50 cm tier was REFUSED, HTTP 400, "cut at a LOWER TIER") | `XPTerrainBuilderData/Patches/+40+000/+49+002/LFPG_auto.patch.osm` 07:22, report `tmp/auto_patch_v2/+49+002/LFPG/LFPG.report.json` |
| built mesh | the owner's tile, 2,112,143 vertices | `ThunderBlade/Custom Scenery Library/Ortho4XP/zOrtho4XP_+49+002/Data+49+002.mesh` (build log `20261027T133503Z_+49+002.log`) |
| survey | 1 m DTM inset, `lidar_credible` (Z0 108.13 from CIFP; DEM−Z0 0.05 m) | `Elevation_data/+40+000/N49E002_airport_insets/LFPG_france1m.tif` |
| map | tunnel / bridge / layer / class tags (the extracts carry no `name`) | `OSM_data/+40+000/+49+002/+49+002_{big_roads,airport_small_roads,airports}.osm.bz2` |
| pack | TaiModels LFPG hard-deck bridge objects `H3`, `H7`, `H8`, `H17`, `H18`, `H19` (`ATTR_hard_deck`) | `Patches/+40+000/+49+002/o4_v2_rebake_LFPG.json` `units` |

All three surfaces were rasterised on one 2 m grid (lat 48.993–49.040, lon
2.520–2.615): the hand patch as Ortho4XP applies it (nested polygons later, ramps
linear or smoothstep along the high→low axis), the mesh by linear interpolation
of its own vertices, the DTM by nearest sample. The inventory scripts lived in
the lane scratch folder and were deleted with it (owner's file never copied
into the repo).

**The hand patch's datum is not the survey's.** Its flats sit 0–7 m (median
≈ 3 m) below the 2026 survey, unevenly (T2 aprons 103 vs 103–107, the north
runway platform 113–118 vs 114–118, the Roissypole zone 97 vs 101–105), while the
survey agrees with the CIFP thresholds to 0.05 m. Every depth in this spec is
therefore RELATIVE — the floor below the surrounding uncut ground (the crest) in
the same surface — never an absolute elevation. See Q226.

## 2. How depth was measured

At every portal (an end of a chain of OSM `tunnel=yes|covered` ways, same
road/rail family, that is not shared inside the chain) in the hand patch's
cover, 230 portals in all:

- **crest** = 75th percentile of the surface 25–60 m around the portal;
- **floor** = the lowest surface within 12 m;
- **depth** = crest − floor, read separately in the owner's patch, the survey
  and the built mesh.

A portal is "cut" in a surface where depth ≥ 3 m. Ramps: each owner ramp
quad with a drop ≥ 3 m (38) was matched to the auto patch's `tunnel_ramp`
faces (42) by end distance < 70 m; direction = sign of (high→low)·(top→floor).

## 3. Inventory (by landmark)

Depths are owner / survey / auto, median [range], over the owner's cut
portals of each site.

| # | landmark (lat, lon) | what the owner built | owner | survey | auto | portal classes |
|---|---|---|---|---|---|---|
| F1 | A1 motorway under runway 09L/27R, west end (49.0256, 2.5363); pack hard deck `H19` | 55 m-wide trench at the runway platform −7 m, 247 m long through the runway and strip; north approach ramp 576 m (5 m, 0.9 %) | 7.0 | 5.2 [1.6–6.4] | 5.2 [−1.3–13.2] | too_deep 2, missing+filled 2, too_shallow 1, match 1 |
| F2 | A1 under runway 09R/27L (49.0218, 2.5340); pack `H18` | trench −7 m, 477 m × 46 m | 8.0 [7–9] | 5.6 | 5.8 | too_shallow 3, match 3 |
| F3 | A1 under the taxiway bridges south of 09R/27L (49.0178, 2.5323); pack `H17` ×3 | trench −7 m, 552 × 50 m; south ramp 191 m (3 m) | 7.0 | 5.4 | 5.4 [5.0–13.0] | match 14, too_deep 4 |
| F4 | LGV (TGV line) under the north runways and taxiways (49.0218, 2.5690); pack `H7` ×2 | rail trench at −12 to −17 m below the runway platform, decks left at 113–114 over it | 12.5 [12–17] | 10.0 | 9.6 | too_shallow 7, match 3 |
| F5 | LGV trench north of the airfield (49.030, 2.568) | open rail cut −12 m, ramps 501 m (7 m) and 226 m (3 m) | 12 | 9.1 | 8.1 | (no tunnel tag: trench polygons) |
| F6 | LGV / RER B trench and the TGV station between 2C/2D and 2E/2F (49.013, 2.571) | trench 94 m (−9) north of the station; south ramp 739 m 100.9→91 (1.3 %) | 10.7 [6–13.5] | 9.6 | 11.6 | match 3, extra 3, missing+filled 1 |
| F7 | T1 access spur and T1 lower roads (49.013, 2.5415) | the T1 ring/spur at 96 under the T1 aprons (103–105) | 9.0 | 6.7 | 13.4 [10.8–14.1] | extra 15, too_deep 6, owner-flat 6, match 3 |
| F8 | Roissypole primary-road tunnels by the CDG 1 RER station (49.0105, 2.551) | 96 trench under 103 deck, ramp 106→96 over 118 m (8.5 %) | 6.5 | 6.2 | 5.0 [2.1–5.7] | match 6, missing+filled 1, too_shallow 1 |
| F9 | 2A/2B west interchange (49.0065, 2.555) | 97 level under 103, three walled pits (rings 103 around 97, ≤ 2 m apart) at the secondary-road portals | 6.0 | 6.3 | 4.9 [3.4–17.1] | match 18, too_deep 5, extra 3 |
| F10 | T3 / CDGVAL road knot north of the TGV line (49.0115, 2.564) | a stair of levels 110/109/107/105/103 with ramps 6–22 % | 6.0 | 3.0 | 8.6 [8.6–10.8] | too_deep 3, extra 4 |
| F11 | primary road along the north side of 2B/2D (49.0086, 2.5645) | 97 trench 511 × 19 m | 6.0 | 6.9 | 11.2 | too_deep 1 |
| F12 | 2E/2F forecourt, secondary and service tunnels (49.0053, 2.592) | the whole forecourt road level at 96, 7 m under the 103 aprons (21 ha basin) | 7.0 | 6.2 [0.5–7.8] | 5.9 [0.5–13.2] | match 17, too_deep 7, missing+filled 6, extra 4, too_shallow 4, missing 2 |
| F13 | 2E/2F north service roads and freight (49.0108, 2.585) | basin 96 (26 ha) and service ramps 103→100→98→96 | 7.0 | 6.7 | 4.0 [2.9–12.5] | too_shallow 3, extra 2, match 2 |
| F14 | 2A south service ramp (49.0029, 2.5568) | ramp 103→97 over 131 m | 6.0 | 5.7 | 11.8 | too_deep 1 |
| F15 | 2E south, 2E/2G link (49.0013, 2.590) | none (flat 103) | – | – | – | extra 1 |
| B1 | T2 central road between 2A/2C and 2B/2D, under the departure/arrival viaducts (49.0039, 2.5670) | 1,238 m × up to 192 m at 96, 7 m under the 103 aprons | 7.0 | 1.0 | 0.85 | (no portal: road under stacked bridges, layer 2–3 over it) |
| B2 | Roissypole / zone between T1 and T2, north of 2A–2D (49.0098, 2.5631) | 38 ha basin at 97; the survey reads it 4–7 m higher relative to the aprons | 4.6 | 3.2 | 3.1 | (basin) |

## 4. Difference classes and counts

230 portals: match 70, none in either 64, **extra in auto 36**, **too deep 31**,
**too shallow 20**, survey cut that the owner flattened 15 (+8 flattened by both,
+3 owner-flat / auto follows survey), **missing (auto filled a survey cut) 11**,
**missing (no survey cut) 3**, unmeasured 4. 38 owner ramps: **missing 17**,
**wrong position 8**, **reversed 4**, **wrong length 2**, present in the mesh
without a ramp face 7.

### 4.1 Too deep (31 portals; plus the 21 "extra" portals that sit on a survey cut)

The auto floor is 10–17 m under the crest where the owner is 6–9 m and the
survey already shows 5–9 m (A1 F1/F3, T1 F7, 2A/2B F9, T3 F10, 2E/2F F12).

**Mechanism (measured):** `planar/structures.py` takes the mouth's ground as
`dem_z_at(cap_c)` — the DEM at the mouth's cap — and the floor as that ground
less `tunnel.mouth_depth_m` (7.5). On the 30 auto ramps deeper than 3 m,
`floor − (DEM at the floor − 7.5)` is +0.22 m median, 20 of 30 within ±1 m.
Where the survey's open approach trench reaches the portal, that DEM is the
trench floor, so 7.5 m is cut a second time: 14 of the 30 mouths stand in a
survey cut of 3–7 m. The #1280 arm (`planar/lidar_road.py`, 27g) fires only
when the survey notches the road along a MAJORITY of the bore's stations — a
real covered tunnel, whose survey reads its cover, never fires — so 27g's "not
7 m in addition to the existing cut" is enforced for 13 mouths and missed at
these. The §33 (3) crest cap (`_approach_ground` + mouth_depth) only LOWERS a
crest standing proud; nothing raises a crest that stands inside a cut.

### 4.2 Missing: the auto surface sits ABOVE a survey cut (11 portals) or no cut at all (3)

Examples: A1 north portal under 09L/27R (49.0263, 2.5367): survey floor 111.4,
mesh 114.3, owner 7 m; inside F1 the mesh is 7.3 m above the survey (the
runway 09L/27R face is graded across the A1 at 114.9–119.4). Roissypole primary
tunnel `-3458` (49.0109, 2.5509): 27g refused the mouth ("the survey carries
the road through ... nothing is cut") yet the road ribbon `big_roads:-3459` is
solved at 105.8–107.7 over a survey road at 101.8 (+4.7 m); the same +4.2 to
+4.7 m at 2A south `-34487`, the TGV-station service road `-34489/-34490` and the
106→96 ramp `-34484`. Mechanism: NOT attributed. Two candidates, to be
separated by one `v2_solve_replay --probe-site` at each site:
(a) the groundside road grade cap (the owner's ramps there are 8.5–8.7 %; the
survey's descents 6–10 %) lifts the ribbon out of the trench; (b) the 22n hold —
under F1 the pack's `H19` is an airside hard deck (`deck_datum_z` 118.65) and the
runway face is solved flush across it, the trench under it unbuilt (#1138).
Of the 3 no-survey-cut misses, two are 2E/2F service tunnels (49.0043, 2.5905;
49.0029, 2.5775) and one the 2C/2D service ramp `-19104` (49.0041, 2.5852).

### 4.3 Too shallow (20 portals)

Owner deeper than both survey and auto, auto ≈ survey within 1 m: the LGV under
the north runways (owner 12–17 m, survey 9.3–10.9, auto 8.2–10.4) and the A1
south portals under 09R/27L (49.0204, 2.5337: owner 9, survey 4.0–5.6, auto
4.3–6.0). Elsewhere the auto is 1.5–3.5 m shallower than its own survey
(2E/2F `-4528`, `-3553`, `-13950`; Roissypole `-294`, `-369`): the mesh rounds
the survey's trench at the portal.

### 4.4 Extra in auto (36 portals)

- 21 on a survey cut (≥ 3 m) the owner flattened over: auto = survey + 2.5 to 7 m (T1
  satellite service tunnels 49.0149, 2.5409, survey 8 m, auto 10.7; T1 spur
  `-13048`, `-10310/-10312`; 2A west `-1219/-1222` survey 6.5, auto 13.5).
  This is 4.1's mechanism.
- 15 with neither survey (< 3 m) nor owner: the 2E/2F forecourt secondaries
  `-4529/-4534/-3475/-4287` (49.0050, 2.587–2.596), which stand in the owner's
  forecourt basin already 7 m under the aprons, the auto cutting 6–7.5 m below
  that basin floor; the service tunnels at the TGV station under the T2 apron
  (`-11664` 49.0080, 2.5713; `-6050/-6055`; `-4906`; `-11828` 49.0105, 2.5751;
  `-14546` 49.0106, 2.5628); the rail portal `-20670` (49.0120, 2.5702);
  `-16019` (2E/2F west, 49.0049, 2.5775); `-6881` (2E south, 49.0010, 2.5904).

### 4.5 Ramps (38 owner ramps)

- Missing 17: the owner's ramp drop is absent from the mesh (Roissypole
  106→96, 2A south 103→97, TGV-station service 103→95, T1 west 103→96 ×3, T3
  knot 109→103, 2E/2F east 103→98 / 103→100). The survey shows ≥ 50 % of the
  owner's drop at 6 of them.
- Wrong position 8: the auto ramp is 43–225 m from the owner's (A1 south approach
  43 m; 2E/2F east 57 m and 225 m; T3 knot 49–116 m), because the auto ramp is
  planned from the mapped portal at the 5 % design grade, while the owner's ramps
  sit where the road physically descends — the survey shows that descent
  (e.g. 2E/2F east `-34535`: survey drop 3.7 m along the owner's ramp, mesh −0.5).
- Reversed 4: 2C/2D south service ramp (49.0037, 2.5823) — auto ramp `-11377`
  14.8 m deep running the other way 132–183 m off; T3 knot `-34482`, `-34556`.
- Wrong length 2: the LGV south ramp (owner 739 m at 1.3 %, auto 74 m with
  2.6 m) and a T3 knot ramp (owner 33 m, auto 214 m).
- Owner ramp grades: 6 % median; 12 of 38 steeper than 8 %, five 10–22 %.

### 4.6 Basins and the covered forecourt (not portals)

B1 (T2 central road under the viaducts) and B2 (Roissypole) are wide low levels
the survey does not show: the 1 m DTM reads the viaduct/forecourt deck, and the
owner lowers the road 7 m. 15 + 8 + 3 survey cuts the owner flattened
(e.g. the RER B trench west of T2, 49.0065, 2.5477, survey 6.4 m) are the
opposite case.

## 5. Evidence per class, and the rules as RULED (RULINGS 2026-10-28k)

The owner answered Q226–Q233 on 2026-10-27T15:56:40Z (RULINGS 2026-10-28k,
verbatim there). Where the answers depart from the draft's recommendations
they change the rules: Q228 a (R6 is IN), Q229 b (landside zones are led by
the objects and the road grading, not the survey), Q231 b (roads under the
movement area go to the 7.5 m mouth depth unless an object states another
value — this REPLACES the draft's "keep the surveyed floor if ≥ 5 m" under a
runway or taxiway), Q233 a with the owner's note (rail follows the survey and
never takes a road ramp, but at a tunnel mouth rail takes a LONGER, shallower
ramp than a road: at most 3.5 % on coarse elevation).

| class | what separates it in the inputs | rule |
|---|---|---|
| too deep / extra-on-survey-cut | the cover's level over the bore against the survey's road at the portal | R1 |
| too shallow under a runway / taxiway | the cover over the bore is movement-area pavement | R1 (231 b) |
| extra with no sign | credible survey: the cover stands less than `[channel] object_min_depth_m` over the road | R1 (232 a) |
| missing (filled survey cut) | the survey's both-sides cut along the approach, a ribbon solved > 0.5 m above it | R2 (after attribution) |
| missing under a hard deck (F1) | pack `ATTR_hard_deck` object over the road, survey notch under it | R3 (227 a) |
| ramp missing / position / reversed | the survey's own descent along the mapped road | R4 |
| too shallow (rail) | `railway=*` on the bore | R5 (233 a) |
| forecourt under stacked viaducts (B1) | OSM ways `bridge=yes`, `layer ≥ 2` running over a `layer ≤ 0` road for ≥ 100 m inside the aerodrome boundary | R6 (228 a) |
| owner's landside zone level (B2) | the pack's tunnel-mouth objects, buildings and the road grading law | R7 (229 b) |
| owner flattened a survey cut | no witness separates it; RULED keep the survey's cut | (230 a) |

**R1 — THE MOUTH IS MEASURED FROM THE COVER, never from ground already inside
the cut (226 a, 231 b, 232 a; amends 14f and 27g).** ONE derivation
(`planar/mouth_datum.py`) states every unauthored OSM bore mouth's floor; the
mouth planner, the constraint generator (`Tunnel.depth_m`), the published
mouth depths and the census's `tunnel_mouth_canonical` read that one value.
- `cover` — on a CREDIBLE inset (`inset_class.lidar_credible`), the median
  over the bore's first 40 m inside the portal of the higher of the survey on
  the bore's axis and the lower of the two sides' highest ground within
  `4 × mouth_depth_m` (§45's `_lidar_cut` reading, ratified 09-16g). On a
  coarse DEM the cover is the DEM at the mouth's cap, as today (14f), with
  §33 (3)'s embankment cap.
- `road` — the survey's road at the portal: the least of §45's
  `_lidar_floor` (minimum across the carriageway) over the portal and the
  approach's first 12 m.
- `clearance = cover − road`.
- **No sign (232 a).** On a credible inset, `clearance <
  [channel] object_min_depth_m` (3.0): neither the survey nor a ground rise
  shows a cut, and the mouth is refused by name. On a coarse DEM a missing
  rise is no evidence (a 7 m trench is below a 30 m grid) and 14f stands.
- **The depth owed.** Under the MOVEMENT AREA (a runway- or taxi-family cell
  over the bore's first 40 m) the road goes to `cover − mouth_depth_m` (7.5 m,
  231 b). Elsewhere (aprons, roads, ground) a road that already clears
  `[tunnel] clearance_m` (5.0) under its cover is kept, else cut to
  `cover − clearance_m` (232 a, 27g's blend). A RAIL bore is never deepened
  (R5): its floor is the survey's.
- `floor = min(road, cover − depth owed)`. Where the floor is the surveyed
  road (`road − floor ≤ split_tol_m`), the survey already carries the road and
  the mouth is refused by name — nothing is cut a second time (the double cut
  of §4.1). Otherwise the mouth is built at `floor`, and its depth under the
  cap's ground (`DEM(cap) − floor`) is the tunnel's `depth_m`, the value the
  constraint generator ties the mouth to its cap by.
- **An object states the value (231 b exception).** A pack portal (`pin`), a
  tunnel wall object, a door well or a wall corridor keeps its own depth; an
  object deck over the ramp keeps its `bridge.clearance_m` band (20am).

**R2 — A surveyed open cut is carried into the surface (230 a).** Where the
credible survey shows a road in a both-sides cut and R1 builds no mouth there
(the survey carries it), the road's ribbon may not be lifted out of the
survey's trench by more than `split_tol_m`. LANDS ONLY AFTER ATTRIBUTION: one
`v2_solve_replay --probe-site` at each §4.2 site names the pass that lifts it
(the groundside road grade cap, or the 22n airside face across a hard deck).

**R3 — Under an airside hard-deck bridge over a surveyed road the trench is
opened (227 a; lifts the 22n hold for this witness, with 26p).** A pack object
with `ATTR_hard_deck` whose deck stands flush on airside pavement (22n class A)
and under which the survey notches a mapped road: the terrain under the deck
footprint is cut to the surveyed road, the deck seated flush at the solved
airside (22n (2)), the cut stopping at the deck's outline (20as / 20am). This
is #1138's trench at LFPG's witness and is built through #1138's spec.

**R4 — The approach ramp lies where the survey descends.** On a credible inset
a ramp built at an R1 floor climbs at the design grade only where the
survey's road stands above it; where the survey's own road descends steeper
than the design grade toward the mouth, the ramp takes the survey's descent up
to `tunnel.ramp_max_grade` (the residual reported), so the ramp tops out where
the survey's road meets it and is never cut below the surveyed road along
the approach. On a coarse DEM the design ramp stands.

**R5 — Rail (233 a).** A `railway=*` bore takes no road ramp. On a credible
inset its floor is the survey's (R1, never deepened). At a tunnel mouth rail
takes a LONGER ramp than a road: design grade `[tunnel] rail_ramp_grade`,
ceiling `[tunnel] rail_ramp_max_grade` (new law keys; see the source note
below).

*Rail grade law (233 a's "at most 3.5 %").* `law/*.toml` held one rail grade,
`emit.toml [road_cross_section] "railway:rail" = 0.04` — a LOW-CONFIDENCE ribbon
cap from one adhesion-practice source, not a tunnel-ramp law. Proposed, with
their source: `rail_ramp_max_grade = 0.035` — the EU Technical Specification
for Interoperability, Infrastructure (TSI INF, Regulation (EU) 1299/2014,
§4.2.3.6): main tracks of passenger-dedicated lines up to 35 mm/m (the LGV
lines are built to it), the owner's figure; `rail_ramp_grade = 0.0125` — the
same TSI's 12.5 mm/m design limit for mixed-traffic lines (the owner's LGV
south ramp at F6 runs 1.3 %).

**R6 — A road under stacked viaducts inside the airport sits a mouth depth
below the apron (228 a).** A mapped road (`layer ≤ 0`) running at least
100 m under bridge ways of `layer ≥ 2` inside the aerodrome boundary is lowered
to `apron − mouth_depth_m` along the covered run, with R4 ramps at both ends;
emittable only as an open road level under the viaduct objects (§7).

**R7 — A landside zone takes the level its objects and its roads set, not
the survey's (229 b).** Inside the aerodrome boundary a landside zone (B2) is
levelled to the tunnel-mouth objects' floors, the building pads' seats and
the road grading law (a road leaving a lowered mouth climbs at its grade cap),
the survey only where none of these states a level.

## 6. Consumer census (RULINGS 2026-08-30l)

| pass (module) | reads | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|---|---|---|---|---|---|---|---|
| `planar/structures.py` mouth datum (`mouth_dem`, `mouth_z`, crest cap) | DEM at the cap | **changes** (crest from the cover; floor from R1) | – | reads R1 floor | – | rail branch | – | – |
| `planar/lidar_road.py` (27g) → `planar/mouth_datum.py` | §45 cut along the bore | **replaced** by the one R1 reading (cover, road, clearance, the depth owed, the refusals) | – | under-deck witness reuses it | – | rail never deepened | – | – |
| `planar/channel_geometry.py` `_lidar_cut` / `_lidar_floor` | survey both sides | read only | read only | read only | read only | read only | – | – |
| `planar/structure_mouth.py` `road_profile`, `mouth_at_pavement`, slide | mouth floor, road | reads new floor | – | – | **changes** (profile from survey) | rail grade | ramps at both ends | – |
| `planar/structure_approach.py` (approach walk, `standing_cover`) | approach ground | reads | – | – | reads | – | – | – |
| `planar/bore_continuation.py` (#1028 "no portal") | bore chains | – | – | – | – | rail chains | – | – |
| `planar/covered_ground.py`, `planar/structure_deck`, `planar/structure_underpass` | decks over roads | – | – | **changes** (cut under hard deck) | – | – | – | – |
| `airport/tunnel_objects.py`, `portal_objects.py`, `object_cut.py` | pack portals, floors | pinned mouths unchanged (R1 skips `pin`) | – | reads deck outline | – | – | – | – |
| `classify/ribbon_mint.py`, road grade law (`roads.groundside_road`) | road ribbons | – | **changes** (survey datum, cap lift) | – | reads | – | reads | reads (grade cap) |
| `planar/zones.py` adjacent-ground blend | DEM | – | must not fill a declared cut | – | – | – | – | **changes** (zone level from objects / roads) |
| `constraints/structures.py` (mouth/wall rows) | mouth floor, walls | rows at new floor | terrace rows for surveyed walls | rows under deck | – | – | – | – |
| `emit` tunnel canonical (`law/emit.toml` §33 (5)) | `rim − mouth_depth_m` | **changes** to R1's floor | – | – | – | – | – | – |
| object stage deck seating (`auto_patch/object_stage.py`, `emit/rebake.deck_datum_from_surface`) | solved airside at the deck | – | – | deck stays flush (22n (2)) | – | – | – | reads (pad seats) |
| census (`tools/harness/law_support`, families `tunnel_mouth_canonical`, `ramp_in_strip`, 19c/19l exemptions) | mouth floor law | price at R1 floor | surveyed walls = declared terraces | object-decked trench (19c) | ramp grade | rail cap | – | – |
| `verify/structures.py`, `verify/keepout.py` | mouth depth | R1 | – | – | – | – | – | – |

Prefer one derivation site: R1 is ONE function (`planar/mouth_datum.mouth_datum`,
the cover/floor of a mouth) whose floor the mouth planner builds and whose
depth (`Tunnel.depth_m`) the constraint generator, `pipeline/publication.
tunnel_mouth_depths` and the census's `tunnel_mouth_canonical` read — never
three readings.

## 7. Acceptance against the hand patch, and emittability

Measured relative to the crest in each surface (§2), on LFPG tile +49+002,
one build against its matched control (the lane's instrument rasterises the
emitted patches; the counts in §4 read the owner's built mesh, so the lane
reports its own before/after on one instrument):

1. Too deep: no unauthored mouth floor more than `mouth_depth_m + 1.5 m`
   (9.0 m) under its cover; the too-deep count falls.
2. At the owner-cut portals under the movement area, auto depth within 1.5 m
   of the owner's or of `mouth_depth_m` (231 b), whichever is deeper than the
   survey; elsewhere within 1.5 m of the owner's or within 0.5 m of the survey
   (230 a).
3. Extra with no sign (232 a): refused by name on a credible inset.
4. Missing (filled): mesh floor ≤ survey floor + 0.5 m at the §4.2 portals
   once R2's lifting pass is attributed and ruled; F1 within 1.5 m of the
   survey's 111 m under R3.
5. The match portals: depth within 1.0 m of the control's.
6. Ramps: no ramp cut below the surveyed road along its approach (R4).
7. No regression: the census of the closing build has no new
   `ramp_in_strip` or `tunnel_mouth_canonical` rows outside the declared
   exemptions; a dry structure A/B on the registered captures (KATL, KCLT,
   EGGW, EGLL, KBUF, NZWN) lists every mouth that changes.

## 8. Owner questions (answered 2026-10-27T15:56:40Z: RULINGS 2026-10-28k)

**Q226 — How should the auto patch be judged against your LFPG patch?** Your
patch's levels sit 0–7 m (≈ 3 m typical) below the 2026 survey, which matches the
published runway threshold elevations to 0.05 m.
- A. Depth below the surrounding ground (recommended)
- B. Absolute elevations as in your patch

**Q227 — A1 under runway 09L/27R, west end (49.0256, 2.5363):** the pack's
runway bridge (`H19`, a hard deck) stands over the A1; your patch opens a 55 m
wide trench 7 m under the runway for 247 m; the survey shows the road 6 m under
the runway; the auto build fills it to runway level (22n hold).
- A. Lift the 22n hold where a hard-deck bridge stands over a road the survey
  shows: cut to the surveyed road under the deck (recommended)
- B. Keep the hold

**Q228 — T2's central road between 2A/2C and 2B/2D, under the departure and
arrival viaducts (49.0039, 2.5670):** your patch lowers it 7 m below the aprons
for 1.2 km; the 1 m survey reads it at apron level (it sees the viaduct deck).
- A. A road running ≥ 100 m under viaducts mapped at layer 2 or higher, inside
  the airport boundary, sits 7.5 m below the apron (R6)
- B. Follow the survey (recommended until the 50 cm LiDAR-HD tier answers; it
  was refused, HTTP 400, on this build)

**Q229 — The Roissypole zone between Terminal 1 and Terminal 2 (49.0098,
2.5631):** your patch puts the whole zone 6 m below the aprons; the survey
reads it 2–3 m below.
- A. Follow the survey (recommended)
- B. Lower whole landside zones to your patch's level

**Q230 — Survey cuts your patch flattens** (23 portals, e.g. the RER B trench
west of T2 at 49.0065, 2.5477, 6 m deep; Terminal 1's lower service roads at
49.0149, 2.5409, 8 m):
- A. Keep the survey's cut (recommended)
- B. Flatten them as your patch does

**Q231 — Where your patch is deeper than the survey and the survey clears 5 m**
(the A1 under runway 09R/27L at 49.0204, 2.5337: yours 9 m, survey 4–5.6 m; the
TGV line under the north runways at 49.0218, 2.5690: yours 12–17 m, survey
10 m):
- A. The survey decides (27g: 5 m under a deck is enough) (recommended)
- B. Top every road under a runway or taxiway up to the 7.5 m mouth depth

**Q232 — Tagged tunnels with no sign of a cut** (15 portals: service roads under
the T2 apron at the TGV station, 49.0080, 2.5713; the 2E/2F forecourt secondaries
at 49.0050, 2.5900, which already sit 7 m under the aprons):
- A. No cut where the road already clears 5 m under the apron, or where neither
  the survey nor a ground rise shows one (recommended)
- B. Keep cutting 7.5 m at every tagged portal

**Q233 — Railway tunnels and trenches (the TGV line north of the airfield and at
the TGV station between 2C/2D and 2E/2F):**
- A. Rail follows the survey and never gets a road ramp; on coarse elevation a
  rail ramp at 3.5 % (recommended)
- B. Rail gets the road tunnel law

## 9. Not done here (draft round)

- No engine code changed; no capture taken and none registered
  (`frames.py list LFPG` was not needed: the measurement read the owner's built
  tile, its auto patch and report directly).
- 4.2's mechanism (which pass lifts the road over a survey cut) is not
  attributed; R2 waits for one `v2_solve_replay --probe-site` per site.
- The pack objects' own stated depths (`H17` deck 9.3 m over its origin,
  `H19` 12.9 m, `H7` 6.7 m) were not reconciled with the owner's 7 m: whether
  an object's origin is its road level is not established.
- No LiDAR-HD retry (the 50 cm tier answered HTTP 400 on the owner's build).

## 10. As built (lane `llfpgcut`, 2026-10-27)

Implemented on `claude/llfpgcut-cuts-tunnels` (one derivation,
`planar/lidar_road.survey_mouth`, called once per unauthored OSM bore group
in `planar/structures.build_structures`):

- **R1.** `cover` = the higher of the SURROUNDING GROUND (the survey's upper
  quartile on the 25–60 m annulus round the portal — §2's own crest, 226 a)
  and the cover OVER THE BORE (median over its first 40 m of the higher of
  the axis survey and §45's lower-side top); `road` = the least of §45's
  `_lidar_floor` over the portal and the approach's first 12 m. The annulus
  was added after the first arm: a dual carriageway's trench (the A1, 55 m)
  is wider than either side's 30 m reach, and the over-bore reading alone
  called the A1 portals "no sign". DEVIATION FOR THE MASTER: 231 b is read as
  "every road under AIRSIDE PAVEMENT" — a runway, taxi or apron cell, or a
  pack hard-deck object, over the bore anywhere along it (LFPG's A1 bores
  under 09R/27L run under the H17/H18 decks and under no cell) — owed 7.5 m;
  232 a's 5 m keep applies elsewhere (ground, buildings, groundside roads).
  A role split runway/taxi vs apron (the questions' literal wording) fitted
  the owner's patch worse: his T1 and 2E/2F roads stand 7–9 m under the
  aprons where the survey reads 5.7–7.1.
- The depth goes to the solve: `Tunnel.depth_m = DEM(cap) − floor`. Before,
  a 27g blended floor (`mouth_z`) was overridden in the constraint
  generator, which tied the floor to `cap − mouth_depth_m` whenever
  `depth_m` was 0 — measured on the 1.0.436 LFPG patch, `tunnel:-10256` was
  floored at 88.87 (= 96.36 − 7.5) against its planar 95.54, `-413` at 91.43
  against 98.50. This was the double cut's second half.
- **R4.** A survey mouth's design grade is `ramp_grade + the surveyed road's
  own rise over the closing length`, capped at `ramp_max_grade`.
- **R5.** `[tunnel] rail_ramp_grade = 0.0125`, `rail_ramp_max_grade = 0.035`
  (EU TSI INF §4.2.3.6), checked at load; a rail bore on a credible survey
  is never deepened.
- **R2, attributed.** `v2_solve_replay --why-at` on the base replay: the A1
  north portal (49.0263, 2.5367) is a pavement face held at H19's deck datum
  118.65 by the objective (22n — R3's class); the Roissypole primary road
  (49.0109, 2.5509; its tunnel's east end is a #1028 "no portal") and the 2A
  south service portal (49.0029, 2.5543) are a taxiway's adjacent-ground
  `graded_strip` (zone 1 / 2) held by the objective and `zones.
  adjacent_ground` — NOT the road grade cap. Built: a mouth the survey
  decides keeps the zones off its open approach trench (`survey_trench`, a
  keepout like the corridor it replaces, bounded by `clearance / ramp_grade`;
  measured necessary at CYXY `tunnel:-725`, whose kept mouth otherwise gave
  its approach to the strip zone). Built after the owner's Q245 "Yes"
  (2026-10-27): a taxiway's zone 1/2 gives way to a surveyed trench inside it
  (`lidar_road.survey_road_trenches`, cut at `zones.zone_regions`, the zones'
  single derivation site): every mapped road through a taxiway band whose
  credible survey reads §45's both-sides cut over two or more 5 m stations
  (read one cut reach past the band) takes a trench as wide as the
  carriageway + rim stand-off + 1:1 bank (bank ≤ 2 × `mouth_depth_m`) out of
  the TAXIWAY bands, with the keepout stand-off; a runway strip never yields;
  a coarse DEM reads nothing (14f). Consumer census: the zone regions are its
  only reader — every pass downstream reads the trimmed region, as for any
  keepout trim. Reported on the terrain-edge line. Twins:
  `tests/auto_patch_v2/test_taxi_zone_trench.py`.
- **R6, built (round 2, after 28p).** `planar/viaduct_road.viaduct_road_groups`,
  called once in `build_structures` beside the §34 (5) underpasses: a mapped
  road (`layer <= 0`, not bridge/tunnel) running `[tunnel] viaduct_min_run_m`
  (100) under `highway`/`railway` bridge ways of `layer >= viaduct_min_layer`
  (2) inside the apt.dat boundary, read along its heading-keeping ROUTE through
  the forecourt's many short ways (least turn at every node, none over
  `approach_turn_max_deg`; two parallel carriageways within
  `dual_carriageway_max_separation_m` are one trench), becomes two sibling
  Law-B (`sunken_road`) halves meeting capless at the run's midpoint: level
  at `apron − mouth_depth_m` (apron = median DEM at the nearest edges of the
  airside apron cells within `viaduct_apron_reach_m`, 300), climbing back to
  the ground beyond the run on the mapped road at the design grade, or —
  where no mapped road carries the climb, or the road curls more than 45°
  within one trench width — INSIDE the run, steepening up to
  `ramp_max_grade`. The generator pins the profile per station (Law B's
  existing rows); the mouth-law readers exempt it as every non-OSM source.
  Dry: LFPG `viaduct-road:0` (T2 central service road, 49.00354, 2.56225;
  floor 99.33 = apron 106.83 − 7.5, 35 m wide, 331 m run), `viaduct-road:1`
  refused by name (the climb does not fit its 140 m run); KATL
  `viaduct-road:0` (33.64154, −84.41815, floor 283.39, 250 m run). Twins:
  `tests/auto_patch_v2/test_viaduct_road.py`. NOTE: the owner's B1 is a
  ~260 m wide flat polygon at 96 m (his `altitude=96` way spanning
  49.0029–49.0052, 2.5600–2.5770), not a road trench; R6 as ruled lowers
  the mapped road only.
- **NOT built:** R3 (227 a, #1138's trench under a hard deck — the runway
  faces under the deck must be cut out and re-roled; its own spec/census;
  batch AK's `bridge_span` serves EDGE-WALL bridges, not `ATTR_hard_deck`
  decks, so it does not build R3 either), R7 (229 b: no "landside zone"
  region and no level source beyond the objects is specified — it replaces
  the groundside ground's DEM term inside the boundary for every airport, a
  solver-objective change that needs its own spec and consumer census).
