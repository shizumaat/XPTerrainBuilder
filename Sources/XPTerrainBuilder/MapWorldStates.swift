import SwiftUI
import SceneryKit

/// The Build map's World states (#2024; Qt: `O4_Qt_Map_World`, same
/// colours): what the World pack draws on each tile. Borders only, never
/// a fill (#1256: a tint colours the imagery being judged) — each the
/// shared fading band inside the tile's edge (`TileBand`). A full tile is
/// green (also a built tile the World pack does not list, #2031), a mesh whose imagery streams is teal with its
/// sharp fraction as a bar along its bottom edge, a drape is pink, and a
/// placeholder a faint thin gray outline; a tile with nothing is left
/// unmarked. Another tool's mesh is dotted. Drawn under the built-tile
/// borders.
enum MapWorldStates {
    static let full = Color(red: 0.30, green: 0.69, blue: 0.43)        // #4CAF6E
    static let mesh = Color(red: 0.19, green: 0.69, blue: 0.78)        // #30B0C7
    static let drape = Color(red: 1.0, green: 0.39, blue: 0.51)        // #FF6482
    static let placeholder = Color(white: 0.85)
    /// The placeholder outline's opacity and width (Qt: PLACEHOLDER_ALPHA).
    static let placeholderOpacity = 0.30
    static let placeholderWidth: CGFloat = 1
    /// Another tool's mesh: the border's dash in points, dotted (Qt: OTHER_TOOL_DASH).
    static let otherToolDash: [CGFloat] = [2, 3]

    static func color(_ state: O4WorldTile.State) -> Color? {
        switch state {
        case .full: return full
        case .meshLowRes: return mesh
        case .drape: return drape
        case .placeholder: return placeholder
        case .nothing: return nil
        }
    }

    static func draw(in context: GraphicsContext, world: [BuildModel.TileCoord: O4WorldTile],
                     visible: (BuildModel.TileCoord) -> Bool,
                     rect: (BuildModel.TileCoord) -> CGRect,
                     skip: (BuildModel.TileCoord) -> Bool) {
        // Every placeholder in one stroke: ~18,000 tiles on a converted world.
        var outlines = Path()
        for (coord, tile) in world where tile.state == .placeholder && visible(coord) {
            outlines.addRect(rect(coord).insetBy(dx: 1, dy: 1))
        }
        context.stroke(outlines, with: .color(placeholder.opacity(placeholderOpacity)),
                       lineWidth: placeholderWidth)
        for (coord, tile) in world where visible(coord) && !skip(coord) {
            guard tile.state != .placeholder, let base = color(tile.state) else { continue }
            let r = rect(coord)
            TileBandDrawing.draw(in: context, rect: r, color: base,
                                 dash: tile.otherTool ? otherToolDash : [])
            if tile.state == .meshLowRes, r.width > 24 {
                let h = min(max(r.height * 0.05, 3), 6)
                let bar = CGRect(x: r.minX + 3, y: r.maxY - h - 3, width: r.width - 6, height: h)
                context.fill(Path(bar), with: .color(Color.black.opacity(0.35)))
                context.fill(Path(CGRect(x: bar.minX, y: bar.minY,
                                         width: bar.width * min(max(tile.sharp, 0), 1),
                                         height: h)),
                             with: .color(full))
            }
        }
    }
}
