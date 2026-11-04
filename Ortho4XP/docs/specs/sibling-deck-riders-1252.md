# Deck riders: OBJECT_MSL rows on a re-seated frame's deck (#1252)

Lane f1252, 2026-11-03. Extends `airport/frame_riders.py` (RULINGS 2026-10-22f, AGL
lifts) to absolute rows; scoped by RULINGS 2026-09-11d (MSL rows convert),
2026-10-14g (AGL rows kept) and 2026-10-28p (5) (companions re-seated,
overlays left alone).

## The defect

KDFW (Aerosoft, five packs). `KDFW_5_Scenery` is the airport pack; its 113
`OBJECT_MSL` frames, garages included, are re-seated by the placement plan
(the 1.0.41x plan moved garage `190.obj` from 184.36 to 172.04, -12.3 m).
`KDFW_1_Parked_Cars` places 14,725 library cars on the ground and 218
`lib/cars/car_static_invar.obj` rows `OBJECT_MSL 191.10-199.50`; 198 of
them stand on a garage deck of the airport pack (rider elevation minus the
authored deck height under it: 100 rows at +0.13/+0.14 m, 97 at
+0.24/+0.33 m, 1 at -0.87 m; 20 rows have no airport-pack geometry under
them at all). The sibling pack is never touched, so those cars stay where
the garage WAS. Converting them (11d) would drop them under the deck.

The same class in the airport pack itself: a STOCK `OBJECT_MSL` row (a
resource the pack does not ship, so the rebake plan never sees it) on a
deck of the pack's own `OBJECT_MSL` frame converts to on-ground and lands
under the deck. Measured: KDFW_5 has 0 stock MSL rows; KMCI has 716 stock
MSL rows, but every KMCI frame is `OBJECT` / `OBJECT_AGL` (0 MSL frames),
so the rule below does not reach them (see "Not covered").

## The rule (one witness, no names)

A row RIDES a frame when

1. the frame is an `OBJECT_MSL` row of the airport pack that the plan
   MOVES (split, row-seated or converted) by more than `MOVE_MIN_M` 0.05 m
   (the frame's authored zero is its elevation column; its written zero is
   `surface_z - y_zero` per cut body, the seat's elevation, or the drape at
   the anchor for an on-ground conversion);
2. the row is `OBJECT_MSL`, its anchor stands over a static solid triangle
   of the frame's AUTHORED geometry (`.anchor_bak` when present), and its
   elevation is that triangle's world height at the anchor within
   `contact_m` = `[rebake] elevated_base_m` (0.5 m: a row higher than that
   over a surface does not stand on it). The highest such surface wins.

A rider is written `OBJECT_MSL` at `authored elevation + the frame's
displacement under it` (the cut body whose plan box holds the anchor, the
smallest; else the frame's median). Its height above the deck is kept
exactly. Every other row is unchanged by this rule.

Populations:

* AIRPORT PACK: the stock `OBJECT_MSL` conversions (`placement_write.
  deck_riders_of_pack`, after `frame_rider_seats`); pack-own rows keep the
  carrier/unit machinery.
* SIBLING PACKS (`sibling_riders`): enabled, not the serving pack, no
  apt.dat, a DSF for the tile (`pack_local.tile_candidates`, shared with
  `companion`), shipping NO object of their own (a pack that does is a
  companion, 28p (5)), and a DSF whose command stream places an object
  from a pool with an elevation plane (`dsf_commands.
  object_pool_boxes`, no dump) whose pool box meets the airport boundary
  (a pack whose objects lie elsewhere on the tile, Global_Forests_v2, is
  never dumped). Their riders move as above.
* FREE SIBLING ROWS (owner ruling 2026-11-04T00:08Z: "If cars (or other
  objects) from a secondary pack are not on top of/overlap with any other
  objects, then they should be seated on the new ground"): a sibling's
  `OBJECT_MSL` row that is not a rider, lies inside the airport boundary
  (apt.dat row 130 of the airport pack, else its pavement hull;
  `sibling_riders.airport_region`) and stands over no static solid of any
  OTHER object — the airport pack's and every candidate pack's placing
  objects inside the boundary, library paths resolved through the
  install's library index, the row's own model (same origin) excluded
  (`frame_riders.over_objects`) — converts to on-ground,
  like the airport pack's rows under 11d. Over an object it does not stand
  on, or outside the boundary (VFR overlays), it stays as authored.

KDFW (same replay): of Parked_Cars' 21 non-rider MSL cars, 19 convert to
on-ground and 2 stay (over an airport-pack object, not on it). The 3 on the
graded sheet move -19.47 .. -19.00 m to the new surface; 16 lie off the
graded sheet (raw mesh there). Counting the other packs' objects too
(Parked_Cars 14,943, Street_Lights 1,644, AEP 1,050, simHeaven 344,
Terminal_Interiors 3 footprints) leaves the split at 19 / 2.

## Consumer census: every pass that writes a pack DSF's objects

| # | pass | reads / writes | interaction with sibling writes | ruling |
|---|---|---|---|---|
| 1 | `placement_write.apply_plan` -> `dsf_write.write_pack` (airport pack) | main DSF from its `.anchor_bak` | frames come from this plan; siblings are written only AFTER it succeeds (a `BackupUnproven` main writes no sibling) | ordered in `object_stage._place_objects` |
| 2 | same, companion plans `ICAO~k` | companion DSF | sibling set excludes packs that ship objects: disjoint packs | no sibling stage for a companion plan |
| 3 | same, sibling plan `ICAO~riders<k>` (NEW) | sibling DSF from its `.anchor_bak`, verified round trip, record | `write_pack` composes other airports' recorded edits (#25) | the one write path; no second writer |
| 4 | `unpatched_pack.restore_airport` (12d) | packs found by `object_rebake.modified_packs` (the write records) | a sibling carries the record, so an unpatched airport's sibling is restored too | covered, no edit |
| 5 | `pack_journal.replay` (stopped build, #598) | packs snapshotted by `apply_plan` | sibling snapshotted by the same `apply_plan` | covered, no edit |
| 6 | `user_seat_stage` (#1703) | `write_pack(seats=)` on the airport pack | hand seats are per-DSF records; a sibling write keeps none of the main's | none |
| 7 | `forest_stage` (#1360), `optimise_stage` (#1707), missing art (#433) | `write_pack(forests= / optimise= / omit=)` on the airport pack | a sibling write passes `None` / `()`: re-applies what ITS record holds | none |
| 8 | `object_stage_reuse` (#879) | serves the main placement from its record | a served airport does not re-run the sibling stage: the sibling keeps the write that matched the same inputs; a SIBLING-only pack update is not in the recipe | gap, reported |
| 9 | `engine_v2._fresh_companion_dumps` | pre-build dumps of companion candidates | read-only; the sibling dump is made in the object stage, like the airport pack's | none |
| 10 | stale sibling | a sibling this airport wrote before with no rider now | written again with no seat: its pristine rows come back | `sibling_stage.plans` |

## Not covered (reported, not built)

* Frames placed `OBJECT` / `OBJECT_AGL` (KMCI's 716 stock cars over
  on-ground frames): the frame's authored zero is the terrain its author
  saw, which the object stage does not have.
* A neighbour pack's dump is only READ from the mod cache, never made: a
  pack with no cached dump contributes no footprint.
* A companion pack's stock rows on decks; polygon/network nodes with an
  explicit elevation (#1252's second population).
