# 2023 NOAA lidar: Alaska Coastal Communities (Dillingham/Aleknagik, Ekuk,
# Ekwok, Koliganek, Manokotak, New Stuyahok) -- 0.5 m bare-earth DEM on
# NOAA OCM Digital Coast (dataset 10425; lidar ID 10424).  Issue #154
# (PADL); spec docs/specs/us-holder-providers-spec.md §4; RULINGS
# 2026-09-30bm.
role=airport_inset

# Strategy: windowed /vsicurl reads out of NOAA's dataset VRT (compound
# CRS NAD83(2011) / UTM 4N + NAVD88 height, metre; 750 m tiles).
access_strategy=direct_cog
cog_urls=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/AK_CstalComms_DEM_2023_10425/AK_CstalComms_DEM_2023_m10425_EPSG-6333.vrt
source_nodata=-999999

# Heights: NAVD88 (GEOID12B), METRES (metadata; the VRT's compound CRS
# declares metre).
vertical_unit=m
vertical_datum=NAVD88

# 0.5 m source; the inset target floor is 0.5 m.
native_resolution_m=0.5

# The VRT extent (measured 2026-09-30): -159.111..-157.190 E,
# 58.761..59.756 N.
coverage_bbox=-159.12,58.75,-157.18,59.76

publication_date=2023
license=Public domain (NOAA OCM Digital Coast)
license_note=No use restriction published (NOAA OCM: "Access Constraints: None"); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=NOAA 2023 Alaska Coastal Communities lidar, via NOAA OCM Digital Coast

ladder_member=True
priority=90
enabled=True
