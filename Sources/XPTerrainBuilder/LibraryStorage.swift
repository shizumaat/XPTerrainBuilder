import SwiftUI
import SceneryKit

/// Library mode's storage rows (#2007, owner 2026-11-11): the data folder,
/// then the ONE disk budget (RULINGS 2026-11-10d; its default 11a) that
/// everything the app keeps fits in, caches included, then — after the
/// patch library and Convert existing tiles — the Caches line: one total,
/// Clear… and Details…, the per-cache list in its own window
/// (`StorageSection`). One `StorageModel` scan feeds all three. The Qt
/// window's `O4_Qt_Library_Storage` holds the same rows.
struct DataFolderRow: View {
    @ObservedObject var model: StorageModel

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(O4StorageText.folderTitle).bold()
            Text(model.scan?.root ?? "—")
                .lineLimit(1).truncationMode(.middle)
                .textSelection(.enabled)
                .foregroundStyle(.secondary)
        }
    }
}

/// The disk budget, visible and editable. Unset, the default applies,
/// holds the current install (RULINGS 2026-11-11h (1)) and Confirm records
/// it; a budget below what is in use asks "downgrade scenery to low
/// res to fit?" with the bytes first (Cancel keeps the old budget).
struct DiskBudgetSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: StorageModel
    @State private var field = ""
    @State private var asking: Int64?

    private var budget: O4StorageBudget? { model.scan?.budget }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(O4StorageText.budgetTitle).bold()
            if let budget {
                let lines = O4StorageText.budgetLines(budget)
                Text(lines.line).fixedSize(horizontal: false, vertical: true)
                Text(O4StorageText.defaultLine(budget))
                    .scaledFont(.caption).foregroundStyle(.secondary)
                let held = O4StorageText.heldLine(budget)
                if !held.isEmpty {
                    Text(held).scaledFont(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if !lines.warning.isEmpty {
                    Label(lines.warning, systemImage: "exclamationmark.triangle.fill")
                        .scaledFont(.caption).foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            HStack {
                TextField(O4StorageText.budgetField, text: $field)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 90)
                    .onSubmit(submit)
                Button(O4StorageText.budgetSet, action: submit)
                    .disabled(Double(field).map { $0 <= 0 } ?? true)
                if budget?.budgetSet == true {
                    Button(O4StorageText.budgetUseDefault) { setBudget(0) }
                } else if let budget {
                    Button(O4StorageText.budgetConfirm) {
                        setBudget(Double(budget.budgetBytes) / 1e9)
                    }
                }
            }
            .disabled(model.isWorking || buildModel.isBuilding)
        }
        .help(O4StorageText.budgetHelp)
        .onAppear(perform: showBudget)
        .onChange(of: model.scan) { _, _ in showBudget() }
        .confirmationDialog(O4StorageText.downgradeTitle, isPresented: Binding(
            get: { asking != nil }, set: { if !$0 { cancel() } }), presenting: asking) { bytes in
            Button(O4StorageText.downgradeOk, role: .destructive) {
                asking = nil
                model.applyBudget(gigabytes: Double(bytes) / 1e9, buildModel)
            }
            Button("Cancel", role: .cancel) { cancel() }
        } message: { bytes in
            if let budget { Text(O4StorageText.downgradeMessage(budget, bytes)) }
        }
    }

    /// The field shows the budget that applies (the default when unset).
    private func showBudget() {
        guard let budget else { return }
        field = String(format: "%.0f", Double(budget.budgetBytes) / 1e9)
    }

    private func submit() {
        guard let gigabytes = Double(field), gigabytes > 0 else { return showBudget() }
        let bytes = Int64(gigabytes * 1e9)
        if let budget, O4StorageText.needsDowngrade(budget, bytes) {
            asking = bytes
        } else {
            setBudget(gigabytes)
        }
    }

    private func setBudget(_ gigabytes: Double) {
        buildModel.setConfigValue(StorageModel.budgetKey, to: .double(gigabytes))
        model.refresh(buildModel)
    }

    /// Cancel keeps the old budget.
    private func cancel() {
        asking = nil
        showBudget()
    }
}

/// Caches: one total, Clear… (every cache, asked first) and Details….
struct CachesLine: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: StorageModel
    @State private var details = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(O4StorageText.cachesTitle).bold()
                Spacer()
                Text(model.scan.map { Library.size($0.cacheBytes) } ?? "—").monospacedDigit()
            }
            .help(O4StorageText.cachesHelp)
            HStack {
                Button(O4StorageText.cachesClear) { model.askClearAll() }
                    .disabled(model.isWorking || buildModel.isBuilding || (model.scan?.cacheBytes ?? 0) == 0)
                Button(O4StorageText.cachesDetails) { details = true }
                Spacer()
                if model.isWorking { ProgressView().controlSize(.small) }
                Button { model.refresh(buildModel) } label: { Image(systemName: "arrow.clockwise") }
                    .help("Measure the data folder again")
                    .disabled(model.isWorking)
            }
            if !model.status.isEmpty {
                Text(model.status).scaledFont(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .modifier(StorageClearConfirm(model: model, buildModel: buildModel))
        .sheet(isPresented: $details) {
            StorageDetailsSheet(model: model).environmentObject(buildModel)
        }
    }
}

/// The per-cache list, out of the pane (owner 2026-11-11).
struct StorageDetailsSheet: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: StorageModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            Form { StorageSection(model: model) }
                .formStyle(.grouped)
                .modifier(StorageClearConfirm(model: model, buildModel: buildModel))
            Divider()
            HStack {
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
            }
            .padding(10)
        }
        .frame(minWidth: 520, minHeight: 480)
        .navigationTitle(O4StorageText.cachesDetailsTitle)
    }
}
