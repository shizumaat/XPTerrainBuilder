import SwiftUI
import SceneryKit

/// The map's tile legend (#1958; the Qt map's `O4_Qt_Map_Legend`, same
/// words and colors): which border is a tile this app built, which is
/// "some ortho" another tool made, which tile no longer fits the airport
/// pack X-Plane draws, and which lives on another drive. Only the kinds
/// on the map now are listed; with no built tile there is no legend.
struct MapTileLegend: View {
    enum Kind: CaseIterable {
        case built, other, stale, external

        /// The legend's words (Qt: `LEGEND_LABELS`, same order).
        var label: String {
            switch self {
            case .built: return "XPTerrainBuilder tile"
            case .other: return "Other ortho"
            case .stale: return "Airport pack changed"
            case .external: return "On another drive"
            }
        }

        var color: Color {
            switch self {
            case .built: return MapCanvasView.builtTile
            case .other: return MapCanvasView.otherOrthoTile
            case .stale: return MapCanvasView.staleTile
            case .external: return MapCanvasView.builtExternalTile
            }
        }

        var dashed: Bool { self == .stale }
    }

    @ObservedObject var buildModel: BuildModel

    /// The kinds present among the built tiles now.
    static func kinds(built: [BuildModel.TileCoord: O4TileInfo],
                      stale: [BuildModel.TileCoord: O4StaleTile]) -> [Kind] {
        guard !built.isEmpty else { return [] }
        var present: [Kind] = []
        if built.values.contains(where: { !$0.builtElsewhere }) { present.append(.built) }
        if built.values.contains(where: \.builtElsewhere) { present.append(.other) }
        if !stale.isEmpty { present.append(.stale) }
        if built.values.contains(where: { $0.volume != nil }) { present.append(.external) }
        return present
    }

    var body: some View {
        let kinds = Self.kinds(built: buildModel.built, stale: buildModel.staleTiles)
        if !kinds.isEmpty {
            VStack(alignment: .leading, spacing: 3) {
                ForEach(kinds, id: \.self) { kind in
                    HStack(spacing: 6) {
                        Rectangle()
                            .strokeBorder(kind.color,
                                          style: StrokeStyle(lineWidth: 2,
                                                             dash: kind.dashed ? [4, 2] : []))
                            .frame(width: 14, height: 10)
                        Text(kind.label)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding(.horizontal, 9)
            .padding(.vertical, 6)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
        }
    }
}
