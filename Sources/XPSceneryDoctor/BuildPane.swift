import SwiftUI
import SceneryKit

/// Right inspector pane in Build mode: the Ortho4XP main-window controls
/// translated to native boxes — Tile Details (what's selected, imagery,
/// zoom level), Build Options (which pipeline steps run) and Activity (the
/// engine's three progress bars + queue).
struct BuildPane: View {
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var showingBaseFolderPicker = ViewState(false)

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Ortho4XP Build")
                    .font(.headline)
                Text(engineSubtitle)
                    .font(.caption)
                    .foregroundStyle(buildModel.engine == nil ? .orange : .secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            Divider()

            if buildModel.engine == nil {
                noEngine
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        box("Tile Details") { tileDetails }
                        box("Build Options") { buildOptions }
                        box("Activity") {
                            ActivityBox(queue: buildModel.queue,
                                        isBuilding: buildModel.isBuilding)
                                .environmentObject(buildModel.activity)
                        }
                    }
                    .padding(10)
                }
                Divider()
                bottomBar
            }
        }
        .fileImporter(isPresented: $showingBaseFolderPicker.value,
                      allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result {
                buildModel.customBuildDir = url.path
                buildModel.refreshTileStates()
            }
        }
    }

    private var engineSubtitle: String {
        if let engine = buildModel.engine {
            var text = "Engine \(engine.version)"
            if let missing = buildModel.missingPackages, !missing.isEmpty {
                text += " — python packages missing"
            }
            return text
        }
        return "No engine configured"
    }

    private var noEngine: some View {
        VStack(spacing: 12) {
            Image(systemName: "globe.europe.africa")
                .font(.system(size: 36))
                .foregroundStyle(.tertiary)
            Text("Point XPScenery Doctor at an Ortho4XP folder to build photoscenery tiles from here.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            SettingsLink {
                Text("Open Settings…")
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func box<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 8) {
                content()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(4)
        } label: {
            Text(title).font(.callout.weight(.semibold))
        }
    }

    // MARK: - Tile details

    private var tileDetails: some View {
        VStack(alignment: .leading, spacing: 8) {
            if buildModel.selected.isEmpty {
                Text("Click tiles on the map to select them — or search for an airport.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                HStack {
                    Text(selectionSummary)
                        .font(.callout)
                    Spacer()
                    Button("Clear") { buildModel.clearSelection() }
                        .controlSize(.small)
                }
                Text(selectedKeysPreview)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .truncationMode(.tail)
            }
            Divider()
            Picker("Imagery", selection: providerBinding) {
                Text("Tile / global default").tag("")
                Divider()
                ForEach(buildModel.providers) { provider in
                    Text(provider.isCombined ? "\(provider.code) (combined)" : provider.code)
                        .tag(provider.code)
                }
            }
            .help("The imagery source for this build. Combined providers stack regional layers.")
            Picker("Zoom Level", selection: zlBinding) {
                ForEach(12...19, id: \.self) { zl in
                    Text("ZL\(zl)").tag(zl)
                }
            }
            .help("Higher zoom levels mean sharper imagery and much larger downloads: one ZL step ≈ 4× the data.")
            LabeledContent("Tile Folder") {
                HStack(spacing: 4) {
                    Text(buildModel.customBuildDir.isEmpty
                         ? "Ortho4XP/Tiles" : buildModel.customBuildDir)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundStyle(.secondary)
                    Button {
                        showingBaseFolderPicker.value = true
                    } label: {
                        Image(systemName: "folder")
                    }
                    .buttonStyle(.borderless)
                    .help("Choose a custom base folder for built tiles")
                    if !buildModel.customBuildDir.isEmpty {
                        Button {
                            buildModel.customBuildDir = ""
                            buildModel.refreshTileStates()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                        }
                        .buttonStyle(.borderless)
                        .help("Back to the engine's Tiles folder")
                    }
                }
            }
            .font(.callout)
        }
    }

    private var selectionSummary: String {
        let count = buildModel.selected.count
        let built = buildModel.selected.filter {
            buildModel.tileStates[$0]?.hasDSF == true
        }.count
        var text = "\(count.formatted()) tile\(count == 1 ? "" : "s") selected"
        if built > 0 { text += " (\(built) already built)" }
        return text
    }

    private var selectedKeysPreview: String {
        let keys = buildModel.selected.sorted().map { $0.key }
        let shown = keys.prefix(8).joined(separator: "  ")
        return keys.count > 8 ? shown + "  +\(keys.count - 8) more" : shown
    }

    // MARK: - Build options

    private var buildOptions: some View {
        VStack(alignment: .leading, spacing: 6) {
            stepToggle("vector", "Runs first: OSM roads/water + elevation become the tile's vector data.")
            stepToggle("mesh", "Triangulates the 3D terrain mesh (needs the vector step's output).")
            stepToggle("masks", "Draws the water transparency masks along coastlines.")
            stepToggle("dsf", "Downloads imagery, converts textures and writes the final DSF.")
            stepToggle("overlay", "Extracts roads/buildings overlays from existing scenery (needs the overlay source configured in the engine config).")
            Divider()
            Toggle(isOn: linkTilesBinding) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("Link finished tiles into Custom Scenery")
                    Text("Symlinks the tile folder; the Manage side then adds it to scenery_packs.ini.")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .toggleStyle(.checkbox)
    }

    private func stepToggle(_ step: String, _ help: String) -> some View {
        Toggle(OrthoBuildJob.stepLabel(step), isOn: Binding(
            get: { buildModel.steps.contains(step) },
            set: { on in
                if on { buildModel.steps.insert(step) } else { buildModel.steps.remove(step) }
            }
        ))
        .help(help)
    }

    // MARK: - Bottom bar

    private var bottomBar: some View {
        HStack(spacing: 8) {
            if let missing = buildModel.missingPackages, !missing.isEmpty {
                Label("Missing: \(missing.joined(separator: ", "))", systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .help("The engine's python can't import these packages — run the engine setup from Settings ▸ Ortho4XP.")
            } else if let summary = buildModel.lastRunSummary, !buildModel.isBuilding {
                Text(summary).foregroundStyle(.secondary)
            }
            Spacer()
            if buildModel.isBuilding {
                Button(buildModel.isStopping ? "Force Stop" : "Stop") {
                    buildModel.stopBuild()
                }
            } else {
                Button("Build \(buildModel.selected.count.formatted())") {
                    buildModel.startBuild()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!buildModel.canBuild)
                .help(buildModel.selected.isEmpty
                      ? "Select tiles on the map first"
                      : "Build the selected tiles with the steps above")
            }
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .frame(height: ResultsPane.bottomBarHeight)
        .background(.bar)
    }

    private var providerBinding: Binding<String> {
        Binding(get: { buildModel.buildProvider },
                set: { buildModel.objectWillChange.send(); buildModel.buildProvider = $0 })
    }

    private var zlBinding: Binding<Int> {
        Binding(get: { buildModel.buildZL },
                set: { buildModel.objectWillChange.send(); buildModel.buildZL = $0 })
    }

    private var linkTilesBinding: Binding<Bool> {
        Binding(get: { buildModel.linkTiles },
                set: { buildModel.objectWillChange.send(); buildModel.linkTiles = $0 })
    }
}

/// The engine's three progress bars (mesh / download / convert) plus the
/// queue — the "activity" cluster of the Ortho4XP main window. Observes only
/// the high-frequency activity model.
struct ActivityBox: View {
    @EnvironmentObject var activity: BuildActivityModel
    let queue: [BuildModel.TileCoord]
    let isBuilding: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if isBuilding {
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text([activity.currentTileKey, activity.currentStepLabel]
                            .compactMap { $0 }.joined(separator: " — "))
                        .font(.callout)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
            } else {
                Text("Idle")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            bar(1, "Mesh")
            bar(2, "Download")
            bar(3, "Convert")
            if !queue.isEmpty {
                Divider()
                Text("Queued: " + queue.prefix(6).map { $0.key }.joined(separator: "  ")
                     + (queue.count > 6 ? "  +\(queue.count - 6) more" : ""))
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
    }

    private func bar(_ id: Int, _ label: String) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 64, alignment: .leading)
            ProgressView(value: Double(activity.bars[id] ?? 0), total: 100)
                .controlSize(.small)
            Text("\(activity.bars[id] ?? 0)%")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(width: 36, alignment: .trailing)
        }
    }
}
