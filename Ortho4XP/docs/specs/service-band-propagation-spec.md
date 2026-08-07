# Service-band propagation — edges must bind — spec

Author: lead (Fable), 2026-08-07. Charter: the 2026-08-07 owner
ruling "Service routes are taxiways at a larger cap; EDGES MUST
BIND" (RULINGS — read the verbatim). K1 measured every service edge
inert (byte-identical patch withheld); the owner rules that a
defect. Recorded suspect from cycle-8's own measurement: service
stringing fires 4/389 segments at SPJC — sliced-road nodes at edges
vs the 1.0 m perpendicular tolerance.

## Job 1 — confirm the limiter (attribution before fix)

One measurement pass at SPJC + HECA: why does band propagation along
service edges fire ~0x? Confirm (or refute, with the real mechanism)
the stringing-tolerance suspect: sliced-road nodes landing ON
segment edges vs the perp tolerance. Quote firing fractions per
airport, and the node-geometry class that fails (distances,
canonical ids). If the mechanism is NOT the recorded suspect, STOP
after Job 1 and report — the fix half of this spec assumes it.

## Job 2 — the fix

Make service stringing string the route: repair at the
slicing/stringing site so the band propagates edge-by-edge from the
mouth seat, consistent with node-identity law (shared boundaries
spelled once; no proximity semantics beyond the tolerance's ruled
meaning; repair at mint, never post-weld).

Acceptance:
1. **K1 INVERTS**: with `O4_PROBE_NO_SERVICE_EDGES=1` the patch now
   CHANGES (edges bind). The gate stays; its inertness twin flips to
   an effect twin.
2. Stringing coverage: SPJC 4/389 → ≥90% of service segments strung,
   or the lawful remainder named per segment.
3. Groundside seats derive from route bands: two specimens (one
   building, one lot) whose seated values trace along the route from
   a mouth seat by canonical identity.
4. **Airside untouched**: airside census cells and airside emitted
   values identical to the receiver-only arm (receiver-only direction
   is law; band propagation is groundside-side). Any airside delta
   is a STOP.
5. Battery matched controls; every groundside moved row attributed.

## Job 3 — the last road-merge blocker (independent measurement)

Attribute the cycle-9 airside-view world-asymmetry: +110 @10k /
−381 @−500 (the `within_shape::apron|apron` carrier that survives
receiver-only). Decomposition first on existing arms (census
--rows-json is on the lane); at most TWO pre-registered knives.
This is the remaining unattributed carrier in the owner's road-feed
merge table — the thread's merge gate re-reads after it.

## Protocol

Work on lane/c9feed (tip 717e67e) in its worktree. blast.py on every
file. Builds via harness + run_with_ledger, body-sha discipline,
warm cache. Budget: 6 builds hard cap 8 across both jobs (Job 1 is
offline-first). Known noise: o4_library_index_*.cache contamination
flag (chored; matched arms carry it identically). Deviations:
STOP-and-report for Fable review. DO NOT MERGE — the road-feed merge
stays the owner's gate.
