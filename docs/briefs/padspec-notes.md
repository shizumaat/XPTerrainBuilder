# padspec notes — handover at machine shutdown (Fable, 2026-10-07)

Branch `claude/padspec` (main b6e2371f). Design only; no engine code touched.

## DONE
- REVIEW: `docs/briefs/padspec-review.md` (verdict per piece, evidence, defect classes).
- SPEC: `design-surface-spec.md` **§56** (appended; `tools/docq.py spec '§56'`): (1) outline rule
  (round close 3 m, DP 1 m, holes < 200 m2 filled, rider rings in, no opening), (2) weld + road
  absorption at 10 m, (3) collar DELETED with replacement table, (4) objects, (5) 38-row consumer
  census (grep-verified by scout), (6) emittability/tunnels/basins/§55, (7) probe numbers,
  (8) bars + build-time + 6-step plan, (9) three owner questions.
- PROBES (need the corpus captures; results saved in `docs/briefs/padspec-scratch/`):
  `outline_probe.py` (12 variants) and `road_probe.py` on perfA362/OTHH.pkl, gaps3/HECA.pkl,
  onelevel318/KCLT.pkl + `/tmp/harness/swg_*.v2/*.graded.json`. Key numbers (also in §56 (7)):
  OTHH unit:28#8/0 1,717 -> 650 verts (holes 34->4, +5,557 m2 of which apron 1,818 re-clipped,
  trench 47); HECA T3 1,476 -> 472; KCLT 990 -> 305; roads at OTHH site 26/29 absorbed at D=10 m
  (170 verts, 2,436 m2), HECA 0/2. Collar evidence (sidecar `platforms` of swg builds):
  rim_relief_max_m 0.000-0.002 on every live OTHH/KCLT collar (KCLT building49 0.23/0.48),
  HECA max 0.415 (building147 residual), minted 5-15 m; OTHH site 12 collar faces, 11 slivers
  1-96 m2; airport-wide OTHH 99 collar faces / 2,589 verts.
- Scout consumer census (file:line) is embedded in `docs/briefs/padspec-summary.md`.

## PARTIAL / NOT DONE
- `padspec-summary.md` is the scout's raw census + short header (no polished summary).
- No frames registered (no new captures taken). ratchets.py not run (docs-only change).
- §56 (1) (5) rider rings: `PlanCluster.rider_rings` is a proposed field; the implementer
  must confirm `rider_candidates` exposes rings (not verified).
- Not verified: `platform_split` call order vs `roles.py:874` cutback for road absorption.
- A cloud lane without the corpus can refine the prose of §56 and the review; it cannot
  re-derive the probe numbers (they come from 0.5-1.1 GB captures on this machine).

## NEXT STEP
Master reads §56 (9) Q1-Q3 to the owner; an Opus implementer takes §56 (8)'s plan step 1.
