import Foundation

/// How often a streamed scan's partial results reach the screen (#2055).
///
/// The engine streams `ScanBatch` at ~10 Hz so a long scan fills the map as
/// it goes. Every batch the app published re-rendered every view observing
/// the build model (25-90 ms each with a large World pack), so a 25 s
/// launch scan kept the main thread busy for most of those 25 s. The scan
/// still accumulates every batch; this says when the accumulated tiles are
/// published: the first batch at once (the map fills immediately), then at
/// most once per `interval`; `ScanDone` always publishes the final truth.
/// One rule in both apps (Qt: `O4_Scan_Stream_Throttle`), twinned on
/// `Ortho4XP/tests/fixtures/scan_stream_throttle_cases.json`.
public struct ScanStreamThrottle: Sendable {
    public static let defaultInterval: TimeInterval = 1.0

    public let interval: TimeInterval
    private var publishedAt: TimeInterval?

    public init(interval: TimeInterval = Self.defaultInterval) {
        self.interval = interval
    }

    /// A new scan starts: its first batch publishes at once.
    public mutating func reset() {
        publishedAt = nil
    }

    /// True when the batch arriving at `now` (seconds, any monotonic clock)
    /// should publish the accumulated tiles; records the publication.
    public mutating func shouldPublish(now: TimeInterval) -> Bool {
        if let last = publishedAt, now - last < interval { return false }
        publishedAt = now
        return true
    }
}
