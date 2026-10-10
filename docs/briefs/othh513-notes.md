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
