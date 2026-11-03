import SwiftUI
import SceneryKit

/// Settings ▸ Storage (#1724): every folder of the data folder with the
/// space deleting it frees and when it was last used, a Clear button per
/// cache, and "Clear files not used for…" across every cache. The engine's
/// `storage_*` commands walk the folders and delete
/// (`Ortho4XP/src/o4_engine/storage.py`); the Qt window's
/// `O4_Qt_Settings_Storage.StorageSection` shows the same rows. Built
/// tiles and patches are listed and never cleared here; every clear asks
/// first and names the space it frees.
@MainActor
final class StorageModel: ObservableObject {
    @Published var scan: O4StorageScan?
    @Published var isWorking = false
    @Published var status = ""
    /// A clear the user is being asked to confirm.
    @Published var pending: PendingClear?

    struct PendingClear: Identifiable {
        let id = UUID()
        let title: String
        let message: String
        let kinds: [String]
        let olderThanDays: Double?
    }

    static let ageChoices: [Double] = [30, 60, 90, 180, 365]

    func refresh(_ buildModel: BuildModel) {
        guard let client = buildModel.libraryContext()?.client else {
            status = "The engine is not running."
            return
        }
        isWorking = true
        status = "Measuring the data folder…"
        Task {
            do {
                scan = try await client.storageScan()
                status = ""
            } catch {
                status = "\(error)"
            }
            isWorking = false
        }
    }

    /// One cache: its size is already measured, so ask straight away.
    func askClear(_ store: O4StorageStore) {
        pending = PendingClear(
            title: "Clear \(store.label)?",
            message: "This frees up to \(Library.size(store.bytes)). \(store.note)",
            kinds: [store.kind], olderThanDays: nil)
    }

    /// Every cache's files not used for `days`: a dry run first, so the
    /// confirmation names the space it frees.
    func askClearOlder(than days: Double, _ buildModel: BuildModel) {
        guard let client = buildModel.libraryContext()?.client else { return }
        isWorking = true
        status = "Measuring what would go…"
        Task {
            do {
                let preview = try await client.storageClear(kinds: [], olderThanDays: days, dryRun: true)
                status = ""
                if preview.files == 0 {
                    status = "No cache file is older than \(Int(days)) days."
                } else {
                    pending = PendingClear(
                        title: "Clear cache files not used for \(Int(days)) days?",
                        message: "This deletes \(preview.files) file(s) and frees \(Library.size(preview.freedBytes)). "
                            + "Built tiles and airport patches are kept.",
                        kinds: [], olderThanDays: days)
                }
            } catch {
                status = "\(error)"
            }
            isWorking = false
        }
    }

    func confirm(_ clear: PendingClear, _ buildModel: BuildModel) {
        guard let client = buildModel.libraryContext()?.client else { return }
        isWorking = true
        status = "Clearing…"
        Task {
            do {
                let done = try await client.storageClear(
                    kinds: clear.kinds, olderThanDays: clear.olderThanDays, dryRun: false)
                status = "Freed \(Library.size(done.freedBytes)) in \(done.files) file(s)."
                    + (done.stopped ? " A build started, so the rest was kept." : "")
            } catch {
                status = "\(error)"
            }
            isWorking = false
            refresh(buildModel)
        }
    }
}

/// The Storage pane's sections, above its two setting rows.
struct StorageSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var model = StorageModel()
    @State private var olderThan: Double = 90

    var body: some View {
        Section("Data Folder") {
            if let scan = model.scan {
                LabeledContent("Folder") {
                    Text(scan.root).textSelection(.enabled).lineLimit(1).truncationMode(.middle)
                }
                LabeledContent("Caches", value: Library.size(scan.cacheBytes))
                LabeledContent("Your tiles and patches", value: Library.size(scan.keptBytes))
                if scan.measured != "private" {
                    Text("Sizes are allocated bytes: this disk cannot report shared (cloned) blocks.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            HStack {
                Button("Refresh") { model.refresh(buildModel) }
                    .disabled(model.isWorking)
                if model.isWorking { ProgressView().controlSize(.small) }
                Text(model.status).font(.caption).foregroundStyle(.secondary)
            }
        }
        .onAppear { if model.scan == nil { model.refresh(buildModel) } }
        .confirmationDialog(model.pending?.title ?? "", isPresented: Binding(
            get: { model.pending != nil }, set: { if !$0 { model.pending = nil } }),
            presenting: model.pending) { clear in
            Button("Clear", role: .destructive) { model.confirm(clear, buildModel) }
            Button("Cancel", role: .cancel) {}
        } message: { clear in
            Text(clear.message)
        }
        if let scan = model.scan {
            Section("Caches") {
                ForEach(scan.stores.filter(\.isCache)) { store in
                    StorageRow(store: store) { model.askClear(store) }
                        .disabled(model.isWorking || buildModel.isBuilding)
                }
                HStack {
                    Picker("Clear cache files not used for", selection: $olderThan) {
                        ForEach(StorageModel.ageChoices, id: \.self) { days in
                            Text(days >= 365 ? "1 year" : "\(Int(days)) days").tag(days)
                        }
                    }
                    Button("Clear…") { model.askClearOlder(than: olderThan, buildModel) }
                        .disabled(model.isWorking || buildModel.isBuilding)
                }
            }
            Section("Kept") {
                ForEach(scan.stores.filter { !$0.isCache }) { store in
                    StorageRow(store: store, clear: nil)
                }
            }
        }
    }
}

/// One store: label and note, size, last use, and Clear… for a cache.
private struct StorageRow: View {
    let store: O4StorageStore
    let clear: (() -> Void)?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text(store.label)
                Text(store.note).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Library.size(store.bytes)).monospacedDigit()
                Text("Last used \(Library.date(store.lastUsed))")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let clear {
                Button("Clear…", action: clear).disabled(store.files == 0)
            }
        }
        .help(store.path)
    }
}
