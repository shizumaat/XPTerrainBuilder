import XCTest
import SwiftUI
import AppKit
import SceneryKit
@testable import XPTerrainBuilder

/// #1563: the tile pane showed no missing-textures warning for a tile the
/// engine reports 252 missing on (+47-113, a symlink into a scenery
/// library). The check was asked for by a `.task` on the row itself, and
/// the row's body is empty until a check says otherwise — SwiftUI starts
/// no task on an empty view, so the check was never asked for. These host
/// the views for real, as the pane draws them.
@MainActor
final class TileMissingTexturesRowTests: XCTestCase {
    private let missing = O4TileTextureCheck(
        buildDir: "/Custom Scenery/zOrtho4XP_+47-113", checked: true,
        missingCount: 252, missing: ["22768_12192_USA216.dds"])

    private final class Calls { var count = 0 }

    /// The pane as it draws the row: an always-drawn line, the row, and
    /// the check task on the pane.
    private struct Pane: View {
        let answer: O4TileTextureCheck?
        let calls: Calls
        @State private var check: O4TileTextureCheck?
        var body: some View {
            VStack(alignment: .leading) {
                Text("Imagery")
                TileMissingTexturesRow(check: check) { nil }
            }
            .modifier(TileTextureCheckTask(
                key: "textures|+47-113", load: {
                    calls.count += 1
                    return answer
                }, check: $check))
        }
    }

    /// Host `view` in a window and let SwiftUI run its tasks.
    private func settle<V: View>(_ view: V) -> NSHostingView<V> {
        let host = NSHostingView(rootView: view)
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 400, height: 200),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.contentView = host
        window.orderFront(nil)
        let end = Date().addingTimeInterval(1.5)
        while Date() < end { RunLoop.main.run(until: Date().addingTimeInterval(0.05)) }
        window.orderOut(nil)
        return host
    }

    func testThePaneAsksForTheCheckAndTheRowAppears() {
        let calls = Calls()
        let shown = settle(Pane(answer: missing, calls: calls)).fittingSize.height
        XCTAssertEqual(calls.count, 1, "the check was never asked for")
        let quiet = settle(Pane(answer: nil, calls: Calls())).fittingSize.height
        XCTAssertGreaterThan(shown, quiet, "a tile missing textures shows the row")
    }

    /// The mechanism behind #1563, pinned so the task never moves back
    /// onto the row: a task on a view that shows nothing never runs.
    func testATaskOnAnEmptyRowNeverRuns() {
        let calls = Calls()
        _ = settle(VStack {
            Text("Imagery")
            TileMissingTexturesRow(check: nil) { nil }
                .task { calls.count += 1 }
        })
        XCTAssertEqual(calls.count, 0)
    }
}
