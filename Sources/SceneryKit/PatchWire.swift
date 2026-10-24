import Foundation

// Reply types of the patch-editor commands, protocol 1.12
// (Ortho4XP/docs/specs/patch-editor-20261015.md §2 — a FROZEN contract).
// The command names and JSON keys are STRING LITERALS matched against the
// engine's `o4_engine/jsonl.py` handlers; `PatchWireTests` is the drift
// alarm. Binary arrays travel as base64 of little-endian packed values.

/// Protocol-version comparisons for commands an older engine lacks (it
/// answers "unknown command", so the feature is simply not offered).
public enum O4ProtocolVersion {
    /// True when `version` ("1.12") is at least `major.minor`.
    public static func isAtLeast(_ version: String, _ major: Int, _ minor: Int) -> Bool {
        let parts = version.split(separator: ".").map { Int($0) ?? 0 }
        guard parts.count >= 2 else { return false }
        return (parts[0], parts[1]) >= (major, minor)
    }

    /// The patch editor's commands exist from protocol 1.12.
    public static func supportsPatchEditor(_ version: String) -> Bool {
        isAtLeast(version, 1, 12)
    }
}

/// An `ok: false` reply: the engine's sentence naming the cause and the fix.
public struct O4CommandError: Error, Equatable, Sendable, CustomStringConvertible {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var description: String { message }
}

extension O4JSON {
    /// The value as a Foundation object, for JSONSerialization.
    public var foundationValue: Any {
        switch self {
        case .null: return NSNull()
        case .bool(let b): return b
        case .int(let i): return i
        case .double(let d): return d
        case .string(let s): return s
        case .array(let a): return a.map(\.foundationValue)
        case .object(let o): return o.mapValues(\.foundationValue)
        }
    }

    /// Decode a command result into a `Decodable` reply type. Snake-case
    /// wire keys are spelled out in each type's CodingKeys: a key strategy
    /// would also rewrite tag and header KEYS (`alt_abs` → `altAbs`).
    public func decode<T: Decodable>(_ type: T.Type) throws -> T {
        let data = try JSONSerialization.data(
            withJSONObject: foundationValue, options: [.fragmentsAllowed])
        return try JSONDecoder().decode(T.self, from: data)
    }
}

/// Little-endian packed arrays carried as base64 strings.
public enum O4Binary {
    public static func float32(base64: String) throws -> [Float] {
        try unpack(base64, as: UInt32.self).map { Float(bitPattern: $0) }
    }

    public static func float64(base64: String) throws -> [Double] {
        try unpack(base64, as: UInt64.self).map { Double(bitPattern: $0) }
    }

    public static func uint32(base64: String) throws -> [UInt32] {
        try unpack(base64, as: UInt32.self)
    }

    private static func unpack<T: FixedWidthInteger>(_ base64: String, as: T.Type) throws -> [T] {
        guard let data = Data(base64Encoded: base64) else {
            throw O4CommandError("The engine sent a binary array that is not base64.")
        }
        let width = MemoryLayout<T>.size
        guard data.count % width == 0 else {
            throw O4CommandError("The engine sent a binary array of \(data.count) bytes, not a multiple of \(width).")
        }
        return data.withUnsafeBytes { raw in
            (0..<(data.count / width)).map {
                T(littleEndian: raw.loadUnaligned(fromByteOffset: $0 * width, as: T.self))
            }
        }
    }
}

/// A [min_lat, min_lon, max_lat, max_lon] box in degrees.
public struct O4LatLonBox: Codable, Equatable, Sendable {
    public var minLat: Double
    public var minLon: Double
    public var maxLat: Double
    public var maxLon: Double

    public init(minLat: Double, minLon: Double, maxLat: Double, maxLon: Double) {
        self.minLat = minLat; self.minLon = minLon
        self.maxLat = maxLat; self.maxLon = maxLon
    }

    public init(from decoder: Decoder) throws {
        var c = try decoder.unkeyedContainer()
        minLat = try c.decode(Double.self); minLon = try c.decode(Double.self)
        maxLat = try c.decode(Double.self); maxLon = try c.decode(Double.self)
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.unkeyedContainer()
        try c.encode(minLat); try c.encode(minLon); try c.encode(maxLat); try c.encode(maxLon)
    }

    /// The wire form, for command arguments.
    public var wireArray: [Double] { [minLat, minLon, maxLat, maxLon] }

    public func contains(_ other: O4LatLonBox) -> Bool {
        minLat <= other.minLat && minLon <= other.minLon && maxLat >= other.maxLat && maxLon >= other.maxLon
    }

    public func intersects(_ other: O4LatLonBox) -> Bool {
        minLat <= other.maxLat && other.minLat <= maxLat
            && minLon <= other.maxLon && other.minLon <= maxLon
    }
}

/// Where a patch comes from: the engine's auto patch or a manual file
/// (an editor-saved `<ICAO>_edited.patch.osm` or a hand-made JOSM patch).
public enum O4PatchSource: String, Codable, Sendable {
    case auto
    case manual
}

// MARK: - patch_list / patch_load / patch_save / patch_revert

public struct O4PatchListEntry: Codable, Equatable, Sendable {
    public let icao: String
    public let source: O4PatchSource
    public let path: String
    public let bbox: O4LatLonBox
    public let nodes: Int
    public let ways: Int
}

public struct O4PatchList: Codable, Equatable, Sendable {
    public let airports: [O4PatchListEntry]

    public init(airports: [O4PatchListEntry]) { self.airports = airports }

    private enum CodingKeys: String, CodingKey { case airports }

    /// Decodes entry by entry: one malformed entry (e.g. a null bbox from an
    /// empty patch) is dropped and logged, never the whole listing.
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        var list = try c.nestedUnkeyedContainer(forKey: .airports)
        var kept: [O4PatchListEntry] = []
        while !list.isAtEnd {
            do {
                kept.append(try list.decode(O4PatchListEntry.self))
            } catch {
                _ = try? list.decode(SkippedEntry.self)
                NSLog("patch_list: dropped an undecodable entry: \(error)")
            }
        }
        airports = kept
    }

    private struct SkippedEntry: Decodable {}
}

/// One `[id, lat, lon, alt_or_null]` node row.
public struct O4PatchNodeRow: Codable, Equatable, Sendable {
    public let id: Int64
    public let lat: Double
    public let lon: Double
    public let alt: Double?

    public init(id: Int64, lat: Double, lon: Double, alt: Double?) {
        self.id = id; self.lat = lat; self.lon = lon; self.alt = alt
    }

    public init(from decoder: Decoder) throws {
        var c = try decoder.unkeyedContainer()
        id = try c.decode(Int64.self)
        lat = try c.decode(Double.self)
        lon = try c.decode(Double.self)
        alt = try c.decodeIfPresent(Double.self)
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.unkeyedContainer()
        try c.encode(id); try c.encode(lat); try c.encode(lon)
        if let alt { try c.encode(alt) } else { try c.encodeNil() }
    }

    /// The wire form, for `patch_save`.
    public var wireArray: [Any] { [id, lat, lon, alt.map { $0 as Any } ?? NSNull()] }
}

public struct O4PatchWayRow: Codable, Equatable, Sendable {
    public let id: Int64
    public let refs: [Int64]
    public let tags: [String: String]

    public init(id: Int64, refs: [Int64], tags: [String: String]) {
        self.id = id; self.refs = refs; self.tags = tags
    }

    /// The wire form, for `patch_save`.
    public var wireObject: [String: Any] { ["id": id, "refs": refs, "tags": tags] }
}

public struct O4PatchLoad: Codable, Equatable, Sendable {
    public let icao: String
    public let source: O4PatchSource
    public let path: String
    public let stale: Bool
    public let staleInputs: [String]
    public let minDistinctSpacingM: Double
    public let identityDp: Int
    public let header: [String: String]
    public let nodes: [O4PatchNodeRow]
    public let ways: [O4PatchWayRow]

    private enum CodingKeys: String, CodingKey {
        case icao, source, path, stale, header, nodes, ways
        case staleInputs = "stale_inputs"
        case minDistinctSpacingM = "min_distinct_spacing_m"
        case identityDp = "identity_dp"
    }
}

public struct O4PatchSaveReply: Codable, Equatable, Sendable {
    public let path: String
    public let nodes: Int
    public let ways: Int
}

public struct O4PatchRevertReply: Codable, Equatable, Sendable {
    public let disabledPath: String

    private enum CodingKeys: String, CodingKey { case disabledPath = "disabled_path" }
}

// MARK: - pack_outlines

/// One `[lat, lon]` point.
public struct O4LatLon: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double

    public init(lat: Double, lon: Double) {
        self.lat = lat; self.lon = lon
    }

    public init(from decoder: Decoder) throws {
        var c = try decoder.unkeyedContainer()
        lat = try c.decode(Double.self)
        lon = try c.decode(Double.self)
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.unkeyedContainer()
        try c.encode(lat); try c.encode(lon)
    }
}

/// The pack's own apt.dat pavement (row 110) and boundary (row 130), as
/// amended before L4: no `footprints` — the map draws buildings from
/// `pack_objects` (`PackFootprints`).
public struct O4PackOutlines: Codable, Equatable, Sendable {
    public struct Pavement: Codable, Equatable, Sendable {
        /// "pavement" or "boundary".
        public let kind: String
        /// Exterior first, then the holes.
        public let rings: [[O4LatLon]]
    }

    public let pavement: [Pavement]
    public let missing: [String]
}

// MARK: - terrain_sample / mesh_crop / pack_objects (binary payloads)

public struct O4TerrainSample: Decodable, Equatable, Sendable {
    public let bbox: O4LatLonBox
    public let rows: Int
    public let cols: Int
    public let spacingM: Double
    public let dlat: Double
    public let dlon: Double
    /// Row-major, row 0 = south edge; `rows * cols` values.
    public let elevations: [Float]
    public let sources: [String: String?]

    private enum CodingKeys: String, CodingKey {
        case bbox, rows, cols, dlat, dlon, sources
        case spacingM = "spacing_m", elevF32B64 = "elev_f32_b64"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        bbox = try c.decode(O4LatLonBox.self, forKey: .bbox)
        rows = try c.decode(Int.self, forKey: .rows)
        cols = try c.decode(Int.self, forKey: .cols)
        spacingM = try c.decode(Double.self, forKey: .spacingM)
        dlat = try c.decode(Double.self, forKey: .dlat)
        dlon = try c.decode(Double.self, forKey: .dlon)
        elevations = try O4Binary.float32(base64: c.decode(String.self, forKey: .elevF32B64))
        // §2 names the keys (base, inset) but not their value type.
        sources = (try? c.decodeIfPresent([String: String?].self, forKey: .sources)) ?? [:]
        guard elevations.count == rows * cols else {
            throw O4CommandError("terrain_sample sent \(elevations.count) values for a \(rows) × \(cols) grid.")
        }
    }
}

public struct O4MeshCrop: Decodable, Equatable, Sendable {
    public let meshPath: String
    /// (lon, lat, elev) triples.
    public let vertices: [Double]
    public let triangles: [UInt32]

    private enum CodingKeys: String, CodingKey {
        case meshPath = "mesh_path", verticesF64B64 = "vertices_f64_b64"
        case trianglesU32B64 = "triangles_u32_b64"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        meshPath = try c.decode(String.self, forKey: .meshPath)
        vertices = try O4Binary.float64(base64: c.decode(String.self, forKey: .verticesF64B64))
        triangles = try O4Binary.uint32(base64: c.decode(String.self, forKey: .trianglesU32B64))
    }
}

public struct O4PackObjects: Decodable, Equatable, Sendable {
    public struct Model: Decodable, Equatable, Sendable {
        public let key: String
        /// Authored (x, y, z) metres, triples (empty in a footprints-only answer).
        public let vertices: [Float]
        public let triangles: [UInt32]
        /// The plan outline, authored (x, z) pairs — a footprints-only
        /// answer's model carries this instead of the massing (#797).
        public let planHull: [Float]

        private enum CodingKeys: String, CodingKey {
            case key, verticesF32B64 = "vertices_f32_b64", trianglesU32B64 = "triangles_u32_b64"
            case planHullF32B64 = "plan_hull_f32_b64"
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            key = try c.decode(O4WireKey.self, forKey: .key).value
            vertices = try c.decodeIfPresent(String.self, forKey: .verticesF32B64)
                .map { try O4Binary.float32(base64: $0) } ?? []
            triangles = try c.decodeIfPresent(String.self, forKey: .trianglesU32B64)
                .map { try O4Binary.uint32(base64: $0) } ?? []
            planHull = try c.decodeIfPresent(String.self, forKey: .planHullF32B64)
                .map { try O4Binary.float32(base64: $0) } ?? []
        }
    }

    public struct Placement: Decodable, Equatable, Sendable {
        public let model: String
        public let lat: Double
        public let lon: Double
        public let headingDeg: Double
        public let aglM: Double

        private enum CodingKeys: String, CodingKey {
            case model, lat, lon, headingDeg = "heading_deg", aglM = "agl_m"
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            model = try c.decode(O4WireKey.self, forKey: .model).value
            lat = try c.decode(Double.self, forKey: .lat)
            lon = try c.decode(Double.self, forKey: .lon)
            headingDeg = try c.decode(Double.self, forKey: .headingDeg)
            aglM = try c.decode(Double.self, forKey: .aglM)
        }
    }

    public struct Facade: Decodable, Equatable, Sendable {
        public let ring: [O4LatLon]
        public let heightM: Double

        private enum CodingKeys: String, CodingKey { case ring, heightM = "height_m" }
    }

    public let models: [Model]
    public let placements: [Placement]
    public let facades: [Facade]
    public let missing: [String]
}

/// A model key: §2 does not fix its JSON type, so a number or a string
/// is accepted and kept as a string.
private struct O4WireKey: Decodable {
    let value: String

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { value = s }
        else { value = String(try c.decode(Int64.self)) }
    }
}

/// Resumes a continuation exactly once, whichever of a command's reply
/// and its completion event gets there first (`packObjects`).
final class O4ResumeOnce<T: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<T, Error>?

    func set(_ continuation: CheckedContinuation<T, Error>) {
        lock.withLock { self.continuation = continuation }
    }

    func resume(_ result: Result<T, Error>) {
        let c: CheckedContinuation<T, Error>? = lock.withLock {
            defer { continuation = nil }
            return continuation
        }
        c?.resume(with: result)
    }
}
