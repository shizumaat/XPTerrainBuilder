# Pitkin County, Colorado -- 2016 lidar (classified LAS point clouds),
# gridded in-engine to a 1 m DTM.  Issue #130 (KASE, Aspen); spec
# docs/specs/las-tile-lidar-provider-spec.md; owner RULINGS 2026-09-30av
# (the provider) and 2026-09-30aw (ON, no licence switch; the USGS3DEP
# ladder reaches it as a rung).
#
# Why this source: the only USGS 1 m project around Aspen never flew the
# cell over the airfield (RULINGS 2026-09-30ab), and the 2016 Pitkin
# County flight's airfield tiles were WITHHELD from the state (CWCB)
# distribution and never reached USGS -- the county's own server still
# serves all of them (RULINGS 2026-09-30au).
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

# Strategy: an ArcGIS feature index of LAS tiles -> whole-tile download
# into Elevation_data/_las_tiles/PITKIN1M/ (the las_tiles refresh scope)
# -> per-tile ground-class binning-mean DTM -> the shared warp.
access_strategy=las_tile_index

# The tile index (FeatureServer layer 6 of the county's Contour and LiDAR
# Index): {west},{south},{east},{north} = the airport box in EPSG:4326.
index_url_template=https://maps.pitkincounty.com/arcgis/rest/services/Hosted/Contour_and_LiDAR_Index_(HFV)/FeatureServer/6/query?geometry={west},{south},{east},{north}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=name&returnGeometry=false&f=json
# The attribute that names a tile.
index_name_field=name
# One 3,000 x 3,000 ft tile, LAS 1.4 point format 6, uncompressed.
tile_url_template=https://maps.pitkincounty.com/downloads/elevation/2016_LiDAR/Classified_LAS1.4/2016-{name}.las
# Metadata: https://maps.pitkincounty.com/downloads/elevation/2016_LiDAR/metadata/2016-Pitkin_Classified_Lidar.xml

# Point coordinates: NAD83(2011) / Colorado Central (ftUS).  A tile whose
# header CRS disagrees is refused (never cached).
source_crs=6428
# Heights: NAVD88 (Geoid12A), US survey feet -> metres, never shifted.
vertical_unit=ftUS
vertical_datum=NAVD88

# ASPRS classes gridded (2 = ground); withheld-flagged points dropped.
ground_classes=2
# The DTM cell, in metres (laid out in the source CRS).
grid_resolution_m=1
native_resolution_m=1
# A cell needs this many ground points before the fill; the fill closes
# holes up to this many cells deep (3 x 3 mean-of-valid rounds); beyond
# it the cell is NoData and the base DEM shows through under the bake.
min_points_per_cell=1
fill_radius_cells=3

# Per-airport caps (KASE: 63 tiles, 7.06 GB).  Over either, the provider
# is SKIPPED and recorded unavailable -- never no-coverage.
max_tiles_per_airport=64
max_bytes_per_airport=8000000000
# Keep the raw tiles so a grid-rule change re-grids without a re-download.
keep_raw_las=true

# Declared accuracy (Merrick & Co. for CWCB, 2016): RMSEz 4.5 cm.
rmse_z_m=0.045
publication_date=2016-08

# Pitkin County's LiDAR index reaches -107.28..-106.59 E, 39.02..39.37 N
# (index extent, measured 2026-09-30); the county boundary (Census TIGER,
# GEOID 08097) is -107.466..-106.426 E, 38.978..39.366 N.  No lidar tile
# lies west of -107.28, so this box holds every tile.  Outside it the
# provider answers no-coverage with no network call.
coverage_bbox=-107.40,38.95,-106.30,39.55

license=Pitkin County GIS open data (disclaimer only)
# The disclaimer is the one the county's LiDAR / Data Download pages link
# as "All users agree to Pitkin County's GIS Disclaimer" (verified
# 2026-09-30).
license_note=No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw); disclaimer: https://pitkincounty.com/478/Disclaimer
attribution=Pitkin County, Colorado — 2016 LiDAR (Merrick & Co. for CWCB)

# BELOW USGS3DEP (100): PITKIN1M reaches an airport as USGS3DEP's ladder
# rung (resolution_ladder=1|...|provider:PITKIN1M), and standalone only
# when pinned (airport_elevation_providers=PITKIN1M).
priority=90

enabled=True
