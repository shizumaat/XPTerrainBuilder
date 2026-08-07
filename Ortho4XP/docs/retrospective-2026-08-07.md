# Retrospective — why HECA airside is not under 100 tonight
2026-08-07 ~00:30 PDT · tip `13d7ef1` + lane/c9air · frame: flat
worlds −500/10,000, harness census, adjudicated airside

## The number and the verdict

HECA adjudicated airside stands at **3,734** (−500 world; canyon
4,006, unfixed tonight). The gate was <100 by 04:00. The mechanism
ladder run tonight (fp#8 offline replay, every constraint class
knifed out one at a time) proves the remainder is not a tuning or
convergence problem: with every box and interval removed the law
itself is satisfiable (742 over-cap, worst 0.08 m). What holds the
3,734 up is FOUR named structures, each needing a designed round,
none safely landable in a release-night window.

## The four remaining defect structures (our best understanding)

**1. Pad-frontage seating — ~50% of the remainder (1,870 rows on 40
building ways).** Your "frontage coupling ⇒ band seating" ruling
landed its first half (pads seat FROM the band — the 2-cycle died).
The second half never landed: the frontage CHORD between a seated pad
and its apron must either grade within apron law or take the ruled
relief form. Today the seat is lawful and the chord is not priced:
worst case one building seat 7.42 m above its apron across 183 rows.
Splitting by distance shows both sub-classes: long chords (≥50 m,
638 rows) are all lawful at even a 5% relief cap — they are RELIEF
work; short chords (<10 m, 485 rows, p50 grade 8.6%) mostly survive
any cap — they are STEP/WALL work (the split-level form). This is a
spec-and-round, not a fix: it decides, per frontage, which ruled form
applies.

**2. Relief generation is incomplete law — (b), the largest single
"why".** HECA declares 34 fan zones and 12 terrace joints, but only
358 of 4,305 within-shape rows sit on declared relief. Even a
BLANKET 5% apron cap would leave 1,368 rows — meaning no cap change
reaches zero: the generator must CREATE more relief (more fan
coverage, more panels) than the current zone construction yields.
This is the same class as the drainage-minimum project you deferred:
generation machinery, not repair.

**3. Feature-weld hardening — structural, 2,045 both-hard edges.**
Between the two final projections the hard node set grows 1,120 →
9,527 (strips and walls hardened by feature welds). An over-cap edge
between two HARD nodes is unfixable by any projection by
construction — both ends are frozen. The cure is upstream (what may
harden, and when) and touches the emit chain — a designed round with
the seam families as its counter-read.

**4. On-DEM airside stranding — the whole ≥10 m airside band (89
rows), deliberately not fixed blind.** 140 airside-role vertices sit
exactly on the DEM constant. Two readings, and they need YOUR
adjudication, not a guess: (a) a missing airside seat ladder (these
vertices should have been seated from the graph and weren't), or
(d) a missing lawful-terrace exemption — under the adjacent-ground
zone law some of these may be the lawful graded/DEM boundary the
census should adjudicate as terrace, not defect.

## Why we could not eliminate them tonight

Tonight's lane landed everything that was safely landable: one (a)
fix (a groundside pin ceiling silently tightening airside bounds
through the partition's pair-only coverage — partition now covers
BOUNDS; −395 rows, twinned, byte-identical everywhere else). The
rest failed the release-night test on purpose: each is
already-RULED law whose second half is a designed round (1), new
generation machinery (2), an upstream architecture change (3), or an
open owner adjudication (4). Landing any of them under a 03:30
freeze would have meant improvising architecture against your own
deviation protocol, with the whole battery as blast radius.

The honest campaign-shape answer to "why is this taking so long":
the elimination has been real — HECA airside 20,629 → 3,734 (−82%)
across cycles 5–9, the canyon from unbuildable to counted — but
every cycle's attribution had to be dug out from under instruments
that misreported (all since calibrated and twinned under your
instrument-truth ruling). What remains is no longer mystery: it is
four named structures with owners, three of them waiting on design
rounds and one on a sentence from you.

## What I recommend next (in order)

1. Your adjudication on item 4's (a)-vs-(d) split — one sentence.
2. The pad-frontage round (item 1) — spec exists in outline; largest
   single win (~1,870 rows).
3. The relief-generation round (item 2) — the real drive-to-zero
   long pole; should be scoped WITH the deferred drainage project
   (same generator).
4. The hardening round (item 3).
5. Cycle 9 (road feed → graph) is in flight tonight and lands the
   groundside mass independently of all of the above.

No app was built, per the gate. The tree is green, every lane's work
is merged or parked cleanly, and the checkpoint boots the next
session into this exact state.
