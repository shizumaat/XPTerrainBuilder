# R1.3 — WHO MINTED the pass-2 contradictory pins (lane `r1pins`, 2026-09-03)

Zero-airside plan §3 R1, step 3.  ATTRIBUTION ONLY — no mechanism changes on
this branch; every edit is a write-only, env-gated instrument or this document.
Evidence base: `r1-attribution-20260903.md` (R1.1, control body `134e5eadc7b0`)
and the parked R1.2 ledger (`lane/r1solve` @ `6acef114`, arm-A build `r1a`,
`O4_STALL_GUARD_ADJUDICATE=1`): pass-2 `membrane_conform` exits on a PROVEN
INFEASIBLE pin set — 1,368 of 4,498 reachable nodes with L > U, max gap
19.64 m, exit carrier (2379, 24595) budget 3.76 m vs dz −20.64 m
(pinned/free), detect carrier (24595, 24935) budget 0.81 m vs dz −18.13 m
(free/pinned).  Node 24595 is a FREE membrane node between two CONSTANTS
whose values differ by ≈ 38.8 m across a two-edge chain whose budgets sum
to 4.57 m.

Standing law framing this round: *feasibility is guaranteed* (a real
airport with real thresholds has a lawful surface, so an infeasible pin set
means a pass MINTED contradictory pins) and *intent questions route to the
owner*.

## 0. What "a pin" is in pass 2 (read, no build)

`airside_no_step.membrane_conform` (`src/auto_patch/airside_no_step.py:1123`)
holds EVERY node that is not tier-4 airside membrane CONSTANT at its pass-1
value (`membrane_free_nodes`, :966): tier 1 = runway ring nodes
(`_runway_node_set`), tier 2 = taxiway-family rings + interiors
(`route_profile.anchors._ROUTE_ROLES`) + the round-3 apron spine STATIONS,
tier 3 = building pad rings.  The cap graph the envelope judges is (a) the
IMPOSED no-step pairs touching the membrane (`airside_no_step` enumeration,
budget = `classify_pair` cap × direct distance, window
`AIRSIDE_NO_STEP_WINDOW_M` = 150 m, k = 16) and (b) the membrane's OWN law
edges — within-shape / lattice / station / transverse — with every budget
RAISED to its pass-1 residual under the §H1.2 do-no-harm relaxation
(`PASS2_RELAXATION`; arm A: 4,244 budgets raised, worst raise 19.425 m).
The "pins" are therefore pass 1's values on tier-1/2/3 nodes, and the
contradiction the envelope proves is: two constants ``v_a`` (high) and
``v_b`` (low) with ``v_a − v_b > d(a,i) + d(b,i)`` for some membrane node
``i`` — the shortest cap-weighted chains from each.

The instrument this lane adds (`O4_STALL_ENVELOPE_DUMP=<dir>`, write-only)
dumps the exact envelope inputs at every adjudicated projection (the same
columns `_stall_envelope_gap` reads — ONE code path, the analysis re-runs
that function offline with predecessor tracking) plus, at the pass-2 call
site, the pin provenance of every constant: tier, FGP hard-set family
(runway-datum / tile-seam / terrain / seed-pin / free-in-FGP), plan xy / ll,
and the shape roles carrying the node.  The vertex history of the SAME
surface (control body = replay body, R1.2 proved byte-identity) is the R1.1
`who_wrote --vertex-dump` of the control (`r1ctl/vertices.jsonl`): the last
value-changing writer of each constant BEFORE `final_grade_projection`, and
whether FGP's own main projection moved it, answers "who pinned it".

## 1. Pre-registered predictions (written BEFORE the replay)

| P | claim | falsifier |
|---|---|---|
| P1 | The HIGH side of the worst contradictions (top-10 by gap) is a **tier-3 building pad ring** seated at the pad's flat datum (pad law 09-01g; the solve writeback `solve.py:6246` carries the seat) and the LOW side is a **tier-2 apron spine station / taxiway ring** carrying the centerline profile; the free node between them sits on the frontage chord.  ≥ 6 of the top 10 chains have one pad anchor. | < 4 of 10 chains touch a tier-3 anchor |
| P2 | The budget that makes the chain rigid is the **no-step pair budget** `classify_pair` cap × direct distance at `APRON_MAX_GRADE` = 0.01 (`config.py:1004`) — a 3.76 m budget is a ≈ 376 m pair at 1 %, or ≈ 250 m at `TAXI_MAX_GRADE` 0.015 (`config.py:821`) — NOT an own-law edge: the relaxed own-law edges (budget = pass-1 residual) are by construction satisfiable at pass-1 values, so the envelope's rigidity comes from the imposed pairs whose budgets were never relaxed. | the carrier edge (2379, 24595) is an own-law edge (`membrane_own_law`) |
| P3 | Runway datum (tier 1) anchors < 5 % of the 1,368 infeasible nodes' (a_L, a_U) pairs; the runway-adjacent residual is R5's 12 rows, not this. | ≥ 10 % have a tier-1 side |
| P4 | Groundside pins never anchor pass 2 (a service-road-shared apron vertex is tier 4 = free; groundside roles are not senior) — zero anchors carry `service_ring` / `gs_weld` / `terrain_pin` sources.  If groundside DOES appear it is through FGP's own hard set on a tier-2 node (seed-pin), which is R6's channel. | any anchor whose FGP pin family is terrain / seed-pin with a groundside role |
| P5 | Grouping the 1,368 by (senior-side tier pair): tier3↔tier2 ≥ 50 %, tier2↔tier2 ≥ 25 %, tier1↔any ≤ 10 %.  The tier2↔tier2 group is the OD-2/apron-relief class (two centerline profiles on real relief, ~85 m across HECA) and is TRUE GEOMETRY under the 1 % apron cap; the tier3↔tier2 group dissolves under ONE owner ruling (pad yields to spine, or the frontage no-step pair is not law across a pad seat). | tier2↔tier2 < 10 % (then a single ruling on pads closes nearly everything) |
| P6 | The 38.8 m disagreement behind the worst carrier is NOT real relief between two neighbouring senior surfaces: one of the two constants was written by a pass other than the solve's profile writer (a pad seat, a groundside weld, or FGP's own main projection), i.e. it is MINTED.  Check: the anchor's DEM vs its value differs by > 5 m on exactly one side. | both anchors sit within 2 m of their own DEM (then the relief is real and the cap cannot span it) |
| P7 | The main solve's airside-pass infeasibility (8,674 nodes, 6.06 m; carriers (29199,29201), (6557,6857), (1293,7843)) is the SAME population seen earlier in the build: the R1.1 "inherited junction/apron" class at 30.1102816,31.4067699 — pinned by `rod_interval` / junction rows, i.e. the seat-anchor class, not the pad class. | its anchors are tier-3 pads |

Arm plan: ONE `solve_cut.py --replay` of the R1.2 arm-A capture
(`r1a_capture/HECA`, phases 1–4 frozen) under the CONTROL configuration
(main code, no `O4_FGP_HOLD_RELEASE` gate exists on main) with the dump
instruments; R1.2 proved this replay reproduces the control body
`134e5eadc7b0`, so the 1,368-node population is measured on the control
surface, not the parked arm.  A full HECA build only if the replay cannot
carry the dump (it can: the instruments are inside the solve stage).
No sweep; CYXY not needed.

(Measured results follow.)
