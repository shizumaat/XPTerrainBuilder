Spec 2068 Amendment A1 (Fable, 2026-11-13) — review of ltower2068 9b06dbb6f; LAST Opus round. Uncommitted; commit as Ortho4XP/docs/specs/2068-upper-pad-spec-A1.md on claude/spec-2068tower.

REVIEW: reader/level/held-or-not sound (building1/p1 at D+4.70, LPHR identical). Datum drop = spec error: arm cut at one strip-width from airside pavement only → contacts 87→65, front 174→130 m, prediction 32.55→32.25 (ctrl.log:12 vs k0b.log:12). 83 violated hard rows (32 within 100 m) = spec omission: level not a road destination; worst single-vertex road_ramp §37(6) ceiling v1482 37.79 vs 33.80 (k0b.log:59-62). Flat hold: terrace_profile extends hold through consecutive pad stations (constraints/road_ramp.py:735-746); level rim reads as building1 frontage via /p<k> fold. Witness too loose: PLANE_SHARE=0.1 (geom/foot_planes.py:20); KBWI building22/25/28 passed at 0.19–0.20, LEMD building24 0.445.

RULINGS
(1) Datum: in storey_edge.arm_storeys, far = face − (other airside pavement ∪ every non-upper building pad).buffer(R); R and 1.5 m opening unchanged. Expect arm ≈850 m² starting ~12.5 m S of terminal SE corner; building1 contacts 87, front 174 m (check PAD BLOCKS line first).
(2) Road to upper pad:
 (a) airport/road_ramp.road_terrace (~:1264–1434): vertex bordered by group_up level → new key `level`, not `pad`. terrace_rewrite resolves L = stage-1 level of block datum vertex + y. terrace_profile ends flat hold at last floor-pad station; then target = min(L, z_e + cap·d), cap 10% (RULINGS 10-07b), also for `own` roads on this run only. No straight link.
 (b) group_up level rim vertex: no §37(6) target/ceiling, no terrace target; terrace_rewrite drops those single-vertex rows; landing rows hold it.
 (c) riser_sets (constraints/riser.py:42): for group_up level, far side also takes other vertices of every face carrying storey_arm_pad for that pad; riser_exempt withdraws arm multi-vertex rows spanning rim→arm. Publish rim runs with step > [cockpit] visual_m as declared terrace joints (wall_terrace_joints channel) and in upper_pads sidecar with height. No new row family/kerb/cap change. If a violated hard row within 100 m remains: STOP → owner.
 Expect neck arrives ~2.5–3.5 m under level; report small_roads:-658 profile (pad ramp 13a(3)).
(3) Witness (replaces §1(2)–(4); rise ≥ low_level_min_step_m stays): T1 no born-airside pavement within pad_frontage_m of the pad (only §27-flipped road faces allowed); T2 plinth cover ≥ 0.5; T3 another pad of the same unit with lowest solid base within BAND_M of t fronts born-airside pavement (= the block group_up names); T4 unchanged (ground 0.5–1.5×rise, relief < rise, walled part on plane). Expect KBWI 7 pads fail T1/T2/T3; LEMD building24 fails T2; LOWS building8 undecided — if it still reads, list it for master. Do not narrow ground band.
(4) Held or not: group_up takes upper pad held or not; block must be held non-conforming block of same unit, datum column, top within BAND_M of t. No block → no level → no arm.

CENSUS: road_terrace (key level); terrace_profile/terrace_rewrite (constraints/road_ramp.py:633, 825; byte-identical without level key, twin); §37(6) rows dropped on rim only; riser_sets extend; wall_terrace_joints (pipeline/publication.py) rim runs declared; 29x between-levels + reach seed 27a(11) unchanged, report if they name an arm vertex; pad_ramp small_roads:-658 unchanged, reported; upper_pads reader (airport/unit_storey.py) T1–T3, `air` split born/flipped at call site in roles.py after airside_edge_flip (keep roles.py growth to the call).

BARS (replace U2,U5,U6; U1,U3,U4,U7 stand): U2′ PAD BLOCKS contacts 87 front 174, arm pieces service_road, no airside within pad_frontage_m of level. U5′ D(building1) within 0.05 of control 33.92; airside movers >0.05 listed, none >15 m from cut; --why-at ends landing:building1/p1. U6′ 0 hard violations within 100 m, arm ≤10%, risers listed+declared, drawn_gate PASS. U3 note: level expected 38.62 (+0.39 over pad DEM median, +0.15 at owner point). U8 census over 76 captures: LPPI building2 only; KCLT capture lacks cl key — recapture or name skipped.
ORDER: reader+census; cut(1)+PAD BLOCKS; (2)abc; replay; one closing build LPPI +38-029.
TESTS: reader twins T1/T2(0.4)/T3 refuse; arm twin; terrace twin (+ no-level identical); riser twin; synthetic solve twin (apron, floor pad, 20 m arm, level +4.7 → 0 hard, apron unmoved).
RISKS: U5′ residual → owner with number; riser is a bank 30–60% not a wall; T1 may refuse a real pad touched at a corner (safe side 13r).
OWNER Q3: plinth ~2.5–3.5 m above driveway arrival at 10%: (a) keep 10% + bank (assumed) or (b) allow ~20% between a unit's storeys (real ground ~12%)?
Files: /private/tmp/claude-501/ltower2068/{k0b.log,ctrl.log,census.txt}; origin/claude/ltower2068.


---

## A4

### Spec 2068 A4: a floor yard needs a terrace at its fence and a level under it (Fable review, 2026-11-15)

Base `origin/claude/l2068d` `a9c8dab4f`. Amends the floor yard gates (`classify/floor_yard.py` module doc); everything not named stands, F7 and F8 included. One Opus round, effort medium. RULINGS 2026-10-05e, 11-13r, 11-14a/b. Never raise the lane cap; delete scratch builds when you report. Line numbers are the l2068d tree.

#### 0. Review finding
KMCI building43 was never put on a plane: it is not a held block, so no yard record reaches the projection (`project_fence_yards`: `no_level 5`, `vertices 0`), while its 166 yard vertices have their cross rows withdrawn (`constraints/yard_edge.py:148-178`) — the drawn "bank" is free vertices drifting. Its "fence" is two small rail rings of `Thong_Trimsheet_01.obj` (comps 235–238) on the pad's own rim; ground at them is level with the pad ground beside them (local drop −0.04…+0.03 m). F4 passed only because it compares against the DEM median of the whole 176 m pad (rises 3.2 m). Code path: record stored only for a held non-conforming pad (`planar/overlay.py:447-452`); planner does not hold a pad fronting no airside (`planar/platform.py:252-254`); projection skips a yard with no record (`solve/project_yard.py:70-74`). The sidecar hides it (late-stage design report does not project, `solve/design.py:476-489`) and still declares 37 `wall_terrace` joints (`pipeline/upper_pad_publication.py:161-186`).

Other yards (local drop = pad facing ground minus fence floor-station DEM): LPPI building2 +1.53/+1.31/+1.29/+1.28, held, projected at 33.588 (keep). HECA building138 +0.10 not held; HECA building6 +0.11/+0.38 held, no yard face survives planar but the record drives 1 road run; HECA building157 refused by F8; HECA building17 +1.48 not held; LOWS building17 +0.98 at the root, held conforming, no record, yard 985–996 m from the pad, unprojected.

#### 1. Rules (general; no airport named)

**F4′: the terrace is witnessed at the fence** (replaces F4's reference; `classify/floor_yard._witnesses`, `:273-287`).
- A fence line is a witness when the DEM median at its floor stations stands more than `split_level.BAND_M` under the DEM median of the pad's facing ground.
- Facing ground is the part of the floor pad within d(line, pad) + 2 × `[edge_lines] host_reach_m` of the line, read with `unit_storey.dem_samples` at 1 m.
- Empty facing ground or no finite sample is no witness. No new law value.
- The chain rule is unchanged, but evaluate along the chain: roots within `host_reach_m` of the pad first, then only lines within reach of a tied line. Never test every line of the unit.
- `yard_g6_ratio` and the stat's "off" become the weakest tied line's fence DEM minus facing-ground DEM.
- Where a unit line with floor stations stands within reach of the pad and none is a witness, the refusal is named: `floor_yard_refused:<ref>` = `no terrace at the fence (local drop <x> m)`.

**F1′: a yard stands only where its level exists.**
- (a) In `planar/overlay.py`, immediately before pass C (`:617-618`), `ribbon_cells` loses every cell whose `fence_yard_pad(ref)` names a pad with no yard record in `reg`. A record is a `landings` entry with `yard_plane` and that `pad`, or `held[pad][FLOOR_YARD]`. Count `fence_yard_no_level` in the pad counts and print the refs. Covers upper and floor yards alike.
- (b) `constraints/yard_edge.yard_records` (`:70-82`) returns a record only while a yard face of its pad stands in the map. That removes a road run with no yard face.
- No new module. If a helper is needed, put it in `model/registries.py` or `model/planar.py`.
- Correct the F1 and F7 text in the module doc: F7's level is an estimate, not the level the projection lands on.

#### 2. Consumer census (RULINGS 2026-08-30l)

| Consumer | file:line | Ruling |
|---|---|---|
| `_witnesses` → plane, region, F6, F7, F8 | `classify/floor_yard.py:180-206` | F4′ at the one site; downstream unchanged |
| `fence_yard._yard` (upper yard, G6′) | `classify/fence_yard.py:167-199` | untouched |
| front keep-offs reading late polygons | `planar/overlay.py:352, 365, 382, 483` | still see a cell dropped at pass C; that ground stays unclaimed (accepted) |
| pass C | `planar/overlay.py:618-623`; `planar/ribbons.py:29` | receives the filtered cells |
| late-stage re-derive | `pipeline/late_stage.py:324-330` | same overlay, same filter |
| `yard_records` readers | `solve/project_yard.py:52-53, 142-146`; `constraints/yard_edge.py:89, 158`; `pipeline/upper_pad_publication.py` | F1′(b) at the one reader |
| `projected_vertices` / `yard_exempt` | `constraints/yard_edge.py:148-178` | unchanged; no orphan face remains |
| `yard_edge_joints` | `pipeline/upper_pad_publication.py:161-186` | no face, no joint |

#### 3. Order of work
1. `lane_worktree.sh up l2068e origin/claude/l2068d`.
2. F4′ and its twins.
3. F1′ and its twins.
4. Replays, one capture at a time in the foreground (any script importing classify needs the `__main__` guard):
   - `--replay frames/l2068a2/LPPI_f0.pkl --from classify --allow-degraded-dem`
   - `--replay frames/l2068d/KMCI.pkl --from classify`
   - Classify-stat reads on `lheca4/HECA.pkl` and `lowspad/LOWS.pkl` (LOWS ~9 min, HECA ~6 min).
5. Ratchets and the registry gates.
6. Close on the owner's site: `build_airport.py LPPI --tile 38 -29 --pack-copy`, then `drawn_gate.py LPPI` at tower=38.551644,-28.442702,60 fence=38.553014,-28.444539,60 fenceW=38.552622,-28.445456,40, against l2068d's baseline (`/tmp/harness/l2068d_lppi.*` drawn json if present, else frames/l2068d).

#### 4. Bars
Materiality 0.01 m levels, 0.05 m local drops, 1 m² areas. At most two fix attempts per bar, then STOP. Write `.progress` stamps.
- **K1, KMCI replay.** `floor_yard_refused:building43` names F4′ with local drops −0.04…+0.03. `fence_yards 0`. No cell or face with ref `fenceyard:*:building43`. No `fence_yard:` joint for it. Classification at that pad equals main's.
- **L1, LPPI replay.** `floor_yard:building2` keeps the same four fences and witness 219/451; pieces 2,113 / 426 / 87 m², region difference from l2068d ≤ 1 m²; local drops +1.53 / +1.31 / +1.29 / +1.28; `fence_yard:building1` line identical; `facade_strip.yards.no_level` 0.
- **L2, LPPI build.** 0 nodes move > 0.01 m against `frames/l2068d/LPPI_auto.patch.osm`; building2 datum 33.408, yard faces 33.588; sidecar `no_level 0`; `drawn_gate` PASS, no MOVED.
- **C1, corpus.** HECA building138 and building6 refused by F4′; HECA building17 passes F4′ (+1.48) and its cells are dropped by F1′(a); HECA building157 stays refused; LOWS building17 has no yard face; no capture shows `no_level` > 0; no run stands without a yard face.
- **Y7.** A map with no yard is byte-identical in classify and planar on one other capture.
- **Build time.** F4′ reads at most 400 samples per tested line, along the chain only. Report the classify clock before and after from the replay's own print; no timing run.

#### 5. Tests
- `test_floor_yard.py`: a rail ring on the rim of a pad whose ground falls 3 m along its length mints nothing and names the refusal, even though the whole-pad median stands over the ring by more than the band. The existing positive case passes unchanged (local drop 2.5). A line reachable only through a non-witness is not tied.
- Planar twin: a floor-yard cell whose pad is unheld, or held conforming, yields no `fenceyard` face and the count. A held non-conforming pad keeps it.
- `test_yard_edge.py`: a record whose pad has no yard face gives no record and no run.
- Also `test_fence_yard.py`, `test_harness.py`, `test_no_airport_specific_code.py`, the registry twins (`windows_text_io`, `patch_env_classification`, `tile_failures`, `console_encoding`), and `ratchets.py dupes --near`, `unused`, `layers`.

#### 6. STOP rules
- LPPI's root line (`unit:0:dsf:obj6#3`) reads under the band on the closing build's DEM: report the four drops and stop. Never lower the band or change the reference.
- Any LPPI node moves, or any LPPI face other than a `fenceyard` face changes.
- A yard face survives with `no_level` above 0 after F1′.

#### 7. Not in this round
- F7 unchanged. If a real-witness site ever shows a cut, the place is `solve/project_yard` where L is known (never touch the upper yard).
- Q1 reach: nothing bounds how far from its pad a floor yard may stand (LOWS 985 m). Master/owner rule later.
- Q2: a real local witness at an unheld pad (HECA building17) — wait for a sim read.

#### 8. Unverified at spec time
- The l2068d KMCI build numbers are not registered.
- Why row-less yard vertices sit −1.25…+0.95 off DEM was not traced.
- F4′ on LPPI's build DEM (capture is degraded-DEM; margin over the band 0.28 m).
- Whether building43 is a garage on an authored cut.
- Optional drawn proof at KMCI: `build_airport.py KMCI --tile 39 -95 --pack-copy` then `drawn_gate.py KMCI --site b43=39.309679,-94.713679,120 --against <main control>` — run it if the 4-build cap allows (KMCI is in the next test app).
