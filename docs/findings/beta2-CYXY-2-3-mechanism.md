# BETA2 CYXY-2 / CYXY-3 — interventional mechanism (lane b2cyxyhill)

STATUS: STUB. Rows CYXY-2 / CYXY-3 of docs/BETA2-BLOCKERS.md.

Sites: 60.7141907,-135.0766528 (`building9 -> pav4`), 60.7155636,-135.0792452
(`building10 -> dsf:pol129`). Attribution (no interventional measurement yet)
in docs/findings/beta2-CYXY-SPJC-regressions.md §"CYXY-2 and CYXY-3".

Plan: capture CYXY with tools/v2_solve_replay.py, replay from the constraint
stage, read `pairs_held_as_terrace` and each pair's `pair_dem_step_m` against
`frontage_step_max_m = 3.2` (law/emit.toml:530-547), then intervene on ONE
variable (the pad median the step is measured against).
