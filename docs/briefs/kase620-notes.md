# kase620 — finishing PR #629 (#620; RULINGS 2026-10-12q (1))

Branch `claude/kase620` (from `origin/claude/rwyend620` 820143f01 — that name is held by the old
worktree `.claude/worktrees/rwyend620`; the master re-points the PR). Worktree `.claude/worktrees/kase620`.
Scratch `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/kase620`
(`rp.sh ARM ICAO PKL` = replay from planar + emit + verify + profile; `rows.py PKL V...` = every row on a vertex;
`faces.py PKL END FACE...` = faces / vertices near an end in the runway frame).

## Item 1 — KASE 15: MECHANISM (by intervention, capture `frames/pads67/KASE.pkl`)
Rows on the two centre-line vertices (v1584 break 61.1 m, v1589 outer ring 76.6 m; arm a0 = 820143f01):
* v1584: 2 × resa_transverse (slack 2.0 / 1.4 m), 2 × end-profile CHORD (lo −1.968 hi +0.14, act −0.621), 2 × FAA end-edge rate
  (±1.307, act +0.585).  v1589: 2 × resa_transverse, 1 chord (lo −2.741, act −2.050), 1 rate.  All priced (300), none hard, none binding.
* NO transect PAIR row between them.  `constraints/strips.end_corridor_longitudinal` ran the transect block OUTSIDE its
  `for ring_idx in (1, 2)` loop, so it read the leaked index (2) — transect pairs were minted at the FAR end of every runway only.
  KASE 15 is end 1.  Nothing "outside the strip rows" holds the ground: the row was never stated (which is why every drop arm
  left it unchanged).  INTERVENTION: loop the block over both ends -> −9.23 % becomes −5.94 % (= 5 % + q/15.5 m), dz at band end −2.05 -> −1.56.
* SECOND cause, the 15 census rows: both READERS (`verify/strips.groups`, `check_grade._runway_strip_groups`) fit the runway axis
  to every runway-role ring.  KASE 15 has a 60.2 m x 42 m paved pad beyond the end (face 1, role runway, the runway's ref — a §40
  shoulder; apt.dat row 100 declares no overrun at 15), so the fit ran 60 m long (L 2566.7 vs slab 2500.7), width 152 m
  (end rect half 152 vs 96): every 15-end station read 60 m short (the 61 -> 76.6 m pairs judged at the 3 % near cap), and at
  the 33 end vertices 96-152 m lateral were read as end band.  The generator / break / --profile use the SLAB (§40 (1)/(4)).
  FIX: `runway_axes` sidecar rows gain the two overruns; `verify.strips.published_slabs` / `end_groups` and the harness reader
  frame the end family on the slab.  KASE runway_end_skirt 15 -> 0.
* THIRD, what the breakline made: the break at 61.0 m lands 0.85 m behind the pad's far edge (60.2 m) and no row tied the
  ground to that edge (the transect pairs pair VERTICES on one line; the pad corners stand at t = +/-21) — pad 2340.66,
  break vertex 2340.22: 0.44 m in 0.85 m.  FIX: the TRANSECT FOOT (`end_transect_foot`): an end-band vertex follows the nearest
  crossing inward of its own line with runway-role pavement of the runway's ref beyond the end, by the profile's increment,
  one-way (chord head -> also post-solve clamped).  KASE 15 now: pad 2340.66 -> 2340.50 -> 2339.72 (−5.03 %), band end +0.88 m fill.

## Item 2 — tolerance: ONE key
`emit.instrument.strip_edge_noise_m` (0.15, unchanged) through `law.tables.end_profile_noise_m(law, reader=)`: generator = key −
materiality (floor 0); readers = key (floor `rounding_noise_m`).  0 = the cap exactly.  Tables below.

## Item 4 — NLWF 25 (and what the same reads found elsewhere)
* The 2.8 % pair (v329-v328, 37 m, over by 0.16 m) stands on a mapped service road crossing the end band: the road's
  `road_ramp` equality to the DEM + its own caps hold it.  ROAD CAP GOVERNS (RULINGS 2026-10-02ag (2)): the end family
  (pairs, transects, feet — the chords already did) and `resa_transverse` no longer state or read a row on a
  `road_cap_governs` vertex.  NLWF harness census: runway_end_skirt 3 -> 0, resa_transverse 0, LAW-TRUE 81 -> 78.
  (The replay's own `--verify` does not carry `road_cap_governs` — it is added in `pipeline/build.py` — so it still prints
  those rows; the harness census on the emitted patch is the reading.)
* KBFI (new capture `frames/kase620/KBFI.pkl`): the end rows bound an APRON edge two-way (ring pairs of two apron-edge
  vertices; FAA three-station rate rows over them) — the tolerance arm moved 11 apron vertices <= 0.20 m.  Fixed: a pair of
  two pavement vertices is not stated, a mixed pair is one-way (ground follows), a rate triple with a pavement station is
  not stated; readers the same.  Tolerance arm now moves 0 airside vertices.  Base -> arm still moves 6 apron-edge
  vertices <= 0.07 m: with EVERY end row dropped BY RULING HEAD (166 rows) the same 6 move 0.07 m — the breakline re-nodes the apron's ring
  (8 new vertices on it), no row.

## TOOL TRAP found (not fixed — the master's)
`v2_solve_replay.py --drop-generator end_corridor_longitudinal` (and `end_corridor_rate`, `resa_transverse`, `strip_transverse`)
drops NOTHING: `drop_rows` filters on `row.source.generator`, every strips row carries `"strips"`, and the drop gate
(`replay_arms.drop_gate`) ACCEPTS a registered generator function name that matches no row.  The log still prints
"dropped generators [...]".  This is why lane rwyend620's seven drop arms "left the profile unchanged" (they were all the
same problem), and it voided this lane's first KBFI / HECA interventions.  The arm that works names the RULING HEADS:
`--drop-generator "rulesets.end_skirt runway-end profile pair"` / `... chord` / `rulesets.end_skirt.rate end-edge change` /
`rulesets.end_skirt.rate corridor stations` (scratch `droparm.sh`).

## Measured (matched replays from planar: base = origin/main 89693e99d in worktree kase620base, arm = this branch)
See `table_final.txt` in the scratch dir; the final report carries it.

## Closing builds (harness, this tree)
* KASE `kase620_KASE` 37.7 s body b6d21d6dffda: runway_end_skirt 0, LAW-TRUE 3493; 15 end −0.59 % then −5.03 %.
* SPJC `kase620_SPJC` 83.4 s body c24798c27bf5 (= the rwyend620 build's body): runway_end_skirt 0, LAW-TRUE 3439.
* CYCG REFUSED by the harness: the merged engine is 1.50.1836 and the tile's HRDEM no-coverage negative was recorded by
  1.50.1835 — it wants `--refresh-data dem` (a shared-corpus event; the master's call, not a lane's).  CYCG stands on the
  matched replay pair.

## Final per-end table (matched replays; census = harness census on the emitted patch; q0 = the tolerance key at 0)
Columns: first-segment grade to the break, then the following segments | dz at the break, dz at the band's end @ its distance.

    
    ## KASE  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (7, 1, 3497, 1265) -> arm (0, 4, 3493, 1261) | q0 (0, 4, 3493, 1261)
       movers base->arm: row-side 9/0.65 [runway bar 0): strip 9 (worst 0.650 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 7/0.26 [runway bar 0): strip 7 (worst 0.260 m]; solve-owned 0/0.00; structure 0/0.00
       15/33 end 15: BEFORE -2.34% | dz brk -1.43 end -1.79@76.6  AFTER -0.59% then -5.03 | dz brk -0.36 end -1.14@76.6  [fill(+)/cut(-) brk 1.07 end 0.65]  Q0 -0.36% then -5.03 | dz brk -0.22 end -1.0@76.6
       15/33 end 33: BEFORE -0.16% | dz brk -0.1 end -0.12@75.9  AFTER -0.34% then +0.61 | dz brk -0.21 end -0.12@75.9  [fill(+)/cut(-) brk -0.11 end 0.0]  Q0 -0.34% then +0.61 | dz brk -0.21 end -0.12@75.9
    
    ## CYCG  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (5, 0, 62, 6) -> arm (0, 0, 57, 1) | q0 (0, 0, 57, 1)
       movers base->arm: row-side 8/1.96 [runway bar 0): strip 8 (worst 1.960 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 12/0.14 [runway bar 0): strip 12 (worst 0.140 m]; solve-owned 0/0.00; structure 0/0.00
       15/33 end 15: BEFORE -2.75% | dz brk -1.65 end -2.06@74.9  AFTER -2.01% then -4.87 | dz brk -1.2 end -1.93@74.9  [fill(+)/cut(-) brk 0.45 end 0.13]  Q0 -1.77% then -4.87 | dz brk -1.06 end -1.79@74.9
       15/33 end 33: BEFORE -2.24% | dz brk -1.34 end -1.69@75.4  AFTER -1.73% then -1.97 | dz brk -1.04 end -1.34@75.4  [fill(+)/cut(-) brk 0.3 end 0.35]  Q0 -1.71% then -2.04 | dz brk -1.03 end -1.34@75.4
    
    ## NLWF (owner-approved)  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (3, 0, 81, 5) -> arm (0, 0, 78, 2) | q0 (0, 0, 78, 2)
       movers base->arm: row-side 7/1.64 [runway bar 0): strip 7 (worst 1.640 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 7/0.14 [runway bar 0): strip 7 (worst 0.140 m]; solve-owned 0/0.00; structure 0/0.00
       07/25 end 07: BEFORE +0.42% | dz brk None end 0.17@40.3  AFTER +0.22% | dz brk None end 0.09@40.3  [fill(+)/cut(-) brk None end -0.08]  Q0 -0.12% | dz brk None end -0.05@40.3
       07/25 end 25: BEFORE +4.44% | dz brk None end 1.76@39.6  AFTER +0.30% | dz brk None end 0.12@39.6  [fill(+)/cut(-) brk None end -1.64]  Q0 -0.05% | dz brk None end -0.02@39.6
    
    ## CYXY (owner-approved)  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (20, 0, 1358, 275) -> arm (6, 2, 1370, 301) | q0 (4, 2, 1398, 329)
       movers base->arm: row-side 30/0.95 [runway bar 0): strip 30 (worst 0.950 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 22/0.14 [runway bar 0): strip 22 (worst 0.140 m]; solve-owned 0/0.00; structure 0/0.00
       02/20 end 02: BEFORE +1.52% then +1.54/+1.50/+1.40/.. | dz brk 0.46 end 9.47@624.3  AFTER +1.52% then +1.54/+1.50/+1.40/.. | dz brk 0.46 end 9.47@624.3  [fill(+)/cut(-) brk 0.0 end 0.0]  Q0 +1.52% then +1.54/+1.50/+1.40/.. | dz brk 0.46 end 9.47@624.3
       02/20 end 20: BEFORE no node  AFTER no node  [fill(+)/cut(-) brk None end None]  Q0 no node
       14L/32R end 14L: BEFORE -0.57% | dz brk -0.34 end -0.43@74.8  AFTER -0.72% then +0.00 | dz brk -0.43 end -0.43@74.8  [fill(+)/cut(-) brk -0.09 end 0.0]  Q0 -0.72% then +0.00 | dz brk -0.43 end -0.43@74.8
       14L/32R end 32R: BEFORE -0.80% | dz brk -0.48 end -0.6@74.8  AFTER -1.10% then +0.40 | dz brk -0.66 end -0.6@74.8  [fill(+)/cut(-) brk -0.18 end 0.0]  Q0 -1.10% then +0.40 | dz brk -0.66 end -0.6@74.8
       14R/32L end 14R: BEFORE -0.56% | dz brk -0.34 end -0.42@74.8  AFTER -0.62% then -0.33 | dz brk -0.37 end -0.42@74.8  [fill(+)/cut(-) brk -0.03 end 0.0]  Q0 -0.62% then -0.33 | dz brk -0.37 end -0.42@74.8
       14R/32L end 32L: BEFORE no node  AFTER no node  [fill(+)/cut(-) brk None end None]  Q0 no node
    
    ## KBFI  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (2, 0, 1511, 54) -> arm (0, 0, 1512, 52) | q0 (0, 0, 1513, 52)
       movers base->arm: row-side 24/0.55 [runway bar 0): strip 23 (worst 0.550 m]; solve-owned 6/0.07; structure 0/0.00
       movers arm->q0:   row-side 6/0.15 [runway bar 0): strip 6 (worst 0.150 m]; solve-owned 0/0.00; structure 0/0.00
       14L/32R end 14L: BEFORE -0.64% then +0.02/+2.84/+4.44/.. | dz brk -0.39 end 1.37@1015.7  AFTER -0.75% then -0.20/+0.02/+2.84/.. | dz brk -0.46 end 1.37@1015.7  [fill(+)/cut(-) brk -0.07 end 0.0]  Q0 -0.75% then -0.20/+0.02/+2.84/.. | dz brk -0.46 end 1.37@1015.7
       14L/32R end 32R: BEFORE -0.47% then +0.03/+1.00/+0.77/.. | dz brk -0.29 end 1.2@1462.7  AFTER -0.47% then +0.03/+1.00/+0.77/.. | dz brk -0.29 end 1.2@1462.7  [fill(+)/cut(-) brk 0.0 end 0.0]  Q0 -0.47% then +0.03/+1.00/+0.77/.. | dz brk -0.29 end 1.2@1462.7
       14R/32L end 14R: BEFORE +0.30% then +0.45/+0.17/+0.00/.. | dz brk 0.18 end 0.46@432.8  AFTER +0.41% then +0.55/+0.20/+0.16/.. | dz brk 0.25 end 0.46@432.8  [fill(+)/cut(-) brk 0.07 end 0.0]  Q0 +0.41% then +0.55/+0.20/+0.16/.. | dz brk 0.25 end 0.46@432.8
       14R/32L end 32L: BEFORE -0.21% then +0.14/-0.41/-0.23/.. | dz brk -0.13 end -0.84@262.7  AFTER -0.15% then +0.19/-0.07/-0.41/.. | dz brk -0.09 end -0.84@262.7  [fill(+)/cut(-) brk 0.04 end 0.0]  Q0 -0.13% then +0.02/-0.13/-0.41/.. | dz brk -0.08 end -0.84@262.7
    
    ## SPJC (owner-approved)  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (11, 0, 3422, 727) -> arm (0, 0, 3407, 716) | q0 (0, 0, 3407, 716)
       movers base->arm: row-side 20/1.74 [runway bar 0): strip 20 (worst 1.740 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 22/0.14 [runway bar 0): strip 22 (worst 0.140 m]; solve-owned 0/0.00; structure 0/0.00
       16L/34R end 16L: BEFORE -1.74% | dz brk -1.04 end -1.31@75.3  AFTER -1.73% then -1.59 | dz brk -1.04 end -1.28@75.3  [fill(+)/cut(-) brk 0.0 end 0.03]  Q0 -1.50% then -2.45 | dz brk -0.9 end -1.27@75.3
       16L/34R end 34R: BEFORE -1.39% | dz brk -0.83 end -1.04@74.8  AFTER -1.73% then +0.00 | dz brk -1.04 end -1.04@74.8  [fill(+)/cut(-) brk -0.21 end 0.0]  Q0 -1.50% then -0.87 | dz brk -0.9 end -1.03@74.8
       16R/34L end 16R: BEFORE -3.55% | dz brk -2.13 end -2.67@75.3  AFTER -1.73% then -4.90 | dz brk -1.04 end -1.78@75.3  [fill(+)/cut(-) brk 1.09 end 0.89]  Q0 -1.50% then -4.90 | dz brk -0.9 end -1.64@75.3
       16R/34L end 34L: BEFORE -3.69% | dz brk -2.22 end -2.78@75.3  AFTER -1.73% then -4.97 | dz brk -1.04 end -1.79@75.3  [fill(+)/cut(-) brk 1.18 end 0.99]  Q0 -1.50% then -4.97 | dz brk -0.9 end -1.65@75.3
    
    ## KPDX (owner-approved)  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (6, 0, 3057, 591) -> arm (0, 0, 3049, 584) | q0 (0, 0, 3049, 584)
       movers base->arm: row-side 34/0.35 [runway bar 0): strip 34 (worst 0.350 m]; solve-owned 0/0.00; structure 0/0.00
       movers arm->q0:   row-side 2/0.10 [runway bar 0): strip 2 (worst 0.100 m]; solve-owned 0/0.00; structure 0/0.00
       10L/28R end 10L: BEFORE -0.47% | dz brk -0.29 end -0.36@76.0  AFTER -0.54% then -0.06 | dz brk -0.33 end -0.34@76.0  [fill(+)/cut(-) brk -0.04 end 0.02]  Q0 -0.54% then -0.06 | dz brk -0.33 end -0.34@76.0
       10L/28R end 28R: BEFORE -0.06% then +0.18/-0.59/-0.98/.. | dz brk -0.04 end -0.35@208.1  AFTER -0.32% then -0.75/+3.40/-1.57/.. | dz brk -0.19 end -0.35@208.1  [fill(+)/cut(-) brk -0.15 end 0.0]  Q0 -0.32% then -0.75/+3.40/-1.57/.. | dz brk -0.19 end -0.35@208.1
       10R/28L end 10R: BEFORE -0.50% | dz brk -0.3 end -0.38@76.5  AFTER -0.66% then +0.19 | dz brk -0.4 end -0.37@76.5  [fill(+)/cut(-) brk -0.1 end 0.01]  Q0 -0.66% then +0.19 | dz brk -0.4 end -0.37@76.5
       10R/28L end 28L: BEFORE -0.23% then +0.00/+0.00/-0.80/.. | dz brk -0.14 end -0.4@251.0  AFTER -0.58% then +0.00/+0.00/-2.54/.. | dz brk -0.36 end -0.4@251.0  [fill(+)/cut(-) brk -0.22 end 0.0]  Q0 -0.58% then +0.00/+0.00/-2.54/.. | dz brk -0.36 end -0.4@251.0
       3/21 end 21: BEFORE -1.40% | dz brk -0.86 end -1.41@100.4  AFTER -1.38% | dz brk -0.84 end -1.41@102.5  [fill(+)/cut(-) brk 0.02 end 0.0]  Q0 -1.38% | dz brk -0.84 end -1.41@102.5
       3/21 end 3: BEFORE -1.61% | dz brk -0.98 end -1.23@76.4  AFTER -1.69% then -1.22 | dz brk -1.03 end -1.22@76.4  [fill(+)/cut(-) brk -0.05 end 0.01]  Q0 -1.69% then -1.22 | dz brk -1.03 end -1.22@76.4
    
    ## HECA (owner-approved)  census (end_skirt, resa_transverse, LAW-TRUE, adjudicated airside): base (27, 0, 55796, 11952) -> arm (0, 0, 55775, 11925) | q0 (0, 0, 55775, 11925)
       movers base->arm: row-side 410/2.04 [runway bar 0): strip 34 (worst 2.040 m]; solve-owned 377/0.05; structure 0/0.00
       movers arm->q0:   row-side 20/0.14 [runway bar 0): strip 20 (worst 0.140 m]; solve-owned 0/0.00; structure 0/0.00
       05C/23C end 05C: BEFORE +0.26% then +0.82/-3.25/+1.43/.. | dz brk 0.16 end 8.84@1126.7  AFTER +0.45% then +0.81/-3.25/+1.43/.. | dz brk 0.27 end 8.84@1126.7  [fill(+)/cut(-) brk 0.11 end 0.0]  Q0 +0.67% then +0.80/-3.25/+1.43/.. | dz brk 0.4 end 8.84@1126.7
       05C/23C end 23C: BEFORE -0.68% then -0.21 | dz brk -0.41 end -1.65@652.1  AFTER -0.53% then -0.22 | dz brk -0.32 end -1.65@652.1  [fill(+)/cut(-) brk 0.09 end 0.0]  Q0 -0.32% then -0.25 | dz brk -0.19 end -1.65@652.1
       05L/23R end 05L: BEFORE -1.07% | dz brk -0.64 end -0.77@72.1  AFTER -1.34% then +0.21 | dz brk -0.8 end -0.78@72.1  [fill(+)/cut(-) brk -0.16 end -0.01]  Q0 -1.34% then +0.21 | dz brk -0.8 end -0.78@72.1
       05L/23R end 23R: BEFORE -2.02% then +0.77/+0.00/+0.26/.. | dz brk -1.21 end -4.72@1547.5  AFTER -1.80% then -2.82/+0.76/+0.00/.. | dz brk -1.08 end -4.72@1547.5  [fill(+)/cut(-) brk 0.13 end 0.0]  Q0 -1.60% then -3.56/+0.74/+0.00/.. | dz brk -0.96 end -4.72@1547.5
       05R/23L end 05R: BEFORE +0.74% then +1.38/+8.00/+0.40 | dz brk 0.44 end 12.59@941.5  AFTER +0.95% then +1.36/+8.00/+0.40 | dz brk 0.57 end 12.55@941.5  [fill(+)/cut(-) brk 0.13 end -0.04]  Q0 +1.17% then +1.35/+8.00/+0.40 | dz brk 0.7 end 12.55@941.5
       05R/23L end 23L: BEFORE -1.29% then -0.82/+1.39 | dz brk -0.77 end -7.13@846.9  AFTER -1.12% then -0.83/+1.39 | dz brk -0.67 end -7.13@846.9  [fill(+)/cut(-) brk 0.1 end 0.0]  Q0 -0.90% then -0.85/+1.39 | dz brk -0.54 end -7.13@846.9

Residuals named: CYXY keeps 6 runway_end_skirt rows (4 lip vertices at two ends where the zone-band row and the end chord
both price one vertex and split 0.24-0.26 m; 2 where a taxiway (pav9) stands 0.4 m above a code-1 runway's end inside its
band and its adjacent ground follows the taxiway), +2 resa_transverse at that taxiway, +24 within_shape rows on the
role-less terrain_edge feature way (the census reads that way all-pairs at 1.5 %: 14 rows on it at base) where the
band's rim at the bluff is lifted <= 0.95 m.  KASE +3 resa_transverse (6.4-7.2 % over 48 m): the breakline's own lateral
pairs on the valley side.  HECA 05R: the band's end cut 2.04 m / 1.75 m (rising ground, the climb surface).
HECA base -> arm: 375 apron vertices <= 0.05 m (runway 0, taxi 1 @ 0.03); arm -> q0: 0.  INTERVENTION (every end-profile
row dropped by ruling head, 97 rows, scratch `drop2/HECA`): base -> drop2 reads the SAME 375 apron vertices <= 0.05 m and the
SAME 05R strip movers (−2.04 / −1.75 m); arm -> drop2 moves 0 airside and 16 strip vertices (worst 1.42 m at 23R).  So
neither the apron's 5 cm nor the 05R cut is the new profile's rows: both come with the breakline's re-noded map / the
retirement of main's two-sided 5 % end rows (not separated — one more arm: main's rows on the broken map).

## Suites
Full non-Qt on the final code: 9,651 passed, 19 skipped, 1 xfailed, 1 xpassed (169 s; includes tests/auto_patch_v2).
ratchets: DUPLICATE PASS, LAYER PASS; size WARN check_grade.py 13,793 -> 14,326, publication.py 1,171 -> 1,282 (main's
growth + 9), project.py 1,039, run_checks 1,194 lines.

## RESUME HERE
* Nothing open in code.  Not done: the CYCG harness build (corpus refresh needed, above); no push (local branch
  claude/kase620); the CYXY lip / taxiway-zone conflicts and the terrain_edge census reading are findings for the master.
