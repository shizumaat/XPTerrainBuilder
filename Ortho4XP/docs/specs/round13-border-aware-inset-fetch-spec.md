# Round 13 — border-aware inset fetching: valid data outranks a newer date

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **r13border**. Pre-ship
mode (docs/RULINGS.md); deviations STOP-and-report. Engine-side:
`src/O4_Airport_Elevation_Insets.py` + tests. No conflicts with the
app-side lane (Swift files only).

## Measured attribution

KMCI's 1 m inset was assembled ENTIRELY from
`KS_Statewide_2018_A18` tiles — the Kansas statewide project — for a
Missouri airport, yielding a 100 % NODATA raster the old coverage
metric reported as full. Mechanism (O4_Airport_Elevation_Insets.py
~943-970): `discover` sorts sources newest-publication-first and
`fetch` keeps ONLY the newest-date group (`chosen = sources whose
publication_date == newest`), then mosaics without any validity check.
A border airport's bbox intersects tiles from BOTH states' projects;
whichever published latest wins wholesale, valid or not. The owner's
directive: "extra precautions and error handling for other airports
close to potential data borders like state and country lines."

## The laws

### R13-1 A FETCH RECORD WITHOUT A VALID RASTER IS NO RECORD

At fetch-or-reuse time, an inset whose sidecar `.json` exists but
whose `.tif` is ABSENT, or fails the round-11 validity test
(`inset_valid_fraction` < `INSET_MIN_VALID_FRAC` — reuse the R11
implementation, never a second one), is treated as UNFETCHED: the
stale record is renamed `<name>.json.invalid-<date>` (evidence, not
deletion) and the fetch runs again. This retires the
manually-rm-the-json class permanently.

### R13-2 EVERY PIXEL TAKES THE NEWEST SOURCE WITH VALID DATA THERE

`fetch` stops restricting to the newest-date group. The assembly rule:
each pixel of the assembled inset takes the NEWEST discovered source
that has VALID (non-NODATA) data at that pixel — so a border airport
mosaics across both states' projects, newest data still wins wherever
it is real, and a project that is NODATA over the airport contributes
nothing. Implementer owns the gdal mechanics (verify whether
multi-input `gdal.Warp` propagates NODATA correctly for
later-wins ordering; if not, sequential passes filling target NODATA
from the next-newest source — measured, not assumed). Constraints:
* only sources sharing the provider definition's `vertical_datum` mix
  (all 3DEP is NAVD88 today — assert it, do not silently mix);
* bound the source count (cap at the existing discovery result — no
  new network behaviour beyond fetching sources `discover` already
  returns; downloads still happen only inside authorised refresh
  scopes, unchanged);
* after assembly, measure `inset_valid_fraction` on the RESULT and
  write it into the sidecar; below threshold the file still lands
  (with its honest record) and R11's runtime refusal remains the last
  line of defense.

### R13-3 THE RECORD NAMES ITS SOURCES, PER CONTRIBUTION

The sidecar gains: `valid_fraction`, and per-source entries
(title, publication_date, source_id) split into `sources_used` vs
`sources_empty_over_bbox` (a discovered source whose contribution was
entirely NODATA over the bbox). The fetch log line says when a
multi-project mosaic happened: `[inset] KMCI: border-aware mosaic — N
source(s) across M project(s), valid 99.x %`.

## Tests (extend tests/test_airport_elevation_insets.py or a new
## tests/test_round13_border_fetch.py — follow the existing fixture
## idiom; synthetic rasters, no network)

1. Record-invalidation twin: json-without-tif refetches; json+invalid
   tif (0 % valid) refetches and archives the record; json+valid tif
   is left alone byte-identical.
2. Border-mosaic twin: two synthetic sources, newer NODATA over the
   east half, older valid everywhere ⇒ assembled inset valid
   everywhere, east half from the older source, west half from the
   newer; sidecar names both correctly.
3. All-invalid twin: every source NODATA over the bbox ⇒ file lands
   with valid_fraction ~0 and an honest record; R11's refusal path
   (existing twin) still covers the runtime side.
4. Datum-guard twin: mixed vertical_datum candidates refuse the mix
   loudly.

## Acceptance (owner-authorised refetch — the standing "definitely
## refetch KMCI" directive)

From the lane's Ortho4XP dir, ledgered:
`venv/bin/python tools/run_with_ledger.py -- venv/bin/python
tools/harness/build_airport.py KMCI --refresh-data dem`
* The stale KMCI record (json without tif) is archived and the fetch
  RUNS (R13-1 — no manual rm needed).
* The new `KMCI_usgs3dep.tif` reports valid_fraction ≥ 0.95 in its
  sidecar, with Missouri-side project tiles in `sources_used`; quote
  the sidecar's sources and fraction verbatim.
* `tools/flat_site_sweep.py --dem-source airport-inset` (read-only,
  indexed) reads real KMCI relief (recon baseline off base DEM:
  ~15.6 m), not no_data.
* The build itself rc=0 with the inset BAKED (the frame line shows
  KMCI's inset in the DEM world, not "no inset baked"); KFLV/KMKC
  insets untouched byte-identical (R13-1 leaves valid records alone).

## Bookkeeping

Lead writes the DEFERRED_VERIFICATION line at merge. Other
effectively-empty insets on the tile (KSTJ etc., 9 flagged by R11)
will self-heal through R13-1 on their airports' next authorised dem
refresh — record that expectation in the report, do not refresh them
here (one authorised scope, one airport's need).

## AMENDMENT 2026-08-11 (lead ruling on the acceptance STOP:
## THE HARNESS GAINS --warm-insets)

The patch-build path is documented pure-disk and never reaches
`ensure_airport_insets`; the two existing remedies are each unlawful
(the standalone fetch tool bypasses the refresh lock/ledger; a tile
build refreshes every void inset against the one-airport scope). The
consult-before-create answer is the implementer's third option,
APPROVED and IN SCOPE:

* `tools/harness/build_airport.py` gains `--warm-insets ICAO[,ICAO..]`
  — valid ONLY together with `--refresh-data dem`; inside the existing
  per-scope lock, before the build's DEM prep, it calls
  `ensure_airport_insets` for exactly the named airports (forcing the
  pass for them even when the tile's `is_cached` stamp would skip it),
  with every write inside the authorised scope's snapshot + the
  refresh ledger record naming the airports. One INDEX.md row update
  on the existing build_airport entry (a parameter, not a new tool).
* One harness twin in tests/test_harness.py's idiom: `--warm-insets`
  without `--refresh-data dem` refuses; with it, the named airport's
  `ensure_airport_insets` is invoked and a foreign airport's is not
  (monkeypatched, no network).
* ACCEPTANCE becomes: `... build_airport.py KMCI --refresh-data dem
  --warm-insets KMCI` — then the original bullets verbatim (archived
  stale record, sidecar sources_used/valid_fraction ≥ 0.95 with
  Missouri-side sources, sweep reads real relief, inset baked in the
  frame line, KFLV/KMKC byte-identical).
* The `is_cached` size>0 gate (a non-empty-but-invalid raster skips
  the whole pass) is RECORDED as a ledger item, not fixed here —
  `--warm-insets` bypasses it for explicitly named airports, which is
  the instrument the heal path needs.
