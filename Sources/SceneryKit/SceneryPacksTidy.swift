import Foundation

/// The engine's `tidy_scenery_packs` reply (protocol 1.25, #1729,
/// `Ortho4XP/src/O4_Scenery_Packs_Tidy.py`): the packs scenery_packs.ini
/// did not list, now filed in their kind's group — airports above Global
/// Airports, then overlays, libraries, orthos, and meshes below every
/// ortho. The engine owns the rule for both apps; this one only asks.
public struct O4SceneryPacksTidy: Decodable, Equatable, Sendable {
    public let added: [String]
    /// The copy of the user's ini kept before the first change, or "".
    public let backup: String
}

extension PackKind {
    /// The engine's name for the kind (`O4_Custom_Scenery.PACK_KINDS`).
    public var engineName: String {
        switch self {
        case .airport: return "airport"
        case .landmark: return "landmark"
        case .ortho: return "ortho"
        case .mesh: return "mesh"
        case .library: return "library"
        case .other: return "other"
        }
    }
}

extension OrthoEngineClient {
    /// File the packs the ini does not list yet. `kinds` is this app's
    /// scan (pack name → kind), so the engine reads no pack it already
    /// knows. An engine before 1.25 answers ok=false, which throws.
    public func tidySceneryPacks(customSceneryDir: String,
                                 kinds: [String: PackKind]) async throws -> O4SceneryPacksTidy {
        let command = "tidy_scenery_packs"
        let arguments: [String: Any] = [
            "custom_scenery_dir": customSceneryDir,
            "kinds": kinds.mapValues { $0.engineName },
        ]
        return try await withCheckedThrowingContinuation { continuation in
            send(command: command, arguments: arguments) { reply in
                let result: Result<O4SceneryPacksTidy, Error> =
                    Self.decodeReply(reply, command: command)
                continuation.resume(with: result)
            }
        }
    }
}
