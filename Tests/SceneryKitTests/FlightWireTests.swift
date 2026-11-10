import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_flight_plan_profile.py::test_the_wire_fixture`:
/// the Python side writes `Ortho4XP/tests/fixtures/flight_plan_wire.json`
/// from `flight_commands.py`, and this side decodes every field of it.
@Suite struct FlightWireTests {
    static let wire: O4JSON = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/flight_plan_wire.json")
        // swiftlint:disable:next force_try
        let object = try! JSONSerialization.jsonObject(with: Data(contentsOf: url))
        return O4JSON.from(object)
    }()

    @Test func plansListDecodes() {
        let rows = O4FlightPlanFile.list(from: Self.wire["flight_plans_list"])
        #expect(rows == [
            O4FlightPlanFile(path: "/X-Plane 12/Output/FMS plans/CCCCDDDD.fms",
                             name: "CCCCDDDD", origin: "CCCC", destination: "DDDD",
                             modifiedAt: 1_700_000_500),
            O4FlightPlanFile(path: "/X-Plane 12/Output/FMS plans/AAAABBBB.fms",
                             name: "AAAABBBB", origin: "AAAA", destination: "BBBB",
                             modifiedAt: 1_700_000_000),
        ])
        #expect(O4FlightPlanFile.list(from: nil).isEmpty)
    }

    @Test func planReadDecodes() throws {
        let plan = try #require(O4FlightPlanRead.parse(Self.wire["flight_plan_read"]))
        #expect(plan.origin == "ENGM" && plan.destination == "ENBR")
        #expect(plan.waypoints.map(\.ident) == ["ENGM", "TOC", "TOD", "ENBR"])
        #expect(plan.waypoints.map(\.secondsAfterTakeoff) == [0, 900, 2400, 3300])
        #expect(plan.waypoints[1].altitudeFeet == 24000)
        #expect(plan.alternate?.ident == "ENZV")
        #expect(plan.alternate?.secondsAfterTakeoff == nil)
        #expect(plan.eteSeconds == 3300)
        #expect(abs((plan.cruiseMS ?? 0) - 280.0 * 1852.0 / 3600.0) < 1e-9)
        #expect(plan.cruiseAltitudeFeet == 24000)
        #expect(plan.routeKm > 300)
    }

    @Test func aPlanWithoutTheNewFieldsDecodesNil() throws {
        let plan = try #require(O4FlightPlanRead.parse(Self.wire["flight_plan_read_fms"]))
        #expect(plan.alternate == nil && plan.eteSeconds == nil && plan.cruiseMS == nil)
        #expect(plan.waypoints.allSatisfy { $0.secondsAfterTakeoff == nil })
    }
}
