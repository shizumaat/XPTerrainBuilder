import XCTest
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
@testable import XPTerrainBuilder

/// #2310: map imagery reaches the renderer as a plain bitmap, decoded off
/// the main thread — never an ImageIO-backed JPEG whose decode the draw
/// would run (through Metal device creation) on the main thread.
final class BitmapDecodeTests: XCTestCase {
    func jpeg() throws -> Data {
        let ctx = try XCTUnwrap(CGContext(data: nil, width: 16, height: 8, bitsPerComponent: 8,
                                          bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                                          bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue))
        ctx.setFillColor(CGColor(red: 0.2, green: 0.4, blue: 0.1, alpha: 1))
        ctx.fill(CGRect(x: 0, y: 0, width: 16, height: 8))
        let out = NSMutableData()
        let dest = try XCTUnwrap(CGImageDestinationCreateWithData(
            out, UTType.jpeg.identifier as CFString, 1, nil))
        CGImageDestinationAddImage(dest, try XCTUnwrap(ctx.makeImage()), nil)
        XCTAssertTrue(CGImageDestinationFinalize(dest))
        return out as Data
    }

    /// The control: what ImageIO hands back (even with ShouldCacheImmediately)
    /// is still JPEG-backed — the shape the hang sample drew.
    func testImageIOImageIsJPEGBacked() throws {
        let source = try XCTUnwrap(CGImageSourceCreateWithData(try jpeg() as CFData, nil))
        let image = try XCTUnwrap(CGImageSourceCreateImageAtIndex(
            source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary))
        XCTAssertEqual(image.utType as String?, UTType.jpeg.identifier)
    }

    func testDecodeOffMainGivesABitmap() async throws {
        let data = try jpeg()
        let (image, onMain) = await Task.detached {
            (BitmapDecode.image(data: data), Thread.isMainThread)
        }.value
        XCTAssertFalse(onMain)
        let bitmap = try XCTUnwrap(image)
        XCTAssertNil(bitmap.utType, "no ImageIO source behind the image")
        XCTAssertEqual(bitmap.width, 16)
        XCTAssertEqual(bitmap.height, 8)
        XCTAssertEqual(bitmap.bitsPerPixel, 32)
        XCTAssertEqual(bitmap.alphaInfo, .premultipliedLast)
        // The pixels are already in the provider: no decode left to do.
        let bytes = try XCTUnwrap(bitmap.dataProvider?.data)
        XCTAssertGreaterThanOrEqual(CFDataGetLength(bytes), bitmap.bytesPerRow * bitmap.height)
        let px = CFDataGetBytePtr(bytes)!
        XCTAssertTrue(px[1] > px[0] && px[1] > px[2], "the green tile stays green")
    }

    func testGarbageIsNil() async {
        let image = await Task.detached { BitmapDecode.image(data: Data([1, 2, 3])) }.value
        XCTAssertNil(image)
    }
}
