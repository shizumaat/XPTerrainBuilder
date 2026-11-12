import Foundation

// The map's "Live flight preview" (#2001, capability `live_preview`):
// the engine lists the installed texture squares of a viewport and reads
// one small mip of each (`Ortho4XP/src/o4_engine/live_preview_commands.py`,
// `O4_Live_Preview.py`); the app draws. The Qt window's
// `O4_Qt_Live_Preview.py` is the same.

/// One square of `live_preview_squares`: an Ortho4XP texture (16 × 16
/// slippy tiles, so its bounds are web-mercator and it draws without
/// reprojection), its stamp (changes when a finer tier lands) and the mip
/// size to fetch at this zoom.
public struct O4LivePreviewSquare: Sendable, Equatable {
    public let key: String
    public let path: String
    public let stamp: String
    public let px: Int
    public let north: Double
    public let south: Double
    public let west: Double
    public let east: Double
    /// The installed file is at full resolution (`O4_Live_Preview`'s
    /// `sharp`): the map outlines it (#2020).
    public var sharp = false

    public init(key: String, path: String, stamp: String, px: Int,
                north: Double, south: Double, west: Double, east: Double) {
        self.key = key; self.path = path; self.stamp = stamp; self.px = px
        self.north = north; self.south = south; self.west = west; self.east = east
    }

    /// The reply's `squares`; a malformed row is skipped.
    public static func list(from result: O4JSON?) -> [O4LivePreviewSquare] {
        (result?["squares"]?.arrayValue ?? []).compactMap { row in
            guard let key = row["key"]?.stringValue, let path = row["path"]?.stringValue,
                  let north = row["north"]?.doubleValue, let south = row["south"]?.doubleValue,
                  let west = row["west"]?.doubleValue, let east = row["east"]?.doubleValue
            else { return nil }
            var square = O4LivePreviewSquare(key: key, path: path,
                                             stamp: row["stamp"]?.stringValue ?? "",
                                             px: row["px"]?.intValue ?? 256,
                                             north: north, south: south, west: west, east: east)
            square.sharp = row["sharp"]?.boolValue ?? false
            return square
        }
    }
}

/// The images an app keeps, least recently listed dropped first
/// (`O4_Live_Preview.APP_CACHE_IMAGES`; 256 px RGBA is 256 KB, so at
/// most 48 MB). A square keeps its old image until the new one arrives.
public struct LivePreviewCache<Image> {
    public static var limit: Int { 192 }

    private var entries: [String: (stamp: String, px: Int, image: Image)] = [:]
    private var order: [String] = []

    public init() {}

    public var count: Int { entries.count }

    public func image(_ key: String) -> Image? { entries[key]?.image }

    /// Is the held image this stamp, at least this size?
    public func isCurrent(_ square: O4LivePreviewSquare) -> Bool {
        guard let held = entries[square.key] else { return false }
        return held.stamp == square.stamp && held.px >= square.px
    }

    /// The squares just listed move to the recent end.
    public mutating func touch(_ keys: [String]) {
        let listed = Set(keys).intersection(entries.keys)
        order.removeAll { listed.contains($0) }
        order.append(contentsOf: keys.filter { listed.contains($0) })
    }

    public mutating func insert(_ square: O4LivePreviewSquare, _ image: Image) {
        entries[square.key] = (square.stamp, square.px, image)
        order.removeAll { $0 == square.key }
        order.append(square.key)
        while order.count > Self.limit {
            entries.removeValue(forKey: order.removeFirst())
        }
    }

    public mutating func removeAll() {
        entries.removeAll()
        order.removeAll()
    }
}

extension OrthoEngineClient {
    /// The installed texture squares of a viewport (`live_preview_squares`);
    /// `pxPerDegree` is screen pixels per degree of longitude. `[]` from an
    /// engine without the command.
    public func livePreviewSquares(
        south: Double, west: Double, north: Double, east: Double,
        pxPerDegree: Double, sceneryDir: String,
        completion: @escaping @Sendable ([O4LivePreviewSquare]) -> Void
    ) {
        send(command: "live_preview_squares",
             arguments: ["south": south, "west": west, "north": north, "east": east,
                         "px_per_deg": pxPerDegree, "scenery_dir": sceneryDir]) { reply in
            completion(reply.ok ? O4LivePreviewSquare.list(from: reply.result) : [])
        }
    }

    /// One square's mip (`live_preview_mip`): the encoded JPEG/PNG bytes,
    /// or nil (a texture being replaced, an engine without the command).
    public func livePreviewMip(path: String, px: Int,
                               completion: @escaping @Sendable (Data?) -> Void) {
        send(command: "live_preview_mip", arguments: ["path": path, "px": px]) { reply in
            guard reply.ok, let text = reply.result?["data"]?.stringValue else {
                completion(nil)
                return
            }
            completion(Data(base64Encoded: text))
        }
    }
}
