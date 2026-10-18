import SwiftUI
import SceneryKit

/// The Patch box's node inspector in Edit mode (patch-editor spec §4,
/// mockup): one node — lat/lon, the elevation field (m, with ft and the
/// loaded value), "Used by", Delete; several — the elevation range, "Set
/// to", "Offset", Delete N.
struct PatchNodeInspector: View {
    @ObservedObject var model: PatchEditModel
    let doc: PatchDocument
    @StateObject private var altText = ViewState("")
    @StateObject private var setText = ViewState("")
    @StateObject private var offsetText = ViewState("")

    static let feetPerMetre = 3.280839895

    var body: some View {
        let ids = model.selection.sorted()
        VStack(alignment: .leading, spacing: 6) {
            if ids.isEmpty {
                note("Click a node or a line to select it (a line selects its whole shape); ⇧-click or ⇧-drag to select several.")
            } else if ids.count == 1, let node = doc.nodes[ids[0]] {
                single(node)
            } else {
                multi(ids)
            }
        }
    }

    // MARK: - One node

    @ViewBuilder
    private func single(_ node: PatchNode) -> some View {
        HStack {
            Text("Node \(node.id)").scaledFont(.callout, weight: .semibold)
            Spacer()
            Text("1 selected").scaledFont(.caption).foregroundStyle(.secondary)
        }
        row("lat", String(format: "%.9f", node.lat))
        row("lon", String(format: "%.9f", node.lon))
        HStack(spacing: 6) {
            Text("Elevation").foregroundStyle(.secondary)
            TextField(node.alt == nil ? "from the mesh" : "", text: $altText.value)
                .textFieldStyle(.roundedBorder)
                .scaledFont(.callout, monospacedDigit: true)
                .onSubmit { if let v = Self.number(altText.value) { model.setSelectionAlt(v) } }
            Text("m").foregroundStyle(.secondary)
        }
        .scaledFont(.callout)
        .onAppear { altText.value = Self.metres(node.alt) }
        .onChange(of: node) { altText.value = Self.metres(node.alt) }
        note(elevationNote(node))
        let roles = Set(doc.waysUsing(node.id).compactMap(\.roleName)).sorted()
        if !roles.isEmpty {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("Used by").foregroundStyle(.secondary).scaledFont(.callout)
                Text(roles.joined(separator: ", ")).scaledFont(.callout).fixedSize(horizontal: false, vertical: true)
            }
        }
        Button("Delete node", role: .destructive) { model.deleteSelection() }
    }

    private func elevationNote(_ node: PatchNode) -> String {
        var parts: [String] = []
        if let alt = node.alt { parts.append(String(format: "%.1f ft", alt * Self.feetPerMetre)) }
        if let loaded = model.loadedNodes[node.id] {
            parts.append("was " + (loaded.alt.map { String(format: "%.2f m", $0) } ?? "from the mesh"))
        } else {
            parts.append("new node")
        }
        return parts.joined(separator: " · ")
    }

    // MARK: - Several nodes

    @ViewBuilder
    private func multi(_ ids: [Int64]) -> some View {
        let alts = ids.compactMap { doc.nodes[$0]?.alt }
        HStack {
            Text("\(ids.count.formatted()) nodes").scaledFont(.callout, weight: .semibold)
            Spacer()
            if let lo = alts.min(), let hi = alts.max() {
                Text(String(format: "%.2f – %.2f m", lo, hi)).scaledFont(.callout, monospacedDigit: true)
            }
        }
        if alts.count < ids.count {
            note("\((ids.count - alts.count).formatted()) of them take their elevation from the mesh; Offset leaves those alone.")
        }
        field("Set to", text: $setText.value, placeholder: "—") { model.setSelectionAlt($0) }
        field("Offset", text: $offsetText.value, placeholder: "+0.50") { model.offsetSelectionAlt($0) }
        Button("Delete \(ids.count.formatted()) nodes", role: .destructive) { model.deleteSelection() }
    }

    private func field(_ label: String, text: Binding<String>, placeholder: String,
                       apply: @escaping (Double) -> Void) -> some View {
        HStack(spacing: 6) {
            Text(label).foregroundStyle(.secondary).frame(width: 48, alignment: .leading)
            TextField(placeholder, text: text)
                .textFieldStyle(.roundedBorder)
                .scaledFont(.callout, monospacedDigit: true)
                .onSubmit { if let v = Self.number(text.wrappedValue) { apply(v) } }
            Text("m").foregroundStyle(.secondary)
            Button("Apply") { if let v = Self.number(text.wrappedValue) { apply(v) } }
                .disabled(Self.number(text.wrappedValue) == nil)
        }
        .scaledFont(.callout)
    }

    // MARK: - Helpers

    static func number(_ text: String) -> Double? {
        Double(text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "."))
    }

    static func metres(_ alt: Double?) -> String { alt.map { String(format: "%.2f", $0) } ?? "" }

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
