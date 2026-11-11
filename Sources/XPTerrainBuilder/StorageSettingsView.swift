import SwiftUI
import SceneryKit

/// Settings ▸ Storage ▸ Caches ▸ Details… (#1724; RULINGS 2026-11-11k; its
/// own window since #2007): every folder of the data folder with the
/// space deleting it frees and when it was last used, a Clear button per
/// cache, and "Clear files not used for…" across every cache. Settings'
/// data folder, disk budget and Caches line read the same model
/// (`LibraryStorage.swift`). The engine's
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
        /// "Make all low-res again" rather than a deletion (#1992).
        var lowRes = false
    }

    static let ageChoices: [Double] = [30, 60, 90, 180, 365]
    /// The one disk budget's setting (`storage_budget.SETTING`).
    static let budgetKey = "storage_budget_gb"

    /// The Caches line's Clear…: every cache, its measured total.
    func askClearAll() {
        guard let scan else { return }
        pending = PendingClear(title: O4StorageText.clearAllTitle,
                               message: O4StorageText.clearAllMessage(scan.cacheBytes),
                               kinds: [], olderThanDays: nil)
    }

    /// The disk budget lowered below what is in use, confirmed (#2007):
    /// the budget is set, then the automatic cleanup's budget hold
    /// (`storage_budget.hold`) clears to fit, caches first.
    func applyBudget(gigabytes: Double, _ buildModel: BuildModel) {
        buildModel.setConfigValue(Self.budgetKey, to: .double(gigabytes))
        guard let client = buildModel.libraryContext()?.client else { return }
        isWorking = true
        status = "Fitting the new budget…"
        Task {
            do {
                let done = try await client.storageAutoClean()
                status = "Freed \(Library.size(done.freedBytes)) in \(done.files) file(s)."
                    + (done.stopped ? " A build started, so the rest was kept." : "")
            } catch {
                status = "\(error)"
            }
            isWorking = false
            refresh(buildModel)
        }
    }

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

    /// "Make all low-res again" (#1992 §7): a dry run first, so the
    /// confirmation names the space it frees; pins are untouched.
    func askMakeLowRes(_ buildModel: BuildModel) {
        guard let client = buildModel.libraryContext()?.client else { return }
        isWorking = true
        status = "Measuring what would go…"
        Task {
            do {
                let preview = try await client.imageryMakeAllLowRes(dryRun: true)
                status = ""
                if preview.downgraded == 0 {
                    status = O4OnDemandText.makeLowResNone
                } else {
                    pending = PendingClear(
                        title: O4OnDemandText.makeLowResTitle + "?",
                        message: O4OnDemandText.makeLowResMessage(
                            freedBytes: preview.freedBytes, textures: preview.downgraded),
                        kinds: [], olderThanDays: nil, lowRes: true)
                }
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
                    // Sharp imagery is made low-res, not deleted (#1992).
                    let sharp = (preview.kinds?["ondemand"] ?? 0) > 0
                    pending = PendingClear(
                        title: "Clear cache files not used for \(Int(days)) days?",
                        message: "This deletes \(preview.files) file(s) and frees \(Library.size(preview.freedBytes)). "
                            + "Built tiles and airport patches are kept."
                            + (sharp ? " " + O4OnDemandText.olderSharpNote : ""),
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
        if clear.lowRes { return makeLowRes(client, buildModel) }
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

extension StorageModel {
    fileprivate func makeLowRes(_ client: OrthoEngineClient, _ buildModel: BuildModel) {
        isWorking = true
        status = "Making imagery low-res again…"
        Task {
            do {
                let done = try await client.imageryMakeAllLowRes(dryRun: false)
                status = "Freed \(Library.size(done.freedBytes)) in \(done.downgraded) texture(s)."
                    + (done.stopped ? " A build started, so the rest was kept." : "")
            } catch {
                status = "\(error)"
            }
            isWorking = false
            refresh(buildModel)
        }
    }
}

/// The confirmation every clear asks first (the pane and the details).
struct StorageClearConfirm: ViewModifier {
    @ObservedObject var model: StorageModel
    let buildModel: BuildModel

    func body(content: Content) -> some View {
        content.confirmationDialog(model.pending?.title ?? "", isPresented: Binding(
            get: { model.pending != nil }, set: { if !$0 { model.pending = nil } }),
            presenting: model.pending) { clear in
            Button(clear.lowRes ? O4OnDemandText.makeLowResTitle : "Clear", role: .destructive) {
                model.confirm(clear, buildModel)
            }
            Button("Cancel", role: .cancel) {}
        } message: { clear in
            Text(clear.message)
        }
    }
}

/// The details window's sections (Settings ▸ Storage ▸ Caches ▸ Details…).
struct StorageSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: StorageModel
    @State private var olderThan: Double = 90

    var body: some View {
        Section("Data Folder") {
            if let scan = model.scan {
                LabeledContent("Folder") {
                    Text(scan.root).textSelection(.enabled).lineLimit(1).truncationMode(.middle)
                }
                LabeledContent("Caches", value: Library.size(scan.cacheBytes))
                    .help(O4StorageText.cachesHelp)
                LabeledContent("Your tiles and patches", value: Library.size(scan.keptBytes))
                    .help(O4StorageText.keptHelp)
                if let installed = scan.installed {
                    // X-Plane's installed tiles, wherever they live (owner, 1.0.480).
                    LabeledContent(O4StorageText.installedTitle) {
                        Text(O4StorageText.installedLines(installed).joined(separator: "\n"))
                            .multilineTextAlignment(.trailing)
                    }
                    .help(O4StorageText.installedHelp)
                }
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
        if let scan = model.scan {
            Section("Caches") {
                ForEach(scan.stores.filter(\.isCache)) { store in
                    // Sharp imagery is made low-res, never deleted (#1992).
                    StorageRow(store: store) {
                        if store.isOnDemand { model.askMakeLowRes(buildModel) } else { model.askClear(store) }
                    }
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
                if store.isOnDemand {
                    // The favorites, inside the budget (#1992 §7): their own
                    // line; the warning when the tiles do not fit even low-res.
                    Text(O4OnDemandText.pinsText(bytes: store.pinnedBytes ?? 0,
                                                 files: store.pinnedFiles ?? 0,
                                                 cores: store.coreFiles ?? 0))
                        .font(.caption).foregroundStyle(.secondary)
                    let warning = O4StorageText.ondemandWarning(store)
                    if !warning.isEmpty {
                        Text(warning).font(.caption).foregroundStyle(.orange)
                    }
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Library.size(store.bytes)).monospacedDigit()
                Text("Last used \(Library.date(store.lastUsed))")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let clear {
                Button(store.isOnDemand ? O4OnDemandText.makeLowResTitle + "…" : "Clear…",
                       action: clear).disabled(store.files == 0)
            }
        }
        .help(store.path)
    }
}
