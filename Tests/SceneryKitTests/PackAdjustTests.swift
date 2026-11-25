import Testing
import Foundation
@testable import SceneryKit

/// An airport pack's adjustments as one question (capability
/// `pack_adjust`, issue #1916). The wire names are STRING LITERALS matched
/// against `Ortho4XP/src/o4_engine/events.py`; these tests are the drift
/// alarm.
struct PackAdjustTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackAdjust",
            "pack": "Some Pack", "pack_root": "/X/Custom Scenery/Some Pack",
            "lat": 29, "lon": -96, "state": "found", "error": "", "files": [],
            "items": [
                ["key": "trees", "count": 3, "uses": 9, "automatic": false],
                ["key": "drapes", "count": 12, "uses": 40, "automatic": false],
                ["key": "flatten", "count": 1, "uses": 0, "automatic": true],
            ],
        ]
    }

    @Test func decodesEveryRow() throws {
        guard case .packAdjust(let a)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.packRoot == "/X/Custom Scenery/Some Pack" && a.lat == 29 && a.lon == -96)
        #expect(a.choices.map(\.key) == ["trees", "drapes"])
        #expect(a.choices.allSatisfy { $0.checked }, "an absent `checked` is ticked")
        #expect(a.automatic.map(\.key) == ["flatten"])
        #expect(a.asks)
        #expect(a.titleText == "Adjust “Some Pack”?")
        #expect(a.choices[1].detail == "12 photo images (40 polygons) laid over "
                + "the airport cover the tile’s imagery.")
    }

    @Test func groundTexturesOpenUnticked() {
        var event = fullEvent
        event["items"] = [
            ["key": "drapes", "count": 12, "uses": 40, "automatic": false, "checked": true],
            ["key": "ground", "count": 17, "uses": 55, "automatic": false, "checked": false],
        ]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.choices.map(\.key) == ["drapes", "ground"])
        #expect(a.choices.filter(\.checked).map(\.key) == ["drapes"])
        #expect(a.choices[1].title == "Hide large ground textures included with the package")
        #expect(a.choices[1].detail == "17 painted ground or grass images (55 polygons) laid "
                + "mostly over unpaved ground at the airport cover the tile’s imagery.")
    }

    @Test func genericGroundNamesItsHectares() {
        var event = fullEvent
        event["items"] = [
            ["key": "generic", "count": 7, "uses": 61, "automatic": false,
             "checked": true, "hectares": 4310],
        ]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.choices.map(\.key) == ["generic"])
        #expect(a.choices[0].checked)
        #expect(a.choices[0].hectares == 4310)
        #expect(a.choices[0].title == "Hide generic X-Plane ground textures the package drapes")
        #expect(a.choices[0].detail == "7 stock X-Plane grass, sand or scrub textures "
                + "(61 polygons, about 4,310 ha) cover the tile’s imagery.")
    }

    @Test func flattenAloneAsksNothing() {
        var event = fullEvent
        event["items"] = [["key": "flatten", "count": 1, "automatic": true]]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(!a.asks)
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packAdjust(let a)? = O4Event.parse(object: ["event": "PackAdjust"]) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.items.isEmpty && !a.asks && a.state == "found")
        #expect(a.steps.isEmpty && a.stepsOn.isEmpty && !a.rebuild && !a.editing)
    }

    /// The pack row's Adjust… (owner 2026-11-15T13:12Z, capability
    /// `pack_adjust_edit`): the rows as the pack is, the Optimise steps, and
    /// the terrain row that rebuilds the tile.
    @Test func adjustDecodesTheRowsStepsAndRebuild() {
        var event = fullEvent
        event["state"] = "adjust"
        event["items"] = [
            ["key": "drapes", "count": 12, "uses": 40, "automatic": false,
             "checked": true, "applied": true, "rebuild": false],
            ["key": "terrain", "count": 1, "uses": 1, "automatic": false,
             "checked": false, "applied": false, "rebuild": true],
        ]
        event["steps"] = [
            ["key": "dedupe", "count": 4, "tris": 1_000_000, "mb": 0, "checked": true],
            ["key": "textures", "count": 3, "tris": 0, "mb": 12, "checked": false],
        ]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.editing && a.asks)
        #expect(a.titleText == "Adjust “Some Pack”")
        #expect(a.choices[0].applied && !a.choices[0].rebuild)
        #expect(a.choices[1].rebuild && !a.choices[1].baseline(editing: true))
        #expect(a.choices[1].detail.hasSuffix(O4PackAdjustCopy.rebuildNote))
        #expect(a.steps.map(\.key) == ["dedupe", "textures"])
        #expect(a.stepsOn == ["dedupe"])
        var outcome = fullEvent
        outcome["state"] = "applied"
        outcome["rebuild"] = true
        guard case .packAdjust(let o)? = O4Event.parse(object: outcome) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(o.rebuild && !o.asks)
    }

    /// The tiles a terrain answer still owes a rebuild, after a run
    /// (engine `tile_rebuild_pending`).
    @Test func pendingNamesTheTilesToRebuild() {
        let event: [String: Any] = [
            "event": "PackAdjust", "state": "pending", "rebuild": true,
            "items": [["tile": "+29-096", "lat": 29, "lon": -96, "pack": "Some Pack",
                       "change": "hidden", "id": "+29-096@1"]]]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(!a.asks)
        #expect(a.pending == [O4PackAdjustPending(id: "+29-096@1", lat: 29, lon: -96,
                                                  tile: "+29-096", pack: "Some Pack",
                                                  change: "hidden")])
        #expect(O4PackAdjustCopy.rebuilding(tile: "+29-096", pack: "Some Pack", change: "hidden")
                == "Rebuilding tile +29-096 to match: terrain objects hidden in “Some Pack”.")
    }

    @Test func adjustWithOnlyOptimiseStepsAsks() {
        let event: [String: Any] = ["event": "PackAdjust", "state": "adjust", "items": [],
                                    "steps": [["key": "swap", "count": 2]]]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.asks)
    }

    /// #2272: the terrain row in Adjust… lists every terrain object the
    /// last build recognised, each ticked when the row hides it.
    @Test func terrainRowListsItsObjects() {
        let event: [String: Any] = [
            "event": "PackAdjust", "state": "adjust", "pack": "TFFJ", "pack_root": "/P",
            "items": [["key": "terrain", "count": 1, "uses": 1, "automatic": false,
                       "checked": true, "rebuild": true,
                       "objects": [["path": "Ortho/Cliffs.obj", "hideable": false, "hidden": true],
                                   ["path": "Ortho/RocksE.obj", "hideable": false,
                                    "hidden": false]]]]]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.asks)
        let objects = a.choices[0].objects
        #expect(objects.map(\.name) == ["Cliffs.obj", "RocksE.obj"])
        #expect(objects.map(\.hidden) == [true, false])
        #expect(objects[1].detail == "It models detail the tile’s elevation data lacks: "
                + "kept unless you hide it.")
        #expect(O4PackTerrainObject(path: "a/b.obj", hideable: true, hidden: true).detail
                == "The tile’s detailed elevation matches it: hidden unless you keep it.")
    }
}
