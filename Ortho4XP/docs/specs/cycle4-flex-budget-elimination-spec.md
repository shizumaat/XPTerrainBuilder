# Cycle 4 — Runway flex budget elimination (owner-ruled)

**Status: BINDING.** Implements RULINGS.md "2026-08-05 — Runway flex: the
LAW is the only bound (owner)". The ruling text is the law; this spec is
its mechanical form. Mode: BUILD-COMPLETE-THEN-DEBUG (RULINGS 12320bd) —
no gates, no flip ceremony; decide-and-note.

## The ruling (verbatim binding)

`RUNWAY_FLEX_MAX_DISPLACEMENT_M` is DELETED, and `budget_left` leaves the
clamp chain — `min(pull, slack)` remains. The lawful bounds are what they
always were: CIFP pins (absolute, v1), runway grade caps per segment incl.
end zones (the priced slack), and the verify-relax apply check.
Minimization stays the OBJECTIVE via the flex's minimum-move demand design
(÷2 splits, drain-what's-demanded), never via an arbitrary cap. Expected:
closes the +7.011 m 05C/23C↔23R law shortfall within lawful profile room.

## Sites

1. `src/auto_patch/config.py:819` — delete the constant. Fix the stale
   comment at `config.py:5067` ("runway flex can add up to …") to state
   the law bounds instead.
2. `src/auto_patch/elevation_per_surface/route_profile/solve.py`
   (`_apply_runway_flex_hook`):
   - delete the import at line ~211 and the "HARD DISPLACEMENT BUDGET"
     comment block above it (lines ~205-210);
   - lines ~407-413: `move = min(pull, slack)`; delete the
     `budget_left` computation. If `original_profiles` /
     `moved_already` have no remaining reader after this, delete them
     too (check the honest-instrument accumulators first — they must
     keep working);
   - fix the stale prose at ~296 ("the 4.0 m displacement budget …
     stands") and the comment at ~4129 that names the constant.
3. Grep the whole tree (`src/`, `tests/`, `tools/`, `docs/specs/` prose
   quoted in comments) for `RUNWAY_FLEX_MAX_DISPLACEMENT_M` and
   `budget_left`; no live reference survives. (Pre-checked: no test or
   tool references exist; verify anyway.)

## Explicitly unchanged

- The demand tolerance (`runway_flex_demand_tol_m`), round-drain floor,
  retirement-after-2, origin split ÷2, greedy keep, slack clamp
  (`flex_slack_at`), snapshot-simultaneous rounds, and the honest
  instrument accumulators. The flex still asks for the MINIMUM move that
  drains the demand; only the arbitrary cumulative cap dies.
- CIFP pins stay absolute (RULINGS "CIFP thresholds absolute for v1").

## Acceptance (flat oracle is the acceptance, per the ruling)

- Unit suite: `tests/test_flex_convergence.py`,
  `tests/test_flex_demand_dead_zone.py`, `tests/test_final_band_inversion.py`
  green (update twins that encode the budget, if any are found).
- HECA constant-DEM oracle (harness `oracle.py` or `build_airport.py
  --dem`): quote the law/ride split lines before/after for the
  05C/23C↔23R pair — the +7.011 m law shortfall is expected to close
  within lawful profile room. Report the residual honestly if it does
  not; a residual is verdict-vocabulary (a)-(d) work
  (no-lawful-infeasible, RULINGS 5578b6a), never re-capping.

Build budget: 1× HECA oracle pair (~10-20 min) + unit twins. Materiality
floor 0.01 m; attempt cap 2; heartbeat per the `.progress` convention.
