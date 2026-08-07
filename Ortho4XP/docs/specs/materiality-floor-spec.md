# Materiality floor — 0.5 m accumulated, guarded, runways exempt — spec

Author: lead (Fable), 2026-08-07. Charter: the owner's four-part
2026-08-07 floor ruling (RULINGS "Materiality floor") + the
role-less-host lead ruling of the same day. ADJUDICATION-ONLY: law,
generation, and law-true counts unchanged; patches do not move.

## The work (census/check_grade adjudication layer)

1. **The floor, per SITE**: using the landed `--sites` clustering
   (census.py, merged today), an adjudicated site is ACTIONABLE only
   if its accumulated unlawful excess ≥ 0.5 m. Accumulation = the
   site's summed per-row excess in metres (state the exact summation
   in the report header; it must be derivable from the rows the site
   already carries — no new measurement).
2. **The sharp guard**: a site below the floor stays ACTIONABLE if
   ANY of its rows has a single step ≥ 0.15 m OR local grade ≥ 2× its
   cap. Constants are named knobs with the ruling cited.
3. **Runway exemption**: any site containing a runway-family role is
   ALWAYS actionable (never floored).
4. **Role-less feature ways side with their host** (the lead ruling):
   shape_interior_ring / gap_interior_ring / gap_drainage_spine /
   crown_spine rows take the host shape's role, side, and cap; rows
   duplicating a host way's geometry belong to the host only. This
   removes the airside-default-at-1.5% class and the double-count.
5. Sub-floor sites are REPORTED under their own label
   (counted-never-dropped, the wall_foot_ll/disconnected_ring
   convention) so the owner's provisional floor stays revisitable.

## Acceptance (0 builds — offline on the frame-of-record patches)

1. Battery before/after: the site table and adjudicated/actionable
   split per cell; every reclassified site listed with its
   accumulation, guard verdicts, and families. Law-true counts
   byte-identical everywhere.
2. Runway-exemption twin; floor fixture; both guard fixtures
   (step-only trips, steepness-only trips); host-siding fixture
   (role-less way judged at host cap, no double-count); sub-floor
   label lockstep with the register.
3. The new headline table (sites / actionable sites / visible
   actionable sites) for the owner.

## Budget

0 builds; pytest via run_with_ledger. Deviations: STOP-and-report.
