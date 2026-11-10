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
    /// The corridor's tiles with their legend key, sorted: the tiles of
    /// `FlightStatus.jobs` by their job, and before the engine reports
    /// any, the tiles the route crosses plus those within `corridorKm`
    /// as X-Plane's own scenery (`O4_Fly_Layers.corridor_cells`).
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
