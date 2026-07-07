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
    /// Explicit open/close choices for top-level groups. Groups holding
    /// error-severity findings default OPEN so a fresh run puts errors on
    /// screen without interaction (the old category list auto-expanded
    /// Missing Resources for the same reason); everything else defaults
    /// closed.
    @StateObject private var topChoices = ViewState([String: Bool]())
    /// Nested category groups the user has CLOSED — categories inside an
    /// opened package default to open, so expanding a package shows findings,
    /// not a second layer of closed disclosure triangles.
    @StateObject private var collapsed = ViewState(Set<String>())
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

    // MARK: - List

    private func resultsList(findings visible: [Finding]) -> some View {
        let dupItems = visible.filter { $0.category == .duplicatePackage }
        let dupGroups = filteredDuplicateGroups
        let (packs, installWide) = buildGroups(findings: visible,
                                               unusedGroups: filteredUnusedGroups)
        return List(selection: $selection.value) {
            // Redundant Packages: the one section that stays top-level —
            // its whole point is relationships BETWEEN packages.
            if !dupGroups.isEmpty || !dupItems.isEmpty {
                DisclosureGroup(isExpanded: topBinding(
                    "duplicates",
                    defaultOpen: dupItems.contains { $0.severity == .error })) {
                    duplicatesContent(groups: dupGroups, items: dupItems)
                } label: {
                    HStack {
                        Text(FindingCategory.duplicatePackage.rawValue)
                            .font(.callout.weight(.medium))
                        if !dupGroups.isEmpty {
                            Text("\(dupGroups.count) airport\(dupGroups.count == 1 ? "" : "s") overlapped")
                                .font(.caption.monospacedDigit())
                                .foregroundStyle(.secondary)
                        }
                        severitySummary(dupItems)
                    }
                }
            }

            ForEach(packs) { group in
                DisclosureGroup(isExpanded: topBinding(
                    "pack:\(group.id)", defaultOpen: group.worst == .error)) {
                    packContent(group)
                } label: {
                    packLabel(group)
                }
            }

            if !installWide.isEmpty {
                DisclosureGroup(isExpanded: topBinding(
                    "install",
                    defaultOpen: installWide.contains { entry in
                        entry.items.contains { $0.severity == .error }
                    })) {
                    ForEach(installWide, id: \.category) { entry in
                        categoryGroup(owner: "install", category: entry.category,
                                      items: entry.items, unused: [])
                    }
                } label: {
                    HStack {
                        Text("Entire Installation")
                            .font(.callout.weight(.medium))
                        let count = installWide.reduce(0) { $0 + $1.items.count }
                        Text("\(count)")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                        severitySummary(installWide.flatMap { $0.items })
                    }
                }
            }

            // Unused-resource verification is install-wide and only done at
            // the very end of a run — show its progress as its own row.
            if controller.isRunning {
                HStack {
                    Text(FindingCategory.unusedResources.rawValue)
                        .font(.callout.weight(.medium))
                    UnusedVerifyBadge()
                }
            }
        }
        .listStyle(.inset)
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

    @ViewBuilder
    private func duplicatesContent(groups: [DuplicateGroup], items: [Finding]) -> some View {
        if !groups.isEmpty {
            DuplicatesView(groups: groups, otherFindings: [])
                .frame(height: Self.tableHeight(
                    rows: groups.reduce(0) { $0 + $1.packs.count }))
        }
        // DUP-01 rows duplicate the table's airports; the rest (disabled
        // packs, near-identical folders) render as regular findings.
        ForEach(items.filter { groups.isEmpty || $0.checkID != "DUP-01" }) { finding in
            FindingRow(finding: finding).tag(finding.id)
        }
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

    @ViewBuilder
    private func packContent(_ group: PackGroup) -> some View {
        ForEach(group.categories, id: \.category) { entry in
            categoryGroup(owner: group.id, category: entry.category,
                          items: entry.items, unused: group.unused)
        }
    }

    /// Category header as a plain BUTTON with conditional rows beneath —
    /// not a nested DisclosureGroup. Two disclosure levels deep inside a
    /// selectable List, the outline row intermittently swallows the chevron
    /// click (and the 0.4 s streaming re-diffs cancel in-flight toggles),
    /// so expansion felt random. A button always receives its click, and
    /// the open state lives in our own set, which every rebuild respects.
    @ViewBuilder
    private func categoryGroup(owner: String, category: FindingCategory,
                               items: [Finding], unused: [UnusedResourceGroup]) -> some View {
        let key = "\(owner)|\(category.rawValue)"
        let isOpen = !collapsed.value.contains(key)
        Button {
            withAnimation {
                if isOpen { collapsed.value.insert(key) } else { collapsed.value.remove(key) }
            }
        } label: {
            categoryHeader(category, items: items, unused: unused, isOpen: isOpen)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        if isOpen {
            // The manual header lost DisclosureGroup's automatic child
            // indent — restore it so rows read as INSIDE the category.
            if category == .unusedResources && !unused.isEmpty {
                // "Could not audit" info findings would otherwise be
                // swallowed by the table replacing the finding rows.
                ForEach(items.filter { $0.checkID == "UNUSED-00" }) { finding in
                    FindingRow(finding: finding)
                        .padding(.leading, Self.categoryChildIndent)
                        .tag(finding.id)
                }
                UnusedResourcesView(groups: unused)
                    .frame(height: Self.tableHeight(
                        rows: unused.reduce(0) { $0 + $1.files.count }))
                    .padding(.leading, Self.categoryChildIndent)
            } else {
                ForEach(items) { finding in
                    FindingRow(finding: finding)
                        .padding(.leading, Self.categoryChildIndent)
                        .tag(finding.id)
                }
            }
        }
    }

    /// Leading indent for rows under a category header, matching what a
    /// nested DisclosureGroup would have added.
    static let categoryChildIndent: CGFloat = 22

    /// One height for every bottom status bar (results, package inspector)
    /// so their top dividers align exactly across the window. Fixed, not
    /// padding-driven: the results bar contains regular-size buttons, the
    /// inspector bar only text — equal padding gives unequal heights.
    static let bottomBarHeight: CGFloat = 38

    private func categoryHeader(_ category: FindingCategory, items: [Finding],
                                unused: [UnusedResourceGroup], isOpen: Bool) -> some View {
        HStack(spacing: 6) {
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .rotationEffect(.degrees(isOpen ? 90 : 0))
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
            Spacer(minLength: 0)
        }
    }

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
                Text("cross-checking \(p.done)/\(p.total) packages")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            } else {
                Text("auditing…")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func topBinding(_ key: String, defaultOpen: Bool) -> Binding<Bool> {
        Binding(
            get: { topChoices.value[key] ?? defaultOpen },
            set: { topChoices.value[key] = $0 }
        )
    }

    // MARK: - Bottom bar (progress + fixes, per feedback)

    private func bottomBar(fixable: [Finding]) -> some View {
        let selectedFixable = fixable.filter { selection.value.contains($0.id) }
        // Appearance-changing fixes (spill clamps) never ride the bulk
        // button — the user selects those deliberately.
        let bulkFixable = fixable.filter { !($0.proposedFix?.changesAppearance ?? false) }
        return HStack(spacing: 8) {
            if controller.isRunning {
                ProgressView().controlSize(.small)
                StageLabelText(suffix: fixable.isEmpty
                    ? nil : "\(fixable.count) fixable so far")
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
            Button("Fix All (\(bulkFixable.count))") {
                confirmingFix.value = bulkFixable
            }
            .disabled(bulkFixable.isEmpty || controller.isFixing || controller.isRunning)
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
