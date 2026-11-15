# Spec 2068 A3 — rulings on the A2 round's three stops: the fence's own stations are the ground witness, a projected vertex is not an unknown, a road inside the yard stands on the yard's ground (#2068 LPPI tower) (Fable, 2026-11-14)

Base: `origin/claude/l2068a2` `ec5ba9109` (on main `d381a76e4`). Amends `2068-fence-grade-spec-A2.md`; everything in A2 not named here stands. Owner 2026-11-14T16:25Z: "LPPI, option a" (the 3.5 % fence-foot plane). RULINGS 2026-10-05e, 11-13r, 11-14a, 11-14b. One Opus round, effort high. Never raise the lane cap; delete scratch builds when you report.

Review (TWO-ROUND-CAP-REVIEW of l2068a2): all three STOPs trace to the spec or to pre-existing engine rows, not to lane bugs. The lane's F0–F3 and F5 code is sound and is the base for the next round. Two A2 defects: the plane tilt cap was 10 % (over the hard 5 % pavement ceiling), and the Y3 plinth bar was mis-specified (L−1.04…L+0.00 is correct for a 5 m band on a 3.5 % plane).

## 0. Measured in review

Capture `/Users/noah/XPTerrainBuilderData/.harness/frames/l2068a2/LPPI_f0.pkl` (degraded DEM). Frame xy in metres; L is the level (replay 32.97 + 4.70 = 37.67; closing patch 38.11).

- 451 stations at 2 m on 8 unit lines of `lppi_terminal_10.obj`; 109 upper. Plane tilt 3.50 %, rms 0.232, residuals +0.55 / −1.19. Region with G6 bypassed: 2,542 m² in two pieces (833 west compound, 1,710 east). Plane − y_p: tower −0.41, B −1.36, C −1.46, D −0.85, E −0.97.

**STOP 1 — G6 asked the wrong question.** `za` (DEM median of airside within `pad_frontage_m` of the unit's floor parts, `airport/unit_storey.py:245-250`) reads 34.63. The DEM at the fence's own floor stations (base ≤ t + 1.0, n 338) reads 32.22; block datum D is 32.97. The DEM does not contradict the fence: DEM = 32.68 + 1.07 × base over all 451 stations (r 0.87); yard DEM − (pad DEM median 37.47 + plane − y_p) median −0.04 (q10 −1.06, q90 +0.97); A→B (51.7 m) DEM falls 5.06 m (9.8 %), plane 1.77 m (3.4 %).

**STOP 2 — four things hold the arm.** K0 chain: D v1072 34.75 ← v1423 34.52 by `road_cross_section` 2.36 % × 9.3 m ← neck v598 33.51 by `pavement_road_cap` 10 % × 10.1 m. The fallback mints 10 % on every ring edge of a pavement face unless a hard Diff already caps the pair at or under it (`constraints/pavement_cap.py:84, 136-140, 175-177`); a 20 % row never displaces it. The arm face `dsf:pol96#2` (467 m²) is L-shaped; the road pair split reads the minimum-area rectangle's axis (`constraints/roads.py:5-9, 338`), so the N–S climb is priced as cross-fall. A2's (a) stage-1 foot and (b) no-station vertices are also present (lane-reported). The OSM ribbon `small_roads:-658` shares the arm's west kerb vertices and is not an arm. Even freed, 20 % over 20 m reaches L − 0.56 at the level.

**STOP 3 — a soft stand-off pair with a hard twin.** Row 102123: yard v2120 36.67 vs apron v604 33.50, 1.80 m apart, allowed 0.0901 = 5 % × 1.80. `groundside_ramps` pairs every apron ring vertex with the nearest groundside pavement vertex within 1.954 m as a soft 5 % Diff (`constraints/groundside.py:42-98`); the yard's stand-off is 1.454 m. `pavement_ceiling` twins every pavement Diff under 30 m as a hard row at max(5 %, row cap) (`constraints/ceiling.py:189-209`). (Parent family inferred; the next lane prints `row.source.inputs` first.) Only new hard row: 65 → 66. Census clean: 389 rows control, 384 with the yard.

**F0 over the 264 files of `F0_line_flips_literal.txt`:**

| Reading | Flips | Fence | Glass | Rail | Other |
|---|---|---|---|---|---|
| Literal (lane code) | 264 | 37 | 18 | 17 | 192 |
| Vertical hull at each column | 124 | 32 | 14 | 16 | 62 |
| Ribbon (every column has foot and head) | 90 | 27 | 13 | 15 | 35 |
| Ground ribbon (§1 R4) | 8 | 2 | 0 | 0 | 6 |

The two LPPI captures disagree in D (32.54 old, 32.97 here); replay bars compare runs on `LPPI_f0.pkl` only.

## 1. Rulings (general; no airport named — 05e)

**R1 — G6′: the ground confirms the fence's foot at the fence's own stations (replaces A2 G6).** U = upper stations (G4); F = stations of the same unit's fences whose base is within `split_level.BAND_M` of the floor t. Pass when ½ ≤ (median DEM(U) − median DEM(F)) / (median base(U) − median base(F)) ≤ 1½. F needs ≥ `min_run_m / station_m` stations; with no floor run, use T4's `za` for DEM(F) and t for base(F). NaN refuses. The yard's own DEM median goes into evidence (`yard_dem_m`), reported, not gated. LPPI: 5.01 / 4.11 = **1.22**.

**R2 — the plane never exceeds the pavement ceiling.** Tilt cap = `[common] pavement_max_grade`, not the role's longitudinal cap (`classify/fence_yard.py:135-137`). G5's rms read on the capped plane.

**R3 — a projected vertex is not an unknown of the solve (makes A2 G7 true).** A PROJECTED vertex: a yard-face vertex no other face carries, and a free run vertex of R5. New `constraints/yard_edge.py`, `yard_exempt(rows, planar, counts)`, called beside `riser.riser_exempt` (`constraints/assembly.py:56`), before the ceiling (`:79`) and the fallback (`:90`). Withdraws (i) every row naming a projected vertex and any other vertex, (ii) every `road_ramp` row naming a projected vertex (`runout_exempt` precedent, `constraints/ramp_runout.py:464-489`). Single-vertex rows of other families stay. `pavement_road_cap` skips a pair holding a projected vertex (`pavement_cap.py:148-149, 167-168`). Count key `yard_rows_withdrawn`. Yard edge stays declared for the census (`pipeline/upper_pad_publication.py:138-187`).

**R4 — F0′: the ground ribbon (replaces the column reading; literal and cross-section both refused).** In `airport/line_object.component_shape`, a zero-plan-width component's height is its tallest column only when it is a GROUND RIBBON; otherwise its y extent, as on main. All five: (1) every column carries a foot and a head; (2) tallest column under `line_object_max_h`; (3) shortest column over new `[rebake] line_ribbon_min_panel_m = 1.5` (beside `structures.toml:872-874`, comment carries the §0 population); (4) between joined columns neither foot nor head climbs steeper than `emit.design.bank_slope` (0.33, `emit.toml:844`), read where it lives; (5) lowest foot at or under `elevated_base_m` (`structures.toml:865`) over the file's zero. Verdict per resource. The 8 files that flip (master reads before landing): LPPI `lppi_terminal_10.obj` + its `__b2_f8773ef4` variant; Orbx KBVS `ORBX_KBVS_FENCE_6a9ce919…` and `…_bfbf1811…`; LICR `Terminal_19.obj`; EGCC `car_park_metal__b1_3445fc02.obj`; KIND `KINDV2_KHUPHU1A_000.obj` + `__b0_680ccb7f`. Nearest miss: EGGW `Fence2019` (foot slope 0.39).

**R5 — F4′: a road inside the yard stands on the yard's ground (replaces A2 F4; no terrace, foot, station or cap change).**
- Gross yard G: `fence_yard._region` also returns G (flood's passable parts with road cells, plus pockets and base band, cut to the upper Voronoi, before cells and stand-off are removed). G rides the pad's evidence beside the plane as rings, key `yard_hull`, through `upper_pad_reads` into the landing record (`planar/group_up.py:49-65, 129-134`).
- Run: vertices of groundside road-family faces within the snap grid of G. FREE when only road-family faces carry it; FIXED when an airside-side face, any other standing face or the level carries it, or it lies outside G.
- Projection (`solve/project_yard.project_fence_yards`, after the yard): each free run vertex takes z = clamp(L + plane(x, y) − y_p, lo, hi); hi = min over sources f of z_f + g·d(f, v); lo = max of z_f − g·d(f, v); g = `[road_contact] upper_pad_road_grade` (14b); d = shortest path inside the union of the run's faces; sources = fixed vertices of the run's faces except the level's own. The rim keeps A1 (2)(c)'s declared step. lo > hi takes the mean, counted `infeasible` (expected 0).
- A free run vertex is projected, so R3 applies.
- Census: every face with a free run vertex joins `publication.lifted_caps` at g (`pipeline/publication.py:180-196`; `tools/check_grade.py:8187-8193`).
- An upper pad with no yard keeps A1's arm unchanged.

**R6 — the lane's five interpretations: all confirmed** (law into `attach_unit_fences`; flood hull = hull(upper stations ∪ pad grown by reach); unit line half-width = component plan width; `za` via `UPPER_AIR_Z_KEY` kept as R1's fallback; plane rides pad evidence into `upper_pad_reads`, `yard_hull` the same way). Also confirmed: the shared ring-run walker fix.

## 2. Order of work (from `claude/l2068a2`)

1. `lane_worktree.sh up l2068a3 origin/claude/l2068a2`. Print row 102123's `source.inputs` on a G6-bypass replay to confirm STOP 3; if not a `groundside_ramp` twin, report and continue.
2. R4 + twins. Re-read the 264 registered files: exactly the 8 flip.
3. R1, R2. Replay `--replay LPPI_f0.pkl --from classify --allow-degraded-dem --solved-out`; print G6′ ratio, plane, region.
4. R3. Replay with `--why-hard`.
5. Bars Y1–Y4, Y6 on the replay. Commit — the shippable state.
6. R5. Replay with `--why-at 38.551706,-28.442893` and `--why-hard`. Bars Y5, Y6. Commit, or revert to step 5 on a STOP.
7. Y7 on one other registered capture with a unit upper storey. Yard census over the captures l2068a2 used, one at a time.
8. Tests (§5), ratchets, registry gates.
9. Close: `build_airport.py LPPI --tile 38 -29 --pack-copy`, then `drawn_gate.py` with A2's five sites.

MEMORY: one capture at a time, in the foreground (~16 s, ~0.9 GB). Any script importing classify needs the `__main__` guard.

## 3. Consumer census additions (08-30l)

| Consumer | file:line | Ruling |
|---|---|---|
| `groundside_ramps` stand-off pair + ceiling twin | `constraints/groundside.py:76-98`; `ceiling.py:189-209` | withdrawn for projected vertices at assembly (R3) |
| `pavement_road_cap` ring and weld pairs | `pavement_cap.py:153-207` | skip a pair with a projected vertex |
| `road_ramp` targets and ceilings | `constraints/road_ramp.py:883`; `ramp_runout.py:464` | withdrawn on projected vertices; `terrace_rewrite` must not re-mint |
| `riser_exempt`, `upper_arm_sets` | `constraints/riser.py:58-144` | unchanged |
| `is_line_shaped` readers | `pack_partition.py:503`; `placement_cut.py:146-165`; `placement_atom.py:174`; `scatter.py:153-158`; `deck_family_contact.py:94` | R4 at the one reader; 8 files |
| `lifted_caps` | `publication.py:180-196, 250, 286`; `verify_stage.py:74-78` | run faces at g |
| `project_facade_strips` wrapper | `solve/project_strip.py:365-372`; `solve/design.py:463-473` | yard, then run |
| `upper_pad_records` | `upper_pad_publication.py:214` | `yard` gains `run_vertices`, `infeasible`, `g6_ratio` |
| stage code keys | `pipeline/stage_code.py`, `src/O4_Step_Code.py`, `src/auto_patch/provenance_code.py` | add `constraints.yard_edge` |

## 4. Bars (replay on `LPPI_f0.pkl`; control = the `l2068a2` tip on the same capture; z relative to L)

- **Y1** Fence parts `line`. Tower pad 355 m² ± 5; terminal 8,008–8,016 m². No pad-ring vertex within 1 m of the fence. L = D + 4.70 ± 0.05. In the build, D within 0.05 of 33.41.
- **Y2** G6′ ratio 1.22 ± 0.05. Tilt 3.2–3.8 %. Rms ≤ 0.3. 100–115 upper stations. Region 2,542 m² ± 5 % in two pieces. `yielded` 0. No yard vertex on an airside face.
- **Y3** Every yard vertex within 0.01 of L + plane − y_p. Plane at sites ± 0.05: B −1.36, C side −1.46, E −0.97. At the plinth's rim L − 0.9 … L − 0.2. Within 5 m of the pad L − 1.1 … L + 0.0.
- **Y4** As A2 (drawn, from the build).
- **Y5** (with R5) D = L − 0.85 ± 0.3. C within 0.1 of control. No two run vertices that see each other steeper than 20 %. `infeasible` 0. Rim step at the level ≤ 0.95, declared over `visual_m`. `--why-at` D names no row.
- **Y6** Hard-violated set equals control's 65 rows. 0 rows name a projected vertex. No airside mover over 0.05. No census family rises vs control's 389, except rows on the run's own ways (listed). `drawn_gate` PASS at the five sites, no MOVED outside them.
- **Y7** With no upper pad or no unit fence, classify and planar byte-identical on one other capture. `fence_division` / `edge_strips` stats at LPPI equal control.
- **Corpus** The 8 flips of R4 and no other. Yards minted: LPPI only.

## 5. Tests

Line-object twin (3.5 m sheet climbing 4 m at 20 % is a line; at 50 % not; 1.0 m rail climbing 6 m not; ribbon whose foot starts 12 m up not; one-level-column sheet reads its y extent; two stacked sheets not; boxed wall unchanged). `test_fence_yard.py`: G6′ passes with floor stations, passes on the `za` fallback, refuses at 0.3 and 2.0, refuses on NaN; a 12 % fence profile yields a 5 % plane or refuses on rms. `test_yard_edge.py`: cross row, its ceiling twin and a `road_ramp` row on a projected vertex withdrawn; single-vertex row stays; shared vertex keeps its rows. Projection twin (road through a yard flush beyond (plane − entry)/g and at g inside; fixed vertex pulls both ways; level's vertices are no source). `test_group_up.py` record carries `yard_hull`. Also `test_harness.py`, `test_no_airport_specific_code.py`, registry twins (`windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`), `ratchets.py dupes --near` / `unused` / `layers`.

## 6. STOP rules

- A 9th file flips, or one of the 8 does not → STOP at step 2 with the list.
- G6′ outside 0.5–1.5 on the build's DEM → no yard; ship F0′ and F1; report the ratio.
- After R3 a hard row naming a projected vertex survives → report its family and inputs. If a stage solve leaves `optimal`, or airside moves, fall back to withdrawing only rows that mix a projected and an unprojected vertex, and report.
- R5 misses Y5 or Y6 after one attempt → revert to the step 5 commit and ship the yard without it.
- Evidence cannot carry rings → carry `yard_hull` the way `road_terrace` records are carried, and say so.

## 7. Owner questions (unchanged from A2)

Q2 (south road down to the plane), Q3 (tank lot floor), Q4 (unit fences in the §27 division) wait for the sim read.

## 8. Unverified at spec time

Parent family of row 102123; A2's (a) and (b) at the arm; that a column with only single-vertex rows solves cleanly and `terrace_rewrite` does not re-mint; census readers of the lifted cap on the run's ways; the G6′ ratio on the build's DEM; the six non-LPPI flips' seat changes; the drawn look of the cut beside the ramp and of the fence where the arm's southern piece crosses under it; run-vertex heights away from D.
