import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_live_preview.py` (#2001; owner
/// 2026-11-12T19:28Z): the reply of `live_preview_squares` in
/// `Ortho4XP/tests/fixtures/live_preview_reply.json` (its fields are the
/// engine's, asserted there) decodes with its `stale` squares and marked
/// tiles; the image cache is bounded in bytes; the fetch plan is
/// `O4_Live_Preview.fetch_plan`'s (coarse first, then each square at its
/// own size); a `pending` mip is told apart.
@Suite struct LivePreviewWireTests {
    static let reply: O4JSON = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/live_preview_reply.json")
        // swiftlint:disable:next force_try
        return O4JSON.from(try! JSONSerialization.jsonObject(with: Data(contentsOf: url)))
    }()

    static func square(_ key: String, stamp: String = "1", px: Int = 64) -> O4LivePreviewSquare {
        O4LivePreviewSquare(key: key, path: "/x/\(key).dds", stamp: stamp, px: px,
                            north: 1, south: 0, west: 0, east: 1)
    }

    @Test func theReplyDecodes() {
        let squares = O4LivePreviewSquare.list(from: Self.reply)
        #expect(squares.count == 2)                      // the malformed row is skipped
        #expect(squares[0].key == "+53-061/21216_21712_BI16.dds")
        #expect(squares[0].px == 4096 && squares[1].px == 512)
        #expect(squares[0].sharp && !squares[1].sharp)    // #2020: full resolution
        #expect(!squares[0].stale && squares[1].stale)    // X-Plane holds the earlier one
        #expect(abs(squares[0].north - 53.435719206694195) < 1e-12)
        #expect(squares[1].west == -60.64453125 && squares[1].east == -60.556640625)
        #expect(O4LivePreviewSquare.list(from: nil).isEmpty)
        let tiles = O4LivePreviewTile.list(from: Self.reply)
        #expect(tiles == [O4LivePreviewTile(lat: 53, lon: -62, state: "own"),
                          O4LivePreviewTile(lat: 54, lon: -61, state: "reload")])
    }

    @Test func aPendingMipIsToldApart() {
        let image = O4JSON.from(["width": 64, "height": 64, "format": "jpeg", "data": "AAEC"])
        #expect(O4LivePreviewMip.from(ok: true, result: image) == .image(Data([0, 1, 2])))
        #expect(O4LivePreviewMip.from(ok: true, result: O4JSON.from(["pending": true])) == .pending)
        #expect(O4LivePreviewMip.from(ok: false, result: nil) == .failed)
    }

    @Test func aChangedStampOrALargerMipIsFetchedAgain() {
        var cache = LivePreviewCache<Int>()
        cache.insert(Self.square("a"), 7, px: 64, bytes: 1)
        #expect(cache.isCurrent(Self.square("a")))
        #expect(cache.isCurrent(Self.square("a", px: 32)))
        #expect(!cache.isCurrent(Self.square("a", stamp: "2")))
        #expect(!cache.isCurrent(Self.square("a", px: 256)))
        #expect(cache.image("a") == 7)                   // kept until the new one lands
    }

    /// The same rows and answer as `test_the_fetch_plan_is_coarse_first_then_finer`.
    @Test func theFetchPlanIsCoarseFirstThenFiner() {
        #expect(LivePreviewCache<Int>.coarsePx == 64)
        var cache = LivePreviewCache<Int>()
        cache.insert(Self.square("c", stamp: "1"), 0, px: 4096, bytes: 1)
        cache.insert(Self.square("d", stamp: "1"), 0, px: 256, bytes: 1)
        let rows = [Self.square("a", px: 1024), Self.square("b", px: 32),
                    Self.square("c", stamp: "2", px: 256), Self.square("d", px: 256)]
        let plan = cache.plan(rows).map { "\($0.square.key)\($0.px)" }
        #expect(plan == ["a64", "a1024", "b32", "c256"])
    }

    @Test func theCacheIsBoundedInBytesLeastRecentlyListedFirst() {
        #expect(LivePreviewCache<Int>.limitMB == 512)
        var cache = LivePreviewCache<Int>()
        cache.budget = 100
        for i in 0..<10 { cache.insert(Self.square("k\(i)"), i, px: 64, bytes: 30) }
        #expect(cache.count == 3 && cache.bytes == 90)
        cache.touch(["k7"])                               // listed again: recent
        cache.insert(Self.square("k10"), 10, px: 64, bytes: 30)
        #expect(cache.image("k7") == 7 && cache.image("k8") == nil && cache.bytes <= 100)
        cache.insert(Self.square("huge"), 99, px: 4096, bytes: 1000)   // the newest stays
        #expect(cache.count == 1 && cache.image("huge") == 99)
        cache.removeAll()
        #expect(cache.count == 0 && cache.bytes == 0)
    }
}
