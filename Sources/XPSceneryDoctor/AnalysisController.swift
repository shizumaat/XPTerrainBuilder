import Foundation
import SwiftUI
import SceneryKit

/// UserDefaults key for the X-Plane root path. Lives in the app's standard
/// preferences plist (~/Library/Preferences/com.novemberlima.XPSceneryDoctor.plist
/// when run from the bundle).
enum PrefKeys {
    static let xplanePath = "XPlanePath"
}

@MainActor
final class AnalysisController: ObservableObject {
    @AppStorage(PrefKeys.xplanePath) var xplanePath: String = ""

    @Published var isRunning = false
    @Published var stageLabel = ""
    @Published var report: AnalysisReport?
    /// Bumped when a fresh report lands; views observe it to open the window.
    @Published var reportGeneration = 0
    @Published var errorMessage: String?

    // Map: the scanned installation (packs with tiles/airports/status) and
    // the user's tile selection.
    @Published var installationPacks: [SceneryPack] = []
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
    /// False until the first scan of the current install completes — the map
    /// window shows a loading cover instead of a half-laid-out split view.
    @Published var hasScannedInstallation = false
    /// (probed, total) while the installation scan runs — drives the
    /// determinate loading bar. nil outside a scan.
    @Published var scanProgress: (done: Int, total: Int)?
    /// (checked, total) while the unused-resource cross-check sweeps every
    /// pack. nil outside that stage.
    @Published var unusedVerifyProgress: (done: Int, total: Int)?
    @Published var selectedTiles: Set<String> = [] {
        didSet {
            priorityBox.update(Set(packsAffectingSelection().map { $0.name }))
        }
    }

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
            let (packs, overlays) = await Task.detached(priority: .userInitiated) {
                let packs = InstallationScanner(root: root).scan { done, total in
                    Task { @MainActor [weak self] in
                        self?.scanProgress = (done, total)
                    }
                }.packs
                return (packs, MapOverlays(packs: packs))
            }.value
            guard let self else { return }
            self.installationPacks = packs
            // Exact marks from the last report survive the rescan until the
            // auto-run refreshes them.
            self.mapOverlays = overlays.applyingExactMarkers(self.report?.packMarkers ?? [:])
            self.isScanningInstallation = false
            self.scanProgress = nil
            self.hasScannedInstallation = true
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

    /// Packs the current tile selection touches (by DSF tile or airport position).
    func packsAffectingSelection() -> [SceneryPack] {
        let tiles = selectedTiles
        guard !tiles.isEmpty else { return [] }
        return installationPacks.filter { pack in
            guard !pack.isLaminar else { return false }
            if !pack.tiles.isDisjoint(with: tiles) { return true }
            return pack.airports.values.contains { info in
                tiles.contains(TileMath.key(latitude: info.latitude, longitude: info.longitude))
            }
        }
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
        stageLabel = "Starting…"
        errorMessage = nil
        report = AnalysisReport(xplaneRoot: root.path, findings: [], stats: AnalysisStats())
        reportGeneration += 1

        // Manual scoped runs bypass the cache for the selection (the user is
        // asking "check this again"); packs our own fixes touched are always
        // recomputed. Everything else rides the signature cache.
        var options = Analyzer.Options(scope: scope, cacheURL: Self.cacheFileURL)
        options.forceFresh = pendingInvalidation
        if let scope { options.forceFresh.formUnion(scope) }
        pendingInvalidation = []
        let priorityBox = self.priorityBox

        // Full/auto runs stay off the performance cores (.utility) so the
        // machine remains usable while they grind; only a manual scoped run
        // — where the user is actively waiting — gets .userInitiated.
        // concurrentPerform workers inherit the spawning thread's QoS.
        let taskPriority: TaskPriority = scope == nil ? .utility : .userInitiated
        let stream = AsyncStream<StreamMessage> { continuation in
            Task.detached(priority: taskPriority) {
                let final = Analyzer(root: root).run(
                    options: options,
                    priority: { priorityBox.current }
                ) { event in
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
                    self.stageLabel = stage.label
                    if case .verifyingUnused(let done, let total) = stage {
                        self.unusedVerifyProgress = (done, total)
                    } else {
                        self.unusedVerifyProgress = nil
                    }
                    self.flushPending(&pending)
                    lastFlush = .now
                case .event(.findings(let new)):
                    pending.append(contentsOf: new)
                    if ContinuousClock.now - lastFlush > .milliseconds(400) {
                        self.flushPending(&pending)
                        lastFlush = .now
                    }
                case .event(.duplicateGroups(let groups)):
                    self.report?.duplicateGroups = groups
                case .event(.unusedResources(let groups)):
                    self.report?.unusedResources.append(contentsOf: groups)
                case .completed(let final):
                    // The final report supersedes everything streamed.
                    pending = []
                    self.report = final
                    self.isRunning = false
                    self.unusedVerifyProgress = nil
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
        current.findings.append(contentsOf: pending)
        current.findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        report = current
        pending = []
    }

    // MARK: - Pack actions

    func applyPackAction(_ action: PackAction, to packNames: [String]) {
        // Not while analyzing: the scan reads pack folders and the ini.
        guard let root = rootURL, !packNames.isEmpty, !isApplyingAction, !isRunning else { return }
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
    func reorderPacks(_ orderedNames: [String]) {
        guard let root = rootURL, orderedNames.count > 1, !isApplyingAction, !isRunning else { return }
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

    func applyFixes(to findings: [Finding]) {
        let fixable = findings.filter { $0.proposedFix != nil }
        guard !fixable.isEmpty, !isFixing, !isRunning else { return }
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
    func trashUnusedFiles(_ paths: [String]) {
        guard !paths.isEmpty, !isFixing, !isRunning else { return }
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

    func revertModifications(_ records: [ModificationRecord]) {
        guard !records.isEmpty, !isFixing, !isRunning else { return }
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
