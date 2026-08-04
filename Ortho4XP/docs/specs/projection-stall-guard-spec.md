# Projection stall guard: stop paying for the infeasible

Fable spec, 2026-08-04. From the convergence round's STOP (scratchpad
convergence/ — read it first; its traced metrics are this design's
evidence). Lines against 32452a1. BINDING: docs/RULINGS.md.

**Mechanism (attributed):** under the band envelope, each capped
projection's max residual is pinned from ~sweep 2 by ONE genuinely
inconsistent pair (anchor VALUES vs the cap graph: L−U == residual to
6 dp) while the solver still reduces tens of thousands of violating
edges (HECA call 1: 60,634 → 7,195, last reduction sweep 1,700).
Residual-keyed termination is UNSAFE (would 2× the shipped violations);
state-delta keying misses limit cycles (active count RISING 1.1-1.6
mm/sweep forever).

## The guard (gate `O4_PROJECTION_STALL_GUARD`, default "0", implied ON
## by `route_metric_envelope_enabled()` — the existing implication idiom)

In the chromatic sweep loop: track the ACTIVE VIOLATING-EDGE count's
running minimum; a new minimum counts only if it improves the old by ≥
`STALL_REL_IMPROVEMENT` (0.005); if no qualifying minimum for
`STALL_PATIENCE_SWEEPS` (16) full passes, TERMINATE the projection and
REPORT (write-only, existing forensics channel): sweeps spent/saved,
final active count, and the carrier pair(s) of the max residual with
their L−U adjudication class — these are the drain-list value defects.
Constants named, Fable-owned (not owner constants).

## Acceptance (pre-register per airport before each arm)

(a) full census + check_grade deltas ≤ materiality (0.01 m-class) in
BOTH frames, all five airports — the guard fires only after productive
work ends, so the shipped surface must be ≈ what it already ships;
(b) sweep counts vs convergence/'s table (HEAZ CAND toward ~8.4k, HECA
toward ~15.5k; OFF arms must NOT terminate early anywhere — verify
the implication gating means OFF never enters the guard, byte-identity
gate-off on the three NEW baselines);
(c) the report names the carrier pairs (join the drain list);
(d) suite: same 23 reds;
(e) exclusive re-time all five airports (check_build_time, foreground,
3 runs/arm) and the UPDATED APPROVAL PACKET (target: SPJC/HECA CAND
deltas near zero vs their OFF; HEAZ well under budget).
Convergence guards: this is the family's attempt 2 (the residual metric
was attempt 1) — a miss on (a) or (b) is a STOP with attribution.
