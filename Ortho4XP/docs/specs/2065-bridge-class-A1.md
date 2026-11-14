# #2065 A1 — amendment to `bridge-classifier-spec.md` after R1 (Fable review, 2026-11-13)

Amends `docs/specs/bridge-classifier-spec.md` (origin/claude/spec-bridgeclass 2193c1d37).
Read on origin/claude/lbridge1 bfd320042 (R1), origin/claude/lothhdeck2 54220fe81, main deaddf5e8.
Paths under `Ortho4XP/src/auto_patch_v2/`. RULINGS 2026-10-22m/o/p/d, 10-05e, 08-30l, 11-13r.
Evidence: the R1 census (697 rows, 84 airports: 687 from the main run + 10 from the ENAT/PHOG/TNCM
re-read) and four read-only probes on the R1 code over the same plans, feeds and DEM (no build).
R1 census rows: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-frosty-jemison-49af9b/cefbef3f-64e7-4c8d-9220-de7d4ea95540/scratchpad/lbridge1/census2.jsonl`.

## A0. Findings

F1 W6, measured. For every frame with a W-deck, each other body's distance from the bridge region
(group decks ∪ half-width route corridors, as R1 builds it) at the 95th percentile of its plan
vertices; worst body per frame, in metres and in widths of the widest W-deck (w):

| frame | worst body | m | × w |
|---|---|---|---|
| OTHH unit:7 (B02/B03/B06) | `Bridge_0x_CLUTTER_LOD0_001` (lamps) | 0.8 | 0.05 |
| YSSY unit:19 `road3_d` | `road2.obj` | 1.1 | 0.06 |
| OTHH unit:15 (B01) | `Bridge_01_LOD0_003` (abutment / wing walls) | 4.2 | 0.20 |
| LEMG unit:14 `bridgeFunf` | `bridgeFunf-LEMG62` | 9.0 | 0.34 |
| EDDF unit:53 `Bridge_4_hard` | `Tunnel_4.obj` | 30.7 | 0.84 |
| KTUL unit:0 / 1 / 5 | `BRIDGESn_001` | 13.8–24.5 | 1.39–1.48 |
| LFPO unit:5 | `Buildings28partI43` | 36.5 | 2.85 |
| building frames (17) | terminal bodies | ≥ 81.5 | ≥ 6.98 (LGAV), then SCEL unit:85 7.34, KIND 7.74, SEQM 7.93, KPHL 24.6, rest ≥ 17 |

OTHH fails R1's W6 only on the 0.5 m tolerance. In unit:7 no body has more than 3.2 % of its
vertices beyond 1 m. In unit:15, 17 % of two 6–12 vertex bodies stand 3.0 m out, and 7.7 % of
`LOD0_003` stands beyond 3 m (3.1 % beyond 5 m). Every building frame has a body 98–100 % beyond 10 m.

F2 The five R1 false positives are of two kinds, and W4 can refuse neither:
- ROOFS (LSZH `VorfahrtDach` y 13.5–15.4, PHNL `solar1` y 26): the plate IS the top solid; the
  surface that carries the road is another object beneath it.
- PIECES of a longer elevated structure (SCEL `Calle_Piso2` y 8.0 flat, YBBN `trainstation_00_02b`
  y 8.0 flat, VHHH `ROAD` y 14.8 flat; also EBCI `Parkingramp` y 7.0 flat): real driven decks whose
  ends are in the air because the structure carries on past them.

F3 The map separates both. RUN-ON = metres of `bridge≠no` route way carrying on past a plate end
(along the path, then through way joins; probe cap 120 m), per end a / b:

| holds (≤ 11 m) | refused (an end ≥ 28 m) |
|---|---|
| OTHH B02 0/0, B06 0/0, B04 0/0, B01 0/6, B05 0/9 | SCEL Piso2 82/85 |
| KDEN ×12 ≤ 3, except Outer_Train 0/10 | YBBN station 121+/1016+ |
| KLAX ×2, KTPA ×2, KPWA, RJTT bridge6, LIMC ×2, KMCI road-bridge-5: 0/0 | LSZH roof 71/8; PHNL solar 127+/264+ |
| LEMG bridgeDrei 11/8 | EBCI ramp 9/121+; CZNL Nelson 0/121+ |
| KTUL ≤ 6 | LEMG bridgeFunf 63/40; KMCI road-bridge-1 25/29, -2 11/28, -6 22/28 |

VHHH `ROAD` was not re-read (see A6).

F4 The pack separates roofs. Share of stations with an up-facing pack face 2.5–12 m under the
driven layer: LSZH 0.97 and PHNL 0.94 (another frame's surface); LIMC train-traintunel 0.91 / 0.92,
KPHL Trainbridge 1.00, OTHH TerminalRoads_01 1.00 (own frame); every other W-deck ≤ 0.33
(KTUL unit:5 0.33, CZNL 0.31, KSTL 0.29, B01 0.14, B02 0.03, B06 0.04).

F5 Two witnesses tried and REJECTED:
(a) "a pack surface carries on past the end at deck level" fires at both B01 ends (its own approach
    slabs `LOD0_001/002/003`, 3–4 of 4 samples) and at none of SCEL / YBBN / EBCI.
(b) end height over the raw DEM under the authored seat: OTHH B05 3.0–3.9 m and KMCI road-bridge-1
    4.7–5.0 m against YBBN 6.7, SCEL 6.3, EBCI 6.9 — no margin; OTHH's DEM carries no embankment.

F6 Of R1's 34 F decks, 31 stand in all-deck frames (30 single-member frames + YBBN unit:66), which
22d/22p already seat and the owner signed off (KDEN, KMCI, KLAX). The three others are OTHH B04,
OTHH B05 (carries a `split_level` plate) and SCEL Piso2. The frames #2065 is about (deck +
furniture on one anchor: OTHH units 4, 7, 15) are exactly the ones today's all-deck law never read.

## A1. Rules (replace or add to §1)

W6 FREE FRAME (replaces §1 W6). Region as R1: the group's decks ∪ each W-deck's route corridor (half
the plate's width about the route, `fill_road_reach_m` past each end). REACH = max(`[bridge]
free_frame_reach_min_m` 1.0, `free_frame_reach_share` 0.5 × the widest W-deck's width). A body of the
frame is THE BRIDGE'S OWN when at least 0.95 of its plan vertices lie within REACH of the region
(lamp arms, parapets, wing walls, abutment cones, gantries). The frame is free when every other body
is the bridge's own and none stands beside a building (the 22n witness, `planar/deck_bridge.
_beside_a_building` — not a new pad reader). Else `attached_bridge`.
By F1: OTHH unit:7, unit:15, YSSY unit:19 and LEMG unit:14 pass (≤ 0.34 w); EDDF, KTUL, LFPO, KPHL
(≥ 0.84 w) and every building frame (≥ 6.98 w) stay attached. Same outcome as the lane's "1.0 m grow
+ corridor ± plate width" run (`w6_both`), stated as one distance that also holds round a stub.
No airport, pack or resource is named.

W7 ENDS (new). A road deck ends where its mapped bridge ends. At each end of a W-deck's route, the
RUN-ON (F3) is walked along the path and on through every node a `bridge≠no` route way of the FEED
(not only the ways near the plate) continues from. An end with run-on > `[bridge]
free_end_run_on_max_m` (20.0; measured holds ≤ 11, refusals ≥ 28) is a JOINT: the structure goes on
past the plate. A deck with a joint that does not abut a deck of its own group (`[placement]
footprint_touch_m`) fails W7. Every other route end is a LAND END. A stub's ends are its
centreline's: the one abutting a group deck is a joint, the other a land end.

W4b NOTHING DRIVEN BENEATH (new). Refused when, on more than `ROOF_UNDER_SHARE` 0.5 of the stations,
an up-facing face of any pack object — own frame or another, brought to the deck's height by that
object's own authored zero — lies between `[bridge] roof_under_min_m` 2.5 and `roof_under_max_m`
12.0 under the driven layer: the plate is a roof or an upper floor, and the road is on what lies
beneath. Read only for decks that pass W1–W6 and W7; never for a stub.

THE RULE FOR A CANOPY: a plate is a road deck only if (W7) the map's bridge ends at the plate's ends
and (W4b) no pack surface lies a storey beneath it along the route. A canopy, roof, floor, station
or kerbside street fails one of the two. 13r: either failing → today's path.

CLASS ORDER (replaces §1's table order): `stack_deck`, `cut_deck`, `airside_hard_deck`,
`road_overpass`, `all_deck_frame`, then for a deck with W1–W7 + W4b holding: `graded_deck` if
`deck_datum_z` is set, `plated_deck` (new) if it carries an `edge` / `walled` / `split_level` plate,
else `free_bridge`; then `attached_bridge` (W1–W5 hold, W6 fails — whatever W7 says), `graded_deck`,
`not_a_bridge` (reason: the first failed witness, W7 and W4b included).
An all-deck frame keeps 22d/22p and its reader whatever the witness says; the census records
`witness_holds` on its row so the list for question A is to hand.

PIPELINE: the F read runs at the PACK stage (R3's stack must exist before the planar faces). There
W1 reads `highway` / `railway` routes only (a taxiway route is class A's witness), and a plate with
apt.dat pavement or a runway on it (`airport/deck_stack._Airside`) is not read. Stack and cut frames
are `taken` first; `overpass_deck.road_overpasses` takes F decks as `taken`.

ERRATA to the spec:
- the touch key is `[placement] footprint_touch_m` (0.5); there is no `touch_m` key.
- §3 census row 4 is an EDIT, not "unchanged": `airport/deck_stack._rewrite_ways` (592–601) cuts a
  carried stretch by the deck's rotated rectangle, which an OTHH ramp fills to 0.12–0.14.
- `geom/deck_ground._end_length` (50–62) clamps L_e to 2 × `platform_collar_max_m` = 30 m and reads
  `emit.road_contact.ramp_grade`; a free bridge needs its own clamp (A4).
- §7 Q2's default is changed (question B).

## A2. R1's readings, ruled

1 ROUTE CHOICE — CONFIRMED. Best path ranked (passes W1, ribbon cover, bridge metres) over every
  leaf-to-leaf path of each chain (cap 64); ends = the outermost crossings of the plate outline; a
  chain ending within one step inside counts as an end; chain joins only at nodes inside the plate
  + one step (#2035 unchanged). W7's walk is the only read that leaves the plate.
2 W3 LAYERS — CONFIRMED. Faces merged per `deck_flush_m`; a z joins the layer seen most recently,
  then the closest ("the layer running on", 94f9383cc); the surface is the highest-mean layer among
  those on ≥ 0.8 of the stations with both ends; end stations 0.05 m inside; `edge_m` 0.5.
3 W4 WINDOW — CONFIRMED. Solids between `deck_plane_bin_m` (0.5) and `clearance_minimum_m` (4.2)
  over the interpolated layer, on centreline stations, own frame only. It stays the same-frame roof
  test; W4b and W7 carry the rest.
4 W5 — CONFIRMED as built: any highway / railway / waterway way of another chain crossing the route
  between the ends, a water polygon, or ground ≥ 1.0 m under the end chord. Known gap, listed not
  fixed: it does not see the SEA (CYVR BS1 / BS1A, ENAT, TJSJ moscoso fail W5 and stay on today's path).
5 W6 MEASURE — CONFIRMED in form (share of plan vertices, one verdict per frame over all its W-decks
  and joined stubs, corridor = half the mean plate width, carried straight on where the chain
  stops); the tolerance is CORRECTED by A1 W6.
6 STUB — CONFIRMED. `flag` only, failed W1 or W2 only, touches a W-deck at `footprint_touch_m`, W3
  and W4 along `geom/centreline.ribbon_centreline` (the rectangle's axis does not follow a loop
  ramp), width = area / centreline length ≤ 1.5 × the widest W-deck. CORRECTED for R2: the stub's
  axis, stations and layer are kept on its `Witness` (R1 discards them), since its land end is read
  off them.
7 CLASSIFIER INPUTS — CONFIRMED (the readers' outcomes are passed in; the census reads them off the
  plan; a plan before version 12 takes the member origin from its unit anchor). The ORDER is
  CORRECTED by A1.

## A3. Pre-registered census after A1 (gate G0; the NAMED lists are the gate)

| class | decks |
|---|---|
| `free_bridge` (6) | OTHH `Bridge_01_LOD0_000` (unit:15); `Bridge_02_LOD0_000`, `Bridge_06_LOD0_000`, `Bridge_03_LOD0_000` (joins B02; unit:7); `Bridge_04_LOD0_000` (unit:4); YSSY `road3_d` (unit:19) |
| `plated_deck` (1) | OTHH `Bridge_05_LOD0_000` (`split_level`) |
| `all_deck_frame`, witness holds (20) | KDEN ×12 (units 50, 55, 60, 63, 67, 151, 165, 167, 168, 171, 178, 185); KLAX 94, 141; KTPA 50, 66; KMCI road-bridge-5; KPWA 66bridge4; LEMG bridgeDrei; RJTT bridge6 |
| `all_deck_frame`, witness refused (11) | W7: CZNL Nelson, EBCI Parkingramp, KMCI road-bridge-1 / -2 / -6, LSZH VorfahrtDach, PHNL solar1, YBBN trainstation_00_02b, VHHH ROAD (expected, unverified); W4b: LIMC train-traintunel_1 / _2 |
| `not_a_bridge` by W7 (2) | SCEL `Calle_Piso2_Term_New` (or `all_deck_frame` if `frame_is_bridge` counts its `family` member); LEMG `bridgeFunf-LEMG128` |
| `attached_bridge` (42) | R1's 48 less OTHH unit:7 ×3, unit:15, YSSY unit:19, LEMG unit:14 |
| unchanged | `airside_hard_deck` 50, `road_overpass` 25, `cut_deck` 9, `graded_deck` 127 |

Any other deck in `free_bridge`, or any OTHH deck above missing from it, is a STOP: report, do not tune.

## A4. R2 — seat by class (one Opus round, medium; no terrain change)

Base: origin/claude/lothhdeck2 rebased onto main, lbridge1 merged in. Both branches edit
`airport/deck_carry.py` and `planar/overpass_deck.py`: lbridge1's `route_chains` move wins;
lothhdeck2's clearance-at-the-crossing read is kept.

S0 WITNESS A1 (no behaviour change; runs first as its own low-effort lane):
- `law/structures.toml` + `law/model.py` `[bridge]`: `free_frame_reach_share = 0.5`,
  `free_frame_reach_min_m = 1.0`, `free_end_run_on_max_m = 20.0`, `roof_under_min_m = 2.5`,
  `roof_under_max_m = 12.0`, each with the F1 / F3 / F4 numbers in its comment.
- `airport/bridge_witness.py`: `_free_frame` takes the reach; new `run_on` (W7) and `beneath` (W4b);
  `Witness` gains the two ends (point, outward tangent, END LINE = plate outline within half the
  local width of the crossing, top = the W3 layer there, run-on, land / joint) and, for a joined
  stub, its axis, stations and layer.
- `airport/bridge_class.py`: A1 order, `plated_deck`, `DeckFacts.plated`.
- `tools/bridge_census.py`: columns `reach_m`, `run_on_a/b`, `beneath`, `witness_holds`; reads the
  other frames' faces for W4b.
- twins in `tests/auto_patch_v2/test_bridge_witness.py`: lamps 0.8 m off a stub's edge stay the
  bridge's; a wing wall 0.2 w out stays; a hall 7 w out attaches; a plate on a mapped bridge that
  runs 30 m past one end fails W7 and 10 m passes; a group-abutting end is exempt; a roof over
  another object's deck fails W4b and a deck over a crossing deck (short share) passes; the A1
  class order.
- Gate G0: the census equals A3.

S1 THE READ: new `planar/free_bridge.py` (thin, like `planar/deck_stack_attach`) + data in new
`model/free_bridge.py` (`FreeBridge`: id, member ids, decks; `FreeDeck`: object id, ring, carried
way ids between its ends, two `FreeEnd`s, `stub_of`; `FreeEnd`: stations, top, out, land).
`Airport.free_bridges`. Called in `pipeline/build.pack_stage` and `tools/v2_solve_replay.py` right
after `attach_deck_stacks`. One note per deck read or refused, with the witness that decided it.

S2 PUBLISH: `pipeline/rebake_inputs` → the plan member of each free deck carries `plate_kind =
"free"`, `free_bridge` (id), `deck_ends` / `deck_end_stations` = the route end lines (not the
rectangle's), new `deck_end_tops`, `deck_end_land`. `model/rebake.py` field + plan version bump;
`airport/rebake_plan.py` stamps them.

S3 SEAT: `airport/free_bridge_seat.free_bridge_zeros` admits members with `plate_kind == "free"`
only. `_free_deck`, the `_is_the_bridge` call and `bridge_groups` leave this path; one zero per
`free_bridge` id over its land ends (`deck_end_land`). `airport/deck_end_read.deck_end_reads` takes
a free member's end lines and tops as published (no rectangle, no `_plate_top`, no max-y); the 22p
no-embankment reading is unchanged. Every body of the frame takes its bridge's zero as today.

S4 `planar/overpass_deck.road_overpasses`: free decks are `taken`.

S5 `tools/v2_rebake_replay.py plan --bridge-witness` (extension): prints each deck's class and ends.

Consumer census (08-30l) — every reader of `plate_kind` on lothhdeck2:

| consumer | ruling |
|---|---|
| `airport/free_bridge_seat.py` (`PLATED_KINDS`, `_free_deck`) | EDIT: admission by `"free"`; `PLATED_KINDS` stays for the other readers |
| `airport/deck_end_read.py` | EDIT: published ends and tops for `"free"` |
| `pipeline/rebake_inputs.py` (`_edge_seat_plates`, `_deck_plate`, `_unit_members`) | EDIT: publish; a free deck never also gets a deck / overpass plate |
| `airport/rebake_plan.py:389–410`, `model/rebake.py:214, 464, 565` | EDIT: fields, version |
| `airport/airside_deck_seat.py:424` (`_plate_zero`: `deck` / `overpass`) | unchanged; VERIFY `"free"` falls through to no plate zero |
| `airport/anchor_rule.py:615–630` (`walled` / `split_level` / `edge`) | unchanged |
| `airport/cut_deck_seat.py:294` (`deck` / `overpass`) | unchanged; a cut frame is never free |
| `airport/open_frame_seat.py:623, 646` (`walled`) | unchanged |
| `airport/placement_body.py:201`, `placement_file.py:454` (`split_level`) | unchanged |
| `airport/placement_plan.py:1006` | EDIT: the call keeps its guards (airside, refused bridge, cut, floor) |
| `airport/placement_coherence.py`, `written_seat_census.py`, `tools/seat_feet_census.py`, `tools/drawn_site.py --end-lines` | EDIT: read the published route ends |
| `planar/overpass_deck.py`, `planar/deck_bridge.py` | EDIT `taken` / VERIFY no free deck is class A |
| `pipeline/stage_code`, object-stage code keys, closure twins, `test_no_airport_specific_code` | as the twins say |

Bars:
1. G0.
2. Object-stage replay of OTHH units 4 / 7 / 15 on the lothhdeck2 plan (`v2_rebake_replay.py plan
   --sampler graded`): interchange (B02 / B03 / B06) ONE zero within 0.15 of 4.12; B01 zero within
   0.15 of 0.40; B04 ends within ±0.10 (lothhdeck2c read +0.09 / +0.07); no bridge body buried > 0.5.
3. Corpus mover replay: every airport's plan replays body for body except the frames of the six A3
   free decks. YSSY unit:19 is listed with its predicted seat change (> 0.5 m needs the master's read
   before landing). The KBNA / KDEN / KMCI / KLAX sign-off sites are identical.
4. Closing: ONE build — `build_airport.py OTHH --tile 25 51 --pack-copy --texture-mode
   default_xplane` — then `drawn_gate.py OTHH --tag T --against <control .drawn.json>` with
   `--site b01_n=25.255961,51.616827,40 --site b01_s=25.255355,51.616856,40
   --site b02_s=25.250232,51.616103,40 --site b02_n=25.253714,51.617281,40
   --site b06_sw=25.250572,51.616200,40 --site b06_n=25.253623,51.616497,40
   --site b03_stub=25.251608,51.617077,40 --site b04_s=25.251211,51.620195,40
   --site b04_n=25.251875,51.620457,40`.
   PASS; MOVED only on objects of units 4 / 7 / 15; patch→drawn ≤ 20 / 46,313. Far-end gaps are
   listed, not barred (R3).

Build time: W7 and W4b are read only for decks that passed W1–W6 (R1: median 77 ms per deck).

## A5. R3 — grade-up, incl. the B03 stub weld (one Opus round, high)

As spec §3 (a free bridge = a deck stack with no floor), with these rulings:

1. WHICH BRIDGES: one free stack per `FreeBridge` whose zero is a flush land end (22m). A bridge
   that keeps its authored clearance (22p: no embankment at either end) mints nothing and is listed.
   All-deck frames are not free (A1) and mint nothing.
2. ZERO: pre-solve, max over land ends of (G_e − top_e), G_e = `airport/deck_stack._end_ground` one
   step beyond the end line along `out_e`.
   GATE G1, before any other R3 code: on an OTHH capture this pre-solve zero is within 0.15 m of R2's
   drawn zero for B01 and for the interchange. If not — the raw DEM at B01's end lines reads only
   +0.9 … +1.6 m over the DEM at its anchor, and the solve may draw the ground there differently —
   STOP and report; do not tune.
3. ENDS GRADED: an apron at each land end with gap > `deck_flush_m`. Length = gap / the design grade
   (`emit.road_contact.ramp_grade`, 5 %) + one step, at most `fill_road_reach_m` (100 m). Where
   another region cuts the run short (airside, a pad, another deck's shadow, the patch edge) the
   grade steepens to the smallest that closes the gap, never above `[tunnel] ramp_max_grade`
   (10 %; 10-08c / d). An end the ramp cannot close gets NO apron and is listed
   (`far_end_beyond_reach`, `far_end_outside_patch`, `far_end_on_water`, `far_end_on_airside`).
   No partial ramp (question B).
4. THE WELD: the first `abutment_sample_step_m` of every apron (the slab) and the end line itself are
   held in [zero + top_e − `deck_flush_m`, zero + top_e] (R1), at every graded end, far ends
   included. The bank beside the apron falls at `emit.design.bank_slope` to the DEM, its toe pinned (R4).
5. THE STUB (B03 south end, 25.251608, 51.617077): its land end is the centreline end that abuts no
   group deck; end line and top (2.48 authored) from its kept stations and layer; `out` = the
   centreline's outward tangent. It has no route, so no road ramp is seeded: the apron and its slab
   are the weld. Its other end is a joint with B02: no row, no apron.
6. UNDER THE PLATE: a ceiling only (R3: zero + plate y − `deck_flush_m`, the plate's own triangles
   by `floor_z_at`); the ground under a ramp is never raised to it.
7. CARRIED WAYS between the ends become bridge stretches by the plate's RING (erratum); B06's 216 m
   of untagged way −5650 stops being a terrain road.
8. OBJECT STAGE: the plan member carries `(top of the governing end, that end line's stations, 0.0,
   "free")`; `free_bridge_seat` reads the zero off the drawn surface there, so seat and terrain
   agree by construction.

Consumer census (08-30l) — every reader of `Airport.deck_stacks` / `DeckStack` on main:

| # | consumer | ruling |
|---|---|---|
| 1 | `model/deck_stack.py` (`DeckStack`, `StackDeck`, `sidecar`) | EDIT: `kind` ("trench" default / "free"), `StackDeck.out_a/out_b` default None, floorless legal (floor, rim, runouts, caps empty) |
| 2 | `airport/deck_stack.stack_floors` (513) ← `planar/object_floor_cells.py:190` | EDIT: skip a free stack (no floor, no void band) |
| 3 | `airport/deck_stack._stack_shade` (564) | VERIFY a free stack's shade is its plates |
| 4 | `airport/deck_stack._rewrite_ways` (592) | EDIT: a free deck's stretch by its ring |
| 5 | `airport/deck_stack.attach_stacks` (604) | EDIT: free stacks appended after trench stacks; the no-stack return also holds with only free stacks; idempotent on `osm_ways_mapped` |
| 6 | `geom/deck_ground.py` (`_deck_rect` 44, `_end_length` 50, `_beyond` 65, `end_aprons` 85, `_deck_zone` 94, `ground_footprint` 113) | EDIT for `kind == "free"`: shadow = the plate's ring; apron along `out_e`; ruling 3's length; no caps; empty keep; aprons only at graded ends; no bank beside the deck's side edges |
| 7 | `planar/stack_ground.py` (`stack_ground_pieces` 50, `deck_end_road_zone` 98), `planar/overlay.py:372` | unchanged; VERIFY a free piece outside the aerodrome's zone bands is minted and solved |
| 8 | `constraints/deck_stack.deck_stack_rows` (77) | EDIT: free = R1 at graded ends + R3; no R2; R1 only on non-airside, non-structure vertices |
| 9 | `model/deck_ends.end_road_vertices` (30) → `airport/deck_ends.deck_end_seeds` → `airport/road_ramp.py:2026` | EDIT: for a free deck only vertices of its CARRIED ways; trench stacks identical |
| 10 | `constraints/fill_bank._stack_toe` (39) | unchanged; VERIFY the free aprons' toe is pinned |
| 11 | `pipeline/publication.py:1413` | EDIT: a floorless stack publishes a `free_bridges` sidecar row (id, zero; per end: stations, top, G_e, land, graded or listed + why, length, grade) |
| 12 | `tools/drawn_check.py`, `tools/drawn_site.py --end-lines` | EDIT: read `free_bridges` |
| 13 | `pipeline/build.py:399–403`, `tools/v2_solve_replay.py:696, 2254` | unchanged callers; the log line counts free stacks |
| 14 | `planar/deck_bridge`, `structure_underpass`, `planar/channel`, `planar/channel_claims.py:345`, `constraints/structures.py:905` | unchanged (their `floor_ref` / `wall_ref` are basins' and channels'); VERIFY |
| 15 | zone / strip / groundside generators | unchanged; VERIFY no row names a free stack-ground vertex alone |
| 16 | emit, verify, `check_grade` (`LAW_FAMILIES`) | unchanged; VERIFY new rows only within 150 m of a graded end |
| 17 | object stage (`free_bridge_seat`, `deck_end_read`, censuses) | EDIT: ruling 8 |
| 18 | tile mesh, `terrain_cut_stage` | unchanged |
| 19 | `pipeline/stage_code`, closure and registry twins, `test_no_airport_specific_code` | as the twins say |

Heightfield: every new surface is single-valued; the slab meets the plate edge at one height; the
ground under a plate stays under it.

Twins (`tests/auto_patch_v2/test_deck_stack1971.py`): floorless stack; curved plate (ring, not
rectangle); carried-ways-only R1; stub end (no route) welds; a 22p bridge mints nothing; an end
beyond reach mints nothing; steepening on a short run; apron cut by a crossing road; water end;
KDEN's stack byte-equal.

Bars:
1. G1.
2. `v2_solve_replay.py --replay --from classify --verify --emit` on an OTHH capture, with the
   PREDICTED drawn check written down first.
3. KDEN stack byte-identical in planar replay; KBNA / KMCI / KLAX sign-off sites identical.
4. Closing: ONE OTHH build as R2, sites as R2 with radius 120 at the far ends (`b02_n`, `b06_n`,
   `b03_stub`, `b01_n`, `b01_s`) and `--against` R2's closing `.drawn.json`:
   - every land end of B01 / B02 / B03 / B04 / B06 within ±0.30 of the drawn surface one step beyond
     it (near end flush, far end graded);
   - B03 stub welded (drawn ground within `deck_flush_m` + 0.05 of its end top across the end line);
   - B06 SW tip included;
   - interchange zero within 0.15 of 4.12; B01 within 0.15 of 0.40; B04 ends ±0.05;
   - no bridge body buried > 0.5; patch→drawn ≤ 20 / 46,313;
   - MOVED only on terrain inside the published aprons and objects of units 4 / 7 / 15.

## A6. Risks and what is not verified

- VHHH `ROAD` (R1: F, way −9021, y 14.8 flat) could not be re-read: the tile feed returned no route
  in the probe and DEM N22E113 is missing. A3 expects W7 to refuse it; G0 decides.
- PHNL: DEM N21W158 missing (W5 ground unread; W7 and W4b measured).
- W6's building test (`_beside_a_building`) is not read offline; the census reads containment only.
- W4b brings other frames to the deck's height by DEM at each anchor + the unit's AGL (about ±2 m):
  fit for a storey window, not for a tight one.
- YSSY `road3_d` is the one free deck outside OTHH: a ramp deck rising 1.6 → 8.8 m to an elevated
  road. Its low end seats flush; its high end stands about 6.8 m over the raw DEM, beyond reach, so
  R3 lists it and builds nothing there.
- B01 and the interchange zeros (0.40, 4.12) are lothhdeck2's drawn reads, not re-measured here.
- Real bridges the witness refuses stay on today's path and are listed: KTUL ×3 (their second body
  reaches 1.4 w), KPHL Trainbridge, LEMG bridgeFunf and CZNL Nelson (the mapped bridge is longer
  than the plate), EDDF Bridge_4, the sea-crossing bridges (W5), KSEA unit:16 (W3 0.48).
- The seven R1 interpretations ruled in A2 are those visible in the code; the lane's own list was not
  on the branch.

## A7. Owner questions (defaults applied unless the owner rules otherwise)

A. All-deck bridge frames that hold the witness (20 decks: KDEN 12, KLAX 2, KTPA 2, KMCI 1, KPWA 1,
   LEMG 1, RJTT 1) keep today's seat. Grade the terrain up to their far ends too?
   (a, default now) no — list their end gaps; (b) decide after the OTHH sim read; (c) include them now.
B. A far end the ramp cannot close: (a, default) build nothing there and list it; (b) build the ramp
   as far as it goes and list the step.
C. (default) One OTHH sim read after R3; R2's seats are checked on the drawn mesh by the gate.
