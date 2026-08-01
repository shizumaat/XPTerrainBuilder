---
name: grade-check
description: Law-true grade defect counts for an airport. Use whenever counting grade violations, verifying zero-defect acceptance, or judging a build's surface lawfulness — a bare tools/check_grade.py run on a patch overcounts and its numbers must never be quoted as defect counts.
---

# Law-true grade check

The ONLY count that may be quoted as "defects" comes from the pytest frame,
which applies role caps, exemptions, and the law-true reference:

```bash
cd /Users/noah/XPTerrainBuilder/Ortho4XP
O4_TEST_AIRPORTS=<ICAO> venv/bin/python tools/run_with_ledger.py -- venv/bin/python -m pytest tests/test_pavement_grade.py -q
```

Replace `<ICAO>` with the airport (e.g. `KCLT`, `HECA`). Multiple airports:
comma-separated.

## Rules that gate the number you report

- **Bare `tools/check_grade.py` on a patch overcounts** (588/15k raw vs 0
  actionable at KCLT). Use it for locating geometry, never for counts.
- **Full census only.** Quarantine-excluded counts are unauthorized (owner
  2026-08-01, `docs/RULINGS.md`). The acceptance bar is absolute zero
  actionable law-true defects, pre-existing included.
- **Run from `Ortho4XP/` in the main tree** — wrong cwd or a worktree
  without `venv/` + `OSM_data/` builds a silently smaller layout (a
  PreToolUse hook blocks this, don't fight it).
- **Before quoting any DEM elevation**: check the inset-cache and sidecar
  STALE/rebuild log lines — warm-vs-cold cache state has moved terrain 12 m.
- **Emitted-defect scans** must subtract `_crown_of` — projection values are
  crown-lifted; an emitted step can be z′-level.
- The ledger wrapper means an identical already-passing run is reported from
  the ledger instead of re-executed; check
  `venv/bin/python tools/run_with_ledger.py --history` before repeating an
  expensive run another session may have done.
