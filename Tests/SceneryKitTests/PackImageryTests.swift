import Testing
import Foundation
@testable import SceneryKit

/// #1227: installed ortho packs the app did not build read their imagery
/// from their own file names (or Ortho4XP cfg), including packs linked in
/// from another volume.
@Suite struct PackImageryTests {
    @Test func dominantProviderAndBaseZoomFromFileNames() {
        var names = (0..<30).map { "\(25000 + $0 * 16)_10752_BI16.dds" }
        names += (0..<4).map { "\(25000 + $0 * 16)_10752_BI18.dds" }   // airport cover
        names += ["25000_10752_GO216.dds", "25000_10752_BI16_sea.ter", "readme.txt"]
        #expect(PackImagery.fromFileNames(names) == PackImagery(provider: "BI", zl: 16))
    }

    @Test func providerCodesEndingInDigitsParse() {
        let names = ["24576_10240_USA_216.dds", "24592_10240_USA_216.ter"]
        #expect(PackImagery.fromFileNames(names) == PackImagery(provider: "USA_2", zl: 16))
    }

    @Test func noOrtho4XPNamesMeansUnknown() {
        #expect(PackImagery.fromFileNames(["grass.dds", "rock_01.ter"]) == nil)
    }

    @Test func configFallbackStripsLegacyQuotes() {
        let cfg = "default_website='Arc'\ndefault_zl=17\nzone_list=[]\n"
        #expect(PackImagery.parseConfig(cfg) == PackImagery(provider: "Arc", zl: 17))
        #expect(PackImagery.parseConfig("default_zl=16\n") == nil)
    }

    @Test func scannerReadsImageryThroughSymlinkedPack() throws {
        let fm = FileManager.default
        let base = fm.temporaryDirectory.appendingPathComponent("pack-imagery-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: base) }
        // The pack lives on "another volume" and is linked into Custom Scenery.
        let external = base.appendingPathComponent("External/zOrtho4XP_+45-123")
        let textures = external.appendingPathComponent("textures")
        try fm.createDirectory(at: textures, withIntermediateDirectories: true)
        for i in 0..<24 {
            try Data().write(to: textures.appendingPathComponent("\(23000 + i * 16)_10432_GO217.dds"))
        }
        let root = base.appendingPathComponent("X-Plane")
        let customScenery = root.appendingPathComponent("Custom Scenery")
        try fm.createDirectory(at: customScenery, withIntermediateDirectories: true)
        try fm.createSymbolicLink(at: customScenery.appendingPathComponent("zOrtho4XP_+45-123"),
                                  withDestinationURL: external)

        let scan = InstallationScanner(root: root).scan(cache: [:])
        let pack = try #require(scan.installation.packs.first { $0.name == "zOrtho4XP_+45-123" })
        #expect(pack.imagery == PackImagery(provider: "GO2", zl: 17))
        // The warm path rebuilds packs from the cache with the same answer.
        let warm = InstallationScanner(root: root).packsFromCache(scan.cache)
        #expect(warm.first?.imagery == PackImagery(provider: "GO2", zl: 17))
    }
}
