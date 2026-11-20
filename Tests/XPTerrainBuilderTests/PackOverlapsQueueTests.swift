import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// #2200: one overlapping-packs question per tile — Apply closes the sheet
/// and never re-opens the same tile's question behind it. Qt: the window
/// shows one non-modal question per tile and pair set.
@MainActor
final class PackOverlapsQueueTests: XCTestCase {
    private func offer(_ lat: Int, _ lon: Int, _ state: String = "ask") -> O4PackOverlaps {
        O4PackOverlaps(lat: lat, lon: lon, items: [], files: [], state: state, error: "")
    }

    func testPressingTwiceThenApplyClosesTheSheet() {
        var (shown, queue) = PackOverlapsQueue.arrive(offer(25, 55), onScreen: nil, queue: [])
        (shown, queue) = PackOverlapsQueue.arrive(offer(25, 55), onScreen: shown, queue: queue)
        (shown, queue) = PackOverlapsQueue.arrive(offer(25, 55, "found"), onScreen: shown, queue: queue)
        XCTAssertEqual(queue.count, 0)
        (shown, queue) = PackOverlapsQueue.closed(shown, answered: true, queue: queue)
        XCTAssertNil(shown)
    }

    func testAnotherTileWaitsItsTurnOnceAndApplyDropsTheAnsweredTile() {
        var (shown, queue) = PackOverlapsQueue.arrive(offer(25, 55), onScreen: nil, queue: [])
        (shown, queue) = PackOverlapsQueue.arrive(offer(25, 56), onScreen: shown, queue: queue)
        (shown, queue) = PackOverlapsQueue.arrive(offer(25, 56, "found"), onScreen: shown, queue: queue)
        XCTAssertEqual(queue.map(\.state), ["found"])
        (shown, queue) = PackOverlapsQueue.closed(shown, answered: true, queue: queue)
        XCTAssertEqual(shown?.lon, 56)
        XCTAssertTrue(queue.isEmpty)
    }

    func testTheWaitKeys() {
        XCTAssertEqual(PackCommandWaits.overlapsKey(lat: -3, lon: 7), "overlaps|-03+007")
        XCTAssertEqual(PackCommandWaits.packKey("/X/Custom Scenery/Pack A/"), "pack|Pack A")
    }
}
