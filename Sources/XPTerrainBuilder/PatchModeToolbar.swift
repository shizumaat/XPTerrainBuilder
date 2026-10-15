import SwiftUI

/// The map's patch toolbar (mockup, top left): the View | Edit segmented
/// control, Undo / Redo and the "Pack outlines" check box. Shown while the patch layer is drawn.
struct PatchModeToolbar: View {
    @ObservedObject var model: PatchEditModel

    var body: some View {
        if model.isShowing {
            HStack(spacing: 6) {
                Picker("", selection: $model.mode) {
                    ForEach(PatchEditModel.Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .fixedSize()
                .help("View the patch, or edit its nodes.")
                Divider().frame(height: 16)
                Button { model.undoManager?.undo() } label: { Image(systemName: "arrow.uturn.backward") }
                    .disabled(!(model.undoManager?.canUndo ?? false))
                    .help(model.undoManager?.undoMenuItemTitle ?? "Undo")
                Button { model.undoManager?.redo() } label: { Image(systemName: "arrow.uturn.forward") }
                    .disabled(!(model.undoManager?.canRedo ?? false))
                    .help(model.undoManager?.redoMenuItemTitle ?? "Redo")
                if let outlines = model.build?.packOutlines {
                    Divider().frame(height: 16)
                    PackOutlinesToggle(outlines: outlines)
                }
            }
            .buttonStyle(.borderless)
            .padding(.horizontal, 6).padding(.vertical, 3)
            .background(.black.opacity(0.45), in: RoundedRectangle(cornerRadius: 8))
            .padding(.vertical, 8)
            .onChange(of: model.mode) {
                if model.mode == .view { model.drag.hoverEdge = nil }
            }
        }
    }
}

/// Shows or hides the pack's own apt.dat pavement, boundary and building
/// outlines under the patch (remembered per user, on by default).
private struct PackOutlinesToggle: View {
    @ObservedObject var outlines: PatchPackOutlines

    var body: some View {
        Toggle("Pack outlines", isOn: $outlines.enabled)
            .toggleStyle(.checkbox)
            .help(help)
    }

    private var help: String {
        let base = "Show the airport pack's own pavement, boundary and building outlines "
            + "(dashed) under the patch, for reference."
        return outlines.missing.isEmpty ? base : base + "\n\n" + outlines.missing.joined(separator: "\n")
    }
}
