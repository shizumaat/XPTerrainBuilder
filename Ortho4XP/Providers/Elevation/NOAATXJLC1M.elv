# 2017 TNRIS (StratMap) lidar: Jefferson, Liberty and Chambers counties,
# Texas -- 1 m bare-earth DEM re-hosted by NOAA OCM Digital Coast
# (dataset 9047; lidar ID 9040).  Issue #154 (KBMT); spec
# docs/specs/us-holder-providers-spec.md §4; RULINGS 2026-09-30bm.
role=airport_inset

# Strategy: windowed /vsicurl reads out of NOAA's dataset VRT (EPSG 26915,
# horizontal-only CRS).
access_strategy=direct_cog
cog_urls=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/TNRIS_JeffLibCham_DEM_2018_9047/TNRIS_JeffLibCham_DEM_2018_m9047_EPSG-26915.vrt
source_nodata=-9999

# Heights: NAVD88 (Geoid12b), METRES (metadata "Units - Meters"); the VRT
# CRS declares no vertical axis, so the unit is the metadata's, verified
# by value at KBMT 2026-09-30 (8.8 at the ARP, field 32 ft = 9.8 m).
vertical_unit=m
vertical_datum=NAVD88

native_resolution_m=1

# The VRT extent (measured 2026-09-30): -94.442..-93.778 E, 29.606..30.144 N.
coverage_bbox=-94.45,29.60,-93.77,30.15

publication_date=2018
license=Public domain (NOAA OCM Digital Coast)
license_note=No use restriction published (NOAA OCM: "Access Constraints: None"); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=Texas Natural Resources Information System (TNRIS) 2017 lidar, via NOAA OCM Digital Coast

ladder_member=True
priority=90
enabled=True
