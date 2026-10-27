import SwiftUI
import AppKit
import SceneryKit

/// The map-centric main window: toolbar (search / analyze), world map with
/// the X-Plane tile grid + scenery overlays, package inspector on the right,
/// results in the bottom third.
struct MapMainView: View {
    @EnvironmentObject var controller: AnalysisController
    @AppStorage("MapSceneryFilter") private var sceneryFilterRaw = MapSceneryFilter.all.rawValue
    @EnvironmentObject var buildModel: BuildModel
    @StateObject private var searchText = ViewState("")
    /// The point a coordinate search went to (#1317); nil = no reticle.
    @StateObject private var searchReticle = ViewState<SearchReticle?>(nil)
    /// The codes an airport-code list did not find (#542), shown as an
    /// alert after the rest are selected; empty = no alert.
    @StateObject private var unknownCodesMessage = ViewState("")
    @StateObject private var showingPicker = ViewState(false)
    /// Why the last folder the user picked was not accepted (empty = none).
    @StateObject private var rejectedFolder = ViewState("")
    /// X-Plane installs found on this Mac for the first-run screen (#819).
    @StateObject private var foundInstalls = ViewState<[String]>([])
    /// Native inspector visibility, persisted manually (ViewState instead of
    /// @AppStorage — the @State-family macros are unavailable on this
    /// toolchain, see ViewState.swift).
    @StateObject private var inspectorShown = ViewState(
        UserDefaults.standard.object(forKey: "InspectorShown") as? Bool ?? true)

    static let systemInfo = SystemInfo.current()

    var body: some View {
        Group {
            // First run, step 2 (after the data-folder sheet below): a VALID
            // X-Plane folder is required before anything can be built — with
            // no CIFP corpus the engine refuses the tile outright (beta plan
            // §1 B2). "Non-empty" was not enough: a wrong folder passed.
            if XPlaneInstall.problem(at: controller.xplanePath) != nil {
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
            // A different X-Plane folder is a different Global Airports
            // apt.dat: ask the engine to re-index it.
            buildModel.refreshAirportIndex()
        }
        .fileImporter(isPresented: $showingPicker.value, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result { acceptXPlaneFolder(url.path) }
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
        // Airports on a tile edge (protocol 1.8): one sheet per build press,
        // whichever entry point started it — so it covers a resume too.
        .sheet(item: Binding(
            get: { buildModel.boundaryPrompt },
            set: { if $0 == nil { buildModel.boundaryPrompt = nil } }
        )) { prompt in
            BoundaryAirportsSheet(prompt: prompt) { choice, remember in
                buildModel.answerBoundaryPrompt(choice, remember: remember)
            }
            .interactiveDismissDisabled()
        }
        // Tiles not built / built with warnings (protocol 1.10, #562, #564).
        .sheet(item: $buildModel.runIssues) { issues in
            RunIssuesSheet(issues: issues, buildModel: buildModel) {
                buildModel.runIssues = nil
            }
        }
        // A tile that failed with a cause the user can fix, asked as soon
        // as it fails (#695).
        .modifier(LinkFixAlert(buildModel: buildModel))
        // A pack X-Plane will not load (protocol 1.9, #433): owner-fixed
        // copy; the primary button only when the art can be omitted.
        .alert(buildModel.packArtPrompt?.titleText ?? "", isPresented: Binding(
            get: { buildModel.packArtPrompt != nil },
            set: { _ in }
        ), presenting: buildModel.packArtPrompt) { art in
            if art.canOmit {
                Button(O4PackMissingArtCopy.primaryButton) {
                    buildModel.answerPackArtPrompt(omit: true)
                }
            }
            Button(O4PackMissingArtCopy.secondaryButton, role: .cancel) {
                buildModel.answerPackArtPrompt(omit: false)
            }
        } message: { art in
            Text(art.canOmit
                 ? art.bodyText + "\n\n" + O4PackMissingArtCopy.detail
                 : art.bodyText)
        }
        .alert("Error", isPresented: Binding(
            get: { controller.errorMessage != nil },
            set: { if !$0 { controller.errorMessage = nil } }
        )) {
            Button("OK") { controller.errorMessage = nil }
        } message: {
            Text(controller.errorMessage ?? "")
        }
        .modifier(UnknownCodesAlert(message: unknownCodesMessage))
    }

    private var subtitle: String {
        guard buildModel.engine != nil else {
            return "Build engine not configured — see Settings"
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

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        // Imagery picker up front (its own button, away from the search
        // cluster), search and inspector trailing.  No refresh button
        // (#1258): the Custom Scenery watcher rescans on any change.
        ToolbarItem(placement: .navigation) {
            // Live map imagery source — independent of the build provider.
            Menu {
                Picker("Imagery Preview", selection: Binding(
                    get: { buildModel.mapPreviewProvider },
                    set: { buildModel.mapPreviewProvider = $0 }
                )) {
                    // The engine's one list (#1345): sources the map can't
                    // draw, or that didn't answer at launch, show greyed
                    // with the reason.
                    ForEach(ImageryMenu.sections(ImageryMenu.entries(
                        buildModel.imagerySources, statuses: buildModel.imageryStatus,
                        forMap: true))) { section in
                        Section(section.title) {
                            ForEach(section.entries) { entry in
                                Text(entry.label).tag(entry.code)
                                    .disabled(!entry.enabled)
                                    .help(entry.tooltip)
                            }
                        }
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
        // Trailing edge, per the HIG (Finder/Mail put search last). The
        // scenery-layer filter sits just left of search, standard filter
        // icon (filled while a filter is active).
        ToolbarItem(placement: .automatic) {
            Menu {
                Picker("Scenery", selection: $sceneryFilterRaw) {
                    ForEach(MapSceneryFilter.allCases, id: \.rawValue) { filter in
                        Text(filter.label).tag(filter.rawValue)
                    }
                }
                .pickerStyle(.inline)
            } label: {
                Image(systemName: sceneryFilterRaw == MapSceneryFilter.all.rawValue
                      ? "line.3.horizontal.decrease.circle"
                      : "line.3.horizontal.decrease.circle.fill")
            }
            .help("Show the tiles you built, other installed ortho/mesh packages, or both")
        }
        ToolbarItem(placement: .automatic) {
            ToolbarSearchField(text: searchText,
                               placeholder: "Airport, tile like +48-006, or lat, lon",
                               onSubmit: performSearch,
                               onClear: { searchReticle.value = nil })
                .frame(width: 220)
                .help("Several airport codes (KCLT, KASE OTHH) select all their tiles at once; "
                      + "a latitude and longitude (49.0127, 2.5582 or 49°00'45.6\"N 2°33'29.4\"E) "
                      + "centres the map there")
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
    /// "+48-006", a typed latitude and longitude (#1317), a list of airport
    /// codes ("KCLT, KASE OTHH" — every tile they touch), or a package.
    private func performSearch() {
        let query = searchText.value.trimmingCharacters(in: .whitespaces).lowercased()
        guard !query.isEmpty else { return }
        searchReticle.value = nil

        // Tile key, then a point (CoordinateQuery, shared with the Qt field).
        switch CoordinateQuery.parse(searchText.value) {
        case let .tile(lat, lon)?:
            buildModel.click(lat: lat, lon: lon, command: false, shift: false)
            var cam = controller.mapCamera.value
            cam.centerLon = Double(lon) + 0.5
            cam.centerLat = Double(lat) + 0.5
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
            return
        case let .point(lat, lon)?:
            // Centre at ZL 19 under a reticle; the text stays, so Esc
            // (or the clear button) clears both.
            var cam = controller.mapCamera.value
            cam.centerLon = lon
            cam.centerLat = lat
            cam.scale = MapCamera.pixelsPerDegree(zoomLevel: CoordinateQuery.zoomLevel)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
            searchReticle.value = SearchReticle(lat: lat, lon: lon)
            return
        case nil:
            break
        }

        // A list of codes selects all their tiles; one code (or a name)
        // falls through to the single-airport search below, unchanged.
        if let batch = AirportCodeList.resolve(searchText.value, lookup: airportCodeLookup()) {
            selectAirportBatch(batch)
            return
        }

        // Code or name, best match first (#543): the list's first row.
        if let best = buildModel.airportSearch.results(for: searchText.value, limit: 1).first {
            selectAirport(best)
            return
        }

        // Finding an airport also selects its tile — the airport index
        // doubles as the tile picker.
        func zoomAndSelect(_ info: AirportInfo, code: String) {
            var cam = controller.mapCamera.value
            cam.centerLon = info.longitude
            cam.centerLat = info.latitude
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
            buildModel.selectTile(containingLat: info.latitude, lon: info.longitude)
            let tile = AirportTile(lat: Int(floor(info.latitude)), lon: Int(floor(info.longitude)))
            buildModel.searchTags.add([tile: [code.uppercased()]])
        }

        // Custom-pack airports the index lacks: exact ICAO, then prefix,
        // then name contains.
        let airports = controller.mapOverlays.airports
        let match = airports.first { $0.icao.lowercased() == query }
            ?? airports.first { $0.icao.lowercased().hasPrefix(query) }
            ?? airports.first { $0.info.name.lowercased().contains(query) }
        if let match {
            zoomAndSelect(match.info, code: match.icao)
            return
        }

        // Packages: same zoom the inspector's double-click uses.
        if let pack = controller.installationPacks.first(where: {
            $0.name.lowercased().contains(query)
        }) {
            controller.zoomToPack(pack)
        }
    }

    /// A search result was chosen (#543): select (adding, as a search
    /// does) every tile the airport touches, its datum tile active, tag
    /// them with its code, and frame it.
    private func selectAirport(_ airport: GlobalAirport) {
        let datum = AirportTile(lat: Int(floor(airport.latitude)), lon: Int(floor(airport.longitude)))
        let tiles = [datum] + AirportCodeList.tiles(latitude: airport.latitude,
                                                     longitude: airport.longitude,
                                                     extent: airport.extent).filter { $0 != datum }
        buildModel.selectTiles(tiles.map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) })
        buildModel.searchTags.add(Dictionary(uniqueKeysWithValues: tiles.map { ($0, [airport.icao.uppercased()]) }))
        if tiles.count == 1 {
            var cam = controller.mapCamera.value
            cam.centerLon = airport.longitude
            cam.centerLat = airport.latitude
            cam.scale = max(cam.scale, 60)
            cam.clamp(in: controller.mapCanvasSize.value)
            controller.mapCamera.value = cam
        } else {
            controller.zoomToTiles(tiles.map { (lat: $0.lat, lon: $0.lon) })
        }
        searchText.value = ""
    }

    /// Text the field handles without the airport list: a tile key, a
    /// coordinate, or a list of codes.
    private func searchHandledElsewhere(_ text: String) -> Bool {
        CoordinateQuery.parse(text) != nil
            || AirportCodeList.resolve(text, lookup: airportCodeLookup()) != nil
    }

    /// Code → tiles for a code list: the Global Airports index (which
    /// carries each airport's extent), then the custom packs' airports
    /// (a point each) for codes the index lacks.
    private func airportCodeLookup() -> (String) -> [AirportTile]? {
        let custom = controller.mapOverlays.airports
        return AirportCodeList.lookup(buildModel.globalAirports) { code in
            custom.first { $0.icao.uppercased() == code }.map {
                AirportCodeList.tiles(latitude: $0.info.latitude,
                                      longitude: $0.info.longitude, extent: nil)
            }
        }
    }

    /// Select (adding to the selection, as a single airport does) every
    /// tile of a code list, frame them, and alert on the codes that were
    /// not found (owner decision on #542) — the text stays in the field
    /// then, to be corrected.
    private func selectAirportBatch(_ batch: AirportBatch) {
        let tiles = batch.tiles.map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) }
        if !tiles.isEmpty {
            buildModel.selectTiles(tiles)
            buildModel.searchTags.add(batch.picks)
            controller.zoomToTiles(batch.tiles.map { (lat: $0.lat, lon: $0.lon) })
        }
        if batch.unknown.isEmpty { searchText.value = "" }
        unknownCodesMessage.value = batch.unknownCodesMessage ?? ""
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
                .overlay {
                    SearchReticleOverlay(reticle: searchReticle, camera: controller.mapCamera)
                }
                .overlay(alignment: .top) {
                    MapHintOverlay().environmentObject(buildModel)
                }
                .overlay(alignment: .topTrailing) {
                    AirportSearchResults(text: searchText, search: buildModel.airportSearch,
                                         handledElsewhere: searchHandledElsewhere,
                                         onPick: selectAirport)
                }
                .overlay(alignment: .topLeading) {
                    // Select from flight plan (#829): over the map, not a
                    // sheet, so the selection is watched as the radius moves.
                    FlightPlanPanel(model: buildModel.flightPlan) { tiles in
                        controller.zoomToTiles(tiles.map { (lat: $0.lat, lon: $0.lon) })
                    }
                }
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .environmentObject(buildModel)
                .environmentObject(buildModel.activity)
                .environmentObject(buildModel.imagery)
        } second: {
            BuildConsoleView()
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .environmentObject(buildModel)
        }
        .inspector(isPresented: inspectorBinding) {
            // Hairline between the map/console and the inspector — the
            // inspector container doesn't draw its own separator here.
            HStack(spacing: 0) {
                Divider()
                BuildPane()
                    .environmentObject(buildModel)
                    .environmentObject(controller)
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
            Image(nsImage: NSApplication.shared.applicationIconImage)
                .resizable()
                .frame(width: 64, height: 64)
            Text("XPTerrainBuilder")
                .font(.title2.weight(.semibold))
            Text("Select your X-Plane folder to get started.")
                .foregroundStyle(.secondary)
            Text("XPTerrainBuilder reads X-Plane's own airport and runway data to grade "
                 + "runways, taxiways and aprons. Without it every airport would "
                 + "drape over the raw terrain, so a build cannot start.")
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 440)
            ForEach(foundInstalls.value, id: \.self) { path in
                Button("Found X-Plane at \(path) — Use it") { acceptXPlaneFolder(path) }
                    .buttonStyle(.borderedProminent)
            }
            if foundInstalls.value.isEmpty {
                Button("Choose X-Plane Folder…") { showingPicker.value = true }
                    .buttonStyle(.borderedProminent)
            } else {
                Button("Choose another…") { showingPicker.value = true }
            }
            if !rejectedFolder.value.isEmpty {
                Text(rejectedFolder.value)
                    .font(.callout)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 440)
            }
            // The preset cards (#822): the first choice a new user makes.
            PresetCardsView()
                .frame(maxWidth: 640)
                .padding(.top, 8)
            Text(Self.systemInfo.summary)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            foundInstalls.value = XPlaneInstall.detectInstalls()
            buildModel.applyDefaultPresetIfUnset()
        }
    }

    /// Validated before it is accepted — the picker and the found-install
    /// buttons alike: an invalid folder would otherwise seed nothing and
    /// leave Build permanently off with no explanation.
    private func acceptXPlaneFolder(_ path: String) {
        if let problem = XPlaneInstall.problem(at: path) {
            rejectedFolder.value = problem
        } else {
            rejectedFolder.value = ""
            controller.xplanePath = path
        }
    }
}

/// The alert an airport-code list raises for codes it could not identify
/// (owner decision on #542); empty message = no alert. A modifier of its
/// own so `MapMainView.body` stays cheap to type-check.
struct UnknownCodesAlert: ViewModifier {
    @ObservedObject var message: ViewState<String>

    func body(content: Content) -> some View {
        content.alert(AirportBatch.unknownCodesTitle, isPresented: isPresented) {
            Button("OK") { message.value = "" }
        } message: {
            Text(message.value)
        }
    }

    private var isPresented: Binding<Bool> {
        Binding(get: { !message.value.isEmpty },
                set: { if !$0 { message.value = "" } })
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
    /// The field was emptied (Esc, its clear button, or deleting the text).
    var onClear: () -> Void = {}

    func makeNSView(context: Context) -> NSSearchField {
        let field = Self.makeField(placeholder: placeholder)
        // Action fires on Return (and on clear), not per keystroke.
        field.sendsWholeSearchString = true
        field.target = context.coordinator
        field.action = #selector(Coordinator.submitted(_:))
        field.delegate = context.coordinator
        context.coordinator.observeFocusRequests(for: field)
        return field
    }

    /// The bare control. Long text scrolls horizontally inside the field
    /// instead of being clipped at its right edge (#1224).
    static func makeField(placeholder: String) -> NSSearchField {
        let field = NSSearchField()
        field.placeholderString = placeholder
        field.controlSize = .regular
        field.usesSingleLineMode = true
        field.lineBreakMode = .byClipping
        field.cell?.isScrollable = true
        field.cell?.wraps = false
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
            if field.stringValue.isEmpty { parent.onClear() }
        }

        @objc func submitted(_ sender: NSSearchField) {
            parent.text.value = sender.stringValue
            if !sender.stringValue.isEmpty {
                parent.onSubmit()
            } else {
                parent.onClear()
            }
        }
    }
}
