import Testing
import Foundation
@testable import SceneryKit

/// The app READS the engine's airport index, it does not build one: the
/// apt.dat parse lives in `src/O4_Airport_Index.py` (docs/specs/
/// airport-index-engine-command-spec.md). These tests cover the reader's
/// contract with that file format.
@Suite struct GlobalAirportIndexTests {
    /// A v4 cache as `build_index` writes it: header, one `#SRC`
    /// provenance line, then 7-column rows.
    static let v4Cache = [
        "O4AIRPORTIDX 4 3",
        "#SRC 1755200000000000000 421337 /X-Plane 12/Global Scenery/Global Airports/Earth nav data/apt.dat",
        ["ZZZ1", "Override Field", "Testville", "Testland", "10.5", "-20.25", "icao_airport"]
            .joined(separator: "\t"),
        ["XTS3", "Water Field", "", "", "41.5", "-70.25", "seaplane_base"]
            .joined(separator: "\t"),
        ["XTS4", "Helipad Field", "Helitown", "", "42.5", "-71.5", "heliport"]
            .joined(separator: "\t"),
    ].joined(separator: "\n") + "\n"

    static func write(_ text: String, to url: URL) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(),
                                                withIntermediateDirectories: true)
        try Data(text.utf8).write(to: url)
    }

    /// A scratch file that cleans itself up; `body` gets its URL.
    static func withCache(_ text: String,
                          _ body: (URL) throws -> Void) throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("airport-index-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent(GlobalAirportIndex.cacheFilename)
        try write(text, to: url)
        try body(url)
    }

    static func positions(_ airports: [GlobalAirport]) -> [String: [Double]] {
        Dictionary(uniqueKeysWithValues: airports.map {
            ($0.icao, [$0.latitude, $0.longitude])
        })
    }

    /// The wire constant this app finds the optimistic cache by — the twin
    /// of `O4_File_Names.airport_index_cache()`'s basename.
    @Test func cacheFilenameIsTheEngineSpelling() {
        #expect(GlobalAirportIndex.cacheFilename == ".airport_index.tsv")
    }

    @Test func readsAV4Cache() throws {
        try Self.withCache(Self.v4Cache) { url in
            let airports = try #require(GlobalAirportIndex.readCache(at: url))
            // #SRC lines are provenance, not airports.
            #expect(airports.count == 3)
            #expect(Self.positions(airports) == [
                "ZZZ1": [10.5, -20.25],
                "XTS3": [41.5, -70.25],
                "XTS4": [42.5, -71.5],
            ])
            // File order is preserved (the engine writes them ranked).
            #expect(airports.map(\.icao) == ["ZZZ1", "XTS3", "XTS4"])
        }
    }

    /// v3 is the oldest format the reader accepts, and its rows carry the
    /// same columns 0/4/5.
    @Test func readsAV3Cache() throws {
        let v3 = [
            "O4AIRPORTIDX 3 1",
            "#SRC 1 2 /somewhere/apt.dat",
            ["AAAA", "Alpha", "Aville", "Aland", "48.5", "-6.25", "icao_airport"]
                .joined(separator: "\t"),
        ].joined(separator: "\n") + "\n"
        try Self.withCache(v3) { url in
            let airports = try #require(GlobalAirportIndex.readCache(at: url))
            #expect(Self.positions(airports) == ["AAAA": [48.5, -6.25]])
        }
    }

    /// 6-column (pre-category) rows still parse; malformed rows and the
    /// 0/0 placeholder are skipped rather than poisoning the whole read.
    @Test func acceptsSixColumnRowsAndSkipsUnusableOnes() throws {
        let mixed = [
            "O4AIRPORTIDX 4 6",
            "#SRC 1 2 /somewhere/apt.dat",
            ["SIX1", "Six Column", "", "", "1.5", "2.5"].joined(separator: "\t"),
            ["ZERO", "Placeholder", "", "", "0.0", "0.0", "airport"]
                .joined(separator: "\t"),
            ["SHRT", "Too Few Columns", "12.0"].joined(separator: "\t"),
            ["WIDE", "Too Many", "", "", "3.5", "4.5", "airport", "extra"]
                .joined(separator: "\t"),
            ["NANL", "Unparseable Latitude", "", "", "north", "4.5", "airport"]
                .joined(separator: "\t"),
            ["GOOD", "Kept", "", "", "-33.9", "151.2", "airport"]
                .joined(separator: "\t"),
        ].joined(separator: "\n") + "\n"
        try Self.withCache(mixed) { url in
            let airports = try #require(GlobalAirportIndex.readCache(at: url))
            #expect(airports.map(\.icao) == ["SIX1", "GOOD"])
            #expect(Self.positions(airports) == [
                "SIX1": [1.5, 2.5], "GOOD": [-33.9, 151.2],
            ])
        }
    }

    /// A v2 header predates the category column the engine now always
    /// writes: it means an older engine wrote the file, so it is rejected
    /// (the engine is about to replace it anyway).
    @Test func rejectsPreV3Headers() throws {
        let v2 = [
            "O4AIRPORTIDX 2 1",
            ["AAAA", "Alpha", "", "", "48.5", "-6.25"].joined(separator: "\t"),
        ].joined(separator: "\n") + "\n"
        try Self.withCache(v2) { url in
            #expect(GlobalAirportIndex.readCache(at: url) == nil)
        }
        let v1 = [
            "O4AIRPORTIDX 1 1",
            ["AAAA", "Alpha", "", "", "48.5", "-6.25"].joined(separator: "\t"),
        ].joined(separator: "\n") + "\n"
        try Self.withCache(v1) { url in
            #expect(GlobalAirportIndex.readCache(at: url) == nil)
        }
    }

    @Test func rejectsJunkAndMissingFiles() throws {
        for junk in ["", "not an index at all\n", "O4AIRPORTIDX\n",
                     "O4AIRPORTIDX 4\n", "O4AIRPORTIDX four 3\n",
                     "{\"version\": 1}\n"] {
            try Self.withCache(junk) { url in
                #expect(GlobalAirportIndex.readCache(at: url) == nil,
                        "accepted a bad header: \(junk.debugDescription)")
            }
        }
        let missing = FileManager.default.temporaryDirectory
            .appendingPathComponent("no-such-index-\(UUID().uuidString).tsv")
        #expect(GlobalAirportIndex.readCache(at: missing) == nil)
    }

    /// An index with a valid header but no rows is EMPTY, not nil — the
    /// difference between "the engine has nothing to show" and "there is
    /// no usable index here".
    @Test func headerOnlyCacheIsEmptyNotNil() throws {
        try Self.withCache("O4AIRPORTIDX 4 0\n") { url in
            #expect(GlobalAirportIndex.readCache(at: url)?.isEmpty == true)
        }
    }
}
