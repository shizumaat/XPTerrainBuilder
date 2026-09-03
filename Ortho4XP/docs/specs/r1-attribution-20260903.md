# R1.1 — attribution of the HECA control's airside residuals (2026-09-03)

Lane `r1attrib`, zero-airside plan R1 step 1 (`zero-airside-plan-20260903.md`
§3 R1.1).  ATTRIBUTION ONLY — no mechanism changed; every edit on this
branch is instrumentation (`O4_AIRSIDE_CERT_DUMP`, `who_wrote --vertex-dump`)
or this document.

## Pre-registered predictions (written BEFORE the instrumented build)

Baseline read from the STANDING CONTROL's own sidecar (artifact ledger
entry `air7_HECA_arm`, tree `13902ca6`, body `e916085b677a`, served with
`artifact_ledger.serve` — no build): `airside_certificate.readings`.

| reading | n_edges_scoped | n_over | mixed | both-hard | worst m |
|---|---|---|---|---|---|
| solve_exit | 718,567 | 3,054 | 2,181 | 0 | 4.58 |
| final1_entry | 249,767 | 3,291 | 1,731 | 3 | 8.02 |
| final1_exit (verdict) | 253,108 | **2,167** | 1,184 | 3 | 7.00 |

final1_exit by family group (sum 2,167): service_junction 1,061
(`service_junction:-` 740, `unified:service_junction` 295, `:spine` 21,
`:service` 5; both-hard 3), apron 690 (351 + 321 + `:spine` 18),
transverse 148, junction 133 (47 + 45 + `junction:transverse_no_step`
36 + `:spine` 5), service_road 123 (102 + 19 + 2), rod_interval 10,
unified_graph 2.

Predictions, by family, of what an R1.2 feasibility drive (S1 law-join +
S2 clamp yield + the solve driving its own membrane / no-step law to
certification) closes:

| P | family (count) | predicted last writer of the endpoints | predicted disposition | predicted count closed by R1.2 |
|---|---|---|---|---|
| P1 | service_junction + service_road, the MIXED rows (1,184 of 2,167) | one endpoint airside (solve writeback / FGP), the other a groundside service node last written by `seat_service_pavement_on_law` / `seat_groundside_on_law` (pipeline 7012/7047) or an FGP hold | the 01r groundside-service-pin class; hold-release-only (S1 `_solve_law_hold_filter`) closes the rows whose hard endpoint is a `svc_free_end` / `svc_profile` pin; the rest is R6 (cap-consistent-at-mint) — NOT airside solve work | ≈ 450 close (hold release), ≈ 730 remain |
| P2 | apron 690 | ≥ 70 % of rows have an endpoint whose last change is FGP's writeback (`solve.py:10859`) with a move ≥ 0.1 m (01p: 71–94 %); the solve-exit apron residue (512 rows, worst 0.39 m) is the undriven membrane / no-step law (01n) | closes: the 512 under the solve-side drive (membrane join certifying), the FGP-added ≈ 180 under S1 + S2 | ≈ 650 of 690 |
| P3 | transverse 148 + `junction:transverse_no_step` 36 = 184 | FGP-only families (ABSENT at solve_exit); endpoints last written by the solve writeback | closes under S1 (the solve's no-step pairs replace FGP's own transect / no-step mint; fgp1 measured the transverse both-hard class 300 → 0) | ≥ 160 of 184 |
| P4 | junction 97 (47 + 45 + 5) | solve exit carried 181 and FGP closed 84; the rest sit on runway-adjacent nodes | ≥ 50 % have a hard endpoint pinned `runway_node` / `pad` → senior-protected (R5); the rest closes under the drive | ≈ 45 of 97 |
| P5 | rod_interval 10 + unified_graph 2 | — | sub-0.15 m; quant-floor noise or S2 | 12 |
| **total** | 2,167 | | | **≈ 1,320 close / ≈ 850 remain** (≈ 730 service pins, ≈ 50 senior, rest mixed) |

The 827-class (control `who_wrote --author final_grade_projection`
untouched moves; 896 on the ON configuration, fgpall ledger: building 537
p50 0.63, apron 140, service_road 137, service_junction 72, junction 10):

| P | subset | predicted last writer before FGP | predicted disposition |
|---|---|---|---|
| P6a | building (≈ 60 %) | solve writeback (`solve.py:6246`) carrying the pad seat | `no_step apron\|building` partner drag — OD-2 (split-level un-hold) territory; NOT closable by a feasibility drive on the current law |
| P6b | apron + junction (≈ 20 %) | solve writeback | closes under S2 (clamp yields) + the drive |
| P6c | service_road + service_junction (≈ 20 %) | `seat_*_on_law` or solve writeback | R6 pin class |

Falsifiers: (i) if < 50 % of apron rows have an FGP-moved endpoint, 01p's
re-authoring mechanism does not own the apron residue; (ii) if the
transverse / transverse_no_step rows DO appear at solve_exit under their
own family, P3's "FGP-only" premise is wrong; (iii) if the mixed rows'
groundside endpoints are NOT hard-pinned (pins null), P1's pin class is
not the mechanism and hold release cannot be the arm.

## Second build (justified in one line)

The 896-class exists only under the ON configuration (`O4_FGP_SOLVE_LAW`
+ `_MEMBRANE` + `_CLAMP` + `_CARRIERS`), which is the configuration R1.3
flips; the charter names that population explicitly, so ONE more HECA
build, same instruments, that configuration.  No sweep, no third arm.

(Measured results follow below once the builds land.)
