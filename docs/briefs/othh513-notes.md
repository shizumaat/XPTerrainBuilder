# othh513 — OTHH owner sim read of app 1.0.385 (#513, #514, #515)

Lane branch `claude/othh513`, base main `d1f5a0dc0`. All reads below are of
files; nothing in the X-Plane install, the shared data repo or the app logs
was written.

## Frames

| era | engine | artefact |
|---|---|---|
| app 1.0.383 (owner's previous OTHH read, 07a) | main 798702f2, BEFORE walls #464 / §18 | pack DSF dump `Airport_mod_cache/…/+25+051.dsf.0dd541a6.text` (Oct 7 05:10), patch `/tmp/harness/sw1007_OTHH.*` |
| walls merged (#464) | main d0b2f0f4 | `/tmp/harness/sw6_OTHH.*` |
| app 1.0.385 (this read) | main 616e5d58a | patch `/tmp/harness/sw11_OTHH.*` (body eb7565539e36) = the owner's own `Patches/+20+050/+25+051/OTHH_auto.patch.osm` (body identical); as-built pack DSF dump `+25+051.dsf.5ae81e87.text` (Oct 10 07:41); as-built tile mesh `zOrtho4XP_+25+051/Data+25+051.mesh`; as-built plan `o4_v2_placement_OTHH.json` |
| author | pristine pack DSF | `+25+051.dsf.anchor_bak.4229c95f.text` |

NOTE on the brief: app 1.0.383 was frozen 2026-10-07 02:54 on main 798702f2 —
BEFORE the walls branch (#464, §18 authored seats). The app log shows no app
run between Oct 7 21:07 and Oct 10 07:19, so 1.0.384 was never run by the
owner: this read is the FIRST sim read of §18.

## FINDING A (one mechanism under all three issues) — the DSF writer drops the author's elevation column on the rows §18 keeps

Spec §18 (3) (b): a placement authored to the cut is KEPT — "the writer
writes nothing for it (no split file, no baked offset, no DSF row)".
`pipeline/authored_seats` keeps it out of every seat and the rebake plan
publishes 15 `authored (cut)` records at OTHH. But
`airport/placement_write.build_plan` never read those records:
`dsf_write.conversions_for_dump` converts EVERY `OBJECT_AGL` / `OBJECT_MSL`
row to a plain on-ground `OBJECT`, and §16g (5) seats a multi-anchor
resource by `OBJECT_MSL`. For a kept placement the elevation column IS the
author's seat, so the conversion moves the object by exactly its authored
lift.

As built in the owner's 1.0.385 pack DSF (dump 5ae81e87) against the
pristine DSF:

    OBJECT_AGL 1338 51.604849508 25.295771820  4.298496986 158.265965   (author, Drainage_01)
    OBJECT     1338 51.604849508 25.295771344 158.265965               (1.0.385)
    OBJECT_AGL   83 51.603116178 25.253681716 -5.500236515 0.000000    (author, tunnel south west 2)
    OBJECT       83 51.603115702 25.253681716 0.000000                 (1.0.385)

`o4_v2_placement_OTHH.json` lists all 13 pit rows (36156–36168) and 7 wall
rows (36223–36229) under `conversions`, and the two `tunnel1` rows
(36230/36231) under `msl_seats`.

### As built, on the owner's own tile mesh (grade 3.96 m)

`<scratch>/othh513/asbuilt.py`: each DSF row's anchor sampled in
`Data+25+051.mesh` (`tools/mesh_elevation_sampler.py --point`), origin =
mesh (+ AGL) or MSL, plus the OBJ's own y range.

Pits (#513 north end, #514 south end). "zero" = the object's y = 0 plane =
its rim.

| object (rows) | end | author's row on the 1.0.385 mesh: rim vs grade | AS BUILT 1.0.385: rim vs grade | as built: body bottom vs the cut floor |
|---|---|---|---|---|
| Drainage_01 (36164/5) — 32 m from the #513 site | N | −0.01 | **−4.31** | 3.82 m BELOW the −0.35 floor |
| Drainage_02 (36162/3) — the #451 north site | N | −0.01 | **−4.31** | 3.82 m below |
| Drainage_03 (36160/1) | N | −0.01 | **−4.31** | 3.82 m below |
| Dewatering_01 (36166–8) — 174 m from the #513 site | N | −0.14 | **−13.64** | 13.14 m below the −9.68 floor |
| Drainage_04 (36158/9) — #451 south site 1 | S | −0.01 | **−4.31** | 3.82 m below |
| Drainage_05 (36156/7) — #451 south site 2 | S | −0.01 | **−4.31** | 3.82 m below |

The mesh under every one of those anchors is the CUT FLOOR (−0.350 /
−9.680): the cut is emitted, in the right place and at the depth the author
lifted for (4.2985 = 3.816 plate + 0.5 clearance − 0.017). With the author's
row every rim lands 1 cm under grade. The object is sunk by its own lift
because the row lost it. No #337 / gap sheet is involved: at the #513 site
the sheet `gap:20` carries an interior ring 0.7 m outside the rim and stands
at 3.96 like the rim (09e (2) holds).

Walls (#515). "crest" = the wall's flat top plate.

| wall (row) | author's AGL | author's row on the 1.0.385 mesh: crest vs grade | AS BUILT 1.0.385: crest vs grade |
|---|---|---|---|
| tunnel south west 2 (36223) — the #515 site | −5.500 | +2.13 | **+7.63** |
| tunnel middle - east (36225) | −3.000 | +2.00 | **+5.00** |
| tunnel middle - west (36226) | −3.000 | +1.97 | **+4.97** |
| tunnel west 3 (36224) | +0.999 | +2.59 | **+1.59** |
| tunnel west 1 (36228) | +2.499 | +2.40 | **−0.10** (flush) |
| tunnel west 2 (36227) | −0.000 | +1.59 | +1.59 |
| tunnel_sw (36229) | −0.000 | +1.58 | +1.58 |
| tunnel1 ×2 (36230/1) | −5.000 | +1.99 | +1.96 (`OBJECT_MSL −3.625`: §16g (5) re-seat, 2 cm off by chance) |

The author's rows give 1.58 – 2.59 m (median 2.0) — the numbers §18 and
07c/07f were ruled on. As built three walls stand 5.0 – 7.6 m over grade,
one a metre low and one flush. The ground beside the walls did NOT come
down: outside ground is 3.96 in sw6, sw10 and sw11 (rim ring
`structure_rim:tunnel_wall` at 3.96, ramp ring identical).

The owner's "close to 3 m" at 25.2538736, 51.603365 is NOT what the files
give there: the wall at that site (`tunnel south west 2`) measures +7.63 m
as built. Reported as measured; either way the fix returns it to +2.13.

### Before (1.0.383)

Different mechanism, same objects: before §18 the lifted pits were not read
as ground-seated, so NO basin was cut under them (#451 "drainage trench is
missing": `sw1007_OTHH.osm` has no ring at any of the five anchors) and
their rows were converted and split (`Drainage_01_LOD0_001__b0/__b1` …);
the walls were split and plate-re-seated (`tunnel south west 2__b0`). §18
(#464) then cut the trenches the author lifted for and stopped re-seating —
and exposed the unconditional row conversion.

### Fix (general rule, no airport/pack name)

`airport/placement_write.dump_rows` (new: the ROW half of the plan, one
implementation for `build_plan` and `tools/obj8_split_report.py`, which
carried a second copy): a row whose placement is in
`RebakePlan.authored_seats` with `seat == "authored (cut)"` (the record's id
and `members`) is SETTLED like a split row — never converted, never given a
§16g (5) elevation, never a rider. `airport/authored_seat.kept_ids` /
`kept_rows` (`pipeline/authored_seats.kept_ids` now delegates). Count
`authored_rows_kept` in the plan's provenance.

### Intervention (offline, on the 1.0.385 plan)

`tools/obj8_split_report.py /tmp/harness/sw11_OTHH.v2/OTHH.rebake.json
--graded …/OTHH.graded.json --dsf-dump …/+25+051.dsf.anchor_bak.4229c95f.text`
on the lane tree (the report now prints the row half through the writer's
own `dump_rows`): **22 rows keep the author's seat, all 22 "kept as
authored"** (13 pit rows 36156–36168, 9 wall rows 36223–36231; the two
`tunnel1` rows no longer take an `OBJECT_MSL`). As built the same plan
converted 20 of them and MSL-seated 2. The author's rows on the owner's
mesh are the "author's row" columns above: rims −0.01 / −0.14 m, crests
+1.58 … +2.59 m.

(The guard flagged a shared-repo side effect on that run: 12
`Airport_mod_cache/NLWF-…` paths and 2 `Masks/-20-180/-15-179` — the
owner's app building NLWF at the same time, not this read-only tool.)

## FINDING B — #514's other half: the south-end pits the engine RE-SEATS (plain rows, no lift)

`Drainage_06` (rows 11323/11324) and `Dewatering_02` (11325/11326) are
plain `OBJECT` rows: §18 gives them no record ("a plain placement … seats
as its law always did"), so they are split and re-anchored. With the
AUTHOR's rows on the 1.0.385 mesh they would be exact (anchor on flat
ground beside the pit: rim +0.01 / 0.00). As built:

| body | class / anchor rule | as built: rim vs grade | note |
|---|---|---|---|
| `Drainage_06_000__b0` (the 283 × 179 m L-shaped trench shell, basin:0) | `skirted` / "low-side foot" on the trench floor | **−2.68** (bottom 0.92 m under the −0.74 floor) | B1 |
| `Drainage_06_000__b1`, `06_001__b1`, `__b2` (basin:7) | `basin` / rim vertex `basin_wall:7@1065` | **−0.15** | B2 |
| `Dewatering_02_LOD0_001__b0`, `_002__b0` (basin:6) | `basin` / rim vertex `basin_wall:6@1063` | **−0.23** | B2 |
| `Drainage_06_001__b0` (basin:0), `__b3` (basin:9) | `basin` / rim vertex | 0.00 | |
| `Dewatering_02_LOD0_002__b1…b10`, `_001__b1/b2` (8–12 cm fittings authored +3.2 … +5.0 over the rim) | `plate_only` / `other`, "footless_own_ground" | **−13.64** (on the pit floor) | B3, same anchors and file hashes in the 1.0.383 DSF |

**B1 — a concave shell's centroid is outside its own ring.**
`placement_cut._rim_of` / `anchor_rule.rim_of` ask whether the body's
LOWEST COMPONENT stands inside an emitted basin ring by that component's
PLAN CENTROID (`Part.lat/lon`). The trench shell's centroid
(25.25354708, 51.62568384) is 19 m OUTSIDE its L-shaped ring
`basin_wall:0`, so the body is not `basin`, falls to `skirted`, and the
generic rule anchors it at its low-side foot on the trench floor (−0.74).
INTERVENTION (scratch `b1_intervention.diff`, not landed: the ring is the
centroid's, else the one MOST of the component's own feet stand in; three
call sites — `placement_body.py:178`, `:512`, `anchor_rule.py:996`):
`Drainage_06_000__b0` becomes `basin`, anchored `basin rim
(basin_wall:0@1052)`, y_zero 0, surface 3.96 → rim at grade. Side effect
seen in the same run: `Drainage_06_001` forms 3 bodies instead of 4 (the
basin:9 body merges), so it is body-formation law (§14 / §14a), not a
one-line fix. The 1.0.383 DSF also anchored this body inside the trench
floor (25.253837167, 51.624824998): standing, not a regression. NOT FIXED.

**B2 — a rim-vertex anchor falls onto the wall face in the DSF.** The
basin rule anchors a body ON a rim-ring vertex (surface 3.96). The DSF
stores coordinates on a 0.03125°/65535 pool grid (5.3 cm N–S, 4.8 cm E–W);
the written row lands up to a quantum off, and INSIDE the ring the mesh is
the wall band (4.7 m or 13.6 m of fall in 0.707 m). Measured on the owner's
mesh: plan anchor 25.25207633841, 51.6246568 → 3.960; written row
25.252076181, 51.624656672 → **3.733**; plan 25.25375087599, 51.62468183911
→ 3.960; written 25.253750858, 51.624681468 → **3.810**. Two other rim
anchors quantised outward and read 3.960. Standing since the basin-rim
anchor exists (same rows in the 1.0.383 DSF). NOT FIXED — candidate rule:
the rim anchor point is taken one DSF quantum or more OUTSIDE the ring.

**B3 — fittings over a covered pit seat on the pit floor.** Standing
(identical rows on 1.0.383); 8–12 cm objects, 13.6 m under their authored
place. NOT FIXED.

### "The basin seems a bit too big … a visible gap" — which rule sizes the cut

Every pit here but basin:9 reads `shell 0.00 m thick` (the drain objects
have SLOPED BANKS, not a vertical wall: floor plate 66–782 m² inside a
467–3,824 m² outline, so `shell_thickness_m` finds no wall face). §47 (3)
then says the shell is thinner than the lattice floor 0.7071 m, the FLOOR
ring stays on the object's outer face and the RIM YIELDS OUTWARD by
`rim_yield` 0.707 m. So in plan the cut is the object's outline + 0.71 m on
every side, and that 0.71 m is the mesh wall band falling from grade to the
floor: a slot 0.71 m wide and 4.3 m (13.6 m) deep all round the object. The
floor is `solid_min − floor_clearance_m 0.5` (plate −3.816 → terrain
−4.316 under the rim: −0.35 MSL; Drainage_06 plate −4.201 → −0.74;
Dewatering −13.142 → −9.68). basin:9 (`Drainage_06_001` b3, a walled sump,
shell 0.78 m) has no yield: its rim is its outer face. Same rule, same
numbers in sw6, sw10 and sw11 — it is the §47 design, and the fix of
finding A does not change it: with the author's rows back the rims stand
at grade INSIDE a cut 0.71 m wider than the object. INTENT QUESTION for the
owner (see the report).

## Closing

- Closing build `othh513_OTHH` (harness, `/tmp/harness/othh513_OTHH.*`,
  frame registered): rc 0, patch clock 636.5 s (bar 660; background run
  beside the owner's app), body **eb7565539e36** == sw11 (the fix does not
  touch the patch), rebake plan sha 8e24e55b3f68 == sw11 (15 authored
  seats, object-framed ramps, wall rims, tunnel ramps unmoved).
- The airport harness build has no DSF write half; the fix is read by the
  offline row report above (22 rows kept as authored) and by the twin
  `tests/auto_patch_v2/test_authored_seat.py::test_a_kept_seat_keeps_its_dsf_row`.
  The first tile build of the next app rewrites the pack DSF from the
  pristine `.anchor_bak` and restores the 22 rows.
- Suites: `tests/auto_patch_v2` + `test_no_airport_specific_code.py` +
  `test_harness.py` green; `tools/ratchets.py` duplicate + layer ratchets
  PASS, no size warning on a touched file.
