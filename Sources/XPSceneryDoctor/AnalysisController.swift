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

    // Pack actions (duplicates view)
    @Published var isApplyingAction = false
    @Published var actionErrors: [PackActionOutcome] = []

    var rootURL: URL? {
        guard !xplanePath.isEmpty else { return nil }
        return URL(fileURLWithPath: xplanePath, isDirectory: true)
    }

    var pathIsValid: Bool {
        guard let url = rootURL else { return false }
        return Installation.looksLikeXPlaneRoot(url)
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
    func analyze() {
        guard let root = rootURL, !isRunning else { return }
        isRunning = true
        stageLabel = "Starting…"
        errorMessage = nil
        report = AnalysisReport(xplaneRoot: root.path, findings: [], stats: AnalysisStats())
        reportGeneration += 1 // opens the report window right away

        let stream = AsyncStream<StreamMessage> { continuation in
            Task.detached(priority: .userInitiated) {
                let final = Analyzer(root: root).run { event in
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
                case .completed(let final):
                    // The final report supersedes everything streamed.
                    pending = []
                    self.report = final
                    self.isRunning = false
                }
            }
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
            self.isApplyingAction = false
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
