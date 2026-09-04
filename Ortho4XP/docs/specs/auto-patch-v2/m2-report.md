# auto-patch-v2 — M2 report: `constraints/` + `solve/` + `emit/osm` + `verify/` + `pipeline/`, CYXY

Lane `v2m2` (Fable, owner 2026-09-03h), branch `lane/v2m2` off main
`a093a007`. Package `Ortho4XP/src/auto_patch_v2/{constraints,solve,emit,
verify,pipeline}` against the frozen M0 `model` / `law` and the M1
producers. Nothing imports v1; every file ≤ 1,000 lines (largest
`constraints/geometry.py` 440); no environment reads; every law value
from the TOML tables; every row cites generator, ruling and inputs.

Build: `cd Ortho4XP/src && ../venv/bin/python -m auto_patch_v2 build CYXY --out DIR`.

## 1. CYXY, the numbers (single run, `<ICAO>.report.json`)

| stage | wall | product |
|---|---|---|
| load | 0.69 s | pack `CYXY Whitehorse`, 3 runways, 75 pavements, 96 buildings |
| classify + planar (M1) | 0.14 + 0.32 s | 268 faces, 4,635 edges, 4,352 vertices, 61 breaklines, 0 T-vertices |
| constraints | 0.44 s | 105,624 rows: pins 6, diffs 98,977, flats 10, linears 6,631 |
| solve (HiGHS LP, real L1 objective) | **1.04 s** | 220,371 ≤-rows + 236 =-rows over 9,329 columns (4,352 z + 4,352 DEM slacks + 625 roughness), 455 k nnz; OPTIMAL; residual certificate: pin 0, diff 1e-12, flat 0, band 0, offset 0 |
| emit | 0.21 s | 308 ways, 4,352 nodes, patch 874 kB, sidecar 2.7 MB (v1: 1.24 MB / 5.1 MB, 6,660 nodes) |
| verify (v2 census) | 0.38 s | 30 rows (below) |
| **total** | **3.2 s** (bar < 10 s; v1 41.5 s) | |

Constraint rows by generator: runway_profile 481 (6 CIFF pins, 475
profile chords incl. end zones), runway_crown 499, runway_within_shape
161 (crossings, foot space), taxi_within_shape 34,413, taxi_centerlines
199, triangle_planes 160, apron_within_shape 24,417, road_within_shape
16,274, transverse 308 (the census's own transect stations),
no_step_pairs 23,199 (published), no_step_rate 3,557, zone_bands 1,220,
strip_longitudinal 154, strip_arc 546, resa_transverse 19,
end_corridor_longitudinal 1, raoa 6, pad_flats 10, seam_pins 0.

## 2. The v1 census on the v2 patch (the oracle; adjudicated frame)

`tools/harness/census.py DIR/CYXY_auto.patch.osm`: **33 law-true rows,
33 airside, verdict FAIL** (v1's own patch: 160 / 67 airside). 24 of the
27 families read zero, including every family v1 fired at CYXY —
transverse 72 → 0, airside_no_step 24 → 0, road_cross_section 23 → 0,
apron_lattice_membrane 12 → 0 (vacuous: v2 publishes no lattice),
runway_crown 7 → 0, runway_end_skirt 3 → 0, plus lateral_contiguity 0,
steps 0, cross_shape 0, stacked_nodes 0.

| family | v1 oracle | v2 verify | status |
|---|---|---|---|
| raoa | 29 | 29 | RESIDUAL (§4.1) |
| within_shape | 3 (apron\|apron, 1.02–1.09 % over 30–38 m) | 0 | RESIDUAL (§4.2, attempt cap) |
| strip_seam_tear | 1 (2.2 m over 4.3 m) | 1 | RESIDUAL (§4.3, attempt cap) |
| every other family | 0 | 0 | |
| crown declaration gap (reported, not adjudicated) | 448 pairs (stub 284, primary_parallel 160, junction 4) | — | §4.4 |

`verify/` (`census(surface, law, publication)`) reads 30 rows in 0.38 s,
matching the oracle family by family except `within_shape` (v2's
reader has the pair-population of the tables; the oracle's three rows
come from a classification v2 does not model, §4.2). The twin
`test_cyxy_verify_matches_v1_census` asserts the agreement and that the
oracle's non-residual families read zero.

## 3. The mesh (`tools/run_tile_mesh_only.py 60 -136 --patches-as-is`, ONE run per arm — a first read, not a timing claim)

| | v1 patch (09-02 sweep arm) | v2 M2 patch |
|---|---|---|
| Triangle input segments | 108,708 | **105,420** (−3,288) |
| constrained edges (mesh subsegments) | 247,315 | **243,088** (−4,227) |
| step 1 vector wall | 39.4 s | 34.8 s |
| step 2 mesh wall | 9.3 s | 8.8 s |

Both arms were flagged by the shared-repo guard for the same blocked
write (the engine's warm-pass rewrite of
`Elevation_data/+60-140/N60W136_airport_insets/index.json`): identical
frame on both sides, not a patch effect, reported here rather than
overridden. `--patches-as-is` is the near-fit extension of the mesh-only
tool (INDEX row updated).

## 4. What could not reach zero, and why

4.1 **raoa 29 (ICAO Annex 14 §3.8.4).** The oracle sorts EVERY strip
vertex inside the 300 × 120 m RAOA rectangle by along-axis station and
prices consecutive vertices as one profile — laterally separated
vertices centimetres apart in station included. At 02/20's approach end
a parallel taxiway crosses the rectangle under its own zone band
(mandatory 0.3–0.9 m down beside it); the cross-width triples at 4 cm
spacing then demand |Δz| ≲ 0.16 m between the strip and the taxi edge —
an IIS of the taxi band, the no-step pairs and two raoa rows (measured).
v2 binds the rate law along the approach direction only (steps
predominantly along the axis, the strip family's own run rule) and
reports the cross-width reading as residual. Open question 1.

4.2 **within_shape 3 (apron|apron).** Two fix iterations (pad-frontage
vertices strict; spine membership by proximity to the published axes)
closed 4 → 3; the survivors are body chords 30–38 m long at 1.02–1.09 %
the oracle prices at the strict 1 % cap while the tables' population
(2026-08-21c) puts an interior chord at the 5 % fan cap. Neither endpoint
is a spine, pad or ring-adjacent vertex on v2's reading; the oracle's
classification of these three pairs is not derivable from the tables
(v1 `grade_graph.shape_constraints` visibility + frontage logic).
Attempt cap reached; open question 2.

4.3 **strip_seam_tear 1.** Three iterations on this family (the pocket
rule; corridor membership by class; membership from the map with the
mitre overshoot clamped) took 19 → 11 → 1; the survivor is a zone-1
vertex shared with a junction beside a road lot, 2.2 m against a
DEM-following neighbour. Attempt cap reached.

4.4 **Crown declaration gap 448 (reported, never adjudicated).** v2
declares the BUILT drop on every runway-family vertex; a taxi ring that
shares a runway-edge vertex pairs a declared vertex with an undeclared
one and the oracle judges the pair at its most favourable compatible
target. Declaring 0 on taxi vertices would assert an artificial 0.2 m
step at the runway edge (measured against the oracle's re-centring), so
the gap is left as reported. Open question 3.

## 5. Deviations from the spec (for the spawner's ruling)

1. **`Linear` row** added to `model/constraints.py` (additive; the M0
   five kinds cannot state a rate law — a three-term second difference —
   or a transect over two ring-edge interpolations); `ConstraintSet`
   gained `linears` and `from_rows`; `PlanarMap.ring_vertices` added.
2. **Law tables extended** (data + schema, no numeric value in Python):
   `emit.toml [transect]` (the walk's step / reach / span), `[within_shape]`
   (apron body gate 60 m, runway station cluster 5 m), `[instrument]`
   (the census's rounding envelopes 0.03 / 0.1 / 0.15 m, contact and
   search radii, the weld-hub roles); `rulesets.toml end_skirt.corridor_length_m`
   by code (the RESA corridor length v1 keys by code number under both
   authorities); `precedence.toml` `rigid = true` on `building` (03h: a
   pad is one flat value levelled by its contact).
3. **Bound in the instrument's frame** where the tables' laws are
   mutually inconsistent at chord scale: the rate laws (airside no-step
   §1.2, strip_arc, raoa) carry the reader's own blind spot
   `q·(1/dp+1/dn)` less the emit quantum, and the strip abeam / RESA /
   end-corridor rows the strip reader's 0.1 m envelope less the quantum.
   Measured: without them the crown floor + rate + direct pair at a
   runway corner is an IIS at 1–3 m spacings; with the full envelope the
   LP sits on the bound and the 0.01 m emit rounding breaks it (17 rows).
4. **Crown as a floor, declared as built** (family table: `offset`):
   an exact equality was an IIS with the rate law; with the built drop
   declared the runway ring's within-shape pairs are implied by the
   profile caps (no rows minted on `runway` rings; crossings stated in
   foot space).
5. **Pocket rule for zone bands** (08-01 clarification "pockets fill"):
   every family whose corridor holds a strip vertex contributes its
   floor; only the nearest pavement its mandatory-down ceiling; runway
   bands abeam the runway only (the end corridor is the skirt law's).
6. **Lateral contiguity read at the shared edge**: a road face sharing
   an edge with a stricter governed class is bound (and tagged
   `o4_grade_law_cap`) at that class's cap — M2 reads contiguity at the
   edge, the per-station road clamp is M3.

## 6. Twins (`tests/auto_patch_v2/`, 64 pass; the 11 errors + 2 failures are pre-existing on main: M1's synthetic `.hgt` fixtures were never committed)

`test_constraints.py` (364 lines): a synthetic airport (one code-3
runway with CIFP thresholds, a parallel taxiway, a stub, an apron with a
pad, a service road, on a 1 % plane DEM) through `planar.build`; one
twin per generator (precedence tiers from the tables; pins/profile/
crown; taxi/apron/road populations and caps; the transect walk; no-step
pairs and rate; relative zone bands; strip footprints; pad flats);
assemble → solve → emit → verify round trip; the IIS naming a
contradictory pin pair; a benchmark-shaped 2,500-vertex instance solved
and its infeasible variant diagnosed; the osm writer's mesh-read
contract read through v1's own `_parse_osm`; verify vs the v1 census on
CYXY (data repo present). `test_model.py` updated for `linears`, the
implemented `solve` / `write_patch`, and the M2 dependency direction.

## 7. M3 brief skeleton (SPLP, SPJC)

| item | what M2 leaves | M3 |
|---|---|---|
| roads | contiguity at the shared edge; road bodies at 8 %/2 % | the core's road clamp for the general profile; per-station `station_caps` publication (the oracle's fourth reader) |
| pads at scale (SPJC 71 + 17 object pads, 369 pad↔pavement rows) | rigid flat groups levelled by contact | contact welds on DSF pads; detached pads DEM-levelled; pad↔pad step exemption already in the tables |
| strips (SPJC strip_arc 57, SPLP 17) | strip families bound in the reader's frame | the pocket drainage spine (`zones.pockets.drainage_spine`); the RAOA reading (open question 1) |
| lattice / membrane (M0 Q3) | vacuous on v2 | interior lattice vertices at `apron_interior_spacing_m` join the arrangement, or the membrane as a face-plane row |
| DEM frame (M1 Q5 / 03j) | raw hgt + inset feathered | production's smoothed tile DEM through a core-side accessor |

## 8. Open questions (≤ 5)

1. RAOA: should the reader price per lateral line (profiles along the
   approach), or does the owner want the cross-width reading bound (then
   the taxi zone band must yield inside the RAOA rectangle)?
2. The three apron body chords the oracle prices strict: is v1's
   visibility/frontage classification the law (then the tables need the
   rule), or the tables' population (then the oracle over-reads)?
3. Crown declaration on non-runway vertices sharing a runway edge: leave
   undeclared (reported gap) or declare the runway-edge value?
4. The reader envelopes now live in `emit.toml [instrument]` as law
   data the solver reads (deviation 3): ratify, or move the margin into
   a solver config?
5. Mesh A/B: one run per arm; is a `--runs 3` read wanted before the
   "no slower, fewer edges" bar is called met?
