import SwiftUI
import SceneryKit

/// Library ▸ Convert existing tiles (World spec §13 M1, §14
/// `ConvertTilesSection`; Qt: `O4_Qt_Convert_Tiles.ConvertTilesSection`):
/// the per-tile `zOrtho4XP_` packs moved into the World pack through the
/// engine's `world_migrate` — Measure (the dry run), Convert…, Stop and
/// Undo…. The engine writes every result sentence.
struct ConvertTilesSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @State private var status = ""
    @State private var running = false
    @State private var measured: O4WorldMigrateResult?
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
                Button(O4WorldMigrateText.measure) { run(dryRun: true) }
                    .disabled(running)
                Button(O4WorldMigrateText.convert) { asking = .convert }
                    .disabled(running || (measured?.toMove ?? 0) == 0)
                if running {
                    Button(O4WorldMigrateText.stop) {
                        buildModel.libraryContext()?.client.stopWorldMigrate()
                    }
                }
                Spacer()
                Button(O4WorldMigrateText.undo) { asking = .undo }
                    .disabled(running)
            }
            .disabled(!supported)
            if !status.isEmpty {
                Text(status)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
            }
        }
        .alert(item: $asking) { action in
            Alert(
                title: Text(action == .convert ? O4WorldMigrateText.confirmTitle
                                               : O4WorldMigrateText.undoTitle),
                message: Text(action == .convert ? O4WorldMigrateText.confirmText
                                                 : O4WorldMigrateText.undoText),
                primaryButton: .default(Text(action == .convert ? O4WorldMigrateText.convert
                                                                : O4WorldMigrateText.undo)) {
                    run(dryRun: false, revert: action == .undo)
                },
                secondaryButton: .cancel())
        }
    }

    private func run(dryRun: Bool, revert: Bool = false) {
        guard !running, let context = buildModel.libraryContext() else { return }
        running = true
        status = dryRun ? O4WorldMigrateText.measuring : O4WorldMigrateText.converting
        Task { @MainActor in
            defer { running = false }
            do {
                let result = try await context.client.worldMigrate(
                    dryRun: dryRun, revert: revert, sceneryDir: context.sceneryDir)
                status = result.summary
                measured = dryRun ? result : nil
            } catch {
                status = error.localizedDescription
            }
        }
    }
}
