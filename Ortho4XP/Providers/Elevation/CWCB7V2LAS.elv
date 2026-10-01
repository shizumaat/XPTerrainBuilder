# Colorado Water Conservation Board -- 2015 Western Colorado Point Cloud
# (Partial Delta, Gunnison, Mesa & Montrose; Quantum Spatial), classified
# LAS 1.2 in per-tile zips, gridded in-engine to a 1 m DTM.  Issue #154
# (7V2, North Fork Valley: the CWCB dataset there is LAS-only); spec
# docs/specs/us-holder-providers-spec.md §3.3 / §5; owner RULINGS
# 2026-09-30bm.
#
# Joins the USGS3DEP ladder through ladder_member=True wherever its
# coverage box reaches the airport box.
role=airport_inset
access_strategy=las_tile_index

# The tile index is the CWCB lidar API (the one CWCB discovery the
# cwcb_lidar_api strategy uses): POST tiles with the surgical polygon,
# filtered to this dataset through its tileSummaries listing.
index_format=cwcb
tiles_url=https://coloradohazardmapping.com/api/lidar/tiles
summaries_url=https://coloradohazardmapping.com/api/lidar/tileSummaries
file_url_template=https://coloradohazardmapping.com/api/lidar/files/{tileKey}/{formatKey}
dataset_ids=5167f85f-e2c9-4a13-b20f-aaea2fb88b57
# The dataset's one product: the classified LAS tile, as a zip.
format_key=20d03d8e-c823-4683-b71b-88326784a9f6
summaries_max_age_days=30

# Each tile is a zip holding ONE .las: the zip comes whole into the
# las_tiles cache, the member is extracted, the zip deleted.
archive_member=las
# LAS 1.2, point format 1, uncompressed.
point_formats=1

# Point coordinates: NAD83 / UTM zone 13N (each tile's GeoKey directory,
# measured 2026-10-01), heights NAVD88 metres.  A tile whose header CRS
# disagrees is refused (never cached).
source_crs=26913
vertical_unit=m
vertical_datum=NAVD88

ground_classes=2
grid_resolution_m=1
native_resolution_m=1
min_points_per_cell=1
fill_radius_cells=3

footprint_buffer_m=300
core_feather_m=60
fetch_slots=2

# Per-airport caps on the SURGICAL set (7V2 measured by lane lasidx154,
# see the report on #154; one tile ~107 MB of LAS, ~55 MB zipped).  The
# byte cap is judged on the listing's size (the LAS), before any byte
# moves.  Over either the rung is SKIPPED (unavailable).
max_tiles_per_airport=16
max_bytes_per_airport=1800000000
keep_raw_las=true

publication_date=2016-02

# The dataset's tile extent, measured from its tileSummaries listing
# (9,184 tiles, 2026-10-01; whole hull -108.3879..-106.8264 E,
# 38.3649..39.2601 N) as one box per 0.25-degree row of the tiles' union:
# the hull would reach KASE (Aspen, 0.22 degrees from the nearest tile),
# a control airport this dataset does not cover.
coverage_bbox=-108.389,38.363,-108.116,38.501
coverage_bbox=-108.387,38.499,-107.521,38.751
coverage_bbox=-108.383,38.749,-106.825,39.001
coverage_bbox=-108.354,38.999,-106.979,39.251
coverage_bbox=-107.435,39.249,-107.377,39.262

license=Unknown (CWCB lidar portal; no use restriction published)
license_note=No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw, the PITKIN1M / CWCB1M reasoning for the CWCB portal)
attribution=Colorado Water Conservation Board — 2015 Western Colorado LiDAR point cloud (Quantum Spatial)

ladder_member=True
priority=90

enabled=True
