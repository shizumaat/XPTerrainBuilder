# S8 — the two validator gaps, and what they make visible

Lane `lane/s8valid`. Every number from `tools/harness/census.py --no-cache`
over the FROZEN 1.0.245 artifacts (`baselines/1.0.245/*.osm.gz` gunzipped
beside their sidecars), in the S7 **`retired`** frame — the control run at
this lane's base (8d08b41) reproduces `tmp/s7_domain_frame.md` exactly
(CYXY 245, HECA 7416, KCLT 2050, KSTJ 390, OTHH 5906).

Neither reader moves geometry. Every row below is a **newly-visible
pre-existing condition**, not a regression.

## 1. Premise verdicts (author-verified before any wiring)

**Item 1 — the constraint is LIVE in production, not dormant.**
`config.SVC_SPINE_FIRST` defaults ON (`O4_SVC_SPINE_FIRST`, config.py:4348);
under it `service_road` joins `grade_graph.SOFT_VISIBILITY_ROLES`
(grade_graph.py:89) and its body pairs resolve through the same
`classify_pair`/`_bake_edge` path as `service_junction` — body cap
`SERVICE_ROAD_MAX_GRADE` along the route, `SERVICE_ROAD_MAX_TRANSVERSE`
across it. `insert_service_lateral_nodes` (lateral_spine_nodes.py:1039)
plants the aligned cross-section vertices that make that cap bite at
station spacing. The validator read NONE of it: `_TRANSVERSE_ROLES` gathered
`{junction, service_junction, apron}`, and the service-axis filter went
through `_GROUNDSIDE_ROLES`, whose intersection with that set is
`{service_junction}`. So `service_road` cross-sections were priced by
nobody.

**Item 2 — the crown's law source is PER-NODE DECLARED DATA, and the
declaration is authoritative.** The rate is the ruleset's
(`grade_law.runway_crown_rate`), but two lawful mechanisms REDUCE a node's
drop below `rate × half_width`: rail continuity (`crown._rail_continuous_drops`
— "the crown may not spend budget the profile already needs") and the
tile-seam taper. The resolved per-node value is exported as the sidecar's
`crown_drops`, the same field the solver built to and the within-shape law
already re-centres on. Measured on the battery: HECA 89 and KCLT 17 runway
nodes carry NO declaration at all — lawful relaxations. A reader that
re-derived `rate × offset` would report the law's own relaxations as
defects. **No STOP: the two authorities compose, they do not conflict.**

How the crown is emitted, which is what makes it readable: the runway RING
carries `z' − drop` and the ridge is a separate `o4_feature=crown_spine`
breakline at `z'`. `crown_centerline` is EMPTY on all five patches — the ring
holds no ridge vertex — so the realised crown is the fall from the breakline
to the ring node, and nothing but this reader looks at that pair.

## 2. The five-airport delta

| airport | ruleset | S7 `retired` | **S8** | `transverse` +service_road | `runway_crown` | airside | adjudicated |
|---|---|---:|---:|---:|---:|---:|---:|
| CYXY | icao | 245 | **317** | 169 → 231 (**+62**) | **10** | 67 → **77** | 245 → **307** |
| HECA | icao | 7416 | **8038** | 3289 → 3911 (**+622**) | **0** | 1720 (=) | 7416 → **8038** |
| KCLT | faa | 2050 | **2164** | 508 → 622 (**+114**) | **0** | 1074 (=) | 1080 → **1194** |
| KSTJ | faa | 390 | **401** | 26 → 37 (**+11**) | **0** | 377 (=) | 54 → **65** |
| OTHH | icao | 5906 | **5933** | 85 → 112 (**+27**) | **0** | 5670 (=) | 5906 → **5933** |

**Every transverse row added is `transverse::service_road|service_road`**
(+836 battery-wide). Verified row by row against the role join, and the
PRE-EXISTING population is preserved exactly — the other three role pairs
sum to the old family total at all five airports (CYXY 107 + 52 + 10 = 169;
HECA 3196 + 72 + 21 = 3289; KCLT 468 + 36 + 4 = 508; KSTJ 15 + 11 = 26;
OTHH 85). So a taxi axis still prices no service road, and no apron or
junction row moved. All 836 new rows are GROUNDSIDE: **AIRSIDE is invariant
at all five airports.**

**`runway_crown` reads ZERO at four of five.** Four airports realise their
declared crown to within 1.5 cm (OTHH exactly: ring 3.66, ridge 3.96,
declared 0.30). CYXY's 10 rows are the whole battery's crown population.

## 3. The AIRSIDE rows, for the round's docket

CYXY `runway_crown` = 10 rows, all AIRSIDE, worst |Δ| 0.073 m realised
against 0.114 m declared. **All ten sit at runway INTERSECTIONS** (8 on
`runway_crossing` shapes, 2 on `runway` nodes welded to one), and all ten
carry the cited exception — ICAO Annex 14 §3.1.19, "nor be less than 1 per
cent EXCEPT AT RUNWAY OR TAXIWAY INTERSECTIONS"; FAA Table 3-6 S-1 the same
— so they are stamped `out_of_scope="runway_intersection"`, counted in the
family and skipped by the acceptance verdict. **CYXY's ADJUDICATED total is
unchanged by item 2** (245 → 307 is item 1 alone).

Reported anyway, because the exception removes the LAW and not the fact: at
CYXY's 02/20 × 14R/32L crossing a declared 0.114 m crown is realised at
0.005 m. Nothing requires it there; the round may still want to look.

## 4. What the readers are

* `check_grade._TRANSVERSE_TAXI_ROLES` / `_TRANSVERSE_SERVICE_ROLES` are
  IMPORTED from `lateral_spine_nodes.TAXI_AXIS_PRICED_ROLES` /
  `SERVICE_AXIS_PRICED_ROLES` — one list, two readers. The service pass
  now SELECTS its targets through the same set it is priced by, which is
  what makes the lockstep comment true again. The cap needed no change: it
  already resolves through `config.transverse_cap_for_longitudinal_cap`,
  the one source `grade_graph._bake_edge` binds with.
* `check_grade._check_runway_crown` pairs each declared runway node with
  the nearest point on a `crown_spine` breakline (elevation interpolated
  along it) and reports `declared − realised − quantisation` as a
  shortfall. A shape with NO declaration anywhere is judged against
  `grade_law.transverse_minimum_for_role`, and only where
  `transverse_minimum_binds("runway")` — counted and printed as its own
  condition, never a silent zero. No ridge in the patch at all ⇒ rows for
  the whole declared drop.

## 5. Byte identity — the diff moves no bytes

The diff touches one emitter file (`lateral_spine_nodes`: a public alias,
one selector expression, and a set widened where the taxi pass's targets
cannot intersect it), so it was MEASURED, not argued. Capture-armed
`build_airport.py` arms in this lane:

| airport | frozen 1.0.245 | this lane | shapes | shared repo |
|---|---|---|---:|---|
| CYXY | `61efa43c3aeb` | **`61efa43c3aeb`** | 462 | UNCHANGED |
| HECA | `f562cbfeb8f9` | **`f562cbfeb8f9`** | 3887 | UNCHANGED |

And the S7 DEFERRED line "nothing verifies that a FRESHLY BUILT patch
censuses the same way" is paid for this change: the freshly built HECA
patch censuses **8038 / transverse 3911 / runway_crown 0 / airside 1720**,
identical to the frozen artifact under the same readers.

## 6. Twins

* `tests/test_lateral_cross_section.py` — the scope IS the lateral pass's
  own target roles (both sets, both directions); an over-cap service-road
  cross-section IS censused at `SERVICE_ROAD_MAX_TRANSVERSE`; a compliant
  one is not; a TAXI axis still prices no service road.
* `tests/test_crown_minimum_bound.py` — the file that held the
  generation-binding half now holds the validator half: flat runway vs a
  declared 0.30 m crown → rows; properly crowned runway → zero; one cm of
  emit grid → zero; an intersection row → measured but out of scope; an
  undeclared runway → judged at the ruleset floor; no ridge → the whole
  crown; a LAW-RELAXED 0.05 m drop realised exactly → zero.
* `tests/conftest.py::write_synthetic_patch` — one writer for the emitted
  patch + sidecar pair both twins need (a per-file copy is the
  census-wrapper defect at fixture scale).
* `tests/test_census_instrument.py` — S7's tripwire asserting the crown
  family did NOT exist is flipped to assert it does, per its own
  instruction.
