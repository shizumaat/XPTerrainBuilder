# Creation-order seniority — minted geometry defers (Fable spec,
# 2026-08-21; owner ruling RULINGS 2026-08-21e)

Basis: SPJC's 22-row emit-minted class. 114 of 142 residue T-junctions are
minted AFTER the final projection by ring-minting emitters (adjacent-ground
band emit, gap-fill spines, crown completion, densify, tile cuts); the
post-projection welds then join them at values two authorities set
independently. Two weld reorders were law-neutral — ordering alone cannot
reach geometry that does not exist yet. The ruling: later-minted geometry
DEFERS to the surface that exists.

## The mechanism — a CONFORMING MINT, one function

1. `grade_law.conforming_mint(senior_value, junior_ring, position, cap)`:
   when any pass creates a vertex or adjacency against an already-settled
   surface, the minted vertex takes the SENIOR surface's value at that
   position (the ring that was there first; interpolated along its edge —
   the same linearity the census reads), and the JUNIOR ring conforms its
   own neighbourhood by a bounded monotone walk under ITS cap from the
   weld value outward (the F3c walk shape: descend/ascend at ≤ cap until
   the existing junior values are met; touch only junior vertices within
   the walk's reach; never move a senior vertex). By construction the
   minted adjacency and the walked sub-edges are within cap.
2. SENIORITY = CREATION ORDER: solve/projection output > earlier emitter >
   later emitter. Each ring-minting pass declares its rank (an explicit
   ordered registry in pipeline.py — the pipeline's own part order is the
   rank; no new constants). At a junction of two junior rings, the earlier-
   ranked one is senior; ties by shape id (deterministic).
3. RETROFIT SCOPE (this round): the two post-projection weld passes
   (epsilon-wedge + nid-level — the verify-only counts 142/68 become the
   conforming mint's work list) and the ring-minting emitters that feed
   them (adjacent-ground band emit, gap-fill spines, crown completion,
   densify, tile cuts) — each pass's INSERTS go through conforming_mint.
   Passes that only move values are untouched.
4. The loud residue lines flip meaning: after this, a nonzero
   post-projection insert count is lawful (the mint conforms), but a
   minted adjacency OVER CAP at emit is a STOP counted on its own line
   (`[conforming-mint] minted N, walked M junior vertices, over_cap 0`).

## Lockstep

5. The census prices minted adjacencies as ring edges (it already does —
   that IS the 22-row class); with the mint conforming, those rows
   disappear because the surface is lawful, not because the census looks
   away. No census change. The walk's touched vertices are recorded in
   the sidecar (`conforming_mint_walks`: position, senior rank, junior
   shape, reach) so a census row inside a walk region is attributable.

## Twins

6. (a) Synthetic senior ring + junior emitter mint: adjacency within cap,
   senior vertices bit-identical, junior walk monotone at ≤ cap;
   (b) two junior rings: earlier rank wins, deterministic tie-break;
   (c) zero-mint airport byte-identical; (d) the walk terminates (reach
   bounded by demand/cap) and is idempotent; (e) census-vs-sidecar walk
   regions round-trip.

## Acceptance (lane/compose; budget discipline)

7. Fastpath: on the A4/weld-arm SPJC patch, list the 22 rows' junctions
   and predict which mint (which emitter rank) owns each.
8. ONE SPJC build: the 22-row emit-minted class → 0; `[conforming-mint]`
   over_cap 0; rows_diff confined to the weld regions; SPJC number
   reported honestly (the 26 projection-residual rows are the parallel
   read's item, not this spec's).
9. Fastpath re-price HECA/CYXY; rebuild only if rows_diff shows movement
   beyond walk regions (a STOP anyway). Usual instruments;
   [writeback-band] > 10 m = 0.

Pre-delegated: materiality 0.01 m; attempt cap 2 then STOP; a senior
vertex moved by a mint is a STOP; a minted adjacency over cap at emit is a
STOP; any airside increase anywhere is a STOP.
