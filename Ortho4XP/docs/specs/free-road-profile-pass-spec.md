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
