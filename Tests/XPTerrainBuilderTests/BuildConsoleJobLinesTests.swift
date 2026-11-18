import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// #2148: the build console shows the selected tiles' lines; another
/// job's lines (the World job's downloads) never (Qt twin:
/// tests/test_qt_build_history.py::test_console_drops_job_lines).
@MainActor
final class BuildConsoleJobLinesTests: XCTestCase {
    func testJobLinesAndOtherTilesAreNotShown() {
        let console = BuildConsoleModel()
        console.append("[+47+012] Step 2 done")
        console.append("[+69+018] Step 1 done")
        console.append("[job:world]    Downloading missing orthophoto 1_2_BI_low13.jpg")
        console.append("=== Run complete ===")
        console.setView(filter: ["+47+012"], saved: [], live: true)
        XCTAssertEqual(console.visibleLines, ["[+47+012] Step 2 done", "=== Run complete ==="])
        console.setView(filter: [], saved: [], live: true)
        XCTAssertFalse(console.visibleLines.contains { $0.hasPrefix("[job:") })
        XCTAssertEqual(console.visibleLines.count, 3)
    }
}
