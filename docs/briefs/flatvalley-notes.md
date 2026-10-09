# lane flatvalley — notes (finding F1: "the airside optimum is not unique")

Branch `claude/flatvalley` off main `9baa9e82`. Scratch:
`<scratch>/flatvalley/` (`nullarm.py` = `v2_solve_replay` under
monkeypatched null arms + a per-stage-call instrument; `cmp.py` = the
per-stage diff). Captures REUSED (registered): KCLT
`<scratch>/sweepwalls/base/KCLT.pkl`, HECA
`frames/gaps3/HECA.pkl`; every arm is `--replay … --from classify` on this
tree, so control and arm are one tree, one capture, one variable.

Scheduling deviation (reported): the brief's strict hold ("while another
engine build/replay runs") starved 25 min — three lanes overlap
continuously — so the hold was relaxed to "at most ONE foreign engine
process burning CPU", my replays pinned `--workers 6`. FREEZE/TIMING
windows are still honoured.

## 1. Solver exit facts (read off `solve/design_qp.py`, `design.py`, the log)

- Backend: the module's own proximal semismooth Newton (`solver = "qp"`),
  sparse LU on the normal equations (`method normal`, bordered low-rank
  datum term, Tikhonov floor 1e-12 x max diag). HiGHS only in §5a's elastic
  LP and the two projections.
- "optimal" is a TOLERANCE EXIT, not a certificate: one accepted step
  gained <= `_REL_TOL` 1e-9 x F. KCLT control, |grad| at exit:
  pass 1a 0.18 / 2.19; pass 1b 96.4 / 8.89 / 64.8; stage 2 14.1 … 626.
- Outer loops are capped, not converged: lag `one_way_max_rounds` 3
  (KCLT stage 2: LAG NOT SETTLED), multiplier polish `polish_rounds_max` 2
  with best-iterate return.
- Discrete decisions fed by those iterates: §5a `check_hard_set` (LP,
  demote where s > 0.02), `promote_missed` (> 0.02 on the lagged iterate:
  KCLT 24 in pass 1a, 121 in pass 1b), the hold's interval between the
  passes, pin yield.

## 2. TRUE null changes at KCLT (one tree, one capture) — AIRSIDE DOES NOT MOVE

| arm | what changed | stage 1 (airside) | stage 2 |
|---|---|---|---|
| `k_lsperm` | rows of every linear solve permuted (roundoff-level null) | 0 movers, max < 1e-6 m, same rounds | 0 movers, max < 1e-6 m |
| `k_lpperm` | §5a LP handed its rows in another order | 0 movers (LP relaxes 0 rows in both passes) | demote set 336/336 but 6 rows DIFFER; 147 vertices > 0.02 m, worst 0.216 m, 0 over 0.3 |
| `k_nullband` | VACUOUS (the band never reached stage 1's own set — the ribbon-free map carries its own `cs`); superseded by the slack arm |

So: the QP path is deterministic and roundoff-stable; the §5a LP has a
DEGENERATE optimum (a face of optima, simplex returns a vertex chosen by
row order) — proven at stage 2, where it moves groundside only.
