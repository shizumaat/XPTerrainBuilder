import SwiftUI
import SceneryKit

/// Settings ▸ Storage ▸ Convert existing tiles (World spec §13 M1, §14
/// `ConvertTilesSection`; Qt: `O4_Qt_Convert_Tiles.ConvertTilesSection`):
/// the per-tile `zOrtho4XP_` packs moved into the World pack through the
/// engine's `world_migrate` — Measure (the dry run), Convert…, Cancel and
/// Undo…. While a step runs a bar counts the tiles (owner
/// 2026-11-11T15:32Z; `WorldMigrateRun`). The engine writes every result
/// sentence.
struct ConvertTilesSection: View {
    @EnvironmentObject var buildModel: BuildModel
    /// `buildModel.worldMigrate`: one run, wherever it is shown.
    @ObservedObject var run: WorldMigrateRun
    /// The start's onboarding (#2007) measures at once: its "Move…" shows
    /// the dry run's numbers before anything moves.
    var measureOnAppear = false
    @State private var asking: Action?

    enum Action: Identifiable {
        case convert, undo
        var id: Self { self }
    }

    private var supported: Bool {
        buildModel.engineCapabilities.supports(O4EngineCapabilities.worldMigrate)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(O4WorldMigrateText.title).bold()
            Text(O4WorldMigrateText.intro)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button(O4WorldMigrateText.measure) { start(.measure) }
                    .disabled(run.isRunning)
                Button(O4WorldMigrateText.convert) { asking = .convert }
                    .disabled(run.isRunning || (run.measured?.toMove ?? 0) == 0)
                if run.canCancel {
                    Button(O4WorldMigrateText.stop) {
                        run.markCancelling()
                        buildModel.libraryContext()?.client.stopWorldMigrate()
                    }
                    .disabled(run.cancelling)
                }
                Spacer()
                Button(O4WorldMigrateText.undo) { asking = .undo }
                    .disabled(run.isRunning)
            }
            .disabled(!supported)
            if run.isRunning {
                if let fraction = run.fraction {
                    ProgressView(value: fraction)
                } else {
                    ProgressView().progressViewStyle(.linear)
                }
            }
            if !run.status.isEmpty {
                Text(run.status)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
            }
        }
        .onAppear { if measureOnAppear, !run.isRunning { start(.measure) } }
        .alert(item: $asking) { action in
            Alert(
                title: Text(action == .convert ? O4WorldMigrateText.confirmTitle
                                               : O4WorldMigrateText.undoTitle),
                message: Text(action == .convert ? O4WorldMigrateText.confirmText
                                                 : O4WorldMigrateText.undoText),
                primaryButton: .default(Text(action == .convert ? O4WorldMigrateText.convert
                                                                : O4WorldMigrateText.undo)) {
                    start(action == .convert ? .convert : .undo)
                },
                secondaryButton: .cancel())
        }
    }

    private func start(_ step: WorldMigrateRun.Step) {
        guard let context = buildModel.libraryContext() else { return }
        run.start(step, client: context.client, sceneryDir: context.sceneryDir)
    }
}
