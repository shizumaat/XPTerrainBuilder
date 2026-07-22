// Renders the XPTerrainBuilder app icon in the spirit of the classic Xcode
// icon: a tilted blueprint sheet with a claw hammer laid across it. The
// blueprint carries a wireframe mountain-topography illustration and a
// title block reading "PROJECT: EARTH" / "ARCHITECT: NOVEMBER LIMA".
// Usage: swift scripts/make_icon.swift <output-dir>
import Foundation
import CoreGraphics
import CoreText
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

// MARK: - Palette

// Blueprint blues, lifted from the classic diazo print look.
let paperLight = color(0.36, 0.62, 0.92)
let paperMid = color(0.27, 0.53, 0.86)
let paperDark = color(0.18, 0.42, 0.76)
/// Sketch lines: near-white with a touch of translucency, like pencil on blueprint.
let inkWhite = color(1, 1, 1, 0.92)
let inkFaint = color(1, 1, 1, 0.55)

// Hammer materials: polished steel head, varnished hickory handle.
let steelLight = color(0.90, 0.92, 0.95)
let steelMid = color(0.64, 0.67, 0.72)
let steelDark = color(0.34, 0.37, 0.42)
let woodHi = color(0.86, 0.65, 0.40)
let woodMid = color(0.72, 0.49, 0.26)
let woodDark = color(0.51, 0.32, 0.15)
let grainBrown = color(0.36, 0.21, 0.09)

// MARK: - Text

/// Draws a single line of text with CoreText. `anchor` 0 = left edge at `p`,
/// 0.5 = centered, 1 = right edge at `p`.
func text(_ ctx: CGContext, _ s: String, size: CGFloat, at p: CGPoint,
          color: CGColor = inkWhite, fontName: String = "MarkerFelt-Wide",
          anchor: CGFloat = 0, angle: CGFloat = 0) {
    let font = CTFontCreateWithName(fontName as CFString, size, nil)
    let attrs = [
        kCTFontAttributeName: font,
        kCTForegroundColorAttributeName: color,
    ] as CFDictionary
    guard let astr = CFAttributedStringCreate(kCFAllocatorDefault, s as CFString, attrs) else { return }
    let line = CTLineCreateWithAttributedString(astr)
    let width = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
    ctx.saveGState()
    ctx.translateBy(x: p.x, y: p.y)
    ctx.rotate(by: angle)
    ctx.textPosition = CGPoint(x: -width * anchor, y: 0)
    CTLineDraw(line, ctx)
    ctx.restoreGState()
}

// MARK: - Blueprint sheet

let sheetW: CGFloat = 810
let sheetH: CGFloat = 660

/// Two-peak gaussian heightfield over the unit square, used for the terrain mesh.
func terrainHeight(_ x: CGFloat, _ y: CGFloat) -> CGFloat {
    func peak(_ cx: CGFloat, _ cy: CGFloat, _ amp: CGFloat, _ sx: CGFloat, _ sy: CGFloat) -> CGFloat {
        let dx = (x - cx) / sx, dy = (y - cy) / sy
        return amp * exp(-(dx * dx + dy * dy))
    }
    return peak(0.38, 0.60, 0.88, 0.26, 0.30)
         + peak(0.74, 0.42, 0.48, 0.20, 0.24)
         + peak(0.14, 0.28, 0.22, 0.18, 0.20)
}

/// Wireframe terrain mesh in sheet-local coordinates: rows recede upward with
/// a slight shear and shrink for depth, verticals connect them into a mesh.
func drawTerrainMesh(_ ctx: CGContext, in rect: CGRect) {
    let cols = 16, rows = 11
    let heightScale: CGFloat = rect.height * 0.48
    let depth = rect.height * 0.42

    func point(_ i: Int, _ j: Int) -> CGPoint {
        let u = CGFloat(i) / CGFloat(cols)
        let v = CGFloat(j) / CGFloat(rows)
        let scale = 1.0 - 0.22 * v                       // perspective shrink
        let x = rect.midX + (u - 0.5) * rect.width * scale + v * rect.width * 0.06
        let y = rect.minY + v * depth + terrainHeight(u, v) * heightScale * (1.0 - 0.25 * v)
        return CGPoint(x: x, y: y)
    }

    ctx.saveGState()
    ctx.setLineJoin(.round)
    ctx.setLineCap(.round)

    // Depth lines first (fainter), then the row polylines over them.
    ctx.setStrokeColor(inkFaint)
    ctx.setLineWidth(2.4)
    for i in 0...cols {
        ctx.move(to: point(i, 0))
        for j in 1...rows { ctx.addLine(to: point(i, j)) }
        ctx.strokePath()
    }
    ctx.setStrokeColor(inkWhite)
    ctx.setLineWidth(3.4)
    for j in 0...rows {
        ctx.move(to: point(0, j))
        for i in 1...cols { ctx.addLine(to: point(i, j)) }
        ctx.strokePath()
    }

    // Summit marker: small triangle on the main peak, as on topo charts.
    let summit = point(6, 4)
    ctx.setLineWidth(3.5)
    ctx.move(to: CGPoint(x: summit.x, y: summit.y + 26))
    ctx.addLine(to: CGPoint(x: summit.x - 15, y: summit.y + 2))
    ctx.addLine(to: CGPoint(x: summit.x + 15, y: summit.y + 2))
    ctx.closePath()
    ctx.strokePath()
    ctx.restoreGState()
}

/// Leader line with a little elbow, from a label toward a feature.
func leader(_ ctx: CGContext, from: CGPoint, elbow: CGPoint, to: CGPoint) {
    ctx.saveGState()
    ctx.setStrokeColor(inkWhite)
    ctx.setLineWidth(2.6)
    ctx.setLineCap(.round)
    ctx.move(to: from)
    ctx.addLine(to: elbow)
    ctx.addLine(to: to)
    ctx.strokePath()
    ctx.fillEllipse(in: CGRect(x: to.x - 4, y: to.y - 4, width: 8, height: 8))
    ctx.restoreGState()
}

/// The blueprint, drawn in local coordinates with origin at its bottom-left.
func drawSheet(_ ctx: CGContext) {
    // Paper: diagonal blueprint-blue gradient.
    let space = CGColorSpaceCreateDeviceRGB()
    let paper = CGGradient(colorsSpace: space,
                           colors: [paperLight, paperMid, paperDark] as CFArray,
                           locations: [0, 0.55, 1])!
    ctx.saveGState()
    ctx.clip(to: CGRect(x: 0, y: 0, width: sheetW, height: sheetH))
    ctx.drawLinearGradient(paper,
        start: CGPoint(x: 0, y: sheetH),
        end: CGPoint(x: sheetW, y: 0), options: [])
    ctx.restoreGState()

    // Drafting frame: heavy outer border, fine inner border.
    let outer = CGRect(x: 26, y: 26, width: sheetW - 52, height: sheetH - 52)
    ctx.setStrokeColor(inkWhite)
    ctx.setLineWidth(5)
    ctx.stroke(outer)
    ctx.setLineWidth(2)
    ctx.stroke(outer.insetBy(dx: 10, dy: 10))

    // Title block: band across the bottom of the frame, one divider,
    // "PROJECT: EARTH" left and "ARCHITECT: NOVEMBER LIMA" right.
    let bandH: CGFloat = 62
    let band = CGRect(x: outer.minX, y: outer.minY, width: outer.width, height: bandH)
    ctx.setLineWidth(4)
    ctx.stroke(band)
    let divider = outer.minX + outer.width * 0.42
    ctx.move(to: CGPoint(x: divider, y: band.minY))
    ctx.addLine(to: CGPoint(x: divider, y: band.maxY))
    ctx.strokePath()
    let baseline = band.minY + 21
    text(ctx, "PROJECT: EARTH", size: 24,
         at: CGPoint(x: outer.minX + 20, y: baseline))
    text(ctx, "ARCHITECT: NOVEMBER LIMA", size: 26,
         at: CGPoint(x: divider + 24, y: baseline))

    // The illustration: wireframe mountain topography above the title block.
    let drawing = CGRect(x: outer.minX + 60, y: band.maxY + 70,
                         width: outer.width - 120, height: outer.maxY - band.maxY - 180)
    drawTerrainMesh(ctx, in: drawing)

    // Hand annotations with leaders, like the original's callouts. Both stay
    // on the left half — the hammer lies over the sheet's right side.
    text(ctx, "SUMMIT 4,392 M", size: 30,
         at: CGPoint(x: outer.minX + 148, y: outer.maxY - 74))
    leader(ctx,
           from: CGPoint(x: outer.minX + 262, y: outer.maxY - 84),
           elbow: CGPoint(x: outer.minX + 250, y: outer.maxY - 130),
           to: CGPoint(x: drawing.minX + drawing.width * 0.41,
                       y: drawing.minY + drawing.height * 0.62))

    text(ctx, "TERRAIN MESH", size: 28,
         at: CGPoint(x: outer.minX + 24, y: band.maxY + 26))
    leader(ctx,
           from: CGPoint(x: outer.minX + 130, y: band.maxY + 56),
           elbow: CGPoint(x: outer.minX + 160, y: band.maxY + 90),
           to: CGPoint(x: drawing.minX + drawing.width * 0.20,
                       y: drawing.minY + drawing.height * 0.30))

    // North arrow, upper left corner of the drawing area.
    let north = CGPoint(x: outer.minX + 84, y: outer.maxY - 84)
    ctx.setStrokeColor(inkWhite)
    ctx.setLineWidth(3)
    ctx.strokeEllipse(in: CGRect(x: north.x - 30, y: north.y - 30, width: 60, height: 60))
    ctx.move(to: CGPoint(x: north.x, y: north.y - 22))
    ctx.addLine(to: CGPoint(x: north.x, y: north.y + 22))
    ctx.addLine(to: CGPoint(x: north.x - 9, y: north.y + 8))
    ctx.strokePath()
    text(ctx, "N", size: 24, at: CGPoint(x: north.x + 12, y: north.y + 10))
}

// MARK: - Hammer

/// Claw hammer in local coordinates: origin at the head's center, head axis
/// along x (claw tapering off to -x, striking face at +x), wooden handle
/// running down -y. Drawn side-on like the classic Xcode hammer: the claw
/// reads as a wedge with a gentle downward sweep, the face as a bright bell.
func drawHammerBody(_ ctx: CGContext) {
    let space = CGColorSpaceCreateDeviceRGB()

    // ---- Wooden handle (drawn first; the head overlaps its top) ----------
    // Slightly tapered: narrower at the head, flaring toward a rounded butt.
    let handle = CGMutablePath()
    handle.move(to: CGPoint(x: -30, y: -20))
    handle.addCurve(to: CGPoint(x: -40, y: -690),
                    control1: CGPoint(x: -34, y: -280), control2: CGPoint(x: -32, y: -520))
    handle.addCurve(to: CGPoint(x: 0, y: -738),
                    control1: CGPoint(x: -41, y: -720), control2: CGPoint(x: -24, y: -738))
    handle.addCurve(to: CGPoint(x: 40, y: -690),
                    control1: CGPoint(x: 24, y: -738), control2: CGPoint(x: 41, y: -720))
    handle.addCurve(to: CGPoint(x: 30, y: -20),
                    control1: CGPoint(x: 32, y: -520), control2: CGPoint(x: 34, y: -280))
    handle.closeSubpath()

    ctx.saveGState()
    ctx.addPath(handle)
    ctx.clip()
    let wood = CGGradient(colorsSpace: space,
                          colors: [woodHi, woodMid, woodDark] as CFArray,
                          locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(wood,
        start: CGPoint(x: -40, y: 0), end: CGPoint(x: 40, y: 0), options: [])

    // Grain: long wavering streaks down the handle, darker and lighter.
    let grains: [(x: CGFloat, wobble: CGFloat, width: CGFloat, alpha: CGFloat)] = [
        (-20, 7, 3.0, 0.30), (-11, -5, 2.2, 0.22), (-3, 9, 3.6, 0.28),
        (5, -7, 2.4, 0.20), (13, 5, 3.0, 0.26), (21, -4, 2.0, 0.18),
        (-16, -9, 1.6, 0.14), (9, 11, 1.8, 0.15),
    ]
    ctx.setLineCap(.round)
    for grain in grains {
        ctx.setStrokeColor(color(0.36, 0.21, 0.09, grain.alpha))
        ctx.setLineWidth(grain.width)
        ctx.move(to: CGPoint(x: grain.x, y: -24))
        ctx.addCurve(to: CGPoint(x: grain.x * 1.2, y: -720),
                     control1: CGPoint(x: grain.x + grain.wobble, y: -260),
                     control2: CGPoint(x: grain.x - grain.wobble, y: -500))
        ctx.strokePath()
    }
    // Varnish sheen along the lit side.
    let sheen = CGGradient(colorsSpace: space, colors: [
        color(1, 1, 1, 0.30), color(1, 1, 1, 0.05), color(1, 1, 1, 0),
    ] as CFArray, locations: [0, 0.5, 1])!
    ctx.drawLinearGradient(sheen,
        start: CGPoint(x: -30, y: 0), end: CGPoint(x: -2, y: 0), options: [])
    // End-grain shading at the butt.
    ctx.setFillColor(color(0.30, 0.17, 0.07, 0.35))
    ctx.fill(CGRect(x: -42, y: -738, width: 84, height: 26))
    ctx.restoreGState()

    // Soft occlusion where the handle disappears into the head.
    ctx.saveGState()
    ctx.addPath(handle)
    ctx.clip()
    ctx.setFillColor(color(0, 0, 0, 0.30))
    ctx.fillEllipse(in: CGRect(x: -36, y: -66, width: 72, height: 40))
    ctx.restoreGState()

    // ---- Steel head (classic-Xcode arrangement) --------------------------
    // Claw at -x (screen left, pointing up-left after the scene rotation),
    // block, tapered neck, flared bell and rounded striking face at +x
    // (screen right — it pokes past the blueprint's corner). Local frame:
    // handle down -y.
    let head = CGMutablePath()
    head.move(to: CGPoint(x: -232, y: 2))             // claw tip, upper corner
    head.addCurve(to: CGPoint(x: -78, y: 50),         // claw top sweeping in
                  control1: CGPoint(x: -186, y: 24), control2: CGPoint(x: -128, y: 42))
    head.addCurve(to: CGPoint(x: 78, y: 50),          // block crown
                  control1: CGPoint(x: -30, y: 56), control2: CGPoint(x: 30, y: 56))
    head.addCurve(to: CGPoint(x: 128, y: 38),         // neck taper (top)
                  control1: CGPoint(x: 100, y: 47), control2: CGPoint(x: 116, y: 42))
    head.addCurve(to: CGPoint(x: 188, y: 44),         // bell flare (top)
                  control1: CGPoint(x: 152, y: 36), control2: CGPoint(x: 174, y: 40))
    head.addCurve(to: CGPoint(x: 212, y: 0),          // rounded face cap
                  control1: CGPoint(x: 204, y: 40), control2: CGPoint(x: 212, y: 22))
    head.addCurve(to: CGPoint(x: 188, y: -44),
                  control1: CGPoint(x: 212, y: -22), control2: CGPoint(x: 204, y: -40))
    head.addCurve(to: CGPoint(x: 128, y: -38),        // bell back to neck
                  control1: CGPoint(x: 174, y: -40), control2: CGPoint(x: 152, y: -36))
    head.addCurve(to: CGPoint(x: 78, y: -50),         // neck to block
                  control1: CGPoint(x: 116, y: -42), control2: CGPoint(x: 100, y: -47))
    head.addLine(to: CGPoint(x: -80, y: -50))         // block underside
    head.addCurve(to: CGPoint(x: -196, y: -30),       // claw underside, gentle S
                  control1: CGPoint(x: -130, y: -50), control2: CGPoint(x: -168, y: -42))
    head.addCurve(to: CGPoint(x: -232, y: -12),       // out to the tip
                  control1: CGPoint(x: -214, y: -24), control2: CGPoint(x: -228, y: -18))
    head.closeSubpath()
    // Punched V-notch between the claw's two prongs (even-odd fill).
    head.move(to: CGPoint(x: -228, y: -4))
    head.addLine(to: CGPoint(x: -148, y: 8))
    head.addLine(to: CGPoint(x: -150, y: -2))
    head.closeSubpath()

    ctx.saveGState()
    ctx.addPath(head)
    ctx.clip(using: .evenOdd)
    let headGrad = CGGradient(colorsSpace: space, colors: [
        steelLight, steelMid, steelDark,
    ] as CFArray, locations: [0, 0.55, 1])!
    ctx.drawLinearGradient(headGrad,
        start: CGPoint(x: 0, y: 56), end: CGPoint(x: 0, y: -52), options: [])

    // Long soft specular along the crown of block and claw.
    let spec = CGGradient(colorsSpace: space, colors: [
        color(1, 1, 1, 0.8), color(1, 1, 1, 0),
    ] as CFArray, locations: [0, 1])!
    ctx.saveGState()
    let specPath = CGMutablePath()
    specPath.addEllipse(in: CGRect(x: -170, y: 8, width: 300, height: 42),
                        transform: CGAffineTransform(rotationAngle: -0.06))
    ctx.addPath(specPath)
    ctx.clip()
    ctx.drawLinearGradient(spec,
        start: CGPoint(x: 0, y: 52), end: CGPoint(x: 0, y: 6), options: [])
    ctx.restoreGState()

    // Neck ring: a bright band where the bell meets the neck.
    let ring = CGGradient(colorsSpace: space, colors: [
        color(1, 1, 1, 0), color(1, 1, 1, 0.45), color(1, 1, 1, 0),
    ] as CFArray, locations: [0, 0.5, 1])!
    ctx.drawLinearGradient(ring,
        start: CGPoint(x: 116, y: 0), end: CGPoint(x: 140, y: 0), options: [])

    // Bright striking face: light builds toward the rounded cap.
    let faceGrad = CGGradient(colorsSpace: space, colors: [
        color(1, 1, 1, 0), color(1, 1, 1, 0.55),
    ] as CFArray, locations: [0, 1])!
    ctx.drawLinearGradient(faceGrad,
        start: CGPoint(x: 178, y: 0), end: CGPoint(x: 212, y: 0), options: [])

    // Eye ridge: faint darker band where the handle passes through.
    let eye = CGGradient(colorsSpace: space, colors: [
        color(0, 0, 0, 0), color(0, 0, 0, 0.16), color(0, 0, 0, 0),
    ] as CFArray, locations: [0, 0.5, 1])!
    ctx.drawLinearGradient(eye,
        start: CGPoint(x: -32, y: 0), end: CGPoint(x: 36, y: 0), options: [])
    ctx.restoreGState()

    // Rim light along the top silhouette, claw tip to bell.
    ctx.saveGState()
    ctx.setStrokeColor(color(1, 1, 1, 0.45))
    ctx.setLineWidth(3)
    ctx.setLineCap(.round)
    ctx.move(to: CGPoint(x: -228, y: 4))
    ctx.addCurve(to: CGPoint(x: -78, y: 52),
                 control1: CGPoint(x: -184, y: 26), control2: CGPoint(x: -126, y: 44))
    ctx.addCurve(to: CGPoint(x: 76, y: 52),
                 control1: CGPoint(x: -30, y: 58), control2: CGPoint(x: 30, y: 58))
    ctx.strokePath()
    ctx.restoreGState()
}

// MARK: - Compose

func drawScene(_ ctx: CGContext) {
    // Blueprint sheet, tilted slightly counter-clockwise, with a soft shadow.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -16), blur: 34,
                  color: color(0, 0, 0, 0.42))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)
    ctx.saveGState()
    ctx.translateBy(x: 470, y: 545)
    ctx.rotate(by: 0.10)
    ctx.translateBy(x: -sheetW / 2, y: -sheetH / 2)
    drawSheet(ctx)
    ctx.restoreGState()
    ctx.endTransparencyLayer()
    ctx.restoreGState()

    // Hammer across the sheet: head upper middle, handle to the lower right.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -18), blur: 30,
                  color: color(0, 0, 0, 0.48))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)
    ctx.saveGState()
    // Sample geometry: head at the sheet's top-right corner (face poking
    // past the edge), handle crossing down-left to end left of center.
    ctx.translateBy(x: 706, y: 825)
    ctx.rotate(by: -0.52)
    drawHammerBody(ctx)
    ctx.restoreGState()
    ctx.endTransparencyLayer()
    ctx.restoreGState()
}

func renderMaster() -> CGImage {
    let space = CGColorSpaceCreateDeviceRGB()
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    drawScene(ctx)
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
