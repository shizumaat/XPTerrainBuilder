import Foundation

/// The words of imagery on demand in both apps (#1992 spec §7, P4): the
/// mirror of `Ortho4XP/src/O4_Imagery_OnDemand_Text.py`, which the Qt
/// window reads. `Ortho4XP/tests/test_imagery_ondemand_ui.py` parses the
/// `static let` literals below and requires them to equal the Python
/// constants, and requires `followValues` to fill every template slot.
/// The follow status line is a template per job state plus one detail
/// template, filled with the same number formats as the Qt window's, so
/// every `ImageryFollowStatus` field is shown, worded once.
public enum O4OnDemandText {
    // Favorites (spec §7: the Library's tile menu, the star beside the tile
    // pane's title and on the Build map's built cells, #2033; "pin" renamed
    // Favorite by RULINGS 2026-11-10c (1); identifiers and the engine wire
    // keep "pin" / `pinned`). A Favorite is storage priority: any built
    // tile, set any time, its sharp imagery made low-res last.
    public static let pinTitle = "Add to Favorites"
    public static let unpinTitle = "Remove from Favorites"
    public static let favoriteTitle = "Favorite"
    public static let pinnedState = "Favorite: its sharp imagery is kept longest"
    public static let pinnedBadge = "Favorite"
    public static let pinHelp = "A favorite tile keeps its sharp imagery longest: when storage is tight, its high-resolution imagery is the last made low-res again."
    public static let starAddHelp = "Make this tile a favorite: its sharp imagery is the last made low-res when storage is tight."
    public static let starRemoveHelp = "A favorite: its sharp imagery is the last made low-res when storage is tight. Click to remove it from Favorites."

    /// The star's tooltip for a tile that is (or is not) a favorite.
    public static func starHelp(_ pinned: Bool) -> String { pinned ? starRemoveHelp : starAddHelp }

    // Storage (spec §6.3 / §7: the ondemand row and its pins line).
    public static let makeLowResTitle = "Make all low-res again"
    public static let makeLowResNone = "No sharp imagery to make low-res again."
    public static let pinsLine = "Favorites: {bytes} in {files} texture(s), made low-res last"
    public static let coresLine = "{files} of them near airports, made low-res last"
    public static let olderSharpNote = "Sharp imagery near flown areas is made low-res again, not deleted, and fetched again when you fly near; favorites are kept."

    // The follow status line (spec §7: the activity area).
    public static let followStartTitle = "Follow X-Plane"
    public static let followStopTitle = "Stop Following"
    public static let followStarting = "Starting to follow X-Plane…"
    public static let followWaiting = "Waiting for X-Plane: {reason}"
    public static let followFollowing = "Following X-Plane: {sharp} of {textures} sharp nearby, {in_flight} downloading, {late} late"
    public static let followPaused = "Imagery paused: {reason}"
    public static let followStopped = "Not following X-Plane"
    public static let followError = "Following stopped: {reason}"
    public static let followDetail = "{queued} queued · {slots} at a time · {buffer} · {landed} landed ({bytes_landed}) · {failed} failed · X-Plane {xplane} at {lat}, {lon}, {speed} kt, track {track}° · {flight_loads} flight loads · {jumps} jumps · {reloads} reload offers"
    public static let waitingReason = "its Web API is not answering"
    /// The reload offer under the follow line (#2019, owner 2026-11-12:
    /// X-Plane reloads only when the user asks): its line per
    /// `reloadOffer` code and the button that sends `scenery_reload`.
    public static let reloadSceneryTitle = "Reload scenery"
    public static let reloadOfferImagery = "Sharper imagery landed after X-Plane loaded this area: reload the scenery to see it."
    public static let reloadOfferTiles = "New tiles replaced ones X-Plane had already loaded: reload the scenery to see them."
    public static let reloadOfferCoverage = "The World pack now covers more of the world: reload the scenery (or restart X-Plane) once so X-Plane can use it."

    /// The reload offer's line; empty when none is pending.
    public static func reloadOfferLine(_ code: String) -> String {
        switch code {
        case "imagery": return reloadOfferImagery
        case "tiles": return reloadOfferTiles
        case "coverage": return reloadOfferCoverage
        default: return ""
        }
    }
    /// The first sentence while the job follows (or waits) with no
    /// on-demand texture in its index.
    public static let followNoTiles = "No on-demand tiles to follow yet: build a tile with imagery on demand, or convert one in the Library"
    static let noTilesStates: Set<String> = ["waiting", "following"]
    public static let xplaneAnswering = "answering"
    public static let xplaneSilent = "not answering"
    public static let bufferNone = "nothing queued"
    public static let bufferAhead = "{seconds} s ahead"
    static let knotsPerMS = 1.943844

    /// `ImageryFollowStatus.state` → the line's first sentence.
    public static let followTemplates: [String: String] = [
        "starting": followStarting, "waiting": followWaiting,
        "following": followFollowing, "paused": followPaused,
        "stopped": followStopped, "error": followError,
    ]

    /// `12.3 MB` / `1.25 GB` (decimal), the same in both apps.
    public static func sizeText(_ bytes: Int64) -> String {
        let value = Double(bytes)
        return value >= 1e9 ? String(format: "%.2f GB", value / 1e9)
            : String(format: "%.1f MB", value / 1e6)
    }

    /// The "Make all low-res again" confirmation: the space it frees.
    public static func makeLowResMessage(freedBytes: Int64, textures: Int) -> String {
        "This makes \(textures) sharp texture(s) low-res again and frees \(sizeText(freedBytes)). "
            + "They are fetched again when you fly near; favorites are kept."
    }

    /// The Storage row's extra lines: the airport cores among the counted
    /// textures (when any), then the favorites, inside the ortho budget.
    public static func pinsText(bytes: Int64, files: Int, cores: Int = 0) -> String {
        let pins = fill(pinsLine, ["bytes": sizeText(bytes), "files": "\(files)"])
        return cores == 0 ? pins : fill(coresLine, ["files": "\(cores)"]) + "\n" + pins
    }

    /// One sentence for an `imagery_pin` reply.
    public static func pinDone(_ result: O4ImageryPinResult) -> String {
        if !result.pinned { return "\(result.tile) is no longer a favorite." }
        if result.served == 0, result.toFetch == 0 { return "\(result.tile) is a favorite." }
        return "\(result.tile) is a favorite: \(result.served) texture(s) sharp now, \(result.toFetch) to fetch."
    }

    /// The template slots of one status, formatted as the Qt window does.
    public static func followValues(_ s: O4ImageryFollowStatus) -> [String: String] {
        [
            "reason": s.reason.isEmpty ? waitingReason : s.reason,
            "sharp": "\(s.sharp)", "textures": "\(s.textures)",
            "in_flight": "\(s.inFlight)", "late": "\(s.late)",
            "queued": "\(s.queued)", "slots": "\(max(1, s.slots))",
            "buffer": s.bufferSeconds.map {
                fill(bufferAhead, ["seconds": String(format: "%.0f", $0)])
            } ?? bufferNone,
            "landed": "\(s.landed)", "bytes_landed": sizeText(s.bytesLanded),
            "failed": "\(s.failed)",
            "xplane": s.xplane ? xplaneAnswering : xplaneSilent,
            "lat": String(format: "%.3f", s.lat), "lon": String(format: "%.3f", s.lon),
            "speed": String(format: "%.0f", s.speedMS * knotsPerMS),
            "track": String(format: "%.0f", s.trackDegrees),
            "flight_loads": "\(s.flightLoads)", "jumps": "\(s.jumps)", "reloads": "\(s.reloads)",
        ]
    }

    /// `(headline, detail)` of the status line for one status.
    public static func followLines(_ s: O4ImageryFollowStatus) -> (headline: String, detail: String) {
        let values = followValues(s)
        var template = followTemplates[s.state] ?? followStarting
        if noTilesStates.contains(s.state), s.textures == 0 { template = followNoTiles }
        return (fill(template, values), fill(followDetail, values))
    }

    /// The line's headline beside the Follow / Stop button (`running`):
    /// the status's own while the two agree; else -- before the job's
    /// first status, or a stale one -- "Starting..." or "Not following",
    /// so the line never reads "Not following X-Plane" beside "Stop
    /// Following" (#2028). Python: `follow_headline`.
    public static func followHeadline(_ s: O4ImageryFollowStatus?, running: Bool) -> String {
        if let s, s.running == running { return followLines(s).headline }
        return running ? followStarting : followStopped
    }

    // A background core sharpening's row in the Build view's Activity
    // list (#2039, `ImageryCoresProgress`): the status per state, the
    // tile's coordinate the row's title. Python: `CORES_ROW_TEMPLATES`.
    public static let coresRowActive = "Sharpening airport imagery · {done} of {total} squares"
    public static let coresRowDone = "Airport imagery sharp · {done} of {total} squares"
    public static let coresRowError = "Sharpening airport imagery failed · {failed} of {total} squares failed"
    public static let coresRowStopped = "Sharpening airport imagery stopped · {done} of {total} squares"
    public static let coresRowStopHelp = "Stop sharpening this tile's airport imagery: the squares not started stay low-res until you fly near"

    /// The status line of an `ImageryCoresProgress` row. Python:
    /// `cores_row_status`.
    public static func coresRowStatus(_ p: O4ImageryCoresProgress) -> String {
        let template: String
        switch p.state {
        case "done": template = coresRowDone
        case "error": template = coresRowError
        case "stopped": template = coresRowStopped
        default: template = coresRowActive
        }
        return fill(template, ["done": "\(p.done)", "total": "\(p.total)", "failed": "\(p.failed)"])
    }

    /// `template` with each `{key}` replaced (Python's `str.format`).
    static func fill(_ template: String, _ values: [String: String]) -> String {
        values.reduce(template) { text, pair in
            text.replacingOccurrences(of: "{\(pair.key)}", with: pair.value)
        }
    }
}
