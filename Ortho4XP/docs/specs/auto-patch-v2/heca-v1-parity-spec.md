# v2 — HECA parity with v1: the priority model (spec, 2026-09-08)

Owner (RULINGS 2026-09-08a): v2 "much worse almost everywhere" than v1
at HECA; determine the changes. Measured by scout `hecav1v2` (RULINGS
08d, one tree, one frame). Author: session (Fable). Implementer: lane
`v2chord`. The owner may veto 08d-1 before the merge.

## 1. Change 1 — the runway fits the THRESHOLD CHORD, not the DEM

Today: `pipeline/build.py:40` DEM-fit 20/m on runway vertices;
`rulesets.toml:39 runway_profile_smoothness 5000` straightens between
holds. v1: `runway_redistribute.py` anchors a CIFP-chord parabolic
envelope and fills (05R/23L +4.70 m, bow −4.25 vs v2 −9.61 at the DEM).
Change: a per-vertex CHORD target for every runway ridge vertex — the
straight line between the two CIFP threshold pins (`runway_profile`'s
pins) at the vertex's station — and the runway family's fit term
becomes |z − chord| (weight `common.runway_chord_fit`, senior to the DEM
fit, junior to the K/max-grade/transverse HARD rows and to the
smoothness preference). The DEM fit stays for every other role. Keys in
`rulesets.toml [common]`; law python limits as always. Expected: 05R/23L
bow −9.6 → ≈ −4 (fill); 05C/23C descends steadily from 05C; the
05L/23R hump falls with change 2. Twin: a two-pin ridge over a valley
DEM sits on the chord.

## 2. Change 2 — surface families beyond the route graph YIELD (04i as tiers)

Today every surface family is hard (`law_tiers.mode hard`); 07a and 08d
measured them as redundant 1.5 % shortcuts that drag (05C/23C) or lift
(05L/23R +7.5 m) the runway. v1: per-edge caps that yield (junction max
9.1 %). Change: `junction_mesh`, `taxi_box`, `no_step_pairs` (§1.1),
`apron_within_shape` chords/edge portions and `roads` profiles are
minted as PREFERENCE rows (`Diff.soft`, escalation group per family per
face, `ceiling` = a per-family max: `taxi_yield_max` 3 % / `apron_yield_max`
3 % / roads their own core clamp — state keys) charged JUNIOR to the
chord term and senior to the DEM fit; the runway-connected route
graph's chain rows (05ac: centreline + lateral hops + crossings), the
reach bands, the K rows and the runway transverse law stay HARD. The
04t(1) last resort stays for what is still infeasible. Expected: the
05L/23R hump +7.61 → ≤ +1.59 (the measured drop arm), the SW strips
follow the runway fill (strip tie 06e), the census reads yielded rows
as v1's does — the `apron_over_preference`-style report figure per
family (`yielded_rows`, max grade) in sidecar/report/census.

## 3. Change 3 — a joint carries ≤ 2 m, hard; else the cell grades through

`emit.toml [terrace] max_step_m = 2.0` becomes LAW (v1
`APRON_TERRACE_MAX_STEP_M`): in `pipeline/territory.py apply_joints`, a
label boundary whose predicted step (the contacts' ceiling difference
less what the in-shape path can hold at the apron cap) exceeds 2 m is
NOT a joint — its rows stay (as change-2 preferences, so the cell grades
through at the apron cap toward its contacts and yields where it must);
a joint under 2 m stays declared. Same rule for 06n's between-cell
joints. Expected: HECA joints 62/63/64/71/72/0/27/31 (5.9–9.45 m)
disappear, pav132 and pav131 become continuous surfaces (v1's −3.6 mean
cut); CYXY 3 / OTHH 15 joints (≤ 0.39 m) unchanged.

## 4. Change 4 — the owner's site: the apron edge RAMPS to the groundside

At 30.1139552, 31.4095465 (pav131 face 215 vs the 3-node sliver face
269 of the same pavement, joint 27 = 6.20 m) — with change 3 the joint
cannot exist; the sliver face is a classification artefact: merge a
same-pavement face under `emit.identity.min_distinct_spacing_m` × k
area into its neighbour (state k). Where the apron meets GROUNDSIDE
(v1's 3 m step the owner disliked): the apron edge ramps to the
groundside ring at the groundside cap (`GROUNDSIDE_MAX_GRADE` 5 %, v1
`config.py:1519` — v2 key in `zones.toml` or `common`), a preference
under change 2. Twin: an apron 3 m above groundside 60 m away → a 5 %
ramp, no step.

## 5. Acceptance (ONE airport = HECA; then CYXY/SPJC/OTHH/LEMD `--base-arm`)

Synthetic-first on the HECA capture (the 60 s solve-arm pattern,
`docs/specs/auto-patch-v2/heca-sag-ablation/`): quote 05R/23L, 05C/23C,
05L/23R bows and z−DEM (mean/min/max) after each change. ONE build
`build_airport.py HECA --engine v2`: the three runway profiles vs v1's
(scout table §5: bows −9.53 / −4.25 / −0.28, z−DEM), z_v2 − z_v1 by role
vs today's (mean −0.43, p10 −4.08, p90 +2.49, > 1 m 57 %) — the bar is
the SAME-FRAME divergence halving (|dz| > 1 m ≤ 30 %, > 6 m ≤ 200), the
owner's site (no step > 2 m within 60 m), joints (none > 2 m), the
`yielded_rows` figure per family and the census under both readings
(law-true violations as v1's, and yielded-as-lawful), solve wall.
CYXY/SPJC/OTHH/LEMD verify unchanged (0/0/0/16). Build-time statement.
The scout's scripts (`scratchpad/hecav1v2/cmp2.py`, `rwy.py`) are the
comparison instrument — promote them to `tools/` with an INDEX entry
(second use).
