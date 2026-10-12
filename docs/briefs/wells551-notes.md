# wells551 — no pit at the jetways (#551)

## RESUME HERE (2026-10-12, resumed lane; main merged at 1ff5a912a, docs only)

DONE: witness landed 7a8356d44 (unchanged since). Replay pair on `pads67/OTHH.pkl` (`--from planar
--emit`; base = basins526's `g_planar` replay under main's code, arm = this branch): basin WAYS 49 -> 10
(45 -> 10 basins; the 4 extra ways are `#1` split parts of basins 15/32/48/63). The 10 kept basins are
BYTE-IDENTICAL (ring node lat/lon + alt), 39 removed, every removed one a jetway (Type4 x9, Type5 x7,
Type6 x11, Type7 x14, Type8 x4, Type10 x2 memberships). Node movers > 0.01 m over the 32,713 common
nodes: 0; runway nodes 1,867: 0 moved, 0 missing. Only-base nodes 1,491 (the removed rings: tunnel_trench
412, apron 376, building 81, untagged 1,107); only-arm 82 (apron faces re-knit where a ring left). Ways by
role: tunnel_trench 49 -> 10, apron 152 -> 151, building 183 -> 179, untagged 221 -> 186. The 15 authored
seats (6 pit rims basin:1/2/3/4/5/8 + 9 tunnel crests, #525) identical; #448/#451 drainage basins 1/2/3/5/8
kept identical. Owner sites: 25.263167,51.6135647 was INSIDE basin:71 and 25.2637538,51.6131875 inside
basin:32 — both gone; 25.2631354,51.6134952 lies 1.7 m from basin:68's centroid and 25.2630678,51.6118374
~4 m from basin:17's (the point is beside the ring) — both gone; no arm basin holds any of the four.
Other sweep airports by their pads67 captures (`witness_probe.py`): HECA 3 EGCC_Jetway_metal_03 placements
refused standing (top 10.81 / plate -4.30), witnesses after 0 — HECA builds 0 basins before and after
(sw8/sw12 frames: 0 basin ways); KCLT 0 standing, 0 witnesses, 0 basins; CYXY/KASE/NLWF 0; SPJC 1
(torre_nueva.obj, a 62 m tower over a 4.7 m plate; witnesses after 0; sw8_SPJC has no basin). Suites:
test_wells551 + test_m4b + test_no_airport_specific_code 22 passed; ratchets PASS (dupes, layers).
Scripts: scratchpad `w551/basin_table.py` (table + movers + sites), `w551/witness_probe.py`.
IN FLIGHT: closing harness build `wells551b_OTHH` (--patch-only; a dead-session `wells551_OTHH` stem in
/tmp/harness blocked the first tag) and the v2 suite. NEXT: census A/B vs basins526_OTHH, body hash,
register the frame, final report.

### Basin table (base = basins526_OTHH build / g_planar replay, both 45; arm = replay, 10)
| base id | source objects | floor_z | floor alt | ring nodes | centroid lat, lon | verdict | arm id |
| basin:0 | OTHH_Drainage_06_000.obj, OTHH_Drainage_06_001.obj | -0.24 | [-0.74] | 41 | 25.2536287, 51.6256649 | KEPT identical | basin:0 |
| basin:1 | OTHH_Drainage_03_LOD0_000.obj, OTHH_Drainage_03_LOD0_001.obj | 0.15 | [-0.35] | 27 | 25.2919175, 51.6058785 | KEPT identical | basin:1 |
| basin:2 | OTHH_Drainage_01_LOD0_000.obj, OTHH_Drainage_01_LOD0_001.obj | 0.15 | [-0.35] | 31 | 25.2956323, 51.6046429 | KEPT identical | basin:2 |
| basin:3 | OTHH_Drainage_02_LOD0_000.obj, OTHH_Drainage_02_LOD0_001.obj | 0.15 | [-0.35] | 24 | 25.2964105, 51.6066101 | KEPT identical | basin:3 |
| basin:4 | OTHH_Dewatering_01_LOD0_002.obj | -9.18 | [-9.68] | 25 | 25.2958440, 51.6031740 | KEPT identical | basin:4 |
| basin:5 | OTHH_Drainage_04_LOD0_000.obj, OTHH_Drainage_04_LOD0_001.obj | 0.15 | [-0.35] | 20 | 25.2536840, 51.6231058 | KEPT identical | basin:5 |
| basin:6 | OTHH_Dewatering_02_LOD0_002.obj | -9.18 | [-9.68] | 25 | 25.2520500, 51.6246163 | KEPT identical | basin:6 |
| basin:7 | OTHH_Drainage_06_000.obj, OTHH_Drainage_06_001.obj | -0.24 | [-0.74] | 18 | 25.2536326, 51.6243920 | KEPT identical | basin:7 |
| basin:8 | OTHH_Drainage_05_000.obj, OTHH_Drainage_05_001.obj | 0.15 | [-0.35] | 5 | 25.2538893, 51.6221427 | KEPT identical | basin:8 |
| basin:9 | OTHH_Drainage_06_001.obj | -0.24 | [-0.74] | 4 | 25.2535061, 51.6239857 | KEPT identical | basin:9 |
| basin:10 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 27 | 25.2629686, 51.6162362 | REMOVED standing | - |
| basin:11 | OTHH_Jetway_Type5.obj | -0.34 | [-0.84] | 27 | 25.2610506, 51.6109463 | REMOVED standing | - |
| basin:12 | OTHH_Jetway_Type5.obj | -0.34 | [-0.84] | 29 | 25.2607603, 51.6101417 | REMOVED standing | - |
| basin:15 | OTHH_Jetway_Type5.obj | -0.34 | [-0.84, 2.3] | 11 | 25.2656237, 51.6108343 | REMOVED standing | - |
| basin:15#1 | OTHH_Jetway_Type5.obj | -0.34 | [1.97, 2.3] | 5 | 25.2656044, 51.6108308 | REMOVED standing | - |
| basin:17 | OTHH_Jetway_Type5.obj | -0.34 | [-0.84] | 17 | 25.2630874, 51.6118733 | REMOVED standing | - |
| basin:19 | OTHH_Jetway_Type5.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2643711, 51.6114056 | REMOVED standing | - |
| basin:21 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 7 | 25.2668489, 51.6096847 | REMOVED standing | - |
| basin:23 | OTHH_Jetway_Type5.obj | -0.34 | [-0.84, 0.96] | 7 | 25.2604693, 51.6094272 | REMOVED standing | - |
| basin:25 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 8 | 25.2626405, 51.6154080 | REMOVED standing | - |
| basin:30 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 8 | 25.2716605, 51.6122074 | REMOVED standing | - |
| basin:32 | OTHH_Jetway_Type6.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 7 | 25.2637570, 51.6131861 | REMOVED standing | - |
| basin:32#1 | OTHH_Jetway_Type6.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 6 | 25.2637260, 51.6133008 | REMOVED standing | - |
| basin:43 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 9 | 25.2678015, 51.6074584 | REMOVED standing | - |
| basin:45 | OTHH_Jetway_Type6.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2643609, 51.6129158 | REMOVED standing | - |
| basin:46 | OTHH_Jetway_Type6.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 9 | 25.2649594, 51.6127017 | REMOVED standing | - |
| basin:47 | OTHH_Jetway_Type6.obj, OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 7 | 25.2656360, 51.6123409 | REMOVED standing | - |
| basin:48 | OTHH_Jetway_Type10.obj, OTHH_Jetway_Type8.obj | -0.34 | [-0.84] | 8 | 25.2612973, 51.6117021 | REMOVED standing | - |
| basin:48#1 | OTHH_Jetway_Type10.obj, OTHH_Jetway_Type8.obj | -0.34 | [-0.84] | 5 | 25.2613761, 51.6117262 | REMOVED standing | - |
| basin:50 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2680085, 51.6054802 | REMOVED standing | - |
| basin:57 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 9 | 25.2633429, 51.6173800 | REMOVED standing | - |
| basin:61 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 6 | 25.2594773, 51.6090867 | REMOVED standing | - |
| basin:62 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 12 | 25.2595025, 51.6094735 | REMOVED standing | - |
| basin:63 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84, 0.86, 0.97, 2.31] | 9 | 25.2621804, 51.6168632 | REMOVED standing | - |
| basin:63#1 | OTHH_Jetway_Type4.obj | -0.34 | [2.31, 2.51] | 4 | 25.2621649, 51.6168617 | REMOVED standing | - |
| basin:65 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2662798, 51.6105178 | REMOVED standing | - |
| basin:66 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2686319, 51.6124332 | REMOVED standing | - |
| basin:67 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 9 | 25.2680272, 51.6121420 | REMOVED standing | - |
| basin:68 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 7 | 25.2631496, 51.6135023 | REMOVED standing | - |
| basin:69 | OTHH_Jetway_Type8.obj | -0.34 | [-0.84] | 8 | 25.2672113, 51.6089151 | REMOVED standing | - |
| basin:71 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 8 | 25.2631574, 51.6135653 | REMOVED standing | - |
| basin:72 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 8 | 25.2670516, 51.6118431 | REMOVED standing | - |
| basin:75 | OTHH_Jetway_Type8.obj | -0.34 | [-0.84] | 10 | 25.2671576, 51.6088791 | REMOVED standing | - |
| basin:78 | OTHH_Jetway_Type6.obj | -0.31 | [-0.81] | 7 | 25.2670378, 51.6117715 | REMOVED standing | - |
| basin:82 | OTHH_Jetway_Type7.obj | -0.35 | [-0.85] | 6 | 25.2715171, 51.6151188 | REMOVED standing | - |
| basin:88 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 7 | 25.2621984, 51.6169257 | REMOVED standing | - |
| basin:90 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 8 | 25.2594485, 51.6095051 | REMOVED standing | - |
| basin:94 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 8 | 25.2633135, 51.6173277 | REMOVED standing | - |
| basin:100 | OTHH_Jetway_Type4.obj | -0.34 | [-0.84] | 10 | 25.2634043, 51.6173445 | REMOVED standing | - |

## (2026-10-10 session notes follow)


Branch `claude/wells551` from main 4b60e97ed. Reference: `/tmp/harness/basins526_OTHH.*` (45 basins,
35 from `Jetway/OTHH_Jetway_Type*.obj`), replay base = the basins526 lane's `g_planar` replay of
`pads67/OTHH.pkl` (main's code).

## 1. The owner's question — what in the jetway object made the engine cut a pit

Each jetway OBJ carries a SERVICE ROOM under the rotunda, modelled in full (`<scratch>/wells551/
comp_probe.py`): a floor plate at y −4.27…−4.31 (20–39 m² of horizontals at depth, 0.26–0.48 of the
41–76 m² footprint), a staircase from +1.0 down to −4.3 (steps 0.15 m apart), ducts and equipment
(~1,300 welded components), the room's ceiling AT the apron. The DSF row is a plain `OBJECT`.
Rule 1 (`airport/obj8._read_placement`, per component) admits a thick solid whose floor is ≥ 2.5 m
under the ground and under its own datum, with a |n_y| ≥ 0.7 plate, whose shell tops out within the
1 m contact band of the ground (`rim_reaches_grade`); `through_grade` refuses only a COMPONENT rising
through the ground. The room passes exactly like a pit (its ceiling is at grade); the 9 m rotunda
above is other components. The 35 "pits" are 4.8 m cuts to the room floor + 0.5 m.

## 2. The two populations (`pop_table.txt`, `lid_table.txt`)

| population | row | plate y | solid top y | top/depth | pack cover above the band |
|---|---|---|---|---|---|
| Drainage 01–05 | OBJECT_AGL +4.30 (kept, §18) | −3.82 | +0.06 | 0.01 | 0.00 |
| Drainage 06 (incl. walled sump basin:9) | OBJECT | −4.20 | +0.06 | 0.01 | 0.00 |
| Dewatering 01 / 02 | OBJECT_AGL +13.50 / OBJECT | −13.14 | +5.35 | 0.41 | 0.02 |
| Jetway Type4–8, 10 (35) | OBJECT | −4.27…−4.31 | +9.01 / +9.34 | 2.09–2.17 | 0.26–1.00 |

Candidates: (a) own lid — refuted (the Drainage sumps have a grating at +0.06 over 100 % of the
plate; real pits); (b) the author's lift — refuted alone (Drainage 06 / Dewatering 02 plain rows,
real pits); (c) pack cover ≥ 0.5 (the existing diagnostic key) — 34 of 35, basin:75 at 0.26 survives;
(d) DEPTH vs HEIGHT: pits 0.01–0.41, wells 2.09–2.17, a ×5 gap with only 1 in it — chosen, no number.

## 3. What landed

`obj8._read_placement`: after the component loop, a placement with witnesses whose solid top
(`base + max component max_y − anchor ground`) exceeds its deepest plate's depth is STANDING ON THE
GROUND: witnesses dropped, `ObjReport.standing[path] = (n, top, depth)`; `_absorb` merges it;
`planar/basins._no_floor_refusals` prints it. Classify-time membership and the plan's below-grade
skip read the same answer. The 04i basement test stays as the second line (its m4b twin amended:
a building 8 m over a 5 m basement is now refused at the read). Twins: `tests/auto_patch_v2/
test_wells551.py` (open pit cut; building on its own basement refused; pit under another object's
canopy stays). Spec §47 (8); `[basin]` comment in structures.toml.

## 4. OTHH replay (pads67 capture, `--from planar --emit`): 45 → 10 basins (the 35 jetway wells
removed by design, listed in the spec); 15 authored seats identical; node movers vs the main-code
replay: 0 (every common node within 0.01 m); the removed rings' nodes are the only-base nodes.
