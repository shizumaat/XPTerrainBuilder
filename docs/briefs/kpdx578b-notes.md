# kpdx578b — lane notes (OTHH basins moved by #578)

## RESUME HERE
- Branch `claude/kpdx578b` from main cf3f752ac. STOPPED for a ruling: the
  correct fix does NOT restore OTHH's pre-#578 basin set (45); it gives 20.
  No harness build was run (OTHH, KPDX) — waiting on the choice below.

## Attribution (replays of pads67/OTHH.pkl, `--from planar`, one change per arm)
| arm | basins | refused | under min area |
|---|---|---|---|
| main cf3f752ac (#578) | 49 | 95 | 41 |
| #578 with `_edge_on` off | 45 | 99 | 37 |
| #578 with the bare union back in `skirt._plan_union` | 49 | 95 | 41 |
| #578 + `frame_entry.enter` fixed | 20 | 124 | 12 |

- `skirt._plan_union` through `frame_entry.union` changes nothing.
- `_edge_on` is the TRIGGER, not the cause. On the two jetway resources
  (OTHH_Jetway_Type5/4.obj, 150,948 / 146,922 triangles) it drops 3,896 /
  3,884 triangles, all steep faces, 0.0001 m2 in total, widest 0.9 um; the
  plan union and the above-zero union are unchanged to 0.001 m2.
- The four basins: own cover basin:20 93 % -> 77 %, basin:56 99 % -> 56 %,
  basin:79 96 % -> 0 %, basin:98 97 % -> 0 %, because `obj8.at_grade_geometry`
  returned polygons `None` for ONE of each pair of jetway placements
  (dsf:obj8568, dsf:obj8508) where it returned 45.76 / 40.6 m2 before.

## Mechanism
`frame_entry.enter` loses a VALID footprint. Placed and snapped to 1 mm the
jetway's 43 m2 above-grade MultiPolygon (25 parts) is invalid; each
(make_valid, re-snap) round hands make_valid its own GeometryCollection and
nests it once more; after the 4 rounds + the closing make_valid it is deeper
than `_MAX_PART_DEPTH = 4`, the unroll stops on a collection, the polygon
filter keeps nothing and `enter` returns `None`. Not named anywhere: the
caller reads "no cover". Reproduced standalone on the resource at clip
planes -0.35 and +0.25 (of 17 swept) with `_edge_on`, none without — the
needles only move which inputs need the long ladder.

## The conflict
With `enter` fixed, 25 basins that pre-#578 main ADMITTED are refused as
basements: all 25 sit on jetways (Type7 x10, Type4 x7, Type5 x3, Type6 x3,
Type10, Type8); their own cover read 0-70 % only because one member's
footprint had entered as nothing; it reads 94-99 %. No new admission.
10 jetway basins stay admitted (35 jetway basins in all).

## Fix on the branch (not merged, awaiting the ruling)
- `airport/frame_entry.py`: the parts are unrolled until flat;
  `_MAX_PART_DEPTH` removed.
- Twins in `tests/auto_patch_v2/test_v2witnessvalid.py` (2) + fixture
  `fixtures/enter_deep_repair_578.wkb` (26 kB).
