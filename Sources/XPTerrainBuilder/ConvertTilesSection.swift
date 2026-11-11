import SwiftUI
import SceneryKit

/// Settings ▸ Storage ▸ Convert existing tiles (World spec §13 M1, §14
/// `ConvertTilesSection`; Qt: `O4_Qt_Convert_Tiles.ConvertTilesSection`):
/// the per-tile `zOrtho4XP_` packs moved into the World pack through the
/// engine's `world_migrate` — a choice of what to keep (owner
/// 2026-11-11T15:32Z, `world_retire`: keep all, keep the tiles with custom
/// airports, make everything dynamic; each shows the dry run's figures),
/// Measure (the dry run), Convert…, Cancel, Undo… and Free space… (removes
/// the local tiles made dynamic). While a step runs a bar counts the tiles (owner
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
        case convert, undo, free
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
            Picker("", selection: $run.choice) {
                ForEach(O4WorldMigrateText.choices, id: \.id) { choice in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(choice.title)
                        Text(run.line(for: choice.id))
                            .scaledFont(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .tag(choice.id)
                }
            }
            .pickerStyle(.radioGroup)
            .labelsHidden()
            .disabled(run.isRunning)
            HStack {
                Button(O4WorldMigrateText.measure) { start(.measure) }
                    .disabled(run.isRunning)
                Button(O4WorldMigrateText.convert) { asking = .convert }
                    .disabled(run.isRunning || run.toMove == 0)
                if run.canCancel {
                    Button(O4WorldMigrateText.stop) {
                        run.markCancelling()
                        buildModel.libraryContext()?.client.stopWorldMigrate()
                    }
                    .disabled(run.cancelling)
                }
                Spacer()
                Button(O4WorldMigrateText.freeSpace) { asking = .free }
                    .disabled(run.isRunning)
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
                title: Text(words(action).title),
                message: Text(words(action).text),
                primaryButton: .default(Text(words(action).button)) {
                    start(action == .convert ? .convert : action == .undo ? .undo : .freeSpace)
                },
                secondaryButton: .cancel())
        }
    }

    /// The confirmation's words (Qt: `ask_convert`, `ask_undo`, `ask_free`).
    private func words(_ action: Action) -> (title: String, text: String, button: String) {
        switch action {
        case .convert:
            let extra = run.choice == "keep_all" ? "" : " " + O4WorldMigrateText.confirmDynamic
            return (O4WorldMigrateText.confirmTitle, O4WorldMigrateText.confirmText + extra,
                    O4WorldMigrateText.convert)
        case .undo:
            return (O4WorldMigrateText.undoTitle, O4WorldMigrateText.undoText, O4WorldMigrateText.undo)
        case .free:
            return (O4WorldMigrateText.freeTitle, O4WorldMigrateText.freeText,
                    O4WorldMigrateText.freeSpace)
        }
    }

    private func start(_ step: WorldMigrateRun.Step) {
        guard let context = buildModel.libraryContext() else { return }
        run.start(step, client: context.client, sceneryDir: context.sceneryDir)
    }
}
