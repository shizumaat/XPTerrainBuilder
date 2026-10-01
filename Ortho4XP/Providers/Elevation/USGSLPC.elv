# USGS 3DEP Lidar Point Clouds (LPC), gridded in-engine to a 1 m DTM.
# Issue #153; owner RULINGS 2026-09-30bl (1); the LAS-tile machinery of
# #130 (docs/specs/las-tile-lidar-provider-spec.md).
#
# The last lidar rung: where TNM lists the flight's LAZ point clouds but
# its Original Product Resolution DEM does not cover the airport.  The
# tiles are LAZ (compressed): the engine needs the lazrs backend
# (CAPABILITY_LAZ); without it the rung records unavailable and the
# ladder climbs on to 3 m / 10 m.
#
# Reached as USGS3DEP's ladder rung after USGSOPR.
role=airport_inset
access_strategy=las_tile_index

# The tile index is the TNM Access API listing of the LPC dataset over the
# SURGICAL core's envelope (aerodrome boundary + footprint_buffer_m).
index_format=tnm
index_url_template=https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Lidar Point Cloud (LPC)&bbox={west},{south},{east},{north}&outputFormat=JSON
tile_extensions=laz,las
point_compression=laz
# LAS 1.2 (formats 0-3) and LAS 1.4 (6-8) flights both appear in 3DEP.
point_formats=0,1,2,3,6,7,8

# Every project carries its own CRS: read per tile from its header
# (compound CRS -> the vertical unit; else the horizontal unit).
source_crs=from_header
vertical_unit=from_header
vertical_datum=NAVD88

ground_classes=2
grid_resolution_m=1
native_resolution_m=1
min_points_per_cell=1
fill_radius_cells=3

# The surgical core (spec §2) and its seam feather (spec §4); the rest of
# the inset box is the next seamless rung (two-layer inset).
footprint_buffer_m=300
core_feather_m=60
# rockyweb.usgs.gov serves ~0.1-0.2 MB/s per connection (measured
# 2026-10-01).
fetch_slots=4
# A USGS LPC tile is ~1 km and 40-120 MB: a large airport's core is 20-30
# tiles.  Over either cap the rung is SKIPPED (unavailable, never
# no-coverage) and the ladder climbs on.
max_tiles_per_airport=40
max_bytes_per_airport=3000000000
keep_raw_las=true

# Same regions as USGS3DEP.elv.
coverage_bbox=-125.0,24.0,-95.15,49.05
coverage_bbox=-95.25,48.9,-94.9,49.45
coverage_bbox=-95.15,24.0,-66.0,48.35
coverage_bbox=-180.0,51.0,-141.0,71.5
coverage_bbox=-141.0,54.5,-130.0,60.0
coverage_bbox=172.0,51.0,180.0,53.5
coverage_bbox=-161.0,18.5,-154.5,22.5
coverage_bbox=-68.0,17.5,-64.5,18.6
coverage_bbox=144.5,13.2,146.2,20.6
coverage_bbox=-171.2,-14.5,-169.4,-13.8

license=Public Domain (U.S. Geological Survey)
attribution=U.S. Geological Survey 3D Elevation Program (3DEP), Lidar Point Clouds

priority=84

enabled=True
