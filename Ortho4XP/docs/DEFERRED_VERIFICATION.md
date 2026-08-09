# Deferred-verification ledger (pre-ship mode)

One line per streamlined land: the change, and the verification that
was SKIPPED under the 2026-08-09 "Pre-ship development mode" ruling
(docs/RULINGS.md). The ship gate pays this whole file in one
hardening round before the first official release: full suite,
battery A/B + censuses, timing profile, absolute-zero acceptance.
A change the sim verdict kills may strike its lines instead.

- 2026-08-09 lane/padrings (footprint-hugging pad rings, spec §2.5): skipped blast-radius suites, OTHH acceptance build, full offline-replay report.
- 2026-08-09 lane/basinseat (basin §2.2 rim-flush reseat): skipped blast-radius suites, clearance/threshold regression test completeness, all builds; in-sim only.
- 2026-08-09 integration of the four-lane round: battery airports never rebuilt under the merged tree (HEAZ byte-check + OTHH only); KCLT/KBNA/HECA/SPJC/SPLP/CYXY patches unverified post-merge; objpads real-DEM convergence loop unverified end-to-end.
- 2026-08-09 lane/flatdet (FLAT-SITE detector, report-only): ran only tests/test_flat_site_detector.py + test_harness.py -k sidecar; ZERO builds, so the pipeline call site is proven only by an in-process detect_for_layout + to_osm round trip, never by a real build's log/sidecar; no blast-radius suites for config.py/layout.py/pipeline.py/check_grade.py; inertness (byte-identical patch geometry vs pre-change) asserted by construction and never measured; the sweep's DEM frame is the BASE .hgt only — the production inset-baked surface is unswept (OTHH probed by hand: 5.014 m relief vs the 5.0 m 1-arcsec floor, a 0.014 m miss).
