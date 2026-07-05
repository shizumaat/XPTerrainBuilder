import Foundation

/// Top-level entry point: scan the installation, run every analyzer, and
/// assemble the report. Pure and synchronous — callers run it off the main
/// thread and observe progress via the callback.
public struct Analyzer {
    public let root: URL
    public let config: HealthConfig

    public init(root: URL, config: HealthConfig = HealthConfig()) {
        self.root = root
        self.config = config
    }

    public enum Stage: Sendable {
        case scanningInstallation(String?)
        case readingLog
        case checkingDuplicates
        case inspectingPack(String)
        case done

        public var label: String {
            switch self {
            case .scanningInstallation(let detail):
                return detail.map { "Scanning Custom Scenery… (\($0))" } ?? "Scanning Custom Scenery…"
            case .readingLog: return "Reading Log.txt…"
            case .checkingDuplicates: return "Checking for redundant packages…"
            case .inspectingPack(let name): return "Inspecting \(name)…"
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
    }

    /// Runs the full analysis. `onEvent` may be called from any thread
    /// (pack scans run in parallel) and must be thread-safe.
    public func run(onEvent: @escaping @Sendable (Event) -> Void = { _ in }) -> AnalysisReport {
        var findings: [Finding] = []
        var stats = AnalysisStats()

        func emit(_ new: [Finding]) {
            guard !new.isEmpty else { return }
            findings.append(contentsOf: new)
            onEvent(.findings(new))
        }

        // Read the log before the scan opens thousands of directories, so log
        // access can't be starved of file descriptors by the enumeration.
        let logRead = TextFile.read(root.appendingPathComponent("Log.txt"))

        onEvent(.stage(.scanningInstallation(nil)))
        let installation = InstallationScanner(root: root).scan { detail in
            onEvent(.stage(.scanningInstallation(detail)))
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
        let (logFindings, lines) = LogAnalyzer(installation: installation).analyze(logRead: logRead)
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

        onEvent(.stage(.done))
        findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        return AnalysisReport(
            xplaneRoot: root.path,
            findings: findings,
            stats: stats,
            duplicateGroups: duplicateGroups
        )
    }

    /// Cheap re-scan of just the duplicate state, for refreshing the report
    /// after the user disables/moves/trashes packs (a full run re-parses
    /// hundreds of thousands of files; this only re-reads pack metadata).
    public func refreshDuplicates() -> (findings: [Finding], groups: [DuplicateGroup]) {
        let installation = InstallationScanner(root: root).scan()
        return DuplicateAnalyzer(installation: installation).analyze()
    }
}
