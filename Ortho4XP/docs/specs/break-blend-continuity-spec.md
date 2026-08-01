# Break-blend continuity: the interpolation weight must be continuous

Fable spec, 2026-08-01. Small, compartmentalized (owner protocol). Line
numbers against `fa5aad0`.

**Mechanism (attributed, exact):** the break blend
(`one_solve.py:1884-1886`) interpolates `elev[i] = hi + (lo-hi)*t` with
`t = dc/(dc+df)` where `dc`/`df` come from `_reach_plain`
(`one_solve.py:1607`), a VALUE-ordered Dijkstra whose `dist[k]` is the
distance of whichever value-winning path happened to win — NOT a
continuous function of position. Adjacent vertices inherit distances
from different paths; at the owner's example site two nodes 0.7 m apart
got t 0.490 vs 0.84-0.90 and an 8.9 m pit over flat DEM (Δt × the
pocket's 22.4 m deficit, to the centimetre). Airport-wide: 80% of all
≥2 m close-pair steps inside break regions carry |Δt| ≥ 0.1; where t is
continuous the surface is smooth. The comment at `one_solve.py:2234`
("the blend is continuous, so the break region is a smooth [surface]")
is FALSE as shipped and must be corrected to describe the fixed
behaviour.

**Context ruling:** the quarantine machinery is scheduled for retirement
(owner: zero breaks in paved areas; the route-metric envelope spec is
the drain). This fix is the INTERIM: while any break region exists, its
painted surface must at least be continuous. It must not entrench the
blend — no new capability, only continuity.

## The fix

Compute the blend weight from a CONTINUOUS field: a separate
distance-only multi-source pass (plain metric Dijkstra from the ceiling
witness set and from the floor witness set over the same edges the
blend already uses), used ONLY for `t`. The value fields keep their
existing semantics untouched — this changes no envelope, no witness, no
break membership, only the interpolation weight inside already-broken
pockets. The `else 0.5` degenerate branch: keep, but it must now be
unreachable except where both distance fields are genuinely zero
(same-node witness); assert-count its firings into the existing
forensics row (`t_fallback` count) so the "which branch fired"
question from the attribution report is answered by production.

Gate: `O4_BREAK_BLEND_CONTINUOUS`, default "0" this round (flip is a
separate decision after the battery). Gate off ⇒ byte-identical.

## Acceptance

1. Unit test: a synthetic pocket where two adjacent nodes previously
   received discontinuous t now grade smoothly; the degenerate branch
   counter fires only on the constructed same-node case.
2. Gate-off byte identity: CYXY `dcebb6ff…`, SPLP `c2316222…` (note the
   NEW SPLP baseline — corrected CIFP), HECA α body `4be7fb4b…`.
3. Gate-on HECA α build: (a) the owner's example site
   (30.106022/31.395272) — the five-vertex ring reads smooth (no ≥2 m
   step between the former 90.06 pair and its 98.8-99.1 neighbours);
   (b) his other two coordinates re-read; (c) full-severity census
   (severity/census.py): cliff subset (Δz≥2 m over ≤10 m) expected to
   drop by the ~80% |Δt|-carried share — pre-register the exact number
   from the alpha_cliffs Δt table before building; (d) break-node
   POPULATION unchanged (this fix must not move break membership — if
   it does, it did more than the weight).
4. Cost: one Δt-continuity pass ≈ one extra Dijkstra per projection —
   quote from the phase ledger; if ≥1% of the auto-patch budget, stop
   and report per the hard law.

## Out of scope

The route-metric envelope (its own spec, sized by the running
counterfactual); the quarantine retirement; any change to break
membership, witnesses, or values.
