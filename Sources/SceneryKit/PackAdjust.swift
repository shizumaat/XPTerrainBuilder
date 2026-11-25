import Foundation

/// One adjustment of an airport pack (engine `PackAdjust.items`, issue
/// #1916): `trees` (point old flat forests at the X-Plane 12 3D trees),
/// `drapes` (hide the package's draped photos over the airport), `ground`
/// (hide its large ground textures, #1962), `terrain` (hide its objects
/// that model terrain where detailed elevation covers them, RULINGS
/// 2026-11-13i), `generic` (hide the stock X-Plane ground any overlay
/// pack drapes over the tile, with the `hectares` it covers, #2085) — each a checkbox, ticked when the sheet opens as
/// `checked` says (the engine's `adjust_stage.UNCHECKED`: only `ground`,
/// RULINGS 2026-11-09a (3); `terrain` opens ticked since owner
/// 2026-11-15T13:12Z) — or `flatten` (the apt.dat's `1302 flatten 1`, removed with no
/// question: `automatic`). In the pack row's Adjust… (`state` "adjust")
/// `checked` is the pack as it is, `applied` says the live file carries
/// it and `rebuild` that the tile's mesh reads it (the terrain objects).
public struct O4PackAdjustItem: Sendable, Equatable, Identifiable {
    public let key: String
    /// Definitions (`trees`, `drapes`, `ground`, `terrain`).
    public let count: Int
    /// Polygons drawing them.
    public let uses: Int
    public let automatic: Bool
    /// Ticked when the question opens.
    public let checked: Bool
    /// Hectares the row's polygons cover (`generic`; 0 otherwise).
    public let hectares: Int
    /// Adjust…: the pack's live file carries it.
    public let applied: Bool
    /// A change to it also needs the tile rebuilt (`terrain`).
    public let rebuild: Bool
    /// `terrain` in the pack row's Adjust… (#2272): every terrain object
    /// the last build recognised in the pack, each ticked when the row
    /// hides it — the user's per-object override.
    public let objects: [O4PackTerrainObject]
    public var id: String { key }

    public init(key: String, count: Int, uses: Int, automatic: Bool,
                checked: Bool = true, hectares: Int = 0,
                applied: Bool = false, rebuild: Bool = false,
                objects: [O4PackTerrainObject] = []) {
        self.key = key
        self.count = count
        self.uses = uses
        self.automatic = automatic
        self.checked = checked
        self.hectares = hectares
        self.applied = applied
        self.rebuild = rebuild
        self.objects = objects
    }

    /// The row's title.
    public var title: String { O4PackAdjustCopy.itemTitles[key] ?? key }
    /// The row's one-line explanation.
    public var detail: String {
        let text = (O4PackAdjustCopy.itemDetails[key] ?? "")
            .replacingOccurrences(of: "{n}", with: "\(count)")
            .replacingOccurrences(of: "{uses}", with: "\(uses)")
            .replacingOccurrences(of: "{ha}", with: hectares.formatted(
                .number.locale(Locale(identifier: "en_US"))))
        return rebuild ? text + " " + O4PackAdjustCopy.rebuildNote : text
    }

    /// The tick that changes nothing: the pack as it is (Adjust…), or not
    /// applied (a build's question).
    public func baseline(editing: Bool) -> Bool { editing ? checked : false }
}

/// One terrain object of a pack (#2272, the `terrain` row's `objects`):
/// `hideable` when the tile's detailed elevation matches it (the row hides
/// it unless the user keeps it), `hidden` when the row hides it now.
public struct O4PackTerrainObject: Sendable, Equatable, Identifiable {
    public let path: String
    public let hideable: Bool
    public let hidden: Bool
    public var id: String { path }

    public init(path: String, hideable: Bool, hidden: Bool) {
        self.path = path
        self.hideable = hideable
        self.hidden = hidden
    }

    /// The file name the row shows.
    public var name: String { (path as NSString).lastPathComponent }
    /// The object's one-line explanation.
    public var detail: String {
        hideable ? O4PackAdjustCopy.terrainObjectMatched : O4PackAdjustCopy.terrainObjectKept
    }
}

/// A tile a pack answer still owes a rebuild (engine
/// `o4_engine.tile_rebuild_pending`, `PackAdjust` `state` "pending" after a
/// run): the terrain objects were hidden or shown after its vector step.
public struct O4PackAdjustPending: Sendable, Equatable, Identifiable {
    public let id: String
    public let lat: Int
    public let lon: Int
    public let tile: String
    public let pack: String
    /// "hidden" or "shown".
    public let change: String

    public init(id: String, lat: Int, lon: Int, tile: String, pack: String, change: String) {
        self.id = id
        self.lat = lat
        self.lon = lon
        self.tile = tile
        self.pack = pack
        self.change = change
    }
}

/// An airport pack's adjustments as ONE question (engine `PackAdjust`,
/// capability `pack_adjust`, issue #1916). `state` "found" (a build) or
/// "ask" (the report): Apply sends `pack_adjust` "update" with the checked
/// rows and every row shown, Never for this pack "never", Not now
/// nothing. "adjust" (capability `pack_adjust_edit`) is the pack row's
/// Adjust…: every row ticked as the pack is now and the Optimise `steps`;
/// Apply sends "change" with the checked rows, every row shown and the
/// checked steps (only what differs is written), Cancel nothing. The
/// other states are a command's outcome; `rebuild` says the tile must be
/// rebuilt (a terrain objects change).
public struct O4PackAdjust: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    public let items: [O4PackAdjustItem]
    public let files: [String]
    public let state: String
    public let error: String
    /// Adjust…: the "Optimise pack" steps with work on the tile.
    public let steps: [O4PackOptimiseStep]
    /// Adjust…: the steps the pack's live recipe carries.
    public let stepsOn: [String]
    /// An outcome: the change needs the tile rebuilt.
    public let rebuild: Bool
    /// `state` "pending": the tiles still owed a rebuild.
    public let pending: [O4PackAdjustPending]

    /// One question per pack, tile and row set.
    public var id: String {
        "\(packRoot)|\(lat)|\(lon)|" + items.map(\.key).joined(separator: ",")
    }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                items: [O4PackAdjustItem], files: [String], state: String,
                error: String, steps: [O4PackOptimiseStep] = [],
                stepsOn: [String] = [], rebuild: Bool = false,
                pending: [O4PackAdjustPending] = []) {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.items = items
        self.files = files
        self.state = state
        self.error = error
        self.steps = steps
        self.stepsOn = stepsOn
        self.rebuild = rebuild
        self.pending = pending
    }

    /// The rows the user chooses (each checked when the question opens).
    public var choices: [O4PackAdjustItem] { items.filter { !$0.automatic } }
    /// The rows the app applies with no question.
    public var automatic: [O4PackAdjustItem] { items.filter(\.automatic) }
    /// The pack row's Adjust….
    public var editing: Bool { state == "adjust" }
    /// A question to ask: a build's or the report's, with a choice in it,
    /// or the pack row's Adjust….
    public var asks: Bool {
        ((state == "found" || state == "ask") && !choices.isEmpty)
            || (editing && (!choices.isEmpty || !steps.isEmpty))
    }
    public var titleText: String {
        editing ? O4PackAdjustCopy.editTitle(pack: pack) : O4PackAdjustCopy.title(pack: pack)
    }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_Adjust.py`, whose twin
/// `tests/test_qt_pack_adjust.py` reads this file to pin the parity).
public enum O4PackAdjustCopy {
    public static func title(pack: String) -> String {
        "Adjust “\(pack)”?"
    }

    public static let body = "The app is modifying this airport package. "
        + "These changes help it fit your scenery. Choose what to apply:"

    /// Per row: its checkbox (or, automatic, its label).
    public static let itemTitles: [String: String] = [
        "trees": "Update trees",
        "drapes": "Hide draped orthophotos included with the package",
        "ground": "Hide large ground textures included with the package",
        "terrain": "Hide terrain objects included with the package",
        "generic": "Hide generic X-Plane ground textures the package drapes",
        "flatten": "Remove the airport’s flatten flag (always)",
    ]

    /// Per row: its explanation.
    public static let itemDetails: [String: String] = [
        "trees": "{n} old flat (X-Plane 11) tree resources become X-Plane 12 "
            + "3D trees.",
        "drapes": "{n} photo images ({uses} polygons) laid over the airport "
            + "cover the tile’s imagery.",
        "ground": "{n} painted ground or grass images ({uses} polygons) laid "
            + "mostly over unpaved ground at the airport cover the tile’s "
            + "imagery.",
        "terrain": "{n} objects ({uses} placements) model hills or cliffs "
            + "that the tile’s detailed elevation data already describes. "
            + "The package’s other objects are then placed on that "
            + "terrain.",
        "generic": "{n} stock X-Plane grass, sand or scrub textures ({uses} "
            + "polygons, about {ha} ha) cover the tile’s imagery.",
        "flatten": "The apt.dat asks X-Plane to flatten the airport, which "
            + "does not work with this app’s terrain mesh.",
    ]

    public static let detail = "The original files are kept as backups. Undo "
        + "is Restore originals on the pack’s row under Modified airports."

    public static let applyButton = "Apply"
    public static let notNowButton = "Not now"
    public static let neverButton = "Never for this pack"

    // The pack row's Adjust… (owner 2026-11-15T13:12Z).
    public static func editTitle(pack: String) -> String {
        "Adjust “\(pack)”"
    }

    public static let editBody = "Change what the app does to this airport "
        + "package. Only what you change is written again, from the original files."
    public static let optimiseHeading = "Optimise pack:"
    // The terrain row's per-object choice (#2272, owner 2026-11-24T15:33Z).
    public static let terrainObjectsHeading = "Terrain objects to hide:"
    public static let terrainObjectMatched = "The tile’s detailed elevation "
        + "matches it: hidden unless you keep it."
    public static let terrainObjectKept = "It models detail the tile’s elevation "
        + "data lacks: kept unless you hide it."
    public static let rebuildNote = "Changing this also rebuilds the tile: the "
        + "ground under these objects is shaped to them while they are shown."
    public static let applyRebuildButton = "Apply and rebuild tile"
    public static let cancelButton = "Cancel"
    public static let adjustButton = "Adjust…"
    public static let adjustHelp = "Adjust: change what is hidden or optimised "
        + "in this package. Only the package’s scenery file is written again; a "
        + "change to its terrain objects also rebuilds the tile."

    public static func rebuildLater(tile: String, pack: String, reason: String) -> String {
        "Rebuild tile \(tile) to finish the change to \(pack)’s terrain objects: \(reason)"
    }

    public static func rebuildQueued(tile: String, pack: String) -> String {
        "Tile \(tile) will be rebuilt when this run finishes, to match the change to \(pack)’s terrain objects."
    }

    public static func rebuilding(tile: String, pack: String, change: String) -> String {
        "Rebuilding tile \(tile) to match: terrain objects \(change) in “\(pack)”."
    }
}
