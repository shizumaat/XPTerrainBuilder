# Lane c0clocks: exact groundwork for the one-map solve (#2206)

Read `common.md` and `Ortho4XP/docs/specs/one-map-solve-spec-20261123.md`. Implement ONLY two exact steps; the
design's other steps wait for experiments on the Mac:
- **Step 0**: each prefix run's step walls, the stage-1 worker's outcome and clock, and the `fc.finish()` tail in
  `report.json`.
- **Step 4, first half**: memoise the feasibility LP across stage-1 passes with an unchanged hard set
  (`solve/feasibility.py:437`). The answer must be identical, shown by a synthetic twin.
Output must be byte-identical: clocks and a memo change no heights.
