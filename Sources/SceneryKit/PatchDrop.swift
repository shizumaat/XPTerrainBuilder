import Foundation

/// One patch a drop would install (#1979): the engine's
/// `patch_drop_plan` row (`Ortho4XP/src/o4_engine/patch_drop.py`).
public struct O4PatchDropItem: Decodable, Equatable, Sendable {
    public let source: String
    public let name: String
    public let icao: String
    /// The tile key, `+39-107`.
    public let tile: String
    /// "header" or "geometry": how the tile was found.
    public let foundBy: String
    public let destination: String
    public let replaces: Bool
    public let companions: [String]
    /// After `patch_drop_install`: where replaced files were set aside.
    public let backups: [String]?

    private enum CodingKeys: String, CodingKey {
        case source, name, icao, tile, destination, replaces, companions, backups
        case foundBy = "found_by"
    }
}

/// The `patch_drop_plan` / `patch_drop_install` reply. `summary` is the
/// confirmation both apps show, one line per patch then per skipped file.
public struct O4PatchDropPlan: Decodable, Equatable, Sendable {
    public let items: [O4PatchDropItem]
    public let tiles: [String]
    public let summary: [String]
}

/// The confirmation's words, the same as the Qt window's
/// (`O4_Qt_Patch_Drop.TITLE` / `INSTALL`).
public enum O4PatchDropCopy {
    public static let title = "Install dropped patches?"
    public static let install = "Install"

    public static func building(_ tiles: [String]) -> String {
        "Tile \(tiles.joined(separator: ", ")) is building; install the "
            + "patches when its build finishes."
    }

    public static func installed(_ item: O4PatchDropItem) -> String {
        "Tile \(item.tile): installed "
            + "\((item.destination as NSString).lastPathComponent); "
            + "the next build applies it."
    }
}

extension OrthoEngineClient {
    /// What dropping `paths` would install (#1979). Writes nothing; a drop
    /// with no patch in it answers ok=false with the sentence, which throws.
    public func patchDropPlan(paths: [String]) async throws -> O4PatchDropPlan {
        try await patchDrop("patch_drop_plan", paths: paths)
    }

    /// Install what `patchDropPlan` listed for `paths`.
    public func patchDropInstall(paths: [String]) async throws -> O4PatchDropPlan {
        try await patchDrop("patch_drop_install", paths: paths)
    }

    private func patchDrop(_ command: String, paths: [String]) async throws -> O4PatchDropPlan {
        try await withCheckedThrowingContinuation { continuation in
            send(command: command, arguments: ["paths": paths]) { reply in
                let result: Result<O4PatchDropPlan, Error> =
                    Self.decodeReply(reply, command: command)
                continuation.resume(with: result)
            }
        }
    }
}
