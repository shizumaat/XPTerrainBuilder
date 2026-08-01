---
name: ab-time
description: Wall-clock build-time measurement protocol. Use for any timing, performance regression check, or before/after speed comparison — single-run timings swing ±25% and must never be quoted; most questions are answerable from the recorded phase-time ledger without building at all.
---

# A/B build-time measurement

## Step 0 — you may not need a build

Every build already persists per-phase wall times to
`~/.ortho4xp/auto_patch_build_times`. For phase-level A/B attribution, read
that file (attribute rows by `finished_at`; concurrent sessions write there
too). Only run fresh builds when the ledger can't answer the question.

## Fresh measurement

```bash
cd /Users/noah/XPTerrainBuilder/Ortho4XP
venv/bin/python tools/check_build_time.py --run --runs N <ICAO...>
```

- **Never one run per side** — the noise floor is ±25%; `--runs N` compares
  per-metric medians.
- **Timing runs are EXCLUSIVE** (owner 2026-07-31): no other build, pytest,
  or Ortho4XP instance may be live (a PreToolUse hook pgrep-blocks this).
  Correctness builds, by contrast, may run in parallel freely.
- **Never wrap timing in `run_with_ledger.py`** — a ledger replay would
  report a stale number as a fresh measurement (hook-blocked).
- **A session's FIRST build is cold-cache and must not be a baseline.**
- Check sidecar STALE/rebuild log lines before attributing any A/B delta —
  a stale pavement-pack sidecar books ~8 s into phase 2.
- Baselines: `tools/build_time_baselines.json`; owner approvals:
  `tools/build_time_approvals.json`.

## Budget law (canonical in `Ortho4XP/CLAUDE.md` §6)

Per-airport auto-patch ≤ 60 s, whole-tile ≤ 300 s, both cold and excluding
download. Any change costing ≥1% of its budget (0.6 s / 3 s) needs a Fable
optimization review; crossing a budget needs written explanation + explicit
owner approval.
