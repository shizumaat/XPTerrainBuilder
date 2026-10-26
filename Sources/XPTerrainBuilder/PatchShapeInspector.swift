import SwiftUI
import SceneryKit

/// The Patch box's shape inspector in Edit mode (issue #759, spec §4 as
/// amended 2026-10-15): one shape — role, `ref`, node count, plan area,
/// perimeter, elevation range, "Used by" (other shapes sharing its nodes),
/// "Copy shape reference" (#1281, `PatchCopy.swift`), "Set elevation…"
/// (#1357), "Delete shape"; several — their count and node count, "Set
/// elevation…", "Delete N shapes".
struct PatchShapeInspector: View {
    @ObservedObject var model: PatchEditModel
    let doc: PatchDocument
    @State private var copied = false

    var body: some View {
        let ways = doc.ways.filter { model.shapeSelection.contains($0.id) }
        VStack(alignment: .leading, spacing: 6) {
            if ways.count == 1 {
                single(ways[0])
            } else {
                HStack {
                    Text("\(ways.count.formatted()) shapes").scaledFont(.callout, weight: .semibold)
                    Spacer()
                    Text("\(model.shapeNodes.count.formatted()) nodes").scaledFont(.caption).foregroundStyle(.secondary)
                }
            }
            if !model.selection.isEmpty {
                note("Also \(model.selection.count.formatted()) selected nodes, deleted with the shapes.")
            }
            note("Drag a selected shape to move it; nodes it shares with other shapes move too.")
            Button(PatchSetElevationSheet.title) { model.showsSetElevation = true }
                .help("Give every node of the selected shapes one elevation")
            Button(ways.count == 1 ? "Delete shape" : "Delete \(ways.count.formatted()) shapes", role: .destructive) {
                model.deleteSelection()
            }
        }
        .sheet(isPresented: $model.showsSetElevation) { PatchSetElevationSheet(model: model, doc: doc) }
    }

    @ViewBuilder
    private func single(_ way: PatchWay) -> some View {
        let stats = PatchShapeStats(way: way, in: doc)
        HStack {
            Text(way.roleName ?? "shape").scaledFont(.callout, weight: .semibold)
            Spacer()
            Text("Way \(way.id)").scaledFont(.caption).foregroundStyle(.secondary)
        }
        if let ref = way.tags["ref"] { row("ref", ref) }
        row("Nodes", stats.nodeCount.formatted())
        if way.isClosed { row("Area", "\(Int(stats.area.rounded()).formatted()) m²") }
        row(way.isClosed ? "Perimeter" : "Length", "\(Int(stats.perimeter.rounded()).formatted()) m")
        if let lo = stats.minAlt, let hi = stats.maxAlt {
            row("Elevation", String(format: "%.2f – %.2f m", lo, hi))
        }
        if stats.nodesWithoutElevation > 0 {
            note("\(stats.nodesWithoutElevation.formatted()) nodes: elevation from the mesh.")
        }
        row("Used by", stats.neighbours == 1 ? "1 other shape" : "\(stats.neighbours.formatted()) other shapes")
        HStack(spacing: 6) {
            Button(PatchCopyItem.shapeReferenceTitle) {
                if let text = model.shapeReference(way) { PatchClipboard.copy(text, noting: $copied) }
            }
            .help("Copies a text block that identifies this shape, for an issue report.")
            if copied { Text("Copied").scaledFont(.caption).foregroundStyle(.secondary) }
        }
    }

    private func row(_ key: String, _ value: String) -> some View {
        HStack {
            Text(key).foregroundStyle(.secondary)
            Spacer()
            Text(value).scaledFont(.callout, monospacedDigit: true).textSelection(.enabled)
        }
        .scaledFont(.callout)
    }

    private func note(_ text: String) -> some View {
        Text(text).scaledFont(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
    }
}
