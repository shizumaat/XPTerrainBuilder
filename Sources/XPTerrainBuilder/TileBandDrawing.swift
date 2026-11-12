import SwiftUI
import SceneryKit

/// Paints the map's tile-state band (`TileBand`, the rule; Qt:
/// `O4_Qt_Tile_Band`): the World states, the built tiles and the Fly
/// view's corridor cells all draw their colour through `draw`.
enum TileBandDrawing {
    /// `color`'s band inside `rect` (screen points); `opacity` scales the
    /// colour (a dimmed tile); `dash` (points) is drawn as a line along
    /// the band's outer side.
    static func draw(in context: GraphicsContext, rect: CGRect, color: Color,
                     opacity: Double = 1, dash: [CGFloat] = []) {
        let band = TileBand.band(px: rect.width)
        if band.mode == .line {
            line(context, rect, band.inset, band.width, color.opacity(opacity), dash)
            return
        }
        let outer = color.opacity(opacity * (dash.isEmpty ? TileBand.outerAlpha : TileBand.dashedOuterAlpha))
        let gradient = Gradient(colors: [outer, color.opacity(0)])
        for side in TileBand.sides(rect, inset: band.inset, width: band.width) {
            var path = Path()
            path.addLines(side.polygon)
            path.closeSubpath()
            context.fill(path, with: .linearGradient(gradient, startPoint: side.outer,
                                                     endPoint: side.inner))
        }
        if !dash.isEmpty {
            line(context, rect, band.inset, TileBand.dashLinePt, color.opacity(opacity), dash)
        }
    }

    /// A placeholder's faint outline, just inside the edge.
    static func outline(in context: GraphicsContext, rect: CGRect, color: Color) {
        line(context, rect, TileBand.tinyLinePt / 2, TileBand.tinyLinePt, color, [])
    }

    private static func line(_ context: GraphicsContext, _ rect: CGRect, _ inset: CGFloat,
                             _ width: CGFloat, _ color: Color, _ dash: [CGFloat]) {
        let d = inset + width / 2
        context.stroke(Path(rect.insetBy(dx: d, dy: d)), with: .color(color),
                       style: StrokeStyle(lineWidth: width, lineJoin: .miter, dash: dash))
    }
}
