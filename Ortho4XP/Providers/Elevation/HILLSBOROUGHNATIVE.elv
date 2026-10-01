# Hillsborough County, Florida -- the 2017 SWFWMD / Dewberry lidar DEM at
# its NATIVE 2.5 ft posting, State Plane Florida West.  Issue #154; spec
# docs/specs/us-holder-providers-spec.md §3.4 / §4; RULINGS 2026-09-30bm.
# Airports: KTPA KMCF KVDF KPCM.
#
# The county serves the same DEM twice: a bilinear-resampled WGS84 LERC
# tile cache in metres (HILLSBOROUGH1M, 1.06 m) and this native image
# service, which has no tile cache and is asked through exportImage.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset
access_strategy=arcgis_export_image
export_url=https://maps.hillsboroughcounty.org/arcgis/rest/services/initial_install/n767demmosaic/ImageServer
# NAD83(2011) / Florida West (ftUS); pixel 2.5 ftUS = 0.762 m.
source_epsg=6443
native_resolution_m=0.762
# HEIGHTS IN US SURVEY FEET, NAVD88 (GEOID12B) -- the service declares
# vcsWkid 6360 (NAVD88 height ftUS); the exported GeoTIFF carries no
# vertical CRS, so the .elv is the witness.
vertical_unit=ftUS
vertical_datum=NAVD88
# MANDATORY (#155): the service declares no noDataValue of its own.
nodata=-9999
# maxImageWidth 15,000 / maxImageHeight 4,100 (service JSON, 2026-09-30):
# a 3000 x 4200 request answers "exceeds the size limit".
max_request_px=6000000
max_request_width_px=15000
max_request_height_px=4100
export_format=lerc
lerc_max_error=0.01
# Judged BEFORE the first GET on the UNCOMPRESSED size (4 B/px).  KTPA's
# box at 0.762 m is ~104 Mpx = 418 MB by that estimate (it refused at the
# 400 MB default, measured 2026-09-30) while LERC moves ~0.75 B/px on the
# wire (~80 MB).  KMCF's box is longer (3,489 m runway).
max_bytes_per_airport=800000000
# The service's full extent (EPSG:6443 -> 4326, measured 2026-09-30).
coverage_bbox=-82.66,27.63,-82.04,28.19
publication_date=2017-03
license=Hillsborough County GIS / SWFWMD public lidar (no restriction published)
license_note=No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw); copyrightText "Southwest Florida Water Management District (SWFWMD), Mapping & GIS"; hydro-enforced bare earth (3D breaklines)
attribution=Southwest Florida Water Management District / Hillsborough County -- 2017 lidar (Dewberry)
ladder_member=True
priority=90
enabled=True
