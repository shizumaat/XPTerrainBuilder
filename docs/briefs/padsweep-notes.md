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
