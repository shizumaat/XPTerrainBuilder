# Appendix A — THE LAW inventory for auto-patch-v2 (scout, 2026-09-03; read-only, no builds)

Source of truth for `auto_patch_v2/law/`. Cited lines are v1 as of main e4c568c6.


All paths under `/Users/noah/XPTerrainBuilder/Ortho4XP/` unless absolute. No builds were run; nothing below required one.

## 1. Law families (the instrument)

Register: `tools/check_grade.py:6179-6237` `LAW_FAMILIES` (key, title, bucket). Acceptance frame: `law_context_from_sidecar` `:6971-7060` (refuses without `.axes.json`, `:6989`), `LAW_TRUE_KNOBS` `:7251-7256` (1.5 %, proximity = `SHARED_VERTEX_TOL_M` 0.5 m `src/auto_patch/layout.py:99`, 5 m edge search, 0.5 m step), `run_checks_law_true` `:7259-7275`, `run_checks` `:7340-7367`, ruleset taken from the sidecar never re-derived `:7392-7398`; `row_side` `:7278-7313` (airside / groundside / mixed via `_GROUNDSIDE_ROLES` `:1035-1038` = groundside_pavement, service_road, service_junction, tunnel_ramp; mixed counts against airside). Ruleset resolution: `config.resolve_ruleset` `:8620` (K-prefix → FAA `:8608-8609`), `DEFAULT_RULESET="icao"` `:8600`; `Ruleset` dataclass `:7457`, `ICAO_RULESET` `:8009`, `FAA_RULESET` `:8312`.

| key (bucket) | measures | cap / source | roles | ruling |
|---|---|---|---|---|
| within_shape | ring vertex-pair grade vs role cap (apron: nearest-spine chord only) | `ROLE_GRADE_LIMITS` config:1904 | all value roles | 08-21b/c/d RULINGS:1662-1672; 08-24 :1685 (5 % only back-edge zones) |
| road_cross_section | across-axis pairs on road rings | `SERVICE_ROAD_MAX_TRANSVERSE` 0.020 config:954, axis split ≥45° :993 | service_road/junction | 08-25g :1798 |
| plane_gradient | triangle-plane slope | role cap | junction mesh (`mesh_edges`) | user 2026-07-05 (sidecar `mesh_edges`) |
| runway_end_skirt | end-skirt down-grade & rate | FAA near zone 61 m/3 %, 5 % max, 0.02/30.5 per m config:8406-8410; ICAO 5 % :8091-8094 | runway_clearance | reg-set 08-08 :1193 |
| terrace_joint_route / _strip / terrace_actual_step | declared apron terrace joints crossing routes / inside strip / exceeding declared step | sidecar `terrace_joints` | apron | 08-06 no joints across roads :783 |
| basin_floor_declaration | basin facility floor vs body depth | sidecar `basin_facilities` | object basins | 08-26 :1847 |
| adjacent_ground_tear / strip_seam_tear | graded-strip tears (wall straddle exempt) | zone envelope `grade_law.adjacent_ground_envelope` :1530 | graded_strip | 08-01 zone law RULINGS:38 |
| transverse | cross-corridor grade | `Ruleset.taxi_transverse_max` (ICAO A/B 2 %, C–F 1.5 % config:836/8106) | taxi family | STANDARDS ICAO §3.9.11 |
| drainage_spine | spine at/above lower pavement | `DRAINAGE_SPINE_LAW_ENABLED` config:6398 | pockets | 08-01 clarification (enclosed pockets) |
| apron_lattice_membrane | lattice pair over apron budget | `APRON_LATTICE_SPACING_M` config:10194 | apron | 08-24b/c :1689-1691, 08-26 :1858 |
| airside_no_step | direct-distance grade + rate of change | `AIRSIDE_NO_STEP_WINDOW_M` 150, K 16 config:10243-10259; `TRANSVERSE_NO_STEP` :10370 | all airside | 08-27 :1861 |
| lateral_contiguity | road vs strictest touching class | `grade_law.lateral_contiguity_cap` :1988 | road ↔ apron | 08-25b :1698 |
| strip_longitudinal / strip_arc | strip abeam slope, rate | `RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE` config:6979 (FAA = runway cap :6981); arc 0.02/30.5 | graded_strip | reg-set 08-08 |
| resa_transverse | end corridor transverse | `resa_transverse_max` 0.05 | runway_clearance | reg-set 08-08 |
| raoa | ICAO-only rate | 0.02/30 config:8163 | runway strip | reg-set |
| drainage_minimum | surface flatter than minimum | FAA `apron_min_drainage_grade` 0.005 :8437; runways only crown | runway | 08-13b/14 :1604-1606 |
| runway_crown | crown below declared drop | `RUNWAY_CROWN_TRANSVERSE` 0.010 config:865 | runway | 08-05 :490-497 |
| wall_in_runway_strip | wall inside strip keep-out | `grade_law.runway_strip_wall_keepout_rings` :795 | retaining_wall | 08-21d :1672 |
| stacked_nodes | one coordinate, disagreeing values | — | all | canonical identity |
| cross_shape (cross) | proximity pairs across shapes | `LAW_TRUE_KNOBS` | all | — |
| frontage_near_miss (cross) | pad ↔ pavement across sliver | — | building | 08-08 :1106 |
| vertex_to_edge_step / mid_edge_step (steps) | steps; `STEP_EXEMPTIONS` :6253 (building↔building only) | 0.5 m | all | 06-20 |

Outside the register (instruments only): `verification.check_ols_surfaces`, `check_object_pads`, `airside_certificate` evidence `:6967`.

## 2. Role caps and precedence

`ROLE_GRADE_LIMITS` `src/auto_patch/config.py:1904-2001`: runway `RUNWAY_MAX_GRADE` 0.015 (:1393), end zones `RUNWAY_END_GRADE` 0.008 (:1394), K 305 m (:1578); primary/secondary_parallel, stub, cross_connector, junction `TAXI_MAX_GRADE` 0.015 (:821; ICAO code A/B narrow 0.030 :829); apron/building `APRON_MAX_GRADE` 0.01 (:1004, :1059); tunnel_ramp 0.040 (:1406); service_road/service_junction 0.080 (:1341); groundside_pavement = road cap (:1526); `None` (no within-shape rule) for boundary, retaining_wall, taxiway/runway_clearance, graded_strip, ols_cut, bridge_trench/causeway, object_pad. Interior apron fan cap `FAN_RAMP_CAP` = 0.05 (:1556). Transverse: `TAXI_MAX_TRANSVERSE_NARROW` 0.020 :836; road 0.020 :954; crowns 0.010 :865-867. ICAO vs FAA per-code tables: runway ICAO {1,2: 2 %, 3: 1.5 %, 4: 1.25 %} :8020-8022 vs FAA narrow 2 %/wide 1.5 % :8322-8324; end zone FAA capped 762 m :8329.

`layout.AUTHORITY_PRECEDENCE` `src/auto_patch/layout.py:443-453`: runway, runway_crossing, primary_parallel, secondary_parallel, stub, cross_connector, junction, tunnel_ramp, apron, building, service_road, service_junction, groundside_pavement; unnamed roles tail (:456-464). Rationale :424-442 (RULINGS 2026-08-03 "emitters emit, never grade"; averaging minted HECA's 1,497 groundside rows — memory `emit-consensus-mints-violations`). `SOFT_RECEIVER_ROLES` :413-422.

## 3. Senior invariants (one line each, RULINGS.md anchor)

- Airside is king — groundside has zero pull on airside, directional only (:16; memory `airside-is-king`).
- Feasibility is guaranteed; quarantine unauthorized, full census (:19-24, escalated 08-01); "no lawful-infeasible ground", DEM is a seed (:353-370).
- Constant-DEM invariant: DEM≡0 / 10,000 m must emit zero violations, seats at floor/ceiling (:378-410).
- CIFP thresholds absolute for v1 (:511-516); runway may flex between pins within grade law only, no displacement budget (:267-282, :587-603). "H7" not found as a label anywhere.
- Groundside terrace law (:25-27) as AMENDED 08-07: walls only at tunnel/bridge carves, everything else feathers (:887-917).
- Free-road ruling (:28-30, `groundside.free_road_subsegments`); roads laterally flat (:1798); truck route through apron = spine at apron cap (:1816); road profile 8 % lift/cut, core owns general roads (:1963-1967).
- Anchor placement: no hard anchors mid-taxiway (:34-37).
- Adjacent-ground zones 1–2 graded, beyond raw DEM; enclosed pockets fill + drainage spine (:38-40; memory `adjacent-ground-zone-law`).
- Fabric model: only pavement, pads, reg-set strips/drainage/RESA shaped; unregulated ground nothing (:1164-1192).
- Apron = taut membrane on centerline scaffold, never DEM drape, no plateaus; DEM last priority, straight planes between anchors (:1689-1696); strict chord = vertex→nearest visible anchor (:1672, :1695); strip area never apron population (:1672); apron hard gates (:1440-1459).
- No steps in airside pavement: grade + rate-of-change (:1861-1863); no terrace joints across any road (:783-791).
- Building pads: welded to apron, seat is the weld (:1106-1120); NO footprint outside the pad, weld to touching pavement, mixed pads weld airside and cut back groundside by 0.6 m (09-01g/i :2020, :2023); tiny pads fold (:1687); pad in basin sits at floor (:1771).
- Tunnel: canonical mouth (:1897); mapped bores preserved/roofed, 0.6 m cut clearance, ramp wins over pavement but never cuts runway family (:967-998); ramp walls its own cut, never crosses a pad (:1057-1082); foot retired, 0.6 m gap, one corridor-top value (:2010-2016); crest = DEM all round, mouth wall 5.1 m above mouth (`BRIDGE_ROAD_CLEARANCE_M` config:5568) (:2062-2066).
- Bridge decks: mapped road bridge over emitted below-grade = deck, not cuttable (:1908); no object ⇒ terrain deck at road level cutting the ramp (:1920); deck needs 5.1 m, ramp climbs beyond (:1931). Object seating datum = deck top (memory `othh-bridge-deck-datum-r12`); grade law outranks shared-datum groups (:1868).
- Creation-order seniority (:1675); contact is canonical identity, never proximity (:1708; memory `canonical-identity-join` 11-dp).
- HECA is not flat, 85 m real (:73); scenery signature apt.dat + DSF only (:75, `driver.py:401`).
- Strings = smoothing refinement only (:45-50), string back door retired (:221-243).
- Cut-piece floor: accept the drape (:51-53); seam-tear wall-straddle exemption (memory, `_check_strip_seam_tears` :4357).
- Zero-airside beta bar; runways never pulled past cap (:2029-2033).

## 4. Inputs

apt.dat `src/auto_patch/apt_dat_reader.py:106-121` row constants; dispatch `:531-610` — 100 runway (`_parse_runway` :960), 110 pavement (:1092), 120 painted lines (:1195), 130 boundary (:1160), 1201/1202 taxi network (:1025/:1046), 1206 truck edges (:1069), 1300 startups (:603). 102 helipad is defined (:108) but I found no parse branch. CIFP `cifp_reader.parse_cifp_file` :84 (threshold elev ft, displaced distance). OSM: `osm_load._load_osm_airports` :224, `_load_osm_small_roads` :691, `_load_osm_big_roads` :671 (bridge/tunnel/layer tags retained :976-977), buildings `osm_aeroway.extract_building_info` :88. DEM: `elevation._load_airport_dem` :241 (`override_dem` = Ortho4XP's smoothed tile DEM). DSF: `dsf_reader.read_dsf_pavements` :701, `read_dsf_buildings` :1060, `read_dsf_object_buildings` :1450; OBJ8 hardness `obj8_reader.load_object_file` :283 (`ATTR_hard_deck` :322).

## 5. Output the mesh reads

Emitter `layout.to_osm` :1099; way tags :3063-3077 (`aeroway`, `role`, `shapeID`, `ref`), `altitude` :3179, `node_altitudes` :3253, per-node `alt_abs` :3016; sidecar `_write_axes_sidecar` :3709 (keys :3755-4220).
Mesh reader `src/O4_Vector_Map.py:2639-2826` reads ONLY: way `cst_alt_abs`/`cst_alt_rel`/`var_alt_rel`/`altitude`/`node_altitudes`/`altitude_high|low`(+`cell_size`,`profile`,`steepness`) and node `alt_abs`/`alt_rel` (:2783-2788, which override way values); `role` only for `GRADED_COVERAGE_ROLES` seawall/flood admission :148-150, :2798. `ref`, `shapeID`, `aeroway` are NOT read by the mesh. Sidecar: mesh reads only `road_bridge_decks` (:1446-1479); everything else is instrument-only. Rings become constrained edges via `insert_way` :2804 with `PATCH_RING_MARKER` :97; open ways `DUMMY` :2824.
Apply cost: every ring edge is a Triangle constraint (`-pq<min_angle>` `O4_Mesh_Utils.py:1193-1195`, Steiner cap :1189); `O4_Vector_Utils.insert_edge` :187 splits at every crossing; near-parallel sub-cm edges mint needles (memory `session-20260828`: HECA p99 aspect 43,275 vs 23, 62k needles, "station-on-edge 2 cm parallel constraints"). Chord density: two 60 m decimators (`emit_decimate.MAX_CHORD_M` :199, `PAVEMENT_NODE_MAX_CHORD_M` layout:145; memory `two-decimators-mask-each-other`). T-vertex weld class: `docs/chain_identity_one_solve_plan.md:102,181`.

## 6. Mechanism, not law (do not carry)

| v1 mechanism | retired by |
|---|---|
| R5 transition law on crests / `TRANSITION_ROLES` walls | 09-03b :2066 (deleted) |
| Wall foot, outline close (`BUILDING_OUTLINE_FILL_R`) | 09-01c :2012, 09-01g :2020 |
| Break quarantine, `break_nodes` sidecar | 08-01 :19-24, layout:3788 |
| String back door / `O4_CORRIDOR_REF_STRING`, string-bend | :221-243, :1629 |
| Runway flex displacement budget | :587-603 |
| Fan zones, relief generation | :1164-1192 |
| Retaining walls outside carves | :887-917 |
| Pad-request next-build convergence | :1600 |
| Drainage minimum on taxi/apron | :1604-1606 |
| `free_road_profile`, `tunnel_road` claim | :1967 |
| Seat coupler `SEAT_COUPLE_SHARED_SURFACE` | HELD (memory `seat-flip-verdict`) |
| Gap-spine bridge over-budget | stands down :1865 |
| Band inversion / writeback band, crown-frame double lift | memories `heaz-band-inversion-attributed`, `r8-writeback-band-crown-frame` |
| Emit consensus averaging | precedence :424-442 |
| Last-writer ordering, pad-edge weld radius | :1982, :2018 |

## Not found / unverified

- Memory `chain-divergence-audit`: no such file in the memory dir; nearest is `docs/chain_identity_one_solve_plan.md`.
- "H7" runway-profile label: absent from RULINGS/STATUS top block; substance cited via 08-04/08-05.
- The 0.6 m `wall_gap_m` constant: ruling text only (:2016); no named constant located in `config.py`/`bridges.py`.
- 102 helipad parse branch; "08-08 apron relief" as a distinct ruling (only fabric model :1164 and memory `heca-is-not-flat`).
