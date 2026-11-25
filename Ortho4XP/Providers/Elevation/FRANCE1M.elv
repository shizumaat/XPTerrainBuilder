# Institut national de l'information geographique et forestiere (IGN,
# France) RGE ALTI, 1 metre -- the fallback after FRANCE50CM (#1217).
#
# LiDAR HD (FRANCE50CM) only covers what its 2021-2026 campaign has
# flown; where it returns no tiles, RGE ALTI 1 m covers all of
# metropolitan France.  Served anonymously by the Geoplateforme raster
# WMS as float32 GeoTIFF in Lambert-93, nodata tagged -99999, NGF-IGN69
# heights; MaxWidth/MaxHeight 5010 px (verified live 2026-10-21 near LFPG).
#
# The layer is the NATIVE Lambert-93 pyramid RGEALTI-MNT_PYR-ZIP_FXX_
# LAMB93_WMS (MinScaleDenominator 3571 = 1 m), not the all-France
# ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES: that one is a WGS84G pyramid
# whose finest level is ~4.4e-5 degree, so a 1 m request came back as
# blocks ~3.4 m E-W x ~4.9 m N-S (measured 2026-11-25 at 400 m windows
# near LFLB / LFMN: 70 % of adjacent pixels identical; native layer 3 /
# 13 %).

role=airport_inset

country=FRA
access_strategy=wcs_kvp

wcs_getcoverage_template=https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=RGEALTI-MNT_PYR-ZIP_FXX_LAMB93_WMS&STYLES=&CRS=EPSG:2154&BBOX={xmin},{ymin},{xmax},{ymax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/geotiff
source_epsg=2154
max_request_pixels=5010

native_resolution_m=1

# Metropolitan France including Corsica.
coverage_bbox=-5.2,41.3,9.6,51.1

vertical_datum=NGF-IGN69
license=Licence Ouverte / Etalab 2.0
attribution=IGN France, RGE ALTI

priority=85

enabled=True
