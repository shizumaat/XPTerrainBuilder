# Whidbey Island, Washington -- 2023-2024 USGS / Washington DNR Refresh
# lidar ("Whidbey Refresh23 2024"), 1.5 ft bare-earth DTM, served by the
# Washington Lidar Portal (lidarportal.dnr.wa.gov).  Issue #154 (KNUW,
# KNRA, HOLDER airports); spec docs/specs/us-holder-providers-spec.md
# §3.6/§4.
#
# THE GATE -- OWNER RULING 2026-09-30bn (Q-154), verbatim: "Go with (a),
# honor the gate like a browser".  The portal answers its query and
# download endpoints with HTTP 403 unless the request carries the dlgate
# cookie its front page sets (Set-Cookie: dlgate=ok; Max-Age=7200) and a
# browser user agent.  The strategy GETs the front page ONCE per process
# with a browser agent, replays the cookies until their Max-Age, and
# records both in provenance.  No CAPTCHA solving, no credentials; if
# the portal adds a login or terms forbidding scripted access, the
# provider records unavailable: ... gate and is never worked around.
# Fact for the owner (lane aoi154, 2026-09-30): the portal's robots.txt
# lists "Disallow: /download" and "Disallow: /query" for every agent.
#
# Declarative inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
role=airport_inset

access_strategy=aoi_zip_download
query_url=https://lidarportal.dnr.wa.gov/query
download_url=https://lidarportal.dnr.wa.gov/download
gate_cookie_from=/
user_agent_profile=browser
# Project "Whidbey Refresh23 2024", dataset "DTM".
dataset_ids=1783
# Members: datasetsC/whidbey_refresh23_2024/dtm/be_w{x}n{y}_dtm.tif
# (1500 x 1500 Float32 LZW, 1.5 ft cells, EPSG:2927 ftUS, nodata -999999).
member_glob=*/dtm/*_dtm.tif
source_nodata=-999999

# Heights: NAVD88, US survey FEET -> metres at the shared warp (§2).
vertical_unit=ftUS
vertical_datum=NAVD88
native_resolution_m=0.457

footprint_buffer_m=300
core_feather_m=60

# Spec §3.6 default.  The full inset box (boundary + 2 km) at KNUW lists
# more than this; the surgical core fits (scout: 24 files / 183 MB).
max_bytes_per_airport=300000000

publication_date=2024
# The dataset's extent (portal /project, Whidbey Refresh23 2024 DTM,
# measured 2026-09-30): -122.782..-122.116 E, 47.896..48.639 N.
coverage_bbox=-122.79,47.89,-122.11,48.64

license=Washington DNR / USGS 3DEP lidar (public; no use restriction published)
license_note=No restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw). The portal's download gate is honoured exactly as a browser meets it -- front-page dlgate cookie + browser user agent, recorded in provenance -- per owner RULINGS 2026-09-30bn ("Go with (a), honor the gate like a browser"); a login or forbidding terms disable it (unavailable), never a workaround. robots.txt disallows /query and /download for crawlers; owner RULINGS 2026-10-01c: XPTerrainBuilder is one user's interactive client fetching one airport for that user -- a browser, not a crawler or indexer -- so robots.txt does not apply; acceptable use.
attribution=Washington State Department of Natural Resources / USGS — 2023-2024 Whidbey Refresh lidar (Washington Lidar Portal)

ladder_member=True
priority=90

enabled=True
