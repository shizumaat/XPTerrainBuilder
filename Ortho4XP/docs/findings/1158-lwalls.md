# #1158 — pavement must not cross a pack retaining wall (lane lwalls)

Law: owner RULINGS 2026-10-20ak (pavement never crosses a pack retaining
wall; the part past the wall's lower face is misplaced and clipped at the
wall), 20ax (a wall cuts pavement into separate shapes; a noticeable step
means two levels with the change hidden in the wall; pack-own and borrowed
pavement alike), 20al (borrowed pavement gives way to clear pack objects),
20ba (a clear elevation step is more than 2 m within less than 3 m), 20ai
(the lower level is the real ground past the wall foot).

## Attribution (dry, KATL capture at the #1197 commit; `classify/wall_clip` over `airport.pavements`)

Cutting walls (retain their height, taller than 2 m): `muro_27R`,
`muro_concreto`, `muro_concreto5`, `muro_ladrillo`.

| pavement | wall | over the footprint | on the upper band | on the lower band | verdict |
|---|---|---|---|---|---|
| `pav14` (Global) | `muro_concreto` | 935 m² | 3,291 m² | 576 m² | OVERHANG: 576 m² past the lower face leaves (the #1139 lane measured 653 m² past it; the rest is where the wall's step is under 0.75 of its height, at its ends) |
| `pav14` (Global) | `muro_concreto5` | 644 m² | 103 m² | 13 m² | overhang 13 m² |
| `pav4` (Global) | `muro_concreto5` | 78 m² | 1,078 m² | 1 m² | overhang 1 m² |
| `dsf:pol22` (pack) | `muro_concreto5` | 399 m² | 1,326 m² | 165 m² | TWO-LEVEL: runs on past both bands; footprint only |
| `dsf:pol43` (pack) | `muro_concreto` | 119 m² | 1,141 m² | 0 | footprint only |
| `dsf:pol46` (pack) | `muro_concreto5` | 11 m² | 108 m² | 0 | footprint only |

## Rule (`classify/wall_clip`, called once from `classify/evidence.build_evidence`)

1. WHICH WALLS: wall-class components that retain their own height
   (`airport/wall_class`) and stand taller than `[service]
   retaining_wall_clear_step_m` = 2.0 (20ba).
2. THE SIDES: `airport/wall_class.retaining_sides` reads the witness's own
   across samples (every 2 m round the ring `max(3 m, h)` out): a sample
   whose ground stands at least `retaining_wall_step_min_fraction` (0.75) of
   the height the wall retains (`WallComponent.retained_m`: its solid height,
   or its depth under its zero) under the far one is LOWER, as much over it
   UPPER — the bands are where the wall retains, never a slope beside it.
   Each sample owns the 2 m ray from the wall to its ring point. MEASURED:
   with a 2 m label (the clear step read across the 25 m the samples span)
   the gentle north run of `muro_concreto5` read as two-level `pav14`, and
   the solve then stood the ground 7.4 m under pavement left at the upper
   level (`strip_seam_tear` 7.18–7.36 m at 33.64108, -84.4216).
3. Per pavement polygon a cutting wall overlaps: the footprint leaves it;
   the part on ONE band that ends inside that band (it reaches nothing in
   the band's last metre) is an OVERHANG and leaves it (20ak); where both
   sides run on past their bands it is TWO-LEVEL and only the footprint
   leaves it (20ax), counted `wall_clip_two_level`. Pieces under `[cells]
   min_area_m2` are noise and dropped; split pieces are `<id>#wall<k>`.
4. Pack-own and borrowed pavement alike (20ax).

Not done (finding for the owner): 20ax's same-elevation case (a wall standing
on level pavement still "probably" cuts it). No witness separates a pack
retaining wall on level ground from any wall-shaped part (a facade, a
parapet), so only walls with a step cut. A TWO-LEVEL polygon that stays
connected round a wall's end is not split there: no line in the geometry
says where the upper level ends round the end.

## Consumer census (RULINGS 2026-08-30l)

| consumer | reads | ruling |
|---|---|---|
| `classify/roles` slice region, `_ref_for`, `pav_of` | `Evidence.pavement_union` / `pavement_polys` | CLIPPED (the intent); `#wall<k>` ids resolve by prefix |
| `classify/sources.classify_sources` | `pavement_polys` + description by id | CLIPPED; description read off the base id (existing `#` rule) |
| `classify/evidence` OSM roads / taxiways, pads, jetway ground | `pavement_union` | CLIPPED: a centreline over the wall is no longer on pavement |
| `constraints/wall_zone` (#1151) | planar faces at the wall | the "overhanging edge" case no longer arises at a cutting wall; crossing rows are released as before |
| `planar/channel` hole-and-neck read, `airport/flat_site*`, `airport/borrow` coverage | raw `airport.pavements` | UNCHANGED by design: they read the authored polygons, not the planar map |
| census (`tools/check_grade`) | the emitted patch | reads the clipped faces |

## Acceptance

- KATL `muro_concreto`: no pavement past the lower face; the cut stands at
  the wall outline; the ground past the foot at the real ground (20ai).
- Twin `tests/auto_patch_v2/test_wall_clip1158.py`.

## Replay (KATL capture at the #1197 commit, `--replay --from classify`, harness census)

| | base (#1197 tree) | arm (this rule) |
|---|---|---|
| 33.638945, -84.417116 — 3.0 m past `muro_concreto`'s lower face (the overhang) | pav14 node 300.48 m (taxiway level, 10 m over the ground below) | zone ground 291.35 m (the lower level; DEM there 297.65, the lidar smear) |
| 33.63735, -84.41711 — the wall's south end | `strip_seam_tear` 8.13 m (300.36 m beside 292.23 m) | no row |
| in-scope rows within 30 m of the two `muro_concreto` walls | 25 (worst `hard_conflict` 17.46 m, the 8.13 m seam tear) | 15 (worst `pavement_over_road_cap` 10.75 m) |
| KATL adjudicated (law-true) | 5,203 | 5,188 |

Residual: `adjacent_ground_step` 9.33 m inside `adjacent_ground:taxi:E:zone2#156`
at 33.637367, -84.417 — 14 m south of `muro_concreto`'s south end, where the
taxiway's zone ground (299.5 m) meets the released lower ground (290.17 m,
DEM 290.62). Round the wall's END there is no wall to hide the change of
level; the base read 4.7 m there.
