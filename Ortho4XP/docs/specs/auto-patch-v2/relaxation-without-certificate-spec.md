# v2 — the 04t(1) last resort never waits on a certificate (spec, 2026-09-05)

Owner 05s: runways are flat laterally (the transverse maximum is law,
lane `lane/v2rwytransverse` 781d560d) and HECA is solvable. Scout
attribution (RULINGS 2026-09-05u): with the runway edges held, every 1202
taxi route between HECA's runway complexes is feasible at ≤ 1.15 % (23R ↔
23C: 53.6 m of climb against a 66.7 m budget at 1.5 %; 23R ↔ 05R: 75.9 vs
96.9). The hard set is infeasible because of ONE chain through the hangar
apron pav132: apron frontage/body plan chords at 1 % (one of 700 m) and the
rims of 11 FLAT hangar pads (597 m at zero grade) reach the pav98/T
junction with 29.5 m of budget where the taxi route grants 43.4 m. That is
exactly the conflict 04t(1) rules on (RULINGS 2026-09-04t-1: the least-
total-variance combination — slight over-cap apron, slight pad slope,
never a cliff). v2 never applied it: `iis_time_budget_s` (120 s, and 300 s
in the measurement arm) expired before a certificate, and the fallback
(`solve/tiers.py`) DEMOTED the taxi tier (3,037 rows, up to 5 m) — the
one family the owner's law order forbids yielding. Author: session
(Fable). Implementer: lane `v2relaxfull`.

## 1. Law

`emit.toml [relaxation]`:

```toml
scope_without_certificate = "relaxable"   # no certificate inside iis_time_budget_s ⇒ 04t(1) runs over EVERY relaxable row (relaxable_from_role's tier and junior, pads as planes ≤ pad_slope_max) — never the tier ladder for a governed family
tier_ladder_last          = true          # the tier ladder (04i) answers only when the relaxable scope is still infeasible — and then it names the family it demoted as a FAILURE in the report and the app log
```

`iis_time_budget_s` stays 120. No other key changes; the transverse
maximum merges as law with this.

## 2. Mechanism (`solve/relax.py`, `solve/tiers.py`, `solve/api.py`,
`pipeline/build.py`)

1. Order of answers when the hard set is infeasible: (i) IIS-scoped
   04t(1) as today when the certificate arrives in budget; (ii) with no
   certificate, 04t(1) over the FULL relaxable scope: every row owned by
   `relaxable_from_role`'s tier or junior takes a slack (the existing
   `_model` — PWL approximation of the variance since HECA's rows exceed
   `qp_max_rows`), every rigid pad becomes a plane bounded by
   `pad_slope_max` (05f), the objective the same least-total-variance
   program; (iii) only if (ii) is still infeasible, the tier ladder — and
   the demoted family is reported as a named FAILURE (`report.solve.
   demoted`, the `[v2] law tiers` line, the app's per-airport failure)
   because a governed family yielding is not a lawful surface.
2. The relaxed rows keep the `relaxed_rows` sidecar (04x-2 heading) and
   the oracle's relaxed reading; the report states which scope answered
   (`certificate` | `relaxable` | `ladder`).
3. The runway profile is free to BOW below its CIFP line within the
   longitudinal law (it already is; the scout measured v1's 05C/23C at
   −9.27 m mid-runway; the 1202 argument needs ≥ 3.78 m). No change.

## 3. Acceptance (ONE airport = HECA, on a branch that carries
`lane/v2rwytransverse`)

- Twins (`test_relax.py`): an infeasible synthetic with the IIS budget set
  to 0 s → the relaxable scope answers (status `relaxed`, scope
  `relaxable`), the taxi rows untouched, the apron rows carry the slack,
  the pad a plane ≤ 1 %; the same with an unrelaxable conflict (two
  runway pins) → the ladder answers and the report names the failure.
  Repoint the two twins the transverse lane left red
  (`test_routes.py::test_reach_bands_are_the_envelope_of_the_hard_rows`,
  `test_relax.py::test_relaxation_spreads_the_relief_and_forms_no_step`)
  on their measured meaning, or state why they must stay red.
- HECA `build_airport.py HECA --engine v2` ONCE: scope `relaxable`; no
  tier demoted; every runway half ≤ 1.5 % + quantum cross-fall (the
  lane's `rwy_xfall.py` reading, promote it to `tools/` with an INDEX
  entry — second use); relaxed-row count, max slack, the apron pav132's
  worst over-cap in %, the pad slopes; oracle census airside/groundside
  (today 40/7 on the crown-min surface, 1,604/55 on the ladder); v2-
  verify rows; solve + relaxation wall (the ladder cost 783–1,273 s; the
  relaxable LP must come in well under that — quote it).
- CYXY `--base-arm` against a main control: the transverse law changes
  CYXY's 14L/32R halves (measured by the transverse lane: ≤ 2.09 m on
  strips); quote the delta by role again on this branch.
- Build-time statement per CLAUDE.md.

## 4. Out of scope

Re-pricing apron chords over route distance (the scout's option 2): the
owner's apron law is 1 % in all directions (2026-06-18, 08-21b); 04t(1)
is the ruled resolution when it meets relief. The route graph's apron
chords (`routes.py:216-222`) stay.
