import SwiftUI
import SceneryKit

/// Bottom third of the map window: the analysis results as collapsible
/// category groups with counts, the same finding rows as the report window,
/// multi-select + Fix, and the live progress in the bottom bar.
struct ResultsPane: View {
    @EnvironmentObject var controller: AnalysisController
    /// Pack names in the current map view/selection; results are filtered to
    /// them (install-wide findings with no pack stay visible). nil = show all.
    var packFilter: Set<String>? = nil
    @StateObject private var selection = ViewState(Set<Finding.ID>())
    @StateObject private var expanded = ViewState(Set<FindingCategory>([.missingResource]))
    @StateObject private var confirmingFix = ViewState<[Finding]?>(nil)

    private var findings: [Finding] {
        let all = controller.report?.findings ?? []
        guard let filter = packFilter else { return all }
        return all.filter { $0.packName.map(filter.contains) ?? true }
    }

    private var filteredDuplicateGroups: [DuplicateGroup] {
        let groups = controller.report?.duplicateGroups ?? []
        guard let filter = packFilter else { return groups }
        return groups.filter { group in group.packs.contains { filter.contains($0.name) } }
    }

    private var filteredUnusedGroups: [UnusedResourceGroup] {
        let groups = controller.report?.unusedResources ?? []
        guard let filter = packFilter else { return groups }
        return groups.filter { filter.contains($0.packName) }
    }

    private var fixable: [Finding] {
        findings.filter { $0.proposedFix != nil }
    }

    private var selectedFixable: [Finding] {
        fixable.filter { selection.value.contains($0.id) }
    }

    var body: some View {
        VStack(spacing: 0) {
            if let report = controller.report {
                header(for: report)
                Divider()
                if findings.isEmpty && !controller.isRunning {
                    ContentUnavailableView(
                        "No Findings",
                        systemImage: "checkmark.seal",
                        description: Text("The analyzed packages look healthy.")
                    )
                } else {
                    resultsList(report: report)
                }
            } else {
                ContentUnavailableView(
                    "No Analysis Yet",
                    systemImage: "stethoscope",
                    description: Text("Select tiles on the map and press Analyze — or Analyze All (⇧⌘R) for the whole install.")
                )
            }
            Divider()
            bottomBar
        }
    }

    private func header(for report: AnalysisReport) -> some View {
        HStack(spacing: 8) {
            Text("Results")
                .font(.headline)
            Text(subtitle(for: report))
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            Button {
                controller.exportReportJSON()
            } label: {
                Image(systemName: "square.and.arrow.up")
            }
            .buttonStyle(.borderless)
            .help("Export the report as JSON (⇧⌘E)")
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
    }

    private func subtitle(for report: AnalysisReport) -> String {
        var parts: [String] = []
        if let scope = report.scopeDescription { parts.append(scope) }
        if controller.isRunning {
            parts.append("\(findings.count) findings so far")
        } else {
            parts.append("Generated \(report.generatedAt.formatted(date: .abbreviated, time: .shortened))")
            if packFilter != nil, findings.count != report.findings.count {
                parts.append("\(findings.count) of \(report.findings.count) findings in view")
            } else {
                parts.append("\(findings.count) findings")
            }
        }
        return parts.joined(separator: " — ")
    }

    private func resultsList(report: AnalysisReport) -> some View {
        List(selection: $selection.value) {
            ForEach(FindingCategory.allCases, id: \.self) { category in
                let items = findings.filter { $0.category == category }
                if !items.isEmpty {
                    DisclosureGroup(isExpanded: categoryBinding(category)) {
                        categoryContent(category, items: items, report: report)
                    } label: {
                        HStack {
                            Text(category.rawValue)
                                .font(.callout.weight(.medium))
                            Text("\(items.count)")
                                .font(.caption.monospacedDigit())
                                .foregroundStyle(.secondary)
                            severitySummary(items)
                        }
                    }
                }
            }
        }
        .listStyle(.inset)
        .onChange(of: findings.count) {
            let valid = Set(findings.map { $0.id })
            selection.value = selection.value.intersection(valid)
        }
        .confirmationDialog(
            "Apply fixes to \(confirmingFix.value?.count ?? 0) file\((confirmingFix.value?.count ?? 0) == 1 ? "" : "s")?",
            isPresented: Binding(
                get: { confirmingFix.value != nil },
                set: { if !$0 { confirmingFix.value = nil } }
            )
        ) {
            Button("Apply Fixes") {
                if let toFix = confirmingFix.value {
                    controller.applyFixes(to: toFix)
                    selection.value = []
                }
                confirmingFix.value = nil
            }
        } message: {
            Text("Content edits keep a backup beside the original; renames record the old name. Everything is listed under Window ▸ Modifications and can be reverted.")
        }
    }

    @ViewBuilder
    private func categoryContent(_ category: FindingCategory, items: [Finding],
                                 report: AnalysisReport) -> some View {
        switch category {
        case .duplicatePackage where !filteredDuplicateGroups.isEmpty:
            DuplicatesView(
                groups: filteredDuplicateGroups,
                otherFindings: items.filter { $0.checkID != "DUP-01" }
            )
            .frame(height: 300)
        case .unusedResources where !filteredUnusedGroups.isEmpty:
            UnusedResourcesView(groups: filteredUnusedGroups)
                .frame(height: 300)
        default:
            ForEach(items) { finding in
                FindingRow(finding: finding).tag(finding.id)
            }
        }
    }

    private func severitySummary(_ items: [Finding]) -> some View {
        HStack(spacing: 6) {
            let errors = items.filter { $0.severity == .error }.count
            let warnings = items.filter { $0.severity == .warning }.count
            if errors > 0 {
                Label("\(errors)", systemImage: "xmark.octagon.fill")
                    .foregroundStyle(.red)
            }
            if warnings > 0 {
                Label("\(warnings)", systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
            }
        }
        .font(.caption)
        .labelStyle(.titleAndIcon)
    }

    private func categoryBinding(_ category: FindingCategory) -> Binding<Bool> {
        Binding(
            get: { expanded.value.contains(category) },
            set: { open in
                if open { expanded.value.insert(category) } else { expanded.value.remove(category) }
            }
        )
    }

    // MARK: - Bottom bar (progress + fixes, per feedback)

    private var bottomBar: some View {
        HStack(spacing: 8) {
            if controller.isRunning {
                ProgressView().controlSize(.small)
                Text(fixable.isEmpty
                     ? controller.stageLabel
                     : "\(controller.stageLabel) — \(fixable.count) fixable so far")
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            } else if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Applying fixes…").foregroundStyle(.secondary)
            } else if controller.report != nil {
                Text(selectedFixable.isEmpty
                     ? "\(fixable.count) finding\(fixable.count == 1 ? "" : "s") can be fixed automatically"
                     : "\(selectedFixable.count) fixable selected")
                    .foregroundStyle(.secondary)
            } else {
                Text(MapMainView.systemInfo.summary)
                    .foregroundStyle(.tertiary)
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
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }
}
