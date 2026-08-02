# Quarantine retirement, round 1: the terrain-pinned pair export

Fable spec, 2026-08-02. Owner law (RULINGS.md): quarantine is
UNAUTHORIZED; zero breaks in paved areas; full-census counts. Line
numbers against `9a28151`. Sized by the breaksrc decomposition
(scratchpad `breaksrc/` — read it first; its per-node source map
`HECA_sources.json` is the pre-registration substrate).

**Mechanism (attributed):** the terrain-pinned pair export at
`solve.py:5630-31` (+ the deferred-ring branch `:5682`) mints 94.2% of
the residual break nodes (4,665 of 4,952 at HECA): when an incident law
edge exceeds `budget + 0.03 m` and one endpoint is terrain-pinned, it
quarantines BOTH endpoints — a node-scope quarantine for a pair-scope
law failure, never consulting any envelope. 55% of its nodes are
dragged-in free partners; 36.7% have no violation of their own; it is
the sole cause of 5,714 hidden validator rows. 96% of its firings are
on the LATE final projection's exit state. The genuine conflict inside
it: 582 nodes with a ≥1.0 m own-law deficit (strip-weld DEM pins and
apron classes).

## The change

Gate `O4_RETIRE_TERRAIN_PIN_QUARANTINE`, default "0" this round. Under
the gate, the export at `:5630`/`:5682` writes NOTHING into the break
sidecar — the law reports what it finds. PRE-CONDITION to verify by
code reading before implementing (STOP and report if false): the export
writes only the sidecar/break bookkeeping, never elevations and never
anything a later stage reads back — i.e. the emitted BODY must be
byte-identical under the gate. Everything else untouched: the A2/A3/
A4/B3 minters (287 nodes total) stay this round; the service-road
second envelope engine (`anchors.py:2289-2318`, 74 nodes) is REPORTED
as the remaining one-engine violation, not changed.

## AMENDMENT (2026-08-02, Fable ruling after the pre-condition STOP)

The pre-condition's clause 2 is FALSE: `_projection_broken_idx` also
feeds `layout._final_projection_broken_keys` (solve.py:5751-5762) →
the NEXT final projection's `pre_broken` (:5104-5111, ungated) →
`immovable` (one_solve.py:2517-2532) — a load-bearing freeze, not
bookkeeping. RULING: **shape (a), FULL retirement.** Under the owner's
law both effects are quarantine; a sidecar-only split would leave the
unauthorized freeze operating. Supporting facts: the 202 carried
blockers are ~all groundside/service (4 airside), own-law deficits
p50 0.121 m with 66/192 at no violation, and freezing free groundside
nodes as input to the late airside projection independently violates
airside-is-king. The released nodes fall under the band-governed
envelope like every other free node.

Under the gate, the export at :5630/:5682 contributes NEITHER to
`_break_node_ll` NOR to `_final_projection_broken_keys`. The other
minters' contributions to both stay untouched this round.

Acceptance §§1-2 are REPLACED by:
1. Gate-off byte identity unchanged (CYXY `dcebb6ff…`, SPLP
   `c2316222…`, HECA repaired `9a49cbce…`).
2. Gate-on HECA (all three gates): the surface delta vs `9a49cbce…`
   is MEASURED and must be confined — movers within the released
   nodes' neighbourhoods (identity-join the moved set against the
   ~165 released + their law-graph neighbours; an unexplained mover
   population is a STOP); census cliff count NOT up (≤138); census
   total row count within ±2% of 8,179; check_grade actionable
   quoted (expected ~8,000-8,200 per the zero-quarantine reading);
   sidecar break nodes 4,952 → ~287; the pre_broken carry 375 → ~173
   verified from the probe instrumentation; the owner's reference
   sites unchanged or improved.
Original §§3-5 stand (HEAZ remainder, unit test — now asserting BOTH
effects retired — suite, build-time).

## Acceptance (original — §§1-2 superseded by the amendment above)

1. Gate-off byte identity: CYXY `dcebb6ff…`, SPLP `c2316222…`, HECA
   repaired-arm body `9a49cbce…` (with the two fix gates on and this
   gate off).
2. Gate-on HECA (all three gates): emitted body BYTE-IDENTICAL
   `9a49cbce…` (the pre-condition, proven); sidecar break nodes
   4,952 → ~287; check_grade actionable 2,294 → ~8,000-8,171 (the
   truth the owner ordered); census total row count UNCHANGED (~8,179);
   the newly-visible population's magnitude profile matches the
   decomposition (p50 ≈ 0.04 m — mostly sub-decimetre, with the
   582-node ≥1 m class enumerated by role for the next fix spec).
3. HEAZ gate-on: break nodes 398 → report the remainder (HEAZ was not
   decomposed; its split is a deliverable here, cheap).
4. Unit test: a synthetic terrain-pinned over-cap pair is REPORTED, not
   quarantined, under the gate; quarantined as before without it.
5. Suite: no new reds. Build-time: ~nil (bookkeeping removal); quote.

## Out of scope

The 582-class value fix (next spec, from this round's role census);
A2/A3/A4/B3 retirement (round 2, after this round proves the pattern);
the service envelope engine unification; validator changes
(check_grade already honors an empty break list — nothing to change);
the standards-gap review (parallel track).
