import SwiftUI
import SceneryKit

/// The first-visit hint over the map (issue #828): "Search your airport,
/// or click its square on the map", pointing up at the toolbar search
/// field. Dismissed for good by the first selection or its close button
/// (SceneryKit `MapGuidance`, the rule the Qt window shares);
/// Help ▸ Show Tips brings it back.
struct MapHintOverlay: View {
    @EnvironmentObject var buildModel: BuildModel
    @AppStorage(PrefKeys.mapHintDismissed) private var dismissed = false

    var body: some View {
        ZStack {
            // Always in the hierarchy, so the selection observer below
            // keeps running while the hint is hidden.
            Color.clear.frame(width: 1, height: 1)
            if !dismissed { hint }
        }
        .onChange(of: buildModel.selected.isEmpty) { _, isEmpty in
            apply(isEmpty ? .deselected : .selected)
        }
    }

    private var hint: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
            Text(MapGuidance.hintText)
                .font(.callout.weight(.medium))
            Image(systemName: "arrow.up.right")
                .help("The search field is at the top right of the window")
            Button {
                apply(.closed)
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.borderless)
            .help("Hide this tip (Help ▸ \(MapGuidance.showTipsTitle) brings it back)")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(.regularMaterial, in: Capsule())
        .shadow(radius: 4)
        .padding(.top, 14)
    }

    private func apply(_ event: MapGuidance.Event) {
        dismissed = MapGuidance.dismissed(after: event, from: dismissed)
    }
}
