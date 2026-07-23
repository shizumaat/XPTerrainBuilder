import Foundation

extension Bundle {
    /// SceneryKit's resource bundle.
    ///
    /// SwiftPM's generated `Bundle.module` accessor only checks the .app root
    /// and the absolute .build path baked in at compile time — never
    /// Contents/Resources, where make_app.sh installs the bundle. Inside the
    /// packaged app the .build fallback also fails under Finder launches
    /// (TCC blocks the app's access to ~/Documents), trapping at startup.
    /// Check the installed location first; `.module` still serves
    /// `swift run` and `swift test`.
    static let sceneryKit: Bundle = {
        if let url = Bundle.main.resourceURL?
            .appendingPathComponent("XPTerrainBuilder_SceneryKit.bundle"),
            let bundle = Bundle(url: url) {
            return bundle
        }
        return .module
    }()
}
