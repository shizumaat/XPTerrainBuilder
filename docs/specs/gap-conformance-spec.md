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
