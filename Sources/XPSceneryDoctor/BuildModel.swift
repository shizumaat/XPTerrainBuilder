import Foundation
import SwiftUI
import SceneryKit
import os

private let buildLog = Logger(subsystem: "com.novemberlima.XPSceneryDoctor", category: "build")

/// Main-window mode: the doctor (Manage) or the Ortho4XP front-end (Build).
enum AppMode: String, CaseIterable {
    case manage, build

    var label: String {
        switch self {
        case .manage: return "Manage"
        case .build: return "Build"
        }
    }
}

/// High-frequency build activity (progress bars, current step), isolated
/// from BuildModel exactly like ProgressModel is from AnalysisController:
/// only the small activity box observes this, so per-texture progress ticks
/// never redraw the map canvas.
@MainActor
final class BuildActivityModel: ObservableObject {
    /// Engine bar ids: 1 = mesh, 2 = imagery download, 3 = DDS conversion.
    @Published var bars: [Int: Int] = [:]
    @Published var currentStepLabel: String?
    @Published var currentTileKey: String?
}

/// The build console: engine stdout, append-heavy. Lines accumulate here
/// and a ~10 Hz generation bump tells the (NSTextView-backed) console view
/// to pull what's new — per-line @Published updates would hammer SwiftUI
/// during imagery downloads.
@MainActor
final class BuildConsoleModel: ObservableObject {
    @Published private(set) var generation = 0
    /// Monotonic count of every line ever appended (survives trimming, so
    /// the view can tell "new lines" from "buffer rebuilt").
    private(set) var totalAppended = 0
    /// Bumped on clear so the view knows to rebuild rather than append.
    private(set) var clearCount = 0
    private(set) var lines: [String] = []
    private var flushScheduled = false

    static let maxLines = 4000
    static let trimTo = 3000

    func append(_ line: String) {
        lines.append(line)
        totalAppended += 1
        if lines.count > Self.maxLines {
            lines.removeFirst(lines.count - Self.trimTo)
        }
        scheduleFlush()
    }

    func clear() {
        lines = []
        clearCount += 1
        generation += 1
    }

    private func scheduleFlush() {
        guard !flushScheduled else { return }
        flushScheduled = true
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(100))
            guard let self else { return }
            self.flushScheduled = false
            self.generation += 1
        }
    }
}

/// Build-mode state: the configured engine, the map tile selection, the
/// build queue and the engine's global config. Owns the per-tile driver
/// processes; one tile builds at a time (the engine itself is single-tile).
@MainActor
final class BuildModel: ObservableObject {
    struct TileCoord: Hashable, Comparable, Sendable {
        let lat: Int
        let lon: Int

        var key: String { TileMath.key(lat: lat, lon: lon) }

        static func < (lhs: TileCoord, rhs: TileCoord) -> Bool {
            (lhs.lat, lhs.lon) < (rhs.lat, rhs.lon)
        }
    }

    // MARK: Persisted settings

    @AppStorage("AppMode") private var modeRaw: String = AppMode.manage.rawValue
    @AppStorage("OrthoEnginePath") var enginePath: String = "" {
        didSet { reloadEngine() }
    }
    @AppStorage("OrthoProvider") var buildProvider: String = ""
    @AppStorage("OrthoZoomLevel") var buildZL: Int = 16
    @AppStorage("OrthoCustomBuildDir") var customBuildDir: String = ""
    /// Symlink finished tiles into Custom Scenery — the file watcher then
    /// picks them up and the Manage side reconciles scenery_packs.ini.
    @AppStorage("OrthoLinkTiles") var linkTiles: Bool = true

    var mode: AppMode {
        get { AppMode(rawValue: modeRaw) ?? .manage }
        set {
            objectWillChange.send()
            modeRaw = newValue.rawValue
        }
    }

    /// Selected build steps, persisted as an ordered subset of the engine's
    /// step sequence.
    @Published var steps: Set<String> {
        didSet { UserDefaults.standard.set(Array(steps), forKey: "OrthoSteps") }
    }

    // MARK: Engine state

    @Published private(set) var engine: OrthoEngine?
    @Published private(set) var schema: OrthoConfigSchema
    @Published private(set) var providers: [OrthoEngine.Provider] = []
    /// nil = probe not run yet or engine missing; [] = environment ready.
    @Published private(set) var missingPackages: [String]?
    @Published private(set) var globalConfigValues: [String: O4Value] = [:]
    @Published var engineError: String?

    // MARK: Build state

    @Published var selected: Set<TileCoord> = []
    @Published private(set) var tileStates: [TileCoord: OrthoEngine.TileState] = [:]
    @Published private(set) var queue: [TileCoord] = []
    @Published private(set) var activeTile: TileCoord?
    @Published private(set) var isBuilding = false
    @Published private(set) var isStopping = false
    @Published private(set) var lastRunSummary: String?

    let activity = BuildActivityModel()
    let console = BuildConsoleModel()

    private var runner: OrthoBuildRunner?
    private var exitOutcome: OrthoBuildOutcome?
    private var builtThisRun = 0
    private var failedThisRun = 0

    init() {
        let saved = UserDefaults.standard.stringArray(forKey: "OrthoSteps")
        steps = Set(saved ?? OrthoBuildJob.allSteps)
        schema = OrthoConfigSchema.bundledSnapshot()
            ?? OrthoConfigSchema(engineVersion: "", groups: [:], vars: [:])
        reloadEngine()
    }

    /// Steps in the engine's canonical order (the set has no order).
    var orderedSteps: [String] {
        (OrthoBuildJob.allSteps + ["overlay"]).filter { steps.contains($0) }
    }

    // MARK: - Engine loading

    func reloadEngine() {
        engineError = nil
        guard !enginePath.isEmpty else {
            engine = nil
            providers = []
            missingPackages = nil
            return
        }
        let root = URL(fileURLWithPath: enginePath, isDirectory: true)
        guard let located = OrthoEngine.locate(at: root) else {
            engine = nil
            providers = []
            missingPackages = nil
            engineError = "Not recognized as an Ortho4XP folder (needs Ortho4XP.py and src/)."
            return
        }
        engine = located
        providers = located.providers()
        refreshTileStates()
        reloadGlobalConfig()

        // Environment probe + live schema extraction off the main thread;
        // the bundled snapshot serves until (or unless) the real one lands.
        Task { [weak self] in
            let (missing, extracted) = await Task.detached(priority: .utility) {
                (OrthoBuildRunner.missingPythonPackages(engine: located),
                 OrthoBuildRunner.extractSchema(engine: located))
            }.value
            guard let self, self.engine == located else { return }
            self.missingPackages = missing ?? []
            if let extracted {
                self.schema = extracted
                self.reloadGlobalConfig()
            }
        }
    }

    var tileBaseFolder: URL? {
        guard let engine else { return nil }
        if !customBuildDir.isEmpty {
            return URL(fileURLWithPath: customBuildDir, isDirectory: true)
        }
        return engine.tilesDirectory
    }

    func refreshTileStates() {
        guard let base = tileBaseFolder else {
            tileStates = [:]
            return
        }
        let states = OrthoEngine.tileStates(inBaseFolder: base)
        tileStates = Dictionary(uniqueKeysWithValues:
            states.map { (TileCoord(lat: $0.lat, lon: $0.lon), $0) })
    }

    // MARK: - Global config

    func reloadGlobalConfig() {
        guard let engine else {
            globalConfigValues = [:]
            return
        }
        guard let file = try? OrthoConfigFile(contentsOf: engine.globalConfigURL) else {
            // Engine creates the file on first import; defaults apply until then.
            globalConfigValues = [:]
            return
        }
        globalConfigValues = file.values(schema: schema)
    }

    /// The effective value shown in the settings editor: file value if set,
    /// otherwise the schema default.
    func configValue(for name: String) -> O4Value? {
        globalConfigValues[name] ?? schema.vars[name]?.default
    }

    func setConfigValue(_ name: String, to value: O4Value) {
        guard let engine else { return }
        var file = (try? OrthoConfigFile(contentsOf: engine.globalConfigURL)) ?? OrthoConfigFile()
        file.set(name, to: value)
        do {
            try file.write(to: engine.globalConfigURL)
            globalConfigValues[name] = value
        } catch {
            engineError = "Could not write Ortho4XP.cfg: \(error.localizedDescription)"
        }
    }

    // MARK: - Tile selection

    func toggleTile(lat: Int, lon: Int) {
        guard lat >= -90, lat < 90, lon >= -180, lon < 180 else { return }
        let coord = TileCoord(lat: lat, lon: lon)
        if selected.contains(coord) {
            selected.remove(coord)
        } else {
            selected.insert(coord)
        }
    }

    func selectTile(containingLat lat: Double, lon: Double) {
        let coord = TileCoord(lat: Int(floor(lat)), lon: Int(floor(lon)))
        selected.insert(coord)
    }

    func clearSelection() {
        selected = []
    }

    // MARK: - Building

    var canBuild: Bool {
        engine != nil && !selected.isEmpty && !isBuilding && !orderedSteps.isEmpty
    }

    func startBuild() {
        guard canBuild else { return }
        queue = selected.sorted()
        isBuilding = true
        isStopping = false
        builtThisRun = 0
        failedThisRun = 0
        lastRunSummary = nil
        runNextTile()
    }

    /// Graceful stop: the current tile aborts via the engine's red flag and
    /// nothing further dequeues. A second press hard-kills the process.
    func stopBuild() {
        guard isBuilding else { return }
        queue = []
        if isStopping {
            runner?.kill()
        } else {
            isStopping = true
            runner?.requestStop()
            console.append("Stopping after the current operation — press Stop again to force-kill.")
        }
    }

    private func runNextTile() {
        guard let engine, let tile = queue.first else {
            finishRun()
            return
        }
        queue.removeFirst()
        activeTile = tile
        activity.currentTileKey = tile.key
        activity.currentStepLabel = "Starting…"
        activity.bars = [:]
        exitOutcome = nil

        let job = OrthoBuildJob(
            lat: tile.lat, lon: tile.lon,
            steps: orderedSteps,
            provider: buildProvider.isEmpty ? nil : buildProvider,
            zl: buildZL,
            buildDir: customBuildDir)
        console.append("")
        console.append("========== Tile \(tile.key) — \(orderedSteps.map { OrthoBuildJob.stepLabel($0) }.joined(separator: ", ")) ==========")

        let runner = OrthoBuildRunner()
        self.runner = runner
        do {
            try runner.start(
                job: job, engine: engine,
                onEvent: { [weak self] event in
                    Task { @MainActor [weak self] in self?.handle(event) }
                },
                onExit: { [weak self] status in
                    Task { @MainActor [weak self] in
                        // The termination handler can beat the pipe's final
                        // reads — give the exit event a beat to land first.
                        try? await Task.sleep(for: .milliseconds(250))
                        self?.processExited(status)
                    }
                })
        } catch {
            console.append("ERROR: could not launch the build driver: \(error.localizedDescription)")
            failedThisRun += 1
            activeTile = nil
            finishRun()
        }
    }

    private func handle(_ event: OrthoBuildEvent) {
        switch event {
        case .console(let line):
            console.append(line)
        case .engineVersion(let version):
            buildLog.notice("driver attached to engine \(version)")
        case .progress(let bar, let percent):
            activity.bars[bar] = percent
        case .stepStarted(let step):
            activity.currentStepLabel = OrthoBuildJob.stepLabel(step)
        case .stepFinished(let step, let ok):
            if !ok { console.append("*** Step \(OrthoBuildJob.stepLabel(step)) failed.") }
        case .stepSkipped(let step):
            console.append("(skipping unknown step \(step))")
        case .stopping:
            isStopping = true
        case .fatal(let message):
            console.append("FATAL: \(message)")
        case .exit(let outcome):
            exitOutcome = outcome
        }
    }

    private func processExited(_ status: Int32) {
        let outcome = exitOutcome ?? (isStopping ? .stopped : .fail)
        let finished = activeTile
        runner = nil
        activeTile = nil
        activity.currentStepLabel = nil
        activity.currentTileKey = nil

        switch outcome {
        case .ok:
            builtThisRun += 1
            if let tile = finished {
                console.append("Tile \(tile.key) finished.")
                selected.remove(tile)
                if linkTiles { linkIntoCustomScenery(tile) }
            }
        case .fail:
            failedThisRun += 1
            if status != 0, exitOutcome == nil {
                console.append("*** Build process exited unexpectedly (status \(status)).")
            }
        case .stopped:
            console.append("Build stopped.")
        }
        refreshTileStates()

        if outcome == .ok, !queue.isEmpty {
            runNextTile()
        } else {
            // A failed tile stops the queue — its problem usually repeats
            // (provider auth, missing env) and burning hours on the rest
            // helps nobody. The console says what happened.
            if outcome == .fail, !queue.isEmpty {
                console.append("Remaining \(queue.count) tile(s) not started — fix the error above and build again.")
                queue = []
            }
            finishRun()
        }
    }

    private func finishRun() {
        isBuilding = false
        isStopping = false
        activity.bars = [:]
        if builtThisRun > 0 || failedThisRun > 0 {
            var parts: [String] = []
            if builtThisRun > 0 { parts.append("\(builtThisRun) tile\(builtThisRun == 1 ? "" : "s") built") }
            if failedThisRun > 0 { parts.append("\(failedThisRun) failed") }
            lastRunSummary = parts.joined(separator: ", ")
            console.append("=== Run complete: \(lastRunSummary!) ===")
        }
    }

    /// Symlink the tile's build folder into Custom Scenery (the engine
    /// GUI's Ctrl+click). The installation watcher notices the new pack and
    /// the next scan adds it to scenery_packs.ini.
    private func linkIntoCustomScenery(_ tile: TileCoord) {
        let xplanePath = UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? ""
        guard !xplanePath.isEmpty, let base = tileBaseFolder else { return }
        let source = base.appendingPathComponent(OrthoEngine.tileFolderName(lat: tile.lat, lon: tile.lon))
        guard FileManager.default.fileExists(atPath: source.path) else { return }
        let target = URL(fileURLWithPath: xplanePath)
            .appendingPathComponent("Custom Scenery")
            .appendingPathComponent(source.lastPathComponent)
        guard !FileManager.default.fileExists(atPath: target.path) else { return }
        do {
            try FileManager.default.createSymbolicLink(at: target, withDestinationURL: source)
            console.append("Linked \(source.lastPathComponent) into Custom Scenery.")
        } catch {
            console.append("Could not link \(source.lastPathComponent) into Custom Scenery: \(error.localizedDescription)")
        }
    }
}
