# Site-first re-open — the owner's standing sites ARE the acceptance
# (owner review round, 2026-08-29)

Owner, on 1.0.267: "all the trouble spots I reported still exist with
only very minor differences... review the changes that were made and why
they passed without actually fixing the bugs."

## The review's findings (recorded so the failure mode cannot recur)

1. hecar5 item 1: the deck stand-down was real, but the spec bar (zero
   tear rows, ≤0.05 m) was NOT met — the lane honestly reported worst
   |de| 2.56 m remaining; the Fable review merged below the bar and
   summarised "tear gone". THE RULE: a spec's acceptance bar is not
   satisfied by improvement; a below-bar merge requires the owner's
   explicit sign-off with the residual quoted.
2. Rounds 5b→5k: item 4's 9.35 % was proven in an arm whose mechanism
   (way-level scoping) was later DISSOLVED; in the successor
   configuration the same site re-measured 163 % (5d) and 152 % (5e) —
   flagged in lane reports — while subsequent rounds optimised the
   airside gate and census arithmetic. The family shipped (owner-
   ordered skip) with the sites last measured OPEN, and the lead's
   summaries still carried the retired arm's number. THE RULE: every
   round's report re-quotes the OWNER-SITE numbers in the CURRENT
   configuration, first, before any instrument metric; a configuration
   change invalidates every site number measured before it.
3. What IS verified present in the owner's own 1.0.267 patches: LEMD
   wall-top station law (cross-band 0.00), corridor width/centring
   (12.7 m, envelope), OTHH claimed-corridor walls, CYXY terrain
   (R18-1c), HECA deck removal. The sim-visible residuals concentrate
   in the ROAD-RAMP sites and the runway crossing.

## The re-opened sites (each closes at ITS coordinate, current config)

- HECA runway crossing 30.1076307,31.4094328 — its own spec
  (runway-crossing-strict-claim-spec.md).
- HECA item 2: 30.1066499,31.4007725 → ramp → weld at
  30.1052938,31.3989669 (owner patch today: junction still spans
  104.11–108.56 — cliff intact).
- HECA item 3: 30.1044752,31.3966654 → 30.1046554,31.3973678 (road
  tops 105.87 vs junction 106.88 — still ~1 m short).
- HECA item 4: 30.114984,31.4107959 (road 93.07–97.65 vs apron 98+).
- CYXY road: 60.7100244,-135.0727863 → 60.7087015,-135.0746305
  (self-pins measured 0.270 m in-lane; VERIFY on the owner-frame
  build).
- NEW — HECA apron over-extension (owner 2026-08-29c): the line
  30.1135641,31.4088047 → 30.1149573,31.4106698 is the apron's
  authored BACK EDGE (a wall; apron elevated above groundside parking
  lots; the package sends no pavement across it). MEASURED on the
  owner's patch: apron shape -10584 (shapeID 584, 143 nodes) covers
  EVERY station of that line — and the OSM airports feed has no apron
  polygon there, so the footprint is pipeline-built or ADOPTED.
  Prime suspect: the §H2 lot-adoption class (apron absorbing the
  groundside parking lots). Attribute which pass gave 584 its
  footprint (classification sidecar / adoption logs), then the apron
  ends at its authored edge; the wall stands; groundside lots stay
  groundside at their own law. This site likely interacts with item 4
  (30.114984,31.4107959 sits at this apron's corner).

## Open mechanism question for items 2/3/4 (measure FIRST)

Why does the shipped per-station configuration not build the ramps the
way-level arm built? Candidate (from 5e's own twin: "a 1 % station
between two pins refuses a 4 m rise"): the lateral walk caps the
stations AT the apron edge at 1 %, choking every ramp at its top.
RULINGS 2026-08-28e says "once it LEAVES the apron it can descend at up
to 8 %" — the owner's "leaves" is the departure edge, not lateral
proximity. Derive where each of the three sites' stations get their 1 %
from; if apron-edge lateral adjacency is the choke, the adjacency read
must exclude the departure corridor of an end-on road (the first
half-width of run off the contact edge is part of "leaving").

## Acceptance

SITE-FIRST: each coordinate above closed at its class (monotone ramp /
weld step law / pit gone) measured on the CURRENT default configuration
and quoted first in every report; census law-true totals not worsened,
residuals attributed; no instrument metric substitutes for a site.
