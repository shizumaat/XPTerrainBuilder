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

    func analyze() {
        guard let root = rootURL, !isRunning else { return }
        isRunning = true
        stageLabel = "Starting…"
        errorMessage = nil

        let box = WeakBox(self)
        Task { [weak self] in
            let report = await Self.runAnalysis(root: root) { stage in
                let label = stage.label
                Task { @MainActor in
                    box.value?.stageLabel = label
                }
            }
            self?.report = report
            self?.isRunning = false
            self?.reportGeneration += 1
        }
    }

    /// Lets a @Sendable progress closure reach back to the MainActor
    /// controller without capturing a weak `self` var (a Swift 6 error).
    private final class WeakBox<T: AnyObject>: @unchecked Sendable {
        weak var value: T?
        init(_ value: T) { self.value = value }
    }

    nonisolated static func runAnalysis(
        root: URL,
        progress: @escaping @Sendable (Analyzer.Stage) -> Void
    ) async -> AnalysisReport {
        await Task.detached(priority: .userInitiated) {
            Analyzer(root: root).run(progress: progress)
        }.value
    }

    // MARK: - Pack actions

    func applyPackAction(_ action: PackAction, to packNames: [String]) {
        guard let root = rootURL, !packNames.isEmpty, !isApplyingAction else { return }
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
