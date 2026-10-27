import Foundation

/// One tile with a custom patch (#1229, RULINGS 2026-10-26c): the engine's
/// `custom_patches` row (`Ortho4XP/src/O4_Custom_Patches.py`). A custom
/// patch is any `*.patch.osm` in the tile's Patches folder that is not
/// `<ICAO>_auto.patch.osm`; the build applies it and does not auto-patch
/// that airport.
public struct O4CustomPatchTile: Decodable, Equatable, Sendable {
    public let lat: Int
    public let lon: Int
    /// The custom patch file names, sorted.
    public let files: [String]

    public init(lat: Int, lon: Int, files: [String]) {
        self.lat = lat
        self.lon = lon
        self.files = files
    }
}

/// The `custom_patches` reply: every tile of the data root with one.
public struct O4CustomPatches: Decodable, Equatable, Sendable {
    public let tiles: [O4CustomPatchTile]
}

/// The `use_auto_patch` reply: where each custom patch was set aside.
public struct O4UseAutoPatchReply: Decodable, Equatable, Sendable {
    public let setAside: [String]

    private enum CodingKeys: String, CodingKey { case setAside = "set_aside" }
}

/// The tile info's words, the same as the Qt pane's
/// (`O4_Custom_Patches.CUSTOM_PATCH_TITLE` / `info_text` / …).
public enum O4CustomPatchText {
    public static let title = "Custom patch"
    public static let useAutoPatchTitle = "Use auto patch"
    public static let useAutoPatchHelp =
        "Renames the custom patch to .disabled (it is never deleted), "
        + "so the next build auto-patches the airport."

    public static func info(_ files: [String]) -> String {
        files.joined(separator: ", ") + " — the auto patch does not run for "
            + (files.count == 1 ? "this airport" : "these airports")
    }
}

extension OrthoEngineClient {
    /// Every tile with a custom patch (#1229). An engine without the
    /// command answers ok=false, which throws — the caller draws no band.
    public func customPatches() async throws -> O4CustomPatches {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "custom_patches", arguments: [:]) { reply in
                let result: Result<O4CustomPatches, Error> =
                    Self.decodeReply(reply, command: "custom_patches")
                continuation.resume(with: result)
            }
        }
    }

    /// "Use auto patch": set the tile's custom patches aside (renamed to
    /// `….disabled`, never deleted) so the next build auto-patches them.
    public func useAutoPatch(tile: String) async throws -> O4UseAutoPatchReply {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "use_auto_patch", arguments: ["tile": tile]) { reply in
                let result: Result<O4UseAutoPatchReply, Error> =
                    Self.decodeReply(reply, command: "use_auto_patch")
                continuation.resume(with: result)
            }
        }
    }
}
