# Seam continuity as law: bind the fabric, delete the pull

Fable spec, 2026-08-04, assignment 6 (designer-authored, lead-approved
with the §2a amendment below). DISPATCH FENCE (updated 2026-08-04
evening): the owner's no-degradation-shield ruling (RULINGS.md)
AUTHORIZES this round including its endgame — dispatch follows the
ref-pull lane's commit and the seed-fix round's merge (one_solve.py
collision avoidance); the rod-composition fix is phase 0 OF THIS ROUND
(precondition to the kill, own pre-reg: the 2.54 m corridor-sag class,
solve.py:5602-03, compose links across removed runs per the audited
fix). O4_CORRIDOR_REF_STRING arrives already default-"0" (retired by
ruling; ref-pull lane) — phase C still deletes the code path. Phase C
honors its bands and STOP rules; a miss returns for attribution. The §7 reference-rod
proximal pull is a soft second authority implementing the RETIRED
least-displacement metric; this spec re-expresses the ONE thing it is
load-bearing for — tile-seam fabric continuity — as a directed
constraint family in the one solve, then deletes the pull and its refs
channel entirely. Lines against the tree at dispatch (s7 evidence was
measured in the `s7-attrib` worktree at 399c24d). BINDING:
docs/RULINGS.md (single-solve architecture — this deletes the fifth
second authority; airside-is-king as constraint direction; string
purpose statement; feasibility-is-guaranteed; grade-law completeness;
convergence guards). FENCE: the interim round (weight 0.2 → 0.02 +
loud-stall conversion) is dispatching separately — this spec is the
ENDGAME and must not touch the interim knobs.

## Mechanism (s7_attrib/ — PRE_REG.md P4/P6 + the census arms)

The pull injects `z[ref] += w·(z_ref − z[ref])` at the top of every
sweep (one_solve.py:1185-1189; also :424); a ref that conflicts with a
cap never quiets, so the loop exits through the `ref_prev` steady-state
break WITHOUT `certified` (one_solve.py:1274-1281) and ships the
residual. The adjudication round proved it UNBINDS THE CAP: a 12×
cap violation held open at w=0.2, synthetic on the real function. Yet
w=0 regresses the tile seam — the pull is accidentally load-bearing
for the fabric BETWEEN the hard seam pins:

- solve.py:5593-5603 (the recorded regression): without the reference
  term the final pass re-drags the fp#8-held seam fabric ~101 → 85.98.
- Measured (s7 census, law-true frame): HECA `seam::seam` 12 → **93**
  at w=0 (w=0.02: 19); CYXY 2 → 9; HECA `adj_edge` worst 1.05 → 2.60 m.
- Everything else IMPROVES at w=0 — HECA within 9 952 → 8 511, HEAZ
  118 → 63, CYXY 171 → 156, worst within_pair down at all three — i.e.
  P6's falsifier fired: retirement is cheap EVERYWHERE except the seam.
  The re-expression is therefore scoped to the seam fabric ONLY.

Today the seam has POINT law but no CHAIN law: `_seam_spine_anchors`
(solve.py:6335) pins the nearest spine node per centerline×seam
crossing hard at the smoothed seam DEM, and the tile-seam DEM pins ride
`seed_rwy_seam`/`layout._seam_pin_idx` (the spine-freeze preserved
set) — but the cut-edge vertices between pins are held only by the
pull's soft memory of the writeback. That is the defect: a cross-tile
CONTRACT (the neighbour tile shows raw DEM at the cut) enforced by an
uncertifiable soft term.

## The design (directed constraint family; the Ruling-54/box pattern)

1. **Seam-fabric membership.** The seam fabric = every solve node on a
   tile cut line (the tile_cut vertices), chained along the cut between
   consecutive hard pins (same chain decomposition idiom as
   `_build_spine_corridors`, solve.py:6381).
2. **The binding law — boxes, not pulls.** Each seam-fabric node gets a
   signed BOX `[seamDEM − tol, seamDEM + tol]` from the smoothed seam
   DEM (the cross-tile contract is LAW, like the runway profile — law
   tier, not phase-A estimate). The box channel already exists
   (`node_box`, one_solve.py:938; the seat_boxes store view) and a box
   projection is exact and CERTIFIABLE — the categorical difference
   from the pull. `tol` = the validator's existing seam-tear threshold
   constant, read from ONE place by both the solve and the seam census
   (lockstep, grade-law completeness).
2a. **Exemption lockstep (LEAD AMENDMENT, review catch).** The seam
   census does not bind every cut node: it carries the wall-straddle
   exemption class (lawful terraces straddling the cut — the HECA
   303→293 class, interior-anchor classifier, 4 endpoint-touching
   survivors deliberate) and the adjacent-ground terrace law makes
   graded/DEM boundary steps lawful. A box family reading only the
   TOLERANCE constant would have the solve flatten walls the validator
   deliberately exempts — and band 1's counts would compare a stricter
   law against a looser census. Therefore the box law reads BOTH from
   the one place: the tolerance constant AND the exemption predicate
   (a node on an exempt wall-straddle site gets no seamDEM box; its
   chain terminates at the wall like at a hard pin). Twin required: a
   synthetic exempt straddle node is NOT boxed, its neighbours are.
3. **Along-chain law.** Chain edges carry the owning role's cap between
   pins (ordinary within-shape edges — mostly present already; the
   family guarantees no chain span is lawless).
4. **Direction seam → interior** (airside-is-king's pattern): interior
   nodes conform to the seam boundary; no interior force may move a
   seam-fabric node outside its box — structural, because a box cannot
   be dragged. No witness admission changes needed.
5. **The kill.** With the family proven, delete: the pull term and
   `ref_active` exit arm (one_solve.py:424/:1185-1189/:1274-1281),
   `_ref_pull_weight`/`O4_YIELD_REF_WEIGHT` (:338),
   `_node_ref_arrays`/`node_ref`/`node_refs`/`group_refs` plumbing, and
   the `O4_CORRIDOR_REF_STRING` gate (solve.py:2520/:2767-2787) — the
   refs channel has NO consumer but the pull. The loud-stall conversion
   (interim round) remains the uncertified-exit instrument; after the
   kill, every exit must certify or stall loudly.

Gate: `O4_SEAM_FABRIC_LAW`, default "0", for phases A/B; the phase-C
deletion is ungated by nature (it changes the default surface) and
lands ONLY after the bands below pass and the owner approves — the
default arm's bytes change, so acceptance is law-not-bytes.

## Documented interactions (the brief's required statements)

- **`O4_CORRIDOR_REF_STRING` (default "1"): dies with the pull.** The
  string-derived z_ref on corridor nodes (2 020 at HEAZ) is the string
  acting as a back-door SURFACE AUTHORITY — exactly what the string
  purpose statement forbids. When the pull dies, corridor refs lose
  their only consumer and are deleted, which ENFORCES that ruling.
  Corridor SHAPE is lawfully carried by the signed-interval rod family
  (the taut-string edges — the spine-freeze movement report measured
  those as the dominant binding law), NOT by z_ref: the known
  key-drop hole (solve.py:5602-03, the 2.54 m sag cause) must be
  closed by composing rod links across removed runs (the audited
  rod-carry fix) BEFORE the kill lands; the interim round's
  `O4_CORRIDOR_REF_STRING` A/B names which spans currently lean on
  z_ref — consume its result, do not re-measure.
- **The spine-yield round (4b591fc) rides the same channel**
  (`node_refs=_spine_refs`): after the kill, yielded spine nodes are
  plain free. This was measured — the sy_w0 arm is HEAZ's best surface
  on record (law-true 70 vs 130, worst within_pair 1.31 vs 4.05) — and
  the least-displacement metric is retired, so free is the intended
  end state; the movement REPORT survives (forensics channel, not the
  pull). The yield's synthetic tests that assert ref behaviour are
  rewritten to assert the post-kill contract.

## Pre-registered outcomes (bands; law-true frame, both frames quoted)

1. Seam holds at pull-dead: HECA `seam::seam` ≤ 20 success / ≤ 40
   partial (default 12, w=0 regression 93); CYXY ≤ 4 (default 2, w=0
   9); HECA `adj_edge` worst back to ≤ 1.1 m (default 1.05).
2. The census win is BANKED, not traded: HECA within ≤ 9 000 (default
   9 952; w=0 showed 8 511), HEAZ ≤ 80 (118/63), CYXY ≤ 160 (171/156);
   worst within_pair not above the default arm at any airport.
3. The final-pass re-drag class is dead: |z_final − z_incoming| on
   seam-fabric nodes ≤ tol (the arm2 displacement instrument is the
   report); the ~101 → 85.98 signature cannot recur.
4. Certification: the 12× synthetic on the real function certifies
   (`certified=True`, zero over-cap at exit) under the box family;
   zero uncertified exits across the battery (the loud-stall
   instrument reads clean) — hard, not a band.
5. The 2.54 m corridor-sag class does not return (rod composition
   landed first); corridor profile spot-check at HEAZ quoted.
6. Sweep counts quoted per airport (report only — the pull's early
   uncertified exits made its sweep counts LOOK cheaper; honesty note
   pre-registered: sweeps may rise while the surface improves).

## Acceptance

Phase A/B: gate-off byte identity 2× on the current default anchors AT
DISPATCH TIME (cited symbolically — the seat-flip and interim rounds
are churning the hashes; pin the five body hashes in the round's
PRE_REG before any arm). Phase C (the kill): full five-airport battery,
census matrices both frames OFF→ON→post-kill, suite same reds as the
round baseline (enumerate before; rewrite only ref-asserting tests,
cite each), new twins (box certifiability, seam-chain membership,
direction test: an interior drag cannot move a boxed seam node, the
12× synthetic, corridor-shape-without-z_ref). Only `check_build_time
--run` timings quotable; box projections replace per-sweep pull work —
any measured cost ≥ 1 % of budget ⇒ Fable-5 review per hard law. Build
budget: identity 2×5 + HEAZ/CYXY/HECA law arms + the phase-C battery
≈ 3 h honest wall total, foreground, WORKTREE, no commit without the
owner's phase-C approval. Convergence guards: 0.01 m materiality, 2
attempts, `.progress`.

## STOP rules

Band-1 miss (the seam law is not yet the load-bearer — return the
attribution, do NOT ship the kill); any uncertified exit on the
battery post-kill; the sag class returns; rod composition not landed
when phase C is reached (phase C waits, phases A/B still deliver);
second miss on any target.

## Out of scope

The interim round's knobs (0.02 weight, loud-stall — separate,
dispatching); the held spine-seed/band attribution (assignment 4 —
nothing here validates seeds against bands; seam boxes read the seam
DEM, not `reach_band_unified`); emit decimation; the other scheduled
post-solve writers; string gates beyond the corridor-ref deletion.
