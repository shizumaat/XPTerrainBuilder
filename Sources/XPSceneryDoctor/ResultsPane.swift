import SwiftUI
import SceneryKit

/// Bottom third of the map window: analysis results grouped BY PACKAGE —
/// every package the map is looking at expands into its finding categories
/// (Missing Resources, Package Health, …). Redundant Packages stays a
/// top-level section (its findings span packages by nature) and install-wide
/// findings get their own section at the end. Multi-select + Fix and the
/// live progress live in the bottom bar.
struct ResultsPane: View {
    @EnvironmentObject var controller: AnalysisController
    /// Pack names in the current map view/selection; results are filtered to
    /// them (install-wide findings with no pack stay visible). nil = show all.
    var packFilter: Set<String>? = nil
    @StateObject private var selection = ViewState(Set<Finding.ID>())
    @StateObject private var confirmingFix = ViewState<[Finding]?>(nil)

    /// EXPENSIVE — string-set filtering over every finding. Computed exactly
    /// once per body evaluation and passed down; as a computed property read
    /// from each category row it profiled at ~45% of the main thread.
    private var findings: [Finding] {
        let all = controller.report?.findings ?? []
        guard let filter = packFilter else { return all }
        // Airports of the packs in view — log lines mention ICAOs, not packs.
        let icaos = Set(controller.installationPacks
            .filter { filter.contains($0.name) }
            .flatMap { $0.airports.keys })
        return all.compactMap { finding in
            switch finding.checkID {
            case "LOG-90":
                // Aggregate log noise: keep only the lines that mention a
                // selected pack or one of its airports.
                let lines = finding.detail.components(separatedBy: "\n").filter { line in
                    filter.contains(where: { line.contains($0) })
                        || icaos.contains(where: { line.contains(" \($0) ") || line.contains("'\($0)'") })
                }
                guard !lines.isEmpty else { return nil }
                return finding.withContent(
                    title: "\(lines.count) scenery-related log message\(lines.count == 1 ? "" : "s") for this selection",
                    detail: lines.joined(separator: "\n"))
            case "LOG-92":
                // Default-data ATC losses never belong to a selection.
                return nil
            case "INST-02":
                // Non-scenery folders have no location by definition —
                // always visible (their relatedPacks are never in any
                // viewport, so the default branch would hide them forever).
                return finding
            case "DUP-02":
                // Disabled-packs aggregate: narrow to the ones in view.
                guard let related = finding.relatedPacks else { return finding }
                let visible = related.filter { filter.contains($0.name) }
                guard !visible.isEmpty else { return nil }
                guard visible.count < related.count else { return finding }
                return finding.withContent(
                    title: "\(visible.count) of \(related.count) disabled scenery pack\(related.count == 1 ? "" : "s") in view",
                    detail: "Disabled but still on disk: \(visible.map { $0.name }.joined(separator: ", ")).",
                    relatedPacks: visible)
            default:
                if let packName = finding.packName {
                    return filter.contains(packName) ? finding : nil
                }
                // Multi-pack findings (near-identical folders …) follow the
                // packs they involve; truly install-wide ones stay visible.
                if let related = finding.relatedPacks {
                    return related.contains(where: { filter.contains($0.name) }) ? finding : nil
                }
                return finding
            }
        }
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

    var body: some View {
        let visible = findings
        let fixable = visible.filter { $0.proposedFix != nil }
        VStack(spacing: 0) {
            if let report = controller.report {
                header(for: report, findings: visible)
                Divider()
                if visible.isEmpty && filteredDuplicateGroups.isEmpty
                    && filteredUnusedGroups.isEmpty && !controller.isRunning {
                    ContentUnavailableView(
                        "No Findings",
                        systemImage: "checkmark.seal",
                        description: Text("The analyzed packages look healthy.")
                    )
                } else {
                    resultsList(findings: visible)
                }
            } else {
                ContentUnavailableView(
                    "No Analysis Yet",
                    systemImage: "stethoscope",
                    description: Text("Select tiles on the map and press Analyze — or Analyze All (⇧⌘R) for the whole install.")
                )
            }
            Divider()
            bottomBar(fixable: fixable)
        }
    }

    private func header(for report: AnalysisReport, findings: [Finding]) -> some View {
        HStack(spacing: 8) {
            Text("Results")
                .font(.headline)
            Text(subtitle(for: report, findings: findings))
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

    private func subtitle(for report: AnalysisReport, findings: [Finding]) -> String {
        var parts: [String] = []
        if let scope = report.scopeDescription { parts.append(scope) }
        if controller.isRunning {
            parts.append("\(findings.count.formatted()) findings so far")
        } else {
            parts.append("Generated \(report.generatedAt.formatted(date: .abbreviated, time: .shortened))")
            if packFilter != nil, findings.count != report.findings.count {
                parts.append("\(findings.count.formatted()) of \(report.findings.count.formatted()) findings in view")
            } else {
                parts.append("\(findings.count.formatted()) findings")
            }
        }
        return parts.joined(separator: " — ")
    }

    // MARK: - Grouping

    /// One package's slice of the report, precomputed once per body.
    ///
    /// Keyed by pack NAME, knowingly: findings carry only packName (no pack
    /// path), so the rare same-named twin in Custom Scenery and the disabled
    /// folder (lore #15) merges into one display group here. That's benign —
    /// ids stay unique (dictionary grouping), each finding's own path points
    /// into the right folder — but don't extend this into a lookup table for
    /// pack OPERATIONS; those must key by path.
    private struct PackGroup: Identifiable {
        let id: String  // pack name
        var kind: PackKind?
        /// Categories in FindingCategory declaration order; Redundant
        /// Packages never appears here (it stays top-level).
        var categories: [(category: FindingCategory, items: [Finding])] = []
        var unused: [UnusedResourceGroup] = []
        var findingCount = 0
        var worst = Severity.info
    }

    private func buildGroups(
        findings: [Finding], unusedGroups: [UnusedResourceGroup]
    ) -> (packs: [PackGroup], installWide: [(category: FindingCategory, items: [Finding])]) {
        var byPack: [String: [Finding]] = [:]
        var installWide: [Finding] = []
        for finding in findings where finding.category != .duplicatePackage {
            if let pack = finding.packName {
                byPack[pack, default: []].append(finding)
            } else {
                installWide.append(finding)
            }
        }
        var unusedByPack: [String: [UnusedResourceGroup]] = [:]
        for group in unusedGroups {
            unusedByPack[group.packName, default: []].append(group)
        }
        // A pack whose only issue is unused files still gets a group.
        for name in unusedByPack.keys where byPack[name] == nil { byPack[name] = [] }

        func categorize(_ items: [Finding], hasUnused: Bool) -> [(category: FindingCategory, items: [Finding])] {
            FindingCategory.allCases.compactMap { category in
                guard category != .duplicatePackage else { return nil }
                let inCategory = items.filter { $0.category == category }
                if inCategory.isEmpty && !(category == .unusedResources && hasUnused) { return nil }
                return (category, inCategory)
            }
        }

        var packs: [PackGroup] = byPack.map { name, items in
            var group = PackGroup(id: name, kind: items.first(where: { $0.packKind != nil })?.packKind)
            group.unused = unusedByPack[name] ?? []
            group.categories = categorize(items, hasUnused: !group.unused.isEmpty)
            group.findingCount = items.count
            group.worst = items.map { $0.severity }.min() ?? .info
            if group.kind == nil {
                group.kind = group.unused.isEmpty ? nil : .other
            }
            return group
        }
        // Most severe first (Severity orders error < warning < info), then name.
        packs.sort { ($0.worst, $0.id.lowercased()) < ($1.worst, $1.id.lowercased()) }
        return (packs, categorize(installWide, hasUnused: false))
    }

    // MARK: - Outline

    private func resultsList(findings visible: [Finding]) -> some View {
        ResultsOutlineView(
            roots: outlineSpecs(findings: visible),
            selection: selection.value,
            onSelectionChange: { selection.value = $0 }
        )
        .onChange(of: visible.count) {
            let valid = Set(visible.map { $0.id })
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

    /// Hosted outline rows live in their own NSHostingView hierarchies,
    /// which do NOT inherit this view's environment — inject explicitly.
    private func wrap<V: View>(_ view: V) -> AnyView {
        AnyView(
            view
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .padding(.vertical, 2)
                .frame(maxWidth: .infinity, alignment: .leading)
        )
    }

    private func outlineSpecs(findings visible: [Finding]) -> [OutlineNodeSpec] {
        let dupItems = visible.filter { $0.category == .duplicatePackage }
        let dupGroups = filteredDuplicateGroups
        let (packs, installWide) = buildGroups(findings: visible,
                                               unusedGroups: filteredUnusedGroups)
        var roots: [OutlineNodeSpec] = []

        // Redundant Packages: the one section that stays top-level — its
        // whole point is relationships BETWEEN packages.
        if !dupGroups.isEmpty || !dupItems.isEmpty {
            var children: [OutlineNodeSpec] = []
            if !dupGroups.isEmpty {
                children.append(OutlineNodeSpec(
                    id: "dup-table",
                    view: wrap(DuplicatesView(groups: dupGroups, otherFindings: [])
                        .frame(height: Self.tableHeight(
                            rows: dupGroups.reduce(0) { $0 + $1.packs.count })))))
            }
            // DUP-01 rows duplicate the table's airports; the rest (disabled
            // packs, near-identical folders) render as regular findings.
            children += dupItems
                .filter { dupGroups.isEmpty || $0.checkID != "DUP-01" }
                .map(findingSpec)
            roots.append(OutlineNodeSpec(
                id: "duplicates",
                view: wrap(HStack {
                    Text(FindingCategory.duplicatePackage.rawValue)
                        .font(.callout.weight(.medium))
                    if !dupGroups.isEmpty {
                        Text("\(dupGroups.count) airport\(dupGroups.count == 1 ? "" : "s") overlapped")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                    severitySummary(dupItems)
                }),
                defaultExpanded: dupItems.contains { $0.severity == .error },
                typeSelect: FindingCategory.duplicatePackage.rawValue,
                children: children))
        }

        for group in packs {
            roots.append(OutlineNodeSpec(
                id: "pack:\(group.id)",
                view: wrap(packLabel(group)),
                defaultExpanded: group.worst == .error,
                typeSelect: group.id,
                children: group.categories.map { entry in
                    categorySpec(owner: group.id, category: entry.category,
                                 items: entry.items, unused: group.unused)
                }))
        }

        if !installWide.isEmpty {
            let count = installWide.reduce(0) { $0 + $1.items.count }
            roots.append(OutlineNodeSpec(
                id: "install",
                view: wrap(HStack {
                    Text("Entire Installation")
                        .font(.callout.weight(.medium))
                    Text("\(count)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                    severitySummary(installWide.flatMap { $0.items })
                }),
                defaultExpanded: installWide.contains { entry in
                    entry.items.contains { $0.severity == .error }
                },
                typeSelect: "Entire Installation",
                children: installWide.map { entry in
                    categorySpec(owner: "install", category: entry.category,
                                 items: entry.items, unused: [])
                }))
        }

        // Unused-resource verification is install-wide and only done at the
        // very end of a run — show its progress as its own row.
        if controller.isRunning {
            roots.append(OutlineNodeSpec(
                id: "verify",
                view: wrap(HStack {
                    Text(FindingCategory.unusedResources.rawValue)
                        .font(.callout.weight(.medium))
                    UnusedVerifyBadge()
                })))
        }
        return roots
    }

    private func categorySpec(owner: String, category: FindingCategory,
                              items: [Finding], unused: [UnusedResourceGroup]) -> OutlineNodeSpec {
        var children: [OutlineNodeSpec] = []
        if category == .unusedResources && !unused.isEmpty {
            // "Could not audit" info findings would otherwise be swallowed
            // by the table replacing the finding rows.
            children = items.filter { $0.checkID == "UNUSED-00" }.map(findingSpec)
            children.append(OutlineNodeSpec(
                id: "unused-table:\(owner)",
                view: wrap(UnusedResourcesView(groups: unused)
                    .frame(height: Self.tableHeight(
                        rows: unused.reduce(0) { $0 + $1.files.count })))))
        } else {
            children = items.map(findingSpec)
        }
        return OutlineNodeSpec(
            id: "\(owner)|\(category.rawValue)",
            view: wrap(HStack {
                Text(category.rawValue)
                    .font(.callout)
                if category == .unusedResources, !unused.isEmpty {
                    // The expanded view is a per-FILE table, so the headline
                    // count must be files, not findings.
                    Text(Self.unusedSummary(unused))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                } else {
                    Text("\(items.count)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                    severitySummary(items)
                }
            }),
            defaultExpanded: true, // opening a package shows findings, not
                                   // a second layer of closed chevrons
            typeSelect: category.rawValue,
            children: children)
    }

    /// A finding is a selectable row whose detail is a native CHILD row —
    /// expanding it is ordinary outline expansion, so row heights stay
    /// static and the outline machinery does all the work.
    private func findingSpec(_ finding: Finding) -> OutlineNodeSpec {
        OutlineNodeSpec(
            id: "find:\(finding.id)",
            view: wrap(FindingLabel(finding: finding)),
            findingID: finding.id,
            typeSelect: finding.title,
            children: [OutlineNodeSpec(
                id: "detail:\(finding.id)",
                view: wrap(FindingDetailView(finding: finding).padding(.vertical, 4)))])
    }

    private func packLabel(_ group: PackGroup) -> some View {
        HStack(spacing: 8) {
            PackKindIcon(kind: group.kind)
            Text(group.id)
                .font(.callout.weight(.medium))
                .lineLimit(1)
                .truncationMode(.middle)
            if group.findingCount > 0 {
                Text("\(group.findingCount)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            severitySummary(group.categories.flatMap { $0.items })
            if !group.unused.isEmpty {
                Text(Self.unusedSummary(group.unused))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
    }

    /// One height for every bottom status bar (results, package inspector)
    /// so their top dividers align exactly across the window. Fixed, not
    /// padding-driven: the results bar contains regular-size buttons, the
    /// inspector bar only text — equal padding gives unequal heights.
    static let bottomBarHeight: CGFloat = 38

    /// Embedded tables size to their rows instead of a fixed 300 pt block.
    static func tableHeight(rows: Int) -> CGFloat {
        min(320, CGFloat(max(rows, 1)) * 26 + 92)
    }

    /// e.g. "3,214 files — 68.4 GB"
    static func unusedSummary(_ groups: [UnusedResourceGroup]) -> String {
        let files = groups.reduce(0) { $0 + $1.files.count }
        let bytes = groups.reduce(Int64(0)) { $0 + $1.totalBytes }
        let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
        return "\(files.formatted()) file\(files == 1 ? "" : "s") — \(size)"
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

    /// Small leaf views that observe ProgressModel, so high-frequency stage
    /// ticks re-render only these and never the surrounding lists.
    ///
    /// While the per-pack pipeline runs, progress is DETERMINATE — we know
    /// exactly how many packages need evaluating — so the bar shows a round
    /// determinate indicator and "done/total — current package" instead of
    /// a spinner. Other stages (scan, log, duplicates) stay indeterminate.
    struct RunProgressView: View {
        @EnvironmentObject var progress: ProgressModel

        var body: some View {
            if let p = progress.packProgress {
                ProgressView(value: Double(p.done), total: Double(max(p.total, 1)))
                    .progressViewStyle(.circular)
                    .controlSize(.small)
                Text("\(p.done.formatted())/\(p.total.formatted()) — \(p.name)")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            } else if let v = progress.unusedVerifyProgress {
                ProgressView(value: Double(v.done), total: Double(max(v.total, 1)))
                    .progressViewStyle(.circular)
                    .controlSize(.small)
                Text("\(v.done.formatted())/\(v.total.formatted()) — cross-checking unused files against every package")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            } else {
                ProgressView().controlSize(.small)
                StageLabelText()
            }
        }
    }

    struct StageLabelText: View {
        @EnvironmentObject var progress: ProgressModel
        var suffix: String?

        var body: some View {
            Text(suffix.map { "\(progress.stageLabel) — \($0)" } ?? progress.stageLabel)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }

    struct UnusedVerifyBadge: View {
        @EnvironmentObject var progress: ProgressModel

        var body: some View {
            if let p = progress.unusedVerifyProgress {
                // Candidates only become deletable findings after the
                // every-package cross-check.
                ProgressView(value: Double(p.done), total: Double(max(p.total, 1)))
                    .frame(width: 130)
                    .controlSize(.small)
                Text("cross-checking \(p.done.formatted())/\(p.total.formatted()) packages")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            } else {
                Text("auditing…")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Bottom bar (progress + fixes, per feedback)

    private func bottomBar(fixable: [Finding]) -> some View {
        let selectedFixable = fixable.filter { selection.value.contains($0.id) }
        // Appearance-changing fixes (spill clamps) never ride the bulk
        // button — the user selects those deliberately.
        let bulkFixable = fixable.filter { !($0.proposedFix?.changesAppearance ?? false) }
        return HStack(spacing: 8) {
            if controller.isRunning {
                RunProgressView()
            } else if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Applying fixes…").foregroundStyle(.secondary)
            } else if controller.report != nil {
                Text(selectedFixable.isEmpty
                     ? "\(fixable.count.formatted()) finding\(fixable.count == 1 ? "" : "s") can be fixed automatically"
                     : "\(selectedFixable.count.formatted()) fixable selected")
                    .foregroundStyle(.secondary)
            } else {
                Text(MapMainView.systemInfo.summary)
                    .foregroundStyle(.tertiary)
            }
            Spacer()
            Button("Fix Selected") {
                confirmingFix.value = selectedFixable
            }
            .disabled(selectedFixable.isEmpty || controller.isFixing)
            Button("Fix All (\(bulkFixable.count.formatted()))") {
                confirmingFix.value = bulkFixable
            }
            .disabled(bulkFixable.isEmpty || controller.isFixing)
            .help(controller.isRunning
                  ? "Applies the fixes found so far — more may appear as the analysis continues"
                  : "Apply every automatic fix shown in this list (appearance-changing fixes must be selected individually)")
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .frame(height: Self.bottomBarHeight)
        .background(.bar)
    }
}

/// Category icon tinted to match the map legend — shared by the inspector's
/// package rows and the results pane's package groups.
struct PackKindIcon: View {
    let kind: PackKind?

    var body: some View {
        let (symbol, color): (String, Color) = switch kind {
        case .airport: ("airplane.circle", .red)
        case .landmark: ("building.2", .blue)
        case .ortho: ("photo", .brown)
        case .mesh: ("mountain.2", .green)
        case .library: ("books.vertical", .purple)
        case .other, nil: ("shippingbox", .secondary)
        }
        return Image(systemName: symbol)
            .font(.callout)
            .foregroundStyle(color)
            .frame(width: 18)
            .help(kind?.rawValue ?? "")
    }
}
