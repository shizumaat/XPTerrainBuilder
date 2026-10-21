# Institut national de l'information geographique et forestiere (IGN,
# France) RGE ALTI, 1 metre -- the fallback after FRANCE50CM (#1217).
#
# LiDAR HD (FRANCE50CM) only covers what its 2021-2026 campaign has
# flown; where it returns no tiles, RGE ALTI 1 m covers all of
# metropolitan France.  Served anonymously by the Geoplateforme raster
# WMS (layer ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES) as float32
# GeoTIFF in Lambert-93, nodata tagged -99999, NGF-IGN69 heights;
# MaxWidth/MaxHeight 5010 px (verified live 2026-10-21 near LFPG).

role=airport_inset

country=FRA
access_strategy=wcs_kvp

wcs_getcoverage_template=https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES&STYLES=&CRS=EPSG:2154&BBOX={xmin},{ymin},{xmax},{ymax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/geotiff
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
