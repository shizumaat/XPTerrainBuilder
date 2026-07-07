import SwiftUI

@main
struct XPSceneryDoctorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var controller = AnalysisController()

    var body: some Scene {
        Window("XPScenery Doctor", id: "main") {
            MapMainView()
                .environmentObject(controller)
                .environmentObject(controller.progress)
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
        }
    }
}

struct AppCommands: Commands {
    @ObservedObject var controller: AnalysisController
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        CommandGroup(after: .newItem) {
            Button("Analyze Selection") {
                let names = Set(controller.packsAffectingSelection().map { $0.name })
                controller.analyze(scope: names)
            }
            .keyboardShortcut("r", modifiers: .command)
            .disabled(!controller.pathIsValid || controller.isRunning
                      || controller.selectedTiles.isEmpty)

            Button("Analyze Entire Installation") {
                controller.analyze()
            }
            .keyboardShortcut("r", modifiers: [.command, .shift])
            .disabled(!controller.pathIsValid || controller.isRunning)

            Button("Export Report…") {
                controller.exportReportJSON()
            }
            .keyboardShortcut("e", modifiers: [.command, .shift])
            .disabled(controller.report == nil)
        }
        CommandGroup(after: .windowList) {
            Button("Analysis Report") {
                openWindow(id: "report")
            }
            .keyboardShortcut("1", modifiers: [.command, .option])
            .disabled(controller.report == nil)

            Button("Modifications") {
                openWindow(id: "modifications")
            }
            .keyboardShortcut("2", modifiers: [.command, .option])
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
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
