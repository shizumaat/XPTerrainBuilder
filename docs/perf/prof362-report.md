# prof362 — OTHH auto-patch build profile (issue #362, RULINGS 2026-10-04v)

Lane `prof362`, branch `claude/prof362`, tree = main `56e67443`, worktree
`/Users/noah/XPTerrainBuilder/.claude/worktrees/prof362`. No engine edit.
Three OTHH harness builds (`tools/harness/build_airport.py OTHH --no-ledger`),
one at a time, nice 0, machine quiet before each (no other python / pytest /
build; top foreign process < 3 % CPU before runs 2 and 3; before run 1
WindowServer 46 % and a decaying `mds_stores`, gone at the second sample).
Emitted patch sha1 identical in all three runs and to sweep `sw1034_OTHH`:
`4d59e868f385…`. All numbers are SINGLE runs (±25 % law applies to walls).

## 0. Verdict

- **≤ 600 s COLD at OTHH is NOT reachable with the candidates below.**
  Cold today ≈ 2,340 s plain (derived: run 2 + cold partition). The five
  exact, single-site candidates (A–E) take it to **≈ 1,500 s cold /
  ≈ 1,050 s warm**. Adding process pools and the extension cache (F–J,
  each needing design or a proof) reaches **≈ 1,050–1,100 s cold /
  ≈ 600–850 s warm**. Floor without restructuring the pack stage: ~1,000 s
  cold.
- **One line is 437 s of the build and its result is thrown away**
  (finding 5a): door wells ask `obj8.at_grade_geometry` for linework +
  polygons, use only the polygons, and the linework window intersection
  costs 437.3 s in 2,304 calls. The polygon window costs 0.4 s in 14,344.
- The real LP is 1.5 s of HiGHS (4 calls). 58 % of the build is GEOS,
  23 % engine Python, 9 % numpy. Every stage is one thread on one core.
- HECA is also over the bar cold (711 s in sw1034); KCLT 441 s.

## 1. Stage walls (s)

| stage | run 1 cold, cProfile (heartbeat live) | run 3 cold, cProfile (heartbeat off) | run 2 WARM, plain | sw1034 cold plain (loaded machine) |
|---|---|---|---|---|
| load | 54.2 | 52.8 | 24.6 | 29.4 |
| pack partition | 551.9 MISS+WROTE | 540.3 MISS+WROTE | 50.3 HIT | 519.2 MISS |
| planar (pass 1) | 1,109.9 | 1,071.6 | 982.3 | 1,008.2 |
| – door wells | 612.5 | 595.7 | 583.0 | — |
| – sunken roads | 37.5 | 35.1 | 31.9 | — |
| – wall corridors | 179.5 | 170.1 | 120.3 | 122.3 |
| constraints (pass 1) | 135.7 | 134.1 | 71.4 | 73.9 |
| solve (2nd planar pass + stage-1 constraints + LP) | 552.0 | 544.8 | 380.7 | 392.1 |
| emit | 29.0 | 28.7 | 21.9 | 22.9 |
| rebake plan | 292.6 | 290.9 | 282.4 | 292.4 |
| verify | 53.6 | 54.0 | 26.2 | 27.2 |
| TOTAL | 2,839.2 | 2,777.2 | 1,894.5 | 2,419.5 |

cProfile inflation: ×1.0 on GEOS-bound stages (door wells 596 vs 583,
rebake 291 vs 282), ×1.4 wall corridors, ×1.4 solve stage, ×1.9
constraints, ×2.1 verify and load. The partition cache saves 490 s; the
warm stage still costs 50 s. The rebake plan is NOT cached (282 s warm).

### Instrument defect (run 1's profile must not be read for cumulative times)

Python 3.14 `cProfile` rides `sys.monitoring`, which fires in every thread.
The engine's 1 s `o4-heartbeat` thread (`src/auto_patch/progress.py:440`)
pushes and pops on the profiler's single context stack: in run 1
`pipeline/build.py:555(build)` reads 376 s cumulative for a 2,839 s build
and 564 s is booked to `_thread.lock.acquire`. Run 3 repeats the cold
profile with that thread not started (scratch runner `prof_run.py`:
patches `threading.Thread.start/join` for the thread named `o4-heartbeat`,
plus observation-only shims; no engine file touched). Run 3's tree sums to
2,777.2 s at `build`, so its cumulative times are sound. Any future profile
of this engine needs the same treatment; `tools/profile_airport_build.py`
refuses by name since the v1 cut.

## 2. Where the time is (run 3, profiled cold; whole build 2,777 s)

Self time by kind: shapely/GEOS 1,618.7 s (58.2 %), engine Python
651.3 s (23.4 %), numpy 259.4 s (9.3 %), builtins 175.4 s (6.3 %),
PROJ/GDAL 15.4 s, I/O + parse ≈ 24 s (`parse_obj8` 1,763 calls 23.7 s),
HiGHS 1.5 s (`highspy._core.run`, 4 calls).

Top self-time: `shapely.intersection` 694,728 calls 460.1 s;
`shapely.union_all` 765,984 calls 451.6 s; `numpy.ufunc.reduce` 20.1 M
calls 102.8 s; shapely decorator wrappers 133 M calls 81.5 s own;
`STRtree.__init__` 85,267 calls 73.3 s; `make_valid` 30,425 calls 62.0 s;
`shapely.lib.set_coordinates` 51,481 calls 60.1 s;
`contact.py:807 _point_tri_dist2_rows` 20,390 calls 59.6 s;
`get_parts` 221,160 calls 51.5 s; `buffer` 4.8 M calls 48.7 s.

Per stage (cumulative s, ncalls; full trees with tottime and file:line in
`docs/perf/prof362-stage-trees.txt`):

**load 52.8** — `dem_production.py:1056 load_production_dem` 46.4 →
`O4_Vector_Map.py:2076 compose_tile_dem_from_disk` 46.1 →
`O4_Airport_Utils.py:925 smooth_raster_over_airports` 41.7;
`pack.py:101 select_pack` 5.3. numpy-bound. (24.6 s plain.)

**pack partition 540.3** (`pipeline/build.py:324 pack_stage`)
- `pack_partition.py:537 partition_pack` 265.9
  - `contact.py:1004 partition` 180.5: `contact.py:597 placed_parts` 86.5
    (`contact.py:326 plan_hull` 193,710 calls 99.8 over both callers;
    `contact.py:509 solid_height` 213,932 calls 26.4);
    `contact.py:885 _narrow_pass` 82.8; `_abutment_pairs` 6.0
  - `pack_partition.py:338 _build_member` 1,087 calls 82.3:
    `skirt.py:164 reading` 38.5 (`skirt.py:79 _plan_union` 385 unions 52.8),
    `obj8_grade.py:379 base_profile` 37.8
- `footprint_connector.py:636 solid_connectors` 89.5
  (`footprint_connector.py:260 cluster_topology` 20 calls 51.9;
  `sheet_chain.py:53 sheet_links` 15.2)
- `placement_family.py:617 plan_clusters` 88.7
  (`obj8_grade.py:721 compose_profiles` 2,288 calls 48.5; `sheet_links` 14.6)
- `basin_witness.py:60 read_objects` 83.5 (`obj8.py:674 read_placed_objects`
  70.8: `_witness` 4,839 calls 43.9, OBJ parse 18.8; `deck_signature` 12.8)
- `planar/group.py:357 derive` 8.1

**classify 49.5** — `skirt.py:265 skirted_placements` 26.1
(35,886 `reading` calls), `ribbon_mint.py:142` 9.1.

**planar pass 1, 1,071.6** (`planar/build.py:177 build`, 2 calls 1,432.1)
- `pack_reads.py:76 _read` 637.5 (once per build since once362):
  `door_wells.py:244 read_door_wells` 595.7, `read_sunken_roads` 35.1
- `basins.py:405 build_basins` 2 calls 355.4 (≈ 178 per pass)
- `wall_corridors.py:565 read_wall_corridors` 2 calls 341.2 (170.1 + 171.1)
- `overlay.py:179 build_arrangement` 2 calls 82.6
  (`terrain_edge.py:128 _outward` 798 calls 42.6, 5.9 M `.coords` reads)

**constraints** (`constraints/__init__.py:143 generate`, 2 calls 264.1;
134.1 pass 1, 132.0 inside the solve stage)
- `pads.py:293 _fronting` 454 calls 104.6 — 13,114,600 `Point()` builds
  and 13,114,600 scalar `distance` calls
- `taxi.py:399 taxi_box` 43.5 → `stretches.py:334 _tied` 66,097 calls
  62.7 (146.6 M each of `hypot`/`min`/`max`/`abs`; shared with verify)
- `junction_mesh.py:239` 40.8; `apron.py:161` 17.8; `zones.py:451` 15.0;
  `foot_rows.py:164` 13.5; `pads.py:675` 11.6
- pure-Python loops dominate (×1.9 inflated; 71 s plain per pass)

**solve stage 544.8** — `stage_one_map.py:185 stage_one_problem` 500.8
(second `planar.build` 360.5 + second `shape_constraints` 132.0);
`solve/design.py:119 solve_design` 43.9 (`design_assemble.py:94 assemble`
3 calls 25.1; HiGHS 1.5).

**emit 28.7** — `publication.py:375 publication` 24.9
(`routes.py:859 route_pairs` 3 calls 38.6 total, 38.3 self; `write_patch` 0.6).

**rebake plan 290.9** — `rebake_plan.py:178 plan` 289.9 →
`pack_partition.py:803 extend_partition` 288.6 → `contact.py:1134 extend`
281.6 (self 31.0): `_narrow_pass` 172.9, `placed_parts` 25 calls 55.8,
ndarray `.all` 27,690 calls 16.5, `_build_member` 95 calls 6.4.

**verify 54.0** — `within.py:621 taxi_box` 26.9 (`box_bound` → `_tied`),
`within.py:309 within_shape` 16.0. Pure Python (26 s plain).

### Call-count pathologies

| what | calls | cost (profiled s) |
|---|---|---|
| `obj8._in_window` on LINEWORK (result unused by door wells) | 2,304 | 437.3 |
| `frame_entry.transform` of at-grade linework per placement | 2,304 | 82.9 (`set_coordinates` 60.1) |
| `pads._fronting` scalar `Point()` + `distance` | 13.1 M + 13.1 M | 104.6 |
| `stretches._tied` scalar loops | 66,097 (146.6 M `hypot`) | 62.7 |
| `wall_geometry._plan_segments_indexed` per-triangle Python | 82,182 (9.0 M `LineString()`, 92 M genexpr steps) | 85.3 |
| `chord_bearing_mod180` per segment | 3.98 M | 40.3 |
| `wall_geometry._straight_runs` small unions | 82,094 unions | 45.4 |
| `wall_geometry._band_polygon` | 106,990 `unary_union` | 50.1 |
| `contact._narrow_rows` | 3,674,984 | 79.6 |
| `placement_boxes.box_gap_m` / `placement_contact._seg_gap2` / `_box_apart` | 37.7 M / 35.5 M / 85.6 M | ≈ 60 |
| `basins._rim_index` STRtree over a whole object's linework parts | 308 trees | 73.7 build + 35.8 freeing them (`_LRU.put`) |
| `terrain_edge._outward` `.coords` reads | 5.9 M | 42.6 |
| `flat_site_mode._find` / `_union` (run 1 counts) | 203 M / 101.5 M | ≈ 25 |

## 3. The four findings

### 5a. Door wells — 595.7 s (583.0 plain)

| part | calls | s |
|---|---|---|
| witness pass `door_wells.py:129 _sill_witnesses` (`obj8._witness` 27,112 calls 62.5) | 1 | 68.0 |
| rule 3 `building` (`door_wells.py:220`) | 996 | 386.0 |
| rule 3 `shell` (`door_wells.py:236`) | 996 | 113.4 |
| rule 3 `above` (`door_wells.py:240`) | 1,149 | 26.1 |
| family loop outside the three reads | — | 2.2 |

- Inside the 1,992 `building` + `shell` reads (`at_grade_geometry` 495.7 s):
  **437.3 s is `_in_window(lu, within, False)`, the linework window**
  (`obj8.py:1130`), measured by splitting `_in_window` on its `polygons`
  flag: LINES 2,304 calls 437.3 s, POLYS 14,344 calls 0.4 s. Door wells
  take `[1]` (the polygons) at `door_wells.py:233-234` and `:237-238`; the
  linework is never read. The remaining 58 s is `memo_union`, the linework
  affine (`frame_entry.transform`, 82.9 s over all 2,304 calls, also
  unused here) and `_place`.
- Memoisation: 996 `building` calls = 996 distinct (placement, window)
  keys, 291 distinct placements, 169 distinct resources; `shell` the same;
  `above` 1,149 calls = 1,149 distinct, 324 placements, 202 resources. No
  repeated key: a placement-level memo buys nothing. The resource-level
  memo already works (`memo_union` 14,344 calls, 1,937 unions computed).
  `is_building` 210,462 evaluations over 169 resources cost 1.1 s — not a
  sink. `_place` 14,344 calls 21.7 s; `frame_entry.enter` 23,918 calls
  65.0 s (4,300 from `_place`; 40.2 s is `obj8_grade._place_all` in the
  cluster profiles). 701 of 996 `building` reads return nothing.
- Refused regions: 159 regions reach rule 3; **148 end BASEMENT and cost
  520.4 s of the 525.5 s** (building 384.9, shell 113.2, above 22.3). The
  4 wells cost 1.7 s. Worst single regions are jetways with ONE member
  read: `OTHH_Jetway_Type4.obj` 8.4 + 2.0 s, Type5 7.0 + 2.3 s.
- Reordering: the BASEMENT test needs the union of all three covers and
  prints the cover percentage, so it cannot move ahead of the reads without
  risking the refusal text. It does not need to: dropping the unused
  linework leaves rule 3 at ≈ 60–90 s.

### 5b. Pack partition — 540.3 s profiled cold (519 plain loaded; 50.3 warm)

Five blocks of 80–180 s, no single sink: contact partition 180.5
(placing 167,677 parts 86.5; narrow tests 82.8), member build 82.3 (skirt
38.5, base profile 37.8), connectors 89.5, clusters 88.7, object read 83.5.
- Pairs: `pairs_tested` 2,440,243 and contacts 506,044 are the totals AFTER
  the rebake extension (`OTHH.rebake.json`); the load partition finds
  350,927 contacts and 101,946 abutments. The load-only pair count is not
  printed; by narrow-pass time the load pass is 82.8 s and the extension
  172.9 s. `_narrow_rows` runs 3,674,984 times over both.
- Spatial index: broad phase is vectorised (`_broad_pairs` 4 calls 10.5 s),
  not a sink. The narrow phase is Python-per-pair (`_narrow_rows` 22 µs a
  call) feeding numpy batches (`flush` 20,390 batches 138.7 s).
- Per-resource work repeated per placement: small here. 1,087 members,
  167,677 parts; `plan_hull` runs once per part (193,710 calls including the
  extension). Distinct resources among the 1,087 members were not counted.
- The warm stage's 50 s is work the cache does not hold (object read and
  witnesses). Not profiled warm.

### 5c. Rebake plan — 290.9 s (282.4 plain, same warm and cold)

`extend_partition` re-adds 6 plate resources (95 members, 6,235 parts)
against 1,256 neighbour parts and spends more than the whole-pack contact
partition (281.6 vs 180.5 s):
- `_narrow_pass` 172.9 s — twice the load pass's 82.8 s, for 155,117 new
  contacts. `contact.py:1229-1232` keeps same-member pairs, so each plate
  object's parts are tested against each other.
- `placed_parts` 25 calls 55.8 s — one for the new members, 24 that
  re-place WHOLE base neighbour members (`contact.py:1183`) to recover the
  few near parts. That is the recomputation of what the first partition
  had: the cache revives recipes, not placed parts.
- 47.5 s in the neighbourhood loop (`contact.py:1170-1174`, 31.0 self +
  16.5 in `.all`): one full-array box compare per new part, 6,235 × 167,677.
- Nothing of this is cached: a warm build pays all 282 s.

### 5d. Second planar pass inside `solve` — 500.8 s profiled (≈ 330 plain)

| part | pass 2 (profiled s) | inputs differ between passes? |
|---|---|---|
| wall corridors | 171.1 (≈ 120 plain) | NO in a build. `classification` is read only at `wall_corridors.py:589`, `mouth_roads(...) if measure else []`, and every later use is behind `if measure`; `planar/build.py:217` never passes `measure`. once362's "mouth_roads differs" is the replay probe's path only. |
| basins | ≈ 178 (≈ 160 plain) | YES for the cut (cells, runway/tunnel unions, pads). NO for the cost: 315.2 of 355.4 s is `_rim_open` (`basins.py:236`), the rule-3 rim diagnostic — "reported, never a refusal" — reading only the ring and its members' at-grade linework. |
| arrangement | ≈ 41 | yes (ribbon-free cells) |
| shapes + constraints | 132.0 (≈ 66 plain) | yes |
| door wells, sunken roads, tunnel corridors, thin plates | 0 | once362 holds |

## 4. Ranked plan (OTHH; seconds are plain-time estimates from the profile)

| # | candidate | site | saves cold | exactness | pool? |
|---|---|---|---|---|---|
| A | Door wells stop computing the at-grade LINEWORK (affine + window) they discard | `airport/obj8.py:1129-1131`, callers `airport/door_wells.py:233`, `:237` | **≈ 445** (437.3 window + ≈ 20 affine) | byte-identical by construction (value never read) | n/a |
| B | Wall corridors read once per build (join the once362 reads) | `planar/build.py:217` → `planar/pack_reads.py:76` | **≈ 120** | byte-identical by construction when `measure` is False | n/a |
| C | Basin rim diagnostic memoised across the two passes, keyed on ring bytes + member ids | `planar/basins.py:558` (`_rim_open`), store on the `ResourceCache` | **≈ 145** | byte-identical by construction (content key; a different ring misses) | n/a |
| D | Rim index over the parts near the ring only (bbox ⊕ reach) instead of the whole object's parts | `planar/basins.py:279 _rim_index`, `:518` | ≈ 50 (pass 1; STRtree 73.7 + freeing 35.8 over two passes) | needs a short proof: a part farther than `reach` from the ring's box cannot answer `query_nearest(max_distance=reach)` | n/a |
| E | Rebake extension: index the neighbourhood query; re-place only the near components | `airport/contact.py:1170-1174`, `:1183` | ≈ 85 (47.5 + ≈ 40) | byte-identical by construction (same set, same parts) | n/a |
| F | Cache the rebake extension beside the partition (key: partition fingerprint + plate paths) | `airport/rebake_plan.py:222`, `airport/partition_cache.py` | 0 cold, **≈ 195 warm** on top of E | byte-identical if the key is complete; needs a twin | n/a |
| G | Pool the per-member pack work: `_build_member` 82, `placed_parts` 86, witnesses 44, `compose_profiles` 48 | `airport/pack_partition.py:537`, `airport/contact.py:597`, `airport/obj8.py:674`, `airport/placement_family.py:536` | ≈ 170 (260 s of independent work, ≈ 4× on 6 cores after pickling) | byte-identical if results merge in input order; each worker parses its own resources (total parse 19 s) — do NOT ship the multi-GB `ResourceCache` | yes, per member / per cluster |
| H | Narrow contact pass in parallel chunks (load 83 + extension 173) | `airport/contact.py:885` | ≈ 150 | NEEDS A PROOF: the pass consults the union-find as it goes (`contact.py:1229-1232`), so order may decide which pairs are tested | yes, part arrays shared read-only |
| I | Wall corridors pass 1: bulk segment construction and bearings, or one worker per family (139 families) | `airport/wall_geometry.py:79`, `:101`; `airport/wall_corridors.py:618` | ≈ 70 of 120 | vectorising needs a proof (float order); per-family pool is exact but the intake order is flagged ORDER-DEPENDENT at `wall_corridors.py:597` | yes, per family |
| J | Door-well witness pass per placement | `airport/door_wells.py:129` | ≈ 40 of 68 | exact if merged in input order | yes |
| K | `_fronting` and `_tied` vectorised | `constraints/pads.py:293`, `constraints/stretches.py:334` | ≈ 60 (both passes + verify) | needs a proof (float order of scalar loops) | no |
| L | Frozen engine: fingerprint the 24 cache modules at freeze time instead of the app version | `airport/partition_cache.py:146 code_digest` | 0 per build; an app update that leaves those modules alone stops cold-starting every user (−490 s for them) | no output change | n/a |

Arithmetic: cold ≈ 2,340 → A–E **≈ 1,495**; + G, H, I, J, K ≈ 1,005.
Warm 1,894 → A–E ≈ 1,049; + F ≈ 855; + I, J, K ≈ 685.

**Not reachable: ≤ 600 s cold at OTHH with this list.** After A–E the
remainder is ≈ 500 partition, ≈ 200 rebake, ≈ 130 door wells, ≈ 120 wall
corridors, ≈ 120 basins pass 1, ≈ 140 constraints (two passes), ≈ 75
arrangement, ≈ 100 everything else. Getting under 600 cold needs the
partition and the rebake extension rebuilt around a shared, parallel
contact pass (G + H done well ≈ −400), plus I, J, K. That is design
work, not a patch. Two things would move the bar without it and are the
owner's to rule: dropping the basin rim diagnostic from the build (a note,
never a gate: −160 s more), and Law C wall corridors, which only OTHH
enables (`law/airports.toml [OTHH] kerb_wall_corridors`: 240 s today).

## 5. Environment

**(i) App 2.3× slower than the harness: contention, not the frozen engine.**
Not run frozen — the app's object stage rewrites the pack in the X-Plane
install and I found no safe way to run it. From
`~/Library/Logs/XPTerrainBuilder/engine-stderr.log` (OTHH 5,204.0 s, line
66377):
- The OTHH tile's lines interleave with tiles −13−078 (SPJC: mesh, masks,
  DSF encode), +30+031 (HECA, then its mesh and DSF), +40−004 (LEMD,
  1,593 s) and +39−107 (KASE, KEGE). OTBD and OTBH ran in the same tile.
- App pack partition ≈ 487 s (8m07 total at step end) vs harness 519 s:
  the same. App HECA 776.7 s vs sweep 711.1 s: 1.09×.
- The slowdown appears only once the other tiles are busy: the app's
  classify step is 41m16 against 1,008 s (2.46×).
- That app build predates once362 (door wells ran again inside solve).
Unverified: whether the app's workers also land on efficiency cores;
`Sources/` sets no QoS that I could find.

**(ii) Single-threaded stages: all of them.** `src/auto_patch_v2` has no
process pool, thread pool or worker thread (grep), the build process sat at
99–100 % of one core at every sample, and HiGHS ran 1.5 s. Five
performance cores idle for the whole build.

## 6. Other airports (sw1034, cold, plain, LOADED machine — sweep ran in parallel)

Every stage over 60 s:

| airport | total | stages > 60 s |
|---|---|---|
| OTHH | 2,419.5 | pack partition 519.2, planar 1,008.2, constraints 73.9, solve 392.1, rebake plan 292.4 |
| HECA | 711.1 | pack partition 208.3, constraints 76.5, solve 251.1, verify 71.8 |
| KCLT | 440.9 | planar 83.9, solve 157.3 |
| KASE 62.2, SPJC 96.5, CYXY 30.7, NLWF 7.0 | — | none |

HECA misses the bar cold and has neither door-well nor wall-corridor cost
(planar 42 s): its 251 s solve and 208 s partition are the generic costs
(G, H, K and the second pass), not the OTHH-specific ones. A and B do
nothing for HECA.

## 7. Leads from the peer session

- `O4_Airport_Elevation_Insets.package_object_footprints` →
  `dsf_reader.read_dsf_object_buildings` / `_compute_dsf_object_buildings`:
  zero calls in the airport harness build. It is on the tile path only and
  is NOT measured here.
- Law C wall corridors: confirmed, 120.3 s plain pass 1 and the same again
  in pass 2 (B removes pass 2).

## 8. Unverified / not done

- Cold plain total on a quiet machine was not measured (both cold runs were
  profiled); 2,340 s is run 2 + (≈ 500 − 50). The cold partition plain
  figure is the loaded sweep's 519 s.
- Savings are profile-derived estimates from single runs; none was
  implemented or replayed, so no byte-identity was demonstrated.
- Per-stage GEOS / numpy / Python shares are given for the whole build and
  qualitatively per stage, not as a per-stage table.
- Distinct resources among wall-corridor placements (372) and partition
  members (1,087) not counted; load-only `pairs_tested` not separated.
- The second pass's split (basins ≈ 178, arrangement ≈ 41) is total ÷ 2
  and log arithmetic, not a per-pass measurement.
- Frozen engine not run. `check_build_time.py --runs N` not run
  (3 × 45 min would not fit; single runs only).
- `frames.py register --kind profile` REFUSED: "kind must be one of
  ('capture', 'rebake', 'patch', 'graded', 'mesh', 'inset')". The files are
  copied to the frames directory but not registered; I did not edit the tool.
- While run 2 was timing I ran a few 2-second `pstats` reads and file reads
  on other cores.
- The lane-local partition cache written by run 1 was moved aside (not
  deleted) to make run 3 cold; run 3 wrote a fresh one.

## 9. Files

`/Users/noah/XPTerrainBuilderData/.harness/frames/prof362/`:
`OTHH_run3_cold_nohb.prof` (the profile to read), `OTHH_run1_cold.prof`
(corrupt cumulative times; counts only), `run1_cold_cprofile.log`,
`run2_warm_plain.log`, `run3_cold_cprofile_nohb.log`,
`run3_doorwell_census.json` (per-region rule-3 time and outcome),
`prof362-stage-trees.txt`, `prof_run.py` (runner), `ps.py` (pstats reader),
this report. Harness artefacts: `/tmp/harness/prof362_OTHH*`,
`prof362_OTHH_warm*`, `prof362_OTHH_r3*`.
