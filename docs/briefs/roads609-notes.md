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
* HECA post-merge pair LANDED (origin/main d64b880da vs branch): #627's hard datum group HOLDS the T3 complex
  (building6/7 no longer move); remaining: 92 pads moved — building128 69.86 → 65.33 (−4.53), building33 −3.05,
  building38 −2.97, building13 −2.95 (+ building4's collar 8 nodes), building86 −2.35 …; solve-owned airside 2,786
  movers worst 1.11 m (apron route11 176/194 at 30.12678,31.39606, dsf:objpav383 1.02, pav39 0.27), RUNWAY 90 nodes
  ≤ 0.05 m, strip 609 ≤ 0.20, structure 6 ≤ 0.18. Same mechanism (unheld pads move to the road welded to them,
  10a (2) (a)); every one is an owner item at an approved airport. Branch NOT merge-ready without that list ruled.

## ROUND 2 (RULINGS 2026-10-13a (1)–(3): road yields to the pad; garages stay at 223 with ramps; ramp the -8188 approach)
* Branch merged origin/main (bfda39378); base worktree `roads609base` at origin/main (`kclt3_base/` replay).
* MECHANISM CHOSEN: a stage-2 rewrite, `constraints/road_ramp.pad_ramp_rewrite` (called LAST in `reach_seed_rewrite`,
  after `pad_weld_release`): over the ribbon NETWORK a pad serves (every mapped-road ribbon face sharing a rim with a
  building pad, and every ribbon face reached from one through shared vertices, stopping at a face that touches
  stage-1 airside — those keep the airside foot's rows), every vertex off the rim: §37 (6) target + hard ceiling
  withdrawn; §37 (9) coverage-edge join pin released OUTRIGHT (recorded stage "2p" → `with_pin_yield`, the core road
  carries the ramp outward under its own cap-Lipschitz levelling — the run the ribbon cannot have inside the
  patch); ONE one-way design row `z[v] − z[rim] = clip(dem[v] − proxy[rim], ±g·d)` (g = `[road_contact]
  ramp_grade` 5 %; head "roads.groundside_road ramp from the pad" registered in `[design] one_way_rulings`); the
  hard cross-section cap rows (10 %) stay. `classify/roles._cut_back_groundside(hold=False)` for the ribbon pass: a
  road reaching a pad is never held off it as a §28 (6) terrace (13a (3)). Twin `tests/auto_patch_v2/test_roads609.py`.
  Why not `exit_reach` at classify: the pad's level is a STAGE-2 unknown (pads are rigid → not `airside_stage_roles`),
  so neither classify nor stage 1 knows it; the core's own levelling outside the patch is the run.
* ARMS (KCLT `--from classify`, pads vs `kclt3_base`): arm3 (welded face only) garages 223 → 218.7–219.3 — the
  neighbouring ribbon face of the same forecourt kept its hard join pin 5.7 m on; arm4 (network) → 220.3–220.8 —
  the released join re-stated as a target at the core's level (221.0) still drew the pad through the design rows;
  arm5 (one-way rows, join Bands too) same; arm6 (join released outright, no target) → **building86 222.59–222.97
  (−0.40), building88 222.61–222.68 (−0.48), building90 222.53–222.99 (−0.50)**; `--why-vertex 16965`: the chain ends
  at a FREE road vertex "held by bending alone" through the design row — the residual is the objective contest
  (many road rows + bending/fit vs the pad's one facing preference); the one-way register did not remove it
  (`one_way_rows` 24,593 in the LP). Other pads vs base: building77 +0.65 (210.45 → 211.10), building59 −0.34,
  building67 −0.23. Solve-owned airside 2 ≤ 0.02; structure 17 ≤ 1.30 (tunnel rims, as round 1).
  BAR (b) "every pad identical within 0.02 m" NOT MET: residual 0.65 / 0.50 m. Next candidate: price the design
  row at a weight below the pad level rows, or lag the rim as a constant from a pad-only pre-pass.
* NOT DONE in round 2: approved-airport pairs, closing harness build vs sw20, ramp table, the mesh read
  (`obj8_split_report --mesh` on seat610), the twin re-pins (gap_apron / gap_terrace) — pending the pad bar.

## ROUND 3 (lane roads609c; master's call on Q-A: (b) seniority by construction) — RESUME HERE
* Branch `claude/roads609` (worktree `.claude/worktrees/roads609c`), origin/main b790c8336 merged (adf54e81c). Base worktree
  `roads609base` moved to origin/main b790c8336; its KCLT replay is `<scratch>/roads609/kclt7_base/` (pads67 capture,
  `--from classify --emit --verify`). Arms `kclt7_arm` … `kclt14_arm` (each with `KCLT.solved.pkl` for `--why-vertex`);
  pair reads `avd_kclt7..14.json` (`airside_value_delta.py BASE ARM --tol 0.02 --by-ref 8 --json`), pad rows via
  `<scratch>/roads609/pad_movers.py AVD.json 0.02`.
* MECHANISM (the one stage 2 already uses to read stage 1): `solve_design` runs stage 2 in TWO passes when the
  rewrite's report names a junior set — SENIOR: `_solve_stage(..., drop=junior, fixed=levels ∪ {junior: DEM},
  drop_faces=junior_faces, levelled_out=lv2)` (the junior vertices' rows and the pad-road faces' triangles and MINTED
  rows out, as stage 1 drops foreign vertices / welded-road rows — `design_stage._groundside_minter(planar, law,
  faces)` now takes a face set and also matches `vertex:N` inputs); JUNIOR: `_solve_stage(..., fixed=levels ∪ lv2)`
  — only the junior vertices unknown, every pad/lot level a CONSTANT. Report: `stages["stage2_senior"]`,
  `reach_seed.junior_vertices/junior_faces`; `_fold_stage` folds the senior pass's counters as stage 1's.
  THE WITNESS (classify, general): `ribbon_mint` flags a ribbon PART whose area inside the AIRSIDE extent (the
  30e (2) extent without the pads) is under `cells.min_area_m2` as `pad_road`; `planar/build` publishes
  `PlanarMap.pad_roads` (refs); `road_ramp._welded_ribbon_vertices` reads only pad roads (airside-touching faces
  excluded): junior = their vertices off a pad rim and off any other pavement face; `near` (the design row to the
  nearest rim) over the rim-connected network as round 2.
  TRAP FOUND AND FIXED: `design_assemble` keyed three stage-1 reads (conforming rows dropped, welded-road rows dropped,
  ribbon-free bodies) on `drop` being non-empty — the senior pass tripped them and the pads fell 5 m (kclt7_arm);
  they key on `stage_roles is not None` now (stage 1's own signal).
* MEASURED, KCLT pair vs origin/main (pads > 0.02 m):
  | arm | junior set | garages 86/88/90 | other pads |
  | kclt7 | pad network, drop-keyed stage-1 reads | −5.26/−4.94/−5.90 (the trap) | 33 pads |
  | kclt8 | pad network (stop at airside) | −0.03/−0.03/−0.03 | b77 +0.65, b59 −0.34, b67 −0.22, b26 0.09, b56 0.07, b6/b74 0.04 |
  | kclt9 | EVERY airside-free ribbon | −0.03 | b58 +2.20, b59 +1.46, b67 −0.99, b72 +0.81, b26 −0.72, b77 +0.55, b57 −0.33 … (16) — main's lots are pulled by main's roads today; freed, they take no-road levels and their pads follow |
  | kclt10 | pad network, stop at any pavement | −0.03 | b77 +0.65, b59 −0.34, b67 −0.17, b56 0.07, b74 0.03 |
  | kclt11/12/13/14 | pad-road witness (way / part / part-area), junior faces' minted rows dropped | −0.03 | b77 +0.65, b59 −0.34, b67 −0.17, b56 0.07, b74 0.03 (identical in every arm) |
  Solve-owned airside 0 movers in every arm from kclt8 on; structure 12 ≤ 1.30 (tunnel rims, as rounds 1–2).
* BAR NOT MET. Two residuals: (a) the garages −0.03 m (222.99→222.96; a 0.03 shift of the whole rigid plane — a
  planar-map difference, not a road row: the junior pass has NO pad column; unattributed); (b) building77 +0.65,
  building59 −0.34, building67 −0.17 — INVARIANT under every junior configuration, so NOT the solve: they are
  welded to lots `dsf:pol71` (+0.76) / `dsf:pol58` (+1.04), and pol71 follows `dsf:pol83` (+1.25) which follows
  `dsf:pol84` (+2.79, nodes 6 m above DEM at 1794,474 frame m; `--why-vertex 19668`: "no row binds — the objective
  holds it"). pol84 is touched by `dsf:pol53`, building74 and `small_roads:-3991#2/#3/#4` (#3/#4 NEW in the arm, a
  network-bridged stretch of an airside-admitted way; not a pad road). Every solve-side treatment of -3991 left pol84
  unchanged, so the lift is upstream: round 1's classify/planar changes — the ribbon touch-witness pass
  (`_cut_back_groundside(only=new ribbon cells, hold=False)`, which welds instead of knifing), the network bridge
  admitting #3/#4 beside pol84, or the pad extent. NEXT: a classify intervention pair (hold=True for the ribbon
  pass; then no bridge) read at pol84 — `a1_extent_arm.py` is the instrument shape.
* NOT DONE: the ramp table, approved-airport pairs, twin re-pins (`test_gap_apron`/`test_gap_terrace` still red,
  state as round 1), closing build, #229, suites beyond the touched files (72 passed).

## ROUND 4 (lane roads609d; RULINGS 2026-10-13b (5), 13d, 13e) — RESUME HERE
* Branch `claude/roads609` (worktree `.claude/worktrees/roads609c`), origin/main 574729a79 merged (7d49fae88); base
  worktree `roads609base` at 574729a79. Scratch `<scratch>/roads609/r4/`: `base/` (main replay), `arm0` (882fb55da),
  `a_hold` / `a_nobridge` / `a_noextent` (intervention arms, `arm_run.py` + `run_arm.sh`), `a2_b` (the branch's
  `--gap-free` base), `a4` (the late stage, `run_late2.sh`), `pair.sh ICAO TAG` (harness pair vs `/tmp/harness/sw23_*`),
  `build*_ICAO.log`. REPLAY IS NOW TWO RUNS: `--from classify --gap-free --solved-out B.pkl` then
  `--from classify --late-from B.pkl` (the single `--from classify` run solves the pad roads in one solve — not the build).
* ATTRIBUTION OF ROUND 3'S RESIDUALS (KCLT pair vs main, one intervention each, `avd_a_*.json`):
  | arm | garages 86/88/90 | building77 | pol84 / pol83 / pol71 | structures |
  | branch 882fb55da | −0.03 ×3 | +0.65 | +2.79 / +1.25 / +0.76 | 12 tunnel rims ≤ 1.30 |
  | (a) ribbon pass `hold=True` | −0.03 ×3 | +0.65 | identical to the branch | identical — NOT the cause |
  | (b) no network bridge | 0 / −0.03 / 0 | 0 | 0 / 0.02 / 0.28 | 0 (but building59 −0.54, pol58 0.54) |
  | (c) pads not in the extent | 0 ×3 | +0.65 | identical to the branch | identical |
  So: the lot chain and the tunnel rims came from the NETWORK BRIDGE admitting stretches between two airside mouths
  (`small_roads:-3991#3/#4`, `-30357/-30359`), the garages' −0.03 from the forecourt admitted through the pad extent,
  building59/67 from the patch's own ribbons being WELDED where main knifed. Then a deeper one: with every new road
  junior (round 3's two-pass solve) pol84 still rose 2.93 m — the constraint set was generated from the map WITH the
  roads, so the patch's own ribbons re-read their borders (terrace / between-levels / join rewrites) and moved
  (93 main ribbons ≤ 2.43 m), the lots with them. No row order inside one map removes that.
* MECHANISM (replaces round 3's senior/junior solve, which is DELETED — `solve/design*.py` are main's again):
  1. `classify/ribbon_mint`: `mint_osm_ribbons` is main's mint again (per-way bridge, pads knifed, `ribbon_extent`
     without pads); `mint_pad_roads` runs LAST (after the gap pieces) over what `network_spans(extent ∪ pads,
     serve=pads)` adds — a path is bridged only when one of its mouths stands on a pad — less the first pass's spans,
     pads subtracted at the footprint, evidence `pad_road`; the touch witness reads those cells only (`hold=False`).
  2. THE PAD ROAD IS A FOLLOWER OF THE LAST STAGE (§55 (4), the gap pieces' own machinery): `stage_one_map.gap_free`
     drops pad-road cells too, `late_followers` adds `model.planar.pad_road_faces`; `pad_ramp_rewrite` runs in
     `run_late_stage` (released joins published through `pin_yield`). The base map is main's, cell for cell.
  3. `constraints/pad_road_reach` (13d's read): per pad|road network between two standing levels, least grade =
     |rise| / run along the pad roads' edges; over the road cap the remainder, `shift_m` inside `[road_contact]
     pad_shift_max_m` (0.5 m, working value), `step_m` left. READ AND LOGGED, NOT APPLIED.
* MEASURED (harness builds at 8231c75f9, tag `r4c_<ICAO>`, vs `/tmp/harness/sw23_<ICAO>.osm` = main 574729a79;
  CYXY / NLWF at a3b11615b, tag `r4_`, no pad road there):
  | airport | pads > 0.02 m | solve-owned airside | structures | pad roads | other movers | rebake plan | build s (sw23 → branch) |
  | KCLT | 0 | 0 | 0 | 35 | none | identical | 344 → 415 |
  | HECA | 0 | 0 | 0 | 202 | 24 gap parts / 399 nodes worst 7.36 m (`gap:5/s0`), 10 follower ribbons ≤ 0.68 m | identical | 704 → 743 |
  | OTHH | 0 | 0 | 0 | 171 | 7 gap pieces / 16 nodes worst 0.20 m (`gap:27`) | 2 deck datums: unit:24 4.61 → 4.46, unit:20 3.96 → 3.97 | 420 → 534 |
  | SPJC | 0 | 0 (1 node ADDED) | 0 | 138 | none | units identical (one stock library resource unresolved — environment) | 81 → 121 |
  | KASE | 0 | 0 | 0 | 6 | none | identical | 36 → 47 |
  | CYXY | 0 | 0 | 0 | 0 | body b3d42825d802 = sw23 | — | 32 → 35 |
  | NLWF | 0 | 0 | 0 | 0 | body 500d6429f065 = sw23 | — | 7 → 7 |
  (six builds ran in parallel: the wall times are not a timing measurement.) KCLT replay: the branch's `--gap-free`
  patch is BYTE-IDENTICAL to main's (`cmp`), late stage "none relaxed", fixed off constant 0.
* 13d TABLE — pad|road networks where no ramp inside 10 % fits (pad fixed; the shift is read, not applied):
  | airport | pad | rise / run | grade needed | far end | remainder | shift inside 0.5 | step left |
  | SPJC | building24 | +3.90 / 2.4 m | 161 % | lot `dsf:pol36#1` −12.0238115,−77.1070113 | +3.66 | +0.50 | 3.16 |
  | SPJC | building24 | +3.95 / 14.2 m | 27.9 % | lot `dsf:pol35` −12.0221301,−77.1077552 | +2.53 | +0.50 | 2.03 |
  | SPJC | building8 | +2.01 / 17.5 m | 11.5 % | apron `pav35` −12.0319743,−77.1046877 | +0.26 | +0.26 | 0 |
  | HECA | building148 ↔ building152 | 2.39 / 13.7 m | 17.5 % | each other, 30.1289254,31.4137903 | ±1.02 | ±0.50 | 0.52 (0.02 if both move) |
  KCLT 0 of 5, OTHH 0 of 2, KASE 0 of 1.
* KCLT RAMPS (`road_course_profile --on-patch`, `r4/ramps_a4.txt`): on-patch worst over 10 m — forecourt `-16661` 0.8 %,
  `-16664` 0.8 %, `-16649` 2.4 %, `-16651` 0.4 %, `-24655` 3.4 %, `-24651` 4.5 %; approaches `-8186` 5.7 %, `-8188`
  3.9 %, `-8200` 1.8 % (the 5.1 m wall at 35.222959,−80.945684 is gone on-patch). AT THE PATCH EDGE the instrument reads
  47–55 % over 10 m at seven exits (e.g. 35.224347,−80.945714; 35.225615,−80.945279; 35.223856,−80.945906): the pad
  roads stand at 223 and the capture DEM outside is 218. The join yields are published (`road_join_yield`, +3.6 … +5.2 m
  at those exits) for the core road to carry the ramp outward — NOT VERIFIED: needs a tile build (mesh).
* KNOWN DEFECT, NOT FIXED: at an airport with BOTH gap pieces and pad roads (HECA, OTHH) the two are unknowns of
  the same last stage, and the pad roads' rows move the gap pieces (HECA `gap:5/s0` −7.36 m beside T3). FIX SHAPE:
  the pad roads as their own stage after the gap pieces — `run_late_stage` a second time, base = the gap stage's
  result, no cut, followers = pad roads only (one more derive at those airports).
* NOT BUILT: 13d step 2 (the pad shift — a pad welded to a standing lot or apron cannot move without re-solving
  what it is welded to: owner/spec question), 13e step 3 (explicit release of the longitudinal cap spread over the
  run; today an infeasible pad road is relaxed by the hard-feasibility LP row by row) and its consumer census of
  "road ≤ 10 %" readers; ramps inside the patch at the exits; the mesh read; #229.

### ROUND 4 — STATE AT THE STOP (WIP commit; machine shutdown 2026-10-13)
* OWNER RULED Q1 = option 1 (RULINGS 2026-10-13f): only FREE-STANDING pads shift (≤ 0.5 m, `[road_contact]
  pad_shift_max_m`); a pad welded to a lot or apron stays and the road steepens (13e). NOT BUILT (the reach read
  reports `shift_m`; nothing applies it).
* DONE AND MEASURED (commit 3a8de8be8): the pad roads' OWN stage after the gap pieces — `late_stage.run_last_stages`
  (gap stage on the classification without pad roads, then `run_late_stage(roads_only=True)`; a second derive only
  where both exist). Replay vs main's late stage (`r4/ref_OTHH`, `r4/ref_HECA`; arms `o3`, `h1`): OTHH and HECA
  0 movers in every frame, gap pieces 0, follower ribbons 0, only pad roads added. One late stage with an internal
  order on ONE derive was tried first (`o1`/`o2`): 12 gap nodes still moved ≤ 0.20 m at OTHH — refuted, deleted.
  Cost: one more derive (HECA ~97 s, OTHH ~72 s). NOT yet re-proved by harness builds (rebake plans not re-compared).
* IN THE WIP COMMIT, HALF-DONE (unit twins green: test_roads609, test_roadmint100, test_late_stage; full suite NOT
  re-run; no twin yet for the three new pieces):
  1. `constraints/pad_road_reach.pad_grade_release` (13e): widens the longitudinal `Diff` caps of a pad|road network
     whose least grade is over the cap, drops its PAD_RAMP design rows; called in `run_late_stage`. Not yet exercised
     on a real case (KCLT has none; run SPJC / HECA). The CENSUS LAW CONTEXT IS OWED: readers that assume a road
     ≤ 10 % — `tools/check_grade.py` road families (road_cross_section / within_shape / the `road_cap_governs`
     readers at :2908 :3670 :4317), `verify/strips.py` `road_cap_geometry`, `emit/road_join.with_pin_yield`'s
     budget, object seating on road faces — need a sidecar key for the released stretches (`pad_ramp["released"]`
     is in the late report only).
  2. `pad_road_reach`: a far end nearer than the road is wide (2 × lane width) is BESIDE the pad, not along the
     road, and is skipped (SPJC building24's 2.4 m / 161 % row was a lot across the road, by inference from
     run < width — not yet looked at on the map).
  3. `classify/pad_road_exit.extend_pad_roads` (the ramp INSIDE the patch): in the roads stage the classification
     is rewritten — from each patch exit of a pad road the network is walked outward until a 5 % profile from the
     pad's solved level meets the DEM; minted as pad road (`pad_exit`). `_mint_spans(min_len=0.0)` for pad roads.
     KCLT replay `r4/k9` (two runs, base byte-identical to main, pads/airside/structures 0 movers, none relaxed):
     49 exit cells, 2,135 m. DEFECT OPEN: the exit cells do NOT descend — `-8190` stays at 222.6–223.2 over 245 m
     (DEM 217.4–218.2) and drops 53 % at its far patch edge; all its vertices are in `near`, so the PAD_RAMP design
     row is there but does not carry (suspect: `clip(dem − proxy[rim], ±g·d)` reads `preferred_z` of the rim, or the
     row is outweighed by bending between the 223 forecourt and a released far join). Also open: `-24651` 50.8 %
     on-patch at a 6 m dead-end stub, `-24655` / `-30420` / `-16664` s=0 edges (ways that end at a bridge way or a
     sliver). NEXT: `--why-from r4/k9/KCLT.solved.pkl --why-vertex <a -8190#1 vertex>`.
* NEXT COMMANDS (from `<worktree>/Ortho4XP`): replay = `tools/v2_solve_replay.py --replay <frames>/pads67/KCLT.pkl
  --from classify --gap-free --emit B --verify --solved-out B/KCLT.solved.pkl`, then `… --from classify --late-from
  B/KCLT.solved.pkl --emit A --verify --solved-out A/KCLT.solved.pkl` (`r4/run_late.sh NAME ICAO`); the
  `tools/INDEX.md` row for `v2_solve_replay.py` does NOT yet say that pad roads need the two-run form.
* HARNESS RESIDUE of the killed builds: none in the shared data repo (`.harness/locks` empty, no ledger line);
  in `/tmp/harness` only `r4_HECA.*`, `r4b_HECA.*`, `r4b_KCLT.*`, `r4b_OTHH.*` (`.engine_caches`, `.env.json`,
  `.progress`; no patch, no result) — the master's to delete. Frames NOT registered.
* NOT DONE: harness builds on the current code, full suite, ratchets, 13d step 2, the census law context, the
  ramp table on a working exit ramp, the small buildings between the garages, the closing KCLT build, #229.

## ROUND 5 (lane roads609e; RULINGS 2026-10-13a (1)-(3), 13d, 13e, 13f) — RESUME HERE
* Branch `claude/roads609` (worktree `.claude/worktrees/roads609c`), origin/main 94352a0c5 merged (0d4e47c61). Scratch
  `<scratch>/roads609/r5/`: `late.sh NAME ICAO BASE.pkl` (late stage on an existing gap-free base), `two.sh` (both runs),
  `ramps.sh DIR ICAO [PATCH]` (road_course_profile over every pad road of DIR/replay.log), `pair.sh ICAO TAG` (harness
  pair vs sw23: movers, rebake cmp, late-stage log), `read.sh`, `rebake_diff.py`, probes (`at.py`, `faces_ll.py`,
  `patch_at.py`, `ways_at.py`, `exit_probe.py` on `kclt_exit_in.pkl` = extend_pad_roads' grabbed inputs).
* A. The WIP was green as it stood (full non-Qt 9718 passed); ratchets pass.
* B. MECHANISM (KCLT `-8190`, `--why-from r4/k9/KCLT.solved.pkl --why-at 35.223092,-80.944095`): the vertex was held by
  ONE row, `road_ramp` "ramp from the pad", bound `+0.37` m from rim v16908 (222.68 m, a constant). The design row read
  `clip(dem[v] - proxy[r])` with proxy = the rim's DEM (217.5 m), so "0.37 m over the rim" all the way out. Not a weld
  row, not a missing anchor: the row's datum. FIXES (each measured on the KCLT replay, then twinned):
  1. the row reads the rim's STANDING level (the last stage's constants) and the run ALONG the road (shortest path on
     the pad roads' edges; the straight line cut bends);
  2. a road end the arrangement could not weld to a rim node stands off it (pass C's notch, <= 3 identity cells): it
     is at that rim (`-8198`: 0.7 m off the terminal pad, ramped from a rim 133 m round the block, 60 %);
  3. the exit walk: an exit is the way's own crossing of the patch edge off a pad road OR a pad's edge (garage
     entries), never a way vertex that merely lies within a lane of one (`-13743`); the run is the pad's OFFSET over
     its ground / design grade (the old "until a design-grade profile meets the terrain" ran 1,000 m down KASE's
     valley: 2,295 m from 3 exits -> 303 m); the run restarts at every pad the walk passes; an exit within one lane of
     design grade of its ground is not walked; A BRANCH THAT LEADS NOWHERE (a dead end before the run completes) is
     pruned (`-24651`: 17 m stub, its 8 x 1 m tip cell 5 m under the garage lip); exit cells get the ONE touch witness
     (`roles._cut_back_groundside(hold=False)`), so an exit reaching another pad is welded to it;
  4. the row takes the profile NEARER THE GROUND of two at the design grade: toward the terrain never past it, and the
     pad's offset closed over its ground (the first never comes down a slope falling faster than 5 %, the second
     floats over ground rising toward the pad — `-13743` 2.3 m up).
  The instrument: `road_course_profile --gap` (a sample in the patch's closing by 1.5 m reads the nearest ring, not
  the DEM) and a repaired-ring triangle keeps its plane — half the old "47-55 % at the patch edge" readings were one
  sample in a 0.7 m notch sliver or a 0.09 m crack between rings at the same level (`-6064`, `-8190`, `-30417`).
* KCLT RAMP TABLE (closing build `r5b_KCLT`, 72 pad-road ways, `r5/kr5b/compact.txt`): on-patch worst over 10 m <= 10 %
  on 68; over: `-28436` 12.3 % (22 m connector: its first 5 m cross `-8205`'s face obliquely, a 0.57 m seam at the T),
  `-8187` 10.4 %, `-24655` 10.3 %, `-8190` 10.1 % (the centreline read of edges held at the 10 % cap). Patch edge:
  `-24651` 44.9 % and `-24655` 45.4 % at s=0 = the two way TIPS 1 m beyond garage building90's lip (35.225620,
  -80.945188 / 35.225615, -80.945279; main read 47.9 / 48.6 % there — dead ends, pruned, unchanged); every other pad
  road meets the outside ground within 6.4 % (`-10041`). The former 5.1 m wall on `-8188` (35.222959, -80.945684):
  on-patch 5.2 %. Joins still yielding > 0.5 m at the site: the notch joins against pads (road end at 222.5 vs pad
  222.7, the core sliver between them yields, e.g. 35.22283, -80.94256 +6.3 m on `-8201`, 35.22158, -80.94238 +3.4 m
  on `-11471`, 35.22582, -80.94369 +4.7 m at garage building88's entry) and two lateral core joins (35.22310,
  -80.94338 +2.6 m on `-8190#1`; 35.22346, -80.94257 +1.6 m at `-28436`/`-28438`) — NOT VERIFIED in the mesh.
* C. 13e RELEASE exercised on the real cases (closing builds): SPJC building24 -> lot `dsf:pol35` +3.95 m / 14.2 m =
  27.9 % (far end -12.0221301, -77.1077552); building24 -> lot `dsf:pol36#1` +3.72 m / 27.8 m = 13.4 % (-12.0240330,
  -77.1069011); building8 -> apron `pav35` +2.01 m / 17.5 m = 11.5 % (-12.0319743, -77.1046877); HECA building148 <->
  building152 2.39 m / 13.7 m = 17.5 % (30.1289254, 31.4137903). Every pad stays (13f: none is free-standing).
  THE SPJC 2.4 m / 161 % ROW ON THE MAP: building24 is ONE 99,237 m2 pad at 24.36 m whose east rim stands on ground at
  28.21 m (cut 3.85 m into rising ground); the "far end" is a 74 m2 groundside pavement sliver `dsf:pol36#1` at
  28.06-28.33 m 0.63 m off that rim, ACROSS the pad road `-6132#1` from it — a lateral neighbour, not a road end. The
  witness (an end nearer than 2 x lane width is beside the pad) stands; the level difference is the pad's own cut
  bank, there with or without a road (a pad question for the owner, not a road one).
  CONSUMER CENSUS of "road <= 10 %" readers:
  | reader | reads | released stretch |
  | solve, `roads` longitudinal Diff + last-stage `pavement_ceiling` / `pavement_road_cap` Diff | the cap | widened to the stretch's grade x (1 + 1e-3), its vertices only (`pad_grade_release`) |
  | solve, `road_cross_section` | cross-fall | untouched (13e) |
  | solve, PAD_RAMP design rows (5 %) | design grade | dropped on that network |
  | v1 census `check_grade._check_within_shape` | way tag `o4_grade_law_cap_lifted` | LIFTED on those faces, counted in the lifted stats, never silenced; transverse pairs still judged |
  | v2 verify `census_frame(lifted_caps(pm))` | `publication.lifted_caps` | same map, same faces |
  | sidecar `lifted_caps` (evidence) | records | `[shapeID, "pad:<ref>", road ref, run m, grade]` |
  | `road_cap_governs` readers (verify/strips, check_grade :2908 :3670 :4317) | apron / strip pairs under a ribbon | untouched (airside) |
  | `emit/road_join.with_pin_yield` budget | patch exits | untouched (a released stretch lies between two standing levels) |
  | object seating, lateral contiguity `o4_grade_law_cap_t`, road_course_profile | final z / transverse / no law | untouched |
  ONE channel: `PlanarMap.pad_road_released` (face -> pad, run, grade), written by the last stage, read by
  `publication.lifted_caps` — the §34 (9) pinched-ramp lift's own readers.
* D. 13f: `pad_road_reach.free_standing_pads` (no value face but its own and its pad roads' within `[design]
  pad_frontage_m`), `pad_shifts` (the largest `shift_m` its roads ask, none if two ask opposite ways), `shift_pads`
  (every constant on the pad's faces, rigidly); then the reach is read again and 13e releases what is left. NO
  FREE-STANDING CASE at the seven airports (SPJC / HECA's short pads all have other pavement within 3 m) — built on
  a synthetic twin (two free pads 5 m apart over 20 m: each moves 0.5 m toward the other).
* E. Twins `tests/auto_patch_v2/test_roads609e.py` (10): red before on the pre-round code — the four exit twins fail
  on the WIP walk (run, at-grade, stub, pad-edge exit), the rim-level twin asserts the old read in-test, the others
  need what did not exist (the run, the stand-off, the slope profile, 13f, the published lift).
* F. Phase split (closing builds run five in parallel — not a timing measurement; sw23 -> r5b, s): KCLT total 344 ->
  398 (late stage 0 -> 62), HECA 703 -> 830 (115 -> 236), OTHH 420 -> 510 (79 -> 169), SPJC 81 -> 107 (0 -> 27), KASE 36
  -> 37 (0 -> 3); CYXY / NLWF have no pad road and take no late stage (`gap_free` is None: the stage is skipped).
  The cost is the second DERIVE (planar build + every generator over the whole map, then `late_constraints` drops the
  rows with no unknown — KCLT: 2,561 Diff / 918 Linear of them). Cheapest structural reduction, NOT done: a roads-only
  derive — pass C (`planar/ribbons._ribbons_pass_c`) already joins ribbons to a FINISHED arrangement, so the pad
  roads could be noded onto the gap stage's map and only the follower faces' generators run.
* MODULES: `constraints/pad_ramp.py` (new; the pad ramp out of `constraints/road_ramp.py`, which held two things);
  `classify/pad_road_exit.py`; `constraints/pad_road_reach.py` (13f, 13e); `pipeline/late_stage.py`;
  `model/planar.py` (`pad_road_released`); `pipeline/publication.py` (`lifted_caps`, `_lifted_records`);
  `tools/road_course_profile.py` (`--gap`); `tools/INDEX.md` (the two-run replay note, `--gap`).
* G. CLOSING PROOF (harness builds at 7ef473b66, tag `r5b_<ICAO>`, registered `frames.py` lane roads609e; vs
  `/tmp/harness/sw23_<ICAO>` = main 574729a79): pads > 0.02 m 0, solve-owned airside 0, structures 0, every other ref
  family 0 movers at all five (HECA, OTHH gap pieces and main's ribbons included); only new `service_road` refs
  (KCLT 88, HECA 297, OTHH 163, SPJC 321, KASE 9). Node sets: HECA airside one node fewer (a plateau ring), SPJC
  airside one more, OTHH structures four more (added, not moved). Rebake plans: KCLT / HECA / KASE IDENTICAL; OTHH
  one value, `OTHH_TerminalRoads_Parking_000.obj` (dsf:obj8710, unit:24 member 31, a flag deck) `deck_datum_z` 4.61 ->
  4.46 (its deck datum reads the ground under its ring, which is now graded pad road); SPJC counts only (one stock
  library resource `jet_c.obj` "unresolved" where sw23 read it "stock" — the library index, not geometry). CYXY /
  NLWF: no pad road, no late stage — not rebuilt (round 4's bodies b3d42825d802 / 500d6429f065 = sw23).
  CENSUS (`harness/census.py`, law-true totals sw23 / round-4 r4c / round-5 r5b):
  | airport | total | airside | groundside | road_cross_section | within_shape | hairline_pair | hard_conflict |
  | KCLT | 17480 / 17595 / 17857 | 13295 / 13292 / 13292 | 3881 / 3995 / 4254 | 817 / 853 / 950 | 11263 / 11323 / 11410 | 1969 / 1988 / 2063 | 320 / 320 / 321 |
  | HECA | 56359 / 57696 / 58599 | 52812 / 52798 / 52796 | 3347 / 4649 / 5545 | 558 / 826 / 1363 | 45470 / 45998 / 46061 | 1937 / 2240 / 2420 | 389 / 564 / 701 |
  | OTHH | 1803 / 2335 / 2448 | 1102 / 1050 / 1050 | 392 / 861 / 954 | 3 / 30 / 62 | 57 / 127 / 150 | 1615 / 2028 / 2093 | 0 / 18 / 9 |
  | SPJC | 3439 / 3887 / 4550 | 2965 / 2967 / 2969 | 379 / 812 / 1468 | 49 / 130 / 341 | 2453 / 2539 / 2689 | 480 / 671 / 951 | 9 / 61 / 61 |
  | KASE | 3493 / 3507 / 3545 | 3439 / 3439 / 3440 | 41 / 55 / 90 | 13 / 17 / 37 | 2617 / 2619 / 2634 | 43 / 50 / 54 | 0 / 0 / 0 |
  BAR NOT MET on the census: airside is unchanged (or lower), but the groundside families grow with every new pad-road
  face — KCLT attributed row by row: EVERY added row is on a pad-road face (road_cross_section +133 worst 0.80 m,
  within_shape +147 worst 3.77 m, hairline +97, mid_edge_step +2); the standing faces' counts equal sw23's exactly.
  The road_cross_section growth matches the last stage's own hard-feasibility relaxations (HECA 163 rows worst 2.87 m,
  SPJC 40 worst 2.28 m): a pad road welded along a pad on one side and another standing level on the other cannot
  hold the cross-fall cap. HECA's `roads.groundside_road ramp ceiling` relaxations (45, worst 16.85 m) are round 4's
  (h1: 76, worst 16.85 m): pad-road faces that touch airside keep their absolute §37 (6) ceiling while welded to a pad.
* NOT DONE: #229; a fix for the pad-road cross-fall / within-shape growth (next round: attribute HECA / SPJC rows the
  way KCLT's are, then the two classes — cross-fall between a fixed rim and a lower standing edge, and the airside-
  touching pad roads that keep their absolute ceilings); the mesh read of the joins; the roads-only derive (F).
