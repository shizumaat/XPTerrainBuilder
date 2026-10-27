import Foundation

/// The engine's `tile_texture_check` reply (protocol 1.22,
/// `Ortho4XP/src/O4_Tile_Texture_Check.py`): the textures an installed
/// tile's `terrain/*.ter` files name that its `textures/` folder lacks —
/// a tile X-Plane will not load. The engine owns the check; this app only
/// shows it, in the Qt pane's words.
public struct O4TileTextureCheck: Decodable, Equatable, Sendable {
    public let buildDir: String
    /// False when the tile has no terrain folder: nothing to check.
    public let checked: Bool
    public let missingCount: Int
    /// The first missing names (at most the engine's `SAMPLE_SIZE`).
    public let missing: [String]

    private enum CodingKeys: String, CodingKey {
        case buildDir = "build_dir", checked
        case missingCount = "missing_count", missing
    }

    public init(buildDir: String, checked: Bool, missingCount: Int, missing: [String]) {
        self.buildDir = buildDir
        self.checked = checked
        self.missingCount = missingCount
        self.missing = missing
    }

    /// `1,805` — Python's `format(n, ",")`, whatever the user's locale.
    private static func grouped(_ value: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.groupingSeparator = ","
        formatter.usesGroupingSeparator = true
        return formatter.string(from: NSNumber(value: value)) ?? String(value)
    }

    /// The tile pane's line (`O4_Tile_Texture_Check.warning_text`).
    public var warningText: String {
        let count = missingCount == 1
            ? "1 texture"
            : "\(Self.grouped(missingCount)) textures"
        return "\(count) missing — X-Plane cannot load this tile"
    }

    /// The explanation (`O4_Tile_Texture_Check.detail_text`).
    public var detailText: String {
        let shown = Array(missing.prefix(3))
        let more = missingCount - shown.count
        let names = shown.joined(separator: ", ")
            + (more > 0 ? " and \(Self.grouped(more)) more" : "")
        return "This tile's terrain files name textures its textures folder does not have (\(names)). They may have been moved to the Trash or deleted; put them back from the Trash, or rebuild the tile with the imagery it was built with."
    }
}

extension OrthoEngineClient {
    /// Check one installed tile folder (`buildDir`). An engine before 1.22
    /// answers ok=false, which throws — the caller shows nothing.
    public func tileTextureCheck(buildDir: String) async throws -> O4TileTextureCheck {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "tile_texture_check", arguments: ["build_dir": buildDir]) { reply in
                let result: Result<O4TileTextureCheck, Error> =
                    Self.decodeReply(reply, command: "tile_texture_check")
                continuation.resume(with: result)
            }
        }
    }
}
