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

    struct Row: Identifiable {
        let id: String
        let icao: String
        let airportName: String
        let pack: DuplicatePack
    }

    private var rows: [Row] {
        groups.flatMap { group in
            group.packs.map { pack in
                Row(id: "\(group.icao)\u{1F}\(pack.name)",
                    icao: group.icao,
                    airportName: group.airportName,
                    pack: pack)
            }
        }
    }

    /// Selected rows resolved to unique pack names (one pack can appear
    /// under several airports).
    private var selectedPackNames: [String] {
        let byID = Dictionary(uniqueKeysWithValues: rows.map { ($0.id, $0.pack.name) })
        return Array(Set(selection.value.compactMap { byID[$0] })).sorted()
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
        Table(rows, selection: $selection.value) {
            TableColumn("Airport") { row in
                Text("\(row.icao) — \(row.airportName)")
            }
            .width(min: 140, ideal: 190)

            TableColumn("Package") { row in
                Text(row.pack.name)
                    .help(row.pack.path)
            }

            TableColumn("Priority") { row in
                Text(row.pack.iniIndex.map { String($0 + 1) } ?? "—")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            .width(60)

            TableColumn("Status") { row in
                StatusBadge(pack: row.pack)
            }
            .width(90)
        }
        .contextMenu(forSelectionType: Row.ID.self) { ids in
            // Right-clicking outside the selection acts on the clicked rows.
            let names = packNames(for: ids.isEmpty ? selection.value : ids)
            actionButtons(for: names)
        }
        .onDeleteCommand {
            if !selectedPackNames.isEmpty { confirmingTrash.value = true }
        }
    }

    private func packNames(for ids: Set<Row.ID>) -> [String] {
        let byID = Dictionary(uniqueKeysWithValues: rows.map { ($0.id, $0.pack.name) })
        return Array(Set(ids.compactMap { byID[$0] })).sorted()
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
                actionButtons(for: selectedPackNames)
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

    @ViewBuilder
    private func actionButtons(for names: [String]) -> some View {
        Button("Disable") {
            controller.applyPackAction(.disable, to: names)
        }
        Button("Enable") {
            controller.applyPackAction(.enable, to: names)
        }
        Button("Move to Disabled Folder") {
            controller.applyPackAction(.moveToDisabledFolder, to: names)
            selection.value = []
        }
        Divider()
        Button("Move to Trash…", role: .destructive) {
            confirmingTrash.value = true
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
        } else if pack.isEnabled {
            Text("Enabled")
                .font(.caption)
                .foregroundStyle(.orange)
                .help("Loads but is shadowed or conflicts with the active package")
        } else {
            Text("Disabled")
                .font(.caption)
                .foregroundStyle(.secondary)
                .help("Listed as SCENERY_PACK_DISABLED in scenery_packs.ini")
        }
    }
}
