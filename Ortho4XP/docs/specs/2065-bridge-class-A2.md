# #2065 A2 — amendment to `2065-bridge-class-A1.md` (+ A1-E1) after R2's first round (Fable review, 2026-11-14)

Read on origin/claude/lbridge3 2d9aa82a9 (base 99b690072), frames `.harness/frames/lbridge3/`,
RULINGS 2026-11-14d/e/f. Paths under `Ortho4XP/src/auto_patch_v2/`. ONE Opus round (medium) on
claude/lbridge3 as it stands (no merge of main before the closing); no terrain change. A miss goes
to the owner. Never raise the lane cap; delete scratch builds on report.

## B0. Findings
F1 TWO DEMS. The pack stage reads W5 on `airport.dem`, the PRODUCTION frame
   (`planar/free_bridge.py:71`; `airport/dem_production.py`: smoothing + the flat-site substitution;
   OTHH is `flat_candidate`, z0 3.962). The census and `v2_rebake_replay.py plan --bridge-witness`
   read the authored `.hgt` + insets (`tools/bridge_census.py:205`). R2's replay bars were met on
   the second; the build runs the first. R1 census: W5 holds by `ground` ALONE on 7 decks (OTHH B06
   3.4 m, YSSY road3_d 1.9, KDEN Garage_Bridge 1.5, KPWA 66bridge4, KTPA South / North, SBRJ Ponte),
   by a way on 66, by water on 2; 9 rows fail at W5.
F2 B06's driven layer runs -0.44 / -0.18 at its ends to +8.3 at the crown: the pack shows the span.
F3 `deck_datum_z` is the median of graded standing vertices in the ring buffered 0.5 m
   (`emit/rebake.py:52`): one approach-road vertex sets it (B01 3.96 in production, None in the G0
   plan; YSSY road3_d 1.0). It is not a free deck's seat.
F4 B04. The published end "chord" joins the two farthest stations of the outline within half a width
   of the crossing (`model/free_bridge.py:75`, `bridge_witness.py:544`); that outline wraps a corner,
   so the chord is a secant THROUGH the plate: 9/9 and 7/9 of its samples lie inside B04's ring, up
   to 3.9 m / 4.1 m from the outline, skewed 19° / 25°. The seat read the carried road under the
   deck, 3.54; the ground outside the ends is 3.65-3.70 and 3.78-3.83 by both drawn reads (arm
   -0.14 / -0.29 at zero -1.02; control +0.23 / +0.08 at -0.70). Not sampled directly.
F5 `admitted` tests 22n per deck ring (`planar/free_bridge.py:236`): in a bridge of several decks
   every body on deck B is "outside" deck A. Never exercised (the interchange failed W5 first).
F6 `drawn_gate.mesh_layer` fails a DSF older than the patch file (`drawn_gate.py:195`); a control
   rebuilt after the arm rewrote the same body into the lane's `Patches/` with a newer mtime.

## B1. Rules
W5 SPAN (amends A1). W5 is an OR of positive witnesses; level ground (a flat-site substitution, a
smoothed DEM) is evidence of nothing and refuses nothing by itself. It holds on any of:
(a) a crossing way of another chain; (b) water; (c) HUMP (new, pack geometry only): some interior
station of the driven layer stands at least `deck_min_clearance_under_m` (1.0) above BOTH end tops —
a road that climbs over something and comes down again; (d) ground under the end chord, as built, on
`airport.dem`. A monotonic ramp or a level deck with none of (a)-(d) stays on today's path (13r) and
is listed `W5: none (level ground)`. REJECTED: "the deck seated at its ends stands clear of the
ground" — on a blurred or substituted DEM it cannot tell an embankment ramp from one on piers.

END LINE (replaces A1 W7's "outline within half the local width"). At a route end (crossing p,
outward tangent out, deck width w): inside the square of side w centred on p and aligned with the
route, for each lateral offset the point of the plate outline OUTERMOST along out. It follows a skew
end edge, never turns down a side, never catches a curved ramp's far arm. A stub's ends: the same
about its axis.

END GROUND (S3). A free deck's published `deck_ends` chord joins the first and last stations of its
END LINE, moved `[bridge] free_end_ground_out_m` (new, 1.5 — where the drawn bar reads,
`tools/drawn_site.OUTSIDE_M`; inside R3's slab) along out. `deck_end_read` / `approach_seat` read it
as today (road ribbon where most stations lie on one). The top stays the W3 layer at the end.

FREE DECK AND `deck_datum_z` (replaces E1's hold). `plate_kind == "free"` IS the class decision; the
object stage never re-decides it. `rebake_plan.with_free` publishes a free deck whatever its datum
and sets the member's `deck_datum_z` to None there (one derivation site, 08-30l), counted
`free_deck_over_graded_face` with the value in its note; `free_deck_held_datum` is retired.

| reader | ruling for a free member |
|---|---|
| `anchor_rule.datum_of` :641 | unchanged: reads None, returns the deck-top datum with the published ends (as B04 today) |
| `airside_deck_seat._airside_witness` :352, `airside_zero` :401 | EDIT: None — class A took its frames at the planar stage (`_Airside.meets`, `admitted`) |
| `airside_deck_seat.deck_owns_its_datum` :48 | EDIT: True (a signature free deck never rides a unit, `placement_plan.py:992`) |
| `placement_family.member_is_bridge_deck` :390 | EDIT: True (out of the wall chain and the contents) |
| `footprint_unit._deck_lending` :555 | unchanged: lends nothing. Its own frame's bodies take the bridge zero; a touching body of ANOTHER frame keeps its seat, listed if it moves > 0.05 |
| `placement_plan.py:1022-1033` | EDIT: a frame holding a free member asks neither `_airside_frame` nor `_refused_bridge`; the cut / floor guards stay; `free_bridge_seat` is the last writer of every body of the frame |
| `written_seat_census.deck_rows` :143 | EDIT: `free_member` tested first ("B free-standing") |
| `bridge_class` :98 | unchanged (E1) |

The two predicates test `plate_kind == FREE_PLATE` (`model/free_bridge`): no new import upward.

22n AT THE PLANAR STAGE — CONFIRMED (`_beside_a_building` needs the classification), CORRECTED: one
test per bridge against the UNION of the rings of every free deck of its frame. R3 mints free stacks
from `PlanarMap.free_bridges` (admitted), never `Airport.free_bridges`.

## B2. Files and twins
`airport/bridge_witness.py` (`span_of(..., layer)`; `_end_line(ring, p, out, width)`; `_deck_ends`,
`_stub_ends`), `model/free_bridge.py` (`published(..., out_m)`; `_chord` goes), `law/structures.toml`
+ `law/model.py` (the key, with F4's numbers), `planar/free_bridge.py` (`admitted`),
`pipeline/rebake_inputs.py`, `airport/rebake_plan.py`, `airside_deck_seat.py`, `placement_family.py`,
`placement_plan.py`, `written_seat_census.py`, `tools/bridge_census.py` (column `w5_by`: way / water /
hump / ground; `ground` rows marked DEM-dependent) + its INDEX row; stage-code keys and closure twins
as the twins say.
Twins — `test_bridge_witness.py`: a humped ramp on level ground holds, and with `ground=None`; a
level deck and a monotonic ramp on level ground with no way or water fail; no deck that held W5
loses it; a plate with a 20° skew end and an off-centre crossing: every end-line station within
0.05 m of the end edge, every chord sample outside the ring; a ring that curls back contributes no
far-arm station. `test_free_bridge_read.py`: a free member with a datum is published with
`deck_datum_z` None; 22n reads the union (a lamp on deck B of a two-deck bridge does not attach it).
`test_free_bridge_seat.py`: a frame with a second flag deck carrying a datum seats every body at the
bridge zero; `airside_zero` is None for a free member over an airside role; a signature free deck is
not unit-carried.

## B3. Gates and bars — the PRODUCTION DEM is the gate
The `--bridge-witness` re-stamp of an older plan is a census aid and never a bar again.
P0 Census (authored DEM): E3's named lists stand. Only the nine R1 W5-failures may change, and only
   by `hump`: CYVR BS1 / BS1A, GOBD terminalRoads, KBOI Terminal_4_road_2, SBGL
   PredioEstacionamentoTPS2, TJSJ moscosobridge, YBBN track1b, YSSY road1, ENAT_Bridge. A new
   `free_bridge` among them is listed under P4 — not a STOP. Any other change is a STOP.
P1 `v2_solve_replay.py --capture OTHH` on the branch prints 3 bridges, 5 decks: {B01}, {B02, B03,
   B06}, {B04}. `--capture YSSY`: road3_d free, or the witness that refuses it listed (not a STOP).
   If P1 fails: STOP before any build.
P2 ONE `build_airport.py OTHH --patch-only`: plan counts `free_deck_members` 5, `free_deck_plated` 1
   (B05); the planar notes admit 3 bridges; patch body 861468fee49a (else the terrain moved: STOP).
P3 `v2_rebake_replay.py plan` on THAT plan, `--sampler graded`, no `--bridge-witness`: ONE zero per
   bridge; at its governing land end |zero + top - G| <= 0.05; every other land end >= -0.05; no body
   of units 4 / 7 / 15 buried > 0.5. Predictions written down first: B01 about 0.4 (3.96 - 3.53;
   today 3.72); B04 -0.78..-0.73, ends about +0.15 / 0.00; interchange about 6.14 (both production
   reads: arm +0.43 at 6.57, control -0.84 at 5.30). A4 bar 2's 4.12 and +/-0.10 were lothhdeck2's
   ground and are struck.
P4 Corpus mover replay: A4 bar 3 (YSSY unit:19 and any P0 gain with its predicted seat change;
   > 0.5 m needs the master's read before landing).
P5 Closing, ONE build, order:
   1. Control: reuse `.harness/frames/lbridge3/ctl3.drawn.json` (lb3ctl3, 99b690072, the nine A4
      sites) when P2's body is 861468fee49a — no control build. Otherwise build the control FIRST (its
      own worktree if a slot is free) and run its sited `drawn_gate --json` at once.
   2. `build_airport.py OTHH --tile 25 51 --pack-copy --texture-mode default_xplane`: the LAST writer
      of the worktree's `Patches/` before the gate.
   3. Straight after: `drawn_gate.py OTHH --tag T --against <control>` with A4's nine `--site`s, and
      `drawn_site --end-lines <arm plan>`. A control needed later is never built in the arm's worktree.
   Bars: PASS; MOVED only on objects of units 4 / 7 / 15; each free bridge's governing land end
   within +/-0.15 of the drawn ground, no land end under -0.15, B04 both ends in [-0.10, +0.30]; far
   ends listed (R3); patch->drawn no worse than the control (23 / 47,164).
   Register the P2 plan and graded, the closing plan, the arm site read and `.drawn.json` as frames.

## B4. Not verified; for R3
- No mesh frame of the round: F4's ground values are arithmetic on the two drawn reads.
- Which face gives B01 its 3.96, and whether the role under a deck ring is "building" (F5), unread.
- The crowns of the nine P0 rows are not in the census; P0 decides.
- R3: the list of witness-holding all-deck frames (14d A) must be read on the production DEM (P1's
  instrument), not the census — six of the seven ground-only decks are theirs.
- Follow-up, not this round: `drawn_gate` could compare the patch body, not its mtime.

## B5. Owner questions
None. B01's 3.3 m drop is base spec §6's and is read at the one OTHH read after R3 (14d C).
