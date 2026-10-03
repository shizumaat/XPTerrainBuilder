
- 2026-09-30x (#127, facade127): the welded-carrier rule skips the carrier own-ground test, the too-far-from-own-ground test and the reach cap; spec-author confirmation or bound owed before the beta 2 tag (RULINGS 2026-09-30x).
- 2026-09-30 (#154, export154): the OREGONDOGAMI / HILLSBOROUGHNATIVE witnesses (KEUG, KSLE, KTPA) were measured on lane-local provider fetches only; the replay census vs a shared-corpus control is owed — the shared corpus holds no DEM for +44-124 / +27-083 and only a superseded-schema road feed near KEUG, so no capture/control exists until the session warms them (`build_airport.py KEUG --refresh-data osm_layers`, `--refresh-data dem --warm-insets KEUG`; same for KSLE, KTPA) after the global ladder assembly lands.
- 2026-10-01 (#164, rings164impl): the approach-graded elevation rings landed CODE + SYNTHETIC TWINS only — the lane ran in the cloud, where there is no data corpus. Owed to the session, on the shared corpus: the `rings` refresh on KASE (+39-107) plus the four control tiles (HECA / KCLT / SPJC / CYXY); the KASE closing build and spec §8 (1)–(3) measured on the baked `alt_dem` (the box-edge band slope distribution, the 9 km and 15 km approach probes, the three transition grades); §8 (5) the five control captures replayed `--emit --verify` for byte-identity (ANY mover is a STOP, the owner rules); §8 (6) triangles and the build-time checker's `--runs 3` for step 2; §8 (7) the `frame.json` corpus-clean read. The lane's own measurements are the synthetic twins' (`tests/test_approach_rings.py`), which bound the transition grades but say nothing about the real terrain.
- 2026-10-01 (#164, rings164impl): NOT DONE in the lane and owed as its own follow-up — the coastline band's own BAKE is still ONE mixed-resolution VRT baked once, so its unfeathered 10 m-vs-20 m cell-edge step (ring spec §0 fact 6) stands. Only its GRADING was rewired through the shared `approach_class` (values unchanged, Q2). Per-class band layers through `bake_overlay_layer_into_alt_dem` need the band plan to carry `layers` + per-class regions; the ring side already has both.
- 2026-10-01 (#164, rings164impl): the `--witness` ring rows (ring spec census row 19) and the Qt / `O4_Qt_Settings` / Swift `SettingsLayout.swift` one-line surfaces (census row 18) are NOT implemented. The `approach_rings` cfg key is registered with its hint, so both UIs render it from the schema; the "approach rings: 10 m to 10 km (CODE), 30 m to 20 km" tile-info line from `summarize_tile_elevation_sources` is owed.
- 2026-10-02 (#42 / #110, gen1): the lane ran in the cloud with CODE + TWINS ONLY — no data corpus — so BOTH changes landed on synthetic twins plus the CYXY `tests/` fixture, and neither ran a tile build. Owed to the session, on the shared corpus: (#110) the five control captures replayed `--emit --verify` with a role census per capture, confirming the cloud reading that nothing crosses the airside/groundside line and naming every face that moves `groundside_pavement` -> `parking_lot` / `service_road`, plus the grade effect of the new 5 % lot cap and 8 % road cap on faces that previously carried the `groundside_pavement` cap; the closing build at the owner's representative airport; and the owner's sim read of the road ribbons (`road_ribbon_min_aspect` 6.0 is measured against synthetic shapes and CYXY's 120-cell fixture only — no multi-airport collateral sweep). (#42) the owner's app read with "Modify custom airports" unchecked: no `[v2 rebake]` line on the console and no pack touched; the cloud twin proves the stage and its print at the function level only.
- 2026-10-02 (#103, harnessbugs/mount103): the build-cwd law now excuses a missing corpus dir when `CS.mountable()` passes, but the END-TO-END proof the issue describes is owed — a cloud session with the data repo attached, fresh clone, `O4_CORPUS_SNAPSHOT` set and NO hand-made `OSM_data` symlink, running `build_airport.py CYXY` to rc 0 / 0 leaks (the shape `docs/CLOUD-CORPUS.md` now documents). The lane ran CODE + TWINS only in a corpus-free clone: it proved `require_build_cwd` passes and `CS.mount` then creates the symlink, but never ran the two in one real build. The `mountable()` timing (121.8 ms, 0.20 % of the 60 s auto-patch budget) is from a synthetic manifest of HECA's file COUNT, not HECA's bytes — correct for a stat-bound check, but not a measurement of the real snapshot.
- 2026-10-02 lane cyxy108 (#108): the new `verify/cutback.py` reader was
  proved against the oracle on a SYNTHETIC HECA-route19 strip only (this
  clone has no corpus, so `test_cyxy_verify_matches_v1_census` SKIPS).
  Owed on a real corpus: one `tests/auto_patch_v2/test_constraints.py
  ::test_cyxy_verify_matches_v1_census` run, confirming the reader reads
  the census's 9 `groundside_cutback` rows on the built CYXY surface
  (tolerance `max(2, 0.2*9)`), and that no other family moved.
- 2026-10-02 lane cyxy108 (#108): the new reader's build-time cost was
  measured SYNTHETICALLY (40k road + 40k far vertices, lawful strip:
  113 ms median of 3; the same shape unlawful end to end: 759 ms for
  40,000 rows). Owed: the per-family `verify.WALL_S["groundside_cutback"]`
  from one real HECA/OTHH build, against the 0.6 s (1 % of 60 s) gate.
- 2026-10-02 lane cyxy108 (#108): ten census families remain with NO v2
  verify reader and NO reasoned `NOT_IMPLEMENTED` entry (`seam_residual`,
  `bank_across_seam`, `ramp_in_road`, `object_cut_offset`,
  `object_cut_depth`, `ramp_in_strip`, `road_coverage_join`, `sea_wall`,
  `zone_on_pavement`, `sentinel_elevation`), frozen as
  `test_v2cutback.OPEN_PARITY_GAPS`. Each is owed a reader or a reason;
  which, per family, is an owner/spawner call, and any of them reading
  non-zero on a built airport is the next `#108`.
- 2026-10-02 (#106/#107, harnessbugs/census106116): the one-writer site fix changes the printed lat/lon of EVERY family that previously fell through to `run_checks`'s ring-centroid fallback — 20 of the 50 row-producing families, `adjacent_ground_step` plus `plane_gradient`, `transverse_grade`, `lateral_contiguity`, `stacked_nodes`, `drainage_minimum`, `runway_crown`, `cross_shape_proximity`, `terrace_*` and all three step families. Counts are unaffected by construction; the SITES move. Owed on a real corpus: `build_airport.py HECA` then `census.py <patch>.osm --rows-json`, checking each row's `lat`/`lon` against its own `site_m` projected through the sidecar `anchor`, and confirming no family's printed site regressed. The lane proved it synthetically only (all 20 verified statically to carry real metre endpoints). The original observation was `nlwfroad100c_NLWF` (-14.3113508, -178.0609526), which is not one of the five sweep airports.
- 2026-10-02 (#116, harnessbugs/census106116): the strip-station fixes may MOVE COUNTS on a real strip, and the direction is predicted but unmeasured — station counts should RISE (the eps-inclusive boundary admits boundary-coincident rim vertices; the canonical chain start recovers the two stations the array boundary used to eat), so `strip_arc` / `strip_abeam` / `resa_transverse` / `raoa` row counts may rise with them. NOTE the eps predicate was widened past #116's own family to all four strip-footprint station sets (reported deviation: patching `strip_arc` alone would leave two readers disagreeing about where a strip is). Owed: `census.py` family counts for those four on a HECA patch against the current shared control for the same base-sha; and KCLT.
- 2026-10-02 (#116, harnessbugs/census106116): the DEFINITIVE read is the original terrace11c pair — the two replay arms at 30.0996269, 31.3974530 (HECA) whose `strip_arc` CRITICAL motion row appeared in one arm only. Re-run both arms and confirm the row no longer flips. Needs the captures; the lane had none.
- 2026-10-02 lane roadsfree143 (#143, RULINGS 2026-10-02v (1)): the stage-1 foreign rule for a pinned groundside road vertex was proved on a SYNTHETIC apron + service road only (this clone has no corpus and the brief forbids builds). Measured there: 4 road-footed rows left stage 1 (10,270 -> 10,266), stage-1 unknowns 177 unchanged, airside bit-identical with and without the §37 (9) join pin (0.0 m). OWED on the corpus, the owner's session: the HECA / KCLT / SPJC replays the ruling quotes — 3,537 solve-owned HECA movers over 0.02 m, worst 1.00 m at 30.13577666876, 31.41073906739, runway 85 movers worst ≤ 0.06 m, stage-1 rows 123,305 -> 122,592, hard_conflict against the 115 bar, CRITICAL motion, and KCLT's 3 door-ramp structure pins of the same shape (NOT in `groundside_pin_rulings` — reported, not decided). The references are re-cut once per the ruling.
- 2026-10-02 lane padgates101 (#101, owner RULINGS 2026-10-02v (3)): v1's
  two pad-admission gates were ported and verified SYNTHETICALLY only (17
  twins, `tests/auto_patch_v2/test_padgates101.py`) — the lane had no
  corpus and no captures by brief. Owed on a real corpus, and the owner's
  session is the one that can run it: (a) `tools/v2_solve_replay.py
  --replay --from classify HECA`, reading the new `cluster pads` counters
  `no_tall_base` / `no_building_evidence` / `osm_vouched` / `unmeasured`
  and the `pad_refusals` sidecar rows, with the HECA elevated train
  (`road_train/concrete_3.obj`, v1's 31,220 m2 slab/mast weld) expected in
  the `min_tall_base_fill` list; (b) the same for KCLT / SPJC / OTHH /
  LEMD so the per-airport refused counts are on the record before the
  sweep; (c) one HECA closing build against the airside reference,
  confirming the airside constraint set is UNCHANGED (the gates mint
  fewer pads and must move no airside vertex); (d) the per-family
  build-time delta — the measurement is O(components) over a population
  already walked and was NOT timed on a real pack.
- 2026-10-02 lane padgates101 (#101): the FALLBACK half's gate (the v1
  footprint-cache rings, admitted on their cached role OR an OSM
  building) was proved by inspection of `airport/load.py`'s source
  spelling, not against a real cache. Owed: one HECA read confirming the
  `dsf:object:object_unvouched` population is non-empty and that
  `pad_refusals.fallback_no_building_evidence` counts it.
- 2026-10-02 lane altraster238 (#238): the `.alt` frame sidecar and the
  reader that takes it were proved on a SYNTHETIC raster only (this clone
  has no corpus and the brief forbids builds). The twin posts a 9-square
  raster on the KASE-class frame (±5.5″ beyond the tile) over a surface
  LINEAR in tile-relative degrees, so a correct bilinear read is exact
  everywhere: read under the recorded frame the worst error is < 1e-3 m,
  read under the old viewfinder constant it is metres. OWED on the
  corpus, the owner's session: one KASE +39-107 tile build at
  `elevation_level=10`, then `mesh_elevation_sampler.py Data+39-107.mesh
  --alt-raster Data+39-107.alt` over the free vertices kaseread368
  measured 58 m of disagreement at — the banner must name the written
  sidecar (10834x10834, x/y about -0.0015 .. 1.0015) and worst/rms must
  come back under 1 cm, which is the best-fit extent kaseread368 found.
  The 58 m number itself is from that lane's read and is NOT re-measured
  here. Also owed: one build of a tile with NO airport insets, confirming
  the sidecar it writes is the viewfinder frame (3673, -0.01 .. 1.01) and
  that `patch_transect.py --alt` and `mesh_region_tris.py
  --interp-alt-audit` read it unchanged against their pre-#238 numbers.
- 2026-10-02 lane interiors10 (#10 HECA-5, branch `claude/interiors10`):
  the contents seat (`footprint_unit.contents_seat`, the no-carrier
  part-id join, the unit carry reading the surface at its anchor) was
  measured at HECA only (CONTENTS APART 180 -> 25 bodies > 0.5 m off
  their unit's datum; files 3,558 -> 3,658). OWED: the object stage of
  the other packs (LEMD, OTHH, KCLT, SPJC, KASE) through
  `obj8_split_report` — the rule moves every pack's contents and the
  #31 unit-carried files' anchors — and the owner's sim read of HECA's
  terminals (T1/T2/T3, the T23 hangar 30.11475, 31.39793: doors and
  glass were +10.58 m) in the next app build.
- 2026-10-02 lane t3onelevel10 (RULINGS 2026-10-02aj (2), branch
  `claude/t3onelevel10`): the block cut is gated on the unit's composed
  base verdict (`pad_blocks.unit_base`; only `stepped` is cut). Measured
  on replays only (HECA `hecamove/HECA.pkl --from classify`, KCLT/SPJC
  `sweep1005attr/*.pkl --from planar`): HECA and SPJC plans unchanged,
  KCLT `building49` (35.21284, -80.93814; no base plane) 2 blocks -> 1.
  HECA T3 (`building4`) is NOT changed: its cluster `unit:43#6330`
  composes STEPPED (34 planes — ceilings, upper floors and roof nets read
  as base planes); the FLAT `unit:40` is `heca_ground_polygon.obj`, not
  the terminal. OWED: the HECA closing build + census (not run — it
  would reproduce the unchanged T3), and the owner's ruling on T3's
  stepped read.
