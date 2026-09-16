# United States Geological Survey 3D Elevation Program (3DEP) 1 metre lidar.
#
# Declarative elevation-inset provider, parsed by
# src/O4_Airport_Elevation_Insets.py:initialize_elevation_providers_dict.
# Same comment and key=value syntax as the imagery Providers/<Region>/<CODE>.lay
# files. Unknown keys are preserved; edit freely.

# Detail tier (spec section 3.6): meter-class data fetched only inside
# airport bounding boxes. Tile-wide "base" sources are the Phase A2 refactor.
role=airport_inset

# Named fetch strategy implemented in code (strategy registry in the module).
access_strategy=tnm_cog

# The National Map (TNM) Access API product-discovery endpoint. The
# {west},{south},{east},{north} placeholders are substituted with the
# airport bounding box in EPSG:4326 (degrees) at discovery time.
discovery_url_template=https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Digital Elevation Model (DEM) 1 meter&bbox={west},{south},{east},{north}&outputFormat=JSON

# Native ground resolution of the source rasters, in metres.
native_resolution_m=1

# Cheap pre-filter before the discovery request is issued; discovery is
# authoritative.  3DEP IS US-ONLY (owner RULINGS 2026-09-16c): the single
# box this file used to declare (-180,15,-64,72) reached all of Canada,
# Mexico, Central America and the Caribbean, so every airport in them
# recorded a durable "no-coverage" that the once-per-engine-version
# re-probe door (RULINGS 2026-09-15ay) then re-asked forever -- CYXY
# (Whitehorse) was refused a `--refresh-only dem` for exactly this.
#
# The declaration is therefore a LIST of boxes, one per 3DEP region, from
# the USGS 3DEP product description: "3DEP ... for the conterminous United
# States, Alaska, Hawaii, and the U.S. territories"
# (https://www.usgs.gov/3d-elevation-program, and the 1-metre DEM coverage
# map at https://apps.nationalmap.gov/3depdem/).  A repeated coverage_bbox=
# line is joined by the reader, so each box carries its own comment.
#
# Conterminous United States, west of the Northwest Angle: the border is
# the 49th parallel from the Strait of Georgia to Lake of the Woods, so a
# box ending at 49.05 keeps Vancouver and the BC interior out.
coverage_bbox=-125.0,24.0,-95.15,49.05
# The Northwest Angle, Minnesota (to 49.38 N) -- the one piece of the
# lower 48 north of the 49th parallel.
coverage_bbox=-95.25,48.9,-94.9,49.45
# Conterminous United States east of the Angle, north to Isle Royale,
# Michigan (48.22 N) and the northern tip of Maine (47.46 N).  A
# rectangle cannot follow the Great Lakes / St Lawrence border, so
# southern Ontario and the Montreal corridor stay inside this box;
# discovery is authoritative there and answers no products.
coverage_bbox=-95.15,24.0,-66.0,48.35
# Alaska west of the 141st meridian (the Yukon border): mainland, the
# Alaska Peninsula and the Aleutians east of the antimeridian.  A single
# Alaska rectangle would swallow Yukon and northern British Columbia --
# it is what put CYXY (Whitehorse, 60.71 -135.07) inside 3DEP's declared
# coverage -- so the SOUTHEAST PANHANDLE is a separate box below.
coverage_bbox=-180.0,51.0,-141.0,71.5
# The southeast panhandle, between the 141st meridian and Dixon Entrance,
# south of the 60th parallel (the Alaska/BC/Yukon border follows both).
# A rectangle still spills onto the BC coast ranges behind the panhandle;
# discovery is authoritative there and answers no products.
coverage_bbox=-141.0,54.5,-130.0,60.0
# The Aleutian chain WEST of 180 deg.  The reader's boxes are plain
# W,S,E,N rectangles and cannot cross the antimeridian, so the chain is
# split into two boxes rather than left uncovered.
coverage_bbox=172.0,51.0,180.0,53.5
# Hawaii (main islands; the Northwestern Hawaiian Islands carry no 1 m 3DEP).
coverage_bbox=-161.0,18.5,-154.5,22.5
# Puerto Rico and the U.S. Virgin Islands.
coverage_bbox=-68.0,17.5,-64.5,18.6
# Guam and the Commonwealth of the Northern Mariana Islands.
coverage_bbox=144.5,13.2,146.2,20.6
# American Samoa.
coverage_bbox=-171.2,-14.5,-169.4,-13.8

# Vertical datum of the delivered elevations. NAVD88 is within ~1 m of
# EGM96 across the continental United States; the lidar is treated as
# truth and never shifted toward the base DEM.
vertical_datum=NAVD88

license=Public Domain (U.S. Geological Survey)
attribution=U.S. Geological Survey 3D Elevation Program (3DEP)

# Higher priority wins when several providers cover the same airport.
priority=100

enabled=True
