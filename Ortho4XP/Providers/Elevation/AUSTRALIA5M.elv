# Geoscience Australia lidar digital elevation model, 5 metre.
#
# Bare-earth 5 m composite of ~236 lidar surveys (2001-2015, about
# 245,000 square kilometres: the populated coasts, Murray-Darling
# floodplains and town surveys -- NOT continental), served anonymously
# over an OGC Web Coverage Service on services.ga.gov.au.  Uses the
# generic wcs access strategy; GDAL's WCS driver handles this ArcGIS
# endpoint at protocol version 1.0.0 (verified live 2026-07-15).
# Airports outside the survey patchwork come back as windows of 0.0
# fill (see provider_fill_value below): a whole-window fill is recorded
# as no-coverage, a partial one is masked -- either way the base tier
# keeps the uncovered ground.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=AUS

access_strategy=wcs

wcs_service_url=https://services.ga.gov.au/gis/services/DEM_LiDAR_5m_2025/MapServer/WCSServer
wcs_version=1.0.0
wcs_coverage=1

# THE PROVIDER FILL (#1340): beyond each survey's extent the mosaic serves
# exactly 0.0, not nodata (YMML, YMEN: whole windows of 0; the GDAL band
# declares -32768, which never occurs).  WCS 1.0.0 offers no request
# parameter for a nodata answer and DescribeCoverage declares no null
# value (checked live 2026-10-26), so the fill is declared here: a large
# edge- or centre-connected region of exact 0.0 is masked as nodata
# (elevation_access/provider_fill.py).
provider_fill_value=0

# Native ground resolution of the source raster, in metres.
native_resolution_m=5

# Cheap pre-filter: continental Australia and Tasmania.
coverage_bbox=112.9,-43.7,153.7,-9.0

# Australian Height Datum (via AUSGeoid); horizontal GDA94.
vertical_datum=AHD
license=Creative Commons Attribution 4.0 (CC BY 4.0)
attribution=Commonwealth of Australia (Geoscience Australia)

priority=80

enabled=True
