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

## R4 — THE STRING HOLDS ON THE PEGGED SPAN ONLY (Fable amendment,
## 2026-08-15, composed-tree blocker B1)

Measured defect (svcround composed tree, HECA): run (46,0) — 265
stations, 2,364.6 m — carries pegs ONLY at s=0/3.0/7.2 m (three south
mouth welds, all ≈127.21).  ``solve_run_profile`` synthesises DEM end
ties only when the run has FEWER THAN TWO pegs total, so a many-pegged
run's far terminus stays unpegged; the tube is ±inf beyond anchor
reach; FLAT IS LAWFUL — the string holds 127.21 for 2.36 km and stamps
the -11585 service_junction 37.6 m above ambient (40 tear rows at
30.10937,31.38545).  Interventional attribution: R1-off arm erupts
identically (R1 exonerated); station dump shows WHOLE-RUN targets
127.2132 over DEM 89.7; peg dump above.  A DEM tie at the far end
alone is REFUSED here: it re-draws the run as a 2.36 km chord
(127.21→89.6) with an ~8 m census-invisible ridge mid-corridor — the
km-scale seed-character class the warm-start retirement named
(in-sim-only detection).

The law: pegs are the corridor's LAW TARGETS, and the 1-D string is
the law object BETWEEN targets.  Beyond a run's outermost pegged
stations there is nothing lawful to string to — DEM under the road's
own cap is the only law there (the free-end principle, applied to the
span boundary instead of synthesised across open country).

Mechanism (caller-side, ``anchors.py`` run assembly;
``solve_run_profile``'s own contract is unchanged):

- A run with >= 2 pegged stations is strung over the CLOSED SPAN
  [first pegged station .. last pegged station] only.  Stations
  outside the span are NOT profiled: they keep the spine-first
  DEM-follow station rule (band-clamped pointwise), exactly as if the
  corridor ended at its outermost law target.  They join no
  ``svc_profile`` hold and no R1 accounting.
- A run with <= 1 pegged station is not strung at all — the whole run
  keeps the pointwise station rule.  (This retires the synthetic
  both-end DEM tie as the caller's under-pegged path: a zero-peg
  kilometre run strung between two DEM ties is the SAME chord class.
  The function keeps the tie mechanism for direct callers/twins.)
- The bang-bang regression class S2 measured (cap-ridden humps near
  anchors) cannot return through this: outside the pegged span the
  reach band is wide by construction (no law target within reach), so
  the pointwise rule is DEM there, not a cap envelope.

Acceptance: composed HECA loses the -11585 eruption (junction back at
ambient ≈89.6; the 40 tear rows gone) with no new family firing;
CYXY census at-or-better vs composed 294; unit twins for the three
span cases (one-sided pegs / zero pegs / both-ends pegged unchanged).

## R5 — ROAD RUNS TRACK TERRAIN (Fable spec, owner-ratified
## 2026-08-15 evening; conditions: within grade longitudinally,
## flat laterally)

Owner in-sim reports on 1.0.252 (CYXY sites 60.7100216,-135.0726292 /
60.7096716,-135.073278 / 60.7015765,-135.0674007; HECA
30.1156366,31.4114059): the taut string draws the STRAIGHTEST lawful
profile, so a road strung between mouths rides a chord — a causeway
5.2 m over a terrain dip (CYXY road 349: 0.4 % grade over a 2.7 %
dip), a 12–16 m canyon through a rise (CYXY junction-190 complex flat
at ~706 under 718–722 HRDEM terrain), an elevated plateau (HECA).
`who_wrote --at` confirms the solve ingests the held profile value
unchanged.  Taut-string semantics are CORRECT for airside spines
(test_dem_hump_inside_the_band_is_not_traced stands, unchanged) and
WRONG for roads, whose owner-law is terrain-hugging.

THE LAW: a service-road run's profile is the CAP-CONSTRAINED
LEAST-DEVIATION TRACKER of its low-passed station DEM.

- LATERAL (owner condition 2, already law): every cross-section takes
  ONE station value (the station-shared value rule) — restate as an
  explicit twin, not re-implemented.
- LONGITUDINAL (owner condition 1): every adjacent-station grade
  <= the road cap — hard constraint, explicit twin.
- PEGS remain exact law targets (mouth welds, free-end ties, interior
  values); the reach-band tube still clamps everywhere.
- BETWEEN pegs the profile minimizes deviation from `smooth_de` (the
  existing low-passed station DEM) subject to the above.  Where
  terrain out-runs the cap the profile departs minimally (the
  cap-Lipschitz projection); the departure spans join the audit —
  recorded, no conflict minted (DEM deviation stays unreported by
  ruling; the AUDIT is not the census).
- Mechanism: the cap-Lipschitz regularization of `smooth_de` clamped
  into (tube ∩ peg cone) — the K1b carrier machinery pattern
  (forward/backward Lipschitz passes), applied to the DEM objective.
  NOT the warm-start hazard class: warm start flattened because its
  carrier was cone-midpoint-seeded at range; here the source IS the
  terrain, and the filter only moves values where the cap forces it.
- SCOPE: service-road corridor runs only.  Airside spine profiles
  keep the taut string.  R4's span rule stands: outside the pegged
  span the same tracker applies with no pegs (subsumes the pointwise
  station rule for chained roads — strung and unstrung stretches now
  converge in character, healing their seam).  Per-vertex fallback
  for roads with NO station substrate is out of scope (its own
  docket: the unmapped-route population), as are the stamped-low
  drainage/gap flats and the OLS-cut/road interaction.

Acceptance (harness only):
1. Twins: (a) longitudinal cap holds at every emitted station pair;
   (b) cross-section single-value invariant; (c) a dip within cap is
   TRACKED (max |z − smooth_de| ≤ 0.5 m on a synthetic within-cap
   dip); (d) a rise steeper than cap departs minimally and the audit
   records the span; (e) pegs are exact; (f) both-ends-pegged airside
   spine runs byte-unchanged (taut string kept).
2. CYXY: road 349 tracks its dip; the junction-190 complex rises with
   terrain (no 10 m+ undercut); census no new family, adjudicated
   at-or-better vs 303 modulo honest re-pricing (report deltas).
3. HECA: -11585 stays at ambient (B1 must not return); censuses
   reported vs 6,700 with family deltas attributed.
4. Build-time: O(n) passes per run — state the wall delta from the
   ledger frame; no exclusive timing (suspended).

Pre-delegated: materiality floor 0.01 m; attempt cap 2 per target;
deviations STOP-and-report to the Fable lead (this spec's author).

### R5b — THE TRACKER PROFILE HOLDS (Fable adjudication of R5's
### STOP, 2026-08-15; owner ratification rides the round)

R5's first measurement: sites (i)-(iii) PASS with airside
byte-identical, but unpegged stretches carry the tracker as SEEDS
(R4's join-no-hold clause), so the projections re-roughen them —
over-cap emitted segments 38→71 at CYXY, and the transverse cost
(+45 CYXY / +430 HECA, each row milder) prices a surface the tracker
never actually emitted.  This is the SAME soft-seed failure the
pegged-span hold already names ("as a SOFT seed the whole-run profile
is written and then written over — measured").

Amendment: tracker stations HOLD (join the ``svc_profile`` keyset)
wherever the tracker's profile is cap-lawful — pegged span and
unpegged stretches alike — under EXACTLY the R1 validity release
(over-cap segment / relaxed inverted tube stations release to the
solve with the tracker value as seed).  R4's span rule is unchanged
for STRINGING; its join-no-hold clause is superseded for TRACKED
stations by this hold.  The R5 acceptance criteria re-run unchanged;
the two CYXY new-family rows (one weld site 60.69699,-135.05965 and
one plane_gradient) are re-measured under the hold and docketed if
they survive.

### R5b REFUTED BY MEASUREMENT (Fable adjudication, 2026-08-15)

The hold arm (lane commit 7919c3e): sites unchanged (all PASS in both
arms), transverse unchanged (CYXY 91→90, HECA 1,741→1,751), and +211
adjudicated at HECA via ONE-SIDED WELD-OR-GAP — freezing the road's
1-D profile leaves welded 2-D neighbours (junction yards, groundside
lots) unable to reach it within their own caps; under seeds the solve
reconciles BOTH sides.  The premise instrument was wrong: over-cap
EMITTED segments count the RELIEF a terrain-following road lawfully
has (a chord has none by construction) — it never measured
projection re-roughening.  RULING: R5-seeds is the production arm
(lane d7e3435 merges; 7919c3e does not).  The one-sided-weld class
joins the node-vs-edge mouth law pair docket — the structural fix is
law-paired boundaries in the one graph, never a frozen side.

## R5c — GRADED-ROAD CHARACTER: SMOOTH LONGITUDINALLY, CO-LEVELED
## ACROSS THE COMPOSITE (Fable spec, 2026-08-15; owner in-sim on R5,
## CYXY 60.7087015,-135.0746305)

R5's tracker follows the low-passed terrain faithfully — including
its wiggles — where the owner wants ROAD character: "a smooth graded
surface", not terrain-hugging bumps.  And the visible "road" is a
COMPOSITE (service_road 349 pieces + service_junction 63 pieces on
one corridor): each shape takes station values from its own chain
projection, so the surface can slope laterally across the corridor
even though every single shape is cross-section-flat.

1. **REVERSAL SUPPRESSION (longitudinal).**  After the R5 tracker,
   collapse grade REVERSALS below materiality: a local
   rise-fall-rise (or fall-rise-fall) whose interior amplitude is
   < `SVC_PROFILE_REVERSAL_MIN_M` (ONE new constant, default 0.4 m)
   over any span is levelled through (monotone bridge between its
   endpoints, still clamped to tube ∩ peg cone ∩ cap).  Result:
   piecewise-monotone ramps between real terrain features; large
   terrain movement still tracked.  Both owner conditions unchanged
   (cap; one value per cross-section).
2. **CORRIDOR CO-LEVEL (lateral).**  All shapes of one corridor
   (road pieces + junction pieces whose vertices project onto the
   SAME chain within the existing station reach) share the chain's
   station value at their arclength — extend station cluster
   membership across shape boundaries instead of per shape.  A
   junction hosting MULTIPLE chains keeps its junction rule (mouth
   welds win; then the through-chain of its widest road).
3. Airside untouched — byte-identical.

Acceptance: twins for (1) reversal-collapse (synthetic wiggle
levelled; real 2 m terrain feature kept) and (2) cross-shape
station sharing (junction vertex adopts through-chain value);
CYXY: the owner stretch (lot → 60.7087015,-135.0746305) is
monotone within one reversal and laterally level across road+
junction pieces at equal arclength; R5's three site verifications
still PASS; censuses reported vs CYXY 377 / HECA 6,998, no new
family; ledger-frame walls only.  Materiality 0.01 m; attempt cap
2; deviations STOP to the Fable lead.
