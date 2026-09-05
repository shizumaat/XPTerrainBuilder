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

## 5. Amendment 2026-09-05 (lane v2relaxfull STOP → RULINGS 2026-09-05v)

The full relaxable scope is STILL infeasible at HECA; the certificate with
every relaxable row dropped names 65 rows: runway 05C/23C's 16 transverse
+ 1 profile, 30 `no_step` pairs, 4 taxi rows (pav112/pav91) and **15
reach bands** — no pin, no apron, no pad. The reach bands and the no_step
route distances are computed over `constraints/routes.py`'s graph, which
puts every APRON PLAN CHORD (`routes.py` apron branch, `_face_pairs`, cap
1 %) into the route metric. A path that cuts across pav132 on a 700 m
chord grants 7 m where the taxi route around it grants 43 m, so the band
at the pav98/T junction is far below what the taxi law allows, and the
bands are HARD and never relaxed — relaxing the apron rows cannot free
them. §4 above ("the route graph's apron chords stay") is WITHDRAWN.

Law (04o, route-true): the ROUTE GRAPH for reach and no_step = the
movement-surface route network — runway-family and taxi-family ring
edges, taxi centrelines and per-stretch chords at their stretch caps, and
the 1202 taxilane centrelines that CROSS an apron (at the apron cap),
plus apron ring edges (its perimeter) — and NO apron plan chord. Apron
chords remain the apron law's own hard-but-relaxable rows
(`apron_within_shape`), never a route.

Mechanism: `routes.py` apron branch replaced by the apron's crossing
1202 centreline chains (the classification already names the taxi
chains touching each cell); a twin asserts the graph carries no
`CHORD` edge whose both endpoints lie on an apron face; `reach_bands`
and `no_step` unchanged in form. Acceptance as §3 (HECA once; expect
scope `relaxable` or `certificate`, no demotion, relaxed rows on
pav132's apron chords and the hangar pads, taxi rows untouched, census
under 40/7 airside is the bar to quote against).

## 6. Amendment 2026-09-05 — owner ruling 05x (a): junction = bounded route territory

HECA's hangar apron pav132 (335,171 m², apron-named, 19 crossing taxi
chains, 21 % of it within 25 m of a route) is cut by the route-proximity
rule into a 214,262 m² JUNCTION cell (three faces 1.2–1.3 km across); its
junction-mesh and taxi rows are tier-0 hard and the certificate (308
rows) is made of them. RULED (a): on an apron-derived cell the junction
role is the BOUNDED ROUTE TERRITORY — the union of (i) each crossing
centreline's corridor of half-width `[junction] route_territory_half_
width_m` (25 m) and (ii) the tight areas at centreline intersections
(the existing `max_area_m2` tight-junction test on the intersection
neighbourhood) — and every remaining part of the face is APRON under the
apron law. The proximity contour (`prox`, user 2026-07-06) is
intersected with that territory before the cut; parts under
`cells.min_area_m2` follow the existing rule. Corridor cells (`kind ==
"corridor"`, width ≤ `corridor.max_width_m`) and tight junctions
(`area ≤ max_area_m2`) are unchanged.

Twins: a synthetic 600 × 400 m apron crossed by two centrelines → two
50 m corridors + one intersection junction + apron remainder, the
remainder's role `apron`; the `explain` evidence records `territory_
frac` and the apron remainder area. Acceptance: HECA once (scope
`certificate` or `relaxable`, no demotion, all six runway halves ≤ 1.5 %
+ quantum, relaxed rows on pav132's apron remainder and the hangar pads,
census vs 40/7, v2-verify, solve wall); the classification change touches
every airport — `--base-arm` deltas by role at CYXY, SPJC and OTHH (their
crossed aprons: state which cells changed role and the census before →
after; 0/0 must hold).

## 7. Amendment 2026-09-05 — the runway family is part of the route network (RULINGS 2026-09-05y)

The nine-row HECA certificate after §6: two reach bands on each edge of
runway 05C/23C at stubs pav91/pav101, 60 m apart and tied within ±0.455 m
by the transverse law, but 3,206 m vs 6,417 m from the 23R pin in the
route graph — the graph has no route ACROSS or ALONG the runway body
(`classify` cuts the taxi centreline parts inside `runway_union`; the
runway faces contribute no edges). RULED: `constraints/routes.py` adds
the runway family to the graph — (i) every runway-family face's ring
edges at the runway's longitudinal cap (`rulesets.<auth>.runway.
longitudinal` by code), both crown halves, so the two edges and the
thresholds are joined along the length; (ii) the crossing 1202 taxi
centreline parts across the runway at the runway cap (recover them from
the taxi network before the runway cut, or as the straight crossing
between the two edge intersections); (iii) the width between the two
edges at the runway `transverse_max` (a CROSSING kind edge). The reach
band then IS the envelope of the runway profile + transverse law + the
taxi routes. Twins: a synthetic parallel-taxiway/stub/runway fixture
whose two runway edges get reach bands that overlap by at least the
transverse allowance; `reach` from a pin along the runway ring equals
pin ± cap·distance. Acceptance as §3/§6 (HECA once, the three base arms).
