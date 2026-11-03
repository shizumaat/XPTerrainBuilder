import SwiftUI
import SceneryKit

/// The tile pane's "Imagery check" row (#1666; the Qt pane's
/// `O4_Qt_Imagery_Freshness.ImageryFreshnessRow`, same words — the engine
/// writes the status and its reason). With newer imagery from the tile's
/// source, "Update Imagery" asks first, then removes the tile's downloaded
/// imagery and rebuilds it.
///
/// The row only SHOWS a check; `TileImageryFreshnessTask` on the
/// always-drawn pane asks for it (see `TileMissingTexturesRow` for why).
struct TileImageryFreshnessRow: View {
    let freshness: O4ImageryFreshness?
    /// Update the tile's imagery; a refusal sentence, or nil once queued.
    let update: () async -> String?

    @State private var confirming = false
    @State private var refusal: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text("Imagery check:")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            VStack(alignment: .leading, spacing: 2) {
                Text(freshness?.label ?? "Checking…")
                    .scaledFont(.caption)
                    .foregroundStyle(freshness?.isNewer == true ? Color.orange : Color.primary)
                    .help(freshness?.detail ?? "")
                if freshness?.isNewer == true {
                    Button(O4ImageryFreshnessText.updateTitle) { confirming = true }
                        .controlSize(.small)
                        .help(O4ImageryFreshnessText.updateHelp)
                        .confirmationDialog(O4ImageryFreshnessText.confirmTitle,
                                            isPresented: $confirming) {
                            Button(O4ImageryFreshnessText.updateTitle) {
                                Task { refusal = await update() }
                            }
                            Button("Cancel", role: .cancel) {}
                        } message: {
                            Text(O4ImageryFreshnessText.confirmText)
                        }
                    if let refusal {
                        Text(refusal)
                            .scaledFont(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

/// Asks for the active tile's imagery check whenever `key` changes.
struct TileImageryFreshnessTask: ViewModifier {
    let key: String
    let load: () async -> O4ImageryFreshness?
    @Binding var freshness: O4ImageryFreshness?

    func body(content: Content) -> some View {
        content.task(id: key) {
            freshness = nil           // never show the last tile's answer
            let answer = await load()
            if !Task.isCancelled { freshness = answer }
        }
    }
}
