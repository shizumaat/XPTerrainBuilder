import Foundation

public struct GeoPoint: Sendable, Codable {
    public let lon: Double
    public let lat: Double

    public init(lon: Double, lat: Double) {
        self.lon = lon
        self.lat = lat
    }
}

/// Where a DSF actually PLACES things: object positions and polygon windings
/// by definition-table index. This is the placement layer the DEFN-only
/// reader skips — needed for exact landmark positions, LOAD_CENTER
/// computation and draped-polygon coverage.
public struct DSFGeometry: Sendable {
    public var definitions = DSFDefinitions()
    /// Object definition index -> every placement (lon, lat).
    public var objectPlacements: [Int: [GeoPoint]] = [:]
    /// Polygon definition index -> windings (outer ring first per command).
    public var polygonWindings: [Int: [[GeoPoint]]] = [:]
}

/// Full-file DSF parser: GEOD pools (16/32-bit, delta + run-length encoded,
/// SCAL-scaled) and the CMDS command stream, per the official DSF spec.
/// Raw values normalize by 65535 (16-bit) / 2^32-1 (32-bit) before scaling;
/// a scale multiplier of 0 means the raw value passes through — both
/// validated empirically against the reference install (decoded coordinates
/// must land inside the tile's sim/west..east/south..north bounds).
public enum DSFGeometryReader {

    /// Hard cap on how much of a (decompressed) DSF we'll hold in memory.
    static let maxBytes = 512 << 20

    public static func read(url: URL) -> DSFGeometry? {
        guard let handle = try? FileHandle(forReadingFrom: url),
              let head = try? handle.read(upToCount: 6) else { return nil }
        try? handle.close()
        let data: Data?
        if head.starts(with: DSFReader.sevenZipMagic) {
            data = SevenZip.readHead(of: url, maxBytes: maxBytes)
        } else {
            data = try? Data(contentsOf: url, options: .mappedIfSafe)
        }
        guard let data, data.count > 12 + 16 else { return nil }
        return parse(data)
    }

    static func parse(_ data: Data) -> DSFGeometry? {
        guard data.starts(with: DSFReader.rawMagic) else { return nil }
        var geometry = DSFGeometry()
        var pools: [Pool] = []
        var commands: Data? = nil

        // Atom walk. The trailing 16 bytes are the MD5 footer for complete
        // files; a truncated 7z head simply ends early.
        var offset = 12
        while offset + 8 <= data.count {
            let id = atomID(data, at: offset)
            let length = data.littleEndianInt32(at: offset + 4)
            guard length >= 8, offset + length <= data.count else { break }
            let body = data.subdata(in: data.startIndex + offset + 8..<data.startIndex + offset + length)
            switch id {
            case "DEFN", "NFED":
                let props = geometry.definitions.properties
                geometry.definitions = DSFReader.parseDefinitionAtom(body)
                geometry.definitions.properties = props
            case "HEAD", "DAEH":
                geometry.definitions.properties = DSFReader.parseHeadAtom(body)
            case "GEOD", "DOEG":
                pools = parsePools(body)
            case "CMDS", "SDMC":
                commands = body
            default:
                break
            }
            offset += length
        }

        let debug = ProcessInfo.processInfo.environment["XPSD_DEBUG_DSF"] != nil
        if debug { print("debug: pools=\(pools.count) cmdsBytes=\(commands?.count ?? -1)") }
        guard let commands, !pools.isEmpty else { return nil }
        guard walkCommands(commands, pools: pools, into: &geometry) else {
            if debug { print("debug: command walk derailed") }
            return nil
        }
        return geometry
    }

    static func atomID(_ data: Data, at offset: Int) -> String {
        String(decoding: data[data.startIndex + offset..<data.startIndex + offset + 4], as: UTF8.self)
    }

    // MARK: - Pools

    /// One coordinate pool with its first two planes decoded and scaled
    /// (longitude, latitude — later planes are parsed past but not kept).
    struct Pool {
        var lon: [Double] = []
        var lat: [Double] = []
        var count: Int { lon.count }
    }

    /// GEOD subatoms in file order: POOL/PO32 define pools, SCAL/SC32 the
    /// matching scales, paired by order per atom type. POOL SELECT indexes
    /// pools by their order of appearance within GEOD, both widths combined.
    static func parsePools(_ body: Data) -> [Pool] {
        struct RawPool {
            var planes: [[UInt32]]
            var is32: Bool
            var orderIndex: Int
        }
        var raw16: [RawPool] = [], raw32: [RawPool] = []
        var scales16: [[(Double, Double)]] = [], scales32: [[(Double, Double)]] = []
        var order: [(is32: Bool, index: Int)] = []

        var offset = 0
        while offset + 8 <= body.count {
            let id = atomID(body, at: offset)
            let length = body.littleEndianInt32(at: offset + 4)
            guard length >= 8, offset + length <= body.count else { break }
            let sub = body.subdata(in: body.startIndex + offset + 8..<body.startIndex + offset + length)
            switch id {
            case "POOL", "LOOP":
                if let planes = decodePlanes(sub, is32: false) {
                    order.append((false, raw16.count))
                    raw16.append(RawPool(planes: planes, is32: false, orderIndex: order.count - 1))
                } else {
                    if ProcessInfo.processInfo.environment["XPSD_DEBUG_DSF"] != nil {
                        print("debug: 16-bit pool #\(raw16.count) decode failed (\(sub.count) bytes)")
                    }
                    return []
                }
            case "PO32", "23OP":
                if let planes = decodePlanes(sub, is32: true) {
                    order.append((true, raw32.count))
                    raw32.append(RawPool(planes: planes, is32: true, orderIndex: order.count - 1))
                } else {
                    if ProcessInfo.processInfo.environment["XPSD_DEBUG_DSF"] != nil {
                        print("debug: 32-bit pool #\(raw32.count) decode failed (\(sub.count) bytes)")
                    }
                    return []
                }
            case "SCAL", "LACS":
                scales16.append(decodeScales(sub))
            case "SC32", "23CS":
                scales32.append(decodeScales(sub))
            default:
                break
            }
            offset += length
        }

        func scaled(_ pool: RawPool, scales: [[(Double, Double)]], poolIndex: Int) -> Pool {
            let scale = poolIndex < scales.count ? scales[poolIndex] : []
            let divisor = pool.is32 ? Double(UInt32.max) : 65535.0
            var result = Pool()
            for planeIndex in 0..<min(2, pool.planes.count) {
                let (multiplier, add) = planeIndex < scale.count ? scale[planeIndex] : (0, 0)
                let values = pool.planes[planeIndex].map { rawValue -> Double in
                    multiplier == 0 ? Double(rawValue)
                        : add + Double(rawValue) * multiplier / divisor
                }
                if planeIndex == 0 { result.lon = values } else { result.lat = values }
            }
            return result
        }

        var pools: [Pool] = []
        var seen16 = 0, seen32 = 0
        for slot in order {
            if slot.is32 {
                pools.append(scaled(raw32[slot.index], scales: scales32, poolIndex: seen32))
                seen32 += 1
            } else {
                pools.append(scaled(raw16[slot.index], scales: scales16, poolIndex: seen16))
                seen16 += 1
            }
        }
        return pools
    }

    /// Pool atom: uint32 point count, uint8 plane count, then per plane one
    /// encoding byte (bit 0 = differenced, bit 1 = run-length) and the data.
    static func decodePlanes(_ sub: Data, is32: Bool) -> [[UInt32]]? {
        var reader = ByteReader(sub)
        guard let count32 = reader.u32(), let depth = reader.u8() else { return nil }
        let count = Int(count32)
        // Empty pools (real files carry them, even with depth 0) have no
        // per-plane data at all.
        if count == 0 { return Array(repeating: [], count: Int(depth)) }
        guard count < 4_000_000, depth > 0, depth <= 16 else {
            if ProcessInfo.processInfo.environment["XPSD_DEBUG_DSF"] != nil {
                print("debug: pool header rejected count=\(count) depth=\(depth)")
            }
            return nil
        }

        func readValue() -> UInt32? {
            is32 ? reader.u32() : reader.u16().map(UInt32.init)
        }
        let wrap: UInt64 = is32 ? 0x1_0000_0000 : 0x1_0000

        var planes: [[UInt32]] = []
        for _ in 0..<depth {
            guard let encoding = reader.u8(), encoding <= 3 else { return nil }
            var values: [UInt32] = []
            values.reserveCapacity(count)
            if encoding & 2 == 0 {
                for _ in 0..<count {
                    guard let value = readValue() else { return nil }
                    values.append(value)
                }
            } else {
                // Run-length: high bit set = one value repeated (n & 0x7f)
                // times; clear = n individual values.
                while values.count < count {
                    guard let run = reader.u8() else { return nil }
                    if run & 0x80 != 0 {
                        guard let value = readValue() else { return nil }
                        values.append(contentsOf: repeatElement(value, count: Int(run & 0x7f)))
                    } else {
                        for _ in 0..<Int(run) {
                            guard let value = readValue() else { return nil }
                            values.append(value)
                        }
                    }
                }
                guard values.count == count else { return nil }
            }
            if encoding & 1 != 0 {
                var accumulator: UInt64 = 0
                for i in values.indices {
                    accumulator = (accumulator + UInt64(values[i])) % wrap
                    values[i] = UInt32(accumulator)
                }
            }
            planes.append(values)
        }
        return planes
    }

    static func decodeScales(_ sub: Data) -> [(Double, Double)] {
        var reader = ByteReader(sub)
        var scales: [(Double, Double)] = []
        while let multiplier = reader.f32(), let offset = reader.f32() {
            scales.append((Double(multiplier), Double(offset)))
        }
        return scales
    }

    // MARK: - Commands

    /// Command stream walk per the DSF spec's numeric IDs. Unknown command =
    /// the stream is derailed; give up rather than harvest garbage.
    static func walkCommands(_ body: Data, pools: [Pool], into geometry: inout DSFGeometry) -> Bool {
        var reader = ByteReader(body)
        var currentPool = 0
        var currentDefinition = 0

        func point(_ index: Int) -> GeoPoint? {
            guard currentPool < pools.count else { return nil }
            let pool = pools[currentPool]
            guard index < pool.count, index < pool.lat.count else { return nil }
            return GeoPoint(lon: pool.lon[index], lat: pool.lat[index])
        }
        // removeValue (not subscript-read) hands the array over UNIQUELY
        // referenced, so append stays amortized O(1). Reading it while the
        // dictionary also held it made every append clone the definition's
        // whole accumulated array — quadratic, and a dense forest/city tile
        // with 100k+ windings ground a single pack for hours.
        func addObjects<S: Sequence<Int>>(_ indices: S) {
            var points = geometry.objectPlacements.removeValue(forKey: currentDefinition) ?? []
            for index in indices {
                if let p = point(index) { points.append(p) }
            }
            geometry.objectPlacements[currentDefinition] = points
        }
        func addWindings(_ windings: [[Int]]) {
            var existing = geometry.polygonWindings.removeValue(forKey: currentDefinition) ?? []
            for winding in windings {
                existing.append(winding.compactMap(point))
            }
            geometry.polygonWindings[currentDefinition] = existing
        }

        let debug = ProcessInfo.processInfo.environment["XPSD_DEBUG_DSF"] != nil
        var trace: [(UInt8, Int)] = []
        while let command = reader.u8() {
            if debug {
                trace.append((command, reader.offset - 1))
                if trace.count > 12 { trace.removeFirst() }
            }
            switch command {
            case 1: // POOL SELECT
                guard let index = reader.u16() else { return false }
                currentPool = Int(index)
            case 2: // JUNCTION OFFSET SELECT
                guard reader.skip(4) else { return false }
            case 3:
                guard let d = reader.u8() else { return false }
                currentDefinition = Int(d)
            case 4:
                guard let d = reader.u16() else { return false }
                currentDefinition = Int(d)
            case 5:
                guard let d = reader.u32() else { return false }
                currentDefinition = Int(d)
            case 6: // SET ROAD SUBTYPE
                guard reader.skip(1) else { return false }
            case 7: // OBJECT
                guard let index = reader.u16() else { return false }
                addObjects(CollectionOfOne(Int(index)))
            case 8: // OBJECT RANGE (end exclusive)
                guard let first = reader.u16(), let end = reader.u16() else { return false }
                if first < end { addObjects(Int(first)..<Int(end)) }
            case 9: // NETWORK CHAIN
                guard let n = reader.u8(), reader.skip(Int(n) * 2) else { return false }
            case 10: // NETWORK CHAIN RANGE
                guard reader.skip(4) else { return false }
            case 11: // NETWORK CHAIN 32
                guard let n = reader.u8(), reader.skip(Int(n) * 4) else { return false }
            case 12: // POLYGON
                guard let _ = reader.u16(), let n = reader.u8() else { return false }
                var indices: [Int] = []
                for _ in 0..<Int(n) {
                    guard let index = reader.u16() else { return false }
                    indices.append(Int(index))
                }
                addWindings([indices])
            case 13: // POLYGON RANGE (end exclusive)
                guard let _ = reader.u16(), let first = reader.u16(), let end = reader.u16()
                else { return false }
                if first < end { addWindings([Array(Int(first)..<Int(end))]) }
            case 14: // NESTED POLYGON
                guard let _ = reader.u16(), let windingCount = reader.u8() else { return false }
                var windings: [[Int]] = []
                for _ in 0..<Int(windingCount) {
                    guard let n = reader.u8() else { return false }
                    var indices: [Int] = []
                    for _ in 0..<Int(n) {
                        guard let index = reader.u16() else { return false }
                        indices.append(Int(index))
                    }
                    windings.append(indices)
                }
                addWindings(windings)
            case 15: // NESTED POLYGON RANGE: count byte = windings, then
                     // count+1 uint16 fence posts (validated against real
                     // tiles — the spec's phrasing is ambiguous here)
                guard let _ = reader.u16(), let windingCount = reader.u8() else { return false }
                var posts: [Int] = []
                for _ in 0..<(Int(windingCount) + 1) {
                    guard let index = reader.u16() else { return false }
                    posts.append(Int(index))
                }
                var windings: [[Int]] = []
                for i in 0..<max(0, posts.count - 1) {
                    if posts[i] < posts[i + 1] { windings.append(Array(posts[i]..<posts[i + 1])) }
                }
                addWindings(windings)
            case 16: // TERRAIN PATCH
                break
            case 17:
                guard reader.skip(1) else { return false }
            case 18:
                guard reader.skip(9) else { return false }
            case 23, 26, 29: // PATCH TRIANGLE / STRIP / FAN
                guard let n = reader.u8(), reader.skip(Int(n) * 2) else { return false }
            case 24, 27, 30: // ... CROSS-POOL: (pool, index) pairs
                guard let n = reader.u8(), reader.skip(Int(n) * 4) else { return false }
            case 25, 28, 31: // ... RANGE
                guard reader.skip(4) else { return false }
            case 32:
                guard let n = reader.u8(), reader.skip(Int(n)) else { return false }
            case 33:
                guard let n = reader.u16(), reader.skip(Int(n)) else { return false }
            case 34:
                guard let n = reader.u32(), reader.skip(Int(n)) else { return false }
            default:
                if debug {
                    print("debug: unknown command \(command) at cmds offset \(reader.offset - 1)")
                    print("debug: trace \(trace.map { "\($0.0)@\($0.1)" }.joined(separator: " "))")
                }
                return false // unknown command: derailed
            }
        }
        return true
    }
}

/// Little-endian cursor over a Data blob.
struct ByteReader {
    private let bytes: [UInt8]
    private(set) var offset = 0

    init(_ data: Data) { bytes = [UInt8](data) }

    var remaining: Int { bytes.count - offset }

    mutating func u8() -> UInt8? {
        guard offset < bytes.count else { return nil }
        defer { offset += 1 }
        return bytes[offset]
    }

    mutating func u16() -> UInt16? {
        guard offset + 2 <= bytes.count else { return nil }
        defer { offset += 2 }
        return UInt16(bytes[offset]) | (UInt16(bytes[offset + 1]) << 8)
    }

    mutating func u32() -> UInt32? {
        guard offset + 4 <= bytes.count else { return nil }
        defer { offset += 4 }
        return UInt32(bytes[offset]) | (UInt32(bytes[offset + 1]) << 8)
            | (UInt32(bytes[offset + 2]) << 16) | (UInt32(bytes[offset + 3]) << 24)
    }

    mutating func f32() -> Float? {
        u32().map { Float(bitPattern: $0) }
    }

    mutating func skip(_ count: Int) -> Bool {
        guard count >= 0, offset + count <= bytes.count else { return false }
        offset += count
        return true
    }
}
