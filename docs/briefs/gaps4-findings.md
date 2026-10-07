# gaps4 findings — pavement gaps at HECA, measured for the spec author (2026-10-06)

Lane `gaps4` MEASURED AND RECORDED; it designed nothing and enabled nothing.
Branch `feature/pavement-gaps`. Issues #292, #358, #430; RULINGS 2026-10-04q,
04u, 06a, 06b. The record of the round is spec §53 (18).

Frames (all under `/Users/noah/XPTerrainBuilderData/.harness/frames/gaps3/`):
`BASE/` (sheet-free replay, body sha `09847984ac94` = main's HECA) and `ARM/`
(`--late-from BASE/solved.pkl`, body sha `21ac4385b6a8`, 2,274 ways / 41,974
nodes), both solved on `5e7e5144`; capture `HECA.pkl`. Reader:
`tools/v2_late_read.py` (bars) and its `--site` (`tools/v2_late_site.py`, new
this lane). "DEM" is the capture's own `Airport.dem` (production frame).

READING CAUTION for every section below: a gap piece carries vertices on its
RIM only (`gap:7`: one face, 58 vertices, all on the rim). A level inside a
piece is read on the face's own triangulation of those rim vertices; the tile
mesh may triangulate the interior differently. Slopes "inside the piece" are
therefore slopes of that triangulation, not of solved interior vertices.

## 1. Owner sites — numbers first

| site | BASE at the point | ARM at the point | DEM | ARM against its neighbours |
|---|---|---|---|---|
| #430 lot 30.1154841, 31.4105884 | no face (the mesh's own ground, 102.11) | `groundside_pavement:gap:7`, 97.65 | 102.11 | toward the road at 30.115331, 31.4106152: piece 97.62–97.72 over 28 m (0.1–0.5 %), rim 97.27, then `service_road:route3` 97.05 three metres on (0.22 m); across: 0.18 m to `route3` over 4 m. BASE: the road stands at 97.05–97.16 where the ground beside it is 102.6–103.0. |
| #292 lot 30.1159784, 31.4106264 | no face (101.86) | `gap:7` (THE SAME PIECE AND FACE as #430), 97.09 | 101.86 | falls north from 97.83 to 93.66 over 52 m (8.2–8.7 % by 4 m, worst 10.4 % over 1 m) toward `apron:pav37` (92.08–92.84 on the shared rim); west–east 2.8 %, worst 3.6 %. |
| #358 pavement 30.1193169, 31.4085087 | no face (96.94); beside it ribbon `small_roads:-20210` at 96.33–96.66, i.e. 6.73 m above `apron:pav37` (89.57) two metres away | `groundside_pavement:gap:0`, 90.24 | 96.94 | continuous: `apron:pav37` 89.57 → ribbon `-20210` 89.67–89.92 → piece 90.07–90.79 → pad `building:building26` 90.79 (the building at 30.1191963, 31.4082803); worst level difference between two faces 0.07 m; worst slope 8.5 % over 1 m ON THE RIBBON; 1.7 % along the piece (worst 9.5 % over 1 m across the line). Across the line the piece's rim stands at 90.79 seventeen metres from pad `building63` at 86.04 (4.74 m, faceless ground between). |

Verdict by site, against what the owner asked (the read is the ARM, which is
NOT enabled in a build):

- #430: the ARM grades the place as a flat lot at the road's level (0.22 m
  from the road, 4.5 m under the DEM). MET in the arm, with two residues:
  the piece's triangulation folds near the road rim (24.5 % and 32.7 % over
  1 m at s=+15 / s=+28 of the two sections: rim vertices at 98.64 and 97.76
  three metres apart), and the pair `gap:7 | route3` is counted STEPPING at
  0.25 m over 1.58 m (30.1162375, 31.4097695; 0.12 m over the cap).
- #292: the ARM replaces a 9 m drop at the apron rim (DEM 101.2–101.9 against
  `pav37` 92.1–92.8) by one plane falling at the road cap to the apron. It
  is at or just over the 8 % cap for 50 m. Whether that is "smooth with the
  adjacent airside" is the owner's to read.
- #358: the ARM reads the pavement as continuous from the apron to the pad.
  MET in the arm. In the BASE the ribbon `small_roads:-20210` is the thing
  the owner saw: a road 6.7 m above the apron beside it.

### gaps3's lead: CONFIRMED as a number, on the OTHER piece

`gap:8 (10,136 m2) | service_road:route3`: 3.91 m (piece 101.07 against road
97.16, 1.41 m apart) at 30.1152588, 31.4106360 — confirmed. But `gap:8` is
the piece SOUTH of `route3`; the owner's #430 lot is `gap:7`, NORTH of it,
and meets the road within 0.22–0.25 m. `gap:8`: two faces, 83 vertices,
levels 96.42–107.14, no welded neighbour at all (2,279 m of rim on the mesh's
own ground), stand-off neighbours `route3` (815 m of its rim within 2.1 m)
and `apron:pav111` (0.01 m at 30.1149386, 31.4106360; 25.8 m of rim within
2.1 m). Across `route3` from the #430 lot the arm reads `gap:7` 97.27 →
`route3` 97.05–97.16 → `gap:8` 103.6 eight metres on (6.47 m): the road sits
in a trench between the two pieces, and only the north side comes down to it.

### Site tables

`gap:7` (10,601 m², one face, 58 vertices of which 54 unknown, levels 92.08–100.35):

| neighbour | how | length / distance | levels | step |
|---|---|---|---|---|
| `apron:pav37` | welded (shared edge) | 112.2 m in 2 runs (75.1 m longest), centred 30.1164328, 31.4104489 | 92.08–92.84 | 0 (shared vertices); stand-off part 0.01 m |
| `service_road:route3` | stand-off (1.45 m) | 375 m of the rim within 2.1 m | road 92.05–100.47 along the piece | worst 0.25 m over 1.58 m at 30.1162375, 31.4097695 (STEPS by 0.12 m) |
| the mesh's own ground | no face across the rim | 1,203.8 m | piece rim 92.11–100.35; DEM 101–104 | the piece stands 4–5 m under the DEM along this rim |

`gap:0` (709,001 m², 6 faces, 5,507 vertices, levels 62.35–105.07) at the #358 site:

| neighbour (local to the site) | how | levels | step |
|---|---|---|---|
| `apron:dsf:objpav68` | welded, 333.0 m | 89.68–91.93 | 0.00 m |
| `apron:pav37` | welded 3 vertices; stand-off 0.50 m | 89.13–92.05 | 0.01 m |
| `service_road:small_roads:-20210` (OSM `highway=service`, follower ribbon) | welded, 47.7 m | BASE 96.33–96.66, ARM 89.32–90.11 | 0.07 m to the apron in the ARM (6.73 m in the BASE) |
| `building:building26` | stand-off 1.10 m | 90.79–90.86 | piece 90.79–90.80 at the pad here (the piece's 5.22 m pair with this pad is 370 m south, see §3) |

The whole piece has 29 welded neighbours (1,746 m of apron rim on `route11`,
`objpav68`, `pav53`, `pav39`; 26 OSM ribbons) and 80+ stand-off neighbours;
the full list is in the reader's output (`--site 358-pavement …`).

## 2. Bars (ARM against BASE, 0.02 m; held = round 12–13, `gaps2-hold/A2/late.log`)

| bar | this lane (merged tree `5e7e5144`) | held |
|---|---|---|
| fixed vertices off their constant (existing movers) | 0 of 34,540 (worst 0.000 m) | 0 |
| foreign vertices on standing faces | 0 | 0 |
| standing way groups identical to the base | 1,152 of 1,152 | 1,152 / 1,152 |
| follow rows missed by > 0.02 m | 165 of 1,583 — pad 121, apron 22, other 22; 25 conflict vertices; worst 5.23 m at 30.1159894, 31.4079381 (`building26`) | 165 of 1,583 (121 / 22 / 22) |
| stepping pairs across the stand-off | 68 of 147; 52 on pieces ≥ 1,000 m² | 68 of 147; 52 |
| follower ribbons whose worst offset grew > 0.1 m | 5 of 59 (47 with a fixed vertex within 6 m): one OVER the road cap (`small_roads:-3927` 0.54 → 1.39 m, 67.2 % over 2.06 m at 30.1262730, 31.4057686, no follow row on the vertex), four slopes within the cap over 4.7–5.9 m | 8 of 59 |
| join | 68 gap faces, 60 follower ribbons, 8,476 follower vertices (363 held on a leader); 43,010 vertices of which 34,540 fixed, 6 held at identity, 0 unjoined, 0 rim nodes off an edge | — |

Every bar equals its held value except the ribbons (5 against 8; not
attributed — the reader's ribbon section was reworked between the two reads,
`cf4527d5`).

Census (`tools/harness/census.py`, law-true, ruleset `icao` from the sidecar):

| | BASE | ARM | Δ |
|---|---|---|---|
| ADJUDICATED | 14,187 (airside 12,362, groundside 1,821, mixed 4) | 14,720 (airside 12,306, groundside 2,410, mixed 4) | +533 |
| LAW-TRUE TOTAL | 55,830 | 56,527 | +697 |
| within_shape | 45,699 | 46,140 | +441 |
| hairline_pair | 1,565 | 1,729 | +164 |
| road_cross_section | 402 | 506 | +104 |
| road_coverage_join | 0 | 32 | +32 |
| pavement_over_road_cap | 15 | 26 | +11 |
| terrace_actual_step | 0 | 4 | +4 |
| hard_conflict | 264 | 207 | −57 |
| airside_no_step | 4,020 | 4,018 | −2 |
| every other family (taxi_box 2,448, transverse 920, strip_* …) | equal | equal | 0 |

Airside adjudicated FALLS by 56 (12,362 → 12,306) with no standing vertex
moved; which rows leave is not read out (found, not attributed).

## 3. The worst stepping pairs (ARM; piece | standing neighbour; level difference beyond nothing — the raw difference; distance across the stand-off)

| piece (m²) | neighbour | difference | piece vs neighbour | apart | at |
|---|---|---|---|---|---|
| gap:5 (28,284) | building7 | 5.28 m | 95.07 / 100.39 | 2.00 m | 30.1126959, 31.3972667 |
| gap:0 (709,001) | building26 | 5.22 | 96.05 / 90.80 | 1.80 | 30.1159894, 31.4079381 |
| gap:5 | building6 | 4.51 | 96.52 / 92.03 | 1.25 | 30.1125378, 31.3958556 |
| gap:0 | building59 | 4.45 | 87.17 / 91.65 | 1.80 | 30.1193496, 31.4068328 |
| gap:4 (35,542) | building4 | 3.95 | 101.04 / 97.06 | 1.72 | 30.1104675, 31.3957315 |
| gap:8 (10,136) | route3 | 3.91 | 101.07 / 97.16 | 1.41 | 30.1152588, 31.4106360 |
| gap:10 (6,019) | building10 | 3.35 | 100.37 / 103.73 | 1.58 | 30.1144784, 31.4078500 |
| gap:0 | lot pav57 | 3.20 | 94.03 / 97.24 | 1.58 | 30.1158406, 31.4089239 |
| gap:0 | building29 | 3.17 | 93.96 / 90.80 | 1.39 | 30.1161293, 31.4092663 |
| gap:15 (2,964) | route22 | 2.79 | 101.55 / 104.37 | 1.78 | 30.1029351, 31.3959144 |
| gap:10 | building9 | 2.53 | 102.09 / 99.55 | 1.58 | 30.1137432, 31.4075699 |
| gap:0 | building131 | 2.44 | 66.73 / 64.28 | 1.58 | 30.1244858, 31.3951270 |
| gap:0 | building128 | 2.30 | 67.51 / 69.86 | 2.00 | 30.1245850, 31.3949039 |
| gap:9 (6,173) | building10 | 2.06 | 101.38 / 103.45 | 1.61 | 30.1147174, 31.4079434 |
| gap:1 (57,376) | building6 | 2.06 | 89.95 / 92.03 | 1.75 | 30.1143508, 31.3944700 |
| gap:0 | building147 | 2.02 | 73.68 / 75.75 | 2.00 | 30.1272923, 31.4051407 |
| gap:5 | building4 | 1.67 | 96.99 / 98.65 | 1.19 | 30.1125020, 31.3976195 |
| gap:28 (437) | building147 | 1.55 | 72.29 / 73.82 | 1.20 | 30.1279147, 31.4044817 |
| gap:15 | apron pav6 | 1.53 | 102.47 / 100.90 | 1.98 | 30.1045003, 31.3965366 |
| gap:0 | building52 | 1.35 | 87.26 / 85.89 | 1.80 | 30.1193541, 31.4067705 |

(The reader's own column is the excess over cap × distance plus the stand-off
allowance; the pairs and their order are its top 20. 16 of the 20 are pads.)

## 4. The witness question — what the map and OSM actually say at the three sites

What exists to read, at all three: ONE pack sheet body (`dsf:gapsheet2`,
`Airport/ground/asphalt.obj`, 1,490,182 m²) covers all three points — the
sheet does not separate them. NO OSM polygon holds any of them except the
aerodrome boundary (way −98): HECA's OSM extract has no `amenity=parking`,
no `landuse`, and its 13 `aeroway=apron` areas do not reach these points.
OSM offers lines only: `highway=service` ways (kind `airport_small_roads`).

| | #430 lot | #292 "hill" | #358 pavement |
|---|---|---|---|
| piece | `gap:7`, 10,601 m² | `gap:7` — same piece, same face, 55 m north | `gap:0`, 709,001 m² (the landside network) |
| piece touches an apron (04q trigger) | yes: 112.2 m welded to `pav37` (04q's cell evidence: 139.5 m) | same | yes: 1,765 m welded in 8 runs |
| that contact after opening the aprons by 2 / 5 / 10 m (rim within 2.1 m) | 216 / 216 / 209 m — it SURVIVES | same | `objpav68` 338 / 338 / 338 m; `pav37` 238 / 237 / 222 m |
| road evidence in the piece (OSM `highway` inside) | 242 m over 3 ways (−18830 101 m, −20273 80 m, −18829 62 m) | same | 52,518 m over 475 ways |
| road along the piece | `route3` (apt.dat ground route ribbon), 375 m of rim | same | 2,025 m of rim on 12+ road faces |
| the point's distance to: apron / nearest road face / nearest pad | 60.6 m / 15.1 m (`route3`) / 63.3 m | 53.7 m / 56.4 m (`route3`) / 82.2 m | 22.5 m / 15.7 m (`small_roads:-20210`) / 24.9 m (`building26`) |
| nearest OSM ways to the point | −18830 at 4.2 m, −20273 at 4.5 m (both run through the lot) | −20273 at 15.3 m | −20210 at 19.3 m (between the point and the apron) |
| the piece opened by 2 / 5 / 10 m | 1 part of 9,505 / 9,488 / 9,431 m² holds both #430 and #292 (three slivers < 130 m² fall off at 2 m) | same part | 34 / 118 / 90 parts; at 10 m the site sits in a part of 11,302 m² that touches the apron and has `route3` and `-20210` within 2.1 m |

Statements:

1. "LOT JOINED ONLY TO A ROAD" (#430, RULINGS 06a) — NO WITNESS IN THE MAP
   SAYS THIS ABOUT THE OWNER'S LOT. Its piece `gap:7` is welded to apron
   `pav37` over 112 m, and that contact survives opening both the apron and
   the piece; `route3` is its only road. Read literally, 06a's rule ("a piece
   whose only fixed neighbour is a road") does NOT select `gap:7`, and 04q
   sends it to class (i) (apron contact + road evidence = a road leaving the
   apron) or (ii). The 04q record's "143 m of `pav37` contact is a fringe
   (0 m survives a 2 m opening)" could NOT be reproduced by this lane's
   reading (above); the two were measured differently (round 1 was before
   the stand-off) and the difference is not attributed.
   What the map DOES say that is particular to the lot: the apron contact is
   at the far (north-west) end, 105 m from the lot point and 5 m lower
   (92.1–92.8 against the road's 97.0–97.7 at the lot); two OSM service ways
   run through the lot part; the lot part is 15 m from `route3`.
2. #430 AND #292 ARE NOT SEPARATED BY ANYTHING: one sheet body, one piece,
   one face, no neck at 2, 5 or 10 m, no OSM area, no pavement or cell
   boundary between them. If the owner means two different treatments (a lot
   at the road's level; a slope that blends into the airside), the map holds
   no line between the two. The only difference is position: which fixed
   neighbour is nearer (road 15 m against apron 61 m at #430; apron 54 m
   against road 56 m at #292), and the 5 m between those neighbours' levels —
   which is what the ARM's single plane already expresses (flat by the road,
   falling at the cap to the apron).
3. "PAVEMENT CONTINUOUS WITH THE APRON" (#358): no PIECE-level witness —
   `gap:0` is the whole landside network and satisfies every 04q clause at
   once (broad apron contact AND mouths AND 52 km of road evidence). A LOCAL
   witness exists only after the piece is divided: at a 10 m opening the
   site's part (11,302 m²) is welded to the apron and bounded by a pad. The
   opening width is a threshold of the reader's choosing — that is a design
   decision, not a measurement. Note the OSM service way `-20210` lies
   BETWEEN the apron and this pavement, so "road evidence" is present at the
   one site where the owner reads the pavement as apron.
4. A general separation the measurements do support, stated without choosing
   it: per place, the set of FIXED NEIGHBOURS WITHIN REACH and the level
   difference between them. #358: apron and pad 50 m apart, 1.2 m apart in
   level — one continuous surface satisfies both. #430 / #292: road and apron
   5 m apart in level over 100+ m — one plane at the cap satisfies both.
   `gap:8` (south of `route3`): the road 4–6 m under the piece's other rim —
   the terrace-inside-the-piece case of 04u.

## 5. No-op and determinism

NO-OP AND DETERMINISM (lane `gaps4`, tree `b4f3f99d` = the branch with main `6f06e41b` merged; `tools/harness/build_airport.py`, tags `g4b_<ICAO>`, write guard armed, nothing blocked; the gap stage is not enabled in a build):

| airport | body sha | main's | |
|---|---|---|---|
| CYXY | `2a00c361ffc2` | `2a00c361ffc2` | equal |
| SPJC | `9d611f11e04b` | `9d611f11e04b` | equal |
| KCLT | `795da9629004` | `795da9629004` | equal |
| KASE | `738c2a8ceb64` | `738c2a8ceb64` | equal |
| NLWF | `84be89f8b7bc` | `84be89f8b7bc` | equal |
| OTHH | `88794a1d264b` | `88794a1d264b` | equal |
| HECA (sheet-free replay, `gaps3/BASE`) | `09847984ac94` | `09847984ac94` | equal |
| HECA ARM replay, default pool (8 workers) | `21ac4385b6a8` | = `gaps3/ARM` (solved on `5e7e5144`) | equal |
| HECA ARM replay, `--workers 1` | `21ac4385b6a8` | = the default | equal |

(CYXY, SPJC, KCLT, KASE and NLWF were also built on the tree before main `6f06e41b` was merged, tags `g4_<ICAO>`: the same five shas.)

## 6. Found, not fixed

- `tests/test_elevation_gap_census_providers.py::test_providers_mode_reads_the_engine_ladder_offline`
  failed once in the `-n auto` suite while a KCLT build held every core and
  passed alone (3 passed) — load-sensitive, not this branch's.
- `tools/v2_late_read.py` has no twin of its own (its `--site` extension has
  one: `tests/test_v2_late_site.py`).
- The census's airside adjudicated count falls by 56 in the ARM with no
  standing vertex moved — not attributed.
- Ribbons grown > 0.1 m: 5 here against the held 8 — not attributed.
- 04q's "fringe" reading of `gap:7 | pav37` does not reproduce (statement 1).
- In the BASE (= main) `route3` stands 5.5–5.7 m under the DEM beside the
  #430 lot (97.05 against 102.72) and `small_roads:-20210` stands 6.7 m above
  the apron two metres from it at #358: both are main's own, both are what
  the owner sees today.

## 7. Sections (1 m samples; every 4th row and every face change shown; `-` = no face)

**430-lot — section toward 30.1153310, 31.4106152 (17.2 m off)** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | - | gap:7 97.81 | 101.98 |
| -36 | - | gap:7 97.79 | 101.95 |
| -32 | - | gap:7 97.77 | 101.92 |
| -28 | - | gap:7 97.76 | 101.89 |
| -24 | - | gap:7 97.74 | 101.86 |
| -20 | - | gap:7 97.73 | 101.88 |
| -16 | - | gap:7 97.71 | 101.91 |
| -12 | - | gap:7 97.69 | 101.95 |
| -8 | - | gap:7 97.68 | 101.99 |
| -4 | - | gap:7 97.66 | 102.05 |
| +0 | - | gap:7 97.65 | 102.11 |
| +4 | - | gap:7 97.63 | 102.18 |
| +8 | - | gap:7 97.62 | 102.26 |
| +12 | - | gap:7 97.72 | 102.44 |
| +16 | - | - | 102.63 |
| +18 | road route3 97.05 | road route3 97.05 | 102.72 |
| +20 | road route3 97.11 | road route3 97.11 | 102.81 |
| +24 | road route3 97.16 | road route3 97.16 | 103.01 |
| +25 | - | - | 103.06 |
| +26 | - | gap:8 | 103.11 |
| +27 | - | - | 103.17 |
| +28 | - | - | 103.22 |
| +32 | - | gap:8 103.63 | 103.43 |
| +36 | - | gap:8 103.78 | 103.64 |
| +40 | - | gap:8 103.93 | 103.86 |

**430-lot — section across that line** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | - | gap:7 98.69 | 103.62 |
| -36 | - | gap:7 98.49 | 103.37 |
| -32 | - | gap:7 98.28 | 103.13 |
| -28 | - | gap:7 98.08 | 102.90 |
| -24 | - | gap:7 97.98 | 102.69 |
| -20 | - | gap:7 97.89 | 102.48 |
| -16 | - | gap:7 97.79 | 102.30 |
| -12 | - | gap:7 97.70 | 102.24 |
| -8 | - | gap:7 97.63 | 102.18 |
| -4 | - | gap:7 97.64 | 102.11 |
| +0 | - | gap:7 97.65 | 102.11 |
| +4 | - | gap:7 97.65 | 102.12 |
| +8 | - | gap:7 97.66 | 102.13 |
| +12 | - | gap:7 97.86 | 102.14 |
| +16 | - | gap:7 98.11 | 102.16 |
| +20 | - | gap:7 98.35 | 102.17 |
| +24 | - | - | 102.19 |
| +25 | - | gap:7 98.64 | 102.20 |
| +28 | - | gap:7 97.76 | 102.23 |
| +29 | - | - | 102.24 |
| +32 | road route3 97.58 | road route3 97.58 | 102.27 |
| +36 | road route3 97.67 | road route3 97.67 | 102.32 |
| +40 | road route3 97.77 | road route3 97.77 | 102.37 |

**292-lot — section west -> east** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | - | gap:7 95.95 | 102.20 |
| -36 | - | gap:7 96.06 | 102.20 |
| -32 | - | gap:7 96.18 | 102.19 |
| -28 | - | gap:7 96.29 | 102.18 |
| -24 | - | gap:7 96.41 | 102.18 |
| -20 | - | gap:7 96.52 | 102.17 |
| -16 | - | gap:7 96.64 | 102.12 |
| -12 | - | gap:7 96.75 | 102.06 |
| -8 | - | gap:7 96.86 | 102.01 |
| -4 | - | gap:7 96.98 | 101.94 |
| +0 | - | gap:7 97.09 | 101.86 |
| +4 | - | gap:7 97.21 | 101.79 |
| +8 | - | gap:7 97.32 | 101.72 |
| +12 | - | gap:7 97.44 | 101.69 |
| +16 | - | gap:7 97.54 | 101.65 |
| +18 | - | - | 101.63 |
| +20 | - | - | 101.62 |
| +24 | - | - | 101.64 |
| +28 | - | - | 101.67 |
| +32 | - | - | 101.69 |
| +36 | - | - | 101.72 |
| +40 | - | - | 101.74 |

**292-lot — section south -> north** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | - | gap:7 97.71 | 101.90 |
| -36 | - | gap:7 97.73 | 101.84 |
| -32 | - | gap:7 97.75 | 101.79 |
| -28 | - | gap:7 97.77 | 101.79 |
| -24 | - | gap:7 97.78 | 101.81 |
| -20 | - | gap:7 97.80 | 101.82 |
| -16 | - | gap:7 97.82 | 101.83 |
| -12 | - | gap:7 97.83 | 101.84 |
| -8 | - | gap:7 97.78 | 101.85 |
| -4 | - | gap:7 97.43 | 101.86 |
| +0 | - | gap:7 97.09 | 101.86 |
| +4 | - | gap:7 96.75 | 101.85 |
| +8 | - | gap:7 96.41 | 101.84 |
| +12 | - | gap:7 96.07 | 101.83 |
| +16 | - | gap:7 95.66 | 101.81 |
| +20 | - | gap:7 95.31 | 101.75 |
| +24 | - | gap:7 94.98 | 101.70 |
| +28 | - | gap:7 94.65 | 101.64 |
| +32 | - | gap:7 94.32 | 101.53 |
| +36 | - | gap:7 93.99 | 101.36 |
| +40 | - | gap:7 93.66 | 101.19 |

**358-pavement — section toward 30.1191963, 31.4082803 (25.8 m off)** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | apron pav37 89.43 | apron pav37 89.43 | 95.82 |
| -36 | apron pav37 89.47 | apron pav37 89.47 | 96.00 |
| -32 | apron pav37 89.52 | apron pav37 89.52 | 96.20 |
| -28 | apron pav37 89.57 | apron pav37 89.57 | 96.44 |
| -24 | - | - | 96.61 |
| -23 | road small_roads:-20210 96.33 | road small_roads:-20210 89.67 | 96.65 |
| -20 | road small_roads:-20210 96.66 | road small_roads:-20210 89.92 | 96.76 |
| -18 | - | gap:0 90.07 | 96.84 |
| -16 | - | gap:0 90.12 | 96.91 |
| -12 | - | gap:0 90.05 | 97.07 |
| -8 | - | gap:0 90.09 | 97.03 |
| -4 | - | gap:0 90.16 | 96.99 |
| +0 | - | gap:0 90.24 | 96.94 |
| +4 | - | gap:0 90.33 | 96.91 |
| +8 | - | gap:0 90.42 | 96.86 |
| +12 | - | gap:0 90.52 | 96.82 |
| +16 | - | gap:0 90.61 | 96.79 |
| +20 | - | gap:0 90.70 | 96.77 |
| +24 | - | gap:0 90.79 | 96.75 |
| +25 | - | - | 96.75 |
| +26 | pad building26 90.79 | pad building26 90.79 | 96.75 |
| +28 | pad building26 90.79 | pad building26 90.79 | 96.74 |
| +32 | pad building26 90.79 | pad building26 90.79 | 96.74 |
| +36 | pad building26 90.79 | pad building26 90.79 | 96.68 |
| +40 | pad building26 90.79 | pad building26 90.79 | 96.62 |

**358-pavement — section across that line** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | pad building63 86.04 | pad building63 86.04 | 94.05 |
| -37 | - | - | 94.27 |
| -36 | - | - | 94.34 |
| -32 | - | - | 94.64 |
| -28 | - | - | 94.97 |
| -24 | - | - | 95.31 |
| -21 | - | gap:0 90.79 | 95.59 |
| -20 | - | gap:0 90.69 | 95.69 |
| -16 | - | gap:0 90.65 | 96.06 |
| -12 | - | gap:0 90.64 | 96.30 |
| -8 | - | gap:0 90.46 | 96.53 |
| -4 | - | gap:0 90.35 | 96.75 |
| +0 | - | gap:0 90.24 | 96.94 |
| +4 | - | gap:0 90.22 | 97.13 |
| +8 | - | gap:0 90.22 | 97.30 |
| +12 | - | gap:0 90.22 | 97.47 |
| +16 | - | gap:0 90.19 | 97.63 |
| +20 | - | gap:0 90.18 | 97.73 |
| +24 | - | gap:0 90.17 | 97.67 |
| +28 | - | gap:0 90.16 | 97.61 |
| +32 | - | gap:0 90.14 | 97.56 |
| +36 | - | gap:0 90.13 | 97.51 |
| +40 | - | gap:0 90.11 | 97.47 |

**gaps3-lead — section toward 30.1153310, 31.4106152 (8.3 m off)** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | road route3 104.91 | road route3 104.91 | 105.00 |
| -36 | road route3 104.84 | road route3 104.84 | 104.84 |
| -33 | - | - | 104.72 |
| -32 | - | - | 104.68 |
| -31 | - | gap:8 104.34 | 104.64 |
| -29 | - | - | 104.56 |
| -28 | - | - | 104.52 |
| -24 | - | - | 104.35 |
| -21 | - | gap:8 104.19 | 104.21 |
| -20 | - | gap:8 104.15 | 104.16 |
| -16 | - | gap:8 104.00 | 103.96 |
| -12 | - | gap:8 103.84 | 103.75 |
| -8 | - | gap:8 103.69 | 103.53 |
| -5 | - | - | 103.36 |
| -4 | - | - | 103.31 |
| -1 | - | gap:8 | 103.15 |
| +0 | - | gap:8 101.07 | 103.09 |
| +1 | - | - | 103.04 |
| +2 | road route3 97.16 | road route3 97.16 | 102.98 |
| +4 | road route3 97.14 | road route3 97.14 | 102.89 |
| +8 | road route3 97.04 | road route3 97.04 | 102.69 |
| +9 | - | - | 102.64 |
| +10 | - | gap:7 97.19 | 102.60 |
| +12 | - | gap:7 97.71 | 102.50 |
| +16 | - | gap:7 97.68 | 102.32 |
| +20 | - | gap:7 97.62 | 102.19 |
| +24 | - | gap:7 97.64 | 102.13 |
| +28 | - | gap:7 97.65 | 102.07 |
| +32 | - | gap:7 97.67 | 102.02 |
| +36 | - | gap:7 97.68 | 101.99 |
| +40 | - | gap:7 97.70 | 101.97 |

**gaps3-lead — section across that line** (s m | BASE | ARM | DEM)

| s | base | arm | DEM |
|---|---|---|---|
| -40 | - | - | 102.98 |
| -36 | - | - | 102.99 |
| -32 | - | - | 103.00 |
| -28 | - | - | 103.03 |
| -24 | - | - | 103.07 |
| -22 | - | gap:8 103.44 | 103.09 |
| -20 | - | gap:8 103.44 | 103.11 |
| -16 | - | gap:8 103.43 | 103.12 |
| -13 | - | - | 103.12 |
| -12 | - | - | 103.12 |
| -8 | - | - | 103.13 |
| -4 | - | - | 103.12 |
| -2 | - | gap:8 | 103.11 |
| +0 | - | gap:8 101.07 | 103.09 |
| +1 | - | - | 103.08 |
| +4 | road route3 97.10 | road route3 97.10 | 103.06 |
| +8 | road route3 97.01 | road route3 97.01 | 103.02 |
| +12 | road route3 96.92 | road route3 96.92 | 103.03 |
| +16 | road route3 | road route3 | 103.04 |
| +20 | - | - | 103.04 |
| +23 | - | gap:7 96.85 | 103.06 |
| +24 | - | gap:7 97.16 | 103.08 |
| +27 | - | - | 103.14 |
| +28 | - | - | 103.15 |
| +29 | - | gap:7 97.64 | 103.17 |
| +32 | - | gap:7 97.64 | 103.21 |
| +36 | - | gap:7 97.58 | 103.26 |
| +40 | - | - | 103.31 |
