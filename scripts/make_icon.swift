// Renders the XPScenery Smith app icon:
// an FAA-sectional-style airport symbol on a night IFR-chart background,
// with an Xcode-style crossed hammer and screwdriver in front — building
// and adjusting scenery. Usage: swift scripts/make_icon.swift <output-dir>
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024

// MARK: - Palette

// Dark-mode IFR palette: near-black canvas, slate airways, cyan accent.
let nightTop = CGColor(red: 0.11, green: 0.12, blue: 0.15, alpha: 1)
let nightBottom = CGColor(red: 0.03, green: 0.035, blue: 0.05, alpha: 1)
let airwaySlate = CGColor(red: 0.55, green: 0.63, blue: 0.75, alpha: 0.42)
let airwayCyan = CGColor(red: 0.25, green: 0.78, blue: 0.90, alpha: 0.55)
/// VFR sectional airport magenta (lighted, services) — lifted a touch to
/// read on the night chart.
let sectionalMagenta = color(0.62, 0.16, 0.34)
/// Runways are cut out of the disc — chart background shows through.
let nightMid = color(0.065, 0.072, 0.095)

// Tool materials: brushed steel and graphite, with the chart's cyan carried
// into the screwdriver grip so the tools belong to the same palette.
let steelLight = color(0.82, 0.85, 0.90)
let steelMid = color(0.62, 0.65, 0.71)
let steelDark = color(0.38, 0.41, 0.47)
let graphiteHandle = color(0.17, 0.18, 0.22)
let graphiteHandleHi = color(0.30, 0.32, 0.37)
let gripCyan = color(0.10, 0.30, 0.38)
let gripCyanHi = color(0.16, 0.45, 0.55)
let gripCyanDark = color(0.05, 0.16, 0.22)

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Chart

/// Night IFR-chart backdrop: near-black gradient with enroute-chart
/// furniture — airways, hollow waypoint fixes, a partial VOR compass rose.
func drawChart(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()
    let night = CGGradient(colorsSpace: space, colors: [
        nightTop, nightBottom,
    ] as CFArray, locations: [0, 1])!
    ctx.saveGState()
    ctx.clip(to: CGRect(x: -SIZE, y: -SIZE, width: SIZE * 3, height: SIZE * 3))
    ctx.drawLinearGradient(night,
        start: CGPoint(x: 0, y: SIZE * 1.5),
        end: CGPoint(x: 0, y: -SIZE * 0.5), options: [])
    ctx.restoreGState()

    func airway(_ from: CGPoint, _ to: CGPoint, color: CGColor, width: CGFloat, dashed: Bool = false) {
        ctx.saveGState()
        ctx.setStrokeColor(color)
        ctx.setLineWidth(width)
        if dashed { ctx.setLineDash(phase: 0, lengths: [26, 18]) }
        ctx.move(to: from)
        ctx.addLine(to: to)
        ctx.strokePath()
        ctx.restoreGState()
    }

    /// Hollow waypoint triangle, as on enroute charts.
    func fix(at p: CGPoint, size: CGFloat, color: CGColor) {
        ctx.saveGState()
        ctx.setStrokeColor(color)
        ctx.setLineWidth(5)
        ctx.move(to: CGPoint(x: p.x, y: p.y + size))
        ctx.addLine(to: CGPoint(x: p.x - size * 0.87, y: p.y - size * 0.5))
        ctx.addLine(to: CGPoint(x: p.x + size * 0.87, y: p.y - size * 0.5))
        ctx.closePath()
        ctx.strokePath()
        ctx.restoreGState()
    }

    // Airways converging on the airport (as they do at a hub).
    airway(CGPoint(x: -100, y: 760), CGPoint(x: 1124, y: 300), color: airwaySlate, width: 4)
    airway(CGPoint(x: 180, y: -100), CGPoint(x: 830, y: 1124), color: airwaySlate, width: 4)
    airway(CGPoint(x: -100, y: 300), CGPoint(x: 1124, y: 620), color: airwayCyan, width: 4)
    airway(CGPoint(x: 700, y: -100), CGPoint(x: 220, y: 1124), color: airwaySlate, width: 3, dashed: true)

    // Waypoint fixes on the airways.
    fix(at: CGPoint(x: 250, y: 628), size: 24, color: airwaySlate)
    fix(at: CGPoint(x: 796, y: 423), size: 24, color: airwayCyan)
    fix(at: CGPoint(x: 405, y: 279), size: 22, color: airwaySlate)

    // Partial VOR compass rose, lower right.
    let roseCenter = CGPoint(x: 880, y: 130)
    let roseRadius: CGFloat = 210
    ctx.setStrokeColor(airwaySlate)
    ctx.setLineWidth(4)
    ctx.strokeEllipse(in: CGRect(x: roseCenter.x - roseRadius, y: roseCenter.y - roseRadius,
                                 width: roseRadius * 2, height: roseRadius * 2))
    for i in 0..<36 {
        let angle = CGFloat(i) * .pi / 18
        let long = i % 3 == 0
        let inner = roseRadius - (long ? 26 : 14)
        ctx.move(to: CGPoint(x: roseCenter.x + cos(angle) * inner,
                             y: roseCenter.y + sin(angle) * inner))
        ctx.addLine(to: CGPoint(x: roseCenter.x + cos(angle) * roseRadius,
                                y: roseCenter.y + sin(angle) * roseRadius))
    }
    ctx.strokePath()
}

/// VFR sectional airport symbol, KTDO-style: solid magenta disc, four stubby
/// service ticks, a rotating-beacon star on top (with its punched center),
/// and the gray runway strip cutting through the disc.
func drawAirportSymbol(_ ctx: CGContext, center: CGPoint, discRadius R: CGFloat) {
    ctx.saveGState()
    ctx.translateBy(x: center.x, y: center.y)
    ctx.setFillColor(sectionalMagenta)

    // Disc.
    ctx.fillEllipse(in: CGRect(x: -R, y: -R, width: R * 2, height: R * 2))

    // Three stubby rectangular service ticks — the star replaces the top one.
    let tickWidth = R * 0.42
    let tickReach = R * 1.30
    for i in 1..<4 {
        ctx.saveGState()
        ctx.rotate(by: CGFloat(i) * .pi / 2)
        ctx.fill(CGRect(x: -tickWidth / 2, y: R - 6, width: tickWidth, height: tickReach - R + 6))
        ctx.restoreGState()
    }

    // Beacon star in place of the top spur: center height solved so its two
    // lower points land exactly on the disc's edge.
    let outerR = R * 0.55
    let innerR = outerR * 0.42
    let starCenter = CGPoint(x: 0, y: R * 1.392)
    let star = CGMutablePath()
    for k in 0..<10 {
        let angle = CGFloat.pi / 2 + CGFloat(k) * .pi / 5
        let radius = k % 2 == 0 ? outerR : innerR
        let point = CGPoint(x: starCenter.x + cos(angle) * radius,
                            y: starCenter.y + sin(angle) * radius)
        if k == 0 { star.move(to: point) } else { star.addLine(to: point) }
    }
    star.closeSubpath()
    star.addEllipse(in: CGRect(x: starCenter.x - R * 0.11, y: starCenter.y - R * 0.11,
                               width: R * 0.22, height: R * 0.22))
    ctx.addPath(star)
    ctx.fillPath(using: .evenOdd)

    // Runway strip: cut out of the disc (chart background shows through),
    // square corners, inset from the edge by the same margin as a spur's
    // width.
    ctx.rotate(by: -.pi / 15)
    let stripLength = (R - tickWidth) * 2
    let stripWidth = R * 0.29
    ctx.setFillColor(nightMid)
    ctx.fill(CGRect(x: -stripLength / 2, y: -stripWidth / 2,
                    width: stripLength, height: stripWidth))

    ctx.restoreGState()
}

// MARK: - Tools (Xcode-style crossed hammer + screwdriver)

/// Both tools cross here; the airport symbol sits above, in the V between
/// the hammer head and the screwdriver blade.
let crossPoint = CGPoint(x: 512, y: 455)

/// Linear gradient across the local y (width) of a tool part, light side up.
func fillAcross(_ ctx: CGContext, path: CGPath, from yLight: CGFloat, to yDark: CGFloat,
                colors: [CGColor], locations: [CGFloat] = [0, 1]) {
    ctx.saveGState()
    ctx.addPath(path)
    ctx.clip()
    let space = CGColorSpaceCreateDeviceRGB()
    let grad = CGGradient(colorsSpace: space, colors: colors as CFArray, locations: locations)!
    ctx.drawLinearGradient(grad,
        start: CGPoint(x: 0, y: yLight), end: CGPoint(x: 0, y: yDark), options: [])
    ctx.restoreGState()
}

/// Runs `body` rotated about the cross point, wrapped in a transparency
/// layer so the whole tool casts one soft, globally-downward shadow (the
/// shadow is set before the rotation, so it doesn't rotate with the tool).
func toolLayer(_ ctx: CGContext, angle: CGFloat, body: (CGContext) -> Void) {
    ctx.saveGState()
    ctx.translateBy(x: crossPoint.x, y: crossPoint.y)
    ctx.setShadow(offset: CGSize(width: 0, height: -14), blur: 26,
                  color: color(0, 0, 0, 0.50))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)
    ctx.saveGState()
    ctx.rotate(by: angle)
    body(ctx)
    ctx.restoreGState()
    ctx.endTransparencyLayer()
    ctx.restoreGState()
}

/// Screwdriver pointing up-right (blade at +x), drawn under the hammer.
/// Local frame: +x along the shaft toward the tip, +y is the up-left side
/// (which faces the icon's top, so it gets the light).
func drawScrewdriver(_ ctx: CGContext) {
    toolLayer(ctx, angle: .pi / 4) { ctx in
        // Grip: chart-cyan capsule with darker moulded ribs.
        let grip = CGPath(roundedRect: CGRect(x: -375, y: -42, width: 260, height: 84),
                          cornerWidth: 42, cornerHeight: 42, transform: nil)
        fillAcross(ctx, path: grip, from: 42, to: -42,
                   colors: [gripCyanHi, gripCyan, gripCyanDark], locations: [0, 0.45, 1])
        ctx.saveGState()
        ctx.addPath(grip)
        ctx.clip()
        ctx.setFillColor(gripCyanDark)
        for s: CGFloat in [-330, -283, -236, -189] {
            ctx.fill(CGRect(x: s - 6, y: -42, width: 12, height: 84))
        }
        ctx.restoreGState()

        // Ferrule between grip and shaft.
        let ferrule = CGPath(roundedRect: CGRect(x: -122, y: -28, width: 36, height: 56),
                             cornerWidth: 8, cornerHeight: 8, transform: nil)
        fillAcross(ctx, path: ferrule, from: 28, to: -28,
                   colors: [steelMid, steelDark])

        // Shaft, then the flat blade flaring at the tip.
        let shaft = CGMutablePath()
        shaft.addRect(CGRect(x: -92, y: -14, width: 324, height: 28))
        shaft.move(to: CGPoint(x: 232, y: 14))
        shaft.addLine(to: CGPoint(x: 282, y: 24))
        shaft.addLine(to: CGPoint(x: 300, y: 24))
        shaft.addLine(to: CGPoint(x: 300, y: -24))
        shaft.addLine(to: CGPoint(x: 282, y: -24))
        shaft.addLine(to: CGPoint(x: 232, y: -14))
        shaft.closeSubpath()
        fillAcross(ctx, path: shaft, from: 24, to: -24,
                   colors: [steelLight, steelMid, steelDark], locations: [0, 0.55, 1])
    }
}

/// Hammer with the head up-left (at +x) and the handle running down-right,
/// drawn over the screwdriver — the Xcode hero tool. Local frame: +x along
/// the handle toward the head; the icon's top is toward local -y here, so
/// the light lives on the -y side.
func drawHammer(_ ctx: CGContext) {
    toolLayer(ctx, angle: .pi * 3 / 4) { ctx in
        // Graphite handle.
        let handle = CGPath(roundedRect: CGRect(x: -355, y: -33, width: 545, height: 66),
                            cornerWidth: 33, cornerHeight: 33, transform: nil)
        fillAcross(ctx, path: handle, from: -33, to: 33,
                   colors: [graphiteHandleHi, graphiteHandle, color(0.09, 0.10, 0.12)],
                   locations: [0, 0.4, 1])

        // Steel head: sledge block perpendicular to the handle, with a
        // darker cheek band on the handle side and a bright striking edge.
        let head = CGPath(roundedRect: CGRect(x: 180, y: -138, width: 110, height: 276),
                          cornerWidth: 26, cornerHeight: 26, transform: nil)
        fillAcross(ctx, path: head, from: -138, to: 138,
                   colors: [steelLight, steelMid, steelDark], locations: [0, 0.5, 1])
        ctx.saveGState()
        ctx.addPath(head)
        ctx.clip()
        ctx.setFillColor(steelDark)
        ctx.fill(CGRect(x: 180, y: -138, width: 26, height: 276))
        ctx.setStrokeColor(color(1, 1, 1, 0.35))
        ctx.setLineWidth(6)
        ctx.move(to: CGPoint(x: 287, y: -132))
        ctx.addLine(to: CGPoint(x: 287, y: 132))
        ctx.strokePath()
        ctx.restoreGState()
    }
}

// MARK: - Compose

/// The full scene: night IFR chart, the airport symbol up top, and the
/// crossed tools in front.
func drawScene(_ ctx: CGContext) {
    drawChart(ctx)
    drawAirportSymbol(ctx, center: CGPoint(x: 512, y: 685), discRadius: 112)
    drawScrewdriver(ctx)
    drawHammer(ctx)
}

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
    ctx.setFillColor(nightBottom)
    ctx.addPath(shape)
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()

    drawScene(ctx)

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
