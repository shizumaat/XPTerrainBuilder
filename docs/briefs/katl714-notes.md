# katl714 — KATL runway 10/28 over I-285 (#714); the apron retaining wall (#715)

Lane `katl714`, branch `claude/katl714`, base main `367e84cae`.
Capture `scratchpad/katl714/cap/KATL.pkl` (159 s, 25,081 vertices / 1,491 faces).
Control harness build `katl714_base` (rc 0, 761 s).

## #714 ATTRIBUTION (before any edit)

* OSM: I-285 is two carriageways, ways -2193 / -2190 (`highway=motorway lanes=5
  tunnel=yes covered=yes layer=-1`), 31 m apart, crossing runway 10/28 at ~60°;
  covered stretch ~330 m each (mouths 33.61947,-84.43149 / 33.62113,-84.42853 and
  33.61943,-84.43216 / 33.62109,-84.42922); runway 10/28 is `layer=1`.
* DEM (USGS 3DEP lidar inset, BARE EARTH): the covered stretch reads the ROAD
  FLOOR. Along the runway centreline 301.0 at -84.4319, 281.6 at -84.4315,
  ~285 to -84.4293, 302.6 at -84.4289 — a 240 m long, 16-20 m deep walled cut
  under the runway. Across the bore at the crossing the cut spans -76..+44 m.
* What the engine builds there today: NO structure. `bore_table` admits the four
  bores (`under the classified cover for 329.6 m`), but every mouth is refused
  (`tunnel:-2193@0: the mouth stands against pavement pav17`, `@1: the wall would
  stand inside the runway strip keep-out`, same for -2190); the pack's
  `tunel_A/B/C.obj` are refused as corridors (`roofed along its axis (3884 m2 …):
  a building or a deck, not a wall skirt`; `trench ring has 0 open ends`).
  So the airside surface is solved straight over the bare-earth DEM.
* Why 10/28 dips: `constraints/runway_chord`'s TARGET is a moving quadratic of
  the ridge vertices' `dem_z` (500 m window); the cut pulls it to 290.1 m at
  s=1625 (DEM bin 284.7). Built ridge min 294.83 at s=1575 (BOW −9.62 m), max
  grade 2.30 %, max grade change 2.48 %/100 m (`rwy_profile --binned --target`
  on `katl714_base`). The bore's cap/crest rule is NOT involved (no bore built);
  `ramp_cuts_runway_family=false` holds (no ramp exists). `--why-at` on the
  worst vertex v4546 (z 294.57, DEM 282.31) shows only the runway's own profile/
  chain/no-step rows — the surface sits where its DEM-fed target put it.
* Taxiway pav15 (primary parallel) and stub pav15, apron pav17 (the pack's paved
  deck south of the runway, its zig-zag south edge = the portal line) dip the
  same way (pav15 down to 294.81, pav17 293.94-297.27).

## THE PACK'S OBJECTS (recognised, read only)

| object | placement (lat, lon, hdg) | geometry |
|---|---|---|
| `New Buildings/tunel_A.obj` | 33.619828,-84.431614, 90.24 | deck plate at y=0 (x 18..51, z −93..87: 33×180 m), diagonal walls to y=−23.74 |
| `New Buildings/tunel_A.obj` | 33.620558,-84.429349, 269.81 | same, mirrored north |
| `New Buildings/tunel_B.obj` | 33.621709,-84.428233, 101.50 | plate + walls to y=−25.43 |
| `New Buildings/tunel_C.obj` | 33.621844,-84.427080, 276.00 | plate (x 25..50, z −93..40) + walls to y=−25.87 |

All plain `OBJECT` (draped): the plate's top is the deck (= airside surface),
the walls' foot the road (23.7-25.9 m under). The structure reader records them
as `no_floor` (bottoms 258.5 / 264.9 / 266.6 MSL in the base frame).
No existing witness consumes them: `[tunnel.object]` corridors refuse a roofed
shell; the wall-class classifier (`airport/wall_class`) does not apply (they
are not thin); the bridge/`elevated_deck` laws read decks OVER roads.

## THE FIX — `planar/covered_ground.py` (one derivation site)

The ground over a covered road is the ground BESIDE it. For every mapped bore
under airside pavement (`airside_cut_roles`, ≥ `terrain_cover_min_m`), the cut
is read across its axis every 5 m: floor under the carriageway, each side's rim
where the DEM climbs `covered_rim_rise_frac` (0.9) of the rise within
`covered_rim_search_m` (100 m), the ground beside = highest DEM within
`covered_side_probe_m` (10 m) past the rim. A side whose rise is under the
MOUTH DEPTH (7.5 m, the least a real road floor stands under its cover) reads
no cut. The rim-to-rim footprint, clipped to the airside pavement over it,
lifts `Vertex.dem_z` (never lowers) — written in `planar/build` beside
`ramp_targets` (which still win on ramp vertices).

### CONSUMER CENSUS (RULINGS 2026-08-30l) — readers of `Vertex.dem_z`

The change is a VALUE change of one field at its one write site; no shape,
role, region or record is added. Readers:

| reader | reads | ruling |
|---|---|---|
| `constraints/runway_chord` (trend), `runway_profile`, `runway_yield`, `taxi_trend`, `apron_trend` | the ground the profile follows | INTENDED: the deck's ground, not the road floor |
| `solve/design_assemble`, `design`, `design_ground`, `design_stage`, `rows`, `ground_band` | the per-vertex fit / ground band | INTENDED, same |
| `constraints/pad_*`, `eat`, `ramp_runout`, `platform` | pad / frontage ground | unaffected at KATL (no pad inside the footprint); same meaning elsewhere |
| `constraints/seams` | tile-seam DEM pin | unaffected (no footprint on a tile seam; a seam vertex inside one would take the deck ground) |
| `airport/road_ramp`, `emit/road_join` | road ground / join | 3 road-ribbon vertices at KATL inside the pavement-clipped footprint; intended |
| `planar/shapes` | presence check only | unaffected |
| `pipeline/publication`, `runway_report`, `xplat`, `build` | reports / sidecar | report the lifted ground (the reports' "z − DEM" over the cover now reads against the deck ground) |
| readers of `airport.dem` directly (structures, objects, basins, emitter outside the patch) | the REAL DEM | unchanged by construction: the open cut beyond the deck and every object seat keep the true ground |

## MEASURED (replay `--from planar --emit` vs the base `--bank-from` emit, same capture)

Runway 10/28 crown spine at the owner site (-84.43076): **294.6 → 301.6 m**;
across the freeway (-84.4335..-84.4275) the arm rises monotonically
300.7 → 303.8, grade +0.08..+0.83 %. Binned ridge: min 294.83 → 300.24
(the remaining −4.3 m bow at s=1125 is the field's own sag, DEM 299.6 there),
max |grade| 2.30 → 0.94 %, max grade change 2.48 → 0.42 %/100 m.

Taxiway pav15 across the freeway: base dips to 294.81, arm 300.5 → 303.9
monotone. Airside movers > 0.02 m (all at the I-285 cover, all UP): runway
10/28 258/601 nodes (max +6.97), pav15 parallel 266/648 (+6.50) and stub
68/187 (+5.05), apron pav17 80/80 (+6.92), pav9 parallel 10/19 (+2.55),
cross-connectors pav15/pav9 (+0.40); elsewhere ≤ 0.11 m (junction pav13,
apron pav13 21 nodes 0.11 m — solver coupling), other runways ≤ 0.04 m.

Sweep airports (dry census of `covered_ground` over registered captures):
HECA, OTHH, SPJC, CYXY, NLWF, KPDX, KASE, KCLT — **no bore qualifies; nothing
lifts**. (Before the mouth-depth rule SPJC lifted a runway 1.15 m and KCLT an
apron 4.63 m; the rule removed both.)

## CLOSING HARNESS BUILD (rebased on main d30332185)

Control `katl714_base2` (main d30332185, rc 0, 859 s, artifact ledger
ab5c43e68946) vs arm `katl714_arm2` (rc 0, 560 s; ledger store refused
CONTAMINATED-KEY because this notes file was edited during the build — no
code moved). Planar log: `covered ground (#714): 8 bore(s) … footprint
65,817 m2; 114 of 114 vertex(es) … max lift 20.01 m`. Runway 10/28 binned:
ridge min 294.83 → 300.22, BOW −9.62 → −4.33 (the field's own sag at
s=1125), max |grade| 2.30 → 0.82 %, max grade change 2.48 → 0.42 %/100 m;
crown spine at the owner site 294.55 → 301.52. Airside movers identical to
the replay (10/28 +6.97, pav15 +6.50, pav17 +6.92, pav9 +2.55, all at the
cover; elsewhere ≤ 0.06 m).

## RESIDUAL — THE PORTAL (not fixed here)

At the SW mouths the road ribbons that stand inside the patch for 10-30 m past
the deck edge (big_roads:-7388 / -2194, small_roads:-30824/-30827) share the
deck edge's vertices (free-road rule) and climb from it at the road cap: base
291-293 m, arm 296-298 m (harness: road ribbons within 50 m of the SW mouth
max 294.31 → 299.99), against the road floor 281-282 m. The step to the
real road happens at the patch's terrain edge instead of at the portal. The
cure is a declared step at the deck edge over a covered bore's mouth (the
pack's portal walls as the terrace), the same mechanism #715 needs.

## #715 ATTRIBUTION (33.6412038, -84.4211416)

* The wall: `objects/muro_concreto5.obj` at 33.641131,-84.420841 (hdg 0),
  10.65 m tall (y −9.70 .. +0.95: zero = the apron, crest 0.95 m proud), 3.4 m
  thick, plan path 33.6394,-84.42176 → 33.6409,-84.42170 → 33.64127,-84.42140 →
  33.64124,-84.42029 → 33.64109,-84.42008 (~340 m). DEM across it at -84.4211:
  301.7 (apron) | 300.5 at 33.6412 | 291.1 at 33.64125 — a 10.6 m step that
  matches the wall height. Also `objects/muro_ladrillo.obj` 33.641293,-84.421887
  (16.6 m component; read as `through_grade`).
* What the engine does: the apron (dsf:pol22 / pav4) holds 299.9-300.4 (1.5-
  1.9 m under its DEM 301.8), and the lower side — service roads
  small_roads:-12997/-12996 and groundside `gap:5` — is held at 298.5-299.7 m
  against DEM 290.8-291.1 (+8 m), sharing vertices with the apron along the
  wall line; no terrace is declared (`wall_terrace 0`).
* Why (1): `airport/wall_class.wall_class_components` rejects the wall — its
  footprint ring is 1,192 m² over a 689 m perimeter, mean width 3.46 m >
  `[service] retaining_wall_max_width_m` 1.0 — so `wall_terraces` (10-03c)
  never sees it. A width-per-height relaxation alone (≤ 0.35 × height) admits
  205 other KATL components (facades, aircraft): not a rule.
* A witness that IS selective: the DEM on a 3 m ring round the component steps
  (10th..90th percentile) by 0.75-1.25 × its height, and it is ≤ 0.5 × height
  thick. Dry census over the registered captures: KATL `muro_concreto5`
  (10.65 m, step 12.14) and `muro_concreto` (12.01 m, step 11.10) — 590 → 592
  wall-class; HECA OTHH SPJC CYXY NLWF KPDX KCLT 0 new; KASE 2 parts of one
  city building 6 km off the field (39.1854,-106.8177).
* Why (2) — MEASURED, the classifier is NOT enough: with it (branch
  `claude/katl715-wip`, replay `--from classify`) the site is unchanged
  (apron 299.8-300.4, roads -12997/-12996 298.4-299.9 against DEM 291): the
  lower side at the wall is `gap:5` (a §53 gap piece — lane katlgap719 / PR
  #725 removes it: it was minted from the pack's `poligonos/muro_contension.pol`
  wall PHOTO) and service roads that SHARE the apron's vertices along the wall
  line (free-road weld), so no lot vertex stands across the wall and no pair
  row is released. After #725 the lower side is roads + zones: the fix needs
  the wall terrace to hold for a ROAD at the foot (10-03c reads lots only) —
  a spec question, not a threshold.

# katlwall — "the wall is the step" (RULINGS 2026-10-15a (1)/(2), #715 + #714 residual)

Lane `katlwall`, branch `claude/katlwall` (contains `claude/katl714` = PR #727
and the `katl715-wip` witness, rewritten).

## CONSUMER CENSUS (RULINGS 2026-08-30l) — every pass that holds roads, lots and airside across a line

The change adds no shape, role or region: it adds ONE flag
(`WallComponent.retains` / `WallPiece.retains`, derived once in
`airport/wall_class`) and ONE published channel (`PlanarMap.mouth_walls`,
derived once in `planar/covered_ground`, read as retaining `WallPiece`s by
`airport/road_ramp.mouth_wall_pieces`). Every reader of the wall pieces and
every pass that couples the two sides of a wall line:

| pass | what it does across the line | ruling under 15a (2) |
|---|---|---|
| `airport/road_ramp.road_terrace` `foot` / `pad` (10-03b, the free-road / bordered-run rule) | a road vertex in a pavement's adjacent ground takes that pavement's stage-1 level | CHANGED: a foot whose way from the road vertex crosses (or starts in) a retaining wall is refused — the road below is not bordered by the pavement above (`_across_retaining`) |
| `road_ramp_targets` mouths (§37 (6)) | a road vertex shared with airside is a MOUTH; the ramp descends from it | CHANGED: a mouth ON a retaining wall (within 0.5 m) is no mouth (`_on_retaining`) — measured KATL: the ramp from the shared apron vertices held small_roads:-12997 at 297 m |
| `reach_contacts` (§37 (10)) | a road end within reach of an airside edge takes its level (a row) | CHANGED: a contact whose way crosses a retaining wall is dropped (`reach_contacts_across_retaining_wall`) |
| `wall_terraces` (10-03c) | declares upper / lower across a wall; `pairs` lot→pad | CHANGED at a retaining wall only: road vertices are lower too (and a road vertex inside the wall); no lot needed. Thin non-retaining walls unchanged |
| `constraints/road_ramp.wall_release` | withdraws stage-2 pair rows straddling the line with one end lower | UNCHANGED code; now sees the roads in `lower` |
| `solve/design_assemble` bending (`rows._cotangent_laplacian`) | the thin-plate stencil spans faces across the wall | CHANGED: edges across a declared wall carry no weight (`solve/wall_cut.wall_cut_edges`) — measured on the twin: with every pair row released the road stood 3.5 m over its ground, carried by the strip's bending |
| `constraints/road_ramp.wall_terrace_rows` | lot → pad level | unchanged (no pad below at KATL) |
| `pipeline/publication.wall_terrace_joints` → `terrace_joints_ll` | the declared joint (step = min(wall height, emitted)) | unchanged; the census reads the declared step |
| `[cutout.wall_corridor]` (structures cutouts) | tunnel wall corridors | not read: the portal objects are refused as corridors (roofed); unchanged |
| `planar/weld.py` | sliver weld, same side only (airside never welds groundside) | not involved: the KATL shared vertices are the ribbon mint's kerb, not the weld; geometry unchanged |
| pass-C ribbon welds (`pad read` `ribbon_welded`) | ribbon rims welded to pads | not involved at the sites (no pad at the wall or mouths) |
| zone corridor rows (`constraints/zones.zone_bands`, `solve/project` zone projection) | ground vertex vs pavement edge, 3-term rows | stage-2 Linear rows: released by `wall_release` where they cross with a lower end; road kerb vertices carry none |
| `classify/retaining_wall` (§47), `planar/shore` | read `wall_class_components` | a thick retaining wall is now wall-class for them too (the WIP's measured scope: KATL 2 components) |
| `pipeline/terrace_witness` | report only | unchanged |

## THE WITNESS (airport/wall_class._retains_its_height)

Slender (width ≤ 0.5 × height) AND the ground stepping 0.75–1.25 × height
ACROSS the wall: every 2 m round a ring max(3 m, height) outside the
footprint, each point against the point as far out on the far side, the
90th percentile of |difference|. The WIP's ring 10th–90th spread admitted 56
thin HECA strips (a long wall on a slope rises along itself) — refuted and
replaced. Dry census (registered captures): KATL 4 retaining
(`muro_concreto5` 10.65 m, `muro_concreto` 12.01 m, `muro_27R` 19.99 m,
`terminal_F/Vidrios.obj` comp 17 12.51 m), 2 declared wall terraces;
HECA 0, OTHH 0, SPJC 0, KPDX 0, CYXY 0, NLWF 0, KASE 0 (the far-off city
building of the WIP no longer qualifies); KCLT 4 thin pieces (2.2–2.7 m)
retaining, 0 terraces, road-terrace feet unchanged (1482).

## THE MOUTH (planar/covered_ground._mouth_walls)

Per mouth (the covered deck's edge at the pavement's end) where a pack object
whose solid reaches the mouth depth (7.5 m) under its own zero stands in the
cut: one piece = that edge (0.5 m strip) ∪ the open cut beyond it off the
pavement, as wide as the cut's own section there (rim to rim). KATL:
tunel_A ×2, tunel_B, tunel_C (depth 23.74 / 25.43 / 25.87 m), 30 pieces over
the 8 bores. A first cut (the portal's plan box off the pavement) missed the
NE mouths (the road between the runway and taxiway decks lies outside every
portal box) and RAISED NE1's road 293.7 → 301.7 (its foot moved to the
taxiway); refuted and replaced.

## MEASURED — closing harness build `katlwall_KATL4` (8467dd64e, ledger dce4ffc81aa5) vs main control `katlwall_base` (e5f799bb3, ledger 8edab3a042b5)

* Runway 10/28 (as #727): crown at the owner site 33.6200754, -84.4307614
  294.30 → 301.22 m; binned ridge min 294.83 → 300.22, BOW −9.62 → −4.33,
  max |grade| 2.30 → 0.82 %, max grade change 2.48 → 0.42 %/100 m.
* I-285 mouths — highest road node within 50 m out (5 m bins): SW1
  294.44 → 281.95, SW2 281.50 → 280.88, NE1 294.33 → 290.17, NE2
  295.96 → 288.90 m (road floor DEM 280.5-290).
* muro_concreto5 (#715): apron above 299.96-300.05 (unchanged); roads
  below the south run (8-26 m north of 33.6412038, -84.4211416) 291.45-299.97
  → 291.45-294.85 m; at 33.641131, -84.420841 the nearest road node
  299.97 → 292.46. Declared step 10.66 m, emitted 10.655 m (agreement
  +0.005). Residual: kerb vertices shared with the taxi zone-1 strip at the
  wall foot stand 1.5-3.5 m over the 291 m floor (294.5 / 292.8 at the
  owner site).
* Airside stage-1 movers vs the #727 arm (same capture, replay): 0. Vs main:
  #727's own (10/28 +6.97, pav15 +6.50, pav17 +6.92, stub +5.05, pav9 +2.55,
  connectors ≤ 0.40, other runways ≤ 0.04, pav14 ≤ 0.20 m).
* Census (law-true, adjudicated): main 13073 → arm 11566. Of the arm's own
  share (replay arms on one capture: #727 13360 → this lane 13054): NEW
  terrace_joint_strip 17 (the mouth joints stand inside runway 10/28's strip —
  the I-285 cut is there), adjacent_ground_step +28 / mid_edge_step +11 /
  strip_seam_tear +7 at the mouths and +4 / +9 / +5 at the wall (the zone
  strips that follow the road into the cut / to the wall foot); fewer
  within_shape (−434), hard_conflict (−40), road_cross_section (−27).
* Sweep airports (dry, registered captures): HECA OTHH SPJC KPDX CYXY NLWF
  KASE — 0 retaining walls, 0 covered-ground cuts: nothing reads the new
  rule. KCLT — 4 thin pieces retain, 0 wall terraces; harness build
  `katlwall_KCLT` (c61ccd03e) vs `katlwall_KCLTbase` (main): patch and rebake
  plan BYTE-IDENTICAL.
