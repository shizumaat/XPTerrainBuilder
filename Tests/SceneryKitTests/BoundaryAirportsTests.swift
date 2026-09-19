import Testing
import Foundation
@testable import SceneryKit

/// Boundary airports on a tile edge (protocol 1.8, spec
/// insets-follow-patch-set-spec.md §C.2–§C.4, owner RULINGS 2026-09-18h/18i).
///
/// The wire names here are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` class and field names; they never
/// appear in Python source, so these tests are the drift alarm.
struct BoundaryAirportsTests {

    private func parse(_ object: [String: Any]) -> O4Event? {
        O4Event.parse(object: object)
    }

    private var fullEvent: [String: Any] {
        [
            "event": "BoundaryAirportsReady",
            "request_id": 7,
            "airports": [
                [
                    "icao": "LPMT", "name": "Montijo",
                    "home": [38, -10],
                    "neighbours": [[38, -9]],
                    "crossing_m": 1_243.7,
                ],
                [
                    "icao": "SPLP", "name": "Las Palmas",
                    "home": [-13, -76],
                    "neighbours": [[-13, -77], [-14, -77]],
                    "crossing_m": 88.0,
                ],
            ],
            "add_tiles": [[38, -9], [-13, -77], [-14, -77]],
            "remembered": "",
            "error": "",
            "default_choice": "neighbour",
        ]
    }

    // MARK: Decode

    @Test func decodesTheEventWithEveryField() throws {
        guard case .boundaryAirportsReady(let ready)? = parse(fullEvent) else {
            Issue.record("not decoded as boundaryAirportsReady")
            return
        }
        #expect(ready.requestID == 7)
        #expect(ready.remembered.isEmpty)
        #expect(ready.error.isEmpty)
        #expect(ready.defaultChoice == "neighbour")
        #expect(ready.airports.count == 2)
        #expect(ready.airports[0].icao == "LPMT")
        #expect(ready.airports[0].name == "Montijo")
        #expect(ready.airports[0].home == O4TileRef(lat: 38, lon: -10))
        #expect(ready.airports[0].neighbours == [O4TileRef(lat: 38, lon: -9)])
        #expect(ready.airports[0].crossingMeters == 1_243.7)
        #expect(ready.airports[1].neighbours.count == 2)
        #expect(ready.addTiles == [O4TileRef(lat: 38, lon: -9),
                                   O4TileRef(lat: -13, lon: -77),
                                   O4TileRef(lat: -14, lon: -77)])
    }

    /// The dialog's preselected action is ENGINE-owned (RULINGS 18i (2)),
    /// so it must survive the decode — and an engine that predates the
    /// field still preselects the owner's default rather than nothing.
    @Test func defaultChoiceIsCarriedAndDefaultsToNeighbour() throws {
        var object = fullEvent
        object["default_choice"] = "skip"
        guard case .boundaryAirportsReady(let skipped)? = parse(object) else {
            Issue.record("not decoded"); return
        }
        #expect(skipped.defaultChoice == "skip")

        object.removeValue(forKey: "default_choice")
        guard case .boundaryAirportsReady(let absent)? = parse(object) else {
            Issue.record("not decoded"); return
        }
        #expect(absent.defaultChoice == "neighbour")
    }

    @Test func decodesAnEmptyAndAnErroredPreflight() throws {
        guard case .boundaryAirportsReady(let empty)? = parse([
            "event": "BoundaryAirportsReady", "request_id": 2,
        ]) else { Issue.record("not decoded"); return }
        #expect(empty.airports.isEmpty)
        #expect(empty.addTiles.isEmpty)
        #expect(empty.remembered.isEmpty)

        guard case .boundaryAirportsReady(let failed)? = parse([
            "event": "BoundaryAirportsReady", "request_id": 3,
            "error": "no apt.dat for +38-010",
        ]) else { Issue.record("not decoded"); return }
        #expect(failed.error == "no apt.dat for +38-010")
    }

    @Test func tileRefKeysAreTheMapsOwnTileNames() {
        #expect(O4TileRef(lat: 38, lon: -9).key == "+38-009")
        #expect(O4TileRef(lat: -14, lon: -77).key == "-14-077")
    }

    // MARK: The flow's branches, against a fake client

    /// Stands in for `OrthoEngineClient`: records what was asked and hands
    /// back whatever request id (or none) the test wants.
    private final class FakeSender: O4BoundaryPreflightSender, @unchecked Sendable {
        var asked: [[O4TileRef]] = []
        let answer: Int?

        init(answer: Int?) { self.answer = answer }

        func requestBoundaryAirports(tiles: [O4TileRef],
                                     completion: @escaping @Sendable (Int?) -> Void) {
            asked.append(tiles)
            completion(answer)
        }
    }

    /// Drive the flow exactly as BuildModel does: send, feed the command's
    /// reply, then feed events.
    private func run(_ sender: FakeSender, tiles: [O4TileRef],
                     events: [O4BoundaryAirportsReady]) -> [O4BoundaryFlow.Step] {
        var flow = O4BoundaryFlow()
        var steps: [O4BoundaryFlow.Step] = []
        var started: Int??
        sender.requestBoundaryAirports(tiles: tiles) { started = $0 }
        if let started { steps.append(flow.started(requestID: started)) }
        for event in events { steps.append(flow.ready(event)) }
        return steps
    }

    private func ready(requestID: Int = 7, remembered: String = "",
                       error: String = "", airports: Int = 1,
                       addTiles: [O4TileRef] = [O4TileRef(lat: 38, lon: -9)]
    ) -> O4BoundaryAirportsReady {
        O4BoundaryAirportsReady(
            requestID: requestID,
            airports: (0..<airports).map { i in
                O4BoundaryAirport(icao: "LPM\(i)", name: "Montijo",
                                  home: O4TileRef(lat: 38, lon: -10),
                                  neighbours: [O4TileRef(lat: 38, lon: -9)],
                                  crossingMeters: 1_243.7)
            },
            addTiles: addTiles, remembered: remembered, error: error,
            defaultChoice: "neighbour")
    }

    /// Branch 1 — nothing to ask about (or the preflight failed): enqueue
    /// with NO policy and no dialog.
    @Test func emptyOrErroredPreflightEnqueuesWithNoPolicy() {
        let sender = FakeSender(answer: 7)
        let steps = run(sender, tiles: [O4TileRef(lat: 38, lon: -10)],
                        events: [ready(airports: 0, addTiles: [])])
        #expect(steps == [.waiting, .outcome(.enqueue(policy: nil, addTiles: []))])
        #expect(sender.asked == [[O4TileRef(lat: 38, lon: -10)]])

        let failed = run(FakeSender(answer: 7), tiles: [],
                         events: [ready(error: "boom")])
        #expect(failed.last == .outcome(.enqueue(policy: nil, addTiles: [])))
    }

    /// Branch 2 — a remembered answer is applied WITHOUT asking, and only
    /// "neighbour" grows the tile list.
    @Test func rememberedAnswersAreAppliedWithoutAsking() {
        let neighbour = run(FakeSender(answer: 7), tiles: [],
                            events: [ready(remembered: "neighbour")])
        #expect(neighbour.last == .outcome(.enqueue(
            policy: "neighbour", addTiles: [O4TileRef(lat: 38, lon: -9)])))

        let skip = run(FakeSender(answer: 7), tiles: [],
                       events: [ready(remembered: "skip")])
        #expect(skip.last == .outcome(.enqueue(policy: "skip", addTiles: [])))
    }

    /// Branch 3 — ONE ask for the whole press, carrying the engine's
    /// preselected action.
    @Test func airportsWithNoRememberedAnswerAsk() {
        let steps = run(FakeSender(answer: 7), tiles: [], events: [ready(airports: 2)])
        guard case .outcome(.ask(let airports, let addTiles, let defaultChoice))? = steps.last else {
            Issue.record("expected an ask, got \(String(describing: steps.last))")
            return
        }
        #expect(airports.count == 2)
        #expect(addTiles == [O4TileRef(lat: 38, lon: -9)])
        #expect(defaultChoice == "neighbour")
    }

    /// An engine older than 1.8 does not know the command: reply ok=false
    /// ⇒ nil ⇒ today's behaviour exactly, no dialog, no policy keyword.
    @Test func anOlderEngineDegradesSilently() {
        var flow = O4BoundaryFlow()
        let sender = FakeSender(answer: nil)
        var started: Int??
        sender.requestBoundaryAirports(tiles: []) { started = $0 }
        #expect(started != nil)              // the completion DID run
        #expect(started! == nil)             // …with no request id
        #expect(flow.started(requestID: nil)
                == .outcome(.enqueue(policy: nil, addTiles: [])))
        #expect(flow.isSettled)
        // A stray event afterwards can never enqueue a second build.
        #expect(flow.ready(ready()) == .ignored)
    }

    // MARK: Correlation

    @Test func anotherPressesEventIsIgnored() {
        var flow = O4BoundaryFlow()
        #expect(flow.started(requestID: 7) == .waiting)
        #expect(flow.ready(ready(requestID: 6)) == .ignored)
        #expect(!flow.isSettled)
        #expect(flow.ready(ready(requestID: 7, remembered: "skip"))
                == .outcome(.enqueue(policy: "skip", addTiles: [])))
    }

    /// The event can beat the command's own reply onto the main actor: the
    /// flow holds it rather than guessing, and settles once the id lands.
    @Test func anEventBeforeTheReplyIsHeldNotGuessed() {
        var flow = O4BoundaryFlow()
        #expect(flow.ready(ready(requestID: 7, remembered: "neighbour")) == .waiting)
        #expect(flow.started(requestID: 7)
                == .outcome(.enqueue(policy: "neighbour",
                                     addTiles: [O4TileRef(lat: 38, lon: -9)])))
    }

    @Test func aTimeoutNeverStopsTheBuild() {
        var flow = O4BoundaryFlow()
        #expect(flow.started(requestID: 7) == .waiting)
        #expect(flow.giveUp() == .outcome(.enqueue(policy: nil, addTiles: [])))
        // A late answer after the build already started is ignored.
        #expect(flow.ready(ready(remembered: "neighbour")) == .ignored)
    }

    // MARK: The setting the "remember" checkbox writes

    /// `auto_patch_boundary` is FROZEN for the front ends (spec §F): the
    /// key, its three values and their labels. The settings row renders
    /// straight off this, so a drift here is a blank picker.
    @Test func theSettingIsInTheBundledSchemaWithItsThreeValues() throws {
        let schema = try #require(OrthoConfigSchema.bundledSnapshot())
        let variable = try #require(schema.vars["auto_patch_boundary"])
        #expect(variable.type == "str")
        #expect(variable.default == .string("Ask"))
        #expect(variable.values == ["Ask", "Build adjacent", "Skip patch"])
        #expect(variable.label(forValue: "Ask") == "Ask me each time")
        #expect(variable.label(forValue: "Build adjacent") == "Build the adjacent tiles too")
        #expect(variable.label(forValue: "Skip patch") == "Skip those airports' patches")
        // NOTE (reported, engine-side): the snapshot puts the key in NO
        // group at all. The mac app resolves its rows by NAME out of
        // `vars` (SettingsView), so its row renders either way; a front
        // end that walks `groups` would not see it.
        #expect(schema.groups.values.allSatisfy { !$0.contains("auto_patch_boundary") })
    }

    /// An ask does NOT settle the press (the user has not answered yet),
    /// and closing it does.
    @Test func anAskStaysOpenUntilItIsClosed() {
        var flow = O4BoundaryFlow()
        _ = flow.started(requestID: 7)
        guard case .outcome(.ask) = flow.ready(ready()) else {
            Issue.record("expected an ask"); return
        }
        #expect(!flow.isSettled)
        flow.close()
        #expect(flow.isSettled)
        #expect(flow.ready(ready()) == .ignored)
    }
}
