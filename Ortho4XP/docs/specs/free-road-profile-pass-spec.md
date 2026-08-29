# Free-road profile pass (HECA round 5b) — one-way weld + whole-path ramp

Closes what round 5 left open (heca-round5-drainage-and-ramps-spec law 3,
un-implemented; lane/hecar5's interventional evidence, merged 52d54c6e).
The contact-cap scoping (`O4_ROAD_CONTACT_CAP_SCOPE`) shipped DEFAULT OFF
(9ac6ee55) because alone it re-prices but nothing builds the profile:
item-2's site went 0.70 m worse and 9 airside rows moved. This round
builds the profile pass and flips the scoping ON in the same arm.

## Standing evidence (lane/hecar5 — do not re-derive)

- The crossing adoption DOES build the ramp (106.70 → 108.383) and
  `_grade_limit_groundside_chords` (pipeline 6692 + 6957) flattens it
  back: its binding pair is the ring's own RETURN side across the U-loop
  — 5–25 m EUCLIDEAN between points far apart along the PATH. The
  route-metric lesson (rm-route-metric-within-shape-spec, rod-chains-
  split-at-branches) applies verbatim: chords across parallel legs of
  one road must be priced along the path, never across the loop.
- Weld states at the owner sites: item 2 welded (0.000 m); item 4 mouth
  seat (0.02 m); item 3 UNBOUND — nearest end-on approach 1.538 m vs
  the derived 1.5 m (`_PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M`) mouth
  tolerance, so nothing binds it.

## Law

1. ONE-WAY WELD: a free road's contact with aircraft pavement pins the
   ROAD to the pavement's SOLVED value — a Dirichlet endpoint. The road
   is solved AFTER airside and never feeds back; airside is king stays
   whole-cloth (zero MOVED airside is again the gate, and now reachable
   by construction).
2. END-ON BINDING TOLERANCE: an end-on approach binds when its gap to
   the pavement is within the road's own half-width (geometric, no new
   constant — item 3's 1.538 m gap binds under a 6 m road; derive, don't
   hardcode; publish refused near-misses like the veto refusals).
3. WHOLE-PATH PROFILE: per free-road chain (path metric, split at
   branches — the rod-chain law), solve the longitudinal profile between
   pinned ends (and DEM-held free ends) at ≤ `SERVICE_ROAD_MAX_GRADE`
   (8 %), monotone where the pins demand it, distributed over the whole
   run including U-turn legs. The profile OWNS the chain's values;
   `_grade_limit_groundside_chords` either prices profile-solved chains
   along the PATH metric or exempts them — it never re-flattens across
   the loop.
4. The contact-cap scoping gate flips DEFAULT ON in this arm (one flag
   day, one measured round).

## Acceptance

- Item 2: monotone ramp start→junction (weld 0.000 kept), cliff at
  30.1052938,31.3989669 gone; the U-turn leg carries the climb to
  30.107403,31.4022258.
- Item 3: end binds (law 2), monotone ramp to 30.1046554,31.3973678.
- Item 4: monotone descent off the apron at 30.114984,31.4107959.
- ZERO MOVED airside rows vs the OFF arm (the round-5 trade eliminated).
- HECA census improves at the four sites; patch-wide not worsened
  beyond attributed un-blinding.
- Controls CYXY/SPJC/OTHH byte-identical OFF; ON deltas attributed.
- Twins: one-way weld direction (airside never moves), binding
  tolerance both sides, path-metric limiter pricing, U-loop
  interventional twin (the flatten reproduced OFF, gone ON).

## AMENDMENT 1 (Fable, 2026-08-28, on lane/hecar5b's fork)

The lane built all four laws; item 4 proves the pass (204.08 % ->
9.35 %). The blocker is METRIC COLLISION: the census prices within-shape
road pairs by euclidean chord, so a path-lawful 8 % ramp across a U-loop
reads 8.33-9.11 % (CYXY +120 rows = 8 % x path/chord, exactly).

RULED — OPTION 1, as the composition of two standing laws:
1. WITHIN-SHAPE ROAD-FAMILY PAIRS ARE PRICED ALONG THE ROAD'S OWN PATH
   METRIC (the route-metric-within-shape precedent extended to the road
   family), and a chord that LEAVES the shape's own pavement polygon is
   the GAP-CHORD class (RULINGS 2026-08-24b: "a step is lawful only
   across a pavement gap") — never priced as surface grade. ONE
   implementation in the harness law register (check_grade), consumed by
   both readers (emitter limiter + census) — the twins pin the two
   readers to one code path per the census-wrapper law.
2. THE MOVED-AIRSIDE GATE IS ADJUDICATED ON THE SOLVE-OWNED FRAME
   (tools/airside_value_delta.py's second frame, its documented
   distinction): graded_strip and other soft receivers ADOPT from the
   pavement they abut and count as airside only in the row-side split —
   adoption rows are attributed churn, not a breach. Gate: solve-owned
   moved airside = 0.
3. Gates (profile pass + contact-cap scoping) flip DEFAULT ON only in
   the arm where: all four owner sites monotone/lawful, the metric-
   collision rows GONE (CYXY back to control class counts or every
   residual attributed), solve-owned moved airside 0, OTHH/LEMD arms
   built.

## AMENDMENT 2 (Fable, 2026-08-28, on lane/hecar5c's report; 5c merged
9486c765 default-OFF)

5c's path metric is RATIFIED as landed (CYXY collision 71->0, both
scopings — longitudinal-only, census-reader-only — correct and twinned).
Two blockers remain, ruled/chartered:

1. PER-STATION CAP UNIFICATION (the lateral_contiguity self-
   disagreement, ruled): cap authority lives at ONE granularity — the
   STATION. The lateral walk's own adjacency read produces a per-station
   cap vector (1 % where the station is genuinely alongside/inside an
   apron per the free-road ruling; SERVICE_ROAD_MAX_GRADE 8 % free), and
   pricing, the solve graph, and the profile pass's cap-Lipschitz
   envelope ALL consume that one vector — one derivation, three readers.
   The way-level `O4_ROAD_CONTACT_CAP_SCOPE` gate DISSOLVES into this:
   end-on contact binds values and never caps any station; lateral
   contact caps exactly the stations it touches. The CYXY +130
   lateral_contiguity rows and item-4's 1 %-held ramp both fall out.
2. THE DOWNSTREAM AIRSIDE CHANNEL (chartered, mechanism-before-fix):
   1,756 solve-owned airside nodes move at HECA concentrated at item-4's
   apron (worst 2.07 m) via a re-derivation AFTER the profile pass
   (candidates: seat_groundside_on_law, ribbon conformance, final
   projection anchor-reach). FIRST measurement of the round: who_wrote
   at 30.11445,31.40993 in the profile-ON arm. LAW: airside solves first
   and NEVER re-derives from road inputs — whatever pass re-seats an
   apron from a road value is the defect, whatever the fix costs.
   Solve-owned moved airside = 0 stays the gate.
3. Flip-ON conditions restated: all four owner sites monotone/lawful at
   their per-station caps (item 4 back to the 9.35 % class, item 2's
   U-loop lawful under path pricing); CYXY/SPJC/OTHH totals not
   worsened, residuals attributed; solve-owned moved airside 0; all
   four controls + LEMD built.
