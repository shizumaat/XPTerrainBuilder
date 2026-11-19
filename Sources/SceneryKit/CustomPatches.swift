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
    /// The elevation notices not yet answered (#2179); empty from an
    /// engine that predates them.
    public let notices: [O4CustomPatchNotice]

    public init(lat: Int, lon: Int, files: [String], notices: [O4CustomPatchNotice] = []) {
        self.lat = lat
        self.lon = lon
        self.files = files
        self.notices = notices
    }

    private enum CodingKeys: String, CodingKey { case lat, lon, files, notices }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        lat = try c.decode(Int.self, forKey: .lat)
        lon = try c.decode(Int.self, forKey: .lon)
        files = try c.decode([String].self, forKey: .files)
        notices = try c.decodeIfPresent([O4CustomPatchNotice].self, forKey: .notices) ?? []
    }
}

/// Which elevation a custom patch was built for, said once per patch
/// (owner 2026-11-19T13:42Z, #2179): the engine's
/// `O4_Custom_Patches.elevation_notices` row; `text` is the engine's
/// sentence, shown as is.
public struct O4CustomPatchNotice: Decodable, Equatable, Sendable, Identifiable {
    public var id: String { file }
    public let icao: String
    public let file: String
    public let source: String
    public let text: String

    public init(icao: String, file: String, source: String, text: String) {
        self.icao = icao
        self.file = file
        self.source = source
        self.text = text
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
    /// The custom-patch notice's other answer (#2179).
    public static let keepTitle = "Keep custom patch"
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
    /// `….disabled`, never deleted; only `icao`'s when given) so the next
    /// build auto-patches them.
    public func useAutoPatch(tile: String, icao: String = "") async throws -> O4UseAutoPatchReply {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "use_auto_patch", arguments: ["tile": tile, "icao": icao]) { reply in
                let result: Result<O4UseAutoPatchReply, Error> =
                    Self.decodeReply(reply, command: "use_auto_patch")
                continuation.resume(with: result)
            }
        }
    }

    /// The custom-patch notice was answered (#2179, capability
    /// `custom_patch_notice`): not shown again until the file changes.
    public func customPatchNoticeSeen(tile: String, file: String) async throws {
        let _: O4CustomPatchNoticeSeenReply = try await request(
            "custom_patch_notice_seen", ["tile": tile, "file": file])
    }
}

/// The `custom_patch_notice_seen` reply.
struct O4CustomPatchNoticeSeenReply: Decodable, Sendable {
    let tile: String
    let file: String
}
