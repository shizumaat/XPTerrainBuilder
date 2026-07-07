import SwiftUI
import SceneryKit

/// Right pane: whatever the map window is looking at (live as it moves),
/// in scenery_packs.ini load order (first wins), with kind icons, status
/// badges, drag-to-reorder, and the context-aware pack actions.
struct PackInspectorView: View {
    @EnvironmentObject var controller: AnalysisController
    let packs: [SceneryPack]
    // Selection is keyed by pack PATH — the List rows' identity. Keying by
    // name broke selection entirely (the gear menu never enabled) because
    // the ForEach identity and the tag disagreed.
    @StateObject private var selection = ViewState(Set<String>())

    private var affected: [SceneryPack] { packs }

    /// X-Plane load order: ini rank ascending (reorder override first, then
    /// the scanned iniIndex), unlisted packs last, names break ties.
    private var ordered: [SceneryPack] {
        let override = controller.iniOrderOverride
        func rank(_ pack: SceneryPack) -> Int {
            override?[pack.name] ?? pack.iniIndex ?? Int.max
        }
        return affected.sorted {
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
                            // simultaneousGesture: a plain onTapGesture
                            // would steal single clicks from selection.
                            .simultaneousGesture(TapGesture(count: 2).onEnded {
                                controller.zoomToPack(pack)
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

    /// "254 packages in view, 128.3 GB" — or, with rows selected,
    /// "3 of 254 selected, 8.3 GB".
    private var footerSummary: String {
        let selected = affected.filter { selection.value.contains($0.url.path) }
        if selected.isEmpty {
            let bytes = affected.reduce(Int64(0)) { $0 + $1.sizeBytes }
            let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
            return "\(affected.count) package\(affected.count == 1 ? "" : "s") in view, \(size)"
        }
        let bytes = selected.reduce(Int64(0)) { $0 + $1.sizeBytes }
        let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
        return "\(selected.count) of \(affected.count) selected, \(size)"
    }

    private func packRow(_ pack: SceneryPack) -> some View {
        HStack(spacing: 6) {
            statusDot(pack.status)
            PackKindIcon(kind: pack.kind)
            VStack(alignment: .leading, spacing: 1) {
                Text(pack.name)
                    .lineLimit(1)
                    .truncationMode(.middle)
                if let detail = packDetail(pack) {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
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
        // Reflect status changes on the map/inspector.
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(1))
            controller.refreshInstallation()
        }
    }
}
