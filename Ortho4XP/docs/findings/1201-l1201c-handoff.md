# #1201 follow-up (lane l1201c): KSEA sim read 2026-10-27T17:12Z, paused handoff

Paused on the owner's shutdown order (2026-10-27T17:43Z). NO ENGINE CODE CHANGED yet.
Base `origin/main` 096ab9dbe. This file is the only change on the branch.

Owner (verbatim): "1. 16L safety end retaining wall is a bit too low 2. 16C the wall appears
to be several meters too high, and the safety area grading should be adapted to meet the wall
3. 16R is correct 4. Why do both 16C and 16R safety areas have trenches cut in them for the
service roads? Those should just be at grade."

## What is measured (attribution done for items 1-3; item 4 partly)

Instruments: fresh capture `v2_solve_replay --capture KSEA` (155 s, 15,365 V / 1,034 F;
it was in /private/tmp and is lost on shutdown, recapture), replay `--from constraints
--solved-out`, control build `build_airport.py KSEA --base-arm --tag KSEA_l1201c_base`
(rc 0, 700.5 s; NOT stored in the artifact ledger: external-candidate deltas from other lanes),
and `v2_rebake_replay.py plan` on that build's rebake plan with BOTH samplers, against the
owner's own pack mesh `~/X-Plane 12/Custom Scenery/zOrtho4XP_+47-123/Data+47-123.mesh` and
the original DSF dump `Airport_mod_cache/.../+47-123.dsf.3a1d79de.text` (the one with 2 MSL rows).
The owner's written pack (engine 1.50.1883, provenance `Earth nav data/+40-130/o4_placement_provenance.json`)
shows the same result as the mesh-sampler replay.

### 16C: the wall is NOT seated at all: it is the old +8.7 m (mechanism A, placement stage)
* The written pack has 16C as `conversions[0]` (OBJECT_MSL 118.87 -> on-ground OBJECT), not a split:
  X-Plane puts y 0 on the mesh at the origin (the runway end, ~130.7) -> plate top ~8.7 m over the RSA.
* Why: under the MESH sampler the walled-plate datum reads the stations at 117.3-122.2 (half of
  them on raw DEM / the trench road, see mechanism B), median 118.82; `authored_landing.
  lands_on_authored_seat` compares that with the MSL row's absolute 118.87 -> "lands" ->
  `placement_file._cut_and_file` keeps it ("authored_seat_lands"), and then
  `placement_write.dump_rows` CONVERTS the kept MSL row to on-ground, because its `settled`
  set (split indices | `authored_seats` kept rows | terrain features) does not hold the
  placement-stage 14g (3) keeps. A kept OBJECT_MSL row converted is not "kept as authored".
  Graded sampler: 15 of 30 stations off-sheet, median 120.26, does not land -> split (why the
  l1201 replay never saw it).
* FIX A (general): rows kept by `authored_seat_lands` join `settled` in `dump_rows`
  (`ss.kept`, reason "authored_seat_lands"), so their authored row is written as authored.

### 16C west half and 16L: the safety area stops short of the plate (mechanism B, planar)
Band reach at the seat stations (graded.json of the control build; + = reaches the inner edge):
* 16R: +1.8 ... +2.1 m at every station except the road cut (stations 18-19) -> flush, correct.
* 16C: stations 0-14 (west half) -14.0 ... -8.6 m; stations 15-17 and 24-29 +1.9 ... +2.2 m;
  20-23 -9.4 ... -7.2 m. Cause: `planar/terrain_edge.clip_to_terrain_edge` finds CRESTS at
  s ~284-289 (`PlanarMap.terrain_edges` 0 and 2, 0.4-0.7 m from the inner edge): its outward
  probe reads the plate's OWN lidar step (121.1 -> 102.8 over s 294-316).
* 16L: -19.7 ... -19.4 m at every station (band ends at s ~275, `zone2#42`). Cause (static
  reading, confirm on the replay): `model/end_area._end_length` takes the shortest of the
  centreline and the two side lines; the plate's inner edge is oblique on the east side
  (s 272.9 at t +75), so the side line's DEM-drop reading (15g (C)) hits the plate's own step at
  ~275 and cuts the WHOLE end there before `min(..., inner_s)`.
* So at 16L the seat reads DEM/core mesh (~123.6) while the graded RSA ends at 124.7 20 m
  back -> "a bit too low"; at 16C the seat reads half DEM -> the landing keep of mechanism A.
* FIX B (general, 27t "the safety area ends at the plate's inner edge"):
  1. `model/end_area.end_area_lengths`: at an end a walled plate caps, a DEM drop whose crest
     stands at or beyond the plate's nearest inner-edge s (minus `edge_probe_m`) is the plate's
     own step -> the length is `inner_s`; an earlier genuine drop still wins.
  2. `planar/terrain_edge`: a crest cell within `edge_probe_m` of a walled plate's footprint is
     not a crest (thread `airport.walled_plates` footprints from `planar/zones.zone_regions`).
  3. `planar/zones`: runway bands minus the plate footprints (no stand-off), so the oblique
     inner edge (16L east) is not overlapped by the end box.
  16R must not move: it has no crest near its plate and its end length is already 302.8.
  Replay check (solved band at the stations, replay of the current tree): 16R 114.76-115.22
  (median 115.03), 16C 121.13-122.23 (median 121.87) -> once the band reaches the plate the
  seat is flush within +-0.6 m across the width; the "flat inner edge" follow-up is probably
  unnecessary.

### Item 4: service roads trenched in the 16C / 16R safety areas
Roads: 16R `small_roads:-22031` (242.8 m in the RSA, t +13...+22, s 111-302) and `-22030`;
16C `-22044` (180.6 m, t +15...+23, s 118-302), `-22045`, `-22046`; all `highway=service`.
Replay, road vs the band beside it (road - band):
* 16R: s 111 -4.2/-4.3, s 162 -4.3/-4.4, s 212 -3.3/-3.4, s 262 -2.4/-2.5 m.
* 16C: s 118 -1.4, s 139-147 -1.9 ... -2.2, s 193 -3.0/-3.1, s 241 -4.2/-4.3, s 288-300 -5.1 ... -5.7 m.
Two parts:
* (i) MINTED: the road stands BELOW ITS OWN DEM by up to 4.3 m (16C s 288: road 117.6, DEM 121.9;
  16R s 111: 120.8 vs 122.2). These roads run onto the plate; `constraints/walled_plate.
  under_plate_rows` caps every vertex under the plate at the LOWEST station DEM - 0.05
  (16C 117.95, 16R 111.2) and the road's own grade law carries that dip back up the RSA. Wrong
  under any ruling; fix the cap's level (e.g. per-vertex DEM / the station ground nearest the
  vertex, never the min over the width) or exempt road vertices on the plate.
* (ii) RULED TODAY: band - DEM is 1.0-1.3 m (16C) and 2.7-2.9 m (16R) of fill, and owner
  RULINGS 2026-10-20c (39) says "a road through the outer runway safety-area band follows its
  own ground" (#951, KLAX). So "at grade" REVERSES 20c -> OWNER QUESTION below. The KLAX road
  of #951 (33.946977, -118.436319, ways -2346/-2347) is `highway=secondary, lanes=2`; the KSEA
  roads are `highway=service`: a witness that separates the two cases.

## OWNER QUESTION (draft, for the master)
Q-A. Roads inside a runway safety area: (a) every road through the safety area sits at grade
on it (reverses 2026-10-20c; KLAX's #951 road would be pulled back up to the runway-end
level); (b) an airport SERVICE road (`highway=service`) through the safety area sits at grade
on it, and a public road (secondary, residential, ...) keeps 20c (its own ground, wall at the
band edge); (c) keep 20c for all (KSEA keeps a 1-3 m cut after the cap fix).
Recommend (b).

## Exact next step
1. `tools/harness/lane_worktree.sh up l1201c claude/l1201c`; recapture KSEA (`v2_solve_replay
   --capture KSEA --out /private/tmp/claude-501/l1201c/KSEA.pkl`, ~155 s) and register it.
2. Implement FIX A, FIX B (1-3) and the cap fix of item 4 (i); twins in
   `tests/auto_patch_v2/test_walled_plate1201.py` (synthetic: crest at the plate not clipped,
   oblique inner edge, landed MSL row not converted).
3. Replay `--from planar` (B changes planar) and re-measure the stations / roads (scratch
   scripts: band z at the plate stations by LinearND over graded_strip vertices; graded.json
   face cover per station; per-station band reach along the outward axis).
4. Implement Q-A once the owner answers (zone-2 road yield: `planar/road_yield` + `road_shadow`).
5. ONE KSEA closing build + census against `KSEA_l1201c_base` (/tmp/harness, likely lost on
   shutdown: rebuild the control on origin/main), then `v2_rebake_replay plan --sampler mesh`
   with the owner's mesh to confirm 16C is a split with its datum.
6. Gates: tests/auto_patch_v2, closure + registry twins, ratchets, test_no_airport_specific_code. PR "Refs #1201".

## Cloud?
Steps 2-4 (code + synthetic twins) can run in a cloud container. The replay/measurement,
the closing build and the mesh-sampler check need this Mac (corpus, KSEA pack, owner's mesh).
