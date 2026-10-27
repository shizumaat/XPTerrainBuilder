import XCTest
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
@testable import XPTerrainBuilder
@testable import SceneryKit

/// #1540: past the ZL where the server answers "no imagery here" (Bing's
/// camera tile at HECA is ZL 20 and 21 although BI declares no ceiling),
/// the map draws the finest imagery the place has, scaled up — never the
/// server's empty tile. Disk cache only: no network.
final class ImageryOverzoomTests: XCTestCase {
    static let source = """
    {"code": "BI", "region": "Global", "name": "Bing", "combined": false, "members": [],
     "buildable": true, "previewable": true, "reason": "", "attribution": "",
     "preview": {"template": "https://ecn.t0.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=1",
                 "referer": ""}}
    """

    func jpeg() throws -> Data {
        let ctx = try XCTUnwrap(CGContext(data: nil, width: 8, height: 8, bitsPerComponent: 8,
                                          bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                                          bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue))
        ctx.setFillColor(CGColor(red: 0.2, green: 0.4, blue: 0.1, alpha: 1))
        ctx.fill(CGRect(x: 0, y: 0, width: 8, height: 8))
        let out = NSMutableData()
        let dest = try XCTUnwrap(CGImageDestinationCreateWithData(out, UTType.jpeg.identifier as CFString, 1, nil))
        CGImageDestinationAddImage(dest, try XCTUnwrap(ctx.makeImage()), nil)
        XCTAssertTrue(CGImageDestinationFinalize(dest))
        return out as Data
    }

    @MainActor
    func testANoImageryTileDrawsTheFinestImageryScaledUp() async throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("imagery-overzoom-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let (x, y) = (1231526, 864412)          // ZL 21 at HECA
        func put(_ z: Int, _ data: Data) throws {
            let dir = root.appendingPathComponent("Previews/livemap/BI/\(z)", isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try data.write(to: dir.appendingPathComponent("\(x >> (21 - z))_\(y >> (21 - z)).jpg"))
        }
        try put(21, Data(count: 1033))           // Bing's camera tile, as 1.0.436 cached it
        try put(20, Data(count: 1033))
        try put(19, try jpeg())

        let imagery = ImageryModel()
        let sources = try JSONDecoder().decode([O4ImagerySource].self,
                                               from: Data("[\(Self.source)]".utf8))
        imagery.configure(sources: sources, dataRoot: root)
        imagery.setProvider("BI")
        XCTAssertEqual(imagery.activeMaxZL, 21)

        var hit: (image: CGImage, alpha: CGFloat, ancestor: MapOverzoom.Ancestor)?
        for _ in 0..<200 where hit == nil {
            hit = imagery.displayImage(z: 21, x: x, y: y)
            if hit == nil { try await Task.sleep(for: .milliseconds(20)) }
        }
        let anc = try XCTUnwrap(hit?.ancestor, "no imagery drawn at ZL 21")
        XCTAssertEqual(anc, MapOverzoom.ancestor(z: 21, x: x, y: y, maxZ: 19))
        XCTAssertEqual(imagery.drawnMaxZL(lat: 30.1219, lon: 31.4056), 19)
        // the cached camera tiles are gone, the imagery stays
        let livemap = root.appendingPathComponent("Previews/livemap/BI")
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: livemap.appendingPathComponent("21/\(x)_\(y).jpg").path))
        XCTAssertTrue(FileManager.default.fileExists(
            atPath: livemap.appendingPathComponent("19/\(x >> 2)_\(y >> 2).jpg").path))
    }
}
