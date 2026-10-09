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

### OTHH harness build `surf337_OTHH` (single run, `--no-ledger`, idle machine: load 1.3)

rc 0; body `b58e5698e7c5` = the replay arm `B`. PATCH BUILD **510.1 s** (main
`sw6_OTHH` 435.3 s; bar 660 s), harness wall 701.5 s (main 619.8 s).

| phase (s) | load | partition | classify | planar | constraints | solve | late_stage | emit | verify | total |
|---|---|---|---|---|---|---|---|---|---|---|
| main `sw6_OTHH` | 25.0 | 129.4 | 45.8 | 93.0 | 37.8 | 78.0 | — | 9.2 | 10.6 | 435.3 |
| `surf337_OTHH` | 23.7 | 126.8 | 48.1 | 92.1 | 37.8 | 78.3 | 75.2 | 10.1 | 11.1 | 510.0 |

Late stage: 131 pieces → 147 published records (92 whole, 11 lot, 15 step,
29 apron), 17 knives; `gap_follow` 2,186 rows, 632 lot rows, 7 relaxed
(worst 8.98 m — the basin parts).

### FOUND, NOT FIXED (2) — the rebake plan changes for six units (blocking for OTHH)

`OTHH.rebake.json` vs main's: `authored_seats`, `abutments`, `connectors`,
`contacts`, `flat`, `skipped` identical; `counts.deck_end_lines` 7 → 1 and SIX
units differ. Four bus bridges lose their deck-END seat and take one datum:
`OTHH_Bridge_05_LOD0_000` (unit:0, 25.248352, 51.615297) `deck_ends` → none,
`deck_datum_z` none → 3.96; `OTHH_Bridge_04_LOD0_000` (unit:4, 25.251561,
51.620307) → 3.885; `OTHH_Bridge_02_CLUTTER_LOD0_000` (unit:7, 25.252264,
51.617813) → 3.96; `OTHH_Bridge_01_CLUTTER_LOD0_000` (unit:16, 25.255677,
51.616821) → 3.63. Two datums move: `OTHH_TerminalRoads_01_000` (unit:80)
4.61 → 4.22, `OTHH_Emiri_Terminal_01` (unit:14) 3.97 → 3.96. The deck reader
of the object stage reads the cells under a deck; a gap piece there turns a
free-standing deck (seated by its end lines) into a deck over pavement. NOT in
§60 (5)'s consumer table — the claim "every downstream reader sees only more
or larger §53 pieces" fails for the rebake plan's deck readers. Not
attributed further (no intervention run); HECA's plan is identical to main's.

## Step 6 — HECA (fresh capture, 135 s; `CTL` = stripped; pairs `--gap-free` / `--late-from`)

* CONTROL = MAIN: stripped pair body `ad4ef9685c5f` = main's `swga_HECA`.
  ARM body `75c751a9dd95` = the CLOSING BUILD `surf337_HECA` (rc 0, patch
  build 522.9 s vs main's 524.7 s single run; late stage 114.2 s vs 117.0 s;
  rebake plan IDENTICAL to main's).
* LOAD: 2 pages / 63,176 m² / 1 def as `dsf:gapsheet23`, `24` after the 23
  object bodies.
* PIECES: 38 → 38, 78 → 78 records, 33 → 33 knives. `gap:0` 709,062 →
  728,160 m² (+19,098); the 53,392 m² piece → 63,939 m² (+10,547) and is
  RENUMBERED `gap:2` → `gap:1` (it overtakes the 57,249 m² piece, which becomes
  `gap:2`) — the spec said the numbering holds; nothing reads the ordinal.
* OWNER SITES: the three site parts are node-for-node identical in both arms
  (0 nodes over 0.005 m): `gap:7/lot` (#430), `gap:7/ramp0` (#292),
  `gap:0/s4/lot` (#358) — the sites read as on main (97.64 / 98.47 / 90.25).
  `pav6` (30.1047, 31.3965) identical, 103.27 at the site.
* AIRSIDE DOES MOVE (the spec predicted none): the page reshapes two APRON
  parts by 3 vertices (`gapapron:1`, `gapapron:2`), so stage 1 re-solves:
  runway 0 nodes (3 / 3 groups identical); taxi 157 nodes > 0.01 m, worst
  0.18 m (`pav111` 30.10172644, 31.39677571, 111.80 → 111.62); apron 37
  nodes, worst 0.06 m (`pav5` 30.10364304, 31.39442027); strips 542, worst
  0.17 m. Base stage relaxations identical (taxi 63 / 61, pad 17 / 10).
* LATE: `gap:0/s0/lot` (the grown part) 241 nodes > 0.005 m, worst 0.13 m;
  `gap:8/s0/lot` 2 nodes, 2.37 m at 30.11510995, 31.41089017 (101.80 →
  104.17; 42 m from #430, another part) and 0.74 m at 30.11414468,
  31.40954131 — not attributed.
* CENSUS (closing build, this tree's tool / main's `swga_HECA`, main's tool):
  CRITICAL motion 2 / 2; visual 1,912 / 1,910 (cliff 28 / 28, approach 25 /
  25, runway view 8 / 8, unmeshable 1,851 / 1,849); adjudicated 14,407 /
  14,403 (airside 12,196 / 12,195); `hard_conflict` rows 294 / 294.

## Handover

Full non-Qt split 9,027 passed / 20 skipped / 1 xpassed (after the last code
change); `-n0 tests/test_qt_*.py` 311 passed; the four gate files 202 passed;
`tools/ratchets.py` DUPLICATE PASS, LAYER PASS (size WARN, pre-existing:
`pipeline/build.py` 1,474 → 1,621, of which this lane +7).
Frames registered (`surf337`): OTHH and HECA captures, both build patches.

---

# surf337b — the review's fix list (spec §60 (9) F1–F4), 2026-10-09

Lane `surf337b`, same branch / worktree, `claude/surfreview` merged (docs + probes).
Scratch `<scratch>/surf337b/`. Replays off `frames/surf337/OTHH.pkl` with the
reviewer's gap-free base `<scratch>/surfreview/base/solved.pkl`.

## F1 — R1a (`9cf2cc1a`): a part follows a structure's RIM, never its floor

`constraints/gap_follow`: a face whose role is a floor / ramp role binds no
follow row; a wall void binds by its RIM edges alone — an edge no other cell
behind the step shares (the foot, shared with the floor, and the seam between
two wall parts are not rim). The two role sets are the existing ones
(`emit/graded.FLOOR_ROLES`, `planar/basins.WALL_ROLE`), handed in by the stage
as `pipeline/late_stage.BEHIND_STEP` (a `gap_follow.BehindStep`).

DEVIATION (layering, non-blocking): `constraints` may not import `emit` or
`planar` (the layer ratchet), and moving `FLOOR_ROLES` down into
`model/structures` puts it in the partition cache's code digest (every airport
re-reads its pack once, and the screen-sidecar probe goes stale). So the
generator takes the sets as an argument; `tools/v2_late_read.py` passes the same
constant. No new list.

OTHH late arm `F1` (body `7fd7ebfcae39`, 6 min 39 s), control = the reviewer's
`ctl` (= the surf337 build body):

| bar | control | F1 | bar met |
|---|---|---|---|
| `gap:1/s3` (25.2958182, 51.6027774) | −9.52..4.02 | 3.96..3.96 | yes |
| `gap:1/s4` (25.2964682, 51.6065259) | 2.14..4.03 | 3.96..3.96 | yes |
| `gap:2/s1` (25.2539674, 51.6255951) | 1.97..3.97 | 3.90..3.98 | NO by ONE node: 3.90 at 25.25414793751, 51.62585320745 (0.06 m under the rim) |
| relaxed follow rows | 7 | 0 | yes |
| `within_shape` | 528 | 374 (= main) | yes |
| census rows ≥ 0.5 m | 500 | 308 | yes |
| non-gap way groups moved | — | 0 of 1,062 identical (10 gap groups differ) | yes |
| authored seats (15) | — | identical | yes |

The one node: a piece vertex ON the basin rim (the flush cut) is bound to its
rim neighbours within `cap × d` — the row any ring gives — not pinned; the
reviewer's arm pinned it. F2 removes the case (no piece vertex lies on a rim):
3.95..3.97 there.

## F3 — R2 (`a9f116c3`): the deck datum reads STANDING cells only

`emit/rebake.deck_datum_from_surface` skips a vertex only gap pieces own
(`standing_vertex_ids`; a vertex a piece shares with a standing cell counts).

ACCEPTANCE WITHOUT A BUILD (`<scratch>/surf337b/plan_from_screen.py`): the
surf337 build's screen sidecar, its 13 deck rings RE-READ under this tree's
reader, through `rebake_screen.build_plan` → plan sha `8e24e55b3f68` = main's
`sw6_OTHH.v2/OTHH.rebake.json`: `deck_end_lines` 7, the six bus-bridge decks
`deck_ends` present / datum None, `TerminalRoads_Parking_000` 4.61,
`Emiri_Terminal_17_03` 3.97.

INSTRUMENT NOTE: the surface must be the build's IN-MEMORY one (rebuilt from a
`--solved-out` pickle with `emit.graded.graded_surface`), not `<ICAO>.graded.json`:
the JSON is the surface after `with_terrain_edges`, and main's OWN json reads
Emiri 4.0 where main's build recorded 3.97 — off the json the plan differs from
main's in that one member on any tree (the review's "Emiri 4.0" is that reading).

## F2 — R1b (`cc44f2c3`, its own commit; rests on owner Q1)

`planar/basins.build_basins`: a `gap:` cell goes through
`structure_approach.cut_gap_cells` (blade = rim ⊕ the mint's stand-off), LAST;
every standing cell is cut flush at the rim as before.

OTHH `--from classify --late-from` arm `F12` (body `500f5dddce63`, 6 min 37 s):

| bar | main | F1 only | F1 + F2 | bar met |
|---|---|---|---|---|
| rim nodes `basin_wall:0` / `:3` / `:4` | 54 / 35 / 28 | 63 / 45 / 31 | 54 / 35 / 28 | yes |
| `terrace_actual_step` `groundside_pavement\|tunnel_trench` | 0 | 21 | 4 | NO (4) |
| CRITICAL visual cliff | 18 | 36 | 22 | NO (those 4) |
| rows ≥ 0.5 m | 287 | 308 | 291 | — |
| the three basin parts | — | 3.96 / 3.90..3.98 / 3.96 | 3.96..3.96 / 3.95..3.97 / 3.96..3.96 | yes |
| relaxed | — | 0 | 0 | yes |
| non-gap way groups moved (vs F1) | — | — | 0 (12 gap groups differ) | yes |
| authored seats | — | identical | identical | yes |

`basin_wall:6` is back to main's 30 nodes; `basin_wall:5` keeps +3 (34 vs 31) —
they are `gapapron:6`'s, a §59 APRON part (a standing apron cell, cut flush like
any apron), all at the rim's 3.96.

THE 4 ROWS (attributed, not fixed): all at `basin_wall:0`, 4.7 m over
4.0–4.9 m, at 25.2539223, 51.6256993 and 25.2541457, 51.6258433 (×3). They are
the census's STRADDLE reading (`check_grade._check_terrace_actual_step`
reading 1: two pavement vertices on opposite sides of a declared joint line,
both within 5 m of it and of each other): two gap KNIVES (`shapes [37, 125]`,
declared steps 0.007 / 0.001 m) end at the collar beside this basin, and where
the wall void is 0.7 m wide the floor's vertices (−0.74) stand within 5 m of
the piece's (3.96) across the knife's line. The surface is right: piece 3.96,
rim 3.96 with main's nodes, floor −0.74, the declared wall between. The
reading has no notion of a wall between a pair; that is an instrument rule
(a pair across a structure rim is not a terrace pair) for the spec author —
not changed here.

## F4 — closing

OTHH harness build `surf337b_OTHH` (`--no-ledger`, single run, load 2.6): rc 0,
body `500f5dddce63` = the F1+F2 replay; `OTHH.rebake.json` sha `8e24e55b3f68`
= main's. PATCH BUILD **410.8 s** (bar 660), harness wall 414.3 s.

| phase (s) | load | partition | classify | planar | constraints | solve | late_stage | emit | verify | total |
|---|---|---|---|---|---|---|---|---|---|---|
| main `sw6_OTHH` | 25.0 | 129.4 | 45.8 | 93.0 | 37.8 | 78.0 | — | 9.2 | 10.6 | 435.3 |
| `surf337_OTHH` | 23.7 | 126.8 | 48.1 | 92.1 | 37.8 | 78.3 | 75.2 | 10.1 | 11.1 | 510.0 |
| `surf337b_OTHH` | 23.7 | 6.6 | 50.8 | 107.6 | 38.6 | 79.4 | 75.6 | 10.2 | 11.1 | 410.8 |

The partition cache HIT here (6.6 s; the two others re-read the pack) — net of
partition 404.2 s vs main's 305.9 s: late stage +75.6, planar +14.6 (single
run), classify +5.0.

CENSUS (closing body) vs main by family: CRITICAL motion 0 / 0; CRITICAL visual
2,062 / 1,846 — `hairline_pair` 2,040 / 1,828 (+212: groundside +175 of which
`groundside_pavement|groundside_pavement` +143; `apron|apron` +11, `?|?` +8,
`apron|groundside_pavement` +12, roads +36), `terrace_actual_step` 4 / 0,
`ramp_in_strip` 6 / 6, `within_shape` 12 / 12; in view by: cliff 22 / 18,
unmeshable 2,040 / 1,828, approach 0 / 0, runway 0 / 0. `within_shape` 374 / 374;
`groundside_cutback` 26 / 25.

OWNER SITES BY COORDINATE (`tools/osm_site.py`, every way within 25 m, main
`sw6_OTHH.osm` vs the closing build; "same" = node count and altitude span):

| site | main | branch |
|---|---|---|
| #453 25.2559273, 51.6083381 | 4 ways | the same 4, nothing new |
| #454 25.2792668, 51.6001421 | 2 ways | the same 2, nothing new |
| #455 25.2762962, 51.5920062 | 2 ways | the same 2, nothing new |
| #450 25.2542342, 51.6213069 | 7 ways | the same 7 + `gap:2/s0` (240 nodes, 3.61..4.16, 9.7 m away), `gap:2/s4` (3.96..3.99, 4.3 m), `gap:2/s4#1`, `#2` (3.89..3.96, 3.8 m), `gap:2/s8`, `#1` (3.96) and their interior ring |
| #450 25.253661, 51.6208155 | none | none |
| #451 25.2536839, 51.6231506 | 3 ways | 2 the same; `basin_wall:5` rim 31 → 34 nodes, all 3.96; new `gapapron:6` (59 nodes, flat 3.96, 8 m) |
| #451 25.2539056, 51.6221564 | 2 ways | the same 2 + one gap interior ring (14 nodes, 3.96, 11 m) |
| #451 25.2963819, 51.6065055 | 2 ways | the same 2 (`basin_wall:3` rim back to main's) + `gap:1/s4` (36 nodes, flat 3.96, 11 m), `gap:1/s4#1` (3.96), `gap:1/s1` (3.91..3.97, 22 m) |
| terminal 25.259994, 51.6104872 | 9 ways | 8 the same; `pav4` 163 → 168 nodes, flat 3.96; new `gapapron:25` (12 nodes, 3.96, 14.5 m) |
| 04-Oct cliff 25.25535, 51.62062 | 8 ways at 3.96 | the same 8, nothing new |

THE FIVE LARGEST PIECES (capture's class table; m² after the collar in the build):
`gap:0` 155,095 m², road by evidence (touches an apron), 25.2840197, 51.6000389;
`gap:1` 61,497 m² (61,702 before the collar), late road piece, 25.2768965, 51.6196906;
`gap:2` 51,287 m² (51,751), road by evidence, 25.2529797, 51.6206082;
`gap:3` 50,666 m², road by evidence, 25.2581967, 51.6193267;
`gap:4` 35,982 m², late road piece, 25.2671451, 51.5908223.
Largest APRON part: `gapapron:0` 12,758 m², 25.2787749, 51.6041032.
131 pieces, 732,231 m² (732,999 before the collar).

NO-OP BODIES (fresh captures on this tree, `--from classify --emit`):
CYXY `cf8e9e89ec62` = main's `swga_CYXY`; KASE (naturally sheet-free: source 9
/ sheet 0 / refused 25) `f9b157158a39` = main's `swga_KASE`.

### HECA replay pair on the final head (fresh strip of `frames/surf337/HECA.pkl`; `CTLBASE` → `CTL`, `BBASE` → `B`)

* OFF (`CTL`, sheets stripped) body `ad4ef9685c5f` = main's `swga_HECA`; ON (`B`)
  body `75c751a9dd95` = the first lane's closing build `surf337_HECA` — F1, F2
  and F3 are byte no-ops on HECA's PATCH (no below-grade structure beside a piece).
* No new piece: 38 → 38 pieces, 81 → 81 gap / apron-part groups (the `gap:1` ↔
  `gap:2` renumbering, D4). Owner gap sites node-identical off / on: `gap:7/lot`
  65 nodes, `gap:7/ramp0` 48, `gap:0/s4/lot` 160 — same node sets, max |dz| 0.0.
  Runway 3 / 3 groups identical, 0 nodes moved.

### FOUND — F3's HECA bar FAILS: the plan is NOT main's under R2 (one member, 0.165 m)

`plan_from_screen.py` on the `surf337_HECA` screen + arm `B`'s solved surface:
with the reader of the tree BEFORE F3 the plan is sha-identical to main's
`swga_HECA.v2/HECA.rebake.json` (`793b2f7479de` — the instrument is exact);
with F3 it is `1956d7537290`, ONE member differing:

`unit:43` `Airport/T23/T3_road.obj` (`dsf:obj223`, a flag deck, `elevated_deck`,
ring 23,646 m² about 30.1123889, 31.3962650): `deck_datum_z` 98.61 → 98.445.

The ring holds 791 surface vertices: 680 STANDING (662 the `building4` pad's,
13 `dsf:pol10`, 8 road) with median 98.445, and 111 owned by gap pieces alone
(`gap:32` 76, `gap:21` 24, `gap:2` 5, `gap:5/s4` 4, `gap:5/s0` 2; median 98.69).
Main's 98.61 is the median of all 791 — the same dilution of a pad reading by
piece vertices that R2 names at OTHH (`TerminalRoads_Parking_000` over
`building9`), standing on main since the §53 pieces (HECA had 38 before §60).
The spec's "HECA's plan is already main's" held only without R2.

No general reader gives both identities: standing-only = main at OTHH and
moves this HECA deck 0.165 m down; "a piece vertex never FOUNDS a datum but
counts beside standing ones" = main at HECA and the bus bridges at OTHH, but
leaves `TerminalRoads_Parking_000` at 4.22 (main 4.61) and Emiri at 3.96
(3.97); no F3 = main at HECA and six units off at OTHH. NOT decided here — the
spec author's / owner's (STOP-and-report; F3 is its own commit `a9f116c3`).
No HECA build was run on the final head (one closing build per round).
