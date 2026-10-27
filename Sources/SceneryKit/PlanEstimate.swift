import Foundation

// The build-cost estimate, protocol 1.15 (issue #820). The engine's
// `plan_estimate` command (Ortho4XP/src/o4_engine/plan_estimate.py)
// replies `{"status": "started"}`; the `PlanEstimateReady` event carrying
// the command's id brings this result. JSON keys are STRING LITERALS
// matched against that module. Every figure is a `[lo, hi]` range.

/// One `[lo, hi]` pair as the engine sends it.
public struct O4Range: Decodable, Equatable, Sendable {
    public let lo: Double
    public let hi: Double

    public init(_ lo: Double, _ hi: Double) {
        self.lo = lo
        self.hi = hi
    }

    public init(from decoder: Decoder) throws {
        var c = try decoder.unkeyedContainer()
        lo = try c.decode(Double.self)
        hi = try c.decode(Double.self)
    }
}

/// The engine's answer: per tile, the total, and the free space it was
/// set against. `verdict` is "ok", "warn" or "refuse"; `reason` is the
/// sentence to show for the last two.
public struct O4PlanEstimate: Decodable, Equatable, Sendable {
    public struct Tile: Decodable, Equatable, Sendable, Identifiable {
        public let lat: Int
        public let lon: Int
        public let downloadGB: O4Range
        public let diskGB: O4Range
        public let timeS: O4Range
        public var id: String { TileMath.key(lat: lat, lon: lon) }

        private enum CodingKeys: String, CodingKey {
            case lat, lon, downloadGB = "download_gb", diskGB = "disk_gb", timeS = "time_s"
        }

        public init(lat: Int, lon: Int, downloadGB: O4Range, diskGB: O4Range, timeS: O4Range) {
            self.lat = lat
            self.lon = lon
            self.downloadGB = downloadGB
            self.diskGB = diskGB
            self.timeS = timeS
        }
    }

    public struct Total: Decodable, Equatable, Sendable {
        public let downloadGB: O4Range
        public let diskGB: O4Range
        public let timeS: O4Range

        private enum CodingKeys: String, CodingKey {
            case downloadGB = "download_gb", diskGB = "disk_gb", timeS = "time_s"
        }

        public init(downloadGB: O4Range, diskGB: O4Range, timeS: O4Range) {
            self.downloadGB = downloadGB
            self.diskGB = diskGB
            self.timeS = timeS
        }
    }

    public let tiles: [Tile]
    public let total: Total
    public let freeGB: Double?
    public let cacheFreeGB: Double?
    public let verdict: String
    public let reason: String

    private enum CodingKeys: String, CodingKey {
        case tiles, total, freeGB = "free_gb", cacheFreeGB = "cache_free_gb", verdict, reason
    }

    public init(tiles: [Tile], total: Total, freeGB: Double?, cacheFreeGB: Double?,
                verdict: String, reason: String) {
        self.tiles = tiles
        self.total = total
        self.freeGB = freeGB
        self.cacheFreeGB = cacheFreeGB
        self.verdict = verdict
        self.reason = reason
    }

    /// The refusal sentence when the build cannot fit, else nil.
    public var blockingReason: String? {
        guard verdict == "refuse" else { return nil }
        return reason.isEmpty ? "Not enough free disk space." : reason
    }

    /// The warning or refusal line to show, else nil.
    public var verdictLine: String? {
        (verdict == "warn" || verdict == "refuse") && !reason.isEmpty ? reason : nil
    }
}

/// The panel's lines, spelled exactly as the Qt window's
/// `O4_Qt_Plan_Estimate` helpers (`gb_text`, `time_text`, `total_text`,
/// `tile_text`) spell them.
public enum PlanEstimateText {
    /// `[0.96, 5.05]` → "1.0–5.1 GB"; nothing to move is "none".
    public static func gb(_ range: O4Range) -> String {
        if range.hi < 0.05 { return "none" }
        return String(format: "%.1f–%.1f GB", range.lo, range.hi)
    }

    /// Seconds as minutes, or hours past 90 minutes.
    public static func time(_ range: O4Range) -> String {
        if range.hi <= 0 { return "none" }
        if range.hi < 90 * 60 {
            let lo = max(1, Int((range.lo / 60).rounded()))
            let hi = max(lo, Int((range.hi / 60).rounded(.up)))
            return lo == hi ? "about \(lo) min" : "\(lo)–\(hi) min"
        }
        return String(format: "%.1f–%.1f h", range.lo / 3600, range.hi / 3600)
    }

    /// "Download 1.0–5.1 GB · Disk 3.4–16.2 GB of 27.3 GB free · 16–79 min"
    public static func total(_ estimate: O4PlanEstimate) -> String {
        var disk = "Disk \(gb(estimate.total.diskGB))"
        if let free = estimate.freeGB { disk += String(format: " of %.1f GB free", free) }
        return ["Download \(gb(estimate.total.downloadGB))", disk, time(estimate.total.timeS)]
            .joined(separator: " · ")
    }

    /// "+45-123  ↓ 0.5–2.7 GB · disk 1.8–8.5 GB · 8–42 min"
    public static func tile(_ row: O4PlanEstimate.Tile) -> String {
        "\(row.id)  ↓ \(gb(row.downloadGB)) · disk \(gb(row.diskGB)) · \(time(row.timeS))"
    }
}

extension O4ProtocolVersion {
    /// `plan_estimate` exists from protocol 1.15 (#820).
    public static func supportsPlanEstimate(_ version: String) -> Bool {
        isAtLeast(version, 1, 15)
    }
}

extension OrthoEngineClient {
    /// What building `tiles` will cost (protocol 1.15, #820). Asynchronous
    /// on the engine side: the reply is `{"status": "started"}` and the
    /// `PlanEstimateReady` event naming this command's id carries the
    /// estimate or the error. `provider` "" and the tile's own zoom level
    /// resolve as `enqueue_build` resolves them.
    public func planEstimate(tiles: [O4TileRef], provider: String, zoomlevel: Int,
                             customBuildDir: String, doVector: Bool, doImagery: Bool,
                             doOverlays: Bool) async throws -> O4PlanEstimate {
        let once = O4ResumeOnce<O4PlanEstimate>()
        let arguments: [String: Any] = [
            "tiles": tiles.map { [$0.lat, $0.lon] },
            "provider": provider,
            "zoomlevel": zoomlevel,
            "custom_build_dir": customBuildDir,
            "do_vector": doVector,
            "do_imagery": doImagery,
            "do_overlays": doOverlays,
        ]
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: "plan_estimate",
                 arguments: arguments,
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused plan_estimate.")))
                     }
                 },
                 completionEvent: { event in once.resume(Self.decodePlanEstimateReady(event)) })
        }
    }

    /// One `PlanEstimateReady` event → the typed estimate or its error.
    static func decodePlanEstimateReady(_ event: O4JSON?) -> Result<O4PlanEstimate, Error> {
        guard let event else { return .failure(O4CommandError("The engine exited before the estimate was ready.")) }
        if case .string(let text)? = event["error"], !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        guard let result = event["result"], result != .null else {
            return .failure(O4CommandError("The engine sent no estimate."))
        }
        return Result { try result.decode(O4PlanEstimate.self) }
    }
}
