# #712 / #1003 round 5 — lane lheca5 handoff (paused 2026-10-26 ~23:00 local, owner's order)

Spec: `docs/specs/fill-step-at-road-kerb-spec.md` (on main). Law: RULINGS 2026-10-27i (§5.1 (a):
the lot between fill and road is not re-classed; the fill runs to the lot; the step sits at the
lot's far edge), 2026-10-27j (`fill_road_reach_m` = 100 m is law; cited on the key).
Branch `claude/l1088c-road-drop` (PR #1134), merged with main 1445b7ae7. PR body NOT changed.

## Done

1. **§3 verify (no build).** R1 candidates and verdicts, off `frames/m1/CYXY.pkl` and
   `frames/l1088c/HECA.pkl` (`--from classify` equivalent, classify_sources under the tree):
   - CYXY: 1 candidate `pav4` (11.5 m, 488 m tertiary through) -> NOT welded to a pad -> stays lot.
   - HECA: 1 candidate `dsf:pol10` (18.5 m, 3,444 m secondary through). Its outline overlaps
     `building5`'s footprint by 495 m2, but the touch witness HOLDS it (hillside): the cells stand
     0.954 m apart, shared edge 0.0 m at 0.01 m tolerance (17.4 m only within `on_tol_m` 1.0 on the
     raw footprints). -> **`dsf:pol10` fails the contact test** -> stays a lot (27i, as ruled).
   - The witness used: `classify/pad_touch.source_weld_partners` (Rule T touching, less §28 (6)
     held) — the classifier's own weld verdict on the source, not a new tolerance.
   - CYXY twin `test_cyxy_verify_matches_v1_census`: red on the branch (mid_edge_step v1 7 / v2 2 at
     pav4|small_roads:-1071#1, caused by R1: green with R1 off), **green on this branch** (R1
     re-kinds nothing at CYXY). An earlier arm that kept pav4 a strip with its network way as the
     axis also cleared mid_edge_step but raised transverse 22 -> 68 (the OSM way is off-centre and
     diagonal in the page): recorded, not shipped (pav4 is no longer a strip).
2. **§2 the riser.** `planar/fill_riser.py` (new): along the far kerb of each road strip OR lot
   (27i) the fill's lens touched, across the road from the contact (`_across`), within the lens
   span (per-segment flat bands), width `max(min_distinct_spacing, 2 x grid)`, where
   `L - ramp_grade * s - DEM > visual_m`; ref `<landing>#strip`; geometry + height on
   `Registries.landings[ref]["risers"]`. Wired in `planar/landing.py` PASS 1a (`_to_road` returns
   the level; `_risers`), PASS 2 (reached roads/lots join `held_c`, risers emitted as regions).
   `planar/platform.py` passes `lots=` (LOT_ROLES via `fill_road.road_strips(..., roles=)`).
   `airport/riser_wall.py` (replaces deleted `road_edge_wall.py`): one `road_terrace['wall']`
   record per riser read off the noded faces (`line` = faces + one identity spacing, `upper`/
   `lower`/`kerb`, `retains`, `road_edge`). `model/planar.drop_edges` re-sourced to `kerb`.
   `constraints/platform.block_strip_rows` skips landing risers. `solve/design_ground.
   riser_outer_vertices`: the riser's outer line takes the weak ground datum (DEVIATION from the
   spec's consumer table — `--why-vertex` showed "no row binds, the objective holds it" at +1.85 m).
   Sidecar `landings` rows carry `riser_ref` / `riser_heights_m`.
3. **§6.** Dropped: `_network_strip` global re-kind, `road_edge_wall.py`, `road_terrace['drop']`
   and its report line, R4 tests (replaced by riser twins in `tests/auto_patch_v2/
   test_road_edge_drop.py`). Kept everything §6 lists. `road-edge-drop-spec.md` marked superseded
   in part.
4. **Control (§4).** `build_airport.py HECA --base-arm` at main 1445b7ae7 -> `lheca5ctl`, body
   `fcb672ebbd29`, 1283 s, registered `frames/lheca5/lheca5ctl.osm` (ledger did NOT store it:
   external-candidate delta). This is build 1 of 2.

## Measured (replays; no round build yet)

- `pad_fill_to_road` 3 (3,412.9 m2) with lots as targets; WITHOUT lots 0 (with pol10 a lot no road
  strip is within reach of any fill) — lots-as-targets is what 27i needs.
- Fill areas identical to round 4 (`lheca_HECA`): building5/landing10 29,351.6 m2, building6/
  landing0 16,612.5, landing1 4,421.2 …
- Base solve `frames/lheca5/base_r5b.pkl` (gap-free): **#712 site** nearest vertices on
  `building6/landing1` at **96.71** (bar 96.62 +/- 0.5: met); **#1003 site** on `building5/landing10`
  at **101.67** (bar 101.66 +/- 0.5: met). Risers minted: **1** (`building6/landing0#strip`, along
  `dsf:pol10`'s far edge near 30.1100, 31.3856, h 7.0 m; kerb z 91.3-95.2 over DEM 86.4-88.0). Its
  outer line stood +0.94..+1.71 over DEM because one riser edge escaped `wall_cut` (the record's
  pre-snap ring, 0.10-0.16 m off the noded vertices) — FIXED after that solve (riser_wall reads the
  noded faces); not yet re-measured.
- Tests: `tests/auto_patch_v2` 3,892 passed; serial re-run of the xdist errors passes;
  `test_v2dsfagl::test_real_pack_roundtrip_and_idempotent_write` fails identically on main
  (machine pack backup state). Closure + registry twins pass; `tools/ratchets.py` passes (size
  warnings: road_ramp.py 1,887 (+202 vs baseline), roles.py 1,634, constraints/platform.py 1,364,
  model/planar.py 1,210, publication.py 1,421).

## Exact next step

1. (optional, ~45 min) re-run the base + late replays to check the riser's outer line and the
   gap pieces beside it: `v2_solve_replay.py --replay frames/l1088c/HECA.pkl --from classify
   --gap-free --solved-out B.pkl`, then `--late-from B.pkl --verify --solved-out L.pkl`.
   Probe scripts used are trivial (risers: landings[*]["risers"], walls with road_edge).
2. The ONE round build: `build_airport.py HECA --tag lheca5` from the lane tree at this sha
   (the first attempt was stopped by the pause, before output).
3. One census call: `tools/harness/census.py frames/lheca5/lheca5ctl.osm /tmp/harness/lheca5.osm`;
   register the round patch with `frames.py register --copy`.
4. Bars of §4 against the control; PR #1134 body: "Fixes #712, Fixes #1003" only if all met, else
   "Refs" + unmet bars.

## Open questions / watch

- Only one riser at HECA: building5/landing10 (T3, #1003) mints none (its far kerbs within
  `visual_m`, or no contact "across" the lot). Check the gap pieces around T3 (the round-3
  residuals: `big_roads:-6586`, `small_roads:-3964`, `gap:2/s0`, `gap:27/lot`) in the late map.
- `wall_release` with a polygon wall also releases rows from the riser's outer vertices to gap
  vertices beyond (they touch the polygon) — same semantics as pack walls; the base fixes those
  vertices in the last stage.
- The riser height is the max predicted level over the DEM; the step floor uses it per lower
  vertex against its nearest upper vertex.
