// Icon concept: Mjolnir in the movie-replica 3/4 pose — head resting at
// the lower left showing its top face, front cheek and round-bossed
// striking face, Norse knotwork on the chamfers, leather handle with
// spiral steel bands rising to the upper right, strap loop at the pommel.
// Squircle canvas per Apple guidelines. No display stand.
// Usage: swift scripts/icon_mjolnir.swift <output-dir>
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let SIZE: CGFloat = 1024
let space = CGColorSpaceCreateDeviceRGB()

func color(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: r, green: g, blue: b, alpha: a)
}

func gradient(_ colors: [CGColor], _ locations: [CGFloat]) -> CGGradient {
    CGGradient(colorsSpace: space, colors: colors as CFArray, locations: locations)!
}

func P(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }

func quad(_ a: CGPoint, _ b: CGPoint, _ c: CGPoint, _ d: CGPoint) -> CGPath {
    let p = CGMutablePath()
    p.move(to: a); p.addLine(to: b); p.addLine(to: c); p.addLine(to: d)
    p.closeSubpath()
    return p
}

func mix(_ a: CGPoint, _ b: CGPoint, _ t: CGFloat) -> CGPoint {
    P(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
}

// MARK: - Head geometry (oblique box, photo-matched)

// Screen-space basis eyeballed from the replica photo:
//   A: long axis (to the back-right, slightly up)
//   U: handle/up axis (up-right)
//   D: depth (into scene, up-left)
let A = CGVector(dx: 340, dy: 105)
let U = CGVector(dx: 140, dy: 215)
let D = CGVector(dx: -148, dy: 66)

let F0 = P(286, 168)                       // front-bottom-left corner
let FA = P(F0.x + A.dx, F0.y + A.dy)       // front-bottom-right
let FU = P(F0.x + U.dx, F0.y + U.dy)       // front-top-left
let FAU = P(FA.x + U.dx, FA.y + U.dy)      // front-top-right
let TU = P(FU.x + D.dx, FU.y + D.dy)       // back-top-left
let TAU = P(FAU.x + D.dx, FAU.y + D.dy)    // back-top-right
let B0 = P(F0.x + D.dx, F0.y + D.dy)       // back-bottom-left

/// Center of the top face — where the handle enters.
let handleBase = P(FU.x + A.dx / 2 + D.dx / 2, FU.y + A.dy / 2 + D.dy / 2)
let handleDir = CGVector(dx: 0.545, dy: 0.838)   // normalized U
let handleLen: CGFloat = 425
let pommel = P(handleBase.x + handleDir.dx * handleLen,
               handleBase.y + handleDir.dy * handleLen)

// MARK: - Knotwork

/// Interlaced Norse-knot suggestion: repeating figure-eight squiggles along
/// a strip between two edge lines. Reads as engraving at icon sizes.
func drawKnotwork(_ ctx: CGContext, from a0: CGPoint, to a1: CGPoint,
                  across: CGVector, count: Int) {
    let strip = quad(a0, a1,
                     P(a1.x + across.dx, a1.y + across.dy),
                     P(a0.x + across.dx, a0.y + across.dy))
    ctx.saveGState()
    ctx.addPath(strip)
    ctx.clip()
    // Recessed dark base, shaded across the strip for an embossed groove.
    ctx.addPath(strip)
    ctx.setFillColor(color(0.13, 0.14, 0.17))
    ctx.fillPath()
    ctx.drawLinearGradient(gradient([
        color(0, 0, 0, 0.45), color(0, 0, 0, 0), color(1, 1, 1, 0.14),
    ], [0, 0.55, 1]),
        start: a0, end: P(a0.x + across.dx, a0.y + across.dy), options: [])
    ctx.setStrokeColor(color(0.55, 0.58, 0.64, 0.85))
    ctx.setLineWidth(2.6)
    ctx.setLineCap(.round)
    let mid = CGVector(dx: across.dx / 2, dy: across.dy / 2)
    for i in 0..<count {
        let t0 = CGFloat(i) / CGFloat(count)
        let t1 = CGFloat(i) + 1 == CGFloat(count) ? 1 : (CGFloat(i) + 1) / CGFloat(count)
        let s = mix(a0, a1, t0), e = mix(a0, a1, t1)
        let sm = P(s.x + mid.dx, s.y + mid.dy), em = P(e.x + mid.dx, e.y + mid.dy)
        // Two interlocking arcs per cell.
        ctx.move(to: P(s.x + across.dx * 0.15, s.y + across.dy * 0.15))
        ctx.addQuadCurve(to: P(em.x, em.y),
                         control: P(sm.x + (em.x - sm.x) * 0.3 + across.dx * 0.8,
                                    sm.y + (em.y - sm.y) * 0.3 + across.dy * 0.8))
        ctx.move(to: P(s.x + across.dx * 0.85, s.y + across.dy * 0.85))
        ctx.addQuadCurve(to: P(e.x + across.dx * 0.4, e.y + across.dy * 0.4),
                         control: P(sm.x + (em.x - sm.x) * 0.7 - across.dx * 0.4,
                                    sm.y + (em.y - sm.y) * 0.7 - across.dy * 0.4))
    }
    ctx.strokePath()
    ctx.restoreGState()
}

// MARK: - Head

func drawHead(_ ctx: CGContext) {
    // One soft shadow for the whole head mass.
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -22), blur: 46,
                  color: color(0, 0, 0, 0.55))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)

    // --- Front cheek: cast steel with a broad glossy sheen -------------
    let cheek = quad(F0, FA, FAU, FU)
    ctx.saveGState()
    ctx.addPath(cheek)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.68, 0.70, 0.74), color(0.54, 0.55, 0.59),
        color(0.42, 0.43, 0.47), color(0.34, 0.35, 0.39),
    ], [0, 0.42, 0.8, 1]),
        start: FU, end: P(FA.x, FA.y - 30), options: [])
    // Broad soft specular near the lit corner.
    ctx.drawRadialGradient(gradient([
        color(1, 1, 1, 0.30), color(1, 1, 1, 0.08), color(1, 1, 1, 0),
    ], [0, 0.55, 1]),
        startCenter: P(FU.x + 120, FU.y - 40), startRadius: 0,
        endCenter: P(FU.x + 120, FU.y - 40), endRadius: 260, options: [])
    // Gentle occlusion along the bottom edge only.
    ctx.drawLinearGradient(gradient([
        color(0, 0, 0, 0.18), color(0, 0, 0, 0),
    ], [0, 1]),
        start: P(F0.x + A.dx / 2, F0.y + A.dy / 2),
        end: P(F0.x + A.dx / 2 + U.dx * 0.22, F0.y + A.dy / 2 + U.dy * 0.22), options: [])
    // A whisper of AO under the top chamfer.
    ctx.drawLinearGradient(gradient([
        color(0, 0, 0, 0.13), color(0, 0, 0, 0),
    ], [0, 1]),
        start: P(FU.x + A.dx / 2, FU.y + A.dy / 2),
        end: P(FU.x + A.dx / 2 - U.dx * 0.18, FU.y + A.dy / 2 - U.dy * 0.18), options: [])
    // Cast-metal mottling.
    for (x, y, r, a) in [(430, 300, 90, 0.07), (560, 380, 70, 0.06),
                         (360, 240, 60, 0.06), (620, 300, 60, 0.05),
                         (500, 220, 80, 0.055)] as [(CGFloat, CGFloat, CGFloat, CGFloat)] {
        ctx.drawRadialGradient(gradient([
            color(1, 1, 1, a), color(1, 1, 1, 0),
        ], [0, 1]),
            startCenter: P(x, y), startRadius: 0,
            endCenter: P(x, y), endRadius: r, options: [])
    }
    ctx.restoreGState()

    // --- Top face: glossy, sky-lit, with a sweeping sheen band ---------
    let top = quad(FU, FAU, TAU, TU)
    ctx.saveGState()
    ctx.addPath(top)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.97, 0.98, 1.0), color(0.84, 0.87, 0.92), color(0.72, 0.75, 0.81),
    ], [0, 0.6, 1]),
        start: TU, end: P(FAU.x, FAU.y - 20), options: [])
    // Diagonal sheen sweeping across the face.
    ctx.drawLinearGradient(gradient([
        color(1, 1, 1, 0), color(1, 1, 1, 0.55), color(1, 1, 1, 0),
    ], [0.30, 0.48, 0.66]),
        start: P(FU.x, FU.y), end: P(TAU.x, TAU.y), options: [])
    ctx.restoreGState()

    // --- Far end cap: a foreshortened sliver that closes the solid -----
    let endShift = CGVector(dx: 22, dy: 4)
    let endCap = quad(FA, P(FA.x + endShift.dx, FA.y + endShift.dy),
                      P(FAU.x + endShift.dx, FAU.y + endShift.dy), FAU)
    ctx.saveGState()
    ctx.addPath(endCap)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.30, 0.31, 0.35), color(0.20, 0.21, 0.24),
    ], [0, 1]),
        start: FAU, end: FA, options: [])
    ctx.restoreGState()

    // --- Striking face (left): shadowed, warm floor bounce, round boss -
    let strike = quad(F0, FU, TU, B0)
    ctx.saveGState()
    ctx.addPath(strike)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.55, 0.56, 0.60), color(0.38, 0.39, 0.43), color(0.28, 0.28, 0.32),
    ], [0, 0.6, 1]),
        start: TU, end: F0, options: [])
    // Warm bounce light from below.
    ctx.drawLinearGradient(gradient([
        color(0.55, 0.42, 0.30, 0.22), color(0.55, 0.42, 0.30, 0),
    ], [0, 1]),
        start: P(B0.x + 40, B0.y - 20), end: P(TU.x, TU.y), options: [])
    // Round boss: projected circle on the face plane.
    let faceCenter = P(F0.x + U.dx / 2 + D.dx / 2, F0.y + U.dy / 2 + D.dy / 2)
    let e1 = CGVector(dx: U.dx / 256, dy: U.dy / 256)   // unit up in face
    let e2 = CGVector(dx: D.dx / 162, dy: D.dy / 162)   // unit depth in face
    let r1: CGFloat = 88, r2: CGFloat = 88
    var bossTransform = CGAffineTransform(
        a: e1.dx * r1, b: e1.dy * r1,
        c: e2.dx * r2, d: e2.dy * r2,
        tx: faceCenter.x, ty: faceCenter.y)
    let boss = CGPath(ellipseIn: CGRect(x: -1, y: -1, width: 2, height: 2),
                      transform: &bossTransform)
    ctx.saveGState()
    ctx.addPath(boss)
    ctx.clip()
    // Dished boss: convex shading with a hot spot toward the light.
    ctx.drawRadialGradient(gradient([
        color(0.80, 0.82, 0.86), color(0.56, 0.57, 0.61), color(0.36, 0.37, 0.41),
    ], [0, 0.55, 1]),
        startCenter: P(faceCenter.x + 22, faceCenter.y + 56), startRadius: 0,
        endCenter: P(faceCenter.x, faceCenter.y), endRadius: 110, options: [])
    // Inner AO along the lower rim of the dish.
    ctx.drawLinearGradient(gradient([
        color(0, 0, 0, 0.28), color(0, 0, 0, 0),
    ], [0, 1]),
        start: P(faceCenter.x - 46, faceCenter.y - 78),
        end: P(faceCenter.x, faceCenter.y), options: [])
    ctx.restoreGState()
    // Rim: bright on the lit arc, dark on the shadowed arc.
    ctx.addPath(boss)
    ctx.setStrokeColor(color(0.88, 0.90, 0.94, 0.95))
    ctx.setLineWidth(4)
    ctx.strokePath()
    ctx.saveGState()
    ctx.addPath(boss)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.10, 0.11, 0.13, 0.5), color(0.10, 0.11, 0.13, 0),
    ], [0, 0.35]),
        start: P(faceCenter.x - 70, faceCenter.y - 90),
        end: P(faceCenter.x, faceCenter.y), options: [])
    ctx.restoreGState()
    // Inner engraved ring.
    var ringTransform = CGAffineTransform(
        a: e1.dx * r1 * 0.72, b: e1.dy * r1 * 0.72,
        c: e2.dx * r2 * 0.72, d: e2.dy * r2 * 0.72,
        tx: faceCenter.x, ty: faceCenter.y)
    let ring = CGPath(ellipseIn: CGRect(x: -1, y: -1, width: 2, height: 2),
                      transform: &ringTransform)
    ctx.addPath(ring)
    ctx.setStrokeColor(color(0.24, 0.25, 0.28, 0.8))
    ctx.setLineWidth(2.5)
    ctx.strokePath()
    ctx.restoreGState()

    // --- Knotwork chamfer bands: NARROW strips hugging the edges -------
    drawKnotwork(ctx, from: FU, to: FAU,
                 across: CGVector(dx: -D.dx * 0.13, dy: -D.dy * 0.13), count: 8)
    drawKnotwork(ctx, from: F0, to: FU,
                 across: CGVector(dx: A.dx * 0.055, dy: A.dy * 0.055), count: 4)
    drawKnotwork(ctx, from: F0, to: FA,
                 across: CGVector(dx: U.dx * 0.085, dy: U.dy * 0.085), count: 8)

    // Edge highlights and closing silhouette lines.
    ctx.setStrokeColor(color(1, 1, 1, 0.55))
    ctx.setLineWidth(2.5)
    ctx.setLineCap(.round)
    ctx.move(to: FU); ctx.addLine(to: FAU)
    ctx.move(to: FU); ctx.addLine(to: TU)
    ctx.strokePath()
    ctx.setStrokeColor(color(0.12, 0.13, 0.15, 0.7))
    ctx.setLineWidth(2)
    ctx.move(to: F0); ctx.addLine(to: FA)
    ctx.move(to: F0); ctx.addLine(to: FU)
    ctx.move(to: FA); ctx.addLine(to: FAU)      // right end silhouette
    ctx.strokePath()
    // Far edges of the top face, softly closed.
    ctx.setStrokeColor(color(0.45, 0.47, 0.51, 0.8))
    ctx.setLineWidth(2)
    ctx.move(to: TU); ctx.addLine(to: TAU)
    ctx.move(to: TAU); ctx.addLine(to: FAU)
    ctx.strokePath()

    ctx.endTransparencyLayer()
    ctx.restoreGState()
}

// MARK: - Handle

func drawHandle(_ ctx: CGContext) {
    let dir = handleDir
    let normal = CGVector(dx: -dir.dy, dy: dir.dx)   // left of travel
    let half: CGFloat = 30

    func along(_ t: CGFloat, _ n: CGFloat) -> CGPoint {
        P(handleBase.x + dir.dx * t + normal.dx * n,
          handleBase.y + dir.dy * t + normal.dy * n)
    }

    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -12), blur: 22,
                  color: color(0, 0, 0, 0.4))
    ctx.beginTransparencyLayer(auxiliaryInfo: nil)

    // Leather shaft.
    let shaft = quad(along(-30, -half), along(handleLen - 28, -half),
                     along(handleLen - 28, half), along(-30, half))
    ctx.saveGState()
    ctx.addPath(shaft)
    ctx.clip()
    // Cylindrical shading across the width, with a glossy sheen stripe.
    ctx.drawLinearGradient(gradient([
        color(0.26, 0.16, 0.09), color(0.50, 0.33, 0.20),
        color(0.40, 0.26, 0.15), color(0.15, 0.09, 0.05),
    ], [0, 0.3, 0.65, 1]),
        start: along(200, -half), end: along(200, half), options: [])
    ctx.drawLinearGradient(gradient([
        color(1, 1, 1, 0), color(1, 0.95, 0.85, 0.30), color(1, 1, 1, 0),
    ], [0.18, 0.32, 0.5]),
        start: along(200, -half), end: along(200, half), options: [])
    // Sweat-darkened grip zone (mid-shaft).
    ctx.drawLinearGradient(gradient([
        color(0, 0, 0, 0), color(0.05, 0.02, 0.0, 0.35), color(0, 0, 0, 0),
    ], [0, 0.5, 1]),
        start: along(90, 0), end: along(310, 0), options: [])
    // Spiral steel bands: thin bright strips winding up the shaft.
    for i in 0..<9 {
        let t = 26 + CGFloat(i) * 42
        let band = CGMutablePath()
        band.move(to: along(t, -half))
        band.addQuadCurve(to: along(t + 26, half),
                          control: along(t + 20, -half * 0.2))
        band.addLine(to: along(t + 36, half))
        band.addQuadCurve(to: along(t + 10, -half),
                          control: along(t + 26, -half * 0.2))
        band.closeSubpath()
        ctx.addPath(band)
        ctx.setFillColor(color(0.78, 0.81, 0.86, 0.9))
        ctx.fillPath()
        // Band shading follows the cylinder.
        ctx.saveGState()
        ctx.addPath(band)
        ctx.clip()
        ctx.drawLinearGradient(gradient([
            color(1, 1, 1, 0.35), color(0, 0, 0, 0.0), color(0, 0, 0, 0.4),
        ], [0, 0.45, 1]),
            start: along(t, -half), end: along(t, half), options: [])
        ctx.restoreGState()
    }
    // Leather seam shadows between bands.
    ctx.setStrokeColor(color(0, 0, 0, 0.18))
    ctx.setLineWidth(2)
    for i in 0..<9 {
        let t = 47 + CGFloat(i) * 42
        ctx.move(to: along(t, -half))
        ctx.addLine(to: along(t + 26, half))
    }
    ctx.strokePath()
    ctx.restoreGState()

    // Pommel: knotwork-engraved steel cap, slightly flared.
    let cap = quad(along(handleLen - 30, -half - 7), along(handleLen + 26, -half - 9),
                   along(handleLen + 26, half + 9), along(handleLen - 30, half + 7))
    ctx.saveGState()
    ctx.addPath(cap)
    ctx.clip()
    ctx.drawLinearGradient(gradient([
        color(0.86, 0.88, 0.92), color(0.60, 0.63, 0.69), color(0.34, 0.37, 0.42),
    ], [0, 0.55, 1]),
        start: along(handleLen, -half - 8), end: along(handleLen, half + 8), options: [])
    // Etched knot squiggles on the cap.
    ctx.setStrokeColor(color(0.25, 0.27, 0.31, 0.8))
    ctx.setLineWidth(2)
    for i in 0..<3 {
        let t = handleLen - 18 + CGFloat(i) * 16
        ctx.move(to: along(t, -half - 2))
        ctx.addQuadCurve(to: along(t + 8, half + 2), control: along(t - 8, 0))
    }
    ctx.strokePath()
    ctx.restoreGState()
    // Cap end: small rounded tip on the handle axis.
    ctx.setFillColor(color(0.55, 0.58, 0.64))
    ctx.fillEllipse(in: CGRect(x: pommel.x + dir.dx * 28 - 24,
                               y: pommel.y + dir.dy * 28 - 18, width: 48, height: 36))

    ctx.endTransparencyLayer()
    ctx.restoreGState()

    // Compact leather strap loop hanging off the pommel.
    ctx.saveGState()
    ctx.setStrokeColor(color(0.55, 0.36, 0.20))
    ctx.setLineWidth(13)
    ctx.setLineCap(.round)
    let anchor = P(pommel.x + dir.dx * 16, pommel.y + dir.dy * 16)
    ctx.move(to: anchor)
    ctx.addCurve(to: P(anchor.x + 52, anchor.y - 86),
                 control1: P(anchor.x + 66, anchor.y - 4),
                 control2: P(anchor.x + 78, anchor.y - 48))
    ctx.addCurve(to: P(anchor.x - 6, anchor.y - 34),
                 control1: P(anchor.x + 26, anchor.y - 124),
                 control2: P(anchor.x - 22, anchor.y - 74))
    ctx.strokePath()
    // Strap edge highlight.
    ctx.setStrokeColor(color(0.78, 0.58, 0.38, 0.6))
    ctx.setLineWidth(3.5)
    ctx.move(to: anchor)
    ctx.addCurve(to: P(anchor.x + 48, anchor.y - 84),
                 control1: P(anchor.x + 60, anchor.y - 8),
                 control2: P(anchor.x + 72, anchor.y - 48))
    ctx.strokePath()
    ctx.restoreGState()
}

// MARK: - Compose

func render() -> CGImage {
    let ctx = CGContext(data: nil, width: Int(SIZE), height: Int(SIZE),
                        bitsPerComponent: 8, bytesPerRow: 0, space: space,
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!

    let shape = CGPath(roundedRect: CGRect(x: 100, y: 100, width: 824, height: 824),
                       cornerWidth: 185, cornerHeight: 185, transform: nil)
    ctx.saveGState()
    ctx.setShadow(offset: CGSize(width: 0, height: -10), blur: 24,
                  color: color(0, 0, 0, 0.30))
    ctx.addPath(shape)
    ctx.setFillColor(color(0.06, 0.07, 0.10))
    ctx.fillPath()
    ctx.restoreGState()

    ctx.saveGState()
    ctx.addPath(shape)
    ctx.clip()

    // Storm-light slate with a cool glow behind the head.
    ctx.drawLinearGradient(gradient([
        color(0.17, 0.19, 0.25), color(0.09, 0.10, 0.14), color(0.05, 0.055, 0.08),
    ], [0, 0.55, 1]),
        start: P(512, 924), end: P(512, 100), options: [])
    ctx.drawRadialGradient(gradient([
        color(0.45, 0.55, 0.75, 0.32), color(0.45, 0.55, 0.75, 0),
    ], [0, 1]),
        startCenter: P(440, 420), startRadius: 0,
        endCenter: P(440, 420), endRadius: 500, options: [])

    // Slight global lift so the composition centers in the squircle.
    ctx.translateBy(x: 30, y: 40)

    // Soft contact shadow pooling under the head.
    ctx.drawRadialGradient(gradient([
        color(0, 0, 0, 0.42), color(0, 0, 0, 0),
    ], [0, 1]),
        startCenter: P(430, 150), startRadius: 0,
        endCenter: P(430, 150), endRadius: 330,
        options: [])

    drawHandle(ctx)
    drawHead(ctx)

    ctx.restoreGState()

    ctx.addPath(shape)
    ctx.setStrokeColor(color(1, 1, 1, 0.14))
    ctx.setLineWidth(2.5)
    ctx.strokePath()

    return ctx.makeImage()!
}

let outDir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "concepts"
let outURL = URL(fileURLWithPath: outDir, isDirectory: true)
try? FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)
let dest = CGImageDestinationCreateWithURL(
    outURL.appendingPathComponent("4-mjolnir.png") as CFURL,
    UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, render(), nil)
CGImageDestinationFinalize(dest)
print("Rendered 4-mjolnir.png")
