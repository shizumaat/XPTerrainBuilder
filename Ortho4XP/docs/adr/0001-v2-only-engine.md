# 0001 v2 is the only engine; v1 survives as readers and the object stage

## Date

2026-10-18 (records RULINGS 2026-09-13au; ADR format approved in RULINGS 2026-10-17a Q7)

## Status

accepted

## Context

By 2026-09-13 the owner judged v2 superior and asked for v1 and its config
setting to be removed. RULINGS 2026-09-13au retired v1 in two stages. Stage A
made v2 the only engine that could run: it deleted the `auto_patch_engine`
setting, the app's Settings row and `build_airport.py --engine`. Stage B deleted
every `src/auto_patch/` module that v2 does not import. `src/auto_patch/CLAUDE.md`
records how it ended: stage B round 1 (2026-09-17) cut the import seams, and round
2 (2026-10-04) deleted the tree. 29 modules remain, listed in
`tests/test_v1_retired.py` `KEEP`.

## Decision

`src/auto_patch_v2/` is the only engine: the planar map, the law constraints, the
one staged solve and the emit. What remains of `src/auto_patch/` is the tile
driver, the readers (apt.dat, CIFP, DSF, AGP, OBJ8, OSM aeroway), the flat-site
detector and the post-mesh object stage. None of it builds or solves a surface.
RULINGS 2026-09-13au is the canonical law. This ADR summarises it and adds no law.

## Consequences

- New engine work goes in `auto_patch_v2`. A new module under `auto_patch/` is a
  visible edit to `KEEP` in `tests/test_v1_retired.py`.
- No setting, flag or harness option selects an engine.
- The harness, the census, `shared_repo_guard`, the ledger and the lane worktree
  tooling do not depend on the engine, and they stayed (13au).
