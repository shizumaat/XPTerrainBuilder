# measure362 — narrow-pass pair shares, R5 exactness, cluster-profile readers, extension memo (#362)

Docs-only commits landed on main during the run; no `src` file changed, so every line reference below holds at `9d960fed`. All four measurements are taken. Both partitions were re-derived through the engine's own functions and matched the cache exactly (contacts and abutments tuple-equal at both airports).

**Headlines**
- **R5 has almost no prize and is not exact.** Dropping cross-unit pairs saves about 2.5 s at OTHH and nothing at HECA, and it mints 618 / 1,074 extra abutments.
- **All-pairs verdicts cost about 1.2–1.3× today's narrow pass**, matching the design's "worst case 1.3×".
- **The lazy-profile precondition is refuted as written**, but the real reader set is smaller than the design assumed and nothing in the production build prints, digests or publishes it.
- **An intra-resource memo covers about 93 % of the extension's narrow pass.** The test runs in placed coordinates; the only verdict differences between instances are budget "doubt" merges, attributed for Type6/Type7 only.

Wall times below are single instrumented runs on a machine with other lanes active. Read them as shares, not timings.

## (i) R5: cross-unit share and exactness

Load-partition narrow pass (`pend` is the list handed to `_narrow_pass` at `contact.py:1040-1043`):

| | OTHH pend | OTHH tested | OTHH rows | OTHH `_narrow_rows` s | HECA pend | HECA tested | HECA rows | HECA `_narrow_rows` s |
|---|---|---|---|---|---|---|---|---|
| intra-member | 541,276 (29.5 %) | 541,276 | 263,720,022 (79.8 %) | 25.4 | 106,004 (25.9 %) | 106,004 | 86,279,363 (79.3 %) | 8.2 |
| intra-unit, cross-member | 1,095,544 (59.8 %) | 592,139 | 66,359,163 (20.1 %) | 25.2 | 298,867 (73.0 %) | 171,537 | 22,399,255 (20.6 %) | 6.3 |
| cross-unit | 195,418 (10.7 %) | 182,723 (13.9 % of tested) | 284,092 (0.086 %) | 3.7 | 4,657 (1.1 %) | 3,086 | 129,439 (0.12 %) | 0.07 |
| total | 1,832,238 | 1,316,138 | 330,363,277 | 54.3 (pass 117.6) | 409,528 | 280,627 | 108,808,057 | 14.6 (pass 34.9) |

Exactness, from a simulated unit-local pass:

| | OTHH | HECA |
|---|---|---|
| units / contact components today | 110 / 14,737 | 44 / 5,246 |
| cross-unit contact edges today | 162 of 350,927 | 138 of 116,372 |
| components spanning two or more units | 2 | 9 |
| same-unit groups joined only through another unit's part | 1 (splits in 2) | 14 (107 extra components) |
| components under R5 | 14,741 | 5,366 |
| abutment candidates before the union-find skip | 828,789 | 307,551 |
| abutments today / under R5 | 101,946 / 102,564 | 40,358 / 41,432 |
| abutments only under R5 / only today | **618** / 0 | **1,074** / 0 |
| intra-member edge set | identical (249,341) | identical (81,481) |
| R5 pass wall vs today | 115.0 vs 117.6 s | 34.9 vs 34.9 s |

- **Prize:** cross-unit pairs are box-near but almost never stack rows, so removing them saves roughly 3.7 s of per-pair Python at OTHH and nothing measurable at HECA.
- **Exactness:** yes, components are joined only through another unit's part at both airports, and R5 would change the abutment set. The intra-placement edges that `bodies_of_plan` reads are unchanged.
- Cross-unit weld pairs are 0 at both airports.

## (ii) Skipped versus tested

| | pend | tested | skipped as already joined | rows if the skipped were tested | extra `_narrow_rows` s | all-pairs CPU vs today |
|---|---|---|---|---|---|---|
| OTHH load | 1,832,238 | 1,316,138 (71.8 %) | 516,100 (28.2 %) | +34,880,646 (+10.6 %) | +20.2 on 54.3 | ≈ 1.23× |
| HECA load | 409,528 | 280,627 (68.5 %) | 128,901 (31.5 %) | +29,755,432 (+27.3 %) | +6.2 on 14.6 | ≈ 1.34× |
| OTHH extension | 608,005 | 521,354 (85.7 %) | 86,651 (14.3 %) | +52,433,694 (+4.6 %) | +4.0 on 59.2 | ≈ 1.05× |

- Every skip is a cross-member pair; intra-member pairs are never skipped (`contact.py:923`).
- Skipped pairs carry far fewer rows per pair than tested ones, which is why the pair share overstates the cost.
- The CPU ratio is an estimate: measured extra per-pair seconds, plus the batched distance time scaled by rows.
- Doubt pairs today: 353 at OTHH load, 186 at HECA, 2,347 in the OTHH extension.

## (iii) Lazy cluster base profiles: refuted as stated

Every code reader of `PlanCluster.base_profile` / `.composition` and the three `WHY` keys:

| Reader | file:line | Population read | Reaches |
|---|---|---|---|
| `WHY["base_profiles"]`, `["base_planes"]`, `["base_composition"]` | `planar/cluster.py:262-266` | every cluster | the `WHY` dict only |
| whole `WHY` dict printed | `tools/v2_solve_replay.py:1926` | all keys | stdout of the classify re-derive arm (a tool, not the build) |
| `[clusters]` say-line | `pipeline/build.py:513-529` | reads `gate`, `units`, `touch_m`, `floor_split_m`, `with_rings`, `min_m2` only | build log; no base key |
| `_cluster_index` | `planar/pad_blocks.py:491` | every cluster with a valid ring, eagerly at index build | the verdict string stored per row |
| `unit_base` | `planar/pad_blocks.py:507-520` | uses only the best-overlap row of the STRtree query | `plan_blocks` `:571`, then `BlockPlan.base` / `base_cluster` (`:148-151`, `to_dict` `:155-157`) |
| partition cache write and hit | `pipeline/build.py:501-503`, `:494-495` | whole cluster tuple pickled | cache payload bytes |
| producer | `placement_family.py:861`, `:866-880` | every body group; cheap exit when no member has a plane (`:579-584`) | — |
| test | `tests/auto_patch_v2/test_base_profile_compose.py:283-289` | every cluster returned by `plan_clusters` | — |

No reader exists in these (0 hits each): `classify/evidence.py`, `constraints/cluster_pad.py`, `planar/platform.py`, `pipeline/publication.py`, `pipeline/xplat.py`, `auto_patch/engine_v2.py`.
- `xplat.py:291-296` digests partition and group counts only.
- `publication.py:325-361` reads members, area, floors, bodies and footed.
- `tools/obj8_split_report.py:708-709` calls `cluster_base_profile` itself rather than reading the field.
- The OTHH and HECA build products (`.osm`, axes sidecar, graded, report, result, progress) contain none of these keys. The 1,175 / 429 `"base_profile"` entries in `rebake.json` are the per-member field, a different thing that must stay.

What this means for the lazy lane:
- **The pad clusters do not read it at all**, contrary to the design's reader (a).
- **`cluster.py:262-266` counts over all clusters.** The three keys feed only the tool print, so they must be dropped or made on-demand.
- **`pad_blocks.py:491` reads eagerly.** It must move to query time.
- **The cache pickles the field.** A lazy field changes payload bytes and any `repr(clusters)` identity digest, so it needs a `CACHE_VERSION` decision.

Population from the cached clusters:

| | OTHH | HECA |
|---|---|---|
| clusters | 24,521 | 6,151 |
| with a composed profile (the rest take the cheap exit) | 2,288 | 1,586 |
| with rings (what `_cluster_index` reads) | 1,834 | 1,962 |
| with rings and a profile | 725 | 1,133 |
| walled and ≥ 5,000 m² | 71 (41 with a profile) | 90 (71 with a profile) |

The design's "212 pad clusters" at OTHH is the area-only count from the say-line; walled and over threshold is 71.

## (iv) Rebake extension at OTHH

The extension adds 95 members (93 jetways of 5 resources plus 2 `tunnel1.obj`), 27,690 parts and 1,256 neighbour parts. Its 608,005 pending pairs equal 2,440,243 − 1,832,238 exactly.

| Pair class | pend | tested | rows | `_narrow_rows` s | contacts found |
|---|---|---|---|---|---|
| intra-member (one jetway instance) | 502,921 | 502,921 | 1,138,068,031 (98.8 %) | 58.3 | 213,095 |
| same resource, other member | 54,358 | 5,529 | 7,518,206 | 0.4 | 791 |
| other resource | 20,892 | 2,894 | 3,973,621 | 0.2 | 391 |
| new part to base part | 29,834 | 10,010 | 2,339,814 | 0.4 | 681 |
| total | 608,005 | 521,354 | 1,151,899,672 | 59.2 (pass 259.9) | 214,958 |

- **Share of all pairs:** intra-jetway-member pairs are 502,921 of the 2,440,243 pending (20.6 %), or 27.4 % of the 1,837,492 actually tested. They carry 76.8 % of all rows stacked across both passes, because the extension stacks 3.5× the rows of the whole load pass.
- **Memo coverage:** paying one member per resource costs 27,728 pairs and 61.7 M rows. The memo covers 475,193 pairs (91.1 % of tested), 1,076.4 M rows (93.4 %) and 55.0 of 59.2 s of per-pair Python. That is about 93 % of the pass, roughly 160 of prof362's 173 s.
- **Coverage if the per-member screen is kept:** if the cheap `_narrow_rows` screen still runs per member (see doubt below), only the distance batches are saved: about 72 %, roughly 125 of 173 s.
- **Coordinates:** placed, not authored.
  - `_place` rotates by heading, translates by `o.xy` and adds `anchor_z + agl_m` (`contact.py:134-143`).
  - `placed_parts` stores those points and their boxes (`:618`, `:637-639`).
  - `_narrow_rows` screens placed points against placed boxes (`:846-882`).
  - The verdict is `d <= e2` on placed triangles (`:905-907`, `:936-939`), with ε = 0.25 m and budget 400,000.
- **Verdict differences between instances:** intra-member edge sets differ between members of one resource in every jetway type.

| Resource | members | distinct headings | members whose edge set differs from the first | (comp, comp) pairs that disagree |
|---|---|---|---|---|
| Type4 | 18 | 13 | 5 | 3 |
| Type5 | 22 | 14 | 3 | 3 |
| Type6 | 16 | 6 | 14 | 4 |
| Type7 | 27 | 18 | 24 | 1 |
| Type8 | 10 | 7 | 3 | 3 |

- **Cause, attributed for Type6 and Type7 only:** all 5 disagreeing pairs are budget doubt merges (`:863-864`, `:942-945`). The pair is tested apart in most members and merged on doubt in the members whose heading pushes the candidate × triangle product over budget. No ε-margin flip was seen. Types 4, 5 and 8 were not attributed.
- **Consequence:** a memo of the contact verdict alone is not byte-exact against today. It becomes exact only if the doubt screen is still evaluated per member in placed coordinates.

## Method

- **Scripts and outputs:** `m.py` and `m2.py` in `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/measure362/`, with `OTHH.load.json`, `OTHH.ext.json`, `HECA.load.json` and the three logs beside them. One process at a time, bytecode writes off, repo left clean.
- **Inputs:**
  - OTHH payload: `…/scratchpad/perfC362/payload.cache`.
  - HECA payload: `…/scratchpad/perfC362/basetree/Ortho4XP/tmp/engine_caches/Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/o4_v2_partition_+30+031_HECA.cache`.
  - Screen reference for the extension: `/tmp/harness/prof362_OTHH_warm.v2/OTHH.rebake.json`.
  - Code: main's `Ortho4XP/src`.
- **Re-derivation:** the payload is unpickled, a `ResourceCache` is bound to the recipes, and `contact.partition` is called with the arguments of `pack_partition.py:666-680`. `plan_hull` and `solid_height` are stubbed because the contact and abutment passes never read them.
  - OTHH: 26.7 s obj parse, then 141.6 s (placing 9.8, broad 3.0, narrow 117.6).
  - HECA: 12.3 s, then 42.5 s.
- **Instrumentation:** wrappers around `_narrow_rows`, `_narrow_pass` and `_broad_pairs` only. A tested pair is the two consecutive `_narrow_rows` calls the loop makes; skipped is pend minus tested; rows are the stacked row counts.
- **Skipped cost:** the original `_narrow_rows` is called on each skipped pair in both directions.
- **R5 simulation:** the same engine functions in the order of `partition():1023-1054`, with cross-unit pairs filtered out and a fresh union-find. This costs a second narrow pass per airport.
- **Extension:** `RP.screen_of`, then `PP.extend_partition` with `contact.extend` wrapped to record and then abort before the frame conversion. No airport load, 346 s wall.
- **Attribution:** `m2.py` re-places the Type6 and Type7 members and reruns the intra-member narrow pass, recording doubt per pair (82 s).

## Not measured

- **How many clusters `unit_base` actually queries.** It needs the planar stage's platform pads. `tools/v2_solve_replay.py --replay --from planar` with `--pad-read` would give it.
- **Whether R5's extra abutments change any group or seat.** That needs `planar/group.derive` with the DEM, via a `v2_solve_replay` stage replay or a `pack_stage_profile.py` run.
- **Doubt versus margin for Types 4, 5 and 8.** `m2.py` takes the resource paths as arguments, about 2–3 minutes.
- **Extension contact count against the build's `rebake.json`.** Its counts are post-`filtered()` (506,044 contacts), so my pre-filter 214,598 new edges cannot be compared directly; the pair count is the check.
- **Stable wall times.** The narrow pass read 117.6 s here against prof362's 82.8 s profiled, and the extension pass 259.9 s against 172.9 s. `tools/check_build_time.py --runs N` is the entry for real timings.
- **HECA extension.** HECA has 640 deferred placements but no plates (rebake plan 0.4 s), so there is nothing to measure.
- **The prof362 OTHH build stdout.** I did not locate it; the say-line claim rests on the code reading plus the product grep.
