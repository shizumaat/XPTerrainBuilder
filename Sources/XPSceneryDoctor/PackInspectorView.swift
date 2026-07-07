import SwiftUI
import SceneryKit

/// Right pane: the packages in the current tile selection — or, with no
/// selection, whatever the map window is looking at (live as it moves) —
/// in scenery_packs.ini load order (first wins), with kind icons, status
/// badges, drag-to-reorder, and the context-aware pack actions.
struct PackInspectorView: View {
    @EnvironmentObject var controller: AnalysisController
    let packs: [SceneryPack]
    let isViewportMode: Bool
    @StateObject private var selection = ViewState(Set<String>()) // pack names

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
                Text("Drag to change X-Plane load order")
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
                    description: Text(isViewportMode
                        ? "No custom package covers the visible map area. Pan or zoom out — or click a tile to inspect it."
                        : "No custom package covers the selected tile\(controller.selectedTiles.count == 1 ? "" : "s").")
                )
            } else {
                List(selection: $selection.value) {
                    // Row identity by PATH: the same-named pack can appear
                    // installed and uninstalled at once. Selection stays by
                    // name (acting on both copies together is meaningful).
                    ForEach(ordered, id: \.url.path) { pack in
                        packRow(pack).tag(pack.name)
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
                .contextMenu(forSelectionType: String.self) { names in
                    packActionButtons(for: names.isEmpty ? selection.value : names)
                }

                Divider()
                HStack {
                    Text(footerSummary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
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
                    .disabled(selection.value.isEmpty || controller.isApplyingAction || controller.isRunning)
                    .help("Actions for the selected packages")
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(.bar)
            }
        }
    }

    /// "254 packages in view, 128.3 GB" — or, with rows selected,
    /// "3 of 254 selected, 8.3 GB".
    private var footerSummary: String {
        let selected = affected.filter { selection.value.contains($0.name) }
        if selected.isEmpty {
            let bytes = affected.reduce(Int64(0)) { $0 + $1.sizeBytes }
            let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
            return "\(affected.count) package\(affected.count == 1 ? "" : "s") \(isViewportMode ? "in view" : "in selection"), \(size)"
        }
        let bytes = selected.reduce(Int64(0)) { $0 + $1.sizeBytes }
        let size = ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
        return "\(selected.count) of \(affected.count) selected, \(size)"
    }

    private func packRow(_ pack: SceneryPack) -> some View {
        HStack(spacing: 6) {
            statusDot(pack.status)
            kindIcon(pack.kind)
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
            parts.append("Last modified: \(modified.formatted(date: .abbreviated, time: .omitted))")
        }
        return parts.isEmpty ? nil : parts.joined(separator: " — ")
    }

    /// Category icon, tinted to match the map legend.
    private func kindIcon(_ kind: PackKind) -> some View {
        let (symbol, color): (String, Color) = switch kind {
        case .airport: ("airplane.circle", .red)
        case .landmark: ("building.2", .blue)
        case .ortho: ("photo", .brown)
        case .mesh: ("mountain.2", .green)
        case .library: ("books.vertical", .purple)
        case .other: ("shippingbox", .secondary)
        }
        return Image(systemName: symbol)
            .font(.callout)
            .foregroundStyle(color)
            .frame(width: 18)
            .help(kind.rawValue)
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

    /// Same context-aware pattern as the duplicates table.
    @ViewBuilder
    private func packActionButtons(for names: Set<String>) -> some View {
        let selected = affected.filter { names.contains($0.name) }
        let enabled = selected.filter { $0.status == .enabled }.map { $0.name }
        let disabled = selected.filter { $0.status == .disabled }.map { $0.name }
        let uninstalled = selected.filter { $0.status == .uninstalled }.map { $0.name }

        if !disabled.isEmpty {
            Button("Enable\(disabled.count < names.count ? " (\(disabled.count))" : "")") {
                apply(.enable, to: disabled)
            }
        }
        if !enabled.isEmpty {
            Button("Disable\(enabled.count < names.count ? " (\(enabled.count))" : "")") {
                apply(.disable, to: enabled)
            }
        }
        if !uninstalled.isEmpty {
            Button("Install\(uninstalled.count < names.count ? " (\(uninstalled.count))" : "")") {
                apply(.install, to: uninstalled)
            }
        }
        let installed = enabled + disabled
        if !installed.isEmpty {
            Button("Uninstall\(installed.count < names.count ? " (\(installed.count))" : "")") {
                apply(.uninstall, to: installed)
            }
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
