# auto-patch-v2 — M3b report: SPJC lawful on every class except the pad↔pavement class (waits on 03k)

Lane `v2m3b` (Fable, owner 2026-09-03h), branch `lane/v2m3b` off main
`a46e4651`. Every file ≤ 1,000 lines (largest `law/model.py` 807); no
environment reads; every law value from the TOML tables (two new keys in
`structures.toml [building_pad]`, one new section `emit.toml
[lateral_contiguity]`, §5); nothing imports v1. Commits in §9, on the
branch, not merged.

Build: `cd Ortho4XP && PYTHONPATH=src venv/bin/python -m auto_patch_v2 build SPJC --out DIR`
(production DEM frame S13W078, guard armed, read-only).

## 0. Attribution first: 128 of 135 SPJC pads were never in the map

The M3a code loaded 135 building footprints at SPJC (7 OSM, 96 DSF
facades, 32 cached OBJ8) and classified **7** pads. The DSF text-dump
reader took a facade winding's control point from columns 2–3, but a
facade point at `cpp = 5` is `lon lat wall ctrl_lon ctrl_lat`: one
`Cargo_Terminal.fac` winding (`BEGIN_POLYGON 74 6 5`) read `wall = 4.0`
as a longitude, flattened to a polygon 707,000 km² wide, and
`unary_union` swallowed every other footprint into it (14 parts, one of
area 7.07 × 10¹¹ m²). Fixed in `airport/dsf.py::_flatten` (control point
= the last two columns when `cpp ≥ 4`; twin
`test_dsf_facade_control_point_is_the_last_two_columns`). SPJC now
classifies **53 pads** (66 footprints ≥ 250 m² union to 53; v1 emitted
71 `building` + 17 `object_pad`). Every number below is after the fix.

## 1. SPJC end to end (single run; `SPJC.report.json`)

| stage | wall | product |
|---|---|---|
| load | 3.58 s (2.4 s = the tile compose, 11,017² grid) | pack `SPJC Lima by Los Flipantes 3.0`, 2 runways, 147 pavements (96 DSF `.pol` pages), 135 footprints |
| classify + planar | 0.41 + 0.70 s | 407 faces, 9,495 edges, 9,128 vertices, 183 breaklines, **0 T-vertices**; faces by role: runway 4, taxi family 97, apron 20, building 53, service 28, groundside_pavement 13 (6 before the cut-backs split them), graded_strip 192 |
| constraints | 1.12 s | 403,558 rows: taxi 229,805 + 917 + 128, apron 96,484, no_step 50,618 + 7,865, road 8,730, zones 2,373, transverse 1,603, runway 608 + 430 + 1,642, strips 211 + 471 + 18 + 1, pad_flats 53, **frontage_near_miss 34**, raoa 0, seam 0 |
| solve | 6.02 s | HiGHS LP **824,216 ≤-rows + 1,560 =-rows over 20,105 columns** (9,128 z + DEM slacks + roughness + 432 preference groups), 1.68 M nnz, OPTIMAL; residual pin/diff/flat/band/offset 0 |
| emit | 0.32 s | 474 ways, 9,128 nodes, patch 1.77 MB, sidecar 5.9 MB (v1: 2.75 / 24.1 MB, 14,495 nodes); `station_caps` 486 published |
| verify | 0.86 s | 1 row (§3) |
| **total** | **13.0 s** (bar < 30 s; v1 166.2 s) | |

## 2. Census by family — v1 oracle vs v2 verify (whole airport, production frame)

| family | v1's own patch (09-02) | v2 as landed from main (7 pads) | v2 + DSF fix, before M3b law | **v2 M3b** oracle | v2 verify |
|---|---|---|---|---|---|
| airside_no_step apron\|building + building\|junction (**the pad class**) | 344 | 0 (vacuous: no pad pairs published) | 0 (same) | 0 (same — see §4) | 0 |
| airside_no_step, other | 87 | 0 | 0 | 0 | 0 |
| strip_arc | 57 | 0 | 0 | 0 | 0 |
| drainage_spine | 37 | 0 (vacuous, §6) | 0 | 0 | — |
| transverse | 54 | 0 | 0 | 0 | 0 |
| road_cross_section | 33 | 0 | 0 | 0 | 0 |
| within_shape | 22 | 0 | 0 | 0 | 0 |
| apron_lattice_membrane | 14 | 0 (vacuous, §6) | 0 | 0 | — |
| frontage_near_miss | — | 0 | **15** (airside) | **0** | 0 |
| vertex_to_edge_step / mid_edge_step | 1 | 0 | 5 + 13 (4 airside pad↔apron, 14 groundside lot↔lot) | **0** | 0 |
| cross_shape | 0 | 0 | 1 (airside) | **0** | 0 |
| lateral_contiguity | (gs) | 46 (gs) | 46 (gs) | **0** | 0 |
| plane_gradient | — | 1 (gs) | 1 (gs) | 1 (gs, §3) | 1 |
| **total / airside adjudicated** | **686 / 596** | 47 / 0 | 81 / 20 | **1 / 0** | 1 |

Every other family reads 0 on every column. Verdict line: `ADJUDICATED 1
airside=0 groundside=1`. The oracle and v2's verify agree row for row.

**What closed the 81 → 1.** (a) *Mixed pads* (09-01g/i): a terminal
pad at 24.55 m (its airside contact) shared vertices with the groundside
DSF page `dsf:pol200` and dragged it 4.8 m below the DEM (29.4 m) while
the neighbouring page `dsf:pol38` followed the DEM — 14 groundside step
rows at one site. `classify/roles.py::_cut_back_groundside` now cuts
every groundside value cell back `groundside_cutback_m` = 0.6 m from a
pad that touches both sides; the terrace in the stand-off is the lawful
airside/groundside boundary (the step readers skip airside↔groundside
pairs). SPJC: 7 cells cut. (b) *Near-miss frontage* (08-08, Appendix A
`frontage_near_miss`): 15 rows at pads 0.5–0.7 m off their apron (the
v1 SPJC building29 class — a DSF facade against an apt.dat apron); no
identity join closes a 0.7 m sliver, so the pad was DEM-levelled beside
an apron at its own value (steps 0.5–1.1 m). `constraints/pads.py::
frontage_near_miss` mirrors the oracle's reader exactly (both endpoints
unshared with the pad, each endpoint unshared with any pad, `|z_e −
z_pad(nearest)| ≤ apron cap · d_e`): 34 rows at SPJC, and under 03h they
level the pad by its frontage as a shared vertex would. (c) *Lateral
contiguity per station* (08-02 clause 2, 08-28 Amendment 2): M2 read
contiguity at shared edges; the census walks stations 5 m apart along
the road's long axis with a 60 m perpendicular probe and takes the
strictest class in the touching run — a road across a junction from an
apron, or beside a pad, is 1 % at those stations. `constraints/
contiguity.py` is that walk (constants from the new table section, the
strip keep-out from `strips.runway_groups`); a road face is bound at its
strictest station cap, the way carries it as `o4_grade_law_cap`, and the
vector is published as sidecar `station_caps` `[lat, lon, cap]` (the
fourth reader). SPJC: 486 stations. `verify/contiguity.py` prices the
published cap against its OWN re-walk (stricter than the oracle, which
trusts a published cap), `verify/frontage.py` is the near-miss twin;
both registered in `verify/census.py` (`NOT_IMPLEMENTED` shrinks by two).

## 3. Residual (attempt cap: two iterations per family; none spent)

* **plane_gradient 1, groundside** (`service_road route0`, −12.02485,
  −77.11583): a 3-vertex sliver face with a 0.5 m edge (the identity
  spacing) beside two 11 m edges. Its solved plane is 0.82 % (the 16
  triangle rows sit at ≤ 0.81 % of a 1.47 % bound); the EMITTED plane is
  2.96 % because the 0.01 m elevation quantum on a 0.5 m edge is a 2 %
  grade by itself. Not a surface defect: an emit-quantisation artefact
  of a construction sliver. The fixes are either a dissolve of
  3-vertex faces whose shortest edge is the identity spacing (planar
  build) or a finer quantum (`emit.materiality.elevation_m` is a table
  value — the convergence-guard floor — not this lane's to change).
  Open question 3.

## 4. THE PAD CLASS under the current rule (03h/03i), and the 03k decision input

**Rows the oracle reads: 0.** v2's tables exclude rigid roles from the
no-step publication ("never a no-step pair endpoint of its own"), so
the oracle — which prices exactly the published list — cannot see a pad
↔ pavement pair. That zero is vacuous. **Priced offline the way v1
priced it** (every pad vertex against every airside pavement vertex
within the 150 m window at the apron cap + 0.03 m, all pairs, no K
limit) the CURRENT solution carries **3,858 over-cap pairs**: apron
2,228, junction 1,566, primary_parallel 34, stub 30; worst building9,
8.5 m over 147 m (v1 read 344 with K = 16 per node; the population is
the same class). Why: SPJC's pads are flat groups across REAL relief —
DEM relief across a pad p50 0.86 m, p90 4.24 m, max 8.70 m (36 of 53
pads over 0.5 m, 20 over 1.0 m); 21 pads are welded (levelled by an
airside contact), 32 detached (DEM-levelled, max 4.85 m off their DEM
mean). The apron itself sits p50 0.61 m / p90 2.45 m / max 7.82 m off
the DEM; the taxi family p50 0.04 m / max 3.26 m.

**Measured, not implemented — the IIS question.** A scratch arm added
the pad↔pavement no-step pairs v2 does not publish (5,350 pairs under
v2's own K/sector rule) to the shipped constraint set and solved:
**OPTIMAL in 6.6 s — no IIS.** At SPJC the pad class contradicts NO
governed surface; it is closed by the ungoverned side moving. Versus the
shipped solve: 20 of 53 pads re-level by > 0.5 m (building9 8.16 m,
building10 3.46 m, building15 2.95 m); the apron moves at 358 vertices
> 0.5 m (max 2.44 m, p90 0.56 m), junctions 281 (max 0.88 m), stubs 30
(max 0.66 m), primary parallels 2 (max 0.56 m), the runways 0 (max 0.17
m). So the three 03k options at SPJC: **(a) declare a terrace** — 36
pads span > 0.5 m of relief, so up to 36 declared joints (each a
`terrace_joints` row the census already reads; 08-06 forbids joints
across roads and 08-24 plateaus — 7 of the 36 pads front a service
road); the airside pavement would not move; **(b) taxiways yield
locally to the apron membrane** — the measured arm IS this option's
magnitude: the pad class closes with taxi-family movement ≤ 0.88 m at
313 vertices and apron movement ≤ 2.44 m, every row within its own cap
(the solve is feasible), runways untouched; **(c) accept** — 3,858
all-pairs / ~344 K-limited rows stay true geometry excluded from the
bar. SPJC is gentle (memory `spjc-is-gentle`): HECA's R1.3 sites, where
two governed constants straddle 4–10 m, are where (b) can become an IIS;
here it does not. Nothing in v2's pad generators changed for this.

## 5. Law tables and model extended (03e; additive, every value = v1's — the law twin checks each)

`structures.toml [building_pad]`: `frontage_near_miss_m` = 1.0
(`BUILDING_FRONTAGE_NEAR_MISS_M`), `frontage_soft_roles` = apron,
junction (`NEAR_MISS_FRONTAGE_SOFT_ROLES`). `emit.toml
[lateral_contiguity]`: `station_step_m` 5, `probe_m` 60, `gap_tol_m`
0.05, `min_member_m` 0.5 (`auto_patch/lateral_contiguity.py`). Schema:
`BuildingPad` + 2 fields, `LateralContiguity`, `EmitLaw.lateral_
contiguity`. `SIDECAR_KEYS += station_caps`. `road_law_caps(planar, law,
airport)`, `face_tags(planar, law, airport)` gained the airport (the
strip keep-out); `Classification.stats["mixed_pad_cutbacks"]`.

## 6. What SPJC did NOT need, and why (brief item 1)

* **Drainage spines / pockets**: the oracle's `drainage_spine` reads v1's
  `gap_drainage_spine` feature ways; v2 emits none and the pocket rule
  (M2, `zones.py`) already fills a pocket toward its nearest pavement's
  band. 0 rows, vacuous. A face-plane row for a filled pocket needs a
  pocket vertex population v2's map does not carry (M0 Q3) — not built.
* **Apron lattice / membrane**: `apron_lattice_membrane` reads v1's
  published `apron_lattice_edges`; v2 has no interior vertices (M0 Q3).
  0 rows, vacuous. Binding a membrane without carriers would constrain
  nothing the mesh reads (the mesh harmonic-extends ring values into the
  interior — `O4_Mesh_Utils.post_process_nodes_altitudes`); a constraint
  family needs carriers or a face-plane statement — open question 4.
* **OLS cuts (v1 16 `ols_cut` ways), runway-end skirts (8), object pads
  (17)**: the register has no OLS family (`verification.check_ols_
  surfaces` is an instrument outside it, Appendix A §1);
  `runway_end_skirt` / `resa_transverse` read `runway_clearance` rings
  and v2 states the skirt and RESA laws on the end-corridor
  `graded_strip` ground instead (M3a, `strips.py`: 18 + 1 rows here,
  0 census rows); `basin_floor_declaration` reads `basin_facilities`
  (empty). OBJ8 footprints are pads in v2 (32 loaded, the ≥ 250 m² ones
  among the 53). None of the three is a census requirement; whether the
  owner wants OLS cuts and skirt rings as TERRAIN products of v2 (zone 3
  is the DEM by 08-01) is open question 5.

## 7. Tunnels at SPJC — a real mapped bore, not a v1 artefact

OSM `-13-078_big_roads`: ways **−2525 and −641**, `highway=trunk`,
`tunnel=yes`, 2 lanes each, 1,264 / 1,259 m — the two carriageways of Av.
Elmer Faucett under the west runway. Against v2's map: **141 m under
pavement** (16R/34L over 37 m at solved 7.4–8.3 m, the primary parallel
over ~65 m) **and 396 m under graded strips**; the DEM along the bore is
flat, 6.5–7.9 m. Ends: north −12.00874/−77.12730 and south
−12.01997/−77.12940 (328 / 191 m from pavement, 309 / 116 m from the
strips) — exactly v1's two `tunnel_ramp` + `tunnel_wall` sites
(−12.0081/−77.1271 and −12.0206/−77.1293). v1's sidecar `tunnel_vetoes`
names OTHER ways (−451 secondary "no_cover_no_cut"; −3153/−3154
motorway "adjacent_road_veto"), so Appendix B's "the 08-16 log vetoed
both" was those, and the Faucett bore was admitted. **Verdict: mapped
tunnel, generate.** NOT generated here: ramp / wall faces are a NEW
SHAPE CLASS in the layout (`tunnel_ramp` cells, `retaining_wall` rings,
a bore corridor under the strips) and RULINGS 2026-08-30l requires the
consumer census in one table at spec time before any consumer is edited
— that table is §10 (the M4 brief). The mouths lie 116–309 m outside the
strips: the ramp descends from the DEM (7.6 m) at 4 % to the mouth datum
(bore ceiling 5.1 m under the covering surface at ~7.4 m → mouth floor
≈ 2.3 m, some 130 m of ramp) entirely on ground v2 does not model
today, and the covered 537 m stays roofed under the runway/strip surface
(no cut).

## 8. The mesh bar (`tools/run_tile_mesh_only.py -13 -78 --patches-as-is`, 3 runs per arm, foreground, medians; the same data-repo SPLP −13-078 piece on both arms, only SPJC differs)

| arm | input segments | constrained edges | triangles | step 1 median | step 2 median |
|---|---|---|---|---|---|
| v1 (data-repo 08-30 SPJC cut) | 129,025 | 149,413 | 358,546 | 16.76 s (16.66 / 16.76 / 16.81) | 6.83 s (6.73 / 6.83 / 6.92) |
| **v2 M3b** | **123,724** | **133,351** (−16,062) | **327,898** | 16.36 s (16.21 / 16.36 / 16.36) | 6.81 s (6.80 / 6.81 / 6.82) |

Fewer constrained edges (−10.7 %), fewer triangles (−8.5 %), both steps
no slower. Both arms: `[guard] shared repo UNCHANGED by this build`.

## 9. Twins and commits

`tests/auto_patch_v2/`: **84 pass** (78 + `test_m3b.py` 5: the cut-back,
the near-miss generator, the station walk + way tag, a solve → publish →
verify round trip reading 0 on both new families with the near-miss pad
at its frontage level, and the verify reader flagging a published cap
looser than its own walk; + the DSF cpp-5 twin); the law twin now checks
the six new constants against v1. Commits on `lane/v2m3b`: `905bffa9`
(the fixes, tables, twins) · this report.

Scratch (not promoted; second-use candidates for a v2 `solve_cut`
equivalent): `probe_state.py` (pickles airport + map + constraints +
solution once), `probe_site.py` / `probe_ll.py` (a site's vertices, z,
DEM, faces), `probe_padclass.py`, `probe_iis.py`, `probe_tunnel.py`,
`mesh_arm.sh`.

## 10. M4 brief skeleton — structures (OTHH tunnels, LEMD basins / decks) with the tunnel consumer census (08-30l)

| item | what M3b leaves | M4 |
|---|---|---|
| tunnel geometry | SPJC evidence (§7): a mapped bore = OSM `tunnel=yes` ways × airside faces; mouths = where the corridor leaves cover; ramp = mouth → DEM at `tunnel.ramp_max_grade` | `airport/osm.py` keeps `tunnel`/`layer`/`bridge`; `classify` emits `tunnel_ramp` cells (corridor width from lanes) outside cover, and a `bore` region under cover (no face, the covering surface stays); `planar` adds `retaining_wall` rings at `wall_gap_m` = 0.6 m round the ramp; generators: ramp longitudinal ≤ 4 %, mouth floor ≤ covering surface − `bore_datum_m` 5.1 (a `Linear` against the covering face's interpolation), wall crest = DEM (`Pin` on the wall ring, "crest = dem"), never cutting the runway family (`ramp_cuts_runway_family = false` → the bore stays roofed there) |
| consumer census for the new shape class (one table, before any consumer edit) | — | readers of face role/side/caps: `precedence.view` (caps: ramp = `common.roles.tunnel_ramp` 4 %, wall = none), `zones.zone_regions` (ramp/wall are never strip; the strip must not claim the ramp corridor), `no_step` (ramp is groundside → excluded), `transverse.axes` (no axis), `contiguity` (a road entering the ramp: the walk reads the ramp as a road-family neighbour? rule: ramp is its own class, cap 4 %), `apron_within_shape` (a ramp beside an apron: no shared vertices — the wall ring separates them), `strips` (a ramp inside the strip footprint: `wall_in_runway_strip = false` refuses), `verify/steps` (wall↔ground is airside↔? — the wall ring is `side = airside` in the tables; a wall↔strip step is BY DESIGN and needs the wall-straddle exemption the oracle has), `emit` (`aeroway`, `role` tags; the mesh reads only altitudes), the seam band (a mouth on a graticule line) |
| bridges / decks (OTHH) | none | `road_bridge_decks` (the ONE sidecar key the mesh reads) from OSM `bridge=yes` over an emitted below-grade; deck ≥ `bridge.clearance_m` above the ramp; `deck_datum = deck_top` for object seating |
| basins (LEMD) | none | `basin_facilities` declaration from the pack's basin objects; floor = declared; pads inside sit at the floor |
| pads over relief | 03k pending (§4 is the input) | whichever option the owner rules: (a) terrace joints published in `terrace_joints`; (b) pad↔pavement pairs enter the no-step publication (rigid roles become endpoints) — the measured arm; (c) nothing |
| scale | SPJC 13.0 s at 824 k rows | HECA ≈ 15× SPJC's vertices → the LP alone ≈ 1–2 min unless the K·N pairs and apron all-pairs (96 k rows here) are thinned: M5's own item |

## 11. Open questions (≤ 5)

1. **03k** — with §4's numbers: at SPJC option (b) is feasible and moves
   taxi-family vertices ≤ 0.88 m within their caps; which option is the
   law for v2's pad generators (and does the answer differ where (b) is
   an IIS, the HECA class)?
2. The near-miss frontage law now levels a pad by a 0.7 m sliver exactly
   as a weld does (34 rows): ratify as the reading of 03h "levelled by
   its contact", or is a source-offset pad detached?
3. The emit-quantisation sliver (§3): dissolve 3-vertex faces whose
   shortest edge is the identity spacing at planar build, or is the 1
   groundside row acceptable as PASS-with-residual?
4. Membrane and drainage spine: vacuous on v2 by construction (no
   interior carriers, no spines). Are they satisfied by the mesh's own
   harmonic interior, or does the owner want interior carriers (M0 Q3)?
5. OLS cuts / skirt rings as v2 TERRAIN products (v1 emits 16 + 8 at
   SPJC; none is a census family): in scope for v2, or does zone 3 = DEM
   (08-01) retire them?

NOT done: the tunnel generator (§7, needs the §10 table ruled); CYXY /
SPLP re-censused after the DSF fix (one airport per round — their pad
counts may change; noted in `DEFERRED_VERIFICATION.md`); a `--runs 3`
solve-time read (single-run walls only); promotion of the scratch probes.
