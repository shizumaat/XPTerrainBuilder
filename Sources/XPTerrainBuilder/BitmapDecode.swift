import CoreGraphics
import Foundation
import ImageIO

/// Encoded image bytes (JPEG/PNG) turned into a plain bitmap CGImage, on the
/// calling thread — call it off the main thread (#2310).
///
/// `kCGImageSourceShouldCacheImmediately` alone is not enough: the image it
/// returns still carries ImageIO's provider, and SwiftUI's renderer asks that
/// provider for an IOSurface at draw time, which sends the JPEG through
/// ImageIO's hardware path (CMPhoto → VideoToolbox → Metal device creation)
/// on the main thread — 1.0.590 hung there for good. Redrawing into a
/// CGBitmapContext leaves an image whose provider is the bitmap's own bytes,
/// so the render only uploads pixels.
enum BitmapDecode {
    static func image(data: Data) -> CGImage? {
        dispatchPrecondition(condition: .notOnQueue(.main))
        guard let source = CGImageSourceCreateWithData(data as CFData, [
            kCGImageSourceShouldCache: false,
        ] as CFDictionary),
              let lazy = CGImageSourceCreateImageAtIndex(source, 0, [
                  kCGImageSourceShouldCache: false,
              ] as CFDictionary) else { return nil }
        return bitmap(lazy)
    }

    /// `image` drawn into a premultiplied RGBA bitmap context: decoded now.
    static func bitmap(_ image: CGImage) -> CGImage? {
        let width = image.width, height = image.height
        guard width > 0, height > 0,
              let ctx = CGContext(data: nil, width: width, height: height,
                                  bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)
                                      ?? CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
        else { return nil }
        ctx.interpolationQuality = .none
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        return ctx.makeImage()
    }
}
