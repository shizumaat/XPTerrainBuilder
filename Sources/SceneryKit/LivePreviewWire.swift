import Foundation

// The map's "Live flight preview" (#2001, capability `live_preview`):
// the engine lists the installed texture squares of a viewport, with the
// mip each is shown at and what X-Plane holds there, and reads the mips
// (`Ortho4XP/src/o4_engine/live_preview_commands.py`, `O4_Live_Preview.py`);
// the app draws. The Qt window's `O4_Qt_Live_Preview.py` is the same.

/// One square of `live_preview_squares`: an Ortho4XP texture (16 × 16
/// slippy tiles, so its bounds are web-mercator and it draws without
/// reprojection), its stamp (changes when a finer tier lands) and the mip
/// size the map shows it at (its on-screen size in device pixels, up to
/// the file's full width).
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
    /// X-Plane still shows what was here before this file changed: the
    /// map hatches it, "reload to see" (`LivePreviewText`).
    public var stale = false

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
            square.stale = row["stale"]?.boolValue ?? false
            return square
        }
    }
}

/// One 1° tile of the reply's `tiles`: `own` (X-Plane draws its own
/// scenery there; the map's base imagery shows, marked) or `reload`
/// (our tile is installed, X-Plane loaded what was there before).
public struct O4LivePreviewTile: Sendable, Equatable {
    public let lat: Int
    public let lon: Int
    public let state: String

    public init(lat: Int, lon: Int, state: String) {
        self.lat = lat; self.lon = lon; self.state = state
    }

    /// The reply's `tiles`; a row without a state is skipped.
    public static func list(from result: O4JSON?) -> [O4LivePreviewTile] {
        (result?["tiles"]?.arrayValue ?? []).compactMap { row in
            guard let lat = row["lat"]?.intValue, let lon = row["lon"]?.intValue,
                  let state = row["state"]?.stringValue else { return nil }
            return O4LivePreviewTile(lat: lat, lon: lon, state: state)
        }
    }
}

/// `live_preview_mip`'s answer: the encoded JPEG/PNG, `pending` while the
/// engine reads a fine level on its worker (ask again), or `failed`.
public enum O4LivePreviewMip: Sendable, Equatable {
    case image(Data)
    case pending
    case failed

    public static func from(ok: Bool, result: O4JSON?) -> O4LivePreviewMip {
        guard ok else { return .failed }
        if result?["pending"]?.boolValue == true { return .pending }
        guard let text = result?["data"]?.stringValue, let data = Data(base64Encoded: text)
        else { return .failed }
        return .image(data)
    }
}

/// The images an app keeps, bounded in bytes, least recently listed
/// dropped first (`O4_Live_Preview.APP_CACHE_MB`, `ByteLRU`; a 4096 px
/// RGBA image is 64 MB). A square keeps its old image until the new one
/// arrives. `plan` is `O4_Live_Preview.fetch_plan`.
public struct LivePreviewCache<Image> {
    public static var limitMB: Int { 512 }
    /// The first image fetched for a square that shows nothing yet.
    public static var coarsePx: Int { 64 }

    private var entries: [String: (stamp: String, px: Int, bytes: Int, image: Image)] = [:]
    private var order: [String] = []
    public private(set) var bytes = 0
    public var budget = LivePreviewCache.limitMB << 20

    public init() {}

    public var count: Int { entries.count }

    public func image(_ key: String) -> Image? { entries[key]?.image }

    /// The held image's stamp and size.
    public func held(_ key: String) -> (stamp: String, px: Int)? {
        entries[key].map { ($0.stamp, $0.px) }
    }

    /// Is the held image this stamp, at least this size?
    public func isCurrent(_ square: O4LivePreviewSquare) -> Bool {
        guard let held = entries[square.key] else { return false }
        return held.stamp == square.stamp && held.px >= square.px
    }

    /// The fetches, in order: a `coarsePx` image for each square that
    /// shows nothing (nearest first), then each square not current at its
    /// own size. A square with an older image skips the coarse step.
    public func plan(_ rows: [O4LivePreviewSquare]) -> [(square: O4LivePreviewSquare, px: Int)] {
        var coarse: [(square: O4LivePreviewSquare, px: Int)] = []
        var fine: [(square: O4LivePreviewSquare, px: Int)] = []
        for square in rows where !isCurrent(square) {
            if entries[square.key] == nil, square.px > Self.coarsePx {
                coarse.append((square, Self.coarsePx))
            }
            fine.append((square, square.px))
        }
        return coarse + fine
    }

    /// The squares just listed move to the recent end.
    public mutating func touch(_ keys: [String]) {
        let listed = Set(keys).intersection(entries.keys)
        order.removeAll { listed.contains($0) }
        order.append(contentsOf: keys.filter { listed.contains($0) })
    }

    /// Keep `image` (`px` wide, `bytes` decoded) for `square`; the least
    /// recently used go while over `budget` (the newest always stays).
    public mutating func insert(_ square: O4LivePreviewSquare, _ image: Image, px: Int, bytes cost: Int) {
        remove(square.key)
        entries[square.key] = (square.stamp, px, cost, image)
        order.append(square.key)
        bytes += cost
        while bytes > budget, order.count > 1 {
            remove(order[0])
        }
    }

    private mutating func remove(_ key: String) {
        guard let old = entries.removeValue(forKey: key) else { return }
        bytes -= old.bytes
        order.removeAll { $0 == key }
    }

    public mutating func removeAll() {
        entries.removeAll()
        order.removeAll()
        bytes = 0
    }
}

extension OrthoEngineClient {
    /// The squares and marked tiles of a viewport (`live_preview_squares`);
    /// `pxPerDegree` is screen points per degree of longitude, `scale`
    /// device pixels per point. Empty from an engine without the command.
    public func livePreviewSquares(
        south: Double, west: Double, north: Double, east: Double,
        pxPerDegree: Double, scale: Double, sceneryDir: String,
        completion: @escaping @Sendable ([O4LivePreviewSquare], [O4LivePreviewTile]) -> Void
    ) {
        send(command: "live_preview_squares",
             arguments: ["south": south, "west": west, "north": north, "east": east,
                         "px_per_deg": pxPerDegree, "scale": scale,
                         "scenery_dir": sceneryDir]) { reply in
            guard reply.ok else { return completion([], []) }
            completion(O4LivePreviewSquare.list(from: reply.result),
                       O4LivePreviewTile.list(from: reply.result))
        }
    }

    /// One square's mip (`live_preview_mip`).
    public func livePreviewMip(path: String, px: Int,
                               completion: @escaping @Sendable (O4LivePreviewMip) -> Void) {
        send(command: "live_preview_mip", arguments: ["path": path, "px": px]) { reply in
            completion(O4LivePreviewMip.from(ok: reply.ok, result: reply.result))
        }
    }
}
