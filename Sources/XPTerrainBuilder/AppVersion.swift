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

    /// App version, engine version and commit — the triple a beta bug report
    /// quotes (docs/BETA-PLAN-20260916.md §1 B3). The engine version and the
    /// commit are stamped into Info.plist by scripts/make_app.sh; under
    /// `swift run` there is no stamp, so the engine version falls back to the
    /// bundled schema snapshot's and the commit reads "dev".
    static func triple(liveEngineVersion: String? = nil) -> BuildTriple {
        BuildTriple(app: current,
                    infoDictionary: Bundle.main.infoDictionary,
                    engineFallback: liveEngineVersion)
    }
}
