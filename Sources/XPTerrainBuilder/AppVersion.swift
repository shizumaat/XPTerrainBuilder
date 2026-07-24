import Foundation
import SceneryKit

/// XPTerrainBuilder's own version — `1.0.<build>`, the build component bumped
/// by scripts/make_app.sh on every package.
///
/// The tracked `Resources/VERSION` is the source of truth: SwiftPM copies it
/// into the app's resource bundle, so `swift run` reports the same string as
/// the packaged app. make_app.sh stamps that same string into Info.plist for
/// Finder and crash reports, which is the fallback here.
enum AppVersion {
    static let current: String = ProductVersion.firstValid(trackedVersion, bundleVersion)

    private static var trackedVersion: String? {
        guard let url = Bundle.appResources.url(forResource: "VERSION", withExtension: nil)
        else { return nil }
        return try? String(contentsOf: url, encoding: .utf8)
    }

    private static var bundleVersion: String? {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
    }
}
