import SwiftUI
import SceneryKit

enum SidebarItem: Hashable {
    case all
    case category(FindingCategory)

    var title: String {
        switch self {
        case .all: return "All Findings"
        case .category(let category): return category.rawValue
        }
    }

    var systemImage: String {
        switch self {
        case .all: return "list.bullet"
        case .category(.installation): return "internaldrive"
        case .category(.missingResource): return "questionmark.folder"
        case .category(.duplicatePackage): return "square.on.square"
        case .category(.packageHealth): return "stethoscope"
        case .category(.performance): return "gauge.with.needle"
        }
    }
}

/// The analysis report in a real, resizable window (BBEdit-search-results
/// style): category sidebar with counts, searchable findings list, and an
/// actionable table for redundant packages.
struct ReportWindow: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var sidebarSelection = ViewState<SidebarItem?>(.all)
    @StateObject private var searchText = ViewState("")
    @StateObject private var severityFilter = ViewState<Severity?>(nil)

    var body: some View {
        if let report = controller.report {
            NavigationSplitView {
                sidebar(for: report)
                    .navigationSplitViewColumnWidth(min: 200, ideal: 230)
            } detail: {
                detail(for: report)
            }
            .searchable(text: $searchText.value, placement: .toolbar, prompt: "Filter findings")
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    Picker("Severity", selection: $severityFilter.value) {
                        Text("All").tag(Severity?.none)
                        Text("Errors (\(report.errorCount))").tag(Severity?.some(.error))
                        Text("Warnings (\(report.warningCount))").tag(Severity?.some(.warning))
                        Text("Info (\(report.infoCount))").tag(Severity?.some(.info))
                    }
                    .pickerStyle(.segmented)
                    .help("Filter findings by severity")
                }
                ToolbarItem(placement: .automatic) {
                    Button {
                        controller.exportReportJSON()
                    } label: {
                        Label("Export…", systemImage: "square.and.arrow.up")
                    }
                    .help("Export the full report as JSON (⇧⌘E)")
                }
            }
            .navigationTitle("Analysis Report")
            .navigationSubtitle(subtitle(for: report))
            .alert("Some actions failed", isPresented: actionErrorsBinding) {
                Button("OK") { controller.actionErrors = [] }
            } message: {
                Text(controller.actionErrors
                    .map { "\($0.packName): \($0.message ?? "unknown error")" }
                    .joined(separator: "\n"))
            }
        } else {
            ContentUnavailableView(
                "No Analysis Yet",
                systemImage: "stethoscope",
                description: Text("Run Analyze from the main window (⌘R).")
            )
            .frame(minWidth: 480, minHeight: 320)
        }
    }

    private func subtitle(for report: AnalysisReport) -> String {
        let stats = report.stats
        return "\(report.xplaneRoot) — \(stats.packsScanned) packs, \(report.findings.count) findings"
    }

    private var actionErrorsBinding: Binding<Bool> {
        Binding(
            get: { !controller.actionErrors.isEmpty },
            set: { if !$0 { controller.actionErrors = [] } }
        )
    }

    // MARK: - Sidebar

    private func sidebar(for report: AnalysisReport) -> some View {
        List(selection: $sidebarSelection.value) {
            Label(SidebarItem.all.title, systemImage: SidebarItem.all.systemImage)
                .badge(filteredCount(report.findings))
                .tag(SidebarItem.all)

            Section("Categories") {
                ForEach(FindingCategory.allCases, id: \.self) { category in
                    let item = SidebarItem.category(category)
                    let count = filteredCount(report.findings.filter { $0.category == category })
                    Label(item.title, systemImage: item.systemImage)
                        .badge(count)
                        .tag(item)
                }
            }
        }
        .listStyle(.sidebar)
    }

    /// Count respecting the severity filter (not the search, which is cheap
    /// feedback the list itself gives).
    private func filteredCount(_ findings: [Finding]) -> Int {
        guard let severity = severityFilter.value else { return findings.count }
        return findings.filter { $0.severity == severity }.count
    }

    // MARK: - Detail

    @ViewBuilder
    private func detail(for report: AnalysisReport) -> some View {
        let selection = sidebarSelection.value ?? .all
        switch selection {
        case .category(.duplicatePackage):
            DuplicatesView(
                groups: report.duplicateGroups,
                otherFindings: visibleFindings(in: report).filter {
                    $0.category == .duplicatePackage && $0.checkID != "DUP-01"
                }
            )
        case .all:
            FindingsList(findings: visibleFindings(in: report), grouped: true)
        case .category(let category):
            FindingsList(
                findings: visibleFindings(in: report).filter { $0.category == category },
                grouped: false
            )
        }
    }

    private func visibleFindings(in report: AnalysisReport) -> [Finding] {
        var findings = report.findings
        if let severity = severityFilter.value {
            findings = findings.filter { $0.severity == severity }
        }
        let query = searchText.value.trimmingCharacters(in: .whitespaces)
        if !query.isEmpty {
            findings = findings.filter {
                $0.title.localizedCaseInsensitiveContains(query)
                    || $0.detail.localizedCaseInsensitiveContains(query)
                    || ($0.path?.localizedCaseInsensitiveContains(query) ?? false)
            }
        }
        return findings
    }
}

// MARK: - Findings list

struct FindingsList: View {
    let findings: [Finding]
    let grouped: Bool

    var body: some View {
        if findings.isEmpty {
            ContentUnavailableView(
                "No Findings",
                systemImage: "checkmark.seal",
                description: Text("Nothing matches the current filters.")
            )
        } else {
            List {
                if grouped {
                    ForEach(FindingCategory.allCases, id: \.self) { category in
                        let items = findings.filter { $0.category == category }
                        if !items.isEmpty {
                            Section("\(category.rawValue) (\(items.count))") {
                                ForEach(items) { FindingRow(finding: $0) }
                            }
                        }
                    }
                } else {
                    ForEach(findings) { FindingRow(finding: $0) }
                }
            }
            .listStyle(.inset)
        }
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
                SeverityIcon(severity: finding.severity)
                Text(finding.title)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
    }
}

struct SeverityIcon: View {
    let severity: Severity

    var body: some View {
        switch severity {
        case .error:
            Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        case .warning:
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
        case .info:
            Image(systemName: "info.circle.fill").foregroundStyle(.blue)
        }
    }
}
