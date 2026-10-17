import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_airport_rank.py` (#815, #817): both run
/// `Ortho4XP/tests/fixtures/airport_rank_cases.json`, so the Mac and Qt
/// apps rank a tile's airports — and read the index's size columns — the
/// same way.
@Suite struct AirportRankTests {
    struct Cases: Decodable {
        struct Entry: Decodable {
            let code: String, lat: Double, lon: Double
            let extent: [Double]?
            let size_class: Int, runway_m: Int
        }
        struct Largest: Decodable { let tile: [Int]; let codes: [String] }
        struct Title: Decodable { let largest: [String]; let searched: [String]; let codes: [String] }
        struct CacheRow: Decodable { let row: String; let runway_m: Int?; let size_class: Int? }
        let index: [Entry]
        let largest: [Largest]
        let titles: [Title]
        let cache_rows: [CacheRow]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/airport_rank_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func largestByTileLikeThePythonTwin() {
        let airports = Self.cases.index.map { e in
            GlobalAirport(icao: e.code, latitude: e.lat, longitude: e.lon,
                          extent: e.extent.map {
                              AirportExtent(minLatitude: $0[0], minLongitude: $0[1],
                                            maxLatitude: $0[2], maxLongitude: $0[3])
                          },
                          runwayMeters: e.runway_m, sizeClass: e.size_class)
        }
        let largest = AirportRank.largestByTile(airports)
        for c in Self.cases.largest {
            #expect(largest[AirportTile(lat: c.tile[0], lon: c.tile[1])] == c.codes, "\(c.tile)")
        }
        #expect(largest.count == Self.cases.largest.count)
    }

    @Test func titleCodesLikeThePythonTwin() {
        for c in Self.cases.titles {
            #expect(AirportRank.titleCodes(largest: c.largest, searched: c.searched) == c.codes,
                    "\(c.largest) / \(c.searched)")
        }
    }

    @Test func readsTheV6SizeColumns() throws {
        for c in Self.cases.cache_rows {
            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent("rank-\(UUID().uuidString).tsv")
            defer { try? FileManager.default.removeItem(at: url) }
            try ("O4AIRPORTIDX 6 1\n" + c.row + "\n").write(to: url, atomically: true, encoding: .utf8)
            let airports = try #require(GlobalAirportIndex.readCache(at: url))
            #expect(airports.count == 1)
            #expect(airports.first?.runwayMeters == c.runway_m)
            #expect(airports.first?.sizeClass == c.size_class)
            #expect(airports.first?.extent != nil)
        }
    }
}
