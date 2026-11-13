import SwiftUI
import SceneryKit

/// The one run of Convert existing tiles (`world_migrate`), shared by the
/// start's onboarding sheet and Settings ▸ Storage (`buildModel
/// .worldMigrate`), so closing and reopening Settings shows the run still
/// going. Owner 2026-11-11T15:32Z: while the measure or the move runs, a
/// bar counts the tiles (`WorldMigrateProgress`), Cancel stops it cleanly
/// and Done waits for the step's result line. Owner 2026-11-12T19:08Z:
/// Measure starts by itself (`startAuto`: at the engine's start, when
/// Settings ▸ Storage opens and after a step) when Custom Scenery holds
/// per-tile packs and the kept measure is missing or stale, in the
/// background; its result shows at once with "Measured 12 min ago", and
/// every count shows the time since the step began. The Qt window's
/// `O4_Qt_Convert_Tiles.ConvertTilesSection` holds the same states.
@MainActor
final class WorldMigrateRun: ObservableObject {
    enum Step { case measure, convert, undo, freeSpace }

    /// The step running, nil when none.
    @Published private(set) var running: Step?
    /// The engine's last count of the running step (nil before the first).
    @Published private(set) var progress: O4WorldMigrateProgress?
    /// The result line (or the step's running words).
    @Published private(set) var status = ""
    /// The last dry run's result, Convert's numbers.
    @Published private(set) var measured: O4WorldMigrateResult?
    /// The chosen `world_retire` choice (`O4WorldMigrateText.choices`).
    @Published var choice = "keep_all"
    /// A step finished and its result line is shown (Done is offered).
    @Published private(set) var hasResult = false
    @Published private(set) var cancelling = false
    /// When the running step began (its elapsed time).
    @Published private(set) var startedAt: Date?
    /// The running measure started by itself (`startAuto`).
    @Published private(set) var automatic = false
    /// When the shown measure was taken.
    @Published private(set) var measuredAt: Date?

    var isRunning: Bool { running != nil }
    /// Called after each step's result with that step (the map rescans
    /// Custom Scenery, which it skipped while the step ran; after a move,
    /// undo or Free space a new measure starts by itself).
    var onFinish: (@MainActor (Step?) -> Void)?
    /// Cancel stops the measure and the move (Undo runs to its end).
    var canCancel: Bool { running == .measure || running == .convert }
    /// The bar's fraction; nil while the total is not known yet.
    var fraction: Double? {
        guard let progress, progress.total > 0 else { return nil }
        return Double(progress.done) / Double(progress.total)
    }

    func begin(_ step: Step, automatic: Bool = false, now: Date = Date()) {
        running = step
        progress = nil
        hasResult = false
        cancelling = false
        startedAt = now
        self.automatic = automatic && step == .measure
        status = step != .measure ? O4WorldMigrateText.converting
            : automatic ? O4WorldMigrateText.measuringBackground : O4WorldMigrateText.measuring
    }

    /// One `WorldMigrateProgress`; ignored when nothing runs.
    func show(_ count: O4WorldMigrateProgress) {
        guard running != nil, count.total > 0 else { return }
        progress = count
        status = O4WorldMigrateText.progressLine(count)
    }

    /// The line under the bar at `now`: the count (or the step's words)
    /// with the time since the step began; the result line when idle.
    func statusLine(now: Date = Date()) -> String {
        guard running != nil, let startedAt else { return status }
        let elapsed = now.timeIntervalSince(startedAt)
        if let progress { return O4WorldMigrateText.progressLine(progress, elapsed: elapsed) }
        return status + " " + O4WorldMigrateText.elapsedText(elapsed)
    }

    /// "Measured 12 min ago" for the shown measure (nil before one).
    func measuredLine(now: Date = Date()) -> String? {
        measuredAt.map { O4WorldMigrateText.measuredAgo(now.timeIntervalSince($0)) }
    }

    func finish(_ outcome: Result<O4WorldMigrateResult, Error>) {
        let step = running
        let wasAutomatic = automatic
        switch outcome {
        case .success(let result):
            status = result.summary
            measured = step == .measure ? result : nil
            measuredAt = step == .measure ? (result.measuredAt ?? Date()) : nil
        case .failure(let error):
            // The engine's sentence (`O4CommandError.description`); its
            // localizedDescription is Foundation's generic text.
            status = "\(error)"
            // A measure that started by itself keeps the last one shown.
            if !wasAutomatic {
                measured = nil
                measuredAt = nil
            }
        }
        running = nil
        progress = nil
        cancelling = false
        startedAt = nil
        automatic = false
        hasResult = true
        onFinish?(step)
    }

    /// The kept measure (`world_measure_state`), shown while nothing runs.
    func restore(_ state: O4WorldMeasureState) {
        guard running == nil, let result = state.result else { return }
        measured = result
        measuredAt = result.measuredAt ?? state.measuredAt
        status = result.summary
    }

    func markCancelling() { cancelling = true }

    /// The engine's line for a choice after a measure, else its hint.
    func line(for choice: String) -> String {
        measured?.choices.first(where: { $0.id == choice })?.line
            ?? O4WorldMigrateText.choices.first(where: { $0.id == choice })?.hint ?? ""
    }

    /// Tiles the chosen choice would move or make dynamic (0 before a measure).
    var toMove: Int { measured?.toMove(choice: choice) ?? 0 }

    /// Start a step on `client` unless one runs; `automatic`: a measure
    /// that started by itself, at the background priority.
    func start(_ step: Step, client: OrthoEngineClient, sceneryDir: String,
               automatic: Bool = false) {
        guard running == nil else { return }
        begin(step, automatic: automatic)
        let choice = self.choice
        Task { @MainActor in
            do {
                finish(.success(try await client.worldMigrate(
                    dryRun: step == .measure, revert: step == .undo,
                    purge: step == .freeSpace, choice: choice,
                    background: automatic, sceneryDir: sceneryDir)))
            } catch {
                finish(.failure(error))
            }
        }
    }

    /// Show the kept measure and start one in the background when the
    /// engine says so (`world_measure_state.auto`: per-tile packs or
    /// tiles to adopt again, and no measure kept or Custom Scenery changed
    /// since). Nothing while a step runs.
    func startAuto(client: OrthoEngineClient, sceneryDir: String) {
        guard running == nil else { return }
        Task { @MainActor in
            guard let state = try? await client.worldMeasureState(sceneryDir: sceneryDir) else { return }
            restore(state)
            if state.auto, !state.running, running == nil {
                start(.measure, client: client, sceneryDir: sceneryDir, automatic: true)
            }
        }
    }
}
