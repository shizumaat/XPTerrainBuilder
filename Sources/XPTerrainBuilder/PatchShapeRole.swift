import SwiftUI
import SceneryKit

// A shape's classification by hand (#1697; Qt's `O4_Qt_Patch_Role`):
//
// In Edit mode one selected shape that belongs to a pack pavement (its
// `ref` is `pav<N>`) shows "Classification" — the role it was built with —
// and a menu of the pavement roles. A choice is stored at once by the
// engine (`patch_role_set`) beside the patch, keyed by the pavement's
// apt.dat ring: a user edit the classifier honours on every rebuild
// (RULINGS 2026-10-15d), so the next build regrades the whole airport
// with it. One ⌘Z step, which is not an unsaved patch edit. "Automatic"
// hands the shape back to the classifier.

/// The Patch box's "Classification" row for one selected shape.
struct PatchShapeRoleBox: View {
    @ObservedObject var model: PatchEditModel
    let doc: PatchDocument
    let way: PatchWay
    @State private var roles: O4PatchRoles?

    static let title = "Classification"

    private var source: String? { O4PatchRoles.source(ofRef: way.tags["ref"]) }
    private var supported: Bool {
        O4ProtocolVersion.supportsPatchRoles(model.build?.protocolHello?.protocolVersion ?? "")
    }

    var body: some View {
        if supported, source != nil {
            content.task(id: "\(doc.tile) \(doc.icao)") { await reload() }
        }
    }

    @ViewBuilder
    private var content: some View {
        let built = way.tags["role"] ?? ""
        let hand = roles?.override(forRef: way.tags["ref"])
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(Self.title).foregroundStyle(.secondary)
                Spacer()
                Menu(label(hand?.role ?? built)) {
                    ForEach(roles?.choices ?? [], id: \.self) { choice in
                        Button(choice.label) { set(choice.role, built: built, hand: hand) }
                            .disabled(choice.role == (hand?.role ?? built))
                    }
                    if hand != nil {
                        Divider()
                        Button("Automatic") { set(nil, built: built, hand: hand) }
                    }
                }
                .fixedSize()
                .disabled(roles == nil)
                .help("Change what this pavement is; the whole airport is regraded with it on the next rebuild")
            }
            .scaledFont(.callout)
            if let hand {
                note(hand.role == built
                     ? "Set by hand (the classifier said \(label(hand.was)))."
                     : "Set by hand: \(label(hand.role)). Rebuild the tile to regrade the airport with it.")
                if doc.source == .manual {
                    note("The edited ground shape is in use, so the build uses it instead until you go back to the automatic shape.")
                }
            }
        }
    }

    private func label(_ role: String) -> String {
        roles?.choices.first { $0.role == role }?.label ?? (role.isEmpty ? "shape" : role)
    }

    private func note(_ text: String) -> some View {
        Text(text).scaledFont(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
    }

    private func reload() async {
        guard let client = model.build?.patchEditorClient() else { return }
        roles = try? await client.patchRoles(tile: doc.tile, icao: doc.icao)
    }

    /// Store `role` (nil: back to the classifier) for the shape's pavement;
    /// ONE undo step.
    private func set(_ role: String?, built: String, hand: O4PatchRoles.Override?) {
        guard let ref = way.tags["ref"] else { return }
        let was = hand?.was ?? built
        send(ref: ref, role: role, was: was, name: role == nil ? "Automatic Classification" : "Change Classification",
             registering: true)
    }

    private func send(ref: String, role: String?, was: String, name: String, registering: Bool) {
        guard let client = model.build?.patchEditorClient() else { return }
        let tile = doc.tile, icao = doc.icao
        Task { @MainActor in
            do {
                let reply = try await client.patchRoleSet(tile: tile, icao: icao, ref: ref, role: role, was: was)
                model.tilesNeedingRebuild.insert(tile)
                if registering { registerUndo(ref: ref, to: reply.previousRole, back: reply.role, was: was, name: name) }
                await reload()
            } catch {
                model.editError = "The shape's classification could not be changed: \(error)"
            }
        }
    }

    /// Undo / redo: send `to`, and register the way back.
    private func registerUndo(ref: String, to: String?, back: String?, was: String, name: String) {
        guard let undo = model.undoManager else { return }
        undo.registerUndo(withTarget: model) { _ in
            MainActor.assumeIsolated {
                registerUndo(ref: ref, to: back, back: to, was: was, name: name)
                send(ref: ref, role: to, was: was, name: name, registering: false)
            }
        }
        undo.setActionName(name)
    }
}
