import Foundation
import SwiftUI
import SceneryKit

/// UserDefaults key for the X-Plane root path. Lives in the app's standard
/// preferences plist (~/Library/Preferences/com.novemberlima.XPSceneryDoctor.plist
/// when run from the bundle).
enum PrefKeys {
    static let xplanePath = "XPlanePath"
}

/// High-frequency progress state, isolated from AnalysisController so a
/// stage tick can't invalidate the map canvas, inspector and results list —
/// only the small views that actually render progress observe this.
@MainActor
final class ProgressModel: ObservableObject {
    @Published var stageLabel = ""
    /// (probed, total) while the installation scan runs — drives the
    /// determinate loading bar. nil outside a scan.
    @Published var scanProgress: (done: Int, total: Int)?
    /// (checked, total) while the unused-resource cross-check sweeps every
    /// pack. nil outside that stage.
    @Published var unusedVerifyProgress: (done: Int, total: Int)?
    /// (completed, total, current pack) while the per-pack analysis pipeline
    /// runs — drives the determinate ring in the results bottom bar. nil
    /// outside that stage.
    @Published var packProgress: (done: Int, total: Int, name: String)?
}

@MainActor
final class AnalysisController: ObservableObject {
    @AppStorage(PrefKeys.xplanePath) var xplanePath: String = ""

    /// See ProgressModel — deliberately NOT @Published here.
    let progress = ProgressModel()

    @Published var isRunning = false
    @Published var report: AnalysisReport?
    /// Bumped when a fresh report lands; views observe it to open the window.
    @Published var reportGeneration = 0
    @Published var errorMessage: String?

    // Map: the scanned installation (packs with tiles/airports/status) and
    // the user's tile selection.
    //
    // The camera and canvas size are ViewState objects OWNED here but NOT
    // observed: only MapCanvasView subscribes, so a drag frame redraws the
    // canvas alone. If the main window held them as @StateObject, every
    // camera tick would re-evaluate the whole window body (the beachball).
    let mapCamera = ViewState(MapCamera())
    let mapCanvasSize = ViewState(CGSize.zero)
    /// Packs visible in the map viewport, debounced from camera movement.
    /// This IS the working set: the inspector, results filter and analysis
    /// priority all follow whatever the map is looking at.
    @Published var viewportPacks: [SceneryPack] = []
    private var viewportTask: Task<Void, Never>?

    @Published var installationPacks: [SceneryPack] = []
    /// The last completed full scan (packs + library indexes) — handed to
    /// the analyzer so it doesn't rescan the same 4,200 packs minutes after
    /// the map scan already did.
    private var lastScan: Installation?
    /// Precomputed draw/query structures — rebuilt only when the scan
    /// changes, never per frame.
    @Published var mapOverlays = MapOverlays.empty
    @Published var isScanningInstallation = false
    /// Read by analysis workers pulling packs — tile selection changes move
    /// the selected packs to the front of the pending queue mid-run.
    let priorityBox = PriorityBox()
    /// Packs our own fixes/actions touched since their cache entries were
    /// written — forced fresh on the next run.
    private var pendingInvalidation: Set<String> = []
    /// Fixes applied WHILE a run is in flight: the run's final report was
    /// computed from pre-fix reads, so these are subtracted when it lands
    /// (otherwise fixed findings would resurrect at run end). Correctness
    /// across runs is already covered by content signatures +
    /// pendingInvalidation; this is only about the in-flight report.
    private var fixedDuringRun: Set<UUID> = []
    private var trashedDuringRun: Set<String> = []
    /// The seeded (last-session) unused groups are REPLACED by the run's
    /// first fresh batch, then subsequent batches append.
    private var receivedUnusedThisRun = false

    // Search: debounced, filtered off the main thread against a precomputed
    // lowercased corpus. nil = no active search. (Live filtering of 7k+
    // findings on every keystroke beachballs the report window.)
    @Published var searchFilterIDs: Set<UUID>? = nil
    private var searchCorpus: [(id: UUID, blob: String)] = []
    private var searchTask: Task<Void, Never>?

    init() {
        loadPersistedReport()
    }

    // Pack actions (duplicates view)
    @Published var isApplyingAction = false
    @Published var actionErrors: [PackActionOutcome] = []
    /// Fresh ini ranks published right after a drag-reorder so the inspector
    /// shows the new order instantly; the follow-up rescan (seconds on a big
    /// install) clears it once packs carry the new iniIndex themselves.
    @Published var iniOrderOverride: [String: Int]? = nil

    // Fixes + modification log
    @Published var isFixing = false
    @Published var fixErrors: [String] = []
    @Published var lastFixSummary: String?
    @Published var modifications: [ModificationRecord] = []

    private let fixEngine = FixEngine()

    var rootURL: URL? {
        guard !xplanePath.isEmpty else { return nil }
        return URL(fileURLWithPath: xplanePath, isDirectory: true)
    }

    var pathIsValid: Bool {
        guard let url = rootURL else { return false }
        return Installation.looksLikeXPlaneRoot(url)
    }

    // MARK: - Installation scan (map data)

    /// A refresh requested while a scan is in flight; runs when it finishes.
    /// (An in-flight scan read the ini before whatever prompted the request,
    /// so its results can be stale — the follow-up scan settles things.)
    private var pendingRefresh = false

    func refreshInstallation() {
        guard let root = rootURL else { return }
        guard !isScanningInstallation else {
            pendingRefresh = true
            return
        }
        isScanningInstallation = true
        Task { [weak self] in
            let (installation, overlays) = await Task.detached(priority: .userInitiated) {
                let installation = InstallationScanner(root: root).scan(
                    progress: { done, total in
                        Task { @MainActor [weak self] in
                            self?.progress.scanProgress = (done, total)
                        }
                    },
                    onPartial: { partial in
                        // Populate the map live as packs are discovered.
                        // Overlays are built here on the worker thread; the
                        // completed scan below supersedes any queued partial.
                        let overlays = MapOverlays(packs: partial)
                        Task { @MainActor [weak self] in
                            guard let self, self.isScanningInstallation else { return }
                            self.installationPacks = partial
                            self.mapOverlays = overlays
                                .applyingExactMarkers(self.report?.packMarkers ?? [:])
                            self.scheduleViewportUpdate()
                        }
                    }
                )
                return (installation, MapOverlays(packs: installation.packs))
            }.value
            guard let self else { return }
            self.lastScan = installation
            self.installationPacks = installation.packs
            // Exact marks from the last report survive the rescan until the
            // auto-run refreshes them.
            self.mapOverlays = overlays.applyingExactMarkers(self.report?.packMarkers ?? [:])
            self.isScanningInstallation = false
            self.progress.scanProgress = nil
            self.scheduleViewportUpdate()
            if self.pendingRefresh {
                self.pendingRefresh = false
                self.refreshInstallation()
            } else {
                // Only a scan that saw the final ini may drop the reorder
                // override — packs now carry the new iniIndex themselves.
                self.iniOrderOverride = nil
                // Analysis runs by itself: the signature cache makes an
                // unchanged install a fast pass, and anything that changed
                // gets picked up without the user asking.
                if !self.isRunning {
                    self.analyze()
                }
            }
        }
    }

    /// Debounced (120 ms) recompute of the packs visible in the map window.
    /// Called from the canvas as the camera moves; never runs in a render.
    func scheduleViewportUpdate() {
        viewportTask?.cancel()
        let cam = mapCamera.value
        let size = mapCanvasSize.value
        let overlays = mapOverlays
        viewportTask = Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(120))
            guard !Task.isCancelled, size.width > 0 else { return }
            let halfW = Double(size.width) / 2 / cam.scale
            let halfH = Double(size.height) / 2 / cam.scale
            let packs = overlays.packs(inViewport: (
                minLon: cam.centerLon - halfW, maxLon: cam.centerLon + halfW,
                minLat: cam.centerLat - halfH, maxLat: cam.centerLat + halfH
            ))
            let sorted = packs.sorted { $0.name.lowercased() < $1.name.lowercased() }
            self?.viewportPacks = sorted
            // Panning to an area mid-analysis moves its packs to the front
            // of the work queue.
            self?.priorityBox.update(Set(sorted.map { $0.name }))
        }
    }

    /// Zoom the map to a pack's coverage — shared by the toolbar search and
    /// the inspector's double-click. Airports first: an airport point is
    /// always right, while a tile-bbox fit spans the ocean for packs that
    /// ship stray tiles (the CYHZ +44+044 case).
    func zoomToPack(_ pack: SceneryPack) {
        var cam = mapCamera.value
        if let airport = pack.airports.values.first {
            cam.centerLon = airport.longitude
            cam.centerLat = airport.latitude
            cam.scale = max(cam.scale, 60)
        } else {
            let tiles = pack.tiles.compactMap { TileMath.parse($0) }
            guard !tiles.isEmpty else { return }
            let lats = tiles.map { Double($0.lat) }, lons = tiles.map { Double($0.lon) }
            cam.centerLat = (lats.min()! + lats.max()! + 1) / 2
            cam.centerLon = (lons.min()! + lons.max()! + 1) / 2
            let spanLon = max(lons.max()! - lons.min()! + 1, 2)
            let spanLat = max(lats.max()! - lats.min()! + 1, 2)
            cam.scale = min(700 / spanLon, 400 / spanLat, 120)
        }
        cam.clamp(in: mapCanvasSize.value)
        mapCamera.value = cam
        scheduleViewportUpdate()
    }

    // MARK: - Analysis

    private enum StreamMessage: Sendable {
        case event(Analyzer.Event)
        case completed(AnalysisReport)
    }

    /// Starts an analysis and streams results into the report as they land,
    /// so the report window (opened immediately via reportGeneration) fills
    /// in live. Finding batches are coalesced to ~0.4 s flushes — the pack
    /// scan finishes dozens of packs per second and per-batch List updates
    /// would hammer SwiftUI diffing.
    func analyze(scope: Set<String>? = nil) {
        guard let root = rootURL, !isRunning else { return }
        isRunning = true
        progress.stageLabel = "Starting…"
        errorMessage = nil
        fixedDuringRun = []
        trashedDuringRun = []
        receivedUnusedThisRun = false
        // Keep the last results ON SCREEN while the run streams: cached
        // packs re-emit the very same findings (same UUIDs — deduped in
        // flushPending), changed packs re-analyze, and the final report
        // supersedes everything. Blanking the report here made every
        // relaunch look like starting from zero even though the answers
        // were already sitting in last-report.json.
        if report == nil {
            report = AnalysisReport(xplaneRoot: root.path, findings: [], stats: AnalysisStats())
        }
        reportGeneration += 1

        // Manual scoped runs bypass the cache for the selection (the user is
        // asking "check this again"); packs our own fixes touched are always
        // recomputed. Everything else rides the signature cache.
        var options = Analyzer.Options(scope: scope, cacheURL: Self.cacheFileURL)
        options.forceFresh = pendingInvalidation
        if let scope { options.forceFresh.formUnion(scope) }
        pendingInvalidation = []
        // Skip the analyzer's own rescan when the map scan just did the
        // same work (it triggers analysis right after finishing).
        if let lastScan, lastScan.root == root { options.preScanned = lastScan }
        let priorityBox = self.priorityBox

        // Full/auto runs stay off the performance cores (.utility) so the
        // machine remains usable while they grind; only a manual scoped run
        // — where the user is actively waiting — gets .userInitiated.
        // concurrentPerform workers inherit the spawning thread's QoS.
        let taskPriority: TaskPriority = scope == nil ? .utility : .userInitiated
        let stream = AsyncStream<StreamMessage> { continuation in
            Task.detached(priority: taskPriority) {
                // Stage events fire per pack — hundreds per second when the
                // cache makes packs near-instant. Throttle at the PRODUCER so
                // the main actor never even sees the flood (terminal events
                // always pass; the final report supersedes everything).
                let lastStageYield = LockedBox(ContinuousClock.now - .seconds(1))
                let final = Analyzer(root: root).run(
                    options: options,
                    priority: { priorityBox.current }
                ) { event in
                    if case .stage(let stage) = event {
                        if case .done = stage {} else {
                            let now = ContinuousClock.now
                            let skip = lastStageYield.withLock { last -> Bool in
                                if now - last < .milliseconds(100) { return true }
                                last = now
                                return false
                            }
                            if skip { return }
                        }
                    }
                    continuation.yield(.event(event))
                }
                continuation.yield(.completed(final))
                continuation.finish()
            }
        }

        Task { [weak self] in
            var pending: [Finding] = []
            var lastFlush = ContinuousClock.now
            for await message in stream {
                guard let self else { return }
                switch message {
                case .event(.stage(let stage)):
                    self.progress.stageLabel = stage.label
                    if case .verifyingUnused(let done, let total) = stage {
                        self.progress.unusedVerifyProgress = (done, total)
                    } else {
                        self.progress.unusedVerifyProgress = nil
                    }
                    if case .inspectingPack(let name, let done, let total) = stage {
                        self.progress.packProgress = (done, total, name)
                    } else {
                        self.progress.packProgress = nil
                    }
                    // Reassigning the report re-diffs every list — keep that
                    // at the same ~0.4 s cadence as finding batches, not per
                    // stage tick.
                    if ContinuousClock.now - lastFlush > .milliseconds(400) {
                        self.flushPending(&pending)
                        lastFlush = .now
                    }
                case .event(.findings(let new)):
                    pending.append(contentsOf: new)
                    if ContinuousClock.now - lastFlush > .milliseconds(400) {
                        self.flushPending(&pending)
                        lastFlush = .now
                        self.persistReportThrottled()
                    }
                case .event(.duplicateGroups(let groups)):
                    self.report?.duplicateGroups = groups
                case .event(.unusedResources(let groups)):
                    if self.receivedUnusedThisRun {
                        self.report?.unusedResources.append(contentsOf: groups)
                    } else {
                        // First fresh batch replaces the seeded last-session
                        // groups (appending would double them).
                        self.receivedUnusedThisRun = true
                        self.report?.unusedResources = groups
                    }
                case .completed(let final):
                    // The final report supersedes everything streamed —
                    // minus whatever the user fixed while it was running
                    // (it was computed from pre-fix reads).
                    pending = []
                    var final = final
                    if !self.fixedDuringRun.isEmpty {
                        let fixed = self.fixedDuringRun
                        final.findings.removeAll { fixed.contains($0.id) }
                    }
                    if !self.trashedDuringRun.isEmpty {
                        let trashed = self.trashedDuringRun
                        final.unusedResources = final.unusedResources.compactMap { group in
                            var group = group
                            group.files.removeAll { trashed.contains($0.path) }
                            return group.files.isEmpty ? nil : group
                        }
                    }
                    self.report = final
                    self.isRunning = false
                    self.progress.unusedVerifyProgress = nil
                    self.progress.packProgress = nil
                    if let markers = final.packMarkers {
                        self.mapOverlays = self.mapOverlays.applyingExactMarkers(markers)
                    }
                    self.rebuildSearchCorpus()
                    self.persistReport()
                }
            }
        }
    }

    // MARK: - Search

    func updateSearch(_ query: String) {
        searchTask?.cancel()
        let trimmed = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !trimmed.isEmpty else {
            searchFilterIDs = nil
            return
        }
        if searchCorpus.isEmpty { rebuildSearchCorpus() }
        let corpus = searchCorpus
        searchTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(250)) // debounce
            guard !Task.isCancelled else { return }
            let ids = await Task.detached(priority: .userInitiated) {
                Set(corpus.filter { $0.blob.contains(trimmed) }.map { $0.id })
            }.value
            guard !Task.isCancelled else { return }
            self?.searchFilterIDs = ids
        }
    }

    private func rebuildSearchCorpus() {
        guard let report else {
            searchCorpus = []
            return
        }
        searchCorpus = report.findings.map { finding in
            var blob = finding.title.lowercased()
            blob += "\n" + finding.detail.lowercased()
            if let path = finding.path { blob += "\n" + path.lowercased() }
            if let pack = finding.packName { blob += "\n" + pack.lowercased() }
            return (finding.id, blob)
        }
    }

    // MARK: - Persistence

    static var reportFileURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("XPSceneryDoctor", isDirectory: true)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("last-report.json")
    }

    static var cacheFileURL: URL {
        reportFileURL.deletingLastPathComponent().appendingPathComponent("analysis-cache.json")
    }

    /// Packs (by prefix of their folder path) that the given absolute file
    /// paths live in — used to invalidate cache entries after our own edits.
    private func packNames(containing paths: [String]) -> Set<String> {
        var names = Set<String>()
        for path in paths {
            for pack in installationPacks where path.hasPrefix(pack.url.path + "/") {
                names.insert(pack.name)
                break
            }
        }
        return names
    }

    /// Save the report so quitting and relaunching resumes the review session.
    func persistReport() {
        guard let report else { return }
        let url = Self.reportFileURL
        Task.detached(priority: .utility) {
            if let data = try? report.jsonData() {
                try? data.write(to: url, options: .atomic)
            }
        }
    }

    /// Persist the STREAMING report at most once a minute during a run, so a
    /// relaunch seeds with roughly what was on screen — not the last
    /// completed run's snapshot from hours ago.
    private var lastReportPersist = ContinuousClock.now - .seconds(120)
    private func persistReportThrottled() {
        guard ContinuousClock.now - lastReportPersist >= .seconds(60) else { return }
        lastReportPersist = .now
        persistReport()
    }

    private func loadPersistedReport() {
        let url = Self.reportFileURL
        Task { [weak self] in
            let loaded = await Task.detached(priority: .utility) { () -> AnalysisReport? in
                guard let data = try? Data(contentsOf: url) else { return nil }
                let decoder = JSONDecoder()
                decoder.dateDecodingStrategy = .iso8601
                return try? decoder.decode(AnalysisReport.self, from: data)
            }.value
            guard let self, let loaded, self.report == nil, !self.isRunning else { return }
            self.report = loaded
            self.rebuildSearchCorpus()
        }
    }

    private func flushPending(_ pending: inout [Finding]) {
        guard !pending.isEmpty, var current = report else { return }
        // The report is seeded with last session's findings; cache-served
        // packs re-emit the SAME findings (UUIDs persist through the cache),
        // so only genuinely new ones append.
        let existing = Set(current.findings.map { $0.id })
        let fresh = pending.filter { !existing.contains($0.id) }
        pending = []
        guard !fresh.isEmpty else { return }
        current.findings.append(contentsOf: fresh)
        current.findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        report = current
    }

    // MARK: - Pack actions

    func applyPackAction(_ action: PackAction, to packNames: [String]) {
        guard let root = rootURL, !packNames.isEmpty, !isApplyingAction else { return }
        // Enable/disable only rewrite the ini and are fine mid-analysis
        // (the pipeline reads pack FILES; the ini was consumed at scan
        // start). Folder-moving actions would pull files out from under
        // the analyzers — refuse those with an explanation, not silence.
        if isRunning && !action.isIniOnly {
            errorMessage = "\(action.label) moves package folders, which can't happen while the analysis is reading them. Try again when it finishes (Enable/Disable work anytime)."
            return
        }
        isApplyingAction = true
        actionErrors = []

        Task { [weak self] in
            let (outcomes, dupFindings, groups) = await Task.detached(priority: .userInitiated) {
                let outcomes = PackActionService(root: root).apply(action, to: packNames)
                // Re-scan duplicate state so the table reflects reality, not
                // our guess about what the action did.
                let (findings, groups) = Analyzer(root: root).refreshDuplicates()
                return (outcomes, findings, groups)
            }.value

            guard let self else { return }
            if var report = self.report {
                report.duplicateGroups = groups
                report.findings = report.findings.filter { $0.category != .duplicatePackage } + dupFindings
                report.findings.sort {
                    ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
                }
                self.report = report
            }
            self.actionErrors = outcomes.filter { !$0.success }
            self.pendingInvalidation.formUnion(
                outcomes.filter { $0.success }.map { $0.packName })
            self.isApplyingAction = false
            self.rebuildSearchCorpus()
            self.persistReport()
        }
    }

    /// Rewrite scenery_packs.ini so `orderedNames` load in this relative
    /// order (minimal-movement permutation — see PackActionService.reorder).
    /// Allowed during analysis: reordering is ini-only, like enable/disable
    /// — the running pipeline reads pack FILES, and it consumed the ini at
    /// scan start. (This guard once included !isRunning, which made drags
    /// silently snap back for the entire 30-minute cold run.)
    func reorderPacks(_ orderedNames: [String]) {
        guard let root = rootURL, orderedNames.count > 1, !isApplyingAction else { return }
        isApplyingAction = true
        Task { [weak self] in
            let (error, order) = await Task.detached(priority: .userInitiated) {
                let service = PackActionService(root: root)
                let error = service.reorder(packNames: orderedNames)
                return (error, service.iniOrder())
            }.value
            guard let self else { return }
            self.isApplyingAction = false
            if let error {
                self.errorMessage = "Could not update scenery_packs.ini: \(error.localizedDescription)"
            } else {
                self.iniOrderOverride = order
            }
            self.refreshInstallation()
        }
    }

    // MARK: - Fixes

    /// Safe DURING a run too: a finding is only visible once its pack's
    /// scan completed, fix writes are atomic (concurrent readers see
    /// old-or-new, never torn), and staleness self-heals via content
    /// signatures + pendingInvalidation. fixedDuringRun keeps the run's
    /// final report from resurrecting what was just fixed.
    func applyFixes(to findings: [Finding]) {
        let fixable = findings.filter { $0.proposedFix != nil }
        guard !fixable.isEmpty, !isFixing else { return }
        isFixing = true
        fixErrors = []

        let engine = fixEngine
        Task { [weak self] in
            let outcomes = await Task.detached(priority: .userInitiated) {
                engine.apply(fixable)
            }.value

            guard let self else { return }
            let succeeded = Set(outcomes.filter { $0.success }.map { $0.findingID })
            self.pendingInvalidation.formUnion(self.packNames(
                containing: outcomes.filter { $0.success }.map { $0.filePath }))
            if self.isRunning { self.fixedDuringRun.formUnion(succeeded) }
            if var report = self.report {
                report.findings.removeAll { succeeded.contains($0.id) }
                self.report = report
            }
            self.fixErrors = outcomes.filter { !$0.success }.map {
                "\(URL(fileURLWithPath: $0.filePath).lastPathComponent): \($0.message ?? "unknown error")"
            }
            if !succeeded.isEmpty {
                self.lastFixSummary = "Fixed \(succeeded.count) file\(succeeded.count == 1 ? "" : "s"). Every change is listed under Window ▸ Modifications and can be reverted."
            }
            self.loadModifications()
            self.isFixing = false
            self.rebuildSearchCorpus()
            self.persistReport()
        }
    }

    /// Trash unused files, recording each in the manifest for revert.
    /// Allowed during a run: unused groups only exist AFTER the deletion-
    /// grade cross-check, and trashing is atomic per file.
    func trashUnusedFiles(_ paths: [String]) {
        guard !paths.isEmpty, !isFixing else { return }
        isFixing = true
        fixErrors = []

        let engine = fixEngine
        Task { [weak self] in
            let outcomes = await Task.detached(priority: .userInitiated) {
                engine.trashFiles(paths, checkID: "UNUSED-01", summary: "Moved to Trash (unused resource)")
            }.value

            guard let self else { return }
            let trashed = Set(outcomes.filter { $0.success }.map { $0.filePath })
            self.pendingInvalidation.formUnion(self.packNames(containing: Array(trashed)))
            if self.isRunning { self.trashedDuringRun.formUnion(trashed) }
            if var report = self.report {
                report.unusedResources = report.unusedResources.compactMap { group in
                    var group = group
                    group.files.removeAll { trashed.contains($0.path) }
                    return group.files.isEmpty ? nil : group
                }
                self.report = report
            }
            self.fixErrors = outcomes.filter { !$0.success }.map {
                "\(URL(fileURLWithPath: $0.filePath).lastPathComponent): \($0.message ?? "unknown error")"
            }
            if !trashed.isEmpty {
                self.lastFixSummary = "Moved \(trashed.count) file\(trashed.count == 1 ? "" : "s") to the Trash. Restore anytime from Window ▸ Modifications or the Trash itself."
            }
            self.loadModifications()
            self.isFixing = false
            self.rebuildSearchCorpus()
            self.persistReport()
        }
    }

    func loadModifications() {
        let engine = fixEngine
        Task { [weak self] in
            let records = await Task.detached { engine.log.load() }.value
            self?.modifications = records.sorted { $0.date > $1.date }
        }
    }

    /// Allowed during a run for the same reasons fixes are: restores are
    /// atomic file moves, and the touched packs re-analyze via
    /// pendingInvalidation + content signatures.
    func revertModifications(_ records: [ModificationRecord]) {
        guard !records.isEmpty, !isFixing else { return }
        isFixing = true
        fixErrors = []

        let engine = fixEngine
        Task { [weak self] in
            let outcomes = await Task.detached(priority: .userInitiated) {
                engine.revert(records)
            }.value

            guard let self else { return }
            self.fixErrors = outcomes.filter { !$0.success }.map {
                "\(URL(fileURLWithPath: $0.record.filePath).lastPathComponent): \($0.message ?? "unknown error")"
            }
            self.pendingInvalidation.formUnion(self.packNames(
                containing: outcomes.filter { $0.success }.map { $0.record.filePath }))
            let reverted = outcomes.filter { $0.success }.count
            if reverted > 0 {
                self.lastFixSummary = "Reverted \(reverted) file\(reverted == 1 ? "" : "s") to the original. Re-run Analyze (⌘R) to refresh findings."
            }
            self.loadModifications()
            self.isFixing = false
        }
    }

    // MARK: - Export

    func exportReportJSON() {
        guard let report else { return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "XPSceneryDoctor-report.json"
        panel.allowedContentTypes = [.json]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            try report.jsonData().write(to: url)
        } catch {
            errorMessage = "Could not save report: \(error.localizedDescription)"
        }
    }
}
