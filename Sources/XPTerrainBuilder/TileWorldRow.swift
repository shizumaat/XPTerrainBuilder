import SwiftUI
import SceneryKit

/// The tile pane's "World pack" row (owner 2026-11-12T20:23Z; the Qt
/// pane's `O4_Qt_Tile_World_Row.TileWorldRow`, same words): what the World
/// pack holds for the tile — "Built (in the World pack): mesh + full
/// imagery", who made it and where its own files live — and, for a real
/// tile, Rebuild Tile (its rebuild inputs, even when the tiles folder
/// holds only those), Export Package… and Remove from World Pack… (its
/// package first, then the placeholder; confirmed first). Hidden when the
/// World pack holds nothing of the tile.
struct TileWorldRow: View {
    let coord: BuildModel.TileCoord
    let world: O4WorldTile?
    /// Rebuild the tile; a refusal sentence, or nil once it is queued.
    let rebuild: () -> String?
    let exportPackage: () -> Void
    /// Remove it from the World pack; the note to show.
    let remove: () async -> String

    @State private var note: String?
    @State private var confirming = false

    var body: some View {
        let status = O4WorldStateText.paneStatus(world)
        if !status.isEmpty {
            VStack(alignment: .leading, spacing: 3) {
                Text(status)
                    .scaledFont(.caption, weight: .semibold)
                    .fixedSize(horizontal: false, vertical: true)
                let detail = O4WorldStateText.paneDetail(world)
                if !detail.isEmpty {
                    Text(detail)
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if O4WorldStateText.builtInWorld(world) {
                    HStack(spacing: 6) {
                        Button(O4WorldStateText.rebuildButton) { note = rebuild() }
                        Button(O4TilePackageCopy.exportTitle) { exportPackage() }
                        Button(O4WorldStateText.removeButton) { confirming = true }
                    }
                    .controlSize(.small)
                }
                if let note {
                    Text(note)
                        .scaledFont(.caption2)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .confirmationDialog(
                O4WorldStateText.removeTitle.replacingOccurrences(of: "{tile}", with: coord.key),
                isPresented: $confirming
            ) {
                Button(O4WorldStateText.removeConfirm, role: .destructive) {
                    Task { note = await remove() }
                }
            } message: {
                Text(O4WorldStateText.removeMessage)
            }
            .onChange(of: coord) { _, _ in note = nil }
        }
    }
}
