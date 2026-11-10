# Norwegian Polar Institute (Norsk Polarinstitutt) S0 Terrengmodell,
# REGIONAL models ("Delmodell"): bare-earth terrain models of Svalbard,
# 5 m (2.5 m around Longyearbyen and Sveagruva, 2 m on Bjornoya),
# generated from stereo models of the 2008-2012 aerial survey (2021 for
# one block); NPI quotes a standard deviation of about 2-5 m outside
# glaciers.  Dataset doi:10.21334/npolar.2014.dce53a47.
#
# Declarative elevation-inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
#
# Published as one deflated zip per production block (one GeoTIFF each,
# tiled LZW Float32, ETRS89 / UTM 33N or 35N) at
# https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/ .
# The host answers ranged requests, so each block is read in place
# through /vsizip//vsicurl/ -- but the members are DEFLATED, so GDAL
# streams a block up to the window it needs (a 5 m block is 1-1455 MB):
# the footprints below keep every airport to the blocks it touches.
# Not used: the 20 m / 50 m mosaics (Mosaikk/NP_S0_DTM20.zip): outside the
# stereo blocks they are contour-derived (NPI: std. dev. ~25 m), below
# ARCTICDEM2M, which already serves Svalbard.

# Detail tier: fetched only inside airport bounding boxes.
role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc).  Svalbard (SJM; an
# apt.dat row may say NOR); the coverage boxes keep it to the archipelago.
country=SJM,NOR

access_strategy=direct_cog

native_resolution_m=5
# DECLARED DEM CLASS (#1929): photogrammetric DTM, 2-5 m standard
# deviation -- "fine", not lidar.
dem_class=fine

# Svalbard with Bjornoya and Hopen; the cog_source footprints below are
# the precise coverage.
coverage_bbox=9.4,74.0,34.0,81.0

# Heights are ORTHOMETRIC (mean sea level), not ellipsoidal: measured
# 2026-11-10 against COPERNICUSGLO30BASE (EGM2008) over the 2011
# Longyearbyen block, 136,942 cells: median +0.51 m, -0.07 m on terrain
# 2-40 m, sea-level cells read +0.52 m (WGS84 ellipsoidal heights would
# read ~+32 m here).  No geoid shift; the GeoTIFFs carry no vertical CRS.
vertical_datum=Mean sea level (NPI Svalbard; within ~0.5 m of EGM2008)

license=Creative Commons Attribution 4.0 (CC BY 4.0)
attribution=Norwegian Polar Institute, S0 Terrain model Svalbard (doi:10.21334/npolar.2014.dce53a47)

# Above ARCTICDEM2M (50: a 2 m satellite DSM, buildings and snow in it)
# in Svalbard, below the national lidar providers (80-100).
priority=60

enabled=True

# FOOTPRINTED SOURCES (strategies/direct_cog.py, cog_source): one line per
# data island of each block, W,S,E,N boxes on a 0.2 x 0.1 degree grid
# from a 100 m sampling of the block's valid cells (2026-11-10).  Coarse
# blocks first, then oldest first: the warp lets LATER inputs win, so the
# finest, newest block is read last.  A new NPI block is a new line here.
# NP_S0_DTM5_1990_00000_33.zip: 5 m, 1990 imagery, 1 footprint box(es)
cog_source=10.60,79.70,11.00,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_1990_00000_33.zip/NP_S0_DTM5_1990_00000_33/S0_DTM5_1990_00000_33.tif
# NP_S0_DTM5_2008_13652_33.zip: 5 m, 2008 imagery, 3 footprint box(es)
cog_source=13.20,77.90,14.60,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13652_33.zip/NP_S0_DTM5_2008_13652_33/S0_DTM5_2008_13652_33.tif
cog_source=13.40,78.00,14.20,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13652_33.zip/NP_S0_DTM5_2008_13652_33/S0_DTM5_2008_13652_33.tif
cog_source=13.40,77.70,15.00,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13652_33.zip/NP_S0_DTM5_2008_13652_33/S0_DTM5_2008_13652_33.tif
# NP_S0_DTM5_2008_13657_35.zip: 5 m, 2008 imagery, 1 footprint box(es)
cog_source=24.80,76.40,25.60,76.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13657_35.zip/NP_S0_DTM5_2008_13657_35/S0_DTM5_2008_13657_35.tif
# NP_S0_DTM5_2008_13659_33.zip: 5 m, 2008 imagery, 4 footprint box(es)
cog_source=20.60,79.10,21.00,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13659_33.zip/NP_S0_DTM5_2008_13659_33/S0_DTM5_2008_13659_33.tif
cog_source=20.60,79.00,22.00,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13659_33.zip/NP_S0_DTM5_2008_13659_33/S0_DTM5_2008_13659_33.tif
cog_source=20.80,78.90,22.00,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13659_33.zip/NP_S0_DTM5_2008_13659_33/S0_DTM5_2008_13659_33.tif
cog_source=21.00,78.80,21.80,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13659_33.zip/NP_S0_DTM5_2008_13659_33/S0_DTM5_2008_13659_33.tif
# NP_S0_DTM5_2008_13660_33.zip: 5 m, 2008 imagery, 9 footprint box(es)
cog_source=9.80,78.80,11.40,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=10.00,78.90,11.20,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=10.00,78.70,11.60,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=10.20,78.60,11.80,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=10.60,78.50,12.00,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=10.80,78.40,12.20,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=11.00,78.30,12.40,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=11.20,78.20,12.60,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
cog_source=11.40,78.10,12.60,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13660_33.zip/NP_S0_DTM5_2008_13660_33/S0_DTM5_2008_13660_33.tif
# NP_S0_DTM5_2008_13666_35.zip: 5 m, 2008 imagery, 8 footprint box(es)
cog_source=19.80,78.50,20.40,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=21.00,77.30,22.60,77.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=21.00,77.10,23.20,77.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=21.00,77.20,23.40,77.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=21.20,77.00,22.40,77.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=22.60,77.00,23.00,77.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=23.00,77.30,23.40,77.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
cog_source=24.80,77.70,25.40,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13666_35.zip/NP_S0_DTM5_2008_13666_35/S0_DTM5_2008_13666_35.tif
# NP_S0_DTM5_2008_13667_35.zip: 5 m, 2008 imagery, 2 footprint box(es)
cog_source=20.40,79.30,21.40,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13667_35.zip/NP_S0_DTM5_2008_13667_35/S0_DTM5_2008_13667_35.tif
cog_source=20.80,79.20,21.40,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2008_13667_35.zip/NP_S0_DTM5_2008_13667_35/S0_DTM5_2008_13667_35.tif
# NP_S0_DTM5_2009_13822_33.zip: 5 m, 2009 imagery, 22 footprint box(es)
cog_source=10.20,79.70,11.20,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.40,79.60,11.40,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.60,79.80,10.80,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.60,79.50,11.40,79.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.60,79.40,11.80,79.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.60,79.30,13.20,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.60,79.20,13.40,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=10.80,79.10,14.00,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.00,79.00,14.20,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.20,78.70,14.60,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.40,78.80,14.60,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.40,78.60,14.80,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.60,78.90,14.40,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=11.80,78.50,14.80,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=12.00,78.40,15.00,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=12.40,78.30,15.00,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=12.60,78.20,14.60,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=12.80,78.10,14.00,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=15.80,78.70,16.60,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=15.80,78.60,16.80,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=16.00,78.80,16.40,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
cog_source=16.00,78.50,16.60,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13822_33.zip/NP_S0_DTM5_2009_13822_33/S0_DTM5_2009_13822_33.tif
# NP_S0_DTM5_2009_13824_33.zip: 5 m, 2009 imagery, 3 footprint box(es)
cog_source=16.80,78.30,18.40,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13824_33.zip/NP_S0_DTM5_2009_13824_33/S0_DTM5_2009_13824_33.tif
cog_source=17.00,78.40,18.00,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13824_33.zip/NP_S0_DTM5_2009_13824_33/S0_DTM5_2009_13824_33.tif
cog_source=17.20,78.20,18.40,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13824_33.zip/NP_S0_DTM5_2009_13824_33/S0_DTM5_2009_13824_33.tif
# NP_S0_DTM5_2009_13827_35.zip: 5 m, 2009 imagery, 5 footprint box(es)
cog_source=21.20,77.10,21.40,77.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13827_35.zip/NP_S0_DTM5_2009_13827_35/S0_DTM5_2009_13827_35.tif
cog_source=21.20,76.90,22.60,77.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13827_35.zip/NP_S0_DTM5_2009_13827_35/S0_DTM5_2009_13827_35.tif
cog_source=21.20,77.00,23.00,77.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13827_35.zip/NP_S0_DTM5_2009_13827_35/S0_DTM5_2009_13827_35.tif
cog_source=21.40,76.80,22.20,76.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13827_35.zip/NP_S0_DTM5_2009_13827_35/S0_DTM5_2009_13827_35.tif
cog_source=22.20,77.10,22.80,77.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13827_35.zip/NP_S0_DTM5_2009_13827_35/S0_DTM5_2009_13827_35.tif
# NP_S0_DTM5_2009_13833_33.zip: 5 m, 2009 imagery, 5 footprint box(es)
cog_source=16.00,78.50,18.20,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13833_33.zip/NP_S0_DTM5_2009_13833_33/S0_DTM5_2009_13833_33.tif
cog_source=16.00,78.40,18.40,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13833_33.zip/NP_S0_DTM5_2009_13833_33/S0_DTM5_2009_13833_33.tif
cog_source=16.40,78.30,17.20,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13833_33.zip/NP_S0_DTM5_2009_13833_33/S0_DTM5_2009_13833_33.tif
cog_source=16.40,78.60,17.40,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13833_33.zip/NP_S0_DTM5_2009_13833_33/S0_DTM5_2009_13833_33.tif
cog_source=17.80,78.30,18.40,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13833_33.zip/NP_S0_DTM5_2009_13833_33/S0_DTM5_2009_13833_33.tif
# NP_S0_DTM5_2009_13835_33.zip: 5 m, 2009 imagery, 6 footprint box(es)
cog_source=15.20,78.20,17.60,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
cog_source=15.40,78.30,17.40,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
cog_source=15.40,78.10,17.60,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
cog_source=15.80,78.00,17.40,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
cog_source=16.20,77.90,17.60,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
cog_source=16.60,77.80,17.00,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2009_13835_33.zip/NP_S0_DTM5_2009_13835_33/S0_DTM5_2009_13835_33.tif
# NP_S0_DTM5_2010_13821_35.zip: 5 m, 2010 imagery, 8 footprint box(es)
cog_source=26.00,78.80,27.00,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=26.00,78.70,27.20,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=26.40,78.60,27.40,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=27.60,78.80,30.00,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=27.80,78.70,28.20,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=27.80,78.90,30.00,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=28.40,78.70,29.00,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
cog_source=28.40,79.00,29.00,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13821_35.zip/NP_S0_DTM5_2010_13821_35/S0_DTM5_2010_13821_35.tif
# NP_S0_DTM5_2010_13826_33.zip: 5 m, 2010 imagery, 5 footprint box(es)
cog_source=15.20,76.70,17.40,77.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13826_33.zip/NP_S0_DTM5_2010_13826_33/S0_DTM5_2010_13826_33.tif
cog_source=15.80,76.60,17.40,76.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13826_33.zip/NP_S0_DTM5_2010_13826_33/S0_DTM5_2010_13826_33.tif
cog_source=16.00,76.50,17.40,76.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13826_33.zip/NP_S0_DTM5_2010_13826_33/S0_DTM5_2010_13826_33.tif
cog_source=16.20,76.40,17.00,76.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13826_33.zip/NP_S0_DTM5_2010_13826_33/S0_DTM5_2010_13826_33.tif
cog_source=16.40,77.00,17.60,77.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13826_33.zip/NP_S0_DTM5_2010_13826_33/S0_DTM5_2010_13826_33.tif
# NP_S0_DTM5_2010_13828_33.zip: 5 m, 2010 imagery, 2 footprint box(es)
cog_source=11.20,78.90,12.40,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13828_33.zip/NP_S0_DTM5_2010_13828_33/S0_DTM5_2010_13828_33.tif
cog_source=11.20,78.80,12.60,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13828_33.zip/NP_S0_DTM5_2010_13828_33/S0_DTM5_2010_13828_33.tif
# NP_S0_DTM5_2010_13832_35.zip: 5 m, 2010 imagery, 16 footprint box(es)
cog_source=17.40,80.10,22.40,80.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=17.60,80.00,22.40,80.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=17.80,80.30,21.80,80.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=17.80,80.20,22.20,80.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=17.80,79.80,22.40,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=17.80,79.90,22.60,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=18.00,79.70,21.80,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=18.60,79.60,19.00,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=18.60,80.40,20.80,80.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=19.20,79.60,20.20,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=19.40,80.60,20.00,80.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=19.40,80.50,21.40,80.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=20.00,80.80,20.80,80.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=20.00,80.70,21.60,80.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=20.20,80.60,21.80,80.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
cog_source=21.20,80.40,21.80,80.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13832_35.zip/NP_S0_DTM5_2010_13832_35/S0_DTM5_2010_13832_35.tif
# NP_S0_DTM5_2010_13836_33.zip: 5 m, 2010 imagery, 5 footprint box(es)
cog_source=13.60,78.10,14.60,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13836_33.zip/NP_S0_DTM5_2010_13836_33/S0_DTM5_2010_13836_33.tif
cog_source=13.60,78.00,15.00,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13836_33.zip/NP_S0_DTM5_2010_13836_33/S0_DTM5_2010_13836_33.tif
cog_source=14.00,77.90,15.20,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13836_33.zip/NP_S0_DTM5_2010_13836_33/S0_DTM5_2010_13836_33.tif
cog_source=14.40,77.80,15.40,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13836_33.zip/NP_S0_DTM5_2010_13836_33/S0_DTM5_2010_13836_33.tif
cog_source=14.80,77.70,15.20,77.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13836_33.zip/NP_S0_DTM5_2010_13836_33/S0_DTM5_2010_13836_33.tif
# NP_S0_DTM5_2010_13918_33.zip: 5 m, 2010 imagery, 10 footprint box(es)
cog_source=13.00,79.80,15.40,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=13.20,79.90,14.20,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=13.20,79.70,15.60,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=13.40,79.60,15.60,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=13.60,79.40,15.80,79.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=13.80,79.30,15.80,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=14.20,80.00,14.80,80.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=14.20,79.20,16.00,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=14.40,79.90,14.60,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
cog_source=14.40,79.10,15.40,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13918_33.zip/NP_S0_DTM5_2010_13918_33/S0_DTM5_2010_13918_33.tif
# NP_S0_DTM5_2010_13920_35.zip: 5 m, 2010 imagery, 14 footprint box(es)
cog_source=19.80,78.50,22.40,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=19.80,78.40,22.60,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.20,78.30,22.60,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.20,78.10,23.40,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.40,78.00,23.60,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.40,77.40,23.80,77.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.40,77.50,24.20,77.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.40,77.60,24.60,77.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.60,78.60,22.00,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.80,77.70,24.60,77.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=20.80,77.90,24.60,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=21.00,77.80,24.60,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=22.00,77.30,23.60,77.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
cog_source=22.20,77.20,23.20,77.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13920_35.zip/NP_S0_DTM5_2010_13920_35/S0_DTM5_2010_13920_35.tif
# NP_S0_DTM5_2010_13922_33.zip: 5 m, 2010 imagery, 10 footprint box(es)
cog_source=15.40,79.90,17.80,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.40,79.70,18.20,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.40,79.60,19.00,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.60,80.00,17.00,80.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.60,79.40,19.00,79.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.60,79.30,19.20,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.80,79.10,18.00,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=15.80,79.20,19.00,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=16.60,79.00,17.80,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
cog_source=16.80,78.90,17.80,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13922_33.zip/NP_S0_DTM5_2010_13922_33/S0_DTM5_2010_13922_33.tif
# NP_S0_DTM5_2010_13923_33.zip: 5 m, 2010 imagery, 2 footprint box(es)
cog_source=14.80,77.90,15.40,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13923_33.zip/NP_S0_DTM5_2010_13923_33/S0_DTM5_2010_13923_33.tif
cog_source=15.20,77.80,15.60,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2010_13923_33.zip/NP_S0_DTM5_2010_13923_33/S0_DTM5_2010_13923_33.tif
# NP_S0_DTM5_2011_13820_35.zip: 5 m, 2011 imagery, 5 footprint box(es)
cog_source=31.00,80.00,33.00,80.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13820_35.zip/NP_S0_DTM5_2011_13820_35/S0_DTM5_2011_13820_35.tif
cog_source=31.00,80.10,34.00,80.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13820_35.zip/NP_S0_DTM5_2011_13820_35/S0_DTM5_2011_13820_35.tif
cog_source=31.20,80.20,33.80,80.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13820_35.zip/NP_S0_DTM5_2011_13820_35/S0_DTM5_2011_13820_35.tif
cog_source=31.40,79.90,31.60,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13820_35.zip/NP_S0_DTM5_2011_13820_35/S0_DTM5_2011_13820_35.tif
cog_source=32.40,80.30,33.60,80.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13820_35.zip/NP_S0_DTM5_2011_13820_35/S0_DTM5_2011_13820_35.tif
# NP_S0_DTM5_2011_13831_35.zip: 5 m, 2011 imagery, 19 footprint box(es)
cog_source=19.40,79.50,26.60,79.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=19.40,79.60,27.20,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=19.80,79.40,26.20,79.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=20.20,79.70,27.60,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=20.40,79.30,26.00,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=21.60,79.80,27.80,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.00,80.30,25.20,80.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.00,80.20,26.60,80.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.00,80.10,28.60,80.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.20,80.40,25.20,80.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.20,79.90,28.00,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.20,80.00,28.60,80.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=22.40,80.50,23.40,80.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=23.60,80.50,24.40,80.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=24.60,80.60,25.40,80.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=25.00,79.20,25.60,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=25.40,80.30,26.20,80.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=25.40,80.40,26.60,80.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
cog_source=26.00,80.50,26.40,80.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_13831_35.zip/NP_S0_DTM5_2011_13831_35/S0_DTM5_2011_13831_35.tif
# NP_S0_DTM5_2011_25160_33.zip: 5 m, 2011 imagery, 15 footprint box(es)
cog_source=10.60,79.80,13.40,79.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=10.60,79.70,13.60,79.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=11.00,79.90,12.20,80.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=11.00,79.50,13.80,79.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=11.20,79.40,14.00,79.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=11.60,79.30,14.40,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=13.00,79.20,14.60,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=13.20,79.10,16.20,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=13.80,79.00,16.40,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=14.00,78.90,16.60,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=14.20,78.80,16.40,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=14.40,78.60,16.20,78.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=14.60,78.50,16.40,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=15.00,78.40,16.20,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
cog_source=15.20,79.20,16.00,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25160_33.zip/NP_S0_DTM5_2011_25160_33/S0_DTM5_2011_25160_33.tif
# NP_S0_DTM5_2011_25161_33.zip: 5 m, 2011 imagery, 14 footprint box(es)
cog_source=16.00,79.10,16.80,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=16.00,79.00,17.00,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=16.20,78.90,21.20,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=16.20,78.70,21.60,78.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=16.40,78.60,21.60,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=17.20,78.50,18.20,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=17.60,79.10,20.80,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=17.60,79.00,21.00,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=18.00,79.20,20.40,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=18.80,79.50,19.40,79.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=18.80,78.40,19.80,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=18.80,78.50,20.20,78.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=19.00,79.40,20.20,79.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
cog_source=19.00,79.30,20.40,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25161_33.zip/NP_S0_DTM5_2011_25161_33/S0_DTM5_2011_25161_33.tif
# NP_S0_DTM5_2011_25162_33.zip: 5 m, 2011 imagery, 8 footprint box(es)
cog_source=14.40,78.10,16.00,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=14.40,78.00,16.40,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=14.80,77.90,16.80,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=15.00,78.20,15.60,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=15.20,77.80,16.80,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=17.00,78.10,17.80,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=17.00,78.00,18.00,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
cog_source=17.20,77.90,17.60,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25162_33.zip/NP_S0_DTM5_2011_25162_33/S0_DTM5_2011_25162_33.tif
# NP_S0_DTM5_2011_25163_33.zip: 5 m, 2011 imagery, 11 footprint box(es)
cog_source=13.60,77.30,17.80,77.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=13.60,77.50,18.00,77.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.00,77.20,17.80,77.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.00,77.60,18.20,77.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.20,77.10,17.60,77.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.20,77.70,18.20,77.80|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.40,77.00,17.60,77.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=14.80,76.90,16.60,77.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=15.40,77.80,18.20,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=17.00,77.90,18.20,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
cog_source=17.40,78.00,18.40,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2011_25163_33.zip/NP_S0_DTM5_2011_25163_33/S0_DTM5_2011_25163_33.tif
# NP_S0_DTM5_2012_25235_33.zip: 5 m, 2012 imagery, 9 footprint box(es)
cog_source=17.40,78.10,19.20,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=17.40,78.20,19.40,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=17.60,77.40,18.60,77.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=17.80,77.60,18.80,77.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=18.00,77.70,18.80,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=18.00,78.50,19.00,78.70|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=18.00,77.90,19.20,78.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=18.00,78.40,19.20,78.50|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
cog_source=18.20,78.30,19.20,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25235_33.zip/NP_S0_DTM5_2012_25235_33/S0_DTM5_2012_25235_33.tif
# NP_S0_DTM5_2012_25236_35.zip: 5 m, 2012 imagery, 3 footprint box(es)
cog_source=22.40,79.10,24.40,79.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25236_35.zip/NP_S0_DTM5_2012_25236_35/S0_DTM5_2012_25236_35.tif
cog_source=22.40,79.30,25.20,79.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25236_35.zip/NP_S0_DTM5_2012_25236_35/S0_DTM5_2012_25236_35.tif
cog_source=22.40,79.20,25.40,79.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25236_35.zip/NP_S0_DTM5_2012_25236_35/S0_DTM5_2012_25236_35.tif
# NP_S0_DTM5_2012_25238_35.zip: 5 m, 2012 imagery, 2 footprint box(es)
cog_source=29.60,78.90,30.80,79.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25238_35.zip/NP_S0_DTM5_2012_25238_35/S0_DTM5_2012_25238_35.tif
cog_source=29.80,79.00,30.80,79.10|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2012_25238_35.zip/NP_S0_DTM5_2012_25238_35/S0_DTM5_2012_25238_35.tif
# NP_S0_DTM5_2021_00000_33.zip: 5 m, 2021 imagery, 2 footprint box(es)
cog_source=17.60,78.00,18.60,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2021_00000_33.zip/NP_S0_DTM5_2021_00000_33/S0_DTM5_2021_00000_33.tif
cog_source=18.00,78.20,18.40,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM5_2021_00000_33.zip/NP_S0_DTM5_2021_00000_33/S0_DTM5_2021_00000_33.tif
# NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr.zip: 2.5 m, 2009 imagery, 3 footprint box(es)
cog_source=15.20,78.20,16.40,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr.zip/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr/S0_DTM2_5_2009_13835_33_Longyearbyenomr.tif
cog_source=15.40,78.30,15.80,78.40|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr.zip/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr/S0_DTM2_5_2009_13835_33_Longyearbyenomr.tif
cog_source=15.40,78.10,16.40,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr.zip/NP_S0_DTM2_5_2009_13835_33_Longyearbyenomr/S0_DTM2_5_2009_13835_33_Longyearbyenomr.tif
# NP_S0_DTM2_5_2009_13835_33_Sveagruvaomr.zip: 2.5 m, 2009 imagery, 2 footprint box(es)
cog_source=16.40,77.90,17.00,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2009_13835_33_Sveagruvaomr.zip/NP_S0_DTM2_5_2009_13835_33_Sveagruvaomr/S0_DTM2_5_2009_13835_33_Sveagruvaomr.tif
cog_source=16.60,77.80,16.80,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2009_13835_33_Sveagruvaomr.zip/NP_S0_DTM2_5_2009_13835_33_Sveagruvaomr/S0_DTM2_5_2009_13835_33_Sveagruvaomr.tif
# NP_S0_DTM2_5_2011_25162_33_Longyearbyenomr.zip: 2.5 m, 2011 imagery, 2 footprint box(es)
cog_source=15.20,78.20,15.60,78.30|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2011_25162_33_Longyearbyenomr.zip/NP_S0_DTM2_5_2011_25162_33_Longyearbyenomr/S0_DTM2_5_2011_25162_33_Longyearbyenomr.tif
cog_source=15.20,78.10,15.80,78.20|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2011_25162_33_Longyearbyenomr.zip/NP_S0_DTM2_5_2011_25162_33_Longyearbyenomr/S0_DTM2_5_2011_25162_33_Longyearbyenomr.tif
# NP_S0_DTM2_5_2011_25162_33_Sveagruvaomr.zip: 2.5 m, 2011 imagery, 2 footprint box(es)
cog_source=16.20,77.80,16.80,77.90|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2011_25162_33_Sveagruvaomr.zip/NP_S0_DTM2_5_2011_25162_33_Sveagruvaomr/S0_DTM2_5_2011_25162_33_Sveagruvaomr.tif
cog_source=16.40,77.90,16.80,78.00|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_5_2011_25162_33_Sveagruvaomr.zip/NP_S0_DTM2_5_2011_25162_33_Sveagruvaomr/S0_DTM2_5_2011_25162_33_Sveagruvaomr.tif
# NP_S0_DTM2_2009_13819_33.zip: 2 m, 2009 imagery, 1 footprint box(es)
cog_source=18.60,74.30,19.40,74.60|/vsizip//vsicurl/https://public.data.npolar.no/kartdata/S0_Terrengmodell/Delmodell/NP_S0_DTM2_2009_13819_33.zip/NP_S0_DTM2_2009_13819_33/S0_DTM2_2009_13819_33.tif
