import SwiftUI

/// The map's patch toolbar (mockup, top left): the View | Edit segmented
/// control and Undo / Redo. Shown while the patch layer is drawn.
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
