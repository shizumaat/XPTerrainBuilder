import SwiftUI
import SceneryKit

/// The tile pane's missing-textures warning (the Qt pane's
/// `O4_Qt_Missing_Textures.MissingTexturesRow`, same words): an installed
/// tile whose terrain files name textures its `textures/` folder lacks is a
/// tile X-Plane will not load. The engine's `tile_texture_check` answers;
/// the row says so in one line, explains on hover, and offers "Rebuild
/// Tile" through the Build box's own path. Nothing shows while all is well.
struct TileMissingTexturesRow: View {
    @EnvironmentObject var buildModel: BuildModel
    let coord: BuildModel.TileCoord

    @State private var check: O4TileTextureCheck?
    @State private var refusal: String?

    /// Re-check when the tile, its folder, a scan or a build changes.
    private var checkKey: String {
        "\(coord.key)|\(buildModel.built[coord]?.buildDir ?? "")|\(buildModel.built.count)|\(buildModel.isBuilding)"
    }

    var body: some View {
        Group {
            if let check, check.missingCount > 0 {
                VStack(alignment: .leading, spacing: 4) {
                    Label(check.warningText, systemImage: "exclamationmark.triangle.fill")
                        .scaledFont(.caption)
                        .foregroundStyle(.orange)
                        .help(check.detailText)
                    HStack {
                        Button("Rebuild Tile") {
                            refusal = buildModel.rebuildWithItsImagery(coord)
                        }
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
        .task(id: checkKey) {
            refusal = nil
            check = await buildModel.tileTextureCheck(for: coord)
        }
    }
}
