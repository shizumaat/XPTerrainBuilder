import Foundation

/// The auto-patch object reseater's per-pack sidecar
/// (`.o4_reanchor_provenance.json`): which .obj files the engine rewrote so
/// a custom airport's 3-D objects sit on a rebuilt mesh, keyed by the tile
/// whose mesh drove the bake. The pristine original of every rewritten file
/// lives beside it as `<name>.anchor_bak`.
///
/// Read side and restore mirror the engine's
/// `Ortho4XP/src/auto_patch/object_rebake.py` (`_load_provenance`,
/// `restore`): restore puts the backups back byte-identically, leaves the
/// backup files in place (the next bake adopts them as authoritative), and
/// removes the sidecar. `.anchor_bak.orphaned` relics are never touched.
public enum ReanchorProvenance {
    public static let sidecarName = ".o4_reanchor_provenance.json"
    public static let backupSuffix = ".anchor_bak"

    public struct PackModifications: Sendable, Hashable {
        public let packRoot: URL
        /// Rewritten object resource paths per tile key ("+46+008"). The
        /// empty-string key collects prototype-era entries with no
        /// recorded tile.
        public let objectsByTile: [String: [String]]

        public init(packRoot: URL, objectsByTile: [String: [String]]) {
            self.packRoot = packRoot
            self.objectsByTile = objectsByTile
        }
    }

    /// Parse a pack's sidecar. nil when the pack carries none (or an
    /// unreadable/empty one). Handles both the version-1 format
    /// (`objects` as a map with per-entry `tile`) and the prototype
    /// format (`objects` as a list, tile derived from the recorded
    /// `mesh` path), like the engine's `_normalise_provenance`.
    public static func read(packRoot: URL) -> PackModifications? {
        let sidecar = packRoot.appendingPathComponent(sidecarName)
        guard let data = try? Data(contentsOf: sidecar),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }

        var byTile: [String: [String]] = [:]
        if let objects = raw["objects"] as? [String: Any] {
            for (resource, entry) in objects {
                let tile = (entry as? [String: Any])?["tile"] as? String ?? ""
                byTile[tile, default: []].append(resource)
            }
        } else if let list = raw["objects"] as? [String] {
            let tile = tileName(fromMeshPath: raw["mesh"] as? String ?? "")
            for resource in list {
                byTile[tile, default: []].append(resource)
            }
        }
        guard !byTile.isEmpty else { return nil }
        for key in byTile.keys { byTile[key]?.sort() }
        return PackModifications(packRoot: packRoot, objectsByTile: byTile)
    }

    /// `.../Data+35-081.mesh` -> `+35-081` (the engine's
    /// `_tile_name_from_mesh_path`).
    static func tileName(fromMeshPath path: String) -> String {
        let base = (path as NSString).lastPathComponent
        if base.hasPrefix("Data"), base.hasSuffix(".mesh") {
            return String(base.dropFirst("Data".count).dropLast(".mesh".count))
        }
        return (base as NSString).deletingPathExtension
    }

    /// Restore every `<file>.anchor_bak` original over its live file and
    /// remove the sidecar. Returns the number of files restored. The live
    /// file keeps the backup's modification date (the engine's `copy2`)
    /// so mtime-fingerprinted pack sidecars don't churn.
    @discardableResult
    public static func restore(packRoot: URL) throws -> Int {
        let fm = FileManager.default
        var restored = 0
        let enumerator = fm.enumerator(at: packRoot,
                                       includingPropertiesForKeys: nil)
        while let item = enumerator?.nextObject() as? URL {
            let name = item.lastPathComponent
            guard name.hasSuffix(backupSuffix) else { continue }
            let live = item.deletingLastPathComponent()
                .appendingPathComponent(String(name.dropLast(backupSuffix.count)))
            try Data(contentsOf: item).write(to: live)
            if let mtime = try? fm.attributesOfItem(atPath: item.path)[.modificationDate] {
                try? fm.setAttributes([.modificationDate: mtime],
                                      ofItemAtPath: live.path)
            }
            restored += 1
        }
        let sidecar = packRoot.appendingPathComponent(sidecarName)
        if fm.fileExists(atPath: sidecar.path) {
            try fm.removeItem(at: sidecar)
        }
        return restored
    }
}
