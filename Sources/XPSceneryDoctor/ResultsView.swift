import SwiftUI
import SceneryKit

struct ResultsView: View {
    let report: AnalysisReport
    @EnvironmentObject var controller: AnalysisController
    @Environment(\.dismiss) private var dismiss
    @StateObject private var severityFilter = ViewState<Severity?>(nil)

    private var filtered: [Finding] {
        guard let severity = severityFilter.value else { return report.findings }
        return report.findings.filter { $0.severity == severity }
    }

    private var grouped: [(FindingCategory, [Finding])] {
        FindingCategory.allCases.compactMap { category in
            let items = filtered.filter { $0.category == category }
            return items.isEmpty ? nil : (category, items)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            if filtered.isEmpty {
                emptyState
            } else {
                List {
                    ForEach(grouped, id: \.0) { category, findings in
                        Section(header: Text("\(category.rawValue) (\(findings.count))")) {
                            ForEach(findings) { finding in
                                FindingRow(finding: finding)
                            }
                        }
                    }
                }
                .listStyle(.inset)
            }
            Divider()
            footer
        }
        .frame(width: 640, height: 520)
    }

    private var header: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Analysis Report")
                    .font(.headline)
                Text("\(report.stats.packsScanned) packs · \(report.stats.objFilesParsed) objects · \(report.stats.texturesInspected) textures · \(report.stats.logLinesScanned) log lines")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Picker("", selection: $severityFilter.value) {
                Text("All (\(report.findings.count))").tag(Severity?.none)
                Text("Errors (\(report.errorCount))").tag(Severity?.some(.error))
                Text("Warnings (\(report.warningCount))").tag(Severity?.some(.warning))
                Text("Info (\(report.infoCount))").tag(Severity?.some(.info))
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .fixedSize()
        }
        .padding(12)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Spacer()
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 36))
                .foregroundStyle(.green)
            Text(report.findings.isEmpty ? "No issues found. Your scenery looks healthy!" : "No findings match this filter.")
                .foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var footer: some View {
        HStack {
            Button("Export JSON…") { controller.exportReportJSON() }
            Spacer()
            Button("Done") { dismiss() }
                .keyboardShortcut(.defaultAction)
        }
        .padding(12)
    }
}

struct FindingRow: View {
    let finding: Finding

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 6) {
                Text(finding.detail)
                    .font(.callout)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)

                if let suggestion = finding.suggestion {
                    Label {
                        Text(suggestion)
                            .font(.callout)
                            .textSelection(.enabled)
                            .fixedSize(horizontal: false, vertical: true)
                    } icon: {
                        Image(systemName: "lightbulb")
                            .foregroundStyle(.yellow)
                    }
                }

                HStack(spacing: 12) {
                    if let url = finding.url {
                        Link(destination: url) {
                            Label(url.host()?.contains("x-plane.org") == true ? "Find on x-plane.org" : "More info", systemImage: "safari")
                        }
                        .font(.caption)
                    }
                    if let path = finding.path {
                        Button {
                            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
                        } label: {
                            Label("Reveal in Finder", systemImage: "folder")
                        }
                        .buttonStyle(.link)
                        .font(.caption)
                    }
                    Spacer()
                    Text(finding.checkID)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.tertiary)
                }
            }
            .padding(.vertical, 4)
        } label: {
            HStack(spacing: 8) {
                severityIcon
                Text(finding.title)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
    }

    @ViewBuilder
    private var severityIcon: some View {
        switch finding.severity {
        case .error:
            Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        case .warning:
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
        case .info:
            Image(systemName: "info.circle.fill").foregroundStyle(.blue)
        }
    }
}
