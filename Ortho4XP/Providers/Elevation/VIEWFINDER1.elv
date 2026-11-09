# Viewfinderpanoramas (J. de Ferranti), 1 arc-second archives.
#
# Base-tier (tile-wide) definition, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
# The legacy "View" keyword resolves to this definition wherever its
# archive zones cover the tile, else to VIEWFINDER3.

role=base
access_strategy=viewfinder_zip

# Legacy short keyword: the cache file path (FNAMES.viewfinderpanorama)
# and the download log/retry labels stay byte-identical to the historic
# behaviour.
legacy_keyword=View
# The name log lines give this source.
display_name=Viewfinderpanoramas

download_url_template=https://viewfinderpanoramas.org/dem1/{archive_code}.zip

resolution_arc_seconds=1

# The letter+number archive codes de Ferranti publishes at 1 arc-second
# (issue #1974: the historic 35-zone whitelist missed N29, N30, O30 and
# ~280 more).  GENERATED from the site's coverage map by
# tools/refresh_viewfinder_coverage.py; its header carries the source
# URL and the fetch date.
archive_zones_file=viewfinder_dem1_zones.txt

# Wellington International has missing elevation data in the 1 arc-second
# resolution (historic hardcoded exception, now declarative).
exclude_tiles=-42,174

vertical_datum=EGM96
license=Free for non-commercial use with attribution (viewfinderpanoramas.org)
attribution=Jonathan de Ferranti, viewfinderpanoramas.org

priority=60
enabled=True
