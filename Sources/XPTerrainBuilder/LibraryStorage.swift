import SwiftUI
import SceneryKit

/// Settings ▸ Storage's rows (RULINGS 2026-11-11k (2); the Library pane's
/// from #2007 until 11k retired Library mode): the data folder, then the
/// ONE disk budget (RULINGS 2026-11-10d; its default 11a/11h) that
/// everything the app keeps fits in, caches included, then Convert
/// existing tiles and the Caches line: one total, Clear… and Details…, the
/// per-cache list in its own window (`StorageSection`). One `StorageModel`
/// scan feeds them all. The Qt window's `O4_Qt_Library_Storage` holds the
/// same rows (`StorageRows`).
struct StorageSettingsRows: View {
    @EnvironmentObject var buildModel: BuildModel
    /// The app's one storage model (#2029): measured in the background,
    /// shown at once.
    private var storage: StorageModel { buildModel.storage }

    var body: some View {
        Section { DataFolderRow(model: storage) }
        Section { DiskBudgetSection(model: storage) }
        Section { ConvertTilesSection(run: buildModel.worldMigrate, autoMeasure: true) }
        Section { StorageTiersSection() }
        Section { CachesLine(model: storage) }
            .onAppear { storage.showShared(buildModel) }
    }
}

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

/// The disk budget, visible and editable (#2022): a slider from the
/// minimum (what is always kept) to the most (as much as fits while
/// keeping 50 GB free), a number field beside it, the stacked usage bar
/// and, while the slider moves, the line saying what that budget would
/// clear. Unset, the default applies, holds the current install (RULINGS
/// 2026-11-11h (1)) and Confirm records it; a budget below what is in use
/// asks "downgrade scenery to low res to fit?" with the bytes first
/// (Cancel keeps the old budget).
struct DiskBudgetSection: View {
    @EnvironmentObject var buildModel: BuildModel
    @ObservedObject var model: StorageModel
    @State private var field = ""
    @State private var gigabytes: Double = 0
    @State private var dragging = false
    @State private var asking: Int64?

    private var budget: O4StorageBudget? { model.scan?.budget }

    /// The slider's ends in GB (the engine's range; a degenerate one widens).
    private var range: ClosedRange<Double> {
        guard let budget else { return 0...1 }
        let low = Double(budget.minimumBytes ?? 0) / 1e9
        let high = Double(budget.maximumBytes ?? budget.budgetBytes) / 1e9
        return low...max(high, low + 1)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(O4StorageText.budgetTitle).bold()
            if let budget {
                let lines = O4StorageText.budgetLines(budget)
                Text(lines.line).fixedSize(horizontal: false, vertical: true)
                StorageUsageBar(budget: budget)
                sliderRow(budget)
                let held = O4StorageText.heldLine(budget)
                if !held.isEmpty {
                    Text(held).scaledFont(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                let notice = O4StorageText.rangeNotice(budget)
                ForEach([notice, lines.warning].filter { !$0.isEmpty }, id: \.self) { text in
                    Label(text, systemImage: "exclamationmark.triangle.fill")
                        .scaledFont(.caption).foregroundStyle(.orange)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            HStack {
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

    /// The labelled slider row with the number field, the slider's
    /// labelled ends, and the preview line while the slider moves.
    @ViewBuilder private func sliderRow(_ budget: O4StorageBudget) -> some View {
        let ends = O4StorageText.endLabels(budget)
        // One row (owner 2026-11-12, 1.0.495): the label left, the slider
        // filling the middle, the number field right; the label and field
        // keep their size so the row never wraps the lines above it.
        HStack(spacing: 8) {
            Text(O4StorageText.budgetField).fixedSize()
            Slider(value: $gigabytes, in: range) { editing in
                dragging = editing
                field = String(format: "%.0f", gigabytes)
                if !editing { submit() }
            }
            .labelsHidden()
            .frame(maxWidth: .infinity)
            TextField("", text: $field)
                .labelsHidden()
                .textFieldStyle(.roundedBorder)
                .multilineTextAlignment(.trailing)
                .frame(width: 70)
                .onSubmit(submit)
        }
        .disabled(model.isWorking || buildModel.isBuilding)
        HStack(alignment: .top) {
            Text(ends.min)
            Spacer()
            Text(ends.max).multilineTextAlignment(.trailing)
        }
        .scaledFont(.caption).foregroundStyle(.secondary)
        .fixedSize(horizontal: false, vertical: true)
        if dragging {
            Text(O4StorageText.previewText(budget, Int64(gigabytes * 1e9)))
                .scaledFont(.caption).fixedSize(horizontal: false, vertical: true)
        }
    }

    /// The slider and field show the budget that applies (the default
    /// when unset), inside the slider's range.
    private func showBudget() {
        guard let budget else { return }
        let applied = Double(budget.budgetBytes) / 1e9
        gigabytes = min(max(applied, range.lowerBound), range.upperBound)
        field = String(format: "%.0f", applied)
    }

    private func submit() {
        guard let typed = Double(field), typed > 0 else { return showBudget() }
        let bytes = Int64(typed * 1e9)
        if let budget, O4StorageText.needsDowngrade(budget, bytes) {
            asking = bytes
        } else {
            setBudget(typed)
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

/// What is in use by kind (#2022): one stacked bar and its legend.
struct StorageUsageBar: View {
    let budget: O4StorageBudget
    static let colors: [Color] = [.gray, .blue, .orange, .teal, .purple, .secondary]

    var body: some View {
        let parts = O4StorageText.barParts(budget)
        let total = max(1, parts.reduce(0) { $0 + $1.bytes })
        VStack(alignment: .leading, spacing: 2) {
            GeometryReader { geometry in
                HStack(spacing: 0) {
                    ForEach(Array(parts.enumerated()), id: \.offset) { index, part in
                        Rectangle().fill(Self.colors[index % Self.colors.count])
                            .frame(width: geometry.size.width * CGFloat(part.bytes) / CGFloat(total))
                    }
                }
            }
            .frame(height: 10)
            .clipShape(RoundedRectangle(cornerRadius: 3))
            HStack(spacing: 10) {
                ForEach(Array(parts.enumerated()), id: \.offset) { index, part in
                    HStack(spacing: 3) {
                        Circle().fill(Self.colors[index % Self.colors.count]).frame(width: 7, height: 7)
                        Text(part.legend)
                    }
                }
            }
            .scaledFont(.caption).foregroundStyle(.secondary)
        }
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
            } else if model.updating {
                Text(O4StorageText.updating).scaledFont(.caption).foregroundStyle(.secondary)
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
