# Auto-patch week review — main 2026-08-31 → 2026-09-03 (4f2cc234)

Page: https://claude.ai/code/artifact/32b12a80-726b-494a-b419-0e2333f6caf2
(same content, with tables). Three read-only sweeps: every merge vs its
recorded measurement; the phase-time ledger; a pass-by-pass read of
`src/auto_patch`. No builds were run.

## Verdict
* **Airside count: not moved.** HECA acceptance-airside 1,075 (09-02
  sweep) → 1,094 on main (+19 NEW strip_seam_tear, unowned). Every
  airside DECREASE recorded this week is an instrument correction (air1
  −765, zero patch bytes) or SPLP's H5 (−25); every real surface change
  booked a small airside INCREASE kept under a ruling (4a +46, H7 +12/+3).
  The big wins (HECA 6,403 → 2,838 total) are groundside/far-ring totals.
* **Performance: mixed.** Exclusive 2-run medians 08-31 → 09-02: HECA
  −102.7 s (756.7), OTHH −39.6 (434.0), LEMD +25.7 (573.9, emit +14
  unattributed), SPJC/CYXY/SPLP hold. HECA is 12.6× the 60 s gate; tiles
  2.3–3.3× the 300 s budget. No timing evidence for anything merged 09-03.
* **Plan of record: right axis, wrong root** (below).

## Merges (verdict decided by one fact)
VALIDATED: 4a (total −2,170 HECA), hard5 (SPLP −25 vs matched control),
H7 (runway 0), apt.dat skip 459125a0, wallcrest (OTHH airside 1,202 =
1,202, groundside −92). NEUTRAL-BY-DESIGN (gate-OFF byte-identical):
fgp S1–S3, air7, ovfix, 2c reverted, chipmerge, r1attrib. REFUTED: air4
(deleted), air6 (kept gated OFF against 29e). UNVERIFIED: Batch 1+2 (no
airside split ever recorded), ltbatch3 (never built at KCLT), building
split (no numbers), weldov (its HECA/KCLT arms never built — sole
emit-side suspect for main's +19), tilewedge (cause unreproduced).
Seven merges since the last five-airport sweep (29f owed); the KCLT /
SPJC airside split the plan calls "first action of R1" never computed.

## Architecture (20 passes; the solve is pass 12 and owns every vertex)
After the solve: post-solve terrain emit (3 wall emitters, transition
law), feature conformance (deconflict ×2, enforce ×5, chord limit ×4,
separation ×2), five pre-FGP re-seeders (881 + 198 + 113 + 101 value
changes on solve-owned nodes; decimate is ring re-mapping only), FGP
(rebuilds node list/graph from scratch; `membrane_conform` lives ONLY
here; S1–S3 default OFF), post-projection receivers (relevel ×3, crown
extension duplicated at solve.py:8644 and pipeline.py:7819), strip
reconcile (four more retaining-wall emitters), late reclips; tile_cut
×7. Post-solve `node_altitudes` writers: groundside 2, decimate 1,
conformance 2, FGP 1, anchors 10, tile_cut 9, crown 3, gap_fill 4,
boundary 10, seam_anchors 5, + ~50 shape constructors.

Redundancy census (single derivation site per 30l): FGP graph vs solve
registers (716/2,167 residuals minted by the rebuilt graph); five
re-seeders; crown ×2; 60 m chord cap in three symbols / two decimators;
`unary_union` 159 calls, 36 in loops, `_tunnel_pavement_union` uncached
in a triple loop; `law_anchor_values` rebuilt by 11 callers; THREE
below-grade ref lists that DISAGREE (groundside / road_bridge_deck /
building_feasibility); law frame parsed 2–4× per census; O(n²) shape
loops without STRtree (pipeline 4791, six in bridges); seven
retaining-wall constructors; ~1,500–2,000 road lines duplicating the
core's `clamp_road_network` + ~1,050 lines of gated-dead depressed-road
emitters (29e: delete).

## Is the plan right?
Right that nothing measured downstream of FGP means anything until the
surface it consumes is lawful, and that emit is innocent. Wrong root,
twice: (1) `membrane_conform` exists only inside FGP, so "drive imposed
law to feasibility inside the solve" relocates the pass; and R1.2 arm B
proved the pin set INFEASIBLE (1,368/4,498 nodes, 20.64 m demanded vs
3.76 m budget). A real airport has a lawful surface, so the contradiction
was minted BEFORE the solve — runway datum (pass 6), bridge/deck pins
(7), zone dem_seed (10), scorer roles → caps (8): R4/R5 territory, which
the plan schedules after R1. (2) R1 reads acceptance at FGP entry, after
the five re-seeders re-authored 1,293 solve values — measure at
`00_post_solve` or retire the re-seeders first.

RECOMMENDED REORDER: R1.3 attribution of the infeasible pins → one owner
ruling on which senior yields → retire the five re-seeders and the FGP
rebuilt graph (S1 consumes the registers) so ONE author stands between
solve exit and emit → then re-measure air2/air3/bldround and run R3–R5.
Each step removes a writer; none adds a pass.

## Size
Upstream Ortho4XP 1.40.12 whole program 17,979 lines; vendored core
52,294 (11,433 = our inset module); auto_patch 225,964 (comments +
docstrings ~90,300; code ~120,000; 3,387 functions, 14 over 1,000 lines;
605 `O4_*` gates, 192 default-ON, 40 default-OFF; "RETIRED" ×324,
"byte-identical" ×404, 3,258 dated references in source). A principled
implementation of the objective is ~20k lines; we are ~6×. The size is
the architecture's symptom: authority spread over a dozen post-solve
writers, each repairing the last, each with its own law spelling,
union, gate and history. Consolidation is deletion, not rewrite: every
post-solve writer becomes a solve constraint or goes; gates burn in /
delete; seven wall constructors → one; unions and anchor dicts → layout
attributes; roads → the core; prose → RULINGS.

## Owner decisions
1. Reorder R1 as above, or keep the plan's order.
2. Which senior yields when runway datum / deck pins / zone seeds /
   scorer caps contradict by 20 m (R1.3 names the pairs).
3. Pay the owed sweep + KCLT/SPJC airside split on main before any
   further merge.
4. Adopt deletion as the round shape: a round closes when a writer is
   gone and the count did not rise.

Superseded the same evening by the owner's direction to plan
`auto-patch-v2` from the ground up (see `auto-patch-v2-plan.md`).
