import Testing
import Foundation
@testable import SceneryKit

/// Beta plan §1 B2: a build cannot start without a valid X-Plane folder.
///
/// `BuildModel.canBuild` is `engine != nil && … && xplaneBlockReason == nil`,
/// and `xplaneBlockReason` is exactly `XPlaneInstall.buildBlockReason(…)` fed
/// the X-Plane pref and the two config keys — the app target is not a test
/// target (Package.swift has SceneryKitTests only), so the predicate canBuild
/// delegates to is what is pinned here, with the same inputs.
///
/// The engine twin of this law is `Ortho4XP/tests/test_cifp_missing_refusal.py`
/// (`O4_Settings_Model.xplane_install_problem` / `cifp_refusal_reason`).
@Suite struct XPlaneInstallTests {

    /// A fake X-Plane tree under a temp dir — never the real install.
    private func makeTree(cifp: Bool) throws -> URL {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("xpi-\(UUID().uuidString)", isDirectory: true)
        let fm = FileManager.default
        try fm.createDirectory(at: root.appendingPathComponent("Custom Scenery"),
                               withIntermediateDirectories: true)
        if cifp {
            try fm.createDirectory(
                at: root.appendingPathComponent("Resources/default data/CIFP"),
                withIntermediateDirectories: true)
        }
        return root
    }

    @Test func noFolderIsNotAnInstall() {
        #expect(XPlaneInstall.problem(at: "") != nil)
        #expect(XPlaneInstall.problem(at: "   ") != nil)
        #expect(XPlaneInstall.problem(at: "/definitely/not/here") != nil)
    }

    @Test func customSceneryAloneIsNotEnough() throws {
        let root = try makeTree(cifp: false)
        defer { try? FileManager.default.removeItem(at: root) }
        let problem = XPlaneInstall.problem(at: root.path)
        #expect(problem != nil)
        #expect(problem?.contains("CIFP") == true)
    }

    @Test func aFullTreeIsAccepted() throws {
        let root = try makeTree(cifp: true)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(XPlaneInstall.problem(at: root.path) == nil)
    }

    /// canBuild is false with no X-Plane path, AND the reason is surfaced —
    /// the block reason is the string BuildPane shows as the button's help.
    @Test func buildIsBlockedWithNoXPlanePathAndSaysWhy() {
        let reason = XPlaneInstall.buildBlockReason(
            xplanePath: "", cifpDataPath: "", customSceneryDir: "")
        #expect(reason != nil)
        #expect(reason?.contains("X-Plane") == true)
        #expect(reason?.isEmpty == false)
    }

    @Test func buildIsBlockedWhenTheFolderIsNotAnInstall() throws {
        let root = try makeTree(cifp: false)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(XPlaneInstall.buildBlockReason(
            xplanePath: root.path, cifpDataPath: "", customSceneryDir: "") != nil)
    }

    @Test func aValidInstallUnblocksTheBuild() throws {
        let root = try makeTree(cifp: true)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(XPlaneInstall.buildBlockReason(
            xplanePath: root.path,
            cifpDataPath: "",
            customSceneryDir: root.appendingPathComponent("Custom Scenery").path) == nil)
    }

    /// The gate is the engine's law, not a folder-shaped ritual.
    @Test func aNavigraphCorpusAloneIsEnough() throws {
        let cifp = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("navigraph-\(UUID().uuidString)/CIFP", isDirectory: true)
        try FileManager.default.createDirectory(at: cifp, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: cifp.deletingLastPathComponent()) }
        #expect(XPlaneInstall.buildBlockReason(
            xplanePath: "", cifpDataPath: cifp.path, customSceneryDir: "") == nil)
    }

    /// A typo must resolve to nothing, never fall back to another corpus.
    @Test func aCIFPPathThatIsNotADirectoryResolvesToNothing() throws {
        let root = try makeTree(cifp: true)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(XPlaneInstall.resolveCIFPDir(
            cifpDataPath: root.appendingPathComponent("nope").path,
            customSceneryDir: root.appendingPathComponent("Custom Scenery").path) == nil)
    }

    @Test func navigraphWinsOverTheStockCorpus() throws {
        let root = try makeTree(cifp: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let navigraph = root.appendingPathComponent("Custom Data/CIFP")
        try FileManager.default.createDirectory(at: navigraph, withIntermediateDirectories: true)
        #expect(XPlaneInstall.resolveCIFPDir(
            cifpDataPath: "",
            customSceneryDir: root.appendingPathComponent("Custom Scenery").path)
            == navigraph.path)
    }
}
