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
/// The `flight_*` commands and `FlightStatus` belong to lane F1b: until
/// an engine has them the pane says `FlyText.noFlightManager` and is
/// exercised on the shared fixture (`FlyPaneTests`).
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
    /// #2001's checkbox; the imagery drawing is a stub (lane U2 report).
    @Published var livePreview: Bool {
        didSet { UserDefaults.standard.set(livePreview, forKey: Self.livePreviewKey) }
    }
    @Published private(set) var status: O4FlightStatus?
    @Published private(set) var worldStatus: O4JSON?
    @Published private(set) var track = AircraftTrack()
    @Published private(set) var position: O4AircraftPosition?
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
    }

    // MARK: - The map's layers

    var drawing: [[GeoPoint]] {
        guard let plan else { return [] }
        return RouteTiles.drawing(points: plan.waypoints.map { (lat: $0.lat, lon: $0.lon) })
    }

    var cells: [FlyCell] {
        FlyLayers.corridorCells(plan: plan, corridorKm: Double(corridorKm), jobs: status?.jobs ?? [])
    }

    // MARK: - Events

    func show(_ position: O4AircraftPosition) {
        self.position = position
        track.add(lat: position.lat, lon: position.lon, track: position.trackDegrees)
    }

    /// A `FlightStatus` (lane F1b adds its `O4Event` case and calls this).
    func show(_ status: O4FlightStatus) { self.status = status }

    /// A `WorldStatus`'s fields (lane W1 calls this).
    func showWorld(_ fields: O4JSON) { worldStatus = fields }

    /// Aircraft positions while Fly is shown (`aircraft_watch`).
    func setWatching(_ on: Bool) {
        guard on != watching, let context = build?.libraryContext() else { return }
        watching = on
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

    func divert() {
        guard let flight = status?.flight else { return }
        command("flight_divert", ["flight": flight, "to": "alternate"]) { _ in }
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
