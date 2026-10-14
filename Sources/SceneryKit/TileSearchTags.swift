import Foundation

/// Which search codes picked each selected tile (issue #667): the build
/// progress list shows them after the tile's coordinate, `-13-078 (SPJC)`,
/// several in the order typed, `(KCLT, KJQF)`; a tile selected by hand
/// shows nothing. UI state for the session — never persisted, never sent
/// to the engine. The Python half of the text is
/// `O4_Airport_Batch.tile_tag`; both read the `tags` vectors of
/// `Ortho4XP/tests/fixtures/airport_code_list_cases.json`.
public struct TileSearchTags: Sendable, Equatable {
    public private(set) var codes: [AirportTile: [String]] = [:]

    public init() {}

    /// Add a search's picks (the Mac app ADDS to the selection): a code
    /// already on a tile keeps its place, new ones follow it.
    public mutating func add(_ picks: [AirportTile: [String]]) {
        for (tile, new) in picks {
            var have = codes[tile] ?? []
            for code in new where !have.contains(code) { have.append(code) }
            codes[tile] = have
        }
    }

    /// Drop the tags of every tile no longer selected.
    public mutating func keep(only selected: Set<AirportTile>) {
        codes = codes.filter { selected.contains($0.key) }
    }

    /// The text after `tile`'s coordinate: ` (KCLT, KJQF)`, or "".
    public func suffix(for tile: AirportTile) -> String {
        Self.suffix(codes[tile] ?? [])
    }

    public static func suffix(_ codes: [String]) -> String {
        codes.isEmpty ? "" : " (\(codes.joined(separator: ", ")))"
    }
}
