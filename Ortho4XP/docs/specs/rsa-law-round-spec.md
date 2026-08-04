# RSA law round: strip precedence + abeam-longitudinal (G-1 general, G-2)

Fable spec, 2026-08-04. The two P0 gaps from the standards-gap review
(scratchpad standards_gap/ — read its G-1/G-2 entries + citation table
first; every regulatory number below is primary-verified there). Lines
against 4b591fc. BINDING: docs/RULINGS.md (grade-law completeness:
generation-binding + validator twin; region rulesets are FUTURE — this
round lands the blended values with per-authority constants NAMED so
phase B can split them).

## §1 Strip precedence (G-1 general — the wall part landed in 0b9efaf)
The runway-strip footprint (CL ± RUNWAY_STRIP_HALF_WIDTH_BY_CODE + the
end corridor) is SUPREME: inside it, no other role's corridor/envelope
law may govern ground — the strip corridor law wins for any station
regardless of owning shape (the apron-corridor-inside-the-strip case
that built the 9.7 m wall). Gate O4_STRIP_PRECEDENCE default "0".
Emitter side: the adjacent-ground family consults the footprint and
defers (the keepout machinery from 0b9efaf generalizes from walls to
corridor LAW). Validator twin: within the footprint, ground is judged
by the strip law (zones/transverse/longitudinal), never the local
role's. Pre-register: HECA's strip-abeam band re-grades inside strip
law; no wall regressions (still 0); census deltas quoted both frames.

## §2 Abeam-longitudinal law (G-2 — MISSING family)
FAA 3.16.5.1 item 1: between the ends, the RSA's longitudinal grades
meet the RUNWAY's own standards; ICAO 3.4.13: graded-strip longitudinal
<= 1.5% code 4 / 1.75% code 3 / 2% code 1-2; 3.4.14 no abrupt changes.
New constants RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE = {1:.02,
2:.02, 3:.0175, 4:.015} (ICAO; FAA-side constant named alongside for
phase B). The lateral corridor law gains the along-frontage term:
strip-band ground is bounded longitudinally at the by-code slope (the
generation-binding half — the corridor envelope consumes it); validator
twin: a longitudinal reader over the strip bands (transect-style along
the runway axis, reusing the transverse reader's pattern). Same gate as
§1 (one law family: the strip's own law, both axes). Pre-register: the
strip bands' longitudinal profile at HECA/KCLT quoted before/after
(KCLT: six precision code-4 ends, the largest strip population — the
FAA fixture's first law exercise); new-visible rows quoted honestly
(the count RISES — the reader sees what was never read).

## Acceptance
Gate-off byte identity on the five default anchors (2x); gates-on arms
HECA + KCLT + HEAZ both frames with pre-registrations; suite same 23
reds + twins per law; runway vertices byte-identical; work in a
WORKTREE (the main tree may host concurrent measurement) with the
documented symlink pattern; foreground; only check_build_time --run
timings quotable; do NOT commit. Convergence guards apply.
