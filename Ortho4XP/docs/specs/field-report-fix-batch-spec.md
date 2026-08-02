# Field-report fix batch: walls, drainage, lateral pricing, coverage

Fable spec, 2026-08-02. One batched round, four class-disjoint fixes,
each behind its own gate, one artifact regeneration, one battery — per
the batching policy. Line numbers against `ceef13f`. BINDING:
docs/RULINGS.md. Every fix's mechanism is attributed in the referenced
investigation reports (scratchpad dirs) — read each before its section.

## §A Runway-strip wall inadmissibility (owner: "never at runways")
Evidence: `standards_gap/`. Gate `O4_RUNWAY_STRIP_WALL_LAW`, default "0".
1. A strip-footprint predicate: inside runway CL ±
   `RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code]` (plus the end corridor per
   `runway_end_corridor_half_width_m`), `ROLE_RETAINING_WALL` is
   INADMISSIBLE: all three wall emitters (`_emit_apron_walls`
   adjacent_ground.py:5942, `emit_stacked_conflict_walls` :1781,
   `emit_groundside_terrace_walls` :2317) skip faces there; remove
   `_RUNWAY_ROLES` from `_WALL_SCOPE_PAVEMENT_ROLES` (:380) so a runway
   never QUALIFIES a wall.
2. The displaced drop relocates lawfully: the strip corridor law
   already grades to the 75 m edge; beyond it zone-3's free floor makes
   the terrace lawful (adjacent-ground zone law). No new corridor math.
3. New validator check `check_no_wall_in_runway_strip` (wall vertices
   inside any strip footprint = violation), on in the law-true frame.
Pre-registered: HECA wall-in-strip ways 4 → 0 (the 19 vertex sites);
no other airport regresses (0 elsewhere today); the strip band beside
05R/23L re-grades inside its own corridor law; runway profiles untouched.

## §B Drainage-spine law (owner: below the lower adjacent pavement)
Evidence: `drainspine/`. Gate `O4_DRAINAGE_SPINE_LAW`, default "0".
1. New lockstep law function beside `adjacent_ground_envelope`
   (grade_law.py): for an ENCLOSED interior between two pavements, the
   spine ceiling = `min(edge₁, edge₂) − DRAINAGE_SPINE_MIN_FALL_M`
   (new constant, PROVISIONAL 0.30 m — owner may move it), floor = the
   existing corridor floors (bounding BOTH directions — the old arm's
   −17.7 m craters must stay impossible). Consumed by
   `_spine_interval` (gap_fill.py:658-698) AND
   `_freeze_spine_parent_specs` (:2154) — one law, both readers.
2. Post-projection re-clamp: the gap-spine writeback freezes against
   pre-projection pavement (solve.py:3253-3270) and the final passes
   then move the pavement; re-reference the spine after the late pass
   (the foot re-reference pattern the zone rows already use,
   solve.py:3299 ff.) or re-clamp — implementer picks the one that
   composes with the existing machinery and says why.
3. Validator: `check_grade` currently SKIPS `gap_drainage_spine` ways
   (check_grade.py:154-162). Keep the ring-skip, add the real check:
   spine vertex z < min(adjacent pavement edges) − 0 (flag any
   at-or-above); report against the law's fall constant separately.
Pre-registered: HECA 182 at/above-lower vertices → 0; 21 blocking
spines → 0; no vertex below the corridor floor (crater guard); the
owner's site cross-section drains monotonically to the spine.

## §C Lateral pricing + transverse visibility
Evidence: `lateral/`. Two solver defects + one validator promotion.
Gate `O4_ROUTE_LEG_EXACT`, default "0", covers 1+2 (they compose).
1. `_RouteDistanceOracle._nearest` (grade_graph.py) attaches to the
   nearest POINT ON the centreline polyline (segment projection), not
   the nearest graph vertex. (440/692 HECA axes are 2-point polylines;
   vertex attachment minted phantom off-spine legs p90 77.5 m, max
   454.5 m; the owner's on-centreline vertex was charged 190 m.)
2. `_route_leg_floor` (grade_graph.py:1166, applied :1597-1601) regains
   the chord gate its predecessor had: pairs with chord ≤ 120 m keep
   the chord law (constant named, cited to the ds_decompose docstring
   principle: local pairs on continuous pavement are chord-priced).
3. Validator: promote the transect instrument
   (`scratchpad/lateral/transect.py`) into `check_grade` as
   `check_transverse_grade`: perpendicular transects at 10 m stations
   over the sidecar axes, threshold = the existing isotropic transverse
   cap for the role/letter (config.py:644-650 semantics; the nominal
   1.5% at C-F finally gets an unconditional reader). Always-on in the
   law-true frame (it is a READER; the law already exists).
Pre-registered: the owner's pair allowance 6.201 → ~0.573 m and the
10.9% pair FLAGS; baked-cap inflation census (29.6% of caps >2× flat
law) collapses to near-zero >2× except genuinely-far pairs; the
transect census's 2,973 ≥1.5% stations become visible rows (the
actionable number RISES again — that is the owner's honest-count law,
state it in the report, never soften it).

## §D Coverage: the dead guard + the H1 attribution
Evidence: `gsclass/` §§5-6. No gate needed for 1 (a probe) — 2 is
gated `O4_SOURCE_COVERAGE_CHECK`, default "0" this round.
1. ATTRIBUTION FIRST (one build): run the coverage probe
   (`O4_COVERAGE_PROBE="30.1064235,31.3992159"`, the 9-stage hook) and
   NAME the pass that deletes H1's 90.8 m². If the mechanism is an
   obvious min-area/fragment-drop threshold acting on a fully-enclosed
   interior piece, fix it in this round (cite the site); if it is
   design-intentional, STOP and report for a ruling.
2. Wire `verification.check_source_coverage()` (verification.py:302 —
   currently ZERO call sites) into the build's verification pass under
   the gate: source pavement minus emitted union, pieces ≥5 m² with
   ≥70% enclosed boundary = loud build-time failure listing pieces.
Pre-registered: the probe names one pass; with its fix, H1 + the
839.9 m² hole + the two smaller flagged holes emit pavement (4 → 0
flag-worthy holes at HECA); the wired check passes on all five
airports afterward (or its failures are named source-data gaps like
H2, reported not failed — distinguish by the H2 rule: no substrate
record ⇒ not a coverage loss).

## NOT in this batch
The scorer service-adjacency feature (§the absorption ruling is DRAFT —
implementation waits for the owner's text confirmation); quarantine
round 2 (the 287 remaining minters, the HEAZ inverted-band 6, the
service second-envelope engine — own spec, also gated on that ruling);
the ruleset architecture (phases A/B, own spec); standards gaps G-2..G-14.

## Acceptance
Per-fix pre-registrations above, plus: gate-off byte identity (CYXY
`dcebb6ff…`, SPLP `c2316222…`, HECA repaired `9a49cbce…`); all-gates-on
HECA+HEAZ arms with full census + check_grade both quoted (two frames,
never merged); no regression at any of the owner's five reference
coordinates (the four field-report sites + the example intersection);
suite green over the same 23 known reds; build-time per phase ledger
(the transect check and coverage check run in the validator, not the
build — their cost lands on check_grade wall time, quote it).
