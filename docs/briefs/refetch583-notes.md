# refetch583 — lane notes (issue #583)

## Step 1 — attribution (read + app log, 2026-10-12)

- WHY a re-fetch was pending at all: KGRF / KTCM sidecars (shared corpus,
  read only) carry `delivered_rung 0` with airport cover 0.00 / 0.54
  (< 0.80), so `ladder_recheck` re-asks the same-resolution rungs (#153).
  Rung 3 `USGSLPC` is `unavailable` by CAP (54 tiles / 26.1 GB vs 40 /
  3.0 GB) and records `listing_ids: None`, so `_stored_rung_listing`
  answers "cannot say" and EVERY id discovery lists is new: the re-check
  is `new-listing` on every build, forever. RULINGS 2026-09-30bv REPORTED
  (2) named this class and left it undecided. The owner's app log
  (`~/Library/Logs/XPTerrainBuilder/engine-stderr.log` lines 139/148 and
  712/714) shows the same two airports re-fetched by two consecutive app
  builds of +47-123 (hundreds of MB each time).
- WHY the pre-flight was silent: `build_airport.py main` passes
  `None if args.tile else args.icao` to `this_airports_inset_problem`,
  which returns None with no icao ("a --tile run judges the whole tile");
  nothing judges the other airports of the tile. Only the index negatives
  (`unverified_inset_negatives`) are tile-wide.
- WHY the guard let the writes through: the strategies cut their scratch
  beside the destination (`<inset>.tif.refetch.rungN`, `.tnmN.zip`,
  `.prefetchN.tif`, `.surroundN`, …) and GDAL writes them in C; the guard
  patches Python `open` / `os.*` only. The Python `os.remove` of each
  scratch file was then the first call it saw.
