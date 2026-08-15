# Service-road law — roads behave like taxiways (Fable, 2026-08-15)

Owner rulings (2026-08-15, in-sim bug reports at HECA/CYXY): all roads
must be LATERALLY SMOOTH and WITHIN THEIR GRADE CAP, just like a
taxiway, carried by a spine; a road meeting a taxiway arrives AT the
taxiway's elevation (the runway rule, generalized); gap spines and
drainage stop at a service road.  Companion fixes already in lanes:
mouth proximity anchors (mouthweld), gap-spine subdivision (gapstop),
curved-road chord rects (luneix).

## Measured premises (road-architecture recon, 2026-08-15, HECA)

- Spine COVERAGE is not the defect: 96/96 service_road shapes are
  within the DEM-follow seeder's 8.5 m station reach; the per-vertex
  fallback is 140 nodes airport-wide.
- P1 THE HELD UNLAWFUL PROFILE: 707 corridor runs strung with 147
  over-cap segments (worst 80.49 % vs the 8 % cap; 1,417 reported
  conflicts) out of ``_relax_tube``'s [min,max] relaxation of INVERTED
  station tubes — then HELD HARD (``svc_profile`` keyset) into fp#8
  and the final projection.  94.5 % of within_shape service row
  endpoints are BOTH-ENDS-HARD (weld anchor x held profile): the
  1,376-row 1-10 m body and the 45-row >=10 m class are unfixable by
  the projections BY CONSTRUCTION.
- P2 THE STARVED LATERAL PASS: ``insert_service_lateral_nodes`` reads
  ``layout.apt_taxi_centerlines`` (row-1206 only: 24 courses) while
  816 chains are registered in ``grade_graph.centerline_specs`` — the
  exact defect class ruling 3 closed for the seeder, still open here.
  Only 492 cross-section nodes exist airport-wide; cross-sections on
  feed-chain roads are never planted, so lateral co-leveling has no
  substrate (transverse: 2,796 service rows).
- P3 ISOTROPY LOSS: 2,151 of 15,892 ring-adjacent service pairs
  (13.5 %) find no SHARED nearest route (``_edge_route`` -> None) and
  grade isotropically at 8 % — the 2 % transverse cap never applies.

## The law (R1-R3)

R1  A HELD PROFILE MUST BE LAWFUL OR IT IS NOT HELD (the anchor-
    placement law, applied to ``svc_profile``).  The corridor
    profile's own audit already names every over-cap segment and every
    relaxed inverted tube.  Every station in such a segment/tube is
    RELEASED from the ``svc_profile``/hold keysets (the existing 1-D
    validity release at anchors.py ~3642-3690 is the mechanism —
    extend it to these two conditions), so the projections may grade
    those nodes under the road's own law edges.  Stations whose audit
    is clean stay held (the smooth majority must not loosen).  Every
    release is counted and reported with its run id and worst grade.
    NO value is clamped; the string value remains the seed.

R2  THE LATERAL PASS READS THE REGISTERED CHAINS.
    ``insert_service_lateral_nodes`` consumes
    ``grade_graph.service_chain_lines`` (all 816 at HECA) instead of
    the 24 row-1206 courses, exactly as the seeder was fixed by
    ruling 3.  Cross-section feet are then planted on every road the
    seeder stations, and the station-shared value rule co-levels
    them.  The 492 -> expected thousands node-count change is
    geometry: census/hashes will move; report the family deltas.

R3  TRANSVERSE CAP WITHOUT A SHARED ROUTE: when ``_edge_route``
    returns None for a service-family pair, the anisotropy bake uses
    the NEAREST route of EITHER endpoint (tightest resulting cap
    wins) instead of skipping the transverse cap.  A pair genuinely
    off-network (neither endpoint within the perp tolerance of any
    route) stays isotropic as today.  Report the migrated pair count.

## Acceptance

1. Unit twins: (a) an over-cap strung run releases exactly its
   over-cap stations, a clean run releases none; (b) the lateral pass
   plants feet on a feed-chain-only road (synthetic layout); (c) an
   unshared-route pair takes the nearest-route transverse cap.
   Run once (pre-ship).
2. HECA + CYXY through the harness, before/after: the service-family
   census rows (HECA before: within_shape 816, transverse 2,796,
   >=10 m class 45) must DROP materially, and no new family fires;
   both-ends-hard endpoint share of surviving within_shape rows must
   fall from 94.5 %.  Full family tables reported; row deltas
   attributed per R.
3. Build-time impact statement (R2 plants more nodes: state the wall
   delta; ledger tripwire only, timing gates suspended).
4. Lane isolation: all work in lane worktree ``roadlaw``; no commit;
   integration by the lead.

## Pre-delegated decisions

- R1's release conditions are EXACTLY the audit's two classes
  (over-cap segment membership; station inside a relaxed inverted
  tube).  No new thresholds.
- R2 keeps the 1206 courses as chains too (union, deduped by the
  existing chain dedupe) — nothing mapped is dropped.
- A deviation from R1-R3 as written is a STOP-and-report to the lead,
  never the implementer's decision.
