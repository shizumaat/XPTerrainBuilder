import SwiftUI
import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// The Build pane's Activity and Completed sections (#1556) and the list's
/// native selection, one with the map's (#1537). Qt twins:
/// `Ortho4XP/tests/test_qt_activity_keep.py`, `test_qt_activity_list.py`.
@MainActor
final class ActivitySectionsTests: XCTestCase {
    private let a = BuildModel.TileCoord(lat: 47, lon: -123)
    private let b = BuildModel.TileCoord(lat: 48, lon: -6)
    private let c = BuildModel.TileCoord(lat: 49, lon: -6)

    private func model() -> BuildActivityModel {
        let model = BuildActivityModel()
        model.queueRows([a, b, c])
        return model
    }

    private func set(_ model: BuildActivityModel, _ coord: BuildModel.TileCoord,
                     _ state: TileProgress.State) {
        model.tiles[coord] = TileProgress(state: state, label: state.rawValue, percent: 0)
    }

    func testDoneTilesLeaveActivityForCompleted() {
        let model = model()
        set(model, a, .done)
        set(model, b, .error)
        set(model, c, .stopped)
        XCTAssertEqual(model.rows(in: .completed), [a])
        XCTAssertEqual(Set(model.rows(in: .activity)), [b, c])
        XCTAssertEqual(ActivitySections.completedTitle(model.rows(in: .completed).count),
                       "Completed (1)")
    }

    func testARequeuedDoneTileMovesBackToActivity() {
        let model = model()
        set(model, a, .done)
        set(model, b, .done)
        XCTAssertEqual(model.rows(in: .completed).count, 2)
        model.queueRows([a])
        XCTAssertEqual(model.rows(in: .completed), [b])
        XCTAssertEqual(model.rows(in: .activity).first, a)
    }

    func testCompletedStartsCollapsedAndKeepsTheChoice() {
        let model = model()
        XCTAssertFalse(model.completedExpanded)
        model.completedExpanded = true
        set(model, a, .done)
        model.queueRows([a])
        set(model, a, .done)
        XCTAssertTrue(model.completedExpanded)
    }

    // MARK: - #1537: the list's native selection is the map selection

    private final class Map {
        var selected: Set<BuildModel.TileCoord> = []
        var active: BuildModel.TileCoord?
        var framed: [BuildModel.TileCoord] = []
    }

    private func listSelection(_ map: Map, rows: [BuildModel.TileCoord])
        -> Binding<Set<BuildModel.TileCoord>> {
        ActivityListSelection.binding(
            rows: { rows },
            selected: Binding(get: { map.selected }, set: { map.selected = $0 }),
            active: Binding(get: { map.active }, set: { map.active = $0 }),
            frame: { map.framed.append($0) })
    }

    func testTheListShowsTheMapSelection() {
        let map = Map()
        let list = listSelection(map, rows: [a, b])
        XCTAssertEqual(list.wrappedValue, [])
        map.selected = [a, c]          // c has no row
        XCTAssertEqual(list.wrappedValue, [a])
        map.selected = [a, b]          // every row: every row shows it
        XCTAssertEqual(list.wrappedValue, [a, b])
    }

    func testAListClickSelectsItsTileOnTheMapAndFramesIt() {
        let map = Map()
        map.selected = [a, c]
        map.active = a
        let list = listSelection(map, rows: [a, b])
        list.wrappedValue = [b]
        XCTAssertEqual(map.selected, [b])
        XCTAssertEqual(map.active, b)
        XCTAssertEqual(map.framed, [b])
        list.wrappedValue = [a, b]      // ⌘-click adds a: active, no frame
        XCTAssertEqual(map.selected, [a, b])
        XCTAssertEqual(map.active, a)
        XCTAssertEqual(map.framed, [b])
        list.wrappedValue = [a, b]      // unchanged: nothing happens
        XCTAssertEqual(map.framed, [b])
    }

    /// RULINGS 2026-10-28n: the selection is the platform's own — no
    /// custom fill, ring or box-edge metrics are left in the app.
    func testNoCustomRowFillIsLeft() throws {
        let sources = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Sources/XPTerrainBuilder")
        let files = try FileManager.default.contentsOfDirectory(atPath: sources.path)
            .filter { $0.hasSuffix(".swift") }
        XCTAssertFalse(files.contains("ActivityRowFill.swift"))
        for file in files {
            let text = try String(contentsOf: sources.appendingPathComponent(file), encoding: .utf8)
            for name in ["ActivityRowFill", "PaneBoxMetrics", "activityRowFill", "filledRows"] {
                XCTAssertFalse(text.contains(name), "\(file) still names \(name)")
            }
        }
        let list = try String(contentsOf: sources.appendingPathComponent("ActivitySections.swift"),
                              encoding: .utf8)
        XCTAssertTrue(list.contains("List(selection:"))
        XCTAssertTrue(list.contains("Section(isExpanded:"))
    }
}
