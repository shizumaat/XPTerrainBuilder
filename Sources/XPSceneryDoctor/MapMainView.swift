import SwiftUI
import SceneryKit

/// The map-centric main window: toolbar (search / analyze), world map with
/// the X-Plane tile grid + scenery overlays, package inspector on the right,
/// results in the bottom third.
struct MapMainView: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var camera = ViewState(MapCamera())
    @StateObject private var canvasSize = ViewState(CGSize.zero)
    @StateObject private var searchText = ViewState("")
    @StateObject private var showingPicker = ViewState(false)
    /// Packs in the visible map region, debounced from camera movement so
    /// the inspector tracks the map without re-diffing every frame.
    @StateObject private var viewportPacks = ViewState<[SceneryPack]>([])
    @StateObject private var viewportTask = ViewState<Task<Void, Never>?>(nil)

    static let systemInfo = SystemInfo.current()

    var body: some View {
        Group {
            if controller.xplanePath.isEmpty {
                onboarding
            } else {
                VSplitView {
                    HSplitView {
                        MapCanvasView(camera: camera, canvasSize: canvasSize)
                            .frame(minWidth: 480, minHeight: 300)
                            .layoutPriority(1)
                        PackInspectorView(
                            packs: controller.selectedTiles.isEmpty
                                ? viewportPacks.value
                                : controller.packsAffectingSelection(),
                            isViewportMode: controller.selectedTiles.isEmpty
                        )
                        .frame(minWidth: 240, idealWidth: 300, maxWidth: 420)
                    }
                    .layoutPriority(2)
                    ResultsPane(packFilter: Set(
                        (controller.selectedTiles.isEmpty
                            ? viewportPacks.value
                            : controller.packsAffectingSelection())
                        .map { $0.name }
                    ))
                    .frame(minHeight: 180, idealHeight: 300)
                }
                .onChange(of: camera.value) { scheduleViewportUpdate() }
                .onChange(of: canvasSize.value) { scheduleViewportUpdate() }
                .onChange(of: controller.mapOverlays.packBounds.count) { scheduleViewportUpdate() }
            }
        }
        .frame(minWidth: 900, minHeight: 620)
        .navigationTitle("XPScenery Doctor")
        .navigationSubtitle(subtitle)
        .toolbar { toolbarContent }
        .task {
            if controller.installationPacks.isEmpty {
                controller.refreshInstallation()
            }
        }
        .onChange(of: controller.xplanePath) {
            controller.selectedTiles = []
            controller.installationPacks = []
            controller.refreshInstallation()
        }
        .fileImporter(isPresented: $showingPicker.value, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result {
                controller.xplanePath = url.path
            }
        }
        .alert("Error", isPresented: .constant(controller.errorMessage != nil)) {
            Button("OK") { controller.errorMessage = nil }
        } message: {
            Text(controller.errorMessage ?? "")
        }
    }

    /// Debounced (120 ms) recompute of the packs visible in the map window.
    private func scheduleViewportUpdate() {
        viewportTask.value?.cancel()
        let cam = camera.value
        let size = canvasSize.value
        let overlays = controller.mapOverlays
        viewportTask.value = Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(120))
            guard !Task.isCancelled, size.width > 0 else { return }
            let halfW = Double(size.width) / 2 / cam.scale
            let halfH = Double(size.height) / 2 / cam.scale
            let packs = overlays.packs(inViewport: (
                minLon: cam.centerLon - halfW, maxLon: cam.centerLon + halfW,
                minLat: cam.centerLat - halfH, maxLat: cam.centerLat + halfH
            ))
            viewportPacks.value = packs.sorted { $0.name.lowercased() < $1.name.lowercased() }
        }
    }

    private var subtitle: String {
        if controller.isScanningInstallation { return "Scanning Custom Scenery…" }
        guard !controller.installationPacks.isEmpty else { return "" }
        let count = controller.installationPacks.count
        let selected = controller.selectedTiles.count
        return selected == 0
            ? "\(count) packages"
            : "\(count) packages — \(selected) tile\(selected == 1 ? "" : "s") selected"
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigation) {
            if controller.isScanningInstallation {
                ProgressView().controlSize(.small)
            }
        }
        ToolbarItem(placement: .principal) {
            TextField("Search airport or package…", text: $searchText.value)
                .textFieldStyle(.roundedBorder)
                .frame(width: 240)
                .onSubmit { performSearch() }
                .overlay(alignment: .trailing) {
                    if !searchText.value.isEmpty {
                        Button {
                            searchText.value = ""
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)
                        .padding(.trailing, 5)
                        .help("Clear search")
                    }
                }
        }
        ToolbarItem(placement: .automatic) {
            Button {
                controller.selectedTiles = []
            } label: {
                Label("Clear Selection", systemImage: "square.dashed")
            }
            .disabled(controller.selectedTiles.isEmpty)
            .help("Clear the tile selection")
        }
        ToolbarItem(placement: .primaryAction) {
            Button {
                let names = Set(controller.packsAffectingSelection().map { $0.name })
                controller.analyze(scope: names)
            } label: {
                Label("Analyze", systemImage: "waveform.path.ecg")
            }
            .disabled(controller.selectedTiles.isEmpty
                      || controller.packsAffectingSelection().isEmpty
                      || controller.isRunning)
            .help("Analyze the packages covering the selected tiles (⌘R)")
        }
        ToolbarItem(placement: .automatic) {
            Menu {
                Button("Analyze Entire Installation") { controller.analyze() }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
                    .disabled(controller.isRunning)
                Divider()
                Button("Refresh Map") { controller.refreshInstallation() }
                    .disabled(controller.isScanningInstallation)
            } label: {
                Image(systemName: "ellipsis.circle")
            }
        }
    }

    // MARK: - Search

    /// Zoom the map to a matching airport (ICAO or name) or package.
    private func performSearch() {
        let query = searchText.value.trimmingCharacters(in: .whitespaces).lowercased()
        guard !query.isEmpty else { return }

        // Airports first: exact ICAO, then prefix, then name contains.
        let airports = controller.mapOverlays.airports
        let match = airports.first { $0.icao.lowercased() == query }
            ?? airports.first { $0.icao.lowercased().hasPrefix(query) }
            ?? airports.first { $0.info.name.lowercased().contains(query) }
        if let match {
            var cam = camera.value
            cam.centerLon = match.info.longitude
            cam.centerLat = match.info.latitude
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: canvasSize.value)
            camera.value = cam
            controller.selectedTiles = [TileMath.key(latitude: match.info.latitude,
                                                     longitude: match.info.longitude)]
            return
        }

        // Packages: select all their tiles and zoom to fit.
        if let pack = controller.installationPacks.first(where: {
            $0.name.lowercased().contains(query)
        }) {
            let tiles = pack.tiles.compactMap { TileMath.parse($0) }
            let airportTiles = pack.airports.values.map {
                TileMath.key(latitude: $0.latitude, longitude: $0.longitude)
            }
            controller.selectedTiles = Set(pack.tiles).union(airportTiles)
            if !tiles.isEmpty {
                let lats = tiles.map { Double($0.lat) }, lons = tiles.map { Double($0.lon) }
                var cam = camera.value
                cam.centerLat = (lats.min()! + lats.max()! + 1) / 2
                cam.centerLon = (lons.min()! + lons.max()! + 1) / 2
                let spanLon = max(lons.max()! - lons.min()! + 1, 2)
                let spanLat = max(lats.max()! - lats.min()! + 1, 2)
                cam.scale = min(700 / spanLon, 400 / spanLat, 120)
                cam.clamp(in: canvasSize.value)
                camera.value = cam
            } else if let airport = pack.airports.values.first {
                var cam = camera.value
                cam.centerLon = airport.longitude
                cam.centerLat = airport.latitude
                cam.scale = max(cam.scale, 60)
                cam.clamp(in: canvasSize.value)
                camera.value = cam
            }
        }
    }

    // MARK: - Onboarding

    private var onboarding: some View {
        VStack(spacing: 14) {
            Image(systemName: "stethoscope")
                .font(.system(size: 44))
                .foregroundStyle(.tint)
            Text("XPScenery Doctor")
                .font(.title2.weight(.semibold))
            Text("Select your X-Plane folder to get started.")
                .foregroundStyle(.secondary)
            Button("Choose X-Plane Folder…") { showingPicker.value = true }
                .buttonStyle(.borderedProminent)
            Text(Self.systemInfo.summary)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
