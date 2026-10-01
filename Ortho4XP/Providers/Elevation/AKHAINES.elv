# Haines, Alaska -- 2020 DGGS lidar (RDF 2021-4), 1 m DTM, served by the
# Alaska DGGS elevation portal (elevation.alaska.gov).  Issue #154 (PAHN,
# a HOLDER airport); spec docs/specs/us-holder-providers-spec.md §4.
#
# THE FILE (lane aoi154, 2026-09-30): the portal serves dataset 1363
# ("Haines 2020 / DTM HS", listed as a hillshade layer) as ONE member,
# dds4/haines_2020/dtm/haines_2020_dtm_01242020.tif -- read whole: a
# 20,220 x 20,526 Float32 GeoTIFF, 1 m cells, NAD83 / UTM 8N (EPSG:26908,
# no vertical CRS), nodata -3.4e38, LZW; values 5-928 m; disc median at
# the ARP 6.6 m.  It IS the DTM.  The spec's two ruled lines do not fit
# it: the download is a zip generated per request (chunked, no ranges,
# data-descriptor members) and the member has no static URL (404 on the
# dds4 path), so neither direct_cog nor /vsizip//vsicurl/ can window it.
# The AOI strategy downloads the whole 322 MB zip per airport -- the cap
# below is raised from the 300 MB default for exactly that file.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

access_strategy=aoi_zip_download
query_url=https://elevation.alaska.gov/query.json
download_url=https://elevation.alaska.gov/download
# Project "Haines 2020", dataset "DTM HS" (the one-file DTM above).
dataset_ids=1363
member_glob=*/dtm/*.tif
user_agent_profile=engine

# Heights: NAVD88 (GEOID12B), metres (RDF 2021-4 metadata).
vertical_unit=m
vertical_datum=NAVD88
native_resolution_m=1

footprint_buffer_m=300
core_feather_m=60

# ONE 322,529,624-byte file whatever the polygon (measured 2026-09-30).
max_bytes_per_airport=350000000

publication_date=2021
# The dataset's extent (portal project.json, Haines 2020):
# -135.603..-135.293 E, 59.163..59.336 N.
coverage_bbox=-135.61,59.16,-135.29,59.34

license=State of Alaska DGGS public data (Raw Data File 2021-4)
license_note=No charge, no redistribution restriction published; use constraint: products shall indicate the source and describe modifications (DGGS RDF 2021-4 metadata). Not redistributed as data (owner RULINGS 2026-09-30aw).
attribution=Alaska Division of Geological & Geophysical Surveys — High-resolution lidar data for Haines, Alaska, December 2020 (RDF 2021-4)

ladder_member=True
priority=90

enabled=True
