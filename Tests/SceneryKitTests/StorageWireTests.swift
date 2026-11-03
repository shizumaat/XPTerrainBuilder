import Foundation
import Testing
@testable import SceneryKit

/// Settings ▸ Storage (#1724): the engine's `storage_scan` and
/// `storage_clear` results (`Ortho4XP/src/o4_engine/storage.py`), as the
/// `LibraryReady` event carries them.
struct StorageWireTests {
    @Test func storageScanDecodes() throws {
        let store: [String: Any] = [
            "kind": "imagery", "label": "Orthophotos", "policy": "cache", "note": "n",
            "path": "/d/Orthophotos", "bytes": 1_000, "apparent_bytes": 3_000,
            "files": 2, "last_used": 1_700_000_000.5]
        let kept: [String: Any] = [
            "kind": "tiles", "label": "Built tiles", "policy": "kept", "note": "n",
            "path": "/d/Tiles", "bytes": 0, "apparent_bytes": 0, "files": 0,
            "last_used": NSNull()]
        let event = O4JSON.from(["event": "LibraryReady", "command": "storage_scan", "error": "",
                                 "result": ["root": "/d", "stores": [store, kept],
                                            "cache_bytes": 1_000, "kept_bytes": 0,
                                            "measured": "private", "auto_clean_days": 0.0,
                                            "caps": [String: Any]()] as [String: Any]] as [String: Any])
        let scan: O4StorageScan = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(scan.stores.map(\.kind) == ["imagery", "tiles"])
        #expect(scan.stores[0].isCache && !scan.stores[1].isCache)
        #expect(scan.stores[0].apparentBytes == 3_000 && scan.stores[1].lastUsed == nil)
        #expect(scan.cacheBytes == 1_000 && scan.measured == "private")
    }

    @Test func storageClearDecodes() throws {
        let event = O4JSON.from(["event": "LibraryReady", "command": "storage_auto_clean", "error": "",
                                 "result": ["freed_bytes": 42, "files": 3, "kinds": ["tmp": 42],
                                            "dry_run": false, "stopped": false,
                                            "ran": true] as [String: Any]] as [String: Any])
        let done: O4StorageCleared = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(done.freedBytes == 42 && done.files == 3 && done.ran == true && !done.dryRun)
    }
}
