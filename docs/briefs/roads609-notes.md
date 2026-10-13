# roads609 — notes (issue #609: the forecourt roads between KCLT's garages; owner 2026-10-12 "admit the forecourt roads", RULINGS 12r owed)

## RESUME HERE
* Branch `claude/roads609` (worktree `.claude/worktrees/roads609`) off origin/main 8d0cd75e8.
* Scratch `<scratchpad 466e18b3…>/roads609/`: `base/` (replay of `frames/pads67/KCLT.pkl --from classify --emit
  --verify --solved-out`, main code), `a1_extent_arm.py` (the attribution instrument: classify-only, shipped vs one
  intervention, read at the site).
* Step A (attribution) DONE below. Consumer census DONE below. Code next.

## Step A — WHY THE FORECOURT ROADS ARE NOT IN THE PATCH (verified on the pads67 KCLT capture, main 8d0cd75e8)
Facts re-read (`tools/osm_site.py`, base replay patch): within 250 m of 35.2248,-80.9450 the patch holds ONE
`service_road` (`small_roads:-30034`, 247 m); within 150 m the three garage pads building86 (223.0–223.4),
building88 (223.1), building90 (223.0–223.45); the feed (`+35-081_airport_small_roads.osm.bz2`) holds 32
`highway=service` ways within 120 m (34 with `big_roads`; one `bridge=yes layer=2`, dropped by `road_ways` as
every bridge is).

THE GATE: `classify/ribbon_mint.ribbon_extent` — 30e (2) "the way's parts INSIDE THE PATCH" — defines the patch as
the pavement union + the airside bands' zone-2 envelopes. A BUILDING PAD IS NOT IN IT (nor is anything groundside),
so a road that reaches a pad and nothing airside has no in-patch stretch at all, and 30e (2)'s gap bridge joins
stretches of ONE OSM WAY only — the forecourt network is 32 short ways (2–23 nodes; OSM splits a road at every
junction), so no way has two in-patch stretches to bridge. The other candidate gates do NOT fire: not the airport
boundary / airside claim (the ways are inside the load box, `airport.osm_ways` holds 34 of them), not the 1206 dedup
(no route there), not min_len (10 m), not the bridge/layer handling (1 of 32), not the pack-object cover (the mint
subtracts standing CELLS only; the slab `techos_1` is no cell — #229 unbuilt), not the feed's own filter (the ways
are in the feed).

Intervention (`a1_extent_arm.py`, classify only, seconds): SHIPPED 529 ribbons / 36,988 m² airport-wide, 0 within
150 m of the site. ARM "the pads are in the extent" (one line: `ribbon_extent` ∪ the building cells): 547 ribbons /
38,682 m², 8 within 150 m — but only 1,054 m² of STUBS at the garage rims (`small_roads:-16665` 84 m², `-16649` 45 m²,
`-16651` 46 m², `-24655` 777 m² …): the way's part inside the pad is in the extent, the pad then subtracts it, and
the part BETWEEN the garages is still out of the patch. So two things are missing, both at the one site:
1. A PAD IS PATCH: `ribbon_extent` gains the pad cells (a road entering a pad in source = the road serving it; the
   touch witness of 09j then welds it to the rim).
2. THE GAP IS THE ROAD'S, NOT THE WAY'S: 30e (2)'s 250 m bridge joins two in-patch stretches along the ROAD
   NETWORK (ways sharing a node), not along one OSM way — the forecourt between two garage entries is a path of
   several ways. The per-way bridge is the special case of the path along one way; `road_gap_bridge_m` is unchanged.
3. THE WELD: `mint_osm_ribbons` subtracts every pad WITH the set-back knife (roadweld100: "the ribbon takes the same
   set-back itself"), so a ribbon is always GAPPED from a pad and never welds (09j (2) says a road touching a pad
   in source is welded; the knife is the engine's own gap, which 09j says is no witness). The ribbon cells now go
   through the same touch witness every lot and 1206 corridor goes through (`_cut_back_groundside`, read on the
   NEW ribbon cells only so no existing cell is re-cut — the roadweld100 measured hazard).

## Consumer census — every pass that reads a mapped-road ribbon (`is_osm_ribbon_ref`) or groundside pavement at a pad
| site | reads | with a ribbon WELDED to a pad rim / admitted between pads |
|---|---|---|
| `classify/roles._cut_back_groundside` | touch witness per groundside cell vs pads | NOW reads the ribbon cells too (new cells only): touching → clipped at rim + `pad_touch`/`pad_weld`; held (§28 (6) step > 2.4 m) → knife; gapped → as drawn |
| `classify/gap_mint` :123 | ribbons are FLUSH (no stand-off) for gap pieces | unchanged: a gap piece abuts a ribbon flush; the ribbon now also abuts the pad |
| `classify/facade_mint` | facades minted BEFORE ribbons | unchanged (a road inside a facade lot is the lot) |
| `planar/weld.weld_cells` | `pad_touch.weld_partners(cell)` → welds the cell to the named pad's rim, pad frozen | the ribbon now names its pad; same halves as a lot |
| `planar/zones` :183 | ribbon gets no stand-off inside a band; kerb is the band's | unchanged |
| `planar/shapes` :430 | a ribbon is UNLABELLED (30aa) — no road separator | unchanged |
| `planar/shape_mouths` :45, `shape_airside` :98/:185 | ribbon is no side, no separator | unchanged |
| `planar/ribbons` | ribbon stations | unchanged |
| `constraints/pads.pad_welded_vertices` | every vertex both a pad's and a groundside value face's = PAD column | the ribbon's rim vertices become pad columns (senior) — the weld law of 09j (2) |
| `constraints/pads` :510 | rim-strip rule skips ribbons | unchanged |
| `constraints/pad_frontage_gs` :358/:404 | 09j touch: a cell sharing the pad's rim | the ribbon is such a cell now |
| `constraints/apron` :449 | ribbon mints no apron row | unchanged |
| `constraints/ceiling` :119 | band→ribbon rows keep the road cap | unchanged |
| `constraints/roads` / `road_ramp` :1141 | ribbon vertices are never "own" bordered runs; contact set = airside value roles (pad included) + lot | a ribbon welded to a pad gets the §37 (6) ramp from that CONTACT at the pad's pre-solve level, design 5 % / cap 10 % |
| `solve/design_stage._welded_faces` | ribbons are the welded road faces (stage 2) | unchanged |
| `pipeline/ribbon_steps` | ribbon kerb vs airside cliff read | unchanged |
| `pipeline/terrace_witness` | retaining-wall witness on road ring edges | reads the new faces like every road |
| `pipeline/late_stage` :98 | ribbon near a gap piece skipped for stations | unchanged |
| `verify` families | `road_cross_section`, `within_shape`, `pad_*` price the new faces | counted in the census |
Object stage: a body whose feet stand on a ribbon face reads that graded surface (10n (3)); the bodies between the
garages stood on NO face before (off-surface → mesh ground in the tile build).

## Arm 1 — KCLT replay (`frames/pads67/KCLT.pkl --from classify --emit --verify`, branch 6399c2cf1 vs main 8d0cd75e8; `<scratch>/base/`, `<scratch>/arm1/`)
* RIBBONS: 529 → 602 faces, 36,988 → 72,498 m²; within 150 m of 35.2248,-80.9450: 0 → 17 faces / 6,973 m² (the
  forecourt's `small_roads:-16661/-16664/-16665/-16660/-16663/-16649/-16662/-16651/-24651/-24655`, the terminal
  approaches `-8186/-8188/-8200`); 10 of them WELDED to a garage pad (`pad_touch` d=0.0: building86 ×3, building88 ×2,
  building90 ×6); airport-wide `ribbon_pad_welds` 53, ribbons held off as §28 (6) terraces 10.
* THE GARAGES DROP TO THEIR GROUND: building86 223.0–223.4 → **218.44–218.82**, building88 223.1 → **218.80–219.08**,
  building90 223.0–223.45 → **218.33–218.79** (DEM 218.1–219.6; −4.69 m worst). `--why-vertex 16965` (a building86
  rim vertex shared with no road): held by the pad rows through a chain to a §37 (9) COVERAGE-EDGE JOIN PIN on the
  ribbon `small_roads:-16649#2` (v22433, 218.29 = the core road's level) 2.7 m off the rim — the road leaves the
  patch 2.7 m from the pad and is pinned at DEM there; its hard cross-section row ties the rim; the pad (touching no
  airside, a soft 27a (9) facing preference at 223 only) MOVES to where the road welded to it grades inside its caps —
  exactly 10a (2) (a) and 09j. The 223 level of 12c was the 27a (9) facing read's (connect549 arm A2) and nothing in
  law holds it once the roads are welded. (`exit_reach` at a pad mouth reads the DEM at the mouth as the patch level
  — the pad's seat is unknown at classify — so the ribbon stub past the rim is one station long.)
* AIRSIDE: solve-owned 0 movers, RUNWAY 0; row-side 244 (strip 56 worst 2.32 m at 35.22609,-80.93521; apron 30
  ≤ 0.65; other 158 = the garage pads); STRUCTURE 17 tunnel-wall rim nodes ≤ 1.30 m at 35.20218,-80.94025 (the
  terminal tunnel: ribbons `small_roads:-30357/-30359` beside it are now welded to their pad instead of knifed; the
  census shows cross_connector rows over the bore moved ≤ 0.92 m |de|).
* RAMPS (`road_course_profile --on-patch`): garage entries flat — `-16664` 3.2 %, `-16649` 3.4 %, `-24655` 5.8 % at its
  patch edge, `-16651` 1.5 %, `-16661` 1.1 %; the terminal approach `-8188` (217.3 → building75 222.44): the ribbon is
  HELD off building75 by the §28 (6) hillside step (DEM step > 2.4 m) and ends 2.7 m short of the rim with a 5.1 m
  wall (50.7 % over 10 m at 35.222959,-80.945684) — the #519 "road diving into a hole" class, the one lawful terrace.
* THE 223 WORLD (if the owner holds 12c's plane): the forecourt would be a 223 plateau welded to the three pads and
  ramps would sit at its EXITS — rise 4.9–5.8 m over DEM 217.3–218.2 at the five exits (35.225810,-80.943949;
  35.225349,-80.945790; 35.223592,-80.945233; 35.223252,-80.945231; 35.222959,-80.945684): 98–115 m at the 5 % design
  grade, 49–58 m at the 10 % cap; the terrain outward is flat (217–220), nothing obstructs. No law holds 223 today
  (10a (2) (a): a pad's object level is a preference, never a hold) — OWNER QUESTION.
* OBJECTS (dry run `obj8_split_report` on `frames/kclt608/KCLT.rebake.json`, graded base vs arm1;
  `tools/rebake_plan_diff.py zeros`): 55 bodies change unit or zero (54 > 0.05 m), re-partition 67/88. The garage
  unit `fu:31:2809` is now level-cut (/p0 building90 218.37, /p1 building88 218.85). The small bodies between the
  garages (base: written at 223.11, own ground −0.35..−0.48 on the graded read, +2.4..+5.0 on mesh ground): arm1
  `paredes_10 b14/b15` at 35.2244049,-80.9445682 z 218.30 (own ground −0.52 → stands 0.03 m off the ribbon under
  it), `b13` 35.2254439,-80.9446534 z 218.45 (own −0.36), `b2/b3` 35.2241809,-80.9458015 z 218.60 (own −0.22/−0.61),
  `b5/b6` on building90 218.33/218.34 (own 0.00/−0.38). Movers elsewhere: `techos_1` low-side-foot bodies at
  35.2219199,-80.9457901 / 35.2228061,-80.9425073 −3.04 (the forecourt slab bodies on the new road ground);
  `paredes_10` footless at 35.2234854,-80.9443605 −1.93 ×7, −1.87 ×7, −1.75 ×7; east side `002/007_ALB` fu:3:161/162
  +2.12 / +1.64 (35.2178533,-80.9294227 — ribbons newly admitted there); §15 floating footed bodies 10 → 40 (worst
  3.47 m `paredes_10 b47` at 35.2234314,-80.9442846 over `techos_1 b3`).
* CENSUS: LAW-TRUE 17444 → 17886 (+442: NEW service_road within_shape 146, road_cross_section 107 (+25
  building|service_road), hairline_pair 88, within_shape building|service_road 79, hard_conflict groundside 40;
  airside NEW taxi_box 51 / airside_no_step 44 / within_shape 18 cross_connector at the tunnel 35.2015,-80.9402);
  ADJUDICATED 6104 → 6521 (airside 2949 → 3040, groundside 3133 → 3456); steps 17 → 28; CRITICAL motion 4 = 4,
  visual 1974 → 2076. Hard feasibility relaxed 309 → 349.
* Twin `tests/auto_patch_v2/test_gap_apron.py::test_the_class_table_read_on_a_real_map` (HECA real-map pin: 38 gap
  pieces) FAILS on the branch (60 pieces + 12 gap aprons): the ribbons occupy more ground — re-pin after the HECA arm.
* Tools promoted: `tools/rebake_plan_diff.py` (`zeros` = kclt608 c2_osr_diff, `separations` = a2_separations) + INDEX
  row + `tests/test_rebake_plan_diff.py`.
* RUNNING: HECA pair (`heca_base/` main tree, `heca_arm1/`), then CYXY/NLWF/SPJC/OTHH pairs (`run_pairs.sh`), all on
  the PRE-MERGE branch 6399c2cf1 vs main 8d0cd75e8; origin/main has moved to d64b880da (#627 one level, #626) —
  merge AFTER the pairs, then the closing harness build vs `frames/kclt608/kclt608_KCLT.osm` (= #627's KCLT
  3f22a1e516b3) and the tile builds.

## Approved airports — replay pairs (PRE-MERGE branch 6399c2cf1 vs main 8d0cd75e8, `frames/pads67/*.pkl --from classify`)
* HECA (`heca_base/`, `heca_arm1/`): solve-owned airside 2,786 movers worst 1.11 m (apron `route11` 176/194 at
  30.12678,31.39606; `dsf:objpav383` 1.02), RUNWAY 90 nodes ≤ 0.05 m, strip 609 ≤ 0.20; 92 PADS moved — **building6
  101.77 → 89.20–89.77 (−12.57 m, 30.11451,31.39611 WELDED-TO-ROAD), building7 101.79 → 94.47–94.91 (−7.32),
  building128 −4.53, building33/38/13 −3.0, building86 −2.35**; groundside gap:0 944 nodes ≤ 2.90, dsf:pol10 1.65.
  Plan diff (`rebake_plan_diff zeros`, plan `/private/tmp/harness/kclt608_HECA.v2/HECA.rebake.json`): 817 bodies
  change unit or zero, 674 > 0.05 m — the T3 complex `fu:40:120/p1` 101.79 → `/p0` 89.37 (−12.42: T3_14 ×4,
  T3_brick_clean, floor, meridien ×2, t3_13 ×2, titles_1 ×3, door ×3, glass_blue, metal_strip_2 …), `lancang` → /p2
  94.49 (−7.30), `T3_19` +10.37 (carried). Census LAW-TRUE 55,982 → 58,684 (+2,702), ADJUDICATED 14,447 → 16,764
  (groundside 2,518 → 4,829). NOT ACCEPTABLE at an approved airport.
* THE MECHANISM (same as KCLT's garages, `--why-vertex`): a ribbon WELDED to a pad whose §37 (9) COVERAGE-EDGE JOIN
  PIN (hard, at the core road's = DEM level) stands a few metres off the rim; `exit_reach` gave the ribbon no run
  because the pad's level is unknown at classify (it reads the DEM at the mouth as the patch level); the ribbon's
  hard cross-section / cap rows then tie the rim to the pin and the PAD — its level a soft datum / facing
  preference, 10a (2) (a) — moves to the road. 09j (1) says the pad is senior and the road comes to it; the hard
  road rows against a soft pad level invert that wherever the pad is not HELD (airside contact, or a #627 datum
  group — the T3 group is hard on origin/main now, so the post-merge pair below is the read that counts).
* CYXY: airside 0 / structure 0; groundside `pav4` (the 04u lot beside building9) 698.42–702.14 → 694.99–702.14
  (51/66 nodes, worst 3.55 m), `dsf:pol131/132/2/124` ≤ 1.47; ribbons `dsf:pol23` 2.99, `small_roads:-1070` 2.99,
  `-1071#1` 1.62 (5 new refs).
* NLWF: 0 movers in every frame.
* SPJC: airside 0 / structure 0; pads building28 25.07 → 22.96 (−2.11), building30 −1.43, building22 +0.70, building7
  +0.42, building23 +0.28 (9 pads); strip `adjacent_ground:taxi:E:zone2#11` 9 nodes worst 3.00 m at
  −12.03225,−77.11186; groundside `dsf:pol36#1/37` ≤ 3.15; 144 new ribbon refs (`small_roads:-9143` +3.58 …).
* OTHH: airside 0 / structure 8 ≤ 0.10; pads building4 0.41, building3 0.32, building9 0.21 (7 pads, 597 nodes);
  214 new ribbon refs, 37 new groundside pieces.
* origin/main d64b880da (#627 one level, #626) MERGED into the branch after these pairs; a base worktree
  `roads609base` at origin/main serves the post-merge pairs (`heca2_*`, `kclt2_*`).

## Closing (branch c6d52bbb0 = 6399c2cf1 + 254207389 + origin/main d64b880da; then 83c51c107 console pin)
* `roads609_KCLT` harness build: rc 0, 435 s, body c96ca98266ce, ledger 9f3bfeb59245; frames registered
  (`frames.py list KCLT` → `frames/roads609/`). vs `frames/kclt608/kclt608_KCLT.osm` (= #627's KCLT 3f22a1e516b3):
  RUNWAY 2 nodes 0.05 m (35.22475552,-80.93645381), solve-owned 46 ≤ 0.05 m, structure 17 tunnel-wall rim nodes ≤ 1.30
  m (35.20218,-80.94025); row-side 320: building90 −4.69, building86 −4.55, building88 −4.32 (the garages to their
  ground 218.33–219.08), building77 +0.65, building59 −0.34; strip 67 ≤ 2.32; groundside dsf:pol84 2.79, pol83 1.25.
  Census: LAW-TRUE 17931 (kclt608 17499), ADJUDICATED 6573 (airside 3038, groundside 3510, mixed 25), CRITICAL
  motion 4 = 4 (worst 0.280 m strip_arc, same site), steps 28 (17).
* TILE BUILD REFUSED by the corpus pre-flight (verbatim): "REFUSING: 1 artifact(s) are MISSING from the shared data
  repo … [dem] Elevation_data/**/N35W081_airport_insets/KVUJ_*.tif [stale] — STALE airport elevation inset
  …/N35W081_airport_insets/KVUJ_usgs3dep.tif — it was cut for -80.178694,35.390689,-80.121899,35.440769 but KVUJ now
  r… To fetch them deliberately: --refresh-data dem" — the master's refresh; no mesh-ground placement read was
  possible for KCLT or HECA this lane (D not done).
* Suites on the merged tree: v2 `tests/auto_patch_v2` 2983 passed / 3 skipped / 1 xfailed / 1 xpassed / 2 FAILED;
  full non-Qt 9634 passed / 19 skipped / 1 xfailed / 1 xpassed / 4 FAILED — the two console-encoding rows fixed
  (83c51c107); the two HECA real-map pins still RED: `test_gap_apron::test_the_class_table_read_on_a_real_map` (38
  gap pieces → 60 + 12 gap aprons; road pieces [0,2,4,7,11,12,28,29] → [0,1,7,9,16,20,44,49,65]; aprons no-road
  [22,24,35] → [41,43,68], road [13,15,16,17,20,30,33,36] → [11,19,21,28,29,36,53,60,69]; stats (11, 8) → (12, 9))
  and `test_gap_terrace::test_the_rule_read_on_a_real_map_gives_the_recorded_counts` — NOT re-pinned: a pin of a
  HECA table the branch changes, left red for the master's decision. Ratchets: DUPLICATE PASS, LAYER PASS; size WARN
  classify/roles.py 1444 → 1522 (+78 here; the main merge carries the rest).
* Post-merge HECA pair (`heca2_base/` roads609base = origin/main d64b880da, `heca2_arm/`): base done; the arm's hard
  set is 565,731 rows (LP 17.6 s, OVER BUDGET, 0 relaxed) — see the report for its delta if it landed.
