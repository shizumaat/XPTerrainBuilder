import Foundation

/// The imagery follow job's state (engine `ImageryFollowStatus`, #1992
/// P3b, capability `imagery_follow`): the engine fetches finer imagery
/// tiers ahead of X-Plane's camera and reports every ~2 s, at once on a
/// change, and once with `state == "stopped"` when it ends.
///
/// `state` is `starting`, `waiting` (X-Plane or its Web API not
/// answering), `following`, `paused` (a build runs, or offline; `reason`
/// is the engine's sentence, shown verbatim), `stopped` or `error`.
/// `slots` is how many textures are fetched at once (1 unless the
/// buffer ahead of the aircraft is depleting); `bufferSeconds` is that
/// buffer, nil when nothing is queued. `reloads` counts the scenery
/// reloads the engine asked X-Plane for after a spawn or jump whose
/// imagery missed the flight-start window (#1992 P5, capability
/// `imagery_spawn_reload`). The field names are the JSON keys
/// of `class ImageryFollowStatus` in `Ortho4XP/src/o4_engine/events.py`.
public struct O4ImageryFollowStatus: Sendable, Equatable {
    public let state: String
    public let reason: String
    public let xplane: Bool
    public let lat: Double
    public let lon: Double
    public let speedMS: Double
    public let trackDegrees: Double
    public let queued: Int
    public let inFlight: Int
    public let slots: Int
    public let bufferSeconds: Double?
    public let sharp: Int
    public let textures: Int
    public let landed: Int
    public let late: Int
    public let failed: Int
    public let bytesLanded: Int64
    public let flightLoads: Int
    public let jumps: Int
    public let reloads: Int

    /// Is the job running (not stopped and not failed)?
    public var running: Bool { state != "stopped" && state != "error" }

    /// Parses an `ImageryFollowStatus` event object.
    public static func parse(_ object: [String: Any]) -> O4ImageryFollowStatus {
        func int(_ key: String) -> Int { (object[key] as? NSNumber)?.intValue ?? 0 }
        func double(_ key: String) -> Double { (object[key] as? NSNumber)?.doubleValue ?? 0 }
        let buffer = double("buffer_s")
        return O4ImageryFollowStatus(
            state: object["state"] as? String ?? "starting",
            reason: object["reason"] as? String ?? "",
            xplane: (object["xplane"] as? NSNumber)?.boolValue ?? false,
            lat: double("lat"), lon: double("lon"),
            speedMS: double("speed_ms"), trackDegrees: double("track_deg"),
            queued: int("queued"), inFlight: int("in_flight"),
            slots: max(1, int("slots")),
            bufferSeconds: buffer < 0 ? nil : buffer,
            sharp: int("sharp"), textures: int("textures"),
            landed: int("landed"), late: int("late"), failed: int("failed"),
            bytesLanded: (object["bytes_landed"] as? NSNumber)?.int64Value ?? 0,
            flightLoads: int("flight_loads"), jumps: int("jumps"),
            reloads: int("reloads"))
    }
}
