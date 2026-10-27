import AppKit
import SwiftUI
import SceneryKit

/// What the patch layer copies for an issue report (#1281; Qt
/// `O4_Qt_Patch_Reference` and `PatchEditor.add_copy_actions`): a node's
/// `lat, lon` (9 decimals; the click's own anywhere on the map, #1314) and
/// a selected shape's reference block (`PatchShapeReference`). The map's
/// right-click menu offers them in View and Edit mode; the inspectors'
/// coordinates and "Copy shape reference" button copy the same text.
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
    /// coordinates" of a node (8 pt), else of the click (#1314); "Copy
    /// shape reference" while one shape is selected and the layer shows.
    func copyItems(at p: CGPoint, camera: MapCamera, size: CGSize) -> [PatchCopyItem] {
        let click = camera.coordinate(of: p, in: size)
        var at = (lat: click.lat, lon: click.lon)
        guard isShowing, let doc = document, let grid else {
            return [PatchCopyItem(title: PatchCopyItem.coordinatesTitle,
                                  text: PatchNodeInspector.latLon(lat: at.lat, lon: at.lon))]
        }
        let screen = PatchEditScreen(doc: doc, camera: camera, size: size)
        if let id = screen.nodeHit(at: p, grid: grid), let node = doc.nodes[id] {
            at = (node.lat, node.lon)
        }
        var items = [PatchCopyItem(title: PatchCopyItem.coordinatesTitle,
                                   text: PatchNodeInspector.latLon(lat: at.lat, lon: at.lon))]
        if shapeSelection.count == 1, let way = doc.ways.first(where: { shapeSelection.contains($0.id) }),
           let text = shapeReference(way) {
            items.append(PatchCopyItem(title: PatchCopyItem.shapeReferenceTitle, text: text))
        }
        return items
    }
}
