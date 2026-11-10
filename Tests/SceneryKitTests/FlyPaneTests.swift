import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_fly_pane.py`: the Python rules
/// (`O4_Fly_Text`, `O4_Fly_Layers`) write
/// `Ortho4XP/tests/fixtures/fly_pane_cases.json`; `FlyText` / `FlyLayers`
/// give the same answers, and the events in it decode.
@Suite struct FlyPaneTests {
    static let raw: [String: Any] = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/fly_pane_cases.json")
        // swiftlint:disable:next force_try force_cast
        return try! JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
    }()
    static let doc = O4JSON.from(raw)
    static func cases(_ name: String) -> [[O4JSON]] {
        (doc["text"]?[name]?.arrayValue ?? []).compactMap(\.arrayValue)
    }
    static func plan(_ json: O4JSON) -> O4FlightPlanRead? { O4FlightPlanRead.parse(json) }
    static let status = O4FlightStatus.parse(doc["events"]?["FlightStatus"])!

    @Test func eventsDecode() throws {
        let events = try #require(Self.raw["events"] as? [String: Any])
        let object = try #require(events["AircraftPosition"] as? [String: Any])
        let position = O4AircraftPosition.parse(object)
        #expect(position == O4AircraftPosition(lat: 53.3, lon: -60.4, altitudeM: 640.5, trackDegrees: 91.5,
                                               speedMS: 72, onGround: false, paused: true))
        if case .aircraftPosition(let p)? = O4Event.parse(object: object) {
            #expect(p == position)
        } else {
            Issue.record("AircraftPosition is not an O4Event")
        }
        #expect(Self.status.items.count == 9 && Self.status.jobs.count == 4)
        #expect(Self.status.countdownSeconds == 712 && !Self.status.ready)
        #expect(Self.status.jobs[0] == O4FlightStatus.Job(lat: 53, lon: -61, role: "departure", kind: "full",
                                                          state: "building", remainingSeconds: 412,
                                                          marginSeconds: nil))
    }

    @Test func countdownAndItems() {
        for c in Self.cases("countdown") {
            #expect(FlyText.countdown(c[0].doubleValue) == c[1].stringValue)
        }
        for c in Self.cases("items") {
            let r = c[0].arrayValue!
            let item = O4FlightStatus.Item(key: r[0].stringValue!, state: r[1].stringValue!,
                                           etaSeconds: r[2].doubleValue, detail: r[3].stringValue ?? "")
            #expect(FlyText.itemText(item) == c[1].stringValue)
        }
    }

    @Test func planWords() throws {
        for c in Self.cases("plan_rows") {
            let row = O4FlightPlanFile(path: "", name: c[0]["name"]?.stringValue ?? "",
                                       origin: c[0]["origin"]?.stringValue ?? "",
                                       destination: c[0]["destination"]?.stringValue ?? "", modifiedAt: 0)
            #expect(FlyText.planRowLabel(row) == c[1].stringValue)
        }
        for c in Self.cases("quick_plan") {
            let d = c[0].arrayValue!, a = c[1].arrayValue!
            let made = O4FlightPlanRead.quick(from: (d[0].stringValue!, d[1].doubleValue!, d[2].doubleValue!),
                                              to: (a[0].stringValue!, a[1].doubleValue!, a[2].doubleValue!))
            let want = try #require(Self.plan(c[2]))
            #expect(made.origin == want.origin && made.destination == want.destination)
            #expect(made.waypoints == want.waypoints && made.source == want.source)
            #expect(abs(made.routeKm - want.routeKm) < 1e-6)
            // The wire form reads back as the same plan.
            #expect(Self.plan(O4JSON.from(made.wire)) == made)
        }
        for c in Self.cases("cruise_kt") {
            #expect(FlyText.cruiseKt(Self.plan(c[0])) == c[1].intValue)
        }
        for c in Self.cases("card") {
            let lines = (c[2].arrayValue ?? []).compactMap(\.stringValue)
            #expect(FlyText.cardLines(Self.plan(c[0])!, cruise: c[1].doubleValue!) == lines)
        }
        for c in Self.cases("unknown_airport") {
            #expect(FlyText.unknownAirport(c[0].stringValue!) == c[1].stringValue)
        }
        for c in Self.cases("refusal") {
            #expect(FlyText.refusal(c[0].stringValue!) == c[1].stringValue)
        }
    }

    @Test func statusLines() {
        for c in Self.cases("world_line") {
            #expect(FlyText.worldLine(c[0] == .null ? nil : c[0]) == c[1].stringValue)
        }
        for c in Self.cases("status_line") {
            #expect(FlyText.statusLine(O4FlightStatus.parse(c[0])) == c[1].stringValue)
        }
        for c in Self.cases("legend_key") {
            #expect(FlyText.legendKey(kind: c[0].stringValue!, state: c[1].stringValue!) == c[2].stringValue)
        }
    }

    @Test func trackAndCorridor() throws {
        let track = try #require(Self.doc["track"])
        var made = AircraftTrack()
        var changed: [Bool] = []
        for step in track["steps"]?.arrayValue ?? [] {
            let s = step.arrayValue!
            changed.append(made.add(lat: s[0].doubleValue!, lon: s[1].doubleValue!, track: 90))
        }
        #expect(changed == (track["changed"]?.arrayValue ?? []).compactMap(\.boolValue))
        let parts = (track["parts"]?.arrayValue ?? []).map { part in
            part.arrayValue!.map {
                GeoPoint(lon: $0.arrayValue![1].doubleValue!, lat: $0.arrayValue![0].doubleValue!)
            }
        }
        #expect(made.parts == parts)
        for c in Self.doc["corridor"]?.arrayValue?.compactMap(\.arrayValue) ?? [] {
            let jobs = O4FlightStatus.parse(.object(["flight": .string("x"), "jobs": c[2]]))?.jobs ?? []
            let cells = FlyLayers.corridorCells(plan: Self.plan(c[0]), corridorKm: c[1].doubleValue!, jobs: jobs)
            let want = (c[3].arrayValue ?? []).map {
                FlyCell(lat: $0.arrayValue![0].intValue!, lon: $0.arrayValue![1].intValue!,
                        key: $0.arrayValue![2].stringValue!)
            }
            #expect(cells == want)
        }
    }
}
