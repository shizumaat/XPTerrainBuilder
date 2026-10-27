# #1138 / #1298 — lane lpackcut handoff (paused by the owner's order, 2026-10-27)

Branch `claude/lpackcut-roofed-tunnels` (PR #1489).  Rulings in force:
2026-10-27l (Q192), 2026-10-27r (Q196), with 26p, 20am/ao/ar/at.  Spec:
`docs/specs/roofed-pack-tunnels-spec.md` §9 (R4, the edge-wall bridge).  Full
measured detail: `docs/findings/1298-1138-lpackcut.md` "Round 4".

## Done
- Merged origin/main (f9ce1d2cb, RULINGS through 27y) into the branch.
- `airport/hanging_objects.edge_wall_reading` / `flush_hanging`: a plated
  hanging object with no hard deck (KATL `tunel_A/B/C`) is an EDGE-WALL
  BRIDGE; `portal_objects.read_portals` returns it as a `Portal` with
  `edge_walls` (deep wall plan segments).
- `planar/structure_mouth.edge_wall_mouth`: the mouth at the NEAREST walls'
  back across the corridor width (changed AFTER the closing build from the
  furthest — see below); `planar/structures` uses it and records
  `Tunnel.span_deck_z` (the ground the top is flush with).
- `planar/covered_span.edge_spans` (new; registered in `pipeline/stage_code`):
  the span between consecutive edge objects over a covered bore is clipped
  into #714's covered ground (`planar/covered_ground`, `cache` now passed from
  `planar/build`).
- `constraints/structures`: `deck_floor`, `_span_deck_rows` (HARD Band rows at
  `span_deck_z` on every terrain deck over such a trench), head
  `bridge.edge_wall_deck_level` added to `law/emit.toml` `hard_rulings` and
  ranked in `hard_conflict_ranks` with `tunnel.mouth_depth_m`.
- Twins: `tests/auto_patch_v2/test_hanging_objects1298.py` (11 pass);
  portal / mouth / stage-code closure / covered-ground tests pass; ratchets
  PASS (lint B905 fixed).  Full non-Qt suite was STOPPED at 29 % (0 failures
  so far) by the pause — not complete.

## Measurements (sources)
- Closing build `lpackcut_katl27r` (/tmp/harness/lpackcut_katl27r.*; built on
  a LOCAL branch `lpackcut-measure-27r` = branch 76b5f7556 + origin/claude/
  lpackpave ca2abf1a2, NOT pushed), census
  /private/tmp/claude-501/lpackcut/r4/census_KATL.txt.  Harness flagged the run
  CONTAMINATED (object stage `pack_rebake` wrote 3 install paths, e.g.
  `Custom Scenery/zOrtho4XP_+33-085/XPTerrainBuilder_+33-085.cfg`); no ledger key.
- Control: lane lpackpave's `lpackpave_KATL` (#1495 alone) in /tmp/harness.
- Owner's site 33.622378944, −84.426822485: 294.13 (#1495 alone; production
  298.24) → 302.99; taxiway beside on the span 302.00–302.28 (0.7–1.0 m under
  the road — the deck level is the pre-solve ground beside the cover, 303.1).
- I-285 trench floors: taxiway-north crossing 277.11 (tunel_C side), 276.80
  (tunel_B side); 10/28 crossing (tunel_A south) 274.10 / 275.62 / 277.21.
  10/28 runway span 301.1–302.1 (unchanged; a 3 m dip at 33.6202, −84.4310 is
  in the control too).
- Census: ADJUDICATED 3,889 → 3,723, airside_for_acceptance 3,366 → 3,136, but
  `strip_transverse` 141 rows, worst 27.22 m `runway|tunnel_ramp` at 33.61987,
  −84.43094 — ATTRIBUTED to the furthest-back mouth: the square mouth's corner
  stood 26 m behind tunel_A south's skewed headwall inside 10/28's span.
- Dry structure records after the nearest-back change (r3 capture
  `/private/tmp/claude-501/lpackcut/r3/KATL.pkl`, probe
  `/private/tmp/claude-501/lpackcut/scripts/probe_structs.py`): −2193@0 moved
  30.1 m in (was 55.7), mouth 8.7 m south of the headwall; the north crossing
  now keeps −2189@0 (deck −3152) as the overlap winner.  Other captures
  (EGGW, EGLL, KBUF, LGAVft, NZWN, LFPG): structure records unchanged.

## Exact next step
1. Run the full non-Qt suite (`venv/bin/python -m pytest -q -n 4 tests
   --ignore-glob='tests/test_qt_*.py'` from `Ortho4XP/`).
2. ONE KATL build of the nearest-back variant on branch + `claude/lpackpave`
   (as above) to confirm the 27 m `strip_transverse` rows are gone and the
   site stays at ~303; report the 10/28-south sites (33.61983, −84.43218;
   33.6208, −84.4282) before/after against `lpackpave_KATL`.
3. Then update PR #1489's body (keep "Refs #1298"; "Fixes #1138" only if the
   bar is met).  The PR body is NOT updated yet this round.

## Open questions / not done
- Service road 0.7–1.0 m over the taxiway (bar 0.05 m): needs a deck level
  from the solved airside, not the pre-solve ground; a relational tie to the
  airside vertex in the edge object's plan was measured worse (300.87).
- Only one of the overlapping parallel carriageways per edge is cut (31h
  overlap; 46 m > the 40 m dual separation); a dry merge of the mouths one edge
  object stops was worse (mouth slid 140 m out, lost the deck) and reverted.
- tunel_A north pins no mouth (bore ends 8–12 m off its plan, tolerance 5 m).
- A mouth line that follows a skewed wall (an exact drop at the back) needs a
  skewed corridor cap.
- EGGW face seat (foot on floor, top on the cover ground): not small (object
  stage, ahead of group zero 22o/q) — not done.
- The contaminated build (pack_rebake install writes) is an object-stage /
  harness matter, not this change.
