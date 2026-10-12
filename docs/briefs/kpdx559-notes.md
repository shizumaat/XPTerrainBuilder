# kpdx559 — lane notes (issue #559)

## RESUME HERE
- Branch `claude/kpdx559`. Fix + twins committed. Offline closing evidence
  taken (capture + replay). REMAINING: full non-Qt suite, `tools/ratchets.py`,
  and the ONE harness build of KPDX — which the harness REFUSES today because
  the shared corpus frame for +45-123 is not current (see "Harness build").

## Reproduction
- `build_airport.py KPDX --tile 45 -123` and `build_airport.py KPDX` both
  REFUSE before building: 1 of 66 approach-ring cells unanswered
  (`--refresh-data rings`), and with `--allow-degraded-dem` 9 inset
  negatives recorded by an unrecorded engine version (`--refresh-data dem`).
  Neither refresh was run by this lane (a download into the shared corpus).
- Reproduced offline: `tools/v2_solve_replay.py --capture KPDX` dies at the
  identical coordinate, 20 s in. The pack is Flightbeam KPDX
  (`c_USA - 100_airport - KPDX (Flightbeam)`), not Global Airports.

## Traceback (the app prints only the message)
`pack_partition.partition_pack` -> `_build_member` -> `skirt.is_skirt` ->
`skirt.reading` -> `below_zero_reading` -> `skirt.footprint` ->
`skirt._plan_union` -> bare `shapely.ops.unary_union(polys)`.
Resource: `objects/terminal_lights_ac.obj` (315,822 vertices, 93,950 solid
triangles, 1,255 components). The coordinate is in the OBJECT's authored
frame (x, z), not the airport's.

## Mechanism (measured)
- 85,253 plan triangles pass `_bulk_polys`' filter (`is_valid & area > 1e-9`);
  every operand is valid; GEOS 3.13.1's exact overlay refuses their union.
- The file prints float32 vertices to 8 decimals (100 % round-trip to float32
  at 8 dp). A wall authored vertical stands off its plan line by a float32
  step (15 um at 200 m reach): 11,074 triangles are <= 1 step wide in plan
  (97.5 % of them steep faces), total area 0.029 m2 of 4,440 m2.
- The six triangles at the reported point are 1.0 / 2.5 / 1.6 / 2.0 steps
  wide needles of one component (580).
- INTERVENTIONS on the captured input:
  * drop triangles whose plan width <= 1 float32 step -> exact union returns
    (area 4440.0430 vs 4440.0497 for `union_all(grid_size=1e-6)` of all).
  * drop width <= 1e-6 m (774 triangles) -> returns.
  * snap coordinates to 1e-6 / 1e-4 / 1e-3 -> returns.
  * read the vertices AT their float32 values (<= 5 nm move) -> returns
    (area 4440.0499). So the 8-dp decimal parse is part of the trigger.
  * drop only the 4 needles within 1 m of the point -> refusal MOVES to
    (-43.52, ...): the failure is not local to one site.
  * needles alone (11,074): no refusal; each component alone: no refusal;
    any neighbourhood of the point up to 300 m: no refusal.
- Reduced by delta-minimisation to 2,321 triangles / 80 components (561
  needles; without them the reduced set unions). That is the fixture.

## Fix
- `airport/obj8_clip.py`: `_edge_on(pts)` + `_bulk_polys` drops a plan
  triangle whose width (altitude on its longest edge) is at or below
  `np.spacing(float32(largest |coordinate|))`. Derivation site: where a
  triangle becomes a plan polygon. No airport, no tuned number.
- `airport/skirt.py`: `_plan_union` unions through `frame_entry.union`
  (spec §51 Law B); registered in G2 (`test_v2witnessvalid._UNION_FUNCTIONS`).
- Twins: `tests/auto_patch_v2/test_edge_on_faces.py` (10) + fixture
  `tests/auto_patch_v2/fixtures/edge_on_needles_559.npz` (21 kB).

## Offline closing evidence
- capture KPDX: completes, 868 s (pack partition 269 s), no frame-entry
  rung fell. `--replay --emit --verify`: rc 0, patch emitted (786 ways,
  12,073 nodes), verify DEFECT families all zero.

## Harness build
- NOT RUN: refused as above. Needs the master to authorise
  `--refresh-data rings` and `--refresh-data dem` for +45-123.

## Found, not fixed
- see final report.
