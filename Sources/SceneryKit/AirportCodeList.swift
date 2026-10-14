import Foundation

/// One 1°×1° tile, south-west corner.
public struct AirportTile: Hashable, Comparable, Sendable {
    public let lat: Int
    public let lon: Int

    public init(lat: Int, lon: Int) {
        self.lat = lat
        self.lon = lon
    }

    public static func < (lhs: AirportTile, rhs: AirportTile) -> Bool {
        (lhs.lat, lhs.lon) < (rhs.lat, rhs.lon)
    }
}

/// What a typed list of airport codes resolved to.
public struct AirportBatch: Sendable, Equatable {
    /// The codes found, upper-cased, in the order typed.
    public var codes: [String] = []
    /// The codes not in the index, in the order typed.
    public var unknown: [String] = []
    /// Every tile the found airports touch, sorted, no repeats.
    public var tiles: [AirportTile] = []

    /// One line for the search field's inline notice: what is selected
    /// and every code that was not found. Same wording as the Qt app.
    public var summary: String {
        var parts: [String] = []
        if !codes.isEmpty {
            parts.append("Select \(tiles.count) tile\(tiles.count == 1 ? "" : "s") for "
                         + codes.joined(separator: ", "))
        }
        if !unknown.isEmpty {
            parts.append("Unknown airport code\(unknown.count == 1 ? "" : "s"): "
                         + unknown.joined(separator: ", "))
        }
        return parts.joined(separator: " — ")
    }
}

/// A list of airport codes typed into the search field (issue #542):
/// `KCLT, kase OTHH` selects the tiles of all three airports at once.
///
/// The Swift half of ONE rule; the Python half (the Qt app's) is
/// `Ortho4XP/src/O4_Airport_Batch.py`. Both read the same vectors,
/// `Ortho4XP/tests/fixtures/airport_code_list_cases.json`, so they cannot
/// drift without a twin going red. Commas, semicolons and whitespace all
/// separate codes; case does not matter; a repeated code counts once; an
/// unknown code is reported and the rest still selected; an airport
/// selects every tile its extent touches.
///
/// A query is a LIST only when it could not be an ordinary search: it
/// holds a comma or semicolon, or two or more words of which at least one
/// is an exact airport code. Otherwise `resolve` returns nil and the
/// caller runs its single-airport search exactly as before. Tile keys
/// (`+48-006`) are the caller's to recognise first.
public enum AirportCodeList {
    /// An extent wider than this (degrees) is a data error — an
    /// antimeridian wrap or a stray node — and the airport falls back to
    /// its datum tile.
    static let maxExtentDegrees = 1.0

    /// The query's codes: split on commas, semicolons and whitespace,
    /// upper-cased, first occurrence kept.
    public static func codes(in query: String) -> [String] {
        var codes: [String] = []
        let tokens = query.split(whereSeparator: { $0 == "," || $0 == ";" || $0.isWhitespace })
        for token in tokens {
            let code = token.uppercased()
            if !codes.contains(code) { codes.append(code) }
        }
        return codes
    }

    /// Every tile an airport touches; without an extent (or with an
    /// implausibly wide one) the airport is its datum point.
    public static func tiles(latitude: Double, longitude: Double,
                             extent: AirportExtent?) -> [AirportTile] {
        if let e = extent {
            let latSpan = e.maxLatitude - e.minLatitude
            let lonSpan = e.maxLongitude - e.minLongitude
            if (0...maxExtentDegrees).contains(latSpan), (0...maxExtentDegrees).contains(lonSpan) {
                var tiles: [AirportTile] = []
                for lat in Int(floor(e.minLatitude))...Int(floor(e.maxLatitude)) {
                    for lon in Int(floor(e.minLongitude))...Int(floor(e.maxLongitude)) {
                        tiles.append(AirportTile(lat: lat, lon: lon))
                    }
                }
                return tiles
            }
        }
        return [AirportTile(lat: Int(floor(latitude)), lon: Int(floor(longitude)))]
    }

    /// Resolve a typed list through `lookup` (code → its tiles, nil when
    /// unknown). Nil when the query is not a list.
    public static func resolve(_ query: String,
                               lookup: (String) -> [AirportTile]?) -> AirportBatch? {
        let codes = codes(in: query)
        let explicit = query.contains(",") || query.contains(";")
        guard !codes.isEmpty, codes.count >= 2 || explicit else { return nil }
        var batch = AirportBatch()
        var tiles = Set<AirportTile>()
        for code in codes {
            if let found = lookup(code) {
                batch.codes.append(code)
                tiles.formUnion(found)
            } else {
                batch.unknown.append(code)
            }
        }
        if !explicit && batch.codes.isEmpty { return nil }
        batch.tiles = tiles.sorted()
        return batch
    }

    /// A `resolve` lookup over the Global Airports index; codes match
    /// case-blind and the first airport carrying a code wins, as in the
    /// index itself. `fallback` answers codes the index lacks (the app's
    /// custom-pack airports, which carry a point only).
    public static func lookup(_ index: [GlobalAirport],
                              fallback: @escaping (String) -> [AirportTile]? = { _ in nil })
        -> (String) -> [AirportTile]? {
        var byCode: [String: GlobalAirport] = [:]
        for airport in index where byCode[airport.icao.uppercased()] == nil {
            byCode[airport.icao.uppercased()] = airport
        }
        return { code in
            guard let airport = byCode[code.uppercased()] else { return fallback(code) }
            return tiles(latitude: airport.latitude, longitude: airport.longitude,
                         extent: airport.extent)
        }
    }
}
