# EAT recognition scoping — routed wrap, vacuous bound, cut-only pin
# (Fable spec, 2026-08-25; implements RULINGS 2026-08-25c; companion to
# eat-anchor-rect-spec.md, whose mechanism is unchanged)

Evidence: the 2026-08-25 LEMD attribution — all 12 contradictory final-
band anchor pairs are EAT-pin vs EAT-pin; 149 pins over 9 values on the
14R (1.0-2.0 km) and 36R (4.2-4.6 km) corridors, owning shapes plain
apron/junction rings, 36R pins 59-66 m above adjacent DEM-seeded
pavement; the [empty-interval] 2,291-node empty polytope is the same
author. The owner rules LEMD HAS NO EATs.

## The three clauses (RULINGS 2026-08-25c)

1. ROUTED WRAP RECOGNITION. A crossing segment qualifies ONLY if a taxi
   CENTERLINE (the engine's own taxi-route set — apt.dat routes /
   recognized taxi centerlines; never service) crosses the corridor
   there, AND that route connects to the airside network on BOTH sides
   of the extended centerline (both route ends reach a runway anchor on
   the law graph — the standing "no taxi route to any runway anchor"
   guard candidate is subsumed, both-sides required). Pavement rings
   with no through-centerline in the corridor never qualify.
2. VACUOUS-SURFACE FAR BOUND. No rect beyond
   `D_clear = setback + tail_height / slope`
   (per the end's region constants and code letter — the distance where
   the regulation surface clears the tallest tail). No new tuning
   constant; this is the regulation's own geometry. `EAT_MIN_CROSSING_
   DIST_M` (300) stays as the near bound.
3. CUT-ONLY PIN. Compute the pavement's unconstrained reference at the
   rect (its band/seed level absent the EAT pin — use the value the
   node carries at pin time; the pin site runs after seeding). Pin only
   where `regulation < reference` (a cut), rect-level per the 2026-08-21
   rect-refusal ruling (any pin failing ⇒ judge the RECT: if the rect's
   regulation sits above its reference everywhere, the rect pins
   nothing). Never lift pavement to the surface.

## Mechanics

- Implement all three in/around `solver_primitives._build_eat_anchor_
  rect_pins` and its scoping helpers (`eat_end_projection`,
  `eat_scoping_bounds`) — extend, never fork; the rect construction,
  value formula, region table and the contradiction guard stay.
- The wrap test prices connectivity on the SAME graph/route set the
  solve uses (no second route notion); "both sides reach a runway
  anchor" reuses the law-graph reachability the guard machinery
  already has.
- Every refusal is LOUD with its clause: `[eat-scope] end 14R: rect at
  D=2030 REFUSED (no through-centerline / beyond D_clear=1280 /
  regulation above reference by +9.9 m)`.
- Gate `O4_EAT_SCOPING_V2`, default ON; OFF = today's recognition,
  byte-identical (for attribution arms).

## Twins

(a) Synthetic wrap (centerline crossing, both sides connected) at
    D=450 with regulation below reference → pinned exactly as today.
(b) Apron ring in the corridor, no through-centerline → no rect.
(c) Crossing centerline connected one side only (dead end) → no rect.
(d) Wrap beyond D_clear → no rect.
(e) Wrap with regulation above reference → rect refused, loud line.
(f) Flag OFF → byte-identical to today.

## Acceptance

- LEMD BUILDS: tools/harness/build_airport.py LEMD completes with ZERO
  final-band inversions and `[eat-scope]` refusals listing every
  former rect; the [empty-interval] count collapses (report the
  number); census the patch and report airside/groundside (a NEW
  fixture — no bar exists; the numbers found the bar).
- KCLT (the reference EAT airport): its real EAT rects SURVIVE
  recognition (report which rects pin, values unchanged vs a flag-OFF
  control build read from the same tree).
- KDFW: the rect-refusal behavior (2026-08-21 ruling) is preserved;
  report rect counts both flags.
- CYXY: byte-identical (no EATs).
- Attempt cap 2, materiality 0.01 m; STOP on second miss. No shared-
  repo writes, no timing claims.
