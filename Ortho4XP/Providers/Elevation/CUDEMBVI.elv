# NOAA NCEI Continuously Updated DEM (CUDEM), ninth arc-second US Virgin
# Islands topobathymetric tiles -- as the TERRAIN inset of the BRITISH
# Virgin Islands.
#
# The same catalog as CUDEMUSVI.elv (role=bathymetry, which no terrain
# selection reads): its tiles reach east over Tortola, Beef Island,
# Virgin Gorda and Anegada, where no national survey is public and the
# alternative is the 30 m global model.  This sibling serves only BVI
# airports (country gate below), so USGS3DEP keeps the US islands.

role=airport_inset

# apt.dat's 1302 country rows: TUPJ and TUPA read VGB, TUPW reads GBR
# (state "British Virgin Islands").  The GBR providers' boxes stop in
# Europe, and this box stops in the Virgin Islands.
country=VGB,GBR
access_strategy=static_stac

catalog_url=https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NCEI_ninth_Topobathy_USVI_9529/stac/catalog.json

# Ninth arc-second is ~3.4 m at these latitudes.
native_resolution_m=3.4

# The British islands only: Jost Van Dyke and Tortola east to Anegada.
coverage_bbox=-64.85,18.30,-64.25,18.78

# A local tidal datum (approximately mean sea level), not NAVD88: the
# same mean-sea-level sense as the islands' runway heights.
vertical_datum=Local Tidal (approx MSL)
license=Public Domain (NOAA NCEI)
attribution=NOAA NCEI Continuously Updated DEM (CUDEM)

# Below USGS3DEP (100), which serves the US Virgin Islands.
priority=90

enabled=True
