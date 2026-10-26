import Testing
import Foundation
@testable import SceneryKit

/// A built tile's imagery (#1334): the cfg's, else what its texture names
/// carry. The fixture is shared with `Ortho4XP/tests/test_tile_imagery_parity.py`,
/// which runs the engine's `imagery_from_file_names` and `effective_imagery`
/// over the same cases.
struct TileImageryTests {

    private func fixture() throws -> [String: Any] {
        let url = try #require(Bundle.module.url(
            forResource: "Fixtures/Imagery/tile_imagery", withExtension: "json"))
        return try #require(
            try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    @Test func detectionMatchesTheEngine() throws {
        for case let entry as [String: Any] in try fixture()["detect"] as? [Any] ?? [] {
            let names = entry["names"] as? [String] ?? []
            let found = PackImagery.fromFileNames(names)
            if let provider = entry["provider"] as? String {
                #expect(found == PackImagery(provider: provider, zl: entry["zl"] as? Int), "\(names)")
            } else {
                #expect(found == nil, "\(names)")
            }
        }
    }

    @Test func resolverMatchesTheEngine() throws {
        for case let entry as [String: Any] in try fixture()["resolve"] as? [Any] ?? [] {
            let info = try #require(O4TileInfo(json: O4JSON.from(try #require(entry["info"]))))
            let found = TileImageryChoice.resolve(info)
            if let expect = entry["expect"] as? [Any], expect.count == 3 {
                let source = try #require(TileImageryChoice.Source(rawValue: expect[2] as? String ?? ""))
                #expect(found == TileImageryChoice(provider: expect[0] as? String ?? "",
                                                   zl: expect[1] as? Int, source: source))
            } else {
                #expect(found == nil)
            }
        }
    }

    @Test func configWinsAndDetectionFillsTheGap() throws {
        let cfg = try #require(O4TileInfo(json: .object([
            "lat": .int(47), "lon": .int(11), "provider": .string("Arc"), "zl": .int(17),
            "detected_provider": .string("BI"), "detected_zl": .int(16),
        ])))
        #expect(TileImageryChoice.resolve(cfg)?.source == .config)
        let bare = try #require(O4TileInfo(json: .object([
            "lat": .int(47), "lon": .int(11), "detected_provider": .string("BI"),
            "detected_zl": .int(16),
        ])))
        #expect(TileImageryChoice.resolve(bare) == TileImageryChoice(provider: "BI", zl: 16, source: .detected))
    }
}
