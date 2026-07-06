// Renders the XPScenery Doctor app icon:
// an FAA-sectional-style airport symbol on a chart background, half of it
// under a brass-and-wood magnifying glass that genuinely magnifies what's
// inside the lens. Usage: swift scripts/make_icon.swift <output-dir>
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024

// MARK: - Palette

// Bolder, more saturated palette per the macOS 27 icon refinements.
let chartCream = CGColor(red: 0.969, green: 0.949, blue: 0.882, alpha: 1)
let chartCreamDeep = CGColor(red: 0.886, green: 0.831, blue: 0.694, alpha: 1)
let chartGrid = CGColor(red: 0.42, green: 0.60, blue: 0.72, alpha: 0.65)
let chartContour = CGColor(red: 0.76, green: 0.55, blue: 0.33, alpha: 0.30)
/// FAA sectional blue: towered airports (KPDX is towered).
let sectionalBlue = CGColor(red: 0.055, green: 0.32, blue: 0.71, alpha: 1)

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Chart + airport symbol (drawn twice: base and magnified)

/// Sectional-chart background covering the whole canvas: soft vertical
/// gradient, crisp graticule, a single restrained contour band.
func drawChart(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()
    let paper = CGGradient(colorsSpace: space, colors: [
        chartCream, chartCreamDeep,
    ] as CFArray, locations: [0, 1])!
    ctx.saveGState()
    ctx.clip(to: CGRect(x: -SIZE, y: -SIZE, width: SIZE * 3, height: SIZE * 3))
    ctx.drawLinearGradient(paper,
        start: CGPoint(x: 0, y: SIZE * 1.5),
        end: CGPoint(x: 0, y: -SIZE * 0.5), options: [])
    ctx.restoreGState()

    // Graticule: thinner and crisper than a paper chart, bolder blue.
    ctx.setStrokeColor(chartGrid)
    ctx.setLineWidth(2.5)
    var x: CGFloat = -SIZE
    while x < SIZE * 2 {
        ctx.move(to: CGPoint(x: x, y: -SIZE))
        ctx.addLine(to: CGPoint(x: x, y: SIZE * 2))
        x += 128
    }
    var y: CGFloat = -SIZE
    while y < SIZE * 2 {
        ctx.move(to: CGPoint(x: -SIZE, y: y))
        ctx.addLine(to: CGPoint(x: SIZE * 2, y: y))
        y += 128
    }
    ctx.strokePath()

    // One quiet terrain contour, lower right.
    ctx.setStrokeColor(chartContour)
    ctx.setLineWidth(5)
    ctx.addArc(center: CGPoint(x: 1000, y: 40), radius: 500,
               startAngle: .pi * 0.45, endAngle: .pi * 0.95, clockwise: false)
    ctx.strokePath()
}

/// KPDX as depicted on the sectional: large towered airports show the actual
/// runway layout in blue — two long parallels (10L/28R, 10R/28L) and the
/// 3/21 crosswind angling across the west end.
func drawKPDX(_ ctx: CGContext, center: CGPoint, scale: CGFloat) {
    ctx.saveGState()
    ctx.translateBy(x: center.x, y: center.y)
    ctx.scaleBy(x: scale, y: scale)
    ctx.setFillColor(sectionalBlue)

    func runway(cx: CGFloat, cy: CGFloat, length: CGFloat, width: CGFloat, angle: CGFloat) {
        ctx.saveGState()
        ctx.translateBy(x: cx, y: cy)
        ctx.rotate(by: angle)
        ctx.fill(CGRect(x: -length / 2, y: -width / 2, width: length, height: width))
        ctx.restoreGState()
    }

    let heading: CGFloat = -.pi / 20            // runways 10/28: just south of east-west
    runway(cx: 0, cy: 52, length: 330, width: 36, angle: heading)     // 10L/28R (north)
    runway(cx: 14, cy: -52, length: 380, width: 36, angle: heading)   // 10R/28L (south, longer)
    // 3/21 crosswind: crossing the parallels' west ends, angling northeast.
    runway(cx: -108, cy: 10, length: 260, width: 32, angle: .pi / 3.4)

    ctx.restoreGState()
}

/// The full "scene": chart plus the airport diagram.
/// Placement: at 1.6x magnification about the lens center, only content
/// within lensRadius/1.6 of the lens center stays visible inside the glass —
/// KPDX sits so its eastern runway ends land there, with the crosswind
/// runway out on the bare chart.
func drawScene(_ ctx: CGContext) {
    drawChart(ctx)
    drawKPDX(ctx, center: CGPoint(x: 445, y: 490), scale: 1.05)
}

// MARK: - Magnifying glass

let lensCenter = CGPoint(x: 620, y: 470)
let lensRadius: CGFloat = 240
let rimWidth: CGFloat = 34
let magnification: CGFloat = 1.6

func lensPath() -> CGPath {
    CGPath(ellipseIn: CGRect(x: lensCenter.x - lensRadius, y: lensCenter.y - lensRadius,
                             width: lensRadius * 2, height: lensRadius * 2), transform: nil)
}

func ringPath(outer: CGFloat, inner: CGFloat) -> CGPath {
    let path = CGMutablePath()
    path.addEllipse(in: CGRect(x: lensCenter.x - outer, y: lensCenter.y - outer,
                               width: outer * 2, height: outer * 2))
    path.addEllipse(in: CGRect(x: lensCenter.x - inner, y: lensCenter.y - inner,
                               width: inner * 2, height: inner * 2))
    return path
}

func drawMagnifiedContent(_ ctx: CGContext) {
    ctx.saveGState()
    ctx.addPath(lensPath())
    ctx.clip()
    // Magnify about the lens center.
    ctx.translateBy(x: lensCenter.x, y: lensCenter.y)
    ctx.scaleBy(x: magnification, y: magnification)
    ctx.translateBy(x: -lensCenter.x, y: -lensCenter.y)
    drawScene(ctx)
    ctx.restoreGState()

    // Liquid Glass edge refraction: near the rim, light bends harder — an
    // annulus re-rendered at higher magnification creates the visible
    // "shape distortion at the edge" of the macOS 27 style.
    let refractionBand: CGFloat = 26
    ctx.saveGState()
    ctx.addPath(ringPath(outer: lensRadius, inner: lensRadius - refractionBand))
    ctx.clip(using: .evenOdd)
    ctx.translateBy(x: lensCenter.x, y: lensCenter.y)
    ctx.scaleBy(x: magnification * 1.10, y: magnification * 1.10)
    ctx.translateBy(x: -lensCenter.x, y: -lensCenter.y)
    drawScene(ctx)
    ctx.restoreGState()

    // Flatter glass tint: light wash, restrained edge falloff.
    ctx.saveGState()
    ctx.addPath(lensPath())
    ctx.clip()
    let space = CGColorSpaceCreateDeviceRGB()
    let tint = CGGradient(colorsSpace: space, colors: [
        color(0.78, 0.89, 0.94, 0.08),
        color(0.60, 0.76, 0.84, 0.04),
        color(0.25, 0.38, 0.48, 0.16),
    ] as CFArray, locations: [0, 0.82, 1])!
    ctx.drawRadialGradient(tint, startCenter: lensCenter, startRadius: 0,
                           endCenter: lensCenter, endRadius: lensRadius, options: [])
    ctx.restoreGState()
}

func drawGlint(_ ctx: CGContext) {
    ctx.saveGState()
    ctx.addPath(lensPath())
    ctx.clip()

    // Broad soft sheen, upper left.
    let space = CGColorSpaceCreateDeviceRGB()
    let sheenCenter = CGPoint(x: lensCenter.x - lensRadius * 0.48,
                              y: lensCenter.y + lensRadius * 0.56)
    let sheen = CGGradient(colorsSpace: space, colors: [
        color(1, 1, 1, 0.28), color(1, 1, 1, 0.0),
    ] as CFArray, locations: [0, 1])!
    ctx.drawRadialGradient(sheen, startCenter: sheenCenter, startRadius: 0,
                           endCenter: sheenCenter, endRadius: lensRadius * 0.85, options: [])

    // Sharp crescent streak.
    ctx.setStrokeColor(color(1, 1, 1, 0.75))
    ctx.setLineWidth(20)
    ctx.setLineCap(.round)
    ctx.addArc(center: lensCenter, radius: lensRadius - rimWidth - 26,
               startAngle: .pi * 0.60, endAngle: .pi * 0.88, clockwise: false)
    ctx.strokePath()
    ctx.setLineWidth(9)
    ctx.setStrokeColor(color(1, 1, 1, 0.5))
    ctx.addArc(center: lensCenter, radius: lensRadius - rimWidth - 60,
               startAngle: .pi * 0.64, endAngle: .pi * 0.76, clockwise: false)
    ctx.strokePath()
    ctx.restoreGState()
}

func drawBrassRim(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()

    // Drop shadow of the whole glass onto the chart — tighter and lighter
    // for the flatter macOS 27 look.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 8, height: -12), blur: 24,
                  color: color(0.1, 0.08, 0.04, 0.35))
    ctx.setFillColor(color(0.42, 0.28, 0.10, 1))
    ctx.addPath(ringPath(outer: lensRadius + rimWidth, inner: lensRadius))
    ctx.fillPath(using: .evenOdd)
    ctx.restoreGState()

    // Brass body: diagonal gradient clipped to the ring.
    ctx.saveGState()
    ctx.addPath(ringPath(outer: lensRadius + rimWidth, inner: lensRadius))
    ctx.clip(using: .evenOdd)
    let brass = CGGradient(colorsSpace: space, colors: [
        color(0.98, 0.87, 0.55), color(0.83, 0.62, 0.25),
        color(0.55, 0.36, 0.10), color(0.90, 0.74, 0.40),
        color(0.62, 0.42, 0.14),
    ] as CFArray, locations: [0, 0.3, 0.55, 0.8, 1])!
    ctx.drawLinearGradient(brass,
        start: CGPoint(x: lensCenter.x - lensRadius, y: lensCenter.y + lensRadius),
        end: CGPoint(x: lensCenter.x + lensRadius, y: lensCenter.y - lensRadius),
        options: [])
    ctx.restoreGState()

    // Rim edges: thin dark outer + inner lines, bright specular arc.
    ctx.setStrokeColor(color(0.30, 0.19, 0.05, 0.9))
    ctx.setLineWidth(5)
    ctx.strokeEllipse(in: CGRect(x: lensCenter.x - lensRadius - rimWidth, y: lensCenter.y - lensRadius - rimWidth,
                                 width: (lensRadius + rimWidth) * 2, height: (lensRadius + rimWidth) * 2))
    ctx.strokeEllipse(in: CGRect(x: lensCenter.x - lensRadius, y: lensCenter.y - lensRadius,
                                 width: lensRadius * 2, height: lensRadius * 2))
    ctx.setStrokeColor(color(1, 0.96, 0.82, 0.9))
    ctx.setLineWidth(7)
    ctx.setLineCap(.round)
    ctx.addArc(center: lensCenter, radius: lensRadius + rimWidth / 2,
               startAngle: .pi * 0.55, endAngle: .pi * 0.95, clockwise: false)
    ctx.strokePath()
}

func drawHandle(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()
    // Handle runs down-right from the rim at -45°.
    let angle: CGFloat = -.pi / 4
    let start = CGPoint(x: lensCenter.x + cos(angle) * (lensRadius + rimWidth - 6),
                        y: lensCenter.y + sin(angle) * (lensRadius + rimWidth - 6))

    ctx.saveGState()
    ctx.translateBy(x: start.x, y: start.y)
    ctx.rotate(by: angle)
    ctx.setShadow(offset: CGSize(width: 10, height: -14), blur: 28,
                  color: color(0.1, 0.08, 0.04, 0.4))

    // Brass ferrule connecting rim and handle.
    let ferrule = CGRect(x: -8, y: -34, width: 78, height: 68)
    ctx.saveGState()
    ctx.clip(to: ferrule)
    let ferruleGrad = CGGradient(colorsSpace: space, colors: [
        color(0.95, 0.83, 0.50), color(0.60, 0.40, 0.12), color(0.88, 0.72, 0.38),
    ] as CFArray, locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(ferruleGrad,
        start: CGPoint(x: 0, y: 34), end: CGPoint(x: 0, y: -34), options: [])
    ctx.restoreGState()

    // Wooden grip: tapered, rounded end.
    let gripLength: CGFloat = 300
    let grip = CGMutablePath()
    grip.move(to: CGPoint(x: 66, y: -30))
    grip.addLine(to: CGPoint(x: 66 + gripLength, y: -21))
    grip.addArc(center: CGPoint(x: 66 + gripLength, y: 0), radius: 21,
                startAngle: -.pi / 2, endAngle: .pi / 2, clockwise: false)
    grip.addLine(to: CGPoint(x: 66, y: 30))
    grip.closeSubpath()

    ctx.saveGState()
    ctx.addPath(grip)
    ctx.clip()
    let wood = CGGradient(colorsSpace: space, colors: [
        color(0.52, 0.32, 0.16), color(0.35, 0.20, 0.09),
        color(0.46, 0.28, 0.13), color(0.24, 0.13, 0.05),
    ] as CFArray, locations: [0, 0.45, 0.7, 1])!
    ctx.drawLinearGradient(wood,
        start: CGPoint(x: 66, y: 30), end: CGPoint(x: 66, y: -30), options: [])
    // Grain.
    ctx.setStrokeColor(color(0.18, 0.10, 0.04, 0.35))
    ctx.setLineWidth(3)
    for offset: CGFloat in [-14, -4, 8, 16] {
        ctx.move(to: CGPoint(x: 70, y: offset))
        ctx.addCurve(to: CGPoint(x: 66 + gripLength, y: offset * 0.6),
                     control1: CGPoint(x: 150, y: offset + 6),
                     control2: CGPoint(x: 240, y: offset - 5))
        ctx.strokePath()
    }
    // Top highlight along the grip.
    ctx.setStrokeColor(color(1, 0.85, 0.6, 0.25))
    ctx.setLineWidth(6)
    ctx.move(to: CGPoint(x: 74, y: 18))
    ctx.addLine(to: CGPoint(x: 50 + gripLength, y: 13))
    ctx.strokePath()
    ctx.restoreGState()

    // Grip outline.
    ctx.setStrokeColor(color(0.15, 0.08, 0.03, 0.8))
    ctx.setLineWidth(4)
    ctx.addPath(grip)
    ctx.strokePath()
    ctx.restoreGState()
}

// MARK: - Compose

func renderMaster() -> CGImage {
    let space = CGColorSpaceCreateDeviceRGB()
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    // macOS icon shape: 824pt squircle-ish rounded rect centered in 1024.
    let content = CGRect(x: 100, y: 100, width: 824, height: 824)
    let shape = CGPath(roundedRect: content, cornerWidth: 185, cornerHeight: 185, transform: nil)

    // Soft canvas shadow behind the shape.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -12), blur: 30,
                  color: color(0, 0, 0, 0.30))
    ctx.setFillColor(chartCream)
    ctx.addPath(shape)
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()

    drawScene(ctx)          // base chart + symbol
    drawBrassRim(ctx)       // rim first: casts shadow onto the chart
    drawMagnifiedContent(ctx)
    drawGlint(ctx)
    drawHandle(ctx)

    // Subtle inner bevel on the icon shape.
    ctx.addPath(shape)
    ctx.setStrokeColor(color(1, 1, 1, 0.25))
    ctx.setLineWidth(3)
    ctx.strokePath()
    ctx.restoreGState()

    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, size: Int, to url: URL) {
    let space = CGColorSpaceCreateDeviceRGB()
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

let outDir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon-out"
let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
try? FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)

let master = renderMaster()
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
