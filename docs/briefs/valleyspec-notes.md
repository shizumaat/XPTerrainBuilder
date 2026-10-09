# valleyspec — notes (spec §61: the taxiway edge takes its centreline's level)

Lane `valleyspec` (Fable, spec author; edits NO engine code), 2026-10-09.
Branch `claude/valleyspec` = `claude/flatvalley` + main `e2eec15c` (engine identical
to main; `docs/frames.jsonl` merged both sides).  Scratch `<scratch>/valleyspec/`;
the arm scripts are copied to `docs/briefs/valleyspec-scratch/` (`nullarm.py` =
flatvalley's arms + the `xsec:W` / `xfall:W` / `xreach:M` arms; `freeclass.py` = who
the free columns are, by the chain that could name them; `arm.sh`, `hold.sh`,
`measure.sh`, `null.sh`, `cmp.py`, `mv.py`).  Captures REUSED: KCLT
`<scratch>/sweepwalls/base/KCLT.pkl` (9baa9e82; the engine under `solve/` and
`constraints/` is unchanged to e2eec15c and KCLT was byte-identical across the
gap-piece merge — the fresh control on this tree reproduces flatvalley's pass-1a
F 126360.912 exactly), HECA `frames/gapapron3/HECA.pkl` (183edd34, re-derived at
`--from classify` under this tree, so the gap-piece apron cells are in).

Scheduling: the hold is flatvalley's relaxed form (at most ONE foreign engine
process over 50 % CPU; FREEZE / TIMING windows always) — reported as a deviation
from the brief's strict hold, same reason (three lanes overlap continuously).
Walls quoted are single runs under foreign load.

## 1. Who the unnamed columns are (probe 0, offline: `freeclass.py` on flatvalley's pass-1a QP dump + the control's `pm_s1`)

KCLT 1,797 free columns (bend-only, no body datum):

| n | class | why no level today |
|---|---|---|
| 1,435 | taxi-family face whose own chain is SHORT (< 250 m = half `runway_profile_window_m`), foot in reach (median 35 m, p90 142 m) | §8.6.1 extends the trend across a face only for a LONG chain; a chain is one breakline between branches, so a long parallel is many short chains |
| 191 | owned face, foot past `taxi_trend_face_reach_m` 250 m | the reach backstop |
| 89 | long chain's face, foot in reach | the fit returned no value at the station |
| 53 | taxi face no chain owns | nothing to project on |
| 28 | shared with a building pad | free in pass 1a only (hold rows dropped); held in 1b |
| 1 | not taxi-family | — |

## 2. The arms (KCLT, `--from classify`, one tree one capture)

| arm | null-change (bar ≤ 20 @0.02 / 0 > 0.3) | cost vs control (pass 1b stage-1 movers / > 0.3 / worst) | runway (avd) | adjudicated airside | note |
|---|---|---|---|---|---|
| control | 1b 615 / 31 / 0.81 | — | — | 3,355 | reproduces flatvalley |
| xsec 30, v1 (pin COLUMN priced) | — | 4,442 / 668 / 1.96 | 166 / 0.235 | — | WITHDRAWN: the chain's runway-contact column at 30 pulls the runway |
| xsec 30 (pin as VALUE) | 1a 3 / 1b 29 / 0 / 0.25 | 4,462 / 671 / 1.96 | 179 / 0.24 | 3,238 | REFUTED weight: `airside_no_step` +47 (steps to 2.4 m), `taxi_box` +104 — the row outranks the sheet |
| xsec 3 | — | 2,213 / 363 / 1.59 | 29 / 0.11 | 3,294 | `taxi_box` +15 |
| xsec 1 | — | 1,642 / 330 / 1.49 | 4 / 0.06 | 3,351 | families ± 3 |
| xsec 1 + membrane 0.3 on the 321 leftovers | 1a 0 / 1b 37 / 0 / 0.10 | 1,799 / 366 / 1.49 | 4 / 0.06 | 3,339 | MISS on count: pass 1b's `no_descent` floor |
| **xsec 1 + membrane 1.0 — RULED** | **1a 0 (0.0003) / 1b 0 (0.019) / whole map 0** | 1,827 / 384 / 1.49 | 4 / 0.06 | 3,336 (−19) | taxi tier 51 = 51; CRITICAL `groundside_cutback` visual 3 → 2; walls 17.8 + 33.1 s (control 13.3 + 22.7) |

Frames (registered, `frames.py list KCLT`): control `valleyspec/KCLT_auto.patch.osm`,
ruled arm `KCLT_auto.patch.e2eec15c.osm` (the register's own rename), null twin
`k_xs1g_slack_KCLT.osm`, refuted weight `k_xs30_KCLT.osm`.

## 3. HECA (`gapapron3/HECA.pkl`; control + ruled arm + null twin)

Ruled arm `h_xs1g` (1,160 cross-section rows, 28 pin constants; 5,369 membrane rows on
2,139 columns — 1,743 on taxi faces NO chain owns, HECA's big `dsf:objpav` junctions):

| | control `h_ctl` | ruled arm | twin `h_xs1g_slack` | twin + the arm's §5a set FORCED `h_xs1g_slackF` |
|---|---|---|---|---|
| null-change 1a / 1b | (lane) 157 / 535 | — | **0 / 1,813** (0 > 0.3, worst 0.195); demote 14/14 with ONE pad `frontage_hold` row different (two adjacent rows of the pad at 30.1286, 31.4021), promote 812 / 810 | **0 / 4** (worst 0.14 at `gapapron:1` 30.10294, 31.39591); sets equal |
| cost vs control (1b stage-1 movers) | — | 3,739 / 367 > 0.3 / 0.98 | | |
| avd | — | strip 2,869 / taxi 1,246 / apron 848 / runway **2 / 0.06** | | |
| adjudicated airside | 12,201 | 12,170 (−31); `hard_conflict` 240 → 237; taxi tier 62/61 = | | |
| CRITICAL | | `strip_seam_tear` visual 22 → 23; `vertex_to_edge_step` motion 0 → 1 (apron|junction 0.52 m over 0.98 m at 30.10901, 31.40396, unshared ways −10704/−10670) | | |
| stage-1 wall | 84.7 + 83.9 s | 73.3 + 117.0 s | | |

So at HECA the valley closes (1a: 0) and the remaining pass-1b non-reproducibility is
the §5a LP's degenerate choice among equal relaxation sets — attributed by
intervention (1,813 → 4), AIRSIDE, hence ruled as part of the change (§61 (5)).

## 4. Deviations and what was not done

- The membrane fallback's weight 0.3 (the lane's QP-level finding) was NOT enough in
  pass 1b (37 movers); the ruled 1.0 is the same number as the cross-section row.
- A one-way form of the cross-section row (the edge follows, the chain never feels
  it) was not built: the engine's lag machinery is one-sided-row only; the pin as a
  VALUE removes the only pull that mattered (runway 166 → 4 vertices, 0.235 → 0.06 m).
- The route-level (whole-letter) taxi trend across chain pieces is reported, not
  designed.
- Nothing landed in the engine; no closing build (no engine file changed).
