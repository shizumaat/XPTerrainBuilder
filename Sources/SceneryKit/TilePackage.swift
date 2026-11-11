import Foundation

/// A `.xptb` package (#2014; engine `tile_bundle.package` / `.install` /
/// `.merge`): a tile's, a region's or one airport's downloaded map and
/// elevation data, shared however its maker likes. Installing one leaves
/// nothing to download but imagery. The Qt window shows the same plan
/// and asks the same questions (`O4_Qt_Tile_Package.py`).
public enum O4TilePackage {
    /// A package's extension, and a tile bundle's (still installed).
    public static let fileExtension = "xptb"
    public static let legacyExtension = "xptbundle"
    /// The exported type identifier `make_app.sh` declares.
    public static let typeIdentifier = "com.novemberlima.xptb"

    /// True for a file the package install takes (not a patch drop).
    public static func isPackage(_ url: URL) -> Bool {
        [fileExtension, legacyExtension].contains(url.pathExtension.lowercased())
    }
}

/// One airport of a package's tile and how its pack compares with the
/// one installed here (`match`: "same", "different" or "absent").
public struct O4PackageAirport: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { icao }
    public let icao: String
    public let pack: String
    public let installedPack: String
    public let match: String

    private enum CodingKeys: String, CodingKey {
        case icao, pack, match
        case installedPack = "installed_pack"
    }
}

public struct O4PackageTile: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { tile }
    public let tile: String
    public let airports: [O4PackageAirport]
}

/// An airport that already has a patch the package would replace: the
/// user keeps theirs (the default) or backs it up and uses the package's.
public struct O4PackageConflict: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { tile + icao }
    public let tile: String
    public let icao: String
    /// "custom" (the user's own patch) or "package" (another package's).
    public let kind: String
    public let installed: String
    public let choice: String
    /// Where "Back up mine" puts the installed patch.
    public let backup: String
}

/// What a recipient's build still downloads (`tile_bundle.kinds.still_needs`):
/// `what` is "imagery", "data" or "other_airports"; `bytes` nil for imagery.
public struct O4PackageNeed: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { what }
    public let what: String
    public let text: String
    public let bytes: Int64?
}

/// The maker's estimate of the recipient's build (`tile_bundle.estimate`).
public struct O4PackageBuildEstimate: Decodable, Equatable, Sendable {
    public let buildSeconds: Double
    public let downloadBytes: Int64

    private enum CodingKeys: String, CodingKey {
        case buildSeconds = "build_seconds"
        case downloadBytes = "download_bytes"
    }
}

/// `package_plan` / `package_install` result.
public struct O4PackagePlan: Decodable, Equatable, Sendable {
    public let path: String
    public let format: String
    public let legacy: Bool
    public let title: String
    public let creator: String
    public let notes: String
    public let url: String
    public let tiles: [O4PackageTile]
    public let licence: String
    public let noncommercial: Bool
    public let bytes: Int64
    public let files: Int
    public let conflicts: [O4PackageConflict]
    /// The confirmation's lines, the same in both apps.
    public let summary: [String]
    /// After install: the files placed, and per tile what would still
    /// download besides imagery (empty lists when nothing).
    public let installed: Int?
    public let downloadsLeft: [String: [String]]?
    /// "exact", "patch", "tile" or "combined" (`tile_bundle.kinds`); empty
    /// for a package saved before kinds, and absent for a tile bundle.
    public let kind: String?
    public let stillNeeds: [O4PackageNeed]?
    public let estimate: O4PackageBuildEstimate?

    private enum CodingKeys: String, CodingKey {
        case path, format, legacy, title, creator, notes, url, tiles, licence
        case noncommercial, bytes, files, conflicts, summary, installed, kind, estimate
        case downloadsLeft = "downloads_left"
        case stillNeeds = "still_needs"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        path = try c.decode(String.self, forKey: .path)
        format = try c.decode(String.self, forKey: .format)
        legacy = try c.decode(Bool.self, forKey: .legacy)
        title = try c.decode(String.self, forKey: .title)
        creator = try c.decode(String.self, forKey: .creator)
        notes = try c.decode(String.self, forKey: .notes)
        url = try c.decode(String.self, forKey: .url)
        tiles = try c.decode([O4PackageTile].self, forKey: .tiles)
        licence = try c.decode(String.self, forKey: .licence)
        noncommercial = try c.decode(Bool.self, forKey: .noncommercial)
        bytes = try c.decode(Int64.self, forKey: .bytes)
        files = try c.decode(Int.self, forKey: .files)
        conflicts = try c.decode([O4PackageConflict].self, forKey: .conflicts)
        summary = try c.decode([String].self, forKey: .summary)
        installed = try c.decodeIfPresent(Int.self, forKey: .installed)
        downloadsLeft = try c.decodeIfPresent([String: [String]].self, forKey: .downloadsLeft)
        kind = try c.decodeIfPresent(String.self, forKey: .kind)
        stillNeeds = try c.decodeIfPresent([O4PackageNeed].self, forKey: .stillNeeds)
        // An empty `{}` (a package saved before kinds) reads as no estimate.
        estimate = try? c.decodeIfPresent(O4PackageBuildEstimate.self, forKey: .estimate)
    }
}

/// `package_save` / `package_merge` result.
public struct O4PackageSaved: Decodable, Equatable, Sendable {
    public let path: String
    public let bytes: Int64
    public let kind: String?
    public let files: Int
    public let tiles: [String]
    public let noncommercial: Bool
    public let seconds: Double
}

/// `package_airports` result: the airports each tile grades or holds the
/// user's own files for, those with the user's own files, and the one the
/// export window opens on.
public struct O4PackageAirports: Decodable, Equatable, Sendable {
    public let tiles: [String: [String]]
    public let custom: [String: [String]]?
    public let `default`: String?

    /// Every airport offered, sorted, once.
    public var all: [String] { Array(Set(tiles.values.joined())).sorted() }
}

/// One package kind's row of the export window (`package_estimate`,
/// `tile_bundle.estimate.kind_figures`): its name, one-line explanation,
/// the estimated package size, and the recipient's downloads and build.
public struct O4PackageKindEstimate: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { kind }
    public let kind: String
    public let title: String
    public let explanation: String
    public let available: Bool
    public let why: String
    public let files: Int
    public let bytes: Int64
    public let downloadBytes: Int64
    public let buildSeconds: Double
    public let stillNeeds: [O4PackageNeed]
    /// The row's figures in the words both apps show ("about 104.2 MB ·
    /// recipient downloads only imagery · builds in about 14 min (estimate)").
    public let figures: String

    private enum CodingKeys: String, CodingKey {
        case kind, title, explanation, available, why, files, bytes, figures
        case downloadBytes = "download_bytes"
        case buildSeconds = "build_seconds"
        case stillNeeds = "still_needs"
    }
}

/// `package_estimate` result: each kind's row for exporting `airport`.
public struct O4PackageEstimate: Decodable, Equatable, Sendable {
    public let airport: String
    public let tiles: [String]
    public let kinds: [O4PackageKindEstimate]
}

/// The words both apps use (Qt: `O4_Qt_Tile_Package`).
public enum O4TilePackageCopy {
    public static let exportTitle = "Export Package…"
    public static let installTitle = "Install package?"
    public static let install = "Install"
    public static let keepMine = "Keep my patch"
    public static let useTheirs = "Back up mine and use the package's"
    public static let combineTitle = "Combine Packages…"
    public static let airportLabel = "Airport"
    public static let wholeTileOnly = "Whole tile (no airport)"
    public static let estimateNote = "Sizes and times are estimates; imagery is never included."


    public static func installed(_ plan: O4PackagePlan) -> String {
        let left = (plan.downloadsLeft ?? [:]).filter { !$0.value.isEmpty }
        let tiles = plan.tiles.map(\.tile).joined(separator: ", ")
        if left.isEmpty {
            return "Installed \(plan.title.isEmpty ? "the package" : plan.title) for tile "
                + "\(tiles): building it downloads only imagery."
        }
        return "Installed the package for tile \(tiles); still to download: "
            + left.map { "\($0.key) (\($0.value.joined(separator: ", ")))" }.sorted()
                .joined(separator: "; ")
    }
}

extension OrthoEngineClient {
    /// The airports each tile grades (the export sheet's choices).
    public func packageAirports(tiles: [(lat: Int, lon: Int)],
                                workingDir: String) async throws -> O4PackageAirports {
        try await libraryRequest("package_airports", [
            "tiles": tiles.map { [$0.lat, $0.lon] }, "working_dir": workingDir])
    }

    /// Each package kind's estimate for exporting `airport` ("" for the
    /// whole-tile row only).
    public func packageEstimate(tiles: [(lat: Int, lon: Int)], workingDir: String,
                                airport: String) async throws -> O4PackageEstimate {
        try await libraryRequest("package_estimate", [
            "tiles": tiles.map { [$0.lat, $0.lon] }, "working_dir": workingDir,
            "airport": airport])
    }

    /// Writes the package of `tiles` (of `airports` only when given) to
    /// `out`, a `.xptb` path; `kind` "exact", "patch" or "tile".
    public func packageSave(tiles: [(lat: Int, lon: Int)], workingDir: String, out: String,
                            airports: [String], kind: String = "", title: String,
                            creator: String, notes: String,
                            url: String) async throws -> O4PackageSaved {
        try await libraryRequest("package_save", [
            "tiles": tiles.map { [$0.lat, $0.lon] }, "working_dir": workingDir, "out": out,
            "airports": airports, "kind": kind, "title": title, "creator": creator,
            "notes": notes, "url": url,
        ])
    }

    /// What installing `path` would do; writes nothing.
    public func packagePlan(path: String, workingDir: String,
                            choices: [String: String] = [:]) async throws -> O4PackagePlan {
        try await libraryRequest("package_plan", ["path": path, "working_dir": workingDir,
                                                  "choices": choices])
    }

    /// Installs `path`; `choices` answers the plan's conflicts by ICAO
    /// ("keep" or "replace").
    public func packageInstall(path: String, workingDir: String,
                               choices: [String: String]) async throws -> O4PackagePlan {
        try await libraryRequest("package_install", ["path": path, "working_dir": workingDir,
                                                     "choices": choices])
    }

    /// Combines several packages into one at `out`.
    public func packageMerge(paths: [String], out: String) async throws -> O4PackageSaved {
        try await libraryRequest("package_merge", ["paths": paths, "out": out])
    }
}
