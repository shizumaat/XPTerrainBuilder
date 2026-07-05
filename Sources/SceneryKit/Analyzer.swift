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
        case scanningInstallation
        case readingLog
        case checkingDuplicates
        case inspectingPack(String)
        case done

        public var label: String {
            switch self {
            case .scanningInstallation: return "Scanning Custom Scenery…"
            case .readingLog: return "Reading Log.txt…"
            case .checkingDuplicates: return "Checking for redundant packages…"
            case .inspectingPack(let name): return "Inspecting \(name)…"
            case .done: return "Done"
            }
        }
    }

    public func run(progress: @escaping @Sendable (Stage) -> Void = { _ in }) -> AnalysisReport {
        var findings: [Finding] = []
        var stats = AnalysisStats()

        progress(.scanningInstallation)
        let installation = InstallationScanner(root: root).scan()
        stats.packsScanned = installation.packs.count
        stats.libraryPacks = installation.packs.filter { $0.isLibrary }.count
        stats.airportsIndexed = installation.packs.reduce(0) { $0 + $1.airports.count }

        if installation.packs.isEmpty {
            findings.append(Finding(
                checkID: "INST-01",
                severity: .warning,
                category: .installation,
                title: "No scenery packs found",
                detail: "No folders were found in \(installation.customSceneryURL.path). Check that the selected folder is an X-Plane installation root.",
                path: installation.customSceneryURL.path
            ))
        }

        progress(.readingLog)
        let (logFindings, lines) = LogAnalyzer(installation: installation).analyze()
        findings.append(contentsOf: logFindings)
        stats.logLinesScanned = lines

        progress(.checkingDuplicates)
        findings.append(contentsOf: DuplicateAnalyzer(installation: installation).analyze())

        let health = PackageHealthAnalyzer(installation: installation, config: config)
        let healthResult = health.analyze { packName in
            progress(.inspectingPack(packName))
        }
        findings.append(contentsOf: healthResult.findings)
        stats.objFilesParsed = healthResult.objFilesParsed
        stats.texturesInspected = healthResult.texturesInspected

        progress(.done)
        findings.sort {
            ($0.severity, $0.category.rawValue, $0.title) < ($1.severity, $1.category.rawValue, $1.title)
        }
        return AnalysisReport(xplaneRoot: root.path, findings: findings, stats: stats)
    }
}
