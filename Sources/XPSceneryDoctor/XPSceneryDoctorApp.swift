import SwiftUI

@main
struct XPSceneryDoctorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var controller = AnalysisController()

    var body: some Scene {
        Window("XPScenery Doctor", id: "main") {
            MainView()
                .environmentObject(controller)
        }
        .windowResizability(.contentSize)
        .defaultPosition(.center)
        .commands {
            AppCommands(controller: controller)
        }

        Window("Analysis Report", id: "report") {
            ReportWindow()
                .environmentObject(controller)
        }
        .defaultSize(width: 960, height: 640)

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
            Button("Analyze") {
                controller.analyze()
            }
            .keyboardShortcut("r", modifiers: .command)
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
        }
    }
}

/// Makes the app behave like a regular GUI app even when the binary is
/// launched from a terminal (SwiftPM `swift run`) rather than the .app bundle.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
