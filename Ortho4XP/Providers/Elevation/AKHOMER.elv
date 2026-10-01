# Homer, Alaska -- 2019 DGGS Homer lidar, 1 m bare-earth DTM, served by
# the Alaska DGGS elevation portal (elevation.alaska.gov).  Issue #154
# (PAHO, a HOLDER airport: the census's holder is "2019 DGGS Homer");
# spec docs/specs/us-holder-providers-spec.md §3.6/§4, RULINGS 2026-09-30bm.
#
# WHICH DATASET (lane aoi154, measured 2026-09-30, a deviation from the
# brief's ids=885 -- reported, not decided):
#   885  Homer Topobathy 2018 DTM (USACE NCMP 1 m, 1 km tiles, ~7 MB each)
#        is a COASTAL strip: over the PAHO core it listed 7 files / 50 MB
#        and delivered airport_valid_fraction 0.327, runway 4/22
#        centreline 41.5 % valid, NO valid cell within 60 m of the ARP --
#        below the 0.80 airport-cover rule.
#   1345 Homer 2019 DTM is ONE 1,419,887,064-byte BigTIFF
#        (dds4/homer_2019/dtm/homer_dtm.tif) whatever the polygon:
#        airport_valid_fraction 0.846, runway centreline 100 % valid,
#        ARP disc median 24.36 m vs apt.dat 25.30 m (-0.94 m); 1,420 MB
#        downloaded in 656 s (2.2 MB/s), warp ~10 s.
# The 2019 file is the only dataset that covers the aerodrome, so the cap
# below is raised to hold it (the PITKIN1M precedent: 1.2 GB).
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

# Strategy: POST the request polygon (form field geojson=) to the query
# endpoint -> [{dataset_id, files, bytes, ...}] filtered to dataset_ids;
# the bytes answer is the cap check; GET the download endpoint -> one zip
# into scratch -> members via /vsizip/ -> VRT -> the shared warp.
access_strategy=aoi_zip_download
query_url=https://elevation.alaska.gov/query.json
download_url=https://elevation.alaska.gov/download
# Project "Homer 2019", dataset "DTM".
dataset_ids=1345
# Member: dds4/homer_2019/dtm/homer_dtm.tif (BigTIFF, 1 m).
member_glob=*/dtm/*.tif
# The portal has no gate: the engine's own agent.
user_agent_profile=engine

# Heights: NAVD88 (GEOID12B), metres (DGGS metadata).
vertical_unit=m
vertical_datum=NAVD88
native_resolution_m=1

# THE SURGICAL CORE (the las_tile_index idiom, spec §1/§3): as a ladder
# rung the portal is asked for the aerodrome boundary buffered by this
# many metres; the ladder assembles the surround.  Standalone (no
# footprint) the whole inset box is asked for.  (This dataset is one file
# either way.)
footprint_buffer_m=300
core_feather_m=60

# Per-airport cap on the portal's byte answer.  Over it the provider is
# SKIPPED and recorded unavailable, never no-coverage.
max_bytes_per_airport=1500000000

publication_date=2019
# The dataset's extent (portal project.json, Homer 2019, measured
# 2026-09-30): -151.729..-151.374 E, 59.599..59.706 N.
coverage_bbox=-151.73,59.59,-151.37,59.71

license=State of Alaska DGGS public data (2019 Homer lidar)
license_note=No restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw); DGGS asks that products indicate the source.
attribution=Alaska Division of Geological & Geophysical Surveys — 2019 Homer lidar (Alaska elevation portal)

# BELOW USGS3DEP (100): a ladder member by resolution (spec §1 global
# assembly), standalone only when pinned
# (airport_elevation_providers=AKHOMER).
ladder_member=True
priority=90

enabled=True
