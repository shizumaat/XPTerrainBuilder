import Foundation

/// Which airports name a tile (issue #815): the Swift half of ONE rule
/// whose Python half is `Ortho4XP/src/O4_Airport_Rank.py`. Both read
/// `Ortho4XP/tests/fixtures/airport_rank_cases.json`.
///
/// The SIZE is the engine's: its airport index writes each airport's
/// longest runway and size class (0 = largest; runway length, surface and
/// type — no airport is named), and this side only orders by it.
public enum AirportRank {
    /// A progress row's title lists at most this many codes.
    public static let titleCodeLimit = 4

    /// The class a row without size columns (a pre-v6 cache) reads as —
    /// `O4_Airport_Rank.UNKNOWN_SIZE_CLASS`.
    public static let unknownSizeClass = 3

    /// Largest first: class, then longest runway, then code — a total
    /// order, so both apps break ties the same way.
    public static func precedes(_ a: (code: String, sizeClass: Int, runwayMeters: Int),
                                _ b: (code: String, sizeClass: Int, runwayMeters: Int)) -> Bool {
        if a.sizeClass != b.sizeClass { return a.sizeClass < b.sizeClass }
        if a.runwayMeters != b.runwayMeters { return a.runwayMeters > b.runwayMeters }
        return a.code < b.code
    }

    /// Each tile → the codes of its `limit` largest airports, largest
    /// first. An airport belongs to every tile its extent touches (the
    /// #542 rule a code search selects by).
    public static func largestByTile(_ airports: [GlobalAirport],
                                     limit: Int = titleCodeLimit) -> [AirportTile: [String]] {
        var byTile: [AirportTile: [(code: String, sizeClass: Int, runwayMeters: Int)]] = [:]
        for airport in airports {
            let key = (code: airport.icao,
                       sizeClass: airport.sizeClass ?? unknownSizeClass,
                       runwayMeters: airport.runwayMeters ?? 0)
            for tile in AirportCodeList.tiles(latitude: airport.latitude,
                                              longitude: airport.longitude,
                                              extent: airport.extent) {
                byTile[tile, default: []].append(key)
            }
        }
        return byTile.mapValues { ranked in
            ranked.sorted(by: precedes).prefix(max(0, limit)).map(\.code)
        }
    }

    /// The codes a tile's progress row names, at most `limit`: a searched
    /// code not among the largest goes FIRST (the user asked for it by
    /// name), the largest fill the rest. Upper-cased; no code repeats.
    public static func titleCodes(largest: [String], searched: [String],
                                  limit: Int = titleCodeLimit) -> [String] {
        let top = largest.map { $0.uppercased() }
        let shown = Array(top.prefix(max(0, limit)))
        let wanted = searched.map { $0.uppercased() }.filter { !shown.contains($0) }
        var codes: [String] = []
        for code in wanted + top where !codes.contains(code) { codes.append(code) }
        return Array(codes.prefix(max(0, limit)))
    }
}
