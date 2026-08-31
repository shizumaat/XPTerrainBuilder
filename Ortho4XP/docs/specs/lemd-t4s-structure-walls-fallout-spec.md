# LEMD T4S — structure-walls footprint fallout at the basin
# (RULINGS 2026-08-30k; the hecab79 residual-1 class realized)

Confirmed by a matched-control read (bridge round 4, control tree
6d40ce0c, no bridge code): **141 airside within_shape rows** at LEMD,
worst four all 11.94 m at 11.0–16.1 % against a 1.0 % cap, clustered
at 40.49239,-3.56990 — the T4S basin — present identically in control
and arm, i.e. minted by the merged pack-wide structure-walls change
(object_footprints/dsf_reader) at LEMD, absent before it. The
pre-merge LEMD census had no such class.

## Attribution first

The site is the T4S terminal shell (building1 in the current
numbering, was building8; 33,475 m² hull) beside the committed basin
arc (trench floor 587.75, rim 600.25, G=596.682). Hypotheses to
separate (measure, don't guess): (a) the shell's new concave/multi-part
footprint parts intersect the basin rim/trench rings and joined a
grading population the hull never did; (b) a new part's own ring spans
the basin edge so ONE shape carries 588-and-600 values (within_shape at
16 %); (c) pad-seat movement re-seated a part at a wrong value. Use
tools/osm_site.py / role_overlap_read.py on the round-4 matched control
patch; the identity join is canonical 11-dp.

## Constraints (hard)

- Basin-arc invariants: trench floor 587.75, coverage, G=596.682 at
  0.000000 m; rim flush with the pad (600.25 class, RULINGS 30c).
- The building79 law and the structure-walls mechanism stand (owner
  30e/30h) — fix the INTERACTION at the basin, not the footprint law.
- The segmented-linear-array demotion and R18-2 gate untouched.

## Acceptance (site-first)

At 40.49239,-3.56990: the within_shape building rows are gone (the
shell's parts each carry one surface's values); LEMD law-true census
back to the pre-fallout class profile (quote the within_shape airside
count control→arm; round-4 matched control: 183 total / 141 airside);
basin invariants re-quoted. Synthetic twin for the demonstrated
mechanism. ONE closing LEMD build; control = bridge round-4 matched
control (ledger body 839eac5c1c55). Below-bar = STOP with residual.
