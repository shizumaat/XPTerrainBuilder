# SM3 — Certified solver exit + empty-interval refusal (Fable, 2026-08-15)
Evidence: C1 attribution (task record; /tmp/c1/). 263+ HECA airside rows
(236.9 m excess) trace to: (a) the stall criterion — relative test
(drop < max(1, 0.5 %·n_material), patience 2) exits a STILL-DESCENDING
solve at sweep 2,632/250,000 with the certificate showing over_cap
apron edges ALL carrying a free endpoint (both-hard=0 — headroom
exists); (b) phase-A harmonic splitting 2,061 EMPTY polytopes
(cap_slab vs band_ceiling up to 10.11 m) at the midpoint — laundering a
contradiction the writeback then clamps ("a clamp is EVIDENCE of a
solver defect upstream").
1. EXIT IS CERTIFIED, NOT PATIENT: replace the relative flat-block test
   with an absolute criterion — exit only when material violating edges
   (≥0.01 m) stop improving in WORST RESIDUAL and COUNT over a patience
   window, or the sweep budget is spent; report the certificate delta.
   Never exit "converged" while both metrics still descend.
2. EMPTY INTERVALS REFUSE OR RESOLVE, NEVER MIDPOINT: attribute the
   binding pair per node (cap_slab_from_X vs band_ceiling etc.); where
   the band ceiling is the lawful winner widen the slab read to the
   band's route metric for that node; a residual genuine contradiction
   REFUSES loudly (feasibility-is-guaranteed posture), never midpoints.
Acceptance: HECA census airside within_shape falls by the SM3 share
(report per sub-mechanism using the C1 method: pairs over their own
baked budget); worst residual and certificate over_cap counts reported
before/after; no new family; CYXY byte-stable or attributed; capture
the [apron-terrace] DEMAND CENSUS margin histogram from the
O4_STEP_DEBUG build (the C1 dossier's one outstanding measurement) and
include it in the report. Wall delta from the ledger frame (the
criterion change may add sweeps — state it; budgets law still suspended
but tripwire applies). Materiality 0.01; attempt cap 2; STOP to lead.
