# Gap conformance — rings never cliff, interiors erode, spines descend
# (Fable spec F3, 2026-08-15; owner law in RULINGS.md "GAP INTERIOR
# RINGS NEVER CLIFF AGAINST PAVEMENT" + the erosion generalization the
# owner confirmed at CYXY)

Measured offenders (CYXY R5 patch `CYXY_20260815T181744`, HECA
`HECA_20260815T181805`): ring `-10527` at 698.5–698.9 sits 4–5 m
below adjacent road/groundside 702.7 within 11 m (owner: "should
never create cliffs"); `gap_drainage_spine -10476` stamped flat 695.8
across all 9 nodes, 7.7 m BELOW its own terrain (703.5) — a
manufactured canal; HECA "elevated plateau" 30.1156366,31.4114059 —
gap surfaces at 94.7–95.2 beside on-terrain roads at 100.3 (DEM
101.8).  The owner's preferred CYXY geometry: the ring cuts across
the pocket's neck (≈60.7095516,-135.0719304 → 60.7103078,
-135.0723208) and does not extend into the 8–15 m sliver at
60.709358,-135.0734701.

## The law

1. **CONFORMANCE BAND.** Within `GAP_PAVEMENT_CONFORM_MARGIN_M` of
   any enclosing graded pavement edge, gap surface vertices take the
   NEAREST pavement edge's SOLVED elevation (interpolated along the
   edge, the mouth-weld read posture: uncrowned, post-solve).  Never
   terrain, never a stamped basin value.  A gap vertex near TWO
   pavements blends by inverse distance between their edge values
   (the sliver case — both sides conform, no interior).
2. **THE INTERIOR IS THE ERODED POCKET.**  The gap interior — the
   region that may descend to terrain — is the pocket ERODED by the
   margin (shapely `buffer(-margin)` on the pocket polygon, largest
   piece(s) kept).  Lobes narrower than 2×margin erode away entirely
   and are pure conformance band.  The emitted `gap_interior_ring`
   IS the eroded boundary — this yields the owner's cut-across-the-
   neck geometry with no hand-drawn lines.
3. **THE SPINE DESCENDS LAWFULLY AND NEVER BELOW TERRAIN.**  A
   drainage spine's profile from its conformed boundary endpoints:
   `value(s) = max(terrain(s), boundary_value − slope_cap·s)` walked
   from each end (take the max of the two walks) — it descends at the
   lawful groundside slope until it MEETS terrain, then follows
   terrain.  This kills the stamped-flat trench class: a spine value
   below local terrain is impossible by construction.  Interior gap
   faces conform to their spine (existing consumption machinery).
4. `GAP_PAVEMENT_CONFORM_MARGIN_M` is ONE new named constant in
   `config.py`, default **10.0 m** — erodes the measured 8–15 m
   CYXY sliver, keeps the ≈87 m neck.  No other new constants.

## Scope

`src/auto_patch/gap_fill.py` (+ its presolve construct mirror — the
gapstop parity twin "every constructed station consumed" must keep
passing) and the gap emitter's ring/spine valuation.  Roads, strips,
aprons, airside: UNTOUCHED — airside must be byte-identical.

## Acceptance (harness only; vs the two patches named above)

1. Twins: (a) a synthetic pocket with a narrow lobe erodes it (ring
   cuts at the neck); (b) band vertices equal their nearest edge's
   solved value; (c) two-pavement sliver blends, no step; (d) spine
   profile ≥ terrain everywhere, descends ≤ slope cap, follows
   terrain after contact; (e) gapstop parity twin still passes.
2. CYXY: ring cliff at 60.709994,-135.0726683 gone (ring vertices
   there = adjacent pavement values); the -10527 ring no longer
   extends into the sliver; drainage spine at 60.7124,-135.0802 no
   longer below terrain (was flat 695.8 under 703.5).
3. HECA: plateau flats at 30.1156366,31.4114059 conform (no ~5.4 m
   step against the on-terrain roads); `-11585` stays ambient.
4. Censuses both airports: totals + family deltas reported vs CYXY
   377 / HECA 6,998; airside byte-identical; no new family.
5. Build-time: ledger-frame walls only.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; deviations
STOP-and-report to the Fable lead.

## F3b — THE STAGED SPINE LAW (Fable amendment, 2026-08-16, adjudicating
## the +1,332 drainage_spine collision)

Measured on the lane's HECA arm (HECA_20260815T203509): +1,332
drainage_spine rows, all other airside families +0.  Mechanism: spec
clause 3's ``max(terrain, cone)`` walk follows terrain UP wherever
interior terrain sits above (lower bounding edge − MIN_FALL), while
``grade_law.drainage_spine_envelope`` demands the WHOLE spine ≥
MIN_FALL below the lower edge (the dam clause).  Both laws are right
in their own region; the spec drew no boundary.  The owner's words
("a drainage spine pulls terrain down to follow grading
requirements") also refute clause 3's terrain floor as written: an
enclave hill above its pavements is GRADED DOWN, not followed.

The staged law (supersedes clause 3; one law, both readers):

* BAND (distance from a bounding pavement edge ≤
  GAP_PAVEMENT_CONFORM_MARGIN_M): the spine is PINNED to the
  conformed edge value — ``drainage_spine_envelope`` returns the
  pinned (0, 0) offsets there; the dam clause does not apply.
* INTERIOR: ``value(s) = max(cone_floor(s), min(terrain(s),
  min_edges − MIN_FALL))`` where ``cone_floor(s) = max over
  conformed ends (end_value − bench_slope·s)``.  The cone floor is
  the anti-trench guard (depth bounded by lawful descent — the CYXY
  flat-695.8 canal collapses to ≤ ~2.4 m below its boundary); the
  ``min(..)`` is the dam clause where terrain is high (the enclave
  hill is pulled down to drain) and terrain-following where terrain
  is already below the drainage ceiling.
* VALIDATOR rows: band station off its pin > materiality; interior
  station above the drainage ceiling (dam) or below the cone floor
  (crater/stamped flat).  The existing crater guard (lateral floor)
  stays.

Acceptance deltas: the HECA re-census must show the +1,332 collapse
to true violations only; CYXY re-runs (its passed acceptance was
measured under the superseded clause 3 and is void until re-measured).

## F3c — GRADED HANDOFF ON EMPTY INTERSECTION (Fable amendment,
## 2026-08-18; owner-ruled, RULINGS "CRATER-VS-DAM RESOLVES BY GRADED
## HANDOFF")

The residual class (DEFERRED 2026-08-16, verified arithmetically off
the emitted patch): at a station far from BOTH parents the higher
parent's crater FLOOR (`adjacent_ground_envelope`, anti-trench) can
stand above the lower parent's dam CEILING (`drainage_spine_envelope`,
"below the lower adjacent pavement") — HECA way `-13464` @
30.116941,31.443884: runway floor 140.99 − 1.701 = 139.29 vs dam
ceiling −0.3 under an apron 6.0 m lower; intervals disjoint; the
2026-07-09 fallback took the nearer parent and left the spine 4.31 m
proud of the lower edge. 34 of HECA's 70 surviving drainage_spine
rows are this class.

The ruled law — neither clause hard-wins; the spine DESCENDS from one
authority to the other:

* In `_spine_interval` (gap_fill.py:971), when `max(floors) >
  min(ceils)` with two parents, the fallback is no longer the nearer
  parent's own interval. The station's value target becomes the
  MONOTONE HANDOFF: interpolate from the higher-floor parent's floor
  toward the lower-ceiling parent's ceiling by relative distance
  (`w = d_high/(d_high + d_low)`), then clamp the profile to lawful
  slope (`bench_slope`, the clause-3 cone constant) walked from the
  higher side — where the separation is too short to descend the full
  drop lawfully, the descent runs AT the cap from the higher side and
  the residual against the dam ceiling is reported (PASS-with-residual
  under the materiality floor, a census row above it — never a silent
  nearer-parent value).
* Adjacent stations of the same spine must not oscillate between
  regimes: the handoff is evaluated per station but the emitted
  profile keeps the clause-3 monotone-walk posture (max of walks from
  conformed ends still applies afterwards; the handoff supplies the
  interval, not the final profile).
* One law, both readers: the validator prices the same handoff value —
  a station inside a disjoint-interval zone is judged against the
  handoff, not against either parent's raw clause.

Acceptance (residual-sweep lane): twins — (a) disjoint-interval
synthetic: value descends monotonically from floor-parent to
ceiling-parent at ≤ bench_slope, never proud of the handoff; (b)
intersecting intervals byte-identical to today; (c) short-separation
case reports the residual. HECA re-census: the 34-row `-13464` class
collapses to at most the short-separation residuals; the other 36
survivors re-attributed after (they were never this class — report,
don't chase past the attempt cap). CYXY stays 0. Airside otherwise
byte-identical. Materiality 0.01 m; attempt cap 2; STOP to lead.
