import Foundation

/// The Fly map's layers as data (spec `flight-manager-and-world-20261110`
/// §4.3, §14; #2001; lane U2): the aircraft's track and the route's
/// corridor tiles by legend. The Qt window's `O4_Fly_Layers.py` holds the
/// same rules (`FlyPaneTests` against `fly_pane_cases.json`).
public struct AircraftTrack: Sendable, Equatable {
    /// One hour at one position a second.
    public static let maxPoints = 3600
    /// A position closer than this to the last one is not added (parked).
    public static let minStepM = 20.0
    /// A step longer than this starts a new piece (a jump, a flight load).
    public static let breakKm = 30.0

    private var pieces: [[GeoPoint]] = []
    /// The last position and its track, degrees.
    public private(set) var last: (lat: Double, lon: Double, track: Double)?

    public init() {}

    public static func == (a: Self, b: Self) -> Bool { a.pieces == b.pieces }

    static func stepM(_ a: GeoPoint, _ b: GeoPoint) -> Double {
        let mid = (a.lat + b.lat) / 2 * .pi / 180
        var dlon = (b.lon - a.lon + 540).truncatingRemainder(dividingBy: 360)
        if dlon < 0 { dlon += 360 }
        dlon -= 180
        return hypot(dlon * 111_320 * cos(mid), (b.lat - a.lat) * 111_320)
    }

    /// One position; true when the drawing changed.
    @discardableResult
    public mutating func add(lat: Double, lon: Double, track: Double = 0) -> Bool {
        let point = GeoPoint(lon: lon, lat: lat)
        last = (lat, lon, track)
        if let prev = pieces.last?.last {
            let step = Self.stepM(prev, point)
            if step < Self.minStepM { return false }
            if step > Self.breakKm * 1000 || abs(point.lon - prev.lon) > 180 {
                pieces.append([])
            }
        } else {
            pieces.append([])
        }
        pieces[pieces.count - 1].append(point)
        trim()
        return true
    }

    private mutating func trim() {
        var extra = pieces.reduce(0) { $0 + $1.count } - Self.maxPoints
        while extra > 0, !pieces.isEmpty {
            let cut = min(extra, pieces[0].count)
            pieces[0].removeFirst(cut)
            extra -= cut
            if pieces[0].isEmpty { pieces.removeFirst() }
        }
    }

    /// What the map draws.
    public var parts: [[GeoPoint]] { pieces.filter { $0.count > 1 } }

    public mutating func clear() {
        pieces = []
        last = nil
    }
}

/// One corridor tile and its legend key (`FlyText.legend`).
public struct FlyCell: Hashable, Sendable, Comparable {
    public let lat: Int
    public let lon: Int
    public let key: String

    public static func < (a: Self, b: Self) -> Bool {
        (a.lat, a.lon, a.key) < (b.lat, b.lon, b.key)
    }
}

public enum FlyLayers {
    /// The aircraft on the map (owner 2026-11-12T15:33Z: "a small airplane
    /// like you would typically see on a garmin g1000 mfd"): a top-down
    /// airplane, nose up, in screen points about the aircraft's position
    /// (x right, y forward), 21 x 22 pt at every zoom, filled white with a
    /// dark outline. Python: `O4_Fly_Layers.AIRCRAFT_SYMBOL` (the same
    /// points, held equal by `fly_pane_cases.json`).
    public static let aircraftSymbol: [(x: Double, y: Double)] = [
        (0.0, 11.0), (1.3, 9.5), (1.5, 4.0), (10.5, -1.5), (10.5, -3.5),
        (1.5, -1.5), (1.1, -7.0), (4.5, -9.5), (4.5, -11.0), (0.0, -10.0),
        (-4.5, -11.0), (-4.5, -9.5), (-1.1, -7.0), (-1.5, -1.5),
        (-10.5, -3.5), (-10.5, -1.5), (-1.5, 4.0), (-1.3, 9.5),
    ]

    /// `aircraftSymbol` at screen point (`x`, `y`) (y down), its nose along
    /// `trackDegrees` (clockwise from north). Python:
    /// `O4_Fly_Layers.aircraft_symbol`.
    public static func aircraftSymbol(x: Double, y: Double,
                                      trackDegrees: Double) -> [(x: Double, y: Double)] {
        let r = trackDegrees * .pi / 180, c = cos(r), s = sin(r)
        return aircraftSymbol.map { p in
            (x: x + p.x * c + p.y * s, y: y + p.x * s - p.y * c)
        }
    }

    /// The corridor's tiles with their legend key, sorted: the tiles of
    /// `FlightStatus.jobs` by their job, and before the engine reports
    /// any, the tiles the route crosses plus those within `corridorKm`
    /// as X-Plane's own scenery (`O4_Fly_Layers.corridor_cells`).
    /// The jobs the Fly map draws: the flight's once it reports any, with
    /// build-ahead's tiles around the aircraft that are not the flight's
    /// (`WorldStatus.jobs`, the same rows: track mode runs beside a
    /// flight, #2019); with no flight and no plan, build-ahead's tiles
    /// alone so free flight shows its drapes; else none (the plan's
    /// corridor). Python: `O4_Fly_Layers.map_jobs`.
    public static func mapJobs(flight: [O4FlightStatus.Job], planned: Bool,
                               ahead: [O4FlightStatus.Job]) -> [O4FlightStatus.Job] {
        if !flight.isEmpty {
            let mine = Set(flight.map { AirportTile(lat: $0.lat, lon: $0.lon) })
            return flight + ahead.filter { !mine.contains(AirportTile(lat: $0.lat, lon: $0.lon)) }
        }
        return planned ? [] : ahead
    }

    public static func corridorCells(plan: O4FlightPlanRead?, corridorKm: Double,
                                     jobs: [O4FlightStatus.Job] = []) -> [FlyCell] {
        var cells: [AirportTile: String] = [:]
        if !jobs.isEmpty {
            for job in jobs {
                cells[AirportTile(lat: job.lat, lon: job.lon)] =
                    FlyText.legendKey(kind: job.kind, state: job.state)
            }
        } else if let plan, !plan.waypoints.isEmpty {
            let points = plan.waypoints.map { (lat: $0.lat, lon: $0.lon) }
            for tile in RouteTiles.tiles(points: points, radiusKm: corridorKm) {
                cells[tile] = "own"
            }
        }
        return cells.map { FlyCell(lat: $0.key.lat, lon: $0.key.lon, key: $0.value) }.sorted()
    }
}
