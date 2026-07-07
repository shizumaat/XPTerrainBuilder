import SwiftUI
import SceneryKit

/// The map-centric main window: toolbar (search / analyze), world map with
/// the X-Plane tile grid + scenery overlays, package inspector on the right,
/// results in the bottom third.
struct MapMainView: View {
    @EnvironmentObject var controller: AnalysisController
    @StateObject private var searchText = ViewState("")
    @StateObject private var showingPicker = ViewState(false)

    static let systemInfo = SystemInfo.current()

    var body: some View {
        Group {
            if controller.xplanePath.isEmpty {
                onboarding
            } else {
                // The real split layout mounts (and settles its pane sizes)
                // underneath an opaque loading cover from the very first
                // frame; the cover fades once the scan lands, so the user
                // never sees the splits mid-layout or panes without data.
                ZStack {
                    mainLayout
                    if !controller.hasScannedInstallation {
                        loadingCover
                            .transition(.opacity)
                    }
                }
                .animation(.easeOut(duration: 0.3), value: controller.hasScannedInstallation)
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
            controller.hasScannedInstallation = false
            controller.refreshInstallation()
        }
        .fileImporter(isPresented: $showingPicker.value, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result {
                controller.xplanePath = url.path
            }
        }
        .alert("Error", isPresented: Binding(
            get: { controller.errorMessage != nil },
            set: { if !$0 { controller.errorMessage = nil } }
        )) {
            Button("OK") { controller.errorMessage = nil }
        } message: {
            Text(controller.errorMessage ?? "")
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
        // Trailing edge, per the HIG (Finder/Mail put search last).
        ToolbarItem(placement: .automatic) {
            ToolbarSearchField(text: searchText,
                               placeholder: "Search airport or package…",
                               onSubmit: performSearch)
                .frame(width: 220)
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
            var cam = controller.mapCamera.value
            cam.centerLon = match.info.longitude
            cam.centerLat = match.info.latitude
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
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
                var cam = controller.mapCamera.value
                cam.centerLat = (lats.min()! + lats.max()! + 1) / 2
                cam.centerLon = (lons.min()! + lons.max()! + 1) / 2
                let spanLon = max(lons.max()! - lons.min()! + 1, 2)
                let spanLat = max(lats.max()! - lats.min()! + 1, 2)
                cam.scale = min(700 / spanLon, 400 / spanLat, 120)
                cam.clamp(in: controller.mapCanvasSize.value)
                controller.mapCamera.value = cam
            } else if let airport = pack.airports.values.first {
                var cam = controller.mapCamera.value
                cam.centerLon = airport.longitude
                cam.centerLat = airport.latitude
                cam.scale = max(cam.scale, 60)
                cam.clamp(in: controller.mapCanvasSize.value)
                controller.mapCamera.value = cam
            }
        }
    }

    private var mainLayout: some View {
        VSplitView {
            HSplitView {
                MapCanvasView(camera: controller.mapCamera,
                              canvasSize: controller.mapCanvasSize)
                    .frame(minWidth: 480, minHeight: 300)
                    .layoutPriority(1)
                PackInspectorView(
                    packs: controller.selectedTiles.isEmpty
                        ? controller.viewportPacks
                        : controller.packsAffectingSelection(),
                    isViewportMode: controller.selectedTiles.isEmpty
                )
                .frame(minWidth: 240, idealWidth: 300, maxWidth: 420)
            }
            .layoutPriority(2)
            ResultsPane(packFilter: Set(
                (controller.selectedTiles.isEmpty
                    ? controller.viewportPacks
                    : controller.packsAffectingSelection())
                .map { $0.name }
            ))
            .frame(minHeight: 180, idealHeight: 300)
        }
    }

    // MARK: - Loading cover

    /// Facsimile of the final layout with fixed pane sizes (no split views —
    /// nothing to settle): the empty night-chart world with a determinate
    /// scan progress bar, and pulsing placeholder bars where the inspector
    /// and results will appear.
    private var loadingCover: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                LoadingMapPlaceholder()
                Divider()
                SkeletonPane(rows: 14)
                    .frame(width: 300)
            }
            Divider()
            SkeletonPane(rows: 5)
                .frame(height: 260)
        }
        .background(Color(nsColor: .windowBackgroundColor))
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

/// The genuine AppKit search control, wrapped: correct placeholder
/// metrics, magnifier, clear button, ESC handling — for free.
struct ToolbarSearchField: NSViewRepresentable {
    /// Posted by the Edit ▸ Find menu (⌘F) to focus the field.
    static let focusNotification = Notification.Name("XPSDFocusSearch")

    @ObservedObject var text: ViewState<String>
    let placeholder: String
    let onSubmit: () -> Void

    func makeNSView(context: Context) -> NSSearchField {
        let field = NSSearchField()
        field.placeholderString = placeholder
        field.controlSize = .regular
        // Action fires on Return (and on clear), not per keystroke.
        field.sendsWholeSearchString = true
        field.target = context.coordinator
        field.action = #selector(Coordinator.submitted(_:))
        field.delegate = context.coordinator
        context.coordinator.observeFocusRequests(for: field)
        return field
    }

    func updateNSView(_ field: NSSearchField, context: Context) {
        if field.stringValue != text.value {
            field.stringValue = text.value
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    final class Coordinator: NSObject, NSSearchFieldDelegate {
        let parent: ToolbarSearchField
        private var focusObserver: NSObjectProtocol?

        init(_ parent: ToolbarSearchField) {
            self.parent = parent
        }

        deinit {
            if let focusObserver {
                NotificationCenter.default.removeObserver(focusObserver)
            }
        }

        func observeFocusRequests(for field: NSSearchField) {
            focusObserver = NotificationCenter.default.addObserver(
                forName: ToolbarSearchField.focusNotification, object: nil, queue: .main
            ) { [weak field] _ in
                guard let field, field.window?.isKeyWindow == true else { return }
                field.window?.makeFirstResponder(field)
            }
        }

        func controlTextDidChange(_ notification: Notification) {
            guard let field = notification.object as? NSSearchField else { return }
            parent.text.value = field.stringValue
        }

        @objc func submitted(_ sender: NSSearchField) {
            parent.text.value = sender.stringValue
            if !sender.stringValue.isEmpty {
                parent.onSubmit()
            }
        }
    }
}

/// The empty night-chart world (coarse coastlines, no overlays) with the
/// installation-scan progress centered on it. Observes ProgressModel — the
/// high-frequency ticks stay contained here.
struct LoadingMapPlaceholder: View {
    @EnvironmentObject var progressModel: ProgressModel

    private var progress: (done: Int, total: Int)? { progressModel.scanProgress }

    var body: some View {
        ZStack {
            Canvas(rendersAsynchronously: false) { context, size in
                let cam = MapCamera.fitted(to: size)
                var landPath = Path()
                for ring in LandData.polygons {
                    guard let first = ring.first else { continue }
                    landPath.move(to: cam.point(lon: first.x, lat: first.y, in: size))
                    for pt in ring.dropFirst() {
                        landPath.addLine(to: cam.point(lon: pt.x, lat: pt.y, in: size))
                    }
                    landPath.closeSubpath()
                }
                context.fill(landPath, with: .color(MapCanvasView.land))
                context.stroke(landPath, with: .color(MapCanvasView.coast), lineWidth: 1)
            }
            .background(MapCanvasView.ocean)

            VStack(spacing: 10) {
                Text("Reading Your Scenery")
                    .font(.headline)
                    .foregroundStyle(.white.opacity(0.92))
                if let progress, progress.total > 0 {
                    ProgressView(value: Double(progress.done), total: Double(progress.total))
                        .frame(width: 280)
                    Text("\(progress.done.formatted()) of \(progress.total.formatted()) packages")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.white.opacity(0.65))
                } else {
                    ProgressView()
                        .progressViewStyle(.linear)
                        .frame(width: 280)
                    Text("Listing Custom Scenery…")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.65))
                }
            }
            .padding(22)
            .background(.black.opacity(0.55), in: RoundedRectangle(cornerRadius: 12))
        }
    }
}

/// Pulsing gray placeholder bars standing in for a pane that has no data yet.
struct SkeletonPane: View {
    let rows: Int
    @StateObject private var pulsing = ViewState(false)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(0..<rows, id: \.self) { i in
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.primary.opacity(0.09))
                    .frame(height: 13)
                    // Deterministic ragged widths so it reads as text lines.
                    .containerRelativeFrame(.horizontal) { width, _ in
                        width * (0.45 + Double((i * 37) % 45) / 100)
                    }
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .opacity(pulsing.value ? 0.45 : 1)
        .animation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true), value: pulsing.value)
        .onAppear { pulsing.value = true }
    }
}
