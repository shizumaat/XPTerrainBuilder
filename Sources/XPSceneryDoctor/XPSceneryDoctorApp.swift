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

        Settings {
            SettingsView()
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
