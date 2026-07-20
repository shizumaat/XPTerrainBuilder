// Renders the XPScenery Smith app icon:
// an FAA-sectional-style airport symbol on a chart background, half of it
// under a brass-and-wood magnifying glass that genuinely magnifies what's
// inside the lens. Usage: swift scripts/make_icon.swift <output-dir>
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

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Chart + airport symbol (drawn twice: base and magnified)

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

/// The full "scene": night IFR chart plus the airport symbol, dead center.
/// Sized so that after 1.6x magnification the beacon star's top clips under
/// the lens rim (disc 90 -> star top ~2.12R = 191 base -> ~305 vs 296 lens).
func drawScene(_ ctx: CGContext) {
    drawChart(ctx)
    // Disc sized so the star's top (1.942R) exceeds what the distorted lens
    // shows at its edge (lensRadius / M(rim) ≈ 206) — the tip passes under
    // the rim with magenta reaching the glass edge.
    drawAirportSymbol(ctx, center: CGPoint(x: 512, y: 512), discRadius: 108)
}

// MARK: - Magnifying glass

let lensCenter = CGPoint(x: 512, y: 512)
let lensRadius: CGFloat = 296
let rimWidth: CGFloat = 30
let magnification: CGFloat = 1.6

// Frosted-graphite glass material (macOS 27 Preview-loupe territory,
// not storybook brass) — a notch lighter so it separates from the black.
let graphiteLight = color(0.56, 0.58, 0.63)
let graphiteMid = color(0.30, 0.32, 0.36)
let graphiteDark = color(0.13, 0.14, 0.17)

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

// True lens distortion: continuous radial magnification, 1.6x at the lens
// center easing to ~1.5x at the rim. A real lens never skips or repeats
// content — the image just compresses toward the frame — so the star's tip
// squashes smoothly and stays magenta all the way to where the rim covers it.
let rimFalloff: CGFloat = 0.10
let falloffExponent: CGFloat = 6

func radialMagnification(_ r: CGFloat) -> CGFloat {
    magnification - rimFalloff * magnification * pow(r / lensRadius, falloffExponent)
}

/// Render the flat scene to pixels, then resample it through the radial
/// magnification profile for everything inside the lens.
func makeDistortedLensImage() -> CGImage {
    let w = Int(SIZE)
    let space = CGColorSpaceCreateDeviceRGB()

    var src = [UInt8](repeating: 0, count: w * w * 4)
    src.withUnsafeMutableBytes { raw in
        let ctx = CGContext(data: raw.baseAddress, width: w, height: w,
                            bitsPerComponent: 8, bytesPerRow: w * 4, space: space,
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        drawScene(ctx)
    }

    var dst = [UInt8](repeating: 0, count: w * w * 4)
    let cx = lensCenter.x
    let cyMem = SIZE - lensCenter.y // bitmap rows run top-down

    let minX = max(0, Int(cx - lensRadius) - 1), maxX = min(w - 1, Int(cx + lensRadius) + 1)
    let minY = max(0, Int(cyMem - lensRadius) - 1), maxY = min(w - 1, Int(cyMem + lensRadius) + 1)

    src.withUnsafeBufferPointer { srcBuf in
        dst.withUnsafeMutableBufferPointer { dstBuf in
            let s = srcBuf.baseAddress!, d = dstBuf.baseAddress!
            for py in minY...maxY {
                for px in minX...maxX {
                    let dx = CGFloat(px) + 0.5 - cx
                    let dy = CGFloat(py) + 0.5 - cyMem
                    let r = (dx * dx + dy * dy).squareRoot()
                    guard r < lensRadius else { continue }
                    let m = radialMagnification(r)
                    let sx = cx + dx / m
                    let sy = cyMem + dy / m
                    // Bilinear sample.
                    let x0 = Int(sx), y0 = Int(sy)
                    guard x0 >= 0, y0 >= 0, x0 < w - 1, y0 < w - 1 else { continue }
                    let fx = sx - CGFloat(x0), fy = sy - CGFloat(y0)
                    let di = (py * w + px) * 4
                    for c in 0..<4 {
                        let p00 = CGFloat(s[(y0 * w + x0) * 4 + c])
                        let p10 = CGFloat(s[(y0 * w + x0 + 1) * 4 + c])
                        let p01 = CGFloat(s[((y0 + 1) * w + x0) * 4 + c])
                        let p11 = CGFloat(s[((y0 + 1) * w + x0 + 1) * 4 + c])
                        let top = p00 + (p10 - p00) * fx
                        let bottom = p01 + (p11 - p01) * fx
                        d[di + c] = UInt8(max(0, min(255, top + (bottom - top) * fy)))
                    }
                }
            }
        }
    }

    let data = CFDataCreate(nil, dst, dst.count)!
    let provider = CGDataProvider(data: data)!
    return CGImage(width: w, height: w, bitsPerComponent: 8, bitsPerPixel: 32,
                   bytesPerRow: w * 4, space: space,
                   bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue),
                   provider: provider, decode: nil, shouldInterpolate: true,
                   intent: .defaultIntent)!
}

func drawMagnifiedContent(_ ctx: CGContext) {
    ctx.saveGState()
    ctx.addPath(lensPath())
    ctx.clip()
    ctx.draw(makeDistortedLensImage(), in: CGRect(x: 0, y: 0, width: SIZE, height: SIZE))
    ctx.restoreGState()

    // Flatter glass tint: faint cool lift over the black, restrained edge.
    ctx.saveGState()
    ctx.addPath(lensPath())
    ctx.clip()
    let space = CGColorSpaceCreateDeviceRGB()
    let tint = CGGradient(colorsSpace: space, colors: [
        color(0.70, 0.82, 0.95, 0.10),
        color(0.55, 0.68, 0.85, 0.04),
        color(0.05, 0.08, 0.14, 0.16),
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
        color(1, 1, 1, 0.16), color(1, 1, 1, 0.0),
    ] as CFArray, locations: [0, 1])!
    ctx.drawRadialGradient(sheen, startCenter: sheenCenter, startRadius: 0,
                           endCenter: sheenCenter, endRadius: lensRadius * 0.85, options: [])

    // Sharp crescent streak — quieter on the dark glass.
    ctx.setStrokeColor(color(1, 1, 1, 0.45))
    ctx.setLineWidth(16)
    ctx.setLineCap(.round)
    ctx.addArc(center: lensCenter, radius: lensRadius - rimWidth - 22,
               startAngle: .pi * 0.62, endAngle: .pi * 0.86, clockwise: false)
    ctx.strokePath()
    ctx.setLineWidth(7)
    ctx.setStrokeColor(color(1, 1, 1, 0.28))
    ctx.addArc(center: lensCenter, radius: lensRadius - rimWidth - 52,
               startAngle: .pi * 0.66, endAngle: .pi * 0.76, clockwise: false)
    ctx.strokePath()
    ctx.restoreGState()
}

func drawBrassRim(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()

    // Soft ambient shadow under the glass.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 30,
                  color: color(0.05, 0.06, 0.08, 0.28))
    ctx.setFillColor(graphiteMid)
    ctx.addPath(ringPath(outer: lensRadius + rimWidth, inner: lensRadius))
    ctx.fillPath(using: .evenOdd)
    ctx.restoreGState()

    // Graphite body: one quiet top-lit gradient.
    ctx.saveGState()
    ctx.addPath(ringPath(outer: lensRadius + rimWidth, inner: lensRadius))
    ctx.clip(using: .evenOdd)
    let graphite = CGGradient(colorsSpace: space, colors: [
        graphiteLight, graphiteMid, graphiteDark,
    ] as CFArray, locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(graphite,
        start: CGPoint(x: lensCenter.x, y: lensCenter.y + lensRadius + rimWidth),
        end: CGPoint(x: lensCenter.x, y: lensCenter.y - lensRadius - rimWidth),
        options: [])
    ctx.restoreGState()

    // Hairlines: darker outer edge, light inner edge where glass meets rim.
    ctx.setStrokeColor(color(0.04, 0.05, 0.06, 0.55))
    ctx.setLineWidth(3)
    ctx.strokeEllipse(in: CGRect(x: lensCenter.x - lensRadius - rimWidth, y: lensCenter.y - lensRadius - rimWidth,
                                 width: (lensRadius + rimWidth) * 2, height: (lensRadius + rimWidth) * 2))
    ctx.setStrokeColor(color(1, 1, 1, 0.30))
    ctx.setLineWidth(2.5)
    ctx.strokeEllipse(in: CGRect(x: lensCenter.x - lensRadius, y: lensCenter.y - lensRadius,
                                 width: lensRadius * 2, height: lensRadius * 2))

    // Restrained specular on the rim's upper left.
    ctx.setStrokeColor(color(1, 1, 1, 0.35))
    ctx.setLineWidth(5)
    ctx.setLineCap(.round)
    ctx.addArc(center: lensCenter, radius: lensRadius + rimWidth / 2,
               startAngle: .pi * 0.58, endAngle: .pi * 0.92, clockwise: false)
    ctx.strokePath()
}

func drawHandle(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()
    // Short rounded capsule, same graphite material, down-right at -45°.
    let angle: CGFloat = -.pi / 4
    let start = CGPoint(x: lensCenter.x + cos(angle) * (lensRadius + rimWidth - 10),
                        y: lensCenter.y + sin(angle) * (lensRadius + rimWidth - 10))

    ctx.saveGState()
    ctx.translateBy(x: start.x, y: start.y)
    ctx.rotate(by: angle)
    ctx.setShadow(offset: CGSize(width: 0, height: -8), blur: 22,
                  color: color(0.05, 0.06, 0.08, 0.25))

    let handleLength: CGFloat = 260
    let handleWidth: CGFloat = 72
    let capsule = CGPath(roundedRect: CGRect(x: 0, y: -handleWidth / 2,
                                             width: handleLength, height: handleWidth),
                         cornerWidth: handleWidth / 2, cornerHeight: handleWidth / 2,
                         transform: nil)
    ctx.saveGState()
    ctx.addPath(capsule)
    ctx.clip()
    let grad = CGGradient(colorsSpace: space, colors: [
        graphiteLight, graphiteMid, graphiteDark,
    ] as CFArray, locations: [0, 0.5, 1])!
    ctx.drawLinearGradient(grad,
        start: CGPoint(x: 0, y: handleWidth / 2),
        end: CGPoint(x: 0, y: -handleWidth / 2), options: [])
    // Soft top highlight.
    ctx.setStrokeColor(color(1, 1, 1, 0.22))
    ctx.setLineWidth(4)
    ctx.move(to: CGPoint(x: 22, y: handleWidth / 2 - 12))
    ctx.addLine(to: CGPoint(x: handleLength - 26, y: handleWidth / 2 - 12))
    ctx.strokePath()
    ctx.restoreGState()

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
    ctx.setFillColor(nightBottom)
    ctx.addPath(shape)
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()

    drawScene(ctx)          // base chart (airport hidden under the lens)
    drawBrassRim(ctx)       // rim first: casts shadow onto the chart
    drawMagnifiedContent(ctx)
    drawGlint(ctx)

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
