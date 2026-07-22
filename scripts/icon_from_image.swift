// Builds the app icon from a rendered source image: composites the artwork
// onto the Apple-guideline squircle over a matched studio backdrop, with an
// optional rotation (used to give IconSource2's design IconSource1's more
// heroic diagonal). Emits AppIcon.iconset + preview-1024.png.
// Usage: swift scripts/icon_from_image.swift <source-image> <output-dir> [angle-degrees]
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024

guard CommandLine.arguments.count > 2 else {
    FileHandle.standardError.write(Data(
        "usage: icon_from_image.swift <source-image> <output-dir> [angle-degrees]\n".utf8))
    exit(1)
}
let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let angleDegrees = CommandLine.arguments.count > 3 ? Double(CommandLine.arguments[3]) ?? 0 : 0

guard let src = CGImageSourceCreateWithURL(sourceURL as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
    FileHandle.standardError.write(Data("could not read \(sourceURL.path)\n".utf8))
    exit(1)
}

let space = CGColorSpaceCreateDeviceRGB()

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

/// The source render's backdrop color, sampled from its top-left corner —
/// the squircle fill uses exactly this so the rotated image blends with no
/// visible seams.
let backdropColor: CGColor = {
    var pixel = [UInt8](repeating: 0, count: 4)
    let ctx = CGContext(data: &pixel, width: 1, height: 1,
                        bitsPerComponent: 8, bytesPerRow: 4, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    // Draw so that the source's near-corner pixel lands in our 1x1 buffer.
    ctx.draw(image, in: CGRect(x: -0.06 * CGFloat(image.width), y: -0.90 * CGFloat(image.height),
                               width: CGFloat(image.width), height: CGFloat(image.height)))
    return color(CGFloat(pixel[0]) / 255, CGFloat(pixel[1]) / 255, CGFloat(pixel[2]) / 255)
}()

func render() -> CGImage {
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    let shape = CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824),
                       cornerWidth: 185, cornerHeight: 185, transform: nil)
    // Soft canvas shadow behind the squircle.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 24,
                  color: color(0, 0, 0, 0.30))
    ctx.addPath(shape)
    ctx.setFillColor(backdropColor)
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()
    // Flat fill in the render's own backdrop color — rotation corners
    // become invisible.
    ctx.setFillColor(backdropColor)
    ctx.fill(CGRect(x: 0, y: 0, width: SIZE, height: SIZE))

    // Artwork: rotated about its center, scaled to fill the content area.
    // The sources carry generous margins, so post-rotation corners stay
    // clear of the subject.
    let w = CGFloat(image.width), h = CGFloat(image.height)
    ctx.saveGState()
    ctx.translateBy(x: 512, y: 488)
    ctx.rotate(by: CGFloat(angleDegrees) * .pi / 180)
    let scale = 884 / max(w, h)
    ctx.scaleBy(x: scale, y: scale)
    ctx.interpolationQuality = .high
    ctx.draw(image, in: CGRect(x: -w / 2, y: -h / 2, width: w, height: h))
    ctx.restoreGState()
    ctx.restoreGState()

    // Hairline inner rim on the squircle.
    ctx.addPath(shape)
    ctx.setStrokeColor(color(0, 0, 0, 0.08))
    ctx.setLineWidth(2)
    ctx.strokePath()

    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, size: Int, to url: URL) {
    let ctx = CGContext(data: nil, width: size, height: size,
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.interpolationQuality = .high
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: size, height: size))
    let scaled = ctx.makeImage()!
    let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, scaled, nil)
    CGImageDestinationFinalize(dest)
}

try? FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)
let master = render()
let iconset = outURL.appendingPathComponent("AppIcon.iconset", isDirectory: true)
try? FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
let sizes: [(name: String, px: Int)] = [
    ("icon_16x16", 16), ("icon_16x16@2x", 32),
    ("icon_32x32", 32), ("icon_32x32@2x", 64),
    ("icon_128x128", 128), ("icon_128x128@2x", 256),
    ("icon_256x256", 256), ("icon_256x256@2x", 512),
    ("icon_512x512", 512), ("icon_512x512@2x", 1024),
]
for entry in sizes {
    writePNG(master, size: entry.px, to: iconset.appendingPathComponent("\(entry.name).png"))
}
writePNG(master, size: 1024, to: outURL.appendingPathComponent("preview-1024.png"))
print("Rendered \(iconset.path)")
