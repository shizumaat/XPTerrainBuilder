import Foundation

/// One tile's airport cores sharpening in the background (engine
/// `ImageryCoresProgress`, #2039, capability `imagery_core_rows`): after a
/// build in on-demand mode, a World publish, a flight's kept endpoints or
/// an adopt. The Build view shows it as a row in the Activity list.
///
/// `state` is `active` while it runs, then `done`, `error` (`failed`
/// squares) or `stopped`; `done` of `total` squares landed. The field
/// names are the JSON keys of `class ImageryCoresProgress` in
/// `Ortho4XP/src/o4_engine/events.py`.
public struct O4ImageryCoresProgress: Sendable, Equatable {
    public let lat: Int
    public let lon: Int
    public let state: String
    public let done: Int
    public let failed: Int
    public let total: Int

    public init(lat: Int, lon: Int, state: String, done: Int, failed: Int, total: Int) {
        self.lat = lat
        self.lon = lon
        self.state = state
        self.done = done
        self.failed = failed
        self.total = total
    }

    /// Still sharpening: the row offers stop.
    public var running: Bool { state == "active" }

    /// The bar's fraction, 0...1.
    public var fraction: Double { total > 0 ? Double(done + failed) / Double(total) : 0 }

    /// Parses an `ImageryCoresProgress` event object.
    public static func parse(_ object: [String: Any]) -> O4ImageryCoresProgress {
        func int(_ key: String) -> Int { (object[key] as? NSNumber)?.intValue ?? 0 }
        return O4ImageryCoresProgress(
            lat: int("lat"), lon: int("lon"),
            state: object["state"] as? String ?? "active",
            done: int("done"), failed: int("failed"), total: int("total"))
    }
}
