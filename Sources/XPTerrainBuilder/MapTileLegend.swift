import SwiftUI
import SceneryKit

/// The map's tile legend (#1958, #2024; the Qt map's `O4_Qt_Map_Legend`,
/// same words, colors and order): what the World pack draws on each tile
/// (`MapWorldStates`), which border is a tile this app built, which is
/// "some ortho" another tool made, which tile no longer fits the airport
/// pack X-Plane draws, which lives on another drive, and what the orange
/// custom-patch band means. Only the kinds on the map now are listed.
struct MapTileLegend: View {
    enum Kind: CaseIterable {
        case worldFull, worldMesh, worldDrape, worldPlaceholder, worldNothing, worldOtherTool
        case built, other, stale, external, customPatch

        /// The legend's words (Qt: `LEGEND_LABELS`, same order).
        var label: String {
            switch self {
            case .worldFull: return O4WorldStateText.legendFull
            case .worldMesh: return O4WorldStateText.legendMesh
            case .worldDrape: return O4WorldStateText.legendDrape
            case .worldPlaceholder: return O4WorldStateText.legendPlaceholder
            case .worldNothing: return O4WorldStateText.legendNothing
            case .worldOtherTool: return O4WorldStateText.legendOtherTool
            case .built: return "XPTerrainBuilder tile"
            case .other: return "Other ortho"
            case .stale: return "Airport pack changed"
            case .external: return "On another drive"
            case .customPatch: return O4WorldStateText.legendCustomPatch
            }
        }

        var color: Color {
            switch self {
            case .worldFull: return MapWorldStates.full
            case .worldMesh: return MapWorldStates.mesh
            case .worldDrape: return MapWorldStates.drape
            case .worldPlaceholder: return MapWorldStates.placeholder.opacity(MapWorldStates.placeholderOpacity)
            case .worldNothing: return .clear   // unmarked: an empty swatch
            case .worldOtherTool: return MapCanvasView.otherOrthoTile
            case .built: return MapCanvasView.builtTile
            case .other: return MapCanvasView.otherOrthoTile
            case .stale: return MapCanvasView.staleTile
            case .external: return MapCanvasView.builtExternalTile
            case .customPatch: return MapCanvasView.customPatchBand
            }
        }

        var dash: [CGFloat] {
            switch self {
            case .stale: return [4, 2]
            case .worldOtherTool: return MapWorldStates.otherToolDash
            default: return []
            }
        }

        var lineWidth: CGFloat {
            switch self {
            case .customPatch: return 3
            case .worldPlaceholder: return 1
            default: return 2
            }
        }
    }

    @ObservedObject var buildModel: BuildModel
    /// The Fly view hides this legend: its pane holds the one key
    /// (`FlyLegend`, owner 2026-11-12T19:12Z; Qt: `tile_legend_shown`).
    @ObservedObject private var modes: AppModeModel

    init(buildModel: BuildModel) {
        self.buildModel = buildModel
        self.modes = buildModel.appMode
    }

    /// The kinds present on the map now, in the legend's order.
    static func kinds(built: [BuildModel.TileCoord: O4TileInfo],
                      stale: [BuildModel.TileCoord: O4StaleTile],
                      world: [BuildModel.TileCoord: O4WorldTile] = [:],
                      customPatch: Bool = false) -> [Kind] {
        var present: [Kind] = []
        let states = Set(world.values.map(\.state))
        if states.contains(.full) { present.append(.worldFull) }
        if states.contains(.meshLowRes) { present.append(.worldMesh) }
        if states.contains(.drape) { present.append(.worldDrape) }
        if states.contains(.placeholder) { present.append(.worldPlaceholder) }
        if !world.isEmpty { present.append(.worldNothing) }
        if world.values.contains(where: \.otherTool) { present.append(.worldOtherTool) }
        if built.values.contains(where: { !$0.builtElsewhere }) { present.append(.built) }
        if built.values.contains(where: \.builtElsewhere) { present.append(.other) }
        if !built.isEmpty, !stale.isEmpty { present.append(.stale) }
        if built.values.contains(where: { $0.volume != nil }) { present.append(.external) }
        if customPatch { present.append(.customPatch) }
        return present
    }

    var body: some View {
        let kinds = Self.kinds(built: buildModel.built, stale: buildModel.staleTiles,
                               world: buildModel.worldTiles,
                               customPatch: !buildModel.customPatchTiles.isEmpty)
        if !kinds.isEmpty, modes.mode != .fly {
            VStack(alignment: .leading, spacing: 3) {
                ForEach(kinds, id: \.self) { kind in
                    HStack(spacing: 6) {
                        Rectangle()
                            .strokeBorder(kind.color,
                                          style: StrokeStyle(lineWidth: kind.lineWidth,
                                                             dash: kind.dash))
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
