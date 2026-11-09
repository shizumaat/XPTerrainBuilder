import AppKit
import SwiftUI
import SceneryKit

/// The tile pane's "Path" row (#1987; the Qt pane's
/// `O4_Qt_Tile_Path_Row.TilePathRow`, same words). The tile's folder with
/// its links resolved — a `zOrtho4XP_*` link in Custom Scenery shows the
/// folder on the drive it points to — and a small button that shows it in
/// Finder, disabled with "<drive> is not connected." while that drive is
/// away.
struct TilePathRow: View {
    static let title = "Path"

    let info: O4TileInfo

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(Self.title + ":")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(info.folderPath)
                        .scaledFont(.caption)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help(info.folderPath)
                    Button {
                        NSWorkspace.shared.activateFileViewerSelecting(
                            [URL(fileURLWithPath: info.folderPath, isDirectory: true)])
                    } label: {
                        Image(systemName: "arrow.up.forward.app")
                    }
                    .buttonStyle(.borderless)
                    .scaledFont(.caption)
                    .disabled(!info.folderReachable)
                    .help("Show in Finder")
                }
                if let volume = info.volume, !info.folderReachable {
                    Text(O4TileVolumeText.offlineNote(volume))
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}
