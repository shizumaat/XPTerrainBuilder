import Foundation

/// What a scenery pack primarily is — determines how performance findings
/// are judged and grouped (a library's textures don't all load; an airport's do).
public enum PackKind: String, Codable, Sendable, CaseIterable {
    case airport = "Airports"
    case landmark = "Landmarks & Overlays"
    case ortho = "Ortho Imagery"
    case mesh = "Mesh"
    case library = "Libraries"
    case other = "Other"
}

/// Where a pack stands with X-Plane.
public enum PackStatus: String, Codable, Sendable {
    /// In Custom Scenery, enabled in scenery_packs.ini.
    case enabled
    /// In Custom Scenery, SCENERY_PACK_DISABLED in the ini.
    case disabled
    /// Sitting in "Custom Scenery (Disabled)" — X-Plane never sees it.
    case uninstalled
}

/// An airport parsed from a pack's apt.dat, with chart position.
public struct AirportInfo: Codable, Sendable, Hashable {
    public let name: String
    public let latitude: Double
    public let longitude: Double
    /// From apt.dat 1302 metadata rows, when the author filled them in.
    public var city: String? = nil
    public var country: String? = nil

    public init(name: String, latitude: Double, longitude: Double,
                city: String? = nil, country: String? = nil) {
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.country = country
    }
}

/// One scenery pack, installed (Custom Scenery) or not (Custom Scenery (Disabled)).
public struct SceneryPack: Codable, Sendable {
    public let name: String
    public let url: URL
    /// var: ini-only pack actions (enable/disable, reorder) patch these in
    /// memory instead of rescanning 4,200 folders for an edit we made.
    public var status: PackStatus
    /// Priority from scenery_packs.ini; lower loads first (wins conflicts). nil = not listed.
    public var iniIndex: Int?
    public let isLibrary: Bool
    /// ICAO -> airport info, parsed from the pack's apt.dat (empty if none).
    public let airports: [String: AirportInfo]
    /// DSF tile names covered by this pack (e.g. "+41-073").
    public let tiles: Set<String>
    /// sim/overlay property from a sampled DSF: true = overlay scenery,
    /// false = base mesh, nil = no DSF sampled.
    public let isOverlay: Bool?
    /// True for packs shipped by Laminar (Global Airports etc.) that we skip for health checks.
    public let isLaminar: Bool
    /// Content-change hash (names/sizes/mtimes to depth 2 + every DSF) — the
    /// analysis cache key. Empty when unknown.
    public var signature: String = ""
    /// terrain/ contains .ter files — .ter-based scenery (ortho or mesh).
    public var hasTerrain: Bool = false
    /// textures/ holds photo-tile quantities of images (Ortho4XP-style).
    public var isPhotoTextured: Bool = false
    /// A plugins/ folder exists — the pack is a legitimate plugin carrier
    /// even with no DSF tiles or airports.
    public var hasPlugins: Bool = false
    /// Approximate size on disk (files to depth 3 + every DSF).
    public var sizeBytes: Int64 = 0
    /// Newest content mtime seen during the scan.
    public var modifiedDate: Date? = nil

    /// Resolved filesystem root for READING content — the symlink target
    /// when the pack folder is a symlink, else nil. FileManager's
    /// enumerator and contentsOfDirectory do NOT resolve a root that is
    /// itself a symlink, so every walk of a symlinked pack saw an empty
    /// folder (60% of the reference install analyzed blind until this).
    /// Identity, display and pack ACTIONS stay on `url`.
    public var resolvedURL: URL? = nil

    /// Where analyzers must walk from.
    public var contentRoot: URL { resolvedURL ?? url }

    public var isEnabled: Bool { status == .enabled }
    public var isInstalled: Bool { status != .uninstalled }
    public var hasDSF: Bool { !tiles.isEmpty }

    /// Classification is CONTENT-first — name hints only break ties. Name
    /// guessing misfiled orthos like z_SpainUHDv2 (no "ortho" in the name)
    /// as landmarks whenever the sampled DSF's overlay flag was unreadable.
    public var kind: PackKind {
        if isLibrary { return .library }
        if !airports.isEmpty { return .airport }
        guard hasDSF else { return .other }
        let lower = name.lowercased()
        if hasTerrain {
            // .ter-based scenery: photo-tile texture volume = ortho, a
            // handful of textures = elevation mesh. Names break ties.
            if isPhotoTextured { return .ortho }
            return lower.contains("ortho") || lower.contains("photo") ? .ortho : .mesh
        }
        if isOverlay == true { return .landmark }
        if isOverlay == false { return .mesh }
        // Overlay flag unknown (unreadable sample DSF), no terrain content.
        return lower.contains("mesh") ? .mesh : .landmark
    }
}

/// A pack's exact position on the map, when the scan can pin it more
/// precisely than the centroid of its tile coverage. The map applies these
/// over its own tile-centroid marks (MapOverlays.applyingExactMarkers) and
/// falls back to the centroid for any pack with no entry here.
public struct PackMarker: Sendable, Codable, Hashable {
    public let packName: String
    public let point: GeoPoint

    public init(packName: String, point: GeoPoint) {
        self.packName = packName
        self.point = point
    }
}

public struct Installation: Sendable {
    public let root: URL
    public let packs: [SceneryPack]
    /// Exact map marks produced by the scan — see PackMarker.
    public let packMarkers: [PackMarker]

    public init(root: URL, packs: [SceneryPack], packMarkers: [PackMarker] = []) {
        self.root = root
        self.packs = packs
        self.packMarkers = packMarkers
    }

    public var logURL: URL { root.appendingPathComponent("Log.txt") }
    public var customSceneryURL: URL { root.appendingPathComponent("Custom Scenery") }

    /// Same installation with the pack array swapped — for in-memory
    /// patches after ini-only actions the app itself performed.
    public func replacingPacks(_ newPacks: [SceneryPack]) -> Installation {
        Installation(root: root, packs: newPacks, packMarkers: packMarkers)
    }

    /// A folder looks like an X-Plane install if it has a Custom Scenery folder,
    /// a Log.txt, or the X-Plane executable/Resources layout.
    public static func looksLikeXPlaneRoot(_ url: URL) -> Bool {
        let fm = FileManager.default
        let candidates = ["Custom Scenery", "Log.txt", "Resources/default scenery"]
        return candidates.contains { fm.fileExists(atPath: url.appendingPathComponent($0).path) }
    }
}
