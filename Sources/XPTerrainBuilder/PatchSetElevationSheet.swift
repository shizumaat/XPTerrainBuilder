import SwiftUI
import SceneryKit

/// "Set elevation…" for the selected patch shapes (issue #1357; Qt's
/// `O4_Qt_Patch_Elevation_Dialog`). It states first what the edit touches
/// ("N shared nodes, M neighbouring shapes affected"), then takes one value
/// in m or ft, prefilled with the selection's mean `alt_abs`. "Also set
/// shared nodes" is on by default. Apply is ONE undoable edit, saved
/// through the normal path.
struct PatchSetElevationSheet: View {
    static let title = "Set elevation…"

    @ObservedObject var model: PatchEditModel
    let plan: PatchShapeElevation
    @State private var text = ""
    @State private var unit: PatchShapeElevation.Unit = .metres
    @State private var includeShared = true

    init(model: PatchEditModel, doc: PatchDocument) {
        let plan = PatchShapeElevation(shapes: model.shapeSelection, in: doc)
        self.model = model
        self.plan = plan
        _text = State(initialValue: Self.format(plan.meanAlt, in: .metres))
    }

    var body: some View {
        let n = model.shapeSelection.count
        VStack(alignment: .leading, spacing: 10) {
            Text(n == 1 ? "1 shape" : "\(n.formatted()) shapes").scaledFont(.callout, weight: .semibold)
            Text(plan.summary(includeShared: includeShared)).scaledFont(.callout)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 6) {
                Text("Elevation").foregroundStyle(.secondary)
                TextField("", text: $text)
                    .textFieldStyle(.roundedBorder)
                    .scaledFont(.callout, monospacedDigit: true)
                    .frame(width: 110)
                    .onSubmit(apply)
                Picker("", selection: $unit) {
                    ForEach(PatchShapeElevation.Unit.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(width: 80)
            }
            Toggle("Also set shared nodes (they move the neighbouring shapes)", isOn: $includeShared)
            if plan.meanAlt == nil {
                Text("These nodes take their elevation from the mesh today.").foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button("Cancel", role: .cancel) { model.showsSetElevation = false }
                    .keyboardShortcut(.cancelAction)
                Button("Apply", action: apply)
                    .keyboardShortcut(.defaultAction)
                    .disabled(PatchNodeInspector.number(text) == nil)
            }
        }
        .padding(20)
        .frame(width: 380)
        .onChange(of: unit) { old, new in
            // Keep the typed value: convert it into the new unit.
            let metres = PatchNodeInspector.number(text).map { PatchShapeElevation.metres($0, from: old) }
            text = Self.format(metres, in: new)
        }
    }

    private func apply() {
        guard let v = PatchNodeInspector.number(text) else { return }
        model.setShapesAlt(PatchShapeElevation.metres(v, from: unit), includeShared: includeShared)
        model.showsSetElevation = false
    }

    private static func format(_ metres: Double?, in unit: PatchShapeElevation.Unit) -> String {
        metres.map { String(format: "%.2f", PatchShapeElevation.value($0, in: unit)) } ?? ""
    }
}
