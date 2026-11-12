import Testing
import Foundation
@testable import XPTerrainBuilder
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_world_built.py`: both feed the statuses of
/// `Ortho4XP/tests/fixtures/world_swap_watch_cases.json` to a fresh watch,
/// so both apps rescan the Build map on the same World/flight swaps.
@Suite struct WorldSwapWatchTests {
    static let cases: [[String: Any]] = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/world_swap_watch_cases.json")
        // swiftlint:disable:next force_try
        let root = try! JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        return root["cases"] as! [[String: Any]]
    }()

    @Test func aSwapRescansOnce() throws {
        #expect(!Self.cases.isEmpty)
        for test in Self.cases {
            var watch = WorldSwapWatch()
            let name = test["name"] as? String ?? ""
            for step in test["steps"] as? [[String: Any]] ?? [] {
                let expected = step["rescan"] as? Bool
                if let jobs = step["flight"] {
                    let status = try #require(O4FlightStatus.parse(
                        O4JSON.from(["flight": "f", "jobs": jobs])))
                    #expect(watch.flightStatus(status) == expected, "\(name)")
                } else if let swap = step["world"] {
                    let status = O4WorldStatus.parse(["last_swap": swap])
                    #expect(watch.worldStatus(status) == expected, "\(name)")
                }
            }
        }
    }
}
