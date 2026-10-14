import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_airport_batch.py` (issue #542): both run
/// the SAME vectors, `Ortho4XP/tests/fixtures/airport_code_list_cases.json`,
/// so the Mac and Qt search fields cannot read a code list differently.
@Suite struct AirportCodeListTests {
    struct Cases: Decodable {
        struct Split: Decodable { let query: String; let codes: [String] }
        struct Tiles: Decodable {
            let lat: Double, lon: Double
            let extent: [Double]?
            let tiles: [[Int]]
        }
        struct Entry: Decodable {
            let code: String, lat: Double, lon: Double
            let extent: [Double]?
        }
        struct Pick: Decodable { let tile: [Int]; let codes: [String] }
        struct Batch: Decodable {
            let codes: [String]; let unknown: [String]; let tiles: [[Int]]; let picks: [Pick]
        }
        struct Tag: Decodable { let codes: [String]; let tag: String }
        struct Resolve: Decodable { let query: String; let batch: Batch? }
        let split: [Split]
        let tiles: [Tiles]
        let index: [Entry]
        let resolve: [Resolve]
        let tags: [Tag]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/airport_code_list_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    static func extent(_ values: [Double]?) -> AirportExtent? {
        guard let v = values else { return nil }
        return AirportExtent(minLatitude: v[0], minLongitude: v[1],
                             maxLatitude: v[2], maxLongitude: v[3])
    }

    static func tiles(_ pairs: [[Int]]) -> [AirportTile] {
        pairs.map { AirportTile(lat: $0[0], lon: $0[1]) }
    }

    @Test func splitsLikeThePythonTwin() {
        for c in Self.cases.split {
            #expect(AirportCodeList.codes(in: c.query) == c.codes, "\(c.query)")
        }
    }

    @Test func airportTilesLikeThePythonTwin() {
        for c in Self.cases.tiles {
            let got = AirportCodeList.tiles(latitude: c.lat, longitude: c.lon,
                                            extent: Self.extent(c.extent)).sorted()
            #expect(got == Self.tiles(c.tiles), "\(c.lat),\(c.lon)")
        }
    }

    @Test func resolvesLikeThePythonTwin() {
        let index = Self.cases.index.map {
            GlobalAirport(icao: $0.code, latitude: $0.lat, longitude: $0.lon,
                          extent: Self.extent($0.extent))
        }
        let lookup = AirportCodeList.lookup(index)
        for c in Self.cases.resolve {
            let got = AirportCodeList.resolve(c.query, lookup: lookup)
            guard let want = c.batch else {
                #expect(got == nil, "\(c.query)")
                continue
            }
            var picks: [AirportTile: [String]] = [:]
            for p in want.picks { picks[AirportTile(lat: p.tile[0], lon: p.tile[1])] = p.codes }
            #expect(got == AirportBatch(codes: want.codes, unknown: want.unknown,
                                        tiles: Self.tiles(want.tiles), picks: picks), "\(c.query)")
        }
    }

    /// #667: the progress row's suffix, the same text as the Python twin.
    @Test func tagSuffixLikeThePythonTwin() {
        for c in Self.cases.tags {
            #expect(TileSearchTags.suffix(c.codes) == c.tag)
        }
    }

    /// #667: the Mac app ADDS a search to the selection, so it adds tags;
    /// a code already on a tile keeps its place; deselecting drops a tag;
    /// a hand-selected tile has none.
    @Test func tagsAddAcrossSearchesAndDropOnDeselect() {
        let a = AirportTile(lat: 35, lon: -81), b = AirportTile(lat: 25, lon: 51)
        let hand = AirportTile(lat: 10, lon: 10)
        let lookup: (String) -> [AirportTile]? = { code in
            ["KCLT": [a], "KJQF": [a], "OTHH": [b]][code]
        }
        var tags = TileSearchTags()
        tags.add(AirportCodeList.resolve("KCLT, OTHH", lookup: lookup)!.picks)
        tags.add(AirportCodeList.resolve("kjqf kclt", lookup: lookup)!.picks)
        #expect(tags.suffix(for: a) == " (KCLT, KJQF)")
        #expect(tags.suffix(for: b) == " (OTHH)")
        #expect(tags.suffix(for: hand) == "")
        tags.keep(only: [b, hand])
        #expect(tags.suffix(for: a) == "")
        #expect(tags.suffix(for: b) == " (OTHH)")
    }

    @Test func fallbackAnswersCodesTheIndexLacks() {
        let lookup = AirportCodeList.lookup([]) { code in
            code == "XPAK" ? [AirportTile(lat: 1, lon: 2)] : nil
        }
        let batch = AirportCodeList.resolve("xpak, KZZZ", lookup: lookup)
        #expect(batch?.tiles == [AirportTile(lat: 1, lon: 2)])
        #expect(batch?.summary == "Select 1 tile for XPAK — Unknown airport code: KZZZ")
    }

    /// The state that drives the Mac alert (owner decision on #542):
    /// a message only when a code is unknown; same text as the Qt twin.
    @Test func alertMessageOnlyWhenACodeIsUnknown() {
        let index = [GlobalAirport(icao: "KCLT", latitude: 35.2, longitude: -80.9),
                     GlobalAirport(icao: "OTHH", latitude: 25.3, longitude: 51.6)]
        let lookup = AirportCodeList.lookup(index)
        #expect(AirportCodeList.resolve("KCLT, OTHH", lookup: lookup)?.unknownCodesMessage == nil)
        #expect(AirportCodeList.resolve("KCLT, kzzz", lookup: lookup)?.unknownCodesMessage
                == "Not identified: KZZZ. The tiles of KCLT are selected.")
        #expect(AirportCodeList.resolve("KZZZ, QQQQ", lookup: lookup)?.unknownCodesMessage
                == "Not identified: KZZZ, QQQQ. No tiles were selected.")
        #expect(AirportBatch.unknownCodesTitle == "Some airport codes were not found")
    }

    @Test func readsTheV5ExtentColumns() throws {
        let cache = [
            "O4AIRPORTIDX 5 2",
            ["XEDG", "Edge", "", "", "47.95", "8.95", "icao_airport",
             "47.9", "8.9", "48.02", "9.01"].joined(separator: "\t"),
            ["KCLT", "Charlotte", "", "", "35.2", "-80.9", "icao_airport"]
                .joined(separator: "\t"),
        ].joined(separator: "\n") + "\n"
        try GlobalAirportIndexTests.withCache(cache) { url in
            let airports = try #require(GlobalAirportIndex.readCache(at: url))
            #expect(airports.map(\.icao) == ["XEDG", "KCLT"])
            #expect(airports[0].extent == AirportExtent(minLatitude: 47.9, minLongitude: 8.9,
                                                        maxLatitude: 48.02, maxLongitude: 9.01))
            #expect(airports[1].extent == nil)
        }
    }
}
