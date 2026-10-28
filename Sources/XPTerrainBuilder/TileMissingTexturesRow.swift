import SwiftUI
import SceneryKit

/// The tile pane's missing-textures warning (the Qt pane's
/// `O4_Qt_Missing_Textures.MissingTexturesRow`, same words): an installed
/// tile whose terrain files name textures its `textures/` folder lacks is a
/// tile X-Plane will not load. The engine's `tile_texture_check` answers;
/// the row says so in one line, explains on hover, and offers "Rebuild
/// Tile" through the Build box's own path. Nothing shows while all is well.
///
/// The row only SHOWS a check; `TileTextureCheckTask` on the always-drawn
/// pane asks for it. A `.task` on this row never ran (#1563): while the
/// row shows nothing its body is empty, and SwiftUI starts no task on an
/// empty view — so the first check, the one that would show the row, was
/// never asked for.
struct TileMissingTexturesRow: View {
    let check: O4TileTextureCheck?
    /// Rebuild the tile; a refusal sentence, or nil once it is queued. A new
    /// check passes through nil (`TileTextureCheckTask`), which drops the
    /// last refusal with the row.
    let rebuild: () -> String?

    @State private var refusal: String?

    var body: some View {
        Group {
            if let check, check.missingCount > 0 {
                VStack(alignment: .leading, spacing: 4) {
                    Label(check.warningText, systemImage: "exclamationmark.triangle.fill")
                        .scaledFont(.caption)
                        .foregroundStyle(.orange)
                        .help(check.detailText)
                    HStack {
                        Button("Rebuild Tile") { refusal = rebuild() }
                            .controlSize(.small)
                            .help("Build this tile again with the imagery it was built with.")
                        if let refusal {
                            Text(refusal)
                                .scaledFont(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}

/// Asks for the active tile's texture check whenever `key` changes, into
/// `check`. Apply it to a view that is always drawn (the tile pane), never
/// to the row it feeds — see `TileMissingTexturesRow`.
struct TileTextureCheckTask: ViewModifier {
    let key: String
    let load: () async -> O4TileTextureCheck?
    @Binding var check: O4TileTextureCheck?

    func body(content: Content) -> some View {
        content.task(id: key) {
            check = nil           // never show the last tile's answer
            let answer = await load()
            if !Task.isCancelled { check = answer }   // a newer tile's key won
        }
    }
}

extension BuildModel {
    /// Re-check when the tile, its folder, a scan or a build changes.
    func tileTextureCheckKey(for coord: TileCoord?) -> String {
        guard let coord else { return "textures|" }
        return "textures|\(coord.key)|\(built[coord]?.buildDir ?? "")|\(built.count)|\(isBuilding)"
    }
}
