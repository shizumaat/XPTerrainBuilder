# A WALLED PLATE CAPS A RUNWAY'S SAFETY AREA — recognition, seat, grade (#1201)

Status: **SPEC, awaiting owner rulings Q1 and Q2 (§8)**. Lane `l1201`, base
`origin/main` 7430f543b. Scoping: lane `lwalls`, `docs/findings/1201-lwalls.md`
(PR #1481). Measured on a FRESH capture (`v2_solve_replay --capture KSEA`, this
base, 15,379 V / 1,034 F, registered as frames `l1201` capture) and its replay
solve (`--from constraints`, status optimal, 89.5 s), and one base build
(`build_airport.py KSEA --base-arm`, tag KSEA_20261026T211437, rc 0; its artifact-ledger
store was refused as CONTAMINATED-KEY because this spec was written into the tree
mid-build, so it is not a shared control). No engine code is changed by this spec.

Owner, 2026-10-21 (issue #1201, verbatim): "the runway end retaining walls at
KSEA ... are built to cap the runway end safety area with a road running by their
foot, and their top should be flush with the runway safety area terrain. They
should be recognized by shape, position, and surrounding features so they're
seated correctly and the terrain is graded to match them."

KSEA is where the defect was found and is the closing test; nothing below names an
airport, a pack or a coordinate window (RULINGS 2026-10-05e).

## §1 What stands there (site numbers first)

Three pack objects, one beyond each NORTH runway end, each placed with its origin
on the extended centreline about 30 m beyond the threshold. `s` = metres beyond
the runway end along the outward axis, `t` = metres across it.

| End | Object (kind) | Plate (flat top) | Outer wall | Inner edge s | Outer edge s | Foot road |
|---|---|---|---|---|---|---|
| 16R | `KSEA_RWY16R_APP-KSEA_KJ_02.obj` (OBJECT, AGL 0) | y −10.0, 5,425 m², t −105…+90 | to y −38.0 (28.0 m); approach-light pier to y −55.5 | 302.8 | ~326–333 | `small_roads:-803` at z 87.8–88.8 (DEM 87.8–90.4), s 315–351 |
| 16C | `KSEA_RWY16C_POD-KSEA_KJ_02.obj` (OBJECT_MSL 118.87) | y 0.0 → **118.87–119.3 MSL**, t −105…+75 | to 92.9 MSL (26.0 m) | 298.6 | 313.3 | `small_roads:-12798#1` z 104.4–105.8, `-1163` z 101.9–103.5, s 309–329 |
| 16L | `KSEA_RWY16L_POD-KSEA_KJ_02.obj` (OBJECT_MSL 118.87) | y +0.5 → **119.4 MSL**, t −105…+75; light-pier deck +4.7 at t −30…0 | to 98.9 MSL (20.5 m); pier to y −48 | 296.3 | 304.7 | `small_roads:-12798#1` z 105.4–109.8, `-6016` z 92–95, s 306–374 |

The FAA C/D/E safety area (RULINGS 2026-10-15c (2): 1,000 ft = 304.8 m from the
runway end) ends 2.0 m (16R), 6.2 m (16C) and 8.5 m (16L) beyond the plates' inner
edges: **each plate is the end of its safety area.** The lidar inset (USGS 3DEP)
shows the step at each: 16R 112.5 → 88.2 m over s 316–344; 16C 121.1 → 102.8 m
over s 294–316; 16L 123.3 → 105–107 m over s 296–316.

**What the build does with them today (base 7430f543b).**

| End | Plate top now | Solved safety area at the plate | Plate vs RSA | Wall foot vs ground at its foot |
|---|---|---|---|---|
| 16C | **130.67** (on-ground conversion: y 0 at the runway mesh at the origin) | 122.0 (band, s 293–298) | **+8.7 m** | foot 104.7 over 102.0–103.5: **floats 1.2–2.7 m** |
| 16L | **132.07** (same) | 124.2 (band grade carried to s 296; the band itself stops at s 275) | **+7.9 m** | foot 111.6 over 105.6–112.0: **floats up to 6.0 m** |
| 16R | **138.8** (feet law on the pier's buried foot, §1a) | 115.05 (band end s 305: 114.56–115.02) | **+18.7 … +23.8 m** | foot 105.8–110.8 over 87.8–88.8: **floats 17.5–22.5 m** |

and the terrain does not meet them either:

* 16C: the safety-area band (`adjacent_ground:runway:4:zone2#11/#23`) runs to s 305
  at 121.2–121.7 m over a DEM of 108.5–116.0 — **up to 13.0 m over the ground**, i.e.
  6.4 m PAST the plate's inner edge and out over the lidar step;
* 16R: OSM service road `small_roads:-6086#3`, mapped on top of the plate, is solved
  at up to 124.76 m over a 110.6 m DEM (**+14.1 m**) between s 232 and 330;
* 16L: the band stops at s 275 (roads `small_roads:-5593` / `-1163` beat it, 19a),
  21 m short of the plate.

### §1a 16R today

Measured on the base build (`build_airport.py KSEA --base-arm`, KSEA_20261026T211437,
rc 0, 549.8 s; its rebake plan replayed through the placement stage,
`v2_rebake_replay.py plan --sampler graded`). The object is split into two bodies; the
main body `b0` (the plate, the wall and the approach-light pier) is anchored by
"low-side foot (no point within 0.3 m of the body's zero plane: terrain spread
1.19 m)" with `y_zero` **−55.469** — the pier's buried foot — at a surface of 93.35 m
(the graded sampler; the lidar there is 88.3 m). The plate top lands at surface + 45.47
= **138.8 m (133.8 m on the lidar ground) against a safety area of 115.05 m:
+18.7 … +23.8 m**, and the wall's foot (y −38) at 105.8–110.8 m over the road at
87.8–88.8 m: **floating 17.5–22.5 m**. The app's 2026-10-20 bodies carry the same
offset (−55.469).

The 16C and 16L rows of the same replay are `conversions` (`kind_before`
OBJECT_MSL, `z_before` 118.87, no `msl_seats`): written on-ground, as §1 says.

## §2 Attribution — three mechanisms, each in the code

* **M1 (16C, 16L) — the MSL guard keeps them out of every reader.** Both are
  `OBJECT_MSL` rows whose geometry lies wholly at or below their origin (the author's
  datum, 118.87 m, is the plate top, not the ground at the origin).
  `airport/pack_partition.py:653-659` skips them ("OBJECT_MSL built around its origin
  (geometry below it): kept on-ground whole", owner Q54, RULINGS 2026-10-20s guard)
  and the 11d conversion writes them as on-ground `OBJECT`: X-Plane puts y 0 on the
  mesh at the origin, which is the RUNWAY (130.67 / 131.57 m solved), 11.8 / 12.7 m
  above the author's datum. Verified in the capture's `partition.skipped` and in the
  app's own written DSF of 2026-10-20 (`+47-123.dsf.398540c3.text`: `OBJECT 703` /
  `OBJECT 704` with no elevation). Because they never enter the partition, the wall
  classifier, the deck reader and every seat rule are blind to them.
* **M2 (16R) — a walled plate read as a deck candidate, seated by its deepest foot.**
  `airport/deck_signature.py` finds the plate (5,363 m², 45.65 m over its lowest
  feet) but no spanning evidence and leaves it `candidate`; the member's
  `base_profile` verdict is `feet` with `feet_y` −55.47 — the APPROACH-LIGHT PIER's
  foot, authored 18 m under the road at s 350. The app's 2026-10-20 bodies show the
  result: `KSEA_RWY16R_APP-KSEA_KJ_02__b0_f0883546.obj` header "offset 4.996 −55.469
  −412.975 tilt −0.016723 −0.007801" — the body re-anchored 413 m north with its
  lowest foot at y 0, i.e. lifted by the pier's buried depth.
* **M3 (all three) — the safety area does not know the structure.** `planar/zones.py`
  runs the end band the full RSA length (15c (2)) and ties it to raw ground with the
  1:3 bank (15c (3)); nothing clips it at a plate, so it overhangs the step (16C) or
  is stopped by a road short of it (16L). The wall classifier
  (`airport/wall_class.py`) admits only slender components (plan thickness ≤ 0.5 ×
  height, #715) — a plate 15–47 m deep over a 20–28 m wall is not slender, so no
  wall record (`PlanarMap.road_terrace['wall']`) exists and neither the declared
  terrace (15a (2)) nor the road-at-the-foot release (19a/19i/19k) reads it. And
  `constraints/wall_zone.py`'s "BEFORE THE WALL" rule, were the plate a wall today,
  would hold the ground up to 4 h (112 m) before it FLAT at the runway end's level —
  wrong for a safety area that falls 3–5 % (census row 11).

## §3 Rule 1 — RECOGNITION: a walled plate at a runway end

A pack placement (any row kind, its origin set taken whole — `msl_feet` "rows
sharing one origin are one rigid set") is a **RUNWAY-END WALLED PLATE** of runway
end E when its static solid geometry, placed, shows all of:

1. **A PLATE.** The largest-area 0.5 m bin of near-horizontal solid faces
   (|n_y| ≥ `deck_plate_normal_y_min`, the deck reader's own threshold) holding at
   least `walled_plate.min_area_m2` (proposed 1,000 m²; measured 1,905–5,425 m²).
2. **POSITION.** The plate lies beyond E: its INNER EDGE (the plate boundary nearest
   the runway, read every `station_m` = 5 m across) at s ∈ [0.5 L, L + 60 m] where L
   is E's safety-area length in the law tables
   (`law.tables.runway_safety_area_length_m`), and its extent across the axis covers
   at least `walled_plate.min_cover` (proposed 0.8) of the safety-area width
   (2 × `zone2_half_width_m`). Measured: inner edges 296.3–302.8 m (L 304.8 m);
   cover 180–195 m of 152.4 m = 1.18–1.28.
3. **SHAPE — an outer wall.** Steep solid faces (|n_y| < 0.3) under the plate's OUTER
   edge (the side away from the runway) reaching at least
   `retaining_wall_min_height_m` (2.0 m, the wall classifier's floor) below the plate
   along at least `min_cover` of the plate's cross extent. Its exposed height `h` is
   the median depth of that face under the plate. Measured: 28.0 / 26.0 / 20.5 m.
4. **SURROUNDINGS — lower ground at the foot.** The DEM steps down across the outer
   edge: the median over stations of DEM(inner edge − 5 m) − DEM(outer edge + 8 m)
   lies in [0.5 h, h + `foot_tol_m`] (`foot_tol_m` 0.5 m, so a top seated at the
   safety area never leaves its foot floating more than that). Measured: 16R 25.1 m
   (0.90 h), 16C 18.3 m (0.70 h), 16L 16–18 m (0.78–0.88 h).

The road at the foot is NOT a recognition witness (a river or a field at the foot is
the same structure); where a road (a road face or an OSM `highway` way) runs within
`max(h, 20 m)` of the foot, it is the lower ground §5 (3) releases. At KSEA all three
have one.

It is read once, in the airport stage, by a new module
`airport/walled_plate.py` (one responsibility: the recognition) over the placed
objects and the runway ends — BEFORE the partition's MSL guard, so a walled plate is
taken out of the guard's skip and partitioned like an on-ground row (M1). It publishes
one record per plate: the placement's origin set, E, the plate level `y_p`, the inner
edge stations `(lat, lon, y_p(t))`, the outer edge polyline, `h`, the foot polyline.

## §4 Rule 2 — THE SEAT: the plate's top is flush with the safety area

Recommended reading, Q2 (a). The placement (every body of its origin set; 22c/22f/22o:
one rigid group, the pier and the light deck ride it) takes ONE zero:

    zero = median over inner-edge stations i of ( z_solved(i) − y_p(i) )

`z_solved` the design surface the safety-area band produces at the plate's inner edge
(§5 (1) carries the band there). This is §16e (1)'s CREST-PLATE DATUM ("the crest
plate at the ground there"): the record stamps the member's existing `plate_y` = `y_p`
and `plate_stations` = the inner-edge stations (`airport/rebake_plan.py`), and
`airport/anchor_rule.py`'s datum anchor seats it; `open_frame_seat.rigid_open` takes a
datum body's zero first (its `dat[0]`), so no other body's lowest zero wins. The
deck verdict yields: a walled plate is never a deck `candidate` (M2), and its feet
are reported, never seated (§16e (3)). For a converted MSL row the seat replaces the
20s guard's on-ground conversion and the 20m feet seat, for this class only.

Measured (Q2 (a)), against the ground at each foot:

| End | Plate top now | Seat (a) | Δ | Foot (a) | Ground at the foot | Foot |
|---|---|---|---|---|---|---|
| 16R | 138.8 | 115.05 | −23.8 | 87.05 | 87.8–88.8 (road `-803`) | buried 0.8–1.8 m |
| 16C | 130.67 | 122.0 | −8.7 | 96.0 | 102.0–103.5 | buried 6.0–7.5 m |
| 16L | 132.07 | 124.2 | −7.9 | 103.7 | 105.6–112.0 | buried 1.9–8.3 m |

Q2 (b) — grade the safety area to the authored top instead (MSL rows keep 118.87;
the AGL row keeps the mesh at its origin, 126.38 − 10 = 116.38) — needs the band to
fall from the blast-pad end to the plate at **−5.5 % (16C, 130.0 → 118.9 over 199 m)
and −6.5 % (16L, 131.3 → 119.4 over 182 m)**, against the FAA safety area's 5 %
(RULINGS 2026-10-12q (1)(b)); 16R would take +1.3 m of fill at a lawful −3.5 %.
(b) is unlawful at two of three ends.

## §5 Rule 3 — THE GROUND

1. **The safety area ends at the plate** (Q1 (a)). The runway-end graded band
   (`planar/zones.py`, the one derivation site of the end box) is clipped at the
   plate's inner edge, as RULINGS 2026-10-20k clips it at water: no band face past the
   inner edge, no 1:3 bank (15c (3)) at the plate. Where the band stops short of the
   inner edge today (16L: a road beats it at s 275, 19a), the band's own longitudinal
   law is carried to the inner edge for the SEAT ONLY (the `z_solved` of §4 is read on
   the band's grade extended to the inner edge; the roads keep 19a). The end
   corridor's longitudinal law (12q (1)) and the transects (`constraints/strips.py`
   `end_transect_pairs` / `end_transect_foot`) read the shortened band.
2. **Under the plate the ground is hidden and never rises through it.** Every vertex
   whose plan point lies inside the plate takes a one-sided row
   `z_v ≤ z(inner station) + (y_top(v) − y_p) − clearance_m` (clearance 0.05 m;
   `y_top(v)` the plate's authored top over v) — the mesh may fall to the DEM under
   it (the step lives here, §7). This covers the top-of-plate service roads (16R
   `small_roads:-6086#3`, today +14.1 m over its DEM). A one-sided row between solve
   unknowns, the kind `one_way_rows` already are.
3. **Beyond the outer edge the wall is the step** (15a (2), 10-03c): the plate is
   published as a wall record in `PlanarMap.road_terrace['wall']` with `retains`, its
   UPPER side the safety area and its LOWER side the foot, through the ONE wall
   classifier (`airport/wall_class.wall_class_components` gains the walled plate as an
   admitted `WallComponent`, its line the outer edge polyline). The existing readers
   then release the lower ground: `constraints/wall_zone.split` (beyond the wall: the
   row is released), `constraints/road_ramp.wall_release` and `solve/wall_cut` (pair
   rows across the wall withdrawn), and the road at the foot keeps its own ground
   (19a / 19i / 19k — already law: measured today `-803` at 88.0–88.4 over a DEM of
   88.0–88.4).
4. **`wall_zone`'s "BEFORE THE WALL" flat plane does not apply to a safety-area row
   against a walled plate**: the band keeps its own longitudinal law up to the inner
   edge (§5 (1)); a flat plane at the runway-end level 4 h out would lift the 16R
   band by up to 10 m.

## §6 Consumer census (RULINGS 2026-08-30l) — every pass that reads the region

Region: the plate footprint, its inner edge, its outer edge, the ground at its foot.

| # | Consumer | Reads | Today | Under this spec |
|---|---|---|---|---|
| 1 | `airport/pack_partition.py` MSL skip (20s guard) | `origin_built` | PODs skipped, on-ground whole (M1) | a walled plate's origin set is partitioned; the guard stays for everything else |
| 2 | `airport/msl_feet.py` `origin_set_lifts` / `feet_seats` (20m) | the row's lift | guard → `None` (no lift) | not reached for a walled plate (row 5 seats it) |
| 3 | `airport/deck_signature.py` `classify` / `promote` | plate, evidence | 16R `candidate` | a walled-plate member is not a deck (`deck_kind` "") — trim at this one site |
| 4 | `airport/open_frame_seat.py` `rigid_open`, `group_zero` | `OPEN_KINDS`, datum bodies | 16R lowest zero | the datum body's zero governs (`dat[0]`); group zero unchanged for other groups |
| 5 | `airport/anchor_rule.py` §16e (1) datum, `airport/rebake_plan.py` (stamps `plate_y`, `plate_stations`) | `plate_y`, `plate_stations` | unset (null / []) | stamped from the record; REUSED, no new seat code |
| 6 | `airport/placement_seat_tilt.py` | the body's seat frame | 16R b0 tilted −0.96° | the plate datum is one plane; tilt cap (15a (3), 1°) unchanged |
| 7 | `airport/wall_class.py` → `classify/retaining_wall`, `planar/shore`, `airport/road_ramp` (`wall_pieces`, `wall_terraces`, `road_terrace`) | `WallComponent` | not admitted (not slender) | admitted with `retains`, line = outer edge; shore: no shore here, unchanged |
| 8 | `planar/zones.py` (end box, 20k water clip, 15c (3) bank) | the band region | full RSA length + 1:3 bank | clipped at the inner edge; no bank at the plate |
| 9 | `constraints/strips.py` (`end_transect_pairs`, `end_transect_foot`), `constraints/zones.py` (`zone_bands`, `strip_transverse`) | band rows | rows to s 305 | rows inside the clipped band only |
| 10 | `constraints/wall_zone.py` `split` / `flat` / `foot_ground` | `retains` walls | — | beyond: released (wanted); BEFORE: excluded for a safety-area row against a walled plate (§5 (4)) |
| 11 | `constraints/road_ramp.py` `wall_release`, `between_levels`; `solve/wall_cut.py` | wall records | — | pair rows across the outer edge withdrawn (wanted) |
| 12 | `planar/road_yield.py` (19a), `planar/road_shadow.py` (19ad) | roads in the band | 16L band stopped at s 275 by roads | unchanged; the seat reads the band's grade carried to the inner edge (§5 (1)) |
| 13 | NEW under-plate rows (§5 (2)) | plate footprint | none (16R road +14.1 m over DEM) | one-sided caps |
| 14 | `pipeline/publication.py` (`road_terrace['wall']` → sidecar) | wall records | — | the plate's record published like any wall |
| 15 | census `tools/harness/law_support/grade_law.runway_strip_wall_keepout_rings` (08-01: no retaining wall at a runway edge, end rect over the RSA length) | `retaining_wall` faces | no face emitted for an object | the end rect stops at a walled plate's inner edge (Q1 (a)); 15b's declared-wall forgiveness covers pairs across the outer edge |
| 16 | census `verify/strips.rsa_end_lengths`, the end-corridor family (12q (1)(d)), `law_support/strip_seam.WallFaces` | RSA length beyond the end | 304.8 m | the plate's inner edge |
| 17 | `airport/terrain_feature.py` | area ≥ 250,000 m² | not a feature | unchanged (≤ 5,425 m²) |
| 18 | `airport/airside_group_seat.py` (22q) | touches airside pavement | no (inner edges 182–243 m past the blast pads) | unchanged |

No consumer is edited before the rulings. The region is trimmed at its single
derivation sites (row 3 for the deck verdict, row 7 for the wall, row 8 for the band).

## §7 Emittability (heightfield mesh)

A heightfield cannot hold a vertical. The step from the safety area to the foot is
carried horizontally UNDER THE PLATE, between two constrained lines: the inner edge
(at the band's z) and the outer edge / foot line (at the lower ground). Plate depths
14.7 m (16C), 8.4 m (16L, t −80…+20), 26–30 m (16R): the mesh falls 18.3 m over
14.7 m (51°), 16–18 m over 8.4 m (62–65°), 24.6 m over ~27 m (42°) — steep triangles,
always below the plate (§5 (2)) and behind the wall face, never seen. The two lines
are 8.4 m or more apart, far above `emit.identity.min_distinct_spacing_m`, so the
identity merge keeps both. In front of the wall the mesh is the lower ground; a foot
above it is bounded by recognition witness 4 (≤ 0.5 m). Emittable at all three.

## §8 OWNER QUESTIONS

**Q1 — Does the safety area end at the plate?** Each plate stands 2.0–8.5 m short of
the FAA safety area's 304.8 m (15c (2)), and 2026-08-01 says a retaining wall is never
lawful at a runway edge (the census checks it over the whole safety-area length).
(a) The safety area ENDS at a recognised walled plate's inner edge: the graded band
stops there, the wall there is lawful (it is the safety area's end — your "built to
cap the runway end safety area"), and the census reads the shorter safety area.
(b) The safety area keeps its full length and runs under the plate. **Recommend (a)**:
under (b) at 16L the band reaches the plate's outer edge (304.7 m) and the 20 m drop
has to happen in FRONT of the wall face, burying its top — the look you reported.

**Q2 — Which sets the level: the safety area or the object?** (a) The object follows
the graded safety area: the plate's top is seated flush with the safety area at the
plate's inner edge, and its foot lands where it may (measured: every foot ends at or
below the road at its foot, buried 0.8–8.3 m; tops move 16R −23.8 m, 16C −8.7 m, 16L −7.9 m). This
replaces, for these objects only, the 2026-10-20s guard that keeps such MSL objects
on the runway's level today. (b) The safety area is graded to the object's authored
height. **Recommend (a)**: (b) needs the safety area to fall 5.5 % (16C) and 6.5 %
(16L) against the 5 % limit.

## §9 Acceptance (one KSEA closing build, after the rulings)

Site numbers, in this order: each plate's top − the safety area at its inner edge
within ±0.25 m (16R, 16C, 16L); no vertex under a plate above it (16R
`small_roads:-6086#3` 124.76 → ≤ plate top); each wall's foot at or below the ground
at its foot (≤ +0.5 m); the foot roads unchanged (±0.1 m: `-803`, `-12798#1`,
`-1163`); no safety-area band face past an inner edge (16C today 6.4 m past). Then:
runway, taxiway and apron movers 0; the census's adjudicated airside count not up;
a dry census of the walled-plate recognition over every registered capture lists
what it admits (expected: these three; any other admit is reported before merge).

## §10 Implementation plan (after the rulings; one Opus lane, medium)

1. `airport/walled_plate.py` (new: recognition, the record); twin over a synthetic
   placed plate + wall + DEM step, and three negatives (no wall, no step, off-axis).
2. `airport/pack_partition.py`: a walled plate's origin set bypasses the MSL skip.
3. `airport/deck_signature.py`: no deck verdict for a walled-plate member.
4. `airport/rebake_plan.py`: stamp `plate_y` / `plate_stations` from the record.
5. `airport/wall_class.py`: admit the plate as a `retains` `WallComponent`.
6. `planar/zones.py`: clip the end box at the inner edge.
7. `constraints/wall_zone.py`: exclude safety-area rows from "BEFORE THE WALL" at a
   walled plate; `constraints/` new under-plate cap rows (a new module, one family).
8. Census rows 15–16 (`grade_law`, `verify/strips`).
Register the new module in `O4_Step_Code._SHARED` / `provenance_code.PATCH_CODE_MODULES`.
Build-time impact: the recognition reads geometry the partition already parses, per
placement near a runway end only — expected < 0.1 s per airport (< 1 % of the 60 s
budget); the cap rows add ≤ a few hundred one-sided rows.

## §11 What the owner looks at in the sim

North of the 16C and 16L thresholds (about 300 m past each, where the approach lights
leave the runway's safety area), and north of the 16R threshold at the same distance:
the long concrete structure across the end of the safety area, the service road
along its foot. Today the 16C and 16L structures should stand roughly 8 m ABOVE the
grass of the safety area and the 16R one roughly 20 m above it, their bases floating
over the road; after the fix their
tops are flush with the grass and the road runs at their foot.
