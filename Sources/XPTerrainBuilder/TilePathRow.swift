import AppKit
import SwiftUI
import SceneryKit

/// The tile pane's "Path" row (#1987; the Qt pane's
/// `O4_Qt_Tile_Path_Row.TilePathRow`, same words). The tile's folder with
/// its links resolved — a `zOrtho4XP_*` link in Custom Scenery shows the
/// folder on the drive it points to — and a small button that shows it in
/// Finder, disabled with "<drive> is not connected." while that drive is
/// away. A tile whose folder holds only records (adopted or converted
/// into the World pack) shows and reveals its DSF in the World pack
/// instead (#2027, `O4WorldTile.revealDSF`).
struct TilePathRow: View {
    static let title = "Path"

    let info: O4TileInfo
    /// The tile's World state (nil: the pack does not hold it).
    var world: O4WorldTile? = nil

    private var worldDSF: String? { world?.revealDSF(info) }
    private var path: String { worldDSF ?? info.folderPath }
    private var reachable: Bool { worldDSF != nil || info.folderReachable }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(Self.title + ":")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(path)
                        .scaledFont(.caption)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help(path)
                    Button {
                        NSWorkspace.shared.activateFileViewerSelecting(
                            [URL(fileURLWithPath: path, isDirectory: worldDSF == nil)])
                    } label: {
                        Image(systemName: "arrow.up.forward.app")
                    }
                    .buttonStyle(.borderless)
                    .scaledFont(.caption)
                    .disabled(!reachable)
                    .help("Show in Finder")
                }
                if let volume = info.volume, !reachable {
                    Text(O4TileVolumeText.offlineNote(volume))
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}
