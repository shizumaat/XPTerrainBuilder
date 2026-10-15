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
