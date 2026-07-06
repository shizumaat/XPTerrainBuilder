import Foundation

/// The resource definition tables of a DSF tile: every terrain, object,
/// polygon and network file the tile can reference. Paths are as written by
/// the compiler — pack-relative for local resources, virtual paths for
/// library ones.
public struct DSFDefinitions: Sendable {
    public var terrains: [String] = []
    public var objects: [String] = []
    public var polygons: [String] = []
    public var networks: [String] = []
    public var rasters: [String] = []
    /// HEAD/PROP key-value pairs (sim/overlay, sim/west, …).
    public var properties: [String: String] = [:]

    public var isOverlay: Bool? {
        properties["sim/overlay"].map { $0 == "1" }
    }

    /// Every resource-file reference in the definition tables.
    public var allResources: [String] {
        terrains + objects + polygons + networks
    }
}

public enum DSFReadResult: Sendable {
    case ok(DSFDefinitions)
    /// 7z-compressed DSF and libarchive was unavailable — normally 7z tiles
    /// decode in-process via SevenZip.
    case compressed
    case invalid
}

/// Reads just the DEFN atom of a DSF file.
///
/// DSF is `"XPLNEDSF" + int32 version`, then a sequence of atoms
/// `[4-byte id][int32 total length incl. 8-byte header]`, ending with a
/// 16-byte MD5 footer. The DEFN atom (subatoms TERT/OBJT/POLY/NETW/DEMN,
/// each a run of NUL-terminated strings) is a few KB near the front, so the
/// reader seeks over everything else — installs can hold >150k tiles and
/// whole-file reads would be hundreds of gigabytes.
public enum DSFReader {
    static let rawMagic = Data("XPLNEDSF".utf8)
    static let sevenZipMagic = Data([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])

    public static func readDefinitions(url: URL) -> DSFReadResult {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return .invalid }
        defer { try? handle.close() }
        guard let fileSize = (try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? Int,
              fileSize > 12 + 16
        else { return .invalid }

        guard let header = try? handle.read(upToCount: 12), header.count == 12 else { return .invalid }
        if header.starts(with: sevenZipMagic) {
            return readCompressedDefinitions(url: url)
        }
        guard header.starts(with: rawMagic) else { return .invalid }

        let atomsEnd = fileSize - 16 // MD5 footer
        var offset = 12
        var defs = DSFDefinitions()
        var sawDEFN = false

        while offset + 8 <= atomsEnd {
            guard let atomHeader = try? handle.read(upToCount: 8), atomHeader.count == 8 else { return .invalid }
            let id = String(decoding: atomHeader.prefix(4), as: UTF8.self)
            let length = atomHeader.littleEndianInt32(at: 4)
            guard length >= 8, offset + length <= atomsEnd + 16 else { return .invalid }

            if id == "DEFN" || id == "NFED" {
                guard let body = try? handle.read(upToCount: length - 8), body.count == length - 8 else {
                    return .invalid
                }
                let props = defs.properties
                defs = parseDefinitionAtom(body)
                defs.properties = props
                sawDEFN = true
                // HEAD precedes DEFN in practice; if we have both, stop early.
                if !defs.properties.isEmpty { return .ok(defs) }
            } else if id == "HEAD" || id == "DAEH" {
                guard let body = try? handle.read(upToCount: length - 8), body.count == length - 8 else {
                    return .invalid
                }
                defs.properties = parseHeadAtom(body)
                if sawDEFN { return .ok(defs) }
            }

            offset += length
            do {
                try handle.seek(toOffset: UInt64(offset))
            } catch {
                return .invalid
            }
        }
        return .ok(defs)
    }

    /// 7z-wrapped DSF (X-Plane accepts these; Global Forests ships 37k of
    /// them). HEAD and DEFN sit at the front, so decompressing a bounded head
    /// of the stream is enough — LZMA decodes sequentially and never touches
    /// the (huge) geometry tail. Two passes: 1 MB catches virtually every
    /// tile; a 16 MB retry covers meshes with oversized leading atoms.
    static func readCompressedDefinitions(url: URL) -> DSFReadResult {
        guard SevenZip.available else { return .compressed }
        for cap in [1 << 20, 16 << 20] {
            guard let data = SevenZip.readHead(of: url, maxBytes: cap) else { return .invalid }
            if let defs = parseAtoms(in: data) { return .ok(defs) }
            if data.count < cap { return .invalid } // whole entry read, no DEFN
        }
        return .invalid
    }

    /// Atom walk over in-memory data (same layout as the seeking reader).
    /// Returns nil if the data ends before both HEAD and DEFN were seen —
    /// callers retry with a larger head.
    static func parseAtoms(in data: Data) -> DSFDefinitions? {
        guard data.count > 12, data.starts(with: rawMagic) else { return nil }
        var offset = 12
        var defs = DSFDefinitions()
        var sawDEFN = false, sawHEAD = false

        while offset + 8 <= data.count {
            let id = String(decoding: data[data.startIndex + offset..<data.startIndex + offset + 4],
                            as: UTF8.self)
            let length = data.littleEndianInt32(at: offset + 4)
            // Garbage length: corrupt stream or we've walked into the MD5
            // footer of a fully-read entry — keep whatever we already have.
            guard length >= 8 else { break }
            let bodyEnd = offset + length
            // Atom runs past what we decompressed: only a problem if it's one
            // we still need.
            if bodyEnd > data.count {
                if !sawDEFN, ["DEFN", "NFED", "HEAD", "DAEH"].contains(id) { return nil }
                break
            }
            let body = data.subdata(in: data.startIndex + offset + 8..<data.startIndex + bodyEnd)
            if id == "DEFN" || id == "NFED" {
                let props = defs.properties
                defs = parseDefinitionAtom(body)
                defs.properties = props
                sawDEFN = true
            } else if id == "HEAD" || id == "DAEH" {
                defs.properties = parseHeadAtom(body)
                sawHEAD = true
            }
            if sawDEFN && sawHEAD { return defs }
            offset = bodyEnd
        }
        return sawDEFN ? defs : nil
    }

    /// HEAD atom: contains a PROP subatom of NUL-separated key/value pairs.
    static func parseHeadAtom(_ body: Data) -> [String: String] {
        var properties: [String: String] = [:]
        var offset = 0
        let bytes = [UInt8](body)
        while offset + 8 <= bytes.count {
            let id = String(decoding: bytes[offset..<offset + 4], as: UTF8.self)
            let length = Int(bytes[offset + 4])
                | (Int(bytes[offset + 5]) << 8)
                | (Int(bytes[offset + 6]) << 16)
                | (Int(bytes[offset + 7]) << 24)
            guard length >= 8, offset + length <= bytes.count else { break }
            if id == "PROP" || id == "PORP" {
                let strings = parseStringTable(bytes[(offset + 8)..<(offset + length)])
                var i = 0
                while i + 1 < strings.count {
                    properties[strings[i]] = strings[i + 1]
                    i += 2
                }
            }
            offset += length
        }
        return properties
    }

    static func parseDefinitionAtom(_ body: Data) -> DSFDefinitions {
        var defs = DSFDefinitions()
        var offset = 0
        let bytes = [UInt8](body)

        while offset + 8 <= bytes.count {
            let id = String(decoding: bytes[offset..<offset + 4], as: UTF8.self)
            let length = Int(bytes[offset + 4])
                | (Int(bytes[offset + 5]) << 8)
                | (Int(bytes[offset + 6]) << 16)
                | (Int(bytes[offset + 7]) << 24)
            guard length >= 8, offset + length <= bytes.count else { break }

            let strings = parseStringTable(bytes[(offset + 8)..<(offset + length)])
            switch id {
            case "TERT", "TRET": defs.terrains = strings
            case "OBJT", "TJBO": defs.objects = strings
            case "POLY", "YLOP": defs.polygons = strings
            case "NETW", "WTEN": defs.networks = strings
            case "DEMN", "NMED": defs.rasters = strings
            default: break
            }
            offset += length
        }
        return defs
    }

    static func parseStringTable(_ slice: ArraySlice<UInt8>) -> [String] {
        var strings: [String] = []
        var current: [UInt8] = []
        for byte in slice {
            if byte == 0 {
                if !current.isEmpty {
                    strings.append(String(decoding: current, as: UTF8.self))
                    current = []
                }
            } else {
                current.append(byte)
            }
        }
        if !current.isEmpty {
            strings.append(String(decoding: current, as: UTF8.self))
        }
        return strings
    }
}

extension Data {
    func littleEndianInt32(at offset: Int) -> Int {
        guard count >= offset + 4 else { return 0 }
        return Int(self[startIndex + offset])
            | (Int(self[startIndex + offset + 1]) << 8)
            | (Int(self[startIndex + offset + 2]) << 16)
            | (Int(self[startIndex + offset + 3]) << 24)
    }
}
