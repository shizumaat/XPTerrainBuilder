# auto-patch-v2 — M5i report: the two residual classes (lane v2hecalemd, 2026-09-05)

Lane `lane/v2hecalemd` off main `39298a60` (RULINGS 05d/05e). Two items:
**A** HECA's last resort did not fit the 120 s IIS budget (61/54, tier 3
demoted); **B** LEMD's two contradicting `structures` pins (5/3, 5.99 m
tier-8 yield). Every law value from the TOML tables (two new keys, both
cited below); no env reads; no v1 imports in v2 (the oracle edit is
`tools/check_grade.py`, v1's tool, twinned in `tests/test_harness.py`);
every touched v2 file ≤ 1,000 lines (largest `law/model.py` 936,
`solve/relax.py` 837). Attempt cap: one attempt per item. Synthetic-first:
both items were attributed and fixed on offline captures of the pipeline's
pre-solve product (`pm`, `cs` pickled after `generate`; HECA 19 s, LEMD
80 s to capture; the relaxation replayed in 100 s); the airports built
ONCE each at the close, through the harness, concurrently (correctness
runs — not timing-grade).

## 0. Site first — the closing table (branch `28e455f5`+, tag `…T153536`)

| airport | artifact key | build s | mode | oracle census adj / airside | airside by family | relaxed (04x-2 heading) |
|---|---|---|---|---|---|---|
| HECA | `4856370d74f8` | 124.9 (solve 101.8) | **relaxed-optimal, NO tier demoted**, 1 round | **24 / 17** (05d: 61 / 54) | mid_edge_step 11 + vertex_to_edge 3 cross_connector\|junction at two sites (30.1373,31.4058 / 30.1381,31.4053) = the round-3 near-coincident-rim class (m5c §6.2, m5d "26 rim steps"); cross_shape 3 building\|building slivers (m5d's 3) | 150 rows priced lawful at their relaxed cap; **0 rows at the relaxed site** |
| LEMD | `f4f0491023f4` | 95.8 (solve 6.8) | **hard feasible, no surface yielded** (05d: tier 8, 62 rows soft, 5.99 m) | **2 / 0** (05d: 5 / 3) | — (2 groundside: groundside_pavement steps 0.61 / 0.51 m at one site 40.46226,−3.57288, present in m5g's "two groundside") | — |
| CYXY | `f84bd6ffae29` | 5.0 | hard feasible | **0 / 0** (unchanged) | — | — |

## A. HECA — attribution (interventional, offline) and the fix

* **Where the budget went.** On the HECA capture (1.30 M rows, 23.8 k
  columns) the whole-model certificate LP on the ENVELOPE-FREE set costs
  **107 s** cold (presolve off), **142 s** with presolve on (a ray IS
  returned there — the "reduced model carries no ray" premise of m5d does
  not hold in highspy 1.15.1, but it buys nothing), **207 s** with the
  hard model's own L1 objective. m5d's 22–32 s was measured WITH the reach
  bands; v2integ's `envelope_free` (the right thing for what the ray
  names) made the LP three to seven times harder. The same LP WITH the
  bands, over the columns the rows touch, proves infeasibility in
  **3.0 s** and its support names the site: the band vertices (3337 / 3338
  / 3692 — the 23C→05L site) and the crown row.
* **The mechanism** (`solve/iis.py`, `solve/relax.py`): (1) THE CACHED
  CERTIFICATE — `Certificate`: the with-envelope HiGHS model built once
  (presolve off, used columns only), its ray the seed; a round's relaxed
  rows are FREED IN PLACE (`changeRowsBounds`, the basis kept) and the
  next ray hot-starts (0.1 s measured); (2) THE BOUNDED NEIGHBOURHOOD —
  `RowIndex.neighbourhood` grows the seed by row-hops (an all-pairs face
  row makes a whole ring one hop) along `HOP_SCHEDULE = (1, 2, 3, 4, 6, 8)`
  and `neighbourhood_certificate` solves the envelope-free rows of each
  neighbourhood until one is infeasible — its ray is a Farkas certificate
  of the whole model (a subset's certificate is the model's), nothing is
  approximated; past the schedule the whole-model LP answers under the
  remaining budget (HECA: 8 hops / 193 k rows 14 s, 12 hops / 442 k rows
  68 s and still feasible — the whole model is the cheaper question
  there). HECA: hops 1–3 feasible (0.08 s), **4 hops / 20,162 rows / 0.29 s
  → 4-row certificate** (`Diff:apron`, `Diff:pads`, `Linear:zones` on face
  356); site 6,262 candidates; stage 1 feasible in ONE round (v2integ's
  round-2 LP is not needed: the certificate seeded from the 23C→05L site
  names the apron whose relaxation closes both contradictions).
  `RelaxReport.certificates` records the path per round (kind, hops,
  rows, wall, support).
* **04x-1 QP size gate**: `[relaxation] qp_max_rows = 100000` — above it
  stage 1 goes straight to the PWL (`note` says so); HECA's 20 s QP burn
  is gone (SPJC / OTHH fell to the PWL every build the same way).
* **HECA solve**: hard 11.8 s (unchanged) + IIS **4.3 s** (was 107–120 s+)
  + stage 1 (PWL) 40.4 s + stage 2 55.5 s = **101.8 s**, relaxed-optimal,
  no demotion, certificate OK. Build total 124.9 s under three concurrent
  builds. Prediction "total < 120 s": the SOLVE meets it; the build does
  not (load 3.7 + planar 7.1 + constraints 5.4 + verify/emit ≈ 23 s on
  top). Stage 1 + 2 (96 s) are now the whole cost — the PWL LP and the
  normal L1 solve over 1.3 M rows.
* **The relaxation it chose**: 512 rows (328 apron chords + 178 no-step
  pairs + 4 frontage on face 356, one pad face 1148 as a plane at
  1.28 % / 0.85 m rise over 66 m); excess grade mean 0.11 %, max 2.80 %
  (one 15 m frontage row), relief Σ 28.7 m. Larger than m5d's 117 rows /
  Σ 2.95 m: the 23C→05L drop (53.6 m over a 52.8 m budget, m5g §4) is now
  spread as the ruling asks instead of demoting the apron tier.
* **04x-2 oracle**: `check_grade.py` reads sidecar `relaxed_rows`
  (`SIDECAR_LAW_KEYS`), joins by the emitted node identities, prices a
  relaxed chord at `cap_after × the solve's own distance` (a route pair's
  d is the ROUTE distance — HECA's two apron|junction rows read 0.98 m over
  53.5 m direct / 60.3 m route: lawful at 1.63 %), a pad pair on its plane,
  a frontage within its metre slack, and stamps
  `out_of_scope = "relaxed_by_04t1"` — reported under its own heading in
  `OUT_OF_SCOPE_CLASSES`, never adjudicated; a relaxed row over even its
  relaxed cap stays a violation. HECA: 150 rows under the heading. Twin
  `test_harness.py::test_a_relaxed_row_is_priced_at_its_relaxed_cap_…`.

## B. LEMD — attribution and the fix

* `diagnose(minimal=True)` on the LEMD capture: **2 rows in 2.7 s** — two
  `Pin`s on ONE vertex 23109 (40.48922873, −3.59407179), face 1134 role
  `retaining_wall` ref **`basin_wall:22`**: `tunnel:-5938` "crest = dem
  (09-03b L1)" at **616.99** and `basin:22` (Terminal 4 green,
  `LEMD_OBJ-Airport_Terminal4_green-LEMD02.obj`) "rim = ground: DEM where
  bare (09-03b L1; 04d)" at **611.00**. The vertex is NOT shared by two
  structures: `constraints/structures.py::_faces_of` joined every
  `retaining_wall` face to the nearest tunnel BY ROLE, so the basin's own
  wall band was claimed as tunnel -5938's wall and pinned at the DEM of its
  projection onto the tunnel's wall path (5.99 m higher). The verify reader
  keys `tunnel_wall` / `basin_wall:` exactly; the generator did not.
* **Fix**: the join is by the tunnel's own ref (`WALL_REF = "tunnel_wall"`,
  `RAMP_REF = "tunnel_ramp"`). Offline replay: LEMD hard set **feasible,
  optimal, no yield, 6.9 s**; the build agrees (table). The three
  cross_connector micro-steps of m5g (0.51–0.61 m over 0.05 m) are gone
  with the tier-8 yield — they were its shadow, not the weld's tolerance.
* **The precedence row** (spawner ruling): `precedence.toml [structures]
  datum_order = ["tunnel", "basin"]` — a vertex two structures GENUINELY
  pin keeps the senior structure's pin; `structures.reconcile_datums` is a
  `generate` post-pass beside `seam_exempt` (`counts["structure_datum_
  withdrawn"]`, 0 at LEMD after the join fix). The tunnel is senior: its
  crest is the bore's own geometry; a basin rim is the ground's reading.
  Twins `test_m5i.py` (a `basin_wall:` face with a tunnel wall's exact
  geometry is never the tunnel's; the senior pin survives, the junior is
  withdrawn, a lone basin pin stays; the count key).
* LEMD v2-verify: `tunnel_wall_top_flat` 62 (≤ 1.64 m across 2 m band
  stations) and `tunnel_mouth_canonical` 7 are PRE-EXISTING (64/62/62 in
  every prior LEMD build's report.json; the oracle reads 0 airside) — not
  attributed here.

## 3. Twins

`tests/auto_patch_v2` **231 passed** (225 + 6 in `test_m5i.py`: the join,
the datum precedence, the counts key, the cached certificate freeing rows
in place and hot-starting, the neighbourhood certificate being a true
certificate within its hops, the report's certificate path);
`test_harness.py` + `test_census_cache.py` green with the 04x-2 twin
(chord at / over its relaxed cap, the solve's own distance, a pad plane
at / over its slope, the register and the sidecar key).

## 4. Not done

* The five-airport sweep (orchestrator's). SPJC / OTHH / KCLT not rebuilt
  (the QP gate changes their stage-1 path: PWL at once instead of after a
  20 s QP time-out — the same answer, 20 s sooner; not measured).
* No timing claim: single concurrent builds. The stage 1 + stage 2 cost at
  HECA (96 s) is the next budget item, not this lane's.
* The relaxed pad at HECA slopes **1.28 %** (face 1148) — over the 05e
  spawner default `pad_slope_max` 1 % that is not yet a table value.
* HECA's 17 airside rows are the round-3 rim class (14) and the building
  slivers (3): owned elsewhere, not touched.
* A pre-existing census warning: sidecar key `pad_pavement_no_step_edges`
  is in neither oracle register (emitted by v2, read by no oracle family).

## 5. Open questions (≤ 2)

1. `HOP_SCHEDULE` and the whole-model fallback are module constants in
   `solve/iis.py` (solver mechanics, measured at HECA) — should the
   schedule's last hop live in `[relaxation]` as a table value?
2. Stage 1 (PWL, 40 s) + stage 2 (55 s) now carry HECA's solve: is a
   stage-2 warm start from stage 1's solution (the same rows plus the
   fixed relief) worth a lane, or is 102 s acceptable for the one airport
   in relaxed mode?
