# Landesamt fuer Vermessung und Geoinformation Schleswig-Holstein
# (Germany) digital terrain model DGM1, 1 metre.
#
# Bare-earth 1 km XYZ tiles, Datenlizenz Deutschland Zero 2.0,
# resolved through the state's GeoJSON tile index (fetched once and
# cached -- the download script needs per-tile year and bucket tokens
# only the index knows) and downloaded whole (the host ignores ranged
# requests).  Verified live 2026-07-16 at Sylt.  The XYZ carries no
# CRS, so the warp assigns EPSG:25832.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=DEU
access_strategy=tile_grid_http

tile_url_template={file_name}
index_url=https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/single.php?file=DGM1_SH__Massendownload.geojson&id=4
# The host sends its leaf certificate without the intermediate (issue
# #1923; openssl verify 21).  Ship that intermediate, fetched from the
# leaf's AIA "CA Issuers" URL (www.d-trust.net/cgi-bin/D-TRUST_BR_CA_1-20-1_2020.crt),
# chaining to certifi's "D-TRUST BR Root CA 1 2020", pinned by the
# SHA-256 of its DER bytes.  Valid to 2035-02-11.
tls_extra_ca=D-TRUST_BR_CA_1-20-1_2020.pem
tls_extra_ca_sha256=199ab2aaafff40401e0a3b7b87ee9964659effa94a1fecbe918ae136e4b4e0a8
fetch_mode=download
download_suffix=.xyz
tile_size_km=1
source_epsg=25832
warp_source_epsg=25832

native_resolution_m=1
# Schleswig-Holstein.
coverage_bbox=7.8,53.3,11.4,55.1

vertical_datum=DHHN2016
license=Datenlizenz Deutschland Zero 2.0 (no restrictions)
attribution=GeoBasis-DE/LVermGeo SH

priority=85
enabled=True
