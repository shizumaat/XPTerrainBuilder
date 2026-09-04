# auto-patch-v2 — plan (owner direction 2026-09-03 evening)

**Goal.** A ground-up `auto_patch_v2`, built side by side with v1, that
produces FULLY LAW-COMPLIANT graded-elevation products for airports,
simpler and faster to generate and to apply to the mesh. Not byte-identity
with v1 (owner amendment): v1's patches are not lawful either. First
milestone airports: SPJC, SPLP, CYXY. Bars: the v1 law-true census
(`tools/harness/census.py`, the campaign's own instrument) reads ZERO on
v2's patch; build wall time under the 60 s ship gate for those three;
patch applies to the mesh faster than v1's (fewer constrained edges, no
T-vertex/duplicate-chain class); every source file ≤ 1,000 lines; total
≈ 20–25k lines including tests.

**Why from the ground up.** The week review (`review-20260903-week.md`)
measured v1 at 225,964 lines (≈120k code, 605 env gates, 14 functions over
1,000 lines) with a dozen post-solve writers each repairing the last. The
size is the architecture's symptom: value authority is spread, every law
is spelled at more than one site, and the same geometry is recomputed per
pass. Today's two findings are the pattern: the tunnel wall crest derived
at two sites (one masking the other), and pass-2 "infeasible" pins that
were phantom values a backfill invented (R1.3, 977 of 1,362). v2 fixes the
cause: ONE data model, ONE law table, ONE solver, ONE writer.

**Portability requirement.** X-Plane's Next-Gen scenery (FSExpo 2026,
Supnik): S2 hierarchical cells replace 1° DSF tiles; terrain becomes
layered raster datasets (elevation grids, orthophotos, LiDAR) patchable
per layer; a tile engine ships late 2026 with third-party support; DSF
stays compatible. Nothing is stated about airport flattening, mesh
authoring formats or an SDK. So v2's core product must be format-agnostic
— a graded surface with breaklines — and the Ortho4XP `.osm` patch is one
adapter over it; an elevation-grid adapter (rasterise the graded surface
into a cell's DEM layer) is the second, when the format is known.

## 1. Architecture

Seven packages, one direction of dependency (each imports only those
above it). No package writes vertex elevations except `solve`; no package
reads the environment except `pipeline` (no `O4_*` gates: behaviour is a
config object with a schema, checked in with defaults).

| # | package | job | ≈ lines | v1 material worth keeping |
|---|---|---|---|---|
| 1 | `airport/` | domain model + loaders: apt.dat (100/102 runways, 110 pavements, 120 linear, 1201/1202 taxi network, 1206 ground routes, 130 boundary), CIFP thresholds, OSM (roads, buildings, bridge/tunnel/layer tags), DEM + insets sampler, DSF objects, scenery signature. Pure dataclasses in ONE local metric frame (one `pyproj` transformer per airport). | 4,000 | `apt_dat_reader.py` (2,159 — split by record type), `cifp`, `dsf_reader.py` (2,334 — keep the DSFTool dump cache + reader, drop the rest), `osm_load.py` (1,537 — keep the extract filter), the core's inset machinery stays core-side |
| 2 | `classify/` | roles per pavement face from apt.dat surface + taxi network + OSM evidence: runway, runway_crossing, primary/secondary parallel, junction, stub, apron, service_road/junction, groundside, building pad. One scorer, one output (`Role` per face). | 2,000 | `pavement/global_slice.py`, `pavement_scoring.py` (2,853 — the v2 rules, not the v1 gates) |
| 3 | `law/` | THE LAW AS DATA: grade caps per role (longitudinal/transverse, FAA/ICAO), authority precedence, adjacent-ground zone widths, tunnel/bridge model constants (bore datum 5.1 m, wall gap 0.6 m, crest = DEM), building pad law, seam law, chord density. TOML data files (human-readable, editable without code changes — owner 2026-09-03e; each key commented with meaning, unit and ruling id) + a typed schema/loader (`Law.load`, `Law.for_airport`) that validates and fails loudly; **no mechanism, no numeric value in Python**. Appendix A (law inventory) is its source of truth. | 800 | `grade_law.py` constants, `check_grade.LAW_FAMILIES` definitions, `layout.AUTHORITY_PRECEDENCE` |
| 4 | `planar/` | the PLANAR MAP: faces (role, ref), edges (both faces), vertices (11-dp identity, all incident faces), breaklines (centerlines, runway profile stations, zone boundaries, structure outlines), STRtree index, cached unions. Built ONCE from `airport` + `classify`; every later stage reads it, none mutates it. Shared edges exist once ⇒ no welds, no annuli, no T-vertices by construction. | 3,000 | `layout.py` ideas (shape/ref/role), `pavement/junctions.py`, `centerlines.py`, `hole_router.py` (audit first) |
| 5 | `constraints/` | from planar map + law + inputs, ONE constraint set: hard pins (runway profile from CIFP/apt.dat, tile seams), difference constraints \|z_i − z_j\| ≤ cap·d on every edge (longitudinal along breaklines, transverse across faces), rigid flat groups (pads), zone bands toward DEM (adjacent-ground zones 1–2; zone 3 = DEM), structure constraints (tunnel ramp descent + mouth datum + wall crest = DEM, deck clearance, basin floors), building pad contacts, no-step pairs, apron membrane. Generators are pure functions returning rows; structures (`tunnels.py`, `bridges.py`, `buildings.py`, `basins.py`) are constraint GENERATORS, not writers. | 5,000 | tunnel/bridge/deck/pad LAW from `bridges.py`/`object_terrain_*` — the rules, never the emitters |
| 6 | `solve/` | ONE solver, ONE writer. Sparse convex QP: minimise Σ w_i (z_i − dem_i)² + λ·roughness along breaklines, subject to the linear constraint set; `scipy` HiGHS (present in the venv) for the LP feasibility phase and an ADMM/OSQP-class QP for the objective (OSQP to be added to the freeze if adopted; scipy-only fallback exists). Infeasibility is DIAGNOSED exactly (irreducible infeasible subsystem naming the pins and their generators) and reported, never smeared by a stall guard. Output: z per vertex + the residual certificate. | 1,500 | the CONSTRAINT semantics of `one_solve.feasibility_project` (\|Δz\| ≤ cap·d, hard nodes, flat groups); none of the Gauss-Seidel machinery, bands, seat couplers, fairing sweeps |
| 7 | `emit/` | products over the graded surface: `GradedSurface` (vertices with z, faces, breaklines, roles — JSON/GeoPackage), the Ortho4XP `.osm` patch adapter (ways per face, node `ele`, tags role/ref/shapeID, interior rings, chord density from `law`, ONE quantisation at 11 dp, sidecar with only what the mesh and the census read), and later an S2 elevation-layer adapter. | 1,500 | `to_osm` tag contract (what `O4_Vector_Map` reads), `emit_snap` |
| — | `verify/` | the census as pure functions over `GradedSurface` + `law` — the SAME tables the solver used, so a family cannot be omitted; plus a v1-oracle mode that runs `tools/harness/check_grade.py` on the emitted patch for cross-validation until v2's census is proven equal on three airports. | 1,500 | `check_grade.py` families (as the oracle, not as code) |
| — | `pipeline/` | orchestration (≈ 300 lines), CLI, progress events (the JSONL wire the app already speaks), content-hash stage cache (inputs → planar map → constraints → solution; a change re-runs only downstream), config schema. | 800 | `progress.py`, the harness entry points unchanged (`build_airport.py --engine v2`) |

Total ≈ 20k source + ≈ 8k tests. Files over 1,000 lines: none planned.
If any grows past it, the split is by data type (loaders) or by constraint
family (generators); the one candidate is `solve/assemble.py` (matrix
assembly for ~20 constraint kinds) — keep assembly per kind in
`constraints/` so the solver only stacks rows.

### What v2 deliberately does not have
No post-solve writers (transition law, conformance, re-seeders, FGP,
seam anchors, crown extension, relevel, reclip): all of them are either a
constraint the solver honours or gone. No gates. No history in code
(rulings stay in RULINGS; code cites the ruling id). No per-pass unions
(the planar map caches). No second decimator (chord density is a law
parameter applied once at planar-map build). No "band inversion", "seat
coupler", "flex", "reach band", "seed" vocabulary: a vertex has a DEM
sample, constraints, and a solved value.

## 2. The solve, precisely
Variables: z ∈ R^n over planar-map vertices (HECA ≈ 100–150k; CYXY ≈ 5k).
Constraints (all linear): pins z_i = p_i; edges −c·d ≤ z_i − z_j ≤ c·d;
flat groups z_i = z_j; bands l_i ≤ z_i ≤ u_i (zone 2 toward DEM, tunnel
datum floors, deck clearance as z_deck − z_ramp ≥ 5.1). Objective: Σ w_i
(z_i − dem_i)² with w by role (airside high, groundside 1, zone 3 pinned
to DEM), plus a second-difference penalty along breaklines for
smoothness. Measured (solver-benchmark-20260903.md): scipy/HiGHS LP with the real
objective solves 150k vertices in 5.3 s (2.0 GB), 15k in 0.23 s; OSQP is
refused (112 mm violations at default, 680 s + a false infeasible at
1e-6). M2 uses the L1 form (|z − dem| + L1 roughness) as a pure LP; a
HiGHS QP via `highspy` is the follow-up benchmark. Feasibility first (LP phase 1): if
infeasible, extract an IIS and report `(constraint, generator, inputs)`
— the R1.3 question ("who minted the contradiction") is answered by the
solver itself, every build, in the log. The solver never invents a value:
a vertex with no constraint and no DEM is an error at planar-map build.

## 3. Milestones (each: one spec, twins, one airport, the v1 census as oracle)
| M | deliverable | airport | bar |
|---|---|---|---|
| M0 | Appendix A law inventory + Appendix B v1-at-three-airports scope, ratified by the owner; `law/` tables written from A | — | owner sign-off on the law tables |
| M1 | `airport/` + `classify/` + `planar/`: planar map for CYXY; zero T-vertices; role agreement with v1 REPORTED, not a bar (03j) | CYXY | DONE 1c…5eb250d0: 1.13 s, 0 T-vertices, 48 %/71 % agreement, every difference listed |
| M2 | `constraints/` + `solve/` + `emit/osm` + `verify/` + `pipeline/`: CYXY lawful | CYXY | DONE 8a4d5d56 (04a): 3.2 s; v1 census 160 → 33 (raoa 29 = oracle artefact, within_shape 3, tear 1); mesh edges 247k → 243k, step 1 39.4 → 34.8 s |
| M3 | groundside, roads (core clamp; v2 only the contacts), building pads | SPLP, SPJC | SPLP DONE cf37ed6a (04b): 6.8 s, census 27 → 0; SPJC in flight (pad↔pavement class waits on 03k) |
| M4 | structures: tunnels (mouth/ramp/wall/crest = DEM), bridges/decks, basins | OTHH, LEMD | census 0; owner sim read |
| M5 | HECA, KCLT: relief (85 m) and scale | HECA, KCLT | census 0; HECA < 60 s |
| M6 | `emit/` S2 elevation-layer adapter stub + `GradedSurface` spec frozen | — | round-trips CYXY |

Side by side: `Ortho4XP/src/auto_patch_v2/`, selected by
`build_airport.py --engine v2` and the app's config; v1 keeps shipping.
The five-airport sweep gates each milestone (29f). No milestone starts
before M0 is ratified.

## 4. Owner decisions (RULED 2026-09-03d)
1. **Numeric solver**: add OSQP to the freeze if it measurably beats
   scipy/HiGHS on the v2 QP — measure first, then add.
2. **Law tables**: v2's `law/` is v2's own single source; v1 is NOT
   retargeted (no value); v1's census remains the cross-validation oracle.
3. **Loaders and classifiers are rewritten**, v1 as the reference only.
4. **Mesh-apply bar**: tile mesh wall time and constrained-edge count,
   v2 patch vs v1 patch on the same tile — no slower, fewer edges.
5. **Models**: Fable for design, specs, reviews AND implementation
   (owner 2026-09-03h: higher success rate).
6. **Apron relief (03h/03i)**: SENIORITY FOLLOWS FROM BEING GOVERNED —
   anything without a grade law yields to everything that has one. Pads
   yield by omission: a pad is a flat group levelled by its apron
   contact, never a pin the apron climbs to. `precedence.toml` states
   the principle; the loader derives the ungoverned tier from the caps.

## 5. The numbers v2 starts from (Appendix B)
| | SPJC | SPLP | CYXY |
|---|---|---|---|
| v1 build (09-02, exclusive) | 166.2 s (solve 113, emit 49) | 9.5 s | 41.5 s |
| law-true rows / AIRSIDE to close | 686 / **596** | 35 / **27** | 160 / **67** |
| the airside classes | pad↔pavement no-step 369, strip_arc 57, drainage_spine 37 | strip_arc 17, runway ring pairs 3 (1.7 % vs 1.5) | transverse at junctions/roads 72, no_step 24 |
| patch / sidecar bytes | 2.75 MB / 24.1 MB | 0.30 / 1.1 | 1.24 / 5.1 |
| nodes, chords p50 (apron p50) | 14,495, 9.5 m (1.96 m) | 1,654, 15 m | 6,660, 14.4 m |
| mesh step 2 (tile) | 8.1 s | 23.3 s | 11.2 s |

Generation is 30–40× the mesh cost; solve + emit are 97–98 % of it. The
mesh reads only altitude fields (Appendix A §5) — the 24 MB sidecar is
instrument-only, so v2's sidecar carries exactly the census inputs.
Three-quarters of SPJC's airside rows are one class (building pads
stepping against pavement): the M3 pad law is the SPJC milestone. SPLP's
three runway rows show the centreline twin and the ring census disagree —
v2's `verify/` measures rings, as the census does.

Appendices: `auto-patch-v2/appendix-a-law-inventory.md` (the law),
`auto-patch-v2/appendix-b-three-airports.md` (scope and mesh cost).
