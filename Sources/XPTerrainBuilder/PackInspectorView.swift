import SwiftUI
import SceneryKit

/// Right pane: whatever the map window is looking at (live as it moves),
/// in scenery_packs.ini load order (first wins), with kind icons, status
/// badges, drag-to-reorder, and the context-aware pack actions.
struct PackInspectorView: View {
    @EnvironmentObject var controller: AnalysisController
    /// Leaf model (lore #13): size batches stream during runs, and only
    /// this view should re-render for them — never the map canvas.
    @EnvironmentObject var packSizes: PackSizesModel
    let packs: [SceneryPack]
    // Selection is keyed by pack PATH — the List rows' identity. Keying by
    // name broke selection entirely (the gear menu never enabled) because
    // the ForEach identity and the tag disagreed.
    @StateObject private var selection = ViewState(Set<String>())

    private var affected: [SceneryPack] { packs }

    /// X-Plane load order: ini rank ascending (reorder override first, then
    /// the scanned iniIndex), unlisted packs last, names break ties.
    private var ordered: [SceneryPack] {
        Self.ordered(packs: affected, override: controller.iniOrderOverride)
    }

    /// Static so the double-click hook can recompute the CURRENT row order
    /// at click time (its stored closure may belong to a recycled row).
    static func ordered(packs: [SceneryPack], override: [String: Int]?) -> [SceneryPack] {
        func rank(_ pack: SceneryPack) -> Int {
            override?[pack.name] ?? pack.iniIndex ?? Int.max
        }
        return packs.sorted {
            (rank($0), $0.name.lowercased()) < (rank($1), $1.name.lowercased())
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Available Packages")
                    .font(.headline)
                Text("Drag to change X-Plane load order — double-click to show on the map")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .help("Packs higher in the list load first and win conflicts. Reordering rewrites scenery_packs.ini, moving each pack only as far as needed.")
            Divider()
            if affected.isEmpty {
                ContentUnavailableView(
                    "No Custom Scenery Here",
                    systemImage: "square.dashed",
                    description: Text("No custom package covers the visible map area. Pan or zoom out to find some.")
                )
            } else {
                List(selection: $selection.value) {
                    // Row identity AND selection by PATH: unique even when
                    // the same-named pack exists installed and uninstalled.
                    ForEach(ordered, id: \.url.path) { pack in
                        packRow(pack)
                            .tag(pack.url.path)
                            // Native double-click: a zero-impact probe in the
                            // row hooks the List's backing NSTableView and
                            // sets its doubleAction — the standard AppKit
                            // mechanism, so selection and drag are untouched
                            // (SwiftUI gestures all interfered one way or
                            // another). The pack is resolved at CLICK time
                            // from the controller so recycled rows can't
                            // capture a stale ordering.
                            .background(TableDoubleClickHook { [weak controller] row in
                                guard let controller else { return }
                                let current = Self.ordered(
                                    packs: controller.viewportPacks,
                                    override: controller.iniOrderOverride)
                                guard current.indices.contains(row) else { return }
                                controller.zoomToPack(current[row])
                            })
                    }
                    .onMove { source, destination in
                        var names = ordered.map { $0.name }
                        names.move(fromOffsets: source, toOffset: destination)
                        // Uninstalled packs have no ini line to reorder.
                        let installed = Set(affected.filter { $0.isInstalled }.map { $0.name })
                        controller.reorderPacks(names.filter { installed.contains($0) })
                    }
                }
                .listStyle(.inset)
                .contextMenu(forSelectionType: String.self) { paths in
                    packActionButtons(for: paths.isEmpty ? selection.value : paths)
                }

                Divider()
                // Same height and type size as the results pane's bottom bar.
                HStack {
                    Text(footerSummary)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Spacer()
                    // Pack actions (Enable/Disable/Install/Uninstall/Reveal)
                    // for the selected rows; enabled once rows are selected.
                    Menu {
                        packActionButtons(for: selection.value)
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .disabled(selection.value.isEmpty || controller.isApplyingAction)
                    .help("Actions for the selected packages (folder moves wait for the analysis; Enable/Disable work anytime)")
                }
                .font(.callout)
                .padding(.horizontal, 12)
                .frame(height: ResultsPane.bottomBarHeight)
                .background(.bar)
            }
        }
    }

    /// Exact size once the pack has been analyzed, "~estimate" until then
    /// (the scanner's number is depth-limited), "calculating…" when even
    /// the estimate is empty.
    private func sizeLabel(_ pack: SceneryPack) -> String {
        if let exact = packSizes.exact[pack.name] {
            return ByteCountFormatter.string(fromByteCount: exact, countStyle: .file)
        }
        if pack.sizeBytes > 0 {
            return "~" + ByteCountFormatter.string(fromByteCount: pack.sizeBytes, countStyle: .file)
        }
        return "…"
    }

    private func totalBytes(_ packs: [SceneryPack]) -> (bytes: Int64, allExact: Bool) {
        var bytes: Int64 = 0
        var allExact = true
        for pack in packs {
            if let exact = packSizes.exact[pack.name] {
                bytes += exact
            } else {
                bytes += pack.sizeBytes
                allExact = false
            }
        }
        return (bytes, allExact)
    }

    /// "254 packages in view, 128.3 GB" — or, with rows selected,
    /// "3 of 254 selected, 8.3 GB". "≈" while any size is still estimated.
    private var footerSummary: String {
        let selected = affected.filter { selection.value.contains($0.url.path) }
        if selected.isEmpty {
            let (bytes, allExact) = totalBytes(affected)
            let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
            return "\(affected.count.formatted()) package\(affected.count == 1 ? "" : "s") in view, \(allExact ? "" : "≈")\(size)"
        }
        let (bytes, allExact) = totalBytes(selected)
        let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
        return "\(selected.count.formatted()) of \(affected.count.formatted()) selected, \(allExact ? "" : "≈")\(size)"
    }

    private func packRow(_ pack: SceneryPack) -> some View {
        HStack(spacing: 6) {
            statusDot(pack.status)
            PackKindIcon(kind: pack.kind)
            VStack(alignment: .leading, spacing: 1) {
                Text(pack.name)
                    .lineLimit(1)
                    .truncationMode(.middle)
                HStack(spacing: 6) {
                    if let detail = packDetail(pack) {
                        Text(detail)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                    Spacer(minLength: 4)
                    // Exact size once analyzed; "~" marks the scanner's
                    // depth-limited estimate until then.
                    Text(sizeLabel(pack))
                        .monospacedDigit()
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
            }
            Spacer(minLength: 4)
            Image(systemName: "line.3.horizontal")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .help("Drag to change load order")
        }
        .help(pack.url.path)
    }

    /// "KBNA, Nashville, USA — Last modified: Jul 7, 2026". Missing data
    /// points are simply left out; multi-airport packs list ICAOs instead
    /// of one city.
    private func packDetail(_ pack: SceneryPack) -> String? {
        var parts: [String] = []
        if pack.airports.count == 1, let (icao, info) = pack.airports.first {
            var place = [icao]
            if let city = info.city { place.append(city) }
            if let country = info.country { place.append(country) }
            parts.append(place.joined(separator: ", "))
        } else if !pack.airports.isEmpty {
            parts.append(pack.airports.keys.sorted().prefix(6).joined(separator: " "))
        }
        if let modified = pack.modifiedDate {
            parts.append(modified.formatted(date: .abbreviated, time: .shortened))
        }
        return parts.isEmpty ? nil : parts.joined(separator: " — ")
    }

    @ViewBuilder
    private func statusDot(_ status: PackStatus) -> some View {
        switch status {
        case .enabled:
            Circle().fill(.green).frame(width: 7, height: 7)
        case .disabled:
            Circle().fill(.orange).frame(width: 7, height: 7)
        case .uninstalled:
            Circle().stroke(.secondary, lineWidth: 1).frame(width: 7, height: 7)
        }
    }

    /// Same context-aware pattern as the duplicates table. `paths` are the
    /// selected rows' pack paths.
    @ViewBuilder
    private func packActionButtons(for paths: Set<String>) -> some View {
        let selected = affected.filter { paths.contains($0.url.path) }
        let enabled = selected.filter { $0.status == .enabled }.map { $0.name }
        let disabled = selected.filter { $0.status == .disabled }.map { $0.name }
        let uninstalled = selected.filter { $0.status == .uninstalled }.map { $0.name }

        if !disabled.isEmpty {
            Button("Enable\(disabled.count < selected.count ? " (\(disabled.count))" : "")") {
                apply(.enable, to: disabled)
            }
        }
        if !enabled.isEmpty {
            Button("Disable\(enabled.count < selected.count ? " (\(enabled.count))" : "")") {
                apply(.disable, to: enabled)
            }
        }
        // Folder-moving actions can't run mid-analysis (files are being
        // read); ini-only enable/disable above stay available.
        if !uninstalled.isEmpty {
            Button("Install\(uninstalled.count < selected.count ? " (\(uninstalled.count))" : "")") {
                apply(.install, to: uninstalled)
            }
            .disabled(controller.isRunning)
        }
        let installed = enabled + disabled
        if !installed.isEmpty {
            Button("Uninstall\(installed.count < selected.count ? " (\(installed.count))" : "")") {
                apply(.uninstall, to: installed)
            }
            .disabled(controller.isRunning)
        }
        if !selected.isEmpty {
            Divider()
            Button("Reveal in Finder") {
                NSWorkspace.shared.activateFileViewerSelecting(selected.map { $0.url })
            }
        }
    }

    private func apply(_ action: PackAction, to names: [String]) {
        controller.applyPackAction(action, to: names)
        // Ini-only actions patch the model in memory; folder moves still
        // need a rescan to reflect the new disk layout.
        guard !action.isIniOnly else { return }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(1))
            controller.refreshInstallation()
        }
    }
}

/// Zero-sized, click-transparent probe that finds the SwiftUI List's backing
/// NSTableView and installs the standard AppKit `doubleAction` on it — the
/// native double-click mechanism, so it can't interfere with selection or
/// drag the way SwiftUI gestures do. The clicked row index comes from the
/// table itself at event time.
struct TableDoubleClickHook: NSViewRepresentable {
    let action: (Int) -> Void

    func makeNSView(context: Context) -> ProbeView {
        let view = ProbeView()
        view.action = action
        return view
    }

    func updateNSView(_ view: ProbeView, context: Context) {
        view.action = action
        view.hookIfNeeded()
    }

    final class ProbeView: NSView {
        var action: ((Int) -> Void)?
        private weak var table: NSTableView?

        /// Never participate in hit testing — the probe must be invisible
        /// to clicks or it would recreate the problem it solves.
        override func hitTest(_ point: NSPoint) -> NSView? { nil }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            hookIfNeeded()
        }

        func hookIfNeeded() {
            guard window != nil else { return }
            var view: NSView? = self
            while let current = view, !(current is NSTableView) { view = current.superview }
            guard let found = view as? NSTableView else { return }
            // Rows recycle, so whichever probe hooked last owns the (weak)
            // target; if it deallocates, the next row render re-hooks here.
            table = found
            found.target = self
            found.doubleAction = #selector(rowDoubleClicked(_:))
        }

        @objc private func rowDoubleClicked(_ sender: Any?) {
            guard let row = table?.clickedRow, row >= 0 else { return }
            action?(row)
        }
    }
}
