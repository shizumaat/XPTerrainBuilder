# IslandsDEM v1.0 (ÍslandsDEM), the national elevation model of Iceland,
# 2 metre.
#
# A seamless country-wide mosaic of ArcticDEM strips (Polar Geospatial
# Center) aligned to Copernicus GLO-30, with glacier lidar and drone
# surveys folded in, published by Náttúrufræðistofnun (the Natural
# Science Institute of Iceland, formerly Landmælingar Íslands) under
# CC BY 4.0.  The 2 m model is cut into 70 tiles of 50 x 50 km in
# ISN2016 (EPSG:8088), each one tiled ZSTD GeoTIFF that the host serves
# with ranged reads.  The download grid is a public WFS layer
# (LMI_vektor:islandsdem_footprint) whose features carry each tile's
# URL; asked for GeoJSON in EPSG:4326 it is exactly the one-catalog
# shape of the geojson_tile_index strategy, so this is a pure
# definition (verified live 2026-11-02 at Keflavik, tile 56).

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=ISL

access_strategy=geojson_tile_index

index_url=https://gis.lmi.is/geoserver/LMI_vektor/ows?service=WFS&version=1.1.0&request=GetFeature&typeName=LMI_vektor:islandsdem_footprint&outputFormat=application/json&srsName=EPSG:4326&propertyName=nr_reits,dem,geom
# The feature property holding the 2 m ISN2016 height tile (the others
# are the hillshade and an ISN93 copy).
url_property=dem

# Native ground resolution of the source tiles, in metres.
native_resolution_m=2

# Iceland (the catalog's tile footprints, rounded out).
coverage_bbox=-24.9,63.2,-13.3,66.7

# Orthometric heights in metres above sea level: the ArcticDEM
# ellipsoidal heights were reduced with the IceGeoid model to the
# Icelandic height system.
vertical_datum=ISH2004 (orthometric, IceGeoid)
license=Attribution 4.0 International (CC BY 4.0)
attribution=ÍslandsDEM v1.0, Náttúrufræðistofnun (Natural Science Institute of Iceland); ArcticDEM, Polar Geospatial Center

priority=85

enabled=True
