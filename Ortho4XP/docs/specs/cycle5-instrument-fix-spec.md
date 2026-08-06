# Cycle 5 — Instrument-fix round ((d)-class, spec)

**Status: BINDING.** Sources: SPJC-verdicts attribution (spjcverd
worktree, tmp/spjcverd_report.md), c4proj lockstep-gap finding, tip
battery report (c4tip, tmp/battery/). Mode: BUILD-COMPLETE-THEN-DEBUG.
Instruments REPORT, the law ADJUDICATES — every fix below makes an
instrument tell the truth; none changes a surface.

## Items

1. **Runway-datum radius** (`grade_graph_validate._grades_from_runway_datum`,
   `_RWD_RADIUS_M = 15.0`): a vertex 19.45 m from 16L/34R grading to it
   at 1.24% (< 1.5% cap) is flagged because the magic radius misses the
   runway. Replace the literal with the join/contact law's reach
   (`RUNWAY_JOIN_NEAR_M` / contact machinery — ONE authority for "near a
   runway"), never a new literal. Acceptance: the SPJC floor row (F2)
   stops flagging; diff the full battery-patch populations before/after
   (reuse the c4tip patches read-only — no rebuilds) and show no new
   misses.
2. **Grid-residual excuse** (`RASTER_REACH_BAND_GRID_RESIDUAL_M = 0.25`,
   config.py ~1766-1797): its mechanism claim is FALSIFIED (rows
   invariant under 3.0/2.0/1.5 m cells; it now excuses a ~50-row
   0.24-0.32 m continuum). DELETE the excuse; the rows report. The
   SPJC ceil quartet those rows contain is (a)-class solve/projection
   work (successor target) — do NOT chase it here; the instrument's job
   is to show it.
3. **CYXY anti-gaming ceil fixture**
   (`test_route_band_flags_cyxy_apron_ceiling`): asserts a defect that
   no longer exists (2 raw rows, both another class). Replace with the
   current population's invariant or delete; the +50 m injector test
   already carries the anti-gaming duty. Cite this spec in the change.
4. **`tools/trace_reach_route.py` REVIVED** (preferred over attic): it
   replays the RETIRED nearest-visible-centerline engine and refuses
   coordinates the live band serves — and it is the route-binding
   tracer the canyon-residual attribution needs. Re-implement on the
   live path (`building_feasibility.spine_value_fields` /
   `reach_band_unified` imports — never a re-derivation), same CLI.
   Update its tools/INDEX.md row in the same commit.
5. **Deferred adjudication in the harness**: the oracle's compliance
   verdict and census pass/fail must adjudicate EXCLUDING
   version-deferred classes per RULINGS d48bc0a, reporting them under
   their own heading (the battery computed this by hand — make the
   instrument do it). Citation in output: d48bc0a.
6. **Near-miss frontage census family**: the law binds
   (frontage_near_miss edges: HEAZ 4 · SPJC 12-38 · KCLT 78-86 · HECA
   118-138) but no LAW_FAMILIES row measures it (cross_shape reads 0
   everywhere) — enforcing it can only read as within_shape noise.
   Register the family in `check_grade.LAW_FAMILIES` with its lockstep
   twin (the test_harness structural twins force this); census gains
   the row.
7. **Sub-inversion band visibility**: production band law is
   inversion-only (`assert_no_final_band_inversion`) — a 0.3 m ceiling
   excess ships silent. Add a REPORT line (not a gate) for band excess
   above materiality; wire it into the build log and sidecar evidence.

## Discipline

Reuse the c4tip battery patches for population diffs (single-pass — no
rebuilds for censusing); pytest fixture builds only where a test itself
builds. No real-DEM acceptance builds. Materiality 0.01 m; attempt cap
2 per item; heartbeat. Twins: test_harness.py must pass (family
registration), test_final_band_inversion.py, the route-band tests
(SPJC's ceil-quartet red REMAINS red until the solve round — expected,
say so in the report, do not chase).
