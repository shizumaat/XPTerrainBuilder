# Texas statewide lidar -- TxGIO (formerly TNRIS) StratMap and partner
# collections, 1 metre bare-earth DEM, best available per tile.
# Issue #154 (11 HOLDER airports: KGRK KACT KTPL KGLE KBWD KILE KTRL KGTU
# KHLR T31 KLUD); spec docs/specs/us-holder-providers-spec.md §3.2/§4;
# owner RULINGS 2026-09-30bm.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

# Strategy: ONE statewide tile-index FeatureServer layer (EPSG:3857,
# maxRecordCount 2000), filtered to the best-available tile of each
# quarter-quad cell; each feature names a TILE (tileid) of a COLLECTION
# (collid).  The TxGIO resources API (one listing per collection, memoised
# in Elevation_data/texas1m_resources.json) resolves the collection's
# per-quad DEM zip; the ONE member per tile is copied out of the remote
# zip by HTTP range reads (archive_access=remote_member) -- the archive is
# never downloaded whole.
access_strategy=arcgis_feature_tiles
index_layer_url=https://feature.geographic.texas.gov/arcgis/rest/services/Status_Maps/Lidar_Index_Public/FeatureServer/0
# bestavail is a STRING field ('Yes' / 'No'), verified live 2026-09-30.
index_where=bestavail='Yes'
tile_id_field=tileid
collection_field=collid
archive_resolver=tnris_resources
archive_resolver_url=https://api.tnris.org/api/v1/resources/?collection_id={collid}&resource_type_abbreviation=DEM
archive_resource_suffix=_dem.zip
# The S3 ORIGIN, never the CloudFront host data.geographic.texas.gov
# (403 on non-browser agents -- scout hold154b); public-read, ranges OK.
archive_url_template=https://s3.amazonaws.com/data.tnris.org/{collid}/resources/{prefix}_{tileid7}_dem.zip
archive_access=remote_member
# One member per feature: {prefix2}-1m_{tileid}.tif (or .img).
member_filter_template=-1m_{tileid}

# Members carry their own CRS: EPSG 6343 / 26915 / 26914, or (Hays-
# Williamson 2024) a compound UTM 14N + NAVD88 WKT without a top-level
# code -- all warp as read.  A member with NO CRS at all is declared in
# this one (UTM 14N, the statewide majority) rather than dropped.
source_srs=EPSG:6343
# Heights: NAVD88 metres (the tile CRS declares metre where it declares a
# vertical axis; a contradiction is refused, never scaled).
vertical_unit=m
vertical_datum=NAVD88
# Fill values: -9999 (StratMap 2020) and -999999 (2024) -- declared on the
# band; an undeclared one below any land is sniffed per member.
source_nodata=-9999

native_resolution_m=1

# THE SURGICAL CORE (spec §1/§4, the PITKIN1M rule): when the ladder hands
# the aerodrome boundary, only tiles whose footprint meets the boundary
# buffered by this many metres are read; the rest of the inset box is the
# next ladder rung, assembled around the core as ONE raster.
footprint_buffer_m=300
core_feather_m=60

# Per-airport cap on the tile members read.  Over it the provider is
# SKIPPED and recorded unavailable -- never no-coverage, never a slice.
max_archives_per_airport=16

# The tile index's own extent (FeatureServer layer extent, measured
# 2026-09-30): -106.875..-93.500 E, 25.814..36.548 N.
coverage_bbox=-106.88,25.81,-93.49,36.55

publication_date=2008-2024 (per collection; best available per tile)
license=CC0 1.0 (TxGIO public data)
license_note=TxGIO publishes its lidar collections as public data with no use restriction (CC0); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=Texas Geographic Information Office (TxGIO), StratMap lidar

# BELOW USGS3DEP (100): reaches an airport as a ladder member
# (ladder_member=True, the global assembly of spec §1) or standalone when
# pinned (airport_elevation_providers=TEXAS1M).
ladder_member=True
priority=90
enabled=True
