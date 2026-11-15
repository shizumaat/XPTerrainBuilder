import Foundation

/// One step of one tile HELD for memory (#2101) — `class MemoryWait` in
/// Ortho4XP/src/o4_engine/events.py, matched as the STRING LITERAL
/// "MemoryWait" in `O4Event.parse`. The engine writes `message`
/// (`o4_engine.memory_waits.wait_message`); the tile's Activity row shows
/// it verbatim until `resolved` or the tile's next step starts.
public struct O4MemoryWait: Sendable, Equatable {
    public let lat: Int
    public let lon: Int
    public let stepKey: String
    public let neededGB: Double
    public let freeGB: Double
    /// "machine" (another application holds the memory) or "run".
    public let reason: String
    public let message: String
    public let resolved: Bool
    public let attempt: Int

    public init(lat: Int, lon: Int, stepKey: String, neededGB: Double,
                freeGB: Double, reason: String, message: String,
                resolved: Bool, attempt: Int = 0) {
        self.lat = lat
        self.lon = lon
        self.stepKey = stepKey
        self.neededGB = neededGB
        self.freeGB = freeGB
        self.reason = reason
        self.message = message
        self.resolved = resolved
        self.attempt = attempt
    }

    static func parse(_ object: [String: Any]) -> O4MemoryWait {
        func number(_ key: String) -> NSNumber? { object[key] as? NSNumber }
        return O4MemoryWait(
            lat: number("lat")?.intValue ?? 0,
            lon: number("lon")?.intValue ?? 0,
            stepKey: object["step_key"] as? String ?? "",
            neededGB: number("needed_gb")?.doubleValue ?? 0,
            freeGB: number("free_gb")?.doubleValue ?? 0,
            reason: object["reason"] as? String ?? "",
            message: object["message"] as? String ?? "",
            resolved: number("resolved")?.boolValue ?? false,
            attempt: number("attempt")?.intValue ?? 0)
    }
}
