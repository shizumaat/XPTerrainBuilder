# Late stage reuses the base map's prefix: spec and consumer census (2026-10-20)

Status: PROPOSAL; phases 1 and 2a landed by lane m8 (exact: HECA body identical). Owner approval: RULINGS via #1056, 2026-10-20 (Q21 (b)): "the late stage reuses the base map's prefix products (planar arrangement, constraints) outside the gap pieces". Issues: #803, #412. Census law: RULINGS 2026-08-30l.

## 1. Problem (measured)

The last stage (`pipeline/late_stage.py`, spec §55 (4)) does three things:
1. It cuts the gap pieces by the base's levels.
2. It runs **the caller's whole prefix** on the cut classification (`late_derive` → `prefix.run_prefix`).
3. It solves only the followers.

When an airport has both gap pieces and pad roads (`run_last_stages`, 13a (1)), it does this **twice**: once for the gap stage, then once for the roads-only stage.

HECA, main e2f2e7e43, cold miss arm (`check_build_time --runs 3`, `O4_V2_STAGE_CACHE=0`), loaded machine:
- Median build: 1,091 s.
- `late_stage` median: 367 s.

The sampled profile of one build (1,336 s, loaded) breaks the late stage's 598 s down as follows:

| part | s |
|---|---|
| `late_derive` × 2 | 462 |
| — planar | 221: `build_structures` 85 (of it `shore_region` 42.5, fixed by #1053), arrangement 102 (pass C 30, `platform_split` 16, zones 15, shore walls 10, weld 7), pack reads 14 |
| — constraints | 131 (`run_generator` 111: `junction_mesh` 23, `apron_within_shape` 21, `road_within_shape` 11, `taxi_box` 11, `zone_bands` 10, `foot_rows` 8, `pad_flats` 7, …) |
| — road profiles | 59 |
| — channels | 50 (`road_ramp` 34) |
| `late_cut` | 77 (`extend_pad_roads` 73: the all-cells union 34.5, the per-way `_way_intervals` overlay 30) |
| `late_solve` | 58 |

## 2. What the solve uses (the reason reuse is lawful)

- `late_fixed` (`stage_one_map.py:137-147`) holds every vertex on a standing face as a **constant** at its base level, joined by exact coordinate.
- `late_constraints` (`stage_one_map.py:341-345`) **drops every row whose vertices are all constants**.
- So the late solve reads only the rows that touch a follower, plus its own rows: `pad_ramp_rewrite`, `runout_rows`, `pad_grade_release`, `gap_follow_rows`, `slab_weld_rows`.
- Every derived row inside the base region is never solved against.

What still consumes the whole re-derived map:
- `cs_full` becomes the build's `cs` (`build.py:621-622`). It feeds the emit, the publication, verify, the xplat dump, and the late record's certificate.
- `stage` feeds `joint_steps`.
- `strips` feeds the publication.

A reuse design must therefore produce `pm`, `cs_full`, `stage` and `strips` for the WHOLE cut map. It may build them from the base's products wherever the cut changes nothing.

## 3. What differs between the base and the cut classification

- **Base:** `gap_free(cl)` drops the gap-ref cells and the `pad_road` cells. Ids are kept.
- **Gap stage:** `cut_classification` keeps every standing cell (same id). It replaces each piece by its parts:
  - new ids from `max(id)+1`;
  - refs `<ref><suffix>`;
  - roles `groundside_pavement` or `parking_lot`.
- **Roads-only stage:** its base is the gap stage's `pm_g`, not the main base. Pad-road cells are re-added with new ids, extended by `extend_pad_roads`, and get run-out cells (`mint_ramp_runouts`).
- **New cells are late cells** (`classify/roles.py:750-754`). They join the arrangement only in pass C.

## 4. Consumer census (one row per pass the derive runs)

L = local: a changed cell influences a bounded neighbourhood. G = global. "vid" = keyed by vertex or face id, which the re-noded map renumbers as a whole (polygonize/walk order, `planar/build.py:306-342`). Ruling column: what this spec does with the pass.

| pass | L/G | radius of a new cell | key | ruling |
|---|---|---|---|---|
| pack, ring and wall-corridor reads (`planar/build.py:233-248`) | L; already memoised per build (`pack_reads._store`, `cache.placed`) | 0 for gap pieces. Pad roads count as structure cover (`structure_approach.py:436-440`) | object/ref | KEEP the memo. Nothing to do |
| `crossing_claims` / `underpass_bores` | L (reads every cell) | the way | way key | RE-RUN (cheap) |
| channels, `build_structures`, `build_basins` | L: "a gap piece never leads" (standing cover excludes gap; basins cut gap cells last). Pad roads are not excluded | 0 for gap; the structure for pad roads | ref | gap stage: REUSE the base's result. Roads stage: RE-RUN. A zero-effect bar is measured first (§6, phase 2) |
| `mouth_pair_roads` | L (`taken` = union of all cells) | the mouth-road face | ref | RE-RUN (cheap) |
| weld, zones (`overlay.py:219-228`; `zones.py:292`) | exclude late cells, so identical | 0 | — | REUSE |
| pass A noding (`overlay.py:350`) | G operation, identical input | 0 | — | REUSE (keep the intermediates) |
| pass B pads | identical except `shelf_regions(late=…)`, whose held ground includes the late polygons | a shelf beside a piece | ref | RE-RUN `shelf_regions` only; REUSE the rest of pass B when no shelf touches a late cell, else RE-RUN pass B |
| pass C (`ribbons.py:29-127`) | the first `_faces_of` is identical; the final union is G as an operation, local in effect (≈ grid to `3·cut_w`); face order kept by `base_order` | grid to `3·cut_w` | geometry | RE-RUN (it is where the late cells enter) |
| claims, slivers, `dissolve_sliver_zones` | L with neighbour cascades | adjacent faces | geometry | RE-RUN |
| face walk, ids, DEM sample, `covered_ground`, `ramp_targets` | DEM L; ids G | — | **vid** | RE-RUN (ids) |
| `build_shapes` | G (pavement components); gap parts labelled after the union | shape labels near parts | vid | RE-RUN |
| flat_site | ~0 | — | — | REUSE the base's verdict |
| road_profile | per tile way + the map's route breaklines; `band_fn(pm)` changes near pieces | ways whose band or route changes | way id; `preferred` by vid | REUSE the per-way clamp by way id where the band is unchanged. Re-answer only the vertices within R |
| channels `runway_chord`, `taxi_trend`, `apron_trend`, `eat` | airside only | 0 (followers are never airside) | vid | REUSE, remapped by coordinate |
| channel `road_ramp` + coverage join | G (routes from airside contacts) | route length | vid | RE-RUN, bounded to the routes touching the region R (phase 3) |
| `shape_stage` (`reach_band_values`, Dijkstra over taxi routes) | G graph, airside | 0 | vid | REUSE, remapped |
| generators, airside families (runway_*, taxi_*, junction_mesh, apron_*, hard_plane, eat_anchor_rect, strips/zones/raoa, platform_*, frontage_hold, reach_bands, no_step_*) | mixed; rows name airside or pad vertices, all constants, so all are dropped from the late solve | n/a to the solve | vid | REUSE the BASE's rows, remapped by coordinate (phase 3). Prerequisite: a per-generator role census proving no row can name a follower. `pad_fronting_level` and `groundside_frontage_level` are flagged |
| generators, groundside families (road_within_shape, road_ramp, road_contact, road_coverage_join, wall_terrace, groundside_ramp, transverse, cross_shape_pairs, groundside_frontage_level, pad_fronting_level, foot_rows, structures/rim_level/basins/channels, water_pins, seam_pins, flat_datum) | can name follower vertices | route / face | vid | RE-RUN, restricted to faces within R (phase 3: a generator `region` argument) |
| assembly (ceiling, pavement_cap, seam_exempt) | L per row, but reads across generators | row | vid | RE-RUN on the merged set |
| jetway strips | L per cluster pad | pad | vid | REUSE, remapped |
| `hold_pass` | not read by `late_solve` (`late_stage.py:301`) | — | — | SKIP in the late derive |

R, the re-derive radius, is `max(gap_follow.reach_m, reach_m(pad), pad_ramp.stand_off_m, 3·cut_w) + one face ring`, measured from the late cells.

## 5. The design

1. **Phase 1, exact, LANDED (lane m8).** The pad-road exit walk no longer overlays every tile way with the whole airport's union. `ribbon_mint._way_intervals` answers a way that does not meet the extent with the prepared predicate. An empty intersection is exactly a false `intersects`, so the output is byte-identical. Expected: most of the 30 s.
2. **Phase 2a, exact, LANDED (lane m8): the arrangement's FRONT.**
   - `planar/arrangement_memo` is new. `build_arrangement`'s front (the runway ridges, the weld, the zones, the apron cut, the pad terraces, the platforms) reads only the NON-late cells, which are the same objects and values in the base map and in both late derives.
   - It is held for the build (`pipeline/build.build` is `@scoped`) and served on a value-identical key: the pickled digest of the non-late cells, keepouts, cut lines and grid, plus the airport and law held weakly.
   - Its mutable records (registries, edge report, pad-clip and platform records) are deep-copied on store and on serve.
   - `shelf_regions` reads the late polygons, so it and everything after it (landing, plateau, pass A, pass B, pass C) still run.
   - Outside a build nothing is held.
   - A cell's id is not in the key: the front never reads it (the weld orders by position), and the last stage renumbers cells it did not change (HECA: 20 `gapapron` cells, ids only).
   - Up to 3 fronts are held.
   - Profiled cost of the front per derive at HECA: about 40 s (weld 7, zones 15, platforms 16, terraces/apron cut ~5).
   - **Measured, HECA closing build `m8late4`.** The build runs four derives: main, ribbon-free stage 1, gap stage, roads stage.
     - The **gap stage is served** the stage-1 front.
     - **Main misses**: its `Airport` is a different object from the one the later derives get.
     - **The roads stage misses, lawfully**: it carries one more non-late cell, `runout:0`.
     - Body `80456bf49005…` is identical to main.
   - Serving the roads stage would mean keying a front by its cells and patching in the run-out cells. That belongs to phase 2b.
2. **Phase 2b, LANDED (lane m8, exact): the late derive's own repeats.**
   - A profile of the late stage on replay (`v2_solve_replay --late-from`, HECA, loaded machine) showed two pure repeats inside every derive.
     - Pass C's pad clip rebuilt the whole airside's mitred band buffer per ribbon (`ribbon_weld._weld_to_rim`). It is now `rim_zone`, once per clip.
     - The road profiles built a fresh `LineString` of every `through` way for every vertex (`RoadProfiles.answer`). It is now `RoadProfiles._line`, one per way, keyed and checked by identity, never pickled.
   - Replay A/B, same capture and base:
     - `_weld_to_rim` 10.9 → 1.6 s; `RoadProfiles.answer` 36.9 → 23.7 s.
     - `run_last_stages` 299.7 → 281.8 s (−6 %).
     - Solved z identical (max |Δ| = 0 over 47,051 vertices).
   - **Not taken:** the structure pass's per-overlap-pass `mouths()` / `mouth_at_pavement` / `pavement_half_widths` (about 19 s per late stage). Their inputs are pass-invariant, but `mouths()`' products are mutated in place (`m.approach`). Reusing them needs a copy discipline the #971 owner should rule on first.
3. **Phase 2c (not done): the planar intermediates past the front.**
   - The base's planar build returns, beside `pm`, the arrangement intermediates: pass A's noded lines, pass B's pad lines and faces, the first `_faces_of`, and the structures/basins result. These live in memory, are never cached on disk, and are dropped after the late stage.
   - The gap stage's derive starts pass C from them. The roads-only stage starts from the gap stage's own intermediates (`pm_g` is in memory).
   - Bar: on HECA, OTHH and KCLT, every standing vertex of the cut map is at the same coordinate and level (the canonical join). The `ribbon_airside_added/removed` counters (`overlay.py:418-424`) stay 0.
   - Expected at HECA: about 90–120 s of the 221 s planar, × 2 derives.
3. **Phase 3, the rows.**
   - `cs_full` = (the BASE's rows, remapped by coordinate, for every generator proven airside-only) + (the groundside generators re-run with `region = faces within R`) + the late stage's own rows.
   - The assembly post-passes run on the merged set.
   - Prerequisite: the per-generator role census (§4, airside row), written as a twin that fails when a generator's rows can name a non-airside vertex.
   - Bar: verify and census families unchanged on HECA, OTHH and KCLT, or each changed row read and within the visibility bars (pavement 0.05 m, ground 0.5 m).
   - Expected at HECA: about 70–90 s of 131 s constraints, plus about 40 s of road profiles and channels, × 2.
4. **Not reused, by ruling:** the arrangement's ids and `build_shapes` labels are always re-derived. A remap by coordinate is the only join (canonical-identity law).

## 5a. Phase 3 per-generator census (measured; phase 3 STOPPED)

**Method.** I re-ran every generator in `constraints.GENERATORS` on HECA's base map and on the late stage's cut map, using `v2_solve_replay --late-from` products: capture at main 11c9b7d89 + #1069, gap stage `pm_cut_1`, roads stage `pm_cut_2`. For each generator:
- the base rows were remapped to the cut map by coordinate (`remap_row`);
- the two sets were compared as multisets, ignoring `source.inputs`, the face/way ids, which renumber;
- the cut rows that name a follower (`late_followers`) were counted.

**Gap stage.** Total generator wall on the cut map is 42.7 s.

| class | generators | cut-map wall |
|---|---|---|
| SAME as the base, no follower named | runway_* (6), taxi_chain, taxi_centerlines, taxi_box, junction_mesh, junction_raw_transverse, no_step_pairs, no_step_rate, reach_bands, strip_* (3), resa_transverse, end_corridor_longitudinal, raoa, pad_frontage_level, pad_fronting_level, platform_plane, landing_level, frontage_hold, frontage_near_miss, structures, rim_level | 25.5 s (junction_mesh 15.8, taxi_box 2.6, no_step_pairs 1.2) |
| AIRSIDE but DIFFERENT on the cut map | apron_within_shape (±7,770 of 354,462), apron_edge_portions (+2,112/−1,106), pad_flats (±36), pad_slope_ceiling, platform_collar, landing_runout | 9.0 s |
| names FOLLOWERS (not airside-only) | **triangle_planes (80 rows)**, road_within_shape (2,190,500), road_ramp, road_contact, road_coverage_join, wall_terrace, groundside_ramp, transverse, cross_shape_pairs, zone_bands, groundside_frontage_level | 8.2 s |

**Roads-only stage, against the main base.** The SAME set shrinks further: taxi_chain, no_step_pairs, pad_frontage_level, pad_fronting_level, frontage_near_miss and platform_plane all differ. Its real base is the gap stage's map, which this comparison did not use.

**Verdict: phase 3 as specified is STOPPED and returned to the owner/master.**
1. **The "no airside generator names a follower" twin would FAIL as stated.** `triangle_planes` (a taxi generator) names 80 follower vertices at HECA. The airside/groundside split is not a property of the generator families.
2. **Equality with the base is empirical, not structural.** Six airside generators produce different rows on the cut map because pass C re-nodes faces beside the pieces. The SAME list is one airport's measurement, and no witness separates the cases in general.
3. **Reused rows would carry the BASE's face ids in `source.inputs`.** Verify, census and publication read those ids. A face-id remap would be a new identity join.
4. **The prize is small.** The SAME set is ~25 s per derive at HECA, about 50 s per late stage (two derives), out of ~280 s.

Recommended instead: leave the generators re-derived. The one outsized cost the census surfaced is `road_within_shape` minting **2,345,423 rows on the cut map against 157,121 on the base**, 2.19 M of them naming followers. That deserves its own issue: the late assembly and `late_constraints` filter carry them.

## 6. Bars and order

- Phase 1 ships alone: byte-identical body.
- Phases 2 and 3 each:
  - one HECA capture replay A/B (`--late-from`), then ONE HECA cold build;
  - every vertex within the bars against main;
  - `late_stage` wall down on `check_build_time --runs 3`.
- Two fix iterations per phase, then stop and report.

## 7. Open items

- **The per-generator role census** (phase 3 prerequisite). Not done.
- **Whether `groundside_pavement` (the gap parts' role) is in `road_family_roles`.** That decides whether the parts enter the `road_ramp` routes and so the bound of R for channels.
- **Late-stage sub-pass timings in the build log.** Today the re-derives run silent (`prefix.py:296`). A `--late-from` replay gives them.
- **A side finding.** The report's `constraints.by_generator` shows the base's counts while `cs` is the late one (`build.py:660`).
