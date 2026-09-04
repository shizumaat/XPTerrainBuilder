# auto-patch-v2 — M4c report: the five-airport residual classes and the harness entry

Lane `v2resid` (Fable, owner 2026-09-03h / spawner brief 2026-09-04),
branch `lane/v2resid` off main `eaac452d`. Every v2 file ≤ 1,000 lines
(touched: `constraints/zones.py` 287, `constraints/strips.py` 400,
`verify/within.py` 225); no environment reads in v2; every law value from
the TOML tables (no table changed); nothing in v2 imports v1 (the harness
imports both). Commits in §7, on the branch, not merged.

Build and measure: `venv/bin/python tools/harness/build_airport.py ICAO
--engine v2` then `tools/harness/census.py <tag>.osm` — the standard entry,
now for both engines (§1).

## 0. Site first — the five-airport table (oracle census = `census.py`, adjudicated / airside)

| airport | before (04e, main `eaac452d`) | **after (this lane, ledgered)** | build s (single, ledgered) | v2 verify rows after | artifact-ledger key |
|---|---|---|---|---|---|
| CYXY | 1 / 1 (strip_seam_tear 2.16 m) | **0 / 0 PASS** | 4.5 | 0 | `c23880b3e574` |
| SPLP | 0 / 0 | **0 / 0 PASS** | 7.5 | 3 (within_shape, oracle 0 — §5) | `a4a3758be45b` |
| SPJC | 1 / 0 (plane_gradient groundside sliver) | **0 / 0 PASS** | 12.8 | 0 | `0a79668a0b63` |
| OTHH | 2 / 2 (plane_gradient 1, strip_seam_tear 1) | **0 / 0 PASS** | 28.9 | 0 | `42a253005ec9` |
| LEMD | 14 / 13 (plane_gradient 13, strip_seam_tear 1) | **0 / 0 PASS** | 30.5 | 71 (tunnel_wall_top_flat 63, tunnel_mouth_canonical 8 — M4-owned, unchanged) | `4d96b4d41c41` |

Timing (brief item 3; `build_airport.py --engine v2 --no-ledger
--no-artifact-ledger`, three foreground runs each, nothing else building,
harness `build_seconds` / v2 `wall_s.total`): **CYXY median 4.3 s**
(4.3 / 4.4 / 4.3; v2 4.32 / 4.35 / 4.34: load 1.8, planar 0.35,
constraints 0.6, solve 0.85, emit 0.2, verify 0.4), **SPLP median 7.3 s**
(7.2 / 7.3 / 7.3; v2 7.24 / 7.25 / 7.32: load 3.3, planar 0.67, four seam
passes 0.46 + 0.71 + 0.71 + 0.87). v1 for the same two: 41.5 s / 9.5 s
(M2 / M3a reports).

## 1. The harness entry — `build_airport.py ICAO --engine v2`

Extended, not forked (`tools/harness/build_airport.py::build_patch_v2`,
line 1885; `v2_law_tables_digest`, line 1866; `main` dispatch on
`args.engine`). One path for both engines:

* the same refusals (build cwd, cold DEM/inset frame, drifted cfg frame,
  private corpus, implicit refresh, swallowed guard refusal), the same
  arming composition (`arm_shared_repo_protection` → guard around the
  build → `require_no_swallowed_write_block` → churn report), the same
  sidecar guarantee, the same run-ledger wrap and the same artifact
  ledger store/serve;
* v2 products land in `<tag>.v2/` (`<ICAO>.report.json` carries the IIS
  when infeasible, `<ICAO>.graded.json`, tile pieces); the patch and its
  sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json`, so
  `census.py` is unchanged;
* `frame.json` records `engine`, `law_tables` (`{dir, files, sha256}` —
  sha256 over sorted `src/auto_patch_v2/law/*.toml` name+bytes) and a
  `v2` block (solve status, LP size, stage walls, v2-verify counts, tile
  pieces); `dem_inset_provenance` is the v2 loader's production-frame
  provenance;
* the artifact-ledger variant key carries `engine` and
  `law_tables_sha256` ONLY when the engine is not v1
  (`artifact_ledger.build_variant`), so every v1 key ever stored is a
  hit and a v2 patch is never served for a v1 arm;
* refused by name under `--engine v2`: `--tile`, `--dem`,
  `--geometry-only`, `--solve-capture` (not wired; a silently inert flag
  is the precedent). A solve that is not optimal/feasible refuses to
  report — no patch is written.

Twins (`tests/test_harness.py` §12, 6 tests): the refusals; v1 variant
keys byte-identical with/without the flag and v2 keys distinct per law
digest; the digest names every table and moves with one byte; a stubbed
v2 pipeline through `build_patch_v2` publishes every `build_patch` result
key plus `engine`/`law_tables`, lands the patch under the harness names
and moves (never copies) it; infeasible solve and missing sidecar refuse;
`main` dispatches through one store. INDEX row updated. Ledger keys
recorded in §0 (and `bc5f168c95b6`, the first CYXY run at the pre-reader
tree).

## 2. `strip_seam_tear` — three sites, three mechanisms, all real steps (not reader frames)

Attributed on the planar map + solve in-process (vertex, faces, rows
binding it), then fixed at the generator; the reader
(`_check_strip_seam_tears`, wall-straddle exemption) was NOT the frame in
any of the three — each pair was two governed strip vertices ≤ 4.3 m
apart with a genuine 1.0–2.4 m step.

* **CYXY 2.16 m over 4.27 m** (60.70433,−135.06937): zone-1 lip vertex
  v2762 shared with `groundside_pavement dsf:pol19` sat on the DEM
  (704.89) 4.3 m from the junction lip vertex v2757 (702.73) because
  `zone_bands` skipped every governed-role vertex (`vw.pavement_vertices`)
  — the groundside pavement's boundary was an exemption, the very reading
  RULINGS 2026-08-30 ("taxiway adjacent-ground band cuts groundside: a
  shape boundary is not an exemption") forbids. Fix `zones.py:202`: only a
  vertex an AIRSIDE value face touches, or a ROAD-family vertex (a road
  edge-sharing pavement IS that pavement, memory `free-road-ruling`; its
  1.5 % cap cannot hold the lip's 3 % mandatory-down — measured CYXY, an
  IIS of the two rows on the first cut), keeps its own law; a strip vertex
  shared with any other groundside value face is banded. CYXY v2 verify
  1 → 0, oracle 1 → 0.
* **OTHH 1.03 m over 1.58 m** (25.2596,51.6045 area; v18834 ↔ v18833):
  the pocket rule's ceiling reference JUMPED at the taxi corridor's outer
  edge — v18833 (22 m from a code-F taxiway, inside its corridor) took
  the taxi band (−0.37..−1.10 → 3.59), its neighbour v18834 (23 m, one
  metre outside) had only the runway's band at d = 75 (mandatory-down
  −1.17..−2.31 → 2.56). Fix `zones.py:235-273`: inside a corridor the
  reference is the nearest pavement edge BY TRUE DISTANCE, its band
  clamped to its own half-width (the docstring's own "changes
  continuously with the nearest edge"); a beyond-corridor pavement is
  admitted only as that nearest reference (as a farther candidate its
  floor is void — measured CYXY, an IIS of five rows), and only for a
  vertex some corridor holds (measured LEMD: a vertex 3 m off a runway
  END took a taxiway 19 m away, an IIS against the end chord). OTHH
  2 → 0 (oracle), 0 seam rows.
* **LEMD 2.44 m over 3.0 m** (18R/36L north end centre, v2175 608.66 ↔
  v2796 606.22, DEM 600.8 — the runway end sits 6–8 m above the DEM on
  fill): the end-corridor longitudinal generator binds only CONSECUTIVE
  ring pairs whose step is along the axis; the 3 m lip ring around an
  end has none (its vertices step across), so the lip's outer ring was
  tied to the runway only through 33 m RESA transverse rows and the DEM
  pull took it under. Fix `strips.py:288 _end_foot_rows`: the CHORD form
  of the same 5 % end-skirt law from the runway END EDGE — every strip
  vertex in an end corridor abeam the runway's width is bound to the end
  edge's interpolation over its along-axis distance (wall vertices and
  pavement vertices excluded; a vertex beside the corner keeps the
  transverse rows). LEMD seam 1 → 0; end-corridor rows 51 → 81
  (LEMD), 1 → 4 (CYXY).

Ruling C (09-01c) merge-and-weld was not needed: no two strips had to be
merged; each tear was a missing or discontinuous BAND on one vertex.

## 3. `plane_gradient` — 15 rows, two instrument classes, zero patch bytes

Every one of the 15 (SPJC 1, OTHH 1, LEMD 13) was re-read on the planar
map with the SOLVED and the EMITTED (0.01 m-quantised) vertex values:

* **12 slivers** (heights 0.04–0.5 m — a vertex within the identity
  spacing of the opposite edge; longest edges 6–47 m): solved plane
  0.82–1.50 % (at or under cap), emitted plane 1.24–4.47 %. The 0.01 m
  quantum on a sub-metre height IS the grade. The reader's flat 0.03 m
  noise prices a swing, not a tilt.
* **3 stub triangles on a crowned runway edge** (OTHH `stub pav32`, LEMD
  `stub pav71`, `pav155`): two runway-edge vertices declared 0.30 m
  drops, the stub's own vertex UNDECLARED; the reader defaulted it to the
  ridge (`drops.get(id, 0.0)`) and read 15–28 % where the raw plane is
  0–1.5 % — the pair-check defect `grade_law.crown_pair_offset_interval`
  closed on 2026-08-16, alive in the plane check of BOTH readers.

Decision (brief: "dissolve at planar build and/or price at the emitted
quantum; measure which"): PRICED AT THE QUANTUM, in the readers —
`check_grade.plane_reading` / `plane_fit_noise` (`tools/check_grade.py:882,
912`) and `verify/within.py:177,194`, one arithmetic. The allowance is
`cap·dist + noise + (q/2)·Σ1/hᵢ·dist` (the fitted gradient's error bound
over three vertices each rounded by q/2; a fraction of a mm/m for a
well-shaped triangle) and an undeclared vertex is judged under both ends
of `[0, max declared drop]`. Dissolving slivers at planar build was NOT
attempted: the slivers are snap-rounding artefacts of the 0.5 m grid
(three near-collinear grid points), removing a face from a validated
arrangement re-nodes its neighbours (I1–I7), and the rendered surface
they carry is a ≤ 1 cm ripple.

Instrument A/B on stored v1 controls (old reader = main `eaac452d`, new
reader = this branch; same bytes): CYXY `r1bf_cyxy_final` 157 = 157
(plane 0 = 0); **HECA `r1bf_heca_on` 2,811 → 2,809 (plane 5 → 3, airside
1,069 → 1,068)**. v2: SPJC 1 → 0, OTHH 1 → 0, LEMD 13 → 0. Twins:
`tests/test_check_grade_plane_crown.py` (+4: the three original
properties untouched; sliver at cap passes, sliver at 100 % flags,
Σ1/hᵢ, undeclared-vs-declared) and `tests/auto_patch_v2/test_verify_plane.py`
(+5, the same cases through a hand-built `Patch`). Separate commit (§7).

## 4. What the IIS named on the way (each a mechanism, each fixed)

1. banding road-family vertices to the lip (road 1.5 % vs lip 3 %
   mandatory-down: roads exempt, free-road ruling); 2. a beyond-corridor
   taxiway's FLOOR on a runway zone-2 vertex (floor-only rows come only
   from corridors that hold the vertex); 3. a beyond-corridor reference
   for a vertex no corridor holds (LEMD end, `_end_foot_rows` vs the
   taxi band) — found by bisecting the 934 added rows against the pickled
   pre-change solve (the HiGHS IIS on 2.3 M rows did not return in 11
   min; the bisection took ~2 min). Membership-class lookup: a strip
   face's class key did not match its pavement's on the OTHH site (the
   band came from the family search), so the corridor test is now the
   family search's own — noted, not chased.

## 5. Residuals and DEFERRED_VERIFICATION

* SPLP v2-verify `within_shape` 1 → **3** (cross_connector pav15/pav28,
  2.06–2.14 % over 11–29 m vs 1.5 %); the oracle reads 0 on the same
  patch. A v2-verify/oracle instrument disagreement (M3a's open item, now
  three rows); not attributed here.
* LEMD `tunnel_wall_top_flat` 63 / `tunnel_mouth_canonical` 8 — v2-only
  tunnel readers, M4-owned, unchanged.
* DEFERRED_VERIFICATION: no v1 airport was rebuilt (the instrument
  correction was measured on the two stored v1 controls, not on a fresh
  HECA build; the ~1.1-row HECA move is from the reader alone);
  SPJC/OTHH/LEMD have single-run times only (`--runs 3` on CYXY and SPLP
  per the brief); no mesh bar run; only the directly covering suites ran
  once (`tests/auto_patch_v2` 104 green, `tests/test_harness.py` v2/engine
  selection 23 green, the two plane twins); the full suite was not run.

## 6. Open questions (≤ 3)

1. Pocket rule: the reference now switches at the equidistant line
   between a runway and a nearer taxiway; where the two ceilings differ
   (runway mandatory-down vs taxi band at its clamped half-width) a
   ≤ 0.3 m ridge across one vertex spacing is possible on flat ground —
   below every tear threshold, but is a blend the owner's intent?
2. The plane-fit envelope forgives the emitted quantum on
   identity-spacing slivers in the READER; if the owner wants the mesh
   free of them, the planar build (snap rounding) is the place — a
   separate mechanism.
3. `groundside_pavement` vertices on a zone ring now carry the 3–5 %
   mandatory-down lip (roads stay exempt under the free-road ruling);
   the pavement grades away under its 8 % cap. Owner may prefer the
   cut-back form of 08-30 (the band claims the width geometrically).

## 7. Commits (branch `lane/v2resid`, not merged)

* `51e4a032` — `--engine v2` harness entry (+twins, INDEX); zones.py
  (08-30 band binds groundside pavement; nearest-by-distance reference
  inside a corridor); strips.py `_end_foot_rows`.
* `6bf0cc52` — instrument correction, both plane readers (+twins).
* this report + `docs/DEFERRED_VERIFICATION.md` lines.
