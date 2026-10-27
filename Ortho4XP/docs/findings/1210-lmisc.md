# #1210 — a LAS tile that declares no CRS never lets the ladder settle (lane lmisc)

## Attribution

Tile +48-124, KFHR inset sidecar `N48W124_airport_insets/KFHR_usgs3dep.json`:
the USGS3DEP ladder delivered rung 4 (1/9″); rung 3 (USGSLPC) is recorded
`transient` (HTTP 429 on tile `USGS_LPC_WA_SANJUANCO_2009_000297`).

The TNM LPC listing over the airport is 57 tiles of the 2009 legacy flight
`WA_SANJUANCO_2009`. Header of `…_000300.laz` (first 64 KB, range read
2026-10-26): LAS 1.1, point format 1 (LAZ bit set), TerraScan, ONE VLR
(`laszip encoded`), and no GeoKeys or WKT VLR. Its extents are x 496,999.94–497,749.94,
y 5,375,800.05–5,376,550.05 and z 25.39–106.88, which reads as UTM 10N in metres.
`las_header_units` -> `header.parse_crs()` is `None` -> `ProviderUnavailable("USGSLPC: tile declares no CRS")`.

The loop:
1. The `transient` rung records no listing, so `ladder_recheck_owed` names it and the re-check
   finds every id new and re-runs the ladder.
2. The re-run downloads tiles, validates the first one and is refused with
   `unavailable: tile declares no CRS`.
3. An `unavailable` that is not the cap class (#583) or the decoder class
   (#595) records NO listing (`_stored_rung_listing` -> `None`), so step 1
   is owed again on every pass, and `--refresh-data dem` cannot settle the frame.

The refusal is correct: a 1 m lattice cannot be laid without a CRS, and
guessing a UTM zone from coordinates is a data-truth decision (State Plane
feet and UTM metres overlap in range). The defect is that the refusal is
not RECORDED as an answer.

## Rule

THE PRODUCT CLASS. A listed tile whose own bytes make it unusable for a
reason that is a function of the tile, the provider's definition and the
engine — a CRS that is absent, unreadable, unprojected, or not the one the
provider declares — is refused `ProviderUnavailable` with
`declined_by_product = True`.  The ladder records it exactly as the cap
class: `listing_ids` (the rung's listing) + `declined_under`
(`_rung_ask_signature`: definition digest, engine version, capabilities).
The re-check then asks the rung again only when the listing, the
definition or the engine moves: a new flight over the airport, an
edited `.elv`, or a new engine that can read the tile. A short or damaged
download is NOT this class, because downloading again can fix it.

No law change: this extends the #583 record (RULINGS 2026-09-30bu (4) and
#583's signature rule) to a second deterministic refusal.

## Acceptance

* Twin: a ladder whose LPC rung raises the product-class refusal records
  `unavailable` + `listing_ids` + `declined_under`; `ladder_recheck_owed`
  is `[]` for it; the same listing re-checks `unchanged`; a new id re-asks.
* Twin: `las_header_units` on a header with no CRS raises with
  `declined_by_product`.
* Real: KFHR `--refresh-data dem` settles the tile: the rung records
  `unavailable` with its listing, and `ladder_recheck_owed` is `[]`.
