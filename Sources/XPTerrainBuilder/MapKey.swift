import SwiftUI
import SceneryKit

/// The map's ONE key in the Build and Fly views (owner 2026-11-12T22:05Z;
/// Qt: `O4_Qt_Map_Key`, same items, order and colours): a pill at the
/// map's bottom-right under the ZL pill, its items in a row — a swatch in
/// the item's one colour and a short word (`MapKeyText`), truncated with
/// "…" when the row runs out of room, the full sentence on hover. The
/// Build view lists the kinds on the map now (#1958, #2024), the Fly view
/// its corridor's keys (§14; the preview's only while "Live flight
/// preview" is on).
struct MapKey: View {
    @ObservedObject var buildModel: BuildModel
    @ObservedObject private var modes: AppModeModel
    @ObservedObject private var fly: FlyModel
    /// The Build view's key is hidden while only other packs are shown.
    let showBuildKinds: Bool
    /// The map's width: the pill is at most `MapKeyText.maxWidthFraction`.
    let mapWidth: CGFloat

    init(buildModel: BuildModel, showBuildKinds: Bool, mapWidth: CGFloat) {
        self.buildModel = buildModel
        self.modes = buildModel.appMode
        self.fly = buildModel.fly
        self.showBuildKinds = showBuildKinds
        self.mapWidth = mapWidth
    }

    /// The kinds present on the Build map now, in the key's order (Qt:
    /// `O4_Qt_Map_Legend.legend_kinds`).
    static func buildItems(built: [BuildModel.TileCoord: O4TileInfo],
                           stale: [BuildModel.TileCoord: O4StaleTile],
                           world: [BuildModel.TileCoord: O4WorldTile] = [:],
                           customPatch: Bool = false) -> [String] {
        var present: Set<String> = []
        let states = Set(world.values.map(\.state))
        if states.contains(.full) { present.insert("full") }
        if states.contains(.meshLowRes) { present.insert("mesh") }
        if states.contains(.drape) { present.insert("drape") }
        if states.contains(.placeholder) { present.insert("placeholder") }
        if world.values.contains(where: \.otherTool) { present.insert("other_tool") }
        let infos = built.filter { !drawnByWorld($0.value, world[$0.key]) }.values
        if infos.contains(where: { !$0.builtElsewhere }) { present.insert("built") }
        if infos.contains(where: \.builtElsewhere) { present.insert("other") }
        if !infos.isEmpty, !stale.isEmpty { present.insert("stale") }
        if infos.contains(where: { $0.volume != nil }) { present.insert("external") }
        if customPatch { present.insert("custom") }
        return MapKeyText.ordered(present)
    }

    /// Is a scanned tile drawn by its World state alone (#2027): its folder
    /// holds only records and the World pack holds its DSF (Qt:
    /// `O4_Qt_Map_Legend.drawn_by_world`)?
    static func drawnByWorld(_ info: O4TileInfo, _ world: O4WorldTile?) -> Bool {
        world?.revealDSF(info) != nil
    }

    /// The Fly view's items: every cell key, the preview's only while
    /// "Live flight preview" is on (Qt: `FlyLayer.key_items`).
    static func flyItems(livePreview: Bool) -> [String] {
        MapKeyText.ordered(Set(FlyText.legend.map(\.0)
            .filter { livePreview || !FlyText.previewKeys.contains($0) }
            .compactMap { MapKeyText.flyKeyItems[$0] }))
    }

    /// The item's one colour (nil: the empty swatch of an unmarked tile).
    static func color(_ item: String) -> Color? {
        switch item {
        case "full": return MapWorldStates.full
        case "built": return MapCanvasView.builtTile
        case "mesh": return MapWorldStates.mesh
        case "drape": return MapWorldStates.drape
        case "placeholder": return MapWorldStates.placeholder.opacity(MapWorldStates.placeholderOpacity)
        // another tool's mesh: a white swatch, its dots the item (the map
        // draws the tile in its state's colour, dotted)
        case "other_tool": return .white
        case "other": return MapCanvasView.otherOrthoTile
        case "meshing": return FlyMapOverlay.color("meshing")
        case "draping": return FlyMapOverlay.color("draping")
        case "route": return FlyMapOverlay.color("own")
        case "stale": return MapCanvasView.staleTile
        case "external": return MapCanvasView.builtExternalTile
        case "custom": return MapCanvasView.customPatchBand
        case "sharp": return FlyMapOverlay.color("sharp")
        default: return nil
        }
    }

    /// The swatch's stroke: dashed for a drape being draped or a stale
    /// tile, dotted for another tool's mesh, thick for the patch band.
    static func style(_ item: String) -> StrokeStyle {
        let width: CGFloat = item == "custom" ? 3 : item == "placeholder" ? 1 : 2
        let dash: [CGFloat] = ["stale", "draping"].contains(item) ? [4, 2]
            : item == "other_tool" ? MapWorldStates.otherToolDash : []
        return StrokeStyle(lineWidth: width, dash: dash)
    }

    private var items: [String] {
        if modes.mode == .fly { return Self.flyItems(livePreview: fly.livePreview) }
        guard showBuildKinds else { return [] }
        return Self.buildItems(built: buildModel.built, stale: buildModel.staleTiles,
                               world: buildModel.worldTiles,
                               customPatch: !buildModel.customPatchTiles.isEmpty)
    }

    var body: some View {
        let items = self.items
        if !items.isEmpty {
            HStack(spacing: 10) {
                ForEach(items, id: \.self) { item in
                    HStack(spacing: 4) {
                        Rectangle()
                            .strokeBorder(Self.color(item) ?? .clear, style: Self.style(item))
                            .frame(width: 12, height: 9)
                        Text(MapKeyText.short[item] ?? item)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                    .help(MapKeyText.full[item] ?? "")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(.ultraThinMaterial, in: Capsule())
            .frame(maxWidth: max(120, mapWidth * MapKeyText.maxWidthFraction), alignment: .trailing)
            .fixedSize(horizontal: false, vertical: true)
        }
    }
}
