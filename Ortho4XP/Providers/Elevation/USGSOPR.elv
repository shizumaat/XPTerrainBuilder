# USGS 3DEP lidar DEMs at their ORIGINAL PRODUCT RESOLUTION (OPR).
# Issue #153; owner RULINGS 2026-09-30bl (1).
#
# Why this source: the #151 census found 51 US airports (all of Alaska's
# lidar airports -- PANC, PAFA, PAEI, PAJN, PAED -- plus KGEG, KGTF, KPUB,
# KGPT ...) where USGS holds QL1/QL2 lidar but publishes NO 1 m product.
# The same flights are listed by TNM as "Original Product Resolution"
# DEMs: per-project ~1 km GeoTIFF tiles, 0.5-1.5 m, each in its own CRS
# and HEIGHT UNIT (metres; or US survey / international feet, declared by
# a NAVD88-in-feet compound CRS or only implied by a State Plane foot
# CRS).  Grid, CRS and height unit are read from every file
# (source_units=from_source); heights in feet are converted to metres
# before the mosaic.
#
# Reached as USGS3DEP's ladder rung (resolution_ladder=...|provider:
# USGSOPR), after USGS 1 m and Pitkin County, before the 1/9 and 1/3
# arc-second seamless layers.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset
access_strategy=tnm_cog

# The TNM Access API listing of the OPR dataset over the inset box (paged:
# KGEG lists 97 tiles).
discovery_url_template=https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Original Product Resolution (OPR) Digital Elevation Model (DEM)&bbox={west},{south},{east},{north}&outputFormat=JSON

# Nominal posting (orders the rung beside the other 1 m rungs and sets the
# warp target); the record carries what the FILES say (native_resolution_m
# = the coarsest contributing product, native_resolution_range_m).
native_resolution_m=1
source_units=from_source
# The OPR dataset also lists the 5 m Alaska IFSAR DTMs (2010) beside the
# lidar: a product coarser than this is not lidar-class and is left out of
# the mosaic (recorded as sources_excluded_too_coarse); the seamless rungs
# below carry those areas.  Measured 2026-10-01 over the 51 census
# airports: lidar products post 0.5-1.5 m (MS Coastal 4 ftUS = 1.22 m).
max_source_resolution_m=2

# Judged like a surgical lidar core: DELIVERED only when it covers the
# AIRPORT (INSET_MIN_AIRPORT_COVER_FRAC of the aerodrome boundary box),
# else the ladder moves on (to the point clouds, then 3 m / 10 m).
ladder_judge=airport_cover

# Never a whole-tile elevation_level overlay: a 1 x 1 degree tile is
# thousands of ~1 km OPR tiles, many stripped (read whole).
supports_wide_area=false

# Same regions as USGS3DEP.elv (3DEP is US-only, RULINGS 2026-09-16c).
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

vertical_datum=NAVD88
license=Public Domain (U.S. Geological Survey)
attribution=U.S. Geological Survey 3D Elevation Program (3DEP), Original Product Resolution DEMs

# A RUNG of USGS3DEP's ladder, never ranked on its own in 'auto'
# (pinning airport_elevation_providers=USGSOPR still works).  Priority
# only orders it among pinned providers.
ladder_only=true
priority=85

enabled=True
