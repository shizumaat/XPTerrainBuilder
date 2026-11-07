# Landesbetrieb Geoinformation und Vermessung Hamburg (Germany)
# digital terrain model DGM1, 1 metre (2022-04-30 epoch).
#
# Bare-earth 1 km GeoTIFF tiles, Datenlizenz Deutschland Namensnennung
# 2.0, published as ONE whole-city zip (~1.36 GB) on the Hamburg
# Transparency Portal (dataset "gelaendemodelle-hamburg-dgm2",
# https://suche.transparenz.hamburg.de/dataset/gelaendemodelle-hamburg-dgm2).
# The portal's archive host answers ranged requests, so nothing is
# downloaded whole (issue #1923): the zip's central directory is listed
# once through /vsizip//vsicurl/ (cached as the tile index) and each
# airport's few 1 km members are read in place by the warp.  Verified
# live 2026-11-06 at EDDH (tile 566/5942: 1000x1000 Float32, ETRS89 /
# UTM 32N).  The archive keeps every snapshot URL (the 2025 snapshot
# _243830_snap_2 still answers); a newer epoch is a new URL here.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=DEU

access_strategy=tile_grid_http

tile_url_template={file_name}
index_url=/vsizip//vsicurl/https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/dgm1_hh_2022-04-30_258334_snap_1.zip
tile_size_km=1
source_epsg=25832

# Native ground resolution of the source grid, in metres.
native_resolution_m=1

# Hamburg, and its North Sea exclave Neuwerk (tiles 466-468 / 5973-5976).
coverage_bbox=9.6,53.3,10.4,53.8
coverage_bbox=8.35,53.88,8.55,53.98

vertical_datum=DHHN2016
license=Datenlizenz Deutschland Namensnennung 2.0 (attribution required)
attribution=Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung

priority=85

enabled=True
