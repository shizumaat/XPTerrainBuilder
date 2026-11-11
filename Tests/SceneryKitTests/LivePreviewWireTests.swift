import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_live_preview.py` (#2001): the reply of
/// `live_preview_squares` in `Ortho4XP/tests/fixtures/live_preview_reply.json`
/// (its fields are the engine's, asserted there) decodes, and the image
/// cache keeps the newest `O4_Live_Preview.APP_CACHE_IMAGES`.
@Suite struct LivePreviewWireTests {
    static let reply: O4JSON = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/live_preview_reply.json")
        // swiftlint:disable:next force_try
        return O4JSON.from(try! JSONSerialization.jsonObject(with: Data(contentsOf: url)))
    }()

    static func square(_ i: Int, stamp: String = "1-1", px: Int = 64) -> O4LivePreviewSquare {
        O4LivePreviewSquare(key: "k\(i)", path: "/x/\(i).dds", stamp: stamp, px: px,
                            north: 1, south: 0, west: 0, east: 1)
    }

    @Test func theReplyDecodes() {
        let squares = O4LivePreviewSquare.list(from: Self.reply)
        #expect(squares.count == 2)                      // the malformed row is skipped
        #expect(squares[0].key == "+53-061/21216_21712_BI16.dds")
        #expect(squares[0].px == 256 && squares[1].px == 128)
        #expect(abs(squares[0].north - 53.435719206694195) < 1e-12)
        #expect(squares[1].west == -60.64453125 && squares[1].east == -60.556640625)
        #expect(O4LivePreviewSquare.list(from: nil).isEmpty)
    }

    @Test func aChangedStampOrALargerMipIsFetchedAgain() {
        var cache = LivePreviewCache<Int>()
        cache.insert(Self.square(0), 7)
        #expect(cache.isCurrent(Self.square(0)))
        #expect(cache.isCurrent(Self.square(0, px: 32)))
        #expect(!cache.isCurrent(Self.square(0, stamp: "2-2")))
        #expect(!cache.isCurrent(Self.square(0, px: 256)))
        #expect(cache.image("k0") == 7)                  // kept until the new one lands
    }

    @Test func theCacheIsCappedLeastRecentlyListedFirst() {
        var cache = LivePreviewCache<Int>()
        let limit = LivePreviewCache<Int>.limit
        #expect(limit == 192)
        for i in 0..<limit { cache.insert(Self.square(i), i) }
        cache.touch(["k0"])                              // listed again: recent
        cache.insert(Self.square(limit), limit)
        #expect(cache.count == limit)
        #expect(cache.image("k0") == 0 && cache.image("k1") == nil)
        cache.removeAll()
        #expect(cache.count == 0)
    }
}
