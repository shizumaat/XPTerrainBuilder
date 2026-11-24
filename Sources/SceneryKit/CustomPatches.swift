import Foundation

/// One tile with a custom patch (#1229, RULINGS 2026-10-26c): the engine's
/// `custom_patches` row (`Ortho4XP/src/O4_Custom_Patches.py`). A custom
/// patch is any `*.patch.osm` in the tile's Patches folder that is not
/// `<ICAO>_auto.patch.osm`. Each hand-made one is used "As made" or by
/// "Our auto patch", per airport (#2179, `airports`).
public struct O4CustomPatchTile: Decodable, Equatable, Sendable {
    public let lat: Int
    public let lon: Int
    /// The custom patch file names, sorted.
    public let files: [String]
    /// The elevation notices not yet answered (#2179); empty from an
    /// engine that predates them.
    public let notices: [O4CustomPatchNotice]
    /// One picker row per airport with a hand-made custom patch (#2179,
    /// capability `custom_patch_use`); empty from an older engine.
    public let airports: [O4CustomPatchUse]

    public init(lat: Int, lon: Int, files: [String], notices: [O4CustomPatchNotice] = [],
                airports: [O4CustomPatchUse] = []) {
        self.lat = lat
        self.lon = lon
        self.files = files
        self.notices = notices
        self.airports = airports
    }

    private enum CodingKeys: String, CodingKey { case lat, lon, files, notices, airports }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        lat = try c.decode(Int.self, forKey: .lat)
        lon = try c.decode(Int.self, forKey: .lon)
        files = try c.decode([String].self, forKey: .files)
        notices = try c.decodeIfPresent([O4CustomPatchNotice].self, forKey: .notices) ?? []
        airports = try c.decodeIfPresent([O4CustomPatchUse].self, forKey: .airports) ?? []
    }
}

/// How one airport uses its custom patch (#2179, RULINGS 2026-11-23d/f):
/// the engine's `O4_Custom_Patches.airport_uses` row, in the
/// `custom_patches` reply, the Build box's `BuildAirportsReady
/// .custom_patch_use` and the `custom_patch_use` reply.
public struct O4CustomPatchUse: Decodable, Equatable, Sendable, Identifiable {
    /// The patch unchanged, on the elevation it was made for (the default).
    public static let asMade = "as_made"
    /// Our auto patch on the high-resolution elevation; the file is kept.
    public static let autoPatch = "auto_patch"

    public var id: String { "\(tile.lat),\(tile.lon),\(icao)" }
    public let icao: String
    public let tile: O4TileRef
    public let files: [String]
    /// `asMade` or `autoPatch`.
    public let use: String
    /// False while the airport takes the default (As made).
    public let chosen: Bool
    /// Shown under an airport used as made (RULINGS 2026-11-23f); "" else.
    public let warning: String

    public init(icao: String, tile: O4TileRef, files: [String], use: String,
                chosen: Bool = false, warning: String = "") {
        self.icao = icao
        self.tile = tile
        self.files = files
        self.use = use
        self.chosen = chosen
        self.warning = warning
    }

    private enum CodingKeys: String, CodingKey { case icao, tile, files, use, chosen, warning }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        icao = try c.decode(String.self, forKey: .icao)
        let pair = try c.decode([Int].self, forKey: .tile)
        guard pair.count >= 2 else {
            throw DecodingError.dataCorruptedError(forKey: .tile, in: c,
                                                   debugDescription: "tile is [lat, lon]")
        }
        tile = O4TileRef(lat: pair[0], lon: pair[1])
        files = try c.decodeIfPresent([String].self, forKey: .files) ?? []
        use = try c.decodeIfPresent(String.self, forKey: .use) ?? Self.asMade
        chosen = try c.decodeIfPresent(Bool.self, forKey: .chosen) ?? false
        warning = try c.decodeIfPresent(String.self, forKey: .warning) ?? ""
    }

    /// One `BuildAirportsReady.custom_patch_use` row; nil when malformed.
    static func from(_ row: O4JSON) -> O4CustomPatchUse? {
        guard let icao = row["icao"]?.stringValue,
              let pair = row["tile"]?.arrayValue, pair.count >= 2,
              let lat = pair[0].intValue, let lon = pair[1].intValue else { return nil }
        return O4CustomPatchUse(
            icao: icao, tile: O4TileRef(lat: lat, lon: lon),
            files: row["files"]?.arrayValue?.compactMap(\.stringValue) ?? [],
            use: row["use"]?.stringValue ?? asMade,
            chosen: row["chosen"]?.boolValue ?? false,
            warning: row["warning"]?.stringValue ?? "")
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

/// The tile info's words, the same as the Qt pane's
/// (`O4_Custom_Patches.CUSTOM_PATCH_TITLE` / `info_text` / …).
public enum O4CustomPatchText {
    public static let title = "Custom patch"
    /// The custom-patch notice's answers (#2179): "Our auto patch" for
    /// that airport, or keep it as made.
    public static let useAutoPatchTitle = "Use our auto patch"
    public static let keepTitle = "Keep as made"
    /// The picker's two modes (RULINGS 2026-11-23d), the same words as
    /// the Qt window's (`O4_Custom_Patches.AS_MADE_TITLE` / …).
    public static let asMadeTitle = "As made"
    public static let autoPatchTitle = "Our auto patch"
    public static let asMadeHelp = "Uses the patch unchanged, on the elevation it was made for. The airport keeps its author's shape and its scenery package is used unmodified."
    public static let autoPatchHelp = "Grades the airport to the slope rules on our high-resolution elevation. Your patch is kept, not used."
    /// Under an airport used as made (RULINGS 2026-11-23f); the engine
    /// sends it too, as the row's `warning`.
    public static let asMadeWarning = "Higher-resolution elevation is available for this airport, but it requires our auto patch."

    public static func info(_ files: [String]) -> String {
        files.joined(separator: ", ")
    }

    public static func title(of use: String) -> String {
        use == O4CustomPatchUse.autoPatch ? autoPatchTitle : asMadeTitle
    }

    public static func help(of use: String) -> String {
        use == O4CustomPatchUse.autoPatch ? autoPatchHelp : asMadeHelp
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

    /// How `icao` in `tile` uses its custom patch from the next build on
    /// (#2179, capability `custom_patch_use`): `O4CustomPatchUse.asMade`,
    /// `.autoPatch`, or "default". Nothing is renamed.
    public func customPatchUse(tile: String, icao: String, use: String) async throws -> O4CustomPatchUse {
        try await request("custom_patch_use", ["tile": tile, "icao": icao, "use": use])
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
