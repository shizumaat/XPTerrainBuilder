import Foundation

/// The Fly pane's words (spec `Ortho4XP/docs/specs/
/// flight-manager-and-world-20261110.md` §4.3, §6.2, §14; lane U2). The
/// Qt window's `Ortho4XP/src/O4_Fly_Text.py` holds the same words and
/// rules; `Ortho4XP/tests/test_fly_pane.py` checks the words here and
/// `FlyPaneTests` checks the rules against the shared fixture
/// `Ortho4XP/tests/fixtures/fly_pane_cases.json`.
///
/// The plan-tier words "placeholder", "drape", "light" never reach the
/// user (§14): the map legend says `legend`.
public enum FlyText {
    public static let planSourceLabel = "Flight plan"
    public static let planChoose = "Choose a flight…"
    public static let planSimbrief = "SimBrief: latest plan"
    public static let planNone = "No plan: follow the aircraft"
    public static let simbriefPlaceholder = FlightPlanCopy.simBriefPlaceholder
    public static let simbriefButton = "Fetch"
    public static let openPlan = FlightPlanCopy.openButton
    public static let quickFrom = "From"
    public static let quickTo = "To"
    public static let quickButton = "Use"
    public static let prepare = "Prepare flight"
    public static let buildAlternate = "Also build the alternate"
    public static let cruiseLabel = "Cruise speed (kt)"
    public static let corridorLabel = "Corridor (km each side)"
    public static let simPriorityLabel = "While flying"
    /// `fly_sim_priority` (§5.5): (value, words).
    public static let simPriorities: [(String, String)] = [
        ("smooth", "Smooth flying first"),
        ("balanced", "Balanced"),
        ("fast", "Build fastest"),
    ]
    public static let drapePxLabel = "Photo detail ahead"
    /// `drape_photo_px` (RULINGS 2026-11-11j): (value, words).
    public static let drapePxKey = "drape_photo_px"
    public static let drapePxChoices: [(Int, String)] = [
        (512, "Quick"),
        (1024, "Sharper"),
        (4096, "Full detail (slow)"),
    ]
    public static let livePreview = "Live flight preview"
    public static let livePreviewHelp = "Shows the imagery installed for X-Plane on the map, square by square, as it arrives; zoom in to see it."
    public static let divert = "Divert…"
    public static let endFlight = "End flight"
    public static let noFlightManager = "This engine has no flight manager yet."
    public static let noStatus = "Prepare a flight to see what it needs."

    /// §6.2's readiness rows, in the engine's order.
    public static let readinessLabels: [String: String] = [
        "world": "World pack in X-Plane",
        "budget": "Fits the disk budget",
        "network": "Internet, or everything on disk",
        "prefetch": "Map data and elevation",
        "departure": "Departure airport",
        "first_window": "Scenery around the departure",
        "route": "Route built ahead in time",
        "destination": "Destination airport",
        "alternate": "Alternate airport",
        "loaded": "Loaded in X-Plane",
    ]
    static let stateMarks: [String: String] = [
        "done": "✓", "working": "…", "waiting": "○", "blocked": "!", "failed": "✕",
    ]
    /// The map legend (§14): (key, words), drawn in this order.
    public static let legend: [(String, String)] = [
        ("own", "X-Plane's own scenery"),
        ("quick", "photo, quick"),
        ("built", "built"),
        ("building", "building"),
    ]

    public static let defaultCruiseKt = 250
    public static let defaultCorridorKm = 20
    static let ktToMS = 1.852 * 1000.0 / 3600.0

    static let worldStates: [String: String] = [
        "off": "World pack off", "idle": "World pack ready",
        "following": "World pack following the aircraft",
        "building": "World pack building ahead",
        "paused": "World pack paused", "error": "World pack stopped",
    ]

    /// "1,234" (Python's `format(n, ",")`).
    static func grouped(_ value: Int) -> String {
        let digits = String(abs(value))
        var out = ""
        for (i, ch) in digits.enumerated() {
            if i > 0, (digits.count - i) % 3 == 0 { out.append(",") }
            out.append(ch)
        }
        return (value < 0 ? "-" : "") + out
    }

    /// One `flight_plans_list` row in the plan menu: "CYLW → CYYC
    /// (CYLWCYYC)"; the bare name when the plan names no airports.
    public static func planRowLabel(_ row: O4FlightPlanFile) -> String {
        if !row.origin.isEmpty || !row.destination.isEmpty {
            return "\(row.origin.isEmpty ? "?" : row.origin) → "
                + "\(row.destination.isEmpty ? "?" : row.destination) (\(row.name))"
        }
        return row.name
    }

    public static func unknownAirport(_ ident: String) -> String {
        let code = ident.trimmingCharacters(in: .whitespaces).uppercased()
        return "No airport \(code.isEmpty ? "?" : code) in X-Plane's list."
    }

    /// A refused `flight_*` command, for the user: an engine without the
    /// command says `noFlightManager`, else the engine's own sentence.
    public static func refusal(_ error: String) -> String {
        error.isEmpty || error.hasPrefix("unknown command") ? noFlightManager : error
    }

    /// The cruise speed field's prefill: the plan's, else 250 kt.
    public static func cruiseKt(_ plan: O4FlightPlanRead?) -> Int {
        guard let ms = plan?.cruiseMS, ms > 0 else { return defaultCruiseKt }
        return Int((ms / ktToMS).rounded())
    }

    static func duration(_ seconds: Double) -> String {
        let minutes = Int((seconds / 60).rounded())
        if minutes < 60 { return "\(minutes) min" }
        return "\(minutes / 60) h " + String(format: "%02d min", minutes % 60)
    }

    /// The flight card: route, alternate, distance and time en route
    /// (the plan's, else the distance at `cruise` knots).
    public static func cardLines(_ plan: O4FlightPlanRead, cruise: Double) -> [String] {
        var ete = plan.eteSeconds ?? 0
        if ete == 0, cruise > 0 { ete = plan.routeKm / (cruise * 1.852) * 3600 }
        return [
            "\(plan.origin.isEmpty ? "?" : plan.origin) → \(plan.destination.isEmpty ? "?" : plan.destination)",
            plan.alternate.map { "Alternate \($0.ident)" } ?? "No alternate in the plan",
            "\(grouped(Int(plan.routeKm.rounded()))) km · \(duration(ete)) en route",
        ]
    }

    /// "Ready in about 12 min"; a dash when there is no defensible figure
    /// (`O4_Flight_Schedule.countdown_text`).
    public static func countdown(_ seconds: Double?) -> String {
        guard let seconds else { return "Ready in —" }
        if seconds <= 0 { return "Ready" }
        if seconds < 60 { return "Ready in under a minute" }
        return "Ready in about \(Int((seconds / 60).rounded(.up))) min"
    }

    /// One readiness row as a line: "✓ Departure airport",
    /// "… Destination airport · about 4 min".
    public static func itemText(_ item: O4FlightStatus.Item) -> String {
        let text = "\(stateMarks[item.state] ?? "○") \(readinessLabels[item.key] ?? item.key)"
        if !item.detail.isEmpty { return text + " · " + item.detail }
        if !["done", "failed", "blocked"].contains(item.state), let eta = item.etaSeconds, eta > 0 {
            return text + " · about \(max(1, Int((eta / 60).rounded(.up)))) min"
        }
        return text
    }

    /// The World pack's one line from a `WorldStatus` event's fields; a
    /// dash before the engine reports one.
    public static func worldLine(_ status: O4JSON?) -> String {
        guard let status, status.objectValue?.isEmpty == false else { return "World pack: —" }
        var text = worldStates[status["state"]?.stringValue ?? ""] ?? "World pack"
        let building = status["building"]?.arrayValue?.count ?? 0
        if building > 0 { text += " · \(building) building" }
        let loaded = status["loaded"]?.arrayValue?.count ?? 0
        if loaded > 0 { text += " · \(loaded) in X-Plane" }
        let reason = status["reason"]?.stringValue ?? ""
        return reason.isEmpty ? text : text + " · " + reason
    }

    /// The flight's state line under the countdown: the engine's
    /// sentence, else the route flown so far.
    public static func statusLine(_ status: O4FlightStatus?) -> String {
        guard let status else { return "" }
        if !status.reason.isEmpty { return status.reason }
        if status.routeKm > 0 {
            return "\(grouped(Int(status.doneKm.rounded()))) of \(grouped(Int(status.routeKm.rounded()))) km flown"
        }
        return ""
    }

    /// A corridor tile's legend key from its job's kind and state.
    public static func legendKey(kind: String, state: String) -> String {
        if state == "fetching" || state == "building" { return "building" }
        if state == "staged" || state == "swapped" { return kind == "full" ? "built" : "quick" }
        return "own"
    }
}

extension O4FlightPlanRead {
    /// A two-airport plan from the departure + arrival quick entry, in
    /// `flight_plan_read`'s shape (`O4_Fly_Text.quick_plan`).
    public static func quick(from dep: (ident: String, lat: Double, lon: Double),
                             to arr: (ident: String, lat: Double, lon: Double)) -> O4FlightPlanRead {
        let places = [dep, arr].map {
            O4FlightPlace(ident: $0.ident.uppercased(), lat: $0.lat, lon: $0.lon,
                          altitudeFeet: nil, secondsAfterTakeoff: nil)
        }
        return O4FlightPlanRead(
            source: "quick", origin: places[0].ident, destination: places[1].ident,
            waypoints: places, alternate: nil, eteSeconds: nil, cruiseMS: nil,
            cruiseAltitudeFeet: nil,
            routeKm: RouteTiles.routeLengthKm(places.map { (lat: $0.lat, lon: $0.lon) }))
    }

    /// The plan as the `plan` argument of `flight_create` (the
    /// `flight_plan_read` shape).
    public var wire: [String: Any] {
        func place(_ p: O4FlightPlace) -> [String: Any] {
            ["ident": p.ident, "lat": p.lat, "lon": p.lon,
             "alt_ft": p.altitudeFeet as Any? ?? NSNull(),
             "t_s": p.secondsAfterTakeoff as Any? ?? NSNull()]
        }
        return ["source": source, "origin": origin, "destination": destination,
                "waypoints": waypoints.map(place),
                "alternate": alternate.map(place) as Any? ?? NSNull(),
                "ete_s": eteSeconds as Any? ?? NSNull(),
                "cruise_ms": cruiseMS as Any? ?? NSNull(),
                "cruise_alt_ft": cruiseAltitudeFeet as Any? ?? NSNull(),
                "route_km": routeKm]
    }
}
