import SwiftUI
import SceneryKit

/// Every file XPTerrainBuilder has modified, grouped by scenery package,
/// with per-package and per-file revert.
struct ModificationsWindow: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var selection = ViewState(Set<ModificationRecord.ID>())

    private var selectedRecords: [ModificationRecord] {
        controller.modifications.filter { selection.value.contains($0.id) }
    }

    /// Package name derived from the record's path under Custom Scenery.
    static func packName(for record: ModificationRecord) -> String {
        let components = URL(fileURLWithPath: record.filePath).pathComponents
        for (i, component) in components.enumerated()
            where component == "Custom Scenery" || component == "Custom Scenery (Disabled)" {
            if i + 1 < components.count { return components[i + 1] }
        }
        return "Other"
    }

    private var sections: [(pack: String, records: [ModificationRecord])] {
        var byPack: [String: [ModificationRecord]] = [:]
        for record in controller.modifications {
            byPack[Self.packName(for: record), default: []].append(record)
        }
        return byPack
            .map { (pack: $0.key, records: $0.value.sorted { $0.date > $1.date }) }
            .sorted { $0.pack.lowercased() < $1.pack.lowercased() }
    }

    var body: some View {
        Group {
            if controller.modifications.isEmpty {
                ContentUnavailableView(
                    "No Modified Files",
                    systemImage: "checkmark.shield",
                    description: Text("Files changed by Apply Fix appear here, grouped by package. Content edits keep a backup beside the original; renames record the old name; trashed files sit in the Trash — all revertible.")
                )
            } else {
                VStack(spacing: 0) {
                    List(selection: $selection.value) {
                        ForEach(sections, id: \.pack) { section in
                            Section {
                                ForEach(section.records) { record in
                                    recordRow(record).tag(record.id)
                                }
                            } header: {
                                HStack {
                                    Text("\(section.pack) (\(section.records.count))")
                                    Spacer()
                                    Button("Revert All in Package") {
                                        controller.revertModifications(section.records)
                                    }
                                    .buttonStyle(.link)
                                    .font(.caption)
                                    .disabled(controller.isFixing)
                                }
                            }
                        }
                    }
                    .listStyle(.inset)
                    .contextMenu(forSelectionType: ModificationRecord.ID.self) { ids in
                        let records = controller.modifications.filter { ids.contains($0.id) }
                        Button("Revert to Original") {
                            controller.revertModifications(records)
                        }
                        Button("Reveal in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting(
                                records.map { URL(fileURLWithPath: $0.backupPath) }
                            )
                        }
                    }

                    Divider()
                    actionBar
                }
            }
        }
        .frame(minWidth: 620, minHeight: 320)
        .navigationTitle("Modifications")
        .navigationSubtitle("\(controller.modifications.count) modified file\(controller.modifications.count == 1 ? "" : "s") in \(sections.count) package\(sections.count == 1 ? "" : "s")")
        .task {
            controller.loadModifications()
        }
    }

    private func recordRow(_ record: ModificationRecord) -> some View {
        HStack(spacing: 8) {
            Image(systemName: iconName(for: record))
                .foregroundStyle(.secondary)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 1) {
                Text(URL(fileURLWithPath: record.filePath).lastPathComponent)
                    .help(record.filePath)
                Text(record.summary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            Text(record.checkID)
                .font(.caption2.monospaced())
                .foregroundStyle(.tertiary)
            Text(record.date, format: .dateTime.day().month().hour().minute())
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }

    private func iconName(for record: ModificationRecord) -> String {
        if record.summary.hasPrefix("Renamed") { return "character.cursor.ibeam" }
        if record.summary.hasPrefix("Moved to Trash") { return "trash" }
        if record.summary.hasPrefix("Converted") { return "photo" }
        return "pencil"
    }

    private var actionBar: some View {
        HStack {
            if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Working…").foregroundStyle(.secondary)
            } else {
                Text("Revert restores the original: from its backup, the Trash, or by renaming back.")
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            Button("Revert Selected") {
                controller.revertModifications(selectedRecords)
                selection.value = []
            }
            .disabled(selectedRecords.isEmpty || controller.isFixing)
            Button("Revert All (\(controller.modifications.count))") {
                controller.revertModifications(controller.modifications)
                selection.value = []
            }
            .disabled(controller.modifications.isEmpty || controller.isFixing)
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }
}
