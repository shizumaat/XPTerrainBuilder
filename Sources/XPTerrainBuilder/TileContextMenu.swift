import AppKit
import SceneryKit

/// The map's tile right-click menu (#938; Qt O4_Qt_Tile_Menu): Show in
/// Finder, which reveals the tile's folder (greyed out while the tile has
/// none yet), after the patch layer's copy items when there are any
/// (#1281, `PatchCopy.swift`). The menu's items target this object, so the
/// caller keeps it alive while the menu is open.
@MainActor
final class TileContextMenu: NSObject {
    static let revealTitle = "Show in Finder"

    let folder: URL?
    let copies: [PatchCopyItem]
    let menu = NSMenu()

    init(coord: BuildModel.TileCoord, folder: URL?, copies: [PatchCopyItem] = []) {
        self.folder = folder
        self.copies = copies
        super.init()
        menu.autoenablesItems = false
        for (k, copy) in copies.enumerated() {
            let item = NSMenuItem(title: copy.title, action: #selector(copyItem(_:)), keyEquivalent: "")
            item.target = self
            item.tag = k
            menu.addItem(item)
        }
        if !copies.isEmpty { menu.addItem(.separator()) }
        let item = NSMenuItem(title: Self.revealTitle,
                              action: #selector(reveal), keyEquivalent: "")
        item.target = self
        item.isEnabled = folder != nil
        item.toolTip = folder == nil
            ? "Tile \(coord.key) has no folder yet: build it first." : folder?.path
        menu.addItem(item)
    }

    @objc private func copyItem(_ sender: NSMenuItem) {
        guard copies.indices.contains(sender.tag) else { return }
        PatchClipboard.copy(copies[sender.tag].text)
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
