# Institut national de l'information geographique et forestiere (IGN,
# France) RGE ALTI, 1 metre -- OVERSEAS France (#2272).
#
# The sibling of FRANCE1M.elv: the very same Geoplateforme raster WMS
# layer (ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES, "MNT issu du RGEALTI"),
# whose capabilities box reaches lon -62.95..58, lat -24..51.1 and whose
# ISO metadata (CSW record IGNF_RGE-ALTI, revision 2.0, 2026-10-01) lists
# every overseas territory but French Polynesia, New Caledonia and
# Wallis-et-Futuna.  FRANCE1M asks in Lambert-93 (EPSG:2154, metropolitan
# only); the overseas territories span five UTM zones, so this file asks
# in EPSG:4326 (WMS 1.3.0 axis order: BBOX=lat,lon,lat,lon) and the
# wcs_kvp strategy converts its pad and pixel grid from metres to degrees.
#
# Answers: float32 GeoTIFF, nodata tagged -99999 (no survey: open sea,
# ZICAD restricted zones), MaxWidth/MaxHeight 5010 px.  The SOURCE itself
# carries a sentinel smear beside some survey edges: -99999 blended into
# real values, at every request pixel from 1 m up (measured 2026-11-24,
# share of valid 1 m pixels below -600 / -600..-150 / -150..-60 m: Saint-
# Pierre 20.3 / 0.09 / 0.04 %, Marie-Galante 1.8 / 0.02 / 0.01 %, Mayotte
# 0.5 / 0.02 / 0.00 %, Saint-Barthelemy 0 / 0 / 0 %).  value_floor_m
# below drops all but the lightest blends; the sentinel-smear rim rule
# (elevation_access.sentinel_smear) runs on every fetch for the rest.
#
# VERIFIED 2026-11-24 (lane lign, 50-60 m overview probes per territory,
# valid = not -99999): every territory below answers real terrain; in
# the Antilles and Mayotte the sea beside the coast carries smooth
# negative heights to about -40 m -- the Litto3D topo-bathymetric survey
# assembled into the product, real seabed, not fill.  The seabed reaches
# the depth masks through the bathymetry twin FRANCEDOMTIDAL.elv.

role=airport_inset

# The ISO codes apt.dat's 1302 country rows use for overseas airports
# (TFFJ BLM, TFFG MAF, TFFR GLP, TFFF MTQ, SOCA GUF, FMEP/FMEE/FMCZ FRA or
# none, LFVP SPM); RULINGS 2026-10-20bc.  SXM (Sint Maarten, the Dutch
# side) is NOT France: the island's box below never serves it.
country=FRA,BLM,MAF,GLP,MTQ,GUF,REU,MYT,SPM
access_strategy=wcs_kvp

wcs_getcoverage_template=https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES&STYLES=&CRS=EPSG:4326&BBOX={ymin},{xmin},{ymax},{xmax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/geotiff
source_epsg=4326
max_request_pixels=5010

native_resolution_m=1

# No ground in these territories stands below sea level by more than a
# few metres, and the Litto3D seabed stops near -60 m: anything under
# -150 m is the smeared -99999 sentinel, never terrain.
value_floor_m=-150.0

# One box per territory: the metadata's footprint padded to the measured
# valid extent (the Litto3D seabed reaches past the land footprint).
# Saint-Martin (French side) and Saint-Barthelemy.
coverage_bbox=-63.17,17.85,-62.77,18.14
# Guadeloupe, Les Saintes, Marie-Galante, La Desirade.
coverage_bbox=-61.82,15.81,-60.98,16.53
# Martinique.
coverage_bbox=-61.24,14.37,-60.79,14.89
# Guyane.
coverage_bbox=-54.63,2.08,-51.60,5.78
# La Reunion.
coverage_bbox=55.20,-21.40,55.85,-20.85
# Mayotte.
coverage_bbox=44.97,-13.01,45.31,-12.62
# Saint-Pierre-et-Miquelon.
coverage_bbox=-56.54,46.74,-56.07,47.15

# Normal heights on each territory's own tide-gauge datum (CSW record,
# reference systems): IGN 1988 (Guadeloupe; IGN 1988 SB / SM for
# Saint-Barthelemy / Saint-Martin, LS / MG for Les Saintes /
# Marie-Galante, IGN 1992 LD for La Desirade), IGN 1987 (Martinique),
# NGG 1977 (Guyane), IGN 1989 (Reunion), SHOM 1953 (Mayotte), DANGER 1950
# (Saint-Pierre-et-Miquelon).  All are mean-sea-level datums, not
# ellipsoidal heights, so no geoid_shift: like NGF-IGN69 in FRANCE1M they
# pass through unshifted (their offset to EGM2008 is decimetres).
vertical_datum=IGN 1988 / IGN 1987 / NGG 1977 / IGN 1989 / SHOM 1953 / DANGER 1950 (local MSL)
license=Licence Ouverte / Etalab 2.0
license_note=CSW record IGNF_RGE-ALTI: "Pas de restriction d'acces public selon INSPIRE", Licence Ouverte / Open License (compatible ODC-BY, CC-BY 2.0); attribution required.
attribution=IGN France, RGE ALTI

priority=85

enabled=True
