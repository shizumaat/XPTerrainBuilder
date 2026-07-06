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

    public var summary: String {
        switch self {
        case .addFarLOD(_, let distance):
            return "Add far-cull LOD (\(distance) m)"
        }
    }

    public var targetPath: String {
        switch self {
        case .addFarLOD(let path, _): return path
        }
    }
}

public struct Finding: Identifiable, Codable, Sendable, Hashable {
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
        proposedFix: ProposedFix? = nil
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
}

/// One package's role in a duplicated airport, for the actionable table UI.
public struct DuplicatePack: Codable, Sendable, Hashable, Identifiable {
    public var id: String { name }
    public let name: String
    public let path: String
    public let isEnabled: Bool
    /// Load priority from scenery_packs.ini (lower loads first / wins).
    public let iniIndex: Int?
    /// True for the pack X-Plane will actually show for this airport.
    public let isWinner: Bool
    /// Total size on disk in bytes (0 if not computed).
    public let sizeBytes: Int64

    public init(name: String, path: String, isEnabled: Bool, iniIndex: Int?, isWinner: Bool, sizeBytes: Int64 = 0) {
        self.name = name
        self.path = path
        self.isEnabled = isEnabled
        self.iniIndex = iniIndex
        self.isWinner = isWinner
        self.sizeBytes = sizeBytes
    }
}

/// A file in a pack that nothing references (dead ortho source images,
/// leftover .ter sets, …).
public struct UnusedFile: Codable, Sendable, Hashable, Identifiable {
    public var id: String { path }
    public let path: String
    public let sizeBytes: Int64

    public init(path: String, sizeBytes: Int64) {
        self.path = path
        self.sizeBytes = sizeBytes
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

    public init(
        xplaneRoot: String,
        findings: [Finding],
        stats: AnalysisStats,
        duplicateGroups: [DuplicateGroup] = [],
        unusedResources: [UnusedResourceGroup] = []
    ) {
        self.generatedAt = Date()
        self.xplaneRoot = xplaneRoot
        self.findings = findings
        self.stats = stats
        self.duplicateGroups = duplicateGroups
        self.unusedResources = unusedResources
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

/// One installed scenery pack under Custom Scenery.
public struct SceneryPack: Sendable {
    public let name: String
    public let url: URL
    public let isEnabled: Bool
    /// Priority from scenery_packs.ini; lower loads first (wins conflicts). nil = not listed.
    public let iniIndex: Int?
    public let isLibrary: Bool
    /// ICAO -> airport name, parsed from the pack's apt.dat (empty if none).
    public let airports: [String: String]
    public let hasDSF: Bool
    /// True for packs shipped by Laminar (Global Airports etc.) that we skip for health checks.
    public let isLaminar: Bool
}

public struct Installation: Sendable {
    public let root: URL
    public let packs: [SceneryPack]
    public let libraryIndex: LibraryIndex

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
