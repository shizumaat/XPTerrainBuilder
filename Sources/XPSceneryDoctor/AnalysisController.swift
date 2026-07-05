import Foundation
import SwiftUI
import SceneryKit

/// UserDefaults key for the X-Plane root path. Lives in the app's standard
/// preferences plist (~/Library/Preferences/com.noahlieberman.XPSceneryDoctor.plist
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
    @Published var showingResults = false
    @Published var errorMessage: String?

    var rootURL: URL? {
        guard !xplanePath.isEmpty else { return nil }
        return URL(fileURLWithPath: xplanePath, isDirectory: true)
    }

    var pathIsValid: Bool {
        guard let url = rootURL else { return false }
        return Installation.looksLikeXPlaneRoot(url)
    }

    func analyze() {
        guard let root = rootURL, !isRunning else { return }
        isRunning = true
        stageLabel = "Starting…"
        errorMessage = nil

        Task { [weak self] in
            let report = await Self.runAnalysis(root: root) { stage in
                Task { @MainActor [weak self] in
                    self?.stageLabel = stage.label
                }
            }
            self?.report = report
            self?.isRunning = false
            self?.showingResults = true
        }
    }

    nonisolated static func runAnalysis(
        root: URL,
        progress: @escaping @Sendable (Analyzer.Stage) -> Void
    ) async -> AnalysisReport {
        await Task.detached(priority: .userInitiated) {
            Analyzer(root: root).run(progress: progress)
        }.value
    }

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
