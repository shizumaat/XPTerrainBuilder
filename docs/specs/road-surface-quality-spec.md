# Road surface quality — lateral flatness + post-limiter authors
# (Fable spec, 2026-08-25; RULINGS 2026-08-25g; the owner's 1.0.259
# read: roads improved but "a lot of bumps and laterally not flat")

Evidence: the 2026-08-25 roads attribution and the roadseal round's
§1.3 ordering audit. Remaining road classes after the seal fix:
76 longitudinal-tear rings, 31 transverse-tear rings (e.g. 3.50 m over
1.00 m = 350%), the 2,422 `exit_over_budget` transects, and FOUR
post-limiter road authors measured at the seams (18b weld 2@0.10 m,
19_final_projection 2,084@5.83 m, 20_post_projection_conformance
1,308@5.83 m, 22_weld_crown_densify 80@5.64 m) — road nodes moved
metres AFTER the last law that prices them.

## §1 Lateral law (RULINGS 2026-08-25g)

1. Within-ring TRANSVERSE road pairs (pair axis ≥ 45° to the road
   axis — the roads attribution's classifier, promote its notion into
   the law reader, one implementation) price at the road CROSS-SECTION
   limit (the existing config cross-section constant for roads; never
   a literal), not the longitudinal chord cap. Crown declarations
   (`crown_drops`) exempt exactly as elsewhere.
2. Registered in `LAW_FAMILIES` with the register/census/fixture
   parity twins (`test_harness.py`).
3. The SOLVE must enforce what the census prices (one law): the road
   ring's transverse pairs enter the grade graph at the cross-section
   cap. Solve-side and census-side land TOGETHER.

## §2 Post-limiter road authors (the bumps)

1. ATTRIBUTE FIRST, inside the lane: of the four measured passes,
   which author the IN-SIM bump population (sample the owner-visible
   road runs; the 5.83 m movers in 19/20 are the prime suspects).
   One targeted probe run, not four blind fixes.
2. FIX per evidence, mechanism-true: the ordering defect is that
   roads exit the limiter un-re-priced. The remedy shape (pick per
   attribution): the road chord+cross-section law re-clamps road
   nodes AFTER pass 20 (a final road conformance pass reusing the
   SAME law objects — one law, run late), or the authoring passes
   exempt road-family nodes they have no law for. A pass that moves
   a road node > materiality with no law pricing it is the defect.
3. STOP if the authoring pass is itself a law with seniority over
   roads (report the conflict, don't improvise seniority).

## Acceptance (ONE HECA build + owner-road smoothness read)

- Station profiles along the owner site's roads (30.1023, 31.3951
  area): longitudinal bumps and lateral tilt reported before/after
  (the in-sim complaint is the bar — quote worst lateral grade vs the
  cross-section limit).
- Census: the 31 transverse-tear rings and the N-1-class rows priced
  under §1 (report the new family's count honestly — the bar is
  founded by the owner); airside byte-stable; groundside road rows
  reported vs the roadseal-era table.
- exit_over_budget 2,422: report the delta (not this spec's target;
  a large move is attributed, not claimed).
- SPJC/CYXY non-regression. KAFW N-1 re-read if artifacts allow
  without a build.
- Attempt cap 2 per section, materiality 0.01 m, STOP on second miss.
  No shared-repo writes, no timing claims.
