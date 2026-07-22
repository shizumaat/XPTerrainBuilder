// Liquid-Glass-era icon: a simple white Mjolnir PROFILE (head edge-on, a
// natural striking pose) with a lightning-bolt cutout through the head, on
// a storm-gray gradient. Outputs:
//   glyph-1024.png    white glyph alone on transparency (Icon Composer layer)
//   AppIcon.iconset   full-square fallback icns art (system masks the squircle)
//   preview-1024.png  squircle-masked composite (runtime Dock / Finder icon)
// Usage: swift scripts/icon_glass.swift <output-dir>
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024
let space = CGColorSpaceCreateDeviceRGB()

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Glyph (white profile, bolt punched out)

/// Bolt polygon (unit coords, zigzag along +y), drawn rotated so it runs
/// horizontally — in line with the head's striking faces.
let boltPoints: [CGPoint] = [
    CGPoint(x: 58, y: 0), CGPoint(x: 18, y: 118), CGPoint(x: 46, y: 118),
    CGPoint(x: 8, y: 230), CGPoint(x: 96, y: 88), CGPoint(x: 62, y: 88),
    CGPoint(x: 104, y: 0),
]

func renderGlyph() -> CGImage {
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    // Head profile matched to the IconSource2 render's proportions: a tall
    // central body (600×380, ~1.6:1) beveling down at each end to smaller
    // flat striking faces (~72% of the body height).
    let head = CGMutablePath()
    head.move(to: CGPoint(x: 306, y: 860))              // body top-left
    head.addLine(to: CGPoint(x: 718, y: 860))           // body top edge
    head.addLine(to: CGPoint(x: 794, y: 812))           // bevel taper (right)
    head.addQuadCurve(to: CGPoint(x: 812, y: 786),
                      control: CGPoint(x: 809, y: 802))
    head.addLine(to: CGPoint(x: 812, y: 554))           // right striking face
    head.addQuadCurve(to: CGPoint(x: 794, y: 528),
                      control: CGPoint(x: 809, y: 538))
    head.addLine(to: CGPoint(x: 718, y: 480))           // bevel back to body
    head.addLine(to: CGPoint(x: 306, y: 480))           // body bottom edge
    head.addLine(to: CGPoint(x: 230, y: 528))           // bevel taper (left)
    head.addQuadCurve(to: CGPoint(x: 212, y: 554),
                      control: CGPoint(x: 215, y: 538))
    head.addLine(to: CGPoint(x: 212, y: 786))           // left striking face
    head.addQuadCurve(to: CGPoint(x: 230, y: 812),
                      control: CGPoint(x: 215, y: 802))
    head.closeSubpath()                                 // left bevel to start

    // Handle: stout and short like the render — the head stays dominant.
    let handle = CGPath(roundedRect: CGRect(x: 512 - 65, y: 0, width: 130, height: 520),
                        cornerWidth: 62, cornerHeight: 62, transform: nil)

    // Bolt cutout on the body, mirrored, running with the striking faces.
    let s: CGFloat = 1.8
    let ox: CGFloat = 512 - 115 * s
    let oy: CGFloat = 770
    let bolt = CGMutablePath()
    for (i, pt) in boltPoints.enumerated() {
        let point = CGPoint(x: 1024 - (ox + pt.y * s), y: oy - pt.x * s)
        if i == 0 { bolt.move(to: point) } else { bolt.addLine(to: point) }
    }
    bolt.closeSubpath()

    // Standard-margin placement: rotate 120° CCW (striking pose), then
    // center the rotated silhouette and scale it to the icon grid's glyph
    // area (~700pt of the 1024 canvas).
    let rot = CGAffineTransform(translationX: 512, y: 512)
        .rotated(by: 2 * .pi / 3)
        .translatedBy(x: -512, y: -512)
    let union = CGMutablePath()
    union.addPath(head)
    union.addPath(handle)
    var rotCopy = rot
    let rotatedUnion = union.copy(using: &rotCopy)!
    let bounds = rotatedUnion.boundingBoxOfPath
    let target: CGFloat = 700
    let fitScale = min(target / bounds.width, target / bounds.height)
    let fit = CGAffineTransform(translationX: -bounds.midX, y: -bounds.midY)
        .concatenating(CGAffineTransform(scaleX: fitScale, y: fitScale))
        .concatenating(CGAffineTransform(translationX: 512, y: 512))
    var full = rot.concatenating(fit)

    // White fills (separately, so opposing windings can't carve holes),
    // then the bolt punched clean through.
    ctx.setFillColor(color(1, 1, 1))
    ctx.addPath(head.copy(using: &full)!)
    ctx.fillPath()
    ctx.addPath(handle.copy(using: &full)!)
    ctx.fillPath()
    ctx.setBlendMode(.clear)
    ctx.addPath(bolt.copy(using: &full)!)
    ctx.fillPath()
    ctx.setBlendMode(.normal)

    return ctx.makeImage()!
}

// MARK: - Backgrounds

func stormGradient(_ ctx: CGContext) {
    let bg = CGGradient(colorsSpace: space, colors: [
        color(0.44, 0.47, 0.54), color(0.30, 0.32, 0.38), color(0.17, 0.18, 0.23),
    ] as CFArray, locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(bg,
        start: CGPoint(x: 512, y: SIZE), end: CGPoint(x: 512, y: 0), options: [])
}

/// Full-square fallback art: opaque edge to edge, so the system clips it
/// into the squircle itself (no gray backdrop, no double-rounding).
func renderSquare(glyph: CGImage) -> CGImage {
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    stormGradient(ctx)
    // Soft grounding shadow, then the glyph.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -12), blur: 30,
                  color: color(0, 0, 0, 0.35))
    ctx.draw(glyph, in: CGRect(x: 0, y: 0, width: SIZE, height: SIZE))
    ctx.restoreGState()
    return ctx.makeImage()!
}

/// Squircle-masked composite for the runtime Dock icon and Finder custom
/// icon (those surfaces show artwork verbatim, so it must be pre-rounded).
func renderSquircle(glyph: CGImage) -> CGImage {
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    let shape = CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824),
                       cornerWidth: 185, cornerHeight: 185, transform: nil)
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -8), blur: 18,
                  color: color(0, 0, 0, 0.30))
    ctx.addPath(shape)
    ctx.setFillColor(color(0.2, 0.2, 0.25))
    ctx.fillPath()
    ctx.restoreGState()
    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()
    stormGradient(ctx)
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 26,
                  color: color(0, 0, 0, 0.35))
    // Scale the glyph into the squircle's content frame.
    ctx.translateBy(x: 512, y: 512)
    ctx.scaleBy(x: 824 / SIZE, y: 824 / SIZE)
    ctx.draw(glyph, in: CGRect(x: -512, y: -512, width: SIZE, height: SIZE))
    ctx.restoreGState()
    ctx.restoreGState()
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

// MARK: - Main

let outDir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "glass-icon"
let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
try? FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)

let glyph = renderGlyph()
writePNG(glyph, size: 1024, to: outURL.appendingPathComponent("glyph-1024.png"))

let square = renderSquare(glyph: glyph)
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
    writePNG(square, size: entry.px, to: iconset.appendingPathComponent("\(entry.name).png"))
}
writePNG(renderSquircle(glyph: glyph), size: 1024,
         to: outURL.appendingPathComponent("preview-1024.png"))
print("Rendered \(iconset.path)")
