# Grade Debt Ledger

**Frame:** composed main after the R5+R5c merge (engine 1.50.1696), censuses
`CYXY_20260815T214510` / `HECA_20260815T214605`, 2026-08-15 late.
"Adjudicated" = law-true census rows after registered exemptions (declared
terraces), out-of-scope, and version-deferred families — the pass/fail
population. Airside has been **byte-identical through every arm tonight**:
nothing below is a regression from today's rounds; it is the standing debt,
now fully attributed.

## Headline

| airport | adjudicated | airside | groundside | mixed |
|---|---|---|---|---|
| CYXY | **333** | 74 | 259 | 0 |
| HECA | **6,955** | 1,733 | 5,134 | 88 |

Airside is not zero. The airside mass decomposes into three categories
(C1–C3 below); none is unattributed.

## Root-cause categories

### C1 — The mega-apron relief residual (largest airside block)
**Rows:** HECA airside `within_shape` 1,502 (worst 11.36 m, p50 0.82);
CYXY `raoa` 8 (worst 6.15) is kin.
**Cause:** HECA's real ~85 m relief against apron/taxi caps. The production
law (spine-frame + §7 reference rods + route-metric band) is the ruled
answer; these rows are its residual — the solve does not fully reach the
lawful surface feasibility-is-guaranteed says exists.
**Proposed:** its own round, fed by the two OPEN owner rulings from K1b
(the string-bend class and the rwy-flexed class). No new law proposed here
until those are ruled.

### C2 — Strip conformance seams
**Rows:** airside `strip_seam_tear` 45 (worst 8.55 — two pre-existing
sites + the docketed B2 site), `strip_arc` 55, `strip_longitudinal` 3,
`adjacent_ground_tear` 4.
**Cause:** strips conform to two authorities at a seam and disagree — the
node-vs-edge class.
**Proposed law (already docketed, refined by R5b's refutation):** shared
boundaries are LAW-PAIRED in the one graph — never a frozen side, never
two independent conformances. One spec covers this and the R5c weld-site
dossier (C6).

### C3 — Station misalignment expressed as transverse tilt
**Rows:** groundside `transverse` 1,684 HECA / 82 CYXY (ALL same-shape;
p50 grade 5.1 % at p50 width 7.5 m; junctions carry 1,154 of 1,684),
airside `transverse` 104 / 63.
**Cause (corrected 2026-08-15 late, after the owner's 0 %-by-construction
question):** the cap and the instrument are both right — each paired
cross-section IS 0 % by the station-shared value rule, and the census
casts true perpendiculars. The rows live BETWEEN stations: where opposite
edges carry vertices at misaligned arclengths, edge interpolation samples
two different effective stations and the road's lawful LONGITUDINAL grade
appears as lateral tilt (8 % × ~4 m misalignment ≈ 4–5 % across 7.5 m —
the measured p50). A flat chord had zero longitudinal grade, so the class
was invisible until R5 made roads track terrain. The mesh interpolates
the same way, so these are real small diagonal warps, honestly priced.
Junction rings dominate because they have no cross-section pairing at
all; the 350 % worst cases are genuine junction cliffs (co-level
residue).
**Fix (no ruling needed):** plant aligned partner feet on BOTH edges at
every road station, and extend the R5c co-level so junction ring
vertices join the through-chain's stations. The family then collapses
to the real cliffs.

### C4 — Landside lots, frontage welds, and the lot-over-road class
**Rows:** groundside `within_shape` 3,176 HECA / 174 CYXY, plus most of
`mid_edge_step` 231 / `vertex_to_edge_step` 47.
**Cause (three rulings, all made tonight):** the free-road width test has
no landside term (car parks absorb public roads — 142/160 HECA groundside
shapes contain mapped roads); building-pad datums weld into frontage road
networks; lots were cut-only (`min(terrain, 8 % cone)` — the 40,000 m³
CYXY hollow).
**Fixes (ruled, spec next):** R6 — roads carry OSM-sourced spines that
pass THROUGH pavement (crossed pavement consumes spine stations);
R7 — mouths-only welds (never buildings; parallel frontage cuts back to
DEM at its real level) + two-sided cut-and-fill lots + the landside term
in the free-road knife. The sink dossier's model (r = 0.96) says this
category collapses when the illegitimate low welds go.

### C5 — Gap fill and drainage
**Rows:** airside `drainage_spine` 8 (the gapstop single-spine residual);
the photographed plateau walls are mostly census-invisible (no law pair
spans pavement→gap→pavement at range).
**State:** F3/F3b implemented on `lane/gapconform` and HELD at the
attempt cap — the staged spine law is in (conformance band pinned,
interior dam + descent cones, MIN_FALL still provisional), but a
1,323-row emitter population (spines riding terrain above pavement at
median 76 m range, worst 25.6 m) is not yet located to its emitting path.
**Next:** one attribution pass (sample rows → way ids → emitter), then F3
merges and this category plus much of the in-sim flats class closes.

### C6 — Marginalia (small, named, bounded)
`frontage_near_miss` 94 (88 mixed, worst 11.53 — rides C1's relief),
`runway_crown` 9 (all ≤ 0.07 m), `runway_end_skirt` 3, `plane_gradient` 7,
`lateral_contiguity` 3, and the R5c weld site (2 step rows + 1 sliver,
dossiered — joins C2's law-pair spec).

### C7 — Withheld patches (invisible to any census)
**KAFW:** +32 arm refuses (0.287 m transverse seeding deficit between
parallel runways) — R8 specced: the DEM-follow band becomes route-feasible
transversely (or interim: join contacts at every taxi crossing, seated
through `faa_joint_solve`).
**KDFW:** refuses on a different family — a hard-seed plateau at
183.286 m against a runway station at 176.470 (6.8 m law spread,
650 nodes). Unattributed; the larger +32-098 blocker.
A refused patch is a whole airport absent from the tile — these outrank
any row category for in-sim impact.

### C8 — What no census can see
Seed-character and DEM-deviation-at-range classes are census-invisible by
ruling (the warm-start lesson). In-sim remains the only detector; the
mixed-version tile-seam hazard (tiles built on 1.0.249–251 carry flattened
edges) persists until affected tiles are rebuilt on the current app.

## Priority reading

1. **C7** (whole airports missing) — R8 + the KDFW attribution.
2. **C4** (the groundside bulk, ~3,400 rows, all three laws already ruled) — R6/R7 spec + lane.
3. **C5** (F3's last attribution pass) — closes the photographed classes.
4. **C3** is a station-alignment fix (no ruling needed) — ~1,700 rows collapse to the real junction cliffs.
5. **C1/C2** are the airside end-game — the two open K1b rulings gate them.
