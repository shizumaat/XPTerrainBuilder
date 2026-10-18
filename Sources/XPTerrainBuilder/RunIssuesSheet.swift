import SwiftUI
import AppKit
import SceneryKit

/// The finished run's ONE report (issue #562; owner RULINGS 2026-10-12a,
/// #564): each tile that was not built, or was built without an airport
/// patch, in the engine's own three sentences — what failed, why, what to
/// do. The technical detail sits behind a disclosure.
///
/// Each tile carries the two report buttons (#565): "Report this problem"
/// shows the engine's REDACTED report for the user to read, then copies it
/// and opens the prefilled GitHub issue; "Save report file" writes it
/// where the user chooses. Nothing leaves the machine without that press.
struct RunIssuesSheet: View {
    let issues: O4RunIssues
    @ObservedObject var buildModel: BuildModel
    let dismiss: () -> Void
    @State private var showDetail = false
    @State private var preview: O4FailureReport?
    @State private var note: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(issues.title, systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .symbolRenderingMode(.multicolor)
            if let preview {
                reportPreview(preview)
            } else {
                issueList
            }
            if let note { Text(note).font(.caption).foregroundStyle(.secondary) }
            HStack {
                Spacer()
                if !buildModel.retryTiles.isEmpty {
                    Button("Build failed tiles again") {
                        buildModel.buildFailedTilesAgain()
                        dismiss()
                    }
                    .disabled(buildModel.isBuilding)
                }
                Button("OK", action: dismiss).keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 580)
    }

    private var issueList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(issues.tiles.enumerated()), id: \.offset) { _, tile in
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(tile.entries.enumerated()), id: \.offset) { _, entry in
                            VStack(alignment: .leading, spacing: 2) {
                                // #853: the same label the Qt box gives it
                                Text(entry.severityLabel.uppercased())
                                    .font(.caption2).fontWeight(.semibold)
                                    .foregroundStyle(entry.severity == "blocking"
                                                     ? Color.red : Color.secondary)
                                Text(entry.what).fontWeight(.semibold)
                                Text(entry.why)
                                Text(entry.remedy)
                            }
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        if tile.requeued {
                            // #695: fixed while the run went on.
                            Label(O4TileFailureCopy.requeuedLine, systemImage: "arrow.clockwise")
                                .foregroundStyle(.secondary)
                        }
                        if let link = tile.removableLink {
                            linkButtons(tile, link: link)
                        }
                        if buildModel.canReportFailures {
                            HStack {
                                Button(O4TileFailureCopy.reportButton) { report(tile) }
                                Button(O4TileFailureCopy.saveReportButton) { save(tile) }
                            }
                        }
                    }
                }
                DisclosureGroup("Technical details", isExpanded: $showDetail) {
                    Text(detailText)
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .frame(maxHeight: 380)
    }

    /// The tile's folder is a link to a drive that is not mounted (#668):
    /// remove the link and build here, or leave it.
    private func linkButtons(_ tile: O4TileIssues, link: String) -> some View {
        HStack {
            Button(O4TileFailureCopy.removeLinkButton) {
                buildModel.removeLinkAndRebuild(tile, link: link) { refusal in
                    if let refusal {
                        note = O4TileFailureCopy.removeLinkFailed(refusal)
                    } else {
                        dismiss()
                    }
                }
            }
            Button(O4TileFailureCopy.removeLinkCancel, action: dismiss)
        }
    }

    private func reportPreview(_ report: O4FailureReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(O4TileFailureCopy.reportPreviewTitle).fontWeight(.semibold)
            Text(O4TileFailureCopy.reportPreviewNote).font(.caption)
            ScrollView {
                Text(report.report)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: 300)
            HStack {
                Button(O4TileFailureCopy.openIssueButton) {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(report.report, forType: .string)
                    if let url = URL(string: report.issueURL) { NSWorkspace.shared.open(url) }
                    preview = nil
                    note = "The report is on the clipboard."
                }
                Button("Back") { preview = nil }
            }
        }
    }

    private func report(_ tile: O4TileIssues) {
        buildModel.failureReport(for: tile) { result in
            if let result {
                preview = result
            } else {
                note = unavailable
            }
        }
    }

    private func save(_ tile: O4TileIssues) {
        // First ask for the report's own file name, then for the place.
        buildModel.failureReport(for: tile) { result in
            guard let result else { note = unavailable; return }
            let panel = NSSavePanel()
            panel.nameFieldStringValue = result.fileName
            guard panel.runModal() == .OK, let url = panel.url else { return }
            buildModel.failureReport(for: tile, savePath: url.path) { saved in
                note = (saved?.savedPath.isEmpty == false)
                    ? "Report saved to \(saved!.savedPath)." : unavailable
            }
        }
    }

    private var unavailable: String {
        "The report could not be made. The log is at "
            + EngineStderrLog.shared.fileURL.path + "."
    }

    private var detailText: String {
        var parts = [issues.detail].filter { !$0.isEmpty }
        parts.append("Log: " + EngineStderrLog.shared.fileURL.path)
        return parts.joined(separator: "\n\n")
    }
}
