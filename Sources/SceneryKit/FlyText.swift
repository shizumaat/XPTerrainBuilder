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
    public static let quickTo = "To (optional)"
    public static let quickButton = "Use"
    /// A departure-only plan (#2023: From with an empty To): the card's
    /// words, and the status line's while it prepares and once it may leave.
    public static let noDestination = "no destination"
    public static let departureOnlyCard = "Prepares the departure area; the rest builds as you fly"
    public static let departureOnlyPreparing = "Departure only: the departure tile at full detail, the tiles around it as quick photos (Quick, whatever Photo detail ahead says); the rest builds as you fly."
    public static let departureOnlyFlying = "Departure only: the scenery ahead builds as you fly."
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
    /// The photo source the World pack's builds fetch (owner
    /// 2026-11-12T19:17Z): the global `default_website` the Build pane's
    /// "Tile / global default" means; read per build by the engine.
    public static let photoSourceLabel = "Photo source"
    public static let photoSourceKey = "default_website"
    /// `drape_photo_px` (RULINGS 2026-11-11j): (value, words).
    public static let drapePxKey = "drape_photo_px"
    public static let drapePxChoices: [(Int, String)] = [
        (512, "Quick"),
        (1024, "Sharper"),
        (4096, "Full detail (slow)"),
    ]
    public static let livePreview = "Live flight preview"
    public static let livePreviewHelp = "Shows the imagery installed for X-Plane on the map, square by square, as it arrives; zoom in to see it."
    /// The map's button beside the zoom controls (#2016): it pans to the
    /// aircraft and keeps the zoom; disabled, with `noAircraftPosition` as
    /// its help, while no position is current.
    public static let centerOnAircraft = "Center on aircraft"
    public static let noAircraftPosition = "No aircraft position: X-Plane is not running, or Fly mode is off."
    /// Seconds an `AircraftPosition` stays current: the watch sends one a
    /// second and nothing while X-Plane does not answer.
    public static let aircraftFreshS = 5.0

    /// True when the last position (received at `seenAt`) is younger than
    /// `aircraftFreshS` — the center-on-aircraft button's rule.
    public static func aircraftIsCurrent(seenAt: Date?, now: Date) -> Bool {
        guard let seenAt else { return false }
        let age = now.timeIntervalSince(seenAt)
        return age >= 0 && age < aircraftFreshS
    }
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
    /// The Fly view's ONE map key (owner 2026-11-12T19:11Z/19:12Z: one
    /// palette, drapes named as drapes): (key, words), drawn in this
    /// order. The World pack's states keep the Build map's words and
    /// colours (`O4WorldStateText`, `MapWorldStates`), and the flight's
    /// tiles use them once built; a build under way is its own colour,
    /// dashed for a drape and solid for a mesh. The Build map's tile
    /// legend is hidden on the Fly view. Python: `O4_Fly_Text.LEGEND`.
    public static let legend: [(String, String)] = [
        ("draping", "Photo being draped"),
        ("meshing", "Mesh being built"),
        ("draped", "Photo drape on X-Plane's mesh"),
        ("built", "Full: mesh and sharp imagery"),
        ("mesh", "Mesh: imagery sharpens in flight"),
        ("placeholder", "Placeholder: built or draped in flight"),
        ("own", "On the route, not built yet"),
        ("custom", "Orange band: custom airport patch, no auto patch"),
        ("sharp", "full-detail photo"),
    ]
    /// The keys drawn dashed (Qt: `O4_Qt_Fly_Layer.LEGEND_DASHED`).
    public static let dashedKeys: Set<String> = ["draping"]
    /// The legend's keys the map draws only while "Live flight preview"
    /// is on (a square of installed imagery at full resolution, #2020).
    public static let previewKeys: Set<String> = ["sharp"]

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
        let origin = plan.origin.isEmpty ? "?" : plan.origin
        let alternate = plan.alternate.map { "Alternate \($0.ident)" } ?? "No alternate in the plan"
        if departureOnly(plan) {
            return ["\(origin) → \(noDestination)", alternate, departureOnlyCard]
        }
        var ete = plan.eteSeconds ?? 0
        if ete == 0, cruise > 0 { ete = plan.routeKm / (cruise * 1.852) * 3600 }
        return [
            "\(origin) → \(plan.destination.isEmpty ? "?" : plan.destination)",
            alternate,
            "\(grouped(Int(plan.routeKm.rounded()))) km · \(duration(ete)) en route",
        ]
    }

    /// A plan with a departure and no destination (#2023): every waypoint
    /// at the first one's position (`O4_Fly_Text.departure_only`).
    public static func departureOnly(_ plan: O4FlightPlanRead?) -> Bool {
        guard let plan, let first = plan.waypoints.first else { return false }
        return plan.waypoints.allSatisfy { $0.lat == first.lat && $0.lon == first.lon }
    }

    /// A `FlightStatus` of a departure-only flight: no route, a departure
    /// job and no destination job (`O4_Fly_Text.status_departure_only`).
    public static func statusDepartureOnly(_ status: O4FlightStatus?) -> Bool {
        guard let status, status.routeKm == 0 else { return false }
        let roles = Set(status.jobs.map(\.role))
        return roles.contains("departure") && !roles.contains("destination")
    }

    /// The `destination` of `flight_update` when the quick entry adds a To
    /// to the active departure-only flight (#2023); nil otherwise
    /// (`O4_Fly_Text.added_destination`).
    public static func addedDestination(_ status: O4FlightStatus?,
                                        _ plan: O4FlightPlanRead?) -> O4FlightPlace? {
        guard let status, let plan, statusDepartureOnly(status), !departureOnly(plan),
              plan.waypoints.count >= 2, let first = plan.waypoints.first,
              let last = plan.waypoints.last,
              ["preparing", "ready", "flying"].contains(status.state) else { return nil }
        if let dep = status.jobs.first(where: { $0.role == "departure" }),
           dep.lat != Int(first.lat.rounded(.down)) || dep.lon != Int(first.lon.rounded(.down)) {
            return nil
        }
        return last
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
        if statusDepartureOnly(status) {
            return status.state == "preparing" ? departureOnlyPreparing : departureOnlyFlying
        }
        if status.state == "preparing" { return preparingLine(status) }
        if status.routeKm > 0 {
            return "\(grouped(Int(status.doneKm.rounded()))) of \(grouped(Int(status.routeKm.rounded()))) km flown"
        }
        return ""
    }

    static let jobWords: [String: String] = [
        "building": "building", "fetching": "building", "queued": "waiting",
        "late": "waiting", "staged": "ready", "swapped": "ready",
        "external": "ready", "failed": "failed", "shed": "skipped",
        "choice": "waiting for your choice",
    ]

    /// While a flight prepares: "Preparing: departure building ·
    /// destination waiting · 12 of 23 tiles ready" (owner
    /// 2026-11-12T19:02Z). Python: `O4_Fly_Text.preparing_line`.
    public static func preparingLine(_ status: O4FlightStatus) -> String {
        guard !status.jobs.isEmpty else { return "Preparing: planning the tiles" }
        var parts: [String] = []
        for role in ["departure", "destination"] {
            if let job = status.jobs.first(where: { $0.role == role }) {
                parts.append("\(role) \(jobWords[job.state] ?? job.state)")
            }
        }
        let ready = status.jobs.filter { ["staged", "swapped", "external"].contains($0.state) }.count
        parts.append("\(ready) of \(status.jobs.count) tiles ready")
        return "Preparing: " + parts.joined(separator: " · ")
    }

    static let hereJob: [String: String] = [
        "queued": "Quick photo: waiting for a build slot",
        "late": "Quick photo: waiting for a build slot",
        "staged": "Quick photo: built, going in",
        "failed": "Quick photo: the build failed",
    ]
    static let hereKind: [String: String] = [
        "placeholder": "Quick photo: not built yet",
        "drape": "Quick photo: in place",
        "full": "Scenery built at full detail",
    ]

    /// The Fly pane's block for the aircraft's own tile with no plan
    /// (#2020), from `WorldStatus.here`: the headline, the quick photo's
    /// state and the full-detail squares around the aircraft; empty
    /// before the engine reports one. Python: `O4_Fly_Text.here_lines`.
    public static func hereLines(_ here: O4JSON?) -> [String] {
        guard let here, here.objectValue?.isEmpty == false else { return [] }
        let airport = here["airport"]?.stringValue ?? ""
        let place = airport.isEmpty ? "tile \(here["tile"]?.stringValue ?? "?")" : airport
        let kind = here["kind"]?.stringValue ?? "", job = here["job"]?.stringValue ?? ""
        let squares = here["squares"]?.intValue ?? 0, sharp = here["sharp"]?.intValue ?? 0
        if kind.isEmpty && job.isEmpty { return ["Imagery at \(place): drawn by other scenery"] }
        var quick: String
        if job == "building" {
            let elapsed = max(0, here["elapsed_s"]?.intValue ?? 0)
            let minutes = max(1, Int(((here["estimate_s"]?.doubleValue ?? 0) / 60).rounded(.up)))
            quick = "Quick photo: building · \(elapsed / 60):"
                + String(format: "%02d", elapsed % 60) + " of about \(minutes) min"
        } else {
            quick = hereJob[job] ?? hereKind[kind] ?? ""
        }
        let ready = ["drape", "full"].contains(kind) && ["", "swapped"].contains(job)
            && sharp >= squares
        var lines = ["\(ready ? "Imagery ready" : "Preparing imagery") at \(place)"]
        if !quick.isEmpty { lines.append(quick) }
        if squares > 0 {
            lines.append("Full detail nearby: \(sharp) of \(squares) squares sharp")
        } else if job == "building", here["core"]?.boolValue == true {
            lines.append("Full detail nearby: fetching")
        }
        return lines
    }

    /// A corridor tile's legend key from its job's kind and state: a
    /// drape being draped or a mesh being built, the World pack's drape
    /// or full once in, else not built yet.
    public static func legendKey(kind: String, state: String) -> String {
        if state == "fetching" || state == "building" { return kind == "full" ? "meshing" : "draping" }
        if state == "staged" || state == "swapped" { return kind == "full" ? "built" : "draped" }
        return "own"
    }
}

extension O4FlightPlanRead {
    /// A two-airport plan from the departure + arrival quick entry, in
    /// `flight_plan_read`'s shape (`O4_Fly_Text.quick_plan`).
    /// No arrival: a departure-only plan of one waypoint (#2023).
    public static func quick(from dep: (ident: String, lat: Double, lon: Double),
                             to arr: (ident: String, lat: Double, lon: Double)?) -> O4FlightPlanRead {
        let places = ([dep] + (arr.map { [$0] } ?? [])).map {
            O4FlightPlace(ident: $0.ident.uppercased(), lat: $0.lat, lon: $0.lon,
                          altitudeFeet: nil, secondsAfterTakeoff: nil)
        }
        return O4FlightPlanRead(
            source: "quick", origin: places[0].ident,
            destination: places.count > 1 ? places[1].ident : "",
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

/// An adopted departure or destination (#2025): the flight card asks "fly
/// the existing mesh, or upgrade it first". Python: `O4_Fly_Text`
/// `choice_question` / `choice_keep_label` / `choice_upgrade_label`.
extension FlyText {
    public static let choiceKeep = "Fly the existing mesh"
    public static let choiceUpgrade = "Upgrade with XPTerrainBuilder grading"

    static func choicePlace(_ row: O4FlightStatus.Choice) -> String {
        let role = ["departure": "Departure", "destination": "Destination"][row.role] ?? "Airport"
        let ident = row.icao.isEmpty ? "tile " + String(format: "%+03d%+04d", row.lat, row.lon) : row.icao
        return "\(role) \(ident)"
    }

    /// The question while unanswered, the answer after.
    public static func choiceQuestion(_ row: O4FlightStatus.Choice) -> String {
        let place = choicePlace(row)
        switch row.choice {
        case "keep": return "\(place): flying the existing mesh"
        case "upgrade": return "\(place): upgrading with XPTerrainBuilder grading"
        default:
            return "\(place): its tile was not built by XPTerrainBuilder. Fly it as it is, or upgrade it first?"
        }
    }

    /// "Fly the existing mesh (built by Ortho4XP, patched: yes)".
    public static func choiceKeepLabel(_ row: O4FlightStatus.Choice) -> String {
        var words = "built by " + (row.builtBy.isEmpty ? "another tool" : row.builtBy)
        if row.builtBy.lowercased().hasPrefix("ortho4xp") {
            words += ", patched: " + (row.patched.isEmpty ? "unknown" : row.patched)
        }
        return "\(choiceKeep) (\(words))"
    }

    /// "Upgrade with XPTerrainBuilder grading (about 25 min)".
    public static func choiceUpgradeLabel(_ row: O4FlightStatus.Choice) -> String {
        guard let seconds = row.upgradeEstimateSeconds else { return choiceUpgrade }
        return "\(choiceUpgrade) (about \(max(1, Int((seconds / 60.0).rounded(.up)))) min)"
    }
}
