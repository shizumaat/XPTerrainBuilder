# XPTerrainBuilder

macOS Swift app + vendored Python engine that builds X-Plane ortho scenery.

- `Sources/` — SwiftPM targets: `SceneryKit` (engine client + models),
  `XPTerrainBuilder` (app). Build: `swift build`; app bundle:
  `./scripts/make_app.sh`; bundled engine: `./scripts/make_engine.sh`.
- `Ortho4XP/` — the Python engine. It has its own `CLAUDE.md`, and
  `src/auto_patch/` another; read them before engine work (the hard
  build-time law lives there). Python is `Ortho4XP/venv/bin/python`
  (no system python; `venv/bin/pip` is broken — use `python -m pip`).

## Blast-radius index (check before editing)

Before editing anything under `Ortho4XP/src/` or `Sources/`, run:

    Ortho4XP/venv/bin/python tools/blast.py <file>

~100-token answer: direct importers, tests to run, role-literal / env-flag /
wire-protocol hazards, co-change neighbors. Self-rebuilds when stale (~2 s).
`tools/blast.py --audit` verifies index recall against grep ground truth.

## Cross-language wire protocol (silent-break hazard)

`Ortho4XP/src/o4_engine/events.py` class names ARE the JSONL wire names
(`type(self).__name__`); `Sources/SceneryKit/OrthoEngineClient.swift` matches
them as string literals. Renaming either side breaks the other silently —
the string never appears in Python source. `blast.py` reports drift.

## Doc landmines

- `docs/HANDOVER.md` and `docs/PITFALLS.md` describe the retired
  XPSceneryDoctor app: their file maps are wrong; the numbered gotcha
  lore is still valid.
- `Ortho4XP/STATUS.md`: only the TOP dated block is current; the rest is
  history. Never load it whole (~90k tokens).

## Measurement traps (each of these has actually bitten)

- auto_patch builds run only from `Ortho4XP/` cwd with `venv/` AND
  `OSM_data/` present — wrong cwd or a fresh worktree exits 0 with a
  silently smaller layout that reads as a fake speedup.
- Single-run wall times swing ±25%: never A/B one run per side
  (`tools/check_build_time.py --runs N`).
- Before quoting any DEM elevation or phase timing, check the inset-cache
  and sidecar STALE/rebuild log lines — warm-vs-cold cache state has moved
  terrain 12 m and faked an 8 s regression.
