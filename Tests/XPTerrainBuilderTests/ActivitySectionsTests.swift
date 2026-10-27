import AppKit
import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// The Build pane's Activity and Completed sections (#1556) and the
/// selected rows' fill (#1537). Qt twins: `Ortho4XP/tests/test_qt_completed.py`.
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

    private func luminance(_ color: NSColor, _ name: NSAppearance.Name) -> CGFloat {
        var out: CGFloat = 0
        NSAppearance(named: name)!.performAsCurrentDrawingAppearance {
            let rgb = color.usingColorSpace(.sRGB)!
            out = 0.2126 * rgb.redComponent + 0.7152 * rgb.greenComponent
                + 0.0722 * rgb.blueComponent
        }
        return out
    }

    func testTheFillIsSubtleButDistinctInBothAppearances() {
        let fill = ActivityRowFill.system
        let pane = NSColor.underPageBackgroundColor
        let first = ActivityRowFill.awayFromText(.textBackgroundColor)
        for name in [NSAppearance.Name.darkAqua, .aqua] {
            let step = abs(luminance(fill, name) - luminance(pane, name))
            let firstStep = abs(luminance(first, name) - luminance(pane, name))
            XCTAssertGreaterThan(step, 0.005, "\(name)")
            XCTAssertLessThan(step, firstStep / 2, "\(name)")
        }
        XCTAssertLessThan(luminance(fill, .darkAqua), luminance(pane, .darkAqua))
        XCTAssertGreaterThan(luminance(fill, .aqua), luminance(pane, .aqua))
    }

    func testSubtleIsAQuarterStep() {
        let pane = NSColor(srgbRed: 0.2, green: 0.2, blue: 0.2, alpha: 1)
        let out = ActivityRowFill.subtle(pane: pane, text: pane)   // away = 0.1
        XCTAssertEqual(out.redComponent, 0.175, accuracy: 1e-6)
    }

    func testTheFillSpansTheBoxWithSquareCorners() {
        XCTAssertEqual(ActivityRowFill.cornerRadius, 0)
        XCTAssertEqual(ActivityRowFill.sideReach, PaneBoxMetrics.edgeInset)
        XCTAssertEqual(PaneBoxMetrics.edgeInset,
                       PaneBoxMetrics.padding + PaneBoxMetrics.groupBoxInset)
    }

    func testAwayFromText() {
        let dark = ActivityRowFill.awayFromText(NSColor(srgbRed: 0.2, green: 0.2, blue: 0.2, alpha: 1))
        XCTAssertEqual(dark.redComponent, 0.1, accuracy: 1e-6)
        let light = ActivityRowFill.awayFromText(NSColor(srgbRed: 0.8, green: 0.8, blue: 0.8, alpha: 1))
        XCTAssertEqual(light.redComponent, 0.9, accuracy: 1e-6)
    }
}
