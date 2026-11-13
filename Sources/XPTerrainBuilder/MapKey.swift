import SwiftUI
import SceneryKit

/// The map's ONE key in the Build and Fly views (owner 2026-11-12T22:05Z,
/// #2031; Qt: `O4_Qt_Map_Key`, same items, words, order and colours): a
/// pill at the map's bottom-right under the ZL pill, its items in a row —
/// a swatch in the item's one colour and a short word (`MapKeyText`),
/// truncated with "…" when the row runs out of room, the full sentence on
/// hover. The Build view lists the kinds on the map now (#1958, #2024),
/// the Fly view its corridor's items (§14).
struct MapKey: View {
    @ObservedObject var buildModel: BuildModel
    @ObservedObject private var modes: AppModeModel
    /// The Build view's key is hidden while only other packs are shown.
    let showBuildKinds: Bool
    /// The map's width: the pill is at most `MapKeyText.maxWidthFraction`.
    let mapWidth: CGFloat

    init(buildModel: BuildModel, showBuildKinds: Bool, mapWidth: CGFloat) {
        self.buildModel = buildModel
        self.modes = buildModel.appMode
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
        // a stale built tile draws "Pack changed" in place of its World band
        let rows = world.filter { stale[$0.key] == nil || built[$0.key] == nil }.values
        let states = Set(rows.map(\.state))
        let looks = built.compactMap { builtLook($0.value, world[$0.key], stale: stale[$0.key] != nil) }
        if states.contains(.full) || looks.contains(where: { $0.item == "full" }) { present.insert("full") }
        if states.contains(.meshLowRes) { present.insert("mesh") }
        if states.contains(.drape) { present.insert("drape") }
        if states.contains(.placeholder) { present.insert("placeholder") }
        if rows.contains(where: \.otherTool) || looks.contains(where: \.dotted) { present.insert("other_tool") }
        if looks.contains(where: { $0.item == "stale" }) { present.insert("stale") }
        if customPatch { present.insert("custom") }
        return MapKeyText.ordered(present)
    }

    /// How a scanned built tile is drawn (#2031; Qt:
    /// `O4_Qt_Map_Legend.built_look`): nil when its World state draws it
    /// alone. A stale tile is the dashed "Pack changed"; a built tile the
    /// World pack does not list is "Full", dotted when another tool built
    /// it. Where it lives ("Requires <drive>") is a label, not a colour.
    static func builtLook(_ info: O4TileInfo, _ world: O4WorldTile?,
                          stale: Bool) -> (item: String, dotted: Bool)? {
        if stale { return ("stale", false) }
        if let world, world.state != .nothing { return nil }
        return ("full", info.builtElsewhere)
    }

    /// The Fly view's items: every cell key's (Qt: `FlyLayer.key_items`).
    static func flyItems() -> [String] {
        MapKeyText.ordered(Set(FlyText.legend.compactMap { MapKeyText.flyKeyItems[$0.0] }))
    }

    /// The item's one colour, the same on the Build and Fly views (#2031;
    /// Qt: `O4_Qt_Map_Key.item_color`).
    static func color(_ item: String) -> Color? {
        switch item {
        case "full": return MapWorldStates.full
        case "mesh": return MapWorldStates.mesh
        case "drape": return MapWorldStates.drape
        case "placeholder": return MapWorldStates.placeholder.opacity(MapWorldStates.placeholderOpacity)
        case "building": return FlyMapOverlay.building
        // another tool's tile: a white swatch, its dots the item (the map
        // draws the tile in its state's colour, dotted)
        case "other_tool": return .white
        case "stale": return MapCanvasView.staleTile
        case "custom": return MapCanvasView.customPatchBand
        default: return nil
        }
    }

    /// The swatch's stroke: dashed for a stale tile, dotted for another
    /// tool's tile, thick for the patch band.
    static func style(_ item: String) -> StrokeStyle {
        let width: CGFloat = item == "custom" ? 3 : item == "placeholder" ? 1 : 2
        let dash: [CGFloat] = item == "stale" ? [4, 2]
            : item == "other_tool" ? MapWorldStates.otherToolDash : []
        return StrokeStyle(lineWidth: width, dash: dash)
    }

    private var items: [String] {
        if modes.mode == .fly { return Self.flyItems() }
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
