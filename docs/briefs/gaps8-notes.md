# gaps8 notes — spec §55 (15) built and replayed; STOP at S-E on the census table (2026-10-07)

Lane `gaps8`, branch `feature/pavement-gaps`. Scratch `<scratch>/gaps8/`
(`ARM3/` = the ONE replay: patch, sidecar, `solved.pkl`, `log.txt`;
`arm3.txt`, `arm3.site.txt`, `census.txt`, `census.json`,
`rows.HECA_auto.patch.json` = the ARM's rows — the two patches share a stem
and the base dump was overwritten; BASE's rows are `<scratch>/gaps7/rows.HECA_auto.patch.json`).
The replay frame is registered: `/Users/noah/XPTerrainBuilderData/.harness/frames/gaps8/`
(patch body `5eff6d9f4ed1`, sidecar, `solved.pkl`, `log.txt`). CYXY harness
build `gaps8_CYXY` body `2a00c361ffc2` = main's.
The closing HECA build (S-G) was NOT run: the census missed its stated
tolerance at S-E.

## Done

| step | state |
|---|---|
| S-A1 | `model.planar.shares_gap_part(pm, ids)` + `gap_step_part(ref)`; read by `planar/shapes.straddles` and `shape_airside.declarable_pairs`. |
| S-A2 | `planar/shape_parts.py` (`label_gap_parts`, `part_shape_of_face`): parts out of the pavement union, one label per step part, welded rim keeps the standing label, `shape_of_face` by kind, `ShapeStats.part_contours_undeclared`; the 29j orphan rule never reads a part face. Twins `tests/auto_patch_v2/test_shape_parts.py` (7, one a frame twin on `gaps7/ARM2`). |
| S-B | sidecar LAW key `late_stage` {floor_m, followers}: `run_late_stage` reads the floor ONCE and records it (`report["stage"]`), `publication.late_stage`, emit register, `check_grade.SIDECAR_LAW_KEYS`; `late_stage_unknown_nodes`, `late_stage_floor_m`; `+ floor_m` for unknown\|unknown pairs in `within_shape` (never a road cross-section pair), `pavement_over_road_cap`, `cross_shape`; `cross_shape` reads `_declared_step_allowance`. Twins `tests/test_late_stage_census.py` (9, one a frame twin). |
| S-D | `_check_hard_conflict`: a groundside-tier record sides groundside. |
| S-E | ONE replay + reader + three sites + census (below). |
| S-F (tool) | `census.py --class` (`tools/harness/census_class.py`), INDEX rows, twin `tests/test_census_class.py`. |

## S-E measured (replay `ARM3`, against `gaps6/BASE`)

Stage: movers 0 of 34,540; LP relaxed 91 (follows 37 / 3.57 m; ramp ceiling
15 / 9.52; ceiling last stage 15 / 3.62; road_cross_section 9 / 0.23;
constant-end ceiling 9 / 1.42; lot 6 / 10.78); follow misses 92 = DECLARED
43 + OWN-GROUP 49 (26 / 8 / 10 / 5, worst 2.05 m); lot rows 214 / 6 missed
(worst 5.39 m, gap:8); stepping pairs 84 / 69, 24 at a merged station;
knives 46, worst 7.94 m; gap joints 78 / 2,768 m; 49 knives' facing rim
2,027 m against 2,514 m declared, short only `gap:4/s1 | s2` (8.5 m, 3.2 m);
contours 13, all through ribbons, none in a part; ribbons grown 9 (gaps7 6).
Cliffs: 4.95 -> 0.18 m; 4.53 -> 0.64; 4.23 -> 0.64; ramp1 0.52 -> 0.28;
in-part pairs beyond cap x d + floor 14 -> 0. Sites 97.46 / 97.56 / 90.24.

Census, adjudicated, vs BASE (replay arm): within_shape +17 (5,673);
pavement_over_road_cap +12 (27); mid_edge_step +4 (46); vertex_to_edge +2
(12); cross_shape 0; terrace_actual_step +32; road_cross_section +77;
plane_gradient +2; road_coverage_join +32 (a replay reading: gaps7 read 32
in its replay and 2 in its build); hard_conflict 91 (the replay sidecar
lacks BASE's 264 — gaps7 item 5; a build carries 264 + 91). Total +5 in
the replay, about +239 build-equivalent against the predicted -50…+50.

WHY (rows classed, `attr.py`):
* within_shape: 236 of the rows the prediction sent to "the constant-end
  remainder" stand on NON-follower ribbons — standing ways, both nodes
  constants, BASE's own rows (BASE carries 279 ribbon rows). The stage's
  own rows are 61: follower ribbon 29 with a constant end + 3 both-unknown
  over the floor (`small_roads:-3929`); parts 18 constant-end under the
  floor (`gap:15`), 6 both-unknown over the floor (gap:8 5.93 m over
  32.5 m; `gap:1`), 5 with a constant end over the floor (`gap:15`).
* terrace_actual_step: the 14 knife rows did NOT go to 0 (same count as
  gaps7; worst 8.33 m `gap:5/s2 | s4`): the family prices the nearest
  straddling pair against the joint's `step_m + cap x d`, and a knife's
  midline is several joint records each declaring its own pairs' step.
  Plus 8 part\|standing (three pads' feet, a tunnel ramp, `pav131`, `route24`
  beside a joint line), 3 in-part, 3 part\|ribbon.
* pavement_over_road_cap: 11 part rows, all at named residuals (`gap:1`,
  gap:8 x3, `gap:15` x2, `gap:37/lot | objpav113` x5).

## Found, not fixed

1. LABEL ORDER. Parts are labelled after the standing PAVEMENT and before
   the roads (the spec's site, `_label_pavement`). Labelled after
   `_label_others` instead, the standing labels equal the base's on every
   vertex (0 lost against 524 standing road vertices unlabelled here:
   12 standing roads read a part contact as a crossing) but 5 more ribbon
   contours stand (19; `small_roads:-18724 / -18725 / -20429 / -18892 /
   -20428`). Measured on `gaps7/ARM2`; the probed numbers follow the order
   built.
2. `weld_same_role_mouths` / `separated_label_pairs` read a part's rim
   edges: standing shapes split against the base on 139 vertices (gaps7:
   105). Identity only (the pairs are inside the apron body).
3. Two follower-ribbon vertices the stage held at identity read UNKNOWN in
   the census (on ribbon ways only).
4. road_cross_section +77 = 97 new - 20 gone; 96 new rows on follower
   ribbons (71 both-unknown, 25 one constant end), 39 on `small_roads:-3929`
   / `-3927` (worst 1.66 m over 11.6 m, 14.3 % against 2.7 %); 16 over 0.5 m.
5. `census.py --rows-json` over two patches with one stem keeps the last.

## Next command (the closing build, once the table is re-ruled)

    cd Ortho4XP && venv/bin/python tools/harness/build_airport.py HECA
    venv/bin/python tools/harness/census.py \
        /Users/noah/XPTerrainBuilderData/.harness/frames/gaps6/BASE/HECA_auto.patch.osm <build patch> --class
