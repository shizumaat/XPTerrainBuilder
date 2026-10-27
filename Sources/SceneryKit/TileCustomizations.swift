import Foundation

/// One setting a tile's cfg customizes (#1350): the engine's
/// `tile_customizations` row (`Ortho4XP/src/O4_Tile_Customizations.py`).
/// The JSON keys are the wire contract; the engine owns the comparison
/// against the global layer, this app only shows it.
public struct O4TileCustomization: Decodable, Equatable, Sendable, Identifiable {
    /// The cfg name (`road_level`).
    public let key: String
    /// The Settings window's label for it, else the cfg name.
    public let label: String
    public let tileValue: String
    /// What the tile would use without its override: the global config,
    /// else the registry default.
    public let defaultValue: String
    /// The two values as the Settings window shows them (On/Off, menu titles).
    public let tileText: String
    public let defaultText: String
    /// The terrain steps read it: changing it reshapes the ground,
    /// the airport grading or the water on the next build.
    public let affectsOutput: Bool

    public var id: String { key }

    private enum CodingKeys: String, CodingKey {
        case key, label
        case tileValue = "tile_value", defaultValue = "default_value"
        case tileText = "tile_text", defaultText = "default_text"
        case affectsOutput = "affects_output"
    }

    public init(key: String, label: String, tileValue: String, defaultValue: String,
                tileText: String, defaultText: String, affectsOutput: Bool) {
        self.key = key
        self.label = label
        self.tileValue = tileValue
        self.defaultValue = defaultValue
        self.tileText = tileText
        self.defaultText = defaultText
        self.affectsOutput = affectsOutput
    }

    /// Marks a row whose setting the terrain steps read
    /// (`O4_Tile_Customizations.GROUND_MARK`).
    public static let groundMark = "◆"

    /// The tile pane's line: `Label: 5 (default 4)`, the ground mark in
    /// front when the setting reshapes the terrain. Same words as the Qt
    /// pane (`O4_Tile_Customizations.row_text`).
    public var displayText: String {
        var name = label
        while name.hasSuffix("?") { name.removeLast() }
        let text = "\(name): \(tileText) (default \(defaultText))"
        return affectsOutput ? "\(Self.groundMark) \(text)" : text
    }

    /// The row's hover text (`O4_Tile_Customizations.row_tooltip`).
    public var helpText: String {
        affectsOutput
            ? key + " — changes the ground shape, airport grading or water: "
                + "the terrain steps run again on the next build"
            : key
    }
}

/// The `tile_customizations` reply: the tile and its customized settings,
/// empty when it customizes nothing.
public struct O4TileCustomizations: Decodable, Equatable, Sendable {
    public let lat: Int
    public let lon: Int
    public let customizations: [O4TileCustomization]
}

extension OrthoEngineClient {
    /// The tile's customized settings (#1350). `workingDir`: the folder
    /// holding the tile folders. An engine without the command answers
    /// ok=false, which throws — the caller shows no badge.
    public func tileCustomizations(lat: Int, lon: Int,
                                   workingDir: String) async throws -> O4TileCustomizations {
        try await withCheckedThrowingContinuation { continuation in
            send(command: "tile_customizations", arguments: [
                "lat": lat, "lon": lon, "working_dir": workingDir,
            ]) { reply in
                let result: Result<O4TileCustomizations, Error> =
                    Self.decodeReply(reply, command: "tile_customizations")
                continuation.resume(with: result)
            }
        }
    }
}
