# Brief pack — lane `v2cutfeet`

Base: main `087b0d6f` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§11b (7): a placement foot on a structure-cut face states no ground row — OTHH's ramp bumps are the tunnel object's own foot rows (RULINGS 2026-09-13bs).

## The brief

OTHH's curving tunnel ramp has bumps (owner 13bn item 2). Scout v2othh327 (RULINGS 13bs — read it whole: the profile table, the eight foot rows, the interventional arm) proved the cause: §11b foot rows (`constraints/foot_rows.py:107,122-136`) from the tunnel object's OWN body seat the ramp face at the ground datum. Implement §11b (7): in `foot_rows._verdict`, a foot whose `index.role_at()` lands on a structure-cut role (`tunnel_ramp`, `tunnel_trench`, `wall_corridor_ramp`, `door_ramp`, `garage_ramp`, `retaining_wall`, the basin floor — take the role set from `law/families.toml` / the structure roles the emitter names, ONE list, not literals) takes a `cut` verdict: counted, reported (`DesignReport.foot_rows` by verdict), NO `Linear`. The object stage then seats such a body on the solved cut surface at its feet (it already reads the design surface under its feet — confirm nothing else needs to change; the tunnel object's crest plate law §16e (1) stands). Measure on the registered OTHH capture (`tools/harness/frames.py list OTHH` — scout v2othh327's `OTHH.pkl` + its two arms `OTHH.solved.pkl` / `OTHH.nofeet.pkl` beside it): `v2_solve_replay.py` replay with your change vs the base; then ONE OTHH build (`build_airport.py OTHH`, base arm from the ledger). LEMD and KCLT: prove byte-identity by replay on their registered captures (neither has feet on a structure cut — say so with the count). The cross-kerb monotone chain (`planar/structures.py:116, 375, 439` — no `Flat` when the curving ramp's kerbs separate past `_STATION_CLUSTER_M`) is OWED, not yours unless it costs a bar.

## Bars

- OTHH ramp `tunnel-object:tunnel south west 2.obj@0`: z − design at 25.253869, 51.603365 mean 1.22 / max 3.31 → ≤ 0.05 m; the profile monotone −1.138 → 3.962 at ≤ 8 % every station (today 12 of 21 monotone rows violated).
- OTHH `tunnel_ramp` off-design max 5.09 → ≤ 0.05 m; in-scope `within_shape tunnel_ramp` 13 → 0; `wall_corridor_ramp` off-DEM max 1.39 → ≤ 0.15 m; `retaining_wall` 1.42 → ≤ 0.1.
- The design solve OPTIMAL with `HARD SET SETTLED` (today feasible, 2 violated, SET NOT SETTLED 833 flips); the three settled lines quoted both arms.
- `cut` foot verdicts printed in the report (expect ~574 pairs at OTHH; 0 at LEMD and KCLT).
- LEMD and KCLT replays BYTE-IDENTICAL; the object stage's seat of `tunnel south west 2#b0` re-read: crest flush (13v bar ≤ 0.3 m), the body riding the ramp.
- ONE OTHH build; suite twice (`tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`).

## Files

Yours: `Ortho4XP/src/auto_patch_v2/constraints/foot_rows.py`, `Ortho4XP/src/auto_patch_v2/solve/design_report.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/airport/placement_family.py`, `Ortho4XP/src/auto_patch_v2/planar/structure_underpass.py`, `Ortho4XP/src/auto_patch_v2/emit/osm_adapter.py`, `Ortho4XP/src/auto_patch_v2/airport/obj8.py`

## Spec (object-placement) §11b (7)

### §11b (7) A FOOT ON A STRUCTURE CUT STATES NO GROUND ROW (Fable 2026-09-13; RULINGS 2026-09-13bs, owner OTHH read 13bn item 2) — lane `v2cutfeet`

OTHH's tunnel object `tunnel south west 2#b0` is re-seated to the ground
(3.962) and its §11b foot rows then demand that the ramp its own walls cut
stand at that ground every few metres: the ramp sags between the nails
(+3.31 m off its design line at the owner's point; 12 of 21 monotone rows
violated; all 13 of OTHH's over-cap `tunnel_ramp` rows on this one ramp).
Dropping the foot rows solves the same capture as a +3.6 % descent, optimal,
hard set settled.

7. A placement foot whose surface sample lands on a structure-cut face —
   `tunnel_ramp`, `tunnel_trench`, `wall_corridor_ramp`, `door_ramp`,
   `garage_ramp`, `retaining_wall`, a basin floor — takes a `cut` verdict at
   `foot_rows._verdict` (beside `basin` / `pavement` / `padded` / `bare`),
   counted and reported, and emits NO `Linear`. The cut surface is §33 /
   §34's; the object RIDES it (§16a: cut where its carrier is cut; §16c (3):
   a foot over a structure cut is not a ground foot). An object at a trench
   edge keeps its crest plate (§16e (1)) and rides the cut with its feet.

BARS (the registered OTHH capture): `tunnel_ramp` off-design max 5.09 →
≤ 0.05 m; in-scope `within_shape tunnel_ramp` 13 → 0; `wall_corridor_ramp`
off-DEM 1.39 → ≤ 0.15; design solve OPTIMAL, hard set settled; `cut`
verdicts printed (~574 pairs); LEMD and KCLT byte-identical; ONE OTHH build;
suite twice. Owed: a `Flat` row at every station of a curving ramp (the
kerbs separate past `_STATION_CLUSTER_M` and the monotone chain zig-zags).

## RULINGS

## 2026-09-13bs — ATTRIBUTED (scout `v2othh327`, one OTHH capture on 7949757a, two solved arms, the shipped tile read) and RULED (Fable, spec §11b (7)): OTHH's ramp bumps at 25.253869, 51.603365 are OBJECT FOOT ROWS on the ramp face. The ramp: `tunnel-object:tunnel south west 2.obj@0` (an OBJECT-walled corridor, §33 plates; mouth floor −1.138, crest 3.962, 140.2 m, `design_grade` 3.64 %; OTHH's DEM is a synthetic constant 3.962 — no relief to cross). The owner's point is ramp vertex v5266 (s = 37.55 m, east kerb): the profile runs −1.138 → 0.655 → 1.854 → 1.971 → **3.543** (+3.31 m off its design line) → 3.110 → 2.727 → 3.711 → 3.310 … level at 3.21–3.71 for ~90 m, then the whole 5.1 m drop in the last 50 m at 10–15 %; 12 of 21 monotone `Offset` rows VIOLATED (−0.434, −0.383, −0.401 …), 18 of 351 ramp-cap `Diff` rows violated (worst 4.681 m over 33.6 m vs 2.669 allowed); all 13 of OTHH's in-scope `within_shape tunnel_ramp` rows are this ramp (16.1 … 8.7 % vs 8 %). `--why-at`: the only pins are the mouth floor and three top pins — no wall-plate station pin, no zone band, no road contact; the rows that lose are the ramp's own. WHAT OUTWEIGHS THEM: eight `Linear` foot rows (`constraints/foot_rows.py:107,122-136`, `structures.placement foot_row`, RULINGS 11q, §11b) from the tunnel object's OWN body `tunnel south west 2#b0`, soft equalities at its re-seated ground datum 3.962 (`crest_law: dem`) — every interior local MAXIMUM of the profile is a vertex carrying a foot row at weight ≥ 0.4 (v5266 3.543, v5257 3.711, v5274 3.957), every local minimum one that carries none: the object re-seated to the ground then demands that the ramp its own walls cut stand at that ground. INTERVENTIONAL (`--drop-generator foot_rows`, same tree, same capture): site z − design mean 1.22 / max 3.31 → 0.0 / 0.02; `tunnel_ramp` off-DEM max 5.09 → 1.16 m (99 → 8 of 361 over 0.5); `wall_corridor_ramp` 1.39 → 0.15; the solve `feasible` (91 rounds, 833 flips, 2 hard violated) → OPTIMAL (35 rounds, settled, 0 violated); solver 6.98 → 2.58 s; the no-feet profile −1.138 → 3.962 at +3.52 … +3.88 % every station, z == target to 3 dp, zero cross-fall. SCOPE: 574 of OTHH's 771 foot-row pairs land ≥ 0.2 weight on a STRUCTURE surface (249 on `tunnel_ramp` + `retaining_wall`, 247 on `wall_corridor_ramp` + `retaining_wall`, 33 `tunnel_trench`, 24 `retaining_wall`, 19 `door_ramp`). The shipped tile carries the bumps vertex for vertex (a 1.57 m step across the 28 m carriageway at s ≈ 36, then −0.81 over 12.1, +0.98 over 10.3). LEMD's 7a is `source osm` with n = 2 per station and ZERO foot rows — a different class (LEMD's 38 over-cap `tunnel_ramp` rows are unattributed, milder). A latent weakness named, NOT the cause: past s = 23 the curving ramp's kerbs separate by 1.0–1.6 m along the axis, over `_STATION_CLUSTER_M` 1.0, so no `Flat` row ties the width and the monotone chain zig-zags across kerbs (`structures.py:116, 375, 439`) — harmless in the no-feet arm, owed as a robustness item. Scout housekeeping: one shared-repo write, `o4_dsf_object_positions_+25+051.cache` mtime churn, byte-identical (a pickle read without the env export) — recorded, not contamination.

* FABLE'S RULING (§11b (7)): A FOOT ON A STRUCTURE CUT STATES NO GROUND ROW. A placement foot whose surface sample lands on a structure-cut face — `tunnel_ramp`, `tunnel_trench`, `wall_corridor_ramp`, `door_ramp`, `garage_ramp`, `retaining_wall`, the basin floor — takes a `cut` verdict at the single derivation site (`foot_rows._verdict`, beside `basin` / `pavement` / `padded` / `bare`), counted and reported, emitting NO `Linear`: the cut surface is stated by §33 / §34 and the OBJECT RIDES IT, exactly as §16a rules for a carried body ("cut where its carrier is cut") and §16c (3) for a foot over a structure cut. The self-referential case decides the intent question the scout raised: an object whose walls cut the trench cannot also demand the trench stand at the ground it was cut out of; an object standing at a trench EDGE keeps its crest plate (§16e (1)) and rides the cut with its feet. Lane `v2cutfeet` (pack). Bars (the registered OTHH capture, no build for the bars): `tunnel_ramp` off-design max 5.09 → ≤ 0.05 m; in-scope `within_shape tunnel_ramp` 13 → 0; `wall_corridor_ramp` off-DEM 1.39 → ≤ 0.15; the design solve OPTIMAL with the hard set settled; the `cut` verdict count printed (expect ~574 pairs at OTHH); LEMD and KCLT byte-identical (no feet on a structure cut — prove it); the object stage's seat of `tunnel south west 2#b0` re-read (its crest still flush, 13v); ONE OTHH build; suite twice. Owed beside it: the cross-kerb monotone chain (`Flat` at every station of a curving ramp — the station cluster by axis projection with the width tied).

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently). Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; files under 1,000 lines.
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

