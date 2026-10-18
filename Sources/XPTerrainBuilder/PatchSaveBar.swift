import SwiftUI
import SceneryKit

/// The Patch box's save bar (patch-editor spec §4, mockup): "● N unsaved
/// edits", "Revert to auto…" with its confirmation INSIDE the pane, Save
/// (⌘S); after a save the re-seating note and "Rebuild tile"; a hand-made
/// patch says it was made outside the editor and has no Revert.
struct PatchSaveBar: View {
    @ObservedObject var model: PatchEditModel
    let doc: PatchDocument
    @StateObject private var confirmingRevert = ViewState(false)

    private var file: String { (doc.path as NSString).lastPathComponent }
    private var n: Int { model.unsavedEdits }
    private var canRevert: Bool { !doc.isHandMade && (doc.source == .manual || n > 0) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if model.tilesNeedingRebuild.contains(doc.tile), n == 0 {
                note(doc.source == .manual
                     ? "The tile is out of date until you rebuild it. Fitting custom airport buildings is off for this airport while the edited ground shape is in use."
                     : "The tile is out of date until you rebuild it.")
                Button("Rebuild tile") { model.rebuildTile() }
                    .disabled(model.build?.isBuilding ?? false)
            }
            if doc.isHandMade {
                note("This airport ground shape was made outside the editor. Saving writes back to \(file); there is no automatic shape to go back to.")
            }
            if confirmingRevert.value { revertConfirmation }
            if let error = model.editError, model.prompt == nil {
                note(error, color: .orange)
            }
            HStack(spacing: 6) {
                if n > 0 {
                    Text("● \(n) unsaved edit\(n == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundStyle(MapCanvasView.buildSelection)
                }
                Spacer(minLength: 4)
                if canRevert, !confirmingRevert.value {
                    Button(O4Glossary.term("undo_edits") + "…") { confirmingRevert.value = true }
                }
                Button(model.isSaving ? "Saving…" : O4Glossary.term("save_edits")) { Task { await model.save() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(n == 0 || model.isSaving)
                    .help("Save your edits to the airport ground shape (⌘S)")
            }
        }
        .onChange(of: doc.path) { confirmingRevert.value = false }
    }

    private var revertConfirmation: some View {
        VStack(alignment: .leading, spacing: 6) {
            if doc.source == .manual {
                note("Go back to the automatic ground shape? \(file) is moved aside to \(file).disabled (not deleted), and the next build of this tile uses the automatic shape."
                     + (n > 0 ? " Your \(n) unsaved edit\(n == 1 ? " is" : "s are") discarded." : ""))
            } else {
                note("Discard your \(n) unsaved edit\(n == 1 ? "" : "s") and reload the automatic ground shape?")
            }
            HStack {
                Spacer()
                Button("Cancel") { confirmingRevert.value = false }
                Button(doc.source == .manual ? "Undo my edits" : "Discard edits", role: .destructive) {
                    confirmingRevert.value = false
                    Task { await model.revertToAuto() }
                }
            }
        }
        .padding(8)
        .background(.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 6))
    }

    private func note(_ text: String, color: Color = .secondary) -> some View {
        Text(text).font(.caption).foregroundStyle(color).fixedSize(horizontal: false, vertical: true)
    }
}

/// The unsaved-edits question on the map, before switching airport or
/// quitting (in-app, no alert).
struct PatchUnsavedPromptCard: View {
    @ObservedObject var model: PatchEditModel

    var body: some View {
        if let prompt = model.prompt, let doc = model.document {
            let n = model.unsavedEdits
            let edits = "\(n) unsaved edit\(n == 1 ? "" : "s")"
            VStack(alignment: .leading, spacing: 8) {
                Text("Unsaved edits to \(doc.icao)").font(.headline)
                Text(message(prompt, doc: doc, edits: edits)).font(.callout).fixedSize(horizontal: false, vertical: true)
                if let error = model.editError {
                    Text(error).font(.caption).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                }
                HStack {
                    Button(prompt == .quit ? "Cancel" : "Keep Editing") { model.answerPrompt(save: nil) }
                        .keyboardShortcut(.cancelAction)
                    Spacer()
                    Button("Don't Save", role: .destructive) { model.answerPrompt(save: false, discard: true) }
                    Button("Save") { model.answerPrompt(save: true) }
                        .keyboardShortcut(.defaultAction)
                        .disabled(model.isSaving)
                }
            }
            .padding(14)
            .frame(width: 380)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
            .shadow(radius: 12)
            .padding(.top, 56)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
    }

    private func message(_ prompt: PatchEditModel.UnsavedPrompt, doc: PatchDocument, edits: String) -> String {
        switch prompt {
        case .quit:
            return "Save your \(edits) before quitting?"
        case .switchAirport(let icao, _):
            return icao == doc.icao
                ? "\(doc.icao)'s ground shape changed on disk. Save your \(edits) before reloading it?"
                : "Save your \(edits) before showing \(icao)?"
        }
    }
}

/// File ▸ Save my edits (⌘S) — the airport ground shape.
struct PatchSaveCommand: View {
    @ObservedObject var model: PatchEditModel

    var body: some View {
        Button(O4Glossary.term("save_edits")) { Task { await model.save() } }
            .keyboardShortcut("s", modifiers: .command)
            .disabled(model.unsavedEdits == 0 || model.isSaving)
    }
}
