# Lane `walls3` — notes (2026-10-07; continues `cloudwalls` PR #460, implements object-placement spec §18)

Branch `claude/walls3` = `origin/claude/cloudwalls` 1ba381b5 + main 318efe5b + `origin/claude/authspec` c108304c.
Scratch: `<scratchpad>/walls3/` (`pd2.py` planar dump off the capture with seat records / basin refusals / deck
intervals; `pd1.pkl`, `pd3.pkl`, `pd3.log`; `pits.py` the intake read of every pit placement; `step1.txt`).
Capture: `/Users/noah/XPTerrainBuilderData/.harness/frames/perfB362/OTHH.pkl` (`--from planar`).

## Task 1 — D's red twins: DONE (7371f213, f3223f8a)
25 twins read the road cap from the law; fixtures whose meaning needed the number are re-derived from it.
Two things for the master:
- `test_v2doorramp::test_law_register` asserted door_ramp cap > tunnel_ramp / service_road cap. All three are 10 %
  now (07d + 17h Q1), so "strictly steeper" no longer holds — asserted as "never below". QUESTION: is that the meaning
  wanted, or should door / wall-corridor ramps stay strictly steeper than the road?
- A 26th twin CI never sees (it needs the mounted frames): `test_gap_terrace::test_the_rule_read_on_a_real_map…`
  (HECA, frames gaps3). D changes it: parts 93 -> 84, knives 48 -> 34, merged 66, dropped 6 -> 9 m2, and the owner's
  pavement-gap site 30.1159784, 31.4106264 reads `gap:7/lot` where it read `gap:7/ramp0`. Re-recorded; the HECA
  pavement-gap geometry DOES move with the 10 % cap.

## Task 2 — §18: step 1 measured, rule implemented (88bb16fb)
### Step 1 (the replay §18 (8) asks for first) — `h_cut` per wall on A+B+C+D
| wall | h_cut (m) | §18 expected | h_uncut |
|---|---|---|---|
| tunnel south west 2 | 2.15 | 2.04 | 4.50 |
| tunnel1 (x2) | 1.98 / 1.98 | 2.00 / 1.99 | 4.55 |
| tunnel middle - west | 2.00 | 2.00 | 2.00 |
| tunnel middle - east | 2.00 | 2.00 | 2.00 |
| tunnel_sw (#453) | 1.58 | 2.21 | 5.00 |
| tunnel west 2 (#455) | 1.59 | 2.07 | 5.00 |
| tunnel west 3 (#454) | 2.59 | 2.62 | 6.00 |
| tunnel west 1 | 2.40 | 2.4 (flat portal) / 4.95 (ramp) | 7.50 |
- `tunnel west 1` is a FLAT PORTAL (bores at both ends, grade 0) — §18's second reading.
- All nine read in band (0 … 3.0): nine kept, none re-seated; median stated height 2.00 m.
- `tunnel_sw` / `west 2` read 1.58 / 1.59, not 2.21 / 2.07: the full-length ramp (07b (2)) is shallower under the
  anchor than the OSM ramp §18 (2) sampled. §18 (8) step 6's acceptance "crest 2.0 ± 0.3" at #453 misses by 0.12 m.
- The two `middle` walls' anchors stand BESIDE their trench. §18 (3) (a)'s formula text says "the ramp profile at the
  anchor's station", which reads 0.19 / −0.41 there; §18 (2)'s own table reads them on uncut ground (2.00). The code
  follows the table: the floor where the anchor stands inside `Corridor.trench`, the ground where it does not.

### The pits — §18 (5)'s expectation FAILS (STOP, reported)
Expected basins by resource 2 -> 8. MEASURED 2 -> 4: `Drainage_01` (basin:1, rim −0.02 m) and `Dewatering_01`
(basin:2, rim −0.14 m) are cut and kept; `Drainage_02..05` are REFUSED as basements (04i rule 4).
Mechanism: each pit is two placements at one anchor with one lift (+4.2985): `_001` (floor plate −3.816, lift − depth
0.48: in band, read ground-seated, 1–3 floor witnesses) and `_000` (deepest solid −2.943 for 02..05, lift − depth 1.36:
OUT of the 1.0 band, left lifted). The lifted `_000` then stands over the floor and the region reads 100 % under its
own object's solids at or above the ground. `Drainage_01_000` is −3.609 (0.69: in band), which is why 01 works.
Not fixed (spec frozen; a wider band would be a number tuned to one pack). Candidate rule for the spec author: the
lift is one decision per ANCHOR FAMILY (same anchor, same lift) — if one member reads lifted-by-its-own-depth, its
siblings are read ground-seated with it.
- Rim: the floor row cuts `floor_clearance_m` (0.5) UNDER the floor plate, so the rim of a kept pit lands −0.02 /
  −0.14 m (at grade), not §18's +0.48 / +0.36 (07c (5) says "about 0.4 m over grade").

### Deviations from §18's text (all reported, none decided silently)
1. Kept members are EXCLUDED (the existing "terrain adapted" skip), so they are in no unit; the record is plan-level
   `RebakePlan.authored_seats` (id, resource, datum, seat, h_cut_m, h_uncut_m, proud_m / agl_authored_m), not three new
   `Member` fields.
2. The proud height rides the existing plate CLEARANCE (`Datum(plate_y − clear)`), no new `plate_proud_m` field.
3. Re-seat target = the pack's MEDIAN stated height (07c (4)), not §18 (3) (b)'s per-wall `h_uncut`.
4. `PlacedObject.agl_m` stays the AUTHORED lift; the new flag is `ground_seated` (+ `base_z`), where §18 (5) names
   `agl_read` / `agl_authored`. Forty readers of `agl_m` need the authored value.
5. The lift is measured against the deepest GENUINE solid (a decal under a shell is not its depth), and only for a
   shell at least `admission_depth_m` deep; a lift that founds no pit is read as it was. (262 placements — people 4 cm
   off the ground — passed §18 (5)'s bare test.)
6. The pit witness is judged only where the author STATED a seat — a pit read ground-seated by its lift. A plain
   pit (no lift) has no record and keeps the floor-plate seat exactly as before (§18 (3) (a) would also call a plain
   pit anchored outside its floor "authored (cut)"; that would take the plate datum from 35 jetway / plain-pit units
   whose siblings then seat by another rule). A kept pit excludes EVERY member of its basin, not the witness alone.
7. Plan version 13 with the read window widened to five (v9 still loads — `test_welded_deck` twins it).
8. NOT DONE: the `seat` column in `v2_solve_replay --emit/--verify` and `obj8_split_report.py` (§18 (6) last row);
   LEMD read (§18 (8) step 7).

## Task 4 — #450: attributed and fixed (986a1ef9)
`tunnel:-1355@0`: mouth at 25.2542625, 51.6212946 (the owner's true mouth). `climb_from` 260.3 = far edge + gap of
OBJECT deck `dsf:obj11305` (deck top 10.03 m) crossing the approach at s 152.3..259.7. The free ramp reaches the
ground ~51 m out, so the bridge stands 100 m beyond the ramp; the owner's "no tunnel here" site is ~82 m out, under
260 m of flat trench. The object branch already drops such a deck; the mapped-bore branch did not.
`structure_deck.decks_over_climb` (new) is that rule. Reaches every airport with a mapped bore and a bridge / object
deck beyond its free ramp top.

## Task 3 / 5 — see the final report (replay chain, closing build, reach).

## Task 3 — OTHH proof (replay of perfB362/OTHH.pkl `--from planar --emit --verify`, then the closing build)
Closing build `walls3_OTHH` at 0d3ce4ce: rc 0, patch 778.9 s (+ rebake plan 193.2 s, object-stage work), body_sha256
`d1cd169ed577` (= the replay's; the bar 88794a1d264b is MEANT to move), ways 1871 / nodes 27808, solve optimal, verify
rows 369, no DEFECT family. Plan `OTHH.rebake.json` version 13, sha256 `6ca0865866af`. Frames registered (lane walls3).

| wall | authored AGL | crest over ground, authored seat on the NEW surface | sw plan (before) | now |
|---|---|---|---|---|
| tunnel south west 2 | −5.50 | +2.05 | re-seated flush (−2.05 m) | kept, 0 moved |
| tunnel1 (x2) | −5.00 | +2.00 / +2.00 | flush (−2.00 / −1.99) | kept, 0 moved |
| tunnel middle - west / east | −3.00 | +2.00 / +2.00 | flush (−2.00) | kept, 0 moved |
| tunnel_sw (#453) | 0.00 | +1.75 (design 1.58) | refused, untouched, over uncut ground | corridor cut; kept, 0 moved |
| tunnel west 2 (#455) | 0.00 | +1.47 (design 1.59) | refused | corridor cut; kept |
| tunnel west 3 (#454) | +1.00 | +2.47 (design 2.59) | refused | corridor cut; kept |
| tunnel west 1 | +2.50 | +2.40 | refused | flat portal cut; kept |
("crest over ground" = sampled terrain under the anchor + agl + crest plate − 3.962; the sampler is a 3-vertex IDW.)

- #453 25.2559273, 51.6083381: `tunnel_ramp`, 3.04 m under ground; ramp 103.3 x 31.0 m (the walls' plan), 4.94 %.
- #454 25.2792668, 51.6001421: `tunnel_ramp`, 3.46 m under ground; ramp 221.3 x 38.7 m, 2.30 %.
- #455 25.2762962, 51.5920062: `tunnel_ramp`, 4.03 m under ground; ramp 221.3 x 41.5 m, 2.30 % (+ the flat portal of
  `tunnel west 1`, 35.6 x 39.5 m).
- #448: the five `Terminal_Base_2_1` bays — walls 6.3 m, ramp 6.3 m, mouth vertices 2.57–2.61 (= the wall bottom,
  1.35–1.39 m under ground: floor NOT raised), top vertices 3.83–3.91, 21.5–22.1 % (exempt). `DutyFree@2` — walls
  20.3 m, flat 6.6 m at 2.60 then 13.7 m at 10 %. The wall-corridor record carries the wall BOTTOM only (crest plate 0):
  what stands above grade / how much building is below is not read by this reader.
- #449: the shared lengthwise edge IS a `road_centerline` cut line (`route456`, 38.9 of 38.9 m inside both halves, no
  node of its own inside the ramp). After: half a — ramp 18.9 m of 38.9 m at 10 %, knee at s 20.0 with vertices at
  2.09 on BOTH edges and ON the centreline (ridge 0.87 m -> 0.00); half b — ramp 38.9 m at 4.86 %, no knee.
- #451: NOT fixed at the three owner sites (Drainage_02 / 04 / 05 anchors: no graded face). Cut now: `Drainage_01`
  (basin floor −0.35 = 4.32 m under ground) and `Dewatering_01` (−9.68); see the STOP above. Side effect to rule on:
  `Drainage_02..05_*_001` now read below-grade (plan `below grade 4`, never re-seated) with no basin under them, while
  their `_000` shells stay ordinary unit members. `[basin] authored_rim_tol_m = 0` switches the whole pit half off.
- #450: the ramp climbs from −0.96 at the mouth to ground by s ~70 and ends; no graded face at the owner's
  "no tunnel here" site (it was 260 m of trench at −1.14).

## Task 5 — reach
Sweep plans `/tmp/harness/swg_{CYXY,HECA,KASE,KCLT,NLWF,SPJC}.v2/*.rebake.json`: plate_objects 0, plate_members 0,
below_grade 0 at all six — §18's seat decision reads nothing there. Every plan's BYTES move once (version 13,
`authored_seats: []`), the law sha moves (two keys), and the partition code digest moves (`obj8`, `authored_seat`):
one cold pack partition per airport. The pit intake can add a basin only where a pack lifts a shell >= 2.5 m deep by
its own depth; not measured on those packs. D (10 % cap) reaches all six (HECA measured: gap terraces 93 -> 84 parts).
B / C / #450 reach any airport with a wall corridor or a mapped bore with a deck beyond its free ramp top (KCLT has
terrain-adapted members; not measured).

# Lane `walls4` — continuation (2026-10-07 night; same branch `claude/walls3`, PR #464)
Scratch `<scratchpad>/walls4/` (`rep2/` = the final replay of `perfB362/OTHH.pkl --from planar --emit --verify
--solved-out`; `mkpd.py` solved.pkl -> the dict `walls3/sites.py` reads + the pit table; `fam.py` the family read
on the capture; `names.py` undefined-name scan).

## Task 1 — owner RULINGS 2026-10-07e (a508c8f0)
Every ramp the pack's own objects frame (door well; wall corridor: bay / open / through) is ONE line from the
object's depth at s 0 to the ground at the object's outer end. No cap, no knee, no step.
- `wall_corridor_ramps.full_wall_ramp` (depth / wall length; the only refusal is a floor over its ground),
  `door_ramps.door_profile` (sill / well length). `Tunnel.pinched = (OBJECT_FRAMED, length, grade)` on every one.
- `constraints/structures.framed_plane`: every ramp vertex pinned on the plane at its OWN station, ending at the
  outermost emitted vertex. WHY: the old station clusters (1 m) tied to one level cost grade x 0.5 m at the top —
  0.055 m at 10 %, 0.27 m on the 72 % synthetic door ramp.
- DELETED: law `[cutout.door] ramp_grade`, `[cutout.wall_corridor] max_ramp_grade`; `BAY_EXEMPT`,
  `structure_geometry.covered_start`, `WallCorridorRecord.plate_plan`. KEPT (they price the seams the lift does not
  take): role rows `door_ramp` / `wall_corridor_ramp` 0.10, `oracle_cap`, v1 `STRUCTURE_RAMP_MAX_GRADE` — tied at
  load to `tunnel.ramp_max_grade`. `[cutout.door] max_length_m` is LIVE (door_wells rule 3's reach), re-commented.
- QUESTION for the owner (in the spec, §47 (7) AMENDED 2 (2)): the ramp runs the FULL framed length even where a
  cover protrudes over part of the walls (the 14be plate-edge knee is gone). At OTHH that makes DutyFree@2 6.7 %
  (cover edge at s 10.5) and both through halves 4.86 % (cover edge at s 29.0) — nothing but the bays and the doors
  is over 10 %. The other reading (knee at the plate edge, uncapped) would give 13.9 % / 19.1 % and bring the
  half-a / half-b mismatch back.
- OTHH door ramps: four wells 2.1 m long under a 1.70 m sill = 82.6-82.9 %. That is what 07e's words give; worth
  the owner's eye in the sim.
- The walls3 `sites.py` sampler (3-nearest-vertex IDW) misreads a long quad at mid-station (it printed 3.93 on one
  side of the through corridor): read the face VERTICES instead — all on the plane.

## Task 2 — the seat column (a508c8f0)
`pipeline/authored_seats.seat_lines`, printed by `v2_solve_replay --emit/--verify` (JSON `authored_seats`) and
`obj8_split_report.py`.

## Pits — the anchor family (1a312767; spec §18 (5), (9); owner 07f)
`authored_seat.anchor_family_key` (quantum / heading 0.001 deg / lift 0.001 m); `obj8._family_depths` at intake;
`PlacedObject.family`; `Basin.member_ids` carries the families. NOT shared with `deck_signature.family_key`
(millimetre + AGL, no heading — changing it would move the deck signature); one key function, two spellings remain.
Replay: 13 placements ground-seated (9 before), exactly Drainage_01..05 `_000/_001` + Dewatering_01 `_000.._002`.

## walls4 proof — closing build `walls4_OTHH` at 1a312767 (frames registered, lane walls4)
rc 0; patch 460.1 s single run (swg_OTHH 429.7: partition +14.5 — one cold pack partition, the law digest moved —
solve +6.3, verify +4.1, planar +2.9, the rest within 1 s) + plan 218.6 s (185.4); nothing else was running.
Body `5a4b2cd3abed` = the replay's (`walls4/rep2`). Plan v13 `8e24e55b3f68`: authored_seats 15 (9 crest, 6 rim with
their families), below_grade 0. Verify 367 rows, defects {}.
LEMD read (§18 (8) step 7; replay of `sheetchain/LEMD.pkl --from planar --verify`): ONE seat record — `Bridge4.obj`
crest, h_cut +2.02 = h_uncut +2.02, authored (cut), kept; no rim record (its pit carries no lift: plain, floor-plate
seat as before); 0 anchor families; verify defects all zero.
