# #1254 lane lroads — handoff (paused by owner order, 2026-10-27)

Branch `claude/lroads-grade` (PR #1473). Spec, attribution and the round 1/2
tables are in `Ortho4XP/docs/findings/roads-lroads.md`. Round 3 (RULINGS
2026-10-27f + 2026-10-27s) is implemented and committed at 2ece91548; this
WIP commit adds only this note and the frames registry line.

## Done (round 3)

- Law: `rulesets.toml [common] road_joint_free_grade_change = 0.08`,
  `road_joint_k_m_per_pct = 3.0` (RULINGS 27s), and the fields in
  `law/model.py CommonLaw`.
- `airport/road_joint.py` (new): `junction_joints` finds each sized joint
  (the side street, whose centreline ends on the main road's,
  `_side_end`). It moves the street's mouth vertices onto the main road's
  frame at the main road's level, then sizes the street from the joint with
  `transition`:
  - it leaves within 8 % of the main road's grade along the street;
  - it then changes grade at no more than 1 % per 3 m;
  - it lands on its own clamp; peak grade is capped at `cap_ceiling`.
  It also reframes street-face vertices the frame had handed to another route
  (LGAV v22038, which was on the track -1258).
  READING TAKEN: the 8 % free break, then K = 3 m per 1 % for the rest of the
  change (the "excess" reading of 27s). The stricter reading is "no free break
  when the change is over 8 %". Owner or master to confirm.
- `constraints/roads.road_pair_reading`: a pair across two routes within
  `pair_lateral_m`, whose frames carry two DIFFERENT junction roads, is the
  street's longitudinal grade. The junction road is the fourth frame field:
  `PlanarMap.road_junction_road`, published as the sixth `road_route_frame`
  field and read by the generator, v2 verify and `check_grade`.
  Only a sized joint's vertices carry it; an unsized crossing keeps 2 %.
  (Tagging every public route instead minted 3 `cross_shape` rows at unsized
  junctions — arm a7, now refuted and replaced.)
- Registries: `road_joint` is in `stage_code`, `O4_Step_Code` and
  `provenance_code`; the closure twins pass.
- Tests: `tests/auto_patch_v2/test_public_road_release.py` adds the
  junction-mouth reading and a 4-case transition twin.
  It passes along with `test_law_tables` and `test_constraints` (51 passed).
- Ratchets: duplicate, near-duplicate, unused, layer and lint all pass.

## Measurements (LGAV capture `/Users/noah/XPTerrainBuilderData/.harness/frames/lroads/LGAV.pkl`, replay arm a9 = the committed code)

At the -1276 / -1190 junction, 37.95121, 23.98649 (about 1.4 km due east of the
runway 21L threshold):

- The 0.60 m `mid_edge_step` is gone. Against round 1 (arm a3) the census
  has 0 new rows and 4 fewer (3 `mid_edge_step`, 1 `vertex_to_edge_step`).
  Adjudicated is 1690 (round 1: 1694, base: 1707); airside stays 1437.
- Joint grade changes, read off the emitted ring vertices, are all within the
  8 % free change:
  - 10.3 % on the main road's surface, then 15.8 % entering the street
    (5.5 %);
  - about 4 % at s 800 and about 6 % at s 776.
  Joint report: kerb 153.37 m, main grade along the street 11.0 %, street
  chord grade 14.6 %, transition 47.8 m.
- The side street's worst gap to the DEM over its last 60 m is about 2.05 m
  (s 804: 154.59 against 156.64). The joint itself is 1.87 m under its DEM
  (153.29 against 155.16), because the main road's levelled kerb already
  sits 0.7–1.4 m under its own DEM there. The arm without a transition had
  0.52 m but carried the step.
- Source: `road_course_profile --detail=-1276:764:831` on the a9 emit, and
  `scripts/faceverts.py` on the a9 solved pickle. Both are in the lane
  scratchpad, which will not survive: re-run the replay.

## Closing build (round 3)

`build_airport.py LGAV --tag lroads3`: rc 0, body_sha 7cf338b6646b, built in
715 s. It is registered as the frame
`/Users/noah/XPTerrainBuilderData/.harness/frames/lroads/lroads3.osm`.
It has NOT been censused yet. The artifact ledger did not store it (the shared
repo changed during the run).

## Exact next step

1. `venv/bin/python tools/harness/census.py /Users/noah/XPTerrainBuilderData/.harness/frames/lroads/lroads3.osm`.
   Expect adjudicated 1690, as replay a9 gave.
2. Run `road_course_profile --capture <LGAV.pkl> --detail=-1276:764:831` on
   that patch. Confirm the profile and that the mid-edge step is gone.
3. Re-run the full non-Qt suite. It was stopped at 99 % with one F, file
   unknown. Two failures already known to be outside this change:
   - `test_v2dsfagl::test_real_pack_roundtrip_and_idempotent_write` fails on
     clean main;
   - `test_bathymetry_band_stamp` fails only in the lroads tree.
4. Merge origin/main. Push. Update the PR body so it starts with
   "Fixes #1254" and has a round 3 section quoting the numbers above. Drop
   the "Round 2: stopped" wording.

## Open questions

- Which reading of 27s: the 8 % free break plus K for the rest (taken), or
  no break at all when the change exceeds 8 %?
- The about 2 m gap to the DEM at the joint follows from the main road's
  levelled kerb. Accept it, or should the main road's section tilt at the
  mouth?
- Junctions where the side street is too short for the transition: 14 at
  LGAV are left as they are (counted as `too_short` in the
  `junction_joints` report).
