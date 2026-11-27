import Testing
import Foundation
@testable import SceneryKit

/// #2301: the launch caches write the engine's imagery sources and World
/// states back out and read them on the next launch; what comes back is
/// exactly what the engine sent.
struct LaunchCacheCodecTests {
    @Test func imagerySourcesSurviveTheCacheRoundTrip() throws {
        let url = try #require(Bundle.module.url(
            forResource: "Fixtures/Imagery/imagery_menu", withExtension: "json"))
        let object = try #require(
            try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let rows = try O4JSON.from(try #require(object["rows"])).decode([O4ImagerySource].self)
        #expect(!rows.isEmpty)
        let back = try JSONDecoder().decode(
            [O4ImagerySource].self, from: JSONEncoder().encode(rows))
        #expect(back == rows)
    }

    @Test func worldTilesSurviveTheCacheRoundTrip() throws {
        let tiles = [
            O4WorldTile(state: .meshLowRes, origin: "xptb", sharp: 0.25, source: "lean",
                        volume: "Ortho", dsf: "/w/+48-006.dsf", provider: "BI"),
            O4WorldTile(state: .off),
        ]
        let back = try JSONDecoder().decode(
            [O4WorldTile].self, from: JSONEncoder().encode(tiles))
        #expect(back == tiles)
    }
}
