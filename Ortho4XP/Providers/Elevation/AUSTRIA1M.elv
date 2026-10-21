# Bundesamt fuer Eich- und Vermessungswesen (BEV, Austria) airborne
# laser scanning digital terrain model, 1 metre.
#
# Bare-earth national lidar (Stichtag 2019 campaign), CC BY 4.0,
# published as 50 km EPSG:3035 BigTIFF tiles with deterministic names
# and ranged reads (verified live 2026-07-16 at Vienna: the tile is
# 7.9 GB but /vsicurl window-reads it).  Uses the tile_grid_http
# strategy with metre-named tiles.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=AUT
access_strategy=tile_grid_http

tile_url_template=https://data.bev.gv.at/download/ALS/DTM/20190915/CRS3035RES50000mN{northing_m}E{easting_m}.tif
tile_size_km=50
source_epsg=3035

native_resolution_m=1
# Austria.
coverage_bbox=9.5,46.3,17.2,49.1

vertical_datum=GHA (Austrian height system)
license=Creative Commons Attribution 4.0 (CC BY 4.0)
attribution=BEV, Bundesamt fuer Eich- und Vermessungswesen

priority=85
enabled=True
