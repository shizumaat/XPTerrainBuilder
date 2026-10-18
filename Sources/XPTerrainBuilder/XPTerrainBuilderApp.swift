import SwiftUI
import SceneryKit

@main
struct XPTerrainBuilderApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var controller: AnalysisController
    @StateObject private var buildModel: BuildModel

    init() {
        let controller = AnalysisController()
        let buildModel = BuildModel()
        // X-Plane's default airports come from the ENGINE's index (the
        // `airport_index` command): BuildModel owns the session that asks
        // for it, the map controller owns the marks and the search.
        buildModel.onGlobalAirports = { [weak controller] airports in
            controller?.setGlobalAirports(airports)
        }
        _controller = StateObject(wrappedValue: controller)
        _buildModel = StateObject(wrappedValue: buildModel)
    }

    var body: some Scene {
        Window("XPTerrainBuilder", id: "main") {
            MapMainView()
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .environmentObject(buildModel)
                .textScaleRoot()
        }
        .defaultSize(width: 1280, height: 860)
        .defaultPosition(.center)
        .commands {
            AppCommands(controller: controller, buildModel: buildModel)
        }

        // The patch editor's 3D preview (#46, spec §5): one window,
        // opened by the map's "3D" button or ⌘3.
        WindowGroup("3D Preview", id: TerrainPreview.windowID, for: String.self) { _ in
            TerrainPreviewWindow()
                .environmentObject(buildModel)
        }
        .defaultSize(width: 1000, height: 640)

        // Analysis Report and Modifications windows removed — the scenery
        // doctor is planned as a separate app.
        Settings {
            SettingsView()
                .environmentObject(buildModel)
        }
    }
}

struct AppCommands: Commands {
    @ObservedObject var controller: AnalysisController
    @ObservedObject var buildModel: BuildModel
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        // The stock About panel shows the app version alone; a beta report
        // needs the engine version and the commit with it (see AboutPanel).
        CommandGroup(replacing: .appInfo) {
            Button("About XPTerrainBuilder") {
                AboutPanel.show(engineVersion: buildModel.schema.engineVersion)
            }
        }

        // Manage (analysis/report/modifications) commands are disabled for
        // now along with the Manage mode itself.
        CommandGroup(after: .textEditing) {
            Button("Find") {
                NotificationCenter.default.post(name: ToolbarSearchField.focusNotification,
                                                object: nil)
            }
            .keyboardShortcut("f", modifiers: .command)
        }

        // The patch editor's ⌘S (#46): saves the edited patch.
        CommandGroup(replacing: .saveItem) {
            PatchSaveCommand(model: buildModel.patchEdit)
        }

        // Brings the map's first-visit hint back (#828).
        CommandGroup(after: .help) {
            Button(MapGuidance.showTipsTitle) {
                UserDefaults.standard.set(false, forKey: PrefKeys.mapHintDismissed)
            }
        }

        CommandGroup(after: .toolbar) {
            Button("3D Preview") {
                openWindow(id: TerrainPreview.windowID, value: TerrainPreview.windowValue)
            }
            .keyboardShortcut("3", modifiers: .command)
            // View ▸ Bigger / Smaller / Actual Size text (#827).
            Divider()
            TextScaleCommands()
        }
    }
}

/// User-facing appearance override (Settings ▸ Appearance). "system" follows
/// the OS light/dark mode; explicit values pin the app, Proxyman-style.
enum AppearanceSetting: String, CaseIterable {
    case system, light, dark

    static let prefKey = "Appearance"

    var label: String {
        switch self {
        case .system: return "System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }

    func apply() {
        switch self {
        case .system: NSApp.appearance = nil
        case .light: NSApp.appearance = NSAppearance(named: .aqua)
        case .dark: NSApp.appearance = NSAppearance(named: .darkAqua)
        }
    }

    static func applyCurrent() {
        let raw = UserDefaults.standard.string(forKey: prefKey) ?? ""
        (AppearanceSetting(rawValue: raw) ?? .system).apply()
    }
}

/// Makes the app behave like a regular GUI app even when the binary is
/// launched from a terminal (SwiftPM `swift run`) rather than the .app bundle.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        AppearanceSetting.applyCurrent()
        // Icon comes entirely from the system pipeline now (Assets.car
        // Liquid Glass icon + icns fallback) — no runtime overrides. Clear
        // any custom bundle icon a previous freeform-era build assigned.
        let path = Bundle.main.bundlePath
        if UserDefaults.standard.string(forKey: "AppliedFreeformIcon") != nil,
           FileManager.default.isWritableFile(atPath: path) {
            NSWorkspace.shared.setIcon(nil, forFile: path, options: [])
            UserDefaults.standard.removeObject(forKey: "AppliedFreeformIcon")
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    /// Unsaved patch edits (#46) ask in the map before the app quits.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        MainActor.assumeIsolated { PatchEditModel.current?.shouldTerminate() ?? .terminateNow }
    }
}
