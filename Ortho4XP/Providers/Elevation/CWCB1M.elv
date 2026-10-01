# Routt County, Colorado -- 2016 lidar (Merrick & Co. for the Colorado
# Water Conservation Board), served as a ready-gridded 3 ft DEM per tile
# by the CWCB lidar API.  Issue #154 (HOLDER airports KHDN Yampa Valley,
# KCAG Craig); spec docs/specs/us-holder-providers-spec.md §3.5 / §4;
# owner RULINGS 2026-09-30bm.
#
# Why this source: USGS 3DEP publishes no 1 m product over these two
# fields; the county flight reached the state (CWCB) distribution with
# the airfields present (KHDN 20 tiles, KCAG 14, 100 % box cover, scout
# hold154b 2026-09-30).
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

# Strategy: POST the airport polygon (WKT) -> tile keys; filter to the
# dataset through its cached tileSummaries listing; GET each tile zip
# whole into scratch; read the .img member through /vsizip/; VRT -> the
# shared warp (feet -> metres at the one vertical-unit site).
access_strategy=cwcb_lidar_api
tiles_url=https://coloradohazardmapping.com/api/lidar/tiles
summaries_url=https://coloradohazardmapping.com/api/lidar/tileSummaries
file_url_template=https://coloradohazardmapping.com/api/lidar/files/{tileKey}/{formatKey}
# "2016 Routt County" (GET /api/lidar/datasets).
dataset_ids=4e85e347-5533-4c2f-bf9e-522a9fd81bec
# The per-tile IMG DEM product of that dataset (the other format is LAS).
format_key=30993bf7-abc8-4339-978a-5e61cd692768
member_suffix=.img
# Days the cached tile listing (Elevation_data/cwcb1m_<dataset>_summaries
# .json, 5,309 tiles) is trusted before it is re-listed.
summaries_max_age_days=30

# The IMG header names "NAD83(2011) / Colorado North (ftUS)" without an
# authority code: pinned here (EPSG 6430).  1000 x 1000 cells of 3 ft.
source_srs=EPSG:6430
source_nodata=-9999
# Heights: NAVD88, US survey feet (Float32 values 6,377-6,539 at KHDN)
# -> metres at the warp, never shifted.
vertical_unit=ftUS
vertical_datum=NAVD88
native_resolution_m=0.9144

# THE SURGICAL CORE (as PITKIN1M, owner RULINGS 2026-09-30ay): the tiles
# whose footprint meets the aerodrome boundary buffered by this many
# metres; the rest of the inset box is the next ladder rung, assembled
# around the core as ONE raster (the two-layer inset, spec §4).
footprint_buffer_m=300
core_feather_m=60
fetch_slots=2

# Per-airport caps (spec §4; KHDN 20 tiles, KCAG 14; the listing's
# member bytes are 4.2-4.6 MB per tile, ~2.2 MB zipped).  Over either,
# the provider is SKIPPED and recorded unavailable -- never no-coverage.
max_tiles_per_airport=24
max_bytes_per_airport=120000000

publication_date=2016-10

# The 2016 Routt County dataset's tile hull (tileSummaries, 5,309 tiles,
# measured 2026-09-30): -107.6748..-106.7264 E, 39.9107..40.8280 N,
# rounded outward.  Outside it the provider answers no-coverage with no
# network call.
coverage_bbox=-107.68,39.91,-106.72,40.83

license=Unknown (CWCB lidar portal; no use restriction published)
license_note=No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw, the PITKIN1M reasoning for the same Merrick/CWCB flight family)
attribution=Colorado Water Conservation Board — 2016 Routt County LiDAR (Merrick & Co. for CWCB)

# A holder rung (spec §1): joins the USGS3DEP ladder by coverage box once
# the global assembly reads this key; standalone only when pinned
# (airport_elevation_providers=CWCB1M).  Below USGS3DEP (100).
ladder_member=True
priority=90

enabled=True
