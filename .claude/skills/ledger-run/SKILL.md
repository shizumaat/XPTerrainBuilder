---
name: ledger-run
description: Run correctness verification (pytest, airport builds, check_grade) through the persistent cross-session run ledger. Use before and for any expensive correctness run so work another session already did is not repeated.
---

# Ledgered verification runs

Correctness verification goes through the run ledger (owner 2026-07-18),
which persists results across sessions keyed by code-tree hash + argv +
`O4_*` env. An identical already-passing run is reported from the ledger
instead of re-executed.

```bash
cd /Users/noah/XPTerrainBuilder/Ortho4XP
venv/bin/python tools/run_with_ledger.py -- <command>
```

- **Check history first** — another session may have paid for this run
  already:

```bash
cd /Users/noah/XPTerrainBuilder/Ortho4XP && venv/bin/python tools/run_with_ledger.py --history
```

- **Never wrap wall-time benchmarks** (`check_build_time.py --run`,
  profilers) — timing must be measured fresh (hook-blocked). Use the
  `ab-time` skill for those.
- Correctness builds may run in parallel with other sessions' builds
  (owner 2026-07-31); only timing runs are exclusive.
- Run from `Ortho4XP/` in the main tree with `venv/` and `OSM_data/`
  present — wrong cwd silently yields a smaller layout (hook-blocked).
