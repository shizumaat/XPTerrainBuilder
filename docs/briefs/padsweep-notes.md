# Lane `padsweep` — notes (branch `claude/padsweep`)

Merged head for every build below: `c1a26f166` = `claude/pass2` 46c1e433c + `claude/weldverify` ffdd2b16c
(+ `origin/main` 6dfb97854, already contained) + the `solve/linear.py` docstring sentence and the null-space twin.

## 1. Integration

- `git merge origin/claude/weldverify`: ONE conflict, `docs/frames.jsonl` (both sides appended) — both sides kept,
  every line valid JSON (1,076 lines). The spec auto-merged: §61 (0)–(11), §62, §63 each present once. No code
  conflict: since the common ancestor `claude/seat2` ec43c00a the two branches share only
  `airport/road_descent.py` and `pipeline/build.py` in `src/` (main's cloudtidy on both sides), merged clean.
- `git merge origin/main`: already up to date.
- `solve/linear.py::_linear_solve` docstring: the `normal` result depends on `x0`.
  `tests/auto_patch_v2/test_v2linear.py::test_a_null_space_column_keeps_its_warm_start` (8 pass).
- Suites on the merged head: non-Qt split 9,215 passed / 19 skipped / 1 xfailed / 1 xpassed / 1 FAILED
  (`tests/test_auto_patch_freshness.py::test_lazy_inputs_skipped_when_patch_current` — passes alone, 106/106
  `-n0`; a load flake under `-n auto`, see the closing re-run); Qt 311 passed; the four named suites 204 passed;
  `tools/ratchets.py` PASS (size WARN lines are both parents' own).

## 2. Sweep `sw11_<ICAO>` vs main's `sw10_<ICAO>`

Instruments: `tools/harness/build_airport.py ICAO --tag sw11_ICAO` (padsweep tree); `tools/harness/census.py`
(arm by the padsweep tree, base by a main worktree `pass2main` @ 6dfb97854); `tools/airside_value_delta.py
--tol 0.02`; `tools/pad_edge_read.py --capture frames/pads67/ICAO.pkl --source` (arm: the sidecar's `pad_touch`;
base: the capture re-classified under this tree); `tools/v2_solve_replay.py --replay frames/pads67/ICAO.pkl
--from classify [--gap-free] --null-change`. Scratch reader `<scratch>/padsweep/row.py` (reads those tools'
JSON; prices nothing). Raw rows follow per airport.

### NLWF

```
=== NLWF: body f769493a0662 -> bd60526fb563; status optimal; patch wall 6.8 -> 6.2 s; rebake plan sha 6084575669d1 -> 6084575669d1
  wall by stage (base -> arm): 
  MOVERS row-side: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  MOVERS solve-owned: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  PAD EDGES (runs / m) base -> arm: BARE 2/40 -> 2/40; cls:M 2/15 -> 2/15; cls:S 1/11 -> 1/11
  PLATFORMS 1 -> 1; hold verdicts {'held': 1} -> {'held': 1}; datums moved > 0.02 m: 0; 10 largest []
    held pads 1: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 0 -> arm []
  HARD_CONFLICT by tier: {'groundside': 8} -> {'groundside': 8}
  CENSUS law-true total 79 -> 78; ADJUDICATED airside-for-acceptance 3 -> 2; by side {'airside': 3, 'groundside': 52, 'mixed': 0, 'unknown': 0} -> {'airside': 2, 'groundside': 52, 'mixed': 0, 'unknown': 0}
    platform_rim_relief          air/mixed/gs 1/0/0 -> 0/0/0  (air+mixed -1, gs +0)
  CRITICAL_MOTION: 0 -> 0; without hairline_pair 0 -> 0; hairline_pair 0 -> 0 (+0); families changed {}
  CRITICAL_VISUAL: 23 -> 23; without hairline_pair 2 -> 2; hairline_pair 21 -> 21 (+0); families changed {}
  QP exits base: total {'optimal': 8}; design {'optimal': 3}; design/stages/stage1 {'optimal': 1}; design/stages/stage2 {'optimal': 3}; design/stages/stage1a {'optimal': 1}
  QP exits arm: total {'optimal': 8}; design {'optimal': 3}; design/stages/stage1 {'optimal': 1}; design/stages/stage2 {'optimal': 3}; design/stages/stage1a {'optimal': 1}
   [NLWF] NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.000 stage2 0/0/0.000 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 0=0, lp relaxed 8=8)
[NLWF] NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.000 stage2 0/0/0.000 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 0=0, lp relaxed 8=8)
```

### CYXY

```
=== CYXY: body c8933945d187 -> 5280c1eefe96; status optimal; patch wall 26.4 -> 25.8 s; rebake plan sha None -> None
  wall by stage (base -> arm): 
  MOVERS row-side: 314 > 0.02 m, worst 0.2; A-only 4 B-only 6; {'strip': (80, 0.2), 'taxi': (45, 0.18), 'apron': (123, 0.18), 'other': (66, 0.11)}
  MOVERS solve-owned: 209 > 0.02 m, worst 0.2; A-only 3 B-only 0; {'strip': (42, 0.2), 'taxi': (45, 0.18), 'apron': (122, 0.18)}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  by-ref building: 6 ref(s), 99 nodes, worst 0.11; only in A 0, only in B 0
  by-ref service_road: 10 ref(s), 63 nodes, worst 0.09; only in A 0, only in B 2
  by-ref groundside_pavement: 2 ref(s), 13 nodes, worst 0.1; only in A 0, only in B 0
  PAD EDGES (runs / m) base -> arm: BARE 4/74 -> 4/74; HELD 2/157 -> 2/157; cls:M 5/9 -> 5/9
  PLATFORMS 9 -> 9; hold verdicts {'held': 9} -> {'held': 9}; datums moved > 0.02 m: 5; 10 largest [('building10', 703.2, 703.1), ('building14', 695.93, 695.87), ('building13', 694.95, 694.89), ('building1', 705.02, 704.96), ('building12', 695.32, 695.27)]
    held pads 9: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 0 -> arm []
  HARD_CONFLICT by tier: {'groundside': 5} -> {'groundside': 4}
  CENSUS law-true total 1313 -> 1304; ADJUDICATED airside-for-acceptance 259 -> 250; by side {'airside': 259, 'groundside': 88, 'mixed': 0, 'unknown': 0} -> {'airside': 250, 'groundside': 92, 'mixed': 0, 'unknown': 0}
    airside_no_step              air/mixed/gs 14/0/0 -> 15/0/0  (air+mixed +1, gs +0)  RISES AIRSIDE
    hard_conflict                air/mixed/gs 0/0/5 -> 0/0/4  (air+mixed +0, gs -1)
    pad_airside_renode           air/mixed/gs 3/0/0 -> 2/0/0  (air+mixed -1, gs +0)
    platform_rim_relief          air/mixed/gs 9/0/0 -> 0/0/0  (air+mixed -9, gs +0)
    within_shape                 air/mixed/gs 211/0/38 -> 211/0/43  (air+mixed +0, gs +5)
  CRITICAL_MOTION: 0 -> 0; without hairline_pair 0 -> 0; hairline_pair 0 -> 0 (+0); families changed {}
  CRITICAL_VISUAL: 52 -> 54; without hairline_pair 0 -> 0; hairline_pair 52 -> 54 (+2); families changed {'hairline_pair': (52, 54)}
  QP exits base: total {'no_descent': 5, 'optimal': 5}; design {'no_descent': 2, 'optimal': 2}; design/stages/stage1 {'no_descent': 1}; design/stages/stage2 {'no_descent': 2, 'optimal': 2}; design/stages/stage1a {'optimal': 1}
  QP exits arm: total {'optimal': 10}; design {'optimal': 4}; design/stages/stage1 {'optimal': 1}; design/stages/stage2 {'optimal': 4}; design/stages/stage1a {'optimal': 1}
   [CYXY] NULL-CHANGE pass1a 0/0/0.003 pass1b 7/0/0.078 stage2 10/0/0.078 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 0=0, lp relaxed 4=4)
[CYXY] NULL-CHANGE pass1a 0/0/0.003 pass1b 7/0/0.078 stage2 10/0/0.078 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 0=0, lp relaxed 4=4)
```

### KASE

```
=== KASE: body be2708bae87e -> 2330243b34e3; status optimal; patch wall 37.2 -> 34.9 s; rebake plan sha 4fd4c84874d0 -> 4fd4c84874d0
  wall by stage (base -> arm): 
  MOVERS row-side: 216 > 0.02 m, worst 5.59; A-only 18 B-only 22; {'other': (53, 5.59), 'apron': (60, 0.54), 'taxi': (37, 0.51), 'strip': (66, 0.45)}
  MOVERS solve-owned: 115 > 0.02 m, worst 0.54; A-only 0 B-only 22; {'apron': (60, 0.54), 'taxi': (37, 0.51), 'strip': (18, 0.45)}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  by-ref building: 1 ref(s), 34 nodes, worst 0.54; only in A 1, only in B 0
  by-ref service_road: 4 ref(s), 19 nodes, worst 0.85; only in A 0, only in B 0
  PAD EDGES (runs / m) base -> arm: BARE 5/84 -> 4/368; cls:M 1/0 -> 2/0
  PLATFORMS 2 -> 2; hold verdicts {'held': 1, None: 1} -> {'held': 2}; datums moved > 0.02 m: 0; 10 largest []
    held pads 2: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 0 -> arm []
  HARD_CONFLICT by tier: {'pad': 63} -> {'groundside': 1}
  CENSUS law-true total 4907 -> 4762; ADJUDICATED airside-for-acceptance 2646 -> 2518; by side {'airside': 2620, 'groundside': 37, 'mixed': 26, 'unknown': 0} -> {'airside': 2495, 'groundside': 40, 'mixed': 23, 'unknown': 0}
    airside_no_step              air/mixed/gs 1281/25/0 -> 1247/23/0  (air+mixed -36, gs +0)
    hard_conflict                air/mixed/gs 63/0/0 -> 0/0/1  (air+mixed -63, gs +1)
    pad_airside_weld             air/mixed/gs 1/0/0 -> 0/0/0  (air+mixed -1, gs +0)
    platform_refused             air/mixed/gs 1/0/0 -> 0/0/0  (air+mixed -1, gs +0)
    platform_rim_relief          air/mixed/gs 2/0/0 -> 0/0/0  (air+mixed -2, gs +0)
    road_cross_section           air/mixed/gs 0/0/13 -> 0/0/15  (air+mixed +0, gs +2)
    strip_transverse             air/mixed/gs 59/1/0 -> 58/0/0  (air+mixed -2, gs +0)
    taxi_box                     air/mixed/gs 649/0/0 -> 633/0/0  (air+mixed -16, gs +0)
    within_shape                 air/mixed/gs 489/0/24 -> 482/0/24  (air+mixed -7, gs +0)
  CRITICAL_MOTION: 1 -> 1; without hairline_pair 1 -> 1; hairline_pair 0 -> 0 (+0); families changed {}
  CRITICAL_VISUAL: 45 -> 44; without hairline_pair 1 -> 1; hairline_pair 44 -> 43 (-1); families changed {'hairline_pair': (44, 43)}
  QP exits base: total {'no_descent': 12, 'optimal': 4}; design {'no_descent': 4, 'optimal': 1}; design/stages/stage1 {'no_descent': 2, 'optimal': 1}; design/stages/stage2 {'no_descent': 4, 'optimal': 1}; design/stages/stage1a {'no_descent': 2, 'optimal': 1}
  QP exits arm: total {'no_descent': 4, 'optimal': 8}; design {'no_descent': 2, 'optimal': 1}; design/stages/stage1 {'optimal': 3}; design/stages/stage2 {'no_descent': 2, 'optimal': 1}; design/stages/stage1a {'optimal': 3}
   [KASE] NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.000 stage2 0/0/0.000 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 63=63, lp relaxed 1=1)
[KASE] NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.000 stage2 0/0/0.000 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 63=63, lp relaxed 1=1)
```

### SPJC

```
=== SPJC: body 3896972bf638 -> ef27cacddf54; status optimal; patch wall 81.2 -> 76.0 s; rebake plan sha 6fd340d15af6 -> 6fd340d15af6
  wall by stage (base -> arm): total 81->76
  MOVERS row-side: 593 > 0.02 m, worst 4.63; A-only 137 B-only 24; {'other': (371, 4.63), 'apron': (153, 0.65), 'strip': (33, 0.25), 'taxi': (36, 0.07)}
  MOVERS solve-owned: 207 > 0.02 m, worst 0.65; A-only 5 B-only 21; {'apron': (153, 0.65), 'strip': (18, 0.14), 'taxi': (36, 0.07)}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  by-ref building: 20 ref(s), 344 nodes, worst 2.1; only in A 4, only in B 0
  by-ref service_road: 16 ref(s), 59 nodes, worst 0.87; only in A 0, only in B 0
  by-ref groundside_pavement: 6 ref(s), 18 nodes, worst 1.03; only in A 0, only in B 3
  PAD EDGES (runs / m) base -> arm: AIRSIDE 2/0 -> 0/0; BARE 31/2132 -> 34/3560; ENGINE 1/32 -> 1/32; GAPPED 2/0 -> 3/0; HELD 1/0 -> 2/0; cls:M 25/856 -> 27/905; cls:S 1/0 -> 1/0
  PLATFORMS 24 -> 24; hold verdicts {'held': 16, None: 8} -> {'held': 18, None: 6}; datums moved > 0.02 m: 6; 10 largest [('building6', 35.3, 35.77), ('building4', 36.37, 35.94), ('building13', 29.41, 29.51), ('building10', 30.6, 30.52), ('building35', 21.55, 21.53), ('building45', 19.81, 19.79)]
    held pads 18: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 0 -> arm []
  HARD_CONFLICT by tier: {'groundside': 2, 'pad': 1, 'taxi': 7} -> {'groundside': 8, 'pad': 1}
  CENSUS law-true total 3598 -> 3443; ADJUDICATED airside-for-acceptance 901 -> 715; by side {'airside': 901, 'groundside': 282, 'mixed': 0, 'unknown': 0} -> {'airside': 715, 'groundside': 301, 'mixed': 0, 'unknown': 0}
    airside_no_step              air/mixed/gs 176/0/0 -> 172/0/0  (air+mixed -4, gs +0)
    hard_conflict                air/mixed/gs 8/0/2 -> 1/0/8  (air+mixed -7, gs +6)
    mid_edge_step                air/mixed/gs 1/0/14 -> 0/0/14  (air+mixed -1, gs +0)
    pad_airside_weld             air/mixed/gs 4/0/0 -> 5/0/0  (air+mixed +1, gs +0)  RISES AIRSIDE
    pavement_over_road_cap       air/mixed/gs 0/0/5 -> 0/0/4  (air+mixed +0, gs -1)
    platform_refused             air/mixed/gs 8/0/0 -> 6/0/0  (air+mixed -2, gs +0)
    platform_rim_relief          air/mixed/gs 24/0/0 -> 0/0/0  (air+mixed -24, gs +0)
    road_cross_section           air/mixed/gs 0/0/51 -> 0/0/49  (air+mixed +0, gs -2)
    transverse                   air/mixed/gs 8/0/10 -> 8/0/8  (air+mixed +0, gs -2)
    within_shape                 air/mixed/gs 460/0/196 -> 311/0/214  (air+mixed -149, gs +18)
  CRITICAL_MOTION: 0 -> 0; without hairline_pair 0 -> 0; hairline_pair 0 -> 0 (+0); families changed {}
  CRITICAL_VISUAL: 507 -> 523; without hairline_pair 41 -> 41; hairline_pair 466 -> 482 (+16); families changed {'hairline_pair': (466, 482)}
  QP exits base: total {'optimal': 11}; design {'optimal': 4}; design/stages/stage1 {'optimal': 2}; design/stages/stage2 {'optimal': 4}; design/stages/stage1a {'optimal': 1}
  QP exits arm: total {'optimal': 11}; design {'optimal': 4}; design/stages/stage1 {'optimal': 2}; design/stages/stage2 {'optimal': 4}; design/stages/stage1a {'optimal': 1}
   [SPJC] NULL-CHANGE pass1a 1/0/0.020 pass1b 0/0/0.006 stage2 0/0/0.006 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 58=58, lp relaxed 9=9)
[SPJC] NULL-CHANGE pass1a 1/0/0.020 pass1b 0/0/0.006 stage2 0/0/0.006 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 58=58, lp relaxed 9=9)
```

Reads of the four small airports:

- NLWF: 0 movers; `platform_rim_relief` 1 -> 0 (the family went with the collar). Null-change 0/0/0.
- CYXY: runway 0; airside movers <= 0.20 m (strip 80, taxi 45, apron 123), pads 66 nodes <= 0.11 m; structure 0.
  One NEW adjudicated airside row: `airside_no_step` `junction|secondary_parallel` 0.11 m at
  60.70535517, -135.07512583 (14 -> 15); `platform_rim_relief` 9 -> 0; net airside 259 -> 250.
  QP exits: base 5 `no_descent` -> arm 0 (all optimal). Null-change 0 / 7 / 10 movers, 0 over 0.3 m: MET.
- KASE: runway 0; apron 60 <= 0.54, taxi 37 <= 0.51, strip 66 <= 0.45; the pad that main REFUSED
  (`platform_refused` 1 -> 0, hold verdict None -> held) is now one level: its nodes move up to 5.59 m
  (39.22203059, -106.87134373). `hard_conflict` pad 63 -> 0, groundside 0 -> 1. Adjudicated airside
  2,646 -> 2,518, no family rises airside. Null-change 0/0/0.
- SPJC: runway 0; apron 153 <= 0.65; pads 371 nodes <= 4.63 m (two more pads held: `platform_refused` 8 -> 6,
  held 16 -> 18); `hard_conflict` taxi 7 -> 0, groundside 2 -> 8 (the lot/road ceiling rows now side
  groundside), pad 1 -> 1. Adjudicated airside 901 -> 715. ONE family rises airside: `pad_airside_weld` 4 -> 5
  (new row 0.88 m at -12.02837652, -77.10581736). `hairline_pair` +16 (CRITICAL visual 507 -> 523, 41 -> 41
  without it). Edge read: AIRSIDE 2 -> 0 runs, BARE 2,132 -> 3,560 m (newly flat pads standing off bare ground).
  Null-change 1 / 0 / 0: MET.
### KCLT

```
=== KCLT: body c5fdf0daa2d3 -> f64f845341cd; status optimal; patch wall 278.2 -> 330.2 s; rebake plan sha 511a51f45b14 -> 511a51f45b14
  wall by stage (base -> arm): constraints 27->23, solve 121->188, total 278->330
  MOVERS row-side: 6344 > 0.02 m, worst 4.12; A-only 289 B-only 189; {'other': (1160, 4.12), 'apron': (2633, 2.65), 'taxi': (732, 1.35), 'strip': (1819, 1.21)}
  MOVERS solve-owned: 3869 > 0.02 m, worst 1.44; A-only 7 B-only 259; {'apron': (2384, 1.44), 'taxi': (732, 1.35), 'strip': (753, 1.0)}
  MOVERS structure: 11 > 0.02 m, worst 1.43; A-only 0 B-only 0; {'structure_rim:tunnel_wall': (8, 1.43), 'structure_rim:tunnel_wall+tunnel_ramp': (2, 1.42), 'tunnel_ramp': (1, 1.42)}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  by-ref building: 57 ref(s), 1226 nodes, worst 2.65; only in A 10, only in B 2
  by-ref service_road: 296 ref(s), 2364 nodes, worst 3.13; only in A 9, only in B 25
  by-ref groundside_pavement: 28 ref(s), 506 nodes, worst 1.71; only in A 2, only in B 0
  PAD EDGES (runs / m) base -> arm: AIRSIDE 7/17 -> 0/0; BARE 84/3425 -> 78/4562; ENGINE 2/0 -> 0/0; GAPPED 3/24 -> 4/24; TOUCH-OFF 8/62 -> 0/0; cls:M 109/1026 -> 117/1290; cls:S 4/18 -> 4/18
  PLATFORMS 55 -> 55; hold verdicts {'held': 44, None: 11} -> {'held': 53, None: 2}; datums moved > 0.02 m: 25; 10 largest [('building75', 221.02, 222.44), ('building83', 221.02, 222.44), ('building42', 216.32, 216.15), ('building43', 216.25, 216.08), ('building49/b1', 218.55, 218.65), ('building49/b0', 218.8, 218.9), ('building51', 218.72, 218.82), ('building52', 217.67, 217.59), ('building53', 217.46, 217.38), ('building54', 217.33, 217.25)]
    held pads 53: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 1 -> arm [('building12', 0.092), ('building26', 0.065), ('building49/b0', 0.678), ('building49/b1', 8.326), ('building68', 1.543)]
  HARD_CONFLICT by tier: {'groundside': 276, 'pad': 5, 'taxi': 50} -> {'groundside': 276, 'pad': 33}
  CENSUS law-true total 17470 -> 17515; ADJUDICATED airside-for-acceptance 3341 -> 2995; by side {'airside': 3318, 'groundside': 2929, 'mixed': 23, 'unknown': 0} -> {'airside': 2973, 'groundside': 3133, 'mixed': 22, 'unknown': 0}
    adjacent_ground_step         air/mixed/gs 18/0/0 -> 16/0/0  (air+mixed -2, gs +0)
    airside_no_step              air/mixed/gs 481/0/0 -> 473/0/0  (air+mixed -8, gs +0)
    frontage_near_miss           air/mixed/gs 10/0/0 -> 7/0/0  (air+mixed -3, gs +0)
    hard_conflict                air/mixed/gs 55/0/276 -> 33/0/276  (air+mixed -22, gs +0)
    mid_edge_step                air/mixed/gs 13/0/17 -> 0/0/14  (air+mixed -13, gs -3)
    pad_airside_renode           air/mixed/gs 47/0/0 -> 53/0/0  (air+mixed +6, gs +0)  RISES AIRSIDE
    pad_airside_weld             air/mixed/gs 5/0/0 -> 7/0/0  (air+mixed +2, gs +0)  RISES AIRSIDE
    pavement_over_road_cap       air/mixed/gs 0/1/15 -> 0/0/9  (air+mixed -1, gs -6)
    plane_gradient               air/mixed/gs 0/0/7 -> 0/0/8  (air+mixed +0, gs +1)
    platform_refused             air/mixed/gs 11/0/0 -> 0/0/0  (air+mixed -11, gs +0)
    platform_rim_relief          air/mixed/gs 53/0/0 -> 0/0/0  (air+mixed -53, gs +0)
    road_cross_section           air/mixed/gs 0/0/771 -> 0/0/818  (air+mixed +0, gs +47)
    strip_arc                    air/mixed/gs 11/0/0 -> 12/0/0  (air+mixed +1, gs +0)  RISES AIRSIDE
    taxi_box                     air/mixed/gs 224/0/0 -> 227/0/0  (air+mixed +3, gs +0)  RISES AIRSIDE
    transverse                   air/mixed/gs 4/0/302 -> 8/0/322  (air+mixed +4, gs +20)  RISES AIRSIDE
    vertex_to_edge_step          air/mixed/gs 0/0/4 -> 0/0/3  (air+mixed +0, gs -1)
    within_shape                 air/mixed/gs 2353/0/1537 -> 2104/0/1683  (air+mixed -249, gs +146)
  CRITICAL_MOTION: 5 -> 4; without hairline_pair 5 -> 4; hairline_pair 0 -> 0 (+0); families changed {'frontage_near_miss': (1, 0)}
  CRITICAL_VISUAL: 1973 -> 2038; without hairline_pair 4 -> 2; hairline_pair 1969 -> 2036 (+67); families changed {'adjacent_ground_step': (2, 1), 'groundside_cutback': (2, 1), 'hairline_pair': (1969, 2036)}
  QP exits base: total {'optimal': 14, 'no_descent': 3}; design {'optimal': 6}; design/stages/stage1 {'no_descent': 3}; design/stages/stage2 {'optimal': 6}; design/stages/stage1a {'optimal': 2}
  QP exits arm: total {'round_cap': 3, 'optimal': 14}; design {'round_cap': 1, 'optimal': 5}; design/stages/stage1 {'round_cap': 1, 'optimal': 2}; design/stages/stage2 {'round_cap': 1, 'optimal': 5}; design/stages/stage1a {'optimal': 2}
[KCLT] NULL-CHANGE pass1a 0/0/0.001 pass1b 0/0/0.000 stage2 0/0/0.000 (movers > 0.02 / > 0.3 / worst m; bar 20 / 0; promoted 161=161, lp relaxed 309=309)
```

### HECA

```
=== HECA: body 5fce51e016a0 -> 645b3b7f49f3; status optimal; patch wall 569.2 -> 677.5 s; rebake plan sha 1956d7537290 -> 75018e8013b8
  wall by stage (base -> arm): partition 52->45, classify 26->23, solve 258->390, late_stage 115->111, total 569->677
  MOVERS row-side: 10445 > 0.02 m, worst 9.48; A-only 375 B-only 294; {'other': (2306, 9.48), 'apron': (2236, 5.19), 'taxi': (2339, 1.16), 'strip': (3453, 0.73), 'runway': (111, 0.13)}
  MOVERS solve-owned: 5893 > 0.02 m, worst 2.19; A-only 0 B-only 8; {'apron': (2136, 2.19), 'taxi': (2339, 1.16), 'strip': (1307, 0.59), 'runway': (111, 0.13)}
  MOVERS structure: 0 > 0.02 m, worst 0.0; A-only 0 B-only 0; {}
  RUNWAY nodes moved > 0.02 m: 111, worst 0.13 @ 30.13223500946, 31.39747096527
    runway way 05C/23C: 1154 joined, worst |dz| 0.03 m, worst shape 0.038 pp / 30 m, sites > 0.1 pp: 0 []
    runway way 05L/23R: 686 joined, worst |dz| 0.13 m, worst shape 0.24 pp / 30 m, sites > 0.1 pp: 10 [(0.24, '30.12694322, 31.39039445'), (0.159, '30.13852330, 31.40588179'), (0.151, '30.13935325, 31.40651482')]
  by-ref building: 87 ref(s), 2003 nodes, worst 9.48; only in A 10, only in B 11
  by-ref service_road: 189 ref(s), 2101 nodes, worst 9.07; only in A 8, only in B 25
  by-ref groundside_pavement: 55 ref(s), 2438 nodes, worst 6.16; only in A 12, only in B 18
  PAD EDGES (runs / m) base -> arm: AIRSIDE 31/556 -> 3/46; BARE 297/14831 -> 326/17058; ENGINE 41/331 -> 22/302; GAPPED 2/66 -> 5/86; HELD 4/165 -> 1/2; TOUCH-OFF 13/446 -> 3/49; cls:M 243/7872 -> 258/10569; cls:S 1/0 -> 1/0
  PLATFORMS 42 -> 47; hold verdicts {'held': 32, None: 8, 'residual': 2} -> {None: 8, 'held': 37, 'residual': 2}; datums moved > 0.02 m: 26; 10 largest [('building98', 103.51, 94.43), ('building68', 92.1, 85.34), ('building117', 101.75, 95.12), ('building93', 82.72, 83.89), ('building105', 82.47, 83.55), ('building84', 85.12, 84.05), ('building83', 85.12, 84.07), ('building174', 74.42, 75.2), ('building178', 73.93, 74.54), ('building186', 71.97, 72.37)]
    held pads 37: datum off its held contact > 0.02 m: 3 [('building165', 0.105), ('building157', 0.075), ('building169', 0.059)]; tilted (tilt_pct > 0.05): base 3 -> arm [('building100', 93.4), ('building169', 0.08), ('building5', 0.212), ('building59', 0.319), ('building101', 0.513), ('building178', 0.603), ('building36', 0.321), ('building93', 0.06)]
  HARD_CONFLICT by tier: {'groundside': 209, 'pad': 24, 'taxi': 63} -> {'groundside': 359, 'pad': 32, 'taxi': 1}
  CENSUS law-true total 56069 -> 56270; ADJUDICATED airside-for-acceptance 12176 -> 11934; by side {'airside': 12167, 'groundside': 2234, 'mixed': 9, 'unknown': 0} -> {'airside': 11925, 'groundside': 2675, 'mixed': 9, 'unknown': 0}
    adjacent_ground_step         air/mixed/gs 5/0/0 -> 8/0/0  (air+mixed +3, gs +0)  RISES AIRSIDE
    airside_no_step              air/mixed/gs 4011/0/0 -> 4037/0/0  (air+mixed +26, gs +0)  RISES AIRSIDE
    frontage_near_miss           air/mixed/gs 16/0/0 -> 15/0/0  (air+mixed -1, gs +0)
    hard_conflict                air/mixed/gs 87/0/209 -> 33/0/359  (air+mixed -54, gs +150)
    mid_edge_step                air/mixed/gs 6/0/46 -> 0/0/55  (air+mixed -6, gs +9)
    pad_airside_renode           air/mixed/gs 21/0/0 -> 20/0/0  (air+mixed -1, gs +0)
    pad_airside_weld             air/mixed/gs 4/0/0 -> 6/0/0  (air+mixed +2, gs +0)  RISES AIRSIDE
    pad_frontage_infeasible      air/mixed/gs 0/0/0 -> 5/0/0  (air+mixed +5, gs +0)  RISES AIRSIDE
    pavement_over_road_cap       air/mixed/gs 0/3/15 -> 0/5/17  (air+mixed +2, gs +2)  RISES AIRSIDE
    plane_gradient               air/mixed/gs 4/0/1 -> 2/0/2  (air+mixed -2, gs +1)
    platform_refused             air/mixed/gs 5/0/0 -> 0/0/0  (air+mixed -5, gs +0)
    platform_rim_relief          air/mixed/gs 42/0/0 -> 0/0/0  (air+mixed -42, gs +0)
    road_coverage_join           air/mixed/gs 0/0/1 -> 0/0/0  (air+mixed +0, gs -1)
    road_cross_section           air/mixed/gs 0/0/518 -> 0/0/555  (air+mixed +0, gs +37)
    strip_seam_tear              air/mixed/gs 23/0/0 -> 37/0/0  (air+mixed +14, gs +0)  RISES AIRSIDE
    strip_transverse             air/mixed/gs 260/0/0 -> 247/0/0  (air+mixed -13, gs +0)
    taxi_box                     air/mixed/gs 2456/0/0 -> 2457/0/0  (air+mixed +1, gs +0)  RISES AIRSIDE
    terrace_actual_step          air/mixed/gs 4/6/29 -> 1/4/15  (air+mixed -5, gs -14)
    transverse                   air/mixed/gs 357/0/604 -> 379/0/618  (air+mixed +22, gs +14)  RISES AIRSIDE
    vertex_to_edge_step          air/mixed/gs 2/0/13 -> 1/0/16  (air+mixed -1, gs +3)
    within_shape                 air/mixed/gs 4853/0/798 -> 4666/0/1038  (air+mixed -187, gs +240)
  CRITICAL_MOTION: 3 -> 3; without hairline_pair 3 -> 3; hairline_pair 0 -> 0 (+0); families changed {'terrace_actual_step': (0, 1), 'vertex_to_edge_step': (1, 0)}
  CRITICAL_VISUAL: 1913 -> 2032; without hairline_pair 60 -> 88; hairline_pair 1853 -> 1944 (+91); families changed {'adjacent_ground_step': (4, 6), 'hairline_pair': (1853, 1944), 'mid_edge_step': (26, 35), 'strip_seam_tear': (23, 37), 'vertex_to_edge_step': (5, 8)}
  QP exits base: total {'no_descent': 4, 'optimal': 11}; design {'no_descent': 1, 'optimal': 2}; design/stages/base/stage1 {'no_descent': 2, 'optimal': 1}; design/stages/base/stage2 {'optimal': 6}; design/stages/base/stage1a {'no_descent': 1, 'optimal': 2}
  QP exits arm: total {'optimal': 15}; design {'optimal': 3}; design/stages/base/stage1 {'optimal': 3}; design/stages/base/stage2 {'optimal': 6}; design/stages/base/stage1a {'optimal': 3}
```

### OTHH

```
=== OTHH: body 21b0f9bf523a -> eb7565539e36; status optimal; patch wall 537.3 -> 546.1 s; rebake plan sha 8e24e55b3f68 -> 8e24e55b3f68
  wall by stage (base -> arm): solve 82->90, total 537->546
  MOVERS row-side: 86 > 0.02 m, worst 0.19; A-only 805 B-only 200; {'apron': (45, 0.19), 'other': (41, 0.19)}
  MOVERS solve-owned: 0 > 0.02 m, worst 0.0; A-only 5 B-only 27; {}
  MOVERS structure: 1 > 0.02 m, worst 0.04; A-only 1 B-only 1; {'structure_rim:tunnel_wall': (1, 0.04)}
  RUNWAY nodes moved > 0.02 m: 0, worst 0
  by-ref building: 3 ref(s), 83 nodes, worst 0.19; only in A 12, only in B 0
  by-ref groundside_pavement: 13 ref(s), 68 nodes, worst 0.28; only in A 0, only in B 1
  PAD EDGES (runs / m) base -> arm: BARE 28/212 -> 29/208; cls:M 54/589 -> 49/562; cls:W 33/385 -> 33/385
  PLATFORMS 16 -> 16; hold verdicts {'held': 14, None: 2} -> {None: 1, 'held': 15}; datums moved > 0.02 m: 0; 10 largest []
    held pads 15: datum off its held contact > 0.02 m: 0 []; tilted (tilt_pct > 0.05): base 0 -> arm []
  HARD_CONFLICT by tier: {} -> {}
  CENSUS law-true total 2562 -> 2241; ADJUDICATED airside-for-acceptance 493 -> 168; by side {'airside': 458, 'groundside': 3, 'mixed': 35, 'unknown': 0} -> {'airside': 133, 'groundside': 3, 'mixed': 35, 'unknown': 0}
    pad_airside_renode           air/mixed/gs 52/0/0 -> 54/0/0  (air+mixed +2, gs +0)  RISES AIRSIDE
    platform_refused             air/mixed/gs 2/0/0 -> 0/0/0  (air+mixed -2, gs +0)
    platform_rim_relief          air/mixed/gs 16/0/0 -> 0/0/0  (air+mixed -16, gs +0)
    within_shape                 air/mixed/gs 374/0/0 -> 65/0/0  (air+mixed -309, gs +0)
  CRITICAL_MOTION: 0 -> 0; without hairline_pair 0 -> 0; hairline_pair 0 -> 0 (+0); families changed {}
  CRITICAL_VISUAL: 2062 -> 2054; without hairline_pair 22 -> 10; hairline_pair 2040 -> 2044 (+4); families changed {'hairline_pair': (2040, 2044), 'within_shape': (12, 0)}
  QP exits base: total {'optimal': 10}; design {'optimal': 3}; design/stages/base/stage1 {'optimal': 1}; design/stages/base/stage2 {'optimal': 5}; design/stages/base/stage1a {'optimal': 1}
  QP exits arm: total {'no_descent': 1, 'optimal': 9}; design {'no_descent': 1, 'optimal': 2}; design/stages/base/stage1 {'optimal': 1}; design/stages/base/stage2 {'optimal': 5}; design/stages/base/stage1a {'optimal': 1}
```

Reads of the three large airports (walls are single runs; KCLT's and HECA's ran beside this lane's own census /
replay reads and are NOT evidence; OTHH ran alone but for the first ~30 s — 546.1 s, bar 660 s MET):

- KCLT: runway 0. Airside: apron 2,384 <= 1.44, taxi 732 <= 1.35, strip 753 <= 1.00 (solve-owned). STRUCTURE 11
  nodes 1.41-1.43 m — one tunnel-wall rim + its ramp at 35.22182657, -80.94183645 (8 `structure_rim:tunnel_wall`,
  2 rim+ramp, 1 `tunnel_ramp`) — NOT attributed here. Held 44 -> 53 (`platform_refused` 11 -> 0); the edge read
  AIRSIDE 7 -> 0 runs, TOUCH-OFF 8 / 62 m -> 0, ENGINE 2 -> 0. `hard_conflict` taxi 50 -> 0, pad 5 -> 33
  (16 `platform plane` + 15 `pad_slope_max ceiling` + 2 `frontage_hold`: the LP relaxes a HELD block's flat rows
  against pavement ceilings at `building12`, `building49/b0`, `/b1`, `building46`, `building79`, worst 0.34 m —
  present in BOTH parents' replays (`frames/pass2/KCLT_auto.patch.osm`, weldverify `kv6`), absent on main).
  Adjudicated airside 3,341 -> 2,995; families rising airside: `pad_airside_renode` +6, `pad_airside_weld` +2
  (0.64 m 35.21610606, -80.92907988; 0.63 m 35.21034641, -80.92898245), `strip_arc` +1 (0.39 m 35.22118171,
  -80.93695414), `taxi_box` +3 net (13 new, worst 0.70 m 35.22399174, -80.9375963), `transverse` +4 (6 new at
  that same junction, 0.49-0.70 m). `hairline_pair` +67 (expected +43). QP: `round_cap` x3 (stage 1 x1, stage 2
  x1, + the design record) where main had `no_descent` x3. Null-change 0/0/0: MET.
- HECA: RUNWAY 111 nodes, worst 0.13 m (30.13223501, 31.39747097) all on 05L/23R; shape (largest change of the
  level delta over 25-35 m along the axis) 0.24 pp at 30.12694322, 31.39039445, 10 node pairs over 0.1 pp
  (next 0.159 at 30.13852330, 31.40588179; 0.151 at 30.13935325, 31.40651482); 05C/23C <= 0.03 m, 0.04 pp.
  Inside 10a (1)'s 0.5 m; the 0.24 pp site is for the master's eye. Structure 0. Held 32 -> 37, datums moved 26
  (sheet `objpav402`: building98 103.51 -> 94.43, building117 101.75 -> 95.12; building68 92.10 -> 85.34).
  Edge read: AIRSIDE 31 / 556 m -> 3 / 46 m, TOUCH-OFF 13 / 446 -> 3 / 49, ENGINE 41 / 331 -> 22 / 302,
  HELD 4 / 165 -> 1 / 2, GAPPED 2 / 66 -> 5 / 86, BARE 14,831 -> 17,058 m. `hard_conflict` taxi 63 -> 1,
  pad 24 -> 32, groundside 209 -> 359 (reclassification of the lot / road ceilings + the rim strips).
  Adjudicated airside 12,176 -> 11,934. Rising airside: `strip_seam_tear` 23 -> 37 (ONE seam, section 3 b),
  `adjacent_ground_step` +3 (two on that seam, one 0.83 m at 30.11972181, 31.40925572), `airside_no_step` +26,
  `transverse` +22, `pad_frontage_infeasible` 0 -> 5 (0.281 m at 30.11721238, 31.38159758 = `building36`; the
  other four are pass2's, <= 0.105 m), `pad_airside_weld` +2 (0.66 m 30.12857809, 31.41290302; 0.32 m
  30.12161392, 31.41883864), `pavement_over_road_cap` mixed +2 (1.16 m 30.12787413, 31.40451801; 0.92 m
  30.12086521, 31.41818487), `taxi_box` +1. CRITICAL motion 3 -> 3 (`terrace_actual_step` +1 = the #507 wall,
  `vertex_to_edge_step` -1); CRITICAL visual 1,913 -> 2,032: `hairline_pair` +91 (expected +30), without it
  60 -> 88 = `strip_seam_tear` +14, `mid_edge_step` +9, `vertex_to_edge_step` +3, `adjacent_ground_step` +2.
  QP exits: every solve `optimal` (main: 4 `no_descent`). Rebake plan sha CHANGED (1956d753 -> 75018e80).
- OTHH: solve-owned airside movers 0; runway 0; pads 83 nodes <= 0.19 m (3 refs), apron 45 <= 0.19.
  STRUCTURE: ONE node, 0.04 m, `structure_rim:tunnel_wall` at 25.26473780, 51.61171830, and one `basin_wall` rim
  node re-sited (A-only 25.26436318, 51.61131128 / B-only 25.26501762, 51.61258695) — the bar is 0; not
  attributed. REBAKE PLAN SHA IDENTICAL to main (8e24e55b3f68: the 15 authored seats and object frames unchanged).
  `hard_conflict` 0 -> 0. Adjudicated airside 493 -> 168 (`within_shape` 374 -> 65, `platform_rim_relief` 16 -> 0);
  one family rises: `pad_airside_renode` 52 -> 54. `hairline_pair` +4 (expected +122: NOT seen). Edge read W 33 /
  385 m unchanged. v2-verify 444 rows, no defects. QP: one `no_descent` in the design record (main: 0).

### HECA site reads (sw10 -> sw11; `<scratch>/padsweep/sites.py`, the graded surfaces + the value delta's join)

- #430 30.1154841, 31.4105884: 0 joined nodes moved within 30 m; `gap:7/lot` 97.19..97.40 -> 96.32..96.53,
  `gap:8/s0/lot` 97.40..97.80 -> 96.53..96.93, `route3` 97.24..97.37 -> 96.37..96.50 (the late stage re-cut the
  pieces: the nodes are new, the levels fell 0.87 m together).
- #292 30.1159784, 31.4106264: `gap:7/lot` 97.37..99.50 -> 97.43..98.90, `gap:7/ramp0` 95.58..99.50 -> 95.24..98.90.
- #358 30.1193169, 31.4085087: 12 nodes moved, worst 0.40 m — apron `objpav68#0` 89.44..89.62 -> 89.05..89.23,
  `pav37` -0.38, `building26` 90.56 -> 90.20, `gap:0/s4/lot` 89.33..90.92 -> 88.95..90.59 (all down ~0.37 together).
- T3 `building4`: datum 101.788 -> 101.789, held 486 contacts. Main's rim read 93.09..101.79 over its runs; the
  merged head's rim is 101.79 on every run of the pad proper, and six `building4/landing<k>` pads carry the low
  levels (92.72..101.79). Beside it: the gap pieces meet the rim within 0.01-0.02 m (M runs); bare ground stands
  up to 8.9 m under it (B runs, 678 m the longest); P runs left: ENGINE 2.34 m at 30.11404019, 31.39909783
  (`gap:0/s0/lot`), `landing2` ENGINE 3.8 m at 30.11345819, 31.39782685, `landing1` ENGINE 2.52 m at
  30.11316054, 31.39810187, `landing4` HELD 1.14 m at 30.11167576, 31.39215158.
- `building12` 30.11524973, 31.40942194 (no platform record — landside only): main rim 95.61..96.14 with
  TOUCH-OFF runs (`pav57` 3.30 m off over 124 m, `route3` 1.9 m off over 72 m); merged rim 93.60..94.74 — the pad
  MOVED down 1.4 m (10a (2)) — `route3` / `route3#2` and `pav57` now TOUCH at 0.00-0.06 m; `pad_touch`: touching
  `pav57`, `pav57#1`, `route3#2`. The pad is not one level (1.1 m across its rim).
- #495 30.10900813, 31.40395756: `route21` apron 104.89..104.99 unchanged; `objpav112#2` junction 104.34 -> 104.41;
  the step now 0.48 m (was 0.55).
- #507 30.12155524, 31.41995156: `objpav1` 98.52..98.62 -> 98.69..98.79 | `objpav402` 95.40 -> 95.17: the wall step
  3.22 -> 3.62 m (census `terrace_actual_step` apron|apron 3.62 m, CRITICAL motion +1).
- `building36` | `dsf:objpav366` 30.11685, 31.38175: `building36` held 63.319 -> RESIDUAL 63.544 (13 of 13
  contacts released, tilt 0.32, rim 63.26..63.54); `objpav366#2` (the rim strip) welds at 0.00;
  `small_roads:-3884` stands 0.70 m off the rim (main 0.72). `mid_edge_step` service_road rows here: 0.67 m x4
  new; `pad_frontage_infeasible` 0.281 m at 30.11721238, 31.38159758.
