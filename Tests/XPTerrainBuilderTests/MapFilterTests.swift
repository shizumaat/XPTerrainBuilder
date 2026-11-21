import XCTest
@testable import XPTerrainBuilder

/// #2097: the map's Filter menu (Qt twin: tests/test_map_filter.py).
final class MapFilterTests: XCTestCase {
    func testStoredFormRoundTripsInMenuOrder() {
        let filter = MapFilter(stored: "drape,icao,nonsense")
        XCTAssertEqual(filter.hidden, [.drape, .icao])
        XCTAssertEqual(filter.stored, "icao,drape")
        XCTAssertFalse(MapFilter(stored: "").isFiltering)
    }

    func testAnAirportNeedsItsKindAndItsSource() {
        XCTAssertTrue(MapFilter(stored: "").showsAirport(icaoCoded: true, custom: false))
        XCTAssertFalse(MapFilter(stored: "icao").showsAirport(icaoCoded: true, custom: true))
        XCTAssertTrue(MapFilter(stored: "icao").showsAirport(icaoCoded: false, custom: true))
        XCTAssertFalse(MapFilter(stored: "global").showsAirport(icaoCoded: false, custom: false))
    }

    func testATileNeedsAnyOfItsItems() {
        XCTAssertTrue(MapFilter(stored: "").showsTile(state: nil, pinned: false))
        XCTAssertFalse(MapFilter(stored: "full").showsTile(state: .full, pinned: false))
        XCTAssertTrue(MapFilter(stored: "full").showsTile(state: .full, pinned: true))
        XCTAssertFalse(MapFilter(stored: "full,favorites").showsTile(state: .full, pinned: true))
        XCTAssertTrue(MapFilter(stored: "full").showsTile(state: .drape, pinned: false))
        XCTAssertFalse(MapFilter(stored: "drape").showsTile(state: .drape, pinned: false))
        XCTAssertFalse(MapFilter(stored: "").showsTile(state: .nothing, pinned: false))
        XCTAssertTrue(MapFilter(stored: "favorites,full,drape").showsAnyTile)
        XCTAssertFalse(MapFilter(stored: "favorites,full,drape,off").showsAnyTile)
        XCTAssertTrue(MapFilter(stored: "").showsTile(state: .off, pinned: false))   // #2100
        XCTAssertFalse(MapFilter(stored: "off").showsTile(state: .off, pinned: false))
        XCTAssertTrue(MapFilter(stored: "full").showsTile(state: .off, pinned: false))
    }

    /// #2214 (Qt twin: test_the_filter_menu_hides_the_patch_layer_and_its_gestures).
    @MainActor
    func testAirportPatchHidesTheLayer() {
        XCTAssertTrue(MapFilter(stored: "").showsPatch)
        XCTAssertFalse(MapFilter(stored: "patch").showsPatch)
        XCTAssertEqual(MapFilter(stored: "patch,icao").stored, "icao,patch")
        XCTAssertTrue(MapFilter(stored: "patch").showsAnyTile)
        XCTAssertEqual(MapFilterItem.sections.last?.header, "Patch")
    }
}
