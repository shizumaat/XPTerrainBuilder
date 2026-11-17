import XCTest
@testable import XPTerrainBuilder

/// Owner 2026-11-17T15:55Z: the app starts with no tiles selected. A
/// selection an earlier version stored is forgotten at launch, so a tile
/// the user picks is never added to last session's set.
final class LaunchSelectionTests: XCTestCase {
    func testLaunchForgetsTheStoredSelection() {
        let suite = "LaunchSelectionTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(["+37-026", "+38-028"], forKey: PrefKeys.selectedTiles)
        defaults.set("+37-026", forKey: PrefKeys.activeTile)
        LaunchSelection.start(defaults: defaults)
        XCTAssertNil(defaults.stringArray(forKey: PrefKeys.selectedTiles))
        XCTAssertNil(defaults.string(forKey: PrefKeys.activeTile))
    }

    func testBuildModelNoLongerStoresTheSelection() throws {
        // The selection is session state: nothing in BuildModel writes it.
        let source = try String(contentsOfFile: #filePath
            .replacingOccurrences(of: "Tests/XPTerrainBuilderTests/LaunchSelectionTests.swift",
                                  with: "Sources/XPTerrainBuilder/BuildModel.swift"),
            encoding: .utf8)
        XCTAssertFalse(source.contains("PrefKeys.selectedTiles"))
        XCTAssertFalse(source.contains("PrefKeys.activeTile"))
    }
}
