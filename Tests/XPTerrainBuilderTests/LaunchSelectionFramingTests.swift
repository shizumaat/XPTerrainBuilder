import XCTest
import CoreGraphics
@testable import XPTerrainBuilder

/// #1554: at launch the map frames the restored tile selection — one tile
/// fills the view with the Activity-row margin, several fit their union,
/// and nothing restored leaves the camera where it was.
@MainActor
final class LaunchSelectionFramingTests: XCTestCase {
    private let size = CGSize(width: 1000, height: 700)

    private func controller() -> AnalysisController {
        let controller = AnalysisController()
        controller.mapCanvasSize.value = size
        controller.mapCamera.value = MapCamera.fitted(to: size)
        return controller
    }

    /// The tile rectangle's corners in view points under `cam`.
    private func corners(_ tiles: [(lat: Int, lon: Int)], _ cam: MapCamera)
        -> (CGPoint, CGPoint) {
        let lats = tiles.map(\.lat), lons = tiles.map(\.lon)
        let nw = cam.point(lon: Double(lons.min()!), lat: Double(lats.max()! + 1), in: size)
        let se = cam.point(lon: Double(lons.max()! + 1), lat: Double(lats.min()!), in: size)
        return (nw, se)
    }

    private func assertInView(_ tiles: [(lat: Int, lon: Int)], _ cam: MapCamera,
                              file: StaticString = #filePath, line: UInt = #line) {
        let (nw, se) = corners(tiles, cam)
        XCTAssertGreaterThanOrEqual(nw.x, 0, file: file, line: line)
        XCTAssertGreaterThanOrEqual(nw.y, 0, file: file, line: line)
        XCTAssertLessThanOrEqual(se.x, size.width, file: file, line: line)
        XCTAssertLessThanOrEqual(se.y, size.height, file: file, line: line)
    }

    func testOneRestoredTileIsFramed() {
        let controller = controller()
        controller.frameRestoredSelection([(lat: 48, lon: -6)])
        let cam = controller.mapCamera.value
        XCTAssertEqual(cam, MapCamera.framing(tileLat: 48, lon: -6, in: size))
        assertInView([(lat: 48, lon: -6)], cam)
        // The tile fills the view: it spans most of its limiting side.
        let (nw, se) = corners([(lat: 48, lon: -6)], cam)
        XCTAssertGreaterThan(max((se.x - nw.x) / size.width,
                                 (se.y - nw.y) / size.height), 0.7)
    }

    func testThreeRestoredTilesFrameTheirUnion() {
        let controller = controller()
        let tiles = [(lat: 48, lon: -6), (lat: 49, lon: -6), (lat: 48, lon: -4)]
        let before = controller.mapCamera.value
        controller.frameRestoredSelection(tiles)
        let cam = controller.mapCamera.value
        XCTAssertNotEqual(cam, before)
        XCTAssertEqual(cam.centerLon, -4.5, accuracy: 1e-9)
        XCTAssertEqual(cam.centerLat, 49, accuracy: 1e-9)
        assertInView(tiles, cam)
        XCTAssertGreaterThan(cam.scale, 10 * before.scale)
    }

    func testNothingRestoredLeavesTheCamera() {
        let controller = controller()
        let before = controller.mapCamera.value
        controller.frameRestoredSelection([])
        XCTAssertEqual(controller.mapCamera.value, before)
    }
}
