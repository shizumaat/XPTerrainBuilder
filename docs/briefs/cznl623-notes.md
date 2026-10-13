# cznl623 notes (issue #623) — RESUME HERE

Lane worktree `.claude/worktrees/cznl623`, branch `claude/cznl623` from 7d29f9d75.
Scratch: `<session scratchpad>/cznl623/` (owner evidence copied to `owner/`).

## Step 1 — reproduced (2026-10-12)
`build_airport.py CZNL --tag cznl623-base` -> /tmp/harness/cznl623-base.osm, body_sha 438b80c3206d,
artifact ledger 83997a9fcc60. 15 nodes at 1798.00, status optimal.
Build log already says `off-DEM > 0.5 m by role: graded_strip 29/98 (max 1266.48)` and
`objective 2731680.11`; census DOES list 8 `adjacent_ground_step` rows |de| 1263-1265 m
(v2-verify rows=11) — verify reports rows but nothing fails the airport.

## Step 2 — MECHANISM (by intervention)
`--why-at 49.494329,-117.301232` on the solved capture: v434 z 1798.00, DEM 531.58, ONE binding row:
`water PIN z=1798.000` (constraints/water.py, RULINGS 09-09m (1)). Not an LP bound, not a void, not the pinless runway.
The level comes from `airport/dem_production.TileWater.level_of`: median of the tile DEM on a 32x32 grid
over the polygon's WHOLE bounds. Polygon 1281 (inland, Kootenay Lake) has tile-relative bounds
x 0.53..1.345, y 0.249..1.174 — the cached water layer is not cut at the tile edge — and
`_BakedTile.sample` CLIPS out-of-tile posts onto the edge cell. 69 posts inside the lake:
min 531.4, p5 533, p25 1210, median 1798.0, max 2242 (edge mountainsides).
INTERVENTION: sample only posts inside polygon ∩ the tile's own degree cell -> level 532.07;
replay: v434 z 532.07 (DEM 531.58), graded_strip max off-DEM 1266.48 -> 2.21 m. status optimal both arms.
Other zone-2 ring (#0) is on the land side: its vertices sample dry, no pin.
Also changed: no finite sample -> NaN (was 0.0, a sea level an inland body does not hold); water.py already skips non-finite.
Touched so far: `src/auto_patch_v2/airport/dem_production.py` (TileWater.level_of, new _level_posts).

## Step 3/4 — fix + guards written (tests green: test_ground_envelope 11, water_datum/zerocrater/parity186/defectfloor/tile_failures 82)
- CAUSE: `airport/dem_production.py` TileWater.level_of -> `_level_posts` (posts inside body ∩ tile cell); no sample -> NaN.
- SOLVE GUARD: new `solve/ground_band.py` (`ground_envelope`, `outside_envelope`): DEM hull under all map vertices ± `emit.cockpit.sentinel_drop_m` (50 m).
  `pipeline/build.py` says "OFF THE GROUND", report `solve.off_ground`; `auto_patch/engine_v2.py` fails the airport,
  code `airport_surface_off_ground` (new `O4_Tile_Failures.CATALOGUE` entry); `tools/harness/build_airport.py` shouts.
- SHIP GUARD: sidecar key `ground_envelope` (publication.py, osm_adapter key list, check_grade SIDECAR_LAW_KEYS/ctx/run_checks);
  `verify/pins.sentinel_elevation` + `check_grade._check_sentinel_elevation` two-sided: published envelope first, else own p5..p95 ± 50.
  `verify/census.DEFECT_KEYS` += sentinel_elevation (verify gate) — NOTE for master: 08v says "the gate reads the runway family only"; this adds a non-law family.
- Demonstration (cause fix reverted, replay --emit --verify): sentinel_elevation 15 rows, listed as DEFECT. census.py on the OWNER's patch: sentinel_elevation 15 (was 0).
- Sibling scan (scratch scan4.py, 156 v2 patches on disk): only CZNL has governed nodes > 50 m outside its band; KBIL 9 / LPPT 31 are `mouth_road` ways
  (tunnel mouths, own ground); raw scan also hits tunnel_ramp/tunnel_wall at KTEX/LSGL/LSGB/LSGN/HEAZ/KASE/MGGT/KABQ/KGJT/LPCS (own ground, lawful).
  58 v1 patches (generator O4_Airport_Pavement_Builder) not judged.
TODO: pinless runway finding; closing CZNL build; suites; ratchets.

## Step 6 — closing build (2026-10-12 19:15)
`build_airport.py CZNL --tag cznl623-fix2` -> /tmp/harness/cznl623-fix2.osm body_sha 8b29ed2545a8, artifact ledger 3b8542b3bd49.
469 nodes 532.07..535.40; the 15 formerly spiked nodes all 532.07 (the lake's in-tile level; DEM under them 531.6).
graded_strip off-DEM max 1266.48 -> 2.21 m. v2-verify rows 11 -> 3 (runway_crown 3). Census LAW-TRUE 35 (new family counted; 20 under the old census) -> 12
(hairline_pair 10, road_cross_section 1, pad_airside_renode 1 — all present before, not this lane's).
PINLESS RUNWAY: not a defect of the solve. Both thresholds carry CIFP 534.924 and the solve has 2 runway_profile pins;
`runway_caps[].pins` names only the GOVERNING span (the pair that set g_pin) and a level runway has g_pin 0 -> no span -> `pins: []`.
A reporting ambiguity in constraints/runway_yield.py RunwayCap (not changed).
TODO: suites, ratchets, commit.

## DONE (2026-10-12 19:25)
Commit 4f23d8723 on claude/cznl623. Tests: test_ground_envelope 11; tests/auto_patch_v2 2982 passed / 3 skipped / 1 xfailed / 1 xpassed;
rest of non-Qt suite 6646 passed / 16 skipped; ratchets PASS (duplicate + layers).
Frames registered: CZNL capture (base 7d29f9d75), CZNL patch (closing build).
NOT done: no app/tile build; KBIL/LPPT mouth_road rows not adjudicated; RunwayCap `pins: []` wording untouched;
the river case (one level per polygon over a sloping river) is a finding, not fixed.
