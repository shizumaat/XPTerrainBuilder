import Foundation
import SceneryKit
import UniformTypeIdentifiers
import AppKit

/// Fly mode's state (spec `flight-manager-and-world-20261110` §4.3, §14;
/// lane U2): the plan being named, the flight card's controls, the
/// flight manager's last `FlightStatus` / `WorldStatus`, and the aircraft
/// with its track for the map. The Qt window's `O4_Qt_Fly_Pane.FlyPane`
/// holds the same; words and rules are SceneryKit `FlyText` / `FlyLayers`.
///
/// The `flight_*` commands, `FlightStatus` and `FlightReady` are the
/// flight manager's (capability `flight_manager`); an engine without them
/// makes the pane say `FlyText.noFlightManager`.
@MainActor
final class FlyModel: ObservableObject {
    static let simPriorityKey = "FlySimPriority"
    static let livePreviewKey = "FlyLivePreview"

    weak var build: BuildModel?

    /// X-Plane's saved FMS plans (`flight_plans_list`), newest first.
    @Published private(set) var plans: [O4FlightPlanFile] = []
    /// The plan menu's choice: "", "simbrief", "none" or a plan's path.
    @Published var source = "" {
        didSet { if source != oldValue { choose(source) } }
    }
    @Published private(set) var plan: O4FlightPlanRead? {
        didSet { if let plan { cruiseKt = FlyText.cruiseKt(plan) } }
    }
    /// The last sentence for the user (a refusal, an unknown airport).
    @Published private(set) var message: String?
    @Published var quickFrom = ""
    @Published var quickTo = ""
    /// Off by default (RULINGS 2026-11-10g); per flight, never remembered.
    @Published var buildAlternate = false {
        didSet { if buildAlternate != oldValue { update(["build_alternate": buildAlternate]) } }
    }
    @Published var cruiseKt = FlyText.defaultCruiseKt
    @Published var corridorKm = FlyText.defaultCorridorKm
    @Published var simPriority: String {
        didSet { UserDefaults.standard.set(simPriority, forKey: Self.simPriorityKey) }
    }
    /// #2001's checkbox: the map draws each square's installed imagery
    /// (`preview`) while Fly shows.
    @Published var livePreview: Bool {
        didSet {
            UserDefaults.standard.set(livePreview, forKey: Self.livePreviewKey)
            preview.setEnabled(watching && livePreview)
        }
    }
    /// The drapes' photo width (`drape_photo_px`, the engine's global
    /// setting, read per tile by build-ahead; RULINGS 2026-11-11j).
    var drapePx: Int {
        get {
            guard let value = build?.configValue(for: FlyText.drapePxKey) else { return 512 }
            return value.intValue ?? Int(value.cfgLiteral) ?? 512
        }
        set {
            objectWillChange.send()
            build?.setConfigValue(FlyText.drapePxKey, to: .int(newValue))
        }
    }
    let preview = LivePreviewModel()
    @Published private(set) var status: O4FlightStatus?
    @Published private(set) var worldStatus: O4JSON?
    /// Build-ahead's tiles in free flight (`WorldStatus.jobs`).
    @Published private(set) var worldJobs: [O4FlightStatus.Job] = []
    @Published private(set) var track = AircraftTrack()
    @Published private(set) var position: O4AircraftPosition?
    /// When `position` arrived (`FlyText.aircraftIsCurrent`, #2016).
    @Published private(set) var positionAt: Date?
    /// "Divert…": the airport search sheet and its query (lane F2).
    @Published var divertShown = false
    @Published var divertQuery = ""
    /// The last `FlightNotice` (also posted as a system notification).
    @Published private(set) var notice: O4FlightNotice?
    private var watching = false

    var simBriefUser: String {
        get { UserDefaults.standard.string(forKey: FlightPlanSelection.simBriefKey) ?? "" }
        set {
            objectWillChange.send()
            UserDefaults.standard.set(newValue, forKey: FlightPlanSelection.simBriefKey)
        }
    }

    init(build: BuildModel) {
        self.build = build
        let defaults = UserDefaults.standard
        simPriority = defaults.string(forKey: Self.simPriorityKey) ?? "balanced"
        livePreview = defaults.bool(forKey: Self.livePreviewKey)
        preview.context = { [weak build] in
            guard let build, build.engineCapabilities.supports(O4EngineCapabilities.livePreview),
                  let context = build.libraryContext() else { return nil }
            return (context.client, context.sceneryDir)
        }
    }

    // MARK: - The map's layers

    var drawing: [[GeoPoint]] {
        guard let plan else { return [] }
        return RouteTiles.drawing(points: plan.waypoints.map { (lat: $0.lat, lon: $0.lon) })
    }

    var cells: [FlyCell] {
        FlyLayers.corridorCells(plan: plan, corridorKm: Double(corridorKm),
                                jobs: FlyLayers.mapJobs(flight: status?.jobs ?? [],
                                                        planned: plan != nil, ahead: worldJobs))
    }

    // MARK: - Events

    func show(_ position: O4AircraftPosition) {
        self.position = position
        positionAt = Date()
        track.add(lat: position.lat, lon: position.lon, track: position.trackDegrees)
    }

    /// A `FlightStatus` (the flight manager, every 2 s and on a change).
    func show(_ status: O4FlightStatus) { self.status = status }

    /// A `FlightReady`: `flight_plan_simbrief`'s plan, or its refusal.
    func showReady(_ reply: O4JSON) {
        if let error = reply["error"]?.stringValue, !error.isEmpty {
            message = FlyText.refusal(error)
        } else if let plan = O4FlightPlanRead.parse(reply["result"]) {
            message = nil
            self.plan = plan
        }
    }

    /// A `FlightNotice` (lane F2): a system notification, and the pane's
    /// last notice line.
    func show(_ notice: O4FlightNotice) {
        self.notice = notice
        FlightNotifier.post(notice)
    }

    /// A `WorldStatus` (every 2 s while build-ahead runs): the World line's
    /// fields and the tiles it lays ahead in free flight.
    func showWorld(_ status: O4WorldStatus) {
        worldStatus = .object([
            "state": .string(status.state), "reason": .string(status.reason),
            "building": .array(status.building.map { .string($0.tile) }),
            "loaded": .array(status.loaded.map { .string($0) }),
        ])
        if worldJobs != status.jobs { worldJobs = status.jobs }
    }

    /// Aircraft positions while Fly is shown (`aircraft_watch`).
    func setWatching(_ on: Bool) {
        guard on != watching, let context = build?.libraryContext() else { return }
        watching = on
        preview.setEnabled(on && livePreview)
        context.client.aircraftWatch(on: on)
        if on { refreshPlans() }
    }

    // MARK: - Naming the flight

    private var xplaneDir: String {
        UserDefaults.standard.string(forKey: PrefKeys.xplanePath) ?? ""
    }

    func refreshPlans() {
        guard let context = build?.libraryContext() else { return }
        context.client.flightPlansList(xplaneDir: xplaneDir) { rows in
            Task { @MainActor [weak self] in self?.plans = rows }
        }
    }

    private func choose(_ choice: String) {
        message = nil
        switch choice {
        case "": break
        case "simbrief": fetchSimBrief()
        case "none": plan = nil
        default: readPlan(path: choice)
        }
    }

    func readPlan(path: String) {
        guard let context = build?.libraryContext() else { return }
        context.client.flightPlanRead(path: path) { result in
            Task { @MainActor [weak self] in
                switch result {
                case .success(let plan): self?.plan = plan
                case .failure(let error): self?.message = error.message
                }
            }
        }
    }

    func openPlanFile() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = ["fms", "lnmpln"].compactMap { UTType(filenameExtension: $0) }
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        readPlan(path: url.path)
    }

    func fetchSimBrief() {
        command("flight_plan_simbrief", ["user": simBriefUser]) { _ in }
    }

    /// The departure + arrival quick entry, from X-Plane's airport list.
    func useQuickEntry() {
        guard let build else { return }
        func find(_ code: String) -> GlobalAirport? {
            let ident = code.trimmingCharacters(in: .whitespaces).uppercased()
            return build.globalAirports.first { $0.icao.uppercased() == ident }
        }
        guard let dep = find(quickFrom) else { message = FlyText.unknownAirport(quickFrom); return }
        guard let arr = find(quickTo) else { message = FlyText.unknownAirport(quickTo); return }
        message = nil
        plan = .quick(from: (dep.icao, dep.latitude, dep.longitude),
                      to: (arr.icao, arr.latitude, arr.longitude))
    }

    // MARK: - The flight manager (lane F1b's commands)

    func prepare() {
        guard let plan else { return }
        command("flight_create", ["plan": plan.wire, "build_alternate": buildAlternate,
                                  "cruise_kt": cruiseKt, "corridor_km": corridorKm]) { _ in }
    }

    private func update(_ arguments: [String: Any]) {
        guard let flight = status?.flight else { return }
        command("flight_update", arguments.merging(["flight": flight]) { a, _ in a }) { _ in }
    }

    /// "Divert…"'s airport search over X-Plane's airport list.
    var divertResults: [FlyDivertText.Airport] {
        guard let build else { return [] }
        let airports = build.globalAirports.map {
            FlyDivertText.Airport(ident: $0.icao, name: $0.name, lat: $0.latitude, lon: $0.longitude)
        }
        return FlyDivertText.matches(divertQuery, in: airports)
    }

    var hasAlternate: Bool { plan?.alternate != nil }

    /// `flight_divert`: the plan's alternate (nil) or a searched airport.
    func divert(to airport: FlyDivertText.Airport?) {
        guard let flight = status?.flight else { return }
        let to: Any = airport.map { ["ident": $0.ident, "lat": $0.lat, "lon": $0.lon] } ?? "alternate"
        divertShown = false
        divertQuery = ""
        command("flight_divert", ["flight": flight, "to": to]) { _ in }
    }

    /// The reload in the air (S6 (b)): "Reload scenery now" / "Not now".
    func reload(notNow: Bool) {
        guard let flight = status?.flight else { return }
        command("flight_reload", ["flight": flight, "not_now": notNow]) { _ in }
    }

    /// "Fly with X-Plane's own scenery there" (RULINGS 2026-11-10k Q3).
    func waiveOffline() {
        update(["waive_offline": true])
    }

    func endFlight() {
        guard let flight = status?.flight else { return }
        command("flight_end", ["flight": flight]) { [weak self] _ in self?.status = nil }
    }

    private func command(_ name: String, _ arguments: [String: Any],
                         then: @escaping @MainActor (O4JSON?) -> Void) {
        guard let context = build?.libraryContext() else { return }
        context.client.flightCommand(name, arguments: arguments) { result in
            Task { @MainActor [weak self] in
                switch result {
                case .success(let reply):
                    self?.message = nil
                    then(reply)
                case .failure(let error):
                    self?.message = FlyText.refusal(error.message)
                }
            }
        }
    }
}
