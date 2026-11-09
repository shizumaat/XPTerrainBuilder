import SwiftUI
import SceneryKit

/// The tile pane's "Airport packs" row (#1958; the Qt pane's
/// `O4_Qt_Tile_Stale_Row.TileStaleRow`, same words): shown only on a tile
/// whose airport pack changed since its build — why, airport by airport,
/// and one click to rebuild it for the packs X-Plane draws now.
struct TileStaleRow: View {
    let stale: O4StaleTile
    /// Rebuild the tile; a refusal sentence, or nil once it is queued.
    let rebuild: () -> String?

    @State private var refusal: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label(O4TileStaleText.rowTitle + ": changed since the build",
                  systemImage: "exclamationmark.triangle.fill")
                .scaledFont(.caption)
                .foregroundStyle(MapCanvasView.staleTile)
            ForEach(stale.airports, id: \.icao) { airport in
                Text(airport.text)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(O4TileStaleText.rebuildNote)
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
            HStack {
                Button(O4TileStaleText.rebuildButton) { refusal = rebuild() }
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
