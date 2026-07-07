import SwiftUI
import SceneryKit

/// The map-centric main window: toolbar (search / analyze), world map with
/// the X-Plane tile grid + scenery overlays, package inspector on the right,
/// results in the bottom third.
struct MapMainView: View {
    @EnvironmentObject var controller: AnalysisController
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
        .navigationTitle("XPScenery Doctor")
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
        return "\(controller.installationPacks.count) packages"
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
            Menu {
                // Analysis runs by itself; these force a fresh pass past the
                // cache when something looks stale.
                Button("Re-analyze Packages in View") {
                    controller.analyze(scope: Set(controller.viewportPacks.map { $0.name }))
                }
                .disabled(controller.isRunning || controller.viewportPacks.isEmpty)
                Button("Analyze Entire Installation") { controller.analyze() }
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
                               placeholder: "Search",
                               onSubmit: performSearch)
                .frame(width: 220)
        }
        ToolbarItem(placement: .automatic) {
            Button {
                inspectorBinding.wrappedValue.toggle()
            } label: {
                Image(systemName: "sidebar.trailing")
            }
            .help(inspectorShown.value ? "Hide the package list" : "Show the package list")
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
        } second: {
            ResultsPane(packFilter: Set(controller.viewportPacks.map { $0.name }))
            .environmentObject(controller)
            .environmentObject(controller.progress)
        }
        .inspector(isPresented: inspectorBinding) {
            // Hairline between the map/results and the package list — the
            // inspector container doesn't draw its own separator here.
            HStack(spacing: 0) {
                Divider()
                PackInspectorView(packs: controller.viewportPacks)
                    .environmentObject(controller)
                    .environmentObject(controller.progress)
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
