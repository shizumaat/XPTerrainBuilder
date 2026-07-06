import SwiftUI
import SceneryKit

/// Right pane: the packages affecting the current tile selection, grouped
/// by kind, with status badges and the context-aware pack actions.
struct PackInspectorView: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var selection = ViewState(Set<String>()) // pack names

    private var affected: [SceneryPack] {
        controller.packsAffectingSelection()
    }

    private var sections: [(kind: PackKind, packs: [SceneryPack])] {
        let grouped = Dictionary(grouping: affected, by: { $0.kind })
        return PackKind.allCases.compactMap { kind in
            grouped[kind].map { (kind, $0.sorted { $0.name.lowercased() < $1.name.lowercased() }) }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            if controller.selectedTiles.isEmpty {
                ContentUnavailableView(
                    "No Tiles Selected",
                    systemImage: "square.dashed",
                    description: Text("Click a tile on the map (⇧-drag for a region). The packages covering it appear here.")
                )
            } else if affected.isEmpty {
                ContentUnavailableView(
                    "No Custom Scenery Here",
                    systemImage: "square.dashed",
                    description: Text("No custom package covers the selected tile\(controller.selectedTiles.count == 1 ? "" : "s").")
                )
            } else {
                List(selection: $selection.value) {
                    ForEach(sections, id: \.kind) { section in
                        Section("\(section.kind.rawValue) (\(section.packs.count))") {
                            ForEach(section.packs, id: \.name) { pack in
                                packRow(pack).tag(pack.name)
                            }
                        }
                    }
                }
                .listStyle(.inset)
                .contextMenu(forSelectionType: String.self) { names in
                    packActionButtons(for: names.isEmpty ? selection.value : names)
                }

                Divider()
                HStack {
                    Text("\(affected.count) package\(affected.count == 1 ? "" : "s") in selection")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Menu {
                        packActionButtons(for: selection.value)
                    } label: {
                        Image(systemName: "wrench.and.screwdriver")
                    }
                    .menuStyle(.borderlessButton)
                    .fixedSize()
                    .disabled(selection.value.isEmpty || controller.isApplyingAction || controller.isRunning)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(.bar)
            }
        }
    }

    private func packRow(_ pack: SceneryPack) -> some View {
        HStack(spacing: 6) {
            statusDot(pack.status)
            VStack(alignment: .leading, spacing: 1) {
                Text(pack.name)
                    .lineLimit(1)
                    .truncationMode(.middle)
                if !pack.airports.isEmpty {
                    Text(pack.airports.keys.sorted().prefix(6).joined(separator: " "))
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        }
        .help(pack.url.path)
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
