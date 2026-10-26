import AppKit
import SwiftUI
import SceneryKit

/// What the patch layer copies for an issue report (#1281; Qt
/// `O4_Qt_Patch_Reference` and `PatchEditor.add_copy_actions`): a node's
/// `lat, lon` (9 decimals) and a selected shape's reference block
/// (`PatchShapeReference`). The map's right-click menu offers them in View
/// and Edit mode; the inspectors' coordinates and "Copy shape reference"
/// button copy the same text.
enum PatchClipboard {
    static func copy(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    /// How long a "Copied" note stays.
    static let copiedNoteSeconds = 1.5

    /// Copy, and raise `copied` (the view's "Copied" note) for
    /// `copiedNoteSeconds`.
    @MainActor
    static func copy(_ text: String, noting copied: Binding<Bool>) {
        copy(text)
        copied.wrappedValue = true
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(copiedNoteSeconds))
            copied.wrappedValue = false
        }
    }
}

/// One right-click menu item: its title and the text it copies.
struct PatchCopyItem: Equatable {
    static let coordinatesTitle = "Copy coordinates"
    static let shapeReferenceTitle = "Copy shape reference"

    let title: String
    let text: String
}

extension PatchEditModel {
    /// The engine version a shape reference names (the hello's, else the
    /// config schema's).
    var engineVersion: String {
        guard let build else { return "" }
        return build.protocolHello?.version ?? build.schema.engineVersion
    }

    /// The reference block for one shape of the open document.
    func shapeReference(_ way: PatchWay) -> String? {
        guard let document else { return nil }
        return PatchShapeReference.text(for: way, in: document, engineVersion: engineVersion)
    }

    /// The copy items for a right-click at `p` on the map: "Copy
    /// coordinates" on a node (8 pt), "Copy shape reference" while one
    /// shape is selected. None while the patch layer is hidden.
    func copyItems(at p: CGPoint, camera: MapCamera, size: CGSize) -> [PatchCopyItem] {
        guard isShowing, let doc = document, let grid else { return [] }
        var items: [PatchCopyItem] = []
        let screen = PatchEditScreen(doc: doc, camera: camera, size: size)
        if let id = screen.nodeHit(at: p, grid: grid), let node = doc.nodes[id] {
            items.append(PatchCopyItem(title: PatchCopyItem.coordinatesTitle,
                                       text: PatchNodeInspector.latLon(lat: node.lat, lon: node.lon)))
        }
        if shapeSelection.count == 1, let way = doc.ways.first(where: { shapeSelection.contains($0.id) }),
           let text = shapeReference(way) {
            items.append(PatchCopyItem(title: PatchCopyItem.shapeReferenceTitle, text: text))
        }
        return items
    }
}
