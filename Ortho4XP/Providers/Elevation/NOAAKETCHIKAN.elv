# 2014 FEMA lidar: Ketchikan, Alaska -- 3 ft (0.914 m) bare-earth DEM
# re-hosted by NOAA OCM Digital Coast (dataset 8522; lidar ID 8521) as
# ONE GeoTIFF behind an EPSG-named VRT.  Issue #154 (PAKT); spec
# docs/specs/us-holder-providers-spec.md §4; RULINGS 2026-09-30bm.
role=airport_inset

# Strategy: windowed /vsicurl reads out of NOAA's dataset VRT (compound
# CRS NAD83(2011) / Alaska zone 1 + NAVD88 height, metre).
access_strategy=direct_cog
cog_urls=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/AK_Ketchikan_FEMA_DEM_2014_8522/AK_Ketchikan_FEMA_DEM_2014_m8522_EPSG-6394.vrt

# Heights: NAVD88 (Geoid12A), METRES (metadata "Vertical units are
# meters"; the VRT's compound CRS declares metre).
vertical_unit=m
vertical_datum=NAVD88

native_resolution_m=0.9144

# The VRT extent (measured 2026-09-30): -131.890..-131.454 E,
# 55.290..55.518 N.
coverage_bbox=-131.90,55.28,-131.45,55.52

publication_date=2014
license=Public domain (NOAA OCM Digital Coast)
license_note=No use restriction published (NOAA OCM: "Access Constraints: None"); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=FEMA 2014 Ketchikan lidar, via NOAA OCM Digital Coast

ladder_member=True
priority=90
enabled=True
