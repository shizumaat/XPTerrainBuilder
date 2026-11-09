# Viewfinderpanoramas (J. de Ferranti), 3 arc-second archives.
#
# Base-tier (tile-wide) definition; the global fallback source, matching
# the historic default behaviour of the "View" keyword outside the
# 1 arc-second zone whitelist (see VIEWFINDER1.elv).

role=base
access_strategy=viewfinder_zip
legacy_keyword=View
# The name log lines give this source.
display_name=Viewfinderpanoramas

download_url_template=https://viewfinderpanoramas.org/dem3/{archive_code}.zip

resolution_arc_seconds=3

# The letter+number archive codes de Ferranti publishes at 3 arc-second
# (issue #1933: Iceland and Greenland -- P22, P27, Q27 ... -- have no
# dem3 zone archive, only regional ones, and asking for one 404'd; those
# zones are served by VIEWFINDER1).  GENERATED from the site's coverage
# map by tools/refresh_viewfinder_coverage.py; its header carries the
# source URL and the fetch date.
archive_zones_file=viewfinder_dem3_zones.txt

vertical_datum=EGM96
license=Free for non-commercial use with attribution (viewfinderpanoramas.org)
attribution=Jonathan de Ferranti, viewfinderpanoramas.org

priority=10
enabled=True
