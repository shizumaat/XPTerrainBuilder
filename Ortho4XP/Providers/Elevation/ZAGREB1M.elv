# City of Zagreb (Croatia) digital terrain model 2024, ~1 metre.
#
# City-area bare-earth model hosted as a tiles-only ArcGIS LERC
# pyramid on the global Web Mercator grid (verified live 2026-07-16
# in the city centre).  NOTE: the international airport lies in
# Velika Gorica, OUTSIDE the city data mask -- its windows honestly
# fall through to the base tier; this provider serves the city area
# itself.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=HRV
access_strategy=arcgis_lerc_tiles

tile_url_template=https://tiles.arcgis.com/tiles/Usi0jGQwMmBUpFjr/arcgis/rest/services/ZG_DTM_2024/ImageServer/tile/{level}/{row}/{col}
tile_level=17

native_resolution_m=1
# Zagreb area.
coverage_bbox=15.65,45.60,16.35,45.98

vertical_datum=Croatian height system (HVRS71)
license=Open city geodata (City of Zagreb / GDi)
attribution=Grad Zagreb / GDi

priority=80
enabled=True
