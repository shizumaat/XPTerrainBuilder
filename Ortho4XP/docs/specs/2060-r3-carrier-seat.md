# #2060 round 3 — the carrier seat is order-free; only an attached rider tilts

Fable design confirmation of lcylw2 26c8c31ec, RULINGS 2026-11-14c (2); amends `2060-round2-spec.md` R1/R2/R4.
R3 stands. Last Opus round: a miss goes to the owner.

## Findings (Fable, read-only)
- Cycle: no carrier-of-record to choose. A rider always rides a footed group-body slot
  (`placement_carrier.py:435-438`, `placement_plan.py:1192-1194`) and a footed slot never rides, so the SLOT graph
  is acyclic; the loop exists only at member level (one member = one record). Round-2 HECA plan: 204 of 895
  carried riders cut before their carrier — 62 in true member cycles (SCCs of 26, 5, 3), 142 downstream because
  `cut_order` takes `rest[0]` whether or not it is in the cycle (`placement_carrier.py:1014`).
- b44: `building__b44_10e43c36` names slot id `concrete_3__b1.obj` (never refreshed), same zero as its carrier
  (80.531): only the tilt is missing. `T3_30__b3` on `building_texture__b42_f060cbda` is a second, pre-existing case.
- Blind count: `seat_tilt_level_rider` absent at HECA because `rider_counts` matches `merged_into` against written
  file names and a rider cut first carries the slot id.
- 4140 grass: `grass__b1` is 56.3 m in plan from carrier `concrete_3__b15` (contact chain); round 2 rotated it about
  that far pivot (low point 68.68 → 68.43). The frame was already buried in control (pre-existing, not #2060).
- CYLW Hangar_8__b1 is NOT an R3 gap: a 171 × 108 m footless body 29–200 m from Hangar_9__b0's anchor; its parts
  belong to unit fu:24:558 on pad building5, so 22o puts it at 416.807. Leave R3 alone. Round 2 regressed it
  unmeasured (file 23416ffe → e2c3b474, baking Hangar_9's tilt over a 29–200 m lever; the CYLW build ran without
  `--pack-copy`, "objects NOT MEASURED").
- 5933 is an instrument artefact: sign file (110ef48f), `lowest_z` (105.88) and carrier frame identical in control,
  r1, r2; only the probe `at` moved 29 m. General test: a row whose def hash and `lowest_z` match control is
  unmoved; its clearance change belongs to the rows under it.

## Rules (14p (1), 22o; no new ruling, no new law key, no airport code)
- T1 — carrier slots are formed before any member is cut. Hoist the pure block at `placement_plan.py:1168-1190`
  (`_group_bodies` → `_deck.deck_seat` → `_pst.seat_tilt`) into a pre-pass over `staged`, after `frame_tilts`
  (:1108) and before `cut_order` (:1120). Keep `formed[mi]`; fill `seat_of[(mi, k)] = _applied(b)` and
  `slot_anchor[(mi, k)] = b.anchor`. The loop reads `formed[mi]`; the post-write refresh (:1313-1316) stays. Fill
  from the formed body, not `frame_seats` (§49's deck seat can move a slot off its frame key). Do not pre-fill
  `file_of` (`merged_into` and reason strings byte-identical). Do not change `cut_order` or member order.
  `Candidate.group == -1` has no slot and takes no seat.
- T2 — only an attached rider rotates. Add `placement_seat_tilt.attached(rider_boxes, c, touch_m)`: least
  `placement_boxes.box_gap_m` between the rider's part boxes and `c.part_boxes or (c.box,)` ≤
  `open_frame_seat.TOUCH_M` (1.0 m). `rider_seat` returns the body unchanged, no seat, when not attached; count
  `seat_tilt_rider_unattached`. `frame_tilts`' `rider_headings` (:387-402) counts attached riders only. An
  unattached rider keeps its carrier's zero as before round 2.
- T3 — the census is order-free. Record `rides[(mi, body_id)] = (c.member, c.group)` at `_carried_file` (:1221) and
  `slot_written[(mi, body_id)] = body` at :1313. After the unit's loop replace the in-loop `rider_counts` (:1328)
  with one pass over the unit's written riders: `seat_tilt_rider_followed` (same grad as written carrier);
  `seat_tilt_level_rider` (attached, carrier written tilted, zeros within 0.05, rider level) must be 0;
  `seat_tilt_rider_orphan` (rider tilted, carrier kept whole, level, or other grad) must be 0;
  `rider_before_carrier`, `rider_before_carrier_zero_apart` report only.
- R3 unchanged: a rider whose own parts name another unit takes that unit's zero (22o) and, unattached, bakes no tilt.

## Consumer census (30l) for "attached rider"
| Reader | Interaction |
|---|---|
| `rider_seat` | the one decision site |
| `frame_tilts` heading veto | same predicate |
| `placement_file._cut_and_file` :497-498, `baked_name` :40-65 | bake/name whatever seat the body carries; no edit |
| `open_frame_seat.group_zero` (`_tilted`, `alone` :616, `follows` :629) | reads `merged_into`, not the seat; unchanged |
| `_rigid_open`, `split_guard.py:120` | skip records with a tilted body; counts unchanged on the replay |
| `cut_deck_seat.py:357` | already clears the seat |
| `authored_landing.body_zero`, `placement_record.to_dict`, `obj8_split_report` | read/print only |

## Files
`airport/placement_plan.py`, `airport/placement_seat_tilt.py`, `tests/auto_patch_v2/test_tilted_group2060.py`,
`tools/drawn_site.py` (+ INDEX entry + twin). `tools/blast.py` on both src files first. Expect ~+130/−30 src.

Instrument: promote `cmp2.py` (third use; kept at `/Users/noah/XPTerrainBuilderData/.harness/frames/lcylw2/keep/`)
as `drawn_site.py --clearance-only --against CTL.json`: a row whose def and `lowest_z` equal control prints UNMOVED
and is never counted worse. Do not change `clearance_m`.

## Twins (each of the first three must fail on 26c8c31ec)
1. Member cycle (A's rider on B's slot, B's rider on A's tilting slot): both riders bake the carrier's grad, identically in either member order.
2. A member downstream of a cycle, cut first: same result.
3. A rider 79 m from a tilting carrier: no seat, level hash, `seat_tilt_rider_unattached == 1`, the frame still tilts, and at another heading `frame_tilt_mixed_heading == 0`.
4. A level rider whose `merged_into` is a stale slot id is counted in `seat_tilt_level_rider`; a rider tilted on a carrier later kept whole is counted in `seat_tilt_rider_orphan`.
5. Hangar_8 shape: a far rider with its own unit takes the group zero, level; the carrier keeps its zero.
6. Existing round-2 twins stay green.
7. The `--against` UNMOVED twin.

## Replay control (HECA, no build)
`tools/v2_rebake_replay.py plan` on `/Users/noah/XPTerrainBuilderData/.harness/frames/lcylw2/HECA.rebake.json` with
`HECA.graded.json`, at 26c8c31ec and on the round-3 tree. Exactly three bodies change: `Hangar_Tower/building__b44`
takes `concrete_3__b1`'s hash; `Hangar_Tower/T3_30__b3` takes `building_texture__b42`'s hash;
`Private_hall/grass__b1` returns to level. Any other changed body must be a rider cut before a tilted carrier
(list it); anything else: STOP. Counts: `seat_tilt_level_rider` 0, `seat_tilt_rider_orphan` 0,
`seat_tilt_rider_followed` 3 (was 2), `rider_before_carrier` 204, `frame_tilt_applied` 5, `group_zero_bodies` 973,
`group_zero_tilted_kept` 1, `group_zero_tilted_moved` 13. If the shared-repo guard trips, report the path; do not refresh.

## Closing builds (`--pack-copy`; df ≥ 30 GB; never raise the lane cap; delete scratch builds on report)
1. CYLW tile 49 −120, control at 22d554dd7 and branch: `drawn_gate.py CYLW --tag T --site H9=49.955886,-119.380657,40
   --site H8=49.954583,-119.381220,105 --against CONTROL`. Plan: the four Hangar_8/9 bodies equal `cyl_base.json`
   (`Hangar_9__b0_7233be0a` zero 417.097, `Hangar_9__b1_90d6de11` 416.807, `Hangar_8__b0_f9b1883d` 416.807,
   `Hangar_8__b1_23416ffe` 416.807) — else STOP. H9: PASS, clearance within 0.3, no wall afloat. H8: PASS and not
   MOVED against control (a FAIL on a record identical to control is pre-existing: report, not a miss).
2. HECA tile 30 31: `drawn_site --clearance-only --against ctl.cl.json` over all rows, plus `drawn_gate` sites
   `b44=30.116730,31.392282,25` and `grass=30.128157,31.400477,15`. First confirm the installed World mesh is the one
   control read (205,626 triangles in the b44 box). Row 5247: same hash as row 5406, clearance 0.00 ± 0.05,
   `on_object` True. Row 5068: same hash as 5340, `lowest_z` within 0.15 of 88.20. Row 4140: `grass__b1_e36c235e`,
   `lowest_z` 68.68, clearance −0.38 (control). Row 3929 holds 0.00, `on_object` True. Row 5933 UNMOVED (110ef48f,
   105.88). No moved row worse than control by > 0.1 m. Rows 3361, 3400, 3867, 4124 hold. Register both plans with
   `frames.py register` before cleanup.

## Residuals (pre-existing, not this round)
HECA `T3_17__b5_193f5a72` (row 5002) 10.52 m under its carrier `building_texture__b63` (cut before the carrier, missed
its 22o move); Private_hall `floor__b14`, `floor_dark__b2`, `grass__b1` 0.56 m under their senior's group zero; an
SCC-aware `cut_order` would remove 142 of the 204 early riders but moves rows such as 5002 and needs its own round.
