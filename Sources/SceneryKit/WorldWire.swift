import Foundation

/// The World pack (flight manager / World spec 2026-11-10, capability
/// `world_pack`): ONE Custom Scenery pack, `zXPTerrainBuilder World`, holds
/// every tile the app manages and an empty overlay placeholder DSF where
/// none is built. The names are STRING LITERALS matched against
/// `Ortho4XP/src/O4_World_Pack.py` (`PACK_NAME`, `PLACEHOLDER_AGENT`,
/// `PLACEHOLDER_MAX_BYTES`).
public enum O4WorldPack {
    public static let packName = "zXPTerrainBuilder World"
    /// The app's overlay pack (#2021, RULINGS 2026-11-12e): X-Plane's own
    /// roads, forests and buildings for every full tile, its ini row
    /// directly above the World pack's (`O4_Overlay_Pack.PACK_NAME`).
    public static let overlaysPackName = "yXPTerrainBuilder Overlays"
    /// The legacy overlay link (`yOrtho4XP_Overlays`) and per-tile /
    /// grouped-build links (`zOrtho4XP_…`): ours too.
    static let legacyOverlaysPackName = "yOrtho4XP_Overlays"
    static let tileLinkPrefix = "zOrtho4XP_"

    /// Is the Custom Scenery entry `name` one of this app's own packs —
    /// never "Other scenery", never a third-party pack? The mirror of
    /// `O4_Custom_Scenery._is_our_pack`; both read the cases of
    /// `Ortho4XP/tests/fixtures/world_pane_cases.json`.
    public static func isOurs(_ name: String) -> Bool {
        name.hasPrefix(tileLinkPrefix)
            || [packName, overlaysPackName, legacyOverlaysPackName].contains(name)
    }

    /// `sim/creation_agent` of a placeholder DSF.
    public static let placeholderAgent = "XPTerrainBuilder world placeholder"
    /// A placeholder is 328 bytes; a larger DSF is never one.
    public static let placeholderMaxBytes = 4096

    /// Is the DSF at `url` (of `size` bytes, when the caller has it from a
    /// listing) a World-pack placeholder — NOT a tile (spec §18)? Reads
    /// the head of small files only.
    public static func isPlaceholder(_ url: URL, size: Int?) -> Bool {
        if let size, size > placeholderMaxBytes { return false }
        guard let handle = try? FileHandle(forReadingFrom: url) else { return false }
        defer { try? handle.close() }
        let head = (try? handle.read(upToCount: placeholderMaxBytes)) ?? Data()
        return head.range(of: Data(placeholderAgent.utf8)) != nil
    }
}

/// The World pack's state (engine `WorldStatus`, spec §5.3): emitted when
/// the pack changes and, once build-ahead runs, every ~2 s. The field
/// names are the JSON keys of `class WorldStatus` in
/// `Ortho4XP/src/o4_engine/events.py`; `world_status` replies the same
/// fields plus `regions`.
public struct O4WorldStatus: Sendable, Equatable {
    /// One row of `regions` (`world_status` only).
    public struct Region: Sendable, Equatable {
        public let id: String
        public let name: String
        public let enabled: Bool
        public let placeholders: Int
        public let tiles: Int
    }

    /// One row of `building` (W2 build-ahead): a tile being built.
    public struct Building: Sendable, Equatable {
        public let tile: String
        public let kind: String
        public let step: String
        public let remainingS: Int
    }

    public let state: String
    public let reason: String
    public let installed: Bool
    /// nil: unknown (X-Plane not running, or its log not read yet).
    public let seenByXPlane: Bool?
    public let restartNeeded: Bool
    /// `placeholder`, `drape`, `full`, `staged` counts.
    public let tiles: [String: Int]
    public let queue: Int
    public let building: [Building]
    /// Build-ahead's tiles in track mode, `FlightStatus.jobs`' rows
    /// (`[[lat, lon], "ahead", kind, state]`): the Fly map in free flight.
    public var jobs: [O4FlightStatus.Job] = []
    /// The aircraft's own tile while build-ahead runs (`fly_here`): the
    /// Fly pane's "Preparing imagery at ..." (`FlyText.hereLines`, #2020).
    public var here: O4JSON?
    public let loaded: [String]
    /// `[tile, kind, utc]`, empty before the first swap.
    public let lastSwap: [String]
    public let slots: Int
    public let frameMS: Double
    public let governor: String
    public let bytes: Int64
    public let regions: [Region]

    /// Parses a `WorldStatus` event object or a `world_status` reply.
    public static func parse(_ object: [String: Any]) -> O4WorldStatus {
        func int(_ key: String) -> Int { (object[key] as? NSNumber)?.intValue ?? 0 }
        let counts = (object["tiles"] as? [String: Any] ?? [:])
            .compactMapValues { ($0 as? NSNumber)?.intValue }
        let regions = (object["regions"] as? [Any] ?? []).compactMap { item -> Region? in
            guard let row = item as? [String: Any] else { return nil }
            return Region(
                id: row["id"] as? String ?? "",
                name: row["name"] as? String ?? "",
                enabled: (row["enabled"] as? NSNumber)?.boolValue ?? false,
                placeholders: (row["placeholders"] as? NSNumber)?.intValue ?? 0,
                tiles: (row["tiles"] as? NSNumber)?.intValue ?? 0)
        }
        let building = (object["building"] as? [Any] ?? []).compactMap { item -> Building? in
            guard let row = item as? [Any], row.count >= 4 else { return nil }
            return Building(tile: row[0] as? String ?? "", kind: row[1] as? String ?? "",
                            step: row[2] as? String ?? "",
                            remainingS: (row[3] as? NSNumber)?.intValue ?? 0)
        }
        var status = O4WorldStatus(
            state: object["state"] as? String ?? "off",
            reason: object["reason"] as? String ?? "",
            installed: (object["installed"] as? NSNumber)?.boolValue ?? false,
            seenByXPlane: (object["seen_by_xplane"] as? NSNumber)?.boolValue,
            restartNeeded: (object["restart_needed"] as? NSNumber)?.boolValue ?? false,
            tiles: counts,
            queue: int("queue"),
            building: building,
            loaded: (object["loaded"] as? [Any] ?? []).compactMap { $0 as? String },
            lastSwap: (object["last_swap"] as? [Any] ?? []).compactMap { $0 as? String },
            slots: int("slots"),
            frameMS: (object["frame_ms"] as? NSNumber)?.doubleValue ?? 0,
            governor: object["governor"] as? String ?? "ok",
            bytes: (object["bytes"] as? NSNumber)?.int64Value ?? 0,
            regions: regions)
        status.jobs = jobRows(object["jobs"])
        if let here = object["here"] as? [String: Any] { status.here = O4JSON.from(here) }
        return status
    }

    /// `jobs` rows from the event's decoded JSON.
    static func jobRows(_ value: Any?) -> [O4FlightStatus.Job] {
        (value as? [Any] ?? []).compactMap { item in
            guard let row = item as? [Any], row.count >= 4, let tile = row[0] as? [Any],
                  tile.count == 2, let lat = (tile[0] as? NSNumber)?.intValue,
                  let lon = (tile[1] as? NSNumber)?.intValue else { return nil }
            return O4FlightStatus.Job(lat: lat, lon: lon, role: row[1] as? String ?? "",
                                      kind: row[2] as? String ?? "", state: row[3] as? String ?? "",
                                      remainingSeconds: nil, marginSeconds: nil)
        }
    }
}
