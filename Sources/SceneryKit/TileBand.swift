import CoreGraphics

/// The map's tile-state band: the ONE drawing rule both apps use for a
/// tile's colour on the map (owner 2026-11-12T22:01Z; Qt:
/// `O4_Tile_Band`, same numbers — `tests/test_tile_band.py` twins them).
/// A tile's colour is a band INSIDE its own edge, inset so a neighbour's
/// band never overlaps it, a few points wide (wider as the tile grows on
/// screen, within a min and max), full colour at its outer side fading to
/// transparent toward the tile's centre. A dashed or dotted key keeps its
/// dash as a line along the band's outer side, over a fainter band. A tile
/// too small for a gradient gets a plain inset line; a tiny one a 1 pt
/// line inside its edge. Lengths are screen points.
public enum TileBand {
    public static let insetPt: CGFloat = 1.5
    public static let widthMinPt: CGFloat = 4.0
    public static let widthMaxPt: CGFloat = 8.0
    public static let widthFraction: CGFloat = 0.06
    public static let gradientMinPx: CGFloat = 40.0
    public static let lineMinPx: CGFloat = 10.0
    public static let lineWidthPt: CGFloat = 2.0
    public static let tinyLinePt: CGFloat = 1.0
    public static let outerAlpha: Double = 0.95
    public static let dashedOuterAlpha: Double = 0.45
    public static let dashLinePt: CGFloat = 2.0
    public static let innerGapPt: CGFloat = 2.0

    public enum Mode: Equatable { case band, line }

    /// How a tile `px` points wide draws: a gradient band, or a line of
    /// `width` whose outer side is `inset` inside the edge.
    public struct Band: Equatable {
        public let mode: Mode
        public let inset: CGFloat
        public let width: CGFloat
    }

    public static func band(px: CGFloat) -> Band {
        if px >= gradientMinPx {
            return Band(mode: .band, inset: insetPt,
                        width: min(max(px * widthFraction, widthMinPt), widthMaxPt))
        }
        if px >= lineMinPx { return Band(mode: .line, inset: insetPt, width: lineWidthPt) }
        return Band(mode: .line, inset: 0, width: tinyLinePt)
    }

    /// One side of the band: its mitred polygon and the gradient's ends
    /// (full colour at `outer`, transparent at `inner`).
    public struct Side {
        public let polygon: [CGPoint]
        public let outer: CGPoint
        public let inner: CGPoint
    }

    /// The band's four sides inside `rect` (top, right, bottom, left).
    public static func sides(_ rect: CGRect, inset: CGFloat, width: CGFloat) -> [Side] {
        let o = rect.insetBy(dx: inset, dy: inset)
        let i = o.insetBy(dx: width, dy: width)
        let mx = rect.midX, my = rect.midY
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }
        return [
            Side(polygon: [p(o.minX, o.minY), p(o.maxX, o.minY), p(i.maxX, i.minY), p(i.minX, i.minY)],
                 outer: p(mx, o.minY), inner: p(mx, i.minY)),
            Side(polygon: [p(o.maxX, o.minY), p(o.maxX, o.maxY), p(i.maxX, i.maxY), p(i.maxX, i.minY)],
                 outer: p(o.maxX, my), inner: p(i.maxX, my)),
            Side(polygon: [p(o.maxX, o.maxY), p(o.minX, o.maxY), p(i.minX, i.maxY), p(i.maxX, i.maxY)],
                 outer: p(mx, o.maxY), inner: p(mx, i.maxY)),
            Side(polygon: [p(o.minX, o.maxY), p(o.minX, o.minY), p(i.minX, i.minY), p(i.minX, i.maxY)],
                 outer: p(o.minX, my), inner: p(i.minX, my)),
        ]
    }

    /// An installed tile's inner line: its inset in points, inside the
    /// band (3 % of the tile when there is no gradient band).
    public static func innerInset(px: CGFloat) -> CGFloat {
        let b = band(px: px)
        return b.mode == .band ? b.inset + b.width + innerGapPt : px * 0.03
    }
}
