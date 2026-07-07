import SwiftUI
import SceneryKit

/// Files no DSF, resource file or library export references — leftover ortho
/// imagery sets, dead .ter files, forgotten textures. Multi-select and Trash;
/// everything is recoverable from the Trash and tracked in Modifications.
struct UnusedResourcesView: View {
    @EnvironmentObject var controller: AnalysisController
    let groups: [UnusedResourceGroup]

    @StateObject private var selection = ViewState(Set<Row.ID>())
    @StateObject private var confirmingTrash = ViewState<[String]?>(nil)
    @StateObject private var sortOrder = ViewState([
        KeyPathComparator(\Row.sizeBytes, order: .reverse)
    ])

    struct Row: Identifiable {
        let id: String   // absolute path
        let packName: String
        let fileName: String
        let relativePath: String
        let sizeBytes: Int64
        let modified: Date
    }

    private var rows: [Row] {
        groups.flatMap { group in
            group.files.map { file in
                Row(
                    id: file.path,
                    packName: group.packName,
                    fileName: URL(fileURLWithPath: file.path).lastPathComponent,
                    relativePath: String(file.path.dropFirst(group.packPath.count + 1)),
                    sizeBytes: file.sizeBytes,
                    modified: file.modifiedDate ?? .distantPast
                )
            }
        }
        .sorted(using: sortOrder.value)
    }

    private var totalBytes: Int64 { groups.reduce(0) { $0 + $1.totalBytes } }

    private var selectedPaths: [String] {
        rows.filter { selection.value.contains($0.id) }.map { $0.id }
    }

    var body: some View {
        if groups.isEmpty {
            ContentUnavailableView(
                controller.isRunning ? "Analyzing…" : "No Unused Files Found",
                systemImage: controller.isRunning ? "magnifyingglass" : "checkmark.seal",
                description: Text(controller.isRunning
                    ? "Unreferenced files will appear here once the scan reaches them."
                    : "Every image and terrain file is referenced by the packs that ship it (packs with unreadable DSFs are skipped — see their info findings).")
            )
        } else {
            VStack(spacing: 0) {
                table
                Divider()
                actionBar
            }
            .confirmationDialog(
                trashConfirmationTitle,
                isPresented: Binding(
                    get: { confirmingTrash.value != nil },
                    set: { if !$0 { confirmingTrash.value = nil } }
                )
            ) {
                Button("Move to Trash", role: .destructive) {
                    if let paths = confirmingTrash.value {
                        controller.trashUnusedFiles(paths)
                        selection.value = []
                    }
                    confirmingTrash.value = nil
                }
            } message: {
                Text("Files move to the Trash (recoverable) and are listed under Window ▸ Modifications, where Revert puts them back. Double-check anything you're unsure about with Reveal in Finder first.")
            }
        }
    }

    private var trashConfirmationTitle: String {
        let paths = confirmingTrash.value ?? []
        let size = rows.filter { paths.contains($0.id) }.reduce(Int64(0)) { $0 + $1.sizeBytes }
        return "Move \(paths.count) file\(paths.count == 1 ? "" : "s") (\(ByteCountFormatter.string(fromByteCount: size, countStyle: .file))) to the Trash?"
    }

    private var table: some View {
        Table(rows, selection: $selection.value, sortOrder: $sortOrder.value) {
            TableColumn("Package", value: \.packName) { row in
                Text(row.packName)
            }
            .width(min: 120, ideal: 200)

            TableColumn("File", value: \.relativePath) { row in
                Text(row.relativePath)
                    .truncationMode(.head)
                    .help(row.id)
            }

            TableColumn("Size", value: \.sizeBytes) { row in
                Text(ByteCountFormatter.string(fromByteCount: row.sizeBytes, countStyle: .file))
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .width(80)

            TableColumn("Modified", value: \.modified) { row in
                Text(row.modified == .distantPast
                     ? "—"
                     : row.modified.formatted(date: .abbreviated, time: .omitted))
                    .foregroundStyle(.secondary)
            }
            .width(90)
        }
        .contextMenu(forSelectionType: Row.ID.self) { ids in
            let paths = ids.isEmpty ? selectedPaths : Array(ids)
            Button("Move to Trash…", role: .destructive) {
                confirmingTrash.value = paths
            }
            Button("Reveal in Finder") {
                NSWorkspace.shared.activateFileViewerSelecting(paths.map { URL(fileURLWithPath: $0) })
            }
        }
        .onDeleteCommand {
            if !selectedPaths.isEmpty { confirmingTrash.value = selectedPaths }
        }
    }

    private var actionBar: some View {
        HStack {
            if controller.isFixing {
                ProgressView().controlSize(.small)
                Text("Moving to Trash…").foregroundStyle(.secondary)
            } else {
                Text(summaryText).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Trash Selected") {
                confirmingTrash.value = selectedPaths
            }
            .disabled(selectedPaths.isEmpty || controller.isFixing)
            Button("Trash All (\(rows.count))") {
                confirmingTrash.value = rows.map { $0.id }
            }
            .disabled(rows.isEmpty || controller.isFixing)
            .help("Move every listed file to the Trash (files here have already passed the whole-install cross-check)")
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    private var summaryText: String {
        let total = ByteCountFormatter.string(fromByteCount: totalBytes, countStyle: .file)
        if selectedPaths.isEmpty {
            return "\(rows.count) unreferenced files across \(groups.count) package\(groups.count == 1 ? "" : "s") — \(total) reclaimable"
        }
        let selectedSize = rows.filter { selection.value.contains($0.id) }.reduce(Int64(0)) { $0 + $1.sizeBytes }
        return "\(selectedPaths.count) selected (\(ByteCountFormatter.string(fromByteCount: selectedSize, countStyle: .file)))"
    }
}
