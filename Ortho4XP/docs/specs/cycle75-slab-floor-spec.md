# Cycle 7.5 — Slab budgets floor at the law

**Status: BINDING.** Implements RULINGS 2026-08-06 "Slab budgets floor
at the law" (owner-ratified). Evidence: c7cert fix-4 STOP dossier —
7,218 of 7,920 §10 rod slabs price TIGHTER than the grade-law cap on
their own pair (median 5.26×, p90 26.45×, max 2,305×), owning 6,300
over-cap edges (31.5% of HECA's converged fp#8 residual).

## The change

Every interval/slab (rod-channel) budget FLOORS at its pair's
grade-law budget: `slab_budget = max(slab_budget, law_budget(pair))`.
A slab may narrow freedom only down TO the law, never below it.
Smoothness (smoothest, minimum grade) remains the solve's OBJECTIVE —
soft, never a hard constraint beyond law. One clamp site at the slab's
minting/pricing authority (find it with blast.py; do not scatter
clamps at consumers). The §10.1 clamp lookup precedent (emit-
amplification fix f9953d0) is the nearest existing pattern — extend,
don't fork.

## Acceptance

- HECA dem1 instrumented build: the slab-owned over-cap class (6,300
  edges) collapses; fp#8 residual and SOLVE EXIT certificate quoted
  before/after; census vs the current frame (HECA dem1 5,969).
- COUNTER-READ (the reason rods exist): the seam families —
  strip_seam_tear, adjacent_ground_tear, mid_edge_step — must stay
  flat or improve, both HECA worlds + HEAZ sentinel. A regression
  there is a STOP-and-report (the repricing then needs the
  seam-continuity design review, not a bigger clamp).
- Twins: a slab-tighter-than-law synthetic must come out floored; the
  seam twins stay green.

Budget: ~3 builds + twins. Materiality 0.01 m; attempt cap 2;
heartbeat; foreground; no real-DEM; no shared-repo writes.
