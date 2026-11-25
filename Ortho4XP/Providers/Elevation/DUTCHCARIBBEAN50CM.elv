# Caribisch Nederland lidar DTM, 0.5 metre -- Saba, Sint Eustatius and
# Bonaire (the BES islands).
#
# Flown 2023 for the Dataroom Caribisch Nederland (Beeldmateriaal
# Nederland / Het Waterschapshuis) and published as ONE tiled GeoTIFF per
# island (256 px blocks, 6+ overviews) on basisdata.nl, which redirects
# (HTTP 307) to object storage; GDAL follows the redirect and reads only
# the requested window (Bonaire's file is 2.87 GB: never download it).
#
# The files declare no usable CRS (a LOCAL_CS with metre units, no datum):
# each island's grid is its own DPnet engineering CRS, so every source
# line below names its EPSG code in the third field and the direct_cog
# strategy hands the warp a vrt://...?a_srs=EPSG:n wrapper.  The codes
# (2024, EPSG dataset v11.0xx) resolve in PROJ 9.7 (Windows wheel's
# proj.db v12.029) and in the macOS engine's PROJ 9.9 (verified
# 2026-11-25, lane lbes: the warped corners land on each island's box).
#
# Nodata is tagged 3.4028235e38 (float max): the open sea, about 75 % of
# each file.

role=airport_inset

# apt.dat's 1302 country rows for TNCS, TNCE and TNCB read
# "NLD Caribbean Netherlands"; BES is the ISO code of the islands
# themselves.  NETHERLANDS50CM (country NLD too) never reaches the
# Caribbean: its box stops at the European Netherlands.  Sint Maarten
# (SXM, TNCM) is a separate country with no public lidar here.
country=NLD,BES
access_strategy=direct_cog

native_resolution_m=0.5

# One footprint per island: the file's own extent (corners warped from its
# engineering CRS, 2026-11-25).
# Saba (TNCS).
coverage_bbox=-63.264,17.609,-63.206,17.655
# Sint Eustatius (TNCE).
coverage_bbox=-63.009,17.456,-62.942,17.529
# Bonaire (TNCB).
coverage_bbox=-68.429,12.023,-68.189,12.313

cog_source=-63.264,17.609,-63.206,17.655|https://basisdata.nl/hwh-ortho/Caribisch_NL/LiDAR/caribisch/Saba/02a_DTM_50cm/M_SABA2023.TIF|EPSG:10641
cog_source=-63.009,17.456,-62.942,17.529|https://basisdata.nl/hwh-ortho/Caribisch_NL/LiDAR/caribisch/St_Eustatius/02a_DTM_50cm/M_STATIA2023.TIF|EPSG:10745
cog_source=-68.429,12.023,-68.189,12.313|https://basisdata.nl/hwh-ortho/Caribisch_NL/LiDAR/caribisch/Bonaire/02a_DTM_50cm/M_BONAIRE2023.TIF|EPSG:10759

# The publisher states no vertical datum.  The heights are local mean sea
# level (the islands' own tide-gauge levels; runway checks against apt.dat
# agree to a metre or two), so they pass through unshifted like every
# other national lidar.
vertical_datum=unstated by the publisher (local MSL)
license=Creative Commons Attribution 4.0 (CC BY 4.0)
attribution=Dataroom Caribisch Nederland / Beeldmateriaal Nederland / Het Waterschapshuis, lidar DTM 2023

priority=90

enabled=True
