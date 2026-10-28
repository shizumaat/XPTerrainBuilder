import SwiftUI

/// The map's tile selection focus ring (#1537). A ring, not a fill: a fill
/// tints the very imagery the user is judging. The active tile: a solid
/// ring with a soft outer glow (the macOS focus-ring look); other selected
/// tiles: dashed. The colour is the system accent colour, so it follows
/// System Settings (Qt: the palette highlight, `O4_Qt_Selection_Ring`).
/// The Activity list shows the same selection with its own native
/// highlight (`ActivityListSelection`, #1537).
enum TileSelectionRing {
    static var color: Color { .accentColor }

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
