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
        post(title: notice.title, body: notice.text, id: "\(notice.flight)-\(notice.code)",
             sound: notice.severity == "warning")
    }

    /// Any notice of the app as one notification (a pack's shipped package,
    /// RULINGS 2026-11-11m (4), uses it too).
    static func post(title: String, body: String, id: String, sound: Bool = false) {
        // An unbundled run (swift run, tests) has no notification center.
        guard Bundle.main.bundleIdentifier != nil else { return }
        let center = UNUserNotificationCenter.current()
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        if sound { content.sound = .default }
        let request = UNNotificationRequest(identifier: "\(id)-\(UUID().uuidString)",
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
