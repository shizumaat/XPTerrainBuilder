# Natural Resources Canada High Resolution Digital Elevation Model (HRDEM)
# lidar, served through the Canadian federal geospatial datacube STAC API.
#
# Declarative elevation-inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
# Same comment and key=value syntax as USGS3DEP.elv. This is the Phase C2
# extensibility proof: a whole new provider family (a STAC search endpoint
# serving Cloud-Optimized GeoTIFF assets) added as one definition file plus
# one access-strategy class, with no change to the fetch/cache/bake/grid
# orchestration.

# Detail tier (spec section 3.6): meter-class data fetched only inside
# airport bounding boxes.
role=airport_inset

# Named fetch strategy implemented in code: a STAC /search query for
# intersecting items, then a mosaic + warp of their Cloud-Optimized GeoTIFF
# Digital Terrain Model assets through GDAL's virtual file system.
access_strategy=stac

# The STAC API search endpoint. The stac strategy POSTs a bbox+collections
# body (falling back to a GET query string), so the collections are given
# separately below rather than baked into the URL.
discovery_url_template=https://datacube.services.geo.ca/stac/api/search

# STAC collection(s) to search. hrdem-lidar is the 1 metre lidar-derived
# HRDEM mosaic collection.
collections=hrdem-lidar

# Preferred STAC asset key(s) for the bare-earth Digital Terrain Model, in
# order; the strategy falls back to any DTM-looking or GeoTIFF asset.
dtm_asset_keys=dtm

# Native ground resolution of the source rasters, in metres.
native_resolution_m=1

# Cheap pre-filter before the discovery request is issued; discovery is
# authoritative.  HRDEM IS CANADA-ONLY (Natural Resources Canada,
# https://natural-resources.canada.ca/science-data/science-research/
# geomatics/elevation-data -- "coverage of the Canadian landmass").  The
# single box this file used to declare (-141,41,-52,84) reached 41 deg N
# across the whole continent, i.e. most of the northern United States;
# every US airport in it recorded a durable "no-coverage" that the
# once-per-engine-version door (RULINGS 2026-09-15ay) then re-asks --
# nine such records sit on N45W123 (Portland, Oregon) today.  Now that
# the reader holds a LIST (owner RULINGS 2026-09-16c) the border is
# followed in three boxes.  The west edge stays at the 141st meridian
# (the Alaska border); the boxes still spill onto the Alaska panhandle,
# the Great Lakes states and northern New England, where a rectangle
# cannot follow the border and discovery is authoritative.
#
# West of Lake of the Woods: the 49th parallel border, BC to Manitoba.
# This is the box that keeps Portland, Seattle and the whole northwest
# of the United States out.
coverage_bbox=-141.0,48.9,-95.15,84.0
# Ontario and the Great Lakes, south to Middle Island (41.68 N), Canada's
# southernmost point.  Southern Ontario lies SOUTH of Minneapolis, so a
# rectangle holding Toronto necessarily holds the upper Midwest and the
# Great Lakes states as well; discovery is authoritative there.
coverage_bbox=-95.15,41.6,-74.0,84.0
# Quebec and Atlantic Canada, south to Cape Sable, Nova Scotia (43.4 N).
coverage_bbox=-74.0,43.0,-52.0,84.0

# Vertical datum of the delivered elevations. CGVD2013 is the Canadian
# geodetic vertical datum; the lidar is treated as truth and never shifted
# toward the base DEM (the feather-ring offset is logged for inspection).
vertical_datum=CGVD2013

license=Open Government Licence - Canada
attribution=Natural Resources Canada

# Below USGS3DEP (100); they never overlap (Canada vs United States), so
# the ordering only documents intent.
priority=90

enabled=True
