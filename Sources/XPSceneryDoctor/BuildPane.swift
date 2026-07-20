import SwiftUI
import SceneryKit

/// Right inspector pane in Build mode, mirroring the Qt front end's context
/// panel: a Selection box (active tile's details + "Installed in X-Plane"),
/// a Build box (step groups, always visible so more tiles can be queued
/// mid-run), and an Activity box (per-tile rows + run clock, only during a
/// run).
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
                        box("Selection") { selectionBox }
                        box("Build") { buildBox }
                        if buildModel.isBuilding || !buildModel.activity.runOrder.isEmpty {
                            box("Activity") {
                                ActivityBox()
                                    .environmentObject(buildModel)
                                    .environmentObject(buildModel.activity)
                            }
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
                buildModel.rescan()
            }
        }
    }

    private var engineSubtitle: String {
        guard let engine = buildModel.engine else { return "No engine configured" }
        var text = "Engine \(engine.version)"
        if !buildModel.usesProtocol { text += " (legacy driver)" }
        if let missing = buildModel.missingPackages, !missing.isEmpty {
            text += " — python packages missing"
        }
        return text
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

    // MARK: - Selection box (active tile details)

    @ViewBuilder
    private var selectionBox: some View {
        if let active = buildModel.activeTile {
            let info = buildModel.built[active]
            Text("Tile \(active.key)\(titleSuffix(active, info))")
                .font(.callout.weight(.semibold))
            detailRow("Imagery", info?.provider.isEmpty == false ? info!.provider : "—")
            detailRow("Zoom level", zlText(info))
            detailRow("Mesh built", dateText(info?.meshDate))
            detailRow("Imagery updated", dateText(info?.imageryDate))
            if let dem = info?.customDEM, !dem.isEmpty {
                detailRow("Elevation", (dem as NSString).lastPathComponent)
            }
            Toggle("Installed in X-Plane", isOn: Binding(
                get: { buildModel.isInstalled(active) },
                set: { buildModel.setInstalled(active, $0) }
            ))
            .toggleStyle(.checkbox)
            .disabled(info?.dsfPresent != true || buildModel.isBuilding)
            .help(info?.dsfPresent == true
                  ? "Links the tile into Custom Scenery so X-Plane loads it"
                  : "Build the tile first")
            if buildModel.selected.count > 1 {
                Divider()
                let installedCount = buildModel.selected.filter { buildModel.isInstalled($0) }.count
                Text("\(buildModel.selected.count) tiles selected · \(installedCount) installed")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("Clear Selection") { buildModel.clearSelection() }
                    .controlSize(.small)
            }
        } else {
            Text("Click a tile on the map — ⌘-click adds, ⇧-click selects a range. Or search an airport / tile key.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        if buildModel.isScanning {
            HStack(spacing: 6) {
                ProgressView().controlSize(.mini)
                Text(buildModel.scanPhase.isEmpty ? "Scanning…" : buildModel.scanPhase)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func titleSuffix(_ tile: BuildModel.TileCoord, _ info: O4TileInfo?) -> String {
        if buildModel.isScanning, info == nil { return "  (scanning…)" }
        return info == nil ? "  (not built)" : ""
    }

    private func zlText(_ info: O4TileInfo?) -> String {
        guard let zl = info?.zl else { return "—" }
        return "ZL\(zl)" + (info?.hasZones == true ? " + zones" : "")
    }

    private func dateText(_ epoch: Double?) -> String {
        guard let epoch, epoch > 0 else { return "—" }
        return Date(timeIntervalSince1970: epoch)
            .formatted(date: .abbreviated, time: .shortened)
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label + ":")
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            Text(value)
                .font(.caption)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }

    // MARK: - Build box

    private var buildBox: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(buildSummary)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Picker("Imagery", selection: providerBinding) {
                Text("Tile / global default").tag("")
                Divider()
                ForEach(buildModel.providers) { provider in
                    Text(provider.isCombined ? "\(provider.code) (combined)" : provider.code)
                        .tag(provider.code)
                }
            }
            Picker("Build ZL", selection: zlBinding) {
                ForEach(12...18, id: \.self) { zl in
                    Text("ZL\(zl)").tag(zl)
                }
            }
            .help("Higher zoom levels mean sharper imagery and much larger downloads: one ZL step ≈ 4× the data.")
            Divider()
            Toggle("Vector, mesh & masks", isOn: boolBinding(\.doVector))
                .help("OSM data, elevation, triangulation and water masks — the tile's terrain.")
            Toggle("Imagery & DSF", isOn: boolBinding(\.doImagery))
                .help("Downloads imagery, converts textures and writes the final DSF.")
            Toggle("Extract overlays", isOn: boolBinding(\.doOverlays))
                .help("Extracts roads/buildings overlays from the overlay source configured in the engine config.")
            Toggle("Skip already-built tiles", isOn: boolBinding(\.skipBuilt))
            Toggle("Install finished tiles automatically", isOn: boolBinding(\.linkTiles))
            Divider()
            LabeledContent("Tile folder") {
                HStack(spacing: 4) {
                    Text(buildModel.customBuildDir.isEmpty
                         ? "Ortho4XP/Tiles" : buildModel.customBuildDir)
                        .font(.caption)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundStyle(.secondary)
                    Button {
                        showingBaseFolderPicker.value = true
                    } label: {
                        Image(systemName: "folder")
                    }
                    .buttonStyle(.borderless)
                    if !buildModel.customBuildDir.isEmpty {
                        Button {
                            buildModel.customBuildDir = ""
                            buildModel.rescan()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                        }
                        .buttonStyle(.borderless)
                    }
                }
            }
            .font(.callout)
        }
        .toggleStyle(.checkbox)
    }

    private var buildSummary: String {
        let count = buildModel.selected.count
        guard count > 0 else { return "No tiles selected" }
        let todo = buildModel.buildableSelection.count
        var text = "\(count) tile\(count == 1 ? "" : "s") selected"
        if todo < count { text += " · \(count - todo) already built (skipped)" }
        return text
    }

    // MARK: - Bottom bar (the ▶ Build button lives here)

    private var bottomBar: some View {
        HStack(spacing: 8) {
            if let missing = buildModel.missingPackages, !missing.isEmpty {
                Label("Missing: \(missing.joined(separator: ", "))",
                      systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .help("The engine's python can't import these packages — run the engine setup from Settings ▸ Ortho4XP.")
            } else if let summary = buildModel.lastRunSummary, !buildModel.isBuilding {
                Text(summary).foregroundStyle(.secondary)
            }
            Spacer()
            if buildModel.isBuilding {
                Button(buildModel.isStopping ? "Stopping…" : "■ Stop") {
                    buildModel.stopBuild()
                }
                .disabled(buildModel.isStopping)
            }
            Button(buildButtonLabel) {
                buildModel.startBuild()
            }
            .buttonStyle(.borderedProminent)
            .disabled(!buildModel.canBuild || buildModel.buildableSelection.isEmpty)
            .help(buildModel.selected.isEmpty
                  ? "Select tiles on the map first"
                  : "Build the selected tiles with the steps above")
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .frame(height: ResultsPane.bottomBarHeight)
        .background(.bar)
    }

    private var buildButtonLabel: String {
        let n = buildModel.buildableSelection.count
        if buildModel.isBuilding, buildModel.usesProtocol {
            return "＋ Queue \(n) tile\(n == 1 ? "" : "s")"
        }
        return n > 0 ? "▶ Build \(n) tile\(n == 1 ? "" : "s")" : "▶ Build"
    }

    // MARK: - Bindings (AppStorage on the model doesn't self-publish)

    private var providerBinding: Binding<String> {
        Binding(get: { buildModel.buildProvider },
                set: { buildModel.objectWillChange.send(); buildModel.buildProvider = $0 })
    }

    private var zlBinding: Binding<Int> {
        Binding(get: { buildModel.buildZL },
                set: { buildModel.objectWillChange.send(); buildModel.buildZL = $0 })
    }

    private func boolBinding(_ keyPath: ReferenceWritableKeyPath<BuildModel, Bool>) -> Binding<Bool> {
        Binding(get: { buildModel[keyPath: keyPath] },
                set: { buildModel.objectWillChange.send(); buildModel[keyPath: keyPath] = $0 })
    }
}

/// Per-tile rows + the run clock, like the Qt Activity group: each row is
/// tile key · status · progress bar · per-tile cancel; below them Elapsed /
/// Remaining. Observes only the high-frequency activity model.
struct ActivityBox: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var activity: BuildActivityModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if activity.totalTiles > 0 {
                Text("Building \(activity.totalTiles) tile\(activity.totalTiles == 1 ? "" : "s") — \(activity.doneTiles) done")
                    .font(.callout.weight(.medium))
            }
            ForEach(activity.runOrder, id: \.self) { coord in
                row(coord, activity.tiles[coord])
            }
            Divider()
            HStack {
                Text("Elapsed \(Self.clock(activity.elapsedSeconds))")
                Spacer()
                Text("Remaining ≈ \(activity.remainingSeconds.map(Self.clock) ?? "—")")
            }
            .font(.caption.monospacedDigit())
            .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func row(_ coord: BuildModel.TileCoord, _ progress: TileProgress?) -> some View {
        let progress = progress ?? TileProgress(state: .queued, label: "queued", percent: 0)
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Text(coord.key)
                    .font(.caption.monospaced())
                Text(progress.state == .active
                     ? "\(progress.label) · \(Int(progress.percent))%" : progress.label)
                    .font(.caption)
                    .foregroundStyle(statusColor(progress.state))
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                if buildModel.usesProtocol, buildModel.isBuilding,
                   progress.state == .queued || progress.state == .active
                    || progress.state == .indeterminate {
                    Button {
                        buildModel.cancelTile(coord)
                    } label: {
                        Image(systemName: "xmark.circle")
                    }
                    .buttonStyle(.borderless)
                    .controlSize(.small)
                    .help("Cancel this tile")
                }
            }
            ProgressView(value: progress.state == .done ? 100 : progress.percent, total: 100)
                .controlSize(.small)
                .tint(progressTint(progress.state))
        }
    }

    private func statusColor(_ state: TileProgress.State) -> Color {
        switch state {
        case .done: return .green
        case .error: return .red
        default: return .secondary
        }
    }

    private func progressTint(_ state: TileProgress.State) -> Color {
        switch state {
        case .done: return .green
        case .error: return .red
        default: return .accentColor
        }
    }

    static func clock(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        if total >= 3600 {
            return String(format: "%d:%02d:%02d", total / 3600, (total % 3600) / 60, total % 60)
        }
        return String(format: "%d:%02d", total / 60, total % 60)
    }
}
