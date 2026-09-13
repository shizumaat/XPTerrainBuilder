import Foundation

/// The curated settings organization, mirroring the Qt UI's registry
/// (O4_Settings_Model._LAYOUT) category for category and row for row. Each
/// row names an engine config variable; its type, allowed values, default
/// and hint come from the engine's schema at runtime, so an engine update
/// can refine a row without an app change. Rows whose variable a given
/// engine doesn't know are simply not shown.
struct SettingItem: Identifiable, Equatable {
    enum Scope: Equatable {
        /// App-wide engine setting — always edits the global Ortho4XP.cfg.
        case app
        /// Tile setting — edits the selected tiles' configs when tiles are
        /// selected on the map, else the global defaults (Qt semantics).
        case tile
    }

    let name: String
    let label: String
    let scope: Scope
    let advanced: Bool
    var id: String { name }

    init(_ name: String, _ label: String, _ scope: Scope, advanced: Bool = false) {
        self.name = name
        self.label = label
        self.scope = scope
        self.advanced = advanced
    }
}

struct SettingCategory: Identifiable, Equatable {
    let key: String
    let title: String
    let icon: String
    let items: [SettingItem]
    var id: String { key }
}

enum SettingsLayout {
    /// Engine app-level rows folded into the General pane (the Qt "General"
    /// category minus the Qt-app-only path preferences, which the mac app
    /// covers with its own X-Plane and data-folder settings).
    static let engineGeneral: [SettingItem] = [
        SettingItem("custom_scenery_dir", "X-Plane Custom Scenery folder", .app),
        SettingItem("custom_overlay_src", "Overlay source scenery folder", .app),
        SettingItem("custom_overlay_src_alternate", "Alternate overlay source", .app, advanced: true),
        SettingItem("cifp_data_path", "CIFP/AIRAC data folder", .app, advanced: true),
        SettingItem("verbosity", "Console output", .app),
        SettingItem("cleaning_level", "Build file cleanup level", .app),
    ]

    static let categories: [SettingCategory] = [
        SettingCategory(key: "network", title: "Performance & Network", icon: "speedometer", items: [
            SettingItem("max_build_slots", "Parallel tile builds", .app),
            SettingItem("max_download_slots", "Parallel orthophoto downloads", .app),
            SettingItem("max_convert_slots", "Parallel DDS conversions", .app),
            SettingItem("overpass_server_choice", "OSM Overpass server", .app),
            SettingItem("osm_regional_extracts", "OSM regional extracts", .app),
            SettingItem("osm_extract_refresh_days", "Extract refresh age (days)", .app, advanced: true),
            SettingItem("http_timeout", "HTTP timeout (s)", .app, advanced: true),
            SettingItem("max_connect_retries", "Connection retries", .app, advanced: true),
            SettingItem("max_baddata_retries", "Bad-data retries", .app, advanced: true),
            SettingItem("check_tms_response", "Retry on imagery server errors", .app, advanced: true),
        ]),
        SettingCategory(key: "imagery", title: "Imagery & Zoom Levels", icon: "photo", items: [
            SettingItem("texture_mode", "Texture mode", .tile),
            SettingItem("airport_ortho_fade_width", "Airport ortho fade width (m)", .tile),
            SettingItem("cover_airports_with_highres", "Airport imagery upgrade", .tile),
            SettingItem("cover_zl", "Airport coverage ZL", .tile),
            SettingItem("cover_extent", "Airport coverage extent (km)", .tile),
            SettingItem("sea_texture_blur", "Sea texture blur (m)", .tile, advanced: true),
            SettingItem("sea_nodata_fill", "Repair imagery no-data over water", .tile),
            SettingItem("color_harmonization", "Harmonize texture colors", .tile),
            SettingItem("skip_downloads", "Skip imagery downloads", .app, advanced: true),
            SettingItem("skip_converts", "Skip DDS conversion", .app, advanced: true),
        ]),
        SettingCategory(key: "mesh", title: "Mesh", icon: "triangle", items: [
            SettingItem("curvature_tol", "Curvature tolerance", .tile),
            SettingItem("apt_curv_tol", "Airport curvature tolerance", .tile),
            SettingItem("apt_curv_ext", "Airport curvature extent (km)", .tile),
            SettingItem("coast_curv_tol", "Coastline curvature tolerance", .tile),
            SettingItem("coast_curv_ext", "Coastline curvature extent (km)", .tile),
            SettingItem("limit_tris", "Max triangles (millions)", .tile),
            SettingItem("min_angle", "Min triangle angle (°)", .tile, advanced: true),
            SettingItem("sea_smoothing_mode", "Sea surface smoothing", .tile, advanced: true),
            SettingItem("water_smoothing", "Inland water smoothing passes", .tile, advanced: true),
            SettingItem("mesh_zl", "Max imagery zoom the mesh allows", .tile, advanced: true),
        ]),
        SettingCategory(key: "elevation", title: "Elevation", icon: "mountain.2", items: [
            SettingItem("elevation_level", "Tile elevation detail level", .tile),
            SettingItem("elevation_coastline_band_km", "Coastline lidar band width (km)", .tile, advanced: true),
            SettingItem("base_elevation_source", "Base elevation source", .app),
            SettingItem("custom_dem", "Custom elevation data (DEM)", .tile),
            SettingItem("fill_nodata", "Fill missing elevation data", .tile),
            SettingItem("auto_patch", "Auto-patch airports (runway slopes)", .tile),
            SettingItem("modify_custom_airports", "Modify custom airports (reseat objects)", .tile),
            SettingItem("airport_elevation_insets", "Fetch airport lidar insets", .tile),
            SettingItem("airport_elevation_level", "Airport elevation detail level", .tile),
            SettingItem("airport_elevation_inset_margin_m", "Lidar extent beyond airport (m)", .tile),
            SettingItem("airport_elevation_inset_feather_m", "Lidar edge blend width (m)", .tile),
            SettingItem("airport_elevation_providers", "Inset providers", .tile, advanced: true),
            SettingItem("airport_inset_water", "Detect ponds in lidar", .tile, advanced: true),
            SettingItem("apt_smoothing_pix", "Airport elevation smoothing (px)", .tile, advanced: true),
            SettingItem("apt_smoothing_auto", "Scale smoothing to data quality", .tile, advanced: true),
            SettingItem("working_grid_arc_seconds", "Working grid spacing", .tile, advanced: true),
            SettingItem("iterate", "Iterative DEM refinement step", .tile, advanced: true),
        ]),
        SettingCategory(key: "vector", title: "Roads & OSM Data", icon: "road.lanes", items: [
            SettingItem("road_level", "Road detail level", .tile),
            SettingItem("road_banking_limit", "Road banking limit (m)", .tile, advanced: true),
            SettingItem("lane_width", "Road lane width (m)", .tile, advanced: true),
            SettingItem("max_levelled_segs", "Max levelled road segments", .tile, advanced: true),
            SettingItem("clean_bad_geometries", "Repair bad OSM geometries", .tile, advanced: true),
        ]),
        SettingCategory(key: "water", title: "Water & Masks", icon: "drop", items: [
            SettingItem("water_tech", "Water rendering tech", .tile),
            SettingItem("water_simplification", "Water node simplification (m)", .tile, advanced: true),
            SettingItem("min_area", "Min water area (km²)", .tile, advanced: true),
            SettingItem("max_area", "Max unmasked water area (km²)", .tile, advanced: true),
            SettingItem("ratio_water", "Water transparency ratio", .tile),
            SettingItem("ratio_bathy", "Bathymetry multiplier", .tile),
            SettingItem("mask_zl", "Water mask resolution", .tile),
            SettingItem("masks_width", "Mask width (m)", .tile),
            SettingItem("masking_mode", "Coastline mask style", .tile),
            SettingItem("inland_shore_feather_m", "Inland shore feather (m)", .tile),
            SettingItem("coastal_foam_edge", "Wavy shoreline with foam band", .tile),
            SettingItem("use_masks_for_inland", "Mask inland water", .tile, advanced: true),
            SettingItem("imprint_masks_to_dds", "Imprint masks into DDS", .tile, advanced: true),
            SettingItem("distance_masks_too", "Build distance masks", .tile, advanced: true),
            SettingItem("masks_custom_extent", "Custom mask extent", .tile, advanced: true),
        ]),
        SettingCategory(key: "bathymetry", title: "Bathymetry", icon: "water.waves", items: [
            SettingItem("masks_use_DEM_too", "Measured depth in masks", .tile),
            SettingItem("bathymetry_airport_radius_km", "Fetch radius around anchors (km)", .tile),
            SettingItem("bathymetry_near_icao_airports", "Near ICAO airports", .tile),
            SettingItem("bathymetry_near_other_airports", "Near small airfields (no ICAO)", .tile),
            SettingItem("bathymetry_near_seaplane_bases", "Near seaplane bases", .tile),
            SettingItem("bathymetry_near_heliports", "Near heliports", .tile),
            SettingItem("reef_visibility_depth", "Reef visibility depth (m)", .tile),
            SettingItem("osm_shallow_water_fallback", "Mapped shallow-water fallback", .tile),
            SettingItem("bathymetry_band_km", "Band width along shoreline (km)", .tile, advanced: true),
            SettingItem("dsf_bathymetry", "DSF sea level raster source", .tile, advanced: true),
        ]),
        SettingCategory(key: "rendering", title: "Rendering & Overlays", icon: "sparkles", items: [
            SettingItem("overlay_lod", "Overlay draw distance (m)", .tile),
            SettingItem("terrain_casts_shadows", "Terrain casts shadows", .tile),
            SettingItem("use_decal_on_terrain", "Terrain decal detail", .tile),
            SettingItem("normal_map_strength", "Normal map strength", .tile, advanced: true),
            SettingItem("ovl_exclude_pol", "Exclude overlay polygon types", .app, advanced: true),
            SettingItem("ovl_exclude_net", "Exclude overlay road types", .app, advanced: true),
        ]),
    ]

    /// Every row that participates in search: the General engine rows plus
    /// all category rows, tagged with their category title.
    static let searchIndex: [(category: String, item: SettingItem)] =
        engineGeneral.map { ("General", $0) }
        + categories.flatMap { category in category.items.map { (category.title, $0) } }
}
