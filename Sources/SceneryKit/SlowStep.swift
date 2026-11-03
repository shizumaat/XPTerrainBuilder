import Foundation

/// One step of one tile ran past its slow-step threshold (engine
/// `SlowStep`, protocol 1.24, issue #1351).
///
/// The engine writes every word: `title` and `message` (what the step is
/// doing, why it is slow, the ETA at the current rate) are shown verbatim,
/// and `options` are the answers the step supports — "continue",
/// "coarser" (only where the running phase can finish on coarser data),
/// "cancel" — with their button words in `optionLabels`, in order. A later
/// event of the same tile and step replaces the open alert (the ETA
/// refreshes); `resolved` closes it. The Qt window shows the same event
/// (`Ortho4XP/src/O4_Qt_Slow_Step.py`).
public struct O4SlowStep: Sendable, Equatable, Identifiable {
    public let lat: Int
    public let lon: Int
    public let stepKey: String
    public let title: String
    public let message: String
    public let reason: String
    public let options: [String]
    public let optionLabels: [String]
    public let etaSeconds: Double?
    public let resolved: Bool

    /// One alert per tile and step.
    public var id: String { "\(lat)|\(lon)|\(stepKey)" }

    public init(lat: Int, lon: Int, stepKey: String, title: String,
                message: String, reason: String, options: [String],
                optionLabels: [String], etaSeconds: Double?, resolved: Bool) {
        self.lat = lat
        self.lon = lon
        self.stepKey = stepKey
        self.title = title
        self.message = message
        self.reason = reason
        self.options = options
        self.optionLabels = optionLabels
        self.etaSeconds = etaSeconds
        self.resolved = resolved
    }

    /// The answers in order, each with its button words (the engine's;
    /// an answer without words shows its code).
    public var buttons: [(choice: String, label: String)] {
        options.enumerated().map { index, choice in
            (choice, index < optionLabels.count ? optionLabels[index] : choice)
        }
    }

    /// Parses a `SlowStep` event object.
    public static func parse(_ object: [String: Any]) -> O4SlowStep {
        func strings(_ key: String) -> [String] {
            (object[key] as? [Any])?.compactMap { $0 as? String } ?? []
        }
        return O4SlowStep(
            lat: (object["lat"] as? NSNumber)?.intValue ?? 0,
            lon: (object["lon"] as? NSNumber)?.intValue ?? 0,
            stepKey: object["step_key"] as? String ?? "",
            title: object["title"] as? String ?? "",
            message: object["message"] as? String ?? "",
            reason: object["reason"] as? String ?? "",
            options: strings("options"),
            optionLabels: strings("option_labels"),
            etaSeconds: (object["eta_seconds"] as? NSNumber)?.doubleValue,
            resolved: (object["resolved"] as? NSNumber)?.boolValue ?? false)
    }
}
