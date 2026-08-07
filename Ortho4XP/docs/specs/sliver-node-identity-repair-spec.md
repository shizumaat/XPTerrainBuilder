# Sliver / node-identity regression repair — spec

Author: lead (Fable), 2026-08-07. Charter:
`Ortho4XP/tmp/sliver_attrib/sliver_attrib_dossier.md` (46-point
vintage series) + `Ortho4XP/tmp/density_audit/density_dossier.md`.
Governing law: `cycle5-node-identity-spec` — the
shared-boundary-spelled-twice class is FORBIDDEN (cut on the settled
lattice; planarize snaps, never twins; weld-after-cut FORBIDDEN).
Phase A is justified by that law alone, independent of the sliver
question; Phase B is the interventional arm both dossiers lack.

## Phase A — repair at mint, under existing law

A1. **Interior-ring emission** (landing `8c6e047`, layout.py:2570
region): interior rings must INTERN against existing boundary nids
where they touch existing geometry — the code's own "already-interned
… nothing new is created here" assertion becomes true by
construction. Repair at mint; post-hoc welding is forbidden by the
governing spec. Specimen acceptance: ring `-13507` shares nids with
the two `groundside_pavement` ways it crosses (the 18.5 mm class is
gone).

A2. **Wall emission weld completeness** (the 08-05 terrace/wall
block, `db4d823`→`3850c92`→`8c6e047`): wall vertices lying on foreign
edges weld — private-on-foreign-edge returns to the A5 envelope
value 0 (specimen: wall `-13298` vs svc_junction `-12373`).

A3. **Fix-P coincident mints** (c5nodeid merge, `f5b643b`):
apron-role coincident-node coordinates return to the pre-merge
envelope (≤3), repaired at the minting site.

Acceptance A (pinned instrument
`Ortho4XP/tmp/sliver_attrib/cda_pinned.py`, sha efd18c00 — never a
drifted copy; REAL frame): T-vertices / near-parallel / coincident /
crossings return to the 08-01→08-05 envelope (tv ≤ 35, np ≤ 11,
co ≤ 3, x ≤ 36). Oracle-world (−500/10,000) patches: matched-control
battery censuses; every moved row attributed; zero new adjudicated
airside anywhere (airside-negative trades forbidden). The unpinned
`graded_strip~graded_strip` creep family is OUT OF SCOPE — do not
chase it; report its counts unchanged or improved.

## Phase B — the interventional sliver counter-read

Re-run the mesh step only (the density audit's offline method, its
scripts beside its dossier) on TODAY's HECA frame: fixed patch vs
unfixed patch, same everything else. Count in-bbox sub-0.1 m² mesh
triangles. PRE-REGISTERED expectation: the fixed patch collapses the
~2.36 M sliver class toward the 08-05 DSF baseline (~466 in-bbox
DSF; stock mesh 18). If ≥50% of the sliver mass SURVIVES the fix:
STOP and report — the unpinned creep family becomes the prime
suspect; that is a new attribution round, not this lane's chase.

## Sequencing constraint

Real-DEM harness builds are currently impossible (the guard-blocked
DEM-prep degrade hole; separate harness fix lane dispatched
2026-08-07). Phase A's oracle-world verification may proceed
immediately; the REAL-frame series point and Phase B run AFTER the
harness fix merges. Do not work around the guard.

## Budget

Phase A: 2–4 patch-only builds post-harness-fix + the oracle pair;
Phase B: 2 offline mesh runs. Build-time impact: none intended
(interning at mint); any measurable phase delta is flagged for the
ledger tripwire. Deviations: STOP and report for Fable review.
