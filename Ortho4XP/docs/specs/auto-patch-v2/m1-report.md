# auto-patch-v2 — M1 report: `airport/` + `classify/` + `planar/`, the planar map for CYXY

Lane `v2m1` (Fable, owner 2026-09-03h), branch `lane/v2m1` off main
`01fa48cb`. Package `Ortho4XP/src/auto_patch_v2/{airport,classify,planar}`
against the frozen M0 `model` / `law` (M0 §3). Nothing imports v1; every
file ≤ 1,000 lines; no environment reads; every threshold that exists
lives in `classify/rules.toml` (03e), every law value in `law/*.toml`.

## 1. CYXY, the numbers (`python -m auto_patch_v2.planar CYXY --out DIR`)

Inputs resolved exactly as v1's 09-02 arm resolved them — the `CYXY
Whitehorse` **custom pack** (its apt.dat AND its DSF's 44 draped `.pol`
pavement pages, 136 k m²), NOT the Global Airports block the M0 brief
named (the arm's patch header says `o4_apt_dat=…/Custom Scenery/CYXY
Whitehorse/…`; the Global block has 27 pavements, the pack 31 — see §5 Q1).

| | v2 M1 | v1 09-02 arm |
|---|---|---|
| faces | **268** (pavement 116, pads 10, roads 10, graded strips 144 — zone 1/zone 2 per class) | 385 shapes + 95 feature ways |
| edges (each once, both faces named) | **4,635** | — (T-vertex/weld class: 33 coordinate twins, 6 weld residues) |
| vertices (11-dp identity, DEM sample on every one) | **4,352** (target ≤ 6,660) | 6,660 nodes |
| breaklines | **61** (runway_profile 10 chains over 3 runways at 12 m stations, taxi_centerline 45, road_centerline 6) | — |
| T-vertices | **0** (STRtree check of every vertex against non-incident edges, beside I5) | — |
| min distinct-vertex spacing | **0.50 m** (every vertex on the 0.5 m identity grid, `emit.identity.min_distinct_spacing_m`) | 116 chords < 1 m |
| max chord | 60.0 m (`chords.pavement_max_chord_m`; apron rings 50 m) | 59 chords > 60 m |
| dropped polygonised faces | 48 (holes beyond zone 2 and sub-0.5 m² slivers — the DEM owns them) | — |
| wall time (CLI, single run) | **1.13 s** = load 0.67 + classify 0.13 + planar 0.32 + write 0.01 (target < 5 s) | 41.5 s build |

Area by role (m²): runway 206,896 · runway_crossing 2,124 · primary_parallel
156,390 · secondary_parallel 5,195 · stub 38,061 · cross_connector 19,757 ·
junction 77,685 · apron 138,773 · service_junction 51,545 · service_road
2,670 · groundside_pavement 73,760 · building 12,008 · graded_strip 921,885.

Loader report: pack `CYXY Whitehorse`, apt.dat block sha `a8223e1b…`, DSF
`+60-136.dsf` sha `ba2a1655…`; 6 helipads reported (102, not graded); CIFP
thresholds joined on all 6 ends (0 missing); OSM 1,532 ways (3 feeds);
buildings: 4 OSM + 90 DSF facade pieces + 2 cached OBJ8 footprints → 10
pads ≥ 250 m² inside the boundary (61 folded); 591 OBJ8 placements, all
`lib/` paths (hardness unresolved — M1 does not read the library index);
DEM = `N60W136.hgt` + `CYXY_hrdem.tif` (HRDEM 1 m, CGVD2013) feathered over
60 m.

Twins: `tests/auto_patch_v2/` — 65 pass in 2.6 s (`-n0`), fixtures 198,768
bytes (the pack's CYXY block, its CIFP RWY records, the three OSM feeds
cropped to 0.015–0.025°, the DSF dump cropped to pavement/facade polygons
+ 30 placements, the cached footprints, a 61×61 synthetic `.hgt` and a
48×48 synthetic inset GeoTIFF).

## 2. Role agreement with v1 (M1 bar: ≥ 95 % of pavement area) — **NOT MET**

Measured by `tests/auto_patch_v2/test_role_agreement.py` (v1 = the `role`
tags of the 09-02 arm's patch, ledger tag `CYXY_20260901T235159`; every v2
pavement cell intersected with the v1 rings):

| | |
|---|---|
| pavement population compared | 772,538 m² (v1 covers 99.1 % of it) |
| **exact role agreement** | **48.1 %** |
| **law-family agreement** (taxi sub-roles ≡ junction: same taxi cap tables; `plane_gradient` is the one family that differs) | **71.4 %** |

Every disagreeing pair, with the reason (the twin refuses a pair without one):

| v2 role | v1 role | m² | reason |
|---|---|---|---|
| primary_parallel / stub / cross_connector / secondary_parallel | junction | 179,602 | v1 emits every slice face as `junction`; v2 names corridors by geometry against the runways (same taxi-family caps) |
| junction | apron | 45,833 | the route-proximity band (user 2026-07-06, "< 50 m from a centreline or runway is NOT apron") — v1 cut it too, then `junction_repair` re-roled interior faces back to apron |
| service_junction | groundside_pavement | 41,445 | DSF page `dsf:pol117` (a lot) touched only by a FREE ground-route part → service territory (user 2026-07-02); v1's road carve severed it from the runway chain and demoted it |
| apron | groundside_pavement | 32,460 | runway touch-chain (user 2026-06-09): v1's service-road CARVE severed these lots; v2 keeps a road inside wide pavement uncut (free-road ruling 2026-07-27, width-only term) so the chain reaches the runway |
| stub / primary_parallel / cross_connector | apron | 36,387 | Apron 1's lane network: v2 cuts the apron by every through lane and the halves read as corridors (width ≤ 50 m); v1's `junction_repair` re-roled them apron |
| groundside_pavement | apron / junction / service_junction | 26,053 | the reverse touch-chain case: v2 severs at DSF-page / pad boundaries where v1 chained through |
| apron / service_junction | service_road / service_junction | 18,433 | v1 carries the OSM road feed (`groundside` service corridors/junctions inside pavement); M1 carries the 1206 routes only — roads are M3 |
| groundside / apron / junction / cross_connector | building | 8,000 | v1 pads v2 folded (< 250 m², `structures.building_pad.min_area_m2`) or outside the boundary + 50 m gate |
| runway | runway_crossing | 2,888 | v1's crossing rings extend past the slab overlap (junction-snap stations) |
| apron | junction | 1,679 | pavement with no route at all (`pav28` remainder, `pav29`): v1 junction via gap-spine synthesis; v2 apron per the proximity ruling |

What closed on the way (measured, kept as rules): DSF `.pol` pavement pages
(136 k m² v1 grades that apt.dat lacks — the first run agreed 41 %, mostly
"uncovered"); ramp lead-in trim (user 2026-07-04); through-route proximity
(user 2026-07-06/26); free-road scoping (2026-07-27, width-only); OSM
`aeroway=taxiway` centrelines where the 1202 network is silent (the 2 km
`pav28` strip had no route at all); runway slabs include blast pads.

What would close the rest and was deliberately NOT carried: `junction_repair`'s
apron re-role and the road-carve severing are v1 post-solve/geometry-final
REPAIR passes (plan §1 "What v2 deliberately does not have"); the road-feed
service centrelines and the R7a landside-evidence term are M3 (roads,
groundside). The residual is therefore a **ruling question, not a defect
fix**: which classification the owner wants for (a) apron lanes (corridor
vs apron), (b) lots reached only through a road (free-road width vs carve),
(c) the taxi sub-role register vs v1's flat `junction` — §5 Q2–Q4.

## 3. What v1 does that M1 deliberately does not carry

| v1 | not carried because |
|---|---|
| runway ring 3 m width margin (`_LEGACY_RUNWAY_MARGIN_M`) | legacy mechanism; the slab is the apt.dat width |
| production DEM prep (grid densification, overlay bake, `smooth_raster_over_airports`) | M0 §4: "`DemSample` over the .hgt with the inset applied (bilinear)"; the core's inset machinery stays core-side (plan §1) — §5 Q5 |
| painted-line (120) centrelines when a 1202 network exists | v1 parity (fallback only); strings are a smoothing refinement, never authority (RULINGS :45-50) |
| gap-spine synthesis, apron lattice, drainage spines, interior rings, crown spines | mechanisms (Appendix A §6); M2 constraints, not geometry |
| `.agp` hangar footprints, OBJ8 library-path hardness (library.txt resolution) | needs the X-Plane library index; reported as unresolved (591 at CYXY, none hard) |
| OLS cuts, runway end skirts / RESA, retaining walls, tunnels/bridges | M2/M4 constraint generators over the same map |
| SURFACE-attribute tier of DSF pavement acceptance | needs the resolved `.pol`; name tier only |
| junction_repair, apron→junction re-roles, road carve, single-authority arbitration | post-solve writers — gone by design |

## 4. M2 constraint-generator brief skeleton (Appendix A §1 → generators)

| generator (`constraints/`) | families (Appendix A §1) | rows over the map |
|---|---|---|
| `runway_profile.py` | within_shape (runway family), runway_crown, drainage_minimum, raoa | `Pin` at the station nearest each CIFP threshold (absolute, RULINGS :511); `Diff` along each `runway_profile` breakline at `rulesets.runway.longitudinal` by code number, end zones at `end_zone`; crown as `Offset` centreline vs slab edge (`common.runway_crown_transverse`) |
| `taxi.py` | within_shape (taxi family), transverse, plane_gradient (junction), airside_no_step | `Diff` along `taxi_centerline` breaklines (longitudinal by letter) and across every face edge of the taxi family (transverse); no-step window/K over airside vertices |
| `apron.py` | within_shape (apron), apron_lattice_membrane, drainage_spine, terrace_* | `Diff` on every apron face edge at `common.roles.apron`; interior lattice ≤ 50 m is an OPEN question (M0 Q3): the map has no interior vertices — either lattice vertices join the arrangement or the membrane is a face-plane constraint |
| `pads.py` | frontage_near_miss, airside_no_step (pad↔pavement), steps | **pads YIELD (03h)**: each `building` face is a `Flat` group; its value is a `Diff(0 cap)` to the touching pavement vertices (contact = canonical identity, weld to touching pavement 09-01g), never a `Pin` the apron climbs to; mixed pads cut back 0.6 m groundside (09-01i) |
| `zones.py` | adjacent_ground_tear, strip_seam_tear, strip_longitudinal, strip_arc, resa_transverse | `Band` per `graded_strip` vertex from `zone_bounds(law, role, d, code)` relative to its pavement-edge vertex (zone 1 lip, zone 2 band); zone 3 = DEM (`Pin` to `dem_z` on the outer ring) |
| `roads.py` (M3) | road_cross_section, lateral_contiguity | `Diff` along `road_centerline` at `common.roles.service_road`, across the corridor at `transverse`; contiguity to touching apron |
| `structures.py` (M4) | basin_floor_declaration, wall_in_runway_strip | tunnel mouth/ramp/crest, decks, basins from `structures.toml` |
| `seams.py` | stacked_nodes, cross_shape, steps | none needed: one vertex per coordinate BY CONSTRUCTION (I1); tile-seam pins to the neighbour's values |

Solver weights (plan §2): airside faces high, groundside 1, zone-3 ring
pinned to DEM; objective L1 to `dem_z` + roughness along breaklines.

## 5. Open questions for the owner (≤ 5)

1. **Which apt.dat is CYXY's?** The M0 brief names Global Airports; the 09-02 arm (and hence every v1 number) is the `CYXY Whitehorse` custom pack. M1 follows v1's pack precedence (custom pack with pavement wins) so the agreement compares like with like; the Global block would change the pavement population (27 vs 31 polygons, no DSF pages).
2. **The 95 % bar vs v1 repair passes.** The residual (§2) is in three v1 mechanisms v2 does not have: `junction_repair`'s apron re-role of lane-cut faces, the road carve that severs lots, and the flat `junction` register. Ruling needed: is v1's classification the truth to match (then those three become rules in `rules.toml`), or is the rulings-derived one (proximity, free-road width, connectivity through touching pavement) the truth and the bar re-based on it?
3. **Apron lanes.** A stand lane network cut through Apron 1 makes the halves "corridors" (area / shared edge ≤ 50 m) — taxi law at 1.5 % on what is stand apron. Should the corridor test require an authored taxiway NAME/letter (1202 `taxiway_X`) and treat unnamed lanes as apron cuts only?
4. **Lots reached only through a road.** Free-road ruling (2026-07-27) says a road inside wide pavement is the apron; R7a added a landside term (parking aisles) v1 uses to carve. M1 has the width term only, so DSF-page car parks chain to the runway as apron. Ruling: is "pavement outside the runway-touch chain OR under OSM parking" the landside evidence M3 should carry?
5. **DEM frame.** v2 samples the authored `.hgt` + inset (feathered 60 m); v1 grades against Ortho4XP's densified, overlay-baked, airport-smoothed tile DEM. For M2's census parity the mesh sees the smoothed one — should v2 sample the composed tile DEM through a core-side accessor (kept read-only) instead?

## 6. Files (lines)

`src/auto_patch_v2/airport/`: `apt_dat.py` 627, `cifp.py` 101, `osm.py`
119, `dem.py` 281, `dsf.py` 287, `pack.py` 73, `load.py` 350, `__init__.py`
12. `classify/`: `rules.toml` 66, `rules.py` 183, `evidence.py` 354,
`roles.py` 485, `__init__.py` 11. `planar/`: `chords.py` 53, `zones.py` 93,
`overlay.py` 140, `build.py` 253, `index.py` 121, `__main__.py` 125,
`__init__.py` 12. Tests: `test_airport_load.py` 256, `test_classify.py`
186, `test_planar.py` 167, `test_role_agreement.py` 171; `test_model.py`
dependency twin extended to the producers. `tools/INDEX.md`: one entry.
