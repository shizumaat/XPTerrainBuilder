# 2010 USACE lidar: Columbia River (ID, MT, OR, WA) -- 1 m bare-earth DEM
# re-hosted by NOAA OCM Digital Coast (dataset 8562).  Issue #154 (KAST,
# for the case the DOGAMI statewide mosaic does not serve it); spec
# docs/specs/us-holder-providers-spec.md §4; RULINGS 2026-09-30bm.
role=airport_inset

# Strategy: windowed /vsicurl reads out of NOAA's UTM 10N dataset VRT
# (horizontal-only CRS EPSG 26910).  The dataset's UTM 11N half
# (_EPSG-26911.vrt, eastern WA/ID) serves no HOLDER airport and is not
# listed.
access_strategy=direct_cog
cog_urls=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/USACE_Columbia_River_DEM_2010_8562/USACE_Columbia_River_DEM_2010_m8562_EPSG-26910.vrt

# Heights: NAVD88 (Geoid09), METRES (metadata "NAVD88 (Geoid 09) heights
# in meters"); the VRT CRS declares no vertical axis.
vertical_unit=m
vertical_datum=NAVD88

native_resolution_m=1

# The UTM 10N VRT extent (measured 2026-09-30): -124.126..-119.969 E,
# 45.315..46.384 N.
coverage_bbox=-124.13,45.31,-119.96,46.39

publication_date=2010
license=Public domain (NOAA OCM Digital Coast)
license_note=No use restriction published (NOAA OCM: "Access Constraints: None"); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=USACE 2010 Columbia River lidar, via NOAA OCM Digital Coast

ladder_member=True
priority=90
enabled=True
