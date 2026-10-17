import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_airport_search.py` (#543): both read
/// `Ortho4XP/tests/fixtures/airport_search_cases.json`, so the Mac and Qt
/// search fields normalise, label and rank airports the same way.
@Suite struct AirportSearchTests {
    struct Cases: Decodable {
        struct Normal: Decodable { let text: String; let normal: String }
        struct Label: Decodable {
            let code: String, name: String, city: String, country: String, label: String
        }
        struct NoMatch: Decodable { let query: String; let text: String }
        struct Entry: Decodable {
            let code: String, name: String, city: String, country: String
            let size_class: Int, runway_m: Int
        }
        struct Search: Decodable { let query: String; let codes: [String] }
        let normalize: [Normal]
        let labels: [Label]
        let no_match: [NoMatch]
        let index: [Entry]
        let search: [Search]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/airport_search_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func normalizeLikeThePythonTwin() {
        for c in Self.cases.normalize {
            #expect(AirportSearch.normalize(c.text) == c.normal, "\(c.text)")
        }
    }

    @Test func labelsLikeThePythonTwin() {
        for c in Self.cases.labels {
            #expect(AirportSearch.resultLabel(code: c.code, name: c.name, city: c.city,
                                              country: c.country) == c.label)
        }
        for c in Self.cases.no_match {
            #expect(AirportSearch.noMatchText(c.query) == c.text)
        }
    }

    @Test func rankingLikeThePythonTwin() {
        let search = AirportSearch(Self.cases.index.map {
            GlobalAirport(icao: $0.code, latitude: 0, longitude: 0, extent: nil,
                          runwayMeters: $0.runway_m, sizeClass: $0.size_class,
                          name: $0.name, city: $0.city, country: $0.country)
        })
        for c in Self.cases.search {
            #expect(search.results(for: c.query).map(\.icao) == c.codes, "\(c.query)")
        }
    }

    @Test func limitHolds() {
        let search = AirportSearch((0..<20).map {
            GlobalAirport(icao: String(format: "A%03d", $0), latitude: 0, longitude: 0,
                          name: "Alpha \($0)")
        })
        #expect(search.results(for: "alpha").count == AirportSearch.resultLimit)
        #expect(search.results(for: "alpha", limit: 3).count == 3)
    }
}
