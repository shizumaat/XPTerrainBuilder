# valleyspec — spec §61: the taxiway edge takes its centreline's level (the valley closed, the solve reproducible)

Lane `valleyspec` (Fable, spec author / ruling; NO engine code), 2026-10-09.
Branch `claude/valleyspec` (= `claude/flatvalley` + main `e2eec15c`); spec
`Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` §61; notes
`docs/briefs/valleyspec-notes.md`; probes `docs/briefs/valleyspec-scratch/`;
frames `frames.py list KCLT|HECA` (lane valleyspec, 7 patches).

## The law ruled (§61 (1))

Every taxi-family vertex that is not a centreline vertex and carries no trend row
takes ONE relational row to its own face's chain at the foot of its perpendicular,
`z_v = (1−t)·z_a + t·z_b`, priced at `[design] taxi_xsec` = **1.0** (= `bend_taxi`);
a runway-contact pin enters as the runway's VALUE (`preferred_z`), never a column;
a vertex no chain reaches (past `taxi_trend_face_reach_m`, or on a face no chain
owns) takes the membrane to its mesh neighbours at the same 1.0.  It is §8.6.1's
own statement ("a cross-section is handed one value; its shape stays the
transverse law's") carried to the faces §8.6.1 left out — the SHORT chains, which
are 80 % of KCLT's unnamed columns because a chain is one breakline between
branches and a long parallel is many of them — with the value read from the
SOLVED centreline, so 08t (1) / 10v hold: no DEM enters.  Chosen over the
membrane because the membrane is physics, not law, and reaches through the
strip's DEM ring (the lane's +19 at KCLT); over the taxi trend at 30 because at
that weight the row outranks the sheet (runway 179 vertices / 0.24 m,
`airside_no_step` steps to 2.4 m, `taxi_box` +104).

## The probe table (control / membrane / ruled), one tree one capture

| | KCLT control | KCLT membrane (lane) | **KCLT ruled** | HECA control | HECA membrane (lane, 9baa9e82) | **HECA ruled** |
|---|---|---|---|---|---|---|
| null-change movers 1a / 1b (bar ≤ 20, 0 > 0.3) | 506 / 615 (31 > 0.3, 0.81) | 0 / 0 | **0 / 0** (worst 0.0003 / 0.019) | 157 / 535 (42 > 0.3) | 0 / 0 | **0 / 1,813** (0 > 0.3, worst 0.195) — the §5a LP's degenerate pad-row choice, not the valley (ATTRIBUTED: the twin with the arm's relaxation set FORCED reads 4 / 0 / 0.14 — 1,813 → 4) |
| one-time cost: stage-1 movers / > 0.3 / worst | — | 1,149 airside / 245 / 1.62 | 1,827 / 384 / 1.49 | — | 968 / 209 / 1.01 | 3,739 / 367 / 0.98 |
| avd: runway | — | 0 | **4 / 0.06** | — | 0 | **2 / 0.06** |
| avd: strip / taxi / apron | — | 998 / 73 / 78 | 2,683 / 290 / 178 | — | 621 / 340 / 7 | 2,869 / 1,246 / 848 |
| adjudicated airside | 3,355 | 3,374 (+19) | **3,336 (−19)** | 12,201 (12,196 at 9baa9e82) | 12,168 (−28) | **12,170 (−31)** |
| taxi-tier `hard_conflict` | 51 | 51 | 51 | 62 / 61 | = | 62 / 61 (census 240 → 237) |
| CRITICAL | — | = | `groundside_cutback` visual 3 → 2 | — | = | `strip_seam_tear` visual +1; `vertex_to_edge_step` motion 0 → 1 (unshared apron|junction seam, 30.10901, 31.40396) |
| stage-1 wall | 13.3 + 22.7 s | 13.9 + 32.1 | 17.8 + 33.1 | 84.7 + 83.9 | +18 | 73.3 + 117.0 (+22 s) |

## The exit (§61 (4))

Tolerance exit on objective gain stays; `_REL_TOL` becomes the law number
`[design] qp_rel_tol` = 1e-12.  Capped outer loops (`LAG NOT SETTLED`, `HARD SET
NOT SETTLED`, QP `round_cap`) stay NAMED LINES in the log and the sidecar
(`qp_exits`, `lag_settled`, `hard_settled` added), never a build failure.

## The §5a LP and `promote_missed` (§61 (5))

PART OF THIS CHANGE: a tie-break among the LP's EQUAL optima — a second LP at the
held optimum minimising Σ rank(row)·s in canonical lat/lon order (ε-perturbation
as the one-LP fallback).  Not 07b's refuted order: tiers, weights and the
optimum are untouched; only the choice among equal answers becomes a function of
the geometry.  `promote_missed`'s threshold stands; its HECA flip (2 rows) is the
LP flip's consequence at the same site.

## Acceptance and the standing check (§61 (6))

Runway ≤ 0.1 m (09b); taxi tier ± 3; adjudicated airside by family not rising;
CRITICAL not rising; and the STABILITY BAR as a harness check:
`tools/v2_solve_replay.py --null-change [N]` (extends `--probe-site`'s Band
injection and `--stage1-diff`), one line `NULL-CHANGE pass1a a/b/c pass1b a/b/c
stage2 a/b/c`, `--json` key `null_change`; bar ≤ 20 at 0.02 m, 0 over 0.3 m.

## Sub-steps (§61 (8)) — 8 steps ≈ 8 h, 3 replays + 1 HECA build

1 the foot in `constraints/taxi_trend` (`taxi_xsec_feet`, `PlanarMap.taxi_xsec`);
2 law keys `taxi_xsec`, `free_membrane`, `qp_rel_tol`; 3 the rows in
`design_assemble` + the stub-fixture twin; 4 KCLT replay (expect the ruled row);
5 `--null-change`; 6 the §5a tie-break + HECA replay + the one seam read;
7 sidecar keys + DEFERRED_VERIFICATION line; 8 the HECA closing build.

## Owner questions (§61 (9))

Q1 Every airport's taxiway edges re-level once to their centreline's profile
(KCLT 1,827 vertices worst 1.49 m, HECA 3,739 worst 0.98 m; runway ≤ 0.06 m;
census not rising) so that builds become reproducible — accept?  Recommend YES.
Q2 A capped outer loop stays a surfaced line, not a build failure — accept?
Recommend YES.

## Not settled here

- The HECA `vertex_to_edge_step` CRITICAL motion row (0.52 m over 0.98 m at
  30.10901, 31.40396): a topology seam the valley masked; one planar read owed.
- The control's HECA null-change was not re-twinned on this tree (the lane's
  9baa9e82 numbers stand); the `taxi_xsec` weight was measured at KCLT only
  (30 / 3 / 1), HECA at the ruled 1.0 only.
- A route-level (whole-letter) taxi trend across chain pieces: reported, not
  designed.
