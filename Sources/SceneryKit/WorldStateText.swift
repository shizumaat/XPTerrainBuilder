import Foundation

/// The words of a tile's World state in both apps (#2024): the Build map's
/// legend, the Library's World column and the tile pane's "World pack" row. The mirror of
/// `Ortho4XP/src/O4_World_State_Text.py`, which the Qt window reads;
/// `Ortho4XP/tests/test_world_state.py` parses the literals below and
/// requires them to equal the Python ones.
public enum O4WorldStateText {
    // The map key's World-state sentences (`MapKeyText`, #2031).
    public static let legendFull = "Full: mesh and sharp imagery"
    public static let legendMesh = "Mesh only: imagery sharpens in flight"
    public static let legendDrape = "Photo drape on X-Plane's mesh"
    public static let legendPlaceholder = "Placeholder: built or draped in flight"
    public static let legendOtherTool = "Dotted: a tile another tool built"
    /// The orange band (#1229) the owner asked about (2026-11-12, "gold").
    public static let legendCustomPatch = "Orange band: custom airport patch, no auto patch"

    // The Library's World column.
    public static let columnTitle = "World"
    public static let stateWords: [String: String] = [
        "full": "Full",
        "drape": "Drape",
        "placeholder": "Placeholder",
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

    // The tile pane's "World pack" row (owner 2026-11-12T20:23Z: a tile
    // fully built in the World pack must not read "not built").
    public static let paneRowTitle = "World pack"
    public static let paneBuilt = "Built (in the World pack): {what}"
    public static let paneWhat: [String: String] = [
        "full": "mesh + full imagery",
        "drape": "photo drape",
    ]
    public static let paneMesh = "mesh, {percent}% sharp"
    public static let panePlaceholder = "Placeholder in the World pack: not built yet"
    /// The tile title's suffix where the Tiles folder holds no build but
    /// the World pack holds the tile (in place of "(not built)").
    public static let titleInWorld = "(in the World pack)"
    public static let rebuildButton = "Rebuild Tile"
    public static let removeButton = "Remove from World Pack…"
    public static let removeTitle = "Remove tile {tile} from the World pack?"
    public static let removeMessage = "Its package is written first (XPTerrainBuilder_packages), then the tile is a placeholder again: X-Plane shows its own scenery there until the tile is built again. Its original folder (originals/) and its files on other drives are never touched."
    public static let removeConfirm = "Remove"
    public static let removed = "Tile {tile} is a placeholder again; its package: {package}"
    public static let removedNoPackage = "Tile {tile} is a placeholder again; no package was written: {why}"

    /// Does the World pack hold a real tile (not a placeholder) here?
    /// (Qt: `O4_World_State_Text.built_in_world`.)
    public static func builtInWorld(_ world: O4WorldTile?) -> Bool {
        guard let world else { return false }
        return [.full, .meshLowRes, .drape].contains(world.state)
    }

    /// The pane's status line (Qt: `pane_status`); empty when the World
    /// pack holds nothing of the tile.
    public static func paneStatus(_ world: O4WorldTile?) -> String {
        guard let world else { return "" }
        switch world.state {
        case .meshLowRes:
            let what = paneMesh.replacingOccurrences(
                of: "{percent}", with: String(Int((world.sharp * 100).rounded())))
            return paneBuilt.replacingOccurrences(of: "{what}", with: what)
        case .full, .drape:
            return paneBuilt.replacingOccurrences(of: "{what}",
                                                  with: paneWhat[world.state.rawValue] ?? "")
        case .placeholder:
            return panePlaceholder
        case .nothing:
            return ""
        }
    }

    /// Who made it and where its own files live (Qt: `pane_detail`):
    /// "built here · original folder kept"; empty for none.
    public static func paneDetail(_ world: O4WorldTile?) -> String {
        guard let world else { return "" }
        return [originWords[world.origin] ?? "", sourceText(world.source, volume: world.volume)]
            .filter { !$0.isEmpty }
            .joined(separator: " · ")
    }

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
/// volume, dsf]` and as a Library row's `world` dict.
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
    /// The tile's DSF in the World pack (#2027; nil from an older engine).
    public let dsf: String?

    public init(state: State, origin: String = "", sharp: Double = 0,
                source: String = "", volume: String = "", dsf: String? = nil) {
        self.state = state
        self.origin = origin
        self.sharp = sharp
        self.source = source
        self.volume = volume
        self.dsf = dsf
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
                                      volume: entry[6] as? String ?? "",
                                      dsf: entry.count > 7 ? entry[7] as? String : nil))
    }

    /// What "Show in Finder" reveals in the World pack (#2027): this
    /// tile's DSF there when the tile's build folder holds no DSF of its
    /// own (an adopted or converted tile keeps only its records in
    /// Tiles/), else nil (the build folder). Qt:
    /// `O4_World_State_Text.world_dsf`.
    public func revealDSF(_ info: O4TileInfo?) -> String? {
        guard let dsf, !dsf.isEmpty, info?.dsfPresent != true else { return nil }
        return dsf
    }

    /// Another tool made the mesh (drawn dotted).
    public var otherTool: Bool { origin == "other" }
}
