# Polar Geospatial Center ArcticDEM v4.1 2 m DATED STRIPS (photogrammetric
# surface models from Maxar stereo pairs), served as Cloud-Optimized
# GeoTIFFs on the AWS open-data registry and listed by PGC's STAC API.
#
# Declarative elevation-inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
# Strips, not the mosaic: the v4.1 mosaic (2023) predates recent
# construction (Nuuk's new runway, opened 2024, is only in the strips).

# Detail tier: fetched only inside airport bounding boxes.
role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc).  ArcticDEM covers all land
# north of 60 N plus Alaska and Kamchatka.  National lidar providers rank
# above it where they exist (HRDEM, NORWAY1M, SWEDEN1M, FINLAND2M,
# ISLANDSDEM ...); it ranks above the global Copernicus inset.
country=GRL,CAN,USA,RUS,NOR,SJM,SWE,FIN,ISL,FRO

# Newest-valid-first composite of dated strips with their quality bitmask
# (src/elevation_access/strategies/stac_dated_strips.py).
access_strategy=stac_dated_strips
discovery_url_template=https://stac.pgc.umn.edu/api/v1/search
collections=arcticdem-strips-s2s041-2m
strip_asset_key=dem
strip_mask_asset_key=mask
search_limit=100
# Strips read per airport box at most, newest first; the composite stops
# earlier once every cell is filled.
max_strips=40

native_resolution_m=2
# DECLARED DEM CLASS (#1929): satellite stereo DSM, vertical error ~1-4 m,
# strips that may predate the airport -- "fine", not lidar, whatever the
# 2 m pixel says (the pixel rule would class it lidar: the old-DEM witness
# never fired, grade_disagree_m took the lidar 1.5 m, runway_profile read
# CASE_LIDAR).
dem_class=fine

# North of 60 N, all longitudes; Alaska south of 60 N; Kamchatka.
coverage_bbox=-180.0,60.0,180.0,84.0
coverage_bbox=-180.0,51.0,-129.0,60.0
coverage_bbox=155.0,50.5,166.0,60.0

# Heights are WGS84 ELLIPSOIDAL.  geoid_shift reduces every cell to EGM2008
# after the fetch (src/elevation_access/geoid_shift.py; Greenland's
# undulation is about +25..+35 m), so the inset matches the base DEM.
geoid_shift=egm2008
vertical_datum=EGM2008 (reduced from WGS84 ellipsoidal heights)

# A SURFACE model: buildings and snow are in it.  The same post-fetch pass
# Copernicus uses replaces mapped building footprints by ground.
surface_model_building_masking=True
footprint_mask_buffer_m=6

license=Creative Commons Attribution 4.0 (CC BY 4.0)
attribution=ArcticDEM, Polar Geospatial Center, University of Minnesota (DEMs provided by the Polar Geospatial Center under NSF-OPP awards 1043681, 1559691, 1542736, 1810976 and 2129685)

# Below every national lidar provider (80-100), above COPERNICUSGLO30 (1).
priority=50

enabled=True
