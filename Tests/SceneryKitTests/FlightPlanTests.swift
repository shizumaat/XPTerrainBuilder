import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_flight_plan.py` (#829): both read
/// `Ortho4XP/tests/fixtures/flight_plan_cases.json` and the plan files in
/// `Ortho4XP/tests/fixtures/flight_plan/`, so the Mac and Qt "Select from
/// flight plan" parse the same waypoints, select the same tiles and say the
/// same words. No network: SimBrief is a committed fetcher answer.
@Suite struct FlightPlanTests {
    struct Row: Decodable {
        let ident: String, lat: Double, lon: Double
        init(from decoder: Decoder) throws {
            var c = try decoder.unkeyedContainer()
            ident = try c.decode(String.self)
            lat = try c.decode(Double.self)
            lon = try c.decode(Double.self)
        }
    }

    struct Cases: Decodable {
        struct Copy: Decodable {
            let menu_title, open_button, simbrief_placeholder, simbrief_button: String
            let simbrief_note, radius_label, of_route_label: String
        }
        struct Plan: Decodable {
            let file, origin, destination, summary_km, summary_nm: String
            let waypoints: [Row]
        }
        struct Failure: Decodable { let name, text, message: String }
        struct URLCase: Decodable { let user, url: String }
        struct Unit: Decodable { let value: Double; let unit: String; let km: Double }
        struct Count: Decodable { let count: Int; let text: String }
        struct Route: Decodable {
            let name: String
            let points: [[Double]]
            let radius_km: Double
            let tiles: [[Int]]
        }
        struct Drawing: Decodable { let points: [[Double]]; let parts: [[[Double]]] }
        let copy: Copy
        let radius_max: [String: Int]
        let radius_default: [String: Int]
        let plans: [Plan]
        let errors: [Failure]
        let simbrief_urls: [URLCase]
        let units: [Unit]
        let tiles_text: [Count]
        let routes: [Route]
        let drawing: [Drawing]
    }

    static let fixtures = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Ortho4XP/tests/fixtures")

    static let cases: Cases = {
        let url = fixtures.appendingPathComponent("flight_plan_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    static func points(_ rows: [[Double]]) -> [(lat: Double, lon: Double)] {
        rows.map { ($0[0], $0[1]) }
    }

    @Test func eachFormatParsesItsFixtureLikeThePythonTwin() throws {
        for c in Self.cases.plans {
            let url = Self.fixtures.appendingPathComponent("flight_plan").appendingPathComponent(c.file)
            let plan = try FlightPlanReader.readPlanFile(url)
            #expect(plan.waypoints.map(\.ident) == c.waypoints.map(\.ident), "\(c.file)")
            #expect(plan.waypoints.map(\.lat) == c.waypoints.map(\.lat), "\(c.file)")
            #expect(plan.waypoints.map(\.lon) == c.waypoints.map(\.lon), "\(c.file)")
            #expect(plan.origin == c.origin && plan.destination == c.destination, "\(c.file)")
            #expect(RouteTiles.summaryText(plan, unit: "km") == c.summary_km, "\(c.file)")
            #expect(RouteTiles.summaryText(plan, unit: "nm") == c.summary_nm, "\(c.file)")
            // Without a name the content picks the reader.
            let sniffed = try FlightPlanReader.parsePlanText(String(decoding: Data(contentsOf: url), as: UTF8.self))
            #expect(sniffed.waypoints.map(\.ident) == c.waypoints.map(\.ident), "\(c.file) sniffed")
        }
    }

    @Test func anUnreadablePlanSaysWhyLikeThePythonTwin() {
        for c in Self.cases.errors {
            #expect(throws: FlightPlanError(c.message)) {
                _ = try FlightPlanReader.parsePlanText(c.text, name: c.name)
            }
        }
    }

    @Test func simBriefURLLikeThePythonTwin() throws {
        for c in Self.cases.simbrief_urls {
            #expect(try FlightPlanReader.simBriefURL(c.user) == c.url, "\(c.user)")
        }
        #expect(throws: FlightPlanError.self) { _ = try FlightPlanReader.simBriefURL("  ") }
    }

    @Test func unitsWordsAndCopyLikeThePythonTwin() {
        for c in Self.cases.units {
            #expect(abs(RouteTiles.radiusKm(c.value, unit: c.unit) - c.km) < 1e-9)
        }
        for c in Self.cases.tiles_text {
            #expect(RouteTiles.tilesText(c.count) == c.text)
        }
        let copy = Self.cases.copy
        #expect(FlightPlanCopy.menuTitle == copy.menu_title)
        #expect(FlightPlanCopy.openButton == copy.open_button)
        #expect(FlightPlanCopy.simBriefPlaceholder == copy.simbrief_placeholder)
        #expect(FlightPlanCopy.simBriefButton == copy.simbrief_button)
        #expect(FlightPlanCopy.simBriefNote == copy.simbrief_note)
        #expect(FlightPlanCopy.radiusLabel == copy.radius_label)
        #expect(FlightPlanCopy.ofRouteLabel == copy.of_route_label)
        #expect(FlightPlanCopy.radiusMax == Self.cases.radius_max)
        #expect(FlightPlanCopy.radiusDefault == Self.cases.radius_default)
    }

    @Test func routeTilesOnKnownRoutesLikeThePythonTwin() {
        for c in Self.cases.routes {
            let tiles = RouteTiles.tiles(points: Self.points(c.points), radiusKm: c.radius_km)
            #expect(tiles.map { [$0.lat, $0.lon] } == c.tiles, "\(c.name) r\(c.radius_km)")
        }
    }

    @Test func routeDrawingLikeThePythonTwin() {
        for c in Self.cases.drawing {
            let parts = RouteTiles.drawing(points: Self.points(c.points))
            #expect(parts.count == c.parts.count)
            for (got, want) in zip(parts, c.parts) {
                #expect(got.count == want.count)
                for (p, q) in zip(got, want) {
                    #expect(abs(p.lat - q[0]) < 1e-9 && abs(p.lon - q[1]) < 1e-9)
                }
            }
        }
    }

    @Test func aLargerRadiusNeverDropsATileAndKeepsTheEndpoints() {
        for c in Self.cases.routes {
            let pts = Self.points(c.points)
            var previous = Set<AirportTile>()
            for radius in [0.0, 25, 100, 300] {
                let tiles = Set(RouteTiles.tiles(points: pts, radiusKm: radius))
                #expect(previous.isSubset(of: tiles), "\(c.name) r\(radius)")
                previous = tiles
                #expect(tiles.contains(RouteTiles.tileOf(pts[0].lat, pts[0].lon)))
                #expect(tiles.contains(RouteTiles.tileOf(pts[pts.count - 1].lat, pts[pts.count - 1].lon)))
            }
        }
    }
}
