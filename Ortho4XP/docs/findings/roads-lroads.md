# Public roads follow the terrain inside the band (#1254, #947; lane lroads)

Law: owner RULINGS 2026-10-22h (Q111, "111. Yes"). A mapped road of a
PUBLIC class (not airside, not `service` or another airport-internal road;
read off the existing road classification, never a geometry window) takes
the DEM's grade wherever the DEM along it is steeper than
`[common] road_max_grade` (10 %), instead of being capped. Airside and
service roads keep the cap. The band is the one RULINGS 2026-09-18n already
scopes (`[road_profile]`: the patch coverage buffered `lane_width + 2`, plus
the `runout_m` run-out along the way). Airside is king (no groundside pull
on airside) is unchanged.

## Attribution (LGAV capture at 59fa7241d, `v2_solve_replay --capture LGAV`)

Site: the hill east of the field, residential ways -1190 / -4571 at
37.95169, 23.98665 (RULINGS 22h's site).

Base replay (`--replay --from constraints --emit`), `road_course_profile
--detail=-1190`:

- -1190 is on the patch from s = 56 to s = 248 m. Over that run the DEM
  climbs 16.1 m in 144 m (11.2 % mean, 16 % locally); the patch climbs at
  exactly 10.0 % (0.40 m per 4 m sample) and ends 2.45 m BELOW the DEM at
  s = 200 (153.13 vs 155.22). The patch-edge step at s = 52/56 is 0.78 m.
- The coverage-edge join at v22038 (37.95110, 23.98636) is released by
  27a (10): core ribbon 160.23 m against the patch's 152.54 m, excess
  -7.69 m — the largest join yield on the airport.
- `--why-at 37.95118,23.98655` (worst vertex v22049, z - DEM = -4.49 m):
  the binding chain ends on the `road_ramp` ramp ceiling BAND (z <= target
  + visual) at v22063, then climbs through `road_within_shape` (+4.48 m at
  10 %) and `pavement_road_cap` (+2.02 m at 10 %).

So three solve consumers hold the road at the cap: the ramp TARGET (whose
floor is the core clamp at `road_max_grade` inside the band), the
within-shape longitudinal rows, and the hard fallback/ceiling twins at
`road_max_grade`. The core (`O4_Vector_Utils.clamp_road_network`) clamps the
same in-band segments at the same cap, so the ribbon outside the patch
carries the same capped profile out through the run-out.

#947 ("roads around airports are bumpy or have sudden sharp drops"): at
the LGAV hill the drop is this mechanism — the capped road leaves the
DEM by up to 2.45 m inside the patch and meets the terrain with a step at
the patch edge and a 7.69 m join yield at the coverage edge. The other
LGAV patch-edge steps over 0.5 m (`road_course_profile --reach 200`: 23,
worst -2914 / -4017 6.98 m at 37.9315, 23.9399) sit at structures (the
Attiki Odos trench, #1138/#1246) and are not this mechanism.

## The rule (one derivation, every consumer reads it)

1. **Public class** (`emit.toml [road_profile] public_classes`): the OSM
   `highway` values of the existing class table that are public roads —
   motorway … tertiary (+ `_link`), unclassified, residential,
   living_street, road. Not `service`, not `track`. One list, read by the
   core and by v2 through `O4_Cfg_Vars.road_neighbourhood_law`.
2. **The in-band cap of a public way is the ceiling** (`[road_profile]
   cap_ceiling`, 30 %, "nothing above this is a road any class drives"):
   `O4_Vector_Utils.road_inside_cap(way_class, cap, cap_ceiling,
   public_classes)`, called by the core's `clamp_road_network` and by v2's
   `road_profile.core_profiles`, so the core ribbon, v2's fit target, the
   ramp floor and the coverage-edge join stay ONE profile. The clamp is the
   identity wherever the terrain is under the cap, so a public road on its
   own terrain IS the terrain. Service roads, tracks and untagged ways keep
   `road_grade_limit`.
3. **The release** (`constraints/public_road.py`, the last assembly
   post-pass): on the faces of public ways whose own ramp target
   (`PlanarMap.road_ramp_z`) is steeper than the road cap
   (`PlanarMap.public_road_lifted`, derived once in
   `airport/road_ramp.with_road_ramp`), every difference row between two
   RELEASED vertices — a vertex of such a face that is not airside
   (§20b stage 1), not a band kerb, and touched by no other pavement face —
   is widened to the target's own difference over that pair (x 1.001). A
   row is never tightened. Cross-sections stay level because the target is
   one value per (route, station) (§37 (8)).
4. **The census honours the lift**: `publication.lifted_caps` carries the
   released faces (face -> the steepest target grade), so the v1 census's
   `o4_grade_law_cap_lifted` tag and v2 verify's `Patch.of(lifted_caps=…)`
   take them as the §34 (9) lift; `check_grade.pavement_over_road_cap`
   skips a pair whose ways both carry the lift (the engine copy releases
   the same pair).

## Consumer census (RULINGS 2026-08-30l)

| # | consumer | reads the cap how | ruling |
|---|----------|-------------------|--------|
| 1 | core `clamp_road_network` in-band segments | `cap_inside = road_grade_limit` | public way: `road_inside_cap` (rule 2) |
| 2 | v2 `road_profile.core_profiles` (fit, ramp floor, join) | same | same helper (rule 2) |
| 3 | `road_ramp` ramp ceiling band `z <= target + visual` | reads the target | unchanged (target changes) |
| 4 | `road_descent` mouth ramps | design grade, steepened to the cap | unchanged: leaving airside is the cap's case |
| 5 | `roads.road_within_shape` longitudinal / cross rows | `cap_l·Δs + cap_t·Δt` | released (rule 3) |
| 6 | `ceiling.pavement_ceiling` road twins | `road_max_grade` | released (rule 3) |
| 7 | `pavement_cap.pavement_road_cap` | `road_max_grade` | released (rule 3) |
| 8 | road terrace / reach seed / between-levels (stage 2) | stage 1 levels, cap runs | unchanged; measured |
| 9 | `check_grade` within_shape, v2 `verify.within` | role cap; §34 (9) lift | lift via `lifted_caps` (rule 4) |
| 10 | `check_grade.pavement_over_road_cap` | `PAVEMENT_ROAD_CAP` | skip lifted|lifted pairs (rule 4) |
| 11 | step families, cross_shape, road_cross_section | steps / transverse | unchanged; measured (level sections) |
| 12 | `road_coverage_join` census family | the join pin | unchanged (one profile, rule 2) |

## Acceptance

- LGAV site: -1190 and -4571 within 0.5 m of the DEM at the patch edge and
  along the patch where the DEM is steeper than 10 %; no public-road chord
  on the patch steeper than max(road_max_grade, the DEM's own grade along
  it) beyond the 12y visual bar; the 7.69 m join yield at v22038 gone.
  (The brief's "no public road chord over road_max_grade" contradicts
  RULINGS 22h, which makes those chords lawful where the DEM is steeper;
  this file reads it as "no chord steeper than the terrain allows".)
- Zero new adjudicated census rows against the base replay (same capture).
- Airside unchanged: stage 1 is untouched by construction (no released
  vertex is a stage-1 vertex); measured as the airside max |dz| between
  arms.
- Closing build: LGAV through `tools/harness/build_airport.py`.
