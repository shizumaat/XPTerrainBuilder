import SwiftUI
import SceneryKit

/// The one run of Convert existing tiles (`world_migrate`), shared by the
/// start's onboarding sheet and Settings ▸ Storage (`buildModel
/// .worldMigrate`), so closing and reopening Settings shows the run still
/// going. Owner 2026-11-11T15:32Z: while the measure or the move runs, a
/// bar counts the tiles (`WorldMigrateProgress`), Cancel stops it cleanly
/// and Done waits for the step's result line. The Qt window's
/// `O4_Qt_Convert_Tiles.ConvertTilesSection` holds the same states.
@MainActor
final class WorldMigrateRun: ObservableObject {
    enum Step { case measure, convert, undo }

    /// The step running, nil when none.
    @Published private(set) var running: Step?
    /// The engine's last count of the running step (nil before the first).
    @Published private(set) var progress: O4WorldMigrateProgress?
    /// The result line (or the step's running words).
    @Published private(set) var status = ""
    /// The last dry run's result, Convert's numbers.
    @Published private(set) var measured: O4WorldMigrateResult?
    /// A step finished and its result line is shown (Done is offered).
    @Published private(set) var hasResult = false
    @Published private(set) var cancelling = false

    var isRunning: Bool { running != nil }
    /// Cancel stops the measure and the move (Undo runs to its end).
    var canCancel: Bool { running == .measure || running == .convert }
    /// The bar's fraction; nil while the total is not known yet.
    var fraction: Double? {
        guard let progress, progress.total > 0 else { return nil }
        return Double(progress.done) / Double(progress.total)
    }

    func begin(_ step: Step) {
        running = step
        progress = nil
        hasResult = false
        cancelling = false
        status = step == .measure ? O4WorldMigrateText.measuring : O4WorldMigrateText.converting
    }

    /// One `WorldMigrateProgress`; ignored when nothing runs.
    func show(_ count: O4WorldMigrateProgress) {
        guard running != nil, count.total > 0 else { return }
        progress = count
        status = O4WorldMigrateText.progressLine(count)
    }

    func finish(_ outcome: Result<O4WorldMigrateResult, Error>) {
        let step = running
        switch outcome {
        case .success(let result):
            status = result.summary
            measured = step == .measure ? result : nil
        case .failure(let error):
            // The engine's sentence (`O4CommandError.description`); its
            // localizedDescription is Foundation's generic text.
            status = "\(error)"
            measured = nil
        }
        running = nil
        progress = nil
        cancelling = false
        hasResult = true
    }

    func markCancelling() { cancelling = true }

    /// Start a step on `client` unless one runs.
    func start(_ step: Step, client: OrthoEngineClient, sceneryDir: String) {
        guard running == nil else { return }
        begin(step)
        Task { @MainActor in
            do {
                finish(.success(try await client.worldMigrate(
                    dryRun: step == .measure, revert: step == .undo, sceneryDir: sceneryDir)))
            } catch {
                finish(.failure(error))
            }
        }
    }
}
