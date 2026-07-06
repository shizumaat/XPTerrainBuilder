import Foundation

/// An EXPORT line from a library.txt: a virtual path backed by a real file in some pack.
public struct LibraryExport: Sendable {
    public let virtualPath: String
    public let realPath: String
    public let packName: String
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
        let libraryTxt = packURL.appendingPathComponent("library.txt")
        guard let text = TextFile.contents(of: libraryTxt) else { return }
        for rawLine in TextFile.lines(text) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            // EXPORT, EXPORT_RATIO, EXPORT_EXTEND, EXPORT_BACKUP, EXPORT_EXCLUDE
            guard line.hasPrefix("EXPORT") else { continue }
            // Split on spaces AND tabs — authors use both.
            var parts = line.split(omittingEmptySubsequences: true,
                                   whereSeparator: { $0 == " " || $0 == "\t" }).map(String.init)
            guard parts.count >= 3 else { continue }
            let keyword = parts.removeFirst()
            if keyword == "EXPORT_RATIO" { parts.removeFirst() } // skip the ratio number
            guard parts.count >= 2 else { continue }
            let virtualPath = parts[0]
            let realPath = parts[1...].joined(separator: " ")
            add(LibraryExport(virtualPath: virtualPath, realPath: realPath, packName: packName))
        }
    }

    public mutating func add(_ export: LibraryExport) {
        let key = export.virtualPath.lowercased()
        exports[key, default: []].append(export)
        if let prefix = export.virtualPath.split(separator: "/").first {
            prefixes[String(prefix).lowercased(), default: []].insert(export.packName)
        }
    }

    /// Exact match ignoring case. Returns the canonical export if the only
    /// difference from `virtualPath` is letter case.
    public func caseInsensitiveMatch(for virtualPath: String) -> LibraryExport? {
        exports[virtualPath.lowercased()]?.first
    }

    /// Pack names that export anything under the same top-level prefix,
    /// i.e. "is this library installed at all?"
    public func packsExportingPrefix(of virtualPath: String) -> Set<String> {
        guard let prefix = virtualPath.split(separator: "/").first else { return [] }
        return prefixes[String(prefix).lowercased()] ?? []
    }

    /// Closest exported paths to a missing virtual path, for typo detection.
    /// Only compares paths sharing the same top-level prefix and same filename
    /// neighborhood so we stay cheap and avoid absurd suggestions.
    public func nearestExports(to virtualPath: String, limit: Int = 3) -> [LibraryExport] {
        let lowered = virtualPath.lowercased()
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
