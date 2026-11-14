# FABDEM V1-2 (bare-earth Copernicus GLO-30) as a whole BASE tile --
# FALLBACK ONLY (issue #1942).
#
# Used only when the configured base source (Viewfinderpanoramas by
# default) cannot be reached or has no file for a land cell (issue #561,
# elevation_access/base_fallback.py), ranked FIRST among the fallbacks:
# bare earth sits closer to the configured terrain models than the
# Copernicus SURFACE model it was made from.  The same zipped cells
# FABDEM.elv reads for airport insets, read in place
# (cell_strategy=degree_zipped_cog); the tile is cached at
# Elevation_data/<block>/<cell>_FABDEMBASE.tif.  It covers 60S-80N
# only, so it is NOT a sea witness (no land_complete): COPERNICUSGLO30BASE
# stays that.

role=base
access_strategy=degree_cog_base_tile
cell_strategy=degree_zipped_cog
display_name=FABDEM (bare-earth GLO-30)

url_template=https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/{block_latitude_token}{block_longitude_token}-{block_end_latitude_token}{block_end_longitude_token}_FABDEM_V1-2.zip
member_template={latitude_token}{longitude_token}_FABDEM_V1-2.tif

resolution_arc_seconds=1

coverage_bbox=-180.0,-60.0,180.0,80.0

# Asked first when the configured base source is down.
fallback_rank=1

vertical_datum=EGM2008
license=CC BY-NC-SA 4.0 (non-commercial; attribution; share-alike)
attribution=FABDEM V1-2: Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. Environmental Research Letters 17, 024016. University of Bristol, CC BY-NC-SA 4.0; contains modified Copernicus DEM data (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA

# NOT a primary base source: disabled, so the automatic base selection
# never takes it.  fallback_rank above is what makes it a fallback.
priority=0
enabled=False
