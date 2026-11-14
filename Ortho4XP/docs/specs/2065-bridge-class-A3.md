# #2065 A3 — R3 rewritten: grade the terrain up to every bridge end (Fable, 2026-11-14)

Replaces `2065-bridge-class-A1.md` §A5 and §A7 A / C; corrects A2 B1 ("R3 mints free stacks from
`PlanarMap.free_bridges`"). Read on origin/claude/lbridge4 4213db958 (R2, batch 21); RULINGS
2026-11-14d / e / f, 10-28k, 10-22m / p, 08-30l, 10-05e; the 53-end survey
`/private/tmp/claude-501/bridgeends/res2.txt` + `res3.pkl` (AUTHORED DEM: a list of cases, never a
gate); R2's drawn end reads `.harness/frames/lbridge4/arm_endreads.txt`. Paths under
`Ortho4XP/src/auto_patch_v2/`. ONE Opus round (high) on main after batch 21. A miss goes to the owner.
Never raise the lane cap; delete your scratch builds when you report.

Master's notes on the spec author's four flagged departures (accepted): (1) the free-bridge zero is
fixed before the solve on `airport.dem` and every land end is held to it (#1971 pattern); G1 records
the difference from R2's drawn zeros, not a STOP; (2) all-deck seats are kept by a shield (predicted
seat), a residual step at a graded kept end is listed (bar ±0.30); (3) plated B05 is listed, not graded
(owner Q3); (4) KMCI road-bridge-5 a is held at the planar stage (`end_on_lot`); if no general predicate
separates it, that is a finding for the owner, not a switch.

## C0. Findings
F1 The seat's zero is not known before the solve. R2 seats the interchange flush on DRAWN ground 5.70
   at B06's SW end (zero 6.14); its other ends read 3.95-4.88, B01 3.96 / 2.62; the authored DEM reads
   0.68-4.55 at the same ends. A1 rule 2 (zero from the DEM) and rule 8 (seat re-read on the drawn
   ground) agree only where the solve leaves the governing end on the DEM. #1971 fixes the zero before
   the solve and holds EVERY end line to it (R1; KDEN lkden3: written zero 1626.531 = solved).
F2 The road ramp exists. `airport/road_ramp.road_ramp_targets(deck_ends=)` (:743, :938-946) seeds the
   road at a deck end; `road_descent.descend` runs it at 5 % along the walked route. No length cap
   was seen in road_ramp :938-1010 (`road_descent` itself was not read). `fill_road_reach_m` capped only A1's APRON.
F3 A railway has no ribbon (`classify/ribbon_mint._ribbon_ways` :320: `highway` classes only).
F4 A road is patch ground only inside `ribbon_mint.road_extent` (:84, called :518): the aerodrome
   boundary + `boundary_reach_m` 50 m and the airside envelope. KDEN Outer_Train_Bridge b and KPWA
   66bridge4 a meet the patch edge 1 m out.
F5 All-deck frames are not read by the witness (`planar/free_bridge.py:189`). Their seat
   (`anchor_rule.py:717` -> `bridge_approach.approach_seat`) reads BOTH rectangle end lines on the
   drawn surface: ground raised at a far end flips a 22p bridge to 22m (:140-141) or takes the max (:148).
F6 The survey's obstructions, by kind: another frame's pack solid on the path (LEMG a 1 m, KTPA South
   b 19 m); the mapped route stops (KDEN Garage x4 b 0-0.7 m, KLAX Bridge_T1 b 16 m); a lot (KMCI
   road-bridge-5 a); airside (YSSY b, 32 m of 137); another deck over the path (KLAX Road_Bridges a
   at 106 m, KDEN Parking_Hill 31309 b at 3 m); at-grade crossings (KDEN 31316 a, RJTT a); a stub (B03).
F7 `free_bridge_seat._bridge_zero` (:122-124) and `deck_end_read._walked` (:147-148) drop an unread
   end silently.

## C1. Rules
1 WHICH BRIDGES. Every deck holding W1-W7 + W4b on `airport.dem`: the free bridges, and (14d) the
  decks of all-deck frames. `_read_free_bridges` reads all-deck frames too and keeps them on new
  `Airport.kept_bridges` (the `FreeBridge` record): never `plate_kind = "free"`, never `taken`, their
  seat readers untouched. A `plated_deck` (OTHH B05) is listed and nothing is built (Q3). No distance
  test anywhere (14f (1)).
2 THE ZERO, two modes, fixed at the pack stage and never re-derived.
  FREE: R2's rule (`_bridge_zero` over `deck_end_reads`) on a DEM surface: highest `G_e - top_e` over
  land ends, a 22p clearance one candidate. `G_e` = `deck_stack._end_ground(airport, stations, out_e,
  free_end_ground_out_m)` (:244; A2's chord, 1.5 m out). The terrain is then held to it at every
  land end (rule 5).
  KEPT (all-deck): today's reader (`approach_seat`: rectangle ends, `datum.y`, 22p) on the same DEM
  surface = the PREDICTED seat. The governing end and a 22p anchor get no row and no ground.
  Both stages call the SAME functions through a member-shaped view of the pack object (the fields
  `rebake_plan` :349-410 / `with_free` :423 stamp); no second implementation of a zero.
3 END STATES, read once per land end at the pack stage (`airport/bridge_witness`), published.
  gap = zero + top_e - G_e. PATH = the carried way outward from the end, then through way joins by
  the straightest continuation (road or rail); a stub's path is its axis ray. g = `ramp_grade` 5 %
  (road, stub) or `[tunnel] rail_ramp_grade` 1.25 % (rail, 10-28k; Q2). RUN = gap / g +
  `abutment_sample_step_m`. The nearest obstruction within max(RUN, the end line's length) decides:
  - FLUSH: gap <= `deck_flush_m`.
  - HELD (14f (4); built as today): `end_at_pack_solid` — a non-deck solid of ANOTHER frame, standing
    >= `[bridge] end_solid_min_height_m` (new, 2.0) over >= `end_solid_min_area_m2` (new, 10.0; the
    survey's values); `end_route_stops` — a routed deck whose path ends before RUN; `end_on_lot` — the
    path enters a gap-mint lot piece (PLANAR stage, beside `admitted`; see C5).
  - LISTED (question B's default: nothing built): `end_on_airside` (`deck_stack._Airside`; never
    altered); `end_under_low_deck` (rule 8); `end_on_water`; `end_beyond_reach` (a STUB over
    `fill_road_reach_m` 100 m: 14e lifts the cap only where a road or rail is followed); `end_off_dem`.
  - GRADED: every other end. A1 rule 3's steepening is struck (`road_descent` keeps its own).
  A bridge mints a stack only if it has a GRADED end; otherwise nothing of R3 touches it.
4 GROUND (`geom/deck_ground`, `kind != "trench"`). APRON = the path's first RUN metres buffered half
  the end line's length, flat caps (it follows the road; no length cap, 14e); its first step is the
  SLAB. BANK = the apron grown by max(`bank_min_width_m`, gap / `bank_slope`), toe pinned (R4). No
  bank beside the deck's sides, no caps, no floor. FREE: a FLUSH end gets the slab alone.
5 ROWS (`constraints/deck_stack`, all under `edge_deck.RIGID`; no new head). R1 [zero + top_e -
  flush, zero + top_e] on the end line, the slab and the end-line road vertices — FREE: every land end
  not held or listed; KEPT: GRADED ends only. R3 (ceiling under the plate) FREE only. R6 PROFILE
  (new): a corridor vertex at path distance s that no road ramp owns stands in [P(s) - `visual_m` / 2,
  P(s)], P(s) = zero + top_e - g (s - step); dropped where P(s) <= DEM + flush. Never on an airside
  or structure vertex.
6 THE ROAD. Road end: the ramp is the carried road's (`deck_end_seeds`; F2). Rail and stub ends: R6
  is the ramp. An at-grade road crossing a corridor is seeded at P(s) through the same `deck_ends`
  map (14f (3)). RESULT REQUIRED where the path runs on groundside pavement with no ribbon (OTHH B02
  N, B06 N, B04): the pavement inside the corridor follows P(s). The lane's seam probe rules whether
  the apron cuts that cell or the cell's vertices take R6; G2 is the bar.
7 EXTENT AND WAYS. `road_extent`'s reach gains each stack's ring, aprons and banks grown by
  `boundary_reach_m` (ONE site, 08-30l): the carried ways are ribboned there, and the exit law and
  the coverage join (`emit/road_join`) fall beyond the ramp's landing. `_rewrite_ways` (:601), for a
  stack with a GRADED end: a carried stretch inside the plate's RING not already `bridge != no`
  becomes a bridge stretch (B06's way -5650); the run-on of a bridge way past a GRADED end (<=
  `free_end_run_on_max_m`) becomes at grade, or no ribbon exists to seed.
8 ANOTHER DECK ON THE PATH (14f (2)). A deck of another bridge whose ring holds a path station
  within RUN: its underside there (its stack zero, else DEM at its anchor + `agl_m`, + its plate) less
  P(s) >= `[bridge] clearance_m` (5.1) -> the ramp runs UNDER it, no weld, no row of that deck; less
  -> `end_under_low_deck`. Decks and bodies of the bridge's OWN frame (B01's approach slabs) are the
  bridge: the ground stays under them (R3). A way at another `layer` / `bridge` / `tunnel` is never
  seeded or graded (14f (3): the structure passes own it).
9 OBJECT STAGE. FREE: R2 unchanged; every R1 end reads the zero. KEPT: the plan member gains
  `deck_end_graded` (per rectangle end, matched to the route end by nearest midpoint; plan v15);
  `approach_seat(graded=)` leaves a graded end out of the embankment test and the max, so the seat is
  today's. The step left at a graded KEPT end is the prediction error; it is listed.
10 ONE-END ZERO (F7). `_bridge_zero` never drops a land end silently. An unread land end of a bridge
  with a stack is counted `free_end_unread` and noted (the terrain holds its ends); with no stack the
  bridge is REFUSED as free (13r: today's path) and listed.

## C2. Consumer census (08-30l) — changes to A1 §A5's table; rows not named stand
| consumer | ruling |
|---|---|
| 1 `model/deck_stack.py` | EDIT: `kind` trench / free / kept; per end: state + why, path, run, grade |
| 4 `deck_stack._rewrite_ways` :601 | EDIT: rule 7; trench stacks identical |
| 5 `deck_stack.attach_stacks` :613 | EDIT: free and kept stacks minted at the PACK stage (classify needs them); corrects A2 |
| 6 `geom/deck_ground.py` :41-147 | EDIT: rule 4 |
| 8 `constraints/deck_stack.py` :77 | EDIT: rule 5; the `floor_vs` skip (:96-98) is the trench's only |
| 9 `model/deck_ends.end_road_vertices` :30 | EDIT: carried-way and crossing vertices (rule 6) |
| 11 `pipeline/publication.py` :1413 | EDIT: `free_bridges` rows: id, mode, zero; per end: stations, top, G_e, gap, state, run, grade, apron |
| 17 object stage | EDIT: rules 9, 10; `model/rebake.py:43` 14 -> 15 |
| N1 `classify/ribbon_mint.road_extent` :84 | EDIT: rule 7 |
| N2 `planar/free_bridge._read_free_bridges` :189, `admitted` :217 | EDIT: kept bridges; cut / hard-deck tests on them; a refused bridge's ground is dropped, counted `free_stack_refused_at_planar` (a STOP on OTHH, KDEN, YSSY or a sign-off replay) |
| N3 `emit/road_join`, `constraints/road_ramp` join, `geom/coverage.py:30` | unchanged; VERIFY no join pin on a ramp vertex and that an island of faces emits |
| N4 `planar/structure_approach` (`ROAD_REACH_KEY`) | unchanged; VERIFY a reach ribbon is seeded |
| N5 `bridge_approach.approach_seat`, `anchor_rule.py:717`, `deck_end_read.py:184` | EDIT: `graded` |
| N6 core mesh (road levelling removed inside coverage + 6 m) | unchanged; VERIFY at KDEN train_b |
| N7 `tools/bridge_census.py`, `drawn_site --end-lines`, `drawn_check` | EDIT: `--ends`; read the rows (INDEX rows, twins) |

Heightfield: every surface single-valued; a ramp under another deck is ground under a deck.

## C3. Twins
`test_deck_stack1971.py`: floorless free and kept stacks; apron follows a curved way; RUN 300 m is
not capped and a stub at 101 m is listed; rail end takes R6 at 1.25 %; an at-grade crossing in a
corridor is seeded; pass under a deck at 5.1 m and listed at 5.0; each HELD / LISTED witness; a bridge
with no GRADED end mints nothing; untagged stretch rewritten, tagged untouched, run-on at grade;
KDEN's trench stack byte-equal. `test_free_bridge_seat.py`: a kept 22p bridge with both ends graded
keeps its clearance; a kept 22m bridge with its far end raised keeps its seat; rule 10 both ways.
`test_bridge_witness.py`: path walk; solid thresholds. Ribbon twin: the reach holds a bridge 2 km out.

## C4. Gates — production DEM before the build, drawn mesh after (A2)
G0 Before any terrain code: `tools/bridge_census.py --ends` on `v2_solve_replay.py --capture` of OTHH,
   KDEN, KLAX, KMCI, KTPA, LEMG, KPWA, RJTT, YSSY (no build): one row per land end (rule 3), kept as
   frames. Bars: E3's 6 free + 20 kept decks present, B05 listed; each of LEMG bridgeDrei a, KTPA
   South_Bridge b, YSSY road3_d b, KDEN Garage_Bridge x4 b (obj31305-31308), KMCI road-bridge-5 a
   (planar stage: G2) is HELD, LISTED or FLUSH — one GRADED is a STOP. Other held ends are reported.
G1 OTHH zeros written down beside R2's drawn zeros (B01 0.385, interchange 6.14, B04 -0.64). Not a
   STOP: the terrain holds the ends. A difference over 0.5 m heads the report (the seat moves by it).
G2 `v2_solve_replay.py --replay <capture> --from classify --verify --emit`, OTHH and KDEN, the
   predicted end table written first: every R1 end's ground within [-0.09, +0.05] of zero + top_e;
   R6 vertices in band; no infeasible row; KDEN's trench stack node-equal to the base replay. KBNA,
   KMCI, KLAX replays: bridge-frame seats identical to base; emit identical outside published
   footprints (KBNA and KMCI: everywhere). A KMCI change is never landed without the owner's word.
G3 Closing, at most three tile builds, A2 P5's order (control first, arm the last writer of `Patches/`):
   OTHH `build_airport.py OTHH --tile 25 51 --pack-copy --texture-mode default_xplane`, then
   `drawn_gate.py OTHH --tag T --against <control>` with A4's nine sites, radius 120 at b02_n, b06_n,
   b03_stub, b01_n, b01_s. Control: `frames/lbridge4/lb4arm3.drawn.json` if the base's patch-only
   body equals that frame's, else a control build. Bars (drawn): every land end of B01 / B02 / B03 /
   B04 / B06 within +/-0.15 of the ground 1.5 m out; B03's stub within flush + 0.05 across its end
   line; ramp grade <= 5.5 % between stations; written zero = pack zero +/-0.05; no bridge body
   buried > 0.5; MOVED only inside published footprints and on units 4 / 7 / 15.
   KDEN `build_airport.py KDEN --tile 39 -105 --pack-copy --texture-mode default_xplane` + a base
   control, sites `mid_s=39.833647,-104.715970,120 mid_n=39.834407,-104.715986,120
   pkhwy=39.843296,-104.677804,120 pkhill_a=39.848402,-104.677912,120
   pkhill_b=39.848338,-104.669799,60 train_b=39.837287,-104.730978,200
   garage_b=39.849469,-104.677427,120 stack=39.842347,-104.673859`. Bars: no body of a bridge frame
   MOVED; each GRADED kept end's deck within +/-0.30 of the drawn ramp top (listed per end); nothing
   moved at garage_b or the stack; train_b drawn outside the old coverage.
   States in F6 are expected, unverified; G0 decides.

## C5. Not verified
- `airport.dem` at any end (no capture read): G1's difference; if it is the flat datum at B06's SW
  tip, the interchange seats near 4.40 and the road there is cut about 1.7 m.
- Today's seats of the 20 kept decks (the survey's "cur" is anchor ground + AGL, not the 22m / 22p seat).
- Rule 6 on groundside pavement: how those faces take a row, and whether the apron may cut them.
- `end_on_lot`: KMCI's ref ends `/lot`; OTHH's six graded ends stand on plain `gap:` pieces of the
  same role. If no general predicate separates them it is a finding for the owner (05e), not a switch.
- Whether lbridge4 admits YSSY road3_d; exact flags of the replay tools; island emit (N3, N6).

## C6. Owner questions (defaults applied)
B (open) Where a ramp cannot be built (airside, a deck under 5.1 m, water, a stub over 100 m):
  (a, default, recommended) build nothing and list; (b) build as far as it goes and leave the step.
Q2 Rail ramp grade: (a, default, recommended) 1.25 % (10-28k: "rails can't be as steep") — KDEN
  Outer_Train b about 540 m at the survey's 6.7 m gap; (b) 5 % as a road, about 135 m.
Q3 OTHH B05 (plated, `split_level`): (a, default) list, build nothing; (b) seat it as a free bridge
  and grade it (its seat changes). Recommend (a) now and decide at the OTHH read.
