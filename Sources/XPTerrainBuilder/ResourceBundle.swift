import Foundation

extension Bundle {
    /// The app target's resource bundle (see Bundle.sceneryKit in SceneryKit
    /// for why `Bundle.module` alone is not safe in the packaged app).
    static let appResources: Bundle = {
        if let url = Bundle.main.resourceURL?
            .appendingPathComponent("XPTerrainBuilder_XPTerrainBuilder.bundle"),
            let bundle = Bundle(url: url) {
            return bundle
        }
        return .module
    }()
}
