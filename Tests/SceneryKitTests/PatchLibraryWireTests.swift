import Foundation
import Testing
@testable import SceneryKit

/// #1699 phase 2: the patch library's results, as `o4_engine.library`'s
/// `library_check` / `library_apply` / `library_matches` /
/// `library_publish_preview` / `library_publish` send them.
struct PatchLibraryWireTests {
    private func ready(_ command: String, _ result: [String: Any]) -> O4JSON? {
        O4JSON.from(["event": "LibraryReady", "command": command, "error": "",
                     "result": result] as [String: Any])
    }

    @Test func checkAndApplyDecode() throws {
        let row: [String: Any] = [
            "icao": "KPDX", "tile": "+45-123", "state": "newer", "pack": "KPDX (Flightbeam)",
            "entry_pack": "KPDX (Flightbeam)", "version": 2, "local_version": 1,
            "entry": "entries/KPDX/KPDX (Flightbeam)/0123456789ab/v2",
            "signature": String(repeating: "a", count: 32), "verified": true,
            "publisher": "dev", "solved_usable": true, "reason": "", "warning": ""]
        let check: O4PatchLibraryCheck = try OrthoEngineClient.decodeLibraryReady(
            ready("library_check", ["configured": true, "rows": [row], "regions": ["+40-130"],
                                    "checked": "2026-11-02T23:00:00Z"])).get()
        #expect(check.rows.first?.localVersion == 1 && check.rows.first?.solvedUsable == true)
        let applied: O4PatchLibraryApplied = try OrthoEngineClient.decodeLibraryReady(
            ready("library_apply", ["icao": "KPDX", "tile": "+45-123", "version": 2,
                                    "entry": "entries/KPDX/p/0123456789ab/v2", "mode": "solved",
                                    "reason": "", "edits": "none", "files": 6, "bytes": 12,
                                    "warning": ""])).get()
        #expect(applied.mode == "solved" && applied.conflict == nil)
    }

    @Test func matchesPreviewAndPublishDecode() throws {
        let matches: O4PatchLibraryMatches = try OrthoEngineClient.decodeLibraryReady(
            ready("library_matches", ["configured": true, "airports": ["KPDX": [[
                "tier": "exact", "entry": "e/v1", "pack": "p", "version": 1, "verified": false,
                "publisher": "pilot", "solved_usable": false,
                "reason": "the patch was solved by another version of the auto-patch engine"]]]])).get()
        #expect(matches.airports["KPDX"]?.first?.tier == "exact")
        let preview: O4PatchLibraryPreview = try OrthoEngineClient.decodeLibraryReady(
            ready("library_publish_preview", [
                "icao": "KPDX", "entry": "e/v1", "version": 1, "pack": "p", "kind": "payware",
                "files": [["name": "solved/KPDX_auto.patch.osm.xz", "bytes": 10]],
                "bytes": 10, "problems": [], "verified": true, "signed_in": "",
                "licence": "ODbL-1.0", "licence_accepted": false, "attribution": "…"])).get()
        #expect(preview.signedIn.isEmpty && preview.files.count == 1)
        let published: O4PatchLibraryPublished = try OrthoEngineClient.decodeLibraryReady(
            ready("library_publish", ["pull_url": "https://github.com/o/r/pull/1", "number": 1,
                                      "entry": "e/v1", "version": 1, "auto_merge": true])).get()
        #expect(published.autoMerge)
        #expect(O4ProtocolVersion.supportsPatchLibrary("1.24"))
        #expect(!O4ProtocolVersion.supportsPatchLibrary("1.23"))
    }
}
