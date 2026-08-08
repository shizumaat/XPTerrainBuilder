# Aerodrome design standards implemented by `auto_patch`

This is the human-readable index of the FAA / EASA / ICAO rules that `auto_patch`
enforces, with citations and a pointer to the **code constant that implements each rule**.

> **Source of truth = the code constant, not this document.**
> `src/auto_patch/config.py` holds the machine-readable rule *values*. This file explains
> *why* each value is what it is and where the standard comes from. If a number here
> disagrees with the constant in code, the code wins — and the doc should be fixed. Never
> hard-code a rule value at a call site; import it from `config.py`.

Algorithmic rules (vertical-curve relaxation, the elevation-solver priority cascade) are
not single constants — they live in the modules noted below, and this index points at them.

## Grade limits

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Within-shape grade cap, taxiway-family (taxiway, parallels, stub, cross-connector) | 1.5% | FAA AC 150/5300-13 | `config.py` `ROLE_GRADE_LIMITS` |
| Taxiway **longitudinal** grade cap `cL` (along the route, size-dependent) | C–F 1.5%, A/B 3.0% | ICAO Annex 14 Vol I §3.9.8; EASA CS-ADR-DSN.D.265 | `config.py` `taxi_grade_cap_for_letter` (`TAXI_MAX_GRADE` / `TAXI_MAX_GRADE_NARROW`), gate `TAXI_GRADE_BY_WIDTH` |
| Taxiway **transverse** grade cap `cT` (across the route) | C–F 1.5%, A/B 2.0% | ICAO Annex 14 Vol I §3.9.11 (taxiway transverse slopes); EASA CS-ADR-DSN.D.280 | `config.py` `taxi_transverse_cap_for_letter` (`TAXI_MAX_TRANSVERSE_NARROW`), same gate |
| Within-shape grade cap, apron / junction body (all directions) | 1.5% | FAA AC 150/5300-13 (per-user 2026-05-07) | `config.py` `ROLE_GRADE_LIMITS` |
| Within-shape grade cap, aircraft STAND (all directions) | 1.0% | FAA AC 150/5300-13B §5.9 / EASA CS ADR-DSN.E.360 / ICAO Annex 14 §3.13 | `config.py` `STAND_MAX_GRADE` + `ROLE_GRADE_LIMITS["stand"]`. Aprons are split into `ROLE_STAND` pads (at ramp-start 1300/1301 zones), lane corridors, and body by `pavement/apron_split.decompose_aprons` so the cap binds to real geometry |
| Within-shape grade cap, terminal | 1.5% | design | `config.py` `ROLE_GRADE_LIMITS` |
| Ground-vehicle service road + its junctions (apt.dat 1206 truck route + OSM small road, dedicated strip off aircraft pavement) | 8.0% | VDOT Road Design Manual App. A1, *Geometric Design Standards for Service Roads (GS-9)*, "Relationship of maximum grades to design speed": LEVEL terrain 8% @ 10–20 mph, 7% @ 30–40 mph. No aviation authority regulates it (FAA AC 150/5300-13B, ICAO Annex 14/Doc 9157, EASA CS-ADR-DSN, ACRP 25 verified silent). Owner-approved 2026-08-03 (was 5.0%, design, user 2026-07-04; 4.0% before that) | `config.py` `SERVICE_ROAD_MAX_GRADE` + `ROLE_GRADE_LIMITS["service_road"]` / `["service_junction"]` — **`service_junction` rides the same constant**, so the two cannot be set apart without a second owner ruling; rect+junction network built by `pavement/service_roads.build_service_road_network` |
| Tunnel ramp navigable grade | 4.0% | per-user 2026-05-08 | `config.py` `ROLE_GRADE_LIMITS` |
| Groundside pavement (curbside / parking) ramp grade | 5.0% | ADA 2010 Standards §403.3 (walking-surface running slope ≤ 1:20); Iowa SUDAS ch. 8 §8B-1 *Parking Lots — Layout and Design* ("Slopes greater than 5% are discouraged"); City of Santa Barbara Parking Design Standards §D.5 ("slopes of all parking areas shall not exceed 5%, excluding ramps"). No aviation authority regulates it (FAA/ICAO/EASA/ACRP verified silent) — region-invariant. Owner-approved 2026-08-03 (was 4.0%, **uncited**, inherited from the tunnel-ramp constant, per-user 2026-05-22) | `config.py` `GROUNDSIDE_MAX_GRADE` + `ROLE_GRADE_LIMITS["groundside_pavement"]`; `groundside.py` imports it |
| Grade rule SKIPPED (footprint outlines / vertical walls / clearance shadows) | — | n/a (trace terrain or vertical by design) | `config.py` `ROLE_GRADE_LIMITS` = `None` for `boundary`, `retaining_wall`, `taxiway_clearance`, `runway_clearance` |

The within-shape grade *validator* (`tools/check_grade.py`) reads `ROLE_GRADE_LIMITS`
directly, so it always matches whatever the table says.

The taxiway caps are **anisotropic** in the local route frame: a pair's grade
budget is `cL·Δs∥ + cT·Δs⊥`, where `Δs∥` is the along-route spine ARC and `Δs⊥`
the transverse offset (`grade_law.Allowance`, `grade_graph.ds_decompose`). For C–F
`cT == cL` so the allowance is isotropic (the legacy `cap·dist`); only A/B and
curved spines are genuinely anisotropic, which is what lets a climbing taxiway
CURVE keep its full longitudinal budget through a junction (the spine arc, not its
shorter chord). See `docs/anisotropic_edge_handling_plan.md`.

## Runway longitudinal profile

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Max longitudinal grade | 1.5% | FAA AC 150/5300-13B (ARC C–E) | `pavement/runway_segments.py` `MAX_RUNWAY_GRADE` |
| Max grade in first / last quarter (code 3/4) | 0.8% | EASA CS-ADR-DSN / ICAO Annex 14 | `pavement/runway_segments.py` `RUNWAY_END_GRADE` |
| Vertical-curve length | L = K·\|Δg\|, K = 305 m (ARC C/D) | FAA vertical-curve rule (L ≥ 1000 ft × \|ΔG\| for Design Group III+) | `runway_regrade.py` `DEFAULT_ARC_K_M`; `pavement/runway_segments.py` `MAX_RUNWAY_GRADE_CHANGE_PER_M` (= 1/30000 per m) |

The runway profile is built and re-checked by:
- `pavement/runway_segments.py` `faa_joint_solve` — emit-time FAA gate (envelope clamp +
  grade-limited smoothing + vertical-curve relaxation).
- `runway_regrade.py` `regrade_runway` — re-optimises threshold altitudes against tile-seam
  HARD anchors while honoring the grade cap and K-factor (relaxation order: K-factor first,
  then grade cap; seam altitudes are never relaxed).
- `runway_redistribute.py` — re-runs the FAA gates after seams / tile cuts so the combined
  multi-segment profile stays compliant.

### Tile seam = another runway-grading anchor (owner ruling 2026-07-24)

> "We are not giving up the CIFP thresholds, it's just that a tile seam acts like a
> crossing runway, it's ANOTHER anchor that is part of the runway grading. The tile
> seam at ALL points must be anchored at DEM."

Every non-runway role takes the seam DEM directly at its own vertex. A runway cannot: it
also carries CIFP threshold elevations and the grade / vertical-curve law above, and it is
laterally FLAT — so its seam contact (a whole LINE across the runway's width; 148 m of it
where SPLP's RW02/20 meets lon −77 at 18°) reaches the surface through the runway's one
degree of freedom, its longitudinal profile. The seam therefore enters the profile solve
as additional HARD anchored samples, exactly like a crossing-runway anchor.

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Seam-contact anchor spacing (walk of the runway's contact with the tile line and with both cut-back lines) | 10 m | design (owner ruling 2026-07-24 "ALL points"; finer than the DEM posting costs nothing but reports resampling steps as conflicts) | `config.py` `RUNWAY_SEAM_CONTACT_STEP_M`, gate `RUNWAY_SEAM_CONTACT_ANCHORS` |
| Cut-back offset — where `tile_cut` actually ends the pavement, and therefore where the seam DEM must be met | 5 m either side of the integer line | design (the ruling names "the nodes along a tile seam at the cutback") | `config.py` `TILE_CUT_HALF_WIDTH_M` (also the `tile_cut.cut_layout_at_tile_boundaries` `half_width_m` default — one source) |
| Anchor admission | the two EXTREME contacts always; an interior contact only when both its neighbouring segments stay within `MAX_RUNWAY_GRADE` | the grade cap above is LAW and wins over a terrain match | `runway_redistribute._select_feasible_seam_anchors` |
| Unreachable contacts | REPORTED, never midpointed — station, DEM value, grade demanded, and post-solve residual | owner ruling 2026-07-24 ("report … by how much they conflict") | `layout._runway_seam_law_conflicts` + `layout._runway_seam_audit`; one summary log line per runway |

Cross-tile determinism: `redistribute_runway_profile` runs BEFORE `tile_cut`, so each tile
build measures the contact on the WHOLE runway and generates the same three lines from the
same fixed 5 m offset; the DEM at a tile line is the `preserve_boundary`-blended value both
tiles share. Both builds therefore derive an identical anchor set — and an identical
profile — without seeing each other.

### The CROWN must be zero at the seam (owner ruling 2026-07-24)

> "We need to deal with the crown spine when a seam crosses a runway. Because we have to
> be at DEM we need to be sure the crown spine connects all the way to the shape edge
> after the seam cut, and that the spine ramps smoothly down to 0 crown at the seam at
> less than 1% grade."

The anchor rule above puts the runway PROFILE on the DEM at the cut-back line. A crowned
runway emits its edges at `profile − crown_drop`, so without this ramp the pavement edge
sits the whole crown BELOW the terrain the 10 m tile-cut gap renders (measured at SPLP,
both tiles: 0.20–0.23 m on the two mid-width cut-edge nodes, with no axial taper at all —
the pre-ruling taper measured distance to the nearest seam *vertex*, which at an 18°
oblique crossing is 49 m away and never binds).

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Crown shed rate approaching a tile seam | 0.5% | owner ruling 2026-07-24 ("less than 1%"); half the pre-ruling 1.0%, below both the FAA Table 3-6 minimum runway crown (1.0%) and `RUNWAY_END_GRADE` (0.8%), and 3× under `RUNWAY_MAX_GRADE` | `config.py` `RUNWAY_CROWN_SEAM_TAPER`, gate `CROWN_SEAM_RAMP`; applied in `crown._seam_ramp_cap` |
| Where the crown reaches 0 | exactly on the cut-back line (`TILE_CUT_HALF_WIDTH_M` off the tile line) | the ruling: the pavement's real edge is where the profile meets DEM | `crown._seam_cut_dist_m` (floored at 0 inside the gap) |
| Largest crown this can shed | `RUNWAY_CROWN_TRANSVERSE × 30 m` = 0.30 m over 60 m | the ruling's "must shed over more than 30 m" | `crown._RUNWAY_HALFW_CAP_M` |
| Crown spine (ridge breakline) at a seam | terminates ON the cut-back edge; `_SPINE_EDGE_CLEAR_M` / `_SPINE_RING_CLEAR_M` waived there only | the clearance avoids a value conflict with a ring vertex; at a cut edge the drop is 0, so ridge and ring carry the same value | `crown._extend_spine_to_cut_edges`, `crown._emit_ways_for_profile(seam_cut_exempt=…)` |

Cross-tile determinism: the ramp is `rate × (distance from the node's own lat/lon to the
nearest integer lat/lon line − TILE_CUT_HALF_WIDTH_M)`. Only the graticule and two fixed
constants enter — never "my tile's side of the cut" — so both tile builds compute the
identical drop at any shared seam position. Because the cap is a function of the
perpendicular distance alone its gradient is exactly the rate, so the realised shed along
any line (runway axis, rail, oblique cut edge) is ≤ the rate.

## Aerodrome reference code

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Code NUMBER from runway length | 1 (<800 m), 2 (800–1199), 3 (1200–1799), 4 (≥1800 m) | ICAO Annex 14 | `config.py` `runway_code_number()` |
| Code LETTER from taxiway width | A (≥7.5), B (≥10.5), C (≥15), D (≥18), E (≥23), F (≥25 m) | ICAO Annex 14 | `config.py` `taxiway_code_letter()` |
| Max wingspan per code letter | A 15 … F 80 m | ICAO Annex 14 | `config.py` `WINGSPAN_BY_CODE_LETTER` |
| Max aircraft TAIL HEIGHT per code letter | A 6.1, B 9.1, C 13.7, D 18.3, E 20.1, F 24.4 m | FAA AC 150/5300-13B Table 1-1 (ADG by tail height: I ≤20 ft, II <30, III <45, IV <60, V <66, VI <80); ADG I–VI ↔ code letter A–F | `config.py` `TAIL_HEIGHT_BY_CODE_LETTER` |
| Code LETTER from RUNWAY width | A (<15), B (≥15), C (≥21), D (≥28), E (≥42), F (≥55 m) | FAA AC 150/5300-13B Table 3-3 runway widths by ADG (I 18.3, II 22.9, III 30.5, IV/V 45.7, VI 61.0 m); ICAO Annex 14 Table 3-1. ADG IV and V share 150 ft, so 45 m resolves to **E** — the taller tail, i.e. the conservative reading for a ceiling law | `config.py` `runway_code_letter()` (distinct from the TAXIWAY table above — different standard) |

## Runway-end safety area (RESA) and runway strip

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| RESA / runway-end graded length, by code | 1:60, 2:90, 3:150, 4:240 m | ICAO Annex 14 (90 m min, 240 m recommended) | `config.py` `RUNWAY_END_CLEARANCE_LENGTH_BY_CODE` |
| Runway-end governed footprint ANCHOR | measured from the RUNWAY END (apt.dat row-100 endpoint); blast pad / stopway pavement past the end sits INSIDE the footprint and consumes governed length | FAA AC 150/5300-13B §3.16 (the safety area is measured from the runway end and encompasses the stopway).  User ruling 2026-07-09 — the pre-fix pavement-exit anchor extended every skirt by its blast-pad length (KCLT 18R: 429 m vs the lawful 305 m; HECA pads 59–71 m = the "~70 m too long" report) | `grade_law.runway_end_governed_length_beyond_pavement_m`, `runway_end_skirt_floor_profile_beyond_pavement`, `runway_end_skirt_profile_breakpoints_beyond_pavement`; consumers `clearance._emit_one_end` + `verification.check_runway_end_skirt` (lockstep) |
| RESA longitudinal slope cap | 5% | ICAO Annex 14 | `config.py` `RUNWAY_END_RESA_MAX_SLOPE` |
| Graded runway-strip half-width, by code | 1:30, 2:40, 3:75, 4:75 m | ICAO Annex 14 (graded portion) | `config.py` `RUNWAY_STRIP_HALF_WIDTH_BY_CODE` |
| Runway shoulder max width per side (extent-based widening cap; measured strips wider than this adjoining a runway are taxiway/apron, never shoulder) | 15 m | FAA AC 150/5300-13B / EASA CS-ADR-DSN.B.080 (runway + shoulders ≤ 75 m at code F) | `config.py` `RUNWAY_SHOULDER_EXTENT_MAX_M`; detector `pavement/runways._detect_runway_shoulder_extent`, wired in `pipeline.py` after the row-100 spec widening |

## Lateral (wingtip) clearance

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Taxiway clearance half-width | ½ wingspan + 3 m margin | FAA AC 150/5300-13 TOFA; ICAO wingspan table | `config.py` `taxiway_clearance_half_width_m()`, `TAXIWAY_WINGTIP_MARGIN_M` |
| Obstruction threshold (terrain rise above surface edge that triggers a cut) | 1.0 m (taxiway, runway & service road) | design | `config.py` `CLEARANCE_OBSTRUCTION_THRESHOLD_M` |
| Lateral strip slope | 0 (flat shadow, cut-only) | design (a non-zero slope carves canyons where pavement sits below its surroundings) | `config.py` `CLEARANCE_LATERAL_MAX_SLOPE` |
| Max outward reach (earthwork bound) | taxiway 100 m, runway 300 m | design (must exceed code-4 RESA 240 m) | `config.py` `CLEARANCE_MAX_REACH_M` |
| Service-road roadside clearance band | 15 m beyond the road edge, cut-only | **design choice, NOT an AASHTO mandate** — FAA sets no service-road grade/clear-zone numbers (width/marking only); the AASHTO Roadside Design Guide low-speed clear zone is only 2–3 m. Our 15 m band is a conservative design value (a ground-vehicle road has no wingtip envelope, so the band is the reach). Do not cite it to AASHTO as a requirement (2026-07-08 audit) | `config.py` `CLEARANCE_MAX_REACH_M["service"]`, `CLEARANCE_OBSTRUCTION_THRESHOLD_M["service"]`; walker: `clearance.emit_surface_clearance_cuts` Pass A3 |

The clearance pass is `clearance.emit_surface_clearance_cuts`: it samples the DEM inside the
protected band and cuts terrain that rises above the adjacent surface-edge altitude down to a
ramped ceiling. Terrain at or below the surface is left untouched (cut-only — we never fill).

## Single source of truth
Every grade / vertical-curve rule value is defined once in `config.py` (the named caps
above, which `ROLE_GRADE_LIMITS` also references). The solver modules import those values
and re-export them under their existing local names — there is no second copy:
- `elevation.py` `TAXI_MAX_GRADE` / `APRON_MAX_GRADE` ← `config.py`.
- `pavement/runway_segments.py` `MAX_RUNWAY_GRADE` / `RUNWAY_END_GRADE` /
  `RUNWAY_END_FRACTION` / `MAX_RUNWAY_GRADE_CHANGE_PER_M` ← `config.py`.
- `runway_regrade.py` `DEFAULT_GRADE_CAP` / `DEFAULT_ARC_K_M` ← `config.py`.
- `groundside.py` `GROUNDSIDE_MAX_GRADE` ← `config.py`.

To change a rule value, edit the constant in `config.py` only.

## Transverse (lateral / crown) grades — RESEARCHED 2026-07-07, IMPLEMENTED (part 30)

User ruling 2026-07-07: everything with a spine (runway, taxiway, service road) crowns
for drainage — spine slightly higher than the edges, per-role values. Verified from the
primary documents (FAA AC 150/5300-13B Chg 1; EASA CS-ADR-DSN Issue 7 — identical in
Issue 4; ICAO Annex 14 Vol I 7th ed.; AASHTO Green Book).  Implemented constants
(`config.py`): crown RATES `RUNWAY_CROWN_TRANSVERSE` / `TAXI_CROWN_TRANSVERSE` (1%,
gentlest-legal) and `SERVICE_ROAD_CROWN_TRANSVERSE` (1.5%); transverse LAW caps
`TAXI_MAX_TRANSVERSE_NARROW` (2%) and `SERVICE_ROAD_MAX_TRANSVERSE` (2%); gate
`ENABLE_SPINE_CROWN`.  Mechanism: `src/auto_patch/crown.py` (crown drop field + law
offsets, solver+validator lockstep) — the planned-constant names below are historical.

| Feature | Min | Max | Crowned? | Standard | Planned constant |
|------|-----|-----|----------|----------|------------------|
| Runway, AAC A–B / code A–B | 1.0% | 2.0% | Yes (center crown standard) | FAA ¶3.16.2 + Table 3-6 (S-1); CS ADR-DSN.B.080(b)(2),(c); ICAO §3.1.19 | `RUNWAY_TRANSVERSE_{MIN,MAX}_NARROW` |
| Runway, AAC C–E / code C–F | 1.0% | 1.5% | Yes | FAA Table 3-6; CS ADR-DSN.B.080(b)(1) | `RUNWAY_TRANSVERSE_{MIN,MAX}` |
| Taxiway, FAA all ADGs | 1.0% | 1.5% (1–2% if only <30,000 lb) | Yes ("ideal configuration is a center crown") | FAA ¶4.14.2(1)(a)–(c) | `TAXI_TRANSVERSE_{MIN,MAX}` |
| Taxiway, ICAO/EASA code A–B | drainage-sufficient | 2.0% | not mandated | CS ADR-DSN.D.280(b)(2); ICAO §3.9.11 | (covered by existing `TAXI_MAX_TRANSVERSE_NARROW`) |
| Taxiway, ICAO/EASA code C–F | — | 1.5% | not mandated | CS ADR-DSN.D.280(b)(1) | — |
| Apron / stand | FAA 0.5% min | ICAO/EASA 1% any direction; FAA rec. 1% stands | No (drain to inlets/edge) | FAA ¶5.9.1–5.9.2; CS ADR-DSN.E.360(b); ICAO §3.13.4–5 | (existing `APRON_MAX_GRADE`) |
| Paved service/perimeter road | 1.5% | 2.0% (2.5% intense rainfall) | Yes (normal crown) | AASHTO Green Book Ch.4 "Cross Slope" / Exhibit 4-4 (high-type 1.5–2%); TxDOT RDM §4-10-4 cross-check | `SERVICE_ROAD_TRANSVERSE_{MIN,MAX}` |
| Unpaved (low-type) road | 2% | 6% (3% desirable) | Yes | AASHTO Exhibit 4-4 | — |

Adjacent-surface values (same research, for clearance/shoulder work): runway paved
shoulder 1.5–5% (Table 3-6 S-2); RSA side slope 1.5–5% (A–B) / 1.5–3% (C–E, S-3);
taxiway shoulder + TSA 1.5–5%; unpaved strip adjacent to any paved edge 5%±0.5% for the
first 10 ft, edge drop-off 1.5in±0.5in (FAA Fig. 3-33 Detail A: 3–5% negative for 10 ft).
FAA "Table 3-7 Transverse Grades Based on ADG" is the runway OFA (S-4 ≤0%, back slopes
8:1/10:1/16:1 by ADG) — NOT taxiway pavement; FAA taxiway transverse is ADG-independent.

Notable FAA-vs-EASA deltas: FAA keys runways to AAC, EASA/ICAO to code letter (numbers
agree); FAA mandates a 1% taxiway minimum + centerline crown, EASA/ICAO have no taxiway
minimum and don't mandate crown; ICAO/EASA allow single-crossfall runways where rain-wind
justifies.

## Adjacent-ground grade law — lateral corridor off a pavement edge — RESEARCHED 2026-07-08

The LATERAL generalization of the runway-end skirt (which is the LONGITUDINAL instance of
the same idea): ground beside a paved surface is governed as a two-zone-plus-ungraded
**corridor** off the pavement edge — a signed `(floor_offset, ceiling_offset)` envelope
relative to the edge elevation, as a function of lateral distance `d`. Design, primary-
verified regulatory model and the four Noah rulings: `docs/adjacent_ground_grade_law_plan.md`.
Law function: `grade_law.adjacent_ground_envelope(role, code_number, code_letter, d)`
(pure; the bounds ACCUMULATE across zones so they are continuous in `d`). Verified from
FAA AC 150/5300-13B w/ Chg 1, ICAO Annex 14 Vol I 8th ed., EASA CS-ADR-DSN Issue 7
(ICAO/EASA strip text is word-identical).

**Ruling 1 (ENFORCE FULLY):** each graded zone is a mandatory-DOWN band `[min, max]` with
direction, exactly as the FAA writes it — a FLAT surround (offset 0) is OUTSIDE the corridor
in a down-mandatory band, so flat surrounds beside pavement are regraded to at least the
minimum fall. Where FAA mandates DOWN and ICAO merely permits UP, FAA wins (maximal
conformance; one blended global ruleset).

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Drainage lip width (zone 1, runway & taxiway strips) | 3 m (10 ft) | FAA AC 150/5300-13B Fig 3-33 Detail A; §4.14.2 (first 10 ft) | `config.py` `ADJACENT_GROUND_LIP_WIDTH_M` |
| Drainage lip transverse slope (mandatory DOWN) | 3–5% down | FAA Fig 3-33 Detail A (3–5% negative for 10 ft); FAA TSA 5%±0.5% (§4.14.2); ICAO Annex 14 §3.4.15 (negative ≤5%) | `config.py` `ADJACENT_GROUND_LIP_{MIN,MAX}_DOWN_SLOPE` |
| Runway graded strip — transverse fall (zone 2) | min 1.5%; max 3% (code 3/4 ≈ AAC C–E) / 5% (code 1/2 ≈ AAC A/B) | FAA AC 150/5300-13B Table 3-6 S-3 (RSA side slope 1.5–5% A/B, 1.5–3% C–E; FAA has a 1.5% MINIMUM, ICAO none); ICAO Annex 14 §3.4.15 | `config.py` `RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE`, `RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE` |
| Runway graded strip — width (zone-2 outer bound) | 30 / 40 / 75 / 75 m by ICAO code number | ICAO Annex 14 §3.4.8–9 (graded portion) — **reuses** the strip half-width, no duplicate | `config.py` `RUNWAY_STRIP_HALF_WIDTH_BY_CODE` (existing) |
| Taxiway graded strip — transverse fall (zone 2) | 1.5–5% down (UP ≤2.5% C–F / 3% A/B) | ICAO Annex 14 §3.11.5 / EASA CS-ADR-DSN.D.280; FAA TSA 1.5–5% (§4.5.3, §4.14.2) | `config.py` `TAXIWAY_STRIP_BAND_{MIN,MAX}_DOWN_SLOPE` |
| Taxiway graded strip — width (OMGWS-derived, by code letter) | A 10.25 / B 11 / C 12.5 / D 18.5 / E 19 / F 22 m | ICAO Annex 14 §3.11.4 / EASA CS-ADR-DSN.D.325(b) (OMGWS <4.5 / 4.5–6 / 6–9 m → 10.25/11/12.5; D/E/F → 18.5/19/22) | `config.py` `TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER`, `taxiway_strip_graded_half_width_for_letter()` |
| Ungraded strip (zone 3) — rising-ground cap; NO downward mandate | ceiling ≤5% UP; floor unbounded (cliffs lawful) | ICAO Annex 14 §3.4.16 (runway strip) / §3.11.6 (taxiway strip) — open channels / drops permitted only in the non-graded strip | `config.py` `ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE`; floor `None` in `grade_law.adjacent_ground_envelope` |
| Adjacent-ground outward reach (earthwork bound) | runway 300 m / taxiway 100 m | design (must exceed code-4 RESA 240 m) — **reuses** the clearance reach | `config.py` `CLEARANCE_MAX_REACH_M` (existing) |
| Apron shoulder (the only governed band beyond an apron edge) | 3 m at 1–3% down | FAA AC 150/5300-13B §5.9.2 (10 ft shoulder at 1–3%) — a RECOMMENDATION, not a requirement; no code mandates grading beyond an apron edge | `config.py` `APRON_SHOULDER_WIDTH_M`, `APRON_SHOULDER_{MIN,MAX}_DOWN_SLOPE` |
| Apron beyond-shoulder fill render target (zone-3 free-floor region) | 3–5% down | FAA AC 150/5300-13B §5.9.2 ("then 3–5% beyond") — a render target, not a corridor | `config.py` `APRON_BEYOND_SHOULDER_{MIN,MAX}_DOWN_SLOPE` |
| Apron edge retaining-wall threshold | 1.5 m drop below the shoulder edge | design (ruling 3; grade-to-edge + vertical drop/retaining wall is lawful where no RSA/OFA/TOFA overlaps — reuse the tunnel `retaining_wall` emitter) | `config.py` `APRON_EDGE_WALL_MIN_DROP_M` |
| Apron wall / shoulder SCOPE — pavement adjacency | wall (and shoulder fill band) only where another built pavement lies within 5 m; open-terrain apron frontage is ungoverned on the FILL side (raw DEM grades to the apron edge). CUT side unaffected. | design — owner ruling 2026-07-25 (lead reading, stated back for confirmation): "narrowing the scope of apron walls so that they only occur if there's adjacent pavement within 5m … if it's open terrain just let the raw Ortho4XP dem grade up to the apron edge". Lawful because no code mandates grading beyond an apron edge (the 3 m shoulder is an FAA *recommendation*). | `config.py` `APRON_WALL_PAVEMENT_ADJACENCY_M`, gate `APRON_WALL_SCOPE_ENABLED`; emitter + validator share `adjacent_ground.apron_wall_frontage_qualifier` |
| Apron wall run — continuation hysteresis | run STARTS above 1.5 m, CONTINUES down to 1.5 − 0.3 m | design (ruling 3 companion; owner in-sim "ramps and sharp drops" 2026-07-25 — SPJC stations at 1.4988/1.4936 m split one 237 m frontage into two runs with a bare notch between; the wall's EXISTENCE decision stays at the ruled threshold, only its continuation is tolerant) | `config.py` `APRON_WALL_RUN_HYSTERESIS_M`, gate `APRON_WALL_CONTINUITY_ENABLED` |
| Apron wall part — minimum emitted run / area | 6 m along the frontage, 4 m² | design (ruling 3 companion, same report): the clip residue of a wall run is now emitted multipart-safe, so genuinely tiny lobes must be gated — a shorter face protects nothing a neighbouring band does not already cover and reads in-sim as a spike triangle; skipped pieces are counted, never silently capped | `config.py` `APRON_WALL_MIN_RUN_M`, `APRON_WALL_MIN_AREA_M2` |
| Edge drop-off tolerance, pavement↔unpaved | 1.5 in ± 0.5 in | FAA (all pavement types); ICAO "flush" (§3.4.10) | (documented; enforced via the flush edge = lip start) |
| Adjacent-ground daylight slope-limit (along-frontage benching) | governed depth grows ≤2.0 × the along-frontage station spacing | engineering judgment — NO external citation (grading benches into a hillside; the daylight line cannot jump discontinuously along the frontage); user ruling 2026-07-09 (CYXY shapeID 417 knife-slot report) | `config.py` `ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`; law `grade_law.adjacent_ground_supported_depths` (emitter + validator lockstep) |

Runway ENDS are OUT OF SCOPE of this lateral law — the longitudinal runway-end law
(`grade_law.runway_end_envelope`, both bounds: the skirt floor for falling terrain and
the RESA ceiling for rising terrain) owns terrain beyond a runway end. Service roads
keep the unchanged 15 m cut-only flat shadow (see the corrected note in "Lateral (wingtip)
clearance" — a design choice, not an AASHTO mandate).

## Obstacle limitation surfaces — terrain cut — RESEARCHED 2026-07-24

Design + slice plan: `docs/specs/obstacle-limitation-surfaces-spec.md` (gap-audit GAP 1).
This is the CONTINUATION of the adjacent-ground zone-3 ceiling and of the runway-end
corridor: where those laws stop, the OLS transitional and approach surfaces bound how
high terrain may stand.

An OLS is an **obstacle** limitation surface. The codes forbid new obstacles above it and
require assessment of existing ones; they do **not** mandate grading terrain down to it
(terrain penetrations are handled procedurally, via PANS-OPS and the AIP). Cutting terrain
to it is therefore a deliberate scenery-repair reinterpretation — the same framing as the
runway-end skirt — and that is why only two surfaces are modelled and why the
inner-horizontal and conical surfaces are refused as cut surfaces.

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Ruleset adoption | classic Annex 14 Table 4-1. NOT FAA Part 77 §77.19 (a *notification* surface set — weaker near-field: approach 34:1 = 2.94% vs ICAO 2%). NOT Amendment 18's ADG-keyed OFS/OES (applicable 2028-11-26; the repo has no ADG plumbing) — **WATCH item** | ICAO Annex 14 Vol I 8th ed Ch 4; 14 CFR §77.19; ICAO SL AN 4/1.2.31-25/23 | gate `config.OLS_CUT_ENABLED` |
| Transitional surface slope | 14.3% (1:7); 20% (1:5) for non-instrument / non-precision code 1–2 | ICAO Annex 14 Table 4-1 | `config.py` `OLS_TRANSITIONAL_SLOPE`, `OLS_TRANSITIONAL_SLOPE_STEEP`; `grade_law.ols_transitional_slope` |
| OLS strip half-width (the line the transitional rises from) | instrument 140 m (code 3/4) / 70 m (1/2); non-instrument **reuses** 30/40/75/75 | ICAO Annex 14 §3.4.3–3.4.4 — the FULL strip, not the graded portion; §3.4.4 == §3.4.9 widths for non-instrument, so no duplicate constant | `config.py` `OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE` + existing `RUNWAY_STRIP_HALF_WIDTH_BY_CODE`; `grade_law.ols_strip_half_width_m` |
| Transitional anchor (the continuity ruling) | the adjacent-ground zone-3 ceiling VALUE at the handover distance S | design ruling (spec): guarantees an exactly continuous composed ceiling — a step between two active cut bands mints a wall. Sits ≤~2 m below the Annex nearest-centreline datum ⇒ stricter ⇒ lawful-conservative | `grade_law.ols_transitional_ceiling` (shares `_adjacent_strip_envelope` with the lateral law) |
| Approach surface — first section only | inner edge half-widths: non-instr 30/40/75/75; NPA & precision 75/75/150/150 m. Setback 60 m (30 m non-instr code 1). Divergence 10% non-instr / 15% instrument. Slope: non-instr 5/4/3.33/2.5%; NPA 3.33/3.33/**2**/**2**%; precision 2.5/2.5/2/2% | ICAO Annex 14 Table 4-1. ICAO's 300 m NPA 3/4 inner edge adopted over EASA CS-ADR-DSN.H's 280 m (wider = stricter for a cut law); EASA equivalence otherwise assumed, still not primary-verified | `config.py` `OLS_APPROACH_*`; `grade_law.ols_approach_ceiling` |
| Approach anchor elevation | the SOLVED runway-end elevation | Annex 14 puts the inner edge at the threshold; a displaced threshold makes our anchor farther out along the same rising surface ⇒ our ceiling is lower ⇒ conservative. Matches the skirt/RESA anchor discipline | `ols.py` emitter + `verification.check_ols_surfaces` (shared) |
| Surfaces deliberately NOT cut | inner horizontal, conical, take-off climb, the OFZ set, approach 2nd/horizontal sections | Annex 14 Table 4-1 — these are obstacle surfaces; terrain penetrations are lawfully *assessed*, not graded away. As cuts, inner-horizontal + conical decapitate every hill within 4 km above +45 m (at SPLP, a mountain range) | spec §"scope ruling" |
| Mountain refusal | a contiguous penetration island needing >15 m of cut anywhere emits NOTHING | design — NO citation. Shaving a real mountain's fringe while leaving its core sculpts a moat; the charter is DEM-artefact repair (5–15 m lumps), not obstacle removal | `config.py` `OLS_MAX_CUT_DEPTH_M`; `grade_law.ols_island_refused` (emitter + validator lockstep) |
| Emission reaches / cut trigger | transitional 300 m past the handover; approach 1000 m past the inner edge; trigger 1.0 m | design (earthwork + visual-blast-radius bounds, the `CLEARANCE_MAX_REACH_M` philosophy) — NOT regulatory lengths. Table 4-1's 3000 m first section is a *law* length, not a cut reach | `config.py` `OLS_TRANSITIONAL_EMIT_REACH_M`, `OLS_APPROACH_EMIT_REACH_M`, `OLS_OBSTRUCTION_THRESHOLD_M` |

**Correction logged 2026-07-24:** `docs/grade_law_gap_audit.md` GAP 1 previously recorded
the approach first-section slope as "3.33% (NPA 3/4)" with a 60–280 m inner edge. NPA code
3/4 is **2%** (the same as precision 3/4); 3.33% is NPA code **1/2**, and 280 m is EASA's
figure where ICAO gives 300 m. Corrected in that file and tabled correctly above.

## End-around taxiway (EAT) departure-surface ceiling — owner ruling 2026-07-27

An **end-around taxiway** loops beyond a runway end and crosses the extended
centreline, so an aircraft taxiing there stands directly under the departure /
take-off-climb surface. The surface must clear the aircraft's **tail**, which forces
the EAT **pavement** *below* the runway-end elevation — KATL taxiway Victor runs
~30 ft (≈9 m) below its runway end for exactly this reason.

This is the **first grade law that binds taxi PAVEMENT to a runway-end surface**.
The OLS section above is a *terrain-cut* law and lists the take-off climb surface
among the surfaces deliberately **not** cut; that ruling is about terrain and is
unchanged. This law is a different object: a ceiling on our own paved geometry, so
the taxiway we build is one an aircraft can actually use.

Ruleset selection is by region (owner ruling): **FAA for North America, EASA
everywhere else**, decided from the ICAO location-indicator first letter.

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Ruleset by region | ICAO prefix `K`/`C`/`P`/`M` (USA, Canada, US Pacific, Mexico–Central America) ⇒ FAA; everything else ⇒ EASA. Unknown/blank ⇒ EASA (the stricter ceiling beyond ~240 m) | owner ruling 2026-07-27 | `config.py` `eat_surface_slope_and_setback()`, `EAT_FAA_ICAO_PREFIXES` |
| FAA departure surface | 40:1 (**2.5%**) rising **from the DER at DER elevation**, setback **0** | FAA AC 150/5300-13B §4.12; FAA Order 8260.3 (TERPS) departure surface | `config.py` `EAT_FAA_DEPARTURE_SLOPE`, `EAT_FAA_SETBACK_M` |
| EASA take-off climb surface (code 3/4) | **2%** from a **60 m** inner edge beyond the runway end | EASA CS-ADR-DSN H.435 / Table J-2; CS-ADR-DSN J.480(e) | `config.py` `EAT_EASA_TAKEOFF_CLIMB_SLOPE`, `EAT_EASA_SETBACK_M` |
| Max EAT pavement elevation | `end_elev + max(0, D − setback)·slope − tail_height` (D = distance beyond the runway end along the extended centreline) | the two rows above + Table 1-1 tail heights; the tail is what penetrates, not the wingtip | `grade_law.eat_pavement_ceiling()` |
| Tail height by code letter | A 6.1 … F 24.4 m | FAA AC 150/5300-13B Table 1-1 (see *Aerodrome reference code* above) | `config.py` `TAIL_HEIGHT_BY_CODE_LETTER` |
| Anchor point / elevation | the apt.dat **row-100 endpoint** (the DER), at the end's **SOLVED** profile elevation read through its frozen-nearest pavement ring vertex — never a DEM read | FAA §4.12 / CS-ADR-DSN J.480(e) both measure from the runway end; the solved-elevation anchor matches the skirt / RESA / OLS-approach discipline | `clearance.emit_runway_end_skirts` publishes `layout.eat_ceiling_presolve`; `solver_primitives._build_eat_ceiling_constraints` + `verification.check_eat_ceiling` consume it (lockstep, via `solver_primitives.eat_ceiling_offset`) |
| Scoping — minimum crossing distance | **300 m** beyond the end | design, NOT regulatory. Taxi pavement closer than this is an ordinary runway-end connector, and the ceiling there is violently infeasible (−18.6 m at 60 m for a code-E tail). A real EAT crosses hundreds of metres out — KCLT's 18C loop at 439–482 m | `config.py` `EAT_MIN_CROSSING_DIST_M` |
| Scoping — corridor half-width | **90 m** about the extended centreline | design, NOT regulatory. A single conservative constant instead of the surface's true splay (a refinement); wider than the code-4 graded strip (75 m), narrow enough to leave the flanking apron/taxi network alone | `config.py` `EAT_CORRIDOR_HALF_WIDTH_M` |
| Enforcement | ONE one-sided solver interval edge per governed pavement node to the end's anchor node (`z_node − z_end ≤ ceiling`); the floor side is OPEN and no ramp geometry is stamped — the grade caps and smoothest target produce the descent/climb ramps | design (the RESA B3 band template, inverted: this law *deliberately* constrains pavement variables) | `solver_primitives._build_eat_ceiling_constraints`, wired in `elevation_per_surface/route_profile/solve.py`; gate `config.EAT_SURFACE_CEILING_ENABLED` (`O4_EAT_SURFACE_CEILING`) |

> **Gate state: DEFAULT OFF (2026-07-27) — build-time blocker, not a design doubt.**
> The law, its encoding, its scoping and its reader are complete and unit-proven
> (`tests/test_eat_ceiling.py`, including a projection test showing the pavement driven
> from +0.9 m to a full tail height under the surface). What is unsolved is the
> reach-envelope interaction. Measured at KCLT: **228.9 s** with the ceiling constraints
> neutered, versus a build **killed at 15:02 of CPU and 20.3 GB RSS** with them active,
> `sample(1)` showing ~100 % of the time in `heapq.heappop`/`siftup` inside
> `one_solve.feasibility_project`'s `_reach` Dijkstra.
>
> This is the documented KBNA class (`one_solve.py`, "ENVELOPE EXCLUSION FOR ZONE
> EDGES"): a signed slab injects negative directed weights into `ceil_radj`, and `_reach`
> is a lazy Dijkstra. Adjacent-ground zone slabs escape it via the `interval_yield_from`
> **index threshold** — but an EAT ceiling couples *pavement to pavement*, so both
> endpoints sit below that threshold and the exclusion cannot fire. No reorientation of
> the slab helps: a ceiling below its anchor *is* a negative ceiling-propagation weight.
>
> Unblocking fix (owner call — it changes a shared solver file): give
> `feasibility_project` an explicit per-edge "envelope leaf" marker instead of the index
> threshold, so the EAT slabs are excluded from the envelope adjacency the way the zone
> slabs are. Then flip the default and re-measure KCLT.
