# Weld before projection — emit-minted adjacencies enter the law (Fable
# spec, 2026-08-21; owner "proceed"; closes the 22-row SPJC class)

Basis (SPJC seat/weld attribution, lane/compose): the nid-level final weld
(layout.py:2325) inserts on-edge node references into welded partner ways
AFTER the bake and AFTER final_grade_projection — minting ring adjacencies
no law priced (22 of SPJC's 48 sub-5 m > 2x rows; endpoints within 9 mm of
baked nodes; the PAIR is new). The law-aware emit snap validates baked
pairs only. Values are single-authored everywhere (the 2026-08-08
seat-is-the-weld ruling holds); the defect is topology timing.

## The change

1. ORDERING. The nid-level final weld's insert step becomes a PRE-
   PROJECTION pass: run it (topology only — inserts at existing positions
   with the partner's authoritative z, exactly as today) before
   final_grade_projection (pipeline.py:6488), so the bake and the
   projection see the welded rings. The weld pass inside to_osm becomes
   idempotent verification: it may insert NOTHING new on a ring the
   pre-projection pass welded (count and assert 0; a nonzero count is a
   loud report line, not silence).
2. SCOPE. Only the nid-level weld insert moves. Sliver-corner repair,
   needle removal, on-edge moves, backfill, decimation, emit snap stay
   where they are (A1's measurement: the value channel dominates
   broken_by_emit; those passes are not this spec's territory).
3. LAW COVERAGE. Because the inserts now precede the bake re-walk of the
   final projection (the transect walk and the A4 nearest-spine sets are
   built at that point), the minted adjacencies are priced like any ring
   edge: ring-adjacent branch, A2/A3/A4 classification, MIN_PAIR_DIST_M
   floor unchanged. No new law; coverage only.

## Twins

4. (a) Zero-weld airport: byte-identical patch (the pass is a no-op).
   (b) Synthetic two-shape weld: the inserted adjacency appears in the
   bake and is priced; the projection conforms the sub-edge under its
   cap; the to_osm weld inserts 0.
   (c) The inserted node's z is the partner's authoritative value before
   the projection and may move WITH its ring in the projection (it is a
   normal node from then on); the seat-is-the-weld invariant holds at
   emit.
   (d) Idempotence: running the pre-projection weld twice inserts 0 the
   second time.

## Acceptance (lane/compose; budget discipline)

5. Fastpath first: on the A4 patches, count the adjacencies the reorder
   would newly price per airport (the emit log's insert counts are the
   upper bound: SPJC 68).
6. ONE build: SPJC (staged + transects). Target: the 22-row class
   collapses; SPJC airside ≤ 189 is the hope but NOT this spec's promise
   (the 26 projection-residual rows are a separate item) — report the
   number and the class split honestly.
7. Then fastpath re-price HECA/CYXY; full rebuilds only if the SPJC arm
   shows the reorder moves more than the weld class (census_rows_diff
   must show GONE/NEW confined to sub-5 m weld adjacencies and their
   immediate neighbours; anything else is a STOP).
8. Usual instruments; [writeback-band] > 10 m = 0; no timing; kill switch
   O4_WELD_BEFORE_PROJECTION default ON in the lane.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; any airside
increase on any airport (fastpath or arm) is a STOP; a to_osm weld insert
count > 0 on a pre-welded ring is a STOP (the two passes disagree on the
weld set — fix the disagreement, never suppress the count).
