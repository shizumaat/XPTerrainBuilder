# North Carolina Statewide Lidar Phase 3 (2024), 3.125 ft (0.9525 m)
# bare-earth DEM, re-hosted unchanged by NOAA OCM Digital Coast on its
# anonymous S3 bucket (the state's own sdd.nc.gov needs an Azure B2C
# login).  Issue #154 (17 NC HOLDER airports: KGSO KRDU KFAY KPOB KTTA
# KSOP KBUY KTDF KHBI KSIF KRCZ KHRJ KSCR KHFF KFBG W77 43A); spec
# docs/specs/us-holder-providers-spec.md §3.1/§4; RULINGS 2026-09-30bm.
role=airport_inset

# Strategy: windowed /vsicurl reads straight out of NOAA's dataset VRTs
# (44,813 Float32 COG tiles, ~5.2 MB each).  NOAA split the tiles over TWO
# EPSG-named VRTs: the first declares the horizontal CRS only, the second
# (_1) a compound NC ftUS + "NAVD88 height (ftUS)" CRS.  Cold open
# measured 2026-09-30: 3.9 s + 1.9 s (13.3 MB + 6.7 MB of VRT XML).
access_strategy=direct_cog
cog_urls=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NC_phase3_2024_15636/NC_phase3_2024_m15636_EPSG-6543.vrt,https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NC_phase3_2024_15636/NC_phase3_2024_m15636_EPSG-6543_1.vrt
source_nodata=-999999

# HEIGHTS ARE US SURVEY FEET (metadata: "vertical datum of NAVD88
# (GEOID18), Feet"; the _1 VRT's CRS declares ftUS).  Verified by value
# at KRDU 2026-09-30: 419 at the ARP, field 435 ft -- metres would put
# Raleigh at 419 m.  The shared warp converts (spec §2).
vertical_unit=ftUS
vertical_datum=NAVD88

native_resolution_m=0.9525

# The two VRTs' union extent (measured 2026-09-30):
# -80.183..-78.256 E, 34.624..36.551 N.
coverage_bbox=-80.19,34.62,-78.25,36.56

publication_date=2024
license=CC0 1.0
license_note=Published by NC Emergency Management / NOAA OCM Digital Coast with no use restriction (CC0 1.0); not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)
attribution=North Carolina Emergency Management, NC Statewide Lidar Phase 3 (2024), via NOAA OCM Digital Coast

ladder_member=True
priority=90
enabled=True
