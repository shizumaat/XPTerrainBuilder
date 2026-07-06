import Foundation

/// Author-facing lifecycle of an export, set by bare status directives
/// (PUBLIC / PRIVATE / DEPRECATED / SEMI_DEPRECATED) that apply to every
/// EXPORT line after them until the next directive — the same semantics
/// WED uses. Laminar's default libraries mark legacy XP8–11 art this way;
/// deprecated paths still resolve (sometimes to blank placeholder art) but
/// may be dropped in future X-Plane versions.
public enum LibraryExportStatus: Sendable {
    case `public`, `private`, deprecated, semiDeprecated

    public var isDeprecated: Bool { self == .deprecated || self == .semiDeprecated }
}

/// An EXPORT line from a library.txt: a virtual path backed by a real file in some pack.
public struct LibraryExport: Sendable {
    public let virtualPath: String
    public let realPath: String
    public let packName: String
    public let status: LibraryExportStatus

    public init(virtualPath: String, realPath: String, packName: String,
                status: LibraryExportStatus = .public) {
        self.virtualPath = virtualPath
        self.realPath = realPath
        self.packName = packName
        self.status = status
    }
}

/// Index of every virtual path exported by every installed library pack.
///
/// X-Plane scenery references shared assets by "virtual paths" (e.g.
/// `opensceneryx/objects/airport/fuel_truck.obj`). A library pack's library.txt
/// maps those virtual paths onto real files. When Log.txt reports a missing
/// resource, this index answers: is the owning library installed at all, and
/// if so, is there an export whose path *almost* matches (case or typo)?
public struct LibraryIndex: Sendable {
    /// lowercased virtual path -> exports (several packs may export the same path).
    public private(set) var exports: [String: [LibraryExport]] = [:]
    /// lowercased first path component -> pack names exporting under that prefix.
    public private(set) var prefixes: [String: Set<String>] = [:]

    public init() {}

    public var exportCount: Int { exports.count }

    public mutating func indexLibrary(at packURL: URL, packName: String) {
        indexLibraryFile(at: packURL.appendingPathComponent("library.txt"), packName: packName)
    }

    /// Index one library-format text file. X-Plane only reads "library.txt",
    /// but packs ship alternate configs ("library - orthos.txt") the user
    /// swaps in by renaming — the unused-resource audit indexes those too so
    /// a deletion can't break a configuration away from being active.
    public mutating func indexLibraryFile(at libraryTxt: URL, packName: String) {
        guard let text = TextFile.contents(of: libraryTxt) else { return }
        var status = LibraryExportStatus.public
        for rawLine in TextFile.lines(text) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            // Status directives scope every following EXPORT (PUBLIC may
            // carry a date: "PUBLIC 20240630").
            if line.hasPrefix("PUBLIC") { status = .public; continue }
            if line == "PRIVATE" { status = .private; continue }
            if line == "DEPRECATED" { status = .deprecated; continue }
            if line == "SEMI_DEPRECATED" { status = .semiDeprecated; continue }
            // EXPORT, EXPORT_RATIO, EXPORT_EXTEND, EXPORT_BACKUP, EXPORT_EXCLUDE,
            // EXPORT_SEASON, EXPORT_EXCLUDE_SEASON
            guard line.hasPrefix("EXPORT") else { continue }
            // Split on spaces AND tabs — authors use both.
            var parts = line.split(omittingEmptySubsequences: true,
                                   whereSeparator: { $0 == " " || $0 == "\t" }).map(String.init)
            guard parts.count >= 3 else { continue }
            let keyword = parts.removeFirst()
            // EXPORT_RATIO carries a ratio, the _SEASON forms a season list
            // ("sum" / "spr,sum") before the virtual path. XP12's default
            // libraries remap thousands of legacy lib/g8… paths through
            // EXPORT_SEASON — dropping the extra token indexed them under
            // the season name and made them look uninstalled.
            if keyword == "EXPORT_RATIO" || keyword.hasSuffix("_SEASON") { parts.removeFirst() }
            guard parts.count >= 2 else { continue }
            let virtualPath = parts[0]
            let realPath = parts[1...].joined(separator: " ")
            add(LibraryExport(virtualPath: virtualPath, realPath: realPath,
                              packName: packName, status: status))
        }
    }

    /// Lowercased with backslashes unified to slashes — X-Plane accepts "\"
    /// as a path separator in library.txt (RD_Library ships that way), and
    /// DSF references use "/".
    static func normalizeKey(_ path: String) -> String {
        path.replacingOccurrences(of: "\\", with: "/").lowercased()
    }

    public mutating func add(_ export: LibraryExport) {
        // Store separator-normalized so realPath file checks work too.
        let normalized = LibraryExport(
            virtualPath: export.virtualPath.replacingOccurrences(of: "\\", with: "/"),
            realPath: export.realPath.replacingOccurrences(of: "\\", with: "/"),
            packName: export.packName,
            status: export.status
        )
        let key = Self.normalizeKey(normalized.virtualPath)
        exports[key, default: []].append(normalized)
        if let prefix = key.split(separator: "/").first {
            prefixes[String(prefix), default: []].insert(export.packName)
        }
    }

    /// Exact match ignoring case and separator style. Returns the canonical
    /// export if the only difference from `virtualPath` is case or "\" vs "/".
    public func caseInsensitiveMatch(for virtualPath: String) -> LibraryExport? {
        exports[Self.normalizeKey(virtualPath)]?.first
    }

    /// The match, but only when EVERY export of the path is deprecated or
    /// semi-deprecated — one public seasonal/regional variant means the path
    /// is still supported and must not be flagged.
    public func fullyDeprecatedMatch(for virtualPath: String) -> LibraryExport? {
        guard let all = exports[Self.normalizeKey(virtualPath)], !all.isEmpty,
              all.allSatisfy({ $0.status.isDeprecated }) else { return nil }
        return all.first
    }

    /// Pack names that export anything under the same top-level prefix,
    /// i.e. "is this library installed at all?"
    public func packsExportingPrefix(of virtualPath: String) -> Set<String> {
        guard let prefix = Self.normalizeKey(virtualPath).split(separator: "/").first else { return [] }
        return prefixes[String(prefix)] ?? []
    }

    /// Closest exported paths to a missing virtual path, for typo detection.
    /// Only compares paths sharing the same top-level prefix and same filename
    /// neighborhood so we stay cheap and avoid absurd suggestions.
    public func nearestExports(to virtualPath: String, limit: Int = 3) -> [LibraryExport] {
        let lowered = Self.normalizeKey(virtualPath)
        guard let prefix = lowered.split(separator: "/").first else { return [] }
        let targetFile = (lowered as NSString).lastPathComponent

        var scored: [(Int, LibraryExport)] = []
        for (key, exps) in exports {
            guard key.hasPrefix(prefix) else { continue }
            let candidateFile = (key as NSString).lastPathComponent
            // Cheap pre-filter: filenames must be similar in length.
            guard abs(candidateFile.count - targetFile.count) <= 3 else { continue }
            let fileDistance = Self.editDistance(targetFile, candidateFile, max: 3)
            guard fileDistance <= 3 else { continue }
            let pathDistance = Self.editDistance(lowered, key, max: 6)
            guard pathDistance <= 6 else { continue }
            if let export = exps.first {
                scored.append((pathDistance, export))
            }
        }
        return scored.sorted { $0.0 < $1.0 }.prefix(limit).map { $0.1 }
    }

    /// Bounded Levenshtein distance; returns max+1 when the bound is exceeded.
    static func editDistance(_ a: String, _ b: String, max bound: Int) -> Int {
        if abs(a.count - b.count) > bound { return bound + 1 }
        let aChars = Array(a), bChars = Array(b)
        if aChars.isEmpty { return bChars.count }
        if bChars.isEmpty { return aChars.count }
        var previous = Array(0...bChars.count)
        var current = [Int](repeating: 0, count: bChars.count + 1)
        for i in 1...aChars.count {
            current[0] = i
            var rowMin = current[0]
            for j in 1...bChars.count {
                let cost = aChars[i - 1] == bChars[j - 1] ? 0 : 1
                current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
                rowMin = min(rowMin, current[j])
            }
            if rowMin > bound { return bound + 1 }
            swap(&previous, &current)
        }
        return previous[bChars.count]
    }
}
