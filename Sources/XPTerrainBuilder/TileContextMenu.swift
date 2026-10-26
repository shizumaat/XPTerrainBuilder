import AppKit
import SceneryKit

/// The map's tile right-click menu (#938; Qt O4_Qt_Tile_Menu): Show in
/// Finder, which reveals the tile's folder (greyed out while the tile has
/// none yet). The patch editor's items for its selection come first
/// (`extra`: "Set elevation…" on selected shapes, #1357). The menu's items
/// target this object, so the caller keeps it alive while the menu is open.
@MainActor
final class TileContextMenu: NSObject {
    static let revealTitle = "Show in Finder"

    let folder: URL?
    let menu = NSMenu()
    private let extra: [(title: String, run: () -> Void)]

    init(coord: BuildModel.TileCoord, folder: URL?, extra: [(title: String, run: () -> Void)] = []) {
        self.folder = folder
        self.extra = extra
        super.init()
        menu.autoenablesItems = false
        for (index, entry) in extra.enumerated() {
            let item = NSMenuItem(title: entry.title, action: #selector(runExtra(_:)), keyEquivalent: "")
            item.target = self
            item.tag = index
            menu.addItem(item)
        }
        if !extra.isEmpty { menu.addItem(.separator()) }
        let item = NSMenuItem(title: Self.revealTitle,
                              action: #selector(reveal), keyEquivalent: "")
        item.target = self
        item.isEnabled = folder != nil
        item.toolTip = folder == nil
            ? "Tile \(coord.key) has no folder yet: build it first." : folder?.path
        menu.addItem(item)
    }

    @objc private func runExtra(_ sender: NSMenuItem) { extra[sender.tag].run() }

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
