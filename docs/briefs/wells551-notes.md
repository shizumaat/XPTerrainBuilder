# wells551 — no pit at the jetways (#551)

## RESUME HERE (2026-10-12, resumed lane; main merged at 1ff5a912a, docs only)

WITNESS REVISED 82eafb1b8 (+ 64d02c7f1 code key): the v2 suite on the first witness (height against depth
alone) FAILED two owner-ruled twins — `test_v2lemd4::test_a_tower_in_the_pit_is_cover_not_the_rim`
(2026-09-06f: 8 m tower on a 5 m pit's rim = pit) and `test_v2lemd3::test_a_partly_covered_region_is_a_
pit_the_pad_yields_inside` (2026-09-06c: 8 m box over HALF a 5 m pit = covered pit) — both taller than deep.
The separator they keep and the jetway lacks is an OPEN PLATE (`w551/roof_probe.py`, roof over the object's
own deepest plate): jetway rooms 0.97–0.99, the `whole` twin 1.00, Drainage gratings 1.00, Dewatering
0.02–0.56, `half` 0.47, towers 0.01. The witness is now BOTH: plate roofed by its own solids >=
basement_cover_min (0.9, the 09-06c fraction read on the plate; `airport/obj8_roof.roofed_fraction`,
memoised per (resource, component) in `ResourceCache.roof_memo`) AND top above ground > plate depth.
`ObjReport.standing[path] = (n, top, depth, roofed)`; `ReadLaw.basement_cover_min`; the lemd3 `whole` twin
reads the earlier refusal (like m4b); new twin: bowl + grated sump (OTHH's Drainage pair) stays a pit.
Replay pair (base = basins526 `g_planar`, arm = `w551/arm2`): basin WAYS 49 -> 10 (45 -> 10 basins; the 4
extra ways are `#1` split parts of 15/32/48/63), the 10 kept BYTE-IDENTICAL, 39 removed all jetways
(Type4 x9, Type5 x7, Type6 x11, Type7 x14, Type8 x4, Type10 x2 memberships); movers > 0.01 m over 32,713
common nodes 0; runway 1,867 nodes 0 moved / 0 missing; only-base 1,491 (the removed rings), only-arm 82
(apron re-knit). 15 authored seats identical (6 rims basin:1/2/3/4/5/8 + 9 tunnel crests, #525); #448/#451
basins 1/2/3/5/8 identical. Arm1 (first witness) vs arm2: same node set, 0 movers, node NUMBERING differs
only. Owner sites: 25.263167,51.6135647 inside basin:71 and 25.2637538,51.6131875 inside basin:32 — gone;
25.2631354,51.6134952 (1.7 m off basin:68) and 25.2630678,51.6118374 (~4 m off basin:17) — gone; no arm
basin holds any. Other airports (`witness_probe.py` on pads67 captures, revised): OTHH 124 standing in 7
resources (Type4/5/6/7/8/10 roofed 1.00 + PowerStation_Clutter_000 x1 9.29 over 2.55 roofed 1.00;
Type6_Tall x6 no longer standing — roofed < 0.9 in the engine's read — they witnessed under main too and
formed no basin); HECA 0 standing, 3 EGCC_Jetway witnesses as under main, 0 basins before/after (sw8/sw12);
SPJC torre_nueva x1 standing (62 m over 4.7, roofed 1.00; sw8_SPJC has no basin: 0 -> 0); KCLT 0/0.
Suites: v2 + harness + no-airport-code + v1_retired: 3355 passed 1 failed (the code key, fixed 64d02c7f1)
18 errors under xdist that PASS serially (load); ratchets PASS. IN FLIGHT: closing build `wells551c_OTHH`
(the partition code key changed: cold partition). NEXT: census A/B vs basins526_OTHH, body, register,
spec §47 (8) MEASURED, final report.


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
