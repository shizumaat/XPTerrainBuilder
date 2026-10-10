# RESUME HERE (lane holering stopped by the coordinator 2026-10-09 15:48, machine shutdown; nothing red, NO engine code changed)

ESTABLISHED BY INTERVENTION (pass-1a instrument, HECA, R-E tree f3596b84 + main):
* The pass-1a instability under R-E is NOT the apron hole rings (828 rim columns: 0 movers) — it is the HELD PADS'
  FRONTAGE DATUM COLUMNS (`model.platform.datum_vertices`, 38 single-vertex building-only columns in stage 1 by design,
  flat-pad spec §1 (2)): in pass 1a the hold rows are stripped and 16 of them carry nothing but the hard 5 %
  `pavement_max_grade ceiling` twins — a §61 (0) valley; building88's datum moves −0.914 m under 30 satisfied ceilings.
  base 13/1/0.914 (= the full replay's pass 1), noRE 5/0/0.152, pinrim (datum+rim columns pinned at own values) 0/0/0.006.
* Candidates, pass 1a: C1 `datum_weld` (datum column → membrane rows to its weld contacts at free_membrane 1.0): 0/0/0.005;
  C2 `foreign1a` (datum column foreign in a set with no hold row naming it = pass 1a): 0/0/0.0001. C2 preferred (pass 1a
  = unpulled airside; a pad pulls nothing by construction). NOT YET run on the full replay (killed at shutdown).
* The runway 0.14 m (m → e) is NOT instability: e's final runway = its pass-1a runway (0.008 m; β_R 0, all 2,604 bands
  unpulled, m likewise); pass 1a is null-stable at the runway (0.0001) in every arm. It is the difference between the
  two trees' pass-1a OPTIMA (R-E's problem has +14,131 diffs over m, more than the 5,695 cross-ring pairs). A stability
  fix will not move it → likely an OWNER QUESTION (accept R-E's 0.14 m at HECA over 09b's 0.1 m, or hold R-E).

NEXT COMMAND (one heavy thing at a time; weld63 shares the machine):
  cd /Users/noah/XPTerrainBuilder/.claude/worktrees/holering/Ortho4XP
  S=<scratch>/holering  # instruments also in docs/briefs/holering-scratch/ (prelude.py p1a.py padcols.py rwjoin.py armC1.py armC2.py pairC1.sh)
  $S/pairC1.sh c2 HECA $S/armC2.py      # gap-free base --null-change + late pair + pad_edge_read (~20 min)
  $S/pairC1.sh kc2 KCLT $S/armC2.py     # (~10 min); then ke0 KCLT with tools/v2_solve_replay.py for the R-E-alone KCLT null-change control
  then read c2 vs seat2's e and m (sheetlevel's read_arm.sh / seat2's read.sh + cen.py): null-change line, runway, AIR-TOUCH/NEAR,
  datums, hard_conflict tiers, census by family + CRITICAL. Prelude pickle (711 MB, rebuild with prelude.py HECA OUT.pkl, 4 min)
  was at $S/HECA_prob.pkl (scratch may be gone after shutdown). Captures: frames/pads67/{HECA,KCLT}.pkl (registered).
LANDING FORM OF C2 (drafted, not written): move HOLD_RULING/HOLD_DATUM_RULING to model/platform.py (re-export from
  constraints/platform); in solve/design_stage.stage_split a datum vertex whose column is not airside through a weld and
  that no row with those heads names is FOREIGN (dummy DEM, rows dropped); twin in tests/auto_patch_v2/test_flatpad128v3.py
  (split with cs keeps the datum, split with _strip(cs) drops it); spec amendment §61 (11) + a line under §62 (4) R-E.

# holering notes — the apron HOLE RING in pass 1a (Fable: attribution, design, fix only if the probe holds)

Lane `holering`. Worktree `.claude/worktrees/holering`, branch `claude/holering` off `origin/claude/seat2-re`
f3596b84 (= main 1e524b12 + §61 + R-D rule 1 + §62 R-E) merged with `origin/main` (6e6f4849: RULINGS 09i/09j/09k,
docs only). Scratch `<scratch>/holering/` (`.progress`, `prelude.py`, `p1a.py`, `arms/`).

## Frame

* The defect (sheetlevel d9b0cb1c, by intervention): under R-E at HECA the runway 05L/23R moves 115 nodes, worst
  +0.14 m, 1.7 km from the sheet; `--null-change` reads pass1 13/1/0.914 (building88's vertex at
  30.12101407579,31.41755189267 = v12285 on the full map), pass2 164/0/0.107, pass3 13/0/0.159 (base m: 7/0, 9/0, 9/0).
  Pinning the runway (arm P) leaves pass 1 at 6/1/0.510 and zeroes pass 2 / stage 2.
* Law: 09i (a pad takes the apron's level), 09k (an apron prefers flat; the 1 % preference STANDS over the trend —
  not touched here), 09e/09h (§61: the edge takes its centreline's level; a vertex no chain reaches takes the
  membrane; null-change ≤ 20 at 0.02 m and 0 over 0.3 m), 09b (runway ≤ 0.1 m).
* Frames reused: seat2's late pairs on `frames/pads67/HECA.pkl` / `KCLT.pkl` (`<scratch>/seat2/{m,e,km,ke}`),
  sheetlevel's arms P / N / W (`<scratch>/sheetlevel/`). No new capture.

## Instrument (scratch, never lands)

`prelude.py ICAO OUT.pkl` runs `v2_solve_replay.replay_problem(--from classify --gap-free)` ONCE and pickles
`{pm, cs, law, airport, stage1}`; `p1a.py PROB.pkl ARM` solves PASS 1a alone (the ribbon-free stage-1 problem with
the hold rows stripped, `flex.yield_stage_one` as the build runs it) twice — the arm, then the arm plus the 30 §61 (6)
ceilings (`replay_null.ceilings` on the arm's own pass-1a levels) — and reports movers over the levelled set by vertex
class: apron HOLE RIM (a vertex of a hole ring of an apron face), PAD-ONLY (building faces only), RUNWAY, other.
Arms: `base` (R-E as on the branch), `noRE` (the cross-ring rows dropped = m's pass 1a), `pinrim` (rim + pad-only
columns pinned at the arm's own pass-1a values: the intervention), candidates by name. `--rows V…` prints every
assembled pass-1a row at a vertex. A pass-1a pair is ~3 min at HECA against ~20 min for the full late pair.

## Step 0 — reproduce (pending)

## Step 1 — reproduce and attribute (pass-1a pairs on `HECA_prob.pkl`, R-E tree, `--workers 6`)

| arm | pass-1a NULL (movers > 0.02 / > 0.3 / worst) all | apron hole RIM (828) | PAD-ONLY levelled (38) | RUNWAY (2,604) | other |
|---|---|---|---|---|---|
| `base` (R-E) | **13 / 1 / 0.914** (= the full replay's pass 1: 13/1/0.914) | **0 / 0 / 0.000** | **9 / 1 / 0.914** | 0 / 0 / 0.0001 | 4 / 0 / 0.033 (`gapapron:1`) |
| `noRE` (the 5,695 cross-ring pairs dropped post hoc) | 5 / 0 / 0.152 | 0 / 0 / 0 | 5 / 0 / 0.152 | 0 / 0 / 0.0001 | 0 |
| `pinrim` (rim + pad-only columns pinned at their own pass-1a value) | **0 / 0 / 0.006** | 0 | 0 | 0 / 0 / 0.0 | 0 / 0 / 0.006 |

WHO THE 38 PAD-ONLY COLUMNS ARE (`padcols.py`): exactly the HELD pads' FRONTAGE DATUM COLUMNS (`model.platform.
datum_vertices`: one building-only vertex per held block, the one farthest from its weld — 39 datums, 38 of them
columns on the stage-1 map). They are stage-1 columns BY DESIGN (`design_roles.airside_stage_vertices`, flat-pad spec
§1 (2) / RULINGS 2026-09-30f/r / 02ag (1): "the weld's hard two-way hold ties the apron CONTACTS to it, and the column
itself is pinned at the apron's own frontage level") — and in PASS 1a every hold row is stripped (`HoldPass.strip`), so
the datum column carries: no bending (not on this stage's sheet; a single vertex, no triangle), no trend and no
detached mean (both skip `datum_v` on purpose, §56 R4), no membrane (`_bend_neighbours` finds nothing), and EITHER the
level belt (22 of them: no one-sided row at all → `apply_level_belt` gives the column its own DEM, z = DEM exactly,
stable) OR nothing but the hard 5 % `pavement_max_grade ceiling` twins of its pad's (dropped, one-way) frontage rows —
16 of them (building88: 2 rows to one pavement vertex 29 m away, free inside ±1.45 m; building146, 65, 68, 98, 101, 117,
144, 153, 174, 64, …). THOSE are the valley: §61 (0)'s class — a column with bending-only curvature, here with NO
curvature at all, inside a hard band — on a building-pad datum instead of a taxiway edge. The QP's exit lands it
anywhere in the band: building88's datum moves −0.914 m under 30 satisfied ceilings; under R-E the path differs and
the same column lands elsewhere (m: −0.136 at the same vertex, sheetlevel step 3).

REFUTED (by the table): the apron HOLE RING. Every hole-rim vertex is stable in pass 1a under R-E (828 columns, 0
movers at 0.02 m): the cross-ring rows + the membrane do name them. The brief's three hole-ring candidates
(cross-ring pairs in 1a — they ARE in 1a; an interpolated sheet level across the hole; a tie-break for the
preference rows) have no population. R-E's own rows are not the mechanism either (`noRE` keeps 5 movers on the same
datum columns).

THE RUNWAY. In pass 1a the runway is null-stable in every arm (0.0001 m). Joining each arm's pass-1a surface to the
full replays' FINAL surfaces by vertex key (`rwjoin.py`): `base`-1a vs e-final at the runway 0 / 0 / **0.008** — e's
runway IS its pass-1a runway (`runway_bands_unpulled` 2,604 = all; β_R 0 in m and in e alike: no pad pulls the
runway in either tree). So the 115 nodes / 0.14 m between m and e are the difference between the two trees' PASS-1a
OPTIMA — R-E's problem (e: 916,207 diffs, pass-1a 132,362 rows / 471,900 hard sides; m: 902,076 / 129,663 / 455,028
— more than the 5,695 cross-ring pairs: ~2,700 further rows the new pairs induce) seats the sheet differently and the
one-sided 1 % tier carries that 1.7 km to the junction band and on to 05L/23R. `base` vs `noRE` (the post-hoc filter
alone) moves the pass-1a runway 28 nodes / 0.041 m. Not a stability defect: no stability fix will move it. (Checked
on m: m's final runway also = its pass 1a — β_R 0 — the 0.117 between `noRE`-1a and m-final is `noRE` ≠ m's problem.)

## Step 2 — the candidates, pass 1a (same instrument)

| candidate | rows | pass-1a NULL all / rim / pad-only / runway |
|---|---|---|
| C1 `datum_weld`: the datum column takes one first-difference row to each of its own WELD contacts at `free_membrane` 1.0 (the §61 membrane; its block's frontage as the neighbourhood), after the belt | +186 (22 datums already belted) | **0 / 0 / 0.005**; 0; 0; 0.0001 |
| C2 `foreign1a`: the datum column is an unknown of the airside problem ONLY while a `frontage_hold datum` Band names it — in pass 1a (holds stripped) it is FOREIGN (fixed at its dummy value, every row touching it dropped) | 39 columns out of pass 1a | **0 / 0 / 0.0001**; 0; 0; 0.0001 |

Both close the valley in pass 1a. C2 is the one taken to the full replay first: it is the stated meaning of pass 1a
(`flex.py`: "every frontage-hold row DROPPED: the runway's UNPULLED profile") carried to the column those rows exist
for — the datum column's justification for being airside IS the hold (`airside_stage_vertices`' own comment) — and a
pad then pulls nothing in pass 1a BY CONSTRUCTION (C1's two-way rows at 1.0 pull the welds toward their mean by
~1/300 of the law's weight: mm, but not zero). C1 stays as the fallback. Neither touches the preference / trend balance
(09k), the hole rings, any law weight or any law row.
