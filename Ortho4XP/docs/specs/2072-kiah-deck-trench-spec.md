# #2072 / #1902 — hard-deck trench spec (round 2, last Opus round)

Fable review of round 1 (claude/lkiah2072 37683bfe6), 2026-11-14. A miss goes to the owner.
Base: `claude/lkiah2072` 37683bfe6, merge main first. General rules only; KIAH is the test case.

## Verdict on round 1
Keep it (`edge_deck._span_rows` own-ground hulls, `design_ground._deck_ground_vertices`,
`edge_deck.deck_floor(air_roles=)`). The remaining defects sit in the planar stage and in the floor's row model.
Round 1's capture was not registered; all its numbers are unverified (code-checked only).

Attribution checks:
- (a) dead-end trenches clipped at taxi pavement: consistent (`planar/structures.py:1006-1050`, refusal `:1043-1047`;
  only runway pavement gets a wall, `deck_uncut` `:408`, `deck_bridge.deck_cut(uncut=, rim_off=)` `:628-690`).
- (b) floor at the 5 m bound "fixed in stage 1": NOT confirmed (`solve/design_stage.py:66-76`). A ladder deck's floor has
  no level row, only a one-sided ">= 5 m under the seats" row (`constraints/structures.py:589-605`) and a soft target at
  `mouth_z` (`planar/structure_geometry.py:386-392`). Pinning the floor removes the stage question.
- (b) ramp-top step: consistent; `deck_bores.deck_lanes` (`:136-170`) splits lanes by separation only
  (`dual_carriageway_max_separation_m` = 40); one corridor has one flat level per station (`constraints/structures.py:446-449`).
- (c) void draws base DEM: consistent (`deck_bridge.py:675-681`, `emit/graded.py:20-24`).
- Also: between two decks the floor target is flat per half while the rows are linear (`edge_floor.sloped_floor_rows`): a
  step at the midpoint wherever the two floors differ.

## Principle
A hard-deck trench is self-contained: its floor is a level set before the solve, it never touches airside pavement, each
road has its own run-out, and none of its ground is left to the DEM.

## Rules
**A. A trench never ends on airside pavement** (2026-10-30a (2); 2026-11-03b (2); `bore_continuation`'s witness).
Where a hard-deck trench's run-out is stopped by airside pavement no deck ring carries, and the strict refit at
`ramp_max_grade` cannot top out before the stop:
- A1: the open stretch is level at the floor up to the stop (`climb_from` = the stop; no ramp, no top pin).
- A2: that pavement joins the corridor's `uncut`: rim on the pavement edge, floor stops `rim_off` short, the void between is the wall.
- A3: such a trench is never refused "the mouth stands against pavement". No far mouth is opened.

**B1. The floor under a ladder deck is a pinned level.** Every datum station group of a trench with
`deck_floor_min_m > 0` is pinned (senior, source `DECK_FLOOR`) at the value `ramp_targets` gives it. `ramp_targets`
becomes linear on `Tunnel.edge_floor_s` between two decks' floors (2026-10-28u Q271 (b)), so target and pin are one
number. The one-sided seat row is no longer minted for these trenches; a clearance shortfall is reported in
`publication.tunnel_mouth_depths`, never a row (#1903: the cut never lifts airside).

**B2. Lanes by level.** Two neighbouring mouths on one deck side are one lane only if within
`dual_carriageway_max_separation_m` AND their own roads' ground beyond the deck differs by <= 0.5 m (median DEM along each
mouth's parent road, from deck edge + gap, over one design ramp length; 0.5 m = owner ground bar 2026-10-15; reuse a law
key carrying it, else add `[tunnel] lane_level_tol_m`). Each lane tops out on its own road. If two lanes' rings overlap
and `structure_overlap` refuses, report the refusal; do not work around it.

**C. No void wider than a wall band inside a deck's reach.** In `deck_cut`'s wall-less branch, `outer` takes the floor
only; the rest of the ring is left unowned so `deck_ground` mints it as `deck_ground:<oid>#k`, head span-held at deck
level, toe on the (pinned) floor vertices: the patch draws the 2026-10-30b bank. Walled decks (`_walled_trench`) unchanged.

## Consumer census (RULINGS 2026-08-30l)
| Consumer | Reads | Ruling |
|---|---|---|
| `planar/structures.py` clip loop `:1006-1050`, refusal `:1043-1047` | stops | A1, A3; call sites only (logic in `deck_bores.py` / `deck_bridge.py`) |
| `deck_bridge.deck_cut` `:628` | `uncut`, `outer` | A2, C |
| `deck_bridge.deck_ground` `:767` | reach less taken | unchanged; mints C's bands |
| `structure_geometry.ramp_targets` `:350` | `mouth_z`, `edge_floor_s` | B1 linear stretch |
| `constraints/structures.py` `:570-650` | ladder branch | B1 pin, no seat row |
| `deck_bores.deck_lanes` `:136`, caller `structures.py:382` | mouth order | B2 |
| `edge_deck._span_rows`, `_bridge_ground` | deck-ground faces, floor roles | unchanged; toe skipped as floor, head spanned — twin |
| `edge_deck.deck_floor` + `walled_plate.release_across` | floor / trench sets | unchanged; report count of rows withdrawn between toe and head |
| `solve/design_ground._deck_ground_vertices` | deck-ground vertices | unchanged |
| `solve/design_stage.stage_split`, `pin_yield.stage1_read_pins` | columns, pins | twin: no floor vertex shares a column with an airside vertex; stage 1 reads no floor pin |
| `pipeline/shapes.apply_joints` `:133` | `DECK_FLOOR` rows | unchanged |
| `planar/ribbons` | free area | none in a void; twin for A |
| `emit/graded.rim_runs`, `osm_adapter` | void rings | unchanged; band emitted as `graded_strip` |
| census `check_grade` families | emitted rings | must price no row on `deck_ground:*`; else exempt like `fill_bank:` / `stack_ground:` (`model/planar.py:139-150`, `constraints/fill_bank.py:62`) with a twin |
| `publication.tunnel_mouth_depths`, `rebake_inputs._deck_plate` | floor, stations | add clearance note; plate unchanged |
| `tools/drawn_check.py`, `harness/drawn_gate.py` | drawn mesh | new road layer (step 5) |

## Steps
0. Replay first: capture KIAH and register it in frames. On the round-1 tree print per deck the floor group's column, any
   airside vertex in it, and the top-station pin with its ground — first lines of the report.
1. Rule A + synthetic twin (deck, road, pavement stop 12 m out): level floor, wall on the pavement edge, no floor vertex in an airside column, not refused.
2. Rule B1 + twins: pin equals target; no seat row; linear between two decks; a low deck solve lifts nothing.
3. Rule B2 + twin: trunk pair + a road 4 m higher → two lanes; a dual 0.2 m apart stays one.
4. Rule C + twin: no void point inside the reach farther than `wall_gap_m + wall_band_width_m` from a wall; band is `deck_ground` with toe on floor vertices.
5. Extend `drawn_gate.py` (do not fork): `--road-step M` (default 0.5) samples the drawn mesh each 1 m along every mapped road within a site's radius and FAILs above M. INDEX row + twin in the same commit.
6. Replay controls, no build: LFPG `lfpg6`, KBNA `kbnafix` with `--replay --from planar`: deck stations within 0.01 m of base; floors within 0.3 m; list any lane change.
7. One closing build.

## Bars (drawn mesh, closing build)
- Roads: on every road within 150 m of each of the five decks, max step between consecutive 1 m samples <= 0.5 m.
- obj24551 (29.987353, -95.330258): deck top − floor under the deck >= 5.0 m and within 0.3 m of `Tunnel.depth_m`; both slots at floor level up to the wall.
- Airside: every end-line station of the five decks within 0.05 m of its `DeckAnchor.z_m`; deck flush within 0.04 m (2026-10-30a (1)).
- No spike: nothing drawn inside a deck's reach above the deck top by > 0.04 m; within 60 m of the site nothing > 0.5 m over both DEM and deck top.
- `drawn_gate` PASS at the five sites (deck centroids from `PlanarMap.decks`), no MOVED outside them against the control.

## Owner decisions (intent; defaults applied unless the owner rules otherwise)
1. obj24551 look: (A, default) an open slot ~12 m each side at road depth ending in a vertical face at the apron, road hidden under the apron; (B) no cut, ground flush. Full bore to the far end is a later issue.
2. Under-deck sides: (A, default) sloped banks per 2026-10-30b; (B) vertical abutments at the road edge with a flush shelf (reverses "there is no vertical wall").
