# 0004 Synthetic-first iteration; one closing build; the sweep per merged batch

## Date

2026-10-18 (records the owner's BUILD ECONOMY + GATES, 2026-08-29e/f)

## Status

accepted

## Context

A real airport build takes minutes to tens of minutes. Repeating it for every
change and every airport made rounds slow. The owner set a build economy
(2026-08-29e/f). Its canonical text is the "BUILD ECONOMY + GATES" section of
`Ortho4XP/CLAUDE.md`. A brief that demands more verification than that section
allows is invalid.

## Decision

Mechanisms iterate synthetic-first. A lane captures the airport once with
`tools/v2_solve_replay.py --capture`, then replays stages for each change
(`--replay --from STAGE`, `--why-hard`, `--probe-site`, `--emit`, `--verify`), and
also uses offline replays and synthetic twins. The real airport builds once per
round, as the closing test, at one representative airport (the one with the
owner's site). The five-airport sweep runs once per merged batch at app-build
time, run by the orchestrator and never by a lane. Controls are shared through the
artifact ledger and never rebuilt.

## Consequences

- Lanes register their captures (`tools/harness/frames.py register`), so the next
  lane can replay a capture instead of taking a new one.
- A build or census wrapper written privately by a lane is a defect. Builds and
  measurements go through `tools/harness/` (root `CLAUDE.md`).
- Ambiguity, not resolved here: "2026-08-29e/f" is cited as a ruling key, but
  `docs/RULINGS.md` has no entry headed 2026-08-29. The binding text is the
  `Ortho4XP/CLAUDE.md` section.
