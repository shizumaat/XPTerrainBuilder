import Foundation

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
        case inspectingPack(String)
        case findingUnused(String?)
        case done

        public var label: String {
            switch self {
            case .scanningInstallation(let detail):
                return detail.map { "Scanning Custom Scenery… (\($0))" } ?? "Scanning Custom Scenery…"
            case .readingLog: return "Reading Log.txt…"
            case .checkingDuplicates: return "Checking for redundant packages…"
            case .inspectingPack(let name): return "Inspecting \(name)…"
            case .findingUnused(let detail):
                return detail.map { "Auditing resources… (\($0))" } ?? "Auditing resources…"
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
    }

    /// Runs the analysis. `scope` restricts the deep per-pack stages to the
    /// named packs (the map's tile selection); nil = whole install. The
    /// installation scan always covers everything — library indexes must be
    /// complete regardless of scope. `onEvent` may be called from any thread
    /// (pack scans run in parallel) and must be thread-safe.
    public func run(
        scope: Set<String>? = nil,
        onEvent: @escaping @Sendable (Event) -> Void = { _ in }
    ) -> AnalysisReport {
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

        onEvent(.stage(.scanningInstallation(nil)))
        let fullInstallation = InstallationScanner(root: root).scan { detail in
            onEvent(.stage(.scanningInstallation(detail)))
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

        let health = PackageHealthAnalyzer(installation: installation, config: config)
        let healthResult = health.analyze(
            progress: { packName in
                onEvent(.stage(.inspectingPack(packName)))
            },
            onPackFindings: { packFindings in
                onEvent(.findings(packFindings))
            }
        )
        // Streamed above per pack; fold into the aggregate without re-emitting.
        findings.append(contentsOf: healthResult.findings)
        stats.objFilesParsed = healthResult.objFilesParsed
        stats.texturesInspected = healthResult.texturesInspected

        // PERF-02: packs that load together in the same tile region. A pack's
        // textures are attributed evenly across its tiles (an ortho region
        // isn't all resident over one tile), airports usually carry full
        // weight on their single tile.
        let tileFindings = Self.tileCoLoadFindings(
            packs: installation.packs,
            packVRAM: healthResult.packVRAM,
            config: config
        )
        findings.append(contentsOf: tileFindings)
        onEvent(.findings(tileFindings))

        onEvent(.stage(.findingUnused(nil)))
        let auditAnalyzer = ResourceAuditAnalyzer(installation: installation)
        let (auditFindings, unusedGroups) = auditAnalyzer.analyze(
            progress: { detail in
                onEvent(.stage(.findingUnused(detail)))
            },
            onPack: { packFindings, group in
                onEvent(.findings(packFindings))
                if let group { onEvent(.unusedResources([group])) }
            }
        )
        findings.append(contentsOf: auditFindings)

        onEvent(.stage(.done))
        findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        return AnalysisReport(
            xplaneRoot: root.path,
            findings: findings,
            stats: stats,
            duplicateGroups: duplicateGroups,
            unusedResources: unusedGroups,
            system: system,
            scopeDescription: scope.map { "\($0.count) selected package\($0.count == 1 ? "" : "s")" }
        )
    }

    /// Regions where several packs' textures together exceed the VRAM budget.
    static func tileCoLoadFindings(
        packs: [SceneryPack],
        packVRAM: [String: Int64],
        config: HealthConfig
    ) -> [Finding] {
        var tileLoads: [String: [(name: String, share: Int64)]] = [:]
        for pack in packs where !pack.isLaminar && !pack.isLibrary && pack.isEnabled {
            guard let vram = packVRAM[pack.name], vram > 0, !pack.tiles.isEmpty else { continue }
            let share = vram / Int64(pack.tiles.count)
            for tile in pack.tiles {
                tileLoads[tile, default: []].append((pack.name, share))
            }
        }

        var candidates: [(tile: String, packs: [(name: String, share: Int64)], total: Int64)] = []
        for (tile, loads) in tileLoads where loads.count >= 2 {
            let total = loads.reduce(0) { $0 + $1.share }
            if total >= config.tileVRAMWarnBytes {
                candidates.append((tile, loads.sorted { $0.share > $1.share }, total))
            }
        }

        var findings: [Finding] = []
        var seenPackSets = Set<Set<String>>()
        for candidate in candidates.sorted(by: { $0.total > $1.total }) {
            let packSet = Set(candidate.packs.map { $0.name })
            guard seenPackSets.insert(packSet).inserted else { continue }
            guard findings.count < 5 else { break }

            let totalStr = ByteCountFormatter.string(fromByteCount: candidate.total, countStyle: .memory)
            let budgetStr = ByteCountFormatter.string(fromByteCount: config.vramBudgetBytes, countStyle: .memory)
            let list = candidate.packs.prefix(6)
                .map { "'\($0.name)' (~\(ByteCountFormatter.string(fromByteCount: $0.share, countStyle: .memory)))" }
                .joined(separator: ", ")
            findings.append(Finding(
                checkID: "PERF-02",
                severity: .warning,
                category: .performance,
                title: "Tile \(candidate.tile): combined textures ~\(totalStr)",
                detail: "\(candidate.packs.count) enabled packs load together over tile \(candidate.tile), estimating ~\(totalStr) of textures against this Mac's ~\(budgetStr) usable VRAM: \(list). Flying here can push past VRAM even though each pack looks fine alone.",
                suggestion: "Disable the packs you don't need in this region, or reduce texture quality when flying here.",
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
