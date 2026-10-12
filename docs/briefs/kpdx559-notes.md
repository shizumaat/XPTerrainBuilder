# kpdx559 — lane notes (issue #559)

## RESUME HERE
- Branch `claude/kpdx559`. Fix + twins committed and pushed. Full non-Qt
  suite green (9289 passed, 19 skipped, 1 xfailed, 1 xpassed — the xpass is
  on unmodified main too). `tools/ratchets.py`: duplicate + layer PASS.
- Capture registered: `frames.py list KPDX` (copied into the data repo).
- Closing harness build DONE by the master (see "Harness closing build").
  Nothing left on this lane; PR #578 twin made platform-true.

## Platform finding (PR #578 CI, 2026-10-12)
- The raw needle soup REFUSES only on macOS arm64. CI installs the same
  `shapely==2.1.2` wheel family on all three OSes (macosx_11_0_arm64,
  manylinux2014_x86_64, win x86_64); the fixture's bare `unary_union`
  raised on macos-15 and RETURNED on ubuntu-22.04 and windows-latest. The CI
  log does not print `shapely.geos_version` (local mac: 3.13.1), so whether
  the wheels carry different GEOS builds or the same GEOS behaves differently
  per architecture is NOT established. #559 as the owner saw it may be
  mac-arm64-only; the edge-on rule holds on every platform regardless.
- The twin now asserts the invariant everywhere and the refusal conditionally.

## Harness closing build (run by the master after refreshing the corpus)
- KPDX: body c976010a3b6c, 287 s, solve optimal, verify defects none;
  census law-true 3052, adjudicated 684 (the same totals as the lane's
  replay-emitted patch).

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

- `tools/harness/census.py` on the REPLAY-emitted patch (not a harness
  build; degraded DEM frame — no elevation quoted): ruleset faa, LAW-TRUE
  TOTAL 3052 (within 3052, cross 0, steps 0), ADJUDICATED 684 (airside 586,
  groundside 98) verdict FAIL; COCKPIT critical motion 0, critical visual 754
  (worst 4.582 m, channel_floor_at_declaration, tunnel_trench); drainage_minimum
  1808, hairline_pair 426, channel_floor_at_declaration 414, within_shape 254.
  KPDX has never built, so there is no control to compare with.

## Harness build
- NOT RUN: refused as above. Needs the master to authorise
  `--refresh-data rings` and `--refresh-data dem` for +45-123.

## Found, not fixed
- KPDX pack partition 269 s (capture 868 s): far over the 60 s airport budget.
- KPDX first census is a FAIL (numbers above): tunnel_ramp within_shape rows to
  9.47 m / 11.7 % against a 10 % cap, tunnel_trench channel floor 4.58 m off.
- Sibling triangle->plan-polygon sites keep the area-only floor and were NOT
  changed: `below_zero.py:134`, `sunken_roads.py:189`, `wall_geometry._plan_polys`,
  `object_cut._plan_polys`, `basin_witness.py:196`.
- Bare unions of LOCAL pack triangles remain in `obj8_clip._clip_component`,
  `_clip_both` and `skirt.below_zero_reading` (`unary_union(below)`).
- The OBJ8 reader parses 8-dp decimal text to float64; at the float32 values
  the file means, this union does not refuse. Not changed (55 importers,
  every golden moves).
- The app-side message names the coordinate as if airport-local; it is in
  the object's frame and names no resource (lane failmsg562's surface).
