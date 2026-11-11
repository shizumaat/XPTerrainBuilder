import SwiftUI
import SceneryKit

extension BuildModel {
    /// At the start (#2007, RULINGS 2026-11-11a): when no World folder
    /// exists the engine makes it (`world_onboard`), and when tiles could
    /// move into it the onboarding sheet asks once. "Not now" leaves
    /// Library ▸ Convert existing tiles to ask again.
    func checkWorldOnboardAtLaunch() {
        guard !worldOnboardChecked,
              engineCapabilities.supports(O4EngineCapabilities.worldOnboard),
              let context = libraryContext(), !context.sceneryDir.isEmpty else { return }
        worldOnboardChecked = true
        Task { @MainActor [weak self] in
            guard let done = try? await context.client.worldOnboard(sceneryDir: context.sceneryDir)
            else { return }
            if done.created, done.offer > 0 { self?.worldOnboard = done }
        }
    }
}

/// The onboarding: what managing the tiles gives, then Move… (the
/// dry run's numbers first, then Convert…) or Not now. The Qt window's
/// `O4_Qt_World_Onboard.OnboardDialog` is the same.
struct WorldOnboardSheet: View {
    @EnvironmentObject var buildModel: BuildModel
    let offer: O4WorldOnboard
    @State private var moving = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(O4WorldOnboardText.title).font(.title3.weight(.semibold))
            Text(O4WorldOnboardText.introText(offer.offer))
                .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 6) {
                ForEach(O4WorldOnboardText.advantageLines, id: \.self) { line in
                    Label(line, systemImage: "checkmark.circle")
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Text(O4WorldOnboardText.note).scaledFont(.caption).foregroundStyle(.secondary)
            if moving {
                Divider()
                ConvertTilesSection(measureOnAppear: true)
            }
            HStack {
                Spacer()
                if moving {
                    Button(O4WorldOnboardText.done) { buildModel.worldOnboard = nil }
                        .keyboardShortcut(.defaultAction)
                } else {
                    Button(O4WorldOnboardText.notNow) { buildModel.worldOnboard = nil }
                    Button(O4WorldOnboardText.move) { moving = true }
                        .keyboardShortcut(.defaultAction)
                }
            }
        }
        .padding(20)
        .frame(width: 520)
    }
}
