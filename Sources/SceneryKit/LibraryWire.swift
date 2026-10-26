import Foundation

// MARK: - Library (#824)

/// The engine's `library_scan` result (`Ortho4XP/src/o4_engine/library.py`):
/// every built tile of the tiles folder, their total, and the download
/// caches. Snake-case wire keys are spelled out in each CodingKeys.
public struct O4LibraryScan: Decodable, Equatable, Sendable {
    public let tiles: [O4LibraryTile]
    public let tilesBytes: Int64
    public let caches: [O4LibraryCache]

    private enum CodingKeys: String, CodingKey {
        case tiles, caches, tilesBytes = "tiles_bytes"
    }
}

/// One custom pack a tile's build modified (restorable with
/// `reanchor_restore`).
public struct O4LibraryPack: Decodable, Equatable, Hashable, Sendable {
    public let packName: String
    public let packPath: String
    public let objects: Int

    private enum CodingKeys: String, CodingKey {
        case objects, packName = "pack_name", packPath = "pack_path"
    }
}

/// One built tile, as the Library lists it.
public struct O4LibraryTile: Decodable, Equatable, Identifiable, Sendable {
    public let tile: String
    public let lat: Int
    public let lon: Int
    public let buildDir: String
    public let sizeBytes: Int64
    public let zl: Int?
    public let provider: String
    /// Unix time of the newest mesh or texture file; nil when unknown.
    public let built: Double?
    public let airports: [String]
    public let packsModified: [O4LibraryPack]
    public let linkStatus: String
    public let inXPlane: Bool
    /// "XPTerrainBuilder", or "other" for a tile another tool built.
    public let builtBy: String
    /// Built by another tool: never rebuilt or deleted by the Library.
    public let readOnly: Bool

    public var id: String { tile }

    private enum CodingKeys: String, CodingKey {
        case tile, lat, lon, zl, provider, built, airports
        case buildDir = "build_dir", sizeBytes = "size_bytes"
        case packsModified = "packs_modified", linkStatus = "link_status"
        case inXPlane = "in_xplane", builtBy = "built_by", readOnly = "read_only"
    }

    /// Sort keys for the Library table (a `Table` column sorts by a
    /// `Comparable` key path; optionals and arrays are not).
    public var zlSortKey: Int { zl ?? 0 }
    public var builtSortKey: Double { built ?? 0 }
    public var airportsText: String { airports.joined(separator: ", ") }
    public var packsText: String { packsModified.map(\.packName).joined(separator: ", ") }
    public var builtByText: String { readOnly ? "Other tool (read-only)" : "XPTerrainBuilder" }
    public var inXPlaneSortKey: Int { inXPlane ? 1 : 0 }

    /// Whether `query` (already lower-cased) appears in any listed field.
    public func matches(_ query: String) -> Bool {
        guard !query.isEmpty else { return true }
        return [tile, provider, airportsText, packsText, builtByText, zl.map(String.init) ?? ""]
            .contains { $0.lowercased().contains(query) }
    }
}

/// One download cache: its folder, size and what freeing it costs later.
public struct O4LibraryCache: Decodable, Equatable, Identifiable, Sendable {
    public let kind: String
    public let label: String
    public let path: String
    public let bytes: Int64
    public let redownload: String

    public var id: String { kind }
}

/// `free_cache` / `library_delete` results.
public struct O4LibraryFreed: Decodable, Equatable, Sendable {
    public let freedBytes: Int64

    private enum CodingKeys: String, CodingKey {
        case freedBytes = "freed_bytes"
    }
}

extension OrthoEngineClient {
    /// Every Library command replies `{"status": "started"}` and the
    /// `LibraryReady` event naming its id carries the result or the error
    /// (`class LibraryReady` in Ortho4XP/src/o4_engine/events.py). An
    /// engine without the commands answers "unknown command".
    private func libraryRequest<T: Decodable & Sendable>(_ command: String,
                                                         _ arguments: [String: Any]) async throws -> T {
        let once = O4ResumeOnce<T>()
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: command,
                 arguments: arguments,
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused \(command).")))
                     }
                 },
                 completionEvent: { event in once.resume(Self.decodeLibraryReady(event)) })
        }
    }

    /// One `LibraryReady` event → the typed result or its error.
    static func decodeLibraryReady<T: Decodable>(_ event: O4JSON?) -> Result<T, Error> {
        guard let event else { return .failure(O4CommandError("The engine exited before it answered.")) }
        if case .string(let text)? = event["error"], !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        guard let result = event["result"], result != .null else {
            return .failure(O4CommandError("The engine sent no result."))
        }
        return Result { try result.decode(T.self) }
    }

    public func libraryScan(workingDir: String, sceneryDir: String) async throws -> O4LibraryScan {
        try await libraryRequest("library_scan", ["working_dir": workingDir, "scenery_dir": sceneryDir])
    }

    /// Empties one cache; the app confirms with the user first.
    public func freeCache(kind: String) async throws -> O4LibraryFreed {
        try await libraryRequest("free_cache", ["kind": kind, "confirm": true])
    }

    /// Deletes built tiles (never one another tool built: the engine
    /// refuses the whole call); the app confirms with the user first.
    public func libraryDelete(tiles: [(lat: Int, lon: Int)], workingDir: String,
                              sceneryDir: String) async throws -> O4LibraryFreed {
        try await libraryRequest("library_delete", [
            "tiles": tiles.map { [$0.lat, $0.lon] }, "working_dir": workingDir,
            "scenery_dir": sceneryDir, "confirm": true,
        ])
    }
}
