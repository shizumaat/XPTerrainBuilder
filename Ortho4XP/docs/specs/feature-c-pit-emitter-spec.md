# Feature C pit emitter (drainage basins) — spec

Author: lead (Fable), 2026-08-07. Charter: owner 2026-08-07 —
"create [a spec] and kickoff agents to complete the drainage pit
work" (the OTHH class). No prior spec exists for the emitter half.

## State of record

Feature C (sunken basins; `object_terrain_features.py`, gate landed
`396b004` "Feature C gate + recognition-based pool exclusion")
CLASSIFIES drainage pits but HAS NO EMITTER — recognition landed,
the acting half never did. Recorded misclassification modes the
recognition had to defeat (verify current state at HEAD before
building on them): the height gate counted BELOW-grade extent as
building height; the bowl gate counted the pit's own rim as ground
contact.

## Law constraints (all standing; violations are STOP-and-report)

1. A pit interior is REAL below-grade terrain: never flattened to
   grade, never a building, never removed.
2. Zero airside effect (airside-is-king): emitting a pit must move no
   airside value anywhere. Pits are non-route ground — they may
   terrace freely under the groundside terrace law.
3. If a pit lies inside an airside-surrounded enclave, the 2026-08-07
   enclave ruling governs (gap interior ring + spine, airside-
   interior) — FLAG such a pit and STOP on it rather than improvise;
   emit the rest.
4. Role vocabulary: prefer existing role literals (blast.py names the
   role-literal hazard); if a NEW role literal is genuinely required,
   STOP and report — role literals are wire-adjacent and
   owner-visible.
5. No terrace joint may cross any road (2026-08-06 ruling) — a pit
   rim adjoining a road takes its relief inside the pit, not across
   the road.

## The work

Give Feature C an emitter: the classified basin emits a carve — rim
ring + interior that preserves the below-grade surface (DEM-following
interior or lawful terraced interior; the implementer proposes the
minimal mechanism consistent with how the existing carve/cutout
machinery works — read `gap_fill.py` and the Feature A tunnel-carve
precedent before designing, and report the chosen mechanism in the
final report).

## Acceptance

1. OTHH (+25+051): the basins Feature C classifies at OTHH emit —
   enumerate them from the classification output first and quote the
   list (count, coords) in the report; after the emitter, each is
   present in the patch as a carved region, interior below grade.
2. Battery inertness: all battery-airport patches BYTE-IDENTICAL
   (no Feature C instances there — prove it, don't assume it; if any
   battery airport has an instance, report before proceeding).
3. OTHH census (law-true frame): zero NEW airside rows vs a pre-change
   OTHH control; groundside deltas reported and attributed (lawful
   terracing expected).
4. Twins: headless tests for the emitter (classification fixture →
   emitted carve; no-instance → byte-identical), registered per the
   repo's test conventions.
5. Build-time impact statement (emitter runs only where Feature C
   fires; expected ~zero on battery airports).

## Budget

2–4 OTHH patch-equivalent builds (warm-cache discipline; first OTHH
build in this session is cold and is not a comparison arm) + a
pre-change OTHH control + blast-radius pytest via run_with_ledger.
Hard cap 6 builds. Deviations: STOP-and-report for Fable review.
