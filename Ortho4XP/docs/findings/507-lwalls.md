# #507 — the step across a declared pack-wall terrace exceeds the wall (lane lwalls): ATTRIBUTION, no fix

Site: HECA 30.12155524, 31.41995156 — aprons `dsf:objpav1` (upper) and
`dsf:objpav402` (lower) across service road `small_roads:-18656`, at the pack
wall `Airport/Hangar/metal_strip_2.obj` comp 12 (3.10 m, outline 292.7 m).
PR #1065 (RULINGS 2026-10-19ao, census only) left one CRITICAL
`terrace_actual_step` row: 3.70 m over 4.73 m against an allowance of about
3.29 m.

## Current main (fresh HECA capture at 5acfc6f39 = main 59fa7241d + #1197, which changes no HECA component; `--replay --from constraints`, harness census)

* Emitted nodes within 2.4 m of the site: 98.45, 97.26 and 95.70 m — the
  step across the wall reads 2.75 m, under the wall's 3.10 m.
* `terrace_actual_step` rows within 80 m of the site: **0** (33 airport-wide).
  The CRITICAL apron/apron row is gone on main; what stands at the site now
  is `hard_conflict` on the service road (`roads.groundside_road ramp
  ceiling`, worst 3.15 m) and `within_shape apron|service_road` 3.4–3.8 m
  about 48 m east along `small_roads:-18656`.

## Why no code here

1. The defect as filed does not reproduce on main.
2. The proposed geometric bound would add a row between two AIRSIDE aprons
   from a pack wall. The existing bound (`constraints/road_ramp._wall_step_rows`,
   #715) is a stage-2 one-way floor at RETAINING walls; the apron/apron step
   is solved in stage 1, where no wall row reaches. RULINGS 2026-10-19ao
   says "the geometry is not changed by this ruling", so moving an airside
   apron by a pack wall needs the owner's word first.

Recommended: close #507 on the next batch's HECA census if it reads 0
`terrace_actual_step` at the site; the service-road `hard_conflict` there is
a separate road-ramp question.
