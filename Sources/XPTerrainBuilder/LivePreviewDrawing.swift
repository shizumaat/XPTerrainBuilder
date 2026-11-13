import SwiftUI
import SceneryKit

/// The live flight preview on Fly mode's map (#2001; owner
/// 2026-11-12T19:28Z: the map shows exactly what X-Plane shows): each
/// square's installed imagery, the full-resolution ones outlined (#2020),
/// the `stale` squares and `reload` tiles hatched ("Reload scenery to
/// see"), the `own` tiles washed (X-Plane's own scenery; the map's base
/// imagery shows). The Qt window's `O4_Qt_Live_Preview.LivePreview.paint`
/// is the same; the words and colors are `LivePreviewText`.
@MainActor
enum LivePreviewDrawing {
    /// A mark's words are drawn on a rect at least this wide (points).
    static let labelMinWidth: CGFloat = 140

    static func color(_ key: String) -> Color {
        let rgb = LivePreviewText.markColors[key] ?? (140, 140, 140)
        return Color(red: Double(rgb.0) / 255, green: Double(rgb.1) / 255, blue: Double(rgb.2) / 255)
    }

    static func draw(_ preview: LivePreviewModel, _ cam: MapCamera, _ size: CGSize,
                     _ context: inout GraphicsContext, sharpColor: Color?) {
        _ = preview.revision
        func rect(north: Double, west: Double, south: Double, east: Double) -> CGRect {
            let a = cam.point(lon: west, lat: north, in: size)
            let b = cam.point(lon: east, lat: south, in: size)
            return CGRect(x: min(a.x, b.x), y: min(a.y, b.y),
                          width: abs(b.x - a.x), height: abs(b.y - a.y))
        }
        var sharp = Path()
        var stale: [CGRect] = []
        for square in preview.drawn {        // coarse level first (#2012)
            guard let image = preview.image(square) else { continue }
            let r = rect(north: square.north, west: square.west, south: square.south, east: square.east)
            context.draw(Image(decorative: image, scale: 1), in: r)
            if square.sharp { sharp.addRect(r.insetBy(dx: 0.5, dy: 0.5)) }
            if square.stale { stale.append(r) }
        }
        // "Sharp photo" (#2031, the preview's toggle): nil hides the outlines
        if let sharpColor { context.stroke(sharp, with: .color(sharpColor), lineWidth: 1) }
        func tileRects(_ state: String) -> [CGRect] {
            preview.tiles.filter { $0.state == state }.map {
                rect(north: Double($0.lat + 1), west: Double($0.lon),
                     south: Double($0.lat), east: Double($0.lon + 1))
            }
        }
        let bounds = CGRect(origin: .zero, size: size)
        mark(stale + tileRects("reload"), color("reload"), spacing: 8, opacity: 0.9,
             label: LivePreviewText.reloadLabel, bounds, &context)
        mark(tileRects("own"), color("own"), spacing: 14, opacity: 0.6,
             label: nil, bounds, &context)
    }

    /// `rects` hatched with diagonal lines, outlined and labelled (no
    /// words for a nil `label`).
    private static func mark(_ rects: [CGRect], _ color: Color, spacing: CGFloat, opacity: Double,
                             label: String?, _ bounds: CGRect, _ context: inout GraphicsContext) {
        guard !rects.isEmpty else { return }
        for r in rects {
            let shown = r.intersection(bounds)
            guard !shown.isNull, shown.width > 0 else { continue }
            var hatch = Path()
            var x = shown.minX - shown.height
            while x < shown.maxX {
                hatch.move(to: CGPoint(x: x, y: shown.maxY))
                hatch.addLine(to: CGPoint(x: x + shown.height, y: shown.minY))
                x += spacing
            }
            var clipped = context
            clipped.clip(to: Path(shown))
            clipped.stroke(hatch, with: .color(color.opacity(opacity)), lineWidth: 1)
            context.stroke(Path(r.insetBy(dx: 0.5, dy: 0.5)), with: .color(color), lineWidth: 1)
            guard let label, shown.width >= labelMinWidth else { continue }
            let text = context.resolve(Text(label).font(.caption).foregroundColor(.white))
            let measured = text.measure(in: shown.size)
            let plate = CGRect(x: shown.midX - measured.width / 2 - 6, y: shown.midY - measured.height / 2 - 3,
                               width: measured.width + 12, height: measured.height + 6)
            context.fill(Path(roundedRect: plate, cornerRadius: 4), with: .color(.black.opacity(0.66)))
            context.draw(text, at: CGPoint(x: shown.midX, y: shown.midY))
        }
    }
}
