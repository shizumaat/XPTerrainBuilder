import SwiftUI
import SceneryKit

/// The Patch box's shape inspector in Edit mode (issue #759, spec §4 as
/// amended 2026-10-15): one shape — role, `ref`, node count, plan area,
/// perimeter, elevation range, "Used by" (other shapes sharing its nodes),
/// "Delete shape"; several — their count and node count, "Delete N shapes".
struct PatchShapeInspector: View {
    @ObservedObject var model: PatchEditModel
    let doc: PatchDocument

    var body: some View {
        let ways = doc.ways.filter { model.shapeSelection.contains($0.id) }
        VStack(alignment: .leading, spacing: 6) {
            if ways.count == 1 {
                single(ways[0])
            } else {
                HStack {
                    Text("\(ways.count.formatted()) shapes").font(.callout.weight(.semibold))
                    Spacer()
                    Text("\(model.shapeNodes.count.formatted()) nodes").font(.caption).foregroundStyle(.secondary)
                }
            }
            if !model.selection.isEmpty {
                note("Also \(model.selection.count.formatted()) selected nodes, deleted with the shapes.")
            }
            note("Drag a selected shape to move it; nodes it shares with other shapes move too.")
            Button(ways.count == 1 ? "Delete shape" : "Delete \(ways.count.formatted()) shapes", role: .destructive) {
                model.deleteSelection()
            }
        }
    }

    @ViewBuilder
    private func single(_ way: PatchWay) -> some View {
        let stats = PatchShapeStats(way: way, in: doc)
        HStack {
            Text(way.roleName ?? "shape").font(.callout.weight(.semibold))
            Spacer()
            Text("Way \(way.id)").font(.caption).foregroundStyle(.secondary)
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
    }

    private func row(_ key: String, _ value: String) -> some View {
        HStack {
            Text(key).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.callout.monospacedDigit()).textSelection(.enabled)
        }
        .font(.callout)
    }

    private func note(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
    }
}
