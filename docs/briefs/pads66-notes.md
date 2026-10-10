# pads66 notes — finishes `claude/pads63` (PR #480) for the master's merge, 2026-10-09

Scratch `<scratch>/pads66/` (`.progress`; `build.sh` / `hold.sh` = the sweep builds, serial, held on other lanes' engine work with a 20 s
poll; `inst.sh ICAO` = one airport's whole read against its main reference, each census / feet under its own tree's tool; `zat.py`
= the surface at a coordinate on two graded.json; `bank.py` = the pad-rim bank read; `fam.py`, `feetbins.py`, `rw.py`, `feet10.sh`).

## Item 1 — `airside_no_step` reads the pad-weld face allowance (`ffd3dde2`)

* `tools/check_grade.py` `_check_published_law_edges(..., weld_nodes=)`: the §1.1 published route pair answers to `budget_m +
  _weld_give(...)` — the ONE reader the three pavement families use — with `d` = the record's `dist_m` (the ROUTE distance the
  engine's `Diff` row is stated on, which is what `weld_floor.widen_face_rows` multiplies `delta` by). The lattice family calls
  the same function without the argument and reads as before.
* DEVIATION 2 of pads65 closed: the sidecar now carries the set itself. `constraints/no_step.hold_interval` writes
  `weld_widened.face_nodes` = the 11-dp coordinates of the vertices of the faces the closing contacts touch (`face_widen[pref][0]`
  — the very set `widen_face_rows` and `pair_graph(bump=)` test membership in), and `weld_widened_nodes(nodes, platforms)` joins
  by identity. The `ways` argument and the join by way `ref` are gone (a `ref` names every face of an apron: at HECA `pav39` is
  20 faces, the contacts touch 2 of them + the plateau face; `face_nodes` 348). The record's `faces` refs stay, informational.
* Twins: `tests/test_weld_floor_census.py` (the face join by identity, a record with refs only reads nothing, the no-step pair on a
  widened face over its route distance / one end off / under-allowance / no record), `tests/auto_patch_v2/test_nearmiss148.py`
  (the engine's record carries `face_nodes`, a subset of the listed face's vertices that contains the near-miss contacts).
* Bodies are unchanged by it (sidecar key only): KASE 718538f4d2e2, SPJC 3ef3e7c7013d, HECA 527f80ef55e7, KCLT e52fc9b4c757,
  OTHH 96d1b4d6cfbc = pads65's `p65_*`.
* HECA re-read (`swq_HECA`, rows within 200 m of `building147`'s west contact 30.12910063740, 31.40069373691): **16 → 7** (bar
  ≤ 4: MISSED by 3). 6 `apron|junction` direct rows 1.63–1.76 % over 94–135 m + the one `apron|apron` RATE row. The 6 are pairs
  with ONE end outside the engine's widened set — two junction vertices of `pav39` faces the contacts do not touch
  (30.12993504303, 31.40049126053 and 30.13017406863, 31.40023697366) — over their unwidened budget by 0.13–0.20 m; no
  `hard_conflict` is recorded within 250 m in the taxi tier. Under pads65's ref join they were allowed (the over-allowance);
  under the engine's own set they are rows the engine did not widen and the emitted surface does not meet. NOT attributed
  further (attempt cap; the seat review's "spill into rows the widening does not name": 62 at p64, 6 now). Family total
  4,026 (main) → 4,038; adjudicated airside 12,204 → 12,010 (p65 under the ref join: 12,024).
* The `apron|apron` 3.33 % row (30.128918, 31.399319, way -10255) is a §1.2 RATE row (grade CHANGE 3.33 %/station over 37.9 m,
  |dz| 0.35) — the weld allowance is a grade allowance and does not apply to it. It is NOT on main's `swga_HECA`: main's one row
  within 200 m is a different rate row (2.69 % over 28.2 m at 30.12908, 31.40090, way -10218).

## Item 2 — the sweep at `ffd3dde2` (`swq_<ICAO>`, `tools/harness/build_airport.py` through the ledger; all rc 0, status optimal, guard clean)

References: `sw6_*` (main) for six, `swga_HECA` (main `e2eec15c`, body ad4ef9685c5f). Reference censuses under MAIN's tool (its
`check_grade.py` / `census.py` last changed 2026-10-07; pads65's / sweeppads' reference JSONs reused), new ones under this tree's.

| | CYXY | NLWF | KASE | SPJC | KCLT | HECA | OTHH |
|---|---|---|---|---|---|---|---|
| body ref → swq | cf8e9e89ec62 → b20103c51fd7 | 45ec40e74dcb → 369eabe9dfef | f9b157158a39 → 718538f4d2e2 | 61f66f149737 → 3ef3e7c7013d | 0b1566de77d5 → e52fc9b4c757 | ad4ef9685c5f → 527f80ef55e7 | 73676fda6914 → 96d1b4d6cfbc |
| = pads65's build | new (swp was df41462dd0b2) | = swp | = p65 | = p65 | = p65 | = p65 | = p65 |
| build s | 24.5 | 6.2 | 31.3 | 69.4 | 236.0 | 498.5 | 469.5 |
| rebake plan vs ref | identical c1b16b8b6d25 | identical 6084575669d1 | identical 4fd4c84874d0 | identical 6fd340d15af6 | identical 511a51f45b14 | DIFFERS 793b2f7479de → 75018e8013b8 | identical 8e24e55b3f68 |
| released pads / welds | 0 / 0 | 0 / 0 | 1 / 4 → 0 / 0 | 0 / 0 | 0 / 0 | 6 / 27 → 0 / 0 | 0 / 0 |
| WARNED pads | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `weld_widened` | – | – | `building1` Δ 1.25 pp, 1 face, 41 nodes, 449 rows, steepest 2.76 % / 14.1 m at 39.22010294331, -106.86487635609 | – | – | `building147` Δ 0.312 pp, 2 refs, 348 nodes, 12,914 rows, steepest 2.12 % / 4.2 m at 30.12789668888, 31.40455951596; sealed `building138` 1 @ 0.021, `building157` 3 @ 0.039, `building165` 3 @ 0.042 | – |
| runway movers > 0.02 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| structure movers > 0.02 | 0 | 0 (no structure) | 0 | 8 `structure_rim:channel_wall` ≤ 0.05 | 4 ≤ 0.06 | 0 | 1 @ 0.04 (the known rim) |
| hard_conflict taxi | 0 = 0 | 0 = 0 | 0 = 0 | 6 = 6 | 51 = 51 | 63 → 64 | 0 = 0 |
| hard_conflict pad | 2 → 4 | 0 = 0 | 66 → 0 | 1 = 1 | 4 → 31 | 27 → 101 | 0 = 0 |
| hard_conflict groundside | 5 → 4 | 7 = 7 | 0 → 2 | 1 = 1 | 291 → 292 | 204 → 232 | 0 = 0 |
| solve-owned movers > 0.02 (worst) | 306 (1.02 strip) | 0 | 107 (0.54) | 303 (0.45) | 1,693 (0.59) | 2,767 (1.01) | 0 |
| … over 0.3 m (far-field > 300 m from a pad) | 30 (0) | 0 | 18 (0) | 1 (0) | 28 (11) | 277 (8) | 0 |
| adjudicated airside | 254 → 265 | 3 → 2 | 2,654 → 2,525 | 891 → 711 | 3,355 → 3,027 | 12,204 → 12,010 | 489 → 160 |
| CRITICAL motion | 0 = 0 | 0 = 0 | 1 = 1 | 0 = 0 | 5 → 4 | 2 = 2 | 0 = 0 |
| CRITICAL visual | 52 = 52 | 23 = 23 | 45 → 44 | 507 → 502 | 1,974 → 1,997 | 1,910 → 1,959 | 1,846 → 1,717 |
| `platform_rim_relief` | 9 → 0 | 1 → 0 | 2 → 0 | 24 → 0 | 53 → 0 | 42 → 0 | 16 → 0 |
| `platform_refused` | 0 | 0 | 1 → 0 | 8 → 6 | 11 → 0 | 5 → 0 | 2 → 0 |
| `pad_frontage_infeasible` | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| feet < 0.3 m | no feet | 134 → 130 | 1,715 → 1,737 | 1,287 → 1,454 | 4,370 → 6,095 | 17,136 → 19,671 | 56,016 → 55,758 |
| feet > 3 m | – | 0 = 0 | 5 → 0 | 62 → 4 | 86 → 90 | 2,383 → 932 | 5,612 → 5,553 |
| placements with a foot > 0.3 m | 0 | 19 → 18 | 56 → 54 | 11 = 11 | 64 → 62 | 245 → 223 | 266 → 263 |

Structure movers, listed: SPJC one channel's rim (the rim is flush with junction `pav6`, which moved — pads65's read): 0.05 at
-12.00990389238, -77.11747097538; 0.04 × 6 at -12.00957845905…-12.00998525071, -77.11763167125…-77.11742965350; 0.02 at
-12.00852080008, -77.11815048659. KCLT `tunnel_ramp` 0.06 at 35.20105481483, -80.94033935031 and 35.20105482035,
-80.94041621906, 0.02 at 35.22699148745, -80.94620242601; `structure_rim:tunnel_wall` 0.02 at 35.22181305165, -80.94187489425.

Read beside the table (found, not fixed):
* HECA pad-tier `hard_conflict` 27 → 101: 81 of them on ONE pad, `building75` (face 972; 61 `pad_slope_max ceiling` + 20 `platform
  plane`, stage 2, worst 1.47 m at 30.12102080807, 31.41858178911; level 100.861 → 100.498); 6 on `building4`, 6 on `building65`.
  KCLT 4 → 31: `building12` 18 (worst 0.21 m at 35.20672335458, -80.93142683988), `building49/b1` 7 (0.34 m), `building79` 3,
  `building49/b0` 2. CYXY 2 → 4 (≤ 0.12 m).
* CYXY (never rebuilt after the fixes): solve-owned 306 movers, worst 1.02 m at 60.70713679960, -135.07154139788 (`graded_strip` +
  `junction`), 30 over 0.3 m, taxi family worst 0.43; `strip_longitudinal` 2 → 5, `strip_arc` 1 → 3 (worst 0.57 → 0.93),
  adjudicated airside 254 → 265 — the one airport whose adjudicated count ROSE.
* OTHH feet: < 0.3 m 56,016 → 55,758 (−258), CRITICAL-motion feet 1,823 on 109 bodies → 1,986 on 110; the plan is byte-identical, so
  it is the surface under them (18 `building` vertices moved, worst 0.19 at 25.28889436857, 51.60295145486).
* KCLT `drainage_minimum` 1,808 → 1,944, `pad_airside_weld` 5 → 8, hairline_pair +24; HECA hairline_pair +49 (pads65's read),
  `frontage_near_miss` 16 → 18 (worst 0.62 → 0.86), `pavement_over_road_cap` n 15 → 22 (airside 0 = 0).
* HECA rebake plan differs from main's (the six `building4/landing*` are new: 5 held at 101.57–101.78).
* HECA `building147` SE corner: a GROUNDSIDE gap ramp `gap:0/s0/ramp0` now joins the pad (71.02) to apron `pav39` (73.28) over
  8.6 m = 26 % at 30.12735096927, 31.40514589283 (main: the collar's 4.8 m bank inside the pad + a 3.1 m step between two gap
  pieces 1 m apart).

## Owner sites (`zat.py` on the two graded.json: the containing face, z by its 3 nearest ring vertices — one reader both sides)

* OTHH terminal 25.259994, 51.6104872 r 150: main 57 faces / 2,330 ring vertices / 12 collar faces / 6 building faces / 29 road faces
  → **56 / 1,742 / 0 / 17 / 29**. The #447–#455 sites: plan byte-identical (8e24e55b3f68); the surface at #453 0.92, #454 0.50,
  #455 −0.07, #451a/b/c −0.35 (basin floors), #450 mouth vertex −1.14 — each identical to main to 0.00 m; structure frame 1 mover
  (the known rim, 0.04); solve-owned movers 0.
* HECA gap sites main → swq: #430 `gap:7/lot` 97.54 → 97.72 (+0.18); #292 `gap:7/ramp0` 98.89 → 99.07 (+0.17); #358 `gap:0/s4/lot`
  89.96 → 90.15 (+0.19). (Main's quoted 97.64 / 98.47 / 90.25 were read on a replay with another reader; this reader on main's
  build gives the left column. The +0.18 is the difference to report.)
* The re-levelled apron 30.1047, 31.3965: `apron:gapapron:1` 103.30 → 103.29, nearest vertex 103.27 → 103.26.
* T3 landings / lots 30.11408, 31.39756: main `parking_lot:dsf:pol10` 94.41 → `building4/landing2#collar`, the vertex at 0.5 m
  on `landing3` at 101.78 (+7.37). Landings `building4/landing0…4` held at 101.734 / 101.570 / 101.674 / 101.784 / 101.633 (deck
  `T3_road.obj`), `landing5` (1.3 m²) no level. The landing collars carry 94.3 → 101.8; lot `dsf:pol10` 79.70 / 89.24 / 95.94.
* `building147` grade profile (datum 70.929 → 71.018): WEST 1.96 % at 9.7 m, 1.75–1.92 % out to 106 m (30.13008841594,
  31.40067803895: −2.04 m); EAST apron contact 30.12817180270, 31.40426373051 +0.15 at 7.7 m = 1.95 %, 1.81 % at 38 m. Main:
  0.00 to 15–22 m (the plateau), steepest 1.56 % east / 0.77 % west.
* The ten blocker-site feet (60 m; within 0.3 / floating / buried), main → swq: 30.1110593, 31.404281 26/64/0 → 23/64/0;
  30.1279552, 31.403143 33/0/87 → 107/0/4; 30.1197331, 31.4092557 69/3/2 = 69/3/2; 30.1167201, 31.4094167 45/0/15 = 45/0/15;
  30.1265141, 31.4031689 0/8/30 → 30/8/0; 30.1125123, 31.3961245 11/150/3 = 11/150/3; 30.1080544, 31.3958302 204/0/68 =
  204/0/68; 30.1110619, 31.4041921 41/66/0 → 36/66/0; 30.1141299, 31.3970260 5/124/12 → 63/61/10; 30.1123068, 31.3953685
  21/86/1 → 48/54/6. Pads: `building4` within 3,827 of 11,416 → 5,244 of 11,913 (bodies floating 170 → 34); `building147` within
  375 of 935 → 881 of 930 (buried 469 → 41).

## The pad-rim bank (`bank.py`: BARE rim vertices = every face at the vertex a pad face, no collar; `meshsec.py` on a real mesh)

On main the collar is INSIDE the pad outline (the outline vertex is the collar's outer rim, at ground level; the flat platform is
inset by the collar width). On the branch the pad is flat to the same outline.

| site | main: the bank | branch: at the outline | bare-rim vertices moved > 0.3 / 1 / 3 m |
|---|---|---|---|
| SPJC `building24` -12.02301598560, -77.10703890752 | platform 24.36 → ground 28.99 = 4.63 m over 15.1 m (31 %), inside the outline | rim 24.35, ground 29.0: **MESH READ** — nodes 2.1–7 m outside the outline at 28.6–29.2 (+4.3…+4.9), triangles 150–315 % (56–72°), median reach 6.2 m; the run is 9 rim vertices ~209 m | 80 / 60 / 38 |
| KASE `building2` 39.22203058774, -106.87134372641 | 2363.14 → 2368.73 = 5.59 m over 20.8 m (27 %), inside | rim 2363.14; no patch node within 74 m (apron `pav6` 2363.18); the step to the ground is 5.59 m, mesh not built; run 19 vertices ~194 m | 31 / 12 / 9 |
| KCLT `building10` 35.20620148932, -80.93964693712 | 214.10 → 218.27 = 4.17 m over 20.9 m (20 %), inside | rim 214.10; first patch node 12.1 m out, service road `small_roads:-7096` at 217.58 (+3.48): 29 % if the mesh spans it straight; run 6 vertices ~125 m | 193 / 102 / 3 |
| HECA `building4` (T3) 30.11161278988, 31.39325661430 (bare) and 30.11141419231, 31.39239027817 (under a landing collar) | the pad's outline band stood at ground 93.1–94.4 for 15+ m inside the outline, the platform 101.79 beyond it | rim 101.79, 7.85–8.70 m ABOVE the lot (main `dsf:pol10` 94.24 at 1.6 m): where a landing collar stands, 8.0 m in 6.5 m (123 %); bare, the first patch node is 15.7 m out at 94.01 | 1,313 / 903 / 592 |

The mesh step: `tools/run_tile_mesh_only.py -13 -78` (ONE run; `--patches-as-is` is refused by the engine now — "auto_patch=ICAO
but NO CIFP data resolves … tile build ABORTED" — so the run regenerated the tile's patches: SPJC body = the sweep's), 110 s,
150,516 vertices / 292,256 triangles, shared repo unchanged.
