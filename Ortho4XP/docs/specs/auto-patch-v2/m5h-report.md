# auto-patch-v2 — M5h report: pads are one flat group (lane v2padflat, 2026-09-05)

Lane `lane/v2padflat` off main `3e95e73f` (the v2integ merge). Brief: the
M5 twin whose pad reads 711.34 … 712.51 m (1.18 m across) is RED — "a
rigid flat group no longer holds in the HARD mode; a tilted pad would
ship sloped buildings". Every law value from the TOML tables (no new
key); no env reads; no v1 imports; every touched file ≤ 1,000 lines
(largest `pipeline/build.py` 423, `engine_v2.py` 534). Attempt cap: one
attempt per target.

## 0. Site first

| airport | tag / artifact key | build s | hard set | oracle census adj / airside | pads not flat (`pad_flat`) | v2 verify rows |
|---|---|---|---|---|---|---|
| CYXY | `CYXY_20260904T150604` / `bd78e2c034b4` | 4.8 | feasible | **0 / 0** | **0** of 10 | 0 |
| SPJC | `SPJC_20260904T150610` / `d7ca6dc04663` | 51.4 | feasible | **0 / 0** | **0** of 53 | 2 `adjacent_ground_tear` = the v2integ control's own (`SPJC_20260904T143940`: 2; oracle 0/0 both) |
| KCLT (stored, v2integ round `KCLT_20260904T143118` / `9cdcda3b702d`, re-read only) | — | — | INFEASIBLE → tier 8 (m5g) | 3 / 0 (m5g) | **0** of 143; no relaxed pad in the sidecar | — |

The two builds ran concurrently (correctness runs, not timing-grade).

## 1. Attribution — the premise "hard mode" is REFUTED; the plane is 04t(1)'s

* The red twin is `test_pinned_runways_make_the_apron_yield_not_the_taxiways`
  (a second runway pinned 30 m above the first, lawful reach ≈ 22 m), not
  the hard fixture: `test_apron_between_taxiways_over_relief_is_feasible_hard`
  is GREEN on `3e95e73f` — pad1 (attached, welded into the apron) and pad2
  (detached) both carry ONE `Flat` group (`constraints/pads.py`) and solve
  to one value. On the pinned fixture `rep.mode == "relaxed"`: the last
  resort (04t-1) applies, names pad1's `Flat` (kind `pad`, slope 0.0227 over
  130 m, relief 2.95 m) and re-solves it as ONE PLANE — z(−60,150) 711.335 …
  z(60,200) 712.513, u = 0.00035, v = 0.0227, plane residual 0.000 m, the
  certificate OK. That is the design of m5d §1.3 ("a pad becomes ONE PLANE
  … its contact may slope") and 04x's spawner rulings. Planes exist
  nowhere else: `solve/tiers.py::demote` keeps every `Flat` (and `Band`)
  hard at every depth.
* Why it turned red at the merge (interventional, offline replay in a
  throwaway worktree at `7ddf3f5b`, no builds): there the last resort
  STOOD DOWN — "the IIS (7 rows) names no relaxable row — Band:reach,
  Diff:no_step, Linear:runway_profile, Pin:runway_profile" — and the tier
  machinery answered (`tiered`, k_min 3, 769 demoted, no_step yield 14.0 m),
  pads flat at 711.033 / 702.386. v2integ's `envelope_free` (reach bands
  set aside) + `diagnose(minimal=False)` (Farkas support) let the last
  resort find its candidates, exactly as it was meant to; the twin's flat
  assertion dated from the tiered era and v2integ widened the mode without
  re-founding the pad assertion.
* Suspects in the brief: (a) zone bands vs the Flat — no strip exists in
  the fixture, no `Band`/zone `Linear` on either pad; (c) attached /
  detached classification — pad1 shares its rim with the apron (15 apron
  `Diff` rows + the 04r route pairs on its vertices), attached; (b) the
  plane conversion — inside the relaxation only, never the hard assembly.

## 2. The fix

1. **Twin re-founded** (`tests/auto_patch_v2/test_m5.py`): in relaxed mode
   a pad the IIS named is ONE PLANE (`verify.pads.plane_residual` ≤
   `[relaxation] materiality_m`), every other pad one flat value; in tiered
   mode no pad is relaxed and all are flat. Module docstring states the
   law: "a pad is ONE FLAT VALUE in the hard and the tiered solve always;
   ONLY inside the 04t(1) relaxation may a pad the IIS names be ONE PLANE".
2. **Bands on a detached pad apply to the group's single level, never
   per vertex** (`constraints/zones.py`). Measured first (synthetic
   probe, then the twin): a DETACHED 100 m pad inside the runway's zone 2
   along the 1.5 % lip was hard-INFEASIBLE — IIS = the pad's `Flat` + the
   nearest rim's band [−0.585, −0.3075] at d = 17.5 + a far-rim FLOOR
   relative to its own foot 1.5 m higher (the band is 0.28 m wide; the
   floor at one end sat above the ceiling at the other); the 12 m pad of
   the v2integ twin was feasible only because its lip barely slopes. Now
   only the nearest rim vertex carries the band and no other rim vertex
   carries any zone row (the `Flat` carries the level). This is the
   m5g §6-2 class ("KCLT's hard set is now infeasible under the
   detached-pad band, IIS budget-bound") — not rebuilt here (report only).
   Twins: `test_v2integ.py` (far rim carries no row; the long-pad fixture
   hard-feasible, pad one value).
3. **`pad_flat` verify check** (`verify/pads.py`, registered in
   `verify/census.py` beside the acceptance keys, always present in the
   census dict): every rigid-role shape (`precedence.toml rigid`) with its
   holes — an unrelaxed pad's spread > `[materiality] elevation_m` (0.01)
   is a row (`reading = spread`); a pad in the sidecar `relaxed_rows`
   (kind `pad`, joined by face id) is read as a plane: least-squares
   residual > `[relaxation] materiality_m` is a row (`plane_residual`).
   Not a law family (the v1 == v2 register twin holds). `DEFECT_KEYS =
   ("pad_flat",)`: `pipeline/build.py` logs `verify: DEFECT pad_flat n …`
   and publishes `report.verify.defects`; `auto_patch/engine_v2.py` fails
   the airport BY NAME (stage `verify`, before the patch is placed) — a
   sloped pad no ruling relaxed can never ship silently; `build_airport.py`
   shouts `v2-verify DEFECT …` and records `verify_defects` in the v2
   record. Twins `test_pad_flat.py` (3): the hard fixture reads zero and
   the key is present; a 0.5 m tilt is one row; the relaxed pad (spread
   1.18 m) is no row until its plane is bent.

Twins: `tests/auto_patch_v2` **219 passed** (215 + 4). Driver twins
`test_engine_v2_rebake.py` green; `test_auto_patch_engine_dispatch.py` has
2 reds (`_Res` fixture lacks `rebake_plan`) that are IDENTICAL on the
untouched main tree — not this lane's.

## 3. Not done

* The five-airport sweep (orchestrator's); KCLT and HECA not rebuilt
  (KCLT's stored patch re-read only: 143 pads, all flat, none relaxed —
  the tier-8 row of m5g §3 was not a pad).
* Whether a 2.27 % pad slope is "slightly sloping" (04t-1): an INTENT
  question — the fixture's relief is deliberately unreachable (8 m past
  the lawful reach), the variance program spread it over the no-step
  rows (up to 12 % over 111 m) and the pad; no number bounds a relaxed
  pad's slope in the tables. Reported, not decided (a
  `[relaxation] pad_slope_max` would be one table value if the owner
  wants a bar).
* SPJC's 2 v2-verify `adjacent_ground_tear` rows (strip|strip, 1.2–1.3 m
  over 0.5–0.7 m, way 182; oracle reads 0) predate this lane.
* No build-time impact measured (the reader is 0.45–1.12 s inside the
  verify stage, already counted there; the zones change removes rows).
