import SwiftUI
import SceneryKit

/// Every file XPScenery Doctor has modified, with the option to restore the
/// .xpsd-backup originals — individually or all at once.
struct ModificationsWindow: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var selection = ViewState(Set<ModificationRecord.ID>())

    private var selectedRecords: [ModificationRecord] {
        controller.modifications.filter { selection.value.contains($0.id) }
    }

    var body: some View {
        Group {
            if controller.modifications.isEmpty {
                ContentUnavailableView(
                    "No Modified Files",
                    systemImage: "checkmark.shield",
                    description: Text("Files edited by Apply Fix appear here. Every edit keeps a backup of the original, so it can be reverted at any time.")
                )
            } else {
                VStack(spacing: 0) {
                    Table(controller.modifications, selection: $selection.value) {
                        TableColumn("File") { record in
                            Text(URL(fileURLWithPath: record.filePath).lastPathComponent)
                                .help(record.filePath)
                        }
                        .width(min: 140, ideal: 200)

                        TableColumn("Change") { record in
                            Text(record.summary)
                                .foregroundStyle(.secondary)
                        }

                        TableColumn("Check") { record in
                            Text(record.checkID)
                                .font(.caption.monospaced())
                                .foregroundStyle(.tertiary)
                        }
                        .width(60)

                        TableColumn("Date") { record in
                            Text(record.date, format: .dateTime.day().month().hour().minute())
                                .foregroundStyle(.secondary)
                        }
                        .width(130)
                    }
                    .contextMenu(forSelectionType: ModificationRecord.ID.self) { ids in
                        let records = controller.modifications.filter { ids.contains($0.id) }
                        Button("Revert to Original") {
                            controller.revertModifications(records)
                        }
                        Button("Reveal in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting(
                                records.map { URL(fileURLWithPath: $0.filePath) }
                            )
                        }
                    }

                    Divider()
                    actionBar
                }
            }
        }
        .frame(minWidth: 560, minHeight: 300)
        .navigationTitle("Modifications")
        .navigationSubtitle("\(controller.modifications.count) modified file\(controller.modifications.count == 1 ? "" : "s")")
        .task {
            controller.loadModifications()
        }
    }

    private var actionBar: some View {
        HStack {
            if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Working…").foregroundStyle(.secondary)
            } else {
                Text("Reverting restores the .xpsd-backup original and removes the backup.")
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
