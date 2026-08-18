# Road chord limiter — the road family joins the finalize-stage
# Lipschitz clamp (Fable spec, 2026-08-18; wave-3 step 1)
# Ruled basis: ROADS CARRY SPINES LIKE TAXIWAYS (RULINGS 2026-08-15
# evening); GROUNDSIDE PAVEMENT GRADES AT THE ROAD LIMIT (2026-08-12);
# ONE CORRIDOR = ONE LAW OBJECT (2026-08-12b); TRANSVERSE STAYS
# EUCLIDEAN (2026-08-18, RM (a)) — road faces stay chord-law, so the
# limiter enforces exactly the metric the census prices.

Problem, measured: `_grade_limit_groundside_chords` (finalize.py:452,
groundside.py:3718) clamps ROLE_GROUNDSIDE_PAVEMENT only. Road faces
(ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION) have NO chord limiter — the
frontage round's honest exposure moved area from chord-limited lots
onto unlimited road faces (+892 HECA groundside in the 2026-08-16
battery), and the A2 frontage cutback went default-OFF because the
unlimited-road-chord gap cost +286 HECA / +76 SPJC
(pipeline.py:4877-4886 names this spec as its re-arm condition).

## The law

1. **SCOPE.** The finalize-stage limiter runs over the road family —
   ROLE_SERVICE_ROAD + ROLE_SERVICE_JUNCTION — in the SAME unified
   pass as groundside (one shared-node key space, so road↔lot welds
   stay flush). ROLE_TUNNEL_RAMP is EXCLUDED (its law is the portal
   walk; touching it is a STOP).
2. **CAP.** Per-role from `ROLE_GRADE_LIMITS` — the road limit, one
   constant, per the standing ruling. A node shared between roles
   takes the STRICTER cap (flag the count in the report).
3. **CORRIDOR COHERENCE.** One corridor = one law object: the
   shared-node unification must span the corridor chain
   (rect↔junction↔rect) so the clamp cannot introduce steps at
   segment boundaries — the existing groundside unification mechanism,
   extended, not a second implementation.
4. **KERNEL.** The two-sided `_chord_cut_and_fill` (R7c posture), 4
   sweeps, same as groundside. Welds NOT pinned — the measured
   groundside lesson stands (CYXY way -10126: many-weld rings make
   pinning unlawful; emit precedence overwrites weld nodes anyway).
5. **A2 RE-ARM.** In the same lane, after the limiter's own acceptance
   passes: `O4_ROAD_FRONTAGE_CUTBACK` default flips to "1"
   (pipeline.py:4890). The env var stays as the attribution
   instrument.

## Acceptance (lane on the Mac; composed censuses per the harness)

1. Twins: (a) a road ring exceeding cap over an interior chord is
   clamped two-sided; (b) a corridor chain shares node values across
   its shapes post-clamp (no minted step); (c) mouth-weld values still
   win at emit; (d) with zero road shapes the groundside result is
   byte-identical to today; (e) tunnel_ramp untouched.
2. Censuses HECA + SPJC + CYXY: the road-face exposure prices down
   (the +286/+76 A2 arm deltas must collapse with A2 re-armed); the
   frontage witnesses hold (CYXY sink site stays 1 row / 0.39 m);
   per-family deltas reported vs the 2026-08-16 battery frame.
3. AIRSIDE BYTE-IDENTICAL on all measured airports — the limiter is
   a groundside/road-only writer; any airside pull is a STOP.
4. Build-time: one more role family in an existing late pass —
   expected far under the 1% gate; ledger tripwire, no timed run.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; if
road-vs-groundside caps disagree at a shared node, stricter cap wins
(report count); if corridor unification pulls airside values,
airside-frozen posture — STOP-and-report, never a partial clamp.
