import AppKit
import Foundation
import SceneryKit
import UniformTypeIdentifiers

/// "Select from flight plan…" (issue #829), the state behind
/// `FlightPlanPanel` and `FlightRouteOverlay`; the Qt half is
/// `Ortho4XP/src/O4_Qt_Flight_Plan.py`, the rule both use is SceneryKit
/// `FlightPlanReader` + `RouteTiles` (twin of `O4_Flight_Plan.py`).
///
/// While the panel is open the map's selection is the tiles selected
/// before plus every tile within the radius of the route; the radius
/// changes it live. Select keeps it with the departure tile active; Cancel
/// puts the old selection back.
@MainActor
final class FlightPlanSelection: ObservableObject {
    static let unitKey = "FlightPlanUnit"
    static let radiusKey = "FlightPlanRadius"
    static let simBriefKey = "SimBriefUser"

    weak var build: BuildModel?

    @Published private(set) var isShown = false
    @Published private(set) var plan: FlightPlan?
    /// Why the last plan could not be read (nil = none).
    @Published private(set) var errorMessage: String?
    @Published private(set) var isFetching = false
    @Published private(set) var tiles: [AirportTile] = []
    /// The route as drawn (split at the antimeridian).
    @Published private(set) var drawing: [[GeoPoint]] = []
    /// Bumped when a new plan loads, so the map frames it.
    @Published private(set) var loads = 0
    @Published var simBriefUser: String {
        didSet { UserDefaults.standard.set(simBriefUser, forKey: Self.simBriefKey) }
    }
    @Published var unit: String {
        didSet {
            guard unit != oldValue else { return }
            let km = RouteTiles.radiusKm(radius, unit: oldValue)
            UserDefaults.standard.set(unit, forKey: Self.unitKey)
            radius = min(radiusMax, (km / RouteTiles.radiusKm(1, unit: unit)).rounded())
        }
    }
    @Published var radius: Double {
        didSet {
            UserDefaults.standard.set(radius, forKey: Self.radiusKey)
            refresh()
        }
    }

    private var base: Set<BuildModel.TileCoord> = []
    private var baseActive: BuildModel.TileCoord?

    init(build: BuildModel) {
        self.build = build
        let defaults = UserDefaults.standard
        let savedUnit = defaults.string(forKey: Self.unitKey) ?? "km"
        let unit = FlightPlanCopy.units.contains(savedUnit) ? savedUnit : "km"
        let saved = defaults.object(forKey: Self.radiusKey) as? Double
        self.unit = unit
        self.radius = saved ?? Double(FlightPlanCopy.radiusDefault[unit] ?? 50)
        self.simBriefUser = defaults.string(forKey: Self.simBriefKey) ?? ""
    }

    var radiusMax: Double { Double(FlightPlanCopy.radiusMax[unit] ?? 300) }

    // MARK: - Opening and closing

    func open() {
        guard !isShown, let build else { return }
        base = build.selected
        baseActive = build.activeTile
        plan = nil
        tiles = []
        drawing = []
        errorMessage = nil
        isShown = true
    }

    func select() {
        if let first = plan?.points.first {
            let tile = RouteTiles.tileOf(first.lat, first.lon)
            build?.activeTile = BuildModel.TileCoord(lat: tile.lat, lon: tile.lon)
        }
        close()
    }

    func cancel() {
        build?.selected = base
        build?.activeTile = baseActive
        close()
    }

    private func close() {
        isShown = false
        plan = nil
        drawing = []
        tiles = []
    }

    // MARK: - Loading a plan

    func openFile() {
        let panel = NSOpenPanel()
        panel.title = FlightPlanCopy.openButton
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = FlightPlanCopy.fileTypes.compactMap {
            UTType(filenameExtension: $0)
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            load(try FlightPlanReader.readPlanFile(url))
        } catch {
            errorMessage = (error as? FlightPlanError)?.message ?? error.localizedDescription
        }
    }

    func fetchSimBrief() {
        let user = simBriefUser
        isFetching = true
        errorMessage = nil
        Task { [weak self] in
            do {
                let plan = try await FlightPlanReader.fetchSimBrief(user: user)
                self?.isFetching = false
                self?.load(plan)
            } catch {
                self?.isFetching = false
                self?.errorMessage = (error as? FlightPlanError)?.message ?? error.localizedDescription
            }
        }
    }

    func load(_ plan: FlightPlan) {
        guard isShown else { return }
        self.plan = plan
        errorMessage = nil
        drawing = RouteTiles.drawing(points: plan.points)
        refresh()
        loads += 1
    }

    // MARK: - The live selection

    var summary: String? { plan.map { RouteTiles.summaryText($0, unit: unit) } }

    private func refresh() {
        guard isShown, let plan, let build else { return }
        tiles = RouteTiles.tiles(points: plan.points, radiusKm: RouteTiles.radiusKm(radius, unit: unit))
        build.selected = base.union(tiles.map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) })
    }
}
