# Apron chord anchor targets + DEM-last (Fable spec, 2026-08-25;
# implements RULINGS 2026-08-25 both rulings; general law, HECA is the
# acceptance airport)

Companion evidence: docs/findings/apron-membrane-findings-20260824.md and
the 2026-08-25 pad-seat round (lane/backedge b18c3f92 report): narrowing
seats against the frontage-attachment subset regressed HECA 1,964 → 2,249
because the census chords price against a much wider population than the
frontage anchors. The owner's ruling replaces the population itself.

## §1 The chord-target law (RULINGS 2026-08-25 first ruling)

1. An apron ring vertex's strict chord is measured to its NEAREST VISIBLE
   ANCHOR, where the anchor candidate set is the union of:
   (a) ring vertices lying ON a taxiway centerline (the existing
       `SPINE_PERP_TOL_M` notion — unchanged), and
   (b) ring vertices lying on a BUILDING PAD boundary (the enumeration's
       existing `bld` membership — the same weld-projection identity,
       no new vertex, no new geometric notion).
   Whichever is CLOSER wins. One chord per vertex, deterministic ties on
   lower ring index (A4.3(a) unchanged).
2. VISIBILITY IS APRON-ONLY: the chord must be visible across apron-role
   pavement (the pad's own footprint at the target end counts; the chord
   may not cross non-apron pavement or gaps). Implement as a restriction
   of the ONE existing visibility predicate (the `vis` thunk both readers
   consume) — never a third notion of "can this chord be walked".
3. CAPS: a chord whose target is a PAD prices in the STAND class (1 %,
   RULINGS 2026-08-24c stand scope — the pad-intercept precedent already
   prices to the pad; this makes the pad a first-class target rather than
   an interceptor). A chord whose target is a CENTERLINE keeps today's
   cap assignment unchanged. BUILDING FRONTAGE CHORDS (pad→centerline)
   ARE UNTOUCHED — `is_frontage_chord` and its rules stand as-is.
4. Reach: the existing `BUILDING_REACH_CORRIDOR_M` bound applies to the
   nearest-anchor search unchanged; a vertex with no visible anchor in
   reach contributes nothing (as today).
5. ONE implementation: extend `grade_graph.nearest_spine_pairs`
   (grade_graph.py:537) into the nearest-ANCHOR enumeration, carrying the
   target kind (spine | pad) per pair; `PairContext.nearest_spine` stays
   the strict-population flag (both kinds are strict); the kind selects
   the cap class in `classify_pair`/`is_apron_strict_chord`. The census,
   the solve's law-edge minting and the pytest fixtures all read this one
   enumeration — a reader-private copy is the census-wrapper defect.

## §2 DEM-last (RULINGS 2026-08-25 second ruling; staged AFTER §1 lands
## and is measured)

1. Where the law leaves a choice of level (a seat interval, an unanchored
   interior), ANCHOR-CONSISTENCY is preferred over DEM proximity; DEM is
   the LAST tiebreaker. Concretely: the seat chosen inside a pad's lawful
   interval biases toward the level minimizing chord residuals against
   its OWN §1 anchor neighborhood (the pads/centerlines its vertices now
   chord to), not toward DEM. The scaffold interpolation (24c) already
   carries no DEM attraction; unanchored regions keep their DEM soft-seed
   (the pad-less-apron case, unchanged).
2. Gate separately (`O4_DEM_LAST_SEAT_BIAS`, default OFF until §1's HECA
   read is in): the two rulings compose but must be measured apart —
   the 2026-08-25 round's lesson is that seat movement against the wrong
   population regresses; §1 changes the population, §2 then moves seats.
3. The parked pad-seat-consistency mechanism (b18c3f92, flag OFF) is the
   chassis for §2's seat bias: re-aim its consistency interval from the
   frontage-attachment records to the §1 anchor neighborhood. Do not
   re-enable the frontage-subset version.

## Twins

(a) Synthetic ring: vertex nearer a pad vertex than any spine vertex →
    one chord to the pad at 1 %; nearer a spine vertex → chord to spine
    at today's cap; equidistant → lower ring index.
(b) Visibility: an anchor behind non-apron pavement (or across a gap) is
    not a candidate; the next-nearest visible anchor wins.
(c) Frontage chords: byte-identical classification before/after on a
    fixture with pads (the unchanged-rules clause).
(d) Flag off (`O4_APRON_CHORD_ANCHOR_TARGET`, default ON in-lane) →
    byte-identical to today (enumeration falls back to spine-only).
(e) Census/solve parity: `test_harness.py` twins pass — the census and
    the solve mint from the one enumeration; a family added/changed
    without register parity fails there.

## Acceptance (HECA first — owner: rulings general, intended for HECA)

- ONE HECA build + census on lane/backedge. The population CHANGES, so
  report BOTH frames honestly: the old-frame count (bar 1,487) and the
  new-frame count with the class table (stand-to-pad vs stand-to-spine
  split). No silent re-baselining: the bar is re-founded by the owner
  after this read, not by the lane.
- Relative drape instruments (apron median vs own corridor,
  `apron_drape_read` ring relief/amp50, cliff metric B ≤ 532) must not
  regress vs the v5 arm. Owner sites -10682 / -10144 read smooth.
- Then SPJC + CYXY non-regression (their pad classes are thin; expect
  small deltas — report them).
- Attempt cap 2, materiality floor 0.01 m, then STOP with the class
  table. No shared-repo writes, no timing claims.
