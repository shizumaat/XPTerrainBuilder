import Foundation
import Testing
@testable import SceneryKit

/// Owner 2026-11-12T21:55Z (lane ltiledetail): a World-pack tile's records
/// reach the tile pane — what its airports stood on and which it graded,
/// and the imagery its record names when no cfg names one (Python twin:
/// tests/test_world_records.py).
struct TileRecordDetailTests {
    @Test func theAirportRowsArrive() throws {
        let info = try #require(O4TileInfo(json: .object([
            "lat": .int(51), "lon": .int(-115), "build_dir": .string("/t"),
            "airport_elevation": .string("HRDEM 1 m: CYBW, CYYC"),
            "airports": .string("CYYC (Calgary pack)"),
        ])))
        #expect(info.airportElevation == "HRDEM 1 m: CYBW, CYYC")
        #expect(info.airports == "CYYC (Calgary pack)")
        let older = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "airports": .string(""),
        ])))
        #expect(older.airportElevation == nil && older.airports == nil)
    }

    @Test func theImageryRecordNamesTheImageryWithoutACfg() throws {
        let info = try #require(O4TileInfo(json: .object([
            "lat": .int(49), "lon": .int(-98), "provider": .string(""),
            "detected_provider": .string("Arc"), "detected_zl": .int(16),
        ])))
        let choice = try #require(TileImageryChoice.resolve(info))
        #expect(choice.provider == "Arc" && choice.zl == 16 && choice.source == .detected)
    }
}
