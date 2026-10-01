# Oregon DOGAMI statewide lidar bare-earth mosaic (Oregon Department of
# Geology and Mineral Industries).  Issue #154; spec
# docs/specs/us-holder-providers-spec.md §3.4 / §4; RULINGS 2026-09-30bm.
#
# One ImageServer mosaics every Oregon Lidar Consortium survey with the
# NEWEST on top (ZOrder = survey year, MosaicOperator First, descending):
# at KEUG the 2023 Willamette Valley South flight.  It replaces the six
# Oregon OLC NOAA re-hosts (RULINGS 2026-09-30bm §4).  No tile cache
# (exportTilesAllowed=false), so the box is CHUNKED through exportImage.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset
access_strategy=arcgis_export_image
export_url=https://gis.dogami.oregon.gov/arcgis/rest/services/lidar/DIGITAL_TERRAIN_MODEL_MOSAIC/ImageServer
# The request grid is laid in the service's own frame: NAD83(2011) Oregon
# GIC Lambert, INTERNATIONAL feet (pixelSizeX = 3 ft = 0.9144 m), so the
# server never reprojects.
source_epsg=6557
native_resolution_m=0.9144
# HEIGHTS IN INTERNATIONAL FEET (NAVD88).  Converted to metres by the
# engine's ONE vertical-unit site (the shared warp), not by a server-side
# renderingRule: the service lists no raster function but "None", the
# exported GeoTIFF declares no vertical CRS (so the .elv is the witness),
# and the raw and the x0.3048 rule answers agree to the float (measured
# 2026-09-30 at KEUG: 361.476 ft raw = 110.178 m rule).
vertical_unit=ft
vertical_datum=NAVD88
# MANDATORY (#155): an empty noData= answers 0.0 with no tag outside the
# mosaic -- a false sea level.  Every chunk's tag is verified.
nodata=-9999
# The service refuses a request above ~8 Mpx (scout hold154c); 6 Mpx per
# chunk (maxImageWidth/Height 120,000 -- no per-side limit binds).
max_request_px=6000000
# LERC on the wire: ~0.75 B/px against ~3.1 B/px for a LZW TIFF (measured
# 2026-09-30, 1 Mpx at KEUG).  The mosaic itself is stored LERC at
# CompressionTolerance 0.08 ft (serviceProperties); the export adds at
# most lerc_max_error (feet, the source unit).
export_format=lerc
lerc_max_error=0.01
# Judged BEFORE the first GET on the uncompressed size (4 B/px).
max_bytes_per_airport=400000000
# The service's full extent (EPSG:6557 -> 4326, measured 2026-09-30).
coverage_bbox=-124.84,41.70,-116.34,46.60
publication_date=2023
license=Oregon DOGAMI public lidar (no restriction published)
license_note=No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw); copyrightText "Oregon Department of Geology and Mineral Industries"
attribution=Oregon Department of Geology and Mineral Industries (DOGAMI), Oregon Lidar Consortium
# Joins the USGS3DEP ladder by resolution once the global assembly lands
# (spec §1); standalone below USGS3DEP (100).
ladder_member=True
priority=90
enabled=True
