import SwiftUI
import SceneryKit

/// The tile pane's "Favorite" row (#1992 §7; "pin" renamed Favorite,
/// RULINGS 2026-11-10c (1); the Qt pane's `O4_Qt_Imagery_OnDemand.TilePinRow`,
/// same words): a switch that makes the tile a favorite (engine
/// `imagery_pin`). Shown on every built tile; the switch works on a tile
/// built with imagery on demand (or already a favorite), and says why not
/// on the others.
struct TilePinRow: View {
    let pinned: Bool
    /// Can the tile be a favorite (built on demand, or already one)?
    let applies: Bool
    /// Favorite or not; a sentence for the user (the reply or the refusal).
    let setPinned: (Bool) async -> String

    @State private var working = false
    @State private var note: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(O4OnDemandText.pinRowTitle + ":")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            VStack(alignment: .leading, spacing: 2) {
                Toggle(isOn: Binding(get: { pinned }, set: { wanted in
                    working = true
                    Task {
                        note = await setPinned(wanted)
                        working = false
                    }
                })) {
                    Text(!applies ? O4OnDemandText.notOnDemandState
                         : pinned ? O4OnDemandText.pinnedState : O4OnDemandText.lowResState)
                        .scaledFont(.caption)
                }
                .toggleStyle(.switch)
                .controlSize(.mini)
                .disabled(working || !applies)
                .help(O4OnDemandText.pinHelp)
                .accessibilityLabel(O4OnDemandText.pinRowTitle)
                if let note {
                    Text(note).scaledFont(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        .onChange(of: pinned) { _, _ in note = nil }
    }
}
