import SwiftUI
import SceneryKit

/// Actionable view of redundant packages: a multi-select table of every
/// (airport, package) pair, with pack actions available from the Actions
/// menu button, the row context menu, and the Delete key — all one code path.
struct DuplicatesView: View {
    @EnvironmentObject var controller: AnalysisController
    let groups: [DuplicateGroup]
    let otherFindings: [Finding]

    @StateObject private var selection = ViewState(Set<Row.ID>())
    @StateObject private var confirmingTrash = ViewState(false)
    @StateObject private var sortOrder = ViewState([KeyPathComparator(\Row.icao)])

    struct Row: Identifiable {
        let id: String
        let icao: String
        let airportName: String
        let pack: DuplicatePack

        // Non-optional keys for sortable columns.
        var packName: String { pack.name }
        var priority: Int { pack.iniIndex ?? Int.max }
        var sizeBytes: Int64 { pack.sizeBytes }
        var kindName: String { pack.kind?.rawValue ?? "" }
        var modified: Date { pack.modifiedDate ?? .distantPast }
        var statusRank: Int { pack.isWinner ? 0 : (pack.isEnabled ? 1 : 2) }
    }

    private var rows: [Row] {
        groups.flatMap { group in
            group.packs.map { pack in
                // Keyed by PATH, not name: the same-named pack can exist in
                // both Custom Scenery and the disabled folder at once (the
                // LFMN crash), and duplicate row ids trap Dictionary inits
                // and break Table selection.
                Row(id: "\(group.icao)\u{1F}\(pack.path)",
                    icao: group.icao,
                    airportName: group.airportName,
                    pack: pack)
            }
        }
        .sorted(using: sortOrder.value)
    }

    /// Selected rows resolved to unique pack names (one pack can appear
    /// under several airports).
    private var selectedPackNames: [String] {
        let byID = Dictionary(rows.map { ($0.id, $0.pack.name) },
                              uniquingKeysWith: { first, _ in first })
        return Array(Set(selection.value.compactMap { byID[$0] })).sorted()
    }

    /// Unique selected packs by status, for context-aware actions.
    private func packNames(withStatus status: PackStatus, in ids: Set<Row.ID>) -> [String] {
        var names = Set<String>()
        for row in rows where ids.contains(row.id) && (row.pack.status ?? .enabled) == status {
            names.insert(row.pack.name)
        }
        return names.sorted()
    }

    var body: some View {
        if groups.isEmpty && otherFindings.isEmpty {
            ContentUnavailableView(
                controller.isRunning ? "Analyzing…" : "No Redundant Packages",
                systemImage: controller.isRunning ? "magnifyingglass" : "checkmark.seal",
                description: Text(controller.isRunning
                    ? "Overlapping packages will appear here once the scan reaches them."
                    : "No airport is provided by more than one custom package.")
            )
        } else {
            VStack(spacing: 0) {
                table
                if !otherFindings.isEmpty {
                    Divider()
                    List(otherFindings) { FindingRow(finding: $0) }
                        .listStyle(.inset)
                        .frame(height: 140)
                }
                Divider()
                actionBar
            }
            .confirmationDialog(
                trashConfirmationTitle,
                isPresented: $confirmingTrash.value
            ) {
                Button("Move to Trash", role: .destructive) {
                    controller.applyPackAction(.trash, to: selectedPackNames)
                    selection.value = []
                }
            } message: {
                Text("The folders move to the Trash and their scenery_packs.ini entries are removed. You can restore them from the Trash.")
            }
        }
    }

    private var trashConfirmationTitle: String {
        let names = selectedPackNames
        return names.count == 1
            ? "Move “\(names[0])” to the Trash?"
            : "Move \(names.count) packages to the Trash?"
    }

    // MARK: - Table

    private var table: some View {
        Table(rows, selection: $selection.value, sortOrder: $sortOrder.value) {
            TableColumn("Airport", value: \.icao) { row in
                Text("\(row.icao) — \(row.airportName)")
            }
            .width(min: 140, ideal: 190)

            TableColumn("Package", value: \.packName) { row in
                Text(row.pack.name)
                    .help(row.pack.path)
            }

            TableColumn("Type", value: \.kindName) { row in
                Text(row.pack.kind?.rawValue ?? "—")
                    .foregroundStyle(.secondary)
            }
            .width(90)

            TableColumn("Priority", value: \.priority) { row in
                Text(row.pack.iniIndex.map { String($0 + 1) } ?? "—")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            .width(60)

            TableColumn("Size", value: \.sizeBytes) { row in
                Text(row.pack.sizeBytes > 0
                     ? ByteCountFormatter.string(fromByteCount: row.pack.sizeBytes, countStyle: .file)
                     : "—")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .width(80)

            TableColumn("Modified", value: \.modified) { row in
                Text(row.pack.modifiedDate.map { $0.formatted(date: .abbreviated, time: .omitted) } ?? "—")
                    .foregroundStyle(.secondary)
            }
            .width(90)

            TableColumn("Status", value: \.statusRank) { row in
                StatusBadge(pack: row.pack)
            }
            .width(90)
        }
        .contextMenu(forSelectionType: Row.ID.self) { ids in
            // Right-clicking outside the selection acts on the clicked rows.
            actionButtons(for: ids.isEmpty ? selection.value : ids)
        }
        .onDeleteCommand {
            if !selectedPackNames.isEmpty { confirmingTrash.value = true }
        }
    }

    private func packNames(for ids: Set<Row.ID>) -> [String] {
        let byID = Dictionary(rows.map { ($0.id, $0.pack.name) },
                              uniquingKeysWith: { first, _ in first })
        return Array(Set(ids.compactMap { byID[$0] })).sorted()
    }

    /// Context-aware actions: each button appears only when the selection
    /// contains packs it applies to, and acts on exactly that subset.
    @ViewBuilder
    private func actionButtons(for ids: Set<Row.ID>) -> some View {
        let enabled = packNames(withStatus: .enabled, in: ids)
        let disabled = packNames(withStatus: .disabled, in: ids)
        let uninstalled = packNames(withStatus: .uninstalled, in: ids)
        let installed = (enabled + disabled).sorted()
        let all = packNames(for: ids)

        if !disabled.isEmpty {
            Button(countLabel("Enable", disabled, of: all)) {
                controller.applyPackAction(.enable, to: disabled)
            }
        }
        if !enabled.isEmpty {
            Button(countLabel("Disable", enabled, of: all)) {
                controller.applyPackAction(.disable, to: enabled)
            }
        }
        if !uninstalled.isEmpty {
            Button(countLabel("Install", uninstalled, of: all)) {
                controller.applyPackAction(.install, to: uninstalled)
            }
        }
        if !installed.isEmpty {
            Button(countLabel("Uninstall", installed, of: all)) {
                controller.applyPackAction(.uninstall, to: installed)
                selection.value = []
            }
        }
        if !all.isEmpty {
            Divider()
            Button("Move to Trash…", role: .destructive) {
                confirmingTrash.value = true
            }
        }
    }

    private func countLabel(_ verb: String, _ subset: [String], of all: [String]) -> String {
        subset.count == all.count ? verb : "\(verb) (\(subset.count))"
    }

    // MARK: - Actions

    private var actionBar: some View {
        HStack {
            if controller.isApplyingAction {
                ProgressView()
                    .controlSize(.small)
                Text("Applying…")
                    .foregroundStyle(.secondary)
            } else {
                Text(selectionSummary)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Menu {
                actionButtons(for: selection.value)
            } label: {
                Label("Actions", systemImage: "wrench.and.screwdriver")
            }
            .menuStyle(.borderedButton)
            .fixedSize()
            .disabled(selectedPackNames.isEmpty || controller.isApplyingAction || controller.isRunning)
            .help(controller.isRunning
                  ? "Available when the analysis finishes"
                  : "Apply an action to the selected packages")
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    private var selectionSummary: String {
        let count = selectedPackNames.count
        switch count {
        case 0: return "\(groups.count) airports with overlapping packages — select packages to act on them"
        case 1: return "1 package selected"
        default: return "\(count) packages selected"
        }
    }

}

struct StatusBadge: View {
    let pack: DuplicatePack

    var body: some View {
        if pack.isWinner {
            Text("Active")
                .font(.caption.weight(.medium))
                .padding(.horizontal, 6)
                .padding(.vertical, 1)
                .background(.green.opacity(0.18), in: Capsule())
                .foregroundStyle(.green)
                .help("Highest-priority enabled package — this is the one X-Plane shows")
        } else {
            switch pack.status ?? .enabled {
            case .enabled:
                Text("Enabled")
                    .font(.caption)
                    .foregroundStyle(.orange)
                    .help("Loads but is shadowed or conflicts with the active package")
            case .disabled:
                Text("Disabled")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .help("Listed as SCENERY_PACK_DISABLED in scenery_packs.ini")
            case .uninstalled:
                Text("Uninstalled")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .help("In 'Custom Scenery (Disabled)' — X-Plane never sees it")
            }
        }
    }
}
