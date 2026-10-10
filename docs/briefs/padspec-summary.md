# padspec summary (Fable, 2026-10-07) — see padspec-notes.md, padspec-review.md, design-surface-spec.md §56

Verdicts: outline TRIM at geom.cluster_outlines (1,717->650 OTHH); roads within 10 m ABSORBED (26/29 at site); collar DELETED (carries 0.00-0.48 m, minted 5-15 m, 11 slivers at site); blocks/hold/weld KEPT; landing bank KEPT. Owner Q: courtyards >=200 m2 kept (yes); jetway roots in outline (yes); residual as reported rim step (yes).

## Scout consumer census (grep-verified, file:line) — raw report

CONSUMER CENSUS — building-pad geometry (worktree padspec, HEAD b6e2371f). Read-only; nothing built.
All paths relative to /Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP/ ; `v2/` = src/auto_patch_v2/.

CORRECTIONS TO THE BRIEF (verified)
- There is NO `[platform]`, `[cluster_pad]` or `[pads]` law table. The keys live in `[building_pad]` (v2/law/structures.toml:490), `[placement]` (:688) and emit.toml (design keys). families.toml carries the census family records.
- Blocks are NOT `building#N`. Block ref = `<unit>/b<k>` (BLOCK_SEP, v2/model/planar.py:90-95); collar = `<ref>#collar` (COLLAR_SUFFIX :58); `<ref>#k` is the SURPLUS-PIECE spelling of one cluster pad cut by the runway difference (v2/classify/evidence.py:766). Also `<unit>/p<k>` planes (model/planar.py:113) and `#plateau:<block>` apron pieces (PLATEAU_MARK :70).
- "Jetway basement floors": no such thing found (grep jetway×basement/floor = 0 hits). The jetway object is the JETWAY STRIP (apron projection) + riders; see D.
- The ref grammar has ONE site: model/planar.py `is_collar_ref` :61, `platform_ref_of` :80, `block_ref` :93, `block_of` :98, `unit_ref_of` :147. But ~15 readers still spell `ref.split("#")[0]` by hand (rows marked S below).

1. PIPELINE ORDER
 P0 pack stage, pipeline/build.py:359-602: `partition_pack` (:466) -> `planar.cluster.clusters` (:543, def v2/planar/cluster.py:204) -> `Airport.partition/groups/clusters` (:556). Reads pack OBJ8/DSF placements + DEM (connector verdicts, cluster.py:150).
 A  classify (build.py:668 `classify`) -> `build_evidence` -> `_pads` (v2/classify/evidence.py:565, called :299). Reads BOTH: pack clusters via `_cluster_pads` (:468) -> `geom.cluster_outlines` (:541; def v2/geom/cluster_outline.py:325) with `deck_shades` (:533) and OSM building evidence (:551, :625); and the admitted footprints no cluster covers (fallback union, sources rules.toml:128 `["osm","dsf:fac","dsf:object","dsf:agp"]`). Gates: runway difference, `min_area`, boundary gate + `pad_gate_near_m`, `_absorb_enclosed`, `_drop_skirted` (:778). Writes `(ref, Polygon)` with ref `building{N}` / `building{N}#k` (:757-766), `PAD_REFUSED` (:462). Cell minted at v2/classify/roles.py:641 `add("building", ref, poly, "building")`; groundside cut back from pads roles.py:874 (`groundside_cutback_m`).
 C/B arrangement, v2/planar/overlay.py `build_arrangement` (:179), pads = regions with `is_rigid_role` (:230), in this order:
   1 `apron_cut_to_pads` :242 (pad_cut.py:68) — apron cut back to pad footprint before pass A
   2 `pad_terrace_split` :247 — writes TERRACES
   3 `platform_split` :255 (platform.py:316) — mints PLATFORM (pad eroded by C, same ref) + COLLAR (`ref#collar`, platform.py:453); calls `pad_blocks.plan_blocks` (platform.py:329, pad_blocks.py:543) and `_mint_blocks` (:530) -> `<unit>/b<k>` + `/b<k>#collar` (:565-568). Reads pad polygon, airside regions, DEM, `Airport.partition`/clusters (pad_blocks.py:428, :463, `unit_base` :499). Writes PLATFORMS, HELD, BLOCK_PLANS (platform.py:325-330, :403-440, :571-573).
   4 `landing_cut` :263 (landing.py) — writes LANDINGS, `.../landing<k>#collar` (landing.py:226)
   5 `plateau_cut` :267 (pad_cut.py:481) — stand-zone plateaus cut from the apron; writes PLATEAUS
   6 pass A, `build_rim` :325, `airside_clip` :327 (pad_cut.py:199; `airside_vertex_snap` pad_cut.py:312) — writes PAD_AIRSIDE (:369-370)
   7 ribbons (v2/planar/ribbons.py:50-66): road ribbons clipped by airside UNION PADS; `merge_platform_faces` ribbons.py:170.
 D  jetway strips AFTER stage 1: build.py:1059-1060 `jetway_strips(pm, law, airport, cs, rider_candidates(...))` (constraints/jetway_strip.py:186; riders airport/riders.py:173), projected in solve/project_strip.py:97, published build.py:1274-1285.
 Sidecar keys (pipeline/publication.py:502-559): `cluster_pads`, `pad_refusals`, `platforms`, `deck_shades`, `pad_cluster_mismatch`, `terrace_joints`, `pad_pavement_no_step_edges`, `pad_airside_renode`; `jetway_strips` :638. Allow-list emit/osm_adapter.py:177-194. Module registries carried into captures: pipeline/capture_state.py:139-160 (BLOCK_PLANS NOT carried, :59).

2. LAW KEYS (verbatim values; comments truncated where long — full text at the cited line)
 structures.toml `[building_pad]` :490
  :491 weld_to_touching_pavement = true   # contact = value (09-01g)
  :492 footprint_outside_pad_m = 0.0   # NO footprint outside the pad — outline close retired (09-01g)
  :493 groundside_cutback_m = 0.6   # mixed pad: welds airside, groundside cut back and may differ (09-01i, 01e standoff)
  :494 min_area_m2 = 250.0   # tiny pads fold into their host (08-24 :1687; PAD_MIN_AREA_M2)
  :495 in_basin_sits_at_floor = true ; :496 step_exemption_pad_to_pad = true
  :497 frontage_near_miss_m = 1.0   # soft-pavement ring edge within this of a pad, unshared, is a FRONTAGE across a sliver (comment cites "SPJC building29 0.68 m source offset")
  :498 platform_collar_max_m = 15.0   # "THE MINTED WIDTH of every collar, not just its ceiling ... narrowed to the widest emit.design.bank_sample_m station that still leaves a platform ... floor emit.design.bank_min_width_m ... a pad no collar down to the floor leaves a platform in gets NO platform (refused, reported), never a steeper collar. × emit.design.bank_slope = the largest end-ground step a SOLID connector joins across"
  :499 platform_collar = true   # "a unit pad (>= [placement] cluster_pad_min_m2) that FRONTS AIRSIDE is minted as a PLATFORM ... inside a COLLAR (the annulus, a 1:3 bank from the welded rim whose TOE the solve places) ... An experiment knob awaiting the owner's sim read: false = today's welded plate"
  :500 frontage_hold = true   # "every minted platform is TESTED at the mint (planar/pad_blocks.py) and a unit that fails is CUT into flat blocks at its necks (<ref>/b<k>) ... false = 29s contact-led tilt"
  :501 frontage_hold_margin_m = 0.3   # flat-pad spec §2 (1): the DEM proxy's allowance (= the §17 body float bar)
  :502 frontage_blocks_max = 5   # a unit needing more blocks is a STOP for the owner
  :503 frontage_soft_roles = ["apron", "junction"]
 structures.toml `[placement]` (key lines, values exact; I did not capture each key's line number — awk listing of :783-1093): rigid_reach_m 2.0; cluster_pad_min_m2 5000.0 (:796); pad_between_aprons false; airside_floor false; footprint_touch_m 0.5; rider_reach_max_m 12.0; floor_split_m 0.5; pad_from_cluster true (:877); pad_airside_clip true; pad_keeps_footprint true; pad_airside_snap_max_m 5.0; chain_min_height_m 2.5; contents_min_fraction 0.95; sheet_chain_min_fraction 0.5; post_max_area_m2 4.0; post_max_extent_m 3.0; flat_line_max_width_m 1.0; post_bridge_gap_m 1.25; connector_span_m 200.0; connector_solid_gap_m 20.0; min_tall_base_fill 0.002; tall_member_min_extent_m 2.5; building_evidence true; evidence_min_height_m 6.0; evidence_min_coverage 0.0; seat_tilt_max_deg 1.5.
 structures.toml `[skirt]` :505-513: perimeter_fraction 0.5, depth_tolerance_m 0.5, min_depth_m 0.3, edge_tolerance_m 0.5, pad_cover_fraction 0.5, drops_pad true, seat_low_side true.
 emit.toml: :649 jetway_strip_m = 40.0 ("40 m covers every HECA gate and 119/130 LEMD gates"; 0 disarms); :650 stand_zone_radius_m = 30.0; :651 stand_zone_startup_reach_m = 60.0; :652 stand_zone_startup_kinds = ["gate","tie_down"]; :653 jetway_strip_plane_tol_m = 0.5; :730 bank_min_width_m = 5.0 "# the narrowest bank / collar". Ruling strings: :589 and :993 "structures.building_pad platform_collar rim", :785 "platform plane", :786 "frontage_hold", :992 "platform_collar bank". (emit.toml table headers for these lines NOT verified; families.toml names the parameter `emit.design.jetway_strip_m`.) `bank_slope`, `bank_sample_m`, `pad_slope_max` values NOT read.
 classify/rules.toml: :128 sources (above), :129 facade_strip_min_reach_m = 5.0, :130 pad_gate_near_m = 1.0.
 precedence.toml:74 building = { family="common", side="airside", value=true, aeroway="apron", rigid=true } — `building` is the only `rigid` hit in that file.
 No `[pad_cut]` / `[pad_blocks]` keys exist; the cuts read the keys above.

3. CENSUS (BREAK = depends on collar cells / inner-outer pair; ROLE = reads role only; S = hand-spelt split("#")[0])
 MINT / DERIVATION
 geom/cluster_outline.py | cluster_outlines :325, deck_shades :118, airside_vertex_snap :816 | A | the one outline derivation | callers evidence.py:541, constraints/cluster_pad.py:153, pad_cut.py:312
 classify/evidence.py | _pads :565, _cluster_pads :468, _drop_skirted :904 | A | mints refs | above
 classify/roles.py | :641 mint; :874 pad cutback of groundside cells (`mixed_pad_cutback` :920) | A ring | ROLE+shape
 classify/ribbon_mint.py:172-177 | A ring buffered by groundside_cutback_m as "occupied" for road ribbons (D) | ROLE+shape
 classify/facade_mint.py:136, :180 | A ring knives; host join S | ROLE+shape
 classify/airside_edge.py:332, :339 | excludes role building from the airside edge | ROLE
 planar/overlay.py:230-267, :369 | A/B/C orchestration; :822 PLATEAU_MARK | BREAK-adjacent (order)
 planar/pad_cut.py | apron_cut_to_pads :68; airside_clip :199 (:241 rigid select); plateau_cut :481 reads HELD + `platform_ref_of` outlines (:536) | A,B,C | plateau needs HELD (block/platform registry), not the collar cell itself
 planar/platform.py | platform_split :316 (:365 skips refs ending COLLAR_SUFFIX), _mint_blocks :530, merge_platform_faces :651 (:669 keys refs + collar) | B,C | BREAK
 planar/pad_blocks.py | plan_blocks :543, unit_base :499, bay_m :535 (reads jetway_strip_m) | C | reads pad polygon, DEM, partition
 planar/landing.py | :94-98 HELD blocks; :119-130 is_collar_ref/platform_ref_of/block_of; :226 mints landing collar; :267 S | B,C | BREAK
 planar/pad_sliver.py | plateau scraps (:209-224) | C | PLATEAU_MARK
 planar/pad_terrace.py :114-217 | A ring vs touching apron levels -> TERRACES | shape
 planar/ribbons.py :50-66, :208-211 | D: ribbons clipped/welded against airside ∪ rigid faces; :170 merges platform faces | reads B by PLATFORMS | BREAK-adjacent (merge keys on collar refs)
 planar/ribbon_weld.py:26 | D: uses pad_cut._polys | shape
 planar/cluster.py :190 | platform_collar_max_m × bank slope = connector step_max | law key only
 planar/basins.py:422, :791; planar/structures.py:284, :964; planar/structure_approach.py:100; planar/structure_service.py:416; planar/wall_corridor_ramps.py:131, :235-236 (S) | A | ROLE (+ ring as knife/obstacle)
 planar/shapes.py:275, :518; planar/weld.py:66; planar/build.py:173 (TERRACES) | rigid role | ROLE
 CONSTRAINTS / SOLVE
 constraints/platform.py | collar/platform pairing :99-112 (returns only refs having BOTH collar and platform faces); rows :157-164 ("#collar" literal); :241-266 unit join (S at :241, :251); LANDINGS :422-460; refused :507-521; hold sets :630-750 (writes HELD near_miss :750); PLATEAUS :931; sidecar record :996-1014 | B,C | BREAK (pair assumed)
 constraints/pads.py | _pad_polys :237; plate excludes collar :546; `platformed` = any collar face :605 (switches off per-vertex relief); held :871; frontage reads collar OUTER rim minus inner ring :970-980 | A,B | BREAK
 constraints/cluster_pad.py | cluster_polys :153; cluster_pad_faces :183; _base_ref :216-231 (S); pad_cluster_mismatch :324; plane groups, collar rides platform entry :429-442; block split :459-465 | A,B,C | BREAK
 constraints/pad_frontage_gs.py :167-187 (collar -> base ref, S), :297, :324, :369 | B + groundside pavement/roads (D) | BREAK
 constraints/pavement_cap.py :77 PAD_ROLE, :116-117 collar vertices excluded, :154 | B | BREAK
 constraints/ceiling.py:163-165 | imports COLLAR/PLANE/RIM rulings from platform | B | BREAK (ruling names)
 constraints/jetway_strip.py | :142-146 cluster_pad_faces + _pad_polys; :177-180 "outline a rider stands on is the collar's" (S); :238 (S); :305-316 strip disarmed on HELD units | A,B,C,D | BREAK
 constraints/no_step.py :429-790 | HELD datum/plateau vertices, "platform:<ref>" row ids :631-641 | C | BREAK on HELD
 constraints/pad_fronting.py :117-139, :212-216, :237 | _pad_polys, plane_groups, TERRACES | A | shape
 constraints/pad_relief.py:87 | _pad_polys | A | shape
 constraints/taxi.py:105, :157; constraints/junction_mesh.py:250; verify/within.py:351 | common.roles["building"].longitudinal cap | ROLE
 constraints/apron.py:175, :378; gap_follow.py:158 (S :106,:167,:234); routes.py:232; structures.py:826 (S :142,:264,:732); foot_rows.py:403-406; roads.py:61-63 (stage_air_vertices) | rigid role | ROLE
 solve/design_ground.py :110-157 coverage_edge_collar_vertices | B | BREAK (early-returns with no collar, :140)
 solve/project_strip.py :385 (comment: a pad with a collar gives its RIM's level), :419 pad_edges keyed S | A,B,D | BREAK-adjacent
 solve/design_roles.py:18, solve/pin_yield.py (prose only :35-39), solve/design_assemble.py (collar hit, not opened) | NOT VERIFIED beyond grep
 model/islands.py :58-73 | rigid faces WITH HOLES = courtyards — a collar is a rigid face with a hole | B | BREAK-adjacent (collar hole vs courtyard; not read further)
 model/platform.py :150-175 | datum vertex via literal "#collar" :164-165 | B,C | BREAK
 VERIFY / PUBLISH / EMIT
 verify/within.py :371-378 | skips collar shapes | BREAK; verify/pads.py :137 pad_flat skips collar | BREAK; verify/jetway.py :31-40 | D sidecar; verify/census.py :128-150 notes; verify/frame.py:198 rigid | ROLE
 pipeline/publication.py | PAD_AIRSIDE :99-118; PAD_REFUSED :279-295; cluster_pads :308-313; platforms :669-688; jetway_strips_ll :692-737; pad terraces :914-988; S joins :1129, :1204 | A,B,C,D
 pipeline/late_stage.py:54, :95 (S) | ROLE
 emit/osm_adapter.py :177-194 | sidecar key allow-list only (no collar geometry logic found in my grep; :1154 is a comment)
 OBJECT STAGE (reads the SIDECAR, role literal `building`)
 airport/placement_read.py | PAD_FACE_ROLE :53; pads exclude collar :99-100; `_collars_as_platform` :111-146 publishes the collar's OUTER ring under the platform ref with platform-plane heights — "THE ONE SITE the object stage learns of the platform" | B | BREAK
 airport/pad_block_seat.py | block_rings :50 (block_of :56), sever :115, seat_unit :186, split_units :277 | C | BREAK on `/b<k>`
 airport/anchor_rule.py | PadRing :84, _pad_of :351, fold_pad_ref :386, pad_contains :413, BUILDING :69 | A ring+z | shape
 airport/placement_family.py :793-823, :891; footprint_unit.py :82, :199, :762, :826, :911 (src label "cluster_pad"); footprint_seats.py :49, :150; placement_body.py :41, :484; placement_plan.py :122; placement_file.py :343, :500; riders.py :279-345 (fold_pad_ref, jetway_strips `pad_ref`) | PadRing consumers | shape
 airport/road_ramp.py :1209-1227 | pad_roles faces | ROLE+ring; airport/footprint_connector.py :701-709 | step_max = platform_collar_max_m × bank_slope | law key
 airport/obj8_grade.py:830, skirt.py:23, pack_partition.py:470/:552/:727 (deck shades stamp), partition_code.py:102 (cache fingerprint lists geom.cluster_outline) | indirect
 DROPPED from the starting table (no direct read found by grep): airport/placement_atom.py, airport/placement_contact.py (only `m_per_deg_exact` imported by placement_read), airport/contact.py (matched only on a generic term; not opened). planar/pad_cut does not match `#collar` by name except through platform_ref_of.

4. check_grade.py (tools/check_grade.py)
 pad_airside_weld | _check_pad_airside_weld :6813, call :13159 with `_PAD_SLOPE_MAX` (= emit.within_shape.pad_slope_max, :6806; fallback 0.01 :6809) and `_HARD_TOL_M` | a pad vertex shared with airside standing further from another vertex of the same pad than cap×d; computed from the patch; SKIPS collar ways :6857 | LAW_FAMILIES :10280
 pad_cluster_mismatch | :6919, call :13172 | prices sidecar `pad_cluster_mismatch`; families.toml:120-122 parameter `structures.placement.pad_from_cluster` | :10273
 pad_airside_renode | :6983, call :13203 | sidecar `pad_airside_renode`: airside nodes minted/deleted by the pad stage; bar = empty | :10290
 platform_rim_relief | :7038, call :13222 | sidecar `platforms` (rim_relief_max_m, worst_ll, collar_m, collar_needed_m); REPORT; families.toml:208-210 parameter `structures.building_pad.platform_collar_max_m` | :10303
 pad_frontage_hold / pad_frontage_infeasible | _check_pad_frontage :7068 (held True/False), calls :13229, :13234 | held contact off datum by > frontage_hold_margin_m / unheld contacts; from `platforms` | :10313, :10316 (TWO family names from one function)
 platform_refused | :7142, call :13245 | `platforms` records with `refused`; families.toml:254-256 same parameter | :10306
 Also: jetway_strip :7163 / :10297 (families.toml:154-156, `emit.design.jetway_strip_m`); `_check_frontage_near_miss` :9549; `_is_platform_collar` :7028 (literal "#collar" :7031) used at :2491, :6857, :7749 (pavement-cap exclusion) — all three BREAK/Change if collar ways vanish; :10582 reads `<unit>/p1/b2`.

5. AIRPORT-SPECIFIC / HARD-CODED
 - No ICAO branch found in v2 code: only `airport/dsf_write.py:1138 if icao == plan.icao` (generic) and `emit/surface.py:14 "icao": "CYXY"` (looks like a docstring/example; NOT opened).
 - Airport names appear in COMMENTS as calibration evidence for thresholds: structures.toml:497 (SPJC building29), :498 (KCLT/SPJC/HECA platform counts), emit.toml:649 (HECA/LEMD gates), :653 jetway_strip_plane_tol_m = 0.5 "sits between the largest passing (0.481) and the smallest refused" HECA/SPJC pads, rules.toml:130 pad_gate_near_m = 1.0 "the smallest value carrying fac201" (SPJC Cargo_Terminal). The last two are thresholds placed between named airports' measurements — for the owner/spec author to judge against RULINGS 05e.
 - Literal "#collar" outside model/planar: constraints/platform.py:157-164, model/platform.py:164-165, check_grade.py:7031. Literal role "building": placement_read.py:53, pavement_cap.py:77, anchor_rule.py:69, plus the ROLE rows above.
 - Hand-spelt `split("#")[0]` joins (S rows) are a second spelling of `platform_ref_of`/`unit_ref_of`; they do NOT strip `/b<k>`, so a block face joins as `<unit>/b<k>`, not `<unit>` (constraints/cluster_pad.py:231 wraps it in unit_ref_of; the others do not).

NOT VERIFIED / NOT DONE
 - No brief pack was named; `tools/docq.py`, `tools/blast.py` and `frames.py` were NOT run — this census is grep + targeted reads only.
 - Function bodies were opened only for: evidence._pads, overlay.build_arrangement :226-270, placement_read :85-140, constraints/platform :96-112, pads :542-548/:601-608/:966-980, cluster_pad :425-442, verify/within :366-378, verify/pads :132-140, project_strip :412-422, the check_grade docstrings. Every other row is a grep hit at the cited line; "what it does" there comes from the matching line/adjacent comment.
 - Not opened: solve/design_assemble.py, law/design_schema.py, law/model.py, law/rebake_schema.py, model/frame.py, model/rebake.py, pipeline/xplat.py, airport/{bridge_family, footprint_carry, placement_census, placement_write, pool, sunken_roads, wall_geometry, frame_entry}.py, geom/feet_graph.py, geom/pad_evidence.py, planar/{group, channel_witness, structure_underpass}.py (all matched `platform`/`jetway`/`collar`; some `platform` hits may be the OS sense).
 - `[placement]` per-key comments and line numbers not quoted individually; emit.toml section headers not confirmed.
