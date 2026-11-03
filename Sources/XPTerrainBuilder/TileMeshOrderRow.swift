import SwiftUI
import SceneryKit

/// The tile pane's scenery-order warning (#1729; the Qt pane's
/// `O4_Qt_Mesh_Order.MeshOrderRow`, same words and buttons). X-Plane draws
/// a tile's ground from the first pack in its scenery order that ships a
/// base mesh for it: when another pack's mesh is drawn instead of this
/// tile, the row says so and offers "Move Tile Above" / "Disable Scenery";
/// when the tile hides a local mesh (an airport's own ground) it offers
/// "Show Its Ground". Nothing shows while all is well.
///
/// The row only SHOWS a check; `TileMeshOrderTask` on the always-drawn pane
/// asks for it (see `TileMissingTexturesRow` for why).
struct TileMeshOrderRow: View {
    @Binding var order: O4TileMeshOrder?
    /// Make a choice (`raise` / `lower` / `disable` on a pack); the fresh
    /// order, or the refusal sentence.
    let apply: (_ action: String, _ pack: String) async -> Result<O4TileMeshOrder, O4CommandError>

    @State private var refusal: String?

    var body: some View {
        if let order {
            VStack(alignment: .leading, spacing: 4) {
                if let line = order.hiddenByText, let first = order.hiddenBy.first {
                    warning(line, detail: O4MeshOrderCopy.hiddenByDetail)
                    HStack {
                        choice(O4MeshOrderCopy.moveAboveButton, "raise", first)
                        choice(O4MeshOrderCopy.disableButton, "disable", first)
                    }
                }
                if let line = order.hidesText, let last = order.hides.last {
                    warning(line, detail: O4MeshOrderCopy.hidesDetail)
                    choice(O4MeshOrderCopy.showGroundButton, "lower", last)
                }
                if let refusal {
                    Text(refusal)
                        .scaledFont(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private func warning(_ line: String, detail: String) -> some View {
        Label(line, systemImage: "exclamationmark.triangle.fill")
            .scaledFont(.caption)
            .foregroundStyle(.orange)
            .help(detail)
    }

    private func choice(_ title: String, _ action: String, _ pack: String) -> some View {
        Button(title) {
            Task {
                switch await apply(action, pack) {
                case .success(let fresh):
                    refusal = nil
                    order = fresh
                case .failure(let error):
                    refusal = error.message
                }
            }
        }
        .controlSize(.small)
    }
}

/// Asks for the active tile's scenery order whenever `key` changes.
struct TileMeshOrderTask: ViewModifier {
    let key: String
    let load: () async -> O4TileMeshOrder?
    @Binding var order: O4TileMeshOrder?

    func body(content: Content) -> some View {
        content.task(id: key) {
            order = nil           // never show the last tile's answer
            let answer = await load()
            if !Task.isCancelled { order = answer }
        }
    }
}

extension BuildModel {
    /// Re-check when the tile, its folder, a scan or a build changes.
    func tileMeshOrderKey(for coord: TileCoord?, packs: Int) -> String {
        guard let coord else { return "mesh-order|" }
        return "mesh-order|\(coord.key)|\(built[coord]?.buildDir ?? "")|\(built.count)|\(isBuilding)|\(packs)"
    }
}
