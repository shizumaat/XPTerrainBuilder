# Spec: the fill's step at the road kerb (#712 / #1003, round 5)

Two-round-cap review of PR #1088 and PR #1134 rounds 3–4 (Fable reviewer, read-only, 2026-10-26). It reviews branch `origin/claude/l1088c-road-drop` at `af660010b`. `B:` marks a line on that branch.

Law: RULINGS 2026-10-20d, 2026-10-19ap, 2026-10-03e, 2026-10-14a (2), 2026-10-15a (2), 2026-10-19ai (low-level riser), 2026-10-05e (no airport-specific code), 2026-08-30l (consumer census).

Not verified: owner Q58 ("the 17 m ramp") and Q33 ("flatten it all") are cited by both PR bodies, but neither is in `docs/RULINGS.md`. Until they are recorded, the 17.58 m access-road ramp (`road-edge-drop-spec.md` §7) is an unratified compromise. Round 4's numbers have no control build.

## 1. Why the rounds did not converge

The rounds stacked four rules: R1 re-kind, R2 lens, R3 mouth lift and R4 drop wall. Each was added to repair the previous one's side effect. The drop, which is the one thing 20d asks for, was never given geometry of its own. It is derived four times, each from a later stage's output:

1. The fill level: `z_hi = datum_pred + widest reach band + y` (`B:model/platform.py:132-153`).
2. The §37 mouth lift on the fill's ring vertices (`B:airport/road_ramp.py:775`), read from (1).
3. `drop_runs` at the base derive: a run of kerb vertices whose §37 target stands more than `visual_m` over its DEM (`B:airport/road_edge_wall.py:83-101`).
4. `road_edge_walls` at the late derive: one wall per run that happens to have a gap-piece vertex inside a band `EPS_M = 0.05` … `BAND_M = 0.4` m off the kerb (`B:road_edge_wall.py:53-54, 139-176`).

**Step (4) is why two bars never moved.**
- A heightfield step needs two vertex lines, and nothing mints them. The wall therefore exists only where pass C left a gap sheet standing off the kerb by chance: 16 runs gave 6 walls and 10 `no_lower`. That is the "6 joints against ≥ 8" bar.
- The constants 0.05/0.4 are HECA measurements, which is a tuned window that 05e forbids.
- Beside a `no_lower` run, the gap piece is still held by the road's next edge, a ribbon or the fill collar. That is the "28 of 37 nodes > 0.5 m over DEM" bar.

**R1 is a global classification change with no station line.**
- `_network_strip` re-kinds any page at most 25 m wide with at least 60 % network road through it to `strip` (`B:classify/sources.py:173-199`). The network tree is read only there, while the strip's road stations still come from the service-road / 1206 evidence.
- So an R1 page loses its lot rows and gains no longitudinal authority.
- Where the network ribbon meets the page's end, the two authorities step. At CYXY this is `pav4` against `small_roads:-1071#1`, a 0.51–0.86 m `mid_edge_step`: the red twin `test_cyxy_verify_matches_v1_census`.
- WED's default "New Taxiway N" names are not a witness, because `taxi_name_match` returns `None` for them.
- The HECA rises are the same mechanism at `dsf:pol10`'s ribbons.

**D5 moved the block it was holding still.** `datum_vertices(fills=True)` gives a frontage-less block a stage-2 column. `building6` went flat (tilt 0.218 % → 0), but its mean moved +0.10 m. That is the control's own tilt span, not a defect: the ±0.05 bar was written against a tilted control.

**No matched control after round 3.** CRITICAL motion (6 against 4) and hard_conflict (1,271 against 739) cannot be split between the round and the main merge.

## 2. The rule: the fill's step, at one derivation site

The derivation site is `planar/landing.landing_regions` PASS 1a, where the pad fill is minted. Everything below is decided there, from the pack partition, the base regions and the DEM. No later stage derives a drop.

The steps apply to every pad fill `F` (plate or piers, `planar/pad_fill`, kept) of block `B` at predicted level `L = datum_pred + y` that cannot bank (`fill_road.cannot_bank`, kept).

1. **The road.** `R` is the set of road-family cells (`fill_road.road_strips`, kept, excluding `route`/`runout`) within `[building_pad] fill_road_reach_m` of `F`.
   - With no `R`, there is no extension: the collar stands as today, and the count `pad_fill_no_road` is reported as a finding, never a hull.
2. **The lens.** `F` grows to `R`'s near kerb (`extend_to_roads`, kept), less what is held and less `_cut_back` of earlier landings (kept).
   - `R` is never cut. Its kerb vertices on `F` are held at `L`, and they are §37 (6) mouths at `z_hi` (kept).
3. **The step (new, replaces R4).**
   - **Where:** along `R`'s far kerb, within the lens's span along `R`.
   - **What:** `F` mints a riser strip `<unit>/landing<k>#strip`, with the low-level riser's spelling and width: `max(identity weld spacing, 2 × grid)`. It is a bank face that every pad reader skips.
   - **When:** where the kerb's predicted level stands more than `[cockpit] visual_m` over the DEM on the riser's outer line.
   - **Predicted kerb level:** at route distance `s` from the fill contact it is `L − g·s`, with `g = [road_contact] ramp_grade`. This uses the DEM only, at planar time.
   - Below `visual_m` no riser is minted, and the terrain drapes.
4. **The declared step.** Each riser is one `road_terrace['wall']` record:
   - `retains: True`, `road_edge: True`;
   - `line` = the riser's outer line, `upper` = the far-kerb vertices, `lower` = the riser's outer vertices;
   - `height_m` = the maximum predicted kerb level minus the DEM.

   The existing readers take it unchanged: `wall_release`, `solve/wall_cut`, `_wall_step_rows`, `publication.wall_terrace_joints` and `check_grade.DeclaredWallSteps`. Every riser minted is a joint, so the joint count equals the riser count.
5. **The low side keeps its ground.** `model/planar.drop_edges` (kept, re-sourced) returns the edges a riser shares with its road, and `late_stations`/`gap_follow` keep their filters. The riser's outer vertices solve to the DEM under the wall step row.
6. **The block.** Keep `datum_vertices(fills=True)`: flatness is law. The bar is restated in §4.

The riser is emittable: it is the base-profile spec's steepest cell, which is already emitted for `<block>/p1#strip`.

### Consumer census (RULINGS 2026-08-30l)

| # | Reader | With the riser | Ruling |
|---|---|---|---|
| 1 | `planar/landing.landing_regions` PASS 1a | mints the lens, the riser and the wall record | the derivation site |
| 2 | `planar/landing` PASS 2 collars | strips and risers join `held_c` | edited (one line) |
| 3 | `planar/landing.landing_cut` | lot cut under the fill; road cut only under deck landings | unchanged |
| 4 | `planar/ribbons._ribbons_pass_c` | riser is a bank face; a crossing ribbon spans it | unchanged; measure |
| 5 | `planar/low_level` riser readers | reads as a strip, skipped by pad rows | unchanged |
| 6 | `constraints/platform.landing_rows` | riser faces take no landing row | edited: skip `#strip` |
| 7 | `constraints/platform.platform_collar_rows` | — | unchanged |
| 8 | `airport/road_ramp.road_ramp_targets` | mouth at `z_hi` | unchanged |
| 9 | `airport/road_ramp.with_road_ramp` | riser records join the pack walls; `drop_runs`/`road_edge_walls` deleted | edited |
| 10 | `constraints/road_ramp.wall_release`, `_wall_step_rows`, `wall_terrace_rows` | release across the riser | unchanged |
| 11 | `solve/wall_cut` | bending cut at the riser | unchanged |
| 12 | `pipeline/late_stage.late_stations`, `constraints/gap_follow` | no station or follow on a far-kerb edge | unchanged (`drop_edges` source moves) |
| 13 | `publication.wall_terrace_joints`, `check_grade.DeclaredWallSteps` | one joint per riser | unchanged |
| 14 | `airport/placement_read`, `slab_drape` | a body over the lens reads the fill | unchanged |
| 15 | `publication._landings`, `capture_state` | riser ref listed | unchanged |
| 16 | census road laws | the road is judged as a road up to its far kerb | the bar |

Airside: the lens and the riser take nothing within `bank_min_width_m` of the airside, so stage 1 never sees them.

## 3. R1 must narrow

The witness is contact with the high side, in the owner's words "reach the high terminals".

- A page carrying network road through it (the existing 04j numbers) is a road strip only if it edge-shares a building pad cell by at least `[cells] min_shared_m`. The pad cells are already read at classify by `ribbon_mint.mint_pad_roads`.
- The page's network way becomes the strip's station source. Find the strip-station reader with `tools/blast.py --find road_stations` before editing.
- `network_through_m` stays on `SourceRecord` as evidence for every page.
- A page that touches no pad keeps its verdict.
- No width, length or class threshold is added.

Verify this first, with no build: `tools/v2_solve_replay.py --replay --from classify` on `frames/m1/CYXY.pkl` and `frames/l1088c/HECA.pkl` prints the verdicts for `pav4` and `dsf:pol10`. If `dsf:pol10` fails the contact test, R1 drops to evidence only and the fill runs to the lot (owner question 1).

## 4. Acceptance bars and the matched-control protocol

Sites at HECA:
- #712: the parking lot north of the Seasonal Terminal (30.1096365, 31.3889978), within 0.5 m of the slab at 96.62.
- #1003: the lot between T3 and the kerb islands (30.112939, 31.397394), within 0.5 m of 101.66.

Bars:
- **Airside:** 0 solve-owned vertices move more than 0.05 m against the control (identity join).
- **Blocks:** `building5` and `building6` are flat (tilt at most 0.2 %), with their mean inside the control's own min–max for that block. The low-side pads `building22/68/63/14` stay within ±0.05 of the control.
- **Step:**
  - Every riser is one `wall_terrace` joint; report both the joints and the risers minted.
  - Gap-piece vertices within 4 m of a riser's outer line are within 0.5 m of their DEM. This applies to all of them: the named residuals must go, or be re-attributed to a cause other than a riser.
- **Access road:** longitudinal grade within the road cap and a 2 % cross-section (hard). Report its height over the DEM; the 17 m question stays with the owner.
- **Census:**
  - adjudicated at most the control's plus the joints declared;
  - `hard_conflict`, `hairline_pair`, `road_cross_section`, `pavement_over_road_cap` and `plane_gradient` each at most the control's;
  - CRITICAL motion equal to the control's.
- **Twins:**
  - `test_cyxy_verify_matches_v1_census` green;
  - the closure and registry twins, `test_pad_fill.py`, and the R2/R3 cases of `test_road_edge_drop.py`;
  - `tools/ratchets.py`.
- **#359 is out of scope.** Report the lot `dsf:objpav394` numbers before and after; it has no bar here.

Matched control: one tree, one day.
- **Control:** `build_airport.py HECA --base-arm` at the branch's merge base with main, served from the ledger or else built.
- **Round:** the branch merged with that main, built once.
- **Census:** both in the same `census.py control.osm round.osm` call, and both registered in `frames.py`.
- **Before the build:** iterate on `frames/l1088c/HECA.pkl` with `v2_solve_replay --replay --from planar` and the late replay.

## 5. Owner questions

1. If pages of the `dsf:pol10` class fail the pad-contact witness:
   - (a) the fill runs to the lot, and the lot keeps 14a (2) lot law with no re-kind;
   - (b) the lot the fill runs to is re-roled as a road when the fill is minted.

   I recommend (a).
2. `fill_road_reach_m`:
   - (a) keep 100 m (one forecourt depth) as a law value;
   - (b) no bound: the nearest road that serves the block.

   I recommend (a).

## 6. What to keep from #1134 and what to drop

**Keep:**
- `planar/pad_fill.py`;
- landing PASS 1a and its `kind` field;
- `planar/fill_road.py` (`road_strips`, `cannot_bank`, `extend_to_roads`);
- `_cut_back`, including the block cut;
- strips in `held_c`;
- `landing_cut`'s road cut under deck landings, only if R1 survives;
- `model/platform.fill_levels` and the mouth lift;
- `datum_vertices(fills=True)`;
- `wall_release` in the last stage;
- `model/planar.drop_edges` and its two readers, re-sourced to the riser edges;
- `SourceRecord.network_through_m`;
- the deletions of the `fill_ramp`/`fill_road` constraints;
- the law key `fill_road_reach_m` (pending question 2);
- tests R2/R3 and `test_pad_fill.py`.

**Drop:**
- `_network_strip`'s global re-kind (replaced by §3);
- `airport/road_edge_wall.py` entirely;
- the `road_terrace['drop']` publication and its report line;
- the R4 tests, replaced by riser twins;
- `road-edge-drop-spec.md` §2 R1/R4 and §4. This file supersedes them; §1 and §7–8 stay as the measured record.
