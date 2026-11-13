# FABDEM V1-2 (Hawker et al. 2022, University of Bristol): Copernicus
# GLO-30 with buildings and forests removed by machine learning -- a
# BARE-EARTH 1 arc-second model, 60S-80N (issue #1942).
#
# The global bare-earth INSET tier, ranked just above COPERNICUSGLO30 (the
# surface model it was made from, same 2011-2015 epoch): every national
# lidar or photogrammetric source still outranks it.  Because the heights
# are already bare earth, there is NO building-footprint masking pass.
#
# Published on the University of Bristol data portal (dataset
# s5hqmjcdj8yo2ibzi9b4ew3sn, DOI 10.5523/bris.s5hqmjcdj8yo2ibzi9b4ew3sn)
# as 1-degree Cloud-Optimized GeoTIFFs zipped by 10-degree block
# (N50W010-N60E000_FABDEM_V1-2.zip holds N54W005_FABDEM_V1-2.tif).  The
# portal answers ranged requests, so nothing is downloaded whole
# (degree_zipped_cog): each zip's directory is listed once per run and the
# warp reads the cell's member in place.  Verified live 2026-11-13 at EGNS
# (HEAD 200 + a 206 range read on the zip; member 3600x3600 Float32
# DEFLATE COG, nodata -9999, WGS 84).  The portal's own tile GeoJSON
# names the zips and members wrongly (N60W000, N054W005), so the names are
# computed, never read from it.  A new FABDEM version is a new URL here.

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=GLOBAL

access_strategy=degree_zipped_cog

url_template=https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn/{block_latitude_token}{block_longitude_token}-{block_end_latitude_token}{block_end_longitude_token}_FABDEM_V1-2.zip
member_template={latitude_token}{longitude_token}_FABDEM_V1-2.tif

native_resolution_m=30

coverage_bbox=-180.0,-60.0,180.0,80.0

# APPROACH RING 2 ONLY, as COPERNICUSGLO30 (owner RULINGS 2026-10-02c):
# the 1 arc-second ring where no wide-area source covers the cell; the
# higher priority makes the bare-earth model serve it ahead of the surface
# model, so an airport's inset and its ring 2 read the same source.
approach_ring_class=ring2

# Fallback quality whatever its 30 m grid (a radar DSM corrected by machine
# learning): it never makes a genuine terrain model "not better" -- the
# ~30 m lidar-derived Sonny drop folder is still offered over Europe.
fallback_quality=True

vertical_datum=EGM2008
license=CC BY-NC-SA 4.0 (non-commercial; attribution; share-alike)
license_note=Non-commercial licences are usable in this free product (owner RULINGS 2026-11-06d (12)); derivatives are shared alike under CC BY-NC-SA 4.0
attribution=FABDEM V1-2: Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed. Environmental Research Letters 17, 024016. University of Bristol, CC BY-NC-SA 4.0; contains modified Copernicus DEM data (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA

# Just above COPERNICUSGLO30 (priority 1) and below every national source.
priority=2

enabled=True
