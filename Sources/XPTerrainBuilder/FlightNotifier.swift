import Foundation
import SceneryKit
import UserNotifications

/// One `FlightNotice` is one system notification (spec
/// `flight-manager-and-world-20261110` §5.3, §14 "Notifications"; lane F2).
/// The Qt window posts the same through `QSystemTrayIcon.showMessage`.
/// Permission is asked once, the first time a notice arrives; a refusal
/// leaves the notice in the Fly pane only.
@MainActor
enum FlightNotifier {
    private static var asked = false

    static func post(_ notice: O4FlightNotice) {
        // An unbundled run (swift run, tests) has no notification center.
        guard Bundle.main.bundleIdentifier != nil else { return }
        let center = UNUserNotificationCenter.current()
        let content = UNMutableNotificationContent()
        content.title = notice.title
        content.body = notice.text
        if notice.severity == "warning" { content.sound = .default }
        let request = UNNotificationRequest(identifier: "\(notice.flight)-\(notice.code)-\(UUID().uuidString)",
                                            content: content, trigger: nil)
        if asked {
            center.add(request)
            return
        }
        asked = true
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            if granted { center.add(request) }
        }
    }
}
