import Foundation

/// The engine's imagery check of a built tile (protocol 1.27, #1666,
/// `Ortho4XP/src/O4_Imagery_Freshness.py`): does the tile's source still
/// serve the imagery the tile was built from? The engine owns the check
/// and writes the words; this app only shows them (the Qt pane's
/// `O4_Qt_Imagery_Freshness`, the same).
public struct O4ImageryFreshness: Decodable, Equatable, Sendable {
    /// `up_to_date`, `newer`, `unknown` or `not_checked`.
    public let status: String
    /// "Up to date", "Newer imagery available", "Unknown", "Not checked yet".
    public let label: String
    /// Why, for the tooltip.
    public let detail: String

    public init(status: String, label: String, detail: String) {
        self.status = status
        self.label = label
        self.detail = detail
    }

    public var isNewer: Bool { status == "newer" }
}

/// What "Update Imagery" removed before the rebuild.
public struct O4ImageryDiscard: Decodable, Equatable, Sendable {
    public let jpegs: Int
    public let textures: Int
}

/// The "Update Imagery" words (`O4_Imagery_Freshness.UPDATE_CONFIRM_*`
/// and `O4_Qt_Imagery_Freshness.UPDATE_*`: the same strings).
public enum O4ImageryFreshnessText {
    public static let updateTitle = "Update Imagery"
    public static let updateHelp = "Download this tile's imagery again from its source and rebuild the tile with it."
    public static let confirmTitle = "Update this tile's imagery?"
    public static let confirmText = "The imagery downloaded for this tile is removed and the tile is rebuilt with what its source serves now. Until the build finishes, X-Plane shows this tile without its imagery."
}

extension OrthoEngineClient {
    /// Check one built tile (protocol 1.27). Asynchronous on the engine
    /// side: the reply is `{"status": "started"}` and the
    /// `ImageryFreshnessReady` event naming this command's id carries the
    /// answer. An older engine answers ok=false, which throws.
    public func imageryFreshness(lat: Int, lon: Int, workingDir: String,
                                 force: Bool = false) async throws -> O4ImageryFreshness {
        let once = O4ResumeOnce<O4ImageryFreshness>()
        let arguments: [String: Any] = ["lat": lat, "lon": lon,
                                        "working_dir": workingDir, "force": force]
        return try await withCheckedThrowingContinuation { continuation in
            once.set(continuation)
            send(command: "imagery_freshness",
                 arguments: arguments,
                 completion: { reply in
                     if !reply.ok {
                         once.resume(.failure(O4CommandError(reply.error ?? "The engine refused imagery_freshness.")))
                     }
                 },
                 completionEvent: { event in once.resume(Self.decodeImageryFreshnessReady(event)) })
        }
    }

    /// One `ImageryFreshnessReady` event → the typed answer or its error.
    static func decodeImageryFreshnessReady(_ event: O4JSON?) -> Result<O4ImageryFreshness, Error> {
        guard let event else { return .failure(O4CommandError("The engine exited before the imagery check finished.")) }
        if case .string(let text)? = event["error"], !text.isEmpty {
            return .failure(O4CommandError(text))
        }
        guard let result = event["result"], result != .null else {
            return .failure(O4CommandError("The engine sent no imagery check."))
        }
        return Result { try result.decode(O4ImageryFreshness.self) }
    }

    /// "Update Imagery": remove the tile's downloaded imagery so the
    /// rebuild that follows downloads it again. Synchronous on the engine.
    public func discardTileImagery(lat: Int, lon: Int, workingDir: String) async throws -> O4ImageryDiscard {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "imagery_freshness_discard",
                 arguments: ["lat": lat, "lon": lon, "working_dir": workingDir]) { reply in
                continuation.resume(with: Self.decodeReply(reply, command: "imagery_freshness_discard"))
            }
        }
    }
}
