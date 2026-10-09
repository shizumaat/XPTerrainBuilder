# surf337 — notes (implementing spec §60: a `.pol` admitted by its own SURFACE is a gap sheet; #337; RULINGS 2026-10-04e (1), 2026-10-09a, 09b)

Lane `surf337`, branch `claude/surf337` off main `e2eec15c` + `claude/surfspec` (docs).
Scratch `<scratch>/surf337/`. Updated after each step.

## Step 1 — the gate (`6e55b6bc`)

`airport/dsf.pavement_verdict(path, decl) -> "source" | "sheet" | None`;
`is_pavement_def` = `== "source"`; `pol_declaration` / `PolDeclaration` replace
`pol_surface`; `pavement_gate` returns `(verdict, surface)`. Suite 9016 passed.

NON-BLOCKING DOUBT, decided toward the spec's stated invariant ("every
existing `dsf:pol<i>` id stays as today"): §60 (1) step 4 says "source when the
NAME also carries the `conc` word". A name with the `conc` word AND a
paint/sign word (`g/conc_lines.pol`) is REFUSED by main's name gate; if its
file declares a hard surface on a non-paint layer, a literal reading would
make it a NEW source (a new `dsf:pol` index). Built: a source is exactly what
the name alone admits (the `conc` word with no decorative word); that page is
a SHEET. Pinned by `test_a_source_is_exactly_what_the_name_gate_admitted`.
No such def exists on the seven measured packs.

## Step 2 — the population site

`airport/load.py`: a sheet page is read from the dump, consumed before the
polygon index advances, passes the 1,000 m admission (`n_far`), and is
appended to `Airport.gap_sheets` after the object bodies. `LoadReport`
`dsf_gap_sheets`, `dsf_gap_sheet_m2` (the raw page area after the admission —
NOT clipped to the classify gate as the spec's probe number was).
`pipeline/build.py`: one `[load]` line. Twins (a)–(c) in `test_airport_load.py`.
NO-OP: fresh CYXY capture on this tree (14 s) → `--from classify --emit`
body `cf8e9e89ec62` = main's `sw6_CYXY`. Suite 9019 passed.

## Step 3 — mint twin (d)

`test_a_page_sheet_on_a_runway_cell_mints_nothing_and_lists_nothing`.

## Step 4 — ONE tool

`Ortho4XP/tools/pavement_admission_report.py` ported from 2f348508 (`refused`,
`diff`) and the spec's `admit_probe.py` promoted INTO it as the `sheets`
subcommand (INDEX row; twin 4 tests). The probe's own copy of the branch gate
and its control/arm mint re-run are gone: the gate is the tree's, and the
control arm is `--strip-out` (the capture without its page sheets, replayed
`--from classify`). Six `surface337` frame rows ported to `docs/frames.jsonl`.

`sheets` on the registered captures (this tree's gate; polygons source / sheet / refused):

| ICAO | capture | source / sheet / refused | hard-surface defs refused, why |
|---|---|---|---|
| CYXY | fresh, this tree | 44 / 0 / 20 | `lib/airport/markings/DrapedDirSigns` 20 — decorative namespace |
| SPJC | conc333 main28500ecf | 107 / 0 / 284 | `objectfede/lines/red_grid` 46, `lib/airport/lines/safety_area_red` 42, `_yellow` 4 — decorative namespace |
| KCLT | conc333 | 101 / 0 / 1,858 | `DrapedDirSigns` 958 (namespace), `DrapedRwySigns` 759 + `ground_marks/mark_dir_amarillo` 115 (paint layer), `safety_area_white` 21, `colored_area_green` 1, `safety_area_yellow` 1 (namespace) |
| KASE | conc333 | 9 / 0 / 25 | none declares a hard surface |
| NLWF | conc333 | 0 / 0 / 2 | none |
| OTHH | surface337 main900727f2 | 70 / 281 / 8,446 | 6 sheet defs, 5,314,001 m² in the gate (712,279 on runway cells, 1,880,707 taxi, 822,710 apron); refused: markings namespaces 1,812, `Grass3` 3 (terrain word) |
| HECA | gapapron3 | 1 / 2 / 0 | `Asphalt_1_NOLINE` 2 / 63,175 m² |

## Step 5 — OTHH (fresh capture on this tree, `<scratch>/surf337/cap/OTHH.pkl`, 401 s of which partition 246 s — the one-time re-read)

Arms: `CTL` = the capture with its page sheets stripped (`sheets --strip-out`)
replayed `--from classify --emit --verify`; `BBASE` = the capture `--gap-free`
(the build's base map); `B` = `--late-from BBASE/solved.pkl`. All EXIT 0.

* CONTROL = MAIN: `CTL` body `73676fda6914` = main's `sw6_OTHH`. The capture
  frame is main's and the stripped arm IS the rule off.
* LOAD: 281 pages / 6 defs admitted as `dsf:gapsheet0..280` (no object sheet);
  dump verdicts source 70 / sheet 281 / refused 8,554; 5,315,178 m² inside the
  classify gate — 713,920 on runway cells, 1,882,550 taxi, 822,869 apron,
  659,461 pads, 1,420,470 free.
* PIECES (the capture's own classification): **131 pieces / 732,999 m²**
  (spec estimate 122 / 671,706 — +7 % / +9 %; min 207, median 1,719, max
  155,095 m²; rim 142,389 m). §59 class table: ROAD by evidence, touching an
  apron 10 / 275,644 m²; late road, touching none 92 / 391,092; APRON by
  share ≥ 20 % 19 / 42,049; APRON, no road evidence 10 / 24,213 → 102 late
  pieces + 29 apron parts (66,262 m²). Emitted: 130 late part groups, 27 apron
  groups.
* ON STANDING CELLS: runway 0.0 m², taxi 0.0 m², apron 8.95 m² — weld slivers
  ≤ 1.85 m² per piece where a `gapapron:` rim is closed onto its apron (§59
  D1), the largest five on `route0`; service_road 0.46 m².
* BASE STAGE, `CTL` → `BBASE` and `CTL` → `B` (`airside_value_delta`, tol 0.01;
  per-group read tol 0.02): solve-owned airside 0 nodes moved; RUNWAY 2 / 2
  groups identical, 0 / 0 vertices; junction, primary / secondary parallel,
  cross connector, stub: every group identical; pads 53 / 53; `tunnel_ramp`
  3 / 3, `tunnel_trench` 49 / 49 identical; standing aprons 0 movers (11 gain
  rim vertices, +94 / −3); the zone: 2 `adjacent_ground:taxi` parts change by
  1 / 2 vertices and one node 0.010 m (25.27960096, 51.60360218) — the band
  knife; service roads: 3 slivers gone (`small_roads:-2317#1`, `-2407#1`,
  `-8044`, 3–4 nodes), 11 follower-ribbon nodes > 0.02 m, worst 0.15 m
  (`small_roads:-2369` 25.25454063, 51.62572918).
* WALLS: `authored_seats` (15 records: the nine tunnel walls + six basins)
  identical in `CTL`, `BBASE`, `B` and main's `sw6_OTHH.v2/OTHH.rebake.json`.
* SITES: 25.25535, 51.62062 — the same 8 ways at 3.96 m in main and the arm,
  nothing minted within 25 m, no census row; 25.259994, 51.6104872 — the same
  9 ways, plus `gapapron:25` 14.5 m away at the apron's 3.96 m.
* CENSUS (arm under this tree's tool / main's `sw6_OTHH` under main's):
  CRITICAL motion 0 / 0; adjudicated airside 458 / 458; adjudicated 705 / 492
  (groundside 195 / 3, mixed 52 / 31); CRITICAL visual 2,111 / 1,846
  (unmeshable 2,045 / 1,828; CLIFF 36 / 18; approach 21 / 0; runway view 9 / 0).

### FOUND, NOT FIXED — three parts take a basin FLOOR's level (blocking for OTHH)

All 213 new rows ≥ 0.5 m stand at three basins: `gap:1/s3` at `basin_wall:4`
(−9.52..4.02 m, 13.48 m over 87 m at 25.2958182, 51.6027774), `gap:2/s1` at
`basin_wall:0` (1.97..3.97; 25.2539674, 51.6255951), `gap:1/s4` at
`basin_wall:3` (2.14..4.03; 25.2964682, 51.6065259). Every other of the 157
gap groups spans < 1 m and the 27 apron parts are flat at 3.96. The
`structure_rim` ways: 41 of 46 identical, 5 gain nodes and none moves — but
the nodes `basin_wall:4` gains stand at −9.52..−8.04 on a rim at 3.96
(`basin_wall:0` 1.97, `basin_wall:3` 2.14; `:5`, `:6` at 3.96).
MECHANISM (the solve's own duals, `--why-from B/solved.pkl --why-at
25.2955790,51.6031200`): v30309, z −9.52, DEM 3.96, held by ONE binding
`gap_follow` row at its upper bound −9.5273 — the part follows the
`tunnel_trench` FLOOR cell (`basin_floor:4`, −9.68) as its standing neighbour
across the stand-off; the last stage relaxes 7 such rows (worst 8.98 m).
Not a §60 intake defect: the gap stage (§53 (13) / §55) has never met a basin
(HECA's sheet touches none). The rule a part beside a basin should follow
(the rim, not the floor; or no follow across a wall) is the spec author's.
