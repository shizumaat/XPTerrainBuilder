import SwiftUI
import SceneryKit

extension BuildModel {
    /// At the start (#2007, RULINGS 2026-11-11a): when no World folder
    /// exists the engine makes it (`world_onboard`), and when tiles could
    /// move into it that were never offered (RULINGS 2026-11-11h (2)) the
    /// onboarding sheet asks once. "Not now" leaves
    /// Settings ▸ Storage ▸ Convert existing tiles to ask again.
    func checkWorldOnboardAtLaunch() {
        guard !worldOnboardChecked,
              engineCapabilities.supports(O4EngineCapabilities.worldOnboard),
              let context = libraryContext(), !context.sceneryDir.isEmpty else { return }
        worldOnboardChecked = true
        let legacy = UserDefaults.standard.string(forKey: Self.legacyBuildDirKey) ?? ""
        Task { @MainActor [weak self] in
            guard let done = try? await context.client.worldOnboard(
                sceneryDir: context.sceneryDir, legacyBuildDir: legacy)
            else { return }
            self?.adoptWorldHome(done.home, legacy: legacy)
            if done.offer > 0 || done.isForeign { self?.worldOnboard = done }
        }
    }

    /// The retired custom build folder setting (RULINGS 2026-11-12g).
    static let legacyBuildDirKey = "OrthoCustomBuildDir"
    /// Its last value, kept once it is handed over (never read again).
    static let legacyBuildDirBackupKey = "OrthoCustomBuildDirBeforeWorld"

    /// Take the engine's tile home; the retired setting is backed up and
    /// cleared once the engine has moved what it named (nothing `left`).
    func adoptWorldHome(_ home: O4WorldHome?, legacy: String) {
        guard let home else { return }
        let before = tileBaseFolder?.path
        if !home.tilesDir.isEmpty { worldTilesDir = home.tilesDir }
        if !legacy.isEmpty, home.active, home.left == 0, home.error == nil {
            let defaults = UserDefaults.standard
            defaults.set(legacy, forKey: Self.legacyBuildDirBackupKey)
            defaults.removeObject(forKey: Self.legacyBuildDirKey)
        }
        if tileBaseFolder?.path != before { rescan() }
    }
}

/// The onboarding: what managing the tiles gives, then Move… (the
/// dry run's numbers first, then Convert…) or Not now. While a step runs
/// Done waits (and the sheet cannot be dismissed): only Cancel ends it;
/// Done comes back with the step's result line (owner 2026-11-11T15:32Z).
/// The Qt window's `O4_Qt_World_Onboard.OnboardDialog` is the same.
struct WorldOnboardSheet: View {
    @EnvironmentObject var buildModel: BuildModel
    let offer: O4WorldOnboard
    @State private var moving = false

    var body: some View {
        if offer.isForeign {
            foreign
        } else {
            AskingContent(offer: offer, moving: $moving, run: buildModel.worldMigrate)
        }
    }

    /// The World folder is not one the app made: the sentence, nothing offered.
    private var foreign: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(offer.foreignText).fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
            HStack {
                Spacer()
                Button(O4WorldOnboardText.done) { buildModel.worldOnboard = nil }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 520)
    }
}

/// The offer and, after Move…, Convert existing tiles with its run.
private struct AskingContent: View {
    @EnvironmentObject var buildModel: BuildModel
    let offer: O4WorldOnboard
    @Binding var moving: Bool
    @ObservedObject var run: WorldMigrateRun

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
                ConvertTilesSection(run: run, measureOnAppear: true)
            }
            HStack {
                Spacer()
                if moving {
                    Button(O4WorldOnboardText.done) { buildModel.worldOnboard = nil }
                        .keyboardShortcut(.defaultAction)
                        .disabled(!WorldOnboardDone.enabled(moving: moving, run: run))
                } else {
                    Button(O4WorldOnboardText.notNow) { buildModel.worldOnboard = nil }
                    Button(O4WorldOnboardText.move) { moving = true }
                        .keyboardShortcut(.defaultAction)
                }
            }
        }
        .padding(20)
        .frame(width: 520)
        .interactiveDismissDisabled(run.isRunning)
    }
}

/// When the sheet's Done is offered: before Move… (Not now stands there),
/// or once the step has finished with its result line.
enum WorldOnboardDone {
    @MainActor
    static func enabled(moving: Bool, run: WorldMigrateRun) -> Bool {
        !moving || (!run.isRunning && run.hasResult)
    }
}
