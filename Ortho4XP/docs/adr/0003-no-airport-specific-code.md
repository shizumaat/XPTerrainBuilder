# 0003 No airport-specific code

## Date

2026-10-18 (records RULINGS 2026-10-05e)

## Status

accepted

## Context

Defects are found at named airports. A fix that asks which airport is being built
adds a switch that never carries over to other airports. The owner asked for a
rule against this (RULINGS 2026-10-05e). No such rule existed. The one existing
airport-specific setting was Law C (RULINGS 2026-09-10ap:
`law/airports.toml [OTHH] kerb_wall_corridors`). It was kept because nothing in
the geometry or the map told its two cases apart.

## Decision

An airport is a test case. It shows a defect, and the fix is a general rule that
applies to every airport. No engine, app or law-table code asks which airport it
is building: no ICAO literal, no table or key named for an airport, no pack name,
no coordinate window, no threshold tuned so that one named airport passes. If no
general rule in the geometry or the map can tell two cases apart, that is a
finding for the owner, never a switch. Briefs name an airport as the place a
defect was found and as the closing test, never as the scope of the fix.

## Consequences

- `tests/test_no_airport_specific_code.py` checks Python literals, Swift literals
  and law tables. Its RECORDED set may fall, never rise.
- RULINGS 2026-10-05e left the status of the Law C setting OPEN for the owner.
  The root `CLAUDE.md` says the RECORDED set has been empty since RULINGS
  2026-10-05g. This ADR does not rule on it. Read those two entries.
