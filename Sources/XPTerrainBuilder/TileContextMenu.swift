import AppKit
import SceneryKit

/// The map's tile right-click menu (#938; Qt O4_Qt_Tile_Menu). Show in
/// Finder reveals the tile's folder (greyed out while the tile has none
/// yet). In patch Edit mode the menu starts with Slice (#1318; Qt
/// `PatchEditor.add_to_menu`), enabled only for two nodes of one shape that
/// are not neighbours. The menu's items target this object, so the caller
/// keeps it alive while the menu is open.
@MainActor
final class TileContextMenu: NSObject {
    static let revealTitle = "Show in Finder"
    static let sliceTitle = "Slice"

    let folder: URL?
    let menu = NSMenu()
    private weak var patch: PatchEditModel?

    init(coord: BuildModel.TileCoord, folder: URL?, patch: PatchEditModel? = nil) {
        self.folder = folder
        super.init()
        menu.autoenablesItems = false
        if let patch, patch.mode == .edit, patch.document != nil {
            self.patch = patch
            let slice = NSMenuItem(title: Self.sliceTitle, action: #selector(sliceShape), keyEquivalent: "")
            slice.target = self
            do {
                _ = try patch.sliceArgs()
            } catch {
                slice.isEnabled = false
                slice.toolTip = "\(error)"
            }
            menu.addItem(slice)
            menu.addItem(.separator())
        }
        let item = NSMenuItem(title: Self.revealTitle,
                              action: #selector(reveal), keyEquivalent: "")
        item.target = self
        item.isEnabled = folder != nil
        item.toolTip = folder == nil
            ? "Tile \(coord.key) has no folder yet: build it first." : folder?.path
        menu.addItem(item)
    }

    @objc private func sliceShape() {
        patch?.sliceSelection()
    }

    @objc private func reveal() {
        guard let folder else { return }
        NSWorkspace.shared.activateFileViewerSelecting([folder])
    }
}

extension BuildModel {
    /// The tile's build folder when it exists on disk.
    func tileFolder(_ coord: TileCoord) -> URL? {
        guard let info = built[coord], !info.buildDir.isEmpty else { return nil }
        let url = URL(fileURLWithPath: info.buildDir, isDirectory: true)
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory),
              isDirectory.boolValue else { return nil }
        return url
    }
}
