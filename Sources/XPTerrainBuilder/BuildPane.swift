import SwiftUI
import SceneryKit

/// Right inspector pane in Build mode, mirroring the Qt front end's context
/// panel: a Selection box (active tile's details + "Installed in X-Plane"),
/// a Build box (step groups, always visible so more tiles can be queued
/// mid-run), and an Activity box (per-tile rows + run clock, only during a
/// run).
struct BuildPane: View {
    @EnvironmentObject var buildModel: BuildModel
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var showingBaseFolderPicker = ViewState(false)
    /// Custom airport packs (own 3-D objects) in the selected tiles —
    /// the packages "Modify custom airports" would reseat.
    @State private var customAirportPacks: [String] = []
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
    /// Legacy tile-settings alert: offered once per tile per app run.
    @State private var legacyTile: BuildModel.LegacyTileSettings?
    @State private var showingLegacyAlert = false
    @State private var legacyPromptShown: Set<String> = []

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
        .task(id: "\(buildModel.selected.sorted().map(\.key).joined(separator: ","))|\(controller.installationPacks.count)") {
            await refreshCustomAirportPacks()
        }
        .task(id: imageryAuditKey) {
            await refreshTextureAudit()
        }
        .task(id: "\(buildModel.activeTile?.key ?? "")|\(controller.mapOverlays.regions.count)") {
            await refreshOtherScenery()
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
        .alert("Tile built with an older Ortho4XP",
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

    /// Status only — the engine version lives in Settings.
    private var engineSubtitle: String {
        guard buildModel.engine != nil else { return "No engine configured" }
        var parts: [String] = []
        if !buildModel.usesProtocol { parts.append("legacy driver") }
        if let missing = buildModel.missingPackages, !missing.isEmpty {
            parts.append("python packages missing")
        }
        return parts.isEmpty ? "Engine ready" : parts.joined(separator: " — ")
    }

    private var noEngine: some View {
        VStack(spacing: 12) {
            Image(systemName: "globe.europe.africa")
                .font(.system(size: 36))
                .foregroundStyle(.tertiary)
            Text("No Ortho4XP engine available. The app normally uses its bundled engine — check Settings ▸ Ortho4XP if it can't be found, or choose a custom engine folder there.")
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
            HStack(spacing: 5) {
                detailRow("Imagery", info?.provider.isEmpty == false ? info!.provider : "—")
                if let audit = textureAudit, audit.hasConflict {
                    Button {
                        trashMessage = nil
                        showingImageryConflict = true
                    } label: {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.yellow)
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                    .help("Multiple imagery sources are installed in this tile")
                    .popover(isPresented: $showingImageryConflict, arrowEdge: .trailing) {
                        imageryConflictPopover(audit)
                    }
                }
            }
            detailRow("Zoom level", zlText(info))
            detailRow("Mesh built", dateText(info?.meshDate))
            detailRow("Imagery updated", dateText(info?.imageryDate))
            if let dem = info?.customDEM, !dem.isEmpty {
                detailRow("Elevation", (dem as NSString).lastPathComponent)
            }
            // Other installed ortho/mesh packages covering this tile.
            ForEach(otherScenery, id: \.name) { item in
                detailRow("Other scenery", item.name)
                    .help(item.name)
                detailRow("DSF modified", item.dsfDate.map {
                    $0.formatted(date: .abbreviated, time: .shortened)
                } ?? "—")
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
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if let combined = combinedAudit, combined.hasConflict {
                        Button {
                            trashMessage = nil
                            showingCombinedConflict = true
                        } label: {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.yellow)
                                .font(.caption)
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
        guard let info, let zl = info.zl else { return "—" }
        var text = "ZL\(zl)"
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
                ForEach(12...21, id: \.self) { zl in
                    Text("ZL\(zl)").tag(zl)
                }
            }
            .help("Higher zoom levels mean sharper imagery and much larger downloads: one ZL step ≈ 4× the data. Most sources top out below ZL21 — the map's zoom badge shows each source's ceiling.")
            Divider()
            Toggle("Vector, mesh & masks", isOn: boolBinding(\.doVector))
                .help("OSM data, elevation, triangulation and water masks — the tile's terrain.")
            Toggle("Imagery & DSF", isOn: boolBinding(\.doImagery))
                .help("Downloads imagery, converts textures and writes the final DSF.")
            Toggle("Extract overlays", isOn: boolBinding(\.doOverlays))
                .help("Extracts roads/buildings overlays from the overlay source configured in the engine config.")
            Toggle("Modify custom airports", isOn: Binding(
                get: { buildModel.modifyCustomAirports },
                set: { buildModel.setModifyCustomAirports($0) }))
                .disabled(customAirportPacks.isEmpty)
                .help(customAirportPacks.isEmpty
                      ? "No custom airport with its own 3-D objects is in the selected tiles."
                      : "Reseats the 3-D objects in the listed packages at the new ground elevation this build produces, so they neither float above nor sink into the reprofiled terrain.")
            if !customAirportPacks.isEmpty {
                Text(customAirportPacks.joined(separator: ", "))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
                    .padding(.leading, 18)
            }
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
                .font(.callout.weight(.semibold))
            Text("Only one imagery source can be used at a time; this tile's DSF references \(audit.currentProvider) textures. Images from other sources are left over from earlier builds and never shown.")
                .font(.caption)
            VStack(alignment: .leading, spacing: 2) {
                ForEach(audit.sources) { source in
                    let isCurrent = source.provider.lowercased()
                        == audit.currentProvider.lowercased()
                    Text("\(source.provider) — \(source.fileCount) file\(source.fileCount == 1 ? "" : "s"), \(ByteCountFormatter.string(fromByteCount: source.bytes, countStyle: .file))\(isCurrent ? "  (current)" : "")")
                        .font(.caption)
                        .foregroundStyle(isCurrent ? .primary : .secondary)
                }
            }
            Text("If this tile deliberately mixes sources through imagery zones, keep them.")
                .font(.caption2)
                .foregroundStyle(.tertiary)
            if let trashMessage {
                Text(trashMessage)
                    .font(.caption)
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
                .font(.callout.weight(.semibold))
            Text("\(combined.tilesWithConflict) of \(buildModel.selected.count) selected tiles carry textures from more than one source; only each tile's current source is ever shown.")
                .font(.caption)
            VStack(alignment: .leading, spacing: 2) {
                Text("In use: \(providerLabel(combined.currentProviders)) — \(ByteCountFormatter.string(fromByteCount: combined.currentBytes, countStyle: .file))")
                    .font(.caption)
                Text("Unused: \(providerLabel(combined.foreignProviders)) — \(ByteCountFormatter.string(fromByteCount: combined.foreignBytes, countStyle: .file)) in \(combined.foreignFiles.count) files")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("If a tile deliberately mixes sources through imagery zones, keep them.")
                .font(.caption2)
                .foregroundStyle(.tertiary)
            if let trashMessage {
                Text(trashMessage)
                    .font(.caption)
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

    private func legacyAlertMessage(_ legacy: BuildModel.LegacyTileSettings) -> String {
        var parts = ["Tile \(legacy.coord.key)'s settings were written by an older or different Ortho4XP:"]
        for item in legacy.foreignEnums {
            parts.append("• \(item.key) = \(item.value) — not a setting of this version; currently interpreted conservatively. Updating sets: \(item.replacement.isEmpty ? "default" : item.replacement)")
        }
        for pin in legacy.missingPins {
            parts.append("• pinned elevation file no longer exists: \((pin as NSString).lastPathComponent)")
        }
        if !legacy.quotedKeys.isEmpty {
            parts.append("• legacy quoted value format (\(legacy.quotedKeys.count) setting\(legacy.quotedKeys.count == 1 ? "" : "s"))")
        }
        if legacy.usesLegacyFileName {
            parts.append("• legacy config file name (Ortho4XP.cfg)")
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
        var text = "\(count) tile\(count == 1 ? "" : "s") selected"
        if inRun > 0 { text += " · \(inRun) in current run" }
        let skipped = count - todo - inRun
        if skipped > 0 { text += " · \(skipped) already built (skipped)" }
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
                if buildModel.providerMismatches.isEmpty {
                    buildModel.startBuild()
                } else {
                    showingProviderMismatch = true
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(!buildModel.canBuild || buildModel.buildableSelection.isEmpty)
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
        .font(.callout)
        .padding(.horizontal, 12)
        .frame(height: ResultsPane.bottomBarHeight)
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
        if buildModel.buildableSelection.isEmpty, !buildModel.selectedInRun.isEmpty {
            return "The selected tiles are already queued or building in the current run"
        }
        return "Build the selected tiles with the steps above"
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
                Text(activity.remainingUnreliable
                     ? "Remaining: estimating…"
                     : "Remaining ≈ \(activity.remainingSeconds.map(Self.clock) ?? "—")")
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
