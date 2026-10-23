import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// The default-airport marks survive a scan that was already running when
/// the engine's index arrived (1.0.418: the map showed custom airports
/// only — the scan's finished overlays, built from the list it captured
/// before the index landed, replaced the marks setGlobalAirports had
/// installed).
@MainActor
final class GlobalAirportMarksTests: XCTestCase {
    private var root: URL!
    private var savedXPlanePath: String?

    override func setUp() async throws {
        root = FileManager.default.temporaryDirectory
            .appendingPathComponent("marks-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(
            at: root.appendingPathComponent("Custom Scenery", isDirectory: true),
            withIntermediateDirectories: true)
        savedXPlanePath = UserDefaults.standard.string(forKey: PrefKeys.xplanePath)
    }

    override func tearDown() async throws {
        try? FileManager.default.removeItem(at: SceneryIndexCache.cacheURL(for: root))
        try? FileManager.default.removeItem(at: root)
        if let savedXPlanePath {
            UserDefaults.standard.set(savedXPlanePath, forKey: PrefKeys.xplanePath)
        } else {
            UserDefaults.standard.removeObject(forKey: PrefKeys.xplanePath)
        }
    }

    func testIndexDeliveredDuringScanKeepsDefaultMarks() async throws {
        let controller = AnalysisController()
        controller.xplanePath = root.path
        controller.refreshInstallation()
        XCTAssertTrue(controller.isScanningInstallation)
        // The engine's index lands while the scan is in flight.
        controller.setGlobalAirports([
            GlobalAirport(icao: "TEST", latitude: 10, longitude: 20, sizeClass: 1),
        ])
        let deadline = Date().addingTimeInterval(20)
        while controller.isScanningInstallation, Date() < deadline {
            try await Task.sleep(for: .milliseconds(20))
        }
        XCTAssertFalse(controller.isScanningInstallation, "TIMED_OUT waiting for the scan")
        XCTAssertEqual(controller.mapOverlays.defaultAirports.map(\.icao), ["TEST"])
    }
}
