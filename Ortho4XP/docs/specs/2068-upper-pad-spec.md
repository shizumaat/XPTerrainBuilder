# RULINGS 2026-11-13aa (1) — a pad under a unit's upper storey is held at that storey's level (#2068 LPPI tower) (Fable, 2026-11-13)

Base: `claude/lshell1` (94c34de07, in `claude/test-513`). Measured on `/Users/noah/XPTerrainBuilderData/.harness/frames/llppi2068/LPPI_deg.pkl` (degraded DEM).

## 0. Verified
- `dsf:pol96` apron, `airside_edge_was = service_road`, `airside_edge_m = 468.4` (round 1); 8,203 m², perimeter 1,311 m, mean width 2A/P 12.52 m. Shape: ring along the stands, 25 m block S of the terminal's SE corner (DEM 33.3–34.8), ~6 m × ~22 m neck (DEM 34.8 → 37.1), collar round the tower pad (DEM 36.7–40.0).
- Pad `building2` 355.2 m², held `conforming`, over pol96; DEM median 38.23 (36.96–39.11, relief 2.15), 38.47 at the owner's point. Terminal `building1` 8,199 m² held `one_block`, DEM median 33.09; real step +5.14 m.
- All 17 `lppi_terminal_NN.obj` share one anchor → `unit:0`; `unit_storey.unit_floor` 0.0. Over the pad: 20 solid parts, lowest base y 4.70, none footed; plinth `lppi_terminal_09.obj` comp 8 (y 4.7, h 0.0, 350.5 m², 100 % of pad); walled bodies `lppi_terminal_11.obj` comps 8, 9 (y 4.7, h 4.0 / 12.0). Other pads `building1/3/4` lowest bases 0.0/−0.32/0.0.
- Why paths miss it: `upper_storeys` has the pad in unit 0's storey footprint but §27 drops only contact runs along that footprint (pol96's 468 m lie along the stands); `group_low.group_floor(0)` None and pad share's `walled_feet` empty (23f unusable); `low_level_split` skips conforming pads. Lane figure: 33.09 + 4.70 = 37.79; 37.79 − 33.92 = 3.87.
Not verified: lane drawn numbers; `lppi_terminal_10__b2` fence (capture shows comps y 0.0 h 3.5, y 3.13 h 3.3, not `line`); `02__b0` (a part at y 8.7 `lppi_terminal_06` comp 2 is an upper floor); `read_split_levels` on this frame; solver outcomes; corpus census.

## 1. Contract (no second implementation: existing level grammar `<block>/p<k>` in `Registries.landings`, `constraints/platform.landing_rows`, z = D_block + y; precedents `planar/station_level.station_split`, mirror `planar/group_low`)
Witness — `airport/unit_storey.upper_pads(airport, law, air, pads)`; P is an upper pad of unit u when ALL (13r: doubt → today):
1. u has a floor t (`unit_floor`).
2. every solid part of u (not line/scatter) with ≥ half its plan in P has base y ≥ t + `low_level_min_step_m` (3.0).
3. parts based within `BAND_M` of the lowest such base y_p cover ≥ `PLANE_SHARE` of P and ≥ 1 is walled (`height_m ≥ chain_min_height_m` 2.5); canopy/roof alone refuses.
4. ground confirms both sides: rise = y_p − t; Δ = DEM median over P − DEM median over airside pavement within `pad_frontage_m` of the unit's floor parts; 0.5·rise ≤ Δ ≤ 1.5·rise and P's DEM relief < rise; no DEM → refuse (refuses a deck/cab over apron, #1905).
5. recorded only: a pack wall/fence of u within `pad_frontage_m` of P spanning ≤ y_p − rise/2 to ≥ y_p − `BAND_M`.
LPPI: t 0.0, y_p 4.70, cover 1.00, two walled bodies, Δ +5.14, relief 2.15 → pass.
Classify — `classify/storey_edge.arm_storeys`, called once in `roles.classify` right after `knife_storeys` (`classify/roles.py:801`); `airside_edge_flip` untouched. Candidates: a face §27 flipped from a road-class role that touches/overlaps an upper pad. `far` = face − (other airside pavement, buildings excluded).buffer(R), R = mean width 2A/P; open `far` by `pad_frontage_m`/2; arm = parts within the weld spacing of the upper pad → born role back as `<ref>#<k>`, evidence `storey_arm_pad = <pad ref>`; rest keeps the flip; pad cell carries `upper_storey_y`, `upper_storey_unit`; `_cut_back_groundside` (`roles.py:1214`) treats `storey_arm_pad` like `STOREY_Y_KEY` (welded, 20l (a)). LPPI (R 12.52, opening 1.5): arm 1,671 m² gross (≈1,370 net), x −172…−106, y −314…−240, DEM 33.5–40.0; kept apron 6,533 m² one piece; one transverse cut at DEM ≈ 33.9; kept apron ≥ 7 m from the pad. (No opening → 2,771 m² sliver up the terminal face; R/2 or R/3 deletes the neck.)
Planar — new `planar/group_up.py` `plan_group_up`, called in `low_level_split` before the `conforming` continue; shell pads (`by_pad`) excluded. Block = nearest held non-conforming block of the same unit (`unit_share`, as `station_split`); y = y_p − top_of(block); refuse if block top differs from t by > `BAND_M` or block has no datum column; region = `level_cut(P, P, air, others, law, grid, 0.0, whole=True)` (whole pad, `pad_frontage_m` off airside, a riser's width off other pads, `#strip`); mint `_next_plane(block)` with `{"block", "y", "deck": None, "kind": UP_KIND, "pad": ref, "witness": "group_up"}`; drop the pad's held record if nothing remains; verdict read from the pad cell's evidence (as `overlay._storey_lots`).
Seat: none new; `placement_read` `/p<k>` fold publishes the level under the block's plane → footless tower bodies stay in the unit's one zero, plinth on the level (expected gap 0.00); `storey_seat` stays shells-only; if replay shows unit zero ≠ D_block − t by > 0.05 → STOP.

## 2. Consumer census
| Consumer | file | Ruling |
|---|---|---|
| `airside_edge_flip`, `_lateral_airside_m`, `knife_storeys` | `classify/airside_edge.py:333`, `storey_edge.py:147` | unchanged; arm cut after the fixpoint |
| second §27 pass | `classify/gap_apron.py:69` | twin: arm still groundside at end of classify |
| `unreachable_aprons`, `letter_faces_by_neighbour` | `roles.py:805-812` | unchanged; twin kept apron reachable |
| `_cut_back_groundside`, `pad_touch` | `roles.py:1124` | extend: `storey_arm_pad` welds to its pad |
| facade/ribbon/gap mints, `pad_road_exit`, `frontage_road` | `classify/*` | unchanged |
| `upper_storeys`, `storey_band` | `airport/unit_storey.py`, `storey_edge.py:67` | reuse floors; `upper_pads` beside them |
| held verdict | `planar/platform.py` | pad consumed; record dropped when empty; twin |
| `plan_covered`, `plan_low`, `plan_group_low`, `_upper_split`/`plan_up`, `station_split`, `_shell_split` | `planar/low_level.py:585-657` | byte-identical for other pads; upper pad taken first |
| `extend_levels`, `_seeded`, `region_depths`, `cut_fill_bands` | `low_level.py:668-696` | skip `witness == "group_up"`; twin |
| `landing_vertices`, `landing_rows` | `constraints/platform.py:560, 599` | unchanged |
| `block_strip_rows`, collar rows | `constraints/platform.py:187` | unchanged |
| `riser_sets`, `riser_exempt` | `constraints/riser.py:42, 73` | extend predicate to `group_up` |
| cluster plane group, `rim_strip_ties` | `constraints/cluster_pad.py:468-496`, `pads.py:467` | unchanged; twin |
| `datum_vertices`, `stage_air_vertices` | `model/platform.py:291` | level is stage 2; movers listed |
| `wall_cut`, `riser_walls` | `solve/wall_cut.py`, `airport/riser_wall.py:58` | unchanged |
| §37 (6) contact ramp, road ceilings | `constraints/road_ramp.py` | apply to the arm; K0 |
| `pad_terrace` | `planar/pad_terrace` | none minted |
| `/p<k>` fold; unit seats | `airport/placement_read.py:133`, `airport/…` | unchanged; census (expected 0) |
| sidecar | `pipeline/publication.py` | new key `upper_pads` |
| `drawn_check`, `drawn_site`, `v2_explain` | `tools/` | one row per upper pad |
| code keys | `pipeline/stage_code.py`, `O4_Step_Code.py`, `auto_patch/provenance_code.py` | add `group_up` |

## 3. One round (Opus, high)
1 reader + twin; 2 `arm_storeys`, pad evidence, weld branch; 3 `group_up.py`, `low_level_split` call, riser predicate; 4 sidecar + `drawn_check`; 5 K0 replay before riser work (`v2_solve_replay.py --replay <LPPI_deg.pkl> --from classify --allow-degraded-dem --solved-out`, `--why-hard` within 100 m): the arm climbs ≈ 3.9 m in ≈ 40 m (≈ 10 %, DEM ≈ 9 %) vs 8 % free-road ceiling / 5 % §37 (6); if landing rows relax or the arm conflicts, never raise a cap — take the shortfall (expected 0.7–1.0 m) as a declared kerb at the level's edge along the arm (A2 (3) kerb grammar); new row family → STOP; 6 corpus census over `docs/frames.jsonl` captures (upper pads read, arms cut, seats changed) for the master; 7 close: `tools/harness/build_airport.py LPPI --tile 38 -29` (pre-approved refresh), `drawn_gate.py`, `drawn_site.py` at 38.551644, −28.442702.

## 4. Bars (LPPI)
U1 exactly one upper pad `building2` y +4.70 (1/3/4 refused). U2 role diff vs control only pol96 (arm `service_road`, rest `apron`); no airside within `pad_frontage_m` of the level. U3 every level vertex at D(`building1`) + 4.70 ± 0.05, spread 0.000 (expected 37.79; −0.44 vs pad DEM median, −0.69 at the owner's point; 0.5 bar on the median). U4 drawn plinth/tower base within 0.3 of the level. U5 `--why-at` the site ends at `landing:building1/p<k>`; `--stage1-diff` movers listed; airside away from the cut ≤ 0.02. U6 no `hard_conflict` within 100 m on landing/pad/ceiling rows; `airside_no_step`, `frontage_near_miss` = control; arm grade ≤ 8 %; collar cross slope and kerb listed; `drawn_gate` PASS. U7 with no upper pad, classification and planar byte-identical (replay one other capture).

## 5. Tests
`test_unit_storey.py` (plinth + body on a hill passes; canopy-only, deck over level ground, a part reaching down, hill 3× rise, no DEM refuse); `test_storey_edge.py` (arm cut on a U strip with a 6 m neck; sliver stays; no upper pad no change); new `test_group_up.py` (whole pad → block's level; same unit and held; `plan_up`/`plan_group_low` identical elsewhere); riser twin; synthetic solve twin; `test_harness.py`, `test_no_airport_specific_code.py`, registry twins, `ratchets.py dupes --near`/`unused`.

## 6. Risks
Arm may not reach the level at 8 % (K0). South collar welded to a level 1.3–1.6 m under its ground gets cut (pack wall tops ~39.5, matches). Stage-1 set changes along the cut line. False positives elsewhere (two-sided ground test + census). `roles.py` at its guide — keep additions ~4 lines. Coordination: lplate2068 must not seat the plinth (`lppi_terminal_09` b0, a flat plate) alone on the lowered pad before this lands. 13y (4)/#2063 seating gives the same zero.

## 7. Owner questions
Q1 the driveway climbs ~10 % on the real hill vs 8 % road cap: (a) keep 8 % and take the last ~0.7–1.0 m as a kerb at the plinth (assumed), or (b) a road to an upper-storey pad follows the ground's grade? Q2 plinth + ground enough for "certain", or must a pack wall/fence also be present? (Assumed enough; fence recorded only.)
