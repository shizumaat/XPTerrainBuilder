# Copernicus DEM GLO-90 (ESA) as a whole BASE tile -- FALLBACK ONLY.
#
# The second fallback (issue #561), asked when neither the configured
# base source nor COPERNICUSGLO30BASE could be fetched: the same surface
# model at 3 arc-seconds, an eighth of the download (about 4 MB a cell),
# from a separate bucket.  See COPERNICUSGLO30BASE.elv for the rules.

role=base
access_strategy=degree_cog_base_tile
display_name=Copernicus GLO-90

url_template=https://copernicus-dem-90m.s3.amazonaws.com/Copernicus_DSM_COG_30_{latitude_token}_00_{longitude_token}_00_DEM/Copernicus_DSM_COG_30_{latitude_token}_00_{longitude_token}_00_DEM.tif

resolution_arc_seconds=3

# Asked second when the configured base source is down.
fallback_rank=2

vertical_datum=EGM2008
license=ESA Copernicus DEM licence (free use, modification and distribution with attribution)
attribution=Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA

# NOT a primary base source: disabled, so the automatic base selection
# never takes it.  fallback_rank above is what makes it a fallback.
priority=0
enabled=False
