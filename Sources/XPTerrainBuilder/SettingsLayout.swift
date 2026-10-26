import Foundation
import SceneryKit

/// The curated settings organization and its WORDING (issue #823),
/// mirroring the Qt UI's registry (O4_Settings_Model._LAYOUT) category for
/// category and row for row — `Ortho4XP/tests/test_settings_layout_parity.py`
/// parses this file and fails when the two differ. Each row names an engine
/// config variable; its type, allowed values, default and full hint come
/// from the engine's schema at runtime, so an engine update can refine a row
/// without an app change. Rows whose variable a given engine doesn't know
/// are simply not shown.
///
/// A row outside Expert is a plain question (or a glossary term, #831) with
/// a one-line `summary`; the row adds the recommended value (the schema
/// default). An Expert row keeps its technical label and shows the config
/// name as secondary text, so forum advice still maps to it. Expert rows
/// come last in a category and form its collapsed Expert section. Wording
/// and grouping only: config KEYS and stored values never change with them.
struct SettingItem: Identifiable, Equatable {
    enum Scope: Equatable {
        /// App-wide engine setting — always edits the global XPTerrainBuilder.cfg.
        case app
        /// Tile setting — edits the selected tiles' configs when tiles are
        /// selected on the map, else the global defaults (Qt semantics).
        case tile
    }

    let name: String
    let label: String
    let scope: Scope
    let expert: Bool
    let summary: String
    var id: String { name }

    init(_ name: String, _ label: String, _ scope: Scope,
         expert: Bool = false, summary: String = "") {
        self.name = name
        self.label = label
        self.scope = scope
        self.expert = expert
        self.summary = summary
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
    /// The Expert section's title, and the words of a row's secondary line
    /// (Qt: O4_Settings_Model.EXPERT_TITLE, RECOMMENDED_PREFIX,
    /// SECONDARY_SEPARATOR).
    static let expertTitle = "Expert"
    static let recommendedPrefix = "Recommended: "
    static let secondarySeparator = " · "

    /// The grey line under a row (Qt: `Setting.secondary_text`): outside
    /// Expert the summary, in Expert the config name; then the recommended
    /// value, which is the schema default as the row's control shows it.
    static func secondaryText(_ item: SettingItem,
                              _ variable: OrthoConfigSchema.Variable) -> String {
        let head = item.expert ? item.name : item.summary
        let raw = variable.default.cfgLiteral
        let recommended: String
        if raw.isEmpty {
            recommended = ""
        } else if variable.type == "bool", raw == "True" || raw == "False" {
            recommended = raw == "True" ? "On" : "Off"
        } else {
            recommended = variable.label(forValue: raw)
        }
        if recommended.isEmpty { return head }
        let tail = recommendedPrefix + recommended
        return head.isEmpty ? tail : head + secondarySeparator + tail
    }

    /// Engine app-level rows folded into the General pane (the Qt "General"
    /// category minus the Qt-app-only path preferences, which the mac app
    /// covers with its own X-Plane and data-folder settings).
    static let engineGeneral: [SettingItem] = [
        SettingItem("custom_scenery_dir", "Where is X-Plane's Custom Scenery folder?", .app, summary: "Finished tiles are linked into it so X-Plane finds them."),
        SettingItem("custom_overlay_src", "Where should roads, forests and buildings come from?", .app, summary: "An X-Plane scenery folder, usually Global Scenery."),
        SettingItem("verbosity", "How much should the console show?", .app, summary: "More detail helps when you report a problem."),
        SettingItem("cleaning_level", "Which build files should be kept?", .app, summary: "Keeping more makes a rebuild faster but uses more disk."),
        SettingItem("custom_overlay_src_alternate", "Alternate overlay source", .app, expert: true),
        SettingItem("cifp_data_path", "X-Plane's runway data folder", .app, expert: true),
    ]

    static let categories: [SettingCategory] = [
        SettingCategory(key: "network", title: "Speed & Downloads", icon: "speedometer", items: [
            SettingItem("max_build_slots", "How many tiles should build at once?", .app, summary: "Auto uses this machine's processor cores."),
            SettingItem("max_download_slots", "How many imagery downloads should run at once?", .app, summary: "Auto suits most connections."),
            SettingItem("max_convert_slots", "How many imagery files should be converted at once?", .app, summary: "Auto uses every processor core but two."),
            SettingItem("overpass_server_choice", "Map data server", .app, summary: "Where map data downloads from when no stored regional copy covers the tile."),
            SettingItem("osm_regional_extracts", "Use stored regional map data when available?", .app, summary: "Faster than downloading each tile, and kinder to the map servers."),
            SettingItem("osm_extract_refresh_days", "Extract refresh age (days)", .app, expert: true),
            SettingItem("http_timeout", "HTTP timeout (s)", .app, expert: true),
            SettingItem("max_connect_retries", "Connection retries", .app, expert: true),
            SettingItem("max_baddata_retries", "Bad-data retries", .app, expert: true),
            SettingItem("check_tms_response", "Retry on imagery server errors", .app, expert: true),
        ]),
        SettingCategory(key: "imagery", title: "Imagery", icon: "photo", items: [
            SettingItem("cover_airports_with_highres", "Use sharper imagery at airports?", .tile, summary: "The same photos at a finer detail; more download and disk."),
            SettingItem("cover_zl", "Which ZL should the airport imagery use?", .tile, summary: "ZL17 is about 1 m per pixel, ZL18 about 0.6 m."),
            SettingItem("cover_extent", "How far past the airport should it reach (km)?", .tile, summary: "The sharper imagery covers the airport and this band around it."),
            SettingItem("sea_nodata_fill", "Repair blank spots in imagery over the sea?", .tile, summary: "Fills the white or black rectangles some providers leave over coastal water."),
            SettingItem("color_harmonization", "Even out imagery colors across the tile?", .tile, summary: "Removes the patchwork of different photo dates and providers."),
            SettingItem("texture_mode", "Texture mode", .tile, expert: true),
            SettingItem("airport_ortho_fade_width", "Airport ortho fade width (m)", .tile, expert: true),
            SettingItem("sea_texture_blur", "Sea texture blur (m)", .tile, expert: true),
            SettingItem("skip_downloads", "Skip imagery downloads", .app, expert: true),
            SettingItem("skip_converts", "Skip DDS conversion", .app, expert: true),
        ]),
        SettingCategory(key: "mesh", title: "Ground Shape", icon: "triangle", items: [
            SettingItem("curvature_tol", "Curvature tolerance", .tile, expert: true),
            SettingItem("apt_curv_tol", "Airport curvature tolerance", .tile, expert: true),
            SettingItem("apt_curv_ext", "Airport curvature extent (km)", .tile, expert: true),
            SettingItem("coast_curv_tol", "Coastline curvature tolerance", .tile, expert: true),
            SettingItem("coast_curv_ext", "Coastline curvature extent (km)", .tile, expert: true),
            SettingItem("limit_tris", "Max triangles (millions)", .tile, expert: true),
            SettingItem("min_angle", "Min triangle angle (°)", .tile, expert: true),
            SettingItem("sea_smoothing_mode", "Sea surface smoothing", .tile, expert: true),
            SettingItem("water_smoothing", "Inland water smoothing passes", .tile, expert: true),
            SettingItem("mesh_zl", "Max imagery zoom the mesh allows", .tile, expert: true),
        ]),
        SettingCategory(key: "elevation", title: "Elevation & Airports", icon: "mountain.2", items: [
            SettingItem("elevation_level", "How detailed should the elevation be?", .tile, summary: "Auto uses 90 m data with high-resolution data at airports."),
            SettingItem("base_elevation_source", "Which elevation source should be used?", .app, summary: "Auto picks the best source available for the tile."),
            SettingItem("custom_dem", "Use your own elevation file?", .tile, summary: "Used instead of the downloaded elevation. Leave empty for automatic."),
            SettingItem("fill_nodata", "Fill gaps in the elevation data?", .tile, summary: "Off turns gaps into sea level."),
            SettingItem("auto_patch", "Grade airports to official standards (FAA / ICAO / EASA)", .tile, summary: "Shapes runways and taxiways to the slope rules, from X-Plane's runway data."),
            // App-level, not tile-level: a preference about how the user is
            // asked, not a property of a tile (spec §C.4, RULINGS 18a).
            SettingItem("auto_patch_boundary", "What if an airport crosses a tile edge?", .app, summary: "Its ground shape needs the elevation of the tile next door too."),
            SettingItem("modify_custom_airports", "Fit custom airport buildings to the new ground", .tile, summary: "Moves the 3-D objects of installed custom airports onto the reshaped ground."),
            SettingItem("airport_elevation_insets", "High-resolution airport elevation", .tile, summary: "Downloads meter-class elevation for the airports where it exists."),
            SettingItem("airport_elevation_level", "How detailed should airport elevation be?", .tile, summary: "Auto takes the finest available, down to 0.5 m."),
            SettingItem("elevation_coastline_band_km", "Coastline lidar band width (km)", .tile, expert: true),
            SettingItem("airport_elevation_inset_margin_m", "Lidar extent beyond airport (m)", .tile, expert: true),
            SettingItem("airport_elevation_inset_feather_m", "Lidar edge blend width (m)", .tile, expert: true),
            SettingItem("airport_elevation_providers", "Inset providers", .tile, expert: true),
            SettingItem("airport_inset_water", "Detect ponds in lidar", .tile, expert: true),
            SettingItem("apt_smoothing_pix", "Airport elevation smoothing (px)", .tile, expert: true),
            SettingItem("apt_smoothing_auto", "Scale smoothing to data quality", .tile, expert: true),
            SettingItem("working_grid_arc_seconds", "Working grid spacing", .tile, expert: true),
            SettingItem("iterate", "Iterative DEM refinement step", .tile, expert: true),
        ]),
        SettingCategory(key: "vector", title: "Roads & Map Data", icon: "road.lanes", items: [
            SettingItem("road_level", "Which roads should the ground be levelled for?", .tile, summary: "Flattens the ground under roads and railways so they do not tilt."),
            SettingItem("road_banking_limit", "Road banking limit (m)", .tile, expert: true),
            SettingItem("lane_width", "Road lane width (m)", .tile, expert: true),
            SettingItem("max_levelled_segs", "Max levelled road segments", .tile, expert: true),
            SettingItem("clean_bad_geometries", "Repair bad OSM geometries", .tile, expert: true),
        ]),
        SettingCategory(key: "water", title: "Water & Coastlines", icon: "drop", items: [
            SettingItem("water_tech", "Which water should X-Plane draw?", .tile, summary: "XP12 uses X-Plane 12's water; XP11 + bathy blends the older way."),
            SettingItem("ratio_water", "How much photo should show through lakes and rivers?", .tile, summary: "0 is plain X-Plane water, 1 is the photo only."),
            SettingItem("masking_mode", "What should the shoreline look like?", .tile, summary: "How the land fades into the sea."),
            SettingItem("coastal_foam_edge", "Draw a wavy shoreline with a foam band?", .tile, summary: "Replaces the straight land-to-water fade with a more natural edge."),
            SettingItem("ratio_bathy", "Bathymetry multiplier", .tile, expert: true),
            SettingItem("mask_zl", "Water mask resolution", .tile, expert: true),
            SettingItem("masks_width", "Mask width (m)", .tile, expert: true),
            SettingItem("inland_shore_feather_m", "Inland shore feather (m)", .tile, expert: true),
            SettingItem("water_simplification", "Water node simplification (m)", .tile, expert: true),
            SettingItem("min_area", "Min water area (km²)", .tile, expert: true),
            SettingItem("max_area", "Max unmasked water area (km²)", .tile, expert: true),
            SettingItem("use_masks_for_inland", "Mask inland water", .tile, expert: true),
            SettingItem("imprint_masks_to_dds", "Imprint masks into DDS", .tile, expert: true),
            SettingItem("distance_masks_too", "Build distance masks", .tile, expert: true),
            SettingItem("masks_custom_extent", "Custom mask extent", .tile, expert: true),
        ]),
        SettingCategory(key: "bathymetry", title: "Underwater Depth", icon: "water.waves", items: [
            SettingItem("masks_use_DEM_too", "Use measured sea depth along the shore?", .tile, summary: "Auto uses it near airports, where you fly low over the water."),
            SettingItem("bathymetry_airport_radius_km", "How far from those places should it be used (km)?", .tile, summary: "In Auto, depth is fetched for shoreline this close to the places ticked below."),
            SettingItem("bathymetry_near_icao_airports", "Use it near airports with ICAO codes?", .tile, summary: "Where airline and general-aviation approaches cross the water."),
            SettingItem("bathymetry_near_other_airports", "Use it near small airfields?", .tile, summary: "Grass strips, bush fields and other fields without an ICAO code."),
            SettingItem("bathymetry_near_seaplane_bases", "Use it near seaplane bases?", .tile, summary: "Few of them, and you land on the water there."),
            SettingItem("bathymetry_near_heliports", "Use it near heliports?", .tile, summary: "Many of them, so this costs the most download."),
            SettingItem("reef_visibility_depth", "How deep can the sea floor be and still show (m)?", .tile, summary: "Shallower water keeps part of the photo visible, like reefs and sandbanks."),
            SettingItem("osm_shallow_water_fallback", "Use mapped shallow water where no depth is measured?", .tile, summary: "Mapped reefs and shoals keep their photo where no measured depth applies."),
            SettingItem("bathymetry_band_km", "Band width along shoreline (km)", .tile, expert: true),
            SettingItem("dsf_bathymetry", "DSF sea level raster source", .tile, expert: true),
        ]),
        SettingCategory(key: "rendering", title: "Look in the Sim", icon: "sparkles", items: [
            SettingItem("overlay_lod", "How far away should photos over water be drawn (m)?", .tile, summary: "A shorter distance helps frame rate and video memory."),
            SettingItem("terrain_casts_shadows", "Should the ground cast shadows?", .tile, summary: "Only matters when scenery shadows are on in X-Plane."),
            SettingItem("use_decal_on_terrain", "Add fine ground detail up close?", .tile, summary: "Noticeable at very low altitude."),
            SettingItem("normal_map_strength", "Normal map strength", .tile, expert: true),
            SettingItem("ovl_exclude_pol", "Exclude overlay polygon types", .app, expert: true),
            SettingItem("ovl_exclude_net", "Exclude overlay road types", .app, expert: true),
        ]),
    ]

    /// Every row that participates in search: the General engine rows plus
    /// all category rows, tagged with their category title.
    static let searchIndex: [(category: String, item: SettingItem)] =
        engineGeneral.map { ("General", $0) }
        + categories.flatMap { category in category.items.map { (category.title, $0) } }
}
