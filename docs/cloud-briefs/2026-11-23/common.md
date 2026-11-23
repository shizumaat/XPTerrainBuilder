# Cloud lanes, 2026-11-23 (the Mac is asleep)

Base: `claude/project-thread-ddpu46` at 03226a8ab or later (Beta 9 integration, not yet on main). Read
`CLAUDE.md`, `Ortho4XP/CLAUDE.md`, `Ortho4XP/src/CLAUDE.md`, and the rulings named in your brief.

- The cloud has no data corpus, no X-Plane and no captures. Work from code, synthetic fixtures and unit
  tests. Say plainly what needs a real build on the Mac; no airport result may be claimed.
- Work on your own branch `claude/<lane>`. Open a DRAFT PR with base `claude/project-thread-ddpu46`; the PR
  body is your report: net lines +/-, new public symbols, tests run, what is unverified, and a "Process" line.
- Never merge, comment on issues, notify the owner or create routines.
- Keep the gates: `tools/ratchets.py` (duplicates, unused, layers, lint), the code-key closure twins, and
  `tests/test_no_airport_specific_code.py`. No airport-specific code. The Mac app is the layout authority
  and Qt mirrors it in the same PR (`tests/test_qt_layout_parity.py`). `o4_engine/events.py` class names are
  wire names matched in `Sources/SceneryKit/OrthoEngineClient.swift`.
- Do not touch the one-map files being designed on the Mac unless your brief names them:
  `pipeline/late_stage.py`, `planar/ribbons.py`, `classify/gap_terrace.py`.
