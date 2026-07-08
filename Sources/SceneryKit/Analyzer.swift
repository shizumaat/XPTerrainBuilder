import Foundation
import os

let analyzerLog = Logger(subsystem: "com.novemberlima.XPSceneryDoctor", category: "analyzer")

/// Top-level entry point: scan the installation, run every analyzer, and
/// assemble the report. Pure and synchronous — callers run it off the main
/// thread and observe progress via the callback.
public struct Analyzer {
    public let root: URL
    /// nil = derive thresholds from the actual machine at run time.
    public let config: HealthConfig?

    public init(root: URL, config: HealthConfig? = nil) {
        self.root = root
        self.config = config
    }

    public enum Stage: Sendable {
        case scanningInstallation(String?)
        case readingLog
        case checkingDuplicates
        case inspectingPack(name: String, done: Int, total: Int)
        case findingUnused(String?)
        case verifyingUnused(Int, Int)
        case done

        public var label: String {
            switch self {
            case .scanningInstallation(let detail):
                return detail.map { "Scanning Custom Scenery… (\($0))" } ?? "Scanning Custom Scenery…"
            case .readingLog: return "Reading Log.txt…"
            case .checkingDuplicates: return "Checking for redundant packages…"
            case .inspectingPack(let name, let done, let total):
                return "Inspecting \(name)… (\(done)/\(total))"
            case .findingUnused(let detail):
                return detail.map { "Auditing resources… (\($0))" } ?? "Auditing resources…"
            case .verifyingUnused(let done, let total):
                return "Verifying unused files against every package… (\(done)/\(total))"
            case .done: return "Done"
            }
        }
    }

    /// Emitted while an analysis runs so UIs can show results as they land.
    /// The final, sorted report is still the function's return value; streamed
    /// findings are exactly the ones it will contain.
    public enum Event: Sendable {
        case stage(Stage)
        case findings([Finding])
        case duplicateGroups([DuplicateGroup])
        case unusedResources([UnusedResourceGroup])
        /// EXACT on-disk size per pack, as each completes (cached or fresh).
        case packSizes([String: Int64])
    }

    public struct Options: Sendable {
        /// Restrict REPORTED per-pack findings to these packs (the map's
        /// tile selection); nil = whole install.
        public var scope: Set<String>? = nil
        /// Recompute these packs even when their cache entry is valid —
        /// manual Analyze Selection and post-fix invalidation.
        public var forceFresh: Set<String> = []
        /// Persisted per-pack cache location; nil disables caching.
        public var cacheURL: URL? = nil
        /// How often completed per-pack entries are flushed to cacheURL
        /// DURING a run, so a quit or crash mid-run costs at most this much
        /// work instead of the whole cold pass (~25-30 min on the reference
        /// install). Zero = flush after every pack (tests).
        public var cacheFlushInterval: Duration = .seconds(60)
        /// A scan the caller already performed (the app scans for the map
        /// right before analyzing) — skips the analyzer's own multi-minute
        /// rescan of the same 4,200 packs. Signatures are as fresh as that
        /// scan; the app always analyzes right after scanning.
        public var preScanned: Installation? = nil

        public init(scope: Set<String>? = nil, forceFresh: Set<String> = [], cacheURL: URL? = nil) {
            self.scope = scope
            self.forceFresh = forceFresh
            self.cacheURL = cacheURL
        }
    }

    /// Compatibility wrapper: uncached run (CLI default, tests).
    public func run(
        scope: Set<String>? = nil,
        onEvent: @escaping @Sendable (Event) -> Void = { _ in }
    ) -> AnalysisReport {
        run(options: Options(scope: scope), onEvent: onEvent)
    }

    /// Runs the analysis. The installation scan always covers everything —
    /// library indexes must be complete regardless of scope. With a cacheURL,
    /// per-pack work is reused when the pack's content signature is unchanged
    /// since the cached run, so post-initial runs only pay for what changed.
    /// `priority` is re-read as workers pull packs, so selecting tiles mid-
    /// run moves those packs to the front. `onEvent` may be called from any
    /// thread and must be thread-safe.
    public func run(
        options: Options,
        priority: (@Sendable () -> Set<String>)? = nil,
        onEvent: @escaping @Sendable (Event) -> Void = { _ in }
    ) -> AnalysisReport {
        let scope = options.scope
        var findings: [Finding] = []
        var stats = AnalysisStats()
        let system = SystemInfo.current()
        let config = self.config ?? HealthConfig.forSystem(system)

        func emit(_ new: [Finding]) {
            guard !new.isEmpty else { return }
            findings.append(contentsOf: new)
            onEvent(.findings(new))
        }

        // Read the log before the scan opens thousands of directories, so log
        // access can't be starved of file descriptors by the enumeration.
        let logRead = TextFile.read(root.appendingPathComponent("Log.txt"))

        let fullInstallation: Installation
        if let preScanned = options.preScanned {
            fullInstallation = preScanned
        } else {
            onEvent(.stage(.scanningInstallation(nil)))
            fullInstallation = InstallationScanner(root: root).scan { done, total in
                onEvent(.stage(.scanningInstallation("\(done)/\(total) packs")))
            }
        }
        // Scoped runs analyze only the selected packs, but against the full
        // library indexes (missing-resource resolution needs everything).
        let installation: Installation
        if let scope {
            installation = Installation(
                root: fullInstallation.root,
                packs: fullInstallation.packs.filter { scope.contains($0.name) },
                libraryIndex: fullInstallation.libraryIndex,
                defaultLibraryIndex: fullInstallation.defaultLibraryIndex
            )
        } else {
            installation = fullInstallation
        }
        stats.packsScanned = installation.packs.count
        stats.libraryPacks = installation.packs.filter { $0.isLibrary }.count
        stats.airportsIndexed = installation.packs.reduce(0) { $0 + $1.airports.count }

        if installation.packs.isEmpty {
            emit([Finding(
                checkID: "INST-01",
                severity: .warning,
                category: .installation,
                title: "No scenery packs found",
                detail: "No folders were found in \(installation.customSceneryURL.path). Check that the selected folder is an X-Plane installation root.",
                path: installation.customSceneryURL.path
            )])
        }

        // INST-02: folders in Custom Scenery that aren't scenery at all —
        // WED project folders, empty dirs, symlinks to unmounted volumes.
        // X-Plane lists them in the ini and scans them at every launch; we
        // keep them OFF the map (no location) and report them here instead.
        let junkFolders = installation.packs.filter {
            $0.isInstalled && !$0.isLibrary && !$0.isLaminar && !$0.hasPlugins
                && $0.tiles.isEmpty && $0.airports.isEmpty
        }
        if !junkFolders.isEmpty {
            let fm = FileManager.default
            func reason(for pack: SceneryPack) -> String {
                if pack.resolvedURL != nil, !fm.fileExists(atPath: pack.contentRoot.path) {
                    return "symlink to a missing target (unmounted volume?)"
                }
                if fm.fileExists(atPath: pack.contentRoot.appendingPathComponent("earth.wed.xml").path) {
                    return "WED project folder (no compiled scenery)"
                }
                if pack.sizeBytes == 0 { return "empty folder" }
                return "no DSF tiles, airports, library or plugins"
            }
            let lines = junkFolders.sorted { $0.name < $1.name }
                .map { "\($0.name) — \(reason(for: $0))" }
                .joined(separator: "\n")
            emit([Finding(
                checkID: "INST-02",
                severity: .info,
                category: .installation,
                title: "\(junkFolders.count) folder\(junkFolders.count == 1 ? "" : "s") in Custom Scenery \(junkFolders.count == 1 ? "isn't" : "aren't") scenery",
                detail: "X-Plane loads nothing from these, but still lists and scans them at every launch:\n\(lines)",
                suggestion: "Move WED projects and stray folders out of Custom Scenery (or trash empty ones); re-mount the volume for broken symlinks. They are deliberately not shown on the map — no scenery, no location.",
                fixability: .assisted,
                relatedPacks: junkFolders.sorted { $0.name < $1.name }
                    .map { Finding.RelatedPack(name: $0.name, path: $0.url.path) }
            )])
        }

        onEvent(.stage(.readingLog))
        let (allLogFindings, lines) = LogAnalyzer(installation: fullInstallation).analyze(logRead: logRead)
        // Scoped runs only surface log findings attributed to selected packs.
        let logFindings = scope.map { s in
            allLogFindings.filter { $0.packName.map(s.contains) ?? false }
        } ?? allLogFindings
        emit(logFindings)
        stats.logLinesScanned = lines

        onEvent(.stage(.checkingDuplicates))
        let (dupFindings, duplicateGroups) = DuplicateAnalyzer(installation: installation).analyze()
        emit(dupFindings)
        onEvent(.duplicateGroups(duplicateGroups))

        // --- Unified per-pack pipeline (cache- and priority-aware) --------
        // Health checks, the resource audit and escape-reference collection
        // run together per pack, so one signature-valid cache entry replaces
        // every expensive read of that pack.
        var cache = options.cacheURL.map { AnalysisCache.load(from: $0) } ?? AnalysisCache()
        let health = PackageHealthAnalyzer(installation: installation, config: config)
        let audit = ResourceAuditAnalyzer(installation: installation)
        let placement = PlacementAnalyzer(installation: installation)
        let targets = installation.packs.filter { !$0.isLaminar && $0.isInstalled }

        struct PipelineState {
            var entries: [String: PackCacheEntry] = [:]
            var fromCache = 0
            var completed = 0
        }
        let state = LockedBox(PipelineState())
        let cacheSnapshot = cache
        let force = options.forceFresh

        // Crash-resilient caching: flush completed entries periodically so a
        // quit or kill mid-run loses at most one interval of work — without
        // this, the whole 25-30 min cold pass evaporates at pack 4000/4200.
        // Mid-run flushes skip the stale-entry pruning (the final save does
        // it); an interrupted run leaving a few dead entries is harmless.
        let lastCacheFlush = LockedBox(ContinuousClock.now)
        let flushInterval = options.cacheFlushInterval
        // The entries snapshot is LAZY — taken only when a flush is actually
        // due. Snapshotting per completion cloned the ever-growing entries
        // dictionary (every finding + escape-ref list) inside the shared
        // lock: quadratic copy-on-write churn that serialized all workers
        // and froze the pipeline at a pack a minute (profiled: one core in
        // BridgeObjectBox copy/destroy, everyone else in ulock_wait).
        let flushCacheIfDue: @Sendable (() -> [String: PackCacheEntry]) -> Void = { snapshotEntries in
            guard let cacheURL = options.cacheURL else { return }
            let due = lastCacheFlush.withLock { last -> Bool in
                let now = ContinuousClock.now
                guard now - last >= flushInterval else { return false }
                last = now
                return true
            }
            guard due else { return }
            var snapshot = cacheSnapshot
            for (name, entry) in snapshotEntries() { snapshot.entries[name] = entry }
            snapshot.save(to: cacheURL) // atomic write
        }

        analyzerLog.notice("pipeline start: \(targets.count) targets, \(cache.entries.count) cache entries, preScanned=\(options.preScanned != nil)")
        forEachPackPrioritized(targets, priority: priority) { i in
            let pack = targets[i]
            var entry: PackCacheEntry
            var reused = false
            if !force.contains(pack.name), let cached = cacheSnapshot.fullEntry(for: pack) {
                entry = cached
                reused = true
                if entry.diskSizeBytes == nil {
                    // Backfill for entries from before exact sizes existed —
                    // a metadata-only walk, no schema bump needed.
                    entry.diskSizeBytes = DiskUsage.sizeOfDirectory(at: pack.contentRoot)
                }
            } else {
                if let stale = cacheSnapshot.entries[pack.name], stale.hasFullAnalysis {
                    analyzerLog.notice("cache MISS (signature) for \(pack.name, privacy: .public): entry \(stale.signature, privacy: .public) vs pack \(pack.signature, privacy: .public)")
                } else if cacheSnapshot.entries[pack.name] == nil {
                    analyzerLog.info("cache MISS (absent) for \(pack.name, privacy: .public)")
                }
                let freshStart = ContinuousClock.now
                let healthResult = autoreleasepool { health.scanPack(pack) }
                let auditResult = autoreleasepool { audit.scanPack(pack) }
                var placementResult = autoreleasepool { placement.scanPack(pack) }
                placementResult.findings.append(
                    contentsOf: autoreleasepool { AptDatAnalyzer.scanPack(pack) })
                let escapes = ResourceAuditAnalyzer.collectEscapeRefs(in: pack)
                let elapsed = ContinuousClock.now - freshStart
                if elapsed > .seconds(15) {
                    analyzerLog.notice("slow pack \(pack.name, privacy: .public): \(elapsed.components.seconds)s")
                }
                // The placement-count C-09 (placed N× and can't instance)
                // supersedes the health scan's size-based C-09 for the same
                // OBJ — one problem, one row.
                let placementC09Paths = Set(placementResult.findings
                    .filter { $0.checkID == "C-09" }.compactMap { $0.path })
                let healthFindings = placementC09Paths.isEmpty
                    ? healthResult.findings
                    : healthResult.findings.filter {
                        !($0.checkID == "C-09" && placementC09Paths.contains($0.path ?? ""))
                    }
                entry = PackCacheEntry(
                    signature: pack.signature,
                    hasFullAnalysis: true,
                    healthFindings: healthFindings,
                    auditFindings: auditResult?.0 ?? [],
                    placementFindings: placementResult.findings,
                    unusedCandidates: auditResult?.1,
                    escapeRefs: escapes,
                    vramBytes: healthResult.vramEstimateBytes,
                    objFilesParsed: healthResult.objFilesParsed,
                    texturesInspected: healthResult.texturesInspected,
                    markerLon: placementResult.marker?.lon,
                    markerLat: placementResult.marker?.lat,
                    diskSizeBytes: healthResult.diskSizeBytes
                )
            }
            let done = state.withLock { s -> Int in
                s.entries[pack.name] = entry
                if reused { s.fromCache += 1 }
                s.completed += 1
                return s.completed
            }
            if done % 500 == 0 || done == targets.count {
                let hits = state.withLock { $0.fromCache }
                analyzerLog.notice("pipeline \(done)/\(targets.count), \(hits) from cache, latest \(pack.name, privacy: .public)")
            }
            onEvent(.stage(.inspectingPack(name: pack.name, done: done, total: targets.count)))
            let packFindings = entry.healthFindings + entry.auditFindings + entry.placementFindings
            if !packFindings.isEmpty { onEvent(.findings(packFindings)) }
            if let diskSize = entry.diskSizeBytes {
                onEvent(.packSizes([pack.name: diskSize]))
            }
            flushCacheIfDue { state.withLock { $0.entries } }
        }

        var newEntries = state.withLock { $0.entries }
        var packVRAM: [String: Int64] = [:]
        var candidateGroups: [UnusedResourceGroup] = []
        var packMarkers: [String: GeoPoint] = [:]
        var packSizes: [String: Int64] = [:]
        for pack in targets {
            guard let entry = newEntries[pack.name] else { continue }
            findings.append(contentsOf: entry.healthFindings + entry.auditFindings
                            + entry.placementFindings)
            stats.objFilesParsed += entry.objFilesParsed
            stats.texturesInspected += entry.texturesInspected
            if !pack.isLibrary { packVRAM[pack.name] = entry.vramBytes }
            if let candidates = entry.unusedCandidates { candidateGroups.append(candidates) }
            if let lon = entry.markerLon, let lat = entry.markerLat {
                packMarkers[pack.name] = GeoPoint(lon: lon, lat: lat)
            }
            if let diskSize = entry.diskSizeBytes { packSizes[pack.name] = diskSize }
        }
        stats.packsFromCache = state.withLock { $0.fromCache }

        // PERF-02: packs that load together in the same tile region. A pack's
        // textures are attributed evenly across its tiles (an ortho region
        // isn't all resident over one tile), airports usually carry full
        // weight on their single tile.
        let tileFindings = Self.tileCoLoadFindings(
            packs: installation.packs,
            packVRAM: packVRAM,
            config: config
        )
        findings.append(contentsOf: tileFindings)
        onEvent(.findings(tileFindings))

        // Deletion-grade cross-check: candidates survive only if no pack in
        // the whole install (scope notwithstanding) references them from
        // outside. Escape refs from the analyzed packs came out of the
        // pipeline above; the remaining packs (out of scope, Laminar,
        // uninstalled) are swept here, cache-aware, so repeat runs skip the
        // multi-minute read.
        var unusedGroups: [UnusedResourceGroup] = []
        if !candidateGroups.isEmpty {
            var externalRefs: [String] = []
            for entry in newEntries.values { externalRefs.append(contentsOf: entry.escapeRefs) }

            let others = fullInstallation.packs.filter { newEntries[$0.name] == nil }
            let pipelineEntries = newEntries // immutable snapshot for the flusher
            onEvent(.stage(.verifyingUnused(0, others.count)))
            struct SweepState {
                var refs: [String] = []
                var entries: [String: PackCacheEntry] = [:]
                var done = 0
            }
            let sweep = LockedBox(SweepState())
            forEachPackPrioritized(others, priority: nil) { i in
                let pack = others[i]
                let entry: PackCacheEntry
                if let cached = cacheSnapshot.anyEntry(for: pack) {
                    entry = cached
                } else {
                    entry = PackCacheEntry(signature: pack.signature,
                                           escapeRefs: ResourceAuditAnalyzer.collectEscapeRefs(in: pack))
                }
                let done = sweep.withLock { s -> Int in
                    s.refs.append(contentsOf: entry.escapeRefs)
                    s.entries[pack.name] = entry
                    s.done += 1
                    return s.done
                }
                if done % 25 == 0 || done == others.count {
                    onEvent(.stage(.verifyingUnused(done, others.count)))
                }
                // The sweep reads every remaining pack — minutes on a cold
                // install — so its entries ride the same periodic flush.
                flushCacheIfDue {
                    pipelineEntries.merging(
                        sweep.withLock { $0.entries }, uniquingKeysWith: { _, new in new })
                }
            }
            let sweepResult = sweep.withLock { $0 }
            externalRefs.append(contentsOf: sweepResult.refs)
            for (name, entry) in sweepResult.entries { newEntries[name] = entry }

            unusedGroups = ResourceAuditAnalyzer.verifyUnused(
                candidates: candidateGroups, externalRefs: externalRefs)
            unusedGroups.sort { $0.totalBytes > $1.totalBytes }
            // NOT uniqueKeysWithValues: a same-named pack can exist in both
            // Custom Scenery and the disabled folder simultaneously.
            let kinds = Dictionary(installation.packs.map { ($0.name, $0.kind) },
                                   uniquingKeysWith: { first, _ in first })
            let unusedFindings = unusedGroups.map {
                ResourceAuditAnalyzer.unusedFinding(for: $0, packKind: kinds[$0.packName])
            }
            emit(unusedFindings)
            onEvent(.unusedResources(unusedGroups))
        }

        // Persist the cache: fresh entries win; entries for packs that no
        // longer exist are pruned.
        if let cacheURL = options.cacheURL {
            let currentNames = Set(fullInstallation.packs.map { $0.name })
            cache.entries = cache.entries.filter { currentNames.contains($0.key) }
            for (name, entry) in newEntries { cache.entries[name] = entry }
            cache.save(to: cacheURL)
        }

        onEvent(.stage(.done))
        findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        var report = AnalysisReport(
            xplaneRoot: root.path,
            findings: findings,
            stats: stats,
            duplicateGroups: duplicateGroups,
            unusedResources: unusedGroups,
            system: system,
            scopeDescription: scope.map { "\($0.count) selected package\($0.count == 1 ? "" : "s")" }
        )
        report.packMarkers = packMarkers.isEmpty ? nil : packMarkers
        report.packSizes = packSizes.isEmpty ? nil : packSizes
        return report
    }

    /// Regions where what X-Plane ACTUALLY loads together exceeds the VRAM
    /// budget. Scenery is winner-plus-overlays per tile: exactly ONE base
    /// mesh/ortho loads (the highest-priority in scenery_packs.ini — lower
    /// ones are shadowed and cost nothing), then airports, landmarks and
    /// overlay DSFs merge on top. Summing every pack covering a tile
    /// double-counted shadowed orthos (a whole-state photo base under
    /// detailed local tiles false-alarmed constantly).
    static func tileCoLoadFindings(
        packs: [SceneryPack],
        packVRAM: [String: Int64],
        config: HealthConfig
    ) -> [Finding] {
        struct Load { let name: String; let share: Int64; let isBase: Bool; let rank: Int }
        var tileLoads: [String: [Load]] = [:]
        for pack in packs where !pack.isLaminar && !pack.isLibrary && pack.isEnabled {
            guard let vram = packVRAM[pack.name], vram > 0, !pack.tiles.isEmpty else { continue }
            let share = vram / Int64(pack.tiles.count)
            // Base mesh = sim/overlay 0 (sampled), with kind as the fallback
            // when no DSF could be read.
            let isBase = pack.isOverlay == false
                || (pack.isOverlay == nil && (pack.kind == .ortho || pack.kind == .mesh))
            for tile in pack.tiles {
                tileLoads[tile, default: []].append(
                    Load(name: pack.name, share: share, isBase: isBase,
                         rank: pack.iniIndex ?? Int.max))
            }
        }

        var candidates: [(tile: String, loads: [Load], total: Int64, shadowed: Int)] = []
        for (tile, loads) in tileLoads {
            let bases = loads.filter { $0.isBase }
            let winner = bases.min { $0.rank < $1.rank }
            let overlays = loads.filter { !$0.isBase }
            let resident = (winner.map { [$0] } ?? []) + overlays
            guard resident.count >= 2 else { continue }
            let total = resident.reduce(0) { $0 + $1.share }
            if total >= config.tileVRAMWarnBytes {
                candidates.append((tile, resident.sorted { $0.share > $1.share },
                                   total, bases.count - (winner == nil ? 0 : 1)))
            }
        }

        var findings: [Finding] = []
        var seenPackSets = Set<Set<String>>()
        for candidate in candidates.sorted(by: { $0.total > $1.total }) {
            let packSet = Set(candidate.loads.map { $0.name })
            guard seenPackSets.insert(packSet).inserted else { continue }
            guard findings.count < 5 else { break }

            let totalStr = ByteCountFormatter.string(fromByteCount: candidate.total, countStyle: .memory)
            let budgetStr = ByteCountFormatter.string(fromByteCount: config.vramBudgetBytes, countStyle: .memory)
            let list = candidate.loads.prefix(6)
                .map { "'\($0.name)' (~\(ByteCountFormatter.string(fromByteCount: $0.share, countStyle: .memory)))" }
                .joined(separator: ", ")
            let shadowedClause = candidate.shadowed > 0
                ? " (\(candidate.shadowed) lower-priority base pack\(candidate.shadowed == 1 ? "" : "s") covering this tile never load\(candidate.shadowed == 1 ? "s" : "") and \(candidate.shadowed == 1 ? "is" : "are") not counted)"
                : ""
            findings.append(Finding(
                checkID: "PERF-02",
                severity: .warning,
                category: .performance,
                title: "Tile \(candidate.tile): resident textures ~\(totalStr)",
                detail: "What X-Plane actually loads over tile \(candidate.tile) — the winning base scenery plus every overlay that merges on top — estimates ~\(totalStr) of textures against this Mac's ~\(budgetStr) usable VRAM: \(list)\(shadowedClause). Flying here can push past VRAM even though each pack looks fine alone.",
                suggestion: "Disable the overlays you don't need in this region, or reduce texture quality when flying here.",
                fixability: .assisted
            ))
        }
        return findings
    }

    /// Cheap re-scan of just the duplicate state, for refreshing the report
    /// after the user disables/moves/trashes packs (a full run re-parses
    /// hundreds of thousands of files; this only re-reads pack metadata).
    public func refreshDuplicates() -> (findings: [Finding], groups: [DuplicateGroup]) {
        let installation = InstallationScanner(root: root).scan()
        return DuplicateAnalyzer(installation: installation).analyze()
    }
}
