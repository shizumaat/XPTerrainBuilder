# 0002 One shared data repo; downloads are explicit ledgered events

## Date

2026-10-18 (records RULINGS `e9daef5`, the entry "2026-08-05 — One shared data repo across lanes (owner)")

## Status

accepted

## Context

Lanes that keep private caches measure different data. A cache refreshed as a
side effect of a build changes results without anyone noticing: a KCLT road-feed
refresh ran inside a tile build and changed campaign hashes in the middle of the
night. The owner made one shared data repo mandatory. The root `CLAUDE.md` cites
the ruling as RULINGS `e9daef5`. In `docs/RULINGS.md` it is the entry headed
"2026-08-05 — One shared data repo across lanes (owner)". Later entries that apply
it are headed "applying owner ruling e9daef5" (2026-08-08, 2026-08-11).

## Decision

One data repo holds DEM + insets, OSM extracts + road feeds, the airport mod
cache, geotiffs, masks, the DSF cache and orthophotos. Every lane mounts it
through the harness ritual. No lane copies it or creates a private cache.
Downloads and cache regenerations write into the repo exactly once, as explicit
logged events (`build_airport.py --refresh-data <scope>`, recorded in
`.harness/refresh_ledger.jsonl`), and never happen as a side effect of a build.
Two lanes running at once never both regenerate the same cache: the harness takes
a lock, or refuses and reports. Lane products (`Patches`, `Tiles`, `Previews`,
`tmp`) stay inside the lane.

## Consequences

- Two lanes measure the same inputs, and every changed hash has a ledger entry
  behind it.
- A build that would download or regenerate data refuses, and its message names
  the `--refresh-data` command to run instead.
- Ambiguity, not resolved here: `e9daef5` is cited as a key but is not a RULINGS
  heading key. `docs/RULINGS.md` also has two entries dated 2026-08-05, so
  `tools/docq.py ruling 2026-08-05` returns the other one. Find this entry by its
  heading text.
