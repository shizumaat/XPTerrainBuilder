# Seed-fix round: raw law measures, complete seeds, capped contacts

Fable spec, 2026-08-04, assignment 4 (designer-authored, lead-approved
with the §1b amendment below), re-scoped after the
seed attribution landed — scratchpad seed_attrib/, PREDICTIONS.md
pre-registered, worktree seed-attrib @ 86e7310). The owner's axiom is
CONFIRMED on both counts: never the spine — HEAZ was WRONG MEASUREMENT,
HECA is WRONG VALUE. Load-bearing numbers below were re-derived from
seed_attrib/ primaries (build logs + phase-A npz dumps) unless marked
"report figure". BINDING: docs/RULINGS.md (feasibility-is-guaranteed;
grade-law completeness — binding + twin; single-pass; anchor placement
law; convergence guards).

RECONCILIATION (required): DRAFT-route-distance-seat-coupling-spec
(assignment 5) shares §3's mechanism family — polytopes priced on a
metric the projection does not enforce. Decision: UNIFY THE METRIC,
FENCE THE ROUNDS. This round builds the law-graph budget oracle ONCE
(route-metric distance/budget between spine/apron nodes, priced exactly
as phase A projects — single-pass) and §3 consumes it; the coupling
spec is revised to consume the SAME oracle (its "one metric" clause now
cites it) and remains a separate dispatch with its own arms and bands.
Neither round re-derives the other's metric.

## Mechanism (verified from seed_attrib/)

**HEAZ — wrong measurement.** `_margined_budget` (one_solve.py:177)
subtracts the 0.01 m emit-quantization margin from EVERY edge's sweep
budget — correct per pair at emit, compounding per path (report figure:
a 69-hop witness route steals 0.63 m). Verified: default arm stalls at
sweep 17, burns 3983, margined envelope INFEASIBLE 593/2032 (max gap
0.7275); the interventional `O4_QUANT_MARGIN=0` arm burns 10, exits
with 0 violating edges, envelope 0/2032, gap 0.000000. The 1-cm band
is TRUTHFUL (report figure: two runway seeds 4.380 m apart in value,
4.3827 m route budget — 2.6 mm real slack); `O4_BAND_SEED_EXACT` is
orthogonal (byte-identical arm). HEAZ never had an anchor
contradiction — s7 P7's verdict is REVERSED in the raw frame.

**HECA — wrong value, four-link minting chain.** Verified from the
npz: seat anchor 2861 (`seat_on_spine`) hard-stamped z 65.749 vs its
own DEM 60.200, 12.853 m from hard runway-truth anchor 2863
(`seed_rwy_seam`, z 60.790, DEM 59.907; report figure: 33 m from CIFP
RW23R, +0.135 m) — 38.6 % implied grade. The chain: (1)
`spine_value_fields` (building_feasibility.py:589) seeds ONLY
`G.runway_anchor` (:623) — verified 8 of 31 on-spine `seed_rwy_seam`
nodes missing, so the band floor sits ABOVE a node's own hard runway
value at exactly 2 nodes (4818 +2.344, 2863 +1.522); (2) the
no-building apron seat's DEM target is silently clamped UP into that
defective floor (the `min(max(tgt, b[0]), b[1])` clamp in
`build_building_seats`' apron-contact block — anchors.py cited
SYMBOLICALLY, the split-level lane is mid-flight in that file); (3)
`_project_apron_contacts` (anchors.py:678) lifts it further in a
polytope whose only cap constraints are feeder↔feeder at straight gap —
NO constraint against the hard runway anchor 12.85 m away; (4)
solve.py:1662-1665 stamps the result immovable (`base_hard`,
`seat_on_spine`). Margin fix measured NO-OP here: the qm0 arm still
burns 3983 (carrier (2861,2862), residual 4.765730); raw-law envelope
census 1779/7614 is the honest baseline (retires the margined 3101);
worst class `seat_on_spine`×`seed_rwy_seam` 107 nodes / 4.766 m
(report figure).

## The fixes

1. **Raw law measures; the margin stops compounding**
   (one_solve.py:177). (a) INSTRUMENT half, landed direct once proven
   byte-inert: `_stall_envelope_gap` (:770), the stall-report
   adjudication read, and every envelope/census instrument judge on
   RAW budgets — the margin is an emit concern, not a law term. (b)
   SURFACE half, gate `O4_RAW_LAW_SWEEPS` default "0": sweeps enforce
   raw budgets; the quantization guarantee moves to emit as a per-pair
   grid-snap guard (bounded by one 0.01 m step, per-pair by
   construction — CANNOT compound along paths). Consumers enumerated
   before edit via blast.py: `_margined_budget` at :1883 and :2789,
   AND the `_margined_interval` mirror at :1920 (the signed-interval
   family — in scope, same defect shape).
   **LEAD AMENDMENT (§1b): the emit snap must be LAW-AWARE per pair** —
   rounding direction chosen so no snapped pair exceeds its raw cap.
   The emit side has minted violations before (the HECA emit-consensus
   1,497-row case): a naive nearest-grid snap of a pair sitting at
   exactly cap re-mints over-cap census rows and restarts the tolerance
   debate. Twin required: a pair at exact raw cap snaps to a lawful
   pair; the census over-cap count on a snap-only synthetic is ZERO.
2. **Band seeding completeness + inversion law**
   (building_feasibility.py:589/:623). `spine_value_fields` seeds from
   `G.runway_anchor` ∪ on-spine `seed_rwy_seam` hard truth (the
   generation-binding half); twin: `_record_band_inversions` (:661) +
   `assert_no_final_band_inversion` (:698) extended with the
   floor-above-own-hard-value class — fires on HECA's 2 nodes today,
   synthetic twin encodes them. Gate `O4_BAND_SEED_COMPLETE`
   default "0".
3. **Apron-contact polytope caps to hard anchors** (anchors.py:678,
   symbolic — expect rebase onto the split-level lane's tree). The
   polytope gains cap constraints anchor↔feeder for every hard
   runway/seam anchor within reach ON THE SAME SPINE GRAPH PHASE A
   PROJECTS ON (the unified law-graph budget oracle, see
   RECONCILIATION). The silent clamp-up dies: clamping a DEM target
   into the band is lawful only against a §2-verified band, and any
   clamp moving the target beyond materiality is REPORTED. Gate
   `O4_APRON_CONTACT_ANCHOR_CAP` default "0".
4. **Hard-stamp guard** (solve.py:1662-1665). A `seat_on_spine` value
   that cap-contradicts a hard runway/seam anchor within its route
   budget must not become `base_hard` — same shape as the frozen-spine
   fix: it enters YIELD-HARD (Ruling-54 membership; amends the
   spine-yield preserved set, which today preserves `building_seats`
   unconditionally), with the movement reported. Gate
   `O4_SEAT_STAMP_GUARD` default "0".
5. **Loud midpoint** (solve.py:7305). `0.5*(lo+hi)` on an empty
   interval (`lo > hi`) is the silent shape feasibility-is-guaranteed
   forbids — it becomes a named forensics report (node, lo, hi,
   arg-max anchors); PREDICTIONS P3 expects it firing at HECA today.
   Escalation to a build error waits until §2/§3 retire the known
   minters. Ungated write-only report.

## Battery-wide meaning change (state before any number is re-quoted)

Every MARGINED envelope reading changes meaning at fix 1. Affected
standing numbers, named: the carrier dossier's TRUE-set L−U table and
its pocket fractions; spine-freeze RESULTS #1/#3 (HECA 76.5–81.3 %
comparable-call fractions — re-read raw: 1779/7614 is the baseline);
the drain-worklist carrier annex; s7 P7's HEAZ verdict (reversed); the
terrace spec's pre-registered band 1 — its instrument-contingency
annotation is now CONCRETE: re-read in the raw-law frame before
dispatch. The split-level spec's §3 pin resolves as: the band is
certified truthful GIVEN COMPLETE SEEDS — after §2, clamping into
`node_band` is lawful; before §2 it inherits the 2-node floor defect.

## Pre-registered outcomes (bands; measured releases from the
## attribution are the anchors)

1. §1 instrument half byte-inert: current default anchors reproduce 2×
   (hard). §1 surface arm, HEAZ: phase-A burn 3983 → ≤50 (measured 10
   at qm0); raw envelope 0/2032; carriers (2576,2741)/(3151,3152)
   ABSENT (hard).
2. HECA control (pre-registered no-op): §1 alone leaves the 3983 burn
   (measured — qm0 identical). Release band with §1+§3+§4 on: 3983 →
   ≤500 success / ≤2000 partial; no movement ⇒ STOP-with-attribution.
3. §2: the 2 inversion nodes (4818, 2863) → 0, and the inversion twin
   red-before/green-after (exact). §3+§4: the
   `seat_on_spine`×`seed_rwy_seam` worst class (107 nodes / 4.766 m)
   collapses ≥80 % success / ≥40 % partial; 2861's stamped 65.749
   re-seats within cap of 2863's runway truth.
4. §5 report: fires ≥1 at HECA today, 0 after §2+§3 (quoted).
5. Battery, all five, both frames, full class matrix: no new over-cap
   class; worst-|de| severity not up at any airport; census deltas
   quoted honestly in the RAW frame with the frame change stated.

## Acceptance

Gate-off byte identity 2× on the current default anchors AT DISPATCH
TIME (symbolic — the seat-flip lane is churning hashes; pin the five
body hashes in the round's PRE_REG before any arm). Suite: same reds
as the round baseline (enumerate first) + twins per fix (§1
margin-compounding synthetic: an N-hop path raw-feasible but
margined-infeasible; §2 inversion twin; §3 anchor-cap twin on the 2861
geometry; §4 stamp-guard twin; §5 loudness twin). Only
`check_build_time --run` timings quotable; no timing claim; ≥1 %-budget
measured cost ⇒ Fable-5 review per hard law. Build budget: HEAZ arms
are cheap (~70 s class), HECA arms dominate (~600 s class): identity
2×5 + §-wise HEAZ/HECA arms + the final battery ≈ 3–4 h honest wall
total, foreground, WORKTREE, no commit. Convergence guards: 0.01 m
materiality, 2 attempts, `.progress`.

## STOP rules

§1 instrument half not byte-inert (it is a measurement fix — a byte
change means it grades, STOP); band-1 HEAZ release not reproduced;
band-2 HECA no-movement (return the attribution — the chain has a
fifth link); any new over-cap class; a §5 escalation firing after
§2/§3 (a genuine unknown minter — attribute, do not patch inline);
second miss on any target.

## Out of scope (named)

QUEUED PROBE, not this round: adjacent_ground consumes PRE-flex raster
bands — `build_raster_reach_band` runs twice at HECA
(adjacent_ground.py:3546 vs solve.py:1471), ±4.01 m deltas,
sensitivity unmeasured. Also out: the route-distance seat-coupling
round (consumes the oracle, own dispatch); the split-level and terrace
rounds (mid-flight/queued); `O4_BAND_SEED_EXACT` (measured
orthogonal); the seam-continuity round; emit decimation.
