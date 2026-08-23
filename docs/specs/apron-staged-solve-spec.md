# Apron staged solve — movement surfaces first, interior conforms (Fable
# spec, 2026-08-21; owner "proceed"; under RULINGS 2026-08-21b/c and the
# standing "airside is king" precedence)

Basis (lane/compose v1-v3, 2026-08-21): with the apron interior priced at
the 5 % ramp cap, NO violation on any airport carries the 5 % cap, yet the
strict class (frontage chords + corridor-crossing ring edges) worsens
monotonically as the interior is freed — HECA within_shape airside 770 →
1,383 → 2,368 (v1→v3); CYXY passes every arm (17); SPJC ~+20 in all. HECA
exits UNCERTIFIED (over_cap 26,958, 4,097 both-hard). The projection is one
Jacobi/POCS sweep over peers, so the pinned contradictions' residual
spreads onto whatever is free, and a freer interior lets more of it land on
the movement surfaces. The law says the movement surfaces hold strict
ALWAYS and the interior conforms — the solve must encode that precedence.

## The law of precedence (mechanism, not a new cap)

1. Within an APRON, the MOVEMENT-SURFACE nodes are the senior set: every
   node that is an endpoint of a strict pair under `classify_pair` (a
   frontage chord, a frontage edge, a corridor-crossing edge, a spine pair)
   or of a bound transect row (`xsection_spans`). Everything else on the
   apron ring is INTERIOR.
2. The final projection runs the apron in TWO sub-stages inside stage A,
   reusing `feasibility_project_partitioned`'s frozen-set mechanism
   (one_solve.py:2919 — the airside-then-groundside pattern):
   A1 — senior pass: strict pairs + transect rows + spine/runway law, with
        INTERIOR apron nodes FREE but carrying NO law edges of their own
        (their 5 % interior pairs are withheld in this pass; the carrier
        smoothing stays).
   A2 — interior pass: senior nodes FROZEN (data), interior pairs at 5 %
        projected, interior nodes the only movers.
   The existing global stage B (groundside) follows unchanged with all of
   stage A frozen, as today.
3. ONE partition function, both readers: `grade_law.apron_node_seniority`
   (node → SENIOR/INTERIOR from the same predicates `classify_pair` uses),
   exported to the sidecar as a per-node flag on the apron ring
   (`apron_seniority`), so the census can report strict-class rows whose
   senior node moved in A2 (must be 0 — the twin for "nothing moves after
   the senior pass").
4. Certificate: report A1's and A2's `over_cap`/both-hard separately. A1's
   both-hard residue is the honest pin-contradiction number for the
   anchor-placement docket (which pins, by family) — print the top 20 by
   excess with their pin sources (runway anchor / seat / seam pin / CIFP).

## What this does NOT do

5. No cap changes; no pin changes; no new vertices; no change to the
   transect kernel or the population predicate (A1/A2 of the population
   spec stand). Groundside untouched. Kill switch
   `O4_APRON_STAGED_SOLVE` default ON; flag-off == compose-v3 byte-for-byte.

## Acceptance (lane/compose continuation; harness builds; composed census)

6. Twins: (a) synthetic apron + 2 pads + 1 corridor + a transect: after the
   full projection, every senior node's value equals its A1 value exactly;
   interior pairs at 5 % satisfied or reported; (b) seniority partition
   identical between bake and census (sidecar round-trip); (c) flag-off
   byte-identical to compose-v3 on CYXY; (d) an apron with no movement
   surface (no pads, no corridor) has no senior set and projects as today.
7. Builds: CYXY, SPJC, HECA. Per-airport airside ≤ 75 / 189 / 1,487 — ALL
   three. Report the battery→v3→staged table for adjudicated/airside/
   within_shape (by cap)/transverse/steps; census_rows_diff vs battery;
   airside_value_delta; [transverse-bind]; certificate A1/A2; the A1
   both-hard top-20 with pin sources; [writeback-band] >10 m = 0.
8. SPJC residual: if it still exceeds 189, split as before (hairline
   1.02-1.10 % on -10113 vs the weld cluster at (-12.021394,-77.110990));
   the weld cluster is a seat/weld docket item, not this lane's.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; a senior node
moving in A2 is a STOP (fix the freeze, never the count); any airport's
airside above its bar after attempt 2 is a STOP with the A1 both-hard
top-20 attached — that list IS the next round's brief.
