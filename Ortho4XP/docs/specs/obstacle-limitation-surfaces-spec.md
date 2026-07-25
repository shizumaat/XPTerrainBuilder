# Obstacle Limitation Surfaces (OLS) — terrain-penetration cut law (Fable design, 2026-07-24)

ORIGIN (owner session 2026-07-24, SPJC 16R): beyond the runway end, terrain
rises to 10.8 m against a ~6.2 m runway-end elevation, at 100–160 m off the
extended centreline and 170–300 m beyond the end.  That is outside the 75 m
graded-strip corridor (`config.RUNWAY_STRIP_HALF_WIDTH_BY_CODE`), outside the
RESA/skirt footprint (the fill law in `grade_law`; the A2 cut twin
`RUNWAY_END_RESA_ENABLED` governs only the RESA corridor), and beyond every
reach any current pass marches — so nothing touches it.  It is textbook
approach-surface / transitional-surface territory.  This arc is gap-audit
**GAP 1** (`docs/grade_law_gap_audit.md`) and the ruled FOLLOW-ON of the
adjacent-ground law (`docs/adjacent_ground_grade_law_plan.md`, sequencing
decision 4: "OLS … is the FOLLOW-ON arc reusing this envelope machinery —
zones 1-3 here, the transitional/approach/conical surfaces next").
`config.py` already points here: zone 3's outer-bound comment ("beyond it …
the OLS transitional surface takes over").

## The regulatory model
## (researched 2026-07-24, primary-verified: ICAO Annex 14 Vol I 8th ed
## Table 4-1 + §3.4.3-4; cross-checked against IAA ASAM 014 Issue 3 and the
## 2026-07-08 gap audit)

An OLS is an **obstacle** limitation surface: the codes forbid new obstacles
above it and require assessment of existing ones — they do NOT mandate grading
terrain down to it (Annex 14 §4.2; existing terrain penetrations are handled
procedurally via PANS-OPS and the AIP).  Our cut law is therefore a deliberate
scenery-repair reinterpretation, exactly like the skirt: where the DEM
(frequently a surface-model artefact) pokes through the surface a real
aerodrome keeps clear, we cut it back.  That framing drives every scope
decision below.

The classic Annex 14 surface set, keyed by code number + approach class:

- **APPROACH surface** — inner edge perpendicular to the extended centreline,
  at threshold-midpoint elevation:
  * Non-instrument: inner edge 60/80/150/150 m wide (code 1/2/3/4), setback
    30 m (code 1) / 60 m, divergence 10 % each side, first section
    1 600/2 500/3 000/3 000 m at slope **5 / 4 / 3.33 / 2.5 %**.
  * Non-precision code 1/2: inner edge 150 m, setback 60 m, divergence 15 %,
    first section 2 500 m at **3.33 %**.
  * Non-precision code 3/4 and precision CAT I/II/III code 3/4: inner edge
    **300 m**, setback 60 m, divergence 15 %, first section 3 000 m at
    **2 %**, second section 3 600 m at 2.5 %, horizontal section 8 400 m
    (total 15 000 m).  Precision CAT I code 1/2: inner edge 150 m, first
    section 3 000 m at 2.5 %, second 12 000 m at 3 %.
  * ⚠ **Correction to the gap audit's compressed line** ("3.33 % (NPA 3/4)"):
    NPA code 3/4 first section is **2 %**; 3.33 % is NPA code **1/2**.
  * ⚠ EASA CS-ADR-DSN.H gives NPA 3/4 inner edge 280 m vs ICAO's 300 m; adopt
    ICAO 300 m (wider = stricter for a cut law).  EASA equivalence otherwise
    assumed-identical — still not primary-verified (carried flag from the gap
    audit).
- **TRANSITIONAL surface** — rises from the side of the STRIP (and the
  approach-surface edges) up to the inner horizontal: slope **14.3 % (1:7)**
  for all classifications except non-instrument/non-precision code 1/2 at
  **20 % (1:5)**.  Lower edge along the strip sits at the elevation of the
  nearest centreline point; the strip half-width for OLS purposes is the FULL
  strip: instrument 140 m (code 3/4) / 70 m (1/2); non-instrument 75/40/30 m
  (Annex 14 §3.4.3–3.4.4) — NOT the 75 m graded portion the repo already
  models.
- **INNER HORIZONTAL** — 45 m plane, radius 2 000–4 000 m by code/class.
  **CONICAL** — 5 % from its rim, rising 35–100 m.  **TAKE-OFF CLIMB** —
  inner edge 180 m (code 3/4), divergence 12.5 %, 15 000 m at 2 %.
  **OFZ set** (inner approach / inner transitional / balked landing) —
  navaid-frangibility control inside the strip.
- **FAA Part 77 §77.19** — the notification surface set (approach 34:1 NPA /
  50:1 precision, horizontal 150 ft/10 000 ft, transitional 7:1).  Near the
  runway, ICAO Table 4-1 is equal (transitional 1:7) or stricter (approach
  2 % vs 34:1 = 2.94 %), so under the repo's "one blended ruleset, the
  stricter code wins" convention the blend near-field IS ICAO Table 4-1.
  Part 77 exists to trigger obstruction evaluation, not to bound aerodrome
  construction — wrong instrument for a cut law (concurring with the gap
  audit's ruling).
- **ICAO Amendment 18 (2025)** replaces this entire classic set with
  ADG-keyed OFS/OES surfaces (applicable 2028-11-26).  The repo has no ADG
  plumbing, EASA/FAA and the world's built airports remain on the classic
  geometry, and the classic set is what the 2026-07-08 audit verified.  Adopt
  classic Table 4-1; record Amendment 18 as a WATCH item in
  `docs/STANDARDS.md`.

### Scope ruling — what a TERRAIN GRADER implements (decisive)

Implement exactly TWO surfaces, cut-only:

1. **The lateral transitional surface** (14.3 % / 20 % by class+code), as the
   continuation of the adjacent-ground zone-3 ceiling — the lawful rising
   model the zone-3 comment already promises.
2. **The approach surface, first section only** (slope by class+code, splayed
   fan off each runway end) — the surface that actually governs the SPJC 16R
   terrain: at 170–300 m past the end the 2 % precision ceiling is ~8.4–11.0 m
   over a 6.2 m end; the 10.8 m knoll penetrates by up to ~2.4 m at 100–160 m
   off-centreline, inside the ±150 m→186 m fan.

REJECTED, with reasons stated once here:

- **Inner horizontal + conical**: as cut surfaces they decapitate every hill
  within 4 km above +45 m — at SPLP (Andes fixture) that is a mountain range.
  Real aerodromes in terrain operate with assessed OLS penetrations; scenery
  must keep the mountains.  Never implement as cuts.
- **Take-off climb**: at instrument code 3/4 ends its 2 % slope equals the
  approach's, its inner edge (180 m) is narrower than the approach's (300 m),
  and its divergence is smaller — near-field the approach fan subsumes it.
  The only place it is stricter is a code 3/4 VISUAL end (2 % vs 2.5–3.33 %) —
  rare enough to defer; the law function is keyed so a TOCS min-in can be
  added without re-architecture.
- **OFZ set**: inside the strip, where the strip/graded-band law and the
  runway itself already govern terrain.
- **Approach second/horizontal sections** (3.6–15 km): beyond any sane
  emission reach for a per-airport patch (see build-time law); beyond ~1 km
  the ceiling exceeds +20 m and DEM-artefact terrain has daylighted.
- **PAPI OCS / GS reflection plane**: gap-audit GAPs 9/2, separate arcs.

## THE LAW (single source, `grade_law.py` — pure, scalar, no geometry deps)

Three new pure functions beside `adjacent_ground_envelope`, same conventions:
offsets in metres, signed, positive above the anchor; `None` = unbounded / not
this law's domain.  There is NO floor anywhere in this law — OLS is cut-only
by construction.

```python
def ols_lateral_handover_distance_m(
        code_number: int, approach_class: str,
        edge_to_centerline_m: float) -> float:
    """S — the from-EDGE distance where the adjacent-ground lateral law
    hands over to the OLS transitional: the OLS strip half-width
    (instrument 140/140/70/70, non-instrument 75/75/40/30 m from the
    CENTERLINE; Annex 14 §3.4.3-4) minus the station's edge->centreline
    distance, floored at the graded band width W so the transitional can
    never start inside a still-graded zone 1-2 (pre-A4 edge-measured
    overrun, config.STRIP_WIDTH_FROM_CENTERLINE_ENABLED)."""

def ols_transitional_ceiling(
        code_number: int, approach_class: str,
        distance_from_pavement_edge_m: float,
        edge_to_centerline_m: float) -> Optional[float]:
    """Ceiling offset vs the pavement-EDGE elevation of the composed
    lateral law beyond the handover S: continues the zone-3 ceiling VALUE
    at S (computed via the same _adjacent_strip_envelope helper — the join
    is exact by construction, no step), rising at the transitional slope
    (0.143; 0.20 for visual/NPA code 1-2).  None for d < S (adjacent-ground
    territory) and for d >= S + OLS_TRANSITIONAL_EMIT_REACH_M (emission
    bound; ungoverned)."""

def ols_approach_ceiling(
        code_number: int, approach_class: str,
        distance_beyond_runway_end_m: float,
        offset_from_extended_centerline_m: float) -> Optional[float]:
    """Ceiling offset vs the RUNWAY-END elevation of the approach first
    section: None inside the setback (30/60 m), outside the lateral splay
    |offset| > inner_half + divergence * (s - setback), or beyond
    OLS_APPROACH_EMIT_REACH_M; else slope * (s - setback).  Flat
    transversely (Annex 14: slopes measured in the vertical plane through
    the centreline).  Anchored at the SOLVED runway-end elevation (the
    surface the patch renders — the skirt's anchor discipline); a displaced
    threshold makes this strictly conservative (our inner edge sits farther
    out => lower ceiling)."""
```

**CONTINUITY RULING (the handover, decisive).**  The composed lateral ceiling
must be continuous in `d` — a jump between two active cut bands mints a wall.
Chosen design: **anchor the transitional at the zone-3 ceiling value at S,
and under the gate shrink the runway-family adjacent-ground reach from
`CLEARANCE_MAX_REACH_M["runway"]` (300 m) to S.**  The composed ceiling is:
corridor zones 1–2 → zone-3 +5 % on [W, S] → transitional 14.3 %/20 % from
C(S) — continuous everywhere, upward slope kink at S, monotone.  This is also
the legally correct shape: §3.4.16's ≤5 % governs the UNGRADED STRIP, i.e.
exactly [W, S], and today's 5 % march to 300 m was only ever a stand-in
because nothing governed beyond.

Two rejected alternatives: (a) anchor the transitional at the 300 m reach-cap
endpoint — continuous but uniformly ~15 m stricter than Annex geometry at
range, over-cutting legally-clean hills forever outward; (b) anchor at the
true Annex datum (nearest centreline elevation at S) — regulation-exact but
steps 1–2 m against the existing corridor at S (the accumulated zone-1/2 down
offsets), the exact wall class the weld ruling exists to prevent.  The chosen
anchor is ≤~2 m BELOW the Annex datum = stricter = lawful-conservative.

Consequences of the reach shrink (gate-on only): terrain in [S, 300 m] between
the 5 % and 14.3 % lines that today's zone-3 band cuts becomes LAWFUL and is
left alone — the flip makes runway flanks LESS aggressively cut (an accuracy
improvement; A/B'd in slice 3).  Taxiway/apron families are untouched — OLS
attaches to runways only.  `adjacent_ground_envelope` itself is NOT modified;
the emitter and validator pass an explicit `reach_override_m = S` for
runway-family stations when the gate is on (both read `config.OLS_CUT_ENABLED`
— lockstep; law-off byte-identical).

**Corner composition**: alongside the runway the transitional governs; beyond
the end the fan governs; the emitted ceiling anywhere both claim is `min()`.
The Annex's transitional-along-the-approach-edge (the corner wedge between
flank and fan, incl. the 140 m→150 m inner-edge jog) is approximated by that
min-composition; the residual wedge is REPORT-ONLY in the validator
(documented simplification).

**DAYLIGHT + BENCH COUPLING**: both surfaces reuse
`grade_law.adjacent_ground_supported_depths` verbatim over their own station
sequences — the blade-killer benching law is already the shared
emitter/validator lockstep contract; OLS inherits it rather than minting a
second one.

**MOUNTAIN REFUSAL (new law rule)**: a contiguous penetration island whose
required cut depth exceeds `OLS_MAX_CUT_DEPTH_M` anywhere is REFUSED WHOLE (no
cut emitted; forensics line logged).  Cutting the fringe of a real mountain
while leaving its core would sculpt a moat; the charter is DEM-artefact repair
(5–15 m lumps), not obstacle removal.  SPLP's Andes flanks refuse; SPJC's
2.4 m knoll (max cut ≪ 15 m) cuts.  The validator recomputes the same refusal
from the same law + DEM and exempts refused islands (lockstep, same pattern as
the supported-depths exemption).

## Constants (`config.py` — the rule VALUES; law math stays in `grade_law`)

```python
# ── Obstacle limitation surfaces — terrain-penetration CUT law ──
# (docs/specs/obstacle-limitation-surfaces-spec.md; gap-audit GAP 1)
OLS_CUT_ENABLED = _os.environ.get("O4_OLS_CUT", "0") == "1"   # default OFF

# Classic ICAO Annex 14 Vol I (8th ed) Table 4-1, adopted over FAA Part 77
# (notification surface) and Amendment-18 OFS/OES (ADG-keyed, applicable
# 2028 — WATCH item).  Keyed by the repo's approach classes
# (runway_end_approach_class): "visual" = non-instrument,
# "non_precision" = NPA, "precision" = CAT I (apt.dat cannot distinguish
# II/III; their geometry is identical at code 3/4 for the surfaces built).
OLS_TRANSITIONAL_SLOPE = 0.143            # 1:7 — all classes except:
OLS_TRANSITIONAL_SLOPE_STEEP = 0.20       # 1:5 — visual/NPA code 1-2
OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE = {1: 70.0, 2: 70.0, 3: 140.0, 4: 140.0}
# Non-instrument OLS strip == RUNWAY_STRIP_HALF_WIDTH_BY_CODE (30/40/75/75)
# — REUSED, no duplicate (Annex 14 §3.4.4 == §3.4.9 widths).

OLS_APPROACH_SETBACK_M = 60.0             # inner edge beyond the end
OLS_APPROACH_SETBACK_VISUAL_CODE1_M = 30.0
OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M = {  # (approach_class → by code)
    "visual":        {1: 30.0, 2: 40.0, 3: 75.0, 4: 75.0},
    "non_precision": {1: 75.0, 2: 75.0, 3: 150.0, 4: 150.0},
    "precision":     {1: 75.0, 2: 75.0, 3: 150.0, 4: 150.0},
}
OLS_APPROACH_DIVERGENCE = {"visual": 0.10, "non_precision": 0.15,
                           "precision": 0.15}
OLS_APPROACH_FIRST_SECTION_SLOPE = {
    "visual":        {1: 0.05, 2: 0.04, 3: 0.0333, 4: 0.025},
    "non_precision": {1: 0.0333, 2: 0.0333, 3: 0.02, 4: 0.02},
    "precision":     {1: 0.025, 2: 0.025, 3: 0.02, 4: 0.02},
}

# Emission bounds (design values, the earthwork/visual-blast-radius caps —
# the CLEARANCE_MAX_REACH_M philosophy):
OLS_TRANSITIONAL_EMIT_REACH_M = 300.0     # past the handover S; the 45 m
    # inner-horizontal cap sits at ~315 m of 14.3 % rise, so within this
    # reach the cap is unreachable — deliberately NOT modelled.
OLS_APPROACH_EMIT_REACH_M = 1000.0        # past the inner edge (SPJC needs
    # ~300; ceiling +20 m at the cap — artefact terrain daylights long
    # before; the 3 000 m Table first section is a law length, not a cut reach)
OLS_MAX_CUT_DEPTH_M = 15.0                # island refusal guard (SPLP)
OLS_OBSTRUCTION_THRESHOLD_M = 1.0         # cut trigger, matches
    # CLEARANCE_OBSTRUCTION_THRESHOLD_M — added under its own name
```

### `docs/STANDARDS.md` rows to add — new section "Obstacle limitation surfaces — terrain cut — RESEARCHED 2026-07-24"

| Rule | Value | Standard | Implemented in |
|------|-------|----------|----------------|
| Ruleset adoption | classic Table 4-1; NOT Part 77 (notification, weaker near-field); NOT Amdt-18 OFS/OES (ADG-keyed, applicable 2028 — WATCH) | ICAO Annex 14 Vol I 8th ed Ch 4; 14 CFR §77.19; ICAO SL AN 4/1.2.31-25/23 | spec §"regulatory model"; gate `OLS_CUT_ENABLED` |
| Transitional slope | 14.3 % (1:7); 20 % (1:5) visual/NPA code 1–2 | Annex 14 Table 4-1 | `OLS_TRANSITIONAL_SLOPE{,_STEEP}`; law `grade_law.ols_transitional_ceiling` |
| OLS strip half-width (transitional origin) | instrument 140/140/70/70; non-instr reuses 75/75/40/30 | Annex 14 §3.4.3–3.4.4 (FULL strip, not graded portion) | `OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE`; non-instr reuses `RUNWAY_STRIP_HALF_WIDTH_BY_CODE` |
| Transitional anchor | zone-3 ceiling value at the handover S (≤~2 m below the Annex nearest-centreline datum — conservative; continuity with the adjacent-ground law) | design ruling, this spec | `grade_law.ols_transitional_ceiling` (shares `_adjacent_strip_envelope`) |
| Approach first section — inner edge / setback / divergence / slope | tables above | Annex 14 Table 4-1 (8th ed; ICAO 300 m over EASA 280 m — stricter; EASA H still not primary-verified) | `OLS_APPROACH_*`; law `grade_law.ols_approach_ceiling` |
| Approach anchor elevation | solved runway-end elevation; displaced threshold ⇒ conservative | Annex 14 §"inner edge = threshold midpoint elevation"; design | emitter/validator anchor rule |
| Surfaces deliberately NOT cut | inner horizontal, conical, TOCS, OFZ set, approach 2nd/horiz sections | Annex 14 Table 4-1 (obstacle surfaces; terrain penetrations lawful-assessed) | spec §"scope ruling" |
| Emission reaches / cut trigger / refusal depth | 300 m / 1 000 m / 1.0 m / 15 m | design (earthwork + charter bounds, NO regulatory citation) | `OLS_*_EMIT_REACH_M`, `OLS_OBSTRUCTION_THRESHOLD_M`, `OLS_MAX_CUT_DEPTH_M` |

## EMISSION + VALIDATION

**Emitter** — new module `src/auto_patch/ols.py`, entry
`emit_ols_cuts(layout, dem, tile_lat, tile_lon, source_runways)`; role
`ROLE_OLS_CUT = "ols_cut"` (in `layout.py` beside `ROLE_GRADED_STRIP`;
`ROLE_GRADE_LIMITS[...] = None` — clearance-shadow class; surface kind
"aerodrome").

1. **Raster pre-scan (the build-time headline).**  Vectorized numpy over the
   smoothed airport DEM (`elevation._load_airport_dem`, whole-1°-tile
   coverage): for the cells inside each runway's OLS footprint (flank
   rectangles + end fans; a few km² = ~10⁴ cells at 30 m posting, ~10⁵–10⁶ at
   lidar), evaluate the analytic ceiling and mask `DEM > ceiling + trigger`.
   Label penetration ISLANDS; apply the refusal guard per island.  NO geometry
   is built here.  Expected cost ≤ ~5–40 ms/airport; at unobstructed airports
   (HECA/KDFW/OTHH class) the pass ends here — the whole feature costs
   milliseconds, which is what makes it admissible against the
   already-over-budget OTHH wall (HARD LAW, repo `CLAUDE.md`).
2. **Stationed banded emission, islands only.**  Reuse the adjacent-ground
   band machinery, not a new walker: per-station ceiling CLOSURES in the
   `_band_family_closures` pattern feeding `adjacent_ground._build_cut_bands`
   — it already handles piecewise-nonlinear ceilings, run grouping, daylight
   rows, corner fans (`_FAN_MAX_STEP_RAD`) and needle declawing.  Flank
   stations: the runway-family station lines the adjacent-ground march already
   builds, extended beyond its (shrunk) reach; fan stations: the inner-edge
   line beyond each end, rays parallel to the extended centreline, the law's
   own `None`-outside-splay confining the fan (the walker skips ungoverned
   samples — no bespoke fan geometry).  5 m station/step
   (`CLEARANCE_STATION_STEP_M`).
3. **Clip/weld discipline** (the 2026-07-09 WELD RULING,
   `docs/adjacent_ground_grade_law_plan.md`): exact `difference()` against the
   static union (skirt, RESA cut, adjacent bands, pavement, crossing influence
   zone); where an OLS band abuts an adjacent-ground band that is obstructed
   through S, the shared row carries the SAME ceiling value from the same law
   helper — welds by shared coordinates, guarded adoption, no groove.  Inherit
   the skirt's roads/water constraint clamp
   (`runway_end_constrained_length_m` pattern) for the fan.  **Deliberately
   NOT clipped to the airport boundary** — OLS lives outside the fence by
   nature; precedent: runway-end skirts already emit beyond it
   (`check_adjacent_ground` treats outside-boundary as exempt for ITS scope
   only).
4. **Pipeline ordering**: after `emit_runway_end_skirts` + the A2 RESA cut +
   adjacent-ground bands and their tile_cut, so OLS clips against all of them;
   before the final epsilon-wedge weld.  Then
   `tile_cut.cut_layout_at_tile_boundaries` for the fan pieces crossing the
   integer line — cross-tile determinism per the skirt's covering-raster rules
   (both tiles derive the fan from the same whole-runway geometry + shared
   boundary-blended DEM).
5. **Decimation**: emit ceiling values snapped to the bound within
   `_CORRIDOR_SNAP_TOL_M` so planar transitional/fan cuts decimate to a
   handful of triangles (`emit_decimate.decimate_shape_group`).

**Validator** — `verification.check_ols_surfaces(layout, dem, tile_lat,
tile_lon, source_runways=None, tolerance_m=1.5, step_m=5.0)`, the
`check_adjacent_ground` twin: pure reporter, marches the SAME stations, reads
the SAME `grade_law.ols_*` functions and the SAME pre-scan/refusal/
supported-depth scoping (all three exemptions recomputed from the one law —
LOCKSTEP is mandatory), exempts covered columns via the emitter's own static
clip.  Finding kinds: `should_cut_ols_transitional`,
`should_cut_ols_approach`, plus an informational `ols_refused_island` count.
Wired into `verify_and_log` gate-guarded exactly like the adjacent-ground
block: gate off ⇒ not called, byte-identical verify output; gate on with no
emission ⇒ reports the pre-flip baseline.

**Gate**: `O4_OLS_CUT` / `config.OLS_CUT_ENABLED`, **default OFF**.  Emitter
module imported inside the gate (byte-inert off).  FLIP CRITERIA (all
required): (1) in-sim owner sign-off at SPJC (origin terrain governed, no new
walls), CYXY + SPLP (refusals logged, mountains untouched), HECA + KDFW (zero
OLS shapes, zero visual delta); (2) `check_ols_surfaces` findings = 0 at the
battery with emission on; (3) wedge/triangle audits: `check_epsilon_wedges` no
new findings, `tools/mesh_region_tris.py` triangle deltas reviewed; (4)
`tools/check_build_time.py` green — any ≥0.6 s airport cost or ≥3 s tile cost
triggers the Fable-5 optimization review, and any budget crossing needs
written owner approval (HARD LAW); (5) the zone-3 reach-shrink A/B at CYXY
documented (expected: fewer/smaller runway-flank cut bands).  DEPENDENCY:
flank handover correctness wants arc A4
(`STRIP_WIDTH_FROM_CENTERLINE_ENABLED`) ON first; until then
`ols_lateral_handover_distance_m`'s `max(S, W_edge)` floor keeps the join
step-free at the cost of a slightly late handover.

## SLICES

1. **Constants + law + STANDARDS rows.**  All `OLS_*` constants; the three
   `grade_law.ols_*` functions + unit tests: continuity at S to 1e-9 against
   `adjacent_ground_envelope` for every (code, class); slope/table values vs
   this spec; fan `None` boundary exactness; refusal rule determinism.  No
   behaviour.  Build-time: 0.
2. **Raster pre-scan, report-only.**  `ols.py` phase-1 + one verify-log
   forensics line per airport (island count, worst penetration, refusals).
   Run at the fixture battery (SPJC, SPLP, CYXY, HECA, KDFW, KCLT, MMOX) — the
   measured island inventory is the evidence for the reach/refusal defaults
   before any geometry exists.  Acceptance: SPJC 16R reports the origin island
   (~2.4 m worst); HECA/KDFW report zero; SPLP reports refusals.  Build-time
   statement: ≤ 0.05 s/airport measured.
3. **Emitter behind the gate.**  Bands, clips, welds, tile_cut, the
   runway-family reach override, A/B battery.  Acceptance: SPJC origin knoll
   covered by an `ols_cut` band whose sampled surface ≤ ceiling + 0.15 m; zero
   self-overlap findings; zero new tears; flat controls byte-identical gate-on
   (no islands ⇒ no shapes).  Build-time statement per airport, ledgered.
4. **Validator + audits.**  `check_ols_surfaces` + verify wiring + lockstep
   test (emitter output ⇒ 0 findings; forced no-emit ⇒ findings == pre-scan
   islands); wedge/triangle audits at the battery.
5. **Flip proposal.**  The criteria above, owner ruling, then default ON;
   update `src/auto_patch/CLAUDE.md` standards paragraph + `OPEN_ITEMS.md`.

## RISKS

- **Triangle/constrained-edge growth over km²** — the largest-area law in the
  repo.  Mitigated: island-scoped emission, planar snap-to-bound decimation,
  the two audits as flip gates.  Watch KCLT (skirt + EMAS + fan interplay at
  ends).
- **Build-time**: the design is O(footprint cells) vectorized + O(island
  perimeter) geometry; a pathological lidar DEM with large islands is the
  worst case — the refusal guard caps it (a mountain island refuses early).
  Budgets and the Fable-5 review are the tripwire; OTHH is already over budget
  and must measure ~0 (pre-scan only).
- **Cross-tile fans**: determinism depends on whole-runway derivation + the
  shared boundary-blended DEM; out-of-tile DEM samples return None and must be
  skipped exactly as the existing walkers do — asymmetric sampling at the seam
  is the failure mode to test (a fixture runway near a tile line; SPLP's
  RW02/20 seam class).
- **Outside-boundary emission** interacts with `geom_guard` / `to_osm`
  assumptions proven only for skirts — audit those paths for boundary
  assumptions before slice 3.
- **Corner wedge simplification** (min-composition vs the Annex
  transitional-along-approach) leaves a small report-only gap; if in-sim shows
  walls there, the fix is a corner-fan station set, not a law change.
- **Approach-class misdata** (blank apt.dat rows default non-precision):
  defaults to the STRICTER instrument geometry — safe direction; CIFP ILS
  fields (parsed but unused in `cifp_reader`) are the upgrade path if
  misclassification shows up.
- **Interaction with in-flight arcs A2/A3/A4**: OLS clips against the A2 RESA
  cut and depends on A4 for the clean handover; land order A4 → A2 → OLS
  slice 3, or carry the `max()` fallback.

## Sources

- ICAO APAC OLS Quick Reference Guide (Amendment 18 parameters) —
  <https://www.icao.int/sites/default/files/APAC/Meetings/2025/2025%20Workshop%20on%20Implementation%20of%20New%20ICAO%20Annex/Training%20Materials/OLS_QU-1.PDF>
- ICAO State Letter AN 4/1.2.31-25/23 — Amendment 18 to Annex 14 Vol I —
  <https://www.icao.int/sites/default/files/APAC/Meetings/2025/2025%20Workshop%20on%20Implementation%20of%20New%20ICAO%20Annex/Training%20Materials/SL-2025-23_amendment-18-to-Annex-14-Vol-I.pdf>
- IAA ASAM No. 014 Issue 3 — Guidance Material on Aerodrome ICAO Annex 14
  Surfaces (classic Table 4-1 reproduction) —
  <https://www.iaa.ie/docs/default-source/publications/advisory-memoranda/aeronautical-services-advisory-memoranda-(asam)/guidance-material-on-aerodrome-icao-annex-14-surfaces.pdf>
