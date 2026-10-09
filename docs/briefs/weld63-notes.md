# weld63 notes — implementing spec §63 (a cell touching a pad in the source is welded; a gapped cell is free)

Lane `weld63` (Opus, implementation). Worktree `.claude/worktrees/weld63`, branch `claude/weld63` off
`origin/claude/chainlag` ded211fb + `origin/main` 116152e0 (docs-only). Scratch `<scratch>/weld63/` (`.progress`).
Master rulings carried in the brief: Q-A YES (a §28 (6) held terrace > 2.4 m keeps the knife); Q-B = 09j literal
(a landside pad keeps its own seat, the touching road / lot comes to it within its cap).

## Sub-steps

| step | commit | state | what |
|---|---|---|---|
| S | (this) | landed | `constraints/pads._airside_only` drops every groundside role: a pad fronts airside or nothing (its §9b datum). Twin `test_v2frontage::test_a_pad_between_a_road_and_a_lot_keeps_its_datum_and_takes_no_level_row` (red before, green after); 80 pad tests green. `pad_seat.py` / R-C / the solver change were never on this tree. |
| T | 23ad159e | landed | the witness `classify/pad_touch.py` (new module: `touch_distances`, `is_touching`, `touch_records`), read in `classify/roles._cut_back_groundside` BEFORE the knife on identity-gridded rings against every pad within `pad_frontage_m`; `Cell.evidence['pad_touch'] = {pad ref: d}`; sidecar evidence key `pad_touch` (`pipeline/publication.pad_touch`, registered in `emit/osm_adapter` + `check_grade.SIDECAR_EVIDENCE_KEYS`); `tools/pad_edge_read.py --source SIDECAR|CAP.pkl` (classes TOUCH-OFF / HELD / GAPPED / AIRSIDE / ENGINE / UNWITNESSED; INDEX row; 5 twins) ; twin `tests/auto_patch_v2/test_pad_touch.py` (overlap, 0.3 m, 0.8 m, 2 m, beyond the radius, the sidecar record). No surface change. |
| W | 70947240 | landed (acceptance arms `w1` / `kw1` running) | `classify/roles._cut_back_groundside(cells, law, rules, airport)`: per (cell, pad) pair — TOUCHING → clipped at the pad's gridded footprint (no stand-off) + `planar/weld` partner class (`classify.pad_touch.weld_partners`, the pad frozen); TOUCHING across a hillside (`pad_touch.dem_step_m` > `frontage_step_max_m`, Q-A) → HELD, the knife as before; GAPPED → as drawn. `pads.pad_shared` airside-only (shared groundside vertices are pad columns); `pad_frontage_gs.groundside_frontage` mints no row for a face sharing the pad's rim. Twins: `test_pad_touch` (7 W twins), `test_m3b` / `test_round3` rewritten from the set-back to the weld. |
| B′ | 3aa7684b | landed (acceptance arms `x1` / `kx1` queued) | `constraints/road_ramp.pad_weld_release` (last in `reach_seed_rewrite`): the §37 (6) target + ceiling and the §37 (9) join pin of a vertex in `pads.pad_welded_vertices` withdrawn; a withdrawn join recorded stage `2f`. Twin in `test_pad_touch`. |
| P | 44f9955b | landed | sidecar `pad_touch` entries `{cell, faces[, gap_m]}`; `pad_edge_read --source` classes per FACE. Twins: `test_pad_touch` (records name the faces), `test_pad_edge_read` (a run classed by its face). |
| L | — | NOT DONE (nothing to re-home) | the landing exclusion by registry name lived in the unlanded `pad_seat.py`; on this tree the solve's §9b already reads the hard register (`solve/design_assemble`: `hard_follow` anchors the sheet, `datum_v`), and `pads.pad_datum_withdrawn` (the one `landing_vertices` reader in `pads`) has no engine consumer. A `pad_has_fixed_level` with no caller would be dead code. |

## T — the seven-airport touch census (`<scratch>/weld63/census/census.py`; classify of the pads67 captures under T, the edge read of main's sweep products `/tmp/harness/sw1041_<ICAO>[_cold].v2/<ICAO>.graded.json`)

| airport | pads | pads with a groundside neighbour within 3 m (touching ≥ 1) | pairs touching / gap ≤ 1 m / gap ≤ 3 m | knife cuts today | P runs TOUCH-OFF (runs / m) | GAPPED | ENGINE (ribbon / facade / gap piece: the engine's own stand-off) | AIRSIDE |
|---|---|---|---|---|---|---|---|---|
| HECA | 212 | 28 (24) | 42 / 1 / 11 | 17 | **17 / 612** | 2 / 66 (`building164` \| `objpav405` 1.31 m, `building8` \| `route3` 1.53 m) | 4 / 61 (`building75` \| `small_roads:-20325` −5.13 m over 57 m; `building165`, `building6`, `building147`) | 31 / 528 |
| KCLT | 98 | 31 (24) | 38 / 2 / 9 | (not read: that census ran after the W code was in the tree) | **11 / 65** | 2 / 24 (`building62` / `building61` \| `pol48` 1.79 / 1.75 m) | 1 / 0 (`building59` \| `small_roads:-7033#1`) | 7 / 17 |
| SPJC | 66 | 10 (5) | 15 / 1 / 7 | 8 | 1 / 0 (`building24` \| `pol37#1` +1.51 — 09f's held pair) | 2 / 0 (`building28` \| `pol68` 1.12 m, `building46` \| `pol74` 2.76 m) | 1 / 32 (`building52` \| `facstrip:building53`) | 2 / 0 |
| CYXY | 14 | 4 (4) | 5 / 0 / 0 | 4 | 2 / 157 (`building13` \| `pav4` +3.97 over 111 m, `building14` \| `pol129` +3.52 over 46 m — 13o's hillside terraces: HELD under Q-A) | 0 | 0 | 0 |
| OTHH | 33 | 4 (3) | 55 / 0 / 1 | 54 | 0 | 0 | 0 | 0 |
| KASE | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NLWF | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Reading. (a) HECA / KCLT reproduce §63 (2) on the gridded witness (HECA 17 TOUCH-OFF runs / 612 m where the spec read 15 / 565 on
`m`; the two extra are `building15` | `route3` 117 m and `building12` | `route3` 72 m, which the spec's read took by the larger
lot cell). (b) OTHH is the airport W changes most by COUNT — 55 touching pairs, 54 cut by the knife today — and it shows no P run
at all today: every one of those pairs is level across the stand-off, so the weld there is geometry-only; the master's sweep
reads it. (c) FOUND, NOT IN §63's CENSUS: the mapped-road RIBBONS, facade cells and gap pieces are minted AFTER the witness site
with the pads' knife in their own `occupied` union (`classify/ribbon_mint.py:170`, `facade_mint`, `gap_mint`) — a SECOND site of
the engine's gap; the edge read classes them ENGINE (HECA 4 runs / 61 m incl. `building75` | `small_roads:-20325`, KCLT 1, SPJC 1).
§63 (2) read `building147` | `small_roads:-3929` (0.76 m) and KCLT `building27` | `-7016#1` (0.72 m) as source gaps; they are that
knife less the snap. Not changed by this lane (C11 keeps the stand-off for gap / facade pieces; the ribbon is not named).

## W — the minimal probe (before the full arms), and what it found

Frame: late-stage replay pairs on `frames/pads67/{HECA,KCLT}.pkl` from the frozen worktree `weld63frz` (`<scratch>/weld63/pair.sh`),
base `b0` = ded211fb (HECA `hard_conflict` 254 / 104 / 64 = §63 (9)'s base). Probe driver `<scratch>/weld63/probe_drv.py PADS`:
today's knife on every pad pair EXCEPT the named pad, which takes Rule W as built (tree 204934aa = S + T + W code).

`ph` (HECA, `building12` welded): solve OPTIMAL; stage 1 unchanged to the digit (19,644 unknowns / 125,906 rows, the same 30 unsettled
rows and worst 0.0999 m, `346 → 332 relaxed {groundside 167, pad 104, taxi 61}` identical); airside value delta vs `b0`:
SOLVE-OWNED 0 moved (worst 0.0000 m), structure frame 0; `hard_conflict` 254 / 104 / 64 → 249 / 104 / 64. The weld is geometric
fact: `pav57` shares 49 vertices with `building12` (z 94.53–95.17, the pad's own columns), `route3` 4 (94.39–95.03); the lot's
ring edges on the rim are ≤ 1.3 %; `building12` | `pav57` leaves TOUCH-OFF (217 m → 0). So far §63 holds.

WHAT DOES NOT BEHAVE AS §63 (5) / Q-B SAYS — measured, attributed, NOT fixed (no rule improvised):
* `building12` does NOT stand at its DEM datum (104–106) with the road climbing to it. It stands at **94.39–95.17 (median 94.91)**
  — base `b0` 96.01–96.53 (the groundside seat S deleted), DEM under the rim vertex 106.29 (z − DEM −11.46 m).
* D1 — AFTER THE WELD THE PAD HAS NO DATUM OF ITS OWN. `solve/design_assemble` §9 gives a soft terrain datum to (a) a sheet
  component nothing anchors and (b) every GROUNDSIDE role body; a pad welded to a lot / road is one sheet component with them
  (anchored by the road's ramp rows), so it is in neither class: its level is whatever the pavement welded to it takes. §63 C9
  ("a landside pad's vertices — shared ones included — carry its own §9b mean") needs a solve-side row class that §63 (11)
  step 3 does not list; not built (a design decision: its weight against the lot's own datum is the spec author's).
* D2 — EVEN WITH ONE, THE PAD'S LEVEL IS A SOFT TARGET AND THE ROAD'S LAW IS HARD. `--why-at 30.11544369885,31.40991480491` on
  `ph`: v24953 binds on 18 `pads` rows; chain 9 hops / +7.19 m: pad plane → shared `route3` vertex v24792 (94.39) →
  `road_cross_section` 5.52 % × 13.0 m → 1.50 % × 7.3 m → `road_within_shape` 9.33 % × 11.9 m → the apron contact v8305 at
  92.24, **40 m from the rim**. Reaching 104 from 92.24 over that run is 29 %: Q-B's "ramps ≤ 10 % over ≥ 120 m" does not
  exist at this site. Nothing is infeasible with the pad low, so the tier ladder (§63 (4) (ii) "the pad above the road")
  never engages. INTERVENTION (`--why-relax`, full re-solve each): without `road_cross_section` (11,142 rows) the vertex
  rises +0.896 m; without `road_within_shape` (164,908 rows) −0.080 m — no single road family holds the pad down; the whole
  welded sheet (road, lot `pav57` and its own chains to the apron) sits in the cutting and the pad, having no datum, sits with it.
* `building12` | `route3` keeps 18.9 m of TOUCH-OFF (+4.06 m): `route3`'s page there is two carriageways at two levels
  (93–96 and 98–101, both arms: `b0` shows the same 97.6 / 98.5 at 7–8 m from the pad); the pad welds to the lower one and the
  upper one is inside the read's 10 m window. No ring edge is over the cap (worst 10.4 %).

## W — acceptance (replay pairs, one tree per arm; `w1` HECA / `kw1` KCLT at 70947240 vs `b0` / `kb0` at ded211fb; each tree's own census)

HELD under Q-A at classify (`pad_touch.dem_step_m` > 2.4 m): HECA `pol10` | `building4` (−5.09) / `building5` (−5.97), `route3` |
`building15` (+2.80); KCLT `pol24` | `building9`; SPJC `building24` | `pol35` / `pol36` / `pol37` / `pol57` (3.30–4.25 — 09f's site);
CYXY `pav4` | `building13` (4.25), `pol129` | `building14` (4.37 — 13o's terraces); OTHH none (54 cells welded, 0 held).

| read | HECA `b0` → `w1` | KCLT `kb0` → `kw1` | bar | verdict |
|---|---|---|---|---|
| P TOUCH-OFF (runs / m) | **15 / 565 → 8 / 68** | **8 / 62 → 1 / 0** | toward 0 | MET (survivors below) |
| P HELD | 0 → 1 / 2 | 0 | listed | — |
| P GAPPED | 2 / 66 → 5 / 86 | 3 / 24 → 4 / 24 | listed | — |
| P ENGINE (gap piece / ribbon stand-off) | 18 / 156 → 22 / 302 | 2 / 0 → 0 | — | rose at HECA (+146 m: `building131` \| `gap:0/s2/lot` 110 m +1.62) |
| solve | optimal | optimal | optimal | MET |
| `--null-change` | pass1a 9 / 0 / 0.119, pass1b 8 / 0 / 0.091, stage2 8 / 0 / 0.091 | not run | ≤ 20 / 0 | MET |
| airside nodes (solve-owned) removed / added | **9 / 2** | **6 / 3** | 0 / 0 | **MISSED** |
| airside movers > 0.02 m (solve-owned): runway / strip / taxi / apron, worst | 0 / 14 / 20 / 98, **0.14 m** | 0 / 4 / 5 / 6, **0.45 m** | runway 0; airside 0 | runway MET; **airside MISSED** |
| structure frame movers | 0 of 245 | 0 of 363 | 0 | MET |
| `hard_conflict` groundside / pad / taxi | 254 / 104 / 64 → 266 / **124** / **70** | 277 / 33 / 50 → 267 / **53** / 48 | taxi ± 3; pad not rising | **MISSED** (HECA taxi +6, pad +20; KCLT pad +20) |
| pad datums moved > 0.02 m (platforms + cluster pads) | 9 of 120 (`unit:43#16` 99.14 → 97.73, `#830` 99.58 → 100.95, `#850` = `building12` 96.17 → 94.88, `#8/0` 100.58 → 101.78, `#234` = `building59` 85.40 → 85.31 …) | 2 of 83 (`unit:3#456` 215.05 → 214.24, `#95` 215.98 → 215.92) | airside-seated 0 | **MISSED** (`building59`'s cluster fronts `pav131`) |
| census CRITICAL motion / visual | 3 / 1,962 → 3 / **1,973** | (census below) | not rising | **MISSED** (+11 visual) |
| census families that moved | `hard_conflict` 422 → 460, `road_cross_section` 501 → **617**, `transverse` 951 → 981, `within_shape` 45,194 → 45,525, `terrace_actual_step` 21 → 16, `pavement_over_road_cap` 23 → 21 (worst `route3` 4.77 m over 43.5 m =), LAW-TRUE 55,963 → 56,479 | | not rising | **MISSED** |

HECA TOUCH-OFF survivors (`w1`): `building15` | `objpav394` 48.8 m −1.67 at 30.11607022546, 31.40263583057 (welded: the lot falls
away from the rim inside 10 m); `building12` | `route3` 18.9 m +4.06 at 30.11506933865, 31.41007565037 (+ two 0 m runs: the upper
carriageway of the same page 7–10 m off, see the probe); `building8` | `objpav394` −2.23, `building190` (×2) / `building199` |
`objpav405` ±1.1–1.5 (0 m runs: single rim vertices). KCLT: `building56` | `pol22` +1.03 (0 m).

ATTRIBUTION OF THE MISSES (each is a general mechanism the airport showed, none fixed here — no rule improvised):
* M1 — THE KNIFE'S OWN NODES ON AIRSIDE EDGES LEAVE. The 9 removed HECA airside nodes are `apron|groundside_pavement` (×4 at
  30.1209–30.1213, 31.4070, the edge `objpav7#2` shares with `pav131`) and `apron|service_road` (×5) nodes: where a cut-back cell
  also bounds an apron, the knife's mitred corner crossed that shared edge and minted a node on it; with the cell clipped at the
  footprint instead the node is not minted. Stage 1's vertex set therefore changes wherever a welded cell also bounds airside, and
  the airside values re-settle (132 nodes, ≤ 0.14 m at HECA; 15, ≤ 0.45 m at KCLT — the 0.45 m apron node at 35.21568847964,
  −80.94398970459 has no road contact and moved the same in the one-pad probe `pk`).
* M2 — A GROUNDSIDE LOT'S CEILING OUTRANKS THE PAD. §63 (4) (ii) / (12) (iii) rely on "the tier ladder ranks the pad above the
  groundside road". `[design] hard_conflict_ranks` puts `rulesets.common.pavement_max_grade ceiling` and `road_max_grade pavement
  fallback` in the TAXI tier whatever face they stand on, so where a welded lot's ceiling rows and the pad's plane cannot both
  hold it is the PAD that is relaxed: HECA `building59` (cluster `unit:43#234`, airside-fronting, welded to `objpav7#2` on 5
  vertices) `pad_slope_max ceiling` 3 → 20 relaxed rows, against `{pad_slope_max 15, pavement_max_grade ceiling 4, frontage_hold
  2}`; a pad rim edge at 11.3 % over 0.7 m at 30.12058095572, 31.40718551777.
* M3 — A ROAD WELDED TO A PAD AND TO AIRSIDE A FEW METRES APART. HECA `dsf:objpav366` (welded to `building36` and `building96`,
  and to the apron at 30.11721, 31.38160): `pavement_max_grade ceiling` (taxi tier) 0 → 7 and `road_cross_section` 0 → 6 relaxed
  at 30.11688768935, 31.38182078144 — the +6 of the taxi tier.
* M4 — THE ROAD'S CROSS-SECTION AGAINST A LEVEL RIM: census `road_cross_section` +116 rows, `transverse` +30.
