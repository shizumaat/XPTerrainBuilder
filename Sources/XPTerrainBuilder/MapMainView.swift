import SwiftUI
import SceneryKit

/// The map-centric main window: toolbar (search / analyze), world map with
/// the X-Plane tile grid + scenery overlays, package inspector on the right,
/// results in the bottom third.
struct MapMainView: View {
    @EnvironmentObject var controller: AnalysisController
    @AppStorage("MapSceneryFilter") private var sceneryFilterRaw = MapSceneryFilter.all.rawValue
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var searchText = ViewState("")
    @StateObject private var showingPicker = ViewState(false)
    /// Native inspector visibility, persisted manually (ViewState instead of
    /// @AppStorage — the @State-family macros are unavailable on this
    /// toolchain, see ViewState.swift).
    @StateObject private var inspectorShown = ViewState(
        UserDefaults.standard.object(forKey: "InspectorShown") as? Bool ?? true)

    static let systemInfo = SystemInfo.current()

    var body: some View {
        Group {
            if controller.xplanePath.isEmpty {
                onboarding
            } else {
                // The window opens straight onto the (initially empty) map;
                // packs stream in live as the scan discovers them, and split
                // positions restore from their autosave before first display.
                mainLayout
            }
        }
        .frame(minWidth: 900, minHeight: 620)
        .navigationTitle("XPTerrainBuilder")
        .navigationSubtitle(subtitle)
        .toolbar { toolbarContent }
        .task {
            if controller.installationPacks.isEmpty {
                controller.refreshInstallation()
            }
        }
        .onChange(of: controller.xplanePath) {
            controller.installationPacks = []
            controller.refreshInstallation()
            // Fill empty engine paths (Custom Scenery, overlays, CIFP)
            // from the newly chosen X-Plane folder.
            buildModel.seedPathsFromXPlane()
        }
        .fileImporter(isPresented: $showingPicker.value, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result {
                controller.xplanePath = url.path
            }
        }
        // First run: where downloads and built tiles go. Presented until the
        // preference is set; committing the sheet sets it.
        .sheet(isPresented: Binding(
            get: { buildModel.dataRootPath.isEmpty },
            set: { _ in }
        )) {
            DataFolderSheet()
                .environmentObject(buildModel)
                .interactiveDismissDisabled()
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
        if buildModel.mode == .build {
            guard buildModel.engine != nil else {
                return "Ortho4XP engine not configured — see Settings"
            }
            // Engine version lives in Settings, not the main window chrome.
            var parts: [String] = []
            let built = buildModel.built.values.filter { $0.dsfPresent }.count
            if built > 0 { parts.append("\(built.formatted()) tile\(built == 1 ? "" : "s") built") }
            if !buildModel.installed.isEmpty {
                parts.append("\(buildModel.installed.count.formatted()) installed")
            }
            if !buildModel.selected.isEmpty {
                parts.append("\(buildModel.selected.count.formatted()) selected")
            }
            return parts.joined(separator: " — ")
        }
        if controller.isScanningInstallation { return "Scanning Custom Scenery…" }
        let packs = controller.installationPacks
        guard !packs.isEmpty else { return "" }
        let builtIn = packs.filter { $0.isLaminar }.count
        let user = packs.count - builtIn
        return "\(packs.count.formatted()) packages (\(user.formatted()) user installed, \(builtIn.formatted()) X-Plane built-in)"
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        // Manage (and its mode switcher) is disabled for now — the toolbar
        // is Build-only: refresh + imagery picker up front (own buttons,
        // away from the search cluster), search and inspector trailing.
        ToolbarItem(placement: .navigation) {
            Button {
                controller.refreshInstallation()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .help("Refresh the map's scenery overlays")
            .disabled(controller.isScanningInstallation)
        }
        ToolbarItem(placement: .navigation) {
            // Which ortho layers the map shows: our built tiles, other
            // installed ortho/mesh packages (gray outlines), or both.
            Picker("Scenery", selection: $sceneryFilterRaw) {
                ForEach(MapSceneryFilter.allCases, id: \.rawValue) { filter in
                    Text(filter.label).tag(filter.rawValue)
                }
            }
            .pickerStyle(.menu)
            .help("Show your Ortho4XP-built tiles, other installed ortho/mesh packages, or both")
        }
        ToolbarItem(placement: .navigation) {
            // Live map imagery source — independent of the build provider.
            Menu {
                Picker("Imagery Preview", selection: Binding(
                    get: { buildModel.mapPreviewProvider },
                    set: { buildModel.mapPreviewProvider = $0 }
                )) {
                    ForEach(buildModel.imagery.availableProviders, id: \.self) { code in
                        Text(code).tag(code)
                    }
                }
                .pickerStyle(.inline)
            } label: {
                Label(buildModel.imagery.activeLabel ?? "Imagery",
                      systemImage: "globe.americas.fill")
                    .labelStyle(.titleAndIcon)
            }
            .help("Choose which imagery source the map previews — independent of the provider used for building")
        }
        // Trailing edge, per the HIG (Finder/Mail put search last).
        ToolbarItem(placement: .automatic) {
            ToolbarSearchField(text: searchText,
                               placeholder: buildModel.mode == .build
                                   ? "Airport or tile like +48-006" : "Search",
                               onSubmit: performSearch)
                .frame(width: 220)
        }
        // Keep the panel toggle its own control, not glued to the search
        // cluster (modern macOS groups adjacent trailing items).
        if #available(macOS 26.0, *) {
            ToolbarSpacer(.fixed, placement: .automatic)
        }
        ToolbarItem(placement: .automatic) {
            Button {
                inspectorBinding.wrappedValue.toggle()
            } label: {
                Image(systemName: "sidebar.trailing")
            }
            .help(inspectorShown.value ? "Hide the side panel" : "Show the side panel")
        }
    }

    // MARK: - Search

    /// Zoom the map to a matching airport (ICAO or name), a tile key like
    /// "+48-006" (build mode), or a package.
    private func performSearch() {
        let query = searchText.value.trimmingCharacters(in: .whitespaces).lowercased()
        guard !query.isEmpty else { return }

        // Tile-key search, like the Qt search field.
        if buildModel.mode == .build, let tile = TileMath.parse(searchText.value.trimmingCharacters(in: .whitespaces)) {
            buildModel.click(lat: tile.lat, lon: tile.lon, command: false, shift: false)
            var cam = controller.mapCamera.value
            cam.centerLon = Double(tile.lon) + 0.5
            cam.centerLat = Double(tile.lat) + 0.5
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
            return
        }

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
            // Build mode: finding an airport also selects its tile — the
            // airport index doubles as the tile picker.
            if buildModel.mode == .build {
                buildModel.selectTile(containingLat: match.info.latitude,
                                      lon: match.info.longitude)
            }
            return
        }

        // Packages: same zoom the inspector's double-click uses.
        if let pack = controller.installationPacks.first(where: {
            $0.name.lowercased().contains(query)
        }) {
            controller.zoomToPack(pack)
        }
    }

    private var mainLayout: some View {
        // Map over results in an NSSplitView-backed split (divider persists
        // via autosaveName, restoring before first display; hosted subtrees
        // don't inherit this view's environment, so the objects are
        // re-injected per pane). The package list is a NATIVE trailing
        // inspector spanning the full window height, with the standard
        // toolbar toggle.
        RestorableSplit(orientation: .vertical, autosaveName: "MainSplit.Vertical",
                        firstMin: 300, secondMin: 180) {
            MapCanvasView(camera: controller.mapCamera,
                          canvasSize: controller.mapCanvasSize)
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .environmentObject(buildModel)
                .environmentObject(buildModel.activity)
                .environmentObject(buildModel.imagery)
        } second: {
            // Same slot both modes: results while managing, the engine
            // console while building.
            Group {
                if buildModel.mode == .manage {
                    ResultsPane(packFilter: Set(controller.viewportPacks.map { $0.name }))
                } else {
                    BuildConsoleView()
                }
            }
            .environmentObject(controller)
            .environmentObject(controller.progress)
            .environmentObject(buildModel)
        }
        .inspector(isPresented: inspectorBinding) {
            // Hairline between the map/results and the inspector — the
            // inspector container doesn't draw its own separator here.
            HStack(spacing: 0) {
                Divider()
                if buildModel.mode == .manage {
                    PackInspectorView(packs: controller.viewportPacks)
                        .environmentObject(controller)
                        .environmentObject(controller.progress)
                        .environmentObject(controller.packSizes)
                } else {
                    BuildPane()
                        .environmentObject(buildModel)
                        .environmentObject(controller)
                }
            }
            .inspectorColumnWidth(min: 240, ideal: 300, max: 420)
        }
    }

    private var inspectorBinding: Binding<Bool> {
        Binding(
            get: { inspectorShown.value },
            set: { shown in
                inspectorShown.value = shown
                UserDefaults.standard.set(shown, forKey: "InspectorShown")
            }
        )
    }

    // MARK: - Onboarding

    private var onboarding: some View {
        VStack(spacing: 14) {
            Image(systemName: "stethoscope")
                .font(.system(size: 44))
                .foregroundStyle(.tint)
            Text("XPTerrainBuilder")
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
        if field.placeholderString != placeholder {
            field.placeholderString = placeholder
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
