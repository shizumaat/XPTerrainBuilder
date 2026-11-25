# IGN France RGE ALTI 1 m, overseas France -- BATHYMETRY twin (#2272).
#
# The bathymetry-role sibling of FRANCEDOM1M.elv (same service, same
# request).  In the Antilles and Mayotte the RGE ALTI assembles the
# Litto3D topo-bathymetric survey: the sea beside the coast reads smooth
# measured depths (Saint-Barthelemy: 1st / 50th / 90th percentile -42 /
# -19 / -6 m; Saint-Martin -26 / -6 / -2 m; probed 2026-11-24), and the
# survey edge offshore is nodata (-99999), never a fill value.  The
# depth-graded water masks read it (RULINGS 2026-11-24c/j).
role=bathymetry

access_strategy=wcs_kvp
wcs_getcoverage_template=https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES&STYLES=&CRS=EPSG:4326&BBOX={ymin},{xmin},{ymax},{xmax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/geotiff
source_epsg=4326
max_request_pixels=5010
native_resolution_m=1

# Boxes copied from FRANCEDOM1M.elv.
coverage_bbox=-63.17,17.85,-62.77,18.14
coverage_bbox=-61.82,15.81,-60.98,16.53
coverage_bbox=-61.24,14.37,-60.79,14.89
coverage_bbox=-54.63,2.08,-51.60,5.78
coverage_bbox=55.20,-21.40,55.85,-20.85
coverage_bbox=44.97,-13.01,45.31,-12.62
coverage_bbox=-56.54,46.74,-56.07,47.15

vertical_datum=IGN 1988 / IGN 1987 / NGG 1977 / IGN 1989 / SHOM 1953 / DANGER 1950 (local MSL)

# The survey reaches about -60 m.  Beside its edges the source blends the
# -99999 nodata into real values (FRANCEDOM1M.elv has the measurements;
# at the band's 10 m pixel the Saint-Barthelemy edge held 970 blended
# pixels of 254k, all below -360 m); a floor of -150 m drops them while
# every measured depth stays.
value_floor_m=-150.0

license=Licence Ouverte / Etalab 2.0
attribution=IGN France, RGE ALTI (Litto3D)

# As FRANCETIDAL: below CUDEM (100), above the Allen Coral Atlas (80).
priority=95

enabled=True
