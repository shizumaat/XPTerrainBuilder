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
        case .category(.unusedResources): return "archivebox"
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
    @StateObject private var fixableOnly = ViewState(false)

    var body: some View {
        if let report = controller.report {
            NavigationSplitView {
                sidebar(for: report)
                    .navigationSplitViewColumnWidth(min: 200, ideal: 230)
            } detail: {
                detail(for: report)
            }
            .searchable(text: $searchText.value, placement: .toolbar, prompt: "Filter findings")
            .onChange(of: searchText.value) {
                controller.updateSearch(searchText.value)
            }
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    Toggle(isOn: $fixableOnly.value) {
                        Label("Fixable", systemImage: "wrench.and.screwdriver")
                    }
                    .help("Show only findings with a one-click fix")
                }
                if controller.isRunning {
                    ToolbarItem(placement: .automatic) {
                        ProgressView()
                            .controlSize(.small)
                            .help(controller.stageLabel)
                    }
                }
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
            .alert("Some fixes failed", isPresented: fixErrorsBinding) {
                Button("OK") { controller.fixErrors = [] }
            } message: {
                Text(controller.fixErrors.joined(separator: "\n"))
            }
            .alert("Done", isPresented: fixSummaryBinding) {
                Button("OK") { controller.lastFixSummary = nil }
            } message: {
                Text(controller.lastFixSummary ?? "")
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
        if controller.isRunning {
            let count = report.findings.count
            return count == 0
                ? controller.stageLabel
                : "\(count) findings so far — \(controller.stageLabel)"
        }
        let when = report.generatedAt.formatted(date: .abbreviated, time: .shortened)
        return "Generated \(when) — \(report.stats.packsScanned) packs, \(report.findings.count) findings"
    }

    private var actionErrorsBinding: Binding<Bool> {
        Binding(
            get: { !controller.actionErrors.isEmpty },
            set: { if !$0 { controller.actionErrors = [] } }
        )
    }

    private var fixErrorsBinding: Binding<Bool> {
        Binding(
            get: { !controller.fixErrors.isEmpty },
            set: { if !$0 { controller.fixErrors = [] } }
        )
    }

    private var fixSummaryBinding: Binding<Bool> {
        Binding(
            get: { controller.lastFixSummary != nil && controller.fixErrors.isEmpty },
            set: { if !$0 { controller.lastFixSummary = nil } }
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
        case .category(.unusedResources):
            UnusedResourcesView(groups: report.unusedResources)
        case .all:
            FindingsList(findings: visibleFindings(in: report), grouping: .category, isLive: controller.isRunning)
        case .category(let category):
            FindingsList(
                findings: visibleFindings(in: report).filter { $0.category == category },
                grouping: .pack,
                isLive: controller.isRunning
            )
        }
    }

    private func visibleFindings(in report: AnalysisReport) -> [Finding] {
        var findings = report.findings
        if let severity = severityFilter.value {
            findings = findings.filter { $0.severity == severity }
        }
        if fixableOnly.value {
            findings = findings.filter { $0.proposedFix != nil }
        }
        // Search matching runs debounced off the main thread; here it's just
        // a set-membership test.
        if let ids = controller.searchFilterIDs {
            findings = findings.filter { ids.contains($0.id) }
        }
        return findings
    }
}

// MARK: - Findings list

struct FindingsList: View {
    enum Grouping {
        case none
        case category
        case pack
    }

    /// Pack sections ordered by kind (Airports first), then name.
    /// Install-wide findings (no pack) sort last.
    private var packSections: [(title: String, items: [Finding])] {
        var byPack: [String: [Finding]] = [:]
        for finding in findings {
            byPack[finding.packName ?? "", default: []].append(finding)
        }
        return byPack
            .map { name, items -> (key: (Int, String), title: String, items: [Finding]) in
                guard !name.isEmpty else { return ((99, ""), "Install-wide", items) }
                let kind = items.first?.packKind
                let kindRank = kind.map { PackKind.allCases.firstIndex(of: $0) ?? 98 } ?? 98
                let title = kind.map { "\(name) — \($0.rawValue)" } ?? name
                return ((kindRank, name.lowercased()), title, items)
            }
            .sorted { $0.key < $1.key }
            .map { ($0.title, $0.items) }
    }

    @EnvironmentObject var controller: AnalysisController
    let findings: [Finding]
    let grouping: Grouping
    var isLive = false

    @StateObject private var selection = ViewState(Set<Finding.ID>())
    @StateObject private var confirmingFix = ViewState<[Finding]?>(nil)

    private var fixable: [Finding] {
        findings.filter { $0.proposedFix != nil }
    }

    private var selectedFixable: [Finding] {
        fixable.filter { selection.value.contains($0.id) }
    }

    var body: some View {
        if findings.isEmpty {
            ContentUnavailableView(
                isLive ? "Analyzing…" : "No Findings",
                systemImage: isLive ? "magnifyingglass" : "checkmark.seal",
                description: Text(isLive
                    ? "Findings will appear here as they are discovered."
                    : "Nothing matches the current filters.")
            )
        } else {
            VStack(spacing: 0) {
                List(selection: $selection.value) {
                    switch grouping {
                    case .category:
                        ForEach(FindingCategory.allCases, id: \.self) { category in
                            let items = findings.filter { $0.category == category }
                            if !items.isEmpty {
                                Section("\(category.rawValue) (\(items.count))") {
                                    ForEach(items) { finding in
                                        FindingRow(finding: finding).tag(finding.id)
                                    }
                                }
                            }
                        }
                    case .pack:
                        ForEach(packSections, id: \.title) { section in
                            Section("\(section.title) (\(section.items.count))") {
                                ForEach(section.items) { finding in
                                    FindingRow(finding: finding).tag(finding.id)
                                }
                            }
                        }
                    case .none:
                        ForEach(findings) { finding in
                            FindingRow(finding: finding).tag(finding.id)
                        }
                    }
                }
                .listStyle(.inset)
                .onChange(of: findings.count) {
                    // Filters changed under us: drop selection entries that no
                    // longer resolve to a visible row.
                    let valid = Set(findings.map { $0.id })
                    selection.value = selection.value.intersection(valid)
                }

                if !fixable.isEmpty {
                    Divider()
                    fixBar
                }
            }
            .confirmationDialog(
                fixConfirmationTitle,
                isPresented: Binding(
                    get: { confirmingFix.value != nil },
                    set: { if !$0 { confirmingFix.value = nil } }
                )
            ) {
                Button("Apply Fixes") {
                    if let findings = confirmingFix.value {
                        controller.applyFixes(to: findings)
                        selection.value = []
                    }
                    confirmingFix.value = nil
                }
            } message: {
                Text(fixConfirmationMessage)
            }
        }
    }

    private var fixConfirmationTitle: String {
        let count = confirmingFix.value?.count ?? 0
        return count == 1
            ? "Apply the fix to 1 file?"
            : "Apply fixes to \(count) files?"
    }

    /// Say what each kind of fix actually does — renames don't create backup
    /// files, so don't claim one.
    private var fixConfirmationMessage: String {
        let fixes = (confirmingFix.value ?? []).compactMap { $0.proposedFix }
        let allRenames = fixes.allSatisfy {
            if case .renameFile = $0 { return true } else { return false }
        }
        if allRenames && !fixes.isEmpty {
            return "Files are renamed to the exact spelling the scenery references — no content changes. Every rename is listed under Window ▸ Modifications and can be renamed back."
        }
        let hasRenames = fixes.contains {
            if case .renameFile = $0 { return true } else { return false }
        }
        if hasRenames {
            return "Content edits keep a backup beside the original (.xpsd-backup); renames just record the old name. Everything is listed under Window ▸ Modifications and can be reverted."
        }
        return "Each file is backed up beside the original (.xpsd-backup) before editing, and every change can be undone from Window ▸ Modifications."
    }

    private var fixBar: some View {
        HStack {
            if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Applying fixes…").foregroundStyle(.secondary)
            } else {
                Text(selectedFixable.isEmpty
                     ? "\(fixable.count) finding\(fixable.count == 1 ? "" : "s") can be fixed automatically"
                     : "\(selectedFixable.count) fixable selected")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button("Fix Selected") {
                confirmingFix.value = selectedFixable
            }
            .disabled(selectedFixable.isEmpty || controller.isFixing || controller.isRunning)
            Button("Fix All (\(fixable.count))") {
                confirmingFix.value = fixable
            }
            .disabled(fixable.isEmpty || controller.isFixing || controller.isRunning)
            .help(controller.isRunning ? "Available when the analysis finishes" : "Apply every automatic fix shown in this list")
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
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
                if finding.proposedFix != nil {
                    Spacer()
                    Image(systemName: "wrench.and.screwdriver.fill")
                        .font(.caption)
                        .foregroundStyle(.tint)
                        .help("Has a one-click fix")
                }
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
