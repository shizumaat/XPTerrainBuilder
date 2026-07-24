import Testing
import Foundation
@testable import SceneryKit

/// Both products now ship MAJOR.MINOR.BUILD versions the build scripts bump
/// once per build (engine `1.50.<build>`, app `1.0.<build>`). The app reads
/// those strings out of files — its own tracked VERSION resource, the
/// engine's O4_Version.py or VERSION.txt — so the parser has to keep the
/// build component and reject anything that is not a version.
@Suite struct ProductVersionTests {

    @Test func parsesThreeComponentVersions() {
        #expect(ProductVersion("1.50.7") == ProductVersion(major: 1, minor: 50, build: 7))
        #expect(ProductVersion("1.0.0") == ProductVersion(major: 1, minor: 0, build: 0))
        #expect(ProductVersion("1.50.128")?.build == 128)
    }

    @Test func tolerateSurroundingWhitespaceAndQuotes() {
        // A VERSION file read whole, and the engine's version='…' literal.
        #expect(ProductVersion("1.0.3\n")?.description == "1.0.3")
        #expect(ProductVersion("  '1.50.12'  ")?.description == "1.50.12")
    }

    @Test func rejectsAnythingWithoutABuildNumber() {
        #expect(ProductVersion("1.50") == nil)
        #expect(ProductVersion("1.50.7.2") == nil)
        #expect(ProductVersion("unknown") == nil)
        #expect(ProductVersion("") == nil)
        #expect(ProductVersion("1.50.x") == nil)
        #expect(ProductVersion("1.-50.7") == nil)
        // Int() would happily take these; a version file holding them is
        // corrupt, not a version.
        #expect(ProductVersion("1.50.+7") == nil)
        #expect(ProductVersion("1.50. 7") == nil)
    }

    @Test func firstValidPrefersTheEarlierSource() {
        // The app hands over its VERSION resource, then Info.plist.
        #expect(ProductVersion.firstValid("1.0.4\n", "1.0.9") == "1.0.4")
        #expect(ProductVersion.firstValid(nil, "1.0.9") == "1.0.9")
        #expect(ProductVersion.firstValid("garbage", "1.0.9") == "1.0.9")
        #expect(ProductVersion.firstValid(nil, nil) == "unknown")
        #expect(ProductVersion.firstValid("1.0", "nope") == "unknown")
    }

    /// The app's tracked version file — the source of truth make_app.sh bumps
    /// and stamps into Info.plist.
    @Test func trackedAppVersionParsesAsOnePointZeroBuild() throws {
        let repo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // SceneryKitTests
            .deletingLastPathComponent()   // Tests
            .deletingLastPathComponent()   // repo root
        let url = repo.appendingPathComponent("Sources/XPTerrainBuilder/Resources/VERSION")
        let text = try String(contentsOf: url, encoding: .utf8)
        let version = try #require(ProductVersion(text))
        #expect(version.major == 1)
        #expect(version.minor == 0)
    }

    /// A FROZEN engine has no src/O4_Version.py — make_engine.sh stamps the
    /// version into VERSION.txt instead, and that file is the only thing
    /// standing between a release build and "unknown" in Settings.
    @Test func frozenEngineVersionComesFromVersionTxt() throws {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("frozen-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        try "1.50.42\n".write(to: root.appendingPathComponent("VERSION.txt"),
                              atomically: true, encoding: .utf8)

        #expect(OrthoEngine.readVersion(root: root) == "1.50.42")
        #expect(ProductVersion(try #require(OrthoEngine.readVersion(root: root)))?.build == 42)
    }

    /// The vendored engine's version — what Settings shows, and what the
    /// freeze script stamps into VERSION.txt.
    @Test func vendoredEngineVersionParsesAsOnePointFiftyBuild() throws {
        let repo = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let engineRoot = repo.appendingPathComponent("Ortho4XP")
        let raw = try #require(OrthoEngine.readVersion(root: engineRoot))
        let version = try #require(ProductVersion(raw))
        #expect(version.major == 1)
        #expect(version.minor == 50)
        #expect(version.description == raw)
    }
}
