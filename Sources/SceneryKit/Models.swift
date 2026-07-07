import Foundation

/// Severity of a finding, ordered from most to least severe.
public enum Severity: String, Codable, CaseIterable, Comparable, Sendable {
    case error
    case warning
    case info

    private var rank: Int {
        switch self {
        case .error: return 0
        case .warning: return 1
        case .info: return 2
        }
    }

    public static func < (lhs: Severity, rhs: Severity) -> Bool {
        lhs.rank < rhs.rank
    }
}

/// High-level grouping used by the UI.
public enum FindingCategory: String, Codable, CaseIterable, Sendable {
    case installation = "Installation"
    case missingResource = "Missing Resources"
    case duplicatePackage = "Redundant Packages"
    case packageHealth = "Package Health"
    case performance = "Performance"
    /// Issues only the scenery's author can fix — useful when reporting
    /// upstream or developing your own packs, noise otherwise.
    case developerDebug = "Developer Debug"
    case unusedResources = "Unused Resources"
}

/// How actionable a finding is, mirroring the xpsan spec's fixability axis.
public enum Fixability: String, Codable, Sendable {
    case auto       // a safe mechanical edit could fix it
    case assisted   // the user can fix it with clear instructions
    case manual     // needs source assets / 3-D tooling / a download
}

/// A machine-applicable remediation attached to a finding. Applying one
/// always goes through FixEngine, which backs up the original first.
public enum ProposedFix: Codable, Sendable, Hashable {
    /// Insert `ATTR_LOD 0 <distance>` before the OBJ's first draw command so
    /// the object stops rendering beyond a distance suited to its size.
    case addFarLOD(objPath: String, distanceMeters: Int)
    /// Rename an encoding-damaged file (or folder) to the exact spelling the
    /// scenery references.
    case renameFile(fromPath: String, toPath: String)
    /// Re-encode a PNG as a mipmapped, block-compressed DDS and retire the
    /// PNG to a backup (X-Plane loads foo.dds wherever foo.png is referenced).
    /// Non-power-of-two images are resampled to the nearest power of two.
    case convertPNGToDDS(pngPath: String)
    /// Replace uniform per-mesh ATTR_no_blend with GLOBAL_no_blend so the
    /// object stays on the instanced drawing path.
    case promoteGlobalNoBlend(objPath: String)
    /// Insert `LOAD_CENTER <lat> <lon> <size m> <res px>` into a draped
    /// polygon so distant tiles load a lower-resolution texture (Laminar-
    /// endorsed; center/size computed from the DSF windings that use it).
    case insertLoadCenter(polPath: String, latitude: Double, longitude: Double,
                          sizeMeters: Int, resolutionPx: Int)
    /// Clamp every spill light larger than `maxRadiusMeters` down to it
    /// (LIGHT_SPILL_CUSTOM and full_custom_halo LIGHT_PARAMs — the forms
    /// whose size slot is unambiguous). Spill cost scales with covered
    /// screen area, so oversized radii are the classic night-FPS killer.
    /// Changes appearance slightly — offered, never auto-selected.
    case reduceSpillRadius(objPath: String, maxRadiusMeters: Int)
    /// Rewrite an all-opaque DXT5 DDS as DXT1 by dropping the (dead) alpha
    /// blocks — byte-exact colors, half the file size and VRAM.
    case stripDeadAlpha(ddsPath: String)
    /// Give every dropped ATC controller at `icao` an in-band VHF frequency:
    /// the published one (AirNav / OurAirports, fetched when the fix is
    /// applied) when available, otherwise an unused in-band channel — either
    /// way the "lost some controllers" error clears. Rows are added; the
    /// original UHF rows stay.
    case repairControllerFrequencies(aptPath: String, icao: String)

    public var summary: String {
        switch self {
        case .addFarLOD(_, let distance):
            return "Add far-cull LOD (\(distance) m)"
        case .renameFile(_, let toPath):
            return "Rename to '\(URL(fileURLWithPath: toPath).lastPathComponent)'"
        case .convertPNGToDDS:
            return "Convert PNG to DDS"
        case .promoteGlobalNoBlend:
            return "Promote ATTR_no_blend to GLOBAL_no_blend"
        case .insertLoadCenter(_, _, _, let size, _):
            return "Add LOAD_CENTER (\(size) m)"
        case .reduceSpillRadius(_, let radius):
            return "Clamp spill lights to \(radius) m"
        case .stripDeadAlpha:
            return "Strip unused alpha channel (DXT5 → DXT1)"
        case .repairControllerFrequencies(_, let icao):
            return "Add VHF frequency for \(icao)'s dropped controllers"
        }
    }

    /// True for fixes that visibly change how the scenery looks (however
    /// slightly). "Fix All" skips these — the user must select them
    /// deliberately.
    public var changesAppearance: Bool {
        if case .reduceSpillRadius = self { return true }
        return false
    }

    public var targetPath: String {
        switch self {
        case .addFarLOD(let path, _): return path
        case .renameFile(let fromPath, _): return fromPath
        case .convertPNGToDDS(let path): return path
        case .promoteGlobalNoBlend(let path): return path
        case .insertLoadCenter(let path, _, _, _, _): return path
        case .reduceSpillRadius(let path, _): return path
        case .stripDeadAlpha(let path): return path
        case .repairControllerFrequencies(let path, _): return path
        }
    }
}

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

public struct Finding: Identifiable, Codable, Sendable, Hashable {
    /// One pack involved in a multi-pack finding (DUP-02's disabled list,
    /// DUP-03's near-identical folders). Name for viewport filtering, full
    /// path so the UI can identify and reveal each folder individually —
    /// names alone cannot distinguish same-named packs in Custom Scenery
    /// and Custom Scenery (Disabled).
    public struct RelatedPack: Codable, Sendable, Hashable {
        public let name: String
        public let path: String

        public init(name: String, path: String) {
            self.name = name
            self.path = path
        }
    }

    public let id: UUID
    public let checkID: String
    public let severity: Severity
    public let category: FindingCategory
    public let title: String
    public let detail: String
    /// Absolute path of the file or folder this finding refers to, if any.
    public let path: String?
    public let suggestion: String?
    /// A helpful link (e.g. an x-plane.org download page for a missing library).
    public let url: URL?
    public let fixability: Fixability
    public let proposedFix: ProposedFix?
    /// The pack this finding belongs to, for grouping (nil for install-wide).
    public let packName: String?
    public let packKind: PackKind?
    /// Every pack a multi-pack finding involves (nil for single-pack or truly
    /// install-wide findings). Lets the viewport filter apply to aggregates
    /// that have no single packName. Optional: older report JSONs decode fine.
    public let relatedPacks: [RelatedPack]?

    public init(
        checkID: String,
        severity: Severity,
        category: FindingCategory,
        title: String,
        detail: String,
        path: String? = nil,
        suggestion: String? = nil,
        url: URL? = nil,
        fixability: Fixability = .manual,
        proposedFix: ProposedFix? = nil,
        packName: String? = nil,
        packKind: PackKind? = nil,
        relatedPacks: [RelatedPack]? = nil
    ) {
        self.id = UUID()
        self.checkID = checkID
        self.severity = severity
        self.category = category
        self.title = title
        self.detail = detail
        self.path = path
        self.suggestion = suggestion
        self.url = url
        self.fixability = fixability
        self.proposedFix = proposedFix
        self.packName = packName
        self.packKind = packKind
        self.relatedPacks = relatedPacks
    }

    /// Copy with different title/detail (and optionally a narrowed related-
    /// pack list), preserving identity — for display-side filtering of
    /// aggregate findings (fresh UUIDs would churn List diffing and drop
    /// selections on every render).
    public func withContent(title newTitle: String? = nil, detail newDetail: String,
                            relatedPacks newRelated: [RelatedPack]? = nil) -> Finding {
        Finding(
            id: id, checkID: checkID, severity: severity, category: category,
            title: newTitle ?? title, detail: newDetail, path: path, suggestion: suggestion,
            url: url, fixability: fixability, proposedFix: proposedFix,
            packName: packName, packKind: packKind,
            relatedPacks: newRelated ?? relatedPacks
        )
    }

    /// Copy with pack attribution added, preserving identity. Existing
    /// attribution wins.
    public func attributed(packName: String?, packKind: PackKind? = nil) -> Finding {
        guard self.packName == nil, packName != nil else { return self }
        return Finding(
            id: id, checkID: checkID, severity: severity, category: category,
            title: title, detail: detail, path: path, suggestion: suggestion,
            url: url, fixability: fixability, proposedFix: proposedFix,
            packName: packName, packKind: packKind ?? self.packKind,
            relatedPacks: relatedPacks
        )
    }

    init(id: UUID, checkID: String, severity: Severity, category: FindingCategory,
         title: String, detail: String, path: String?, suggestion: String?,
         url: URL?, fixability: Fixability, proposedFix: ProposedFix?,
         packName: String?, packKind: PackKind?, relatedPacks: [RelatedPack]?) {
        self.id = id
        self.checkID = checkID
        self.severity = severity
        self.category = category
        self.title = title
        self.detail = detail
        self.path = path
        self.suggestion = suggestion
        self.url = url
        self.fixability = fixability
        self.proposedFix = proposedFix
        self.packName = packName
        self.packKind = packKind
        self.relatedPacks = relatedPacks
    }
}

/// Summary counters shown at the top of the report.
public struct AnalysisStats: Codable, Sendable {
    public init() {}

    public var packsScanned = 0
    public var libraryPacks = 0
    public var logLinesScanned = 0
    public var objFilesParsed = 0
    public var texturesInspected = 0
    public var airportsIndexed = 0
    /// Packs whose analysis was served from the signature cache (optional
    /// so pre-cache report JSONs still decode).
    public var packsFromCache: Int? = nil
}

/// One package's role in a duplicated airport, for the actionable table UI.
public struct DuplicatePack: Codable, Sendable, Hashable, Identifiable {
    public var id: String { name }
    public let name: String
    public let path: String
    /// Load priority from scenery_packs.ini (lower loads first / wins).
    public let iniIndex: Int?
    /// True for the pack X-Plane will actually show for this airport.
    public let isWinner: Bool
    /// Total size on disk in bytes (0 if not computed).
    public let sizeBytes: Int64
    public let kind: PackKind?
    /// Folder modification date.
    public let modifiedDate: Date?
    public let status: PackStatus?

    public var isEnabled: Bool { (status ?? .enabled) == .enabled }

    public init(name: String, path: String, status: PackStatus, iniIndex: Int?, isWinner: Bool,
                sizeBytes: Int64 = 0, kind: PackKind? = nil, modifiedDate: Date? = nil) {
        self.name = name
        self.path = path
        self.status = status
        self.iniIndex = iniIndex
        self.isWinner = isWinner
        self.sizeBytes = sizeBytes
        self.kind = kind
        self.modifiedDate = modifiedDate
    }
}

/// A file in a pack that nothing references (dead ortho source images,
/// leftover .ter sets, …).
public struct UnusedFile: Codable, Sendable, Hashable, Identifiable {
    public var id: String { path }
    public let path: String
    public let sizeBytes: Int64
    public let modifiedDate: Date?

    public init(path: String, sizeBytes: Int64, modifiedDate: Date? = nil) {
        self.path = path
        self.sizeBytes = sizeBytes
        self.modifiedDate = modifiedDate
    }
}

public struct UnusedResourceGroup: Codable, Sendable, Identifiable {
    public var id: String { packName }
    public let packName: String
    public let packPath: String
    public var files: [UnusedFile]

    public var totalBytes: Int64 { files.reduce(0) { $0 + $1.sizeBytes } }

    public init(packName: String, packPath: String, files: [UnusedFile]) {
        self.packName = packName
        self.packPath = packPath
        self.files = files
    }
}

/// An airport provided by two or more custom packs.
public struct DuplicateGroup: Codable, Sendable, Identifiable {
    public var id: String { icao }
    public let icao: String
    public let airportName: String
    public let packs: [DuplicatePack]

    public init(icao: String, airportName: String, packs: [DuplicatePack]) {
        self.icao = icao
        self.airportName = airportName
        self.packs = packs
    }
}

public struct AnalysisReport: Codable, Sendable {
    public let generatedAt: Date
    public let xplaneRoot: String
    public var findings: [Finding]
    public var stats: AnalysisStats
    public var duplicateGroups: [DuplicateGroup]
    public var unusedResources: [UnusedResourceGroup]
    /// The hardware the analysis was judged against.
    public var system: SystemInfo?
    /// Human-readable scope ("12 selected packages"); nil = whole install.
    public var scopeDescription: String?
    /// Exact map positions (object-placement centroids) for small-footprint
    /// packs, from DSF geometry. Optional: pre-placement reports decode fine.
    public var packMarkers: [String: GeoPoint]?

    public init(
        xplaneRoot: String,
        findings: [Finding],
        stats: AnalysisStats,
        duplicateGroups: [DuplicateGroup] = [],
        unusedResources: [UnusedResourceGroup] = [],
        system: SystemInfo? = nil,
        scopeDescription: String? = nil
    ) {
        self.generatedAt = Date()
        self.xplaneRoot = xplaneRoot
        self.findings = findings
        self.stats = stats
        self.duplicateGroups = duplicateGroups
        self.unusedResources = unusedResources
        self.system = system
        self.scopeDescription = scopeDescription
    }

    public var errorCount: Int { findings.filter { $0.severity == .error }.count }
    public var warningCount: Int { findings.filter { $0.severity == .warning }.count }
    public var infoCount: Int { findings.filter { $0.severity == .info }.count }

    public func jsonData() throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        return try encoder.encode(self)
    }
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
    public let status: PackStatus
    /// Priority from scenery_packs.ini; lower loads first (wins conflicts). nil = not listed.
    public let iniIndex: Int?
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
    /// Approximate size on disk (files to depth 3 + every DSF).
    public var sizeBytes: Int64 = 0
    /// Newest content mtime seen during the scan.
    public var modifiedDate: Date? = nil

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

public struct Installation: Sendable {
    public let root: URL
    public let packs: [SceneryPack]
    public let libraryIndex: LibraryIndex
    /// Exports of X-Plane's own libraries (Resources/default scenery) —
    /// required to audit references without crying wolf on lib/… paths.
    public let defaultLibraryIndex: LibraryIndex

    public var logURL: URL { root.appendingPathComponent("Log.txt") }
    public var customSceneryURL: URL { root.appendingPathComponent("Custom Scenery") }

    /// A folder looks like an X-Plane install if it has a Custom Scenery folder,
    /// a Log.txt, or the X-Plane executable/Resources layout.
    public static func looksLikeXPlaneRoot(_ url: URL) -> Bool {
        let fm = FileManager.default
        let candidates = ["Custom Scenery", "Log.txt", "Resources/default scenery"]
        return candidates.contains { fm.fileExists(atPath: url.appendingPathComponent($0).path) }
    }
}
