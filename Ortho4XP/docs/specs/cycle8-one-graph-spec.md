# Cycle 8 — ONE graph: groundside joins the route graph

**Status: BINDING.** Implements three owner rulings (RULINGS
2026-08-06): "ONE graph", "Service-road mouths seat like apron-edge
buildings", "Frontage coupling ⇒ band seating" — composed with the
standing law (airside is king / receiver-only; DEM is a seed;
groundside terrace law unchanged for ground BETWEEN pavements).
Baseline: the c8base frame of record (c8base worktree,
tmp/c8base_record.md; tip 6f59c5e; worlds −500/10,000). Mode:
BUILD-COMPLETE-THEN-DEBUG.

## The mechanism (ruled)

1. **Service-road centerlines become route-graph spine edges** with
   their 8% budgets — the same edge machinery as taxiways at their
   caps (REACH_NO_SERVICE_SPINES's exclusion inverts for GROUNDSIDE
   reach: airside reach still never rides service roads; groundside
   reach ONLY enters through them — direction, not deletion).
2. **The MOUTH** (service road ↔ airside pavement contact) is the
   interface node, seated exactly like an apron-edge building
   frontage: the airside apron meets it within AIRSIDE law (airside
   wins the seat) — reuse the SAME contact/frontage machinery
   (grade_law.runway_join_contacts pattern / the frontage band), one
   authority for "where a mouth is" and "what seats it".
3. **Bands flow mouth→outward**: lots (groundside aprons, 5%
   within-shape law) and groundside buildings (frontage off lots) get
   feasible bands from what their road routes reach, at groundside
   budgets. DEM chooses where within the band (seed, never bound).
4. **The seat ladder's LAW ISLAND branch dies for connected rings**:
   a ring reachable through the graph gets a band (the D′ class —
   HECA 2,646 rings / 52,878 vertices, KCLT 606). A ring with NO
   route/frontage/weld coupling is NOT SOLVED — left at raw DEM,
   and the census ADJUDICATES it out-of-scope via the SAME
   reachability predicate the solve uses (lockstep: coupling law and
   census land together — the frontage-gap lesson, RULINGS).
5. **Receiver-only, structurally**: no groundside value enters any
   airside constraint set. This is also the Q4 debt's cure.

## Pre-requirement (attribute FIRST, then extend)

**The analytic band is not world-invariant** (c8base finding: width
disagreements HECA 12,657 / KCLT 8,150 / SPJC 4,259 / HEAZ 1,417, max
71 m, ZERO coverage mismatches). Cycle 8 extends this band to
groundside — extend a lying band and D′ becomes a new mystery.
Attribute the disagreement mechanism (suspects: flex/anchor
world-dependence entering band seeds vs the analytic reader's law
pricing); a bounded fix lands first; an unbounded one is a
STOP-and-report before any extension code. The env_band 30–38% carry
shortfall (world-invariant → geometry/decimation) is NAMED context,
not required here.

## Acceptance (vs the c8base frame of record, both worlds)

- **D′ collapses**: the ≥10 m groundside band (4,815 rows, 96%
  groundside) → ≈0 minus named genuinely-disconnected exemptions;
  `[groundside-law-seat]` no_law_source only on disconnected rings;
  the 604/565/720 m and canyon 9,771–9,935 m worst rows GONE.
- **KCLT canyon svc spread gone** (the two-disagreeing-LAW-values
  class); fp#8's D′ carriers (KCLT canyon 5,781.77 / HECA −500
  554.69) off the table.
- **THE Q4 DEBT GATE (hard)**: airside adjudicated per cell ≤ the
  frame of record's (HECA −500 ≤4,707 / 10k ≤4,228; KCLT ≤502/886;
  SPJC ≤428/706; HEAZ ≤390/162) — a groundside round may not raise
  airside by one row.
- Battery re-censused both worlds incl. --magnitude-bands; suite
  FAILED-diff vs the 11 standing (the 12th — cycle 7.5's own DSF
  guard firing on its unfinished redirect — is a CHORE here: make
  the redirect effective in lane worktrees or register the mount;
  the new b5079c60 contamination path stops recurring).
- Twins: mouth seating (airside prices it), band-through-roads
  reach, disconnected-mints-nothing (census + solve same predicate),
  receiver-only direction.
- Named, report state: the KCLT −500 slab carrier (slab=[0.3,inf]
  binding one exit at 0.457 m post-floor).

Budget: attribution replays + ~8-10 builds (both worlds, 4 airports)
+ suite. Materiality 0.01 m; attempt cap 2 per part; heartbeat;
foreground; no real-DEM; no shared-repo writes.

---

## ADDENDUM (lead ruling from the Q4 STOP, 2026-08-06; derives from the
## owner's receiver-only law — flagged for owner ratification)

**THE FINAL PROJECTION PARTITIONS.** A shared projection IS a coupling:
fp holding groundside pairs in the same constraint set as airside is
how a groundside seat moved airside rows (+6 SPJC / +5 HECA — the Q4
debt). Ruled: airside projects FIRST with groundside pairs excluded
from its constraint set; groundside projects AFTER against the frozen
airside values (receiver-only, structurally, in every projection).
The measured-worse reorder (seats after fp, 434→493 — emit-time weld
re-adoption drags airside) is FORBIDDEN as the mechanism; the
partition is the cure. Acceptance: the Q4 gate re-run passes 8/8;
groundside census neutral-or-better.

**SERVICE STRINGING (the D′ finisher).** Service centerlines string
into spine_adj for GROUNDSIDE reach only (the airside exclusion
stands): the 1.0 m perp tolerance assumes taxiway-style node
placement; sliced service roads carry nodes at their EDGES (SPJC 4 of
389 segments string). Fix the stringing for service edges (their own
tolerance or edge-projection), never touching airside stringing; the
Q4 gate re-run is the guard. Expected: the concentrated D′ residual
(HECA 10 ways / KCLT 3 ways; way −12518's 132 still-at-seed nodes)
collapses; the KCLT canyon ≥10 m gs band (1,195) follows.
