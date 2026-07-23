import Foundation
import SwiftUI
import SceneryKit
import os

private let buildLog = Logger(subsystem: "com.novemberlima.XPTerrainBuilder", category: "build")

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

    /// Custom engine override. Empty = the engine bundled with the app.
    @AppStorage("OrthoEnginePath") var enginePath: String = "" {
        didSet { reloadEngine() }
    }
    /// The user's data folder: downloads, caches, built tiles and the
    /// engine's global config. Chosen on first run, changeable in Settings;
    /// handed to every engine process as ORTHO4XP_DATA_ROOT.
    @AppStorage(PrefKeys.dataRoot) var dataRootPath: String = "" {
        didSet {
            OrthoProcessRunner.dataRoot = dataRootPath.isEmpty ? nil : dataRootPath
            reloadEngine()
        }
    }
    @AppStorage("OrthoProvider") var buildProvider: String = ""
    /// The map's live-imagery preview source — independent of the build
    /// provider, switchable from the toolbar (OSM base map by default).
    @AppStorage("MapImageryPreview") var mapPreviewProvider: String = "OSM" {
        didSet {
            objectWillChange.send()
            imagery.setProvider(mapPreviewProvider)
        }
    }
    @AppStorage("OrthoZoomLevel") var buildZL: Int = 16
    @AppStorage("OrthoCustomBuildDir") var customBuildDir: String = ""
    /// Step groups, matching the Qt build box's three checkboxes.
    @AppStorage("OrthoDoVector") var doVector: Bool = true
    @AppStorage("OrthoDoImagery") var doImagery: Bool = true
    @AppStorage("OrthoDoOverlays") var doOverlays: Bool = false
    @AppStorage("OrthoSkipBuilt") var skipBuilt: Bool = true
    /// Install finished tiles into Custom Scenery automatically.
    @AppStorage("OrthoLinkTiles") var linkTiles: Bool = true

    /// Manage (the scenery doctor) is disabled for now — the app always
    /// runs the Build front-end. The Manage panes and their models stay in
    /// the codebase for when it returns.
    var mode: AppMode { .build }

    // MARK: Engine state

    @Published private(set) var engine: OrthoEngine?
    /// The active engine is the copy shipped with the app (no custom path).
    @Published private(set) var usingBundledEngine = false
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
    /// Built tiles whose textures folder mixes imagery sources (only one
    /// can be used) — warning badges on the map + selection pane.
    @Published private(set) var conflictTiles: Set<TileCoord> = []
    @Published private(set) var isScanning = false
    @Published private(set) var scanPhase = ""
    private var scanAccumBuilt: [TileCoord: O4TileInfo] = [:]
    private var scanAccumInstalled: Set<TileCoord> = []

    // MARK: Selection (Qt semantics: a set + one active tile)

    @Published var selected: Set<TileCoord> = []
    @Published var activeTile: TileCoord? {
        didSet { adoptActiveTileConfig() }
    }

    /// Selecting a built tile adopts its recorded imagery source and zoom
    /// level, so a rebuild doesn't silently use a different source. The
    /// user can still change either afterwards — startBuild then warns on
    /// the mismatch.
    private func adoptActiveTileConfig() {
        guard let coord = activeTile, let info = built[coord] else { return }
        if !info.provider.isEmpty { buildProvider = info.provider }
        if let zl = info.zl { buildZL = zl }
    }

    // MARK: Run state

    @Published private(set) var isBuilding = false
    @Published private(set) var isStopping = false
    @Published private(set) var lastRunSummary: String?

    let activity = BuildActivityModel()
    let console = BuildConsoleModel()
    /// Live map imagery for the selected provider (Qt-map parity).
    let imagery = ImageryModel()

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
        OrthoProcessRunner.dataRoot = dataRootPath.isEmpty ? nil : dataRootPath
        reloadEngine()
        loadCachedTileStates()
    }

    /// Optimistic launch for the build map: last session's built/installed
    /// tile squares appear immediately (the engine takes seconds just to
    /// boot); the first rescan revalidates and ScanDone swaps in the truth.
    private func loadCachedTileStates() {
        guard built.isEmpty, installed.isEmpty,
              let base = tileBaseFolder,
              let cached = TileScanCache.load(
                  workingDir: base.path, customSceneryDir: customSceneryPath)
        else { return }
        for info in cached.built {
            built[TileCoord(lat: info.lat, lon: info.lon)] = info
        }
        for pair in cached.installed where pair.count == 2 {
            installed.insert(TileCoord(lat: pair[0], lon: pair[1]))
        }
        refreshConflictTiles()
    }

    /// Re-audit ONE tile's textures folder and update its map badge —
    /// called after the selection pane's trash-cleanup so the warning
    /// clears immediately instead of waiting for the next scan.
    func reauditConflict(for coord: TileCoord) {
        guard let info = built[coord],
              !info.provider.isEmpty, !info.buildDir.isEmpty else {
            conflictTiles.remove(coord)
            return
        }
        let textures = URL(fileURLWithPath: info.buildDir, isDirectory: true)
            .appendingPathComponent("textures", isDirectory: true)
        let provider = info.provider
        Task { [weak self] in
            let conflict = await Task.detached(priority: .utility) {
                TileTextureAudit.hasForeignSources(
                    texturesDir: textures, currentProvider: provider)
            }.value
            guard let self else { return }
            if conflict {
                self.conflictTiles.insert(coord)
            } else {
                self.conflictTiles.remove(coord)
            }
        }
    }

    /// Background sweep over every built tile's textures folder for
    /// mixed-imagery-source conflicts (map warning badges). Names-only
    /// listings — one readdir per tile, no stat calls — so a full ortho
    /// install sweeps in a couple of seconds off the main thread.
    private var conflictAuditTask: Task<Void, Never>?

    private func refreshConflictTiles() {
        conflictAuditTask?.cancel()
        let snapshot: [(TileCoord, String, String)] = built.compactMap {
            coord, info in
            guard !info.provider.isEmpty, !info.buildDir.isEmpty else { return nil }
            return (coord, info.buildDir, info.provider)
        }
        conflictAuditTask = Task { [weak self] in
            let conflicts = await Task.detached(priority: .utility) { () -> Set<TileCoord> in
                var out: Set<TileCoord> = []
                for (coord, dir, provider) in snapshot {
                    if Task.isCancelled { break }
                    let textures = URL(fileURLWithPath: dir, isDirectory: true)
                        .appendingPathComponent("textures", isDirectory: true)
                    if TileTextureAudit.hasForeignSources(
                        texturesDir: textures, currentProvider: provider) {
                        out.insert(coord)
                    }
                }
                return out
            }.value
            guard !Task.isCancelled, let self else { return }
            self.conflictTiles = conflicts
        }
    }

    // MARK: - Engine loading

    /// The user's data folder as a URL; nil until first run has answered.
    var dataRootURL: URL? {
        dataRootPath.isEmpty ? nil : URL(fileURLWithPath: dataRootPath, isDirectory: true)
    }

    func reloadEngine() {
        engineError = nil
        disconnect()
        let resolved: OrthoEngine?
        if enginePath.isEmpty {
            // Default: the engine copy shipped with the app.
            resolved = OrthoEngine.bundled()
            usingBundledEngine = resolved != nil
            if resolved == nil {
                engineError = "The bundled Ortho4XP engine is missing from this copy of the app."
            }
        } else {
            usingBundledEngine = false
            resolved = OrthoEngine.locate(at: URL(fileURLWithPath: enginePath, isDirectory: true))
            if resolved == nil {
                engineError = "Not recognized as an Ortho4XP folder (needs Ortho4XP.py and src/)."
            }
        }
        guard let located = resolved else {
            engine = nil
            providers = []
            missingPackages = nil
            usesProtocol = false
            imagery.configure(providersDir: nil, extentsDir: nil, dataRoot: dataRootURL)
            return
        }
        imagery.configure(
            providersDir: located.resourcesRoot.appendingPathComponent("Providers", isDirectory: true),
            extentsDir: located.resourcesRoot.appendingPathComponent("Extents", isDirectory: true),
            dataRoot: dataRootURL)
        imagery.setProvider(mapPreviewProvider)
        engine = located
        providers = located.providers()
        usesProtocol = OrthoEngineClient.engineSupportsProtocol(located)
        reloadGlobalConfig()
        seedPathsFromXPlane()
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

    /// The custom build dir in the form the engine expects: a TRAILING
    /// SEPARATOR means "create zOrtho4XP_* subfolders here"; without it the
    /// engine uses the path verbatim as one tile's build dir and dumps the
    /// tile's contents straight into it (legacy convention — the Qt GUI
    /// appends the separator the same way).
    private var engineCustomBuildDir: String {
        guard !customBuildDir.isEmpty else { return "" }
        return customBuildDir.hasSuffix("/") ? customBuildDir : customBuildDir + "/"
    }

    var tileBaseFolder: URL? {
        guard let engine else { return nil }
        if !customBuildDir.isEmpty {
            return URL(fileURLWithPath: customBuildDir, isDirectory: true)
        }
        // Tiles live under the data folder; the engine puts them there too
        // (ORTHO4XP_DATA_ROOT). No data root chosen yet → the engine's own
        // Tiles/, the pre-data-root behavior.
        if let dataRoot = dataRootURL {
            return dataRoot.appendingPathComponent("Tiles", isDirectory: true)
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
        if expectedEngineStop {
            expectedEngineStop = false
            console.append("=== Build stopped. ===")
            isBuilding = false
            isStopping = false
            activity.reset()
            // A fresh session reconnects lazily; refresh what's on disk.
            rescan()
            return
        }
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
            if let base = tileBaseFolder {
                TileScanCache.save(
                    built: Array(built.values),
                    installed: installed.map { [$0.lat, $0.lon] },
                    workingDir: base.path, customSceneryDir: customSceneryPath)
            }
            refreshConflictTiles()
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

    // MARK: - Legacy tile settings (built by an older/other Ortho4XP)

    /// Everything about a tile cfg that an older or different Ortho4XP
    /// wrote and this engine interprets rather than takes literally —
    /// surfaced to the user with an offer to modernize the file.
    struct LegacyTileSettings {
        let coord: TileCoord
        let cfgURL: URL
        /// Still the pre-per-tile generic name (Ortho4XP.cfg).
        let usesLegacyFileName: Bool
        /// Enum values this engine doesn't define, with the replacement
        /// an update would write (current global value, else the
        /// registry default).
        let foreignEnums: [(key: String, value: String, replacement: String)]
        /// Keys carrying legacy quoted values ('Arc').
        let quotedKeys: [String]
        /// custom_dem pins whose file no longer exists.
        let missingPins: [String]

        var isEmpty: Bool {
            !usesLegacyFileName && foreignEnums.isEmpty
                && quotedKeys.isEmpty && missingPins.isEmpty
        }
    }

    static func unquoteCfgValue(_ value: String) -> String {
        guard value.count >= 2, let first = value.first,
              first == value.last, first == "'" || first == "\""
        else { return value }
        return String(value.dropFirst().dropLast())
    }

    /// Inspect a built tile's cfg for legacy markers. nil = nothing to say.
    func legacyTileSettings(for coord: TileCoord) -> LegacyTileSettings? {
        guard let info = built[coord], !info.buildDir.isEmpty else { return nil }
        let dir = URL(fileURLWithPath: info.buildDir, isDirectory: true)
        let canonical = dir.appendingPathComponent("Ortho4XP_\(coord.key).cfg")
        let generic = dir.appendingPathComponent("Ortho4XP.cfg")
        let fm = FileManager.default
        let usesLegacyName: Bool
        let cfgURL: URL
        if fm.fileExists(atPath: canonical.path) {
            cfgURL = canonical
            usesLegacyName = false
        } else if fm.fileExists(atPath: generic.path) {
            cfgURL = generic
            usesLegacyName = true
        } else {
            return nil
        }
        guard let file = try? OrthoConfigFile(contentsOf: cfgURL) else { return nil }
        var quoted: [String] = []
        var foreign: [(key: String, value: String, replacement: String)] = []
        var missingPins: [String] = []
        for (key, raw) in file.rawValues {
            let value = raw.trimmingCharacters(in: .whitespaces)
            let bare = Self.unquoteCfgValue(value)
            if bare != value { quoted.append(key) }
            if key == "custom_dem" {
                for token in bare.split(separator: ";").map(String.init)
                where token.hasPrefix("/") && !fm.fileExists(atPath: token) {
                    missingPins.append(token)
                }
                continue
            }
            if let variable = schema.vars[key],
               variable.type == "str",
               let allowed = variable.values, !allowed.isEmpty,
               !allowed.contains(bare) {
                let replacement = globalConfigValues[key]?.cfgLiteral
                    ?? variable.default.cfgLiteral
                foreign.append((key, bare, Self.unquoteCfgValue(replacement)))
            }
        }
        let result = LegacyTileSettings(
            coord: coord, cfgURL: cfgURL, usesLegacyFileName: usesLegacyName,
            foreignEnums: foreign.sorted { $0.key < $1.key },
            quotedKeys: quoted.sorted(), missingPins: missingPins.sorted())
        return result.isEmpty ? nil : result
    }

    /// "Update to current defaults": reduce the per-tile cfg to the
    /// tile's IDENTITY — imagery source, zoom level, hand-drawn zones —
    /// so every other setting falls back to the current global config,
    /// exactly as if the tile were newly created today. Effectively
    /// "delete the tile config", except the keys other features rely on
    /// (source adoption, the mismatch guard, the imagery audit) and the
    /// user's zone work survive. Originals stay as .bak / .legacy.
    func updateLegacyTileSettings(_ legacy: LegacyTileSettings) {
        guard let source = try? OrthoConfigFile(contentsOf: legacy.cfgURL) else { return }
        let raw = source.rawValues
        var lines: [String] = []
        for key in ["default_website", "default_zl", "zone_list"] {
            guard let value = raw[key] else { continue }
            let bare = Self.unquoteCfgValue(value.trimmingCharacters(in: .whitespaces))
            lines.append("\(key)=\(bare)")
        }
        let file = OrthoConfigFile(lines: lines)
        let destination = legacy.usesLegacyFileName
            ? legacy.cfgURL.deletingLastPathComponent()
                .appendingPathComponent("Ortho4XP_\(legacy.coord.key).cfg")
            : legacy.cfgURL
        do {
            try file.write(to: destination)
            if legacy.usesLegacyFileName {
                let backup = legacy.cfgURL.appendingPathExtension("legacy")
                try? FileManager.default.removeItem(at: backup)
                try? FileManager.default.moveItem(at: legacy.cfgURL, to: backup)
            }
            console.append("Tile \(legacy.coord.key): settings reset to current defaults (imagery source, ZL and zones kept).")
            rescan()
        } catch {
            engineError = "Could not update the tile config: \(error.localizedDescription)"
        }
    }

    // MARK: Imagery-source mismatch guard

    struct ProviderMismatch: Identifiable {
        let coord: TileCoord
        /// The tile's recorded imagery source (from its cfg).
        let provider: String
        let zl: Int?
        var id: String { coord.key }
    }

    /// Buildable tiles whose recorded imagery source differs from the
    /// build provider — the accidental-rebuild guard. Selection adopts the
    /// active tile's source, so this is non-empty only after the user
    /// changed the source with tiles selected.
    var providerMismatches: [ProviderMismatch] {
        guard !buildProvider.isEmpty else { return [] }
        return buildableSelection.compactMap { coord in
            guard let info = built[coord], !info.provider.isEmpty,
                  info.provider.lowercased() != buildProvider.lowercased()
            else { return nil }
            return ProviderMismatch(coord: coord, provider: info.provider, zl: info.zl)
        }
    }

    func startBuild() {
        startBuild(batches: [(buildableSelection, buildProvider, buildZL)])
    }

    /// Batched build: each batch carries its own imagery source and ZL
    /// (enqueue_build keeps per-batch settings). The legacy fallback can't
    /// do per-batch sources and always uses the current build settings.
    func startBuild(batches: [(tiles: [TileCoord], provider: String, zl: Int)]) {
        guard canBuild else { return }
        lastRunSummary = nil
        if usesProtocol {
            for batch in batches where !batch.tiles.isEmpty {
                startProtocolBuild(batch.tiles, provider: batch.provider, zl: batch.zl)
            }
        } else {
            startLegacyBuild(batches.flatMap(\.tiles))
        }
    }

    /// Mismatch resolution "rebuild with the new source, clean": trash the
    /// mismatched tiles' textures from other sources first, then build
    /// everything with the current settings. The engine rewrites each
    /// tile's cfg with the new source during the build.
    func startBuildDeletingOldImagery() {
        let dirs: [URL] = providerMismatches.compactMap { mismatch in
            guard let info = built[mismatch.coord], !info.buildDir.isEmpty else { return nil }
            return URL(fileURLWithPath: info.buildDir, isDirectory: true)
                .appendingPathComponent("textures", isDirectory: true)
        }
        let provider = buildProvider
        Task { [weak self] in
            await Task.detached(priority: .utility) {
                for dir in dirs {
                    guard let audit = TileTextureAudit.scan(
                        texturesDir: dir, currentProvider: provider) else { continue }
                    for url in audit.foreignFiles {
                        try? FileManager.default.trashItem(at: url, resultingItemURL: nil)
                    }
                }
            }.value
            guard let self else { return }
            self.console.append("Old-source imagery moved to the Trash for \(dirs.count) tile\(dirs.count == 1 ? "" : "s").")
            self.startBuild()
        }
    }

    /// Mismatch resolution "keep each tile as it was": mismatched tiles
    /// build with their ORIGINAL source and ZL (grouped into batches);
    /// everything else uses the current build settings.
    func startBuildKeepingOriginalSources() {
        let mismatches = providerMismatches
        let mismatched = Set(mismatches.map(\.coord))
        var batches: [(tiles: [TileCoord], provider: String, zl: Int)] = []
        let current = buildableSelection.filter { !mismatched.contains($0) }
        if !current.isEmpty {
            batches.append((current, buildProvider, buildZL))
        }
        let groups = Dictionary(grouping: mismatches) { "\($0.provider)|\($0.zl ?? buildZL)" }
        for group in groups.values.sorted(by: { $0[0].coord < $1[0].coord }) {
            batches.append((group.map(\.coord).sorted(),
                            group[0].provider,
                            group[0].zl ?? buildZL))
        }
        startBuild(batches: batches)
    }

    private func startProtocolBuild(_ todo: [TileCoord], provider: String, zl: Int) {
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
            "provider": provider,
            "zoomlevel": zl,
            "custom_build_dir": engineCustomBuildDir,
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

    /// Whole-run stop (the ■ Stop button): cooperative cancel first (the
    /// engine aborts at its next check), escalating to process termination
    /// after a short grace window — a slow tile download or a wedged
    /// server must never hold the user hostage. The engine restarts
    /// lazily on the next action; builds are re-runnable (atomic writes,
    /// per-airport caches), so a hard stop loses at most in-flight work.
    private var hardStopTask: Task<Void, Never>?
    private var expectedEngineStop = false

    func stopBuild() {
        guard isBuilding else { return }
        isStopping = true
        if usesProtocol {
            client?.send(command: "cancel")
            console.append("Stopping — cancelling the engine (forced in 5 s if it doesn't wind down)…")
            hardStopTask?.cancel()
            hardStopTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self, self.isBuilding else { return }
                self.hardStopEngine()
            }
        } else {
            legacyQueue = []
            legacyRunner?.requestStop()
        }
    }

    private func hardStopEngine() {
        console.append("Engine still busy — terminating it now.")
        expectedEngineStop = true
        client?.terminate()
        Task { [weak self] in
            try? await Task.sleep(for: .seconds(3))
            self?.client?.kill()   // no-op once the process has exited
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
              let file = try? OrthoConfigFile(contentsOf: engine.globalConfigURL(dataRoot: dataRootURL)) else {
            globalConfigValues = [:]
            return
        }
        globalConfigValues = file.values(schema: schema)
    }

    func configValue(for name: String) -> O4Value? {
        globalConfigValues[name] ?? schema.vars[name]?.default
    }

    /// Fill empty engine paths from the X-Plane folder (Qt parity:
    /// _seed_paths_from_xplane): Custom Scenery, the overlay source, and
    /// the CIFP/AIRAC data folder (Custom Data/CIFP — Navigraph updates —
    /// preferred over Resources/default data/CIFP). Never overwrites a
    /// user-set value.
    func seedPathsFromXPlane() {
        guard engine != nil else { return }
        let xplane = UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? ""
        guard !xplane.isEmpty else { return }
        let root = URL(fileURLWithPath: xplane, isDirectory: true)
        var seeds: [(name: String, url: URL)] = []
        func consider(_ name: String, _ candidates: [URL]) {
            let currentValue = globalConfigValues[name]?.cfgLiteral ?? ""
            guard currentValue.isEmpty else { return }
            for candidate in candidates
            where FileManager.default.fileExists(atPath: candidate.path) {
                seeds.append((name, candidate))
                return
            }
        }
        consider("custom_scenery_dir", [root.appendingPathComponent("Custom Scenery")])
        consider("custom_overlay_src", [root.appendingPathComponent("Global Scenery")])
        consider("cifp_data_path", [
            root.appendingPathComponent("Custom Data/CIFP"),
            root.appendingPathComponent("Resources/default data/CIFP"),
        ])
        for seed in seeds {
            setConfigValue(seed.name, to: .string(seed.url.path))
            console.append("Derived \(seed.name) from the X-Plane folder: \(seed.url.path)")
        }
    }

    /// Options for base_elevation_source: auto + the legacy keywords +
    /// every role=base elevation provider the engine ships
    /// (Providers/Elevation/<CODE>.elv). The engine registry can't list
    /// these (they're files), so the picker enumerates them here.
    var elevationSourceOptions: [String] {
        var options = ["auto", "View", "SRTM", "NED1", "NED1/3", "ALOS"]
        if let engine {
            let dir = engine.resourcesRoot.appendingPathComponent("Providers/Elevation")
            let entries = (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []
            options += entries.filter { $0.hasSuffix(".elv") }
                .map { String($0.dropLast(4)) }
                .filter { !options.contains($0) }
                .sorted()
        }
        return options
    }

    // MARK: - Tile-scope config (Qt blended-view semantics)
    //
    // With tiles selected on the map, tile-scope settings edit those tiles'
    // Ortho4XP_±xx±yyy.cfg files as sparse overrides: a value equal to the
    // global effective value REMOVES the override. With no selection they
    // edit the global defaults. App-scope settings always edit the global
    // config.

    /// Bumped after any tile-config write so rows re-read their state.
    @Published private(set) var tileConfigGeneration = 0

    private func tileConfigURL(_ coord: TileCoord) -> URL? {
        guard let base = tileBaseFolder else { return nil }
        let key = TileMath.key(lat: coord.lat, lon: coord.lon)
        return base.appendingPathComponent(OrthoEngine.tileFolderName(lat: coord.lat, lon: coord.lon))
            .appendingPathComponent("Ortho4XP_\(key).cfg")
    }

    private func tileOverride(_ coord: TileCoord, _ name: String) -> O4Value? {
        guard let url = tileConfigURL(coord),
              let file = try? OrthoConfigFile(contentsOf: url) else { return nil }
        return file.values(schema: schema)[name]
    }

    /// The selected tiles' override for one setting.
    enum OverrideState: Equatable {
        case none
        /// Every selected tile carries the same override.
        case uniform(O4Value)
        /// Selected tiles disagree (some overridden, or different values).
        case mixed
    }

    func overrideState(for name: String) -> OverrideState {
        guard !selected.isEmpty else { return .none }
        // Engine-built tiles carry COMPLETE configs — a key merely being
        // present is not a customization. Only values that differ from the
        // global effective value count.
        let global = configValue(for: name)
        var seen: [O4Value?] = []
        for coord in selected {
            var value = tileOverride(coord, name)
            if let v = value, let global, v == global { value = nil }
            seen.append(value)
            if seen.count > 1, seen.last != seen.first { return .mixed }
        }
        if let first = seen.first, let value = first {
            return .uniform(value)
        }
        return .none
    }

    /// The value a settings row should display for its scope: uniform tile
    /// override when present, else the global value, else the schema default.
    func effectiveValue(for item: SettingItem) -> O4Value? {
        if item.scope == .tile, case .uniform(let value) = overrideState(for: item.name) {
            return value
        }
        return configValue(for: item.name)
    }

    /// Writes a settings row's new value to the right place for its scope.
    func setValue(for item: SettingItem, to value: O4Value) {
        guard item.scope == .tile, !selected.isEmpty else {
            setConfigValue(item.name, to: value)
            return
        }
        let inherited = configValue(for: item.name)
        for coord in selected {
            guard let url = tileConfigURL(coord) else { continue }
            var file = (try? OrthoConfigFile(contentsOf: url)) ?? OrthoConfigFile()
            if let inherited, value == inherited {
                file.remove(item.name)
            } else {
                file.set(item.name, to: value)
            }
            do {
                try FileManager.default.createDirectory(
                    at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
                try file.write(to: url)
            } catch {
                engineError = "Could not write \(url.lastPathComponent): \(error.localizedDescription)"
            }
        }
        tileConfigGeneration += 1
    }

    /// Every config variable the current selection actually customizes —
    /// values in tile configs that DIFFER from the global effective value.
    /// (Engine-built tiles write complete configs; matching values aren't
    /// customizations.) Drives the "Selected Overrides" settings sections.
    func overriddenNames() -> Set<String> {
        guard !selected.isEmpty else { return [] }
        var names: Set<String> = []
        for coord in selected {
            guard let url = tileConfigURL(coord),
                  let file = try? OrthoConfigFile(contentsOf: url) else { continue }
            for (name, value) in file.values(schema: schema)
            where configValue(for: name) != value {
                names.insert(name)
            }
        }
        return names
    }

    /// Removes the selected tiles' overrides for the given settings.
    func revertTileOverrides(for names: [String]) {
        for coord in selected {
            guard let url = tileConfigURL(coord),
                  var file = try? OrthoConfigFile(contentsOf: url) else { continue }
            for name in names { file.remove(name) }
            try? file.write(to: url)
        }
        tileConfigGeneration += 1
    }

    func revertTileOverrides(for name: String) {
        revertTileOverrides(for: [name])
    }

    /// Engine gate for auto-patch object reseating inside installed custom
    /// airport packs. A global Ortho4XP.cfg var (modify_custom_airports),
    /// NOT a per-run argument: config reaches parallel worker children,
    /// and the Qt front end reads the same switch. Default matches the
    /// engine's (on).
    var modifyCustomAirports: Bool {
        globalConfigValues["modify_custom_airports"]?.boolValue ?? true
    }

    func setModifyCustomAirports(_ enabled: Bool) {
        setConfigValue("modify_custom_airports", to: .bool(enabled))
    }

    func setConfigValue(_ name: String, to value: O4Value) {
        guard let engine else { return }
        let configURL = engine.globalConfigURL(dataRoot: dataRootURL)
        var file = (try? OrthoConfigFile(contentsOf: configURL)) ?? OrthoConfigFile()
        file.set(name, to: value)
        do {
            try FileManager.default.createDirectory(
                at: configURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try file.write(to: configURL)
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
            zl: buildZL, buildDir: engineCustomBuildDir)
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
