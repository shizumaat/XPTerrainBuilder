# The unified law band — the reach band is the projection of the FULL
# law graph, narrowed before seating and before the solve (Fable spec,
# 2026-08-27; owner ruling RULINGS 2026-08-27 "REFINE THE REACH BAND
# FIRST")

Owner: "The calculation has to be done at some point, seems as good or
better to refine and narrow the reach bands first, then we shouldn't
need nearly as much convergence later. Consider how we can build the
fully constrained graph as efficiently as possible."

## §0 Measured frame (patch `/tmp/harness/HECA_20260827T113319.osm`,
## corrected package data; traces in /tmp)

- building25: route-only band `[77.74, 134.38]` — 56.6 m wide, because
  the binding route to the 05C/23C anchor (106.06) is 1,752 m at 1.5 %
  (budget 26.28 m) and the local off-route leg is only 2.04 m
  (`/tmp/building25_route.kml`). The ring-median seat picked 82.52.
  The apron-207 vertex 72.1 m away (1 % chord budget 0.72 m) solved at
  92.00 — both endpoints individually in-band, the pair 9.77 m over
  cap (`/tmp/building25_chord.osm`). The frontage trace
  (`/tmp/building25_frontage.kml`, per-ring-vertex band ceilings) is
  the seat-side evidence — the implementation lane incorporates its
  numbers here.
- The band graph today contains NONE of the 88,605 published no-step
  direct-distance edges, none of the frontage chords, and none of the
  membrane law edges — three law populations the band cannot see.
- building146 pre-data-fix: contradictory pavement data produced a
  silent bad seat (12.42 m chord); under this spec it produces an
  EMPTY interval and a loud refusal naming the site.

## §1 THE LAW

1. **ONE BAND, FULL GRAPH.** `reach_band_unified`'s per-node interval
   becomes `[max_a (v_a − d_law(a,n)), min_a (v_a + d_law(a,n))]` over
   runway anchors `a`, where `d_law` is the shortest-path BUDGET in
   the full law graph: the existing route-spine edges and local
   off-route leg, PLUS (a) pad frontage chords (the 2026-08-25
   chord-anchor law's own population and caps), (b) the apron membrane
   law edges — lattice, spine-station and ring within-shape edges,
   which exist PRE-FREEZE since round 3, and (c) the no-step
   direct-distance enumeration — the SAME list the sidecar publishes
   and the census prices (one population; the band gains no private
   second notion of any law). Every budget is cap × distance ≥ 0.
2. **NON-NEGATIVITY IS A PINNED INVARIANT.** The 2026-08-13
   reach-envelope blowup (signed slabs → negative-cycle Dijkstra,
   26–56 GB SIGKILL) is the failure class one signed budget away; a
   twin asserts every edge weight ≥ 0 at graph-build time and
   `O4_ENVELOPE_DIAG=1` remains the loud abort.
3. **ORDERING.** Geometry → lattice/stations constructed (round-3
   slot) → THE BAND (full graph) → seats → solve. Seats consume the
   narrowed ceilings through the unchanged median rule; the
   pairwise-seat-rule alternative is SUPERSEDED by this spec.
4. **EMPTY OR INVERTED INTERVAL = LOUD PRE-SOLVE REFUSAL** naming the
   node's lat/lon, both binding anchors and both binding chains (the
   bad-data detector: the building146 class refuses instead of seating
   nonsense; feasibility-is-guaranteed made executable). Refusal
   before any patch is written.
5. **EFFICIENCY (the owner's directive; design requirements, the lane
   refines with measurement):**
   (a) ONE multi-source Dijkstra per bound direction — ceiling sources
   = runway anchors at `v_a` (relax downward-slack), floor likewise —
   over the full graph; never per-node queries. O(E log V);
   E ≈ spine edges + ~90k published law edges + membrane edges,
   V ≈ 140k at HECA — expect seconds, measure and report.
   (b) EXTEND `reach_band_unified`'s edge iterator — never a second
   engine (`trace_reach_route`'s history is the cautionary tale).
   (c) BUILD ONCE, FILTER PER CONSUMER: the no-step k-NN edge build
   (cKDTree, 8-sector) moves BEFORE the band and its one enumeration
   is shared by band, solver pass-2 and census (single-pass
   principle). The frontage-chord and membrane edge sets likewise
   come from their existing builders, not fresh scans.
   (d) SEATS INCREMENT, NEVER RECOMPUTE: a placed seat joins the
   anchor set and re-relaxes only its improvement region (bounded
   Dijkstra from the new source, early-exit where no bound tightens).
   A twin proves incremental == full recompute on a fixture.
   (e) The attachment-cell grid lookup for off-graph queries stays.
6. **CONSEQUENCES, measured not assumed:** the two-pass no-step
   conform and the crossing-adoption pass REMAIN as validator-side
   safety nets; report their residual populations on the narrowed
   band (expected to approach no-op). Retiring either is a later
   owner decision on that evidence, never this lane's.
7. Flag `O4_BAND_FULL_LAW_GRAPH`, default ON; OFF byte-identical.

## §2 Twins

- Wide-route fixture: pad whose route-band is ±20 m but whose frontage
  chord to a 90.0 apron narrows the ceiling to ≤ 90.9 → seat lands
  inside the narrowed interval; flag OFF reproduces the wide band.
- Contradictory fixture (the building146 class): frontage chord
  demanding ≤ X and membrane path demanding ≥ Y > X → empty interval,
  loud refusal naming the node, no patch written.
- Non-negativity: a synthetic negative budget is refused at
  graph-build (never fed to Dijkstra).
- Incremental seat anchor == full recompute (§1.5d).
- OFF byte-identical on a full synthetic build.

## §3 Acceptance (ONE HECA build + SPJC/CYXY/HEAZ; census A/B vs
## `HECA_20260827T113319`)

- building25: band before/after at the pad (expect ~56 m → few-metre
  width bracketing the local surface); seat consistent with the south
  frontage; the 9.77 m and 9.09 m rows GONE — or a refusal naming
  genuinely-contradictory data (report which; the owner adjudicates
  data vs law).
- `airside_no_step` census: report the decrease (2,293 baseline) and
  the conform passes' residual populations (§1.6).
- Dip site, line T, item-2 crossing line: re-read and report.
- HEAZ: still builds (the stand-down retry and the narrowed band
  compose; if the narrowed band refuses HEAZ pre-solve, that is a
  FINDING to report with the named nodes, not a failure to hide).
- SPJC/CYXY matched flag-off controls; senior byte-identity is NOT
  expected here (the band lawfully moves seats) — instead report seat
  deltas with their binding constraints.
- Build-time: the band phase cost quoted explicitly (≥1 % statement
  expected; gates suspended, statement mandatory); no timing claims.
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, heartbeat; no shared-repo writes.

## Amendment 1 (Fable, 2026-08-27 — owner ruling "3": the §1.4 refusal
## is REPORT-FIRST pre-ship)

The lane's §1.4 refusal surfaced exactly one contradictory anchor pair
at HEAZ (3104 at 81.10 vs 3281 at 86.14, 5.04 m over a 4.38 m 15-hop
budget) and would block that airport at main tip. Owner ruling: the
§2-instrument precedent applies — pre-ship, an empty/inverted interval
is a LOUD REPORT (the same message §1.4 specifies: lat/lon, both
anchors, both chains, plus a sidecar record `law_band_contradictions`
the census prints), and the build CONTINUES with the pre-band behaviour
at the affected nodes. `O4_BAND_LAW_REFUSE=1` restores the hard
refusal (the diagnostic/ship-gate arm; default 0 pre-ship). Promotion
to refusal is a ship-gate ruling, adjudicated with the accumulated
contradiction ledger. The HEAZ pair itself remains an open owner
docket (runway seat vs chain cap), carried in DEFERRED_VERIFICATION.
