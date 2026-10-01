# NOAA OCM Digital Coast -- 2012 FEMA Lidar: Valdez, AK (dataset 8539),
# classified COPC LAZ point clouds gridded in-engine to a 1 m DTM.
# Issue #154 (PAVD, Valdez Pioneer Field: the census's one holder that
# exists only as a point cloud); spec docs/specs/us-holder-providers-spec.md
# §3.3 / §4; owner RULINGS 2026-09-30bm (spec), 2026-09-30bu (LAZ through
# lazrs behind CAPABILITY_LAZ), 2026-09-30bw (global ladder assembly).
#
# Joins the USGS3DEP ladder through ladder_member=True wherever its
# coverage box reaches the airport box; standalone only when pinned
# (airport_elevation_providers=NOAAVALDEZLAZ).
role=airport_inset
access_strategy=las_tile_index

# The tile index is the dataset's GeoPackage on NOAA's anonymous S3
# bucket, opened over /vsicurl/ (range reads, never the whole file) and
# filtered by the surgical footprint.  Schema: filename, srs, url.
index_format=ogr
index_url=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/laz/geoid12b/8539/tileindex_ak2012_valdez_m8539.gpkg
index_url_field=url
index_name_field=filename

# COPC LAZ 1.4, point format 6: needs the lazrs backend (CAPABILITY_LAZ);
# without it the rung records unavailable and the ladder climbs on.
point_compression=laz
point_formats=6

# Point coordinates: NAD83(2011) / UTM zone 6N (the index's srs field and
# each tile's compound WKT: EPSG 6335 + NAVD88 height 5703, metres).  A
# tile whose header CRS disagrees is refused (never cached).
source_crs=6335
vertical_unit=m
vertical_datum=NAVD88

# ASPRS classes gridded (2 = ground); withheld-flagged points dropped.
ground_classes=2
grid_resolution_m=1
native_resolution_m=1
min_points_per_cell=1
fill_radius_cells=3

# The surgical core (las-tile spec §2) and its seam feather (§4).
footprint_buffer_m=300
core_feather_m=60
# NOAA's S3 bucket: no politeness limit published; four connections.
fetch_slots=4

# Per-airport caps on the SURGICAL set (PAVD measured by lane lasidx154:
# see the report on #154).  Over either the rung is SKIPPED (unavailable,
# never no-coverage) and the ladder climbs on.
max_tiles_per_airport=16
max_bytes_per_airport=1500000000
keep_raw_las=true

# Declared accuracy (AeroMetric for STARR/FEMA): RMSEz 4.5 cm open terrain.
rmse_z_m=0.045
publication_date=2012

# The dataset's tile-index extent, measured from the GeoPackage
# (64 tiles, 2026-10-01): -146.4313..-146.0961 E, 61.0723..61.1957 N.
coverage_bbox=-146.44,61.07,-146.09,61.20

license=Public domain (NOAA OCM Digital Coast)
license_note=No use restriction published (NOAA OCM Digital Coast); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=FEMA 2012 Valdez, AK lidar (AeroMetric for STARR), via NOAA OCM Digital Coast

# A holder rung of the global ladder (us-holder-providers §1).
ladder_member=True
priority=90

enabled=True
