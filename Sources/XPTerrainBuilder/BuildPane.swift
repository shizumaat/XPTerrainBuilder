import SwiftUI
import SceneryKit

/// Right inspector pane in Build mode, mirroring the Qt front end's context
/// panel: a Selection box (active tile's details + "Installed in X-Plane"),
/// a Build box (step groups, always visible so more tiles can be queued
/// mid-run), and an Activity box (per-tile rows + run clock, only during a
/// run).
struct BuildPane: View {
    /// Height of the pane's bottom status bar. Fixed, not padding-driven:
    /// the bar contains regular-size buttons, and padding alone gives an
    /// unstable height as the label text changes.
    static let bottomBarHeight: CGFloat = 38

    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var showingBaseFolderPicker = ViewState(false)
    /// Custom airport packs (own 3-D objects) in the selected tiles —
    /// the packages "Modify custom airports" would reseat.
    @State private var customAirportPacks: [String] = []
    /// The engine's Airports card for the selected tiles (#818).
    @State private var airportCard: O4BuildAirports?
    @State private var airportCardLoading = false
    @State private var airportCardError: String?
    /// The Build box's plumbing toggles, collapsed by default (#818).
    @State private var showingAdvanced = false
    /// Imagery-source audit of the active tile's textures folder; non-nil
    /// with hasConflict when sources besides the tile's current one exist.
    @State private var textureAudit: TileTextureAudit?
    @State private var showingImageryConflict = false
    @State private var isTrashingImages = false
    @State private var trashMessage: String?
    /// Aggregated audit over a multi-tile selection, plus the conflicted
    /// coords so map badges can be refreshed after a bulk cleanup.
    @State private var combinedAudit: TileTextureAudit.Combined?
    @State private var combinedConflictCoords: [BuildModel.TileCoord] = []
    @State private var showingCombinedConflict = false
    /// Other installed ortho/mesh packages covering the active tile
    /// (gray-outlined on the map) with that tile's DSF modification date.
    @State private var otherScenery: [(name: String, dsfDate: Date?)] = []
    @State private var showingProviderMismatch = false
    @State private var showingMissingDetails = false
    /// Airport packs whose 3-D objects the auto-patch pass reseated in
    /// the active tile ("Modified airports" row), with per-pack revert.
    @State private var modifiedAirports: [ModifiedAirportRow] = []
    @State private var reseatRefresh = 0
    /// Legacy tile-settings alert: offered once per tile per app run.
    @State private var legacyTile: BuildModel.LegacyTileSettings?
    @State private var showingLegacyAlert = false
    @State private var legacyPromptShown: Set<String> = []
    /// The active tile's customized settings (#1350), from the engine.
    @State private var customizations: [O4TileCustomization] = []
    @State private var textureCheck: O4TileTextureCheck?
    @Environment(\.openSettings) private var openSettings

    /// The tile pane's customized-settings words; the Qt pane uses the
    /// same (O4_Qt_GUI.CUSTOM_SETTINGS / EDIT_TILE_SETTINGS).
    static let customSettingsTitle = "Custom settings"
    static let editSettingsTitle = "Edit settings…"

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Build")
                    .scaledFont(.headline)
                Text(engineSubtitle)
                    .scaledFont(.caption)
                    .foregroundStyle(buildModel.engine == nil ? .orange : .secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            Divider()

            if buildModel.engine == nil {
                noEngine
            } else {
                RunListLayout {
                    VStack(alignment: .leading, spacing: 12) {
                        box("Selection") { selectionBox }
                        box("Build") { buildBox }
                        PatchInspector(model: buildModel.patchEdit)
                    }
                    .padding(10)
                }
                .environmentObject(buildModel.activity)
                Divider()
                bottomBar
            }
        }
        .task(id: "\(buildModel.selected.sorted().map(\.key).joined(separator: ","))|\(controller.installationPacks.count)") {
            await refreshCustomAirportPacks()
        }
        .task(id: "airports|\(buildModel.selected.sorted().map(\.key).joined(separator: ","))|\(controller.installationPacks.count)|\(buildModel.built.count)") {
            await refreshAirportCard()
        }
        .task(id: imageryAuditKey) {
            await refreshTextureAudit()
        }
        .task(id: buildModel.planEstimateKey) {
            await buildModel.updatePlanEstimate()
        }
        .task(id: "\(buildModel.activeTile?.key ?? "")|\(controller.mapOverlays.regions.count)") {
            await refreshOtherScenery()
        }
        .task(id: "reseat|\(buildModel.activeTile?.key ?? "")|\(controller.installationPacks.count)|\(buildModel.isBuilding)|\(reseatRefresh)|\(buildModel.packForestsChanged)") {
            await refreshModifiedAirports()
        }
        .modifier(TileTextureCheckTask(
            key: buildModel.tileTextureCheckKey(for: buildModel.activeTile),
            load: { [buildModel] in
                guard let coord = buildModel.activeTile else { return nil }
                return await buildModel.tileTextureCheck(for: coord)
            },
            check: $textureCheck))
        .task(id: customizationsKey) {
            guard let coord = buildModel.activeTile else {
                customizations = []
                return
            }
            customizations = await buildModel.tileCustomizations(for: coord)
        }
        .task(id: "legacy|\(buildModel.activeTile?.key ?? "")|\(buildModel.built.count)") {
            guard let coord = buildModel.activeTile,
                  !legacyPromptShown.contains(coord.key),
                  let legacy = buildModel.legacyTileSettings(for: coord)
            else { return }
            legacyPromptShown.insert(coord.key)
            legacyTile = legacy
            showingLegacyAlert = true
        }
        .alert("Tile built with an older version",
               isPresented: $showingLegacyAlert,
               presenting: legacyTile) { legacy in
            Button("Update to Current Defaults") {
                buildModel.updateLegacyTileSettings(legacy)
            }
            Button("Keep As-Is", role: .cancel) {}
        } message: { legacy in
            Text(legacyAlertMessage(legacy))
        }
        .task(id: "\(buildModel.selected.sorted().map(\.key).joined(separator: ","))|\(buildModel.built.count)") {
            await refreshCombinedAudit()
        }
        .fileImporter(isPresented: $showingBaseFolderPicker.value,
                      allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result {
                buildModel.customBuildDir = url.path
                buildModel.rescan()
            }
        }
    }

    /// Re-reads the active tile's customizations when the tile, its cfg
    /// (a Settings edit) or its badge changes.
    private var customizationsKey: String {
        let active = buildModel.activeTile
        let badged = active.map { buildModel.customizedTiles.contains($0) } ?? false
        return "custom|\(active?.key ?? "")|\(buildModel.tileConfigGeneration)|\(badged)|\(buildModel.built.count)"
    }

    /// Status only — the engine version lives in Settings.
    private var engineSubtitle: String {
        guard buildModel.engine != nil else { return "No engine configured" }
        var parts: [String] = []
        if !buildModel.usesProtocol { parts.append("legacy driver") }
        if let missing = buildModel.missingPackages, !missing.isEmpty {
            parts.append("engine incomplete")
        }
        return parts.isEmpty ? "Engine ready" : parts.joined(separator: " — ")
    }

    private var noEngine: some View {
        VStack(spacing: 12) {
            Image(systemName: "globe.europe.africa")
                .font(.system(size: 36))
                .foregroundStyle(.tertiary)
            Text("No build engine available. The app normally uses its bundled engine — check Settings ▸ General ▸ Build Engine if it can't be found, or choose a custom engine folder there.")
                .scaledFont(.callout)
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
        PaneBox(content: content) {
            Text(title).scaledFont(.callout, weight: .semibold)
        }
    }

    // MARK: - Selection box (active tile details)

    @ViewBuilder
    private var selectionBox: some View {
        if let active = buildModel.activeTile {
            let info = buildModel.built[active]
            Text("Tile \(active.key)\(titleSuffix(active, info))")
                .scaledFont(.callout, weight: .semibold)
            HStack(spacing: 5) {
                detailRow("Imagery", info?.provider.isEmpty == false ? info!.provider : "—")
                if let audit = textureAudit, audit.hasConflict {
                    Button {
                        trashMessage = nil
                        showingImageryConflict = true
                    } label: {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.yellow)
                            .scaledFont(.caption)
                    }
                    .buttonStyle(.borderless)
                    .help("Multiple imagery sources are installed in this tile")
                    .popover(isPresented: $showingImageryConflict, arrowEdge: .trailing) {
                        imageryConflictPopover(audit)
                    }
                }
            }
            if info != nil {
                TileMissingTexturesRow(check: textureCheck) {
                    buildModel.rebuildWithItsImagery(active)
                }
            }
            detailRow(O4Glossary.term("detail"), zlText(info))
            detailRow("Ground shaped", dateText(info?.meshDate))
            detailRow("Imagery updated", dateText(info?.imageryDate))
            if let info {
                // Who built it (#1226, owner Q95): from the build record,
                // else the tile's DSF.
                detailRow("Built by", info.builtBy ?? "—")
            }
            if let dem = info?.customDEM, !dem.isEmpty {
                detailRow("Elevation", (dem as NSString).lastPathComponent)
            }
            // Other installed ortho/mesh packages covering this tile.
            ForEach(otherScenery, id: \.name) { item in
                detailRow("Other scenery", item.name)
                    .help(item.name)
                detailRow("Modified", item.dsfDate.map {
                    $0.formatted(date: .abbreviated, time: .shortened)
                } ?? "—")
            }
            // Custom settings (#1350): each setting this tile's cfg
            // customizes, "name: tile value (default value)", and the way
            // into Settings for this tile alone (the Qt pane: the same).
            if !customizations.isEmpty {
                HStack(alignment: .firstTextBaseline) {
                    Text(Self.customSettingsTitle + ":")
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                        .frame(width: 104, alignment: .trailing)
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(customizations) { row in
                            Text(row.displayText)
                                .scaledFont(.caption)
                                .fixedSize(horizontal: false, vertical: true)
                                .help(row.helpText)
                        }
                        Button(Self.editSettingsTitle) {
                            buildModel.editSettings(for: active)
                            openSettings()
                        }
                        .controlSize(.small)
                        .help("Open Settings for this tile, showing its customized settings.")
                    }
                }
            }
            // Custom patch (#1229, RULINGS 2026-10-26c): the custom patch
            // files the build applies instead of the auto patch, and "Use
            // auto patch", which sets them aside, never deletes them (the
            // Qt pane: the same).
            if let files = buildModel.customPatchTiles[active], !files.isEmpty {
                HStack(alignment: .firstTextBaseline) {
                    Text(O4CustomPatchText.title + ":")
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                        .frame(width: 104, alignment: .trailing)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(O4CustomPatchText.info(files))
                            .scaledFont(.caption)
                            .fixedSize(horizontal: false, vertical: true)
                        Button(O4CustomPatchText.useAutoPatchTitle) {
                            buildModel.useAutoPatch(for: active)
                        }
                        .controlSize(.small)
                        .disabled(buildModel.isBuilding)
                        .help(O4CustomPatchText.useAutoPatchHelp)
                    }
                }
            }
            // Custom airports whose objects the auto-patch pass reseated
            // for this tile's mesh: one label, one row per airport, an
            // undo button per row reverting that airport's pack to the
            // author's original files (.anchor_bak backups).
            if !modifiedAirports.isEmpty {
                HStack(alignment: .firstTextBaseline) {
                    Text("Modified airports:")
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                        .frame(width: 104, alignment: .trailing)
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(modifiedAirports) { row in
                            HStack(spacing: 4) {
                                Text(row.label)
                                    .scaledFont(.caption)
                                    .lineLimit(1)
                                    .truncationMode(.middle)
                                    .help("\(row.packName) — \(row.objectCount) object file\(row.objectCount == 1 ? "" : "s") reseated to this tile's rebuilt ground")
                                Spacer(minLength: 8)
                                // #1360: the pack's 3D trees, undone on
                                // their own (the Qt row's twin button)
                                if row.forestCount > 0 {
                                    Button {
                                        buildModel.undoPackForests(packPath: row.packPath)
                                    } label: {
                                        Image(systemName: "leaf")
                                    }
                                    .buttonStyle(.borderless)
                                    .controlSize(.small)
                                    .disabled(buildModel.isBuilding)
                                    .help(buildModel.isBuilding
                                          ? "Wait for the current run — the engine may be rewriting these files"
                                          : O4PackOldForestsCopy.undoHelp)
                                }
                                Button {
                                    revertModifiedAirports(row)
                                } label: {
                                    Image(systemName: "arrow.uturn.backward.circle")
                                }
                                .buttonStyle(.borderless)
                                .controlSize(.small)
                                .disabled(buildModel.isBuilding)
                                .help(buildModel.isBuilding
                                      ? "Wait for the current run — the engine may be rewriting these files"
                                      : "Revert to default: restores \(row.packName)'s original object files from the backups the reseater kept")
                            }
                        }
                    }
                }
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
                HStack(spacing: 6) {
                    Text("\(buildModel.selected.count) tiles selected · \(installedCount) installed")
                        .scaledFont(.caption)
                        .foregroundStyle(.secondary)
                    if let combined = combinedAudit, combined.hasConflict {
                        Button {
                            trashMessage = nil
                            showingCombinedConflict = true
                        } label: {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.yellow)
                                .scaledFont(.caption)
                        }
                        .buttonStyle(.borderless)
                        .help("\(combined.tilesWithConflict) selected tile\(combined.tilesWithConflict == 1 ? " has" : "s have") multiple imagery sources")
                        .popover(isPresented: $showingCombinedConflict, arrowEdge: .trailing) {
                            combinedConflictPopover(combined)
                        }
                    }
                }
                Button("Clear Selection") { buildModel.clearSelection() }
                    .controlSize(.small)
            }
        } else {
            // Empty state (#828): what a tile is and what a build does,
            // then how to pick one — and how to start when nothing is built.
            VStack(alignment: .leading, spacing: 6) {
                Text(MapGuidance.emptySelectionText)
                Text("Search your airport in the toolbar, or click its square on the map — ⌘-click adds, ⇧-click selects a range.")
                if buildModel.built.isEmpty && !buildModel.isScanning {
                    Text(MapGuidance.nothingBuiltText)
                }
            }
            .scaledFont(.caption)
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
        }
        if buildModel.isScanning {
            HStack(spacing: 6) {
                ProgressView().controlSize(.mini)
                Text(buildModel.scanPhase.isEmpty ? "Scanning…" : buildModel.scanPhase)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private func titleSuffix(_ tile: BuildModel.TileCoord, _ info: O4TileInfo?) -> String {
        if buildModel.isScanning, info == nil { return "  (scanning…)" }
        return info == nil ? "  (not built)" : ""
    }

    private func zlText(_ info: O4TileInfo?) -> String {
        guard let info, let zl = info.zl else { return "—" }
        var text = O4Glossary.detailChoice(zl)
        // Airport high-ZL cover: e.g. "ZL16 + ZL18 ICAO" makes the
        // upgraded-airports setting visible at a glance.
        let mode = info.highZLAirports
        if mode != "", mode != "False", let cover = info.coverZL, cover > zl {
            let scope = ["True": "All", "ICAO": "ICAO", "Existing": "Existing"]
            text += " + ZL\(cover) \(scope[mode] ?? mode)"
        }
        if info.hasZones { text += " + zones" }
        return text
    }

    private func dateText(_ epoch: Double?) -> String {
        guard let epoch, epoch > 0 else { return "—" }
        return Date(timeIntervalSince1970: epoch)
            .formatted(date: .abbreviated, time: .shortened)
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label + ":")
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 104, alignment: .trailing)
            Text(value)
                .scaledFont(.caption)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }

    // MARK: - Build box

    /// Top to bottom (#818): what you're building, the Airports card,
    /// the imagery source, what happens when it's done, and the build
    /// plumbing collapsed under Advanced.
    private var buildBox: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(buildSummary)
                .scaledFont(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            BuildAirportsCard(card: airportCard, isLoading: airportCardLoading,
                              error: airportCardError,
                              fallbackPacks: customAirportPacks)
            Picker("Imagery", selection: providerBinding) {
                Text("Tile / global default").tag("")
                // The engine's one list (#1345), the map picker's order;
                // an offline source shows "(offline)", greyed, its reason
                // as the tooltip.
                ForEach(ImageryMenu.sections(ImageryMenu.entries(
                    buildModel.imagerySources, statuses: buildModel.imageryStatus,
                    forMap: false,
                    tiles: buildModel.selected.map { (lat: $0.lat, lon: $0.lon) }))) { section in
                    Section(section.title) {
                        ForEach(section.entries) { entry in
                            Text(entry.label).tag(entry.code)
                                .disabled(!entry.enabled)
                                .help(entry.tooltip)
                        }
                    }
                }
            }
            Divider()
            Text("When it's done")
                .scaledFont(.caption, weight: .semibold)
                .foregroundStyle(.secondary)
            Toggle("Install in X-Plane automatically", isOn: boolBinding(\.linkTiles))
            Toggle("Skip tiles already built", isOn: boolBinding(\.skipBuilt))
            DisclosureGroup("Advanced", isExpanded: $showingAdvanced) {
                VStack(alignment: .leading, spacing: 6) {
                    Toggle(O4Glossary.term("terrain_steps"), isOn: boolBinding(\.doVector))
                        .help("Downloads map data (roads, water, airports), shapes the ground and blends coastlines and water — the tile's terrain.")
                    Toggle(O4Glossary.term("imagery_and_scenery_file"), isOn: boolBinding(\.doImagery))
                        .help("Downloads imagery, converts textures and writes the final scenery file (DSF).")
                    Toggle(O4Glossary.term("xplane_objects"), isOn: boolBinding(\.doOverlays))
                        .help("Copies the roads, forests and buildings (overlays) of the X-Plane scenery configured as the overlay source.")
                    tileFolderRow
                }
                .padding(.top, 4)
            }
            .scaledFont(.callout)
            // What the build will cost, above Build (#820).
            if buildModel.planEstimate != nil || buildModel.planEstimateError != nil {
                Divider()
                PlanEstimatePanel(buildModel: buildModel)
            }
        }
        .toggleStyle(.checkbox)
    }

    private var tileFolderRow: some View {
        LabeledContent("Tile folder") {
            HStack(spacing: 4) {
                Text(buildModel.customBuildDir.isEmpty
                     ? "Ortho4XP/Tiles" : buildModel.customBuildDir)
                    .scaledFont(.caption)
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
        .scaledFont(.callout)
    }

    /// Asks the engine what grading and fitting will do for the selected
    /// tiles (#818). Debounced: a drag-selection changes the key per tile.
    private func refreshAirportCard() async {
        let tiles = Array(buildModel.selected)
        guard !tiles.isEmpty else {
            airportCard = nil
            airportCardError = nil
            return
        }
        airportCardLoading = true
        try? await Task.sleep(nanoseconds: 300_000_000)
        guard !Task.isCancelled else { return }
        let answer = await buildModel.buildAirportsCard(for: tiles)
        guard !Task.isCancelled else { return }
        switch answer {
        case .success(let card)?:
            airportCard = card
            airportCardError = nil
        case .failure(let error)?:
            airportCard = nil
            airportCardError = "\(error)"
        case nil:
            airportCard = nil
            airportCardError = nil
        }
        airportCardLoading = false
    }

    // MARK: - Imagery-source conflict (active tile)

    /// Task key: re-audit when the active tile, its build dir, or its
    /// configured provider changes (the scan fills these in async).
    private var imageryAuditKey: String {
        guard let active = buildModel.activeTile,
              let info = buildModel.built[active] else { return "" }
        return "\(active.key)|\(info.buildDir)|\(info.provider)"
    }

    private func refreshTextureAudit() async {
        guard let active = buildModel.activeTile,
              let info = buildModel.built[active],
              !info.buildDir.isEmpty, !info.provider.isEmpty else {
            textureAudit = nil
            return
        }
        let dir = URL(fileURLWithPath: info.buildDir, isDirectory: true)
            .appendingPathComponent("textures", isDirectory: true)
        let provider = info.provider
        textureAudit = await Task.detached(priority: .utility) {
            TileTextureAudit.scan(texturesDir: dir, currentProvider: provider)
        }.value
    }

    private func imageryConflictPopover(_ audit: TileTextureAudit) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Multiple imagery sources installed",
                  systemImage: "exclamationmark.triangle.fill")
                .scaledFont(.callout, weight: .semibold)
            Text("Only one imagery source can be used at a time; this tile's scenery file references \(audit.currentProvider) textures. Images from other sources are left over from earlier builds and never shown.")
                .scaledFont(.caption)
            VStack(alignment: .leading, spacing: 2) {
                ForEach(audit.sources) { source in
                    let isCurrent = source.provider.lowercased()
                        == audit.currentProvider.lowercased()
                    Text("\(source.provider) — \(source.fileCount) file\(source.fileCount == 1 ? "" : "s"), \(ByteCountFormatter.string(fromByteCount: source.bytes, countStyle: .file))\(isCurrent ? "  (current)" : "")")
                        .scaledFont(.caption)
                        .foregroundStyle(isCurrent ? .primary : .secondary)
                }
            }
            Text("If this tile deliberately mixes sources through imagery zones, keep them.")
                .scaledFont(.caption2)
                .foregroundStyle(.tertiary)
            if let trashMessage {
                Text(trashMessage)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
            }
            Button(isTrashingImages
                   ? "Moving…"
                   : "Move Unused Images to Trash") {
                trashForeignImages(audit)
            }
            .disabled(isTrashingImages || audit.foreignFiles.isEmpty)
        }
        .padding(12)
        .frame(width: 320)
    }

    private func trashForeignImages(_ audit: TileTextureAudit) {
        isTrashingImages = true
        trashMessage = nil
        let files = audit.foreignFiles
        let tile = buildModel.activeTile
        Task {
            let failures = await Task.detached(priority: .utility) { () -> Int in
                var failed = 0
                for url in files {
                    do {
                        try FileManager.default.trashItem(at: url, resultingItemURL: nil)
                    } catch {
                        failed += 1
                    }
                }
                return failed
            }.value
            isTrashingImages = false
            trashMessage = failures == 0
                ? "Moved \(files.count) image\(files.count == 1 ? "" : "s") to the Trash."
                : "Moved \(files.count - failures); \(failures) could not be moved."
            await refreshTextureAudit()
            // Clear (or confirm) the tile's map badge right away — no
            // rescan needed.
            if let tile { buildModel.reauditConflict(for: tile) }
        }
    }

    /// Other installed ortho/mesh packages covering the active tile, with
    /// the modification date of their DSF for that tile. Our own installed
    /// tile links (into the working dir) are excluded, matching the map.
    private func refreshOtherScenery() async {
        guard let active = buildModel.activeTile else {
            otherScenery = []
            return
        }
        let tileKey32 = Int32((active.lat + 90) * 360 + (active.lon + 180))
        let basePath = buildModel.tileBaseFolder?.path
        let builtDirs = Set(buildModel.built.values.map(\.buildDir))
        let covering = controller.mapOverlays.regions
            .filter { region in
                guard region.tileKeys.contains(tileKey32) else { return false }
                if builtDirs.contains(region.packPath)
                    || builtDirs.contains(region.contentRootPath) { return false }
                if let basePath, let resolved = region.resolvedPath,
                   resolved.hasPrefix(basePath) { return false }
                return true
            }
            .map { (name: $0.packName, root: $0.contentRootPath) }
        let key = active.key
        let folder = String(format: "%+03d%+04d",
                            Int(floor(Double(active.lat) / 10.0)) * 10,
                            Int(floor(Double(active.lon) / 10.0)) * 10)
        otherScenery = await Task.detached(priority: .utility) {
            covering.map { entry in
                let dsf = URL(fileURLWithPath: entry.root)
                    .appendingPathComponent("Earth nav data/\(folder)/\(key).dsf")
                let date = (try? FileManager.default.attributesOfItem(
                    atPath: dsf.path)[.modificationDate]) as? Date
                return (name: entry.name, dsfDate: date)
            }
        }.value
    }

    /// Full audit (with sizes) of every selected built tile, aggregated —
    /// drives the warning in the combined selection info.
    private func refreshCombinedAudit() async {
        guard buildModel.selected.count > 1 else {
            combinedAudit = nil
            combinedConflictCoords = []
            return
        }
        let entries: [(BuildModel.TileCoord, URL, String)] = buildModel.selected.compactMap { coord in
            guard let info = buildModel.built[coord],
                  !info.provider.isEmpty, !info.buildDir.isEmpty else { return nil }
            let textures = URL(fileURLWithPath: info.buildDir, isDirectory: true)
                .appendingPathComponent("textures", isDirectory: true)
            return (coord, textures, info.provider)
        }
        let (combined, coords) = await Task.detached(priority: .utility) {
            () -> (TileTextureAudit.Combined, [BuildModel.TileCoord]) in
            var audits: [TileTextureAudit] = []
            var conflicted: [BuildModel.TileCoord] = []
            for (coord, dir, provider) in entries {
                guard let audit = TileTextureAudit.scan(
                    texturesDir: dir, currentProvider: provider) else { continue }
                audits.append(audit)
                if audit.hasConflict { conflicted.append(coord) }
            }
            return (TileTextureAudit.Combined(audits), conflicted)
        }.value
        combinedAudit = combined
        combinedConflictCoords = coords
    }

    /// "Arc" when one provider, "Multiple" when mixed — per the combined
    /// dialog's source rows.
    private func providerLabel(_ providers: Set<String>) -> String {
        providers.count == 1 ? providers.first! : "Multiple"
    }

    private func combinedConflictPopover(_ combined: TileTextureAudit.Combined) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Multiple imagery sources installed",
                  systemImage: "exclamationmark.triangle.fill")
                .scaledFont(.callout, weight: .semibold)
            Text("\(combined.tilesWithConflict) of \(buildModel.selected.count) selected tiles carry textures from more than one source; only each tile's current source is ever shown.")
                .scaledFont(.caption)
            VStack(alignment: .leading, spacing: 2) {
                Text("In use: \(providerLabel(combined.currentProviders)) — \(ByteCountFormatter.string(fromByteCount: combined.currentBytes, countStyle: .file))")
                    .scaledFont(.caption)
                Text("Unused: \(providerLabel(combined.foreignProviders)) — \(ByteCountFormatter.string(fromByteCount: combined.foreignBytes, countStyle: .file)) in \(combined.foreignFiles.count) files")
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("If a tile deliberately mixes sources through imagery zones, keep them.")
                .scaledFont(.caption2)
                .foregroundStyle(.tertiary)
            if let trashMessage {
                Text(trashMessage)
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
            }
            Button(isTrashingImages
                   ? "Moving…"
                   : "Move All Unused Images to Trash") {
                trashAllForeignImages(combined)
            }
            .disabled(isTrashingImages || combined.foreignFiles.isEmpty)
        }
        .padding(12)
        .frame(width: 340)
    }

    private func trashAllForeignImages(_ combined: TileTextureAudit.Combined) {
        isTrashingImages = true
        trashMessage = nil
        let files = combined.foreignFiles
        let coords = combinedConflictCoords
        Task {
            let failures = await Task.detached(priority: .utility) { () -> Int in
                var failed = 0
                for url in files {
                    do {
                        try FileManager.default.trashItem(at: url, resultingItemURL: nil)
                    } catch {
                        failed += 1
                    }
                }
                return failed
            }.value
            isTrashingImages = false
            trashMessage = failures == 0
                ? "Moved \(files.count) image\(files.count == 1 ? "" : "s") to the Trash."
                : "Moved \(files.count - failures); \(failures) could not be moved."
            await refreshCombinedAudit()
            await refreshTextureAudit()
            // Clear (or confirm) every affected tile's map badge right away.
            for coord in coords { buildModel.reauditConflict(for: coord) }
        }
    }

    /// Recomputes which custom airport packages (with their own 3-D
    /// objects) sit inside the selected tiles. The pack-list filtering is
    /// cheap and runs inline; the per-pack object probe (a disk walk) runs
    /// off the main thread for the few candidates only.
    private func refreshCustomAirportPacks() async {
        let tiles = buildModel.selected
        guard !tiles.isEmpty else {
            customAirportPacks = []
            return
        }
        let tileKeys = Set(tiles.map(\.key))
        // Custom airport = a non-Laminar pack in Custom Scenery whose
        // airports (or overlay DSFs) fall in a selected tile. isLibrary is
        // deliberately NOT excluded: payware airports (Aerosoft LEMD) ship
        // a library.txt exporting their own assets while still being
        // airports — pure libraries drop out via the empty-airports guard.
        let candidates = controller.installationPacks
            .filter { pack in
                guard pack.isInstalled, !pack.isLaminar,
                      !pack.airports.isEmpty else { return false }
                return !pack.tiles.isDisjoint(with: tileKeys)
                    || pack.airports.values.contains { airport in
                        tileKeys.contains(TileMath.key(
                            lat: Int(floor(airport.latitude)),
                            lon: Int(floor(airport.longitude))))
                    }
            }
            .map { (name: $0.name, root: $0.contentRoot) }
        let names = await Task.detached(priority: .utility) {
            candidates
                .filter { PackObjectProbe.hasCustomObjects(at: $0.root) }
                .map(\.name)
                .sorted()
        }.value
        customAirportPacks = names
    }

    /// One "Modified airports" row: an airport (or, when the apt.dat
    /// names none in the tile, a whole pack) whose objects the engine's
    /// reanchor_status command reports as modified for the active tile.
    /// Undo granularity is the PACK — a multi-airport pack reverts as
    /// one unit, so its rows share a packPath.
    struct ModifiedAirportRow: Identifiable {
        let id: String            // packPath|airport label
        let label: String         // "LSZC Buochs" or the pack name
        let packName: String
        let packPath: String
        let objectCount: Int
        /// Forest definitions upgraded to 3D trees (#1360).
        var forestCount: Int = 0
    }

    /// Asks the ENGINE which packs the reseater modified for the active
    /// tile (it owns the sidecar format — identical behavior to the Qt
    /// front end), then flattens to one row per airport using the app's
    /// own airport index.
    private func refreshModifiedAirports() async {
        guard let active = buildModel.activeTile else {
            modifiedAirports = []
            return
        }
        let tileKey = active.key
        let enginePacks = await buildModel.reanchorStatus(for: active)
        guard !enginePacks.isEmpty else {
            modifiedAirports = []
            return
        }
        let installed = controller.installationPacks
        modifiedAirports = enginePacks.flatMap { pack -> [ModifiedAirportRow] in
            let match = installed.first {
                $0.url.path == pack.packPath
                    || $0.contentRoot.path == pack.packPath
            }
            let names = (match?.airports ?? [:])
                .filter { TileMath.key(latitude: $0.value.latitude,
                                       longitude: $0.value.longitude) == tileKey }
                .map { "\($0.key) \($0.value.name)" }
                .sorted()
            guard !names.isEmpty else {
                return [ModifiedAirportRow(
                    id: pack.packPath, label: pack.packName,
                    packName: pack.packName, packPath: pack.packPath,
                    objectCount: pack.objectCount,
                    forestCount: pack.forestCount)]
            }
            return names.map { name in
                ModifiedAirportRow(
                    id: "\(pack.packPath)|\(name)", label: name,
                    packName: pack.packName, packPath: pack.packPath,
                    objectCount: pack.objectCount,
                    forestCount: pack.forestCount)
            }
        }
        .sorted { $0.label < $1.label }
    }

    /// Engine-side restore of the row's pack (.anchor_bak originals put
    /// back; backups stay for the next bake, sidecar removed).
    private func revertModifiedAirports(_ row: ModifiedAirportRow) {
        Task {
            let outcome = await buildModel.reanchorRestore(packPath: row.packPath)
            if let restored = outcome.restored {
                buildModel.console.append(
                    "Restored \(restored) original object file\(restored == 1 ? "" : "s") in \(row.packName).")
            } else {
                buildModel.console.append(
                    "*** Revert failed for \(row.packName): \(outcome.error ?? "unknown error")")
            }
            reseatRefresh += 1
        }
    }

    private func legacyAlertMessage(_ legacy: BuildModel.LegacyTileSettings) -> String {
        var parts = ["Tile \(legacy.coord.key)'s settings were written by an older version of this app:"]
        for item in legacy.foreignEnums {
            parts.append("• \(item.key) = \(item.value) — not a setting of this version; currently interpreted conservatively. Updating sets: \(item.replacement.isEmpty ? "default" : item.replacement)")
        }
        for pin in legacy.missingPins {
            parts.append("• pinned elevation file no longer exists: \((pin as NSString).lastPathComponent)")
        }
        if !legacy.quotedKeys.isEmpty {
            parts.append("• legacy quoted value format (\(legacy.quotedKeys.count) setting\(legacy.quotedKeys.count == 1 ? "" : "s"))")
        }
        parts.append("Updating keeps the tile's imagery source, zoom level and zones, and resets everything else to your current global defaults (the original file is kept as a backup).")
        return parts.joined(separator: "\n")
    }

    private var providerMismatchMessage: String {
        let mismatches = buildModel.providerMismatches
        let sources = Set(mismatches.map(\.provider)).sorted().joined(separator: ", ")
        if mismatches.count == 1, let m = mismatches.first {
            return "Tile \(m.coord.key) was built with \(m.provider); you're about to build it with \(buildModel.buildProvider). Its config will record the new source once built."
        }
        return "\(mismatches.count) of the selected tiles were built with a different imagery source (\(sources)). Rebuilding with \(buildModel.buildProvider) records the new source in each tile's config."
    }

    private var buildSummary: String {
        let count = buildModel.selected.count
        guard count > 0 else { return "No tiles selected" }
        let todo = buildModel.buildableSelection.count
        let inRun = buildModel.selectedInRun.count
        var text = "\(count) tile\(count == 1 ? "" : "s")"
        if let card = airportCard {
            let airports = card.airports.count
            text += " · \(airports) airport\(airports == 1 ? "" : "s")"
            let custom = Set(card.packs.flatMap(\.airports)).count
            if custom > 0 {
                let packs = card.packs.count
                let objects = card.packs.reduce(0) { $0 + $1.objects }
                text += " · \(custom) custom airport\(custom == 1 ? "" : "s") (\(packs) pack\(packs == 1 ? "" : "s"), \(objects.formatted()) objects)"
            }
        }
        if inRun > 0 { text += " · \(inRun) in current run" }
        let skipped = count - todo - inRun
        if skipped > 0 { text += " · \(skipped) already built (skipped)" }
        return text
    }

    // MARK: - Bottom bar (the ▶ Build button lives here)

    private var bottomBar: some View {
        HStack(spacing: 8) {
            if let missing = buildModel.missingPackages, !missing.isEmpty {
                Label(EngineSetup.incompleteTitle,
                      systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .lineLimit(1)
                    .truncationMode(.tail)
                Button("Details") { showingMissingDetails = true }
                    .buttonStyle(.borderless)
                    .scaledFont(.caption)
                    .popover(isPresented: $showingMissingDetails, arrowEdge: .top) {
                        Text(EngineSetup.missingDetail(missing))
                            .textSelection(.enabled)
                            .padding(12)
                            .frame(maxWidth: 320)
                    }
                if let engine = buildModel.engine {
                    Button("Repair") { EngineSetup.run(engine) }
                        .help("Runs the engine setup (Settings ▸ General ▸ Build Engine).")
                }
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
                if buildModel.providerMismatches.isEmpty {
                    buildModel.startBuild()
                } else {
                    showingProviderMismatch = true
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(!buildModel.canBuild || buildModel.buildableSelection.isEmpty)
            // The one disabled-reason the user cannot guess from the map
            // (beta plan §1 B2): no X-Plane folder, so no CIFP, so no build.
            .help(buildModel.xplaneBlockReason ?? buildModel.planBlockReason ?? "")
            .confirmationDialog(
                "Build with a different imagery source?",
                isPresented: $showingProviderMismatch,
                titleVisibility: .visible
            ) {
                Button("Build with \(buildModel.buildProvider), keep old imagery") {
                    buildModel.startBuild()
                }
                Button("Build with \(buildModel.buildProvider), delete old imagery",
                       role: .destructive) {
                    buildModel.startBuildDeletingOldImagery()
                }
                if buildModel.providerMismatches.count > 1 || buildModel.selected.count > 1,
                   buildModel.usesProtocol {
                    Button("Build each tile with its original source") {
                        buildModel.startBuildKeepingOriginalSources()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text(providerMismatchMessage)
            }
            .help(buildButtonHelp)
        }
        .scaledFont(.callout)
        .padding(.horizontal, 12)
        .frame(height: Self.bottomBarHeight)
        .background(.bar)
    }

    private var buildButtonLabel: String {
        let n = buildModel.buildableSelection.count
        if buildModel.isBuilding, buildModel.usesProtocol {
            return n > 0 ? "＋ Queue \(n) tile\(n == 1 ? "" : "s")" : "＋ Queue"
        }
        return n > 0 ? "▶ Build \(n) tile\(n == 1 ? "" : "s")" : "▶ Build"
    }

    private var buildButtonHelp: String {
        if buildModel.selected.isEmpty { return "Select tiles on the map first" }
        if let reason = buildModel.planBlockReason { return reason }
        if buildModel.buildableSelection.isEmpty, !buildModel.selectedInRun.isEmpty {
            return "The selected tiles are already queued or building in the current run"
        }
        return "Build the selected tiles with the steps above"
    }

    // MARK: - Bindings (AppStorage on the model doesn't self-publish)

    private var providerBinding: Binding<String> {
        Binding(get: { buildModel.buildProvider },
                set: { buildModel.chooseBuildProvider($0) })
    }

    private func boolBinding(_ keyPath: ReferenceWritableKeyPath<BuildModel, Bool>) -> Binding<Bool> {
        Binding(get: { buildModel[keyPath: keyPath] },
                set: { buildModel.objectWillChange.send(); buildModel[keyPath: keyPath] = $0 })
    }
}
