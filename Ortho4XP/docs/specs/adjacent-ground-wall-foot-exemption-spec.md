# Adjacent-ground wall-foot exemption (item-4 ruling (d)) — spec

Author: lead (Fable), 2026-08-07. Charter: RULINGS 2026-08-07 "Item-4
… RULED same day (owner, PROVISIONAL): (d)". Evidence:
`Ortho4XP/tmp/item4_evidence/` (frame: c9air fix1 patches, tree
`e9620ff4`, twinned against the lane's recorded census).

## What changes (adjudication side ONLY — patches must not move)

The existing wall-SPANNED tear exemption (both endpoints on a declared
`retaining_wall` way) extends to the ONE-SIDED case. A tear row
(`strip_seam_tear`, `adjacent_ground_tear`) is EXEMPT iff:

1. one endpoint is on-DEM (the instrument's existing on-DEM predicate,
   `|alt_abs − DEM| ≤ 0.005 m`, in the frame the census already uses
   for the spanned exemption — do NOT invent a new tolerance), AND
2. that on-DEM endpoint lies ON a declared `retaining_wall` way
   (way membership, canonical identity — never proximity), AND
3. that endpoint is a member of an `adjacent_ground` band ring.

The law-valued partner's way membership is NOT consulted (that is the
extension). NO magnitude cap: step size at the boundary is a
flat-world artifact by construction (owner ruling text). The exempt
row must still be REPORTED under the existing exemption-visibility
convention (exemptions are counted, never silent — same as
terrace_joints_ll).

## What must NOT change

- Generation: zero. Byte-identical patch bodies everywhere (this is a
  census/adjudication change only).
- The two-sided (spanned) exemption's behavior on its existing
  population.
- No other family's counts at any battery airport.

## Acceptance (all law-true frame, harness census, labelled frames)

1. HECA −500 (c9air fix1 patches or current-tip equivalents): the 48
   ≥10 m airside rows (42 `strip_seam_tear` + 6
   `adjacent_ground_tear`) adjudicate EXEMPT; adjudicated airside
   drops by exactly the rows whose on-DEM endpoint is wall-hosted
   (evidence says 48/48 — a shortfall is a STOP-and-report, not a
   predicate widening).
2. HECA 10k: no change from this exemption is expected (evidence: 0 of
   53 rows touch an on-DEM vertex). Any delta is a STOP.
3. Battery: matched-control censuses on existing patches, FAILED-list
   diff empty, no family moves anywhere except the two named tear
   families at HECA −500.
4. Twin: a fixture test in the harness twins (LAW_FAMILIES path) that
   constructs a one-sided wall-hosted boundary and asserts EXEMPT, and
   a non-wall-hosted on-DEM endpoint and asserts NOT exempt. Register
   per the LAW_FAMILIES/`run_checks` lockstep rule.
5. The exemption is visible in census output with a distinct label
   (e.g. `wall_foot_ll`), so the owner's "revisit at sim pass" has a
   number to look at.

## Budget

0 builds expected (censuses replay on existing patches). Pytest
harness-twin selection only. Build-time impact: none (no production
generation code).

## Provisional marker

Owner wording is "try d". The lane lands the exemption
default-ON but the census label keeps the class enumerable so a
reversal is one revert + re-census, no re-generation.

## Deviations ratified (Fable spec author, 2026-08-07)

1. **`--dem M` threading APPROVED as landed.** check_grade/census were
   DEM-free by design; no on-DEM predicate existed to reuse, so an
   explicit declared world with an inert default is correct (it can
   only under-exempt, and law-true counts never move). CHORED, not in
   this lane: census auto-reads the recorded frame sidecar's
   `synthetic_dem.elevation_m` when present and REFUSES a
   contradicting `--dem` — a censused world must not be silently
   wrong.
2. **Same-value stacked twins count as ONE node for wall-way
   membership.** The house canonical join IS 11-decimal coordinate-
   spelling equality (never proximity); two nodes with identical
   11-dp spelling AND identical value weld into one mesh vertex, so
   way membership extends across the weld. Both spellings must match
   exactly and values must be equal — differing values or differing
   spellings never join. Expected effect: the 46 becomes 48/48. Add a
   twin for the stacked case. (The twin population itself is
   node-identity-round territory — eliminating the twins at source
   later does not change this rule's correctness.)
3. **Battery-wide firing is CORRECT; acceptance 3 was too narrow.**
   The owner ruled a law form, not a HECA patch. The exemption fires
   wherever its predicate holds (measured: SPJC_lo 14, HEAZ_lo 3,
   KCLT_lo 21, all −500-world, both named families only, law-true
   counts unchanged everywhere). The published adjudicated frame
   moves accordingly — that is what "try d" means.
