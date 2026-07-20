import Foundation
import SwiftUI
import SceneryKit
import os

private let buildLog = Logger(subsystem: "com.novemberlima.XPScenerySmith", category: "build")

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

/// One tile's live build progress — the Qt map badge / activity row model.
/// state mirrors the protocol's TileState vocabulary exactly.
struct TileProgress: Equatable {
    enum State: String {
        case queued, active, indeterminate, done, error
    }
    var state: State
    var label: String
    var percent: Double
}

/// High-frequency build activity (per-tile progress, run clock), isolated
/// from BuildModel like ProgressModel is from AnalysisController. The map
/// canvas and activity rows observe this; StepProgress ticks never touch
/// the rest of the window.
@MainActor
final class BuildActivityModel: ObservableObject {
    @Published var tiles: [BuildModel.TileCoord: TileProgress] = [:]
    /// Ordered rows for the Activity box (run order).
    @Published var runOrder: [BuildModel.TileCoord] = []
    @Published var elapsedSeconds: Double = 0
    /// nil = no defensible estimate — render a dash, never a wild number.
    @Published var remainingSeconds: Double?
    @Published var doneTiles = 0
    @Published var totalTiles = 0

    func reset() {
        tiles = [:]
        runOrder = []
        elapsedSeconds = 0
        remainingSeconds = nil
        doneTiles = 0
        totalTiles = 0
    }
}

/// The build console: engine output (stderr under the protocol transport),
/// append-heavy; a ~10 Hz generation bump tells the NSTextView to pull.
@MainActor
final class BuildConsoleModel: ObservableObject {
    @Published private(set) var generation = 0
    private(set) var totalAppended = 0
    private(set) var clearCount = 0
    private(set) var lines: [String] = []
    private var flushScheduled = false

    static let maxLines = 5000
    static let trimTo = 4000

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

/// Build-mode state, mirroring the engine's Qt front end: an engine session
/// over the JSON-lines protocol (scan / enqueue_build / cancel / links),
/// map selection with an active tile, per-tile progress, and the engine's
/// global config. Engines without the protocol (pre-1.50) fall back to the
/// bundled per-tile driver script.
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
    /// Step groups, matching the Qt build box's three checkboxes.
    @AppStorage("OrthoDoVector") var doVector: Bool = true
    @AppStorage("OrthoDoImagery") var doImagery: Bool = true
    @AppStorage("OrthoDoOverlays") var doOverlays: Bool = false
    @AppStorage("OrthoSkipBuilt") var skipBuilt: Bool = true
    /// Install finished tiles into Custom Scenery automatically.
    @AppStorage("OrthoLinkTiles") var linkTiles: Bool = true

    var mode: AppMode {
        get { AppMode(rawValue: modeRaw) ?? .manage }
        set {
            objectWillChange.send()
            modeRaw = newValue.rawValue
            if newValue == .build { connectIfNeeded() }
        }
    }

    // MARK: Engine state

    @Published private(set) var engine: OrthoEngine?
    @Published private(set) var schema: OrthoConfigSchema
    @Published private(set) var providers: [OrthoEngine.Provider] = []
    @Published private(set) var missingPackages: [String]?
    @Published private(set) var globalConfigValues: [String: O4Value] = [:]
    @Published var engineError: String?
    /// The engine speaks the JSON-lines session protocol (dev/1.50+).
    @Published private(set) var usesProtocol = false
    @Published private(set) var protocolHello: (version: String, protocolVersion: String)?

    // MARK: Scan state (what exists on disk / in X-Plane)

    @Published private(set) var built: [TileCoord: O4TileInfo] = [:]
    @Published private(set) var installed: Set<TileCoord> = []
    @Published private(set) var isScanning = false
    @Published private(set) var scanPhase = ""
    private var scanAccumBuilt: [TileCoord: O4TileInfo] = [:]
    private var scanAccumInstalled: Set<TileCoord> = []

    // MARK: Selection (Qt semantics: a set + one active tile)

    @Published var selected: Set<TileCoord> = []
    @Published var activeTile: TileCoord?

    // MARK: Run state

    @Published private(set) var isBuilding = false
    @Published private(set) var isStopping = false
    @Published private(set) var lastRunSummary: String?

    let activity = BuildActivityModel()
    let console = BuildConsoleModel()

    private var client: OrthoEngineClient?
    private var clearProgressTask: Task<Void, Never>?

    // Legacy (non-protocol) fallback
    private var legacyRunner: OrthoBuildRunner?
    private var legacyQueue: [TileCoord] = []
    private var legacyExitOutcome: OrthoBuildOutcome?
    private var legacyDone = 0
    private var legacyFailed = 0

    init() {
        schema = OrthoConfigSchema.bundledSnapshot()
            ?? OrthoConfigSchema(engineVersion: "", groups: [:], vars: [:])
        reloadEngine()
    }

    // MARK: - Engine loading

    func reloadEngine() {
        engineError = nil
        disconnect()
        guard !enginePath.isEmpty else {
            engine = nil
            providers = []
            missingPackages = nil
            usesProtocol = false
            return
        }
        let root = URL(fileURLWithPath: enginePath, isDirectory: true)
        guard let located = OrthoEngine.locate(at: root) else {
            engine = nil
            providers = []
            missingPackages = nil
            usesProtocol = false
            engineError = "Not recognized as an Ortho4XP folder (needs Ortho4XP.py and src/)."
            return
        }
        engine = located
        providers = located.providers()
        usesProtocol = OrthoEngineClient.engineSupportsProtocol(located)
        reloadGlobalConfig()
        if !usesProtocol { refreshTileStatesLegacy() }
        if mode == .build { connectIfNeeded() }

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

    private var customSceneryPath: String {
        let xplane = UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? ""
        guard !xplane.isEmpty else { return "" }
        return URL(fileURLWithPath: xplane).appendingPathComponent("Custom Scenery").path
    }

    // MARK: - Engine session (protocol path)

    private func connectIfNeeded() {
        guard usesProtocol, client == nil, let engine else { return }
        let newClient = OrthoEngineClient(
            onEvent: { [weak self] event in
                Task { @MainActor [weak self] in self?.handle(event) }
            },
            onExit: { [weak self] status in
                Task { @MainActor [weak self] in self?.sessionExited(status) }
            })
        do {
            try newClient.launch(engine: engine)
            client = newClient
            console.append("Engine session started (Ortho4XP \(engine.version)).")
            rescan()
        } catch {
            engineError = "Could not start the engine session: \(error.localizedDescription)"
            console.append("ERROR: \(engineError!)")
        }
    }

    private func disconnect() {
        client?.shutdown()
        client = nil
        legacyRunner?.kill()
        legacyRunner = nil
        isBuilding = false
        isStopping = false
        activity.reset()
    }

    private func sessionExited(_ status: Int32) {
        guard client != nil else { return }
        client = nil
        if isBuilding {
            console.append("*** Engine session ended unexpectedly (status \(status)).")
            isBuilding = false
            isStopping = false
        }
    }

    /// Rescan built + installed tiles through the engine.
    func rescan() {
        guard usesProtocol else {
            refreshTileStatesLegacy()
            return
        }
        connectIfNeeded()
        guard let client, let base = tileBaseFolder else { return }
        scanAccumBuilt = [:]
        scanAccumInstalled = []
        isScanning = true
        client.send(command: "scan", arguments: [
            "working_dir": base.path,
            "custom_scenery_dir": customSceneryPath,
        ])
    }

    // MARK: - Event handling (protocol path)

    private func handle(_ event: O4Event) {
        switch event {
        case .hello(let version, let protocolVersion, _):
            protocolHello = (version, protocolVersion)
            buildLog.notice("engine hello: \(version) protocol \(protocolVersion)")
        case .stderr(let line), .log(_, let line):
            console.append(line)
        case .scanProgress(let phase, _, _):
            scanPhase = phase
        case .scanBatch(let builtTriples, let installedPairs):
            for (lat, lon, info) in builtTriples {
                if let tileInfo = O4TileInfo(json: info) {
                    scanAccumBuilt[TileCoord(lat: lat, lon: lon)] = tileInfo
                }
            }
            for (lat, lon) in installedPairs {
                scanAccumInstalled.insert(TileCoord(lat: lat, lon: lon))
            }
            // Stream into the live maps; ScanDone swaps in the final truth.
            built.merge(scanAccumBuilt) { _, new in new }
            installed.formUnion(scanAccumInstalled)
        case .scanDone:
            built = scanAccumBuilt
            installed = scanAccumInstalled
            isScanning = false
            scanPhase = ""
        case .tileState(let lat, let lon, let state, let label, let percent):
            let coord = TileCoord(lat: lat, lon: lon)
            let state = TileProgress.State(rawValue: state) ?? .queued
            activity.tiles[coord] = TileProgress(
                state: state,
                label: label.isEmpty ? state.rawValue : label,
                percent: percent)
        case .stepProgress(let lat, let lon, _, let label, let percent, let indeterminate):
            let coord = TileCoord(lat: lat, lon: lon)
            let previous = activity.tiles[coord]?.percent ?? 0
            activity.tiles[coord] = TileProgress(
                state: indeterminate ? .indeterminate : .active,
                label: label,
                // Indeterminate steps report no usable percent — hold it.
                percent: indeterminate ? previous : percent)
        case .autoPatchBegin, .autoPatchProgress:
            break // folded into StepProgress labels by the session
        case .buildDone(let lat, let lon, let ok, let error):
            let coord = TileCoord(lat: lat, lon: lon)
            if ok {
                console.append("Tile \(coord.key) finished.")
                selected.remove(coord)
                refreshTileInfo(coord)
                if linkTiles { installLink(coord, quiet: true) }
            } else if !error.isEmpty {
                console.append("*** Tile \(coord.key) failed: \(error)")
            }
        case .runEta(let elapsed, let remaining, let done, let total):
            activity.elapsedSeconds = elapsed
            activity.remainingSeconds = remaining
            activity.doneTiles = done
            activity.totalTiles = total
        case .runDone(let done, let errors, let cancelled):
            isBuilding = false
            isStopping = false
            var parts = ["\(done) tile\(done == 1 ? "" : "s") built"]
            if errors > 0 { parts.append("\(errors) failed") }
            if cancelled { parts.append("stopped") }
            lastRunSummary = parts.joined(separator: ", ")
            console.append("=== Run complete: \(lastRunSummary!) ===")
            rescan()
            // Qt lingers 5 s before hiding the activity rows.
            clearProgressTask?.cancel()
            clearProgressTask = Task { @MainActor [weak self] in
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self, !self.isBuilding else { return }
                self.activity.reset()
            }
        case .engineError(let fatal, let text):
            console.append((fatal ? "FATAL: " : "Engine: ") + text)
            if fatal { engineError = text }
        case .unknown:
            break // additive protocol: ignore unknown event types
        }
    }

    private func refreshTileInfo(_ coord: TileCoord) {
        guard let client, let base = tileBaseFolder else { return }
        client.send(command: "tile_info", arguments: [
            "lat": coord.lat, "lon": coord.lon, "working_dir": base.path,
        ]) { [weak self] reply in
            guard reply.ok, let result = reply.result,
                  let info = O4TileInfo(json: result) else { return }
            Task { @MainActor [weak self] in
                self?.built[coord] = info
            }
        }
    }

    // MARK: - Selection (click / ⌘-click / ⇧-click, Qt semantics)

    func click(lat: Int, lon: Int, command: Bool, shift: Bool) {
        guard lat >= -90, lat < 90, lon >= -180, lon < 180 else { return }
        let coord = TileCoord(lat: lat, lon: lon)
        if command {
            if selected.contains(coord) {
                selected.remove(coord)
                if activeTile == coord { activeTile = selected.sorted().first }
            } else {
                selected.insert(coord)
                activeTile = coord
            }
        } else if shift, let anchor = activeTile {
            // Contiguous rectangle from the active tile.
            for lat in min(anchor.lat, coord.lat)...max(anchor.lat, coord.lat) {
                for lon in min(anchor.lon, coord.lon)...max(anchor.lon, coord.lon) {
                    selected.insert(TileCoord(lat: lat, lon: lon))
                }
            }
        } else {
            selected = [coord]
            activeTile = coord
        }
    }

    func selectTile(containingLat lat: Double, lon: Double) {
        let coord = TileCoord(lat: Int(floor(lat)), lon: Int(floor(lon)))
        selected.insert(coord)
        activeTile = coord
    }

    func clearSelection() {
        selected = []
        activeTile = nil
    }

    // MARK: - Building

    /// Tiles the next Build press would actually build.
    var buildableSelection: [TileCoord] {
        selected.sorted().filter { coord in
            !skipBuilt || built[coord]?.dsfPresent != true
        }
    }

    var canBuild: Bool {
        engine != nil && !buildableSelection.isEmpty
            && (doVector || doImagery || doOverlays)
            && !(isBuilding && !usesProtocol) // legacy path can't queue into a run
    }

    func startBuild() {
        guard canBuild else { return }
        let todo = buildableSelection
        lastRunSummary = nil
        if usesProtocol {
            startProtocolBuild(todo)
        } else {
            startLegacyBuild(todo)
        }
    }

    private func startProtocolBuild(_ todo: [TileCoord]) {
        connectIfNeeded()
        guard let client else { return }
        if !isBuilding {
            activity.reset()
            isBuilding = true
            isStopping = false
        }
        clearProgressTask?.cancel()
        for coord in todo where activity.tiles[coord] == nil {
            activity.tiles[coord] = TileProgress(state: .queued, label: "queued", percent: 0)
            activity.runOrder.append(coord)
        }
        console.append("=== Building \(todo.count) tile\(todo.count == 1 ? "" : "s"): \(todo.prefix(8).map { $0.key }.joined(separator: " "))\(todo.count > 8 ? " …" : "") ===")
        client.send(command: "enqueue_build", arguments: [
            "tiles": todo.map { [$0.lat, $0.lon] },
            "provider": buildProvider,
            "zoomlevel": buildZL,
            "custom_build_dir": customBuildDir,
            "do_vector": doVector,
            "do_imagery": doImagery,
            "do_overlays": doOverlays,
        ]) { [weak self] reply in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if !reply.ok {
                    self.console.append("*** Build refused: \(reply.error ?? "unknown error")")
                    self.isBuilding = false
                    self.activity.reset()
                }
            }
        }
    }

    /// Whole-run stop (the ■ Stop button).
    func stopBuild() {
        guard isBuilding else { return }
        isStopping = true
        if usesProtocol {
            client?.send(command: "cancel")
            console.append("Stopping after the current step…")
        } else {
            legacyQueue = []
            legacyRunner?.requestStop()
        }
    }

    /// Per-tile cancel (the little ✕ on an activity row).
    func cancelTile(_ coord: TileCoord) {
        guard usesProtocol else { return }
        client?.send(command: "cancel_tile", arguments: ["lat": coord.lat, "lon": coord.lon])
        if var progress = activity.tiles[coord] {
            progress.label = "stopping…"
            activity.tiles[coord] = progress
        }
    }

    // MARK: - Install links (Installed in X-Plane)

    func isInstalled(_ coord: TileCoord) -> Bool {
        installed.contains(coord)
    }

    func setInstalled(_ coord: TileCoord, _ install: Bool) {
        guard usesProtocol else {
            legacySetInstalled(coord, install)
            return
        }
        guard let client else { return }
        let buildDir = built[coord]?.buildDir
            ?? tileBaseFolder?.appendingPathComponent(
                OrthoEngine.tileFolderName(lat: coord.lat, lon: coord.lon)).path ?? ""
        client.send(command: install ? "links_install" : "links_uninstall", arguments: [
            "lat": coord.lat, "lon": coord.lon,
            "build_dir": buildDir, "scenery_dir": customSceneryPath,
        ]) { [weak self] reply in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if reply.ok {
                    if install { self.installed.insert(coord) } else { self.installed.remove(coord) }
                    self.console.append("\(install ? "Installed" : "Removed") \(coord.key) \(install ? "into" : "from") X-Plane.")
                } else {
                    self.console.append("Could not \(install ? "install" : "remove") \(coord.key): \(reply.error ?? "unknown error")")
                }
            }
        }
    }

    private func installLink(_ coord: TileCoord, quiet: Bool) {
        guard !customSceneryPath.isEmpty, !installed.contains(coord) else { return }
        setInstalled(coord, true)
    }

    // MARK: - Global config

    func reloadGlobalConfig() {
        guard let engine,
              let file = try? OrthoConfigFile(contentsOf: engine.globalConfigURL) else {
            globalConfigValues = [:]
            return
        }
        globalConfigValues = file.values(schema: schema)
    }

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

    // MARK: - Legacy fallback (engines without the session protocol)

    private func refreshTileStatesLegacy() {
        guard let base = tileBaseFolder else {
            built = [:]
            return
        }
        var scanned: [TileCoord: O4TileInfo] = [:]
        for state in OrthoEngine.tileStates(inBaseFolder: base) {
            let json = O4JSON.object([
                "lat": .int(state.lat), "lon": .int(state.lon),
                "build_dir": .string(state.buildDir.path),
                "dsf_present": .bool(state.hasDSF),
            ])
            scanned[TileCoord(lat: state.lat, lon: state.lon)] = O4TileInfo(json: json)
        }
        built = scanned
        // Installed = matching zOrtho4XP_ links in Custom Scenery.
        var links: Set<TileCoord> = []
        if !customSceneryPath.isEmpty {
            let entries = (try? FileManager.default.contentsOfDirectory(atPath: customSceneryPath)) ?? []
            for name in entries where name.hasPrefix("zOrtho4XP_") {
                if let tile = TileMath.parse(String(name.dropFirst("zOrtho4XP_".count))) {
                    links.insert(TileCoord(lat: tile.lat, lon: tile.lon))
                }
            }
        }
        installed = links
    }

    private func legacySteps() -> [String] {
        var steps: [String] = []
        if doVector { steps += ["vector", "mesh", "masks"] }
        if doImagery { steps.append("dsf") }
        if doOverlays { steps.append("overlay") }
        return steps
    }

    private func startLegacyBuild(_ todo: [TileCoord]) {
        guard !isBuilding else { return }
        isBuilding = true
        isStopping = false
        activity.reset()
        legacyQueue = todo
        legacyDone = 0
        legacyFailed = 0
        for coord in todo {
            activity.tiles[coord] = TileProgress(state: .queued, label: "queued", percent: 0)
            activity.runOrder.append(coord)
        }
        activity.totalTiles = todo.count
        legacyRunNext()
    }

    private func legacyRunNext() {
        guard let engine, let tile = legacyQueue.first else {
            legacyFinish()
            return
        }
        legacyQueue.removeFirst()
        activity.tiles[tile] = TileProgress(state: .indeterminate, label: "starting…", percent: 0)
        legacyExitOutcome = nil
        let job = OrthoBuildJob(
            lat: tile.lat, lon: tile.lon, steps: legacySteps(),
            provider: buildProvider.isEmpty ? nil : buildProvider,
            zl: buildZL, buildDir: customBuildDir)
        console.append("=== Tile \(tile.key) ===")
        let runner = OrthoBuildRunner()
        legacyRunner = runner
        do {
            try runner.start(
                job: job, engine: engine,
                onEvent: { [weak self] event in
                    Task { @MainActor [weak self] in self?.legacyHandle(event, tile: tile) }
                },
                onExit: { [weak self] status in
                    Task { @MainActor [weak self] in
                        try? await Task.sleep(for: .milliseconds(250))
                        self?.legacyExited(tile: tile, status: status)
                    }
                })
        } catch {
            console.append("ERROR: could not launch the build driver: \(error.localizedDescription)")
            legacyFailed += 1
            legacyFinish()
        }
    }

    private func legacyHandle(_ event: OrthoBuildEvent, tile: TileCoord) {
        switch event {
        case .console(let line):
            console.append(line)
        case .progress(let bar, let percent):
            // Legacy bars: 1 mesh, 2 download, 3 convert — no whole-tile
            // model, so show the busiest bar as the tile's percent.
            if bar == 2 || bar == 3 {
                let label = bar == 2 ? "downloading" : "converting"
                activity.tiles[tile] = TileProgress(state: .active, label: label,
                                                    percent: Double(percent))
            }
        case .stepStarted(let step):
            activity.tiles[tile] = TileProgress(
                state: .indeterminate, label: OrthoBuildJob.stepLabel(step),
                percent: activity.tiles[tile]?.percent ?? 0)
        case .stepFinished(let step, let ok):
            if !ok { console.append("*** Step \(OrthoBuildJob.stepLabel(step)) failed.") }
        case .exit(let outcome):
            legacyExitOutcome = outcome
        case .fatal(let message):
            console.append("FATAL: \(message)")
        case .stopping:
            isStopping = true
        case .engineVersion, .stepSkipped:
            break
        }
    }

    private func legacyExited(tile: TileCoord, status: Int32) {
        let outcome = legacyExitOutcome ?? (isStopping ? .stopped : .fail)
        legacyRunner = nil
        switch outcome {
        case .ok:
            legacyDone += 1
            activity.tiles[tile] = TileProgress(state: .done, label: "done", percent: 100)
            activity.doneTiles = legacyDone
            selected.remove(tile)
            if linkTiles { legacySetInstalled(tile, true) }
        case .fail:
            legacyFailed += 1
            activity.tiles[tile] = TileProgress(state: .error, label: "failed", percent: 0)
            if status != 0, legacyExitOutcome == nil {
                console.append("*** Build process exited unexpectedly (status \(status)).")
            }
            if !legacyQueue.isEmpty {
                console.append("Remaining \(legacyQueue.count) tile(s) not started — fix the error above and build again.")
                legacyQueue = []
            }
        case .stopped:
            activity.tiles[tile] = TileProgress(state: .queued, label: "stopped", percent: 0)
            console.append("Build stopped.")
            legacyQueue = []
        }
        refreshTileStatesLegacy()
        if legacyQueue.isEmpty {
            legacyFinish()
        } else {
            legacyRunNext()
        }
    }

    private func legacyFinish() {
        isBuilding = false
        isStopping = false
        if legacyDone > 0 || legacyFailed > 0 {
            var parts = ["\(legacyDone) tile\(legacyDone == 1 ? "" : "s") built"]
            if legacyFailed > 0 { parts.append("\(legacyFailed) failed") }
            lastRunSummary = parts.joined(separator: ", ")
            console.append("=== Run complete: \(lastRunSummary!) ===")
        }
        clearProgressTask?.cancel()
        clearProgressTask = Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled, let self, !self.isBuilding else { return }
            self.activity.reset()
        }
    }

    private func legacySetInstalled(_ coord: TileCoord, _ install: Bool) {
        guard !customSceneryPath.isEmpty else { return }
        let name = OrthoEngine.tileFolderName(lat: coord.lat, lon: coord.lon)
        let target = URL(fileURLWithPath: customSceneryPath).appendingPathComponent(name)
        if install {
            guard let base = tileBaseFolder else { return }
            let source = base.appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath: source.path),
                  !FileManager.default.fileExists(atPath: target.path) else { return }
            do {
                try FileManager.default.createSymbolicLink(at: target, withDestinationURL: source)
                installed.insert(coord)
                console.append("Linked \(name) into Custom Scenery.")
            } catch {
                console.append("Could not link \(name): \(error.localizedDescription)")
            }
        } else {
            // Only remove a link, never a real folder.
            guard (try? FileManager.default.destinationOfSymbolicLink(atPath: target.path)) != nil
            else { return }
            try? FileManager.default.removeItem(at: target)
            installed.remove(coord)
            console.append("Removed \(name) from Custom Scenery.")
        }
    }
}
