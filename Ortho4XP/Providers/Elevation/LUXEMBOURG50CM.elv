# Administration du cadastre et de la topographie (ACT, Luxembourg)
# BD-L-Lidar2024 digital terrain model (MNT), 50 centimetre.
#
# Bare-earth national lidar (2024 flight, >30 pts/m2; the MNT keeps
# only the ground and water classes, so bridges, buildings and
# vegetation are NOT in it), published on data.public.lu as ONE
# country-wide Cloud-Optimized GeoTIFF (EPSG:2169 LUREF / Luxembourg
# TM, Float64 metres, nodata -9999, 128 px blocks, 11 overviews) with
# no registration -- the direct_cog strategy window-reads the airport
# box straight out of it (verified live 2026-11-19 at ELLX, #2185).
# Dataset: data.public.lu "Lidar 2024 - Releve 3D du territoire
# luxembourgeois", licence CC0 1.0.  Vertical accuracy < 10 cm
# (sigma 5.5 cm, ACT documentation v1.1).

role=airport_inset

# THE COUNTRY RULE (owner RULINGS 2026-10-20bc): ISO 3166-1 alpha-3 codes of
# the airports this provider may serve (apt.dat 1302 country), or GLOBAL.
country=LUX

access_strategy=direct_cog

# The 40 GB country-wide Cloud-Optimized GeoTIFF (the "mnt-cog-lidar2024"
# resource of the dataset).
cog_urls=https://download.data.public.lu/resources/bd-l-lidar2024-releve-3d-du-territoire-luxembourgeois/20241223-093912/MNT_Lidar2024.tif

# Native ground resolution of the source raster, in metres.
native_resolution_m=0.5

# Cheap pre-filter: the Grand Duchy.
coverage_bbox=5.7,49.4,6.6,50.2

# Luxembourg normal heights (NG-L, EPSG:5774, levelling tied to the
# Amsterdam datum like the German DHHN): orthometric, within decimetres
# of EGM2008, so no geoid_shift -- as for the neighbouring German states.
vertical_datum=NG-L (Luxembourg normal heights)
license=Creative Commons Zero 1.0 (public domain)
attribution=Administration du cadastre et de la topographie (ACT), Luxembourg, BD-L-Lidar2024

# National lidar, like NETHERLANDS50CM.
priority=90

enabled=True
