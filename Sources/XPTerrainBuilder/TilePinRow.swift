import SwiftUI
import SceneryKit

/// The tile pane's "Resolution" row of an on-demand or pinned tile
/// (#1992 §7; the Qt pane's `O4_Qt_Imagery_OnDemand.TilePinRow`, same
/// words): its state and "Always keep full resolution" / "Let it go
/// low-res again" (engine `imagery_pin`).
struct TilePinRow: View {
    let pinned: Bool
    /// Pin or unpin; a sentence for the user (the reply or the refusal).
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
                Text(pinned ? O4OnDemandText.pinnedState : O4OnDemandText.lowResState)
                    .scaledFont(.caption)
                    .help(O4OnDemandText.pinHelp)
                Button(pinned ? O4OnDemandText.unpinTitle : O4OnDemandText.pinTitle) {
                    working = true
                    Task {
                        note = await setPinned(!pinned)
                        working = false
                    }
                }
                .controlSize(.small)
                .disabled(working)
                .help(O4OnDemandText.pinHelp)
                if let note {
                    Text(note).scaledFont(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        .onChange(of: pinned) { _, _ in note = nil }
    }
}
