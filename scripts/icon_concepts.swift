// Icon concept previews: a wireframe-mesh ANVIL being struck by a small
// Mjolnir-style hammer — the app hammering terrain flat for airports.
// Apple-guideline squircle canvas (no freeform), three style directions:
//   1-night.png      night-chart navy, glowing cyan wireframe (app's map look)
//   2-blueprint.png  blueprint blue, white drafting wireframe
//   3-terrain.png    hypsometric terrain-colored mesh on a dawn sky
// Usage: swift scripts/icon_concepts.swift <output-dir>
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Variant styling

struct Style {
    let name: String
    let bgTop: CGColor
    let bgBottom: CGColor
    /// Wire glow pass (wide, soft); nil = no glow.
    let glow: CGColor?
    /// Wire crisp pass.
    let wire: CGColor
    /// Optional vertical color ramp for the wire (bottom, mid, top) —
    /// overrides `wire` per line when set.
    let ramp: (CGColor, CGColor, CGColor)?
    let accent: CGColor          // impact arcs / sparks
    let hammerLight: CGColor
    let hammerMid: CGColor
    let hammerDark: CGColor
    let handleLight: CGColor
    let handleDark: CGColor
    let drawsGrid: Bool          // faint drafting grid on the background
}

let styles: [Style] = [
    Style(name: "1-night",
          bgTop: color(0.10, 0.11, 0.15), bgBottom: color(0.03, 0.035, 0.055),
          glow: color(0.25, 0.78, 0.90, 0.35),
          wire: color(0.75, 0.93, 1.0, 0.95),
          ramp: nil,
          accent: color(0.35, 0.85, 0.95),
          hammerLight: color(0.85, 0.88, 0.92), hammerMid: color(0.58, 0.62, 0.68),
          hammerDark: color(0.30, 0.33, 0.38),
          handleLight: color(0.55, 0.38, 0.22), handleDark: color(0.32, 0.20, 0.10),
          drawsGrid: false),
    Style(name: "2-blueprint",
          bgTop: color(0.33, 0.58, 0.89), bgBottom: color(0.17, 0.40, 0.74),
          glow: nil,
          wire: color(1, 1, 1, 0.92),
          ramp: nil,
          accent: color(1, 1, 1, 0.95),
          hammerLight: color(0.92, 0.94, 0.97), hammerMid: color(0.66, 0.70, 0.75),
          hammerDark: color(0.36, 0.40, 0.46),
          handleLight: color(0.86, 0.65, 0.40), handleDark: color(0.51, 0.32, 0.15),
          drawsGrid: true),
    Style(name: "3-terrain",
          bgTop: color(0.16, 0.16, 0.30), bgBottom: color(0.72, 0.40, 0.28),
          glow: nil,
          wire: color(1, 1, 1, 0.9),
          ramp: (color(0.30, 0.62, 0.38), color(0.72, 0.55, 0.32), color(0.97, 0.97, 1.0)),
          accent: color(1.0, 0.85, 0.55),
          hammerLight: color(0.90, 0.92, 0.96), hammerMid: color(0.62, 0.66, 0.72),
          hammerDark: color(0.32, 0.35, 0.41),
          handleLight: color(0.55, 0.38, 0.22), handleDark: color(0.32, 0.20, 0.10),
          drawsGrid: false),
]

// MARK: - Anvil geometry (side view, +depth pseudo-3D)

// Content coordinates, y-up. The anvil face (top) sits at y≈570; the small
// hammer strikes it at IMPACT, denting the face grid.
let IMPACT = CGPoint(x: 618, y: 586)
let DEPTH = CGVector(dx: 30, dy: 18)

/// Vertical dent in the top face near the impact point.
func dent(_ x: CGFloat) -> CGFloat {
    let d = (x - IMPACT.x) / 90
    return 14 * exp(-d * d)
}

/// Width of the anvil body at height y (front silhouette), by segments:
/// face (570) → shoulder (520) → waist (440) → flare (360) → base (330).
func bodyEdges(_ y: CGFloat) -> (left: CGFloat, right: CGFloat)? {
    func lerp(_ a: CGFloat, _ b: CGFloat, _ t: CGFloat) -> CGFloat { a + (b - a) * t }
    switch y {
    case 520...570:
        let t = (570 - y) / 50
        return (lerp(340, 380, t), lerp(724, 690, t))
    case 440..<520:
        let t = (520 - y) / 80
        return (lerp(380, 424, t), lerp(690, 646, t))
    case 360..<440:
        let t = (440 - y) / 80
        return (lerp(424, 386, t), lerp(646, 684, t))
    case 300..<360:
        return (376, 694)
    default:
        return nil
    }
}

func strokeWire(_ ctx: CGContext, style: Style, midY: CGFloat = 0,
                width: CGFloat, _ body: (CGContext) -> Void) {
    if let glow = style.glow {
        ctx.saveGState()
        ctx.setStrokeColor(glow)
        ctx.setLineWidth(width + 9)
        ctx.setLineCap(.round)
        body(ctx)
        ctx.strokePath()
        ctx.restoreGState()
    }
    ctx.saveGState()
    if let ramp = style.ramp {
        // Pick the ramp color for this line's height (300..590).
        let t = min(max((midY - 300) / 290, 0), 1)
        func mix(_ a: CGColor, _ b: CGColor, _ t: CGFloat) -> CGColor {
            let ca = a.components ?? [0, 0, 0, 1], cb = b.components ?? [0, 0, 0, 1]
            return color(ca[0] + (cb[0] - ca[0]) * t, ca[1] + (cb[1] - ca[1]) * t,
                         ca[2] + (cb[2] - ca[2]) * t)
        }
        let c = t < 0.5 ? mix(ramp.0, ramp.1, t * 2) : mix(ramp.1, ramp.2, (t - 0.5) * 2)
        ctx.setStrokeColor(c)
    } else {
        ctx.setStrokeColor(style.wire)
    }
    ctx.setLineWidth(width)
    ctx.setLineCap(.round)
    body(ctx)
    ctx.strokePath()
    ctx.restoreGState()
}

func drawAnvil(_ ctx: CGContext, style: Style) {
    // --- Top face: parallelogram with a dented mesh grid ---------------
    let faceL: CGFloat = 316, faceR: CGFloat = 748, faceY: CGFloat = 570
    func faceFront(_ x: CGFloat) -> CGPoint { CGPoint(x: x, y: faceY - dent(x) * 0.0) }
    // Face grid: columns (front→back) and rows (left→right, dented).
    let cols = 9, rows = 3
    for r in 0...rows {
        let t = CGFloat(r) / CGFloat(rows)
        strokeWire(ctx, style: style, midY: 580, width: r == 0 ? 3.4 : 2.2) { c in
            var first = true
            for i in 0...36 {
                let x = faceL + (faceR - faceL) * CGFloat(i) / 36
                let p = CGPoint(x: x + DEPTH.dx * t,
                                y: faceY + DEPTH.dy * t - dent(x) * (1.0 - 0.35 * t))
                if first { c.move(to: p); first = false } else { c.addLine(to: p) }
            }
        }
    }
    for i in 0...cols {
        let x = faceL + (faceR - faceL) * CGFloat(i) / CGFloat(cols)
        strokeWire(ctx, style: style, midY: 580, width: 2.2) { c in
            c.move(to: CGPoint(x: x, y: faceY - dent(x)))
            c.addLine(to: CGPoint(x: x + DEPTH.dx, y: faceY + DEPTH.dy - dent(x) * 0.65))
        }
    }

    // --- Horn (left): tapering curved cone with section lines ----------
    strokeWire(ctx, style: style, midY: 545, width: 3.4) { c in
        c.move(to: CGPoint(x: faceL, y: faceY))
        c.addCurve(to: CGPoint(x: 176, y: 538),
                   control1: CGPoint(x: 250, y: 566), control2: CGPoint(x: 204, y: 552))
        c.addCurve(to: CGPoint(x: 316, y: 500),
                   control1: CGPoint(x: 216, y: 518), control2: CGPoint(x: 262, y: 502))
    }
    for (t, w) in [(CGFloat(0.28), CGFloat(2.0)), (0.58, 2.0), (0.85, 2.0)] {
        let x = 176 + (faceL - 176) * t
        let yTop = 538 + (faceY - 538) * t
        let yBot = 538 + (500 - 538) * t * 1.15
        strokeWire(ctx, style: style, midY: 540, width: w) { c in
            c.move(to: CGPoint(x: x, y: yTop))
            c.addCurve(to: CGPoint(x: x + 6, y: yBot),
                       control1: CGPoint(x: x - 8, y: (yTop + yBot) / 2),
                       control2: CGPoint(x: x - 4, y: yBot + 6))
        }
    }

    // --- Body: contour rows + verticals + diagonal mesh ----------------
    let rowYs: [CGFloat] = [540, 505, 470, 440, 412, 384, 360]
    for y in rowYs {
        guard let e = bodyEdges(y) else { continue }
        strokeWire(ctx, style: style, midY: y, width: 2.2) { c in
            c.move(to: CGPoint(x: e.left, y: y))
            c.addLine(to: CGPoint(x: e.right, y: y))
        }
        // Depth hint on the right side.
        strokeWire(ctx, style: style, midY: y, width: 1.6) { c in
            c.move(to: CGPoint(x: e.right, y: y))
            c.addLine(to: CGPoint(x: e.right + DEPTH.dx * 0.8, y: y + DEPTH.dy * 0.8))
        }
    }
    // Front silhouette edges.
    strokeWire(ctx, style: style, midY: 460, width: 3.4) { c in
        c.move(to: CGPoint(x: 340, y: faceY))
        c.addCurve(to: CGPoint(x: 424, y: 440),
                   control1: CGPoint(x: 372, y: 528), control2: CGPoint(x: 408, y: 484))
        c.addCurve(to: CGPoint(x: 386, y: 360),
                   control1: CGPoint(x: 438, y: 402), control2: CGPoint(x: 402, y: 376))
        c.move(to: CGPoint(x: 724, y: faceY))
        c.addCurve(to: CGPoint(x: 646, y: 440),
                   control1: CGPoint(x: 696, y: 528), control2: CGPoint(x: 662, y: 484))
        c.addCurve(to: CGPoint(x: 684, y: 360),
                   control1: CGPoint(x: 632, y: 402), control2: CGPoint(x: 668, y: 376))
    }
    // Vertical mesh lines through the body.
    for f in [0.22, 0.42, 0.62, 0.82] {
        strokeWire(ctx, style: style, midY: 460, width: 1.8) { c in
            var first = true
            for y in stride(from: CGFloat(570), through: 360, by: -14) {
                guard let e = bodyEdges(y) else { continue }
                let x = e.left + (e.right - e.left) * CGFloat(f)
                if first { c.move(to: CGPoint(x: x, y: y)); first = false }
                else { c.addLine(to: CGPoint(x: x, y: y)) }
            }
        }
    }
    // Diagonals for the triangulated-mesh feel (waist band).
    for i in 0..<6 {
        let x0 = 424 + CGFloat(i) * 38
        strokeWire(ctx, style: style, midY: 440, width: 1.3) { c in
            c.move(to: CGPoint(x: x0, y: 470))
            c.addLine(to: CGPoint(x: x0 + 30, y: 412))
        }
    }

    // --- Base slab ------------------------------------------------------
    strokeWire(ctx, style: style, midY: 330, width: 3.4) { c in
        c.addRect(CGRect(x: 356, y: 300, width: 358, height: 60))
    }
    strokeWire(ctx, style: style, midY: 330, width: 1.8) { c in
        for f in [0.25, 0.5, 0.75] {
            c.move(to: CGPoint(x: 356 + 358 * CGFloat(f), y: 300))
            c.addLine(to: CGPoint(x: 356 + 358 * CGFloat(f), y: 360))
        }
        // Depth top edge.
        c.move(to: CGPoint(x: 714, y: 360))
        c.addLine(to: CGPoint(x: 714 + DEPTH.dx * 0.8, y: 360 + DEPTH.dy * 0.8))
        c.move(to: CGPoint(x: 714 + DEPTH.dx * 0.8, y: 360 + DEPTH.dy * 0.8))
        c.addLine(to: CGPoint(x: 714 + DEPTH.dx * 0.8, y: 306))
    }
}

// MARK: - Mjolnir

/// Small, stout Norse hammer striking down-left onto the impact point:
/// broad rectangular head with flared square ends, short wrapped handle
/// with a pommel loop.
func drawMjolnir(_ ctx: CGContext, style: Style) {
    let space = CGColorSpaceCreateDeviceRGB()
    ctx.saveGState()
    ctx.translateBy(x: IMPACT.x, y: IMPACT.y)
    ctx.rotate(by: -0.42)          // strike axis leaning right of vertical

    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 18,
                  color: color(0, 0, 0, 0.45))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)

    // Head: long axis VERTICAL (striking end down), slight flare at both
    // ends like Mjolnir's block.
    let head = CGMutablePath()
    head.move(to: CGPoint(x: -62, y: 24))       // bottom-left (striking end)
    head.addLine(to: CGPoint(x: 62, y: 24))
    head.addCurve(to: CGPoint(x: 54, y: 92),
                  control1: CGPoint(x: 58, y: 44), control2: CGPoint(x: 54, y: 66))
    head.addCurve(to: CGPoint(x: 62, y: 160),
                  control1: CGPoint(x: 54, y: 118), control2: CGPoint(x: 58, y: 140))
    head.addLine(to: CGPoint(x: -62, y: 160))
    head.addCurve(to: CGPoint(x: -54, y: 92),
                  control1: CGPoint(x: -58, y: 140), control2: CGPoint(x: -54, y: 118))
    head.addCurve(to: CGPoint(x: -62, y: 24),
                  control1: CGPoint(x: -54, y: 66), control2: CGPoint(x: -58, y: 44))
    head.closeSubpath()

    ctx.saveGState()
    ctx.addPath(head)
    ctx.clip()
    let steel = CGGradient(colorsSpace: space, colors: [
        style.hammerLight, style.hammerMid, style.hammerDark,
    ] as CFArray, locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(steel,
        start: CGPoint(x: -62, y: 0), end: CGPoint(x: 62, y: 0), options: [])
    // Engraved bands near each end + knotwork hint (simple chevrons).
    ctx.setStrokeColor(color(0, 0, 0, 0.28))
    ctx.setLineWidth(3)
    for y in [CGFloat(40), 144] {
        ctx.move(to: CGPoint(x: -58, y: y))
        ctx.addLine(to: CGPoint(x: 58, y: y))
    }
    ctx.strokePath()
    ctx.setStrokeColor(color(1, 1, 1, 0.35))
    ctx.setLineWidth(2)
    for i in 0..<3 {
        let y = 74 + CGFloat(i) * 14
        ctx.move(to: CGPoint(x: -14, y: y))
        ctx.addLine(to: CGPoint(x: 0, y: y + 9))
        ctx.addLine(to: CGPoint(x: 14, y: y))
    }
    ctx.strokePath()
    // Bright striking edge at the bottom.
    ctx.setFillColor(color(1, 1, 1, 0.45))
    ctx.fill(CGRect(x: -62, y: 24, width: 124, height: 7))
    ctx.restoreGState()

    // Handle: short and stout, from the head's top center.
    let handle = CGPath(roundedRect: CGRect(x: -15, y: 150, width: 30, height: 150),
                        cornerWidth: 12, cornerHeight: 12, transform: nil)
    ctx.saveGState()
    ctx.addPath(handle)
    ctx.clip()
    let wood = CGGradient(colorsSpace: space, colors: [
        style.handleLight, style.handleDark,
    ] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(wood,
        start: CGPoint(x: -15, y: 0), end: CGPoint(x: 15, y: 0), options: [])
    // Leather wrap.
    ctx.setStrokeColor(color(0, 0, 0, 0.30))
    ctx.setLineWidth(3)
    for i in 0..<5 {
        let y = 168 + CGFloat(i) * 24
        ctx.move(to: CGPoint(x: -15, y: y))
        ctx.addLine(to: CGPoint(x: 15, y: y + 10))
    }
    ctx.strokePath()
    ctx.restoreGState()
    // Pommel cap + strap loop.
    ctx.setFillColor(style.hammerMid)
    ctx.fillEllipse(in: CGRect(x: -17, y: 292, width: 34, height: 22))
    ctx.setStrokeColor(style.hammerDark)
    ctx.setLineWidth(5)
    ctx.strokeEllipse(in: CGRect(x: -8, y: 306, width: 26, height: 30))

    ctx.endTransparencyLayer()
    ctx.restoreGState()
}

/// Impact: concentric arcs + sparks radiating from the strike point.
func drawImpact(_ ctx: CGContext, style: Style) {
    ctx.saveGState()
    ctx.setStrokeColor(style.accent)
    ctx.setLineCap(.round)
    for (r, w, a) in [(CGFloat(46), CGFloat(5), CGFloat(0.9)),
                      (74, 3.5, 0.55), (102, 2.5, 0.3)] {
        ctx.saveGState()
        ctx.setAlpha(a)
        ctx.setLineWidth(w)
        ctx.addArc(center: IMPACT, radius: r,
                   startAngle: .pi * 0.55, endAngle: .pi * 1.28, clockwise: false)
        ctx.strokePath()
        ctx.restoreGState()
    }
    // Sparks.
    ctx.setLineWidth(4)
    for angle in [CGFloat(2.0), 2.5, 3.0, 3.5] {
        let dir = CGPoint(x: cos(angle), y: sin(angle))
        ctx.move(to: CGPoint(x: IMPACT.x + dir.x * 40, y: IMPACT.y + dir.y * 40))
        ctx.addLine(to: CGPoint(x: IMPACT.x + dir.x * 62, y: IMPACT.y + dir.y * 62))
    }
    ctx.strokePath()
    ctx.restoreGState()
}

// MARK: - Compose

func render(style: Style) -> CGImage {
    let space = CGColorSpaceCreateDeviceRGB()
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    // Apple-guideline squircle: 824pt rounded rect centered, transparent
    // margins.
    let shape = CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824),
                       cornerWidth: 185, cornerHeight: 185, transform: nil)
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 24,
                  color: color(0, 0, 0, 0.30))
    ctx.addPath(shape)
    ctx.setFillColor(style.bgBottom)
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()
    let bg = CGGradient(colorsSpace: space, colors: [
        style.bgTop, style.bgBottom,
    ] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(bg,
        start: CGPoint(x: 512, y: 924), end: CGPoint(x: 512, y: 100), options: [])

    if style.drawsGrid {
        ctx.setStrokeColor(color(1, 1, 1, 0.08))
        ctx.setLineWidth(1.5)
        for v in stride(from: CGFloat(150), through: 900, by: 62) {
            ctx.move(to: CGPoint(x: v, y: 100)); ctx.addLine(to: CGPoint(x: v, y: 924))
            ctx.move(to: CGPoint(x: 100, y: v)); ctx.addLine(to: CGPoint(x: 924, y: v))
        }
        ctx.strokePath()
    }

    drawAnvil(ctx, style: style)
    drawImpact(ctx, style: style)
    drawMjolnir(ctx, style: style)

    // Subtle inner top-light on the squircle.
    ctx.addPath(shape)
    ctx.setStrokeColor(color(1, 1, 1, 0.18))
    ctx.setLineWidth(2.5)
    ctx.strokePath()
    ctx.restoreGState()

    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, to url: URL) {
    let dest = CGImageDestinationCreateWithURL(url as CFURL,
                                               UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, image, nil)
    CGImageDestinationFinalize(dest)
}

let outDir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "concepts"
let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
try? FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)
for style in styles {
    writePNG(render(style: style), to: outURL.appendingPathComponent("\(style.name).png"))
    print("Rendered \(style.name).png")
}
