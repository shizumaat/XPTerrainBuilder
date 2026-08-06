# Cycle 5 — Solve certification round (the three (a) bugs)

**Status: LANDED (lane/c5solve, 2026-08-05) — all four fixes implemented
and measured; CERTIFIED exit NOT reached; the honest residual is
quantified below.**

Identity control first: the lane tree reproduced the dossier VERBATIM
before any fix (fp#8 68,672 / 91.617185 m; envelope 14,246 of 18,113 /
74.685667 m; zone consumption 124,183; census 28,059 → adjudicated
21,404 = the tip matrix). Every delta below is therefore attributable to
these diffs. Frame note: this lane does NOT carry `lane/c5inst`.

| fix | verdict | outcome |
|---|---|---|
| 4 certificate | (d) | LANDED. Catch-all split by minting constructor; violating-family count; a SOLVE EXIT reader in the solve's own node space. Surface-neutral (census byte-identical). |
| 1 zone box | (a) | LANDED. Box deleted; relative edge is the one authority; coverage audit proves it lossless (**0 UNCARRIED**, 3 airports). |
| 2 band per sweep | (a) | LANDED. Biggest single win: adjudicated −69%. |
| 3 gs_pin | (a) | LANDED. Hard gs_pin 156→0, on-DEM 25→0, out-of-band hard nodes 70→**0**. |

HECA plateau, round total: adjudicated **21,404 → 6,442 (−69.9 %)**,
airside **20,629 → 5,759 (−72.1 %)**. KCLT plateau **7,477 → 3,404
(−54.5 %)**; its fp#8 raw-law envelope reaches **0 of 22,298 INFEASIBLE,
max gap 0.000000 m** — the spec's stall-guard target, met at KCLT.
HEAZ dem1 1,160 → 1,100; HEAZ dem10000 216 → 212; KCLT dem10000
3,807 → 3,620.

THE STRUCTURAL RESULT. The solve's over-cap population changed CLASS.
Before: `free:below-band ↔ free:below-band` 75.6 %, worst 97.499 m
(the fix-2 defect) with a live `HARD:gs_pin` class. After: that class
and the gs_pin class are both GONE from the table, and the dominant
class is `free:in-band ↔ free:in-band` — 82.66 %, worst 15.950 m. That
is the class the dossier named as the next round's population. (Frame:
both read at the fp#8 dump; the dossier's 3.9 % / 5.620 m was at fp#8
EXIT over a different edge set — the two are NOT the same number and are
not equated here.)

NOT MET, reported rather than chased (attempt cap):
* No airport reaches a CERTIFIED exit. HECA plateau's fp#8 worst
  residual is unchanged at 89.430942 m, carrier `(1013,7022)` — now
  `free/free`, its raw-law envelope gap fallen 74.686 → 16.856 m.
* HECA `--dem 10000` still HARD-FAILS `BandInversionError` identically
  to the tip (384 nodes, worst 1.9521 m, the same 3 anchor pairs). The
  error attributes itself: the CIFP thresholds do not reach each other
  within the route budget — a METRIC/CAP/TOPOLOGY defect, i.e. the
  runway-flex round's territory, not this one's.
* `who_wrote --author` still reports **1,634** untouched-node moves
  (worst 87.930 m) — the second-author class is NOT collapsed. The hold
  ledger's distributional halves did move: final#1 max |dz| 37.319 →
  4.486 m, final#2 p90 6.820 → 1.540 m.

**Original spec text follows unchanged.**

**Status: BINDING.** Evidence: the attribution dossier
(c4tip worktree, `tmp/c5attr_dossier.md`; tip `97838ce`; one
instrumented build, byte-identical body — instrument surface-neutral).
ALL SEVEN tip battery builds exit UNCERTIFIED, both flat worlds; the
solve-exit decomposition at HECA plateau: 68,672 violating edges —
apron 27,087 / junction 21,232 / graded_strip:adjacent_ground 21,115 /
catch-all 5,163; raw-law adjudication: 14,246 of 18,113 reachable nodes
envelope-INFEASIBLE (max gap 74.69 m). Every dominant family verdicts
**(a) BUG**; no law change is authorized by this spec. Mode:
BUILD-COMPLETE-THEN-DEBUG.

## Fix 1 — ONE authority for the adjacent-ground law

The relative interval edge (`solver_primitives.py:2416`) IS the law.
`_zone_foot_boxes` (`solve.py:1384`) snapshots the SAME law as absolute
constants from the fp#8-ENTRY pavement datum and re-clamps every sweep
while the projection moves that datum (p90 24.949 m, max 88.905 m;
65.6% of over-cap rows inside the STALE box vs 6.7% live). Required:
no clamp may derive from a stale datum. Either re-derive the box from
the LIVE datum each sweep, or — preferred if the relative edges fully
carry the law (measure it) — DELETE the box clamp as the duplicate
authority. Acceptance: stale-box row share → 0; the
`graded_strip:adjacent_ground` family (21,115 at exit; the >10 m
tail's 64.79%) collapses; the KCLT dem1 225.34 m / HECA dem1 114.33 m
adjacent-ground residuals go with it.

## Fix 2 — the band BINDS per sweep

The reach-band floor is a ONE-SHOT pre-sweep clamp (`one_solve.py:2566`)
while caps and boxes bind per sweep — decisive asymmetry: 11,144 nodes
below floor (worst 89.637 m) vs 112 above ceiling (0.187 m), 99.5:1,
never improving across all 8 recorded stages. Required: band
floor/ceiling enter the per-sweep constraint set exactly like every
other law. Acceptance: below-floor population → ≈0 (materiality);
the `apron:-`/`junction:-` families (64.3% of edges) collapse.

## Fix 3 — no groundside HARD pin at raw DEM

All 70 out-of-band hard nodes are `gs_pin` — raw DEM entering the solve
as a hard anchor (worst: pinned at 1.000 m, 85.657 m below its own band
floor, dragging an in-band building seat). Standing law: DEM is a SEED,
never an authority; groundside NEVER pulls airside. Required: enumerate
every `gs_pin` source; demote raw-DEM pins to seeds (band-bounded per
the adjacent-ground / groundside law). Boundary-ribbon and tile-seam
hard classes keep their own law — do not sweep them in; name each
source kept-hard with its law citation.

## Fix 4 (d) — the certificate's family axis

The ENTRY/EXIT certificate's arithmetic is verified (10/10 hand-checked)
but its family attribution dumps 80.6% into a catch-all, counts
families-present as "425", and reads a rebuilt constraint set in a
different node space — its ENTRY is NOT the solve's exit state.
Required: the certificate reads the solve's exit in the solve's node
space; family attribution keyed to the constraint constructor that
minted each edge. Report-only instrument; no surface effect.

## Acceptance (the whole round)

- Instrumented builds: HECA `--dem 1`, KCLT `--dem 1` (the worst case,
  114-225 m class), HEAZ sentinel. Target: CERTIFIED exit, or the
  quantified honest residual — the 3.9% in-band-pair class (worst
  5.620 m) is expected to remain and is the NEXT round's population;
  quote it, do not chase it (attempt cap).
- Raw-law adjudication (`O4_STALL_GUARD_ADJUDICATE=1`): envelope-
  INFEASIBLE 14,246/18,113 → 0, or every survivor named.
- Census on the built patches (harness): expect LARGE drops vs the tip
  matrix (checkpoint block); quote honestly, both worlds.
- Suite + harness twins green; the fp#8 hold ledger and who_wrote
  --author confirm the projection stops absorbing (untouched-node
  moves collapse toward materiality).
- The c4tip worktree carries an uncommitted +60-line instrument diff
  (O4_DUMP_SOLVE_STATE keys + .fp8exit.pkl) for re-running the reader —
  replicate under the gate if needed; do not land it unreviewed.

Budget: ~3-4 instrumented builds + suite. Materiality 0.01 m; attempt
cap 2 per fix; heartbeat. No real-DEM builds; no shared-repo writes.
