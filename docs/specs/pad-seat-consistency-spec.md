# Pad-seat consistency interval (Fable spec, 2026-08-24; owner-approved
# direction "pads seated at the elevation that enables the 1 % cap";
# UNIMPLEMENTED — written for the next session)

Companion evidence: docs/findings/apron-membrane-findings-20260824.md —
read it FIRST; every claim below is measured there.

## The measured gap (one sentence)

The reach band seats a pad anywhere inside a FEASIBILITY interval
7-34 m wide (`clamp(DEM, floor, ceiling)`); the chord law then judges
the pad's frontage against the SOLVED corridor with a budget of
0.13-1.06 m — the seat is chosen from an interval up to ~75x wider
than the constraint applied afterwards, with no reference to where the
corridor actually solved. 100 % of HECA's violating pads sit lawfully
INSIDE their band; the band is right but not BINDING.

## The law

1. **Pad seats defer to the solved corridor (creation-order seniority,
   RULINGS 2026-08-21e; the corridor profile is created first).** The
   pad's seating interval becomes
       `band ∩ [corridor_value ± cap × route_distance]`
   where `corridor_value` is the SOLVED value at the pad's governing
   centerline anchor (the same anchor `band.attachment_at` records),
   `cap` the frontage/apron cap (1 %), and `route_distance` the band's
   own route distance to that anchor. The band still guarantees
   feasibility; the corridor term guarantees consistency; DEM still
   chooses WHERE within the (now narrower) lawful range — the standing
   canon ("DEM chooses WHERE within that lawful range") is unchanged.
2. Empty intersection = the pad-seat feasibility gate's population
   (already landed report-first, lane/backedge 00ec80d): a seat that
   cannot be both feasible and corridor-consistent is a SEAT DEFECT
   record, priced like the F3c graded-handoff shape (descend at cap
   from the senior side, report the residual) — never a silent pick.
3. Class scope per the canon the owner named: LARGE buildings fronting
   an apron (seat-is-the-weld, 2026-08-08) and SMALL/DETACHED pads
   (service-route band, 2026-08-06) BOTH take the consistency
   intersection — their existing interval sources differ, the
   intersection clause is the same. No-building aprons are untouched
   (24c addendum: soft DEM seed, cut/fill to the scaffold).
4. Sequencing: this seats pads AFTER the corridor profiles solve and
   BEFORE the apron membrane solve — the order 24c's scaffold model
   assumes. Verify the pipeline already has that order (the band is
   minted by the solve; the seat consumption point is
   `building_feasible_levels` / anchors.py:894 small-pad path); if
   seats are consumed before corridor values exist, that ordering gap
   is a STOP-and-report, not an improvisation.

## What NOT to do (both measured wrong this session)

- Do NOT replace the seat source with the corridor value or the band's
  Chebyshev centre (lane/backedge-seatsrc, reverted 46c27cf: 22/22
  CYXY pads DOWN mean 9.07 m). The band stays the authority; only the
  interval narrows.
- Do NOT chase the route-vs-euclid metric (dead: route ≡ euclid on
  300/300 sampled chords — the enforced graph contains the chord).
- The A4 per-vertex chord ORIGIN cannot currently be expressed
  (nearest_spine is pair-level; origin discarded in canonicalisation).
  If the stand population needs origin awareness, that reader change
  is its own small spec — do not bolt it onto this one.

## Twins

(a) Synthetic corridor + pad at route distance d: seat interval is the
    intersection; DEM inside it is chosen; DEM outside it clamps to
    the intersection edge, never the raw band edge.
(b) Empty intersection → gate record + graded handoff, loud line.
(c) A pad with no frontage band (off-network) behaves exactly as today.
(d) Flag off (`O4_PAD_SEAT_CONSISTENCY`, default ON in-lane) →
    byte-identical to today.
(e) The frontage_band sidecar export (lane/backedge a9d9c88) records
    the narrowed interval beside the raw band interval — census can
    verify seat ∈ intersection.

## Acceptance

- ONE HECA build first: the 525-row large-building class (v5 table,
  findings doc §4) collapses; airside target ≤ 1,487 (report
  honestly); relative drape: apron median within ±0.5 m of ITS
  corridor; cliff metric (B) (shape-pair sites, pinned in
  apron_drape_read) not worse than v3's 532; owner sites -10682 and
  -10144 read smooth; seat-move table (count, worst, per airport)
  prominently — the owner sim-tests after.
- Then SPJC (≤167) + CYXY (≤75... v5 19) — must not regress.
- Usual instruments; [writeback-band] > 10 m = 0; no shared-repo
  writes; no timing. Attempt cap 2 then STOP with the joined
  seat/band/corridor table.
