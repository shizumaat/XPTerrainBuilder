# Deferred-verification ledger (pre-ship mode)

One line per streamlined land: the change, and the verification that
was SKIPPED under the 2026-08-09 "Pre-ship development mode" ruling
(docs/RULINGS.md). The ship gate pays this whole file in one
hardening round before the first official release: full suite,
battery A/B + censuses, timing profile, absolute-zero acceptance.
A change the sim verdict kills may strike its lines instead.

- 2026-08-09 lane/padrings (footprint-hugging pad rings, spec §2.5): skipped blast-radius suites, OTHH acceptance build, full offline-replay report.
- 2026-08-09 lane/basinseat (basin §2.2 rim-flush reseat): skipped blast-radius suites, clearance/threshold regression test completeness, all builds; in-sim only.
- 2026-08-09 integration of the four-lane round: battery airports never rebuilt under the merged tree (HEAZ byte-check + OTHH only); KCLT/KBNA/HECA/SPJC/SPLP/CYXY patches unverified post-merge; objpads real-DEM convergence loop unverified end-to-end.
- 2026-08-09 lane/flatdet (FLAT-SITE detector, report-only): ran only tests/test_flat_site_detector.py + test_harness.py -k sidecar; ZERO builds, so the pipeline call site is proven only by an in-process detect_for_layout + to_osm round trip, never by a real build's log/sidecar; no blast-radius suites for config.py/layout.py/pipeline.py/check_grade.py; inertness (byte-identical patch geometry vs pre-change) asserted by construction and never measured; both sweep arms read a SINGLE raster (base .hgt, or the airport inset alone) — the real production surface is the inset FEATHERED into the base by tile DEM prep, which no arm reproduces; and the 1-arcsec relief floor's move to 8.0 m (lead ruling 2026-08-09) is evidenced by the two-arm sweep only, never by a built patch. The six owner-named flat test airports are swept from LANE-LOCAL rasters (N22E113, S34E151, N37W123, N42W072, owner-approved viewfinderpanoramas dem3 download 2026-08-09) that are NOT in the shared corpus — their rows are not reproducible by another lane until those tiles join through the recorded `--refresh-data` path, and no inset arm exists for any of them. S2a (sea band), S2b (DSM trim), the pavement-only gate extent and the owner-declaration keys are evidenced by the sweep and by synthetic twins only, never by a built patch; the two new `flat_site_declared*` tile-cfg keys are registered but have never been round-tripped through a real cfg file or the Qt settings UI; and no flat-site MODE consumes any of it yet, so `flat_declared` vs `flat_candidate` has never been exercised end to end.
- 2026-08-09 lane/flatmode CORRECTION ROUND (the substitution that did not substitute): the first OTHH acceptance build stamped a `flat_candidate` verdict and moved NOTHING, because DEM prep is entered from several call sites (`elevation._compute_elevations` composes before the per-surface solver does) and `elevation._DEM_CACHE` memoises whatever the FIRST caller produced — the X-Plane root was threaded through one call site only, so the first caller bailed with "no X-Plane root resolved" and froze the real surface. Fixed with a build-scoped root set at the `build_airport_pavement` entry, and the overlay lifted out of `bake_airport_insets_into_alt_dem` into `smooth_raster_over_airports` (DEM assembly, after the bake, before the `.alt` write). UNPAID: no other call site of `_load_airport_dem` was exercised (finalize / verification / the cross-tile cover read in `runway_segments`), and no test asserts the `_DEM_CACHE` interaction itself — the twins assert the root resolution and the no-bake path, not the memoisation order.
- 2026-08-09 lane/flatmode (FLAT-SITE mode phase 2, the DEM source substitution): ran only tests/test_flat_site_mode.py + the files covering the touched code (test_flat_site_detector, test_patch_provenance, test_airport_elevation_insets, test_inset_bake_and_seam, test_dem_baked_query, test_object_elevation_ordering), once; ONE OTHH patch build and no other airport, so the DEGENERACY claim (not_flat / lidar_credible / no_data / gate-off byte-identical) is proven by synthetic twins and NEVER by a built patch — HECA/KCLT/SPJC/SPLP/CYXY were not rebuilt under this tree and no patch-body sha was compared. Also unmeasured: the whole-tile path (only the standalone patch path was exercised, so the production `smooth_raster_over_airports` -> bake -> `.alt` write ordering is proven by code reading and unit twins alone); the mesh step-2 raster-refresh call site (`O4_Mesh_Utils`), which rebuilds the `.alt` with NO dico_airports and rebuilds the airport dictionary from the OSM cache — never exercised; the FEATHERED SHORELINE at OTHH (the synthetic rect covers up to FLAT_SITE_MARGIN_M of nearshore water and the DEM bake has no water machinery — sea triangles are levelled later by O4_Mesh_Utils' own sea/water pass, which this lane did not run); the build-time cost of classifying every S1-passing airport on a busy tile (OTHH's tile classifies 3, a KCLT-class tile could classify ~25 and each pays an apt.dat pick + load); and the pipeline's own report-only `site_class` sidecar record, which for a substituted airport is now measured on the SYNTHETIC surface (verdict unchanged, evidence numbers no longer the honest DEM's — the honest record lives in `dem_inset_provenance.synthetic_flat_site.record`).
- 2026-08-09 lane/flatdet (FLAT-SITE detector, report-only): ran only tests/test_flat_site_detector.py + test_harness.py -k sidecar; ZERO builds, so the pipeline call site is proven only by an in-process detect_for_layout + to_osm round trip, never by a real build's log/sidecar; no blast-radius suites for config.py/layout.py/pipeline.py/check_grade.py; inertness (byte-identical patch geometry vs pre-change) asserted by construction and never measured; both sweep arms read a SINGLE raster (base .hgt, or the airport inset alone) — the real production surface is the inset FEATHERED into the base by tile DEM prep, which no arm reproduces; and the 1-arcsec relief floor's move to 8.0 m (lead ruling 2026-08-09) is evidenced by the two-arm sweep only, never by a built patch. UNSWEPT: the six owner-named flat test airports (VHHH, VMMC, YSSY, KSFO, KOAK, KBOS) pass S1 but have NO S2 reading — their base rasters (N22E113, S34E151, N37W123, N42W072) are absent from the corpus and the download was not authorised in this session, so the owner's flat expectation for all six is unverified; `--elevation-dir` is in place and the sweep completes as soon as the rasters exist.
- 2026-08-10 lane/r4water (PATCH PAVEMENT IS LAND, spec docs/specs/patch-pavement-is-land-spec.md): ran only tests/test_patch_pavement_is_land.py + tests/test_tidal_water_inland_override.py (36 passed), once; ZERO builds, so BOTH halves are proven by twins alone. The ring-marker half is asserted against a Python twin of Triangle4XP's `regionplague` / `setelemattribute` (Triangle4XP.c:13545-13549, :1225) and never by a mesh Triangle4XP actually produced — no `.1.ele` was inspected, so "the interior keeps bit 8 alone" is a reading of the C, not a measurement. UNPAID: the in-sim VMMC verification (C1/G/H rendering as land at patch elevation while the channel stays sea) and a rebuilt +22+113 tile — the 263 SEA|INTERP_ALT triangles / 114,406 m2 figure is the PRE-change measurement and has no post-change counterpart. Also unmeasured: the 36,410 genuine WATER|INTERP_ALT bridge-road triangles are pinned only by the marker-8 twin (road ribbons and OBJ8 objects were never rebuilt); no other airport was rebuilt, so patch rings that legitimately enclose water elsewhere (a patched airport with a mapped pond inside its pavement union) have no before/after; the sea-seed subtraction is exercised on synthetic boxes only, never on a real coastline/patches_area pair; and no census/battery arm was run under this tree.
- 2026-08-10 lane/r4class (Round 4 Lane A — R3 classification hard gates, R4 implied-tunnel tag evidence, R6 gap_fill tunnel blockers): ran only the directly-covering files once (test_pavement_scoring, test_enclave_region, test_implied_tunnel_level_crossing, test_pavement_classification, test_classification_round, test_gap_fill_spine, test_object_tunnel_terrain, test_portal_faces — 256 passed); ZERO builds, so every claim is synthetic-twin evidence and NOT one measured OTHH shape: sid102/104/105/103 are reproduced as fixtures, never re-classified from the real layout, and the R4 chain walk has never seen a real merged three-namespace road network (the position-keyed junction join across big_roads / `S|` small_roads / `F|` feed ids is proven by construction only). UNPAID besides: the population effect of the two apron gates is unmeasured — no census, no battery A/B, so how many shapes at HECA/KCLT/SPJC/SPLP/CYXY change class is unknown and the absolute-zero acceptance gate was never run; `layer` is absent from the tile road caches' tag whitelist (`O4_Vector_Map.ROADS_TAGS_OF_INTEREST`), so R4's `layer < 0` half is live only on airport-road-feed ways and no arm measured what that costs; the G-TUNNEL-ROAD veto fraction reuses `PAVEMENT_SCORE_VETO_FRAC` (0.25) by argument, never by measurement; and R6's blocker DROPS a whole gap where the spec's prose says "a gap face is cut against them" — the region falls to the band / pocket-collar consumer exactly as any other foreign-shape veto does, which no build has confirmed is the wanted form.
- 2026-08-10 lane/r4pads (round-4 R1 pad plan-box fallback retired + sidecar v5, R2 objects claim their containing airport, R5 transition law beside below-grade geometry): ran only tests/test_round4_pads_claims_transition.py (new) plus the files directly covering the touched code (test_object_anchor, test_object_pads, test_post_mesh, test_object_cluster_seating, test_object_elevation_ordering, test_tunnel_portal_acceptance, test_groundside_law_authority), once; ZERO builds. UNPAID: (a) R1's collapse of the pad population is predicted, never measured — no OTHH rebake ran, so "44 % of the patch's ways today" is unverified after the change and no v4→v5 discard was observed on a real sidecar; (b) R2's per-(airport, pack) worklist has never been through a real two-airport tile — the OTBD/OTHH partition, the per-airport short-circuit records, `object_rebake.apply`'s reversion pass over DISJOINT subsets of one pack, and the double-run of the section-2.2 basin pass (once per claiming airport, idempotent by construction only) are all evidenced by synthetic twins alone; the driver's claim geometry is built from CIFP thresholds only (the apt.dat boundary slot is filled after the worklist is collected), so it is narrower than `object_pads._footprint_claim`'s pavement hull and the "unclaimed → nearest" branch carries more objects than it eventually should; (c) R5's transition law has never run inside a build — no wall band or groundside plate has been re-profiled by production code, its build-time cost (an STRtree query per candidate vertex) is unmeasured against the 60 s per-airport budget, and the interaction with the later adjacent-ground / decimation / weld passes that re-derive rings is unverified; and (d) R5's run is measured ALONG the transition surface's own ring, anchored at one portal per below-grade body (lead ruling 2026-08-10, replacing the horizontal-gap reading this lane first implemented): the crest stands at surrounding grade along the ramp and descends only within the cap-limited run of the portal — verified on synthetic twins only (a 600 m densified band: crest 4.00 at mid-ramp against a ramp at −0.01, converging to −3.99 against a −4.02 portal), never in the sim, and the along-ring relaxation's raised iteration budget (max(4000, 64n), 5–21 ms per governed ring in isolation) has never been timed inside a build.
- 2026-08-10 lane/r5tunnel (Round 5 — feature-A tunnel ADMISSION guards, spec docs/specs/round5-vhhh-tunnel-admission-spec.md): ran only tests/test_object_terrain_features.py + tests/test_object_basin_trench.py (the files covering the classifier and the interior-cutout path that shares `_below_grade_drivable_components`), once; ZERO builds, so guard 2's effect is evidenced by synthetic twins plus a READ-ONLY in-process census of the VHHH pack classification sidecar (`o4_object_terrain_classification_+22+113.cache`) — the six cached records were judged against the new predicates, never re-derived by a classifier run, so pooling/component formation under the guards has NOT been observed on real pack geometry. UNPAID besides: (a) the owner's in-sim VHHH pass after the +22+113 rebuild is the acceptance and has not happened — "flat island at Z0 except the five real tunnels" is a prediction; (b) the exclusion-set consequence is traced by code reading only (`exclusions` reaches the Phase 2 y-bake filter in post_mesh and the rebake cache's `excluded_digest`, and nothing else), so the claim that `tunnel/sea.obj` + `sea_X.obj` returning to the y-bake population is harmless — a 21.5 km² shell now offered to `discover_and_rebake_airport` — is UNMEASURED, and no rebake was run to see what the y-bake does with it; (c) the guard-2 refusal marks its component CONSUMED (following the refused-bridge precedent beside it), so the resources are withheld from the bridge and feature-C stages — never measured against a real pack, only asserted on twins; (d) no census, battery or build-time arm was run under this tree, so the population effect on HECA/KCLT/SPJC/SPLP/CYXY and the cost of the per-resource corner-max scan are both unknown; and (e) guard 1 (`TUNNEL_MIN_ABOVE_GRADE_TOP_M`) is landed in a SEPARATE commit and is BLOCKED pending Fable review — it refuses four pre-existing invariants (see that commit message), and no arm has established what threshold, if any, separates VHHH's sea bed from EGLL's below-grade AGL shells.
- 2026-08-10 lane/r6resid (Round 6 — OTHH residuals, spec docs/specs/round6-othh-residuals-spec.md: R6-1 pads never span water, R6-2 evidence must ride the same road, R6-3 flush-deck bridges seat at abutment grade): ran only the directly-covering files once (test_dsf_buildings, test_implied_tunnel_level_crossing, test_object_bridge_terrain, test_object_basin_trench, test_post_mesh, test_object_tunnel_terrain, test_object_rebake, test_object_anchor, test_object_terrain_features, test_terminal_groundside_zone, test_hangar_pads, test_object_bake_span_limit, test_object_cluster_seating, test_supporter_fate, test_supporter_smallest, test_airport_road_feed, test_round4_pads_claims_transition, test_contracts — 686 passed, 11 skipped); ZERO builds, so every number is synthetic-twin evidence. UNPAID, per law: (a) R6-1's regression pin ("pad area over water at OTHH -> ~0; building87 unchanged") was never measured — no OTHH build ran, and building1's 2,055 m2 over-water lobe has no post-change counterpart; the water/sea union was exercised against the REAL OTHH tile caches only by a read-only probe (a west-east transect at 25.2731 N: land from -4.0 to +1.0 km, sea from +1.5 km — the orientation convention is verified, the CLIP is not), and no other coastal airport was swept, so a false-positive clip elsewhere (a mis-oriented OSM coastline, a `natural=water` polygon over reclaimed land) is unbounded; the sea limb's locality (coastline clipped to the pad bbox + half the 2,000 m band) means a pad more than that far offshore from any mapped coastline is not clipped by the coastline limb at all, which no arm measured. (b) R6-2's census pin (OTHH's 8 self-evidenced bores survive, the 2 S1 bores refuse at hop 1) is asserted on synthetic scenes, never re-derived from the real merged three-namespace road network; the pre-existing R4 pin `test_chain_connected_mapped_tunnel_within_100m_qualifies` was REWRITTEN to join at an endpoint (its old scene hung the mapped tunnel off a MID-WAY node, which the new law refuses by design) — the S4 shape it modelled is now out of scope for a different reason (service is not in `_IMPLIED_HW_TYPES`), and that claim is read from the constant, not measured. (c) R6-3's seat has never run post-mesh on a real pack: the abutment-grade median, the mesh-at-anchor sample and the rigid whole-structure bake are proven on a synthetic two-level mesh (water 0.00 inside 50 m of the anchor, land 3.96 outside) and a synthetic 40x40 box, so "deck top ~= 3.65 m" is arithmetic, not a rendered deck; Bridge_02/03/06 staying draped is pinned by an all-land arm, never by the OTHH classification; the crossing-floor decline at bridges.py:9845 named in the spec's diagnosis was NOT touched, so whether the seat alone closes the in-sim symptom is unverified; and `_EXCLUSION_CACHE_VERSION` 4->5 plus `RUN_RECORD_VERSION` 7->8 discard warm caches by construction only — no warm-cache arm was run. (d) No census, battery, build-time or blast-radius arm under this tree; the build-time claim (R6-1 adds ~0.11 s cold for the water+coastline tile parse and ~0.002 s for the union/clip at OTHH, lru-cached after — 0.19 % of the 60 s per-airport budget) is a single read-only probe measurement, not a `check_build_time --runs N` reading.
- 2026-08-10 lane/r7seawall (Round 7 — SEAWALL at the pavement/water edge, spec docs/specs/round7-seawall-spec.md): ran only tests/test_seawall_breaklines.py (new) + tests/test_patch_pavement_is_land.py (the R6-1 regression pins), once — 53 passed; ZERO builds, so the whole law is synthetic-twin evidence. UNPAID: (a) the owner's in-sim VMMC pass after the next +22+113 rebuild IS the acceptance and has not happened — "vertical drop from taxiway deck to flat water" is a prediction, and no mesh Triangle4XP actually produced has been inspected, so the claim that the 0.5 m band between ring and wall comes out SEA (wet texture, mask, sea levelling) while the ring nodes are restored to deck altitude by the `interp_alt_tris` pass is a reading of O4_Mesh_Utils.post_process_nodes_altitudes and of Triangle4XP's regionplague, not a measurement; (b) the offset curve is exercised on synthetic boxes and a corridor twin only — never on a real `patches_area` union against a real coastline, so the buffer's mitre joins at VMMC's actual pavement corners, the node count the wall adds to the mesh, and any interaction with `insert_way(check=True)` encroachment splitting against real coastline/water rings are all unobserved; (c) the INLAND limb (include_water, at `tile.dem.alt_vec`) has never run at all — no airport patch bordering a lake, river or dock was built, and the sea-wins-on-overlap precedence is asserted by coordinate-keyed node identity in a unit test, never on real overlapping geometry; (d) the tidal-lagoon routing (the sea limb cuts against `seed_area`, so a lagoon whose seeds are withheld is walled by the inland limb at DEM level instead of at 0.0) is proven by code reading and by the R6-1 seed-subtraction twins alone; (e) no census, battery, blast-radius or build-time arm under this tree — the build-time claim (two shapely buffers + intersections on the pavement union per tile, bbox-rejected on dry tiles, plus the insertion of the offset breaklines; estimated well under the 0.6 s / 1 %-of-60 s trigger) is an estimate, NOT a `check_build_time --runs N` reading; and (f) the `O4_SEAWALL_OFFSET_M` override is registered nowhere in O4_Cfg_Vars — it is an env-only knob with no cfg round trip and no Qt settings exposure.
- 2026-08-10 lane/r8vhhh (Round 8 — VHHH close-out, spec docs/specs/round8-vhhh-closeout-spec.md: R8-1 claimed-placement cluster insets, R8-2 reach-band writeback clamp, R8-3 OSM tunnel chain yields inside classified object-tunnel bodies): ran only tests/test_round8_vhhh_closeout.py (new, 20 passed) plus the directly-covering files once (test_flat_site_mode, test_flat_site_detector, test_object_tunnel_terrain, test_tunnel_portal_fidelity, test_tunnel_portal_acceptance, test_tunnel_system_veto, test_implied_tunnel_level_crossing — 151 passed, 8 failed, and the SAME 8 fail identically on the clean main tree, so they are pre-existing and untouched by this lane); ZERO builds, so every claim is synthetic-twin evidence. **THE EXPLICITLY LEDGERED ONE (spec R8-2): the INTERVENTIONAL band-escape attribution is NOT done — the clamp is a containment law, not a root cause. Nothing here establishes WHICH solver stage published -12.5 m against a [4.6, 9.4] band; that needs a per-stage interventional arm (stage-boundary readback of the solved field against the same unified band) and is deferred to the hardening round. Every clamp is counted and logged (`layout.band_clamp_findings`, the `[writeback-band]` line) precisely so the defect stays visible until then.** UNPAID besides: (a) the acceptance metric — VHHH `band_excess` floor-side MATERIAL rows -> 0 — has never been measured: no VHHH build ran, the 199 floor-side escapes to 17.15 m have no post-change counterpart, and the clamp's effect on every other battery airport (HECA/KCLT/SPJC/SPLP/CYXY) is unknown, so how many lawful-today vertices the clamp moves is unmeasured and no census or absolute-zero arm was run; (b) `_writeback` now BUILDS the unified band itself when the caller passes none (two extra `build_unified_graph` + `reach_band_unified` constructions per airport, ~1 s each by adjacent_ground's own estimate — a ~3 % charge against the 60 s per-airport budget that was NEVER measured with `check_build_time --runs N`; the `band=` parameter exists so a caller already holding the band can pay nothing, and no call site uses it yet); the node-list rebuild is `readonly=True` with both published index attributes snapshotted, so registry purity is asserted by construction and never by a byte-identical patch arm; (c) ROLE_RUNWAY is excluded from the clamp by design (CIFP-hard, band-checker-exempt) — that scoping is a reading of the checker's exemption, not a measurement; (d) R8-1's claimed-placement scan has never run against a real X-Plane install: the CIFP-runways -> `driver._airport_claim_lonlat` -> `driver._object_anchor_worklist_entries` -> `post_mesh.worklist_claim_assigner` chain is exercised on synthetic points only, so "all 5,708 VHHH placements fall to VHHH" is the recon's number and has no post-change counterpart; the 300 m join and the 5-placement floor are the spec's constants, never swept; the per-cluster BBOX (not hull) is what the rectangular inset bake needs, so two clusters whose hulls clear each other can still have overlapping boxes — the 450 m VHHH channel against 2 x FLAT_SITE_MARGIN_M (200 m) leaves ~50 m of raw DEM by arithmetic alone, never by a built raster; and the scan's build-time cost on a busy tile (one `read_dsf_object_placement_positions` per enabled pack DSF, sidecar-cached, plus a CIFP parse per candidate ICAO) is unmeasured; (e) R8-3's yield has never run inside a build — `_object_trench_body_union` and `_yield_piece_to_object_trench` are proven on synthetic bodies and quads, so the 58 % of OSM ramp area outside every pack body and the 61 conflicting quads have no post-change counterpart, the `tunnel4_done` no-trench survival is asserted on a fixture rather than on the real VHHH classification, and the 50 % drop fraction plus the 2 m margin are chosen constants with no sweep; the drop-vs-clip split (corner-shared ramp/throat pieces drop whole, flat wall bands clip) is justified by this file's own ramp-internal-corner-agreement invariant, never measured against an emitted patch; and the downstream perimeter-wall band, which is traced around the surviving ramp union, was never re-derived after a drop.
- 2026-08-10 lane/fastpath (FLAT-SITE FAST PATH phase 3 — the SOLVE PARTITION, spec docs/specs/flat-site-fast-path-spec.md): ran tests/test_flat_site_fast_path.py (26 new) plus the files directly covering the touched code (test_band_reports_instrument, test_band_seed_completeness, test_eat_ceiling, test_envelope_from_band, test_fan_ramp_law, test_final_projection_snapshot_recapture, test_flat_airport_fast_path_retirement, test_flat_site_detector, test_flat_site_mode, test_gs_no_airside_witness, test_hard_anchor_class_axis, test_one_solve_skirt_pins, test_patch_provenance, test_projection_law_ingestion, test_raster_reach_band, test_reach_band_clusters, test_route_band, test_route_metric_envelope, test_runway_end_resa_cut, test_seam_dem_anchor, test_service_spine_feasibility_exclusion, test_single_graph_acceptance, test_taut_string_probes, test_torn_datum_pin_release, test_zone_constraint_consumption, test_object_bridge_terrain, test_round4_pads_claims_transition — 626 passed, 9 failed, 4 errors), once; ONE OTHH patch build and no other airport. UNPAID: (a) THE EQUIVALENCE TWIN IS SYNTHETIC ONLY — the fast/full arms are compared on a hand-built five-shape fixture, never on a real airport, so "the seam is exact" at OTHH rests on the born-at-Z0 residual report (worst |z − Z0| after the solve) and on the reference-patch comparison, not on a two-arm OTHH A/B; no HECA/KCLT/SPJC/SPLP/CYXY build ran, so battery INERTNESS on non-flat sites is by the gate and the no-substitution-stamp twin alone and was never measured on a real hilly build. (b) NO CENSUS was run on the emitted patch, so the absolute-zero acceptance gate has not been applied to a fast-pathed surface — the claim that a constant field satisfies every within-shape and step law by construction is an argument, not a census row count. (c) THE PHASE-TIME REPORT IS A SINGLE UNCONTROLLED RUN (spec: order-of-magnitude only) — no `check_build_time --runs N`, no matched control arm, and the "Assembling pavement" phase in the OTHH ledger swings 1.4 s to 485 s on cache warmth alone, so no speed claim of any precision is supported. (d) TWO DEVIATIONS from the frozen spec are landed and await Fable review (see the commit message): §1c's below-grade union does not exist at solve time (the emitters run post-solve) and was closed with the pre-solve crossing-influence zone plus an unbounded veto on the R5 transition-role family, and §1b's strip envelope was widened by |runway − Z0| / TAXI_MAX_GRADE — both are strictly conservative, both are evidenced by synthetic twins only, and neither has been measured for how much of a real airport it costs the partition. (e) The reach-band `skip_idx` lever is proven by a closure twin, never by a measurement that the skipped nodes' bands were genuinely never consumed; and `final_grade_projection` deliberately keeps FULL law coverage (its constraint build is not skipped), so the projection re-seeds the pins in a second node space that no test exercises. (f) No blast-radius suites for config.py / solver_primitives.py / solve.py / anchors.py / grade_graph.py, and no build-time statement (per-change timing gates remain suspended). (g) The FLATNESS-CERTIFICATE EXEMPTION (lead ruling 2026-08-10, commit b48d886) was measured by ONE further OTHH build against ONE pre-exemption build of the same lane — 286.35 -> 273.82 s solving, 916.9 -> 900.0 s total — both single uncontrolled runs inside a +/-25 % wall-time noise band, so only the deterministic certificate tally (apron refused 5->0 of 18, junction refused 118->94 of 160) actually evidences the mechanism; the residual gap against the owner's 205.9 s reference phase is UNATTRIBUTED (different tree, and this lane's builds ran with four Airport_mod_cache writes guard-blocked, i.e. cold object caches) and no matched control arm was run. The exemption's soundness — that a born-at-Z0 pin sits exactly at its own DEM sample — is proven by the synthetic equivalence twin only, never by a certified shape's law coverage being re-checked on a real airport.
- 2026-08-11 lane/bandfix (Round 9 — the writeback clamp reads THE band in THE frame, spec docs/specs/round9-writeback-band-frame-spec.md): ran only tests/test_round9_writeback_band_frame.py + test_round8_vhhh_closeout.py + test_final_band_inversion.py (49 passed), once; TWO acceptance builds (CYXY rc=0 was 4 inverted nodes; KCLT rc=0 was 26, under --allow-degraded-dem because the shared corpus has no warm o4_dsf_road_network_+35-081.cache — warming it is an owner --refresh-data airport_mod_cache decision). UNPAID: no other battery airport rebuilt (VHHH/OTHH/HECA/SPJC/SPLP inversion-free is inferred from the shared mechanism, not built); no census on either emitted patch, so the clamp's population effect (KCLT worst clamp 0.27 m on a junction, 3 passes 4/43/38 values) has no absolute-zero arm; the deleted double graph build per airport is a cost REMOVAL claimed without a timing arm; the unconditional env_band mint's memory cost (~len(nodes) tuples every build, previously gated) is unmeasured; and the ledgered interventional band-escape attribution (WHICH stage wrote -12.5 at VHHH) remains open — the clamp is containment, round 9 only fixed its frame. ALSO ON RECORD: KCLT's first acceptance run wrote 1 path into the shared corpus (Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text, the DSFTool dump cache — the harness build path lacks the pytest suite's O4_DSF_CACHE_DIR redirect; pre-existing, not this round's code).
- 2026-08-11 lane/selrestore (app: restore tile selection across launches, spec docs/specs/app-restore-tile-selection-spec.md): ran swift test once (47 passed; TileMath round-trip/reject pins extended). UNPAID: the BuildModel persistence wiring has NO unit coverage — the repo has no app-side test target (SceneryKitTests only), so restore ordering (after loadCachedTileStates), the active-tile fallback and the didSet write-back are covered by the TileMath pins plus the owner's in-app §5 manual acceptance only.
- 2026-08-11 lane/r11kmci (Round 11 — flat-claim guards + inset validity, spec docs/specs/round11-kmci-flat-claim-spec.md, amended in-flight): ran the new twins (15) + direct-covering files once (297 passed, 6 pre-existing test_flat_site_mode no_data failures matched name-for-name at base befb3ba); TWO KMCI acceptance builds under --allow-degraded-dem (cold Airport_mod_cache, pre-existing — the 12:30 owner refresh run hit the identical 4 blocked writes), byte-identical body_sha c893c9f4ded0. MEASURED: adjacent step 59.36→1.70 m, apron min 234.20→292.40 m, ways-below-270 253→0, KFLV clusters 10 of 12 refused on distance (incl. the 12.73 km2 plateau-maker), 2 datum-clean survivors beside KFLV. ACCEPTED RESIDUAL (lead ruling): 29 groundside_pavement nodes 283.75–284.91 m under the spec's 285 floor — base-DEM-conformant real terrain (controls 284.61/283.58). UNPAID: no VHHH arm, so the HZMB fallback-cluster survival is proven by twins + the KFLV survivor pair only, never by a VHHH build; the 9 other effectively-empty insets on the tile (KSTJ etc.) now fall back loudly but were not adjudicated; inset_valid_fraction costs ~5.06 s/42 insets once per process (decimated read, cached) — no timing arm; no census/battery. OWNER items open: KMCI lidar refetch (garbage inset deleted+refetched via --refresh-data dem), airport_mod_cache regularisation for +39-095, and the 12:30 refresh run's own DSFTool dump contamination (+39-095.dsf.d40b9d78.text) on record.
- 2026-08-11 lane/r12bridge (Round 12 — bridge deck-top datum, spec docs/specs/round12-bridge-deck-datum-spec.md + 2 amendments): ran the new twins (35) + direct-covering files once (333 passed) + mesh_sampler/object_rebake importer safety (242 passed, 11 pre-existing skips); ZERO builds — the seat runs only at end of build_mesh, so acceptance is the OFFLINE REPLAY against the 2026-08-10 19:53 +25+051 mesh (class-A pins hit exactly: deltas 4.1589/3.9013/2.9831, deck tops at abutment grade, Bridge_04 supports -2.592 m below water) and the owner's next in-app +25+051 rebuild is the in-sim acceptance. UNPAID: no tile build, so the seat has still never run in production post-mesh; the mesh-attribute column's memory (+~25 MB int64 per tile inside the cached arrays) and the pass-reorder (seat before generic y-bake) have no timing arm; cache versions 15→16/5→6 discard warm classification caches by construction only. OPEN ITEM (new): class B (OTHH Bridge_02/03/06, the owner's third coordinate) remains on the generic y-bake with its per-structure tear — its abutment lines are 175 m chords of the MERGED mega-pool rect (axis along the canal; the classifier flags the merge as an artifact at object_terrain_features.py:3677), so no sampling law can seat it; the fix is splitting the mega-pool merge into per-bridge components — a future classifier round. bridges.py:10080 crossing-floor decline remains untouched (R6-3 ledger).
- 2026-08-11 lane/r12b (Round 12 amendments 3+4 — assembly seat via deck-face ends + agreeing coalition): ledgered battery run LAST over every importer (717 passed, 11 pre-existing skips; ba8e146 also fixed a seat_plane_y0_m test regression 5b4cc41 had introduced on main — caught by exactly that discipline); acceptance replay-only (class A byte-stable across both amendments; class B seats off Bridge_06's 4-member coalition, delta +0.95762, grade 3.9620, tear 0.000, supports to -8.708). UNPAID: the canal-floor land-bit residual stands (the mesh attributes the canal floor as land at 0.00 m — 8 outlier members carry it in the coalition finding's census; a mesh-side water-attribution question for the owner/hardening round); the smear-tie fallback and coalition law have no production exercise beyond OTHH's replay; no tile build — the owner's next in-app +25+051 rebuild remains the in-sim acceptance for ALL of round 12.
- 2026-08-11 lane/r10tunnel (Round 10 — tunnel emission, spec docs/specs/round10-tunnel-emission-spec.md + amendments A1-A8): ran the tunnel test files once per commit (final: 176 passed, 2 pre-existing test_tunnel_portal_fidelity R4 pins matched at base); acceptance KCLT + OTHH harness builds per commit (final KCLT_20260811T1405 / OTHH_20260811T1412, both rc=0, shared repo UNCHANGED). MEASURED: KCLT area-1 passthrough shapes 10→0, patch-wide wall∩ramp 2003.9→0.0 m2, roof∩pavement 1.51→0.0 m2, both F|-255 mouths at mapped portals (48.3→0.6 m), mouth depth 3.2→5.10 m, one flat open corridor (286.6 m2, spread 0.00); OTHH restored IDENTICAL to base (8 clusters / 93 shapes / 32396 m2; the A6-arm deficit was entirely the dedup). UNPAID: no VHHH/battery arm (the cover-fraction constants 0.5/0.10 rest on the KCLT+OTHH separation margins 0.02-vs-0.18 only); the LMML merge-class drop is pinned by twins, never by an LMML build; the corridor law has ONE production instance; walk/cover-computation build-time unmeasured (timing gates suspended); the two pre-existing portal-fidelity pins remain ship-gate items.
- 2026-08-11 lane/cacheredirect (harness engine-cache redirect: `build_airport.py` points `O4_DSF_CACHE_DIR` + `O4_AIRPORT_MOD_CACHE_DIR` at per-run lane-local dirs under `<out>/<tag>.engine_caches/`, the mod cache a symlink-seeded read-through overlay — the pytest suite's own mechanism; closes the round-9 KCLT DSFTool-SUBPROCESS corpus write on record above; an authorised `--refresh-data airport_mod_cache`/`dsf_cache` scope is deliberately NOT redirected): ran tests/test_harness.py once (191 passed, ledgered, three new twins) + TWO guarded KCLT builds. The FIRST (08:17) was snapshot-flagged CONTAMINATED by 96 writes that were ALL the owner's concurrent UNGUARDED app batch-build (KMCI/VHHH/KCLT tiles; attribution: our guard blocked=[], overlay 1,109 symlinks / 0 real files, empty lane dump dir, live `--engine-worker` processes + app tile ledgers +39-095/+22+113/+35-081 — none of the 96 is this build's); the SECOND, in a quiet corpus window, recorded shared repo UNCHANGED with zero contamination rows, rc=0, body sha IDENTICAL to arm 1 (a0852c8f6587), and needed NO --allow-degraded-dem (round 9's KCLT arm did, for the guard-blocked mod-cache writes the redirect now sends lane-local). UNPAID: the cold-cache end-to-end arm — a DSFTool dump actually landing in the lane-local dir mid-build — is proven by the unit twins only, because the corpus is already warm for +35-081 (round 9's contamination left the dump + road-network cache there, with NO refresh-ledger entry: owner decision pending on keep-as-warmed vs purge) so neither build ran DSFTool; `run_tile_mesh_only.py` still lacks the redirect (guard + snapshot only, as before); `oracle.py`/`who_wrote.py` inherit the redirect through `build_patch` but were not rebuilt. Lane-local (uncommitted): `Ortho4XP.cfg` `airport_inset_water` aligned False→True to production to pass the cfg-frame refusal.
- 2026-08-11 lane/stopresume (app: activity-pane stop/resume, spec docs/specs/app-activity-stop-resume-spec.md): swift build + swift test (47) once. UNPAID: no app-side test target, so the stale-event rule (mayOverwriteStopped/resolving), the resumeQueue order/dedup and the run-settings snapshot are pure static helpers with NO pins — owner's in-app acceptance per the spec's §Acceptance; two conservative edge rulings (run-stop drops resumeQueue; stopped rows survive the post-run clear, footer hidden when idle) approved by the lead and recorded here.
- 2026-08-11 lane/r13border (Round 13 — border-aware inset fetch + --warm-insets, spec docs/specs/round13-border-aware-inset-fetch-spec.md + amendment): tests 194+387 ledgered once; gdal nodata-passthrough MEASURED (later valid wins, later nodata never overwrites — one warp, no fill passes). ACCEPTANCE PARTIAL: R13-1 fired end-to-end on the real corpus (stale KMCI record archived as .json.invalid-2026-08-11, refetch ran); TNM 504'd twice (intermittent — out-of-band probe 200 with 7 products: 4x MO_FEMANRCS_2020_D20 OLDER than 3x KS_Statewide_2018_A18, proving R13-2's mechanism against live data); the provider chain fell through to COPERNICUSGLO30 which landed a VALID 30 m inset (valid_fraction 1.0, sweep reads relief 17.12 vs no_data before) — the 1 m 3DEP upgrade awaits a TNM retry. UNPAID/LEDGERED: (1) DEFECT — a transient discovery failure becomes a durable negative: discover() returns None for a 504 exactly as for no-products, so the index caches 'no-coverage'; TransientFetchError exists but discover never raises it (the same record-of-nothing shape R13-1 fixes one layer up) — ship-gate or follow-up round; (2) OWNER DELETION needed: stray guard-blocked temp OSM_data/_regional_extracts/clips/clip_+039-0095_ca6faf7adabd-part0.osm.pbf.tmp-38055-8469427648.osm.pbf; (3) a Copernicus fall-through needs --refresh-data dem,osm_layers (its building masking clips OSM) — scope widening is lead/owner-authorised per event; (4) the is_cached size>0 gate can skip the inset pass for non-empty-but-invalid rasters (--warm-insets bypasses for named airports); (5) known cross-attribution flags from concurrent lanes/app, recorded not chased.
- 2026-08-11 lane/r14roads (Round 14 — roads serve tunnels, spec docs/specs/round14-tunnel-road-integration-spec.md + amendment; RULINGS.md gains the taxiway-family protection superseding ruling 4): tunnel+groundside test files once per commit (final 305 passed, 8 pre-existing matched at base); KCLT + OTHH acceptance builds. MEASURED: the cliff class DEAD (road-vs-tunnel pairs 4@8.31m→0), SE chain 173→90 m with the three run-extenders (8 m synthetic floor, 3.5 0ghway grade, 200 m minimum) removed, junction 378 clear, triangle level plate spread 0.13 m (pinned vertices exact), round-10 table holding, OTHH 8/8 systems on the claimed-pavement instrument with 76 object trenches identical. ACCEPTED RESIDUAL (lead): level plate 0.13 m vs the 0.10 bullet — no protected node moved; two adjacent claimed regions carry different clearance floors (210.87/210.98); fix = ONE floor per connected claimed plate (A7(b) joint depth applied to the claim), FOLDED INTO ROUND 15 with the wall-face/anchor residual (recon: 275 wall nodes ≥1 m above a ramp within 2 m; the unowned 0.62 m wall_gap strip takes Z0; transition anchor lands at the shallowest station against the law's own deepest-station prose). UNPAID: OTHH not rebuilt after the pin commit (pin fires only on tunnel_road refs — argued, not built); the airside-conflict finding (apron -10602 in the triangle, likely scorer-misclassified) awaits classify-instrument adjudication; no VHHH/battery arm; ±5- 2026-08-11 lane/r14roads (Round 14 — roads serve tunnels, spec docs/specs/round14-tunnel-road-integration-spec.md + amendment; RULINGS.md gains the taxiway-family protection superseding ruling 4): tunnel+groundside test files once per commit (final 305 passed, 8 pre-existing matched at base); KCLT + OTHH acceptance builds. MEASURED: the cliff class DEAD (road-vs-tunnel pairs 4@8.31m→0), SE chain 173→90 m with the three run-extenders (8 m synthetic floor, 3.5% highway grade, 200 m minimum) removed, junction 378 clear, triangle level plate spread 0.13 m (pinned vertices exact), round-10 table holding, OTHH 8/8 systems on the claimed-pavement instrument with 76 object trenches identical. ACCEPTED RESIDUAL (lead): level plate 0.13 m vs the 0.10 bullet — no protected node moved; two adjacent claimed regions carry different clearance floors (210.87/210.98); fix = ONE floor per connected claimed plate (A7(b) joint depth applied to the claim), FOLDED INTO ROUND 15 with the wall-face/anchor residual (recon: 275 wall nodes ≥1 m above a ramp within 2 m; the unowned 0.62 m wall_gap strip takes Z0; transition anchor lands at the shallowest station against the law's own deepest-station prose). UNPAID: OTHH not rebuilt after the pin commit (pin fires only on tunnel_road refs — argued, not built); the airside-conflict finding (apron -10602 in the triangle, likely scorer-misclassified) awaits classify-instrument adjudication; no VHHH/battery arm; the OTHH area bullet superseded by the claim law (composition-aware reading recorded).
- 2026-08-11 lane/qtparity (Qt parity — selection restore + stop/resume, spec docs/specs/qt-parity-selection-stop-resume-spec.md): 13 Qt test files once, ledgered (172 passed; 47 new); headless import-clean verified. UNPAID: no visual run — the owner's Windows/Linux app pass is the acceptance (painted 16 pt octagon + centred square, green play disc, orange stopped badge, selection restore via .qt_prefs.json selected_tiles/active_tile); the Q3 DRIFT LIST is open owner backlog: (1) Qt lacks the optimistic built/installed launch overlay (no scan cache), (2) raw ETA shown where Swift suppresses climbing estimates, (3) no per-tile config-conflict badges, (4) NO SecretRequest handler — provider credential prompts have no UI on Windows/Linux (cross-platform feature, most substantive gap), (5) run-clock footer suppression now matched. Engine drained-row rows offer no resume — matches shipped Swift.
- 2026-08-11 lane/r15mesh (Round 15 — degenerate sliver never kills a tile, spec docs/specs/round15-mesh-attr-crash-spec.md): 83 tests once, ledgered; OTHH +25+051 mesh replay rc=0 reproducing the crashed build exactly (8 non-integral attrs contained loudly vs 1 crash); KCLT control clean. BONUS FIX: the old fast-skip line[-2]=="0" skipped post-treatment for ANY attribute ENDING in 0 ("10"/"20"/"40" — SEA/WATER masks silently unprocessed, pre-existing) — replaced with a last-field test. R15-2 STOPPED per its own condition: the mesh weld is INNOCENT (0 pairs within 1e-9 in the INPUT; snap_to_grid(9) welds correctly) — the crash vertices are Triangle STEINER points from a ZERO-WIDTH CONSTRAINED LENS minted by ONE RING SPELLED TWICE in the patch (object_pad:2336 ring vs its shape_interior_ring partner way differing by one vertex EXACTLY on the chord; population 33 twin-ring pairs / 59 missing vertices / 5 exact-on-chord in the OTHH patch; the needle-removal law at layout.py:1606 partners exterior ways only). ROUND-16 QUEUE: twin-ring spelling consistency (auto_patch), with the wall-face/anchor/joint-floor + needle family. UNPAID: the 12,529 sub-micron Steiner components remain in the mesh (containment moves no geometry); run_tile_mesh_only gained first_step=2 (INDEX'd) — a rootless checkout silently builds a smaller mesh at rc=0 (why the replay arg exists), harness-class trap noted; scratch cluster-counter flagged for promotion if round 16 needs the measure.
- 2026-08-11 OWNER RULING (session 2026-08-11b, interview): the +39-095 contamination records from the 2026-08-11 morning runs are ACCEPTED-AS-ANNOTATED, not open contamination — the KMCI 12:07/12:40 runs' [masks] (Masks/+30-100/+39-095/6192_3856.png), [dem] (N39W095_airport_insets KMCI sidecars; superseded by the owner-authorised --warm-insets refetch, refresh-ledgered 15:44/15:53), [airport_mod_cache] (+39-095.dsf.d40b9d78.text DSFTool dump; +35-081/+30+031 footprint caches — the .lock-family/idxchurn class per RULINGS) and [osm_layers] (clip_+039-0095 .tmp partials) rows: content is regenerated-correct, the records were procedural. The stray clip tmp-38055 partial was DELETED under explicit owner authorisation this session. Future sessions must not re-triage these rows; frame/ledger CONTAMINATED lines matching this set read as accepted. OTBD/OTBH flat_site_declared keys DEFERRED (owner: needs in-sim look first).
- 2026-08-11 lane/qtbacklog (Qt backlog QB1-3 + QB4 attribution, spec docs/specs/qt-backlog-parity2-spec.md): 14 Qt test files once, ledgered (200 passed, 28 new in test_qt_backlog_parity.py); import-clean verified. QB1 scan cache at FNAMES.data_path(".tile_scan_cache.json") v1 (atomic write, provider-normalized, key-pair + version guarded); QB2 detector constants 45/30/+5 landed, dash/frozen-clock/tile-clock rules measured ALREADY PRESENT and untouched; QB3 names-only foreign-source audit + screen-point triangle badge (px>14 gate) + info-panel "mixed" row. UNPAID: owner Windows/Linux visual pass (badge legibility across zooms, overlay swap on first rescan); _reaudit_conflict has no UI caller (no texture-cleanup action exists in Qt yet — test-exercised only). QB4 STOP-REPORTED, NOTHING BUILT (measured: Qt runs the engine in-process only — no SecretRequest can reach it, jsonl.serve is the only broker installer; parallel-worker secrets serviced parent-side via keyring, Win/Linux backends already bundled; _SignInDialog covers session/http_basic/api_key with registration_url + LoginError surfaces; build-time LoginError WARNING lands in the visible console drawer) — retire-the-item is an OWNER ruling, pending; NEW unfiled gap the measurement surfaced: the macOS Swift app has NO provider sign-in UI at all (Qt is ahead).
- 2026-08-11 lane/swiftsignin (Swift provider sign-in, spec docs/specs/swift-provider-signin-spec.md): protocol 1.4→1.5 additive (auth_providers/provider_sign_in/provider_sign_out + SignInResult); engine tests once ledgered (95 passed, 11 new incl. the read-loop deadlock twin proving the secret rode the broker); swift build green + 51 SceneryKit tests (4 new decode). THREE deviations Fable-APPROVED in merge: async sign_out (it IS a store op — the spec's "local" premise was false), api_key status pending/probe-worker pattern (store reads can't run on the read loop), additive stored_username() sidecar helper. UNPAID: owner in-app pass (Provider Accounts section + sheet, live dgterritorio session + dataforsyningen api_key sign-in, Keychain prompt attribution, status_pending refresh); live sign-out Keychain-gone check; engine-protocol-multi-gui.md §5 not yet updated with 1.5.
- 2026-08-11 lane/smallq (small queue, spec docs/specs/small-queue-20260811-spec.md): SQ1 KSTJ ATTRIBUTED interventionally — the EAT anchor-rect pin (EAT_SURFACE_CEILING, default ON) authors 241.8184 m (5.6 m below real 1 m-lidar ground, D_mid ≈321 m past the DER) into 18 junction nodes at another runway's threshold, contradicting the RW35 CIFP floor anchor 247.510 by 5.692 m over 0.93-1.24 m route budgets; O4_EAT_SURFACE_CEILING=0 arm builds CLEAN (0 inversions), O4_BAND_SEED_EXACT=0 arm identical-fail (seed-cell exonerated); the EAT pin lacks the seat-guard's hard-anchor contradiction check — fix is a Fable spec (queued); --tile arm never ran (empty default_website refusal), attribution rests on --patch-only. SQ2 artifacts delivered (KCLT: conflict shapes are claimable road pavement, apron-roled shape absent in current tree; NEW finding idx1254 13k m² apron scoring TAXI 0.58 HIGH; KMCI shapeID 995 CONFIRMED wide_blob-only APRON flip at 0.53 HIGH, zero airside features — verdicts are the OWNER's, artifacts in session scratch sq2/) — STOP ON RECORD: classify_report.py is UNGUARDED and wrote the shared corpus twice (10 mod-cache/DSF-dump files, +35-081 ×5 and +39-095 ×5; the symlink-seeded overlay writes THROUGH its symlinks without an armed SharedRepoWriteGuard) — this also ATTRIBUTES the vhhh17 recon build's 6-path CONTAMINATED flag (all +35-081/+39-095, the known cross-attribution class); classify_report must gain redirect_engine_caches + an armed guard before any further use (queued). SQ3 SHIPPED (merge 86889fd): discovery outages raise TransientFetchError at 6 sites (TNM, token-search, WFS index, ArcGIS layer query, static-catalog fetch; STAC deliberately kept stricter), genuine no-data stays durable None; 239 tests once ledgered; one pre-existing test rewritten because it ENCODED the defect (503→None); probe-loop sites (DegreeNamedCog memo, _tile_exists) left on old convention pending a lead/owner ruling.
- 2026-08-11 lane/toolguard (classify_report guard, brief-as-spec): test_harness.py once ledgered (198 passed; 5 new §6d twins, mutation-checked 3/5 fail unguarded; one transient xdist ERROR non-reproducing over two re-runs); the arming composition LIFTED into build_airport.arm_shared_repo_protection (two-phase by design: redirect pre-import, guard around the build call only) and build_patch rewired onto it — no behaviour change, twin-asserted. UNPAID: the guarded classify path has never run a REAL build (twins stub the engine; first real use must confirm corpus unchanged via the report's engine_cache_redirects/write_guard fields); tunnel_airside_conflict's lat/lon join key STOP-reported (mint site bridges.py:5483-5529, file owned by r16 lane; the KCLT instance is adjudicated closed — the key serves the CLASS) — folded into the scorer round.
- 2026-08-11 lane/r16geom (Round 16 + amendments 1-2, spec round16-geometry-consistency-spec.md; merged 7559e91): 22 files ledgered ×4 attempts (final 576 passed / 2 pre-existing matched at base); 12 harness builds, guard UNCHANGED on all. SHIPPED: OTHH unowned wall nodes 17→0, KCLT 24→0 (incl. tunnel_cap); portal anchor (cross-section station); joint claim floor (twin-only — KCLT floors 211.10 both arms, defect non-repro); rings as sliver sources (sub-2° tips 2→0); chain_divergence_audit promoted+INDEX'd. RETIRED by measurement: the 25° class (1,189 lawful corners would deform; existing 2.0°/0.09 m bounds the tail). STOP STANDING (R16-1b): 20 twin-ring pairs / 46 vertices at OTHH — tolerance EXONERATED (5 mm→150 mm byte-identical patches ×3); the block is PAIRING (the 20 pairs never enter the candidate loop; they share 4-32 nids in the EMITTED frame but not pre-splice — next step is the hole ring's pre-splice nid identity). Sub-micron clusters 0 every arm; census Δ0 both airports. UNPAID: tile build + mesh replay (object pads need the 4-step build); R16-3 real-data arm; ramps-clipped-after-wall class.
- 2026-08-11 lane/r17vhhh (Round 17, spec round17-vhhh-reclaimed-island-spec.md; merged 145394c): 344 passed + 1 xpassed ledgered (792 s); tile steps 1-3 + patch-only builds, guard refusals honoured (masks legacy_mask refused, no write). SHIPPED: seal_pavement_to_band as pipeline-exit LAST author (VHHH 1 shape, VMMC/SPJC 0, ZGSZ 4, all SEAL INTACT); ONE band construction (owner law) — band_excess reads the band of record, VHHH 245→0; corridor declaration flat_site_declared_corridors verified on the MESH (7.32 m flat full width, sea 0.00 20 m outside both edges, channel north stays sea); seawall admission role-scoped + tools/seawall_admission.py INDEX'd. ATTRIBUTION (refutes the spec premise): the CANYON AUTHOR IS THE CLAMP obeying a POISONED carried band (junction ceiling [−12.93,−12.14] vs solve 7.01 at Z0 7.315; below-grade anchor in spine_value_fields' ceiling MIN — the KCLT R10 leak family); post-solve seams move nothing material. Canyons UNCHANGED (25C transect −6 m) — fix queued r17b. STOP (R17-3): ≥90% shoreline unreachable via coverage-boundary offset (coverage edge 20-300 m inland; 6.5%→11.1% with corridor) — coastline-wall construction queued r17b. HECA test_route_band XFAIL→XPASS (report agrees with clamp by construction) — labelled drift instrument DEFERRED to ship gate (lead ruling). ONE-BAND ruling not yet extended to seats/anchors/apron-terrace/adjacent-ground (4 constructions/airport remain) — queued.
- 2026-08-11 lane/scorer (S1 wide_blob authorship + S2 KCLT idx1254 + the folded-in tunnel finding, spec docs/specs/scorer-wide-blob-authorship-spec.md): directly-covering files once — test_pavement_scoring.py + test_classification_round.py (119 passed; base 7c03dc4 = 107 passed, so 0 pre-existing failures, +12 new) and test_round14_tunnel_road_integration.py (28 passed, +1 new); both mutation-checked (gate disabled ⇒ 5 fail; lat/lon removed ⇒ 3 fail). ACCEPTANCE PARTIAL, two misses, both attributed, NO third attempt (cap 2). MEASURED: KMCI idx 139 (36,628 m²) and idx 1052 (53,154 m²) — the ruling's own specimens — now stay GROUNDSIDE, gated (`GROUNDSIDE->APRON` gone from KMCI's confusion); census ADJUDICATED KMCI 1513→1518, CYXY 84→84 (Δ0, gentle control holds), KCLT 585→714. MISS 1: the emitted body carrying shapeID 995's 28,622 m² does NOT flip — in the ENACTED build it reads `taxi_contact` 1.0 (it shares edge with the neighbouring landside lot the legacy chain roled apron) so S1's gate never fires on it, and G-CHAIN+G-TAXI-ONLY hand it back APRON through the G-CONFLICT reset; the adjudication measured it in SHADOW mode where the same neighbours are groundside and taxi_contact reads 0 (two instruments, one assumed population). Fixing it means a new law about contact with GATED apron — a deviation, so STOP-and-report, not decided here. MISS 2: KCLT is not Δ0 — +129 adjudicated, 96 % of it `within_shape::groundside_pavement` on two newly-demoted landside bodies (ways -11715 22.6k m², -11729 12.3k m²) whose DEM-followed surface sits at 5-7 % against the 4 % groundside cap; they were flat only because apron law was flattening a hillside car park. That is a groundside-grading defect the gate EXPOSED, not one it created — needs an owner ruling / its own round. UNPAID: no in-sim look; no full suite; no battery beyond KMCI/KCLT/CYXY; `alt_name_apron` is NOT on the ruled airside-contact list (alt-pack-only apron names can no longer author APRON — pinned by a twin and flagged in RULINGS, owner may want it added); the tunnel finding's two mint sites still record the SAME shape twice (one shape reads as "2 AIRSIDE shape(s)" in the log — visible now that both records carry the same centroid, dedup deliberately not done); classify_report's forced shadow frame prints LEGACY roles with no banner saying so (the S2 artifact exists because of that) — a `--mode`/banner extension is a DEFERRED candidate.
- 2026-08-11 HECA mod-cache contamination CLOSED (owner-authorized): the explicit `--refresh-data airport_mod_cache` HECA run (457 s, rc=0, heca-refresh-owner artifacts in /tmp/harness) found the corpus byte-stable — the recon build's 5 rewritten footprint-cache files already matched the refresh's own output, so no ledger delta was recorded and none was needed. The hecarecon CONTAMINATED flag reads as regularised; future sessions do not re-triage it.
- 2026-08-11 lane/r18heca (R18-2 building-evidence pad gate, owner ruling 2026-08-11b): ran the directly-covering files only (test_dsf_object_buildings, test_contracts, test_dsf_buildings, test_object_pads, test_airport_elevation_insets — 347 passed, ledgered); no blast-radius sweep for config.py / dsf_reader.py / object_footprints.py / pipeline.py / terminals.py, no full suite, no battery beyond HECA + OTHH. **Four acceptance items are UNMET and are the round's STOP-report, not skipped verification:** (1) of the four named HECA phantom pads, 177 and 186 are GONE and 172 loses 62.4 % of its area, but **176 survives 100 %** and the residual is attributed to a DIFFERENT defect (below); (2) the ring-population census is not Δ0 — HECA improves by −201 rows / −94 adjudicated with **plane_gradient +1** unattributed; (3) OTHH's object-pad population is **not unchanged** (86 → 66 building pads, 1358 → 1245 rings, 122 refused; the tunnel machinery IS unchanged — tunnel_ramp 17/17, 10 trench floor + 66 rim collar both arms, R14-1 claimed 10 road surfaces both arms, census −25 rows with no family worsening), so the gate is not HECA-local and those 20 OTHH pads are unadjudicated; (4) the two owner coordinates carry no pad in either arm, so the "phantom cut" there was read as the local surface instead — 40 m spread 19.84 m → 0.24 m and 17.97 m → 0.71 m, the 86.71/86.16 m pad floor gone from both neighbourhoods, but the armed surface sits ~93 m against a ~104.7 m DEM and that residual is unexplained. **The blocked root cause:** `object_footprints.structure_ring`'s `name_vouched` matches "hangar"/"terminal" ANYWHERE in the resource path, so HECA's `Airport/Hangar_Tower/` directory vouches 667 of 817 rings and disables BOTH the 0.1 hull-fill and 0.002 tall-base floors across the pack — building176's 31,184 m² seed ring measures hull fill 0.00036 and is kept. Substituting the scoped `evidence_name_vouches` is measured-correct (817 → 210 rings, every survivor's hull fill 0.11–1.64) but makes the HECA build FAIL `assert_no_final_band_inversion` at 679 of 4,792 band-covered nodes (anchor pair 5984 @110.610 m 05C/23C vs 3284 @60.980 m 05L/23R, 2.0709 m route-budget shortfall). Attributed interventionally: the same failure reproduces with the R18-2 gate OFF and only the substitution live, so it is the substitution and not the gate. The remedy is in `elevation_per_surface/` route-budget/seating, outside this round; the wide predicate stands and the code carries the finding at its site. Artifacts: `<scratch>/accept/r18{ctl,arm,arm2,namescope}_HECA.*`, `r18{ctl,arm}_OTHH.*`, `<scratch>/heca_evidence_{base,armed,prefilter,scoped}.json`.
- 2026-08-12 lane/eatguard (EAT anchor-rect adopts the seat-guard's hard-anchor contradiction predicate, spec `eat-anchor-contradiction-guard-spec.md`; closing acceptance builds DROPPED per RULINGS 8537d9f "consolidated acceptance, lead-owned"): ran the directly-covering files only — test_eat_ceiling (72), test_seed_fix_anchor_cap, test_taut_string_probes, test_final_projection_snapshot_recapture, test_torn_datum_pin_release, test_terrain_pin_quarantine_retirement = 113 passed, ledgered; no blast-radius sweep for `route_profile/solve.py` / `solver_primitives.py`, no full suite, no build-time measurement (the guard adds TWO Dijkstras over the airside spine graph per solve, and only when the layout carries EAT pins, plus one per-pin snapshot dict; tripwire only). **Measured, both arms, same corpus (pre-dating the owner's 2026-08-12 warm sweep):** KSTJ `--patch-only` base f5cea9c rc=1, `BandInversionError` at 31 of 603 band-covered nodes, NO patch written; lane rc=0, ZERO inversions, patch + sidecar written, writeback-band clamps 153/118 → 8 with the worst falling from ±4.76 m (the pin's own 241.8184 value against band [247.51, 242.75]) to −0.14 m; 5 of 18 pins refused (worst 4.759 m past floor 246.577, witness anchor 182 = 247.510, route budget 0.9329 m). HEAZ `--patch-only` base vs lane body_sha256 IDENTICAL (e0b5ab907301) — HEAZ publishes no EAT end spec, so the guard is measured-inert there. **NOT measured, and owed on the consolidated arms:** (a) HECA — the −15 m EASA pin's verdict is PREDICTED, not built: the four pins 316 m off the 23C end are refused iff their route budget from that end's anchor is under 15.0 m (≈1000 m of taxi route at the 1.5 % cap), which an end-around taxiway wired into the taxiway system near the runway end will normally be under, so REFUSAL IS EXPECTED; one grep decides it (`[eat-anchor-rect] HECA: N of M pin(s) REFUSED`). (b) **KCLT is the risk item**: it is the feature's reference airport (6 pins at end −8.58 m) and the same arithmetic refuses them whenever the route budget from the DER anchor is under 8.58 m (≈572 m of taxi route) — if that fires, the law neutralises the EAT depression at the airport it was built for, and the owner must rule whether the pin or the anchor yields. (c) no census run at all on any airport (KSTJ base wrote no patch, so it has no census; HEAZ's arms are byte-identical, which is strictly stronger than a census delta). (d) **The guard is priced AFTER two constraint builders have already read `elev`/`base_hard` with the pin in place** — `_hard_for_certificate` (a hard node REFUSES flatness certification, i.e. MORE law, never less) and `_build_gap_spine_constraints(seed_elev=elev)`'s disjoint-parent tie-break. Both are conservative-direction arguments, neither is measured; making them exact needs the unified-graph build moved above `_build_shape_constraints`, which was judged out of scope for this round. Artifacts: `<scratch>/{kstj2,kstj_base,heaz_lane,heaz_base,cyxy_lane}.log`.
- 2026-08-12 lane/scorer AMENDMENT 1 (S1b lawful-airside vouching + S3 groundside at the road limit, spec scorer-wide-blob-authorship-spec.md §AMENDMENT 1; main merged for a single frame): covering files once, ledgered — test_pavement_scoring / test_classification_round / test_owner_constants_round / test_round14_tunnel_road_integration / test_groundside_law_authority / test_apron_terrace_law, 244 passed, 0 pre-existing failures; mutation-checked (closure stubbed ⇒ 5 fail; cap reverted ⇒ 2 fail). MET: KMCI shapeID 995's EMITTED body is now groundside-family (point-in-polygon inside way -11006 groundside_pavement, with idx139 and idx1052 — the S1-only arm still had two of the three as apron); KCLT's +129 becomes +3 adjudicated under the road limit (within_shape +131 → +5, same-law census both sides). SURVIVORS (S1-only arm, road limit): 31 new within_shape rows on ways -11715/-11729/-10588/-10570/-10524 at 8.36-43.37 % — a cluster just over the cap (8.4-9.2 %) plus genuinely steep terrain (16.8/17.7/19.9/43.4 %) the lot emitter never ramped. MISS 1 (no fix attempted, attributed): CYXY is NOT Δ0 — +23 adjudicated (23 transverse service_junction 3.6-28.7 %, 4 within_shape groundside 8.4-8.8 %); mechanism is the S3 KNOCK-ON pinned in the twin — the lateral-contiguity law absorbs a road only into a STRICTER neighbour, so road stubs beside lots are no longer absorbed into the ramp-limited lot and now show their own DEM-followed surface against their own 8 % cap (98 such rows at KCLT, 58 at KMCI). MISS 2 (no fix attempted, attributed): S1b alone adds 24 NEW ADJUDICATED AIRSIDE rows at KCLT (20 transverse junction 1.9-3.5 % on way -10123, 4 transverse apron 1.56-1.65 % on -11612) — both are newly WELDED ~117k m² plates where base/s1 had 22k m² pieces; the composed-plate transverse class, not a classification error. Neither miss is fixable in this lane's file scope (groundside.py / the weld). UNPAID: no in-sim look; no full suite; battery limited to KMCI/KCLT/CYXY; GROUNDSIDE_MAX_GRADE's SAME-LAW consumers (groundside.py's ring ramp-limiters at 1443/1461/1874/1881/1953, the lateral min() at 1567, the Lipschitz field at 3307+, and finalize.py:451's call into them) still target 5 % — stricter than the new cap, so lawful in the interim, and they belong to the lane that owns groundside.py; DIFFERENT-law consumers deliberately unchanged (FAN_RAMP_CAP + grade_graph, object_pads/grade_law pad-pull rate, route_profile/anchors band pricing, flat_fast_path Z0 proof, bridges transition law); auto_patch/CLAUDE.md's grade-cap parenthetical was already stale (says 4 %) and is left to its owner; scorer phase cost +3 % (KMCI 3.84→3.97 s) to +20 % (CYXY 1.25→1.50 s), far under the 2x tripwire, no timing claim made.
- 2026-08-12 lane/scorer AMENDMENT-1 FOLLOW-THROUGH (same-law limiters ride the road cap; RULINGS 2026-08-12 + lead direction): covering files once, ledgered — 11 files, 340 passed, 0 pre-existing failures; twins mutation-checked (alias pointed back at 5 % ⇒ 3 fail). Landed: config.GROUNDSIDE_PAVEMENT_MAX_GRADE (an ALIAS of SERVICE_ROAD_MAX_GRADE, identity-asserted) now read by the role table, the lot emitter's law seat + ring limiter (reseat pass and _dem_follow_polygon), _regrade_merged_host, the post-solve chord/Lipschitz limiter (default + inner bound), the lateral strictest-cap min, and finalize's log line. GROUNDSIDE_MAX_GRADE keeps the fan-ramp law, the band's off-route pricing, the object-pad pull rate and the below-grade TRANSITION law. MEASUREMENT REFUTES THE PREDICTION (KMCI + CYXY built before the consolidated-acceptance ruling; KCLT deliberately NOT built): the road-stub transverse class did NOT clear — KMCI transverse 101 → 101, CYXY 93 → 93, Δ0 against the a1 arm — because those shapes are service_junction, whose cap was ALREADY the road limit through ROLE_GRADE_LIMITS; the min() at groundside.py:1567 only loosens their SEAT, which is not what shapes them. COST: within_shape KMCI 420 → 490, CYXY 4 → 62; ADJUDICATED KMCI 1471 → 1546 (+75), CYXY 104 → 162 (+58). ATTRIBUTED: all 61 new CYXY rows sit on ONE lot (way -10268) at 8.08-10.36 %, i.e. 0.08-2.36 pp OVER the cap, with no declared-law override — the lots now ride AT their cap instead of being flattened to 5 %, and the emitted 2-dp quantization over short chords (plus the chord limiter's 4 sweeps) tips a family of pairs just past it. That is a limiter-vs-validator TOLERANCE defect, not a law error, and closing it means a safety margin below the cap — a design decision, so STOP-and-reported rather than invented here. The alias is a one-line revert if the owner prefers the 5 % shaping with the 8 % law. UNPAID: KCLT follow-through build + census (skipped per the consolidated-acceptance ruling — claims table in the lane report); no in-sim look; no full suite; MISS 2 (the 24 composed-plate transverse airside rows at KCLT) still stands, unowned by this lane.
- 2026-08-12 lane/scorer REVERT-TO-THE-MEASURED-WINNER (lead ruling on the follow-through STOP): the LAW stays the road limit (`ROLE_GRADE_LIMITS["groundside_pavement"]` = `GROUNDSIDE_PAVEMENT_MAX_GRADE`, the alias of `SERVICE_ROAD_MAX_GRADE`, identity-twinned); the SHAPE limiters in groundside.py go back to `GROUNDSIDE_MAX_GRADE` (5 %) — the lot emitter's law seat + ring limiter, `_regrade_merged_host`, the chord/Lipschitz limiter (default + inner bound), the lateral strictest-cap min, and finalize's log line. VERIFIED BY DIFF, NOT BY REBUILD: `git diff 5b9f7fc` over groundside.py / finalize.py / pavement_scoring.py is comment-only, so this tree IS the a1 arm and a1's measured numbers stand as the round's acceptance (KMCI ADJUDICATED 1471 vs the limiter arm's 1546; CYXY 104 vs 162; zero quantization-tip rows). Covering files re-run once, ledgered: 11 files, 341 passed, 0 pre-existing failures; mutation-checked (limiters re-pointed at the cap ⇒ 5 fail, incl. all three split twins). NOTE for whoever reads the fixtures next: the absorption preconditions (`stricter_lot_cap`, 5 classes across 3 files) STILL apply — it is the LAW that binds a road to a neighbour (station caps come from ROLE_GRADE_LIMITS = 8 %), not the shaping, so 5 % shaping does not restore road-into-lot absorption; the conftest fixture says so in its own docstring.
- 2026-08-12 SHIP-GATE OWNER ITEM (from the above): should the groundside SHAPING cap be raised to the ruled law with a MARGIN below it, instead of staying at 5 %? Measured cost of shaping AT the cap with no margin: CYXY within_shape 4 → 62 (61 rows on ONE lot, way -10268, at 8.08-10.36 % — 0.08-2.36 pp over, no declared-law override), KMCI 420 → 490, ADJUDICATED +58 / +75; the emitted 2-dp quantization over short chords plus the chord limiter's 4 sweeps is what tips them. A margin (cap minus a quantization allowance) is a design decision — owner's call, not an implementer's.
- 2026-08-12 lane/r18heca (R18-1 sub-cell INTERP_ALT seeding): ledgered covering files once (test_r18_subcell_seeding, test_r17_corridor_declaration, test_patch_obj8_anchor_sniff, test_r17b_coastline_wall, test_seawall_breaklines, test_harness — 275 passed); no blast-radius sweep for O4_Vector_Map.py, no full suite, and NO CONTROL TILE — the acceptance was cut short by a falsified premise (below), so the "one non-HECA control tile face count unchanged" arm was never run and the landed `seed_interp_alt_subcells` pass is proven only by its twin plus a measured no-op on +30+031. **THE SPEC'S MECHANISM IS FALSIFIED, MEASURED (STOP-and-report, not a skipped check):** on the current tree the seeding is already COMPLETE — the emitted +30+031 `.poly` arrangement over all 95,135 INTERP_ALT-bit segments yields 3,204 faces inside HECA's patch coverage and **0 of them are unseeded** (3,933 face seeds), the owner point's host face is a 281,554 m² apron ring that HAS a seed, and the new pass adds **0** sub-cell seeds. Yet the defect is present: mesh at 30.1170578,31.4098155 reads **98.05 m** (spec target 86–89) and the free-interior-vertex class is **54** at >3 m (17 at >5 m, 2 at >10 m; worst +11.37 m at 30.1289653,31.4007522; the recon's 99.33 m vertex is at 30.1166216,31.4099121, +7.69 m) — the recon's 89 has moved with r17b + R18-2, not with this change. The mechanism is in `O4_Mesh_Utils.post_process_altitudes`: for an INTERP_ALT triangle it assigns `vertices[6*v+2] = vertices[6*v+5]`, i.e. each vertex's OWN carried vector altitude — which for a FREE interior Steiner vertex is the DEM, not an interpolation of the enclosing patch ring. Seeding decides only WHICH triangles get that treatment, so no polygonize/seed change can move this class. The fix belongs in the mesh consumer / `.alt` build and is a different change from the frozen spec, so it stops here for Fable review (standing law: mid-implementation deviations are ruled, not decided). **Two corpus CONTAMINATIONS caused and reported:** `tools/run_tile_mesh_only.py` armed the write guard but never redirected the engine derived-cache roots, and the auto_patch ProcessPool workers (no guard) wrote 8 `Airport_mod_cache/*/o4_object_footprints_*.cache` sidecars (e.g. `CYXY Whitehorse/o4_object_footprints_+60-136.cache`) with `guard.blocked` EMPTY — the R18-2 cache-version bump 4→5 made every pack's sidecar stale, so first read rewrites it. Adding `build_airport.redirect_engine_caches` before the engine import cut that to **1** (`c_EGY - 100_airport - HECA Cairo (Tai Models)/o4_object_footprints_+30+031.cache`, written through the symlink-seeded overlay in step 2), still non-zero and still unauthorised. Owner action: regularise with `build_airport.py --refresh-data airport_mod_cache`. Artifacts: `<scratch>/tile_arm{,2,3}.log`, `<scratch>/free_vertex_class.py`.
- 2026-08-12 lane/r18heca (R18-1b free-interior altitudes, amendment 1): ledgered covering files once (test_r18_free_interior_altitudes, test_r18_subcell_seeding, test_mesh_degenerate_attribute, test_mesh_stop, test_mesh_write_atomic, test_mesh_sampler, test_post_mesh, test_triangle_plane_shared_vertex, test_harness — 317 passed); no blast-radius sweep for O4_Mesh_Utils.py, no full suite. CLOSING ACCEPTANCE BUILDS DROPPED per RULINGS `8537d9f` (consolidated acceptance, lead-owned) — the lane's claims are in the round report and the lead's single HECA tile build checks them. ONE attribution run was taken under that ruling's stated exception and is declared here: a steps-2-only mesh REPLAY on inputs already on disk (no auto_patch, no pack-cache work, `[guard] shared repo UNCHANGED`), because the discriminator this round turns on is only decidable against Triangle4XP's real vertex population — a unit twin cannot carry it, and attempt 1 proved it: the "the vector map authored it" discriminator protected HECA's hill (input node 138790, carried 99.33 m, all four incident edges DUMMY — an ORTHOGRID node), fixing 12,936 Steiner points while the hill did not move. **RESIDUALS, not claims:** the free-interior class does NOT reach 0 — it reads 49 at >3 m (from 54), 14 at >5 m (from 17), 0 at >10 m (from 2), and the owner's point reads 91.13 m against the amendment's 86–89 m band. Decomposed: 39 of the 49 WERE interpolated and still read high against the class metric, 10 were untouched (an isolated component, or a face the attr-scoping excluded). Two things the lane could not settle without more builds and hands to the lead: (a) the class metric itself is a PROXY — it compares a vertex to the mean of its 8 nearest patch nodes across ALL patch ways, so a vertex correctly interpolated from its own face's ring still reads high when those 8 nodes belong to a lower shape (a wall, a terrace, a road below); the recon's 89 and this round's 54 carry the same proxy, so "→ 0" may not be reachable by construction; (b) the pass is scoped to triangles whose attribute is EXACTLY INTERP_ALT, and 55,020 of the 67,143 free vertices it saw were in components holding no patch ring at all — if HECA's patch faces are being flooded by apt.dat APRON/TAXIWAY seeds (64/32) rather than the patch's own INTERP_ALT seed, the scoping is missing them and widening it is the next lever. Artifacts: `<scratch>/replay2.log`, `<scratch>/mesh_control.mesh`.
- 2026-08-12 lane/r18heca (R18-1c, the authorized scoping attempt): the APRON/TAXIWAY-seed hypothesis is REFUTED and the widening is NOT landed. ONE declared replay (steps 2 only, inputs already on disk, `[guard] shared repo UNCHANGED`) carried both the attribution probe and the widened arm: the owner point's own triangle came back with **attribute 8** — plain INTERP_ALT, already in scope — so seed identity was never the cause; and the widened arm (the whole `>= INTERP_ALT` set entering the solve) changed the interpolated set NOT AT ALL (12,123 free vertices either way; owner point 91.13 m, hill vertex 91.36 m, class 49/14/0 — identical to the decimal) while moving **49,717** vertices against the narrow scope's 11,960, 3,771 of them by more than 3 m and one by **32.19 m**, i.e. the apt.dat surfaces re-derived from patch rings for zero measured gain. Reverted to the proven narrow scope; the shipped `O4_Mesh_Utils.py` differs from the arm whose numbers are quoted ONLY in comments, so those numbers stand for the shipped code. The probe was temporary and is removed. Scope is now PINNED by a twin (`TestScopeIsPinned`) so widening must be a deliberate act that fails a test first. **The 86–89 m band is retired as MIS-ANCHORED, with the geometry:** the owner point lies inside exactly one patch shape, a 281,554 m² `apron` whose own ring runs 85.63–101.50 m; 85.63 is that apron's global MINIMUM, not its value here. The patch-ring nodes nearest the owner point are 90.93 m (97 m away), then 91.40 / 91.33 m, and every ring node within 200 m lies in 90.93–94.74 m. The mesh now reads 91.13 m there against a DEM of 98–99 m, i.e. it answers with its face's own ring value to ~0.2 m — which is the law "no vertex inside a patch face answers with DEM", satisfied. The free-interior class stays a REPORTING line per the lead's demotion (49 at >3 m, 14 at >5 m, 0 at >10 m, from 54/17/2).
- 2026-08-12 lane/sweeptools (BS1 sweep selection + BS2 base-arm artifact ledger, spec docs/specs/blast-sweep-and-artifact-ledger-spec.md): ran only the directly-covering files once, ledgered (test_harness, test_blast_index, test_artifact_ledger, test_run_with_ledger — 266 passed, 21 s, tree cdebf82ee4e5); no blast-radius sweep of the harness change and no full suite, per pre-ship mode. UNPAID: (a) the BS1 selection law's MUTATION recall is measured on ONE cheap sample (`auto_patch/strip_seam_law.py`, a 3-file sweep, 2 signal mutations, LAW recall 1.00, symbol-clause-only 1/2) — on a sweep that small clause 2 (cheap file ⇒ run everything) fires and the union degenerates to the full sweep, so recall on a LARGE sweep, where the symbol clause carries the selection alone, is UNMEASURED; the acceptance selection itself (`layout.py` `vertex_bucket`: 6 files of the 113-file full direct-importer sweep) was never judged by running those 113 files against a real mutation, and the tests that would have failed are asserted only by attribution. (b) `tools/blast.py` and the whole repo-root `tools/` tree are OUTSIDE the index's SCAN_ROOTS, so `--tests-for tools/blast.py` falls back wide and can never select `tests/test_blast_index.py` — the fallback line names it, but the selector cannot narrow a change to its own tooling. (c) BS2 store→serve is proven on ONE airport and one hit (CYXY, 63.3 s build then 0.3 s serve, patch/sidecar/frame byte-identical); the store's cross-lane flock under real concurrency, and LRU eviction against a real size cap on real 2.2 MB entries, are exercised only in twins with a synthetic store. (d) No timing arm: 63.3 s and 0.3 s are single runs quoted as orders of magnitude, never as build-time measurements (single-run wall times swing ±25 %). (e) The corpus stamp hashes the tile's base rasters and the airports layer but stamps inset DIRECTORIES by (name, size, mtime) listing only — an inset rewritten in place with identical size and a preserved mtime would not move the stamp.
- 2026-08-12 lane/r17c (round-17 amendment 2 — R17c-1/2/3): (a) NO full suite and no blast-radius suites for the three touched files; only the directly-covering tests were run (band/seed/flat-site/seawall/inset/corridor/mesh-sampler sets, plus the two new twins and the two promoted tools' twins), once, ledgered. (b) R17c-2 moves the flat-site synthetic raster's feather OUTSIDE the declared extent, which also moves the R11-2 datum RING off the site: VHHH's claimed-object cluster refusal (-10.82 m median) was re-read from this round's build log only — no sweep over the other flat sites (VMMC, ZGSZ, and the six owner-named airports) confirms their ring verdicts are unchanged. (c) `flat_fast_path.constant_core` still ERODES the declared extent by the feather; after R17c-2 the raster is exactly Z0 over the whole extent, so the core is now CONSERVATIVE (too small) — the fast path admits fewer shapes than it lawfully could, and R17c-1's refusal scope is correspondingly narrow. Not corrected here: widening it changes which shapes are born at Z0 on every flat site, which is a measured change this round did not budget. (d) The R17-2 declared CORRIDOR is still absent from the tile cfg (`flat_site_declared_corridors=` empty), so the corridor limbs of R17c-2 and R17c-3 are exercised by twins only, never by a build. (e) R17c-1's band-seed refusal is landed but the WRITER (`_build_eat_anchor_rect_pins`) is untouched, so the pinned nodes themselves remain below grade in the emitted surface — see the STOP report.
- 2026-08-12 lane/r17c (addendum, after RULINGS 8537d9f dropped the closing battery): (a) the R17c-1 band-seed REFUSAL is landed and twinned but NEVER CONFIRMED TO FIRE ON A BUILD — two instrumented VHHH runs printed no `[flat-core-seed]` line while the same function's `[below-grade-anchor]` printed, so "inert" and "line lost" were indistinguishable; production now states BOTH cases with a reason, and the lead's consolidated build is what settles it. Until then the VHHH band-membership move (245 -> 0 out-of-band rows, measured) is NOT attributed to R17c-1: R17c-2's DEM change is in the same arm. (b) R17c-2 and R17c-3 have NO built-tile evidence at all: the VHHH tile build was killed at the ruling, so no mesh transects (north shore lon 113.9200, west shore lat 22.3100), no `Seawall:` breakline count/length, and no island-land km2 — every R17c-3 number in the claims table is a PREDICTION, not a measurement. (c) VMMC/ZGSZ islands are predicted-only for the same reason; the VMMC and VHHH figures quoted (5 lines / 4,543.8 m of 12,780.3 m; 11 lines / 1,562.3 m of 20,873.7 m) are the PRE-R17c-3 patch-coverage admission, measured, and are the baseline the consolidated build should be read against. (d) the KCLT control was already complete when the ruling landed and is reported as already-run, not re-run; its arms are unmatched (r17b's was two merges back), so its one-node `tunnel-road-pin` 21 -> 20 delta is unattributed.
- 2026-08-12 lane/reprocut (the repro cutter, spec docs/specs/repro-cutter-spec.md): ran only the directly-covering file once, ledgered (`tests/test_repro_cut.py` — 23 passed, 2.4 s, tree 4bdca9377aef); twins mutation-checked 7/7 (weld ring dropped, R5 never refuses, mesh-side rail disarmed, DEM window keeps the full tile extent, an index-coupled sidecar key admitted, a 110 block stripped of its node rows, the tile rail ignoring the margin). No blast-radius sweep, no full suite, no airport build (the demonstration runs the FIXTURE only), per pre-ship mode. **THE ACCEPTANCE DEMONSTRATION MISSED — no pin REPRODUCED, STOP-and-reported at the attempt cap.** The extraction, the manifest, the pin contract (R5: every pin re-measured on the source artifact before the fixture is written), the refusal rails and the runner all work end-to-end and every `--run` reported `[guard] shared repo UNCHANGED`, but auto_patch is NOT LOCAL and the fixture's numbers are not the artifact's. Two site classes, three radii, all at KCLT against the shipped `+30-090/+35-081/KCLT_auto.patch.osm` (sha 743047c5, engine 1.50.1681): (a) the groundside `service_junction` transverse cluster @(35.20342,-80.94468) r=300 m — pinned worst 3.3595 m / 39.023 % and count 33 — produced ZERO rows in the fixture; role census `service_junction` 383→2, `object_pad` 571→0, `groundside_pavement` 37→1, i.e. the road-feed / lot / pad chain needs airport-wide context a disc does not carry (the road feed itself was live: 2,500 road ways from the sidecar cache, but only 32 centerlines touched the sliced pavement). (b) the airside runway-end strip @(35.22581,-80.93661) — pinned `strip_arc`/`strip_longitudinal` worst 1.25 m / 13.1078 % — DID fire at the site but at 0.52 m / 8.8084 % with `strip_arc` count 5 vs 2 (r=250 m, 137 s); widening to r=700 m moved the class further away (no row within 3 m of the pin site, count still 5) and cost 251 s. ATTRIBUTED: `graded_strip` 482 (source, 3 runways) → 100 (fixture) — a strip is subdivided by the ADJACENT PAVEMENT the disc cuts away, so a fixture strip piece is longer and its interior grades differ; the same mechanism in the groundside arm. UNPAID / open: (a) no pin REPRODUCED on a real site, so the spec's acceptance is NOT met and the tool must not be used as a fix-loop oracle until the locality question is ruled — a DIVERGED verdict is currently the expected outcome; (b) the wall time is 137-251 s, not the spec's "seconds to ~1 min"; (c) the `--run` twin (a full build from a checked-in fixture) is not in the suite — it needs the install and minutes, so the pin loop is twinned at the measure/verify level only; (d) the OSM inputs are carried as a READ-THROUGH SYMLINK OVERLAY of the corpus tiles plus a manifest pinning each referenced file's size+mtime (`--copy-osm` copies them instead) rather than a geometric OSM slice — a re-emitted OSM would drop multipolygon relations, which is strictly worse, but it is an interpretation of the spec's "OSM slices", flagged not decided; (e) the reference slice keeps the SOURCE anchor rather than re-anchoring (axes/routes are anchor-relative metres, so re-anchoring would invalidate the census context the fixture exists to carry); (f) `--copy-osm`, `--allow-degraded-dem` (R8) and the R3 multi-artifact refusal are implemented but never exercised on a real corpus state; (g) the DEM window's `alt_strict` answers NODATA outside the window by design — twinned, but no measurement of what a build does when a pass reaches past the margin.
- 2026-08-12 CONSOLIDATED ACCEPTANCE (lead-owned, RULINGS 8537d9f): riders KSTJ/KMCI/KCLT/CYXY rc=0; tiles VHHH/HECA/OTHH steps 1-2 complete, each stopping at the expected step-4 corpus guard (no shared-repo write). VERIFIED: KSTJ un-dropped (5/18 EAT pins refused); KMCI census 1471 = scorer claim; VHHH canyon GONE (202-sample axis transect, 0 sub-zero; was −11.75/31), corridor LAND at 7.32 walled, north shore Z0 to the edge, Seawall 12 breaklines/54,335 m island-scoped; HECA hill 91.105/91.335 m = R18-1b claim (cone gone), HECA emits ZERO EAT pins (the −15 m ratification item measured ABSENT); KCLT EAT reference pins 11 pinned 0 refused (guard risk item closes benignly); OTHH tile mesh clean through step 2 (r16 mesh-replay debt paid, no crash class). ATTRIBUTED EXPOSURE: KCLT adjudicated 459 vs scorer-frame 382 — the R18-2 evidence gate's FIRST measurement at KCLT (115 rings refused, 41 OSM footprints in evidence; ground under former phantom pads now judged groundside, transverse 299/252-groundside) — the standing exposure class, owner-sim adjudicates. VHHH canyon cleared via the SEAL, not pin refusal ([eat-anchor-rect] 38 pinned unrefused — no route path binds them; [flat-core-seed] inert): the phantom-EAT scoping ratification stays open with VHHH as second exhibit.
- 2026-08-12 lane/r17d (round 17d — the unroutable-EAT law + connected-island walls): ran the `blast.py --tests-for --since 4ca0d96` selection ONCE through `run_with_ledger` (66 files, symbol-attributed 2 / cheap-file 14 / fallback-wide 66). Attribution builds only, all `--patch-only --no-ledger --no-artifact-ledger`: KCLT (885 s) + VHHH (1,094 s) + KSTJ (100 s) report-only arms, and ONE KSTJ arm under the landed law (42 s, body sha 70eb39d813a7 = the report-only arm's, byte-identical). UNPAID: no VHHH or KCLT arm UNDER the landed law — VHHH's claimed 38-pin refusal and the 07L/25R transect are asserted from the report-only route diagnostic plus the twins, never from a built patch, and belong to the lead's consolidated arm; no census on any arm; law 2 is measured on the owner's artifact through production's own readers (`coastline_wall_admission`/`seawall_breaklines`, real OSM coastline + the 09:06 patches) with the cluster extents supplied from `flat_site_mode`'s own cluster function rather than from a DEM bake, so the +7,832 m of wall is a geometry read, not a rendered tile — the in-sim pass on the east island's edge is the acceptance; the cluster-datum refusal is not reproduced in that read (it does not have to be: the refused 0.1255 km2 cluster is not stamped and so cannot enter the reading); build-time impact of either law unmeasured (timing gates suspended) — both are O(graph) traversals over sets already built.
- 2026-08-12 lane/r19heca (Round 19 — HECA seats + instrument honesty, spec docs/specs/round19-heca-seats-and-instrument-spec.md): per-law test files run once and ledgered (R19-5 288 passed; R19-1/R19-3 401 passed 2 skipped; R19-4 725 passed; R19-2 154 passed), blast --tests-for quoted per commit. TWO declared in-lane HECA `--patch-only` arms (r19arm2, r19final), both rc=0 with the shared repo UNCHANGED. MEASURED: the instrument fix is exact on the owner's artifact (same patch, both frames — LAW-TRUE 5180 → 5197, within_shape 1881 → 1898, worst |de| 10.05 → 12.60 m: 628 ring edges re-entered the domain, 17 of them violations); walls `authority_retreat_wall` 56 → 0 with 32 feather faces. UNPAID / OPEN:
  (a) R19-1 took THREE mechanisms, all measured, all on the record. (1) LIP-RUN WALK (bounded reach, PAD_HOST_BODY_REACH_M 10 m): fires (21 pads) but MISSES building114 in arms r19arm2/r19final/r19a2 — it emits 88.51 throughout, because the apron's body sits 16.59 m out. (2) HOST-SURFACE FIELD SAMPLE (no reach, inverse-square over the host's pad-free vertices): arm r19field rc=0, 62 pads moved, building114 -> 90.26 (still a MISS) and the 15,298 m2 building112 was DRAGGED off its host level 85.63 -> 86.45 — the host's own pad-free vertices near that pad start 118.01 m away (87.03/87.04), and 53% of HECA's 214 pads have no pad-free host vertex within 25 m, so "the host's own surface" is a remote reading exactly where the pads are. (3) LEVEL FAMILY + AGREEING COALITION (lead ruling, R12 amendment-4 idiom reused with area weighting): owner-artifact replay gives the ruled claim — building114 88.50 -> 85.63, building189 86.27 -> 85.63, FIVE pads move in total, building112 unmoved. PRODUCTION (arm r19fam, rc=0, 380.7 s, shared repo unchanged): the pass moved FOUR pads and building114 was not among them — it still emits 88.51, and the 14 building|building rows on -10189 are still 14 (worst 2.88 m). SO ALL THREE MECHANISMS MISS IN PRODUCTION WHILE THE THIRD IS EXACT ON THE ARTIFACT, and the arm says why: the level family is an EMIT-TIME structure. In the emitted patch building114 chains to 189 and 189 to 112/113 — the family the coalition needs — but ``relevel_pads_to_host_pavement`` runs POST-SOLVE, PRE-EMIT, and the shared ring vertices that chain them are written later by the weld/conformance passes. Only 11 of 214 pads share a host vertex with another pad even in the emitted frame. This is one root cause behind all three misses (the contact radius, the bounded walk and the field sample each read a layout ring that does not yet look like the emitted one), and it is the owner's call: either the pad law moves after the welds, or the family is derived from the weld candidates rather than from ring vertices. R19-1 SHIPS AS KNOWN-OPEN per the lead ruling; the twins (16, three ruled properties each mutation-bound), the 843-test ledgered sweep and the artifact replay (114 88.50 -> 85.63, 5 pads, building112 unmoved) are paid. Honest-instrument census of the arm: LAW-TRUE 5522, airside_for_acceptance 1657.
  (b) R19-3 has NO production instance in the current tree — the artifact's `object_pad:56` (105.51 m beside a 93.5 m apron) is not emitted here; the nearest object pad to that site is 660 m away. The law is twinned only.
  (c) R19-4's feathers are mostly NOT within their caps: 32 faces, median band ~2.7 m, rises to 5.18 m, and 378 census rows touch them. That is the ruling's own trade ("tight spots get steep slopes, never walls") making previously wall-hidden steps visible — the owner's relief-generation round owns the residual. `groundside_terrace_wall` also went 2 → 25 at HECA (a DIFFERENT emitter, outside this round's scope and still non-carve under the same ruling).
  (d) R19-2's production effect is a single arm's log line, not a census claim; the round changed no other airport's gap-fill and no battery was run.
  (e) Cross-tree caveat: the arm censuses (5658) are NOT comparable with the owner artifact's (5197) — different trees. Only the same-patch instrument A/B is attributable to this round.
- 2026-08-12 lane/r21land (Round 21, spec round21-land-connected-continuity-spec.md): (a) ONE declared interventional +22+113 steps-1-2 arm was run (lane-local build dir, the owner's tile cfg copied WITH its now-retired `flat_site_declared_corridors=` line, which warned and loaded); no acceptance battery, no census, no second tile — the lead's consolidated arms own that. (b) The arm's mesh was built with the PRE-BAND code: the datum band (see the commit "R21 law 1 amendment") landed after it, verified at the DEM level by re-running production's own DEM prep (`compose_tile_dem_from_disk`, write_alt_file=False, guard armed, shared repo UNCHANGED) and by twins — NOT by a second mesh. The only ground it changes is VMMC's isthmus (729 of 9,538 mask posts now keep the real surface); VHHH and ZGSZ are unaffected either way (no isthmus at either). (c) The HECA/mainland control is STRUCTURAL plus one measured probe on real data (ZGSZ's mainland component on +22+113 refuses by the frame test in the arm's own log); no HECA build was run. (d) The `blast --tests-for` selection (46 files, 44 after the two converted-away corridor twins) ran once through the ledger: 1,066 passed, 6 failed — all six PRE-EXISTING at base ab0c1c8, verified in a matched control worktree at that commit. (e) The cluster-admission simplification was MEASURED (fixpoint vs land-component: identical admitted sets at VHHH/VMMC/ZGSZ) but NOT landed — see the STOP report; the r17d fixpoint stands unchanged.
- 2026-08-12 lane/hguard (the OVERLAY WRITE-THROUGH law, both halves: `mirror_tree_as_overlay` seeds copy-on-write and `SharedRepoWriteGuard._violation` judges the RESOLVED path): ran only tests/test_harness.py once through the ledger (204 passed; `blast --tests-for` SELECTED 0 test files for both harness modules — they are loaded dynamically, so the index records no importer, and test_harness.py is the covering file by construction). ONE declared verification arm: a CYXY `--patch-only` build (37.6 s, rc=0, `write_guard_blocked: []`, shared repo UNCHANGED, overlay seeded 1131 cloned / 0 copied / 149 dirs). UNPAID: (a) the arm's airport has NO third-party pack, so NO mod-cache write occurred during it — that a production write lands lane-local is evidenced by the twins and by a post-arm replay of the writers' own `open(path, 'wb')` against the arm's real overlay entry for `OTHH Doha (Aeroscape)/o4_object_exclusions_249b20f913dfbb8b.cache` (one of the seven rewritten on 2026-08-12: guard.blocked==[], shared file byte-identical incl. mtime_ns), never by a build that actually rewrote a sidecar; (b) no OTHH/KMCI rebuild reproduced the three measured incidents under the fix; (c) the clonefile path is macOS/APFS and same-volume — the `shutil.copyfile` fallback is exercised by NO test and by no machine here (1131/1131 cloned), so a cross-volume lane would pay a real 22 GB copy nobody has measured; (d) no full suite, no census, no battery, no build-time arm — the seeding cost (0.10 s, ~420 KB real disk for 22 GB apparent) is measured standalone, not inside the 60 s per-airport budget; (e) STALE PROSE left for the owner/lead: `docs/RULINGS.md` (the e9daef5 corollary still says "symlink-seeded" and names `mirror_tree_as_symlinks`), `docs/specs/suite-corpus-clean-spec.md`, and `tools/classify_report.py`'s comment — all outside this lane's file scope; `tools/repro_cut.py` still calls the deprecated alias.
- 2026-08-12 lane/hguard (#15 overlay write-through; merged dc9a66e): 4 new guard tests + a 30-test subset green in-lane (pytest cache 12:52); NOT re-run on merged main (base moved by a STATUS-only commit — code byte-identical). UNPAID: full test_harness sweep on main; repro_cut.py's 4 call sites still on the deprecated `mirror_tree_as_symlinks` alias (forwarding line kept deliberately).
- 2026-08-12 lane/t10twin (task #10, spec task10-twin-ring-presplice-nid-spec.md + Amendment 3; merged f0abd19): ledgered runs t10-diag-tests (23 passed) + t10-a3-tests (85 passed, 8 files). Declared arms: OTHH + KCLT --patch-only before/after, all rc=0, shared repo UNCHANGED. MEASURED: pairs OTHH 21→0 / KCLT 4→0 (owner artifact 24, tile frame, for the record); sub-micron 0; census family tables byte-identical both airports; body sha OTHH 28a61f8bc880→4ecaaa5ac1be, KCLT 72177a9e0315→6976027dbf9d. Fix shape (i) refuted-not-attempted (same_spelling 771/791); attribution instrumentation KEPT. UNPAID: rc=0 Triangle mesh replay on the fixed patch; emit_decimate.py (shape-level, 32,689 vertices at OTHH) NOT audited for the same one-sided frame; KCLT's 2 unowned tunnel_roof wall nodes pre-existing, unattributed; OTHH 15 beyond_frame + 5 gate_share rings (worst 139.09 m, role=building) not the twin class, unattributed.
- 2026-08-12 lane/t11vouch (task #11, spec task11-r18b-vouching-scope-and-band-remedy-spec.md; merged ae6e947): 109 passed ledgered (dsf_object_buildings + object_pads). PHASE 1 CONFIRMED: scoped predicate moves the flex law line (drained 428.86→349.84 m); anchors surface-lawful, hard-seed population identical (736); pair 05C/23C 110.610 vs 05L/23R 61.280, law spread 49.6353 over budget 47.5591 = 2.0762 short, 680 nodes. PHASE 2 STOP: relax lever measured INERT (relax allowed 0.000 m both arms, 0 minted anchors; 40-round arm made it WORSE 680→752). Substitution PARKED default-OFF (O4_DSF_OBJECT_NAME_VOUCH_SCOPED); wide predicate kept beside evidence_name_vouches until the band remedy lands (ONE-implementation ruling deliberately broken while parked). Controls scoped-ON all byte-identical: CYXY 07321502759a, KSTJ 70eb39d813a7 (0 inversions), OTHH 28a61f8bc880 (0 of 13,863) — HECA is the only airport the substitution moves (Tai Models pack) and the only refusal. UNPAID: the band remedy itself (owner-visible design round: what authors the 05L/23R law half; whether lawful-sag seeding / O4_BAND_SEED_COMPLETE changes the joint outcome); HECA rings 817→210 + pads 215→73 ship only when the gate flips ON; OTHH pad adjudication (unchanged, patch byte-identical).
- 2026-08-12 lane/t16pad (task #16, spec task16-pad-host-emit-frame-spec.md + Amendment 1; merged 0200452): coalition branch re-landed clean (63 twins green incl. R12 byte-unchanged); 138 passed ledgered across 7 covering files; R17 last-author guard untouched-green (relevel-before-_seal_band pinned by a new twin). MEASURED (arm t16a2, HECA --patch-only, late projection ON, rc=0, shared repo UNCHANGED): building114 88.50→85.63 (85.59 pre-projection host value also quoted), building189 flat 85.63, building112 byte-identical, ring −10189 building|building 14→0 (corpus 23→9), swap class identical-to-control; census LAW-TRUE 5505→5576 (+71 = 89 NEW apron|apron rows − 18 GONE) RULED newly-legible per RULINGS 2026-08-07 exposing-pre-existing (geometry byte-identical except the six intended nodes; 89/89 new rows anchor within 1 m of them). Weld-relation index measured seed-identical to contact-radius at HECA (the lever was the late projection, not the relation). UNPAID: apron −10629's own ~11 m spread (relief-round territory); weld-candidate enumeration +0.76 s/build (4 calls; ABOVE the 0.6 s tripwire — profiling round adjudicates); no --tile arm; building146 100.05→100.66 vs owner 08:54 baseline present in BOTH arms (r20/r21-or-coalition, unattributed); O4_PAD_FAMILY_DEBUG probe + pad_levels.py scratch (second use → promotion-eligible).
- 2026-08-12 lane/maskredir (lane-local mask routing, spec lane-local-masks-spec.md; merged): test_harness 212 passed + 5 mask-consumer files 52 passed, once, ledgered. Acceptance smoke: the refused HECA tile arm re-run rc=0 all 4 steps (881.1 s wall under nohup/E-cores — upper bound, not a timing), masks overlay 3 cloned/0 copied (0.3 ms; whole-root fallback 19 ms/173 files), cleanup deleted lane-local clones only, shared rasters byte-untouched, write_guard_blocked=[]. FINDING recorded: pre-fix the legacy cleanup would have DELETED shared masks without rebuilding (dico_sea empty in this frame) — the guard was preventing corpus loss. UNPAID: no coastal-tile arm (step-3 cost on a real masks tile unmeasured); no second airport; conftest deliberately has NO masks redirect (suite mask writes still fail their own test — existing design); HARNESS GAP: fresh lane build dirs lack per-tile cfg ('EMPTY default_website' refusal) — lane seeded a byte copy of the owner's tile cfg; next tile lane hits the same wall (harness item).
- 2026-08-12 lane/cfgprov (per-tile cfg provisioning, ruling 'lane inputs provisioned by the ritual'; merged): test_harness 218 passed once, ledgered; acceptance via gate dry-run (provisioned e10f710e96b9, gate passes on a fresh dir; 0.157 ms cold) — no tile build spent. Canonical source = main-tree Tiles/zOrtho4XP_<tile>/ cfg (data-repo app cfg structurally lacks per-tile vars, verified). UNPAID: run_tile_build.py / profile_tile_build.py still read whatever cfg exists — route through provision_tile_cfg if lanes adopt them; no full-tile arm.
- 2026-08-12 lane/corridor (service-corridor round, spec service-corridor-round-spec.md + Amendments 1-2; merged 7e33b34, SHIPS ON per owner ship ruling 1.0.244): 536+541+504 tests across the three passes, ledgered. MEASURED MET: KCLT ramp corridor surfaced end-to-end (coords 2/3 carry service_road/-junction; wall -12626 GONE, walls 12→0; free end reaches DEM); HECA corridor A axis coverage 618.2/618.2 m zero gaps (was 4 disjoint axes + two gaps), corridor B 519.2 m chain (was none); Amendment 1 killed the trigger teleport (building211 77.43→76.59; airside +252→+130); Amendment 2 band exclusion landed (correct law, measured inert here — 4 pairs refused; the −65 knife was consumer-side on the pre-A1 tree); KCLT/CYXY byte-stable across all three passes (ef4c51b860b6 / 3860ec271c6a). DISCLOSED SHIPPED REGRESSION (owner-accepted): HECA airside +130 adjudicated — solve-stage values on unchanged rings (39 shapes gain rows, 27 worsen worst |de|, apron -11906 0.86→5.69 m; identity-joined per-shape table in the lane report) + ONE new strip_seam_tear 1.21 m (ways -12995|-13028, both pieces new-in-arm). STAGED-SOLVE ROUND owns: the residue, the tear, the corridor profile law (hump/pockets/±8% NOT met), groundside grade-to-DEM inflation (relief round), OTHH/KSTJ corridor effects (consolidated arm quotes them, in-lane unmeasured). Promoted: corridor_axis_coverage.py, arm_site_read.py (INDEX'd, twinned).
- 2026-08-12 lane/padseat (pad seating + rim pockets, spec heca-object-pad-seating-spec.md + Amendment 1; merged 11468ed, rim pockets DEFAULT-OFF): 198 twins ledgered ×3 passes. SETTLED: owner's pad NOT re-requested (corpus-history; seat key only in the owner artifact's emitted section; requests 851 owner/842 lane — the divergence is the standing data-vs-product owner question, interim law tile-frame-only); weld-prediction VINDICATED (cut-back frame seeds + adopts 105.51→93.45); ruling 2 already satisfied (relief cap is a trigger, not a magnitude cap — twins pin it); pad-clip/spine-parent/supersession all REFUTED offline; OTHH absorption knife DECISIVE (post-solve-only: airside 29→9, cluster 23→6, better than baseline) but HECA third channel WORSE (closing row-diff: 1,238/1,330 new airside rows off-face, median 63 m, up to 11.31 m) ⇒ rim pockets ship OFF (byte-identity: structural proof + padseat_default_check hash vs 4ecaaa5ac1be in /tmp/harness/padseat_BYTE_IDENTITY.txt). Knoll fix (mesh 106.3→93.72, no walls) PARKED with the code. STAGED-SOLVE ROUND owns: absorption architecture, HECA off-face channel, 6 residual OTHH rows, HECA tile-frame strip_seam_tear ×7 (cleared of ruling 3 by the OTHH control). Also deferred: enclosed-MRR over-report; _PAD_HOST_ROLES widening (~0 movement); rim detection +2.2 s/build (memoization untried); engine finding O4_Mask_Utils.py:427-434 swallows refusals (routing fixed by maskredir; the except itself narrowed there).
- 2026-08-12 lane/joins (corridor-joins round, spec corridor-joins-round-spec.md; merged): 426 tests ledgered; twins 28 new + 12. MEASURED MET: KCLT free end 6.31 m proud → −0.01 m (transect 2.22 m/40 m, no cliff); seam welds all airports (KCLT mouths 96→99, max seam Δalt 0.010 m = floor residual; HECA 129→139 @0.000; CYXY conflict walls 3→0); owner's site-1 wall GONE (keepout refusal) + welded mouth at the real crossing 26 m away (2 shared nodes, Δalt 0.00, airside values byte-identical); censuses adjudicated KCLT 1403→1080, HECA 8219→7416, CYXY 324→245, KSTJ 54→54; build times IMPROVED (KCLT 550→478 s, HECA 671→562 s recorded-phase direction; CYXY exclusive A/B 40.05 vs 41.91 s). DISCLOSED: HECA worst airside row 11.31→11.36 m (+0.05, knifed to the mouth-join change via nomouth/nofree gate arms; net airside −61) — staged-solve docket; KCLT airside strip_seam_tear +22 (worst 7.18 m; 8/26 near the two refused stacked-conflict walls — ruling-2 fallback, walls→bare steps; grading those transitions = staged-solve/relief docket); over-slack free ends 6/36/2/1 per airport (≤1.4 m, p90 ≤0.10 except KSTJ 0.450) unattributed. Spec premise corrected: site-1 control gap was 11.221 m (graded_strip abutment), not 0.999 — mouth law fired at the actual crossing. UNPAID: full suites, tile arms, in-sim.
- 2026-08-13 lane/perfcache (perf P2 Lane A — the LANE-PERSISTENT derived-cache root, spec perf-p2-instruments-and-cache-spec.md): tests/test_harness.py run ONCE through the ledger (221 passed, 3 new twins; `blast.py` selects no test file for the harness modules — they load dynamically, test_harness.py is the covering file by construction). FOUR declared interventional arms, all `--patch-only --no-ledger`, all rc=0 with the shared repo UNCHANGED: HECA miss 549.2 s / hit 486.0 s, OTHH miss 955.2 s / hit 531.7 s; every body sha equals the FROZEN 1.0.245 baseline (HECA f562cbfeb8f9, OTHH 75594bc8773a) on BOTH the hit and the miss arm. Attribution: the drifting fingerprint component is the pack `.obj` STAT BLOCK, not the gate constants or the cache version (brute-forced: version 0-11 and 25 gate/epsilon variants all miss the stored digest) — the owner's app wrote HECA's shared sidecar at 07:03 and its own Phase-2 y-bake rewrote 376 of 568 `.obj` at 07:14, so a run invalidates the sidecar it just wrote; branch (a), the components differ LEGITIMATELY (content really changed) and the fingerprint is untouched. UNPAID: (a) the 4 arms are single runs, NOT `--runs N` — the wall deltas are quoted beside the phase-time attribution (`Assembling pavement & runway shoulders` 66.82->1.38 s HECA, 419.11->1.19 s OTHH) which is the robust number, and ANOTHER SESSION's HECA build finished at 08:28:43 overlapping our HECA hit arm, so 63.2 s is a floor not a point estimate; (b) no census on any arm (byte-identity to the frozen baseline is the stronger gate and it passed); (c) no KCLT or CYXY pair, no `--tile` arm, no full suite; (d) CONCURRENCY: two builds in ONE lane now share one derived root and the engine's sidecar writers truncate in place — the per-DSF lock is in-process only, so a same-lane parallel pair could interleave a sidecar write; unmeasured, mitigated only by the fingerprint (a torn sidecar fails to load and recomputes); (e) STALENESS: a lane clone now shadows a later shared refresh forever — argued safe because every artifact under the root is content-keyed (input fingerprint / DSF hash in the file name), never measured against an actual `--refresh-data airport_mod_cache` sweep; (f) the seeding cost of the now-mostly-warm overlay (1132 files) is unmeasured inside the 60 s budget, as before.

- 2026-08-13 lane/perfinstr (perf P2 instruments, Lane B items 1-4): tests run ONCE through the run ledger and no full suite (PRE-SHIP MODE). tests/test_solve_capture.py 12/12, tests/test_census_cache.py 22/22, tests/test_run_with_ledger.py + tests/test_profile_tile_build_refusal.py 14/14. NOT run: blast-radius sweeps for pipeline.py (72 direct importers) and for census.py / build_airport.py; the 28 pipeline-importing test files; tests/test_harness.py beyond `-k census` (10/10). The solve-boundary split is covered instead by the acceptance the charter names — the frozen 1.0.245 body hashes reproduced byte-for-byte at CYXY and HECA (build AND replay arms) — which exercises the whole emit path the unit twins cannot. STILL OPEN: (a) `tools/solve_cut.py --census` refuses in v1 (census the replayed patch through the harness entry instead); (b) `--solve-capture` is refused with `--tile` rather than wired (a tile build captures by arming O4_SOLVE_CAPTURE knowingly); (c) the capture pickles the tile DEM handle whole rather than a cropped window — untested, since the airport path carries tile_dem=None; (d) no timed claim of any kind is made for any of the four instruments (single-run walls swing +/-25%; the replay walls quoted are frame facts, not speedup claims); (e) census cache byte-identity verified on the twin fixture and one real patch (HEAZ), no multi-airport arm; (f) no end-to-end profile_tile_build.py run against a real tile — its refusal and ordering are twinned statically only.

- 2026-08-13 lane/perfsidecar (perf P3 — the pack-footprint sidecar keyed on PRISTINE inputs, owner ruling 2026-08-13): tests run ONCE through the run ledger (PRE-SHIP MODE) over the five covering files — test_object_rebake.py, test_dsf_object_buildings.py, test_dsf_object_pavement.py, test_object_bridge_terrain.py, test_post_mesh.py: 346 passed, 10 new twins. A SENSITIVITY ARM (the pre-ruling live-stat key restored in one line) failed exactly 6 of them and left the two miss-twins green — the twins are proved sensitive to the fix and the external-edit detection is proved unweakened. ONE HECA pair, `--patch-only --no-ledger`, fresh LANE-PERSISTENT cache root, sequential and exclusive, both rc=0 with the shared repo UNCHANGED: run 1 total 627.9 s with `Assembling pavement & runway shoulders` 75.95 s (the EXPECTED one-time re-key — HECA's pack carries 385 `.anchor_bak` originals, so the pristine digest differs once from the stored live-stat digest), run 2 total 530.5 s with the same phase at 1.88 s; body sha equals the FROZEN 1.0.245 baseline (f562cbfeb8f9, 3887 shapes) on BOTH arms. UNPAID: (a) the pair is TWO SINGLE RUNS, not `--runs N` — only the phase-time line is quoted as the number, the ~97 s total delta is a floor; (b) NO TILE ARM, so the bake-invariance itself — the thing the fix is for — is proved by the twins and the mechanism (the readers already load geometry from `.anchor_bak`, ruling R1) and NOT end-to-end: a build→bake→build tile pair at HECA or OTHH is the missing acceptance; (c) no census on either arm (byte-identity to the frozen baseline is the stronger gate and it passed); (d) no OTHH/KCLT/CYXY arm, no full suite, no blast-radius sweep of `object_rebake`'s 17 importers or `object_terrain_assembly`'s 21; (e) the fingerprint now costs 0.386 s on its FIRST call per process at HECA (sha256 of 385 baked live files, 750 MB, plus one 31 MB provenance parse) and 0.005 s after — measured on the owner's pack, not inside a build, and never with `--runs N`; it is 0.6% of the 60 s airport budget, below the 1%-of-budget review trigger, and unmeasured at OTHH; (f) the classification sidecar (`object_terrain_assembly`) was moved onto the same key by the same one-implementation call — sound by the same ruling-R1 argument and twinned, but its own recompute cost was never separately measured, so no saving is claimed for it; (g) the pavement sidecar shares the helper and therefore the pristine key: argued safe because a file with a backup has solid geometry and `_is_pavement_object` refuses it, never measured.
## perf P3 lane D (lane/perfsolveD, 2026-08-13)

Optimisation-only lane: `grade_graph.shape_constraints` /
`_spine_membership` / `_spine_crossing_predicate` and
`elevation._drop_overlap_against_fixed_shapes`.  Every change is a
semantics-identical transformation and the acceptance was the perf
phase's byte-identity gate: HECA and CYXY solve-stage replays reproduce
`baselines/1.0.245/MANIFEST.txt` exactly (`f562cbfeb8f9`, `61efa43c3aeb`).

DEFERRED (pre-ship mode): the blast radius was NOT swept.  `blast.py`
names 42 importers / 25 test files for `grade_graph.py` and 63
importers / 21 test files for `elevation.py`; only
`tests/test_grade_graph.py` (incl. 4 new equivalence twins) and
`tests/test_road_feed_in_graph.py` were run.  Also deferred: KCLT /
OTHH / KSTJ replays (only the two captured airports were checked
byte-for-byte) and any census — no census was run because no body
changed.
- 2026-08-13 lane/perfsolveC (perf P3 Lane C — ACTIVE-ROW COMPRESSION in `one_solve._project_chromatic`, spec perf-p3-solve-sinks-spec.md): tests run ONCE through the run ledger (157 passed: the 9 projection suites `blast.py` names plus the new `tests/test_projection_active_row_compression.py`); no full suite, no blast-radius sweep of one_solve.py's 28 importers (PRE-SHIP MODE). Acceptance is the charter's: both frozen 1.0.245 body hashes REPRODUCED by full solve replays — HECA f562cbfeb8f9, CYXY 61efa43c3aeb — plus raw-float64-byte equality of the solved field on six captured `_project_chromatic` calls. Exclusive matched wall pair, back-to-back in one window, zero interlopers before and after each run, `--run-one` per run (BASE = HEAD~1's one_solve.py in the same worktree): HECA 464.0/468.1 -> 443.9/438.1 s (median -25.1 s; solve phase 310.1 -> 286.4 s), CYXY 39.6/40.1 -> 38.6/38.7 s (median -1.2 s; solve phase 30.2 -> 28.8 s). UNPAID / OPEN:
  (a) THE LANE MISSED ITS -40 s FLOOR. Measured ceiling: `_project_chromatic` is 82.8 s of HECA's 417 s replay (wrapper-timed, 21 calls), so the floor needed a 48 % cut of the sink; the delivered cut is 33 % (-30.0 s on the replay, -25.1 s on the whole build). What is left is the MANDATORY full-width residual — the `z[IJ]` gather and `abs(d) - B` over every row of every colour every sweep — and three attempts to make it sparse were measured and REFUTED, not skipped: block-level dirty tracking (385 of 420 colour parts have a moved endpoint every sweep), edge-level worklist with node timestamps (the int32 stamp gather costs as much as the float64 value gather it would avoid: 13.7 vs 14.6 us on a 9,710-row colour), and sorting the box/endpoint columns for locality (the gather was never the cost). The remaining transforms all trade on a NaN premise (`(over > tol).any()` for `over.max() > tol`, `maximum(above, below)` for two masks) or on reordering rows, and were STOPPED per the spec.
  (b) No census on any arm; byte-identity to the frozen baseline is the stronger gate and it passed at both airports. No KCLT / OTHH / KSTJ replay or build, no `--tile` arm.
  (c) The BEFORE replay profile (425.1 s) was taken while lane D ran a HECA replay; the AFTER (395.1 s) was not. The -30.0 s replay delta is therefore a CONSERVATIVE floor read, and the exclusive matched build pair (-25.1 s) is the number to quote.
  (d) `_column_last_write_mask` is built per colour per call (one stable argsort of each repeated endpoint column). Its cost is inside the measured arms but was never isolated; on a graph whose colours are almost all repeated it would be paid on every call.
  (e) The negative-zero gate's INVARIANT half (a field free of -0.0 stays free of it under `a ± b`) is argued from IEEE-754 round-to-nearest and twinned only by a fixture that SEEDS -0.0 and checks both paths agree; no test drives z to a -0.0 mid-sweep, because the argument says it cannot happen.
  (f) `tools/profile_airport_build.py --replay` has no twin: it is exercised by the three profile runs this lane took. Its INDEX row now carries the GIL-scheduling caveat this lane measured the hard way — the sampler priced the box-clamp gather at 6.0 s where `perf_counter` priced it at 0.31 s, a 20x mis-attribution that would have sent the lane at the wrong line. LANE D EDITED THE SAME TOOL ON ITS OWN BRANCH (a `--count` option): the lead resolves that conflict at merge.

## perf P3 wave 2 lane H (lane/perfsolveH, 2026-08-13)

Optimisation-only lane: `_apply_runway_flex_hook`'s value envelope,
`one_profile_solve`'s Gauss-Seidel neighbour pass, and
`_seed_elevations`' nearest-hard backfill.  Every change is a
semantics-identical transformation; acceptance is the perf phase's
byte-identity gate and it PASSED — HECA and CYXY solve-stage replays
reproduce `baselines/1.0.245/MANIFEST.txt` exactly (`f562cbfeb8f9`
3887 shapes, `61efa43c3aeb` 462 shapes), and a clean-tree control
replay at the branch point (020cdae) reproduced the same HECA hash.

`--count` wrapper timers, HECA replay (baseline = same tree pre-edit,
except `one_profile_solve` whose baseline is the 020cdae control):
`_apply_runway_flex_hook` 44.2 -> 14.7 s (1 call; the promoted
`_flex_value_envelope` is 10.7 s of that over 72 calls),
`one_profile_solve` 40.4 -> 29.6 s, `_seed_elevations` 13.2 -> 1.5 s
(4 calls; `nearest_hard_candidates` 0.8 s of that).  Replay walls
424.3 / 437.1 -> 340.2 s.

DEFERRED / UNPAID:

(a) EVERY NUMBER ABOVE WAS TAKEN UNDER CONCURRENT LANE LOAD (lanes E,
    F, G and this lane's own capture build were on the machine; load
    average 10-23 through the window).  The wall figures are therefore
    NOT adjudicable: the control arm's `final_grade_projection` read
    78.2 s against the same tree's 44.3 s an hour earlier, which is the
    size of the distortion.  The defensible claim is the SUM OF THE
    THREE ATTRIBUTED SINK DELTAS, -52 s; the replay-to-replay -84 to
    -97 s is a contaminated read.  P4 owns the exclusive wall.
(b) `final_grade_projection` (spec site, 44.9 s) is NOT separately
    optimised.  Its own self time is below the sampler's floor — the
    44.0-44.3 s is its callees: `_seed_elevations` (paid here),
    `_build_shape_constraints` / `_grade_graph_edges` (24.1 / 22.5 s,
    lane F's presolve neighbours), `build_unified_graph` and
    `shape_constraints` (lane D, merged) and `_project_chromatic`
    (lane C, merged).  Reported as a decomposition, not a saving.
(c) `blast.py` names 67 test files across the three edited modules; all
    67 plus the new twin file ran ONCE through the run ledger (1292
    passed, 5 xfailed, 79 of them new twins).  Two failures —
    `test_r17_band_clamp_last_author.py::...test_no_elevation_author_
    runs_after_the_seal` and `test_single_graph_acceptance.py::
    test_solver_validator_same_edge_budgets@CYXY` — were reproduced on
    the CLEAN 020cdae control tree and are PRE-EXISTING.  No full
    suite, no blast sweep of the 33/43/48 importers.
(d) No KCLT / OTHH / KSTJ replay or build, no `--tile` arm, no census
    on any arm (byte-identity to the frozen baseline is the stronger
    gate and it passed at both captured airports).
(e) The dominated-push suppression in `_flex_value_envelope` is argued
    from heap ordering (`_tie` is monotone, so an equal-key push can
    never win a node) and twinned against the unsuppressed Dijkstra on
    random graphs incl. zero budgets and `-0.0` seeds.  It is NOT
    twinned on HECA's real adjacency — no dump of that graph exists.
(f) `nearest_hard_candidates` bounds the search with numpy `a * a` and
    lets the caller's original `a ** 2` decide the winner, because the
    two DISAGREE: measured on this machine, 2 744 of 2 000 000 random
    doubles in +/-1e6 differ in the last ulp between Python's
    `pow(a, 2.0)` and `a * a`.  The 1e-9 relative slack is argued
    (~4.5 M ulps of margin), never swept — a pathological input where
    the true winner sits outside it is unconstructed, and the fallback
    for non-finite coordinates is exercised only by the twin.
(g) CPython's `sum()` runs NEUMAIER COMPENSATED summation on floats.
    The first cut of the merged neighbour pass replaced the plain-mean
    `sum(...)` with a running accumulator and changed `pm` on 9 of 25
    random neighbour lists; the twin caught it before any replay.  The
    landed version gathers and still calls `sum`, so the compensation
    is unchanged — but nothing outside this lane's twin pins that
    property of the interpreter.
(h) `canonical_points._find_nearest` (3.5 s leaf at HECA) has an exact
    zero-distance early exit available and was NOT taken: the file is
    outside this lane's scope and other wave-2 lanes are editing it.
    Recorded as an opportunity, unmeasured.
- 2026-08-13 lane/perfobj (perf P3 wave 2 Lane G — OBJECT PARTITIONING, spec perf-p3-wave2-sinks-spec.md): tests run ONCE (PRE-SHIP MODE): `tests/test_obj8_partition.py` (21, incl. 5 new lane twins), `tests/test_weld_parts_local_index_space.py`, `tests/test_object_anchor.py`, `tests/test_harness.py` (221). NOT run: the rest of the blast radius (`blast.py` names 8 importers / 4 test files for `obj8_partition.py` and 18 importers / 10 test files for `object_anchor.py`); no full suite; no census on any arm. UNPAID / OPEN:
  (a) THE LANE MISSED ITS -40 s FLOOR BY DESIGN OF THE SITE, not by giving up. Measured ceiling: the WHOLE sink — `object_anchor.partition_structures` over HECA's pack — is 52.2 s CPU (matching P1's 52.5 s sampled), so the -40 s floor asked for a 77 % cut of a function that is already vectorised numpy. Delivered: 52.2 -> 44.9 s CPU (-7.3 s, -14 %), whole uncached reader 67.8 -> 62.8 s CPU.
  (b) NOT REPLAY-REACHABLE (step 1's finding, spec's pre-delegated branch): `partition_structures` is called from `dsf_reader._compute_dsf_object_buildings` (before step 1) and `post_mesh` (tile rebake) only — never from phases 5-6 — so `solve_cut --replay` cannot see it. The lane iterated against the UNCACHED reader (`read_dsf_object_building_evidence`) instead, gated per iteration on the emitted ring set + per-structure evidence rows hashed (`rings_sha256 f375be9975ac393d…`, `rows_sha256 d118a45858d48028…`, identical across every arm).
  (c) WALL NUMBERS ARE UNQUOTABLE THIS WAVE and the lane's first arms were contaminated by it: with five lanes on the machine (load average 32) an identical arm moved `contact_graph`'s wall total by 65 % and made a REGRESSION read as a 13 s win. Every number quoted is `time.process_time` (CPU) via `profile_airport_build.CallCounter(clock=…)`. No exclusive wall pair was taken (P4 owns walls), so the CPU deltas have no wall translation yet.
  (d) THE REMAINING SINK IS THROUGHPUT-BOUND AND ITS BIG WIN IS FLOAT-ORDER-BLOCKED (spec: STOP on that site, record the potential). `_point_triangle_minimum_distances` is 11.6 s CPU over 69,835 calls / 63.4 M point-triangle pairs; microbenchmarked at ~43 us fixed per call and ~0.105 us per pair, so ~65 % is genuine element throughput. The one large reduction available — deriving `dot_3..dot_6` from `dot_1`/`dot_2` and per-triangle scalars via `(p-b)·e_ab = dot_1 - |e_ab|²`, which deletes four of six `(P,T,3)` einsums and the `from_b`/`from_c` arrays — is a float-accumulation reordering. Measured potential: ~3-4 s CPU. NOT TAKEN.
  (e) A SPARSE (paired) kernel was costed and REJECTED on measurement, not taste: of the 63.4 M pairs the kernel still evaluates, 37.8 M (59.7 %) are box-near, so a paired evaluation could remove only 40 % of the throughput term (~2 s) while resting on `numpy.einsum` choosing the same accumulation path for `(N,3)` as for `(P,T,3)` — the gamble the spec forbids.
  (f) `weld_parts`: a scipy `connected_components` rewrite was tried and REFUTED (worse than the Python union-find it replaced, on CPU as well as wall) and reverted; only the once-per-vertex-index hoist landed (-0.2 s). Site is at its attempt cap.
  (g) The prefilter's DEGENERATE-TRIANGLE EXEMPTION is twinned on a synthetic specimen (`test_far_degenerate_triangle_still_claims_contact`), not on a pack: no count exists of how many HECA candidate sets actually contain a contact magnet, so the exemption's COST (magnets bypass the filter entirely) is unmeasured.
  (h) `tests/test_object_anchor.py::test_kclt_eight_bake_pool_end_to_end` FAILS — verified PRE-EXISTING on the lane's merge-base (matched control, same worktree, HEAD version of both edited files). Not this lane's, not fixed here.
  (i) Acceptance byte-identity taken on HECA + CYXY patch builds only; no KCLT / OTHH / KSTJ arm, no `--tile` arm, and `post_mesh`'s cached partition call site (the tile rebake path, which the same change speeds up) was never exercised.
  (j) UNRESOLVED, REPORTED NOT FIXED — the HECA acceptance build was flagged CONTAMINATED: it modified `Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/o4_object_footprints_+30+031.cache` (2 paths) in the SHARED repo despite `O4_AIRPORT_MOD_CACHE_DIR` being redirected lane-local, and the run's own Python write guard reported `blocked: []` — i.e. the write was invisible to it (the KCLT 2026-08-11 subprocess class). Attribution facts, not a diagnosis: the shared file and the lane-local one are SEPARATE inodes, link count 1 each, byte-identical content, written 10 s apart (shared 12:39:41, lane-local 12:39:51); the shared sidecar was STALE against the live pristine fingerprint before the run (stored `78a5f07d…` vs live `1bc2c3d5…`) and now carries the current one. The CYXY build in the same window was clean. Nothing in this lane touches the sidecar or cache-root machinery; the corpus effect is a footprint ring set proven byte-identical to a recompute (`rings_sha256 f375be99…`), so no geometry moved — but the shared repo is NOT UNCHANGED, which the lane's acceptance requires. FOR THE LEAD / the caching lanes (perfcache, perfsidecar) to rule on.
- 2026-08-13 perfbake arm (lead-adjudicated): perfsidecar item (b) — the tile-frame bake-invariance arm — is PAID FOR THE CACHE MECHANISM with a carve-out. Three sequential HECA `--tile 30 31 --no-ledger` builds in worktree perfbake (branch point 020cdae, contains 967e097), all rc=0, guards clean in all three frame.json (shared_repo_writes empty, contaminated=false, only allowed .lock churn). PROVED: run 1 phase "Assembling pavement & runway shoulders" 83.67 s (the expected one-time re-key), runs 2/3 WARM at 2.15/3.16 s with ZERO STALE sidecar lines and three "read from the pack sidecar cache (fingerprint match)" lines each, despite run 1's y-bake rewriting 171 pack .obj files after the sidecars were written and run 2's rewriting 77 — the engine's own bake can no longer invalidate the caches, end-to-end. CARVE-OUT (the arm's byte-identity criterion FAILED for a reason OUTSIDE the fix under test): run 1's HECA patch body = the frozen consol3heca EXACTLY (f562cbfeb8f9), but runs 2/3 drift (2f1dcfde0320, b803326a5742) confined to object_pad ways 689→723→736 + the dependent untagged interior-ring family 336→346→347, every other role identical across all three. Attribution: `o4_object_foot_pads.json` is a PRODUCT written by post_mesh into lane-local Patches/ and READ BACK as an INPUT by the next tile build (config.py:4010, flat_site.py:587) — a ratchet with no fixed point (its sha changed again after run 3). TILE BUILDS ARE NOT IDEMPOTENT under the current pad-request sidecar semantics; this is a measured three-run instance of the standing open owner question (pad-request sidecar data-vs-product, RULINGS "LANE INPUTS ARE PROVISIONED" first-instances clause) and rides that docket, not this fix's. Artifacts: scratchpad run{1,2,3}.log, HECA_run{1,2}.patch.osm, pack_before/after listings, /tmp/harness/perfbake_run{1,2,3}.{frame,result}.json (worktree left up).
- 2026-08-13 shared-corpus write, ATTRIBUTION OPEN (lead): `Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/o4_object_footprints_+30+031.cache` rewritten at 12:39:41 with NO refresh-ledger entry; observed as CONTAMINATED by lane G's HECA acceptance arm (blocked=[], the cross-attribution tell). Content is byte-identical to the correct current pristine-key state (stale live-stat digest → current pristine fingerprint), so no measurement was changed. Every session lane is exonerated by evidence: G's instrument arms guard+redirects (object_pad_evidence_report.py:133), perfbake's three frames are clean, H/E/F build through the harness redirects. Leading candidate per the standing cross-attribution class (memory: app builds write the shared corpus): the production app performing its own first post-merge re-key of the stale sidecar — lawful app behavior on its own data root, observed mid-run by a lane snapshot. Not blocking the phase; re-attribute if it recurs with a session-lane fingerprint.

## perf P3 wave 2 lane E (lane/perfemit, 2026-08-13)

Optimisation-only lane on the emit/finalize path: four
semantics-identical transformations (`conformance._points_near_edge`
band walk; `conformance._edge_linestrings` +
`_crossing_candidate_pairs` bulk query; `pavement.vertices.
_project_means_onto_runway_boundaries` batch; `adjacent_ground.
_snap_ring_to_static` envelope query), each twinned against the scan it
replaces in `tests/test_emit_finalize_prefilters.py` (9 twins).
Acceptance is the perf phase's byte-identity gate: HECA and CYXY
solve-stage replays REPRODUCE `baselines/1.0.245/MANIFEST.txt` exactly
(`f562cbfeb8f9`, `61efa43c3aeb`).

DEFERRED / UNPAID:
(a) THE LANE MISSED ITS ≥30 s TARGET and stopped at the convergence
guards. Measured ceiling: HECA replay phase [6] is 102.2 s sampled, of
which 71.2 s sits at three call sites (`pipeline.py` 6183 / 6316 / 7039)
whose FUNCTIONS the same wave assigns to lanes F
(`groundside.groundside_route_band`, 22.0 s wrapper-timed) and H
(`route_profile.solve.final_grade_projection`, 45.9 s over two calls).
Lane E did not touch them; the lane-E-exclusive remainder is ~31 s
spread over sinks of 2–7 s each, so the target was not reachable
without editing another lane's functions. Reported for Fable review.
(b) MEASURED PAYMENT IS THE CONFORMANCE FAMILY ONLY, from a matched
back-to-back replay pair in one window (BEFORE = the same worktree with
the three source files reverted to HEAD~1; both arms REPRODUCED):
`planarize_airside` 4.5 → 3.3 s, `find_conformance_violations` 2.3 →
1.9 s, `enforce_conformance` 2.0 → 1.8 s. Replay wall 421.4 → 389.6 s
is NOT quoted as the claim — five lanes were building on the machine
all session and the arms are single runs.
(c) THE OTHER TWO CHANGES ARE TWINNED BUT NOT MEASURABLY PAID.
`compute_elevations_and_repair_geometry` read 6.2 / 6.3 / 21.7 / 6.0 /
6.7 s across five arms of the SAME code, and
`emit_adjacent_ground_bands` 6.7–7.5 s: both swing further between arms
than either change could move them. They are argued from mechanism
(one GEOS distance per cluster-runway pair; one 32-gon per ring vertex)
and kept because they are provably identical, not because a number
showed them.
(d) INSTRUMENT LIMIT, recorded so no later lane misreads it:
`profile_airport_build.py --count MODULE:ATTR` patches the DEFINING
module's attribute, so a callable another module bound at import time
(`finalize.py` binds `_enforce_shared_vertices`, `_compute_elevations`,
`_drop_overlap_against_fixed_shapes`) reports `0 call(s)` while running
normally. A zero there is not evidence of no work.
(e) No exclusive wall pair and no `check_build_time --runs N` (wave 2
moves wall adjudication to P4, on the merged tree).
(f) Only HECA and CYXY were replayed — no KCLT / OTHH / KSTJ arm, no
`--tile` arm, and no census on any arm (byte-identity to the frozen
baseline is the stronger gate and it passed).
(g) BLAST RADIUS NOT SWEPT (PRE-SHIP): `blast.py` names 10 importers /
6 test files for `conformance.py`, 10 / 2 for `pavement/vertices.py`
and 40 / 30 for `adjacent_ground.py`. The 36-file union `--tests-for`
names was run ONCE through the run ledger; nothing wider, and no full
suite.
(h) The band walk's superset property (every point within `tol` of the
segment is still yielded) is argued from the cell-index bound and
twinned against brute force on random fixtures — not proved for all
inputs.
(i) The bulk crossing-pair query returns its pairs in a DIFFERENT ORDER
than the per-line loop. Argued safe because every consumer sorts what
it collects per edge (`sorted(by_edge[i])`) before using it, and
twinned as a SET equality only — no test pins the order.
(j) TESTS, run ONCE through the ledger over the 36-file union above:
867 passed, 2 failed — `test_pad_host_pavement_level.py::
test_the_pad_law_re_asserts_after_the_late_projection` and
`test_strip_heal_law_v4.py::test_the_pass_order_is_unchanged_by_the_law`.
Both are SOURCE-INSPECTION tests reading
`inspect.getsource(pipeline.build_airport_pavement)`, and phases [5]+[6]
now live in `pipeline.solve_and_finalize`, so the names they look for
are no longer in the function they read. PRE-EXISTING, proved with a
matched control in this same worktree (the three source files reverted
to HEAD~1: the identical two FAILED lines, 38 passed). Not repaired
here — lane E's scope is optimisation only, and repairing them is a
pipeline-refactor follow-up for the lead.
- 2026-08-13 lane/perftile (perf P3 Lane T — TILE VECTOR STEP, spec perf-p3-wave2-sinks-spec.md): tests run ONCE through the run ledger (128 passed: the 6 files `blast.py` names for `O4_Vector_Utils.py`, the tile-profiler refusal twin, and the new `tests/test_vector_edge_index.py`); no full suite, no blast-radius sweep of the 14 importers / 29 for `O4_Vector_Map.py` (PRE-SHIP MODE). Acceptance is this lane's own gate: the vector step's 20-file PRODUCT SET (`Data+35-081.node`/`.poly`/`.apt`/`.alt` plus the 8 `*_auto.patch.osm` and their `.axes.json`) BYTE-IDENTICAL across two pristine runs and both optimized arms, and a matched vector+mesh pair with `Data+35-081.mesh` byte-identical too. UNPAID / OPEN:
  (a) NO OTHER TILE, NO OTHER AIRPORT. Only `+35-081` was built. `O4_Vector_Utils` is also used by the mesh, mask, imagery, forest and overlay steps; only steps 1 and 2 were exercised. No census (no body changed — the emitted patches are byte-identical because auto_patch REUSED them, so the patch writer was not exercised at all in the measured arms).
  (b) THE WALL SPREAD IS WIDE AND THE MACHINE WAS SHARED. Four other perf lanes were replaying HECA throughout; load average ranged 7-32. Three MATCHED INTERLEAVED pairs give vector-step deltas of -23.5 s, -13.7 s and -24.0 s. The per-sink `--count` numbers are the stable evidence and the UNCHANGED control in the same table (`load_airports_and_prepare_dem`, 19.5-20.2 s in every arm) is what says the two frames matched. No exclusive `check_build_time --runs N` block was run — the charter moved wall adjudication to P4.
  (c) THE P1 TILE PROFILE'S PREMISES WERE BOTH WRONG and are corrected in the report, not in code: it was taken on a NON-PRODUCTION per-tile cfg (`road_level=1`, `mask_zl=14` against the owner's `road_level=auto`, `mask_zl=16`; 26.5 MB `.node` against production's 42.8 MB) and with auto_patch absent. The canonical `+35-081` tile cfg now exists in the MAIN tree, byte-copied from the owner's own app build; it is an untracked product path and is NOT in this commit.
  (d) `tools/profile_tile_build.py` DID NOT ARM THE SHARED-REPO GUARD before this lane; it does now, and the whole-tile `--steps imagery` path is what the hole was for (the first `--tile` arm here had 765 `Orthophotos/+30-090/+35-081` writes blocked). The guard extension has NO twin of its own — it is exercised by this lane's eight measured runs, every one of which reported the repo UNCHANGED. One earlier probe run reported ONE `Airport_mod_cache/...HECA.../o4_object_terrain_classification_+30+031.cache` modification with `guard.blocked` EMPTY: a CONCURRENT lane's HECA build inside this run's snapshot window (+30+031 is not this tile), the documented cross-attribution, not a write by this run.
  (e) MEASURED AND REJECTED, recorded so nobody re-pays for them: a direct-ctypes `Index_InsertData`/`Index_DeleteData` override (interleaved microbench, medians: stock insert 16.42 us vs 16.48 us direct — libspatialindex's own tree work is the cost, the wrapper is noise) and any change to `are_encroached`'s LAPACK calls (`det`/`solve`) or to numpy-float64 node keys (`round(np.float64, 9)` uses numpy's multiply-rint-divide, `round(float, 9)` uses correct decimal rounding — a float-semantics change, STOPPED per the spec's pre-delegated rule). `write_node_file`, `write_poly_file` and `snap_to_grid` came in UNDER the 2 s materiality floor (-0.24 / -0.10 / -0.6 s) and are landed only because they were already written and twinned.

## 2026-08-13 — perf P3 wave 2 lane F (presolve/groundside + global slice)

Landed: `pavement/global_slice.py` per-piece `buffer(0.05)` hoist in the
hole-keyhole walk; `groundside.groundside_route_band` builds its probe
graph with `skip_edge_shape_ids` (within-shape pair generation is dead
work there, proof in-code); `adjacent_ground._build_construct_reach_band`
docstring records a measured-and-rejected band-sharing memo.

Skipped, per PRE-SHIP mode + the wave-2 spec (walls belong to P4):
- No exclusive `check_build_time.py --runs N` arm — the spec moves wall
  adjudication to P4 on the merged tree. Lane quotes replay-to-replay and
  `--count` deltas only.
- Phase-4 `--count` arms were run as a MATCHED CONCURRENT PAIR (control
  worktree at `020cdae` vs lane) rather than serially/exclusively; the
  delta is quoted, never the absolute wall.
- No full pytest suite, no blast-radius suite: only the test files
  directly covering the change, once, through the run ledger
  (`test_one_graph_groundside`, `test_service_band_instruments`,
  `test_band_reports_instrument`, `test_free_road_scoping`,
  `test_global_slice_hole_keyholes` — 63 passed).
- No census of the acceptance patches: acceptance here is BODY-HASH
  IDENTITY to the frozen 1.0.245 manifest (HECA `f562cbfeb8f9`, CYXY
  `61efa43c3aeb`, on both a full build and a solve replay each), which is
  strictly stronger than a census match.
- Only HECA + CYXY were exercised; KCLT / OTHH / KSTJ identity is
  unverified for this lane.

## perf P3 wave 2 — lane perfgraph (grade_graph run-scoped law memo), 2026-08-13

Landed: `grade_graph.shape_constraints_cached` gains a SECOND memo tier,
scoped to one solve RUN (stored on the layout) and keyed on every input
`shape_constraints` reads (`_sc_run_key` + `_ctx_law_digest`). HECA
`shape_constraints` 12,078 -> 10,813 calls, 55.6 -> 49.5 s; CYXY 1,522 ->
1,223 calls, 4.8 -> 3.8 s. Both matched CONCURRENT `--count` pairs against
a control worktree at `fa68843`.

Skipped, per PRE-SHIP mode + the wave-2 spec (walls belong to P4):
- No exclusive `check_build_time.py --runs N` arm and no wall claim: the
  spec moves wall adjudication to P4 on the merged tree. Replay wall
  numbers appear only as run context, never as a claim.
- `--count` arms were MATCHED CONCURRENT PAIRS (control worktree at
  `fa68843` vs lane), not exclusive serial runs; only the delta is quoted.
- No full pytest suite, no blast-radius suite: the 25 `blast --tests-for`
  files were run once through the run ledger (412 passed, 2 failed —
  `test_r17_band_clamp_last_author::test_no_elevation_author_runs_after_the_seal`
  and `test_single_graph_acceptance::test_solver_validator_same_edge_budgets@CYXY`,
  BOTH reproduced identically on a matched control arm at `fa68843`, so
  pre-existing and untouched by this lane).
- No census of the acceptance patches: acceptance is BODY-HASH IDENTITY to
  the frozen 1.0.245 manifest (HECA `f562cbfeb8f9`, CYXY `61efa43c3aeb`,
  solve replays), strictly stronger than a census match.
- Acceptance is REPLAY-only for this lane (no fresh full builds of the
  changed tree); the captures themselves came from full builds at
  `fa68843` whose bodies were byte-identical to the frozen manifest.
- Only HECA + CYXY were exercised; KCLT / OTHH / KSTJ identity is
  unverified for this lane.
- Peak RSS measured once (not a pair-averaged figure): HECA replay
  4.437 GB with the memo vs 4.346 GB without (+90 MB, +2.1 %). Memory is
  bounded by the layout's lifetime; no cap constant was added.

## 2026-08-13 — lane/dupcensus (perf P3): the duplicate-work census

The instrument (`profile_airport_build.py --count-inputs*`) is
observation-only and its twin (`tests/test_profile_input_fingerprint.py`,
24 tests with `test_profile_tile_build_refusal.py`) proves the three
load-bearing properties: duplicate detection fires, outputs/arguments are
untouched, an UNFINGERPRINTABLE input still counts its call.

Skipped, per PRE-SHIP mode:
- No full pytest suite and no blast-radius sweep: only the two test files
  directly covering the two edited tools, once.
- No `check_build_time.py` arm. The census ADDS wall time by construction
  (the fingerprint tax, which the report prices separately and excludes
  from the seconds columns); it is a measurement mode, never on in a
  production build, so the build-time budgets do not apply to it. The
  unfingerprinted `--count` path is byte-for-byte the code it was.
- The census's own SECONDS columns were taken on a machine shared with
  four other perf lanes. Duplicate FRACTIONS (dup s / total s) and call
  COUNTS are the quotable products; absolute seconds carry the standing
  +-25 % single-run caveat and are never quoted as a wall claim.
- Census coverage is HECA (solve replay + full build) and KCLT (tile
  vector step) only — OTHH, CYXY and KSTJ are uncensused.
- `groundside._svc_contiguous_width` and `O4_Vector_Utils`'
  `insert_way`/`insert_edge`/`encode_MultiPolygon`/`snap_to_grid` are hot
  leaves taking large geometry arguments; they are counted (`--count`)
  but NOT fingerprinted, because digesting a pavement union per call
  would cost more wall than the census is worth. Their duplicate status
  is therefore UNMEASURED, not LAWFUL.
- `global_slice._hole_spur` and `solve._value_envelope` are NESTED
  functions and are not reachable by `MODULE:ATTR`; unmeasured.
- Census (b), the full HECA build, has NO body-hash proof of its own:
  `profile_airport_build.py ICAO` calls `build_airport_pavement` and
  never writes an `.osm`, so there is nothing to hash. The
  observation-only claim rests on (i) the twin, and (ii) census (a),
  which ran the SAME instrument with 23 counters armed across the whole
  solve and reproduced the frozen `consol3heca` body hash
  `f562cbfeb8f9` byte-for-byte. The phase 0-4 targets armed only in (b)
  are therefore twin-proven but not hash-proven.
- `profile_airport_build.py`'s BUILD path had neither half of the
  arming composition; this lane armed it (imported from
  `harness/build_airport.arm_shared_repo_protection`, the
  classify_report precedent). `profile_tile_build.py` gained the
  harness's own `provision_tile_cfg`. Neither change is covered by a
  new twin of its own beyond a compile + the existing refusal twin;
  both are proven only by the three census runs completing with
  "shared repo UNCHANGED".

## perf P3 wave 2 — lane perfcenter (centerline_specs input-keyed memo), 2026-08-13

Landed: `grade_graph.centerline_specs` — THE law's centerline enumeration,
called 9-11 times per build by `build_context` (twice per graph build),
`service_chain_lines` and `verification`'s two sidecar exports — gains an
INPUT-KEYED memo on the layout (`layout._cls_specs_memo`, keyed by
`_cls_specs_key`). It is the dupcensus's single material duplicate row.
Measured, matched SERIAL `--count` pair in one worktree via the
`CENTERLINE_SPECS_MEMO` kill switch, `--count-clock cpu`:
HECA replay `centerline_specs` 4.6 -> 0.5 s CPU over an unchanged 11 calls
(the computation itself 11 -> 1 call, 4.6 -> 0.4 s; the key's own cost is
0.1 s over 11 calls); CYXY 0.1 -> 0.0 s.

Skipped, per PRE-SHIP mode + the wave-2 spec (walls belong to P4):
- No exclusive `check_build_time.py --runs N` arm and NO WALL CLAIM. The
  replay walls printed beside each arm (HECA 310.2 s before / 308.3 s
  after; CYXY 33.9 / 33.7) are run context under the standing +-25 %
  single-run caveat, never a claim; the quoted deltas are `--count`
  process_time on the named callables only.
- The before/after pair was taken by flipping the module-level
  `CENTERLINE_SPECS_MEMO` kill switch rather than against a control
  worktree. Same tree, same corpus, same captures, run serially — but the
  two arms are two source states of one branch, not two branches.
- No full pytest suite and no blast-radius sweep: the 25
  `blast --tests-for` files, once, through the run ledger.
- No census of the acceptance patches: acceptance is BODY-HASH IDENTITY to
  the frozen 1.0.245 manifest (HECA `f562cbfeb8f9`, CYXY `61efa43c3aeb`),
  strictly stronger than a census match.
- Only HECA + CYXY were exercised. KCLT / OTHH / KSTJ identity is
  unverified for this lane; so is any airport whose layout MUTATES its
  centerline set between graph builds — the key would simply miss there
  (correct, just unpaid), but that behaviour is proven only on the twins'
  synthetic layouts, never on a real airport.
- The duplicate CENSUS COLUMNS are unchanged by construction, and that is
  not a defect: a duplicate CALL is still a call, so the row still reads
  11 calls / 1 distinct / 10 identity duplicates. What moved is the
  SECONDS those duplicates spend — HECA 4.21 -> 0.06 s, CYXY 0.07 ->
  0.01 s. The brief's "duplicates 9-11 -> 0" is reachable only by DELETING
  call sites, which this lane did not do.
- `_cls_specs_fresh` copies the answer's `pts` / `seg_caps` lists on every
  served call so no two callers ever share a list. No consumer mutates
  them today (audited across `src/` and `tools/`), so the copy is unproven
  insurance rather than a measured need; its cost is inside the 0.1 s the
  key + copy arm shows.
- Memory: the memo holds ONE spec list per layout (references to the same
  coordinate tuples), released with the layout. No RSS pair was taken —
  the perfgraph lane's +90 MB figure came from a per-shape store two
  orders of magnitude larger than this one.
- 0 new law constants and 0 new env flags. `CENTERLINE_SPECS_MEMO` is a
  module-level kill switch for the twin; no law reads it.

## S7 — census domain restoration + drainage retirement (2026-08-13/14)

- lane/s7domain. Verification actually run: the blast `--tests-for`
  selection over grade_law + check_grade + config (131 test files) once
  through `run_with_ledger`, plus a MATCHED CONTROL of the failing files
  on clean main. Both sides: the SAME 19 failures, test-id for test-id
  (test_pavement_grade x7, test_flat_site_mode x6,
  test_tunnel_portal_fidelity x2, test_contracts,
  test_pad_host_pavement_level, test_object_anchor,
  test_runway_seam_dem_steps). S7 introduces ZERO new failures; those 19
  are pre-existing at 8345bf8 and are not this lane's to fix.
- SCOPE CORRECTION, mid-lane: the first retirement commit (8907f5a) took
  the brief's wording ("only runways crown") literally and retired the
  APRON half of §B3 as well. The owner clarification (RULINGS 2026-08-14)
  is narrower. That commit was REVERTED and re-landed at the clarified
  scope; the frame report was re-measured. Nothing else was touched by
  the revert.
- SKIPPED: no build of any kind. The five-airport re-census is over the
  FROZEN 1.0.245 artifacts, as the charter asked — so nothing here
  verifies that a FRESHLY BUILT patch censuses the same way under the
  narrowed family. It cannot differ (the change removes reader domain and
  no emitter ever read the law), but it is not measured.
- SKIPPED: no in-sim pass. The change removes rows from reports; it moves
  no geometry.
- OPEN, and the round's to rule: THE RUNWAY CROWN LAW HAS NO CENSUS
  READER. Measured: a runway emitted dead flat against a declared 0.30 m
  crown drop censuses ZERO rows, because the within-shape crown check
  judges deviation from the DESIGNED crown against the runway's own
  transverse cap allowance and a 1 % crown sits inside a 1.5 % cap by
  construction. The minimum is bound only where it is generated
  (tests/test_crown_minimum_bound.py). This was survivable while §B3
  covered landside pavement; with the 2026-08-14 clarification naming the
  runway crown as one of the three surviving drainage laws, it is a law
  we cannot see. Building the reader is a new law family — spec work.
- OPEN, not touched, reported to the lead: `check_grade._TRANSVERSE_ROLES`
  excludes `service_road` while `lateral_spine_nodes` DOES insert
  cross-section vertices on service_road shapes and constrains them at
  SERVICE_ROAD_MAX_TRANSVERSE. The exclusion is deliberate and in
  documented lockstep ("Expressed over the lateral pass's own target
  roles, which are exactly check_grade._TRANSVERSE_ROLES"), so it is not
  the migration-blindness class and S7 left it alone — but it IS a
  generation-binding constraint whose validator twin reads nothing.
- NOTED: `tunnel_ramp` is groundside in layout.GROUNDSIDE_ROLES and was
  never in the §B3 walk either. With the landside half retired the
  question is moot; recorded in case landside drainage is re-opened.

## 2026-08-14 — S8 (lane/s8valid): the two validator gaps S7 escalated

Both S7 OPEN items above are CLOSED. Neither reader moves geometry;
both make pre-existing conditions visible for the first time.

- DONE, not deferred: the five-airport census delta is MEASURED, over the
  FROZEN 1.0.245 artifacts in the S7 `retired` frame
  (`tools/harness/census.py --no-cache`, `tmp/s8/*.json`). Item 1 adds
  `transverse::service_road|service_road` — CYXY +62, HECA +622,
  KCLT +114, KSTJ +11, OTHH +27 (+836, every row GROUNDSIDE, AIRSIDE
  invariant at all five). Item 2 adds `runway_crown` — CYXY 10, the other
  four ZERO; all ten are AIRSIDE and all ten carry the cited
  intersection exception, so no ADJUDICATED number moves either.
- DONE, not deferred: BYTE IDENTITY. The diff touches one emitter file
  (`lateral_spine_nodes`, a public alias + one selector), so it was
  measured rather than argued: capture-armed `build_airport.py` arms in
  this lane reproduced the frozen 1.0.245 bodies exactly — CYXY
  `61efa43c3aeb` (462 shapes), HECA `f562cbfeb8f9` (3887 shapes, 506 s) —
  shared repo UNCHANGED on both, and the `solve_cut.py --replay` of the
  HECA capture on the FINAL tree reports REPRODUCED against the same
  manifest key.
- DONE, and it PAYS an S7 line: S7 deferred "nothing verifies that a
  FRESHLY BUILT patch censuses the same way". The freshly built HECA
  patch above censuses 8038 / transverse 3911 / runway_crown 0 / airside
  1720 — identical to the frozen artifact under the same readers.
- BUILD-TIME IMPACT (per-change timing gates SUSPENDED, owner 2026-08-04;
  stated anyway): both readers are census-side, and the build touches
  them once through `verification.run_grade_checks` AFTER `to_osm`. The
  five-airport census wall is 34.8 s before and 33.2/36.3 s after — inside
  the run-to-run spread, no measurable regression, and the HECA build
  itself came in at 506 s against the frozen baseline's 571 s.
- SKIPPED: no in-sim pass. Census readers move no bytes, and the byte
  identity above is the proof.
- SKIPPED: full suite / blast-radius sweep (PRE-SHIP MODE). Run once:
  the blast selection (`test_lateral_cross_section`,
  `test_crown_minimum_bound`, `test_route_transparent_laterals`) plus
  every file that reads the census contract (`test_harness`,
  `test_census_instrument`, `test_region_rulesets`,
  `test_reg_families_round`, `test_road_feed_in_graph`) — 509 passed
  through `run_with_ledger`.
- OPEN, reported to the round, NOT this lane's to rule: the runway
  transverse CAP has no transect reader either. `_check_runway_crown`
  reads the MINIMUM half of `grade_law.transverse_surface_bounds`
  (the crown that was declared and not realised); a crown STEEPER than
  `runway_transverse_max` is still read only by the within-shape pair
  law, which is the same cap-allowance blindness in the other
  direction. Building it is a scope decision, not an implementation one.
- OPEN, reported: the 10 CYXY crown rows are all at runway INTERSECTIONS
  and all adjudicated out of scope by the cited exception — but the
  underlying geometry (a declared 0.114 m crown realised at 0.005 m
  where two runways cross) is a real surface fact the round may want to
  look at even though no law requires the crown there.

## Staged-solve S1 (geometry freeze) — lane/s1freeze, 2026-08-13

- OTHH / KCLT / KSTJ / SPJC / SPLP censuses NOT run for the freeze
  increment (only HECA replay + CYXY control-airport arm). Pre-ship mode
  allows one acceptance arm per lane; the consolidated five-airport
  adjudication is lead-owned and still owed for this change.
- The full pytest suite was NOT run; the `blast --tests-for` selection
  over the four edited files (89 files, 2323 passed) plus the new freeze
  twins was, once, through `run_with_ledger`.
- Build-time impact of the freeze block NOT measured exclusively: the
  freeze adds one node-list+context+graph+band build and REMOVES the one
  `adjacent_ground._build_construct_reach_band` used to do, so the
  intended net is ~zero. Replay walls (315.6 s arm 1 / 293.7 s arm 2 vs a
  383.7 s whole build) are not timing arms and must not be quoted.
- The solve-side one-graph reuse is NOT landed (measured and rejected,
  see solve.py's rejected-reuse note); the `id(s.polygon)` re-keying that
  would make it safe is unbuilt.

## Staged-solve S1b (the stage partition) — lane/s1stage, 2026-08-13

- ACCEPTANCE NOT MET, and this is the lane's headline, not a footnote:
  HECA airside adjudicated rows fall 1720 -> 1676 (**-44** of the ruled
  **-130**). Attempt cap 2 reached; the remainder is a STOP for Fable,
  not a third attempt. The lane commits its architecture, its twins and
  its measured position; it does NOT merge.
- The "apron -11906 worst <= 0.86 m" criterion could NOT BE JOINED. No
  pre-corridor HECA artifact exists in this lane or the frozen 1.0.245
  baseline set, and way ids are per-build: `-11906` names no way in
  either the frozen census or any arm here. The apron worst that IS
  joinable moved the wrong way (shape `-10577`, 11.36 -> 11.49 m,
  +0.13 m). Whether that is the named site is UNVERIFIED.
- "Airside rows byte-equal to the pre-corridor airside state on
  unchanged rings" is UNVERIFIABLE for the same reason: there is no
  pre-corridor row dump to be equal TO. What was measured instead is the
  row-level A/B against the frozen 1.0.245 census, reported in full.
- The freeze increment's airside apron churn did NOT resolve; it GREW.
  vs frozen: 93 gone / 103 new (freeze) -> 246 gone / 202 new (this
  lane). vs the freeze arm itself: 184 gone / 140 new. The mechanism is
  named (stage A no longer sees groundside entries OR groundside
  variables, so every airside value a groundside constraint used to
  shape has moved) but the resulting state is not shown to be the
  pre-corridor one.
- 6 of 21 couplings closed (1, 2, 3, 4, 5, 6) + 17 and 18 wired and
  MEASURED INERT at HECA (1 groundside row between arm 1 and arm 2).
  Couplings 7-16 and 19-21 are OPEN and unmeasured by this lane.
- ONE airport replayed (HECA solve_cut) + CYXY control BUILD. OTHH /
  KCLT / KSTJ / SPJC / SPLP censuses NOT run. Consolidated five-airport
  adjudication is lead-owned and owed.
- Tests: the directly-covering selection (24 files, 602 passed) once
  through `run_with_ledger`, NOT the full `blast --tests-for` union
  (96 files) and NOT the full suite.
- `tests/test_single_graph_acceptance.py::test_solver_validator_same_edge_budgets@CYXY`
  fails (2 of 12,013 shared edges, ~1e-3 budget delta) and is
  PRE-EXISTING: the same test fails identically in the clean
  `s1freeze` worktree at this lane's base commit (matched control run
  2026-08-13). Not attributable to this change.
- TWO TWINS UPDATED FOR A SUPERSEDED MECHANISM, needing Fable
  ratification: `test_probe_gates.py` (its default-arm sentinel now
  watches `_partition_by_stage` instead of `_withhold_road_pair_law`,
  which is no longer called) and the hand-built entries in
  `test_probe_gates` / `test_projection_partition` now carry the stage
  tag their minters would stamp. No assertion's INTENT was changed.
- `_withhold_road_pair_law` is KEPT but no longer called on the default
  path (the `O4_PROBE_ROAD_PAIR_LAW_AIRSIDE=1` arm still reaches it).
  Deleting it is S6's kind of work, not this lane's.
- NO build-time measurement. Replay walls (289.2 s arm 1 / 299.5 s
  arm 2 vs the 288.1 s control) are not timing arms and must not be
  quoted as any.
- 0 new law constants and 0 new env flags. The stage tag has no gate by
  design: a gated partition is a partition that can be silently off.

## Staged-solve S1c (route graph + boundary writes) — lane/s1stage, 2026-08-14

- ACCEPTANCE STILL NOT MET on criterion (a): HECA airside **1676** against
  the pre-corridor reference's **1653** — **+23 open**. Attempt cap 2
  reached for the S1c coupling group; STOP, not a third attempt.
- THE REFERENCE IS NOW REAL AND SERVED: artifact-ledger entry
  `9713491f...`, tag `corrHECAoff`, body `7fbe7c26d7e3`, 3316 shapes,
  censused in THIS lane's frame (current main-tree census; lane S7's
  domain revision is NOT in it — every number here is pre-S7 frame).
- S1c IS BYTE-INERT AT HECA. Couplings 7/8/16/20 (arm 3) and 11/13
  (arm 4) both replay to `5e64cbc3b629`, byte-identical to the S1b arm.
  11 and 13 demonstrably FIRE (1 airside node kept hard in the
  mouth-cluster scan; 335-336 of ~12,300 service ring nodes withheld
  from the edge-couple re-clamp) and still change no emitted byte. The
  couplings were real; their effect on this airport is not.
- Therefore the +23 is NOT in couplings 7, 8, 11, 13, 16 or 20, and 17/18
  were already measured inert. It must be in 9, 10, 12 or 21 (the
  remaining boundary couplings) or outside the inventory. That is the
  next increment's attribution, not this one's guess.
- CRITERION (c) TARGETS A SITE THAT NO LONGER EXISTS. Joining apron
  worsts by COORDINATE (not way id) across reference / frozen / arms:
  **no apron site anywhere at HECA went <=0.90 m pre-corridor to >=4.0 m
  in the frozen 1.0.245 state.** The corridor round's disclosed
  "-11906 0.86->5.69" was measured at 1.0.244; the corridor-joins round
  (HECA census 8219->7416) closed it before the baseline froze. The
  criterion cannot be met because its regression is already gone.
- The site this lane could join (30.118136,31.410569) reads 11.33 m
  pre-corridor, 11.36 frozen, 11.33 freeze, **11.49 S1c** — +0.16 m
  worse than the reference, UNATTRIBUTED and owed. Apron sites vs the
  reference overall: 25 better, 36 worse, 11 equal; worst worsening
  +1.58 m at 30.1335,31.4115 (0.00 -> 1.58).
- CRITERION (d), churn: on rings the reference also carries (canonical
  node join, 30,786 shared 11-decimal spellings of 35,569/40,008),
  320 airside rows GONE and 191 NEW — net **-129 better than the
  reference on unchanged rings**, but 511 rows differ, so "byte-equal on
  unchanged rings" is NOT met. On rings corridors changed: 28 gone,
  180 new (+152). The two together are the +23.
- JOIN INSTRUMENT, deviation stated: the ruled 11-decimal lat/lon join
  was applied at NODE level (where the canonical spelling lives and
  where 30,786 rows matched across trees). At ROW level the census dump
  carries only ONE representative lat/lon per row, so a row-level
  lat/lon join would be strictly WEAKER than `census_rows_diff`'s
  existing two-endpoint join — which is an IDENTITY test, not proximity,
  and is transported through a projection whose anchor is byte-equal in
  both sidecars ([30.1089375, 31.434664815]). Every row diff here ran at
  `--tol 0.0`, so the MOVED inference tier is empty by construction.
  Carrying canonical endpoint lat/lon into `--rows-json` would remove
  the deviation and is unbuilt.
- Twins: 3 new S1c rails (stage-A pricing positive + control, the
  untagged-law-graph refusal, and the coupling-16 premise that the walk
  adjacency really does change segmentation). 611 passed / 1 failed
  through `run_with_ledger`, once. The failure is
  `test_solver_validator_same_edge_budgets@CYXY`, PRE-EXISTING (matched
  control in the clean s1freeze worktree at this lane's base).
- 8 hand-built fixtures in `test_route_metric_seat_coupling.py` now
  carry the stage tag their minter would stamp — same ratified pattern
  as the S1b twin updates, no assertion intent changed.
- CYXY control re-run at the S1c tip: `985d880f9e7f`, unchanged. Shared
  repo UNCHANGED. OTHH / KCLT / KSTJ / SPJC / SPLP still not censused.
- `solve_cut --baseline` compares FULL sha256; a 12-char prefix always
  reads DIVERGED. Every identity claim in this lane was made on the
  printed/recorded `body_sha256`, never on that verdict line.

## Staged-solve S2 — whole-run corridor profile (lane/s2profile)

- Battery scope: only HECA and KCLT were replayed and censused. CYXY,
  OTHH, KSTJ, SPJC, SPLP NOT censused under the whole-run profile.
- Timing: NOT measured. The profile adds one taut string per corridor
  run (HECA 707 runs / 6,491 stations, KCLT 308 / 2,831) on top of the
  reach Dijkstra it does not replace. No `--runs N` A/B was taken; the
  per-change build-time gate stays suspended per the campaign ruling.
- `tests/test_pad_host_pavement_level.py::
  test_the_pad_law_re_asserts_after_the_late_projection` fails in this
  lane AND in a clean b2040d1 control worktree with the identical
  `IndexError` — pre-existing, not attributed to this change.
- The 15 blast `--tests-for` files + the two new twin files were run
  ONCE through `run_with_ledger`; no full suite, no blast sweep.
- Whole-tile / in-sim verification not run; the emitted profile is
  judged only through `harness/census.py` and
  `corridor_axis_coverage.py --profile`.
- The HELD posture (`svc_profile` keyset in both projections) has no
  twin proving the hold survives a node-list rebuild at a real airport;
  only the census delta evidences it.

## Staged-solve S2b — run/yard scoping increment (lane/s2profile)

- Same battery scope as S2: HECA + KCLT only. CYXY, OTHH, KSTJ, SPJC,
  SPLP still not censused under the whole-run profile.
- The `not_one_dimensional` release is measured only by its census
  effect (KCLT within_shape service_junction +187 -> +131, seam 28 ->
  27). No twin drives a real doubling-back run end to end.
- The run/yard mean-width discriminator was measured to release only
  75 (HECA) / 122 (KCLT) nodes — the KCLT offenders are LINEAR ribbons,
  so the scoping is not what closed the regression; it is retained
  because the ruling requires it, not because it is load-bearing here.
- Timing still not measured; free-end residual (40 over floor) is
  attributed but NOT fixed.

## staged-solve S5v2 — object pads as a RELATIVE COUPLING (lane/s5pads2, 2026-08-13)

**STOPPED AT A PREMISE OF THE RULED MECHANISM. NOTHING IMPLEMENTED, NO
`src/` CHANGE.** The ruled design (RULINGS "OBJECT PADS: RELATIVE
COUPLING", spec S5) mints, per in-reach structure, a rigid constraint
`pad_level(part nodes) − ground_level(anchor node) = base_y` **between
two IN-SOLVE nodes**, the anchor node being "the solve node at the
placement point". Measured at both battery packs against the FROZEN
1.0.245 patches, there is no such node for the objects that need one.

MECHANISM. `object_anchor.py:2411-2432` samples the render datum at ONE
point per resource — `mesh(placement.lat, placement.lon) + AGL` — so a
coupling can only bind to whatever governs the mesh THERE. Two facts
about that point decide the design, and both are pack-specific:

1. **The datum is SHARED.** Packs author around one datum for hundreds of
   resources. HECA: 385 `.anchor_bak` BAKED resources hang off **4**
   anchor datums, 191 of them (and 1840 of 1883 pad requests) off ONE
   point (30.1121180, 31.4120260). OTHH: 1229 baked resources off 93
   datums, one carrying 466 resources / 2302 requests. A coupling minted
   there is ONE solve variable governing thousands of pads spread across
   the airport — and, where those pads are groundside and the host node
   airside, exactly the cross-stage pull S1/S1b is chartered to retire.
2. **The datum's host is not a SOLVE member.** HECA's dominant datum
   stands ON emitted patch geometry — role `graded_strip` — but
   `graded_strip` is a SOFT RECEIVER (`layout.SOFT_RECEIVER_ROLES`),
   emitted post-solve and ABSENT from
   `solver_primitives.PAVEMENT_ROLES`. It carries the mesh value the
   renderer reads and no solve variable at all.

MEASURED (`tools/object_pad_anchor_report.py`, promoted this lane with
its INDEX row and twins; patches = the frozen baselines
`/tmp/harness/consol3heca.osm` `f562cbfeb8f9` and
`/tmp/harness/consol3othh.osm` `75594bc8773a`; meshes = the three
perfbake HECA `--tile 30 31` runs; shared repo UNCHANGED — guard armed
refuse-mode, `blocked=0`, 18 allowed `.lock` churn entries):

| | HECA | OTHH |
|---|---|---|
| placements / resources / anchor datums | 3201 / 519 / 2700 | 11902 / 1366 / 8537 |
| baked resources / pad requests | 385 / 1883 | 1229 / 9187 |
| datums hosted on any emitted shape | 2112 / 2700 | 7023 / 8537 |
| **pad requests on a SOLVE-role datum** | **0 / 1883** | 4732 / 9187 |
| **baked resources on a SOLVE-role datum** | **0 / 385** | 747 / 1229 |

- HECA's dominant datum: DEM 108.441 m, mesh **101.180 m** — the patch
  cut 7.26 m there — and IDENTICAL across all three perfbake builds, so
  the render datum is build-stable and the ratchet lives entirely in the
  per-part `ground_metres`, not the anchor (confirms the s5pads dossier).
- A PRE-SOLVE DEM read stands 7.261 m from that datum's render ground,
  which is the s5pads premise test's `|.|p90 7.261 m` — that percentile
  was this ONE point carrying 1840 requests, not a distribution.

CONSEQUENCE. At HECA — the round's named acceptance and in-sim airport —
the coupling cannot be minted for a single pad request or a single baked
`.obj`. Acceptance (b) (pack pristine; baseline 171 of 568 rewritten in
perfbake run 1, 77 in run 2) and (c) (cheaper than the y-bake work it
eliminates) are unreachable there BY CONSTRUCTION: nothing is
eliminated. At OTHH about half the population is reachable, dominated by
shared datums. Making HECA reachable means admitting `graded_strip` /
`groundside_pavement` as solve members — the Slice-B terrain-role
admission seam (`solver_primitives._build_node_list`,
`admitted_terrain_refs`) — which is S1/S1b geometry-freeze and stage-
partition work, not S5's, and is a spec change, so it STOPS here for
Fable per the deviation law.

FRAME WARNING, recorded because it nearly produced a false finding: the
same measurement run against the lane's inherited `Patches/` copy
(HECA body `746517957a58`, NOT the frozen `f562cbfeb8f9`) read **0 of
842** requests hosted and the dominant datum 50.8 m off any shape — that
patch carries 3491 shapes against the baseline's 4071 and no
`graded_strip` over the datum. Always check the body hash of a patch
before quoting a population from it (identity-mismatch law).

NOT RUN, and owed if the owner re-charters this lane: every S5 acceptance
arm (a)-(e) — no HECA `--tile 30 31` determinism pair, no `.obj`-rewrite
before/after count beyond the perfbake baseline, no `--count` build-time
pair, no census, no coupling twins, no sensitivity arm. `tools/blast.py`
was run for the promoted tool; `tests/test_object_pad_anchor_report.py`
(12 twins) and `tests/test_harness.py` ran green through
`run_with_ledger` (233 passed), which is the whole test surface this
lane's diff touches — no `src/` file was edited.

## staged-solve S5v3 — object pads, EMISSION-TIME RELATIVE (lane/s5pads3, 2026-08-14)

**STEP 1, the ruling's PRE-REGISTERED PREMISE TEST: PASSES at HECA.**
The ruled mechanism (RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE") reads
the pad target from the patch's OWN evaluated ground at the render datum,
in-run, downstream of the one solve.  Its premise: at a HOSTED datum
(one standing on an emitted patch shape) that evaluation must match the
BUILT mesh within the existing residual class,
`DSF_OBJECT_FOOT_PAD_RESIDUAL_M` = 0.75 m.

THE EVALUATION, spelled out (`src/auto_patch/patch_ground.py`, twins
`tests/test_patch_ground.py`).  The mesher makes a patch ring a
constrained edge loop whose nodes carry the patched altitude; every
patch-valued mesh vertex keeps its own value and every FREE INTERIOR
vertex is harmonically extended from that face's patch-valued vertices
(`O4_Mesh_Utils.interpolate_free_interior_altitudes`, R18-1b), and
Triangle4XP suppresses refinement inside a patch face
(`Triangle4XP.c:7234`, "Refinement in INTERP_ALT tris is useless").  So
the surface inside a face is an interpolation of that face's own ring
values and NEVER the DEM.  `PatchGroundField` reproduces it as: the
INNERMOST non-pad shape covering the point, its ring's own vertex
altitudes, Delaunay-triangulated, barycentric at the query.  ASSUMPTIONS,
each one measured rather than asserted: (i) the frame is layout LOCAL
METRES, which is `O4_Mesh_Utils`' `(lon * cos(lat0), lat)` up to a
uniform scale, and Delaunay is invariant under uniform scaling; (ii)
where the mesher's face corners are ring nodes the rule is EXACT; (iii)
where other input nodes (orthogrid, gluing network, road ribbons) intrude
into a face the two triangulations differ, and that difference is the
measured residual below; (iv) pad roles never host, so the read is never
self-referential.

MEASURED, matched frame — patch `HECA_auto.patch.osm` body sha256
`b803326a5742` (perfbake run 3, 12:48) against the mesh that same run
built (`/tmp/harness/tile_perfbake_run3/Data+30+031.mesh`, 12:49); pack
`c_EGY - 100_airport - HECA Cairo (Tai Models)`; shared repo UNCHANGED
(guard armed refuse-mode, `blocked=0`, 18 allowed `.lock` churn):

| HECA, |patch-evaluated − mesh| at the datum | datums | p50 | p90 | max |
|---|---|---|---|---|
| HOSTED (the patch authors it) | 2112 / 2700 | 0.0293 | **0.6021** | 4.4933 |
| ... weighted by the 1874 hosted pad REQUESTS | 1874 reqs | 0.0000 | **0.0000** | 0.0000 |
| UNHOSTED (DEM read vs mesh — the y-bake population) | 588 / 2700 | 0.3238 | 1.5921 | 13.6767 |
| ... weighted by the 9 unhosted requests | 9 reqs | 0.0039 | 3.3052 | 3.3052 |

p90 0.6021 m is UNDER the 0.75 m cap, and every request-carrying datum
evaluates EXACTLY (1e-6 m).  The unhosted p50 0.3238 m reproduces the
s5pads dossier's off-patch 0.328 m, which cross-checks the instrument.

THE TAIL, attributed rather than waved at: 152 of the 2112 hosted datums
exceed the cap, and they carry **0** pad requests — 113
`groundside_pavement`, 30 `apron`, 7 `service_junction`, 1
`graded_strip`, 1 `service_road`.  They are large NON-PLANAR rings, which
is exactly where assumption (iii) bites.  The design's accuracy is
therefore bounded by the HOST RING'S PLANARITY, and a request landing on
a big non-planar apron could carry a target several metres off; no such
request exists in either battery pack today.

SENSITIVITY ARMS (`--eval-sensitivity`), |arm − the ruled evaluation|
over the same 2112 hosted datums:

| arm | p50 | p90 | max | request-weighted p90 |
|---|---|---|---|---|
| outermost host instead of innermost | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| raw `(lon, lat)` frame instead of metres | 0.0000 | 0.3117 | 2.4793 | 0.0000 |

The host choice is not load-bearing at any datum in this pack; the FRAME
is, in the tail — which is why the frame is fixed by the mesher's own
`scalx` and not by convenience.

BUILD-TO-BUILD DRIFT of the datum's mesh value across the three perfbake
runs: max over datums 0.5958 m, and 0.0000 at the dominant datum (which
reads 101.180 in all three).  That confirms the s5pads2 finding and
identifies the ratchet as downstream of the anchor.

CIRCULARITY, measured because the design turns on it: a pad whose own
ring COVERS its render datum cannot close its residual by any target —
raising the ground raises the object with it, and the residual `AGL +
base_y` is invariant.  At HECA that is **1 of 1883** requests; the other
1882 have their datum outside their own ring.  Such a request is not
padable and belongs to the y-bake fallback.

**NOT RUN — OTHH's mesh arm, and why.**  The premise test needs a BUILT
mesh matched to the patch that produced it.  There is no
`Data+25+051.mesh` anywhere, and `build_airport.py OTHH --tile 25 51`
REFUSES: the main tree has no `Tiles/zOrtho4XP_+25+051/
Ortho4XP_+25+051.cfg`, and provisioning one is an owner act (ruling
2026-08-12b, lane inputs are provisioned, never hand-seeded).  The lane
did NOT hand-seed one.  What WAS measured at OTHH, against the frozen
1.0.245 baseline `/tmp/harness/consol3othh.osm` (body sha256
`75594bc8773a`), guard `blocked=0`, 16 `.lock` churn: 11902 placements /
1366 resources / 8537 anchor datums; 1229 baked resources; 9187 pad
requests; **hosted 7023 / 8537 datums carrying 5410 / 9187 requests and
935 / 1229 baked resources**, so 3777 requests stand on unhosted ground
and stay y-bake.  The tile's DEM reads 3.962 m at every top datum (the
flat-site synthetic constant inset) against patch-evaluated 3.960-3.991,
so at OTHH the patch and the DEM very nearly agree and the premise arm is
expected to be as tight as HECA's — EXPECTED, not measured.  Owed: one
`--tile 25 51` build once the owner provisions that tile's cfg, then the
same `--eval-patch --mesh` arm.

### STEP 2 — STOPPED at an UNSTATED PREMISE of the ruling's request clause

The ruling's mechanism clause reads: "the relative resolution moves to
EMISSION, same build — pad target = the patch's own evaluated ground at
the datum + base_y", and the charter's implementation clause: "The
request MEASUREMENT moves in-run: derive requests from the pack evidence
+ datum evaluation at emission (no post-mesh rebake dependency for
pads)".  The TARGET half is now built and measured (above).  The REQUEST
half rests on a premise that is FALSE as stated: **the pack evidence a
pad request is made of does not exist in-run, and never has.**

MEASURED, by grep and by call-graph, not inferred:

1. `object_footprints.foot_pad_rings` — THE pad-ring law
   (object-reseat-threshold-spec §2.5) — has exactly ONE caller in the
   whole tree: `post_mesh.py:3110`, inside the rebake's `_rings(request)`
   closure.  It has never been called during a build.
2. The in-run building reader
   (`dsf_reader.read_dsf_object_buildings`, `pipeline.py:1596`, which
   DOES run pre-solve and IS sidecar-cached) returns
   `(outer_ring, hole_rings, role)` and nothing else — no `base_y`, no
   placement anchor, no AGL, no `resource_path`.  Its ring is
   `object_footprints.structure_ring`'s CONVEX HULL of one structure.
3. That hull is not merely a different ring, it is the RETIRED ring law:
   §2.5 replaced exactly this single-group hull because it "bridged the
   non-object ground between spread-out parts and flattened it (OTHH
   in-sim, build 1.0.226: a 162,219 m² pad spanning water and parking
   lots)".  `foot_pad_rings` instead hulls each CONTACT PART on its own,
   dilates, unions, and returns one ring per connected component.
4. Per-part contact geometry and `base_y` (the authored y of a cluster's
   lowest solid vertex, `object_anchor.py:183`/`:1406`) exist only inside
   `object_anchor`'s frame, which `post_mesh.rebake_dsf_objects` builds
   AFTER the mesh.  `flat_site.pack_seat_targets` (`flat_site.py:584`)
   and `object_pads` both reach that evidence only by REPLAYING the
   previous build's sidecar — which is the read-back the ruling retires.

So clause (D) is not an emission-site edit; it requires a new in-run
per-structure evidence surface (pool → partition → per-part contact
points → `base_y` → anchor/AGL → `foot_pad_rings`).  Three resolutions
exist and the choice is a DESIGN decision, so per the deviation law this
STOPS for Fable rather than being decided here:

* **R1 — widen the in-run reader.**  Extend `structure_ring` /
  `read_dsf_object_buildings` to also emit per-part contact points,
  `base_y`, anchor + AGL and resource identity, and call
  `foot_pad_rings` in-run.  The heavy work (pooling, partition, geometry
  load) already runs and is cached, so the marginal read cost is small —
  but the post-mesh rebake still builds its OWN frame for the y-bake
  fallback the ruling keeps, so the frame is built TWICE per build.
  `_compute_dsf_object_buildings` alone is a recorded 66.6 s per HECA
  lane build (harness P1 finding, quoted by the build entry itself), so
  a duplicated frame is a straight fail of acceptance (c), "the pad path
  must cost no more than the y-bake work it eliminates".
* **R2 — move only the TARGET.**  Keep the rebake as the request
  MEASUREMENT (rings, `base_y`, identity) and replace only
  `target_ground_metres` with the in-run `patch_ground` evaluation at
  emission.  This kills the target's dependence on the previous build's
  MESH — the ratchet — and is a small, low-risk change; but the sidecar
  READ-BACK survives as the ring/identity carrier, so the ruling's
  retirement clause is not met.
* **R3 — one frame, single pass.**  Build the object frame ONCE, in-run,
  and refactor `post_mesh.rebake_dsf_objects` to CONSUME it rather than
  rebuild it.  The only resolution that satisfies the ruling AND
  acceptance (c), and the largest: it moves `object_anchor`'s frame
  construction across the mesh boundary.

CIRCULARITY, which any of the three must handle and which the
emission-time frame is what made visible: when a pad's own ring covers
its render datum, raising the ground raises the object with it and the
residual `AGL + base_y` is INVARIANT under every target — no pad can
close it, and such a request must fall back to the y-bake.  Measured at
HECA: 1 of 1883 requests.  This is also a candidate mechanism for the
perfbake arm's REFUTED fixed point (object_pad 689 → 723 → 736, sidecar
sha still moving after run 3) and for the measured datum drift (max
0.5958 m over datums between the three runs) — an ATTRIBUTION READ, not
a causal claim, and it wants an interventional arm before anyone acts on
it.

NOT RUN this lane, and owed when the request clause is re-chartered:
acceptance (a) determinism `--tile 30 31` pair, (b) `.obj`-rewrite
before/after count, (c) the `--count` + recorded-phase build-time pair,
(d) `check_object_pads` under the new target, (e) the row-attributed
census vs frozen 1.0.245.  None is measurable yet: **no build path
changed this lane.**  `src/auto_patch/patch_ground.py` is imported by
`tests/test_patch_ground.py` and `tools/object_pad_anchor_report.py`
only — BUILD-TIME IMPACT ZERO, confirmed by `tools/blast.py`
(0 src importers).  Test surface run once through `run_with_ledger`:
`test_patch_ground.py` (12 new twins) + `test_object_pad_anchor_report.py`
(12) + `test_harness.py` — 245 passed.  Shared repo UNCHANGED in both
measurement arms (guard armed refuse-mode, `blocked=0`, 18 and 16
allowed `.lock` churn entries).

### R3 landed, step (1) of 5 — THE OBJECT PAD FRAME (Fable ruling 2026-08-14)

Fable ruled R3, "one frame, single pass", with the refinement that the
frame's inputs are PACK data and so belong in-run pre-solve behind the
pristine-key sidecar family.  Step (1) of the ruled order is landed:

* `object_anchor._measure_structure_parts` gains a MESH-FREE reading
  (`sampler=None`).  It was already one line from being mesh-free — the
  sampler appears exactly once, for `ground_metres` — so the split is a
  guarded branch, not a rewrite.  Twin
  (`test_the_mesh_free_reading_asks_no_mesh_and_matches_the_pack_columns`)
  asserts the sampled and unsampled readings agree on EVERY pack column
  (key, base_y, base_resource, is_ground, plan_box, area, centroid,
  lat/lon) and differ only in the two ground columns.
* `src/auto_patch/object_frame.py` — `build_pad_frame(pool, geometry,
  structures)` returns `PadPart`s (contact-band triangle groups,
  `base_y`, base resource, part centroid) and `PadAnchor`s (the render
  datum + AGL).  It reuses `object_anchor`'s own builders rather than
  re-deriving them; `rendered_base_metres` is
  `_raise_cluster_pad_requests`' `seated=False` formula verbatim.
* `post_mesh.cached_pad_frame` / `pad_frame_cache_key` — the disk half,
  beside `_cached_partition_structures`, keyed on
  `object_rebake.pristine_object_fingerprint_entries` plus the law
  scalars that shape the frame.  `O4_OBJECT_PAD_FRAME_CACHE=0` disables
  the DISK half only, so the flag can never change an answer.
* `ring_covers_its_own_datum` — the circularity fallback's test, with
  its twins (step (5)'s law, landed early because it is frame-side).

Twins: `tests/test_object_pad_frame.py`, 12, including the ruled
acceptance for this step — FRAME-FROM-CACHE == FRAME-FRESH, proved by
making a fresh build raise on the second read so anything returned can
only have come off the disk — plus a re-key twin on a law scalar and a
"cache off changes nothing but cost" twin.

BUILD-TIME IMPACT: ZERO so far.  Nothing in `src/` calls
`build_pad_frame` or `cached_pad_frame` yet — they are reachable only
from the twins.  The frame becomes a build cost when step (2) wires it
in, and that is the same step that removes the rebake's own frame
construction, which is the whole basis of acceptance (c).

TEST CONTROL: `test_contracts.py::test_obj8_partition_signature
[contact_graph]` and `test_object_anchor.py::
test_kclt_eight_bake_pool_end_to_end` FAIL — and fail IDENTICALLY with
this lane's two `src/` edits reverted in the same tree (matched control,
per the standing law).  Both are pre-existing; 281 other tests pass.

OWED — steps (2)-(5) and the acceptance arms, in Fable's ruled order:
(2) `post_mesh.rebake_dsf_objects` consumes the frame instead of
rebuilding it (twin: rebake output unchanged on an identical mesh);
(3) pad emission consumes the frame with the landed `patch_ground`
targets, CORE-only under weld-or-gap (the blend annulus retires);
(4) retire the read-back — the `config.py` consumer gate, `flat_site.py`
:587, and the request/`emitted` persistence — leaving the sidecar a
write-only audit; (5) route a self-covering request to the y-bake
(the law and its twins are landed; the ROUTING is step (3)'s call
site).  Then (a) the HECA `--tile 30 31` determinism pair — which is
also the interventional test of this lane's attribution read, so it must
state explicitly whether object_pad 689 -> 723 -> 736 stabilises —
(b) the `.obj`-rewrite count, (c) the `--count` + recorded-phase pair,
(d) `check_object_pads`, (e) the row-attributed census.  Not started:
this session reached its budget at step (1), not a new blocker.

### R3 step (2) LANDED — the y-bake consumes the frame; the RATCHET reproduces

Step (2) of Fable's ruled order is landed (`7ac6a58`):
`post_mesh.rebake_dsf_objects` now reads the object pad frame instead of
rebuilding it.  What moved is THE WELDING (`obj8_partition.weld_parts`),
which is pure pack data and this pass's dominant cost — `weld_parts`'
own docstring records the 2026-07-26 profile: called from
`structure_deltas` it measured **783.6 s, 57.8 % of a +30+031 build**.
`structure_deltas` gains keyword-only `pad_frame=None`; with a frame in
hand it welds NOTHING (measured directly in the twin: **1 `weld_parts`
call without the frame, 0 with it, identical `RebakeDecision`**).

The frame carries the welding as PART LABELS — one small int per
triangle — not as triangle groups: the record goes to a sidecar, and a
group is a second copy of the pack's geometry.
`object_frame.regroup_welded_parts` is exact by construction (weld_parts
appends in input order into a dict keyed by union-find root, so parts
come back in first-appearance order with their triangles in input
order), and a twin asserts regroup == weld_parts group for group.

Two REFUSALS, because a welded part is a list of pool-frame vertex
INDICES and reading one against the wrong frame gives a plausible wrong
answer silently: `object_anchor.pool_frame_signature` (resource set +
slice starts + vertex count) must match, and the label array must cover
exactly that structure's triangle count.  Either mismatch re-welds and
says so.  Twins cover both.

**ACCEPTANCE, measured on this lane's tree at `7ac6a58`.**  Two
SEQUENTIAL HECA `--tile 30 31 --no-ledger` builds, foreground-class,
shared repo UNCHANGED in both (full-surface before/after snapshot, the
harness's own line), tags `s5step2a` / `s5step2b`:

| arm | wall | vector | mesh | tile | HECA patch body sha256 | object_pad refs |
|---|---|---|---|---|---|---|
| A | 741.0 s | 467.1 | 75.7 | 196.7 | `f562cbfeb8f990461072587bc31ef60e86aa5759c4b46b17a1aa3661dee91369` | 339 core + 350 blend = **689** |
| B | 630.8 s | 408.3 | 55.0 | 166.2 | `2f1dcfde0320f4f2158793bb34f1a878b8d5ef2c6ced52f7aaf5d8813f903a9f` | 354 core + 369 blend = **723** |

(a) **DETERMINISM: FAILS, and the RATCHET DOES NOT STABILISE.**  689 →
723 is the perfbake arm's sequence reproduced EXACTLY (689 → 723 → 736).
Arm A's patch body is **byte-identical to the frozen 1.0.245 baseline**
(`baselines/1.0.245/MANIFEST.txt`, `consol3heca`), which is what pins
the frame: arm A is the same build run 1 was.  The reading is the
pre-registered CONTROL for steps (3)-(5): step (2) is post-mesh only and
changes nothing the emitter reads, so the ratchet is confirmed to live
where the ruling says it does — in the sidecar READ-BACK that steps (3)
and (4) retire — and NOT in anything the frame-consuming rebake touches.
It does not adjudicate the circularity attribution (HECA 1 of 1883):
that still wants its own interventional arm, which is step (5)'s routing.

(b) **PACK PRISTINE: 373 `.obj` files rewritten in BOTH arms** (7589 /
7595 structures re-baked, 6 900 267 / 6 900 570 vertices offset; 1904 /
1894 cluster pad requests).  The count is STABLE across the pair.  The
charter's "171/77" is a DIFFERENT frame (the per-airport perfbake arm,
one pack); this is the +30+031 TILE arm over HEAZ+HECA+HECP and the two
numbers must not be subtracted.  The gate itself — zero rewrites for
within-band objects — is not yet meetable: it is step (3)'s emission
that removes the bake, and step (3) is not landed.

(c) **THE OWNER'S BUILD-TIME GATE: mechanism shown, exclusive pair
OWED.**  Step (2) REMOVES a construction rather than adding one, and the
removal is proved mechanically (1 weld call → 0) rather than by a wall
time.  The recorded phases above are NOT an A/B: both arms run the same
code, arm A on a COLD lane-local `Airport_mod_cache` (`mod_cache_seeded`
0 files) and arm B warm, and the standing law forbids one run per side.
An exclusive `check_build_time --runs N` pair against a `pad_frame=None`
arm is owed and belongs with steps (3)-(5), when the pad path's whole
cost is on the table.

(d) `check_object_pads` — arm B emitted 729 object-pad polygons for 354
building pads; the pad-host level census reports 354 groups (0 adopted,
13 within 3.00 m of the host, 9 no agreeing coalition, 332 no family, 0
no level).  Under the UNCHANGED law: step (2) does not touch emission,
so this is a baseline reading, not the step's acceptance.

(e) **CENSUS: zero delta, and stronger than a census.**  Arm A's HECA
patch body is byte-identical to frozen 1.0.245, so there is no row to
attribute.  Arm B's difference is the ratchet above (a pre-existing
behaviour reproduced exactly), not this step.  NOTE THE FRAME: this lane
branches at `3b21ed6`, BEFORE S7 merged to main (`8d08b41`); any census
run for steps (3)-(5) must be rebased onto — or run through a checkout
of — the S7 MERGED harness, and say which.  No census was run this
session; none was needed for a byte-identical patch.

**OWED — steps (3), (4), (5), unstarted.**  (3) pad emission consumes
the frame with `patch_ground` targets, CORE-only under weld-or-gap;
(4) retire the read-back (`config.py` ~4010 `DSF_OBJECT_OBJECT_PADS`
gate region, `flat_site.pack_seat_targets` at :587 → `object_pads`
`sidecar_path`/`load_sidecar`, `object_pads.pads_for_airport` +
`merge_emitted_records` at `driver.py:938`, and the `emitted`
persistence); (5) route `ring_covers_its_own_datum` requests to the
y-bake.  THE SITE INVENTORY for (3), measured this session so the next
lane does not re-derive it: `emit_object_pads`
(`object_pads.py:757`, called once from `pipeline.py:6635`) takes its
specs from `pads_for_airport(sidecar, icao, claim)` — replacing that
source is the whole of step (3), and it needs an IN-RUN pool
decomposition.  That decomposition must be the POST-MESH one
(`post_mesh._resolve_pack_geometry` → `discover_object_pools` →
`_cached_partition_structures`), NOT `dsf_reader.
_compute_dsf_object_buildings`': the two admit different resources
(A15's outside-the-pack refusal and I-4's multi-placement refusal are
Phase-2 only; the connector prefilter and the terrain classification are
Phase-1 only), so a frame built on the Phase-1 pools would miss the pad
frame cache key and silently cost a second frame — exactly the R1
failure Fable rejected.

Test surface run once through `run_with_ledger` over `blast --tests-for`
(post_mesh + object_anchor + object_frame, 17 files): **702 passed**,
with the two known pre-existing failures unchanged and matched-controlled
at step (1) — `test_contracts::test_obj8_partition_signature
[contact_graph]` and `test_object_anchor::
test_kclt_eight_bake_pool_end_to_end`.  `test_contracts`' own
`structure_deltas` signature row grew `pad_frame` with its reason.

### R3 steps (3)-(5) LANDED — the RATCHET IS DEAD; the coupling serves 55 of ~3,910

Steps 3, 4 and 5 of Fable's ruled order landed at `121924a`.  Pad
emission consumes the frame (`post_mesh.pad_frames_for_airport` →
`object_frame.pad_requests_from_frame` → `object_pads.specs_from_frames`),
the read-back is deleted, and a self-covering request routes to the
y-bake.

TWO GROUND AUTHORITIES, the one design decision inside the ruled
mechanism.  The RENDER DATUM's ground is the PATCH and only the patch —
the ruling's own clause, and the premise test measured it exact
(1e-6 m) at every request-carrying hosted datum; an unhosted datum keeps
the y-bake, never a DEM approximation.  The ground UNDER A PART is
patch-where-authored, ambient DEM otherwise — the MESH'S OWN RULE, and
the in-run stand-in for `MeshElevationSampler.elevation_at_or_none`,
which is what the rebake sampled.  Requiring a host under the PART would
have deleted the population outright: a pad exists precisely where
terrain is not already graded.

**ACCEPTANCE, measured at `121924a`.**  Two SEQUENTIAL HECA
`--tile 30 31 --no-ledger` builds, foreground-class, tags
`s5step3a` / `s5step3b`, shared repo UNCHANGED in both (the harness's own
full-surface before/after snapshot).

| arm | wall | vector | mesh | tile | HECA patch body sha256 | object_pad shapes |
|---|---|---|---|---|---|---|
| A | 612.7 s | 384.5 | 54.7 | 172.2 | `eb83e3c672109cf783aeae6ed1ff8b62f81e981f42c07ab7276f6e0b219c8b0c` | **59** (55 groups) |
| B | 715.9 s | 445.3 | 64.9 | 204.1 | `eb83e3c672109cf783aeae6ed1ff8b62f81e981f42c07ab7276f6e0b219c8b0c` | **59** (55 groups) |

(a) **DETERMINISM: PASSES.  THE RATCHET IS DEAD.**  The two bodies are
BYTE-IDENTICAL, and every pad number is equal arm to arm: 59 shapes /
55 groups, 484 law disagreements, 3,855 refusals, 7,565 structures /
372 `.obj` files / 6,856,707 vertices from the y-bake.  This is the
INTERVENTIONAL verdict on the step-2 attribution read.  Step (2)'s
control pair — the same tree, the same machine, the read-back still in
place — reproduced the perfbake sequence exactly (689 → 723 object_pad
refs, two different bodies `f562cbfe…` / `2f1dcfde…`).  The only thing
that changed between that pair and this one is the retirement of the
sidecar read-back and the emitted-record persistence.  **The ratchet
lived in the read-back, where the ruling said it did, and it is gone.**

(b) **PACK PRISTINE: NOT MET, and the number barely moved.**  372 `.obj`
files rewritten in BOTH arms (step-2 control: 373, both arms); 7,565
structures (7,589 / 7,595); 6,856,707 vertices (6,900,267 / 6,900,570).
The direction is right and the magnitude is ~0.3 %.  The coupling serves
55 groups; the y-bake still answers for everything else, so "zero
rewrites for objects whose pads the coupling serves" is met only for a
population too small to move the count.  WHY is (e)'s finding below.

(c) **THE OWNER'S FASTER-THAN-Y-BAKE GATE: mechanism only; the
EXCLUSIVE TIMED PAIR IS NOT THIS LANE'S.**  Two lanes cannot hold the
machine, so the timed pair joins the round's close-out timing block
under the lead.  The mechanism numbers this lane can state: `weld_parts`
calls per pool 1 → **0** (step 2, measured in its twin); the object
frame built **once** per build and read **twice** inside it (flat-site
S4 pre-solve, pad emission post-solve) through one in-process memo plus
the pristine-key disk sidecar, so the walk to it — DSF text, geometry
resolution, pool discovery — is paid once, not twice; and the retired
recompute is the whole `foot_pad_rings`/request derivation that used to
run post-mesh and be replayed from disk next build.  The wall times
above are NOT an A/B: both arms run the same code and the spread
(612.7 vs 715.9 s) is this machine's ordinary noise on a 3-airport tile.

(d) **`check_object_pads` UNDER THE UNCHANGED LAW.**  Identical in both
arms.  HECA: **484 law disagreements** (worst `pad_pull_shortfall`
8.22 m at 30.11588,31.40871 — `Airport/Hangar_Tower/asphalt_3.obj`) and
**3,855 pad requests REFUSED, worst 38.57 m against the 3.00 m relief
cap**.  HEAZ: 9,322 disagreements, all `pad_datum_unhosted`.  Pad-host
level census (`object_pad`): 55 groups — 3 adopted (worst |delta|
3.40 m), 5 within 3.00 m of the host, 5 no agreeing coalition, 42 no
family; after the relevel, 0 adopted.  The verifier needed NO change:
it compares each core vertex to the target the EMITTER recorded, which
is now the patch-relative rendered base, so it reads the base the same
relative way the coupling defines it.  No `pad_core_off_target`, no
`pad_weld_mismatch` (there is nothing left to weld), no
`pad_deformed_pavement`.

**THE FINDING THAT MATTERS, and it is a LAW-REFERENCE MISMATCH.**  The
in-run derivation raises ~3,910 requests at HECA where the rebake's
sidecar recorded 1,893 — expected, because the emission-time frame can
only measure `seated=False` (the bake decision is post-mesh), so it sees
each part's FULL residual rather than the post-seat residue.  Of those,
**3,855 are refused by `DSF_OBJECT_PAD_MAX_RELIEF_M` measured against
RAW DEM**, worst 38.57 m.  That is the instrument disagreeing with
itself: the ruling moved the pad TARGET onto the patch's own evaluated
ground, and the admissibility cap still measures that target against the
ambient DEM — at HECA our own solved surface stands tens of metres off
it (RULINGS "OBJECT PADS: RELATIVE COUPLING": mesh−DEM at anchors p50
0.82 m / p90 7.26 m, "DOMINATED BY OUR OWN SOLVED SURFACE").  So an
object correctly standing on a solved apron asks for a pad at the
apron's elevation and is refused for being far from raw DEM.  This lane
did NOT change it — the brief holds the law unchanged and `grade_law`
owns the scalar — and it is the two-instruments class: the fix is a
ruling about what the relief cap is relative to, not a tuning knob.
**Owed: an owner/Fable ruling on the cap's reference frame.**  Until it
moves, acceptance (b) cannot be met at HECA by construction.

(e) **CENSUS — row-attributed, FRAME NAMED.**  This branch forked before
S7/S8 and before the S1/S2 stack, so every census below runs through a
**MAIN-TREE harness checkout at `1388b9b`** (S7 + S8 + S1/S2 merged),
`tools/harness/census.py --no-cache` only.  CONTROL: that reader
censuses the frozen 1.0.245 HECA artifact
(`baselines/1.0.245/consol3heca.osm.gz`, body `f562cbfe…`) at **8038**
law-true — the S8 frame's own number, reproduced, so the reader is
pinned.  (Main's 7036 is the S1/S2 STACK's own build, a different code
tree; comparing this lane's patch to it would be the cross-tree
comparison the standing ruling forbids.)

| family / role pair | frozen 1.0.245 | this lane | Δ | attribution |
|---|---:|---:|---:|---|
| LAW-TRUE TOTAL | 8038 | **8033** | **−5** | |
| adjudicated airside | 1720 | **1700** | −20 | |
| `within_shape::building|building` | 52 | **31** | **−21** | site `-10187` CLOSES (below) |
| `within_shape::groundside_pavement` | 1459 | 1487 | +28 | blend-annulus retirement ripple |
| `within_shape::service_junction` | 646 | 634 | −12 | ditto |
| `transverse::service_junction` | 3196 | 3186 | −10 | ditto |
| `transverse::service_road` | 622 | 621 | −1 | ditto |
| `mid_edge_step::service_junction` | 164 | 173 | +9 | ditto |
| `within_shape::apron` | 1401 | 1402 | +1 | ditto |
| `within_shape::service_road` | 101 | 100 | −1 | ditto |
| `vertex_to_edge_step::service_junction` | 35 | 36 | +1 | ditto |
| `frontage_near_miss::building\|service_junction` | 67 | 68 | +1 | ditto |

`object_pad` rows: **0 in both** — the pads themselves carry no law row
in either frame, so every delta above is in a NEIGHBOUR.  The ±tens are
the ruled RETIREMENT working through the layout: 690 pad shapes became
59, so 631 blend plates stopped clipping, welding and decimating against
groundside and service pavement.  Named as such, per the brief: these
are blend-annulus removal rows, not a regression.

**THE TWO NAMED SITES (lead's merge-gate dossier, 43-row pad class).**
Matched by COORDINATE, because way ids are per-build:

* **Site 1 — pad `-10187` at 30.116449,31.386559 (21 rows, 2.76 m
  internal step): CLOSED.**  It is the whole of the −21.  No
  `building|building` row survives anywhere near that coordinate in
  either arm.  This is the site the dossier attributed to the pad
  mechanism, and the emission-time target closes it.
* **Site 2 — pad `-10189` at 30.121367,31.407621 (14 rows, 2.92 m) with
  ring `-13852`/`-13851` at 30.121422,31.408131 (8 rows, 2.92 m):
  UNCHANGED, both halves, row for row.**  Renumbered to `-13222` in this
  lane's build at the identical coordinate and magnitude.  Both are
  `building|building` — role `building`, which no part of the
  object-pad emission path authors — so this site is NOT the pad
  coupling's to close.  **Named for S6** (the shared-vertex /
  weld-or-gap half) per the lead's own framing.
* Also moved and not named by the dossier: `-10202` (5 rows, 0.42 m at
  30.12069,31.419369) is gone; a different building carries 5 rows at
  0.94 m at 30.121531,31.418811.  Reported, not attributed — it is a
  ripple of the same class as the table above.

**TEST SURFACE**, once, through `run_with_ledger` over `blast
--tests-for` for object_pads + post_mesh + flat_site plus the frame and
anchor twins (15 files): **809 passed**.  EIGHT failures, ALL
pre-existing and MATCHED-CONTROLLED in a clean worktree at this lane's
base `9270c8d`: `test_contracts::test_obj8_partition_signature
[contact_graph]`, `test_object_anchor::
test_kclt_eight_bake_pool_end_to_end` (both already controlled at step
1) and six in `test_flat_site_mode.py`, which this lane's wider
selection SURFACED rather than caused.

**STILL OWED.**  (c)'s exclusive `check_build_time --runs N` pair (the
round's close-out block, under the lead); the relief-cap reference
ruling above; OTHH's `--tile 25 51` arm, still blocked on the owner
provisioning that tile's cfg (unchanged since step 1); and the R19-3
`relevel_pads_to_host_pavement` pass, which under weld-or-gap now has no
weld to reconcile — it adopted 3 of 55 groups in both arms and is a
candidate for the same retirement, but retiring it is a design decision
this lane did not take.

## Staged-solve S4 — rim-pocket re-enable (lane/s4rim, 2026-08-14)

Landed: the retirement of `O4_RIM_PRESOLVE_ABSORB` (config.py, gap_fill.py)
per the owner ruling 2026-08-13 (RULINGS "OTHH −639 ADJUDICATED").  The
rim-pocket default stays OFF — the flip was measured in a lane arm only.

- Tests: only the files covering the change were run, once
  (`test_gap_fill_spine.py`, `test_one_solve_gap_spine.py`,
  `test_solve_stage.py`, `test_geometry_freeze.py`; 72 passed).  No blast
  set, no full suite (pre-ship mode).
- Battery: HECA + OTHH only.  CYXY, KCLT, SPJC, SPLP not censused under
  the retirement (it is byte-inert with pockets OFF — proven at HECA by a
  replay byte-identical to the clean-tree build, `a9496e142bff`, not by a
  five-airport sweep).
- NOT measured: whether the pockets-ON airside channel behaves the same
  at the other three battery airports; only HECA and OTHH were armed.
- INSTRUMENT DEFECT FOUND, NOT FIXED: `solve_cut.py` capture→replay does
  NOT reproduce its own build at OTHH on this tree (build `232e028febf6`
  vs control replay `6a0a832588c6`; object_pad 3036 vs 2771, graded_strip
  100 vs 171, within_shape airside 51 vs 686), while HECA reproduces byte
  for byte.  OTHH acceptance was re-run as two full BUILDS instead.  The
  divergence is unattributed and belongs to whoever owns the instrument.
- Timing: not measured (no timing claim made anywhere in this lane).

---

## S6 — transition-machinery retirement (weld or gap), lane `lane/s6weld`

**PRE-EXISTING TEST FAILURE, carried not caused.**
`tests/test_strip_heal_law_v4.py::test_the_pass_order_is_unchanged_by_the_law`
fails on the CLEAN tree at `1faf907` as well as in this lane — proved by
running the identical 30-file `blast --tests-for` selection in a control
worktree (`lane/s6ctl`): control **1 failed / 792 passed**, lane at close
**1 failed / 792 passed**, the same test both times. It asserts that
`inspect.getsource(pipeline.build_airport_pavement)` contains
`blend_cross_strip_seam_steps`, `_heal_emitted_band_tears` and
`emit_stacked_conflict_walls` in order; the three now live in a nested
`_strip_reconcile_passes` that the assertion no longer sees, so `order`
comes back empty. The ORDERING LAW it guards is still real — the test
needs re-pointing at the nested function, which is a test fix this lane
did not take because it is not S6's mechanism.

**NOT RUN (pre-ship mode).** Full battery / full suite; per-change timing
(the retirement removes emitter work, so it cannot regress the budget in
the direction the law polices, but no `--runs N` pair was measured).

**STILL OWED.** The owner's in-sim pass, with VHHH's coast explicitly on
the list — this lane's seawall evidence is the read-only admission
instrument (47 wall lines / 54 734.3 m, byte-identical across the arms),
not a rendered tile. The routed items in `tmp/s6_retirement_results.md`
§7 (groundside absorption cost, the airside `strip_seam_tear` exposure,
KCLT site (c)) are ROUTED, not verified closed.

---

## S5c — PAD RELIEF CAP RE-FRAME (lane/s5cap, 2026-08-14): **STOPPED at the ruling's own pre-registered gate**

RULINGS "PAD RELIEF CAP MEASURES AGAINST THE PAD'S OWN GROUND, NEVER RAW
DEM" (Fable 2026-08-14) moved `DSF_OBJECT_PAD_MAX_RELIEF_M`'s reference
off raw DEM and pre-registered a STOP: *if the re-framed population shows
pads standing far above their LOCAL ground at real sites (tower-class
artifacts), stop with the sites.*  **It fires.**  The mechanism is built,
twinned and green; it is NOT merged.

**WHAT LANDED (lane/s5cap, not merged).**  The reference is the value the
emission path already computed: `object_frame.pad_requests_from_frame`
carries `ground_reference_metres` (the MEDIAN of the group's parts'
`surface_ground_at` — patch where the patch authors, ambient DEM where it
does not, the same two-authority rule the requests use), the emitter
READS it instead of sampling the DEM at the ring centroid (`dem_at` is
gone), records it beside the pad, and `verification.check_object_pads`
holds the cap on the emitted target against that same recorded number.
`grade_law.object_pad_relief_m` / `_admissible` keep their signature and
VALUE; only their reference is re-worded.  The frame's own
`over_relief_cap` flag (the WORST PART's residual against the ground under
IT) is deliberately UNCHANGED and still refuses beside the re-framed cap:
it is already an in-run local measurement, and folding it in would widen
admissibility, which is not this lane's charter.  **That choice is owed a
Fable ruling** — it is why the population moved by 10 and not by 3,846.

**THE MEASUREMENT (HECA `--tile 30 31`, control `s5capctl` at `1faf907`
body `934b939c12b4`, arm `armtile1/2` body `d119f84cf8db`).**

| | control | arm |
|---|---:|---:|
| pads SERVED (records / shapes) | 55 / 59 | **65 / 69** |
| pad requests REFUSED (verify) | 3856 (worst 38.61 m) | **3846** (worst 37.76 m) |
| pad law disagreements | 485 | 484 |
| `.obj` files re-baked (acceptance (b)) | 372 | **372** |

**PREMISE REFUTED.**  The S5v3-c2 entry attributed the 3,855 refusals to
the raw-DEM reference.  With that reference GONE, **3,846 are still
refused** — by the frame's residual test against the pad's OWN in-run
ground.  The binding constraint was never the DEM; it is that HECA's
shared-datum objects render tens of metres above the ground under their
parts.  Acceptance (b) is therefore UNMOVED (372 → 372): the 10 newly
served objects are still y-baked, so pack-pristine is not approached by
this change either.

**THE STOP, with its sites.**  Local relief of every SERVED pad shape
(|emitted altitude − its own ground at the plate|, read with production's
`patch_ground` + `_sample_dem`; approximation stated: evaluated at the
plate's representative point, where the emitter evaluated it under the
request's PARTS):

| | control | arm |
|---|---:|---:|
| p50 / p90 / max (m) | 1.090 / 2.737 / 9.373 | 1.407 / **7.283** / 9.373 |
| shapes over the 3.00 m cap against their own local ground | 1 of 59 | **11 of 69** |

All EIGHT new pads sit in ONE cluster on HECA's western apron —
30.10883,31.38706 · 30.10918,31.38772 · 30.10951,31.38906 ·
30.10953,31.38915 · 30.10953,31.38917 · 30.10955,31.38926 ·
30.10955,31.38928 · 30.10957,31.38937 · 30.10958,31.38939 ·
30.10960,31.38948 — emitted at 99.4–100.6 m over ambient ground of
92.3–93.6 m, i.e. **+5.6 to +8.0 m plates with a gap (no blend annulus
survives weld-or-gap) at their edge**.  The mechanism is exact: the
objects' parts stand on our SOLVED pavement, so the cap's reference is
the pavement's value, while the plate itself is CLIPPED out of that
pavement and lands on the ambient ground beside it.  Pedestals, not
towers, but the same class the STOP names.  The control's single
over-cap shape (−9.373 m at 30.11591,31.40881) is pre-existing and
present in both arms.

**OTHH** (airport arm only — `--tile 25 51` is still blocked on the
owner provisioning that tile's cfg): 145 → **146** pads (182 → 184
shapes); local relief p50 0.545 → 0.547, p90 3.139 → 3.127, max 4.368
unchanged, 20 over-cap shapes in BOTH arms.  No new class.

**DETERMINISM.**  Two SEQUENTIAL HECA tile arms produced a
**byte-identical** DSF (`90f00b8a53f4…`) — the ratchet stays dead under
the bigger population.

**CENSUS** (harness `census.py`, same reader both sides, control body
`934b939c12b4`): LAW-TRUE **7067 → 7070 (+3)**, airside_for_acceptance
1734 → 1737.  Row-level (`census_rows_diff.py`): 7067 EXACT, 0 GONE, 3
NEW, all `within_shape::apron|apron` AIRSIDE — |de| 1.690/1.690/0.080 m,
grades 1.535 %/1.535 %/2.405 % — at 30.130482,31.410557 (ways
-10250, -12682) and 30.133333,31.409827.  Those sites are ~2 km from
every new pad, so they are NOT the pad plates themselves; they are the
pad group's ripple through the shared emit-decimation / on-edge weld
passes.  **Unattributed beyond the class — a STOP in its own right under
the brief's airside clause.**

**TESTS**, once, through `run_with_ledger` (`s5cap-pad-tests`) over
`blast --tests-for` for object_pads / object_frame / verification /
grade_law's pad readers (6 files): **182 passed, 1 failed** —
`test_pad_host_pavement_level::test_the_pad_law_re_asserts_after_the_late_projection`,
a source-inspection test, **pre-existing and matched-controlled** in the
clean `s5capctl` worktree at `1faf907`.  New twins: the cap reads the
emission reference (a pad 36 m off raw DEM and 1 m off its own ground is
SERVED), the refusal boundary at the cap value on that same ground, the
two-authority split, and the validator reading the recorded reference
rather than the raster.

**OWED before this can land:** the owner's verdict on the pedestal class
above; a Fable ruling on whether the frame's worst-part `over_relief_cap`
belongs in the re-framed cap; attribution of the +3 airside apron rows;
and OTHH's tile arm, still blocked on that tile's cfg.

### S5c FINAL INCREMENT — the reference is THE PLATE'S LANDING GROUND (owner 2026-08-14)

RULINGS "PAD CAP REFERENCE IS THE PLATE'S LANDING GROUND": refuse the
towers, keep the feature.  `ground_reference_metres` is now the
two-authority read (`surface_at` — patch where authored, ambient DEM
otherwise) evaluated WHERE THE PLATE LANDS: at the representative point
of each surviving CLIPPED core, taken at the WORST piece, compared
against the value actually written (`pulled`).  It can only be taken
there, after the pavement clip and the erosion, so the admissibility test
moved to that point in `emit_object_pads`.  The frame's
`over_relief_cap` stays exactly as it was and refuses first: parts-vs-host
and plate-vs-landing are different questions and they COMPOSE — the code
agrees with that composition, and `object_frame` no longer carries a
reference field at all.  Emitter and verifier read the one recorded
number.

**HECA `--tile 30 31`** (control `934b939c12b4` → arm `6b09b21c5420`):

| | control | parts-median (STOPPED) | **landing (this)** |
|---|---:|---:|---:|
| pads served (records / shapes) | 55 / 59 | 65 / 69 | **53 / 53** |
| requests refused | 3856 | 3846 | **3858** |
| local relief p50 / p90 / **max** (m) | 1.090 / 2.737 / 9.373 | 1.407 / 7.283 / 9.373 | 1.084 / 2.700 / **3.000** |
| shapes over the cap vs own landing ground | 1 of 59 | 11 of 69 | **0 of 53** |
| `.obj` files re-baked | 372 | 372 | **372** |

**Zero tower-class shapes, max EXACTLY the 3.00 m cap — by construction.**
The eight western-apron pedestals are refused, and so is the control's
own pre-existing −9.373 m outlier at 30.11591,31.40881: served is 53, not
the ~57 expected, because the landing test also condemns two pads the
raw-DEM test had passed.  Determinism: two SEQUENTIAL tile arms,
byte-identical DSF `bf43a91719c0…`.  Acceptance (b) is UNMOVED at 372 —
the y-bake is decided post-mesh on its own threshold and does not consult
the pad outcome; closing (b) is a separate mechanism, not a cap question.
The two dossier sites are unchanged-closed (site `-10187` still carries no
`building|building` row; site 2 still row-for-row present).

**OTHH** (airport arm): **byte-identical to the control**, body
`ac15b9595d0d` both sides, 145 pads / 182 shapes — the landing reference
changes nothing at a flat airport.

**STOP-2 (the airside apron rows) PERSISTS — named, not chased** (owner
instruction: do not chase past cap).  Census LAW-TRUE **7067 → 7081
(+14)**, airside_for_acceptance 1734 → 1748; 7058 EXACT, 2 MOVED
(0.020 m, Δ|de| 0.000), **7 GONE, 21 NEW**, every one
`within_shape::apron|apron` but two `junction|junction`, all AIRSIDE and
all in ONE apron area away from the pads: NEW worst
3.030 m ×2 @30.135128,31.409179 (ways -11908/-12165), 1.690 m ×2
@30.130482,31.410557, then 0.900 @30.134018,31.409578, 0.800
@30.131287,31.410662, 0.760/0.700/0.650/0.610/0.550/0.490
@30.13190-30.13196,31.41035-31.41043, 0.710/0.500/0.230
@30.133109-30.133336,31.409822-31.409914, 0.360 @30.121384,31.414790,
0.230/0.170 (junction) @30.133653,31.409990 and 30.133652,31.409969,
0.100 @30.131373,31.410588, 0.050 @30.133651,31.410066; GONE worst
3.560 @30.129778,31.411799, 2.560 @30.119585,31.409529, then 0.450, 0.280,
0.220, 0.170, 0.070.  Grades are marginal (1.12-8.23 %).  Left for the
round's close-out row adjudication.

**THE OWNER'S INTENT METRIC — NO-MODIFICATION RATE** (production's own
frame derivation over the built patch; the y-bake decides post-mesh on
its own minimum delta, so this attributes "modified" one step earlier
than the bake and the build's `[object-anchor]` line is quoted beside
it):

| | OTHH (flat) | HECA (relief × shared datum) |
|---|---:|---:|
| ground-touching parts | 33,749 | 9,322 |
| parts with NO in-run ground (y-bake path) | 9,639 | 14 |
| parts NEEDING NOTHING (≤ 0.15 m) | **15,984 of 24,110 = 66.3 %** | **12 of 9,308 = 0.1 %** |
| parts over the floor | 8,126 = 33.7 % | 9,296 = 99.9 % |
| STRUCTURES with any over-floor part | **723 of 5,362 = 13.5 %** | 2,412 of 2,426 = 99.4 % |
| `.obj` resources with any over-floor part | 205 of 529 | 237 of 240 |
| \|rendered base − own ground\| p50 / p90 / max | 0.053 / 0.311 / 14.470 m | **11.507 / 28.686 / 37.764 m** |
| y-bake (build log) | not measurable — no tile arm | 7,642 structures / 372 `.obj` |

**The expectation HOLDS at OTHH**: 86.5 % of its structures need nothing
at all, and the median object sits 5 cm off its own ground.  HECA is the
contrast and it is not marginal — the median object renders **11.5 m**
off the ground under it, which is why 3,858 requests are refused by a
3 m cap and 372 `.obj` files are rewritten: no pad mechanism reaches that
class, and the number to question there is the pack's shared-datum
arithmetic, not this cap.  **VHHH is OWED to the round close-out** (no
existing arm, and its tile cfg is not provisioned here — not fought, per
the instruction).

**TESTS**, once, through `run_with_ledger` (`s5cap-pad-tests-landing`):
**183 passed, 1 failed** — the same pre-existing, matched-controlled
`test_the_pad_law_re_asserts_after_the_late_projection`.  New twin:
`test_a_plate_landing_off_its_objects_pavement_is_refused` builds HECA's
western apron in miniature with real geometry (parts on a solved apron at
40 m, ring clipped out of it, plate landing on 5 m DEM) and asserts the
refusal at >30 m.

**OWED / NOTED.**  (1) `pad_core_off_target 3.51 m` is now the worst law
disagreement (477, down from 485): the R19-3 `relevel_pads_to_host_pavement`
pass adopts a host level (2 groups here) WITHOUT updating
`emitted_target_metres`, so the verifier reads the pad it moved as off
target — pre-existing, previously ranked under the 8.27 m pull-shortfall
that is now refused away, and another argument for that pass's retirement.
(2) The scratchpad instruments used twice each here
(`pad_relief_read.py`, `pad_modification_census.py`) are OWED promotion
into `tools/` with index entries and twins if this mechanism lands —
promote-on-reuse, RULINGS `7e90032`.  (3) OTHH's tile arm and VHHH remain
blocked on tile-cfg provisioning.

---

## S1d (staged-solve round, lane/s1d, base d4c8485)

Control arms, all through the harness entries, guard clean
(`write_guard_blocked: []`): HECA `5d12d1ce4b5a` (3211 shapes, law-true
7221, airside 1711), CYXY `0de9dbec1438` (462, 319, 68), OTHH
`3850b8a43867` (2186). Matched pre-edit test control on this tree: 130
passed / 0 failed; post-change 139 passed / 0 failed.

**ITEM 1 — solve_cut capture→replay at OTHH: ATTRIBUTED, NOT CLOSED.**
The docket's suspicion (S5's in-run pad-frame reads + an unbumped
`capture_version`) is REFUTED as stated: S4 measured the divergence at
`1388b9b`, and `git merge-base --is-ancestor 1faf907 1388b9b` is FALSE —
`object_frame.py` does not exist at S4's tree, so S5's pad frame cannot
have caused it. At S4's tree the pad emitter still read the cross-build
request sidecar `o4_object_foot_pads.json` (the ratchet class), which
S5's `1faf907` retired and which is now railed twice
(`test_the_sidecar_reader_is_gone_from_the_emission_path`,
`test_no_terrain_module_reads_the_pad_sidecar`).
On current main the divergence PERSISTS with a different mechanism:
HECA reproduces byte-for-byte (`5d12d1ce4b5a`, 334.7 s) but OTHH does
not (build `3850b8a43867` / replay `5bfafd6d8318`, 2186 vs 2301 shapes).
Attributed by differential: the replay's DEM is NOT the build's DEM —
relief 3.71 → 3.12 m, sea-excluded 11 % → 2 %, and the flat-site pack
read moves from `off 0.03 m / spread 0.53 m` to `off 0.32 m /
spread 1.78 m`, which drives object pads 145 → 191 (182 → 226 polygons).
The build runs the harness-verified production DEM frame
(`airports_layer=True`, insets 100 %); the replay re-runs DEM prep inside
phases [5]+[6] and gets a different surface. `tile_dem` is a captured key
but is None for a `--patch-only` build, so the DEM the solve actually
uses is created AFTER the boundary and no key set can cover it as it
stands. OWED: a Fable-scoped boundary change (capture the prepared
airport DEM, or make the replay adopt the build's DEM frame) plus a
`CAPTURE_VERSION` bump. NOT attempted here — it changes
`solve_and_finalize`'s signature and is a design decision.
LANDED instead: `tools/solve_cut.py` now enforces the BUILD-CWD LAW via
`build_airport.require_build_cwd` (one implementation, never a second
spelling), twin `test_a_replay_from_the_wrong_cwd_refuses`. This closes a
real hole that bit this lane: `O4_File_Names.resource_path` is
`os.path.abspath(".")`, so a replay from the wrong directory lost the
engine's resources, DEM prep failed with FileNotFoundError, the run fell
back to the standalone DEM, and the replay emitted 2,027 shapes and
reported DIVERGED — an operator error indistinguishable from an engine
defect.

**ITEM 2 — rim-pocket writer: BOTH HALVES LANDED, POCKETS STAY PARKED.**
(a) `gap_fill._gap_host_stage` decides a gap face's stage from its
ENCLOSURE HOST, by identity against the lawful-airside list (no role
literal; `ROLE_BUILDING` falls to stage B by non-membership, and the
docstring records why `solve_stage.stage_of_roles` is the right fold for
the wrong question). `construct_gap_fill_presolve` stamps `host_stage`
at mint; `solver_primitives._build_gap_spine_constraints` consumes it and
raises `UntaggedConstraintError` rather than defaulting.
(b) `solve._receiver_nodes_from_roles(roles, stage_b_nodes=())` admits
role-less stage-B spine vertices, fed by the new
`solver_primitives.gap_spine_stage_b_nodes` (canonical-key resolved) at
both `solve_route_profile` and `final_grade_projection`.
BYTE-INERT AT THE SHIPPED DEFAULT, proved not claimed: the HECA replay
with pockets OFF on the changed tree is `5d12d1ce4b5a`, byte-identical to
the control build.
RE-FLIP ARM FAILS ACCEPTANCE (b). `O4_GAP_FILL_RIM_POCKETS=1` at HECA:
law-true 7221 → 7305, airside_for_acceptance 1711 → 1779 (+68); row join
NEW 492 / GONE 408 / net +84, of which ~299 NEW airside
(257 `within_shape::apron|apron`, 22 `junction|junction`, 20 transverse);
259 of 317 NEW airside rows lie >50 m from every gap-fill candidate
(median 119 m) — S4's off-face signature, reproduced.
RESIDUAL MECHANISM, NAMED AND MEASURED: at HECA the construction yields
229 spines tagged **138 STAGE_A / 91 STAGE_B**. The stage-B half is
correctly demoted; the writing population is the 138 that keep STAGE_A
through the "one airside arm on the rim ⇒ airside is king" branch. A rim
pocket is by definition NOT airside-enclosed (that is what distinguishes
it from an interior ring of the airside union), so the open design
question is whether a rim pocket should be stage B UNCONDITIONALLY. That
reinterprets "airside is king" for an enclosure host and contradicts the
twin `test_one_airside_arm_makes_the_rim_pocket_stage_a`, so it is
ROUTED TO FABLE/OWNER rather than decided in-lane (attempt cap reached;
intent questions route to the owner). Pockets remain default OFF.

**ITEM 3 — open couplings 9/10/12/21: NOT STARTED.** Budget went to
items 1, 2 and 4. The dossier entries (`tmp/s1_attribution.md` in the
lane/s1freeze worktree) and the spec's own file:line pointers stand
unchanged; no code was touched, so nothing is half-done. Expected
byte-inert at HECA per S1c's six.

**ITEM 4 — row-adjudication annex: DELIVERED**, `tmp/s1d_row_annex.md`.
Free-end outlier `30.1119707,31.3731240` CLOSED (no row in the control).
The UNATTRIBUTABLE junction way -11890 is now attributed (`within_shape
junction|junction`, airside, 1.84 % vs the 1.5 % law-true cap). The
frontage row persists (`frontage_near_miss`, apron|building, 7.94 %).
S5c's `+14` ruled LAWFUL BOUNDARY CHURN: 71 of the control's airside rows
are `apron|apron` sitting inside 0.05 pp of the 1.5 % cap, so any lawful
re-emission reshuffles membership — that band is recommended as its own
docket line, since it will make every future arm's airside delta noisy.

**OWED AT CLOSE.** OTHH and CYXY censuses on the final tree (only HECA
was censused both ways here); the determinism spot-check (sequential
HECA tile pair) was not run; item 3.

## S4rim2 (staged-solve round, lane/s4rim2, base c0d7ca6)

THE CHANGE (RULINGS 2026-08-14 "RIM-POCKET SPINES ARE UNCONDITIONALLY
STAGE B"): `gap_fill._gap_host_stage`'s conditional "one airside arm on
the rim ⇒ STAGE_A" branch is RETIRED — the function is now
`_gap_host_stage(rim_pocket)`, `STAGE_B if rim_pocket else STAGE_A`, with
no geometry test and nothing about the rim's composition able to reach
the verdict. The retired midpoint scan survives as REPORTING ONLY
(`_rim_airside_arm_mids`) behind one build census line. Twin
`test_one_airside_arm_makes_the_rim_pocket_stage_a` is replaced by
`test_an_airside_rim_arm_is_read_not_written_still_stage_b` (assertion
intent changed BY the ruling, cited in its docstring) plus a new limit
case `test_an_all_airside_rim_pocket_is_stage_b_too`.

BYTE-INERT AT THE SHIPPED DEFAULT, proved not claimed: HECA control on
the changed tree is `5d12d1ce4b5a` (3211 shapes), byte-identical to
S1d's control artifact. Guard clean, shared repo UNCHANGED on all three
arms.

RE-FLIP ARM STILL FAILS ACCEPTANCE (b) — POCKETS STAY PARKED.
`O4_GAP_FILL_RIM_POCKETS=1` at HECA (`3c084a212d0f`, 3286 shapes):
law-true 7221 → 7139, airside_for_acceptance 1711 → 1704. Off-face
signature REDUCED but not gone: 73 of 106 NEW airside rows lie >50 m
from every emitted spine (S1d: 259 of 317), median 82.6 m. The decisive
read is the value equality, not the row count: 5,066 of 17,677 SHARED
airside vertices (canonical 11-decimal join) carry a different elevation
— apron 1,436, junction 2,206, graded_strip 937, building 441 — worst
0.33 m, median 75 m from the nearest pocket spine and up to 734 m away.
Runway and runway_clearance: ZERO moved.

WRITER NAMED (S1's pre-delegated "emitted GEOMETRY, not a solver
variable" branch): the stage tag is not the leak. With pockets ON
`graded_strip` gains 8,198 vertices and loses 824 and `object_pad` loses
409, and `graded_strip` is AIRSIDE-HOSTED (not in `GROUNDSIDE_ROLES`),
so the gap faces and the adjacent-ground bands rebuilt over the pocket
regions enter STAGE A's OWN constraint system by the stage rule "a
construct takes its HOST's stage". The tag decides which stage a
constraint belongs to; it cannot stop the feature changing what stage A
solves. Corroborating channel, same magnitude order: 36 of 214 building
pad seats move (median 0.06 m, max 0.28 m) — the known pad→apron weld
channel. Family to cut at the stage boundary: `graded_strip`
(gap-fill faces + adjacent-ground bands over pocket regions) and
`object_pad`.

ANSWERED IN ONE LINE (charter question): NO genuinely airside-enclosed
gap reaches the rim-pocket path at either battery airport — the new
census line reads HECA 210 pockets / 54 with ≥1 airside rim arm / **0**
airside-enclosed all round, OTHH 99 / 41 / **0**. Structural, not
incidental: a rim closed all the way round by airside IS an interior
ring of the airside union and `_gap_detection_polys` claims it as an
ENCLOSED gap (stage A) before the rim-pocket detector ever sees it.
So the ruling's letter moves no rows at the battery airports.

OTHH ARM CLEAN (`a1a2e8f024fb`, 2238 shapes, vs control `3850b8a43867`):
airside_for_acceptance 5668 → 5668 UNCHANGED; groundside 195 → 206,
adjudicated 5863 → 5869 (+6).

SKIPPED / OWED. (1) The knoll is read at PATCH level only — control has
no patch surface within 15.8 m of 30.1136676,31.4086362; the arm emits a
`gap_interior_ring` 1.72 m away at 93.58–95.48 m, a spine at 92.62 m and
a `gap_fill_spine` graded_strip face at 92.76–103.52 m (the 93.72-class
read), and the law rows within 120 m are unchanged (114 → 114, worst
grade 403.39 %, worst |de| 9.15 m). S4's MESH number (106.3 → 93.72) is
mesh-side and NO tile was built. (2) Only HECA was censused both ways;
OTHH has an A/B census but no `--rows-json` row join; CYXY/KCLT/SPJC/
SPLP were not built. (3) Tests: the blast-selected 9 files +
test_projection_partition + test_solve_capture, once, ledgered (195
passed / 0 failed) — no full suite, no blast sweep. (4) No timing arm;
the pockets-ON HECA build cost 421.8 s vs the control's 376.9 s but the
three arms shared the machine, so that is not a timing claim. (5) The
two lane measurements (off-face distance; airside value join by
canonical key) are scratchpad one-offs on FIRST use — a second use
promotes them into `tools/` with index entries, and the airside value
join is the stronger candidate: it answers "did airside move" as an
EQUALITY where a census A/B can only answer it as a count.

## 2026-08-14 — ENGINE IMAGERY HARDENING (lane/imgharden)

Imagery deletion now guards on the ERROR CLASS: a permission failure is
evidence about the ACCESS, never about the artifact. Attribution map:
`tmp/imagery_delete_map.md` (committed). Eight delete sites classified;
S1 `O4_Tile_Utils.delete_incomplete_imgs` is the 2026-08-12 KCLT site.

DEFERRED, with reasons:

1. **No tile build.** Every changed path is file handling and is covered
   by unit twins (`tests/test_imagery_permission_hardening.py`, 7 tests,
   each verified to FAIL against the pre-change tree — the denied-save
   twin reproduces the incident, printing `Deleted: ...jpg`). The blast
   selection (8 files) ran once through the ledger: 66 passed. No full
   suite, no acceptance build, no in-sim arm (PRE-SHIP MODE).
2. **S3, the geotiff pre-clean** (`O4_Imagery_Utils.convert_texture`,
   the `os.remove` of an existing `Geotiffs/<name>.tif` before
   regenerating it). NOT permission-triggered — `os.path.exists` answers
   False under EPERM, so nothing is deleted — but if the gdal conversion
   then fails (the 10-try loop only logs), the user's previous geotiff
   is already gone. Out of this lane's error-class scope; owed as a
   write-to-temp-then-replace change.
3. **The `grouped` imagery-dir key mismatch.** `download_jpeg_ortho`
   keys `incomplete_imgs` by `Path(file_dir).parent.name`, which is
   `long_latlon` for providers with `imagery_dir = grouped`, while
   `delete_incomplete_imgs` looks the tile up by `short_latlon`. For
   those providers the cleanup silently never fires. Pre-existing, in
   the SAFE direction (a stale white-squared file is kept, not user data
   deleted), so it is recorded rather than changed here.
4. **`_shared_tile_cache_get`'s bare `except Exception: pass`** turns a
   permission-denied map-cache read into a silent miss. It deletes
   nothing, so it is outside the deletion law; it does make a denial
   window quieter than it should be. Owed as a logging change.

- 2026-08-14 lane/cfgdefaults (per-tile cfg DERIVED from global defaults,
  ruling 2026-08-14 "A TILE WITHOUT A PER-TILE CFG USES GLOBAL DEFAULTS"):
  tests were `tests/test_harness.py` once through the run ledger (227
  passed) — `blast --tests-for` selects 0 files for
  `tools/harness/build_airport.py` (it has no direct importers; the twins
  load it dynamically), so the covering file was chosen from the index's
  co-change signal (75%). UNPAID: (1) NO completed tile arm — the OTHH
  `--tile 25 51` run gets past the missing-cfg refusal and stops at the
  EMPTY `default_website` gate, so steps 1-4 were never exercised on a
  derived cfg and no tile product exists to census; (2) the
  `derived → present → was_derived` path is twin-covered but never seen
  across two REAL builds of one build dir; (3) `tools/profile_tile_build.py`
  shares the amended helper and was not run (comment-only edit there).

## S1e (lane/s1e, 2026-08-14) — value-preserving refinement + the single projection

- **Timing re-measurement DEFERRED to the round's timing block.** The
  ruling itself schedules the timing block after this lands.  Arm wall
  times were taken with other builds running and are single runs, so they
  are NOT quotable (standing law: `check_build_time --runs N`, exclusive,
  foreground).  Indicative only: HECA control 397/440 s, late-only 384 s,
  mid-only 365 s; OTHH control 692 s (three-way parallel), late-only 308,
  mid-only 300; CYXY 41 / 35 / 33.  The 2026-07-18 mid-off figures
  (OTHH −64 s) were measured under the OTHER collapse direction and do
  not transfer.
- **HECA determinism pair NOT run** (one HECA build ≈ 6 min; the lane's
  budget went to the two collapse directions × three airports).
  Determinism was proven at CYXY instead: three sequential builds of the
  late-only tree — two with `O4_GEOM_SEAM_AUDIT=1`, one without — all
  emit `58cc46ab7bf9`.  A HECA sequential pair is owed at the round's
  consolidated arm.
- **Tile arms NOT run.** All arms are `--patch-only`.
- **Full suite NOT run** (PRE-SHIP mode).  Run once through the ledger:
  the S1e twins plus the projection/partition/pad/harness files directly
  covering the change (335 passed, 1 PRE-EXISTING failure — see below) and
  the coupling rail twins (82 passed).
- **PRE-EXISTING failure, matched control taken:**
  `test_r17_band_clamp_last_author.py::test_no_elevation_author_runs_after_the_seal`
  fails identically on clean `main` at `0802aac`.  It inspects
  `build_airport_pavement` (pipeline.py 869-3802) for a string that lives
  in `solve_and_finalize` (from 3803), so the R17-1(b) last-author
  invariant it claims to guard structurally is unguarded.  Filed
  separately; not caused by this lane.

## S1f (lane/s1f, 2026-08-14) — the +89 adjudication and the docket

- **The convergence arm is a REFUTATION arm, not an acceptance arm.**
  `s1f_conv_cyxy` (`5dd542654f0c`) and `s1f_conv_heca` (`c2ae6a556821`)
  were built to test branch (b) and the change was reverted on the
  measurement.  Their bodies are evidence, not products; nothing in the
  lane's committed tree produces them.
- **Timing NOT measured, per the standing suspension.**  Indicative only,
  single runs with other builds on the machine: the projection cost 17.4 s
  at HECA before the reverted patience change and 23.8 s after; the arms
  ran 380–404 s (HECA) and 33–35 s (CYXY).  Not quotable.
- **OTHH arm: PAID, and it paid the CYXY one too.**  The OTHH arm built
  on the refuted convergence tree emits `271f5e2df731` — S1e's own
  mid-only OTHH body, byte for byte — and CYXY emits `5dd542654f0c` on
  both the convergence and the committed tree.  The reverted change is
  therefore byte-inert at both airports, so the committed tree's CYXY and
  OTHH bodies are S1e's by measurement.  Only HECA ever moved.
- **HECA determinism pair NOT run** (still owed from S1e; one HECA build
  ≈ 6.5 min).  Identity was proven instead by REPRODUCTION: this lane's
  HECA build with the seam audit armed emits `3ab5a8dfae80`, S1e's own
  mid-only body, and its CYXY control emits `5dd542654f0c`.
- **Tile arms NOT run.**  All arms are `--patch-only`.  The sequential
  HECA tile pair the round's acceptance asks for is unpaid.
- **Full suite NOT run** (PRE-SHIP mode).  `blast --tests-for` over the
  changed files selected 30 files, run once through the ledger: 788
  passed, 5 xfailed (all pre-existing, kill-half §2 exposed consumers).
- **Items 2, 3, 4, 5 are ATTRIBUTED, NOT IMPLEMENTED**, each with its
  minter named by file:line in `Ortho4XP/tmp/s1f_dossier.md`.  In
  particular the solve-capture DEM leak is unclosed, so **OTHH replays
  remain not quotable** (RULINGS 2026-08-14).
- **Item 6's residual question is unmeasured:** whether a near-miss law
  edge was ever built for building22's pad against apron vertex −2409
  needs `_fp_law_counts` dumped from an instrumented run
  (`solve.py:6764`).

## 2026-08-14 — FINAL ARCHITECTURE DOCKET (lane/finalarch, Fable implementation)

The five S1f architecture items, implemented/adjudicated on
lane/finalarch (27885d9 items 2+3; 5c2ad4b items 1a/1b/4/5; bcd762b
item-2 adjudication; d2e7da3 item-1b adjudication).  Full dossier:
`tmp/finalarch_dossier.md`.  Arms: fa_0/fa_A/fa_B (controls),
fa_G_{heca,othh,cyxy} (acceptance), OTHH+HECA capture→replay, HECA
tile pair.  Shared repo UNCHANGED on every arm.

DEFERRED, with reasons:
1. Tests ran ONCE through the ledger (O4_ROUND_TAG=finalarch,
   blast-selected 82 files): 1,774 passed / 2 failed — both failures
   reproduced on the UNCHANGED cacae39 sources (matched control, same
   selection): pre-existing (test_pad_host_pavement_level
   ::test_the_pad_law_re_asserts_after_the_late_projection;
   test_single_graph_acceptance::test_solver_validator_same_edge_budgets
   @CYXY).  No full suite, no blast sweep (PRE-SHIP).
2. KCLT/KSTJ/SPJC/SPLP arms not built — the docket names HECA/CYXY/
   OTHH; the consolidated arm owns the rest.
3. The 1,631-inverted-tube COUNT was not re-measured as a headline
   number: the mechanism is closed structurally (stage-aware anchors,
   conformance recorded per site in layout._svc_cross_stage_conform)
   and the emitted-surface effect is row-attributed in the censuses;
   the corridor-profile conflict count on the next instrumented arm
   is the cheap follow-up read.
4. No timing arm (timing stays with the round's one timing block).

## 2026-08-14 — MODE PLUMBING for the constructive solve (lane/k2mode)

The `solve_model` cfg key, its one reader (`src/O4_Solve_Model.py`),
the harness frame/variant recording and the two UI selectors
(constructive-solve spec, §"Mode plumbing").  Verified: 619 tests in
one blast-selected ledger run (`O4_ROUND_TAG=k2mode`, 16 files, all
pass); two HEAZ arms (iterative + `O4_SOLVE_MODEL=constructive`) —
ledger MISS across modes as required, patch bodies and `.axes.json`
sidecars BYTE-IDENTICAL, censuses identical (269 rows / 262
adjudicated / 23 families both sides); shared repo UNCHANGED on both
arms; `swift build` clean.

DEFERRED, with reasons:
1. No battery build/census beyond HEAZ (PRE-SHIP: no per-lane
   acceptance batteries).  HEAZ was chosen because it is the ~40 s
   fixture and shares HECA's tile — enough to exercise the harness
   path end to end, not a law claim about any other airport.
2. No timing arm.  The one new cost in a build is
   `O4_Solve_Model.current()` after the solve, which imports nothing
   the flat-site classifier has not already imported in the same
   process (measured cold: 0.32 s for `O4_Config_Utils`, paid once
   either way).  Timing stays with the round's timing block.
3. The mode-isolation twin ("flipping the key changes ONLY the solve")
   is asserted TODAY, before K1's constructor lands, so it currently
   proves the weaker fact that flipping the key changes nothing at
   all.  It must be re-run against the landed constructor, where the
   two bodies are EXPECTED to differ and only the census/sidecar
   SHAPE must stay identical.
4. `Sources/SceneryKit/Resources/o4_schema_snapshot.json` was NOT
   regenerated.  It is already stale on main (engineVersion 1.50.0 vs
   1.50.1689, missing `flat_site_declared` and
   `flat_site_declared_elevation_m`, ~8 drifted hints, and a
   non-ASCII encoding the current dump script does not reproduce), so
   refreshing it is a separate change with its own diff.  Consequence
   while it stands: the Swift `solve_model` row appears when the app
   runs a LOOSE engine and not when it runs the FROZEN bundled one.
   The Qt selector and the engine cfg contract are unaffected.

## 2026-08-14 — K1 constructive-solve core (lane/k1construct)

1. Constructive-mode censuses were run at CYXY + HECA + OTHH only (the
   lane's chartered set); SPJC / SPLP / KCLT / HEAZ constructive
   censuses are deferred to the round's consolidation (the acceptance
   verdict already FAILS on the chartered set, so the deferred arms
   cannot change the round's direction, only its detail).
2. The full pytest suite was not run against the mode branch (pre-ship
   law: only the directly-covering test files, once) —
   `tests/test_constructive_solve.py` (13 twins) and the CYXY/HECA
   iterative byte-identity arms are the mode-isolation evidence; the
   35 solve.py-importing test files run at the ship-gate hardening
   round.
3. The constructive HECA solve-phase wall (144.1 s vs iterative
   252-312 s on the same phase ledger) was measured on a machine also
   running census/build arms — DIRECTION ONLY; the lead owns the
   exclusive `--runs 2` pairs (spec acceptance 2).

## K1b constructive solve — living band (2026-08-15, lane/k1construct)
- Battery scope: constructive census run at HECA + CYXY only (the
  amended acceptance's named fixtures); SPJC/SPLP/HEAZ/KCLT/OTHH
  constructive censuses deferred to the lead close-out A/B.
- Suite scope: tests/test_constructive_solve.py run once (20 twins);
  no full-suite arm (pre-ship mode).
- Timing: no exclusive pairs run; ledger-frame walls only (CYXY ~19 s
  vs 34.6 s iterative same-frame; HECA 287.7 s vs 581 s exclusive
  baseline — direction only, the lead close-out owns the exclusive
  pairs).
- The three starred K1b deviations in the spec's implementation
  record await owner ratification.

- 2026-08-15 airport index served by the engine (docs/specs/airport-index-engine-command-spec.md; `O4_Airport_Index` water-runway + candidate coverage, cache v4, `index_count`, the `airport_index` command + `AirportIndexReady`, and the Swift parser reduced to a TSV cache reader): engine tests run ONCE through the run ledger — `tests/test_airport_index.py` + the new `tests/test_engine_airport_index.py` (71 passed); Swift `swift build` + `swift test` once (58 tests, 9 suites). NOT run (PRE-SHIP MODE): the full pytest suite, and the blast radius of `events.py` / `session.py` / `jsonl.py` (19 and 15 and 5 importers, 13 + 12 + 5 test files) — the wire-protocol pair is instead evidenced by `tools/blast.py`, which reports no new events.py↔OrthoEngineClient.swift drift (`AirportIndexReady` present both sides; 19 python handlers cover all 13 Swift call sites). No build, no census: nothing in the tile-build or auto-patch path changes (the index is built only on UI demand, off the transport read loop). The v3→v4 cache bump is unverified against a REAL Global Airports apt.dat — the Qt map and the bathymetry band rebuild transparently through `index_is_stale`, but the one-time 380 MB rebuild's wall time and the real airport count are the owner's in-sim observation.

## Proximity mouth anchors (2026-08-15, lane/mouthweld)
- Battery scope: HECA only (the owner's named site).  CYXY/SPJC/SPLP/
  HEAZ/KCLT builds + censuses deferred — every one of them has service
  roads, and KCLT is where the corridor-mouth class was first measured.
- Suite scope: `tests/test_service_mouth_prox_anchor.py` (9 twins) plus
  the three files that already cover the service pass
  (`test_corridor_joins_round.py`, `test_kill_prep_round.py`,
  `test_service_corridor_round.py`) run ONCE, 95 passed; no full-suite
  arm (pre-ship mode).
- Timing: NOT measured.  The pass adds one grid build over non-service
  ring segments (O(total ring perimeter / 2 m), restricted to cells a
  service node can query) once per airport — 1,108 indexed edges at
  HECA.  Wall clock for the three HECA arms on this tree was 356.4 /
  358.2 / 359.8 s (fix / gate-off control / instrumented), i.e. inside
  single-run noise in BOTH directions; no exclusive timing pair was
  run and no number here may be quoted as a delta.
- Attempt 2 (both STOPs adjudicated: airside-only carrier + held
  `svc_mouth` keyset) re-measured on the same three-arm frame.  The HOLD
  works (64 of 69 seats survive to emit within 0.01 m, was 35 of 141);
  the ACCEPTANCE does not (in-tolerance failing sites 25 control -> 23,
  census 7198 -> 7256).  ROOT CAUSE MEASURED AND REPORTED, NOT CHASED:
  the pass reads the airside surface BEFORE that surface is final —
  at seat time the road and the apron edge already agree to within
  0.03-0.28 m at every failing site, and the apron then moves 5-9 m
  before emit, so the road is now welded to a STALE airside value with
  perfect fidelity.  The ordering question was adjudicated and built as
  attempt 3.
- Attempt 3 (RE-SEAT at the last airside-final moment, immediately before
  `final_grade_projection` freezes the hold): the re-derivation fires (51
  of 69 seats moved, worst 8.995 m) and halves the arrival error — seats
  emitting AT their pavement's value 15/69 -> 34/69, median 0.272 ->
  0.010 m, p90 5.034 -> 0.500 m; in-tolerance failing sites 25 (control)
  -> 9.  ACCEPTANCE STILL MISSES (target ~0-2; and the groundside
  within_shape absorption class did not recede: +32 vs control).
  FINAL ATTRIBUTION, no further iteration: the airside partner moves
  DURING the very projection the seat is frozen for — at HECA -12418 the
  road emits its held 98.64 while apron -10577 emits 93.13, so the apron
  travelled 5.5 m inside `final_grade_projection` itself.  A value seat
  has run out of pipeline: there is no later moment (a seat written after
  the projection would move the road without its neighbours).  The
  LAW-PAIR design — a node-vs-edge coupling in the one graph, so road and
  pavement move together by construction — goes to the round docket.
- Twins grew to 33; the re-derivation rule lives at module level
  (`anchors.reseat_service_mouths`) so the twins drive the rule the pass
  applies, including the uncrowned-endpoint reading and node-list-rebuild
  survival.  Battery/suite/timing scope unchanged from above (the
  re-seat arm built in 340.1 s — still not a timing measurement).

## 2026-08-15 — R5 road runs track terrain (lane/roadtrack)

`corridor_profile.track_dem_profile` (the cap-constrained least-deviation
DEM tracker) + its caller in `anchors._svc_spine_station_seeds`.
PRE-SHIP mode: only the four covering test files were run, once
(`test_corridor_whole_run_profile.py` +19 R5 twins,
`test_grade_graph.py`, `test_lateral_cross_section.py`,
`test_service_mouth_prox_anchor.py` — 136 pass + the recorded
pre-existing `test_the_solve_ingests_the_family_at_BOTH_edge_set_sites`
failure).  SKIPPED: full suite, blast-radius sweep, the other three
battery airports (SPJC/SPLP/KCLT), and any timing measurement.  The
lane DID build one matched acceptance pair per airport (CYXY + HECA,
arm vs a control worktree at the same tree) under the 2026-08-12
measured-arms amendment; walls are ledger-frame only, never a timing
claim (CYXY 53.2 s arm / 54.7 s control; HECA 907.5 s arm / 901.8 s
control, both first-in-lane cold object-footprint builds).

## 2026-08-15 — R5c graded-road character (lane/roadchar)

`corridor_profile._suppress_reversals` (+ `turning_points`,
`monotone_bridge`) called from `track_dem_profile`, and
`anchors._corridor_colevel_rehome` called from
`_svc_spine_station_seeds`; one new constant
`config.SVC_PROFILE_REVERSAL_MIN_M` (0.4 m).  PRE-SHIP mode: only the
covering test files were run, once — `test_r5c_graded_road_character.py`
(18 new twins), `test_corridor_whole_run_profile.py`,
`test_service_parallel_merge.py`, plus the three adjacent service-spine
files (`test_svc_spine_edge_couple.py`,
`test_service_spine_stringing.py`, `test_service_corridor_round.py`):
66 + 56 pass and 1 recorded pre-existing xfail.  SKIPPED: the full
suite, the blast-radius sweep, the other three battery airports
(SPJC/SPLP/KCLT), and any timing measurement.  The lane built CYXY and
HECA through the harness against the R5 reference patches; walls are
LEDGER-FRAME ONLY and are not a timing claim — four heavy builds
(two of the owner's tile builds and two of this lane's) ran
concurrently throughout.
## 2026-08-15 — F3 gap conformance (lane/gapconform)

`gap_fill` conformance band + eroded interior + terrain-floor spine
profile (Fable spec `docs/specs/gap-conformance-spec.md`, owner ruling
"GAP INTERIOR RINGS NEVER CLIFF AGAINST PAVEMENT") plus the one new
constant `config.GAP_PAVEMENT_CONFORM_MARGIN_M`.  PRE-SHIP mode: only
the covering test files were run, once — `test_gap_conformance.py` (new,
11 twins for the spec's four law classes), `test_gap_interior_rings.py`,
`test_pocket_collar_rings.py`, `test_gap_fill_loop_resample.py`,
`test_gap_fill_spine.py`, `test_gap_fill_service_road_stop.py` (the
gapstop parity twin), `test_one_solve_gap_spine.py`,
`test_gap_interior_floor.py`, `test_gap_fill_nearest_index.py`,
`test_crown_spine_seam_weld.py`,
`test_adjacent_ground_validator_lockstep.py`,
`test_chain_divergence_selfcross.py` — 183 pass beside three RECORDED
PRE-EXISTING failures in `test_gap_fill_spine.py` (the rim-pocket gate
twins assert `GAP_FILL_RIM_POCKETS_ENABLED is False`; the shipped
default is `1`, unchanged by this lane).  SKIPPED: full suite,
blast-radius sweep, the other three battery airports (SPJC/SPLP/KCLT),
and any timing measurement.  The lane built one acceptance pair
(CYXY + HECA) against the two reference patches the spec names; walls
are ledger-frame only and are NOT a timing claim — the machine carried
two concurrent tile builds throughout.

## F3/F3b HELD AT THE ATTEMPT CAP (2026-08-15 late, Fable lead)
- F3+F3b on lane/gapconform: solve-refusal fixed (ceiling-only stage);
  validator staged (cone from conformed ends; MIN_FALL kept
  provisional; 262 twins). HELD: 1,323 airside drainage_spine rows on
  the HECA arm (worst 25.6 m, p50 4.66, median 76 m from parents) are
  an EMITTER population not yet located (not the interval reach —
  two_nearest is uncapped; suspect a second spine-emission path or the
  ring chains). Two fix attempts spent; STOP per the convergence law.
  Attribution next round: sample rows' way ids -> which emitter; the
  arm HECA_20260815T212514 (66932401efba) + rows /tmp/harness/rf3b2.json.

## 2026-08-16 — F3b re-clamp attribution + fix (lane/gapconform)

The located author of the held 1,323-row HECA `drainage_spine`
population: `gap_fill.reclamp_gap_spines`, the LAST writer of a gap
spine's values, still carried the clause-3 terrain FLOOR F3b superseded
— it clamped the station into `[lo, hi]` and then RAISED it back to the
stored terrain, so the drainage ceiling was no longer last.  Fix: one
staged-law evaluator (`gap_fill._staged_spine_values`) shared by the
emitter walk and the re-clamp.  PRE-SHIP mode: only the covering test
files were run, once — `test_gap_conformance.py` (15, +4 new F3b
re-clamp twins), the ten gap files of the F3 lane's own list (172 pass
beside the three RECORDED PRE-EXISTING `test_gap_fill_spine.py`
rim-pocket gate failures) and `test_harness.py` /
`test_census_instrument.py` / `test_field_report_fix_batch.py` /
`test_reg_families_round.py` (351).  SKIPPED: full suite,
blast-radius sweep, SPJC/SPLP/KCLT, and any timing measurement.  Two
acceptance arms were built (CYXY + HECA) against the main-tree control
patches the lane already had; walls are ledger-frame only and are NOT a
timing claim.  Build-time impact: one extra conformance index build
(already built per gap-fill pass) and two index queries per emitted
spine way (287 at HECA, 45 at CYXY) inside a pass that already queries
`_spine_interval` per station — far below the 0.6 s / 1 % gate, not
measured.

Residual, NOT chased (attempt cap): HECA keeps 70 `drainage_spine` rows
(main-tree control 66, so +4 for the lane) and CYXY 0 (control 5).  The
dominant survivor — 34 of the 70, way `-13464` @30.116941,31.443884 — is
the EMPTY-INTERSECTION FALLBACK class and is verified arithmetically off
the emitted patch, not inferred: at 54.7 m from both parents the runway's
lateral crater FLOOR (`adjacent_ground_envelope` −1.701 m) stands above
the lower parent's dam CEILING (−0.3 m under an apron 6.0 m lower), the
two parents' intervals do not intersect, and `_spine_interval`'s
2026-07-09 fallback resolves it to the NEARER parent's own interval — the
emitted 139.29 IS the runway floor 140.99 − 1.701 to the centimetre,
4.31 m above the lower edge the dam clause reads.  Which clause yields is
an owner/Fable ruling, not an implementation choice.

## 2026-08-16 — R8 stage 1, transverse-feasible runway seeding (lane/kafwseed)

`grade_law.runway_join_contacts` (crossings added, gate
`O4_RUNWAY_CROSSING_JOIN`, new constant `RUNWAY_JOIN_DEDUP_M`);
`pavement.runway_segments` (`law_line_at`, `seat_law_stations`,
`solve_anchor_set`; the emit solve is handed `anchored ∪ law-seated` and
publishes `law_seated` on the profile state);
`runway_redistribute` (carries / re-seats / holds `law_seated` through
`_insert_seam_anchors`, the end-zone solve and `apply_runway_flex`).
PRE-SHIP mode: only the covering test file was run, once —
`tests/test_anchor_law_join.py`, 16 pass (9 pre-existing + 7 new R8
twins).  SKIPPED: the full suite, the blast-radius sweep, KCLT, and any
timing measurement (per-change timing gates SUSPENDED, RULINGS
2026-08-04; the free ledger tripwire shows no ~2x anomaly — KAFW 128 s
wall against a 136 s refusing base).  Battery arms (KAFW, CYXY, HECA,
SPJC, SPLP) were built through the harness in a matched
same-tree/same-corpus pair of lane worktrees, but every build ran
concurrently with other sessions' builds, so the WALLS are ledger-frame
only and are not a timing claim.  ALSO DEFERRED: `grade_graph_validate`'s
runway-join check still re-derives contacts per ENDPOINT and therefore
now inspects a SUBSET of the joins the solver anchors (conservative — it
cannot mint a false violation — but it is a second "where a join is"
rule and should be folded onto `runway_join_contacts`).

### 2026-08-16 — R8 stage 1, attempt 2 (law-seat release)

`pavement.runway_segments` gains `segment_grades`,
`minted_over_cap_segments`, `solve_holding_seats` and
`within_shape_runway_cap`; both solve sites (emit + redistribute) run
through `solve_holding_seats`.  Covering test file re-run once:
`tests/test_anchor_law_join.py`, 20 pass (9 pre-existing + 11 R8).
Battery re-measured (KAFW/CYXY/HECA/SPJC/SPLP) — CYXY, KAFW, SPJC and
HECA came out BYTE-IDENTICAL to attempt 1 (the release fires only where
the hold mints an over-cap within-shape runway segment, i.e. SPLP only),
so attempt 1's attribution stands unchanged for those four.  SKIPPED as
before: full suite, blast sweep, KCLT, timing.
## 2026-08-16 — KDFW bridge refusal + deck-pin guard (lane/bridgeguard)

PRE-SHIP mode.  RUN, once: `test_kdfw_bridge_refusal.py` (32, new) plus
the five covering files — `test_object_terrain_features.py`,
`test_object_bridge_terrain.py`, `test_round12_bridge_deck_datum.py`,
`test_eat_ceiling.py`, `test_r17d_unroutable_eat.py` — 384 pass, 11
skipped (absent packs).  Two acceptance builds: KDFW (the subject, with
`O4_OBJECT_BRIDGE_TERRAIN` ON) and OTHH (the bridge fixture airport).

A THIRD build, KMCI, was added off-spec: the corpus sweep showed the
clearance gate refuses six of its cosmetic road-bridge records, and
whether a fixture airport still builds under that is the round's biggest
open question.  It does (rc=0).

SKIPPED: the full suite, the blast-radius sweep, every battery airport
other than the three above, and any timing measurement.  No matched-control
arm was built for OTHH: its "byte-identical or attributed" acceptance is
discharged by ATTRIBUTION instead — the v18 classification OTHH's build
wrote is value-for-value identical to the pre-change v17 record set in the
shared data repo (3 bridges, same contracts, same clearances, same single
A4 refusal), and the predicate applied offline to all 35 cached records
over 14 packs refuses ZERO OTHH records.

ONE ARM WAS DISCARDED AND REBUILT, recorded because the trap is generic:
the first OTHH build read a classification the KILLED pre-fix run had left
in the LANE-PERSISTENT mod-cache overlay, and reported OTHH's viaducts
refused.  A lane cache survives the build that wrote it — after any
classifier change, an interrupted run's sidecar is a stale authority, and
the cache VERSION cannot see it because the version did not change between
those two runs.  The KDFW arm read the same pre-fix sidecar and was KEPT:
its record is the SCALE refusal, which the fix cannot touch (the scale
branch returns before the clearance branch, and KDFW exposes a genuine
girder line at 2.01 m, so the changed expression evaluates identically) —
established by reading the cached record's own values, not by argument.

BUILD-TIME IMPACT, not measured (per-change timing gates suspended).
Clause 1 is three comparisons per bridge candidate.  Clause 2 adds ONE
`build_anchor_envelope` (two Dijkstras over the unified spine graph) per
solve, and ONLY on an airport that has object-bridge deck pins — the EAT
guard beside it already pays exactly this cost on every airport with an
EAT rect.  The envelope cannot be shared between the two guards: they
demote different junior sets, so one envelope would answer the other's
question wrongly.

CACHE VERSION 17 -> 18 forces one cold re-classification per pack on
first use.  That is the round-5 island-tunnel precedent (version 15) and
is what makes the rule reach an unedited pack at all; it is a one-time
cost per lane cache, not a per-build one.

CONSEQUENCE FLAGGED FOR THE OWNER, not verified here: a refused structure
takes no ruling-R4 exclusion, so KDFW's five inset objects (220-224.obj)
and every other refused family return to the generic Phase-2 y-bake.
That is the island-tunnel refusal's own precedent ("no terrain was
adapted to them"), but it is an OBJECT-PLACEMENT change at tile-build
time and only the owner's in-sim pass can accept it.

RESULTS (all three rc=0, this tree, clean worktree, shared repo UNCHANGED):
  KDFW  1220.3 s  3491 shapes  body_sha d684de9a144e  census LAW-TRUE 2520 /
        ADJUDICATED 553 (airside 267, groundside 284, mixed 2), FAIL on
        PRE-EXISTING defects — a 21.5 m junction cliff cluster at
        32.879,-97.051, no bridge feature within it.  The subject mechanism
        is CLOSED: 0 bridges, 1 refusal, 0 deck-end pins, and the final
        reach band reports 7 sub-materiality inversions with 2 pinned
        vertices outside band (worst 20.9005 m) — NUMERICALLY IDENTICAL to
        the bridge-OFF arm's own report, i.e. the feature is now inert
        here, against the pre-change bridge-ON arm which died on 650
        nodes / 43 pairs / worst 1.996 m.
  OTHH   465.1 s  2263 shapes  body_sha eb277c2e4beb  census LAW-TRUE 5882 /
        ADJUDICATED 5877, FAIL on pre-existing (OTHH is the object-terrain
        FIXTURE, never a law-clean airport).  3 bridges kept, trench + 2
        causeways born, deck-flush pins attempted: its viaducts keep their
        decks.  Band membership 0 of 13710 outside.
  KMCI   510.6 s  1567 shapes  body_sha 88cb02c03e31  census LAW-TRUE 3026 /
        ADJUDICATED 2049, FAIL on pre-existing.  6 records refused on
        clearance (2.09-2.45 m), 1 kept with its trench + 2 causeways.
        Band membership 0 of 8753 outside.

The two acceptance builds ran at tree bd217eaddcbb, which differs from the
committed tree ONLY in `solve._PROBE_PUBLISHED_ATTRS` (the string-mover
probe's snapshot list; that probe needs O4_STRING_MOVER_LEDGER=1, absent
from every arm's recorded env), so no arm is affected by the delta.

## 2026-08-16 — R6/R7 amendments A1 + A2 (lane/frontage)

`pavement_classification.landside_evidence_layer` /
`runway_disconnected_pavement` (replacing the refuted
`airside_evidence_layer`), `groundside.free_road_subsegments`'
`landside_evidence` term, `groundside._cut_back_road_frontage` +
`_face_carriageway_width` + `_longest_contact_run_m` reached through
`_separate_groundside_from_airside(road_frontage_cutback=…,
groundside_clip=…)`, and one explicit pre-solve call in `pipeline`
gated `O4_ROAD_FRONTAGE_CUTBACK`.  PRE-SHIP mode: only the covering
test files were run, once — `test_road_frontage_cutback.py` (12 new
twins), `test_free_road_scoping.py` (17), plus every file `blast.py`
names for `groundside.py` / `pavement_classification.py`
(`test_groundside_law_authority.py`, `test_membership_round.py`,
`test_pavement_classification.py`, `test_classification_round.py`,
`test_service_corridor_round.py`, `test_band_reports_instrument.py`,
`test_kill_prep_round.py`, `test_one_graph_groundside.py`,
`test_owner_constants_round.py`, `test_pavement_scoring.py`): 355 pass,
0 fail.  SKIPPED: the full suite, SPLP and KCLT, and any timing
measurement.  BUILT through the harness on the shared corpus, against a
base worktree at 837183d served from the artifact ledger: CYXY, SPJC and
HECA in three arms each (base / R7a-only / R7a+R7b).  Walls are
LEDGER-FRAME ONLY and are not a timing claim — another lane's KDFW and
OTHH builds ran concurrently throughout (21 concurrent `build_airport`
processes at peak).

## 2026-08-21 — apron within-shape population = frontage chords (lane/apronpop)

Spec `docs/specs/apron-within-shape-population-spec.md`, owner ruling
RULINGS 2026-08-21b. Commits 9bbeedf (predicate + twins + sidecar family
tag), 0d3028e (the read instrument), this one.

WHAT WAS RUN. The 15 twins of
`tests/test_apron_within_shape_population.py`; the seven test files
directly covering the touched code, once, with a MATCHED CONTROL of the
same selection in a clean `apronpopctl` worktree at the lane's base
commit 8058002; three harness builds (CYXY, SPJC, HECA) plus a CYXY
flag-off arm; `harness/census.py` on all six patches; `census_rows_diff`
and `airside_value_delta` against the 2026-08-21 battery patches
(artifact-ledger tags `w3s7a_*`).

MEASURED (battery -> lane, adjudicated airside):

| airport | airside | within_shape | transverse | steps |
|---|---|---|---|---|
| CYXY | 75 -> 204 | 0 -> 3 | 63 -> 188 | 0 -> 0 |
| SPJC | 189 -> 474 | 45 -> 12 | 46 -> 331 | 0 -> 37 |
| HECA | 1487 -> 1508 | 1284 -> 643 | 95 -> 572 | 3 -> 192 |

The RULED population behaves as the read predicted (SPJC drops exactly
the 34 generic apron rows; HECA drops 641 of the predicted 648; the
survivors are frontage chords). The DEBT RELOCATES TO TRANSVERSE, the
family the ruling itself names as the corridor surface's own law and
which is NOT enforced in the solve on main.

UNPAID / OWED:

- THE BATTERY BARS ARE EXCEEDED at CYXY (204 vs 75) and SPJC (474 vs
  189) and marginally at HECA (1508 vs 1487). The lane is therefore NOT
  mergeable alone; it is measured against a main whose transverse family
  is censused but not solved. No arm was run against
  lane/transect + lane/routemetric, which is where the ruling puts the
  payment — that composed arm is OWED before any merge decision.
- SPLP / KAFW / KDFW were not rebuilt: three of the six battery airports
  have no arm under this tree.
- No build-time measurement (per-change timing gates remain suspended).
  The population shrink is visible as the emit-snap law-pair count
  (CYXY 8443 -> 7139, HECA 77299) but no wall time is claimed.
- The projection-law certificate ROSE rather than fell (spec §6 predicted
  a fall): CYXY 235 -> 277 edges over cap, 193 -> 214 both-hard. Only
  CYXY has both arms; SPJC (806 / 403) and HECA (7283 / 3281) have the
  rule-on arm only, because the spec scoped the flag-off arm to CYXY.
- The census/bake FOREIGN-ROW class (below) is reported, not fixed.

### The test comparison (matched control, worktree `apronpopctl` @ 8058002)

Same 7-file selection, both arms: lane 24 failed / 390 passed, control
11 failed / 389 passed. Test-id for test-id (never counts):

- 11 PRE-EXISTING, identical on both arms: `test_pavement_grade` x5
  airports + `test_runway_longitudinal_grade[HECA]`/`[SPLP]` +
  `test_runway_seam_dem_steps_are_reported`,
  `test_single_graph_acceptance::test_solver_and_validator_same_nodes@CYXY`
  and `::test_solver_validator_same_edge_budgets@CYXY`,
  `test_harness::test_the_near_miss_frontage_law_is_one_authority`.
- 0 fixed by the lane.
- 13 NEW, in four classes — NONE of them fixed here, all owed a ruling:
  1. EIGHT twins that encode the PRE-RULING apron population on
     building-less fixtures (`test_grade_graph` x5, `test_harness` x3):
     an apron with no frontage now yields zero within-shape pairs, which
     is spec §8(e)'s own acceptance criterion. Updating them is a spec
     act, not an implementation act.
  2. A LAW COLLISION with R19-5 "the bake never removes a ring edge from
     the domain" (lead 2026-08-12,
     `test_the_bake_never_removes_a_ring_edge_from_the_domain` +
     `test_a_steep_unbaked_ring_edge_mints_its_census_row`): on an apron,
     a PHYSICAL ring edge with no frontage is no longer law, so the
     class R19-5 exists to catch (HECA -10629's 148 % ring edge) can
     carry no census row. Two owner rulings now disagree.
  3. THE FAN-RAMP LAW IS UNREACHABLE (`test_fan_ramp_law` x2): a
     fan-ramp zone piece is role `apron` and is by construction the
     ground BETWEEN frontages, clear of every movement surface — so it
     now generates zero pairs and its 5 % zone cap is never priced.
     Fan zones are RETIRED by default (W2 2026-08-08), so production is
     unaffected today; the law is not.
  4. A SURFACE REGRESSION at CYXY (`test_cyxy_spine_zero@CYXY`,
     `test_cyxy_spine_zero_no_bowl@CYXY`): 2 spine violations,
     `service_junction` at 37.1 % and 15.5 % against an 8 % cap. Same
     mechanism as the census delta.

## 2026-08-21 — THE COMPOSED ARM: apron population + transverse in the solve (lane/compose)

Specs `docs/specs/apron-within-shape-population-spec.md` and
`docs/specs/transverse-hyperplane-solve-spec.md` (+ AMENDMENT A1); owner
rulings RULINGS 2026-08-21 and 2026-08-21b. lane/apronpop ea4a1b8 with
lane/transect's five commits cherry-picked (zero textual conflicts).
This is the composed arm the apronpop lane recorded as OWED.

WHAT WAS RUN. Six harness builds, all rc=0, all shared-repo UNCHANGED:
CYXY / SPJC / HECA composed; CYXY / SPJC / HECA log-capture reruns
(byte-identical body_sha — they recover the solve-side instrument lines a
piped `tail` had cut, they are not new arms); plus ONE attribution arm,
SPJC with `O4_APRON_WITHIN_SHAPE_FRONTAGE_ONLY=0`. `harness/census.py`,
`census_rows_diff`, `airside_value_delta` and
`frontage_split --apron-population` against the 2026-08-21 battery
patches (artifact-ledger tags `w3s7a_*`). Seven test files.

MEASURED (battery -> apronpop alone -> COMPOSED, adjudicated airside):

| airport | airside | within_shape | transverse | steps |
|---|---|---|---|---|
| CYXY | 75 -> 204 -> 67 | 0 -> 3 -> 3 | 63 -> 188 -> 51 | 0 -> 0 -> 0 |
| SPJC | 189 -> 474 -> 551 | 45 -> 12 -> 258 | 46 -> 331 -> 167 | 0 -> 37 -> 31 |
| HECA | 1487 -> 1508 -> 1167 | 1284 -> 643 -> 770 | 95 -> 572 -> 155 | 3 -> 192 -> 131 |

CYXY and HECA clear their battery bars (67 <= 75, 1167 <= 1487). Transverse
in the solve pays the relocated debt on all three and binds what the census
prices (CYXY 3066/3067, SPJC 8477/8491, HECA 26616/26629).

UNPAID / OWED:

- THE SPJC BAR IS EXCEEDED, 551 vs 189, and it is an INTERACTION neither
  change produces alone. The 2x2: battery 189 / apronpop-only 474 /
  transect-only 195 / composed 551; within_shape airside 45 / 12 / 62 /
  258. 231 NEW rows are `within_shape apron|apron` AIRSIDE and the
  POPULATION IS CORRECT (201 of 233 apron rows are frontage chords), so
  this is not a predicate defect. Mechanism: apronpop withdraws the
  generic apron pair law, leaving the building->spine frontage chord as
  the apron's ONLY within-shape law, and the transverse hyper rows then
  move the apron surface by metres (3797 airside nodes moved, worst
  9.66 m) with the frontage chords absorbing the displacement. The
  carrier regularisation does not hold an apron interior against an
  ACTIVE projection. Spec §5 forbids a replacement regulariser, so the
  remedy is a spec/owner act, not an implementation one.
- BROKEN_BY_EMIT is 54-65 % of every bound transect (CYXY 1701/3066,
  SPJC 4609/8477, HECA 17221/26616; worst 2.05 / 6.63 / 8.35 m). A1 §8d
  makes this reported-not-a-STOP; it is the number that decides whether
  the topology-only emit repairs must move ahead of the final projection.
- The projection-law certificate ROSE: CYXY final#1 EXIT over_cap=1179
  (332 both-hard), SPJC 2670 (379), HECA 16577 (3251); the transverse
  family's own share is CYXY 276/69, SPJC 376/63, HECA 3106/768. The SPJC
  transect-only arm is 1620/441 — composed is worse on over_cap, better
  on both-hard. Solve-side `[transverse-bind] exit_over_budget` is CYXY
  211 (worst 1.037 m), SPJC 326 (3.528 m), HECA 2513 (6.096 m); the
  band clamp's own footprint beside it is 5 / 37 / 56 values, worst
  0.114 / 0.535 / 2.606 m. `[writeback-band]` worst > 10 m count is 0 on
  all three (worst clamp CYXY 0.03 m, SPJC 0.08 m, HECA 4.70 m).
- AIRSIDE MOVED A LOT vs the battery: CYXY 481 nodes (worst 3.95 m),
  SPJC 3797 (9.66 m), HECA 8695 (18.23 m). No groundside pull is implied
  ("airside is king" is about pull, and this is airside's own law
  changing), but the owner's in-sim eye is owed before any merge.
- The CYXY `service_junction` spine 37.1 % row STANDS (2.420 m
  @(60.712398,-135.077719)): it is a FOREIGN-priced generic apron row, so
  the transverse solve cannot reach it. apronpop class 4 unfixed.
- Kept frontage rows > 5 % (spec §10 docket, unfixed): CYXY 0, SPJC 9
  (max 10.08 %), HECA 91 (max 91.06 %, the head all on short 1.8-3.0 m
  chords — seat/anchor defects).
- `junction|junction` generic (ruling clause 4, report-only): CYXY 0,
  SPJC 24, HECA 77.
- SPLP / KAFW / KDFW have no arm under this tree.
- No build-time measurement; per-change timing gates remain suspended.

THE TEST COMPARISON — the composition authors ZERO new failures. Test-id
for test-id: the three twin files pass in full (15 + 11 + 6 = 32/32); the
four heavy suites give 22 failed / 268 passed, and adding
`test_fan_ramp_law` (2) and `test_lateral_cross_section` (1) reproduces
EXACTLY apronpop's 11 pre-existing + 13 NEW four classes, plus
`test_the_solve_ingests_the_family_at_BOTH_edge_set_sites`, which fails on
lane/transect ALONE (verified in the transect worktree at 77aeac2: 1
failed / 64 passed). Nothing on this list is new to the merge.

## 2026-08-21c — the composed arm under A1: interior at 5 % (lane/compose, attempt 2)

Owner ruling RULINGS 2026-08-21c + spec AMENDMENT A1 (main d2f5bc6),
implemented as 396d94b on lane/compose (apronpop + transect + A1). Three
harness builds, all rc=0, all shared-repo UNCHANGED. This is ATTEMPT 2 of
the apron-population spec; no fix was attempted for the STOPs below.

MEASURED — adjudicated airside, battery -> apronpop -> compose-v1 (the
2026-08-21b removal) -> compose-v2 (A1):

| airport | battery | apronpop | v1 | v2 | bar | verdict |
|---|---|---|---|---|---|---|
| CYXY | 75 | 204 | 67 | 16 | 75 | PASS |
| SPJC | 189 | 474 | 551 | 204 | 189 | STOP +15 |
| HECA | 1487 | 1508 | 1167 | 1599 | 1487 | STOP +112 |

within_shape airside 0/3/3/0, 45/12/258/52, 1284/643/770/1383.
transverse airside 63/188/51/4, 46/331/167/51, 95/572/155/63.
steps airside 0/0/0/0, 0/37/31/0, 3/192/131/8.

A1 REPAIRS EVERYTHING THE REMOVAL DAMAGED. Transverse is BELOW the
battery on all three; steps are gone (SPJC 37->0, HECA 192->8); the
surface is far closer to the battery (worst airside |dz| vs battery
CYXY 3.95->0.93 m, SPJC 9.66->1.09 m, HECA 18.23->6.77 m); CYXY clears
its bar by 59 with within_shape airside ZERO, and the CYXY
service_junction spine 37.1 % row that survived both earlier arms is
GONE.

UNPAID / OWED:

- SPJC (204 vs 189) and HECA (1599 vs 1487) EXCEED their bars. The
  attribution is identical on both and is NOT the new law: not one
  violation anywhere carries the 5 % cap. SPJC within_shape airside 52 =
  46 @1.0 % + 6 @1.5 %; HECA 1383 = 1326 @1.0 % + 56 @1.5 % + 1 @8 %. The
  debt sits on the STRICT class.
- HECA's is the RING-ADJACENT branch. Of 1258 within_shape apron|apron
  airside rows, 582 are frontage chords and 676 generic; since no row
  carries the 5 % cap, every violating generic row is necessarily
  ring-adjacent (the only generic-and-strict combination A1 allows) or
  foreign-priced (28 of 676). ~648 rows are apron RING EDGES over the
  strict 1 % cap. Severity rose with the count: >2x-cap 447 -> 663,
  accumulated excess 4332 -> 4564 pct-points. Head sites
  (30.11843,31.41048), (30.11848,31.41047), (30.12442,31.41397) at
  1.11-1.64 % against 1.00 %.
- SPJC's +15 is within_shape +7, transverse +5, frontage_near_miss +2,
  plane_gradient +1; strip_arc, drainage_spine and strip_longitudinal are
  unchanged. The worst NEW rows are apron|apron on way -10113 at
  1.016-1.033 % against 1.000 % over ~260 m chords.
- MECHANISM: 5 % is a far better interior constraint than none, but it is
  still four points looser than the strict cap, so the interior may
  legally tilt under the transect rows and the movement surfaces and ring
  edges bounding it absorb the difference — the v1 failure shape, an order
  of magnitude smaller.
- OWNER QUESTION THIS TURNS ON: is a long apron RING EDGE a movement
  surface (strict) or interior (5 %)? A1 §1a reserved ring-adjacent for
  the strict cap on R19-5 grounds; the measurement says that choice
  decides HECA's bar.
- broken_by_emit is still 48-62 % of every bound transect (CYXY 1471,
  SPJC 4131, HECA 17005) — reported, not a STOP (A1 §8d).
- The projection-law certificate: CYXY 1001 over_cap (451 both-hard),
  SPJC 1670 (427), HECA 18496 (3751). CYXY and SPJC FELL against v1
  (1179 / 2670); HECA rose (16577).
- `[writeback-band]` worst > 10 m count is 0 on all three, but HECA's
  worst clamp rose 4.70 -> 8.80 m.
- A PRE-EXISTING census/bake CAP DRIFT is now visible and is reported, not
  adopted: one ring edge reads the blend branch's 1.5 % in the bake and
  the plain body cap in the census, identically with the interior flag on
  and off. The new cap-lockstep twin asserts NO NEW drift.
- A role-LESS duplicate ring of an apron host keeps the strict cap while
  its host prices its interior at 5 % — one geometry, two laws.
- SPLP / KAFW / KDFW still have no arm under this tree.

TESTS. 37/37 on the three twin files; 341 passed / 1 failed across
test_harness + test_grade_graph + test_fan_ramp_law + the twins, that 1
being one of the 11 the apronpop lane measured on its matched control.
A1 RESOLVED BOTH CLASSES apronpop could not — the R19-5 law collision and
the unreachable fan-ramp law, all four twins passing untouched — and six
of the eight building-less-fixture twins recovered untouched. Two stale
twins were updated as the ruling requires with their substantive
assertions intact.

## 2026-08-21 A2 — ring-adjacent apron edges are interior (lane/compose, v3)

Spec AMENDMENT A2 (main 2e70ae9), implemented as 6c9b9c5. A2 corrects the
LEAD's own A1 §1a clause, so it is not a third attempt at the mechanism.
Three harness builds, all rc=0, all shared-repo UNCHANGED.

MEASURED — adjudicated airside, battery / apronpop / v1 (removal) / v2
(A1) / v3 (A2):

| airport | battery | apronpop | v1 | v2 | v3 | bar | v3 |
|---|---|---|---|---|---|---|---|
| CYXY | 75 | 204 | 67 | 16 | 17 | 75 | PASS |
| SPJC | 189 | 474 | 551 | 204 | 213 | 189 | STOP +24 |
| HECA | 1487 | 1508 | 1167 | 1599 | 2560 | 1487 | STOP +1073 |

within_shape airside 0/3/3/0/0, 45/12/258/52/73, 1284/643/770/1383/2368.
transverse airside 63/188/51/4/5, 46/331/167/51/38, 95/572/155/63/49.
steps airside 0/0/0/0/0, 0/37/31/0/0, 3/192/131/8/5.

UNPAID / OWED:

- NOT ONE VIOLATION ON ANY AIRPORT, IN ANY ARM, IS PRICED AT THE 5 % CAP.
  v3 within_shape airside by cap: CYXY none; SPJC 62 @1.0 % + 11 @1.5 %;
  HECA 2221 @1.0 % + 147 @1.5 %. The interior law mints nothing. What the
  interior cap controls is how far the interior may MOVE, and the strict
  class bounding it absorbs every metre — so widening the interior class
  worsens the strict class monotonically at HECA (within_shape airside
  770 -> 1383 -> 2368 as the interior grows v1 -> v2 -> v3).
- A2's own prediction HELD: the ~648 HECA ring edges it targeted stop
  being violations, because at 5 % they pass. The cost is that the surface
  they no longer hold tilts into the movement surfaces. A2 is the correct
  reading of 2026-08-21b (a non-frontage ring edge IS a generic pair) and
  the wrong lever for the bar.
- HECA v3 residual classified: 2205 apron within_shape airside rows = 786
  frontage chords + 1419 generic; with no row at 5 % every generic one is
  a CORRIDOR-CROSSING ring edge (1366 unified:apron, 25 apron:spine, 28
  foreign). Severity: >2x-cap 447 -> 663 -> 1117, accumulated excess
  4332 -> 4564 -> 6905 pct-points. Head sites (30.11814,31.41057),
  (30.11818,31.41055), (30.11843,31.41048) at 1.37-1.41 % vs 1.00 %.
- SPJC v3 residual (+24) is TWO populations: 15 frontage chords + 47
  corridor-crossing ring edges + 11 junction rows. The metre-heavy rows
  are hairline (1.019-1.097 % vs 1.000 % on 55-178 m chords, way -10113,
  sites (-12.019228,-77.110061), (-12.029663,-77.104875)); the severe rows
  are a localised WELD CLUSTER — 39 of the 53 >2x rows are <= 5 m long,
  |de| 0.16-0.45 m, around (-12.021394,-77.110990) where ways -10113 /
  -10162 / -10698 / -10699 meet. A seat/weld defect, not a grading one.
- NO ARM PASSES ALL THREE. CYXY wants v2/v3, SPJC is ~+20 in both, HECA is
  best at v1 and worst at v3. Since no violation is ever priced at 5 %,
  the interior CAP is not the lever that closes HECA; what closes it is
  whatever stops the interior tilting into its movement surfaces — a
  different mechanism from a cap value, and an owner/spec call.
- DOCKETED BY NAME, nothing fixed: (1) the BLEND-CREDIT READER DRIFT the
  cap-lockstep twin found — bake reads the blend branch's 1.5 % on one
  apron ring edge, census reads the plain 1.0 % body cap; site is the twin
  fixture's bottom ring edge, layout-local (-100,-40)-(300,-40), lat/lon
  (30.4996407,31.4989583)-(30.4996407,31.5031250); A2 removes it from the
  shipping configuration (that edge is interior, both readers agree at
  5 %) but the gap is untouched and still asserted on the flag-off arm.
  (2) `shape_constraints_cached` is keyed by CONTENT and the interior flag
  is NOT in the key, so a flag-flipped re-run of an identical ring is
  served the first arm's caps — test-only (production reads the flag once
  at import), found in test_fan_ramp_law. (3) the SPJC weld cluster.
  (4) HECA's 152 kept frontage rows > 5 %. (5) broken_by_emit at 46-65 %.
  (6) a role-less duplicate ring priced strictly while its host prices its
  interior at 5 %. (7) SPLP / KAFW / KDFW have no arm under this tree.
- A REGRESSION A2 INTRODUCED AND THIS LANE FIXED before building: a pair
  sharing a taxi CENTERLINE was raised to 5 %, which would legalise a 5 %
  grade along a running taxiway. Caught by test_grade_graph's spine twin;
  `spine_caps` is now part of the corridor class and is not gated on ring
  adjacency.

WHAT HOLDS. Transverse is at or below the battery on all three and is best
in v3 (CYXY 63->5, SPJC 46->38, HECA 95->49); steps are gone (SPJC 37->0,
HECA 192->5); `[writeback-band]` worst > 10 m count is 0 everywhere (worst
clamp 0.02 / 0.08 / 4.91 m); CYXY clears its bar by 58 with within_shape
airside zero.

TESTS. 345 passed / 1 failed across the six suites, that 1 being one of the
11 the apronpop lane measured on its matched control. R19-5's catch and the
fan-ramp law both remain resolved; R19-5 now survives at 5 % with its own
twin asserting a 148 % ring edge still fails.

## 2026-08-23 — the apron STAGED SOLVE (lane/compose): mechanism holds, bar does not move

Spec `docs/specs/apron-staged-solve-spec.md` (owner "proceed"), implemented
as 69d897c0 + 091fdc0 + a8588ab. Three harness builds on a clean tree, all
rc=0, all shared-repo UNCHANGED, plus a CYXY flag-off arm.

MEASURED — adjudicated airside, battery / apronpop / v1 / v2 / v3 / STAGED:

| airport | batt | apop | v1 | v2 | v3 | STAGED | bar | verdict |
|---|---|---|---|---|---|---|---|---|
| CYXY | 75 | 204 | 67 | 16 | 17 | 24 | 75 | PASS |
| SPJC | 189 | 474 | 551 | 204 | 213 | 242 | 189 | STOP +53 |
| HECA | 1487 | 1508 | 1167 | 1599 | 2560 | 2472 | 1487 | STOP +985 |

within_shape airside 0/3/3/0/0/2, 45/12/258/52/73/100,
1284/643/770/1383/2368/2280. transverse airside 63/188/51/4/5/10,
46/331/167/51/38/41, 95/572/155/63/49/46.

WHAT IS PROVEN:

- THE PRECEDENCE HOLDS. Senior nodes moved in A2 = 0 on all three; the
  freeze covers the sweeps and the band clamp. No band is rebuilt in A2
  (the R8-2 defect class is avoided by construction).
- FLAG-OFF IS BYTE-FOR-BYTE compose-v3 on CYXY: `O4_APRON_STAGED_SOLVE=0`
  rebuilds body_sha 40617f978f7a, exactly v3's. Spec twin (c), on a real
  airport rather than a fixture.
- The sidecar `apron_seniority` round-trips (CYXY 493 rows, 287 senior /
  206 interior).

UNPAID / OWED — and the two findings that matter are REFUTATIONS:

- A1'S BOTH-HARD RESIDUE IS ESSENTIALLY NIL, which refutes spec section 4's
  premise that it is "the honest pin-contradiction number" and that its
  top-20 is the next round's brief. Measured: CYXY 1 row worst 0.055 m
  (runway-datum both ends); SPJC 26 rows worst 0.006 m (unified:apron,
  terrain both ends); HECA 4 rows worst 0.446 m (unified:junction,
  runway-datum both ends). A1's over_cap is meanwhile large (HECA 4309,
  SPJC 324), so THE SENIOR LAW IS FEASIBLE and its residue is ordinary
  unconverged projection, not a contradiction between pins. There is no
  pin docket to hand on.
- THE STAGED SOLVE CANNOT MOVE THE NUMBER because the senior set is almost
  the whole apron. Interior movers vs seniors re-frozen in A2: CYXY 114 /
  272, SPJC 355 / 2,195, HECA 334 / 1,506. Under A2's predicates 82-86 %
  of interior-pair endpoints are already movement surfaces, so A2 has
  almost nothing to move and precedence almost nothing to protect. A
  mechanism that reorders two sets cannot help when one is nearly empty.
- STILL NOT ONE VIOLATION AT 5 %, a fourth time: staged within_shape
  airside by cap is CYXY 2 @1.0 %, SPJC 89 @1.0 % + 11 @1.5 %, HECA
  2176 @1.0 % + 104 @1.5 %. HECA's accumulated excess on the strict class
  went 4332 -> 7622 pct-points against the battery.
- SPJC residual per spec section 8: within_shape airside 100 (battery 45),
  25 within 1.10x of cap, 58 above 2x — and 42 of those 58 are chords
  <= 5 m, i.e. the WELD CLUSTER at (-12.021394,-77.110990) where ways
  -10113 / -10162 / -10698 / -10699 meet. Seat/weld docket, not this lane.
- Two defects in this round's own code, both found by builds and fixed: a
  SPLIT LAZY ENTRY (KeyError 'lazy_nodes', killed the SPJC build at 288 s)
  and a pin docket that reported the wrong population with every source
  "?". Neither had a surface effect — CYXY's body sha is 6c0cf4f2fd97
  across all three code states.
- SPLP / KAFW / KDFW still have no arm under this tree.

THE QUESTION THIS PUTS BACK. Four mechanisms have now been measured on one
lane — remove the interior, price it at 5 %, extend that to ring edges,
and solve it last with the movement surfaces frozen — and HECA's strict
class is worse than the battery in every one of them (1284 -> 770 / 1383 /
2368 / 2280 while total airside goes 1487 -> 1167 / 1599 / 2560 / 2472).
No arm passes all three airports. The 5 % cap prices nothing anywhere, and
the pins are not in contradiction, so neither the cap value nor the pin
placement is the lever. What remains unexplained is why the strict class
degrades at all once the interior is anything other than 1 % — and that is
a question about the projection's residual spreading, not about apron law.

## 2026-08-23 — READ: HECA/SPJC strict-class residual is INFEASIBILITY, not convergence

Lead request; no new mechanism. One lane-only override added
(`O4_SWEEP_BUDGET_SCALE`, default "1" = today's value bit for bit, f68bdba)
because no live override existed — `O4_FINAL_PROJECTION_MAX_ITERS` was
deleted with the rest of that territory's gates (RULINGS 2026-08-05) and
survives only in a comment. It scales the DERIVED budget only; an imposed
`max_iters` is untouched. Two builds, staged flags as-is, 10x.

VERDICT: **INFEASIBLE STRICT GRAPH.** The budget was never binding, and
10x buys nothing.

THE BUDGET WAS NEVER BINDING. Every projection already exited
`[converged]` — the plateau test, not the ceiling. At 1x, HECA's final
projection ran 1,880 of 250,000 sweeps and ABANDONED 248,120; its
n_material trajectory over the last blocks reads 21,624 -> 21,476 ->
21,416 -> 21,329 (last block drop +87 of 21,329, i.e. 0.4 %). CYXY's
smaller graph reads 96 -> 96 -> 96, drop +0.

BEFORE / AFTER at 10x (1x -> 10x):

| | SPJC | HECA |
|---|---|---|
| A1 over_cap (both-hard) | 324 (13) -> 313 (13) | 4309 (2) -> 3836 (2) |
| A2 over_cap (both-hard) | 35 (32) -> 30 (27) | 564 (451) -> 575 (459) |
| final#1 EXIT over_cap (both-hard) | 1796 (427) -> 1781 (434) | 10980 (4060) -> 10531 (4080) |
| within_shape airside | 100 -> 98 | 2280 -> 2275 |
| within_shape worst | 34.71 % / 1.810 m -> 34.71 % / 1.810 m | 11.59 m -> 11.69 m |
| ADJUDICATED AIRSIDE | 242 -> 242 | 2472 -> 2462 |
| exit label | [converged] every pass | [converged] every pass |
| sweeps used / ceiling | 1,640/250k -> 9,840/2.5M | 1,880/250k -> 11,280/2.5M |
| wall (LEDGER FRAME ONLY, not a timing claim) | 307 s -> 614 s | 1,419 s -> 2,087 s |

6x the sweeps moved SPJC's adjudicated airside by ZERO and its worst
residual by 0.000000 m (2.118673 m both arms, to 7 dp). HECA moved 10 rows
of the 985 it is over its bar, and its worst within_shape row got WORSE
(11.59 -> 11.69 m). That is a plateau, not slow convergence.

THE 20 WORST RESIDUAL EDGES (HECA 10x, by |de|) ARE ONE APRON AND ONE
SHAPE OF DEFECT: all 20 are `within_shape apron|apron` airside on way
**-10612**, at the strict 1.0 % cap, grade 1.36-1.64 %, |de| 10.67-11.69 m
— over chords of **650-857 m**. Sites cluster at (30.11815,31.41057),
(30.11820,31.41055), (30.11843,31.41048), (30.11852,31.41045).

That is the infeasibility stated plainly: one apron spans ~850 m across
terrain that genuinely falls ~11.7 m, and the strict cap allows 8.4 m over
that span. The projection cannot satisfy it and no sweep budget can.

THE RESIDUAL POPULATION, HECA 10x within_shape airside 2275:
- by way: -10612 (558), -13148 (260), -10656 (199), -10348 (178),
  -10682 (173) — five aprons carry 60 % of it;
- by chord: 1,319 rows <= 60 m, 398 <= 200 m, 429 <= 500 m, **129 > 500 m**;
  956 rows are on chords ABOVE the 60 m `APRON_BODY_CHORD_MAX_M` body gate,
  which means they reach the law as RING-ADJACENT or corridor/spine pairs
  (the gate exempts those) — the long-chord class the body gate was written
  to exclude is re-entering through the ring-edge and corridor doors;
- by relative overshoot: 175 within 1.10x, 599 <= 1.5x, 470 <= 2x,
  1,031 > 2x.

SPJC's residual is the mirror image and unchanged from the staged report:
98 rows, 42 of the >2x class on chords <= 5 m — the weld cluster at
(-12.021394,-77.110990).

WHAT THIS HANDS THE NEXT ROUND. Two DIFFERENT defects wear one number:
a LONG-CHORD infeasibility at HECA (aprons whose real relief exceeds what
1 % permits across their own span, entering through the ring-adjacent /
corridor exemptions to the 60 m gate) and a SHORT-CHORD weld cluster at
SPJC. Neither is a cap value, a pin placement, or a sweep budget — all
three have now been measured and excluded.

## 2026-08-23 A3 — ring edges strict only inside the 60 m gate (lane/compose)

Spec AMENDMENT A3 (main f081294), implemented as 3d5fe0c. Sweep scale back
at 1. Three harness builds, staged + transects on, all rc=0, shared repo
UNCHANGED.

ADJUDICATED AIRSIDE — battery / apronpop / v1 / v2 / v3 / staged / A3:

| airport | batt | apop | v1 | v2 | v3 | staged | A3 | bar | verdict |
|---|---|---|---|---|---|---|---|---|---|
| CYXY | 75 | 204 | 67 | 16 | 17 | 24 | 24 | 75 | PASS |
| SPJC | 189 | 474 | 551 | 204 | 213 | 242 | 265 | 189 | STOP +76 |
| HECA | 1487 | 1508 | 1167 | 1599 | 2560 | 2472 | 2276 | 1487 | STOP +789 |

within_shape airside 0/3/3/0/0/2/2, 45/12/258/52/73/100/120,
1284/643/770/1383/2368/2280/2107. CYXY's A3 body sha is IDENTICAL to the
staged arm (6c0cf4f2fd97) — it carries no long ring edge, so A3 is a no-op
there.

THE DRAG HYPOTHESIS: CONFIRMED AT HECA, REFUTED AT SPJC. within_shape
airside split by chord (<= 60 m / > 60 m):

| arm | HECA | SPJC |
|---|---|---|
| battery | 765 / 519 | 45 / 0 |
| staged | 1319 / 961 | 76 / 24 |
| A3 | **1044 / 1063** | **80 / 40** |

HECA's short class fell 1319 -> 1044 (-275, -21 %) and its worst row fell
11.59 -> 9.59 m: relaxing the long constraints DID stop them dragging the
short ones. SPJC's short class did not move (76 -> 80) and its long class
grew 24 -> 40, which is why its total rose.

BY CAP, a fifth arm saying it: STILL NOT ONE VIOLATION AT 5 %. HECA A3
2055 @1.0 % + 52 @1.5 %; SPJC A3 106 @1.0 % + 14 @1.5 %; CYXY 2 @1.0 %.

THE 20 WORST ARE THE SAME CLASS A3 TARGETED AND DID NOT REACH. All 20 are
`within_shape apron|apron` airside on way **-10612**, cap **1.0 %**, grade
1.09-1.26 %, |de| 8.36-9.59 m, chords **665-857 m**; sites (30.11814,
31.41057), (30.11815,31.41057), (30.11843,31.41048), (30.11852,31.41045).
A3 reduced their |de| (11.69 -> 9.59 m) but did NOT reclassify them.

WHY, AND IT IS THE CARVE-OUT THIS LANE FLAGGED WHEN IMPLEMENTING A3. The
gate was applied to the COVER clause and the ring FRONTAGE edge, as A3
words it; the ``spine_caps`` half of ``is_apron_corridor_crossing`` was
deliberately left ungated, because that pair IS the route and gating it
would raise a long taxiway pair to 5 % (the regression A2's first pass
produced and test_grade_graph's spine twin caught). Evidence that this is
the surviving door:
- the sidecar's own ``apron_seniority`` marks 2,712 of 3,288 HECA apron
  nodes SENIOR (82 %), and the nearest apron node to each of the four
  worst sites is SENIOR;
- ``pair_caps`` still carries **9,782 `unified:apron` rows on chords
  > 60 m**, the longest at 1,417 m with a 21.295 m budget — an implied
  **1.50 %**, i.e. a spine/blend cap, not the 5 % interior;
- the residual > 60 m class is 1,063 rows: 280 at 60-200 m, 636 at
  200-500 m, **147 above 500 m**, on ways -10612 (282), -10682 (226),
  -13148 (171), -10656 (146), -10641 (91).
So the long-chord class now reaches the strict law through the SPINE door
rather than the cover door. Whether a long APRON spine pair (1 %, the
apron's own spine — not a 1.5 % taxi route) should take the length gate is
the open question A3 did not answer, and it is what decides HECA.

SPJC WELD-CLUSTER ROWS, listed separately as asked: 37 of the 120
within_shape airside rows lie within ~60 m of (-12.021394,-77.110990), on
sub-3 m chords at 7.8-35.3x their cap (worst 35.31 % on a 1.30 m chord,
|de| 0.460 m, ways -10113 / -10162 / -10698 / -10699). The other 83 rows
peak at 20.27 %. The cluster is a seat/weld defect and is untouched by
every apron-law arm so far.

UNPAID / OWED: SPJC and HECA remain over their bars; the spine-door
question above; the SPJC weld cluster; SPLP / KAFW / KDFW still have no arm
under this tree.

## 2026-08-23 A4 — nearest-spine chords + strip exclusion: HECA PASSES ITS BAR

Spec AMENDMENT A4 (main 45f7268; owner rulings RULINGS 2026-08-21d),
implemented as ef3e842 + b828ff9 on lane/compose. Budget ruling applied:
FASTPATH re-price on all three A3 patches first, then ONE build (HECA).

### The fastpath (artifacts only — no build)

Re-pricing the A3 patches under the A4 population predicted, per airport:

| | HECA | SPJC | CYXY |
|---|---|---|---|
| nearest-spine chords priced | 2,559 | 2,026 | 329 |
| ...violating at 1 % | 1,253 | 513 | 101 |
| max nearest-spine chord | 200 m | 169 m | 188 m |
| strip-EXCLUDED nodes | 140 | 8 | 3 |
| shapes FULLY excluded | **12** | 0 | 0 |
| -10612 chords per vertex | **1** | — | — |

The 12 fully-excluded HECA shapes are `-11412 -11415 -11423 -12240 -12249
-12250 -12251 -12308 -12481 -12482 -12500 -12520` — **including -12251**,
the runway-05C/23C shoulder sliver the owner identified in JOSM.

THE FASTPATH PAID FOR ITSELF: it caught that selecting the nearest spine
node by COORDINATE IDENTITY against `axes_exact` vertices yields an EMPTY
set on real data (not one emitted apron ring vertex equals an axes_exact
vertex; the node the owner named sits 0.002 m off the line). A4.1(i) would
have shipped inert. The candidate set is now ring vertices within
`SPINE_PERP_TOL_M` of a centerline — the engine's own on-the-spine notion.

### The build (HECA, staged + transects)

**ADJUDICATED AIRSIDE 1,273 — UNDER THE 1,487 BAR, by 214.** The first
HECA arm to clear its bar since the battery.

| arm | batt | apop | v1 | v2 | v3 | staged | A3 | **A4** | bar |
|---|---|---|---|---|---|---|---|---|---|
| HECA | 1487 | 1508 | 1167 | 1599 | 2560 | 2472 | 2276 | **1273** | 1487 |

within_shape airside 1284 → … → 2107 (A3) → **1,106** (A4) — *below the
battery*. transverse airside 95 → **35**, the best of any arm. steps
airside 3 → 12.

within_shape airside by cap: **1,075 @1.0 % + 29 @1.5 % + 2 @8 %** — still
none at the 5 % interior cap, now for the sixth arm running.

By chord class (battery / A3 / A4):

| chord | battery | A3 | **A4** |
|---|---|---|---|
| ≤ 60 m | 765 | 1,044 | **789** |
| 60–200 m | 305 | 280 | **290** |
| **> 200 m** | 214 | **783** | **27** |
| max chord | 680 m | 857 m | **555 m** |

THE LONG-CHORD INFEASIBILITY CLASS IS GONE: 783 → 27. The -10612 fan the
owner read in JOSM is resolved — **183 rows, one per site, max chord
199 m** (A3: 367 rows, 665–857 m, up to 53 chords from one vertex).

The 27 survivors > 200 m are all cap 1.0 %, 21 of them on way -10256, at
484–555 m and 1.54–1.55 %. They are SPINE pairs, which A4 deliberately
leaves ungated (a spine pair is the route and keeps its route's cap) —
the remaining long class, and the next question if it matters.

Instruments: `[apron-staged]` A1 over_cap 1,388 (both-hard **2**) | A2 328
(both-hard 315), **senior moved in A2 = 0**; certificate final#1 EXIT
16,768 (3,494 both-hard) vs A3's 22,034 (4,225); `[transverse-bind]`
bound 26,728 / rows 53,456 / exit_over_budget 2,424; **`[writeback-band]`
worst > 10 m count = 0** (worst clamp +6.17 m); airside_value_delta vs
battery 11,348 nodes, worst 12.14 m. census_rows_diff vs A3: 2,238 GONE /
1,045 NEW, net −1,193.

UNPAID / OWED:

- SEAT/WELD RESIDUE, listed separately as the next docket: rows on chords
  ≤ 5 m at more than 2× cap — battery 167, A3 229, **A4 123**. Reduced but
  not addressed; no apron-population change touches it.
- SPJC and CYXY have NO A4 BUILD this round (budget ruling): they run at
  acceptance/merge. The fastpath predicts SPJC's nearest-spine class at
  513 violations and CYXY's at 101, but a prediction is not an arm.
- The 27 spine-pair rows > 200 m at HECA (way -10256).
- A4.1(iii) is worded "ring edges ≤ APRON_BODY_CHORD_MAX_M **per A2/A3**"
  and was implemented as A2/A3's own clauses (ring frontage edge,
  corridor-crossing edge) rather than promoting every short ring edge to
  strict. The broader reading would ADD strict rows; this is flagged for
  ratification.

## 2026-08-23 A4 acceptance — CYXY and SPJC arms: two of three airports pass

The two arms the budget ruling deferred, run at the same tree as the HECA
arm (d861d6f, staged + transects, flags identical). All rc=0, shared repo
UNCHANGED, no HECA rebuild.

### FINAL TABLE — adjudicated airside, battery → A4

| airport | batt | apop | v1 | v2 | v3 | staged | A3 | **A4** | bar | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| CYXY | 75 | 204 | 67 | 16 | 17 | 24 | 24 | **18** | 75 | **PASS −57** |
| SPJC | 189 | 474 | 551 | 204 | 213 | 242 | 265 | **245** | 189 | **STOP +56** |
| HECA | 1487 | 1508 | 1167 | 1599 | 2560 | 2472 | 2276 | **1273** | 1487 | **PASS −214** |

TWO OF THREE PASS. Both passing arms clear by a wide margin; SPJC is the
one airport left, at +56, and its residual is not an apron-law class.

### within_shape airside, by cap and chord class

| | CYXY batt→A4 | SPJC batt→A4 | HECA batt→A4 |
|---|---|---|---|
| rows | 0 → 3 | 45 → 103 | 1284 → 1106 |
| cap 1.0 % | 0 → 3 | 34 → 90 | 1177 → 1075 |
| cap 1.5 % | 0 → 0 | 11 → 13 | 105 → 29 |
| cap 5 % (interior) | **0 → 0** | **0 → 0** | **0 → 0** |
| ≤ 60 m | 0 → 3 | 45 → 89 | 765 → 789 |
| 60–200 m | 0 → 0 | 0 → 14 | 305 → 290 |
| **> 200 m** | 0 → 0 | 0 → **0** | 214 → **27** |
| max chord | — → 7 m | 39 → **178 m** | 680 → **555 m** |

NOT ONE VIOLATION AT THE 5 % INTERIOR CAP ON ANY AIRPORT, IN ANY ARM —
now seven arms and three airports. The interior law mints nothing; it only
governs how far the interior may move.

SPJC's long-chord class is GONE (A3 had 18 rows > 200 m and a 285 m max;
A4 has none, max 178 m). HECA's fell 783 → 27 (all spine pairs).

### SPJC weld cluster — the residual is a seat/weld defect, not apron law

Rows on chords ≤ 5 m at more than 2× cap, and how many sit in the declared
cluster at (-12.021394, -77.110990):

| arm | seat/weld rows | of which in cluster |
|---|---|---|
| battery | 31 | 26 |
| A3 | 43 | 24 |
| **A4** | **48** | **17** |

SPJC's within_shape airside is 103, of which **48 are sub-5 m chords over
2× cap** — nearly half. A4 moved the cluster count down (26 → 17) but the
short-chord class as a whole up. This is the seat/weld docket, untouched by
every apron-population arm, and it is what stands between SPJC and its bar.

### Strip exclusion (A4.2), measured on the A4 patches

| airport | apron shapes | strip-EXCLUDED nodes | shapes FULLY excluded |
|---|---|---|---|
| CYXY | 43 | 3 | 0 |
| SPJC | 87 | 8 | 0 |
| HECA | 153 | **143** | **12** |

HECA's 12: `-11412 -11415 -11423 -12240 -12249 -12250 -12251 -12308 -12481
-12482 -12500 -12520` — including **-12251**, the runway 05C/23C shoulder
sliver the owner identified in JOSM.

### Instruments

| | CYXY | SPJC | HECA |
|---|---|---|---|
| `[apron-staged]` A1 over_cap (both-hard) | 6 (1) | 267 (6) | 1388 (2) |
| A2 over_cap (both-hard) | 3 (3) | 85 (78) | 328 (315) |
| **senior moved in A2** | **0** | **0** | **0** |
| certificate final#1 EXIT | 1065 (471) | 1946 (421) | 16768 (3494) |
| `[transverse-bind]` exit_over_budget | 150 | 208 | 2424 |
| **`[writeback-band]` worst > 10 m** | **0** | **0** | **0** |

UNPAID / OWED:

- SPJC IS THE ONE AIRPORT OVER ITS BAR (245 vs 189, +56), and its
  within_shape residual is dominated by the sub-5 m seat/weld class (48 of
  103). That is the next docket and is not an apron-law question.
- A4.2'S `EXCLUDED` SENIORITY VALUE NEVER REACHES THE SIDECAR. The law
  function carries it and its twin passes, but `solve.py`'s seniority
  export derives its node set FROM THE GRAPH EDGES — and an excluded node
  generates no edge, so it is absent rather than tagged. The exclusion
  itself works (proven by the HECA result and the twins); only its
  *reporting* is incomplete. The counts above come from re-deriving the
  footprint over the emitted patches, not from the sidecar. Fixing the
  export needs a rebuild to observe, so it is left for the merge round.
- The 27 HECA spine-pair rows > 200 m (way -10256, 484–555 m at 1.54 %).
- SPLP / KAFW / KDFW still have no arm under this tree.

## 2026-08-23 — SPJC seat/weld ATTRIBUTION (brief 11ffd34): STOP, no fix

Four pre-registered reads on the A4 SPJC artifacts (`a4_spjc` patch +
sidecar + rows-json). NO BUILD RAN, and none was warranted — see the
verdict.

### Read 1 — the rows

48 within_shape airside rows on chords <= 5 m at > 2x cap, of 103 total.

- **46 of 48 have BOTH endpoints welded** (a node shared by 2-3 shapes,
  apron+junction or apron+apron); only 2 rows touch a 1-shape endpoint.
- **Only 17 of 48 are in the declared cluster.** A larger group (~26) sits
  1,087-1,378 m away — the class is NOT one junction.
- Rows arrive in IDENTICAL DUPLICATE PAIRS: -10092/-10093, -10433/-10445,
  -10162/-10699, -10113/-10698 each report the same chord, |de| and grade.
  One physical edge, judged once per claiming shape.
- By way: -10092 (14), -10093 (10), -10698 (6), -10113 (4), -10162 (4),
  -10699 (3), -10433 (2), -10445 (2), -10470/-10561/-10112 (1 each).
- Worst: 35.85 % over 0.53 m (|de| 0.190 m, ways -10113/-10698);
  32.12 % over 0.72 m (0.230 m, -10162/-10698); 15.79 % over 1.96 m
  (0.310 m, -10092/-10093).

### Read 2 — the values: THE DECISIVE SPLIT

**ZERO emit-consensus disagreements.** Across the 38 distinct endpoints of
the 48 rows, every node carries ONE altitude across all claiming ways.
There is no averaging of two authorities, so this is NOT the
`emit-consensus-mints-violations` class and the seat-is-the-weld ruling
(2026-08-08) is ALREADY HONOURED here.

The emit stage's own instrument agrees: `law-aware emit snap: 61,717 law
pair(s), 0 over cap from a naive snap -> 0 after (worst residual
0.0000 m)`.

Against the solver's bake (`pair_caps`), the 48 split cleanly:

| | rows | meaning |
|---|---|---|
| **BAKED** | **26** | the solver priced THIS pair and exited over cap |
| **pair NEW at emit** | **22** | both endpoints are baked NODES (nearest baked node 0.006-0.009 m) but the PAIR was never priced |

Control: of all 103 within_shape airside rows, 55 are baked and 48 are not.
The 22 are not "emit moved a node" — their endpoints sit within 9 mm of
baked nodes. Emit created an ADJACENCY between two pre-existing, lawfully
valued nodes. The mechanism is in the log: `nid-level final weld: inserted
68 on-edge node reference(s) into welded partner ways`. Inserting an
existing node into a partner way mints a new short ring edge that the bake
never priced — and that the law-aware emit snap cannot catch, because it
checks BAKED pairs only.

### Read 3 — the history: CHURN, not drift

Class SITES: battery 20, A3 28, A4 30.
battery∩A3 18, A3∩A4 12, battery∩A4 8, **all three 8**; 18 NEW in A4, 16
GONE from A3. The class is not a fixed seat defect being carried forward —
it re-forms in different places as the surface moves.

### Read 4 — the junction geometry

9 nodes within 5 m of (-12.021394, -77.110990), every one welded across
2-3 of ways -10113 / -10162 / -10698 / -10699, every one single-valued.
z spread 0.410 m over 4.56 m. Node -3401 (z 23.62) sits 0.23 m BELOW its
~1 m neighbours -2799 (23.85) and -3400 (23.82) — that dimple IS the
32.12 % row. A real local surface dip, not a disagreement.

### VERDICT — "anything else": STOP with row-level evidence

The population is MIXED and neither named branch fits it whole:

- **EMIT-MINTED is REFUTED as specified.** That branch's premise is
  "solver values lawful, emit weld/consensus makes the step", with the fix
  being "the weld must carry ONE authority's value". Measured: the weld
  ALREADY carries one authority on every endpoint (0 of 38 disagree).
  **There is no fix to make on this branch**, which is why no build ran.
- **SOLVER-SEATED is REFUTED.** It requires two shapes solved to different
  z at a shared position; measured zero.
- **PROJECTION RESIDUAL fits the 26 BAKED rows**: they churn arm-to-arm,
  the step is present pre-emit, and the solver exits over cap on them
  (SPJC A4 `[apron-staged]` A1 over_cap 267, A2 85). STOP for the lead.
- **The 22 remaining rows are a class the tree does not name**: emit-minted
  TOPOLOGY. Values are lawful and single-authored; what emit mints is the
  PAIR. No law priced it and no emit-side check covers it. This is a
  law-coverage gap at the nid-level final weld, not a value defect.

UNPAID / OWED:

- SPJC stays at 245 vs bar 189. Its within_shape residual is 103 rows of
  which 48 are this class; neither half is apron-law territory.
- THE COVERAGE GAP IS THE ACTIONABLE ITEM: the nid-level final weld inserts
  node references into partner ways AFTER the bake, minting ring adjacencies
  that no law ever priced and that the law-aware emit snap does not check
  (it validates baked pairs only). Either those inserts must re-enter the
  law, or the emit snap's scope must cover post-weld adjacencies. That is a
  spec question for the lead, not a lane fix.
- The 26 projection-residual rows belong with the solver-exit residue
  already docketed (A1/A2 over_cap).

## 2026-08-23 — weld before projection: implemented, and MEASURABLY INERT. STOP.

Spec `docs/specs/weld-before-projection-spec.md` (owner "proceed"),
implemented as 4d2aba0 on lane/compose. Budget honoured: fastpath count
first, then ONE SPJC build, then the confinement check. No HECA/CYXY
rebuilds — and the diff below is why none was warranted.

### The fastpath (A4 patches, artifacts only)

Adjacencies a reorder would newly price — both endpoints already baked,
pair never baked, none below `MIN_PAIR_DIST_M`:

| airport | newly priced | currently over the 1 % cap |
|---|---|---|
| SPJC | 200 (apron 101 / junction 99) | 26 |
| HECA | 503 (junction 276 / apron 227) | 127 |
| CYXY | 93 (junction 57 / apron 36) | 14 |

These EXCEED the nid-level weld's own insert counts (SPJC 68) — the first
sign that a second pass mints adjacencies too.

### The SPJC arm — the reorder ran and changed nothing

```
[weld-before-projection] SPJC: inserted 28 T-vertex(es) into 17 shape(s)
                         BEFORE the final projection
[final-projection] SPJC: CALL #1
[pav-builder] SPJC: final epsilon-wedge weld — inserted 142 vertex(es)
[pav-builder] nid-level final weld: inserted 68 on-edge node reference(s)
              *** POST-PROJECTION WELD RESIDUE ***
```

- **SPJC airside 245 — IDENTICAL to A4.** Bar 189.
- within_shape airside 103, sub-5 m > 2x class **48 — identical to A4**.
- `census_rows_diff` A4 vs this arm: **417 EXACT, 0 GONE, 0 NEW, net +0.**
  That is the confinement proof in its strongest possible form: not
  "confined to the weld class", but *no law row moved at all*.
- The patch DID change (body_sha 624f4f59454a → 21d687db4191) — the 28
  inserts landed — so the pass is real and surface-neutral, exactly as
  designed.
- `[apron-staged]` A1 over_cap 267 (both-hard 6) | A2 85 (78), senior moved
  in A2 = 0; `[transverse-bind]` bound 8,490 / exit_over_budget 208;
  **`[writeback-band]` worst > 10 m = 0** (worst clamp +0.08 m).

### THE STOP, and it is the one the spec pre-registered

> "a to_osm weld insert count > 0 on a pre-welded ring is a STOP (the two
> passes disagree on the weld set — fix the disagreement, never suppress
> the count)."

The count is **68 — unchanged from A4.** The pre-projection pass inserted
28 T-vertices and removed NOT ONE of the nid-level weld's inserts.

WHY, from the ordering the arm logs: the two passes are not the same weld
seeing the same geometry.

| pass | space | when | inserts |
|---|---|---|---|
| pre-projection weld (new) | ring / coordinate, `FINAL_WELD_TOL_M` | before the projection | 28 |
| **epsilon-wedge weld** | ring / coordinate | **AFTER the projection** | **142** |
| nid-level final weld | emitted nid chains, `_WELD_TOL_M` | inside `to_osm` | **68** |

The 68 adjacencies are minted by geometry that does not exist when the
pre-projection pass runs: the **epsilon-wedge weld inserts 142 vertices
after the projection**, and the nid-level pass then welds against those
rings. Moving the nid-level insert earlier cannot reach a class created
later. The spec scoped the change to "only the nid-level weld insert
moves", so closing this needs the epsilon-wedge weld's timing addressed —
a spec question, not a lane fix, and explicitly out of this spec's scope.

### Disposition

The reorder is KEPT (`O4_WELD_BEFORE_PROJECTION`, default ON): it is
measurably law-neutral (0 rows moved), surface-neutral by construction
(inserts at the edge's own interpolated altitude), and it puts the weld in
the architecturally correct place. It simply does not close the 22-row
class, and the new verification line now says so out loud on every build
instead of leaving a silent 68.

UNPAID / OWED:

- SPJC unchanged at 245 vs 189. The class split stands as attributed: 26
  projection-residual rows (solver exits over cap: A1 267 / A2 85) and 22
  emit-minted-topology rows, now proven to be minted AFTER the projection
  by the epsilon-wedge weld rather than by the nid-level pass.
- THE ACTIONABLE ITEM MOVES ONE PASS EARLIER: the epsilon-wedge weld
  (pipeline part 30j, 142 inserts at SPJC) is the author. Either it moves
  before the projection too, or the law-aware emit snap's scope must cover
  post-weld adjacencies. Both are spec decisions.
- HECA/CYXY were not rebuilt: the SPJC diff showed zero law-row movement,
  which is the budget's own condition for not rebuilding.

## 2026-08-23 — weld A1 (wedge insert moves too): also INERT. STOP, with the mechanism named.

Spec AMENDMENT A1 (main 7932a68), implemented as 53f72a4. ONE SPJC build.

### §1b does NOT fire — the halves separate cleanly

`snap_subcm_vertex_twins` and `enforce_conformance` were already two calls.
Better: **the wedge insert and the nid insert are the SAME function at the
SAME tolerance** (`enforce_conformance` / `FINAL_WELD_TOL_M`, whose
`_plan_shape_inserts` is THE one candidate enumeration). What distinguished
the wedge call was only its DEM/tile frame (the "cuts never fill" bound),
which the pre-projection pass now carries. The snap stays post-projection
per §1b; the pre-projection pass adds an *idempotent* snap because the snap
is the insert's documented precondition (without it the weld propagates
mm-apart twins — CYXY lockstep, 7.7e-5 m).

### The arm

```
[weld-before-projection] SPJC: snapped 370 sub-cm vertex twin(s) across 147 shape(s) first
[weld-before-projection] SPJC: inserted 28 T-vertex(es) into 17 shape(s) BEFORE the final projection
[final-projection] SPJC: CALL #1
[pav-builder] SPJC: final epsilon-wedge weld — inserted 142 vertex(es) into 80 shape(s).
              *** POST-PROJECTION WELD RESIDUE ... requires 0 here ***
[pav-builder] nid-level final weld: inserted 68 ... *** POST-PROJECTION WELD RESIDUE ***
```

- **SPJC airside 245 — identical to A4 and to the first reorder arm.**
- within_shape airside 103; **sub-5 m > 2x class 48 — identical.**
- `census_rows_diff` reorder-arm vs this arm: **417 EXACT, 0 GONE, 0 NEW.**
- Verification counts: wedge **142** (must be 0), nid **68** (must be 0) —
  both unchanged from every prior arm.
- `[apron-staged]` A1 267 (6) | A2 85 (78), senior moved in A2 = 0;
  `[transverse-bind]` exit_over_budget 208; **`[writeback-band]` > 10 m = 0.**

### THE STOP, and this arm names the mechanism

The two calls are now the same function, the same tolerance and the same
DEM frame — and they still disagree **28 vs 142**. So the disagreement is
NOT in the enumerations. It is in the GEOMETRY they are shown:

**114 of the 142 T-junctions do not exist when the pre-projection pass
runs.** They are minted between it and the wedge call by the passes that
emit geometry after the projection — adjacent-ground band emit, gap-fill
spines, crown-field completion, densify, tile cuts. The pipeline's own
comment beside the retired late projection lists exactly these as the
stages that "reshape rings after this point".

That refutes A1's premise the same way the first arm refuted §1's: moving a
weld earlier cannot weld geometry that does not exist yet. The residue is
not a weld-ordering defect at all — it is that **ring-minting emitters run
after the last pass that prices rings**.

### Disposition and what is actually owed

Both reorders are KEPT (`O4_WELD_BEFORE_PROJECTION`, default ON): measured
law-neutral (0 rows moved across two arms), surface-neutral by
construction, and correct ordering. Neither closes the 22-row class, and
the verification lines now say so on every build.

THE ACTIONABLE ITEM IS NOT ANOTHER WELD MOVE. Two attempts have now
measured the same answer, so the attempt cap is reached and this is a STOP:

- either the post-projection ring-minting emitters move ahead of the
  projection (a large re-ordering, far beyond this spec), or
- the law-aware emit snap's scope extends to post-weld adjacencies so the
  minted edges are checked where they are made, or
- the class is adjudicated: these are sub-5 m ring edges at a weld, whose
  |de| is 0.06-0.46 m, and the question is whether a 0.5 m step across a
  0.7 m weld chord is a defect the surface should be graded for at all.

SPJC stays at 245 vs 189, class split unchanged: 26 projection-residual +
22 emit-minted-topology.

## 2026-08-24 — the read's staged-solve fixes: SPJC 245 → 207, A2 both-hard 78 → 0

Five items from the parallel read, implemented as 338c557 + 08b00e3 on
lane/compose. ONE SPJC build plus a cheap CYXY regression guard.

### The conforming-mint spec is PARKED (ecf15a5)

The "22 emit-minted" class it was written for was a JOIN ARTIFACT in my own
instrument: `pair_caps` exported lat/lon at 7 dp (half-ulp 0.0056 m) and my
26/22 split came from a ~5 mm proximity join against that quantum. At 10 mm
all 48 SPJC rows join to baked pairs. The canonical-identity-join law fired
on the tool I built to test it; my "the PAIR is new at emit" conclusion is
WITHDRAWN. The ruling stands and the mechanism is kept intact and tested
but gated OFF (`O4_CONFORMING_MINT=1` arms it) until a real instance exists.

### Results

| | battery | A4 | **read fixes** | bar |
|---|---|---|---|---|
| SPJC adjudicated airside | 189 | 245 | **207** | 189 (+18) |
| CYXY adjudicated airside | 75 | 18 | **16** | 75 (PASS) |

| SPJC | A4 | read fixes |
|---|---|---|
| A1 over_cap (both-hard) | 267 (6) | 267 (6) |
| **A2 over_cap (both-hard)** | **85 (78)** | **0 (0)** |
| within_shape airside | 103 | **69** |
| sub-5 m > 2x class | 48 | **25** (cluster 17) |
| by cap | 90 @1.0 + 13 @1.5 | 56 @1.0 + 13 @1.5 |
| senior moved in A2 | 0 | **0** |

**A2's both-hard population is GONE** — 78 → 0 — which is what item 1
predicted: those were interior pairs frozen at both ends because neither
pass priced them. 76,468 both-senior interior pairs joined A1 at SPJC
(2,184 at CYXY), and A1's own counts are unchanged (267/6), so the newly
priced law was absorbed without cost to the strict class.

### Confinement proof

`census_rows_diff` A4 → read fixes: **378 EXACT, 39 GONE, 1 NEW, net −38**.
GONE: 35 `within_shape apron|apron` airside, 2 `transverse apron|apron`, 2
`frontage_near_miss`. NEW: 1 `within_shape apron|apron`. Every moved row is
in the apron interior/strict classes — nothing beyond, which is the stated
condition for not rebuilding HECA.

`[writeback-band]` worst > 10 m = 0 (worst clamp +0.08 m);
`[transverse-bind]` bound 8,490 / exit_over_budget 208.

### Items delivered

1. Both-senior interior pairs enter A1 at their own 5 % cap; A2 keeps only
   pairs with an interior mover. Seniority hoisted above A1 so both
   sub-stages partition from ONE answer.
2. One partition input: the runtime publishes its own partition and the
   exporter reads it (was 2,395/751 exported vs 2,962/83 at runtime).
3. (a) `excluded_both_hard=N` names the population dropped from the swept
   set but counted by the tally; (b) A2 gains its own both-hard docket —
   correctly SILENT this arm, because A2's both-hard is now 0; (c) an
   all-hard hyperplane row no longer holds `any_active`.
5. `pair_caps` / `mesh_edges` export at the canonical 11 dp instead of 7,
   so identity joins are possible at all — the root cause of the artifact.

UNPAID / OWED:

- SPJC is still +18 over its bar (207 vs 189). Its within_shape residual is
  69 rows, of which 25 are the sub-5 m > 2x seat/weld class (17 in the
  declared cluster) — the parallel read's territory, not this lane's.
- HECA HAS NO ARM under these fixes. The rows_diff showed no movement
  beyond the apron classes, which the budget makes the condition for not
  rebuilding, but "no arm" is not "no regression": HECA's 1,273 is
  unverified against this tree.
- A latent NameError was found in self-review and fixed (08b00e3): the
  `excluded_both_hard` argument had landed in a fourth function where the
  name does not exist. It survived the SPJC build only because that path
  did not execute.

## 2026-08-24 — HECA verification arm under the read fixes: 1,273 → 1,129

ONE HECA build at `git_head=d6b96b9` (read fixes, clean tree,
`code_tree_hash=a199962718ff`), staged + transects, rc=0, shared repo
UNCHANGED. A5 was NOT in this build — see the provenance note.

### Results — HECA passes with more margin

| | battery | A4 | **read fixes** | bar |
|---|---|---|---|---|
| adjudicated airside | 1487 | 1273 | **1129** | 1487 (**PASS −358**) |
| within_shape airside | 1284 | 1106 | **961** | |
| transverse airside | 95 | 35 | **35** | |
| A1 over_cap (both-hard) | — | 1388 (2) | **1553 (2)** | |
| **A2 over_cap (both-hard)** | — | **328 (315)** | **5 (1)** | |
| senior moved in A2 | — | 0 | **0** | |

**A2's both-hard population collapses 315 → 1**, the same effect measured
at SPJC (78 → 0): those were interior pairs frozen at both ends because
neither pass priced them. **21,902** both-senior interior pairs joined A1
at HECA. A1's over_cap rises 1388 → 1553 — it is now enforcing law that
previously went unpriced — while the CENSUS falls, which is the right
direction: more law enforced, fewer violations emitted.

within_shape airside by cap: **928 @1.0 % + 31 @1.5 % + 2 @8 %** — still
none at the 5 % interior cap. By chord: ≤60 m **642** (A4 789), 60–200 m
292, >200 m **27** (unchanged), max chord 555 m. Seat/weld residue
(≤5 m, >2x) **104** (battery 167, A4 123).

`excluded_both_hard` reports for the first time: up to **14,586** on the
largest projection — the population dropped from the swept set but counted
by the tally, which is exactly the reconciliation gap item 3(a) named.

`[transverse-bind]` bound 26,728 / exit_over_budget 2,426;
**`[writeback-band]` worst > 10 m = 0** (worst clamp +6.17 m).

### Confinement

`census_rows_diff` A4 → read fixes: 4,051 EXACT, 6 MOVED, **318 GONE, 142
NEW, net −176**. GONE is dominated by 234 `within_shape apron|apron`
airside; NEW by 87 of the same class. Movement is concentrated in the apron
within-shape and transverse families with a groundside tail — the classes
the change touches.

### PROVENANCE NOTE — a real instrument gotcha

The census printed `frame: sha=5ce4eddc`, which is the A5 commit, and A5
was committed at 08:52:07 while this build ran 08:27:47–08:52:02. The
PATCH's own record is `env.json: git_head=d6b96b9, git_dirty=False,
code_tree_hash=a199962718ff` — read-fixes only, A5 absent. **The census's
`frame:` line reports the tree at CENSUS time, not the tree that built the
patch.** Any arm censused after a subsequent commit will mis-attribute
itself unless the reader checks `env.json`. Worth a harness fix; recorded
here so no later reader takes the census line as the build's provenance.

UNPAID / OWED:

- SPLP / KAFW / KDFW still have no arm under this tree.
- HECA's remaining 961 within_shape airside rows are 642 at ≤60 m, of which
  104 are the sub-5 m seat/weld class — the parallel read's territory.
