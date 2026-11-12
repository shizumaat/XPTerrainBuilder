import Foundation

/// The words of a tile's World state in both apps (#2024): the Build map's
/// legend and the Library's World column. The mirror of
/// `Ortho4XP/src/O4_World_State_Text.py`, which the Qt window reads;
/// `Ortho4XP/tests/test_world_state.py` parses the literals below and
/// requires them to equal the Python ones.
public enum O4WorldStateText {
    // The Build map's legend.
    public static let legendFull = "Full: mesh and sharp imagery"
    public static let legendMesh = "Mesh: imagery sharpens in flight"
    public static let legendDrape = "Photo drape on X-Plane's mesh"
    public static let legendPlaceholder = "Placeholder: built or draped in flight"
    public static let legendNothing = "Unmarked: X-Plane's own scenery"
    public static let legendOtherTool = "Dotted: another tool's mesh"
    /// The orange band (#1229) the owner asked about (2026-11-12, "gold").
    public static let legendCustomPatch = "Orange band: custom airport patch, no auto patch"

    // The Library's World column.
    public static let columnTitle = "World"
    public static let stateWords: [String: String] = [
        "full": "Full",
        "drape": "Drape",
        "placeholder": "Placeholder",
        "nothing": "Nothing",
    ]
    public static let meshWords = "Mesh, {percent}% sharp"
    public static let originWords: [String: String] = [
        "xptb": "built here",
        "adopted": "adopted",
        "other": "another tool's",
    ]
    public static let sourceWords: [String: String] = [
        "originals": "original folder kept",
        "lean": "low-res copy here",
    ]
    public static let onDrive = "on {volume}"
    public static let leanOnDrive = "low-res copy here, full imagery on {volume}"

    static func sourceText(_ source: String, volume: String) -> String {
        if source == "lean", !volume.isEmpty {
            return leanOnDrive.replacingOccurrences(of: "{volume}", with: volume)
        }
        if source == "drive" {
            return volume.isEmpty ? "" : onDrive.replacingOccurrences(of: "{volume}", with: volume)
        }
        return sourceWords[source] ?? ""
    }

    /// The World column's cell (Qt: `O4_World_State_Text.cell_text`):
    /// "Mesh, 12% sharp · adopted · low-res copy here, full imagery on
    /// <drive>"; empty for none.
    public static func cellText(_ world: O4WorldTile?) -> String {
        guard let world else { return "" }
        let head = world.state == .meshLowRes
            ? meshWords.replacingOccurrences(of: "{percent}",
                                             with: String(Int((world.sharp * 100).rounded())))
            : stateWords[world.state.rawValue] ?? ""
        return [head, originWords[world.origin] ?? "", sourceText(world.source, volume: world.volume)]
            .filter { !$0.isEmpty }
            .joined(separator: " · ")
    }
}

/// What the World pack draws on one tile (#2024, the engine's
/// `o4_engine.world_state.WorldTile`): its state, who made its mesh, how
/// much of its imagery is sharp, and where its own files live. Arrives as
/// `ScanBatch.world` rows `[lat, lon, state, origin, sharp, source,
/// volume]` and as a Library row's `world` dict.
public struct O4WorldTile: Sendable, Equatable, Hashable, Decodable {
    public enum State: String, Sendable, CaseIterable, Decodable {
        case full
        case meshLowRes = "mesh_lowres"
        case drape, placeholder, nothing
    }

    public let state: State
    /// "xptb", "adopted", "other" (`O4_Tile_Info.ORIGIN_*`), or "".
    public let origin: String
    /// The fraction of its textures at full width (a mesh tile).
    public let sharp: Double
    /// "originals", "lean", "drive", or "".
    public let source: String
    public let volume: String

    public init(state: State, origin: String = "", sharp: Double = 0,
                source: String = "", volume: String = "") {
        self.state = state
        self.origin = origin
        self.sharp = sharp
        self.source = source
        self.volume = volume
    }

    /// One `ScanBatch.world` row; nil for a malformed one.
    public static func row(_ entry: [Any]) -> (lat: Int, lon: Int, tile: O4WorldTile)? {
        guard entry.count >= 7,
              let lat = (entry[0] as? NSNumber)?.intValue,
              let lon = (entry[1] as? NSNumber)?.intValue,
              let state = State(rawValue: entry[2] as? String ?? "") else { return nil }
        return (lat, lon, O4WorldTile(state: state, origin: entry[3] as? String ?? "",
                                      sharp: (entry[4] as? NSNumber)?.doubleValue ?? 0,
                                      source: entry[5] as? String ?? "",
                                      volume: entry[6] as? String ?? ""))
    }

    /// Another tool made the mesh (drawn dotted).
    public var otherTool: Bool { origin == "other" }
}
