# The pack's cut shell IS the ground; a deck over it ends on its taxiway (#1883 round 3, #1903, #1914)

Two-round-cap review spec (RULINGS 2026-10-20b), 2026-11-06. Round 3 is the last Opus round; a miss goes to the owner (2026-11-03d).

Owner law: 2026-11-03b Q340 a (level B is a region running under bridges at full width), Q343 a;
2026-11-03e (3)(4)(6)(7)(8); 2026-11-04a (16) (deck end line = tile seam); 2026-10-26d (keep the
pack's cut, seat the deck to the taxiway); 2026-10-30f (1) (bridges read BEFORE the solve);
#1903 owner 2026-11-06 ("one continuous trench tracing the object's whole footprint at the depth of
its own floor plates, end to end"); #1914 pending. General rules only (05e); an airport is a test case.
Branch from origin/claude/testapp-1.0.473 (carries 92cdd97dc + dc5ba02f6; main does not).

## 0. Why the failed rounds passed their bars
- Round 1 (1f916cc6d + 3c2858c76): bar was the PLAN (rebake replay body zeros). The written DSF has
  Trench_00/01/02/06 as ONE whole row each, OBJECT_MSL 77.69, so no body seat reached the sim. A deck
  zero as the MEAN of two ends leaves half the cross-span difference at each end. deck_bridge.py:265-269
  refuses this frame as a hard-deck bridge (co-placed trench walls), so edge_deck never saw these decks.
- Round 2 (92cdd97dc): channel_zero puts ONE point (deepest plate, datum 66.47) on the cut; Trench_06's
  inner surface rises 65.5 -> ~71.4 over the SW km, so a flat cut at 67.09/66.66 leaves +4.35/+3.17.
- Floor round (dc5ba02f6): object_floor._within narrowed Trench_06's floor to 438 m2 of a 530,682 m2
  shell; under the decks the shallow liner corridors (Trench_01 c2 / Trench_02 c68 at 74.0) own the
  ground (7.5-9.1 m too high). seat_records whole-row seats floor AND covers, withdrawing the deck split
  (1.0.473 87928c544 flips that rule; restores body seats, not the cut).

## A. One ground under a pack trench: the LOWEST stated surface, over the whole footprint
A1. Reader (airport/object_floor.read_object_floors, ONE derivation site). Add the CONCAVE SHELL
    class beside FLOOR OBJECT: open-top hollow, top surface >= hollow_m (1.0) under its own rim (p90 of
    the outline band) over >= shell_hollow_min_share (0.5) of its inner plan. Shape function in geom/
    (shape_class(top, low, rim) -> concave | covered | convex | flat); tools/drawn_check.shape_witness
    calls THE SAME function (twin: Trench_06 c0 concave, Trench_00 c1 flat, Trench_07__b4 covered).
A2. Surface: for a shell, ALL its solid triangles (banks included). Floor objects keep the
    plate_normal_y_min filter (object_floor._placed_floor:126-128). floor_z_at = lowest face at (x,y).
A3. Footprint = plan union of the shell's faces where its surface lies below the current design ground
    (a cut never raises ground). Delete _within / the between-walls restriction.
A4. Several objects over one point: ground = MINIMUM of every floor/shell surface (deepest wins); a
    shallower shell inside a deeper one (bridge liner over the corridor) owns no ground.
A5. Cells (planar/object_floor_cells.add_object_floor_cells): footprint is senior INCLUDING under every
    deck; trims channel cells, object_cut corridors, deck_cut voids, deck_ground. Split the footprint
    along the shell's creases (slope > [tunnel.object] crease_deg, or step > hollow_m) so breaklines
    carry the steps; pins (constraints/object_floor.object_floor_pins) stay "every vertex to floor_z_at".
A6. Channel datum: a §45 channel YIELDS inside a floor/shell footprint. RETIRE airport/channel_zero.py,
    rebake_inputs._channel_plates and rebake_plan's channel plate_y (B1 replaces them).
A7. #1914 variant (only if the owner rules yes): a CONCAVE SHELL that is the deepest stated surface (A4)
    with its rim at grade (|rim - design ground| <= ground bar over >= half its outline) is HIDDEN: its
    row is left out of the rewritten DSF (add a Dropped record beside Kept in placement_write/dsf_write).
    The CUT is identical in both variants; the ruling toggles only the row. Convex bodies never hidden.
    Implement behind a law key defaulting OFF until the owner rules.

## B. One seat authority for a pack frame; a deck over the cut ends on its taxiway
B1. Datum frame zero (placement_plan, where channel_zero is called today): every body co-placed with a
    floor/shell object (cover_placement_tol_m, same heading) takes the zero the floor was read at — the
    pack's shared datum — EXCEPT a hard-deck piece pavement drives across (B2). seat_records emits the
    whole-row seat for the FLOOR/SHELL row only, never covers. Liners land on the cut by A2.
B2. Deck pieces: a hard-deck piece over a pack cut with pavement across is a DeckBridge for its END
    LINES and SEATS (drop the deck_bridge.py:265-269 refusal for the SEAT; keep it for the CUT: the
    footprint owns the ground under it). Each piece is its own DeckBridge (Trench_00 c1/c2 zeros differ
    3.1 m); edge_deck's RIGID row seats it PRE-SOLVE and holds pavement at both end lines to the deck top
    (2026-11-04a (16)): the taxiway flattens to the deck end, the deck never tilts. Retire cut_deck_seat
    (riders move to the DeckBridge riders path). Trench_00 c0 (ramp plate) rides the piece it touches.
B3. Written rows: deck pieces are split bodies written OBJECT_MSL at their zeros; floor/shell row whole
    at its datum (or dropped, A7). The twin asserts the WRITTEN dump (dsf_write output), not the plan.

## C. Consumer census (CLAUDE.md 30l)
| consumer | reads | ruling |
|---|---|---|
| planar/object_floor_cells | cells, knives, keepouts | A3/A5 owner of the ground |
| planar/channel_claims add_channel_cells, channel_floor | channel cells / datum | yields inside footprint (A6) |
| planar/structures object_cut shell corridors (Trench_01/02 at 74.0) | corridor floor | trimmed to rim; shallower shell owns nothing (A4); walls stay knives |
| planar/deck_bridge deck_cut / _walled_trench / deck_ground | ground under deck | not run where a footprint owns ground (B2) |
| constraints/object_floor | pins | unchanged, over whole footprint (+ crease parts) |
| constraints/edge_deck, deck_lines, deck_anchor | deck seats / span flush | now also these decks (B2) |
| constraints/channel.py:44-66, structures.py:288,861 rim DEM pins, foot_rows | tunnel_trench faces | ref-filter object_floor:*; rim pins excluded on the footprint rim |
| airport/cut_deck_seat, channel_zero, rebake_inputs._channel_plates | object-stage seats | retired (A6, B2) |
| airport/object_floor.seat_records -> terrain_shaped.row_seats -> placement_write | whole-row seat | floor/shell row only (B1) |
| airport/anchor_rule._basin_rim_anchor, open_frame_seat | frame zeros | B1 wins for a datum frame |
| hanging_objects/basins, covered_bores, trench_objects.mouth_portals, floor_mouths | claims / mouths | unchanged; mouths seat at floor_z_at |
| emit/graded tunnel_trench edges, emit/osm_adapter object_floors, publication.object_floors | emit | unchanged |
| verify/keepout object_cut_depth/offset | census | unchanged (should go green) |
| tools/drawn_check shape_witness | classification | shares A1's function |
Seam-probe (replay --from structures) where static reading is not decisive: deck_ground vs footprint.

## D. Acceptance — ONE LGAV build, then tools/drawn_check.py (claude/drawncheck 67e178042; --pack the
AUTHORED pack DSF copy if A7 hides the shell) at the five sites, one run:
- corridorSW 37.92809,23.93672 ; corridorSW2 37.9265,23.9351: Trench_06 c0 open floor - mesh |p50| <= 0.5
  and p95 - p05 <= 1.0 (today +4.35 / +3.17); Trench_07__b7 / Trench_08__b7 bottom - mesh |p50| <= 0.5
  (today +10.86 / +3.47).
- deckSW 37.931323,23.939422 ; deckNE 37.943888,23.951247: Trench_06 c0 open floor - mesh |p50| <= 0.5
  UNDER the deck (today -7.98 / -7.52); Trench_00 c1 and c2 top step at each 47 m END edge |step| <= 0.05
  (today +0.73/+0.34 and -1.49/+3.63); Trench_00 c0 bottom - mesh |p50| <= 0.05 if pavement drives on it,
  else 0.5 (today +4.33).
- No regression: EGLL floors (frames r2-trench), KBNA twy L, ENTC portals replay unchanged (--stage
  structures counts); tests/auto_patch_v2 green; ratchets dupes/unused not up.

## E. Owner questions
Q1 (#1914) hide concave shells that are the deepest surface with rim at grade? Recommend yes.
Q2 bridge liners inside the corridor shell (Trench_01 c2 / Trench_02 c68): keep as objects at the datum
   zero, owning no ground. Recommend keep (visible abutments).
Q3 deck ends: taxiway flattens to the deck end line — already ruled (11-03e (4)/(6), 11-04a (16)).
