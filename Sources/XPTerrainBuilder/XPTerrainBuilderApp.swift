import SwiftUI

@main
struct XPTerrainBuilderApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var controller = AnalysisController()
    @StateObject private var buildModel = BuildModel()

    var body: some Scene {
        Window("XPTerrainBuilder", id: "main") {
            MapMainView()
                .environmentObject(controller)
                .environmentObject(controller.progress)
                .environmentObject(buildModel)
        }
        .defaultSize(width: 1280, height: 860)
        .defaultPosition(.center)
        .commands {
            AppCommands(controller: controller)
        }

        Window("Analysis Report", id: "report") {
            ReportWindow()
                .environmentObject(controller)
                .environmentObject(controller.progress)
        }
        .defaultSize(width: 960, height: 640)

        Window("Modifications", id: "modifications") {
            ModificationsWindow()
                .environmentObject(controller)
        }
        .defaultSize(width: 640, height: 400)

        Settings {
            SettingsView()
                .environmentObject(buildModel)
        }
    }
}

struct AppCommands: Commands {
    @ObservedObject var controller: AnalysisController
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        // Manage (analysis/report/modifications) commands are disabled for
        // now along with the Manage mode itself.
        CommandGroup(after: .textEditing) {
            Button("Find") {
                NotificationCenter.default.post(name: ToolbarSearchField.focusNotification,
                                                object: nil)
            }
            .keyboardShortcut("f", modifiers: .command)
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
}
