import AppKit
import SceneryKit

/// The map's tile right-click menu (#938; Qt O4_Qt_Tile_Menu): Show in
/// Finder, which reveals the tile's folder, or its DSF in the World pack
/// when the folder holds only records (#2027, `tileRevealURL`); greyed
/// out while the tile has none yet. It comes after the patch layer's copy items when there are any
/// (#1281, `PatchCopy.swift`: "Copy coordinates" anywhere, #1314) and its
/// actions (`extra`: "Set elevation…" on selected shapes, #1357; "Insert
/// shape" and "Insert tunnel ramp" at the click, #1314 / #1745,
/// `PatchInsertShape.swift`). In patch Edit mode the menu
/// starts with Slice (#1318; Qt `PatchEditor.add_to_menu`), enabled only
/// for two nodes of one shape that are not neighbours, then "Duplicate
/// shape" (#1963), enabled with a shape selected. "Export Package…" ends
/// it (#2014): the File menu's action for the selection, or the clicked
/// tile when it is not selected. The menu's items
/// target this object, so the caller keeps it alive while the menu is open.
@MainActor
final class TileContextMenu: NSObject {
    static let revealTitle = "Show in Finder"
    /// File ▸ Export Package… for the clicked tile or the selection (#2014).
    static let exportPackageTitle = O4TilePackageCopy.exportTitle
    static let sliceTitle = "Slice"
    /// "Duplicate shape" (#1963; Qt `DUPLICATE_SHAPE_TITLE`), after Slice.
    static let duplicateShapeTitle = "Duplicate shape"
    static let duplicateShapeRefusal = "Select a shape to duplicate."
    /// The patch editor's "Insert shape" (#1314; Qt `INSERT_SHAPE_TITLE`).
    static let insertShapeTitle = "Insert shape"
    /// "Insert tunnel ramp" (#1745; Qt `INSERT_RAMP_TITLE`).
    static let insertTunnelRampTitle = "Insert tunnel ramp"

    let folder: URL?
    let copies: [PatchCopyItem]
    let menu = NSMenu()
    private weak var patch: PatchEditModel?
    private let extra: [(title: String, run: () -> Void)]
    private let exportPackage: (() -> Void)?

    init(coord: BuildModel.TileCoord, folder: URL?, copies: [PatchCopyItem] = [],
         patch: PatchEditModel? = nil, extra: [(title: String, run: () -> Void)] = [],
         exportPackage: (() -> Void)? = nil) {
        self.folder = folder
        self.copies = copies
        self.extra = extra
        self.exportPackage = exportPackage
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
            let duplicate = NSMenuItem(title: Self.duplicateShapeTitle, action: #selector(duplicateShape),
                                       keyEquivalent: "")
            duplicate.target = self
            if patch.shapeSelection.isEmpty {
                duplicate.isEnabled = false
                duplicate.toolTip = Self.duplicateShapeRefusal
            }
            menu.addItem(duplicate)
            menu.addItem(.separator())
        }
        for (k, copy) in copies.enumerated() {
            let item = NSMenuItem(title: copy.title, action: #selector(copyItem(_:)), keyEquivalent: "")
            item.target = self
            item.tag = k
            menu.addItem(item)
        }
        if !copies.isEmpty { menu.addItem(.separator()) }
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
        if exportPackage != nil {
            let export = NSMenuItem(title: Self.exportPackageTitle, action: #selector(runExport),
                                    keyEquivalent: "")
            export.target = self
            menu.addItem(export)
        }
    }

    @objc private func runExport() {
        exportPackage?()
    }

    @objc private func sliceShape() {
        patch?.sliceSelection()
    }

    @objc private func duplicateShape() {
        patch?.duplicateShapes()
    }

    @objc private func copyItem(_ sender: NSMenuItem) {
        guard copies.indices.contains(sender.tag) else { return }
        PatchClipboard.copy(copies[sender.tag].text)
    }

    @objc private func runExtra(_ sender: NSMenuItem) {
        guard extra.indices.contains(sender.tag) else { return }
        extra[sender.tag].run()
    }

    @objc private func reveal() {
        guard let folder else { return }
        NSWorkspace.shared.activateFileViewerSelecting([folder])
    }
}

extension BuildModel {
    /// What "Show in Finder" reveals (#2027): the tile's DSF in the World
    /// pack when its build folder holds only records (an adopted or
    /// converted tile; `O4WorldTile.revealDSF`), else `tileFolder`.
    func tileRevealURL(_ coord: TileCoord) -> URL? {
        if let dsf = worldTiles[coord]?.revealDSF(built[coord]),
           FileManager.default.fileExists(atPath: dsf) {
            return URL(fileURLWithPath: dsf, isDirectory: false)
        }
        return tileFolder(coord)
    }

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
