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
    // Favorites (spec §7: the Library's tile menu and the tile's info pane;
    // "pin" renamed Favorite by RULINGS 2026-11-10c (1); identifiers and the
    // engine wire keep "pin" / `pinned`).
    public static let pinTitle = "Add to Favorites"
    public static let unpinTitle = "Remove from Favorites"
    public static let pinRowTitle = "Favorite"
    public static let lowResState = "Sharp near the aircraft, low-res elsewhere"
    public static let pinnedState = "Kept at full resolution"
    public static let pinnedBadge = "Favorite"
    public static let pinHelp = "A favorite tile is fetched whole at full resolution. It counts toward the ortho budget and is the last imagery made low-res again when the budget is full."
    public static let notOnDemandState = "Built with full imagery everywhere; favorites are for tiles built with imagery on demand."

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
    public static let followDetail = "{queued} queued · {slots} at a time · {buffer} · {landed} landed ({bytes_landed}) · {failed} failed · X-Plane {xplane} at {lat}, {lon}, {speed} kt, track {track}° · {flight_loads} flight loads · {jumps} jumps · {reloads} reloads"
    public static let waitingReason = "its Web API is not answering"
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
        result.pinned
            ? "\(result.tile) is a favorite: \(result.served) texture(s) sharp now, \(result.toFetch) to fetch."
            : "\(result.tile) is no longer a favorite."
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
        let template = followTemplates[s.state] ?? followStarting
        return (fill(template, values), fill(followDetail, values))
    }

    /// `template` with each `{key}` replaced (Python's `str.format`).
    static func fill(_ template: String, _ values: [String: String]) -> String {
        values.reduce(template) { text, pair in
            text.replacingOccurrences(of: "{\(pair.key)}", with: pair.value)
        }
    }
}
