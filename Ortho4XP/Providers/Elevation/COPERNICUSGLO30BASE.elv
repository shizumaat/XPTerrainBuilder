# Copernicus DEM GLO-30 (ESA) as a whole BASE tile -- FALLBACK ONLY.
#
# Used only when the configured base source (Viewfinderpanoramas by
# default) cannot be reached: its download died on the transport after
# every retry (issue #561).  One Cloud-Optimized GeoTIFF per 1-degree
# cell on the registration-free AWS Open Data mirror -- the same objects
# COPERNICUSGLO30.elv reads for airport insets.
#
# The tile is cached at Elevation_data/<block>/<cell>_COPERNICUSGLO30BASE.tif,
# never at the configured source's path, and is read only while the
# configured source's own file is absent: the next build asks the
# configured source again.  Each build that uses it says so in its log.
#
# This is a SURFACE model (forest canopy and buildings are in the
# heights).  Measured 2026-10-12 against the Viewfinderpanoramas cell
# N48W123: +7.5 m mean, 12.9 m RMS.  A substituted cell is therefore
# tied to its Viewfinderpanoramas neighbours along the shared edge
# (elevation_access/base_seam.py), and it is a stand-in for an outage,
# not a choice of source.

role=base
access_strategy=degree_cog_base_tile
display_name=Copernicus GLO-30

url_template=https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{latitude_token}_00_{longitude_token}_00_DEM/Copernicus_DSM_COG_10_{latitude_token}_00_{longitude_token}_00_DEM.tif

resolution_arc_seconds=1

# Asked first when the configured base source is down.
fallback_rank=1

vertical_datum=EGM2008
license=ESA Copernicus DEM licence (free use, modification and distribution with attribution)
attribution=Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA

# NOT a primary base source: disabled, so the automatic base selection
# never takes it.  fallback_rank above is what makes it a fallback.
priority=0
enabled=False
