# Linear-transport redesign — CONSUMER CENSUS (RULINGS 30l)

Read-only census produced for the Phase-2 linear-transport redesign spec
(`docs/specs/linear-transport-redesign-spec.md`, which cites these rows by
number). Mandate: RULINGS 2026-08-31b; discipline: RULINGS 2026-08-30l
("a cross-cutting geometry-law change starts with a CONSUMER CENSUS, not a
first implementation … rule the interaction for each consumer in ONE table
before any consumer is edited").

118 numbered rows across five sections, plus the test / superseded-ruling /
env-flag inventories, plus a §4a supplement that replaces §4a's rows 53-82.

**No build, no edit, no measurement was performed to produce this.** Every
row is static reading (grep / source read). Rows the spec must seam-probe
rather than trust are named explicitly at the end of each part.

---

## BASELINE AND CITATION DRIFT — read this before following any line number

Both parts of this census were measured at **`791ca959`** (main, before the
`lane/phase0roads` merge). Main is now **`33cc55ca`**. Every line number in
both parts below is **as measured at `791ca959`** and is left unedited so
the document stays internally consistent and auditable against the messages
it was delivered in.

`33cc55ca` merged `lane/phase0roads`, which added four **temporary
Phase-0 attribution arms** (measurement switches, all default-OFF, no law
change) to four of the files this census cites. They are purely additive,
so citations shift by a fixed per-file offset:

| file | offset rule (apply to the numbers printed below) | verified anchors |
|---|---|---|
| `src/auto_patch/free_road_profile.py` | old ≤ 262 → **+12**; old ≥ 263 → **+23** | `chain_profile` 123→135; `ch = _chord(i)` 262→274; `solve_free_road_profiles` 298→321; write-back 624→647 |
| `src/auto_patch/groundside.py` | old ≥ 5461 → **+8**; below that, unchanged | `_grade_limit_groundside_chords` def 5414 **unchanged**; `_tunnel_corridor_claim` call 5494→5502; write 5763→5771 |
| `src/auto_patch/pipeline.py` | old ≥ 7149 → **+12**; below that, unchanged | FRP pre-solve 6839 **unchanged**; armed limiter 7147→7159; FRP re-solve 7180→7192; conformance call 7184→7196 |
| `src/auto_patch/adjacent_ground.py` | old ≥ 7593 → **+7**; below that, unchanged | every §2/§3 citation is below 7593 and **unchanged**; supplement's `_svc_polys` 8370→8377 |

All other cited files are byte-identical between `791ca959` and `33cc55ca`.

### Two substantive corrections the merge introduces

1. **"Blocking fact" #1 below is now STALE.** `tools/road_terrain_conformance.py`
   — the RULINGS 31a terrain-conformance instrument — **is on main** as of
   `33cc55ca` (commits `8a8bee93` … `5c1614e0`), with its index row at
   `tools/INDEX.md:93`. The *second* half of that finding still stands
   unchanged and is the load-bearing one: the instrument selects
   `check_grade._ROAD_FAMILY_ROLES` off the **emitted patch**, so it goes
   blind to core-owned roads exactly as the census families do (row #91).
2. **Four new env flags**, all TEMPORARY Phase-0 attribution arms, all
   default-OFF, each landing on a pass this census names:
   `O4_ARM_CHORD_RAISE_ONLY` (`free_road_profile.py:80-90`, restores
   Amendment 3 §2's raise-only chord in place of RULING 2's both-ways chord
   — the single-clause arm the post-mortem lists as OWED),
   `O4_ARM_NO_CHORD_LIMITER` (`groundside.py:5464-5471`, no-ops the whole
   pass at all three call sites), `O4_ARM_NO_WELD_UPBUILD`
   (`pipeline.py:7147-7160`, disarms the 30b pinned up-build at that site
   only), `O4_ARM_NO_BAND_CUT_GS` (`adjacent_ground.py:7596-7607`, stands
   the 2026-08-30 band-cuts-groundside ruling down). They are measurement
   switches, not fixes, and must be deleted with Phase 0 — add them to the
   env-flag inventory's "retire" column, not its "spec-must-rule" column.

---

## Frame and two decisive distinctions found

**A. "tunnel road" names two unrelated things.** `bridges._load_tunnel_road_network`
(`src/auto_patch/bridges.py:947`) is the **OSM road-feed loader** (big_roads +
small_roads + `layout.airport_road_network`, misnamed) — it is *input*, survives
the R14-1 retirement untouched. `layout.TUNNEL_ROAD_REF`
(`src/auto_patch/layout.py:355`) is the **claim class** that retires. Six of the
seven files that grep as "tunnel_road consumers" are feed consumers.

**B. Two published regions, not one.** `tunnel_open_cut_polys` is the **portal
walk's own plan-space extent** (survives); `tunnel_open_cut_claim_polys` is
**R14-1's claim set** (retires). `bridges.py:8836-8848` states in its own
docstring that they are *not* the same region ("OTHH's descending bore FLOOR is a
`groundside_pavement` ring beside the claimed roads, 0-2 of its 33 nodes inside
the claim"). Every claim-keyed consumer must be re-keyed to the cut extent, not
deleted.

---

# 1. `free_road_profile` — callers and readers of its outputs

| # | consumer (file:line) | reads/writes what | interaction | evidence |
|---|---|---|---|---|
| 1 | `src/auto_patch/pipeline.py:6836-6839` | `FREE_ROAD_PROFILE_PRESOLVE` → `solve_free_road_profiles(layout, icao)`; inside the post-solve law-seat block, before `_rod_ckpt "14_groundside_separation"` (`:6861`) | **RETIRE** (call site) | `from .free_road_profile import solve_free_road_profiles` |
| 2 | `src/auto_patch/pipeline.py:7177-7180` | `FREE_ROAD_PROFILE_RESOLVE` → second call, after `_rod_ckpt "19_final_projection"` (`:7085`), before `_post_projection_conformance_passes()` at `:7184` | **RETIRE** | `_frp(layout, icao)` |
| 3 | `src/auto_patch/free_road_profile.py:298` `solve_free_road_profiles` | The pass. Writes `s.node_altitudes` on road-family rings only (`:598-623`) | **RETIRE** | — |
| 4 | `free_road_profile.py:257-272` (`chain_profile` chord branch) | `target[i] = float(ch)` — a bracketed station takes the pin-to-pin chord **exactly, unclamped** | **RETIRE** — this is the 7fd69ec1 cap author named in POSTMORTEM:114-122 | `target[i] = float(ch) if v is not None else None` |
| 5 | `free_road_profile.py:273-275` (envelope branch) | `hi = min(z + _allow(i,p))`, `lo = max(...)`, `clamp(v, lo, hi)` — the cap-Lipschitz envelope | **REWIRE-to-core** — this IS 31b's "bounded lift/cut smoothing over its altitude vector"; the retirement is the chord, not the envelope | RULINGS 31b names "chord/self-pin model" |
| 6 | `free_road_profile.py:91` `cap_distance_prefix` | Per-interval cap-distance prefix `C`; only caller is `chain_profile:189` | **REWIRE-to-core or RETIRE** | grep: no other src/tools caller |
| 7 | `free_road_profile.py:479-486` (self-pins) | `pins[_end] = float(v_end)` on every ≥2-station chain; `FREE_ROAD_PROFILE_SELF_PINS` | **RETIRE** — 86 % of HECA stations chorded (POSTMORTEM:119) | `out["self_pinned"] += 1` |
| 8 | `free_road_profile.py:370` (LAW 1) | `pins_node = {i: cur[i] for i in frozen}` — the one-way weld from `_road_vertex_graph`'s freeze | **REWIRE-to-contact-model** — this is 31b's "(a) pinned transitions" | — |
| 9 | `free_road_profile.py:374-396` (LAW 2) | End-on binding via `_airside_value_at(xy[i], layout, reach=hw)` at the road's own half-width | **REWIRE-to-contact-model** | — |
| 10 | `free_road_profile.py:78/86/624` `PROFILE_KEYS_ATTRIBUTE` / `profile_owned_keys` / `layout._free_road_profile_keys` | The limiter's exemption key set | **RETIRE — NO PRODUCTION READER.** Only `tests/test_free_road_profile.py:191,231` read it | `groundside.py:5520-5560`: exemption "RETIRED … then REFUTED by its own arm (CYXY +187 law-true rows)"; module docstring `:44` "THOSE KEYS STILL HAVE NO PRODUCTION READER" |
| 11 | `free_road_profile.py:417` `layout._free_road_binding_refusals` | Published near-misses | **RETIRE** — read only by `tests/test_free_road_profile.py:301`; **not** in the `to_osm` sidecar | `layout.py:3795-3900` key list has no such key |
| 12 | `free_road_profile.py:435-446, 504-530, 569-593` `O4_FRP_DIAG` | JSONL per-chain dump | **RETIRE** | — |
| 13 | `groundside.py:2887` `_road_vertex_graph` | `(keys, xy, adj, frozen, rings)` over the road family; `frozen` = vertices a non-road **value authority** carries (narrowed to airside+authorities by `ADOPT_FREEZE_AIRSIDE_ONLY`, `config.py:10378`) | **KEEP** — the contact model's primitive | also called by `adopt_road_airside_crossing_values:3148` |
| 14 | `groundside.py:3058` `_airside_value_at` | Settled airside value at a point, `with_gap` | **KEEP** | — |
| 15 | `anchors.py:4025` `service_seed_lines`, `:4365` `service_station_map` | The station derivation FRP borrows | **KEEP** — `anchors.py:4521-4526` uses both itself (in-solve seeder) | — |
| 16 | `free_road_profile.py:353-364` → `lateral_contiguity.cap_at` + `shape.station_cap_vector` | FRP is **reader 3** of the per-station cap vector, not its producer | **KEEP the vector** (produced `groundside.py:3488`; other readers `grade_graph.py:2219,2951`, `anchors.py:5236`; sidecar `layout.py:3890`) | `lateral_contiguity.py:176-192` |
| 17 | **`svc_free_ends` is NOT an FRP output** | Produced by `anchors.py:5733` `layout._svc_free_end_records` (the in-solve service free-end DEM tie); sidecar at `layout.py:3820`; readers `check_grade.py:6848` (EVIDENCE list, never law input), `tools/corridor_axis_coverage.py:236-256`, `solve.py:5289` (`yield_hard`) | **spec-must-rule** (it is corridor-terminus evidence, orthogonal to FRP) | grep `_svc_free_end_records` |
| 18 | **`station_caps` is NOT an FRP output** | `lateral_contiguity.station_cap_vector` → `layout.py:388 _station_caps_ll` → sidecar `station_caps`; `check_grade.py:6700, 6971, 3925-4016` — a **LAW INPUT** key; missing ⇒ census degrades loudly | **KEEP** | `check_grade.py:6690-6700` |
| 19 | `groundside.py:5414` `_grade_limit_groundside_chords` | The pass FRP was ordered against; the road family joined it wave-3; `_chord_cut_and_fill` (`:4945`) is the kernel | **spec-must-rule** — does the chord limiter still run on road roles once the core owns general roads? | `finalize.py:452`, `pipeline.py:6857`, `pipeline.py:7147` |
| 20 | `tools/` | **No tool imports `free_road_profile`.** Nothing in `tools/` or `tools/harness/` prices its outputs by name | evidence row | grep over `tools/` |
| 21 | `tools/harness/who_wrote.py` | Per-vertex authorship by measurement (`--at X,Y`, `--author SITE`) | **KEEP** — this is the seam probe for every "not decisive statically" row below | header `:1-45` |

---

# 2. `TUNNEL_ROAD_REF` / `ROLE_TUNNEL_RAMP`-with-`tunnel_road`-ref readers

| # | consumer (file:line) | reads/writes what | interaction | evidence |
|---|---|---|---|---|
| 22 | `layout.py:355` `TUNNEL_ROAD_REF = "tunnel_road"`; re-export `bridges.py:682` | the constant | **RETIRE** | — |
| 23 | `bridges.py:7628` `_claim_road_pavement` | **THE MINTER.** `_shape.ref = TUNNEL_ROAD_REF` at `:7823` (levelled) and `:8012` (graded); logs `:7830/:8016` | **RETIRE** | called `bridges.py:9654` |
| 24 | `bridges.py:8699` `log_tunnel_road_claim` | claim ledger | **RETIRE** | — |
| 25 | `bridges.py:8444` `_claim_portal_corridor_footprint` | mints the corridor strip `role=ROLE_TUNNEL_RAMP, ref=TUNNEL_ROAD_REF` (`:8585`); skips already-claimed hosts (`:8529`) | **spec-must-rule** — the *footprint claim* is mouth-D's fix (RULINGS 25e, superseded for the service-road family by 30); the *ref* retires | called `bridges.py:9681` |
| 26 | `bridges.py:8802` `log_tunnel_corridor_claim` | corridor-claim ledger | **RETIRE** | — |
| 27 | `bridges.py:8166` `_wall_claimed_corridors` | `if getattr(_s,"ref","") != TUNNEL_ROAD_REF: continue` (`:8195`) — **the waller only sees ref'd shapes** | **REWIRE** — walls must key on ramp/mouth geometry, which is exactly 28c items 2/3 ("no ramp, no walls") | called `bridges.py:9687`; docstring `:8179` "rides `ref=tunnel_road` — it was never in the set the waller saw" |
| 28 | `bridges.py:6655` `_claim_wall_adjudication_gate`, relief predicate `:6721` | `ref == TUNNEL_ROAD_REF or id(s) in _register` → wall-relief union | **REWIRE** | called `:7119` |
| 29 | `bridges.py:3496-3498` `_TUNNEL_PAVEMENT_REFS` | `("tunnel_ramp","tunnel_mouth","tunnel_corridor", TUNNEL_ROAD_REF)` — the ruling-4 branch at `:7155` | **spec-must-rule** (drop the member; the other three stay) | — |
| 30 | `bridges.py:7134-7149` covered-stretch / deck clip ref set | `TUNNEL_ROAD_REF` joined the set per RULINGS 30i | **RETIRE with the claim** | RULINGS `Ortho4XP/docs/RULINGS.md:1796` |
| 31 | `bridges.py:8970` `_stand_down_synthetic_over_claimed` | stands the synthetic rects down where a claim carries bore depth (`_STAND_DOWN_BORE_DEPTH_TOL_M`, `:8911`) | **RETIRE** — the stand-down exists only because the claim duplicates the ramp | called `bridges.py:9666` |
| 32 | `bridges.py:8652` `audit_tunnel_claim_drift`, `:8642` `_stash_tunnel_claim_depth` | claim-drift audit | **RETIRE** | called `pipeline.py:6855, 6858`; `bridges.py:9680` |
| 33 | `groundside.py:121` `claimed_tunnel_corridor` | the predicate; **six readers**: `:1540` `seat_groundside_on_law`, `:1808` `seat_service_pavement_on_law`, `:6957` `_merge_touching_groundside`, `:7274` `_separate_groundside_from_airside`, `:7376` + `:7560` `_clip_shape_yielding_to` / `_deconflict_service_overlaps_once` | **REWIRE-to-role** — under the pre-claim model these become "is this a `tunnel_ramp`?", which every one already handles | `tests/test_claimed_corridor_survives.py:231` asserts `src.count("claimed_tunnel_corridor(") >= 5` |
| 34 | `groundside.py:145` `_carry_claimed_corridor` | carries the authored profile onto a rebuilt piece; used `:7284` | **REWIRE/RETIRE** | — |
| 35 | `groundside.py:372` `BELOW_GRADE_REFS = ("tunnel_ramp","tunnel_trench","tunnel_road")` → `below_grade_sources:417` → `apply_below_grade_transition:744` (index `:757`) | the **R5 transition law** — surroundings grade toward below-grade surfaces | **REWIRE** — drop the third member; ramp/trench keep the law | R14-1 text `RULINGS.md:1497-1499` |
| 36 | `groundside.py:431` `below_grade_family_shapes` | composes `BELOW_GRADE_REFS` ∪ `gap_fill._TUNNEL_BLOCKER_REFS/_ROLES` (`gap_fill.py:166-171`) | **PARTIAL** — consumers `building_feasibility.py:698`, `flat_fast_path.py:305, 353`, `tools/trace_reach_route.py:337` | — |
| 37 | `elevation_per_surface/solver_primitives.py:3297` `_build_tunnel_road_pins` | `if getattr(shape,"ref","") != "tunnel_road": continue` (`:3319`); pins bore-floor vertices `is_hard=True`, marks `claimed_tunnel_road_pin` (`:4148`), joins `layout._seam_pin_idx` (`:4150-4152`) | **RETIRE** — the value contract dies with the claim | called `:4141`; `building_feasibility.py:663` cites it |
| 38 | `tools/trace_reach_route.py:1269-1348` | shims `SP._build_tunnel_road_pins`, records `"tunnel_road_pin"` branch | **REWIRE/RETIRE** | — |
| 39 | `road_piece_ledger.py:47, 51` `_TRACKED_REF_PREFIXES = ("tunnel_",)` | catches `tunnel_road` by prefix; diagnostic (`O4_ROAD_PIECE_LEDGER`, default `"1"`) | **KEEP** (prefix survives) | — |
| 40 | `tools/tunnel_portal_acceptance.py:401-423` (`_check_site_reach`), `:554`, `:1056-1089` (`claim_names_the_bore`) | `patch.ref_ways("tunnel_road")` — "bore geometry" = ramp **OR** below-grade claimed corridor; the claim-cover instrument | **REWIRE-to-ramp/mouth** or RETIRE the check — otherwise the OTHH acceptance battery goes SKIP silently | `:1089` `"no tunnel_road claim surface in the patch"` |
| 41 | `layout.py:444-454` `AUTHORITY_PRECEDENCE` + `to_osm` resolution `layout.py:1207` | a claimed shape **keeps its own role**, so a `tunnel_road`-claimed `groundside_pavement` ring ranks **last**; its bore value loses at emit | **evidence row** — the structural mechanism behind 28c items 2/3/4 (`RULINGS.md:1748-1751`) | `authority_rank(current_shape_role[0])` |
| 42 | `pavement_scoring.py` `G-TUNNEL-ROAD` gate (`:1769` `x["tunnel_cover"] = _cov(..., ev.tunnel_corridors)`) | **NOT the claim class** — an OSM-tag gate (`tunnel=yes` or `layer<0`) denying SERVICE class over a bore | **KEEP** — this *is* the OSM-level crossing classifier RULINGS 31a asks the redesign to build on | `tests/test_pavement_scoring.py:1403-1445` |
| 43 | `bridges.py:947` `_load_tunnel_road_network` (the **road feed**) | consumers: `bridges.py:800, 9275, 10528`; `clearance.py:1112` (`_surface_road_corridors_uncached`); `covered_span.py:66` (`publish`); `ols.py:1746` (`_emit_road_regrades`); `road_bridge_deck.py:149`; docs `pavement/service_roads.py:969`, `osm_load.py:1372` | **KEEP ALL** | body `:947-1035` — pure OSM cache merge |
| 44 | `road_bridge_deck.py:100` `_BELOW_GRADE_REFS` | `("tunnel_ramp","tunnel_corridor","tunnel_trench","object_basin_trench")` — **does not include `tunnel_road`** | **KEEP** | — |
| 45 | `road_lanes.py:291` `road_lane_exclusion_union` → `crossing_terrain.py:223` | depressed-public-road corridor seeded on mapped `tunnel=yes` bores (feed) | **KEEP** | `tests/test_road_lanes.py:159` |

---

# 3. The published open-cut regions

**Complete reader set — `grep tunnel_open_cut` over `src/` + `tools/` returns
exactly these. `tools/` has ZERO readers of either attribute.**

| # | consumer (file:line) | reads/writes what | interaction | evidence |
|---|---|---|---|---|
| 46 | `bridges.py:7463` `_tunnel_open_cut_regions` | derives `(level_zone, approach_zone, level)` from the portal walk | **KEEP** | — |
| 47 | `bridges.py:8826` `publish_tunnel_open_cut_regions` → `layout.tunnel_open_cut_polys` (accumulates) | called `bridges.py:7668`, **inside the retiring `_claim_road_pavement`** | **KEEP the region, RE-HOME the call** — publication must move out of the claim pass | `:7656-7668` |
| 48 | `bridges.py:8873` `publish_tunnel_open_cut_claim_set` → `layout.tunnel_open_cut_claim_polys` | called `bridges.py:9662` with `_claimed` | **RETIRE** | — |
| 49 | `bridges.py:8486` | `_claim_portal_corridor_footprint` re-calls `_tunnel_open_cut_regions` **directly** (does not read the published attr) | **spec-must-rule** | — |
| 50 | `adjacent_ground.py:3447` `claim_edge_profile_index` (reads at `:3472-3474`) | unions **both** lists → descending-ring seniority index; consumed by `emit_authority_retreat_walls` (`:3509`, read `:3608`) | **REWIRE** — loses the claim half; the cut half stands | `O4_CLAIM_EDGE_SENIORITY` (`:3387`) |
| 51 | `groundside.py:5145` `_tunnel_corridor_claim` | reads **only** `tunnel_open_cut_claim_polys`; consumed by `_grade_limit_groundside_chords` at `:5494` as the node-book exclusion (`stats["tunnel_corridor_excluded_rings"]`) | **REWIRE-to-cut-extent** — otherwise the exclusion evaporates and bench values travel across the cut boundary again | `bridges.py:8836-8848` measured: the bore floor is 0-2 of 33 nodes in-claim |
| 52 | env `O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION` (`groundside.py:5142`, default `"1"`) | byte-identical off-arm | **spec-must-rule** | — |

---

# 4. Road-family roles — who writes their altitudes, and who assumes they exist

> **§4a below (rows 53-82) is SUPERSEDED for completeness by the §4a
> SUPPLEMENT at the foot of this document.** The rows stand as correct
> individually; the supplement replaces the claim that they are the whole
> set. §4b (rows 83-102) is unaffected.

### 4a. ALTITUDE WRITERS on `service_road` / `service_junction`, in pipeline order

| # | writer (file:line) | function | when (call site) | interaction |
|---|---|---|---|---|
| 53 | `config.py:2296` `ENABLE_SERVICE_ROADS` → `pavement/service_roads.py:400` `build_service_road_network` | the OSM off-pavement mint + DEM seed | `pipeline.py:2787, 3984-4023` | **REWIRE-to-contact-model** — general roads leave; contact stubs stay |
| 54 | `config.py:4466` `SERVICE_ROAD_CARVE` | the apt.dat-1206 on-pavement carve (`SVC*` refs) | `pipeline.py:2787, 3337, 4615, 5776` | **KEEP** (airside-contact by construction) |
| 55 | `pipeline.py:4615-4652` | road-plaza re-role `junction/apron → service_junction` | phase 1 | **spec-must-rule** |
| 56 | `anchors.py:5173` `apply_service_road_dem_follow` | in-solve DEM-follow envelope + apron anchors | `solve.py:4639` (stage `svc_dem_follow`, `solve.py:972`), `constructive.py:879` | **spec-must-rule** — this is the core's job now |
| 57 | `anchors.py:3330` `apply_groundside_reach` (writes `:3634, 3654, 3747, 3804` via `chord_limit_ring_altitudes`) | reach-band chord limit on groundside+road rings | in-solve | **spec-must-rule** |
| 58 | `anchors.py:~5700-5733` free-end DEM tie | `layout._svc_free_end_records` / `_svc_free_end_idx`; `solve.py:5289` folds them into `yield_hard` | in-solve | **spec-must-rule** |
| 59 | `groundside.py:3331` `apply_lateral_contiguity_law` (writes `:3634`; stamps `station_cap_vector` `:3488`) | absorbs a road into a stricter neighbour; publishes the cap vector | post-solve | **KEEP the vector, spec-must-rule the absorption** |
| 60 | `groundside.py:1756` `seat_service_pavement_on_law` (writes `:1915`) | re-seats road shapes the solve never reached | `pipeline.py:6805` | **spec-must-rule** |
| 61 | `groundside.py:3122` `adopt_road_airside_crossing_values` (writes `:3278`) | road takes the airside value at a crossing; **road-family vertices only** | `pipeline.py:6823` | **KEEP — this is 31b's (a)** |
| 62 | `free_road_profile.py` (pre-solve) | see §1 | `pipeline.py:6839` | **RETIRE** |
| 63 | `groundside.py:1483` `seat_groundside_on_law` (writes `:1627`) | lot seat, ordered after the road seat | `pipeline.py:6842` | **spec-must-rule** |
| 64 | `groundside.py:5414` `_grade_limit_groundside_chords` (writes `:5763`), kernel `_chord_cut_and_fill` `:4945` | two-sided Lipschitz clamp over the **unified road+lot node book**; `weld_outranks_cap=True` only at `pipeline.py:7147` (the item-4 up-build, RULINGS 30b) | `finalize.py:452`, `pipeline.py:6857`, `pipeline.py:7147` (executed at `:7184`) | **spec-must-rule** — the LAST road-family altitude writer of the build |
| 65 | `groundside.py:744` `apply_below_grade_transition` (writes `:777`) | grades neighbours toward below-grade surfaces | post-solve | **REWIRE** (see #35) |
| 66 | `groundside.py:2179` `_regrade_merged_host` (writes `:2247`) | regrades a lot that absorbed a road | post-solve | **spec-must-rule** |
| 67 | `groundside.py:4665` `conform_service_mouths_to_groundside` (writes `:4748`) | mouth conform | post-solve | **spec-must-rule** |
| 68 | `groundside.py:4565` `reclassify_groundside_route_corridors` (clears alts `:4652`; `O4_GROUNDSIDE_ROUTE_CORRIDOR`) | re-roles groundside back to road on a service route | post-solve | **spec-must-rule** |
| 69 | `groundside.py:6518` `_reclassify_groundside_orphan_junctions` (writes `:6721`) | orphan re-role | post-solve | **spec-must-rule** |
| 70 | `groundside.py:6841` `_cut_back_road_frontage` (writes `:6926`) | `O4_ROAD_FRONTAGE_CUTBACK`, **default OFF** (`pipeline.py:5274`) | — | **RETIRE candidate** — *see the CONFLICT note in the supplement; this gating reading is disputed* |
| 71 | `groundside.py:7312` `_clip_shape_yielding_to` (writes `:7396, 7407`) | clip rebuild; carries the claimed profile | post-solve | **REWIRE** |
| 72 | `free_road_profile.py` (re-solve) | see §1 | `pipeline.py:7180` | **RETIRE** |
| 73 | `crown.py:93` `_SERVICE_FAMILY`, drop field `:616, 645`, spines `:1797-1800` | lateral crown on service roads — **`CROWN_SERVICE` defaults `"0"`** (`config.py:868`) | in-solve writeback | **KEEP OFF** — arming it would contradict 31b's "no side-to-side banking" |
| 74 | `junction_repair.py:1803` `sloping_roles = {"service_road"}`, `:2374, 2383, 2456, 2587-2626` | orphan-junction repair keyed on the late `junction → service_road` re-role | post-solve | **spec-must-rule** |
| 75 | `bridges.py:12929` `emit_bridge_ramp_shapes`, `:12713` `insert_bridge_deck_end_pins`, `:13084` `insert_bridge_profile_pins`, `:12427` `bridge_pin_roles` (road roles included), `:15398` `_emit_underpass_road_approaches`, `:15927` `_emit_through_airport_depressed_roads` | bridge/underpass road geometry + pins | `build_bridge_layout_shapes:13374` | **KEEP — 31b's (b)** |
| 76 | `bridges.py:10829` `pavement_cut_roles` / `:10848` `cut_pavement_over_footprint` / `:6464` `_tunnel_ramp_cut_roles` | road roles are **cuttable** (R14-2/A-3 protects only the taxiway family) | `:6625, 14579`; `object_terrain_assembly.py:3211, 3790, 4259` | **spec-must-rule** — fewer road shapes ⇒ less to cut, and the cut lands on raw terrain instead |
| 77 | `ols.py:1674` `_emit_road_regrades` (`REF_ROAD = "ols_road"`, `:1538`) | emits its **own** road deck/band geometry from the feed at `SERVICE_ROAD_MAX_GRADE` (`:1752`); strip stand-down `:1629` | `pipeline.py:7369` `emit_ols_cuts` | **spec-must-rule** — a second road-owning pass in auto_patch, not named in 31b |
| 78 | `layout.py:1207` `to_osm` authority resolution | final per-node value by `authority_rank` | emit | **KEEP** — *see supplement: the resolution proper is `layout.py:2563`* |
| 79 | `emit_decimate.py:199` `MAX_CHORD_M = 60.0`, role set `:205` | decimation of road rings at 60 m | emit | **spec-must-rule** vs the core's `refine=100` (see #112) |
| 80 | `adjacent_ground.py:458-462` `_WALL_SCOPE_PAVEMENT_ROLES`, `:473` `service_corridor_wall_keepout` (courses `:486`, emitted-rect axes `:500-508`), `:3978, 4000` retreat role sets, `:8369-8377` `_svc_polys` wall clip | the band/wall machinery reads road pavement as scope, keep-out and clip | post-solve | **spec-must-rule** — each shrinks; walls can re-enter former road footprints |
| 81 | `clearance.py:109-110` `_SKIRT_CONSTRAINT_ROLES` | a runway end constrained by a `service_road` shape | skirts | **PARTIAL** — fewer constraints |
| 82 | Role-membership lists that silently shrink | `verification.py:45, 1269, 3606, 3725`; `geom_guard.py:620`; `conformance.py:1618-1619`; `seam_anchors.py:378`; `strip_seam_law.py:167`; `tile_cut.py`; `boundary.py` | **PARTIAL** — no crash, populations drop | — |

### 4b. Systems that assume auto_patch emits road pavement AWAY from airside

**Road-feed ingestion** (input; survives): `osm_load.py:1435` `_load_airport_road_network`
(box `:1074`, `AIRPORT_ROAD_FEED_PAD_M` 500 m), published `layout.py:965/971`, called
`pipeline.py:2003` under `if AIRPORT_ROAD_FEED:` (`:1997`). Consumers:
`clearance.py:1179` `airport_road_feed_corridors`; `pavement_classification.py:522
_road_corridor_index` / `:577 _road_feed_lines`; `bridges.py:337, 1009`;
`road_bridge_deck.py:217`; `terminals.py:222`; `pipeline.py:3566`
(`O4_SLICE_ROAD_FEED_SERVICE`); `pipeline.py:4005` → `pavement/service_roads.py:963`
`attach_course_widths` (**road-minting input only — dies with general roads**).

| # | consumer (file:line) | reads/assumes | interaction |
|---|---|---|---|
| 83 | `check_grade.py:1825` (`_ROAD_XSECTION_LAW and law_role(w) in _ROAD_FAMILY_ROLES`), pair route `_xsec:1830`, carrier `ShapePairConstraint.transverse_road:1394` | family **`road_cross_section`** (`:6158`) | **ZERO ROWS** — defined only over road-family rings |
| 84 | `check_grade.py:4011` (`if w.role not in ROAD_ROLES: continue`), roles imported `:3955` | family **`lateral_contiguity`** (`:6190`) | **ZERO ROWS** |
| 85 | `check_grade.py:4247` `_TRANSVERSE_ROLES` (built `:3898-3902` from `TAXI_AXIS_PRICED_ROLES ∪ SERVICE_AXIS_PRICED_ROLES`) | family **`transverse`** (`:6171`) | **PARTIAL** — loses the service half |
| 86 | `check_grade.py:5366` `_check_within_shape`; road-frontage cap relaxation `road_zone` at `:1714` | family **`within_shape`** | **PARTIAL, and may go UP** — road rows leave, but the frontage relaxation at `:1714` also becomes a no-op, re-tightening formerly relaxed apron/junction frontage edges |
| 87 | `check_grade.py:1341-1345` `_airside_groundside_pair` | the exactly-one-is-road ⇒ designed-wall **exemption** used by `vertex_to_edge_step` (`:5768`) and `mid_edge_step` (`:5870`) | **PARTIAL, sign unknown** — removes road-hosted pairs *and* removes the exemption at retained transitions |
| 88 | `check_grade.py:6318` `RETIRED_LAWS` `drainage_minimum::groundside` roles include both road roles | already zero by ruling 2026-08-14 | evidence — do not read a new zero as a regression |
| 89 | `tools/harness/census.py` | **no road-specific selection**; iterates `check_grade.LAW_FAMILIES`, forbidden from enumerating families (pinned `tests/test_harness.py:608`) | **KEEP** |
| 90 | `tests/test_harness.py:806-829` `_MIGRATION_TARGET_ROLES = {"service_road","service_junction"}` | the groundside→road role-migration guard (the OTHH −639 census-blindness verdict) | **spec-must-rule** — it catches population moving **into** road roles; a redesign moving it **out** is the mirror case and is uncovered |
| 91 | **`check_grade` reads only `PATCH.osm`** (`tools/check_grade.py:7943`); `include_roads` writes into the `Vector_Map`/mesh, never a patch | **Core-owned roads are invisible to the census and to every law family.** | **spec-must-rule — this is the biggest single consequence.** The only instrument that could read them is `tools/road_terrain_conformance.py`, which itself selects `check_grade._ROAD_FAMILY_ROLES` off the emitted patch — so it goes blind too. *(Baseline note: at `791ca959` this row also said the instrument was unmerged; it is on main as of `33cc55ca` — see the corrections above. The blindness half is unaffected.)* |
| 92 | `tools/corridor_axis_coverage.py:261, 277, 290` | every road-family node + `free_end_offsets` | **produces nothing** without road-family ways |
| 93 | `tools/arm_site_read.py:95, 240, 253, 213, 722` | the seam-weld table (road↔airside shared node refs per mouth) | **vacuous** without road ways |
| 94 | `tools/role_overlap_read.py:28-29, 54, 69` | canonical invocation is `service_road`/`service_junction` overlap | **PARTIAL** |
| 95 | `tools/spine_coverage.py:57`; `tools/trace_building_frontage.py`; `tools/crossing_zone_conformance.py:47-118`; `tools/census_matrix.py`; `tools/osm_site.py:140` | taxi-only / feed-only / artifact-only | **KEEP** (census_matrix cells for road-only families report a structural zero, not a win) |
| 96 | `groundside.py:4334` `sever_lot_carried_service_roads` (feed at `:4366`) | severs a road corridor **out of** a lot at 11-dp identity — its whole product is non-airside road pavement (RULINGS 30b) | **spec-must-rule — RETIRE or reroute its product to `groundside_pavement`** |
| 97 | `pavement_scoring.py:1194-1263` `road_zone` sever | cuts road corridors out of an outvoted apron using feed corridors | **spec-must-rule** — the cut geometry needs a new owner |
| 98 | `config.py:4661` `ROAD_ONLY_LOT_GROUNDSIDE` (radius `:4668` 7.5 m) | morphological opening of a **road-only component**: core ⇒ lot, narrow strips **stay `service_road`** | **spec-must-rule** — no road-only components ⇒ rule has no domain |
| 99 | `layout.py:1009` `absorbed_road_context` / `:4269` `_absorbed_merged_index` (`O4_SERVICE_LOT_ABSORPTION`) | registry of roads absorbed into a lot; grants the merged-surface exemption | **spec-must-rule** — empty registry ⇒ no exemption |
| 100 | `lateral_contiguity.py:424` (`own_role in ROAD_ROLES and _edge_conformance_on()`), `:176` `station_cap_vector`, `:157-170` `O4_ROAD_CONTACT_CAP_SCOPE`, `:117` `O4_ROAD_AIRSIDE_CONTACT_WIDEN` | the per-station cap vector is derived **for road ways**; three readers depend on it | **spec-must-rule** |
| 101 | `groundside.py:4085` `O4_FULL_WIDTH_SERVICE_CORRIDOR`; `:4589` `O4_GROUNDSIDE_ROUTE_CORRIDOR` | merge shattered pieces into a full-width corridor / re-role groundside back to road so road-weld cliffs don't reopen | **spec-must-rule** — both exist to stop groundside owning road courses |
| 102 | `gap_fill.py:3228` (`STAGE_A` for `{service_road, building}`), hole vetoes `:3857, 3867`; `_TUNNEL_BLOCKER_ROLES/_REFS` `:166-171` | a single `service_junction` can veto a gap-fill hole (3.40 km² HECA infield); groundside is also a blocker (RULINGS 30b) | **PARTIAL, likely a WIN** — needs a build |

---

# 5. The core side — `include_roads` and where the 8 % clamp sits

| # | interaction point (file:line) | reads/writes what | interaction | evidence |
|---|---|---|---|---|
| 103 | `src/O4_Vector_Map.py:996-1007` | `include_airports` → `(apt_array, apt_area, patches_area, graded_area)`, then `include_roads(vector_map, tile, apt_array, apt_area)` | **KEEP order** — auto_patch runs first, the core's roads see its output | — |
| 104 | `O4_Vector_Map.py:1518` | `road_network_banked.difference(improved_buffer(apt_area, tile.lane_width + 2, 0, 0))` — **the apt_area subtraction** | **spec-must-rule (LOAD-BEARING).** `apt_area = unary_union(patches_area, runway_taxiway_apron_area)` (`:1392`) and `patches_area` is the union of **every** patch way regardless of role (`:2305-2313`). Shrinking auto_patch road ownership **shrinks `apt_area`**, so core roads automatically reach into ground auto_patch used to pave — the mechanism the shrink depends on, and also its main hazard | `:1494` "the existing `apt_area` subtraction below still keeps them out … auto_patch owns that ground" |
| 105 | `O4_Vector_Map.py:1404-1422` `road_is_too_much_banked` | returns `True` (⇒ level it) if **either endpoint** falls in `apt_array`; returns `False` early once `filtered_segs >= tile.max_levelled_segs`; else `|alt_vec(way) − alt_vec(shift_way(way, lane_width))| >= road_banking_limit` | **KEEP** — airport-touching roads are already always levelled | — |
| 106 | `O4_Vector_Map.py:1434` `tags_for_exclusion = {"bridge","tunnel"}` | `OSM_to_MultiLineString` (`O4_OSM_Utils.py:1231-1239`) drops a way if its tag **keys** intersect the set | **spec-must-rule (LATENT BUG).** It is a **key-presence** test: `bridge=no` is excluded too. The core levels **nothing** on bridge/tunnel ways — precisely the seam where auto_patch keeps ownership (b) and (c), so the two must be made to agree explicitly | — |
| 107 | `O4_Vector_Map.py:1428, 648, 634` `resolved_road_level` / `small_roads_queries` | `road_level` default `"auto"` = level 1 tile-wide + level 5 inside airport insets | **KEEP** | `O4_Cfg_Vars.py:331-345` |
| 108 | `O4_Vector_Map.py:680` `_airport_auto_roads_layer` | level-5 + `AUTO_AIRPORT_RAIL_QUERIES` fetched per inset bbox, merged into one `airport_small_roads` cache | **KEEP** — this is what makes the core able to take general airport roads at all | `:1497` |
| 109 | `O4_Cfg_Vars.py:346` `road_banking_limit` (0.5 m), `:351` `lane_width` (4.0), `:356` `max_levelled_segs` (200000) | thresholds | **spec-must-rule** — `road_banking_limit` is a **lateral metres** test, not a grade; there is **no longitudinal grade constant anywhere in the core** | grep: `SERVICE_ROAD_MAX_GRADE` has **zero** readers outside `src/auto_patch/` |
| 110 | `O4_Vector_Map.py:1425-1427` **`alt_vec_shift(way)`** → `return tile.dem.alt_vec(VECT.shift_way(way, tile.lane_width))` | **THE ALTITUDE VECTOR.** Passed as `pol_to_alt` to `encode_MultiPolygon` at `:1530` with `refine=100`; `O4_Vector_Utils.py:515-527` calls `refine_way(way, 100)` then `alti_way = pol_to_alt(way).reshape((len(way),1))` and `insert_way(hstack([way, alti_way]), "INTERP_ALT")` | **THE NATURAL CLAMP SITE — `alt_vec_shift` is the function, and the numpy array it returns is the vector.** Its lateral shift by `lane_width` is already the "no side-to-side banking" mechanism 31b names | — |
| 111 | **Decisive caveat on the clamp site** — `O4_Vector_Utils.py:1083-1123` `improved_buffer` buffers the **whole `MultiLineString` at once** | the polygon handed to `pol_to_alt` is a **merged** ring spanning many roads and junctions, traversing out-and-back along each carriageway | **spec-must-rule.** A longitudinal clamp applied naively inside `alt_vec_shift` operates on **ring order**, not centerline station — it would wrap at ring ends and fuse unrelated roads. The alternatives: (i) clamp per-way on `road_network_banked` (a `MultiLineString` of centerlines, `:1449-1514`) and transfer to the ring by nearest-centerline lookup; (ii) buffer per-way instead of once. Both are spec decisions | — |
| 112 | `O4_Vector_Map.py:1530` `refine=100` vs `emit_decimate.MAX_CHORD_M = 60.0` | the core samples road altitudes every ≤100 m; auto_patch decimates its own rings at 60 m | **spec-must-rule** — an 8 % clamp at 100 m granularity cannot resolve a step auto_patch keeps at 60 m | — |
| 113 | `O4_Vector_Map.py:1530` `"INTERP_ALT"` marker; seeds `:2662`, sub-cell seeding `:2152-2203`, seal audit `:2236-2287`; mesher `O4_Mesh_Utils.py:696` (`attr >= INTERP_ALT` ⇒ harmonic extension from authored vertices) | the ring altitudes ARE the authored values; interior interpolates | **KEEP** — confirms the clamp on the ring vector is the right lever | — |
| 114 | `O4_Vector_Map.py:1534-1544` | the `road_network_flat` linestring branch is `if False and …` — **dead** | evidence row | — |
| 115 | `O4_Vector_Map.py:21` `from auto_patch import driver as AUTOPATCH` | the core **already imports auto_patch** | **spec-must-rule (in the spec's favour)** — importing `auto_patch.config.SERVICE_ROAD_MAX_GRADE` into `include_roads` adds no new dependency direction, so the 8 % number stays ONE constant rather than a second copy | — |
| 116 | `O4_Cfg_Vars.py:750-753` `list_vector_vars` | a new `road_grade_limit` key would sit beside `road_banking_limit` | **spec-must-rule** — served live by `o4_engine/session.py:1267`; `Sources/SceneryKit/Resources/o4_schema_snapshot.json:96-99` is a bundled **fallback** (`OrthoConfig.swift:231`), regeneration cosmetic |
| 117 | `O4_Vector_Map.py:120-146` `SEAWALL_PAVEMENT_ROLES` / `GRADED_COVERAGE_ROLES` | `service_junction` **is** in the seawall admission union; `service_road` is deliberately excluded | **spec-must-rule (cross-language)** — dropping `service_junction` pavement changes `graded_area` → `seawall_admission_area` (`:187`) and `airport_island_land` (`:347`) at coastal airports; twinned by `tests/test_r17_seawall_admission.py:46-64, 201-202` |
| 118 | `O4_Vector_Map.py:600-613` `sea_seed_areas` + `PATCH_RING_MARKER` (`:93`) | "pavement in our patch is LAND, so no SEA seed" — cutter is `patches_area` | **spec-must-rule (cross-language)** — less patch pavement ⇒ sea seeds can reach ground road pavement used to declare LAND |

---

# Tests that pin current behaviour (retire or rewrite)

**`free_road_profile`:** `tests/test_free_road_profile.py` (743 lines, **44 tests**
— the whole file; `:331` asserts `FREE_ROAD_PROFILE_PASS is True` by default,
`:222/:502` assert on `inspect.getsource`, `:517` the self-pins off-arm);
`tests/test_road_path_metric.py:229-331` (7 tests: source assertions on
`solve_free_road_profiles`, `"cap_at"`, cap-distance vector-vs-scalar);
`tests/test_weld_outranks_cap_chord_limiter.py` (191 lines, 7 tests — RULING 1 in
the limiter); `tests/test_road_cross_section.py:363-599` (`_chord_cut_and_fill`
twins); `tests/test_membership_round.py` (41 tests, heavy
`_grade_limit_groundside_chords` use).

**`tunnel_road` claim:** `tests/test_round14_tunnel_road_integration.py`
(**43 tests** — the R14-1 spec's own twin file, incl. `:212`
`TUNNEL_ROAD_REF in BELOW_GRADE_REFS`, `:551-571` `_build_tunnel_road_pins`);
`tests/test_portal_corridor_claim.py` (22);
`tests/test_claimed_corridor_survives.py` (13, `:231` counts
`claimed_tunnel_corridor(` call sites);
`tests/test_claimed_corridor_wall_survival.py` (6);
`tests/test_tunnel_corridor_exclusion.py` (12, `:346-356` the claim-set
publisher); `tests/test_tunnel_open_cut_publisher.py` (6 — **splits cleanly**:
`:49-79` region publisher KEEP, `:99-105` claim publisher RETIRE);
`tests/test_claim_edge_profile_seniority.py` (6);
`tests/test_r17b_below_grade_anchor_scope.py` (13, `:80-150` a `tunnel_road`
plate); `tests/test_r17c_flat_core_seed_refusal.py:171`;
`tests/test_seed_branch_attribution.py:38` (`claimed_tunnel_road_pin` in the
register); `tests/test_road_bridge_deck.py:667-688` (the 30i clip ref set — 2
tests); `tests/test_tunnel_portal_acceptance.py:250-395` (the instrument's claim
branch); `tests/test_osm_site.py:550-568`.

**KEEP unchanged** (feed, not claim): `test_pavement_scoring.py:1403-1445`
(G-TUNNEL-ROAD), `test_ols_road_regrade.py`, `test_road_lanes.py`,
`test_lemd_ramp_road_fidelity.py`, `test_road_bridge_deck.py:86-128`,
`test_portal_faces.py:348`, `test_round20_ramp_reach.py:313`,
`test_runway_end_skirt.py:711/775`, `test_tunnel_dem_cut_portals.py`,
`test_round10_tunnel_emission.py:207`.

**Also touched:** `test_corridor_axis_coverage.py` (63 tests, `svc_free_ends`),
`test_corridor_joins_round.py:313-403`, `tests/test_harness.py:642-657, 806-829,
1010-1011, 5706-5722, 5983-6047`, `tests/test_r17_seawall_admission.py`.

*(Added at `33cc55ca`: `tests/test_road_terrain_conformance.py`, 256 lines — the
merged instrument's twins. Not a pinned-behaviour risk; listed for completeness.)*

# RULINGS the retirements supersede (name these in the spec)

Engine `Ortho4XP/docs/RULINGS.md`: **1482-1521** (2026-08-11 KCLT round 14 —
R14-1 "THE PAVED AREA IS THE CORRIDOR", R14-2 "A CUT NEVER INTERRUPTS
AIRCRAFT-TRANSIT PAVEMENT", R14-3 "THE RAMP RUN IS DEPTH OVER GRADE");
**1752-1754** (2026-08-30 canonical tunnel mouth — already supersedes 25e for the
service-road family); **1788** (30f §3 third clause — the deck is not claimable
road pavement); **1796** (30i — `TUNNEL_ROAD_REF` joins the covered-stretch clip);
**1770** (30c §5 — "The deck's value is a PIN in the free-road profile solve" —
**this clause names the retiring pass and must be re-expressed**); **1758** (30b
item-4 up-build airside-frozen); **1748-1751** (28c items 2/3 — the sim defects
the claim class produced).

Repo-root `docs/RULINGS.md`: **:4** (29c contact-is-value — the senior law the
contact model inherits); **:6** (29a equilibrium shift); **:7** (28e free-road
class is 8 %); **:8** (28d service-bore depth 5.1 m); **:9** (25b road
edge-sharing an apron); **:12** (25e portal approach claims and lowers unclaimed
pavement — **the direct ancestor of R14-1's claim**); **:14** (25g roads are
laterally flat); **:15** (25h service roads in apron contact are spines).

# Env flags involved

**Retire with FRP:** `O4_FREE_ROAD_PROFILE` (`config.py:10202`),
`O4_FREE_ROAD_PROFILE_PRESOLVE` (`:10196`), `O4_FREE_ROAD_PROFILE_RESOLVE`
(`:10199`), `O4_FREE_ROAD_SELF_PINS` (`:10129`), `O4_FRP_DIAG`
(`free_road_profile.py:445`).

**Retire/rewire with the claim:** `O4_CLAIM_WALLS` (`bridges.py:8133`),
`O4_CLAIM_FOOTPRINT_SCOPE` (`:8262`), `O4_CLAIM_WALL_GATE` (`:6648`),
`O4_PORTAL_CORRIDOR_CLAIM` (`:8120`), `O4_CLAIM_EDGE_SENIORITY`
(`adjacent_ground.py:3387`), `O4_TUNNEL_CORRIDOR_NODE_BOOK_EXCLUSION`
(`groundside.py:5142`).

**Retire with Phase 0** (added at `33cc55ca`, TEMPORARY measurement switches,
all default-OFF): `O4_ARM_CHORD_RAISE_ONLY`, `O4_ARM_NO_CHORD_LIMITER`,
`O4_ARM_NO_WELD_UPBUILD`, `O4_ARM_NO_BAND_CUT_GS`.

**Keep (mouths/ramps/walls/feed):** `O4_RAMP_WALL_FOOT`, `O4_TUNNEL_DEM_CUT`,
`O4_TUNNEL_VETO_SCOPED`, `O4_IMPLIED_TUNNEL_CHAINS`, `O4_OBJ_TUNNEL_COMPOSE`,
`O4_DEMCUT_PROVENANCE_GATE`, `O4_COVERED_SPAN_MASK`, `O4_TUNNEL_GRAZE_CLIP`,
`O4_TUNNEL_LOW_CONNECTORS`, `O4_TUNNEL_TAXI_BREAKS`, `O4_TUNNEL_DEBUG`,
`O4_AIRPORT_ROAD_FEED(+_PAD_M/_CACHE)`, `O4_ROAD_WIDTH_FROM_FEED`.

**Spec-must-rule (road ownership):** `O4_ENABLE_SERVICE_ROADS`,
`O4_SERVICE_ROAD_CARVE`, `O4_ROAD_CONTACT_CAP_SCOPE`,
`O4_ROAD_AIRSIDE_CONTACT_WIDEN`, `O4_ROAD_AIRSIDE_CROSSING_CONFORM`,
`O4_ROAD_APRON_EDGE_CONFORM`, `O4_ROAD_CROSS_SECTION_LAW`,
`O4_ROAD_PATH_METRIC`, `O4_ROAD_LOT_GROUNDSIDE`, `O4_SERVICE_LOT_ABSORPTION`,
`O4_FULL_WIDTH_SERVICE_CORRIDOR`, `O4_GROUNDSIDE_ROUTE_CORRIDOR`,
`O4_SVC_REROLE_NARROW_ONLY`, `O4_ADOPT_FREEZE_AIRSIDE_ONLY`,
`O4_OLS_ROAD_REGRADE`, `O4_CROWN_SERVICE` (default `"0"` — keep off),
`O4_ROAD_FRONTAGE_CUTBACK` (default `"0"`), `O4_ROAD_EVIDENCE_SEVER` (refuted,
off).

# Not decidable by static reading — seam-probe these, don't guess

1. Whether `within_shape` counts go **up** when the `road_zone` frontage
   relaxation (`check_grade.py:1714`) becomes a no-op (direction knowable,
   magnitude not).
2. The net sign of removing `_airside_groundside_pair`'s road exemption
   (`check_grade.py:1341`) at the *retained* transitions.
3. Which of the ~20 altitude writers in §4a actually move a given road vertex,
   and in what order — `tools/harness/who_wrote.py --at X,Y` is the instrument;
   reading the code has a bad record here (its own header: "nine falsified
   mechanisms in two days from reading attribution as causal").
4. Whether the node-book exclusion re-keyed to `tunnel_open_cut_polys` covers the
   same rings the claim set covered — the two regions are measured different
   (`bridges.py:8842-8848`).
5. Whether `SERVICE_ROAD_PAVEMENT_NEAR_M = 25.0` (`config.py:1396`) already
   implements most of the shrink, and whether its residual is exactly the pinned-
   transition set.
6. Whether removing `gap_fill`'s `service_junction` hole veto (`:3857, 3867`) is a
   win — needs a build.

# Two blocking facts the spec should absorb

- **`tools/road_terrain_conformance.py`** — *superseded in part: the instrument
  is on main as of `33cc55ca` (`tools/INDEX.md:93`). What stands: it reads
  `check_grade._ROAD_FAMILY_ROLES` off the **emitted patch**, so it is blind to
  core-owned roads exactly as the census families are.*
- **Handing general roads to the core makes them unmeasurable by the current
  instrument set.** `check_grade`/`census` read `PATCH.osm` only; `include_roads`
  writes `INTERP_ALT` edges into the `Vector_Map`. The spec needs to name the
  replacement reading (mesh-side sampling, e.g. `tools/mesh_elevation_sampler.py`,
  or an extension of the conformance instrument to the levelled road network)
  before the shrink lands, or the redesign ships the same blindness the
  post-mortem attributes the regression to.

---

## §4a SUPPLEMENT (replaces rows 53-82's completeness claim)

The parallel recon pass on §4a returned after I delivered. It materially expands the road-altitude-writer list — here is the supplement, which **replaces §4a** (my rows 53-82) rather than adding to it.

## Correction to §4a row 53 (the mint)

`pipeline.py:4101-4112` mints `service_road`/`service_junction` from `pavement/service_roads.py:400` with **no altitude of any kind** — `altitude`, `altitude_high`, `node_altitudes` are all `None`. There is no DEM seed at the mint. The seed happens later, in the solver (`solver_primitives.py:3418 _seed_elevations`, called from `solve.py:2056` inside `solve_route_profile` and again at `solve.py:7836` inside `final_grade_projection`). This matters for the redesign: the road family has **no pre-solve value authority at all**, so "shrink the ownership" is a question about the solve and the post-solve passes, not about the mint.

## Additional road-altitude writers (not in my table)

**Pre-solve, geometry-driven:** `groundside.py:4478-4484` `sever_lot_carried_service_roads` (a **second road mint**, DEM-followed + ramp-limited, `ref="lot_carried_road"`, pipeline.py:5196); `groundside.py:4652` and `pavement_classification.py:1066-1068` (both **clear** `node_altitudes` on a re-role to a road role); `seam_anchors.py:173/178` and `:551` (seam DEM anchors, role-agnostic); `pipeline.py:617` `_dedup_coincident_ring_vertices` (5795 and 6653); `flatedge_snap.py:206` (rewrites *neighbour* rings against a `service_road` rect's flat edge — `service_road` is the excluded set, `service_junction` is written); `fabric_sparse.py:593` (`service_junction`, pipeline.py:6189); `canonical_points.weld_layout_vertices` (pipeline.py:268-272, coordinate weld — the precondition for every adoption).

**Tile cut — a whole family I missed:** `tile_cut.py:1324/1335/1355` `_build_piece_shape` (every cut piece of a road shape gets resampled altitudes; seven call sites, 4789 through 7444); `tile_cut.py:1198` `_terrain_pin_slice_nodes` — **`service_road` is in `_PIN_SLICE_ROLES`, `service_junction` is not**, so road slice-edge vertices are DEM-pinned; `tile_cut.py:612` `_absorb_one_sliver`.

**Conformance — role-agnostic writers on road rings:** `conformance.py:1245` `enforce_conformance` (T-vertex inserts, six call sites incl. 6600/6753 and inside `planarize_airside`); `:1592` `_resolve_edge_crossings`; `:1711` `_resolve_yielding_tjunctions` with tier gate `_OVERLAP_TIER` at `:1618-1619` (`service_road`:2, `service_junction`:3 — a junction yields to a road); `:1354/1358` `repair_emit_quantized_rings`.

**In-solve:** `crown.py:517` `build_crown_drop_field` (road family via `_SERVICE_FAMILY`, `CROWN_SERVICE`-gated, `solve.py:6054`) — it moves the emitted value through the `z′` writeback; `anchors.py:3864/3901/3924` inside `apply_groundside_reach` — **`elev[i] = a; hard.add(i)`, the road node HARD-PINNED to the groundside lot's re-levelled value**, publishing `layout._groundside_weld_keys` (this is a road-value authority I had recorded only as a lot writer); `anchors.py:5485/5698/5852/5893/6073` are the actual write sites inside `apply_service_road_dem_follow`; `crown.py:1676` `_weld_terminus_into_rings` (`solve.py:6617`); `solve.py:735` `_apply_runway_flex_hook` (flexed runway profile stamped onto every coincident road vertex).

**THE WRITEBACK:** `solver_primitives.py:4932-4957` `_writeback` — `service_road`, `service_junction` and `junction` share one branch; `s.node_altitudes = [round(e,2) …]`, `altitude*` cleared. Called at `solve.py:6180` (end of `solve_route_profile`) and `solve.py:9859/9863` (end of `final_grade_projection`). Band clamp first at `solver_primitives.py:4863`, applied to every role **except** `ROLE_RUNWAY` — so road corner values *are* clamped to the band of record at both writebacks. This is where solver `elev` becomes road `node_altitudes`, and it is the single point the redesign has to re-scope.

**Post-projection:** `anchors.py:5167` `reseat_service_mouths` at `solve.py:8183` **inside `final_grade_projection`** — re-derives each held mouth seat from the airside edge's *current* value; the last airside-final moment, and the natural home for 31b's pinned-transition law.

**Late / emit:** `emit_decimate.py:175` `repair_sliver_corners` and `:733` `decimate_emit_nodes` — **`service_junction` only**, `service_road` absent from `_AIRSIDE_ROLES`; `adjacent_ground.py:3232` `_retreat_run_walls` (pipeline.py:7752) — road roles **are** in scope: a road loses to runway/taxi/apron/building and wins over `groundside_pavement`, retreating `STACKED_WALL_RETREAT_M` into its own interior with a `retaining_wall` face shipping the difference; `layout.py:2563-2564 → 2581-2582 → 3629-3645` `to_osm` — the authority resolution proper (my §2 row 41 cited `:1207`, which is `_record_authorship`; the `min(_claims, key=…)` resolution is at `:2563` and lands as `alt_abs` at `:3644`).

**Tunnel/bridge writes on road roles:** `bridges.py:7819` (levelled arm — road ring **lowered** to the joint clearance floor), `:8008` (P2 profile arm), `:7951` (host remainder), `:8613` (`_claim_portal_corridor_footprint` host remainder); `bridges.py:10896-10935` `cut_pavement_over_footprint`; `bridges.py:6973/6982, 7241/7257, 7327` the tunnel-ramp clearance-annulus cut — **road roles survive `_tunnel_ramp_cut_roles()` and are cut and resampled**; `junction_repair.py:2476/2534` writes altitudes on a shape that then leaves the road family.

## Band machinery — prices vs. writes (settles my §4a row 80 and §1 row 19)

**Prices only, never writes a road altitude:** `grade_graph.py` (**zero** `node_altitudes` assignments in the file); `law_band.py` (no road reference at all); `lateral_spine_nodes.py` (**zero** assignments — inserts geometry pre-solve, the solve values it); `taut_string.py`; the `adjacent_ground` band emitter (`:6233/:6740/:6823`) mints `graded_strip`/`adjacent_ground` shapes and never assigns to a road shape. `solver_primitives.py:4602 seal_pavement_to_band` **explicitly excludes the road family** (`O4_SEAL_AIRSIDE_ONLY`, default ON, docstring `:4626-4630`). The band's only road write is the `:4863` clamp inside `_writeback`.

**Confirmed non-writers** (worth recording so their silence isn't re-investigated): `gap_fill.py` (zero assignments — road roles are detection/blocker sets only), `boundary.py` (roads are *givers* at `_yield_seam_altitude`; takers are `ROLE_BOUNDARY`), `clearance.py`, `verification.py` (zero assignments), `apron_terrace.py`, `junction_rules.stitch_pavement_polygons`, `junction_repair.source_clip_partial_coverage_shapes`, `crown.insert_runway_crossedge_crown_nodes`, `tile_cut.repin_airside_seam_cutbacks`, and the three bridge-pin passes (`insert_bridge_profile_pins`, `_emit_deck_lip_weld_strips`, `insert_bridge_deck_end_pins` — `_BRIDGE_PIN_ROLES` excludes both service roles). `conformance.py:800 apply_conforming_mints` has **no caller in the main tree** — dormant code.

## One conflict the spec must resolve, and seven undecidables

**Conflict:** I recorded `_cut_back_road_frontage` (`groundside.py:6926`) as gated off (`O4_ROAD_FRONTAGE_CUTBACK`, `pipeline.py:5274`); the recon pass places it live via `groundside.py:7184` → `finalize.py:415` and `pipeline.py:6779`. Two different gates may be in play. **Seam-probe it** — do not assume either reading.

**Not decidable statically** (add to my earlier list; each needs `who_wrote.py` or a source read the spec author does deliberately): (1) whether `geom_guard.py:713 insert_probe_nodes` has any non-debug call path; (2) whether `tile_cut.py:898 _pin_terrain_piece_seam_edge` has a caller outside `tile_cut.py`; (3) the role gates of `junction_repair.py:1142/1164` and `:1759`; (4) the enclosing pass and call site of `bridges.py:5401/5516/5528` — the filter seen is `ref not in _WALL_BAND_REFS`, i.e. role-agnostic, so road shapes plausibly reach it; (5) whether `pavement/vertices.py` (`:676/714/934/953/981/1102/1766`) runs after the mint at `pipeline.py:4101` and can therefore see a road-role shape; (6) the role gate of `solve.py:6595`; (7) the runtime state of `CROWN_SERVICE`, `SVC_SPINE_FIRST`, `TILE_SEAM_TERRAIN_DEM_PIN_ENABLED`, `_WELD_OR_GAP`, `TUNNEL_PORTAL_AIRSIDE_RAISE`, `O4_SEAL_AIRSIDE_ONLY` in a production build.

**Headline for the spec:** the road family has roughly **forty** altitude writers across nineteen modules, and the two solver writebacks (`solver_primitives.py:4932`) plus `to_osm`'s precedence resolution (`layout.py:2563`) are the only two points where all of them converge. Retiring `free_road_profile` removes two of the forty; handing general roads to the core removes the *population* they act on, which is why every "PARTIAL" row in §4b is a population change rather than a code change — and why a single seam-probe build at one airport is worth more than further static reading here.
