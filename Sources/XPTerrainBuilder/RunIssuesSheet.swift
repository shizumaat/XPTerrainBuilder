import SwiftUI
import AppKit
import SceneryKit

/// The finished run's ONE report (issue #562; owner RULINGS 2026-10-12a,
/// #564): each tile that was not built, or was built without an airport
/// patch, in the engine's own three sentences — what failed, why, what to
/// do. The technical detail and the log locations sit behind a disclosure.
struct RunIssuesSheet: View {
    let issues: O4RunIssues
    let dismiss: () -> Void
    @State private var showDetail = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(issues.title, systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .symbolRenderingMode(.multicolor)
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(Array(issues.entries.enumerated()), id: \.offset) { _, entry in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.what).fontWeight(.semibold)
                            Text(entry.why)
                            Text(entry.remedy)
                        }
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    DisclosureGroup("Technical details", isExpanded: $showDetail) {
                        Text(detailText)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            .frame(maxHeight: 360)
            HStack {
                Button("Copy Details") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(
                        issues.entries.map(\.message).joined(separator: "\n\n")
                            + "\n\n" + detailText,
                        forType: .string)
                }
                Button("Show Log in Finder") {
                    NSWorkspace.shared.activateFileViewerSelecting([EngineStderrLog.shared.fileURL])
                }
                Spacer()
                Button("OK", action: dismiss).keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 560)
    }

    private var detailText: String {
        var parts = [issues.detail].filter { !$0.isEmpty }
        parts.append("App log: " + EngineStderrLog.shared.fileURL.path)
        if let engineLog = issues.entries.map(\.logPath).first(where: { !$0.isEmpty }) {
            parts.append("Engine log: " + engineLog)
        }
        return parts.joined(separator: "\n\n")
    }
}
