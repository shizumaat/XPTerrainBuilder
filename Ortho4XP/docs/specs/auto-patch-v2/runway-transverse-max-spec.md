# v2 — the runway TRANSVERSE MAXIMUM is hard law (spec, 2026-09-04)

Owner: HECA on 1.0.285 "has some serious violations, starting with the
05C/23C runway" (RULINGS 2026-09-05o). Author: session (Fable).
Implementer: lane `v2rwytransverse`.

## 1. Measured (app patch 21:18 = harness HECA_20260904T214259, identical)

Runway 05C/23C is two crown halves (faces 14 and 30, 346 shared ridge
vertices, each half 31 m wide). The ridge and half 30's outer edge track
the profile (0.58 % per 200 m). Half 14's OUTER edge falls to **93.4 m
under a ridge at 111–116 m: 18 m across 31 m, a 58 % cross-fall**, a
cliff the length of the runway. That edge is shared with the parallel
taxiway pav112 (28 vertices) and stubs pav91/93/79 (37/26/31): their
taxi-family rows and the DEM fit (HECA's real 85 m relief) hold the edge
at the terrain, and the runway's only cross-slope row — `runway_crown`,
a soft `crown:<v>` preference at weight 1e2 — escalates (the solve log
lists `crown:3557 0.056, crown:3558 0.086, …`). Pre-existing in every
HECA v2 build (10:32 → 21:42 today); neither instrument reports it: v2
`verify/runway.py::runway_crown` checks the MINIMUM drop only, and the
oracle judges crown pairs under the sidecar's declared drops.

The law table already states the rule and nothing reads it:
`rulesets.toml [icao.runway] transverse_max = { by_letter = { A/B 0.020,
C–F 0.015 }, default 0.015 }` (§3.1.18); FAA likewise. Appendix A lists
it as a runway law; no generator in `constraints/` prices it.

## 2. Law

No new key. `transverse_max` is read through `role_cap` / a
`runway_transverse_max(law, code_letter)` accessor in `law/tables.py`
(twin in `test_law_tables.py`: the accessor returns the table's letter
value). The crown MINIMUM stays a preference (M3a; a seam DEM pin may
hold an edge higher than the floor).

## 3. Mechanism

`constraints/runway_profile.py::runway_transverse` (new generator,
family `runway_transverse`, registered in `GENERATORS` beside
`runway_crown`): for every off-ridge runway-family ring vertex `v` with
foot `(a, b, t)` at lateral distance `d` on its own ridge chain — the
same `_foot` the crown uses — one HARD `Linear` row

    (1 − t)·z_a + t·z_b − z_v  ≤  transverse_max × d        (no fall steeper than the cap)
    z_v − ((1 − t)·z_a + t·z_b) ≤  transverse_max × d        (no RISE above the ridge steeper than the cap either)

in the runway family's tier (tier 0, never demoted; `precedence.toml`
authority order puts the runway first). Where the edge vertex is shared
with a taxi-family face the taxiway conforms: its own longitudinal law
then carries the 18 m out into its body at ≤ 1.5 % (owner 03k/04i:
pavement overrides terrain, terrain never blocks). Expect the hard set
to stay INFEASIBLE at HECA for the same pad reasons as today and the
04t(1) relaxation to price the rest — report what the IIS names.

`verify/runway.py::runway_crown` gains the maximum: a built drop
`z_foot − z_v > transverse_max × d + quantum` (or a rise above the ridge
by more than that) is a DEFECT row (`reading = "transverse_max"`), so
the instrument sees what the sim sees. Register the family in
`verify/census.py` and the sidecar evidence exactly as the other verify
families are.

## 4. Acceptance (ONE representative airport = HECA)

- Twins: a synthetic runway whose outer edge is pulled 10 m down by a
  hard pin on a shared taxiway vertex → with the generator the solve
  either holds the edge within `transverse_max × d` (the taxiway yields)
  or the IIS names the pin; the verify reading flags the 10 m drop
  without the generator; the FAA/ICAO letter values.
- HECA `build_airport.py HECA --engine v2` once: for each of the six
  runway halves, the max built cross-fall `max(z_foot − z_v)/d` ≤ the
  cap (quote all six; today's half 14 reads 58 %); the half-14 outer
  edge quoted at three stations (−764, 36, 536 m of the 100 m station
  table) before/after; oracle census airside/groundside vs today's
  40/7; v2-verify rows; relaxation count vs today's 506; solve wall vs
  101.6 s.
- CYXY `--base-arm`: the transverse law is already satisfied there
  (expected byte-identical; if not, quote the delta by role).
- Build-time statement (≈ 2 × 974 rows, negligible).
