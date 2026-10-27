import Testing
@testable import SceneryKit

/// #1539: a never-built tile selected after a built one shows the default
/// zoom (so the default preset card, Sharper airports, matches); a built
/// tile shows the zoom it recorded; the user's choice outranks adoption.
/// Qt twin: tests/test_qt_build_controls_sync.py (build_zl).
struct BuildZoomTests {
    @Test func neverBuiltTileShowsTheDefault() {
        var zoom = BuildZoom()
        zoom.adopt(TileImageryChoice(provider: "BI", zl: 17, source: .config))
        #expect(zoom.current(default: 16) == 17)
        zoom.adopt(nil)  // the next active tile was never built
        #expect(zoom.current(default: 16) == 16)
    }

    @Test func builtTileWithoutARecordedZoomShowsTheDefault() {
        var zoom = BuildZoom()
        zoom.adopt(TileImageryChoice(provider: "BI", zl: nil, source: .config))
        #expect(zoom.current(default: 16) == 16)
    }

    @Test func choosingAZoomOutranksTheAdoption() {
        var zoom = BuildZoom()
        zoom.adopt(TileImageryChoice(provider: "BI", zl: 18, source: .detected))
        zoom.chosen()
        #expect(zoom.adopted == nil)
        #expect(zoom.current(default: 15) == 15)
    }
}

/// #1549: a zoom chosen in Settings with tiles selected is theirs — never
/// the default (RULINGS 2026-10-28j (3)) — and goes with the selection.
struct BuildZoomSelectionTests {
    @Test func aChoiceForTheSelectionOutranksTheAdoption() {
        var zoom = BuildZoom()
        zoom.adopt(TileImageryChoice(provider: "BI", zl: 17, source: .config))
        zoom.chooseForSelection(18)
        #expect(zoom.current(default: 16) == 18)
        zoom.newSelection()
        #expect(zoom.selectionChoice == nil)
        #expect(zoom.current(default: 16) == 17)
    }

    @Test func choosingADefaultDropsTheSelectionsChoice() {
        var zoom = BuildZoom()
        zoom.chooseForSelection(18)
        zoom.chosen()
        #expect(zoom.current(default: 15) == 15)
    }
}
