import Foundation
import SwiftUI
import SceneryKit
import os

private let buildLog = Logger(subsystem: "com.novemberlima.XPTerrainBuilder", category: "build")

/// One tile's live build progress — the Qt map badge / activity row model.
/// state mirrors the protocol's TileState vocabulary, plus ONE app-local
/// member the engine never sends: `.stopped`. Stopping a tile is a local
/// state change (the engine only notices its cancel flag at the next phase
/// boundary — minutes on a mesh phase), so the row must say "stopped" the
/// instant it is clicked, not when the engine gets around to agreeing.
struct TileProgress: Equatable {
    enum State: String {
        case queued, active, indeterminate, done, error, stopped
    }
    var state: State
    var label: String
    var percent: Double
    /// The engine's sentence for a stopped tile — what it is left with
    /// (TileState.detail, #598). Shown under the row, verbatim.
    var detail: String = ""
}

/// The build settings a tile's run was STARTED with, snapshotted per tile so
/// resuming a stopped tile rebuilds it as it was queued — not with whatever
/// the pickers happen to say when the user presses resume.
struct TileRunSettings: Equatable {
    var provider: String
    var zl: Int
}

/// High-frequency build activity (per-tile progress, run clock), isolated
/// from BuildModel like ProgressModel is from AnalysisController. The map
/// canvas and activity rows observe this; StepProgress ticks never touch
/// the rest of the window.
///
/// The rows outlive their run (#1341): a finished row (done, built with
/// warnings, failed, stopped) stays until the app quits. `runTiles` is
/// the run in progress, or the one that just ended until its linger is
/// over — what the map's badges and "Build failed tiles again" describe.
@MainActor
final class BuildActivityModel: ObservableObject {
    @Published var tiles: [BuildModel.TileCoord: TileProgress] = [:] {
        didSet { restamp() }
    }
    /// Every row, in the order the rows were made; `displayOrder` is the
    /// order the Activity box shows them in.
    @Published var runOrder: [BuildModel.TileCoord] = [] {
        didSet { restamp() }
    }
    @Published var runTiles: Set<BuildModel.TileCoord> = []
    @Published var elapsedSeconds: Double = 0
    /// nil = no defensible estimate — render a dash, never a wild number.
    @Published var remainingSeconds: Double?
    /// The estimate has been GROWING (model outlived by a download or an
    /// unsignalled step) — display "still estimating", not the number.
    @Published var remainingUnreliable = false
    @Published var doneTiles = 0
    @Published var totalTiles = 0
    /// Per-tile clocks (TileClocks, protocol 1.3), keyed like `tiles`.
    /// Kept apart from TileProgress so the wholesale row replacement in
    /// the TileState/StepProgress handlers can never stomp a clock.
    @Published var tileClocks: [BuildModel.TileCoord: O4TileClock] = [:]
    /// What each tile was started with — the resume path's settings
    /// source (a resume must not adopt today's pickers).
    @Published var runSettings: [BuildModel.TileCoord: TileRunSettings] = [:]
    /// The title codes after each row's coordinate: the tile's largest
    /// airports, a searched one first (#815, #667) — stamped when queued.
    @Published var runTags: [BuildModel.TileCoord: String] = [:]
    /// A finished row's end-of-build messages (#1341): its gold or red
    /// status reopens them for as long as the row exists.
    @Published var issues: [BuildModel.TileCoord: O4TileIssues] = [:]
    /// Each row's step strip (#825): Map data → Airports → … → Install.
    /// Protocol builds only; a row without one shows no strip.
    @Published var stepStrips: [BuildModel.TileCoord: O4StepStrip] = [:]

    /// Each row's place in the list (`ActivityOrder`).
    private var stamps: [BuildModel.TileCoord: ActivityOrder.Stamp] = [:]
    private var stampCounter = 0

    /// Live rows newest batch first, then finished rows in finish order.
    var displayOrder: [BuildModel.TileCoord] {
        ActivityOrder.order(runOrder.filter { tiles[$0] != nil }, stamps: stamps)
    }

    /// The rows the map draws a badge for: this run's, and any row still
    /// live or waiting for a resume.
    var badges: [BuildModel.TileCoord: TileProgress] {
        tiles.filter {
            runTiles.contains($0.key) || $0.value.state == .stopped
                || !Self.isFinished($0.value)
        }
    }

    nonisolated static func isFinished(_ row: TileProgress) -> Bool {
        ActivityOrder.isFinished(state: row.state.rawValue, label: row.label)
    }

    private func restamp() {
        let rows: [(key: BuildModel.TileCoord, finished: Bool)] = runOrder.compactMap { coord in
            guard let row = tiles[coord] else { return nil }
            return (key: coord, finished: Self.isFinished(row))
        }
        let next = ActivityOrder.restamp(rows, stamps: stamps, counter: stampCounter)
        stamps = next.stamps
        stampCounter = next.counter
    }

    /// A new run: its counters start at zero; earlier rows stay.
    func beginRun() {
        elapsedSeconds = 0
        remainingSeconds = nil
        doneTiles = 0
        totalTiles = 0
        runTiles = []
    }

    /// Put `coords` on the list as queued, as ONE batch at the top: a
    /// new row, or a finished one being built again. A row still live
    /// in this run is left as it is.
    func queueRows(_ coords: [BuildModel.TileCoord]) {
        var next = tiles
        var order = runOrder
        for coord in coords {
            if let row = next[coord], !Self.isFinished(row) { continue }
            next[coord] = TileProgress(state: .queued, label: "queued", percent: 0)
            issues[coord] = nil
            tileClocks[coord] = nil
            if !order.contains(coord) { order.append(coord) }
        }
        runTiles.formUnion(coords)
        runOrder = order
        tiles = next
    }

    /// The run is over (its linger, or the engine gone): the run's
    /// header, clock and map badges go, and so does any row the run left
    /// live (a tile it never started); every finished row stays.
    func endRun() {
        dropLiveRows()
        runTiles = []
        totalTiles = 0
        doneTiles = 0
    }

    private func dropLiveRows() {
        let live = Set(tiles.filter { !Self.isFinished($0.value) }.keys)
        guard !live.isEmpty else { return }
        runOrder.removeAll { live.contains($0) }
        tiles = tiles.filter { !live.contains($0.key) }
        for coord in live {
            tileClocks[coord] = nil
            stepStrips[coord] = nil
        }
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
    /// handed to every engine process as ORTHO4XP_DATA_ROOT, and shared
    /// with the Qt app through DataRootPointer (#1266).
    @AppStorage(PrefKeys.dataRoot) var dataRootPath: String = "" {
        didSet {
            OrthoProcessRunner.dataRoot = dataRootPath.isEmpty ? nil : dataRootPath
            DataRootPointer.write(dataRootPath)
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
    /// Built or selected tiles whose cfg customizes a setting (#1350) —
    /// the map's settings badge. The engine owns the comparison
    /// (`tile_customizations`, O4_Tile_Customizations.py).
    @Published private(set) var customizedTiles: Set<TileCoord> = []
    /// Tiles with a custom patch, and its file names (#1229, RULINGS
    /// 2026-10-26c) — the map's orange band and the tile pane's "Custom
    /// patch" row. The engine owns the rule (`custom_patches`,
    /// O4_Custom_Patches.py).
    @Published private(set) var customPatchTiles: [TileCoord: [String]] = [:]
    @Published private(set) var isScanning = false
    @Published private(set) var scanPhase = ""
    private var scanAccumBuilt: [TileCoord: O4TileInfo] = [:]
    private var scanAccumInstalled: Set<TileCoord> = []
    /// (elapsed, remaining) pairs from recent runEta events — the
    /// climbing-estimate detector's window.
    private var etaSamples: [(at: Double, value: Double)] = []

    // MARK: Selection (Qt semantics: a set + one active tile)

    @Published var selected: Set<TileCoord> = [] {
        didSet {
            persistSelection()
            refreshCustomizedTiles(only: selected.subtracting(oldValue))
            searchTags.keep(only: Set(selected.map { AirportTile(lat: $0.lat, lon: $0.lon) }))
        }
    }
    /// The search codes that picked each selected tile (#667); a search
    /// adds them, deselecting drops them. Session state only.
    var searchTags = TileSearchTags()
    @Published var activeTile: TileCoord? {
        didSet {
            adoptActiveTileConfig()
            persistSelection()
        }
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

    /// Both selection keys, rewritten whole on every change. A selection is
    /// hand-sized (the user clicks tiles), so there is nothing to debounce.
    private func persistSelection() {
        let defaults = UserDefaults.standard
        defaults.set(selected.sorted().map(\.key), forKey: PrefKeys.selectedTiles)
        defaults.set(activeTile?.key ?? "", forKey: PrefKeys.activeTile)
    }

    /// The selection outlives the app: last session's selected set and
    /// active tile come back on launch, the same doctrine as the
    /// built/installed squares. Runs AFTER loadCachedTileStates so the
    /// active tile's config adoption sees `built` exactly as it does on a
    /// user click. Keys that no longer parse are dropped silently, and an
    /// active tile outside the restored set falls back to the set's first
    /// tile — the deselect path's rule.
    private func restoreSelection() {
        let defaults = UserDefaults.standard
        let stored = defaults.stringArray(forKey: PrefKeys.selectedTiles) ?? []
        selected = Set(stored.compactMap(TileMath.parse)
            .map { TileCoord(lat: $0.lat, lon: $0.lon) })
        let active = defaults.string(forKey: PrefKeys.activeTile)
            .flatMap(TileMath.parse)
            .map { TileCoord(lat: $0.lat, lon: $0.lon) }
        activeTile = active.flatMap { selected.contains($0) ? $0 : nil }
            ?? selected.sorted().first
    }

    // MARK: Run state

    @Published private(set) var isBuilding = false
    @Published private(set) var isStopping = false
    @Published private(set) var lastRunSummary: String?

    let activity = BuildActivityModel()
    let console = BuildConsoleModel()
    /// Live map imagery for the selected provider (Qt-map parity).
    let imagery = ImageryModel()

    /// Provider accounts the engine can sign into (auth_providers), and the
    /// last sign-in / sign-out outcome the engine reported.
    @Published private(set) var providerAccounts: [O4ProviderAccount] = []
    @Published private(set) var lastSignInResult: ProviderSignInResult?
    private var signInResultCounter = 0

    // MARK: Default airport index (protocol 1.6)

    /// X-Plane's default (Global Airports) airports, as the engine's index
    /// reports them. The engine OWNS the apt.dat parse
    /// (src/O4_Airport_Index.py, the `airport_index` command); this app
    /// only reads the TSV cache the engine points it at.
    private(set) var globalAirports: [GlobalAirport] = [] {
        didSet { largestAirportsByTile = nil }
    }
    /// Code / name search over `globalAirports` (#543), rebuilt off the
    /// main thread whenever the index is published.
    @Published private(set) var airportSearch = AirportSearch([])
    /// Each tile's largest airports (#815), built from `globalAirports`
    /// the first time a run needs it and dropped when the index changes.
    private var largestAirportsByTile: [AirportTile: [String]]?
    /// Where the index goes once it is read — the map controller, wired at
    /// construction (see XPTerrainBuilderApp). Setting it delivers whatever
    /// has already arrived, so an optimistic read that beat the wiring is
    /// not lost.
    var onGlobalAirports: (([GlobalAirport]) -> Void)? {
        didSet {
            guard !globalAirports.isEmpty else { return }
            onGlobalAirports?(globalAirports)
        }
    }
    /// The engine has answered `airport_index` at least once — after that
    /// the optimistic cache read is stale by definition and must not
    /// overwrite it (whichever of the two finishes first).
    private var engineAnsweredAirportIndex = false

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
        DataRootPointer.write(dataRootPath)
        reloadEngine()
        loadCachedTileStates()
        loadCachedGlobalAirports()
        restoreSelection()
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

    // MARK: - Customized tile settings (#1350)

    /// One tile's customized settings, for the tile pane. Empty when it
    /// customizes nothing, or the engine predates the command.
    func tileCustomizations(for coord: TileCoord) async -> [O4TileCustomization] {
        connectIfNeeded()
        guard let client, let base = tileBaseFolder else { return [] }
        let reply = try? await client.tileCustomizations(
            lat: coord.lat, lon: coord.lon, workingDir: base.path)
        return reply?.customizations ?? []
    }

    /// Ask the engine again for the badge set: every built and selected
    /// tile, or only `coords` (newly selected tiles). One small cfg read
    /// per tile on the engine side.
    func refreshCustomizedTiles(only coords: Set<TileCoord>? = nil) {
        let scope = coords ?? Set(built.keys).union(selected)
        guard !scope.isEmpty, client != nil else { return }
        Task { [weak self] in
            var found: Set<TileCoord> = []
            for coord in scope {
                guard let self else { return }
                let rows = await self.tileCustomizations(for: coord)
                if !rows.isEmpty { found.insert(coord) }
            }
            guard let self else { return }
            self.customizedTiles = self.customizedTiles.subtracting(scope).union(found)
        }
    }

    /// Ask the engine again for every tile with a custom patch (#1229).
    /// An engine without the command leaves the bands as they were.
    func refreshCustomPatchTiles() {
        connectIfNeeded()
        guard let client else { return }
        Task { [weak self] in
            guard let reply = try? await client.customPatches() else { return }
            var found: [TileCoord: [String]] = [:]
            for row in reply.tiles where !row.files.isEmpty {
                found[TileCoord(lat: row.lat, lon: row.lon)] = row.files
            }
            self?.customPatchTiles = found
        }
    }

    /// "Use auto patch" in the tile pane (#1229): the engine renames the
    /// tile's custom patches to `….disabled` — never deletes them — so the
    /// next build auto-patches those airports.
    func useAutoPatch(for coord: TileCoord) {
        connectIfNeeded()
        guard let client, !isBuilding else { return }
        Task { [weak self] in
            do {
                let reply = try await client.useAutoPatch(tile: coord.key)
                for path in reply.setAside {
                    self?.console.append(
                        "Tile \(coord.key): set the custom patch aside as \((path as NSString).lastPathComponent); the next build uses the auto patch.")
                }
            } catch {
                self?.engineError = error.localizedDescription
            }
            self?.refreshCustomPatchTiles()
        }
    }

    /// "Edit settings…" in the tile pane: select the tile alone, so the
    /// Settings window edits it, and open on its Selected Overrides pane.
    func editSettings(for coord: TileCoord) {
        selected = [coord]
        activeTile = coord
        settingsPaneRequest = SettingsPaneRequest.overrides
    }

    /// The Settings pane to show next time the window appears (#1350);
    /// SettingsView takes it and clears it.
    @Published var settingsPaneRequest: String?

    enum SettingsPaneRequest {
        static let overrides = "overrides"
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
                engineError = "The bundled build engine is missing from this copy of the app."
            }
        } else {
            usingBundledEngine = false
            resolved = OrthoEngine.locate(at: URL(fileURLWithPath: enginePath, isDirectory: true))
            if resolved == nil {
                engineError = "Not recognized as a build engine folder (needs Ortho4XP.py and src/)."
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
        connectIfNeeded()

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
                // Not only on the first-run page: a user who never saw it
                // starts from the default preset too (owner 2026-10-22).
                self.applyDefaultPresetIfUnset()
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
            console.append("Engine session started (engine \(engine.version)).")
            rescan()
            refreshAirportIndex()
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
        forgetStopState()
        // Finished rows stay until the app quits (#1341); a live row has
        // no engine left to finish it.
        activity.endRun()
    }

    private func sessionExited(_ status: Int32) {
        guard client != nil else { return }
        client = nil
        if expectedEngineStop {
            expectedEngineStop = false
            console.append("=== Build stopped. ===")
            isBuilding = false
            isStopping = false
            forgetStopState()
            activity.endRun()
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

    // MARK: - Default airport index (protocol path)

    /// Ask the engine for X-Plane's Global Airports index. Sent when a
    /// session starts and whenever the X-Plane folder changes; a session
    /// that isn't up yet gets it from `connectIfNeeded`.
    ///
    /// A "ready" reply names the cache to read; "building" means the
    /// engine is parsing apt.dat on its own worker thread and the
    /// `airportIndexReady` event will name it.
    func refreshAirportIndex() {
        guard let client else { return }
        let xplane = UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? ""
        guard !xplane.isEmpty else {
            engineAnsweredAirportIndex = true
            publishGlobalAirports([])
            return
        }
        client.requestAirportIndex(xplaneDir: xplane) { [weak self] reply in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if reply.isReady {
                    self.engineAnsweredAirportIndex = true
                    self.readGlobalAirports(atPath: reply.path)
                } else if !reply.isBuilding {
                    self.handleAirportIndexNone()
                }
                // "building": the airportIndexReady event finishes it.
            }
        }
    }

    /// The engine replied "none" — nominally no X-Plane folder or no
    /// default apt.dat. But a TCC/permission denial makes the engine's
    /// folder scan come back empty too (a freshly signed build re-prompts
    /// for volume access), so the denial arrives wearing the same reply
    /// (observed on 1.0.253: the default-airports layer silently wiped).
    /// A valid cache from a previous session is the witness that an
    /// install was readable here before: keep the optimistic display and
    /// warn, and do NOT mark the engine as authoritatively answered — the
    /// optimistic read may still be in flight, and a later ready reply
    /// (folder change, permission granted) still supersedes everything.
    /// Genuine "none" (no usable cache either) clears the layer as before.
    private func handleAirportIndexNone() {
        guard let dataRoot = dataRootURL else {
            engineAnsweredAirportIndex = true
            publishGlobalAirports([])
            return
        }
        // The optimistic read already published a non-empty index for
        // this data root — its cache was valid moments ago.
        if !globalAirports.isEmpty {
            warnAirportIndexMasked()
            return
        }
        let url = dataRoot.appendingPathComponent(GlobalAirportIndex.cacheFilename)
        Task { [weak self] in
            let cacheBacked = await Task.detached(priority: .utility) {
                GlobalAirportIndex.cacheLooksValid(at: url)
            }.value
            guard let self else { return }
            if cacheBacked {
                self.warnAirportIndexMasked()
            } else {
                self.engineAnsweredAirportIndex = true
                self.publishGlobalAirports([])
            }
        }
    }

    private func warnAirportIndexMasked() {
        console.append(
            "Engine: could not read the X-Plane folder for the default "
            + "airport index (a macOS permission prompt may be pending) — "
            + "keeping last session's airports on the map.")
    }

    /// Read the engine's TSV index off the main thread and publish it.
    private func readGlobalAirports(atPath path: String) {
        guard !path.isEmpty else {
            publishGlobalAirports([])
            return
        }
        let url = URL(fileURLWithPath: path)
        Task { [weak self] in
            let airports = await Task.detached(priority: .utility) {
                GlobalAirportIndex.readCache(at: url) ?? []
            }.value
            self?.publishGlobalAirports(airports)
        }
    }

    /// Optimistic start, the scenery index's doctrine: last session's cache
    /// sits in the data folder, so the marks can be on the map before the
    /// engine has even booted. Display-grade and stale-tolerant — the
    /// engine's answer supersedes it.
    private func loadCachedGlobalAirports() {
        guard let dataRoot = dataRootURL else { return }
        let url = dataRoot.appendingPathComponent(GlobalAirportIndex.cacheFilename)
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        Task { [weak self] in
            let airports = await Task.detached(priority: .utility) {
                GlobalAirportIndex.readCache(at: url) ?? []
            }.value
            // The engine may have answered first; never overwrite it.
            guard let self, !self.engineAnsweredAirportIndex,
                  self.globalAirports.isEmpty, !airports.isEmpty
            else { return }
            self.publishGlobalAirports(airports)
        }
    }

    private func publishGlobalAirports(_ airports: [GlobalAirport]) {
        globalAirports = airports
        onGlobalAirports?(airports)
        // The search field's index (#543): normalised once, off the main
        // thread; a stale build never overwrites a newer index.
        Task { [weak self] in
            let search = await Task.detached(priority: .userInitiated) {
                AirportSearch(airports)
            }.value
            guard let self, self.globalAirports.count == airports.count else { return }
            self.airportSearch = search
        }
    }

    // MARK: - Event handling (protocol path)

    private func handle(_ event: O4Event) {
        feedStepStrip(event)
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
            refreshCustomizedTiles()
            refreshCustomPatchTiles()
        case .tileState(let lat, let lon, let state, let label, let percent, let detail,
                        let attempt):
            let coord = TileCoord(lat: lat, lon: lon)
            let state = TileProgress.State(rawValue: state) ?? .queued
            applyTileEvent(TileProgress(
                state: state,
                label: label.isEmpty ? state.rawValue : label,
                percent: percent,
                detail: detail), attempt: attempt, to: coord)
            // The engine is done with the attempt the user stopped (#1326).
            if stopPending.contains(coord),
               label == "stopped" || state == .done || state == .error {
                stopConfirmed(coord, attempt: attempt, done: state == .done)
            }
        case .stepProgress(let lat, let lon, let stepKey, let label, let percent, let indeterminate,
                           let attempt):
            let coord = TileCoord(lat: lat, lon: lon)
            let previous = activity.tiles[coord]?.percent ?? 0
            applyTileEvent(TileProgress(
                state: indeterminate ? .indeterminate : .active,
                // Wire label -> plain step name (#831); the wire is unchanged.
                label: O4Glossary.stepDisplay(key: stepKey, label: label),
                // Indeterminate steps report no usable percent — hold it.
                percent: indeterminate ? previous : percent), attempt: attempt, to: coord)
        case .autoPatchBegin, .autoPatchProgress:
            break // folded into StepProgress labels by the session
        case .autoPatchFailed(let airport, let stage, let error, let lat, let lon, let code):
            // H1: name the airport in the console the moment it dies — the
            // silent 2026-08-30 death showed nothing at all. An engine that
            // sends a `code` (protocol 1.10, #562) explains it in the user's
            // words on the tile's buildDone; an older one has only this.
            let coord = TileCoord(lat: lat, lon: lon)
            console.append(code.isEmpty
                ? "*** Tile \(coord.key): airport \(airport) failed at the "
                    + "\(stage) stage — \(error)"
                : O4TileFailureCopy.airportFailedLine(tile: coord.key, airport: airport))
        case .buildDone(let lat, let lon, let ok, let error, let failures, let warnings,
                        let unpatched, let notes):
            let coord = TileCoord(lat: lat, lon: lon)
            // #562 / #564: the engine's own words — what, why, what to do —
            // on the console now and in the run's one report at the end.
            for failure in failures {
                failure.consoleLines(isWarning: false).forEach { console.append($0) }
            }
            for warning in warnings {
                warning.consoleLines(isWarning: true).forEach { console.append($0) }
            }
            for note in notes {
                note.consoleLines(isWarning: false, isNote: true).forEach { console.append($0) }
            }
            let issues = O4TileIssues(
                tileKey: coord.key, lat: lat, lon: lon, built: ok,
                failures: failures, warnings: warnings, notes: notes)
            runIssueLog.add(issues)
            // #1341: kept on the row, whose status reopens them.
            if !issues.entries.isEmpty { activity.issues[coord] = issues }
            // #695: a cause the user can fix is asked NOW, while the rest
            // of the run goes on — not when the run ends.
            if !ok { linkFixes.offer(issues) }
            if ok {
                let airports = unpatched.flatMap(\.airports)
                console.append(warnings.isEmpty && notes.isEmpty
                    ? "Tile \(coord.key) finished."
                    : "Tile \(coord.key) finished with warnings"
                        + (airports.isEmpty ? "."
                           : " — no airport patch for \(airports.joined(separator: ", "))."))
                if !(warnings.isEmpty && notes.isEmpty), var row = activity.tiles[coord] {
                    row.label = O4TileFailureCopy.builtWithWarnings
                    activity.tiles[coord] = row
                }
                selected.remove(coord)
                refreshTileInfo(coord)
                if linkTiles { installLink(coord, quiet: true) }
            } else if failures.isEmpty, !error.isEmpty {
                console.append("*** Tile \(coord.key) failed: \(error)")
            }
        case .runEta(let elapsed, let remaining, let done, let total):
            activity.elapsedSeconds = elapsed
            activity.remainingSeconds = remaining
            activity.doneTiles = done
            activity.totalTiles = total
            // Estimate credibility: a remaining that has grown over the
            // last ~30 s means the model is being outlived (a download
            // or a step with no live signal) — the UI shows "still
            // estimating" instead of a precise-looking number.
            if let remaining {
                etaSamples.append((elapsed, remaining))
                etaSamples.removeAll { elapsed - $0.at > 45 }
                let baseline = etaSamples.first(where: { elapsed - $0.at >= 30 })
                activity.remainingUnreliable =
                    baseline.map { remaining > $0.value + 5 } ?? false
            } else {
                etaSamples.removeAll()
                activity.remainingUnreliable = false
            }
        case .tileClocks(let rows):
            // Rows from earlier runs keep their frozen final clocks (#1341).
            var clocks = activity.tileClocks.filter { !activity.runTiles.contains($0.key) }
            for row in rows {
                let coord = TileCoord(lat: row.lat, lon: row.lon)
                // A stopped row's clock is frozen where the stop left it —
                // the engine keeps counting until its cancel lands — and a
                // queued row runs none (#1326).
                clocks[coord] = Self.displayedClock(
                    row, state: activity.tiles[coord]?.state,
                    previous: activity.tileClocks[coord])
            }
            activity.tileClocks = clocks
        case .runDone(let done, let errors, let cancelled):
            isBuilding = false
            isStopping = false
            var parts = ["\(done) tile\(done == 1 ? "" : "s") built"]
            let warned = runIssueLog.warnedCount
            if warned > 0 { parts.append("\(warned) with warnings") }
            if errors > 0 { parts.append("\(errors) failed") }
            // #695: the report waits for an unanswered fix choice (a sheet
            // and an alert never stack).
            let report = runIssueLog.finish()
            keepRetryTiles()
            if linkFixes.isIdle { runIssues = report } else { deferredRunIssues = report }
            if cancelled { parts.append("stopped") }
            lastRunSummary = parts.joined(separator: ", ")
            console.append("=== Run complete: \(lastRunSummary!) ===")
            rescan()
            // Qt lingers 5 s before the run's header, clock and map badges
            // go; the rows themselves stay until the app quits (#1341).
            clearProgressTask?.cancel()
            clearProgressTask = Task { @MainActor [weak self] in
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self, !self.isBuilding else { return }
                self.activity.endRun()
            }
            // Re-queues still held for a stop the engine never confirmed get
            // their own follow-up run. A run the user STOPPED wholesale takes
            // them down with it — stop is the inverse of resume, at any scale.
            let held = heldForStop
            heldForStop = [:]
            stopPending = []
            if !cancelled, !held.isEmpty {
                startResumeRun(Self.batchedBySettings(
                    held.keys.sorted().map { (coord: $0, settings: held[$0]!.settings) }))
            }
        case .secretRequest(let requestID, let operation, let sessionName,
                            let account, let secret):
            serviceSecretRequest(requestID: requestID, operation: operation,
                                 sessionName: sessionName, account: account,
                                 secret: secret)
        case .signInResult(let sessionName, let ok, let errorText):
            signInResultCounter += 1
            lastSignInResult = ProviderSignInResult(
                id: signInResultCounter, sessionName: sessionName,
                ok: ok, errorText: errorText)
            // Whatever the sheet does with it, the rows' status changed.
            Task { @MainActor [weak self] in await self?.refreshProviderAccounts() }
        case .airportIndexReady(let path, _, let error):
            guard error.isEmpty else {
                console.append("Engine: default airport index unavailable: \(error)")
                publishGlobalAirports([])
                return
            }
            readGlobalAirports(atPath: path)
        case .boundaryAirportsReady(let ready):
            boundaryAirportsReady(ready)
        case .packMissingArt(let art):
            packMissingArt(art)
        case .engineError(let fatal, let text):
            console.append((fatal ? "FATAL: " : "Engine: ") + text)
            if fatal { engineError = text }
        case .imageryDownloadsDone:
            break // the engine's scheduling signal; the tile's row moves on its own
        case .unknown:
            break // additive protocol: ignore unknown event types
        }
    }

    /// Service the engine's brokered secret-store operation from the app's
    /// own Keychain (ProviderSecretStore): the engine binary is ad-hoc
    /// signed, so its own Keychain use would prompt as "Ortho4XP" and lose
    /// its grants on every rebuild — the items live with the app instead.
    private func serviceSecretRequest(requestID: Int, operation: String,
                                      sessionName: String, account: String,
                                      secret: String) {
        guard let client else { return }
        Task.detached(priority: .userInitiated) {
            let store = ProviderSecretStore()
            var arguments: [String: Any] = ["request_id": requestID]
            do {
                switch operation {
                case "get":
                    let value = try store.secret(sessionName: sessionName, account: account)
                    arguments["ok"] = true
                    arguments["secret"] = value ?? NSNull()
                case "set":
                    try store.store(sessionName: sessionName, account: account, secret: secret)
                    arguments["ok"] = true
                case "delete":
                    try store.delete(sessionName: sessionName, account: account)
                    arguments["ok"] = true
                default:
                    arguments["ok"] = false
                    arguments["error"] = "unknown secret operation '\(operation)'"
                }
            } catch {
                arguments["ok"] = false
                arguments["error"] = String(describing: error)
            }
            client.send(command: "secret_response", arguments: arguments)
        }
    }

    // MARK: - Provider accounts (engine-side sign-in)

    /// One finished sign-in / sign-out attempt, as the engine reported it.
    /// `id` rises with every result so a sheet can react to each one.
    struct ProviderSignInResult: Sendable, Equatable {
        let id: Int
        let sessionName: String
        let ok: Bool
        let errorText: String
    }

    /// Re-read the provider account rows from the engine. The login flows
    /// live in the engine (O4_Authenticated_Sessions), so this app only
    /// renders what `auth_providers` reports and sends the two commands.
    func refreshProviderAccounts() async {
        connectIfNeeded()
        guard let client else { return }
        let accounts = await client.authProviders()
        providerAccounts = accounts
        // The engine reads an api_key's stored state on a worker thread
        // (its command thread cannot answer its own brokered secret
        // request); a pending row means "ask again once that lands".
        guard accounts.contains(where: { $0.statusPending }) else { return }
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(700))
            guard let self, let client = self.client else { return }
            self.providerAccounts = await client.authProviders()
        }
    }

    /// Start a sign-in; the outcome arrives as `lastSignInResult`. Returns
    /// the engine's error text when the command itself was refused.
    func providerSignIn(sessionName: String, username: String,
                        secret: String, remember: Bool) async -> String? {
        connectIfNeeded()
        guard let client else { return "engine not running" }
        return await client.providerSignIn(sessionName: sessionName,
                                           username: username, secret: secret,
                                           remember: remember)
    }

    /// Forget one account (credentials, API key, saved session).
    func providerSignOut(sessionName: String) async {
        connectIfNeeded()
        guard let client else { return }
        _ = await client.providerSignOut(sessionName: sessionName)
    }

    // MARK: - Patch editor (#46)

    /// The patch layer (map overlay + "Patch · ICAO" box).
    lazy var patchEdit = PatchEditModel(build: self)

    /// "Select from flight plan…" (#829): the panel and the route overlay.
    lazy var flightPlan = FlightPlanSelection(build: self)
    /// The pack reference outlines under it (spec §0 A4).
    lazy var packOutlines = PatchPackOutlines(patch: patchEdit)
    /// The terrain view under it (#1320: hillshade plus contours).
    lazy var terrainRelief = PatchTerrainRelief(patch: patchEdit)

    /// The engine session for the patch commands, or nil when the engine
    /// is not running or predates them (protocol < 1.12): the patch layer
    /// then stays hidden, without an error.
    func patchEditorClient() -> OrthoEngineClient? {
        connectIfNeeded()
        guard O4ProtocolVersion.supportsPatchEditor(protocolHello?.protocolVersion ?? "") else { return nil }
        return client
    }

    // MARK: - Library (#824)

    /// The engine session and the folders the Library window reads, or
    /// nil when the engine is not running or no tiles folder is known.
    func libraryContext() -> (client: OrthoEngineClient, workingDir: String, sceneryDir: String)? {
        connectIfNeeded()
        guard let client, let base = tileBaseFolder else { return nil }
        return (client, base.path, customSceneryPath)
    }

    /// Library ▸ Rebuild: select those tiles (adopting the active one's
    /// recorded source) and press Build.
    func rebuild(_ coords: [TileCoord]) {
        guard !coords.isEmpty else { return }
        selected = Set(coords)
        activeTile = coords.sorted().first
        startBuild()
    }

    // MARK: - Reanchor status (auto-patch object reseating)

    /// One pack the reseater modified, as the engine reports it.
    struct ReanchorPack: Sendable {
        let packName: String
        let packPath: String
        let objectCount: Int
    }

    /// Packs whose objects the auto-patch reseater modified for `coord`,
    /// via the engine's reanchor_status command — the engine owns the
    /// sidecar format, so this app and the Qt front end behave
    /// identically. Empty when the engine predates the command (unknown
    /// commands reply ok=false) or no X-Plane folder is configured.
    func reanchorStatus(for coord: TileCoord) async -> [ReanchorPack] {
        connectIfNeeded()
        let scenery = customSceneryPath
        guard let client, !scenery.isEmpty else { return [] }
        return await withCheckedContinuation { continuation in
            client.send(command: "reanchor_status", arguments: [
                "scenery_dir": scenery, "lat": coord.lat, "lon": coord.lon,
            ]) { reply in
                guard reply.ok,
                      let packs = reply.result?["packs"]?.arrayValue else {
                    continuation.resume(returning: [])
                    return
                }
                continuation.resume(returning: packs.compactMap { entry in
                    guard let name = entry["pack_name"]?.stringValue,
                          let path = entry["pack_path"]?.stringValue
                    else { return nil }
                    return ReanchorPack(
                        packName: name, packPath: path,
                        objectCount: entry["objects"]?.intValue ?? 0)
                })
            }
        }
    }

    /// Engine-side restore of a pack's .anchor_bak originals (backups
    /// stay in place, sidecar removed). Returns the count restored, or
    /// the engine's error text.
    func reanchorRestore(packPath: String) async -> (restored: Int?, error: String?) {
        connectIfNeeded()
        guard let client else { return (nil, "engine not running") }
        return await withCheckedContinuation { continuation in
            client.send(command: "reanchor_restore",
                        arguments: ["pack_path": packPath]) { reply in
                if reply.ok {
                    continuation.resume(returning:
                        (reply.result?["restored"]?.intValue ?? 0, nil))
                } else {
                    continuation.resume(returning:
                        (nil, reply.error ?? "unknown engine error"))
                }
            }
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

    /// Add several tiles to the selection (an airport-code list, #542);
    /// the first becomes active, as `selectTile` makes its one tile.
    func selectTiles(_ coords: [TileCoord]) {
        guard let first = coords.first else { return }
        selected.formUnion(coords)
        activeTile = first
    }

    /// The progress rows of `todo` name each tile's largest airports, a
    /// searched one first when it is not among them (#815, after #667).
    private func stampRunTags(_ todo: [TileCoord]) {
        let largest = largestAirportsByTile ?? AirportRank.largestByTile(globalAirports)
        largestAirportsByTile = largest
        for coord in todo {
            let tile = AirportTile(lat: coord.lat, lon: coord.lon)
            activity.runTags[coord] = TileSearchTags.suffix(
                AirportRank.titleCodes(largest: largest[tile] ?? [],
                                       searched: searchTags.codes[tile] ?? []))
        }
    }

    func clearSelection() {
        selected = []
        activeTile = nil
    }

    // MARK: - Building

    /// Selected tiles already queued or running in the active run — kept
    /// out of buildableSelection so pressing Queue again can't hand the
    /// engine a second copy of the same tile.
    var selectedInRun: Set<TileCoord> {
        guard isBuilding else { return [] }
        return Set(selected.filter { coord in
            Self.isInRun(activity.tiles[coord]?.state, held: heldForStop[coord] != nil)
        })
    }

    /// Is a row's tile part of the engine's run? A stopped row has left it
    /// (pressing Build or resume may hand the tile over again), and so has
    /// a queued row held here until its stop is confirmed (#1326): the
    /// engine does not have it yet, so Queue must stay usable for it.
    static func isInRun(_ state: TileProgress.State?, held: Bool) -> Bool {
        switch state {
        case .queued: return !held
        case .active, .indeterminate: return true
        case .done, .error, .stopped, nil: return false
        }
    }

    /// Tiles the next Build press would actually build.
    var buildableSelection: [TileCoord] {
        let inRun = selectedInRun
        return selected.sorted().filter { coord in
            guard !inRun.contains(coord) else { return false }
            return !skipBuilt || built[coord]?.dsfPresent != true
        }
    }

    /// Why a build cannot start for want of X-Plane data, or `nil`.
    ///
    /// Beta plan §1 B2: with no CIFP corpus the engine refuses the tile
    /// outright (it used to warn and then build every airport on the raw
    /// DEM, exiting 0), so the app must not offer the Build. One predicate
    /// with the engine and the Qt UI — `XPlaneInstall` is the Swift twin of
    /// `O4_Settings_Model.cifp_refusal_reason`.
    var xplaneBlockReason: String? {
        XPlaneInstall.buildBlockReason(
            xplanePath: UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? "",
            cifpDataPath: globalConfigValues["cifp_data_path"]?.cfgLiteral ?? "",
            customSceneryDir: globalConfigValues["custom_scenery_dir"]?.cfgLiteral ?? "")
    }

    var canBuild: Bool {
        engine != nil && !buildableSelection.isEmpty
            && (doVector || doImagery || doOverlays)
            && !(isBuilding && !usesProtocol) // legacy path can't queue into a run
            && !isBoundaryPreflighting // a second press would ask twice
            && xplaneBlockReason == nil
            && planBlockReason == nil
    }

    // MARK: - Build cost (#820)

    /// The engine's estimate for what the next Build press would build,
    /// or nil (nothing to build, an engine older than 1.15, or none yet).
    @Published private(set) var planEstimate: O4PlanEstimate?
    /// Why the last estimate could not be made, for the panel's line.
    @Published private(set) var planEstimateError: String?

    /// The disk refusal: Build is off while even the low end of the need
    /// exceeds the free space. A queued batch joins a run already going,
    /// so it is never refused here.
    var planBlockReason: String? {
        isBuilding ? nil : planEstimate?.blockingReason
    }

    /// The `.task(id:)` key that re-asks for the estimate: every input of
    /// `plan_estimate` that the Build box can change.
    var planEstimateKey: String {
        [buildableSelection.map(\.key).joined(separator: ","), buildProvider, String(buildZL),
         customBuildDir, "\(doVector)\(doImagery)\(doOverlays)", "\(isBuilding)",
         protocolHello?.protocolVersion ?? ""].joined(separator: "|")
    }

    /// Ask the engine what the next Build press costs. Called from a
    /// `.task(id: planEstimateKey)`, so a newer selection cancels the wait;
    /// the short sleep folds a burst of clicks into one request.
    func updatePlanEstimate() async {
        let tiles = buildableSelection
        guard usesProtocol, let client, !tiles.isEmpty, doVector || doImagery || doOverlays,
              O4ProtocolVersion.supportsPlanEstimate(protocolHello?.protocolVersion ?? "")
        else {
            planEstimate = nil
            planEstimateError = nil
            return
        }
        try? await Task.sleep(for: .milliseconds(250))
        guard !Task.isCancelled else { return }
        do {
            let estimate = try await client.planEstimate(
                tiles: tiles.map { O4TileRef(lat: $0.lat, lon: $0.lon) },
                provider: buildProvider, zoomlevel: buildZL,
                customBuildDir: engineCustomBuildDir,
                doVector: doVector, doImagery: doImagery, doOverlays: doOverlays)
            guard !Task.isCancelled else { return }
            planEstimate = estimate
            planEstimateError = nil
        } catch {
            guard !Task.isCancelled else { return }
            planEstimate = nil
            planEstimateError = (error as? O4CommandError)?.message ?? error.localizedDescription
        }
    }

    // MARK: - Legacy tile settings (built by an older/other Ortho4XP)

    /// Everything about a tile cfg that an older or different Ortho4XP
    /// wrote and this engine interprets rather than takes literally —
    /// surfaced to the user with an offer to modernize the file.
    struct LegacyTileSettings {
        let coord: TileCoord
        let cfgURL: URL
        /// Enum values this engine doesn't define, with the replacement
        /// an update would write (current global value, else the
        /// registry default).
        let foreignEnums: [(key: String, value: String, replacement: String)]
        /// Keys carrying legacy quoted values ('Arc').
        let quotedKeys: [String]
        /// custom_dem pins whose file no longer exists.
        let missingPins: [String]

        var isEmpty: Bool {
            foreignEnums.isEmpty
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
    /// Only this app's own tile config is read: an Ortho4XP config beside
    /// it is ignored, never modernised or moved (RULINGS 2026-10-26c).
    func legacyTileSettings(for coord: TileCoord) -> LegacyTileSettings? {
        guard let info = built[coord], !info.buildDir.isEmpty else { return nil }
        let dir = URL(fileURLWithPath: info.buildDir, isDirectory: true)
        let cfgURL = dir.appendingPathComponent(
            OrthoConfigNames.tileFileName(lat: coord.lat, lon: coord.lon))
        let fm = FileManager.default
        guard fm.fileExists(atPath: cfgURL.path) else { return nil }
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
               // A legacy bool for a mode-valued setting (auto_patch,
               // airport_elevation_insets) is MAPPED, not "foreign" — the
               // foreign-enum rule would otherwise replace a user's Off
               // with the global (engine twin:
               // O4_Settings_Model._normalize_legacy_mode_value).
               !allowed.contains(O4LegacyModes.mappedLiteral(bare, forKey: key) ?? bare) {
                let replacement = globalConfigValues[key]?.cfgLiteral
                    ?? variable.default.cfgLiteral
                foreign.append((key, bare, Self.unquoteCfgValue(replacement)))
            }
        }
        let result = LegacyTileSettings(
            coord: coord, cfgURL: cfgURL,
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
    /// user's zone work survive. The original stays as .bak.
    func updateLegacyTileSettings(_ legacy: LegacyTileSettings) {
        guard let source = try? OrthoConfigFile(contentsOf: legacy.cfgURL) else { return }
        let raw = source.rawValues
        var lines: [String] = []
        for key in ["default_website", "default_zl", "zone_list"] {
            guard let value = raw[key] else { continue }
            let bare = Self.unquoteCfgValue(value.trimmingCharacters(in: .whitespaces))
            lines.append("\(key)=\(bare)")
        }
        var file = OrthoConfigFile(lines: lines)
        file.stampTileConfig(appVersion: AppVersion.current)
        do {
            try file.write(to: legacy.cfgURL)
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
            // EVERY protocol enqueue goes through the boundary preflight
            // (protocol 1.8, spec §C.7): one ask for the whole press.
            startProtocolBuild(batches.map {
                BuildBatch(tiles: $0.tiles, provider: $0.provider, zl: $0.zl)
            })
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

    /// One enqueue_build's worth of work: the tiles and the imagery
    /// settings they are being started with.
    struct BuildBatch: Equatable {
        var tiles: [TileCoord]
        let provider: String
        let zl: Int
    }

    private func sendProtocolBuild(_ batch: BuildBatch, boundaryPolicy: String?) {
        sendProtocolBuild(batch.tiles, provider: batch.provider, zl: batch.zl,
                          boundaryPolicy: boundaryPolicy)
    }

    private func sendProtocolBuild(_ tiles: [TileCoord], provider: String, zl: Int,
                                   boundaryPolicy: String?) {
        connectIfNeeded()
        guard let client else { return }
        // #1326: a tile whose Stop the engine has not confirmed yet is HELD
        // until it does (`stopConfirmed` sends it then) — the engine refuses
        // a second copy of a tile it is still stopping.
        let split = Self.splitHeld(tiles, stopPending: isBuilding ? stopPending : [])
        let todo = split.send
        let settings = TileRunSettings(provider: provider, zl: zl)
        for coord in split.hold {
            heldForStop[coord] = HeldRequeue(settings: settings, boundaryPolicy: boundaryPolicy)
        }
        if todo.isEmpty {
            // Nothing goes to the engine yet.
        } else if !isBuilding {
            activity.beginRun()
            isBuilding = true
            isStopping = false
            // A previous run that died without RunDone leaves nothing in
            // this run's report (#562).
            runIssueLog.begin()
            // THE RUN BOUNDARY: the build request that opens a run starts a
            // fresh engine-stderr.log (twin: O4_Qt_GUI._start_run_now).
            EngineStderrLog.shared.startRun(
                appVersion: AppVersion.current,
                engineVersion: protocolHello?.version ?? schema.engineVersion,
                tiles: todo.map(\.key))
        } else {
            EngineStderrLog.shared.append(
                EngineStderrLog.queuedLine(tiles: todo.map(\.key)))
        }
        clearProgressTask?.cancel()
        // Every enqueue — Build, Queue, Resume, Rebuild — puts the tile's
        // row back to queued with no clock (#1326): a row left "stopped"
        // would drop the new attempt's events as the stopped one's.
        let queued = todo + split.hold
        // Every attempt starts its step strip afresh (#825); a row still
        // live in this run keeps its own, as `queueRows` keeps the row.
        for coord in queued
        where activity.tiles[coord].map(BuildActivityModel.isFinished) ?? true {
            activity.stepStrips[coord] = O4StepStrip()
        }
        activity.queueRows(queued)
        stampRunTags(queued)
        // The settings this tile is being STARTED with — what a later
        // resume of it must use.
        for coord in queued {
            activity.runSettings[coord] = settings
        }
        guard !todo.isEmpty else { return }
        console.append("=== Building \(todo.count) tile\(todo.count == 1 ? "" : "s"): \(todo.prefix(8).map { $0.key }.joined(separator: " "))\(todo.count > 8 ? " …" : "") ===")
        var arguments: [String: Any] = [
            "tiles": todo.map { [$0.lat, $0.lon] },
            "provider": provider,
            "zoomlevel": zl,
            "custom_build_dir": engineCustomBuildDir,
            "do_vector": doVector,
            "do_imagery": doImagery,
            "do_overlays": doOverlays,
        ]
        // Omitted entirely when nil: an engine older than 1.8 rejects
        // unknown keywords, and nil IS "resolve from cfg" there anyway.
        if let boundaryPolicy { arguments["boundary_policy"] = boundaryPolicy }
        client.send(command: "enqueue_build", arguments: arguments) { [weak self] reply in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if !reply.ok {
                    self.console.append("*** Build refused: \(reply.error ?? "unknown error")")
                    self.isBuilding = false
                    self.activity.endRun()
                } else if reply.result?.boolValue == false {
                    // The live run already holds every one of these tiles.
                    self.console.append("Already in this run: \(todo.map(\.key).joined(separator: " ")).")
                }
            }
        }
    }

    // MARK: - Missing art (protocol 1.9, #433)

    /// The finished run's failures and warnings to present, or nil: ONE
    /// report per run (#562, #564), shown by `RunIssuesSheet`.
    @Published var runIssues: O4RunIssues?
    private var runIssueLog = O4RunIssueLog()

    private var reopenedIssues = 0

    /// #1341: a finished row's gold (or red) status was clicked — show
    /// that tile's end-of-build messages again, with the report buttons.
    func reopenIssues(_ coord: TileCoord) {
        guard let tile = activity.issues[coord] else { return }
        reopenedIssues += 1
        // Negative ids never meet the run reports' own (1, 2, …).
        runIssues = O4RunIssues(id: -reopenedIssues, tiles: [tile])
    }

    /// Whether the engine has the `failure_report` command (#565).
    var canReportFailures: Bool {
        O4FailureReport.supported(protocolVersion: protocolHello?.protocolVersion ?? "")
    }

    /// The engine's redacted report of one tile's failures and warnings;
    /// a non-empty `savePath` also writes it there. Completes on the main
    /// actor with nil when the engine cannot answer.
    func failureReport(for tile: O4TileIssues, savePath: String = "",
                       completion: @escaping @MainActor (O4FailureReport?) -> Void) {
        guard let client else { completion(nil); return }
        client.failureReport(
            lat: tile.lat, lon: tile.lon, failures: tile.entries,
            appVersion: AppVersion.current,
            logPath: EngineStderrLog.shared.fileURL.path,
            xplaneDir: UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? "",
            savePath: savePath
        ) { report in
            Task { @MainActor in completion(report) }
        }
    }

    /// "Remove the link and build on this Mac's drive" (#668): the engine
    /// removes the ONE dangling link (never its target, never a folder),
    /// then the tile builds again with the current settings. Completes on
    /// the main actor with nil on success, else the reason it refused.
    func removeLinkAndRebuild(_ tile: O4TileIssues, link: String,
                              completion: @escaping @MainActor (String?) -> Void) {
        guard let client else { completion("The engine is not running."); return }
        client.removeSceneryLink(path: link) { refusal in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if let refusal {
                    completion(refusal)
                    return
                }
                self.requeueFixedTile(tile, link: link)
                completion(nil)
            }
        }
    }

    /// #695: the fixed tile joins the RUNNING build (enqueue_build appends
    /// to a live run) with the settings its run started it with, or starts
    /// a new run when this one has ended; every report of this run says
    /// "fixed and re-queued" for it.
    private func requeueFixedTile(_ tile: O4TileIssues, link: String) {
        let coord = TileCoord(lat: tile.lat, lon: tile.lon)
        runIssueLog.markRequeued(tileKey: tile.tileKey)
        deferredRunIssues?.markRequeued(tileKey: tile.tileKey)
        runIssues?.markRequeued(tileKey: tile.tileKey)
        console.append(O4TileFailureCopy.requeuedConsole(
            tile: tile.tileKey, link: link, intoRun: isBuilding))
        let settings = activity.runSettings[coord]
            ?? TileRunSettings(provider: buildProvider, zl: buildZL)
        startResumeRun([(tiles: [coord], settings: settings)])
    }

    /// The fixable failures of this run, asked one at a time as each tile
    /// fails (#695); the view shows `linkFixes.current`.
    @Published private(set) var linkFixes = O4LinkFixQueue()
    /// The run's report, held while a fix choice is still on screen.
    private var deferredRunIssues: O4RunIssues?

    /// The user's answer to the choice on screen: `remove` removes the
    /// link and re-queues the tile; otherwise it is dismissed (the run's
    /// report still lists the failure and offers the button again).
    func answerLinkFix(remove: Bool) {
        guard let fix = linkFixes.answer() else { return }
        if remove {
            removeLinkAndRebuild(fix.tile, link: fix.link) { [weak self] refusal in
                if let refusal {
                    self?.console.append("*** " + O4TileFailureCopy.removeLinkFailed(refusal))
                }
            }
        }
        guard linkFixes.isIdle, deferredRunIssues != nil else { return }
        // A moment after the alert closes: AppKit drops a sheet asked for
        // while an alert is still dismissing. Read when it fires, so a
        // re-queue confirmed meanwhile is already marked on it.
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(300))
            guard let self, self.linkFixes.isIdle, let report = self.deferredRunIssues else { return }
            self.deferredRunIssues = nil
            self.runIssues = report
        }
    }

    /// The "X-Plane will not load this pack" warning to present, or nil.
    @Published var packArtPrompt: O4PackMissingArt?
    /// Warnings waiting behind the one on screen, in arrival order.
    private var packArtQueue: [O4PackMissingArt] = []
    /// Every warning already shown this session (one per pack, tile and
    /// missing set — each airport of a pack runs the check).
    private var packArtSeen: Set<String> = []

    /// Parity with the Qt window (`O4_Qt_GUI._on_pack_missing_art`): a
    /// "found" event shows the owner-fixed warning once; the completion
    /// states are already on the console through the engine's log line.
    private func packMissingArt(_ art: O4PackMissingArt) {
        guard art.state == "found", !packArtSeen.contains(art.id) else { return }
        packArtSeen.insert(art.id)
        if packArtPrompt == nil {
            packArtPrompt = art
        } else {
            packArtQueue.append(art)
        }
    }

    /// The user's answer to the warning on screen: `omit` sends
    /// `omit_missing_art` (only offered when the event's `canOmit`).
    func answerPackArtPrompt(omit: Bool) {
        if let art = packArtPrompt, omit, art.canOmit {
            client?.omitMissingArt(packRoot: art.packRoot, lat: art.lat, lon: art.lon)
        }
        packArtPrompt = packArtQueue.isEmpty ? nil : packArtQueue.removeFirst()
    }

    // MARK: - Boundary airports (protocol 1.8)

    /// What the user answered, or what a remembered answer resolved to.
    enum BoundaryChoice: String, Equatable {
        /// Build the adjacent tiles too: they join this run's tile list.
        case neighbour
        /// Those airports get no elevation patch this run.
        case skip
    }

    /// One sheet's worth of boundary airports, as the view reads it.
    struct BoundaryPrompt: Identifiable, Equatable {
        let id: Int
        let airports: [O4BoundaryAirport]
        let addTiles: [O4TileRef]
        /// The PRESELECTED (Return-key) choice, engine-owned — never
        /// hardcoded here (owner RULINGS 2026-09-18i (2)).
        let defaultChoice: BoundaryChoice
    }

    /// A preflight that has been sent and not yet answered. The correlation
    /// rules live in `O4BoundaryFlow` (SceneryKit), where they are testable.
    private struct PendingBoundary {
        var batches: [BuildBatch]
        var flow = O4BoundaryFlow()
    }

    /// The sheet to present, or nil. Set only for an interactive ask.
    @Published var boundaryPrompt: BoundaryPrompt?
    /// A build press is waiting on the preflight — the Build button is off
    /// so a second press cannot ask twice.
    @Published private(set) var isBoundaryPreflighting = false

    private var pendingBoundary: PendingBoundary?
    private var boundaryTimeoutTask: Task<Void, Never>?

    /// The preflight can never be the thing that stops a build (spec §C.7):
    /// past this, the run starts with the engine's own default policy.
    static let boundaryPreflightTimeoutSeconds = 60

    /// The saved answer as the app's settings hold it ("Ask" by default).
    var autoPatchBoundarySetting: String {
        globalConfigValues["auto_patch_boundary"]?.cfgLiteral ?? "Ask"
    }

    /// EVERY protocol enqueue (Build, batched Build, resume) enters here:
    /// ask the engine which airports straddle a tile line for the tiles
    /// about to be enqueued, then enqueue once with the resulting policy.
    private func startProtocolBuild(_ batches: [BuildBatch]) {
        let batches = batches.filter { !$0.tiles.isEmpty }
        guard !batches.isEmpty else { return }
        connectIfNeeded()
        guard let client else { return }
        // One preflight at a time; a press while one is in flight is
        // already blocked by canBuild, and a resume is not.
        guard pendingBoundary == nil else {
            for batch in batches { sendProtocolBuild(batch, boundaryPolicy: nil) }
            return
        }
        var seen: Set<TileCoord> = []
        var tiles: [TileCoord] = []
        for batch in batches {
            for coord in batch.tiles where seen.insert(coord).inserted { tiles.append(coord) }
        }
        pendingBoundary = PendingBoundary(batches: batches)
        isBoundaryPreflighting = true
        client.requestBoundaryAirports(
            tiles: tiles.map { O4TileRef(lat: $0.lat, lon: $0.lon) }
        ) { [weak self] requestID in
            Task { @MainActor [weak self] in
                self?.boundaryPreflightStarted(requestID)
            }
        }
        boundaryTimeoutTask?.cancel()
        boundaryTimeoutTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(Self.boundaryPreflightTimeoutSeconds))
            guard !Task.isCancelled else { return }
            self?.boundaryPreflightTimedOut()
        }
    }

    private func boundaryPreflightStarted(_ requestID: Int?) {
        guard var pending = pendingBoundary else { return }
        let step = pending.flow.started(requestID: requestID)
        pendingBoundary = pending
        // requestID == nil is an engine older than 1.8: the flow says
        // "enqueue, no policy" and nothing is logged — silent degradation.
        apply(step, requestID: requestID ?? 0)
    }

    private func boundaryPreflightTimedOut() {
        guard var pending = pendingBoundary, boundaryPrompt == nil else { return }
        let step = pending.flow.giveUp()
        pendingBoundary = pending
        guard case .outcome = step else { return }
        console.append(
            "Boundary-airport check did not answer in \(Self.boundaryPreflightTimeoutSeconds) s — building with the engine's own setting.")
        apply(step, requestID: 0)
    }

    /// The `BoundaryAirportsReady` event, correlated on its request id.
    private func boundaryAirportsReady(_ ready: O4BoundaryAirportsReady) {
        guard var pending = pendingBoundary else { return } // stale: no ask open
        let step = pending.flow.ready(ready)
        pendingBoundary = pending
        if case .outcome = step, !ready.error.isEmpty {
            console.append("Boundary-airport check failed: \(ready.error) — building with the engine's own setting.")
        }
        if case .outcome = step, ready.error.isEmpty, !ready.airports.isEmpty {
            for line in Self.boundaryAirportLines(ready.airports) { console.append(line) }
        }
        apply(step, requestID: ready.requestID)
    }

    private func apply(_ step: O4BoundaryFlow.Step, requestID: Int) {
        switch step {
        case .waiting, .ignored:
            return
        case .outcome(.enqueue(let policy, let addTiles)):
            finishBoundary(policy: policy, addTiles: addTiles)
        case .outcome(.ask(let airports, let addTiles, let defaultChoice)):
            // Interactive: the user decides. The timeout stops here — it
            // guards the ENGINE's answer, never the user's.
            boundaryTimeoutTask?.cancel()
            boundaryTimeoutTask = nil
            boundaryPrompt = BoundaryPrompt(
                id: requestID, airports: airports, addTiles: addTiles,
                defaultChoice: BoundaryChoice(rawValue: defaultChoice) ?? .neighbour)
        }
    }

    /// The sheet's answer. `nil` = Cancel build: nothing is enqueued.
    func answerBoundaryPrompt(_ choice: BoundaryChoice?, remember: Bool) {
        let addTiles = boundaryPrompt?.addTiles ?? []
        boundaryPrompt = nil
        if remember, let choice {
            // The app's one engine-settings write path: an app-level cfg
            // var, so the global XPTerrainBuilder.cfg, no tile write-through.
            setConfigValue("auto_patch_boundary",
                           to: .string(Self.boundarySettingValue(choice)))
        }
        guard let choice else {
            // Cancel build: the press is abandoned, nothing enqueued.
            boundaryTimeoutTask?.cancel()
            boundaryTimeoutTask = nil
            pendingBoundary = nil
            isBoundaryPreflighting = false
            return
        }
        finishBoundary(policy: choice.rawValue,
                       addTiles: choice == .neighbour ? addTiles : [])
    }

    /// Enqueue the press that was waiting on the preflight.
    private func finishBoundary(policy: String?, addTiles: [O4TileRef]) {
        boundaryTimeoutTask?.cancel()
        boundaryTimeoutTask = nil
        guard let pending = pendingBoundary else { return }
        pendingBoundary = nil
        isBoundaryPreflighting = false
        let batches = Self.adding(addTiles, to: pending.batches)
        for batch in batches { sendProtocolBuild(batch, boundaryPolicy: policy) }
    }

    // MARK: Boundary rules (pure — no engine, no view)

    /// The added neighbour tiles join the FIRST batch, so they are built
    /// with the same imagery source and zoom level as the press that
    /// needed them, and appear in the queue like user-selected tiles.
    /// Tiles already in any batch are never added twice.
    nonisolated static func adding(_ addTiles: [O4TileRef], to batches: [BuildBatch]) -> [BuildBatch] {
        guard !addTiles.isEmpty, !batches.isEmpty else { return batches }
        var present = Set(batches.flatMap(\.tiles))
        var extra: [TileCoord] = []
        for tile in addTiles {
            let coord = TileCoord(lat: tile.lat, lon: tile.lon)
            if present.insert(coord).inserted { extra.append(coord) }
        }
        guard !extra.isEmpty else { return batches }
        var batches = batches
        batches[0].tiles += extra
        return batches
    }

    /// "LPMT Montijo — extends 1,240 m into +38-009" (the sheet's row, and
    /// the console line when the answer was remembered).
    nonisolated static func boundaryAirportLines(_ airports: [O4BoundaryAirport]) -> [String] {
        airports.map { airport in
            let name = airport.name.isEmpty ? "" : " \(airport.name)"
            return "\(airport.icao)\(name) — extends \(boundaryCrossingText(airport.crossingMeters)) into \(boundaryTileNames(airport.neighbours))"
        }
    }

    /// Metres, rounded to 10 m — the preflight's precision is not the
    /// user's business and a bare float reads as false accuracy.
    nonisolated static func boundaryCrossingText(_ metres: Double) -> String {
        let rounded = Int((metres / 10).rounded()) * 10
        return "\(rounded.formatted()) m"
    }

    nonisolated static func boundaryTileNames(_ tiles: [O4TileRef]) -> String {
        tiles.map(\.key).joined(separator: ", ")
    }

    /// The `auto_patch_boundary` cfg value a remembered choice writes.
    nonisolated static func boundarySettingValue(_ choice: BoundaryChoice) -> String {
        switch choice {
        case .neighbour: return "Build adjacent"
        case .skip: return "Skip patch"
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
            // The engine's cancellation checkpoints normally answer within
            // a few seconds; 15 s covers a blocking network request that
            // has to time out first, plus the parallel scheduler's own
            // per-worker escalation. Only then force it.
            console.append("Stopping — cancelling the engine (forced in 15 s if it doesn't wind down)…")
            hardStopTask?.cancel()
            hardStopTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(15))
                guard !Task.isCancelled, let self, self.isBuilding else { return }
                self.hardStopEngine()
            }
        } else {
            legacyQueue = []
            legacyRunner?.requestStop()
            hardStopTask?.cancel()
            hardStopTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(15))
                guard !Task.isCancelled, let self, self.isBuilding else { return }
                self.console.append("Engine still busy — terminating it now.")
                self.legacyRunner?.kill()
            }
        }
    }

    private func hardStopEngine() {
        console.append("Engine still busy — terminating it now.")
        expectedEngineStop = true
        client?.terminate()
        Task { [weak self] in
            // SIGTERM starts the engine's own bounded wind-down
            // (SHUTDOWN_GRACE_SECONDS = 10 s); the SIGKILL backstop must
            // outlast it or the graceful exit is cut off mid-flight.
            try? await Task.sleep(for: .seconds(12))
            self?.client?.kill()   // no-op once the process has exited
        }
    }

    // MARK: - Per-tile stop / resume (the activity row's stop sign)

    /// A re-queue held until the engine confirms the stop it follows
    /// (#1326): what it will be sent with.
    struct HeldRequeue: Equatable {
        let settings: TileRunSettings
        let boundaryPolicy: String?
    }

    /// Tiles whose Stop the engine has not confirmed yet: its "stopped"
    /// TileState (or a terminal one) is still to come, and until then
    /// everything it says about the tile is the stopped attempt's (#1326).
    private(set) var stopPending: Set<TileCoord> = []
    /// Re-queues (Build, Queue, Resume, Rebuild) of `stopPending` tiles,
    /// sent when the stop is confirmed — never two copies of one tile.
    @Published private(set) var heldForStop: [TileCoord: HeldRequeue] = [:]
    /// Per tile, the last attempt the user stopped: the engine's events
    /// numbered at or below it are late news (#1326).
    private var staleThrough: [TileCoord: Int] = [:]

    /// A new engine session numbers attempts from 1 again.
    private func forgetStopState() {
        stopPending = []
        heldForStop = [:]
        staleThrough = [:]
    }

    /// Per-tile stop (the red stop sign on an activity row). The engine
    /// only honours its cancel flag at the next phase boundary — minutes
    /// away on a mesh phase — so the ROW stops here and now, at the click,
    /// with its percent frozen where it stood. Until the engine confirms
    /// the stop, the tile is `stopPending` (#1326).
    func cancelTile(_ coord: TileCoord) {
        guard usesProtocol else { return }
        let state = activity.tiles[coord]?.state
        // Stop is the inverse of resume: a row held for its earlier stop is
        // only on this side — it goes back to stopped, nothing is sent.
        if heldForStop.removeValue(forKey: coord) == nil {
            if isBuilding, state == .queued || state == .active || state == .indeterminate {
                stopPending.insert(coord)
            }
            client?.send(command: "cancel_tile",
                         arguments: ["lat": coord.lat, "lon": coord.lon]) { [weak self] reply in
                Task { @MainActor [weak self] in
                    // The run did not have the tile: no stop notice will come.
                    guard reply.result?.boolValue != true else { return }
                    self?.stopConfirmed(coord, attempt: 0, done: false)
                }
            }
        }
        let percent = activity.tiles[coord]?.percent ?? 0
        activity.tiles[coord] = TileProgress(state: .stopped, label: "stopped", percent: percent)
        activity.stepStrips[coord]?.stop(at: ProcessInfo.processInfo.systemUptime)
        if let clock = activity.tileClocks[coord] {
            activity.tileClocks[coord] = O4TileClock(
                lat: clock.lat, lon: clock.lon, elapsedSeconds: clock.elapsedSeconds,
                remainingSeconds: nil, finished: true)
        }
    }

    /// Resume a stopped tile with the settings ITS run was started with.
    /// Engine idle: a single-tile run, now. Engine busy: queued into the
    /// RUNNING build now (#1326) — held only until the engine confirms the
    /// stop it is resuming from.
    func resumeTile(_ coord: TileCoord) {
        guard usesProtocol else { return }
        let settings = activity.runSettings[coord]
            ?? TileRunSettings(provider: buildProvider, zl: buildZL)
        startResumeRun([(tiles: [coord], settings: settings)])
    }

    /// The engine is done with the attempt the user stopped (#1326): its
    /// later events are stale by number, and a re-queue held for it goes
    /// to the engine now — unless the tile finished before its stop took
    /// effect, which leaves nothing to resume.
    private func stopConfirmed(_ coord: TileCoord, attempt: Int, done: Bool) {
        stopPending.remove(coord)
        if attempt > 0 { staleThrough[coord] = max(attempt, staleThrough[coord] ?? 0) }
        guard let held = heldForStop.removeValue(forKey: coord), !done else { return }
        if isBuilding {
            sendProtocolBuild([coord], provider: held.settings.provider, zl: held.settings.zl,
                              boundaryPolicy: held.boundaryPolicy)
        } else {
            startResumeRun([(tiles: [coord], settings: held.settings)])
        }
    }

    /// Group tiles so one batch per (source, ZL) pair goes over as one
    /// enqueue_build, in first-seen order.
    static func batchedBySettings(_ tiles: [(coord: TileCoord, settings: TileRunSettings)])
        -> [(tiles: [TileCoord], settings: TileRunSettings)] {
        var batches: [(tiles: [TileCoord], settings: TileRunSettings)] = []
        for (coord, settings) in tiles {
            if let index = batches.firstIndex(where: { $0.settings == settings }) {
                batches[index].tiles.append(coord)
            } else {
                batches.append((tiles: [coord], settings: settings))
            }
        }
        return batches
    }

    // MARK: Build failed tiles again (#821)

    /// The last run's failed and never-started tiles, each with the
    /// settings it was queued with — what "Build failed tiles again"
    /// re-queues. Taken when the run ends, before the rows linger-clear.
    @Published private(set) var retryTiles: [(coord: TileCoord, settings: TileRunSettings)] = []

    private func keepRetryTiles() {
        let current = TileRunSettings(provider: buildProvider, zl: buildZL)
        retryTiles = activity.runOrder.compactMap { coord in
            guard activity.runTiles.contains(coord),
                  let state = activity.tiles[coord]?.state,
                  state == .error || state == .queued,
                  heldForStop[coord] == nil else { return nil }
            return (coord: coord, settings: activity.runSettings[coord] ?? current)
        }
    }

    /// Re-queue the last run's failed and not-started tiles with the same
    /// options, through the same enqueue path a resume uses.
    func buildFailedTilesAgain() {
        let todo = retryTiles
        guard !todo.isEmpty, !isBuilding else { return }
        retryTiles = []
        if usesProtocol {
            startResumeRun(Self.batchedBySettings(todo))
        } else {
            startLegacyBuild(todo.map { $0.coord })
        }
    }

    /// The Build button's own machinery (`startProtocolBuild`) without its
    /// selection guard: a resumed tile need not still be selected on the
    /// map — not having to re-find it is the whole point.
    private func startResumeRun(_ batches: [(tiles: [TileCoord], settings: TileRunSettings)]) {
        guard engine != nil else { return }
        lastRunSummary = nil
        // A resumed tile starts over: drop its old row and clock so the run
        // re-creates both at zero (and keeps one row per tile).
        for coord in batches.flatMap(\.tiles) {
            activity.tiles[coord] = nil
            activity.runOrder.removeAll { $0 == coord }
            activity.tileClocks[coord] = nil
        }
        // A resume enqueues tiles too, so it asks the same question
        // (spec §C.7: every entry point that enqueues).
        startProtocolBuild(batches.map {
            BuildBatch(tiles: $0.tiles, provider: $0.settings.provider,
                       zl: $0.settings.zl)
        })
    }

    // MARK: Stop/resume rules (pure — no engine, no view)

    /// May an incoming engine state overwrite a row the user has STOPPED?
    /// Only a terminal outcome: a tile that finished before its cancel took
    /// effect is genuinely built, and "stopped" over a built tile would be
    /// a lie; a failure is likewise real. Everything else is stale news
    /// from a run the row has already left.
    static func mayOverwriteStopped(_ incoming: TileProgress.State) -> Bool {
        switch incoming {
        case .done, .error: return true
        case .queued, .active, .indeterminate, .stopped: return false
        }
    }

    /// The row an engine event should leave behind, given what the row
    /// already shows. nil = the event is stale, drop it.
    static func resolving(_ incoming: TileProgress,
                          over current: TileProgress?) -> TileProgress? {
        if let current, current.state == .stopped, !mayOverwriteStopped(incoming.state) {
            // The engine's late "stopped" notice adds one thing to a row
            // already stopped here: what the tile is left with (#598).
            guard incoming.label == "stopped", !incoming.detail.isEmpty,
                  incoming.detail != current.detail else { return nil }
            var kept = current
            kept.detail = incoming.detail
            return kept
        }
        return incoming
    }

    /// Is an engine event news from an attempt the user STOPPED (#1326)?
    /// While the stop is unconfirmed everything about the tile is; after
    /// that the event's `attempt` decides — at or below the stopped one is
    /// late news, above it is the attempt that re-queued the tile. The
    /// row's displayed state decides nothing: a re-queued row reads
    /// "queued" while the old attempt may still be talking.
    static func isStoppedAttempt(_ attempt: Int, staleThrough: Int?, stopPending: Bool) -> Bool {
        if stopPending { return true }
        guard attempt > 0, let staleThrough else { return false }
        return attempt <= staleThrough
    }

    /// Fold a tile's progress event into its row's step strip (#825).
    private func feedStepStrip(_ event: O4Event) {
        let coord: TileCoord
        switch event {
        case .stepProgress(let la, let lo, _, _, _, _, _), .autoPatchBegin(_, let la, let lo),
             .autoPatchProgress(_, _, _, _, _, _, let la, let lo),
             .tileState(let la, let lo, _, _, _, _, _), .buildDone(let la, let lo, _, _, _, _, _, _):
            coord = TileCoord(lat: la, lon: lo)
        default:
            return
        }
        guard var strip = activity.stepStrips[coord] else { return }
        strip.apply(event, at: ProcessInfo.processInfo.systemUptime)
        if strip != activity.stepStrips[coord] { activity.stepStrips[coord] = strip }
    }

    /// `resolving(_:over:)` for an event that may be a stopped attempt's:
    /// such an event lands only as a terminal outcome (a tile that finished
    /// or failed before its stop took effect really did), or as the detail
    /// line of a row still showing the stop.
    static func resolving(_ incoming: TileProgress, over current: TileProgress?,
                          stoppedAttempt: Bool) -> TileProgress? {
        if stoppedAttempt, !mayOverwriteStopped(incoming.state), current?.state != .stopped {
            return nil
        }
        return resolving(incoming, over: current)
    }

    /// The clock a row shows for the engine's TileClocks `row`, or nil for
    /// none: a stopped row keeps the clock its stop froze; a queued row
    /// runs no clock — its estimate alone, never the elapsed of an attempt
    /// that was stopped (the 2 h timer under a queued row, #1326).
    static func displayedClock(_ row: O4TileClock, state: TileProgress.State?,
                               previous: O4TileClock?) -> O4TileClock? {
        switch state {
        case .stopped:
            return previous
        case .queued:
            return O4TileClock(lat: row.lat, lon: row.lon, elapsedSeconds: 0,
                               remainingSeconds: row.remainingSeconds, finished: false)
        case .active, .indeterminate, .done, .error, nil:
            return row
        }
    }

    /// Which tiles of an enqueue go to the engine now and which wait for
    /// their stop to be confirmed (#1326), each in the order given.
    static func splitHeld(_ tiles: [TileCoord], stopPending: Set<TileCoord>)
        -> (send: [TileCoord], hold: [TileCoord]) {
        (tiles.filter { !stopPending.contains($0) }, tiles.filter { stopPending.contains($0) })
    }

    /// What the patch box's "Rebuild tile" does (#1322): a running build
    /// takes the tile, unless it is already part of it.
    enum RebuildDecision: Equatable { case startRun, queueIntoRun, alreadyInRun }

    static func rebuildDecision(isBuilding: Bool, row: TileProgress.State?,
                                held: Bool) -> RebuildDecision {
        guard isBuilding else { return .startRun }
        return isInRun(row, held: held) ? .alreadyInRun : .queueIntoRun
    }

    func rebuildDecision(for coord: TileCoord) -> RebuildDecision {
        Self.rebuildDecision(isBuilding: isBuilding, row: activity.tiles[coord]?.state,
                             held: heldForStop[coord] != nil)
    }

    private func applyTileEvent(_ incoming: TileProgress, attempt: Int, to coord: TileCoord) {
        let stale = Self.isStoppedAttempt(attempt, staleThrough: staleThrough[coord],
                                          stopPending: stopPending.contains(coord))
        guard let next = Self.resolving(incoming, over: activity.tiles[coord],
                                        stoppedAttempt: stale) else { return }
        activity.tiles[coord] = next
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
    // XPTerrainBuilder_±xx±yyy.cfg files as sparse overrides: a value equal to the
    // global effective value REMOVES the override. With no selection they
    // edit the global defaults. App-scope settings always edit the global
    // config.

    /// Bumped after any tile-config write so rows re-read their state.
    @Published private(set) var tileConfigGeneration = 0 {
        didSet { refreshCustomizedTiles(only: selected) }
    }

    private func tileConfigURL(_ coord: TileCoord) -> URL? {
        guard let base = tileBaseFolder else { return nil }
        return base.appendingPathComponent(OrthoEngine.tileFolderName(lat: coord.lat, lon: coord.lon))
            .appendingPathComponent(OrthoConfigNames.tileFileName(lat: coord.lat, lon: coord.lon))
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
        writeThroughToSelectedTiles(item.name, value)
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
            file.stampTileConfig(appVersion: AppVersion.current)
            try? file.write(to: url)
        }
        tileConfigGeneration += 1
    }

    func revertTileOverrides(for name: String) {
        revertTileOverrides(for: [name])
    }

    /// Engine gate for auto-patch object reseating inside installed custom
    /// airport packs. A global XPTerrainBuilder.cfg var (modify_custom_airports),
    /// NOT a per-run argument: config reaches parallel worker children,
    /// and the Qt front end reads the same switch. Default matches the
    /// engine's (on).
    var modifyCustomAirports: Bool {
        globalConfigValues["modify_custom_airports"]?.boolValue ?? true
    }

    func setModifyCustomAirports(_ enabled: Bool) {
        setConfigValue("modify_custom_airports", to: .bool(enabled))
        // WRITE-THROUGH (owner ruling RULINGS 2026-09-18a (2)): this is a
        // TILE-scope var (SettingsLayout.swift), and a tile cfg carrying
        // it BEATS the global the line above writes — which is BETA2
        // GEN-1 itself: all 23 of the owner's tile cfgs said True while
        // this box was unchecked, so the engine reseated packs anyway.
        // Same rule as every other tile-scope edit: set the override when
        // it now differs from the global, REMOVE it when it matches.
        writeThroughToSelectedTiles("modify_custom_airports", .bool(enabled))
    }

    /// Set-or-remove one tile-scope override on every selected tile, against
    /// the global effective value (RULINGS 2026-09-18a (2) — a settings
    /// change or reset updates the selected tiles' cfgs).
    ///
    /// The engine owns the same rule as `tile_settings_write`
    /// (O4_Settings_Model.write_tile), which the Qt window calls in
    /// process; this local writer predates that command and is the one
    /// convergence owed here.
    private func writeThroughToSelectedTiles(_ name: String, _ value: O4Value) {
        guard !selected.isEmpty else { return }
        let inherited = configValue(for: name)
        for coord in selected {
            guard let url = tileConfigURL(coord) else { continue }
            var file = (try? OrthoConfigFile(contentsOf: url)) ?? OrthoConfigFile()
            if let inherited, value == inherited {
                file.remove(name)
            } else {
                file.set(name, to: value)
            }
            // STAMPED (RULINGS 2026-09-18c (2)): provenance, and the
            // library's "built here" witness.
            file.stampTileConfig(appVersion: AppVersion.current)
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
            // A tile value equal to the new global is no longer a
            // customization (and a different one now is): re-badge.
            refreshCustomizedTiles()
        } catch {
            engineError = "Could not write \(configURL.lastPathComponent): \(error.localizedDescription)"
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
        activity.beginRun()
        legacyQueue = todo
        legacyDone = 0
        legacyFailed = 0
        activity.queueRows(todo)
        stampRunTags(todo)
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
                console.append("Remaining \(legacyQueue.count) tile(s) not started — use “Build failed tiles again” after fixing the error.")
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
        keepRetryTiles()
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
            self.activity.endRun()
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
