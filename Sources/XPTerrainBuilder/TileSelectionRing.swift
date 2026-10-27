import SwiftUI

/// The tile selection's focus ring, drawn by the map's selected tiles and
/// by the Activity rows of selected tiles (#1537) from this one
/// definition. A ring, not a fill: a fill tints the very imagery the user
/// is judging. The active tile: a solid ring with a soft outer glow (the
/// macOS focus-ring look); other selected tiles: dashed. The colour is
/// the system accent colour, so it follows System Settings (Qt: the
/// palette highlight, `O4_Qt_Selection_Ring.draw`).
enum TileSelectionRing {
    static var color: Color { .accentColor }

    /// How far the glow reaches outside the ringed rect.
    static let glowReach: CGFloat = 4

    static func draw(in context: GraphicsContext, rect r: CGRect, active: Bool) {
        if active {
            context.stroke(Path(r.insetBy(dx: -1.5, dy: -1.5)),
                           with: .color(color.opacity(0.35)), lineWidth: 5)
            context.stroke(Path(r.insetBy(dx: 1, dy: 1)),
                           with: .color(color), lineWidth: 2.5)
        } else {
            context.stroke(Path(r.insetBy(dx: 1, dy: 1)),
                           with: .color(color),
                           style: StrokeStyle(lineWidth: 2, dash: [5, 4]))
        }
    }
}

/// The ring around a view (an Activity row), `margin` points outside it.
struct TileSelectionRingOverlay: View {
    let active: Bool
    var margin: CGFloat = 3

    var body: some View {
        let pad = margin + TileSelectionRing.glowReach
        Canvas { context, size in
            TileSelectionRing.draw(
                in: context,
                rect: CGRect(origin: .zero, size: size).insetBy(dx: TileSelectionRing.glowReach,
                                                                dy: TileSelectionRing.glowReach),
                active: active)
        }
        .padding(-pad)
        .allowsHitTesting(false)
    }
}
